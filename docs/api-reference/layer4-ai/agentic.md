# crdt_merge.agentic — Agent State Management

**Module**: `crdt_merge/agentic.py`
**Layer**: 4 — AI / Model / Agent
**LOC**: 402
**Dependencies**: `crdt_merge.core`, `crdt_merge.clocks`

---

## Overview

CRDT-backed state management for agentic AI systems. Enables multiple AI agents to share and merge state without coordination.

---

## Classes

### AgentState

Per-agent CRDT state container.

```python
class AgentState:
    def __init__(self, agent_id: str) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `set()` | `set(key: str, value: Any) -> None` | Set state value (LWW semantics) |
| `get()` | `get(key: str, default: Any = None) -> Any` | Get state value |
| `increment()` | `increment(key: str, amount: int = 1) -> None` | Increment counter (GCounter semantics) |
| `add_to_set()` | `add_to_set(key: str, item: Any) -> None` | Add to set (ORSet semantics) |
| `merge()` | `merge(other: AgentState) -> AgentState` | Merge with another agent's state. CRDT compliant. |
| `snapshot()` | `snapshot() -> dict` | Get full state snapshot |
| `to_dict()` | `to_dict() -> dict` | Serialize |
| `from_dict()` | `@classmethod from_dict(cls, d: dict) -> AgentState` | Deserialize |

### SharedKnowledge

Shared knowledge base across multiple agents.

```python
class SharedKnowledge:
    def __init__(self, namespace: str = "default") -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `contribute()` | `contribute(agent_id: str, key: str, value: Any) -> None` | Agent contributes knowledge |
| `query()` | `query(key: str) -> Any` | Query merged knowledge |
| `merge_all()` | `merge_all() -> dict` | Merge all agent contributions |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class Fact`

A single fact with confidence and provenance.

    Attributes:
        value:        The fact's payload (any JSON-serialisable value).
        confidence:   Float in [0, 1]. Higher → more trustworthy.
        source_agent: ID of the agent that produced this fact.
        timestamp:    Wall-clock time when the fact was recorded.
    

**Attributes:**
- `value`: `Any`
- `confidence`: `float`
- `source_agent`: `str`
- `timestamp`: `float`


### `AgentState.get_fact(self, key: str, default: Any = None) → Optional[Fact]`

Return a :class:`Fact` by *key*, or *default* if absent.

**Parameters:**
- `key` (`str`)
- `default` (`Any`)

**Returns:** `Optional[Fact]`


### `AgentState.list_facts(self) → Dict[str, Fact]`

Return all live facts as ``{key: Fact}``.

**Returns:** `Dict[str, Fact]`


### `AgentState.add_tag(self, tag: str) → None`

Add a string tag (ORSet — add-wins semantics).

**Parameters:**
- `tag` (`str`)

**Returns:** `None`


### `AgentState.remove_tag(self, tag: str) → None`

Remove a tag (ORSet remove — kills current tags).

**Parameters:**
- `tag` (`str`)

**Returns:** `None`


### `AgentState.has_tag(self, tag: str) → bool`

Check if *tag* is present.

**Parameters:**
- `tag` (`str`)

**Returns:** `bool`


### `AgentState.tags(self) → set`

Current set of live tags.

**Returns:** `set`


### `AgentState.decrement(self, counter_name: str, amount: int = 1) → None`

Decrement a named counter (PNCounter).

**Parameters:**
- `counter_name` (`str`)
- `amount` (`int`)

**Returns:** `None`


### `AgentState.counter_value(self, counter_name: str) → int`

Return the current value of a named counter (0 if missing).

**Parameters:**
- `counter_name` (`str`)

**Returns:** `int`


### `AgentState.messages(self) → List[dict]`

Return a copy of the message log.

**Returns:** `List[dict]`


### `SharedKnowledge.facts(self) → Dict[str, Fact]`

All merged facts.

**Returns:** `Dict[str, Fact]`


### `SharedKnowledge.tags(self) → set`

Union of all tags.

**Returns:** `set`


### `SharedKnowledge.messages(self) → List[dict]`

Deduplicated, time-sorted message log.

**Returns:** `List[dict]`


### `SharedKnowledge.get_fact(self, key: str, default: Any = None) → Optional[Fact]`

Look up a single fact by *key*.

**Parameters:**
- `key` (`str`)
- `default` (`Any`)

**Returns:** `Optional[Fact]`


### `SharedKnowledge.counter_value(self, counter_name: str) → int`

Return merged counter value.

**Parameters:**
- `counter_name` (`str`)

**Returns:** `int`


## Analysis Notes
