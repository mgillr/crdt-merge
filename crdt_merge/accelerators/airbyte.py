# Copyright 2026 Ryan Gillespie / Optitransfer
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""
Airbyte Custom Destination Connector — write Airbyte streams through CRDT merge.

Implements an Airbyte destination connector that merges incoming records using
CRDT strategies before writing to the final destination.  Strategies are
configurable per-stream via the connector spec.

This module follows the Airbyte Python CDK patterns (spec, check, write) but
does NOT depend on ``airbyte_cdk`` at import time — all CDK references are
lazy-imported so the module is always importable.

Usage::

    from crdt_merge.accelerators.airbyte import AirbyteMergeDestination

    dest = AirbyteMergeDestination(schema=my_schema)
    dest.write(stream_name="users", records=[...])
    spec = dest.get_spec()

All external dependencies use lazy imports.
"""

from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from crdt_merge.accelerators import register_accelerator

# Lazy import helpers
_strategies_mod = None
_provenance_mod = None


def _get_strategies():
    """Lazy-import crdt_merge.strategies."""
    global _strategies_mod
    if _strategies_mod is None:
        from crdt_merge import strategies as _sm
        _strategies_mod = _sm
    return _strategies_mod


def _get_provenance():
    """Lazy-import crdt_merge.provenance."""
    global _provenance_mod
    if _provenance_mod is None:
        from crdt_merge import provenance as _pm
        _provenance_mod = _pm
    return _provenance_mod


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VERSION = "0.7.0"
_CONNECTOR_NAME = "destination-crdt-merge"
_DEFAULT_STRATEGY = "lww"

_STRATEGY_MAP = {
    "lww": "LWW",
    "max": "MaxWins",
    "maxwins": "MaxWins",
    "min": "MinWins",
    "minwins": "MinWins",
    "union": "UnionSet",
    "unionset": "UnionSet",
    "concat": "Concat",
    "priority": "Priority",
    "longest": "LongestWins",
    "longestwins": "LongestWins",
}

# ---------------------------------------------------------------------------
# Airbyte protocol message types (simplified)
# ---------------------------------------------------------------------------


@dataclass
class AirbyteMessage:
    """Simplified Airbyte protocol message."""

    type: str  # RECORD, STATE, LOG, SPEC, CONNECTION_STATUS
    record: Optional[Dict[str, Any]] = None
    state: Optional[Dict[str, Any]] = None
    log: Optional[Dict[str, Any]] = None
    spec: Optional[Dict[str, Any]] = None
    connection_status: Optional[Dict[str, Any]] = None


@dataclass
class AirbyteRecordMessage:
    """An individual Airbyte record."""

    stream: str
    data: Dict[str, Any]
    emitted_at: float = 0.0
    namespace: Optional[str] = None


@dataclass
class StreamConfig:
    """Per-stream CRDT merge configuration."""

    key_column: str
    strategies: Dict[str, str] = field(default_factory=dict)
    default_strategy: str = _DEFAULT_STRATEGY
    timestamp_column: str = "_ab_emitted_at"
    provenance_enabled: bool = False

    def resolve_strategy_name(self, column: str) -> str:
        """Return the strategy name for a given column."""
        raw = self.strategies.get(column, self.default_strategy)
        return _STRATEGY_MAP.get(raw.lower(), raw)


@dataclass
class WriteResult:
    """Result of a write operation."""

    stream_name: str
    records_written: int
    records_merged: int
    conflicts_resolved: int
    merge_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict."""
        return {
            "stream_name": self.stream_name,
            "records_written": self.records_written,
            "records_merged": self.records_merged,
            "conflicts_resolved": self.conflicts_resolved,
            "merge_time_ms": self.merge_time_ms,
        }


# ---------------------------------------------------------------------------
# Strategy resolver (lazy)
# ---------------------------------------------------------------------------


def _build_merge_schema(
    stream_cfg: StreamConfig,
    columns: Sequence[str],
) -> Any:
    """Build a MergeSchema from stream config.

    Returns:
        A crdt_merge.strategies.MergeSchema instance.
    """
    sm = _get_strategies()
    strat_map: Dict[str, Any] = {
        "LWW": sm.LWW,
        "MaxWins": sm.MaxWins,
        "MinWins": sm.MinWins,
        "UnionSet": sm.UnionSet,
        "Concat": sm.Concat,
        "Priority": sm.Priority,
        "LongestWins": sm.LongestWins,
    }

    default_cls = strat_map.get(
        _STRATEGY_MAP.get(stream_cfg.default_strategy.lower(), "LWW"), sm.LWW
    )
    field_strats = {}
    for col in columns:
        name = stream_cfg.resolve_strategy_name(col)
        cls = strat_map.get(name)
        if cls and cls is not default_cls:
            field_strats[col] = cls()

    return sm.MergeSchema(default=default_cls(), **field_strats)


def _resolve_field(
    val_a: Any,
    val_b: Any,
    strategy_name: str,
    ts_a: float = 0.0,
    ts_b: float = 0.0,
) -> Tuple[Any, bool]:
    """Resolve a single field conflict.

    Returns:
        (resolved_value, was_conflict)
    """
    if val_a == val_b:
        return val_a, False

    sm = _get_strategies()
    strat_cls_map: Dict[str, type] = {
        "LWW": sm.LWW,
        "MaxWins": sm.MaxWins,
        "MinWins": sm.MinWins,
        "UnionSet": sm.UnionSet,
        "Concat": sm.Concat,
        "LongestWins": sm.LongestWins,
    }
    cls = strat_cls_map.get(strategy_name, sm.LWW)
    strat = cls()
    resolved = strat.resolve(val_a, val_b, ts_a=ts_a, ts_b=ts_b)
    return resolved, True


# ---------------------------------------------------------------------------
# In-memory stream store
# ---------------------------------------------------------------------------


class _StreamStore:
    """In-memory record store for a single Airbyte stream."""

    def __init__(self, key_column: str) -> None:
        self._key_column = key_column
        self._records: Dict[Any, Dict[str, Any]] = {}
        self._timestamps: Dict[Any, float] = {}

    @property
    def records(self) -> List[Dict[str, Any]]:
        return list(self._records.values())

    @property
    def count(self) -> int:
        return len(self._records)

    def upsert(
        self,
        record: Dict[str, Any],
        timestamp: float,
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Insert or return existing record for merge.

        Returns:
            (existing_record_or_None, is_update)
        """
        key = record.get(self._key_column)
        if key is None:
            raise ValueError(
                f"Record missing key column '{self._key_column}': {record}"
            )
        existing = self._records.get(key)
        if existing is not None:
            old_ts = self._timestamps.get(key, 0.0)
            return existing, True
        self._records[key] = copy.deepcopy(record)
        self._timestamps[key] = timestamp
        return None, False

    def put(self, record: Dict[str, Any], timestamp: float) -> None:
        """Store a (merged) record."""
        key = record[self._key_column]
        self._records[key] = record
        self._timestamps[key] = timestamp

    def get_timestamp(self, key: Any) -> float:
        return self._timestamps.get(key, 0.0)

    def clear(self) -> None:
        self._records.clear()
        self._timestamps.clear()


# ---------------------------------------------------------------------------
# Destination connector
# ---------------------------------------------------------------------------


@register_accelerator
class AirbyteMergeDestination:
    """Airbyte custom destination connector with CRDT merge semantics.

    Attributes:
        name: Accelerator name for the registry.
        version: Connector version string.
    """

    name: str = "airbyte_destination"
    version: str = _VERSION

    def __init__(
        self,
        *,
        stream_configs: Optional[Dict[str, StreamConfig]] = None,
        schema: Optional[Any] = None,
        default_key: str = "id",
        default_strategy: str = _DEFAULT_STRATEGY,
    ) -> None:
        """Initialise the Airbyte destination.

        Args:
            stream_configs: Per-stream merge configurations.
            schema: Optional global MergeSchema applied to all streams.
            default_key: Default primary key column name.
            default_strategy: Default strategy when none specified.
        """
        self._stream_configs: Dict[str, StreamConfig] = stream_configs or {}
        self._global_schema = schema
        self._default_key = default_key
        self._default_strategy = default_strategy
        self._stores: Dict[str, _StreamStore] = {}
        self._state: Dict[str, Any] = {}
        self._write_results: List[WriteResult] = []

    # -- AcceleratorProtocol -------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Return health / readiness status."""
        return {
            "name": self.name,
            "version": self.version,
            "connector": _CONNECTOR_NAME,
            "streams_configured": len(self._stream_configs),
            "streams_active": len(self._stores),
            "status": "ok",
        }

    def is_available(self) -> bool:
        """Always available — no hard external deps."""
        return True

    # -- Airbyte spec --------------------------------------------------------

    def get_spec(self) -> Dict[str, Any]:
        """Return the Airbyte connector specification.

        Returns:
            Dict matching the Airbyte connector spec schema.
        """
        return {
            "documentationUrl": "https://github.com/mgillr/crdt-merge",
            "connectionSpecification": {
                "type": "object",
                "title": "CRDT Merge Destination",
                "description": (
                    "Airbyte destination that merges records using "
                    "conflict-free replicated data type strategies."
                ),
                "required": ["default_key"],
                "properties": {
                    "default_key": {
                        "type": "string",
                        "title": "Default Primary Key",
                        "description": "Column used as primary key for merge.",
                        "default": "id",
                        "order": 0,
                    },
                    "default_strategy": {
                        "type": "string",
                        "title": "Default Merge Strategy",
                        "description": "Strategy applied when no per-column override.",
                        "enum": list(_STRATEGY_MAP.keys()),
                        "default": _DEFAULT_STRATEGY,
                        "order": 1,
                    },
                    "stream_overrides": {
                        "type": "object",
                        "title": "Per-Stream Overrides",
                        "description": (
                            "JSON object mapping stream names to "
                            "{key, strategies} objects."
                        ),
                        "default": {},
                        "order": 2,
                    },
                    "provenance_enabled": {
                        "type": "boolean",
                        "title": "Enable Provenance",
                        "description": "Track merge provenance per record.",
                        "default": False,
                        "order": 3,
                    },
                },
            },
            "supportsIncremental": True,
            "supportsNormalization": False,
            "supportsDBT": True,
            "supported_destination_sync_modes": ["overwrite", "append", "append_dedup"],
        }

    def check_connection(self, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate the connection configuration.

        Args:
            config: Connector config dict from Airbyte.

        Returns:
            (success, error_message_or_None)
        """
        if "default_key" not in config:
            return False, "Missing required field: default_key"
        strategy = config.get("default_strategy", _DEFAULT_STRATEGY)
        if strategy.lower() not in _STRATEGY_MAP:
            return False, f"Unknown default strategy: {strategy}"
        return True, None

    # -- Stream management ---------------------------------------------------

    def configure_stream(
        self,
        stream_name: str,
        *,
        key_column: Optional[str] = None,
        strategies: Optional[Dict[str, str]] = None,
        default_strategy: Optional[str] = None,
        timestamp_column: str = "_ab_emitted_at",
        provenance_enabled: bool = False,
    ) -> None:
        """Configure merge settings for a specific stream.

        Args:
            stream_name: Airbyte stream name.
            key_column: Primary key column.
            strategies: Per-column strategy overrides.
            default_strategy: Stream-level default strategy.
            timestamp_column: Timestamp column name.
            provenance_enabled: Whether to track provenance.
        """
        self._stream_configs[stream_name] = StreamConfig(
            key_column=key_column or self._default_key,
            strategies=strategies or {},
            default_strategy=default_strategy or self._default_strategy,
            timestamp_column=timestamp_column,
            provenance_enabled=provenance_enabled,
        )

    def _get_stream_config(self, stream_name: str) -> StreamConfig:
        """Get or create default config for a stream."""
        if stream_name not in self._stream_configs:
            self._stream_configs[stream_name] = StreamConfig(
                key_column=self._default_key,
                default_strategy=self._default_strategy,
            )
        return self._stream_configs[stream_name]

    def _get_store(self, stream_name: str) -> _StreamStore:
        """Get or create the in-memory store for a stream."""
        cfg = self._get_stream_config(stream_name)
        if stream_name not in self._stores:
            self._stores[stream_name] = _StreamStore(cfg.key_column)
        return self._stores[stream_name]

    # -- Write ---------------------------------------------------------------

    def write(
        self,
        stream_name: str,
        records: List[Dict[str, Any]],
        *,
        timestamp: Optional[float] = None,
    ) -> WriteResult:
        """Write records to a stream, merging with existing data.

        Args:
            stream_name: Name of the Airbyte stream.
            records: List of record dicts to write.
            timestamp: Override timestamp for all records.

        Returns:
            WriteResult with merge statistics.
        """
        t0 = time.monotonic()
        cfg = self._get_stream_config(stream_name)
        store = self._get_store(stream_name)

        written = 0
        merged = 0
        conflicts = 0

        for rec in records:
            ts = timestamp or rec.get(cfg.timestamp_column, time.time())
            existing, is_update = store.upsert(rec, ts)

            if is_update and existing is not None:
                merged_rec, n_conflicts = self._merge_record(
                    existing, rec, cfg, store.get_timestamp(existing[cfg.key_column]), ts,
                )
                store.put(merged_rec, max(store.get_timestamp(existing[cfg.key_column]), ts))
                merged += 1
                conflicts += n_conflicts
            written += 1

        elapsed = (time.monotonic() - t0) * 1000
        result = WriteResult(
            stream_name=stream_name,
            records_written=written,
            records_merged=merged,
            conflicts_resolved=conflicts,
            merge_time_ms=round(elapsed, 3),
        )
        self._write_results.append(result)
        return result

    def write_messages(
        self,
        messages: Iterator[AirbyteMessage],
    ) -> Iterator[AirbyteMessage]:
        """Process a stream of Airbyte messages.

        Yields state messages back after processing records.

        Args:
            messages: Iterator of AirbyteMessage objects.

        Yields:
            AirbyteMessage state checkpoints.
        """
        for msg in messages:
            if msg.type == "RECORD" and msg.record is not None:
                stream = msg.record.get("stream", "")
                data = msg.record.get("data", {})
                ts = msg.record.get("emitted_at", time.time())
                self.write(stream, [data], timestamp=ts)
            elif msg.type == "STATE" and msg.state is not None:
                self._state.update(msg.state)
                yield AirbyteMessage(type="STATE", state=dict(self._state))

    # -- Query ---------------------------------------------------------------

    def read_stream(self, stream_name: str) -> List[Dict[str, Any]]:
        """Read all merged records from a stream.

        Args:
            stream_name: Name of the stream.

        Returns:
            List of merged record dicts.
        """
        store = self._stores.get(stream_name)
        if store is None:
            return []
        return store.records

    def get_state(self) -> Dict[str, Any]:
        """Return current connector state."""
        return dict(self._state)

    def get_write_results(self) -> List[WriteResult]:
        """Return all write results since initialisation."""
        return list(self._write_results)

    def clear_stream(self, stream_name: str) -> None:
        """Clear all records in a stream."""
        store = self._stores.get(stream_name)
        if store is not None:
            store.clear()

    def list_streams(self) -> List[str]:
        """Return names of all active streams."""
        return list(self._stores.keys())

    # -- Internal merge logic ------------------------------------------------

    def _merge_record(
        self,
        existing: Dict[str, Any],
        incoming: Dict[str, Any],
        cfg: StreamConfig,
        ts_existing: float,
        ts_incoming: float,
    ) -> Tuple[Dict[str, Any], int]:
        """Merge an incoming record with an existing one.

        Returns:
            (merged_record, conflict_count)
        """
        all_cols = set(existing.keys()) | set(incoming.keys())
        merged: Dict[str, Any] = {}
        n_conflicts = 0

        for col in all_cols:
            if col == cfg.key_column:
                merged[col] = existing.get(col) or incoming.get(col)
                continue

            val_a = existing.get(col)
            val_b = incoming.get(col)

            if val_a is None and val_b is not None:
                merged[col] = val_b
            elif val_b is None and val_a is not None:
                merged[col] = val_a
            elif val_a == val_b:
                merged[col] = val_a
            else:
                strategy_name = cfg.resolve_strategy_name(col)
                resolved, was_conflict = _resolve_field(
                    val_a, val_b, strategy_name,
                    ts_a=ts_existing, ts_b=ts_incoming,
                )
                merged[col] = resolved
                if was_conflict:
                    n_conflicts += 1

        return merged, n_conflicts
