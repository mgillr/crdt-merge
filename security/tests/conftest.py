# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
# Patent: UK Application No. 2607132.4, GB2608127.3
# Change Date: 2028-04-08, Change License: Apache License, Version 2.0

"""These fault-injection tests drive the trust lattice with unsigned
evidence, so they opt into the legacy unauthenticated modes explicitly.
The library default is fail-closed (verification raises without a key
registry), and the opt-ins are refused unless CRDT_MERGE_INSECURE_TEST_MODE=1,
which this fixture sets for the duration of each test.  The guard tests in
test_insecure_opt_in_guard.py clear it again."""

import warnings

import pytest

from crdt_merge.e4.pco import configure_ed25519_verification
from crdt_merge.e4.proof_evidence import configure_evidence_verification
from crdt_merge.e4.signing import InsecureConfigurationWarning


@pytest.fixture(autouse=True)
def _explicit_legacy_unsigned_mode(monkeypatch):
    # The legacy modes are refused unless the test-mode guard is set.
    monkeypatch.setenv("CRDT_MERGE_INSECURE_TEST_MODE", "1")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InsecureConfigurationWarning)
        configure_ed25519_verification(None, allow_unsigned=True)
        configure_evidence_verification(None, allow_unauthenticated=True)
    yield
    configure_ed25519_verification(None)
    configure_evidence_verification(None)
