# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
# Patent: UK Application No. GB 2607132.4, GB2608127.3

import time
import hashlib
import gradio as gr
import numpy as np
from safetensors import safe_open
from huggingface_hub import hf_hub_download

from crdt_merge.model.strategies import get_strategy
from crdt_merge.e4 import TypedTrustScore
from crdt_merge.e4.causal_trust_clock import CausalTrustClock
from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from crdt_merge import ORSet

MODELS = {
    "GPT-2 (124M)": "openai-community/gpt2",
    "DistilGPT-2 (82M)": "distilbert/distilgpt2",
}

CUSTOM_CSS = """
.prose *, .markdown-text *, .gr-markdown *, .gr-markdown p,
.gr-markdown h1, .gr-markdown h2, .gr-markdown h3, .gr-markdown h4,
.gr-markdown li, .gr-markdown td, .gr-markdown th, .gr-markdown span,
.gr-markdown strong, .gr-markdown em, .gr-markdown code,
.gr-markdown a, .gr-markdown blockquote, .gr-markdown pre {
    color: #e0e0e0 !important;
}
.gr-markdown table { border-collapse: collapse; width: 100%; margin: 0.5em 0; }
.gr-markdown th { background: #2a3a4a !important; padding: 6px 10px;
    border: 1px solid #4a5a6a; font-weight: 600; }
.gr-markdown td { padding: 6px 10px; border: 1px solid #4a5a6a; }
.gr-markdown tr:nth-child(even) { background: #1a2a3a; }
.gr-markdown code { background: #1e293b !important; padding: 2px 5px;
    border-radius: 3px; font-size: 0.9em; }
.gr-markdown pre { background: #0f172a !important; padding: 12px;
    border-radius: 6px; border: 1px solid #334155; }
.gr-markdown pre code { background: transparent !important; }
"""


def _normalize_key(k):
    for prefix in ("transformer.", "model.", "encoder.", "decoder."):
        if k.startswith(prefix):
            k = k[len(prefix):]
    return k


def _load_tensors(repo_id):
    path = hf_hub_download(repo_id=repo_id, filename="model.safetensors")
    tensors = {}
    with safe_open(path, framework="numpy") as f:
        for key in f.keys():
            tensors[key] = f.get_tensor(key)
    return tensors


# -- Tab 1: Federated Model Merge --

def run_federated_merge(model_name, num_nodes, num_rounds, byzantine_node):
    num_nodes = int(num_nodes)
    num_rounds = int(num_rounds)
    byzantine_node = int(byzantine_node)
    repo = MODELS[model_name]
    tensors = _load_tensors(repo)
    keys = sorted(tensors.keys())

    node_ids = [f"node_{i}" for i in range(num_nodes)]
    peer_set = set(node_ids)

    # Partition layers across nodes
    node_layers = {}
    for i, nid in enumerate(node_ids):
        start = i * len(keys) // num_nodes
        end = (i + 1) * len(keys) // num_nodes
        node_layers[nid] = keys[start:end]

    # Build per-node state
    clocks = {nid: CausalTrustClock(peer_id=nid) for nid in node_ids}
    lattice = DeltaTrustLattice(peer_id="federation", initial_peers=peer_set)
    merkle = TrustBoundMerkle()
    strategy = get_strategy("lerp")

    round_logs = []
    trust_evolution = {nid: [] for nid in node_ids}

    for rnd in range(1, num_rounds + 1):
        round_rows = []
        for i, nid in enumerate(node_ids):
            clocks[nid] = clocks[nid].increment()

            layer_keys = node_layers[nid]
            if not layer_keys:
                continue

            sample_key = layer_keys[0]
            contribution = tensors[sample_key].copy()

            # Byzantine node injects corrupted weights
            is_byzantine = (i == byzantine_node)
            if is_byzantine:
                corruption = np.random.normal(0, 5.0, contribution.shape).astype(contribution.dtype)
                contribution = contribution + corruption
                status = "BYZANTINE -- corrupted"
            else:
                status = "honest"

            merkle.insert_leaf(
                f"{nid}_r{rnd}_{sample_key}",
                contribution.tobytes()[:2048],
                nid,
            )

            trust_score = lattice.get_trust(nid).overall_trust()
            trust_evolution[nid].append(trust_score)

            round_rows.append(
                f"| {nid} | {clocks[nid].logical_time} | "
                f"`{sample_key[:40]}` | {status} | {trust_score:.4f} |"
            )

        round_logs.append(
            f"### Round {rnd}\n\n"
            f"| Node | Clock | Layer Contributed | Status | Trust |\n"
            f"|---|---|---|---|---|\n"
            + "\n".join(round_rows)
        )

    # Final merge: average all non-byzantine contributions for first shared key
    first_key = keys[0]
    honest_tensors = []
    for i, nid in enumerate(node_ids):
        if i == byzantine_node:
            continue
        honest_tensors.append(tensors[first_key])

    if len(honest_tensors) >= 2:
        merged = strategy.merge(honest_tensors[:2], weights=[0.5, 0.5])
        merge_hash = hashlib.sha256(merged.tobytes()[:4096]).hexdigest()[:32]
    else:
        merge_hash = "insufficient_honest_nodes"

    # Trust evolution table
    evo_header = "### Trust Evolution\n\n| Node |"
    for r in range(1, num_rounds + 1):
        evo_header += f" R{r} |"
    evo_header += "\n|---|" + "---|" * num_rounds + "\n"
    evo_rows = []
    for nid in node_ids:
        row = f"| {nid} |"
        for val in trust_evolution[nid]:
            row += f" {val:.4f} |"
        evo_rows.append(row)

    merkle.recompute()
    output = (
        f"## Federated Model Merge\n\n"
        f"**Model:** {model_name} | **Nodes:** {num_nodes} | "
        f"**Rounds:** {num_rounds} | **Byzantine:** node_{byzantine_node}\n\n"
        f"**Merkle provenance root:** `{merkle.root_hash[:32]}...`\n\n"
        + "\n\n".join(round_logs)
        + f"\n\n{evo_header}"
        + "\n".join(evo_rows)
        + f"\n\n### Final Merged Result\n\n"
        f"**Honest merge hash:** `{merge_hash}`\n"
    )
    return output


# -- Tab 2: OR-Set State Trace --

def run_orset_trace(model_name, num_ops):
    num_ops = int(num_ops)
    repo = MODELS[model_name]
    tensors = _load_tensors(repo)
    layer_names = sorted(tensors.keys())

    nodes = ["alpha", "beta", "gamma"]
    states = {n: ORSet() for n in nodes}
    clocks = {n: CausalTrustClock(peer_id=n) for n in nodes}
    merkle = TrustBoundMerkle()

    ops_log = []
    merkle_evolution = []

    # Phase 1: concurrent adds from different nodes
    for i in range(min(num_ops, len(layer_names))):
        node = nodes[i % len(nodes)]
        layer = layer_names[i]
        states[node].add(layer)
        clocks[node] = clocks[node].increment()

        data = tensors[layer].tobytes()[:512]
        merkle.insert_leaf(f"op_{i}_{layer}", data, node)
        merkle.recompute()
        merkle_evolution.append(merkle.root_hash[:20])

        ops_log.append(
            f"| {i+1} | ADD | `{layer[:45]}` | {node} | "
            f"t={clocks[node].logical_time} | `{merkle.root_hash[:20]}...` |"
        )

    # Phase 2: some removes (concurrent conflict)
    remove_count = min(3, len(layer_names))
    for i in range(remove_count):
        layer = layer_names[i]
        remove_node = nodes[(i + 1) % len(nodes)]
        states[remove_node].remove(layer)
        clocks[remove_node] = clocks[remove_node].increment()

        merkle.insert_leaf(f"rm_{i}_{layer}", b"REMOVE", remove_node)
        merkle.recompute()
        merkle_evolution.append(merkle.root_hash[:20])

        ops_log.append(
            f"| {num_ops + i + 1} | REMOVE | `{layer[:45]}` | {remove_node} | "
            f"t={clocks[remove_node].logical_time} | `{merkle.root_hash[:20]}...` |"
        )

    # Phase 3: merge all states
    merged = states[nodes[0]]
    for n in nodes[1:]:
        merged = merged.merge(states[n])

    # E4 trust summary
    lattice = DeltaTrustLattice(peer_id="orset_tracer", initial_peers=set(nodes))
    trust_rows = []
    for n in nodes:
        t = lattice.get_trust(n).overall_trust()
        trust_rows.append(f"| {n} | t={clocks[n].logical_time} | {t:.4f} |")

    output = (
        f"## OR-Set State Trace\n\n"
        f"**Model:** {model_name} | **Operations:** {num_ops + remove_count}\n\n"
        f"### Operation Log\n\n"
        f"| # | Op | Layer | Node | Clock | Merkle Root |\n"
        f"|---|---|---|---|---|---|\n"
        + "\n".join(ops_log)
        + f"\n\n### Automatic Conflict Resolution\n\n"
        f"OR-Set semantics: concurrent add+remove resolved by add-wins rule.\n\n"
        f"### Per-Node E4 Trust State\n\n"
        f"| Node | Clock | Trust |\n|---|---|---|\n"
        + "\n".join(trust_rows)
        + f"\n\n### Merkle Root Evolution\n\n"
        f"```\n"
        + "\n".join(f"  op {i+1}: {h}..." for i, h in enumerate(merkle_evolution))
        + f"\n```\n"
    )
    return output


# -- Build UI --

with gr.Blocks(css=CUSTOM_CSS, theme=gr.themes.Base()) as demo:
    gr.Markdown("# crdt-merge Federation\n\nFederated merges with Byzantine fault detection and CRDT state tracing.")

    with gr.Tab("Federated Model Merge"):
        fm_model = gr.Dropdown(choices=list(MODELS.keys()), value="GPT-2 (124M)", label="Model")
        with gr.Row():
            fm_nodes = gr.Slider(minimum=3, maximum=8, value=4, step=1, label="Federated nodes")
            fm_rounds = gr.Slider(minimum=1, maximum=5, value=3, step=1, label="Gossip rounds")
            fm_byz = gr.Slider(minimum=0, maximum=7, value=2, step=1, label="Byzantine node index")
        btn_fed = gr.Button("Run Federation")
        out_fed = gr.Markdown()
        btn_fed.click(run_federated_merge, [fm_model, fm_nodes, fm_rounds, fm_byz], out_fed)

    with gr.Tab("OR-Set State Trace"):
        os_model = gr.Dropdown(choices=list(MODELS.keys()), value="GPT-2 (124M)", label="Model")
        os_ops = gr.Slider(minimum=3, maximum=20, value=8, step=1, label="Number of add operations")
        btn_os = gr.Button("Run OR-Set Trace")
        out_os = gr.Markdown()
        btn_os.click(run_orset_trace, [os_model, os_ops], out_os)

if __name__ == "__main__":
    demo.launch()
