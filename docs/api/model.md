# Model Merge — ModelCRDT & Strategies

CRDT-native model weight merging with 26 strategies, LoRA support, federated bridge, GPU acceleration, and more.

## Quick Example

```python
from crdt_merge.model import ModelCRDT, CRDTMergeState
state = CRDTMergeState("slerp")
state.add(weights, model_id="llama-7b")
merged = state.resolve()
```

---

## API Reference

## `crdt_merge.model`

> crdt-merge model-merge sub-package — public API surface.

**Module:** `crdt_merge.model`

### Classes

#### `CRDTMergeState(strategy_name: 'str', base: 'Any' = None, conflict_resolution: 'ConflictResolution' = <ConflictResolution.HIGHEST_VERSION: 'highest_version'>, seed: 'Optional[int]' = None)`

Conflict-Free Replicated merge state for model merging.

**Properties:**

- `estimated_memory_bytes` — Estimate the total memory footprint of this state in bytes.
- `is_empty` — 
- `is_stochastic` — Whether this state's strategy has internal RNG.
- `model_ids` — List of model IDs currently in the set (excluding tombstoned).
- `needs_base` — Whether this state's strategy requires a base model.
- `size` — Number of active contributions.

**Methods:**

- `add(self, tensor: 'Any', model_id: 'Optional[str]' = None, weight: 'float' = 1.0, version: 'int' = 1, metadata: 'Optional[Dict[str, Any]]' = None) -> "'CRDTMergeState'"` — Add a model contribution to the merge set.
- `add_batch(self, contributions: 'List[Union[Tuple[Any, str], Tuple[Any, str, float], Tuple[Any, str, float, int], Dict[str, Any]]]') -> "'CRDTMergeState'"` — Add multiple model contributions at once.
- `from_dict(d: 'dict') -> "'CRDTMergeState'"` — Deserialize from wire format.
- `get_contribution(self, model_id: 'str') -> 'Optional[MergeContribution]'` — Get a specific contribution by model ID.
- `merge(self, other: "'CRDTMergeState'") -> "'CRDTMergeState'"` — CRDT merge: set union of contributions with conflict resolution.
- `merge_many(states: "List['CRDTMergeState']") -> "'CRDTMergeState'"` — Merge N states at once (more efficient than chained pairwise merges).
- `provenance(self) -> 'List[Dict[str, Any]]'` — Return provenance trail for all contributions.
- `remove(self, model_id: 'str') -> "'CRDTMergeState'"` — Remove a model contribution by ID (OR-Set remove).
- `resolve(self) -> 'Any'` — Apply the merge strategy atomically to all contributions.
- `to_dict(self) -> 'dict'` — Serialize the full CRDT state for wire transfer.

#### `ConflictHeatmap(layer_conflicts: 'Dict[str, float]', model_contributions: 'Dict[str, Dict[int, float]]', num_models: 'int', raw_tensors: 'Optional[Dict[str, List]]' = None) -> 'None'`

Conflict heatmap over model layers.

**Properties:**

- `layer_conflicts` — Per-layer conflict scores.
- `model_contributions` — Per-layer per-model contribution fractions.
- `num_layers` — Number of layers in the heatmap.
- `num_models` — Number of models being compared.
- `overall_conflict` — Mean conflict score across all layers.

**Methods:**

- `from_merge(provenance_summary: 'ProvenanceSummary') -> "'ConflictHeatmap'"` — Build heatmap from provenance data.
- `from_models(models: 'List[Dict[str, Any]]', base: 'Optional[Dict[str, Any]]' = None) -> "'ConflictHeatmap'"` — Compute heatmap directly from model state_dicts.
- `least_conflicted_layers(self, n: 'int' = 10) -> 'List[Tuple[str, float]]'` — Return the *n* least conflicted layers.
- `most_conflicted_layers(self, n: 'int' = 10) -> 'List[Tuple[str, float]]'` — Return the *n* most conflicted layers.
- `parameter_detail(self, layer_name: 'str') -> 'LayerDetail'` — Get detailed parameter-level analysis for a layer.
- `to_csv(self, path: 'Optional[str]' = None) -> 'str'` — Export heatmap as CSV.
- `to_dict(self) -> 'Dict[str, Any]'` — Export heatmap as a plain dict.
- `to_json(self, path: 'Optional[str]' = None) -> 'str'` — Export heatmap as JSON (D3/Plotly compatible).

#### `ConflictResolution(*values)`

Strategy for resolving conflicts when the same model_id appears twice.

**Methods:**


#### `ContinualMerge(base_model: 'dict', strategy: 'str' = 'weight_average', memory_budget: 'float' = 1.0) -> 'None'`

Absorb model updates over time without catastrophic forgetting.

**Properties:**

- `current_weights` — Effective contribution weight of each absorbed model (after decay).
- `history` — List of absorption events.

**Methods:**

- `absorb(self, model: 'dict', weight: 'float' = 1.0, name: 'Optional[str]' = None, replace: 'Optional[str]' = None) -> 'None'` — Absorb a model update into the current merged state.
- `export(self) -> 'dict'` — Return the current merged state_dict.
- `reset(self, base_model: 'dict') -> 'None'` — Restart from a new base model, clearing all history.

#### `FederatedMerge(strategy: 'str' = 'fedavg', mu: 'float' = 0.01) -> 'None'`

Federated learning bridge for FedAvg and FedProx aggregation.

**Properties:**

- `clients` — List of submitted client IDs.
- `total_samples` — Total training samples across all clients.

**Methods:**

- `aggregate(self, global_model: 'Optional[dict]' = None) -> 'FederatedResult'` — Aggregate all submitted client updates.
- `clear(self) -> 'None'` — Clear all submissions for the next round.
- `submit(self, client_id: 'str', model_update: 'dict', num_samples: 'int' = 1) -> 'None'` — Register a client's model update.

#### `FederatedResult(model: 'dict', client_contributions: 'Dict[str, float]', num_clients: 'int', total_samples: 'int', strategy_used: 'str') -> None`

Result of a federated aggregation round.

**Methods:**


#### `GPUMerge(device: 'str' = 'auto', dtype: 'str' = 'float32', chunk_size: 'Union[str, int]' = 'auto') -> 'None'`

GPU-accelerated model merging.

**Methods:**

- `device_info(self) -> 'dict'` — Return information about the current device.
- `is_gpu_available() -> 'bool'` — Check if GPU is available.
- `merge(self, models: 'List[dict]', strategy: 'str' = 'weight_average', schema=None, base_model: 'Optional[dict]' = None, weights: 'Optional[List[float]]' = None, **kwargs: 'Any') -> 'dict'` — Merge models using GPU acceleration.

#### `LayerProvenance(layer_name: 'str', strategy_used: 'str', dominant_source: 'int', contribution_map: 'Dict[int, float]', conflict_score: 'float', metadata: 'Dict[str, Any]' = <factory>) -> None`

Provenance information for a single layer.

**Methods:**


#### `LoRAMerge(schema: 'LoRAMergeSchema') -> 'None'`

Merge LoRA adapters with rank harmonization and per-module strategies.

**Methods:**

- `apply_to_base(self, merged_adapter: 'Dict[str, Dict[str, Any]]', base_model: 'Dict[str, Any]') -> 'Dict[str, Any]'` — Apply a merged LoRA adapter to a base model.
- `merge_adapters(self, adapters: 'List[Dict[str, Dict[str, Any]]]', weights: 'Optional[List[float]]' = None, rank_strategy: 'str' = 'max') -> 'Dict[str, Dict[str, Any]]'` — Merge multiple LoRA adapters into one.
- `merge_adapters_with_provenance(self, adapters: 'List[Dict[str, Dict[str, Any]]]', weights: 'Optional[List[float]]' = None, rank_strategy: 'str' = 'max') -> 'Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]'` — Merge adapters and return provenance information.

#### `LoRAMergeSchema(strategies: 'Dict[str, Union[str, ModelMergeStrategy]]') -> 'None'`

Maps adapter module names to merge strategies.

**Methods:**

- `from_dict(d: 'Dict[str, str]') -> "'LoRAMergeSchema'"` — Deserialize from a plain dict.
- `strategy_for(self, module_name: 'str') -> 'ModelMergeStrategy'` — Return the strategy that applies to *module_name*.
- `to_dict(self) -> 'Dict[str, str]'` — Serialize to a plain dict (strategy names only).

#### `MergeContribution(model_id: 'str', tensor: 'Any', weight: 'float' = 1.0, version: 'int' = 1, metadata: 'Optional[Dict[str, Any]]' = None, timestamp: 'Optional[float]' = None)`

A single model contribution in the CRDT state.

**Methods:**

- `from_dict(d: 'dict') -> 'MergeContribution'` — Deserialize from wire format.
- `to_dict(self) -> 'dict'` — Serialize for wire transfer.

#### `MergePipeline(stages: 'List[Dict[str, Any]]') -> 'None'`

Define and execute multi-stage model merge pipelines.

**Methods:**

- `execute(self, output_path: 'Optional[str]' = None) -> 'PipelineResult'` — Execute all stages in dependency order.
- `from_dict(d: 'Dict[str, Any]') -> "'MergePipeline'"` — Deserialize from a dict.
- `to_dict(self) -> 'Dict[str, Any]'` — Serialize the pipeline to a plain dict.
- `validate(self) -> 'List[str]'` — Validate the pipeline for structural correctness.

#### `MergeResult(tensor: 'Any', provenance: 'Optional[Dict[str, Any]]' = None, metadata: 'Dict[str, Any]' = <factory>) -> None`

Result of a model merge operation.

**Methods:**


#### `ModelCRDT(schema: 'ModelMergeSchema') -> 'None'`

Main entry-point for schema-driven model merging.

**Methods:**

- `crdt_merge(self, models: 'List[Any]', model_ids: 'Optional[List[str]]' = None, base_model: 'Any' = None, weights: 'Optional[List[float]]' = None, seed: 'int' = 42, **kwargs: 'Any') -> 'MergeResult'` — CRDT-guaranteed merge via the two-layer architecture.
- `merge(self, models: 'List[Any]', base_model: 'Any' = None, weights: 'Optional[List[float]]' = None, output_path: 'Optional[str]' = None, **kwargs: 'Any') -> 'MergeResult'` — Merge multiple models according to the schema.
- `merge_with_provenance(self, models: 'List[Any]', base_model: 'Any' = None, weights: 'Optional[List[float]]' = None, **kwargs: 'Any') -> 'MergeResult'` — Same as :meth:`merge` but also populates ``provenance`` in the result.
- `verify(self, strategy: 'Optional[str]' = None, gen_fn: 'Optional[Callable]' = None, trials: 'int' = 100) -> 'Dict[str, Any]'` — Verify CRDT properties of strategies in the schema.

#### `ModelMerge(schema: 'ModelMergeSchema') -> 'None'`

Main entry-point for schema-driven model merging.

**Methods:**

- `crdt_merge(self, models: 'List[Any]', model_ids: 'Optional[List[str]]' = None, base_model: 'Any' = None, weights: 'Optional[List[float]]' = None, seed: 'int' = 42, **kwargs: 'Any') -> 'MergeResult'` — CRDT-guaranteed merge via the two-layer architecture.
- `merge(self, models: 'List[Any]', base_model: 'Any' = None, weights: 'Optional[List[float]]' = None, output_path: 'Optional[str]' = None, **kwargs: 'Any') -> 'MergeResult'` — Merge multiple models according to the schema.
- `merge_with_provenance(self, models: 'List[Any]', base_model: 'Any' = None, weights: 'Optional[List[float]]' = None, **kwargs: 'Any') -> 'MergeResult'` — Same as :meth:`merge` but also populates ``provenance`` in the result.
- `verify(self, strategy: 'Optional[str]' = None, gen_fn: 'Optional[Callable]' = None, trials: 'int' = 100) -> 'Dict[str, Any]'` — Verify CRDT properties of strategies in the schema.

#### `ModelMergeSchema(strategies: 'Dict[str, Union[str, ModelMergeStrategy]]') -> 'None'`

Maps layer-name patterns to merge strategies.

**Methods:**

- `from_dict(d: 'Dict[str, str]') -> "'ModelMergeSchema'"` — Deserialize from a plain dict.
- `strategy_for(self, layer_name: 'str') -> 'ModelMergeStrategy'` — Return the strategy that applies to *layer_name*.
- `to_dict(self) -> 'Dict[str, str]'` — Serialize to a plain dict (strategy names only).

#### `ModelMergeStrategy()`

Abstract base for all model-merge strategies.

**Properties:**

- `category` — Category grouping (e.g. ``'interpolation'``, ``'evolutionary'``).
- `crdt_properties` — CRDT property declaration.
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — Short unique identifier for this strategy (e.g. ``'slerp'``).
- `paper_reference` — Academic citation or URL for the strategy's paper.

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — Merge a list of array-like tensors into one.
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `PipelineResult(final_model: 'Dict[str, Any]', stage_results: 'Dict[str, Dict[str, Any]]', pipeline_provenance: 'Dict[str, Any]', execution_order: 'List[str]') -> None`

Result of a pipeline execution.

**Methods:**


#### `ProvenanceSummary(overall_conflict: 'float', dominant_model: 'int', layer_conflict_ranking: 'List[str]', per_layer: 'Dict[str, LayerProvenance]') -> None`

Aggregated provenance across all layers.

**Methods:**


#### `ProvenanceTracker() -> 'None'`

Track provenance information across multiple layer merges.

**Methods:**

- `summary(self) -> 'ProvenanceSummary'` — Compute aggregated provenance summary.
- `track_merge(self, layer_name: 'str', tensors: 'list', weights: 'Optional[List[float]]', strategy_name: 'str', result: 'Any' = None) -> 'LayerProvenance'` — Track a single layer merge.

#### `SafetyAnalyzer() -> 'None'`

Detect safety-critical layers based on cross-model variance.

**Methods:**

- `detect_safety_layers(self, models: 'List[dict]', base_model: 'Optional[dict]' = None, threshold: 'float' = 0.1) -> 'List[str]'` — Auto-detect safety-critical layers.
- `safety_report(self, models: 'List[dict]', base_model: 'Optional[dict]' = None) -> 'SafetyReport'` — Generate a comprehensive safety analysis.

#### `SafetyReport(safety_layers: 'List[str]', layer_variance: 'Dict[str, float]', risk_score: 'float', recommendation: 'str') -> None`

Comprehensive safety analysis of a model merge.

**Methods:**


### Functions

#### `export_mergekit_config(schema: 'ModelMergeSchema', models: 'Optional[List[str]]' = None) -> 'dict'`

Convert a ModelMergeSchema back to MergeKit format.

#### `export_provenance(summary: 'ProvenanceSummary', format: 'str' = 'json') -> 'str'`

Export provenance summary to a string.

#### `get_strategy(name: 'str', **kwargs: 'Any') -> 'ModelMergeStrategy'`

Instantiate a registered strategy by *name*.

#### `import_mergekit_config(config: 'Union[dict, str]') -> 'Tuple[ModelMergeSchema, dict]'`

Parse a MergeKit-style config into a ModelMergeSchema.

#### `list_strategies() -> 'List[str]'`

Return sorted list of all registered strategy names.

#### `list_strategies_by_category() -> 'Dict[str, List[str]]'`

Return strategies grouped by their ``category`` property.

#### `register_strategy(name: 'str')`

Class decorator that registers a ``ModelMergeStrategy`` subclass.


## `crdt_merge.model.core`

> Core ModelCRDT class and ModelMergeSchema for per-layer strategy assignment.

**Module:** `crdt_merge.model.core`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `MergeResult(tensor: 'Any', provenance: 'Optional[Dict[str, Any]]' = None, metadata: 'Dict[str, Any]' = <factory>) -> None`

Result of a model merge operation.

**Methods:**


#### `ModelCRDT(schema: 'ModelMergeSchema') -> 'None'`

Main entry-point for schema-driven model merging.

**Methods:**

- `crdt_merge(self, models: 'List[Any]', model_ids: 'Optional[List[str]]' = None, base_model: 'Any' = None, weights: 'Optional[List[float]]' = None, seed: 'int' = 42, **kwargs: 'Any') -> 'MergeResult'` — CRDT-guaranteed merge via the two-layer architecture.
- `merge(self, models: 'List[Any]', base_model: 'Any' = None, weights: 'Optional[List[float]]' = None, output_path: 'Optional[str]' = None, **kwargs: 'Any') -> 'MergeResult'` — Merge multiple models according to the schema.
- `merge_with_provenance(self, models: 'List[Any]', base_model: 'Any' = None, weights: 'Optional[List[float]]' = None, **kwargs: 'Any') -> 'MergeResult'` — Same as :meth:`merge` but also populates ``provenance`` in the result.
- `verify(self, strategy: 'Optional[str]' = None, gen_fn: 'Optional[Callable]' = None, trials: 'int' = 100) -> 'Dict[str, Any]'` — Verify CRDT properties of strategies in the schema.

#### `ModelMerge(schema: 'ModelMergeSchema') -> 'None'`

Main entry-point for schema-driven model merging.

**Methods:**

- `crdt_merge(self, models: 'List[Any]', model_ids: 'Optional[List[str]]' = None, base_model: 'Any' = None, weights: 'Optional[List[float]]' = None, seed: 'int' = 42, **kwargs: 'Any') -> 'MergeResult'` — CRDT-guaranteed merge via the two-layer architecture.
- `merge(self, models: 'List[Any]', base_model: 'Any' = None, weights: 'Optional[List[float]]' = None, output_path: 'Optional[str]' = None, **kwargs: 'Any') -> 'MergeResult'` — Merge multiple models according to the schema.
- `merge_with_provenance(self, models: 'List[Any]', base_model: 'Any' = None, weights: 'Optional[List[float]]' = None, **kwargs: 'Any') -> 'MergeResult'` — Same as :meth:`merge` but also populates ``provenance`` in the result.
- `verify(self, strategy: 'Optional[str]' = None, gen_fn: 'Optional[Callable]' = None, trials: 'int' = 100) -> 'Dict[str, Any]'` — Verify CRDT properties of strategies in the schema.

#### `ModelMergeSchema(strategies: 'Dict[str, Union[str, ModelMergeStrategy]]') -> 'None'`

Maps layer-name patterns to merge strategies.

**Methods:**

- `from_dict(d: 'Dict[str, str]') -> "'ModelMergeSchema'"` — Deserialize from a plain dict.
- `strategy_for(self, layer_name: 'str') -> 'ModelMergeStrategy'` — Return the strategy that applies to *layer_name*.
- `to_dict(self) -> 'Dict[str, str]'` — Serialize to a plain dict (strategy names only).

#### `ModelMergeStrategy()`

Abstract base for all model-merge strategies.

**Properties:**

- `category` — Category grouping (e.g. ``'interpolation'``, ``'evolutionary'``).
- `crdt_properties` — CRDT property declaration.
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — Short unique identifier for this strategy (e.g. ``'slerp'``).
- `paper_reference` — Academic citation or URL for the strategy's paper.

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — Merge a list of array-like tensors into one.
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.

#### `get_strategy(name: 'str', **kwargs: 'Any') -> 'ModelMergeStrategy'`

Instantiate a registered strategy by *name*.


## `crdt_merge.model.crdt_state`

> CRDT-Aware Merge State — the layer that makes ALL 26 strategies true CRDTs.

**Module:** `crdt_merge.model.crdt_state`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `CRDTMergeState(strategy_name: 'str', base: 'Any' = None, conflict_resolution: 'ConflictResolution' = <ConflictResolution.HIGHEST_VERSION: 'highest_version'>, seed: 'Optional[int]' = None)`

Conflict-Free Replicated merge state for model merging.

**Properties:**

- `estimated_memory_bytes` — Estimate the total memory footprint of this state in bytes.
- `is_empty` — 
- `is_stochastic` — Whether this state's strategy has internal RNG.
- `model_ids` — List of model IDs currently in the set (excluding tombstoned).
- `needs_base` — Whether this state's strategy requires a base model.
- `size` — Number of active contributions.

**Methods:**

- `add(self, tensor: 'Any', model_id: 'Optional[str]' = None, weight: 'float' = 1.0, version: 'int' = 1, metadata: 'Optional[Dict[str, Any]]' = None) -> "'CRDTMergeState'"` — Add a model contribution to the merge set.
- `add_batch(self, contributions: 'List[Union[Tuple[Any, str], Tuple[Any, str, float], Tuple[Any, str, float, int], Dict[str, Any]]]') -> "'CRDTMergeState'"` — Add multiple model contributions at once.
- `from_dict(d: 'dict') -> "'CRDTMergeState'"` — Deserialize from wire format.
- `get_contribution(self, model_id: 'str') -> 'Optional[MergeContribution]'` — Get a specific contribution by model ID.
- `merge(self, other: "'CRDTMergeState'") -> "'CRDTMergeState'"` — CRDT merge: set union of contributions with conflict resolution.
- `merge_many(states: "List['CRDTMergeState']") -> "'CRDTMergeState'"` — Merge N states at once (more efficient than chained pairwise merges).
- `provenance(self) -> 'List[Dict[str, Any]]'` — Return provenance trail for all contributions.
- `remove(self, model_id: 'str') -> "'CRDTMergeState'"` — Remove a model contribution by ID (OR-Set remove).
- `resolve(self) -> 'Any'` — Apply the merge strategy atomically to all contributions.
- `to_dict(self) -> 'dict'` — Serialize the full CRDT state for wire transfer.

#### `ConflictResolution(*values)`

Strategy for resolving conflicts when the same model_id appears twice.

**Methods:**


#### `Enum(new_class_name, /, names, *, module=None, qualname=None, type=None, start=1, boundary=None)`

Create a collection of name/value pairs.

#### `MergeContribution(model_id: 'str', tensor: 'Any', weight: 'float' = 1.0, version: 'int' = 1, metadata: 'Optional[Dict[str, Any]]' = None, timestamp: 'Optional[float]' = None)`

A single model contribution in the CRDT state.

**Methods:**

- `from_dict(d: 'dict') -> 'MergeContribution'` — Deserialize from wire format.
- `to_dict(self) -> 'dict'` — Serialize for wire transfer.

#### `OrderedDict(...)`

Dictionary that remembers insertion order


## `crdt_merge.model.federated`

> Federated learning bridge — FedAvg and FedProx as CRDT operations.

**Module:** `crdt_merge.model.federated`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `FederatedMerge(strategy: 'str' = 'fedavg', mu: 'float' = 0.01) -> 'None'`

Federated learning bridge for FedAvg and FedProx aggregation.

**Properties:**

- `clients` — List of submitted client IDs.
- `total_samples` — Total training samples across all clients.

**Methods:**

- `aggregate(self, global_model: 'Optional[dict]' = None) -> 'FederatedResult'` — Aggregate all submitted client updates.
- `clear(self) -> 'None'` — Clear all submissions for the next round.
- `submit(self, client_id: 'str', model_update: 'dict', num_samples: 'int' = 1) -> 'None'` — Register a client's model update.

#### `FederatedResult(model: 'dict', client_contributions: 'Dict[str, float]', num_clients: 'int', total_samples: 'int', strategy_used: 'str') -> None`

Result of a federated aggregation round.

**Methods:**


### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.


## `crdt_merge.model.formats`

> MergeKit / FusionBench compatibility layer.

**Module:** `crdt_merge.model.formats`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `ModelMergeSchema(strategies: 'Dict[str, Union[str, ModelMergeStrategy]]') -> 'None'`

Maps layer-name patterns to merge strategies.

**Methods:**

- `from_dict(d: 'Dict[str, str]') -> "'ModelMergeSchema'"` — Deserialize from a plain dict.
- `strategy_for(self, layer_name: 'str') -> 'ModelMergeStrategy'` — Return the strategy that applies to *layer_name*.
- `to_dict(self) -> 'Dict[str, str]'` — Serialize to a plain dict (strategy names only).

### Functions

#### `export_mergekit_config(schema: 'ModelMergeSchema', models: 'Optional[List[str]]' = None) -> 'dict'`

Convert a ModelMergeSchema back to MergeKit format.

#### `import_mergekit_config(config: 'Union[dict, str]') -> 'Tuple[ModelMergeSchema, dict]'`

Parse a MergeKit-style config into a ModelMergeSchema.


## `crdt_merge.model.gpu`

> GPU-accelerated model merging with lazy torch imports.

**Module:** `crdt_merge.model.gpu`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `GPUMerge(device: 'str' = 'auto', dtype: 'str' = 'float32', chunk_size: 'Union[str, int]' = 'auto') -> 'None'`

GPU-accelerated model merging.

**Methods:**

- `device_info(self) -> 'dict'` — Return information about the current device.
- `is_gpu_available() -> 'bool'` — Check if GPU is available.
- `merge(self, models: 'List[dict]', strategy: 'str' = 'weight_average', schema=None, base_model: 'Optional[dict]' = None, weights: 'Optional[List[float]]' = None, **kwargs: 'Any') -> 'dict'` — Merge models using GPU acceleration.


## `crdt_merge.model.heatmap`

> Conflict heatmaps for model merge analysis (Unicorn Feature #4).

**Module:** `crdt_merge.model.heatmap`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `ConflictHeatmap(layer_conflicts: 'Dict[str, float]', model_contributions: 'Dict[str, Dict[int, float]]', num_models: 'int', raw_tensors: 'Optional[Dict[str, List]]' = None) -> 'None'`

Conflict heatmap over model layers.

**Properties:**

- `layer_conflicts` — Per-layer conflict scores.
- `model_contributions` — Per-layer per-model contribution fractions.
- `num_layers` — Number of layers in the heatmap.
- `num_models` — Number of models being compared.
- `overall_conflict` — Mean conflict score across all layers.

**Methods:**

- `from_merge(provenance_summary: 'ProvenanceSummary') -> "'ConflictHeatmap'"` — Build heatmap from provenance data.
- `from_models(models: 'List[Dict[str, Any]]', base: 'Optional[Dict[str, Any]]' = None) -> "'ConflictHeatmap'"` — Compute heatmap directly from model state_dicts.
- `least_conflicted_layers(self, n: 'int' = 10) -> 'List[Tuple[str, float]]'` — Return the *n* least conflicted layers.
- `most_conflicted_layers(self, n: 'int' = 10) -> 'List[Tuple[str, float]]'` — Return the *n* most conflicted layers.
- `parameter_detail(self, layer_name: 'str') -> 'LayerDetail'` — Get detailed parameter-level analysis for a layer.
- `to_csv(self, path: 'Optional[str]' = None) -> 'str'` — Export heatmap as CSV.
- `to_dict(self) -> 'Dict[str, Any]'` — Export heatmap as a plain dict.
- `to_json(self, path: 'Optional[str]' = None) -> 'str'` — Export heatmap as JSON (D3/Plotly compatible).

#### `LayerDetail(variance_map: 'List[float]', sign_agreement: 'float', magnitude_spread: 'float') -> None`

Detailed parameter-level analysis for a single layer.

**Methods:**


#### `ProvenanceSummary(overall_conflict: 'float', dominant_model: 'int', layer_conflict_ranking: 'List[str]', per_layer: 'Dict[str, LayerProvenance]') -> None`

Aggregated provenance across all layers.

**Methods:**


### Functions

#### `compute_conflict_score(tensors: 'list') -> 'float'`

Compute conflict score between tensors from different models.

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.


## `crdt_merge.model.lora`

> LoRA adapter merging with per-module strategy assignment.

**Module:** `crdt_merge.model.lora`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `LoRAMerge(schema: 'LoRAMergeSchema') -> 'None'`

Merge LoRA adapters with rank harmonization and per-module strategies.

**Methods:**

- `apply_to_base(self, merged_adapter: 'Dict[str, Dict[str, Any]]', base_model: 'Dict[str, Any]') -> 'Dict[str, Any]'` — Apply a merged LoRA adapter to a base model.
- `merge_adapters(self, adapters: 'List[Dict[str, Dict[str, Any]]]', weights: 'Optional[List[float]]' = None, rank_strategy: 'str' = 'max') -> 'Dict[str, Dict[str, Any]]'` — Merge multiple LoRA adapters into one.
- `merge_adapters_with_provenance(self, adapters: 'List[Dict[str, Dict[str, Any]]]', weights: 'Optional[List[float]]' = None, rank_strategy: 'str' = 'max') -> 'Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]'` — Merge adapters and return provenance information.

#### `LoRAMergeSchema(strategies: 'Dict[str, Union[str, ModelMergeStrategy]]') -> 'None'`

Maps adapter module names to merge strategies.

**Methods:**

- `from_dict(d: 'Dict[str, str]') -> "'LoRAMergeSchema'"` — Deserialize from a plain dict.
- `strategy_for(self, module_name: 'str') -> 'ModelMergeStrategy'` — Return the strategy that applies to *module_name*.
- `to_dict(self) -> 'Dict[str, str]'` — Serialize to a plain dict (strategy names only).

#### `ModelMergeStrategy()`

Abstract base for all model-merge strategies.

**Properties:**

- `category` — Category grouping (e.g. ``'interpolation'``, ``'evolutionary'``).
- `crdt_properties` — CRDT property declaration.
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — Short unique identifier for this strategy (e.g. ``'slerp'``).
- `paper_reference` — Academic citation or URL for the strategy's paper.

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — Merge a list of array-like tensors into one.
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.

#### `get_strategy(name: 'str', **kwargs: 'Any') -> 'ModelMergeStrategy'`

Instantiate a registered strategy by *name*.


## `crdt_merge.model.pipeline`

> Multi-stage merge pipelines.

**Module:** `crdt_merge.model.pipeline`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `MergePipeline(stages: 'List[Dict[str, Any]]') -> 'None'`

Define and execute multi-stage model merge pipelines.

**Methods:**

- `execute(self, output_path: 'Optional[str]' = None) -> 'PipelineResult'` — Execute all stages in dependency order.
- `from_dict(d: 'Dict[str, Any]') -> "'MergePipeline'"` — Deserialize from a dict.
- `to_dict(self) -> 'Dict[str, Any]'` — Serialize the pipeline to a plain dict.
- `validate(self) -> 'List[str]'` — Validate the pipeline for structural correctness.

#### `ModelCRDT(schema: 'ModelMergeSchema') -> 'None'`

Main entry-point for schema-driven model merging.

**Methods:**

- `crdt_merge(self, models: 'List[Any]', model_ids: 'Optional[List[str]]' = None, base_model: 'Any' = None, weights: 'Optional[List[float]]' = None, seed: 'int' = 42, **kwargs: 'Any') -> 'MergeResult'` — CRDT-guaranteed merge via the two-layer architecture.
- `merge(self, models: 'List[Any]', base_model: 'Any' = None, weights: 'Optional[List[float]]' = None, output_path: 'Optional[str]' = None, **kwargs: 'Any') -> 'MergeResult'` — Merge multiple models according to the schema.
- `merge_with_provenance(self, models: 'List[Any]', base_model: 'Any' = None, weights: 'Optional[List[float]]' = None, **kwargs: 'Any') -> 'MergeResult'` — Same as :meth:`merge` but also populates ``provenance`` in the result.
- `verify(self, strategy: 'Optional[str]' = None, gen_fn: 'Optional[Callable]' = None, trials: 'int' = 100) -> 'Dict[str, Any]'` — Verify CRDT properties of strategies in the schema.

#### `ModelMergeSchema(strategies: 'Dict[str, Union[str, ModelMergeStrategy]]') -> 'None'`

Maps layer-name patterns to merge strategies.

**Methods:**

- `from_dict(d: 'Dict[str, str]') -> "'ModelMergeSchema'"` — Deserialize from a plain dict.
- `strategy_for(self, layer_name: 'str') -> 'ModelMergeStrategy'` — Return the strategy that applies to *layer_name*.
- `to_dict(self) -> 'Dict[str, str]'` — Serialize to a plain dict (strategy names only).

#### `PipelineResult(final_model: 'Dict[str, Any]', stage_results: 'Dict[str, Dict[str, Any]]', pipeline_provenance: 'Dict[str, Any]', execution_order: 'List[str]') -> None`

Result of a pipeline execution.

**Methods:**


### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.


## `crdt_merge.model.provenance`

> Per-parameter provenance tracking for model merges (Unicorn Feature #3).

**Module:** `crdt_merge.model.provenance`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `LayerProvenance(layer_name: 'str', strategy_used: 'str', dominant_source: 'int', contribution_map: 'Dict[int, float]', conflict_score: 'float', metadata: 'Dict[str, Any]' = <factory>) -> None`

Provenance information for a single layer.

**Methods:**


#### `OrderedDict(...)`

Dictionary that remembers insertion order

#### `ProvenanceSummary(overall_conflict: 'float', dominant_model: 'int', layer_conflict_ranking: 'List[str]', per_layer: 'Dict[str, LayerProvenance]') -> None`

Aggregated provenance across all layers.

**Methods:**


#### `ProvenanceTracker() -> 'None'`

Track provenance information across multiple layer merges.

**Methods:**

- `summary(self) -> 'ProvenanceSummary'` — Compute aggregated provenance summary.
- `track_merge(self, layer_name: 'str', tensors: 'list', weights: 'Optional[List[float]]', strategy_name: 'str', result: 'Any' = None) -> 'LayerProvenance'` — Track a single layer merge.

### Functions

#### `compute_conflict_score(tensors: 'list') -> 'float'`

Compute conflict score between tensors from different models.

#### `compute_contribution(tensors: 'list', weights: 'Optional[List[float]]', strategy_name: 'str') -> 'Dict[int, float]'`

Compute per-model contribution fractions.

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `export_provenance(summary: 'ProvenanceSummary', format: 'str' = 'json') -> 'str'`

Export provenance summary to a string.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.


## `crdt_merge.model.safety`

> Safety-critical layer detection for model merging.

**Module:** `crdt_merge.model.safety`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `SafetyAnalyzer() -> 'None'`

Detect safety-critical layers based on cross-model variance.

**Methods:**

- `detect_safety_layers(self, models: 'List[dict]', base_model: 'Optional[dict]' = None, threshold: 'float' = 0.1) -> 'List[str]'` — Auto-detect safety-critical layers.
- `safety_report(self, models: 'List[dict]', base_model: 'Optional[dict]' = None) -> 'SafetyReport'` — Generate a comprehensive safety analysis.

#### `SafetyReport(safety_layers: 'List[str]', layer_variance: 'Dict[str, float]', risk_score: 'float', recommendation: 'str') -> None`

Comprehensive safety analysis of a model merge.

**Methods:**


### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.


## `crdt_merge.model.continual`

> Continual/sequential model merge — absorb updates without catastrophic forgetting.

**Module:** `crdt_merge.model.continual`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `ContinualMerge(base_model: 'dict', strategy: 'str' = 'weight_average', memory_budget: 'float' = 1.0) -> 'None'`

Absorb model updates over time without catastrophic forgetting.

**Properties:**

- `current_weights` — Effective contribution weight of each absorbed model (after decay).
- `history` — List of absorption events.

**Methods:**

- `absorb(self, model: 'dict', weight: 'float' = 1.0, name: 'Optional[str]' = None, replace: 'Optional[str]' = None) -> 'None'` — Absorb a model update into the current merged state.
- `export(self) -> 'dict'` — Return the current merged state_dict.
- `reset(self, base_model: 'dict') -> 'None'` — Restart from a new base model, clearing all history.

#### `datetime(...)`

datetime(year, month, day[, hour[, minute[, second[, microsecond[,tzinfo]]]]])

#### `timezone(...)`

Fixed offset from UTC implementation of tzinfo.


## `crdt_merge.model.strategies`

> Strategy registry with ``@register_strategy`` decorator and plugin discovery.

**Module:** `crdt_merge.model.strategies`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `ModelMergeStrategy()`

Abstract base for all model-merge strategies.

**Properties:**

- `category` — Category grouping (e.g. ``'interpolation'``, ``'evolutionary'``).
- `crdt_properties` — CRDT property declaration.
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — Short unique identifier for this strategy (e.g. ``'slerp'``).
- `paper_reference` — Academic citation or URL for the strategy's paper.

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — Merge a list of array-like tensors into one.
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

### Functions

#### `get_strategy(name: 'str', **kwargs: 'Any') -> 'ModelMergeStrategy'`

Instantiate a registered strategy by *name*.

#### `list_strategies() -> 'List[str]'`

Return sorted list of all registered strategy names.

#### `list_strategies_by_category() -> 'Dict[str, List[str]]'`

Return strategies grouped by their ``category`` property.

#### `register_strategy(name: 'str')`

Class decorator that registers a ``ModelMergeStrategy`` subclass.


## `crdt_merge.model.strategies.base`

> ModelMergeStrategy abstract base class.

**Module:** `crdt_merge.model.strategies.base`

### Classes

#### `ABC()`

Helper class that provides a standard way to create an ABC using

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `CRDTTier(*values)`

Classification of a strategy's CRDT compliance.

**Methods:**


#### `Enum(new_class_name, /, names, *, module=None, qualname=None, type=None, start=1, boundary=None)`

Create a collection of name/value pairs.

#### `MergeResult(tensor: 'Any', provenance: 'Optional[Dict[str, Any]]' = None, metadata: 'Dict[str, Any]' = <factory>) -> None`

Result of a model merge operation.

**Methods:**


#### `ModelMergeStrategy()`

Abstract base for all model-merge strategies.

**Properties:**

- `category` — Category grouping (e.g. ``'interpolation'``, ``'evolutionary'``).
- `crdt_properties` — CRDT property declaration.
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — Short unique identifier for this strategy (e.g. ``'slerp'``).
- `paper_reference` — Academic citation or URL for the strategy's paper.

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — Merge a list of array-like tensors into one.
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

### Functions

#### `abstractmethod(funcobj)`

A decorator indicating abstract methods.

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.


## `crdt_merge.model.strategies.basic`

> Basic model-merge strategies: WeightAverage, SLERP, TaskArithmetic, LinearInterpolation.

**Module:** `crdt_merge.model.strategies.basic`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `LinearInterpolation()`

Linear interpolation / model soups (Wortsman et al., 2022).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `ModelMergeStrategy()`

Abstract base for all model-merge strategies.

**Properties:**

- `category` — Category grouping (e.g. ``'interpolation'``, ``'evolutionary'``).
- `crdt_properties` — CRDT property declaration.
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — Short unique identifier for this strategy (e.g. ``'slerp'``).
- `paper_reference` — Academic citation or URL for the strategy's paper.

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — Merge a list of array-like tensors into one.
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `SphericalLinearInterpolation()`

Spherical linear interpolation (Shoemake 1985, applied to LLMs 2024).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `TaskArithmetic()`

Task arithmetic merge (Ilharco et al., 2023).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `WeightAverage()`

Federated-averaging style weighted average (McMahan et al., 2017).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

### Functions

#### `register_strategy(name: 'str')`

Class decorator that registers a ``ModelMergeStrategy`` subclass.


## `crdt_merge.model.strategies.calibration`

> Post-Calibration model-merge strategies.

**Module:** `crdt_merge.model.strategies.calibration`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `ModelMergeStrategy()`

Abstract base for all model-merge strategies.

**Properties:**

- `category` — Category grouping (e.g. ``'interpolation'``, ``'evolutionary'``).
- `crdt_properties` — CRDT property declaration.
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — Short unique identifier for this strategy (e.g. ``'slerp'``).
- `paper_reference` — Academic citation or URL for the strategy's paper.

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — Merge a list of array-like tensors into one.
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `RepresentationSurgery()`

Post-merge representation correction (2024).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `WeightScopeAlignment()`

Weight Scope Alignment: Normalize weight distributions → align → merge (2024).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

### Functions

#### `register_strategy(name: 'str')`

Class decorator that registers a ``ModelMergeStrategy`` subclass.


## `crdt_merge.model.strategies.evolutionary`

> Evolutionary model-merge strategies.

**Module:** `crdt_merge.model.strategies.evolutionary`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `EvolutionaryMerge()`

Population-based optimization over merge weights (CMA-ES style).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `GeneticMerge()`

Genetic algorithm merge with crossover and mutation (Mergenetic, 2025).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `ModelMergeStrategy()`

Abstract base for all model-merge strategies.

**Properties:**

- `category` — Category grouping (e.g. ``'interpolation'``, ``'evolutionary'``).
- `crdt_properties` — CRDT property declaration.
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — Short unique identifier for this strategy (e.g. ``'slerp'``).
- `paper_reference` — Academic citation or URL for the strategy's paper.

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — Merge a list of array-like tensors into one.
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

### Functions

#### `register_strategy(name: 'str')`

Class decorator that registers a ``ModelMergeStrategy`` subclass.


## `crdt_merge.model.strategies.safety`

> Safety-Aware model-merge strategies.

**Module:** `crdt_merge.model.strategies.safety`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `LEDMerge()`

LEDMerge: Layer-wise Evaluation-Driven best-source selection (2025).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `ModelMergeStrategy()`

Abstract base for all model-merge strategies.

**Properties:**

- `category` — Category grouping (e.g. ``'interpolation'``, ``'evolutionary'``).
- `crdt_properties` — CRDT property declaration.
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — Short unique identifier for this strategy (e.g. ``'slerp'``).
- `paper_reference` — Academic citation or URL for the strategy's paper.

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — Merge a list of array-like tensors into one.
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `SafeMerge()`

Safety-preserving model merging (2025).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

### Functions

#### `register_strategy(name: 'str')`

Class decorator that registers a ``ModelMergeStrategy`` subclass.


## `crdt_merge.model.strategies.subspace`

> Subspace / Sparsification model-merge strategies.

**Module:** `crdt_merge.model.strategies.subspace`

### Classes

#### `AdaptiveRankPruning()`

AdaRank: Per-layer adaptive rank selection + pruned merge (ICLR 2026).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `DareDropAndRescale()`

DARE: Drop And REscale (Yu et al., 2024 — Language Models are Super Mario).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `DareTiesHybrid()`

DARE-TIES: DARE dropping + TIES sign election (Community hybrid, 2024).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `DellaDropElectLowRank()`

DELLA-Merging: DARE + magnitude-aware dropping (Bansal, 2024).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `EMRMerge()`

EMR-Merging: Elect, Mask, Rescale (Huang et al., 2024).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `ModelBreadcrumbs()`

Model Breadcrumbs: Sparse masks + task vector aggregation (Davari & Belilovsky, 2023).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `ModelMergeStrategy()`

Abstract base for all model-merge strategies.

**Properties:**

- `category` — Category grouping (e.g. ``'interpolation'``, ``'evolutionary'``).
- `crdt_properties` — CRDT property declaration.
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — Short unique identifier for this strategy (e.g. ``'slerp'``).
- `paper_reference` — Academic citation or URL for the strategy's paper.

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — Merge a list of array-like tensors into one.
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `SVDKnotTying()`

SVD Knot Tying: Align SVD bases, merge in aligned space (2024).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `SpectralTruncationAdaptiveRescaling()`

STAR: SVD decompose, truncate, rescale, reconstruct (2025).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `TIESMerge()`

TIES-Merging: Trim, Elect sign, Disjoint merge (Yadav et al., NeurIPS 2023).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

### Functions

#### `register_strategy(name: 'str')`

Class decorator that registers a ``ModelMergeStrategy`` subclass.


## `crdt_merge.model.strategies.unlearning`

> Unlearning model-merge strategies.

**Module:** `crdt_merge.model.strategies.unlearning`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `ModelMergeStrategy()`

Abstract base for all model-merge strategies.

**Properties:**

- `category` — Category grouping (e.g. ``'interpolation'``, ``'evolutionary'``).
- `crdt_properties` — CRDT property declaration.
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — Short unique identifier for this strategy (e.g. ``'slerp'``).
- `paper_reference` — Academic citation or URL for the strategy's paper.

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — Merge a list of array-like tensors into one.
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `NegativeMerge()`

NegMerge: Weight negation for unlearning (ICML 2025).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `SplitUnlearnMerge()`

Split → Unlearn → Merge (2025).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

### Functions

#### `register_strategy(name: 'str')`

Class decorator that registers a ``ModelMergeStrategy`` subclass.


## `crdt_merge.model.strategies.weighted`

> Weighted / Importance model-merge strategies.

**Module:** `crdt_merge.model.strategies.weighted`

### Classes

#### `AdaptiveMerging()`

AdaMerging: Entropy-based adaptive merge coefficients (Yang et al., 2024).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `DifferentiableAdaptiveMerging()`

DAM: Differentiable Adaptive Merging via gradient-free coefficient optimization (2024).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `FisherMerge()`

Fisher-weighted averaging (Matena & Raffel, 2022).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `ModelMergeStrategy()`

Abstract base for all model-merge strategies.

**Properties:**

- `category` — Category grouping (e.g. ``'interpolation'``, ``'evolutionary'``).
- `crdt_properties` — CRDT property declaration.
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — Short unique identifier for this strategy (e.g. ``'slerp'``).
- `paper_reference` — Academic citation or URL for the strategy's paper.

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — Merge a list of array-like tensors into one.
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

#### `RegressionMean()`

RegMean: Dataless knowledge fusion via regularized regression mean (Jin et al., 2023).

**Properties:**

- `category` — 
- `crdt_properties` — 
- `crdt_tier` — Auto-classify this strategy's CRDT compliance tier.
- `name` — 
- `paper_reference` — 

**Methods:**

- `merge(self, tensors: 'list', weights: 'Optional[List[float]]' = None, base: 'Any' = None, **kwargs: 'Any') -> 'Any'` — 
- `verify_crdt(self, gen_fn=None, trials: 'int' = 100, base_gen_fn=None) -> 'Dict[str, Any]'` — Empirically verify CRDT properties via random trials.

### Functions

#### `register_strategy(name: 'str')`

Class decorator that registers a ``ModelMergeStrategy`` subclass.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
