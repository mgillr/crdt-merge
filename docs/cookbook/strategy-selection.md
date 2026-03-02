# Strategy Selection Cookbook

How to pick the right strategy for every field type. All examples verified against the live codebase.

---

## Decision Tree

```
Is this field a CRDT primitive (counter, set)?
  → Use the primitive directly: GCounter, ORSet, LWWMap

Is this a DataFrame/record field?
  ↓
Is it numeric?
  ├── Higher should win  → MaxWins()
  ├── Lower should win   → MinWins()
  └── Latest should win  → LWW()

Is it a collection / list of items?
  ├── Set semantics (no duplicates, no order)  → UnionSet(separator=",")
  └── Preserve all history                     → Concat(separator=" | ")

Does it follow a state machine / workflow?
  → Priority(["state1", "state2", ..., "stateN"])

Is it a text field?
  ├── Most recent is correct  → LWW()
  ├── Longer = better         → LongestWins()
  └── Preserve all versions   → Concat()

None of the above?
  → Custom(fn=your_function)
```

---

## Strategy Reference

```python
from crdt_merge.strategies import (
    MergeSchema, LWW, MaxWins, MinWins,
    UnionSet, Concat, Priority, LongestWins, Custom
)
```

| Strategy | Constructor | Rule | Tie-break |
|---|---|---|---|
| `LWW` | `LWW()` | Higher timestamp wins | `max(str(a), str(b))` |
| `MaxWins` | `MaxWins()` | Higher value wins | `repr()` comparison |
| `MinWins` | `MinWins()` | Lower value wins | `repr()` comparison |
| `UnionSet` | `UnionSet(separator=",")` | Set union | N/A |
| `Concat` | `Concat(separator=" \| ", dedup=True)` | Append + sort | N/A |
| `Priority` | `Priority(["a","b","c"])` | Higher index wins | Lexicographic `str()` |
| `LongestWins` | `LongestWins()` | Longer string wins | Falls back to LWW |
| `Custom` | `Custom(fn=my_fn)` | User-defined | User-defined |

---

## Domain Examples

### E-Commerce Product Catalog

```python
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins, UnionSet, LongestWins, Priority

product_schema = MergeSchema(
    default=LWW(),
    # Identity fields: most recent wins
    product_name=LWW(),
    sku=LWW(),
    brand=LWW(),
    # Pricing: lowest wins (customer-friendly / correct legal minimum)
    price=MinWins(),
    sale_price=MinWins(),
    # Ratings: highest observed wins
    rating=MaxWins(),
    review_count=MaxWins(),     # monotonically increasing
    # Taxonomy: union preserves all assignments
    categories=UnionSet(separator=","),
    tags=UnionSet(separator=","),
    # Content: most detailed wins
    description=LongestWins(),
    # Lifecycle: escalate, never regress
    status=Priority(["draft", "pending", "active", "featured", "discontinued"]),
)
```

### User Profile (SaaS)

```python
user_schema = MergeSchema(
    default=LWW(),
    # Personal data: latest update wins
    email=LWW(),
    name=LWW(),
    avatar_url=LWW(),
    # Permissions: union — never take away access during merge
    permissions=UnionSet(separator=","),
    roles=UnionSet(separator=","),
    # Metrics: higher wins
    login_count=MaxWins(),
    storage_used_bytes=MaxWins(),
    # Account tier: escalate (free → trial → paid → enterprise)
    plan=Priority(["free", "trial", "starter", "pro", "enterprise"]),
    # Audit: concatenate all notes
    admin_notes=Concat(separator="\n"),
)
```

### Medical Record (HIPAA Context)

```python
from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins, UnionSet, Priority, Concat

medical_schema = MergeSchema(
    default=LWW(),
    # Demographics: latest wins
    patient_name=LWW(),
    date_of_birth=LWW(),
    # Clinical: critical values — most severe wins
    blood_pressure_systolic=MaxWins(),   # highest observed is most critical
    pain_scale=MaxWins(),                # highest reported
    # Allergies: union — never remove an allergy during merge
    allergies=UnionSet(separator=";"),
    medications=UnionSet(separator=";"),
    # Status: clinical escalation (never downgrade severity)
    severity=Priority(["routine", "urgent", "critical", "emergency"]),
    # Notes: preserve all clinical notes
    clinical_notes=Concat(separator="\n---\n"),
)
```

### Git-like Version Control

```python
versioning_schema = MergeSchema(
    default=LWW(),
    # Version: monotonically increasing
    version=MaxWins(),
    build_number=MaxWins(),
    # Feature flags: union (additive merges)
    feature_flags=UnionSet(separator=","),
    # Release pipeline: can only advance
    pipeline_stage=Priority(["dev", "test", "staging", "production"]),
    # Authors: union preserves all contributors
    contributors=UnionSet(separator=","),
    # Changelog: append all entries
    changelog=Concat(separator="\n"),
)
```

### IoT / Sensor Data

```python
sensor_schema = MergeSchema(
    default=LWW(),
    # Readings: latest always wins (sensors can correct themselves)
    temperature=LWW(),
    humidity=LWW(),
    # Extremes: record min/max for anomaly detection
    max_temperature=MaxWins(),
    min_temperature=MinWins(),
    # Alerts: union — any node seeing an alert should propagate it
    active_alerts=UnionSet(separator=","),
    # Device health: worst-case wins
    error_count=MaxWins(),
    last_error=LWW(),
    # Status: degraded states should persist until manually cleared
    device_status=Priority(["healthy", "degraded", "offline", "error"]),
)
```

### Financial Data (SOX Context)

```python
financial_schema = MergeSchema(
    default=LWW(),
    # Transaction identifiers: exact match required (LWW is safe — same value)
    transaction_id=LWW(),
    account_id=LWW(),
    # Amounts: latest authoritative value
    amount=LWW(),
    currency=LWW(),
    # Audit trail: never lose an entry
    audit_trail=Concat(separator="\n"),
    # Approval status: can only advance
    approval_status=Priority(["pending", "under_review", "approved", "settled"]),
    # Flags: union — any flag from any replica must persist
    compliance_flags=UnionSet(separator=","),
)
```

---

## Choosing Between LWW and MaxWins

**Use `LWW` when**: The most recent update is definitively correct (user changed their email, the new one is right).

**Use `MaxWins` when**: Higher value is always correct regardless of when it was set (score, version number, high-water mark).

```python
from crdt_merge.strategies import LWW, MaxWins

# LWW: timestamp is what matters
lww = LWW()
# ts=1001 (newer) wins even though value is lower
print(lww.resolve(100, 50, ts_a=1000, ts_b=1001))   # 50 — newer wins

# MaxWins: value is what matters, timestamp ignored
mx = MaxWins()
# 100 wins even though it's older
print(mx.resolve(100, 50, ts_a=1000, ts_b=1001))    # 100 — higher wins
```

---

## Choosing Between UnionSet and Concat

**Use `UnionSet` when**: Values are a set (no duplicates, no natural order, just membership).

**Use `Concat` when**: Values are a log/history (duplicates OK, order matters, human-readable).

```python
from crdt_merge.strategies import UnionSet, Concat

# UnionSet: tags are a set
tags = UnionSet(separator=",")
print(tags.resolve("python,ml", "python,ai"))   # "ai,ml,python" (sorted union)

# Concat: notes are a log
notes = Concat(separator=" | ", dedup=True)
print(notes.resolve("Added feature", "Fixed bug"))  # "Added feature | Fixed bug"

# Key difference: UnionSet on notes would collapse identical notes
# Concat on tags would concatenate "python,ml | python,ai" (duplicates)
```

---

## Custom Strategy Checklist

If using `Custom`, verify these properties:

```python
from crdt_merge.strategies import Custom
from crdt_merge.verify import verify_crdt
from crdt_merge.core import LWWRegister

# 1. Commutative: fn(a, b) must equal fn(b, a) for all inputs
# 2. Values should ideally be stable (idempotent)

def my_fn(a, b):
    """Take the longer of two strings, breaking ties by lex order."""
    if a is None: return b
    if b is None: return a
    la, lb = len(str(a)), len(str(b))
    if la != lb:
        return a if la > lb else b
    return max(str(a), str(b))   # lexicographic tiebreak → commutative

strategy = Custom(fn=my_fn)
result = verify_crdt(LWWRegister, strategy=strategy)
assert result.commutativity.passed, "Custom fn is not commutative!"
```
