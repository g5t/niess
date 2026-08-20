"""Turn a discovered chopper train into C. Nothing here reads the instrument."""
from __future__ import annotations

from textwrap import indent

from .model import ChopperTrain

CHOPPER_LIB_REGISTRY = 'mcdotstar/mcstas-chopper-lib@v2.0.0'
CHOPPER_LIB_MINIMUM_VERSION = 20000
INCLUDE_MARKER = '%include "chopper-lib"'
ARRAY_MARKER = 'chopcalc_choppers'

DECLARE_TEXT = f'''
/* niess.chopcalc: chopper-lib, for narrowing the source wavelength band */
{INCLUDE_MARKER}
#if !defined(CHOPPER_LIB_VERSION) || CHOPPER_LIB_VERSION < {CHOPPER_LIB_MINIMUM_VERSION}
#error "niess.chopcalc sets chopper delays in seconds; chopper-lib 2.0.0 or newer is required"
#endif
'''


def declare_text() -> str:
    """The library include, and the guard that stops an older one being used silently.

    The struct layout did not change when chopper-lib's second field went from a phase in
    degrees to a delay in seconds, so without the guard a 1.x library compiles cleanly and
    computes a different band.
    """
    return DECLARE_TEXT


def initialize_text(train: ChopperTrain) -> str:
    """The whole calculation, as one braced compound statement.

    Braced so the array is scoped and ``chopcalc_*`` cannot collide with anything else in
    INITIALIZE. The array is a local with run-time initialisers -- legal for automatic
    storage, and what lets a row name an instrument parameter.
    """
    source = train.source
    rows = ',\n'.join(
        f'  {{{c.speed}, {c.delay}, {c.angle}, {c.path}}}'
        f' /* {c.name}{"" if c.note is None else " -- " + c.note} */'
        for c in train.choppers
    )

    notes = [
        f'{len(train.choppers)} chopper{"" if len(train.choppers) == 1 else "s"} '
        f'considered, path lengths walked along the beam from {source.name!r}.',
    ]
    approximate = [c for c in train.choppers if c.note]
    for chopper in approximate:
        notes.append(f'{chopper.name}: {chopper.note} -- the band comes out wider '
                     f'than this disc really passes.')
    for exclusion in train.excluded:
        notes.append(f'{exclusion.name}: left out, {exclusion.reason}.')

    body = f'''
/* niess.chopcalc: narrow {source.lambda_min}/{source.lambda_max} to the band the chopper
 * train can pass, so the source only samples wavelengths that can reach the sample.
 * Instrument INITIALIZE runs before every _setpos and every component _initialize, so
 * {source.name!r} reads the narrowed values.
{indent(chr(10).join(" * " + n for n in notes), "")}
 */
{{
  chopper_parameters {ARRAY_MARKER}[] = {{
{rows}
  }};
  double chopcalc_latest = {source.latest_emission}; /* {source.latest_emission_note}, s */
  double chopcalc_min = {source.lambda_min}, chopcalc_max = {source.lambda_max};
  unsigned chopcalc_windows = chopper_wavelength_limits(
    &{source.lambda_min}, &{source.lambda_max},
    sizeof({ARRAY_MARKER}) / sizeof(chopper_parameters), {ARRAY_MARKER},
    chopcalc_min, chopcalc_max, chopcalc_latest);
  if (chopcalc_windows == 0 || !({source.lambda_max} > {source.lambda_min})
      || {source.lambda_min} <= 0) {{
    /* chopper_wavelength_limits leaves its outputs alone when it finds nothing; putting
     * the band back makes that a property of this instrument rather than of whichever
     * library version was resolved. It also keeps a degenerate band away from
     * ESS_butterfly, whose own INITIALIZE exits when Lmin >= Lmax. */
    {source.lambda_min} = chopcalc_min;
    {source.lambda_max} = chopcalc_max;
    MPI_MASTER(printf(
      "niess.chopcalc: no usable band between %g and %g AA -- sampling unchanged.\\n"
      "niess.chopcalc: check the chopper speeds and delays; a delay is a time in "
      "seconds, and the sign of a speed sets the direction of rotation.\\n",
      chopcalc_min, chopcalc_max););
  }} else {{
    if (chopcalc_windows > 1) {{
      MPI_MASTER(printf(
        "niess.chopcalc: %u separate bands between %g and %g AA; their envelope is "
        "used, so wavelengths they block are still sampled.\\n",
        chopcalc_windows, chopcalc_min, chopcalc_max););
    }}
    MPI_MASTER(printf("niess.chopcalc: sampling %g to %g AA instead of %g to %g AA.\\n",
      {source.lambda_min}, {source.lambda_max}, chopcalc_min, chopcalc_max););
  }}
}}
'''
    return body


def already_emitted(instrument) -> bool:
    """Has a previous call already narrowed this instrument?"""
    return any(ARRAY_MARKER in str(block) for block in instrument.initialize)


def include_present(instrument) -> bool:
    return any(INCLUDE_MARKER in str(block) for block in instrument.declare)
