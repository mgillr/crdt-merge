# Testing Guide

## Test Organization

```
tests/
├── test_core.py            # Layer 1: CRDT primitives
├── test_strategies.py      # Layer 1: Merge strategies
├── test_clocks.py          # Layer 1: Vector clocks
├── test_dataframe.py       # Layer 2: DataFrame merge
├── test_streaming.py       # Layer 2: Stream merge
├── test_arrow.py           # Layer 2: Arrow engine
├── test_gossip.py          # Layer 3: Gossip protocol
├── test_merkle.py          # Layer 3: Merkle trees
├── test_wire.py            # Layer 3: Wire protocol
├── test_model_*.py         # Layer 4: Model merge (multiple files)
├── test_audit.py           # Layer 5: Audit trails
├── test_encryption.py      # Layer 5: Encryption
├── test_rbac.py            # Layer 5: RBAC
├── test_compliance.py      # Layer 6: Compliance
├── test_pbt_*.py           # Property-based tests
└── test_crdt_*.py          # CRDT law validation
```

## Test Types

### Unit Tests
Standard pytest tests for individual functions and classes.

### Property-Based Tests
Using Hypothesis to verify CRDT properties:
```python
@given(st.integers(), st.integers())
def test_gcounter_commutative(a, b):
    c1 = GCounter("a", a).merge(GCounter("b", b))
    c2 = GCounter("b", b).merge(GCounter("a", a))
    assert c1.value == c2.value
```

### CRDT Law Tests
Formal verification of commutativity, associativity, and idempotency for every CRDT type.

### Integration Tests
End-to-end tests covering multi-layer workflows.

## Coverage

Target: 90%+ line coverage for Layers 1-3.
