# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
# Patent Pending: UK Application No. 2607132.4
"""
crdt-merge 0.9.4 -- Enterprise Technical Demonstration
Live Hugging Face Hub Integration | Full 6-Layer CRDT Proof Engine
https://github.com/mgillr/crdt-merge | https://optitransfer.ch
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import time
from datetime import datetime, timezone
from itertools import permutations
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr
from huggingface_hub import HfApi

from crdt_merge import merge, diff, merge_dicts, merge_with_provenance, GossipState
from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet, LWWMap
from crdt_merge.clocks import VectorClock, Ordering
from crdt_merge.agentic import AgentState, SharedKnowledge
from crdt_merge.compliance import ComplianceAuditor
from crdt_merge.dedup import dedup_records, dedup_list, DedupIndex
from crdt_merge.strategies import (
    MergeSchema, LWW, MaxWins, MinWins, Concat, UnionSet, LongestWins, Priority,
)
from crdt_merge.audit import AuditLog, AuditedMerge
from crdt_merge.unmerge import UnmergeEngine
from crdt_merge.provenance import export_provenance

# ---------------------------------------------------------------------------
# DESIGN CONSTANTS
# ---------------------------------------------------------------------------
BG = "#09090B"
SURFACE = "#18181B"
ELEVATED = "#27272A"
BORDER = "#3F3F46"
TEXT = "#FAFAFA"
TEXT2 = "#A1A1AA"
MUTED = "#71717A"
DIM = "#52525B"
ACCENT = "#06B6D4"
ACC_DIM = "#164E63"
ACC_BG = "#083344"

# ---------------------------------------------------------------------------
# HF HUB API CACHE
# ---------------------------------------------------------------------------
_hf_api: Optional[HfApi] = None
_model_cache: Dict[str, list] = {}
_dataset_cache: Dict[str, list] = {}


def _get_hf_api() -> HfApi:
    """Lazy-init HF API client."""
    global _hf_api
    if _hf_api is None:
        token = os.environ.get("HF_TOKEN", "") or None
        _hf_api = HfApi(token=token)
    return _hf_api


def _fetch_models(n: int = 20) -> list:
    """Fetch top models by downloads, cached in-process."""
    key = f"models_{n}"
    if key in _model_cache:
        return _model_cache[key]
    try:
        hf = _get_hf_api()
        models = list(hf.list_models(sort="downloads", limit=n))
        _model_cache[key] = models
        return models
    except Exception:
        return []


def _fetch_datasets(n: int = 15) -> list:
    """Fetch top datasets by downloads, cached in-process."""
    key = f"datasets_{n}"
    if key in _dataset_cache:
        return _dataset_cache[key]
    try:
        hf = _get_hf_api()
        datasets = list(hf.list_datasets(sort="downloads", limit=n))
        _dataset_cache[key] = datasets
        return datasets
    except Exception:
        return []


# ---------------------------------------------------------------------------
# FORMATTING HELPERS
# ---------------------------------------------------------------------------


def _fmt_num(n: Any) -> str:
    """Format large numbers: 1234567 -> '1.23M'."""
    if n is None:
        return "0"
    try:
        n = int(n)
    except (ValueError, TypeError):
        return str(n)
    if abs(n) >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _ts_now() -> str:
    """Current UTC timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _sha256_short(data: str, length: int = 16) -> str:
    """Truncated SHA-256 hex digest."""
    return hashlib.sha256(data.encode()).hexdigest()[:length]


def _sha256_full(data: str) -> str:
    """Full SHA-256 hex digest."""
    return hashlib.sha256(data.encode()).hexdigest()


def _model_to_record(m, idx: int = 0) -> dict:
    """Convert HF ModelInfo to a plain dict record."""
    return {
        "id": getattr(m, "id", None) or f"model-{idx}",
        "downloads": getattr(m, "downloads", None) or 0,
        "likes": getattr(m, "likes", None) or 0,
        "pipeline_tag": getattr(m, "pipeline_tag", None) or "unknown",
        "library": getattr(m, "library_name", None) or "unknown",
        "author": getattr(m, "author", None) or "unknown",
    }


def _dataset_to_record(d, idx: int = 0) -> dict:
    """Convert HF DatasetInfo to a plain dict record."""
    return {
        "id": getattr(d, "id", None) or f"dataset-{idx}",
        "downloads": getattr(d, "downloads", None) or 0,
        "likes": getattr(d, "likes", None) or 0,
        "author": getattr(d, "author", None) or "unknown",
    }


# ---------------------------------------------------------------------------
# HTML COMPONENT BUILDERS
# ---------------------------------------------------------------------------


def _stat_box(label: str, value: str, accent: bool = False) -> str:
    """Single metric box."""
    color = ACCENT if accent else TEXT
    bg = ACC_BG if accent else ELEVATED
    bdr = ACCENT if accent else BORDER
    return (
        f'<div style="flex:1;min-width:130px;background:{bg};border:1px solid {bdr};'
        f'border-radius:8px;padding:16px 12px;text-align:center;">'
        f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:1.5rem;'
        f'font-weight:700;color:{color};line-height:1.2;">{value}</div>'
        f'<div style="font-size:0.7rem;color:{TEXT2};text-transform:uppercase;'
        f'letter-spacing:0.08em;margin-top:6px;">{label}</div></div>'
    )


def _stat_row(stats: List[Tuple[str, str, bool]]) -> str:
    """Flex row of metric boxes."""
    boxes = "".join(_stat_box(lbl, val, acc) for lbl, val, acc in stats)
    return (
        f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin:12px 0;">'
        f'{boxes}</div>'
    )


def _hash_display(label: str, h: str) -> str:
    """Inline hash badge."""
    return (
        f'<div style="background:{ACC_BG};border:1px solid {ACC_DIM};border-radius:6px;'
        f'padding:6px 10px;margin:4px 2px;display:inline-block;">'
        f'<span style="color:{TEXT2};font-size:0.65rem;text-transform:uppercase;'
        f'letter-spacing:0.05em;">{label} </span>'
        f'<span style="font-family:\'JetBrains Mono\',monospace;color:{ACCENT};'
        f'font-size:0.8rem;">{h}</span></div>'
    )


def _section(title: str) -> str:
    """Section header with bottom border."""
    return (
        f'<div style="font-size:0.75rem;color:{MUTED};text-transform:uppercase;'
        f'letter-spacing:0.1em;margin:24px 0 8px 0;border-bottom:1px solid {BORDER};'
        f'padding-bottom:6px;font-weight:600;">{title}</div>'
    )


def _card(content: str) -> str:
    """Bordered surface card."""
    return (
        f'<div style="background:{SURFACE};border:1px solid {BORDER};border-radius:8px;'
        f'padding:16px;margin:8px 0;">{content}</div>'
    )


def _table(headers: list, rows: list) -> str:
    """Dark data table with hover."""
    hdr_cells = "".join(
        f'<th style="padding:8px 12px;text-align:left;font-size:0.68rem;color:{TEXT2};'
        f'text-transform:uppercase;letter-spacing:0.05em;border-bottom:2px solid {BORDER};'
        f'font-family:\'JetBrains Mono\',monospace;white-space:nowrap;">{h}</th>'
        for h in headers
    )
    body = ""
    for row in rows:
        cells = "".join(
            f'<td style="padding:6px 12px;font-family:\'JetBrains Mono\',monospace;'
            f'font-size:0.78rem;color:{TEXT};border-bottom:1px solid {ELEVATED};'
            f'white-space:nowrap;max-width:320px;overflow:hidden;text-overflow:ellipsis;">{c}</td>'
            for c in row
        )
        body += (
            f'<tr style="transition:background 0.15s;"'
            f' onmouseover="this.style.background=\'{ELEVATED}\'"'
            f' onmouseout="this.style.background=\'transparent\'">{cells}</tr>'
        )
    return (
        f'<div style="overflow-x:auto;margin:6px 0;"><table style="width:100%;'
        f'border-collapse:collapse;background:transparent;">'
        f'<thead><tr>{hdr_cells}</tr></thead><tbody>{body}</tbody></table></div>'
    )


def _badge(label: str, status: str = "info") -> str:
    """Small colored badge."""
    colors = {
        "pass": ("#065F46", "#10B981"),
        "fail": ("#7F1D1D", "#EF4444"),
        "info": (ACC_BG, ACCENT),
        "warn": ("#78350F", "#F59E0B"),
    }
    bg, fg = colors.get(status, colors["info"])
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
        f'font-size:0.68rem;font-family:\'JetBrains Mono\',monospace;'
        f'background:{bg};color:{fg};text-transform:uppercase;letter-spacing:0.05em;">'
        f'{label}</span>'
    )


def _data_ts() -> str:
    """Live data source timestamp footer."""
    return (
        f'<div style="font-size:0.6rem;color:{DIM};text-align:right;margin-top:12px;'
        f'font-family:\'JetBrains Mono\',monospace;">'
        f'LIVE DATA SOURCE -- HUGGING FACE HUB -- {_ts_now()}</div>'
    )


def _property_card(name: str, desc: str, passed: bool, detail: str) -> str:
    """CRDT property proof card."""
    badge = _badge("PASS" if passed else "FAIL", "pass" if passed else "fail")
    return _card(
        f'{badge} '
        f'<span style="color:{TEXT};font-family:\'JetBrains Mono\',monospace;'
        f'font-size:0.82rem;font-weight:600;margin-left:6px;">{name}</span>'
        f'<div style="color:{TEXT2};font-size:0.72rem;margin-top:4px;">{desc}</div>'
        f'<div style="margin-top:6px;">{detail}</div>'
    )


def _error_card(msg: str) -> str:
    """Error display card."""
    return _card(
        f'<span style="color:#EF4444;font-family:\'JetBrains Mono\',monospace;'
        f'font-size:0.85rem;">ERROR: {msg}</span>'
    )


# ---------------------------------------------------------------------------
# TAB 1: CONVERGENCE ENGINE
# ---------------------------------------------------------------------------


def tab1_convergence(node_count: int) -> str:
    t0 = perf_counter()
    models = _fetch_models(int(node_count) * 5)
    if not models:
        return _error_card("Could not fetch models from Hugging Face Hub. Check HF_TOKEN or network.")

    records = [_model_to_record(m, i) for i, m in enumerate(models)]
    n = int(node_count)
    chunk_size = max(1, len(records) // n)

    # Build overlapping node subsets
    nodes: List[GossipState] = []
    node_record_counts: List[int] = []
    for i in range(n):
        start = max(0, i * chunk_size - 2)
        end = min(len(records), (i + 1) * chunk_size + 2)
        gs = GossipState(f"node-{i}")
        subset = records[start:end]
        for r in subset:
            gs.update(r["id"], r)
        nodes.append(gs)
        node_record_counts.append(len(subset))

    # -- LIVE DATA SOURCE --
    html = _section("LIVE DATA FROM HUGGING FACE HUB")
    data_rows = []
    for r in records[:min(12, len(records))]:
        data_rows.append([
            r["id"],
            _fmt_num(r.get("downloads", 0)),
            _fmt_num(r.get("likes", 0)),
            r.get("pipeline", ""),
            r.get("library", ""),
        ])
    html += _table(["MODEL ID", "DOWNLOADS", "LIKES", "PIPELINE", "LIBRARY"], data_rows)
    html += _stat_row([
        ("MODELS FETCHED", str(len(records)), True),
        ("LIVE ENDPOINT", "api.huggingface.co", False),
        ("SORTED BY", "DOWNLOADS (DESCENDING)", False),
    ])

    # -- PRE STATE --
    html += _section("PRE-MERGE STATE: DIVERGENT NODES")
    pre_rows = []
    pre_digests = []
    for i, gs in enumerate(nodes):
        d = gs.digest()
        digest_hash = _sha256_short(json.dumps(d, sort_keys=True))
        pre_digests.append(digest_hash)
        pre_rows.append([
            f"NODE-{i}",
            str(node_record_counts[i]),
            str(gs.size),
            digest_hash,
        ])
    html += _table(["NODE", "INPUT RECORDS", "STATE SIZE", "STATE DIGEST"], pre_rows)

    unique_pre = len(set(pre_digests))
    html += _stat_row([
        ("NODES", str(n), False),
        ("TOTAL RECORDS", str(len(records)), False),
        ("UNIQUE STATES (PRE)", str(unique_pre), False),
        ("STATUS", "DIVERGENT" if unique_pre > 1 else "ALREADY CONVERGED", unique_pre == 1),
    ])

    # -- TEST ALL ORDERINGS --
    html += _section(f"CONVERGENCE TEST: ALL {math.factorial(n)} MERGE ORDERINGS")
    indices = list(range(n))
    all_perms = list(permutations(indices))
    merge_digests: List[str] = []
    merge_timings: List[float] = []
    merge_sizes: List[int] = []

    for perm in all_perms:
        mt0 = perf_counter()
        merged = nodes[perm[0]]
        for idx in perm[1:]:
            merged = merged.merge(nodes[idx])
        mt1 = perf_counter()
        d = merged.digest()
        dh = _sha256_short(json.dumps(d, sort_keys=True))
        merge_digests.append(dh)
        merge_timings.append((mt1 - mt0) * 1000)
        merge_sizes.append(merged.size)

    perm_rows = []
    for i, perm in enumerate(all_perms):
        order_str = " -> ".join(f"N{p}" for p in perm)
        perm_rows.append([
            order_str,
            merge_digests[i],
            str(merge_sizes[i]),
            f"{merge_timings[i]:.3f}ms",
        ])
    html += _table(["MERGE ORDER", "RESULT DIGEST", "SIZE", "TIME"], perm_rows)

    unique_post = len(set(merge_digests))
    converged = unique_post == 1
    avg_time = sum(merge_timings) / len(merge_timings) if merge_timings else 0

    # -- POST STATE --
    html += _section("POST-MERGE STATE: CONVERGENCE PROOF")
    html += _stat_row([
        ("ORDERINGS TESTED", str(len(all_perms)), False),
        ("UNIQUE RESULTS", str(unique_post), converged),
        ("CONVERGED", "YES" if converged else "NO", converged),
        ("AVG MERGE TIME", f"{avg_time:.3f}ms", False),
    ])
    if converged:
        html += _hash_display("CONVERGED DIGEST", merge_digests[0])
        full_hash = _sha256_full(json.dumps(nodes[0].merge(nodes[1]).digest() if n >= 2 else nodes[0].digest(), sort_keys=True))
        html += f'<div style="margin-top:4px;">'
        html += _hash_display("FULL SHA-256", full_hash[:32] + "...")
        html += f'</div>'

    # -- CRDT PROPERTY VERIFICATION --
    html += _section("CRDT PROPERTY VERIFICATION")

    # Commutativity: merge(A,B) == merge(B,A)
    if n >= 2:
        ab = nodes[0].merge(nodes[1])
        ba = nodes[1].merge(nodes[0])
        ab_d = _sha256_short(json.dumps(ab.digest(), sort_keys=True))
        ba_d = _sha256_short(json.dumps(ba.digest(), sort_keys=True))
        comm_pass = ab_d == ba_d
        html += _property_card(
            "COMMUTATIVITY",
            "merge(A, B) must equal merge(B, A) for all pairs",
            comm_pass,
            f'{_hash_display("merge(N0,N1)", ab_d)} {_hash_display("merge(N1,N0)", ba_d)}',
        )

    # Associativity: merge(merge(A,B),C) == merge(A,merge(B,C))
    if n >= 3:
        ab_c = (nodes[0].merge(nodes[1])).merge(nodes[2])
        a_bc = nodes[0].merge(nodes[1].merge(nodes[2]))
        abc_d = _sha256_short(json.dumps(ab_c.digest(), sort_keys=True))
        a_bc_d = _sha256_short(json.dumps(a_bc.digest(), sort_keys=True))
        assoc_pass = abc_d == a_bc_d
        html += _property_card(
            "ASSOCIATIVITY",
            "merge(merge(A, B), C) must equal merge(A, merge(B, C))",
            assoc_pass,
            f'{_hash_display("(A*B)*C", abc_d)} {_hash_display("A*(B*C)", a_bc_d)}',
        )

    # Idempotency: merge(A,A) == A
    aa = nodes[0].merge(nodes[0])
    a_d = _sha256_short(json.dumps(nodes[0].digest(), sort_keys=True))
    aa_d = _sha256_short(json.dumps(aa.digest(), sort_keys=True))
    idemp_pass = a_d == aa_d
    html += _property_card(
        "IDEMPOTENCY",
        "merge(A, A) must equal A for all states",
        idemp_pass,
        f'{_hash_display("N0", a_d)} {_hash_display("merge(N0,N0)", aa_d)}',
    )

    # Final timing
    elapsed = (perf_counter() - t0) * 1000
    html += _stat_row([
        ("TOTAL ELAPSED", f"{elapsed:.1f}ms", True),
        ("PROPERTIES VERIFIED", "3/3" if (n >= 3) else f"{min(n, 3)}/{min(n + 1, 3)}", True),
    ])
    html += _data_ts()
    return html


# ---------------------------------------------------------------------------
# TAB 2: MERGE LAB
# ---------------------------------------------------------------------------


def tab2_merge_lab(strategy_name: str) -> str:
    t0 = perf_counter()
    models = _fetch_models(20)
    if not models:
        return _error_card("Could not fetch models from Hugging Face Hub.")

    records = [_model_to_record(m, i) for i, m in enumerate(models)]

    source_a = records[:14]
    source_b = []
    for r in records[7:20]:
        modified = dict(r)
        modified["downloads"] = int(modified["downloads"] * 1.15) + 42
        modified["likes"] = int(modified["likes"] * 0.9) + 7
        source_b.append(modified)

    # Map user-chosen strategy
    strategy_map = {"LWW": LWW(), "MAXWINS": MaxWins(), "MINWINS": MinWins()}
    strat = strategy_map.get(strategy_name.upper(), LWW())
    schema = MergeSchema(default=LWW(), downloads=strat, likes=strat)

    # -- PRE-MERGE --
    html = _section("PRE-MERGE STATE: DIVERGENT SOURCES")
    html += _stat_row([
        ("SOURCE A RECORDS", str(len(source_a)), False),
        ("SOURCE B RECORDS", str(len(source_b)), False),
        ("OVERLAP ZONE", f"RECORDS 8-14 ({min(len(source_a), 14) - 7} shared keys)", False),
        ("STRATEGY", strategy_name.upper(), True),
    ])

    html += f'<div style="font-size:0.68rem;color:{TEXT2};text-transform:uppercase;margin:10px 0 4px 0;">SOURCE A (first 10 shown)</div>'
    a_rows = [
        [r["id"][:42], _fmt_num(r["downloads"]), _fmt_num(r["likes"]),
         r["pipeline_tag"], r["author"][:20]]
        for r in source_a[:10]
    ]
    html += _table(["MODEL ID", "DOWNLOADS", "LIKES", "PIPELINE", "AUTHOR"], a_rows)

    html += f'<div style="font-size:0.68rem;color:{TEXT2};text-transform:uppercase;margin:10px 0 4px 0;">SOURCE B (first 10 shown)</div>'
    b_rows = [
        [r["id"][:42], _fmt_num(r["downloads"]), _fmt_num(r["likes"]),
         r["pipeline_tag"], r["author"][:20]]
        for r in source_b[:10]
    ]
    html += _table(["MODEL ID", "DOWNLOADS", "LIKES", "PIPELINE", "AUTHOR"], b_rows)

    # -- DIFF --
    html += _section("CONFLICT ANALYSIS: diff()")
    diff_t0 = perf_counter()
    diff_result = diff(source_a, source_b, key="id")
    diff_elapsed = (perf_counter() - diff_t0) * 1000

    n_added = len(diff_result.get("added", []))
    n_removed = len(diff_result.get("removed", []))
    modified_list = diff_result.get("modified", [])
    n_modified = len(modified_list)
    n_unchanged = diff_result.get("unchanged", 0)

    html += _stat_row([
        ("ADDED (B ONLY)", str(n_added), False),
        ("REMOVED (A ONLY)", str(n_removed), False),
        ("MODIFIED (CONFLICTS)", str(n_modified), True),
        ("UNCHANGED", str(n_unchanged), False),
        ("DIFF TIME", f"{diff_elapsed:.3f}ms", False),
    ])

    if modified_list:
        mod_rows = []
        for m in modified_list[:15]:
            key_val = m.get("key", "?")
            changes = m.get("changes", {})
            for field_name, ch in changes.items():
                old_v = ch.get("old", "?")
                new_v = ch.get("new", "?")
                delta = ""
                try:
                    delta = f" ({'+' if int(new_v) > int(old_v) else ''}{int(new_v) - int(old_v)})"
                except (ValueError, TypeError):
                    pass
                mod_rows.append([str(key_val)[:32], field_name, _fmt_num(old_v), _fmt_num(new_v), delta])
        html += _table(["KEY", "FIELD", "SOURCE A", "SOURCE B", "DELTA"], mod_rows)

    # -- MERGE WITH PROVENANCE --
    html += _section("POST-MERGE STATE: MERGE WITH PROVENANCE")
    merge_t0 = perf_counter()
    merged_data, prov_log = merge_with_provenance(source_a, source_b, key="id", schema=schema)
    merge_elapsed = (perf_counter() - merge_t0) * 1000

    html += _stat_row([
        ("MERGED ROWS", str(prov_log.total_rows), True),
        ("FROM BOTH SOURCES", str(prov_log.merged_rows), False),
        ("UNIQUE A", str(prov_log.unique_a_rows), False),
        ("UNIQUE B", str(prov_log.unique_b_rows), False),
        ("CONFLICTS RESOLVED", str(prov_log.total_conflicts), True),
        ("MERGE DURATION", f"{prov_log.duration_ms:.2f}ms", False),
    ])

    # Provenance detail table
    html += f'<div style="font-size:0.68rem;color:{TEXT2};text-transform:uppercase;margin:10px 0 4px 0;">PROVENANCE: CONFLICT RESOLUTION DECISIONS</div>'
    conflict_rows = []
    for rec in prov_log.records:
        for d in rec.conflicts:
            conflict_rows.append([
                str(rec.key)[:32],
                d.field,
                d.strategy,
                _fmt_num(d.value),
                _fmt_num(d.alternative),
                d.source,
            ])
    if conflict_rows:
        html += _table(["KEY", "FIELD", "STRATEGY", "CHOSEN", "ALTERNATIVE", "SOURCE"], conflict_rows[:25])
    else:
        html += _card(f'<span style="color:{TEXT2};font-size:0.8rem;">No conflicts detected -- all records reconciled automatically.</span>')

    # Provenance origin breakdown
    html += f'<div style="font-size:0.68rem;color:{TEXT2};text-transform:uppercase;margin:10px 0 4px 0;">RECORD ORIGIN MAP</div>'
    origin_rows = []
    for rec in prov_log.records:
        badge = _badge(rec.origin.upper(), "info" if rec.origin == "merged" else ("pass" if "a" in rec.origin else "warn"))
        origin_rows.append([str(rec.key)[:32], badge, str(rec.conflict_count)])
    html += _table(["KEY", "ORIGIN", "CONFLICTS"], origin_rows[:20])

    # Final merged table
    merged_list = merged_data if isinstance(merged_data, list) else list(merged_data)
    html += f'<div style="font-size:0.68rem;color:{TEXT2};text-transform:uppercase;margin:10px 0 4px 0;">MERGED OUTPUT (first 12 rows)</div>'
    m_rows = [
        [str(r.get("id", "?"))[:42], _fmt_num(r.get("downloads", 0)),
         _fmt_num(r.get("likes", 0)), str(r.get("pipeline_tag", "?")),
         str(r.get("author", "?"))[:20]]
        for r in merged_list[:12]
    ]
    html += _table(["MODEL ID", "DOWNLOADS", "LIKES", "PIPELINE", "AUTHOR"], m_rows)

    elapsed = (perf_counter() - t0) * 1000
    html += _stat_row([
        ("DIFF TIME", f"{diff_elapsed:.3f}ms", False),
        ("MERGE TIME", f"{merge_elapsed:.3f}ms", False),
        ("TOTAL ELAPSED", f"{elapsed:.1f}ms", True),
    ])
    html += _data_ts()
    return html


# ---------------------------------------------------------------------------
# TAB 3: GOSSIP PROTOCOL
# ---------------------------------------------------------------------------


def tab3_gossip(node_count: int, rounds: int) -> str:
    t0 = perf_counter()
    models = _fetch_models(25)
    datasets = _fetch_datasets(15)
    if not models:
        return _error_card("Could not fetch data from Hugging Face Hub.")

    all_records = [_model_to_record(m, i) for i, m in enumerate(models)]
    all_records += [_dataset_to_record(d, i + 100) for i, d in enumerate(datasets)]

    n = int(node_count)
    r = int(rounds)

    # Build nodes with random 70% subsets
    nodes: List[GossipState] = []
    node_sizes: List[int] = []
    for i in range(n):
        gs = GossipState(f"gossip-{i}")
        subset = random.sample(all_records, k=int(len(all_records) * 0.7))
        for rec in subset:
            gs.update(rec["id"], rec)
        nodes.append(gs)
        node_sizes.append(len(subset))

    # -- PRE STATE --
    html = _section("PRE-GOSSIP STATE: INITIAL DIVERGENT NODES")
    pre_rows = []
    pre_digests = []
    for i, gs in enumerate(nodes):
        d = gs.digest()
        h = _sha256_short(json.dumps(d, sort_keys=True))
        pre_digests.append(h)
        pre_rows.append([f"GOSSIP-{i}", str(node_sizes[i]), str(gs.size), h])
    html += _table(["NODE", "INPUT RECORDS", "STATE SIZE", "STATE DIGEST"], pre_rows)

    unique_pre = len(set(pre_digests))
    html += _stat_row([
        ("NODES", str(n), False),
        ("TOTAL RECORDS", str(len(all_records)), False),
        ("UNIQUE STATES (PRE)", str(unique_pre), False),
        ("SUBSET RATIO", "70%", False),
    ])

    # -- GOSSIP ROUNDS --
    html += _section("GOSSIP ROUNDS: PAIRWISE STATE PROPAGATION")
    timeline_rows = []
    convergence_history: List[int] = [unique_pre]

    for round_num in range(1, r + 1):
        i_idx, j_idx = random.sample(range(n), 2)
        rt0 = perf_counter()
        merged_ij = nodes[i_idx].merge(nodes[j_idx])
        merged_ji = nodes[j_idx].merge(nodes[i_idx])
        # Propagate merged state back
        nodes[i_idx] = merged_ij
        nodes[j_idx] = merged_ji
        rt1 = perf_counter()

        unique_now = len(set(
            _sha256_short(json.dumps(gs.digest(), sort_keys=True)) for gs in nodes
        ))
        convergence_history.append(unique_now)
        timeline_rows.append([
            f"ROUND {round_num:02d}",
            f"N{i_idx} <-> N{j_idx}",
            str(nodes[i_idx].size),
            str(unique_now),
            _badge("CONVERGED" if unique_now == 1 else f"{unique_now} STATES",
                   "pass" if unique_now == 1 else "warn"),
            f"{(rt1 - rt0) * 1000:.3f}ms",
        ])

    html += _table(["ROUND", "PAIR", "MERGED SIZE", "UNIQUE STATES", "STATUS", "TIME"], timeline_rows)

    # Convergence progress bar
    html += f'<div style="font-size:0.68rem;color:{TEXT2};text-transform:uppercase;margin:10px 0 4px 0;">CONVERGENCE TRAJECTORY</div>'
    bar_width = 600
    max_states = max(convergence_history) if convergence_history else 1
    bar_html = f'<div style="display:flex;gap:2px;align-items:flex-end;height:40px;">'
    for idx, s in enumerate(convergence_history):
        pct = s / max_states if max_states > 0 else 0
        h = max(4, int(pct * 36))
        c = ACCENT if s == 1 else DIM
        bar_html += f'<div style="width:{max(4, bar_width // len(convergence_history))}px;height:{h}px;background:{c};border-radius:2px;" title="Round {idx}: {s} states"></div>'
    bar_html += '</div>'
    html += bar_html

    # -- POST STATE --
    html += _section("POST-GOSSIP STATE: FINAL NODE STATES")
    post_rows = []
    post_digests = []
    for i, gs in enumerate(nodes):
        d = gs.digest()
        h = _sha256_short(json.dumps(d, sort_keys=True))
        post_digests.append(h)
        post_rows.append([f"GOSSIP-{i}", str(gs.size), h])
    html += _table(["NODE", "SIZE", "STATE DIGEST"], post_rows)

    unique_post = len(set(post_digests))
    converged = unique_post == 1
    html += _stat_row([
        ("UNIQUE STATES (POST)", str(unique_post), converged),
        ("CONVERGED", "YES" if converged else "NO", converged),
        ("ROUNDS TO CONVERGENCE", str(next((i for i, s in enumerate(convergence_history) if s == 1), r)) if converged else "N/A", converged),
    ])

    # -- ANTI-ENTROPY --
    if n >= 2:
        html += _section("ANTI-ENTROPY VERIFICATION: NODE 0 vs NODE 1")
        d0 = nodes[0].digest()
        d1 = nodes[1].digest()
        push_keys = nodes[0].anti_entropy_push(d1)
        pull_keys = nodes[0].anti_entropy_pull(d1)
        synced = len(push_keys) == 0 and len(pull_keys) == 0
        html += _stat_row([
            ("KEYS TO PUSH (0->1)", str(len(push_keys)), False),
            ("KEYS TO PULL (1->0)", str(len(pull_keys)), False),
            ("SYNC STATUS", "FULLY SYNCHRONIZED" if synced else "DELTA REMAINING", synced),
        ])
        if push_keys:
            html += f'<div style="font-size:0.68rem;color:{TEXT2};margin:4px 0;">PUSH KEYS: {", ".join(list(push_keys)[:5])}</div>'
        if pull_keys:
            html += f'<div style="font-size:0.68rem;color:{TEXT2};margin:4px 0;">PULL KEYS: {", ".join(list(pull_keys)[:5])}</div>'

    # -- VECTOR CLOCKS --
    html += _section("VECTOR CLOCK STATE")
    vc_rows = []
    for i, gs in enumerate(nodes[:min(n, 6)]):
        vc = gs.clock
        vc_val = vc.value if vc else {}
        entries = list(vc_val.items())[:5] if vc_val else []
        vc_str = ", ".join(f"{k}:{v}" for k, v in entries) if entries else "{}"
        if len(vc_val) > 5:
            vc_str += f" ... (+{len(vc_val) - 5} more)"
        vc_rows.append([f"GOSSIP-{i}", str(len(vc_val)), vc_str[:80]])
    html += _table(["NODE", "CLOCK ENTRIES", "VECTOR CLOCK (PARTIAL)"], vc_rows)

    elapsed = (perf_counter() - t0) * 1000
    html += _stat_row([("TOTAL ELAPSED", f"{elapsed:.1f}ms", True)])
    html += _data_ts()
    return html


# ---------------------------------------------------------------------------
# TAB 4: MULTI-AGENT
# ---------------------------------------------------------------------------


def tab4_multi_agent() -> str:
    t0 = perf_counter()
    models = _fetch_models(20)
    datasets = _fetch_datasets(15)
    if not models:
        return _error_card("Could not fetch data from Hugging Face Hub.")

    ts_base = time.time()

    # -- Agent 1: model-analyst --
    analyst = AgentState(agent_id="model-analyst")
    for i, m in enumerate(models[:10]):
        mid = getattr(m, "id", f"model-{i}") or f"model-{i}"
        dl = getattr(m, "downloads", 0) or 0
        pipe = getattr(m, "pipeline_tag", "unknown") or "unknown"
        analyst.add_fact(f"model:{mid}:downloads", dl, confidence=0.85, timestamp=ts_base + i * 0.001)
        analyst.add_fact(f"model:{mid}:pipeline", pipe, confidence=0.80, timestamp=ts_base + i * 0.001)
    analyst.add_tag("model-analysis")
    analyst.add_tag("downloads-tracking")
    analyst.increment("models_analyzed", len(models[:10]))
    analyst.append_message("Analyzed top 10 models by download count", role="agent")

    # -- Agent 2: dataset-intel --
    intel = AgentState(agent_id="dataset-intel")
    for i, d in enumerate(datasets[:10]):
        did = getattr(d, "id", f"dataset-{i}") or f"dataset-{i}"
        dl = getattr(d, "downloads", 0) or 0
        intel.add_fact(f"dataset:{did}:downloads", dl, confidence=0.90, timestamp=ts_base + i * 0.001)
    intel.add_tag("dataset-analysis")
    intel.add_tag("downloads-tracking")
    intel.increment("datasets_analyzed", len(datasets[:10]))
    intel.append_message("Analyzed top 10 datasets by download count", role="agent")

    # -- Agent 3: trend-analyst (overlapping with higher confidence) --
    trend = AgentState(agent_id="trend-analyst")
    for i, m in enumerate(models[:10]):
        mid = getattr(m, "id", f"model-{i}") or f"model-{i}"
        likes = getattr(m, "likes", 0) or 0
        dl = getattr(m, "downloads", 0) or 0
        trend.add_fact(f"model:{mid}:downloads", dl, confidence=0.95, timestamp=ts_base + 10 + i * 0.001)
        trend.add_fact(f"model:{mid}:trend_score", likes * 2 + dl, confidence=0.75, timestamp=ts_base + i * 0.001)
    trend.add_tag("trending")
    trend.add_tag("model-analysis")
    trend.increment("models_analyzed", len(models[:10]))
    trend.append_message("Computed trend scores for top models", role="agent")

    # -- PRE-MERGE --
    html = _section("PRE-MERGE STATE: INDIVIDUAL AGENT KNOWLEDGE")
    agents_data = [
        ("MODEL-ANALYST", analyst),
        ("DATASET-INTEL", intel),
        ("TREND-ANALYST", trend),
    ]
    summary_rows = []
    for name, ag in agents_data:
        facts = ag.list_facts()
        summary_rows.append([
            name,
            ag.agent_id,
            str(len(facts)),
            str(len(ag.tags)),
            ", ".join(sorted(ag.tags)),
            str(ag.counter_value("models_analyzed") + ag.counter_value("datasets_analyzed")),
            str(len(ag.messages)),
        ])
    html += _table(["AGENT", "ID", "FACTS", "TAGS", "TAG LIST", "ITEMS PROCESSED", "MESSAGES"], summary_rows)

    # Sample facts per agent
    for name, ag in agents_data:
        facts = ag.list_facts()
        sample_rows = []
        for k, f in list(facts.items())[:6]:
            sample_rows.append([
                k[:48],
                str(f.value)[:24],
                f"{f.confidence:.2f}",
                f.source_agent,
            ])
        html += f'<div style="font-size:0.68rem;color:{ACCENT};text-transform:uppercase;margin:12px 0 4px 0;">{name}: SAMPLE FACTS</div>'
        html += _table(["FACT KEY", "VALUE", "CONFIDENCE", "SOURCE AGENT"], sample_rows)

    # -- MERGE --
    html += _section("POST-MERGE STATE: SHARED KNOWLEDGE")
    merge_t0 = perf_counter()
    shared = SharedKnowledge.merge(analyst, intel, trend)
    merge_elapsed = (perf_counter() - merge_t0) * 1000

    merged_facts = shared.state.list_facts()
    merged_tags = shared.state.tags

    html += _stat_row([
        ("CONTRIBUTING AGENTS", str(len(shared.contributing_agents)), True),
        ("AGENT IDS", ", ".join(shared.contributing_agents), False),
        ("MERGED FACTS", str(len(merged_facts)), True),
        ("UNION TAGS", str(len(merged_tags)), False),
    ])

    html += f'<div style="font-size:0.68rem;color:{TEXT2};text-transform:uppercase;margin:10px 0 4px 0;">MERGED TAG SET (UNION)</div>'
    tag_html = " ".join(_badge(t, "info") for t in sorted(merged_tags))
    html += f'<div style="margin:4px 0;display:flex;flex-wrap:wrap;gap:4px;">{tag_html}</div>'

    # Counter merge
    html += f'<div style="font-size:0.68rem;color:{TEXT2};text-transform:uppercase;margin:10px 0 4px 0;">MERGED COUNTERS (SUMMED ACROSS AGENTS)</div>'
    counter_rows = []
    for cname in ["models_analyzed", "datasets_analyzed"]:
        pre_vals = " + ".join(str(ag.counter_value(cname)) for _, ag in agents_data)
        merged_val = shared.state.counter_value(cname)
        counter_rows.append([cname.upper(), pre_vals, str(merged_val)])
    html += _table(["COUNTER", "INDIVIDUAL VALUES", "MERGED SUM"], counter_rows)

    # -- CONFIDENCE RESOLUTION EXAMPLES --
    html += _section("CONFIDENCE-BASED FACT RESOLUTION")
    html += f'<div style="font-size:0.72rem;color:{TEXT2};margin:4px 0;">When multiple agents contribute the same fact key, the highest-confidence value wins.</div>'
    conf_rows = []
    for k, f in list(merged_facts.items())[:20]:
        conf_rows.append([
            k[:50],
            str(f.value)[:24],
            f"{f.confidence:.2f}",
            f.source_agent,
            _badge("HIGH" if f.confidence >= 0.9 else "MED" if f.confidence >= 0.8 else "LOW",
                   "pass" if f.confidence >= 0.9 else "info" if f.confidence >= 0.8 else "warn"),
        ])
    html += _table(["FACT KEY", "WINNING VALUE", "CONFIDENCE", "SOURCE AGENT", "LEVEL"], conf_rows)

    # Messages log
    html += _section("MERGED MESSAGE LOG")
    msgs = shared.state.messages
    msg_rows = []
    for m in msgs[:10]:
        role = m.get("role", "?") if isinstance(m, dict) else getattr(m, "role", "?")
        agent = m.get("agent_id", "?") if isinstance(m, dict) else getattr(m, "agent_id", "?")
        content = m.get("content", "?") if isinstance(m, dict) else getattr(m, "content", "?")
        msg_rows.append([str(role)[:10], str(agent), str(content)[:60]])
    html += _table(["ROLE", "AGENT", "CONTENT"], msg_rows)

    elapsed = (perf_counter() - t0) * 1000
    html += _stat_row([
        ("MERGE TIME", f"{merge_elapsed:.3f}ms", False),
        ("TOTAL ELAPSED", f"{elapsed:.1f}ms", True),
    ])
    html += _data_ts()
    return html


# ---------------------------------------------------------------------------
# TAB 5: CRDT PRIMITIVES
# ---------------------------------------------------------------------------


def tab5_primitives() -> str:
    t0 = perf_counter()
    models = _fetch_models(10)
    if not models:
        return _error_card("Could not fetch models from Hugging Face Hub.")

    html = ""

    # ---- 1. GCOUNTER ----
    html += _section("1. GCOUNTER -- DISTRIBUTED DOWNLOAD TRACKING")
    m0 = models[0]
    dl = getattr(m0, "downloads", 100000) or 100000
    model_name = getattr(m0, "id", "model") or "model"
    region_a = dl // 3
    region_b = dl // 3
    region_c = dl - region_a - region_b

    gc_us = GCounter("us-east", region_a)
    gc_eu = GCounter("eu-west", region_b)
    gc_ap = GCounter("ap-south", region_c)

    html += _card(
        f'<div style="color:{TEXT2};font-size:0.78rem;">Tracking downloads for '
        f'<span style="color:{ACCENT};font-weight:600;">{model_name}</span> '
        f'across 3 geographic regions. Real download count: '
        f'<span style="color:{ACCENT};font-weight:600;">{_fmt_num(dl)}</span></div>'
    )

    pre_rows = [
        ["US-EAST", _fmt_num(gc_us.value), _fmt_num(region_a)],
        ["EU-WEST", _fmt_num(gc_eu.value), _fmt_num(region_b)],
        ["AP-SOUTH", _fmt_num(gc_ap.value), _fmt_num(region_c)],
    ]
    html += _table(["REGION", "COUNTER VALUE", "ATTRIBUTED"], pre_rows)

    merged_gc = gc_us.merge(gc_eu).merge(gc_ap)
    gc_ab = gc_us.merge(gc_eu)
    gc_ba = gc_eu.merge(gc_us)
    gc_aa = gc_us.merge(gc_us)
    comm = gc_ab.value == gc_ba.value
    idemp = gc_aa.value == gc_us.value

    html += _stat_row([
        ("MERGED TOTAL", _fmt_num(merged_gc.value), True),
        ("EXPECTED", _fmt_num(dl), False),
        ("COMMUTATIVITY", "PASS" if comm else "FAIL", comm),
        ("IDEMPOTENCY", "PASS" if idemp else "FAIL", idemp),
    ])

    # ---- 2. PNCOUNTER ----
    html += _section("2. PNCOUNTER -- MODEL RATING (UP/DOWN VOTES)")
    m1 = models[1] if len(models) > 1 else models[0]
    likes = getattr(m1, "likes", 500) or 500
    model_name2 = getattr(m1, "id", "model") or "model"

    pn_a = PNCounter()
    pn_a.increment("reviewer-a", likes)
    pn_a.decrement("reviewer-a", likes // 10)

    pn_b = PNCounter()
    pn_b.increment("reviewer-b", likes // 2)
    pn_b.decrement("reviewer-b", likes // 5)

    merged_pn = pn_a.merge(pn_b)
    pn_ab = pn_a.merge(pn_b)
    pn_ba = pn_b.merge(pn_a)
    pn_comm = pn_ab.value == pn_ba.value
    pn_idemp = pn_a.merge(pn_a).value == pn_a.value

    html += _card(
        f'<div style="color:{TEXT2};font-size:0.78rem;">Rating model '
        f'<span style="color:{ACCENT};font-weight:600;">{model_name2}</span> '
        f'-- Real likes: <span style="color:{ACCENT};font-weight:600;">{_fmt_num(likes)}</span></div>'
    )
    html += _table(
        ["REVIEWER", "UPVOTES", "DOWNVOTES", "NET"],
        [
            ["REVIEWER-A", _fmt_num(likes), _fmt_num(likes // 10), str(pn_a.value)],
            ["REVIEWER-B", _fmt_num(likes // 2), _fmt_num(likes // 5), str(pn_b.value)],
        ]
    )
    html += _stat_row([
        ("REVIEWER A NET", str(pn_a.value), False),
        ("REVIEWER B NET", str(pn_b.value), False),
        ("MERGED NET", str(merged_pn.value), True),
        ("COMMUTATIVITY", "PASS" if pn_comm else "FAIL", pn_comm),
        ("IDEMPOTENCY", "PASS" if pn_idemp else "FAIL", pn_idemp),
    ])

    # ---- 3. LWWRegister ----
    html += _section("3. LWWREGISTER -- CONCURRENT MODEL NAME UPDATES")
    m2 = models[2] if len(models) > 2 else models[0]
    real_name = getattr(m2, "id", "model-name") or "model-name"
    ts_now = time.time()

    reg_a = LWWRegister(real_name + "-v1", ts_now - 10, "editor-a")
    reg_b = LWWRegister(real_name + "-v2", ts_now - 5, "editor-b")
    reg_c = LWWRegister(real_name + "-v3", ts_now, "editor-c")

    merged_reg = reg_a.merge(reg_b).merge(reg_c)
    reg_ba = reg_b.merge(reg_a)
    reg_ab = reg_a.merge(reg_b)
    lww_comm = reg_ab.value == reg_ba.value
    lww_idemp = reg_a.merge(reg_a).value == reg_a.value

    html += _table(
        ["EDITOR", "VALUE", "TIMESTAMP OFFSET", "NODE"],
        [
            ["EDITOR-A", str(reg_a.value)[:40], "t - 10s", "editor-a"],
            ["EDITOR-B", str(reg_b.value)[:40], "t - 5s", "editor-b"],
            ["EDITOR-C", str(reg_c.value)[:40], "t - 0s (LATEST)", "editor-c"],
        ]
    )
    html += _stat_row([
        ("WINNER", str(merged_reg.value)[:40], True),
        ("RESOLUTION", "LATEST TIMESTAMP", False),
        ("COMMUTATIVITY", "PASS" if lww_comm else "FAIL", lww_comm),
        ("IDEMPOTENCY", "PASS" if lww_idemp else "FAIL", lww_idemp),
    ])

    # ---- 4. ORSet ----
    html += _section("4. ORSET -- OBSERVED-REMOVE SET (MODEL TAGS)")
    m3 = models[3] if len(models) > 3 else models[0]
    real_tags = list(getattr(m3, "tags", []) or [])[:6]
    if len(real_tags) < 3:
        real_tags = ["text-generation", "pytorch", "en", "transformers"]

    set_a = ORSet()
    set_b = ORSet()
    for t in real_tags[:3]:
        set_a.add(t)
    for t in real_tags[1:]:
        set_b.add(t)
    set_b.add("custom-tag-b")
    set_a.add("custom-tag-a")
    if real_tags:
        set_a.remove(real_tags[0])

    merged_set = set_a.merge(set_b)
    set_ab = set_a.merge(set_b)
    set_ba = set_b.merge(set_a)
    orset_comm = set_ab.value == set_ba.value
    orset_idemp = set_a.merge(set_a).value == set_a.value

    html += _table(
        ["SET", "OPERATION LOG", "ELEMENTS"],
        [
            ["SET A", f"add({', '.join(real_tags[:3])}), add(custom-tag-a), remove({real_tags[0]})", ", ".join(sorted(set_a.value))],
            ["SET B", f"add({', '.join(real_tags[1:])}), add(custom-tag-b)", ", ".join(sorted(set_b.value))],
            ["MERGED", "OR-merge (add wins over concurrent remove)", ", ".join(sorted(merged_set.value))],
        ]
    )
    html += _stat_row([
        ("SET A SIZE", str(len(set_a.value)), False),
        ("SET B SIZE", str(len(set_b.value)), False),
        ("MERGED SIZE", str(len(merged_set.value)), True),
        ("COMMUTATIVITY", "PASS" if orset_comm else "FAIL", orset_comm),
        ("IDEMPOTENCY", "PASS" if orset_idemp else "FAIL", orset_idemp),
    ])

    # ---- 5. LWWMap ----
    html += _section("5. LWWMAP -- LAST-WRITER-WINS MAP (MODEL METADATA)")
    m4 = models[4] if len(models) > 4 else models[0]
    ts_base = time.time()

    map_a = LWWMap()
    map_a.set("name", getattr(m4, "id", "model") or "model", timestamp=ts_base, node_id="node-a")
    map_a.set("downloads", str(getattr(m4, "downloads", 0) or 0), timestamp=ts_base, node_id="node-a")
    map_a.set("status", "active", timestamp=ts_base, node_id="node-a")

    map_b = LWWMap()
    map_b.set("name", (getattr(m4, "id", "model") or "model") + "-updated", timestamp=ts_base + 1, node_id="node-b")
    map_b.set("downloads", str((getattr(m4, "downloads", 0) or 0) + 1000), timestamp=ts_base + 2, node_id="node-b")
    map_b.set("region", "eu-west", timestamp=ts_base + 1, node_id="node-b")

    merged_map = map_a.merge(map_b)
    map_ab = map_a.merge(map_b)
    map_ba = map_b.merge(map_a)
    map_comm = map_ab.value == map_ba.value
    map_idemp = map_a.merge(map_a).value == map_a.value

    html += _table(
        ["KEY", "MAP A (t=0)", "MAP B (t=+1/+2)", "MERGED (LWW)"],
        [
            ["name", str(map_a.get("name"))[:30], str(map_b.get("name"))[:30], str(merged_map.get("name"))[:30]],
            ["downloads", str(map_a.get("downloads")), str(map_b.get("downloads")), str(merged_map.get("downloads"))],
            ["status", str(map_a.get("status")), str(map_b.get("status", "N/A")), str(merged_map.get("status", "N/A"))],
            ["region", str(map_a.get("region", "N/A")), str(map_b.get("region")), str(merged_map.get("region", "N/A"))],
        ]
    )
    html += _stat_row([
        ("MAP A KEYS", str(len(map_a.value)), False),
        ("MAP B KEYS", str(len(map_b.value)), False),
        ("MERGED KEYS", str(len(merged_map.value)), True),
        ("COMMUTATIVITY", "PASS" if map_comm else "FAIL", map_comm),
        ("IDEMPOTENCY", "PASS" if map_idemp else "FAIL", map_idemp),
    ])

    # Summary
    html += _section("PRIMITIVE VERIFICATION SUMMARY")
    summary_rows = [
        ["GCOUNTER", _badge("PASS" if comm else "FAIL", "pass" if comm else "fail"),
         _badge("PASS" if idemp else "FAIL", "pass" if idemp else "fail")],
        ["PNCOUNTER", _badge("PASS" if pn_comm else "FAIL", "pass" if pn_comm else "fail"),
         _badge("PASS" if pn_idemp else "FAIL", "pass" if pn_idemp else "fail")],
        ["LWWREGISTER", _badge("PASS" if lww_comm else "FAIL", "pass" if lww_comm else "fail"),
         _badge("PASS" if lww_idemp else "FAIL", "pass" if lww_idemp else "fail")],
        ["ORSET", _badge("PASS" if orset_comm else "FAIL", "pass" if orset_comm else "fail"),
         _badge("PASS" if orset_idemp else "FAIL", "pass" if orset_idemp else "fail")],
        ["LWWMAP", _badge("PASS" if map_comm else "FAIL", "pass" if map_comm else "fail"),
         _badge("PASS" if map_idemp else "FAIL", "pass" if map_idemp else "fail")],
    ]
    html += _table(["PRIMITIVE", "COMMUTATIVITY", "IDEMPOTENCY"], summary_rows)

    elapsed = (perf_counter() - t0) * 1000
    html += _stat_row([("TOTAL ELAPSED", f"{elapsed:.1f}ms", True), ("PRIMITIVES TESTED", "5", True)])
    html += _data_ts()
    return html


# ---------------------------------------------------------------------------
# TAB 6: DEDUP
# ---------------------------------------------------------------------------


def tab6_dedup() -> str:
    t0 = perf_counter()
    models = _fetch_models(20)
    if not models:
        return _error_card("Could not fetch models from Hugging Face Hub.")

    records = [_model_to_record(m, i) for i, m in enumerate(models)]

    # ---- EXACT DEDUP ----
    html = _section("EXACT DEDUPLICATION")
    duped_records = list(records)
    for r in records[:5]:
        duped_records.append(dict(r))  # exact copy

    html += _stat_row([
        ("ORIGINAL RECORDS", str(len(records)), False),
        ("INJECTED DUPLICATES", str(len(duped_records) - len(records)), False),
        ("TOTAL INPUT", str(len(duped_records)), False),
    ])

    html += f'<div style="font-size:0.68rem;color:{TEXT2};text-transform:uppercase;margin:10px 0 4px 0;">PRE-DEDUP: INPUT RECORDS (first 8 shown)</div>'
    pre_rows = [[r["id"][:40], _fmt_num(r["downloads"]), _fmt_num(r["likes"]), r["pipeline_tag"]] for r in duped_records[:8]]
    html += _table(["MODEL ID", "DOWNLOADS", "LIKES", "PIPELINE"], pre_rows)

    dedup_t0 = perf_counter()
    unique_records, num_removed = dedup_records(duped_records, method="exact")
    dedup_elapsed = (perf_counter() - dedup_t0) * 1000

    html += f'<div style="font-size:0.68rem;color:{TEXT2};text-transform:uppercase;margin:10px 0 4px 0;">POST-DEDUP: UNIQUE RECORDS (first 8 shown)</div>'
    post_rows = [[r["id"][:40], _fmt_num(r["downloads"]), _fmt_num(r["likes"]), r["pipeline_tag"]] for r in unique_records[:8]]
    html += _table(["MODEL ID", "DOWNLOADS", "LIKES", "PIPELINE"], post_rows)

    html += _stat_row([
        ("UNIQUE RECORDS", str(len(unique_records)), True),
        ("DUPLICATES REMOVED", str(num_removed), True),
        ("REDUCTION", f"{(num_removed / len(duped_records) * 100):.1f}%" if duped_records else "0%", True),
        ("DEDUP TIME", f"{dedup_elapsed:.3f}ms", False),
    ])

    # ---- FUZZY DEDUP ----
    html += _section("FUZZY DEDUPLICATION: MODEL NAMES")
    model_names = [str(getattr(m, "id", f"model-{i}") or f"model-{i}") for i, m in enumerate(models)]
    near_dupes = list(model_names)
    for name in model_names[:5]:
        parts = name.split("/")
        if len(parts) > 1:
            near_dupes.append(parts[0] + "/" + parts[1] + "-v2")
        else:
            near_dupes.append(name + "-variant")

    html += f'<div style="font-size:0.68rem;color:{TEXT2};text-transform:uppercase;margin:10px 0 4px 0;">PRE-DEDUP: INPUT NAMES</div>'
    pre_name_rows = [[n[:60], _badge("ORIGINAL" if i < len(model_names) else "NEAR-DUP", "info" if i < len(model_names) else "warn")] for i, n in enumerate(near_dupes)]
    html += _table(["NAME", "TYPE"], pre_name_rows[:15])

    html += _stat_row([
        ("INPUT NAMES", str(len(near_dupes)), False),
        ("ORIGINAL", str(len(model_names)), False),
        ("NEAR-DUPLICATES ADDED", str(len(near_dupes) - len(model_names)), False),
    ])

    fuzzy_t0 = perf_counter()
    unique_names, dup_indices = dedup_list(near_dupes, method="fuzzy", threshold=0.85)
    fuzzy_elapsed = (perf_counter() - fuzzy_t0) * 1000

    html += f'<div style="font-size:0.68rem;color:{TEXT2};text-transform:uppercase;margin:10px 0 4px 0;">POST-DEDUP: UNIQUE NAMES</div>'
    name_rows = [[n[:60]] for n in unique_names[:12]]
    html += _table(["UNIQUE MODEL NAME"], name_rows)

    html += _stat_row([
        ("UNIQUE NAMES", str(len(unique_names)), True),
        ("FUZZY MATCHES REMOVED", str(len(dup_indices)), True),
        ("THRESHOLD", "0.85", False),
        ("FUZZY TIME", f"{fuzzy_elapsed:.3f}ms", False),
    ])

    if dup_indices:
        html += f'<div style="font-size:0.68rem;color:{TEXT2};margin:4px 0;">DUPLICATE INDICES: {dup_indices[:10]}</div>'

    # ---- DISTRIBUTED DEDUP INDEX ----
    html += _section("DISTRIBUTED DEDUP INDEX: MERGE")
    idx_a = DedupIndex(node_id="worker-a")
    idx_b = DedupIndex(node_id="worker-b")

    for r in records[:10]:
        idx_a.add_exact(json.dumps(r, sort_keys=True))
    for r in records[8:]:
        idx_b.add_exact(json.dumps(r, sort_keys=True))

    merged_idx = idx_a.merge(idx_b)

    html += _table(
        ["INDEX", "SIZE", "NODE"],
        [
            ["WORKER-A", str(idx_a.size), "worker-a"],
            ["WORKER-B", str(idx_b.size), "worker-b"],
            ["MERGED", str(merged_idx.size), "merged"],
        ]
    )
    html += _stat_row([
        ("WORKER A", str(idx_a.size), False),
        ("WORKER B", str(idx_b.size), False),
        ("MERGED INDEX", str(merged_idx.size), True),
        ("OVERLAP DEDUPED", str(idx_a.size + idx_b.size - merged_idx.size), True),
    ])

    elapsed = (perf_counter() - t0) * 1000
    html += _stat_row([("TOTAL ELAPSED", f"{elapsed:.1f}ms", True)])
    html += _data_ts()
    return html


# ---------------------------------------------------------------------------
# TAB 7: COMPLIANCE
# ---------------------------------------------------------------------------


def tab7_compliance() -> str:
    t0 = perf_counter()
    models = _fetch_models(10)
    if not models:
        return _error_card("Could not fetch models from Hugging Face Hub.")

    records = [_model_to_record(m, i) for i, m in enumerate(models)]
    source_a = records[:7]
    source_b = []
    for r in records[4:]:
        modified = dict(r)
        modified["downloads"] = int(modified["downloads"] * 1.1) + 10
        source_b.append(modified)

    merged_data, prov_log = merge_with_provenance(source_a, source_b, key="id")

    html = _section("COMPLIANCE AUDIT: 4 REGULATORY FRAMEWORKS")
    html += _stat_row([
        ("SOURCE A", str(len(source_a)), False),
        ("SOURCE B", str(len(source_b)), False),
        ("MERGED", str(prov_log.total_rows), False),
        ("CONFLICTS", str(prov_log.total_conflicts), False),
    ])

    frameworks = ["eu_ai_act", "gdpr", "hipaa", "sox"]
    framework_results = []

    for fw in frameworks:
        html += f'<div style="margin:20px 0 8px 0;font-size:0.9rem;color:{ACCENT};' \
                f'text-transform:uppercase;font-weight:700;letter-spacing:0.08em;' \
                f'border-left:3px solid {ACCENT};padding-left:10px;">{fw.replace("_", " ").upper()}</div>'

        try:
            auditor = ComplianceAuditor(framework=fw, node_id="demo-node")

            auditor.record_merge(
                operation="merge_with_provenance",
                input_hash=_sha256_short(json.dumps([source_a, source_b], default=str)),
                output_hash=_sha256_short(json.dumps(merged_data if isinstance(merged_data, list) else [], default=str)),
                metadata={"records_a": len(source_a), "records_b": len(source_b)},
            )
            auditor.record_unmerge(
                subject_id="source_b",
                fields_removed=["downloads", "likes", "pipeline_tag"],
                metadata={"reason": "data_subject_request", "framework": fw},
            )
            auditor.record_access(
                user_id="admin@enterprise.com",
                operation="read",
                resource="merged_dataset",
                granted=True,
                metadata={"ip": "10.0.0.1"},
            )
            auditor.record_access(
                user_id="analyst@enterprise.com",
                operation="write",
                resource="merged_dataset",
                granted=False,
                metadata={"reason": "insufficient_permissions"},
            )

            report = auditor.validate()

            status_map = {"compliant": "pass", "partial": "warn", "non_compliant": "fail"}
            status_badge = _badge(
                report.status.upper().replace("_", " "),
                status_map.get(report.status, "info"),
            )

            pass_count = sum(1 for f in report.findings if f.status == "pass")
            fail_count = sum(1 for f in report.findings if f.status == "fail")
            na_count = sum(1 for f in report.findings if f.status == "not_applicable")

            html += f'<div style="margin:6px 0;">STATUS: {status_badge}</div>'
            html += _stat_row([
                ("FINDINGS", str(len(report.findings)), False),
                ("PASSED", str(pass_count), pass_count > 0),
                ("FAILED", str(fail_count), False),
                ("N/A", str(na_count), False),
            ])

            finding_rows = []
            for f in report.findings:
                sev_badge = _badge(f.severity.upper(),
                                   "fail" if f.severity == "critical" else
                                   ("warn" if f.severity == "warning" else "info"))
                st_badge = _badge(f.status.upper(),
                                  "pass" if f.status == "pass" else
                                  ("fail" if f.status == "fail" else "info"))
                finding_rows.append([
                    f.rule_id,
                    sev_badge,
                    st_badge,
                    f.description[:90],
                ])
            html += _table(["RULE ID", "SEVERITY", "STATUS", "DESCRIPTION"], finding_rows)

            framework_results.append((fw, report.status, len(report.findings), pass_count, fail_count))

        except Exception as exc:
            html += _card(f'<span style="color:#EF4444;">Framework {fw} error: {str(exc)[:200]}</span>')
            framework_results.append((fw, "error", 0, 0, 0))

    # Summary across all frameworks
    html += _section("CROSS-FRAMEWORK COMPLIANCE SUMMARY")
    fw_summary_rows = []
    for fw, status, total, passed, failed in framework_results:
        status_map = {"compliant": "pass", "partial": "warn", "non_compliant": "fail", "error": "fail"}
        fw_summary_rows.append([
            fw.upper().replace("_", " "),
            _badge(status.upper().replace("_", " "), status_map.get(status, "info")),
            str(total),
            str(passed),
            str(failed),
        ])
    html += _table(["FRAMEWORK", "STATUS", "TOTAL FINDINGS", "PASSED", "FAILED"], fw_summary_rows)

    # ---- AUDITED MERGE CHAIN ----
    html += _section("AUDITED MERGE: TAMPER-EVIDENT HASH CHAIN")
    try:
        audited = AuditedMerge(node_id="audit-demo")
        merged_result, audit_entry = audited.merge(source_a, source_b, key="id")
        source_c = records[:3]
        merged_result2, audit_entry2 = audited.merge(
            merged_result if isinstance(merged_result, list) else list(merged_result),
            source_c,
            key="id",
        )

        chain_valid = audited.audit_log.verify_chain()
        entries = audited.audit_log.entries

        html += _stat_row([
            ("CHAIN LENGTH", str(len(entries)), False),
            ("CHAIN INTEGRITY", "VALID" if chain_valid else "BROKEN", chain_valid),
        ])

        entry_rows = []
        for e in entries:
            verified = e.verify()
            entry_rows.append([
                e.entry_id[:16] + "...",
                e.operation[:20],
                e.node_id,
                e.input_hash[:20] + "...",
                e.output_hash[:20] + "...",
                e.entry_hash[:16] + "...",
                _badge("VALID" if verified else "INVALID", "pass" if verified else "fail"),
            ])
        html += _table(["ENTRY ID", "OPERATION", "NODE", "INPUT HASH", "OUTPUT HASH", "ENTRY HASH", "STATUS"], entry_rows)

    except Exception as exc:
        html += _card(f'<span style="color:#EF4444;">Audit chain error: {str(exc)[:200]}</span>')

    elapsed = (perf_counter() - t0) * 1000
    html += _stat_row([("TOTAL ELAPSED", f"{elapsed:.1f}ms", True)])
    html += _data_ts()
    return html


# ---------------------------------------------------------------------------
# TAB 8: UNMERGE (RIGHT TO FORGET)
# ---------------------------------------------------------------------------


def tab8_unmerge() -> str:
    t0 = perf_counter()
    models = _fetch_models(16)
    if not models:
        return _error_card("Could not fetch models from Hugging Face Hub.")

    records = [_model_to_record(m, i) for i, m in enumerate(models)]
    source_a = records[:10]
    source_b = []
    for r in records[6:]:
        modified = dict(r)
        modified["downloads"] = int(modified["downloads"] * 1.2) + 100
        source_b.append(modified)

    # ---- STEP 1: MERGE ----
    html = _section("STEP 1: MERGE WITH FULL PROVENANCE TRACKING")
    merge_t0 = perf_counter()
    merged_data, prov_log = merge_with_provenance(source_a, source_b, key="id")
    merge_elapsed = (perf_counter() - merge_t0) * 1000

    merged_list = merged_data if isinstance(merged_data, list) else list(merged_data)

    html += _stat_row([
        ("SOURCE A", str(len(source_a)), False),
        ("SOURCE B", str(len(source_b)), False),
        ("MERGED TOTAL", str(len(merged_list)), True),
        ("CONFLICTS RESOLVED", str(prov_log.total_conflicts), False),
        ("MERGE TIME", f"{merge_elapsed:.3f}ms", False),
    ])

    # PRE: merged dataset
    html += _section("PRE-UNMERGE STATE: COMPLETE MERGED DATASET")
    m_rows = [
        [str(r.get("id", "?"))[:42], _fmt_num(r.get("downloads", 0)),
         _fmt_num(r.get("likes", 0)), str(r.get("pipeline_tag", "?")),
         str(r.get("author", "?"))[:20]]
        for r in merged_list[:14]
    ]
    html += _table(["MODEL ID", "DOWNLOADS", "LIKES", "PIPELINE", "AUTHOR"], m_rows)

    # Provenance origin map
    html += f'<div style="font-size:0.68rem;color:{TEXT2};text-transform:uppercase;margin:10px 0 4px 0;">PROVENANCE ORIGIN MAP</div>'
    origin_rows = []
    for rec in prov_log.records:
        origin_badge = _badge(
            rec.origin.upper(),
            "info" if rec.origin == "merged" else ("pass" if "a" in rec.origin else "warn"),
        )
        origin_rows.append([str(rec.key)[:32], origin_badge, str(rec.conflict_count)])
    html += _table(["KEY", "ORIGIN", "CONFLICTS"], origin_rows[:16])

    # Count by origin
    origin_counts = {}
    for rec in prov_log.records:
        origin_counts[rec.origin] = origin_counts.get(rec.origin, 0) + 1
    origin_stats = [(f"ORIGIN: {k.upper()}", str(v), k == "merged") for k, v in origin_counts.items()]
    html += _stat_row(origin_stats)

    # ---- STEP 2: UNMERGE ----
    html += _section("STEP 2: UNMERGE -- REMOVE SOURCE B (DATA SUBJECT RIGHT TO FORGET)")
    engine = UnmergeEngine()
    unmerge_t0 = perf_counter()
    unmerged = engine.unmerge(merged_list, prov_log, remove_source="b", key_field="id")
    unmerge_elapsed = (perf_counter() - unmerge_t0) * 1000

    html += _stat_row([
        ("RECORDS BEFORE", str(len(merged_list)), False),
        ("RECORDS AFTER", str(len(unmerged)), True),
        ("RECORDS REMOVED", str(len(merged_list) - len(unmerged)), True),
        ("UNMERGE TIME", f"{unmerge_elapsed:.3f}ms", False),
    ])

    # POST: remaining records
    html += _section("POST-UNMERGE STATE: REMAINING RECORDS (SOURCE B REMOVED)")
    u_rows = [
        [str(r.get("id", "?"))[:42], _fmt_num(r.get("downloads", 0)),
         _fmt_num(r.get("likes", 0)), str(r.get("pipeline_tag", "?")),
         str(r.get("author", "?"))[:20]]
        for r in unmerged[:14]
    ]
    html += _table(["MODEL ID", "DOWNLOADS", "LIKES", "PIPELINE", "AUTHOR"], u_rows)

    # ---- STEP 3: VERIFY ----
    html += _section("STEP 3: ZERO-RESIDUAL VERIFICATION")
    verify_t0 = perf_counter()
    report = engine.verify_unmerge(merged_list, unmerged, "b", prov_log)
    verify_elapsed = (perf_counter() - verify_t0) * 1000

    html += _stat_row([
        ("VERIFICATION", "PASS" if report.success else "FAIL", report.success),
        ("RECORDS REMOVED", str(report.records_removed), True),
        ("RECORDS REMAINING", str(report.records_remaining), False),
        ("RESIDUAL DATA", f"{report.residual_data} bytes", report.residual_data == 0),
        ("VERIFY TIME", f"{verify_elapsed:.3f}ms", False),
    ])

    success_badge = _badge("ZERO RESIDUAL VERIFIED" if (report.success and report.residual_data == 0) else "RESIDUAL DETECTED", "pass" if (report.success and report.residual_data == 0) else "fail")
    html += _card(
        f'{success_badge}'
        f'<div style="color:{TEXT};font-family:\'JetBrains Mono\',monospace;'
        f'font-size:0.8rem;margin-top:8px;">'
        f'SOURCE REMOVED: {report.source_removed}<br>'
        f'RECORDS REMOVED: {report.records_removed}<br>'
        f'RECORDS REMAINING: {report.records_remaining}<br>'
        f'RESIDUAL DATA: {report.residual_data} bytes<br>'
        f'TIMESTAMP: {report.timestamp}</div>'
    )

    # GDPR compliance note
    html += _card(
        f'<div style="color:{TEXT2};font-size:0.75rem;">'
        f'GDPR ARTICLE 17 COMPLIANCE: The right to erasure ("right to be forgotten") '
        f'requires that personal data be erased without undue delay. The unmerge operation '
        f'above demonstrates cryptographically verified removal of all source B data with '
        f'zero residual proof -- satisfying the technical requirements for data erasure.</div>'
    )

    elapsed = (perf_counter() - t0) * 1000
    html += _stat_row([("TOTAL ELAPSED", f"{elapsed:.1f}ms", True)])
    html += _data_ts()
    return html


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

* {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

body, .gradio-container {
    background: #09090B !important;
    color: #FAFAFA !important;
}

.gradio-container {
    max-width: 1200px !important;
}

/* Tabs */
.tab-nav {
    background: #09090B !important;
    border-bottom: 1px solid #3F3F46 !important;
}

.tab-nav button {
    font-family: 'Inter', sans-serif !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    color: #71717A !important;
    border: none !important;
    background: transparent !important;
    padding: 12px 14px !important;
    border-radius: 0 !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.2s !important;
}

.tab-nav button:hover {
    color: #A1A1AA !important;
}

.tab-nav button.selected {
    color: #06B6D4 !important;
    border-bottom: 2px solid #06B6D4 !important;
    background: transparent !important;
}

/* Buttons */
button.primary, button.lg {
    background: #083344 !important;
    border: 1px solid #06B6D4 !important;
    color: #06B6D4 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    border-radius: 6px !important;
    transition: all 0.2s !important;
}

button.primary:hover, button.lg:hover {
    background: #164E63 !important;
}

/* Sliders and inputs */
input[type=range], select, input[type=text], input[type=number], textarea {
    background: #18181B !important;
    border: 1px solid #3F3F46 !important;
    color: #FAFAFA !important;
    border-radius: 6px !important;
}

/* Labels */
label, .gr-label, span.label-wrap, .label-wrap > span {
    text-transform: uppercase !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.05em !important;
    color: #A1A1AA !important;
    font-weight: 600 !important;
}

/* Panels and blocks */
.gr-panel, .gr-box, .gr-form, .gr-block, .block, .contain {
    background: #09090B !important;
    border: none !important;
    box-shadow: none !important;
}

/* Accordion */
.gr-accordion {
    background: #18181B !important;
    border: 1px solid #3F3F46 !important;
    border-radius: 8px !important;
}

/* Footer hide */
footer {
    display: none !important;
}

/* Prose / Markdown */
.prose, .prose p, .prose li {
    color: #FAFAFA !important;
}

.prose h1, .prose h2, .prose h3, .prose h4 {
    color: #FAFAFA !important;
}

.prose code {
    color: #06B6D4 !important;
    background: #083344 !important;
}

/* Dropdown specific */
.gr-dropdown, .secondary-wrap, .wrap {
    background: #18181B !important;
}

ul[role=listbox] {
    background: #18181B !important;
    border: 1px solid #3F3F46 !important;
}

ul[role=listbox] li {
    color: #FAFAFA !important;
}

ul[role=listbox] li:hover, ul[role=listbox] li.selected {
    background: #27272A !important;
}
"""


# ---------------------------------------------------------------------------
# HEADER / FOOTER
# ---------------------------------------------------------------------------

HEADER_HTML = f"""
<div style="text-align:center;padding:32px 0 16px 0;">
    <div style="font-family:'JetBrains Mono',monospace;font-size:1.8rem;font-weight:700;
         color:{TEXT};letter-spacing:-0.02em;">
        crdt-merge
        <span style="color:{ACCENT};font-size:0.9rem;vertical-align:super;margin-left:4px;">0.9.4</span>
    </div>
    <div style="font-size:0.75rem;color:{TEXT2};text-transform:uppercase;letter-spacing:0.12em;margin-top:8px;">
        ENTERPRISE TECHNICAL DEMONSTRATION
    </div>
    <div style="font-size:0.65rem;color:{MUTED};margin-top:4px;font-family:'JetBrains Mono',monospace;">
        CONFLICT-FREE REPLICATED DATA TYPES FOR DATAFRAMES, JSON AND DATASETS
    </div>
    <div style="display:flex;gap:16px;justify-content:center;margin-top:12px;flex-wrap:wrap;">
        <span style="font-size:0.62rem;color:{DIM};font-family:'JetBrains Mono',monospace;">
            LIVE HF HUB INTEGRATION</span>
        <span style="font-size:0.62rem;color:{DIM};">|</span>
        <span style="font-size:0.62rem;color:{DIM};font-family:'JetBrains Mono',monospace;">
            FULL 6-LAYER CRDT PROOF ENGINE</span>
        <span style="font-size:0.62rem;color:{DIM};">|</span>
        <span style="font-size:0.62rem;color:{DIM};font-family:'JetBrains Mono',monospace;">
            PATENT PENDING UK 2607132.4</span>
    </div>
</div>
"""

FOOTER_HTML = f"""
<div style="text-align:center;padding:24px 0;margin-top:32px;border-top:1px solid {BORDER};">
    <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:{MUTED};">
        crdt-merge 0.9.4 | BSL-1.1 | Copyright 2026 Optitransfer
    </div>
    <div style="margin-top:6px;display:flex;gap:16px;justify-content:center;">
        <a href="https://github.com/mgillr/crdt-merge" target="_blank"
           style="font-size:0.65rem;color:{ACCENT};text-decoration:none;text-transform:uppercase;
                  letter-spacing:0.05em;">GitHub</a>
        <a href="https://pypi.org/project/crdt-merge/" target="_blank"
           style="font-size:0.65rem;color:{ACCENT};text-decoration:none;text-transform:uppercase;
                  letter-spacing:0.05em;">PyPI</a>
        <a href="https://optitransfer.ch" target="_blank"
           style="font-size:0.65rem;color:{ACCENT};text-decoration:none;text-transform:uppercase;
                  letter-spacing:0.05em;">optitransfer.ch</a>
    </div>
</div>
"""


# ---------------------------------------------------------------------------
# APP ASSEMBLY
# ---------------------------------------------------------------------------


def build_app() -> gr.Blocks:
    with gr.Blocks(
        title="crdt-merge 0.9.4 Enterprise Demo",
        css=CUSTOM_CSS,
        theme=gr.themes.Base(
            primary_hue=gr.themes.colors.cyan,
            neutral_hue=gr.themes.colors.zinc,
        ),
    ) as demo:
        gr.HTML(HEADER_HTML)

        with gr.Tabs():
            # -- TAB 1: CONVERGENCE ENGINE --
            with gr.Tab("CONVERGENCE ENGINE"):
                gr.HTML(
                    f'<div style="font-size:0.7rem;color:{TEXT2};margin:8px 0;'
                    f'text-transform:uppercase;letter-spacing:0.05em;">'
                    f'Test CRDT convergence across all N! merge orderings with live HF Hub data. '
                    f'Verifies commutativity, associativity, and idempotency.</div>'
                )
                with gr.Row():
                    t1_slider = gr.Slider(
                        minimum=2, maximum=5, value=3, step=1,
                        label="NODE COUNT",
                    )
                    t1_btn = gr.Button("RUN CONVERGENCE TEST", variant="primary")
                t1_output = gr.HTML()
                t1_btn.click(fn=tab1_convergence, inputs=[t1_slider], outputs=[t1_output])

            # -- TAB 2: MERGE LAB --
            with gr.Tab("MERGE LAB"):
                gr.HTML(
                    f'<div style="font-size:0.7rem;color:{TEXT2};margin:8px 0;'
                    f'text-transform:uppercase;letter-spacing:0.05em;">'
                    f'Merge overlapping datasets with configurable per-field strategies. '
                    f'Full diff analysis and provenance trail.</div>'
                )
                with gr.Row():
                    t2_dropdown = gr.Dropdown(
                        choices=["LWW", "MaxWins", "MinWins"],
                        value="LWW",
                        label="MERGE STRATEGY FOR NUMERIC FIELDS",
                    )
                    t2_btn = gr.Button("RUN MERGE LAB", variant="primary")
                t2_output = gr.HTML()
                t2_btn.click(fn=tab2_merge_lab, inputs=[t2_dropdown], outputs=[t2_output])

            # -- TAB 3: GOSSIP PROTOCOL --
            with gr.Tab("GOSSIP PROTOCOL"):
                gr.HTML(
                    f'<div style="font-size:0.7rem;color:{TEXT2};margin:8px 0;'
                    f'text-transform:uppercase;letter-spacing:0.05em;">'
                    f'Simulate gossip-based state propagation across distributed nodes. '
                    f'Watch convergence unfold round by round.</div>'
                )
                with gr.Row():
                    t3_nodes = gr.Slider(
                        minimum=2, maximum=8, value=4, step=1,
                        label="NODE COUNT",
                    )
                    t3_rounds = gr.Slider(
                        minimum=1, maximum=20, value=8, step=1,
                        label="GOSSIP ROUNDS",
                    )
                    t3_btn = gr.Button("RUN GOSSIP SIMULATION", variant="primary")
                t3_output = gr.HTML()
                t3_btn.click(fn=tab3_gossip, inputs=[t3_nodes, t3_rounds], outputs=[t3_output])

            # -- TAB 4: MULTI-AGENT --
            with gr.Tab("MULTI-AGENT"):
                gr.HTML(
                    f'<div style="font-size:0.7rem;color:{TEXT2};margin:8px 0;'
                    f'text-transform:uppercase;letter-spacing:0.05em;">'
                    f'Merge AI agent states: facts, tags, counters, messages. '
                    f'Highest-confidence fact wins in conflicts.</div>'
                )
                t4_btn = gr.Button("RUN MULTI-AGENT MERGE", variant="primary")
                t4_output = gr.HTML()
                t4_btn.click(fn=tab4_multi_agent, inputs=[], outputs=[t4_output])

            # -- TAB 5: CRDT PRIMITIVES --
            with gr.Tab("CRDT PRIMITIVES"):
                gr.HTML(
                    f'<div style="font-size:0.7rem;color:{TEXT2};margin:8px 0;'
                    f'text-transform:uppercase;letter-spacing:0.05em;">'
                    f'All 5 core CRDT types: GCounter, PNCounter, LWWRegister, ORSet, LWWMap. '
                    f'Each verified for commutativity and idempotency with live data.</div>'
                )
                t5_btn = gr.Button("RUN PRIMITIVES DEMO", variant="primary")
                t5_output = gr.HTML()
                t5_btn.click(fn=tab5_primitives, inputs=[], outputs=[t5_output])

            # -- TAB 6: DEDUP --
            with gr.Tab("DEDUP"):
                gr.HTML(
                    f'<div style="font-size:0.7rem;color:{TEXT2};margin:8px 0;'
                    f'text-transform:uppercase;letter-spacing:0.05em;">'
                    f'Exact and fuzzy deduplication. Distributed DedupIndex merging '
                    f'for multi-worker pipelines.</div>'
                )
                t6_btn = gr.Button("RUN DEDUP ANALYSIS", variant="primary")
                t6_output = gr.HTML()
                t6_btn.click(fn=tab6_dedup, inputs=[], outputs=[t6_output])

            # -- TAB 7: COMPLIANCE --
            with gr.Tab("COMPLIANCE"):
                gr.HTML(
                    f'<div style="font-size:0.7rem;color:{TEXT2};margin:8px 0;'
                    f'text-transform:uppercase;letter-spacing:0.05em;">'
                    f'Audit against EU AI Act, GDPR, HIPAA, and SOX. '
                    f'Tamper-evident hash-chain verification via AuditedMerge.</div>'
                )
                t7_btn = gr.Button("RUN COMPLIANCE AUDIT", variant="primary")
                t7_output = gr.HTML()
                t7_btn.click(fn=tab7_compliance, inputs=[], outputs=[t7_output])

            # -- TAB 8: UNMERGE --
            with gr.Tab("UNMERGE"):
                gr.HTML(
                    f'<div style="font-size:0.7rem;color:{TEXT2};margin:8px 0;'
                    f'text-transform:uppercase;letter-spacing:0.05em;">'
                    f'Right to forget: reversible merge with provenance-based unmerge '
                    f'and zero-residual cryptographic verification.</div>'
                )
                t8_btn = gr.Button("RUN UNMERGE DEMO", variant="primary")
                t8_output = gr.HTML()
                t8_btn.click(fn=tab8_unmerge, inputs=[], outputs=[t8_output])

        gr.HTML(FOOTER_HTML)

    return demo


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = build_app()
    app.launch()
else:
    # HF Spaces expects a module-level `demo` variable
    demo = build_app()
