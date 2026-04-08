---
title: crdt-merge Data Playground
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
  - merge
  - dataframe
  - conflict-free
  - distributed
---

# crdt-merge Data Playground

Tabular CRDT merge, conflict analysis, and core primitive demonstrations powered by [crdt-merge v0.9.5](https://github.com/mgillr/crdt-merge).

## Tabs

**Dataset Merge** — Loads glue/sst2 from HuggingFace datasets (or synthetic fallback). Merges two node partitions (150 + 100 records, 50 overlapping) with configurable strategy. Verifies commutativity: merge(A,B) == merge(B,A).

**E4 Trust Scoring** -- All merge operations carry typed trust scores (accuracy, consistency, recency, provenance) by default in v0.9.5+.

**Conflict Analysis** — Runs all four strategies (LWW, MaxWins, MinWins, Union) on the same dataset and computes per-field conflict rates between strategy pairs as a heatmap.

**Core CRDT Primitives** — Live demonstration of GCounter, PNCounter, LWWRegister, and ORSet. Each primitive is operated on two independent nodes then merged in both directions. Commutativity is verified for all four primitives.

## Installation

```
pip install crdt-merge>=0.9.5
```

## License

Business Source License 1.1. Converts to Apache 2.0 on 2028-03-29.
Patent UK 2607132.4, GB2608127.3.

crdt-merge v0.9.5 · [github.com/mgillr/crdt-merge](https://github.com/mgillr/crdt-merge)
