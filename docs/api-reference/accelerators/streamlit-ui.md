# `crdt_merge/accelerators/streamlit_ui.py`

> Streamlit Visual Merge UI — interactive conflict resolution component.

Displays two data sources side by side with conflicting cells highlighted in
amber.  Users can override resolution strategies per column and export merged
results to Parquet.

All external dependencies use **lazy imports** — the

**Source:** `crdt_merge/accelerators/streamlit_ui.py` | **Lines:** 400

---

## Classes

### `class StreamlitMergeUI`

Streamlit component for visual merge conflict resolution.

    Displays two data sources side by side with conflicting cells
    highlighted in amber. Users can override resolution strategies
    per column and export merged results to Parquet.

    Attributes:
        name: Accelerator name.
        version: Accelerator version.

- `name`: `str`
- `version`: `str`

**Methods:**

#### `StreamlitMergeUI.__init__(self, schema: Optional[MergeSchema] = None, title: str = 'CRDT Merge Conflict Resolution') → None`

Initialize the Streamlit merge UI.

        Args:
            schema: Merge schema with per-field strategies.
            title: Title shown at the top of the component.

#### `StreamlitMergeUI._get_streamlit(self) → Any`

Lazily import ``streamlit``.

#### `StreamlitMergeUI.render(self, left: Any, right: Any, key: str, strategies: Optional[Dict[str, str]] = None) → Optional[List[dict]]`

Render the merge UI in Streamlit and return resolved data.

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

#### `StreamlitMergeUI.render_conflicts(self, conflicts: List[Dict[str, Any]]) → None`

Render a conflict heatmap visualization.

        Args:
            conflicts: List of conflict dicts with ``key``, ``field``,
                ``left_value``, ``right_value``.

#### `StreamlitMergeUI.render_provenance(self, provenance: List[Dict[str, Any]]) → None`

Render provenance trail for merged records.

        Args:
            provenance: List of provenance dicts.

#### `StreamlitMergeUI.export_parquet(self, data: List[dict], filename: str = 'merged.parquet') → None`

Export merged results to downloadable Parquet file.

        Requires ``pyarrow``. Falls back to CSV if unavailable.

        Args:
            data: Merged records.
            filename: Download filename.

#### `StreamlitMergeUI.health_check(self) → Dict[str, Any]`

Return health / readiness status.

        Returns:
            Dict with ``status``, ``streamlit_available``, and version info.

#### `StreamlitMergeUI.is_available(self) → bool`

Check whether streamlit is available.

#### `StreamlitMergeUI.__repr__(self) → str`

*No docstring*


## Functions

### `_to_records(data: Any) → List[Dict[str, Any]]`

Normalise data into a list of dicts.

### `_detect_conflicts(left: List[Dict[str, Any]], right: List[Dict[str, Any]], key: str) → Tuple[List[Dict[str, Any]], List[str]]`

Return list of conflict dicts and all column names.

### `_resolve_merge(left: List[Dict[str, Any]], right: List[Dict[str, Any]], key: str, schema: MergeSchema) → List[Dict[str, Any]]`

Perform a merge using the given schema.

