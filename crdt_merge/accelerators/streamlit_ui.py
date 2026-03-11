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
Streamlit Visual Merge UI — interactive conflict resolution component.

Displays two data sources side by side with conflicting cells highlighted in
amber.  Users can override resolution strategies per column and export merged
results to Parquet.

All external dependencies use **lazy imports** — the module is importable even
without ``streamlit`` installed.

Example::

    from crdt_merge.accelerators.streamlit_ui import StreamlitMergeUI
    ui = StreamlitMergeUI(schema=my_schema)
    ui.render(left_data, right_data, key="id")
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

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
# Strategy name lookup (reused in the UI drop-downs)
# ---------------------------------------------------------------------------

_STRATEGY_MAP: Dict[str, type] = {
    "lww": LWW,
    "max": MaxWins,
    "min": MinWins,
    "union": UnionSet,
    "concat": Concat,
    "longest": LongestWins,
}

_STRATEGY_LABELS: List[str] = list(_STRATEGY_MAP.keys())

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_records(data: Any) -> List[Dict[str, Any]]:
    """Normalise data into a list of dicts."""
    if isinstance(data, list):
        return data
    # pandas / polars DataFrames
    if hasattr(data, "to_dict"):
        try:
            return data.to_dict(orient="records")  # type: ignore[union-attr]  # data is pandas DataFrame at this point (checked above)
        except TypeError:
            return data.to_dicts()  # polars
    if hasattr(data, "to_dicts"):
        return data.to_dicts()
    raise TypeError(f"Unsupported data type: {type(data)}")

def _detect_conflicts(
    left: List[Dict[str, Any]],
    right: List[Dict[str, Any]],
    key: str,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Return list of conflict dicts and all column names."""
    right_by_key = {r[key]: r for r in right}
    all_cols: set = set()
    for r in left:
        all_cols.update(r.keys())
    for r in right:
        all_cols.update(r.keys())
    all_cols.discard(key)
    sorted_cols = sorted(all_cols)

    conflicts: List[Dict[str, Any]] = []
    for row_l in left:
        k = row_l.get(key)
        row_r = right_by_key.get(k)
        if row_r is None:
            continue
        for col in sorted_cols:
            val_l = row_l.get(col)
            val_r = row_r.get(col)
            if val_l != val_r and val_l is not None and val_r is not None:
                conflicts.append({
                    "key": k,
                    "field": col,
                    "left_value": val_l,
                    "right_value": val_r,
                })
    return conflicts, sorted_cols

def _resolve_merge(
    left: List[Dict[str, Any]],
    right: List[Dict[str, Any]],
    key: str,
    schema: MergeSchema,
) -> List[Dict[str, Any]]:
    """Perform a merge using the given schema."""
    right_by_key = {r[key]: r for r in right}
    left_by_key = {r[key]: r for r in left}
    all_keys_ordered: List[Any] = []
    seen: set = set()
    for r in left:
        k = r[key]
        if k not in seen:
            all_keys_ordered.append(k)
            seen.add(k)
    for r in right:
        k = r[key]
        if k not in seen:
            all_keys_ordered.append(k)
            seen.add(k)

    merged: List[Dict[str, Any]] = []
    for k in all_keys_ordered:
        row_l = left_by_key.get(k)
        row_r = right_by_key.get(k)
        if row_l and row_r:
            merged.append(schema.resolve_row(row_l, row_r))
        elif row_l:
            merged.append(dict(row_l))
        elif row_r:
            merged.append(dict(row_r))
    return merged

# ---------------------------------------------------------------------------
# Streamlit Merge UI
# ---------------------------------------------------------------------------

@register_accelerator
class StreamlitMergeUI:
    """Streamlit component for visual merge conflict resolution.

    Displays two data sources side by side with conflicting cells
    highlighted in amber. Users can override resolution strategies
    per column and export merged results to Parquet.

    Attributes:
        name: Accelerator name.
        version: Accelerator version.
    """

    name: str = "streamlit_ui"
    version: str = "0.7.0"

    def __init__(
        self,
        schema: Optional[MergeSchema] = None,
        title: str = "CRDT Merge Conflict Resolution",
    ) -> None:
        """Initialize the Streamlit merge UI.

        Args:
            schema: Merge schema with per-field strategies.
            title: Title shown at the top of the component.
        """
        self._schema = schema or MergeSchema()
        self._title = title
        self._st: Any = None  # lazy streamlit reference

    # -- Lazy import --------------------------------------------------------

    def _get_streamlit(self) -> Any:
        """Lazily import ``streamlit``."""
        if self._st is not None:
            return self._st
        try:
            import streamlit as st  # type: ignore[import-untyped]  # optional dep: streamlit lacks py.typed
            self._st = st
            return st
        except ImportError:
            raise ImportError(
                "Streamlit is required for StreamlitMergeUI. "
                "Install it with: pip install streamlit"
            )

    # -- Public API ---------------------------------------------------------

    def render(
        self,
        left: Any,
        right: Any,
        key: str,
        strategies: Optional[Dict[str, str]] = None,
    ) -> Optional[List[dict]]:
        """Render the merge UI in Streamlit and return resolved data.

        Displays:
        1. Title header
        2. Side-by-side data tables with conflicts highlighted
        3. Per-column strategy selectors
        4. Merge button → merged result table
        5. Export-to-Parquet download button

        Args:
            left: Left data source (list of dicts or DataFrame).
            right: Right data source (list of dicts or DataFrame).
            key: Join key column.
            strategies: Optional per-field strategy overrides.

        Returns:
            Merged data as list of dicts (after user clicks merge), or ``None``.
        """
        st = self._get_streamlit()

        left_recs = _to_records(left)
        right_recs = _to_records(right)

        # Apply user-supplied strategy overrides
        schema = self._schema
        if strategies:
            for col, strat_name in strategies.items():
                cls = _STRATEGY_MAP.get(strat_name.lower())
                if cls:
                    schema.set_strategy(col, cls())

        st.header(self._title)

        # Side-by-side tables
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Source A")
            st.dataframe(left_recs)
        with col2:
            st.subheader("Source B")
            st.dataframe(right_recs)

        # Conflict detection
        conflicts, all_cols = _detect_conflicts(left_recs, right_recs, key)

        if conflicts:
            st.warning(f"⚠️ {len(conflicts)} conflicts detected across "
                        f"{len(set(c['field'] for c in conflicts))} fields")
            self.render_conflicts(conflicts)
        else:
            st.success("✅ No conflicts detected.")

        # Strategy selectors
        st.subheader("Strategy Overrides")
        chosen: Dict[str, str] = {}
        for col in all_cols:
            current = schema.strategy_for(col).name()
            chosen[col] = st.selectbox(
                f"Strategy for '{col}'",
                _STRATEGY_LABELS,
                index=0,
                key=f"strategy_{col}",
            )

        # Apply chosen strategies
        for col, strat_name in chosen.items():
            cls = _STRATEGY_MAP.get(strat_name)
            if cls:
                schema.set_strategy(col, cls())

        # Merge button
        merged_data: Optional[List[dict]] = None
        if st.button("🔀 Merge"):
            merged_data = _resolve_merge(left_recs, right_recs, key, schema)
            st.subheader("Merged Result")
            st.dataframe(merged_data)
            st.success(f"✅ Merged {len(merged_data)} records.")

        return merged_data

    def render_conflicts(self, conflicts: List[Dict[str, Any]]) -> None:
        """Render a conflict heatmap visualization.

        Args:
            conflicts: List of conflict dicts with ``key``, ``field``,
                ``left_value``, ``right_value``.
        """
        st = self._get_streamlit()
        st.subheader("Conflict Details")
        for c in conflicts:
            st.markdown(
                f"**Row** `{c['key']}` · **Field** `{c['field']}`: "
                f"`{c.get('left_value')}` ↔ `{c.get('right_value')}`"
            )

    def render_provenance(self, provenance: List[Dict[str, Any]]) -> None:
        """Render provenance trail for merged records.

        Args:
            provenance: List of provenance dicts.
        """
        st = self._get_streamlit()
        st.subheader("Merge Provenance")
        for entry in provenance:
            key = entry.get("key", "?")
            decisions = entry.get("decisions", [])
            with st.expander(f"Row {key}"):
                for d in decisions:
                    source = d.get("source", "?")
                    field_name = d.get("field", "?")
                    value = d.get("value", "?")
                    st.text(f"  {field_name}: {value} (from {source})")

    def export_parquet(self, data: List[dict], filename: str = "merged.parquet") -> None:
        """Export merged results to downloadable Parquet file.

        Requires ``pyarrow``. Falls back to CSV if unavailable.

        Args:
            data: Merged records.
            filename: Download filename.
        """
        st = self._get_streamlit()
        try:
            import pyarrow as pa  # type: ignore[import-untyped]  # optional dep: pyarrow lacks py.typed
            import pyarrow.parquet as pq

            table = pa.Table.from_pylist(data)
            buf = pa.BufferOutputStream()
            pq.write_table(table, buf)
            st.download_button(
                "⬇️ Download Parquet",
                data=buf.getvalue().to_pybytes(),
                file_name=filename,
                mime="application/octet-stream",
            )
        except ImportError:
            import csv as _csv
            import io as _io

            buf_str = _io.StringIO()
            if data:
                writer = _csv.DictWriter(buf_str, fieldnames=list(data[0].keys()))
                writer.writeheader()
                writer.writerows(data)
            st.download_button(
                "⬇️ Download CSV (Parquet unavailable)",
                data=buf_str.getvalue(),
                file_name=filename.replace(".parquet", ".csv"),
                mime="text/csv",
            )

    # -- Health check -------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Return health / readiness status.

        Returns:
            Dict with ``status``, ``streamlit_available``, and version info.
        """
        try:
            import streamlit  # type: ignore[import-untyped]  # optional dep: streamlit lacks py.typed
            st_version = getattr(streamlit, "__version__", "unknown")
            available = True
        except ImportError:
            st_version = None
            available = False

        return {
            "name": self.name,
            "version": self.version,
            "streamlit_available": available,
            "streamlit_version": st_version,
            "status": "ok" if available else "streamlit_not_installed",
        }

    def is_available(self) -> bool:
        """Check whether streamlit is available."""
        try:
            import streamlit  # type: ignore[import-untyped]  # noqa: F401 — import tests availability; streamlit lacks py.typed
            return True
        except ImportError:
            return False

    def __repr__(self) -> str:
        return f"StreamlitMergeUI(title={self._title!r})"
