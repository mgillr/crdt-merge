# Data Flow — Through the System

## Basic Merge Flow

```
Input Data (2 DataFrames)
         │
         ▼
┌────────────────────┐
│ merge() [Layer 2]  │
│  dataframe.py      │
│                    │
│  1. Identify keys  │
│  2. Match rows     │
│  3. For conflicts: │
│     ┌──────────────┤
│     │ MergeSchema  │
│     │ [Layer 1]    │
│     │              │
│     │ strategy_for │
│     │ (field) →    │
│     │ resolve()    │
│     └──────────────┤
│  4. Return merged  │
│     DataFrame      │
└────────┬───────────┘
         │
         ▼
Merged DataFrame (output)
```

## Streaming Merge Flow

```
Stream A ──┐
           ├──► merge_stream() [Layer 2]
Stream B ──┘        │
                    │  For each pair of records:
                    │  ┌─► MergeSchema.resolve_row()
                    │  │   (per-field strategy resolution)
                    │  └─► yield merged record
                    │
                    ▼
             Merged Stream
```

## Distributed Sync Flow

```
Node A                          Node B
  │                               │
  ├── GossipState ◄──────────────►├── GossipState
  │   [Layer 3]                   │   [Layer 3]
  │                               │
  │   1. Exchange digests         │
  │   2. Identify differences     │
  │      (via MerkleTree)         │
  │   3. compute_delta()          │
  │   4. serialize() via wire     │
  │   5. Transmit                 │
  │   6. deserialize()            │
  │   7. apply_delta()            │
  │   8. Merge locally            │
  │                               │
  └── Converged State ◄──────────►└── Converged State
```

## Model Merge Flow

```
Model A (weights)  Model B (weights)
        │                  │
        └────────┬─────────┘
                 │
      ┌──────────▼──────────┐
      │ ModelMerge [Layer 4] │
      │                      │
      │ 1. Load weights      │
      │ 2. Select strategy   │
      │    (26+ available)   │
      │ 3. Per-layer merge   │
      │ 4. Safety check      │
      │    (SafetyAnalyzer)  │
      │ 5. Validate output   │
      └──────────┬──────────┘
                 │
          Merged Model
```

## Enterprise Wrapper Flow

```
merge() call
     │
     ▼
┌─────────────────┐
│ SecureMerge      │  ← RBAC check (Layer 5)
│ [rbac.py]        │
└────────┬────────┘
         │ (if authorized)
         ▼
┌─────────────────┐
│ AuditedMerge     │  ← Audit trail (Layer 5)
│ [audit.py]       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ EncryptedMerge   │  ← Encryption (Layer 5)
│ [encryption.py]  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ObservedMerge    │  ← Metrics (Layer 5)
│ [observability]  │
└────────┬────────┘
         │
         ▼
   Core merge()
   [Layer 2/1]
```

---

*Data Flow v1.0*
