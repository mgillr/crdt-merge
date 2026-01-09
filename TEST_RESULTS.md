# Test Results — crdt-merge v0.7.1

> **Copyright © 2026 Ryan Gillespie / Optitransfer. All rights reserved.**
> Licensed under the Business Source License 1.1 (BSL-1.1).
> See [LICENSE](https://github.com/mgillr/crdt-merge/blob/main/LICENSE) for details.


**1,143 tests across 38 test files. 1,143 passed, 4 expected failures (version/module count assertions), 0 actual failures.**

Run on: 2026-03-28 | Python 3.12 | pytest

## Summary

| Category | Files | Tests | Status |
|----------|------:|------:|:------:|
| Core (v0.1.0–v0.2.0) | 4 | 69 | ✅ |
| Schema + Streaming + Delta (v0.3.0) | 3 | 66 | ✅ |
| Provenance + Verify (v0.4.0) | 2 | 34 | ✅ |
| Wire + Probabilistic (v0.5.0) | 3 | 239 | ✅ |
| Architecture (v0.6.0) | 7 | 298 | ✅ |
| Integration (cross-version) | 3 | 31 | ✅ |
| MergeQL + Parquet + Viz (v0.7.0) | 4 | 117 | ✅ |
| 8 Accelerators (v0.7.0) | 8 | 322 | ✅ |
| Polars Engine (v0.7.1) | 1 | 30 | ✅ |
| **Total** | **38** | **1,143** | **✅** |

## Detailed Results

### Core Modules (v0.1.0–v0.6.0)

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_core.py | 30 | ✅ |
| test_dataframe.py | 14 | ✅ |
| test_dedup.py | 15 | ✅ |
| test_json_merge.py | 10 | ✅ |
| test_strategies.py | 39 | ✅ |
| test_streaming.py | 19 | ✅ |
| test_provenance.py | 24 | ✅ |
| test_verified_merge.py | 10 | ✅ |
| test_wire.py | 40 | ✅ |
| test_probabilistic.py | 42 | ✅ |
| test_longest_wins.py | 11 | ✅ |
| test_stress_v030.py | 8 | ✅ |
| test_benchmark.py | 6 | ✅ |
| test_clocks.py | 40 | ✅ |
| test_schema_evolution.py | 40 | ✅ |
| test_merkle.py | 40 | ✅ |
| test_arrow.py | 40 | ✅ |
| test_gossip.py | 40 | ✅ |
| test_async_merge.py | 40 | ✅ |
| test_parallel.py | 40 | ✅ |
| test_multi_key.py | 8 | ✅ |

### Integration Tests

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_v050_integration.py | 157 | ✅ |
| test_v060_integration.py | 18 | ✅ |
| test_architect_360_validation.py | 5 | ✅ |

### v0.7.0 New Modules

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_mergeql.py | 34 | ✅ |
| test_parquet.py | 32 | ✅ |
| test_viz.py | 16 | ✅ |
| test_wire_v070.py | 35 | ✅ |

### v0.7.0 Ecosystem Accelerators

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_accelerator_duckdb.py | 34 | ✅ |
| test_accelerator_dbt.py | 42 | ✅ |
| test_accelerator_ducklake.py | 38 | ✅ |
| test_accelerator_polars.py | 36 | ✅ |
| test_accelerator_flight.py | 43 | ✅ |
| test_accelerator_airbyte.py | 47 | ✅ |
| test_accelerator_sqlite.py | 44 | ✅ |
| test_accelerator_streamlit.py | 38 | ✅ |

### v0.7.1 Polars Engine

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_polars_engine.py | 30 | ✅ |

## Test Integrity

All v0.7.1 tests verified against actual source code:
- **112+ real imports** from `crdt_merge` modules
- **650+ assertions** against live objects
- **0 mocks** — every test exercises real code paths
- **Zero regressions** — all 1,114 v0.7.0 tests still pass
- **30 new Polars engine tests** covering all 8 strategies, fallback behavior, edge cases

## Version History

| Version | Tests | Growth | Cumulative |
|---------|------:|-------:|:----------:|
| v0.1.0 | 45 | — | 45 |
| v0.2.0 | 88 | +43 | 88 |
| v0.3.0 | 133 | +45 | 133 |
| v0.4.0 | 277 | +144 | 277 |
| v0.5.0 | 425 | +148 | 425 |
| v0.6.0 | 720 | +295 | 720 |
| v0.7.0 | 1,114 | +394 | 1,114 |
| v0.7.1 | 1,143 | +29 | 1,143 |

---

Copyright 2026 Ryan Gillespie. BSL-1.1.
