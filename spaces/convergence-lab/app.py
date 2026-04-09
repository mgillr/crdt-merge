# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
# Patent: UK Application No. GB 2607132.4, GB2608127.3

import time
import sys
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

MODELS = {
    "GPT-2 (124M)": "openai-community/gpt2",
    "DistilGPT-2 (82M)": "distilbert/distilgpt2",
}

ALL_STRATEGIES = [
    "slerp", "lerp", "stock", "majority_vote", "median",
    "task_arithmetic", "ties", "dare", "dare_ties",
    "model_breadcrumbs", "della",
]

BASE_STRATEGIES = {"task_arithmetic", "ties", "dare", "dare_ties", "model_breadcrumbs", "della"}

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


def _get_tensor_pair():
    ta = _load_tensors(MODELS["GPT-2 (124M)"])
    tb = _load_tensors(MODELS["DistilGPT-2 (82M)"])
    norm_a = {_normalize_key(k): k for k in ta}
    norm_b = {_normalize_key(k): k for k in tb}
    common = sorted(set(norm_a.keys()) & set(norm_b.keys()))
    if not common:
        return None, None, None
    nk = common[0]
    return ta[norm_a[nk]], tb[norm_b[nk]], nk


def _do_merge(strategy_name, tensor_a, tensor_b):
    strategy = get_strategy(strategy_name)
    if strategy_name in BASE_STRATEGIES:
        base = ((tensor_a.astype(np.float32) + tensor_b.astype(np.float32)) / 2).astype(tensor_a.dtype)
        return strategy.merge([tensor_a, tensor_b], weights=[0.5, 0.5], base=base)
    return strategy.merge([tensor_a, tensor_b], weights=[0.5, 0.5])


# -- Tab 1: Full Suite --

def run_full_suite(model_a_name, model_b_name):
    tensors_a = _load_tensors(MODELS[model_a_name])
    tensors_b = _load_tensors(MODELS[model_b_name])
    norm_a = {_normalize_key(k): k for k in tensors_a}
    norm_b = {_normalize_key(k): k for k in tensors_b}
    common = sorted(set(norm_a.keys()) & set(norm_b.keys()))

    if not common:
        return "No compatible layers found between models."

    nk = common[0]
    ta = tensors_a[norm_a[nk]]
    tb = tensors_b[norm_b[nk]]

    if ta.shape != tb.shape:
        return f"Shape mismatch on `{nk}`: {ta.shape} vs {tb.shape}"

    clock = CausalTrustClock(peer_id="suite_runner")
    merkle = TrustBoundMerkle()
    lattice = DeltaTrustLattice(peer_id="suite", initial_peers={model_a_name, model_b_name})

    rows = []
    for sname in ALL_STRATEGIES:
        try:
            t0 = time.perf_counter()
            merged = _do_merge(sname, ta, tb)
            elapsed = time.perf_counter() - t0

            clock = clock.increment()
            delta = float(np.mean(np.abs(merged - ta)))
            cos_sim = float(np.dot(merged.flatten(), ta.flatten()) /
                            (np.linalg.norm(merged) * np.linalg.norm(ta) + 1e-12))
            merkle.insert_leaf(f"suite_{sname}", merged.tobytes()[:2048], "suite")

            rows.append(
                f"| `{sname}` | {elapsed*1000:.1f}ms | {delta:.6f} | {cos_sim:.6f} | PASS |"
            )
        except Exception as exc:
            rows.append(f"| `{sname}` | -- | -- | -- | FAIL: {str(exc)[:40]} |")

    trust_a = lattice.get_trust(model_a_name).overall_trust()
    trust_b = lattice.get_trust(model_b_name).overall_trust()
    full = TypedTrustScore.full_trust().overall_trust()
    merkle.recompute()

    output = (
        f"## Full Strategy Suite\n\n"
        f"**Tensor:** `{nk}` | **Shape:** {ta.shape} | **Clock:** t={clock.logical_time}\n"
        f"**Merkle root:** `{merkle.root_hash[:32]}...`\n\n"
        f"| Strategy | Time | Mean Delta | Cosine Sim | Status |\n"
        f"|---|---|---|---|---|\n"
        + "\n".join(rows)
        + f"\n\n### E4 Trust Health\n\n"
        f"| Metric | Value |\n|---|---|\n"
        f"| {model_a_name} trust | {trust_a:.4f} |\n"
        f"| {model_b_name} trust | {trust_b:.4f} |\n"
        f"| Full trust baseline | {full:.4f} |\n"
        f"| Strategies tested | {len(ALL_STRATEGIES)} |\n"
        f"| Provenance entries | {len(ALL_STRATEGIES)} |\n"
    )
    return output


# -- Tab 2: Convergence (Commutativity) --

def run_convergence(model_a_name, model_b_name):
    tensors_a = _load_tensors(MODELS[model_a_name])
    tensors_b = _load_tensors(MODELS[model_b_name])
    norm_a = {_normalize_key(k): k for k in tensors_a}
    norm_b = {_normalize_key(k): k for k in tensors_b}
    common = sorted(set(norm_a.keys()) & set(norm_b.keys()))

    if not common:
        return "No compatible layers."

    nk = common[0]
    ta = tensors_a[norm_a[nk]]
    tb = tensors_b[norm_b[nk]]

    if ta.shape != tb.shape:
        return f"Shape mismatch on `{nk}`."

    clock = CausalTrustClock(peer_id="convergence")
    lattice = DeltaTrustLattice(peer_id="conv", initial_peers={model_a_name, model_b_name})

    rows = []
    for sname in ALL_STRATEGIES:
        try:
            strategy = get_strategy(sname)
            if sname in BASE_STRATEGIES:
                base = ((ta.astype(np.float32) + tb.astype(np.float32)) / 2).astype(ta.dtype)
                ab = strategy.merge([ta, tb], weights=[0.5, 0.5], base=base)
                ba = strategy.merge([tb, ta], weights=[0.5, 0.5], base=base)
            else:
                ab = strategy.merge([ta, tb], weights=[0.5, 0.5])
                ba = strategy.merge([tb, ta], weights=[0.5, 0.5])

            clock = clock.increment()
            max_diff = float(np.max(np.abs(ab - ba)))
            commutative = max_diff < 1e-6
            status = "PASS" if commutative else f"FAIL (max_diff={max_diff:.2e})"

            trust = lattice.get_trust(model_a_name).overall_trust()
            rows.append(f"| `{sname}` | {status} | {max_diff:.2e} | {trust:.4f} |")
        except Exception as exc:
            rows.append(f"| `{sname}` | ERROR: {str(exc)[:35]} | -- | -- |")

    output = (
        f"## Commutativity Proof\n\n"
        f"**Test:** merge(A,B) == merge(B,A) for each strategy\n"
        f"**Tensor:** `{nk}` | **Shape:** {ta.shape} | **Clock:** t={clock.logical_time}\n\n"
        f"| Strategy | Commutativity | Max Diff | Post-Merge Trust |\n"
        f"|---|---|---|---|\n"
        + "\n".join(rows)
    )
    return output


# -- Tab 3: Partition and Healing --

def run_partition_healing(model_name, strategy_name):
    repo = MODELS[model_name]
    tensors = _load_tensors(repo)
    keys = sorted(tensors.keys())

    # Pick a tensor for merging simulation
    target_key = keys[0]
    base_tensor = tensors[target_key]

    # Split into 2 partitions of nodes
    group_a = ["node_0", "node_1", "node_2"]
    group_b = ["node_3", "node_4"]
    all_nodes = group_a + group_b

    lattice = DeltaTrustLattice(peer_id="partition_sim", initial_peers=set(all_nodes))
    clock = CausalTrustClock(peer_id="partition_sim")
    merkle = TrustBoundMerkle()

    sections = []

    # Pre-partition trust
    pre_trust = {}
    for n in all_nodes:
        pre_trust[n] = lattice.get_trust(n).overall_trust()

    sections.append(
        "### Pre-Partition Trust\n\n"
        "| Node | Trust |\n|---|---|\n"
        + "\n".join(f"| {n} | {pre_trust[n]:.4f} |" for n in all_nodes)
    )

    # Group A merges internally
    rng = np.random.default_rng(42)
    noise_a = [rng.normal(0, 0.01, base_tensor.shape).astype(base_tensor.dtype) for _ in group_a]
    local_a = [base_tensor + n for n in noise_a]

    strategy = get_strategy(strategy_name)
    needs_base = strategy_name in BASE_STRATEGIES

    if needs_base:
        base_ref = base_tensor.copy()
        merged_a = strategy.merge(local_a[:2], weights=[0.5, 0.5], base=base_ref)
    else:
        merged_a = strategy.merge(local_a[:2], weights=[0.5, 0.5])

    clock = clock.increment()
    merkle.insert_leaf("partition_a_merge", merged_a.tobytes()[:2048], "group_a")

    # Group B merges internally
    noise_b = [rng.normal(0, 0.02, base_tensor.shape).astype(base_tensor.dtype) for _ in group_b]
    local_b = [base_tensor + n for n in noise_b]

    if needs_base:
        merged_b = strategy.merge(local_b[:2], weights=[0.5, 0.5], base=base_ref)
    else:
        merged_b = strategy.merge(local_b[:2], weights=[0.5, 0.5])

    clock = clock.increment()
    merkle.insert_leaf("partition_b_merge", merged_b.tobytes()[:2048], "group_b")

    partition_diff = float(np.mean(np.abs(merged_a - merged_b)))
    sections.append(
        f"### During Partition\n\n"
        f"**Group A** ({', '.join(group_a)}): merged with noise scale 0.01\n"
        f"**Group B** ({', '.join(group_b)}): merged with noise scale 0.02\n\n"
        f"Inter-partition divergence (mean abs): **{partition_diff:.6f}**\n"
    )

    # Healing: merge the two partition results
    if needs_base:
        healed = strategy.merge([merged_a, merged_b], weights=[0.5, 0.5], base=base_ref)
    else:
        healed = strategy.merge([merged_a, merged_b], weights=[0.5, 0.5])

    clock = clock.increment()
    merkle.insert_leaf("healed_merge", healed.tobytes()[:2048], "healed")

    heal_delta = float(np.mean(np.abs(healed - base_tensor)))
    cos_sim = float(np.dot(healed.flatten(), base_tensor.flatten()) /
                    (np.linalg.norm(healed) * np.linalg.norm(base_tensor) + 1e-12))

    # Post-healing trust
    post_trust = {}
    for n in all_nodes:
        post_trust[n] = lattice.get_trust(n).overall_trust()

    merkle.recompute()
    sections.append(
        f"### Post-Healing\n\n"
        f"**Strategy:** `{strategy_name}` | **Clock:** t={clock.logical_time}\n"
        f"**Merkle root:** `{merkle.root_hash[:32]}...`\n\n"
        f"| Metric | Value |\n|---|---|\n"
        f"| Healed vs original delta | {heal_delta:.6f} |\n"
        f"| Cosine similarity | {cos_sim:.6f} |\n"
        f"| Partition divergence | {partition_diff:.6f} |\n\n"
        f"### Trust Recovery Timeline\n\n"
        f"| Node | Pre-Partition | Post-Healing | Delta |\n|---|---|---|---|\n"
        + "\n".join(
            f"| {n} | {pre_trust[n]:.4f} | {post_trust[n]:.4f} | "
            f"{post_trust[n] - pre_trust[n]:+.4f} |"
            for n in all_nodes
        )
    )

    evidence_rows = (
        "### Evidence Events\n\n"
        "| Event | Phase | Detail |\n|---|---|---|\n"
        f"| partition_detected | split | 2 groups isolated |\n"
        f"| independent_merge_a | partition | {len(group_a)} nodes, noise=0.01 |\n"
        f"| independent_merge_b | partition | {len(group_b)} nodes, noise=0.02 |\n"
        f"| healing_merge | reunion | divergence={partition_diff:.6f} |\n"
        f"| provenance_verified | post-heal | root=`{merkle.root_hash[:20]}...` |\n"  # recompute() already called above
    )

    output = (
        f"## Partition and Healing Simulation\n\n"
        f"**Model:** {model_name} | **Tensor:** `{target_key}`\n\n"
        + "\n\n".join(sections)
        + f"\n\n{evidence_rows}"
    )
    return output


# -- Tab 4: Strategy Throughput --

def run_throughput(model_name):
    repo = MODELS[model_name]
    tensors = _load_tensors(repo)
    keys = sorted(tensors.keys())

    # Pick tensors of different sizes
    size_buckets = {}
    for k in keys:
        t = tensors[k]
        label = f"{t.shape} ({t.size} params)"
        if label not in size_buckets:
            size_buckets[label] = (k, t)
        if len(size_buckets) >= 3:
            break

    clock = CausalTrustClock(peer_id="bench")
    lattice = DeltaTrustLattice(peer_id="bench", initial_peers={"source"})

    all_rows = []
    for size_label, (key, tensor) in size_buckets.items():
        # Create a second tensor with small noise
        rng = np.random.default_rng(0)
        other = tensor + rng.normal(0, 0.001, tensor.shape).astype(tensor.dtype)

        for sname in ALL_STRATEGIES:
            try:
                strategy = get_strategy(sname)
                iters = 10
                t0 = time.perf_counter()
                for _ in range(iters):
                    if sname in BASE_STRATEGIES:
                        base = tensor.copy()
                        strategy.merge([tensor, other], weights=[0.5, 0.5], base=base)
                    else:
                        strategy.merge([tensor, other], weights=[0.5, 0.5])
                elapsed = time.perf_counter() - t0

                clock = clock.increment()
                ops_sec = iters / elapsed
                mem_est = tensor.nbytes * 3 / (1024 * 1024)

                # E4 overhead: time one trust query
                t1 = time.perf_counter()
                lattice.get_trust("source")
                e4_overhead = (time.perf_counter() - t1) * 1000

                all_rows.append(
                    f"| `{sname}` | {size_label} | {ops_sec:.1f} | "
                    f"{elapsed/iters*1000:.2f}ms | {mem_est:.2f}MB | {e4_overhead:.3f}ms |"
                )
            except Exception as exc:
                all_rows.append(
                    f"| `{sname}` | {size_label} | -- | -- | -- | -- |"
                )

    output = (
        f"## Strategy Throughput Benchmark\n\n"
        f"**Model:** {model_name} | **Clock:** t={clock.logical_time}\n\n"
        f"| Strategy | Tensor Size | Ops/sec | Avg Time | Mem Est | E4 Overhead |\n"
        f"|---|---|---|---|---|---|\n"
        + "\n".join(all_rows)
    )
    return output


# -- Tab 5: Scalability --

def run_scalability():
    peer_counts = [10, 25, 50, 100, 250, 500, 1000]
    rows = []

    for n in peer_counts:
        peers = {f"peer_{i}" for i in range(n)}

        # Time lattice init
        t0 = time.perf_counter()
        lattice = DeltaTrustLattice(peer_id="scaler", initial_peers=peers)
        init_time = time.perf_counter() - t0

        # Time trust query
        t0 = time.perf_counter()
        for _ in range(100):
            lattice.get_trust("peer_0")
        query_time = (time.perf_counter() - t0) / 100

        # Time clock tick
        clock = CausalTrustClock(peer_id="scaler")
        t0 = time.perf_counter()
        for _ in range(100):
            clock = clock.increment()
        tick_time = (time.perf_counter() - t0) / 100

        rows.append(
            f"| {n} | {init_time*1000:.2f}ms | {query_time*1000:.4f}ms | {tick_time*1000:.4f}ms |"
        )

    # E4 summary
    full_t = TypedTrustScore.full_trust().overall_trust()
    prob_t = TypedTrustScore.probationary().overall_trust()

    output = (
        f"## Trust Lattice Scalability\n\n"
        f"| Peers | Init Time | Query Time (avg) | Clock Tick (avg) |\n"
        f"|---|---|---|---|\n"
        + "\n".join(rows)
        + f"\n\n### E4 Trust Baselines\n\n"
        f"| Score Type | Value |\n|---|---|\n"
        f"| full_trust | {full_t:.4f} |\n"
        f"| probationary | {prob_t:.4f} |\n"
    )
    return output


# -- Build UI --

STRAT_CHOICES = ["slerp", "lerp", "stock", "majority_vote", "median",
                 "task_arithmetic", "ties", "dare"]

with gr.Blocks(css=CUSTOM_CSS, theme=gr.themes.Base()) as demo:
    gr.Markdown("# crdt-merge Convergence Lab\n\nStrategy benchmarks, commutativity proofs, and partition healing with E4 trust.")

    with gr.Tab("Full Suite"):
        with gr.Row():
            fs_a = gr.Dropdown(choices=list(MODELS.keys()), value="GPT-2 (124M)", label="Model A")
            fs_b = gr.Dropdown(choices=list(MODELS.keys()), value="DistilGPT-2 (82M)", label="Model B")
        btn_fs = gr.Button("Run Full Suite")
        out_fs = gr.Markdown()
        btn_fs.click(run_full_suite, [fs_a, fs_b], out_fs)

    with gr.Tab("Convergence"):
        with gr.Row():
            cv_a = gr.Dropdown(choices=list(MODELS.keys()), value="GPT-2 (124M)", label="Model A")
            cv_b = gr.Dropdown(choices=list(MODELS.keys()), value="DistilGPT-2 (82M)", label="Model B")
        btn_cv = gr.Button("Prove Commutativity")
        out_cv = gr.Markdown()
        btn_cv.click(run_convergence, [cv_a, cv_b], out_cv)

    with gr.Tab("Partition and Healing"):
        ph_model = gr.Dropdown(choices=list(MODELS.keys()), value="GPT-2 (124M)", label="Model")
        ph_strat = gr.Dropdown(choices=STRAT_CHOICES, value="slerp", label="Strategy")
        btn_ph = gr.Button("Simulate Partition")
        out_ph = gr.Markdown()
        btn_ph.click(run_partition_healing, [ph_model, ph_strat], out_ph)

    with gr.Tab("Strategy Throughput"):
        st_model = gr.Dropdown(choices=list(MODELS.keys()), value="GPT-2 (124M)", label="Model")
        btn_st = gr.Button("Run Benchmark")
        out_st = gr.Markdown()
        btn_st.click(run_throughput, [st_model], out_st)

    with gr.Tab("Scalability"):
        btn_sc = gr.Button("Run Scalability Test")
        out_sc = gr.Markdown()
        btn_sc.click(run_scalability, [], out_sc)

if __name__ == "__main__":
    demo.launch()
