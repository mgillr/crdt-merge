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

"""HuggingFace Hub source and target adapters for merge pipelines."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional


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


class HfSource:
    """Load model weights from HuggingFace Hub for use in merge pipelines.

    Parameters
    ----------
    repo_id : str
        HuggingFace repo ID (e.g., ``"user/model-name"``).
    revision : str, optional
        Git revision (branch, tag, or commit hash).
    token : str, optional
        HuggingFace API token. If None, uses HF_TOKEN env var or cached login.
    """

    def __init__(
        self,
        repo_id: str,
        revision: Optional[str] = None,
        token: Optional[str] = None,
    ):
        self.repo_id = repo_id
        self.revision = revision
        self.token = token or os.environ.get("HF_TOKEN")

    def _hub_api(self):
        """Return a HfApi instance. Isolated for easy mocking in tests."""
        hf = _require_hf_hub()
        return hf.HfApi(token=self.token)

    def load(self) -> dict:
        """Download and load model weights from HuggingFace Hub.

        Returns
        -------
        dict
            Model state dictionary.

        Raises
        ------
        FileNotFoundError
            If no loadable weight files are found.
        ImportError
            If huggingface_hub is not installed.
        """
        api = self._hub_api()

        local_dir = api.snapshot_download(
            repo_id=self.repo_id,
            revision=self.revision,
        )
        local_path = Path(local_dir)

        # Try safetensors first
        safetensor_files = list(local_path.glob("*.safetensors"))
        if safetensor_files:
            try:
                from safetensors.torch import load_file
                state_dict = {}
                for sf in sorted(safetensor_files):
                    state_dict.update(load_file(str(sf)))
                return state_dict
            except ImportError:
                pass  # nosec B110

        # Fallback to pytorch bin
        bin_files = list(local_path.glob("*.bin"))
        if bin_files:
            try:
                import torch
                state_dict = {}
                for bf in sorted(bin_files):
                    state_dict.update(torch.load(str(bf), map_location="cpu", weights_only=True))
                return state_dict
            except ImportError:
                pass  # nosec B110

        raise FileNotFoundError(
            f"No loadable weight files found in {self.repo_id}. "
            "Install safetensors or torch to load model weights."
        )


class HfTarget:
    """Push merged model weights to HuggingFace Hub.

    Parameters
    ----------
    repo_id : str
        Target HuggingFace repo ID.
    token : str, optional
        HuggingFace API token. If None, uses HF_TOKEN env var or cached login.
    private : bool
        Whether the repository should be private (default: False).
    """

    def __init__(
        self,
        repo_id: str,
        token: Optional[str] = None,
        private: bool = False,
    ):
        self.repo_id = repo_id
        self.token = token or os.environ.get("HF_TOKEN")
        self.private = private

    def _hub_api(self):
        """Return a HfApi instance. Isolated for easy mocking in tests."""
        hf = _require_hf_hub()
        return hf.HfApi(token=self.token)

    def save(
        self,
        state_dict: dict,
        model_card: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> str:
        """Upload model weights to HuggingFace Hub.

        Parameters
        ----------
        state_dict : dict
            Model state dictionary to upload.
        model_card : str, optional
            Model card markdown to include as README.md.
        commit_message : str, optional
            Commit message for the upload.

        Returns
        -------
        str
            URL of the created/updated repository.
        """
        api = self._hub_api()

        api.create_repo(
            repo_id=self.repo_id,
            private=self.private,
            exist_ok=True,
        )

        msg = commit_message or "Upload merged model"

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

            api.upload_folder(
                folder_path=str(tmp_path),
                repo_id=self.repo_id,
                commit_message=msg,
            )

        return f"https://huggingface.co/{self.repo_id}"
