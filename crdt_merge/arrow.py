# Copyright 2026 Ryan Gillespie
# SPDX-License-Identifier: Apache-2.0
#
# Commercial licensing: data@optitransfer.ch, rgillespie83@icloud.com

"""Apache Arrow-native merge engine for high-performance CRDT merges.

PyArrow is OPTIONAL — lazy imported. Falls back to pure-Python if unavailable.

Usage:
    from crdt_merge.arrow import arrow_merge, ArrowMerge

    # One-shot convenience merge
    merged = arrow_merge(left_table, right_table, key="id")

    # Engine with custom schema
    engine = ArrowMerge(schema=my_schema, timestamp_col="_ts")
    merged = engine.merge(left_table, right_table, key="id")

    # Streaming batch merge
    for batch in engine.merge_batches(batch_iterator, key="id"):
        process(batch)

    # File-based merge
    stats = engine.merge_ipc("left.arrow", "right.arrow", "out.arrow", key="id")
"""

from __future__ import annotations

import os
import tempfile
from typing import (
    Any,
    Dict,
    Generator,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from crdt_merge.strategies import MergeSchema, MergeStrategy, LWW
from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy


# ---------------------------------------------------------------------------
# Lazy import helpers
# ---------------------------------------------------------------------------


def _import_pyarrow():
    """Import and return the pyarrow module, raising a clear error if missing."""
    try:
        import pyarrow as pa
        return pa
    except ImportError:
        raise ImportError(
            "pyarrow is required for Arrow merge operations. "
            "Install with: pip install pyarrow"
        )


def _has_pyarrow() -> bool:
    """Return True if pyarrow is importable."""
    try:
        import pyarrow  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_table(obj: Any, pa: Any) -> Any:
    """Convert *obj* to a ``pa.Table`` if it is a RecordBatch or list[dict].

    Returns the object unchanged if it is already a Table.
    Raises TypeError for unsupported types.
    """
    if isinstance(obj, pa.Table):
        return obj
    if isinstance(obj, pa.RecordBatch):
        return pa.Table.from_batches([obj])
    if isinstance(obj, list):
        if len(obj) == 0:
            return pa.table({})
        if isinstance(obj[0], dict):
            return pa.Table.from_pylist(obj)
        raise TypeError(
            f"Cannot convert list of {type(obj[0]).__name__} to Arrow Table"
        )
    raise TypeError(
        f"Unsupported input type {type(obj).__name__}. "
        "Expected pa.Table, pa.RecordBatch, or list[dict]."
    )


def _arrow_type_string(arrow_type: Any) -> str:
    """Convert a pyarrow type to a comparable string."""
    return str(arrow_type)


def _schema_dict(table: Any) -> Dict[str, str]:
    """Extract {column: type_string} from a pa.Table."""
    return {field.name: _arrow_type_string(field.type) for field in table.schema}


def _align_table_to_schema(
    table: Any,
    resolved_schema: Dict[str, str],
    pa: Any,
) -> Any:
    """Add missing columns (as all-null) and reorder to match *resolved_schema*.

    This is used after schema evolution to ensure both tables have the same
    column set before merging.
    """
    existing = set(table.column_names)
    arrays = []
    names = []

    for col_name in sorted(resolved_schema.keys()):
        names.append(col_name)
        if col_name in existing:
            arrays.append(table.column(col_name))
        else:
            # Create a null-filled column with the same length
            null_array = pa.nulls(len(table))
            arrays.append(null_array)

    return pa.table(dict(zip(names, arrays)))


def _resolve_column(
    left_col: List[Any],
    right_col: List[Any],
    strategy: MergeStrategy,
    ts_left: Optional[List[float]] = None,
    ts_right: Optional[List[float]] = None,
) -> List[Any]:
    """Apply a merge strategy element-wise to two aligned columns.

    Both columns must be the same length (matched rows only).
    Returns a list of resolved values.
    """
    result = []
    n = len(left_col)
    for i in range(n):
        va = left_col[i]
        vb = right_col[i]
        tsa = ts_left[i] if ts_left else 0.0
        tsb = ts_right[i] if ts_right else 0.0

        if va is None and vb is not None:
            result.append(vb)
        elif vb is None and va is not None:
            result.append(va)
        elif va == vb:
            result.append(va)
        else:
            result.append(strategy.resolve(va, vb, tsa, tsb, "a", "b"))
    return result


def _table_to_row_dicts(table: Any) -> List[Dict[str, Any]]:
    """Convert a pa.Table to a list of dicts (row-oriented)."""
    return table.to_pylist()


def _build_key_index(
    rows: List[Dict[str, Any]], key: str
) -> Dict[Any, int]:
    """Build {key_value: row_index} mapping. Last occurrence wins for dups."""
    idx: Dict[Any, int] = {}
    for i, row in enumerate(rows):
        k = row.get(key)
        if k is not None:
            idx[k] = i
    return idx


def _concat_tables(left: Any, right: Any, pa: Any) -> Any:
    """Concatenate two tables, aligning schemas first."""
    left_cols = set(left.column_names)
    right_cols = set(right.column_names)

    if left_cols == right_cols:
        return pa.concat_tables([left, right], promote_options="default")

    # Align schemas: add missing columns to each
    all_cols = sorted(left_cols | right_cols)

    def _align(table: Any, all_columns: List[str]) -> Any:
        existing = set(table.column_names)
        arrays = {}
        for col in all_columns:
            if col in existing:
                arrays[col] = table.column(col)
            else:
                arrays[col] = pa.nulls(len(table))
        return pa.table(arrays)

    left_aligned = _align(left, all_cols)
    right_aligned = _align(right, all_cols)
    return pa.concat_tables([left_aligned, right_aligned], promote_options="default")


def _dedup_table(table: Any, pa: Any) -> Any:
    """Remove exact duplicate rows from a table.

    Uses a set of tuples for O(n) dedup.
    """
    rows = table.to_pylist()
    if not rows:
        return table
    seen = set()
    unique = []
    for row in rows:
        key = tuple(sorted(row.items()))
        if key not in seen:
            seen.add(key)
            unique.append(row)
    if len(unique) == len(rows):
        return table
    return pa.Table.from_pylist(unique, schema=table.schema) if unique else pa.table(
        {col: pa.array([], type=table.schema.field(col).type) for col in table.column_names}
    )


# ---------------------------------------------------------------------------
# ArrowMerge — main merge engine
# ---------------------------------------------------------------------------


class ArrowMerge:
    """Arrow-native CRDT merge engine.

    Merges two or more Arrow tables using configurable per-column CRDT
    strategies.  Supports keyed merges, streaming batch merges, and
    file-based IPC merges.

    Parameters
    ----------
    schema : MergeSchema or None
        Per-column merge strategies.  Falls back to LWW for every column
        when *None*.
    timestamp_col : str or None
        Name of the column that carries row timestamps for LWW resolution.
    """

    def __init__(
        self,
        schema: Optional[Any] = None,
        timestamp_col: Optional[str] = None,
        engine: str = "auto",
    ) -> None:
        self._schema: Optional[MergeSchema] = schema
        self._timestamp_col: Optional[str] = timestamp_col
        self._engine = engine  # "auto", "polars", or "python"

    # ----- properties --------------------------------------------------------

    @property
    def schema(self) -> Optional[MergeSchema]:
        """Return the configured MergeSchema (may be None)."""
        return self._schema

    @property
    def timestamp_col(self) -> Optional[str]:
        """Return the configured timestamp column name."""
        return self._timestamp_col

    # ----- core merge --------------------------------------------------------

    def merge(
        self,
        left: Any,
        right: Any,
        key: Optional[str] = None,
    ) -> Any:
        """Merge two Arrow tables using CRDT strategies.

        Parameters
        ----------
        left, right :
            ``pa.Table``, ``pa.RecordBatch``, or ``list[dict]``.
        key : str or None
            Column to join on.  When *None*, the tables are concatenated
            and duplicate rows are removed.

        Returns
        -------
        pa.Table
            The merged result.
        """
        pa = _import_pyarrow()

        left = _ensure_table(left, pa)
        right = _ensure_table(right, pa)

        # --- schema evolution ---
        left, right = self._evolve_schemas(left, right, pa)

        if key is None:
            return self._merge_no_key(left, right, pa)

        return self._merge_with_key(left, right, key, pa)

    # ----- streaming merge ---------------------------------------------------

    def merge_batches(
        self,
        batches: Iterator[Any],
        key: Optional[str] = None,
        batch_size: int = 10000,
    ) -> Generator[Any, None, None]:
        """Streaming merge for Arrow IPC record batches.

        Accumulates batches, merges when accumulated row count reaches
        *batch_size*, and yields the merged result as a ``pa.RecordBatch``.

        Parameters
        ----------
        batches :
            Iterator of ``pa.RecordBatch`` or ``pa.Table``.
        key : str or None
            Column to join on.
        batch_size :
            Target number of rows per output batch.

        Yields
        ------
        pa.RecordBatch
        """
        pa = _import_pyarrow()

        accumulated: Optional[Any] = None  # pa.Table or None
        accumulated_rows = 0

        for batch in batches:
            table = _ensure_table(batch, pa)
            if len(table) == 0:
                continue

            if accumulated is None:
                accumulated = table
                accumulated_rows = len(table)
            else:
                accumulated = self.merge(accumulated, table, key=key)
                accumulated_rows = len(accumulated)

            # Yield when we reach the target batch size
            while accumulated_rows >= batch_size:
                # Yield a slice of batch_size rows
                if accumulated_rows > batch_size:
                    yield_table = accumulated.slice(0, batch_size)
                    accumulated = accumulated.slice(batch_size)
                    accumulated_rows = len(accumulated)
                else:
                    yield_table = accumulated
                    accumulated = None
                    accumulated_rows = 0
                yield yield_table.to_batches()[0] if len(yield_table) > 0 else pa.record_batch({})

        # Yield remaining rows
        if accumulated is not None and len(accumulated) > 0:
            yield accumulated.to_batches()[0]

    # ----- IPC file merge ----------------------------------------------------

    def merge_ipc(
        self,
        left_path: str,
        right_path: str,
        output_path: str,
        key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Merge two Arrow IPC files and write the result.

        Parameters
        ----------
        left_path, right_path :
            Paths to Arrow IPC files.
        output_path :
            Path for the merged output IPC file.
        key : str or None
            Column to join on.

        Returns
        -------
        dict
            Statistics: ``{"rows_left", "rows_right", "rows_merged",
            "output_path"}``.
        """
        pa = _import_pyarrow()

        # Read input files
        left_reader = pa.ipc.open_file(left_path)
        right_reader = pa.ipc.open_file(right_path)

        left_table = left_reader.read_all()
        right_table = right_reader.read_all()

        rows_left = len(left_table)
        rows_right = len(right_table)

        # Merge
        merged = self.merge(left_table, right_table, key=key)

        # Write output
        writer = pa.ipc.new_file(output_path, merged.schema)
        writer.write_table(merged)
        writer.close()

        return {
            "rows_left": rows_left,
            "rows_right": rows_right,
            "rows_merged": len(merged),
            "output_path": output_path,
        }

    # ----- memory-mapped merge -----------------------------------------------

    def merge_memory_mapped(
        self,
        left_path: str,
        right_path: str,
        key: Optional[str] = None,
    ) -> Any:
        """Merge two Arrow IPC files using memory-mapped I/O.

        Parameters
        ----------
        left_path, right_path :
            Paths to Arrow IPC files.
        key : str or None
            Column to join on.

        Returns
        -------
        pa.Table
            The merged result.
        """
        pa = _import_pyarrow()

        left_mmap = pa.memory_map(left_path, "r")
        right_mmap = pa.memory_map(right_path, "r")

        left_reader = pa.ipc.open_file(left_mmap)
        right_reader = pa.ipc.open_file(right_mmap)

        left_table = left_reader.read_all()
        right_table = right_reader.read_all()

        result = self.merge(left_table, right_table, key=key)

        left_mmap.close()
        right_mmap.close()

        return result

    # ----- private helpers ---------------------------------------------------

    def _get_strategy(self, col: str) -> MergeStrategy:
        """Return the merge strategy for a given column."""
        if self._schema is not None:
            return self._schema.strategy_for(col)
        return LWW()

    def _evolve_schemas(
        self,
        left: Any,
        right: Any,
        pa: Any,
    ) -> Tuple[Any, Any]:
        """Apply schema evolution if the two tables have different schemas.

        Returns the (possibly modified) left and right tables with aligned
        columns.
        """
        left_sd = _schema_dict(left)
        right_sd = _schema_dict(right)

        if left_sd == right_sd:
            return left, right

        result = evolve_schema(left_sd, right_sd, SchemaPolicy.UNION)
        resolved = result.resolved_schema

        left = _align_table_to_schema(left, resolved, pa)
        right = _align_table_to_schema(right, resolved, pa)

        return left, right

    def _merge_no_key(self, left: Any, right: Any, pa: Any) -> Any:
        """Concatenate and dedup when no key column is specified."""
        combined = _concat_tables(left, right, pa)
        return _dedup_table(combined, pa)

    def _merge_with_key(
        self,
        left: Any,
        right: Any,
        key: str,
        pa: Any,
    ) -> Any:
        """Merge two tables on a key column using per-column strategies.

        When Polars is installed and ``engine`` is ``"auto"`` or ``"polars"``,
        the merge runs entirely in Polars' Rust engine — typically 50-115×
        faster than the pure-Python path.  Install with::

            pip install crdt-merge[fast]
        """
        # ── Polars fast path ─────────────────────────────────────
        use_polars = (
            self._engine in ("auto", "polars")
            and HAS_POLARS
            and polars_merge_arrow is not None
            and self._schema is not None
        )
        if use_polars:
            try:
                result_table, _ = polars_merge_arrow(
                    left, right, key, self._schema, self._timestamp_col
                )
                return result_table
            except Exception as exc:
                if self._engine == "polars":
                    raise  # explicit engine request — don't silently fall back
                logger.warning(
                    "Polars fast path failed, falling back to Python: %s", exc
                )

        # ── Pure-Python path (fallback) ──────────────────────────
        # Validate key exists
        if key not in left.column_names and key not in right.column_names:
            raise ValueError(
                f"Key column '{key}' not found in either table. "
                f"Left columns: {left.column_names}, "
                f"Right columns: {right.column_names}"
            )
        if key not in left.column_names:
            raise ValueError(
                f"Key column '{key}' not found in left table. "
                f"Available: {left.column_names}"
            )
        if key not in right.column_names:
            raise ValueError(
                f"Key column '{key}' not found in right table. "
                f"Available: {right.column_names}"
            )

        left_rows = _table_to_row_dicts(left)
        right_rows = _table_to_row_dicts(right)

        left_idx = _build_key_index(left_rows, key)
        right_idx = _build_key_index(right_rows, key)

        left_keys = set(left_idx.keys())
        right_keys = set(right_idx.keys())

        only_left = left_keys - right_keys
        only_right = right_keys - left_keys
        both = left_keys & right_keys

        # Collect non-key columns
        all_columns = list(
            dict.fromkeys(
                [c for c in left.column_names] +
                [c for c in right.column_names if c not in left.column_names]
            )
        )

        # Get timestamps if configured
        ts_col = self._timestamp_col

        merged_rows: List[Dict[str, Any]] = []

        # Rows only in left
        for k in sorted(only_left, key=lambda x: (str(type(x).__name__), x)):
            merged_rows.append(left_rows[left_idx[k]])

        # Matched rows — resolve conflicts per column
        for k in sorted(both, key=lambda x: (str(type(x).__name__), x)):
            row_a = left_rows[left_idx[k]]
            row_b = right_rows[right_idx[k]]

            ts_a = float(row_a.get(ts_col, 0)) if ts_col else 0.0
            ts_b = float(row_b.get(ts_col, 0)) if ts_col else 0.0

            merged_row: Dict[str, Any] = {}
            for col in all_columns:
                va = row_a.get(col)
                vb = row_b.get(col)

                if va is None and vb is not None:
                    merged_row[col] = vb
                elif vb is None and va is not None:
                    merged_row[col] = va
                elif va == vb:
                    merged_row[col] = va
                else:
                    strategy = self._get_strategy(col)
                    merged_row[col] = strategy.resolve(
                        va, vb, ts_a, ts_b, "a", "b"
                    )
            merged_rows.append(merged_row)

        # Rows only in right
        for k in sorted(only_right, key=lambda x: (str(type(x).__name__), x)):
            merged_rows.append(right_rows[right_idx[k]])

        # Handle rows with None keys — keep all of them
        none_rows_left = [
            row for row in left_rows if row.get(key) is None
        ]
        none_rows_right = [
            row for row in right_rows if row.get(key) is None
        ]
        merged_rows.extend(none_rows_left)
        merged_rows.extend(none_rows_right)

        if not merged_rows:
            # Preserve schema for empty result
            return pa.table(
                {col: pa.array([], type=left.schema.field(col).type)
                 for col in all_columns}
            )

        return pa.Table.from_pylist(merged_rows)


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def arrow_merge(
    left: Any,
    right: Any,
    key: Optional[str] = None,
    schema: Optional[Any] = None,
    timestamp_col: Optional[str] = None,
    engine: str = "auto",
) -> Any:
    """One-shot CRDT merge. Falls back to pure-Python if PyArrow is unavailable.

    Accepts ``pa.Table``, ``pa.RecordBatch``, or ``list[dict]``.

    * If PyArrow is available: uses :class:`ArrowMerge` for efficient merging.
    * If PyArrow is missing **and** inputs are ``list[dict]``: falls back to
      :func:`crdt_merge.dataframe.merge`.

    Parameters
    ----------
    left, right :
        Input data — Arrow tables, record batches, or lists of dicts.
    key : str or None
        Column to join on.
    schema : MergeSchema or None
        Per-column merge strategies.
    timestamp_col : str or None
        Timestamp column for LWW resolution.

    engine : str
        Merge engine: ``"auto"`` (Polars if available, else Python),
        ``"polars"`` (Polars or error), ``"python"`` (always pure-Python).

    Returns
    -------
    pa.Table or list[dict]
        Merged result (type depends on whether PyArrow is available).
    """
    if _has_pyarrow():
        eng = ArrowMerge(schema=schema, timestamp_col=timestamp_col, engine=engine)
        return eng.merge(left, right, key=key)
    else:
        # Fallback to pure-Python
        from crdt_merge.dataframe import merge as df_merge
        return df_merge(
            left, right, key=key, schema=schema, timestamp_col=timestamp_col
        )


# ---------------------------------------------------------------------------
# Batch convenience helpers
# ---------------------------------------------------------------------------


def arrow_merge_tables(
    tables: Sequence[Any],
    key: Optional[str] = None,
    schema: Optional[Any] = None,
    timestamp_col: Optional[str] = None,
) -> Any:
    """Merge a sequence of Arrow tables pairwise.

    Parameters
    ----------
    tables :
        Sequence of ``pa.Table`` (at least one).
    key : str or None
        Column to join on.
    schema : MergeSchema or None
        Per-column merge strategies.
    timestamp_col : str or None
        Timestamp column for LWW.

    Returns
    -------
    pa.Table
        The merged result.
    """
    if not tables:
        pa = _import_pyarrow()
        return pa.table({})

    engine = ArrowMerge(schema=schema, timestamp_col=timestamp_col)
    result = _ensure_table(tables[0], _import_pyarrow())
    for t in tables[1:]:
        result = engine.merge(result, t, key=key)
    return result


def table_to_batches(
    table: Any,
    batch_size: int = 10000,
) -> List[Any]:
    """Split a ``pa.Table`` into a list of ``pa.RecordBatch`` objects.

    Parameters
    ----------
    table :
        The input table.
    batch_size :
        Maximum rows per batch.

    Returns
    -------
    list[pa.RecordBatch]
    """
    pa = _import_pyarrow()
    table = _ensure_table(table, pa)
    return table.to_batches(max_chunksize=batch_size)


def write_ipc(table: Any, path: str) -> str:
    """Write a ``pa.Table`` to an Arrow IPC file.

    Parameters
    ----------
    table :
        The table to write.
    path :
        Output file path.

    Returns
    -------
    str
        The output path.
    """
    pa = _import_pyarrow()
    table = _ensure_table(table, pa)
    writer = pa.ipc.new_file(path, table.schema)
    writer.write_table(table)
    writer.close()
    return path


def read_ipc(path: str) -> Any:
    """Read an Arrow IPC file and return a ``pa.Table``.

    Parameters
    ----------
    path :
        Path to the IPC file.

    Returns
    -------
    pa.Table
    """
    pa = _import_pyarrow()
    reader = pa.ipc.open_file(path)
    return reader.read_all()


# ---------------------------------------------------------------------------
# Schema inspection utilities
# ---------------------------------------------------------------------------


def arrow_schema_info(table: Any) -> Dict[str, str]:
    """Return a dict mapping column names to Arrow type strings.

    Parameters
    ----------
    table :
        A ``pa.Table`` or ``pa.RecordBatch``.

    Returns
    -------
    dict[str, str]
    """
    pa = _import_pyarrow()
    table = _ensure_table(table, pa)
    return _schema_dict(table)


def compare_arrow_schemas(
    left: Any,
    right: Any,
) -> Dict[str, Any]:
    """Compare two Arrow tables' schemas and return a diff.

    Parameters
    ----------
    left, right :
        ``pa.Table`` or ``pa.RecordBatch``.

    Returns
    -------
    dict
        Keys: ``"only_left"``, ``"only_right"``, ``"common"``,
        ``"type_mismatches"``, ``"compatible"``
    """
    pa = _import_pyarrow()
    left = _ensure_table(left, pa)
    right = _ensure_table(right, pa)

    left_sd = _schema_dict(left)
    right_sd = _schema_dict(right)

    left_cols = set(left_sd)
    right_cols = set(right_sd)

    only_left = sorted(left_cols - right_cols)
    only_right = sorted(right_cols - left_cols)
    common = sorted(left_cols & right_cols)

    mismatches = {}
    for col in common:
        if left_sd[col] != right_sd[col]:
            mismatches[col] = {"left": left_sd[col], "right": right_sd[col]}

    return {
        "only_left": only_left,
        "only_right": only_right,
        "common": common,
        "type_mismatches": mismatches,
        "compatible": len(mismatches) == 0 and not only_left and not only_right,
    }


# ---------------------------------------------------------------------------
# Performance benchmarking helper
# ---------------------------------------------------------------------------


def benchmark_arrow_merge(
    num_rows: int = 10000,
    num_cols: int = 10,
    key: str = "id",
    overlap: float = 0.5,
) -> Dict[str, Any]:
    """Generate synthetic data and benchmark Arrow merge vs dict merge.

    Parameters
    ----------
    num_rows :
        Number of rows per table.
    num_cols :
        Number of value columns.
    key :
        Name of the key column.
    overlap :
        Fraction of rows that appear in both tables (0.0–1.0).

    Returns
    -------
    dict
        ``{"arrow_time_ms", "dict_time_ms", "speedup", "rows"}``.
    """
    import time as _time

    pa = _import_pyarrow()

    # Generate data
    overlap_count = int(num_rows * overlap)
    only_count = num_rows - overlap_count

    data_left: Dict[str, list] = {key: []}
    data_right: Dict[str, list] = {key: []}
    for c in range(num_cols):
        col_name = f"col_{c}"
        data_left[col_name] = []
        data_right[col_name] = []

    # Overlapping rows
    for i in range(overlap_count):
        data_left[key].append(i)
        data_right[key].append(i)
        for c in range(num_cols):
            col_name = f"col_{c}"
            data_left[col_name].append(f"left_{i}_{c}")
            data_right[col_name].append(f"right_{i}_{c}")

    # Left-only rows
    for i in range(only_count):
        idx = overlap_count + i
        data_left[key].append(idx)
        for c in range(num_cols):
            col_name = f"col_{c}"
            data_left[col_name].append(f"left_{idx}_{c}")

    # Right-only rows
    for i in range(only_count):
        idx = overlap_count + only_count + i
        data_right[key].append(idx)
        for c in range(num_cols):
            col_name = f"col_{c}"
            data_right[col_name].append(f"right_{idx}_{c}")

    left_table = pa.table(data_left)
    right_table = pa.table(data_right)

    # Arrow merge
    engine = ArrowMerge()
    t0 = _time.perf_counter()
    arrow_result = engine.merge(left_table, right_table, key=key)
    arrow_ms = (_time.perf_counter() - t0) * 1000

    # Dict merge
    from crdt_merge.dataframe import merge as df_merge
    left_dicts = left_table.to_pylist()
    right_dicts = right_table.to_pylist()
    t0 = _time.perf_counter()
    dict_result = df_merge(left_dicts, right_dicts, key=key)
    dict_ms = (_time.perf_counter() - t0) * 1000

    return {
        "arrow_time_ms": round(arrow_ms, 2),
        "dict_time_ms": round(dict_ms, 2),
        "speedup": round(dict_ms / arrow_ms, 2) if arrow_ms > 0 else float("inf"),
        "rows": len(arrow_result),
    }


# ---------------------------------------------------------------------------
# Optional fast engine
# ---------------------------------------------------------------------------

try:
    from crdt_merge._polars_engine import (
        HAS_POLARS,
        polars_merge_arrow,
    )
except ImportError:
    HAS_POLARS = False
    polars_merge_arrow = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Module-level __all__
# ---------------------------------------------------------------------------

__all__ = [
    "ArrowMerge",
    "arrow_merge",
    "arrow_merge_tables",
    "arrow_schema_info",
    "benchmark_arrow_merge",
    "compare_arrow_schemas",
    "read_ipc",
    "table_to_batches",
    "write_ipc",
    "_has_pyarrow",
    "_import_pyarrow",
]
