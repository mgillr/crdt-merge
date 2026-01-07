# SPDX-License-Identifier: BUSL-1.1
#
# Copyright 2026 Ryan Gillespie
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""crdt-merge model-merge sub-package — public API surface.

Quick start::

    from crdt_merge.model import ModelCRDT, ModelMergeSchema

    schema = ModelMergeSchema(strategies={"default": "linear"})
    crdt = ModelCRDT(schema)
    result = crdt.merge([model_a, model_b])
"""

from crdt_merge.model.core import MergeResult, ModelMerge, ModelCRDT, ModelMergeSchema
from crdt_merge.model.strategies import (
    get_strategy,
    list_strategies,
    list_strategies_by_category,
    register_strategy,
)
from crdt_merge.model.strategies.base import ModelMergeStrategy
from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema
from crdt_merge.model.pipeline import MergePipeline, PipelineResult
from crdt_merge.model.provenance import (
    ProvenanceTracker,
    ProvenanceSummary,
    LayerProvenance,
    export_provenance,
)
from crdt_merge.model.heatmap import ConflictHeatmap
from crdt_merge.model.continual import ContinualMerge
from crdt_merge.model.federated import FederatedMerge, FederatedResult
from crdt_merge.model.formats import import_mergekit_config, export_mergekit_config
from crdt_merge.model.gpu import GPUMerge
from crdt_merge.model.safety import SafetyAnalyzer, SafetyReport

__all__ = [
    "ModelMerge",
    "ModelCRDT",
    "ModelMergeSchema",
    "MergeResult",
    "ModelMergeStrategy",
    "register_strategy",
    "get_strategy",
    "list_strategies",
    "list_strategies_by_category",
    "LoRAMerge",
    "LoRAMergeSchema",
    "MergePipeline",
    "PipelineResult",
    "ProvenanceTracker",
    "ProvenanceSummary",
    "LayerProvenance",
    "export_provenance",
    "ConflictHeatmap",
    "ContinualMerge",
    "FederatedMerge",
    "FederatedResult",
    "import_mergekit_config",
    "export_mergekit_config",
    "GPUMerge",
    "SafetyAnalyzer",
    "SafetyReport",
]
