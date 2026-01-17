# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""
Self-Merging Parquet — Parquet files with embedded CRDT merge semantics.

When two Parquet files meet, they know how to merge themselves — no external
configuration needed.  Merge schema, provenance configuration, and compaction
metadata are stored directly in the Parquet key-value metadata section so
every file is self-describing.

Core operation is fully in-memory (list-of-dicts); actual Parquet I/O requires
the optional ``pyarrow`` dependency which is lazy-imported.

Usage::

    from crdt_merge.parquet import SelfMergingParquet
    from crdt_merge.strategies import MergeSchema, LWW, MaxWins

    schema = MergeSchema(default=LWW(), salary=MaxWins())
    smf = SelfMergingParquet("customers", key="id", schema=schema)
    smf.ingest([{"id": 1, "name": "Alice", "salary": 100}])
    smf.ingest([{"id": 1, "name": "Alicia", "salary": 120}])
    assert smf.read()[0]["salary"] == 120

    # Export to real Parquet file (requires pyarrow)
    smf.to_parquet("/tmp/customers.parquet")
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from crdt_merge.strategies import LWW, MergeSchema, MergeStrategy

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_META_PREFIX = "crdt_merge:"
_SCHEMA_META_KEY = f"{_META_PREFIX}schema"
_PROVENANCE_META_KEY = f"{_META_PREFIX}provenance_enabled"
_SOURCE_COUNT_KEY = f"{_META_PREFIX}source_count"
_MERGE_COUNT_KEY = f"{_META_PREFIX}merge_count"
_CREATED_AT_KEY = f"{_META_PREFIX}created_at"
_SCHEMA_VERSION_KEY = f"{_META_PREFIX}schema_version"
_KEY_COLUMN_KEY = f"{_META_PREFIX}key_column"

SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ParquetMergeMetadata:
    """Merge schema stored in Parquet key-value metadata.

    Embeds merge semantics (key, strategies, provenance config) in the
    Parquet file's metadata section so files are self-describing.
    """

    key_column: str
    strategies: Dict[str, str]
    provenance_enabled: bool = True
    schema_version: str = SCHEMA_VERSION
    created_at: Optional[str] = None
    source_count: int = 0
    merge_count: int = 0

    def to_parquet_metadata(self) -> Dict[str, str]:
        """Serialize to Parquet key-value metadata format.

        Returns:
            Dict suitable for embedding in Parquet file metadata.
        """
        return {
            _KEY_COLUMN_KEY: self.key_column,
            _SCHEMA_META_KEY: json.dumps(self.strategies),
            _PROVENANCE_META_KEY: json.dumps(self.provenance_enabled),
            _SCHEMA_VERSION_KEY: self.schema_version,
            _CREATED_AT_KEY: self.created_at or "",
            _SOURCE_COUNT_KEY: str(self.source_count),
            _MERGE_COUNT_KEY: str(self.merge_count),
        }

    @classmethod
    def from_parquet_metadata(cls, meta: Dict[str, str]) -> "ParquetMergeMetadata":
        """Deserialize from Parquet key-value metadata.

        Args:
            meta: Dict from Parquet file metadata.

        Returns:
            ParquetMergeMetadata instance.

        Raises:
            ValueError: If metadata is missing required fields.
        """
        if _KEY_COLUMN_KEY not in meta:
            raise ValueError(
                f"Missing required metadata key '{_KEY_COLUMN_KEY}'. "
                "This file does not appear to be a self-merging Parquet file."
            )
        strategies_raw = meta.get(_SCHEMA_META_KEY, "{}")
        try:
            strategies = json.loads(strategies_raw)
        except json.JSONDecodeError:
            strategies = {}

        provenance_raw = meta.get(_PROVENANCE_META_KEY, "true")
        try:
            provenance_enabled = json.loads(provenance_raw)
        except (json.JSONDecodeError, TypeError):
            provenance_enabled = True

        return cls(
            key_column=meta[_KEY_COLUMN_KEY],
            strategies=strategies if isinstance(strategies, dict) else {},
            provenance_enabled=bool(provenance_enabled),
            schema_version=meta.get(_SCHEMA_VERSION_KEY, SCHEMA_VERSION),
            created_at=meta.get(_CREATED_AT_KEY) or None,
            source_count=int(meta.get(_SOURCE_COUNT_KEY, 0)),
            merge_count=int(meta.get(_MERGE_COUNT_KEY, 0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        return {
            "key_column": self.key_column,
            "strategies": dict(self.strategies),
            "provenance_enabled": self.provenance_enabled,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "source_count": self.source_count,
            "merge_count": self.merge_count,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ParquetMergeMetadata":
        """Deserialize from plain dict."""
        return cls(
            key_column=d["key_column"],
            strategies=d.get("strategies", {}),
            provenance_enabled=d.get("provenance_enabled", True),
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            created_at=d.get("created_at"),
            source_count=d.get("source_count", 0),
            merge_count=d.get("merge_count", 0),
        )

@dataclass
class IngestResult:
    """Result of ingesting data into a self-merging Parquet file."""

    records_ingested: int = 0
    conflicts_resolved: int = 0
    new_records: int = 0
    updated_records: int = 0
    merge_time_ms: float = 0.0
    provenance_entries: int = 0

@dataclass
class CompactResult:
    """Result of compacting a self-merging Parquet file."""

    records_before: int = 0
    records_after: int = 0
    duplicates_removed: int = 0
    compact_time_ms: float = 0.0

@dataclass
class ProvenanceEntry:
    """A single provenance log entry for an ingest operation."""

    source: str
    timestamp: float
    records_ingested: int
    conflicts_resolved: int
    new_records: int
    updated_records: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "timestamp": self.timestamp,
            "records_ingested": self.records_ingested,
            "conflicts_resolved": self.conflicts_resolved,
            "new_records": self.new_records,
            "updated_records": self.updated_records,
        }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_hash(row: dict) -> str:
    """Deterministic content hash for a single record."""
    parts = []
    for k in sorted(row.keys()):
        parts.append(f"{k}={row[k]!r}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]

def _build_merge_schema(
    key: str, strategies: Dict[str, str]
) -> MergeSchema:
    """Build a MergeSchema from a dict of field→strategy-name mappings."""
    from crdt_merge.strategies import (
        Concat,
        LongestWins,
        MaxWins,
        MinWins,
        Priority,
        UnionSet,
    )

    _registry = {
        "lww": LWW,
        "max": MaxWins,
        "maxwins": MaxWins,
        "min": MinWins,
        "minwins": MinWins,
        "union": UnionSet,
        "unionset": UnionSet,
        "concat": Concat,
        "longestwins": LongestWins,
        "longest": LongestWins,
    }

    field_strats: Dict[str, MergeStrategy] = {}
    for fld, name in strategies.items():
        cls = _registry.get(name.lower(), LWW)
        field_strats[fld] = cls()
    return MergeSchema(default=LWW(), **field_strats)

# ---------------------------------------------------------------------------
# SelfMergingParquet
# ---------------------------------------------------------------------------

class SelfMergingParquet:
    """Parquet files with embedded CRDT merge semantics.

    Data is stored in-memory using list-of-dicts format.  Merge schema and
    provenance are tracked as metadata.  Export to actual Parquet files
    requires PyArrow (optional dependency).

    Args:
        name: Logical name for this container.
        key: Primary key column for merge matching.
        schema: MergeSchema defining per-field strategies.
        provenance: Enable provenance tracking.

    Example::

        smf = SelfMergingParquet("users", key="id", schema=MergeSchema(
            default=LWW(), salary=MaxWins(),
        ))
        smf.ingest([{"id": 1, "name": "Alice", "salary": 100}])
        smf.ingest([{"id": 1, "name": "Alicia", "salary": 120}])
        assert smf.read() == [{"id": 1, "name": "Alicia", "salary": 120}]
    """

    def __init__(
        self,
        name: str,
        key: str = "id",
        schema: Optional[MergeSchema] = None,
        provenance: bool = True,
    ) -> None:
        if not name:
            raise ValueError("name must not be empty")
        self._name = name
        self._key = key
        self._schema = schema or MergeSchema(default=LWW())
        self._provenance = provenance
        self._data: Dict[Any, dict] = {}  # key_value → record
        self._provenance_log: List[ProvenanceEntry] = []
        self._source_count: int = 0
        self._merge_count: int = 0
        self._created_at: str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def ingest(
        self,
        data: Any,
        source: Optional[str] = None,
    ) -> IngestResult:
        """Merge new data into the container.

        Args:
            data: List of dicts, or any iterable of records.
            source: Optional source label for provenance.

        Returns:
            IngestResult with merge statistics.
        """
        start = time.time()
        records = self._normalise_input(data)
        source_label = source or f"ingest_{self._source_count}"

        new_records = 0
        updated_records = 0
        conflicts = 0

        for rec in records:
            k = rec.get(self._key)
            if k is None:
                continue  # skip records without key
            if k in self._data:
                existing = self._data[k]
                merged, n_conflicts = self._merge_row(existing, rec)
                self._data[k] = merged
                updated_records += 1
                conflicts += n_conflicts
            else:
                self._data[k] = dict(rec)
                new_records += 1

        self._source_count += 1
        self._merge_count += 1 if updated_records > 0 else 0
        elapsed_ms = (time.time() - start) * 1000

        result = IngestResult(
            records_ingested=len(records),
            conflicts_resolved=conflicts,
            new_records=new_records,
            updated_records=updated_records,
            merge_time_ms=round(elapsed_ms, 2),
            provenance_entries=len(self._provenance_log) + (1 if self._provenance else 0),
        )

        if self._provenance:
            self._provenance_log.append(
                ProvenanceEntry(
                    source=source_label,
                    timestamp=time.time(),
                    records_ingested=len(records),
                    conflicts_resolved=conflicts,
                    new_records=new_records,
                    updated_records=updated_records,
                )
            )

        return result

    def read(self) -> List[dict]:
        """Read all merged records.

        Returns:
            List of merged records ordered by key.
        """
        result = []
        for k in sorted(self._data.keys(), key=lambda x: (str(type(x).__name__), x)):
            result.append(dict(self._data[k]))
        return result

    def compact(self) -> CompactResult:
        """Compact the container, removing exact-duplicate rows and dead entries.

        Returns:
            CompactResult with compaction statistics.
        """
        start = time.time()
        before = len(self._data)

        # Remove entries where all non-key fields are None
        to_remove = []
        for k, rec in self._data.items():
            non_key = {f: v for f, v in rec.items() if f != self._key}
            if all(v is None for v in non_key.values()):
                to_remove.append(k)
        for k in to_remove:
            del self._data[k]

        # Deduplicate by content hash (shouldn't happen with key-based storage but
        # provides a safety net for data ingested with duplicate keys across batches).
        seen_hashes: Dict[str, Any] = {}
        duplicates = 0
        for k, rec in list(self._data.items()):
            h = _row_hash(rec)
            if h in seen_hashes:
                duplicates += 1
                # Keep the one already there
            else:
                seen_hashes[h] = k

        after = len(self._data)
        elapsed_ms = (time.time() - start) * 1000
        return CompactResult(
            records_before=before,
            records_after=after,
            duplicates_removed=before - after,
            compact_time_ms=round(elapsed_ms, 2),
        )

    def metadata(self) -> ParquetMergeMetadata:
        """Get the embedded merge metadata.

        Returns:
            ParquetMergeMetadata reflecting current container state.
        """
        strategies: Dict[str, str] = {}
        for fld, strat in self._schema.fields.items():
            strategies[fld] = strat.name()
        return ParquetMergeMetadata(
            key_column=self._key,
            strategies=strategies,
            provenance_enabled=self._provenance,
            schema_version=SCHEMA_VERSION,
            created_at=self._created_at,
            source_count=self._source_count,
            merge_count=self._merge_count,
        )

    def merge_with(self, other: "SelfMergingParquet") -> IngestResult:
        """Merge another SelfMergingParquet into this one.

        Args:
            other: Another SelfMergingParquet container.

        Returns:
            IngestResult with merge statistics.
        """
        if other._key != self._key:
            raise ValueError(
                f"Key column mismatch: self uses '{self._key}', "
                f"other uses '{other._key}'"
            )
        records = other.read()
        return self.ingest(records, source=f"merge_from:{other._name}")

    def get_provenance_log(self) -> List[Dict[str, Any]]:
        """Return the provenance log as a list of dicts."""
        return [e.to_dict() for e in self._provenance_log]

    # ------------------------------------------------------------------
    # Parquet I/O  (requires pyarrow)
    # ------------------------------------------------------------------

    def to_parquet(self, path: str) -> None:
        """Export to actual Parquet file with embedded metadata.

        Requires PyArrow.  Raises ImportError if not available.

        Args:
            path: Output file path.
        """
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            raise ImportError(
                "PyArrow is required for Parquet I/O. "
                "Install it with: pip install pyarrow"
            )

        records = self.read()
        if not records:
            # Write an empty table with metadata
            table = pa.table({})
        else:
            table = pa.Table.from_pylist(records)

        meta = self.metadata().to_parquet_metadata()
        # Encode metadata values as bytes
        existing_meta = table.schema.metadata or {}
        merged_meta = {
            **{k.encode() if isinstance(k, str) else k: v.encode() if isinstance(v, str) else v
               for k, v in existing_meta.items()},
            **{k.encode(): v.encode() for k, v in meta.items()},
        }
        table = table.replace_schema_metadata(merged_meta)
        pq.write_table(table, path)

    @classmethod
    def from_parquet(cls, path: str) -> "SelfMergingParquet":
        """Load from a Parquet file with embedded merge metadata.

        Requires PyArrow.  Raises ImportError if not available.

        Args:
            path: Input file path.

        Returns:
            SelfMergingParquet instance with data and metadata loaded.
        """
        try:
            import pyarrow.parquet as pq
        except ImportError:
            raise ImportError(
                "PyArrow is required for Parquet I/O. "
                "Install it with: pip install pyarrow"
            )

        table = pq.read_table(path)
        raw_meta = table.schema.metadata or {}
        # Decode bytes keys
        str_meta = {
            (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
            for k, v in raw_meta.items()
        }

        pq_meta = ParquetMergeMetadata.from_parquet_metadata(str_meta)
        schema = _build_merge_schema(pq_meta.key_column, pq_meta.strategies)

        instance = cls(
            name=path,
            key=pq_meta.key_column,
            schema=schema,
            provenance=pq_meta.provenance_enabled,
        )
        instance._created_at = pq_meta.created_at or instance._created_at
        instance._source_count = pq_meta.source_count
        instance._merge_count = pq_meta.merge_count

        records = table.to_pylist()
        for rec in records:
            k = rec.get(pq_meta.key_column)
            if k is not None:
                instance._data[k] = rec

        return instance

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalise_input(self, data: Any) -> List[dict]:
        """Convert various input formats to list of dicts."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        if hasattr(data, "to_dict"):
            # pandas DataFrame
            return data.to_dict("records")
        if hasattr(data, "to_dicts"):
            # polars DataFrame
            return data.to_dicts()
        # Fallback: assume iterable
        return list(data)

    def _merge_row(
        self, existing: dict, incoming: dict
    ) -> Tuple[dict, int]:
        """Merge a single incoming row with an existing row.

        Returns (merged_row, conflict_count).
        """
        all_cols = list(dict.fromkeys(list(existing.keys()) + list(incoming.keys())))
        merged: dict = {}
        conflicts = 0

        for col in all_cols:
            va = existing.get(col)
            vb = incoming.get(col)
            if va is None:
                merged[col] = vb
            elif vb is None:
                merged[col] = va
            elif va == vb:
                merged[col] = va
            else:
                strategy = self._schema.strategy_for(col)
                merged[col] = strategy.resolve(va, vb, 0.0, 0.0, "existing", "incoming")
                conflicts += 1

        return merged, conflicts

    # ------------------------------------------------------------------
    # Dunder methods
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Number of records in the container."""
        return len(self._data)

    def __repr__(self) -> str:
        return (
            f"SelfMergingParquet(name={self._name!r}, key={self._key!r}, "
            f"records={len(self)}, sources={self._source_count})"
        )

    def __contains__(self, key_value: Any) -> bool:
        """Check if a key exists in the container."""
        return key_value in self._data

    def __getitem__(self, key_value: Any) -> dict:
        """Get a record by key value."""
        if key_value not in self._data:
            raise KeyError(f"Key {key_value!r} not found")
        return dict(self._data[key_value])

__all__ = [
    "SelfMergingParquet",
    "ParquetMergeMetadata",
    "IngestResult",
    "CompactResult",
    "ProvenanceEntry",
    "SCHEMA_VERSION",
]
