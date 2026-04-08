# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-04-08
# Change License: Apache License, Version 2.0

"""Tests for trust inheritance manager."""

import time
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../source"))

from crdt_merge.e4.resilience.trust_inheritance import (
    TrustInheritanceManager,
    VouchRecord,
    DeviceCluster,
    TrustResolution,
)


class TestVouchRecord:

    def test_create(self):
        v = VouchRecord(
            institution_id="mit",
            device_ids={"dev-1", "dev-2"},
            trust_ceiling=0.8,
            dimensions=(0.8, 0.7, 0.9, 0.6, 0.8),
            timestamp=time.time(),
        )
        assert v.covers("dev-1")
        assert not v.covers("dev-999")

    def test_content_hash(self):
        v = VouchRecord(
            institution_id="eth",
            device_ids={"d1"},
            trust_ceiling=0.9,
            dimensions=(0.9,) * 5,
            timestamp=1000.0,
        )
        h = v.content_hash()
        assert len(h) > 0


class TestDeviceCluster:

    def test_add_members(self):
        c = DeviceCluster(cluster_id="cluster-1")
        c.add_member("dev-1", trust=0.7)
        c.add_member("dev-2", trust=0.8)
        assert c.size() == 2

    def test_median_trust(self):
        c = DeviceCluster(cluster_id="c1")
        c.add_member("a", trust=0.6)
        c.add_member("b", trust=0.8)
        c.add_member("c", trust=0.9)
        assert abs(c.median_trust() - 0.8) < 0.01

    def test_update_trust(self):
        c = DeviceCluster(cluster_id="c1")
        c.add_member("a", trust=0.5)
        c.update_trust("a", 0.9)
        assert abs(c.median_trust() - 0.9) < 0.01


class TestTrustInheritanceManager:

    def test_init(self):
        mgr = TrustInheritanceManager()
        assert mgr.vouch_count == 0
        assert mgr.cluster_count == 0

    def test_register_institution(self):
        mgr = TrustInheritanceManager()
        mgr.register_institution("mit", trust=0.95)

    def test_submit_vouch(self):
        mgr = TrustInheritanceManager()
        mgr.register_institution("mit", trust=0.95)
        vouch = VouchRecord(
            institution_id="mit",
            device_ids={"dev-1"},
            trust_ceiling=0.8,
            dimensions=(0.8,) * 5,
            timestamp=time.time(),
        )
        result = mgr.submit_vouch(vouch)
        assert result is True
        assert mgr.vouch_count >= 1

    def test_resolve_trust_with_vouch(self):
        mgr = TrustInheritanceManager()
        mgr.register_institution("mit", trust=0.95)
        vouch = VouchRecord(
            institution_id="mit",
            device_ids={"dev-1"},
            trust_ceiling=0.8,
            dimensions=(0.8,) * 5,
            timestamp=time.time(),
        )
        mgr.submit_vouch(vouch)
        resolution = mgr.resolve_trust("dev-1", individual_trust=0.3)
        assert isinstance(resolution, TrustResolution)
        # With institutional vouch, effective trust should be higher
        assert resolution.effective_trust > 0.3

    def test_resolve_trust_no_vouch(self):
        mgr = TrustInheritanceManager()
        resolution = mgr.resolve_trust("unknown-dev", individual_trust=0.2)
        assert isinstance(resolution, TrustResolution)
        # Without vouch, should fall back to individual or base
        assert resolution.effective_trust >= 0.0

    def test_cluster_trust(self):
        mgr = TrustInheritanceManager()
        cluster = DeviceCluster(cluster_id="cl-1")
        cluster.add_member("dev-1", trust=0.7)
        cluster.add_member("dev-2", trust=0.8)
        mgr.register_cluster(cluster)
        mgr.assign_to_cluster("dev-1", "cl-1")
        assert mgr.cluster_count >= 1

    def test_merge_vouches(self):
        mgr = TrustInheritanceManager()
        mgr.register_institution("mit", trust=0.9)
        vouch = VouchRecord(
            institution_id="mit",
            device_ids={"dev-1"},
            trust_ceiling=0.7,
            dimensions=(0.7,) * 5,
            timestamp=time.time(),
        )
        remote_vouches = {"mit": [vouch]}
        mgr.merge_vouches(remote_vouches)
        assert mgr.vouch_count >= 1

    def test_repr(self):
        mgr = TrustInheritanceManager()
        assert "TrustInheritanceManager" in repr(mgr)
