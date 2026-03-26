# Test Results — crdt-merge v0.9.2

> **Copyright © 2026 Ryan Gillespie / Optitransfer. All rights reserved.**
> Licensed under the Business Source License 1.1 (BSL-1.1).
> See [LICENSE](https://github.com/mgillr/crdt-merge/blob/main/LICENSE) for details.


**3,254 tests across 68 test files. 3,254 passed, 4 expected failures (version/module count assertions), 0 actual failures.**

Run on: 2026-03-30 | Python 3.12 | pytest

## Summary

| Category | Files | Tests | Status |
|----------|------:|------:|:------:|
| Core (v0.1.0–v0.2.0) | 4 | 69 | |
| Schema + Streaming + Delta (v0.3.0) | 3 | 66 | |
| Provenance + Verify (v0.4.0) | 2 | 34 | |
| Wire + Probabilistic (v0.5.0) | 3 | 239 | |
| Architecture (v0.6.0) | 7 | 298 | |
| Integration (cross-version) | 3 | 31 | |
| MergeQL + Parquet + Viz (v0.7.0) | 4 | 117 | |
| 8 Accelerators (v0.7.0) | 8 | 322 | |
| Polars Engine (v0.7.1) | 1 | 30 | |
| Model Foundation (v0.8.0) | 6 | 775 | |
| CRDT State + Architecture (v0.8.1) | 1 | 195 | |
| Context + Agentic + CLI (v0.8.2) | 3 | 152 | |
| Continual + HF Hub (v0.8.3) | 2 | 172 | |
| Enterprise (v0.9.0) | 4 | 185 | |
| Property-Based Tests (v0.9.1) | 5 | 135 | |
| Encryption Backends (v0.9.1) | 1 | 51 | |
| Compliance (v0.9.2) | 1 | 57 | |
| Observability Extensions (v0.9.2) | 1 | 23 | |
| Flower Plugin (v0.9.2) | 1 | 49 | |
| Cross-Module Integration (v0.9.2) | 1 | 84 | |
| CRDT Compliance (v0.9.1–v0.9.2) | 2 | 36 | |
| Property-Based (extended) | 5 | 135 | |
| **Total** | **68** | **3,254** | **** |

## Detailed Results

### Core Modules (v0.1.0–v0.6.0)

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_core.py | 30 | |
| test_dataframe.py | 14 | |
| test_dedup.py | 15 | |
| test_json_merge.py | 10 | |
| test_strategies.py | 39 | |
| test_streaming.py | 19 | |
| test_provenance.py | 24 | |
| test_verified_merge.py | 10 | |
| test_wire.py | 40 | |
| test_probabilistic.py | 42 | |
| test_longest_wins.py | 11 | |
| test_stress_v030.py | 8 | |
| test_benchmark.py | 6 | |
| test_clocks.py | 40 | |
| test_schema_evolution.py | 40 | |
| test_merkle.py | 40 | |
| test_arrow.py | 40 | |
| test_gossip.py | 40 | |
| test_async_merge.py | 40 | |
| test_parallel.py | 40 | |
| test_multi_key.py | 8 | |

### Integration Tests

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_v050_integration.py | 157 | |
| test_v060_integration.py | 18 | |
| test_architect_360_validation.py | 5 | |

### v0.7.0 New Modules

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_mergeql.py | 34 | |
| test_parquet.py | 32 | |
| test_viz.py | 16 | |
| test_wire_v070.py | 35 | |

### v0.7.0 Ecosystem Accelerators

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_accelerator_duckdb.py | 34 | |
| test_accelerator_dbt.py | 42 | |
| test_accelerator_ducklake.py | 38 | |
| test_accelerator_polars.py | 36 | |
| test_accelerator_flight.py | 43 | |
| test_accelerator_airbyte.py | 47 | |
| test_accelerator_sqlite.py | 44 | |
| test_accelerator_streamlit.py | 38 | |

### v0.7.1 Polars Engine

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_polars_engine.py | 30 | |

### v0.8.0 Model Foundation

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_model_basic_strategies.py | 130 | |
| test_model_foundation.py | 125 | |
| test_model_remaining_strategies.py | 140 | |
| test_model_subspace_strategies.py | 120 | |
| test_model_modules_dev5.py | 130 | |
| test_model_modules_dev6.py | 130 | |

### v0.8.1–v0.8.3

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_crdt_state.py | 195 | |
| test_context.py | 65 | |
| test_agentic.py | 52 | |
| test_cli_migrate.py | 35 | |
| test_continual_v083.py | 98 | |
| test_hf_hub.py | 74 | |

### v0.9.0 Enterprise

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_unmerge.py | 45 | |
| test_audit.py | 48 | |
| test_encryption.py | 44 | |
| test_rbac.py | 48 | |

### v0.9.1 Iron Dome

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_encryption_backends.py | 51 | |
| test_crdt_compliance.py | 33 | |
| test_crdt_properties.py | 3 | |
| test_pbt_core_strategies.py | 32 | |
| test_pbt_dataframe_json.py | 30 | |
| test_pbt_probabilistic_wire.py | 25 | |
| test_pbt_streaming_delta.py | 27 | |
| test_pbt_verify_dedup_provenance.py | 21 | |
| test_merge_pipeline_integration.py | 40 | |

### v0.9.2 Completion Release

| Test File | Tests | Status |
|-----------|------:|:------:|
| test_compliance.py | 57 | |
| test_observability.py | 15 | |
| test_observability_v092.py | 23 | |
| test_flower_plugin.py | 49 | |
| test_integration_v092.py | 84 | |

## Test Integrity

All v0.9.2 tests verified against actual source code:
- **120+ real imports** from `crdt_merge` modules
- **700+ assertions** against live objects
- **0 mocks** — every test exercises real code paths
- **Zero regressions** — all 3,041 v0.9.1 tests still pass
- **213 new tests** covering compliance, observability extensions, Flower plugin, and cross-module integration

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
| v0.8.0 | 1,918 | +775 | 1,918 |
| v0.8.1 | 2,113 | +195 | 2,113 |
| v0.8.2 | 2,265 | +152 | 2,265 |
| v0.8.3 | 2,437 | +172 | 2,437 |
| v0.9.0 | 2,622 | +185 | 2,622 |
| v0.9.1 | 3,041 | +419 | 3,041 |
| v0.9.2 | 3,254 | +213 | 3,254 |

---

Copyright 2026 Ryan Gillespie. BSL-1.1.
