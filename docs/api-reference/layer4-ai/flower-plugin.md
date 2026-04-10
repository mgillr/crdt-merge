# `crdt_merge/flower_plugin.py`

> Flower (flwr) integration plugin for crdt-merge.

Provides CRDT-based federated learning strategies, client wrappers,
and aggregators that work with or without the Flower framework installed.

**Source:** `crdt_merge/flower_plugin.py` | **Lines:** 500

---

**Exports (`__all__`):** `['CRDTStrategy', 'FlowerCRDTClient', 'FlowerAggregator']`

## Classes

### `class CRDTStrategy(_FlowerStrategyBase)`

Flower-compatible federated learning strategy using CRDT merge.

    Wraps Flower's Strategy interface so model updates from FL clients
    are merged using CRDT semantics rather than FedAvg.

    Works standalone (returns dicts) or with Flower installed (implements Strategy protocol).

    Example::
        strategy = CRDTStrategy(merge_key="layer_name", conflict_resolution="lww")
        # Use with Flower server
        # fl.server.start_server(strategy=strategy, ...)


**Methods:**

#### `CRDTStrategy.__init__(self, merge_key: str = 'layer_name', conflict_resolution: str = 'lww', min_clients: int = 2, min_available: int = 2) → None`

*No docstring*

#### `CRDTStrategy.configure_fit(self, server_round: int, parameters: Any = None, client_manager: Any = None) → List[Tuple]`

Configure the next round of training.

        Returns a list of (client_proxy, FitIns)-like tuples.  When running
        standalone (no Flower), returns an empty list.

#### `CRDTStrategy.aggregate_fit(self, server_round: int, results: List[Tuple], failures: List) → Tuple`

Aggregate training results from clients using CRDT merge.

        *results* is a list of (client_proxy, FitRes)-like tuples.
        Each FitRes is expected to be a dict or an object with a
        ``parameters`` attribute that can be converted to a dict.

        Returns ``(merged_parameters, metrics_dict)``.

#### `CRDTStrategy.initialize_parameters(self, client_manager: Any = None) → Any`

Return initial global parameters (None lets clients decide).

#### `CRDTStrategy.evaluate(self, server_round: int, parameters: Any = None) → Any`

Server-side evaluation (optional). Returns None to skip.

#### `CRDTStrategy.configure_evaluate(self, server_round: int, parameters: Any = None, client_manager: Any = None) → List[Tuple]`

Configure the next round of evaluation.

        Returns a list of (client_proxy, EvaluateIns)-like tuples.

#### `CRDTStrategy.aggregate_evaluate(self, server_round: int, results: List[Tuple], failures: List) → Tuple`

Aggregate evaluation results.

        Returns ``(loss, metrics_dict)``.

#### `CRDTStrategy._crdt_merge_parameters(self, parameter_list: List[Dict]) → Dict`

Core CRDT merge logic for model parameters.

        Merges a list of parameter dicts pairwise using the configured
        conflict resolution strategy.  Each dict maps layer/key names
        to parameter values (scalars, lists, or nested dicts).

#### `CRDTStrategy.get_merge_stats(self) → Dict`

Return merge statistics.

#### `CRDTStrategy.to_dict(self) → Dict`

Serialize strategy configuration and stats.

#### `CRDTStrategy.__repr__(self) → str`

*No docstring*


### `class FlowerCRDTClient`

Flower client wrapper that applies CRDT merge to local model updates.

    Example::
        client = FlowerCRDTClient(node_id="client_1")
        merged = client.merge_update(local_params, global_params)


**Methods:**

#### `FlowerCRDTClient.__init__(self, node_id: str = 'client_0', merge_key: str = 'layer_name', conflict_resolution: str = 'lww') → None`

*No docstring*

#### `FlowerCRDTClient.merge_update(self, local_params: Dict, global_params: Dict) → Dict`

CRDT merge local parameters with global parameters.

        Returns a new dict containing the merged result.

#### `FlowerCRDTClient.get_properties(self) → Dict`

Node properties including merge stats.

#### `FlowerCRDTClient.to_dict(self) → Dict`

Serialize client configuration and stats.

#### `FlowerCRDTClient.__repr__(self) → str`

*No docstring*


### `class FlowerAggregator`

Aggregates multiple Flower client results using CRDT merge.

    Example::
        agg = FlowerAggregator(conflict_resolution="lww")
        agg.add_result("client_1", {"layer1": [0.1, 0.2]})
        agg.add_result("client_2", {"layer1": [0.3, 0.4]})
        merged = agg.aggregate()


**Methods:**

#### `FlowerAggregator.__init__(self, conflict_resolution: str = 'lww', merge_key: str = 'layer_name') → None`

*No docstring*

#### `FlowerAggregator.add_result(self, client_id: str, parameters: Dict, num_examples: int = 0, metadata: Optional[Dict] = None) → None`

Add a client result for later aggregation.

#### `FlowerAggregator.aggregate(self) → Dict`

CRDT merge all client results.

        Returns a dict containing the merged parameters.

#### `FlowerAggregator.reset(self) → None`

Clear all buffered results.

#### `FlowerAggregator.get_stats(self) → Dict`

Return aggregation statistics.

#### `FlowerAggregator.to_dict(self) → Dict`

Serialize aggregator state.

#### `FlowerAggregator.__repr__(self) → str`

*No docstring*


## Functions

### `_merge_values(a: Any, b: Any, resolution: str = 'lww') → Any`

Merge two values using the configured conflict resolution strategy.

    Supports dicts (recursive merge), lists/tuples (element-wise when
    lengths match, otherwise concatenation), and scalars (LWW / max / min).

### `_merge_dicts(a: Dict, b: Dict, resolution: str = 'lww') → Dict`

Deep merge two dicts with configurable conflict resolution.


## Analysis Notes
