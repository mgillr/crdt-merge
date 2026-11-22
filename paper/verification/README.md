# Verification material for the paper

This folder holds what I have for checking the experiments of the paper in the parent folder
([arXiv:2605.19373](https://arxiv.org/abs/2605.19373)).

| File | What it is |
|------|------------|
| `tier1_phase1.py` | A script that repeats the controlled raw-property test (Tier 1, Phase 1; Table 3) |
| `tier2_production_scale.ipynb` | The Colab notebook of the production-scale evaluation (Tier 2), as it ran, with its outputs |
| `tier2_results.json` | The results file that notebook wrote |

The controlled test through the two-layer architecture (Tier 1, Phase 2) is `tests/test_crdt_compliance.py` in this
repository.

sha256:

```
22cf4926a79ceaa96f49eabf60032f861ee6bb1ee7a2c66d0db30070e4f3ca6b  tier2_production_scale.ipynb
7cbe4f895796efef7f78f61aefa9d49388e0ded00f39f17f3cba3b1a87a82fc6  tier2_results.json
```

## Tier 1, Phase 1 (Table 3)

`python paper/verification/tier1_phase1.py` tests commutativity, associativity and idempotency of each of the 26
strategies directly, on the 4x4 tensors of the test fixture, once each, with tolerance 1e-5. It prints the measured
table beside Table 3 and exits with status 1 if any cell differs.

I wrote this script in November 2026; the harness used for the paper is not in the repository. It gives Table 3 cell
for cell with crdt-merge 0.9.2, 0.9.4 and 0.11.0.

Each entry is the outcome on one set of tensors. A failure is a counterexample. A pass shows consistency on those
tensors and is not a proof.

## Tier 2 (Table 1, and the production columns of Table 2)

- Run on 2 April 2026 on one NVIDIA A100-SXM4-80GB with PyTorch 2.10.0+cu128 and CUDA 12.8.
- Library: crdt-merge 0.9.2, as installed by the notebook (printed in its cell 1.2).
- Models: the eight Hugging Face models of the paper's model table. The notebook prints the identifier it used for each.

How to read it:

- Each property is tested on one 128x128 slice per distinct weight shape: five shapes for GPT-2-XL, four for
  Mistral-7B. The notebook counts each result once for every layer of that shape, which is how the per-layer totals
  are formed.
- A second pass repeats each test on a 512x512 slice with a limit of 120 seconds. For `ada_merging` on GPT-2-XL it
  reports a real difference: associativity passes on the 128x128 slice and fails on the 512x512 one. This is the case
  the paper reports.
- The same pass also prints "slice/full mismatch" for `evolutionary_merge` (both models) and `genetic_merge`
  (GPT-2-XL), with a "full" verdict in which all three properties pass. Those lines are not results. One merge of two
  512x512 tensors takes about 240 s for `evolutionary_merge` and about 350 s for `genetic_merge` (measured on a desktop
  CPU with crdt-merge 0.9.2), so the limit is reached inside the test. The notebook catches the timeout as an ordinary
  error and returns zero counts, and zero of zero is printed as a pass. For these two strategies the 512x512 pass did
  not complete; their entries in the paper come from the 128x128 slices.

## Not here

The scripts and raw outputs of the multi-node convergence suite (Tier 3) are not in the repository.
