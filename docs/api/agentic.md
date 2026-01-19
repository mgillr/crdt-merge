# Agentic AI State Merge 🆕

CRDT containers for multi-agent orchestration — facts, tags, counters, messages. **New in v0.8.2.**

## Quick Example

```python
from crdt_merge.agentic import AgentState, SharedKnowledge
researcher = AgentState(agent_id="researcher")
researcher.add_fact("revenue_q1", 4_200_000, confidence=0.9)
analyst = AgentState(agent_id="analyst")
shared = SharedKnowledge.merge(researcher, analyst)
```

---

## API Reference

## `crdt_merge.agentic`

> Agentic AI State Merge — CRDT containers for multi-agent orchestration.

**Module:** `crdt_merge.agentic`

### Classes

#### `AgentState(agent_id: 'str' = '') -> 'None'`

CRDT state container for a single AI agent.

**Properties:**

- `messages` — Return a copy of the message log.
- `tags` — Current set of live tags.

**Methods:**

- `add_fact(self, key: 'str', value: 'Any', confidence: 'float' = 1.0, timestamp: 'Optional[float]' = None) -> 'None'` — Add or update a fact.
- `add_tag(self, tag: 'str') -> 'None'` — Add a string tag (ORSet — add-wins semantics).
- `append_message(self, message: 'str', role: 'str' = 'agent', metadata: 'Optional[dict]' = None) -> 'None'` — Append to the message log (append-only, deduped on merge).
- `counter_value(self, counter_name: 'str') -> 'int'` — Return the current value of a named counter (0 if missing).
- `decrement(self, counter_name: 'str', amount: 'int' = 1) -> 'None'` — Decrement a named counter (PNCounter).
- `from_dict(d: 'dict') -> 'AgentState'` — Deserialise from a plain dict.
- `get_fact(self, key: 'str', default: 'Any' = None) -> 'Optional[Fact]'` — Return a :class:`Fact` by *key*, or *default* if absent.
- `has_tag(self, tag: 'str') -> 'bool'` — Check if *tag* is present.
- `increment(self, counter_name: 'str', amount: 'int' = 1) -> 'None'` — Increment a named counter (PNCounter).
- `list_facts(self) -> 'Dict[str, Fact]'` — Return all live facts as ``{key: Fact}``.
- `merge(self, other: 'AgentState') -> 'AgentState'` — Merge two agent states into a **new** :class:`AgentState`.
- `remove_tag(self, tag: 'str') -> 'None'` — Remove a tag (ORSet remove — kills current tags).
- `to_dict(self) -> 'dict'` — Full serialisation to a plain dict.

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

#### `Fact(value: 'Any', confidence: 'float' = 1.0, source_agent: 'str' = '', timestamp: 'float' = <factory>) -> None`

A single fact with confidence and provenance.

**Methods:**

- `from_dict(d: 'dict') -> 'Fact'` — Deserialise from a plain dict.
- `to_dict(self) -> 'dict'` — Serialise to a plain dict.

#### `GCounter(node_id: 'Optional[str]' = None, initial: 'int' = 0)`

Grow-only counter. Each node has its own slot; value = sum of all slots.

**Properties:**

- `value` — 

**Methods:**

- `from_dict(d: 'dict') -> 'GCounter'` — 
- `increment(self, node_id: 'str', amount: 'int' = 1) -> 'None'` — 
- `merge(self, other: 'GCounter') -> 'GCounter'` — 
- `to_dict(self) -> 'dict'` — 

#### `LWWMap()`

Last-Writer-Wins Map — a dictionary where each key is an LWW Register.

**Properties:**

- `value` — 

**Methods:**

- `delete(self, key: 'str', timestamp: 'Optional[float]' = None) -> 'None'` — 
- `from_dict(d: 'dict') -> 'LWWMap'` — 
- `get(self, key: 'str', default: 'Any' = None) -> 'Any'` — 
- `merge(self, other: 'LWWMap') -> 'LWWMap'` — 
- `set(self, key: 'str', value: 'Any', timestamp: 'Optional[float]' = None, node_id: 'str' = '') -> 'None'` — 
- `to_dict(self) -> 'dict'` — 

#### `LWWRegister(value: 'Any' = None, timestamp: 'Optional[float]' = None, node_id: 'str' = '')`

Last-Writer-Wins Register — stores a single value, latest timestamp wins.

**Properties:**

- `timestamp` — 
- `value` — 

**Methods:**

- `from_dict(d: 'dict') -> 'LWWRegister'` — 
- `merge(self, other: 'LWWRegister') -> 'LWWRegister'` — 
- `set(self, value: 'Any', timestamp: 'Optional[float]' = None, node_id: 'str' = '') -> 'None'` — 
- `to_dict(self) -> 'dict'` — 

#### `ORSet()`

Observed-Remove Set — add and remove elements without conflicts.

**Properties:**

- `value` — 

**Methods:**

- `add(self, element: 'Hashable') -> 'str'` — 
- `contains(self, element: 'Hashable') -> 'bool'` — 
- `from_dict(d: 'dict') -> 'ORSet'` — 
- `merge(self, other: 'ORSet') -> 'ORSet'` — 
- `remove(self, element: 'Hashable') -> 'None'` — 
- `to_dict(self) -> 'dict'` — 

#### `PNCounter()`

Positive-Negative counter — supports both increment and decrement.

**Properties:**

- `value` — 

**Methods:**

- `decrement(self, node_id: 'str', amount: 'int' = 1) -> 'None'` — 
- `from_dict(d: 'dict') -> 'PNCounter'` — 
- `increment(self, node_id: 'str', amount: 'int' = 1) -> 'None'` — 
- `merge(self, other: 'PNCounter') -> 'PNCounter'` — 
- `to_dict(self) -> 'dict'` — 

#### `SharedKnowledge(state: 'AgentState', contributing_agents: 'List[str]') -> 'None'`

Merge multiple :class:`AgentState` instances into shared knowledge.

**Properties:**

- `facts` — All merged facts.
- `messages` — Deduplicated, time-sorted message log.
- `tags` — Union of all tags.

**Methods:**

- `counter_value(self, counter_name: 'str') -> 'int'` — Return merged counter value.
- `from_dict(d: 'dict') -> 'SharedKnowledge'` — Deserialise from a plain dict.
- `get_fact(self, key: 'str', default: 'Any' = None) -> 'Optional[Fact]'` — Look up a single fact by *key*.
- `merge(*agents: 'AgentState') -> 'SharedKnowledge'` — Merge *N* agent states into a :class:`SharedKnowledge` instance.
- `to_dict(self) -> 'dict'` — Full serialisation.

### Functions

#### `dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, match_args=True, kw_only=False, slots=False, weakref_slot=False)`

Add dunder methods based on the fields defined in the class.

#### `field(*, default=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, default_factory=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>, init=True, repr=True, hash=None, compare=True, metadata=None, kw_only=<dataclasses._MISSING_TYPE object at 0x7fad7e44eb40>)`

Return an object to identify dataclass fields.



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
