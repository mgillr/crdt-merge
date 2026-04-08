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

"""Tests for E4Config: defaults, override, validation, and singleton helpers.

Covers the runtime configuration dataclass and the get/set/reset module-level
config management functions.
"""

import pytest

from crdt_merge.e4.integration.config import (
    E4Config,
    get_config,
    set_config,
    reset_config,
)


# ---------------------------------------------------------------------------
# E4Config defaults
# ---------------------------------------------------------------------------

class TestE4ConfigDefaults:

    def test_probation_trust_default(self):
        """Default probation_trust is 0.5."""
        cfg = E4Config()
        assert cfg.probation_trust == 0.5

    def test_quarantine_threshold_default(self):
        """Default quarantine_threshold is 0.1."""
        cfg = E4Config()
        assert cfg.quarantine_threshold == 0.1

    def test_low_trust_threshold_default(self):
        """Default low_trust_threshold is 0.4."""
        cfg = E4Config()
        assert cfg.low_trust_threshold == 0.4

    def test_partial_trust_threshold_default(self):
        """Default partial_trust_threshold is 0.8."""
        cfg = E4Config()
        assert cfg.partial_trust_threshold == 0.8

    def test_cb_window_size_default(self):
        """Default cb_window_size is 100."""
        cfg = E4Config()
        assert cfg.cb_window_size == 100

    def test_cb_sigma_threshold_default(self):
        """Default cb_sigma_threshold is 2.0."""
        cfg = E4Config()
        assert cfg.cb_sigma_threshold == 2.0

    def test_cb_cooldown_seconds_default(self):
        """Default cb_cooldown_seconds is 30.0."""
        cfg = E4Config()
        assert cfg.cb_cooldown_seconds == 30.0

    def test_cb_min_samples_default(self):
        """Default cb_min_samples is 10."""
        cfg = E4Config()
        assert cfg.cb_min_samples == 10

    def test_merkle_branching_factor_default(self):
        """Default merkle_branching_factor is 256."""
        cfg = E4Config()
        assert cfg.merkle_branching_factor == 256

    def test_compatibility_mode_default(self):
        """Default compatibility_mode is 'e4_only'."""
        cfg = E4Config()
        assert cfg.compatibility_mode == "e4_only"

    def test_verification_level_override_default(self):
        """Default verification_level_override is None."""
        cfg = E4Config()
        assert cfg.verification_level_override is None

    def test_async_queue_limit_default(self):
        """Default async_queue_limit is 1024."""
        cfg = E4Config()
        assert cfg.async_queue_limit == 1024

    def test_homeostasis_enabled_default(self):
        """Default homeostasis_enabled is True."""
        cfg = E4Config()
        assert cfg.homeostasis_enabled is True

    def test_delta_max_history_default(self):
        """Default delta_max_history is 64."""
        cfg = E4Config()
        assert cfg.delta_max_history == 64


# ---------------------------------------------------------------------------
# E4Config overrides
# ---------------------------------------------------------------------------

class TestE4ConfigOverride:

    def test_override_probation_trust(self):
        """Override probation_trust at construction."""
        cfg = E4Config(probation_trust=0.3)
        assert cfg.probation_trust == 0.3

    def test_override_merkle_branching_factor(self):
        """Override merkle_branching_factor."""
        cfg = E4Config(merkle_branching_factor=64)
        assert cfg.merkle_branching_factor == 64

    def test_override_compatibility_mode(self):
        """Override compatibility_mode."""
        cfg = E4Config(compatibility_mode="dual_hash")
        assert cfg.compatibility_mode == "dual_hash"

    def test_override_gossip_include_trust_deltas(self):
        """Override gossip_include_trust_deltas."""
        cfg = E4Config(gossip_include_trust_deltas=False)
        assert cfg.gossip_include_trust_deltas is False

    def test_override_stream_per_chunk_validation(self):
        """Override stream_per_chunk_validation."""
        cfg = E4Config(stream_per_chunk_validation=False)
        assert cfg.stream_per_chunk_validation is False


# ---------------------------------------------------------------------------
# trust_thresholds helper
# ---------------------------------------------------------------------------

class TestTrustThresholds:

    def test_trust_thresholds_returns_dict(self):
        """trust_thresholds() returns a plain dict."""
        cfg = E4Config()
        thresholds = cfg.trust_thresholds()
        assert isinstance(thresholds, dict)

    def test_trust_thresholds_keys(self):
        """trust_thresholds() has probation, quarantine, low, partial."""
        cfg = E4Config()
        thresholds = cfg.trust_thresholds()
        assert set(thresholds.keys()) == {"probation", "quarantine", "low", "partial"}

    def test_trust_thresholds_values(self):
        """trust_thresholds() values match the config fields."""
        cfg = E4Config(probation_trust=0.6, quarantine_threshold=0.2)
        thresholds = cfg.trust_thresholds()
        assert thresholds["probation"] == 0.6
        assert thresholds["quarantine"] == 0.2


# ---------------------------------------------------------------------------
# get_config / set_config / reset_config
# ---------------------------------------------------------------------------

class TestConfigSingleton:

    def setup_method(self):
        """Reset config before each test."""
        reset_config()

    def teardown_method(self):
        """Reset config after each test."""
        reset_config()

    def test_get_config_creates_default(self):
        """get_config() creates a default E4Config if not set."""
        cfg = get_config()
        assert isinstance(cfg, E4Config)
        assert cfg.probation_trust == 0.5

    def test_set_config_overrides(self):
        """set_config() replaces the global config."""
        custom = E4Config(probation_trust=0.9)
        set_config(custom)
        assert get_config().probation_trust == 0.9

    def test_reset_config(self):
        """reset_config() returns to factory defaults."""
        set_config(E4Config(probation_trust=0.1))
        reset_config()
        cfg = get_config()
        assert cfg.probation_trust == 0.5

    def test_get_config_stable(self):
        """Repeated get_config() calls return the same instance."""
        cfg1 = get_config()
        cfg2 = get_config()
        assert cfg1 is cfg2
