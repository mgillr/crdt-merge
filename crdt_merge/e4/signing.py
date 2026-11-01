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

"""Strict Ed25519 primitives shared by the E4 modules.

Every E4 signature check goes through :func:`ed25519_verify`.  There is no
fallback: without the ``cryptography`` package every call raises
:class:`Ed25519Unavailable`, and a check that fails returns False without
trying anything else.
"""

from __future__ import annotations

import logging
import os
import warnings

#: Environment variable that must be exactly ``"1"`` before an insecure
#: legacy mode (``allow_unsigned`` / ``allow_unauthenticated``) can be
#: switched on.  It exists so tests can opt in deliberately; production
#: code should never set it.
INSECURE_TEST_MODE_ENV = "CRDT_MERGE_INSECURE_TEST_MODE"

_logger = logging.getLogger("crdt_merge.e4.security")


class Ed25519Unavailable(RuntimeError):
    """Raised when Ed25519 is needed and the ``cryptography`` package is missing."""


class SignatureVerificationNotConfigured(RuntimeError):
    """Raised when a signature must be checked but no key registry is configured."""


class InsecureModeNotPermitted(RuntimeError):
    """Raised when an insecure legacy mode is requested without the guard."""


class InsecureConfigurationWarning(UserWarning):
    """Category of the warning emitted when an insecure legacy mode is enabled."""


def require_insecure_opt_in(option: str, effect: str) -> None:
    """Guard for the legacy modes that switch signature checks off.

    Raises :class:`InsecureModeNotPermitted` unless the environment variable
    ``CRDT_MERGE_INSECURE_TEST_MODE`` is exactly ``"1"``.  When it is, emits
    an :class:`InsecureConfigurationWarning` and a ``logging.WARNING`` record
    so the configuration is visible in test output and logs.
    """
    if os.environ.get(INSECURE_TEST_MODE_ENV) != "1":
        raise InsecureModeNotPermitted(
            f"{option}=True switches signature verification off and is refused: "
            f"{effect}. It is meant for tests only; set "
            f"{INSECURE_TEST_MODE_ENV}=1 to enable it deliberately, or configure "
            "a key registry instead."
        )
    message = (
        f"INSECURE: {option}=True is active; {effect}. "
        "Do not use this outside tests."
    )
    _logger.warning(message)
    warnings.warn(message, InsecureConfigurationWarning, stacklevel=3)


def load_ed25519():
    """Return ``(ed25519 module, InvalidSignature)`` or raise Ed25519Unavailable."""
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as exc:
        raise Ed25519Unavailable(
            "Ed25519 requires the cryptography package, a core dependency of "
            "crdt-merge; this environment is missing it (pip install "
            "'cryptography>=41'). There is no fallback."
        ) from exc
    return ed25519, InvalidSignature


def has_ed25519() -> bool:
    """True when the ``cryptography`` package can be imported."""
    try:
        load_ed25519()
    except Ed25519Unavailable:
        return False
    return True


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """True only for a valid 64-byte Ed25519 signature under a 32-byte key.

    Raises Ed25519Unavailable when the ``cryptography`` package is missing.
    """
    ed25519, InvalidSignature = load_ed25519()
    if not isinstance(public_key, (bytes, bytearray)) or len(public_key) != 32:
        return False
    if not isinstance(signature, (bytes, bytearray)) or len(signature) != 64:
        return False
    try:
        ed25519.Ed25519PublicKey.from_public_bytes(bytes(public_key)).verify(
            bytes(signature), bytes(message)
        )
    except (InvalidSignature, ValueError):
        return False
    return True
