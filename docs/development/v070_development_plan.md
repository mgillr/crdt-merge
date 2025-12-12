# crdt-merge v0.7.0 — Synchronized Development Plan
# "The Integration Release"

**Copyright 2026 Ryan Gillespie**
**Contact:** rgillespie83@icloud.com · data@optitransfer.ch
**License:** Apache-2.0

---

## 1. Mission Statement

v0.7.0 — "The Integration Release" — transforms crdt-merge from a standalone merge toolkit into an
integrated component of the modern data stack. This release delivers:

1. **MergeQL** — SQL interface for CRDT merge operations, reaching every data warehouse user
2. **Self-Merging Parquet** — Files with embedded merge semantics and provenance
3. **Conflict Topology Visualization** — Interactive conflict analysis with D3-compatible export
4. **Data Stack Connectors** — Integration with Kafka, Flink, dbt, Airflow, LangChain, and a REST server

This release bridges the gap between toolkit and product, making CRDT merge accessible through
familiar interfaces (SQL, REST, data pipelines) while preserving zero-dependency core.

### Release Targets

| Metric | v0.6.0 Baseline | v0.7.0 Target |
|--------|----------------|---------------|
| Source modules | 20 | 29 (+9: 3 core + 6 connectors + __init__) |
| Source lines | 7,301 | ~10,800 (+~3,500) |
| Test files | 24 | 35 (+11: 3 core + 7 connector + 1 integration) |
| Tests passing | 704 | ~1,000 (+~296) |
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
# Licensed under Apache-2.0

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
# Licensed under Apache-2.0

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
# Licensed under Apache-2.0

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

### 3.4 Connectors — `crdt_merge/connectors/` (Phase 3)

#### Architecture

Connectors live in a `crdt_merge/connectors/` subdirectory with lazy imports.
Each connector MUST:
1. Handle `ImportError` gracefully (print helpful install message)
2. Work WITHOUT the external dependency for basic type checking
3. Include copyright header
4. Follow the `CRDTMergeConnector` base protocol

```python
# crdt_merge/connectors/__init__.py
# Copyright 2026 Ryan Gillespie
# Licensed under Apache-2.0

from __future__ import annotations
from typing import Protocol, Any, Dict, List, Optional, runtime_checkable

@runtime_checkable
class CRDTMergeConnector(Protocol):
    """Base protocol for all crdt-merge connectors."""
    name: str
    version: str

    def connect(self, **kwargs: Any) -> None: ...
    def merge_from(self, source: Any) -> Any: ...
    def merge_to(self, target: Any, data: Any) -> None: ...
    def health_check(self) -> Dict[str, Any]: ...
```

#### 3.4.1 Kafka Connector — `crdt_merge/connectors/kafka.py` (~400 lines)

**Developer:** Dev D
**Phase:** 3
**External Dep:** `confluent-kafka` (lazy import)

```python
class KafkaMergeConsumer:
    """Consume from Kafka topics with CRDT merge semantics.

    Reads from one or more topics, merges records by key using
    configured strategies, and produces merged output.
    """
    def __init__(self, bootstrap_servers: str, group_id: str,
                 schema: Optional[MergeSchema] = None): ...
    def subscribe(self, topics: List[str]) -> None: ...
    def consume_and_merge(self, timeout: float = 1.0) -> List[dict]: ...
    def commit(self) -> None: ...
    def close(self) -> None: ...

class KafkaMergeProducer:
    """Produce CRDT-merged records to Kafka topics."""
    def __init__(self, bootstrap_servers: str): ...
    def produce(self, topic: str, records: List[dict], key_field: str) -> None: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...
```

Test file: `tests/test_connector_kafka.py` (~20 tests, all mocked)

#### 3.4.2 Flink Connector — `crdt_merge/connectors/flink.py` (~350 lines)

**Developer:** Dev D
**Phase:** 3
**External Dep:** `pyflink` (lazy import)

```python
class FlinkMergeFunction:
    """Flink ProcessFunction with CRDT merge semantics.

    Integrates crdt-merge into Flink streaming pipelines as a
    stateful process function.
    """
    def __init__(self, schema: Optional[MergeSchema] = None): ...
    def process_element(self, value: dict, ctx: Any) -> List[dict]: ...
    def merge_state(self) -> Dict[str, Any]: ...

class FlinkMergeTable:
    """Flink Table API integration for batch merge operations."""
    def __init__(self, table_env: Any = None): ...
    def register_table(self, name: str, data: List[dict]) -> None: ...
    def merge_tables(self, *names: str, key: str,
                     strategies: Optional[Dict[str, str]] = None) -> List[dict]: ...
```

Test file: `tests/test_connector_flink.py` (~20 tests, all mocked)

#### 3.4.3 dbt Connector — `crdt_merge/connectors/dbt.py` (~300 lines)

**Developer:** Dev E
**Phase:** 3
**External Dep:** `dbt-core` (lazy import)

```python
class DbtMergeModel:
    """dbt model that uses CRDT merge instead of standard merge.

    Generates dbt-compatible SQL with CRDT merge semantics embedded
    as Jinja macros.
    """
    def __init__(self, model_name: str, schema: Optional[MergeSchema] = None): ...
    def generate_sql(self) -> str: ...
    def generate_yaml(self) -> str: ...
    def as_macro(self) -> str: ...

class DbtMergeMaterialization:
    """Custom dbt materialization for CRDT merge tables."""
    def __init__(self): ...
    def materialize(self, source_tables: List[str], key: str,
                    strategies: Optional[Dict[str, str]] = None) -> str: ...
```

Test file: `tests/test_connector_dbt.py` (~20 tests, all mocked)

#### 3.4.4 Airflow Connector — `crdt_merge/connectors/airflow.py` (~250 lines)

**Developer:** Dev E
**Phase:** 3
**External Dep:** `apache-airflow` (lazy import)

```python
class CRDTMergeOperator:
    """Airflow operator that performs CRDT merge as a DAG task.

    Reads from configured sources, merges with strategies,
    writes to configured output.
    """
    def __init__(self, task_id: str, sources: List[str], key: str,
                 strategies: Optional[Dict[str, str]] = None, **kwargs): ...
    def execute(self, context: Any) -> List[dict]: ...
    def pre_execute(self, context: Any) -> None: ...

class CRDTMergeSensor:
    """Airflow sensor that waits for merge conflicts to resolve."""
    def __init__(self, task_id: str, check_fn: Any = None, **kwargs): ...
    def poke(self, context: Any) -> bool: ...
```

Test file: `tests/test_connector_airflow.py` (~20 tests, all mocked)

#### 3.4.5 LangChain Connector — `crdt_merge/connectors/langchain.py` (~200 lines)

**Developer:** Dev C
**Phase:** 3
**External Dep:** `langchain` (lazy import)

```python
class CRDTMergeRetriever:
    """LangChain retriever that merges results from multiple sources.

    Uses CRDT merge to combine retrieval results from different
    vector stores or document sources.
    """
    def __init__(self, retrievers: List[Any],
                 schema: Optional[MergeSchema] = None): ...
    def get_relevant_documents(self, query: str) -> List[Any]: ...
    def merge_results(self, results: List[List[Any]]) -> List[Any]: ...

class CRDTMergeTool:
    """LangChain tool that exposes CRDT merge to agents."""
    name: str = "crdt_merge"
    description: str = "Merge datasets using CRDT strategies"
    def _run(self, query: str) -> str: ...
```

Test file: `tests/test_connector_langchain.py` (~20 tests, all mocked)

#### 3.4.6 REST Server — `crdt_merge/connectors/server.py` (~300 lines)

**Developer:** Dev A
**Phase:** 3
**External Dep:** None (uses stdlib `http.server`, optional `flask`)

```python
class CRDTMergeServer:
    """HTTP REST server for CRDT merge operations.

    Exposes merge operations via REST API endpoints:
    - POST /merge — Execute a merge
    - POST /sources — Register a source
    - GET /sources — List sources
    - POST /mergeql — Execute MergeQL query
    - GET /health — Health check
    """
    def __init__(self, host: str = "0.0.0.0", port: int = 8765): ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def register_source(self, name: str, data: List[dict]) -> None: ...

    # Internal handlers
    def _handle_merge(self, request: dict) -> dict: ...
    def _handle_mergeql(self, request: dict) -> dict: ...
    def _handle_sources(self, request: dict) -> dict: ...
    def _handle_health(self) -> dict: ...
```

Test file: `tests/test_connector_server.py` (~20 tests, using stdlib)

---

## 4. Phase Ordering & Dependencies

```
Phase 1 — Foundation (3 weeks)
├── Dev A: mergeql.py (independent — reads core.py, strategies.py)
└── Dev B: parquet.py (independent — reads core.py, provenance.py)

Phase 2 — Integration (2 weeks)
├── Dev C: viz.py (independent — reads provenance.py, dataframe.py)
└── Dev A: MergeQL DuckDB optimizer extension (requires Phase 1 mergeql.py)

Phase 3 — Connectors (3 weeks)
├── Dev A: connectors/server.py (reads mergeql.py from Phase 1)
├── Dev C: connectors/langchain.py (independent)
├── Dev D: connectors/kafka.py (independent)
├── Dev D: connectors/flink.py (independent)
├── Dev E: connectors/dbt.py (independent)
└── Dev E: connectors/airflow.py (independent)

Phase 4 — Integration & Release (2 weeks)
├── Dev A: __init__.py exports update (all modules)
├── Dev D: wire.py v3 tags for MergeQL types
├── Dev E: test_v070_integration.py (cross-module tests)
└── All: Documentation, CHANGELOG, README

Buffer: 1 week

Total: 11 weeks
```

### Dependency Graph

```
                    ┌─────────────┐
                    │   core.py   │ (frozen)
                    └──────┬──────┘
                           │ read-only
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │mergeql.py│ │parquet.py│ │  viz.py  │
        │  Dev A   │ │  Dev B   │ │  Dev C   │
        │ Phase 1  │ │ Phase 1  │ │ Phase 2  │
        └────┬─────┘ └──────────┘ └──────────┘
             │ read-only
        ┌────▼─────┐
        │server.py │ (Phase 3)
        │  Dev A   │
        └──────────┘

        Connectors (Phase 3, all independent):
        ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐
        │ kafka.py │ │ flink.py │ │  dbt.py  │ │airflow.py│ │langchain.py│
        │  Dev D   │ │  Dev D   │ │  Dev E   │ │  Dev E   │ │   Dev C   │
        └──────────┘ └──────────┘ └──────────┘ └──────────┘ └───────────┘
```

---

## 5. Collision Prevention Rules

1. **NO modification** of existing 20 source files (SHA-locked in §2.2)
2. **NO modification** of existing 25 test files (SHA-locked in §2.3)
3. New modules write to their **own files ONLY**
4. New test files write to their **own files ONLY**
5. `__init__.py` updates **ONLY by Dev A in Phase 4**
6. Connectors go in `crdt_merge/connectors/` subdirectory (NOT in main package dir)
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
| `crdt_merge/connectors/__init__.py` | Dev A | 3 | EXCLUSIVE |
| `crdt_merge/connectors/kafka.py` | Dev D | 3 | EXCLUSIVE |
| `crdt_merge/connectors/flink.py` | Dev D | 3 | EXCLUSIVE |
| `crdt_merge/connectors/dbt.py` | Dev E | 3 | EXCLUSIVE |
| `crdt_merge/connectors/airflow.py` | Dev E | 3 | EXCLUSIVE |
| `crdt_merge/connectors/langchain.py` | Dev C | 3 | EXCLUSIVE |
| `crdt_merge/connectors/server.py` | Dev A | 3 | EXCLUSIVE |
| `crdt_merge/__init__.py` | Dev A | 4 | UPDATE ONLY (add exports) |

---

## 6. Test Coverage Targets

| Test File | Tests | Dev | Phase |
|-----------|-------|-----|-------|
| `tests/test_mergeql.py` | ~60 | Dev A | 1 |
| `tests/test_parquet.py` | ~40 | Dev B | 1 |
| `tests/test_viz.py` | ~35 | Dev C | 2 |
| `tests/test_connector_kafka.py` | ~20 | Dev D | 3 |
| `tests/test_connector_flink.py` | ~20 | Dev D | 3 |
| `tests/test_connector_dbt.py` | ~20 | Dev E | 3 |
| `tests/test_connector_airflow.py` | ~20 | Dev E | 3 |
| `tests/test_connector_langchain.py` | ~20 | Dev C | 3 |
| `tests/test_connector_server.py` | ~20 | Dev A | 3 |
| `tests/test_v070_integration.py` | ~40 | Dev E | 4 |
| **Total** | **~295** | | |

### Cumulative Test Projection

| Release | Tests |
|---------|-------|
| v0.5.0 | 425 |
| v0.6.0 | 704 |
| v0.7.0 | ~1,000 |

---

## 7. Dev Team Structure (from MASTER KEY §9.1)

| Dev | Existing Ownership (frozen) | v0.7.0 Assignments |
|-----|----------------------------|-------------------|
| **Dev A** | core.py, strategies.py, __init__.py, clocks.py, gossip.py | mergeql.py, connectors/__init__.py, connectors/server.py, __init__.py update |
| **Dev B** | dataframe.py, datasets_ext.py, json_merge.py, schema_evolution.py, arrow.py | parquet.py |
| **Dev C** | streaming.py, delta.py, merkle.py | viz.py, connectors/langchain.py |
| **Dev D** | probabilistic.py, wire.py, async_merge.py, parallel.py | connectors/kafka.py, connectors/flink.py, wire v3 tags |
| **Dev E** | verify.py, provenance.py, dedup.py | connectors/dbt.py, connectors/airflow.py, test_v070_integration.py |

### Workload Balance

| Dev | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Total Lines |
|-----|---------|---------|---------|---------|-------------|
| Dev A | mergeql (~500) | optimizer ext | server (~300) | __init__.py | ~850 |
| Dev B | parquet (~400) | — | — | — | ~400 |
| Dev C | — | viz (~250) | langchain (~200) | — | ~450 |
| Dev D | — | — | kafka (~400) + flink (~350) | wire v3 | ~800 |
| Dev E | — | — | dbt (~300) + airflow (~250) | integration tests (~400) | ~950 |

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

class TestConnectorIntegration:
    # 10 tests (all external deps mocked)
    def test_connector_protocol(self): ...
    def test_kafka_mock_pipeline(self): ...
    def test_flink_mock_pipeline(self): ...
    def test_dbt_sql_generation(self): ...
    def test_airflow_operator_execution(self): ...
    def test_langchain_retriever(self): ...
    def test_server_endpoints(self): ...
    def test_connector_lazy_import(self): ...
    def test_connector_error_messages(self): ...
    def test_end_to_end_pipeline(self): ...
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
- [ ] All ~295 new tests pass
- [ ] Total: ~1,000 tests passing
- [ ] CRDT laws verified for applicable new types
- [ ] No import errors when connectors' external deps are missing

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
| Connector external deps break tests | All connector tests use mocks; no real external deps in CI |
| MergeQL parser edge cases | Fuzzing test suite with random valid/invalid queries |
| Parquet metadata compatibility | Version field in metadata for forward compatibility |
| Connector scope creep | Connectors provide integration glue ONLY, not full features |
| Wire protocol backward compatibility | New tags only; existing tags immutable |

---

## 12. Timeline

| Week | Phase | Deliverables |
|------|-------|-------------|
| 1-3 | Foundation | mergeql.py + parquet.py (Dev A, B) |
| 4-5 | Integration | viz.py + MergeQL optimizer (Dev A, C) |
| 6-8 | Connectors | All 6 connectors (Dev A, C, D, E) |
| 9-10 | Integration & Testing | Integration tests, wire v3, __init__ (Dev A, D, E) |
| 11 | Buffer | Bug fixes, edge cases, documentation |

**Total: 11 weeks**

---

*Document generated: March 2026*
*Synchronized Development Plan — v0.7.0 "The Integration Release"*
*Previous plan: v0.6.0 dev plan (71 KB, 1,841 lines) — fully executed ✅*
