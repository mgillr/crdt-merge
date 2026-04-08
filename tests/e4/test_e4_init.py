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

"""Tests for the E4 package __init__.py: public API surface, version, convenience imports.

Ensures all expected symbols are exported and importable from crdt_merge.e4.
"""

import pytest


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------

class TestPublicAPI:

    def test_import_typed_trust_score(self):
        """TypedTrustScore is importable from crdt_merge.e4."""
        from crdt_merge.e4 import TypedTrustScore
        assert TypedTrustScore is not None

    def test_import_trust_homeostasis(self):
        """TrustHomeostasis is importable from crdt_merge.e4."""
        from crdt_merge.e4 import TrustHomeostasis
        assert TrustHomeostasis is not None

    def test_import_trust_dimensions(self):
        """TRUST_DIMENSIONS is importable from crdt_merge.e4."""
        from crdt_merge.e4 import TRUST_DIMENSIONS
        assert len(TRUST_DIMENSIONS) == 6

    def test_import_probation_trust(self):
        """PROBATION_TRUST is importable from crdt_merge.e4."""
        from crdt_merge.e4 import PROBATION_TRUST
        assert PROBATION_TRUST == 0.5

    def test_import_quarantine_threshold(self):
        """QUARANTINE_THRESHOLD is importable."""
        from crdt_merge.e4 import QUARANTINE_THRESHOLD
        assert QUARANTINE_THRESHOLD == 0.1

    def test_import_low_trust_threshold(self):
        """LOW_TRUST_THRESHOLD is importable."""
        from crdt_merge.e4 import LOW_TRUST_THRESHOLD
        assert LOW_TRUST_THRESHOLD == 0.4

    def test_import_partial_threshold(self):
        """PARTIAL_THRESHOLD is importable."""
        from crdt_merge.e4 import PARTIAL_THRESHOLD
        assert PARTIAL_THRESHOLD == 0.8

    def test_import_trust_evidence(self):
        """TrustEvidence is importable from crdt_merge.e4."""
        from crdt_merge.e4 import TrustEvidence
        assert TrustEvidence is not None

    def test_import_evidence_types(self):
        """EVIDENCE_TYPES is importable from crdt_merge.e4."""
        from crdt_merge.e4 import EVIDENCE_TYPES
        assert len(EVIDENCE_TYPES) == 5

    def test_import_pack_functions(self):
        """Pack helper functions are importable."""
        from crdt_merge.e4 import (
            pack_attestation_pair,
            pack_clock_pair,
            pack_delta_proof,
            pack_merkle_path,
            pack_state_pair,
        )
        assert callable(pack_attestation_pair)
        assert callable(pack_clock_pair)
        assert callable(pack_delta_proof)
        assert callable(pack_merkle_path)
        assert callable(pack_state_pair)

    def test_import_aggregate_pco(self):
        """AggregateProofCarryingOperation is importable."""
        from crdt_merge.e4 import AggregateProofCarryingOperation
        assert AggregateProofCarryingOperation is not None

    def test_import_subtree_ref(self):
        """SubtreeRef is importable."""
        from crdt_merge.e4 import SubtreeRef
        assert SubtreeRef is not None

    def test_import_projection_delta(self):
        """ProjectionDelta is importable."""
        from crdt_merge.e4 import ProjectionDelta
        assert ProjectionDelta is not None

    def test_import_projection_delta_manager(self):
        """ProjectionDeltaManager is importable."""
        from crdt_merge.e4 import ProjectionDeltaManager
        assert ProjectionDeltaManager is not None

    def test_import_frozen_dict(self):
        """FrozenDict is importable."""
        from crdt_merge.e4 import FrozenDict
        assert FrozenDict is not None


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

class TestAllExport:

    def test_all_defined(self):
        """__all__ is defined in crdt_merge.e4."""
        import crdt_merge.e4
        assert hasattr(crdt_merge.e4, "__all__")

    def test_all_count(self):
        """__all__ has expected number of entries (16)."""
        import crdt_merge.e4
        assert len(crdt_merge.e4.__all__) >= 16

    def test_all_entries_importable(self):
        """Every entry in __all__ is actually importable."""
        import crdt_merge.e4
        for name in crdt_merge.e4.__all__:
            assert hasattr(crdt_merge.e4, name), f"{name} not importable"


# ---------------------------------------------------------------------------
# Cross-module consistency
# ---------------------------------------------------------------------------

class TestCrossModuleConsistency:

    def test_typed_trust_score_is_same_class(self):
        """TypedTrustScore from e4 is the same as from typed_trust."""
        from crdt_merge.e4 import TypedTrustScore as TTS1
        from crdt_merge.e4.typed_trust import TypedTrustScore as TTS2
        assert TTS1 is TTS2

    def test_projection_delta_is_same_class(self):
        """ProjectionDelta from e4 is the same as from projection_delta."""
        from crdt_merge.e4 import ProjectionDelta as PD1
        from crdt_merge.e4.projection_delta import ProjectionDelta as PD2
        assert PD1 is PD2

    def test_pco_is_same_class(self):
        """AggregateProofCarryingOperation from e4 is the same as from pco."""
        from crdt_merge.e4 import AggregateProofCarryingOperation as A1
        from crdt_merge.e4.pco import AggregateProofCarryingOperation as A2
        assert A1 is A2
