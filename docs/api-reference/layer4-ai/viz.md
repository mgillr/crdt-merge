# crdt_merge.viz — Conflict Visualization

**Module**: `crdt_merge/viz.py`
**Layer**: 4 — AI / Model / Agent
**LOC**: 509
**Dependencies**: `crdt_merge.core`, `json`

---

## Classes

### ConflictTopology

Visualize conflict patterns as a topology.

```python
class ConflictTopology:
    def __init__(self) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `add_conflict()` | `add_conflict(key: str, field: str, val_a: Any, val_b: Any, resolved: Any) -> None` | Record conflict |
| `to_d3_json()` | `to_d3_json() -> str` | Export as D3.js compatible JSON |
| `to_html()` | `to_html() -> str` | Render interactive HTML visualization |
| `summary()` | `summary() -> dict` | Conflict statistics |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class ConflictRecord`

A single conflict event.

    Attributes:
        key: Record key where conflict occurred.
        field: Field name.
        sources: Contributing sources.
        values: Conflicting values.
        resolved_value: Value after resolution.
        strategy: Strategy used (default ``"lww"``).
        timestamp: When conflict occurred (ISO-8601 string, optional).
    

**Attributes:**
- `key`: `Any`
- `field`: `str`
- `sources`: `List[str]`
- `values`: `List[Any]`
- `resolved_value`: `Any`
- `strategy`: `str`
- `timestamp`: `Optional[str]`



### `ConflictRecord.to_dict(self) → Dict[str, Any]`

Serialise to a plain dict.

**Returns:** `Dict[str, Any]`



### `class ConflictCluster`

Group of related conflicts sharing a pattern.

    Attributes:
        fields: Fields involved.
        source_pairs: Source pairs in conflict.
        count: Number of conflicts.
        pattern: Description of pattern.
    

**Attributes:**
- `fields`: `List[str]`
- `source_pairs`: `List[Tuple[str, str]]`
- `count`: `int`
- `pattern`: `str`



### `ConflictTopology.from_merge(cls, result: Any, provenance: Optional[Any] = None) → ConflictTopology`

Create from a merge result and optional provenance log.

        Extracts conflict information from merge output and provenance data.

        Supports:
        - ``MergeQLResult`` objects (with ``.data`` and ``.conflicts`` attrs)
        - ``ProvenanceLog`` objects passed as *provenance*
        - Plain list-of-dicts *result* (scanned for ``_provenance`` keys)

        Args:
            result: Merge result (list of dicts with ``_provenance``, or ``MergeQLResult``).
            provenance: Optional ``ProvenanceLog`` for detailed analysis.

        Returns:
            :class:`ConflictTopology` instance.
        

**Parameters:**
- `result` (`Any`)
- `provenance` (`Optional[Any]`)

**Returns:** `ConflictTopology`



### `ConflictTopology.from_records(cls, conflicts: List[Dict[str, Any]]) → ConflictTopology`

Create from raw conflict dicts.

        Args:
            conflicts: List of dicts with keys:
                ``key``, ``field``, ``sources``, ``values``, ``resolved_value``.

        Returns:
            :class:`ConflictTopology` instance.
        

**Parameters:**
- `conflicts` (`List[Dict[str, Any]]`)

**Returns:** `ConflictTopology`



### `ConflictTopology.heatmap(self) → Dict[str, Dict[str, int]]`

Generate field × source conflict frequency matrix.

        Returns:
            Nested dict: ``{field: {source_pair: count}}``.
        

**Returns:** `Dict[str, Dict[str, int]]`



### `ConflictTopology.temporal_pattern(self) → List[Dict[str, Any]]`

Analyze conflict patterns over time.

        Returns:
            List of time-bucketed conflict counts, sorted by timestamp.
        

**Returns:** `List[Dict[str, Any]]`



### `ConflictTopology.clusters(self) → List[ConflictCluster]`

Identify clusters of related conflicts.

        Clusters are grouped by (field, source_pair) combinations.

        Returns:
            List of :class:`ConflictCluster` groups.
        

**Returns:** `List[ConflictCluster]`



### `ConflictTopology.field_frequency(self) → Dict[str, int]`

Count conflicts per field.

        Returns:
            Dict mapping field names to conflict counts.
        

**Returns:** `Dict[str, int]`



### `ConflictTopology.source_frequency(self) → Dict[str, int]`

Count conflicts per source.

        Returns:
            Dict mapping source names to conflict counts.
        

**Returns:** `Dict[str, int]`



### `ConflictTopology.strategy_stats(self) → Dict[str, int]`

Count which strategies resolved conflicts.

        Returns:
            Dict mapping strategy names to usage counts.
        

**Returns:** `Dict[str, int]`



### `ConflictTopology.to_json(self) → str`

Export as D3-compatible JSON.

        The JSON structure contains:
        - ``nodes``: list of field and source nodes
        - ``links``: list of conflict links between nodes
        - ``heatmap``: field × source frequency matrix
        - ``stats``: summary statistics

        Returns:
            JSON string with nodes and links.
        

**Returns:** `str`



### `ConflictTopology.to_csv(self, path: str) → None`

Export conflict records to CSV.

        Args:
            path: Output CSV file path.
        

**Parameters:**
- `path` (`str`)

**Returns:** `None`



### `ConflictTopology.to_csv_string(self) → str`

Export conflict records to a CSV string.

        Returns:
            CSV-formatted string.
        

**Returns:** `str`



### `ConflictTopology.to_dict(self) → Dict[str, Any]`

Export complete topology as dict.

        Returns:
            Dict with heatmap, clusters, summary, stats.
        

**Returns:** `Dict[str, Any]`


## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 3
- Inherited methods: 0
- Circular dependencies: None

### RREA Findings
- Entropy profile: Zero
- Dead code: None
- Shadow dependencies: None
- Chokepoint status: None

### Code Quality (Team 2)
- Docstring coverage: 95.7%
- `__all__` defined: No
- Code smells: None

### Second Pass
- Heightened findings: None (all 1,063 new inherited methods classified as false positive dunders)
