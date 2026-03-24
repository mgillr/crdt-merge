# In-Depth Guides

25 guides covering every major use case. Every code example is verified by an automated test suite (309 tests, all passing).

---

## Data & Records

| Guide | What it covers |
|---|---|
| [CRDT Fundamentals](crdt-fundamentals.md) | CRDT theory, OR-Set, LWW-Register, G-Counter, convergence proofs |
| [CRDT Primitives Reference](crdt-primitives-reference.md) | Working examples for every primitive: OR-Set, VectorClock, DottedVersionVector, dedup |
| [CRDT Verification Toolkit](crdt-verification-toolkit.md) | `verify_crdt`, `verify_commutative`, property-based testing, custom `eq_fn` |
| [Merge Strategies](merge-strategies.md) | LWW, MaxWins, MinWins, UnionSet, Concat, Priority, Custom — complete reference |
| [Schema Evolution](schema-evolution.md) | Backwards-compatible schema changes, field additions, type migrations |
| [MergeQL — Distributed Knowledge](mergeql-distributed-knowledge.md) | SQL-like `MERGE … ON … STRATEGY` interface, custom strategy registration |
| [Probabilistic CRDT Analytics](probabilistic-crdt-analytics.md) | HyperLogLog cardinality, MinHash dedup, Count-Min Sketch frequency |
| [Performance Tuning](performance-tuning.md) | `parallel_merge(max_workers=)`, chunking, DuckDB acceleration, profiling |
| [Troubleshooting](troubleshooting.md) | Common errors, strategy mismatches, schema conflicts, serialisation issues |

---

## Transport & Sync

| Guide | What it covers |
|---|---|
| [Wire Protocol](wire-protocol.md) | Binary format, `serialize`/`deserialize`, `peek_type`, `wire_size` |
| [Gossip & Serverless Sync](gossip-serverless-sync.md) | `GossipState`, peer-to-peer propagation, serverless deployment patterns |
| [Delta Sync & Merkle Verification](delta-sync-merkle-verification.md) | Bandwidth-efficient sync, `MerkleTree` content integrity |

---

## AI & ML Models

| Guide | What it covers |
|---|---|
| [Federated Model Merging](federated-model-merging.md) | `CRDTMergeState`, 26 strategies, no-parameter-server federation |
| [Model Merge Strategies](model-merge-strategies.md) | SLERP, TIES, DARE, DARE-TIES, Fisher, task arithmetic — full reference |
| [Model CRDT Matrix](model-crdt-matrix.md) | Strategy × CRDT-compliance comparison table |
| [LoRA Adapter Merging](lora-adapter-merging.md) | `LoRAMerge`, `LoRAMergeSchema`, per-layer strategy assignment |
| [Continual Learning Without Forgetting](continual-learning-without-forgetting.md) | `ContinualMerge`, `absorb`/`export`, stability measurement |

---

## Agentic & Context Memory

| Guide | What it covers |
|---|---|
| [Convergent Multi-Agent AI](convergent-multi-agent-ai.md) | `AgentState`, `ContextMerge`, `ContextManifest`, multi-agent convergence |
| [Agentic Memory at Scale](agentic-memory-at-scale.md) | `ContextBloom` O(1) dedup, `MemorySidecar` TTL filtering, budget-bounded merge |

---

## Privacy, Security & Compliance

| Guide | What it covers |
|---|---|
| [Security Guide](security-guide.md) | Encryption backends, `StaticKeyProvider`, `EncryptedMerge`, RBAC policies |
| [Security Hardening](security-hardening.md) | Production checklist, key rotation, threat model, backend selection |
| [Privacy-Preserving Merge](privacy-preserving-merge.md) | Field-level encryption cookbook, order-preserving tags, multi-party scenarios |
| [Provenance — Complete AI](provenance-complete-ai.md) | `AuditLog`, `AuditedMerge`, tamper-evident chain, lineage queries |
| [Right to Forget in AI](right-to-forget-in-ai.md) | CRDT `remove()`, GDPR Art.17 erasure, `GDPRForget`, model unmerge |
| [Compliance Guide](compliance-guide.md) | **GDPR, HIPAA, SOX, EU AI Act** — `ComplianceAuditor`, `EUAIActReport`, signed reports |
