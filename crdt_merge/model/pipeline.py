# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Multi-stage merge pipelines.

Allows defining and executing multi-step model merges where the output
of one stage feeds into subsequent stages.

Example::

    from crdt_merge.model.pipeline import MergePipeline

    pipeline = MergePipeline(stages=[
        {"name": "stage1", "strategy": "weight_average",
         "models": [model_a, model_b], "base": None},
        {"name": "stage2", "strategy": "weight_average",
         "models": ["$stage1", model_c], "base": None},
    ])
    result = pipeline.execute()
    print(result.execution_order)  # ['stage1', 'stage2']

Note: Checkpoint/resume is planned for a future version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from crdt_merge.model.core import ModelCRDT, ModelMergeSchema

__all__ = ["MergePipeline", "PipelineResult"]

# ---------------------------------------------------------------------------
# PipelineResult
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Result of a pipeline execution.

    Attributes
    ----------
    final_model : dict
        Final merged state_dict (output of the last stage).
    stage_results : dict[str, dict]
        Output state_dict of each stage.
    pipeline_provenance : dict
        Provenance across all stages — which stage produced each layer's
        final value.
    execution_order : list[str]
        Actual order in which stages were executed.
    """

    final_model: Dict[str, Any]
    stage_results: Dict[str, Dict[str, Any]]
    pipeline_provenance: Dict[str, Any]
    execution_order: List[str]

# ---------------------------------------------------------------------------
# MergePipeline
# ---------------------------------------------------------------------------

class MergePipeline:
    """Define and execute multi-stage model merge pipelines.

    Parameters
    ----------
    stages : list[dict]
        Each stage is a dict with keys:
        - ``name`` (str): unique stage identifier
        - ``strategy`` (str): merge strategy name
        - ``models`` (list): model state_dicts or ``"$stage_name"`` references
        - ``base`` (dict | str | None): optional base model or reference
        - ``weights`` (list[float] | None): optional per-model weights
    """

    def __init__(self, stages: List[Dict[str, Any]]) -> None:
        self._stages = list(stages)
        self._stage_map: Dict[str, Dict[str, Any]] = {}
        for stage in self._stages:
            name = stage.get("name", "")
            if name:
                self._stage_map[name] = stage

    def execute(self, output_path: Optional[str] = None) -> PipelineResult:
        """Execute all stages in dependency order.

        Parameters
        ----------
        output_path : str | None
            Reserved for future use.

        Returns
        -------
        PipelineResult

        Raises
        ------
        ValueError
            If the pipeline has cycles or missing references.
        """
        errors = self.validate()
        if errors:
            raise ValueError(f"Pipeline validation failed: {'; '.join(errors)}")

        order = self._topological_sort()
        stage_results: Dict[str, Dict[str, Any]] = {}
        pipeline_provenance: Dict[str, Any] = {}

        for stage_name in order:
            stage = self._stage_map[stage_name]
            strategy_name = stage.get("strategy", "weight_average")
            models_spec = stage.get("models", [])
            base_spec = stage.get("base")
            weights = stage.get("weights")

            # Resolve model references
            resolved_models = []
            for m in models_spec:
                if isinstance(m, str) and m.startswith("$"):
                    ref_name = m[1:]
                    if ref_name in stage_results:
                        resolved_models.append(stage_results[ref_name])
                    else:
                        raise ValueError(
                            f"Stage '{stage_name}' references '${ ref_name}' "
                            f"but it hasn't been executed yet"
                        )
                else:
                    resolved_models.append(m)

            # Resolve base
            resolved_base = None
            if isinstance(base_spec, str) and base_spec.startswith("$"):
                ref_name = base_spec[1:]
                if ref_name in stage_results:
                    resolved_base = stage_results[ref_name]
            elif base_spec is not None:
                resolved_base = base_spec

            # Create schema and CRDT for this stage
            schema = ModelMergeSchema(strategies={"default": strategy_name})
            crdt = ModelCRDT(schema)

            # Execute merge
            if len(resolved_models) == 0:
                result_sd = {}
            elif len(resolved_models) == 1:
                result_sd = dict(resolved_models[0]) if isinstance(resolved_models[0], dict) else {}
            else:
                merge_result = crdt.merge(
                    resolved_models,
                    base_model=resolved_base,
                    weights=weights,
                )
                result_sd = merge_result.tensor if isinstance(merge_result.tensor, dict) else {}

            stage_results[stage_name] = result_sd

            # Record provenance
            for layer_name in result_sd:
                pipeline_provenance[layer_name] = {
                    "produced_by_stage": stage_name,
                    "strategy": strategy_name,
                }

        # Final model is the last executed stage
        final_model = stage_results[order[-1]] if order else {}

        return PipelineResult(
            final_model=final_model,
            stage_results=stage_results,
            pipeline_provenance=pipeline_provenance,
            execution_order=order,
        )

    def validate(self) -> List[str]:
        """Validate the pipeline for structural correctness.

        Checks for:
        - Duplicate stage names
        - Missing stage references
        - Cycles in the dependency graph

        Returns
        -------
        list[str]
            List of error messages. Empty list means valid.
        """
        errors: List[str] = []

        # Check for duplicate names
        names = [s.get("name", "") for s in self._stages]
        seen = set()
        for n in names:
            if not n:
                errors.append("Stage missing 'name' field")
            elif n in seen:
                errors.append(f"Duplicate stage name: '{n}'")
            seen.add(n)

        # Check references
        stage_names = set(self._stage_map.keys())
        for stage in self._stages:
            stage_name = stage.get("name", "<unnamed>")
            for m in stage.get("models", []):
                if isinstance(m, str) and m.startswith("$"):
                    ref = m[1:]
                    if ref not in stage_names:
                        errors.append(
                            f"Stage '{stage_name}' references unknown stage '${ref}'"
                        )
            base = stage.get("base")
            if isinstance(base, str) and base.startswith("$"):
                ref = base[1:]
                if ref not in stage_names:
                    errors.append(
                        f"Stage '{stage_name}' base references unknown stage '${ref}'"
                    )

        # Check for cycles via DFS
        if not errors:
            cycle_errors = self._detect_cycles()
            errors.extend(cycle_errors)

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the pipeline to a plain dict.

        Model values that are dicts are replaced with ``"<state_dict>"``
        reserved for future serialization extensions.
        """
        stages_out = []
        for stage in self._stages:
            s = dict(stage)
            models_out = []
            for m in s.get("models", []):
                if isinstance(m, str):
                    models_out.append(m)
                elif isinstance(m, dict):
                    models_out.append("<state_dict>")
                else:
                    models_out.append(str(m))
            s["models"] = models_out
            if isinstance(s.get("base"), dict):
                s["base"] = "<state_dict>"
            stages_out.append(s)
        return {"stages": stages_out}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MergePipeline":
        """Deserialize from a dict.

        Note: ``"<state_dict>"`` placeholders become empty dicts.
        """
        stages = []
        for s in d.get("stages", []):
            stage = dict(s)
            models = []
            for m in stage.get("models", []):
                if m == "<state_dict>":
                    models.append({})
                else:
                    models.append(m)
            stage["models"] = models
            if stage.get("base") == "<state_dict>":
                stage["base"] = {}
            stages.append(stage)
        return cls(stages=stages)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_dependencies(self, stage: Dict) -> List[str]:
        """Get stage names that this stage depends on."""
        deps = []
        for m in stage.get("models", []):
            if isinstance(m, str) and m.startswith("$"):
                deps.append(m[1:])
        base = stage.get("base")
        if isinstance(base, str) and base.startswith("$"):
            deps.append(base[1:])
        return deps

    def _topological_sort(self) -> List[str]:
        """Topological sort of stages using DFS.

        Returns
        -------
        list[str]
            Stage names in execution order.
        """
        visited = set()
        order = []
        temp = set()

        def dfs(name: str) -> None:
            if name in visited:
                return
            if name in temp:
                raise ValueError(f"Cycle detected involving stage '{name}'")
            temp.add(name)

            stage = self._stage_map.get(name)
            if stage:
                for dep in self._get_dependencies(stage):
                    dfs(dep)

            temp.remove(name)
            visited.add(name)
            order.append(name)

        for name in self._stage_map:
            if name not in visited:
                dfs(name)

        return order

    def _detect_cycles(self) -> List[str]:
        """Detect cycles in the dependency graph.

        Returns
        -------
        list[str]
            Error messages for detected cycles.
        """
        errors = []
        visited = set()
        path = set()

        def dfs(name: str) -> bool:
            if name in path:
                errors.append(f"Cycle detected involving stage '{name}'")
                return True
            if name in visited:
                return False
            visited.add(name)
            path.add(name)

            stage = self._stage_map.get(name)
            if stage:
                for dep in self._get_dependencies(stage):
                    if dfs(dep):
                        return True

            path.remove(name)
            return False

        for name in self._stage_map:
            if name not in visited:
                dfs(name)

        return errors
