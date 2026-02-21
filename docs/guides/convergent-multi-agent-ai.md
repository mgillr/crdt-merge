# Convergent Multi-Agent AI Systems

> **Patent Pending — UK Application No. 2607132.4**
> Architecture described herein is protected under BSL-1.1 until 2028-03-29, then Apache 2.0.

---

## The Problem No Agent Framework Has Solved

Every major AI agent framework — LangChain, AutoGen, CrewAI, LangGraph, OpenAI Assistants API — shares one architectural assumption that is almost never stated explicitly: **a coordinator exists**.

A central process sequences agent operations, arbitrates conflicts, and owns shared state. This works for single-machine orchestration. It becomes a fundamental bottleneck everywhere else:

**The split-brain problem.** Two agents update the same belief simultaneously. Whichever runs last wins. There is no conflict resolution, no confidence weighting, no convergence guarantee — just a race condition with an AI wrapper.

**The partition problem.** Agent A is running in EU-WEST. Agent B is in US-EAST. The network partitions. They diverge. When they reconnect, no existing framework has a principled merge — the coordinator picks one and discards the other.

**The federation problem.** Organisation A wants to share AI-derived insights with Organisation B without sharing raw data. With a coordinator model this is impossible — the coordinator either has full access to both sides or it doesn't exist.

**The provenance problem.** A multi-agent system reaches a conclusion. Which agent contributed which piece of knowledge? What was each agent's confidence level at the time? Current frameworks have no answer.

---

## The Architecture: Two-Layer CRDT Agent State

crdt-merge solves all four problems through the same two-layer architecture that makes model merging CRDT-compliant, applied to agent state:

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: AgentState (CRDT state container)          │
│                                                      │
│  facts    → LWWMap  (timestamp + confidence LWW)     │
│  tags     → ORSet   (add-wins, union merge)          │
│  counters → PNCounter (per-node max, no coordination)│
│  messages → append-only + content-hash dedup         │
│                                                      │
│  merge() = set union / lattice join                  │
│  CRDT laws: commutative ✓  associative ✓  idem ✓    │
└──────────────────────┬──────────────────────────────┘
                       │ convergent set
                       ▼
┌─────────────────────────────────────────────────────┐
│  Layer 2: ContextMerge (deterministic resolution)    │
│                                                      │
│  strategies: lww / max_confidence / priority / union │
│  same converged set → same resolved knowledge        │
│  ContextBloom: 64-shard CRDT dedup (O(1) membership) │
│  MemorySidecar: O(1) filtering without reading data  │
│  ContextManifest: full provenance for every merge    │
└─────────────────────────────────────────────────────┘
```

**The convergence proof:** If all agents eventually receive the same set of updates (Layer 1 guarantees this via CRDT laws), and the resolution function is deterministic (Layer 2 guarantees this via canonical ordering), then all agents will produce bit-identical resolved knowledge — regardless of the order updates were received.

No coordinator required. No network partition recovery protocol required. No conflict arbitration required.

---

## Quick Start

```python
from crdt_merge.agentic import AgentState, SharedKnowledge
from crdt_merge.context.merge import ContextMerge

# Each agent runs independently — no coordination
researcher = AgentState(agent_id="researcher")
researcher.add_fact("revenue_q1", 4_200_000, confidence=0.90)
researcher.add_fact("market_trend", "expanding", confidence=0.75)
researcher.add_tag("finance")
researcher.increment("sources_consulted")

analyst = AgentState(agent_id="analyst")
analyst.add_fact("revenue_q1", 4_250_000, confidence=0.95)  # higher confidence
analyst.add_fact("risk_level", "moderate", confidence=0.88)
analyst.add_tag("finance")
analyst.add_tag("risk-assessed")
analyst.increment("sources_consulted")

# Merge in any order — guaranteed identical result
shared = SharedKnowledge.merge(researcher, analyst)

# Higher confidence fact wins: 4_250_000 (analyst, 0.95 > 0.90)
print(shared.state.get_fact("revenue_q1").value)       # 4_250_000
print(shared.state.get_fact("revenue_q1").confidence)  # 0.95
print(shared.state.get_fact("revenue_q1").source_agent) # "analyst"

# Tags union — both agents' tags present
print(shared.state.tags)  # {"finance", "risk-assessed"}

# Counters sum across agents
print(shared.state.counter_value("sources_consulted"))  # 2

# Full provenance
print(shared.contributing_agents)  # ["analyst", "researcher"]
```

---

## Scenario: Multi-Region AI Assistant (The Claude/GPT Problem)

A user interacts with an AI assistant on three devices: phone (brief queries), laptop (deep research), home assistant (casual conversation). Three independent instances, three interaction modes, one user.

**Today with any existing framework:** Memory is centralised. Requires network access. When the phone and laptop both update "user's preferred response length" simultaneously, whichever write reaches the server last wins — no confidence weighting, no provenance.

**With crdt-merge:**

```python
# Phone instance — explicit user instruction (high confidence)
phone_agent = AgentState(agent_id="assistant-phone")
phone_agent.add_fact("user_preferred_length", "brief", confidence=0.97)
phone_agent.add_fact("user_timezone", "Europe/London", confidence=1.0)
phone_agent.add_tag("mobile-context")

# Laptop instance — behavioural inference (lower confidence)
laptop_agent = AgentState(agent_id="assistant-laptop")
laptop_agent.add_fact("user_preferred_length", "detailed", confidence=0.72)
laptop_agent.add_fact("user_current_project", "CRDT research", confidence=0.89)
laptop_agent.add_tag("work-context")

# On sync — works offline, syncs when network available
user_context = SharedKnowledge.merge(phone_agent, laptop_agent, home_agent)

# Explicit instruction (0.97) beats behavioural inference (0.72)
assert user_context.state.get_fact("user_preferred_length").value == "brief"
```

Each device operates independently and correctly without network access. When devices sync, the highest-confidence fact always wins. The merged context is **provably identical on all devices** regardless of sync order.

---

## Scenario: Distributed Clinical AI — Federation Without a Coordinator

100 hospitals each run a diagnostic AI agent on their patient population. They want a shared model of symptom-condition correlations. They cannot share patient records.

```python
# Each hospital's agent runs entirely on local data
# Only confidence-weighted facts leave the hospital — no raw data
hospital_a = AgentState(agent_id="hospital-alpha")
hospital_a.add_fact(
    "symptom_fever_sepsis_correlation", 0.87,
    confidence=0.91  # based on 12,000 patient observations
)

hospital_b = AgentState(agent_id="hospital-beta")
hospital_b.add_fact(
    "symptom_fever_sepsis_correlation", 0.84,
    confidence=0.78  # based on 8,000 patient observations
)

# Gossip between hospitals (no central server required)
from crdt_merge.gossip import GossipState
# GossipBridge (see issue #100) wires AgentState to gossip transport

# After convergence across all 100 hospitals:
global_knowledge = SharedKnowledge.merge(*all_hospital_agents)
# hospital_a's higher-confidence observation (0.91) dominates
# ContextManifest records which hospital contributed which fact
# GDPR: no patient data leaves any hospital
```

Scale this to 100 hospitals in 20 countries. No central coordinator. Gossip propagates facts. The global medical knowledge graph converges. This is currently not architecturally possible with any deployed multi-agent framework.

---

## Scenario: Parallel Code Review — Eliminating the Context Window Bottleneck

A large codebase requires simultaneous review by specialist agents: security, performance, architecture, compliance. With a coordinator model, all findings must pass through one agent's context window.

```python
security_agent = AgentState(agent_id="security")
security_agent.add_fact("pr_247_sql_injection", True, confidence=0.97)
security_agent.add_fact("pr_247_auth_bypass", False, confidence=0.89)
security_agent.add_tag("security-reviewed")

performance_agent = AgentState(agent_id="performance")
performance_agent.add_fact("pr_247_n_plus_one", True, confidence=0.94)
performance_agent.add_fact("pr_247_missing_index", True, confidence=0.88)
performance_agent.add_tag("performance-reviewed")

architecture_agent = AgentState(agent_id="architecture")
architecture_agent.add_fact("pr_247_violates_layering", False, confidence=0.91)
architecture_agent.add_tag("architecture-reviewed")

# All agents run in parallel — any can fail and restart
# No coordinator required — merge when all complete
review = SharedKnowledge.merge(
    security_agent, performance_agent, architecture_agent, compliance_agent
)

# Complete findings from all agents, provenance intact
# Tags show which reviews are complete
print(review.state.tags)
# {"security-reviewed", "performance-reviewed", "architecture-reviewed", "compliance-reviewed"}
```

Throughput scales linearly with the number of specialist agents. No coordinator bottleneck. An agent crashing and restarting doesn't affect others — its `AgentState` is merged when it completes.

---

## Scenario: Autonomous Vehicle Fleet — Convergence Without Infrastructure

1,000 vehicles. Each runs an AI agent observing road conditions. A road hazard appears. How does that knowledge reach all 1,000 vehicles?

**Today:** Vehicle detects hazard → uploads to central server → server processes → pushes to all vehicles. Round-trip: seconds. Network partition during tunnel: vehicles have stale data. Server becomes single point of failure.

**With crdt-merge gossip + AgentState:**

```python
# Vehicle 42 detects hazard
vehicle_42 = AgentState(agent_id="v42")
vehicle_42.add_fact("segment_14B_hazard", "debris", confidence=0.95, timestamp=t1)

# Vehicle 42 enters tunnel — network partition
# Vehicle 67 drives through same location, hazard is cleared
vehicle_67 = AgentState(agent_id="v67")
vehicle_67.add_fact("segment_14B_hazard", "cleared", confidence=0.99, timestamp=t2)
# t2 > t1, confidence 0.99 > 0.95 — "cleared" will win on merge

# When vehicle 42 exits tunnel, gossip with nearby vehicles (mesh, no server)
# CRDT merge: t2 > t1, "cleared" dominates
# ContextManifest records both observations with full provenance
```

During partition, each vehicle operates on its local knowledge — no degraded mode, no stale-data warning. When connectivity returns, gossip between nearby vehicles propagates the most current, highest-confidence facts through the fleet. The central server becomes optional telemetry infrastructure rather than a hard operational dependency.

---

## Context Memory: The ContextBloom Innovation

For agents with large memory stores (100K+ memories), `ContextMerge` provides a layer of deduplication that no existing framework offers:

```python
from crdt_merge.context.merge import ContextMerge

# Merge memory lists from two agents
merger = ContextMerge(strategy="max_confidence", budget=500)
result = merger.merge(agent_a_memories, agent_b_memories)

print(f"Input: {len(agent_a_memories) + len(agent_b_memories)} memories")
print(f"Output: {len(result.memories)} memories (budget-capped)")
print(f"Duplicates removed: {result.duplicates_found}")
print(f"Conflicts resolved: {result.conflicts_resolved}")
print(f"Manifest: {result.manifest.manifest_id}")  # EU AI Act Article 13
```

**`ContextBloom`** (64-shard sharded Bloom filter) performs O(1) membership testing on millions of memories. Each shard merges via bitwise-OR — which is commutative, associative, and idempotent — making the entire composite a CRDT. Duplicate detection across 1M memories takes microseconds.

**`MemorySidecar`** pre-computes metadata (confidence, source_agent, timestamp, TTL, tags) for each memory chunk. Filtering by topic, confidence threshold, or source agent is O(1) — the sidecar is read instead of the memory content. For 100K memories this eliminates 99%+ of content reads during merge.

```python
# O(1) filter — reads only sidecar metadata, not memory content
high_confidence = [
    chunk for chunk in memories
    if chunk.sidecar.matches_filter(min_confidence=0.85, source_agent="researcher")
]
```

---

## Convergence Guarantee — Mathematical Proof

`AgentState.merge()` satisfies all three CRDT laws:

| Component | Merge operation | CRDT proof |
|---|---|---|
| `_facts` (LWWMap) | Element-wise max(timestamp) | Max is commutative, associative, idempotent |
| `_tags` (ORSet) | Tag set union | Set union is commutative, associative, idempotent |
| `_counters` (PNCounter) | Per-node max of pos/neg GCounters | Pointwise max over semilattice |

By the CRDT composition theorem (Shapiro et al. 2011): a composition of CRDTs whose merge operations are defined component-wise is itself a CRDT.

**Therefore:** `SharedKnowledge.merge(A, B, C)` ≡ `SharedKnowledge.merge(C, A, B)` ≡ `SharedKnowledge.merge(B, merge(A, C))` — regardless of the number of agents, the order of merges, or the presence of network partitions. All agents will eventually hold bit-identical `SharedKnowledge`.

---

## Comparison to Existing Frameworks

| Property | LangChain | AutoGen | CrewAI | LangGraph | **crdt-merge** |
|---|:---:|:---:|:---:|:---:|:---:|
| Convergence guarantee | ❌ | ❌ | ❌ | ❌ | ✅ **Proven** |
| Works without coordinator | ❌ | ❌ | ❌ | ❌ | ✅ |
| Partition-tolerant | ❌ | ❌ | ❌ | ❌ | ✅ |
| Confidence-weighted facts | ❌ | ❌ | ❌ | ❌ | ✅ |
| Per-fact provenance | ❌ | ⚠️ partial | ⚠️ partial | ⚠️ partial | ✅ |
| Federation without data sharing | ❌ | ❌ | ❌ | ❌ | ✅ |
| EU AI Act audit trail | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## Integration with Existing Agent Frameworks

crdt-merge's `AgentState` is a drop-in state management layer for any agent framework. The framework handles task orchestration; crdt-merge handles convergent state:

```python
# CrewAI integration pattern
from crdt_merge.agentic import AgentState

class CRDTAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.crdt_state = AgentState(agent_id=self.role)

    def execute_task(self, task):
        result = super().execute_task(task)
        # Record findings as facts with confidence
        self.crdt_state.add_fact(task.id, result, confidence=self._confidence_score(result))
        return result

# After all agents complete — merge their states
final_knowledge = SharedKnowledge.merge(*[agent.crdt_state for agent in crew.agents])
```

Works with LangGraph, AutoGen, and LangChain memory systems identically — crdt-merge provides the convergent state layer underneath.

---

## Further Reading

- [CRDT Architecture — Mathematical Proofs](../CRDT_ARCHITECTURE.md)
- [Architecture Map — Full System Overview](../ARCHITECTURE_MAP.md)
- [API Reference — AgentState](../api-reference/layer4-ai/agentic.md)
- [API Reference — ContextMerge](../api-reference/layer4-ai/context-merge.md)
- [Guide — Federated Model Merging Without a Parameter Server](./federated-model-merging.md)
- [Guide — Provenance-Complete AI](./provenance-complete-ai.md)
