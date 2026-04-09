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
Merge Provenance & Lineage — per-field audit trail for every merge decision.

Know exactly what happened to every field: which source won, which strategy
resolved the conflict, and what the alternative value was. Essential for
compliance, debugging, and trust.

Usage:
    from crdt_merge.provenance import merge_with_provenance, export_provenance

    # Merge with full audit trail
    merged_df, log = merge_with_provenance(df_a, df_b, key="id")

    # Inspect decisions
    for record in log:
        for d in record.conflicts:
            print(f"Row {record.key}, field '{d.field}': "
                  f"chose {d.value!r} over {d.alternative!r} via {d.strategy}")

    # Export for compliance
    json_report = export_provenance(log, format="json")
    csv_report = export_provenance(log, format="csv")

    # With strategies
    from crdt_merge.strategies import MergeSchema, LWW, MaxWins
    schema = MergeSchema(default=LWW(), score=MaxWins())
    merged_df, log = merge_with_provenance(df_a, df_b, key="id", schema=schema)
"""

from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple, Union

from .strategies import MergeSchema, MergeStrategy, LWW

__all__ = ["merge_with_provenance", "export_provenance", "MergeDecision", "MergeRecord", "ProvenanceLog"]

@dataclass
class MergeDecision:
    """Record of how a single field was resolved during merge.

    Attributes:
        field: Column/field name.
        source: Where the value came from — "a", "b", "both_equal",
                "a_only", "b_only", or "conflict_resolved".
        strategy: Name of the strategy that resolved it (e.g. "LWW", "MaxWins").
                  Empty string if no conflict resolution was needed.
        value: The final value after merge.
        alternative: The value that was NOT chosen (None if no conflict).
    """
    field: str
    source: str
    strategy: str
    value: Any
    alternative: Any = None

    def was_conflict(self) -> bool:
        """True if this field had a real conflict that needed resolution."""
        return self.source == "conflict_resolved"

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "source": self.source,
            "strategy": self.strategy,
            "value": _safe_repr(self.value),
            "alternative": _safe_repr(self.alternative),
        }

@dataclass
class MergeRecord:
    """Complete provenance for one merged row.

    Attributes:
        key: The primary key value of this row.
        origin: How this row entered the merge — "merged", "unique_a", or "unique_b".
        decisions: Per-field merge decisions.
        conflict_count: Number of fields that had real conflicts.
    """
    key: Any
    origin: str  # "merged", "unique_a", "unique_b"
    decisions: List[MergeDecision] = field(default_factory=list)

    @property
    def conflict_count(self) -> int:
        return sum(1 for d in self.decisions if d.was_conflict())

    @property
    def conflicts(self) -> List[MergeDecision]:
        """Return only decisions where a real conflict was resolved."""
        return [d for d in self.decisions if d.was_conflict()]

    @property
    def fields_from_a(self) -> List[str]:
        return [d.field for d in self.decisions if d.source in ("a", "a_only")]

    @property
    def fields_from_b(self) -> List[str]:
        return [d.field for d in self.decisions if d.source in ("b", "b_only")]

    def to_dict(self) -> dict:
        return {
            "key": _safe_repr(self.key),
            "origin": self.origin,
            "conflict_count": self.conflict_count,
            "decisions": [d.to_dict() for d in self.decisions],
        }

@dataclass
class ProvenanceLog:
    """Complete provenance log for a merge operation.

    Attributes:
        records: Per-row provenance records.
        total_rows: Total rows in merged output.
        total_conflicts: Total field-level conflicts resolved.
        merged_rows: Rows that existed in both sources.
        unique_a_rows: Rows only in source A.
        unique_b_rows: Rows only in source B.
        duration_ms: Time taken for the merge.
    """
    records: List[MergeRecord] = field(default_factory=list)
    total_rows: int = 0
    merged_rows: int = 0
    unique_a_rows: int = 0
    unique_b_rows: int = 0
    total_conflicts: int = 0
    duration_ms: float = 0.0

    def summary(self) -> str:
        lines = [
            "Merge Provenance Report",
            "=" * 40,
            f"Total rows:      {self.total_rows}",
            f"  Merged:        {self.merged_rows}",
            f"  Unique to A:   {self.unique_a_rows}",
            f"  Unique to B:   {self.unique_b_rows}",
            f"Total conflicts: {self.total_conflicts}",
            f"Duration:        {self.duration_ms:.1f}ms",
        ]
        if self.total_conflicts > 0:
            lines.append(f"\nConflict Details:")
            for rec in self.records:
                for c in rec.conflicts:
                    lines.append(
                        f"  Row {rec.key!r}, '{c.field}': "
                        f"{c.value!r} ← {c.strategy} (alt: {c.alternative!r})"
                    )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "total_rows": self.total_rows,
            "merged_rows": self.merged_rows,
            "unique_a_rows": self.unique_a_rows,
            "unique_b_rows": self.unique_b_rows,
            "total_conflicts": self.total_conflicts,
            "duration_ms": self.duration_ms,
            "records": [r.to_dict() for r in self.records],
        }

    def __repr__(self):
        return (f"ProvenanceLog(rows={self.total_rows}, conflicts={self.total_conflicts}, "
                f"{self.duration_ms:.1f}ms)")

def _safe_repr(val: Any) -> Any:
    """Convert value to JSON-safe representation."""
    if val is None:
        return None
    if isinstance(val, (int, float, str, bool)):
        return val
    if isinstance(val, (list, tuple)):
        return [_safe_repr(v) for v in val]
    if isinstance(val, dict):
        return {str(k): _safe_repr(v) for k, v in val.items()}
    if isinstance(val, set):
        return sorted(_safe_repr(v) for v in val)
    return str(val)

def _resolve_with_provenance(
    row_a: dict, row_b: dict, key_val: Any, columns: list,
    schema: Optional[MergeSchema], timestamp_col: Optional[str],
    default_strategy: MergeStrategy,
) -> Tuple[dict, MergeRecord]:
    """Merge two rows and produce full provenance record."""
    result = {}
    record = MergeRecord(key=key_val, origin="merged")

    ts_a = float(row_a.get(timestamp_col, 0)) if timestamp_col else 0.0
    ts_b = float(row_b.get(timestamp_col, 0)) if timestamp_col else 0.0

    for col in columns:
        val_a = row_a.get(col)
        val_b = row_b.get(col)

        if val_a is None and val_b is not None:
            result[col] = val_b
            record.decisions.append(MergeDecision(
                field=col, source="b_only", strategy="", value=val_b))
        elif val_b is None and val_a is not None:
            result[col] = val_a
            record.decisions.append(MergeDecision(
                field=col, source="a_only", strategy="", value=val_a))
        elif val_a == val_b:
            result[col] = val_a
            record.decisions.append(MergeDecision(
                field=col, source="both_equal", strategy="", value=val_a))
        else:
            # Real conflict -- resolve with strategy
            strategy = schema.strategy_for(col) if schema else default_strategy
            resolved = strategy.resolve(val_a, val_b, ts_a, ts_b)
            # Determine which source won
            if resolved == val_a:
                winner_source = "a"
                alt = val_b
            elif resolved == val_b:
                winner_source = "b"
                alt = val_a
            else:
                winner_source = "computed"
                alt = (val_a, val_b)
            result[col] = resolved
            record.decisions.append(MergeDecision(
                field=col, source="conflict_resolved", strategy=strategy.name(),
                value=resolved, alternative=alt))

    return result, record

def merge_with_provenance(
    df_a, df_b, key: str = "id",
    schema: Optional[MergeSchema] = None,
    timestamp_col: Optional[str] = None,
) -> Tuple:
    """
    Merge two DataFrames/list-of-dicts and return full provenance audit trail.

    This is the same merge as crdt_merge.merge(), but with complete per-field
    lineage tracking. Use this when you need to know WHY the merge produced
    a particular result.

    Args:
        df_a: First DataFrame or list of dicts.
        df_b: Second DataFrame or list of dicts.
        key: Primary key column.
        schema: Optional MergeSchema for per-column strategies.
        timestamp_col: Column name for LWW timestamps.

    Returns:
        Tuple of (merged_data, ProvenanceLog).
        merged_data is a list of dicts (always — even if inputs were DataFrames).
        Convert back to DataFrame with pd.DataFrame(merged_data) if needed.
    """
    start = time.time()
    default_strategy = LWW()

    # Normalize inputs to list of dicts
    rows_a = _to_dicts(df_a, key)
    rows_b = _to_dicts(df_b, key)

    # Build index from source B
    b_index: Dict[Any, dict] = {row[key]: row for row in rows_b}

    # Compute column list once
    all_cols: Optional[list] = None
    merged_rows = []
    log = ProvenanceLog()

    # Process source A
    for row_a in rows_a:
        k = row_a.get(key)
        if k is None:
            merged_rows.append(row_a)
            record = MergeRecord(key=None, origin="unique_a")
            for col, val in row_a.items():
                record.decisions.append(MergeDecision(
                    field=col, source="a_only", strategy="", value=val))
            log.records.append(record)
            log.unique_a_rows += 1
            continue
        if k in b_index:
            row_b = b_index.pop(k)
            if all_cols is None:
                all_cols = list(dict.fromkeys(list(row_a.keys()) + list(row_b.keys())))
            merged, record = _resolve_with_provenance(
                row_a, row_b, k, all_cols, schema, timestamp_col, default_strategy
            )
            merged_rows.append(merged)
            log.records.append(record)
            log.merged_rows += 1
            log.total_conflicts += record.conflict_count
        else:
            merged_rows.append(row_a)
            record = MergeRecord(key=k, origin="unique_a")
            for col, val in row_a.items():
                record.decisions.append(MergeDecision(
                    field=col, source="a_only", strategy="", value=val))
            log.records.append(record)
            log.unique_a_rows += 1

    # Remaining from source B (unique to B)
    for k, row_b in b_index.items():
        merged_rows.append(row_b)
        record = MergeRecord(key=k, origin="unique_b")
        for col, val in row_b.items():
            record.decisions.append(MergeDecision(
                field=col, source="b_only", strategy="", value=val))
        log.records.append(record)
        log.unique_b_rows += 1

    log.total_rows = len(merged_rows)
    log.duration_ms = (time.time() - start) * 1000

    # DEF-006: Convert back to original DataFrame type if input was a DataFrame
    if hasattr(df_a, 'to_dict') and hasattr(df_a, 'columns'):
        # pandas DataFrame
        import pandas as pd
        merged_data = pd.DataFrame(merged_rows)
    elif hasattr(df_a, 'to_dicts') and hasattr(df_a, 'columns'):
        # polars DataFrame
        import polars as pl
        merged_data = pl.DataFrame(merged_rows)
    else:
        merged_data = merged_rows

    return merged_data, log

def _to_dicts(data, key: str) -> list:
    """Convert DataFrame or list-of-dicts to list-of-dicts."""
    if isinstance(data, list):
        return data
    # pandas DataFrame
    if hasattr(data, 'to_dict'):
        return data.to_dict('records')
    # Already iterable of dicts
    return list(data)

def export_provenance(log: ProvenanceLog, format: str = "json") -> str:
    """
    Export provenance log to JSON or CSV string.

    Args:
        log: The ProvenanceLog to export.
        format: "json" or "csv".

    Returns:
        String in the requested format.
    """
    if format == "json":
        return json.dumps(log.to_dict(), indent=2, default=str)
    elif format == "csv":
        lines = ["key,origin,field,source,strategy,value,alternative"]
        for rec in log.records:
            for d in rec.decisions:
                val = str(d.value).replace('"', '""') if d.value is not None else ""
                alt = str(d.alternative).replace('"', '""') if d.alternative is not None else ""
                lines.append(
                    f'"{rec.key}","{rec.origin}","{d.field}","{d.source}",'
                    f'"{d.strategy}","{val}","{alt}"'
                )
        return "\n".join(lines)
    else:
        raise ValueError(f"Unknown format: {format}. Use 'json' or 'csv'.")
