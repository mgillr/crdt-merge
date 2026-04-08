---
title: crdt-merge Federation
colorFrom: gray
colorTo: gray
sdk: gradio
sdk_version: "5.50.0"
python_version: "3.12"
app_file: app.py
pinned: false
license: other
license_name: BUSL-1.1
license_link: https://github.com/mgillr/crdt-merge/blob/main/LICENSE
tags:
  - crdt
  - federated-learning
  - gossip
  - distributed
  - convergence
---

# crdt-merge Federation

Distributed gossip convergence simulation powered by [crdt-merge v0.9.4](https://github.com/mgillr/crdt-merge).

## Tabs

**Gossip Convergence** — Simulates N nodes (2-8) exchanging CRDTMergeState via gossip across Random, Ring, or Star topologies. Supports late-joiner nodes and network partitions. Outputs convergence chart, state hash matrix heatmap, and gossip audit log.

**OR-Set State Trace** — Traces internal provenance() data at each gossip step. Shows wire protocol payload sizes, tombstone counts, and round-trip serialization proof: `from_dict(to_dict(state)).state_hash == state.state_hash`.

## Key Properties Demonstrated

- Gossip convergence is guaranteed regardless of message ordering
- All nodes reach identical state_hash
- Wire protocol is compact and self-describing (JSON with Merkle hashes)
- Round-trip serialization preserves exact state identity

## Installation

```
pip install crdt-merge>=0.9.4
```

## License

Business Source License 1.1. Converts to Apache 2.0 on 2028-03-29.
Patent UK 2607132.4, GB2608127.3.

crdt-merge v0.9.4 · [github.com/mgillr/crdt-merge](https://github.com/mgillr/crdt-merge)
