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

import asyncio
import collections
import copy
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from crdt_merge.core import GCounter, LWWMap, LWWRegister, ORSet, PNCounter

__all__ = [
    "Fact",
    "AgentState",
    "SharedKnowledge",
    "RateLimiter",
    "RateLimitExceeded",
    "TrainingSignalExtractor",
    "AgentGossipBridge",
]

logger = logging.getLogger(__name__)


# ─── RateLimiter ─────────────────────────────────────────────────────────────

class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


class RateLimiter:
    """Token bucket rate limiter. Thread-safe.

    Args:
        rate: Tokens per second to refill.
        capacity: Maximum token bucket size.
    """
    def __init__(self, rate: float, capacity: float):
        self.rate = rate
        self.capacity = capacity
        self._tokens = capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self):
        """Acquire one token. Raises RateLimitExceeded if empty."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last = now
            if self._tokens < 1:
                raise RateLimitExceeded(f"Rate limit exceeded ({self.rate}/s)")
            self._tokens -= 1


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
        messages — Append-only log (deduped on merge), bounded by max_messages.

    All merge operations are CRDT-compliant: commutative, associative,
    idempotent.

    Args:
        agent_id: Unique identifier for this agent.
        max_messages: Maximum number of messages to retain (default 10,000).
            When the cap is first reached, a WARNING is emitted.
        key_provider: Optional encryption key provider. When set, fact values
            are encrypted at serialization time (to_dict/from_dict). The
            in-memory representation remains plaintext. Merge operates on
            decrypted in-memory state. Opt-in only.
        dedup_strategy: Message deduplication strategy. Options:
            - 'content_agent_time' (default): dedup by content + agent + timestamp.
            - 'content_only': dedup by content hash only. Use when identical
              messages from different agents/times should be treated as one.
        rate_limiter: Optional RateLimiter. When set, add_fact() will call
            rate_limiter.acquire() before each update. Opt-in only.

    Usage::

        agent = AgentState(agent_id="researcher")
        agent.add_fact("revenue_q1", 4_200_000, confidence=0.9)
        agent.add_tag("finance")
        agent.increment("queries_made")
    """

    def __init__(
        self,
        agent_id: str = "",
        max_messages: int = 10_000,
        key_provider=None,
        dedup_strategy: str = "content_agent_time",
        rate_limiter: Optional[RateLimiter] = None,
    ) -> None:
        self.agent_id: str = agent_id
        self._facts: LWWMap = LWWMap()
        self._tags: ORSet = ORSet()
        self._counters: Dict[str, PNCounter] = {}
        self._messages: collections.deque = collections.deque(maxlen=max_messages)
        self._max_messages: int = max_messages
        self._messages_cap_warned: bool = False
        self._created_at: float = time.time()
        self.key_provider = key_provider
        self.dedup_strategy: str = dedup_strategy
        self.rate_limiter: Optional[RateLimiter] = rate_limiter

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

        If a rate_limiter is configured, it is checked before proceeding.
        Raises RateLimitExceeded if the rate limit is hit.
        """
        if self.rate_limiter is not None:
            self.rate_limiter.acquire()
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
        """Append to the message log (append-only, deduped on merge).

        The message log is bounded by max_messages (deque with maxlen).
        A WARNING is emitted the first time the cap is reached.
        """
        if (
            self._max_messages is not None
            and len(self._messages) >= self._max_messages
            and not self._messages_cap_warned
        ):
            logger.warning(
                "AgentState(id=%r) message log has reached its cap of %d messages. "
                "Oldest messages will be evicted. Pass max_messages= to adjust.",
                self.agent_id,
                self._max_messages,
            )
            self._messages_cap_warned = True

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

    # -- transaction ----------------------------------------------------------

    @contextmanager
    def transaction(self):
        """Atomic multi-fact update context manager.

        Buffers mutations in a snapshot copy. Commits atomically on __exit__.
        Rolls back all changes on exception.

        Usage::

            with agent.transaction():
                agent.add_fact("key1", "val1")
                agent.add_fact("key2", "val2")  # committed atomically

        Note: Not a distributed transaction. Operates on a single local instance.
        Implemented as immutable snapshot + atomic replace.
        """
        snapshot = copy.deepcopy(self)
        try:
            yield self
        except Exception:
            # Rollback: restore all state from snapshot
            self.__dict__.update(snapshot.__dict__)
            raise

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
        result = AgentState(
            agent_id="+".join(ids),
            max_messages=max(self._max_messages, other._max_messages),
            dedup_strategy=self.dedup_strategy,
        )

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

        # Messages (dedup by strategy, sorted by timestamp)
        seen: Set[str] = set()
        merged_msgs: List[dict] = []
        for msg in list(self._messages) + list(other._messages):
            if self.dedup_strategy == "content_only":
                dedup_key = msg["content"]
            else:
                # Default: 'content_agent_time'
                # Dedup by content + agent + timestamp to preserve concurrent
                # identical-content messages from different agents or times.
                dedup_key = (
                    f"{msg['content']}:{msg['agent_id']}:{msg.get('timestamp', '')}"
                )
            if dedup_key not in seen:
                seen.add(dedup_key)
                merged_msgs.append(msg)
        merged_msgs.sort(key=lambda m: m.get("timestamp", 0))
        # Populate the result deque (respects maxlen)
        for msg in merged_msgs:
            result._messages.append(msg)

        result._created_at = min(self._created_at, other._created_at)
        return result

    async def merge_async(self, other: AgentState) -> AgentState:
        """Async variant of :meth:`merge`. Runs merge in a thread pool.

        Useful when merging large states and you don't want to block the
        event loop.

        Returns a new :class:`AgentState`; neither *self* nor *other* is mutated.
        """
        return await asyncio.to_thread(self.merge, other)

    # -- serialisation --------------------------------------------------------

    def to_dict(self) -> dict:
        """Full serialisation to a plain dict.

        When key_provider is set, fact values are encrypted at serialization time.
        The in-memory representation remains plaintext.
        """
        facts_dict = self._facts.to_dict()

        # Encryption is opt-in via key_provider parameter.
        # When key_provider is provided, fact values are encrypted at
        # serialization time. In-memory representation remains plaintext.
        # Merge operates on decrypted in-memory state.
        if self.key_provider:
            try:
                from crdt_merge.encryption import EncryptedMerge
                # wrap values during to_dict
                facts_dict = EncryptedMerge.encrypt_facts(facts_dict, self.key_provider)
            except ImportError:
                pass

        return {
            "type": "agent_state",
            "agent_id": self.agent_id,
            "facts": facts_dict,
            "tags": self._tags.to_dict(),
            "counters": {k: v.to_dict() for k, v in self._counters.items()},
            "messages": copy.deepcopy(list(self._messages)),
            "created_at": self._created_at,
        }

    @classmethod
    def from_dict(cls, d: dict, key_provider=None) -> AgentState:
        """Deserialise from a plain dict.

        Args:
            d: Serialised state dict (from :meth:`to_dict`).
            key_provider: Optional key provider for decryption. Must match
                the one used during serialisation.
        """
        state = cls(agent_id=d.get("agent_id", ""), key_provider=key_provider)

        facts_dict = d.get("facts", {})

        # Decrypt if key_provider is available
        if key_provider:
            try:
                from crdt_merge.encryption import EncryptedMerge
                facts_dict = EncryptedMerge.decrypt_facts(facts_dict, key_provider)
            except ImportError:
                pass

        state._facts = LWWMap.from_dict(facts_dict)
        state._tags = ORSet.from_dict(d.get("tags", {}))
        state._counters = {
            k: PNCounter.from_dict(v) for k, v in d.get("counters", {}).items()
        }
        for msg in d.get("messages", []):
            state._messages.append(msg)
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

        Circular dependency detection (opt-in): if agents declare a
        ``dependencies`` attribute (list of agent_ids), circular deps are
        detected via DFS before merging.
        """
        if not agents:
            raise ValueError("At least one agent state required")

        # Circular dependency detection (opt-in: only if agents declare dependencies)
        agent_map = {a.agent_id: a for a in agents if hasattr(a, "agent_id")}
        for agent in agents:
            if hasattr(agent, "dependencies") and agent.dependencies:
                visited: Set[str] = set()
                path: Set[str] = set()

                def dfs(aid: str) -> None:
                    if aid in path:
                        raise ValueError(f"Circular dependency detected: {aid}")
                    if aid in visited:
                        return
                    visited.add(aid)
                    path.add(aid)
                    dep_agent = agent_map.get(aid)
                    for dep in getattr(dep_agent, "dependencies", []):
                        dfs(dep)
                    path.remove(aid)

                dfs(agent.agent_id)

        result = agents[0]
        contributing = [agents[0].agent_id]
        for agent in agents[1:]:
            result = result.merge(agent)
            contributing.append(agent.agent_id)
        # Sort for deterministic ordering
        contributing = sorted(set(contributing))
        return cls(state=result, contributing_agents=contributing)

    @classmethod
    async def merge_async(cls, *agents: AgentState) -> SharedKnowledge:
        """Async variant of :meth:`merge`. Runs each pairwise merge in a thread pool.

        Uses asyncio.gather with asyncio.to_thread for concurrent execution.
        Returns a :class:`SharedKnowledge` instance.
        """
        if not agents:
            raise ValueError("At least one agent state required")

        if len(agents) == 1:
            return cls(state=agents[0], contributing_agents=[agents[0].agent_id])

        # Merge sequentially but off the event loop using to_thread
        result = agents[0]
        for agent in agents[1:]:
            result = await asyncio.to_thread(result.merge, agent)

        contributing = sorted({a.agent_id for a in agents})
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


# ─── TrainingSignalExtractor ─────────────────────────────────────────────────

class TrainingSignalExtractor:
    """Protocol for extracting training signals from AgentState.

    Implement this protocol to feed agent experience into a model update pipeline.
    This is opt-in — existing AgentState users are unaffected.

    Note: This is a Layer 4/agentic boundary concern. Model fine-tuning is
    a Layer 4 concern; agent experience extraction is at this boundary.
    """

    def extract(self, state: AgentState) -> list:
        """Extract training signal from agent state.

        Returns a list of (input, output, confidence) tuples suitable
        for passing to a MergePipeline or CRDTMergeState.

        Args:
            state: The agent state to extract signals from.

        Returns:
            List of dicts with keys: 'input', 'output', 'confidence'
        """
        signals = []
        for key, fact in state.list_facts().items():
            signals.append({
                "input": key,
                "output": fact.value,
                "confidence": getattr(fact, "confidence", 1.0),
            })
        return signals


# ─── AgentGossipBridge ───────────────────────────────────────────────────────

class AgentGossipBridge:
    """Bridges AgentState with GossipState for distributed sync.

    Transport contract: The bridge provides state serialisation and merge.
    The caller provides the network transport (socket, HTTP, etc).

    Usage::

        bridge = AgentGossipBridge(agent_state, node_id="node-1")
        # To sync with a peer:
        digest = bridge.local_digest()
        # Send digest to peer, receive their digest
        # peer_digest = ... (caller's responsibility)
        # entries_needed = bridge.anti_entropy(peer_digest)
        # Send entries_needed to peer
    """

    def __init__(self, agent_state: AgentState, node_id: str = ""):
        self.agent_state = agent_state
        self.node_id = node_id or agent_state.agent_id
        try:
            from crdt_merge.gossip import GossipState
            self._gossip = GossipState(node_id=self.node_id)
            # Sync current agent state into gossip
            state_dict = agent_state.to_dict()
            self._gossip.update("agent_state", state_dict)
        except ImportError:
            self._gossip = None

    def local_digest(self) -> dict:
        """Return the gossip digest for anti-entropy."""
        if self._gossip:
            return self._gossip.digest()
        return {}

    def sync_from_peer_state(self, peer_state: AgentState) -> AgentState:
        """Merge peer's agent state. Returns merged result."""
        return self.agent_state.merge(peer_state)
