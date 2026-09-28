# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
# Patent: UK Application No. 2607132.4, GB2608127.3
# Change Date: 2028-04-08, Change License: Apache License, Version 2.0

"""These fault-injection tests drive the trust lattice with unsigned
evidence, so they opt into the legacy unauthenticated modes explicitly.
The library default is fail-closed (verification raises without a key
registry)."""

import pytest

from crdt_merge.e4.pco import configure_ed25519_verification
from crdt_merge.e4.proof_evidence import configure_evidence_verification


@pytest.fixture(autouse=True)
def _explicit_legacy_unsigned_mode():
    configure_ed25519_verification(None, allow_unsigned=True)
    configure_evidence_verification(None, allow_unauthenticated=True)
    yield
    configure_ed25519_verification(None)
    configure_evidence_verification(None)
