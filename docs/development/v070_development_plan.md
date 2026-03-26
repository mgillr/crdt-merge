# crdt-merge v0.7.0 — Synchronized Development Plan
# "The Integration Release"

**Copyright 2026 Ryan Gillespie / Optitransfer**
**Contact:** rgillespie83@icloud.com · data@optitransfer.ch
**License:** BSL-1.1

---

## 1. Mission Statement

v0.7.0 — "The Integration Release" — transforms crdt-merge from a standalone merge toolkit into an
integrated component of the modern data stack. This release delivers:

1. **MergeQL** — SQL interface for CRDT merge operations, reaching every data warehouse user
2. **Self-Merging Parquet** — Files with embedded merge semantics and provenance
3. **Conflict Topology Visualization** — Interactive conflict analysis with D3-compatible export
4. **8 Strategic Accelerators** — Ecosystem integrations that plug crdt-merge into the dominant
   tools of the modern data stack:
   - ACC-1: DuckDB UDF / MergeQL Extension (SQL-native CRDT merge inside DuckDB)
   - ACC-2: dbt Package (conflict-aware transforms for 40K+ companies)
   - ACC-3: DuckLake Semantic Conflict Layer (field-level resolution for DuckLake snapshots)
   - ACC-4: Polars Expression Plugin (native DataFrame CRDT merge)
   - ACC-5: Arrow Flight Merge-as-a-Service (enterprise gRPC merge server)
   - ACC-6: Airbyte Destination Connector (CRDT-aware data ingestion)
   - ACC-7: SQLite Extension (local-first / edge CRDT merge)
   - ACC-8: Streamlit Visual Merge UI (interactive conflict resolution component)

This release bridges the gap between toolkit and product, making CRDT merge accessible through
familiar interfaces (SQL, DuckDB, dbt, Polars, Arrow Flight, Airbyte, SQLite, Streamlit) while
preserving zero-dependency core. All accelerators use lazy imports — no mandatory new dependencies.

### Release Targets

| Metric | v0.6.0 Baseline | v0.7.0 Target |
|--------|----------------|---------------|
| Source modules | 20 | ~33 (+13: 3 core + 8 accelerators + accelerators/__init__.py + __init__.py update) |
| Source lines | 7,301 | ~13,000 (+~5,700) |
| Test files | 24 | ~38 (+14: 3 core + 8 accelerator + 2 integration + 1 cross-accelerator) |
| Tests passing | 704 | ~1,200 (+~496) |
| PyPI version | 0.6.0 | 0.7.0 |

---

## 2. Baseline Lock — v0.6.0 Frozen State

### 2.1 Immutability Rule

**ALL 20 source modules and 24 test files from v0.6.0 are FROZEN.**
Any modification to these files without explicit project lead approval = **BLOCKING DEFECT**.

New modules: **write to own files ONLY, import from existing modules (read-only access)**.

### 2.2 Source Module Registry (20 files)

| SHA-256 (first 12) | Lines | File | Owner |
|----|------|------|-------|
| `90bb0015ff9b` | 112 | `crdt_merge/__init__.py` | Dev A (Phase 4 update only) |
| `efc138384672` | 308 | `crdt_merge/core.py` | Dev A |
| `160f8ff8089d` | 334 | `crdt_merge/strategies.py` | Dev A |
| `a786b372c791` | 351 | `crdt_merge/dataframe.py` | Dev B |
| `4fecfabc18ea` | 94 | `crdt_merge/datasets_ext.py` | Dev B |
| `f62760d50eeb` | 128 | `crdt_merge/json_merge.py` | Dev B |
| `733ede5bbd5e` | 353 | `crdt_merge/streaming.py` | Dev C |
| `7e59985197f2` | 353 | `crdt_merge/delta.py` | Dev C |
| `7e31b97d2693` | 505 | `crdt_merge/probabilistic.py` | Dev D |
| `448bf4d70f64` | 619 | `crdt_merge/wire.py` | Dev D |
| `3f08d6847ffb` | 408 | `crdt_merge/verify.py` | Dev E |
| `906648b27e1e` | 363 | `crdt_merge/provenance.py` | Dev E |
| `04b127abcf3c` | 235 | `crdt_merge/dedup.py` | Dev E |
| `882ef0ea14e7` | 314 | `crdt_merge/clocks.py` | Dev A (v0.6.0) |
| `1d0b99ef5d65` | 415 | `crdt_merge/schema_evolution.py` | Dev B (v0.6.0) |
| `0beb79f0a4d9` | 546 | `crdt_merge/merkle.py` | Dev C (v0.6.0) |
| `199f6e06f7c2` | 935 | `crdt_merge/arrow.py` | Dev B (v0.6.0) |
| `f67ccd1a059f` | 538 | `crdt_merge/gossip.py` | Dev A (v0.6.0) |
| `850b4c758a39` | 178 | `crdt_merge/async_merge.py` | Dev D (v0.6.0) |
| `51c6899a41ed` | 212 | `crdt_merge/parallel.py` | Dev D (v0.6.0) |

**Total: 20 modules, 7,301 lines**

### 2.3 Test File Registry (24 files + __init__)

| SHA-256 (first 12) | Lines | File |
|----|------|------|
| `e3b0c44298fc` | 0 | `tests/__init__.py` |
| `43af3c93ff34` | 229 | `tests/test_core.py` |
| `c74987ec08a1` | 276 | `tests/test_strategies.py` |
| `6c1367fb814d` | 99 | `tests/test_dataframe.py` |
| `6742ff96d1b2` | 65 | `tests/test_json_merge.py` |
| `38b567a8d4f9` | 76 | `tests/test_longest_wins.py` |
| `3e0523ba9197` | 238 | `tests/test_streaming.py` |
| `c1f1770031b9` | 355 | `tests/test_probabilistic.py` |
| `096e48082b09` | 328 | `tests/test_wire.py` |
| `abacb5180b77` | 106 | `tests/test_verified_merge.py` |
| `6ae47a1e58a8` | 273 | `tests/test_provenance.py` |
| `3725363be23f` | 116 | `tests/test_dedup.py` |
| `4783dafa76d1` | 380 | `tests/test_stress_v030.py` |
| `b24c1ff3e4f2` | 69 | `tests/test_benchmark.py` |
| `8bd34604d195` | 1095 | `tests/test_architect_360_validation.py` |
| `55e86debd107` | 1335 | `tests/test_v050_integration.py` |
| `c467f358a4ae` | 351 | `tests/test_clocks.py` |
| `e26517cb543b` | 265 | `tests/test_schema_evolution.py` |
| `1eb677f746fa` | 366 | `tests/test_merkle.py` |
| `8a8d2094b1af` | 816 | `tests/test_arrow.py` |
| `4845413e4394` | 496 | `tests/test_gossip.py` |
| `81b030e4600a` | 210 | `tests/test_multi_key.py` |
| `7bec20f72bd7` | 278 | `tests/test_async_merge.py` |
| `cf3fee3230b9` | 278 | `tests/test_parallel.py` |
| `dee9c25e246a` | 874 | `tests/test_v060_integration.py` |

**Total: 25 files (incl. __init__), 8,543 lines, 704 tests passing (2 skipped, 1 xfail)**

### 2.4 Regression Gate

Before ANY v0.7.0 merge:
```bash
cd tests && python -m pytest test_core.py test_strategies.py test_dataframe.py \
  test_json_merge.py test_longest_wins.py test_streaming.py test_probabilistic.py \
  test_wire.py test_verified_merge.py test_provenance.py test_dedup.py \
  test_clocks.py test_schema_evolution.py test_merkle.py test_arrow.py \
  test_gossip.py test_multi_key.py test_async_merge.py test_parallel.py \
  test_v060_integration.py -v
# Expected: 704 passed, 2 skipped, 1 xfail — ZERO failures
```

---

## 3. Module Specifications

### 3.1 MergeQL — `crdt_merge/mergeql.py` (~500 lines)

**Developer:** Dev A (core.py, strategies.py owner)
**Phase:** 1 — Foundation
**Dependencies:** `core.py` (read-only), `strategies.py` (read-only), `schema_evolution.py` (read-only)

#### Purpose

MergeQL provides a SQL-like interface for CRDT merge operations. Instead of writing Python code,
users express merges as SQL statements:

```python
from crdt_merge.mergeql import MergeQL

ql = MergeQL()
ql.register("users_nyc", nyc_data)
ql.register("users_london", london_data)

result = ql.execute("""
    MERGE users_nyc, users_london
    ON id
    STRATEGY name='lww', salary='max', status='custom:priority_resolver'
""")
```

#### Class Signatures

```python
# Copyright 2026 Ryan Gillespie
# Licensed under BSL-1.1

from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from crdt_merge.core import MergeSchema
from crdt_merge.strategies import STRATEGY_REGISTRY

# --- AST Nodes ---

@dataclass
class MergeAST:
    """Abstract syntax tree for a MergeQL statement."""
    sources: List[str]                    # Table names to merge
    on_key: str                           # Join key column
    strategies: Dict[str, str] = field(default_factory=dict)  # field -> strategy
    where_clause: Optional[str] = None    # Optional filter
    explain: bool = False                 # If True, return plan only
    schema_mapping: Optional[Dict[str, str]] = None  # Column rename map
    limit: Optional[int] = None           # Result limit

@dataclass
class MergePlan:
    """Execution plan for a MergeQL query."""
    sources: List[str]                    # Source names
    source_sizes: Dict[str, int]          # Rows per source
    merge_key: str                        # Join key
    strategies: Dict[str, str]            # Applied strategies
    estimated_output_rows: int            # Estimated result size
    schema_evolution_needed: bool         # If column mapping required
    arrow_backend: bool                   # If Arrow engine available
    steps: List[str]                      # Human-readable execution steps

    def __str__(self) -> str:
        """Human-readable plan summary."""
        ...

@dataclass
class MergeQLResult:
    """Result of a MergeQL execution."""
    data: List[dict]                      # Merged records
    plan: MergePlan                       # Execution plan used
    conflicts: int                        # Number of conflicts resolved
    provenance: Optional[List[dict]] = None  # Per-record provenance
    merge_time_ms: float = 0.0            # Execution time
    sources_merged: int = 0               # Count of sources merged

# --- Parser ---

class MergeQLParser:
    """Parse MergeQL SQL-like syntax into AST nodes.

    Supported syntax:
        MERGE source1, source2 [, sourceN...]
        ON key_column
        [STRATEGY field1='strategy1', field2='strategy2']
        [WHERE condition]
        [LIMIT n]
        [MAP old_col -> new_col]

        EXPLAIN MERGE ...  (returns MergePlan without executing)
    """

    KEYWORDS = {'MERGE', 'ON', 'STRATEGY', 'WHERE', 'LIMIT', 'MAP', 'EXPLAIN'}

    def parse(self, query: str) -> MergeAST:
        """Parse a MergeQL query string into an AST.

        Args:
            query: SQL-like merge statement

        Returns:
            MergeAST node

        Raises:
            MergeQLSyntaxError: If query is malformed
            MergeQLValidationError: If query references unknown sources
        """
        ...

    def _tokenize(self, query: str) -> List[str]:
        """Split query into tokens."""
        ...

    def _parse_sources(self, tokens: List[str], pos: int) -> Tuple[List[str], int]:
        """Parse MERGE source1, source2, ..."""
        ...

    def _parse_strategies(self, tokens: List[str], pos: int) -> Tuple[Dict[str, str], int]:
        """Parse STRATEGY field='strategy', ..."""
        ...

    def _parse_where(self, tokens: List[str], pos: int) -> Tuple[Optional[str], int]:
        """Parse WHERE clause."""
        ...

    def _parse_mapping(self, tokens: List[str], pos: int) -> Tuple[Optional[Dict[str, str]], int]:
        """Parse MAP old_col -> new_col, ..."""
        ...

# --- Exceptions ---

class MergeQLError(Exception):
    """Base exception for MergeQL errors."""
    pass

class MergeQLSyntaxError(MergeQLError):
    """Raised when MergeQL query has syntax errors."""
    pass

class MergeQLValidationError(MergeQLError):
    """Raised when MergeQL query references invalid sources or strategies."""
    pass

# --- Engine ---

class MergeQL:
    """SQL-like interface for CRDT merge operations.

    MergeQL makes CRDT merge accessible to SQL users. Register data sources,
    then execute merge operations using familiar SQL syntax.

    Example:
        ql = MergeQL()
        ql.register("east", east_data)
        ql.register("west", west_data)
        result = ql.execute("MERGE east, west ON id STRATEGY name='lww'")
    """

    def __init__(self, *, arrow_backend: bool = False, provenance: bool = True):
        """Initialize MergeQL engine.

        Args:
            arrow_backend: Use Arrow engine for large datasets (requires arrow.py)
            provenance: Automatically track merge provenance
        """
        self._sources: Dict[str, Any] = {}
        self._parser = MergeQLParser()
        self._arrow_backend = arrow_backend
        self._provenance = provenance
        self._custom_strategies: Dict[str, Callable] = {}

    def register(self, name: str, data: Any) -> None:
        """Register a data source for merge operations.

        Args:
            name: Source identifier (used in MERGE statements)
            data: List of dicts, DataFrame, or Arrow table

        Raises:
            ValueError: If name is empty or data is invalid
        """
        ...

    def unregister(self, name: str) -> None:
        """Remove a registered data source."""
        ...

    def register_strategy(self, name: str, func: Callable) -> None:
        """Register a custom merge strategy for use in STRATEGY clauses.

        Args:
            name: Strategy name (used as STRATEGY field='name')
            func: Strategy function (a, b) -> resolved_value
        """
        ...

    def execute(self, query: str) -> MergeQLResult:
        """Execute a MergeQL query.

        Args:
            query: SQL-like merge statement

        Returns:
            MergeQLResult with merged data, plan, and provenance

        Raises:
            MergeQLSyntaxError: If query syntax is invalid
            MergeQLValidationError: If sources or strategies not found
        """
        ...

    def explain(self, query: str) -> MergePlan:
        """Show execution plan without running the merge.

        Args:
            query: SQL-like merge statement

        Returns:
            MergePlan with estimated costs and steps
        """
        ...

    def list_sources(self) -> List[str]:
        """List all registered source names."""
        ...

    def source_info(self, name: str) -> Dict[str, Any]:
        """Get info about a registered source (row count, columns, etc)."""
        ...

    def _build_schema(self, ast: MergeAST) -> MergeSchema:
        """Convert AST strategies into a MergeSchema."""
        ...

    def _execute_merge(self, ast: MergeAST) -> MergeQLResult:
        """Internal merge execution engine."""
        ...

    def _execute_arrow_merge(self, ast: MergeAST) -> MergeQLResult:
        """Arrow-backed merge for large datasets."""
        ...
```

#### Test Specification: `tests/test_mergeql.py` (~60 tests)

```python
class TestMergeQLParser:
    # 15 tests
    def test_parse_basic_merge(self): ...
    def test_parse_multi_source(self): ...
    def test_parse_with_strategy(self): ...
    def test_parse_multi_strategy(self): ...
    def test_parse_with_where(self): ...
    def test_parse_with_limit(self): ...
    def test_parse_with_map(self): ...
    def test_parse_explain(self): ...
    def test_parse_case_insensitive(self): ...
    def test_parse_extra_whitespace(self): ...
    def test_parse_error_no_sources(self): ...
    def test_parse_error_no_on(self): ...
    def test_parse_error_invalid_strategy(self): ...
    def test_parse_error_empty_query(self): ...
    def test_parse_complex_combined(self): ...

class TestMergeQLExecution:
    # 15 tests
    def test_basic_two_source_merge(self): ...
    def test_three_source_merge(self): ...
    def test_merge_with_conflicts(self): ...
    def test_merge_lww_strategy(self): ...
    def test_merge_max_strategy(self): ...
    def test_merge_min_strategy(self): ...
    def test_merge_with_where_filter(self): ...
    def test_merge_with_limit(self): ...
    def test_merge_with_column_mapping(self): ...
    def test_merge_empty_sources(self): ...
    def test_merge_disjoint_keys(self): ...
    def test_merge_overlapping_partial(self): ...
    def test_register_unregister(self): ...
    def test_list_sources(self): ...
    def test_source_info(self): ...

class TestMergeQLStrategies:
    # 10 tests
    def test_default_strategy_lww(self): ...
    def test_per_field_strategies(self): ...
    def test_mixed_strategies(self): ...
    def test_custom_strategy_registration(self): ...
    def test_custom_strategy_in_query(self): ...
    def test_unknown_strategy_error(self): ...
    def test_strategy_from_schema(self): ...
    def test_strategy_numeric_fields(self): ...
    def test_strategy_string_fields(self): ...
    def test_strategy_boolean_fields(self): ...

class TestMergeQLExplain:
    # 5 tests
    def test_explain_basic(self): ...
    def test_explain_multi_source(self): ...
    def test_explain_arrow_backend(self): ...
    def test_explain_schema_evolution(self): ...
    def test_explain_output_format(self): ...

class TestMergeQLProvenance:
    # 5 tests
    def test_provenance_enabled(self): ...
    def test_provenance_disabled(self): ...
    def test_provenance_multi_source(self): ...
    def test_provenance_conflict_tracking(self): ...
    def test_provenance_source_attribution(self): ...

class TestMergeQLIntegration:
    # 10 tests
    def test_mergeql_with_schema_evolution(self): ...
    def test_mergeql_with_arrow_backend(self): ...
    def test_mergeql_with_merge_function(self): ...
    def test_mergeql_with_dataframe_merge(self): ...
    def test_mergeql_with_streaming_data(self): ...
    def test_mergeql_chained_queries(self): ...
    def test_mergeql_large_dataset(self): ...
    def test_mergeql_idempotent_merge(self): ...
    def test_mergeql_commutative_merge(self): ...
    def test_mergeql_associative_merge(self): ...
```

---

### 3.2 Self-Merging Parquet — `crdt_merge/parquet.py` (~400 lines)

**Developer:** Dev B (dataframe.py, schema_evolution.py owner)
**Phase:** 1 — Foundation
**Dependencies:** `core.py` (read-only), `strategies.py` (read-only), `provenance.py` (read-only)

#### Purpose

Self-Merging Parquet embeds CRDT merge semantics directly in Parquet file metadata.
When two Parquet files meet, they know how to merge themselves — no external configuration needed.

```python
from crdt_merge.parquet import SelfMergingParquet

# Create a self-merging file
smf = SelfMergingParquet("users.parquet", schema=MergeSchema(
    key="id", strategies={"name": "lww", "salary": "max"}
))
smf.ingest(batch_1)
smf.ingest(batch_2)  # Auto-merges with existing data

# Read merged result
merged = smf.read()
meta = smf.metadata()  # Shows embedded merge config
```

#### Class Signatures

```python
# Copyright 2026 Ryan Gillespie
# Licensed under BSL-1.1

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import json
import struct
from crdt_merge.core import MergeSchema, merge
from crdt_merge.provenance import ProvenanceLog

# --- Metadata ---

@dataclass
class ParquetMergeMetadata:
    """Merge schema stored in Parquet key-value metadata.

    Embeds merge semantics (key, strategies, provenance config)
    in the Parquet file's metadata section so files are self-describing.
    """
    key_column: str
    strategies: Dict[str, str]
    provenance_enabled: bool = True
    schema_version: str = "1.0"
    created_at: Optional[str] = None
    source_count: int = 0
    merge_count: int = 0

    def to_parquet_metadata(self) -> Dict[str, str]:
        """Serialize to Parquet key-value metadata format.

        Returns:
            Dict suitable for Parquet file metadata
        """
        ...

    @classmethod
    def from_parquet_metadata(cls, meta: Dict[str, str]) -> ParquetMergeMetadata:
        """Deserialize from Parquet key-value metadata.

        Args:
            meta: Dict from Parquet file metadata

        Returns:
            ParquetMergeMetadata instance

        Raises:
            ValueError: If metadata is missing required fields
        """
        ...

@dataclass
class IngestResult:
    """Result of ingesting data into a self-merging Parquet file."""
    records_ingested: int
    conflicts_resolved: int
    new_records: int
    updated_records: int
    merge_time_ms: float = 0.0
    provenance_entries: int = 0

@dataclass
class CompactResult:
    """Result of compacting a self-merging Parquet file."""
    records_before: int
    records_after: int
    duplicates_removed: int
    compact_time_ms: float = 0.0

# --- Engine ---

class SelfMergingParquet:
    """Parquet files with embedded CRDT merge semantics.

    Data is stored in-memory using list-of-dicts format.
    Merge schema and provenance are tracked as metadata.
    Export to actual Parquet files requires PyArrow (optional dependency).

    Example:
        smf = SelfMergingParquet("users", schema=MergeSchema(
            key="id", strategies={"name": "lww", "salary": "max"}
        ))
        smf.ingest([{"id": 1, "name": "Alice", "salary": 100}])
        smf.ingest([{"id": 1, "name": "Alicia", "salary": 120}])
        assert smf.read() == [{"id": 1, "name": "Alicia", "salary": 120}]
    """

    def __init__(self, name: str, schema: Optional[MergeSchema] = None,
                 provenance: bool = True):
        """Initialize a self-merging Parquet container.

        Args:
            name: Logical name for this container
            schema: MergeSchema defining merge key and strategies
            provenance: Enable provenance tracking
        """
        ...

    def ingest(self, data: Any, source: Optional[str] = None) -> IngestResult:
        """Merge new data into the container.

        Args:
            data: List of dicts, or any iterable of records
            source: Optional source label for provenance

        Returns:
            IngestResult with merge statistics
        """
        ...

    def compact(self) -> CompactResult:
        """Compact the container, removing duplicates and dead entries.

        Returns:
            CompactResult with compaction statistics
        """
        ...

    def read(self) -> List[dict]:
        """Read all merged records.

        Returns:
            List of merged records
        """
        ...

    def metadata(self) -> ParquetMergeMetadata:
        """Get the embedded merge metadata.

        Returns:
            ParquetMergeMetadata with current state
        """
        ...

    def to_parquet(self, path: str) -> None:
        """Export to actual Parquet file with embedded metadata.

        Requires PyArrow. Raises ImportError if not available.

        Args:
            path: Output file path
        """
        ...

    @classmethod
    def from_parquet(cls, path: str) -> SelfMergingParquet:
        """Load from a Parquet file with embedded merge metadata.

        Requires PyArrow. Raises ImportError if not available.

        Args:
            path: Input file path

        Returns:
            SelfMergingParquet instance with data and metadata loaded
        """
        ...

    def merge_with(self, other: SelfMergingParquet) -> IngestResult:
        """Merge another SelfMergingParquet into this one.

        Args:
            other: Another SelfMergingParquet container

        Returns:
            IngestResult with merge statistics
        """
        ...

    def __len__(self) -> int:
        """Number of records in the container."""
        ...

    def __repr__(self) -> str: ...
```

#### Test Specification: `tests/test_parquet.py` (~40 tests)

```python
class TestParquetMetadata:
    # 10 tests
    def test_metadata_to_dict(self): ...
    def test_metadata_from_dict(self): ...
    def test_metadata_roundtrip(self): ...
    def test_metadata_missing_key(self): ...
    def test_metadata_empty_strategies(self): ...
    def test_metadata_version(self): ...
    def test_metadata_source_count(self): ...
    def test_metadata_merge_count(self): ...
    def test_metadata_created_at(self): ...
    def test_metadata_provenance_flag(self): ...

class TestSelfMergingParquet:
    # 15 tests
    def test_create_empty(self): ...
    def test_ingest_single_batch(self): ...
    def test_ingest_multiple_batches(self): ...
    def test_ingest_with_conflicts(self): ...
    def test_ingest_disjoint_keys(self): ...
    def test_read_empty(self): ...
    def test_read_after_ingest(self): ...
    def test_compact_removes_duplicates(self): ...
    def test_compact_preserves_data(self): ...
    def test_merge_with_another(self): ...
    def test_len(self): ...
    def test_repr(self): ...
    def test_ingest_result_stats(self): ...
    def test_compact_result_stats(self): ...
    def test_source_label_tracking(self): ...

class TestParquetStrategies:
    # 10 tests
    def test_lww_strategy(self): ...
    def test_max_strategy(self): ...
    def test_min_strategy(self): ...
    def test_sum_strategy(self): ...
    def test_mixed_strategies(self): ...
    def test_default_strategy(self): ...
    def test_custom_schema(self): ...
    def test_no_schema_fallback(self): ...
    def test_strategy_preserved_in_metadata(self): ...
    def test_strategy_roundtrip(self): ...

class TestParquetProvenance:
    # 5 tests
    def test_provenance_enabled(self): ...
    def test_provenance_disabled(self): ...
    def test_provenance_multi_ingest(self): ...
    def test_provenance_source_labels(self): ...
    def test_provenance_in_metadata(self): ...
```

---

### 3.3 Conflict Topology Visualization — `crdt_merge/viz.py` (~250 lines)

**Developer:** Dev C (streaming.py, delta.py owner)
**Phase:** 2 — Integration
**Dependencies:** `core.py` (read-only), `provenance.py` (read-only), `dataframe.py` (read-only)

#### Purpose

Provides conflict analysis and visualization for merge operations. Generates heatmaps,
temporal patterns, and cluster analysis — exportable as D3-compatible JSON or CSV.

```python
from crdt_merge.viz import ConflictTopology

# From merge result
topo = ConflictTopology.from_merge(merge_result, provenance_log)
print(topo.summary())           # Human-readable summary
heatmap = topo.heatmap()        # Field × source conflict matrix
json_data = topo.to_json()      # D3-compatible visualization data
topo.to_csv("conflicts.csv")    # CSV export
```

#### Class Signatures

```python
# Copyright 2026 Ryan Gillespie
# Licensed under BSL-1.1

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import json
import csv
from collections import Counter, defaultdict

@dataclass
class ConflictRecord:
    """A single conflict event."""
    key: Any                              # Record key where conflict occurred
    field: str                            # Field name
    sources: List[str]                    # Contributing sources
    values: List[Any]                     # Conflicting values
    resolved_value: Any                   # Value after resolution
    strategy: str = "lww"                 # Strategy used
    timestamp: Optional[str] = None       # When conflict occurred

@dataclass
class ConflictCluster:
    """Group of related conflicts sharing a pattern."""
    fields: List[str]                     # Fields involved
    source_pairs: List[Tuple[str, str]]   # Source pairs in conflict
    count: int                            # Number of conflicts
    pattern: str                          # Description of pattern

class ConflictTopology:
    """Analyze and visualize merge conflict patterns.

    Provides multi-dimensional conflict analysis:
    - Heatmaps: Which fields conflict most between which sources
    - Temporal: How conflicts evolve over time
    - Clusters: Related conflict groups
    - Summary: Human-readable overview

    All outputs are D3-compatible JSON or CSV for visualization.
    """

    def __init__(self, conflicts: Optional[List[ConflictRecord]] = None):
        """Initialize with a list of conflict records.

        Args:
            conflicts: List of ConflictRecord objects
        """
        ...

    @classmethod
    def from_merge(cls, result: Any, provenance: Optional[Any] = None) -> ConflictTopology:
        """Create from a merge result and optional provenance log.

        Extracts conflict information from merge output and provenance data.

        Args:
            result: Merge result (list of dicts with _provenance, or MergeQLResult)
            provenance: Optional ProvenanceLog for detailed analysis

        Returns:
            ConflictTopology instance
        """
        ...

    @classmethod
    def from_records(cls, conflicts: List[Dict[str, Any]]) -> ConflictTopology:
        """Create from raw conflict dicts.

        Args:
            conflicts: List of dicts with keys: key, field, sources, values, resolved_value

        Returns:
            ConflictTopology instance
        """
        ...

    def add_conflict(self, conflict: ConflictRecord) -> None:
        """Add a conflict record."""
        ...

    def heatmap(self) -> Dict[str, Dict[str, int]]:
        """Generate field × source conflict frequency matrix.

        Returns:
            Nested dict: {field: {source_pair: count}}
        """
        ...

    def temporal_pattern(self) -> List[Dict[str, Any]]:
        """Analyze conflict patterns over time.

        Returns:
            List of time-bucketed conflict counts
        """
        ...

    def clusters(self) -> List[ConflictCluster]:
        """Identify clusters of related conflicts.

        Returns:
            List of ConflictCluster groups
        """
        ...

    def field_frequency(self) -> Dict[str, int]:
        """Count conflicts per field.

        Returns:
            Dict mapping field names to conflict counts
        """
        ...

    def source_frequency(self) -> Dict[str, int]:
        """Count conflicts per source.

        Returns:
            Dict mapping source names to conflict counts
        """
        ...

    def strategy_stats(self) -> Dict[str, int]:
        """Count which strategies resolved conflicts.

        Returns:
            Dict mapping strategy names to usage counts
        """
        ...

    def summary(self) -> str:
        """Generate human-readable conflict summary.

        Returns:
            Multi-line string with conflict statistics
        """
        ...

    def to_json(self) -> str:
        """Export as D3-compatible JSON.

        Returns:
            JSON string with nodes (fields/sources) and links (conflicts)
        """
        ...

    def to_csv(self, path: str) -> None:
        """Export conflict records to CSV.

        Args:
            path: Output CSV file path
        """
        ...

    def to_dict(self) -> Dict[str, Any]:
        """Export complete topology as dict.

        Returns:
            Dict with heatmap, clusters, summary, stats
        """
        ...

    def __len__(self) -> int:
        """Number of conflict records."""
        ...

    def __repr__(self) -> str: ...
```

#### Test Specification: `tests/test_viz.py` (~35 tests)

```python
class TestConflictTopology:
    # 15 tests
    def test_create_empty(self): ...
    def test_create_from_records(self): ...
    def test_from_merge_result(self): ...
    def test_add_conflict(self): ...
    def test_heatmap_basic(self): ...
    def test_heatmap_multi_field(self): ...
    def test_heatmap_multi_source(self): ...
    def test_field_frequency(self): ...
    def test_source_frequency(self): ...
    def test_strategy_stats(self): ...
    def test_summary_format(self): ...
    def test_summary_no_conflicts(self): ...
    def test_len(self): ...
    def test_repr(self): ...
    def test_to_dict(self): ...

class TestTemporalPatterns:
    # 5 tests
    def test_temporal_empty(self): ...
    def test_temporal_single_time(self): ...
    def test_temporal_multiple_times(self): ...
    def test_temporal_no_timestamps(self): ...
    def test_temporal_ordering(self): ...

class TestClusterAnalysis:
    # 5 tests
    def test_clusters_empty(self): ...
    def test_clusters_single_field(self): ...
    def test_clusters_multi_field(self): ...
    def test_clusters_source_pairs(self): ...
    def test_clusters_pattern_description(self): ...

class TestExport:
    # 10 tests
    def test_to_json_format(self): ...
    def test_to_json_d3_compatible(self): ...
    def test_to_json_nodes_and_links(self): ...
    def test_to_json_empty(self): ...
    def test_to_csv_basic(self): ...
    def test_to_csv_headers(self): ...
    def test_to_csv_empty(self): ...
    def test_to_csv_special_chars(self): ...
    def test_roundtrip_json(self): ...
    def test_roundtrip_csv(self): ...
```

---

### 3.4 Strategic Accelerators — `crdt_merge/accelerators/` (Phases 1–4)

#### Architecture

Accelerators live in a `crdt_merge/accelerators/` subdirectory with lazy imports.
Each accelerator MUST:
1. Handle `ImportError` gracefully (print helpful install message)
2. Work WITHOUT the external dependency for basic type checking
3. Include copyright header: `# Copyright 2026 Ryan Gillespie`
4. Follow the `CRDTMergeAccelerator` base protocol

```
crdt_merge/accelerators/
├── __init__.py          # Base protocol + registry
├── duckdb_udf.py       # ACC-1: DuckDB UDF / MergeQL extension
├── dbt_package.py      # ACC-2: dbt macro generator
├── ducklake.py          # ACC-3: DuckLake semantic conflict layer
├── polars_plugin.py     # ACC-4: Polars expression plugin
├── flight_server.py     # ACC-5: Arrow Flight merge service
├── airbyte.py           # ACC-6: Airbyte destination connector
├── sqlite_ext.py        # ACC-7: SQLite CRDT extension
└── streamlit_ui.py      # ACC-8: Streamlit visual merge component
```

```python
# crdt_merge/accelerators/__init__.py
# Copyright 2026 Ryan Gillespie
# Licensed under BSL-1.1

from __future__ import annotations
from typing import Protocol, Any, Dict, List, Optional, runtime_checkable

@runtime_checkable
class CRDTMergeAccelerator(Protocol):
    """Base protocol for all crdt-merge accelerators."""
    name: str
    version: str

    def connect(self, **kwargs: Any) -> None: ...
    def merge_from(self, source: Any) -> Any: ...
    def merge_to(self, target: Any, data: Any) -> None: ...
    def health_check(self) -> Dict[str, Any]: ...

ACCELERATOR_REGISTRY: Dict[str, type] = {}

def register_accelerator(name: str, cls: type) -> None:
    """Register an accelerator class for discovery."""
    ACCELERATOR_REGISTRY[name] = cls

def get_accelerator(name: str) -> type:
    """Get a registered accelerator class by name."""
    ...
```

#### 3.4.1 ACC-1: DuckDB UDF / MergeQL Extension — `crdt_merge/accelerators/duckdb_udf.py` (~500 lines)

**Developer:** Dev A (core.py, strategies.py, mergeql.py owner)
**Phase:** 2 — Technical Foundation
**External Dep:** `duckdb` (lazy import)

SQL-native CRDT merge inside DuckDB. Extends MergeQL with DuckDB UDF registration so users can
run `SELECT * FROM crdt_merge(t1, t2, key:='id', strategy:='lww')` directly in DuckDB.

```python
# Copyright 2026 Ryan Gillespie
# Licensed under BSL-1.1

from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional
from crdt_merge.core import MergeSchema

class DuckDBMergeUDF:
    """DuckDB UDF that wraps crdt-merge operations.

    Registers CRDT merge as a DuckDB scalar/table function, enabling
    SQL-native conflict resolution inside DuckDB queries.

    Example:
        udf = DuckDBMergeUDF(conn)
        udf.register()
        result = conn.sql("SELECT * FROM crdt_merge('t1', 't2', key:='id', strategy:='lww')")
    """
    def __init__(self, connection: Any = None, schema: Optional[MergeSchema] = None): ...
    def register(self) -> None:
        """Register crdt_merge as a DuckDB UDF."""
        ...
    def unregister(self) -> None:
        """Remove the UDF registration."""
        ...
    def merge_tables(self, left: str, right: str, key: str,
                     strategies: Optional[Dict[str, str]] = None) -> Any:
        """Execute a merge on two DuckDB tables and return result."""
        ...
    def register_strategy(self, name: str, func: Callable) -> None:
        """Register a custom merge strategy as a DuckDB UDF callback."""
        ...
    def health_check(self) -> Dict[str, Any]: ...

class DuckDBMergeQLExtension:
    """Bridge between MergeQL parser and DuckDB execution engine.

    Translates MergeQL AST into DuckDB-optimized query plans.
    """
    def __init__(self, connection: Any = None): ...
    def execute_mergeql(self, query: str) -> Any:
        """Execute a MergeQL query via DuckDB backend."""
        ...
    def explain_mergeql(self, query: str) -> str:
        """Show DuckDB execution plan for a MergeQL query."""
        ...
```

Test file: `tests/test_acc_duckdb_udf.py` (~30 tests, mocked DuckDB)
Estimated lines: ~500

#### 3.4.2 ACC-2: dbt Package — `crdt_merge/accelerators/dbt_package.py` (~350 lines)

**Developer:** Dev D
**Phase:** 1 — Foundation (Quick Win)
**External Dep:** `dbt-core` (lazy import, optional — generates pure SQL/Jinja)

dbt Hub package for conflict-aware transforms. Generates cross-database SQL (Jinja templates
for Snowflake, BigQuery, Postgres, DuckDB). Pre-built models for customer dedup, inventory sync,
CRM merge.

```python
# Copyright 2026 Ryan Gillespie
# Licensed under BSL-1.1

from __future__ import annotations
from typing import Any, Dict, List, Optional

class DbtCRDTMergePackage:
    """dbt package generator for CRDT merge macros.

    Generates dbt-compatible Jinja macros that implement CRDT merge
    strategies in pure SQL. Works across all dbt-supported warehouses.

    Example:
        pkg = DbtCRDTMergePackage()
        macro = pkg.generate_macro('lww', key='id', fields=['name', 'email'])
        # {{ crdt_merge(ref('source_a'), ref('source_b'), key='id', strategy='lww') }}
    """
    def __init__(self, target_warehouse: str = "duckdb"): ...
    def generate_macro(self, strategy: str, key: str,
                       fields: Optional[List[str]] = None) -> str:
        """Generate a dbt Jinja macro for the given merge strategy."""
        ...
    def generate_model(self, model_name: str, sources: List[str],
                       key: str, strategies: Dict[str, str]) -> str:
        """Generate a complete dbt model SQL file."""
        ...
    def generate_schema_yaml(self, model_name: str, columns: List[str]) -> str:
        """Generate dbt schema.yml for the merge model."""
        ...
    def generate_package(self, output_dir: str) -> None:
        """Generate a complete dbt package directory structure."""
        ...
    def supported_warehouses(self) -> List[str]:
        """List supported target warehouses."""
        ...
    def health_check(self) -> Dict[str, Any]: ...
```

Test file: `tests/test_acc_dbt_package.py` (~25 tests, pure SQL/Jinja output validation)
Estimated lines: ~350

#### 3.4.3 ACC-3: DuckLake Semantic Conflict Layer — `crdt_merge/accelerators/ducklake.py` (~500 lines)

**Developer:** Dev B (dataframe.py, schema_evolution.py, arrow.py owner)
**Phase:** 3 — Ecosystem Lock-in
**External Dep:** `duckdb` (lazy import)

Field-level conflict resolution for DuckLake snapshots. Merkle-based change detection
for efficient delta sync. Deterministic merge producing identical results regardless of
operation order.

```python
# Copyright 2026 Ryan Gillespie
# Licensed under BSL-1.1

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from crdt_merge.core import MergeSchema

class DuckLakeConflictResolver:
    """Semantic conflict resolution for DuckLake snapshots.

    Provides field-level conflict resolution with configurable strategies
    for DuckLake data snapshots, extending beyond transaction-level conflict
    handling.

    Example:
        resolver = DuckLakeConflictResolver(conn, schema=my_schema)
        result = resolver.merge_snapshots('snapshot_v1', 'snapshot_v2', key='id')
    """
    def __init__(self, connection: Any = None, schema: Optional[MergeSchema] = None): ...
    def merge_snapshots(self, left: str, right: str, key: str) -> Any:
        """Merge two DuckLake snapshots with field-level resolution."""
        ...
    def detect_changes(self, snapshot_a: str, snapshot_b: str) -> List[Dict[str, Any]]:
        """Detect field-level changes between snapshots using Merkle trees."""
        ...
    def audit_trail(self, key: Any) -> List[Dict[str, Any]]:
        """Get full audit trail for a record: which source won each field and why."""
        ...
    def branch(self, snapshot: str, branch_name: str) -> str:
        """Create a branch from a DuckLake snapshot."""
        ...
    def merge_branches(self, branch_a: str, branch_b: str, key: str) -> Any:
        """Merge two branches with CRDT conflict resolution."""
        ...
    def health_check(self) -> Dict[str, Any]: ...
```

Test file: `tests/test_acc_ducklake.py` (~25 tests, mocked DuckDB)
Estimated lines: ~500

#### 3.4.4 ACC-4: Polars Expression Plugin — `crdt_merge/accelerators/polars_plugin.py` (~400 lines)

**Developer:** Dev B (dataframe.py, arrow.py owner)
**Phase:** 3 — Ecosystem Lock-in
**External Dep:** `polars` (lazy import)

Native Polars expression plugin wrapping crdt-merge core. Arrow-native zero-copy interop.

```python
# Copyright 2026 Ryan Gillespie
# Licensed under BSL-1.1

from __future__ import annotations
from typing import Any, Dict, List, Optional
from crdt_merge.core import MergeSchema

class PolarsCRDTMerge:
    """Polars expression plugin for CRDT merge operations.

    Provides native Polars DataFrame merge with CRDT strategies.
    Uses Arrow zero-copy interop for maximum performance.

    Example:
        merger = PolarsCRDTMerge(schema=my_schema)
        result = merger.merge(df_left, df_right, key='id')
        # Or as expression: df.with_columns(crdt_merge('col_a', 'col_b', strategy='lww'))
    """
    def __init__(self, schema: Optional[MergeSchema] = None): ...
    def merge(self, left: Any, right: Any, key: str,
              strategies: Optional[Dict[str, str]] = None) -> Any:
        """Merge two Polars DataFrames with CRDT strategies."""
        ...
    def merge_lazy(self, left: Any, right: Any, key: str,
                   strategies: Optional[Dict[str, str]] = None) -> Any:
        """Lazy merge for streaming large datasets."""
        ...
    def as_expression(self, field: str, strategy: str = "lww") -> Any:
        """Return a Polars expression for use in with_columns()."""
        ...
    def register_namespace(self) -> None:
        """Register 'crdt' namespace on Polars DataFrames."""
        ...
    def health_check(self) -> Dict[str, Any]: ...
```

Test file: `tests/test_acc_polars_plugin.py` (~25 tests, mocked Polars)
Estimated lines: ~400

#### 3.4.5 ACC-5: Arrow Flight Merge Service — `crdt_merge/accelerators/flight_server.py` (~600 lines)

**Developer:** Dev A (core.py, mergeql.py owner)
**Phase:** 4 — Enterprise & Edge
**External Dep:** `pyarrow` (lazy import — uses pyarrow.flight)

gRPC-based Arrow Flight server. DoExchange RPC: client sends two streams, receives merged stream.
Makes crdt-merge available to Java, Go, Rust, C++, JavaScript. Enterprise revenue vehicle.

```python
# Copyright 2026 Ryan Gillespie
# Licensed under BSL-1.1

from __future__ import annotations
from typing import Any, Dict, List, Optional
from crdt_merge.core import MergeSchema

class FlightMergeServer:
    """Arrow Flight server for merge-as-a-service.

    Implements DoExchange for streaming CRDT merge via gRPC.
    Clients send two Arrow streams, receive one merged stream.
    Strategy configured via Flight metadata headers.

    Example:
        server = FlightMergeServer(host='0.0.0.0', port=8815)
        server.serve()  # Blocks, or use server.start() for background
    """
    def __init__(self, host: str = "0.0.0.0", port: int = 8815,
                 default_schema: Optional[MergeSchema] = None): ...
    def serve(self) -> None:
        """Start the Flight server (blocking)."""
        ...
    def start(self) -> None:
        """Start the Flight server in background."""
        ...
    def stop(self) -> None:
        """Stop the Flight server."""
        ...
    def do_exchange(self, context: Any, descriptor: Any, reader: Any, writer: Any) -> None:
        """Handle DoExchange RPC — receive two streams, return merged stream."""
        ...
    def do_get(self, context: Any, ticket: Any) -> Any:
        """Handle DoGet — retrieve previously merged results."""
        ...
    def list_flights(self, context: Any, criteria: Any) -> Any:
        """List available merge endpoints."""
        ...
    def health_check(self) -> Dict[str, Any]: ...

class FlightMergeClient:
    """Client for the Arrow Flight merge service.

    Example:
        client = FlightMergeClient('localhost:8815')
        result = client.merge(left_table, right_table, key='id', strategy='lww')
    """
    def __init__(self, location: str): ...
    def merge(self, left: Any, right: Any, key: str,
              strategies: Optional[Dict[str, str]] = None) -> Any:
        """Send two tables to merge server, receive merged result."""
        ...
    def close(self) -> None: ...
```

Test file: `tests/test_acc_flight_server.py` (~30 tests, mocked Flight)
Estimated lines: ~600

#### 3.4.6 ACC-6: Airbyte Destination Connector — `crdt_merge/accelerators/airbyte.py` (~300 lines)

**Developer:** Dev D
**Phase:** 2 — Technical Foundation
**External Dep:** `airbyte_cdk` (lazy import)

Airbyte destination connector (Python CDK) that resolves conflicts on ingest using CRDT strategies.

```python
# Copyright 2026 Ryan Gillespie
# Licensed under BSL-1.1

from __future__ import annotations
from typing import Any, Dict, List, Optional, Iterable
from crdt_merge.core import MergeSchema

class AirbyteCRDTDestination:
    """Airbyte destination connector with CRDT merge on ingest.

    Wraps crdt-merge as an Airbyte destination that resolves field-level
    conflicts during data ingestion, replacing Airbyte's default
    'last record wins' dedup with configurable CRDT strategies.

    Example:
        dest = AirbyteCRDTDestination(schema=my_schema)
        dest.write(configured_catalog, input_messages)
    """
    def __init__(self, schema: Optional[MergeSchema] = None): ...
    def spec(self) -> Dict[str, Any]:
        """Return Airbyte connector spec with strategy configuration."""
        ...
    def check(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate connector configuration."""
        ...
    def write(self, config: Dict[str, Any], configured_catalog: Any,
              input_messages: Iterable[Any]) -> Iterable[Any]:
        """Write records with CRDT merge resolution."""
        ...
    def health_check(self) -> Dict[str, Any]: ...
```

Test file: `tests/test_acc_airbyte.py` (~20 tests, mocked CDK)
Estimated lines: ~300

#### 3.4.7 ACC-7: SQLite Extension — `crdt_merge/accelerators/sqlite_ext.py` (~500 lines)

**Developer:** Dev C (streaming.py, delta.py, merkle.py owner)
**Phase:** 4 — Enterprise & Edge
**External Dep:** `sqlite3` (stdlib), optional C extension bindings

Local-first / edge CRDT merge for SQLite. Fills the vacuum left by cr-sqlite (archived July 2025).

```python
# Copyright 2026 Ryan Gillespie
# Licensed under BSL-1.1

from __future__ import annotations
from typing import Any, Dict, List, Optional
from crdt_merge.core import MergeSchema

class SQLiteCRDTMerge:
    """SQLite extension for CRDT merge operations.

    Registers CRDT merge as SQLite custom functions, enabling
    local-first / edge data sync with conflict resolution.

    Example:
        ext = SQLiteCRDTMerge(db_path='local.db', schema=my_schema)
        ext.register()
        ext.conn.execute("SELECT crdt_merge(t1.val, t2.val, 'lww') FROM t1, t2 ...")
    """
    def __init__(self, db_path: str = ":memory:",
                 schema: Optional[MergeSchema] = None): ...
    def register(self) -> None:
        """Register CRDT merge functions in SQLite."""
        ...
    def merge_tables(self, left: str, right: str, key: str,
                     strategies: Optional[Dict[str, str]] = None) -> List[dict]:
        """Merge two SQLite tables with CRDT strategies."""
        ...
    def sync_from(self, remote_db: str, tables: List[str]) -> Dict[str, int]:
        """Sync and merge from a remote SQLite database."""
        ...
    def create_crdt_table(self, name: str, columns: Dict[str, str],
                          key: str, strategies: Dict[str, str]) -> None:
        """Create a table with embedded CRDT merge metadata."""
        ...
    def health_check(self) -> Dict[str, Any]: ...
```

Test file: `tests/test_acc_sqlite_ext.py` (~25 tests, uses stdlib sqlite3)
Estimated lines: ~500

#### 3.4.8 ACC-8: Streamlit Visual Merge UI — `crdt_merge/accelerators/streamlit_ui.py` (~250 lines)

**Developer:** Dev C (viz.py owner)
**Phase:** 1 — Foundation (Quick Win)
**External Dep:** `streamlit` (lazy import)

Streamlit component showing merge conflicts visually. Lowest-effort accelerator but
highest-quality marketing asset. Part of Snowflake ecosystem.

```python
# Copyright 2026 Ryan Gillespie
# Licensed under BSL-1.1

from __future__ import annotations
from typing import Any, Dict, List, Optional
from crdt_merge.core import MergeSchema

class StreamlitMergeUI:
    """Streamlit component for visual merge conflict resolution.

    Displays two data sources side by side with conflicting cells
    highlighted in amber. Users can override resolution strategies
    per column and export merged results to Parquet.

    Example:
        ui = StreamlitMergeUI(schema=my_schema)
        ui.render(left_data, right_data, key='id')
    """
    def __init__(self, schema: Optional[MergeSchema] = None,
                 title: str = "CRDT Merge Conflict Resolution"): ...
    def render(self, left: Any, right: Any, key: str,
               strategies: Optional[Dict[str, str]] = None) -> Optional[List[dict]]:
        """Render the merge UI in Streamlit and return resolved data."""
        ...
    def render_conflicts(self, conflicts: List[Dict[str, Any]]) -> None:
        """Render a conflict heatmap visualization."""
        ...
    def render_provenance(self, provenance: List[Dict[str, Any]]) -> None:
        """Render provenance trail for merged records."""
        ...
    def export_parquet(self, data: List[dict], filename: str = "merged.parquet") -> None:
        """Export merged results to downloadable Parquet file."""
        ...
    def health_check(self) -> Dict[str, Any]: ...
```

Test file: `tests/test_acc_streamlit_ui.py` (~20 tests, mocked Streamlit)
Estimated lines: ~250

---

## 4. Phase Ordering & Dependencies

```
Phase 1 — Foundation + Quick Wins (Weeks 1-3)
├── Dev A: mergeql.py (independent — reads core.py, strategies.py)
├── Dev B: parquet.py (independent — reads core.py, provenance.py)
├── Dev C: accelerators/streamlit_ui.py [ACC-8] (quick win — reads viz concepts)
└── Dev D: accelerators/dbt_package.py [ACC-2] (quick win — pure SQL/Jinja generation)

Phase 2 — Technical Foundation (Weeks 3-5)
├── Dev A: accelerators/duckdb_udf.py [ACC-1] (requires Phase 1 mergeql.py)
├── Dev C: viz.py (independent — reads provenance.py, dataframe.py)
└── Dev D: accelerators/airbyte.py [ACC-6] (independent — Python CDK)

Phase 3 — Ecosystem Lock-in (Weeks 5-9)
├── Dev B: accelerators/polars_plugin.py [ACC-4] (Arrow-native interop)
├── Dev B: accelerators/ducklake.py [ACC-3] (DuckLake semantic conflicts)
└── Existing streaming infrastructure available for future Kafka/Flink if desired

Phase 4 — Enterprise & Edge + Release (Weeks 9-13)
├── Dev A: accelerators/flight_server.py [ACC-5] (Arrow Flight merge service)
├── Dev C: accelerators/sqlite_ext.py [ACC-7] (local-first / edge)
├── Dev A: __init__.py exports update (all modules)
├── Dev A: accelerators/__init__.py (base protocol + registry)
├── Dev D: wire.py v3 tags for MergeQL types
├── Dev E: test_v070_integration.py (cross-module tests)
├── Dev E: test_v070_accelerator_integration.py (cross-accelerator tests)
└── All: Documentation, CHANGELOG, README

Buffer: 1 week

Total: 13 weeks (+ 1 week buffer)
```

### Dependency Graph

```
                    ┌─────────────┐
                    │   core.py   │ (frozen)
                    └──────┬──────┘
                           │ read-only
              ┌────────────┼────────────┬────────────────────┐
                                                               ┌──────────┐ ┌──────────┐ ┌──────────┐     ┌──────────────────┐
        │mergeql.py│ │parquet.py│ │  viz.py  │     │ accelerators/    │
        │  Dev A   │ │  Dev B   │ │  Dev C   │     │  __init__.py     │
        │ Phase 1  │ │ Phase 1  │ │ Phase 2  │     │  (base protocol) │
        └────┬─────┘ └──────────┘ └────┬─────┘     └────────┬─────────┘
             │ read-only               │                     │
        ┌──────────────┐        ┌─────────────┐           │
        │duckdb_udf.py  │        │streamlit_ui  │           │
        │ACC-1 (Phase 2)│        │ACC-8 (Phs 1) │           │
        └───────────────┘        └──────────────┘           │
                                                             │
        Quick Wins (Phase 1):                    Phase 2-4 Accelerators:
        ┌────────────┐ ┌──────────────┐   ┌──────────┐ ┌──────────┐
        │dbt_package │ │streamlit_ui  │   │ducklake  │ │polars    │
        │ACC-2 Phs 1 │ │ACC-8 Phase 1 │   │ACC-3 Ph3 │ │ACC-4 Ph3 │
        └────────────┘ └──────────────┘   └──────────┘ └──────────┘
        ┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────┐
        │airbyte   │ │duckdb_udf│ │flight_server │ │sqlite_ext│
        │ACC-6 Ph2 │ │ACC-1 Ph2 │ │ACC-5 Phase 4 │ │ACC-7 Ph4 │
        └──────────┘ └──────────┘ └──────────────┘ └──────────┘
```

---

## 5. Collision Prevention Rules

1. **NO modification** of existing 20 source files (SHA-locked in §2.2)
2. **NO modification** of existing 25 test files (SHA-locked in §2.3)
3. New modules write to their **own files ONLY**
4. New test files write to their **own files ONLY**
5. `__init__.py` updates **ONLY by Dev A in Phase 4**
6. Accelerators go in `crdt_merge/accelerators/` subdirectory (NOT in main package dir)
7. All new CRDT types must satisfy **associative + commutative + idempotent** laws
8. All **704 existing tests** must pass (**regression gate**)
9. Each dev **reads existing modules** (import-only), **never writes**
10. Conflicts require **explicit approval** from project lead

### File Ownership Matrix

| File | Dev | Phase | Write Access |
|------|-----|-------|-------------|
| `crdt_merge/mergeql.py` | Dev A | 1 | EXCLUSIVE |
| `crdt_merge/parquet.py` | Dev B | 1 | EXCLUSIVE |
| `crdt_merge/viz.py` | Dev C | 2 | EXCLUSIVE |
| `crdt_merge/accelerators/__init__.py` | Dev A | 4 | EXCLUSIVE |
| `crdt_merge/accelerators/duckdb_udf.py` | Dev A | 2 | EXCLUSIVE |
| `crdt_merge/accelerators/dbt_package.py` | Dev D | 1 | EXCLUSIVE |
| `crdt_merge/accelerators/ducklake.py` | Dev B | 3 | EXCLUSIVE |
| `crdt_merge/accelerators/polars_plugin.py` | Dev B | 3 | EXCLUSIVE |
| `crdt_merge/accelerators/flight_server.py` | Dev A | 4 | EXCLUSIVE |
| `crdt_merge/accelerators/airbyte.py` | Dev D | 2 | EXCLUSIVE |
| `crdt_merge/accelerators/sqlite_ext.py` | Dev C | 4 | EXCLUSIVE |
| `crdt_merge/accelerators/streamlit_ui.py` | Dev C | 1 | EXCLUSIVE |
| `crdt_merge/__init__.py` | Dev A | 4 | UPDATE ONLY (add exports) |

---

## 6. Test Coverage Targets

| Test File | Tests | Dev | Phase |
|-----------|-------|-----|-------|
| `tests/test_mergeql.py` | ~60 | Dev A | 1 |
| `tests/test_parquet.py` | ~40 | Dev B | 1 |
| `tests/test_viz.py` | ~35 | Dev C | 2 |
| `tests/test_acc_duckdb_udf.py` | ~30 | Dev A | 2 |
| `tests/test_acc_dbt_package.py` | ~25 | Dev D | 1 |
| `tests/test_acc_ducklake.py` | ~25 | Dev B | 3 |
| `tests/test_acc_polars_plugin.py` | ~25 | Dev B | 3 |
| `tests/test_acc_flight_server.py` | ~30 | Dev A | 4 |
| `tests/test_acc_airbyte.py` | ~20 | Dev D | 2 |
| `tests/test_acc_sqlite_ext.py` | ~25 | Dev C | 4 |
| `tests/test_acc_streamlit_ui.py` | ~20 | Dev C | 1 |
| `tests/test_v070_integration.py` | ~40 | Dev E | 4 |
| `tests/test_v070_accelerator_integration.py` | ~30 | Dev E | 4 |
| `tests/test_v070_cross_accelerator.py` | ~25 | Dev E | 4 |
| **Total** | **~430** | | |

### Cumulative Test Projection

| Release | Tests |
|---------|-------|
| v0.5.0 | 425 |
| v0.6.0 | 704 |
| v0.7.0 | ~1,200 |

---

## 7. Dev Team Structure (from MASTER KEY §9.1)

| Dev | Existing Ownership (frozen) | v0.7.0 Assignments |
|-----|----------------------------|-------------------|
| **Dev A** | core.py, strategies.py, __init__.py, clocks.py, gossip.py | mergeql.py, accelerators/__init__.py, accelerators/duckdb_udf.py, accelerators/flight_server.py, __init__.py update |
| **Dev B** | dataframe.py, datasets_ext.py, json_merge.py, schema_evolution.py, arrow.py | parquet.py, accelerators/polars_plugin.py, accelerators/ducklake.py |
| **Dev C** | streaming.py, delta.py, merkle.py | viz.py, accelerators/streamlit_ui.py, accelerators/sqlite_ext.py |
| **Dev D** | probabilistic.py, wire.py, async_merge.py, parallel.py | accelerators/dbt_package.py, accelerators/airbyte.py, wire v3 tags |
| **Dev E** | verify.py, provenance.py, dedup.py | test_v070_integration.py, test_v070_accelerator_integration.py |

### Workload Balance

| Dev | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Total Lines |
|-----|---------|---------|---------|---------|-------------|
| Dev A | mergeql (~500) | duckdb_udf (~500) | — | flight_server (~600), accelerators/__init__.py (~100), __init__.py update | ~1,700 |
| Dev B | parquet (~400) | — | polars_plugin (~400) + ducklake (~500) | — | ~1,300 |
| Dev C | streamlit_ui (~250) | viz (~250) | — | sqlite_ext (~500) | ~1,000 |
| Dev D | dbt_package (~350) | airbyte (~300) | — | wire v3 tags | ~700 |
| Dev E | — | — | — | integration tests (~400) + accelerator integration (~300) + cross-accelerator (~250) | ~950 |

---

## 8. Integration Test Specification

### `tests/test_v070_integration.py` (~40 tests)

```python
class TestMergeQLIntegration:
    # 10 tests
    def test_mergeql_basic_pipeline(self): ...
    def test_mergeql_with_schema_evolution(self): ...
    def test_mergeql_with_arrow_backend(self): ...
    def test_mergeql_with_provenance(self): ...
    def test_mergeql_with_custom_strategy(self): ...
    def test_mergeql_chained_merges(self): ...
    def test_mergeql_explain_accuracy(self): ...
    def test_mergeql_large_dataset(self): ...
    def test_mergeql_crdt_laws(self): ...
    def test_mergeql_error_handling(self): ...

class TestParquetIntegration:
    # 10 tests
    def test_parquet_full_pipeline(self): ...
    def test_parquet_with_mergeql(self): ...
    def test_parquet_with_provenance(self): ...
    def test_parquet_multi_ingest(self): ...
    def test_parquet_compact_integrity(self): ...
    def test_parquet_merge_two_containers(self): ...
    def test_parquet_metadata_persistence(self): ...
    def test_parquet_strategy_roundtrip(self): ...
    def test_parquet_empty_operations(self): ...
    def test_parquet_large_dataset(self): ...

class TestVisualizationIntegration:
    # 10 tests
    def test_viz_from_mergeql(self): ...
    def test_viz_from_parquet(self): ...
    def test_viz_from_dataframe_merge(self): ...
    def test_viz_heatmap_accuracy(self): ...
    def test_viz_json_d3_format(self): ...
    def test_viz_csv_export(self): ...
    def test_viz_summary_content(self): ...
    def test_viz_empty_merge(self): ...
    def test_viz_large_conflict_set(self): ...
    def test_viz_cluster_detection(self): ...

class TestCoreAcceleratorIntegration:
    # 10 tests (all external deps mocked)
    def test_accelerator_protocol(self): ...
    def test_accelerator_registry(self): ...
    def test_accelerator_lazy_import(self): ...
    def test_accelerator_error_messages(self): ...
    def test_duckdb_udf_with_mergeql(self): ...
    def test_dbt_package_sql_generation(self): ...
    def test_streamlit_with_viz(self): ...
    def test_airbyte_destination_pipeline(self): ...
    def test_flight_server_roundtrip(self): ...
    def test_end_to_end_pipeline(self): ...
```

### `tests/test_v070_accelerator_integration.py` (~30 tests)

```python
class TestDuckDBAcceleratorIntegration:
    # 8 tests
    def test_duckdb_udf_register_and_query(self): ...
    def test_duckdb_mergeql_bridge(self): ...
    def test_duckdb_with_parquet_source(self): ...
    def test_duckdb_custom_strategy(self): ...
    def test_duckdb_explain_plan(self): ...
    def test_duckdb_large_table_merge(self): ...
    def test_duckdb_crdt_laws(self): ...
    def test_duckdb_error_handling(self): ...

class TestDbtAcceleratorIntegration:
    # 5 tests
    def test_dbt_macro_generation(self): ...
    def test_dbt_cross_warehouse_sql(self): ...
    def test_dbt_model_with_strategies(self): ...
    def test_dbt_schema_yaml(self): ...
    def test_dbt_package_structure(self): ...

class TestPolarsAcceleratorIntegration:
    # 5 tests
    def test_polars_merge_dataframes(self): ...
    def test_polars_lazy_evaluation(self): ...
    def test_polars_arrow_interop(self): ...
    def test_polars_expression_api(self): ...
    def test_polars_crdt_laws(self): ...

class TestEnterpriseAcceleratorIntegration:
    # 7 tests
    def test_flight_server_do_exchange(self): ...
    def test_flight_client_merge(self): ...
    def test_sqlite_crdt_table(self): ...
    def test_sqlite_sync_from(self): ...
    def test_ducklake_snapshot_merge(self): ...
    def test_ducklake_branch_merge(self): ...
    def test_airbyte_write_pipeline(self): ...

class TestStreamlitAcceleratorIntegration:
    # 5 tests
    def test_streamlit_render_conflicts(self): ...
    def test_streamlit_provenance_view(self): ...
    def test_streamlit_export_parquet(self): ...
    def test_streamlit_with_viz_topology(self): ...
    def test_streamlit_strategy_override(self): ...
```

---

## 9. Wire Protocol v3 Tags (Phase 4)

Dev D extends `wire.py` tag space for new types:

| Tag | Type | Description |
|-----|------|-------------|
| `0x30` | MergeQL query | Serialized MergeQL AST |
| `0x31` | MergePlan | Serialized execution plan |
| `0x32` | MergeQLResult | Serialized query result |
| `0x33` | ParquetMergeMetadata | Serialized Parquet metadata |
| `0x34` | ConflictRecord | Serialized conflict event |
| `0x35` | ConflictTopology | Serialized topology export |

**NOTE:** Wire protocol updates are the ONE exception to the "no modify" rule.
Dev D may add NEW tags to `wire.py` but MUST NOT modify existing tag handling.
This must be explicitly approved by project lead before implementation.

---

## 10. Release Criteria

### 10.1 Test Gates

- [ ] All 704 existing tests pass (zero regressions)
- [ ] All ~430 new tests pass (3 core + 8 accelerator + 3 integration)
- [ ] Total: ~1,200 tests passing
- [ ] CRDT laws verified for applicable new types
- [ ] No import errors when accelerators' external deps are missing
- [ ] All 8 accelerators pass lazy import verification

### 10.2 Documentation

- [ ] CHANGELOG.md updated with v0.7.0 entry
- [ ] README.md updated with new features
- [ ] Roadmap v2.0 updated (v0.7.0 marked complete)
- [ ] notebooks/v070_benchmark.ipynb created and verified
- [ ] Copyright headers on ALL new files

### 10.3 Release Artifacts

- [ ] Version bumped to 0.7.0
- [ ] PyPI package published
- [ ] GitHub push with all new files
- [ ] Static badge updated: `pypi-v0.7.0`

---

## 11. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Accelerator external deps break tests | All accelerator tests use mocks; no real external deps in CI |
| MergeQL parser edge cases | Fuzzing test suite with random valid/invalid queries |
| Parquet metadata compatibility | Version field in metadata for forward compatibility |
| Accelerator scope creep | Accelerators provide integration glue ONLY, not full features |
| Wire protocol backward compatibility | New tags only; existing tags immutable |
| DuckDB API changes | Pin to DuckDB 1.5.0+ extension API; version check in UDF registration |
| cr-sqlite vacuum timing | SQLite extension is Phase 4 — can absorb delays without blocking core |
| Arrow Flight complexity | Server/client split allows incremental delivery; client can ship first |

---

## 12. Timeline

| Week | Phase | Deliverables |
|------|-------|-------------|
| 1-3 | Foundation + Quick Wins | mergeql.py (Dev A), parquet.py (Dev B), dbt_package.py ACC-2 (Dev D), streamlit_ui.py ACC-8 (Dev C) |
| 3-5 | Technical Foundation | viz.py (Dev C), duckdb_udf.py ACC-1 (Dev A), airbyte.py ACC-6 (Dev D) |
| 5-9 | Ecosystem Lock-in | polars_plugin.py ACC-4 (Dev B), ducklake.py ACC-3 (Dev B) |
| 9-13 | Enterprise & Edge + Release | flight_server.py ACC-5 (Dev A), sqlite_ext.py ACC-7 (Dev C), accelerators/__init__.py (Dev A), wire v3 (Dev D), integration tests (Dev E), __init__.py update (Dev A) |
| 14 | Buffer | Bug fixes, edge cases, documentation |

**Total: 13 weeks (+ 1 week buffer)**

---

*Document generated: March 2026*
*Synchronized Development Plan — v0.7.0 "The Integration Release"*
*Previous plan: v0.6.0 dev plan (71 KB, 1,841 lines) — fully executed *
