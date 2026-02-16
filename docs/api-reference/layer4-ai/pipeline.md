# crdt_merge.model.pipeline — Merge Pipeline

**Module**: `crdt_merge/model/pipeline.py`
**Layer**: 4 — AI / Model / Agent
**Dependencies**: `crdt_merge.model.core`, `crdt_merge.model.safety`

---

## Classes

### MergePipeline

Orchestrate multi-step model merge workflows.

```python
class MergePipeline:
    def __init__(self) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `add_step()` | `add_step(name: str, strategy: str, models: List[str], **kwargs) -> MergePipeline` | Add merge step |
| `add_safety_check()` | `add_safety_check(analyzer: SafetyAnalyzer) -> MergePipeline` | Add safety validation |
| `execute()` | `execute() -> PipelineResult` | Execute the pipeline |
| `dry_run()` | `dry_run() -> PipelineReport` | Preview without executing |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `MergePipeline.validate(self) → List[str]`

Validate the pipeline for structural correctness.

        Checks for:
        - Duplicate stage names
        - Missing stage references
        - Cycles in the dependency graph

        Returns
        -------
        list[str]
            List of error messages. Empty list means valid.
        

**Returns:** `List[str]`



### `MergePipeline.to_dict(self) → Dict[str, Any]`

Serialize the pipeline to a plain dict.

        Model values that are dicts are replaced with ``"<state_dict>"``
        placeholder for serialization.
        

**Returns:** `Dict[str, Any]`



### `MergePipeline.from_dict(cls, d: Dict[str, Any]) → 'MergePipeline'`

Deserialize from a dict.

        Note: ``"<state_dict>"`` placeholders become empty dicts.
        

**Parameters:**
- `d` (`Dict[str, Any]`)

**Returns:** `'MergePipeline'`


## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 0
- Inherited methods: 0
- Circular dependencies: None

### RREA Findings
- Entropy profile: Zero
- Dead code: None
- Shadow dependencies: None
- Chokepoint status: None

### Code Quality (Team 2)
- Docstring coverage: 75.0%
- `__all__` defined: Yes
- Code smells: None

### Second Pass
- Heightened findings: None (all 1,063 new inherited methods classified as false positive dunders)
