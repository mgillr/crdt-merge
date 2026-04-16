# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License").
# You may use this file freely for any non-production purpose:
# research, evaluation, development, testing, education, personal use.
#
# A commercial production license is required ONLY if you deploy this
# code in a revenue-generating production environment. All other use
# is permitted without restriction.
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0
#
# On 2028-03-29 this file converts to Apache License, Version 2.0
# and becomes fully open for all use cases including commercial production.

"""
Immune pattern detection within the SNN itself.

Not monitoring worker contributions (that's E4 trust).
Monitors the model's own internal patterns for anomalies:
  - STDP timing violations (post fires before pre in impossible timing)
  - Biologically implausible firing rates
  - Contradictory zone outputs
  - Pathological weight drift

When detected, quarantine the affected zone.

Based on:
  Paper 08 -- Trust Beats Treachery (affinity maturation)
  Artificial Immune Intelligence architecture
  Branch: synapse/immune

Author: Ryan Gillespie
Status: Pre-release
Patent: UK Application No. GB 2607132.4, GB2608127.3
"""

import time
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from crdt_merge.e4.delta_trust_lattice import TrustCircuitBreaker
from crdt_merge.e4.typed_trust import TypedTrustScore
from crdt_merge.core import GCounter, LWWMap, ORSet


class AnomalyType(str, Enum):
    STDP_TIMING_VIOLATION = "stdp_timing"     # post fires before pre impossibly
    FIRING_RATE_EXPLOSION = "rate_explosion"   # zone firing >50% (biologically implausible)
    FIRING_RATE_COLLAPSE = "rate_collapse"     # zone firing <0.1% (dead zone)
    ZONE_CONTRADICTION = "zone_contradiction"  # two zones produce conflicting outputs
    WEIGHT_DRIFT = "weight_drift"             # weights drifting outside stable range
    GRADIENT_PATHOLOGY = "grad_pathology"      # vanishing or exploding in zone


@dataclass
class AnomalyEvent:
    """A detected internal anomaly."""
    anomaly_type: AnomalyType
    zone: str
    severity: float            # 0.0 = minor, 1.0 = critical
    step: int
    details: str
    timestamp: float = field(default_factory=time.time)


class ZoneHealthMonitor:
    """Monitor a single zone's internal health via circuit breaker."""

    def __init__(self, zone: str, sigma_threshold: float = 2.0):
        self.zone = zone
        self._rate_breaker = TrustCircuitBreaker(
            window_size=30, sigma_threshold=sigma_threshold, min_samples=5,
        )
        self._weight_breaker = TrustCircuitBreaker(
            window_size=30, sigma_threshold=sigma_threshold, min_samples=5,
        )
        self._firing_history: List[float] = []
        self._weight_norm_history: List[float] = []
        self._quarantined = False
        self._anomaly_count = GCounter()

    def record_firing_rate(self, rate: float, step: int) -> Optional[AnomalyEvent]:
        self._firing_history.append(rate)
        old_ts = TypedTrustScore(_evidence={"model": {"obs": 1.0 - (self._firing_history[-2] if len(self._firing_history) > 1 else 0.5)}})
        new_ts = TypedTrustScore(_evidence={"model": {"obs": 1.0 - rate}})
        self._rate_breaker.record_trust_change(self.zone, old_ts, new_ts)

        # Hard bounds check
        if rate > 0.50:
            self._anomaly_count.increment(self.zone)
            return AnomalyEvent(
                AnomalyType.FIRING_RATE_EXPLOSION, self.zone,
                severity=min(rate, 1.0), step=step,
                details=f"{self.zone} firing at {rate:.1%} (>50% is pathological)",
            )
        if rate < 0.001 and len(self._firing_history) > 5:
            self._anomaly_count.increment(self.zone)
            return AnomalyEvent(
                AnomalyType.FIRING_RATE_COLLAPSE, self.zone,
                severity=0.8, step=step,
                details=f"{self.zone} firing at {rate:.3%} (dead zone)",
            )

        if self._rate_breaker.is_tripped():
            self._rate_breaker.reset()
            self._anomaly_count.increment(self.zone)
            return AnomalyEvent(
                AnomalyType.FIRING_RATE_EXPLOSION, self.zone,
                severity=0.6, step=step,
                details=f"{self.zone} anomalous firing rate velocity",
            )
        return None

    def record_weight_norm(self, norm: float, step: int) -> Optional[AnomalyEvent]:
        self._weight_norm_history.append(norm)
        if len(self._weight_norm_history) < 2:
            return None

        old_ts = TypedTrustScore(_evidence={"integrity": {"obs": 1.0 - min(self._weight_norm_history[-2] / 10.0, 0.99)}})
        new_ts = TypedTrustScore(_evidence={"integrity": {"obs": 1.0 - min(norm / 10.0, 0.99)}})
        self._weight_breaker.record_trust_change(self.zone, old_ts, new_ts)

        if self._weight_breaker.is_tripped():
            self._weight_breaker.reset()
            self._anomaly_count.increment(self.zone)
            return AnomalyEvent(
                AnomalyType.WEIGHT_DRIFT, self.zone,
                severity=0.7, step=step,
                details=f"{self.zone} weight norm anomalous velocity ({norm:.4f})",
            )
        return None

    def quarantine(self):
        self._quarantined = True

    def release(self):
        self._quarantined = False

    @property
    def is_quarantined(self) -> bool:
        return self._quarantined

    @property
    def anomaly_count(self) -> int:
        return self._anomaly_count.value


class NordImmuneSystem:
    """Self-healing immune system for Nord SNN.

    Monitors all 4 zones for internal anomalies. When a zone becomes
    pathological (dead neurons, exploding rates, weight drift),
    quarantine it to prevent bad patterns from propagating.
    """

    def __init__(self, sigma_threshold: float = 2.0):
        self.zones: Dict[str, ZoneHealthMonitor] = {}
        self.sigma_threshold = sigma_threshold
        self.events: List[AnomalyEvent] = []
        self.quarantine_log = ORSet()
        self._step = 0

    def _get_zone(self, zone: str) -> ZoneHealthMonitor:
        if zone not in self.zones:
            self.zones[zone] = ZoneHealthMonitor(zone, self.sigma_threshold)
        return self.zones[zone]

    def check_health(
        self,
        zone_firing_rates: Dict[str, float],
        zone_weight_norms: Optional[Dict[str, float]] = None,
        step: int = 0,
    ) -> List[AnomalyEvent]:
        """Run health check across all zones."""
        self._step = step
        detected = []

        for zone, rate in zone_firing_rates.items():
            monitor = self._get_zone(zone)
            event = monitor.record_firing_rate(rate, step)
            if event:
                detected.append(event)
                self.events.append(event)
                if event.severity > 0.7:
                    monitor.quarantine()
                    self.quarantine_log.add(f"{zone}:step{step}")

        if zone_weight_norms:
            for zone, norm in zone_weight_norms.items():
                monitor = self._get_zone(zone)
                event = monitor.record_weight_norm(norm, step)
                if event:
                    detected.append(event)
                    self.events.append(event)

        # Cross-zone contradiction check
        rates = list(zone_firing_rates.values())
        if len(rates) >= 2:
            max_rate = max(rates)
            min_rate = min(rates)
            if max_rate > 0.4 and min_rate < 0.005:
                event = AnomalyEvent(
                    AnomalyType.ZONE_CONTRADICTION,
                    zone="cross_zone",
                    severity=0.5,
                    step=step,
                    details=f"extreme zone divergence: max={max_rate:.1%} min={min_rate:.3%}",
                )
                detected.append(event)
                self.events.append(event)

        return detected

    def check_stdp_timing(
        self,
        pre_times: np.ndarray,
        post_times: np.ndarray,
        zone: str,
        step: int = 0,
    ) -> Optional[AnomalyEvent]:
        """Check for impossible STDP timing (post before pre with dt < refractory)."""
        dt = post_times - pre_times
        # Refractory period ~2ms. If post fires within 0.5ms of pre, suspicious.
        violations = np.sum(np.abs(dt) < 0.0005)
        total = len(dt)
        if total > 0 and violations / total > 0.1:
            event = AnomalyEvent(
                AnomalyType.STDP_TIMING_VIOLATION, zone,
                severity=0.6, step=step,
                details=f"{violations}/{total} STDP timing violations in {zone}",
            )
            self.events.append(event)
            return event
        return None

    @property
    def quarantined_zones(self) -> List[str]:
        return [z for z, m in self.zones.items() if m.is_quarantined]

    @property
    def health_report(self) -> dict:
        return {
            "zones": {
                z: {
                    "quarantined": m.is_quarantined,
                    "anomalies": m.anomaly_count,
                    "firing_history_len": len(m._firing_history),
                }
                for z, m in self.zones.items()
            },
            "total_events": len(self.events),
            "quarantined_zones": self.quarantined_zones,
            "quarantine_history": sorted(self.quarantine_log.value),
        }
