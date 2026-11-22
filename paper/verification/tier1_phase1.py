"""Repeat the controlled raw-property test of the paper (Tier 1, Phase 1; Table 3 of arXiv:2605.19373).

For each of the 26 merge strategies, three properties are tested directly on the strategy, on 4x4 float64 tensors:

    commutativity   merge([a, b]) == merge([b, a])
    associativity   merge([merge([a, b]), c]) == merge([a, merge([b, c])])
    idempotency     merge([a, a]) == a

The tensors are those of the fixture in tests/test_crdt_compliance.py (numpy RandomState(42): t1, t2, t3, base), the
tolerance is 1e-5, and each property is tested once. A failure is a counterexample; a pass shows consistency on these
tensors only.

I wrote this script in November 2026 to repeat the test: the harness used for the paper is not in the repository.
With crdt-merge 0.9.2 and 0.9.4 it gives Table 3 cell for cell.

Run:  python paper/verification/tier1_phase1.py
Exit status 0 when every cell equals Table 3, 1 otherwise.
"""
import sys

import numpy as np

import crdt_merge
from crdt_merge.model.crdt_state import CRDTMergeState
from crdt_merge.model.strategies import get_strategy, list_strategies

ATOL = 1e-5

# Table 3 of the paper: commutativity, associativity, idempotency (P = pass, F = fail).
TABLE_3 = {
    "ada_merging": "PFP", "adarank": "PFF", "dam": "PFP", "dare": "FFF", "dare_ties": "FFF", "della": "FFF",
    "dual_projection": "PFP", "emr": "PFF", "evolutionary_merge": "FFF", "fisher_merge": "PFP",
    "genetic_merge": "PFP", "led_merge": "PFP", "linear": "PFP", "model_breadcrumbs": "PFF",
    "negative_merge": "PFF", "regression_mean": "PFP", "representation_surgery": "PFP", "safe_merge": "PFP",
    "slerp": "PFP", "split_unlearn_merge": "PFF", "star": "PFF", "svd_knot_tying": "FFP",
    "task_arithmetic": "PPF", "ties": "PFF", "weight_average": "PFP", "weight_scope_alignment": "PFP",
}


def measure(name, t1, t2, t3, base):
    strategy = get_strategy(name)
    kwargs = {"base": base} if name in CRDTMergeState.BASE_REQUIRED else {}

    def merge(tensors):
        return np.asarray(strategy.merge(tensors, **kwargs), dtype=np.float64)

    ab = merge([t1, t2])
    commutative = np.allclose(ab, merge([t2, t1]), atol=ATOL)
    associative = np.allclose(merge([ab, t3]), merge([t1, merge([t2, t3])]), atol=ATOL)
    idempotent = np.allclose(merge([t1, t1]), t1, atol=ATOL)
    return "".join("P" if ok else "F" for ok in (commutative, associative, idempotent))


def main():
    rng = np.random.RandomState(42)
    t1, t2, t3, base = rng.randn(4, 4), rng.randn(4, 4), rng.randn(4, 4), rng.randn(4, 4)
    names = sorted(list_strategies())
    print(f"crdt-merge {crdt_merge.__version__}, {len(names)} strategies, 4x4 float64, atol {ATOL}")
    print(f"{'strategy':26s} measured  Table 3")
    differ = []
    totals = [0, 0, 0, 0]
    for name in names:
        got = measure(name, t1, t2, t3, base)
        want = TABLE_3.get(name, "???")
        if got != want:
            differ.append(name)
        for i, ch in enumerate(got):
            totals[i] += ch == "P"
        totals[3] += got == "PPP"
        print(f"{name:26s} {got}       {want}{'' if got == want else '   <-- differs'}")
    print(f"totals: commutative {totals[0]}/{len(names)}, associative {totals[1]}/{len(names)}, "
          f"idempotent {totals[2]}/{len(names)}, all three {totals[3]}/{len(names)}   (Table 3: 21, 1, 14, 0 of 26)")
    if differ:
        print("differs from Table 3:", ", ".join(differ))
        return 1
    print("every cell equals Table 3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
