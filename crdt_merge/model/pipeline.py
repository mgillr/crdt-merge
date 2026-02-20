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

"""Multi-stage merge pipelines with checkpoint/resume support.

Allows defining and executing multi-step model merges where the output
of one stage feeds into subsequent stages.  Intermediate results can be
persisted to disk using :class:`PipelineCheckpoint` so that a failed run
can be resumed from the last completed stage.

Example::

    from crdt_merge.model.pipeline import MergePipeline, PipelineCheckpoint

    ckpt = PipelineCheckpoint(path="/tmp/my_pipeline.ckpt.json")
    pipeline = MergePipeline(
        stages=[
            {"name": "stage1", "strategy": "weight_average",
             "models": [model_a, model_b], "base": None},
            {"name": "stage2", "strategy": "weight_average",
             "models": ["$stage1", model_c], "base": None},
        ],
        checkpoint=ckpt,
    )
    result = pipeline.execute()
    print(result.execution_order)  # ['stage1', 'stage2']
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from crdt_merge.model.core import ModelCRDT, ModelMergeSchema

__all__ = ["MergePipeline", "PipelineResult", "PipelineCheckpoint"]

# ---------------------------------------------------------------------------
# PipelineCheckpoint
# ---------------------------------------------------------------------------

class PipelineCheckpoint:
    """Persist and restore intermediate pipeline stage results.

    Stores completed stage outputs as JSON so that :meth:`MergePipeline.execute`
    can skip already-completed stages when resuming after a failure.

    Parameters
    ----------
    path : str
        File path for the checkpoint JSON file.  The file is created (or
        overwritten) on first save and read back automatically on resume.

    Example
    -------
    .. code-block:: python

        ckpt = PipelineCheckpoint("/tmp/pipeline.ckpt.json")
        pipeline = MergePipeline(stages=[...], checkpoint=ckpt)
        result = pipeline.execute()   # saves after each stage
        # If execution fails, re-run the same line — completed stages skip.
        ckpt.clear()                  # remove checkpoint after successful run
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._completed: Dict[str, Dict[str, Any]] = {}
        self._load()

    # -- persistence ----------------------------------------------------------

    def _load(self) -> None:
        """Load checkpoint from disk if it exists."""
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    self._completed = data
            except Exception:
                self._completed = {}

    def _save(self) -> None:
        """Persist checkpoint to disk."""
        try:
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(self._completed, fh)
        except Exception:
            pass  # best-effort; never abort the pipeline on checkpoint I/O failure

    # -- public API -----------------------------------------------------------

    def mark_done(self, stage_name: str, result: Dict[str, Any]) -> None:
        """Record that *stage_name* completed with *result* and persist."""
        self._completed[stage_name] = result
        self._save()

    def get_result(self, stage_name: str) -> Optional[Dict[str, Any]]:
        """Return the cached result for *stage_name*, or *None* if not done."""
        return self._completed.get(stage_name)

    def is_done(self, stage_name: str) -> bool:
        """Return *True* if *stage_name* has a cached result."""
        return stage_name in self._completed

    def clear(self) -> None:
        """Remove all cached results and delete the checkpoint file."""
        self._completed.clear()
        try:
            if os.path.exists(self._path):
                os.remove(self._path)
        except Exception:
            pass

    @property
    def completed_stages(self) -> List[str]:
        """List of stage names that have been completed."""
        return list(self._completed.keys())


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

    def __init__(
        self,
        stages: List[Dict[str, Any]],
        checkpoint: Optional["PipelineCheckpoint"] = None,
    ) -> None:
        self._stages = list(stages)
        self._stage_map: Dict[str, Dict[str, Any]] = {}
        self._checkpoint = checkpoint
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
            # Resume: skip stages that were completed in a previous run
            if self._checkpoint is not None and self._checkpoint.is_done(stage_name):
                cached = self._checkpoint.get_result(stage_name)
                stage_results[stage_name] = cached or {}
                for layer_name in stage_results[stage_name]:
                    pipeline_provenance[layer_name] = {
                        "produced_by_stage": stage_name,
                        "strategy": "checkpoint_restored",
                    }
                continue

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
                            f"Stage '{stage_name}' references '${ref_name}' "
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

            # Save checkpoint after each successful stage
            if self._checkpoint is not None:
                self._checkpoint.mark_done(stage_name, result_sd)

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
