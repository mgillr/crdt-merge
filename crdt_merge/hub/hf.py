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
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""HuggingFace Hub operations for model merging with CRDT verification."""

from __future__ import annotations

import os
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from crdt_merge.model.core import ModelMerge, ModelCRDT, ModelMergeSchema, MergeResult
from crdt_merge.model.provenance import ProvenanceTracker, ProvenanceSummary
from crdt_merge.model.strategies import get_strategy, list_strategies
from crdt_merge.hub.model_card import AutoModelCard, ModelCardConfig


_HF_INSTALL_MSG = (
    "huggingface_hub is required for HuggingFace Hub integration. "
    "Install it with: pip install huggingface_hub"
)


def _require_hf_hub():
    """Lazy-import huggingface_hub, raising a clear error if missing."""
    try:
        import huggingface_hub
        return huggingface_hub
    except ImportError:
        raise ImportError(_HF_INSTALL_MSG)


@dataclass
class HFMergeResult:
    """Result of a Hub-based model merge operation.

    Attributes
    ----------
    state_dict : dict
        Merged model weights as a state dictionary.
    provenance : ProvenanceSummary or None
        Per-layer provenance information from the merge.
    model_card : str
        Generated markdown model card with merge metadata.
    repo_url : str or None
        URL of the HuggingFace repository if pushed, else None.
    """

    state_dict: dict
    provenance: Optional[ProvenanceSummary]
    model_card: str
    repo_url: Optional[str] = None


class HFMergeHub:
    """Push, pull, and merge models on HuggingFace Hub with CRDT verification.

    Requires: pip install huggingface_hub

    Parameters
    ----------
    token : str, optional
        HuggingFace API token. If None, uses HF_TOKEN env var or cached login.
    cache_dir : str, optional
        Local cache directory for downloaded models.
    """

    def __init__(self, token: Optional[str] = None, cache_dir: Optional[str] = None):
        self.token = token or os.environ.get("HF_TOKEN")
        self.cache_dir = cache_dir

    def _hub_api(self):
        """Return a HfApi instance. Isolated for easy mocking in tests."""
        hf = _require_hf_hub()
        return hf.HfApi(token=self.token)

    def merge(
        self,
        sources: List[str],
        strategy: str = "weight_average",
        weights: Optional[List[float]] = None,
        destination: Optional[str] = None,
        auto_model_card: bool = True,
        private: bool = False,
        commit_message: Optional[str] = None,
    ) -> HFMergeResult:
        """Merge models from HuggingFace Hub with CRDT-verified provenance.

        Parameters
        ----------
        sources : list of str
            HuggingFace repo IDs (e.g., ``["user/modelA", "user/modelB"]``).
        strategy : str
            Merge strategy name (default: ``"weight_average"``).
        weights : list of float, optional
            Per-source weights for weighted merges.
        destination : str, optional
            HuggingFace repo ID to push the merged model to.
        auto_model_card : bool
            Generate a provenance-enriched model card (default: True).
        private : bool
            Whether the destination repo should be private.
        commit_message : str, optional
            Commit message for the push.

        Returns
        -------
        HFMergeResult
            Merge result with state dict, provenance, model card, and repo URL.
        """
        if len(sources) < 2:
            raise ValueError("At least two source models are required for merging.")

        available = list_strategies()
        if strategy not in available:
            raise ValueError(
                f"Unknown strategy {strategy!r}. "
                f"Available: {', '.join(sorted(available))}"
            )

        # Pull weights from each source
        model_dicts = [self.pull_weights(repo_id) for repo_id in sources]

        # Perform CRDT-verified merge
        schema = ModelMergeSchema(strategies={"default": strategy})
        merger = ModelCRDT(schema)
        result: MergeResult = merger.merge(model_dicts, weights=weights)

        state_dict = result.tensor if isinstance(result.tensor, dict) else result.tensor
        provenance = result.provenance

        # Generate model card
        card_text = ""
        if auto_model_card:
            card_gen = AutoModelCard()
            card_text = card_gen.generate(
                sources=sources,
                strategy=strategy,
                provenance=provenance,
                weights=weights,
                verified=True,
            )

        # Push to Hub if destination given
        repo_url = None
        if destination:
            repo_url = self.push_weights(
                state_dict=state_dict,
                repo_id=destination,
                model_card=card_text if auto_model_card else None,
                commit_message=commit_message or f"Merge {len(sources)} models via {strategy}",
                private=private,
            )

        return HFMergeResult(
            state_dict=state_dict,
            provenance=provenance,
            model_card=card_text,
            repo_url=repo_url,
        )

    def pull_weights(self, repo_id: str, revision: Optional[str] = None) -> dict:
        """Download model weights from a HuggingFace Hub repository.

        Parameters
        ----------
        repo_id : str
            HuggingFace repo ID (e.g., ``"user/model-name"``).
        revision : str, optional
            Git revision (branch, tag, or commit hash).

        Returns
        -------
        dict
            Model state dictionary.
        """
        hf = _require_hf_hub()
        api = self._hub_api()

        # Download model files to local cache
        local_dir = api.snapshot_download(
            repo_id=repo_id,
            revision=revision,
            cache_dir=self.cache_dir,
        )
        local_path = Path(local_dir)

        # Try safetensors first, then pytorch bin
        safetensor_files = list(local_path.glob("*.safetensors"))
        if safetensor_files:
            try:
                from safetensors.torch import load_file
                state_dict = {}
                for sf in sorted(safetensor_files):
                    state_dict.update(load_file(str(sf)))
                return state_dict
            except ImportError:
                pass

        bin_files = list(local_path.glob("*.bin"))
        if bin_files:
            try:
                import torch
                state_dict = {}
                for bf in sorted(bin_files):
                    state_dict.update(torch.load(str(bf), map_location="cpu"))
                return state_dict
            except ImportError:
                pass

        raise FileNotFoundError(
            f"No loadable weight files found in {repo_id}. "
            "Install safetensors or torch to load model weights."
        )

    def push_weights(
        self,
        state_dict: dict,
        repo_id: str,
        model_card: Optional[str] = None,
        commit_message: str = "Upload merged model",
        private: bool = False,
    ) -> str:
        """Push model weights to a HuggingFace Hub repository.

        Parameters
        ----------
        state_dict : dict
            Model state dictionary to upload.
        repo_id : str
            Target HuggingFace repo ID.
        model_card : str, optional
            Model card markdown to include as README.md.
        commit_message : str
            Commit message for the upload.
        private : bool
            Whether the repository should be private.

        Returns
        -------
        str
            URL of the created/updated repository.
        """
        hf = _require_hf_hub()
        api = self._hub_api()

        # Create repo (no-op if exists)
        repo_url_obj = api.create_repo(
            repo_id=repo_id,
            private=private,
            exist_ok=True,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Save weights
            try:
                from safetensors.torch import save_file
                weight_file = tmp_path / "model.safetensors"
                save_file(state_dict, str(weight_file))
            except ImportError:
                import torch
                weight_file = tmp_path / "pytorch_model.bin"
                torch.save(state_dict, str(weight_file))

            # Save model card
            if model_card:
                readme_path = tmp_path / "README.md"
                readme_path.write_text(model_card, encoding="utf-8")

            # Upload folder
            api.upload_folder(
                folder_path=str(tmp_path),
                repo_id=repo_id,
                commit_message=commit_message,
            )

        return f"https://huggingface.co/{repo_id}"

    def list_merge_models(
        self, author: Optional[str] = None, limit: int = 20
    ) -> List[dict]:
        """List models on HuggingFace Hub tagged with merge metadata.

        Parameters
        ----------
        author : str, optional
            Filter by author/organization.
        limit : int
            Maximum number of results to return (default: 20).

        Returns
        -------
        list of dict
            Model metadata dictionaries with keys: id, author, tags, downloads.
        """
        api = self._hub_api()

        filter_kwargs = {"tags": "merge"}
        if author:
            filter_kwargs["author"] = author

        models = api.list_models(**filter_kwargs, limit=limit)

        results = []
        for model in models:
            results.append({
                "id": model.id if hasattr(model, "id") else str(model),
                "author": getattr(model, "author", None),
                "tags": getattr(model, "tags", []),
                "downloads": getattr(model, "downloads", 0),
            })
        return results
