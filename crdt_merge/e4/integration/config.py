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

"""Runtime configuration for the E4 architecture.

Centralises every tunable threshold and parameter so that production
deployments can override defaults without touching module internals.
All values match the specification defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class E4Config:
    """Unified runtime configuration for the E4 subsystem.

    Attributes are grouped by the component they control.  Every field
    has a sensible default matching the specification.
    """

    # -- trust thresholds (ref 896-899) ------------------------------------
    probation_trust: float = 0.5
    quarantine_threshold: float = 0.1
    low_trust_threshold: float = 0.4
    partial_trust_threshold: float = 0.8

    # -- circuit breaker (ref 829) -----------------------------------------
    cb_window_size: int = 100
    cb_sigma_threshold: float = 2.0
    cb_cooldown_seconds: float = 30.0
    cb_min_samples: int = 10

    # -- Merkle tree (ref 850) --------------------------------------------
    merkle_branching_factor: int = 256

    # -- compatibility (ref 855) -------------------------------------------
    compatibility_mode: str = "e4_only"

    # -- adaptive verification (ref 895) -----------------------------------
    verification_level_override: Optional[int] = None
    async_queue_limit: int = 1024

    # -- homeostasis (ref 828) ---------------------------------------------
    homeostasis_enabled: bool = True
    homeostasis_target_budget: Optional[float] = None

    # -- delta management --------------------------------------------------
    delta_max_history: int = 64

    # -- gossip bridge -----------------------------------------------------
    gossip_include_trust_deltas: bool = True

    # -- stream bridge -----------------------------------------------------
    stream_per_chunk_validation: bool = True
    stream_min_trust: float = 0.1

    # -- agent bridge ------------------------------------------------------
    agent_trust_weight_context: bool = True

    # -- helpers -----------------------------------------------------------

    def trust_thresholds(self) -> dict:
        """Return trust thresholds as a plain dict."""
        return {
            "probation": self.probation_trust,
            "quarantine": self.quarantine_threshold,
            "low": self.low_trust_threshold,
            "partial": self.partial_trust_threshold,
        }


# -- Singleton-ish default config ------------------------------------------

_default_config: Optional[E4Config] = None


def get_config() -> E4Config:
    """Return the current global E4 config, creating one if needed."""
    global _default_config
    if _default_config is None:
        _default_config = E4Config()
    return _default_config


def set_config(config: E4Config) -> None:
    """Replace the global E4 config."""
    global _default_config
    _default_config = config


def reset_config() -> None:
    """Reset to factory defaults."""
    global _default_config
    _default_config = None
