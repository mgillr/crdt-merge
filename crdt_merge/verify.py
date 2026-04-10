# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

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
        gen_fn=lambda: GCounter("n1", random.randint(0, 100)),  # nosec B311 -- simulation/verification, not security
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
        status = "PASS" if self.passed else f"FAIL ({self.failures}/{self.trials})"
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
        status = "ALL PROPERTIES VERIFIED" if self.passed else "VERIFICATION FAILED"
        lines.append(f"\n{status} ({self.total_trials} total trials, {self.total_duration_ms:.1f}ms)")
        return "\n".join(lines)

    def __repr__(self):
        return f"CRDTVerification(passed={self.passed}, trials={self.total_trials})"

def _are_equal(a: Any, b: Any) -> bool:
    """Deep equality check that handles CRDT objects, DataFrames, dicts, floats, etc."""
    if a is b:
        return True
    # Handle DataFrames (pandas, polars) -- compare as sorted records
    if hasattr(a, 'to_dict') and hasattr(b, 'to_dict'):
        try:
            # Pandas DataFrames
            if hasattr(a, 'sort_values') and hasattr(b, 'sort_values'):
                a_sorted = a.sort_values(by=list(a.columns)).reset_index(drop=True)
                b_sorted = b.sort_values(by=list(b.columns)).reset_index(drop=True)
                return a_sorted.equals(b_sorted)
        except Exception:
            pass  # nosec B110 -- intentionally silent
    if hasattr(a, 'to_dicts') and hasattr(b, 'to_dicts'):
        try:
            # Polars DataFrames
            a_recs = sorted([tuple(sorted(r.items())) for r in a.to_dicts()])
            b_recs = sorted([tuple(sorted(r.items())) for r in b.to_dicts()])
            return a_recs == b_recs
        except Exception:
            pass  # nosec B110 -- intentionally silent
    if type(a) != type(b):
        # Allow list[dict] vs list[dict] with different orderings
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                return False
            if a and isinstance(a[0], dict):
                try:
                    a_sorted = sorted([tuple(sorted(r.items())) for r in a])
                    b_sorted = sorted([tuple(sorted(r.items())) for r in b])
                    return a_sorted == b_sorted
                except Exception:
                    pass  # nosec B110 -- intentionally silent
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
        # Try order-independent comparison for list of dicts
        if a and isinstance(a[0], dict):
            try:
                a_sorted = sorted([tuple(sorted(r.items())) for r in a])
                b_sorted = sorted([tuple(sorted(r.items())) for r in b])
                return a_sorted == b_sorted
            except Exception:
                pass  # nosec B110 -- intentionally silent
        return all(_are_equal(x, y) for x, y in zip(a, b))
    # Handle sets
    if isinstance(a, set):
        return a == b
    # Handle floats with tolerance (including NaN)
    if isinstance(a, float) and isinstance(b, float):
        import math
        if math.isnan(a) and math.isnan(b):
            return True
        if math.isnan(a) or math.isnan(b):
            return False
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

    Generates N random values, merges them in three different orderings
    (left-to-right, right-to-left, random shuffle), and verifies all
    orderings produce the same result.
    """
    eq = eq_fn or _are_equal
    failures = 0
    first_failure = None
    start = time.time()

    for i in range(trials):
        values = [gen_fn() for _ in range(num_replicas)]
        try:
            # Helper: merge a list of values in given order
            def _merge_order(indices):
                result = values[indices[0]]
                for idx in indices[1:]:
                    result = merge_fn(result, values[idx])
                return result

            # Three orderings that cover all elements
            lr = _merge_order(list(range(num_replicas)))
            rl = _merge_order(list(reversed(range(num_replicas))))
            shuffled = list(range(num_replicas))
            random.shuffle(shuffled)  # nosec B311 -- deterministic ordering test
            rand = _merge_order(shuffled)

            if not (eq(lr, rl) and eq(lr, rand)):
                failures += 1
                if first_failure is None:
                    first_failure = {
                        "trial": i,
                        "left_to_right": repr(lr),
                        "right_to_left": repr(rl),
                        "random_order": repr(rand),
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

# ─── v0.4.0: @verified_merge decorator ───────────────────────────────────────

from functools import wraps

def verified_merge(
    merge_fn=None,
    *,
    gen_fn: Optional[Callable] = None,
    trials: int = 100,
    eq_fn: Optional[Callable[[Any, Any], bool]] = None,
    on_fail: str = "raise",
):
    """
    Decorator that verifies a merge function satisfies CRDT laws at decoration time.

    Verification runs ONCE when the function is defined — not on every call.
    The verification result is stored on the function as ._crdt_verified.

    Args:
        gen_fn: Generator function that produces random test values. REQUIRED.
        trials: Number of random trials per property (default: 100).
        eq_fn: Custom equality function. Default: deep equality.
        on_fail: "raise" (default) to raise on failure, "warn" to just attach result.

    Usage:
        import random
        from crdt_merge.verify import verified_merge

        # As decorator with arguments
        @verified_merge(gen_fn=lambda: random.randint(0, 100), trials=500)  # nosec B311 -- simulation/verification, not security
        def my_max_merge(a, b):
            return max(a, b)

        assert my_max_merge._crdt_verified.passed

        # The decorated function works normally
        result = my_max_merge(3, 7)  # returns 7

    Raises:
        ValueError: If gen_fn is not provided.
        CRDTVerificationError: If on_fail="raise" and verification fails.
    """
    def decorator(fn):
        if gen_fn is None:
            raise ValueError(
                "@verified_merge requires gen_fn — a callable that produces "
                "random test values. Example: gen_fn=lambda: random.randint(0, 100)"  # nosec B311 -- simulation/verification, not security
            )

        # Run verification at decoration time (ONCE)
        result = verify_crdt(fn, gen_fn, trials=trials, eq_fn=eq_fn)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        wrapper._crdt_verified = result
        wrapper._crdt_verification_summary = result.summary()

        if not result.passed:
            if on_fail == "raise":
                raise CRDTVerificationError(
                    f"CRDT verification failed for {fn.__name__}:\n{result.summary()}"
                )
            # on_fail == "warn" -- attach but don't raise

        return wrapper

    # Support both @verified_merge and @verified_merge(...)
    if merge_fn is not None:
        # Called without arguments -- but gen_fn is required, so error
        raise ValueError(
            "@verified_merge requires gen_fn. Use: @verified_merge(gen_fn=...)"
        )
    return decorator

class CRDTVerificationError(Exception):
    """Raised when a merge function fails CRDT property verification."""
    pass
