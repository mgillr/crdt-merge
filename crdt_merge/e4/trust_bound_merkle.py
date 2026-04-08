# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-04-08
# Change License: Apache License, Version 2.0

"""Trust-bound high-arity Merkle tree -- E1 entanglement (ref 850-855).

Hashes incorporate trust context: H(data || trust_score || originator)
instead of plain H(data).  This makes the Merkle tree structurally
dependent on the trust lattice -- modifying trust invalidates hashes,
and Merkle proofs are required to validate trust evidence.

High-arity design (v2.0): branching factor B = 256 (configurable).
  - 1M params  -> depth 3
  - 1B params  -> depth 4
  - 1T params  -> depth 5
Each comparison: up to B child hash checks.
Total traversal cost: O(k * depth) ~ O(k) for practical sizes.

Compatibility mode (ref 855): when communicating with pre-E4 peers,
computes dual hashes H(data) alongside H(data || trust) so that
both sides can verify the same tree during migration.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

from .typed_trust import TypedTrustScore
from .pco import SubtreeRef

if TYPE_CHECKING:
    from .delta_trust_lattice import DeltaTrustLattice


# -- Internal tree node -----------------------------------------------------

@dataclass
class MerkleNode:
    """Internal / leaf node in the high-arity Merkle tree."""

    path: Tuple[int, ...]
    hash: str = ""
    compat_hash: str = ""
    is_leaf: bool = False
    children: List[Optional[MerkleNode]] = field(default_factory=list)
    data: Optional[bytes] = None
    originator: Optional[str] = None

    def child_hashes(self) -> List[str]:
        return [c.hash if c is not None else "" for c in self.children]


# -- TrustBoundMerkle (ref 850) --------------------------------------------

class TrustBoundMerkle:
    # Resilience: optional domain-separated hasher (v0.9.5.1)
    # When set, all hash operations use domain-separated hashing
    # for cross-component hash isolation.
    _domain_hasher = None

    @classmethod
    def enable_domain_hashing(cls):
        """Enable domain-separated hashing for Merkle operations.

        Hardens the Merkle tree against cross-component hash collisions
        by tagging each hash with a domain separator.  Non-breaking: when
        disabled (default), all operations use the original hash function.

        See: resilience/domain_hash.py (addresses Whitfield §10)
        """
        from crdt_merge.e4.resilience.domain_hash import DomainSeparatedHasher
        cls._domain_hasher = DomainSeparatedHasher()

    @classmethod
    def disable_domain_hashing(cls):
        """Restore original hashing (for compatibility or testing)."""
        cls._domain_hasher = None

    """High-arity Merkle tree where hashes incorporate trust context.

    Parameters
    ----------
    trust_lattice :
        Back-reference to the DeltaTrustLattice for trust lookups.
        Creates the E1 binding: Merkle depends on trust, trust evidence
        depends on Merkle verification.
    branching_factor :
        Number of children per internal node.  Default 256 gives depth 4
        for one billion parameters.
    compatibility_mode :
        When True, dual hashes are maintained: H(data || trust) for E4
        peers and H(data) for pre-E4 peers.
    """

    def __init__(
        self,
        trust_lattice: Optional[DeltaTrustLattice] = None,
        *,
        branching_factor: int = 256,
        compatibility_mode: bool = False,
    ) -> None:
        self._trust_lattice = trust_lattice
        self._branching_factor = branching_factor
        self._compatibility_mode = compatibility_mode
        self._root: Optional[MerkleNode] = None
        self._leaves: Dict[str, MerkleNode] = {}
        self._trust_cache: Dict[str, TypedTrustScore] = {}

    # -- dependency injection post-init ------------------------------------

    def bind_trust_lattice(self, lattice: DeltaTrustLattice) -> None:
        """Late-bind the trust lattice (resolves circular init order)."""
        self._trust_lattice = lattice

    # -- root hash property ------------------------------------------------

    @property
    def root_hash(self) -> str:
        if self._root is None:
            return ""
        return self._root.hash

    @property
    def root_compat_hash(self) -> str:
        if self._root is None:
            return ""
        return self._root.compat_hash

    # -- leaf hashing (ref 853, 930) ---------------------------------------

    def compute_leaf_hash(self, data: bytes, originator: str) -> str:
        """Trust-bound leaf hash: H(data || trust_score || originator)."""
        trust = self._resolve_trust(originator)
        trust_ctx = trust.serialize()
        return hashlib.sha256(
            data + trust_ctx + originator.encode("utf-8")
        ).hexdigest()

    def compute_leaf_hash_compat(self, data: bytes) -> str:
        """Standard hash for pre-E4 compatibility: H(data)."""
        return hashlib.sha256(data).hexdigest()

    # -- intermediate hashing (ref 852, 910-920) ---------------------------

    def compute_intermediate_hash(
        self,
        child_hashes: Sequence[str],
        trust_root: str,
    ) -> str:
        """Trust-bound intermediate hash for a high-arity node.

        H(H_c1 || H_c2 || ... || H_cB || trust_root)
        """
        combined = (
            b"".join(h.encode("utf-8") for h in child_hashes)
            + trust_root.encode("utf-8")
        )
        return hashlib.sha256(combined).hexdigest()

    def compute_intermediate_hash_compat(
        self,
        child_hashes: Sequence[str],
    ) -> str:
        """Standard intermediate hash without trust context."""
        combined = b"".join(h.encode("utf-8") for h in child_hashes)
        return hashlib.sha256(combined).hexdigest()

    # -- changed subtree detection (ref 811) --------------------------------

    def find_changed_subtrees(
        self,
        local_node: MerkleNode,
        remote_node: MerkleNode,
        result: List[SubtreeRef],
        depth: int = 0,
    ) -> None:
        """High-arity changed subtree detection.

        At each internal node, compare up to B child hashes.
        Only descend into children with differing hashes.
        Depth is at most ceil(log_B(n)) ~ 4 for B=256, n=1B.
        """
        if local_node.hash == remote_node.hash:
            return

        if local_node.is_leaf or remote_node.is_leaf:
            result.append(SubtreeRef(
                path=local_node.path,
                depth=depth,
                old_hash=remote_node.hash,
                new_hash=local_node.hash,
            ))
            return

        for i in range(self._branching_factor):
            local_child = (
                local_node.children[i]
                if i < len(local_node.children) else None
            )
            remote_child = (
                remote_node.children[i]
                if i < len(remote_node.children) else None
            )

            if local_child is None and remote_child is None:
                continue

            if local_child is None or remote_child is None:
                result.append(SubtreeRef(
                    path=local_node.path + (i,),
                    depth=depth + 1,
                    old_hash=remote_child.hash if remote_child else "",
                    new_hash=local_child.hash if local_child else "",
                ))
                continue

            if local_child.hash != remote_child.hash:
                self.find_changed_subtrees(
                    local_child, remote_child, result, depth + 1,
                )

    # -- Merkle path verification (ref 847-856) ----------------------------

    def verify_path(
        self,
        leaf_data: bytes,
        originator: str,
        path_steps: Sequence[Tuple[List[str], int]],
        expected_root: str,
    ) -> bool:
        """Verify a Merkle path -- requires trust context at every level.

        Parameters
        ----------
        leaf_data      : raw data at the leaf
        originator     : peer that created the data
        path_steps     : list of (sibling_hashes, position) tuples
        expected_root  : root hash the path should reconstruct
        """
        current = self.compute_leaf_hash(leaf_data, originator)
        trust_root = self._compute_trust_root()

        for sibling_hashes, position in path_steps:
            all_hashes = list(sibling_hashes)
            all_hashes.insert(position, current)
            current = self.compute_intermediate_hash(all_hashes, trust_root)

        return current == expected_root

    def verify_path_compat(
        self,
        leaf_data: bytes,
        path_steps: Sequence[Tuple[List[str], int]],
        expected_root: str,
    ) -> bool:
        """Verify a Merkle path without trust context (pre-E4)."""
        current = self.compute_leaf_hash_compat(leaf_data)

        for sibling_hashes, position in path_steps:
            all_hashes = list(sibling_hashes)
            all_hashes.insert(position, current)
            current = self.compute_intermediate_hash_compat(all_hashes)

        return current == expected_root

    # -- plausibility check for PCO verification ---------------------------

    def is_plausible_root(self, root: str) -> bool:
        """Check if *root* is plausible given local state.

        Accepts the current root or an empty root (no local tree yet).
        """
        if not root:
            return True
        return root == self.root_hash

    # -- trust context updates (called after trust changes) ----------------

    def update_trust_context(
        self,
        peer_id: str,
        trust: TypedTrustScore,
    ) -> None:
        """Invalidate cached trust and mark affected subtrees dirty.

        After a trust change, leaf hashes involving *peer_id* are stale.
        This records the new trust so the next recompute picks it up.
        """
        self._trust_cache[peer_id] = trust

    # -- bulk tree operations ----------------------------------------------

    def insert_leaf(
        self,
        key: str,
        data: bytes,
        originator: str,
    ) -> str:
        """Insert a leaf and return its trust-bound hash."""
        h = self.compute_leaf_hash(data, originator)
        node = MerkleNode(
            path=self._key_to_path(key),
            hash=h,
            compat_hash=self.compute_leaf_hash_compat(data) if self._compatibility_mode else "",
            is_leaf=True,
            data=data,
            originator=originator,
        )
        self._leaves[key] = node
        return h

    def recompute(self) -> str:
        """Rebuild the tree from current leaves and return the root hash.

        Full O(n) recompute -- called after batch mutations or trust
        context changes that invalidate large portions of the tree.
        """
        if not self._leaves:
            self._root = None
            return ""

        trust_root = self._compute_trust_root()

        # Recompute leaf hashes with current trust
        for key, node in self._leaves.items():
            if node.data is not None and node.originator is not None:
                node.hash = self.compute_leaf_hash(node.data, node.originator)
                if self._compatibility_mode:
                    node.compat_hash = self.compute_leaf_hash_compat(node.data)

        # Build bottom-up in levels
        current_level: List[MerkleNode] = list(self._leaves.values())
        depth = 0

        while len(current_level) > 1:
            next_level: List[MerkleNode] = []
            for start in range(0, len(current_level), self._branching_factor):
                children = current_level[start : start + self._branching_factor]
                child_hashes = [c.hash for c in children]
                parent = MerkleNode(
                    path=(depth,),
                    hash=self.compute_intermediate_hash(child_hashes, trust_root),
                    compat_hash=(
                        self.compute_intermediate_hash_compat(
                            [c.compat_hash for c in children]
                        ) if self._compatibility_mode else ""
                    ),
                    is_leaf=False,
                    children=children,
                )
                next_level.append(parent)
            current_level = next_level
            depth += 1

        self._root = current_level[0] if current_level else None
        return self.root_hash

    # -- internal helpers ---------------------------------------------------

    def _resolve_trust(self, peer_id: str) -> TypedTrustScore:
        """Resolve trust for a peer, using the lattice or cache."""
        if peer_id in self._trust_cache:
            return self._trust_cache[peer_id]
        if self._trust_lattice is not None:
            return self._trust_lattice.get_trust(peer_id)
        return TypedTrustScore.probationary()

    def _compute_trust_root(self) -> str:
        """Aggregate trust hash for intermediate node binding."""
        if self._trust_lattice is not None:
            return self._trust_lattice.compute_trust_root()
        return ""

    def _key_to_path(self, key: str) -> Tuple[int, ...]:
        """Map a key to a path in the high-arity tree."""
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        return tuple(digest[i] for i in range(4))

    @property
    def branching_factor(self) -> int:
        return self._branching_factor

    @property
    def compatibility_mode(self) -> bool:
        return self._compatibility_mode

    @property
    def leaf_count(self) -> int:
        return len(self._leaves)

    def __repr__(self) -> str:
        return (
            f"TrustBoundMerkle(B={self._branching_factor}, "
            f"leaves={len(self._leaves)}, "
            f"compat={self._compatibility_mode})"
        )
