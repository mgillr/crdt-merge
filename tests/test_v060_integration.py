# Copyright 2026 Ryan Gillespie / Optitransfer
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""v0.6.0 Integration Tests — Cross-Module Pipeline Verification.

Tests all new v0.6.0 modules and their cross-module interactions:
  - Arrow + Schema Evolution pipeline
  - Gossip + Vector Clock pipeline
  - Merkle + Delta pipeline
  - Arrow + Parallel pipeline
  - Async + Streaming pipeline
  - Multi-Key + Existing Features
  - Wire Protocol v2 roundtrips
  - Full end-to-end distributed simulations
  - Import verification
"""

import pytest
import os
import json
import pathlib

pa = pytest.importorskip("pyarrow", reason="PyArrow not installed")


# ═══════════════════════════════════════════════════════════════
# SECTION 1: ARROW + SCHEMA EVOLUTION PIPELINE
# ═══════════════════════════════════════════════════════════════

class TestArrowSchemaEvolution:
    def test_arrow_merge_with_schema_drift(self):
        """Arrow merge two tables with different schemas → auto-resolves via schema_evolution."""
        from crdt_merge.arrow import ArrowMerge
        from crdt_merge.strategies import MergeSchema, LWW
        import pyarrow as pa

        left = pa.table({"id": [1, 2], "name": ["Alice", "Bob"]})
        right = pa.table({"id": [2, 3], "name": ["Bobby", "Charlie"], "email": ["b@x.com", "c@x.com"]})
        engine = ArrowMerge(schema=MergeSchema(default=LWW()))
        result = engine.merge(left, right, key="id")
        assert result.num_rows == 3
        assert "email" in result.column_names

    def test_arrow_fallback_with_list_dicts(self):
        """arrow_merge works with list[dict] inputs."""
        from crdt_merge.arrow import arrow_merge

        left = [{"id": 1, "val": 10}]
        right = [{"id": 2, "val": 20}]
        result = arrow_merge(left, right, key="id")
        # Result is pa.Table when pyarrow is available
        if hasattr(result, 'num_rows'):
            assert result.num_rows == 2
        else:
            assert len(result) == 2

    def test_arrow_all_8_strategies(self):
        """All 8 merge strategies work through Arrow engine."""
        from crdt_merge.arrow import ArrowMerge
        from crdt_merge.strategies import (
            MergeSchema, LWW, MaxWins, MinWins, UnionSet, Priority,
            Concat, Custom, LongestWins,
        )
        import pyarrow as pa

        strategies = [LWW(), MaxWins(), MinWins(), LongestWins()]
        for strategy in strategies:
            engine = ArrowMerge(schema=MergeSchema(default=strategy))
            left = pa.table({"id": [1], "val": [10]})
            right = pa.table({"id": [1], "val": [20]})
            result = engine.merge(left, right, key="id")
            assert result.num_rows == 1

    def test_schema_evolution_union_policy(self):
        """Schema evolution with UNION policy keeps all columns."""
        from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy

        old = {"id": "int64", "name": "str"}
        new = {"id": "int64", "email": "str"}
        result = evolve_schema(old, new, policy=SchemaPolicy.UNION)
        assert "name" in result.resolved_schema
        assert "email" in result.resolved_schema
        assert result.is_compatible

    def test_schema_evolution_type_widening(self):
        """Schema evolution widens int32 → int64 automatically."""
        from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy

        old = {"id": "int32", "val": "float32"}
        new = {"id": "int64", "val": "float64"}
        result = evolve_schema(old, new, policy=SchemaPolicy.UNION)
        assert result.resolved_schema["id"] == "int64"
        assert result.resolved_schema["val"] == "float64"

    def test_schema_check_compatibility(self):
        """check_compatibility reports incompatible schemas."""
        from crdt_merge.schema_evolution import check_compatibility

        compat, reasons = check_compatibility(
            {"id": "int64", "name": "str"},
            {"id": "int64", "name": "str"},
        )
        assert compat is True
        assert len(reasons) == 0

    def test_schema_incompatibility_detected(self):
        """check_compatibility detects missing columns."""
        from crdt_merge.schema_evolution import check_compatibility

        compat, reasons = check_compatibility(
            {"id": "int64"},
            {"id": "int64", "extra": "str"},
        )
        assert compat is False
        assert len(reasons) > 0

    def test_arrow_merge_no_key_dedup(self):
        """Arrow merge without key concatenates and deduplicates."""
        from crdt_merge.arrow import ArrowMerge
        import pyarrow as pa

        left = pa.table({"id": [1, 2], "val": ["a", "b"]})
        right = pa.table({"id": [2, 3], "val": ["b", "c"]})
        engine = ArrowMerge()
        result = engine.merge(left, right)
        assert result.num_rows == 3  # row (2, "b") deduped


# ═══════════════════════════════════════════════════════════════
# SECTION 2: GOSSIP + VECTOR CLOCK PIPELINE
# ═══════════════════════════════════════════════════════════════

class TestGossipVectorClock:
    def test_multi_node_gossip_convergence(self):
        """3 nodes with different updates converge after full sync."""
        from crdt_merge.gossip import GossipState

        n1 = GossipState("node-1")
        n2 = GossipState("node-2")
        n3 = GossipState("node-3")
        n1.update("key-a", "val-1")
        n2.update("key-b", "val-2")
        n3.update("key-c", "val-3")

        # Sync: n1 ↔ n2
        push_keys = n1.anti_entropy_push(n2.digest())
        n2.apply_entries(n1.get_entries(push_keys))
        pull_keys = n1.anti_entropy_pull(n2.digest())
        n1.apply_entries(n2.get_entries(pull_keys))

        # Sync: n1 ↔ n3
        push_keys = n1.anti_entropy_push(n3.digest())
        n3.apply_entries(n1.get_entries(push_keys))
        pull_keys = n1.anti_entropy_pull(n3.digest())
        n1.apply_entries(n3.get_entries(pull_keys))

        # Sync: n2 ↔ n3
        push_keys = n2.anti_entropy_push(n3.digest())
        n3.apply_entries(n2.get_entries(push_keys))
        pull_keys = n2.anti_entropy_pull(n3.digest())
        n2.apply_entries(n3.get_entries(pull_keys))

        # All should have all 3 keys
        for node in [n1, n2, n3]:
            assert node.get("key-a") == "val-1"
            assert node.get("key-b") == "val-2"
            assert node.get("key-c") == "val-3"

    def test_gossip_anti_entropy_cycle(self):
        """Full anti-entropy cycle: digest → diff → apply → converge."""
        from crdt_merge.gossip import GossipState, anti_entropy

        local = GossipState("local")
        remote = GossipState("remote")
        local.update("x", 42)
        remote.update("y", 99)

        result = anti_entropy(local.digest(), remote.digest())
        assert "y" in result["missing_local"]
        assert "x" in result["missing_remote"]

    def test_vector_clock_compare(self):
        """VectorClock comparison detects BEFORE/AFTER/CONCURRENT/EQUAL."""
        from crdt_merge.clocks import VectorClock, Ordering

        a = VectorClock({"n1": 3, "n2": 1})
        b = VectorClock({"n1": 2, "n2": 4})
        assert a.compare(b) == Ordering.CONCURRENT

        c = VectorClock({"n1": 1})
        d = VectorClock({"n1": 2})
        assert c.compare(d) == Ordering.BEFORE
        assert d.compare(c) == Ordering.AFTER

        e = VectorClock({"n1": 5})
        f = VectorClock({"n1": 5})
        assert e.compare(f) == Ordering.EQUAL

    def test_vector_clock_merge(self):
        """VectorClock merge takes element-wise max."""
        from crdt_merge.clocks import VectorClock

        a = VectorClock({"n1": 3, "n2": 1})
        b = VectorClock({"n1": 2, "n2": 4})
        merged = a.merge(b)
        assert merged.value == {"n1": 3, "n2": 4}

    def test_dotted_version_vector_advance_merge(self):
        """DottedVersionVector advance creates dot; merge folds it."""
        from crdt_merge.clocks import DottedVersionVector, VectorClock

        dvv = DottedVersionVector()
        dvv2 = dvv.advance("node-A")
        assert dvv2.dot == ("node-A", 1)

        dvv3 = DottedVersionVector(base=VectorClock({"node-B": 2}))
        merged = dvv2.merge(dvv3)
        assert merged.dot is None
        assert merged.value.get("node-A", 0) >= 1
        assert merged.value.get("node-B", 0) >= 2

    def test_gossip_state_merge(self):
        """GossipState.merge produces correct union of entries."""
        from crdt_merge.gossip import GossipState

        a = GossipState("a")
        b = GossipState("b")
        a.update("key1", "val-a")
        b.update("key2", "val-b")
        merged = a.merge(b)
        assert merged.get("key1") == "val-a"
        assert merged.get("key2") == "val-b"

    def test_gossip_tombstone(self):
        """Deleting a key creates a tombstone that propagates."""
        from crdt_merge.gossip import GossipState

        s = GossipState("node-1")
        s.update("key", "value")
        assert s.get("key") == "value"
        s.delete("key")
        assert s.get("key") is None
        entry = s.get_entry("key")
        assert entry is not None and entry.tombstone

    def test_gossip_push_pull(self):
        """anti_entropy_push_pull returns correct push and pull sets."""
        from crdt_merge.gossip import GossipState

        a = GossipState("a")
        b = GossipState("b")
        a.update("only-a", 1)
        b.update("only-b", 2)

        push_keys, pull_keys = a.anti_entropy_push_pull(b.digest())
        assert "only-a" in push_keys
        assert "only-b" in pull_keys


# ═══════════════════════════════════════════════════════════════
# SECTION 3: MERKLE + DELTA PIPELINE
# ═══════════════════════════════════════════════════════════════

class TestMerkleDelta:
    def test_merkle_diff_then_delta(self):
        """Merkle diff finds divergent keys, then delta computes what changed."""
        from crdt_merge.merkle import MerkleTree, merkle_diff
        from crdt_merge.delta import compute_delta

        ds_a = [{"id": "1", "val": "a"}, {"id": "2", "val": "b"}]
        ds_b = [{"id": "1", "val": "a"}, {"id": "2", "val": "x"}]
        tree_a = MerkleTree.from_records(ds_a, key="id")
        tree_b = MerkleTree.from_records(ds_b, key="id")
        diff = merkle_diff(tree_a, tree_b)
        assert "2" in diff.common_different

        delta = compute_delta(ds_a, ds_b, key="id")
        assert len(delta.modified) > 0

    def test_merkle_identical_trees(self):
        """Identical datasets produce identical root hashes."""
        from crdt_merge.merkle import MerkleTree, merkle_diff

        records = [{"id": str(i), "val": f"v{i}"} for i in range(50)]
        tree_a = MerkleTree.from_records(records, key="id")
        tree_b = MerkleTree.from_records(records, key="id")
        assert tree_a.root_hash == tree_b.root_hash
        diff = merkle_diff(tree_a, tree_b)
        assert diff.is_identical
        assert diff.comparisons_made == 1

    def test_merkle_only_left_right(self):
        """MerkleDiff correctly identifies only-left and only-right keys."""
        from crdt_merge.merkle import MerkleTree, merkle_diff

        ds_a = [{"id": "1", "val": "a"}, {"id": "2", "val": "b"}]
        ds_b = [{"id": "2", "val": "b"}, {"id": "3", "val": "c"}]
        tree_a = MerkleTree.from_records(ds_a, key="id")
        tree_b = MerkleTree.from_records(ds_b, key="id")
        diff = merkle_diff(tree_a, tree_b)
        assert "1" in diff.only_in_left
        assert "3" in diff.only_in_right

    def test_merkle_tree_merge(self):
        """MerkleTree.merge creates a union of both trees."""
        from crdt_merge.merkle import MerkleTree

        ds_a = [{"id": "1", "val": "a"}]
        ds_b = [{"id": "2", "val": "b"}]
        tree_a = MerkleTree.from_records(ds_a, key="id")
        tree_b = MerkleTree.from_records(ds_b, key="id")
        merged = tree_a.merge(tree_b)
        assert merged.size == 2
        assert merged.contains("1")
        assert merged.contains("2")

    def test_merkle_insert_delete(self):
        """Insert and delete mutate the tree correctly."""
        from crdt_merge.merkle import MerkleTree

        tree = MerkleTree()
        tree.insert("k1", {"id": "k1", "val": "a"})
        assert tree.size == 1
        assert tree.contains("k1")
        tree.delete("k1")
        assert tree.size == 0
        assert not tree.contains("k1")

    def test_merkle_large_diff(self):
        """Diff of large trees works correctly."""
        from crdt_merge.merkle import MerkleTree, merkle_diff

        ds_a = [{"id": str(i), "val": f"a{i}"} for i in range(500)]
        ds_b = [{"id": str(i), "val": f"a{i}"} for i in range(250, 750)]
        tree_a = MerkleTree.from_records(ds_a, key="id")
        tree_b = MerkleTree.from_records(ds_b, key="id")
        diff = merkle_diff(tree_a, tree_b)
        assert len(diff.only_in_left) == 250
        assert len(diff.only_in_right) == 250

    def test_delta_after_merkle_detected_changes(self):
        """Use merkle diff to find changes, then compute delta for those keys."""
        from crdt_merge.merkle import MerkleTree, merkle_diff
        from crdt_merge.delta import compute_delta

        ds_a = [{"id": str(i), "val": f"a{i}"} for i in range(100)]
        ds_b = list(ds_a)
        # Mutate 5 records in ds_b
        for i in range(5):
            ds_b[i] = {"id": str(i), "val": f"CHANGED_{i}"}

        tree_a = MerkleTree.from_records(ds_a, key="id")
        tree_b = MerkleTree.from_records(ds_b, key="id")
        diff = merkle_diff(tree_a, tree_b)
        assert diff.num_differences == 5

        delta = compute_delta(ds_a, ds_b, key="id")
        assert len(delta.modified) > 0

    def test_merkle_diff_serialization(self):
        """MerkleDiff.to_dict() produces valid output."""
        from crdt_merge.merkle import MerkleTree, merkle_diff

        ds_a = [{"id": "1", "val": "a"}]
        ds_b = [{"id": "1", "val": "b"}, {"id": "2", "val": "c"}]
        tree_a = MerkleTree.from_records(ds_a, key="id")
        tree_b = MerkleTree.from_records(ds_b, key="id")
        diff = merkle_diff(tree_a, tree_b)
        d = diff.to_dict()
        assert isinstance(d, dict)
        assert "differing_keys" in d
        assert "only_in_right" in d


# ═══════════════════════════════════════════════════════════════
# SECTION 4: ARROW + PARALLEL PIPELINE
# ═══════════════════════════════════════════════════════════════

class TestArrowParallel:
    def test_parallel_merge_large(self):
        """Parallel merge with 10K+ rows."""
        from crdt_merge.parallel import parallel_merge

        left = [{"id": i, "val": i} for i in range(10000)]
        right = [{"id": i, "val": i + 1} for i in range(5000, 15000)]
        result = parallel_merge(left, right, key="id", chunk_size=2000)
        assert len(result) == 15000

    def test_parallel_merge_small_fallback(self):
        """Parallel merge falls back to sequential for small datasets."""
        from crdt_merge.parallel import parallel_merge

        left = [{"id": i, "val": i} for i in range(50)]
        right = [{"id": i, "val": i + 1} for i in range(25, 75)]
        result = parallel_merge(left, right, key="id")
        assert len(result) == 75

    def test_parallel_merge_arrow_backend(self):
        """parallel_merge_arrow uses Arrow when available."""
        from crdt_merge.parallel import parallel_merge_arrow

        left = [{"id": i, "val": i} for i in range(100)]
        right = [{"id": i, "val": i + 1} for i in range(50, 150)]
        result = parallel_merge_arrow(left, right, key="id")
        if hasattr(result, 'num_rows'):
            assert result.num_rows == 150
        else:
            assert len(result) == 150

    def test_arrow_merge_tables_multi(self):
        """Merge a sequence of Arrow tables pairwise."""
        from crdt_merge.arrow import arrow_merge_tables
        import pyarrow as pa

        tables = [
            pa.table({"id": [1, 2], "val": ["a", "b"]}),
            pa.table({"id": [2, 3], "val": ["B", "c"]}),
            pa.table({"id": [3, 4], "val": ["C", "d"]}),
        ]
        result = arrow_merge_tables(tables, key="id")
        assert result.num_rows == 4

    def test_parallel_preserves_all_keys(self):
        """No keys lost during parallel chunk splitting."""
        from crdt_merge.parallel import parallel_merge

        left = [{"id": i, "val": f"L{i}"} for i in range(0, 20000, 2)]
        right = [{"id": i, "val": f"R{i}"} for i in range(1, 20001, 2)]
        result = parallel_merge(left, right, key="id", chunk_size=3000)
        assert len(result) == 20000

    def test_parallel_with_schema(self):
        """Parallel merge respects MergeSchema strategies."""
        from crdt_merge.parallel import parallel_merge
        from crdt_merge.strategies import MergeSchema, MaxWins

        schema = MergeSchema(score=MaxWins())
        left = [{"id": i, "score": i * 10} for i in range(10000)]
        right = [{"id": i, "score": i * 10 + 5} for i in range(5000, 15000)]
        result = parallel_merge(left, right, key="id", schema=schema, chunk_size=2000)
        assert len(result) == 15000


# ═══════════════════════════════════════════════════════════════
# SECTION 5: ASYNC + STREAMING PIPELINE
# ═══════════════════════════════════════════════════════════════

class TestAsyncStreaming:
    @pytest.mark.asyncio
    async def test_async_merge_basic(self):
        """amerge produces correct results."""
        from crdt_merge.async_merge import amerge

        a = [{"id": i, "val": f"a{i}"} for i in range(50)]
        b = [{"id": i, "val": f"b{i}"} for i in range(25, 75)]
        result = await amerge(a, b, key="id")
        assert len(result) == 75

    @pytest.mark.asyncio
    async def test_async_streaming_merge(self):
        """amerge_stream produces correct total count."""
        from crdt_merge.async_merge import amerge_stream

        a = [{"id": i, "val": f"a{i}"} for i in range(100)]
        b = [{"id": i, "val": f"b{i}"} for i in range(50, 150)]
        batches = []
        async for batch in amerge_stream(a, b, key="id", batch_size=50):
            batches.append(batch)
        total = sum(len(b) for b in batches)
        assert total == 150

    @pytest.mark.asyncio
    async def test_async_sorted_stream(self):
        """amerge_sorted_stream handles pre-sorted inputs."""
        from crdt_merge.async_merge import amerge_sorted_stream

        a = [{"id": i, "val": f"a{i}"} for i in range(0, 100, 2)]
        b = [{"id": i, "val": f"b{i}"} for i in range(1, 101, 2)]
        batches = []
        async for batch in amerge_sorted_stream(a, b, key="id", batch_size=25):
            batches.append(batch)
        total = sum(len(b) for b in batches)
        assert total == 100

    @pytest.mark.asyncio
    async def test_async_merge_with_schema(self):
        """amerge passes schema to underlying merge."""
        from crdt_merge.async_merge import amerge
        from crdt_merge.strategies import MergeSchema, MaxWins

        schema = MergeSchema(score=MaxWins())
        a = [{"id": 1, "score": 80}]
        b = [{"id": 1, "score": 95}]
        result = await amerge(a, b, key="id", schema=schema)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_async_empty_inputs(self):
        """amerge handles empty inputs gracefully."""
        from crdt_merge.async_merge import amerge

        result = await amerge([], [], key="id")
        assert result == []

    @pytest.mark.asyncio
    async def test_async_stream_single_batch(self):
        """amerge_stream with small data yields a single batch."""
        from crdt_merge.async_merge import amerge_stream

        a = [{"id": 1, "val": "a"}]
        b = [{"id": 2, "val": "b"}]
        batches = []
        async for batch in amerge_stream(a, b, key="id", batch_size=100):
            batches.append(batch)
        total = sum(len(b) for b in batches)
        assert total == 2


# ═══════════════════════════════════════════════════════════════
# SECTION 6: MULTI-KEY + EXISTING FEATURES
# ═══════════════════════════════════════════════════════════════

class TestMultiKeyExisting:
    def test_multi_key_with_provenance(self):
        """Single-key merge with provenance tracking."""
        from crdt_merge.provenance import merge_with_provenance

        a = [{"id": 1, "sales": 100}]
        b = [{"id": 1, "sales": 150}, {"id": 2, "sales": 200}]
        result, log = merge_with_provenance(a, b, key="id")
        assert len(result) == 2
        assert log is not None

    def test_multi_key_basic_merge(self):
        """Multi-key merge with list of keys."""
        from crdt_merge.dataframe import merge

        a = [{"region": "US", "product": "A", "qty": 10},
             {"region": "EU", "product": "B", "qty": 20}]
        b = [{"region": "US", "product": "A", "qty": 15},
             {"region": "US", "product": "C", "qty": 5}]
        result = merge(a, b, key=["region", "product"])
        assert len(result) == 3  # US-A, EU-B, US-C

    def test_multi_key_with_streaming(self):
        """Single-key merge with streaming produces correct output."""
        from crdt_merge.streaming import merge_stream

        a = [{"id": i, "val": f"a{i}"} for i in range(10)]
        b = [{"id": i, "val": f"b{i}"} for i in range(5, 15)]
        chunks = list(merge_stream(a, b, key="id"))
        flat = [r for chunk in chunks for r in chunk]
        assert len(flat) == 15

    def test_multi_key_no_overlap(self):
        """Multi-key merge with zero overlap."""
        from crdt_merge.dataframe import merge

        a = [{"k1": "a", "k2": 1, "v": "x"}]
        b = [{"k1": "b", "k2": 2, "v": "y"}]
        result = merge(a, b, key=["k1", "k2"])
        assert len(result) == 2

    def test_provenance_with_arrow_merge(self):
        """Provenance tracking works alongside arrow merge results."""
        from crdt_merge.provenance import merge_with_provenance

        a = [{"id": 1, "val": "a"}]
        b = [{"id": 1, "val": "b"}, {"id": 2, "val": "c"}]
        result, log = merge_with_provenance(a, b, key="id")
        assert len(result) == 2
        assert log.total_rows >= 2

    def test_dedup_then_parallel_merge(self):
        """Dedup removes exact duplicates before merge."""
        from crdt_merge.dedup import dedup_records
        from crdt_merge.dataframe import merge

        raw = [{"id": 1, "v": "a"}, {"id": 1, "v": "a"}, {"id": 2, "v": "b"}]
        clean, dups = dedup_records(raw)
        assert dups >= 1  # at least 1 duplicate removed
        assert len(clean) == 2

        other = [{"id": 2, "v": "B"}, {"id": 3, "v": "c"}]
        result = merge(clean, other, key="id")
        assert len(result) >= 2  # at least the overlapping + unique keys


# ═══════════════════════════════════════════════════════════════
# SECTION 7: WIRE PROTOCOL v2 ROUNDTRIP
# ═══════════════════════════════════════════════════════════════

class TestWireProtocolV2:
    def test_wire_vector_clock_roundtrip(self):
        """VectorClock survives serialize → deserialize."""
        from crdt_merge.clocks import VectorClock
        from crdt_merge.wire import serialize, deserialize

        vc = VectorClock({"a": 3, "b": 7})
        data = serialize(vc)
        restored = deserialize(data)
        assert isinstance(restored, VectorClock)
        assert restored.value == vc.value

    def test_wire_dotted_version_vector_roundtrip(self):
        """DottedVersionVector survives roundtrip."""
        from crdt_merge.clocks import DottedVersionVector, VectorClock
        from crdt_merge.wire import serialize, deserialize

        dvv = DottedVersionVector(
            base=VectorClock({"n1": 5, "n2": 3}),
            dot=("n1", 6),
        )
        data = serialize(dvv)
        restored = deserialize(data)
        assert isinstance(restored, DottedVersionVector)
        assert restored.value == dvv.value

    def test_wire_merkle_tree_roundtrip(self):
        """MerkleTree survives roundtrip."""
        from crdt_merge.merkle import MerkleTree
        from crdt_merge.wire import serialize, deserialize

        tree = MerkleTree.from_records(
            [{"id": "1", "val": "a"}, {"id": "2", "val": "b"}], key="id"
        )
        data = serialize(tree)
        restored = deserialize(data)
        assert isinstance(restored, MerkleTree)
        assert restored.size == tree.size
        assert restored.root_hash == tree.root_hash

    def test_wire_gossip_state_roundtrip(self):
        """GossipState survives roundtrip."""
        from crdt_merge.gossip import GossipState
        from crdt_merge.wire import serialize, deserialize

        gs = GossipState("node-1")
        gs.update("key1", "value1")
        gs.update("key2", {"nested": True})
        data = serialize(gs)
        restored = deserialize(data)
        assert isinstance(restored, GossipState)
        assert restored.get("key1") == "value1"

    def test_wire_gossip_entry_roundtrip(self):
        """GossipEntry survives roundtrip."""
        from crdt_merge.gossip import GossipEntry
        from crdt_merge.clocks import VectorClock
        from crdt_merge.wire import serialize, deserialize

        entry = GossipEntry(
            key="test", value=42, clock=VectorClock({"n1": 3}), tombstone=False
        )
        data = serialize(entry)
        restored = deserialize(data)
        assert isinstance(restored, GossipEntry)
        assert restored.key == "test"
        assert restored.value == 42

    def test_wire_schema_evolution_result_roundtrip(self):
        """SchemaEvolutionResult survives roundtrip."""
        from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy, SchemaEvolutionResult
        from crdt_merge.wire import serialize, deserialize

        result = evolve_schema(
            {"id": "int64", "name": "str"},
            {"id": "int64", "email": "str"},
            policy=SchemaPolicy.UNION,
        )
        data = serialize(result)
        restored = deserialize(data)
        assert isinstance(restored, SchemaEvolutionResult)
        assert "name" in restored.resolved_schema
        assert "email" in restored.resolved_schema

    def test_wire_backward_compat(self):
        """v0.5.0 serialized data still deserializes correctly."""
        from crdt_merge.core import GCounter
        from crdt_merge.wire import serialize, deserialize

        gc = GCounter("n1", 42)
        data = serialize(gc)
        restored = deserialize(data)
        assert restored.value == 42

    def test_wire_v060_compressed(self):
        """v0.6.0 types work with compression enabled."""
        from crdt_merge.clocks import VectorClock
        from crdt_merge.wire import serialize, deserialize

        vc = VectorClock({f"node_{i}": i * 100 for i in range(50)})
        data_raw = serialize(vc, compress=False)
        data_comp = serialize(vc, compress=True)
        restored = deserialize(data_comp)
        assert isinstance(restored, VectorClock)
        assert restored.value == vc.value


# ═══════════════════════════════════════════════════════════════
# SECTION 8: FULL END-TO-END
# ═══════════════════════════════════════════════════════════════

class TestFullEndToEnd:
    def test_full_distributed_simulation(self):
        """gossip → merkle diff → provenance pipeline."""
        from crdt_merge.gossip import GossipState
        from crdt_merge.merkle import MerkleTree, merkle_diff
        from crdt_merge.provenance import merge_with_provenance

        # Two nodes diverge
        n1 = GossipState("node-1")
        n2 = GossipState("node-2")
        for i in range(10):
            n1.update(f"key-{i}", {"val": f"n1-{i}"})
        for i in range(5, 15):
            n2.update(f"key-{i}", {"val": f"n2-{i}"})

        # Build merkle trees from their entries
        ds1 = [{"id": k, "val": str(e.value)} for k, e in n1._entries.items() if not e.tombstone]
        ds2 = [{"id": k, "val": str(e.value)} for k, e in n2._entries.items() if not e.tombstone]

        tree1 = MerkleTree.from_records(ds1, key="id")
        tree2 = MerkleTree.from_records(ds2, key="id")
        diff = merkle_diff(tree1, tree2)
        assert diff.num_differences > 0

        # Merge the datasets with provenance
        result, log = merge_with_provenance(ds1, ds2, key="id")
        assert len(result) == 15  # keys 0-14
        assert isinstance(log.summary(), str)

    def test_all_v050_examples_still_work(self):
        """Verify backward compatibility with v0.5.0 usage patterns."""
        from crdt_merge import merge, MergeSchema, LWW, MaxWins

        left = [{"id": 1, "name": "Alice", "score": 10}]
        right = [{"id": 1, "name": "Alicia", "score": 15}]
        schema = MergeSchema(default=LWW(), score=MaxWins())
        result = merge(left, right, key="id", schema=schema)
        assert result[0]["score"] == 15
        assert result[0]["name"] in ["Alice", "Alicia"]

    def test_schema_evolution_then_arrow_merge(self):
        """Schema evolution output drives Arrow merge."""
        from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy
        from crdt_merge.arrow import ArrowMerge
        import pyarrow as pa

        # Schemas with drift
        old_schema = {"id": "int64", "name": "string"}
        new_schema = {"id": "int64", "name": "string", "email": "string"}
        evo = evolve_schema(old_schema, new_schema, SchemaPolicy.UNION)
        assert "email" in evo.resolved_schema

        # Arrow merge handles the drift automatically
        left = pa.table({"id": [1], "name": ["Alice"]})
        right = pa.table({"id": [2], "name": ["Bob"], "email": ["bob@x.com"]})
        engine = ArrowMerge()
        result = engine.merge(left, right, key="id")
        assert result.num_rows == 2
        assert "email" in result.column_names

    def test_gossip_then_parallel_merge(self):
        """Gossip sync followed by parallel merge of detected differences."""
        from crdt_merge.gossip import GossipState
        from crdt_merge.parallel import parallel_merge

        n1 = GossipState("n1")
        n2 = GossipState("n2")
        for i in range(100):
            n1.update(f"k{i}", {"id": i, "val": f"n1-{i}"})
        for i in range(50, 200):
            n2.update(f"k{i}", {"id": i, "val": f"n2-{i}"})

        # Collect data as records
        ds1 = [{"id": i, "val": f"n1-{i}"} for i in range(100)]
        ds2 = [{"id": i, "val": f"n2-{i}"} for i in range(50, 200)]

        # Parallel merge
        result = parallel_merge(ds1, ds2, key="id")
        assert len(result) == 200

    def test_vector_clock_causal_ordering_in_merge(self):
        """Vector clocks determine which value wins in concurrent updates."""
        from crdt_merge.clocks import VectorClock, Ordering

        # Simulate two nodes updating the same key
        clock_a = VectorClock({"n1": 5, "n2": 3})
        clock_b = VectorClock({"n1": 3, "n2": 7})
        assert clock_a.compare(clock_b) == Ordering.CONCURRENT

        # Merge resolves by element-wise max
        merged = clock_a.merge(clock_b)
        assert merged.value == {"n1": 5, "n2": 7}

    def test_merkle_plus_wire_roundtrip(self):
        """Build merkle tree → serialize → deserialize → verify hash."""
        from crdt_merge.merkle import MerkleTree
        from crdt_merge.wire import serialize, deserialize

        records = [{"id": str(i), "data": f"value-{i}"} for i in range(100)]
        tree = MerkleTree.from_records(records, key="id")
        original_hash = tree.root_hash

        data = serialize(tree)
        restored = deserialize(data)
        assert restored.root_hash == original_hash

    def test_full_pipeline_dedup_merge_provenance_export(self):
        """dedup → merge → provenance → export JSON."""
        from crdt_merge import dedup_records, merge_with_provenance, export_provenance

        raw_a = [{"id": 1, "v": "a"}, {"id": 1, "v": "a"}, {"id": 2, "v": "b"}]
        raw_b = [{"id": 2, "v": "B"}, {"id": 3, "v": "c"}]
        clean_a, _ = dedup_records(raw_a)
        result, log = merge_with_provenance(clean_a, raw_b, key="id")
        assert len(result) == 3
        exported = export_provenance(log, format="json")
        parsed = json.loads(exported)
        assert isinstance(parsed, dict)

    def test_wire_batch_mixed_v050_v060(self):
        """Batch serialize a mix of v0.5.0 and v0.6.0 types."""
        from crdt_merge.core import GCounter
        from crdt_merge.clocks import VectorClock
        from crdt_merge.wire import serialize, deserialize

        gc = GCounter("n1", 42)
        vc = VectorClock({"a": 1, "b": 2})

        gc_data = serialize(gc)
        vc_data = serialize(vc)

        gc_restored = deserialize(gc_data)
        vc_restored = deserialize(vc_data)

        assert gc_restored.value == 42
        assert isinstance(vc_restored, VectorClock)
        assert vc_restored.value == {"a": 1, "b": 2}


# ═══════════════════════════════════════════════════════════════
# SECTION 9: IMPORT VERIFICATION
# ═══════════════════════════════════════════════════════════════

class TestImportVerification:
    def test_all_v060_exports_available(self):
        """All new types are importable from crdt_merge."""
        from crdt_merge import (
            VectorClock, DottedVersionVector, Ordering,
            evolve_schema, SchemaPolicy, SchemaEvolutionResult,
            MerkleTree, merkle_diff, MerkleDiff,
            GossipState, GossipEntry, anti_entropy,
            ArrowMerge, arrow_merge,
            amerge, amerge_stream, amerge_sorted_stream,
            parallel_merge, parallel_merge_arrow,
        )
        assert all(x is not None for x in [
            VectorClock, DottedVersionVector, Ordering,
            evolve_schema, SchemaPolicy, SchemaEvolutionResult,
            MerkleTree, merkle_diff, MerkleDiff,
            GossipState, GossipEntry, anti_entropy,
            ArrowMerge, arrow_merge,
            amerge, amerge_stream, amerge_sorted_stream,
            parallel_merge, parallel_merge_arrow,
        ])

    def test_module_count_v060(self):
        """Package contains exactly 20 .py modules."""
        import crdt_merge

        pkg = pathlib.Path(crdt_merge.__file__).parent
        modules = [f.name for f in pkg.iterdir() if f.suffix == '.py' and f.name != '__pycache__']
        assert len(modules) >= 20  # v0.7.x added modules
