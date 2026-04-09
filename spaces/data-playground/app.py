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
from crdt_merge.clocks import VectorClock
from crdt_merge.merkle import MerkleTree

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


def _build_common_keys(tensors_a, tensors_b):
    norm_a = {_normalize_key(k): k for k in tensors_a}
    norm_b = {_normalize_key(k): k for k in tensors_b}
    common = sorted(set(norm_a.keys()) & set(norm_b.keys()))
    return common, norm_a, norm_b


# -- Tab 1: Dataset Merge --

def run_dataset_merge(model_a_name, model_b_name, strategy_name, num_layers):
    num_layers = int(num_layers)
    repo_a = MODELS[model_a_name]
    repo_b = MODELS[model_b_name]

    tensors_a = _load_tensors(repo_a)
    tensors_b = _load_tensors(repo_b)

    common, norm_a, norm_b = _build_common_keys(tensors_a, tensors_b)
    selected = common[:num_layers]

    strategy = get_strategy(strategy_name)
    needs_base = strategy_name in ("task_arithmetic", "ties", "dare", "dare_ties",
                                   "model_breadcrumbs", "della")

    lattice = DeltaTrustLattice(peer_id="merger", initial_peers={model_a_name, model_b_name})
    merkle = TrustBoundMerkle()
    clock = CausalTrustClock(peer_id="merger")

    rows = []
    for nk in selected:
        key_a = norm_a[nk]
        key_b = norm_b[nk]
        ta = tensors_a[key_a]
        tb = tensors_b[key_b]

        if ta.shape != tb.shape:
            rows.append(f"| `{nk}` | SKIP (shape mismatch {ta.shape} vs {tb.shape}) | -- | -- |")
            continue

        if needs_base:
            base = (ta * 0.5 + tb * 0.5).astype(ta.dtype)
            merged = strategy.merge([ta, tb], weights=[0.5, 0.5], base=base)
        else:
            merged = strategy.merge([ta, tb], weights=[0.5, 0.5])

        clock = clock.increment()
        delta = float(np.mean(np.abs(merged - ta)))
        cos_sim = float(np.dot(merged.flatten(), ta.flatten()) /
                        (np.linalg.norm(merged) * np.linalg.norm(ta) + 1e-12))

        merkle.insert_leaf(nk, merged.tobytes()[:4096], "merger")

        score_a = lattice.get_trust(model_a_name)
        trust_val = score_a.overall_trust()

        rows.append(f"| `{nk}` | {merged.shape} | {delta:.6f} | {cos_sim:.6f} |")

    trust_a = lattice.get_trust(model_a_name).overall_trust()
    trust_b = lattice.get_trust(model_b_name).overall_trust()
    merkle.recompute()

    header = (
        f"## Dataset Merge Results\n\n"
        f"**Strategy:** `{strategy_name}` | **Clock:** t={clock.logical_time} | "
        f"**Merkle root:** `{merkle.root_hash[:24]}...`\n\n"
        f"### Trust Scores\n\n"
        f"| Source | Trust |\n|---|---|\n"
        f"| {model_a_name} | {trust_a:.4f} |\n"
        f"| {model_b_name} | {trust_b:.4f} |\n\n"
        f"### Per-Layer Merge\n\n"
        f"| Layer | Shape | Mean Delta | Cosine Sim |\n|---|---|---|---|\n"
    )
    return header + "\n".join(rows)


# -- Tab 2: Conflict Analysis --

def run_conflict_analysis(model_a_name, model_b_name, top_n):
    top_n = int(top_n)
    repo_a = MODELS[model_a_name]
    repo_b = MODELS[model_b_name]

    tensors_a = _load_tensors(repo_a)
    tensors_b = _load_tensors(repo_b)

    common, norm_a, norm_b = _build_common_keys(tensors_a, tensors_b)

    lattice = DeltaTrustLattice(peer_id="analyzer", initial_peers={model_a_name, model_b_name})
    clock = CausalTrustClock(peer_id="analyzer")

    conflicts = []
    for nk in common:
        key_a = norm_a[nk]
        key_b = norm_b[nk]
        ta = tensors_a[key_a]
        tb = tensors_b[key_b]

        if ta.shape != tb.shape:
            continue

        diff = np.abs(ta.astype(np.float32) - tb.astype(np.float32))
        mean_div = float(np.mean(diff))
        max_div = float(np.max(diff))
        pct_conflict = float(np.mean(diff > 0.01) * 100)

        conflicts.append((nk, mean_div, max_div, pct_conflict, ta.shape))
        clock = clock.increment()

    conflicts.sort(key=lambda x: x[1], reverse=True)
    selected = conflicts[:top_n]

    trust_a = lattice.get_trust(model_a_name).overall_trust()
    trust_b = lattice.get_trust(model_b_name).overall_trust()

    rows = []
    for nk, mean_d, max_d, pct, shape in selected:
        equivocation = "DETECTED" if mean_d > 0.05 else "none"
        invalid_delta = "YES" if max_d > 1.0 else "no"
        rows.append(
            f"| `{nk}` | {shape} | {mean_d:.6f} | {max_d:.6f} | "
            f"{pct:.1f}% | {equivocation} | {invalid_delta} |"
        )

    header = (
        f"## Conflict Analysis\n\n"
        f"**Models:** {model_a_name} vs {model_b_name} | "
        f"**Layers analyzed:** {len(conflicts)} | **Clock:** t={clock.logical_time}\n\n"
        f"### Trust Degradation\n\n"
        f"| Source | Base Trust | Conflict Penalty | Effective Trust |\n|---|---|---|---|\n"
        f"| {model_a_name} | {trust_a:.4f} | "
        f"{len([c for c in conflicts if c[1] > 0.05]) * 0.01:.4f} | "
        f"{max(0, trust_a - len([c for c in conflicts if c[1] > 0.05]) * 0.01):.4f} |\n"
        f"| {model_b_name} | {trust_b:.4f} | "
        f"{len([c for c in conflicts if c[1] > 0.05]) * 0.01:.4f} | "
        f"{max(0, trust_b - len([c for c in conflicts if c[1] > 0.05]) * 0.01):.4f} |\n\n"
        f"### Top Conflict Zones\n\n"
        f"| Layer | Shape | Mean Div | Max Div | Conflict % | Equivocation | Invalid Delta |\n"
        f"|---|---|---|---|---|---|---|\n"
    )
    return header + "\n".join(rows)


# -- Tab 3: Core Primitives --

def run_core_primitives(model_name):
    repo = MODELS[model_name]
    tensors = _load_tensors(repo)
    keys = sorted(tensors.keys())[:5]

    sections = []

    # VectorClock
    vc = VectorClock()
    vc = vc.increment("A")
    vc = vc.increment("A")
    vc_b = VectorClock()
    vc_b = vc_b.increment("B")
    sections.append(
        f"## VectorClock\n\n"
        f"```\n"
        f"Clock A after 2 increments: {vc.to_dict()}\n"
        f"Clock B after 1 increment:  {vc_b.to_dict()}\n"
        f"```\n"
    )

    # MerkleTree
    mt = MerkleTree()
    for k in keys[:3]:
        mt.insert(k, {"data": tensors[k].tobytes()[:1024]})
    sections.append(
        f"## MerkleTree\n\n"
        f"Inserted {3} leaves from real model weights.\n\n"
        f"```\nRoot hash: {mt.root_hash}\n```\n"
    )

    # CausalTrustClock
    clock = CausalTrustClock(peer_id="demo_peer")
    times = []
    for _ in range(5):
        clock = clock.increment()
        times.append(clock.logical_time)
    sections.append(
        f"## CausalTrustClock\n\n"
        f"Peer: `demo_peer` | 5 ticks\n\n"
        f"```\nLogical times: {times}\n```\n"
    )

    # TrustBoundMerkle
    tbm = TrustBoundMerkle()
    provenance_rows = []
    for k in keys[:5]:
        data = tensors[k].tobytes()[:2048]
        tbm.insert_leaf(k, data, "model_source")
        provenance_rows.append(f"| `{k}` | {len(data)} bytes | model_source |")
    tbm.recompute()
    sections.append(
        f"## TrustBoundMerkle\n\n"
        f"Inserted 5 leaves from `{model_name}` real weights.\n\n"
        f"| Key | Data Size | Originator |\n|---|---|---|\n"
        + "\n".join(provenance_rows)
        + f"\n\n```\nProvenance root: {tbm.root_hash}\n```\n"
    )

    # TypedTrustScore
    full = TypedTrustScore.full_trust()
    prob = TypedTrustScore.probationary()
    sections.append(
        f"## TypedTrustScore\n\n"
        f"| Score Type | Value |\n|---|---|\n"
        f"| full_trust | {full.overall_trust():.4f} |\n"
        f"| probationary | {prob.overall_trust():.4f} |\n"
    )

    return "\n---\n\n".join(sections)


# -- Build UI --

STRATEGIES = ["slerp", "lerp", "stock", "majority_vote", "median",
              "task_arithmetic", "ties", "dare"]

with gr.Blocks(css=CUSTOM_CSS, theme=gr.themes.Base()) as demo:
    gr.Markdown("# crdt-merge Data Playground\n\nReal model merges with E4 trust instrumentation.")

    with gr.Tab("Dataset Merge"):
        with gr.Row():
            dd_a = gr.Dropdown(choices=list(MODELS.keys()), value="GPT-2 (124M)", label="Model A")
            dd_b = gr.Dropdown(choices=list(MODELS.keys()), value="DistilGPT-2 (82M)", label="Model B")
        with gr.Row():
            dd_strat = gr.Dropdown(choices=STRATEGIES, value="slerp", label="Strategy")
            sl_layers = gr.Slider(minimum=1, maximum=20, value=5, step=1, label="Layers to merge")
        btn_merge = gr.Button("Run Merge")
        out_merge = gr.Markdown()
        btn_merge.click(run_dataset_merge, [dd_a, dd_b, dd_strat, sl_layers], out_merge)

    with gr.Tab("Conflict Analysis"):
        with gr.Row():
            ca_a = gr.Dropdown(choices=list(MODELS.keys()), value="GPT-2 (124M)", label="Model A")
            ca_b = gr.Dropdown(choices=list(MODELS.keys()), value="DistilGPT-2 (82M)", label="Model B")
        ca_top = gr.Slider(minimum=5, maximum=50, value=15, step=1, label="Top N conflicts")
        btn_conf = gr.Button("Analyze Conflicts")
        out_conf = gr.Markdown()
        btn_conf.click(run_conflict_analysis, [ca_a, ca_b, ca_top], out_conf)

    with gr.Tab("Core Primitives"):
        cp_model = gr.Dropdown(choices=list(MODELS.keys()), value="GPT-2 (124M)", label="Model")
        btn_prim = gr.Button("Run Primitives")
        out_prim = gr.Markdown()
        btn_prim.click(run_core_primitives, [cp_model], out_prim)

if __name__ == "__main__":
    demo.launch()
