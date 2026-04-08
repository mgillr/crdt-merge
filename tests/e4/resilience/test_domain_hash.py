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

"""Tests for domain-separated hashing (Whitfield §10)."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../source"))

from crdt_merge.e4.resilience.domain_hash import DomainSeparatedHasher, HashDomain


class TestDomainSeparatedHasher:
    def setup_method(self):
        self.hasher = DomainSeparatedHasher()

    def test_domain_hash_produces_32_bytes(self):
        result = self.hasher.domain_hash(HashDomain.MERKLE_ROOT, b"test")
        assert len(result) == 32

    def test_different_domains_produce_different_hashes(self):
        data = b"same data"
        h1 = self.hasher.domain_hash(HashDomain.MERKLE_ROOT, data)
        h2 = self.hasher.domain_hash(HashDomain.CLOCK_SNAPSHOT, data)
        h3 = self.hasher.domain_hash(HashDomain.TRUST_HASH, data)
        h4 = self.hasher.domain_hash(HashDomain.DELTA_BOUNDS, data)
        assert len({h1, h2, h3, h4}) == 4, "All domain hashes must differ"

    def test_aggregate_hash_deterministic(self):
        args = (b"merkle", b"clock", b"trust", b"bounds")
        h1 = self.hasher.aggregate_hash(*args)
        h2 = self.hasher.aggregate_hash(*args)
        assert h1 == h2

    def test_aggregate_changes_with_any_component(self):
        base = self.hasher.aggregate_hash(b"m", b"c", b"t", b"b")
        mod_merkle = self.hasher.aggregate_hash(b"X", b"c", b"t", b"b")
        mod_clock = self.hasher.aggregate_hash(b"m", b"X", b"t", b"b")
        mod_trust = self.hasher.aggregate_hash(b"m", b"c", b"X", b"b")
        mod_bounds = self.hasher.aggregate_hash(b"m", b"c", b"t", b"X")
        assert base != mod_merkle
        assert base != mod_clock
        assert base != mod_trust
        assert base != mod_bounds

    def test_verify_aggregate_passes(self):
        args = (b"m", b"c", b"t", b"b")
        expected = self.hasher.aggregate_hash(*args)
        assert self.hasher.verify_aggregate(expected, *args)

    def test_verify_aggregate_fails_on_tamper(self):
        args = (b"m", b"c", b"t", b"b")
        expected = self.hasher.aggregate_hash(*args)
        assert not self.hasher.verify_aggregate(expected, b"X", b"c", b"t", b"b")

    def test_epoch_scoped_hash(self):
        h1 = self.hasher.epoch_scoped_hash(1, b"data")
        h2 = self.hasher.epoch_scoped_hash(2, b"data")
        assert h1 != h2, "Different epochs must produce different hashes"

    def test_hex_output(self):
        result = self.hasher.aggregate_hash_hex(b"m", b"c", b"t", b"b")
        assert len(result) == 64  # hex-encoded 32 bytes

    def test_constant_time_compare_equal(self):
        from crdt_merge.e4.resilience.domain_hash import _constant_time_compare
        assert _constant_time_compare(b"abc", b"abc")

    def test_constant_time_compare_different(self):
        from crdt_merge.e4.resilience.domain_hash import _constant_time_compare
        assert not _constant_time_compare(b"abc", b"xyz")

    def test_constant_time_compare_different_lengths(self):
        from crdt_merge.e4.resilience.domain_hash import _constant_time_compare
        assert not _constant_time_compare(b"ab", b"abc")
