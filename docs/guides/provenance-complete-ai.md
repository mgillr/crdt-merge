# Provenance-Complete AI: Full Lineage from Data to Decision

> **Patent Pending — UK Application No. 2607132.4**
> Architecture described herein is protected under BSL-1.1 until 2028-03-29, then Apache 2.0.

---

## The Lineage Gap in Every AI System Today

An AI system makes a decision. You need to know: **why?**

Not the model's output token probabilities. Not the training loss curve. The actual causal chain:
- Which data sources contributed to the training?
- When two sources conflicted on a fact, which won and why?
- Which agents contributed which pieces of knowledge?
- What was each contributor's confidence level at the time?
- Has any of the underlying data been modified or retracted since?

**No production AI system today can answer all of these questions.** Logs exist. Metadata exists. But the connection between a specific AI decision and the specific data that caused it — with full causal lineage, conflict resolution records, and cryptographic integrity proof — does not.

EU AI Act Article 13 requires transparency. Article 12 requires logging. GDPR Article 5(1)(e) requires data minimisation with audit trails. These are not soft recommendations — they are legal obligations with significant penalties.

crdt-merge's provenance and audit system provides **mathematically verifiable lineage** at every step, from raw data to AI decision.

---

## The Architecture: Provenance as a First-Class CRDT

```
┌─────────────────────────────────────────────────────────────┐
│  Every merge operation creates a ProvenanceLog               │
│                                                              │
│  MergeRecord (per row)                                       │
│    origin: "merged" | "unique_a" | "unique_b"                │
│    key: row primary key                                      │
│    decisions: List[MergeDecision]                           │
│                                                              │
│  MergeDecision (per field)                                   │
│    field: column name                                        │
│    source: which source won                                  │
│    strategy: which strategy resolved the conflict            │
│    value: the winning value                                  │
│    alternative: the losing value (preserved, not discarded)  │
└──────────────────────┬──────────────────────────────────────┘
                       │ immutable audit chain
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  AuditLog — SHA-256 hash chain                               │
│                                                              │
│  AuditEntry {                                               │
│    entry_id: UUID                                           │
│    timestamp: ISO-8601                                      │
│    operation: merge | encrypt | decrypt | unmerge | ...      │
│    input_hash: SHA-256 of input                             │
│    output_hash: SHA-256 of output                           │
│    prev_hash: hash of previous entry (chain link)           │
│    entry_hash: SHA-256 of this entry                        │
│  }                                                          │
│                                                              │
│  verify_chain() — O(n) proof that no entry was tampered     │
└─────────────────────────────────────────────────────────────┘
```

The chain is **append-only and tamper-evident**. Any modification to any entry — including the most recent — breaks the hash chain and is detected immediately by `verify_chain()`.

---

## Quick Start: Per-Field Merge Provenance

```python
from crdt_merge.provenance import merge_with_provenance, export_provenance

# Two records with conflicting values
source_a = [
    {"id": "C001", "revenue": 4_200_000, "risk": "low",    "tier": "enterprise"},
    {"id": "C002", "revenue": 1_800_000, "risk": "medium", "tier": "smb"},
]
source_b = [
    {"id": "C001", "revenue": 4_350_000, "risk": "medium", "tier": "enterprise"},  # conflicts on revenue, risk
    {"id": "C003", "revenue": 950_000,   "risk": "low",    "tier": "startup"},
]

merged, log = merge_with_provenance(source_a, source_b, key="id")

print(f"Rows merged: {log.merged_rows}")
print(f"Unique to A: {log.unique_a_rows}")
print(f"Unique to B: {log.unique_b_rows}")
print(f"Field conflicts resolved: {log.total_conflicts}")
print(f"Merge time: {log.duration_ms:.1f}ms")

# Per-row inspection
for record in log.records:
    if record.conflict_count > 0:
        print(f"\nRow {record.key} — {record.conflict_count} conflicts:")
        for decision in record.conflicts:
            print(f"  field='{decision.field}': "
                  f"chose {decision.value!r} over {decision.alternative!r} "
                  f"via {decision.strategy}")
```

---

## Cookbook: Using Custom Strategies with Provenance

```python
from crdt_merge.provenance import merge_with_provenance
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins, UnionSet

# Define field-level strategies
schema = MergeSchema(
    default=LWW(),
    revenue=MaxWins(),       # higher revenue wins
    risk_score=MinWins(),    # lower risk wins (more conservative)
    tags=UnionSet(),         # union of all tags
)

source_a = [{"id": "1", "revenue": 4200000, "risk_score": 0.3, "tags": ["enterprise"]}]
source_b = [{"id": "1", "revenue": 4350000, "risk_score": 0.4, "tags": ["vip"]}]

merged, log = merge_with_provenance(source_a, source_b, key="id", schema=schema)

for record in log.records:
    for d in record.decisions:
        print(f"{d.field}: {d.value!r} [{d.strategy}] (alternative: {d.alternative!r})")

# revenue: 4350000 [MaxWins] (alternative: 4200000)
# risk_score: 0.3 [MinWins] (alternative: 0.4)
# tags: ['enterprise', 'vip'] [UnionSet] (alternative: None)
```

---

## Cookbook: Export Provenance for Compliance

```python
from crdt_merge.provenance import merge_with_provenance, export_provenance

source_a = [{"id": "P001", "diagnosis": "hypertension", "confidence": 0.91}]
source_b = [{"id": "P001", "diagnosis": "hypertension+arrhythmia", "confidence": 0.87}]

merged, log = merge_with_provenance(source_a, source_b, key="id")

# Export as JSON (for EU AI Act Article 12 compliance)
json_report = export_provenance(log, format="json")
print(json_report)

# Export as CSV (for tabular audit tools)
csv_report = export_provenance(log, format="csv")
print(csv_report)

# Both contain: key, field, source, strategy, value, alternative
# EU AI Act Article 13: "information necessary to interpret decisions"
```

---

## Immutable Audit Log: Tamper-Evident Chain

```python
from crdt_merge.audit import AuditLog, AuditedMerge
import crdt_merge
import hashlib, json

audit = AuditLog(node_id="hospital-node-1")

# Log every merge operation
records_a = [{"id": "1", "value": 100}]
records_b = [{"id": "1", "value": 200}]

merged = crdt_merge.merge(records_a, records_b, key="id")

# Manually log the operation using the public API
def hash_object(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()

audit.log_operation(
    operation="merge",
    input_data={"a": records_a, "b": records_b},
    output_data=merged,
    strategy="lww",
    source_count=2,
)

# Verify chain integrity — O(n) walk of hash chain
assert audit.verify_chain()

print(f"Audit entries: {len(audit)}")

# Tamper detection
entries = list(audit)
# If anything is modified after the fact, verify_chain() will return False
```

---

## Cookbook: AuditedMerge — Automatic Logging

```python
from crdt_merge.audit import AuditedMerge, AuditLog
from crdt_merge.strategies import MergeSchema, MaxWins

# AuditedMerge wraps crdt_merge.merge() with automatic audit logging
audit = AuditLog(node_id="data-pipeline")
am = AuditedMerge(audit_log=audit)

schema = MergeSchema(score=MaxWins())

records_a = [{"id": "U1", "score": 80, "name": "Alice"}]
records_b = [{"id": "U1", "score": 95, "name": "Alice"}]

# Merge is automatically logged to the audit chain
merged, audit_entry = am.merge(records_a, records_b, key="id", schema=schema)
assert merged[0]["score"] == 95  # MaxWins

# All operations are in the audit log
assert audit.verify_chain()
print(f"Operations logged: {len(audit)}")

# Filter by operation type
merge_entries = audit.get_entries(operation="merge")
print(f"Merge operations: {len(merge_entries)}")
```

---

## Cookbook: Full Audit Export

```python
from crdt_merge.audit import AuditLog
import json

audit = AuditLog(node_id="prod-merger")

# After running merges...

# Export to file
audit.export_log(filepath="/tmp/audit_export.json")

# Export to dict (in-memory)
export = audit.export_log()
for entry in export["entries"]:
    print(f"[{entry['timestamp']}] {entry['operation']}: "
          f"in={entry['input_hash'][:8]}... out={entry['output_hash'][:8]}...")
```

---

## Scenario: EU AI Act Compliance for Medical AI

A hospital deploys an AI diagnostic system. Regulators require proof that every AI decision can be traced to its data sources, with conflict resolution records for any disagreements between data sources.

```python
from crdt_merge.provenance import merge_with_provenance, export_provenance
from crdt_merge.audit import AuditLog, AuditedMerge
from crdt_merge.strategies import MergeSchema, MaxWins, LWW
from crdt_merge.agentic import AgentState, SharedKnowledge

# Three diagnostic agents: imaging, lab results, clinical notes
imaging_agent = AgentState(agent_id="imaging-ai")
imaging_agent.add_fact("patient_P001_condition", "pulmonary_nodule", confidence=0.89)
imaging_agent.add_fact("patient_P001_severity",  "moderate", confidence=0.82)
imaging_agent.add_tag("imaging-reviewed")

lab_agent = AgentState(agent_id="lab-ai")
lab_agent.add_fact("patient_P001_condition", "pulmonary_nodule", confidence=0.94)
lab_agent.add_fact("patient_P001_biomarker",  "elevated_CEA", confidence=0.97)
lab_agent.add_tag("lab-reviewed")

notes_agent = AgentState(agent_id="clinical-notes-ai")
notes_agent.add_fact("patient_P001_condition", "pneumonia", confidence=0.61)  # disagrees
notes_agent.add_fact("patient_P001_history",   "smoker_20yr", confidence=0.88)
notes_agent.add_tag("notes-reviewed")

# Merge — higher confidence wins for conflicting facts
shared = SharedKnowledge.merge(imaging_agent, lab_agent, notes_agent)

# EU AI Act Article 12: full log of which agent contributed which fact
print("Contributing agents:", shared.contributing_agents)

# The imaging + lab consensus (0.89, 0.94) outweigh clinical notes (0.61)
# pulmonary_nodule wins — with full provenance of why
condition = shared.state.get_fact("patient_P001_condition")
print(f"Diagnosis: {condition.value} (confidence={condition.confidence})")
print(f"Source: {condition.source_agent}")

# EU AI Act Article 13: export explanation for the patient
audit = AuditLog(node_id="hospital-ai-system")
# Log the multi-agent merge decision
audit.log_operation(
    operation="merge",
    input_data={"agents": [str(a) for a in shared.contributing_agents]},
    output_data={"patient_id": "P001", "decision": condition.value, "confidence": condition.confidence},
    agents=shared.contributing_agents,
)
assert audit.verify_chain()
```

---

## Scenario: Financial Audit Trail for Algorithmic Trading

A trading system merges market data from three feeds. Regulators require proof of which feed influenced which trade decision, and that conflicting data was resolved deterministically.

```python
from crdt_merge.provenance import merge_with_provenance, export_provenance
from crdt_merge.strategies import MergeSchema, LWW, MaxWins
from crdt_merge.audit import AuditedMerge, AuditLog

audit = AuditLog(node_id="trading-system")
am = AuditedMerge(audit_log=audit)

# Three market data feeds — Bloomberg, Reuters, internal
schema = MergeSchema(
    price=LWW(),           # latest timestamp wins
    volume=MaxWins(),      # higher volume is more authoritative
    bid=LWW(),
    ask=LWW(),
)

# Merge feed snapshots at T=14:30:00.001
feed_bloomberg = [{"symbol": "AAPL", "price": 182.45, "volume": 1200000, "bid": 182.44, "ask": 182.46}]
feed_reuters   = [{"symbol": "AAPL", "price": 182.47, "volume": 980000,  "bid": 182.45, "ask": 182.48}]
feed_internal  = [{"symbol": "AAPL", "price": 182.46, "volume": 1350000, "bid": 182.44, "ask": 182.47}]

# Merge with full provenance
merged_ab, log_ab = merge_with_provenance(feed_bloomberg, feed_reuters, key="symbol", schema=schema)
merged_all, log_all = merge_with_provenance(merged_ab, feed_internal, key="symbol", schema=schema)

# The trade is placed using merged_all
# Regulators can inspect: which feed's price was used? Why?
for decision in log_all.records[0].conflicts:
    print(f"  {decision.field}: used {decision.value!r} from {decision.source} "
          f"(alternative: {decision.alternative!r})")

# Export audit trail for regulatory submission
report = export_provenance(log_all, format="json")
# Tamper-evident chain links trade decision back to feed data
assert audit.verify_chain()
```

---

## Scenario: Provenance-Tracked Model Training Data

Track exactly which data contributed to a model, enabling GDPR erasure requests.

```python
from crdt_merge.model import CRDTMergeState
from crdt_merge.audit import AuditLog
from crdt_merge.unmerge import GDPRForget
import numpy as np

audit = AuditLog(node_id="model-training")

# Three datasets contribute to a model
state = CRDTMergeState("ties")

datasets = {
    "dataset_eu_customers":    np.random.randn(64, 64).astype(np.float32),
    "dataset_us_customers":    np.random.randn(64, 64).astype(np.float32),
    "dataset_apac_customers":  np.random.randn(64, 64).astype(np.float32),
}

for dataset_id, weights in datasets.items():
    state.add(weights, model_id=dataset_id, weight=1/3)
    audit.log_operation(
        operation="merge",
        input_data={"dataset": dataset_id},
        output_data={"state_hash": state.state_hash},
        dataset=dataset_id,
        operation_type="add_contribution",
    )

initial_model = state.resolve()

# GDPR request: remove EU customer data from the model
state.remove("dataset_eu_customers")
audit.log_operation(
    operation="unmerge",
    input_data={"state_hash": state.state_hash},
    output_data={"pending": True},
    dataset="dataset_eu_customers",
    reason="GDPR_Article17",
)

updated_model = state.resolve()

# Verify the audit chain covers everything from initial training to erasure
assert audit.verify_chain()
print(f"Audit entries: {len(audit)}")
print(f"Model hash changed: {initial_model['layer'].sum() != updated_model['layer'].sum()}")
```

---

## Scenario: Multi-Agent Research System with Full Provenance

A research AI system uses five specialist agents. Every claim in the final report must be traceable to its source agent, the confidence level at citation time, and any conflicting claims that were resolved.

```python
from crdt_merge.agentic import AgentState, SharedKnowledge
from crdt_merge.audit import AuditLog

audit = AuditLog(node_id="research-orchestrator")

# Specialist agents
web_agent      = AgentState(agent_id="web-researcher")
paper_agent    = AgentState(agent_id="paper-analyser")
data_agent     = AgentState(agent_id="data-analyst")
expert_agent   = AgentState(agent_id="domain-expert")
synthesis_agent= AgentState(agent_id="synthesiser")

# Web researcher finds market data
web_agent.add_fact("market_size_2025",   "4.2B USD",   confidence=0.78)
web_agent.add_fact("growth_rate",        "23% CAGR",   confidence=0.72)
web_agent.add_tag("market-data")

# Paper analyser reads academic literature
paper_agent.add_fact("market_size_2025", "3.8B USD",   confidence=0.85)  # conflict
paper_agent.add_fact("key_players",      ["A", "B", "C"], confidence=0.91)
paper_agent.add_tag("academic-sources")

# Data analyst runs quantitative models
data_agent.add_fact("market_size_2025",  "4.1B USD",   confidence=0.88)  # conflict
data_agent.add_fact("growth_rate",       "19% CAGR",   confidence=0.82)  # conflict
data_agent.add_tag("quantitative")

# Domain expert provides qualitative context
expert_agent.add_fact("market_size_2025","4.0B USD",   confidence=0.93)  # highest confidence
expert_agent.add_fact("risk_factors",    ["regulation", "competition"], confidence=0.87)
expert_agent.add_tag("expert-validated")

# Merge — highest confidence wins for each fact
shared = SharedKnowledge.merge(web_agent, paper_agent, data_agent, expert_agent, synthesis_agent)

# The final report's claims are traceable:
market_size = shared.state.get_fact("market_size_2025")
print(f"Market size: {market_size.value}")
print(f"  Source: {market_size.source_agent}")
print(f"  Confidence: {market_size.confidence}")
# 4.0B USD / expert-validated / 0.93 — expert's higher confidence won

growth = shared.state.get_fact("growth_rate")
print(f"Growth rate: {growth.value}")
print(f"  Source: {growth.source_agent}")
# 19% CAGR / data-analyst / 0.82 — data analyst's higher confidence won

# EU AI Act Article 13: every claim has a named source, confidence, and timestamp
# The merged context is bit-identical on every agent's node
```

---

## Cookbook: ContextManifest — Self-Describing Merge Attestation

```python
from crdt_merge.context.merge import ContextMerge

merger = ContextMerge(strategy="max_confidence", budget=500)

# Merge memories from two agents
result = merger.merge(agent_a_memories, agent_b_memories)

# ContextManifest: machine-readable proof of the merge
manifest = result.manifest
print(f"Manifest ID: {manifest.manifest_id}")
print(f"Input A: {manifest.input_a_count} memories")
print(f"Input B: {manifest.input_b_count} memories")
print(f"Output: {manifest.output_count} memories")
print(f"Duplicates removed: {manifest.duplicates_found}")
print(f"Conflicts resolved: {manifest.conflicts_resolved}")
print(f"Strategy: {manifest.strategy}")
print(f"Timestamp: {manifest.timestamp}")

# The manifest is itself a CRDT — mergeable across nodes
# Satisfies EU AI Act Article 12: "automatic logging of events"
```

---

## Provenance Across the Full Stack

crdt-merge provides provenance at every layer:

| Layer | Module | Provenance mechanism |
|---|---|---|
| Tabular data | `provenance.py` | `ProvenanceLog` — per-field `MergeDecision` for every merge |
| Agent state | `agentic.py` | `AgentState.get_fact()` returns source agent + confidence |
| Context memory | `context/merge.py` | `ContextManifest` — self-describing merge attestation |
| Model weights | `model/` | `CRDTMergeState` tags — UUID per contribution, tombstone per removal |
| All operations | `audit.py` | `AuditLog` — SHA-256 hash chain, tamper-evident |
| Encrypted data | `encryption.py` | `EncryptedValue.order_tag` — deterministic comparison without decryption |
| Distributed sync | `gossip.py` | `VectorClock` — causal ordering proof per key |
| GDPR erasure | `unmerge.py` | `GDPRComplianceReport` — timestamped erasure records |

---

## Why This Matters Beyond Compliance

Provenance isn't just a regulatory checkbox. It enables:

**Debugging.** When a model or agent reaches a wrong conclusion, you can trace exactly which data caused it. Not "the model was trained on X" — the specific record, with its confidence level, with the alternative values that were considered and discarded.

**Trust calibration.** Systems that expose their reasoning process — including the conflicts they resolved and the alternatives they rejected — are more trustworthy than black boxes. `confidence` + `source_agent` + `alternative` together tell a richer story than the final value alone.

**Self-correcting systems.** When a source is found to be unreliable, you can retroactively reduce its influence through `remove()` and re-resolve. The provenance log shows you which decisions were based on that source's data.

**Federation without central trust.** When organisations share AI-derived knowledge without sharing raw data, the provenance layer is what makes the exchange auditable. Each party can verify what contributed to the shared knowledge without having access to the underlying data.

---

## Further Reading

- [CRDT Architecture — Full Mathematical Proof](../CRDT_ARCHITECTURE.md)
- [Architecture Map](../ARCHITECTURE_MAP.md)
- [Guide — Convergent Multi-Agent AI](./convergent-multi-agent-ai.md)
- [Guide — The Right to Forget in Trained AI Models](./right-to-forget-in-ai.md)
- [Guide — Privacy-Preserving Merge](./privacy-preserving-merge.md)
- [Guide — Federated Model Merging Without a Parameter Server](./federated-model-merging.md)
- [API Reference — ProvenanceLog](../api-reference/layer1-core/provenance.md)
- [API Reference — AuditLog](../api-reference/enterprise/audit.md)
- [Compliance Guide](../guides/compliance-guide.md)
