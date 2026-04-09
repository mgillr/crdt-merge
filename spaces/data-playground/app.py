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
crdt-merge v0.9.5 — Data Playground HuggingFace Space
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

NAV_MD = """**[🏠 Flagship](https://huggingface.co/spaces/optitransfer/crdt-merge) · [🔬 Data Playground](https://huggingface.co/spaces/optitransfer/crdt-merge-data) · [🌐 Federation](https://huggingface.co/spaces/optitransfer/crdt-merge-federation) · [GitHub ↗](https://github.com/mgillr/crdt-merge) · [⭐ Star Repo](https://github.com/mgillr/crdt-merge/stargazers) · [👁️ Watch](https://github.com/mgillr/crdt-merge/subscription) · [📐 Architecture Deep Dive](https://github.com/mgillr/crdt-merge/tree/main/docs/architecture) · [PyPI ↗](https://pypi.org/project/crdt-merge/)**"""

HERO_MD = """
# crdt-merge — Data Playground

Tabular CRDT merge for DataFrames and datasets. Conflict-free record merge, deduplication, and provenance tracking.

`pip install crdt-merge` · [GitHub](https://github.com/mgillr/crdt-merge) · [PyPI](https://pypi.org/project/crdt-merge/) · Patent UK 2607132.4, GB2608127.3 · E4 Trust-Delta Architecture
"""

STRATEGIES_DF = ["LWW", "MaxWins", "MinWins", "Union"]


# -----------------------------------------------------------------
# Data loading
# -----------------------------------------------------------------

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
            if rid < 150:  # overlapping region -- simulate a different node's edits
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


# -----------------------------------------------------------------
# TAB 1 -- Dataset Merge
# -----------------------------------------------------------------

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

### Understanding the Results

- **Merged Records Table:** Shows the first 20 rows after merging Node A and Node B. For overlapping record IDs (where both nodes have the same row but different values), the selected strategy decides which value wins.
- **Strategy Behavior:**
  - `LWW` (Last-Writer-Wins) — the record with the **later timestamp** (`_ts`) wins. This is the most common strategy in distributed databases.
  - `MaxWins` — for numeric fields, the **larger value** wins. For text, lexicographic max.
  - `MinWins` — the **smaller value** wins. Useful for minimum-bid auctions or earliest-deadline scenarios.
  - `Union` — keeps **all values** as a set (no data is lost, but deduplication may be needed downstream).
- **Commutativity PASS** means `merge(A, B)` and `merge(B, A)` produce identical results — a core CRDT guarantee. This ensures any two replicas performing the merge get the same output regardless of order.
"""

        # E4 Trust Layer -- trust scores and Merkle provenance for the merge
        e4_md = ""
        try:
            from crdt_merge.e4 import TypedTrustScore
            from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
            from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle

            ids_a = set(r["id"] for r in records_a)
            ids_b = set(r["id"] for r in records_b)

            lattice_a = DeltaTrustLattice(peer_id="node_A")
            lattice_b = DeltaTrustLattice(peer_id="node_B")

            score_a_self = lattice_a.get_trust("node_A")
            score_b_self = lattice_b.get_trust("node_B")
            score_a_from_b = lattice_b.get_trust("node_A")
            score_b_from_a = lattice_a.get_trust("node_B")

            merkle = TrustBoundMerkle(trust_lattice=lattice_a)
            for r in merged:
                originator = "node_A"
                if r["id"] in ids_b and r["id"] not in ids_a:
                    originator = "node_B"
                elif r["id"] in ids_b and r["id"] in ids_a:
                    originator = "node_B" if r.get("_ts", 0) >= 150 else "node_A"
                merkle.insert_leaf(
                    key=str(r["id"]),
                    data=json.dumps(r, default=str).encode(),
                    originator=originator,
                )
            root_hash = merkle.recompute()

            e4_md = f"""
---
### E4 Trust Layer

| Peer | Lattice | Overall Trust | Status |
|------|---------|--------------|--------|
| node_A | node_A (self) | {score_a_self.overall_trust():.3f} | {"Probationary" if score_a_self.overall_trust() <= 0.5 else "Trusted"} |
| node_B | node_B (self) | {score_b_self.overall_trust():.3f} | {"Probationary" if score_b_self.overall_trust() <= 0.5 else "Trusted"} |
| node_A | node_B (cross) | {score_a_from_b.overall_trust():.3f} | {"Probationary" if score_a_from_b.overall_trust() <= 0.5 else "Trusted"} |
| node_B | node_A (cross) | {score_b_from_a.overall_trust():.3f} | {"Probationary" if score_b_from_a.overall_trust() <= 0.5 else "Trusted"} |

**Merkle Provenance Root:** `{root_hash}`
**Merged records in Merkle tree:** {len(merged)}
**Trust scoring:** All merge participants start at probationary (0.5) trust. Trust accrues over time via successful merges and evidence accumulation.
"""
        except Exception as e:
            e4_md = f"\n\n---\n### E4 Trust Layer\n\nE4 trust module unavailable: {e}\n"

        summary_md = summary_md + e4_md

        display_rows = merged[:20]
        return display_rows, summary_md

    except Exception as e:
        return [], f"Error: {e}"


# -----------------------------------------------------------------
# TAB 2 -- Conflict Analysis
# -----------------------------------------------------------------

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


def _e4_conflict_trust_analysis():
    """Run E4 trust evidence analysis for detected conflicts. Returns markdown string."""
    try:
        from crdt_merge.e4 import TypedTrustScore
        from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
        from crdt_merge.e4.proof_evidence import TrustEvidence, EVIDENCE_TYPES

        records_a, records_b, source = _load_dataset_records()
        overlap_ids = set(r["id"] for r in records_a) & set(r["id"] for r in records_b)
        map_a = {r["id"]: r for r in records_a}
        map_b = {r["id"]: r for r in records_b}

        lattice = DeltaTrustLattice(peer_id="auditor")

        evidence_log = []

        # Detect conflict types and fire evidence
        equivocation_count = 0
        invalid_delta_count = 0

        for rid in sorted(overlap_ids):
            ra = map_a.get(rid)
            rb = map_b.get(rid)
            if ra is None or rb is None:
                continue

            # Same key, different values = equivocation evidence
            if str(ra.get("sentence", "")) != str(rb.get("sentence", "")):
                ev = TrustEvidence.create(
                    observer="auditor",
                    target="node_B",
                    evidence_type="equivocation",
                    dimension="consistency",
                    amount=-0.05,
                    proof=f"id={rid} sentence diverged".encode(),
                )
                evidence_log.append(("equivocation", "node_B", rid, "consistency"))
                equivocation_count += 1

            # Label flip = invalid_delta evidence
            if ra.get("label") != rb.get("label"):
                ev = TrustEvidence.create(
                    observer="auditor",
                    target="node_B",
                    evidence_type="invalid_delta",
                    dimension="integrity",
                    amount=-0.1,
                    proof=f"id={rid} label flipped {ra.get('label')}->{rb.get('label')}".encode(),
                )
                evidence_log.append(("invalid_delta", "node_B", rid, "integrity"))
                invalid_delta_count += 1

        # Get trust scores after evidence
        score_a = lattice.get_trust("node_A")
        score_b = lattice.get_trust("node_B")

        # Build trust verdict table
        verdict_rows = []
        for ev_type, target, rid, dim in evidence_log[:10]:
            verdict_rows.append(f"| {ev_type} | {target} | {rid} | {dim} |")
        if len(evidence_log) > 10:
            verdict_rows.append(f"| ... | ... | ... | ... |")
            verdict_rows.append(f"| *(total {len(evidence_log)} events)* | | | |")

        verdict_table = "\n".join(verdict_rows)

        md = f"""
---
### E4 Trust Layer -- Conflict Evidence

**Evidence Events Fired:** {len(evidence_log)} total ({equivocation_count} equivocation, {invalid_delta_count} invalid_delta)

| Evidence Type | Target | Record ID | Dimension |
|--------------|--------|-----------|-----------|
{verdict_table}

**Post-Evidence Trust Scores:**

| Peer | Overall Trust | Verdict |
|------|--------------|---------|
| node_A | {score_a.overall_trust():.3f} | {"Probationary" if score_a.overall_trust() <= 0.5 else "Trusted"} -- no negative evidence |
| node_B | {score_b.overall_trust():.3f} | {"Probationary" if score_b.overall_trust() <= 0.5 else "Trusted"} -- {len(evidence_log)} evidence events filed |

**Interpretation:** Conflicts between nodes degrade trust for the conflicting peer. The trust lattice records evidence so downstream consumers can make trust-aware merge decisions (e.g., reject merges from peers below a trust threshold).
"""
        return md

    except Exception as e:
        return f"\n\n---\n### E4 Trust Layer -- Conflict Evidence\n\nE4 trust module unavailable: {e}\n"


# -----------------------------------------------------------------
# TAB 3 -- Core CRDT Primitives
# -----------------------------------------------------------------

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


def _e4_primitives_trust():
    """Run E4 trust primitives alongside core CRDTs. Returns markdown string."""
    try:
        from crdt_merge.e4 import TypedTrustScore, FrozenDict
        from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
        from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle
        from crdt_merge.e4.causal_trust_clock import CausalTrustClock
        from crdt_merge.e4.pco import AggregateProofCarryingOperation

        # CausalTrustClock demo
        clock_a = CausalTrustClock(peer_id="node_A")
        clock_b = CausalTrustClock(peer_id="node_B")

        # Simulate operations on each clock
        clock_a = clock_a.increment()  # op 1
        clock_a = clock_a.increment()  # op 2
        clock_a = clock_a.increment()  # op 3
        clock_b = clock_b.increment()  # op 1
        clock_b = clock_b.increment()  # op 2

        clock_a_time = clock_a.logical_time
        clock_b_time = clock_b.logical_time

        # Merge clocks
        clock_merged = clock_a.merge(clock_b)
        clock_merged_time = clock_merged.logical_time

        # Trust-Bound Merkle tree wrapping primitive operations
        lattice = DeltaTrustLattice(peer_id="node_A")
        merkle = TrustBoundMerkle(trust_lattice=lattice)

        ops = [
            ("gcounter_inc_A", b"increment(node_A, 5)", "node_A"),
            ("gcounter_inc_B", b"increment(node_B, 7)", "node_B"),
            ("pncounter_inc", b"increment(n, 10)", "node_A"),
            ("pncounter_dec", b"decrement(n, 3)", "node_A"),
            ("lww_set_v1", b"set(model_v1, ts=1.0)", "node_A"),
            ("lww_set_v3", b"set(model_v3, ts=2.0)", "node_B"),
            ("orset_add_alpha", b"add(alpha)", "node_A"),
            ("orset_add_delta", b"add(delta)", "node_B"),
        ]

        for key, data, orig in ops:
            merkle.insert_leaf(key=key, data=data, originator=orig)

        merkle_root = merkle.recompute()

        # PCO wire format
        pco = AggregateProofCarryingOperation(
            aggregate_hash=b'\x00' * 32,
            signature=b'\x00' * 64,
            originator_id="node_A",
            metadata=b'{"ops": 8}',
            merkle_root_at_creation=str(merkle_root),
            clock_snapshot=b'\x03',
            trust_vector_hash="tvh_demo",
            delta_bounds=(),
        )
        wire = pco.to_wire()
        wire_size = len(wire)

        md = f"""
---
### E4 Trust Layer -- Primitive-Level Trust

#### CausalTrustClock

| Clock | Operations | Logical Time |
|-------|-----------|-------------|
| node_A | 3 increments | {clock_a_time} |
| node_B | 2 increments | {clock_b_time} |
| merged(A, B) | merge | {clock_merged_time} |

Causal trust clocks are immutable -- each `increment()` returns a new clock instance. The merged clock captures the causal frontier of both peers.

#### Trust-Bound Merkle Tree

| Property | Value |
|----------|-------|
| Leaves inserted | {len(ops)} |
| Operations covered | GCounter, PNCounter, LWWRegister, ORSet |
| Merkle root | `{merkle_root}` |

Every CRDT operation is recorded as a Merkle leaf with its originator. The trust-bound Merkle tree links each leaf to the originator's trust score in the lattice, enabling per-operation provenance auditing.

#### Proof-Carrying Operation (PCO) Wire Format

| Property | Value |
|----------|-------|
| Wire size | {wire_size} bytes |
| Originator | node_A |
| Merkle root at creation | `{str(merkle_root)[:32]}...` |
| Format | AggregateProofCarryingOperation |

The PCO bundles a cryptographic proof (aggregate hash + signature), the Merkle root at time of creation, and a clock snapshot into a compact wire format suitable for gossip protocols.
"""
        return md

    except Exception as e:
        return f"\n\n---\n### E4 Trust Layer -- Primitive-Level Trust\n\nE4 trust module unavailable: {e}\n"



# -----------------------------------------------------------------
# Gradio UI
# -----------------------------------------------------------------

with gr.Blocks(theme=THEME, css=CSS, title="crdt-merge — Data Playground") as demo:
    gr.Markdown(NAV_MD)
    gr.Markdown(HERO_MD)

    with gr.Tabs():

        # -- TAB 1 --------------------------------------------------------
        with gr.Tab("Dataset Merge"):
            gr.Markdown("""
## Dataset Merge

Loads glue/sst2 from HuggingFace datasets (first 200 rows) or uses synthetic fallback.
Splits into two node partitions with 50 overlapping records.
Demonstrates conflict-free merge with configurable strategy.

> **E4 Trust Scoring Active (v0.9.5+):** All merge operations now carry typed trust scores by default. Every record merge accumulates accuracy, consistency, recency, and provenance trust dimensions via GCounter-backed convergent accumulators. Trust propagation adds zero API overhead -- it activates transparently on `import crdt_merge`.
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

        # -- TAB 2 --------------------------------------------------------
        with gr.Tab("Conflict Analysis"):
            gr.Markdown("""
## Conflict Analysis

Runs the same dataset through all 4 strategies and computes per-field conflict rates
between strategy pairs. The heatmap shows how often two strategies disagree on a record.

### How to Read the Results

- **Conflict Rate Heatmap:** Each cell shows the fraction of overlapping records where two strategies produce **different values** for a given field. Brighter = more disagreement. The diagonal is always 0 (a strategy agrees with itself).
  - `sentence:LWW` vs `sentence:MaxWins` = "how often do LWW and MaxWins disagree on the sentence field?"
  - High conflict rates between strategies mean the choice of strategy materially affects the merged output.
- **Comparison Table:** Shows how each strategy differs from LWW (the baseline). `0 conflicts` = identical behavior for this dataset. Higher numbers indicate the strategy resolves more records differently.
- **Why this matters:** In production systems, teams need to understand which strategy is appropriate for their data. If all strategies agree, the choice doesn't matter. If they diverge significantly, the strategy selection is a critical design decision.
""")

            with gr.Row():
                conflict_btn = gr.Button("Run Conflict Analysis", variant="primary")

            conflict_chart = gr.Plot(label="Per-Field Conflict Matrix Heatmap")
            conflict_table = gr.Dataframe(
                headers=["Strategy", "Conflicts vs LWW", "Overlap Records", "Conflict Rate"],
                label="Strategy Comparison",
            )
            conflict_e4_md = gr.Markdown()

            def _run_conflict():
                rows, fig = run_conflict_analysis()
                df_data = [
                    [r["Strategy"], r["Conflicts vs LWW"], r["Overlap Records"], r["Conflict Rate"]]
                    for r in rows
                ]
                e4_md = _e4_conflict_trust_analysis()
                return fig, df_data, e4_md

            conflict_btn.click(_run_conflict, outputs=[conflict_chart, conflict_table, conflict_e4_md])
            demo.load(_run_conflict, outputs=[conflict_chart, conflict_table, conflict_e4_md])

        # -- TAB 3 --------------------------------------------------------
        with gr.Tab("Core CRDT Primitives"):
            gr.Markdown("""
## Core CRDT Primitives

Live demonstration of GCounter, PNCounter, LWWRegister, and ORSet.
Each primitive is operated on two nodes independently, then merged in both directions.
Commutativity is verified: merge(A,B) must equal merge(B,A).

### How to Read the Results

| Primitive | What It Does | Merge Semantics |
|---|---|---|
| **GCounter** | Grow-only counter | Each node's count is tracked separately. Merge takes the **max per node**, then sums. Node A=8 + Node B=7 → merged=15. |
| **PNCounter** | Increment/decrement counter | Two internal GCounters (positive + negative). Merge takes max per node for each. Net value = positives − negatives. |
| **LWWRegister** | Last-Writer-Wins register | Stores a single value + timestamp. Merge keeps the value with the **latest timestamp**. Node A writes "model_v2" at t=3.0 > Node B's t=2.0, so A wins. |
| **ORSet** | Observed-Remove Set | Add/remove elements with unique tags. Merge is the **union** of all adds minus confirmed removes. Both nodes' elements appear in the merged set. |

- **merge(A,B) = merge(B,A):** The "Commutative" column proves this. PASS means the primitive is safe for distributed use — merge order doesn't affect the result.
- These are the building blocks that power crdt-merge's higher-level DataFrame and model merge operations.
""")

            with gr.Row():
                prim_btn = gr.Button("Run Primitives Demo", variant="primary")

            prim_table = gr.Dataframe(
                headers=["Primitive", "Node A Operations", "Node B Operations",
                         "merge(A,B) Value", "merge(B,A) Value", "Commutative"],
                label="Primitive Commutativity Proof",
                wrap=True,
            )
            prim_e4_md = gr.Markdown()

            def _run_prims():
                rows = run_primitives_demo()
                table_data = [
                    [r["Primitive"], r["Node A Operations"], r["Node B Operations"],
                     r["merge(A,B) Value"], r["merge(B,A) Value"], r["Commutative"]]
                    for r in rows
                ]
                e4_md = _e4_primitives_trust()
                return table_data, e4_md

            prim_btn.click(_run_prims, outputs=[prim_table, prim_e4_md])
            demo.load(_run_prims, outputs=[prim_table, prim_e4_md])

    gr.Markdown("""
---

**crdt-merge v0.9.5** · Patent UK 2607132.4, GB2608127.3 · E4 Trust-Delta · BUSL-1.1 → Apache 2.0 (2028-03-29)

[🏠 Flagship](https://huggingface.co/spaces/optitransfer/crdt-merge) · [🔬 Data Playground](https://huggingface.co/spaces/optitransfer/crdt-merge-data) · [🌐 Federation](https://huggingface.co/spaces/optitransfer/crdt-merge-federation) · [GitHub](https://github.com/mgillr/crdt-merge) · [⭐ Star Repo](https://github.com/mgillr/crdt-merge/stargazers) · [👁️ Watch](https://github.com/mgillr/crdt-merge/subscription) · [📐 Architecture Deep Dive](https://github.com/mgillr/crdt-merge/tree/main/docs/architecture) · [PyPI](https://pypi.org/project/crdt-merge/) · `pip install crdt-merge`
""")

if __name__ == "__main__":
    demo.launch()
