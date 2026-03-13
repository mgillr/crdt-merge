# All Classes — Complete Listing

## Layer 1: Core CRDT Primitives (2,614 LOC)

### crdt_merge.core (320 LOC)
| Class | Constructor | Purpose |
|-------|------------|---------|
| `GCounter` | `(node_id=None, initial=0)` | Grow-only counter |
| `PNCounter` | `()` | Positive-negative counter |
| `LWWRegister` | `(value=None, timestamp=None, node_id="")` | Last-writer-wins register |
| `ORSet` | `()` | Observed-remove set |
| `LWWMap` | `()` | Last-writer-wins map |

### crdt_merge.strategies (377 LOC)
| Class | Constructor | Purpose |
|-------|------------|---------|
| `MergeStrategy` | *(abstract)* | Base strategy class |
| `LWW` | `()` | Last-writer-wins |
| `MaxWins` | `()` | Higher value wins |
| `MinWins` | `()` | Lower value wins |
| `UnionSet` | `(separator=",")` | Set union |
| `Priority` | `(levels: List[str])` | Ranked priority |
| `Concat` | `(separator=" | ", dedup=True)` | Concatenation |
| `LongestWins` | `()` | Longer string wins |
| `Custom` | `(fn: Callable)` | Custom function |
| `MergeSchema` | `(default=None, **field_strategies)` | Per-field schema |

### crdt_merge.clocks (324 LOC)
| Class | Constructor | Purpose |
|-------|------------|---------|
| `VectorClock` | `(clocks=None)` | Causal ordering |
| `DottedVersionVector` | `(clocks=None, dots=None)` | Fine-grained causality |

### crdt_merge.probabilistic (502 LOC)
| Class | Constructor | Purpose |
|-------|------------|---------|
| `MergeableHLL` | `(precision=14)` | HyperLogLog |
| `MergeableBloom` | `(capacity=10000, error_rate=0.01)` | Bloom filter |
| `MergeableCMS` | `(width=1000, depth=5)` | Count-Min Sketch |

### crdt_merge.dedup (260 LOC)
| Class | Constructor | Purpose |
|-------|------------|---------|
| `DedupIndex` | `(key: str)` | Hash-based dedup |
| `MinHashDedup` | `(num_perm=128, threshold=0.5)` | Approximate dedup |

### crdt_merge.provenance (383 LOC)
| Class | Constructor | Purpose |
|-------|------------|---------|
| `ProvenanceTracker` | `(source_a="a", source_b="b")` | Track merge provenance |
| `ProvenanceLog` | *(dataclass)* | Immutable provenance record |

### crdt_merge.verify (448 LOC)
| Class | Constructor | Purpose |
|-------|------------|---------|
| `CRDTVerifier` | `(num_tests=100, seed=None)` | Property-based verifier |
| `VerificationResult` | *(dataclass)* | Verification results |

## Layer 2: Merge Engines (3,984 LOC)

| Class | Module | Constructor |
|-------|--------|-------------|
| `StreamStats` | `streaming.py` | *(dataclass)* |
| `Arrow` | `arrow.py` | `(schema=None)` |
| `ArrowBatch` | `arrow.py` | `(batch_size=10000)` |
| `SelfMergingParquet` | `parquet.py` | `(path, key, schema=None)` |
| `ParquetMerge` | `parquet.py` | `(schema=None)` |
| `ParallelMerge` | `parallel.py` | `(num_workers=4, chunk_size=10000)` |
| `AsyncMerge` | `async_merge.py` | `(schema=None, executor=None)` |

## Layer 3: Sync & Transport (2,626 LOC)

| Class | Module | Constructor |
|-------|--------|-------------|
| `MerkleTree` | `merkle.py` | `(items=None, hash_fn="sha256")` |
| `GossipState` | `gossip.py` | `(node_id, seed_nodes=None)` |
| `DeltaStore` | `delta.py` | `(max_deltas=1000)` |

## Layer 4: AI / Model / Agent (18,410 LOC)

| Class | Module | Constructor |
|-------|--------|-------------|
| `ModelMerge` | `model/core.py` | `(strategy="linear", **kwargs)` |
| `ModelMergeSchema` | `model/core.py` | `(default_strategy="linear", **layer_strategies)` |
| `CRDTMergeState` | `model/crdt_state.py` | `(node_id: str)` |
| `LoRAMerge` | `model/lora.py` | `(strategy="linear", base_model=None)` |
| `ContinualMerge` | `model/continual.py` | `(strategy="ewc", importance_method="fisher")` |
| `FederatedMerge` | `model/federated.py` | `(strategy="fedavg")` |
| `GPUMerge` | `model/gpu.py` | `(device="cuda", dtype="float16")` |
| `MergePipeline` | `model/pipeline.py` | `()` |
| `SafetyAnalyzer` | `model/safety.py` | `(checks=None)` |
| `ConflictHeatmap` | `model/heatmap.py` | `()` |
| `AgentState` | `agentic.py` | `(agent_id: str)` |
| `SharedKnowledge` | `agentic.py` | `(namespace="default")` |
| `ContextMerge` | `context/merge.py` | `(strategy="semantic")` |
| `MemorySidecar` | `context/sidecar.py` | `(capacity=10000)` |
| `ContextConsolidator` | `context/consolidator.py` | `()` |
| `ContextBloom` | `context/bloom.py` | `(capacity=100000)` |
| `ContextManifest` | `context/manifest.py` | `()` |
| `HFMergeHub` | `hub/hf.py` | `(token=None)` |
| `AutoModelCard` | `hub/model_card.py` | `()` |
| `MergeQL` | `mergeql.py` | `()` |
| `ConflictTopology` | `viz.py` | `()` |

## Layer 5: Enterprise Wrappers (3,323 LOC)

| Class | Module | Constructor |
|-------|--------|-------------|
| `AuditLog` | `audit.py` | `(path=None)` |
| `AuditEntry` | `audit.py` | *(dataclass)* |
| `AuditedMerge` | `audit.py` | `(audit_log, user)` |
| `EncryptedMerge` | `encryption.py` | `(backend="fernet", key=None)` |
| `RBACController` | `rbac.py` | `()` |
| `SecureMerge` | `rbac.py` | `(rbac, user)` |
| `MetricsCollector` | `observability.py` | `()` |
| `ObservedMerge` | `observability.py` | `(collector)` |
| `PrometheusExporter` | `observability.py` | `(collector, port=9090)` |
| `GrafanaDashboard` | `observability.py` | `()` |
| `MergeTracer` | `observability.py` | `(service_name="crdt-merge")` |
| `DriftDetector` | `observability.py` | `(baseline=None)` |
| `HealthCheck` | `observability.py` | `()` |
| `UnmergeEngine` | `unmerge.py` | `(audit_log)` |
| `ModelUnmerge` | `unmerge.py` | `()` |
| `GDPRForget` | `unmerge.py` | `(audit_log)` |

## Layer 6: Verification & Compliance (932 LOC)

| Class | Module | Constructor |
|-------|--------|-------------|
| `ComplianceAuditor` | `compliance.py` | `(regulations=None)` |
| `EUAIActReport` | `compliance.py` | `(risk_level="high")` |
