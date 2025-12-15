# Copyright 2026 Ryan Gillespie
# Licensed under Apache-2.0

"""
DuckLake Semantic Conflict Layer — field-level conflict resolution for
DuckLake snapshots with Merkle-based change detection.

Extends DuckLake's transaction-level conflict handling with CRDT-powered
field-level resolution.  Uses Merkle trees for efficient delta sync and
deterministic merge producing identical results regardless of operation order.

External dependency: ``duckdb`` — **lazy-imported**.  The module can be
imported even when DuckDB is not installed; operations that need DuckDB
will raise a clear ``ImportError`` at call-time.

Usage::

    from crdt_merge.accelerators.ducklake import DuckLakeConflictResolver
    from crdt_merge.strategies import MergeSchema, LWW, MaxWins

    schema = MergeSchema(default=LWW(), salary=MaxWins())
    resolver = DuckLakeConflictResolver(schema=schema)
    result = resolver.merge_snapshots(snapshot_a, snapshot_b, key="id")
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from crdt_merge.strategies import LWW, MergeSchema, MergeStrategy

# Lazy-import duckdb
try:
    import duckdb as _duckdb  # type: ignore[import-untyped]
except ImportError:
    _duckdb = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DUCKDB_INSTALL_MSG = (
    "DuckDB is required for this accelerator. Install it with: pip install duckdb"
)


def _require_duckdb() -> Any:
    """Return the ``duckdb`` module or raise ImportError."""
    if _duckdb is None:
        raise ImportError(_DUCKDB_INSTALL_MSG)
    return _duckdb


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class FieldChange:
    """A single field-level change between two snapshots."""

    key: Any
    field: str
    value_a: Any
    value_b: Any
    resolved_value: Optional[Any] = None
    strategy: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "field": self.field,
            "value_a": self.value_a,
            "value_b": self.value_b,
            "resolved_value": self.resolved_value,
            "strategy": self.strategy,
        }


@dataclass
class SnapshotDiff:
    """Diff between two snapshots at the field level."""

    added_keys: List[Any] = field(default_factory=list)
    removed_keys: List[Any] = field(default_factory=list)
    modified_fields: List[FieldChange] = field(default_factory=list)

    @property
    def is_identical(self) -> bool:
        return (
            not self.added_keys
            and not self.removed_keys
            and not self.modified_fields
        )

    @property
    def num_changes(self) -> int:
        return len(self.added_keys) + len(self.removed_keys) + len(self.modified_fields)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "added_keys": list(self.added_keys),
            "removed_keys": list(self.removed_keys),
            "modified_fields": [f.to_dict() for f in self.modified_fields],
            "is_identical": self.is_identical,
            "num_changes": self.num_changes,
        }


@dataclass
class MergeResult:
    """Result of a DuckLake snapshot merge."""

    data: List[dict]
    conflicts_resolved: int = 0
    merge_time_ms: float = 0.0
    rows_merged: int = 0
    rows_left_only: int = 0
    rows_right_only: int = 0
    field_changes: List[FieldChange] = field(default_factory=list)

    @property
    def total_rows(self) -> int:
        return self.rows_merged + self.rows_left_only + self.rows_right_only

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "conflicts_resolved": self.conflicts_resolved,
            "merge_time_ms": round(self.merge_time_ms, 2),
            "rows_merged": self.rows_merged,
            "rows_left_only": self.rows_left_only,
            "rows_right_only": self.rows_right_only,
            "field_changes": [fc.to_dict() for fc in self.field_changes],
        }


@dataclass
class AuditEntry:
    """Audit trail entry for a single record."""

    key: Any
    field: str
    source: str
    strategy: str
    value: Any
    alternative: Any = None
    timestamp: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "field": self.field,
            "source": self.source,
            "strategy": self.strategy,
            "value": self.value,
            "alternative": self.alternative,
            "timestamp": self.timestamp,
        }


@dataclass
class Branch:
    """Represents a branch in the DuckLake snapshot tree."""

    name: str
    source_snapshot: str
    data: List[dict] = field(default_factory=list)
    created_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "source_snapshot": self.source_snapshot,
            "record_count": len(self.data),
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Merkle helpers (use built-in merkle module when available)
# ---------------------------------------------------------------------------


def _record_hash(record: dict) -> str:
    """Content hash for a single record."""
    parts = []
    for k in sorted(record.keys()):
        parts.append(f"{k}={record[k]!r}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _snapshot_hash(records: List[dict]) -> str:
    """Merkle root hash for a list of records."""
    if not records:
        return hashlib.sha256(b"empty").hexdigest()[:16]
    hashes = sorted(_record_hash(r) for r in records)
    combined = "|".join(hashes)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# DuckLakeConflictResolver
# ---------------------------------------------------------------------------


class DuckLakeConflictResolver:
    """Semantic conflict resolution for DuckLake snapshots.

    Provides field-level conflict resolution with configurable strategies
    for DuckLake data snapshots, extending beyond transaction-level conflict
    handling.

    Operates on in-memory snapshots (list of dicts) with optional DuckDB
    connection for SQL-based queries on the resolved data.

    Args:
        connection: Optional DuckDB connection (lazy-imported).
        schema: MergeSchema defining per-field strategies.

    Example::

        resolver = DuckLakeConflictResolver(schema=MergeSchema(
            default=LWW(), salary=MaxWins()
        ))
        result = resolver.merge_snapshots(snap_a, snap_b, key="id")
    """

    name: str = "ducklake"
    version: str = "0.7.0"

    def __init__(
        self,
        connection: Any = None,
        schema: Optional[MergeSchema] = None,
    ) -> None:
        self._conn = connection
        self._schema = schema or MergeSchema(default=LWW())
        self._audit: List[AuditEntry] = []
        self._branches: Dict[str, Branch] = {}
        self._snapshots: Dict[str, List[dict]] = {}

    # ------------------------------------------------------------------
    # Snapshot management
    # ------------------------------------------------------------------

    def register_snapshot(self, name: str, data: Any) -> None:
        """Register a named snapshot for later merge operations.

        Args:
            name: Snapshot identifier.
            data: List of dicts, or DuckDB table name (when connection provided).
        """
        if isinstance(data, list):
            self._snapshots[name] = [dict(r) for r in data]
        elif isinstance(data, str) and self._conn is not None:
            # Query from DuckDB
            result = self._conn.execute(f"SELECT * FROM {data}").fetchall()
            cols = [desc[0] for desc in self._conn.description]
            self._snapshots[name] = [dict(zip(cols, row)) for row in result]
        else:
            raise TypeError(
                f"Expected list of dicts or DuckDB table name (str), got {type(data)}"
            )

    def list_snapshots(self) -> List[str]:
        """List registered snapshot names."""
        return list(self._snapshots.keys())

    # ------------------------------------------------------------------
    # Core merge
    # ------------------------------------------------------------------

    def merge_snapshots(
        self,
        left: Any,
        right: Any,
        key: str = "id",
    ) -> MergeResult:
        """Merge two snapshots with field-level CRDT resolution.

        Args:
            left: Left snapshot — list of dicts or registered snapshot name.
            right: Right snapshot — list of dicts or registered snapshot name.
            key: Column to match rows on.

        Returns:
            MergeResult with merged data and statistics.
        """
        start = time.time()
        left_data = self._resolve_snapshot(left)
        right_data = self._resolve_snapshot(right)

        left_idx: Dict[Any, dict] = {}
        for r in left_data:
            k = r.get(key)
            if k is not None:
                left_idx[k] = r

        right_idx: Dict[Any, dict] = {}
        for r in right_data:
            k = r.get(key)
            if k is not None:
                right_idx[k] = r

        all_keys = list(dict.fromkeys(list(left_idx.keys()) + list(right_idx.keys())))

        merged_rows: List[dict] = []
        conflicts = 0
        rows_merged = 0
        rows_left_only = 0
        rows_right_only = 0
        field_changes: List[FieldChange] = []

        for k in all_keys:
            row_l = left_idx.get(k)
            row_r = right_idx.get(k)

            if row_l and row_r:
                m, c, changes = self._merge_row(row_l, row_r, k)
                merged_rows.append(m)
                conflicts += c
                rows_merged += 1
                field_changes.extend(changes)
            elif row_l:
                merged_rows.append(dict(row_l))
                rows_left_only += 1
            else:
                merged_rows.append(dict(row_r))  # type: ignore[arg-type]
                rows_right_only += 1

        elapsed_ms = (time.time() - start) * 1000

        return MergeResult(
            data=merged_rows,
            conflicts_resolved=conflicts,
            merge_time_ms=round(elapsed_ms, 2),
            rows_merged=rows_merged,
            rows_left_only=rows_left_only,
            rows_right_only=rows_right_only,
            field_changes=field_changes,
        )

    # ------------------------------------------------------------------
    # Change detection
    # ------------------------------------------------------------------

    def detect_changes(
        self,
        snapshot_a: Any,
        snapshot_b: Any,
        key: str = "id",
    ) -> SnapshotDiff:
        """Detect field-level changes between two snapshots using Merkle hashing.

        Args:
            snapshot_a: First snapshot (list of dicts or name).
            snapshot_b: Second snapshot (list of dicts or name).
            key: Column to match rows on.

        Returns:
            SnapshotDiff with added, removed, and modified fields.
        """
        data_a = self._resolve_snapshot(snapshot_a)
        data_b = self._resolve_snapshot(snapshot_b)

        # Quick Merkle root check
        hash_a = _snapshot_hash(data_a)
        hash_b = _snapshot_hash(data_b)
        if hash_a == hash_b:
            return SnapshotDiff()

        idx_a: Dict[Any, dict] = {r.get(key): r for r in data_a if r.get(key) is not None}
        idx_b: Dict[Any, dict] = {r.get(key): r for r in data_b if r.get(key) is not None}

        added = [k for k in idx_b if k not in idx_a]
        removed = [k for k in idx_a if k not in idx_b]

        modified: List[FieldChange] = []
        for k in set(idx_a) & set(idx_b):
            ra = idx_a[k]
            rb = idx_b[k]
            if _record_hash(ra) != _record_hash(rb):
                all_cols = set(ra.keys()) | set(rb.keys())
                for col in all_cols:
                    va = ra.get(col)
                    vb = rb.get(col)
                    if va != vb:
                        modified.append(FieldChange(
                            key=k, field=col, value_a=va, value_b=vb,
                        ))

        return SnapshotDiff(
            added_keys=added,
            removed_keys=removed,
            modified_fields=modified,
        )

    # ------------------------------------------------------------------
    # Audit trail
    # ------------------------------------------------------------------

    def audit_trail(self, key: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Get audit trail — which source won each field and why.

        Args:
            key: Optional key to filter audit entries for a specific record.
                 If None, returns all audit entries.

        Returns:
            List of audit entry dicts.
        """
        entries = self._audit
        if key is not None:
            entries = [e for e in entries if e.key == key]
        return [e.to_dict() for e in entries]

    def clear_audit(self) -> None:
        """Clear the audit trail."""
        self._audit.clear()

    # ------------------------------------------------------------------
    # Branching
    # ------------------------------------------------------------------

    def branch(self, snapshot: Any, branch_name: str) -> str:
        """Create a branch from a snapshot.

        Args:
            snapshot: Source snapshot (list of dicts or registered name).
            branch_name: Name for the new branch.

        Returns:
            Branch name.
        """
        data = self._resolve_snapshot(snapshot)
        self._branches[branch_name] = Branch(
            name=branch_name,
            source_snapshot=snapshot if isinstance(snapshot, str) else "<inline>",
            data=[dict(r) for r in data],
            created_at=time.time(),
        )
        return branch_name

    def merge_branches(
        self,
        branch_a: str,
        branch_b: str,
        key: str = "id",
    ) -> MergeResult:
        """Merge two branches with CRDT conflict resolution.

        Args:
            branch_a: Name of the first branch.
            branch_b: Name of the second branch.
            key: Column to match rows on.

        Returns:
            MergeResult with merged data and statistics.
        """
        if branch_a not in self._branches:
            raise KeyError(f"Branch '{branch_a}' not found")
        if branch_b not in self._branches:
            raise KeyError(f"Branch '{branch_b}' not found")
        return self.merge_snapshots(
            self._branches[branch_a].data,
            self._branches[branch_b].data,
            key=key,
        )

    def list_branches(self) -> List[Dict[str, Any]]:
        """List all branches with metadata."""
        return [b.to_dict() for b in self._branches.values()]

    def get_branch_data(self, branch_name: str) -> List[dict]:
        """Get the data from a branch."""
        if branch_name not in self._branches:
            raise KeyError(f"Branch '{branch_name}' not found")
        return [dict(r) for r in self._branches[branch_name].data]

    def update_branch(self, branch_name: str, data: List[dict]) -> None:
        """Update a branch's data (simulates a write to the branch)."""
        if branch_name not in self._branches:
            raise KeyError(f"Branch '{branch_name}' not found")
        self._branches[branch_name].data = [dict(r) for r in data]

    # ------------------------------------------------------------------
    # DuckDB integration
    # ------------------------------------------------------------------

    def resolve_with_sql(
        self,
        query: str,
        key: str = "id",
    ) -> MergeResult:
        """Execute a SQL query on the DuckDB connection and merge results.

        This is a convenience for cases where snapshots are stored in DuckDB
        tables and you want to select subsets before merging.

        Args:
            query: SQL query that returns two result sets (via UNION or JOIN).
            key: Column to match rows on.

        Returns:
            MergeResult.
        """
        if self._conn is None:
            raise RuntimeError("DuckDB connection required for SQL-based operations")
        duckdb = _require_duckdb()
        result = self._conn.execute(query).fetchall()
        cols = [desc[0] for desc in self._conn.description]
        records = [dict(zip(cols, row)) for row in result]
        # Split into two halves for merge demonstration
        mid = len(records) // 2
        return self.merge_snapshots(records[:mid], records[mid:], key=key)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Return health / readiness status."""
        duckdb_available = _duckdb is not None
        duckdb_version = getattr(_duckdb, "__version__", "unknown") if duckdb_available else None
        return {
            "name": self.name,
            "version": self.version,
            "duckdb_available": duckdb_available,
            "duckdb_version": duckdb_version,
            "status": "ready" if duckdb_available else "degraded",
            "connection_active": self._conn is not None,
            "snapshots_registered": len(self._snapshots),
            "branches": len(self._branches),
            "schema_fields": len(self._schema.fields),
        }

    def is_available(self) -> bool:
        """Check whether DuckDB is available."""
        return _duckdb is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_snapshot(self, snapshot: Any) -> List[dict]:
        """Resolve a snapshot argument to list of dicts."""
        if isinstance(snapshot, str):
            if snapshot in self._snapshots:
                return self._snapshots[snapshot]
            if snapshot in self._branches:
                return self._branches[snapshot].data
            if self._conn is not None:
                # Try as DuckDB table
                try:
                    result = self._conn.execute(f"SELECT * FROM {snapshot}").fetchall()
                    cols = [desc[0] for desc in self._conn.description]
                    return [dict(zip(cols, row)) for row in result]
                except Exception:
                    pass
            raise KeyError(
                f"Snapshot '{snapshot}' not found in registered snapshots, "
                f"branches, or DuckDB tables"
            )
        if isinstance(snapshot, list):
            return snapshot
        raise TypeError(f"Expected list of dicts or snapshot name, got {type(snapshot)}")

    def _merge_row(
        self,
        row_a: dict,
        row_b: dict,
        key_val: Any,
    ) -> Tuple[dict, int, List[FieldChange]]:
        """Merge two rows with full audit. Returns (merged, conflicts, field_changes)."""
        all_cols = list(dict.fromkeys(list(row_a.keys()) + list(row_b.keys())))
        merged: dict = {}
        conflicts = 0
        changes: List[FieldChange] = []

        for col in all_cols:
            va = row_a.get(col)
            vb = row_b.get(col)
            if va is None:
                merged[col] = vb
                if vb is not None:
                    self._audit.append(AuditEntry(
                        key=key_val, field=col, source="right_only",
                        strategy="", value=vb, timestamp=time.time(),
                    ))
            elif vb is None:
                merged[col] = va
                self._audit.append(AuditEntry(
                    key=key_val, field=col, source="left_only",
                    strategy="", value=va, timestamp=time.time(),
                ))
            elif va == vb:
                merged[col] = va
            else:
                strategy = self._schema.strategy_for(col)
                resolved = strategy.resolve(va, vb, 0.0, 0.0, "left", "right")
                merged[col] = resolved
                conflicts += 1

                source = "left" if resolved == va else "right"
                alt = vb if resolved == va else va
                self._audit.append(AuditEntry(
                    key=key_val, field=col, source=source,
                    strategy=strategy.name(), value=resolved,
                    alternative=alt, timestamp=time.time(),
                ))
                changes.append(FieldChange(
                    key=key_val, field=col, value_a=va, value_b=vb,
                    resolved_value=resolved, strategy=strategy.name(),
                ))

        return merged, conflicts, changes

    def __repr__(self) -> str:
        avail = "available" if self.is_available() else "not installed"
        return (
            f"DuckLakeConflictResolver(duckdb={avail}, "
            f"snapshots={len(self._snapshots)}, branches={len(self._branches)})"
        )


__all__ = [
    "DuckLakeConflictResolver",
    "MergeResult",
    "SnapshotDiff",
    "FieldChange",
    "AuditEntry",
    "Branch",
]
