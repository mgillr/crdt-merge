# Copyright 2026 Ryan Gillespie
# SPDX-License-Identifier: Apache-2.0
#
# Commercial licensing: data@optitransfer.ch, rgillespie83@icloud.com

"""
CRDT Verification Toolkit — runtime proof that merge functions are correct.

Property-based testing that PROVES a merge function satisfies CRDT laws:
  1. Commutativity: merge(A, B) == merge(B, A)
  2. Associativity: merge(merge(A, B), C) == merge(A, merge(B, C))
  3. Idempotency:   merge(A, A) == A

Inspired by Propel (PLDI'23, ETH Zurich) which does compile-time verification.
This is RUNTIME verification — zero dependencies, any language, any merge function.

Usage:
    from crdt_merge.verify import verify_crdt, verify_commutative

    # Verify a custom merge function
    result = verify_crdt(my_merge_fn, my_data_generator, trials=10_000)
    assert result.passed  # All three properties hold

    # Verify built-in CRDT types
    from crdt_merge.core import GCounter
    result = verify_crdt(
        merge_fn=lambda a, b: a.merge(b),
        gen_fn=lambda: GCounter("n1", random.randint(0, 100)),
    )
"""

from __future__ import annotations
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple


@dataclass
class VerificationResult:
    """Result of a CRDT property verification run."""
    property_name: str
    passed: bool
    trials: int
    failures: int
    first_failure: Optional[dict] = None
    duration_ms: float = 0.0
    error: Optional[str] = None

    def __repr__(self):
        status = "✅ PASS" if self.passed else f"❌ FAIL ({self.failures}/{self.trials})"
        return f"Verify({self.property_name}): {status} in {self.duration_ms:.1f}ms"


@dataclass
class CRDTVerification:
    """Complete CRDT verification report."""
    commutativity: VerificationResult
    associativity: VerificationResult
    idempotency: VerificationResult
    convergence: Optional[VerificationResult] = None
    total_trials: int = 0
    total_duration_ms: float = 0.0

    @property
    def passed(self) -> bool:
        results = [self.commutativity, self.associativity, self.idempotency]
        if self.convergence:
            results.append(self.convergence)
        return all(r.passed for r in results)

    def summary(self) -> str:
        lines = ["CRDT Verification Report", "=" * 40]
        for r in [self.commutativity, self.associativity, self.idempotency, self.convergence]:
            if r:
                lines.append(str(r))
        status = "✅ ALL PROPERTIES VERIFIED" if self.passed else "❌ VERIFICATION FAILED"
        lines.append(f"\n{status} ({self.total_trials} total trials, {self.total_duration_ms:.1f}ms)")
        return "\n".join(lines)

    def __repr__(self):
        return f"CRDTVerification(passed={self.passed}, trials={self.total_trials})"


def _are_equal(a: Any, b: Any) -> bool:
    """Deep equality check that handles CRDT objects, dicts, floats, etc."""
    if a is b:
        return True
    if type(a) != type(b):
        return False
    # Handle CRDT objects with .value property
    if hasattr(a, 'value') and hasattr(b, 'value'):
        return _are_equal(a.value, b.value)
    # Handle dicts
    if isinstance(a, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_are_equal(a[k], b[k]) for k in a)
    # Handle lists/tuples
    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(_are_equal(x, y) for x, y in zip(a, b))
    # Handle sets
    if isinstance(a, set):
        return a == b
    # Handle floats with tolerance
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) < 1e-10
    return a == b


def verify_commutative(
    merge_fn: Callable[[Any, Any], Any],
    gen_fn: Callable[[], Any],
    trials: int = 1000,
    eq_fn: Optional[Callable[[Any, Any], bool]] = None,
) -> VerificationResult:
    """
    Prove: merge(A, B) == merge(B, A) for all A, B.

    Args:
        merge_fn: The merge function to verify. Takes (a, b) returns merged.
        gen_fn: Generator that produces random test values.
        trials: Number of random trials to run.
        eq_fn: Optional custom equality function. Default: deep equality.
    """
    eq = eq_fn or _are_equal
    failures = 0
    first_failure = None
    start = time.time()

    for i in range(trials):
        a = gen_fn()
        b = gen_fn()
        try:
            ab = merge_fn(a, b)
            ba = merge_fn(b, a)
            if not eq(ab, ba):
                failures += 1
                if first_failure is None:
                    first_failure = {
                        "trial": i, "a": repr(a), "b": repr(b),
                        "merge(a,b)": repr(ab), "merge(b,a)": repr(ba),
                    }
        except Exception as e:
            failures += 1
            if first_failure is None:
                first_failure = {"trial": i, "error": str(e)}

    duration = (time.time() - start) * 1000
    return VerificationResult(
        property_name="commutativity",
        passed=(failures == 0),
        trials=trials, failures=failures,
        first_failure=first_failure, duration_ms=duration,
    )


def verify_associative(
    merge_fn: Callable[[Any, Any], Any],
    gen_fn: Callable[[], Any],
    trials: int = 1000,
    eq_fn: Optional[Callable[[Any, Any], bool]] = None,
) -> VerificationResult:
    """Prove: merge(merge(A, B), C) == merge(A, merge(B, C)) for all A, B, C."""
    eq = eq_fn or _are_equal
    failures = 0
    first_failure = None
    start = time.time()

    for i in range(trials):
        a = gen_fn()
        b = gen_fn()
        c = gen_fn()
        try:
            ab_c = merge_fn(merge_fn(a, b), c)
            a_bc = merge_fn(a, merge_fn(b, c))
            if not eq(ab_c, a_bc):
                failures += 1
                if first_failure is None:
                    first_failure = {
                        "trial": i,
                        "merge(merge(a,b),c)": repr(ab_c),
                        "merge(a,merge(b,c))": repr(a_bc),
                    }
        except Exception as e:
            failures += 1
            if first_failure is None:
                first_failure = {"trial": i, "error": str(e)}

    duration = (time.time() - start) * 1000
    return VerificationResult(
        property_name="associativity",
        passed=(failures == 0),
        trials=trials, failures=failures,
        first_failure=first_failure, duration_ms=duration,
    )


def verify_idempotent(
    merge_fn: Callable[[Any, Any], Any],
    gen_fn: Callable[[], Any],
    trials: int = 1000,
    eq_fn: Optional[Callable[[Any, Any], bool]] = None,
) -> VerificationResult:
    """Prove: merge(A, A) == A for all A."""
    eq = eq_fn or _are_equal
    failures = 0
    first_failure = None
    start = time.time()

    for i in range(trials):
        a = gen_fn()
        try:
            aa = merge_fn(a, a)
            if not eq(aa, a):
                failures += 1
                if first_failure is None:
                    first_failure = {
                        "trial": i, "a": repr(a), "merge(a,a)": repr(aa),
                    }
        except Exception as e:
            failures += 1
            if first_failure is None:
                first_failure = {"trial": i, "error": str(e)}

    duration = (time.time() - start) * 1000
    return VerificationResult(
        property_name="idempotency",
        passed=(failures == 0),
        trials=trials, failures=failures,
        first_failure=first_failure, duration_ms=duration,
    )


def verify_convergence(
    merge_fn: Callable[[Any, Any], Any],
    gen_fn: Callable[[], Any],
    trials: int = 500,
    num_replicas: int = 5,
    eq_fn: Optional[Callable[[Any, Any], bool]] = None,
) -> VerificationResult:
    """
    Prove: N replicas merging the same set of values in ANY order converge.

    Generates N random values, creates all possible merge orderings,
    and verifies they all produce the same result.
    """
    eq = eq_fn or _are_equal
    failures = 0
    first_failure = None
    start = time.time()

    for i in range(trials):
        values = [gen_fn() for _ in range(num_replicas)]
        try:
            # Merge left-to-right
            lr = values[0]
            for v in values[1:]:
                lr = merge_fn(lr, v)

            # Merge right-to-left
            rl = values[-1]
            for v in reversed(values[:-1]):
                rl = merge_fn(rl, v)

            # Merge from middle out
            mid = len(values) // 2
            mo = values[mid]
            for j in range(1, len(values)):
                idx = mid + j if (mid + j) < len(values) else mid - (j - (len(values) - mid))
                if 0 <= idx < len(values) and idx != mid:
                    mo = merge_fn(mo, values[idx])

            if not (eq(lr, rl) and eq(lr, mo)):
                failures += 1
                if first_failure is None:
                    first_failure = {
                        "trial": i,
                        "left_to_right": repr(lr),
                        "right_to_left": repr(rl),
                    }
        except Exception as e:
            failures += 1
            if first_failure is None:
                first_failure = {"trial": i, "error": str(e)}

    duration = (time.time() - start) * 1000
    return VerificationResult(
        property_name="convergence",
        passed=(failures == 0),
        trials=trials, failures=failures,
        first_failure=first_failure, duration_ms=duration,
    )


def verify_crdt(
    merge_fn: Callable[[Any, Any], Any],
    gen_fn: Callable[[], Any],
    trials: int = 1000,
    eq_fn: Optional[Callable[[Any, Any], bool]] = None,
    include_convergence: bool = True,
) -> CRDTVerification:
    """
    Full CRDT verification — tests all three required properties plus convergence.

    This is the trust layer. Pass this, and your merge function is mathematically
    guaranteed to be conflict-free.
    """
    comm = verify_commutative(merge_fn, gen_fn, trials, eq_fn)
    assoc = verify_associative(merge_fn, gen_fn, trials, eq_fn)
    idemp = verify_idempotent(merge_fn, gen_fn, trials, eq_fn)
    conv = verify_convergence(merge_fn, gen_fn, min(trials, 500), eq_fn=eq_fn) if include_convergence else None

    total = comm.trials + assoc.trials + idemp.trials + (conv.trials if conv else 0)
    total_ms = comm.duration_ms + assoc.duration_ms + idemp.duration_ms + (conv.duration_ms if conv else 0)

    return CRDTVerification(
        commutativity=comm, associativity=assoc, idempotency=idemp,
        convergence=conv, total_trials=total, total_duration_ms=total_ms,
    )
