# `crdt_merge/model/continual_verify.py`

> Convergence verification for continual merge sequences.

Provides ``ConvergenceProof`` which empirically verifies that a
``ContinualMerge`` instance satisfies the three CRDT laws:

* **Commutativity** — absorbing models in any order yields the same result.
* **Associativity** — grouping absorptions 

**Source:** `crdt_merge/model/continual_verify.py` | **Lines:** 353

---

**Exports (`__all__`):** `['ConvergenceProof', 'VerifyResult', 'FullVerifyResult']`

## Classes

### `class VerifyResult`

Outcome of a single CRDT-property verification.

    Attributes
    ----------
    passed : bool
        Whether the property held within tolerance.
    property_name : str
        Name of the verified property (e.g. ``"commutativity"``).
    max_deviation : float
        Maximum element-wise deviation observed across all layers.
    details : str
        Human-readable explanation.

- `passed`: `bool`
- `property_name`: `str`
- `max_deviation`: `float`
- `details`: `str`

### `class FullVerifyResult`

Aggregate outcome of verifying all three CRDT properties.

    Attributes
    ----------
    all_passed : bool
        ``True`` only if every individual property passed.
    results : list[VerifyResult]
        Per-property results.

- `all_passed`: `bool`
- `results`: `List[VerifyResult]`

### `class ConvergenceProof`

Verify CRDT convergence properties for continual merge sequences.

    Parameters
    ----------
    merge : ContinualMerge
        A template ``ContinualMerge`` instance whose configuration
        (strategy, memory_budget, convergence mode) will be used for
        verification.  The base model is taken from this instance.


**Methods:**

#### `ConvergenceProof.__init__(self, merge: ContinualMerge) → None`

*No docstring*

#### `ConvergenceProof.verify_commutativity(self, models: List[dict], tolerance: float = 1e-06) → VerifyResult`

Verify that absorption order does not affect the merged result.

        Absorbs *models* in the given order and in reverse order, then
        compares the two exported state dicts.

        Parameters
        ----------
        models : list[dict]
            Model state dicts to absorb.
        tolerance : float
            Maximum allowed element-wise deviation.

        Returns
        -------
        VerifyResult

#### `ConvergenceProof.verify_associativity(self, models: List[dict], tolerance: float = 1e-06) → VerifyResult`

Verify that grouping of absorptions does not affect the result.

        Compares absorbing all models in one pass vs absorbing them in
        two separate groups (first half, then second half as a fresh
        merge against the same base).

        Parameters
        ----------
        models : list[dict]
            Model state dicts (need at least 3 for a meaningful test).
        tolerance : float
            Maximum allowed element-wise deviation.

        Returns
        -------
        VerifyResult

#### `ConvergenceProof.verify_idempotency(self, model: dict, tolerance: float = 1e-06) → VerifyResult`

Verify idempotency of the merge operation.

        Creates a ``ContinualMerge`` whose base is *model*, then absorbs
        *model* again.  If the merge is idempotent, the exported result
        should be identical to *model* (merge(x, x) == x).

        Parameters
        ----------
        model : dict
            A single model state dict.
        tolerance : float
            Maximum allowed element-wise deviation.

        Returns
        -------
        VerifyResult

#### `ConvergenceProof.verify_all(self, models: List[dict], tolerance: float = 1e-06) → FullVerifyResult`

Run all three CRDT property verifications.

        Parameters
        ----------
        models : list[dict]
            Model state dicts (at least 3 recommended).
        tolerance : float
            Maximum allowed element-wise deviation.

        Returns
        -------
        FullVerifyResult


## Functions

### `_max_layer_deviation(a: dict, b: dict) → float`

Compute the maximum element-wise deviation between two state dicts.

### `_build_cm(template: ContinualMerge) → ContinualMerge`

Create a fresh ContinualMerge with the same config and base model.


## Analysis Notes
