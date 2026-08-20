"""Only simulate the wavelengths a chopper train can actually pass.

A source samples uniformly across the band it is given, and a chopper train throws most of
that away. Narrowing the source's own ``Lmin``/``Lmax`` to the band the train passes is
free simulation speed: every neutron that would have been absorbed at the first chopper is
never created.

The band cannot be worked out when the instrument is built, because it depends on chopper
speeds and delays that are run-time parameters. So this emits C instead, calling
chopper-lib from the instrument's INITIALIZE -- which McCode runs before every component's
own initialisation, so the source reads the narrowed values.

    primary.to_mccode(assembler)
    narrow_source_wavelengths(assembler)
"""
from __future__ import annotations

import logging

from .discovery import ChopcalcError, build_train
from .emit import (CHOPPER_LIB_REGISTRY, already_emitted, declare_text,
                   include_present, initialize_text)
from .model import ChopperEntry, ChopperTrain, Exclusion, SourceEntry

logger = logging.getLogger(__name__)

__all__ = [
    'ChopcalcError',
    'ChopperEntry',
    'ChopperTrain',
    'Exclusion',
    'SourceEntry',
    'narrow_source_wavelengths',
]


def narrow_source_wavelengths(
        assembler,
        *,
        source: str | None = None,
        skip=(),
        path_lengths=None,
        latest_emission: float | None = None,
        registry: str = CHOPPER_LIB_REGISTRY,
        strict: bool = False,
) -> ChopperTrain | None:
    """Restrict the source's wavelength band to what the chopper train passes.

    Call it once the instrument is complete -- after every section and every hand-added
    component, before writing the instrument out.

    Parameters
    ----------
    assembler:
        The **top-level** assembler. A child from ``assembler.included(...)`` merges into
        its parent only when the block exits, so its choppers are not visible yet.
    source:
        The source component's name. Inferred from the beam path when omitted.
    skip:
        Chopper names to leave out deliberately. Leaving a chopper out only widens the
        band, so it is always safe.
    path_lengths:
        Flight paths in metres, by chopper name, overriding the measured ones.
    latest_emission:
        Seconds after t=0 that the source can still emit. Taken from the source when it
        says (``tmax_multiplier``); a longer time widens the band, which is the safe
        direction.
    strict:
        Raise :class:`ChopcalcError` instead of warning and doing nothing.

    Returns
    -------
    The train that was used, or ``None`` when nothing could be narrowed.
    """
    from ..mccode import ensure_registry

    if getattr(assembler, 'parent', None) is not None:
        raise ChopcalcError(
            'narrow_source_wavelengths needs the top-level Assembler, after every '
            'section has been added. A section\'s child Assembler is merged into its '
            'parent only on leaving the included() block, so its components -- and '
            'every later section\'s -- are not visible yet.'
        )

    instrument = assembler.instrument
    if already_emitted(instrument):
        return _refuse('this instrument has already been narrowed; calling '
                       'narrow_source_wavelengths twice would apply two bands', strict)

    try:
        train = build_train(instrument, source=source, skip=skip,
                            path_lengths=path_lengths, latest_emission=latest_emission)
    except ChopcalcError as error:
        return _refuse(str(error), strict)

    for exclusion in train.excluded:
        logger.warning('niess.chopcalc: leaving out %s -- %s',
                       ', '.join(exclusion.members), exclusion.reason)

    if not train.choppers:
        why = '; '.join(f'{e.name}: {e.reason}' for e in train.excluded)
        return _refuse(
            f'no chopper reached the calculation, so there is nothing to narrow'
            f'{" -- " + why if why else ""}', strict)

    ensure_registry(assembler, registry)
    if not include_present(instrument):
        assembler.declare(declare_text())
    assembler.initialize(initialize_text(train))
    logger.info(
        'niess.chopcalc: %d chopper(s) narrowing %s/%s of source %r',
        len(train.choppers), train.source.lambda_min, train.source.lambda_max,
        train.source.name,
    )
    return train


def _refuse(message: str, strict: bool) -> None:
    """Emitting nothing is always safe -- the instrument samples the band it was given."""
    if strict:
        raise ChopcalcError(message)
    logger.warning('niess.chopcalc: %s', message)
    return None
