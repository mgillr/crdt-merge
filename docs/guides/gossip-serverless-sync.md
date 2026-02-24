# Gossip Protocol: Distributed Sync Without a Server

> **Patent Pending — UK Application No. 2607132.4**
> Architecture described herein is protected under BSL-1.1 until 2028-03-29, then Apache 2.0.

---

## The Sync Problem Every Distributed System Has

Every distributed system needs to synchronise state across replicas. The standard answer is a **central sync server**: a coordinator that receives writes from all nodes and fans them out to all readers.

This creates a ceiling: the coordinator is the bottleneck. Its throughput becomes the system's throughput. Its availability becomes the system's availability. When it's down, nothing syncs.

The literature offers alternatives — gossip protocols, epidemic broadcast, anti-entropy algorithms — but they are described at the protocol level, not the application level. Building one requires deep distributed systems expertise.

crdt-merge's `GossipState` is a **pure state machine for gossip-based sync**. You provide the transport (HTTP, gRPC, WebSockets, UDP, named pipes, carrier pigeon). crdt-merge provides the merge logic, causality tracking, and anti-entropy algorithm. The central server becomes optional.

---

## The Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  GossipState — pure state machine, no networking             │
│                                                              │
│  KV store: key → GossipEntry {                              │
│    key: str                                                  │
│    value: Any                                               │
│    clock: VectorClock  (causal ordering per key)            │
│    tombstone: bool     (CRDT delete marker)                 │
│  }                                                          │
│                                                              │
│  CRDT merge: element-wise VectorClock max                   │
│  Tombstone semantics: add-wins (re-add resurrects)          │
│                                                              │
│  Anti-entropy:                                               │
│    digest() → compact hash of entire state                  │
│    anti_entropy_push_pull(remote_digest) → (push, pull)     │
│    → push: keys remote doesn't have                         │
│    → pull: keys we don't have                               │
│    Complexity: O(k) where k = divergent keys, not total     │
└──────────────────────────────────────────────────────────────┘
```

The critical property: `GossipState.merge(other)` is **commutative, associative, and idempotent**. It doesn't matter which node syncs with which node first, or how many times a message is delivered. All nodes eventually reach the same state.

---

## Quick Start

```python
from crdt_merge.gossip import GossipState

# Node 1: write some state
node1 = GossipState("node-1")
node1.update("user:42", {"name": "Alice", "status": "active"})
node1.update("user:43", {"name": "Bob",   "status": "inactive"})

# Node 2: write different state (disconnected)
node2 = GossipState("node-2")
node2.update("user:44", {"name": "Carol", "status": "active"})
node2.update("user:42", {"name": "Alice", "status": "away"})  # concurrent update

# Reconnect: full merge (any order → same result)
merged = node1.merge(node2)

# Both keys from both nodes are present
# "user:42" conflict resolved by VectorClock comparison
print(f"State size: {merged.size}")  # 3 users
print(f"user:42 value: {merged.get('user:42')}")
```

---

## Cookbook: Anti-Entropy — Sync Only What Changed

Anti-entropy is the gossip mechanism for efficient reconciliation. Instead of sending all state, each node sends a **digest** (compact hash of its state). The other node compares and sends back only what's needed.

```python
from crdt_merge.gossip import GossipState, anti_entropy

# Two nodes that have diverged
node_eu = GossipState("eu-west")
node_us = GossipState("us-east")

# EU node has some records
for i in range(1000):
    node_eu.update(f"sensor:{i}", {"temp": 20 + i * 0.01, "ts": i})

# US node has overlapping + unique records
for i in range(500, 1500):
    node_us.update(f"sensor:{i}", {"temp": 22 + i * 0.01, "ts": i + 1000})

# --- Anti-entropy handshake ---

# Step 1: EU sends its digest to US (compact — O(1) regardless of state size)
eu_digest = node_eu.digest()
print(f"Digest size: {len(str(eu_digest))} chars")  # small constant

# Step 2: US computes what to push and pull
push_keys, pull_keys = node_us.anti_entropy_push_pull(eu_digest)
print(f"US needs to push {len(push_keys)} keys to EU")
print(f"US needs to pull {len(pull_keys)} keys from EU")

# Step 3: Exchange only the divergent entries
entries_to_push = [node_us.get_entry(k) for k in push_keys if node_us.get_entry(k)]
entries_to_pull_request = pull_keys  # send to EU so EU can respond

# Step 4: Apply received entries
received_from_us = entries_to_push
applied = node_eu.apply_entries(received_from_us)
print(f"EU applied {applied} new entries from US")

# Both nodes now converge to the same state
assert node_eu.merge(node_us).size == node_us.merge(node_eu).size
```

---

## Cookbook: VectorClock Causal Ordering

VectorClocks let nodes distinguish **concurrent updates** from **causally ordered updates** without a central timestamp authority.

```python
from crdt_merge.clocks import VectorClock, Ordering

# Node A increments its clock
clock_a = VectorClock()
clock_a = clock_a.increment("node-a")
clock_a = clock_a.increment("node-a")  # {"node-a": 2}

# Node B starts from A's clock, then advances
clock_b = clock_a.increment("node-b")  # {"node-a": 2, "node-b": 1}

# Compare
print(clock_a.compare(clock_b))   # Ordering.BEFORE — A happened before B
print(clock_b.compare(clock_a))   # Ordering.AFTER  — B happened after A

# Concurrent clocks (neither happened before the other)
clock_c = VectorClock().increment("node-c")  # {"node-c": 1}
print(clock_a.compare(clock_c))   # Ordering.CONCURRENT — no causal relationship

# Merge: element-wise max
merged_clock = clock_a.merge(clock_c)
print(merged_clock.clocks)  # {"node-a": 2, "node-c": 1}
```

---

## Cookbook: DottedVersionVector for Precise Causality

DottedVersionVectors track a single "outstanding mutation" (the dot) for more precise causality than full vector clocks:

```python
from crdt_merge.clocks import DottedVersionVector

# Node creates a new event
dvv = DottedVersionVector()
dvv1 = dvv.advance("node-1")  # base={}, dot=("node-1", 1)

# Node receives the event and advances
dvv2 = dvv1.advance("node-2")  # base={"node-1": 1}, dot=("node-2", 1)

# Causality check
print(dvv2.descends(dvv1))  # True — dvv2 happened after dvv1
print(dvv1.descends(dvv2))  # False

# Merge folds dots into base
merged = dvv1.merge(dvv2)
print(merged.value)  # {"node-1": 1, "node-2": 1}
```

---

## Cookbook: Full Gossip Sync Loop (Bring Your Own Transport)

```python
from crdt_merge.gossip import GossipState
import json

# You implement: send(node_id, message) and receive(message)
# crdt-merge implements: everything else

class MyGossipNode:
    def __init__(self, node_id: str, known_peers: list):
        self.state = GossipState(node_id)
        self.peers = known_peers
        self.node_id = node_id

    def write(self, key: str, value: dict):
        """Write a value to local state."""
        self.state.update(key, value)

    def delete(self, key: str):
        """Tombstone a key — propagates via gossip."""
        self.state.delete(key)

    def gossip_round(self, transport):
        """One round of anti-entropy with a random peer."""
        import random
        peer_id = random.choice(self.peers)

        # Step 1: Send our digest
        our_digest = self.state.digest()
        transport.send(peer_id, {"type": "digest", "from": self.node_id, "digest": our_digest})

    def handle_digest(self, sender_id: str, remote_digest: dict, transport):
        """Handle a digest from a peer — compute and send delta."""
        push_keys, pull_keys = self.state.anti_entropy_push_pull(remote_digest)

        # Push what they're missing
        entries_to_push = [
            self.state.get_entry(k).to_dict()
            for k in push_keys
            if self.state.get_entry(k)
        ]
        transport.send(sender_id, {
            "type": "entries",
            "from": self.node_id,
            "entries": entries_to_push,
            "pull_request": list(pull_keys),
        })

    def handle_entries(self, entries: list, transport, sender_id: str = None):
        """Apply received entries to local state."""
        from crdt_merge.gossip import GossipEntry
        parsed = [GossipEntry.from_dict(e) for e in entries]
        count = self.state.apply_entries(parsed)
        print(f"Applied {count} entries from peer")
        return count

# Usage:
# node = MyGossipNode("node-1", ["node-2", "node-3"])
# node.write("config:feature_flags", {"dark_mode": True, "beta_users": 1000})
# node.gossip_round(my_transport)
```

---

## Scenario: Serverless Configuration Management

A microservices platform runs 500 instances across 3 regions. Configuration changes must propagate to all instances. Today: a central config server (Consul, etcd, ZooKeeper) is a single point of failure.

```python
from crdt_merge.gossip import GossipState
from crdt_merge.wire import serialize, deserialize

# Each instance has a local GossipState
class ConfigNode:
    def __init__(self, instance_id: str):
        self.gossip = GossipState(instance_id)

    def set_config(self, key: str, value: dict):
        self.gossip.update(key, value)

    def get_config(self, key: str) -> dict:
        return self.gossip.get(key)

    def sync_with(self, other_state_bytes: bytes):
        """Merge with a serialized GossipState received from a peer."""
        remote = GossipState.from_dict(deserialize(other_state_bytes))
        self.gossip = self.gossip.merge(remote)

    def get_sync_payload(self) -> bytes:
        return serialize(self.gossip.to_dict())


# Regional gossip: instances gossip within their AZ every 100ms
# Cross-region gossip: designated "bridge" instances gossip between regions

instance_a = ConfigNode("eu-west-1a-001")
instance_b = ConfigNode("eu-west-1a-002")
instance_c = ConfigNode("eu-west-1b-001")  # different AZ

# Operator updates config on instance_a
instance_a.set_config("service:rate_limit", {"rps": 1000, "burst": 1500})

# instance_a gossips with instance_b (same AZ, fast network)
instance_b.sync_with(instance_a.get_sync_payload())

# instance_b gossips with instance_c (cross-AZ)
instance_c.sync_with(instance_b.get_sync_payload())

# All instances converge — no coordinator needed
assert instance_a.get_config("service:rate_limit")["rps"] == 1000
assert instance_b.get_config("service:rate_limit")["rps"] == 1000
assert instance_c.get_config("service:rate_limit")["rps"] == 1000

# If instance_a crashes, instances_b and instance_c already have the config
# No data loss, no recovery ceremony
```

---

## Scenario: Autonomous Vehicle Fleet — Hazard Propagation Without Infrastructure

1,000 vehicles need to share road hazard observations. A tunnel severs their connection to central infrastructure.

```python
from crdt_merge.gossip import GossipState
from crdt_merge.clocks import VectorClock
import time

class VehicleNode:
    def __init__(self, vehicle_id: str):
        self.state = GossipState(vehicle_id)
        self.vehicle_id = vehicle_id

    def report_hazard(self, segment_id: str, hazard_type: str, confidence: float):
        self.state.update(f"hazard:{segment_id}", {
            "type": hazard_type,
            "confidence": confidence,
            "reporter": self.vehicle_id,
            "timestamp": time.time(),
        })

    def clear_hazard(self, segment_id: str):
        """Tombstone the hazard — cleared observation propagates."""
        self.state.delete(f"hazard:{segment_id}")

    def mesh_sync(self, nearby_vehicle: "VehicleNode"):
        """Sync via V2V (vehicle-to-vehicle) mesh — no infrastructure needed."""
        # Each vehicle merge the other's state
        self.state = self.state.merge(nearby_vehicle.state)
        nearby_vehicle.state = nearby_vehicle.state.merge(self.state)

    def get_hazards(self) -> list:
        return [
            (k, v) for k, v in self.state.items()
            if k.startswith("hazard:") and not self.state.is_tombstoned(k)
        ]


# Vehicle 42 enters a road with debris
v42 = VehicleNode("vehicle-42")
v42.report_hazard("seg-14B", "debris", confidence=0.95)

# Vehicle 42 enters tunnel — network partition begins
# Vehicle 67 drives through the same segment 5 minutes later — hazard cleared
v67 = VehicleNode("vehicle-67")
v67.clear_hazard("seg-14B")  # tombstone

# Vehicle 42 exits tunnel — mesh sync with nearby v67
v42.mesh_sync(v67)

# VectorClock comparison: v67's clear (after) beats v42's report (before)
# Hazard is correctly shown as cleared on both vehicles
assert len(v42.get_hazards()) == 0
assert len(v67.get_hazards()) == 0

# The central traffic server is optional telemetry — not a dependency
```

---

## Scenario: Federated Knowledge Base — 100 Research Institutions

100 research institutions each maintain a knowledge base. They want to share discoveries without a central database.

```python
from crdt_merge.gossip import GossipState
from crdt_merge.agentic import AgentState, SharedKnowledge

# Each institution has a GossipState for coordinating knowledge entries
institutions = {
    f"institute_{i}": GossipState(f"institute_{i}")
    for i in range(100)
}

# Each institution writes their discoveries
institutions["institute_0"].update("drug:compound-X-efficacy", {
    "value": 0.87, "confidence": 0.91, "sample_size": 1200,
    "institution": "institute_0"
})
institutions["institute_1"].update("drug:compound-X-efficacy", {
    "value": 0.84, "confidence": 0.85, "sample_size": 800,
    "institution": "institute_1"
})

# Gossip converges — all institutions reach consensus without a central server
# Anti-entropy: each institution gossips with 3 random peers per round

def gossip_round(states: dict, rounds: int = 10):
    """Simulate gossip rounds — each node picks random peers."""
    import random
    node_ids = list(states.keys())
    for _ in range(rounds):
        for node_id, state in states.items():
            peers = random.sample([p for p in node_ids if p != node_id], min(3, len(node_ids)-1))
            for peer_id in peers:
                merged = state.merge(states[peer_id])
                states[node_id] = merged
                states[peer_id] = merged

gossip_round(institutions, rounds=20)

# After convergence: all 100 institutions have the same view
# Higher-confidence entry (institute_0, 0.91) visible to all
print(f"Convergence check: {len(set(str(s.digest()) for s in institutions.values()))} unique states")
# Should be 1 — all identical
```

---

## Scenario: Distributed Agent Memory Sync (No Coordinator)

Multiple AI agent instances running on different servers need to share memory state. No central memory server.

```python
from crdt_merge.gossip import GossipState
from crdt_merge.agentic import AgentState, SharedKnowledge

# Three agent instances on different servers — no shared memory
agent_server_1 = AgentState(agent_id="assistant-server-1")
agent_server_2 = AgentState(agent_id="assistant-server-2")
agent_server_3 = AgentState(agent_id="assistant-server-3")

# Each server learns different facts
agent_server_1.add_fact("user_42_preference", "dark_mode", confidence=0.98)
agent_server_2.add_fact("user_42_location",   "London",    confidence=1.0)
agent_server_3.add_fact("user_42_preference", "brief_responses", confidence=0.93)

# Gossip the AgentState via GossipState as the transport layer
gossip_1 = GossipState("server-1")
gossip_1.update("agent_state", agent_server_1.to_dict())

gossip_2 = GossipState("server-2")
gossip_2.update("agent_state", agent_server_2.to_dict())

gossip_3 = GossipState("server-3")
gossip_3.update("agent_state", agent_server_3.to_dict())

# Gossip converges across servers
merged_gossip = gossip_1.merge(gossip_2).merge(gossip_3)

# All servers arrive at the same merged agent state
final = SharedKnowledge.merge(agent_server_1, agent_server_2, agent_server_3)
print(f"User preference: {final.state.get_fact('user_42_preference').value}")
# "dark_mode" (confidence 0.98 > 0.93) wins deterministically
```

---

## Performance Characteristics

| Operation | Complexity | Notes |
|---|---|---|
| `update(key, value)` | O(1) | VectorClock increment + dict insert |
| `get(key)` | O(1) | Dict lookup |
| `merge(other)` | O(k) | k = keys in other state |
| `digest()` | O(n) first call, O(1) cached | SHA-256 of sorted entries |
| `anti_entropy_push_pull()` | O(k) | k = divergent keys, NOT total keys |
| `apply_entries(entries)` | O(e) | e = entries to apply |
| Gossip convergence | O(log n) rounds | n = number of nodes in network |

Anti-entropy digest comparison is the key efficiency: comparing two states of 1M entries each requires only O(1) digest comparison. If they diverge on 100 keys, only those 100 entries are exchanged.

---

## Wire Protocol Integration

GossipState has a stable wire format for cross-language and cross-system interop:

```python
from crdt_merge.gossip import GossipState
from crdt_merge.wire import serialize, deserialize

state = GossipState("node-1")
state.update("config:key", {"value": 42})

# Serialize for transmission
wire_bytes = serialize(state.to_dict())

# Deserialize on receiving node
received = GossipState.from_dict(deserialize(wire_bytes))
print(received.get("config:key"))  # {"value": 42}
```

---

## Further Reading

- [CRDT Architecture — Full Mathematical Proof](../CRDT_ARCHITECTURE.md)
- [Architecture Map](../ARCHITECTURE_MAP.md)
- [Guide — Convergent Multi-Agent AI](./convergent-multi-agent-ai.md)
- [Guide — Delta Sync and Merkle Verification](./delta-sync-merkle-verification.md)
- [Guide — Provenance-Complete AI](./provenance-complete-ai.md)
- [API Reference — GossipState](../api-reference/layer2-analytics/gossip.md)
- [API Reference — VectorClock](../api-reference/layer1-core/clocks.md)
- [Wire Protocol Reference](../guides/wire-protocol.md)
