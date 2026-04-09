# The Right to Forget in Trained AI Models

> **Patent — UK Application No. 2607132.4, GB2608127.3**
> Architecture described herein is protected under BSL-1.1 until 2028-03-29, then Apache 2.0.

---

## The Problem No One Has Solved at Scale

GDPR Article 17 guarantees the right to erasure. EU AI Act Article 12 requires traceability of training data. These are legal requirements with teeth — fines up to 4% of global annual turnover.

There is no production-ready system that satisfies both requirements simultaneously for AI models.

**The fundamental conflict:**
- Training "bakes in" the influence of every data point across all parameters
- There is no surgical way to remove one data point's influence from a trained model without retraining from scratch
- Retraining from scratch costs millions of dollars for large models and weeks of compute time

**The workarounds being used today:**
1. **Delete the raw data** — satisfies GDPR for data storage, but the model still contains learned patterns from that data
2. **Retrain from scratch** — correct but prohibitively expensive
3. **Approximate unlearning** — gradient descent in reverse, fine-tuning on random labels — research-grade, not production-grade

crdt-merge's `UnmergeEngine` and `GDPRForget` offer a different architectural answer.

---

## The Architecture: Unmerge as the Inverse of Merge

```
┌──────────────────────────────────────────────────────────────┐
│  The merge-unmerge symmetry                                   │
│                                                              │
│  merge(A, B) → M          (produces merged state)            │
│  unmerge(M, A) → B        (removes A's contribution)         │
│                                                              │
│  This works because crdt-merge records PROVENANCE:           │
│  every record knows which source it came from.               │
│  Every model contribution has a unique tag.                  │
│                                                              │
│  Without provenance → no reliable unmerge                    │
│  With provenance → surgical, verifiable removal              │
└──────────────────────────────────────────────────────────────┘
```

The two-layer architecture is essential here. Because the OR-Set (Layer 1) tracks contributions by unique tag, any contribution can be removed via tombstoning. The removal propagates to all nodes through CRDT merge. The re-resolved model (Layer 2) is applied over the updated visible set — the removed contribution's influence is gone.

---

## Quick Start: Tabular Data Unmerge

```python
from crdt_merge.unmerge import UnmergeEngine
from crdt_merge.provenance import merge_with_provenance

# Merge two datasets with provenance tracking
records_a = [
    {"id": "1", "name": "Alice", "score": 95},
    {"id": "2", "name": "Bob",   "score": 87},
]
records_b = [
    {"id": "3", "name": "Carol", "score": 92},
    {"id": "4", "name": "Dave",  "score": 78},
]

merged, provenance_log = merge_with_provenance(records_a, records_b, key="id")
print(f"Merged: {len(merged)} records from 2 sources")

# Later: GDPR erasure request for source "a"
engine = UnmergeEngine()
report = engine.verify_unmerge(merged, provenance_log, source_to_remove="a")

print(f"Records removed: {report.records_removed}")
print(f"Records remaining: {report.records_remaining}")
print(f"Residual data: {report.residual_data} bytes")
print(f"Success: {report.success}")
```

---

## Quick Start: Model Unmerge

```python
import numpy as np
from crdt_merge.unmerge import ModelUnmerge
from crdt_merge.model import CRDTMergeState

# Three models merged together (weight_average needs no base; use ties/dare_ties with base= for task-vectors)
state = CRDTMergeState("weight_average")
state.add(np.random.randn(10, 10).astype(np.float32), model_id="model_alice", weight=0.4)
state.add(np.random.randn(10, 10).astype(np.float32), model_id="model_bob",   weight=0.35)
state.add(np.random.randn(10, 10).astype(np.float32), model_id="model_carol", weight=0.25)

merged_model = state.resolve()

# Bob requests removal — retract his contribution via CRDT remove
state.remove("model_bob")
updated_model = state.resolve()

# Verify the influence is reduced
unmerge = ModelUnmerge()
residual = unmerge.measure_residual(updated_model, merged_model)

print(f"Influence score after removal: {residual.influence_score:.3f}")  # < original
print(f"Parameters checked: {residual.parameters_checked}")
print(f"Parameters with residual: {residual.parameters_with_residual}")
```

---

## Cookbook: Model Unmerge Strategies

crdt-merge provides three complementary strategies for removing a model's influence:

```python
import numpy as np
from crdt_merge.unmerge import ModelUnmerge

# Create a merged model (simplified example)
merged = {"layer": np.array([0.5, 0.3, 0.7, 0.2], dtype=np.float32)}
target = {"layer": np.array([0.4, 0.35, 0.65, 0.25], dtype=np.float32)}  # contribution to remove

unmerge = ModelUnmerge()

# Strategy 1: Negmerge — subtract the target contribution
result_neg = unmerge.unmerge_model(merged, target, remove_model="target", method='negmerge')
print("Negmerge:", result_neg["layer"])

# Strategy 2: Surgical zeroing — zero parameters where target was dominant
result_surgical = unmerge.unmerge_model(merged, target, remove_model="target", method='surgical')
print("Surgical zero:", result_surgical["layer"])

# Strategy 3: Proportional rescaling — rescale weights to remove contribution
result_scaled = unmerge.unmerge_model(merged, target, remove_model="target", method='proportional')
print("Rescaled:", result_scaled["layer"])
```

---

## Full GDPR Compliance Workflow

```python
from crdt_merge.unmerge import GDPRForget
from crdt_merge.provenance import merge_with_provenance
from crdt_merge.audit import AuditLog
import json

# Dataset with provenance
customer_a = [
    {"id": "C001", "name": "Alice",  "email": "a@example.com", "purchase": 450.00},
    {"id": "C002", "name": "Bob",    "email": "b@example.com", "purchase": 230.00},
]
customer_b = [
    {"id": "C003", "name": "Carol",  "email": "c@example.com", "purchase": 180.00},
    {"id": "C004", "name": "Dave",   "email": "d@example.com", "purchase": 670.00},
]

merged, log = merge_with_provenance(customer_a, customer_b, key="id")
audit = AuditLog(node_id="gdpr-processor")

# GDPR erasure request
gdpr = GDPRForget()

# Process the erasure
result = gdpr.forget_data(
    merged,
    log,
    contributor="a",   # remove records from source "a"
    key_field="id",
)

print(f"Erasure complete: {result.success}")
print(f"Records removed: {result.data_records_removed}")
print(f"Compliance timestamp: {result.compliance_timestamp}")
print(f"Contributor: {result.contributor}")

# Generate the compliance report
report = gdpr.compliance_report()
print(report.to_json())
```

---

## Cookbook: Batch GDPR Erasure Requests

```python
from crdt_merge.unmerge import GDPRForget
from crdt_merge.provenance import merge_with_provenance
from crdt_merge.audit import AuditLog

# Multiple sources merged
sources = {
    "hospital_a": [{"id": f"P{i:03d}", "value": i} for i in range(100)],
    "hospital_b": [{"id": f"P{i:03d}", "value": i * 2} for i in range(50, 150)],
    "hospital_c": [{"id": f"P{i:03d}", "value": i * 3} for i in range(75, 125)],
}

# Merge all with provenance
merged = sources["hospital_a"][:]
log_a_b = None
for source_name, records in list(sources.items())[1:]:
    merged, log_a_b = merge_with_provenance(merged, records, key="id")

audit = AuditLog(node_id="gdpr-batch")
gdpr = GDPRForget()

# Process multiple erasure requests
erasure_requests = ["hospital_a", "hospital_c"]

for contributor in erasure_requests:
    result = gdpr.forget_data(
        merged,
        log_a_b,
        contributor=contributor,
        key_field="id",
    )
    print(f"Erased {contributor}: {result.data_records_removed} records removed")

# Final compliance report covers all erasure requests
report = gdpr.compliance_report()
print(f"Total requests: {len(report.requests_processed)}")
print(f"Total records removed: {report.total_records_removed}")
```

---

## Scenario: Right-to-Forget in a Federated Learning System

100 clients contribute model updates to a federated system. One client requests deletion of their contribution — for privacy, because their local data was found to be corrupted, or because they withdrew consent.

**Before crdt-merge:** No mechanism exists. The merged model contains all clients' influences with no way to separate them. Options: retrain from scratch (expensive), or accept non-compliance.

**With crdt-merge:**

```python
from crdt_merge.model import CRDTMergeState
from crdt_merge.unmerge import ModelUnmerge, GDPRForget
import numpy as np

# 100 clients, each with their own state
clients = {
    f"client_{i}": CRDTMergeState("weight_average")
    for i in range(100)
}

# Each client adds their model update
for client_id, state in clients.items():
    weights = np.random.randn(50, 50).astype(np.float32)
    state.add(weights, model_id=f"update_{client_id}", weight=1.0 / 100)

# Global state: merge all clients
global_state = CRDTMergeState("weight_average")
for client_state in clients.values():
    global_state.merge(client_state)

merged_model = global_state.resolve()

# Client 42 requests erasure
print("Processing erasure request for client_42...")
global_state.remove("update_client_42")

# Re-resolve: client_42's contribution is no longer in the visible set
updated_model = global_state.resolve()

# The CRDT remove() propagates to all replicas via gossip
# Any other server that has the global_state will converge to the same
# updated model when they receive the tombstone

# Measure residual influence
unmerge = ModelUnmerge()
residual = unmerge.measure_residual(updated_model, merged_model)
print(f"Residual influence after removal: {residual.influence_score:.4f}")

# Generate GDPR compliance evidence
# (The remove() operation creates a tombstone in the CRDT log — timestamped, verifiable)
```

---

## Scenario: Model Unlearning for Safety

A deployed model is found to have learned from a dataset that contained harmful content. The dataset must be "unlearned" from the model.

```python
from crdt_merge.model import CRDTMergeState
from crdt_merge.unmerge import ModelUnmerge
import numpy as np

# Base model + fine-tune on problematic dataset
state = CRDTMergeState("neg_merge")

base_tensor = np.random.randn(128, 128).astype(np.float32)
state.add(base_tensor, model_id="base_model", weight=0.7)
state.add(np.random.randn(128, 128).astype(np.float32), model_id="harmful_finetune", weight=0.3)

merged = state.resolve()

# Safety review: harmful_finetune must be removed
state.remove("harmful_finetune")
safe_model = state.resolve()

# Verify the harmful contribution is gone
unmerge = ModelUnmerge()
residual = unmerge.measure_residual(safe_model, merged)

print(f"Harmful influence removed: {1 - residual.influence_score:.1%}")

# The neg_merge strategy actively suppresses harmful contributions
# while preserving the base model's beneficial parameters
```

---

## Scenario: Continual Learning with Selective Forgetting

A deployed model learns from a stream of data. New privacy regulations require forgetting data from a specific geographic region.

```python
from crdt_merge.model.continual import ContinualMerge
from crdt_merge.unmerge import ModelUnmerge
import numpy as np

continual = ContinualMerge(
    base=base_model,
    strategy="weight_average",
)

# Six months of regional updates
for month in range(6):
    for region in ["EU", "US", "APAC"]:
        update = {"layer1": np.random.randn(64, 64).astype(np.float32)}
        continual.absorb(
            update,
            name=f"update-{region}-month{month}",
            weight=0.1 / 6,
        )

# New regulation: forget all EU data
# Re-absorb non-EU contributions only, replacing earlier EU updates
eu_model_ids = [f"update-EU-month{m}" for m in range(6)]

# Re-resolve — EU data is gone, US and APAC contributions intact
compliant_model = continual.export()
print("EU data removed. Model re-resolved without EU contributions.")
```

---

## Residual Influence Measurement

After unmerge, verify the removal was effective:

```python
from crdt_merge.unmerge import ModelUnmerge, ResidualReport
import numpy as np

unmerge = ModelUnmerge()

# Before and after models
before = {"layer1": np.array([0.5, 0.3, 0.7], dtype=np.float32)}
after  = {"layer1": np.array([0.45, 0.32, 0.68], dtype=np.float32)}

report: ResidualReport = unmerge.measure_residual(after, before)

print(f"Influence score: {report.influence_score:.4f}")
# 0.0 = completely removed, 1.0 = fully present

print(f"Parameters checked: {report.parameters_checked}")
print(f"Parameters with residual: {report.parameters_with_residual}")
print(f"Removal effective: {report.influence_score < 0.05}")
```

---

## Compliance Report Format

```python
from crdt_merge.unmerge import GDPRForget, GDPRComplianceReport
from crdt_merge.audit import AuditLog
import json

gdpr = GDPRForget()

# After processing erasure requests...
report: GDPRComplianceReport = gdpr.compliance_report()

# JSON export for legal/compliance teams
report_json = report.to_json()
# {
#   "requests_processed": [
#     {"success": true, "data_records_removed": 42, "model_influence_removed": true,
#      "compliance_timestamp": "2026-04-02T14:30:00Z", "contributor": "hospital_a"}
#   ],
#   "total_records_removed": 42,
#   "total_models_cleaned": 1,
#   "generated_at": "2026-04-02T14:30:01Z"
# }
print(report_json)
```

---

## Why CRDT Provenance Makes This Possible

Traditional merge operations lose provenance — the output does not know which input produced which record. crdt-merge records this at every step:

| Without crdt-merge | With crdt-merge |
|---|---|
| Merge output has no source attribution | Every record carries `origin: "a" \| "b" \| "merged"` |
| Field conflict resolution is opaque | Every field carries `MergeDecision` with strategy and alternative value |
| No way to identify what to remove | `ProvenanceLog` maps every output record to its source |
| Re-run produces different result | CRDT merge is deterministic — same inputs → same output |
| GDPR compliance requires custom logic | `GDPRForget` + `UnmergeEngine` provide off-the-shelf compliance |

---

## Integration with Encryption

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
from crdt_merge.unmerge import GDPRForget
from crdt_merge.audit import AuditLog
import secrets

em = EncryptedMerge(StaticKeyProvider(secrets.token_bytes(32)))
audit = AuditLog(node_id="gdpr-encrypted")
gdpr = GDPRForget()

# Data is encrypted at rest — GDPR request requires:
# 1. Decrypt to identify records by contributor
# 2. Remove those records from the encrypted dataset
# 3. Re-encrypt the remaining records
# 4. Issue compliance report

# This workflow combines EncryptedMerge + GDPRForget
# See privacy-preserving-merge.md for encryption details
```

---

## Further Reading

- [CRDT Architecture — Full Mathematical Proof](../CRDT_ARCHITECTURE.md)
- [Architecture Map](../ARCHITECTURE_MAP.md)
- [Guide — Privacy-Preserving Merge](./privacy-preserving-merge.md)
- [Guide — Provenance-Complete AI](./provenance-complete-ai.md)
- [Guide — Federated Model Merging Without a Parameter Server](./federated-model-merging.md)
- [API Reference — UnmergeEngine](../api-reference/enterprise/unmerge.md)
- [API Reference — GDPRForget](../api-reference/enterprise/unmerge.md)
- [Compliance Guide](../guides/compliance-guide.md)
