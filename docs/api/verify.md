# CRDT Law Verification

Property-based testing of commutativity, associativity, idempotency.

## Quick Example

```python
from crdt_merge.verify import verified_merge
@verified_merge(samples=100, key="id")
def my_merge(a, b, key="id"):
    return merge(a, b, key=key)
```

---

## API Reference

## `crdt_merge.verify`

> CRDT Verification Toolkit — runtime proof that merge functions are correct.

**Module:** `crdt_merge.verify`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `CRDTVerification(commutativity: 'VerificationResult', associativity: 'VerificationResult', idempotency: 'VerificationResult', convergence: 'Optional[VerificationResult]' = None, total_trials: 'int' = 0, total_duration_ms: 'float' = 0.0) -> None`

Complete CRDT verification report.

**Properties:**

- `passed` — 

**Methods:**

- `summary(self) -> 'str'` — 

#### `CRDTVerificationError(...)`

Raised when a merge function fails CRDT property verification.

#### `VerificationResult(property_name: 'str', passed: 'bool', trials: 'int', failures: 'int', first_failure: 'Optional[dict]' = None, duration_ms: 'float' = 0.0, error: 'Optional[str]' = None) -> None`

Result of a CRDT property verification run.

**Methods:**


### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.

#### `verified_merge(merge_fn=None, *, gen_fn: 'Optional[Callable]' = None, trials: 'int' = 100, eq_fn: 'Optional[Callable[[Any, Any], bool]]' = None, on_fail: 'str' = 'raise')`

Decorator that verifies a merge function satisfies CRDT laws at decoration time.

#### `verify_associative(merge_fn: 'Callable[[Any, Any], Any]', gen_fn: 'Callable[[], Any]', trials: 'int' = 1000, eq_fn: 'Optional[Callable[[Any, Any], bool]]' = None) -> 'VerificationResult'`

Prove: merge(merge(A, B), C) == merge(A, merge(B, C)) for all A, B, C.

#### `verify_commutative(merge_fn: 'Callable[[Any, Any], Any]', gen_fn: 'Callable[[], Any]', trials: 'int' = 1000, eq_fn: 'Optional[Callable[[Any, Any], bool]]' = None) -> 'VerificationResult'`

Prove: merge(A, B) == merge(B, A) for all A, B.

#### `verify_convergence(merge_fn: 'Callable[[Any, Any], Any]', gen_fn: 'Callable[[], Any]', trials: 'int' = 500, num_replicas: 'int' = 5, eq_fn: 'Optional[Callable[[Any, Any], bool]]' = None) -> 'VerificationResult'`

Prove: N replicas merging the same set of values in ANY order converge.

#### `verify_crdt(merge_fn: 'Callable[[Any, Any], Any]', gen_fn: 'Callable[[], Any]', trials: 'int' = 1000, eq_fn: 'Optional[Callable[[Any, Any], bool]]' = None, include_convergence: 'bool' = True) -> 'CRDTVerification'`

Full CRDT verification — tests all three required properties plus convergence.

#### `verify_idempotent(merge_fn: 'Callable[[Any, Any], Any]', gen_fn: 'Callable[[], Any]', trials: 'int' = 1000, eq_fn: 'Optional[Callable[[Any, Any], bool]]' = None) -> 'VerificationResult'`

Prove: merge(A, A) == A for all A.

#### `wraps(wrapped, assigned=('__module__', '__name__', '__qualname__', '__doc__', '__annotations__', '__type_params__'), updated=('__dict__',))`

Decorator factory to apply update_wrapper() to a wrapper function



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
