"""Connector registry."""
from __future__ import annotations

from typing import Dict, Type

_REGISTRY: Dict[str, Type] = {}


def register(cls: Type) -> Type:
    name = getattr(cls, "name", None)
    if not name:
        raise ValueError(f"connector {cls!r} must define a class-level `name`")
    if name in _REGISTRY and _REGISTRY[name] is not cls:
        raise ValueError(f"duplicate connector name: {name}")
    _REGISTRY[name] = cls
    return cls


def get_connector(name: str) -> Type:
    if name not in _REGISTRY:
        raise KeyError(name)
    return _REGISTRY[name]


def available() -> Dict[str, Type]:
    return dict(_REGISTRY)
