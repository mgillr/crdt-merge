/-
E4 typed-trust lattice proofs (Lean 4, self-contained — no mathlib).

Correspondence to crdt_merge/e4: the TypedTrustScore's SIX canonical
dimensions as a finite enum; Trust = Dim → Nat (scaled, non-negative);
the E4 join as pointwise max; tiers as ordered thresholds (full: every
dim >= 85; clipped: every dim >= 50; else excluded).

Verified: L1 semilattice laws (comm/assoc/idem), L2 join is the least
upper bound, L3 monotonicity, L4 TIER MONOTONICITY (pointwise-higher
trust can never lower the admission tier).
-/

inductive Dim | signature | coverage | consistency | latency | availability | freshness
open Dim

abbrev Trust := Dim → Nat

def trustJoin (a b : Trust) : Trust := fun d => max (a d) (b d)

-- L1: the semilattice laws --------------------------------------------------

theorem trust_join_comm (a b : Trust) : trustJoin a b = trustJoin b a := by
  funext d; simp [trustJoin, Nat.max_comm]

theorem trust_join_assoc (a b c : Trust) :
    trustJoin (trustJoin a b) c = trustJoin a (trustJoin b c) := by
  funext d; simp [trustJoin, Nat.max_assoc]

theorem trust_join_idem (a : Trust) : trustJoin a a = a := by
  funext d; simp [trustJoin]

-- L2: join is the least upper bound -----------------------------------------

theorem trust_join_is_lub (a b c : Trust)
    (ha : ∀ d, a d ≤ c d) (hb : ∀ d, b d ≤ c d) :
    ∀ d, trustJoin a b d ≤ c d := by
  intro d; unfold trustJoin
  exact Nat.max_le.mpr ⟨ha d, hb d⟩

-- L3: monotonicity ------------------------------------------------------------

theorem trust_join_mono (a b : Trust) (d : Dim) :
    a d ≤ trustJoin a b d := Nat.le_max_left _ _
-- L4: tier monotonicity -------------------------------------------------------
/-- Local helpers (core lemma-name portability). -/
theorem ltrans {a b c : Nat} (h1 : a ≤ b) (h2 : b ≤ c) : a ≤ c := Nat.le_trans h1 h2
theorem le2min {n a b : Nat} (h1 : n ≤ a) (h2 : n ≤ b) : n ≤ Nat.min a b :=
  Nat.le_min.mpr ⟨h1, h2⟩

/-- The trust floor: the WEAKEST of the six canonical dimensions. -/
def trustFloor (t : Trust) : Nat :=
  Nat.min (t signature) (Nat.min (t coverage) (Nat.min (t consistency)
    (Nat.min (t latency) (Nat.min (t availability) (t freshness)))))

theorem floor_le_all (t : Trust) : ∀ d, trustFloor t ≤ t d := by
  intro d
  cases d with
  | signature => exact Nat.min_le_left _ _
  | coverage => exact ltrans (Nat.min_le_right _ _) (Nat.min_le_left _ _)
  | consistency =>
      exact ltrans (Nat.min_le_right _ _)
        (ltrans (Nat.min_le_right _ _) (Nat.min_le_left _ _))
  | latency =>
      exact ltrans (Nat.min_le_right _ _)
        (ltrans (Nat.min_le_right _ _)
        (ltrans (Nat.min_le_right _ _) (Nat.min_le_left _ _)))
  | availability =>
      exact ltrans (Nat.min_le_right _ _)
        (ltrans (Nat.min_le_right _ _)
        (ltrans (Nat.min_le_right _ _)
        (ltrans (Nat.min_le_right _ _) (Nat.min_le_left _ _))))
  | freshness =>
      exact ltrans (Nat.min_le_right _ _)
        (ltrans (Nat.min_le_right _ _)
        (ltrans (Nat.min_le_right _ _)
        (ltrans (Nat.min_le_right _ _)
                (Nat.min_le_right _ _))))

theorem trust_floor_mono {a b : Trust}
    (h : ∀ d, a d ≤ b d) : trustFloor a ≤ trustFloor b := by
  have fa := floor_le_all a
  exact le2min (ltrans (fa signature) (h signature))
    (le2min (ltrans (fa coverage) (h coverage))
    (le2min (ltrans (fa consistency) (h consistency))
    (le2min (ltrans (fa latency) (h latency))
    (le2min (ltrans (fa availability) (h availability))
            (ltrans (fa freshness) (h freshness))))))

/-- Tiers as an ordered scale via two independent thresholds:
0 excluded, 1 clipped, 3 full (ordering is all that matters). -/
def tierOf (t : Trust) : Nat :=
  (if 85 ≤ trustFloor t then 2 else 0) + (if 50 ≤ trustFloor t then 1 else 0)

theorem ind_le {k a b : Nat} (hab : a ≤ b) :
    (if k ≤ a then 2 else 0) ≤ (if k ≤ b then 2 else 0) := by
  split <;> split <;> omega

theorem ind1_le {k a b : Nat} (hab : a ≤ b) :
    (if k ≤ a then 1 else 0) ≤ (if k ≤ b then 1 else 0) := by
  split <;> split <;> omega

/-- Pointwise-higher trust can never LOWER the admission tier — conduct
growth upgrades (excluded→clipped→full), never downgrades. -/
theorem tier_monotone (t1 t2 : Trust)
    (h : ∀ d, t1 d ≤ t2 d) : tierOf t1 ≤ tierOf t2 := by
  have hm := trust_floor_mono h
  unfold tierOf
  exact Nat.add_le_add (ind_le hm) (ind1_le hm)
