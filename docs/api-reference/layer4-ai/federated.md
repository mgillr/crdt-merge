# crdt_merge.model.federated — Federated Merge

**Module**: `crdt_merge/model/federated.py`
**Layer**: 4 — AI / Model / Agent
**Dependencies**: `crdt_merge.model.core`, `torch`

---

## Classes

### FederatedMerge

Federated learning aggregation strategies.

```python
class FederatedMerge:
    def __init__(self, strategy: str = "fedavg") -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `aggregate()` | `aggregate(client_models: List[dict], weights: Optional[List[float]] = None) -> dict` | Aggregate client models |
| `secure_aggregate()` | `secure_aggregate(encrypted_models: List[bytes], keys: List[bytes]) -> dict` | Secure aggregation |
| `differential_privacy()` | `differential_privacy(model: dict, epsilon: float, delta: float) -> dict` | Add DP noise |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class FederatedResult`

Result of a federated aggregation round.

    Attributes
    ----------
    model : dict
        Aggregated model state_dict.
    client_contributions : dict[str, float]
        Per-client weight used during aggregation.
    num_clients : int
        Number of participating clients.
    total_samples : int
        Total training samples across all clients.
    strategy_used : str
        The aggregation strategy used.
    

**Attributes:**
- `model`: `dict`
- `client_contributions`: `Dict[str, float]`
- `num_clients`: `int`
- `total_samples`: `int`
- `strategy_used`: `str`



### `FederatedMerge.clear(self) → None`

Clear all submissions for the next round.

**Returns:** `None`



### `FederatedMerge.clients(self) → List[str]`

List of submitted client IDs.

**Returns:** `List[str]`



### `FederatedMerge.total_samples(self) → int`

Total training samples across all clients.

**Returns:** `int`


## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 0
- Inherited methods: 0
- Circular dependencies: None

### RREA Findings
- Entropy profile: Zero
- Dead code: None
- Shadow dependencies: None
- Chokepoint status: None

### Code Quality (Team 2)
- Docstring coverage: 91.7%
- `__all__` defined: Yes
- Code smells: None

### Second Pass
- Heightened findings: None (all 1,063 new inherited methods classified as false positive dunders)
