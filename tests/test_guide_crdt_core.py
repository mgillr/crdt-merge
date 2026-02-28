# tests/test_guide_crdt_core.py
# Test suite for crdt-fundamentals.md, crdt-primitives-reference.md,
# and crdt-verification-toolkit.md guides.

import random
import pytest
import numpy as np

np.random.seed(42)
random.seed(42)

# ---------------------------------------------------------------------------
# crdt-primitives-reference.md — GCounter
# ---------------------------------------------------------------------------

def test_gcounter_basic():
    """GCounter: increment and merge produce per-node-max sum."""
    from crdt_merge import GCounter

    c1 = GCounter(node_id="server_west")
    c2 = GCounter(node_id="server_east")

    c1.increment("server_west", 5)
    c2.increment("server_east", 3)

    merged = c1.merge(c2)
    assert merged.value == 8, f"Expected 8, got {merged.value}"


def test_gcounter_commutativity():
    """GCounter: merge is commutative (order of merge does not matter)."""
    from crdt_merge import GCounter

    c1 = GCounter()
    c2 = GCounter()
    c1.increment("n1", 5)
    c2.increment("n2", 3)

    m1 = c1.merge(c2)
    m2 = c2.merge(c1)
    assert m1.value == m2.value


# ---------------------------------------------------------------------------
# crdt-primitives-reference.md — PNCounter
# ---------------------------------------------------------------------------

def test_pncounter_basic():
    """PNCounter: increment and decrement merged gives correct value."""
    from crdt_merge import PNCounter

    p1 = PNCounter()
    p2 = PNCounter()

    p1.increment("node_a", 10)
    p2.decrement("node_b", 3)

    merged = p1.merge(p2)
    assert merged.value == 7, f"Expected 7, got {merged.value}"


# ---------------------------------------------------------------------------
# crdt-primitives-reference.md — LWWRegister
# ---------------------------------------------------------------------------

def test_lwwregister_basic():
    """LWWRegister: higher timestamp wins on merge."""
    from crdt_merge import LWWRegister

    r1 = LWWRegister(value="old_value", timestamp=1.0)
    r2 = LWWRegister(value="new_value", timestamp=2.0)

    merged = r1.merge(r2)
    assert merged.value == "new_value", f"Expected 'new_value', got {merged.value!r}"


# ---------------------------------------------------------------------------
# crdt-primitives-reference.md — ORSet
# ---------------------------------------------------------------------------

def test_orset_basic():
    """ORSet: union merge and membership check."""
    from crdt_merge import ORSet

    s1 = ORSet()
    s2 = ORSet()

    s1.add("x")
    s1.add("y")
    s2.add("y")
    s2.add("z")

    merged = s1.merge(s2)
    assert merged.value == {"x", "y", "z"}, f"Expected {{'x','y','z'}}, got {merged.value}"
    assert merged.contains("x") is True


# ---------------------------------------------------------------------------
# crdt-primitives-reference.md — LWWMap
# ---------------------------------------------------------------------------

def test_lwwmap_basic():
    """LWWMap: last-write-wins per key on merge."""
    from crdt_merge import LWWMap

    m1 = LWWMap()
    m2 = LWWMap()

    m1.set("key1", "val_a", timestamp=1.0)
    m2.set("key1", "val_b", timestamp=2.0)
    m2.set("key2", "val_c", timestamp=1.0)

    merged = m1.merge(m2)
    assert merged.get("key1") == "val_b", f"Expected 'val_b', got {merged.get('key1')!r}"
    assert merged.get("key2") == "val_c", f"Expected 'val_c', got {merged.get('key2')!r}"


# ---------------------------------------------------------------------------
# crdt-primitives-reference.md — VectorClock
# ---------------------------------------------------------------------------

def test_vectorclock_immutability_and_compare():
    """VectorClock: immutable (returns new clock on increment), compare works."""
    from crdt_merge import VectorClock, Ordering

    vc1 = VectorClock()
    vc1 = vc1.increment("node_a")
    vc1 = vc1.increment("node_a")

    vc2 = VectorClock()
    vc2 = vc2.increment("node_b")

    merged = vc1.merge(vc2)
    assert merged is not None

    ordering = vc1.compare(vc2)
    assert ordering == Ordering.CONCURRENT, f"Expected CONCURRENT, got {ordering}"


# ---------------------------------------------------------------------------
# crdt-primitives-reference.md — MergeableHLL
# ---------------------------------------------------------------------------

def test_mergeablehll_cardinality():
    """MergeableHLL: merged cardinality approximates union count."""
    from crdt_merge import MergeableHLL

    h1 = MergeableHLL()
    h2 = MergeableHLL()

    for i in range(100):
        h1.add(f"item_{i}")
    for i in range(50, 150):
        h2.add(f"item_{i}")

    merged = h1.merge(h2)
    card = merged.cardinality()
    # Approximate — should be within 20% of 150
    assert 120 <= card <= 180, f"HLL cardinality {card} not in expected range [120, 180]"


# ---------------------------------------------------------------------------
# crdt-primitives-reference.md — MergeableBloom
# ---------------------------------------------------------------------------

def test_mergeablebloom_contains():
    """MergeableBloom: merged filter contains items from both sides."""
    from crdt_merge import MergeableBloom

    b1 = MergeableBloom(capacity=1000, fp_rate=0.01)
    b2 = MergeableBloom(capacity=1000, fp_rate=0.01)

    b1.add("hello")
    b2.add("world")

    merged = b1.merge(b2)
    assert merged.contains("hello") is True
    assert merged.contains("world") is True


# ---------------------------------------------------------------------------
# crdt-primitives-reference.md — MergeableCMS
# ---------------------------------------------------------------------------

def test_mergeablecms_estimate():
    """MergeableCMS: merged sketch estimates count correctly."""
    from crdt_merge import MergeableCMS

    c1 = MergeableCMS()
    c2 = MergeableCMS()

    c1.add("apple", 5)
    c2.add("apple", 3)

    merged = c1.merge(c2)
    estimate = merged.estimate("apple")
    # Count-min sketch overestimates; should be >= 5
    assert estimate >= 5, f"Expected estimate >= 5, got {estimate}"


# ---------------------------------------------------------------------------
# crdt-primitives-reference.md — dedup
# ---------------------------------------------------------------------------

def test_dedup_strings():
    """dedup(): removes duplicates from string list, returns (unique, removed_indices)."""
    from crdt_merge import dedup

    unique, removed = dedup(["alice", "bob", "alice", "carol"])
    assert unique == ["alice", "bob", "carol"], f"Got {unique}"
    assert removed == [2], f"Got {removed}"


# ---------------------------------------------------------------------------
# crdt-primitives-reference.md — dedup_records
# NOTE: Guide shows dedup_records(records, key="id") but actual API uses
# dedup_records(records, columns=None, ...) and returns (unique, count).
# This test documents the actual API.
# ---------------------------------------------------------------------------

def test_dedup_records_actual_api():
    """dedup_records(): actual API uses columns=, returns (unique_list, dup_count)."""
    from crdt_merge import dedup_records

    records = [
        {"id": 1, "name": "Alice"},
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
    ]
    # Guide documents: dedup_records(records, key="id") → unique list of length 2
    # Actual API:      dedup_records(records, columns=["id"]) → (list, int)
    result = dedup_records(records, columns=["id"])
    # result is (unique_list, removed_count) or similar tuple
    if isinstance(result, tuple):
        unique_records = result[0]
    else:
        unique_records = result
    assert len(unique_records) == 2, f"Expected 2 unique records, got {len(unique_records)}"


# ---------------------------------------------------------------------------
# crdt-primitives-reference.md — verify_crdt with GCounter
# ---------------------------------------------------------------------------

def test_verify_crdt_gcounter():
    """verify_crdt(): GCounter passes all three CRDT laws."""
    from crdt_merge.verify import verify_crdt
    from crdt_merge import GCounter

    def make_gcounter():
        c = GCounter()
        for _ in range(random.randint(1, 5)):
            c.increment(f"node_{random.randint(0, 3)}", random.randint(1, 10))
        return c

    result = verify_crdt(
        merge_fn=lambda a, b: a.merge(b),
        gen_fn=make_gcounter,
        trials=100,
    )
    assert result.passed, f"GCounter failed CRDT verification: {result}"


# ---------------------------------------------------------------------------
# crdt-verification-toolkit.md — Quick Start: CRDTMergeState with verify_crdt
# ---------------------------------------------------------------------------

def test_verify_crdt_merge_state():
    """verify_crdt() with CRDTMergeState (weight_average strategy)."""
    from crdt_merge.verify import verify_crdt
    from crdt_merge.model import CRDTMergeState

    np.random.seed(42)

    def gen_state():
        state = CRDTMergeState("weight_average")
        n_contributions = np.random.randint(1, 5)
        for i in range(n_contributions):
            tensors = np.random.randn(10, 10).astype(np.float32)
            state.add(tensors, model_id=f"model_{i}", weight=1.0 / n_contributions)
        return state

    result = verify_crdt(
        merge_fn=lambda a, b: a.merge(b),
        gen_fn=gen_state,
        trials=100,
    )

    assert result.passed, f"CRDTMergeState failed: {result}"
    # Validate expected fields
    assert hasattr(result, "commutativity")
    assert hasattr(result, "associativity")
    assert hasattr(result, "idempotency")
    assert hasattr(result, "total_trials")
    assert result.commutativity.failures == 0
    assert result.associativity.failures == 0
    assert result.idempotency.failures == 0


# ---------------------------------------------------------------------------
# crdt-verification-toolkit.md — Cookbook: Custom merge function (max-wins dict)
# ---------------------------------------------------------------------------

def test_verify_crdt_custom_max_merge():
    """verify_crdt(): custom max-wins dict merge passes all three laws."""
    from crdt_merge.verify import verify_crdt

    def my_merge(state_a: dict, state_b: dict) -> dict:
        all_keys = set(state_a) | set(state_b)
        return {k: max(state_a.get(k, 0), state_b.get(k, 0)) for k in all_keys}

    def gen_state() -> dict:
        n_keys = random.randint(1, 5)
        return {f"k{i}": random.randint(0, 100) for i in range(n_keys)}

    result = verify_crdt(my_merge, gen_state, trials=500)
    assert result.passed, f"Custom merge failed CRDT verification: {result}"


# ---------------------------------------------------------------------------
# crdt-verification-toolkit.md — Cookbook: Individual law verification
# NOTE: Guide shows verify_commutative returning a CRDTVerification with
# .commutativity attribute, but the actual API returns a VerificationResult.
# This test uses the actual (correct) API.
# ---------------------------------------------------------------------------

def test_verify_commutative_individual():
    """verify_commutative/associative/idempotent return VerificationResult."""
    from crdt_merge.verify import verify_commutative, verify_associative, verify_idempotent

    def my_merge(a, b):
        all_keys = set(a) | set(b)
        return {k: max(a.get(k, 0), b.get(k, 0)) for k in all_keys}

    def gen_state():
        return {f"k{i}": random.randint(0, 100) for i in range(random.randint(1, 5))}

    comm_result = verify_commutative(my_merge, gen_state, trials=100)
    # verify_commutative returns VerificationResult (NOT CRDTVerification)
    # Correct access: .passed, .trials, .failures, .first_failure
    assert comm_result.passed is True
    assert comm_result.trials == 100
    assert comm_result.failures == 0

    assoc_result = verify_associative(my_merge, gen_state, trials=100)
    assert assoc_result.passed is True

    idem_result = verify_idempotent(my_merge, gen_state, trials=100)
    assert idem_result.passed is True


# ---------------------------------------------------------------------------
# crdt-verification-toolkit.md — Cookbook: Catching a non-CRDT buggy merge
# ---------------------------------------------------------------------------

def test_verify_crdt_catches_buggy_merge():
    """verify_crdt(): can detect a non-commutative merge function."""
    from crdt_merge.verify import verify_crdt

    # Actually-buggy merge: always takes a's value (not commutative when a != b)
    def truly_buggy_merge(a: dict, b: dict) -> dict:
        all_keys = set(a) | set(b)
        return {k: a.get(k, b.get(k)) for k in all_keys}  # always prefers a

    def gen_state():
        n_keys = random.randint(1, 3)
        return {f"k{i}": random.randint(1, 100) for i in range(n_keys)}

    result = verify_crdt(truly_buggy_merge, gen_state, trials=200)
    # This function is NOT commutative when a and b have different values for same key
    assert not result.passed, "Expected buggy merge to fail CRDT verification"
    assert result.commutativity.failures > 0


# ---------------------------------------------------------------------------
# crdt-verification-toolkit.md — Cookbook: Strategies (LWW, MaxWins, MinWins)
# ---------------------------------------------------------------------------

def test_verify_crdt_strategies_lww_maxwins_minwins():
    """verify_crdt(): LWW, MaxWins, MinWins strategies — guide merge_fn is broken.

    The guide's merge_fn returns only {"value": ...} (drops "ts"), so the
    merged state is not equal to the input state, failing idempotency and
    associativity.  A correct merge_fn must propagate all keys.
    This test documents the correct (working) form.
    """
    from crdt_merge.verify import verify_crdt
    from crdt_merge.strategies import LWW, MaxWins, MinWins

    def gen_simple():
        return {"value": random.randint(0, 100), "ts": random.uniform(0, 1000)}

    for name, strategy in [("LWW", LWW()), ("MaxWins", MaxWins()), ("MinWins", MinWins())]:
        # Correct merge_fn: preserve ALL keys, not just "value"
        def merge_fn(a, b, s=strategy):
            winning_value = s.resolve(a["value"], b["value"], a["ts"], b["ts"])
            # Pick the full record whose value won (use higher ts as tiebreak)
            winner = a if a["ts"] >= b["ts"] else b
            return {"value": winning_value, "ts": winner["ts"]}

        result = verify_crdt(merge_fn, gen_simple, trials=100)
        assert result.passed, f"{name} strategy failed CRDT verification: {result}"


# ---------------------------------------------------------------------------
# crdt-verification-toolkit.md — Cookbook: @verified_merge decorator pattern
# ---------------------------------------------------------------------------

def test_verified_merge_decorator_pattern():
    """Custom @verified_merge decorator pattern verifies at decoration time."""
    from crdt_merge.verify import verify_crdt
    from functools import wraps

    def verified_merge(gen_fn, trials=100):
        def decorator(merge_fn):
            result = verify_crdt(merge_fn, gen_fn, trials=trials)
            if not result.passed:
                raise ValueError(
                    f"Merge function '{merge_fn.__name__}' is not a CRDT!\n"
                    f"  Commutativity: {result.commutativity.trials - result.commutativity.failures}/{result.total_trials}"
                )
            return merge_fn
        return decorator

    def gen_sensor_state():
        return {
            "temp": random.uniform(15, 35),
            "ts": random.uniform(0, 1e9),
            "unit": random.choice(["C", "F"]),
        }

    @verified_merge(gen_sensor_state, trials=200)
    def merge_sensor_readings(a: dict, b: dict) -> dict:
        if a["ts"] >= b["ts"]:
            return a
        return b

    # If we got here, the merge function passed CRDT verification
    assert merge_sensor_readings({"temp": 20, "ts": 1.0, "unit": "C"},
                                  {"temp": 25, "ts": 2.0, "unit": "C"}) == {"temp": 25, "ts": 2.0, "unit": "C"}


# ---------------------------------------------------------------------------
# crdt-verification-toolkit.md — CI/CD scenario: patient merge
# ---------------------------------------------------------------------------

def test_patient_merge_is_crdt():
    """Patient record merge satisfies CRDT laws (CI/CD scenario)."""
    from crdt_merge.verify import verify_crdt

    def gen_patient_record():
        return {
            "patient_id": f"P{random.randint(1, 10000):05d}",
            "latest_obs": random.uniform(0, 500),
            "obs_ts": random.uniform(1700000000, 1800000000),
            "flags": set(random.sample(["critical", "warning", "normal"], random.randint(1, 3))),
        }

    def merge_patient_records(a: dict, b: dict) -> dict:
        if a["obs_ts"] >= b["obs_ts"]:
            winner = a
        else:
            winner = b
        return dict(winner, flags=a["flags"] | b["flags"])

    result = verify_crdt(merge_patient_records, gen_patient_record, trials=500)

    assert result.commutativity.failures == 0, (
        f"Commutativity failed {result.commutativity.failures}/500 times\n"
        f"Counterexample: {result.commutativity.first_failure}"
    )
    assert result.associativity.failures == 0, (
        f"Associativity failed {result.associativity.failures}/500 times"
    )
    assert result.idempotency.failures == 0, (
        f"Idempotency failed {result.idempotency.failures}/500 times"
    )
    assert result.passed


# ---------------------------------------------------------------------------
# crdt-verification-toolkit.md — AgentState verification
# ---------------------------------------------------------------------------

def test_agentstate_crdt_compliance():
    """AgentState merge — guide claims CRDT compliance but two bugs exist:

    1. AgentState has no __eq__, so verify_crdt uses identity comparison and
       every check fails (all merged objects are different Python objects).
    2. Even with a custom eq_fn using to_dict(), ORSet UUID ordering in
       to_dict() is not normalised, causing spurious commutativity failures.
       The logical tag set IS commutative; only the raw serialization is not.

    This test verifies the logical values (facts + tags as sets) are CRDT-
    compliant using a normalised equality function.
    """
    try:
        from crdt_merge.verify import verify_crdt
        from crdt_merge.agentic import AgentState
    except ImportError:
        pytest.skip("crdt_merge.agentic not available")

    def gen_agent_state():
        state = AgentState(agent_id=f"agent-{random.randint(1, 100)}")
        n_facts = random.randint(1, 5)
        for i in range(n_facts):
            fact_key = random.choice(["revenue", "risk", "status", "priority", "owner"])
            value = random.choice([100, 200, "active", "inactive"])
            confidence = random.uniform(0.5, 1.0)
            state.add_fact(fact_key, value, confidence=confidence)
        for tag in random.sample(["finance", "risk", "ops", "tech"], random.randint(0, 3)):
            state.add_tag(tag)
        return state

    # Normalised equality: compare logical values only (ignore UUID ordering)
    def agent_eq(a, b):
        a_facts = {k: (v.value, round(v.confidence, 6)) for k, v in a.list_facts().items()}
        b_facts = {k: (v.value, round(v.confidence, 6)) for k, v in b.list_facts().items()}
        return a_facts == b_facts and a.tags == b.tags

    result = verify_crdt(
        merge_fn=lambda a, b: a.merge(b),
        gen_fn=gen_agent_state,
        trials=200,
        eq_fn=agent_eq,
    )

    assert result.passed, (
        f"AgentState failed CRDT compliance:\n"
        f"  Commutativity: {result.commutativity.failures} failures\n"
        f"  Associativity: {result.associativity.failures} failures\n"
        f"  Idempotency:   {result.idempotency.failures} failures\n"
        f"  First comm failure: {result.commutativity.first_failure}"
    )


# ---------------------------------------------------------------------------
# crdt-verification-toolkit.md — CRDTVerification field access
# ---------------------------------------------------------------------------

def test_crdt_verification_fields():
    """CRDTVerification has all expected fields and types."""
    from crdt_merge.verify import verify_crdt, CRDTVerification

    def merge_fn(a, b):
        return max(a, b)

    result = verify_crdt(merge_fn, lambda: random.randint(0, 100), trials=50)

    assert isinstance(result, CRDTVerification)
    assert isinstance(result.passed, bool)
    assert isinstance(result.total_trials, int)
    assert hasattr(result.commutativity, "passed")
    assert hasattr(result.commutativity, "trials")
    assert hasattr(result.commutativity, "failures")
    assert hasattr(result.commutativity, "first_failure")
    assert hasattr(result.associativity, "passed")
    assert hasattr(result.idempotency, "passed")
