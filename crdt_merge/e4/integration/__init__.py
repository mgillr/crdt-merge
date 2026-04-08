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

"""E4 integration package -- system-wide bridges and bootstrap.

This package wires the E4 subsystem into the broader crdt-merge
framework via constructor injection with sensible defaults.

The ``initialize_defaults()`` function is the **single entry point**
called by the one-line import at the bottom of ``crdt_merge/__init__.py``:

    from crdt_merge.e4 import initialize_defaults; initialize_defaults()

It constructs default E4 component instances and registers them as
the default values used by constructor injection throughout the
framework.  Tests bypass this by supplying their own instances.
"""

from __future__ import annotations

from typing import Optional

from crdt_merge.e4.integration.config import E4Config, get_config, set_config


# -- Component registry (populated by initialize_defaults) -----------------

_initialized: bool = False

_default_trust_lattice: Optional[object] = None
_default_circuit_breaker: Optional[object] = None
_default_verifier: Optional[object] = None
_default_gossip_engine: Optional[object] = None
_default_stream_merge: Optional[object] = None
_default_agent_state: Optional[object] = None
_default_compat_controller: Optional[object] = None


def initialize_defaults(config: Optional[E4Config] = None) -> None:
    """Bootstrap the E4 subsystem with default component instances.

    Calling this function is idempotent -- repeated calls are no-ops
    unless *config* differs from the current active configuration.

    Parameters
    ----------
    config :
        Optional override for the runtime configuration.  When ``None``,
        the factory-default ``E4Config()`` is used.
    """
    global _initialized
    global _default_trust_lattice, _default_circuit_breaker
    global _default_verifier, _default_gossip_engine
    global _default_stream_merge, _default_agent_state
    global _default_compat_controller

    if _initialized and config is None:
        return

    cfg = config or get_config()
    set_config(cfg)

    # -- import components lazily to avoid circular import issues -----------
    from crdt_merge.e4.delta_trust_lattice import (
        DeltaTrustLattice,
        TrustCircuitBreaker,
    )
    from crdt_merge.e4.typed_trust import TrustHomeostasis
    from crdt_merge.e4.adaptive_verification import (
        AdaptiveVerificationController,
    )
    from crdt_merge.e4.compatibility import (
        CompatibilityController,
        CompatibilityMode,
    )
    from crdt_merge.e4.integration.gossip_bridge import TrustGossipEngine
    from crdt_merge.e4.integration.stream_bridge import TrustStreamMerge
    from crdt_merge.e4.integration.agent_bridge import TrustAgentState

    # -- circuit breaker ---------------------------------------------------
    circuit_breaker = TrustCircuitBreaker(
        window_size=cfg.cb_window_size,
        sigma_threshold=cfg.cb_sigma_threshold,
        cooldown_seconds=cfg.cb_cooldown_seconds,
        min_samples=cfg.cb_min_samples,
    )
    _default_circuit_breaker = circuit_breaker

    # -- homeostasis -------------------------------------------------------
    homeostasis = TrustHomeostasis() if cfg.homeostasis_enabled else None

    # -- trust lattice (E4 core) -------------------------------------------
    lattice = DeltaTrustLattice(
        peer_id="local",
        circuit_breaker=circuit_breaker,
        homeostasis=homeostasis,
    )
    _default_trust_lattice = lattice

    # -- adaptive verification ---------------------------------------------
    verifier = AdaptiveVerificationController(
        trust_lattice=lattice,
        circuit_breaker=circuit_breaker,
        async_queue_limit=cfg.async_queue_limit,
    )
    _default_verifier = verifier

    # -- compatibility controller ------------------------------------------
    mode_map = {
        "e4_only": CompatibilityMode.E4_ONLY,
        "dual_hash": CompatibilityMode.DUAL_HASH,
        "legacy_only": CompatibilityMode.LEGACY_ONLY,
    }
    compat_mode = mode_map.get(cfg.compatibility_mode, CompatibilityMode.E4_ONLY)
    _default_compat_controller = CompatibilityController(
        default_mode=compat_mode,
    )

    # -- gossip bridge -----------------------------------------------------
    _default_gossip_engine = TrustGossipEngine(
        trust_lattice=lattice,
        verifier=verifier,
    )

    # -- stream bridge -----------------------------------------------------
    _default_stream_merge = TrustStreamMerge(
        verifier=verifier,
        min_trust=cfg.stream_min_trust,
    )

    # -- agent bridge ------------------------------------------------------
    _default_agent_state = TrustAgentState(
        trust_lattice=lattice,
        trust_weight_context=cfg.agent_trust_weight_context,
    )

    _initialized = True


# -- Accessors for the default component instances -------------------------

def get_trust_lattice() -> object:
    _ensure_init()
    return _default_trust_lattice  # type: ignore[return-value]


def get_circuit_breaker() -> object:
    _ensure_init()
    return _default_circuit_breaker  # type: ignore[return-value]


def get_verifier() -> object:
    _ensure_init()
    return _default_verifier  # type: ignore[return-value]


def get_gossip_engine() -> object:
    _ensure_init()
    return _default_gossip_engine  # type: ignore[return-value]


def get_stream_merge() -> object:
    _ensure_init()
    return _default_stream_merge  # type: ignore[return-value]


def get_agent_state() -> object:
    _ensure_init()
    return _default_agent_state  # type: ignore[return-value]


def get_compat_controller() -> object:
    _ensure_init()
    return _default_compat_controller  # type: ignore[return-value]


def is_initialized() -> bool:
    return _initialized


def reset() -> None:
    """Tear down the default instances (used in tests)."""
    global _initialized
    global _default_trust_lattice, _default_circuit_breaker
    global _default_verifier, _default_gossip_engine
    global _default_stream_merge, _default_agent_state
    global _default_compat_controller

    _initialized = False
    _default_trust_lattice = None
    _default_circuit_breaker = None
    _default_verifier = None
    _default_gossip_engine = None
    _default_stream_merge = None
    _default_agent_state = None
    _default_compat_controller = None


# -- internal --------------------------------------------------------------

def _ensure_init() -> None:
    if not _initialized:
        initialize_defaults()
