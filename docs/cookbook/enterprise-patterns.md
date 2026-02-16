# Enterprise Patterns

## Recipe 1: Audited Merge

```python
from crdt_merge.audit import AuditLog, AuditedMerge

log = AuditLog(node_id="enterprise-node")
audited = AuditedMerge(audit_log=log, node_id="enterprise-node")

result, entry = audited.merge(df_a, df_b, key="id", schema=schema)
# Audit entry automatically created with SHA-256 hash chain

assert log.verify_chain()  # Verify integrity
```

## Recipe 2: Encrypted Merge

```python
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
import os

key = os.urandom(32)  # 256-bit encryption key
provider = StaticKeyProvider(key=key)
enc_merge = EncryptedMerge(key_provider=provider)

# merge_encrypted works with list-of-dicts (not DataFrames)
left = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
right = [{"id": 1, "name": "Bob"}, {"id": 3, "name": "Carol"}]

result = enc_merge.merge_encrypted(left, right, key="id")
```

## Recipe 3: RBAC-Protected Merge

```python
from crdt_merge.rbac import (
    RBACController, SecureMerge, Policy, Role, Permission, AccessContext,
)

rbac = RBACController()

# Define roles using Permission flags
analyst_role = Role(
    name="analyst",
    permissions=frozenset({Permission.READ, Permission.MERGE}),
)
admin_role = Role(
    name="admin",
    permissions=frozenset({
        Permission.READ, Permission.WRITE, Permission.MERGE,
        Permission.UNMERGE, Permission.ADMIN,
    }),
)

# Add policies for specific nodes
rbac.add_policy("alice", Policy(role=analyst_role))
rbac.add_policy("bob", Policy(role=admin_role))

secure = SecureMerge(rbac=rbac)

ctx = AccessContext(node_id="alice", role=analyst_role)
result = secure.merge(df_a, df_b, key="id", schema=schema, context=ctx)  # ✅ Allowed
```

## Recipe 4: Full Enterprise Stack

```python
from crdt_merge.audit import AuditLog, AuditedMerge
from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider
from crdt_merge.rbac import RBACController, SecureMerge, Policy, AccessContext, MERGER
from crdt_merge.observability import MetricsCollector, ObservedMerge
import os

# 1. Observability layer
collector = MetricsCollector(node_id="enterprise-node")
observed = ObservedMerge(collector=collector, node_id="enterprise-node")

# 2. Audit layer
log = AuditLog(node_id="enterprise-node")
audited = AuditedMerge(audit_log=log, node_id="enterprise-node")

# 3. RBAC layer
rbac = RBACController()
rbac.add_policy("ops-node", Policy(role=MERGER))
secure = SecureMerge(rbac=rbac)

# 4. Encryption layer
key = os.urandom(32)
enc_merge = EncryptedMerge(key_provider=StaticKeyProvider(key=key))

# Each layer can be used independently; compose as needed:
#   observed.merge(...)           → returns (result, MergeMetric)
#   audited.merge(...)            → returns (result, AuditEntry)
#   secure.merge(..., context=…)  → RBAC-gated merge
#   enc_merge.merge_encrypted(…)  → encrypts fields during merge
```

## Recipe 5: GDPR Forget

```python
from crdt_merge.provenance import merge_with_provenance
from crdt_merge.unmerge import GDPRForget, UnmergeEngine

# Merge with provenance tracking
result, provenance = merge_with_provenance(df_a, df_b, key="id")

# Convert to list of dicts (GDPRForget works with dicts, not DataFrames)
merged_dicts = result.to_dict('records')

# Set up the GDPR forget handler
engine = UnmergeEngine()
forget = GDPRForget(engine=engine)

# Remove a contributor's data (e.g., all records from source "b")
forget_result = forget.forget_data(
    merged_data=merged_dicts,
    provenance=provenance,
    contributor="b",
    key_field="id",
)

# Generate a compliance report
report = forget.compliance_report()
```
