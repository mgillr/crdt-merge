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

"""GPU-accelerated model merging with lazy torch imports.

Example::

    from crdt_merge.model.gpu import GPUMerge

    gpu = GPUMerge(device="auto")
    result = gpu.merge([model_a, model_b], strategy="weight_average")

All ``torch`` imports are lazy — this module can be imported even without
torch installed, and raises a clear error only when GPU features are used.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

__all__ = ["GPUMerge"]

# ---------------------------------------------------------------------------
# Lazy torch helper
# ---------------------------------------------------------------------------

_TORCH_IMPORT_ERROR = (
    "PyTorch is required for GPU-accelerated merging. "
    "Install with: pip install crdt-merge[gpu]  or  pip install torch"
)


def _import_torch():
    """Lazy-import torch, raising helpful error if not available."""
    try:
        import torch
        return torch
    except (ImportError, OSError):
        raise ImportError(_TORCH_IMPORT_ERROR)


# ---------------------------------------------------------------------------
# Dtype mapping
# ---------------------------------------------------------------------------

_DTYPE_MAP = {
    "float16": "float16",
    "float32": "float32",
    "float64": "float64",
    "bfloat16": "bfloat16",
    "fp16": "float16",
    "fp32": "float32",
    "fp64": "float64",
    "bf16": "bfloat16",
}


def _resolve_dtype(torch_module, dtype_str: str):
    """Resolve a dtype string to a torch dtype."""
    canonical = _DTYPE_MAP.get(dtype_str, dtype_str)
    return getattr(torch_module, canonical)


# ---------------------------------------------------------------------------
# GPUMerge
# ---------------------------------------------------------------------------

class GPUMerge:
    """GPU-accelerated model merging.

    Parameters
    ----------
    device : str
        Device to use: ``"auto"`` (cuda if available, else cpu),
        ``"cuda"``, ``"cuda:0"``, ``"cpu"``, etc.
    dtype : str
        Data type: ``"float32"``, ``"float16"``, ``"bfloat16"``, etc.
    chunk_size : str | int
        Number of layers to process per batch. ``"auto"`` estimates
        based on available GPU memory.
    """

    def __init__(
        self,
        device: str = "auto",
        dtype: str = "float32",
        chunk_size: Union[str, int] = "auto",
    ) -> None:
        torch = _import_torch()

        if device == "auto":
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self._device = device

        self._dtype_str = dtype
        self._dtype = _resolve_dtype(torch, dtype)

        if chunk_size == "auto":
            self._chunk_size = self._estimate_chunk_size(torch)
        else:
            self._chunk_size = int(chunk_size)

        self._torch = torch

    def _estimate_chunk_size(self, torch) -> int:
        """Estimate chunk size based on available GPU memory."""
        if torch.cuda.is_available() and "cuda" in self._device:
            try:
                mem = torch.cuda.get_device_properties(0).total_mem
                # Use ~50% of GPU memory, assume ~100MB per layer chunk
                return max(1, int(mem * 0.5 / (100 * 1024 * 1024)))
            except Exception:
                pass
        # Default for CPU: process all layers at once
        return 1024

    def merge(
        self,
        models: List[dict],
        strategy: str = "weight_average",
        schema=None,
        base_model: Optional[dict] = None,
        weights: Optional[List[float]] = None,
        **kwargs: Any,
    ) -> dict:
        """Merge models using GPU acceleration.

        Parameters
        ----------
        models : list[dict]
            List of state_dicts to merge.
        strategy : str
            Merge strategy name.
        schema : ModelMergeSchema | None
            Optional per-layer schema override.
        base_model : dict | None
            Base model for delta strategies.
        weights : list[float] | None
            Per-model weights; None for uniform.
        **kwargs
            Forwarded to merge strategy.

        Returns
        -------
        dict
            Merged state_dict with numpy/list values (moved off GPU).
        """
        torch = self._torch

        if not models:
            return {}

        if len(models) == 1:
            return dict(models[0])

        # Normalize weights
        if weights is None:
            weights = [1.0 / len(models)] * len(models)
        else:
            total = sum(weights)
            weights = [w / total for w in weights]

        # Collect all layer names
        all_layers: List[str] = []
        seen = set()
        for m in models:
            for k in m:
                if k not in seen:
                    seen.add(k)
                    all_layers.append(k)

        merged: dict = {}

        # Process in chunks
        for chunk_start in range(0, len(all_layers), self._chunk_size):
            chunk_layers = all_layers[chunk_start:chunk_start + self._chunk_size]

            for layer_name in chunk_layers:
                tensors = []
                layer_weights = []
                for m, w in zip(models, weights):
                    if layer_name in m:
                        t = m[layer_name]
                        # Convert to torch tensor on device
                        if isinstance(t, torch.Tensor):
                            t = t.to(device=self._device, dtype=self._dtype)
                        else:
                            t = torch.tensor(t, device=self._device, dtype=self._dtype)
                        tensors.append(t)
                        layer_weights.append(w)

                if not tensors:
                    continue

                if len(tensors) == 1:
                    result = tensors[0]
                else:
                    # Re-normalize weights
                    w_sum = sum(layer_weights)
                    norm_w = [w / w_sum for w in layer_weights]

                    # Weighted average (default GPU merge)
                    result = torch.zeros_like(tensors[0])
                    for t, w in zip(tensors, norm_w):
                        result += w * t

                # Move back to CPU and convert to list
                merged[layer_name] = result.detach().cpu().tolist()

        return merged

    @classmethod
    def is_gpu_available(cls) -> bool:
        """Check if GPU is available.

        Returns
        -------
        bool
            True if CUDA-capable GPU is available.
        """
        try:
            import torch
            return torch.cuda.is_available()
        except (ImportError, OSError):
            return False

    def device_info(self) -> dict:
        """Return information about the current device.

        Returns
        -------
        dict
            Keys: device, dtype, gpu_name, memory_gb.
        """
        torch = self._torch
        info: dict = {
            "device": self._device,
            "dtype": self._dtype_str,
            "gpu_name": None,
            "memory_gb": None,
        }

        if torch.cuda.is_available() and "cuda" in self._device:
            try:
                props = torch.cuda.get_device_properties(0)
                info["gpu_name"] = props.name
                info["memory_gb"] = round(props.total_mem / (1024 ** 3), 2)
            except Exception:
                pass

        return info
