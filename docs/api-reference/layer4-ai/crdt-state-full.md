# Crdt State

> CRDT-Aware Merge State — the layer that makes ALL 26 strategies true CRDTs.

**Source:** `crdt_merge/model/crdt_state.py`  
**Lines of Code:** 928

## Overview

Architecture
============

The original ``crdt-merge`` architecture tried to make each merge strategy's
``merge()`` function satisfy CRDT laws (commutativity, associativity,
idempotency) directly on raw tensors. This is **mathematically impossible**
for most model-merge algorithms (SLERP, TIES, DARE, Fisher, etc.).

The solution is a **two-layer architecture** that separates concerns:

    Layer 1 — CRDT State (this module)
        Manages a set of model contributions with provably correct CRDT
        semantics. The merge operation is **set union** which is trivially
        commutative, associative, and idempotent.

    Layer 2 — Strategy (existing ``strategies/`` modules)
        Pure functions that compute a merged model from a set of inputs.
        Applied atomically during ``resolve()`` — never pairwise.

``CRDTMergeState`` provides the CRDT wrapper layer that makes all 25
strategies satisfy the three CRDT laws. Implementation internals are
proprietary — see LICENSE and PATENTS for details.

Usage
=====

::

    from crdt_merge.model.crdt_state import CRDTMergeState

    # Node A creates state and adds its model
    state_a = CRDTMergeState("weight_average")
    state_a.add(tensor_a, model_id="llama-7b-node-a", weight=1.0)

    # Node B creates state and adds its model
    state_b = CRDTMergeState("weight_average")
    state_b.add(tensor_b, model_id="llama-7b-node-b", weight=1.0)

    # Any merge order produces identical states
    merged_1 = state_a.merge(state_b)
    merged_2 = state_b.merge(state_a)
    assert merged_1 == merged_2                 # CRDT guarantee

    # Resolve to get the actual merged tensor
    result = merged_1.resolve()

    # Works with ANY strategy — all 25 are true CRDTs
    state_ties = CRDTMergeState("ties", base=pretrained_base)
    state_ties.add(finetuned_a, model_id="ft-a")
    state_ties.add(finetuned_b, model_id="ft-b")
    merged_model = state_ties.resolve()

## Classes

### `ConflictResolution(str, Enum)`

Strategy for resolving conflicts when the same model_id appears twice.

**Class Attributes:**

- `FIRST_WRITE_WINS` — `'first_write_wins'`
- `LAST_WRITE_WINS` — `'last_write_wins'`
- `HIGHEST_VERSION` — `'highest_version'`

### `MergeContribution`

A single model contribution in the CRDT state.

**Class Attributes:**

- `__slots__` — `('model_id', 'tensor', 'weight', 'version', 'metadata', 'merkle_hash', 'times...`

**Constructor:**

```python
MergeContribution(model_id: str, tensor: Any, weight: float = 1.0, version: int = 1, metadata: Optional[Dict[str, Any]] = None, timestamp: Optional[float] = None)
```

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `to_dict` | `to_dict() -> dict` | Serialize for wire transfer. |
| `from_dict` | `from_dict(d: dict) -> MergeContribution` | Deserialize from wire format. |

**Special Methods:**

- `__repr__() -> str` — —

**Internal Methods:**

- `_compute_hash() -> str` — Compute SHA-256 hash of contribution content.

### `CRDTMergeState`

Conflict-Free Replicated merge state for model merging.

**Class Attributes:**

- `__slots__` — `('strategy_name', 'base', 'conflict_resolution', 'seed', '_contributions', '_...`
- `KNOWN_STRATEGIES` — `frozenset({'weight_average', 'slerp', 'task_arithmetic', 'linear', 'weight_sc...`
- `BASE_REQUIRED` — `frozenset({'task_arithmetic', 'ties', 'dare', 'della', 'dare_ties', 'model_br...`
- `STOCHASTIC` — `frozenset({'dare', 'della', 'dare_ties', 'evolutionary_merge', 'genetic_merge'})`

**Constructor:**

```python
CRDTMergeState(strategy_name: str, base: Any = None, conflict_resolution: ConflictResolution = ConflictResolution.HIGHEST_VERSION, seed: Optional[int] = None)
```

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `add` | `add(tensor: Any, model_id: Optional[str] = None, weight: float = 1.0, version: int = 1, metadata: Optional[Dict[str, Any]] = None) -> 'CRDTMergeState'` | Add a model contribution to the merge set. |
| `add_batch` | `add_batch(contributions: List[Union[Tuple[Any, str], Tuple[Any, str, float], Tuple[Any, str, float, int], Dict[str, Any]]]) -> 'CRDTMergeState'` | Add multiple model contributions at once. |
| `remove` | `remove(model_id: str) -> 'CRDTMergeState'` | Remove a model contribution by ID (OR-Set remove). |
| `merge` | `merge(other: 'CRDTMergeState') -> 'CRDTMergeState'` | CRDT merge: set union of contributions with conflict resolution. |
| `merge_many` | `merge_many(states: List['CRDTMergeState']) -> 'CRDTMergeState'` | Merge N states at once (more efficient than chained pairwise merges). |
| `resolve` | `resolve() -> Any` | Apply the merge strategy atomically to all contributions. |
| `model_ids` | `model_ids() -> List[str]` | List of model IDs currently in the set (excluding tombstoned). |
| `size` | `size() -> int` | Number of active contributions. |
| `is_empty` | `is_empty() -> bool` | — |
| `needs_base` | `needs_base() -> bool` | Whether this state's strategy requires a base model. |
| `is_stochastic` | `is_stochastic() -> bool` | Whether this state's strategy has internal RNG. |
| `estimated_memory_bytes` | `estimated_memory_bytes() -> int` | Estimate the total memory footprint of this state in bytes. |
| `get_contribution` | `get_contribution(model_id: str) -> Optional[MergeContribution]` | Get a specific contribution by model ID. |
| `provenance` | `provenance() -> List[Dict[str, Any]]` | Return provenance trail for all contributions. |
| `to_dict` | `to_dict() -> dict` | Serialize the full CRDT state for wire transfer. |
| `from_dict` | `from_dict(d: dict) -> 'CRDTMergeState'` | Deserialize from wire format. |

**Special Methods:**

- `__eq__(other: object) -> bool` — Two states are equal if they have the same active contribution set.
- `__hash__() -> int` — —
- `__repr__() -> str` — —

**Internal Methods:**

- `_invalidate_cache() -> None` — Invalidate the active-contributions cache.
- `_active_contributions() -> Dict[str, MergeContribution]` — Get contributions not in tombstones.
- `_active_ids() -> frozenset` — Frozen set of active model IDs.
- `_validate_tensor_shape(tensor: Any) -> None` — Validate that *tensor* has the same shape as existing contributions.
- `_auto_id(tensor: Any) -> str` — Generate a content-hash ID for anonymous tensors.


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
