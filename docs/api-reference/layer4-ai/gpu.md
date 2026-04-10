# crdt_merge.model.gpu — GPU Merge

**Module**: `crdt_merge/model/gpu.py`
**Layer**: 4 — AI / Model / Agent
**Dependencies**: `crdt_merge.model.core`, `torch`

---

## Classes

### GPUMerge

GPU-accelerated model merging for large models.

```python
class GPUMerge:
    def __init__(self, device: str = "cuda", dtype: str = "float16") -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `merge()` | `merge(models: List[dict], strategy: str = "linear", **kwargs) -> dict` | GPU-accelerated merge |
| `merge_sharded()` | `merge_sharded(shard_paths: List[List[str]], strategy: str = "linear") -> List[dict]` | Merge sharded models |
| `estimate_memory()` | `estimate_memory(model_sizes: List[int]) -> int` | Estimate GPU memory needed |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `GPUMerge.is_gpu_available(cls) → bool`

Check if GPU is available.

        Returns
        -------
        bool
            True if CUDA-capable GPU is available.
        

**Returns:** `bool`


### `GPUMerge.device_info(self) → dict`

Return information about the current device.

        Returns
        -------
        dict
            Keys: device, dtype, gpu_name, memory_gb.
        

**Returns:** `dict`


## Analysis Notes
