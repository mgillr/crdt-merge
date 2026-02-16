# crdt_merge.hub — HuggingFace Hub Integration

**Package**: `crdt_merge/hub/`
**Layer**: 4 — AI / Model / Agent
**LOC**: 726

---

## HFMergeHub (`hub/hf.py`)

```python
class HFMergeHub:
    def __init__(self, token: Optional[str] = None) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `pull()` | `pull(model_id: str) -> dict` | Pull model from Hub |
| `push()` | `push(model: dict, repo_id: str, commit_message: str = "") -> str` | Push merged model |
| `merge_from_hub()` | `merge_from_hub(model_ids: List[str], strategy: str = "linear") -> dict` | Pull, merge, return |

## AutoModelCard (`hub/model_card.py`)

```python
class AutoModelCard:
    def __init__(self) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `generate()` | `generate(merge_info: dict) -> str` | Generate model card markdown |
| `from_merge()` | `from_merge(models: List[str], strategy: str, result: dict) -> str` | Generate from merge operation |


## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 2
- Inherited methods: 0
- Circular dependencies: None

### RREA Findings
- Entropy profile: Zero
- Dead code: None
- Shadow dependencies: None
- Chokepoint status: None

### Code Quality (Team 2)
- Docstring coverage: 100.0%
- `__all__` defined: Yes
- Code smells: None

### Second Pass
- Heightened findings: None (all 1,063 new inherited methods classified as false positive dunders)
