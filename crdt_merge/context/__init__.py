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

"""
Context Memory System — CRDT-merged memory for AI agents.

This subpackage provides a complete system for merging, deduplicating,
and managing agent memories using CRDT semantics. Every merge operation
is commutative, associative, and idempotent — agents can merge in any
order and always converge to the same state.

Classes:
    MemorySidecar:       Pre-computed metadata per memory chunk (O(1) filtering).
    ContextManifest:     Self-describing merge attestation (EU AI Act traceability).
    ContextBloom:        64-shard bloom filter for O(1) memory dedup.
    ContextConsolidator: Bundles thousands of small memories into indexed blocks.
    MemoryChunk:         A single memory entry with its sidecar.
    ConsolidatedBlock:   A block of consolidated memories.
    ContextMerge:        Quality-weighted, budget-aware context merge (main entry point).
    MergeResult:         Result of a context merge operation.

New in v0.8.2.
"""

from .bloom import ContextBloom
from .consolidator import ConsolidatedBlock, ContextConsolidator, MemoryChunk
from .manifest import ContextManifest
from .merge import ContextMerge, MergeResult
from .sidecar import MemorySidecar

__all__ = [
    "MemorySidecar",
    "ContextManifest",
    "ContextBloom",
    "ContextConsolidator",
    "ConsolidatedBlock",
    "MemoryChunk",
    "ContextMerge",
    "MergeResult",
]
