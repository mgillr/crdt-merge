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

"""Tests for TLA+ formal specification generator."""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../source"))

from crdt_merge.e4.resilience.formal_spec import (
    E4FormalSpec,
    PropertyVerifier,
    SpecBounds,
    TemporalProperty,
    VerificationResult,
)


class TestSpecBounds:

    def test_defaults(self):
        b = SpecBounds()
        assert b.state_space_estimate() > 0

    def test_custom_bounds(self):
        b = SpecBounds(max_peers=5, max_ops=10)
        est = b.state_space_estimate()
        b2 = SpecBounds(max_peers=10, max_ops=20)
        assert b2.state_space_estimate() > est


class TestE4FormalSpec:

    def test_generate(self):
        spec = E4FormalSpec()
        tla = spec.generate()
        assert "MODULE" in tla or "----" in tla
        assert len(tla) > 100

    def test_generate_cfg(self):
        spec = E4FormalSpec()
        cfg = spec.generate_cfg()
        assert len(cfg) > 0

    def test_properties(self):
        spec = E4FormalSpec()
        props = spec.properties
        assert len(props) > 0
        assert all(isinstance(p, TemporalProperty) for p in props)

    def test_bounds_accessible(self):
        spec = E4FormalSpec()
        assert isinstance(spec.bounds, SpecBounds)

    def test_custom_bounds(self):
        bounds = SpecBounds(max_peers=4, max_ops=8)
        spec = E4FormalSpec(bounds=bounds)
        assert spec.bounds.max_peers == 4

    def test_spec_has_variables(self):
        tla = E4FormalSpec().generate()
        assert "VARIABLE" in tla or "variable" in tla.lower()

    def test_spec_has_init(self):
        tla = E4FormalSpec().generate()
        assert "Init" in tla

    def test_spec_has_next(self):
        tla = E4FormalSpec().generate()
        assert "Next" in tla

    def test_repr(self):
        spec = E4FormalSpec()
        r = repr(spec)
        assert len(r) > 0


class TestPropertyVerifier:

    def test_verify_convergence(self):
        v = PropertyVerifier(max_peers=3, max_ops=3)
        result = v.verify_convergence(trials=100)
        assert isinstance(result, VerificationResult)
        assert result.passed is True

    def test_verify_idempotence(self):
        v = PropertyVerifier(max_peers=3, max_ops=3)
        result = v.verify_idempotence(trials=100)
        assert isinstance(result, VerificationResult)
        assert result.passed is True

    def test_verify_commutativity(self):
        v = PropertyVerifier(max_peers=3, max_ops=3)
        result = v.verify_commutativity(trials=100)
        assert isinstance(result, VerificationResult)
        assert result.passed is True

    def test_verify_trust_monotonicity(self):
        v = PropertyVerifier(max_peers=3, max_ops=3)
        result = v.verify_trust_monotonicity(trials=100)
        assert isinstance(result, VerificationResult)
