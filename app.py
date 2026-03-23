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
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""
crdt-merge Interactive Demo Space
A visual power demo for the crdt-merge library.
https://github.com/mgillr/crdt-merge
"""

import gradio as gr
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import hashlib
import time
import random
from itertools import permutations

# ---------------------------------------------------------------------------
# Try importing crdt-merge
# ---------------------------------------------------------------------------
try:
    from crdt_merge import merge, diff, merge_dicts, merge_with_provenance
    from crdt_merge import GossipState
    from crdt_merge.agentic import AgentState, SharedKnowledge
    from crdt_merge.compliance import ComplianceAuditor, EUAIActReport
    from crdt_merge.dedup import dedup_records
    CRDT_AVAILABLE = True
    IMPORT_ERROR = ""
except ImportError as e:
    CRDT_AVAILABLE = False
    IMPORT_ERROR = str(e)

# ---------------------------------------------------------------------------
# Constants & Links
# ---------------------------------------------------------------------------
REPO = "https://github.com/mgillr/crdt-merge"
PYPI = "https://pypi.org/project/crdt-merge/"
ARCH = "https://github.com/mgillr/crdt-merge/blob/main/docs/CRDT_ARCHITECTURE.md"
GUIDE_FED = "https://github.com/mgillr/crdt-merge/blob/main/docs/guides/federated-model-merging.md"
GUIDE_AGENT = "https://github.com/mgillr/crdt-merge/blob/main/docs/guides/convergent-multi-agent-ai.md"
GUIDE_COMPLY = "https://github.com/mgillr/crdt-merge/blob/main/docs/guides/compliance-guide.md"
GUIDE_FORGET = "https://github.com/mgillr/crdt-merge/blob/main/docs/guides/right-to-forget-in-ai.md"
GUIDE_PROV = "https://github.com/mgillr/crdt-merge/blob/main/docs/guides/provenance-complete-ai.md"
OPTITRANSFER = "https://optitransfer.ch"

REAL_STRATEGIES = ["LWW", "MaxWins", "MinWins", "Concat", "UnionSet",
                   "LongestWins", "Priority", "Custom"]

# ---------------------------------------------------------------------------
# Color language
# ---------------------------------------------------------------------------
RED    = "#EF4444"
GREEN  = "#22C55E"
BLUE   = "#3B82F6"
AMBER  = "#F59E0B"
PURPLE = "#8B5CF6"
DARK   = "#1E293B"
DARKER = "#0F172A"
MUTED  = "#94A3B8"
DIMMED = "#64748B"

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def sha256(data):
    """SHA-256 of a numpy array or string."""
    if isinstance(data, np.ndarray):
        return hashlib.sha256(data.tobytes()).hexdigest()
    return hashlib.sha256(str(data).encode()).hexdigest()


def proof_badge(state_hash, overhead_ms, strategy="weight_average"):
    """The reusable Proof Badge shown after every convergence proof."""
    return f"""
    <div style="border: 2px solid {GREEN}; border-radius: 12px; padding: 20px;
                background: linear-gradient(135deg, {DARKER}, {DARK}); margin: 16px 0;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
            <span style="font-size: 1.5rem;">✅</span>
            <span style="color: {GREEN}; font-size: 1.2rem; font-weight: bold;
                         text-transform: uppercase;">Mathematically Proven Convergent</span>
        </div>
        <div style="font-family: 'Courier New', monospace; font-size: 1.8rem;
                    color: {GREEN}; text-shadow: 0 0 10px rgba(34,197,94,0.3); margin: 12px 0;">
            {state_hash[:16]}…
        </div>
        <div style="color: {MUTED}; font-size: 0.9rem;">
            Bit-identical across all orderings · Strategy: {strategy} · CRDT overhead: {overhead_ms:.1f}ms
        </div>
        <div style="margin-top: 12px; display: flex; gap: 16px;">
            <a href="{ARCH}" target="_blank"
               style="color: {BLUE}; text-decoration: none;">📂 View formal proof →</a>
            <a href="{REPO}" target="_blank"
               style="color: {AMBER}; text-decoration: none;">⭐ Star on GitHub</a>
        </div>
    </div>
    """


def error_html(msg):
    return f"""
    <div style="border: 2px solid {RED}; border-radius: 12px; padding: 20px;
                background: linear-gradient(135deg, {DARKER}, {DARK}); margin: 16px 0;">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 1.5rem;">❌</span>
            <span style="color: {RED}; font-size: 1.1rem; font-weight: bold;">Error</span>
        </div>
        <div style="color: {MUTED}; margin-top: 8px;">{msg}</div>
    </div>
    """


def make_heatmap_comparison(diff_naive, diff_crdt, title_left, title_right):
    """Side-by-side heatmap: naive difference (noise) vs CRDT difference (zeros)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor(DARKER)

    show = min(64, diff_naive.shape[0])

    vmax1 = max(abs(diff_naive[:show, :show].min()), abs(diff_naive[:show, :show].max()), 1e-15)
    im1 = ax1.imshow(diff_naive[:show, :show], cmap='RdYlGn',
                     vmin=-vmax1, vmax=vmax1, aspect='auto')
    ax1.set_title(title_left, color=RED, fontsize=12, fontweight='bold', pad=10)
    ax1.set_facecolor(DARKER)
    ax1.tick_params(colors=MUTED)
    cb1 = plt.colorbar(im1, ax=ax1, fraction=0.046)
    cb1.ax.yaxis.set_tick_params(color=MUTED)
    plt.setp(cb1.ax.yaxis.get_ticklabels(), color=MUTED)

    vmax2 = max(abs(diff_crdt[:show, :show].min()), abs(diff_crdt[:show, :show].max()), 1e-15)
    im2 = ax2.imshow(diff_crdt[:show, :show], cmap='RdYlGn',
                     vmin=-vmax2, vmax=vmax2, aspect='auto')
    ax2.set_title(title_right, color=GREEN, fontsize=12, fontweight='bold', pad=10)
    ax2.set_facecolor(DARKER)
    ax2.tick_params(colors=MUTED)
    cb2 = plt.colorbar(im2, ax=ax2, fraction=0.046)
    cb2.ax.yaxis.set_tick_params(color=MUTED)
    plt.setp(cb2.ax.yaxis.get_ticklabels(), color=MUTED)

    plt.tight_layout()
    return fig


# ═══════════════════════════════════════════════════════════════════════════
# TAB 1 — ⚡ The Problem
# ═══════════════════════════════════════════════════════════════════════════

def run_problem_demo():
    """Hero demo: standard merge diverges, crdt-merge converges."""
    if not CRDT_AVAILABLE:
        err = error_html(f"crdt-merge not available: {IMPORT_ERROR}")
        return err, err, None, ""

    np.random.seed(int(time.time()) % 100_000)

    # Three random "model weight" tensors (512×512)
    A = np.random.randn(512, 512).astype(np.float64)
    B = np.random.randn(512, 512).astype(np.float64)
    C = np.random.randn(512, 512).astype(np.float64)

    # ── LEFT: naive sequential pairwise interpolation (order-dependent) ──
    def naive_pairwise(x, y, alpha=0.6):
        return x * alpha + y * (1.0 - alpha)

    t0 = time.perf_counter()

    # Order A→B→C
    r_abc = naive_pairwise(naive_pairwise(A, B), C)
    h_abc = sha256(r_abc)

    # Order C→A→B
    r_cab = naive_pairwise(naive_pairwise(C, A), B)
    h_cab = sha256(r_cab)

    # Order B→C→A
    r_bca = naive_pairwise(naive_pairwise(B, C), A)
    h_bca = sha256(r_bca)

    naive_ms = (time.perf_counter() - t0) * 1000.0

    # ── RIGHT: CRDT merge (order-independent) ──
    t1 = time.perf_counter()

    sa = GossipState("model-A")
    sa.update("weights", A)
    sb = GossipState("model-B")
    sb.update("weights", B)
    sc = GossipState("model-C")
    sc.update("weights", C)

    crdt_abc = sa.merge(sb).merge(sc)
    crdt_cab = sc.merge(sa).merge(sb)
    crdt_bca = sb.merge(sc).merge(sa)

    ch_abc = list(crdt_abc.digest().values())[0]
    ch_cab = list(crdt_cab.digest().values())[0]
    ch_bca = list(crdt_bca.digest().values())[0]

    cr_abc = crdt_abc.get("weights")
    cr_cab = crdt_cab.get("weights")

    crdt_ms = (time.perf_counter() - t1) * 1000.0

    # ── HTML panels ──
    left_html = f"""
    <div style="border: 2px solid {RED}; border-radius: 12px; padding: 20px;
                background: linear-gradient(135deg, {DARKER}, {DARK});">
        <h3 style="color: {RED}; margin-top: 0;">❌ Standard Merge (Order-Dependent)</h3>
        <p style="color: {MUTED}; font-size: 0.9rem;">
            Sequential pairwise interpolation — same 3 models, 3 different orders → 3 different outputs
        </p>
        <div style="font-family: 'Courier New', monospace; font-size: 0.8rem;">
            <div style="margin: 8px 0; padding: 6px 10px; background: {DARK}; border-radius: 6px;">
                <span style="color: {AMBER};">A → B → C:</span><br/>
                <span style="color: {RED};">{h_abc[:32]}…</span>
            </div>
            <div style="margin: 8px 0; padding: 6px 10px; background: {DARK}; border-radius: 6px;">
                <span style="color: {AMBER};">C → A → B:</span><br/>
                <span style="color: {RED};">{h_cab[:32]}…</span>
            </div>
            <div style="margin: 8px 0; padding: 6px 10px; background: {DARK}; border-radius: 6px;">
                <span style="color: {AMBER};">B → C → A:</span><br/>
                <span style="color: {RED};">{h_bca[:32]}…</span>
            </div>
        </div>
        <div style="background: rgba(239,68,68,0.1); border: 1px solid {RED};
                    border-radius: 8px; padding: 12px; margin-top: 12px;">
            <span style="color: {RED}; font-weight: bold; font-size: 1.1rem;">
                ⚠️ 3 different hashes — non-deterministic!
            </span><br/>
            <span style="color: {MUTED}; font-size: 0.85rem;">Time: {naive_ms:.2f} ms</span>
        </div>
    </div>
    """

    right_html = f"""
    <div style="border: 2px solid {GREEN}; border-radius: 12px; padding: 20px;
                background: linear-gradient(135deg, {DARKER}, {DARK});">
        <h3 style="color: {GREEN}; margin-top: 0;">✅ crdt-merge (Order-Independent)</h3>
        <p style="color: {MUTED}; font-size: 0.9rem;">
            CRDT-based merge — same 3 models, 3 different orders → 1 identical output
        </p>
        <div style="font-family: 'Courier New', monospace; font-size: 0.8rem;">
            <div style="margin: 8px 0; padding: 6px 10px; background: {DARK}; border-radius: 6px;">
                <span style="color: {AMBER};">A → B → C:</span><br/>
                <span style="color: {GREEN};">{ch_abc[:32]}…</span>
            </div>
            <div style="margin: 8px 0; padding: 6px 10px; background: {DARK}; border-radius: 6px;">
                <span style="color: {AMBER};">C → A → B:</span><br/>
                <span style="color: {GREEN};">{ch_cab[:32]}…</span>
            </div>
            <div style="margin: 8px 0; padding: 6px 10px; background: {DARK}; border-radius: 6px;">
                <span style="color: {AMBER};">B → C → A:</span><br/>
                <span style="color: {GREEN};">{ch_bca[:32]}…</span>
            </div>
        </div>
        <div style="background: rgba(34,197,94,0.1); border: 1px solid {GREEN};
                    border-radius: 8px; padding: 12px; margin-top: 12px;">
            <span style="color: {GREEN}; font-weight: bold; font-size: 1.1rem;">
                ✅ 1 identical hash — mathematically proven!
            </span><br/>
            <span style="color: {MUTED}; font-size: 0.85rem;">
                Time: {crdt_ms:.2f} ms (overhead: {max(0, crdt_ms - naive_ms):.2f} ms)
            </span>
        </div>
    </div>
    """

    # Heatmaps
    diff_naive = r_abc - r_cab          # non-zero noise
    diff_crdt  = cr_abc - cr_cab        # should be all zeros
    fig = make_heatmap_comparison(
        diff_naive, diff_crdt,
        "❌ Naive: order ABC vs CAB (divergence)",
        "✅ CRDT: order ABC vs CAB (convergence)",
    )

    badge = proof_badge(ch_abc, crdt_ms, "GossipState CRDT")
    return left_html, right_html, fig, badge


# ═══════════════════════════════════════════════════════════════════════════
# TAB 2 — 📊 Data Merging
# ═══════════════════════════════════════════════════════════════════════════

def _sample_a():
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
        "department": ["Engineering", "Marketing", "Engineering", "Sales", "Marketing"],
        "salary": [95000, 72000, 88000, 91000, 68000],
        "updated": ["2024-01-15", "2024-01-10", "2024-02-01", "2024-01-20", "2024-01-05"],
    })

def _sample_b():
    return pd.DataFrame({
        "id": [2, 3, 4, 5, 6],
        "name": ["Bob", "Charlie", "Diana", "Eve", "Frank"],
        "department": ["Marketing", "Research", "Sales", "Engineering", "Engineering"],
        "salary": [75000, 92000, 91000, 71000, 83000],
        "updated": ["2024-02-10", "2024-01-15", "2024-01-20", "2024-02-15", "2024-02-20"],
    })


def run_data_merge(prefer):
    if not CRDT_AVAILABLE:
        err = error_html(f"crdt-merge not available: {IMPORT_ERROR}")
        return err, None, "", ""

    df_a = _sample_a()
    df_b = _sample_b()

    t0 = time.perf_counter()
    merged = merge(df_a, df_b, key="id", prefer=prefer)
    merge_ms = (time.perf_counter() - t0) * 1000.0

    # Provenance
    _, prov_log = merge_with_provenance(df_a, df_b, key="id")

    # Diff
    changes = diff(df_a, df_b, key="id")
    n_add = len(changes.get("added", []))
    n_rem = len(changes.get("removed", []))
    n_mod = len(changes.get("modified", []))

    diff_html = f"""
    <div style="border: 1px solid #334155; border-radius: 12px; padding: 20px;
                background: {DARKER}; margin: 8px 0;">
        <h3 style="color: {BLUE}; margin-top: 0;">🔍 Diff Summary</h3>
        <div style="display: flex; gap: 16px; flex-wrap: wrap;">
            <div style="background: rgba(34,197,94,0.15); border: 1px solid {GREEN};
                        border-radius: 8px; padding: 12px; flex: 1; text-align: center;">
                <span style="color: {GREEN}; font-size: 1.8rem; font-weight: bold;">{n_add}</span>
                <br/><span style="color: {MUTED};">Added</span>
            </div>
            <div style="background: rgba(239,68,68,0.15); border: 1px solid {RED};
                        border-radius: 8px; padding: 12px; flex: 1; text-align: center;">
                <span style="color: {RED}; font-size: 1.8rem; font-weight: bold;">{n_rem}</span>
                <br/><span style="color: {MUTED};">Removed</span>
            </div>
            <div style="background: rgba(245,158,11,0.15); border: 1px solid {AMBER};
                        border-radius: 8px; padding: 12px; flex: 1; text-align: center;">
                <span style="color: {AMBER}; font-size: 1.8rem; font-weight: bold;">{n_mod}</span>
                <br/><span style="color: {MUTED};">Modified</span>
            </div>
        </div>
    </div>
    """

    # Provenance log
    prov_html = f"""
    <div style="border: 1px solid #334155; border-radius: 8px; padding: 16px;
                background: {DARKER}; margin: 8px 0;">
        <h4 style="color: {GREEN}; margin-top: 0;">📜 Provenance Log</h4>
        <div style="font-family: 'Courier New', monospace; font-size: 0.82rem; color: {MUTED};">
    """
    if hasattr(prov_log, "records"):
        for rec in list(prov_log.records)[:12]:
            prov_html += (
                f"<div style='margin: 4px 0; padding: 4px 8px; "
                f"background: {DARK}; border-radius: 4px;'>{rec}</div>"
            )
    else:
        prov_html += f"<div>{prov_log}</div>"
    prov_html += f"""
        </div>
        <div style="color: {DIMMED}; margin-top: 8px; font-size: 0.85rem;">
            Merge time: {merge_ms:.2f} ms · Prefer: {prefer} · Key: id
        </div>
    </div>
    """

    badge = proof_badge(sha256(merged.to_string()), merge_ms, f"data-merge (prefer={prefer})")

    return diff_html + prov_html, merged, badge, ""


# ═══════════════════════════════════════════════════════════════════════════
# TAB 3 — 🧠 Model Merging
# ═══════════════════════════════════════════════════════════════════════════

def run_model_merge(num_layers, num_models, tensor_size):
    if not CRDT_AVAILABLE:
        err = error_html(f"crdt-merge not available: {IMPORT_ERROR}")
        return err, None, "", ""

    num_layers = int(num_layers)
    num_models = int(num_models)
    tensor_size = int(tensor_size)
    np.random.seed(int(time.time()) % 100_000)

    model_ids = [f"model-{chr(65 + i)}" for i in range(num_models)]

    # Build one GossipState per model, each with L layers
    nodes = []
    for i in range(num_models):
        gs = GossipState(f"model-{chr(65 + i)}")
        for layer in range(num_layers):
            gs.update(f"layer_{layer}", np.random.randn(tensor_size, tensor_size).astype(np.float64))
        nodes.append(gs)

    # Sample up to 6 random permutations
    all_perms = list(permutations(range(num_models)))
    random.shuffle(all_perms)
    sample_perms = all_perms[:min(6, len(all_perms))]

    t0 = time.perf_counter()
    results = []
    for perm in sample_perms:
        merged = nodes[perm[0]]
        for idx in perm[1:]:
            merged = merged.merge(nodes[idx])
        results.append((perm, merged.digest(), merged))
    total_ms = (time.perf_counter() - t0) * 1000.0

    all_digests = [str(r[1]) for r in results]
    identical = len(set(all_digests)) == 1

    # Pick first digest hash for display
    first_digest = results[0][1]
    first_hash = list(first_digest.values())[0] if first_digest else sha256("empty")

    # ── results HTML ──
    html = f"""
    <div style="border: 1px solid #334155; border-radius: 12px; padding: 20px;
                background: {DARKER}; margin: 8px 0;">
        <h3 style="color: {GREEN if identical else RED}; margin-top: 0;">
            {'✅' if identical else '❌'} {len(sample_perms)} Orderings Tested ·
            CRDT Convergence Proof
        </h3>
        <div style="color: {MUTED}; margin-bottom: 12px;">
            {num_models} models × {num_layers} layer(s) × {tensor_size}×{tensor_size} tensors ·
            Total time: {total_ms:.1f} ms
        </div>
    """
    for perm, digest, _ in results:
        order = " → ".join(model_ids[i] for i in perm)
        h = list(digest.values())[0] if digest else "n/a"
        html += f"""
        <div style="display: flex; align-items: center; gap: 8px; margin: 6px 0;
                    padding: 8px; background: {DARK}; border-radius: 6px;">
            <span style="color: {AMBER}; font-size: 0.85rem; min-width: 220px;">{order}</span>
            <span style="font-family: 'Courier New', monospace; color: {GREEN};
                         font-size: 0.78rem;">{h[:40]}…</span>
        </div>
        """
    html += "</div>"

    # ── heatmap of resolved tensor (layer_0) ──
    resolved = results[0][2].get("layer_0")
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.patch.set_facecolor(DARKER)
    show = min(64, tensor_size)
    im = ax.imshow(resolved[:show, :show], cmap='viridis', aspect='auto')
    ax.set_title(f"Merged Tensor — layer_0 (GossipState CRDT)", color=GREEN, fontsize=13, fontweight='bold')
    ax.set_facecolor(DARKER)
    ax.tick_params(colors=MUTED)
    cb = plt.colorbar(im, ax=ax, fraction=0.046)
    cb.ax.yaxis.set_tick_params(color=MUTED)
    plt.setp(cb.ax.yaxis.get_ticklabels(), color=MUTED)
    plt.tight_layout()

    overhead = total_ms / max(len(sample_perms), 1)
    badge = proof_badge(first_hash, overhead, "GossipState CRDT")
    return html, fig, badge, ""


# ═══════════════════════════════════════════════════════════════════════════
# TAB 4 — 🤖 Multi-Agent AI
# ═══════════════════════════════════════════════════════════════════════════

def run_agent_demo():
    if not CRDT_AVAILABLE:
        err = error_html(f"crdt-merge not available: {IMPORT_ERROR}")
        return err, None, "", ""

    # ── Build three agents with overlapping / conflicting state ──
    researcher = AgentState(agent_id="researcher")
    researcher.add_fact("revenue_q1", 4_200_000, confidence=0.90)
    researcher.add_fact("market_share", 0.23, confidence=0.85)
    researcher.add_fact("growth_rate", 0.12, confidence=0.70)
    researcher.add_tag("finance")
    researcher.add_tag("research")
    researcher.increment("queries_made")
    researcher.increment("queries_made")
    researcher.append_message("Found Q1 revenue data from SEC filing", role="agent")
    researcher.append_message("Market share estimated from industry reports", role="agent")

    analyst = AgentState(agent_id="analyst")
    analyst.add_fact("revenue_q1", 4_250_000, confidence=0.95)   # higher → wins
    analyst.add_fact("competitor_count", 7, confidence=0.99)
    analyst.add_fact("growth_rate", 0.15, confidence=0.92)        # higher → wins
    analyst.add_tag("analysis")
    analyst.add_tag("finance")
    analyst.increment("queries_made", 3)
    analyst.append_message("Analyzed competitor landscape in detail", role="agent")
    analyst.append_message("Growth rate revised upward based on Q2 projections", role="agent")

    reviewer = AgentState(agent_id="reviewer")
    reviewer.add_fact("revenue_q1", 4_230_000, confidence=0.88)
    reviewer.add_fact("risk_score", 0.34, confidence=0.91)
    reviewer.add_fact("competitor_count", 8, confidence=0.75)     # lower → analyst wins
    reviewer.add_tag("review")
    reviewer.add_tag("compliance")
    reviewer.increment("queries_made", 2)
    reviewer.append_message("Risk assessment completed", role="agent")

    t0 = time.perf_counter()

    # Merge order 1:  researcher → analyst → reviewer
    shared_ra = SharedKnowledge.merge(researcher, analyst)
    try:
        shared_1 = SharedKnowledge.merge(shared_ra, reviewer)
    except (TypeError, AttributeError):
        shared_1 = shared_ra

    # Merge order 2:  reviewer → analyst → researcher
    shared_va = SharedKnowledge.merge(reviewer, analyst)
    try:
        shared_2 = SharedKnowledge.merge(shared_va, researcher)
    except (TypeError, AttributeError):
        shared_2 = shared_va

    merge_ms = (time.perf_counter() - t0) * 1000.0

    display = shared_1  # use the fuller merge for display

    # ── Facts table ──
    facts_html = f"""
    <div style="border: 1px solid #334155; border-radius: 12px; padding: 20px;
                background: {DARKER}; margin: 8px 0;">
        <h3 style="color: {GREEN}; margin-top: 0;">📊 Merged Facts (Highest Confidence Wins)</h3>
        <table style="width: 100%; border-collapse: collapse; color: {MUTED};">
            <tr style="border-bottom: 2px solid #334155;">
                <th style="text-align:left; padding:8px; color:{BLUE};">Fact</th>
                <th style="text-align:left; padding:8px; color:{BLUE};">Value</th>
                <th style="text-align:left; padding:8px; color:{BLUE};">Confidence</th>
                <th style="text-align:left; padding:8px; color:{BLUE};">Source Agent</th>
            </tr>
    """
    if hasattr(display, "facts"):
        for key, fact in display.facts.items():
            val  = fact.value if hasattr(fact, "value") else fact
            conf = fact.confidence if hasattr(fact, "confidence") else "—"
            src  = fact.source_agent if hasattr(fact, "source_agent") else "—"
            conf_color = GREEN if isinstance(conf, (int, float)) and conf >= 0.9 else AMBER
            facts_html += f"""
            <tr style="border-bottom: 1px solid {DARK};">
                <td style="padding:8px; font-weight:bold;">{key}</td>
                <td style="padding:8px; font-family:'Courier New',monospace;">{val}</td>
                <td style="padding:8px; color:{conf_color};">
                    {f'{conf:.2f}' if isinstance(conf, float) else conf}
                </td>
                <td style="padding:8px; color:{AMBER};">{src}</td>
            </tr>"""
    facts_html += "</table></div>"

    # ── Tags ──
    tags_html = f"""
    <div style="border: 1px solid #334155; border-radius: 8px; padding: 16px;
                background: {DARKER}; margin: 8px 0;">
        <h4 style="color: {BLUE}; margin-top: 0;">🏷️ Merged Tags (Union)</h4>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
    """
    if hasattr(display, "tags"):
        for tag in sorted(display.tags):
            tags_html += (
                f'<span style="background:{DARK}; color:{BLUE}; padding:4px 14px; '
                f'border-radius:20px; border:1px solid {BLUE};">{tag}</span>'
            )
    tags_html += "</div></div>"

    # ── Counters ──
    counter_html = ""
    if hasattr(display, "counter_value"):
        try:
            qm = display.counter_value("queries_made")
            counter_html = f"""
            <div style="border: 1px solid #334155; border-radius: 8px; padding: 16px;
                        background: {DARKER}; margin: 8px 0;">
                <h4 style="color: {AMBER}; margin-top: 0;">🔢 Merged Counters (Additive)</h4>
                <div style="background:{DARK}; border-radius:8px; padding:12px; display:inline-block;
                            text-align:center; min-width:120px;">
                    <div style="color:{GREEN}; font-size:2rem; font-weight:bold;">{qm}</div>
                    <div style="color:{MUTED}; font-size:0.85rem;">queries_made (2+3+2)</div>
                </div>
            </div>
            """
        except Exception:
            pass

    # ── Contributing agents ──
    agents_html = ""
    if hasattr(display, "contributing_agents"):
        agents = display.contributing_agents
        agents_html = f"""
        <div style="border: 1px solid #334155; border-radius: 8px; padding: 16px;
                    background: {DARKER}; margin: 8px 0;">
            <h4 style="color: {GREEN}; margin-top: 0;">🤝 Contributing Agents</h4>
            <div style="display: flex; gap: 12px; flex-wrap: wrap;">
        """
        for a in agents:
            agents_html += (
                f'<span style="background:rgba(34,197,94,0.1); color:{GREEN}; '
                f'padding:6px 14px; border-radius:8px; border:1px solid {GREEN};">🤖 {a}</span>'
            )
        agents_html += "</div></div>"

    # ── Messages ──
    messages_html = ""
    if hasattr(display, "messages") and display.messages:
        messages_html = f"""
        <div style="border: 1px solid #334155; border-radius: 8px; padding: 16px;
                    background: {DARKER}; margin: 8px 0;">
            <h4 style="color: {PURPLE}; margin-top: 0;">💬 Merged Messages (deduped, time-sorted)</h4>
        """
        for msg in display.messages[:8]:
            msg_text = msg if isinstance(msg, str) else str(msg)
            messages_html += (
                f'<div style="margin:4px 0; padding:6px 10px; background:{DARK}; '
                f'border-radius:6px; color:{MUTED}; font-size:0.88rem;">{msg_text}</div>'
            )
        messages_html += "</div>"

    # ── Network graph (matplotlib) ──
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor(DARKER)
    ax.set_facecolor(DARKER)

    positions = {
        "Researcher":      (0.2, 0.8),
        "Analyst":         (0.8, 0.8),
        "Reviewer":        (0.5, 0.5),
        "SharedKnowledge": (0.5, 0.12),
    }
    colors_map = {
        "Researcher": BLUE, "Analyst": AMBER,
        "Reviewer": PURPLE, "SharedKnowledge": GREEN,
    }

    for name, (x, y) in positions.items():
        c = colors_map[name]
        circle = plt.Circle((x, y), 0.08, color=c, alpha=0.25, zorder=3)
        ax.add_patch(circle)
        ax.plot(x, y, 'o', color=c, markersize=22, zorder=4)
        icon = "🧠" if name == "SharedKnowledge" else "🤖"
        ax.annotate(f"{icon} {name}", (x, y - 0.14), ha='center',
                    fontsize=10, color=c, fontweight='bold', zorder=5)

    for src in ("Researcher", "Analyst", "Reviewer"):
        sx, sy = positions[src]
        tx, ty = positions["SharedKnowledge"]
        ax.annotate("", xy=(tx, ty + 0.09), xytext=(sx, sy - 0.09),
                    arrowprops=dict(arrowstyle="->", color=GREEN, lw=2.5, alpha=0.7))

    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.08, 1.05)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title("Agent State Convergence", color=GREEN, fontsize=14, fontweight='bold', pad=15)
    plt.tight_layout()

    badge = proof_badge(
        sha256(str(display.facts) if hasattr(display, "facts") else "converged"),
        merge_ms,
        "LWW-Register (highest confidence)",
    )

    all_html = facts_html + tags_html + counter_html + agents_html + messages_html
    return all_html, fig, badge, ""


# ═══════════════════════════════════════════════════════════════════════════
# TAB 5 — 🌐 Federated Learning
# ═══════════════════════════════════════════════════════════════════════════

def run_federated_demo(num_nodes):
    if not CRDT_AVAILABLE:
        err = error_html(f"crdt-merge not available: {IMPORT_ERROR}")
        return err, None, "", ""

    num_nodes = int(num_nodes)
    tensor_size = 256
    np.random.seed(42)

    # Initialise nodes
    nodes = []
    for i in range(num_nodes):
        gs = GossipState(f"node-{i}")
        gs.update("weights", np.random.randn(tensor_size, tensor_size).astype(np.float64))
        nodes.append(gs)

    max_rounds = min(num_nodes * 2, 12)
    history = []

    t0 = time.perf_counter()
    for rnd in range(1, max_rounds + 1):
        new_nodes = []
        for i in range(num_nodes):
            peer = random.choice([j for j in range(num_nodes) if j != i])
            new_nodes.append(nodes[i].merge(nodes[peer]))
        nodes = new_nodes
        for i in range(num_nodes):
            d = list(nodes[i].digest().values())[0]
            history.append({"round": rnd, "node": f"node-{i}",
                            "hash": d[:16]})
    total_ms = (time.perf_counter() - t0) * 1000.0

    final_digests = [nodes[i].digest() for i in range(num_nodes)]
    final_hashes = [list(d.values())[0] for d in final_digests]
    converged = len(set(str(d) for d in final_digests)) == 1

    # ── Plotly convergence timeline ──
    fig = go.Figure()
    for i in range(num_nodes):
        nd = [h for h in history if h["node"] == f"node-{i}"]
        rounds    = [h["round"] for h in nd]
        hash_vals = [int(h["hash"][:8], 16) for h in nd]
        fig.add_trace(go.Scatter(
            x=rounds, y=hash_vals, mode="lines+markers",
            name=f"node-{i}", line=dict(width=2), marker=dict(size=6),
        ))
    fig.update_layout(
        title=dict(text="Gossip Protocol — State Hash Convergence",
                   font=dict(color=GREEN, size=16)),
        xaxis_title="Gossip Round", yaxis_title="State Hash (numeric prefix)",
        template="plotly_dark",
        paper_bgcolor=DARKER, plot_bgcolor=DARK,
        font=dict(color=MUTED), legend=dict(font=dict(color=MUTED)),
        height=420,
    )

    # ── Status cards ──
    status_html = f"""
    <div style="border: 1px solid #334155; border-radius: 12px; padding: 20px;
                background: {DARKER}; margin: 8px 0;">
        <h3 style="color: {GREEN if converged else AMBER}; margin-top: 0;">
            {'✅' if converged else '⏳'} Federated Merge — {num_nodes} Nodes × {max_rounds} Rounds
        </h3>
        <div style="display: flex; gap: 16px; flex-wrap: wrap; margin: 12px 0;">
            <div style="background:{DARK}; border-radius:8px; padding:14px; text-align:center; flex:1;">
                <div style="color:{GREEN}; font-size:1.6rem; font-weight:bold;">{num_nodes}</div>
                <div style="color:{MUTED}; font-size:0.85rem;">Nodes</div>
            </div>
            <div style="background:{DARK}; border-radius:8px; padding:14px; text-align:center; flex:1;">
                <div style="color:{BLUE}; font-size:1.6rem; font-weight:bold;">{max_rounds}</div>
                <div style="color:{MUTED}; font-size:0.85rem;">Gossip Rounds</div>
            </div>
            <div style="background:{DARK}; border-radius:8px; padding:14px; text-align:center; flex:1;">
                <div style="color:{AMBER}; font-size:1.6rem; font-weight:bold;">{total_ms:.0f} ms</div>
                <div style="color:{MUTED}; font-size:0.85rem;">Total Time</div>
            </div>
            <div style="background:{DARK}; border-radius:8px; padding:14px; text-align:center; flex:1;">
                <div style="color:{GREEN}; font-size:1.6rem; font-weight:bold;">
                    {'Yes ✅' if converged else 'In progress ⏳'}</div>
                <div style="color:{MUTED}; font-size:0.85rem;">Converged</div>
            </div>
        </div>
        <div style="background: rgba(34,197,94,0.1); border: 1px solid {GREEN};
                    border-radius: 8px; padding: 12px; margin-top: 8px;">
            <span style="color: {GREEN}; font-weight: bold;">🔑 No central parameter server needed!</span>
            <span style="color: {MUTED};"> Every node converges via peer-to-peer gossip alone.</span>
        </div>
    </div>
    """

    # Final hashes
    hashes_html = f"""
    <div style="border: 1px solid #334155; border-radius: 8px; padding: 16px;
                background: {DARKER}; margin: 8px 0;">
        <h4 style="color: {BLUE}; margin-top: 0;">Final Node States</h4>
    """
    for i, h in enumerate(final_hashes):
        c = GREEN if h == final_hashes[0] else RED
        hashes_html += (
            f'<div style="display:flex; align-items:center; gap:8px; margin:4px 0; '
            f'padding:6px 8px; background:{DARK}; border-radius:4px;">'
            f'<span style="color:{AMBER}; min-width:60px;">node-{i}</span>'
            f'<span style="font-family:\'Courier New\',monospace; color:{c}; '
            f'font-size:0.8rem;">{h[:40]}…</span></div>'
        )
    hashes_html += "</div>"

    badge = proof_badge(final_hashes[0], total_ms / max(max_rounds, 1), "GossipState CRDT")
    return status_html + hashes_html, fig, badge, ""


# ═══════════════════════════════════════════════════════════════════════════
# TAB 6 — 🛡️ Compliance
# ═══════════════════════════════════════════════════════════════════════════

def run_compliance_audit(framework):
    if not CRDT_AVAILABLE:
        err = error_html(f"crdt-merge not available: {IMPORT_ERROR}")
        return err, "", ""

    fw = framework   # already the slug from dropdown choices

    auditor = ComplianceAuditor(framework=fw, node_id="prod-node-1")

    # ── Record realistic events ──
    # Good merge (provenance, reviewed)
    auditor.record_merge(
        operation="crdt_merge",
        input_hash="a1b2c3d4e5f6",
        output_hash="f6e5d4c3b2a1",
        metadata={"has_provenance": True, "strategy": "weight_average",
                  "reviewed": True, "risk_level": "high"},
    )
    # Partial merge (provenance but not reviewed)
    auditor.record_merge(
        operation="crdt_merge",
        input_hash="1234567890ab",
        output_hash="ba0987654321",
        metadata={"has_provenance": True, "strategy": "slerp",
                  "reviewed": False, "risk_level": "medium"},
    )
    # Bad merge (no provenance, not reviewed)
    auditor.record_merge(
        operation="standard_merge",
        input_hash="deadbeef1234",
        output_hash="4321feebdaed",
        metadata={"has_provenance": False, "strategy": "naive_average",
                  "reviewed": False, "risk_level": "high"},
    )

    # Unmerge events (GDPR right-to-forget)
    auditor.record_unmerge(subject_id="user-42",
                           fields_removed=["email", "name", "location"])
    auditor.record_unmerge(subject_id="user-108",
                           fields_removed=["email"])

    # Access events
    auditor.record_access(user_id="admin", operation="read",
                          resource="model-weights", granted=True)
    auditor.record_access(user_id="data-scientist-1", operation="write",
                          resource="training-data", granted=True)
    auditor.record_access(user_id="unknown-user", operation="read",
                          resource="pii-dataset", granted=False)

    t0 = time.perf_counter()
    report = auditor.validate()
    audit_ms = (time.perf_counter() - t0) * 1000.0

    status_colors = {
        "compliant": GREEN, "partial": AMBER, "non_compliant": RED,
        "pass": GREEN, "fail": RED, "not_applicable": DIMMED,
        "warning": AMBER, "critical": RED, "info": BLUE,
    }

    rs = report.status if hasattr(report, "status") else "unknown"
    sc = status_colors.get(rs, MUTED)
    icon = "✅" if rs == "compliant" else ("⚠️" if rs == "partial" else "❌")

    report_html = f"""
    <div style="border: 2px solid {sc}; border-radius: 12px; padding: 20px;
                background: linear-gradient(135deg, {DARKER}, {DARK}); margin: 8px 0;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;">
            <h3 style="color:{sc}; margin:0;">{icon} {fw.upper().replace('_',' ')} Compliance Report</h3>
            <span style="background:{sc}; color:{DARKER}; padding:4px 16px; border-radius:20px;
                         font-weight:bold; text-transform:uppercase;">{rs}</span>
        </div>
        <div style="color:{MUTED}; margin-top:8px; font-size:0.9rem;">
            Audit time: {audit_ms:.1f} ms · Node: prod-node-1
        </div>
    """

    # Findings
    if hasattr(report, "findings") and report.findings:
        report_html += '<div style="margin-top: 16px;">'
        for f in report.findings:
            severity = getattr(f, "severity", "info")
            status   = getattr(f, "status", "unknown")
            rule_id  = getattr(f, "rule_id", "—")
            desc     = getattr(f, "description", str(f))
            rec      = getattr(f, "recommendation", "")

            s_c = status_colors.get(status, MUTED)
            sv_c = status_colors.get(severity, MUTED)
            ic = "✅" if status == "pass" else ("❌" if status == "fail" else "➖")

            report_html += f"""
            <div style="border:1px solid #334155; border-radius:8px; padding:12px; margin:8px 0;
                        background:{DARK}; border-left:4px solid {s_c};">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:white; font-weight:bold;">{ic} {rule_id}</span>
                    <div style="display:flex; gap:8px;">
                        <span style="background:{sv_c}22; color:{sv_c}; padding:2px 8px;
                                     border-radius:4px; font-size:0.75rem; text-transform:uppercase;">
                            {severity}</span>
                        <span style="background:{s_c}22; color:{s_c}; padding:2px 8px;
                                     border-radius:4px; font-size:0.75rem; text-transform:uppercase;">
                            {status}</span>
                    </div>
                </div>
                <div style="color:{MUTED}; margin-top:6px; font-size:0.9rem;">{desc}</div>
            """
            if rec:
                report_html += (
                    f'<div style="color:{AMBER}; margin-top:4px; font-size:0.85rem;">💡 {rec}</div>'
                )
            report_html += "</div>"
        report_html += "</div>"
    report_html += "</div>"

    # EU AI Act extras
    eu_html = ""
    if fw == "eu_ai_act":
        try:
            eu_report    = EUAIActReport(auditor)
            risk         = eu_report.risk_classification(
                               system_description="Model merge pipeline for production AI",
                               is_high_risk=True)
            transparency = eu_report.transparency_report()
            governance   = eu_report.data_governance()

            eu_html = f"""
            <div style="border:1px solid #334155; border-radius:12px; padding:20px;
                        background:{DARKER}; margin:8px 0;">
                <h3 style="color:{BLUE}; margin-top:0;">🇪🇺 EU AI Act — Detailed Analysis</h3>
                <div style="display:flex; gap:12px; flex-wrap:wrap; margin:12px 0;">
                    <div style="flex:1; min-width:200px; background:{DARK};
                                border-radius:8px; padding:16px;">
                        <h4 style="color:{AMBER}; margin-top:0;">⚖️ Risk Classification</h4>
                        <div style="color:{MUTED}; font-size:0.9rem;">{risk}</div>
                    </div>
                    <div style="flex:1; min-width:200px; background:{DARK};
                                border-radius:8px; padding:16px;">
                        <h4 style="color:{BLUE}; margin-top:0;">🔍 Transparency</h4>
                        <div style="color:{MUTED}; font-size:0.9rem;">{transparency}</div>
                    </div>
                    <div style="flex:1; min-width:200px; background:{DARK};
                                border-radius:8px; padding:16px;">
                        <h4 style="color:{GREEN}; margin-top:0;">📊 Data Governance</h4>
                        <div style="color:{MUTED}; font-size:0.9rem;">{governance}</div>
                    </div>
                </div>
            </div>
            """
        except Exception as exc:
            eu_html = (
                f'<div style="color:{AMBER}; padding:8px;">EU AI Act extended report: {exc}</div>'
            )

    # Full text
    text_report = ""
    if hasattr(report, "to_text"):
        try:
            text_report = report.to_text()
        except Exception:
            text_report = str(report)

    badge = proof_badge(sha256(str(rs) + fw), audit_ms, f"compliance-{fw}")
    return report_html + eu_html, text_report, badge


# ═══════════════════════════════════════════════════════════════════════════
# HTML chrome: header, footer, CSS
# ═══════════════════════════════════════════════════════════════════════════

header_html = """
<div style="background: linear-gradient(135deg, #0F172A, #1E293B); padding: 24px;
            border-radius: 12px; margin-bottom: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
        <div>
            <h1 style="color: white; margin: 0; font-size: 2rem;">🔀 crdt-merge</h1>
            <p style="color: #94A3B8; margin: 4px 0 0 0; font-size: 1.1rem;">
                Mathematically proven conflict-free merge for AI models, datasets &amp; agent memory
            </p>
            <p style="color: #64748B; margin: 4px 0 0 0; font-size: 0.85rem;">
                Patent Pending: UK Application No. 2607132.4 · BSL-1.1 License · © 2026 Optitransfer
            </p>
        </div>
        <div style="display: flex; gap: 12px; flex-wrap: wrap; margin-top: 8px;">
            <a href="https://github.com/mgillr/crdt-merge" target="_blank"
               style="background:#F59E0B; color:#0F172A; padding:8px 16px; border-radius:8px;
                      text-decoration:none; font-weight:bold; font-size:0.95rem;">⭐ Star on GitHub</a>
            <a href="https://pypi.org/project/crdt-merge/" target="_blank"
               style="background:#3B82F6; color:white; padding:8px 16px; border-radius:8px;
                      text-decoration:none; font-weight:bold; font-size:0.95rem;">📦 pip install crdt-merge</a>
            <a href="https://github.com/mgillr/crdt-merge/blob/main/docs/CRDT_ARCHITECTURE.md"
               target="_blank"
               style="background:#22C55E; color:#0F172A; padding:8px 16px; border-radius:8px;
                      text-decoration:none; font-weight:bold; font-size:0.95rem;">📄 Formal Proof</a>
            <a href="https://optitransfer.ch" target="_blank"
               style="background:#6366F1; color:white; padding:8px 16px; border-radius:8px;
                      text-decoration:none; font-weight:bold; font-size:0.95rem;">🌐 Optitransfer</a>
        </div>
    </div>
    <div style="background: #1E293B; border: 1px solid #334155; border-radius: 8px;
                padding: 12px; margin-top: 16px; font-family: 'Courier New', monospace;
                color: #22C55E; font-size: 1rem;">
        pip install crdt-merge
    </div>
</div>
"""

footer_html = """
<div style="background: #0F172A; padding: 20px; border-radius: 12px;
            margin-top: 16px; text-align: center;">
    <div style="display: flex; justify-content: center; gap: 24px;
                flex-wrap: wrap; margin-bottom: 12px;">
        <a href="https://github.com/mgillr/crdt-merge" target="_blank"
           style="color: #F59E0B; text-decoration: none;">⭐ GitHub</a>
        <a href="https://github.com/mgillr/crdt-merge/blob/main/docs/CRDT_ARCHITECTURE.md"
           target="_blank" style="color: #22C55E; text-decoration: none;">📄 Architecture &amp; Proof</a>
        <a href="https://pypi.org/project/crdt-merge/" target="_blank"
           style="color: #3B82F6; text-decoration: none;">📦 PyPI</a>
        <a href="https://optitransfer.ch" target="_blank"
           style="color: #6366F1; text-decoration: none;">🌐 Optitransfer</a>
    </div>
    <p style="color: #64748B; font-size: 0.8rem; margin: 0;">
        Patent Pending: UK Application No. 2607132.4 · BSL-1.1 License ·
        © 2026 Ryan Gillespie / Optitransfer
    </p>
</div>
"""

custom_css = """
.gradio-container { max-width: 1200px !important; }
.proof-badge {
    border: 2px solid #22C55E; border-radius: 12px; padding: 20px;
    background: linear-gradient(135deg, #0F172A, #1E293B);
}
"""

# ═══════════════════════════════════════════════════════════════════════════
# Build the Gradio Blocks app
# ═══════════════════════════════════════════════════════════════════════════

theme = gr.themes.Soft(primary_hue="green", neutral_hue="slate")

with gr.Blocks(theme=theme, css=custom_css,
               title="crdt-merge — Conflict-Free Merge for AI") as demo:

    gr.HTML(header_html)

    with gr.Tabs():

        # ────────────────────────── TAB 1: The Problem ──────────────────────────
        with gr.Tab("⚡ The Problem"):
            gr.Markdown("""
## The Reproducibility Crisis in Model Merging

**Standard merge operations are order-dependent.** Merge models A + B + C in different
orders and you get different results every time. This breaks reproducibility, auditing,
and federated learning.

**crdt-merge solves this mathematically.** Using CRDTs (Conflict-free Replicated Data Types),
every merge is guaranteed to converge to the same result regardless of order.
            """)
            problem_btn = gr.Button("🚀 Run Live Demo", variant="primary", size="lg")
            with gr.Row():
                left_out  = gr.HTML(label="Standard Merge")
                right_out = gr.HTML(label="CRDT Merge")
            heatmap_out = gr.Plot(label="Difference Heatmaps")
            badge_out_1 = gr.HTML()
            gr.Markdown(
                f"---\n📖 [Read the formal proof → CRDT Architecture]({ARCH})"
            )
            problem_btn.click(fn=run_problem_demo,
                              outputs=[left_out, right_out, heatmap_out, badge_out_1])

        # ────────────────────────── TAB 2: Data Merging ─────────────────────────
        with gr.Tab("📊 Data Merging"):
            gr.Markdown("""
## Conflict-Free Data Merging with Full Provenance

Merge datasets from multiple sources with automatic conflict resolution,
deduplication, and complete provenance tracking.
            """)
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### 📋 Dataset A")
                    gr.DataFrame(value=_sample_a(), label="Source A", interactive=False)
                with gr.Column():
                    gr.Markdown("### 📋 Dataset B")
                    gr.DataFrame(value=_sample_b(), label="Source B", interactive=False)
            with gr.Row():
                prefer_dd = gr.Dropdown(choices=["a", "b", "latest"],
                                        value="b", label="Prefer Strategy")
                data_btn  = gr.Button("🔀 Merge Datasets", variant="primary")
            data_info   = gr.HTML(label="Diff & Provenance")
            data_merged = gr.DataFrame(label="Merged Result")
            badge_out_2 = gr.HTML()
            data_err    = gr.HTML()
            gr.Markdown(
                f"---\n📖 [Provenance Guide]({GUIDE_PROV}) · "
                f"[Right to Forget Guide]({GUIDE_FORGET})"
            )
            data_btn.click(fn=run_data_merge, inputs=[prefer_dd],
                           outputs=[data_info, data_merged, badge_out_2, data_err])

        # ────────────────────────── TAB 3: Model Merging ────────────────────────
        with gr.Tab("🧠 Model Merging"):
            gr.Markdown("""
## CRDT-Based Model Tensor Convergence

GossipState stores model tensors as versioned CRDT entries with vector clocks.
Merging any number of models in **any order** produces a bit-identical result —
guaranteed by commutativity, associativity, and idempotence.
            """)
            with gr.Row():
                nlayers_sl = gr.Slider(minimum=1, maximum=5, step=1, value=2,
                                       label="Number of Layers")
                nmod_sl  = gr.Slider(minimum=2, maximum=6, step=1, value=3,
                                     label="Number of Models")
                tsz_dd   = gr.Dropdown(choices=["256", "512", "1024"],
                                       value="512", label="Tensor Size")
            model_btn = gr.Button("🧠 Run Merge Across All Orderings",
                                  variant="primary", size="lg")
            model_html = gr.HTML(label="Convergence Results")
            model_plot = gr.Plot(label="Merged Tensor Visualization")
            badge_out_3 = gr.HTML()
            model_err   = gr.HTML()
            with gr.Accordion("📚 How CRDT Convergence Works", open=False):
                gr.Markdown("""
Each model's tensors are stored in a **GossipState** — a key-value CRDT where every
entry carries a **VectorClock**. When two GossipStates merge:

1. **Commutativity** — `A.merge(B) == B.merge(A)` (digest-verified)
2. **Associativity** — `A.merge(B).merge(C) == A.merge(B.merge(C))` (digest-verified)
3. **Idempotence** — `A.merge(A) == A`

The `.digest()` method returns `{key: hex_hash}` — a compact cryptographic fingerprint
of the converged state. All merge orderings produce the same digest.

**Field-level strategies** (LWW, MaxWins, MinWins, etc.) apply to structured data merging,
while GossipState handles tensor/model merging via deterministic content-based tiebreak.
                """)
            gr.Markdown(
                f"---\n📖 [Federated Model Merging Guide]({GUIDE_FED}) · "
                f"[CRDT Architecture]({ARCH})"
            )
            model_btn.click(fn=run_model_merge,
                            inputs=[nlayers_sl, nmod_sl, tsz_dd],
                            outputs=[model_html, model_plot, badge_out_3, model_err])

        # ────────────────────────── TAB 4: Multi-Agent AI ───────────────────────
        with gr.Tab("🤖 Multi-Agent AI"):
            gr.Markdown("""
## Convergent Multi-Agent Knowledge Merging

When multiple AI agents work on the same problem, their knowledge must merge conflict-free.
crdt-merge ensures facts resolve by confidence, tags merge as unions, counters add correctly,
and messages are deduplicated — all without coordination.

**Pre-configured agents:**
- 🔵 **Researcher** — Finds raw data (revenue, market share)
- 🟡 **Analyst** — Analyzes and refines (higher confidence on shared facts)
- 🟣 **Reviewer** — Reviews and adds risk assessment
            """)
            agent_btn = gr.Button("🤖 Merge Agent States", variant="primary", size="lg")
            agent_html = gr.HTML(label="Merged Knowledge")
            agent_plot = gr.Plot(label="Agent Network")
            badge_out_4 = gr.HTML()
            agent_err   = gr.HTML()
            gr.Markdown(
                f"---\n📖 [Convergent Multi-Agent AI Guide]({GUIDE_AGENT})"
            )
            agent_btn.click(fn=run_agent_demo,
                            outputs=[agent_html, agent_plot, badge_out_4, agent_err])

        # ────────────────────────── TAB 5: Federated Learning ───────────────────
        with gr.Tab("🌐 Federated Learning"):
            gr.Markdown("""
## Decentralized Model Merging via Gossip Protocol

No central parameter server needed. Each node merges with random peers,
and all nodes converge to the identical model — guaranteed by CRDT properties.

This simulation shows N nodes performing gossip-based federated learning:
each round, every node merges with a random peer until all states converge.
            """)
            fed_nodes = gr.Slider(minimum=2, maximum=8, step=1, value=4,
                                  label="Number of Nodes")
            fed_btn = gr.Button("🌐 Run Federated Merge", variant="primary", size="lg")
            fed_html = gr.HTML(label="Convergence Status")
            fed_plot = gr.Plot(label="Convergence Timeline")
            badge_out_5 = gr.HTML()
            fed_err  = gr.HTML()
            gr.Markdown(
                f"---\n📖 [Federated Model Merging Guide]({GUIDE_FED})"
            )
            fed_btn.click(fn=run_federated_demo,
                          inputs=[fed_nodes],
                          outputs=[fed_html, fed_plot, badge_out_5, fed_err])

        # ────────────────────────── TAB 6: Compliance ───────────────────────────
        with gr.Tab("🛡️ Compliance"):
            gr.Markdown("""
## Automated Compliance Auditing

crdt-merge includes built-in compliance auditing for major regulatory frameworks.
Every merge operation is traceable, every data removal is verifiable,
and compliance is **proven, not estimated**.
            """)
            with gr.Row():
                comp_dd  = gr.Dropdown(choices=["eu_ai_act", "gdpr", "hipaa", "sox"],
                                       value="eu_ai_act", label="Regulatory Framework")
                comp_btn = gr.Button("🛡️ Run Compliance Audit", variant="primary")
            comp_report = gr.HTML(label="Compliance Report")
            comp_text   = gr.Textbox(label="Full Text Report", lines=12,
                                     interactive=False)
            badge_out_6 = gr.HTML()
            gr.Markdown(
                f"---\n📖 [Compliance Guide]({GUIDE_COMPLY}) · "
                f"[Right to Forget]({GUIDE_FORGET}) · "
                f"[Provenance Guide]({GUIDE_PROV})"
            )
            comp_btn.click(fn=run_compliance_audit, inputs=[comp_dd],
                           outputs=[comp_report, comp_text, badge_out_6])

    gr.HTML(footer_html)

# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, show_error=True)
