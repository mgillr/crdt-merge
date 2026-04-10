# crdt_merge.flower_plugin — Flower Federated Learning

**Module**: `crdt_merge/flower_plugin.py`
**Layer**: 4 — AI / Model / Agent
**LOC**: 500
**Dependencies**: `crdt_merge.model.federated`, `flwr` (Flower)

---

## Overview

Plugin for the Flower federated learning framework, providing CRDT-based model aggregation as a Flower Strategy.

---

## Classes

### CRDTStrategy (Flower Strategy)

```python
class CRDTStrategy(fl.server.strategy.Strategy):
    def __init__(self, merge_strategy: str = "fedavg", **kwargs) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `aggregate_fit()` | `aggregate_fit(server_round, results, failures) -> Tuple[Parameters, dict]` | Aggregate training results |
| `aggregate_evaluate()` | `aggregate_evaluate(server_round, results, failures) -> Tuple[float, dict]` | Aggregate evaluation |


## Analysis Notes
