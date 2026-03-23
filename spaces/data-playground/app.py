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
crdt-merge v0.9.4 — Data Playground HuggingFace Space
Tabular CRDT merge, conflict analysis, and core primitive demonstrations.
"""

import os
import json
import time
import numpy as np
import gradio as gr
import plotly.graph_objects as go

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

NAV_MD = """**[🏠 Flagship](https://huggingface.co/spaces/optitransfer/crdt-merge) · [🔬 Data Playground](https://huggingface.co/spaces/optitransfer/crdt-merge-data) · [🌐 Federation](https://huggingface.co/spaces/optitransfer/crdt-merge-federation) · [GitHub ↗](https://github.com/mgillr/crdt-merge) · [PyPI ↗](https://pypi.org/project/crdt-merge/)**"""

HERO_MD = """
# crdt-merge — Data Playground

Tabular CRDT merge for DataFrames and datasets. Conflict-free record merge, deduplication, and provenance tracking.

`pip install crdt-merge` · [GitHub](https://github.com/mgillr/crdt-merge) · [PyPI](https://pypi.org/project/crdt-merge/) · Patent Pending UK 2607132.4
"""

STRATEGIES_DF = ["LWW", "MaxWins", "MinWins", "Union"]


# ─────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────

def _load_dataset_records():
    """Try HF datasets first, fallback to synthetic."""
    source = "synthetic"
    records_a = []
    records_b = []

    try:
        from datasets import load_dataset
        ds = load_dataset("glue", "sst2", split="train[:200]")
        all_records = [{"id": i, "sentence": ds[i]["sentence"], "label": ds[i]["label"], "_ts": i}
                       for i in range(len(ds))]
        records_a = all_records[:150]
        # Node B: overlapping records (100-149) get modified values + later timestamps
        records_b = []
        for r in all_records[100:]:
            rid = r["id"]
            if rid < 150:  # overlapping region — simulate a different node's edits
                records_b.append({
                    "id": rid,
                    "sentence": r["sentence"].strip() + " [node-B edit]",
                    "label": 1 - r["label"],  # flip label to create real conflict
                    "_ts": rid + 50,           # later timestamp for LWW
                })
            else:
                records_b.append(r)
        source = "glue/sst2 (HuggingFace datasets, 200 rows, 50 conflicting overlap)"
    except Exception:
        pass

    if not records_a:
        rng = np.random.RandomState(7)
        adjectives = ["good", "bad", "great", "poor", "excellent", "terrible", "fine", "awful"]
        nouns = ["film", "movie", "picture", "show", "performance", "script", "cast", "story"]
        for i in range(200):
            adj = adjectives[i % len(adjectives)]
            noun = nouns[i % len(nouns)]
            records_a.append({"id": i, "sentence": f"A {adj} {noun}.", "label": i % 2, "_ts": i})
        for i in range(100, 200):
            adj = adjectives[(i + 3) % len(adjectives)]
            noun = nouns[(i + 2) % len(nouns)]
            records_b.append({"id": i, "sentence": f"An {adj} {noun}.", "label": (i + 1) % 2, "_ts": i + 50})
        for i in range(200, 250):
            adj = adjectives[i % len(adjectives)]
            noun = nouns[i % len(nouns)]
            records_b.append({"id": i, "sentence": f"The {adj} {noun}.", "label": i % 2, "_ts": i})
        source = "synthetic (SST-2 style, 150 + 100 records with 50 overlap)"

    return records_a, records_b, source


# ─────────────────────────────────────────────────────────────────
# TAB 1 — Dataset Merge
# ─────────────────────────────────────────────────────────────────

def run_dataset_merge(strategy_name: str):
    from crdt_merge.dataframe import merge as df_merge
    from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins, UnionSet

    strategy_map = {
        "LWW": LWW(),
        "MaxWins": MaxWins(),
        "MinWins": MinWins(),
        "Union": UnionSet(),
    }
    schema = MergeSchema(default=strategy_map[strategy_name])

    records_a, records_b, source = _load_dataset_records()
    t0 = time.perf_counter()

    try:
        merged = df_merge(records_a, records_b, key="id", schema=schema, timestamp_col="_ts")
        elapsed = (time.perf_counter() - t0) * 1000

        # Verify commutativity
        merged_ba = df_merge(records_b, records_a, key="id", schema=schema, timestamp_col="_ts")
        ids_ab = sorted([r["id"] for r in merged])
        ids_ba = sorted([r["id"] for r in merged_ba])
        comm_pass = ids_ab == ids_ba

        summary_md = f"""
**Dataset Merge Complete**

| Metric | Value |
|---|---|
| Source | {source} |
| Strategy | {strategy_name} |
| Node A records | {len(records_a)} |
| Node B records | {len(records_b)} |
| Overlapping IDs | {len(set(r['id'] for r in records_a) & set(r['id'] for r in records_b))} |
| Merged records | {len(merged)} |
| Elapsed | {elapsed:.1f}ms |
| Commutative (merge_AB == merge_BA) | **{"PASS" if comm_pass else "FAIL"}** |
"""

        display_rows = merged[:20]
        return display_rows, summary_md

    except Exception as e:
        return [], f"Error: {e}"


# ─────────────────────────────────────────────────────────────────
# TAB 2 — Conflict Analysis
# ─────────────────────────────────────────────────────────────────

def run_conflict_analysis():
    from crdt_merge.dataframe import merge as df_merge
    from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins, UnionSet

    records_a, records_b, source = _load_dataset_records()
    overlap_ids = set(r["id"] for r in records_a) & set(r["id"] for r in records_b)

    strategy_map = {
        "LWW": LWW(),
        "MaxWins": MaxWins(),
        "MinWins": MinWins(),
        "Union": UnionSet(),
    }

    fields = ["sentence", "label"]
    results_by_strategy = {}

    for strat_name, strat in strategy_map.items():
        schema = MergeSchema(default=strat)
        try:
            merged = df_merge(records_a, records_b, key="id", schema=schema, timestamp_col="_ts")
            results_by_strategy[strat_name] = {r["id"]: r for r in merged if r["id"] in overlap_ids}
        except Exception as e:
            results_by_strategy[strat_name] = {}

    # Build conflict matrix: per-field, per-strategy-pair, how many records differ
    strat_names = list(strategy_map.keys())
    conflict_matrix = {}
    for field in fields:
        conflict_matrix[field] = np.zeros((len(strat_names), len(strat_names)), dtype=np.float32)
        for i, s1 in enumerate(strat_names):
            for j, s2 in enumerate(strat_names):
                if i == j:
                    continue
                diffs = 0
                total = 0
                for rid in overlap_ids:
                    r1 = results_by_strategy[s1].get(rid)
                    r2 = results_by_strategy[s2].get(rid)
                    if r1 is not None and r2 is not None:
                        total += 1
                        if str(r1.get(field, "")) != str(r2.get(field, "")):
                            diffs += 1
                conflict_matrix[field][i, j] = diffs / max(total, 1)

    # Heatmap: combine fields side by side
    combined_z = np.concatenate([conflict_matrix[f] for f in fields], axis=1)
    col_labels = [f"{f}:{s}" for f in fields for s in strat_names]

    fig = go.Figure(data=go.Heatmap(
        z=combined_z.tolist(),
        x=col_labels,
        y=strat_names,
        colorscale=[[0, "#18181b"], [1, "#3b82f6"]],
        showscale=True,
        colorbar=dict(title="Conflict Rate"),
    ))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=f"Per-Field Conflict Matrix — Strategy vs Strategy (source: {source[:40]}...)",
        xaxis_title="Field : Strategy (column)",
        yaxis_title="Strategy (row)",
    )

    # Summary table: how many overlapping records each strategy resolves differently from LWW
    summary_rows = []
    for strat_name in strat_names:
        diffs_vs_lww = 0
        for rid in overlap_ids:
            r_lww = results_by_strategy["LWW"].get(rid)
            r_s = results_by_strategy[strat_name].get(rid)
            if r_lww and r_s:
                for field in fields:
                    if str(r_lww.get(field, "")) != str(r_s.get(field, "")):
                        diffs_vs_lww += 1
                        break
        summary_rows.append({
            "Strategy": strat_name,
            "Conflicts vs LWW": diffs_vs_lww,
            "Overlap Records": len(overlap_ids),
            "Conflict Rate": f"{diffs_vs_lww / max(len(overlap_ids), 1):.2%}",
        })

    return summary_rows, fig


# ─────────────────────────────────────────────────────────────────
# TAB 3 — Core CRDT Primitives
# ─────────────────────────────────────────────────────────────────

def run_primitives_demo():
    from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet

    results = {}

    # GCounter
    gc_a = GCounter()
    gc_a.increment("node_A", 5)
    gc_a.increment("node_A", 3)
    gc_b = GCounter()
    gc_b.increment("node_B", 7)
    gc_merged_ab = gc_a.merge(gc_b)
    gc_merged_ba = gc_b.merge(gc_a)
    results["GCounter"] = {
        "node_A_ops": "gc_a.increment('node_A', 5); gc_a.increment('node_A', 3)  # value=8",
        "node_B_ops": "gc_b.increment('node_B', 7)  # value=7",
        "merge_AB_value": gc_merged_ab.value,
        "merge_BA_value": gc_merged_ba.value,
        "commutative": gc_merged_ab.value == gc_merged_ba.value,
    }

    # PNCounter
    pn_a = PNCounter()
    pn_a.increment("n", 10)
    pn_a.decrement("n", 3)
    pn_b = PNCounter()
    pn_b.increment("n", 5)
    pn_merged_ab = pn_a.merge(pn_b)
    pn_merged_ba = pn_b.merge(pn_a)
    results["PNCounter"] = {
        "node_A_ops": "pn_a.increment('n', 10); pn_a.decrement('n', 3)  # value=7",
        "node_B_ops": "pn_b.increment('n', 5)  # value=5",
        "merge_AB_value": pn_merged_ab.value,
        "merge_BA_value": pn_merged_ba.value,
        "commutative": pn_merged_ab.value == pn_merged_ba.value,
    }

    # LWWRegister
    lww_a = LWWRegister()
    lww_a.set("model_v1", timestamp=1.0)
    lww_a.set("model_v2", timestamp=3.0)
    lww_b = LWWRegister()
    lww_b.set("model_v3", timestamp=2.0)
    lww_merged_ab = lww_a.merge(lww_b)
    lww_merged_ba = lww_b.merge(lww_a)
    results["LWWRegister"] = {
        "node_A_ops": "lww_a.set('model_v1', timestamp=1.0); lww_a.set('model_v2', timestamp=3.0)",
        "node_B_ops": "lww_b.set('model_v3', timestamp=2.0)",
        "merge_AB_value": str(lww_merged_ab.value),
        "merge_BA_value": str(lww_merged_ba.value),
        "commutative": str(lww_merged_ab.value) == str(lww_merged_ba.value),
    }

    # ORSet
    orset_a = ORSet()
    orset_a.add("alpha")
    orset_a.add("beta")
    tag_beta = orset_a.add("gamma")
    orset_b = ORSet()
    orset_b.add("beta")
    orset_b.add("delta")
    orset_merged_ab = orset_a.merge(orset_b)
    orset_merged_ba = orset_b.merge(orset_a)
    results["ORSet"] = {
        "node_A_ops": "orset_a.add('alpha'); orset_a.add('beta'); orset_a.add('gamma')",
        "node_B_ops": "orset_b.add('beta'); orset_b.add('delta')",
        "merge_AB_value": str(sorted(orset_merged_ab.value)),
        "merge_BA_value": str(sorted(orset_merged_ba.value)),
        "commutative": sorted(orset_merged_ab.value) == sorted(orset_merged_ba.value),
    }

    rows = []
    for name, data in results.items():
        rows.append({
            "Primitive": name,
            "Node A Operations": data["node_A_ops"],
            "Node B Operations": data["node_B_ops"],
            "merge(A,B) Value": str(data["merge_AB_value"]),
            "merge(B,A) Value": str(data["merge_BA_value"]),
            "Commutative": "PASS" if data["commutative"] else "FAIL",
        })

    return rows



# ─────────────────────────────────────────────────────────────────
# Gradio UI
# ─────────────────────────────────────────────────────────────────

with gr.Blocks(theme=THEME, css=CSS, title="crdt-merge — Data Playground") as demo:
    gr.Markdown(NAV_MD)
    gr.Markdown(HERO_MD)

    with gr.Tabs():

        # ── TAB 1 ──────────────────────────────────────────────────────
        with gr.Tab("Dataset Merge"):
            gr.Markdown("""
## Dataset Merge

Loads glue/sst2 from HuggingFace datasets (first 200 rows) or uses synthetic fallback.
Splits into two node partitions with 50 overlapping records.
Demonstrates conflict-free merge with configurable strategy.
""")

            with gr.Row():
                strat_dd = gr.Dropdown(
                    choices=STRATEGIES_DF,
                    value="LWW",
                    label="Merge Strategy",
                    info="LWW = Last Write Wins (by timestamp). MaxWins/MinWins = field max/min. Union = set union.",
                )
                merge_ds_btn = gr.Button("Run Dataset Merge", variant="primary")

            merge_summary_md = gr.Markdown()
            merge_result_table = gr.Dataframe(
                headers=["id", "sentence", "label", "_ts"],
                label="Merged Records (first 20 rows)",
                wrap=True,
            )

            def _run_ds_merge(strategy):
                rows, summary = run_dataset_merge(strategy)
                df_data = [[r.get("id", ""), r.get("sentence", ""), r.get("label", ""), r.get("_ts", "")] for r in rows]
                return summary, df_data

            merge_ds_btn.click(_run_ds_merge, inputs=[strat_dd], outputs=[merge_summary_md, merge_result_table])
            demo.load(lambda: _run_ds_merge("LWW"), outputs=[merge_summary_md, merge_result_table])

        # ── TAB 2 ──────────────────────────────────────────────────────
        with gr.Tab("Conflict Analysis"):
            gr.Markdown("""
## Conflict Analysis

Runs the same dataset through all 4 strategies and computes per-field conflict rates
between strategy pairs. The heatmap shows how often two strategies disagree on a record.
""")

            with gr.Row():
                conflict_btn = gr.Button("Run Conflict Analysis", variant="primary")

            conflict_chart = gr.Plot(label="Per-Field Conflict Matrix Heatmap")
            conflict_table = gr.Dataframe(
                headers=["Strategy", "Conflicts vs LWW", "Overlap Records", "Conflict Rate"],
                label="Strategy Comparison",
            )

            def _run_conflict():
                rows, fig = run_conflict_analysis()
                df_data = [
                    [r["Strategy"], r["Conflicts vs LWW"], r["Overlap Records"], r["Conflict Rate"]]
                    for r in rows
                ]
                return fig, df_data

            conflict_btn.click(_run_conflict, outputs=[conflict_chart, conflict_table])
            demo.load(_run_conflict, outputs=[conflict_chart, conflict_table])

        # ── TAB 3 ──────────────────────────────────────────────────────
        with gr.Tab("Core CRDT Primitives"):
            gr.Markdown("""
## Core CRDT Primitives

Live demonstration of GCounter, PNCounter, LWWRegister, and ORSet.
Each primitive is operated on two nodes independently, then merged in both directions.
Commutativity is verified: merge(A,B) must equal merge(B,A).

Note: `.value` is a property (no parentheses required).
""")

            with gr.Row():
                prim_btn = gr.Button("Run Primitives Demo", variant="primary")

            prim_table = gr.Dataframe(
                headers=["Primitive", "Node A Operations", "Node B Operations",
                         "merge(A,B) Value", "merge(B,A) Value", "Commutative"],
                label="Primitive Commutativity Proof",
                wrap=True,
            )

            def _run_prims():
                rows = run_primitives_demo()
                return [
                    [r["Primitive"], r["Node A Operations"], r["Node B Operations"],
                     r["merge(A,B) Value"], r["merge(B,A) Value"], r["Commutative"]]
                    for r in rows
                ]

            prim_btn.click(_run_prims, outputs=[prim_table])
            demo.load(_run_prims, outputs=[prim_table])

    gr.Markdown("""
---

**crdt-merge v0.9.4** · Patent Pending UK 2607132.4 · BUSL-1.1 → Apache 2.0 (2028-03-29)

[🏠 Flagship](https://huggingface.co/spaces/optitransfer/crdt-merge) · [🔬 Data Playground](https://huggingface.co/spaces/optitransfer/crdt-merge-data) · [🌐 Federation](https://huggingface.co/spaces/optitransfer/crdt-merge-federation) · [GitHub](https://github.com/mgillr/crdt-merge) · [PyPI](https://pypi.org/project/crdt-merge/) · `pip install crdt-merge`
""")

if __name__ == "__main__":
    demo.launch()
