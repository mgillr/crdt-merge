# Conflict Visualization

Conflict topology analysis with heatmaps, temporal patterns, and cluster detection.

## Quick Example

```python
from crdt_merge.viz import ConflictTopology
topo = ConflictTopology()
topo.add_conflicts(conflict_records)
heatmap = topo.heatmap()
```

---

## API Reference

## `crdt_merge.viz`

> Conflict Topology Visualization — interactive conflict analysis with D3-compatible export.

**Module:** `crdt_merge.viz`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `ConflictCluster(fields: 'List[str]', source_pairs: 'List[Tuple[str, str]]', count: 'int', pattern: 'str') -> None`

Group of related conflicts sharing a pattern.

**Methods:**


#### `ConflictRecord(key: 'Any', field: 'str', sources: 'List[str]', values: 'List[Any]', resolved_value: 'Any', strategy: 'str' = 'lww', timestamp: 'Optional[str]' = None) -> None`

A single conflict event.

**Methods:**

- `to_dict(self) -> 'Dict[str, Any]'` — Serialise to a plain dict.

#### `ConflictTopology(conflicts: 'Optional[List[ConflictRecord]]' = None) -> 'None'`

Analyze and visualize merge conflict patterns.

**Methods:**

- `add_conflict(self, conflict: 'ConflictRecord') -> 'None'` — Add a conflict record.
- `clusters(self) -> 'List[ConflictCluster]'` — Identify clusters of related conflicts.
- `field_frequency(self) -> 'Dict[str, int]'` — Count conflicts per field.
- `from_merge(result: 'Any', provenance: 'Optional[Any]' = None) -> 'ConflictTopology'` — Create from a merge result and optional provenance log.
- `from_records(conflicts: 'List[Dict[str, Any]]') -> 'ConflictTopology'` — Create from raw conflict dicts.
- `heatmap(self) -> 'Dict[str, Dict[str, int]]'` — Generate field × source conflict frequency matrix.
- `source_frequency(self) -> 'Dict[str, int]'` — Count conflicts per source.
- `strategy_stats(self) -> 'Dict[str, int]'` — Count which strategies resolved conflicts.
- `summary(self) -> 'str'` — Generate human-readable conflict summary.
- `temporal_pattern(self) -> 'List[Dict[str, Any]]'` — Analyze conflict patterns over time.
- `to_csv(self, path: 'str') -> 'None'` — Export conflict records to CSV.
- `to_csv_string(self) -> 'str'` — Export conflict records to a CSV string.
- `to_dict(self) -> 'Dict[str, Any]'` — Export complete topology as dict.
- `to_json(self) -> 'str'` — Export as D3-compatible JSON.

#### `Counter(iterable=None, /, **kwds)`

Dict subclass for counting hashable items.  Sometimes called a bag

**Methods:**

- `copy(self)` — Return a shallow copy.
- `elements(self)` — Iterator over elements repeating each as many times as its count.
- `fromkeys(iterable, v=None)` — 
- `most_common(self, n=None)` — List the n most common elements and their counts from the most
- `subtract(self, iterable=None, /, **kwds)` — Like dict.update() but subtracts counts instead of replacing them.
- `total(self)` — Sum of the counts
- `update(self, iterable=None, /, **kwds)` — Like dict.update() but add counts instead of replacing them.

#### `defaultdict(...)`

defaultdict(default_factory=None, /, [...]) --> dict with default factory

### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
