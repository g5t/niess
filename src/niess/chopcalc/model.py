"""What discovery hands to emission.

Every field of a :class:`ChopperEntry` is C *text*, not a number. The array it becomes is
a local in ``init()``, so a field may name a run-time instrument parameter -- which is the
point: change a chopper speed on the command line and the band recomputes without a
rebuild.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChopperEntry:
    """One row of the generated ``chopper_parameters`` array."""

    name: str
    """The instance name, or the disc's group id when this row is an envelope."""
    speed: str
    """Hz. The sign sets the direction of rotation, and is preserved."""
    delay: str
    """Seconds, when an opening's centre is on the path."""
    angle: str
    """Degrees. **One** opening -- chopper-lib has no notion of several."""
    path: str
    """Metres travelled from the source, along the beam."""
    note: str | None = None
    """Why this row is approximate, when it is."""


@dataclass(frozen=True)
class SourceEntry:
    """The source, and the two parameters this narrows."""

    name: str
    lambda_min: str
    """An instrument-parameter name. It has to be one: the C writes through its address."""
    lambda_max: str
    latest_emission: str
    """Seconds, as a C expression, so the arithmetic stays visible in the instrument."""
    latest_emission_note: str
    """Where that expression came from, for the generated comment."""


@dataclass(frozen=True)
class Exclusion:
    """A chopper the calculation left out, and why."""

    name: str
    members: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ChopperTrain:
    """Everything the calculation found.

    Returned so a build script can assert on what was used without reading generated C.
    """

    source: SourceEntry
    choppers: tuple[ChopperEntry, ...]
    excluded: tuple[Exclusion, ...]
