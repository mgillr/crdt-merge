/-
crdt-merge machine-checked proofs (Lean 4, self-contained — no mathlib).

Run: scripts/check_theorems.sh  (exit 0 = all verified, zero holes)

Correspondence to the library's two-layer architecture:
  Layer 1 (OR-Set replication)     -> sunion_comm / sunion_assoc / sunion_idem
  Layer 2 (deterministic function) -> sum_append / perm_isum
    (integer aggregation is an exact function of the SET: grouping and
     delivery order cannot change the result — the byte-identical-
     convergence guarantee, at the arithmetic core)

These theorems were first formalized for converge (mgillr/converge
theorem/Converge.lean, P-112) and are recorded here with the library
they prove. Prior art context: CRDT correctness previously verified in
Isabelle/HOL (Zeller et al. 2014; Gomes/Kleppmann et al. 2017).
-/

-- Layer 1: the add-only OR-Set semilattice laws --------------------------

def SUnion (f g : String → Bool) : String → Bool := fun a => f a || g a

theorem sunion_comm (f g : String → Bool) : SUnion f g = SUnion g f := by
  funext a; simp [SUnion, Bool.or_comm]

theorem sunion_assoc (f g h : String → Bool) :
    SUnion (SUnion f g) h = SUnion f (SUnion g h) := by
  funext a; simp [SUnion, Bool.or_assoc]

theorem sunion_idem (f : String → Bool) : SUnion f f = f := by
  funext a; simp [SUnion, Bool.or_self]

-- Layer 2: the deterministic function over the set -----------------------

def lsum : List Nat → Nat
  | [] => 0
  | x :: xs => x + lsum xs

theorem sum_append (l1 l2 : List Nat) :
    lsum l1 + lsum l2 = lsum (l1 ++ l2) := by
  induction l1 with
  | nil => simp [lsum]
  | cons x xs ih =>
      simp only [lsum, List.cons_append]
      rw [Nat.add_assoc x (lsum xs) (lsum l2), ih]

theorem perm_isum : ∀ {l1 l2 : List Int}, l1.Perm l2 → l1.sum = l2.sum := by
  intro l1 l2 hp
  induction hp with
  | nil => rfl
  | cons x p ih => simp only [List.sum_cons]; omega
  | swap x y l => simp only [List.sum_cons]; omega
  | trans h1 h2 ih1 ih2 => exact ih1.trans ih2
