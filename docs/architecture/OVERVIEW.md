# System Overview — crdt-merge v0.9.4

## What is crdt-merge?

crdt-merge is a Python library that applies **Conflict-Free Replicated Data Type (CRDT)** mathematics to real-world data merging problems across six architectural layers:

```
Layer 6 — Compliance        (GDPR, HIPAA, SOX, EU AI Act validation)
Layer 5 — Enterprise        (encryption, RBAC, audit, observability, unmerge)
Layer 4 — AI / Model        (model merging, agentic AI, federated learning)
Layer 3 — Sync & Transport  (wire protocol, gossip, Merkle sync, delta compression)
Layer 2 — Merge Engines     (DataFrame, Arrow, Parquet, streaming, parallel, async)
Layer 1 — Core CRDTs        (GCounter, PNCounter, LWWRegister, ORSet, LWWMap, strategies)
```

Every layer is independently usable. Layers depend strictly downward — no circular dependencies.

---

## Key Metrics (v0.9.4)

| Metric | Value |
|---|---|
| Total LOC | 44,304 |
| Modules | 104 |
| Classes | 212 |
| Functions | 1,586 |
| Test suite | 309 tests, 100% passing |
| Layer 1 (Core) LOC | 2,861 |
| Layer 4 (AI/Model) LOC | 18,410 |
| Layer 5 (Enterprise) LOC | 3,323 |
| Layer 6 (Compliance) LOC | 932 |

---

## Design Philosophy

**Mathematical Correctness First** — Every merge operation is commutative, associative, and idempotent. These are not aspirational properties; they are enforced by the mathematical structure of each primitive.

**Zero-Dependency Core** — Layer 1 uses only Python stdlib. You can merge GCounters without pandas, torch, or cryptography installed.

**Progressive Enhancement** — Each layer adds capabilities without changing lower layers. Enterprise features are opt-in wrappers.

**Strategy Pattern** — Per-field conflict resolution via composable `MergeSchema`. Different columns in the same record can use different strategies.

**Transport Agnostic** — Core merge logic is independent of serialization format. The same `merge()` call works on pandas DataFrames, Polars DataFrames, Arrow tables, and raw dicts.

---

## Quickstart — Layer 1 (No Dependencies)

```python
from crdt_merge.core import GCounter, ORSet, LWWRegister

# Grow-only counter — merges across nodes
counter_a = GCounter()
counter_b = GCounter()
counter_a.increment("node_a", 10)
counter_b.increment("node_b", 7)
merged = counter_a.merge(counter_b)
print(merged.value)   # 17

# Observed-Remove Set — add-wins semantics
s = ORSet()
s.add("user:alice")
s.add("user:bob")
s.remove("user:alice")
print(s.value)        # {"user:bob"}

# LWW Register — latest timestamp wins
r = LWWRegister(value="v1", timestamp=1000.0, node_id="node_a")
r2 = LWWRegister(value="v2", timestamp=1001.0, node_id="node_b")
print(r.merge(r2).value)  # "v2"
```

## Quickstart — Layer 2 (DataFrame Merge)

```python
import pandas as pd
from crdt_merge import merge
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, UnionSet, Priority

df_a = pd.DataFrame([
    {"id": 1, "name": "Alice", "score": 90, "tags": "python,ml", "status": "review", "ts": 1000},
    {"id": 2, "name": "Bob",   "score": 80, "tags": "go",        "status": "draft",  "ts": 1000},
])
df_b = pd.DataFrame([
    {"id": 1, "name": "Alice", "score": 95, "tags": "python,ai", "status": "approved", "ts": 999},
    {"id": 3, "name": "Carol", "score": 88, "tags": "rust",      "status": "published","ts": 1001},
])

schema = MergeSchema(
    default=LWW(),
    score=MaxWins(),
    tags=UnionSet(separator=","),
    status=Priority(["draft", "review", "approved", "published"]),
)

result = merge(df_a, df_b, key="id", schema=schema, timestamp_col="ts")
# id=1: score=95 (MaxWins), tags="ai,ml,python" (union), status="approved" (Priority)
# id=2: kept from df_a only
# id=3: kept from df_b only
print(result)
```

## Quickstart — Layer 5 (Enterprise)

```python
import secrets
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
from crdt_merge.rbac import RBACController, Policy, MERGER
from crdt_merge.audit import AuditLog, AuditedMerge
from crdt_merge.observability import MetricsCollector, ObservedMerge

# Encryption
key_provider = StaticKeyProvider(secrets.token_bytes(32))
em = EncryptedMerge(key_provider=key_provider, backend="aes-256-gcm")

# RBAC
rbac = RBACController()
rbac.add_policy(Policy(role=MERGER, denied_fields={"ssn", "dob"}))

# Audit
audit = AuditLog(node_id="prod-node-1")
am = AuditedMerge(audit_log=audit)
result, entry = am.merge(records_a, records_b, key="id")
assert audit.verify_chain()

# Observability
collector = MetricsCollector()
om = ObservedMerge(collector=collector)
result = om.merge(df_a, df_b, key="id")
print(collector.get_summary())
```

## Quickstart — Layer 6 (Compliance)

```python
from crdt_merge.compliance import ComplianceAuditor
from crdt_merge.audit import AuditLog

audit = AuditLog(node_id="prod-system")
auditor = ComplianceAuditor(framework="gdpr", audit_log=audit)

auditor.record_merge(
    operation="user-profile-merge",
    input_hash="sha256:abc...",
    output_hash="sha256:def...",
)
report = auditor.validate()
print(report.to_text())
print(f"Passed: {report.passed}")
```

---

## Layer Dependency Direction

```
Layer 6  →  Layer 5, Layer 4
Layer 5  →  Layer 4, Layer 2, Layer 1
Layer 4  →  Layer 3, Layer 2, Layer 1
Layer 3  →  Layer 2, Layer 1
Layer 2  →  Layer 1
Layer 1  →  Python stdlib only
```

See [LAYER_MAP.md](LAYER_MAP.md) for per-module detail.
See [DEPENDENCY_GRAPH.md](DEPENDENCY_GRAPH.md) for import-level dependencies.
See [DATA_FLOW.md](DATA_FLOW.md) for request-level data flow.
See [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) for rationale behind key choices.
