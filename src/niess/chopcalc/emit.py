"""Turn a discovered chopper train into C. Nothing here reads the instrument."""
from __future__ import annotations

from textwrap import indent

from .model import ChopperTrain, Export

CHOPPER_LIB_REGISTRY = 'mcdotstar/mcstas-chopper-lib@v3.0.0'
CHOPPER_LIB_MINIMUM_VERSION = 30000
INCLUDE_MARKER = '%include "chopper-lib"'
ARRAY_MARKER = 'chopcalc_choppers'
WINDOWS_MARKER = 'chopcalc_windows'

DECLARE_TEXT = f'''
/* niess.chopcalc: chopper-lib, for narrowing the source wavelength band */
{INCLUDE_MARKER}
#if !defined(CHOPPER_LIB_VERSION) || CHOPPER_LIB_VERSION < {CHOPPER_LIB_MINIMUM_VERSION}
#error "niess.chopcalc describes discs by their openings; chopper-lib 3.0.0 or newer is required"
#endif
'''


def declare_text() -> str:
    """The library include, and the guard that stops an older one being used silently.

    Nothing here changes size or layout when chopper-lib's meaning changes -- the second
    field went from a phase in degrees to a delay in seconds at 2.0.0, and a window angle
    started being placed with the signed speed at 3.0.0 -- so without the guard an older
    library compiles cleanly and computes a different band.
    """
    return DECLARE_TEXT


def export_declare_text(export: Export) -> str:
    """File-scope storage for a train a component reads.

    Declared here and filled in INITIALIZE rather than initialised in place: a row names
    instrument parameters, which are not constant expressions, so it cannot be a static
    initialiser.
    """
    return f"""
/* niess.chopcalc: the chopper train, for components that take it as a parameter.
 * Filled in INITIALIZE and released in FINALLY, so it is valid for the whole run --
 * which the narrowing's own array is not, being scoped to its block. Pass
 * (double *) {export.choppers} to a component whose parameter is declared that way.
 */
multi_chopper_parameters * {export.choppers} = NULL;
int {export.count} = 0;
"""


def initialize_text(train: ChopperTrain) -> str:
    """The whole calculation, as one braced compound statement.

    Braced so the array is scoped and ``chopcalc_*`` cannot collide with anything else in
    INITIALIZE. The array is a local with run-time initialisers -- legal for automatic
    storage, and what lets a row name an instrument parameter.
    """
    source = train.source

    # One window array per disc, named for its row. They have to be separate objects:
    # a multi_chopper_parameters row holds a pointer, not a copy, so every row needs an
    # array that outlives the call -- these are automatic in the same block, which does.
    window_arrays = '\n'.join(
        f'  chopper_window {WINDOWS_MARKER}_{i}[] = {{'
        + ', '.join(f'{{{lo}, {hi}}}' for lo, hi in c.windows)
        + f'}}; /* {c.name} */'
        for i, c in enumerate(train.choppers)
    )
    rows = ',\n'.join(
        f'    {{{c.speed}, {c.delay}, {len(c.windows)}, {WINDOWS_MARKER}_{i}, {c.path}}}'
        f' /* {c.name}, {len(c.windows)} opening{"" if len(c.windows) == 1 else "s"}'
        f'{"" if c.note is None else " -- " + c.note} */'
        for i, c in enumerate(train.choppers)
    )

    published = '' if train.export is None else _publish(train.export)

    notes = [
        f'{len(train.choppers)} chopper{"" if len(train.choppers) == 1 else "s"} '
        f'considered, path lengths walked along the beam from {source.name!r}.',
    ]
    if train.export is not None:
        notes.append(f'Also published as {train.export.choppers} / {train.export.count}, '
                     f'for a component that reads the train.')
    for chopper in (c for c in train.choppers if c.note):
        notes.append(f'{chopper.name}: {chopper.note}.')
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
{window_arrays}
  multi_chopper_parameters {ARRAY_MARKER}[] = {{
{rows}
  }};
  double chopcalc_latest = {source.latest_emission}; /* {source.latest_emission_note}, s */
  double chopcalc_min = {source.lambda_min}, chopcalc_max = {source.lambda_max};
  unsigned chopcalc_bands = multi_chopper_wavelength_limits(
    &{source.lambda_min}, &{source.lambda_max},
    sizeof({ARRAY_MARKER}) / sizeof(multi_chopper_parameters), {ARRAY_MARKER},
    chopcalc_min, chopcalc_max, chopcalc_latest);
  if (chopcalc_bands == 0 || !({source.lambda_max} > {source.lambda_min})
      || {source.lambda_min} <= 0) {{
    /* multi_chopper_wavelength_limits leaves its outputs alone when it finds nothing; putting
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
    if (chopcalc_bands > 1) {{
      MPI_MASTER(printf(
        "niess.chopcalc: %u separate bands between %g and %g AA; their envelope is "
        "used, so wavelengths they block are still sampled.\\n",
        chopcalc_bands, chopcalc_min, chopcalc_max););
    }}
    MPI_MASTER(printf("niess.chopcalc: sampling %g to %g AA instead of %g to %g AA.\\n",
      {source.lambda_min}, {source.lambda_max}, chopcalc_min, chopcalc_max););
  }}
{published}}}
'''
    return body


def _publish(export: Export) -> str:
    """Copy the train to storage that outlives the block it was built in.

    A deep copy, because a row points at its window array rather than carrying it, and
    both are automatic here. Copying the rows alone would leave every ``windows`` pointing
    into a dead frame -- which reads back plausibly for a while, and is the sort of thing
    that shows up as a wrong band on someone else's machine.
    """
    return f'''
  /* publish the train, for a component that takes it as a parameter */
  {export.count} = (int)(sizeof({ARRAY_MARKER}) / sizeof(multi_chopper_parameters));
  {export.choppers} = (multi_chopper_parameters *) calloc(
    (size_t) {export.count}, sizeof(multi_chopper_parameters));
  if ({export.choppers} == NULL) {{
    printf("niess.chopcalc: out of memory publishing {export.choppers}\\n");
    exit(-1);
  }}
  for (int chopcalc_i = 0; chopcalc_i < {export.count}; ++chopcalc_i) {{
    {export.choppers}[chopcalc_i] = {ARRAY_MARKER}[chopcalc_i];
    {export.choppers}[chopcalc_i].windows = (chopper_window *) calloc(
      (size_t) {ARRAY_MARKER}[chopcalc_i].window_count, sizeof(chopper_window));
    if ({export.choppers}[chopcalc_i].windows == NULL) {{
      printf("niess.chopcalc: out of memory publishing {export.choppers}\\n");
      exit(-1);
    }}
    for (unsigned chopcalc_w = 0;
         chopcalc_w < {ARRAY_MARKER}[chopcalc_i].window_count; ++chopcalc_w) {{
      {export.choppers}[chopcalc_i].windows[chopcalc_w] =
        {ARRAY_MARKER}[chopcalc_i].windows[chopcalc_w];
    }}
  }}
'''


def finalize_text(export: Export) -> str:
    """Give back what :func:`_publish` took."""
    return f'''
/* niess.chopcalc: release the published chopper train */
if ({export.choppers} != NULL) {{
  for (int chopcalc_i = 0; chopcalc_i < {export.count}; ++chopcalc_i) {{
    if ({export.choppers}[chopcalc_i].windows != NULL) {{
      free({export.choppers}[chopcalc_i].windows);
    }}
  }}
  free({export.choppers});
  {export.choppers} = NULL;
  {export.count} = 0;
}}
'''


def already_emitted(instrument) -> bool:
    """Has a previous call already narrowed this instrument?"""
    return any(ARRAY_MARKER in str(block) for block in instrument.initialize)


def include_present(instrument) -> bool:
    return any(INCLUDE_MARKER in str(block) for block in instrument.declare)
