# SPDX-License-Identifier: BUSL-1.1
#
# Copyright 2026 Ryan Gillespie
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Strategy registry with ``@register_strategy`` decorator and plugin discovery.

Usage::

    from crdt_merge.model.strategies import register_strategy, get_strategy

    @register_strategy("my_strategy")
    class MyStrategy(ModelMergeStrategy):
        ...

    strategy = get_strategy("my_strategy")
"""

from __future__ import annotations

import importlib
import sys
from typing import Any, Dict, List, Type

from crdt_merge.model.strategies.base import ModelMergeStrategy

__all__ = [
    "register_strategy",
    "get_strategy",
    "list_strategies",
    "list_strategies_by_category",
]

# ---------------------------------------------------------------------------
# Internal registry
# ---------------------------------------------------------------------------

_REGISTRY: Dict[str, Type[ModelMergeStrategy]] = {}


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def register_strategy(name: str):
    """Class decorator that registers a ``ModelMergeStrategy`` subclass.

    Parameters
    ----------
    name : str
        Unique name used to look up the strategy.

    Raises
    ------
    ValueError
        If *name* is already registered.
    TypeError
        If the decorated class is not a subclass of ``ModelMergeStrategy``.
    """

    def _decorator(cls: Type[ModelMergeStrategy]) -> Type[ModelMergeStrategy]:
        if not (isinstance(cls, type) and issubclass(cls, ModelMergeStrategy)):
            raise TypeError(
                f"@register_strategy requires a ModelMergeStrategy subclass, got {cls!r}"
            )
        if name in _REGISTRY:
            raise ValueError(
                f"Strategy '{name}' is already registered (by {_REGISTRY[name]!r})"
            )
        _REGISTRY[name] = cls
        return cls

    return _decorator


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def get_strategy(name: str, **kwargs: Any) -> ModelMergeStrategy:
    """Instantiate a registered strategy by *name*.

    Parameters
    ----------
    name : str
        Registered strategy name.
    **kwargs
        Forwarded to the strategy constructor.

    Raises
    ------
    KeyError
        If the strategy name is not registered.
    """
    _discover_plugins()
    if name not in _REGISTRY:
        raise KeyError(
            f"Unknown strategy '{name}'. Available: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name](**kwargs)


def list_strategies() -> List[str]:
    """Return sorted list of all registered strategy names."""
    _discover_plugins()
    return sorted(_REGISTRY.keys())


def list_strategies_by_category() -> Dict[str, List[str]]:
    """Return strategies grouped by their ``category`` property."""
    _discover_plugins()
    cats: Dict[str, List[str]] = {}
    for name, cls in sorted(_REGISTRY.items()):
        instance = cls()
        cat = instance.category
        cats.setdefault(cat, []).append(name)
    return cats


# ---------------------------------------------------------------------------
# Entry-point plugin discovery
# ---------------------------------------------------------------------------

_PLUGINS_LOADED = False


def _discover_plugins() -> None:
    """Load community strategies from the ``crdt_merge.model_strategies`` entry-point group."""
    global _PLUGINS_LOADED
    if _PLUGINS_LOADED:
        return
    _PLUGINS_LOADED = True

    try:
        if sys.version_info >= (3, 12):
            from importlib.metadata import entry_points
            eps = entry_points(group="crdt_merge.model_strategies")
        else:
            from importlib.metadata import entry_points as _ep
            all_eps = _ep()
            if isinstance(all_eps, dict):
                eps = all_eps.get("crdt_merge.model_strategies", [])
            else:
                eps = all_eps.select(group="crdt_merge.model_strategies") if hasattr(all_eps, "select") else []
    except Exception:
        return

    for ep in eps:
        try:
            ep.load()
        except Exception:
            pass


def _reset_registry() -> None:
    """Reset registry — for testing only."""
    global _PLUGINS_LOADED
    _REGISTRY.clear()
    _PLUGINS_LOADED = False
