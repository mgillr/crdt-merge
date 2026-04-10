# crdt_merge.model.continual — Continual Merge

**Module**: `crdt_merge/model/continual.py`
**Layer**: 4 — AI / Model / Agent
**Dependencies**: `crdt_merge.model.core`, `torch`

---

## Classes

### ContinualMerge

Merging models from continual/incremental learning pipelines.

```python
class ContinualMerge:
    def __init__(self, strategy: str = "ewc", importance_method: str = "fisher") -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `merge()` | `merge(old_model: dict, new_model: dict, importance: Optional[dict] = None) -> dict` | Merge preserving old knowledge |
| `compute_importance()` | `compute_importance(model: dict, data_loader) -> dict` | Compute parameter importance |
| `verify_no_forgetting()` | `verify_no_forgetting(merged: dict, old_model: dict, test_data) -> dict` | Verify catastrophic forgetting hasn't occurred |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class StabilityResult`

Result of measuring how much of a model's contribution is retained.

    Attributes
    ----------
    retention : float
        Overall retention score in [0, 1].  1.0 means the model's changes
        are fully preserved in the merged output; 0.0 means none are.
    per_layer : dict[str, float]
        Per-layer retention scores.
    

**Attributes:**
- `retention`: `float`
- `per_layer`: `Dict[str, float]`


### `ContinualMerge.export(self) → dict`

Return the current merged state_dict.

**Returns:** `dict`


### `ContinualMerge.history(self) → List[dict]`

List of absorption events.

**Returns:** `List[dict]`


### `ContinualMerge.current_weights(self) → Dict[str, float]`

Effective contribution weight of each absorbed model (after decay).

**Returns:** `Dict[str, float]`


### `ContinualMerge.reset(self, base_model: dict) → None`

Restart from a new base model, clearing all history.

**Parameters:**
- `base_model` (`dict`)

**Returns:** `None`


### `ContinualMerge.verify_convergence(self) → bool`

Check whether the current merge configuration guarantees CRDT convergence.

        Returns ``True`` when *all* of these hold:

        1. ``convergence="crdt"`` was set at construction.
        2. Per-layer CRDT states have been initialised.
        3. The underlying strategy declares ``commutative=True``,
           ``associative=True``, and ``idempotent=True`` (or the CRDT
           state container provides those guarantees).

        Returns
        -------
        bool
        

**Returns:** `bool`


### `ContinualMerge.measure_stability(self, model_name: str) → StabilityResult`

Measure how much of *model_name*'s contribution is retained.

        For each layer, computes the cosine similarity between the
        model's task vector (delta from base) and the merged task vector.
        A score of 1.0 means the model's change direction is perfectly
        preserved; 0.0 means it was entirely lost.

        Parameters
        ----------
        model_name : str
            Name of a previously absorbed model.

        Returns
        -------
        StabilityResult

        Raises
        ------
        KeyError
            If *model_name* was not absorbed.
        

**Parameters:**
- `model_name` (`str`)

**Returns:** `StabilityResult`

**Raises:** `KeyError(f"Model '{model_name}' not found.  Known: {[n for n in self._order if n != '__base__']}")`


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class DualProjectionMerge(ModelMergeStrategy)`

Dual-projection continual merge with CRDT guarantees.

    Decomposes task vectors (differences from a base model) into two
    orthogonal components via truncated SVD:

    * **Shared subspace** (top-k singular directions): captures consensus
      changes present across multiple models.  Merged with additive
      semantics (GCounter — commutative, associative, idempotent).
    * **Task-specific subspace** (orthogonal complement): captures
      changes unique to individual fine-tunes.  Merged with add-wins
      semantics (OR-Set — commutative, associative, idempotent).

    The ``stability_weight`` parameter interpolates between full
    plasticity (0.0 — all changes kept) and full stability (1.0 — only
    consensus changes kept).

    Parameters
    ----------
    stability_weight : float
        Balance between stability (1.0) and plasticity (0.0).
        Default: 0.5.
    rank_fraction : float
        Fraction of singular values to keep for the shared subspace.
        Default: 0.5.

    References
    ----------
    Yuan et al., "Dual-Projection Model Merging for Continual Learning",
    NeurIPS 2025.
    


### `DualProjectionMerge.name(self) → str`

*No docstring — needs documentation.*

**Returns:** `str`


### `DualProjectionMerge.category(self) → str`

*No docstring — needs documentation.*

**Returns:** `str`


### `DualProjectionMerge.paper_reference(self) → str`

*No docstring — needs documentation.*

**Returns:** `str`


### `DualProjectionMerge.crdt_properties(self) → Dict[str, Any]`

*No docstring — needs documentation.*

**Returns:** `Dict[str, Any]`


## Analysis Notes
