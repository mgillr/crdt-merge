# Roadmap

## Released

| Version | Focus | Date |
|---|---|---|
| v0.7.x | Core CRDT primitives, merge strategies, MergeSchema, DataFrame engine | 2024 |
| v0.8.x | Streaming, Arrow, Parquet, Gossip, Merkle, Continual Merge, HF Hub | 2025 |
| v0.9.0 | Enterprise: UnmergeEngine, Audit, Encryption, RBAC, Observability | 2025 |
| v0.9.1 | Iron Dome: Pluggable crypto backends, 186 new tests | 2025 |
| v0.9.2 | Completion: Compliance, Observability Extensions, Flower FL Plugin | 2025 |
| v0.9.3 | Usability Enhancements: CLI hardening, docs refresh, packaging fix | 2026-04 |
| v0.9.4 | Documentation complete (20 guides), 4,498 tests passing, RBAC field-strip fix | 2026-04 |

---

## v1.0.0 (Target: Q3 2026)

### Planned
- [ ] Stable public API (no breaking changes after 1.0)
- [ ] Complete documentation for all modules
- [ ] 95%+ test coverage
- [ ] Performance benchmarks published
- [ ] Python 3.13 support verified

### Under Consideration
- [ ] Rust core for performance-critical paths
- [ ] WebAssembly support for browser usage
- [ ] gRPC transport in addition to Arrow Flight
- [ ] Vector database integration (Pinecone, Weaviate)
- [ ] LangChain/LlamaIndex integration
- [ ] Apache Iceberg support

## Beyond v1.0

- Multi-modal model merging (text + image + audio)
- Automatic strategy selection using ML
- Real-time collaborative merging (like Google Docs)
- Blockchain-backed audit trails
