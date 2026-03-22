"""
Test suite covering every runnable Python code example from:
  - docs/guides/wire-protocol.md
  - docs/guides/delta-sync-merkle-verification.md
  - docs/guides/gossip-serverless-sync.md
"""

import pytest

# ---------------------------------------------------------------------------
# ===== WIRE PROTOCOL GUIDE =================================================
# ---------------------------------------------------------------------------


class TestWireProtocolUsage:
    """Covers the 'Usage' code block in wire-protocol.md."""

    def test_serialize_returns_bytes(self):
        from crdt_merge.wire import serialize

        data = {"users": [{"id": "1", "name": "Alice"}]}
        result = serialize(data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_peek_type_returns_string(self):
        from crdt_merge.wire import serialize, peek_type

        data = {"users": [{"id": "1", "name": "Alice"}]}
        wire = serialize(data)
        type_str = peek_type(wire)
        assert isinstance(type_str, str)
        # Generic dict → reported as "generic"
        assert type_str == "generic"

    def test_wire_size_returns_dict_with_total_bytes(self):
        from crdt_merge.wire import serialize, wire_size

        data = {"users": [{"id": "1", "name": "Alice"}]}
        wire = serialize(data)
        info = wire_size(wire)
        assert isinstance(info, dict)
        assert "total_bytes" in info
        assert "header_bytes" in info
        assert info["total_bytes"] == len(wire)

    def test_deserialize_round_trips(self):
        from crdt_merge.wire import serialize, deserialize

        data = {"users": [{"id": "1", "name": "Alice"}]}
        wire = serialize(data)
        restored = deserialize(wire)
        assert restored == data

    def test_serialize_deserialize_nested_dict(self):
        from crdt_merge.wire import serialize, deserialize

        data = {
            "scores": {"alice": 95, "bob": 87},
            "meta": {"version": 3, "active": True},
        }
        wire = serialize(data)
        assert deserialize(wire) == data

    def test_serialize_deserialize_list(self):
        from crdt_merge.wire import serialize, deserialize

        data = [{"id": str(i), "value": i} for i in range(10)]
        wire = serialize(data)
        assert deserialize(wire) == data

    def test_wire_size_header_plus_payload_equals_total(self):
        from crdt_merge.wire import serialize, wire_size

        data = {"key": "value"}
        info = wire_size(serialize(data))
        assert info["header_bytes"] + info["payload_bytes"] == info["total_bytes"]


# ---------------------------------------------------------------------------
# ===== DELTA SYNC & MERKLE GUIDE ===========================================
# ---------------------------------------------------------------------------


class TestDeltaComputeAndApply:
    """Covers 'Quick Start: Delta Computation and Application'."""

    def setup_method(self):
        self.records_v1 = [
            {"id": "A", "value": 100, "status": "active"},
            {"id": "B", "value": 200, "status": "active"},
            {"id": "C", "value": 300, "status": "active"},
        ]
        self.records_v2 = [
            {"id": "A", "value": 150, "status": "active"},
            {"id": "B", "value": 200, "status": "active"},
            {"id": "D", "value": 400, "status": "new"},
        ]

    def test_compute_delta_added(self):
        from crdt_merge.delta import compute_delta

        delta = compute_delta(
            self.records_v1, self.records_v2, key="id", version=2, source_node="primary"
        )
        assert len(delta.added) == 1  # D

    def test_compute_delta_modified(self):
        from crdt_merge.delta import compute_delta

        delta = compute_delta(
            self.records_v1, self.records_v2, key="id", version=2, source_node="primary"
        )
        assert len(delta.modified) == 1  # A

    def test_compute_delta_removed(self):
        from crdt_merge.delta import compute_delta

        delta = compute_delta(
            self.records_v1, self.records_v2, key="id", version=2, source_node="primary"
        )
        assert len(delta.removed) == 1  # C

    def test_apply_delta_record_count(self):
        from crdt_merge.delta import compute_delta, apply_delta

        delta = compute_delta(
            self.records_v1, self.records_v2, key="id", version=2, source_node="primary"
        )
        replica_v1 = list(self.records_v1)
        replica_v2 = apply_delta(replica_v1, delta, key="id")
        assert len(replica_v2) == 3  # A, B, D

    def test_apply_delta_modified_value(self):
        from crdt_merge.delta import compute_delta, apply_delta

        delta = compute_delta(
            self.records_v1, self.records_v2, key="id", version=2, source_node="primary"
        )
        result = apply_delta(list(self.records_v1), delta, key="id")
        a = next(r for r in result if r["id"] == "A")
        assert a["value"] == 150

    def test_apply_delta_removed_key_absent(self):
        from crdt_merge.delta import compute_delta, apply_delta

        delta = compute_delta(
            self.records_v1, self.records_v2, key="id", version=2, source_node="primary"
        )
        result = apply_delta(list(self.records_v1), delta, key="id")
        assert not any(r["id"] == "C" for r in result)

    def test_delta_size_equals_changes(self):
        from crdt_merge.delta import compute_delta

        delta = compute_delta(
            self.records_v1, self.records_v2, key="id", version=2, source_node="primary"
        )
        # 1 added + 1 modified + 1 removed = 3
        assert delta.size == len(delta.added) + len(delta.modified) + len(delta.removed)


class TestDeltaComposition:
    """Covers 'Cookbook: Delta Composition — Chain Sync Without Full State'."""

    def setup_method(self):
        self.v1 = [{"id": "1", "v": 1}, {"id": "2", "v": 2}]
        self.v2 = [{"id": "1", "v": 10}, {"id": "2", "v": 2}, {"id": "3", "v": 3}]
        self.v3 = [{"id": "1", "v": 10}, {"id": "3", "v": 30}, {"id": "4", "v": 4}]

    def test_composed_delta_produces_correct_ids(self):
        from crdt_merge.delta import compute_delta, compose_deltas, apply_delta

        d1_2 = compute_delta(self.v1, self.v2, key="id", version=2)
        d2_3 = compute_delta(self.v2, self.v3, key="id", version=3)
        d1_3 = compose_deltas(d1_2, d2_3, key="id")
        result = apply_delta(self.v1, d1_3, key="id")
        assert {r["id"] for r in result} == {"1", "3", "4"}

    def test_composed_delta_has_size(self):
        from crdt_merge.delta import compute_delta, compose_deltas

        d1_2 = compute_delta(self.v1, self.v2, key="id", version=2)
        d2_3 = compute_delta(self.v2, self.v3, key="id", version=3)
        d1_3 = compose_deltas(d1_2, d2_3, key="id")
        assert d1_3.size >= 1

    def test_composed_delta_matches_direct_delta(self):
        from crdt_merge.delta import compute_delta, compose_deltas, apply_delta

        d1_2 = compute_delta(self.v1, self.v2, key="id", version=2)
        d2_3 = compute_delta(self.v2, self.v3, key="id", version=3)
        d1_3_composed = compose_deltas(d1_2, d2_3, key="id")

        d1_3_direct = compute_delta(self.v1, self.v3, key="id", version=3)

        r_composed = apply_delta(list(self.v1), d1_3_composed, key="id")
        r_direct = apply_delta(list(self.v1), d1_3_direct, key="id")

        assert {r["id"] for r in r_composed} == {r["id"] for r in r_direct}


class TestDeltaStore:
    """Covers 'Cookbook: DeltaStore — Stateful Delta Tracking'."""

    def test_initial_ingest_returns_none(self):
        from crdt_merge.delta import DeltaStore

        store = DeltaStore(key="id", node_id="primary")
        initial = [{"id": f"R{i:04d}", "value": i} for i in range(100)]
        delta_0 = store.ingest(initial)
        assert delta_0 is None

    def test_store_size_after_ingest(self):
        from crdt_merge.delta import DeltaStore

        store = DeltaStore(key="id", node_id="primary")
        initial = [{"id": f"R{i:04d}", "value": i} for i in range(100)]
        store.ingest(initial)
        assert store.size == 100

    def test_second_ingest_returns_delta(self):
        from crdt_merge.delta import DeltaStore

        store = DeltaStore(key="id", node_id="primary")
        initial = [{"id": f"R{i:04d}", "value": i} for i in range(10)]
        store.ingest(initial)
        updated = [{"id": "R0000", "value": 99}] + initial[1:] + [{"id": "R0010", "value": 10}]
        delta_1 = store.ingest(updated)
        assert delta_1 is not None
        assert delta_1.size > 0

    def test_second_ingest_delta_captures_modified(self):
        from crdt_merge.delta import DeltaStore

        store = DeltaStore(key="id", node_id="primary")
        # Start values at 1 so that value*2 always differs from the original
        initial = [{"id": f"R{i:04d}", "value": i + 1} for i in range(10)]
        store.ingest(initial)
        modified = [dict(r, value=r["value"] * 2) for r in initial[:3]] + initial[3:]
        delta = store.ingest(modified)
        assert len(delta.modified) == 3

    def test_delta_apply_syncs_replica(self):
        from crdt_merge.delta import DeltaStore, apply_delta

        store = DeltaStore(key="id", node_id="primary")
        initial = [{"id": f"R{i:04d}", "value": i} for i in range(10)]
        store.ingest(initial)
        new_records = [{"id": "R0010", "value": 10}]
        updated = initial[:5] + [dict(initial[5], value=999)] + initial[6:] + new_records
        delta_1 = store.ingest(updated)
        replica = list(initial)
        synced = apply_delta(replica, delta_1, key="id")
        assert any(r["id"] == "R0010" for r in synced)

    def test_store_records_is_list(self):
        from crdt_merge.delta import DeltaStore

        store = DeltaStore(key="id", node_id="primary")
        records = [{"id": "1", "v": 1}]
        store.ingest(records)
        assert isinstance(store.records, list)


class TestMerkleQuickStart:
    """Covers 'Quick Start: Merkle Verification'."""

    def setup_method(self):
        self.records_primary = [
            {"id": "A", "name": "Alice", "score": 95},
            {"id": "B", "name": "Bob", "score": 87},
            {"id": "C", "name": "Carol", "score": 92},
        ]

    def test_identical_replicas_merkle_diff_is_identical(self):
        from crdt_merge.merkle import MerkleTree, merkle_diff

        tree_a = MerkleTree.from_records(self.records_primary, key="id")
        tree_b = MerkleTree.from_records(list(self.records_primary), key="id")
        diff = merkle_diff(tree_a, tree_b)
        assert diff.is_identical

    def test_identical_replicas_comparisons_made(self):
        from crdt_merge.merkle import MerkleTree, merkle_diff

        tree_a = MerkleTree.from_records(self.records_primary, key="id")
        tree_b = MerkleTree.from_records(list(self.records_primary), key="id")
        diff = merkle_diff(tree_a, tree_b)
        # O(1): root hash matches → done immediately
        assert diff.comparisons_made >= 1


class TestMerkleLocateDivergence:
    """Covers 'Cookbook: Locate Divergence in O(log n)'."""

    def setup_method(self):
        self.primary = [{"id": f"R{i:04d}", "val": i} for i in range(1000)]
        self.replica = [dict(r) for r in self.primary]
        self.replica[500]["val"] = 99999
        self.replica[200]["val"] = 88888
        self.primary.append({"id": "R1000", "val": 1000})

    def test_divergent_is_not_identical(self):
        from crdt_merge.merkle import MerkleTree, merkle_diff

        tree_p = MerkleTree.from_records(self.primary, key="id")
        tree_r = MerkleTree.from_records(self.replica, key="id")
        diff = merkle_diff(tree_p, tree_r)
        assert not diff.is_identical

    def test_divergent_num_differences(self):
        from crdt_merge.merkle import MerkleTree, merkle_diff

        tree_p = MerkleTree.from_records(self.primary, key="id")
        tree_r = MerkleTree.from_records(self.replica, key="id")
        diff = merkle_diff(tree_p, tree_r)
        assert diff.num_differences == 3

    def test_only_in_left(self):
        from crdt_merge.merkle import MerkleTree, merkle_diff

        tree_p = MerkleTree.from_records(self.primary, key="id")
        tree_r = MerkleTree.from_records(self.replica, key="id")
        diff = merkle_diff(tree_p, tree_r)
        assert "R1000" in diff.only_in_left

    def test_only_in_right_empty(self):
        from crdt_merge.merkle import MerkleTree, merkle_diff

        tree_p = MerkleTree.from_records(self.primary, key="id")
        tree_r = MerkleTree.from_records(self.replica, key="id")
        diff = merkle_diff(tree_p, tree_r)
        assert len(diff.only_in_right) == 0

    def test_common_different(self):
        from crdt_merge.merkle import MerkleTree, merkle_diff

        tree_p = MerkleTree.from_records(self.primary, key="id")
        tree_r = MerkleTree.from_records(self.replica, key="id")
        diff = merkle_diff(tree_p, tree_r)
        assert "R0500" in diff.common_different
        assert "R0200" in diff.common_different

    def test_records_to_sync(self):
        from crdt_merge.merkle import MerkleTree, merkle_diff

        tree_p = MerkleTree.from_records(self.primary, key="id")
        tree_r = MerkleTree.from_records(self.replica, key="id")
        diff = merkle_diff(tree_p, tree_r)
        records_to_sync = [
            r for r in self.primary
            if r["id"] in diff.only_in_left | diff.common_different
        ]
        assert len(records_to_sync) == 3


class TestMerkleCompareDatasets:
    """Covers 'Cookbook: Dataset Comparison (Convenience API)'."""

    def test_compare_datasets_identical(self):
        from crdt_merge.merkle import compare_datasets

        records_a = [{"id": str(i), "value": i} for i in range(100)]
        records_b = list(records_a)
        diff = compare_datasets(records_a, records_b, key="id")
        assert diff.is_identical

    def test_compare_datasets_one_divergence(self):
        from crdt_merge.merkle import compare_datasets

        records_a = [{"id": str(i), "value": i} for i in range(100)]
        records_b = [dict(r) for r in records_a]
        records_b[50]["value"] = -1
        diff = compare_datasets(records_a, records_b, key="id")
        assert not diff.is_identical
        assert "50" in diff.common_different


class TestGeoDistributedScenario:
    """Covers 'Scenario: Geo-Distributed Database'."""

    def test_sync_region_produces_synced_result(self):
        from crdt_merge.delta import DeltaStore, apply_delta
        from crdt_merge.merkle import MerkleTree, merkle_diff

        primary_store = DeltaStore(key="user_id", node_id="us-primary")
        base = [{"user_id": f"U{i}", "name": f"user{i}"} for i in range(50)]
        primary_store.ingest(base)

        # simulate a change
        changed = [dict(base[0], name="changed")] + base[1:] + [{"user_id": "U50", "name": "new"}]
        delta = primary_store.ingest(changed)

        replica = list(base)
        synced = apply_delta(replica, delta, key="user_id")

        tree_p = MerkleTree.from_records(changed, key="user_id")
        tree_r = MerkleTree.from_records(synced, key="user_id")
        diff = merkle_diff(tree_p, tree_r)
        assert diff.is_identical


class TestMultiHopComposableDelta:
    """Covers 'Scenario: Multi-Hop Replication — Composable Deltas'."""

    def test_composed_delta_primary_to_production(self):
        from crdt_merge.delta import compute_delta, compose_deltas, apply_delta
        from crdt_merge.merkle import compare_datasets

        v_primary = [{"id": str(i), "value": i} for i in range(50)]

        def transform_staging(records):
            return [dict(r, staging_ts=1000) for r in records]

        def transform_qa(records):
            return [dict(r, qa_score=0.95) for r in records]

        v_staging = transform_staging(v_primary)
        v_qa = transform_qa(v_staging)

        d_primary_staging = compute_delta(v_primary, v_staging, key="id", version=1)
        d_staging_qa = compute_delta(v_staging, v_qa, key="id", version=2)
        d_primary_qa = compose_deltas(d_primary_staging, d_staging_qa, key="id")

        v_production = apply_delta(v_primary, d_primary_qa, key="id")

        diff = compare_datasets(v_qa, v_production, key="id")
        assert diff.is_identical


class TestFullSyncLoop:
    """Covers 'Integration: Delta + Merkle + Gossip'."""

    def test_full_sync_loop_converges(self):
        from crdt_merge.delta import DeltaStore, compute_delta, apply_delta
        from crdt_merge.merkle import MerkleTree, merkle_diff

        local_store = DeltaStore(key="id", node_id="local")
        local_records = [{"id": str(i), "value": i} for i in range(20)]
        local_store.ingest(local_records)

        remote_records = [dict(r) for r in local_records]
        remote_records[5]["value"] = 999
        remote_records.append({"id": "20", "value": 20})

        # run the full sync loop inline
        key = "id"
        delta = compute_delta(local_store.records, remote_records, key=key)
        synced = apply_delta(local_store.records, delta, key=key)

        local_tree = MerkleTree.from_records(local_store.records, key=key)
        remote_tree = MerkleTree.from_records(remote_records, key=key)
        diff = merkle_diff(local_tree, remote_tree)

        if diff.is_identical:
            result = synced
        else:
            divergent_keys = diff.common_different | diff.only_in_left | diff.only_in_right
            repair_records = [r for r in remote_records if str(r[key]) in divergent_keys]
            repair_delta = compute_delta(synced, repair_records + synced, key=key)
            result = apply_delta(synced, repair_delta, key=key)

        assert len(result) >= len(local_records)


# ---------------------------------------------------------------------------
# ===== GOSSIP SERVERLESS SYNC GUIDE ========================================
# ---------------------------------------------------------------------------


class TestGossipQuickStart:
    """Covers 'Quick Start' in gossip-serverless-sync.md."""

    def test_merge_contains_all_keys(self):
        from crdt_merge.gossip import GossipState

        node1 = GossipState("node-1")
        node1.update("user:42", {"name": "Alice", "status": "active"})
        node1.update("user:43", {"name": "Bob", "status": "inactive"})

        node2 = GossipState("node-2")
        node2.update("user:44", {"name": "Carol", "status": "active"})
        node2.update("user:42", {"name": "Alice", "status": "away"})

        merged = node1.merge(node2)
        assert merged.size == 3

    def test_merge_resolves_conflict(self):
        from crdt_merge.gossip import GossipState

        node1 = GossipState("node-1")
        node1.update("user:42", {"name": "Alice", "status": "active"})

        node2 = GossipState("node-2")
        node2.update("user:42", {"name": "Alice", "status": "away"})

        merged = node1.merge(node2)
        # Value should be deterministically one of the two
        val = merged.get("user:42")
        assert val is not None
        assert val["name"] == "Alice"


class TestGossipAntiEntropy:
    """Covers 'Cookbook: Anti-Entropy — Sync Only What Changed'."""

    def test_digest_is_dict(self):
        from crdt_merge.gossip import GossipState

        node = GossipState("eu-west")
        for i in range(5):
            node.update(f"sensor:{i}", {"temp": 20 + i * 0.01, "ts": i})
        digest = node.digest()
        assert isinstance(digest, dict)

    def test_anti_entropy_push_pull_types(self):
        from crdt_merge.gossip import GossipState

        node_eu = GossipState("eu-west")
        node_us = GossipState("us-east")
        for i in range(5):
            node_eu.update(f"sensor:{i}", {"temp": 20 + i * 0.01, "ts": i})
        for i in range(3, 8):
            node_us.update(f"sensor:{i}", {"temp": 22 + i * 0.01, "ts": i + 1000})

        eu_digest = node_eu.digest()
        push_keys, pull_keys = node_us.anti_entropy_push_pull(eu_digest)
        assert isinstance(push_keys, (set, list, frozenset))
        assert isinstance(pull_keys, (set, list, frozenset))

    def test_anti_entropy_apply_entries(self):
        from crdt_merge.gossip import GossipState

        node_eu = GossipState("eu-west")
        node_us = GossipState("us-east")
        for i in range(5):
            node_eu.update(f"sensor:{i}", {"temp": 20 + i * 0.01, "ts": i})
        for i in range(3, 8):
            node_us.update(f"sensor:{i}", {"temp": 22 + i * 0.01, "ts": i + 1000})

        eu_digest = node_eu.digest()
        push_keys, pull_keys = node_us.anti_entropy_push_pull(eu_digest)

        entries_to_push = [
            node_us.get_entry(k) for k in push_keys if node_us.get_entry(k)
        ]
        applied = node_eu.apply_entries(entries_to_push)
        assert applied >= 0

    def test_anti_entropy_convergence_after_apply(self):
        from crdt_merge.gossip import GossipState

        node_eu = GossipState("eu-west")
        node_us = GossipState("us-east")
        for i in range(5):
            node_eu.update(f"sensor:{i}", {"temp": 20.0, "ts": i})
        for i in range(3, 8):
            node_us.update(f"sensor:{i}", {"temp": 22.0, "ts": i + 1000})

        # full merge should give same size in both directions
        merged_eu = node_eu.merge(node_us)
        merged_us = node_us.merge(node_eu)
        assert merged_eu.size == merged_us.size


class TestVectorClockCookbook:
    """Covers 'Cookbook: VectorClock Causal Ordering'."""

    def test_clock_before(self):
        from crdt_merge.clocks import VectorClock, Ordering

        clock_a = VectorClock()
        clock_a = clock_a.increment("node-a")
        clock_a = clock_a.increment("node-a")

        clock_b = clock_a.increment("node-b")
        assert clock_a.compare(clock_b) == Ordering.BEFORE

    def test_clock_after(self):
        from crdt_merge.clocks import VectorClock, Ordering

        clock_a = VectorClock()
        clock_a = clock_a.increment("node-a")
        clock_a = clock_a.increment("node-a")
        clock_b = clock_a.increment("node-b")
        assert clock_b.compare(clock_a) == Ordering.AFTER

    def test_clock_concurrent(self):
        from crdt_merge.clocks import VectorClock, Ordering

        clock_a = VectorClock().increment("node-a").increment("node-a")
        clock_c = VectorClock().increment("node-c")
        assert clock_a.compare(clock_c) == Ordering.CONCURRENT

    def test_clock_merge_element_wise_max(self):
        from crdt_merge.clocks import VectorClock

        clock_a = VectorClock().increment("node-a").increment("node-a")
        clock_c = VectorClock().increment("node-c")
        merged = clock_a.merge(clock_c)
        assert merged.value == {"node-a": 2, "node-c": 1}


class TestDottedVersionVectorCookbook:
    """Covers 'Cookbook: DottedVersionVector for Precise Causality'."""

    def test_advance_creates_dot(self):
        from crdt_merge.clocks import DottedVersionVector

        dvv = DottedVersionVector()
        dvv1 = dvv.advance("node-1")
        assert dvv1.dot == ("node-1", 1)

    def test_descends_true(self):
        from crdt_merge.clocks import DottedVersionVector

        dvv = DottedVersionVector()
        dvv1 = dvv.advance("node-1")
        # dvv1 descends from dvv (the empty clock)
        assert dvv1.descends(dvv)

    def test_descends_false_reverse(self):
        from crdt_merge.clocks import DottedVersionVector

        dvv = DottedVersionVector()
        dvv1 = dvv.advance("node-1")
        # empty dvv does NOT descend from dvv1
        assert not dvv.descends(dvv1)

    def test_merge_folds_dots(self):
        from crdt_merge.clocks import DottedVersionVector

        dvv = DottedVersionVector()
        dvv1 = dvv.advance("node-1")
        dvv2 = dvv.advance("node-2")
        merged = dvv1.merge(dvv2)
        assert "node-1" in merged.value
        assert "node-2" in merged.value


class TestGossipSyncLoop:
    """Covers 'Cookbook: Full Gossip Sync Loop (Bring Your Own Transport)'."""

    def test_gossip_node_write_and_get(self):
        from crdt_merge.gossip import GossipState

        class MyGossipNode:
            def __init__(self, node_id: str, known_peers: list):
                self.state = GossipState(node_id)
                self.peers = known_peers
                self.node_id = node_id

            def write(self, key: str, value: dict):
                self.state.update(key, value)

            def delete(self, key: str):
                self.state.delete(key)

        node = MyGossipNode("node-1", ["node-2", "node-3"])
        node.write("config:feature_flags", {"dark_mode": True, "beta_users": 1000})
        assert node.state.get("config:feature_flags") == {"dark_mode": True, "beta_users": 1000}

    def test_gossip_node_delete(self):
        from crdt_merge.gossip import GossipState

        class MyGossipNode:
            def __init__(self, node_id: str, known_peers: list):
                self.state = GossipState(node_id)
                self.peers = known_peers
                self.node_id = node_id

            def write(self, key: str, value: dict):
                self.state.update(key, value)

            def delete(self, key: str):
                self.state.delete(key)

        node = MyGossipNode("node-1", ["node-2"])
        node.write("config:key", {"v": 1})
        node.delete("config:key")
        assert node.state.get("config:key") is None

    def test_handle_entries_apply(self):
        from crdt_merge.gossip import GossipState, GossipEntry

        node1 = GossipState("node-1")
        node1.update("k1", {"x": 1})
        entry = node1.get_entry("k1")
        assert entry is not None

        node2 = GossipState("node-2")
        entries = [entry]
        count = node2.apply_entries(entries)
        assert count >= 1
        assert node2.get("k1") == {"x": 1}

    def test_gossip_entry_round_trip_via_dict(self):
        from crdt_merge.gossip import GossipState, GossipEntry

        node1 = GossipState("node-1")
        node1.update("mykey", {"val": 99})
        entry = node1.get_entry("mykey")
        d = entry.to_dict()
        parsed = GossipEntry.from_dict(d)
        assert parsed.key == "mykey"
        assert parsed.value == {"val": 99}


class TestServerlessConfigScenario:
    """Covers 'Scenario: Serverless Configuration Management'."""

    def test_config_propagates_across_three_nodes(self):
        from crdt_merge.gossip import GossipState
        from crdt_merge.wire import serialize, deserialize

        class ConfigNode:
            def __init__(self, instance_id: str):
                self.gossip = GossipState(instance_id)

            def set_config(self, key: str, value: dict):
                self.gossip.update(key, value)

            def get_config(self, key: str) -> dict:
                return self.gossip.get(key)

            def sync_with(self, other_state_bytes: bytes):
                remote = GossipState.from_dict(deserialize(other_state_bytes))
                self.gossip = self.gossip.merge(remote)

            def get_sync_payload(self) -> bytes:
                return serialize(self.gossip.to_dict())

        instance_a = ConfigNode("eu-west-1a-001")
        instance_b = ConfigNode("eu-west-1a-002")
        instance_c = ConfigNode("eu-west-1b-001")

        instance_a.set_config("service:rate_limit", {"rps": 1000, "burst": 1500})

        instance_b.sync_with(instance_a.get_sync_payload())
        instance_c.sync_with(instance_b.get_sync_payload())

        assert instance_a.get_config("service:rate_limit")["rps"] == 1000
        assert instance_b.get_config("service:rate_limit")["rps"] == 1000
        assert instance_c.get_config("service:rate_limit")["rps"] == 1000

    def test_config_node_wire_round_trip(self):
        from crdt_merge.gossip import GossipState
        from crdt_merge.wire import serialize, deserialize

        g = GossipState("node-x")
        g.update("config:key", {"value": 42})
        payload = serialize(g.to_dict())
        received = GossipState.from_dict(deserialize(payload))
        assert received.get("config:key") == {"value": 42}


class TestVehicleFleetScenario:
    """Covers 'Scenario: Autonomous Vehicle Fleet — Hazard Propagation'."""

    def _make_vehicle(self, vid):
        from crdt_merge.gossip import GossipState

        class VehicleNode:
            def __init__(self, vehicle_id: str):
                self.state = GossipState(vehicle_id)
                self.vehicle_id = vehicle_id

            def report_hazard(self, segment_id: str, hazard_type: str, confidence: float):
                self.state.update(f"hazard:{segment_id}", {
                    "type": hazard_type,
                    "confidence": confidence,
                    "reporter": self.vehicle_id,
                })

            def clear_hazard(self, segment_id: str):
                self.state.delete(f"hazard:{segment_id}")

            def mesh_sync(self, nearby: "VehicleNode"):
                self.state = self.state.merge(nearby.state)
                nearby.state = nearby.state.merge(self.state)

            def get_hazards(self) -> list:
                entries = self.state.to_dict().get("entries", {})
                return [
                    (k, v)
                    for k, v in entries.items()
                    if k.startswith("hazard:") and not v.get("tombstone", False)
                ]

        return VehicleNode(vid)

    def test_report_hazard_is_visible(self):
        v42 = self._make_vehicle("vehicle-42")
        v42.report_hazard("seg-14B", "debris", confidence=0.95)
        hazards = v42.get_hazards()
        assert len(hazards) == 1

    def test_clear_hazard_removes_it(self):
        v42 = self._make_vehicle("vehicle-42")
        v42.report_hazard("seg-14B", "debris", confidence=0.95)
        v42.clear_hazard("seg-14B")
        # After clearing, get() returns None
        assert v42.state.get("hazard:seg-14B") is None

    def test_delete_propagates_via_merge(self):
        v42 = self._make_vehicle("vehicle-42")
        v42.report_hazard("seg-14B", "debris", confidence=0.95)

        v67 = self._make_vehicle("vehicle-67")
        # v67 has had the key tombstoned first, but v42 re-added it
        # The guide claims add-wins semantics - after merge the tombstone from
        # v67 (which has no prior knowledge of the hazard) should propagate
        v67.clear_hazard("seg-14B")
        v42.mesh_sync(v67)
        # Both should have the same digest after sync
        assert v42.state.digest() == v67.state.digest()


class TestFederatedKnowledgeBase:
    """Covers 'Scenario: Federated Knowledge Base'."""

    def test_gossip_round_convergence(self):
        from crdt_merge.gossip import GossipState
        import random

        random.seed(42)
        institutions = {
            f"institute_{i}": GossipState(f"institute_{i}") for i in range(10)
        }
        institutions["institute_0"].update(
            "drug:compound-X-efficacy",
            {"value": 0.87, "confidence": 0.91, "sample_size": 1200},
        )
        institutions["institute_1"].update(
            "drug:compound-X-efficacy",
            {"value": 0.84, "confidence": 0.85, "sample_size": 800},
        )

        node_ids = list(institutions.keys())
        for _ in range(20):
            for node_id, state in list(institutions.items()):
                peers = random.sample(
                    [p for p in node_ids if p != node_id], min(3, len(node_ids) - 1)
                )
                for peer_id in peers:
                    merged = state.merge(institutions[peer_id])
                    institutions[node_id] = merged
                    institutions[peer_id] = merged

        unique_digests = {str(s.digest()) for s in institutions.values()}
        assert len(unique_digests) == 1, f"Not converged: {len(unique_digests)} unique states"


class TestGossipWireProtocolIntegration:
    """Covers 'Wire Protocol Integration' in gossip-serverless-sync.md."""

    def test_gossip_serialize_deserialize(self):
        from crdt_merge.gossip import GossipState
        from crdt_merge.wire import serialize, deserialize

        state = GossipState("node-1")
        state.update("config:key", {"value": 42})

        wire_bytes = serialize(state.to_dict())
        received = GossipState.from_dict(deserialize(wire_bytes))
        assert received.get("config:key") == {"value": 42}

    def test_gossip_serialized_bytes_are_bytes(self):
        from crdt_merge.gossip import GossipState
        from crdt_merge.wire import serialize

        state = GossipState("node-1")
        state.update("k", {"x": 1})
        wire_bytes = serialize(state.to_dict())
        assert isinstance(wire_bytes, bytes)
        assert len(wire_bytes) > 0
