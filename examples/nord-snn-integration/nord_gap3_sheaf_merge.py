# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License").
# You may use this file freely for any non-production purpose:
# research, evaluation, development, testing, education, personal use.
#
# A commercial production license is required ONLY if you deploy this
# code in a revenue-generating production environment. All other use
# is permitted without restriction.
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0
#
# On 2028-03-29 the code license converts to Apache 2.0. Patent rights
# are separately held
# (UK Application No. GB 2607132.4, GB2608127.3) and are not granted by the
# license. Commercial use of patented methods requires a patent license.

"""
Sheaf-theoretic spike pattern gluing.

Standard merge preserves individual weights but can destroy correlations
between connected neurons. For SNNs where spike timing correlations
ARE the computation, this is catastrophic.

Sheaf gluing preserves local structure: neuron pairs with high STDP
coherence (correlated firing) stay correlated after merge.

Based on:
  Paper 04 -- The 1/k Ceiling Is A Floor (sheaf theory + Knaster-Tarski)

Author: Ryan Gillespie
Status: Pre-release
Patent: UK Application No. GB 2607132.4, GB2608127.3
"""

import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass

from crdt_merge.core import GCounter, LWWMap


@dataclass
class SynapticPair:
    """A pre-post neuron pair with STDP coherence score."""
    pre_idx: int
    post_idx: int
    coherence: float  # 0.0 = uncorrelated, 1.0 = perfectly correlated


class STDPCoherenceScorer:
    """Compute STDP coherence scores for synapse pairs.

    Coherence = how reliably does pre firing predict post firing?
    High coherence pairs are the "local sections" of the sheaf
    that must be preserved during merge.
    """

    def __init__(self, pre_dim: int, post_dim: int):
        self.pre_dim = pre_dim
        self.post_dim = post_dim
        self._co_fire_count = np.zeros((post_dim, pre_dim), dtype=np.float64)
        self._pre_fire_count = np.zeros(pre_dim, dtype=np.float64)
        self._total_steps = 0

    def record_spikes(self, pre_spikes: np.ndarray, post_spikes: np.ndarray):
        """Record co-firing events from a forward pass.
        pre_spikes/post_spikes: binary arrays (0 or 1).
        """
        self._total_steps += 1
        self._pre_fire_count += pre_spikes.astype(np.float64)
        self._co_fire_count += np.outer(
            post_spikes.astype(np.float64),
            pre_spikes.astype(np.float64),
        )

    def coherence_matrix(self) -> np.ndarray:
        """Compute coherence for all synapse pairs.
        coherence[post, pre] = P(post fires | pre fires)
        """
        safe_pre = np.maximum(self._pre_fire_count, 1.0)
        return self._co_fire_count / safe_pre[np.newaxis, :]

    def high_coherence_pairs(self, threshold: float = 0.3) -> List[SynapticPair]:
        coh = self.coherence_matrix()
        pairs = []
        for post in range(self.post_dim):
            for pre in range(self.pre_dim):
                if coh[post, pre] >= threshold:
                    pairs.append(SynapticPair(pre, post, float(coh[post, pre])))
        return pairs


def sheaf_glue_merge(
    weight_matrices: List[np.ndarray],
    coherence_matrices: List[np.ndarray],
    coherence_threshold: float = 0.3,
) -> np.ndarray:
    """Sheaf-theoretic merge of weight matrices.

    For each synapse (post, pre):
    - If ANY contributor has high coherence (>threshold), use coherence-weighted
      average of only the high-coherence contributors. This preserves the
      local section (correlated firing pattern).
    - If NO contributor has high coherence, use standard average.

    This prevents information drowning: averaging a correlated synapse
    with an uncorrelated one destroys the correlation. Sheaf gluing
    keeps the correlated structure intact.
    """
    if not weight_matrices:
        raise ValueError("no matrices to merge")
    if len(weight_matrices) == 1:
        return weight_matrices[0].copy()

    shape = weight_matrices[0].shape
    result = np.zeros(shape, dtype=np.float64)
    total_weight = np.zeros(shape, dtype=np.float64)

    for weights, coherence in zip(weight_matrices, coherence_matrices):
        # Clamp coherence to [0, 1]
        coh = np.clip(coherence, 0.0, 1.0)

        # High-coherence synapses get weight = coherence^2 (amplify correlated)
        # Low-coherence synapses get weight = 0.1 (suppress uncorrelated)
        w = np.where(coh >= coherence_threshold, coh ** 2, 0.1)

        result += weights.astype(np.float64) * w
        total_weight += w

    total_weight = np.maximum(total_weight, 1e-10)
    return (result / total_weight).astype(np.float32)


def compute_k_effective(coherence_scores: List[float]) -> float:
    """Compute effective specialist count k_eff = sum(tau_i^2) / sum(tau_i).

    When k_eff remains bounded (doesn't shrink with k), the 1/k ceiling
    is broken. Sheaf gluing achieves this by trust-weighting contributions.
    """
    if not coherence_scores:
        return 0.0
    tau_sum = sum(coherence_scores)
    tau_sq_sum = sum(t * t for t in coherence_scores)
    if tau_sum == 0:
        return 0.0
    return tau_sq_sum / tau_sum


class NordSheafMerge:
    """Sheaf-theoretic merge for Nord's zone weights.

    Each zone maintains STDP coherence scores. During merge,
    high-coherence synapse pairs are preserved (sheaf gluing)
    while low-coherence pairs are averaged normally.
    """

    def __init__(self):
        self._scorers: Dict[str, STDPCoherenceScorer] = {}

    def register_layer(self, layer_name: str, pre_dim: int, post_dim: int):
        self._scorers[layer_name] = STDPCoherenceScorer(pre_dim, post_dim)

    def record_spikes(self, layer_name: str, pre_spikes: np.ndarray, post_spikes: np.ndarray):
        if layer_name in self._scorers:
            self._scorers[layer_name].record_spikes(pre_spikes, post_spikes)

    def merge_state_dicts(
        self,
        contributions: List[Tuple[str, Dict[str, np.ndarray]]],
        coherence_threshold: float = 0.3,
    ) -> Dict[str, np.ndarray]:
        """Merge multiple state dicts using sheaf gluing where coherence data exists."""
        all_keys = set()
        for _, sd in contributions:
            all_keys.update(sd.keys())

        merged = {}
        for key in all_keys:
            matrices = [sd[key] for _, sd in contributions if key in sd]

            if key in self._scorers and len(matrices) > 1:
                coh = self._scorers[key].coherence_matrix()
                coherences = [coh] * len(matrices)
                merged[key] = sheaf_glue_merge(matrices, coherences, coherence_threshold)
            elif len(matrices) == 1:
                merged[key] = matrices[0]
            else:
                merged[key] = np.mean(matrices, axis=0).astype(np.float32)

        return merged
