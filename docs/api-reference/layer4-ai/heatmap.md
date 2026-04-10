# crdt_merge.model.heatmap — Conflict Heatmap

**Module**: `crdt_merge/model/heatmap.py`
**Layer**: 4 — AI / Model / Agent
**Dependencies**: `crdt_merge.model.core`, `numpy`

---

## Classes

### ConflictHeatmap

Visualize merge conflicts across model layers.

```python
class ConflictHeatmap:
    def __init__(self) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `compute()` | `compute(models: List[dict]) -> HeatmapData` | Compute conflict intensity per layer |
| `to_html()` | `to_html(data: HeatmapData) -> str` | Render as HTML heatmap |
| `to_json()` | `to_json(data: HeatmapData) -> str` | Export as JSON |
| `to_matplotlib()` | `to_matplotlib(data: HeatmapData) -> Figure` | Render as matplotlib figure |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class LayerDetail`

Detailed parameter-level analysis for a single layer.

    Attributes
    ----------
    variance_map : list[float]
        Per-parameter variance across models.
    sign_agreement : float
        Fraction of parameters where all models agree on sign [0, 1].
    magnitude_spread : float
        Standard deviation of magnitudes across models.
    

**Attributes:**
- `variance_map`: `List[float]`
- `sign_agreement`: `float`
- `magnitude_spread`: `float`


### `ConflictHeatmap.from_merge(cls, provenance_summary: ProvenanceSummary) → 'ConflictHeatmap'`

Build heatmap from provenance data.

        Parameters
        ----------
        provenance_summary : ProvenanceSummary
            Output from :meth:`ProvenanceTracker.summary`.
        

**Parameters:**
- `provenance_summary` (`ProvenanceSummary`)

**Returns:** `'ConflictHeatmap'`


### `ConflictHeatmap.layer_conflicts(self) → Dict[str, float]`

Per-layer conflict scores.

**Returns:** `Dict[str, float]`


### `ConflictHeatmap.model_contributions(self) → Dict[str, Dict[int, float]]`

Per-layer per-model contribution fractions.

**Returns:** `Dict[str, Dict[int, float]]`


### `ConflictHeatmap.num_layers(self) → int`

Number of layers in the heatmap.

**Returns:** `int`


### `ConflictHeatmap.num_models(self) → int`

Number of models being compared.

**Returns:** `int`


### `ConflictHeatmap.overall_conflict(self) → float`

Mean conflict score across all layers.

**Returns:** `float`


### `ConflictHeatmap.most_conflicted_layers(self, n: int = 10) → List[Tuple[str, float]]`

Return the *n* most conflicted layers.

        Returns
        -------
        list[tuple[str, float]]
            (layer_name, conflict_score) sorted descending.
        

**Parameters:**
- `n` (`int`)

**Returns:** `List[Tuple[str, float]]`


### `ConflictHeatmap.least_conflicted_layers(self, n: int = 10) → List[Tuple[str, float]]`

Return the *n* least conflicted layers.

        Returns
        -------
        list[tuple[str, float]]
            (layer_name, conflict_score) sorted ascending.
        

**Parameters:**
- `n` (`int`)

**Returns:** `List[Tuple[str, float]]`


### `ConflictHeatmap.parameter_detail(self, layer_name: str) → LayerDetail`

Get detailed parameter-level analysis for a layer.

        Parameters
        ----------
        layer_name : str
            Name of the layer to analyze.

        Returns
        -------
        LayerDetail

        Raises
        ------
        KeyError
            If layer_name is not in the heatmap.
        

**Parameters:**
- `layer_name` (`str`)

**Returns:** `LayerDetail`

**Raises:** `KeyError(f"Layer '{layer_name}' not found in heatmap")`


### `ConflictHeatmap.to_csv(self, path: Optional[str] = None) → str`

Export heatmap as CSV.

        Parameters
        ----------
        path : str | None
            If provided, also write to this file path.

        Returns
        -------
        str
            CSV string.
        

**Parameters:**
- `path` (`Optional[str]`)

**Returns:** `str`


### `ConflictHeatmap.to_dict(self) → Dict[str, Any]`

Export heatmap as a plain dict.

        Returns
        -------
        dict
        

**Returns:** `Dict[str, Any]`


## Analysis Notes
