# crdt_merge.verify — CRDT Verification

**Module**: `crdt_merge/verify.py`
**Layer**: 1 — Core CRDT Primitives
**LOC**: 448
**Dependencies**: `crdt_merge.core`, `crdt_merge.strategies`, `crdt_merge.clocks`

---

## Overview

Formal verification tools for CRDT properties. Validates that merge operations are commutative, associative, and idempotent using property-based testing.

---

## Functions

### verify_crdt()
```python
def verify_crdt(crdt_class: type, num_tests: int = 100) -> VerificationResult
```
Run property-based verification on a CRDT class.

**Tests**:
1. Commutativity: `a.merge(b) == b.merge(a)`
2. Associativity: `a.merge(b).merge(c) == a.merge(b.merge(c))`
3. Idempotency: `a.merge(a) == a`

**Returns**: `VerificationResult` with pass/fail for each property.

### verified_merge (decorator)
```python
@verified_merge
def my_merge_function(a, b): ...
```
Decorator that wraps a merge function to verify CRDT properties at runtime. Raises `CRDTViolationError` if any property fails.

---

## Classes

### CRDTVerifier

Comprehensive CRDT verifier with configurable test generation.

```python
class CRDTVerifier:
    def __init__(self, num_tests: int = 100, seed: Optional[int] = None) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `verify_commutativity()` | `verify_commutativity(merge_fn, generator) -> bool` | Test commutativity |
| `verify_associativity()` | `verify_associativity(merge_fn, generator) -> bool` | Test associativity |
| `verify_idempotency()` | `verify_idempotency(merge_fn, generator) -> bool` | Test idempotency |
| `verify_all()` | `verify_all(merge_fn, generator) -> VerificationResult` | Run all three tests |
| `report()` | `report() -> str` | Human-readable report |

### VerificationResult
```python
@dataclass
class VerificationResult:
    commutative: bool
    associative: bool
    idempotent: bool
    num_tests: int
    failures: List[str]
```


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class CRDTVerification`

Complete CRDT verification report.

**Attributes:**
- `commutativity`: `VerificationResult`
- `associativity`: `VerificationResult`
- `idempotency`: `VerificationResult`
- `convergence`: `Optional[VerificationResult]`
- `total_trials`: `int`
- `total_duration_ms`: `float`



### `CRDTVerification.passed(self) → bool`

Returns `True` if all CRDT properties (commutativity, associativity, idempotency, and optionally convergence) passed verification. A single failure in any property causes this to return `False`.

**Returns:** `bool`



### `CRDTVerification.summary(self) → str`

Returns a human-readable multi-line verification report. Includes results for each CRDT property, a final ✅/❌ status line, and total trial count with duration in milliseconds.

**Returns:** `str`



### `class CRDTVerificationError(Exception)`

Raised when a merge function fails CRDT property verification.



---

## Standalone Verification Functions

*Discovered during Team 4 RREA re-analysis. These are the individual verification functions that `verify_crdt()` delegates to.*

### `verify_commutative(merge_fn: Callable, gen_fn: Callable, trials: int = 100, eq_fn: Optional[Callable] = None) -> VerificationResult`

Prove: `merge(A, B) == merge(B, A)` for all A, B.

**Parameters:**
- `merge_fn` (`Callable[[Any, Any], Any]`): The merge function to verify
- `gen_fn` (`Callable[[], Any]`): Generator that produces random test values
- `trials` (`int`): Number of random trials to run. Default: 100
- `eq_fn` (`Optional[Callable[[Any, Any], bool]]`): Custom equality function. Default: deep equality

**Returns:** `VerificationResult`

### `verify_associative(merge_fn: Callable, gen_fn: Callable, trials: int = 100, eq_fn: Optional[Callable] = None) -> VerificationResult`

Prove: `merge(merge(A, B), C) == merge(A, merge(B, C))` for all A, B, C.

**Parameters:**
- `merge_fn` (`Callable[[Any, Any], Any]`): The merge function to verify
- `gen_fn` (`Callable[[], Any]`): Generator for random test values
- `trials` (`int`): Number of trials. Default: 100
- `eq_fn` (`Optional[Callable]`): Custom equality function

**Returns:** `VerificationResult`

### `verify_idempotent(merge_fn: Callable, gen_fn: Callable, trials: int = 100, eq_fn: Optional[Callable] = None) -> VerificationResult`

Prove: `merge(A, A) == A` for all A.

**Parameters:**
- `merge_fn` (`Callable[[Any, Any], Any]`): The merge function to verify
- `gen_fn` (`Callable[[], Any]`): Generator for random test values
- `trials` (`int`): Number of trials. Default: 100
- `eq_fn` (`Optional[Callable]`): Custom equality function

**Returns:** `VerificationResult`

### `verify_convergence(merge_fn: Callable, gen_fn: Callable, trials: int = 100, num_replicas: int = 3, eq_fn: Optional[Callable] = None) -> VerificationResult`

Prove: N replicas merging the same set of values in ANY order converge.

Generates N random values, merges them in three different orderings (left-to-right, right-to-left, random shuffle), and verifies all orderings produce the same result.

**Parameters:**
- `merge_fn` (`Callable`): The merge function to verify
- `gen_fn` (`Callable`): Generator for random values
- `trials` (`int`): Number of trials. Default: 100
- `num_replicas` (`int`): Number of replicas to simulate. Default: 3
- `eq_fn` (`Optional[Callable]`): Custom equality function

**Returns:** `VerificationResult`

---

## Internal/Private API

### `_are_equal(a: Any, b: Any) -> bool`

Deep equality check that handles CRDT objects, DataFrames, dicts, floats (with epsilon), and nested structures.

**Parameters:**
- `a` (`Any`): First value
- `b` (`Any`): Second value

**Returns:** `bool`

**RREA Classification:** SHADOW — core equality helper used by all verification functions.

---

## Magic Methods (Missing from initial docs)

### `VerificationResult.__repr__(self)`

Returns string representation showing pass/fail status and trial count.

### `CRDTVerification.__repr__(self)`

Returns string representation showing all four verification results and total duration.

---

## RREA Priority Analysis

| Symbol | Classification | Entropy | Reachability Score |
|--------|---------------|---------|-------------------|
| `VerificationResult` | SPECIALIZED | **0.5186** | **11.6 — #1 entropy chokepoint in Layer 1** |
| `CRDTVerification` | SPECIALIZED | 0.2714 | 4.7 |
| `verify_commutative` | SPECIALIZED | 0.2714 | 4.7 |
| `verify_associative` | SPECIALIZED | 0.2714 | 4.7 |
| `verify_idempotent` | SPECIALIZED | 0.2714 | 4.7 |
| `verify_convergence` | SPECIALIZED | 0.2714 | 4.7 |
| `verify_crdt` | SPECIALIZED | — | Public entry point |
| `verified_merge` | SPECIALIZED | — | Decorator entry point |
| `CRDTVerificationError` | SPECIALIZED | — | Error type |
| `_are_equal` | SHADOW | — | **Core equality logic**, used by ALL verify functions |

> ⚠️ **CRITICAL CHOKEPOINT:** `VerificationResult` has the highest entropy (0.5186) and reachability (11.6) of ANY symbol in Layer 1. It is the convergence point for all verification operations and should have comprehensive documentation and testing.

---

## Chokepoint Analysis

### VerificationResult — #1 Entropy Chokepoint in Layer 1

`VerificationResult` is classified as a **SPECIALIZED** node with the highest combined entropy and reachability score in the entire Layer 1 (Core CRDT Primitives) module group.

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **Entropy (H)** | **0.5186** | High information density — many distinct states flow through this type |
| **Reachability Score** | **11.6** | Highest in Layer 1 — 11.6 distinct paths converge on this symbol |
| **Node Type** | SPECIALIZED | High fan-in from all verification functions |

### Why This Matters

`VerificationResult` is the **universal return type** for all verification functions:

- `verify_commutative()` → `VerificationResult`
- `verify_associative()` → `VerificationResult`
- `verify_idempotent()` → `VerificationResult`
- `verify_convergence()` → `VerificationResult`

It is also consumed by `CRDTVerification` (which aggregates four `VerificationResult` instances) and by the `@verified_merge` decorator (which stores the result on the decorated function).

**Any change to `VerificationResult`'s API surface propagates to every downstream consumer.** This includes:
- Adding/removing/renaming fields
- Changing the semantics of `.passed` or `.failures`
- Modifying `__repr__` output (which may be parsed by CI/CD pipelines)

### Top 5 Layer 1 Entropy Chokepoints

| Rank | Symbol | Module | Entropy (H) | Reachability | Type |
|------|--------|--------|-------------|-------------|------|
| 1 | `VerificationResult` | `verify.py` | 0.5186 | 11.6 | SPECIALIZED |
| 2 | `CRDTVerification` | `verify.py` | 0.2714 | 4.7 | SPECIALIZED |
| 3 | `verify_commutative` | `verify.py` | 0.2714 | 4.7 | SPECIALIZED |
| 4 | `verify_associative` | `verify.py` | 0.2714 | 4.7 | SPECIALIZED |
| 5 | `verify_idempotent` | `verify.py` | 0.2714 | 4.7 | SPECIALIZED |

> **Note:** `MergeStrategy` in `strategies.py` has since been identified as the #1 entropy chokepoint *across all of Layer 1* with combined H=0.722 (see [strategies.md](strategies.md)). `VerificationResult` remains the #1 chokepoint within the `verify.py` module.

### Stability Guarantee

`VerificationResult` is a **frozen interface**. Its dataclass fields (`property_name`, `passed`, `trials`, `failures`, `first_failure`, `duration_ms`, `error`) are guaranteed stable across minor versions. New optional fields may be added but existing fields will not be removed or renamed.

---

## Inherited Methods on CRDTVerificationError (GDEPA Runtime Discovery)

*Discovered by Team 3 GDEPA runtime introspection (2026-03-31). These standard Exception methods were undocumented.*

### `CRDTVerificationError.add_note(note: str) -> None`

Add a note to the exception. Notes are appended to the exception's `__notes__` list and displayed in tracebacks.

**Inherited from:** `BaseException` (Python 3.11+)

```python
try:
    verify_crdt(my_crdt)
except CRDTVerificationError as e:
    e.add_note("Occurred during nightly regression test")
    e.add_note(f"Test config: {config}")
    raise
```

**Output:**
```
CRDTVerificationError: Commutativity check failed
Occurred during nightly regression test
Test config: {'num_tests': 1000, 'seed': 42}
```

### `CRDTVerificationError.with_traceback(tb) -> Self`

Set the traceback for the exception and return the exception instance. Used for exception chaining and re-raising with modified tracebacks.

**Inherited from:** `BaseException`

```python
try:
    verify_crdt(my_crdt)
except CRDTVerificationError as e:
    # Re-raise with a different traceback
    raise e.with_traceback(None) from e
```

> **Note:** These are standard Python `Exception` inherited methods. They are included here for completeness since GDEPA runtime introspection identified them as undocumented on `CRDTVerificationError` specifically. The `add_note()` method requires Python 3.11+.
