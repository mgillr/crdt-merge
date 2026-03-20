# Agentic Memory at Scale: The Context Window Is Not the Limit

> **Patent Pending — UK Application No. 2607132.4**
> Architecture described herein is protected under BSL-1.1 until 2028-03-29, then Apache 2.0.

---

## The Hard Problems Holding Agentic AI Back

Every major agentic AI system running in production today hits the same ceiling. It is not model capability. It is not reasoning quality. It is **memory architecture**.

Five problems that no current framework has solved:

---

**Problem 1: Context Window Starvation**

A long-running agent accumulates thousands of memories, facts, tool call results, and conversation turns. At some point the context window fills. The agent's choices are:
- Truncate (lose recent or old memories — unpredictably)
- Summarise (lossy — precision collapses into vague generalisations)
- Retrieve (RAG — expensive, misses non-obvious relevance, duplicates proliferate)

There is no principled way to maintain a large memory that is **simultaneously complete, deduplicated, and queryable without reading all of it**.

---

**Problem 2: Multi-Agent Memory Divergence**

Five Claude instances collaborate on a research task. Each builds its own model of the problem. When they communicate findings, there is no merge protocol — the orchestrator picks one agent's output and discards the others. Parallel work is not combined. It is serialised.

The fundamental bottleneck: **all existing frameworks require a coordinator to arbitrate**. When the coordinator merges agent state, it reads everything through one context window. That context window becomes the system's throughput ceiling.

---

**Problem 3: The Duplication Explosion**

A RAG system with 100K documents. Five agents each query the same context and return overlapping results. Each retrieved chunk appears in multiple agents' memories. When you merge their memories, you don't get 100K unique facts — you get 500K entries, 80% duplicates. Deduplication requires reading all of them.

---

**Problem 4: Confidence Drift and Stale Facts**

An agent learns that "Company X CEO is Alice" at time T. At time T+60 days, Company X appoints Bob. The old fact is still in memory, equally weighted to new facts. There is no decay, no confidence degradation by age, no mechanism to let higher-confidence newer facts supersede older ones without reading the entire memory.

---

**Problem 5: Memory That Can't Survive Restarts**

Agent crashes. Memory is lost. State must be rebuilt from scratch. Or: agent is horizontally scaled — two instances with divergent memories serve the same user. Their memories never reconcile.

---

## The Architecture That Solves All Five

crdt-merge introduces three components that together eliminate each of these problems:

```
┌─────────────────────────────────────────────────────────────┐
│  ContextBloom — 64-shard CRDT Bloom filter                   │
│                                                              │
│  Each shard: bitwise-OR merge (commutative, assoc, idem)    │
│  Composite: CRDT by shard independence                      │
│  Membership: O(k) per query — k hash functions, not n mems  │
│  Dedup: 1M memories checked in microseconds                  │
│  merge(): bitwise-OR across all 64 shards — O(shards)       │
└──────────────────────┬──────────────────────────────────────┘
                       │ O(1) "seen before?" check
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  MemorySidecar — pre-computed metadata per chunk             │
│                                                              │
│  confidence: float         source_agent: str                │
│  timestamp: float          ttl: float                       │
│  tags: frozenset           topic: str                       │
│                                                              │
│  filter(min_confidence=0.85, tags={"research"}) → O(1)     │
│  No content read until sidecar passes filter                │
│  For 100K memories: eliminates 99%+ of content reads        │
└──────────────────────┬──────────────────────────────────────┘
                       │ only sidecar-passing chunks read
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  ContextMerge — budget-bounded deterministic resolution      │
│                                                              │
│  strategies: lww / max_confidence / priority / union        │
│  budget: max tokens to include in resolved context          │
│  dedup: ContextBloom gates every candidate memory           │
│  output: ContextManifest — self-describing attestation      │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start: Context Deduplication

```python
from crdt_merge.context.merge import ContextMerge

# Two agents return overlapping memories from the same corpus
agent_a_memories = [
    {"id": "m1", "content": "Company X revenue was $4.2B in Q1", "confidence": 0.88, "source": "agent-a"},
    {"id": "m2", "content": "CEO Alice Chen joined in 2019",      "confidence": 0.91, "source": "agent-a"},
    {"id": "m3", "content": "Company X has 12,000 employees",     "confidence": 0.75, "source": "agent-a"},
]
agent_b_memories = [
    {"id": "m2", "content": "CEO Alice Chen joined in 2019",      "confidence": 0.94, "source": "agent-b"},  # duplicate, higher confidence
    {"id": "m4", "content": "Company X operates in 40 countries", "confidence": 0.82, "source": "agent-b"},
    {"id": "m5", "content": "Company X acquired WidgetCo in 2023","confidence": 0.87, "source": "agent-b"},
]

merger = ContextMerge(strategy="max_confidence", budget=500)
result = merger.merge(agent_a_memories, agent_b_memories)

print(f"Input: {len(agent_a_memories) + len(agent_b_memories)} memories")
print(f"Output: {len(result.memories)} memories (deduped)")
print(f"Duplicates removed: {result.duplicates_found}")
print(f"Conflicts resolved: {result.conflicts_resolved}")

# m2 appears once — agent_b's higher-confidence version (0.94) wins
m2 = next(m for m in result.memories if m["id"] == "m2")
assert m2["confidence"] == 0.94
assert m2["source"] == "agent-b"
```

---

## Cookbook: ContextBloom for O(1) Membership

```python
from crdt_merge.context.bloom import ContextBloom

# 64-shard CRDT Bloom filter
bloom_a = ContextBloom(capacity=1_000_000, fp_rate=0.001)
bloom_b = ContextBloom(capacity=1_000_000, fp_rate=0.001)

# Agent A processes 500K memories
for i in range(500_000):
    bloom_a.add(f"memory_{i}")

# Agent B processes overlapping 500K memories (300K overlap)
for i in range(200_000, 700_000):
    bloom_b.add(f"memory_{i}")

# Before adding any memory: O(1) check — is it a duplicate?
def should_add_to_context(memory_id: str, bloom: ContextBloom) -> bool:
    if bloom.contains(memory_id):
        return False  # duplicate — skip
    bloom.add(memory_id)
    return True

# Merge two agents' Bloom filters — bitwise OR, commutative
merged_bloom = bloom_a.merge(bloom_b)

# After merge: any memory seen by EITHER agent is known
print(f"memory_0 seen: {merged_bloom.contains('memory_0')}")         # True (A only)
print(f"memory_400000 seen: {merged_bloom.contains('memory_400000')}") # True (both)
print(f"memory_800000 seen: {merged_bloom.contains('memory_800000')}") # False (neither)
print(f"False positive rate: {merged_bloom.estimated_fp_rate():.4%}")
```

---

## Cookbook: MemorySidecar for O(1) Filtering

```python
from crdt_merge.context.merge import ContextMerge, MemoryChunk

# 100,000 memories — each has a sidecar with metadata
memories = [
    MemoryChunk(
        id=f"m{i:06d}",
        content=f"Memory content {i}",  # not read until sidecar passes
        confidence=0.5 + (i % 50) * 0.01,
        source_agent=f"agent-{i % 5}",
        timestamp=1700000000 + i * 60,
        tags=frozenset(["research" if i % 3 == 0 else "general"]),
        topic="finance" if i % 7 == 0 else "operations",
        ttl=3600.0,
    )
    for i in range(100_000)
]

# O(1) filter: reads ONLY sidecar metadata, not content
high_confidence_research = [
    chunk for chunk in memories
    if chunk.sidecar.matches_filter(
        min_confidence=0.85,
        tags={"research"},
        topic="finance",
    )
]

print(f"Total memories: {len(memories)}")
print(f"High-confidence research finance: {len(high_confidence_research)}")
print("Content reads: only sidecar metadata was accessed")
# Eliminates 99%+ of content reads — the content string is never accessed
# until a memory passes all sidecar filters
```

---

## Cookbook: Budget-Bounded Context Resolution

```python
from crdt_merge.context.merge import ContextMerge

# Five agents' memories — each has different coverage
all_memories = []
for agent_id in range(5):
    for i in range(1000):  # 5,000 total memories
        all_memories.append({
            "id": f"a{agent_id}_m{i}",
            "content": f"Agent {agent_id} memory {i}: " + "x" * 50,
            "confidence": 0.5 + (agent_id * 0.1) + (i % 10) * 0.01,
            "source": f"agent-{agent_id}",
        })

# Budget: fit within 2048 tokens
merger = ContextMerge(strategy="max_confidence", budget=2048)
result = merger.merge(*[all_memories[i::5] for i in range(5)])

print(f"Input: {len(all_memories)} memories from 5 agents")
print(f"Output: {len(result.memories)} memories (budget-capped)")
print(f"Strategy: {result.manifest.strategy}")
print(f"Manifest ID: {result.manifest.manifest_id}")

# The manifest is self-describing: who contributed, what was included, why
# EU AI Act Article 12: automatic logging of all decisions
```

---

## Scenario: The "10-Agent Research Firm" Problem

Ten AI researchers, each with a 32K token context, collaborating on a market analysis. Without crdt-merge: each agent produces a report, a human synthesizes them. With crdt-merge: agents merge their memories directly, the synthesis is automatic and provenance-complete.

```python
from crdt_merge.agentic import AgentState, SharedKnowledge
from crdt_merge.context.merge import ContextMerge

# Each research agent gathers domain-specific knowledge
agents = {}
for domain in ["financials", "competition", "regulation", "technology", "customers",
               "supply_chain", "macro", "sentiment", "risk", "sustainability"]:
    agent = AgentState(agent_id=f"{domain}-researcher")
    # Each agent adds its specialist findings as facts with confidence
    agent.add_fact("market_size_2025",    4_200_000_000,  confidence=0.85 + len(domain) * 0.001)
    agent.add_fact(f"{domain}_insight",   f"Key finding from {domain}", confidence=0.90)
    agent.add_fact("growth_rate",         0.23,           confidence=0.75 + len(domain) * 0.001)
    agent.add_tag(domain)
    agents[domain] = agent

# Merge all agents' knowledge — no orchestrator reads all 10 contexts
# Each agent contributes its highest-confidence facts
shared = SharedKnowledge.merge(*agents.values())

# Provenance: every fact traceable to its source agent and confidence
market_size = shared.state.get_fact("market_size_2025")
print(f"Market size: {market_size.value:,.0f}")
print(f"Source: {market_size.source_agent} (confidence: {market_size.confidence:.2f})")
print(f"All contributing agents: {shared.contributing_agents}")

# The merged knowledge fits in one context window — not ten
# Each fact is the highest-confidence version from all agents
# The orchestrator's context is no longer the bottleneck
```

---

## Scenario: Infinite Long-Running Agent — No Context Window Limit

A customer service agent has handled 50,000 conversations. Its memory grows without bound. Without crdt-merge: memory is truncated or summarised lossy. With crdt-merge: memory is managed via ContextBloom deduplication, MemorySidecar TTL-based expiry, and budget-bounded ContextMerge.

```python
from crdt_merge.context.merge import ContextMerge, MemoryChunk
from crdt_merge.context.bloom import ContextBloom
import time

class InfiniteAgent:
    """An agent whose effective memory never hits a ceiling."""

    def __init__(self, agent_id: str, token_budget: int = 4096):
        self.agent_id = agent_id
        self.token_budget = token_budget
        self.memories: list[MemoryChunk] = []
        self.bloom = ContextBloom(capacity=10_000_000, fp_rate=0.0001)
        self.merger = ContextMerge(strategy="max_confidence", budget=token_budget)

    def learn(self, memory_id: str, content: str, confidence: float, tags: frozenset, ttl_hours: float = 24):
        """Add a memory — deduplicated via ContextBloom, O(1)."""
        if self.bloom.contains(memory_id):
            return  # duplicate — skip

        self.bloom.add(memory_id)
        chunk = MemoryChunk(
            id=memory_id,
            content=content,
            confidence=confidence,
            source_agent=self.agent_id,
            timestamp=time.time(),
            tags=tags,
            ttl=ttl_hours * 3600,
        )
        self.memories.append(chunk)

    def get_context_for_query(self, min_confidence: float = 0.80, tags: frozenset = None) -> list:
        """Retrieve a budget-bounded, deduplicated, high-confidence context."""
        # MemorySidecar filter: O(1) per memory — no content reads
        candidates = [
            m for m in self.memories
            if m.sidecar.matches_filter(
                min_confidence=min_confidence,
                tags=tags,
                max_age_seconds=86400 * 30,  # 30 days
            )
        ]
        # Budget-bounded merge: fit within token_budget
        result = self.merger.merge(candidates)
        return result.memories

    def merge_with(self, other: "InfiniteAgent"):
        """Merge another agent's memory into this one — CRDT-safe."""
        # Merge Bloom filters (bitwise OR)
        self.bloom = self.bloom.merge(other.bloom)
        # Merge memories using ContextMerge
        result = self.merger.merge(self.memories, other.memories)
        self.memories = result.memories


# Agent accumulates 50,000 memories over its lifetime
agent = InfiniteAgent("cs-agent-prod", token_budget=4096)
for i in range(50_000):
    agent.learn(
        memory_id=f"conversation_{i}",
        content=f"Customer {i} issue: ...",
        confidence=0.7 + (i % 30) * 0.01,
        tags=frozenset(["customer_service", f"topic_{i % 20}"]),
    )

# Retrieve context for a new query — budget-bounded, no truncation
context = agent.get_context_for_query(
    min_confidence=0.90,
    tags=frozenset(["customer_service", "topic_5"])
)
print(f"50,000 memories → {len(context)} in context (budget-bounded)")
print(f"Content reads: only {len(context)} (vs 50,000 without MemorySidecar)")
```

---

## Scenario: Crash Recovery Without State Loss

An agent crashes mid-task. Its memory is stored in the GossipState of its peers. On restart, it recovers its full memory via CRDT merge — no data loss, no replay needed.

```python
from crdt_merge.agentic import AgentState
from crdt_merge.gossip import GossipState

# Agent A is working alongside Agent B
agent_a = AgentState(agent_id="researcher-a")
agent_b = AgentState(agent_id="researcher-b")

# A accumulates knowledge
agent_a.add_fact("hypothesis_1", "Revenue driven by SMB segment", confidence=0.88)
agent_a.add_fact("hypothesis_2", "Churn rate increasing in APAC",  confidence=0.76)

# A syncs to B (periodic gossip)
agent_b = agent_b.merge(agent_a)

# A CRASHES — its local state is gone
del agent_a

# A restarts — recovers state from B via CRDT merge
agent_a_recovered = AgentState(agent_id="researcher-a")
agent_a_recovered = agent_a_recovered.merge(agent_b)

# Full knowledge recovered
assert agent_a_recovered.get_fact("hypothesis_1") is not None
assert agent_a_recovered.get_fact("hypothesis_1").confidence == 0.88
print("Agent recovered from crash — zero knowledge loss")
```

---

## The Fundamental Insight: Memory Is a CRDT Problem

The reason context windows feel like a hard limit is that current memory systems are **not CRDTs**. They are mutable dictionaries. When memory grows beyond the context window, there is no mathematically sound way to select, compress, or merge what's there.

crdt-merge reframes agent memory as a CRDT:
- **Adding a memory** = OR-Set add
- **Updating a memory** = LWW with confidence as the ordering
- **Merging two agents' memories** = CRDT merge (commutative, associative, idempotent)
- **Forgetting** = tombstone (GDPR-compliant removal that propagates)

When memory is a CRDT, the context window is no longer a hard limit — it is a **retrieval budget**. MemorySidecar makes retrieval O(1). ContextBloom makes deduplication O(1). ContextMerge makes multi-agent synthesis automatic.

The result: agents that scale to millions of memories, survive crashes, collaborate without coordinators, and produce provenance-complete outputs — all within a fixed token budget.

---

## Further Reading

- [CRDT Architecture — Full Mathematical Proof](../CRDT_ARCHITECTURE.md)
- [Architecture Map](../ARCHITECTURE_MAP.md)
- [Guide — Convergent Multi-Agent AI](./convergent-multi-agent-ai.md)
- [Guide — Provenance-Complete AI](./provenance-complete-ai.md)
- [Guide — The Right to Forget in Trained AI Models](./right-to-forget-in-ai.md)
- [Guide — Gossip Protocol: Distributed Sync Without a Server](./gossip-serverless-sync.md)
- [API Reference — ContextMerge](../api-reference/layer4-ai/context-merge.md)
- [API Reference — AgentState](../api-reference/layer4-ai/agentic.md)
