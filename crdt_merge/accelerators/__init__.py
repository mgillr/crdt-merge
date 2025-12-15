# Copyright 2026 Ryan Gillespie
# Licensed under Apache-2.0

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
