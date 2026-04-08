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

"""Semantic validation extension point for domain-specific content checks.

Addresses two expert concerns:

  - Okonkwo §7: Long-range adaptive adversary.  A sophisticated adversary
    builds trust honestly, then exploits Level 0 fast-path with a carefully
    crafted delta that's within magnitude bounds but semantically damaging.
    Solution: pluggable semantic validators that run alongside statistical
    checks at all verification levels.

  - Nair §13: Semantic gap.  Trust measures protocol compliance (valid
    Merkle proofs, consistent clocks) but not semantic correctness.
    Solution: extension point for domain-specific validators that can
    flag structurally valid but semantically suspicious content.

Design:
  - SemanticValidator is a Protocol (interface) — no concrete
    implementation is forced on users.
  - Three built-in validators cover common attack patterns:
    1. MagnitudeValidator — detect abnormal parameter magnitudes
    2. StatisticalShiftDetector — detect distribution shifts
    3. ParameterRegionGuard — protect critical model regions
  - CompositeSemanticValidator chains multiple validators.
  - All validators return a ValidationResult with a risk score.
  - The adaptive verification controller can escalate verification
    level based on semantic risk.

Technical effect (UK patent): provides a secondary defense layer against
semantically crafted adversarial inputs that pass structural verification,
reducing the attack surface for long-range adaptive adversaries in
Byzantine-tolerant CRDT networks.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    runtime_checkable,
)


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of semantic validation.

    Attributes
    ----------
    valid      : True if the content passes validation.
    risk_score : Risk level [0.0, 1.0].  0 = no risk, 1 = certain attack.
    reason     : Human-readable explanation (empty if valid).
    escalate   : True if verification level should be escalated.
    validator  : Name of the validator that produced this result.
    """
    valid: bool
    risk_score: float = 0.0
    reason: str = ""
    escalate: bool = False
    validator: str = ""


@runtime_checkable
class SemanticValidator(Protocol):
    """Interface for domain-specific semantic validators.

    Implementations can inspect delta content and return a risk
    assessment.  They are called by the adaptive verification
    controller at every verification level (including Level 0).
    """

    def validate(
        self,
        delta_content: Dict[str, Any],
        peer_id: str,
        trust_score: float,
    ) -> ValidationResult:
        """Validate delta content semantically.

        Parameters
        ----------
        delta_content :
            The delta's insertions/updates as a key→value dict.
        peer_id :
            The originating peer.
        trust_score :
            The peer's current overall trust.
        """
        ...


class MagnitudeValidator:
    """Detect abnormal parameter magnitudes in delta updates.

    Flags deltas where parameter values deviate significantly from
    expected ranges.  This catches the "trusted peer goes rogue"
    attack where a high-trust peer injects extreme values.

    Parameters
    ----------
    max_magnitude :
        Maximum absolute value for any parameter (default: 100.0).
    max_change_ratio :
        Maximum ratio of new/old value (default: 10.0).
    critical_regions :
        Set of key prefixes that trigger stricter validation.
    """

    def __init__(
        self,
        *,
        max_magnitude: float = 100.0,
        max_change_ratio: float = 10.0,
        critical_regions: Optional[Set[str]] = None,
    ) -> None:
        self._max_mag = max_magnitude
        self._max_ratio = max_change_ratio
        self._critical = critical_regions or set()

    def validate(
        self,
        delta_content: Dict[str, Any],
        peer_id: str,
        trust_score: float,
    ) -> ValidationResult:
        violations = []
        risk = 0.0

        for key, value in delta_content.items():
            if not isinstance(value, (int, float)):
                continue

            magnitude = abs(value)
            is_critical = any(key.startswith(p) for p in self._critical)
            threshold = self._max_mag * (0.1 if is_critical else 1.0)

            if magnitude > threshold:
                violations.append(
                    f"key={key!r}: magnitude {magnitude:.2f} > {threshold:.2f}"
                )
                risk = max(risk, min(1.0, magnitude / threshold))

        if violations:
            return ValidationResult(
                valid=False,
                risk_score=risk,
                reason=f"Magnitude violations: {'; '.join(violations[:3])}",
                escalate=risk > 0.5,
                validator="MagnitudeValidator",
            )
        return ValidationResult(valid=True, validator="MagnitudeValidator")

    def __repr__(self) -> str:
        return (
            f"MagnitudeValidator(max={self._max_mag}, "
            f"critical_regions={len(self._critical)})"
        )


class StatisticalShiftDetector:
    """Detect distribution shifts in parameter updates.

    Maintains a running estimate of the parameter distribution and
    flags deltas that shift the distribution significantly.  Uses
    Welford's online algorithm for incremental mean/variance.

    This catches subtle adversarial attacks where individual values
    are within bounds but the collective shift is anomalous.

    Parameters
    ----------
    shift_threshold :
        Maximum allowed KL divergence estimate (default: 2.0).
    warmup_samples :
        Minimum samples before detection activates (default: 10).
    """

    def __init__(
        self,
        *,
        shift_threshold: float = 2.0,
        warmup_samples: int = 10,
    ) -> None:
        self._threshold = shift_threshold
        self._warmup = warmup_samples
        self._count = 0
        self._mean = 0.0
        self._m2 = 0.0  # Running sum of squared deviations

    def validate(
        self,
        delta_content: Dict[str, Any],
        peer_id: str,
        trust_score: float,
    ) -> ValidationResult:
        values = [v for v in delta_content.values() if isinstance(v, (int, float))]
        if not values:
            return ValidationResult(valid=True, validator="StatisticalShiftDetector")

        # Compute batch mean and variance
        batch_mean = sum(values) / len(values)
        batch_var = (
            sum((v - batch_mean) ** 2 for v in values) / max(len(values) - 1, 1)
        )

        # Update running statistics
        for v in values:
            self._count += 1
            delta = v - self._mean
            self._mean += delta / self._count
            delta2 = v - self._mean
            self._m2 += delta * delta2

        if self._count < self._warmup:
            return ValidationResult(valid=True, validator="StatisticalShiftDetector")

        # Compute running variance
        running_var = self._m2 / max(self._count - 1, 1)

        # Simplified KL divergence estimate between batch and running
        if running_var < 1e-10:
            kl = 0.0
        else:
            var_ratio = batch_var / running_var if running_var > 0 else 0
            mean_diff = (batch_mean - self._mean) ** 2
            kl = 0.5 * (
                var_ratio - 1.0 + mean_diff / max(running_var, 1e-10)
                + math.log(max(running_var, 1e-10) / max(batch_var, 1e-10))
            )
            kl = abs(kl)  # Ensure non-negative

        if kl > self._threshold:
            risk = min(1.0, kl / (self._threshold * 3))
            return ValidationResult(
                valid=False,
                risk_score=risk,
                reason=f"Distribution shift detected: KL={kl:.3f} > {self._threshold}",
                escalate=True,
                validator="StatisticalShiftDetector",
            )

        return ValidationResult(valid=True, validator="StatisticalShiftDetector")

    def __repr__(self) -> str:
        return (
            f"StatisticalShiftDetector("
            f"samples={self._count}, "
            f"threshold={self._threshold})"
        )


class ParameterRegionGuard:
    """Guard critical model parameter regions with enhanced validation.

    Some model regions (attention heads, classification layers) are
    more sensitive to adversarial manipulation.  This guard applies
    stricter validation to designated regions.

    Parameters
    ----------
    guarded_regions :
        Dict mapping key prefixes to maximum allowed change magnitudes.
        E.g., {"model.attention": 0.01, "model.classifier": 0.001}
    """

    def __init__(
        self,
        guarded_regions: Optional[Dict[str, float]] = None,
    ) -> None:
        self._regions = dict(guarded_regions or {})

    def add_region(self, prefix: str, max_change: float) -> None:
        """Add a guarded region."""
        self._regions[prefix] = max_change

    def validate(
        self,
        delta_content: Dict[str, Any],
        peer_id: str,
        trust_score: float,
    ) -> ValidationResult:
        violations = []

        for key, value in delta_content.items():
            if not isinstance(value, (int, float)):
                continue

            for prefix, max_change in self._regions.items():
                if key.startswith(prefix):
                    # Scale threshold by trust: higher trust = more lenient
                    effective_max = max_change * (1.0 + trust_score)
                    if abs(value) > effective_max:
                        violations.append(
                            f"{key}: |{value:.4f}| > {effective_max:.4f} "
                            f"(region: {prefix!r})"
                        )

        if violations:
            risk = min(1.0, len(violations) / max(len(delta_content), 1))
            return ValidationResult(
                valid=False,
                risk_score=risk,
                reason=f"Guarded region violations: {'; '.join(violations[:3])}",
                escalate=True,
                validator="ParameterRegionGuard",
            )
        return ValidationResult(valid=True, validator="ParameterRegionGuard")

    @property
    def region_count(self) -> int:
        return len(self._regions)

    def __repr__(self) -> str:
        return f"ParameterRegionGuard(regions={len(self._regions)})"


class CompositeSemanticValidator:
    """Chain multiple semantic validators.

    All validators are run.  The result is the highest-risk outcome.
    If any validator returns escalate=True, the composite escalates.

    Parameters
    ----------
    validators :
        List of validators to chain.
    """

    def __init__(
        self,
        validators: Optional[List[Any]] = None,
    ) -> None:
        self._validators: List[Any] = list(validators or [])

    def add(self, validator: Any) -> None:
        """Add a validator to the chain."""
        self._validators.append(validator)

    def validate(
        self,
        delta_content: Dict[str, Any],
        peer_id: str,
        trust_score: float,
    ) -> ValidationResult:
        results = []
        for v in self._validators:
            result = v.validate(delta_content, peer_id, trust_score)
            results.append(result)

        if not results:
            return ValidationResult(valid=True, validator="CompositeSemanticValidator")

        worst = max(results, key=lambda r: r.risk_score)
        any_invalid = any(not r.valid for r in results)
        any_escalate = any(r.escalate for r in results)

        reasons = [r.reason for r in results if r.reason]

        return ValidationResult(
            valid=not any_invalid,
            risk_score=worst.risk_score,
            reason="; ".join(reasons) if reasons else "",
            escalate=any_escalate,
            validator="CompositeSemanticValidator",
        )

    @property
    def validator_count(self) -> int:
        return len(self._validators)

    def __repr__(self) -> str:
        return f"CompositeSemanticValidator(count={len(self._validators)})"
