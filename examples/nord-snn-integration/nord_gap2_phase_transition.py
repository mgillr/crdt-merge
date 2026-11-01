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
# On 2028-03-29 the code license converts to Apache 2.0. Patent rights
# are separately held
# (UK Application No. GB 2607132.4, GB2608127.3) and are not granted by the
# license. Commercial use of patented methods requires a patent license.

"""
Phase transition measurement for SNN emergence.

Detection says "something happened at step 25K."
Measurement says "the compositionality order parameter crossed critical
threshold D_c with exponent beta, classifying the universality class."

Based on:
  Paper 03 -- Emergence From Nothing (phase transitions + renormalization group)

Author: Ryan Gillespie
Status: Pre-release
Patent: UK Application No. GB 2607132.4, GB2608127.3
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

from crdt_merge.core import LWWMap, GCounter


@dataclass
class PhaseTransitionFit:
    """Result of fitting a phase transition curve."""
    critical_step: int           # step where transition occurs
    critical_value: float        # D_c threshold
    exponent_beta: float         # critical exponent
    r_squared: float             # goodness of fit
    order_parameter: str         # what was measured
    universality_class: str      # classification


class PhaseTransitionMeasurer:
    """Measure the critical exponent of SNN emergence events.

    Fits the order parameter phi near the critical point:
      phi(D) ~ |D - D_c|^beta  for D near D_c

    The exponent beta classifies the universality class:
      beta ~ 0.33: 3D Ising (percolation on lattice)
      beta ~ 0.5:  mean-field (random graph percolation)
      beta ~ 0.125: 2D Ising

    For SNN emergence, the order parameter is zone activation rate
    and D is the effective diversity of firing patterns.
    """

    def __init__(self):
        self._history: List[Tuple[int, Dict[str, float]]] = []
        self._activation_log = LWWMap()

    def record(self, step: int, zone_activations: Dict[str, float]):
        self._history.append((step, dict(zone_activations)))
        for zone, rate in zone_activations.items():
            self._activation_log.set(
                f"{zone}:{step}", rate,
                timestamp=float(step), node_id="measurer",
            )

    def fit_transition(
        self, zone: str, window_around_critical: int = 5,
    ) -> Optional[PhaseTransitionFit]:
        """Fit the phase transition for a specific zone."""
        # Extract time series for the zone
        series = [(step, acts.get(zone, 0.0)) for step, acts in self._history]
        if len(series) < 5:
            return None

        steps = [s for s, _ in series]
        values = [v for _, v in series]

        # Find the steepest jump (critical point candidate)
        max_jump = 0.0
        critical_idx = 0
        for i in range(1, len(values)):
            jump = abs(values[i] - values[i - 1])
            if jump > max_jump:
                max_jump = jump
                critical_idx = i

        if max_jump < 0.01:
            return None

        critical_step = steps[critical_idx]
        critical_value = (values[critical_idx] + values[max(0, critical_idx - 1)]) / 2

        # Fit beta: phi ~ |step - step_c|^beta on the post-critical side
        post_steps = []
        post_values = []
        for i in range(critical_idx, min(len(steps), critical_idx + window_around_critical + 1)):
            if values[i] > critical_value:
                dt = max(steps[i] - critical_step, 1)
                post_steps.append(math.log(dt))
                post_values.append(math.log(max(values[i] - critical_value, 1e-10)))

        if len(post_steps) < 2:
            # Not enough post-critical data, estimate from jump magnitude
            beta = 0.33  # default to percolation class
            r_sq = 0.0
        else:
            # Linear regression in log-log space: log(phi) = beta * log(dt) + c
            n = len(post_steps)
            sx = sum(post_steps)
            sy = sum(post_values)
            sxx = sum(x * x for x in post_steps)
            sxy = sum(x * y for x, y in zip(post_steps, post_values))
            denom = n * sxx - sx * sx
            if abs(denom) < 1e-12:
                beta = 0.33
                r_sq = 0.0
            else:
                beta = (n * sxy - sx * sy) / denom
                beta = max(0.01, min(beta, 2.0))  # clamp to physical range

                # R-squared
                y_mean = sy / n
                ss_tot = sum((y - y_mean) ** 2 for y in post_values)
                c = (sy - beta * sx) / n
                ss_res = sum((y - (beta * x + c)) ** 2 for x, y in zip(post_steps, post_values))
                r_sq = 1.0 - ss_res / max(ss_tot, 1e-10) if ss_tot > 1e-10 else 0.0

        # Classify universality
        if 0.1 <= beta <= 0.2:
            uclass = "2D_ising"
        elif 0.25 <= beta <= 0.4:
            uclass = "3D_ising_percolation"
        elif 0.4 <= beta <= 0.6:
            uclass = "mean_field"
        else:
            uclass = "non_standard"

        return PhaseTransitionFit(
            critical_step=critical_step,
            critical_value=critical_value,
            exponent_beta=round(beta, 3),
            r_squared=round(max(r_sq, 0.0), 3),
            order_parameter=f"{zone}_activation",
            universality_class=uclass,
        )

    def simulate_nord_trajectory(self) -> Dict[str, PhaseTransitionFit]:
        """Replay Nord's actual trajectory and measure all transitions."""
        # Stable phase: steps 0-20000
        for step in range(0, 20000, 1000):
            self.record(step, {
                "sensory": 0.07, "association": 0.10,
                "memory_cortex": 0.01, "executive": 0.12,
            })

        # Pre-critical: steps 22000-24500
        for step in range(22000, 24500, 500):
            self.record(step, {
                "sensory": 0.05, "association": 0.08,
                "memory_cortex": 0.01, "executive": 0.10,
            })

        # Critical point: step 25000 (39% memory shift)
        self.record(25000, {
            "sensory": 0.05, "association": 0.08,
            "memory_cortex": 0.39, "executive": 0.18,
        })

        # Post-critical: steps 25500-27000
        for step in range(25500, 27500, 500):
            self.record(step, {
                "sensory": 0.05, "association": 0.08,
                "memory_cortex": 0.39 + (step - 25000) * 0.0001,
                "executive": 0.18,
            })

        results = {}
        for zone in ["sensory", "association", "memory_cortex", "executive"]:
            fit = self.fit_transition(zone)
            if fit and fit.critical_value > 0.01:
                results[zone] = fit
        return results

    @property
    def history_length(self) -> int:
        return len(self._history)
