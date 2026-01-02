# Copyright 2026 Ryan Gillespie / Optitransfer
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""
crdt-merge — HuggingFace Space Demo
Conflict-free merge, dedup & sync for DataFrames and datasets.
"""

# Requires: gradio>=4.0,<5.0
import gradio as gr
import pandas as pd
import json
import time
import io

# Import crdt_merge (installed as local package in Space)
from crdt_merge import merge, dedup, diff, merge_dicts
from crdt_merge.dedup import dedup_records


def merge_csvs(file_a, file_b, key_col, prefer, do_dedup):
    """Merge two CSV files using CRDT semantics."""
    try:
        if file_a is None or file_b is None:
            return None, "⚠️ Please upload both CSV files"
        
        df_a = pd.read_csv(file_a.name if hasattr(file_a, 'name') else file_a)
        df_b = pd.read_csv(file_b.name if hasattr(file_b, 'name') else file_b)
        
        key = key_col.strip() if key_col and key_col.strip() else None
        if key and key not in df_a.columns:
            return None, f"⚠️ Key column '{key}' not found in file A. Available: {list(df_a.columns)}"
        if key and key not in df_b.columns:
            return None, f"⚠️ Key column '{key}' not found in file B. Available: {list(df_b.columns)}"
        
        start = time.perf_counter()
        merged = merge(df_a, df_b, key=key, prefer=prefer.lower(), dedup=do_dedup)
        elapsed = time.perf_counter() - start
        
        stats = f"""✅ **Merge complete in {elapsed*1000:.1f}ms**

| Metric | Value |
|---|---|
| File A rows | {len(df_a):,} |
| File B rows | {len(df_b):,} |
| **Merged rows** | **{len(merged):,}** |
| Columns (A) | {len(df_a.columns)} |
| Columns (B) | {len(df_b.columns)} |
| **Columns (merged)** | **{len(merged.columns)}** |
| Key column | {key or 'None (append mode)'} |
| Conflict resolution | {prefer} wins |
| Dedup | {'Yes' if do_dedup else 'No'} |
"""
        return merged, stats
    except Exception as e:
        return None, f"❌ Error: {str(e)}"


def dedup_csv(file_in, columns, method, threshold):
    """Deduplicate a CSV file."""
    try:
        if file_in is None:
            return None, "⚠️ Please upload a CSV file"
        
        df = pd.read_csv(file_in.name if hasattr(file_in, 'name') else file_in)
        records = df.to_dict('records')
        
        cols = [c.strip() for c in columns.split(",")] if columns.strip() else None
        if cols:
            invalid = [c for c in cols if c not in df.columns]
            if invalid:
                return None, f"⚠️ Columns not found: {invalid}. Available: {list(df.columns)}"
        
        start = time.perf_counter()
        unique, removed = dedup_records(records, columns=cols, method=method.lower(), threshold=threshold)
        elapsed = time.perf_counter() - start
        
        result = pd.DataFrame(unique)
        
        stats = f"""✅ **Dedup complete in {elapsed*1000:.1f}ms**

| Metric | Value |
|---|---|
| Input rows | {len(df):,} |
| **Output rows** | **{len(result):,}** |
| Duplicates removed | {removed:,} |
| Reduction | {removed/len(df)*100:.1f}% |
| Method | {method} |
| Columns compared | {cols or 'all'} |
"""
        return result, stats
    except Exception as e:
        return None, f"❌ Error: {str(e)}"


def merge_json_input(json_a, json_b):
    """Deep merge two JSON objects."""
    try:
        a = json.loads(json_a)
        b = json.loads(json_b)
        
        start = time.perf_counter()
        result = merge_dicts(a, b)
        elapsed = time.perf_counter() - start
        
        return json.dumps(result, indent=2), f"✅ Merged in {elapsed*1000:.2f}ms"
    except json.JSONDecodeError as e:
        return "", f"❌ Invalid JSON: {e}"
    except Exception as e:
        return "", f"❌ Error: {e}"


def diff_csvs(file_a, file_b, key_col):
    """Show differences between two CSVs."""
    try:
        if file_a is None or file_b is None:
            return "⚠️ Please upload both CSV files"
        
        df_a = pd.read_csv(file_a.name if hasattr(file_a, 'name') else file_a)
        df_b = pd.read_csv(file_b.name if hasattr(file_b, 'name') else file_b)
        
        key = key_col.strip()
        if not key:
            return "⚠️ Key column is required for diff"
        
        changes = diff(df_a, df_b, key=key)
        
        report = f"## 📊 Diff Report\n\n**{changes['summary']}**\n\n"
        
        if changes['modified']:
            report += "### Modified Rows\n\n"
            for m in changes['modified'][:20]:
                report += f"**Key: {m['key']}**\n"
                for col, vals in m['changes'].items():
                    report += f"  - `{col}`: `{vals['old']}` → `{vals['new']}`\n"
                report += "\n"
            if len(changes['modified']) > 20:
                report += f"*...and {len(changes['modified'])-20} more*\n"
        
        return report
    except Exception as e:
        return f"❌ Error: {e}"


# ============================================================
# Gradio UI
# ============================================================

DESCRIPTION = """
# 🔀 crdt-merge

**Conflict-free merge, dedup & sync for DataFrames and datasets — powered by CRDTs.**

Upload two CSV files and merge them with mathematically guaranteed correctness. 
No conflicts. No coordination. No data loss.

- **Merge**: Combine two datasets by key — conflicts resolved automatically
- **Dedup**: Remove exact or fuzzy duplicates  
- **Diff**: See exactly what changed between versions
- **JSON Merge**: Deep-merge configs and metadata

> ⚡ 320,000+ rows/sec • Zero dependencies • `pip install crdt-merge`
"""

with gr.Blocks(
    title="crdt-merge — Conflict-free Data Merge",
    theme=gr.themes.Soft(),
) as demo:
    gr.Markdown(DESCRIPTION)
    
    with gr.Tabs():
        # ========== MERGE TAB ==========
        with gr.Tab("🔀 Merge CSVs"):
            with gr.Row():
                with gr.Column():
                    file_a = gr.File(label="📄 CSV File A", file_types=[".csv"])
                    file_b = gr.File(label="📄 CSV File B", file_types=[".csv"])
                with gr.Column():
                    key_input = gr.Textbox(label="Key Column", placeholder="e.g. id, name, url", info="Column to match rows on. Leave empty for append + dedup.")
                    prefer_input = gr.Radio(["Latest", "A", "B"], value="Latest", label="Conflict Resolution", info="When both files have different values for the same key")
                    dedup_check = gr.Checkbox(value=True, label="Remove duplicates")
                    merge_btn = gr.Button("🔀 Merge", variant="primary", size="lg")
            
            merge_stats = gr.Markdown()
            merge_output = gr.Dataframe(label="Merged Result", wrap=True)
            
            merge_btn.click(
                merge_csvs,
                inputs=[file_a, file_b, key_input, prefer_input, dedup_check],
                outputs=[merge_output, merge_stats]
            )
        
        # ========== DEDUP TAB ==========
        with gr.Tab("🧹 Deduplicate"):
            with gr.Row():
                with gr.Column():
                    dedup_file = gr.File(label="📄 CSV File", file_types=[".csv"])
                with gr.Column():
                    dedup_cols = gr.Textbox(label="Columns to Compare", placeholder="col1, col2 (leave empty for all)")
                    dedup_method = gr.Radio(["Exact", "Fuzzy"], value="Exact", label="Method")
                    dedup_threshold = gr.Slider(0.5, 1.0, value=0.85, step=0.05, label="Fuzzy Threshold")
                    dedup_btn = gr.Button("🧹 Deduplicate", variant="primary", size="lg")
            
            dedup_stats = gr.Markdown()
            dedup_output = gr.Dataframe(label="Deduplicated Result", wrap=True)
            
            dedup_btn.click(
                dedup_csv,
                inputs=[dedup_file, dedup_cols, dedup_method, dedup_threshold],
                outputs=[dedup_output, dedup_stats]
            )
        
        # ========== DIFF TAB ==========
        with gr.Tab("📊 Diff"):
            with gr.Row():
                diff_file_a = gr.File(label="📄 CSV File A (old)", file_types=[".csv"])
                diff_file_b = gr.File(label="📄 CSV File B (new)", file_types=[".csv"])
            diff_key = gr.Textbox(label="Key Column", placeholder="id")
            diff_btn = gr.Button("📊 Compare", variant="primary")
            diff_output = gr.Markdown()
            
            diff_btn.click(
                diff_csvs,
                inputs=[diff_file_a, diff_file_b, diff_key],
                outputs=[diff_output]
            )
        
        # ========== JSON MERGE TAB ==========
        with gr.Tab("🔧 JSON Merge"):
            with gr.Row():
                json_a = gr.Code(label="JSON A", language="json", value='{\n  "model": {"name": "bert", "layers": 12},\n  "tags": ["nlp"]\n}')
                json_b = gr.Code(label="JSON B", language="json", value='{\n  "model": {"name": "bert-large", "dropout": 0.1},\n  "tags": ["qa"],\n  "metadata": {"author": "team_b"}\n}')
            json_btn = gr.Button("🔧 Deep Merge", variant="primary")
            json_status = gr.Markdown()
            json_output = gr.Code(label="Merged Result", language="json")
            
            json_btn.click(
                merge_json_input,
                inputs=[json_a, json_b],
                outputs=[json_output, json_status]
            )
    
    gr.Markdown("""
---
**[📦 Install](https://github.com/mgillr/crdt-merge)** · `pip install crdt-merge` · **[GitHub](https://github.com/mgillr/crdt-merge)** · MIT License
""")

demo.launch()
