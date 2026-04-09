# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
# Change Date: 2028-03-29 -> Apache-2.0
# See LICENSE for full terms.

"""HuggingFace Hub integration for crdt-merge model merging.

Push, pull, and merge models on HuggingFace Hub with CRDT verification
and provenance-enriched model cards.
"""

from crdt_merge.hub.hf import HFMergeHub, HFMergeResult
from crdt_merge.hub.model_card import AutoModelCard, ModelCardConfig

__all__ = ["HFMergeHub", "HFMergeResult", "AutoModelCard", "ModelCardConfig"]
