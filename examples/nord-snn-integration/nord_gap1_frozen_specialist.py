"""
Frozen specialist architecture for Nord SNN.

After emergence (step 25K), freeze the memory cortex entirely.
New capabilities added as frozen specialists merged via CRDT.
Catastrophic forgetting becomes architecturally impossible.

Based on:
  Paper 01 -- The Convergence Trick (Stability-Plasticity Dilemma)
  Paper 07 -- The Undying Collective (Catastrophic Forgetting)
  Branch: synapse/living-model

Author: Ryan Gillespie
Status: Pre-release
Patent: UK Application No. GB 2607132.4, GB2608127.3
"""

import time
import hashlib
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from crdt_merge.model.crdt_state import CRDTMergeState
from crdt_merge.core import GCounter, LWWRegister, LWWMap, ORSet


@dataclass
class FrozenSpecialist:
    """An immutable snapshot of trained weights."""
    specialist_id: str
    weights: Dict[str, np.ndarray]
    frozen_at_step: int
    capability: str
    content_hash: str = ""

    def __post_init__(self):
        if not self.content_hash:
            h = hashlib.sha256()
            for k in sorted(self.weights.keys()):
                h.update(k.encode())
                h.update(self.weights[k].astype(np.float32).tobytes()[:128])
            self.content_hash = h.hexdigest()


class FrozenSpecialistRegistry:
    """Registry of frozen specialists backed by ORSet (add-wins).

    Once a specialist is frozen and registered, it cannot be modified
    or removed. New capabilities = new frozen specialist added.
    Old specialists persist forever via CRDT add-wins semantics.
    """

    def __init__(self):
        self._specialists: Dict[str, FrozenSpecialist] = {}
        self._registry = ORSet()
        self._freeze_log = LWWMap()
        self._specialist_count = GCounter()

    def freeze_and_register(
        self, specialist_id: str, weights: Dict[str, np.ndarray],
        step: int, capability: str,
    ) -> FrozenSpecialist:
        spec = FrozenSpecialist(
            specialist_id=specialist_id, weights=weights,
            frozen_at_step=step, capability=capability,
        )
        self._specialists[specialist_id] = spec
        self._registry.add(specialist_id)
        self._freeze_log.set(
            specialist_id, {"step": step, "capability": capability, "hash": spec.content_hash},
            timestamp=time.time(), node_id=specialist_id,
        )
        self._specialist_count.increment("registry")
        return spec

    def get(self, specialist_id: str) -> Optional[FrozenSpecialist]:
        return self._specialists.get(specialist_id)

    def merge_specialists(
        self, specialist_ids: List[str], strategy: str = "weight_average",
    ) -> Dict[str, np.ndarray]:
        """Merge frozen specialists via CRDT. None are modified."""
        all_keys = set()
        for sid in specialist_ids:
            spec = self._specialists[sid]
            all_keys.update(spec.weights.keys())

        merged = {}
        for key in all_keys:
            state = CRDTMergeState(strategy)
            for sid in specialist_ids:
                spec = self._specialists[sid]
                if key in spec.weights:
                    state.add(tensor=spec.weights[key], model_id=sid, weight=1.0)
            merged[key] = np.asarray(state.resolve())

        return merged

    @property
    def count(self) -> int:
        return len(self._specialists)

    @property
    def capabilities(self) -> set:
        return {s.capability for s in self._specialists.values()}

    def merge_registry(self, other: "FrozenSpecialistRegistry") -> "FrozenSpecialistRegistry":
        result = FrozenSpecialistRegistry()
        result._registry = self._registry.merge(other._registry)
        result._freeze_log = self._freeze_log.merge(other._freeze_log)
        result._specialist_count = self._specialist_count.merge(other._specialist_count)
        result._specialists = dict(self._specialists)
        result._specialists.update(other._specialists)
        return result


class NordFreezeAfterEmergence:
    """Freeze memory cortex weights after emergence detection.

    Integrates with EmergenceDetector from nord_e4_visionary.
    When emergence fires, snapshot the memory cortex as a frozen specialist.
    Future training produces new specialists that merge with the frozen base.
    The emerged capability (cross-lingual, memory routing) is locked in forever.
    """

    def __init__(self):
        self.registry = FrozenSpecialistRegistry()
        self._frozen_zones: Dict[str, int] = {}  # zone -> step frozen at
        self._active_weights: Dict[str, np.ndarray] = {}

    def freeze_zone(
        self, zone: str, weights: Dict[str, np.ndarray], step: int, capability: str,
    ) -> FrozenSpecialist:
        zone_weights = {k: v for k, v in weights.items() if zone in k.lower()}
        spec = self.registry.freeze_and_register(
            f"{zone}_step{step}", zone_weights, step, capability,
        )
        self._frozen_zones[zone] = step
        return spec

    def is_frozen(self, zone: str) -> bool:
        return zone in self._frozen_zones

    def merge_new_with_frozen(
        self, new_weights: Dict[str, np.ndarray], frozen_weight: float = 0.7,
    ) -> Dict[str, np.ndarray]:
        """Merge new training results with frozen specialists.
        Frozen specialists get higher weight (default 0.7) to preserve
        emerged capabilities. New contributions get 0.3.
        """
        merged = {}
        for key in new_weights:
            zone = self._classify_zone(key)
            if zone in self._frozen_zones:
                spec_id = f"{zone}_step{self._frozen_zones[zone]}"
                spec = self.registry.get(spec_id)
                if spec and key in spec.weights:
                    state = CRDTMergeState("weight_average")
                    state.add(spec.weights[key], model_id="frozen", weight=frozen_weight)
                    state.add(new_weights[key], model_id="new", weight=1.0 - frozen_weight)
                    merged[key] = np.asarray(state.resolve())
                    continue
            merged[key] = new_weights[key]
        return merged

    def _classify_zone(self, layer_name: str) -> str:
        ln = layer_name.lower()
        if "memory" in ln or "genesis" in ln:
            return "memory_cortex"
        if "sensory" in ln:
            return "sensory"
        if "association" in ln or "moe" in ln:
            return "association"
        if "executive" in ln:
            return "executive"
        return "other"

    @property
    def frozen_zones(self) -> Dict[str, int]:
        return dict(self._frozen_zones)
