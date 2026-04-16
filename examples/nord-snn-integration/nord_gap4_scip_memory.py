"""
Gap 4: SCIP memory lifecycle for Genesis Triple Memory.

5 primitives from the Synapse Convergent Intelligence Protocol:
  EXPERIENCE -> new spike pattern enters structural bank
  CONTRIBUTE -> pattern propagates to shared memory
  ABSORB     -> merged patterns enter auxiliary overflow
  EVICT      -> old patterns pruned (context window rotation)
  REGENERATE -> full state reconstructed from CRDT deltas

Branch: synapse/protocol
"""

import time
import hashlib
import numpy as np
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from crdt_merge.core import LWWMap, ORSet, GCounter
from crdt_merge.clocks import VectorClock


class MemoryType(str, Enum):
    PATTERN = "pattern"       # learned firing pattern
    SKILL = "skill"           # composite capability
    FACT = "fact"             # declarative knowledge
    CONTEXT = "context"       # contextual state


@dataclass
class MemoryEntry:
    """A single entry in the SCIP-managed memory."""
    entry_id: str
    memory_type: MemoryType
    content_hash: str
    value: Any
    trust_score: float = 0.5
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    source_zone: str = ""


class SCIPMemoryManager:
    """SCIP lifecycle management for Nord Genesis memory banks.

    Maps the 5 SCIP primitives to Genesis operations:
      Structural bank -> EXPERIENCE (new patterns)
      Personal bank   -> CONTRIBUTE (shared patterns)
      Auxiliary bank   -> ABSORB (overflow/merged)
      Eviction        -> EVICT (prune old patterns)
      Recovery        -> REGENERATE (reconstruct from CRDT)
    """

    def __init__(self, node_id: str, max_entries: int = 256):
        self.node_id = node_id
        self.max_entries = max_entries

        # CRDT-backed stores for each bank
        self.structural = LWWMap()   # EXPERIENCE target
        self.personal = LWWMap()     # CONTRIBUTE target
        self.auxiliary = LWWMap()    # ABSORB target

        # Track all entry IDs (add-wins, never lost)
        self.entry_registry = ORSet()

        # Lifecycle counters
        self.experience_count = GCounter()
        self.contribute_count = GCounter()
        self.absorb_count = GCounter()
        self.evict_count = GCounter()
        self.regenerate_count = GCounter()

        # Causal clock
        self.clock = VectorClock()

        # In-memory entry cache
        self._entries: Dict[str, MemoryEntry] = {}

    def experience(self, entry: MemoryEntry) -> str:
        """EXPERIENCE: new spike pattern enters structural bank."""
        self.clock = self.clock.increment(self.node_id)
        self.experience_count.increment(self.node_id)

        self._entries[entry.entry_id] = entry
        self.entry_registry.add(entry.entry_id)
        self.structural.set(
            entry.entry_id,
            {"type": entry.memory_type.value, "hash": entry.content_hash,
             "trust": entry.trust_score, "zone": entry.source_zone},
            timestamp=entry.created_at, node_id=self.node_id,
        )
        return entry.entry_id

    def contribute(self, entry_id: str) -> bool:
        """CONTRIBUTE: promote pattern from structural to personal (shared)."""
        entry = self._entries.get(entry_id)
        if not entry:
            return False

        self.clock = self.clock.increment(self.node_id)
        self.contribute_count.increment(self.node_id)

        self.personal.set(
            entry_id,
            {"type": entry.memory_type.value, "hash": entry.content_hash,
             "trust": entry.trust_score, "promoted_at": time.time()},
            timestamp=time.time(), node_id=self.node_id,
        )
        return True

    def absorb(self, entry_ids: List[str], merged_id: str, merged_hash: str) -> str:
        """ABSORB: merge multiple entries into auxiliary bank."""
        self.clock = self.clock.increment(self.node_id)
        self.absorb_count.increment(self.node_id)

        self.auxiliary.set(
            merged_id,
            {"source_entries": entry_ids, "hash": merged_hash,
             "absorbed_at": time.time()},
            timestamp=time.time(), node_id=self.node_id,
        )
        self.entry_registry.add(merged_id)
        return merged_id

    def evict(self, entry_id: str) -> bool:
        """EVICT: prune old pattern from active memory.
        The entry stays in the CRDT registry (add-wins) but is marked evicted.
        """
        if entry_id not in self._entries:
            return False

        self.clock = self.clock.increment(self.node_id)
        self.evict_count.increment(self.node_id)

        del self._entries[entry_id]
        return True

    def regenerate(self) -> Dict[str, Any]:
        """REGENERATE: reconstruct full state from CRDT stores."""
        self.regenerate_count.increment(self.node_id)

        state = {
            "structural": dict(self.structural.value),
            "personal": dict(self.personal.value),
            "auxiliary": dict(self.auxiliary.value),
            "registry_size": len(self.entry_registry.value),
            "active_entries": len(self._entries),
        }
        return state

    def merge(self, other: "SCIPMemoryManager") -> "SCIPMemoryManager":
        """CRDT merge of two SCIP memory managers."""
        result = SCIPMemoryManager(f"{self.node_id}+{other.node_id}", self.max_entries)
        result.structural = self.structural.merge(other.structural)
        result.personal = self.personal.merge(other.personal)
        result.auxiliary = self.auxiliary.merge(other.auxiliary)
        result.entry_registry = self.entry_registry.merge(other.entry_registry)
        result.experience_count = self.experience_count.merge(other.experience_count)
        result.contribute_count = self.contribute_count.merge(other.contribute_count)
        result.absorb_count = self.absorb_count.merge(other.absorb_count)
        result.evict_count = self.evict_count.merge(other.evict_count)
        result.regenerate_count = self.regenerate_count.merge(other.regenerate_count)
        result.clock = self.clock.merge(other.clock)
        result._entries = dict(self._entries)
        result._entries.update(other._entries)
        return result

    @property
    def stats(self) -> dict:
        return {
            "node_id": self.node_id,
            "experienced": self.experience_count.value,
            "contributed": self.contribute_count.value,
            "absorbed": self.absorb_count.value,
            "evicted": self.evict_count.value,
            "regenerated": self.regenerate_count.value,
            "structural_entries": len(self.structural.value),
            "personal_entries": len(self.personal.value),
            "auxiliary_entries": len(self.auxiliary.value),
            "registry_total": len(self.entry_registry.value),
            "active_in_memory": len(self._entries),
        }
