# Federated Model Merging Without a Parameter Server

> **Patent Pending — UK Application No. 2607132.4**
> Architecture described herein is protected under BSL-1.1 until 2028-03-29, then Apache 2.0.

---

## The Parameter Server Problem

Every federated learning system in production today relies on a **parameter server** — a central node that:
1. Receives gradient updates or model weights from all clients
2. Aggregates them (FedAvg, FedProx, or similar)
3. Pushes the updated global model back to all clients

This architecture has four fundamental problems:

**Single point of failure.** If the parameter server goes down mid-round, the entire federation stalls. All partial updates from clients are lost.

**Convergence is not guaranteed.** FedAvg and its variants are heuristics. The mathematical properties of aggregation — whether you get the same global model regardless of which clients participated in which round, in what order — are not formally proven. The community treats convergence as empirical.

**Participation synchronisation.** All clients must synchronise within a round. Slow clients (stragglers) hold back fast ones. Asynchronous variants exist but introduce additional complexity and further weaken convergence guarantees.

**The merge problem.** After training, research teams merge fine-tuned models using SLERP, TIES, DARE, and other strategies. None of these strategies satisfy CRDT laws on raw tensors — meaning merge results differ depending on the order models are combined. Two labs merging the same three models in different orders get different results.

---

## The Two-Layer Architecture Applied to Model Merging

crdt-merge solves the merge convergence problem through the same two-layer pattern that powers convergent agent state:

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: CRDTMergeState (OR-Set over contributions)     │
│                                                          │
│  • Each model contribution has a unique tag (UUID)       │
│  • add(model_id, tensors, weight) → tag                  │
│  • remove(model_id) → tombstone all current tags         │
│  • merge(other) = set union on adds + removes            │
│                                                          │
│  merge() is commutative  associative  idempotent  │
│  Merkle root for content-addressable integrity           │
│  Version vector for causal ordering                      │
└──────────────────────┬──────────────────────────────────┘
                       │ visible set (sorted by canonical_key)
                       ┌─────────────────────────────────────────────────────────┐
│  Layer 2: Strategy (pure deterministic function)         │
│                                                          │
│  • Applied over the FULL visible set — never pairwise    │
│  • Canonical ordering: sorted by content_hash            │
│  • Seeded randomness: seed = Merkle_root[:8]             │
│  • 26 strategies: slerp, ties, dare, fisher, ...         │
│                                                          │
│  Same visible set → same merged model on every replica   │
└─────────────────────────────────────────────────────────┘
```

**The key insight:** SLERP, TIES, DARE, and FisherMerge are non-associative and non-commutative on raw tensors. It is mathematically impossible to make them CRDTs directly. The two-layer architecture sidesteps this entirely: the OR-Set handles convergence, and the strategy is called once over the full converged set. Pairwise application is never used.

---

## Quick Start: CRDT-Compliant Model Merge

```python
import numpy as np
from crdt_merge.model import CRDTMergeState

# Three research teams fine-tuning the same base model
# weight_average requires no base model; use ties/dare_ties for task-vector strategies
team_a = CRDTMergeState("weight_average")
team_b = CRDTMergeState("weight_average")
team_c = CRDTMergeState("weight_average")

# Each team adds their fine-tuned weights
team_a.add(math_tensors, model_id="llama-math-v2", weight=0.4)
team_b.add(code_tensors, model_id="llama-code-v3", weight=0.35)
team_c.add(reasoning_tensors, model_id="llama-reason-v1", weight=0.25)

# Team B discovers a bug — remove and replace without coordinator
team_b.remove("llama-code-v3")
team_b.add(fixed_code_tensors, model_id="llama-code-v4", weight=0.35)

# Sync in any order — CRDT guarantees identical result
team_a.merge(team_b)
team_a.merge(team_c)
team_b.merge(team_a)
team_c.merge(team_a)

# All teams have identical state
assert team_a.state_hash == team_b.state_hash == team_c.state_hash

# Resolve — same visible set, same merged model on every node
merged_a = team_a.resolve()
merged_b = team_b.resolve()
merged_c = team_c.resolve()

# Guaranteed bit-identical
for key in merged_a:
    assert np.array_equal(merged_a[key], merged_b[key])
    assert np.array_equal(merged_a[key], merged_c[key])
```

---

## Scenario: Cross-Organisation Model Collaboration — Without Data Sharing

Three pharmaceutical companies independently fine-tune a protein-folding model on their proprietary datasets. They want to combine their improvements without sharing the underlying training data or model weights directly.

**Today:** No formal mechanism. Typically one company's model is taken as the base and the others are merged in a fixed order determined by negotiation — order dependency means the last-merged company has disproportionate influence.

**With crdt-merge:**

```python
from crdt_merge.model import CRDTMergeState
from crdt_merge.wire import serialize, deserialize

# All companies share the same pre-trained base model (publicly available checkpoint)
# dare_ties and ties strategies require a base= to compute task vectors
base_protein_model = load_base_model()  # shared pre-trained weights dict

# Each company runs locally, never shares training data
pharma_a = CRDTMergeState("dare_ties", base=base_protein_model)
pharma_a.add(pharma_a_weights, model_id="pf-model-v4", weight=0.4,
             metadata={"training_samples": 50000, "domain": "oncology"})

pharma_b = CRDTMergeState("dare_ties", base=base_protein_model)
pharma_b.add(pharma_b_weights, model_id="pf-model-v7", weight=0.35,
             metadata={"training_samples": 38000, "domain": "cardiology"})

pharma_c = CRDTMergeState("dare_ties", base=base_protein_model)
pharma_c.add(pharma_c_weights, model_id="pf-model-v2", weight=0.25,
             metadata={"training_samples": 29000, "domain": "neurology"})

# Each company serialises their CRDT state (not raw training data)
# and shares it with the others via the wire protocol
wire_a = serialize(pharma_a)
wire_b = serialize(pharma_b)
wire_c = serialize(pharma_c)

# Any company can produce the final merged model
pharma_a.merge(deserialize(wire_b))
pharma_a.merge(deserialize(wire_c))
merged = pharma_a.resolve()

# Identical result regardless of which company does the final merge
# OR what order the merges happen
# remove() lets any company retract a contribution at any time
```

The contribution weights, metadata, and provenance are all preserved. The `state_hash` (Merkle root over all contributions) allows any party to independently verify they have the same state as any other party, without inspecting the raw weights.

---

## Scenario: Federated Learning Without a Parameter Server

```python
from crdt_merge.model import CRDTMergeState
from crdt_merge.flower_plugin import CRDTStrategy, FlowerCRDTClient

# Server: CRDT-backed aggregation — no "round" synchronisation required
strategy = CRDTStrategy(
    merge_strategy="dare_ties",
    min_clients=3,  # minimum before resolve()
    density=0.5
)

# Client: wraps any PyTorch model
client = FlowerCRDTClient(
    model=my_pytorch_model,
    strategy="ties"
)

# Clients add their trained weights to the shared CRDTMergeState
# The server never needs to wait for all clients — any subset that
# has contributed can call resolve() and get a valid merged model
# Late-arriving clients are included in the next round automatically
```

**What this changes:** In standard FedAvg, if a client's update arrives after the round closes it is discarded. With `CRDTMergeState`, late-arriving contributions are simply merged into the existing state. The parameter server becomes optional — any client can act as the aggregator. If the server crashes, any client with the current `CRDTMergeState` can continue.

The `remove()` operation allows a client to retract a contribution — for privacy (right-to-be-forgotten), model quality (a client discovered their local data was corrupted), or operational reasons. The removal propagates to all nodes through gossip.

---

## Scenario: Continual Learning Across Deployments

```python
from crdt_merge.model.continual import ContinualMerge

# A model deployed across 50 regional servers
# Each server sees different data distribution
# Periodic re-training produces local model updates
continual = ContinualMerge(
    base_model=base_model,
    strategy="ties",
)

# Regional server updates are merged as they arrive
# No coordination required between regional servers
for server_id, local_update in regional_updates.items():
    continual.absorb(
        local_update,
        name=f"update-{server_id}-{epoch}",
        weight=compute_weight(server_id),
    )

# Export at any time — always produces best current merged model
current_global = continual.export()
```

---

## The 25 Strategies — All CRDT-Compliant

All 26 strategies satisfy CRDT laws when used through `CRDTMergeState`. The non-CRDT behaviour of the raw strategy is irrelevant — convergence is guaranteed by the OR-Set layer.

| Strategy | Domain | Key Property |
|---|---|---|
| `weight_average` | General | Uniform averaging |
| `slerp` | Fine-tuned models | Spherical interpolation in weight space |
| `ties` | Multi-task | Trim, elect sign, disjoint merge |
| `dare` | Sparse | Drop and rescale |
| `dare_ties` | Multi-task sparse | Combined DARE + TIES |
| `task_arithmetic` | Task vectors | Linear task vector combination |
| `fisher` | Fisher-weighted | Information-weighted averaging |
| `regmean` | RegMean | Regression mean aggregation |
| `ada_merging` | AdaMerging | Adaptive coefficient merging |
| `LoRAMerge` | LoRA | LoRA delta merging (use `crdt_merge.model.lora`) |
| `evolutionary_merge` | Search-based | Evolutionary parameter search |
| `genetic_merge` | Search-based | Genetic algorithm merge |
| `neg_merge` | Unlearning | Negative contribution merge |
| `safe_merge` | Safety | Safety-constrained merge |
| ... and 11 more | | |

**CRDT overhead:** < 0.5ms per merge operation regardless of model size. The OR-Set operates on contribution metadata (hashes, tags, version vectors) — not on tensor data.

---

## Verifying CRDT Compliance

```python
from crdt_merge.verify import verify_crdt
from crdt_merge.model import CRDTMergeState
import numpy as np

def gen_state():
    state = CRDTMergeState("ties")
    state.add(np.random.randn(10, 10).astype(np.float32), model_id="model")
    return state

result = verify_crdt(
    merge_fn=lambda a, b: a.merge(b),
    gen_fn=gen_state,
    trials=1000
)
assert result.passed  # Commutativity, associativity, idempotency — all verified
print(f"CRDT compliance: {result.commutativity.passed}/{result.total_trials} commutative")
```

---

## Why This Matters Beyond Research

The practical consequence of order-dependent merge algorithms is that the same set of models, merged in different orders, produces different results. This means:

- Two teams running the same experiment get different models
- A/B testing of merge strategies is confounded by order effects
- Merging models from different organisations produces results that depend on which organisation "goes last"
- Federated learning rounds produce results that depend on which clients happened to be synchronised

crdt-merge eliminates all of these. The merged model is a pure function of the contributing models — not of the order in which they were processed, the network topology, or which node happened to act as aggregator.

---

## Further Reading

- [CRDT Architecture — Full Mathematical Proof](../CRDT_ARCHITECTURE.md)
- [Architecture Map](../ARCHITECTURE_MAP.md)
- [Guide — Convergent Multi-Agent AI](./convergent-multi-agent-ai.md)
- [Guide — The Right to Forget in Trained AI Models](./right-to-forget-in-ai.md)
- [API Reference — CRDTMergeState](../api-reference/layer4-ai/model.md)
- [Benchmarks — A100 GPU Performance](../benchmarks/v030_a100_analysis.md)
