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

"""E4 Hardening Package — Peer Review Concern Resolution.

Addresses all 24 concerns raised by the independent peer review review
plus 25 concerns from the alternate panel.  Every module is additive and
non-breaking — existing APIs, imports, and test suites remain unchanged.

Round 1 modules (original panel):
  domain_hash, key_manager, epoch_protocol, convergence_monitor,
  trust_resilience, semantic_validator, delta_validation, performance_spec.

Round 2 modules (alternate panel):
  formal_spec, longcon_sybil, pq_signatures, noniid_convergence,
  trust_inheritance, gossip_budget, deterministic_merge,
  strategy_drift, partition_reconciler, schema_adapter.
"""

# -- Round 1 ---------------------------------------------------------------

from crdt_merge.e4.resilience.domain_hash import (
    DomainSeparatedHasher,
    HashDomain,
)
from crdt_merge.e4.resilience.key_manager import (
    KeyManager,
    KeyPair,
    PeerKeyRegistry,
    RevocationEntry,
)
from crdt_merge.e4.resilience.epoch_protocol import (
    EpochManager,
    EpochState,
    EpochTransition,
)
from crdt_merge.e4.resilience.convergence_monitor import (
    ConvergenceBound,
    ConvergenceMonitor,
)
from crdt_merge.e4.resilience.trust_resilience import (
    TrustPrivacyFilter,
    ByzantineThresholdAnalyzer,
    ColdStartBootstrap,
    ExtendedDimensionRegistry,
)
from crdt_merge.e4.resilience.semantic_validator import (
    SemanticValidator,
    MagnitudeValidator,
    StatisticalShiftDetector,
    ParameterRegionGuard,
    CompositeSemanticValidator,
)
from crdt_merge.e4.resilience.delta_validation import (
    ReanchorPolicy,
    DeltaCompositionSpec,
    ParameterTypeEncoder,
    ParameterType,
    CommutativityAdapter,
)
from crdt_merge.e4.resilience.performance_spec import (
    SketchConfig,
    FanoutOptimizer,
    ProductionDeratingSpec,
    HardwareRequirements,
)

# -- Round 2 ---------------------------------------------------------------

from crdt_merge.e4.resilience.formal_spec import (
    E4FormalSpec,
    PropertyVerifier,
    SpecBounds,
    TemporalProperty,
)
from crdt_merge.e4.resilience.longcon_sybil import (
    LongConDetector,
    LongConConfig,
    SybilAlert,
)
from crdt_merge.e4.resilience.pq_signatures import (
    HmacScheme,
    DilithiumLite,
    HybridScheme,
    register_scheme,
    get_scheme,
    available_schemes,
)
from crdt_merge.e4.resilience.noniid_convergence import (
    TrustConvergenceAnalyser,
    HeterogeneityProfile,
    WarmupSchedule,
)
from crdt_merge.e4.resilience.trust_inheritance import (
    TrustInheritanceManager,
    VouchRecord,
    DeviceCluster,
)
from crdt_merge.e4.resilience.gossip_budget import (
    HierarchicalAggregator,
    SparseTrustDelta,
    AdaptiveGossipRate,
    estimate_bandwidth,
)
from crdt_merge.e4.resilience.deterministic_merge import (
    DeterministicMerge,
    deterministic_sum,
)
from crdt_merge.e4.resilience.strategy_drift import (
    StrategyDriftDiscriminator,
    DriftVerdict,
)
from crdt_merge.e4.resilience.partition_reconciler import PartitionReconciler
from crdt_merge.e4.resilience.schema_adapter import (
    SchemaDescriptor,
    SchemaAligner,
    SchemaRegistry,
    ResultNormaliser,
)

__all__ = [
    # Round 1
    "DomainSeparatedHasher", "HashDomain",
    "KeyManager", "KeyPair", "PeerKeyRegistry", "RevocationEntry",
    "EpochManager", "EpochState", "EpochTransition",
    "ConvergenceBound", "ConvergenceMonitor",
    "TrustPrivacyFilter", "ByzantineThresholdAnalyzer",
    "ColdStartBootstrap", "ExtendedDimensionRegistry",
    "SemanticValidator", "MagnitudeValidator",
    "StatisticalShiftDetector", "ParameterRegionGuard",
    "CompositeSemanticValidator",
    "ReanchorPolicy", "DeltaCompositionSpec",
    "ParameterTypeEncoder", "ParameterType", "CommutativityAdapter",
    "SketchConfig", "FanoutOptimizer",
    "ProductionDeratingSpec", "HardwareRequirements",
    # Round 2
    "E4FormalSpec", "PropertyVerifier", "SpecBounds", "TemporalProperty",
    "LongConDetector", "LongConConfig", "SybilAlert",
    "HmacScheme", "DilithiumLite", "HybridScheme",
    "register_scheme", "get_scheme", "available_schemes",
    "TrustConvergenceAnalyser", "HeterogeneityProfile", "WarmupSchedule",
    "TrustInheritanceManager", "VouchRecord", "DeviceCluster",
    "HierarchicalAggregator", "SparseTrustDelta",
    "AdaptiveGossipRate", "estimate_bandwidth",
    "DeterministicMerge", "deterministic_sum",
    "StrategyDriftDiscriminator", "DriftVerdict",
    "PartitionReconciler",
    "SchemaDescriptor", "SchemaAligner",
    "SchemaRegistry", "ResultNormaliser",
]
