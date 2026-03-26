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
Comprehensive tests for the Context Memory System (crdt_merge.context).

Covers:
  - MemorySidecar: creation, from_fact, filtering, expiry, merge (CRDT laws), serialization
  - ContextManifest: creation, summary, merge, serialization
  - ContextBloom: add/contains, false positives, merge (CRDT laws), sharding, serialization
  - ContextConsolidator: consolidation, querying, block merging
  - ContextMerge: basic merge, dedup, strategy selection, budget, multi-agent, manifest
  - CRDT Law Verification via verify_crdt
  - Scale test: 10K+ memories
  - Integration: merge → serialize → deserialize → merge again
"""

import hashlib
import random
import time

import pytest

from crdt_merge.context import (
    ConsolidatedBlock,
    ContextBloom,
    ContextConsolidator,
    ContextManifest,
    ContextMerge,
    MemoryChunk,
    MemorySidecar,
    MergeResult,
)
from crdt_merge.verify import verify_crdt


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  MemorySidecar Tests                                                     ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestMemorySidecar:
    """Tests for MemorySidecar."""

    def test_from_fact_basic(self):
        sc = MemorySidecar.from_fact("The sky is blue")
        assert sc.fact_id
        assert len(sc.fact_id) == 16
        assert len(sc.content_hash) == 64
        assert sc.confidence == 1.0
        assert sc.topic == ""
        assert sc.source_agent == ""

    def test_from_fact_with_kwargs(self):
        sc = MemorySidecar.from_fact(
            "The sky is blue",
            source_agent="agent-1",
            topic="science",
            confidence=0.95,
            tags=["weather", "fact"],
        )
        assert sc.source_agent == "agent-1"
        assert sc.topic == "science"
        assert sc.confidence == 0.95
        assert sc.tags == ["fact", "weather"]  # sorted at creation for CRDT idempotency

    def test_from_fact_deterministic_hash(self):
        sc1 = MemorySidecar.from_fact("hello")
        sc2 = MemorySidecar.from_fact("hello")
        assert sc1.fact_id == sc2.fact_id
        assert sc1.content_hash == sc2.content_hash

    def test_from_fact_different_content(self):
        sc1 = MemorySidecar.from_fact("hello")
        sc2 = MemorySidecar.from_fact("world")
        assert sc1.fact_id != sc2.fact_id

    def test_content_hash_is_sha256(self):
        fact = "test content"
        expected = hashlib.sha256(fact.encode("utf-8")).hexdigest()
        sc = MemorySidecar.from_fact(fact)
        assert sc.content_hash == expected

    def test_fact_id_is_hash_prefix(self):
        sc = MemorySidecar.from_fact("test")
        assert sc.fact_id == sc.content_hash[:16]

    # ── Filtering ──────────────────────────────────────────────────────────

    def test_matches_filter_no_criteria(self):
        sc = MemorySidecar.from_fact("fact")
        assert sc.matches_filter() is True

    def test_matches_filter_topic(self):
        sc = MemorySidecar.from_fact("fact", topic="science")
        assert sc.matches_filter(topic="science") is True
        assert sc.matches_filter(topic="history") is False

    def test_matches_filter_confidence(self):
        sc = MemorySidecar.from_fact("fact", confidence=0.8)
        assert sc.matches_filter(min_confidence=0.5) is True
        assert sc.matches_filter(min_confidence=0.9) is False

    def test_matches_filter_source_agent(self):
        sc = MemorySidecar.from_fact("fact", source_agent="agent-1")
        assert sc.matches_filter(source_agent="agent-1") is True
        assert sc.matches_filter(source_agent="agent-2") is False

    def test_matches_filter_tags(self):
        sc = MemorySidecar.from_fact("fact", tags=["a", "b", "c"])
        assert sc.matches_filter(tags=["a", "b"]) is True
        assert sc.matches_filter(tags=["a", "d"]) is False

    def test_matches_filter_combined(self):
        sc = MemorySidecar.from_fact(
            "fact", topic="sci", confidence=0.9, source_agent="ag1", tags=["x"]
        )
        assert sc.matches_filter(topic="sci", min_confidence=0.8, source_agent="ag1", tags=["x"])
        assert not sc.matches_filter(topic="sci", min_confidence=0.95)

    # ── Expiry ─────────────────────────────────────────────────────────────

    def test_no_expiry_by_default(self):
        sc = MemorySidecar.from_fact("fact")
        assert sc.is_expired() is False

    def test_not_expired_within_ttl(self):
        sc = MemorySidecar.from_fact("fact", ttl=3600.0)
        sc.timestamp = time.time()
        assert sc.is_expired() is False

    def test_expired_after_ttl(self):
        sc = MemorySidecar.from_fact("fact", ttl=10.0)
        sc.timestamp = time.time() - 20.0
        assert sc.is_expired() is True

    def test_expiry_custom_now(self):
        sc = MemorySidecar.from_fact("fact", ttl=10.0)
        sc.timestamp = 100.0
        assert sc.is_expired(now=105.0) is False
        assert sc.is_expired(now=115.0) is True

    def test_none_ttl_never_expires(self):
        sc = MemorySidecar.from_fact("fact")
        sc.timestamp = 0.0  # very old
        assert sc.is_expired() is False

    # ── Serialisation ──────────────────────────────────────────────────────

    def test_to_dict_from_dict_roundtrip(self):
        sc = MemorySidecar.from_fact(
            "fact",
            source_agent="ag1",
            topic="t",
            confidence=0.7,
            tags=["x", "y"],
            metadata={"k": "v"},
            ttl=60.0,
        )
        d = sc.to_dict()
        sc2 = MemorySidecar.from_dict(d)
        assert sc == sc2

    def test_to_dict_fields(self):
        sc = MemorySidecar.from_fact("hello")
        d = sc.to_dict()
        assert "fact_id" in d
        assert "content_hash" in d
        assert "topic" in d
        assert "tags" in d
        assert "metadata" in d

    def test_from_dict_missing_optional_fields(self):
        d = {"fact_id": "abc", "content_hash": "def"}
        sc = MemorySidecar.from_dict(d)
        assert sc.topic == ""
        assert sc.confidence == 1.0
        assert sc.tags == []
        assert sc.metadata == {}

    # ── Merge ──────────────────────────────────────────────────────────────

    def test_merge_confidence_max_wins(self):
        sc1 = MemorySidecar.from_fact("fact", confidence=0.7)
        sc2 = MemorySidecar.from_fact("fact", confidence=0.9)
        merged = sc1.merge(sc2)
        assert merged.confidence == 0.9

    def test_merge_timestamp_max_wins(self):
        sc1 = MemorySidecar.from_fact("fact")
        sc1.timestamp = 100.0
        sc2 = MemorySidecar.from_fact("fact")
        sc2.timestamp = 200.0
        merged = sc1.merge(sc2)
        assert merged.timestamp == 200.0

    def test_merge_access_count_max_wins(self):
        sc1 = MemorySidecar.from_fact("fact")
        sc1.access_count = 5
        sc2 = MemorySidecar.from_fact("fact")
        sc2.access_count = 10
        merged = sc1.merge(sc2)
        assert merged.access_count == 10

    def test_merge_tags_union(self):
        sc1 = MemorySidecar.from_fact("fact", tags=["a", "b"])
        sc2 = MemorySidecar.from_fact("fact", tags=["b", "c"])
        merged = sc1.merge(sc2)
        assert merged.tags == ["a", "b", "c"]

    def test_merge_ttl_none_dominates(self):
        sc1 = MemorySidecar.from_fact("fact", ttl=60.0)
        sc2 = MemorySidecar.from_fact("fact")  # ttl=None
        merged = sc1.merge(sc2)
        assert merged.ttl is None

    def test_merge_ttl_both_finite(self):
        sc1 = MemorySidecar.from_fact("fact", ttl=60.0)
        sc2 = MemorySidecar.from_fact("fact", ttl=120.0)
        merged = sc1.merge(sc2)
        assert merged.ttl == 120.0

    def test_merge_metadata_union(self):
        sc1 = MemorySidecar.from_fact("fact", metadata={"a": 1})
        sc2 = MemorySidecar.from_fact("fact", metadata={"b": 2})
        merged = sc1.merge(sc2)
        assert "a" in merged.metadata
        assert "b" in merged.metadata

    def test_merge_returns_new_instance(self):
        sc1 = MemorySidecar.from_fact("fact", confidence=0.5)
        sc2 = MemorySidecar.from_fact("fact", confidence=0.9)
        merged = sc1.merge(sc2)
        assert merged is not sc1
        assert merged is not sc2
        assert sc1.confidence == 0.5  # unchanged

    def test_merge_topic_nonempty(self):
        sc1 = MemorySidecar.from_fact("fact", topic="")
        sc2 = MemorySidecar.from_fact("fact", topic="science")
        merged = sc1.merge(sc2)
        assert merged.topic == "science"

    def test_merge_topic_both_nonempty(self):
        sc1 = MemorySidecar.from_fact("fact", topic="alpha")
        sc2 = MemorySidecar.from_fact("fact", topic="beta")
        merged = sc1.merge(sc2)
        assert merged.topic == "beta"  # max("alpha", "beta")


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  ContextManifest Tests                                                   ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestContextManifest:
    """Tests for ContextManifest."""

    def _make(self, **overrides):
        defaults = dict(
            manifest_id="m1",
            created_at=1000.0,
            source_agents=["agent-a"],
            total_memories=100,
            unique_memories=80,
            duplicates_removed=20,
            conflicts_resolved=5,
            strategy_used="lww",
            quality_score=0.9,
            provenance_chain=[],
        )
        defaults.update(overrides)
        return ContextManifest(**defaults)

    def test_creation(self):
        m = self._make()
        assert m.manifest_id == "m1"
        assert m.total_memories == 100

    def test_summary(self):
        m = self._make()
        s = m.summary()
        assert "m1" in s
        assert "100" in s
        assert "80 unique" in s
        assert "lww" in s

    def test_to_dict_from_dict_roundtrip(self):
        m = self._make(
            provenance_chain=[{"op": "merge", "timestamp": 100.0}]
        )
        d = m.to_dict()
        m2 = ContextManifest.from_dict(d)
        assert m == m2

    def test_to_dict_fields(self):
        m = self._make()
        d = m.to_dict()
        assert "manifest_id" in d
        assert "source_agents" in d
        assert "provenance_chain" in d

    def test_merge_source_agents_union(self):
        m1 = self._make(source_agents=["a", "b"])
        m2 = self._make(source_agents=["b", "c"])
        merged = m1.merge(m2)
        assert merged.source_agents == ["a", "b", "c"]

    def test_merge_counts_max(self):
        m1 = self._make(total_memories=50, unique_memories=40)
        m2 = self._make(total_memories=100, unique_memories=80)
        merged = m1.merge(m2)
        assert merged.total_memories == 100
        assert merged.unique_memories == 80

    def test_merge_quality_max(self):
        m1 = self._make(quality_score=0.7)
        m2 = self._make(quality_score=0.9)
        merged = m1.merge(m2)
        assert merged.quality_score == 0.9

    def test_merge_created_at_max(self):
        m1 = self._make(created_at=100.0)
        m2 = self._make(created_at=200.0)
        merged = m1.merge(m2)
        assert merged.created_at == 200.0

    def test_merge_provenance_union(self):
        m1 = self._make(provenance_chain=[{"op": "a", "timestamp": 1.0}])
        m2 = self._make(provenance_chain=[{"op": "b", "timestamp": 2.0}])
        merged = m1.merge(m2)
        assert len(merged.provenance_chain) == 2

    def test_merge_provenance_dedup(self):
        entry = {"op": "merge", "timestamp": 1.0}
        m1 = self._make(provenance_chain=[entry])
        m2 = self._make(provenance_chain=[entry])
        merged = m1.merge(m2)
        assert len(merged.provenance_chain) == 1

    def test_merge_returns_new_instance(self):
        m1 = self._make()
        m2 = self._make()
        merged = m1.merge(m2)
        assert merged is not m1
        assert merged is not m2

    def test_merge_strategy_deterministic(self):
        m1 = self._make(strategy_used="lww")
        m2 = self._make(strategy_used="union")
        merged = m1.merge(m2)
        assert merged.strategy_used == "union"  # max("lww", "union")


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  ContextBloom Tests                                                      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestContextBloom:
    """Tests for ContextBloom."""

    def test_add_and_contains(self):
        cb = ContextBloom(expected_items=1000, fp_rate=0.001, num_shards=4)
        assert cb.contains("hello") is False
        was_dup = cb.add("hello")
        assert was_dup is False
        assert cb.contains("hello") is True

    def test_add_returns_true_for_duplicate(self):
        cb = ContextBloom(expected_items=1000, fp_rate=0.001, num_shards=4)
        cb.add("hello")
        was_dup = cb.add("hello")
        assert was_dup is True

    def test_does_not_contain_absent(self):
        cb = ContextBloom(expected_items=1000, fp_rate=0.001, num_shards=4)
        cb.add("hello")
        assert cb.contains("world") is False

    def test_many_items(self):
        cb = ContextBloom(expected_items=10000, fp_rate=0.01, num_shards=8)
        items = [f"item-{i}" for i in range(1000)]
        for item in items:
            cb.add(item)
        for item in items:
            assert cb.contains(item) is True

    def test_false_positive_rate_bounded(self):
        cb = ContextBloom(expected_items=10000, fp_rate=0.01, num_shards=8)
        for i in range(1000):
            cb.add(f"present-{i}")
        fp_count = sum(
            1 for i in range(10000)
            if cb.contains(f"absent-{i}")
        )
        # Allow generous FP rate bound (5%) since we're testing with few items
        assert fp_count / 10000 < 0.05

    def test_sharding_distributes(self):
        cb = ContextBloom(expected_items=10000, fp_rate=0.01, num_shards=8)
        for i in range(1000):
            cb.add(f"item-{i}")
        # Check that items are distributed across shards
        non_empty = sum(1 for s in cb._shards if s._count > 0)
        assert non_empty > 1

    def test_estimated_items(self):
        cb = ContextBloom(expected_items=10000, fp_rate=0.01, num_shards=8)
        assert cb.estimated_items == 0
        for i in range(100):
            cb.add(f"item-{i}")
        assert cb.estimated_items == 100

    def test_to_dict_from_dict_roundtrip(self):
        cb = ContextBloom(expected_items=1000, fp_rate=0.01, num_shards=4)
        for i in range(50):
            cb.add(f"item-{i}")
        d = cb.to_dict()
        cb2 = ContextBloom.from_dict(d)
        assert cb == cb2
        for i in range(50):
            assert cb2.contains(f"item-{i}")

    def test_to_dict_fields(self):
        cb = ContextBloom(expected_items=1000, num_shards=4)
        d = cb.to_dict()
        assert d["type"] == "context_bloom"
        assert d["num_shards"] == 4
        assert len(d["shards"]) == 4

    def test_merge_basic(self):
        cb1 = ContextBloom(expected_items=1000, fp_rate=0.01, num_shards=4)
        cb2 = ContextBloom(expected_items=1000, fp_rate=0.01, num_shards=4)
        cb1.add("alpha")
        cb2.add("beta")
        merged = cb1.merge(cb2)
        assert merged.contains("alpha")
        assert merged.contains("beta")

    def test_merge_different_shards_error(self):
        cb1 = ContextBloom(num_shards=4)
        cb2 = ContextBloom(num_shards=8)
        with pytest.raises(ValueError, match="shard count"):
            cb1.merge(cb2)

    def test_merge_preserves_items(self):
        cb1 = ContextBloom(expected_items=1000, fp_rate=0.01, num_shards=4)
        cb2 = ContextBloom(expected_items=1000, fp_rate=0.01, num_shards=4)
        for i in range(50):
            cb1.add(f"a-{i}")
        for i in range(50):
            cb2.add(f"b-{i}")
        merged = cb1.merge(cb2)
        for i in range(50):
            assert merged.contains(f"a-{i}")
            assert merged.contains(f"b-{i}")

    def test_merge_returns_new_instance(self):
        cb1 = ContextBloom(num_shards=4)
        cb2 = ContextBloom(num_shards=4)
        merged = cb1.merge(cb2)
        assert merged is not cb1
        assert merged is not cb2

    def test_empty_bloom_operations(self):
        cb = ContextBloom(expected_items=100, num_shards=4)
        assert cb.estimated_items == 0
        assert cb.contains("anything") is False


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  ContextConsolidator Tests                                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestContextConsolidator:
    """Tests for ContextConsolidator."""

    def _make_chunks(self, n: int, topic: str = "", source: str = "") -> list:
        return [
            MemoryChunk(
                fact=f"fact-{i}",
                sidecar=MemorySidecar.from_fact(
                    f"fact-{i}", topic=topic, source_agent=source
                ),
            )
            for i in range(n)
        ]

    def test_consolidate_empty(self):
        c = ContextConsolidator(block_size=10)
        blocks = c.consolidate([])
        assert blocks == []

    def test_consolidate_single_block(self):
        c = ContextConsolidator(block_size=100)
        chunks = self._make_chunks(50)
        blocks = c.consolidate(chunks)
        assert len(blocks) == 1
        assert blocks[0].size == 50

    def test_consolidate_multiple_blocks(self):
        c = ContextConsolidator(block_size=10)
        chunks = self._make_chunks(25)
        blocks = c.consolidate(chunks)
        assert len(blocks) == 3  # 10, 10, 5
        assert blocks[0].size == 10
        assert blocks[1].size == 10
        assert blocks[2].size == 5

    def test_consolidate_exact_block_size(self):
        c = ContextConsolidator(block_size=10)
        chunks = self._make_chunks(20)
        blocks = c.consolidate(chunks)
        assert len(blocks) == 2
        assert all(b.size == 10 for b in blocks)

    def test_sidecar_index_populated(self):
        c = ContextConsolidator(block_size=100)
        chunks = self._make_chunks(5)
        blocks = c.consolidate(chunks)
        block = blocks[0]
        assert len(block.sidecar_index) == 5
        for mc in chunks:
            assert mc.sidecar.fact_id in block.sidecar_index

    def test_block_has_id(self):
        c = ContextConsolidator(block_size=100)
        chunks = self._make_chunks(5)
        blocks = c.consolidate(chunks)
        assert blocks[0].block_id
        assert len(blocks[0].block_id) == 16

    # ── Querying ───────────────────────────────────────────────────────────

    def test_query_no_filter(self):
        c = ContextConsolidator(block_size=100)
        chunks = self._make_chunks(10)
        blocks = c.consolidate(chunks)
        results = c.query(blocks)
        assert len(results) == 10

    def test_query_by_topic(self):
        c = ContextConsolidator(block_size=100)
        chunks_sci = self._make_chunks(5, topic="science")
        chunks_hist = self._make_chunks(5, topic="history")
        blocks = c.consolidate(chunks_sci + chunks_hist)
        results = c.query(blocks, topic="science")
        assert len(results) == 5
        assert all(mc.sidecar.topic == "science" for mc in results)

    def test_query_by_source_agent(self):
        c = ContextConsolidator(block_size=100)
        chunks_a = self._make_chunks(3, source="agent-1")
        chunks_b = self._make_chunks(3, source="agent-2")
        blocks = c.consolidate(chunks_a + chunks_b)
        results = c.query(blocks, source_agent="agent-1")
        assert len(results) == 3

    def test_query_by_confidence(self):
        c = ContextConsolidator(block_size=100)
        chunks = []
        for i in range(10):
            sc = MemorySidecar.from_fact(f"fact-{i}", confidence=i / 10.0)
            chunks.append(MemoryChunk(fact=f"fact-{i}", sidecar=sc))
        blocks = c.consolidate(chunks)
        results = c.query(blocks, min_confidence=0.5)
        assert len(results) == 5  # 0.5, 0.6, 0.7, 0.8, 0.9

    def test_query_across_multiple_blocks(self):
        c = ContextConsolidator(block_size=5)
        chunks = self._make_chunks(15, topic="t1")
        blocks = c.consolidate(chunks)
        assert len(blocks) == 3
        results = c.query(blocks, topic="t1")
        assert len(results) == 15

    # ── Block merging ──────────────────────────────────────────────────────

    def test_merge_blocks_basic(self):
        c = ContextConsolidator(block_size=100)
        # Use distinct fact prefixes so the two sets don't overlap
        chunks_a = [
            MemoryChunk(
                fact=f"alpha-{i}",
                sidecar=MemorySidecar.from_fact(f"alpha-{i}", topic="t1"),
            )
            for i in range(5)
        ]
        chunks_b = [
            MemoryChunk(
                fact=f"beta-{i}",
                sidecar=MemorySidecar.from_fact(f"beta-{i}", topic="t2"),
            )
            for i in range(5)
        ]
        blocks_a = c.consolidate(chunks_a)
        blocks_b = c.consolidate(chunks_b)
        merged = c.merge_blocks(blocks_a, blocks_b)
        total = sum(b.size for b in merged)
        assert total == 10

    def test_merge_blocks_dedup_by_fact_id(self):
        c = ContextConsolidator(block_size=100)
        # Same chunks in both sets
        chunks = self._make_chunks(5)
        blocks_a = c.consolidate(chunks)
        blocks_b = c.consolidate(chunks)
        merged = c.merge_blocks(blocks_a, blocks_b)
        total = sum(b.size for b in merged)
        assert total == 5  # deduped

    def test_merge_blocks_with_bloom(self):
        c = ContextConsolidator(block_size=100)
        bloom = ContextBloom(expected_items=1000, num_shards=4)
        chunks_a = self._make_chunks(5)
        chunks_b = self._make_chunks(5)
        blocks_a = c.consolidate(chunks_a)
        blocks_b = c.consolidate(chunks_b)
        merged = c.merge_blocks(blocks_a, blocks_b, bloom=bloom)
        total = sum(b.size for b in merged)
        assert total == 5  # deduped via bloom

    def test_merge_empty_blocks(self):
        c = ContextConsolidator(block_size=100)
        merged = c.merge_blocks([], [])
        assert merged == []

    # ── ConsolidatedBlock serialization ────────────────────────────────────

    def test_consolidated_block_roundtrip(self):
        c = ContextConsolidator(block_size=100)
        chunks = self._make_chunks(5)
        blocks = c.consolidate(chunks)
        d = blocks[0].to_dict()
        restored = ConsolidatedBlock.from_dict(d)
        assert restored.block_id == blocks[0].block_id
        assert len(restored.memories) == 5

    def test_memory_chunk_roundtrip(self):
        mc = MemoryChunk(
            fact="hello world",
            sidecar=MemorySidecar.from_fact("hello world", topic="test"),
        )
        d = mc.to_dict()
        mc2 = MemoryChunk.from_dict(d)
        assert mc == mc2


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  ContextMerge Tests                                                      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestContextMerge:
    """Tests for ContextMerge."""

    def test_basic_merge(self):
        cm = ContextMerge(strategy="union")
        result = cm.merge(
            [{"fact": "sky is blue"}],
            [{"fact": "grass is green"}],
        )
        assert len(result.memories) == 2
        facts = {mc.fact for mc in result.memories}
        assert "sky is blue" in facts
        assert "grass is green" in facts

    def test_dedup_exact_duplicates(self):
        cm = ContextMerge(strategy="union")
        result = cm.merge(
            [{"fact": "sky is blue"}],
            [{"fact": "sky is blue"}],
        )
        assert len(result.memories) == 1
        assert result.duplicates_found == 1

    def test_dedup_with_different_metadata(self):
        cm = ContextMerge(strategy="union")
        result = cm.merge(
            [{"fact": "sky is blue", "confidence": 0.7}],
            [{"fact": "sky is blue", "confidence": 0.9}],
        )
        assert len(result.memories) == 1
        # Should have merged sidecars → max confidence
        assert result.memories[0].sidecar.confidence == 0.9

    def test_strategy_lww(self):
        cm = ContextMerge(strategy="lww")
        result = cm.merge(
            [{"fact": "temp is 20C", "ts": 100.0, "source": "sensor-a"}],
            [{"fact": "temp is 22C", "ts": 200.0, "source": "sensor-b"}],
        )
        # These have different fact_ids so both should be kept
        assert len(result.memories) == 2

    def test_strategy_max_confidence(self):
        cm = ContextMerge(strategy="max_confidence")
        result = cm.merge(
            [{"fact": "A", "confidence": 0.5}],
            [{"fact": "B", "confidence": 0.9}],
        )
        assert len(result.memories) == 2

    def test_strategy_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            ContextMerge(strategy="invalid")

    def test_budget_limiting(self):
        cm = ContextMerge(strategy="union", budget=3)
        mems = [{"fact": f"fact-{i}", "confidence": i / 10.0} for i in range(10)]
        result = cm.merge(mems[:5], mems[5:])
        assert len(result.memories) == 3
        # Should keep highest confidence
        confs = [mc.sidecar.confidence for mc in result.memories]
        assert min(confs) >= 0.7  # top 3: 0.9, 0.8, 0.7

    def test_min_confidence_filter(self):
        cm = ContextMerge(strategy="union", min_confidence=0.5)
        result = cm.merge(
            [{"fact": "low", "confidence": 0.1}],
            [{"fact": "high", "confidence": 0.9}],
        )
        assert len(result.memories) == 1
        assert result.memories[0].fact == "high"

    def test_manifest_generated(self):
        cm = ContextMerge(strategy="lww")
        result = cm.merge(
            [{"fact": "a", "source": "agent-1"}],
            [{"fact": "b", "source": "agent-2"}],
        )
        assert result.manifest is not None
        assert result.manifest.manifest_id
        assert result.manifest.total_memories == 2
        assert "agent-1" in result.manifest.source_agents
        assert "agent-2" in result.manifest.source_agents
        assert result.manifest.strategy_used == "lww"

    def test_manifest_quality_score(self):
        cm = ContextMerge(strategy="union")
        result = cm.merge(
            [{"fact": "a", "confidence": 0.8}],
            [{"fact": "b", "confidence": 1.0}],
        )
        assert result.manifest.quality_score == pytest.approx(0.9, abs=0.01)

    def test_bloom_carried_forward(self):
        cm = ContextMerge(strategy="union")
        result = cm.merge(
            [{"fact": "alpha"}],
            [{"fact": "beta"}],
        )
        assert result.bloom.contains("alpha")
        assert result.bloom.contains("beta")

    def test_merge_empty_inputs(self):
        cm = ContextMerge(strategy="union")
        result = cm.merge([], [])
        assert len(result.memories) == 0
        assert result.duplicates_found == 0

    def test_merge_one_empty(self):
        cm = ContextMerge(strategy="union")
        result = cm.merge([{"fact": "a"}], [])
        assert len(result.memories) == 1

    def test_merge_with_tags(self):
        cm = ContextMerge(strategy="union")
        result = cm.merge(
            [{"fact": "a", "tags": ["x", "y"]}],
            [{"fact": "b", "tags": ["y", "z"]}],
        )
        facts = {mc.fact: mc for mc in result.memories}
        assert "x" in facts["a"].sidecar.tags

    def test_merge_with_topics(self):
        cm = ContextMerge(strategy="union")
        result = cm.merge(
            [{"fact": "a", "topic": "science"}],
            [{"fact": "b", "topic": "history"}],
        )
        topics = {mc.sidecar.topic for mc in result.memories}
        assert topics == {"science", "history"}

    # ── Multi merge ────────────────────────────────────────────────────────

    def test_merge_multi_basic(self):
        cm = ContextMerge(strategy="union")
        result = cm.merge_multi(
            [{"fact": "a"}],
            [{"fact": "b"}],
            [{"fact": "c"}],
        )
        assert len(result.memories) == 3

    def test_merge_multi_dedup(self):
        cm = ContextMerge(strategy="union")
        result = cm.merge_multi(
            [{"fact": "shared"}],
            [{"fact": "shared"}],
            [{"fact": "shared"}],
        )
        assert len(result.memories) == 1

    def test_merge_multi_min_args(self):
        cm = ContextMerge(strategy="union")
        with pytest.raises(ValueError, match="at least 2"):
            cm.merge_multi([{"fact": "a"}])

    def test_merge_multi_four_agents(self):
        cm = ContextMerge(strategy="union")
        result = cm.merge_multi(
            [{"fact": f"a-{i}"} for i in range(5)],
            [{"fact": f"b-{i}"} for i in range(5)],
            [{"fact": f"c-{i}"} for i in range(5)],
            [{"fact": f"d-{i}"} for i in range(5)],
        )
        assert len(result.memories) == 20

    # ── Priority strategy ──────────────────────────────────────────────────

    def test_strategy_priority(self):
        cm = ContextMerge(
            strategy="priority",
            agent_priority={"trusted": 10, "untrusted": 1},
        )
        result = cm.merge(
            [{"fact": "a", "source": "trusted"}],
            [{"fact": "b", "source": "untrusted"}],
        )
        assert len(result.memories) == 2

    # ── Result structure ───────────────────────────────────────────────────

    def test_merge_result_type(self):
        cm = ContextMerge(strategy="union")
        result = cm.merge([{"fact": "a"}], [{"fact": "b"}])
        assert isinstance(result, MergeResult)
        assert isinstance(result.manifest, ContextManifest)
        assert isinstance(result.bloom, ContextBloom)
        assert isinstance(result.memories, list)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CRDT Law Verification Tests                                            ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestCRDTLaws:
    """Verify CRDT laws for all mergeable types using verify_crdt."""

    def test_memory_sidecar_crdt_laws(self):
        """MemorySidecar.merge must be commutative, associative, idempotent."""

        def gen():
            topics = ["science", "history", "math", ""]
            agents = ["agent-1", "agent-2", "agent-3", ""]
            tag_pool = ["a", "b", "c", "d", "e"]
            fact = f"fact-{random.randint(0, 5)}"
            return MemorySidecar.from_fact(
                fact,
                source_agent=random.choice(agents),
                topic=random.choice(topics),
                confidence=random.random(),
                tags=random.sample(tag_pool, k=random.randint(0, 3)),
                ttl=random.choice([None, 60.0, 120.0]),
                metadata={"k": random.choice(["v1", "v2"])},
            )

        result = verify_crdt(
            merge_fn=lambda a, b: a.merge(b),
            gen_fn=gen,
            trials=200,
        )
        assert result.passed, result.summary()

    def test_context_bloom_crdt_laws(self):
        """ContextBloom.merge must be commutative, associative, idempotent."""

        def gen():
            cb = ContextBloom(expected_items=100, fp_rate=0.01, num_shards=4)
            for _ in range(random.randint(0, 10)):
                cb.add(f"item-{random.randint(0, 20)}")
            return cb

        result = verify_crdt(
            merge_fn=lambda a, b: a.merge(b),
            gen_fn=gen,
            trials=100,
        )
        assert result.passed, result.summary()

    def test_context_manifest_crdt_laws(self):
        """ContextManifest.merge must be commutative, associative, idempotent."""

        def gen():
            agents_pool = ["a1", "a2", "a3"]
            strats = ["lww", "max_confidence", "union"]
            return ContextManifest(
                manifest_id=f"m-{random.randint(0, 5)}",
                created_at=random.uniform(100, 200),
                source_agents=random.sample(agents_pool, k=random.randint(1, 3)),
                total_memories=random.randint(10, 100),
                unique_memories=random.randint(5, 50),
                duplicates_removed=random.randint(0, 20),
                conflicts_resolved=random.randint(0, 10),
                strategy_used=random.choice(strats),
                quality_score=random.random(),
                provenance_chain=[
                    {"op": random.choice(["merge", "dedup"]),
                     "timestamp": random.uniform(0, 100)}
                    for _ in range(random.randint(0, 2))
                ],
            )

        result = verify_crdt(
            merge_fn=lambda a, b: a.merge(b),
            gen_fn=gen,
            trials=200,
        )
        assert result.passed, result.summary()

    def test_sidecar_commutativity(self):
        sc1 = MemorySidecar.from_fact("test", confidence=0.7, tags=["a"])
        sc2 = MemorySidecar.from_fact("test", confidence=0.9, tags=["b"])
        assert sc1.merge(sc2) == sc2.merge(sc1)

    def test_sidecar_associativity(self):
        sc1 = MemorySidecar.from_fact("t", confidence=0.5, tags=["a"])
        sc2 = MemorySidecar.from_fact("t", confidence=0.7, tags=["b"])
        sc3 = MemorySidecar.from_fact("t", confidence=0.9, tags=["c"])
        assert sc1.merge(sc2).merge(sc3) == sc1.merge(sc2.merge(sc3))

    def test_sidecar_idempotency(self):
        sc = MemorySidecar.from_fact("test", confidence=0.8, tags=["x", "y"])
        assert sc.merge(sc) == sc

    def test_bloom_commutativity(self):
        cb1 = ContextBloom(expected_items=100, num_shards=4)
        cb2 = ContextBloom(expected_items=100, num_shards=4)
        cb1.add("alpha")
        cb2.add("beta")
        assert cb1.merge(cb2) == cb2.merge(cb1)

    def test_bloom_associativity(self):
        cb1 = ContextBloom(expected_items=100, num_shards=4)
        cb2 = ContextBloom(expected_items=100, num_shards=4)
        cb3 = ContextBloom(expected_items=100, num_shards=4)
        cb1.add("a")
        cb2.add("b")
        cb3.add("c")
        assert cb1.merge(cb2).merge(cb3) == cb1.merge(cb2.merge(cb3))

    def test_bloom_idempotency(self):
        cb = ContextBloom(expected_items=100, num_shards=4)
        cb.add("x")
        cb.add("y")
        assert cb.merge(cb) == cb

    def test_manifest_commutativity(self):
        m1 = ContextManifest(
            manifest_id="m1", created_at=100.0, source_agents=["a"],
            total_memories=10, unique_memories=8, duplicates_removed=2,
            conflicts_resolved=1, strategy_used="lww", quality_score=0.8,
        )
        m2 = ContextManifest(
            manifest_id="m2", created_at=200.0, source_agents=["b"],
            total_memories=20, unique_memories=15, duplicates_removed=5,
            conflicts_resolved=3, strategy_used="union", quality_score=0.9,
        )
        assert m1.merge(m2) == m2.merge(m1)

    def test_manifest_associativity(self):
        def make(mid, ts, agents):
            return ContextManifest(
                manifest_id=mid, created_at=ts, source_agents=agents,
                total_memories=10, unique_memories=8, duplicates_removed=2,
                conflicts_resolved=1, strategy_used="lww", quality_score=0.8,
            )
        m1 = make("m1", 100, ["a"])
        m2 = make("m2", 200, ["b"])
        m3 = make("m3", 300, ["c"])
        assert m1.merge(m2).merge(m3) == m1.merge(m2.merge(m3))

    def test_manifest_idempotency(self):
        m = ContextManifest(
            manifest_id="m1", created_at=100.0, source_agents=["a"],
            total_memories=10, unique_memories=8, duplicates_removed=2,
            conflicts_resolved=1, strategy_used="lww", quality_score=0.8,
        )
        assert m.merge(m) == m


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  Scale Tests                                                             ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestScale:
    """Scale tests with 10K+ memories."""

    def test_merge_10k_memories(self):
        """Merge 10K memories from two agents, verifying dedup and performance."""
        n = 5000
        overlap = 1000  # 1K shared facts

        mems_a = [{"fact": f"fact-a-{i}", "source": "agent-a", "confidence": 0.8}
                  for i in range(n)]
        mems_b = [{"fact": f"fact-b-{i}", "source": "agent-b", "confidence": 0.7}
                  for i in range(n)]

        # Add overlap
        for i in range(overlap):
            mems_b[i] = {"fact": f"fact-a-{i}", "source": "agent-b", "confidence": 0.9}

        cm = ContextMerge(strategy="union")
        start = time.time()
        result = cm.merge(mems_a, mems_b)
        duration = time.time() - start

        # Should have deduped the overlapping memories
        expected_unique = n + n - overlap
        assert len(result.memories) == expected_unique
        assert result.duplicates_found == overlap
        # Should complete in reasonable time
        assert duration < 30.0, f"Merge took {duration:.1f}s"

    def test_consolidate_10k_memories(self):
        """Consolidate 10K memories into blocks."""
        chunks = [
            MemoryChunk(
                fact=f"fact-{i}",
                sidecar=MemorySidecar.from_fact(f"fact-{i}", topic="test"),
            )
            for i in range(10_000)
        ]
        c = ContextConsolidator(block_size=1000)
        blocks = c.consolidate(chunks)
        assert len(blocks) == 10
        assert sum(b.size for b in blocks) == 10_000

    def test_bloom_10k_items(self):
        """Bloom filter with 10K items — check false positive rate."""
        cb = ContextBloom(expected_items=20_000, fp_rate=0.01, num_shards=16)
        for i in range(10_000):
            cb.add(f"present-{i}")

        # All present items should be found
        for i in range(10_000):
            assert cb.contains(f"present-{i}")

        # Check FP rate on absent items
        fp = sum(1 for i in range(10_000) if cb.contains(f"absent-{i}"))
        assert fp / 10_000 < 0.05  # Allow generous margin

    def test_multi_merge_large(self):
        """Multi-merge across 4 agents with 1K each."""
        sets = [
            [{"fact": f"agent{a}-fact-{i}", "source": f"agent-{a}"}
             for i in range(1000)]
            for a in range(4)
        ]
        cm = ContextMerge(strategy="union")
        result = cm.merge_multi(*sets)
        assert len(result.memories) == 4000


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  Integration Tests                                                       ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestIntegration:
    """Integration tests: merge → serialize → deserialize → merge again."""

    def test_sidecar_merge_serialize_merge(self):
        sc1 = MemorySidecar.from_fact("hello", confidence=0.7, tags=["a"])
        sc2 = MemorySidecar.from_fact("hello", confidence=0.9, tags=["b"])
        merged1 = sc1.merge(sc2)

        # Serialize and deserialize
        d = merged1.to_dict()
        restored = MemorySidecar.from_dict(d)
        assert merged1 == restored

        # Merge again with a third
        sc3 = MemorySidecar.from_fact("hello", confidence=0.5, tags=["c"])
        merged2 = restored.merge(sc3)
        assert merged2.confidence == 0.9
        assert set(merged2.tags) == {"a", "b", "c"}

    def test_bloom_merge_serialize_merge(self):
        cb1 = ContextBloom(expected_items=1000, num_shards=4)
        cb2 = ContextBloom(expected_items=1000, num_shards=4)
        for i in range(50):
            cb1.add(f"a-{i}")
        for i in range(50):
            cb2.add(f"b-{i}")
        merged1 = cb1.merge(cb2)

        # Serialize and deserialize
        d = merged1.to_dict()
        restored = ContextBloom.from_dict(d)
        assert merged1 == restored

        # Merge again
        cb3 = ContextBloom(expected_items=1000, num_shards=4)
        for i in range(50):
            cb3.add(f"c-{i}")
        merged2 = restored.merge(cb3)
        for prefix in ["a", "b", "c"]:
            for i in range(50):
                assert merged2.contains(f"{prefix}-{i}")

    def test_manifest_merge_serialize_merge(self):
        m1 = ContextManifest(
            manifest_id="m1", created_at=100.0, source_agents=["a"],
            total_memories=10, unique_memories=8, duplicates_removed=2,
            conflicts_resolved=1, strategy_used="lww", quality_score=0.8,
        )
        m2 = ContextManifest(
            manifest_id="m2", created_at=200.0, source_agents=["b"],
            total_memories=20, unique_memories=15, duplicates_removed=5,
            conflicts_resolved=3, strategy_used="union", quality_score=0.9,
        )
        merged1 = m1.merge(m2)
        d = merged1.to_dict()
        restored = ContextManifest.from_dict(d)
        assert merged1 == restored

        m3 = ContextManifest(
            manifest_id="m3", created_at=300.0, source_agents=["c"],
            total_memories=30, unique_memories=25, duplicates_removed=5,
            conflicts_resolved=2, strategy_used="lww", quality_score=0.95,
        )
        merged2 = restored.merge(m3)
        assert "c" in merged2.source_agents
        assert merged2.quality_score == 0.95

    def test_full_pipeline_merge_serialize_remerge(self):
        """Full end-to-end: merge → get result → serialize everything → remerge."""
        cm = ContextMerge(strategy="union")

        # First merge
        result1 = cm.merge(
            [{"fact": "earth orbits sun", "source": "astro-bot", "confidence": 0.99}],
            [{"fact": "water is H2O", "source": "chem-bot", "confidence": 0.95}],
        )

        # Serialize the bloom
        bloom_dict = result1.bloom.to_dict()
        restored_bloom = ContextBloom.from_dict(bloom_dict)

        # Serialize memories
        mem_dicts = [
            {"fact": mc.fact, "confidence": mc.sidecar.confidence,
             "source": mc.sidecar.source_agent, "topic": mc.sidecar.topic}
            for mc in result1.memories
        ]

        # Second merge with restored bloom
        cm2 = ContextMerge(strategy="union", bloom=restored_bloom)
        result2 = cm2.merge(
            mem_dicts,
            [{"fact": "pi is 3.14159", "source": "math-bot", "confidence": 0.9}],
        )

        assert len(result2.memories) == 3
        facts = {mc.fact for mc in result2.memories}
        assert "earth orbits sun" in facts
        assert "water is H2O" in facts
        assert "pi is 3.14159" in facts

    def test_consolidator_serialize_roundtrip(self):
        """Consolidate → serialize → deserialize → query."""
        c = ContextConsolidator(block_size=50)
        chunks = [
            MemoryChunk(
                fact=f"fact-{i}",
                sidecar=MemorySidecar.from_fact(f"fact-{i}", topic="test"),
            )
            for i in range(100)
        ]
        blocks = c.consolidate(chunks)

        # Serialize and restore
        block_dicts = [b.to_dict() for b in blocks]
        restored_blocks = [ConsolidatedBlock.from_dict(d) for d in block_dicts]

        # Query on restored blocks
        results = c.query(restored_blocks, topic="test")
        assert len(results) == 100


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  Edge Case Tests                                                         ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


class TestEdgeCases:
    """Edge cases and robustness tests."""

    def test_sidecar_empty_fact(self):
        sc = MemorySidecar.from_fact("")
        assert sc.fact_id
        assert sc.content_hash

    def test_sidecar_unicode_fact(self):
        sc = MemorySidecar.from_fact("日本語テスト ")
        assert sc.fact_id
        assert len(sc.content_hash) == 64

    def test_sidecar_merge_with_empty_tags(self):
        sc1 = MemorySidecar.from_fact("f", tags=[])
        sc2 = MemorySidecar.from_fact("f", tags=["x"])
        merged = sc1.merge(sc2)
        assert merged.tags == ["x"]

    def test_sidecar_merge_with_empty_metadata(self):
        sc1 = MemorySidecar.from_fact("f", metadata={})
        sc2 = MemorySidecar.from_fact("f", metadata={"k": "v"})
        merged = sc1.merge(sc2)
        assert merged.metadata == {"k": "v"}

    def test_bloom_empty_merge(self):
        cb1 = ContextBloom(num_shards=4)
        cb2 = ContextBloom(num_shards=4)
        merged = cb1.merge(cb2)
        assert merged.estimated_items == 0

    def test_manifest_empty_agents(self):
        m = ContextManifest(
            manifest_id="m", created_at=0.0, source_agents=[],
            total_memories=0, unique_memories=0, duplicates_removed=0,
            conflicts_resolved=0, strategy_used="", quality_score=0.0,
        )
        assert m.source_agents == []

    def test_consolidator_block_size_one(self):
        c = ContextConsolidator(block_size=1)
        chunks = [
            MemoryChunk(f"f{i}", MemorySidecar.from_fact(f"f{i}"))
            for i in range(5)
        ]
        blocks = c.consolidate(chunks)
        assert len(blocks) == 5
        assert all(b.size == 1 for b in blocks)

    def test_merge_many_duplicates(self):
        """All memories are the same — should collapse to 1."""
        cm = ContextMerge(strategy="union")
        mems = [{"fact": "same"} for _ in range(100)]
        result = cm.merge(mems[:50], mems[50:])
        assert len(result.memories) == 1

    def test_merge_no_source_agent(self):
        cm = ContextMerge(strategy="union")
        result = cm.merge([{"fact": "a"}], [{"fact": "b"}])
        assert result.manifest.source_agents == []

    def test_bloom_add_many_same_item(self):
        cb = ContextBloom(expected_items=100, num_shards=4)
        for _ in range(100):
            cb.add("same")
        assert cb.contains("same")

    def test_repr_methods(self):
        """All repr methods should not raise."""
        sc = MemorySidecar.from_fact("test")
        repr(sc)

        m = ContextManifest(
            manifest_id="m", created_at=0.0, source_agents=[],
            total_memories=0, unique_memories=0, duplicates_removed=0,
            conflicts_resolved=0, strategy_used="", quality_score=0.0,
        )
        repr(m)

        cb = ContextBloom(num_shards=4)
        repr(cb)

        c = ContextConsolidator()
        repr(c)

        cm = ContextMerge()
        repr(cm)

        mc = MemoryChunk("f", MemorySidecar.from_fact("f"))
        repr(mc)

        blk = ConsolidatedBlock("b", [], {}, 0.0)
        repr(blk)

        mr = MergeResult([], m, cb, 0, 0)
        repr(mr)
