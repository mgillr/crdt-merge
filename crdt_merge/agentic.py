# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""
Agentic AI State Merge — CRDT containers for multi-agent orchestration.

Purpose-built CRDT containers for AI agent frameworks (CrewAI, AutoGen,
LangGraph). Every merge is conflict-free: commutative, associative,
idempotent — agents can sync state in any order and always converge.

Classes:
    Fact         — A single fact with confidence and provenance.
    AgentState   — CRDT state container for a single AI agent.
    SharedKnowledge — Merge N agent states into unified shared knowledge.

Usage:
    from crdt_merge.agentic import AgentState, SharedKnowledge

    researcher = AgentState(agent_id="researcher")
    researcher.add_fact("revenue_q1", 4_200_000, confidence=0.9)
    researcher.add_tag("finance")
    researcher.increment("queries_made")

    analyst = AgentState(agent_id="analyst")
    analyst.add_fact("revenue_q1", 4_250_000, confidence=0.95)

    shared = SharedKnowledge.merge(researcher, analyst)
    print(shared.facts["revenue_q1"].confidence)  # 0.95 — higher confidence wins
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from crdt_merge.core import GCounter, LWWMap, LWWRegister, ORSet, PNCounter

__all__ = ["Fact", "AgentState", "SharedKnowledge"]


# ─── Fact ────────────────────────────────────────────────────────────────────

@dataclass
class Fact:
    """A single fact with confidence and provenance.

    Attributes:
        value:        The fact's payload (any JSON-serialisable value).
        confidence:   Float in [0, 1]. Higher → more trustworthy.
        source_agent: ID of the agent that produced this fact.
        timestamp:    Wall-clock time when the fact was recorded.
    """

    value: Any
    confidence: float = 1.0
    source_agent: str = ""
    timestamp: float = field(default_factory=time.time)

    # -- serialisation --------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise to a plain dict."""
        return {
            "value": self.value,
            "confidence": self.confidence,
            "source_agent": self.source_agent,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Fact:
        """Deserialise from a plain dict."""
        return cls(
            value=d["value"],
            confidence=d.get("confidence", 1.0),
            source_agent=d.get("source_agent", ""),
            timestamp=d.get("timestamp", 0.0),
        )

    def __repr__(self) -> str:
        return (
            f"Fact(value={self.value!r}, confidence={self.confidence}, "
            f"source={self.source_agent!r})"
        )


# ─── AgentState ──────────────────────────────────────────────────────────────

class AgentState:
    """CRDT state container for a single AI agent.

    Wraps :class:`LWWMap`, :class:`ORSet`, and :class:`PNCounter` into a
    purpose-built container for multi-agent systems.

    Sections:
        facts    — LWWMap of ``key → serialised Fact``.
        tags     — ORSet of string labels.
        counters — Dict of ``name → PNCounter``.
        messages — Append-only log (deduped on merge).

    All merge operations are CRDT-compliant: commutative, associative,
    idempotent.

    Usage::

        agent = AgentState(agent_id="researcher")
        agent.add_fact("revenue_q1", 4_200_000, confidence=0.9)
        agent.add_tag("finance")
        agent.increment("queries_made")
    """

    def __init__(self, agent_id: str = "") -> None:
        self.agent_id: str = agent_id
        self._facts: LWWMap = LWWMap()
        self._tags: ORSet = ORSet()
        self._counters: Dict[str, PNCounter] = {}
        self._messages: List[dict] = []
        self._created_at: float = time.time()

    # -- facts ----------------------------------------------------------------

    def add_fact(
        self,
        key: str,
        value: Any,
        confidence: float = 1.0,
        timestamp: Optional[float] = None,
    ) -> None:
        """Add or update a fact.

        The underlying LWWMap uses ``timestamp`` for conflict resolution.
        If two facts share the same timestamp the LWWRegister tie-breaks
        deterministically on ``node_id``.
        """
        ts = timestamp if timestamp is not None else time.time()
        fact = Fact(
            value=value,
            confidence=confidence,
            source_agent=self.agent_id,
            timestamp=ts,
        )
        self._facts.set(key, fact.to_dict(), timestamp=ts, node_id=self.agent_id)

    def get_fact(self, key: str, default: Any = None) -> Optional[Fact]:
        """Return a :class:`Fact` by *key*, or *default* if absent."""
        raw = self._facts.get(key)
        if raw is None:
            return default
        return Fact.from_dict(raw)

    def list_facts(self) -> Dict[str, Fact]:
        """Return all live facts as ``{key: Fact}``."""
        return {k: Fact.from_dict(v) for k, v in self._facts.value.items()}

    # -- tags -----------------------------------------------------------------

    def add_tag(self, tag: str) -> None:
        """Add a string tag (ORSet — add-wins semantics)."""
        self._tags.add(tag)

    def remove_tag(self, tag: str) -> None:
        """Remove a tag (ORSet remove — kills current tags)."""
        self._tags.remove(tag)

    def has_tag(self, tag: str) -> bool:
        """Check if *tag* is present."""
        return self._tags.contains(tag)

    @property
    def tags(self) -> set:
        """Current set of live tags."""
        return self._tags.value

    # -- counters -------------------------------------------------------------

    def increment(self, counter_name: str, amount: int = 1) -> None:
        """Increment a named counter (PNCounter)."""
        if counter_name not in self._counters:
            self._counters[counter_name] = PNCounter()
        self._counters[counter_name].increment(self.agent_id, amount)

    def decrement(self, counter_name: str, amount: int = 1) -> None:
        """Decrement a named counter (PNCounter)."""
        if counter_name not in self._counters:
            self._counters[counter_name] = PNCounter()
        self._counters[counter_name].decrement(self.agent_id, amount)

    def counter_value(self, counter_name: str) -> int:
        """Return the current value of a named counter (0 if missing)."""
        if counter_name not in self._counters:
            return 0
        return self._counters[counter_name].value

    # -- messages -------------------------------------------------------------

    def append_message(
        self,
        message: str,
        role: str = "agent",
        metadata: Optional[dict] = None,
    ) -> None:
        """Append to the message log (append-only, deduped on merge)."""
        self._messages.append(
            {
                "content": message,
                "role": role,
                "agent_id": self.agent_id,
                "timestamp": time.time(),
                "metadata": metadata or {},
            }
        )

    @property
    def messages(self) -> List[dict]:
        """Return a copy of the message log."""
        return list(self._messages)

    # -- merge ----------------------------------------------------------------

    def merge(self, other: AgentState) -> AgentState:
        """Merge two agent states into a **new** :class:`AgentState`.

        Semantics (all CRDT-compliant):
          * **Facts** — LWWMap merge (latest timestamp wins).
          * **Tags**  — ORSet merge (union / add-wins).
          * **Counters** — PNCounter merge per counter name.
          * **Messages** — Union by dedup key, sorted by timestamp.

        Returns a new instance; neither *self* nor *other* is mutated.
        """
        # Merged agent_id is sorted union for determinism → commutativity
        ids = sorted({self.agent_id, other.agent_id})
        result = AgentState(agent_id="+".join(ids))

        # Facts (LWWMap merge)
        result._facts = self._facts.merge(other._facts)

        # Tags (ORSet merge)
        result._tags = self._tags.merge(other._tags)

        # Counters (PNCounter merge per name)
        all_counter_names: Set[str] = set(self._counters) | set(other._counters)
        for name in all_counter_names:
            c1 = self._counters.get(name, PNCounter())
            c2 = other._counters.get(name, PNCounter())
            result._counters[name] = c1.merge(c2)

        # Messages (dedup by content hash, sorted by timestamp)
        seen: Set[str] = set()
        merged_msgs: List[dict] = []
        for msg in self._messages + other._messages:
            dedup_key = (
                f"{msg['content']}:{msg['agent_id']}:{msg.get('timestamp', '')}"
            )
            if dedup_key not in seen:
                seen.add(dedup_key)
                merged_msgs.append(msg)
        merged_msgs.sort(key=lambda m: m.get("timestamp", 0))
        result._messages = merged_msgs

        result._created_at = min(self._created_at, other._created_at)
        return result

    # -- serialisation --------------------------------------------------------

    def to_dict(self) -> dict:
        """Full serialisation to a plain dict."""
        return {
            "type": "agent_state",
            "agent_id": self.agent_id,
            "facts": self._facts.to_dict(),
            "tags": self._tags.to_dict(),
            "counters": {k: v.to_dict() for k, v in self._counters.items()},
            "messages": copy.deepcopy(self._messages),
            "created_at": self._created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AgentState:
        """Deserialise from a plain dict."""
        state = cls(agent_id=d.get("agent_id", ""))
        state._facts = LWWMap.from_dict(d.get("facts", {}))
        state._tags = ORSet.from_dict(d.get("tags", {}))
        state._counters = {
            k: PNCounter.from_dict(v) for k, v in d.get("counters", {}).items()
        }
        state._messages = d.get("messages", [])
        state._created_at = d.get("created_at", 0.0)
        return state

    def __repr__(self) -> str:
        n_facts = len(self._facts.value)
        n_tags = len(self.tags)
        n_ctrs = len(self._counters)
        n_msgs = len(self._messages)
        return (
            f"AgentState(id={self.agent_id!r}, facts={n_facts}, "
            f"tags={n_tags}, counters={n_ctrs}, messages={n_msgs})"
        )


# ─── SharedKnowledge ─────────────────────────────────────────────────────────

class SharedKnowledge:
    """Merge multiple :class:`AgentState` instances into shared knowledge.

    Usage::

        shared = SharedKnowledge.merge(agent_a, agent_b, agent_c)
        print(shared.facts)             # All facts, conflicts resolved
        print(shared.contributing_agents)  # ["analyst", "researcher", "reviewer"]
    """

    def __init__(self, state: AgentState, contributing_agents: List[str]) -> None:
        self.state: AgentState = state
        self.contributing_agents: List[str] = contributing_agents

    # -- class constructor ----------------------------------------------------

    @classmethod
    def merge(cls, *agents: AgentState) -> SharedKnowledge:
        """Merge *N* agent states into a :class:`SharedKnowledge` instance.

        Raises :exc:`ValueError` when called with zero arguments.
        """
        if not agents:
            raise ValueError("At least one agent state required")

        result = agents[0]
        contributing = [agents[0].agent_id]
        for agent in agents[1:]:
            result = result.merge(agent)
            contributing.append(agent.agent_id)
        # Sort for deterministic ordering
        contributing = sorted(set(contributing))
        return cls(state=result, contributing_agents=contributing)

    # -- convenience accessors ------------------------------------------------

    @property
    def facts(self) -> Dict[str, Fact]:
        """All merged facts."""
        return self.state.list_facts()

    @property
    def tags(self) -> set:
        """Union of all tags."""
        return self.state.tags

    @property
    def messages(self) -> List[dict]:
        """Deduplicated, time-sorted message log."""
        return self.state.messages

    def get_fact(self, key: str, default: Any = None) -> Optional[Fact]:
        """Look up a single fact by *key*."""
        return self.state.get_fact(key, default)

    def counter_value(self, counter_name: str) -> int:
        """Return merged counter value."""
        return self.state.counter_value(counter_name)

    # -- serialisation --------------------------------------------------------

    def to_dict(self) -> dict:
        """Full serialisation."""
        return {
            "type": "shared_knowledge",
            "state": self.state.to_dict(),
            "contributing_agents": list(self.contributing_agents),
        }

    @classmethod
    def from_dict(cls, d: dict) -> SharedKnowledge:
        """Deserialise from a plain dict."""
        state = AgentState.from_dict(d.get("state", {}))
        agents = d.get("contributing_agents", [])
        return cls(state=state, contributing_agents=agents)

    def __repr__(self) -> str:
        return (
            f"SharedKnowledge(agents={self.contributing_agents}, "
            f"facts={len(self.facts)}, tags={len(self.tags)})"
        )
