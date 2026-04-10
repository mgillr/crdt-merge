# crdt_merge.model.safety — Safety Analyzer

**Module**: `crdt_merge/model/safety.py`
**Layer**: 4 — AI / Model / Agent
**Dependencies**: `crdt_merge.model.core`, `torch`

---

## Classes

### SafetyAnalyzer

Analyze merged models for safety issues.

```python
class SafetyAnalyzer:
    def __init__(self, checks: Optional[List[str]] = None) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `analyze()` | `analyze(model: dict, reference: Optional[dict] = None) -> SafetyReport` | Run safety analysis |
| `check_divergence()` | `check_divergence(model_a: dict, model_b: dict) -> float` | Measure weight divergence |
| `check_nan_inf()` | `check_nan_inf(model: dict) -> List[str]` | Find NaN/Inf weights |
| `check_magnitude()` | `check_magnitude(model: dict, threshold: float = 100.0) -> List[str]` | Find abnormally large weights |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class SafeMerge(ModelMergeStrategy)`

Safety-preserving model merging (2025).

    Identifies safety-critical parameters and freezes them (uses base
    model's values), then merges the remaining parameters via averaging.

    When ``safety_layers="auto"``, identifies safety-critical params
    as those with highest variance across models.
    


### `SafeMerge.name(self) → str`

*No docstring — needs documentation.*

**Returns:** `str`


### `SafeMerge.category(self) → str`

*No docstring — needs documentation.*

**Returns:** `str`


### `SafeMerge.paper_reference(self) → str`

*No docstring — needs documentation.*

**Returns:** `str`


### `SafeMerge.crdt_properties(self) → Dict[str, Any]`

*No docstring — needs documentation.*

**Returns:** `Dict[str, Any]`


### `class LEDMerge(ModelMergeStrategy)`

LEDMerge: Layer-wise Evaluation-Driven best-source selection (2025).

    For each parameter position, picks the source closest to the mean
    (lowest L2 distance). With an optional ``eval_fn``, evaluates each
    source per position and picks the best.
    


### `LEDMerge.name(self) → str`

*No docstring — needs documentation.*

**Returns:** `str`


### `LEDMerge.category(self) → str`

*No docstring — needs documentation.*

**Returns:** `str`


### `LEDMerge.paper_reference(self) → str`

*No docstring — needs documentation.*

**Returns:** `str`


### `LEDMerge.crdt_properties(self) → Dict[str, Any]`

*No docstring — needs documentation.*

**Returns:** `Dict[str, Any]`


## Analysis Notes
