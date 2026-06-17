"""Compatibility helpers for differing django-mindoff CRUD signatures."""

from __future__ import annotations

import inspect
from functools import lru_cache

from django_mindoff import mo_crud_kit


@lru_cache(maxsize=None)
def _crud_params(method_name: str) -> set[str]:
    method = getattr(mo_crud_kit, method_name)
    return set(inspect.signature(method).parameters)


def mindoff_create_kwargs(validation_level: str) -> dict:
    """Build create kwargs compatible with the installed Mindoff version."""
    params = _crud_params("create")
    if "validation_level" in params:
        return {"validation_level": validation_level}
    if "is_validate" in params:
        return {"is_validate": validation_level != "none"}
    return {}


def mindoff_update_kwargs(validation_level: str, *, skip_db_fill: bool = False) -> dict:
    """Build update kwargs compatible with the installed Mindoff version."""
    params = _crud_params("update")
    kwargs = {}
    if "validation_level" in params:
        kwargs["validation_level"] = validation_level
    elif "is_validate" in params:
        kwargs["is_validate"] = validation_level != "none"

    if "skip_db_fill" in params:
        kwargs["skip_db_fill"] = skip_db_fill
    return kwargs
