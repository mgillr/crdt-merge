# crdt_merge.model.crdt_state — CRDTMergeState

**Module**: `crdt_merge/model/crdt_state.py`
**Layer**: 4 — AI / Model / Agent
**Dependencies**: `crdt_merge.core`, `crdt_merge.clocks`

---

## Overview

CRDT-backed state management for model merge operations. Tracks merge history, version vectors, and enables convergent multi-party model merging.

---

## Classes

### CRDTMergeState

```python
class CRDTMergeState:
    def __init__(self, node_id: str) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `record_merge()` | `record_merge(model_ids: List[str], strategy: str, result_hash: str) -> None` | Record a merge operation |
| `get_version()` | `get_version() -> VectorClock` | Current version vector |
| `merge_state()` | `merge_state(other: CRDTMergeState) -> CRDTMergeState` | Merge two states (CRDT compliant) |
| `history()` | `history() -> List[MergeRecord]` | Full merge history |
| `to_dict()` | `to_dict() -> dict` | Serialize |
| `from_dict()` | `@classmethod from_dict(cls, d: dict) -> CRDTMergeState` | Deserialize |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class ConflictResolution(str, Enum)`

Strategy for resolving conflicts when the same model_id appears twice.

**Attributes:**
- `FIRST_WRITE_WINS`
- `LAST_WRITE_WINS`
- `HIGHEST_VERSION`



### `class MergeContribution`

A single model contribution in the CRDT state.

    Each contribution is content-addressable via its Merkle hash,
    enabling provenance tracking and integrity verification.
    

**Attributes:**
- `__slots__`



### `CRDTMergeState.remove(self, model_id: str) → 'CRDTMergeState'`

Remove a model contribution by ID (OR-Set remove).

        Only removes the current version. A newer ``add()`` with the
        same model_id will override the remove (add-wins).

        Returns
        -------
        self : CRDTMergeState

        .. note:: Not thread-safe — see class docstring.
        

**Parameters:**
- `model_id` (`str`)

**Returns:** `'CRDTMergeState'`



### `CRDTMergeState.merge_many(cls, states: List['CRDTMergeState']) → 'CRDTMergeState'`

Merge N states at once (more efficient than chained pairwise merges).

        Performs a single-pass union over all contribution sets, avoiding
        the O(N²) intermediate-state overhead of sequential pairwise
        ``merge()`` calls.

        The result is identical to ``s1.merge(s2).merge(s3)...`` in any
        order (by CRDT associativity and commutativity).

        Parameters
        ----------
        states : list of CRDTMergeState
            Two or more states to merge. All must share the same
            ``strategy_name``.

        Returns
        -------
        merged : CRDTMergeState
            New state containing the union of all contribution sets.

        Raises
        ------
        ValueError
            If *states* is empty or contains inconsistent strategy names.
        

**Parameters:**
- `states` (`List['CRDTMergeState']`)

**Returns:** `'CRDTMergeState'`

**Raises:** `ValueError('merge_many() requires at least one state')`



### `CRDTMergeState.resolve(self) → Any`

Apply the merge strategy atomically to all contributions.

        This is the **resolution function** — a deterministic pure function
        that produces the same output from the same set of contributions,
        regardless of the order they were added or merged.

        Returns
        -------
        merged_tensor : numpy.ndarray or list
            The merged model weights.

        Raises
        ------
        ValueError
            If the state is empty or base is missing for strategies that need it.
        

**Returns:** `Any`

**Raises:** `ValueError('Cannot resolve empty CRDT state with no base model')`



### `CRDTMergeState.size(self) → int`

Number of active contributions.

**Returns:** `int`



### `CRDTMergeState.is_empty(self) → bool`

*No docstring — needs documentation.*

**Returns:** `bool`



### `CRDTMergeState.needs_base(self) → bool`

Whether this state's strategy requires a base model.

**Returns:** `bool`



### `CRDTMergeState.is_stochastic(self) → bool`

Whether this state's strategy has internal RNG.

**Returns:** `bool`



### `CRDTMergeState.estimated_memory_bytes(self) → int`

Estimate the total memory footprint of this state in bytes.

        Accounts for tensor data in all contributions (active and
        tombstoned entries still held in ``_contributions``), the base
        model tensor, and a fixed overhead estimate for Python objects.

        Returns
        -------
        int
            Estimated memory usage in bytes.
        

**Returns:** `int`



### `CRDTMergeState.get_contribution(self, model_id: str) → Optional[MergeContribution]`

Get a specific contribution by model ID.

**Parameters:**
- `model_id` (`str`)

**Returns:** `Optional[MergeContribution]`



### `CRDTMergeState.provenance(self) → List[Dict[str, Any]]`

Return provenance trail for all contributions.

**Returns:** `List[Dict[str, Any]]`


## Shadow Dependencies

### 5 PyTorch / NumPy Tensor Operations

`CRDTMergeState` and `MergeContribution` rely on 5 implicit tensor method calls that constitute shadow dependencies on NumPy (and, by extension, PyTorch when tensors originate from `torch.Tensor`):

| Method | Location | Purpose |
|--------|----------|---------|
| `.tobytes()` | `MergeContribution._compute_hash()`, `CRDTMergeState._auto_id()` | Serializes tensor to raw bytes for SHA-256 Merkle hashing. Called via `np.asarray(tensor).tobytes()`. |
| `.tolist()` | `MergeContribution.to_dict()`, `CRDTMergeState.to_dict()` | Converts NumPy array to nested Python lists for JSON-safe wire serialization. Called via `np.asarray(tensor).tolist()`. |
| `.nbytes` | `CRDTMergeState.estimated_memory_bytes` | Reads the byte-size of tensor data for memory estimation. Called via `np.asarray(tensor).nbytes`. |
| `.shape` | `CRDTMergeState._validate_tensor_shape()` | Compares tensor dimensionality to enforce shape consistency across contributions. Called via `np.asarray(tensor).shape`. |
| `np.asarray()` | Throughout module | Converts input tensors (lists, PyTorch tensors, etc.) to `np.ndarray`. This is the primary entry point that enables all other operations. |

#### Notes

- All 5 operations are **standard NumPy ndarray methods/attributes** — they do not require PyTorch at runtime.
- When PyTorch tensors are passed in, `np.asarray()` triggers an implicit `.detach().cpu().numpy()` conversion (via PyTorch's `__array__` protocol). This is the mechanism by which PyTorch tensors are consumed without an explicit `import torch`.
- The module includes `try/except ImportError` fallbacks for all NumPy paths, allowing pure-Python operation with list-based tensors when NumPy is unavailable.

---

## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 4
- Inherited methods: 34 (ConflictResolution (from str))
- Circular dependencies: None

### RREA Findings
- Entropy profile: Low (shadow deps present)
- Dead code: None
- Shadow dependencies: `contrib._tag` → `CRDTMergeState`, `contrib.merkle_hash` → `CRDTMergeState`, `contrib.metadata` → `CRDTMergeState`, `contrib.model_id` → `CRDTMergeState`, `contrib.tensor` → `CRDTMergeState`
- Chokepoint status: None

### Code Quality (Team 2)
- Docstring coverage: 81.8%
- `__all__` defined: Yes
- Code smells: None

### Second Pass
- Heightened findings: None (all 1,063 new inherited methods classified as false positive dunders)
