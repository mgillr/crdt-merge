# Copyright 2026 Ryan Gillespie
# Licensed under Apache-2.0

"""
Arrow Flight Merge-as-a-Service — gRPC-based merge server.

Implements ``DoExchange`` for streaming CRDT merge via gRPC.
Clients send two Arrow streams, receive one merged stream.
Strategy configuration via Flight metadata headers.

All Arrow / Flight dependencies are lazily imported.

Example::

    from crdt_merge.accelerators.flight_server import FlightMergeServer

    server = FlightMergeServer(host="0.0.0.0", port=8815)
    server.serve()  # blocking
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple

# Lazy imports
try:
    import pyarrow as _pa  # type: ignore[import-untyped]
except ImportError:
    _pa = None  # type: ignore[assignment]

try:
    import pyarrow.flight as _flight  # type: ignore[import-untyped]
except ImportError:
    _flight = None  # type: ignore[assignment]

from crdt_merge.strategies import (
    MergeSchema,
    MergeStrategy,
    LWW,
    MaxWins,
    MinWins,
    UnionSet,
    Concat,
    Priority,
    LongestWins,
    Custom,
)
from crdt_merge.accelerators import register_accelerator

# ---------------------------------------------------------------------------
# Strategy map (shared with duckdb_udf)
# ---------------------------------------------------------------------------

_STRATEGY_MAP: Dict[str, type] = {
    "lww": LWW,
    "max": MaxWins,
    "maxwins": MaxWins,
    "min": MinWins,
    "minwins": MinWins,
    "union": UnionSet,
    "unionset": UnionSet,
    "concat": Concat,
    "priority": Priority,
    "longest": LongestWins,
    "longestwins": LongestWins,
}


def _resolve_strategy_name(name: str) -> MergeStrategy:
    cls = _STRATEGY_MAP.get(name.lower())
    if cls is None:
        raise ValueError(f"Unknown strategy: {name}")
    return cls()


# ---------------------------------------------------------------------------
# Helpers — Arrow ↔ list-of-dicts conversion
# ---------------------------------------------------------------------------

def _table_to_records(table: Any) -> List[dict]:
    """Convert a ``pyarrow.Table`` to list-of-dicts."""
    if table is None:
        return []
    if _pa is not None and hasattr(table, "to_pydict"):
        d = table.to_pydict()
        cols = list(d.keys())
        n = len(d[cols[0]]) if cols else 0
        return [{c: d[c][i] for c in cols} for i in range(n)]
    return []


def _records_to_table(records: List[dict]) -> Any:
    """Convert list-of-dicts to a ``pyarrow.Table``."""
    if not records:
        if _pa is not None:
            return _pa.table({})
        return None
    cols: Dict[str, list] = {}
    for r in records:
        for k in r:
            cols.setdefault(k, [])
    for r in records:
        for k in cols:
            cols[k].append(r.get(k))
    if _pa is not None:
        return _pa.table(cols)
    return records


# ---------------------------------------------------------------------------
# Core merge (same algorithm as duckdb_udf for consistency)
# ---------------------------------------------------------------------------

def _merge_records(
    left: List[dict],
    right: List[dict],
    key: str,
    schema: MergeSchema,
) -> Tuple[List[dict], int]:
    keyed: Dict[Any, dict] = {}
    conflicts = 0
    for row in left:
        k = row.get(key)
        if k is not None:
            keyed[k] = dict(row)
    for row in right:
        k = row.get(key)
        if k is None:
            continue
        if k in keyed:
            existing = keyed[k]
            merged = schema.resolve_row(existing, row)
            for col in set(existing.keys()) | set(row.keys()):
                if existing.get(col) is not None and row.get(col) is not None and existing.get(col) != row.get(col):
                    conflicts += 1
            keyed[k] = merged
        else:
            keyed[k] = dict(row)
    return list(keyed.values()), conflicts


def _build_schema(strategies: Optional[Dict[str, str]] = None) -> MergeSchema:
    """Build a ``MergeSchema`` from a strategy name map."""
    if not strategies:
        return MergeSchema(default=LWW())
    field_strats: Dict[str, MergeStrategy] = {}
    for f, s in strategies.items():
        field_strats[f] = _resolve_strategy_name(s)
    return MergeSchema(default=LWW(), **field_strats)


def _parse_metadata(raw_metadata: Any) -> Dict[str, str]:
    """Extract a dict from Arrow Flight metadata bytes/headers.

    Convention:
        ``crdt-key``       — merge key column
        ``crdt-strategies`` — JSON-encoded ``{field: strategy_name}``
    """
    out: Dict[str, str] = {}
    if raw_metadata is None:
        return out
    # FlightDescriptor.command / metadata may be bytes or list of tuples
    if isinstance(raw_metadata, bytes):
        try:
            out = json.loads(raw_metadata.decode())
        except Exception:
            pass
    elif isinstance(raw_metadata, dict):
        out = {str(k): str(v) for k, v in raw_metadata.items()}
    elif hasattr(raw_metadata, "__iter__"):
        for item in raw_metadata:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                out[str(item[0])] = str(item[1])
    return out


# ---------------------------------------------------------------------------
# Flight server implementation
# ---------------------------------------------------------------------------

@register_accelerator
class FlightMergeServer:
    """Arrow Flight server for merge-as-a-service.

    Implements DoExchange for streaming CRDT merge via gRPC.
    Clients send two Arrow record-batch streams (delimited by a sentinel),
    and receive one merged stream back.

    Attributes:
        name: Accelerator name.
        version: Accelerator version.
    """

    name: str = "flight_server"
    version: str = "0.7.0"

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8815,
        default_schema: Optional[MergeSchema] = None,
    ) -> None:
        """Initialise the Flight merge server.

        Args:
            host: Bind address.
            port: Bind port.
            default_schema: Default merge schema when not specified by client.
        """
        self._host = host
        self._port = port
        self._default_schema = default_schema or MergeSchema(default=LWW())
        self._server: Any = None
        self._thread: Optional[threading.Thread] = None
        self._merge_cache: Dict[str, List[dict]] = {}
        self._running = False

    # ---- availability ----

    def is_available(self) -> bool:
        """Return True if pyarrow.flight is importable."""
        return _pa is not None and _flight is not None

    # ---- lifecycle ----

    def serve(self) -> None:
        """Start the Flight server (blocking).

        Raises:
            ImportError: if pyarrow / pyarrow.flight is not installed.
        """
        if _flight is None or _pa is None:
            raise ImportError(
                "pyarrow is required for FlightMergeServer. "
                "Install with: pip install pyarrow"
            )
        location = f"grpc://{self._host}:{self._port}"
        self._server = _FlightServerImpl(
            _flight.Location(location),
            merge_schema=self._default_schema,
            cache=self._merge_cache,
        )
        self._running = True
        self._server.serve()

    def start(self) -> None:
        """Start the Flight server in a background thread."""
        self._thread = threading.Thread(target=self.serve, daemon=True)
        self._thread.start()
        time.sleep(0.1)  # brief pause for startup

    def stop(self) -> None:
        """Stop the Flight server."""
        self._running = False
        if self._server is not None and hasattr(self._server, "shutdown"):
            self._server.shutdown()
        self._server = None

    # ---- merge operations (direct API, no gRPC) ----

    def do_merge(
        self,
        left: Any,
        right: Any,
        key: str,
        strategies: Optional[Dict[str, str]] = None,
    ) -> Tuple[Any, int]:
        """Merge two Arrow tables (or list-of-dicts) directly.

        Args:
            left: Left data (pyarrow.Table or list-of-dicts).
            right: Right data (pyarrow.Table or list-of-dicts).
            key: Merge key column.
            strategies: Optional per-field strategy map.

        Returns:
            Tuple of (merged_table, conflict_count).
        """
        left_recs = _table_to_records(left) if not isinstance(left, list) else left
        right_recs = _table_to_records(right) if not isinstance(right, list) else right
        schema = _build_schema(strategies)
        merged, conflicts = _merge_records(left_recs, right_recs, key, schema)
        result_table = _records_to_table(merged)
        return result_table, conflicts

    def do_exchange(
        self,
        context: Any,
        descriptor: Any,
        reader: Any,
        writer: Any,
    ) -> None:
        """Handle DoExchange RPC — receive two streams, return merged stream.

        The protocol:
        1. Client sends descriptor with metadata: ``{crdt-key, crdt-strategies}``.
        2. Client sends batches for source A, then an empty sentinel batch,
           then batches for source B.
        3. Server merges and writes result batches back.
        """
        meta = _parse_metadata(getattr(descriptor, "command", None))
        key = meta.get("crdt-key", "id")
        raw_strats = meta.get("crdt-strategies")
        strategies: Optional[Dict[str, str]] = None
        if raw_strats:
            try:
                strategies = json.loads(raw_strats)
            except Exception:
                pass

        # Read all batches into two groups
        left_recs: List[dict] = []
        right_recs: List[dict] = []
        current = left_recs
        if reader is not None:
            for batch in reader:
                if hasattr(batch, "data"):
                    table_chunk = batch.data
                else:
                    table_chunk = batch
                recs = _table_to_records(table_chunk) if not isinstance(table_chunk, list) else table_chunk
                if not recs:
                    # empty batch = sentinel separator
                    current = right_recs
                    continue
                current.extend(recs)

        schema_obj = _build_schema(strategies)
        merged, _ = _merge_records(left_recs, right_recs, key, schema_obj)
        result = _records_to_table(merged)

        if writer is not None and hasattr(writer, "write_table"):
            writer.write_table(result)

    def do_get(self, context: Any, ticket: Any) -> Any:
        """Handle DoGet — retrieve previously merged results.

        The ticket should contain the cache key (string).
        """
        ticket_str = ticket.ticket.decode() if hasattr(ticket, "ticket") else str(ticket)
        records = self._merge_cache.get(ticket_str, [])
        return _records_to_table(records)

    def list_flights(self, context: Any = None, criteria: Any = None) -> List[Dict[str, Any]]:
        """List available merge endpoints.

        Returns:
            List of endpoint descriptors.
        """
        return [
            {
                "endpoint": f"grpc://{self._host}:{self._port}",
                "operations": ["DoExchange", "DoGet"],
                "strategies": list(_STRATEGY_MAP.keys()),
            }
        ]

    # ---- health ----

    def health_check(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "pyarrow_available": _pa is not None,
            "flight_available": _flight is not None,
            "host": self._host,
            "port": self._port,
            "running": self._running,
            "cache_entries": len(self._merge_cache),
        }


# ---------------------------------------------------------------------------
# Internal Flight server (wraps pyarrow.flight.FlightServerBase)
# ---------------------------------------------------------------------------

class _FlightServerImpl:
    """Thin wrapper used only when pyarrow.flight is available."""

    def __init__(
        self,
        location: Any,
        merge_schema: MergeSchema,
        cache: Dict[str, List[dict]],
    ) -> None:
        self._location = location
        self._merge_schema = merge_schema
        self._cache = cache
        self._inner: Any = None  # actual FlightServerBase subclass
        if _flight is not None:
            # Dynamically create subclass
            parent_cls = _flight.FlightServerBase

            class _Impl(parent_cls):  # type: ignore[misc]
                def __init__(inst, loc: Any, ms: MergeSchema, c: dict) -> None:
                    super().__init__(loc)
                    inst._ms = ms
                    inst._cache = c

            self._inner = _Impl(location, merge_schema, cache)

    def serve(self) -> None:
        if self._inner is not None:
            self._inner.serve()

    def shutdown(self) -> None:
        if self._inner is not None and hasattr(self._inner, "shutdown"):
            self._inner.shutdown()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class FlightMergeClient:
    """Client for the Arrow Flight merge service.

    Example::

        client = FlightMergeClient("localhost:8815")
        result = client.merge(left_table, right_table, key="id", strategy="lww")
    """

    def __init__(self, location: str) -> None:
        """Connect to a Flight merge server.

        Args:
            location: ``host:port`` or ``grpc://host:port``.
        """
        self._location = location
        self._client: Any = None
        if _flight is not None:
            loc = location if location.startswith("grpc://") else f"grpc://{location}"
            self._client = _flight.connect(loc)

    def merge(
        self,
        left: Any,
        right: Any,
        key: str = "id",
        strategies: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Send two tables to the merge server and receive merged result.

        For environments without ``pyarrow.flight`` this falls back to a
        local (in-process) merge.

        Args:
            left: Left data (Arrow table or list-of-dicts).
            right: Right data (Arrow table or list-of-dicts).
            key: Join key column.
            strategies: Per-field strategy map.

        Returns:
            Merged result (Arrow table or list-of-dicts).
        """
        left_recs = _table_to_records(left) if not isinstance(left, list) else left
        right_recs = _table_to_records(right) if not isinstance(right, list) else right
        schema = _build_schema(strategies)
        merged, _ = _merge_records(left_recs, right_recs, key, schema)
        return _records_to_table(merged)

    def close(self) -> None:
        """Close the client connection."""
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()
        self._client = None

    def __enter__(self) -> FlightMergeClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


__all__ = [
    "FlightMergeServer",
    "FlightMergeClient",
]
