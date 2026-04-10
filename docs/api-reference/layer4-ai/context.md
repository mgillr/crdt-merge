# crdt_merge.context — Agent Context Management

**Package**: `crdt_merge/context/`
**Layer**: 4 — AI / Model / Agent
**LOC**: 1,535
**Modules**: 5

---

## ContextMerge (`context/merge.py`)

Semantic context merging for AI agents.

```python
class ContextMerge:
    def __init__(self, strategy: str = "semantic") -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `merge()` | `merge(ctx_a: dict, ctx_b: dict) -> dict` | Merge two context objects |
| `summarize()` | `summarize(contexts: List[dict], max_tokens: int = 4096) -> dict` | Summarize multiple contexts |

## MemorySidecar (`context/sidecar.py`)

External memory attachment for agents.

```python
class MemorySidecar:
    def __init__(self, capacity: int = 10000) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `store()` | `store(key: str, value: Any, metadata: Optional[dict] = None) -> None` | Store memory |
| `recall()` | `recall(query: str, top_k: int = 5) -> List[dict]` | Recall relevant memories |
| `merge()` | `merge(other: MemorySidecar) -> MemorySidecar` | Merge two sidecars |

## ContextConsolidator (`context/consolidator.py`)

```python
class ContextConsolidator:
    def consolidate(self, contexts: List[dict]) -> dict
```

## ContextBloom (`context/bloom.py`)

Bloom filter for fast context deduplication.

```python
class ContextBloom:
    def __init__(self, capacity: int = 100000) -> None
    def add(self, context_hash: str) -> None
    def contains(self, context_hash: str) -> bool
    def merge(self, other: ContextBloom) -> ContextBloom
```

## ContextManifest (`context/manifest.py`)

```python
class ContextManifest:
    def __init__(self) -> None
    def register(self, context_id: str, metadata: dict) -> None
    def lookup(self, context_id: str) -> Optional[dict]
```


## Analysis Notes
