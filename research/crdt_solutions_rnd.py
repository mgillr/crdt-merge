#!/usr/bin/env python3
"""
CRDT-MERGE R&D: 7 Solution Architectures to Make All 25 Strategies True CRDTs
==============================================================================

The fundamental insight: pairwise merge of raw tensors can NEVER satisfy all 3
CRDT laws for most model-merge strategies. The mathematical structure forbids it.

But CRDTs don't require the merge to operate on raw tensors. They require a
merge operation on STATES that is commutative, associative, and idempotent.

This script prototypes and empirically tests 7 architectures:

  SOL-1: G-Set Accumulator (collect-then-resolve)
  SOL-2: Delta-State CRDT (task-vector accumulation)
  SOL-3: Monoid Accumulator (sum + contribution tracking)
  SOL-4: Canonical Ordering (deterministic hash-based order)
  SOL-5: Merkle-DAG CRDT (history-preserving merge tree)
  SOL-6: Hybrid Two-Phase (CRDT accumulation + atomic resolution)
  SOL-7: Lattice Consensus (join-semilattice over model registries)

Each is tested for all 3 CRDT laws against all 25 strategies.
"""

import sys, os, json, hashlib, copy, random, math, time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple, Set, FrozenSet

# Add the project to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from crdt_merge.model.strategies import get_strategy, list_strategies, _REGISTRY

# ===========================================================================
# Helpers
# ===========================================================================

def gen_tensor(size=10, seed=None):
    """Generate a random tensor (numpy array)."""
    rng = np.random.RandomState(seed)
    return rng.randn(size).astype(np.float64)

def tensor_id(tensor):
    """Deterministic hash of a tensor for deduplication."""
    return hashlib.sha256(np.asarray(tensor).tobytes()).hexdigest()[:16]

def approx_equal(a, b, tol=1e-6):
    """Check approximate equality of two array-likes."""
    a_arr = np.asarray(a, dtype=float).ravel()
    b_arr = np.asarray(b, dtype=float).ravel()
    if a_arr.shape != b_arr.shape:
        return False
    return np.allclose(a_arr, b_arr, atol=tol, rtol=tol)

# Strategies that need base=
BASE_REQUIRED = {
    'task_arithmetic', 'ties', 'dare', 'della', 'dare_ties',
    'model_breadcrumbs', 'emr', 'star', 'svd_knot_tying', 'adarank',
    'negative_merge', 'split_unlearn_merge', 'safe_merge',
}

# Strategies that are stochastic (use RNG internally)
STOCHASTIC = {
    'dare', 'della', 'dare_ties', 'evolutionary_merge', 'genetic_merge',
}

# ===========================================================================
# SOLUTION 1: G-Set Accumulator (Grow-Only Set + Atomic Resolution)
# ===========================================================================
# 
# The CRDT state is a set of (model_id, tensor) pairs.
# merge(S1, S2) = S1 ∪ S2  (set union, deduplicated by model_id)
# resolve(S) = strategy.merge(list(S.tensors), base=S.base)
#
# Set union is provably: commutative ✓, associative ✓, idempotent ✓

class GSetState:
    """Grow-only set CRDT state for model contributions."""
    __slots__ = ('contributions', 'base', 'strategy_name', 'weights_map')
    
    def __init__(self, strategy_name: str, base=None):
        self.contributions: Dict[str, np.ndarray] = OrderedDict()  # id → tensor
        self.weights_map: Dict[str, float] = {}  # id → weight
        self.base = base
        self.strategy_name = strategy_name
    
    def add(self, tensor, weight=1.0, model_id=None):
        """Add a model contribution."""
        mid = model_id or tensor_id(tensor)
        self.contributions[mid] = np.array(tensor, dtype=np.float64)
        self.weights_map[mid] = weight
        return self
    
    def merge(self, other: 'GSetState') -> 'GSetState':
        """CRDT merge = set union."""
        result = GSetState(self.strategy_name, base=self.base)
        # Union of contributions (first-seen wins for same ID)
        for mid, t in self.contributions.items():
            result.contributions[mid] = t.copy()
            result.weights_map[mid] = self.weights_map.get(mid, 1.0)
        for mid, t in other.contributions.items():
            if mid not in result.contributions:
                result.contributions[mid] = t.copy()
                result.weights_map[mid] = other.weights_map.get(mid, 1.0)
        if result.base is None and other.base is not None:
            result.base = other.base
        return result
    
    def resolve(self) -> np.ndarray:
        """Apply strategy atomically to all collected contributions."""
        if not self.contributions:
            return self.base if self.base is not None else np.array([])
        
        strategy = get_strategy(self.strategy_name)
        # Sort by model_id for deterministic order
        sorted_ids = sorted(self.contributions.keys())
        tensors = [self.contributions[mid] for mid in sorted_ids]
        weights = [self.weights_map.get(mid, 1.0) for mid in sorted_ids]
        
        kwargs = {}
        if self.strategy_name in STOCHASTIC:
            kwargs['seed'] = 42
        
        if self.strategy_name in BASE_REQUIRED:
            return strategy.merge(tensors, weights=weights, base=self.base, **kwargs)
        return strategy.merge(tensors, weights=weights, **kwargs)
    
    def __eq__(self, other):
        if not isinstance(other, GSetState):
            return False
        return (set(self.contributions.keys()) == set(other.contributions.keys()) and
                all(np.array_equal(self.contributions[k], other.contributions[k]) 
                    for k in self.contributions))
    
    def state_equal(self, other):
        """CRDT state equality (for idempotency check)."""
        return self == other


# ===========================================================================
# SOLUTION 2: Delta-State CRDT (Task Vector Accumulation)
# ===========================================================================
#
# For task-vector strategies: accumulate deltas from a shared base.
# State = {deltas: {model_id: (θᵢ - base)}, base: base}
# merge(S1, S2) = {deltas: S1.deltas ∪ S2.deltas, base: base}
# resolve(S) = base + f(deltas)  where f is strategy-specific
#
# For non-task-vector strategies: falls back to G-Set.

class DeltaState:
    """Delta-state CRDT for task-vector strategies."""
    __slots__ = ('deltas', 'base', 'strategy_name', 'weights_map')
    
    def __init__(self, strategy_name: str, base=None):
        self.deltas: Dict[str, np.ndarray] = OrderedDict()
        self.weights_map: Dict[str, float] = {}
        self.base = base
        self.strategy_name = strategy_name
    
    def add(self, tensor, weight=1.0, model_id=None):
        """Add model contribution as delta from base."""
        mid = model_id or tensor_id(tensor)
        t = np.array(tensor, dtype=np.float64)
        if self.base is not None:
            self.deltas[mid] = t - np.array(self.base, dtype=np.float64)
        else:
            self.deltas[mid] = t.copy()
        self.weights_map[mid] = weight
        return self
    
    def merge(self, other: 'DeltaState') -> 'DeltaState':
        """CRDT merge = delta set union."""
        result = DeltaState(self.strategy_name, base=self.base)
        for mid, d in self.deltas.items():
            result.deltas[mid] = d.copy()
            result.weights_map[mid] = self.weights_map.get(mid, 1.0)
        for mid, d in other.deltas.items():
            if mid not in result.deltas:
                result.deltas[mid] = d.copy()
                result.weights_map[mid] = other.weights_map.get(mid, 1.0)
        if result.base is None and other.base is not None:
            result.base = other.base
        return result
    
    def resolve(self) -> np.ndarray:
        """Reconstruct tensors from deltas and apply strategy."""
        if not self.deltas:
            return self.base if self.base is not None else np.array([])
        
        strategy = get_strategy(self.strategy_name)
        base_arr = np.array(self.base, dtype=np.float64) if self.base is not None else None
        
        sorted_ids = sorted(self.deltas.keys())
        if base_arr is not None:
            tensors = [base_arr + self.deltas[mid] for mid in sorted_ids]
        else:
            tensors = [self.deltas[mid] for mid in sorted_ids]
        weights = [self.weights_map.get(mid, 1.0) for mid in sorted_ids]
        
        kwargs = {}
        if self.strategy_name in STOCHASTIC:
            kwargs['seed'] = 42
        
        if self.strategy_name in BASE_REQUIRED and base_arr is not None:
            return strategy.merge(tensors, weights=weights, base=base_arr, **kwargs)
        return strategy.merge(tensors, weights=weights, **kwargs)
    
    def __eq__(self, other):
        if not isinstance(other, DeltaState):
            return False
        return (set(self.deltas.keys()) == set(other.deltas.keys()) and
                all(np.allclose(self.deltas[k], other.deltas[k])
                    for k in self.deltas))


# ===========================================================================
# SOLUTION 3: Monoid Accumulator (Algebraic Sum + Count)
# ===========================================================================
#
# For linear strategies: State = (weighted_sum, weight_total, model_ids)
# merge(S1, S2) = deduplicated union of contributions
# resolve(S) = weighted_sum / weight_total  (or strategy-specific)
#
# The key: track individual contributions by ID to achieve idempotency.

class MonoidState:
    """Commutative monoid accumulator with deduplication."""
    __slots__ = ('contributions', 'base', 'strategy_name')
    
    def __init__(self, strategy_name: str, base=None):
        self.contributions: Dict[str, Tuple[np.ndarray, float]] = OrderedDict()
        self.base = base
        self.strategy_name = strategy_name
    
    def add(self, tensor, weight=1.0, model_id=None):
        mid = model_id or tensor_id(tensor)
        self.contributions[mid] = (np.array(tensor, dtype=np.float64), weight)
        return self
    
    def merge(self, other: 'MonoidState') -> 'MonoidState':
        """Merge = union with deduplication (first-seen wins)."""
        result = MonoidState(self.strategy_name, base=self.base)
        for mid, (t, w) in self.contributions.items():
            result.contributions[mid] = (t.copy(), w)
        for mid, (t, w) in other.contributions.items():
            if mid not in result.contributions:
                result.contributions[mid] = (t.copy(), w)
        if result.base is None and other.base is not None:
            result.base = other.base
        return result
    
    def resolve(self) -> np.ndarray:
        """Resolve using algebraic properties specific to strategy type."""
        if not self.contributions:
            return self.base if self.base is not None else np.array([])
        
        sorted_ids = sorted(self.contributions.keys())
        tensors = [self.contributions[mid][0] for mid in sorted_ids]
        weights = [self.contributions[mid][1] for mid in sorted_ids]
        
        # For linear strategies, we can use direct algebraic resolution
        category = self.strategy_name
        if category in ('weight_average', 'linear'):
            # Weighted average: Σ(wᵢ * θᵢ) / Σ(wᵢ)
            total_w = sum(weights)
            if total_w == 0:
                return tensors[0]
            result = np.zeros_like(tensors[0], dtype=np.float64)
            for t, w in zip(tensors, weights):
                result += (w / total_w) * t
            return result
        
        # For non-linear: fall back to atomic N-way
        strategy = get_strategy(self.strategy_name)
        kwargs = {}
        if self.strategy_name in STOCHASTIC:
            kwargs['seed'] = 42
        if self.strategy_name in BASE_REQUIRED:
            return strategy.merge(tensors, weights=weights, base=self.base, **kwargs)
        return strategy.merge(tensors, weights=weights, **kwargs)
    
    def __eq__(self, other):
        if not isinstance(other, MonoidState):
            return False
        return (set(self.contributions.keys()) == set(other.contributions.keys()) and
                all(np.array_equal(self.contributions[k][0], other.contributions[k][0])
                    for k in self.contributions))


# ===========================================================================
# SOLUTION 4: Canonical Ordering (Deterministic Hash Sort)
# ===========================================================================
#
# All nodes compute a canonical ordering of models by hash.
# This ensures non-commutative strategies produce identical results
# everywhere, but it changes the abstraction: the "merge" operates
# on sets of identified models, not anonymous tensors.

class CanonicalOrderState:
    """Canonical-order CRDT: deterministic hash-sorted resolution."""
    __slots__ = ('contributions', 'base', 'strategy_name')
    
    def __init__(self, strategy_name: str, base=None):
        self.contributions: Dict[str, Tuple[np.ndarray, float]] = {}
        self.base = base
        self.strategy_name = strategy_name
    
    def add(self, tensor, weight=1.0, model_id=None):
        mid = model_id or tensor_id(tensor)
        self.contributions[mid] = (np.array(tensor, dtype=np.float64), weight)
        return self
    
    def merge(self, other: 'CanonicalOrderState') -> 'CanonicalOrderState':
        result = CanonicalOrderState(self.strategy_name, base=self.base)
        for mid, (t, w) in self.contributions.items():
            result.contributions[mid] = (t.copy(), w)
        for mid, (t, w) in other.contributions.items():
            if mid not in result.contributions:
                result.contributions[mid] = (t.copy(), w)
        if result.base is None and other.base is not None:
            result.base = other.base
        return result
    
    def resolve(self) -> np.ndarray:
        """Sort by hash, then apply strategy in canonical order."""
        if not self.contributions:
            return self.base if self.base is not None else np.array([])
        
        # Sort by hash of model_id for absolute determinism
        sorted_ids = sorted(self.contributions.keys(),
                           key=lambda x: hashlib.sha256(x.encode()).hexdigest())
        tensors = [self.contributions[mid][0] for mid in sorted_ids]
        weights = [self.contributions[mid][1] for mid in sorted_ids]
        
        strategy = get_strategy(self.strategy_name)
        kwargs = {}
        if self.strategy_name in STOCHASTIC:
            kwargs['seed'] = 42
        if self.strategy_name in BASE_REQUIRED:
            return strategy.merge(tensors, weights=weights, base=self.base, **kwargs)
        return strategy.merge(tensors, weights=weights, **kwargs)
    
    def __eq__(self, other):
        if not isinstance(other, CanonicalOrderState):
            return False
        return set(self.contributions.keys()) == set(other.contributions.keys())


# ===========================================================================
# SOLUTION 5: Merkle-DAG CRDT (History-Preserving)
# ===========================================================================
#
# Each model contribution is a node in a Merkle-DAG.
# Merge = union of DAG nodes (CRDT).
# Resolution: topologically sort by hash, apply strategy deterministically.

class MerkleNode:
    __slots__ = ('model_id', 'tensor', 'weight', 'hash')
    def __init__(self, model_id, tensor, weight=1.0):
        self.model_id = model_id
        self.tensor = np.array(tensor, dtype=np.float64)
        self.weight = weight
        self.hash = hashlib.sha256(
            f"{model_id}:{self.tensor.tobytes().hex()}".encode()
        ).hexdigest()[:16]

class MerkleDAGState:
    """Merkle-DAG CRDT for auditable, history-preserving merges."""
    __slots__ = ('nodes', 'base', 'strategy_name')
    
    def __init__(self, strategy_name: str, base=None):
        self.nodes: Dict[str, MerkleNode] = {}  # hash → node
        self.base = base
        self.strategy_name = strategy_name
    
    def add(self, tensor, weight=1.0, model_id=None):
        mid = model_id or tensor_id(tensor)
        node = MerkleNode(mid, tensor, weight)
        self.nodes[node.hash] = node
        return self
    
    def merge(self, other: 'MerkleDAGState') -> 'MerkleDAGState':
        """CRDT merge = DAG union."""
        result = MerkleDAGState(self.strategy_name, base=self.base)
        for h, node in self.nodes.items():
            result.nodes[h] = node
        for h, node in other.nodes.items():
            if h not in result.nodes:
                result.nodes[h] = node
        if result.base is None and other.base is not None:
            result.base = other.base
        return result
    
    def resolve(self) -> np.ndarray:
        """Topological sort by hash, apply strategy."""
        if not self.nodes:
            return self.base if self.base is not None else np.array([])
        
        # Deduplicate by model_id (keep node with lowest hash for determinism)
        by_model: Dict[str, MerkleNode] = {}
        for node in self.nodes.values():
            if node.model_id not in by_model or node.hash < by_model[node.model_id].hash:
                by_model[node.model_id] = node
        
        sorted_ids = sorted(by_model.keys())
        tensors = [by_model[mid].tensor for mid in sorted_ids]
        weights = [by_model[mid].weight for mid in sorted_ids]
        
        strategy = get_strategy(self.strategy_name)
        kwargs = {}
        if self.strategy_name in STOCHASTIC:
            kwargs['seed'] = 42
        if self.strategy_name in BASE_REQUIRED:
            return strategy.merge(tensors, weights=weights, base=self.base, **kwargs)
        return strategy.merge(tensors, weights=weights, **kwargs)
    
    def __eq__(self, other):
        if not isinstance(other, MerkleDAGState):
            return False
        # Equal if same set of model_ids
        ids_self = {n.model_id for n in self.nodes.values()}
        ids_other = {n.model_id for n in other.nodes.values()}
        return ids_self == ids_other


# ===========================================================================
# SOLUTION 6: Hybrid Two-Phase Protocol
# ===========================================================================
#
# Phase 1 (CRDT): OR-Set of contributions — handles add/remove with
#   provably correct CRDT semantics
# Phase 2 (Resolution): Atomic N-way merge on the converged set
#
# The OR-Set uses unique tags per add, so concurrent add+remove
# resolves correctly (add-wins semantics).

class ORSetContribution:
    __slots__ = ('model_id', 'tensor', 'weight', 'tag')
    def __init__(self, model_id, tensor, weight, tag):
        self.model_id = model_id
        self.tensor = np.array(tensor, dtype=np.float64)
        self.weight = weight
        self.tag = tag

class HybridTwoPhaseState:
    """Two-phase CRDT: OR-Set accumulation + atomic resolution."""
    __slots__ = ('elements', 'tombstones', 'base', 'strategy_name', '_tag_counter')
    
    def __init__(self, strategy_name: str, base=None):
        self.elements: Dict[str, ORSetContribution] = {}  # tag → contribution
        self.tombstones: Set[str] = set()  # removed tags
        self.base = base
        self.strategy_name = strategy_name
        self._tag_counter = 0
    
    def add(self, tensor, weight=1.0, model_id=None):
        mid = model_id or tensor_id(tensor)
        self._tag_counter += 1
        tag = f"{mid}_{self._tag_counter}_{random.randint(0, 999999)}"
        self.elements[tag] = ORSetContribution(mid, tensor, weight, tag)
        return self
    
    def remove(self, model_id: str):
        """Remove all elements with given model_id."""
        for tag, elem in list(self.elements.items()):
            if elem.model_id == model_id:
                self.tombstones.add(tag)
    
    def merge(self, other: 'HybridTwoPhaseState') -> 'HybridTwoPhaseState':
        """OR-Set merge: union of elements, union of tombstones."""
        result = HybridTwoPhaseState(self.strategy_name, base=self.base)
        # Union of all elements
        for tag, elem in self.elements.items():
            result.elements[tag] = elem
        for tag, elem in other.elements.items():
            if tag not in result.elements:
                result.elements[tag] = elem
        # Union of tombstones
        result.tombstones = self.tombstones | other.tombstones
        if result.base is None and other.base is not None:
            result.base = other.base
        return result
    
    def _active_contributions(self) -> Dict[str, ORSetContribution]:
        """Get contributions not in tombstones, deduplicated by model_id."""
        active: Dict[str, ORSetContribution] = {}
        for tag, elem in sorted(self.elements.items()):
            if tag not in self.tombstones:
                if elem.model_id not in active:
                    active[elem.model_id] = elem
        return active
    
    def resolve(self) -> np.ndarray:
        active = self._active_contributions()
        if not active:
            return self.base if self.base is not None else np.array([])
        
        sorted_ids = sorted(active.keys())
        tensors = [active[mid].tensor for mid in sorted_ids]
        weights = [active[mid].weight for mid in sorted_ids]
        
        strategy = get_strategy(self.strategy_name)
        kwargs = {}
        if self.strategy_name in STOCHASTIC:
            kwargs['seed'] = 42
        if self.strategy_name in BASE_REQUIRED:
            return strategy.merge(tensors, weights=weights, base=self.base, **kwargs)
        return strategy.merge(tensors, weights=weights, **kwargs)
    
    def __eq__(self, other):
        if not isinstance(other, HybridTwoPhaseState):
            return False
        a1 = self._active_contributions()
        a2 = other._active_contributions()
        return set(a1.keys()) == set(a2.keys())


# ===========================================================================
# SOLUTION 7: Lattice Consensus (Join-Semilattice Registry)
# ===========================================================================
#
# State = registry of (model_id → (version, tensor, weight))
# Order: (v1, t1) ≤ (v2, t2) iff v1 ≤ v2
# Join: per-key max version wins (LWW semantics)
# This forms a join-semilattice → merge is commutative, associative, idempotent.

class LatticeState:
    """Join-semilattice CRDT over versioned model registry."""
    __slots__ = ('registry', 'base', 'strategy_name')
    
    def __init__(self, strategy_name: str, base=None):
        self.registry: Dict[str, Tuple[int, np.ndarray, float]] = {}
        self.base = base
        self.strategy_name = strategy_name
    
    def add(self, tensor, weight=1.0, model_id=None, version=1):
        mid = model_id or tensor_id(tensor)
        if mid in self.registry and self.registry[mid][0] >= version:
            return self  # Existing version is newer
        self.registry[mid] = (version, np.array(tensor, dtype=np.float64), weight)
        return self
    
    def merge(self, other: 'LatticeState') -> 'LatticeState':
        """Join: per-key max version wins."""
        result = LatticeState(self.strategy_name, base=self.base)
        all_keys = set(self.registry) | set(other.registry)
        for mid in all_keys:
            entry_a = self.registry.get(mid)
            entry_b = other.registry.get(mid)
            if entry_a and entry_b:
                # Take highest version; tie-break on model_id hash
                if entry_a[0] > entry_b[0]:
                    result.registry[mid] = (entry_a[0], entry_a[1].copy(), entry_a[2])
                elif entry_b[0] > entry_a[0]:
                    result.registry[mid] = (entry_b[0], entry_b[1].copy(), entry_b[2])
                else:
                    # Same version — take first deterministically
                    result.registry[mid] = (entry_a[0], entry_a[1].copy(), entry_a[2])
            elif entry_a:
                result.registry[mid] = (entry_a[0], entry_a[1].copy(), entry_a[2])
            else:
                result.registry[mid] = (entry_b[0], entry_b[1].copy(), entry_b[2])
        if result.base is None and other.base is not None:
            result.base = other.base
        return result
    
    def resolve(self) -> np.ndarray:
        if not self.registry:
            return self.base if self.base is not None else np.array([])
        
        sorted_ids = sorted(self.registry.keys())
        tensors = [self.registry[mid][1] for mid in sorted_ids]
        weights = [self.registry[mid][2] for mid in sorted_ids]
        
        strategy = get_strategy(self.strategy_name)
        kwargs = {}
        if self.strategy_name in STOCHASTIC:
            kwargs['seed'] = 42
        if self.strategy_name in BASE_REQUIRED:
            return strategy.merge(tensors, weights=weights, base=self.base, **kwargs)
        return strategy.merge(tensors, weights=weights, **kwargs)
    
    def __eq__(self, other):
        if not isinstance(other, LatticeState):
            return False
        return set(self.registry.keys()) == set(other.registry.keys())


# ===========================================================================
# TEST HARNESS
# ===========================================================================

SOLUTIONS = {
    'SOL-1: G-Set Accumulator': GSetState,
    'SOL-2: Delta-State CRDT': DeltaState,
    'SOL-3: Monoid Accumulator': MonoidState,
    'SOL-4: Canonical Order': CanonicalOrderState,
    'SOL-5: Merkle-DAG': MerkleDAGState,
    'SOL-6: Hybrid Two-Phase': HybridTwoPhaseState,
    'SOL-7: Lattice Consensus': LatticeState,
}

def make_state(sol_cls, strategy_name, base=None):
    """Create a fresh CRDT state with one model added."""
    return sol_cls(strategy_name, base=base)


def test_crdt_laws(sol_name, sol_cls, strategy_name, trials=30, tensor_size=10):
    """
    Test all 3 CRDT laws for a given solution × strategy combination.
    
    Returns dict with:
      commutative: bool
      associative: bool
      idempotent: bool
      resolve_consistent: bool (merge order doesn't change resolved value)
      failures: {law: count}
    """
    needs_base = strategy_name in BASE_REQUIRED
    
    results = {
        'commutative': True,
        'associative': True,
        'idempotent': True,
        'resolve_consistent': True,
        'failures': {'commutative': 0, 'associative': 0, 'idempotent': 0, 'resolve': 0},
    }
    
    for trial in range(trials):
        seed_base = trial * 100
        a = gen_tensor(tensor_size, seed=seed_base + 1)
        b = gen_tensor(tensor_size, seed=seed_base + 2)
        c = gen_tensor(tensor_size, seed=seed_base + 3)
        base = gen_tensor(tensor_size, seed=seed_base + 99) if needs_base else None
        
        # Create states with unique model IDs
        def make_single(tensor, model_id, w=1.0):
            s = sol_cls(strategy_name, base=base)
            s.add(tensor, weight=w, model_id=model_id)
            return s
        
        sa = make_single(a, 'model_A')
        sb = make_single(b, 'model_B')
        sc = make_single(c, 'model_C')
        
        # --- COMMUTATIVITY: merge(SA, SB) == merge(SB, SA) ---
        try:
            ab = sa.merge(sb)
            ba = sb.merge(sa)
            # State equality
            if not ab.__eq__(ba):
                results['commutative'] = False
                results['failures']['commutative'] += 1
            # Resolve equality
            r_ab = ab.resolve()
            r_ba = ba.resolve()
            if not approx_equal(r_ab, r_ba):
                results['resolve_consistent'] = False
                results['failures']['resolve'] += 1
        except Exception as e:
            results['commutative'] = False
            results['failures']['commutative'] += 1
        
        # --- ASSOCIATIVITY: merge(merge(SA, SB), SC) == merge(SA, merge(SB, SC)) ---
        try:
            ab_c = sa.merge(sb).merge(sc)
            a_bc = sa.merge(sb.merge(sc))
            # State equality
            if not ab_c.__eq__(a_bc):
                results['associative'] = False
                results['failures']['associative'] += 1
            # Resolve equality
            r_abc = ab_c.resolve()
            r_a_bc = a_bc.resolve()
            if not approx_equal(r_abc, r_a_bc):
                results['resolve_consistent'] = False
                results['failures']['resolve'] += 1
        except Exception as e:
            results['associative'] = False
            results['failures']['associative'] += 1
        
        # --- IDEMPOTENCY: merge(SA, SA) == SA ---
        try:
            aa = sa.merge(sa)
            if not aa.__eq__(sa):
                results['idempotent'] = False
                results['failures']['idempotent'] += 1
            # Resolve should be identical
            r_aa = aa.resolve()
            r_a = sa.resolve()
            # For single-model states, resolve just returns the model
            # so this should always match
            if not approx_equal(r_aa, r_a):
                results['resolve_consistent'] = False
                results['failures']['resolve'] += 1
        except Exception as e:
            results['idempotent'] = False
            results['failures']['idempotent'] += 1
    
    return results


def run_full_matrix():
    """Run all solutions × all strategies × all laws."""
    strategies = list_strategies()
    
    print(f"\n{'='*80}")
    print(f"  CRDT-MERGE R&D: 7 Solutions × {len(strategies)} Strategies × 3 Laws")
    print(f"{'='*80}\n")
    
    all_results = {}
    summary = {}
    
    for sol_name, sol_cls in SOLUTIONS.items():
        print(f"\n{'─'*60}")
        print(f"  {sol_name}")
        print(f"{'─'*60}")
        
        sol_results = {}
        true_crdt_count = 0
        
        for strat_name in strategies:
            try:
                result = test_crdt_laws(sol_name, sol_cls, strat_name, trials=30)
                sol_results[strat_name] = result
                
                c = '✅' if result['commutative'] else '❌'
                a = '✅' if result['associative'] else '❌'
                i = '✅' if result['idempotent'] else '❌'
                r = '✅' if result['resolve_consistent'] else '❌'
                
                all_pass = result['commutative'] and result['associative'] and result['idempotent']
                if all_pass:
                    true_crdt_count += 1
                
                status = '🟢 TRUE CRDT' if all_pass else '🔴 FAILED'
                print(f"  {strat_name:30s}  C:{c} A:{a} I:{i} R:{r}  {status}")
                
            except Exception as e:
                sol_results[strat_name] = {
                    'commutative': False, 'associative': False,
                    'idempotent': False, 'resolve_consistent': False,
                    'error': str(e),
                }
                print(f"  {strat_name:30s}  ⚠️  ERROR: {str(e)[:60]}")
        
        all_results[sol_name] = sol_results
        summary[sol_name] = {
            'true_crdt_count': true_crdt_count,
            'total': len(strategies),
            'percentage': f"{100*true_crdt_count/len(strategies):.0f}%",
        }
        print(f"\n  ═══ {sol_name}: {true_crdt_count}/{len(strategies)} TRUE CRDTs ({summary[sol_name]['percentage']}) ═══")
    
    # ===== GRAND SUMMARY =====
    print(f"\n\n{'='*80}")
    print(f"  GRAND SUMMARY")
    print(f"{'='*80}\n")
    
    for sol_name, s in summary.items():
        bar = '█' * s['true_crdt_count'] + '░' * (s['total'] - s['true_crdt_count'])
        print(f"  {sol_name:35s}  {s['true_crdt_count']:2d}/{s['total']}  [{bar}]  {s['percentage']}")
    
    # Best solution
    best = max(summary.items(), key=lambda x: x[1]['true_crdt_count'])
    print(f"\n  🏆 BEST: {best[0]} — {best[1]['true_crdt_count']}/{best[1]['total']} strategies are TRUE CRDTs")
    
    # Save detailed results
    output = {
        'summary': summary,
        'details': {},
    }
    for sol_name, sol_results in all_results.items():
        output['details'][sol_name] = {}
        for strat, res in sol_results.items():
            output['details'][sol_name][strat] = {
                k: v for k, v in res.items() if k != 'failures'
            }
            output['details'][sol_name][strat]['failures'] = res.get('failures', {})
    
    output_path = os.path.join(os.path.dirname(__file__), 'crdt_solutions_results.json')
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  📊 Detailed results saved to: {output_path}")
    
    return all_results, summary


if __name__ == '__main__':
    results, summary = run_full_matrix()
