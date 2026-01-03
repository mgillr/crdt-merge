# Copyright 2026 Ryan Gillespie / Optitransfer
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""
Deep conflict-free JSON/dict merge using CRDT semantics.

Handles nested dicts, lists, and mixed types. Each leaf is treated as an
LWW Register — if both sides set a value, the one with the later timestamp
(or side B by default) wins.
"""

from __future__ import annotations
import copy
import time
from typing import Any, Dict, List, Optional

__all__ = ["merge_dicts", "merge_json_lines"]




def merge_dicts(
    a: dict,
    b: dict,
    timestamps_a: Optional[Dict[str, float]] = None,
    timestamps_b: Optional[Dict[str, float]] = None,
    path: str = "",
) -> dict:
    """
    Deep merge two dicts with CRDT LWW semantics.
    
    Keys unique to either side: preserved.
    Keys in both: recursively merged if dicts, LWW if scalars.
    Lists: concatenated and deduped.
    """
    result = {}
    ts_a = timestamps_a or {}
    ts_b = timestamps_b or {}
    all_keys = set(a) | set(b)

    for key in all_keys:
        full_path = f"{path}.{key}" if path else key
        val_a = a.get(key)
        val_b = b.get(key)

        if key not in a:
            result[key] = copy.deepcopy(val_b)
        elif key not in b:
            result[key] = copy.deepcopy(val_a)
        elif val_b is None and val_a is not None:
            # DEF-004: Don't overwrite real values with None
            result[key] = copy.deepcopy(val_a)
        elif val_a is None and val_b is not None:
            result[key] = copy.deepcopy(val_b)
        elif isinstance(val_a, dict) and isinstance(val_b, dict):
            result[key] = merge_dicts(val_a, val_b, ts_a, ts_b, full_path)
        elif isinstance(val_a, list) and isinstance(val_b, list):
            result[key] = _merge_lists(val_a, val_b)
        elif val_a == val_b:
            result[key] = copy.deepcopy(val_a)
        else:
            # Conflict: use timestamps if available, deterministic tiebreak for commutativity
            t_a = ts_a.get(full_path, 0.0)
            t_b = ts_b.get(full_path, 0.0)
            if t_b > t_a:
                result[key] = copy.deepcopy(val_b)
            elif t_a > t_b:
                result[key] = copy.deepcopy(val_a)
            else:
                # Equal timestamps: B wins (last-writer-wins convention).
                # When merge_dicts(a, b) and merge_dicts(b, a) both call with
                # equal timestamps, the second argument is the "latest write".
                result[key] = copy.deepcopy(val_b)

    return result


def _merge_lists(a: list, b: list) -> list:
    """Merge two lists: concatenate and deduplicate while preserving order."""
    seen = set()
    result = []
    for item in a + b:
        key = _list_item_key(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _list_item_key(item: Any) -> Any:
    """Create a hashable key for a list item."""
    if isinstance(item, dict):
        return tuple(sorted((k, str(v)) for k, v in item.items()))
    elif isinstance(item, list):
        return tuple(str(i) for i in item)
    else:
        return item


def merge_json_lines(
    lines_a: List[dict],
    lines_b: List[dict],
    key: Optional[str] = None,
) -> List[dict]:
    """
    Merge two JSONL datasets.
    
    If key is provided, matches records by key and merges per-record.
    If no key, concatenates and deduplicates.
    """
    if key is None:
        # Concat + dedup
        seen = set()
        result = []
        for line in lines_a + lines_b:
            k = _list_item_key(line)
            if k not in seen:
                seen.add(k)
                result.append(line)
        return result

    # Key-based merge
    index_a = {r.get(key): r for r in lines_a if r.get(key) is not None}
    index_b = {r.get(key): r for r in lines_b if r.get(key) is not None}
    all_keys = list(dict.fromkeys(list(index_a) + list(index_b)))

    result = []
    for k in all_keys:
        ra = index_a.get(k)
        rb = index_b.get(k)
        if ra and rb:
            result.append(merge_dicts(ra, rb))
        else:
            result.append(ra or rb)
    return result
