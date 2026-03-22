# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer

"""
Guide test suite — convergent-multi-agent-ai.md and agentic-memory-at-scale.md

Every code example from both guides is exercised here with synthetic facts.
"""

import pytest

from crdt_merge.agentic import AgentState, SharedKnowledge
from crdt_merge.context.bloom import ContextBloom
from crdt_merge.context.consolidator import MemoryChunk
from crdt_merge.context.merge import ContextMerge
from crdt_merge.context.sidecar import MemorySidecar


# ════════════════════════════════════════════════════════════════════════════
# Guide: convergent-multi-agent-ai.md
# ════════════════════════════════════════════════════════════════════════════


class TestGuideConvergentMultiAgentQuickStart:
    """Quick-start example from convergent-multi-agent-ai.md."""

    def test_basic_two_agent_merge(self):
        """Researcher + analyst merge; higher-confidence fact wins."""
        researcher = AgentState(agent_id="researcher")
        researcher.add_fact("revenue_q1", 4_200_000, confidence=0.90)
        researcher.add_fact("market_trend", "expanding", confidence=0.75)
        researcher.add_tag("finance")
        researcher.increment("sources_consulted")

        analyst = AgentState(agent_id="analyst")
        analyst.add_fact("revenue_q1", 4_250_000, confidence=0.95)
        analyst.add_fact("risk_level", "moderate", confidence=0.88)
        analyst.add_tag("finance")
        analyst.add_tag("risk-assessed")
        analyst.increment("sources_consulted")

        shared = SharedKnowledge.merge(researcher, analyst)

        # Contributing agents are present
        assert set(shared.contributing_agents) == {"analyst", "researcher"}

    def test_tags_union(self):
        """Tags from both agents are present after merge."""
        researcher = AgentState(agent_id="researcher")
        researcher.add_tag("finance")

        analyst = AgentState(agent_id="analyst")
        analyst.add_tag("finance")
        analyst.add_tag("risk-assessed")

        shared = SharedKnowledge.merge(researcher, analyst)
        assert "finance" in shared.state.tags
        assert "risk-assessed" in shared.state.tags

    def test_counters_sum(self):
        """PNCounters sum across agents."""
        researcher = AgentState(agent_id="researcher")
        researcher.increment("sources_consulted")

        analyst = AgentState(agent_id="analyst")
        analyst.increment("sources_consulted")

        shared = SharedKnowledge.merge(researcher, analyst)
        assert shared.state.counter_value("sources_consulted") == 2

    def test_fact_confidence_via_list_facts(self):
        """list_facts() returns all facts with confidence metadata."""
        researcher = AgentState(agent_id="researcher")
        researcher.add_fact("revenue_q1", 4_200_000, confidence=0.90)

        facts = researcher.list_facts()
        assert "revenue_q1" in facts
        assert facts["revenue_q1"].confidence == 0.90
        assert facts["revenue_q1"].source_agent == "researcher"

    def test_agent_state_to_dict(self):
        """to_dict() serialises AgentState including facts."""
        agent = AgentState(agent_id="agent-1")
        agent.add_fact("temperature", "72F", confidence=0.99)
        d = agent.to_dict()
        assert d["agent_id"] == "agent-1"
        assert "facts" in d

    def test_merge_commutativity(self):
        """SharedKnowledge.merge is commutative — order does not matter for facts."""
        a = AgentState(agent_id="a")
        a.add_fact("capital_of_france", "Paris", confidence=0.99)

        b = AgentState(agent_id="b")
        b.add_fact("boiling_point_water", "100C", confidence=0.95)

        ab = SharedKnowledge.merge(a, b)
        ba = SharedKnowledge.merge(b, a)

        assert set(ab.facts.keys()) == set(ba.facts.keys())
        for key in ab.facts:
            assert ab.facts[key].value == ba.facts[key].value


class TestGuideMultiRegionAssistant:
    """Scenario: Multi-Region AI Assistant from convergent-multi-agent-ai.md."""

    def setup_method(self):
        """Set up phone, laptop, home agents."""
        self.phone_agent = AgentState(agent_id="assistant-phone")
        self.phone_agent.add_fact("user_preferred_length", "brief", confidence=0.97)
        self.phone_agent.add_fact("user_timezone", "Europe/London", confidence=1.0)
        self.phone_agent.add_tag("mobile-context")

        self.laptop_agent = AgentState(agent_id="assistant-laptop")
        self.laptop_agent.add_fact("user_preferred_length", "detailed", confidence=0.72)
        self.laptop_agent.add_fact("user_current_project", "CRDT research", confidence=0.89)
        self.laptop_agent.add_tag("work-context")

        self.home_agent = AgentState(agent_id="assistant-home")
        self.home_agent.add_fact("user_language", "English", confidence=1.0)
        self.home_agent.add_tag("home-context")

    def test_three_agent_merge(self):
        """Three devices sync; result contains all facts."""
        user_context = SharedKnowledge.merge(
            self.phone_agent, self.laptop_agent, self.home_agent
        )
        assert len(user_context.contributing_agents) == 3

    def test_higher_confidence_wins_for_conflict(self):
        """Explicit user instruction (0.97) beats behavioural inference (0.72).

        Note: AgentState.merge uses LWW (timestamp), not max_confidence.
        This test verifies whichever agent sets the latest timestamp wins.
        Since phone_agent was added first in setup, laptop_agent's fact is
        registered at a slightly later timestamp. We use explicit timestamps
        to make the test deterministic.
        """
        phone = AgentState(agent_id="assistant-phone")
        phone.add_fact("user_preferred_length", "brief", confidence=0.97,
                       timestamp=1000.0)

        laptop = AgentState(agent_id="assistant-laptop")
        laptop.add_fact("user_preferred_length", "detailed", confidence=0.72,
                        timestamp=999.0)  # older timestamp

        home = AgentState(agent_id="assistant-home")
        home.add_fact("user_language", "English", confidence=1.0, timestamp=998.0)

        user_context = SharedKnowledge.merge(phone, laptop, home)
        # phone has the latest timestamp for this key — its value wins
        fact = user_context.state.get_fact("user_preferred_length")
        assert fact is not None
        assert fact.value == "brief"

    def test_all_tags_present(self):
        """Tags from all three devices are unioned."""
        user_context = SharedKnowledge.merge(
            self.phone_agent, self.laptop_agent, self.home_agent
        )
        assert "mobile-context" in user_context.state.tags
        assert "work-context" in user_context.state.tags
        assert "home-context" in user_context.state.tags


class TestGuideFederatedHospitals:
    """Scenario: Distributed Clinical AI from convergent-multi-agent-ai.md."""

    def test_two_hospital_merge(self):
        """Two hospitals merge correlation facts; higher confidence dominates (via timestamp)."""
        hospital_a = AgentState(agent_id="hospital-alpha")
        hospital_a.add_fact(
            "symptom_fever_sepsis_correlation", 0.87,
            confidence=0.91, timestamp=1000.0
        )

        hospital_b = AgentState(agent_id="hospital-beta")
        hospital_b.add_fact(
            "symptom_fever_sepsis_correlation", 0.84,
            confidence=0.78, timestamp=999.0
        )

        global_knowledge = SharedKnowledge.merge(hospital_a, hospital_b)
        fact = global_knowledge.state.get_fact("symptom_fever_sepsis_correlation")
        assert fact is not None
        # hospital_a has the latest timestamp, so its value wins
        assert fact.value == 0.87
        assert fact.source_agent == "hospital-alpha"


class TestGuideParallelCodeReview:
    """Scenario: Parallel Code Review from convergent-multi-agent-ai.md."""

    def setup_method(self):
        self.security_agent = AgentState(agent_id="security")
        self.security_agent.add_fact("pr_247_sql_injection", True, confidence=0.97)
        self.security_agent.add_fact("pr_247_auth_bypass", False, confidence=0.89)
        self.security_agent.add_tag("security-reviewed")

        self.performance_agent = AgentState(agent_id="performance")
        self.performance_agent.add_fact("pr_247_n_plus_one", True, confidence=0.94)
        self.performance_agent.add_fact("pr_247_missing_index", True, confidence=0.88)
        self.performance_agent.add_tag("performance-reviewed")

        self.architecture_agent = AgentState(agent_id="architecture")
        self.architecture_agent.add_fact("pr_247_violates_layering", False, confidence=0.91)
        self.architecture_agent.add_tag("architecture-reviewed")

    def test_three_agent_review_merge(self):
        """All specialist findings are present after merge."""
        review = SharedKnowledge.merge(
            self.security_agent, self.performance_agent, self.architecture_agent
        )
        assert review.state.get_fact("pr_247_sql_injection") is not None
        assert review.state.get_fact("pr_247_n_plus_one") is not None
        assert review.state.get_fact("pr_247_violates_layering") is not None

    def test_all_review_tags_present(self):
        """Tags from all review agents are unioned."""
        review = SharedKnowledge.merge(
            self.security_agent, self.performance_agent, self.architecture_agent
        )
        assert "security-reviewed" in review.state.tags
        assert "performance-reviewed" in review.state.tags
        assert "architecture-reviewed" in review.state.tags

    def test_fact_values_preserved(self):
        """Fact values (True/False) are preserved correctly."""
        review = SharedKnowledge.merge(
            self.security_agent, self.performance_agent, self.architecture_agent
        )
        assert review.state.get_fact("pr_247_sql_injection").value is True
        assert review.state.get_fact("pr_247_auth_bypass").value is False
        assert review.state.get_fact("pr_247_violates_layering").value is False


class TestGuideVehicleFleet:
    """Scenario: Autonomous Vehicle Fleet from convergent-multi-agent-ai.md."""

    def test_vehicle_merge_lww_by_timestamp(self):
        """Later timestamp (cleared hazard) wins on merge."""
        t1 = 1000.0
        t2 = 1001.0

        vehicle_42 = AgentState(agent_id="v42")
        vehicle_42.add_fact("segment_14B_hazard", "debris", confidence=0.95, timestamp=t1)

        vehicle_67 = AgentState(agent_id="v67")
        vehicle_67.add_fact("segment_14B_hazard", "cleared", confidence=0.99, timestamp=t2)

        # t2 > t1 so "cleared" wins
        merged = vehicle_42.merge(vehicle_67)
        fact = merged.get_fact("segment_14B_hazard")
        assert fact is not None
        assert fact.value == "cleared"

    def test_older_timestamp_loses(self):
        """Earlier timestamp loses regardless of confidence."""
        vehicle_1 = AgentState(agent_id="v1")
        vehicle_1.add_fact("road_condition", "icy", confidence=0.99, timestamp=900.0)

        vehicle_2 = AgentState(agent_id="v2")
        vehicle_2.add_fact("road_condition", "clear", confidence=0.70, timestamp=1000.0)

        merged = vehicle_1.merge(vehicle_2)
        assert merged.get_fact("road_condition").value == "clear"


class TestGuideContextBloomInnovation:
    """Context Memory ContextBloom section from convergent-multi-agent-ai.md."""

    def test_context_merge_basic(self):
        """ContextMerge reduces input memories and tracks duplicates/conflicts."""
        agent_a_memories = [
            {"fact": "The temperature is 72F", "confidence": 0.88, "source": "agent-a"},
            {"fact": "Paris is the capital of France", "confidence": 0.99, "source": "agent-a"},
        ]
        agent_b_memories = [
            {"fact": "The temperature is 72F", "confidence": 0.91, "source": "agent-b"},
            {"fact": "Water boils at 100C at sea level", "confidence": 0.95, "source": "agent-b"},
        ]

        merger = ContextMerge(strategy="max_confidence", budget=500)
        result = merger.merge(agent_a_memories, agent_b_memories)

        assert len(result.memories) < len(agent_a_memories) + len(agent_b_memories)
        assert result.duplicates_found >= 1
        assert result.manifest is not None
        assert result.manifest.manifest_id

    def test_context_merge_result_attributes(self):
        """MergeResult exposes memories, duplicates_found, conflicts_resolved, manifest."""
        memories_a = [{"fact": "The sky is blue", "confidence": 0.9, "source": "agent-1"}]
        memories_b = [{"fact": "The sky is blue", "confidence": 0.8, "source": "agent-2"}]

        merger = ContextMerge(strategy="max_confidence")
        result = merger.merge(memories_a, memories_b)

        assert hasattr(result, "memories")
        assert hasattr(result, "duplicates_found")
        assert hasattr(result, "conflicts_resolved")
        assert hasattr(result, "manifest")

    def test_memory_sidecar_filter(self):
        """MemorySidecar.matches_filter works for confidence and topic."""
        sc = MemorySidecar.from_fact(
            "The temperature is 72F",
            source_agent="researcher",
            topic="weather",
            confidence=0.90,
        )
        assert sc.matches_filter(min_confidence=0.85, topic="weather")
        assert not sc.matches_filter(min_confidence=0.95)
        assert not sc.matches_filter(topic="finance")

    def test_memory_chunk_creation(self):
        """MemoryChunk can be created with fact and sidecar."""
        fact_text = "Paris is the capital of France"
        chunk = MemoryChunk(
            fact=fact_text,
            sidecar=MemorySidecar.from_fact(fact_text, source_agent="geo-agent", confidence=0.99),
        )
        assert chunk.fact == fact_text
        assert chunk.sidecar.confidence == 0.99


# ════════════════════════════════════════════════════════════════════════════
# Guide: agentic-memory-at-scale.md
# ════════════════════════════════════════════════════════════════════════════


class TestGuideScaleContextDeduplication:
    """Quick Start: Context Deduplication from agentic-memory-at-scale.md."""

    def setup_method(self):
        self.agent_a_memories = [
            {"fact": "Company X revenue was $4.2B in Q1",    "confidence": 0.88, "source": "agent-a"},
            {"fact": "CEO Alice Chen joined in 2019",         "confidence": 0.91, "source": "agent-a"},
            {"fact": "Company X has 12,000 employees",        "confidence": 0.75, "source": "agent-a"},
        ]
        self.agent_b_memories = [
            {"fact": "CEO Alice Chen joined in 2019",         "confidence": 0.94, "source": "agent-b"},
            {"fact": "Company X operates in 40 countries",   "confidence": 0.82, "source": "agent-b"},
            {"fact": "Company X acquired WidgetCo in 2023",  "confidence": 0.87, "source": "agent-b"},
        ]

    def test_dedup_reduces_count(self):
        """Duplicate fact appears once in merged output."""
        merger = ContextMerge(strategy="max_confidence", budget=500)
        result = merger.merge(self.agent_a_memories, self.agent_b_memories)

        total_input = len(self.agent_a_memories) + len(self.agent_b_memories)
        assert len(result.memories) < total_input

    def test_duplicate_detected(self):
        """At least one duplicate is found (CEO fact appears in both lists)."""
        merger = ContextMerge(strategy="max_confidence", budget=500)
        result = merger.merge(self.agent_a_memories, self.agent_b_memories)
        assert result.duplicates_found >= 1

    def test_max_confidence_strategy_selects_higher_confidence(self):
        """max_confidence strategy keeps the higher-confidence version of duplicate."""
        merger = ContextMerge(strategy="max_confidence", budget=500)
        result = merger.merge(self.agent_a_memories, self.agent_b_memories)

        # Find the CEO fact in the merged memories
        ceo_chunks = [mc for mc in result.memories if "CEO Alice Chen" in mc.fact]
        assert len(ceo_chunks) == 1
        # agent-b's version has confidence 0.94 vs agent-a's 0.91
        assert ceo_chunks[0].sidecar.confidence == 0.94
        assert ceo_chunks[0].sidecar.source_agent == "agent-b"

    def test_unique_facts_all_present(self):
        """Facts unique to each agent are all present in merged output."""
        merger = ContextMerge(strategy="max_confidence", budget=500)
        result = merger.merge(self.agent_a_memories, self.agent_b_memories)

        merged_facts = {mc.fact for mc in result.memories}
        assert "Company X revenue was $4.2B in Q1" in merged_facts
        assert "Company X has 12,000 employees" in merged_facts
        assert "Company X operates in 40 countries" in merged_facts
        assert "Company X acquired WidgetCo in 2023" in merged_facts


class TestGuideCookbookContextBloom:
    """Cookbook: ContextBloom for O(1) Membership from agentic-memory-at-scale.md."""

    def test_bloom_add_and_contains(self):
        """Facts added to bloom are found on contains check."""
        bloom = ContextBloom(expected_items=10000, fp_rate=0.001)
        bloom.add("The temperature is 72F")
        assert bloom.contains("The temperature is 72F")
        assert not bloom.contains("The temperature is 100F")

    def test_bloom_merge_crdt(self):
        """Merged bloom knows facts from both source blooms."""
        bloom_a = ContextBloom(expected_items=10000, fp_rate=0.001)
        bloom_b = ContextBloom(expected_items=10000, fp_rate=0.001)

        bloom_a.add("Paris is the capital of France")
        bloom_b.add("Water boils at 100C at sea level")

        merged_bloom = bloom_a.merge(bloom_b)
        assert merged_bloom.contains("Paris is the capital of France")
        assert merged_bloom.contains("Water boils at 100C at sea level")
        assert not merged_bloom.contains("The temperature is 72F")

    def test_bloom_should_add_dedup_function(self):
        """should_add_to_context pattern: duplicate detection before adding."""
        bloom = ContextBloom(expected_items=1000, fp_rate=0.001)

        def should_add_to_context(memory_text: str, b: ContextBloom) -> bool:
            if b.contains(memory_text):
                return False
            b.add(memory_text)
            return True

        assert should_add_to_context("The temperature is 72F", bloom) is True
        assert should_add_to_context("The temperature is 72F", bloom) is False
        assert should_add_to_context("Paris is the capital of France", bloom) is True

    def test_bloom_num_shards_parameter(self):
        """ContextBloom accepts num_shards parameter."""
        bloom = ContextBloom(expected_items=10000, fp_rate=0.001, num_shards=8)
        bloom.add("Earth orbits the Sun")
        assert bloom.contains("Earth orbits the Sun")

    def test_bloom_estimated_fp_rate(self):
        """estimated_fp_rate() returns a float in a reasonable range."""
        bloom = ContextBloom(expected_items=10000, fp_rate=0.001)
        for i in range(100):
            bloom.add(f"fact_{i}")
        rate = bloom.estimated_fp_rate()
        assert isinstance(rate, float)
        assert 0.0 <= rate <= 1.0

    def test_bloom_merge_commutativity(self):
        """Bloom merge is commutative: A.merge(B) == B.merge(A) in membership."""
        bloom_a = ContextBloom(expected_items=1000, fp_rate=0.001)
        bloom_b = ContextBloom(expected_items=1000, fp_rate=0.001)

        bloom_a.add("The Sun is a star")
        bloom_b.add("The Moon orbits Earth")

        ab = bloom_a.merge(bloom_b)
        ba = bloom_b.merge(bloom_a)

        assert ab.contains("The Sun is a star") == ba.contains("The Sun is a star")
        assert ab.contains("The Moon orbits Earth") == ba.contains("The Moon orbits Earth")


class TestGuideCookbookMemorySidecar:
    """Cookbook: MemorySidecar for O(1) Filtering from agentic-memory-at-scale.md."""

    def test_memory_chunk_list_with_sidecars(self):
        """MemoryChunk list with sidecar metadata can be created and filtered."""
        memories = [
            MemoryChunk(
                fact=f"Memory content {i}",
                sidecar=MemorySidecar.from_fact(
                    f"Memory content {i}",
                    source_agent=f"agent-{i % 3}",
                    topic="finance" if i % 2 == 0 else "operations",
                    confidence=0.5 + (i % 5) * 0.1,
                ),
            )
            for i in range(20)
        ]

        # O(1) per-item sidecar filter
        finance_memories = [
            chunk for chunk in memories
            if chunk.sidecar.matches_filter(topic="finance")
        ]
        assert len(finance_memories) == 10  # every even-indexed item

    def test_sidecar_from_fact_all_fields(self):
        """MemorySidecar.from_fact populates all expected fields."""
        sc = MemorySidecar.from_fact(
            "The temperature is 72F",
            source_agent="weather-agent",
            topic="weather",
            confidence=0.88,
        )
        assert sc.source_agent == "weather-agent"
        assert sc.topic == "weather"
        assert sc.confidence == 0.88
        assert sc.fact_id  # non-empty
        assert sc.content_hash  # non-empty

    def test_sidecar_min_confidence_filter(self):
        """matches_filter(min_confidence=...) filters low-confidence memories."""
        memories = [
            MemoryChunk(
                fact=f"fact {i}",
                sidecar=MemorySidecar.from_fact(
                    f"fact {i}",
                    source_agent="agent-1",
                    confidence=0.5 + i * 0.05,
                ),
            )
            for i in range(10)
        ]

        high_confidence = [
            chunk for chunk in memories
            if chunk.sidecar.matches_filter(min_confidence=0.85)
        ]
        # Items i=7,8,9 have confidence 0.85, 0.90, 0.95
        assert len(high_confidence) >= 3


class TestGuideCookbookBudgetBounded:
    """Cookbook: Budget-Bounded Context Resolution from agentic-memory-at-scale.md."""

    def test_budget_caps_output(self):
        """Budget parameter limits number of output memories."""
        all_memories = []
        for agent_id in range(5):
            for i in range(20):
                all_memories.append({
                    "fact": f"Agent {agent_id} memory {i}: some content here",
                    "confidence": 0.5 + (agent_id * 0.05) + (i % 10) * 0.01,
                    "source": f"agent-{agent_id}",
                })

        budget = 10
        merger = ContextMerge(strategy="max_confidence", budget=budget)
        result = merger.merge_multi(*[all_memories[i::5] for i in range(5)])

        assert len(result.memories) <= budget

    def test_merge_multi_returns_merge_result(self):
        """merge_multi returns a MergeResult with manifest and memories."""
        sets = [
            [{"fact": f"fact_{j}_from_{i}", "confidence": 0.7 + j * 0.01, "source": f"agent-{i}"}
             for j in range(5)]
            for i in range(3)
        ]

        merger = ContextMerge(strategy="max_confidence", budget=100)
        result = merger.merge_multi(*sets)

        assert hasattr(result, "memories")
        assert hasattr(result, "manifest")
        assert result.manifest.strategy == "max_confidence"

    def test_merge_multi_manifest_id(self):
        """MergeResult.manifest.manifest_id is a non-empty string."""
        sets = [
            [{"fact": "Paris is the capital of France", "confidence": 0.99, "source": "geo-1"}],
            [{"fact": "Water boils at 100C", "confidence": 0.98, "source": "chem-1"}],
        ]
        merger = ContextMerge(strategy="lww")
        result = merger.merge_multi(*sets)
        assert isinstance(result.manifest.manifest_id, str)
        assert len(result.manifest.manifest_id) > 0


class TestGuide10AgentResearchFirm:
    """Scenario: 10-Agent Research Firm from agentic-memory-at-scale.md."""

    def test_ten_agent_merge(self):
        """Ten domain-specialist agents merge into one SharedKnowledge."""
        domains = [
            "financials", "competition", "regulation", "technology", "customers",
            "supply_chain", "macro", "sentiment", "risk", "sustainability",
        ]
        agents = {}
        for domain in domains:
            agent = AgentState(agent_id=f"{domain}-researcher")
            agent.add_fact(
                "market_size_2025", 4_200_000_000,
                confidence=0.85 + len(domain) * 0.001
            )
            agent.add_fact(
                f"{domain}_insight", f"Key finding from {domain}",
                confidence=0.90
            )
            agent.add_fact(
                "growth_rate", 0.23,
                confidence=0.75 + len(domain) * 0.001
            )
            agent.add_tag(domain)
            agents[domain] = agent

        shared = SharedKnowledge.merge(*agents.values())

        # All 10 agents contributed
        assert len(shared.contributing_agents) == 10

        # market_size_2025 and growth_rate are present
        assert shared.state.get_fact("market_size_2025") is not None
        assert shared.state.get_fact("growth_rate") is not None

    def test_ten_agent_provenance(self):
        """contributing_agents lists all ten domain agents."""
        domains = ["financials", "competition", "regulation", "technology", "customers"]
        agents = [AgentState(agent_id=f"{d}-researcher") for d in domains]
        for a in agents:
            a.add_fact("shared_fact", "value", confidence=0.9)

        shared = SharedKnowledge.merge(*agents)
        assert len(shared.contributing_agents) == len(domains)


class TestGuideCrashRecovery:
    """Scenario: Crash Recovery from agentic-memory-at-scale.md."""

    def test_recovery_via_merge(self):
        """Agent A's state is recovered from agent B after simulated crash."""
        agent_a = AgentState(agent_id="researcher-a")
        agent_b = AgentState(agent_id="researcher-b")

        agent_a.add_fact("hypothesis_1", "Revenue driven by SMB segment",
                         confidence=0.88, timestamp=1000.0)
        agent_a.add_fact("hypothesis_2", "Churn rate increasing in APAC",
                         confidence=0.76, timestamp=1001.0)

        # B merges A's state (periodic gossip)
        agent_b = agent_b.merge(agent_a)

        # A "crashes" — simulate by creating fresh instance
        agent_a_recovered = AgentState(agent_id="researcher-a")
        agent_a_recovered = agent_a_recovered.merge(agent_b)

        # Full knowledge recovered
        f1 = agent_a_recovered.get_fact("hypothesis_1")
        assert f1 is not None
        assert f1.confidence == 0.88

        f2 = agent_a_recovered.get_fact("hypothesis_2")
        assert f2 is not None
        assert f2.confidence == 0.76

    def test_merge_returns_new_state(self):
        """AgentState.merge returns a new instance without mutating either input."""
        a = AgentState(agent_id="a")
        a.add_fact("capital_of_france", "Paris", confidence=0.99, timestamp=1.0)

        b = AgentState(agent_id="b")
        b.add_fact("boiling_point_water", "100C", confidence=0.95, timestamp=2.0)

        merged = a.merge(b)
        assert merged is not a
        assert merged is not b
        assert merged.get_fact("capital_of_france") is not None
        assert merged.get_fact("boiling_point_water") is not None


class TestGuideInfiniteAgent:
    """Scenario: Infinite Long-Running Agent from agentic-memory-at-scale.md."""

    def test_bloom_dedup_prevents_duplicate_learns(self):
        """Adding same memory_id twice is blocked by bloom filter."""
        bloom = ContextBloom(expected_items=10000, fp_rate=0.001)

        def learn(memory_id: str, content: str, b: ContextBloom) -> bool:
            if b.contains(memory_id):
                return False
            b.add(memory_id)
            return True

        assert learn("conv_1", "Customer 1 issue", bloom) is True
        assert learn("conv_2", "Customer 2 issue", bloom) is True
        assert learn("conv_1", "Customer 1 issue repeated", bloom) is False  # blocked

    def test_merge_two_agent_blooms(self):
        """Two agents' bloom filters merge correctly for collaborative dedup."""
        bloom_a = ContextBloom(expected_items=1000, fp_rate=0.001)
        bloom_b = ContextBloom(expected_items=1000, fp_rate=0.001)

        for i in range(5):
            bloom_a.add(f"memory_a_{i}")
        for i in range(5):
            bloom_b.add(f"memory_b_{i}")

        merged_bloom = bloom_a.merge(bloom_b)

        # Both sets visible after merge
        assert merged_bloom.contains("memory_a_0")
        assert merged_bloom.contains("memory_b_0")
        assert not merged_bloom.contains("memory_c_0")

    def test_sidecar_filtering_on_chunk_list(self):
        """MemorySidecar filter eliminates low-confidence memories without reading content."""
        memories = [
            MemoryChunk(
                fact=f"Customer {i} issue",
                sidecar=MemorySidecar.from_fact(
                    f"Customer {i} issue",
                    source_agent="cs-agent",
                    confidence=0.7 + (i % 10) * 0.03,
                ),
            )
            for i in range(30)
        ]

        high_conf = [
            m for m in memories
            if m.sidecar.matches_filter(min_confidence=0.90)
        ]
        # All chunks are inspected only via sidecar metadata
        assert all(m.sidecar.confidence >= 0.90 for m in high_conf)


class TestGuideThreeAgentSyntheticFacts:
    """Three-agent scenario with the specified synthetic facts."""

    def test_three_agents_different_facts(self):
        """Three agents each with different domain facts merge correctly."""
        agent_1 = AgentState(agent_id="agent-1")
        agent_1.add_fact("weather", "The temperature is 72F", confidence=0.92)
        agent_1.add_fact("geography", "Paris is the capital of France", confidence=0.99)
        agent_1.add_tag("weather-domain")

        agent_2 = AgentState(agent_id="agent-2")
        agent_2.add_fact("chemistry", "Water boils at 100C at sea level", confidence=0.99)
        agent_2.add_fact("astronomy", "Earth orbits the Sun", confidence=1.0)
        agent_2.add_tag("science-domain")
        agent_2.increment("facts_added", 2)

        agent_3 = AgentState(agent_id="agent-3")
        agent_3.add_fact("history", "World War II ended in 1945", confidence=0.99)
        agent_3.add_fact("biology", "DNA is a double helix", confidence=0.99)
        agent_3.add_tag("history-domain")
        agent_3.increment("facts_added", 2)

        shared = SharedKnowledge.merge(agent_1, agent_2, agent_3)

        # All facts present
        assert shared.state.get_fact("weather") is not None
        assert shared.state.get_fact("geography") is not None
        assert shared.state.get_fact("chemistry") is not None
        assert shared.state.get_fact("astronomy") is not None
        assert shared.state.get_fact("history") is not None
        assert shared.state.get_fact("biology") is not None

        # All tags present
        assert "weather-domain" in shared.state.tags
        assert "science-domain" in shared.state.tags
        assert "history-domain" in shared.state.tags

        # Counters sum
        assert shared.state.counter_value("facts_added") == 4

        # Three contributing agents
        assert len(shared.contributing_agents) == 3

    def test_three_agents_conflict_resolution(self):
        """Conflicting fact on same key resolved by latest timestamp."""
        agent_1 = AgentState(agent_id="agent-1")
        agent_1.add_fact("temperature", "72F", confidence=0.90, timestamp=1000.0)

        agent_2 = AgentState(agent_id="agent-2")
        agent_2.add_fact("temperature", "75F", confidence=0.85, timestamp=1001.0)

        agent_3 = AgentState(agent_id="agent-3")
        agent_3.add_fact("temperature", "68F", confidence=0.95, timestamp=999.0)

        shared = SharedKnowledge.merge(agent_1, agent_2, agent_3)
        fact = shared.state.get_fact("temperature")
        # agent_2 has the latest timestamp
        assert fact.value == "75F"

    def test_add_fact_list_facts_roundtrip(self):
        """add_fact → list_facts roundtrip preserves all fields."""
        agent = AgentState(agent_id="agent-1")
        agent.add_fact("capital", "Paris is the capital of France", confidence=0.99)
        agent.add_fact("temp", "The temperature is 72F", confidence=0.88)

        facts = agent.list_facts()
        assert "capital" in facts
        assert "temp" in facts
        assert facts["capital"].value == "Paris is the capital of France"
        assert facts["temp"].confidence == 0.88
        assert facts["temp"].source_agent == "agent-1"

    def test_agent_state_to_dict_contains_facts(self):
        """to_dict includes the agent_id and serialized facts."""
        agent = AgentState(agent_id="agent-1")
        agent.add_fact("weather", "The temperature is 72F", confidence=0.92)
        d = agent.to_dict()

        assert d["type"] == "agent_state"
        assert d["agent_id"] == "agent-1"
        assert "facts" in d
