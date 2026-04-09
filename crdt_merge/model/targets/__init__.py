# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
# Change Date: 2028-03-29 -> Apache-2.0; see LICENSE for terms.

"""Model merge pipeline source/target adapters for HuggingFace Hub."""

from crdt_merge.model.targets.hf import HfSource, HfTarget

__all__ = ["HfSource", "HfTarget"]
