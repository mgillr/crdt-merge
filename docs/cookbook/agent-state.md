# Agentic AI State Management

## Recipe 1: Multi-Agent Shared State

```python
from crdt_merge.agentic import AgentState

# Two AI agents working independently
agent_a = AgentState(agent_id="planner")
agent_b = AgentState(agent_id="researcher")

# Each updates its own state
agent_a.add_fact("goal", "Find best restaurant", confidence=0.9)
agent_a.increment("tasks_completed", 3)
agent_a.add_tag("restaurant-search")

agent_b.add_fact("goal", "Check reviews", confidence=0.95)
agent_b.increment("tasks_completed", 5)
agent_b.add_tag("review-analysis")

# Merge — no conflicts, CRDT semantics
merged = agent_a.merge(agent_b)

# GCounter: tasks_completed sums across agents
print(merged.counter_value("tasks_completed"))  # 8

# ORSet: tags are unioned
print(merged.tags)  # {'restaurant-search', 'review-analysis'}

# LWWMap: last-write-wins for facts with the same key
goal = merged.get_fact("goal")
print(goal.value, goal.confidence)

# List all merged facts
for key, fact in merged.list_facts().items():
    print(f"  {key}: {fact.value} (from {fact.source_agent})")
```

## Recipe 2: Shared Knowledge Base

```python
from crdt_merge.agentic import AgentState, SharedKnowledge

# Create individual agent states
agent_1 = AgentState(agent_id="climate_analyst")
agent_1.add_fact("topic:climate", "Global temps rose 1.1°C since pre-industrial era", confidence=0.9)
agent_1.add_tag("climate")
agent_1.increment("papers_reviewed", 12)

agent_2 = AgentState(agent_id="policy_researcher")
agent_2.add_fact("topic:climate", "Paris Agreement targets 1.5°C limit", confidence=0.85)
agent_2.add_tag("climate")
agent_2.add_tag("policy")
agent_2.increment("papers_reviewed", 8)

# Merge N agent states into shared knowledge via classmethod
shared = SharedKnowledge.merge(agent_1, agent_2)

# Access merged data through convenience properties
print(shared.contributing_agents)          # ['climate_analyst', 'policy_researcher']
print({k: f.value for k, f in shared.facts.items()})  # All merged facts
print(shared.tags)                         # {'climate', 'policy'}
print(shared.counter_value("papers_reviewed"))  # 20

# Look up a specific fact (LWW: highest-timestamp wins)
climate_fact = shared.get_fact("topic:climate")
print(climate_fact.value, climate_fact.confidence)
```

## Recipe 3: Context Merge for Long Conversations

```python
from crdt_merge.context import ContextMerge, MemorySidecar

# Create a context merger with a conflict-resolution strategy
# Valid strategies: "lww", "max_confidence", "priority", "union"
ctx_merge = ContextMerge(strategy="max_confidence", budget=10, min_confidence=0.5)

# Agent memories are plain dicts with at least a "fact" key
agent_a_memories = [
    {"fact": "The capital of France is Paris", "confidence": 0.95, "source": "agent_a", "topic": "geography"},
    {"fact": "Python was created by Guido van Rossum", "confidence": 0.99, "source": "agent_a", "topic": "programming"},
]

agent_b_memories = [
    {"fact": "The capital of France is Paris", "confidence": 0.90, "source": "agent_b", "topic": "geography"},
    {"fact": "The Eiffel Tower is in Paris", "confidence": 0.98, "source": "agent_b", "topic": "geography"},
]

# Merge the two memory sets — duplicates are detected via bloom filter
result = ctx_merge.merge(agent_a_memories, agent_b_memories)

print(len(result.memories))        # 3 unique memories
print(result.duplicates_found)     # 1 duplicate detected
print(result.conflicts_resolved)   # 0 conflicts

for mem in result.memories:
    print(f"  - {mem.fact} (confidence={mem.sidecar.confidence})")

# MemorySidecar is the metadata attached to each memory chunk
# Use the from_fact() factory to create one directly
sidecar = MemorySidecar.from_fact(
    "The sky is blue",
    source_agent="observer",
    topic="science",
    confidence=0.99,
    tags=["nature", "observation"],
)
print(sidecar.fact_id)                              # Content-hash-based ID
print(sidecar.matches_filter(topic="science"))      # True
print(sidecar.is_expired())                         # False
```
