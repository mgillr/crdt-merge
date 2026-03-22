# Design Decisions — Key Rationale

Every significant architectural choice is documented here with the problem it solves, the trade-offs accepted, and how to work with it in practice.

---

## D-001: Six-Layer Architecture

**Decision**: Code is organized into 6 layers with strict downward dependency direction.

**Rationale**: Each layer is independently usable. A data engineer merging DataFrames doesn't need torch or cryptography. A compliance team using Layer 6 gets Layer 5 audit automatically. Layers build bottom-up with no circular dependencies (confirmed by AST analysis: 0 circular dependencies).

**Layer summary**:
```
Layer 1 — Core CRDTs       (stdlib only — always available)
Layer 2 — Merge Engines    (pandas/polars/arrow — optional)
Layer 3 — Sync & Transport (wire, gossip, merkle — optional)
Layer 4 — AI / Model       (torch/transformers — optional)
Layer 5 — Enterprise       (cryptography — optional)
Layer 6 — Compliance       (builds on L5 + L4 audit chain)
```

**Trade-off**: Some duplication — e.g., provenance exists at both Layer 1 (general) and Layer 4 (model-specific). This is intentional: Layer 4's provenance has model-specific fields that would create coupling in Layer 1.

**Working with it**:
```python
# Use only what you need — each layer is independently importable
from crdt_merge.core import GCounter          # Layer 1 only
from crdt_merge import merge                  # Layer 2
from crdt_merge.wire import serialize         # Layer 3
from crdt_merge.model import CRDTMergeState  # Layer 4
from crdt_merge.audit import AuditLog         # Layer 5
from crdt_merge.compliance import ComplianceAuditor  # Layer 6
```

---

## D-002: CRDT-First Design

**Decision**: All merge operations satisfy the CRDT convergence theorem (commutative, associative, idempotent).

**Rationale**: These three properties guarantee that any set of replicas observing all updates will converge to identical state, regardless of message delivery order, network partitions, or processing order.

```python
from crdt_merge.core import GCounter

# Proof: commutativity
a = GCounter(); a.increment("x", 5)
b = GCounter(); b.increment("y", 3)
assert a.merge(b).value == b.merge(a).value   # 8 == 8 ✅

# Proof: associativity
c = GCounter(); c.increment("z", 2)
assert a.merge(b).merge(c).value == a.merge(b.merge(c)).value  # ✅

# Proof: idempotency
assert a.merge(a).value == a.value  # ✅
```

**Trade-off**: CRDT semantics can be unintuitive. ORSet's add-wins means a deleted element reappears after merge with a node that added it concurrently. This is mathematically correct, but requires user education.

**Formal verification** (built-in):
```python
from crdt_merge.verify import verify_crdt
from crdt_merge.core import LWWRegister

result = verify_crdt(LWWRegister)
print(result.commutativity.passed)   # True
print(result.associativity.passed)   # True
print(result.idempotency.passed)     # True
```

---

## D-003: Strategy Pattern for Conflict Resolution

**Decision**: Per-field conflict resolution via composable `MergeSchema`.

**Rationale**: Different fields in the same record legitimately need different resolution. A `score` field should always take the max; a `status` field should follow a state machine; a `tags` field should union.

```python
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, UnionSet, Priority

schema = MergeSchema(
    default=LWW(),         # catch-all: latest timestamp wins
    score=MaxWins(),       # numeric: higher always wins
    tags=UnionSet(","),    # set semantics: union
    status=Priority(["draft", "review", "approved", "published"]),
)

# Each field resolved independently
row_a = {"score": 90, "status": "draft",    "tags": "ml",   "ts": 1000}
row_b = {"score": 85, "status": "approved", "tags": "ai",   "ts": 1001}
merged = schema.resolve_row(row_a, row_b, timestamp_col="ts")
# score=90 (MaxWins), status="approved" (Priority), tags="ai,ml" (UnionSet)
```

**Trade-off**: More complex than a single global strategy. Users must learn the MergeSchema API. Reward: explicit, auditable, field-level conflict resolution.

---

## D-004: Zero-Dependency Core

**Decision**: Layer 1 uses only Python stdlib (no pandas, no numpy, no external packages).

**Rationale**: Minimizes installation friction and dependency conflicts. Embedded systems, serverless functions, and edge nodes can use CRDT primitives without a full data science stack.

```python
# Works with zero extra packages installed
from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet, LWWMap
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, Priority
from crdt_merge.verify import verify_crdt
```

**Trade-off**: Vectorized operations (Arrow engine, Polars engine) are in Layer 2 and require optional extras.

---

## D-005: Optional Heavy Dependencies

**Decision**: pandas, pyarrow, polars, torch, transformers, cryptography, duckdb are all optional.

**Rationale**: The library serves radically different audiences. Install only what you use:

```bash
pip install crdt-merge           # Core only (Layer 1-3)
pip install crdt-merge[arrow]    # + pyarrow (Arrow engine)
pip install crdt-merge[model]    # + torch, transformers (model merging)
pip install crdt-merge[enterprise]  # + cryptography (encryption)
pip install crdt-merge[all]      # Everything
```

**Import pattern** — all optional-dependency modules use lazy imports:
```python
# dataframe.py imports pandas only when first called
result = merge(df_a, df_b, key="id")  # pandas imported here if needed
```

**Trade-off**: More complex packaging. Conditional imports throughout the codebase. Error messages mention which extra to install if a dependency is missing.

---

## D-006: Enterprise Features as Wrappers

**Decision**: Audit, encryption, RBAC, and observability are wrappers around core merge, not baked in.

**Rationale**: Enterprise features should be opt-in. The wrapper pattern means the core merge path has zero overhead when not used. Composing wrappers is more flexible than a single class with flags.

**Composition order matters** (outermost → innermost):
```python
from crdt_merge.rbac import RBACController, Policy, MERGER, SecureMerge
from crdt_merge.audit import AuditLog, AuditedMerge
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
from crdt_merge.observability import MetricsCollector, ObservedMerge
import secrets

# Stack: RBAC → Audit → Encryption → Observe → Core
rbac = RBACController()
rbac.add_policy(Policy(role=MERGER, denied_fields={"ssn"}))

audit = AuditLog(node_id="node1")
collector = MetricsCollector()
key_provider = StaticKeyProvider(secrets.token_bytes(32))

# Compose wrappers
secure = SecureMerge(rbac=rbac, role=MERGER)
audited = AuditedMerge(audit_log=audit)
encrypted = EncryptedMerge(key_provider=key_provider)
observed = ObservedMerge(collector=collector)
```

**Trade-off**: Wrapper composition order matters and must be understood by operators. See [Security Guide](../guides/security-guide.md) for the canonical ordering.

---

## D-007: Layer 4 as Largest Layer

**Decision**: Layer 4 (AI/Model) is the largest layer (~18,410 LOC, ~41% of codebase).

**Rationale**: Model merging is the most mathematically complex domain. 26+ strategies cover different approaches:
- Linear interpolation, SLERP, TIES, DARE, DARE-TIES (weight-space strategies)
- Fisher information weighting (second-order)
- Evolutionary/genetic (population-based)
- Calibration, subspace, unlearning (specialized)

Layer 4 is decomposed into well-defined sub-packages:
```
model/strategies/    — 9 modules, each implementing a strategy family
model/targets/       — HuggingFace model adapter
accelerators/        — 8 external system integrations
hub/                 — HuggingFace Hub upload/download
context/             — Agent context management (5 modules)
```

**Trade-off**: The layer may need extraction as a separate package if it continues growing. Current decomposition keeps it manageable.

---

## D-008: Deterministic Tie-Breaking Everywhere

**Decision**: All merge operations with equal inputs produce the same output, regardless of argument order.

**Rationale**: Non-determinism breaks commutativity. If `merge(A, B) ≠ merge(B, A)`, replicas diverge permanently. Every strategy in crdt-merge uses a deterministic tie-break:

| Strategy | Primary | Tie-break |
|---|---|---|
| `LWW` | Higher timestamp | `max(str(val_a), str(val_b))` |
| `MaxWins` | Higher value | `repr()` comparison |
| `MinWins` | Lower value | `repr()` comparison |
| `LWWRegister` | Higher timestamp | Lexicographic `node_id` |
| `Priority` | Higher priority index | Lexicographic `str(val)` |
| `LongestWins` | Longer string | Delegates to `LWW` |

**Gotcha**: Lexicographic node ID comparison means `"node9" > "node10"`. Use zero-padded IDs:
```python
# Bad:  "node1", ..., "node9", "node10" — node9 always beats node10
# Good: "node01", ..., "node09", "node10" — correct numeric order
node_id = f"node{i:02d}"
```

---

## D-009: `__init__.py` as Facade

**Decision**: `crdt_merge/__init__.py` imports from all 6 layers to provide a flat public namespace.

**Rationale**: Users should be able to write `from crdt_merge import merge, AuditLog, ComplianceAuditor` without knowing which layer each lives in. The facade provides discoverability.

```python
# All of these work from the top-level import
from crdt_merge import (
    merge,               # Layer 2
    GCounter,            # Layer 1
    AuditLog,            # Layer 5
    ComplianceAuditor,   # Layer 6
    CRDTMergeState,      # Layer 4
    serialize,           # Layer 3
)
```

**Note**: GDEPA static analysis flags 19 "layer violations" from `__init__.py`. These are all facade imports — expected behavior, not bugs.

---

*Design Decisions v1.1 — updated for v0.9.4*
