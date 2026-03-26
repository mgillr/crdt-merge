# Data Flow — Through the System

How data moves through the six layers for each major operation.

---

## Basic DataFrame Merge Flow

```
Input: Two DataFrames (pandas, polars, or Arrow)
         │
         ┌────────────────────────────────┐
│ merge() [Layer 2: dataframe.py]│
│                                │
│  1. Detect engine              │
│     (pandas / polars / arrow)  │
│  2. Align on key column(s)     │
│  3. For rows in both frames:   │
│     ┌──────────────────────────┤
│     │ MergeSchema [Layer 1]    │
│     │                          │
│     │ For each column:         │
│     │   strategy_for(col)      │
│     │   → LWW / MaxWins /      │
│     │     UnionSet / Priority  │
│     │   → resolve(val_a, val_b,│
│     │       ts_a, ts_b)        │
│     └──────────────────────────┤
│  4. Rows unique to df_a: kept  │
│  5. Rows unique to df_b: kept  │
│  6. Return merged DataFrame    │
└────────────────────────────────┘
         │
         Output: Merged DataFrame (same engine as input)
```

**Code**:
```python
from crdt_merge import merge
from crdt_merge.strategies import MergeSchema, LWW, MaxWins

schema = MergeSchema(default=LWW(), score=MaxWins())
result = merge(df_a, df_b, key="id", schema=schema, timestamp_col="updated_at")
```

---

## Streaming Merge Flow

```
Stream A ──┐
           ├──merge_stream() [Layer 2: streaming.py]
Stream B ──┘         │
                     │  For each record pair (matched by key):
                     │  ┌─MergeSchema.resolve_row()
                     │  │   (Layer 1 — per-field strategy)
                     │  └─yield merged_record
                     │
                                   Merged Record Stream (generator)
```

**Code**:
```python
from crdt_merge.streaming import merge_stream
from crdt_merge.strategies import MergeSchema, LWW

schema = MergeSchema(default=LWW())
for merged_record in merge_stream(stream_a, stream_b, key="id", schema=schema):
    output_sink.write(merged_record)
```

For pre-sorted streams (optimal O(n+m) performance):
```python
from crdt_merge.streaming import merge_sorted_stream
for merged_record in merge_sorted_stream(sorted_a, sorted_b, key="id", schema=schema):
    output_sink.write(merged_record)
```

---

## Parallel Merge Flow

```
Large DataFrame A ──┐
Large DataFrame B ──┘
         │
         (if total rows > 10,000)
┌────────────────────────────────────┐
│ parallel_merge() [Layer 2]         │
│                                    │
│  1. Partition keys into N chunks   │
│     (key-aligned — all rows for    │
│      a given key → same chunk)     │
│                                    │
│  2. ThreadPoolExecutor:            │
│     chunk_1_a + chunk_1_b → merge  │
│     chunk_2_a + chunk_2_b → merge  │
│     ...                            │
│     (up to max_workers threads)    │
│                                    │
│  3. Concatenate chunk results      │
└────────────────────────────────────┘
         │
         Output: Merged DataFrame
```

**Code**:
```python
from crdt_merge.parallel import parallel_merge

result = parallel_merge(
    df_a, df_b,
    key="id",
    schema=schema,
    max_workers=8,
    chunk_size=50_000,
)
```

Note: Falls back to sequential `merge()` for datasets under 10,000 rows.

---

## Distributed Sync Flow (Gossip Protocol)

```
Node A                           Node B
  │                                │
  ├── GossipState [Layer 3]  ───├── GossipState [Layer 3]
  │   gossip.py                    │   gossip.py
  │                                │
  │   Round 1:                     │
  │   1. Compute MerkleTree digest │
  │   2. Send digest to peer       │
  │   3. Peer identifies diff      │
  │   4. compute_delta() [delta.py]│
  │   5. serialize() [wire.py]     │
  │   6. Transmit binary payload   │
  │   7. deserialize()             │
  │   8. apply_delta()             │
  │   9. merge() locally           │
  │                                │
  └── Converged State ──────────└── Converged State
```

**Code**:
```python
from crdt_merge.gossip import GossipState

node_a = GossipState(node_id="node_a")
node_b = GossipState(node_id="node_b")

node_a.update("user:alice", {"name": "Alice", "score": 90})
node_b.update("user:bob",   {"name": "Bob",   "score": 85})

# Exchange state (simulate network round-trip)
state_b_serialized = node_b.serialize()
node_a.merge_remote(state_b_serialized)

# Both nodes now have user:alice and user:bob
```

---

## Model Merge Flow (Layer 4)

```
Model A (state_dict / weights)
Model B (state_dict / weights)
        │
        ┌──────────────────────────────────┐
│ CRDTMergeState [Layer 4]         │
│ model/crdt_state.py              │
│                                  │
│  1. add_contribution(model, id)  │
│     → ORSet tag assigned         │
│     → merkle_hash computed       │
│                                  │
│  2. merge(other_state)           │
│     → OR-Set union of all contribs│
│     → state_hash updated         │
│                                  │
│  3. export(strategy="weight_avg")│
│     → ModelMerge [model/core.py] │
│     → Select per-layer strategy  │
│     → Merge weight tensors       │
│     → SafetyAnalyzer check       │
│     → Return merged state_dict   │
└──────────────────────────────────┘
         │
         Merged Model (state_dict or HF model)
```

**Code**:
```python
from crdt_merge.model.crdt_state import CRDTMergeState

state = CRDTMergeState(strategy="weight_average")
state.add_contribution(model_a, model_id="hospital_a")
state.add_contribution(model_b, model_id="hospital_b")

# Merge with remote state (from another federation node)
merged = state.merge(remote_state)

print(state.state_hash)     # SHA-256 Merkle root of all contributions
merged_weights = state.export()
```

---

## Enterprise Wrapper Flow (Layer 5)

Each enterprise feature is a wrapper that decorates the core merge call:

```
User calls: am.merge(df_a, df_b, key="id")
                 │
                 ┌──────────────────────────────┐
│ AuditedMerge [audit.py]      │
│                              │
│  1. Hash inputs              │
│  2. Call inner merge()       │ ←── core merge() [Layer 2]
│  3. Hash output              │
│  4. Append to audit chain    │
│  5. Return (result, entry)   │
└──────────────────────────────┘
```

**Stacking wrappers** (recommended order):
```
SecureMerge (RBAC check)
    └─AuditedMerge (record in audit chain)
            └─EncryptedMerge (field encryption/decryption)
                    └─ObservedMerge (metrics/tracing)
                            └─core merge() [Layer 2]
```

**Code**:
```python
from crdt_merge.rbac import SecureMerge, RBACController, Policy, MERGER
from crdt_merge.audit import AuditLog, AuditedMerge

rbac = RBACController()
rbac.add_policy(Policy(role=MERGER, denied_fields={"ssn"}))
audit = AuditLog(node_id="node1")

# Create stacked wrapper
secure = SecureMerge(rbac=rbac, role=MERGER)
audited = AuditedMerge(audit_log=audit)

result, entry = audited.merge(df_a, df_b, key="id")
assert audit.verify_chain()   # tamper-evident verification
```

---

## Compliance Validation Flow (Layer 6)

```
Production merge system
         │
         │  ComplianceAuditor.record_merge()
         ┌──────────────────────────────────────┐
│ ComplianceAuditor [Layer 6]          │
│ compliance.py                        │
│                                      │
│  Reads Layer 5 audit chain           │
│  Reads RBAC configuration            │
│  Reads encryption configuration      │
│                                      │
│  .validate() runs rule set:          │
│  ┌─ GDPR: data minimisation check   │
│  ├─ GDPR: storage limitation check  │
│  ├─ HIPAA: PHI field scan           │
│  ├─ SOX: audit chain integrity      │
│  └─ EU AI Act: risk classification  │
│                                      │
│  → ComplianceReport                  │
│     .passed: bool                    │
│     .findings: List[ComplianceFinding]│
│     .to_text() / .to_dict()          │
│     .sign(key) / .verify(key, sig)   │
└──────────────────────────────────────┘
         │
         ComplianceReport (signed or unsigned)
```

**Code**:
```python
from crdt_merge.compliance import ComplianceAuditor
from crdt_merge.audit import AuditLog
import secrets

audit = AuditLog(node_id="prod")
auditor = ComplianceAuditor(framework="gdpr", audit_log=audit)
auditor.record_merge("merge-001", input_hash="abc", output_hash="def")

report = auditor.validate()
key = secrets.token_bytes(32)
sig = report.sign(key)
assert report.verify(key, sig)
print(report.to_text())
```

---

*Data Flow v1.1 — updated for v0.9.4*
