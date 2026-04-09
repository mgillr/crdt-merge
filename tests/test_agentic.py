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
Comprehensive tests for the Agentic AI State Merge module.

Coverage:
    - Fact: creation, serialisation roundtrip
    - AgentState: facts, tags, counters, messages, merge, serialisation
    - SharedKnowledge: 2/3/5-agent merges, accessors, serialisation
    - CRDT laws: commutativity, associativity, idempotency via verify_crdt
    - Edge cases: empty state, duplicate messages, zero confidence, scale
"""

import random
import time

import pytest

from crdt_merge.agentic import AgentState, Fact, SharedKnowledge
from crdt_merge.verify import verify_crdt


# ═══════════════════════════════════════════════════════════════════════════════
# Fact
# ═══════════════════════════════════════════════════════════════════════════════


class TestFact:
    """Tests for the Fact dataclass."""

    def test_fact_creation_defaults(self):
        """Fact with defaults has confidence=1.0 and non-zero timestamp."""
        f = Fact(value="hello")
        assert f.value == "hello"
        assert f.confidence == 1.0
        assert f.source_agent == ""
        assert f.timestamp > 0

    def test_fact_creation_full(self):
        """Fact with all fields explicitly set."""
        f = Fact(value=42, confidence=0.8, source_agent="bot", timestamp=100.0)
        assert f.value == 42
        assert f.confidence == 0.8
        assert f.source_agent == "bot"
        assert f.timestamp == 100.0

    def test_fact_to_dict(self):
        """to_dict produces the expected keys."""
        f = Fact(value="x", confidence=0.5, source_agent="a", timestamp=1.0)
        d = f.to_dict()
        assert d == {
            "value": "x",
            "confidence": 0.5,
            "source_agent": "a",
            "timestamp": 1.0,
        }

    def test_fact_roundtrip(self):
        """to_dict → from_dict preserves all fields."""
        original = Fact(value=[1, 2, 3], confidence=0.75, source_agent="r", timestamp=99.9)
        restored = Fact.from_dict(original.to_dict())
        assert restored.value == original.value
        assert restored.confidence == original.confidence
        assert restored.source_agent == original.source_agent
        assert restored.timestamp == original.timestamp

    def test_fact_from_dict_defaults(self):
        """from_dict applies defaults for missing optional fields."""
        f = Fact.from_dict({"value": "hi"})
        assert f.value == "hi"
        assert f.confidence == 1.0
        assert f.source_agent == ""

    def test_fact_repr(self):
        """repr is human-readable."""
        f = Fact(value="test", confidence=0.9, source_agent="bot")
        r = repr(f)
        assert "test" in r
        assert "0.9" in r


# ═══════════════════════════════════════════════════════════════════════════════
# AgentState -- basic operations
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentStateBasic:
    """Core operations: facts, tags, counters, messages."""

    def test_add_and_get_fact(self):
        a = AgentState("researcher")
        a.add_fact("revenue", 100, confidence=0.9, timestamp=1.0)
        f = a.get_fact("revenue")
        assert f is not None
        assert f.value == 100
        assert f.confidence == 0.9
        assert f.source_agent == "researcher"

    def test_get_fact_missing(self):
        a = AgentState("x")
        assert a.get_fact("nope") is None
        assert a.get_fact("nope", "default") == "default"

    def test_list_facts(self):
        a = AgentState("a")
        a.add_fact("k1", "v1", timestamp=1.0)
        a.add_fact("k2", "v2", timestamp=2.0)
        facts = a.list_facts()
        assert set(facts.keys()) == {"k1", "k2"}
        assert facts["k1"].value == "v1"

    def test_fact_overwrite(self):
        """Later timestamp overwrites earlier fact for same key."""
        a = AgentState("a")
        a.add_fact("x", "old", timestamp=1.0)
        a.add_fact("x", "new", timestamp=2.0)
        assert a.get_fact("x").value == "new"

    def test_add_tag(self):
        a = AgentState("a")
        a.add_tag("finance")
        a.add_tag("ai")
        assert a.has_tag("finance")
        assert a.has_tag("ai")
        assert not a.has_tag("other")

    def test_tags_property(self):
        a = AgentState("a")
        a.add_tag("x")
        a.add_tag("y")
        assert a.tags == {"x", "y"}

    def test_remove_tag(self):
        a = AgentState("a")
        a.add_tag("temp")
        assert a.has_tag("temp")
        a.remove_tag("temp")
        assert not a.has_tag("temp")

    def test_increment_counter(self):
        a = AgentState("a")
        a.increment("queries", 5)
        assert a.counter_value("queries") == 5

    def test_decrement_counter(self):
        a = AgentState("a")
        a.increment("stock", 10)
        a.decrement("stock", 3)
        assert a.counter_value("stock") == 7

    def test_counter_missing(self):
        a = AgentState("a")
        assert a.counter_value("nonexistent") == 0

    def test_append_message(self):
        a = AgentState("a")
        a.append_message("hello", role="user")
        msgs = a.messages
        assert len(msgs) == 1
        assert msgs[0]["content"] == "hello"
        assert msgs[0]["role"] == "user"
        assert msgs[0]["agent_id"] == "a"

    def test_messages_copy(self):
        """messages property returns a copy, not a reference."""
        a = AgentState("a")
        a.append_message("msg1")
        msgs = a.messages
        msgs.append({"fake": True})
        assert len(a.messages) == 1  # original unaffected

    def test_repr(self):
        a = AgentState("bot")
        a.add_fact("f", 1, timestamp=1.0)
        a.add_tag("t")
        r = repr(a)
        assert "bot" in r
        assert "facts=1" in r


# ═══════════════════════════════════════════════════════════════════════════════
# AgentState -- merge
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentStateMerge:
    """Merge semantics: facts, tags, counters, messages."""

    def test_merge_facts_lww(self):
        """Later timestamp wins on same key."""
        a = AgentState("a")
        a.add_fact("price", 100, timestamp=1.0)
        b = AgentState("b")
        b.add_fact("price", 200, timestamp=2.0)
        merged = a.merge(b)
        assert merged.get_fact("price").value == 200

    def test_merge_facts_disjoint(self):
        """Different keys are both preserved."""
        a = AgentState("a")
        a.add_fact("k1", "v1", timestamp=1.0)
        b = AgentState("b")
        b.add_fact("k2", "v2", timestamp=1.0)
        merged = a.merge(b)
        facts = merged.list_facts()
        assert "k1" in facts
        assert "k2" in facts

    def test_merge_tags_union(self):
        """Tags are unioned (ORSet merge)."""
        a = AgentState("a")
        a.add_tag("finance")
        b = AgentState("b")
        b.add_tag("tech")
        merged = a.merge(b)
        assert merged.tags >= {"finance", "tech"}

    def test_merge_counters(self):
        """PNCounters merge correctly across agents."""
        a = AgentState("a")
        a.increment("api_calls", 10)
        b = AgentState("b")
        b.increment("api_calls", 5)
        merged = a.merge(b)
        assert merged.counter_value("api_calls") == 15

    def test_merge_counters_disjoint(self):
        """Different counter names both preserved."""
        a = AgentState("a")
        a.increment("reads", 3)
        b = AgentState("b")
        b.increment("writes", 7)
        merged = a.merge(b)
        assert merged.counter_value("reads") == 3
        assert merged.counter_value("writes") == 7

    def test_merge_messages_dedup(self):
        """Identical messages (same content+agent+timestamp) are deduped."""
        a = AgentState("a")
        b = AgentState("a")
        ts = 1000.0
        # Manually add same message to both
        msg = {"content": "hello", "role": "agent", "agent_id": "a",
               "timestamp": ts, "metadata": {}}
        a._messages.append(msg)
        b._messages.append(dict(msg))  # copy
        merged = a.merge(b)
        assert len(merged.messages) == 1

    def test_merge_messages_different(self):
        """Different messages from different agents are both kept."""
        a = AgentState("a")
        a.append_message("msg_a")
        b = AgentState("b")
        b.append_message("msg_b")
        merged = a.merge(b)
        contents = [m["content"] for m in merged.messages]
        assert "msg_a" in contents
        assert "msg_b" in contents

    def test_merge_messages_sorted_by_timestamp(self):
        """Merged messages are sorted by timestamp."""
        a = AgentState("a")
        a._messages.append({"content": "late", "agent_id": "a", "timestamp": 20.0})
        b = AgentState("b")
        b._messages.append({"content": "early", "agent_id": "b", "timestamp": 10.0})
        merged = a.merge(b)
        assert merged.messages[0]["content"] == "early"
        assert merged.messages[1]["content"] == "late"

    def test_merge_returns_new_instance(self):
        """merge() returns a new AgentState; originals are not mutated."""
        a = AgentState("a")
        a.add_fact("k", 1, timestamp=1.0)
        b = AgentState("b")
        b.add_fact("k", 2, timestamp=2.0)
        merged = a.merge(b)
        assert merged is not a
        assert merged is not b
        # Original a still has its own fact value
        assert a.get_fact("k").value == 1

    def test_merge_created_at_min(self):
        """Merged _created_at is the earlier of the two."""
        a = AgentState("a")
        a._created_at = 100.0
        b = AgentState("b")
        b._created_at = 50.0
        merged = a.merge(b)
        assert merged._created_at == 50.0


# ═══════════════════════════════════════════════════════════════════════════════
# CRDT Laws
# ═══════════════════════════════════════════════════════════════════════════════


def _make_random_agent_state() -> AgentState:
    """Generate a random AgentState for property-based testing."""
    agent_id = random.choice(["alpha", "beta", "gamma", "delta"])
    state = AgentState(agent_id=agent_id)
    state._created_at = random.uniform(1.0, 1000.0)

    # Random facts with fixed timestamps for determinism
    for i in range(random.randint(0, 5)):
        ts = random.uniform(1.0, 1000.0)
        state.add_fact(
            f"fact_{random.randint(0, 10)}",
            random.choice(["a", "b", "c", 1, 2, 3]),
            confidence=random.random(),
            timestamp=ts,
        )

    # Random tags
    for _ in range(random.randint(0, 3)):
        state.add_tag(random.choice(["t1", "t2", "t3", "t4"]))

    # Random counters
    for _ in range(random.randint(0, 3)):
        name = random.choice(["c1", "c2", "c3"])
        state.increment(name, random.randint(1, 10))

    # Random messages with fixed timestamps
    for _ in range(random.randint(0, 2)):
        ts = random.uniform(1.0, 1000.0)
        msg = {
            "content": random.choice(["m1", "m2", "m3"]),
            "role": "agent",
            "agent_id": agent_id,
            "timestamp": ts,
            "metadata": {},
        }
        state._messages.append(msg)

    return state


def _agent_state_eq(a: AgentState, b: AgentState) -> bool:
    """Semantic equality for AgentState: compare facts, tags, counters, messages."""
    # Facts
    if a._facts.value != b._facts.value:
        return False
    # Tags
    if a.tags != b.tags:
        return False
    # Counters
    a_ctr_names = set(a._counters)
    b_ctr_names = set(b._counters)
    if a_ctr_names != b_ctr_names:
        return False
    for name in a_ctr_names:
        if a._counters[name].value != b._counters[name].value:
            return False
    # Messages (compare dedup keys as sets for order-independence after sort)
    def _msg_keys(msgs):
        return set(
            f"{m['content']}:{m['agent_id']}:{m.get('timestamp', '')}"
            for m in msgs
        )
    if _msg_keys(a._messages) != _msg_keys(b._messages):
        return False
    return True


class TestCRDTLaws:
    """Verify AgentState.merge satisfies all CRDT laws."""

    def test_commutativity_manual(self):
        """merge(A, B) semantically equals merge(B, A)."""
        a = AgentState("a")
        a.add_fact("k", 1, timestamp=1.0)
        a.add_tag("t1")
        a.increment("c1", 5)
        b = AgentState("b")
        b.add_fact("k", 2, timestamp=2.0)
        b.add_tag("t2")
        b.increment("c1", 3)
        ab = a.merge(b)
        ba = b.merge(a)
        assert _agent_state_eq(ab, ba)

    def test_associativity_manual(self):
        """merge(merge(A, B), C) == merge(A, merge(B, C))."""
        a = AgentState("a")
        a.add_fact("x", 1, timestamp=1.0)
        b = AgentState("b")
        b.add_fact("y", 2, timestamp=2.0)
        c = AgentState("c")
        c.add_fact("z", 3, timestamp=3.0)
        ab_c = a.merge(b).merge(c)
        a_bc = a.merge(b.merge(c))
        assert _agent_state_eq(ab_c, a_bc)

    def test_idempotency_manual(self):
        """merge(A, A) == A."""
        a = AgentState("a")
        a.add_fact("k", 1, timestamp=1.0)
        a.add_tag("t")
        a.increment("c", 3)
        a.append_message("msg")
        aa = a.merge(a)
        assert _agent_state_eq(aa, a)

    def test_verify_crdt_full(self):
        """Run verify_crdt with random generator — all properties pass."""
        result = verify_crdt(
            merge_fn=lambda a, b: a.merge(b),
            gen_fn=_make_random_agent_state,
            trials=200,
            eq_fn=_agent_state_eq,
            include_convergence=True,
        )
        assert result.commutativity.passed, (
            f"Commutativity failed: {result.commutativity.first_failure}"
        )
        assert result.associativity.passed, (
            f"Associativity failed: {result.associativity.first_failure}"
        )
        assert result.idempotency.passed, (
            f"Idempotency failed: {result.idempotency.first_failure}"
        )
        assert result.passed


# ═══════════════════════════════════════════════════════════════════════════════
# AgentState -- serialisation
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentStateSerialization:
    """to_dict / from_dict roundtrip."""

    def test_roundtrip_empty(self):
        a = AgentState("empty")
        restored = AgentState.from_dict(a.to_dict())
        assert restored.agent_id == "empty"
        assert restored.list_facts() == {}
        assert restored.tags == set()

    def test_roundtrip_full(self):
        a = AgentState("full")
        a.add_fact("revenue", 42, confidence=0.8, timestamp=10.0)
        a.add_fact("profit", 7, confidence=0.6, timestamp=11.0)
        a.add_tag("finance")
        a.add_tag("q1")
        a.increment("queries", 5)
        a.decrement("queries", 2)
        a.increment("errors", 1)
        a._messages.append(
            {"content": "done", "role": "agent", "agent_id": "full",
             "timestamp": 12.0, "metadata": {"step": 3}}
        )
        d = a.to_dict()
        restored = AgentState.from_dict(d)
        assert restored.agent_id == "full"
        assert restored.get_fact("revenue").value == 42
        assert restored.get_fact("profit").confidence == 0.6
        assert restored.tags == {"finance", "q1"}
        assert restored.counter_value("queries") == 3
        assert restored.counter_value("errors") == 1
        assert len(restored.messages) == 1
        assert restored.messages[0]["content"] == "done"

    def test_roundtrip_after_merge(self):
        a = AgentState("a")
        a.add_fact("k", 1, timestamp=1.0)
        b = AgentState("b")
        b.add_fact("k", 2, timestamp=2.0)
        merged = a.merge(b)
        d = merged.to_dict()
        restored = AgentState.from_dict(d)
        assert restored.get_fact("k").value == 2
        assert _agent_state_eq(merged, restored)


# ═══════════════════════════════════════════════════════════════════════════════
# SharedKnowledge
# ═══════════════════════════════════════════════════════════════════════════════


class TestSharedKnowledge:
    """SharedKnowledge.merge and accessors."""

    def test_merge_empty_raises(self):
        with pytest.raises(ValueError, match="At least one"):
            SharedKnowledge.merge()

    def test_merge_single_agent(self):
        a = AgentState("solo")
        a.add_fact("x", 1, timestamp=1.0)
        sk = SharedKnowledge.merge(a)
        assert sk.facts["x"].value == 1
        assert "solo" in sk.contributing_agents

    def test_merge_two_agents(self):
        a = AgentState("researcher")
        a.add_fact("revenue", 100, confidence=0.7, timestamp=1.0)
        a.add_tag("finance")
        b = AgentState("analyst")
        b.add_fact("revenue", 110, confidence=0.95, timestamp=2.0)
        b.add_tag("verified")
        sk = SharedKnowledge.merge(a, b)
        assert sk.facts["revenue"].value == 110  # later timestamp
        assert sk.tags >= {"finance", "verified"}
        assert set(sk.contributing_agents) == {"researcher", "analyst"}

    def test_merge_three_agents(self):
        agents = []
        for name in ["a", "b", "c"]:
            s = AgentState(name)
            s.add_fact(f"fact_{name}", name, timestamp=float(ord(name)))
            s.add_tag(f"tag_{name}")
            agents.append(s)
        sk = SharedKnowledge.merge(*agents)
        assert len(sk.facts) == 3
        assert sk.tags >= {"tag_a", "tag_b", "tag_c"}
        assert set(sk.contributing_agents) == {"a", "b", "c"}

    def test_merge_five_agents(self):
        agents = []
        for i in range(5):
            s = AgentState(f"agent_{i}")
            s.add_fact("shared_key", i, confidence=i * 0.2, timestamp=float(i))
            s.increment("total_ops", i + 1)
            agents.append(s)
        sk = SharedKnowledge.merge(*agents)
        # Last timestamp (4.0) wins
        assert sk.facts["shared_key"].value == 4
        # Counters: sum of (1+2+3+4+5) = 15
        assert sk.counter_value("total_ops") == 15
        assert len(sk.contributing_agents) == 5

    def test_get_fact(self):
        a = AgentState("a")
        a.add_fact("k", "val", timestamp=1.0)
        sk = SharedKnowledge.merge(a)
        assert sk.get_fact("k").value == "val"
        assert sk.get_fact("missing") is None

    def test_messages(self):
        a = AgentState("a")
        a.append_message("hi")
        sk = SharedKnowledge.merge(a)
        assert len(sk.messages) == 1

    def test_counter_value(self):
        a = AgentState("a")
        a.increment("c", 10)
        sk = SharedKnowledge.merge(a)
        assert sk.counter_value("c") == 10
        assert sk.counter_value("missing") == 0

    def test_repr(self):
        a = AgentState("a")
        a.add_fact("f", 1, timestamp=1.0)
        sk = SharedKnowledge.merge(a)
        r = repr(sk)
        assert "SharedKnowledge" in r


# ═══════════════════════════════════════════════════════════════════════════════
# SharedKnowledge -- serialisation
# ═══════════════════════════════════════════════════════════════════════════════


class TestSharedKnowledgeSerialization:
    """to_dict / from_dict roundtrip for SharedKnowledge."""

    def test_roundtrip(self):
        a = AgentState("a")
        a.add_fact("k1", 10, timestamp=1.0)
        a.add_tag("t1")
        b = AgentState("b")
        b.add_fact("k2", 20, timestamp=2.0)
        sk = SharedKnowledge.merge(a, b)
        d = sk.to_dict()
        restored = SharedKnowledge.from_dict(d)
        assert set(restored.contributing_agents) == set(sk.contributing_agents)
        assert restored.facts["k1"].value == 10
        assert restored.facts["k2"].value == 20
        assert restored.tags >= {"t1"}

    def test_roundtrip_type_field(self):
        a = AgentState("x")
        sk = SharedKnowledge.merge(a)
        d = sk.to_dict()
        assert d["type"] == "shared_knowledge"


# ═══════════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases: empty states, duplicates, zero confidence, scale."""

    def test_empty_state_merge(self):
        a = AgentState("a")
        b = AgentState("b")
        merged = a.merge(b)
        assert merged.list_facts() == {}
        assert merged.tags == set()
        assert merged.messages == []

    def test_merge_with_empty(self):
        """Non-empty merged with empty preserves all data."""
        a = AgentState("a")
        a.add_fact("k", 1, timestamp=1.0)
        a.add_tag("t")
        a.increment("c", 5)
        b = AgentState("b")
        merged = a.merge(b)
        assert merged.get_fact("k").value == 1
        assert merged.has_tag("t")
        assert merged.counter_value("c") == 5

    def test_zero_confidence_fact(self):
        """Zero-confidence facts are valid and stored."""
        a = AgentState("a")
        a.add_fact("uncertain", "maybe", confidence=0.0, timestamp=1.0)
        f = a.get_fact("uncertain")
        assert f is not None
        assert f.confidence == 0.0
        assert f.value == "maybe"

    def test_duplicate_messages_same_agent(self):
        """Duplicate messages from the same agent are deduped on merge."""
        a = AgentState("a")
        msg = {"content": "dup", "role": "agent", "agent_id": "a",
               "timestamp": 1.0, "metadata": {}}
        a._messages.append(msg)
        b = AgentState("a")
        b._messages.append(dict(msg))
        merged = a.merge(b)
        assert len(merged.messages) == 1

    def test_many_tags_merge(self):
        a = AgentState("a")
        b = AgentState("b")
        for i in range(50):
            a.add_tag(f"tag_{i}")
            b.add_tag(f"tag_{i + 50}")
        merged = a.merge(b)
        assert len(merged.tags) == 100

    def test_counter_decrement_only(self):
        """Decrementing without incrementing yields negative value."""
        a = AgentState("a")
        a.decrement("debt", 5)
        assert a.counter_value("debt") == -5

    def test_fact_with_complex_value(self):
        """Facts can hold complex nested values."""
        a = AgentState("a")
        val = {"nested": [1, 2, {"deep": True}]}
        a.add_fact("complex", val, timestamp=1.0)
        f = a.get_fact("complex")
        assert f.value == val

    def test_merge_self_idempotent(self):
        """Merging an agent with itself produces equivalent state."""
        a = AgentState("a")
        a.add_fact("k", 1, confidence=0.5, timestamp=1.0)
        a.add_tag("t")
        a.increment("c", 3)
        a._messages.append(
            {"content": "hi", "role": "agent", "agent_id": "a",
             "timestamp": 1.0, "metadata": {}}
        )
        merged = a.merge(a)
        assert _agent_state_eq(merged, a)


# ═══════════════════════════════════════════════════════════════════════════════
# Scale
# ═══════════════════════════════════════════════════════════════════════════════


class TestScale:
    """Scale tests: many facts, many agents."""

    def test_1000_facts_across_10_agents(self):
        """1000+ facts across 10 agents merge correctly."""
        agents = []
        for i in range(10):
            s = AgentState(f"agent_{i}")
            for j in range(100):
                s.add_fact(
                    f"fact_{j}",
                    f"val_{i}_{j}",
                    confidence=random.random(),
                    timestamp=float(i * 100 + j),
                )
            agents.append(s)
        sk = SharedKnowledge.merge(*agents)
        # 100 unique fact keys; the latest timestamp (agent_9) wins each
        assert len(sk.facts) == 100
        for j in range(100):
            f = sk.get_fact(f"fact_{j}")
            assert f is not None
            assert f.value == f"val_9_{j}"  # agent_9 has highest ts

    def test_large_counter_merge(self):
        """Counters across many agents sum correctly."""
        agents = []
        for i in range(20):
            s = AgentState(f"a{i}")
            s.increment("ops", 10)
            agents.append(s)
        sk = SharedKnowledge.merge(*agents)
        assert sk.counter_value("ops") == 200

    def test_many_messages_dedup(self):
        """Duplicate messages across agents are properly deduped."""
        a = AgentState("a")
        b = AgentState("a")  # same agent_id
        for i in range(50):
            msg = {"content": f"msg_{i}", "role": "agent", "agent_id": "a",
                   "timestamp": float(i), "metadata": {}}
            a._messages.append(msg)
            b._messages.append(dict(msg))
        merged = a.merge(b)
        assert len(merged.messages) == 50
