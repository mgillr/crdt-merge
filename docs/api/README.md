# API Reference — crdt-merge v0.8.2

Comprehensive API reference for all crdt-merge modules, generated from source code.

## Module Index

### Core Layer
| Module | Description | Docs |
|--------|-------------|------|
| `crdt_merge.core` | GCounter, PNCounter, LWWRegister, ORSet, LWWMap | [core.md](core.md) |
| `crdt_merge.strategies` | MergeSchema + 8 merge strategies | [strategies.md](strategies.md) |
| `crdt_merge.dataframe` | DataFrame merge + diff | [dataframe.md](dataframe.md) |
| `crdt_merge.dedup` | Exact, fuzzy, MinHash dedup | [dedup.md](dedup.md) |
| `crdt_merge.json_merge` | JSON/dict deep merge | [json_merge.md](json_merge.md) |

### Streaming & Sync
| Module | Description | Docs |
|--------|-------------|------|
| `crdt_merge.streaming` | Streaming merge pipelines | [streaming.md](streaming.md) |
| `crdt_merge.delta` | Delta-state sync | [delta.md](delta.md) |
| `crdt_merge.wire` | Binary wire protocol | [wire.md](wire.md) |

### Distributed Primitives
| Module | Description | Docs |
|--------|-------------|------|
| `crdt_merge.clocks` | HLC + Vector Clocks | [clocks.md](clocks.md) |
| `crdt_merge.gossip` | Gossip protocol | [gossip.md](gossip.md) |
| `crdt_merge.merkle` | Merkle trees | [merkle.md](merkle.md) |

### Engines & Performance
| Module | Description | Docs |
|--------|-------------|------|
| `crdt_merge.arrow` | Arrow merge engine | [arrow.md](arrow.md) |
| `crdt_merge._polars_engine` | Polars engine (38.8×) | [polars_engine.md](polars_engine.md) |
| `crdt_merge.async_merge` | Async merge | [async_merge.md](async_merge.md) |
| `crdt_merge.parallel` | Parallel merge | [parallel.md](parallel.md) |

### Data Formats
| Module | Description | Docs |
|--------|-------------|------|
| `crdt_merge.parquet` | Self-merging Parquet | [parquet.md](parquet.md) |
| `crdt_merge.datasets_ext` | HuggingFace Datasets | [datasets.md](datasets.md) |
| `crdt_merge.mergeql` | MergeQL SQL interface | [mergeql.md](mergeql.md) |

### Quality & Compliance
| Module | Description | Docs |
|--------|-------------|------|
| `crdt_merge.provenance` | Audit trails | [provenance.md](provenance.md) |
| `crdt_merge.verify` | CRDT law verification | [verify.md](verify.md) |
| `crdt_merge.probabilistic` | HLL, Bloom, CMS | [probabilistic.md](probabilistic.md) |
| `crdt_merge.schema_evolution` | Schema evolution | [schema_evolution.md](schema_evolution.md) |
| `crdt_merge.viz` | Conflict visualization | [viz.md](viz.md) |

### Model Merge (v0.8.0+)
| Module | Description | Docs |
|--------|-------------|------|
| `crdt_merge.model` | 26 strategies, LoRA, federated, GPU | [model.md](model.md) |

### Ecosystem Accelerators (v0.7.0+)
| Module | Description | Docs |
|--------|-------------|------|
| `crdt_merge.accelerators` | 8 accelerators | [accelerators.md](accelerators.md) |

### 🆕 v0.8.2 — The Adoption Release
| Module | Description | Docs |
|--------|-------------|------|
| `crdt_merge.context` | Context Memory System | [context.md](context.md) |
| `crdt_merge.agentic` | Agentic AI State Merge | [agentic.md](agentic.md) |
| `crdt_merge.cli` | CLI tools (MergeKit migration) | [cli.md](cli.md) |

---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
