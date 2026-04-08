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

"""Tests for E4SystemIntegration (integration/__init__.py).

Covers bootstrap, registration, system-wide activation, component accessors,
idempotent initialization, and reset.
"""

import pytest

from crdt_merge.e4.integration import (
    initialize_defaults,
    get_trust_lattice,
    get_circuit_breaker,
    get_verifier,
    get_gossip_engine,
    get_stream_merge,
    get_agent_state,
    get_compat_controller,
    is_initialized,
    reset,
)
from crdt_merge.e4.integration.config import E4Config, reset_config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_state():
    """Reset E4 system before and after each test."""
    reset()
    reset_config()
    yield
    reset()
    reset_config()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInitializeDefaults:

    def test_initialize_sets_flag(self):
        """initialize_defaults sets is_initialized to True."""
        assert is_initialized() is False
        initialize_defaults()
        assert is_initialized() is True

    def test_idempotent(self):
        """Repeated calls are idempotent (no-op on second call)."""
        initialize_defaults()
        lattice1 = get_trust_lattice()
        initialize_defaults()
        lattice2 = get_trust_lattice()
        assert lattice1 is lattice2

    def test_with_custom_config(self):
        """Custom config overrides defaults."""
        cfg = E4Config(probation_trust=0.3, merkle_branching_factor=64)
        initialize_defaults(config=cfg)
        assert is_initialized() is True

    def test_reinitialize_with_config(self):
        """Passing a new config forces re-initialization."""
        initialize_defaults()
        lattice1 = get_trust_lattice()
        cfg = E4Config(probation_trust=0.9)
        initialize_defaults(config=cfg)
        lattice2 = get_trust_lattice()
        # Lattice is rebuilt with new config
        assert lattice2 is not lattice1


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:

    def test_reset_clears_flag(self):
        """reset sets is_initialized back to False."""
        initialize_defaults()
        assert is_initialized() is True
        reset()
        assert is_initialized() is False

    def test_reset_clears_all_components(self):
        """After reset, accessors re-initialize on next call."""
        initialize_defaults()
        old_lattice = get_trust_lattice()
        reset()
        # Next call triggers fresh init
        new_lattice = get_trust_lattice()
        assert new_lattice is not old_lattice


# ---------------------------------------------------------------------------
# Component accessors
# ---------------------------------------------------------------------------

class TestComponentAccessors:

    def test_get_trust_lattice(self):
        """get_trust_lattice returns a DeltaTrustLattice."""
        initialize_defaults()
        lattice = get_trust_lattice()
        assert hasattr(lattice, "get_trust")
        assert hasattr(lattice, "peer_id")

    def test_get_circuit_breaker(self):
        """get_circuit_breaker returns a TrustCircuitBreaker."""
        initialize_defaults()
        cb = get_circuit_breaker()
        assert hasattr(cb, "is_tripped")
        assert hasattr(cb, "reset")

    def test_get_verifier(self):
        """get_verifier returns an AdaptiveVerificationController."""
        initialize_defaults()
        v = get_verifier()
        assert hasattr(v, "verify")
        assert hasattr(v, "run_async_followup")

    def test_get_gossip_engine(self):
        """get_gossip_engine returns a TrustGossipEngine."""
        initialize_defaults()
        ge = get_gossip_engine()
        assert hasattr(ge, "prepare_sync")
        assert hasattr(ge, "receive_sync")

    def test_get_stream_merge(self):
        """get_stream_merge returns a TrustStreamMerge."""
        initialize_defaults()
        sm = get_stream_merge()
        assert hasattr(sm, "validate_chunk")
        assert hasattr(sm, "validate_stream")

    def test_get_agent_state(self):
        """get_agent_state returns a TrustAgentState."""
        initialize_defaults()
        as_ = get_agent_state()
        assert hasattr(as_, "put")
        assert hasattr(as_, "get")
        assert hasattr(as_, "merge_context")

    def test_get_compat_controller(self):
        """get_compat_controller returns a CompatibilityController."""
        initialize_defaults()
        cc = get_compat_controller()
        assert hasattr(cc, "default_mode")


# ---------------------------------------------------------------------------
# Auto-init via accessors
# ---------------------------------------------------------------------------

class TestAutoInit:

    def test_accessor_triggers_init(self):
        """Calling an accessor when not initialized triggers init."""
        assert is_initialized() is False
        lattice = get_trust_lattice()
        assert is_initialized() is True
        assert lattice is not None

    def test_verifier_auto_init(self):
        """get_verifier auto-initializes the system."""
        v = get_verifier()
        assert is_initialized() is True
        assert v is not None


# ---------------------------------------------------------------------------
# Config-driven behavior
# ---------------------------------------------------------------------------

class TestConfigDrivenBehavior:

    def test_compatibility_mode_dual_hash(self):
        """Setting compatibility_mode=dual_hash creates dual-hash controller."""
        cfg = E4Config(compatibility_mode="dual_hash")
        initialize_defaults(config=cfg)
        cc = get_compat_controller()
        assert cc is not None
