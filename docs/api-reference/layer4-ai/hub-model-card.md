# Model Card

> Model card generation with merge provenance metadata for HuggingFace Hub.

**Source:** `crdt_merge/hub/model_card.py`  
**Lines of Code:** 364

## Overview

Model card generation with merge provenance metadata for HuggingFace Hub.

## Classes

### `ModelCardConfig`

Configuration for model card generation.

**Class Attributes:**

- `include_lineage` — `bool = True`
- `include_strategies` — `bool = True`
- `include_crdt_badge` — `bool = True`
- `include_eu_ai_act` — `bool = False`
- `language` — `str = 'en'`
- `license` — `str = 'apache-2.0'`
- `tags` — `List[str] = field(default_factory=list)`

### `AutoModelCard`

Generate HuggingFace model cards with merge provenance metadata.

**Constructor:**

```python
AutoModelCard(config: Optional[ModelCardConfig] = None)
```

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `generate` | `generate(sources: List[str], strategy: str, provenance: Optional[ProvenanceSummary] = None, weights: Optional[List[float]] = None, verified: bool = False, base_card: Optional[str] = None) -> str` | Generate a complete model card in markdown format. |
| `generate_metadata` | `generate_metadata(sources: List[str], strategy: str, provenance: Optional[ProvenanceSummary] = None) -> dict` | Generate YAML frontmatter metadata dictionary. |
| `to_json_ld` | `to_json_ld(sources: List[str], strategy: str, provenance: Optional[ProvenanceSummary] = None) -> dict` | Generate JSON-LD metadata for EU AI Act traceability. |

**Internal Methods:**

- `_generate_lineage_section(sources: List[str], strategy: str, weights: Optional[List[float]]) -> str` — —
- `_generate_strategy_section(strategy: str, provenance: Optional[ProvenanceSummary]) -> str` — —
- `_generate_verification_section(verified: bool) -> str` — —
- `_generate_provenance_section(provenance: ProvenanceSummary) -> str` — —
- `_generate_eu_ai_act_section(json_ld: dict) -> str` — —

## Functions

### `_dict_to_yaml()`

```python
_dict_to_yaml(d: dict, indent: int = 0) -> str
```

Minimal YAML serializer for metadata frontmatter (no PyYAML dependency).


## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 1
- Inherited methods: 0
- Circular dependencies: None

### RREA Findings
- Entropy profile: Zero
- Dead code: None
- Shadow dependencies: None
- Chokepoint status: None

### Code Quality (Team 2)
- Docstring coverage: 50.0%
- `__all__` defined: No
- Code smells: None

### Second Pass
- Heightened findings: None (all 1,063 new inherited methods classified as false positive dunders)
