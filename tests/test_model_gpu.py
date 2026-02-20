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

"""Tests for crdt_merge.model.gpu — GPUMerge (torch mocked throughout)."""

from __future__ import annotations

import math
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Build a minimal torch stub so GPUMerge can be instantiated without a real
# GPU and without PyTorch being installed.
# ---------------------------------------------------------------------------

class _FakeTensor:
    """Minimal tensor-like object for stub purposes."""

    def __init__(self, data):
        if isinstance(data, (int, float)):
            self._data = [float(data)]
        elif isinstance(data, (list, tuple)):
            flat = data
            # Flatten one level of nesting
            if flat and isinstance(flat[0], (list, tuple)):
                flat = [x for row in flat for x in row]
            self._data = [float(x) for x in flat]
        else:
            self._data = [0.0]

    def detach(self):
        return self

    def cpu(self):
        return self

    def to(self, device=None, dtype=None):
        return self

    def tolist(self):
        return list(self._data)

    def __mul__(self, scalar):
        result = _FakeTensor([v * scalar for v in self._data])
        return result

    def __rmul__(self, scalar):
        return self.__mul__(scalar)

    def __iadd__(self, other):
        if isinstance(other, _FakeTensor):
            for i in range(min(len(self._data), len(other._data))):
                self._data[i] += other._data[i]
        return self


def _make_torch_stub(cuda_available: bool = False):
    """Return a minimal torch-like MagicMock with a real Tensor class."""
    torch_stub = MagicMock(name="torch")

    # dtype constants
    torch_stub.float32 = "float32_dtype"
    torch_stub.float16 = "float16_dtype"
    torch_stub.float64 = "float64_dtype"
    torch_stub.bfloat16 = "bfloat16_dtype"

    # Expose real Tensor class so isinstance checks work
    torch_stub.Tensor = _FakeTensor

    # cuda availability
    torch_stub.cuda.is_available.return_value = cuda_available

    def _tensor(data, device=None, dtype=None):
        return _FakeTensor(data)

    torch_stub.tensor.side_effect = _tensor

    def _zeros_like(ref):
        z = _FakeTensor([0.0] * len(ref._data))
        return z

    torch_stub.zeros_like.side_effect = _zeros_like

    return torch_stub


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def torch_stub():
    stub = _make_torch_stub(cuda_available=False)
    with patch("crdt_merge.model.gpu._import_torch", return_value=stub):
        yield stub


@pytest.fixture()
def gpu_merge(torch_stub):
    from crdt_merge.model.gpu import GPUMerge
    return GPUMerge(device="cpu", dtype="float32", chunk_size=1024)


# ---------------------------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------------------------

class TestGPUMergeInit:
    def test_init_cpu_device(self, torch_stub):
        from crdt_merge.model.gpu import GPUMerge
        g = GPUMerge(device="cpu", dtype="float32", chunk_size=8)
        assert g._device == "cpu"
        assert g._chunk_size == 8

    def test_auto_device_selects_cpu_when_no_cuda(self, torch_stub):
        torch_stub.cuda.is_available.return_value = False
        from crdt_merge.model.gpu import GPUMerge
        g = GPUMerge(device="auto", dtype="float32", chunk_size=4)
        assert g._device == "cpu"

    def test_dtype_resolved(self, torch_stub):
        from crdt_merge.model.gpu import GPUMerge
        g = GPUMerge(device="cpu", dtype="float32", chunk_size=4)
        assert g._dtype == "float32_dtype"

    def test_dtype_aliases_fp16(self, torch_stub):
        from crdt_merge.model.gpu import GPUMerge
        g = GPUMerge(device="cpu", dtype="fp16", chunk_size=4)
        assert g._dtype == "float16_dtype"

    def test_chunk_size_auto_falls_back_to_1024_on_cpu(self, torch_stub):
        torch_stub.cuda.is_available.return_value = False
        from crdt_merge.model.gpu import GPUMerge
        g = GPUMerge(device="cpu", dtype="float32", chunk_size="auto")
        assert g._chunk_size == 1024

    def test_torch_not_installed_raises_import_error(self):
        with patch(
            "crdt_merge.model.gpu._import_torch",
            side_effect=ImportError("PyTorch is required"),
        ):
            from crdt_merge.model.gpu import GPUMerge  # noqa: F401 — already imported
            with pytest.raises(ImportError, match="PyTorch is required"):
                GPUMerge.__new__(GPUMerge).__init__(
                    device="cpu", dtype="float32", chunk_size=4
                )


# ---------------------------------------------------------------------------
# GPUMerge.merge tests
# ---------------------------------------------------------------------------

class TestGPUMergeMerge:
    def test_empty_models_returns_empty(self, gpu_merge):
        result = gpu_merge.merge([])
        assert result == {}

    def test_single_model_returned_as_copy(self, gpu_merge):
        model = {"layer": [1.0, 2.0]}
        result = gpu_merge.merge([model])
        assert result == model

    def test_two_models_uniform_weights(self, torch_stub):
        """With uniform weights the merge should proceed without error."""
        from crdt_merge.model.gpu import GPUMerge
        g = GPUMerge(device="cpu", dtype="float32", chunk_size=1024)
        model_a = {"w": [1.0, 2.0]}
        model_b = {"w": [3.0, 4.0]}
        result = g.merge([model_a, model_b])
        assert "w" in result

    def test_explicit_weights_normalized(self, torch_stub):
        from crdt_merge.model.gpu import GPUMerge
        g = GPUMerge(device="cpu", dtype="float32", chunk_size=1024)
        model_a = {"x": [0.0]}
        model_b = {"x": [4.0]}
        result = g.merge([model_a, model_b], weights=[1.0, 3.0])
        assert "x" in result

    def test_layer_union_includes_missing_layers(self, torch_stub):
        """Layers present in only one model should appear in merged output."""
        from crdt_merge.model.gpu import GPUMerge
        g = GPUMerge(device="cpu", dtype="float32", chunk_size=1024)
        model_a = {"shared": [1.0], "only_a": [2.0]}
        model_b = {"shared": [3.0], "only_b": [4.0]}
        result = g.merge([model_a, model_b])
        assert "shared" in result
        assert "only_a" in result
        assert "only_b" in result


# ---------------------------------------------------------------------------
# GPUMerge.is_gpu_available
# ---------------------------------------------------------------------------

class TestGPUMergeIsGpuAvailable:
    def test_returns_false_when_torch_import_fails(self):
        """is_gpu_available catches ImportError and returns False."""
        import sys
        import builtins

        real_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):
            if name == "torch":
                raise ImportError("no torch")
            return real_import(name, *args, **kwargs)

        # Temporarily remove any cached torch module to force re-import
        torch_backup = sys.modules.pop("torch", None)
        try:
            with patch("builtins.__import__", side_effect=_fake_import):
                from crdt_merge.model.gpu import GPUMerge
                result = GPUMerge.is_gpu_available()
                assert result is False
        finally:
            if torch_backup is not None:
                sys.modules["torch"] = torch_backup

    def test_classmethod_callable_without_instance(self, torch_stub):
        from crdt_merge.model.gpu import GPUMerge
        result = GPUMerge.is_gpu_available()
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# GPUMerge.device_info
# ---------------------------------------------------------------------------

class TestGPUMergeDeviceInfo:
    def test_device_info_keys_present(self, gpu_merge):
        info = gpu_merge.device_info()
        assert "device" in info
        assert "dtype" in info
        assert "gpu_name" in info
        assert "memory_gb" in info

    def test_device_info_cpu_has_no_gpu_name(self, gpu_merge):
        info = gpu_merge.device_info()
        assert info["device"] == "cpu"
        assert info["gpu_name"] is None
        assert info["memory_gb"] is None
