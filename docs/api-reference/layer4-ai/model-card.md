# `crdt_merge/hub/model_card.py`

> Model card generation with merge provenance metadata for HuggingFace Hub.

**Source:** `crdt_merge/hub/model_card.py` | **Lines:** 364

---

## Classes

### `class ModelCardConfig`

Configuration for model card generation.

    Attributes
    ----------
    include_lineage : bool
        Include merge lineage section showing source models (default: True).
    include_strategies : bool
        Include per-layer strategy breakdown (default: True).
    include_crdt_badge : bool
        Include CRDT convergence verification badge (default: True).
    include_eu_ai_act : bool
        Include EU AI Act traceability JSON-LD block (default: False).
    language : str
        Model language tag (default: ``"en"``).
    license : str
        License identifier (default: ``"apache-2.0"``).
    tags : list of str
        Additional tags for the model card.

- `include_lineage`: `bool`
- `include_strategies`: `bool`
- `include_crdt_badge`: `bool`
- `include_eu_ai_act`: `bool`
- `language`: `str`
- `license`: `str`
- `tags`: `List[str]`

### `class AutoModelCard`

Generate HuggingFace model cards with merge provenance metadata.

    Produces markdown model cards that include:
    - Merge lineage DAG (which models contributed)
    - Per-layer strategy decisions
    - CRDT convergence verification status
    - Optional EU AI Act traceability metadata (JSON-LD)

    Parameters
    ----------
    config : ModelCardConfig, optional
        Card generation configuration. Uses defaults if None.


**Methods:**

#### `AutoModelCard.__init__(self, config: Optional[ModelCardConfig] = None)`

*No docstring*

#### `AutoModelCard.generate(self, sources: List[str], strategy: str, provenance: Optional[ProvenanceSummary] = None, weights: Optional[List[float]] = None, verified: bool = False, base_card: Optional[str] = None) → str`

Generate a complete model card in markdown format.

        Parameters
        ----------
        sources : list of str
            Source model identifiers (repo IDs or names).
        strategy : str
            Primary merge strategy used.
        provenance : ProvenanceSummary, optional
            Merge provenance data for detailed lineage.
        weights : list of float, optional
            Per-source merge weights.
        verified : bool
            Whether the merge passed CRDT convergence verification.
        base_card : str, optional
            Existing model card to append merge sections to.

        Returns
        -------
        str
            Complete markdown model card.

#### `AutoModelCard.generate_metadata(self, sources: List[str], strategy: str, provenance: Optional[ProvenanceSummary] = None) → dict`

Generate YAML frontmatter metadata dictionary.

        Parameters
        ----------
        sources : list of str
            Source model identifiers.
        strategy : str
            Primary merge strategy.
        provenance : ProvenanceSummary, optional
            Merge provenance data.

        Returns
        -------
        dict
            Metadata suitable for HuggingFace model card YAML frontmatter.

#### `AutoModelCard.to_json_ld(self, sources: List[str], strategy: str, provenance: Optional[ProvenanceSummary] = None) → dict`

Generate JSON-LD metadata for EU AI Act traceability.

        Parameters
        ----------
        sources : list of str
            Source model identifiers.
        strategy : str
            Primary merge strategy.
        provenance : ProvenanceSummary, optional
            Merge provenance data.

        Returns
        -------
        dict
            JSON-LD structured metadata for regulatory compliance.

#### `AutoModelCard._generate_lineage_section(self, sources: List[str], strategy: str, weights: Optional[List[float]]) → str`

*No docstring*

#### `AutoModelCard._generate_strategy_section(self, strategy: str, provenance: Optional[ProvenanceSummary]) → str`

*No docstring*

#### `AutoModelCard._generate_verification_section(self, verified: bool) → str`

*No docstring*

#### `AutoModelCard._generate_provenance_section(self, provenance: ProvenanceSummary) → str`

*No docstring*

#### `AutoModelCard._generate_eu_ai_act_section(self, json_ld: dict) → str`

*No docstring*


## Functions

### `_dict_to_yaml(d: dict, indent: int = 0) → str`

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
