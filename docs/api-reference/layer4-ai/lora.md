# crdt_merge.model.lora — LoRA Merge

**Module**: `crdt_merge/model/lora.py`
**Layer**: 4 — AI / Model / Agent
**Dependencies**: `crdt_merge.model.core`, `torch`

---

## Classes

### LoRAMerge

Merge LoRA (Low-Rank Adaptation) adapters.

```python
class LoRAMerge:
    def __init__(self, strategy: str = "linear", base_model: Optional[str] = None) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `merge()` | `merge(adapters: List[dict], weights: Optional[List[float]] = None) -> dict` | Merge LoRA adapters |
| `merge_into_base()` | `merge_into_base(adapter: dict, base: dict, alpha: float = 1.0) -> dict` | Merge adapter into base model |
| `compose()` | `compose(adapters: List[dict]) -> dict` | Compose multiple adapters |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class LoRAMergeSchema`

Maps adapter module names to merge strategies.

    Similar to :class:`ModelMergeSchema` but keyed by LoRA module names
    (e.g., ``q_proj``, ``v_proj``, ``default``).

    Parameters
    ----------
    strategies : dict[str, str | ModelMergeStrategy]
        Mapping from module name patterns to strategy names or instances.
        Use ``"default"`` key for the fallback strategy.
    


### `LoRAMergeSchema.strategy_for(self, module_name: str) → ModelMergeStrategy`

Return the strategy that applies to *module_name*.

        Resolution: exact match on module name → default.

        Raises
        ------
        KeyError
            If no match and no default.
        

**Parameters:**
- `module_name` (`str`)

**Returns:** `ModelMergeStrategy`

**Raises:** `KeyError(f"No strategy matches module '{module_name}' and no default set")`


### `LoRAMergeSchema.to_dict(self) → Dict[str, str]`

Serialize to a plain dict (strategy names only).

**Returns:** `Dict[str, str]`


### `LoRAMergeSchema.from_dict(cls, d: Dict[str, str]) → 'LoRAMergeSchema'`

Deserialize from a plain dict.

**Parameters:**
- `d` (`Dict[str, str]`)

**Returns:** `'LoRAMergeSchema'`


## Analysis Notes
