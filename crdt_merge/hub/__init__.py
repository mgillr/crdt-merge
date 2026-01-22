# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""HuggingFace Hub integration for crdt-merge model merging.

Push, pull, and merge models on HuggingFace Hub with CRDT verification
and provenance-enriched model cards.
"""

from crdt_merge.hub.hf import HFMergeHub, HFMergeResult
from crdt_merge.hub.model_card import AutoModelCard, ModelCardConfig

__all__ = ["HFMergeHub", "HFMergeResult", "AutoModelCard", "ModelCardConfig"]
