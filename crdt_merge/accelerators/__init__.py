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
crdt-merge Accelerators — ecosystem integrations for the modern data stack.

Each accelerator uses lazy imports to avoid mandatory dependencies.
Accelerators implement the AcceleratorProtocol for uniform discovery.

Available accelerators:
    - duckdb_udf: DuckDB UDF / MergeQL extension
    - flight_server: Arrow Flight merge-as-a-service
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class AcceleratorProtocol(Protocol):
    """Base protocol for all crdt-merge accelerators."""

    name: str
    version: str

    def health_check(self) -> Dict[str, Any]:
        """Return health / readiness status."""
        ...

    def is_available(self) -> bool:
        """Check whether external dependencies are available."""
        ...


# ---------------------------------------------------------------------------
# Global registry
# ---------------------------------------------------------------------------

ACCELERATOR_REGISTRY: Dict[str, type] = {}


def register_accelerator(cls: type) -> type:
    """Decorator to register an accelerator.

    Usage::

        @register_accelerator
        class MyAccelerator:
            name = "my_accel"
            version = "0.7.0"
            ...
    """
    name = getattr(cls, "name", cls.__name__)
    ACCELERATOR_REGISTRY[name] = cls
    return cls


def get_accelerator(name: str) -> type:
    """Get a registered accelerator class by name.

    Raises:
        KeyError: if the accelerator is not registered.
    """
    if name not in ACCELERATOR_REGISTRY:
        raise KeyError(
            f"Accelerator '{name}' not registered. "
            f"Available: {list(ACCELERATOR_REGISTRY.keys())}"
        )
    return ACCELERATOR_REGISTRY[name]


def list_accelerators() -> List[str]:
    """List all registered accelerator names."""
    return list(ACCELERATOR_REGISTRY.keys())


__all__ = [
    "AcceleratorProtocol",
    "ACCELERATOR_REGISTRY",
    "register_accelerator",
    "get_accelerator",
    "list_accelerators",
]
