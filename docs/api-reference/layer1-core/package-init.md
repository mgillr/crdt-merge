# `crdt_merge/__init__.py`

> crdt-merge: Conflict-free merge, dedup and sync for DataFrames, JSON and datasets.

Usage:
    from crdt_merge import merge, dedup, diff

    # Merge two DataFrames (pandas, polars, or dicts)
    merged = merge(df_a, df_b, key="id")

    # Composable per-column strategies (NEW in v0.3.0)
    from cr

**Source:** `crdt_merge/__init__.py` | **Lines:** 247

---

**Exports (`__all__`):** `['GCounter', 'PNCounter', 'LWWRegister', 'ORSet', 'LWWMap', 'merge', 'diff', 'dedup', 'dedup_records', 'DedupIndex', 'MinHashDedup', 'merge_dicts', 'merge_json_lines', 'MergeStrategy', 'LWW', 'MaxWins', 'MinWins', 'UnionSet', 'Priority', 'Concat', 'Custom', 'LongestWins', 'MergeSchema', 'merge_stream', 'merge_sorted_stream', 'StreamStats', 'merge_datasets', 'dedup_dataset', 'merge_with_provenance', 'MergeDecision', 'MergeRecord', 'ProvenanceLog', 'export_provenance', 'verified_merge', 'CRDTVerificationError', 'serialize', 'deserialize', 'peek_type', 'wire_size', 'serialize_batch', 'deserialize_batch', 'WireError', 'MergeableHLL', 'MergeableBloom', 'MergeableCMS', 'VectorClock', 'DottedVersionVector', 'Ordering', 'evolve_schema', 'check_compatibility', 'widen_type', 'SchemaPolicy', 'SchemaChange', 'SchemaEvolutionResult', 'MerkleTree', 'MerkleNode', 'MerkleDiff', 'merkle_diff', 'GossipState', 'GossipEntry', 'anti_entropy', 'ArrowMerge', 'arrow_merge', 'amerge', 'amerge_stream', 'amerge_sorted_stream', 'parallel_merge', 'parallel_merge_arrow', 'MergeQL', 'MergeAST', 'MergePlan', 'MergeQLResult', 'MergeQLSyntaxError', 'MergeQLValidationError', 'MergeQLError', 'MergeQLParser', 'MemorySidecar', 'ContextManifest', 'ContextBloom', 'ContextConsolidator', 'ConsolidatedBlock', 'MemoryChunk', 'ContextMerge', 'MergeResult', 'AgentState', 'SharedKnowledge', 'Fact', 'UnmergeEngine', 'ModelUnmerge', 'GDPRForget', 'AuditLog', 'AuditEntry', 'AuditedMerge', 'EncryptedMerge', 'EncryptedValue', 'StaticKeyProvider', 'KeyProvider', 'RBACController', 'SecureMerge', 'Permission', 'Role', 'Policy', 'AccessContext', 'MetricsCollector', 'ObservedMerge', 'MergeMetric', 'HealthCheck', 'MergeTracer', 'DriftDetector', 'DriftReport', 'PrometheusExporter', 'GrafanaDashboard', 'ComplianceAuditor', 'ComplianceReport', 'ComplianceFinding', 'EUAIActReport', 'CRDTStrategy', 'FlowerCRDTClient', 'FlowerAggregator', 'HAS_POLARS']`

## Functions

### `merge_datasets(*args, **kwargs)`

Merge two HuggingFace Datasets. Requires: pip install crdt-merge[datasets]

### `dedup_dataset(*args, **kwargs)`

Deduplicate a HuggingFace Dataset. Requires: pip install crdt-merge[datasets]

### `_load_accelerators()`

Lazy loader for the accelerators sub-package.

### `_load_model()`

Lazy loader for the model-merge sub-package.


---

## RREA Priority Analysis

`__init__.py` is the **package facade** — it imports from ALL layers to provide a flat namespace. The 19 "layer violations" detected by GDEPA are **expected behavior** for a facade module, not architectural bugs.

| Symbol | Classification | Notes |
|--------|---------------|-------|
| `merge_datasets` | SPECIALIZED | HuggingFace integration, line 151 |
| `dedup_dataset` | SPECIALIZED | HuggingFace integration, line 156 |
| `_load_accelerators` | SHADOW | Lazy loader, line 204 |
| `_load_model` | SHADOW | Lazy loader, line 210 |

**Module Stats:** 132 AST LOC, 248 total lines, 4 functions, 0 classes, 106 `__all__` exports.
