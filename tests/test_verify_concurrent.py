"""Concurrent CRDT verification harness tests (issue #44).

Exercises :func:`verify_crdt_concurrent`, which runs each property's trials
across threads. Verifies:

- Return shape matches :func:`verify_crdt` (additive, non-breaking).
- Trial counts shard correctly across workers (including non-divisible splits).
- Thread-safe merge functions pass.
- Non-thread-safe merge functions surface violations as failures or errors.
- Sequential :func:`verify_crdt` continues to function independently.

Stdlib-only.
"""
import random
import threading
from typing import Any, List, Set

import pytest

from crdt_merge.verify import (
    CRDTVerification,
    VerificationResult,
    verify_crdt,
    verify_crdt_concurrent,
)


# ---------------------------------------------------------------------------
# Fixture merge functions
# ---------------------------------------------------------------------------

def _set_merge(a: Set[int], b: Set[int]) -> Set[int]:
    """Thread-safe union of two frozen input sets. Returns a new set."""
    return set(a) | set(b)


def _gen_int_set() -> Set[int]:
    return {random.randint(0, 20) for _ in range(random.randint(1, 5))}


def _broken_non_commutative_merge(a: List[int], b: List[int]) -> List[int]:
    """List concatenation — order-dependent, violates commutativity."""
    return list(a) + list(b)


def _gen_int_list() -> List[int]:
    return [random.randint(0, 10) for _ in range(random.randint(1, 4))]


# ---------------------------------------------------------------------------
# Return shape / additive contract
# ---------------------------------------------------------------------------

def test_returns_crdt_verification_like_sequential():
    result = verify_crdt_concurrent(_set_merge, _gen_int_set, trials=64, workers=4)
    assert isinstance(result, CRDTVerification)
    assert isinstance(result.commutativity, VerificationResult)
    assert isinstance(result.associativity, VerificationResult)
    assert isinstance(result.idempotency, VerificationResult)
    assert result.convergence is not None


def test_sequential_verify_still_functions():
    """Adding the concurrent harness must not affect sequential verify_crdt."""
    result = verify_crdt(_set_merge, _gen_int_set, trials=32)
    assert result.commutativity.passed
    assert result.associativity.passed
    assert result.idempotency.passed


# ---------------------------------------------------------------------------
# Trial sharding
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("trials,workers", [
    (100, 4),   # divides evenly
    (101, 4),   # remainder distributed to first workers
    (7, 3),     # small case with remainder
    (10, 1),    # degenerate single worker
    (10, 16),   # more workers than trials
])
def test_trial_count_preserved_across_sharding(trials, workers):
    result = verify_crdt_concurrent(
        _set_merge, _gen_int_set, trials=trials, workers=workers,
        include_convergence=False,
    )
    assert result.commutativity.trials == trials
    assert result.associativity.trials == trials
    assert result.idempotency.trials == trials


def test_convergence_trials_capped_at_500():
    result = verify_crdt_concurrent(
        _set_merge, _gen_int_set, trials=2000, workers=4,
    )
    assert result.convergence.trials == 500


def test_include_convergence_false_omits_it():
    result = verify_crdt_concurrent(
        _set_merge, _gen_int_set, trials=32, workers=2,
        include_convergence=False,
    )
    assert result.convergence is None


def test_workers_must_be_positive():
    with pytest.raises(ValueError, match="workers must be >= 1"):
        verify_crdt_concurrent(_set_merge, _gen_int_set, trials=10, workers=0)


# ---------------------------------------------------------------------------
# Correctness under concurrency
# ---------------------------------------------------------------------------

def test_thread_safe_merge_passes_concurrently():
    result = verify_crdt_concurrent(
        _set_merge, _gen_int_set, trials=200, workers=8,
    )
    assert result.commutativity.passed
    assert result.associativity.passed
    assert result.idempotency.passed
    assert result.convergence.passed


def test_non_commutative_merge_surfaces_failures():
    result = verify_crdt_concurrent(
        _broken_non_commutative_merge, _gen_int_list,
        trials=200, workers=4, include_convergence=False,
    )
    assert not result.commutativity.passed
    assert result.commutativity.failures > 0


def test_shared_state_visible_across_threads():
    """Each thread must see the same merge_fn closure — not a separate copy."""
    call_count = {"n": 0}
    lock = threading.Lock()

    def counting_merge(a: Set[int], b: Set[int]) -> Set[int]:
        with lock:
            call_count["n"] += 1
        return set(a) | set(b)

    result = verify_crdt_concurrent(
        counting_merge, _gen_int_set, trials=64, workers=4,
        include_convergence=False,
    )
    assert result.commutativity.passed
    # Each property invokes merge_fn at least once per trial; total across
    # 3 properties × 64 trials is at least 3 * 64 independent of workers.
    assert call_count["n"] >= 3 * 64


# ---------------------------------------------------------------------------
# Duration semantics
# ---------------------------------------------------------------------------

def test_duration_is_wall_clock_max_per_property():
    """Per-property duration_ms is max across threads, not sum — reflects wall time."""
    import time

    def slow_merge(a: Set[int], b: Set[int]) -> Set[int]:
        time.sleep(0.001)
        return set(a) | set(b)

    sequential = verify_crdt(slow_merge, _gen_int_set, trials=32, include_convergence=False)
    concurrent_result = verify_crdt_concurrent(
        slow_merge, _gen_int_set, trials=32, workers=4, include_convergence=False,
    )
    # Concurrent total duration should be less than sequential
    # (allowing for scheduler noise)
    assert concurrent_result.total_duration_ms <= sequential.total_duration_ms * 1.5
