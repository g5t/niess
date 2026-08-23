"""Builder lookup for the ``tof`` target."""
from __future__ import annotations

from typing import Any, Callable

from ..dispatch import NiessRegistry

TofBuilder = Callable[[Any], Any | None]


class NiessTofRegistry(NiessRegistry[TofBuilder]):
    """Three-tier builder lookup: niess source type, niess role, McCode type.

    As everywhere else, ``resolve_builder`` returning ``None`` means *nothing is
    registered*, while a builder returning ``None`` means it ran and declined -- which is
    how an opening folded into its disc says so.
    """


DEFAULT_TOF_REGISTRY = NiessTofRegistry()
