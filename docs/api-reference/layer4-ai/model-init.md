# `crdt_merge/model/__init__.py`

> crdt-merge model-merge sub-package — public API surface.

Quick start::

    from crdt_merge.model import ModelCRDT, ModelMergeSchema

    schema = ModelMergeSchema(strategies={"default": "linear"})
    crdt = ModelCRDT(schema)
    result = crdt.merge([model_a, model_b])

**Source:** `crdt_merge/model/__init__.py` | **Lines:** 82

---

**Exports (`__all__`):** `['ModelMerge', 'ModelCRDT', 'ModelMergeSchema', 'MergeResult', 'CRDTMergeState', 'MergeContribution', 'ConflictResolution', 'ModelMergeStrategy', 'register_strategy', 'get_strategy', 'list_strategies', 'list_strategies_by_category', 'LoRAMerge', 'LoRAMergeSchema', 'MergePipeline', 'PipelineResult', 'ProvenanceTracker', 'ProvenanceSummary', 'LayerProvenance', 'export_provenance', 'ConflictHeatmap', 'ContinualMerge', 'FederatedMerge', 'FederatedResult', 'import_mergekit_config', 'export_mergekit_config', 'GPUMerge', 'SafetyAnalyzer', 'SafetyReport']`


## Analysis Notes
