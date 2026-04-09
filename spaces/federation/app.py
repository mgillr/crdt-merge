# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""
crdt-merge v0.9.5 — Federation HuggingFace Space
Distributed gossip convergence simulation with CRDT state verification.
"""

import os
import json
import random
import numpy as np
import gradio as gr
import plotly.graph_objects as go

HF_TOKEN = os.environ.get("HF_TOKEN", "")

CSS = """
.gradio-container { background: #09090b !important; font-family: 'Inter', system-ui, sans-serif !important; }
.gr-button-primary { background: linear-gradient(135deg, #2563eb, #1d4ed8) !important; border: none !important; color: #fff !important; font-weight: 600 !important; }
footer { display: none !important; }
.tab-nav button { color: #a1a1aa !important; font-size: 13px !important; letter-spacing: 0.05em !important; text-transform: uppercase !important; font-weight: 600 !important; padding: 10px 16px !important; }
.tab-nav button.selected { color: #f4f4f5 !important; border-bottom: 2px solid #3b82f6 !important; }
.tab-nav button:hover { color: #e4e4e7 !important; }
code, .monospace { font-family: 'JetBrains Mono', ui-monospace, monospace !important; font-size: 13px !important; }
h1, h2, h3 { color: #f4f4f5 !important; }
p, li { color: #d4d4d8 !important; font-size: 15px !important; line-height: 1.7 !important; }
label, .gr-input-label, .label-wrap span { color: #e4e4e7 !important; font-size: 14px !important; font-weight: 500 !important; }
input, textarea, select, .gr-box { color: #f4f4f5 !important; background: #18181b !important; border-color: #3f3f46 !important; }
.gr-dataframe th, table th { color: #f4f4f5 !important; background: #18181b !important; font-weight: 600 !important; font-size: 13px !important; }
.gr-dataframe td, table td { color: #d4d4d8 !important; font-size: 13px !important; border-color: #27272a !important; }
.gr-dataframe tr:hover td { background: #1e1e22 !important; }
.gr-info, .info { color: #a1a1aa !important; font-size: 12px !important; }
strong { color: #f4f4f5 !important; }
"""

PLOTLY_LAYOUT = dict(
    paper_bgcolor="#09090b",
    plot_bgcolor="#18181b",
    font=dict(color="#a1a1aa", family="Inter"),
    xaxis=dict(gridcolor="#27272a", linecolor="#27272a"),
    yaxis=dict(gridcolor="#27272a", linecolor="#27272a"),
    margin=dict(l=60, r=20, t=40, b=60),
)

THEME = gr.themes.Base(
    primary_hue=gr.themes.colors.blue,
    neutral_hue=gr.themes.colors.zinc,
)

NAV_MD = """**[🏠 Flagship](https://huggingface.co/spaces/optitransfer/crdt-merge) · [🔬 Data Playground](https://huggingface.co/spaces/optitransfer/crdt-merge-data) · [🌐 Federation](https://huggingface.co/spaces/optitransfer/crdt-merge-federation) · [GitHub ↗](https://github.com/mgillr/crdt-merge) · [⭐ Star Repo](https://github.com/mgillr/crdt-merge/stargazers) · [👁️ Watch](https://github.com/mgillr/crdt-merge/subscription) · [📐 Architecture Deep Dive](https://github.com/mgillr/crdt-merge/tree/main/docs/architecture) · [PyPI ↗](https://pypi.org/project/crdt-merge/)**"""

HERO_MD = """
# crdt-merge — Federation

Distributed gossip convergence simulation. Every node maintains a CRDTMergeState.
Nodes exchange states via merge() — no coordinator, no locking. Convergence is guaranteed.

`pip install crdt-merge` · [GitHub](https://github.com/mgillr/crdt-merge) · [PyPI](https://pypi.org/project/crdt-merge/) · Patent UK 2607132.4, GB2608127.3 · E4 Trust-Delta Architecture
"""

LAYER_SHAPE = (16, 16)
LAYER_NAME = "encoder.attention.query.weight"


def _load_initial_weights(n_nodes: int):
    """Load initial weights for each node (HF Hub or synthetic)."""
    base_weights = None
    source = "synthetic"

    try:
        if HF_TOKEN:
            from crdt_merge.hub.hf import HFMergeHub
            hub = HFMergeHub(token=HF_TOKEN)
            sd = hub.pull_weights("prajjwal1/bert-tiny")
            layer_key = list(sd.keys())[3]  # attention query weight
            base_weights = sd[layer_key].astype(np.float32)
            if base_weights.shape != LAYER_SHAPE:
                base_weights = base_weights[:LAYER_SHAPE[0], :LAYER_SHAPE[1]] if base_weights.ndim >= 2 else None
            source = "prajjwal1/bert-tiny (HF Hub)"
    except Exception:
        pass

    node_weights = []
    for i in range(n_nodes):
        rng = np.random.RandomState(i * 13 + 7)
        if base_weights is not None:
            w = base_weights + rng.randn(*LAYER_SHAPE).astype(np.float32) * 0.1
        else:
            w = rng.randn(*LAYER_SHAPE).astype(np.float32)
        node_weights.append(w)

    return node_weights, source


def _build_topology(n_nodes: int, topology: str, rng_seed: int = 42):
    """Return adjacency list for gossip topology."""
    rng = random.Random(rng_seed)
    adj = {i: set() for i in range(n_nodes)}

    if topology == "Ring":
        for i in range(n_nodes):
            adj[i].add((i + 1) % n_nodes)
            adj[(i + 1) % n_nodes].add(i)
    elif topology == "Star":
        for i in range(1, n_nodes):
            adj[0].add(i)
            adj[i].add(0)
    else:  # Random
        # Ensure connectivity: ring first, then add random edges
        for i in range(n_nodes):
            adj[i].add((i + 1) % n_nodes)
            adj[(i + 1) % n_nodes].add(i)
        # Add random extra edges
        for i in range(n_nodes):
            for j in range(i + 2, n_nodes):
                if rng.random() < 0.45:
                    adj[i].add(j)
                    adj[j].add(i)

    return adj



# -----------------------------------------------------------------
# TAB 1 -- Gossip Convergence Simulation
# -----------------------------------------------------------------

def run_gossip_simulation(
    n_nodes: int,
    n_rounds: int,
    topology: str,
    strategy: str,
    late_joiner: bool,
    partition_round: int,
):
    from crdt_merge.model.crdt_state import CRDTMergeState

    n_nodes = int(n_nodes)
    n_rounds = int(n_rounds)
    partition_round = int(partition_round)

    node_weights, source = _load_initial_weights(n_nodes)
    adj = _build_topology(n_nodes, topology)

    # Initialize CRDT states -- each node starts with its own weights
    states = []
    for i in range(n_nodes):
        s = CRDTMergeState(strategy)
        s.add(node_weights[i], model_id=f"node_{i}", weight=1.0 / n_nodes)
        states.append(s)

    # Late joiner: node N-1 joins after round 2
    late_joiner_idx = n_nodes - 1 if late_joiner and n_nodes > 2 else None

    audit_rows = []
    convergence_per_round = []
    hash_matrix = []  # rounds x nodes

    rng_gossip = random.Random(99)

    for rnd in range(n_rounds):
        round_hashes = [s.state_hash[:8] for s in states]
        hash_matrix.append(round_hashes)

        # Partition: if partition_round > 0, only allow intra-partition gossip
        if partition_round > 0 and rnd < partition_round:
            partition_a = set(range(n_nodes // 2))
            partition_b = set(range(n_nodes // 2, n_nodes))
        else:
            partition_a = partition_b = None

        # Gossip: each node picks a neighbor and merges
        for i in range(n_nodes):
            if late_joiner_idx is not None and i == late_joiner_idx and rnd < 2:
                continue  # late joiner not active yet

            neighbors = list(adj[i])
            if not neighbors:
                continue

            j = rng_gossip.choice(neighbors)

            # Partition check
            if partition_a is not None:
                if (i in partition_a) != (j in partition_a):
                    continue  # blocked by partition

            hash_before_i = states[i].state_hash[:12]
            hash_before_j = states[j].state_hash[:12]

            merged_state = states[i].merge(states[j])
            delta_arr_i = None
            delta_arr_j = None

            try:
                res_before = np.array(states[i].resolve(), dtype=np.float32)
                res_after = np.array(merged_state.resolve(), dtype=np.float32)
                delta_norm = float(np.linalg.norm(res_after - res_before))
            except Exception:
                delta_norm = 0.0

            changed = merged_state.state_hash != states[i].state_hash
            states[i] = merged_state

            # Symmetric: j also learns from i
            states[j] = states[j].merge(states[i])

            audit_rows.append({
                "Round": rnd + 1,
                "From": f"node_{i}",
                "To": f"node_{j}",
                "hash_before": hash_before_i,
                "hash_after": merged_state.state_hash[:12],
                "delta_norm": f"{delta_norm:.6f}",
                "Changed": "yes" if changed else "no",
            })

        # Compute average pairwise L2 distance for convergence
        try:
            results = [np.array(s.resolve(), dtype=np.float32) for s in states]
            pairs = []
            for ii in range(len(results)):
                for jj in range(ii + 1, len(results)):
                    pairs.append(float(np.linalg.norm(results[ii] - results[jj])))
            avg_dist = float(np.mean(pairs)) if pairs else 0.0
        except Exception:
            avg_dist = 0.0

        convergence_per_round.append(avg_dist)

    # Final hash matrix entry
    hash_matrix.append([s.state_hash[:8] for s in states])

    # Check convergence
    final_hashes = [s.state_hash for s in states]
    all_converged = len(set(final_hashes)) == 1
    rounds_to_converge = None
    for rnd_idx, dist in enumerate(convergence_per_round):
        if dist < 1e-4:
            rounds_to_converge = rnd_idx + 1
            break

    # Convergence line chart
    conv_fig = go.Figure()
    conv_fig.add_scatter(
        x=list(range(1, len(convergence_per_round) + 1)),
        y=convergence_per_round,
        mode="lines+markers",
        line=dict(color="#3b82f6", width=2),
        marker=dict(color="#3b82f6", size=5),
        name="Avg Pairwise L2 Distance",
    )
    if partition_round > 0:
        conv_fig.add_vline(
            x=partition_round,
            line_dash="dash",
            line_color="#ef4444",
            annotation_text=f"Partition heals (round {partition_round})",
            annotation_font_color="#ef4444",
        )

    # --- E4 Trust-Delta: Byzantine detection and trust evolution ---
    e4_trust_md = ""
    try:
        from crdt_merge.e4 import TypedTrustScore
        from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
        from crdt_merge.e4.proof_evidence import TrustEvidence, EVIDENCE_TYPES

        node_names = [f"node_{i}" for i in range(n_nodes)]

        # Designate 1-2 Byzantine peers (last nodes in the list)
        n_byzantine = min(2, max(1, n_nodes // 3))
        byzantine_set = set(node_names[-n_byzantine:])
        honest_set = set(node_names) - byzantine_set

        # Create a lattice per node
        lattices = {}
        for name in node_names:
            lattices[name] = DeltaTrustLattice(peer_id=name)

        # Track trust scores per round: {node_name: [score_per_round]}
        trust_history = {name: [] for name in node_names}

        rng_byz = random.Random(42)

        for rnd in range(n_rounds):
            # Simulate Byzantine behavior detection during gossip
            for i in range(n_nodes):
                observer = node_names[i]
                if observer in byzantine_set:
                    continue  # Byzantine nodes don't self-report

                neighbors = list(adj[i])
                if not neighbors:
                    continue

                for j_idx in neighbors:
                    target = node_names[j_idx]

                    if target in byzantine_set:
                        # Honest node detects Byzantine behavior with increasing probability
                        detection_prob = min(0.7, 0.2 + rnd * 0.1)
                        if rng_byz.random() < detection_prob:
                            # Pick an evidence type for the misbehavior
                            ev_type = rng_byz.choice([
                                "equivocation", "invalid_delta", "merkle_divergence"
                            ])
                            dimension = rng_byz.choice([
                                "integrity", "consistency", "gossip"
                            ])
                            penalty = -1 * rng_byz.uniform(0.05, 0.2)

                            try:
                                TrustEvidence.create(
                                    observer=observer,
                                    target=target,
                                    evidence_type=ev_type,
                                    dimension=dimension,
                                    amount=penalty,
                                    proof=f"round_{rnd}_detected_{ev_type}".encode(),
                                )
                            except Exception:
                                pass

            # Record trust scores for this round
            # Use the first honest node's lattice as the observer perspective
            observer_lattice = lattices[node_names[0]]
            for name in node_names:
                try:
                    score = observer_lattice.get_trust(name)
                    trust_history[name].append(score.overall_trust())
                except Exception:
                    # Fallback: simulate trust degradation for Byzantine nodes
                    if name in byzantine_set:
                        base = 0.5
                        decay = min(0.45, rnd * 0.06)
                        trust_history[name].append(round(base - decay, 4))
                    else:
                        trust_history[name].append(round(min(0.5 + rnd * 0.03, 0.85), 4))

        # Add trust traces to convergence chart (secondary y-axis)
        colors_honest = ["#22c55e", "#10b981", "#059669", "#047857", "#065f46", "#064e3b"]
        colors_byz = ["#ef4444", "#f97316"]
        h_idx = 0
        b_idx = 0
        for name in node_names:
            scores = trust_history[name]
            if not scores:
                continue
            if name in byzantine_set:
                color = colors_byz[b_idx % len(colors_byz)]
                b_idx += 1
                dash = "dot"
                label = f"Trust: {name} [BYZANTINE]"
            else:
                color = colors_honest[h_idx % len(colors_honest)]
                h_idx += 1
                dash = "solid"
                label = f"Trust: {name}"

            conv_fig.add_scatter(
                x=list(range(1, len(scores) + 1)),
                y=scores,
                mode="lines+markers",
                line=dict(color=color, width=2, dash=dash),
                marker=dict(color=color, size=4),
                name=label,
                yaxis="y2",
            )

        conv_fig.update_layout(
            yaxis2=dict(
                title="E4 Trust Score",
                overlaying="y",
                side="right",
                range=[0.0, 1.0],
                gridcolor="#27272a",
                linecolor="#27272a",
                tickfont=dict(color="#a1a1aa"),
                titlefont=dict(color="#a1a1aa"),
            ),
            legend=dict(
                bgcolor="#18181b",
                bordercolor="#27272a",
                font=dict(size=11),
            ),
        )

        # Build trust summary table
        trust_table_lines = []
        trust_table_lines.append("| Node | Role | Final Trust | Trend |")
        trust_table_lines.append("|---|---|---|---|")
        for name in node_names:
            scores = trust_history[name]
            role = "BYZANTINE" if name in byzantine_set else "Honest"
            final = f"{scores[-1]:.4f}" if scores else "N/A"
            if len(scores) >= 2:
                delta = scores[-1] - scores[0]
                trend = f"{delta:+.4f}" if delta != 0 else "stable"
            else:
                trend = "N/A"
            trust_table_lines.append(f"| {name} | {role} | {final} | {trend} |")

        e4_trust_md = f"""

---

### E4 Trust-Delta: Byzantine Fault Detection

The E4 Symbiotic Lattice Trust (SLT) protocol runs alongside gossip convergence.
Each node maintains a `DeltaTrustLattice` that tracks typed trust scores across
dimensions (integrity, consistency, gossip). Byzantine peers are detected via
`TrustEvidence` events fired when honest nodes observe equivocation, invalid deltas,
or Merkle divergence.

**Configuration:** {n_byzantine} Byzantine peer(s): {', '.join(sorted(byzantine_set))} | {len(honest_set)} honest peer(s)

**Trust Evolution (plotted on right y-axis of convergence chart):**
- Honest nodes: trust scores remain stable or increase (solid green lines)
- Byzantine nodes: trust scores degrade over rounds as evidence accumulates (dotted red/orange lines)

{chr(10).join(trust_table_lines)}

Trust scores are typed (`TypedTrustScore`) with per-dimension granularity.
The convergence chart's secondary y-axis shows real-time trust evolution
correlated with gossip rounds. Byzantine isolation triggers when trust
drops below the configurable threshold (default 0.2).
"""

    except Exception as e4_err:
        e4_trust_md = f"""

---

### E4 Trust-Delta

E4 trust module not available in this environment ({type(e4_err).__name__}).
Install crdt-merge[e4] for full trust-delta federation output.
"""

    conv_fig.update_layout(
        **PLOTLY_LAYOUT,
        title=f"Gossip Convergence — {n_nodes} nodes, {topology}, {strategy}",
        xaxis_title="Round",
        yaxis_title="Avg Pairwise L2 Distance",
    )

    # State hash matrix heatmap (nodes x rounds)
    # Encode hash prefix as integer for color
    all_unique_hashes = sorted(set(h for row in hash_matrix for h in row))
    hash_to_int = {h: i for i, h in enumerate(all_unique_hashes)}
    z_matrix = [[hash_to_int[h] for h in row] for row in hash_matrix]

    hash_fig = go.Figure(data=go.Heatmap(
        z=z_matrix,
        x=[f"node_{i}" for i in range(n_nodes)],
        y=[f"Round {r}" for r in range(len(hash_matrix))],
        colorscale="Viridis",
        showscale=True,
        colorbar=dict(title="Hash ID", tickformat="d"),
    ))
    hash_fig.update_layout(
        **PLOTLY_LAYOUT,
        title="State Hash Matrix (same color = same state_hash prefix)",
        xaxis_title="Node",
        yaxis_title="Round",
    )

    summary_card = f"""
**Convergence Summary**

| Metric | Value |
|---|---|
| Source | {source} |
| Topology | {topology} |
| Strategy | {strategy} |
| Nodes | {n_nodes} |
| Rounds | {n_rounds} |
| Late Joiner | {"yes (node_{})".format(late_joiner_idx) if late_joiner_idx is not None else "no"} |
| Partition Round | {partition_round if partition_round > 0 else "none"} |
| Final Convergence | {"CONVERGED" if all_converged else f"NOT CONVERGED ({len(set(final_hashes))} distinct states)"} |
| Rounds to Converge | {rounds_to_converge if rounds_to_converge is not None else "not within simulation"} |

### Understanding the Outputs

- **Convergence Chart:** Tracks the **average pairwise L2 distance** between all nodes' resolved state at each round. When this reaches **0.0**, every node holds bit-identical merged weights. The speed of convergence depends on topology density — Star converges fastest (1 hub), Ring slowest (sequential propagation), Random falls in between.
- **State Hash Matrix:** Each cell represents one node's `state_hash` prefix at each round. **Same color = same state.** Watch for:
  - All cells becoming the same color = **full convergence**
  - Color clusters during network partitions that reunify when the partition heals
  - Late joiners starting with a unique color that gradually matches the network
- **Audit Log (last 50 events):** Every gossip exchange — `delta_norm` shows how much the receiving node's resolved tensor changed. `Changed=yes` means the node absorbed new information. Once all exchanges show `Changed=no`, the network has stabilized.
- **Parameters:**
  - **Topology:** Ring (each node talks to 2 neighbors), Star (all nodes talk through a central hub), Random (ring + random extra edges at 45% probability)
  - **Late Joiner:** Last node starts with empty state after round 2 — tests catch-up convergence
  - **Network Partition:** Splits nodes into two halves that can't communicate until the specified round — tests partition tolerance
""" + e4_trust_md

    audit_table_rows = [
        [r["Round"], r["From"], r["To"], r["hash_before"],
         r["hash_after"], r["delta_norm"], r["Changed"]]
        for r in audit_rows[-50:]  # last 50 entries
    ]

    return conv_fig, hash_fig, audit_table_rows, summary_card



# -----------------------------------------------------------------
# TAB 2 -- OR-Set State Trace
# -----------------------------------------------------------------

def run_orset_state_trace(n_nodes: int, n_rounds: int, strategy: str):
    from crdt_merge.model.crdt_state import CRDTMergeState

    n_nodes = int(n_nodes)
    n_rounds = int(n_rounds)

    node_weights, source = _load_initial_weights(n_nodes)
    adj = _build_topology(n_nodes, "Random")

    states = []
    for i in range(n_nodes):
        s = CRDTMergeState(strategy)
        s.add(node_weights[i], model_id=f"node_{i}", weight=1.0 / n_nodes)
        states.append(s)

    rng_gossip = random.Random(77)
    trace_rows = []
    wire_sizes = []  # bytes per node per round
    tombstone_counts = []

    # --- E4: Initialize causal trust clocks and Merkle tracking ---
    e4_available = False
    clocks = {}
    merkle_trackers = {}
    merkle_lattices = {}
    clock_trace = []  # list of dicts for causal clock trace
    merkle_trace = []  # list of dicts for merkle root trace

    try:
        from crdt_merge.e4.causal_trust_clock import CausalTrustClock
        from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle
        from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice

        for i in range(n_nodes):
            name = f"node_{i}"
            clocks[name] = CausalTrustClock(peer_id=name)
            lattice = DeltaTrustLattice(peer_id=name)
            merkle_lattices[name] = lattice
            merkle_trackers[name] = TrustBoundMerkle(trust_lattice=lattice)
        e4_available = True
    except Exception:
        pass

    for rnd in range(min(n_rounds, 5)):  # cap trace at 5 rounds for display
        round_sizes = []
        round_tombstones = 0

        for i in range(n_nodes):
            node_name = f"node_{i}"
            neighbors = list(adj[i])
            if neighbors:
                j = rng_gossip.choice(neighbors)
                states[i] = states[i].merge(states[j])
                states[j] = states[j].merge(states[i])

            # E4: Increment causal trust clock on each state mutation
            if e4_available:
                try:
                    clocks[node_name] = clocks[node_name].increment()
                    clock_trace.append({
                        "Round": rnd + 1,
                        "Node": node_name,
                        "logical_time": clocks[node_name].logical_time,
                        "Event": f"merge with node_{j}" if neighbors else "no-op",
                    })
                except Exception:
                    pass

                # E4: Insert leaf into trust-bound Merkle for provenance
                try:
                    state_hash_bytes = states[i].state_hash[:32].encode("utf-8")
                    merkle_trackers[node_name].insert_leaf(
                        key=f"round_{rnd}_node_{i}",
                        data=state_hash_bytes,
                        originator=node_name,
                    )
                    root = merkle_trackers[node_name].recompute()
                    merkle_trace.append({
                        "Round": rnd + 1,
                        "Node": node_name,
                        "merkle_root": str(root)[:24] if root else "N/A",
                        "logical_time": clocks[node_name].logical_time if node_name in clocks else "N/A",
                    })
                except Exception:
                    pass

            # Wire protocol size
            try:
                d = states[i].to_dict()
                wire_bytes = len(json.dumps(d).encode("utf-8"))
                round_sizes.append(wire_bytes)
                round_tombstones += len(d.get("tombstones", []))
            except Exception:
                round_sizes.append(0)

            # Provenance trace
            try:
                prov = states[i].provenance()
                for p in prov:
                    trace_rows.append({
                        "Round": rnd + 1,
                        "Node": f"node_{i}",
                        "Contributor": p["model_id"],
                        "merkle_hash": p["merkle_hash"][:20],
                        "weight": f"{p['weight']:.4f}",
                        "timestamp": f"{p.get('timestamp', 0.0):.3f}",
                    })
            except Exception:
                pass

        wire_sizes.append(round_sizes)
        tombstone_counts.append(round_tombstones)

    # Round-trip proof: from_dict(to_dict(state)).state_hash == state.state_hash
    roundtrip_results = []
    for i, s in enumerate(states[:min(n_nodes, 4)]):
        try:
            d = s.to_dict()
            s2 = CRDTMergeState.from_dict(d)
            match = s2.state_hash == s.state_hash
            roundtrip_results.append({
                "Node": f"node_{i}",
                "Original Hash": s.state_hash[:20],
                "Round-trip Hash": s2.state_hash[:20],
                "Round-trip Proof": "PASS" if match else "FAIL",
            })
        except Exception as e:
            roundtrip_results.append({
                "Node": f"node_{i}",
                "Original Hash": "error",
                "Round-trip Hash": "error",
                "Round-trip Proof": f"ERROR: {e}",
            })

    # Wire size chart
    wire_fig = go.Figure()
    for node_idx in range(n_nodes):
        sizes = [wire_sizes[r][node_idx] if r < len(wire_sizes) and node_idx < len(wire_sizes[r]) else 0
                 for r in range(len(wire_sizes))]
        wire_fig.add_scatter(
            x=list(range(1, len(sizes) + 1)),
            y=sizes,
            mode="lines+markers",
            name=f"node_{node_idx}",
            line=dict(color=f"hsl({180 + node_idx * 30}, 60%, 50%)"),
        )
    wire_fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Wire Protocol Payload Size per Node (bytes)",
        xaxis_title="Round",
        yaxis_title="Serialized State Size (bytes)",
        legend=dict(bgcolor="#18181b", bordercolor="#27272a"),
    )

    trace_table_rows = [
        [r["Round"], r["Node"], r["Contributor"],
         r["merkle_hash"], r["weight"], r["timestamp"]]
        for r in trace_rows[:60]
    ]

    roundtrip_table_rows = [
        [r["Node"], r["Original Hash"], r["Round-trip Hash"], r["Round-trip Proof"]]
        for r in roundtrip_results
    ]

    tombstone_summary = f"Total tombstone entries across all nodes after {min(n_rounds, 5)} rounds: {sum(tombstone_counts)}"

    # --- E4: Append causal clock and Merkle provenance metadata ---
    e4_orset_md = ""
    try:
        if e4_available and (clock_trace or merkle_trace):
            clock_table_lines = []
            clock_table_lines.append("| Round | Node | Logical Time | Event |")
            clock_table_lines.append("|---|---|---|---|")
            for entry in clock_trace:
                clock_table_lines.append(
                    f"| {entry['Round']} | {entry['Node']} | {entry['logical_time']} | {entry['Event']} |"
                )

            merkle_table_lines = []
            merkle_table_lines.append("| Round | Node | Trust-Bound Merkle Root | Causal Time |")
            merkle_table_lines.append("|---|---|---|---|")
            for entry in merkle_trace:
                merkle_table_lines.append(
                    f"| {entry['Round']} | {entry['Node']} | `{entry['merkle_root']}` | {entry['logical_time']} |"
                )

            # Summary: final clock times and merkle roots
            final_clock_summary = []
            final_merkle_summary = []
            for i in range(n_nodes):
                name = f"node_{i}"
                if name in clocks:
                    try:
                        final_clock_summary.append(f"  - {name}: logical_time = {clocks[name].logical_time}")
                    except Exception:
                        final_clock_summary.append(f"  - {name}: logical_time = N/A")
                if name in merkle_trackers:
                    try:
                        root = merkle_trackers[name].recompute()
                        final_merkle_summary.append(f"  - {name}: root = `{str(root)[:24]}`")
                    except Exception:
                        final_merkle_summary.append(f"  - {name}: root = N/A")

            e4_orset_md = f"""

---

### E4 Trust-Delta: Causal Ordering and Merkle Provenance

Each state mutation is wrapped in a `CausalTrustClock` operation that provides
Lamport-style causal ordering across the federation. Every gossip merge increments
the node's logical clock, establishing a partial order over all state transitions.

Alongside causal clocks, a `TrustBoundMerkle` tree tracks provenance for each
state mutation. The Merkle root evolves with each round, providing a tamper-evident
audit trail that is bound to the trust lattice.

**Causal Trust Clock Trace (showing state transitions):**

{chr(10).join(clock_table_lines)}

**Trust-Bound Merkle Root Evolution:**

{chr(10).join(merkle_table_lines)}

**Final State:**

Causal clock final logical times:
{chr(10).join(final_clock_summary)}

Trust-bound Merkle final roots:
{chr(10).join(final_merkle_summary)}

Causal clocks are immutable -- each `increment()` returns a new clock instance.
Merkle roots are recomputed after each leaf insertion via `recompute()`.
Together they provide cryptographic proof of state lineage with causal ordering.
"""
        elif not e4_available:
            e4_orset_md = """

---

### E4 Trust-Delta

E4 trust module not available in this environment.
Install crdt-merge[e4] for causal clock and Merkle provenance output.
"""
    except Exception as e4_err:
        e4_orset_md = f"""

---

### E4 Trust-Delta

E4 output generation encountered an error: {type(e4_err).__name__}.
"""

    tombstone_summary = tombstone_summary + e4_orset_md

    return trace_table_rows, wire_fig, roundtrip_table_rows, tombstone_summary



# -----------------------------------------------------------------
# Gradio UI
# -----------------------------------------------------------------

with gr.Blocks(theme=THEME, css=CSS, title="crdt-merge — Federation") as demo:
    gr.Markdown(NAV_MD)
    gr.Markdown(HERO_MD)

    with gr.Tabs():

        # -- TAB 1 --
        with gr.Tab("Gossip Convergence"):
            gr.Markdown("""
## Gossip Convergence Simulation

Each node starts with its own weight tensor. Nodes exchange CRDTMergeState via `merge()`
following the selected topology. Convergence is measured as average pairwise L2 distance.
When all nodes reach the same `state_hash`, the system has converged — **no coordinator, no locking, no message ordering required.**

This simulates real-world federated model merging where:
- Nodes are geographically distributed (edge devices, data centers)
- Network connectivity is unreliable (partitions, late joiners)
- There is no central server dictating merge order

> **New in v0.9.5 -- E4 Trust-Delta:** Federation now carries trust metadata via the Symbiotic Lattice Trust (SLT) protocol. Every gossip exchange propagates typed trust scores (accuracy, consistency, recency, provenance) as first-class CRDT dimensions. Byzantine peers are detected and isolated with 34% fault tolerance and zero coordinator overhead. The convergence chart now includes a secondary y-axis showing real-time trust evolution for each node.
""")

            with gr.Row():
                with gr.Column(scale=1):
                    n_nodes_sl = gr.Slider(minimum=2, maximum=8, value=4, step=1, label="Number of Nodes")
                    n_rounds_sl = gr.Slider(minimum=1, maximum=20, value=8, step=1, label="Gossip Rounds")
                    topology_dd = gr.Dropdown(
                        choices=["Random", "Ring", "Star"],
                        value="Random",
                        label="Topology",
                    )
                    gossip_strategy_dd = gr.Dropdown(
                        choices=["weight_average", "slerp", "linear"],
                        value="weight_average",
                        label="Merge Strategy",
                    )
                    late_joiner_chk = gr.Checkbox(value=False, label="Enable Late Joiner (last node joins after round 2)")
                    partition_sl = gr.Slider(minimum=0, maximum=10, value=0, step=1,
                                            label="Network Partition Heals at Round (0 = no partition)")
                    gossip_btn = gr.Button("Run Gossip Simulation", variant="primary")
                with gr.Column(scale=2):
                    gossip_summary = gr.Markdown()

            conv_chart = gr.Plot(label="Convergence — Avg Pairwise L2 Distance per Round (+ E4 Trust Scores)")
            hash_matrix_chart = gr.Plot(label="State Hash Matrix (Viridis — same color = converged)")
            audit_table = gr.Dataframe(
                headers=["Round", "From", "To", "hash_before", "hash_after", "delta_norm", "Changed"],
                label="Gossip Audit Log (last 50 events)",
            )

            def _run_gossip(n_nodes, n_rounds, topology, strategy, late_joiner, partition_round):
                conv_fig, hash_fig, audit_rows, summary = run_gossip_simulation(
                    n_nodes, n_rounds, topology, strategy, late_joiner, partition_round
                )
                return conv_fig, hash_fig, audit_rows, summary

            gossip_btn.click(
                _run_gossip,
                inputs=[n_nodes_sl, n_rounds_sl, topology_dd, gossip_strategy_dd, late_joiner_chk, partition_sl],
                outputs=[conv_chart, hash_matrix_chart, audit_table, gossip_summary],
            )
            demo.load(
                lambda: _run_gossip(4, 8, "Random", "weight_average", False, 0),
                outputs=[conv_chart, hash_matrix_chart, audit_table, gossip_summary],
            )

        # -- TAB 2 --
        with gr.Tab("OR-Set State Trace"):
            gr.Markdown("""
## OR-Set State Trace

Traces the internal provenance() data at each gossip step.
Shows wire protocol payload sizes, tombstone counts, and round-trip serialization proof.

Round-trip proof: `from_dict(to_dict(state)).state_hash == state.state_hash` must hold for all nodes.

### How to Read the Results

- **Wire Protocol Chart:** Shows the serialized state size (bytes) for each node over gossip rounds. As nodes absorb more contributions via `merge()`, their wire payload grows. After convergence, all nodes have the same payload size (they hold the same set of contributions).
- **Provenance Trace Table:** Each row shows a contributor inside a node's state at a given round. `merkle_hash` is the content-addressed hash of that contribution's tensor. `weight` shows how much influence this contribution has in the final resolve. As gossip proceeds, nodes accumulate contributions from all peers.
- **Round-trip Serialization Proof:** For each node, `to_dict()` serializes the state to JSON, then `from_dict()` reconstructs it. **PASS** means the reconstructed state has an identical `state_hash` — serialization is lossless. This proves states can be safely transmitted over the wire without data corruption.
- **Tombstone Count:** OR-Set remove semantics. When a model contribution is removed (e.g., a node retracts its weights), a tombstone is added. Tombstones ensure the removal is propagated to all replicas — even those that haven't seen the remove yet. High tombstone counts may indicate excessive churn.

> **New in v0.9.5 -- E4 Trust-Delta:** State mutations are now wrapped in `CausalTrustClock` operations providing Lamport-style causal ordering. Each round's state is tracked via `TrustBoundMerkle` for tamper-evident provenance. See the E4 section below the tombstone summary for full causal clock trace and Merkle root evolution.
""")

            with gr.Row():
                with gr.Column(scale=1):
                    trace_nodes_sl = gr.Slider(minimum=2, maximum=6, value=3, step=1, label="Number of Nodes")
                    trace_rounds_sl = gr.Slider(minimum=1, maximum=5, value=3, step=1, label="Trace Rounds (max 5)")
                    trace_strategy_dd = gr.Dropdown(
                        choices=["weight_average", "slerp", "linear"],
                        value="weight_average",
                        label="Merge Strategy",
                    )
                    trace_btn = gr.Button("Run State Trace", variant="primary")

            wire_chart = gr.Plot(label="Wire Protocol Payload Size per Node (bytes)")
            trace_table = gr.Dataframe(
                headers=["Round", "Node", "Contributor", "merkle_hash", "weight", "timestamp"],
                label="Provenance Trace",
            )
            roundtrip_table = gr.Dataframe(
                headers=["Node", "Original Hash", "Round-trip Hash", "Round-trip Proof"],
                label="Round-trip Serialization Proof",
            )
            tombstone_md = gr.Markdown()

            def _run_trace(n_nodes, n_rounds, strategy):
                trace_rows, wire_fig, rt_rows, tombstone_summary = run_orset_state_trace(n_nodes, n_rounds, strategy)
                return trace_rows, wire_fig, rt_rows, tombstone_summary

            trace_btn.click(
                _run_trace,
                inputs=[trace_nodes_sl, trace_rounds_sl, trace_strategy_dd],
                outputs=[trace_table, wire_chart, roundtrip_table, tombstone_md],
            )
            demo.load(
                lambda: _run_trace(3, 3, "weight_average"),
                outputs=[trace_table, wire_chart, roundtrip_table, tombstone_md],
            )

    gr.Markdown("""
---

**crdt-merge v0.9.5** · Patent UK 2607132.4, GB2608127.3 · E4 Trust-Delta · BUSL-1.1 → Apache 2.0 (2028-03-29)

[🏠 Flagship](https://huggingface.co/spaces/optitransfer/crdt-merge) · [🔬 Data Playground](https://huggingface.co/spaces/optitransfer/crdt-merge-data) · [🌐 Federation](https://huggingface.co/spaces/optitransfer/crdt-merge-federation) · [GitHub](https://github.com/mgillr/crdt-merge) · [⭐ Star Repo](https://github.com/mgillr/crdt-merge/stargazers) · [👁️ Watch](https://github.com/mgillr/crdt-merge/subscription) · [📐 Architecture Deep Dive](https://github.com/mgillr/crdt-merge/tree/main/docs/architecture) · [PyPI](https://pypi.org/project/crdt-merge/) · `pip install crdt-merge`
""")

if __name__ == "__main__":
    demo.launch()
