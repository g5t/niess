# Changelog

Notable changes to niess, newest first.

Versions follow [semantic versioning](https://semver.org/), with the pre-1.0 caveat that a
minor release may still remove things. 0.6.0 does, so it is a minor bump rather than a
patch; everything removed is listed below with what replaces it.

<!-- --8<-- [start:releases] -->
## 0.6.0

Choppers, twice over: described the way they are actually built and controlled, and then
put to work. A disc is now one class however many openings it has, set with a delay rather
than a phase, and placed by where its spindle is rather than by an offset someone worked
out by hand. Two new modules read that description — `niess.chopcalc` narrows a source to
the band its chopper train passes, and `niess.tof` flies neutrons through the train in a
notebook.

### Added

- **`niess.tof`** — `to_tof_model()` turns an emitted instrument into a ready-to-run
  [`tof.Model`](https://scipp.github.io/tof/), with every disc chopper and a detector at
  each monitor and at the sample. It returns a `TofSetup` rather than a bare model, which
  reports in a notebook table which run-time parameters were used and at what value, and
  `with_values()` turns one knob without rebuilding the rest. `pulses=` simulates more than
  one source pulse, which is what shows a disc running at half the source frequency doing
  its job. Install with `pip install 'niess[tof]'`.
- **`niess.chopcalc`** — `narrow_source_wavelengths()` emits a chopper-lib call into the
  instrument's `INITIALIZE` so the source samples only the band the choppers pass, which is
  free simulation speed. The band is computed at run time from the chopper parameters, so
  changing a delay on the command line recomputes it without rebuilding anything.
  `export_choppers=` publishes the train to `DECLARE` for a component that needs the
  chopper description itself rather than the band it implies.
- **A user-supplied particle-flow graph**, accepted by `to_nexus_structure()`,
  `narrow_source_wavelengths()`, `build_train()` and `to_tof_model()`. McCode has no way to
  say that a beam branches — its instruments are a list — so an instrument that splits at
  the sample, as BIFROST does, had every component past that point treated as fed by
  whichever happened to be declared before it. Passing the graph fixes both the `@inputs`
  written into NeXus and the flight paths measured through it. Omitting it derives the flow
  from declaration order, as before.
- **`zero_angle` and `beam_angle` on `DiscChopper`**, saying where the beam crosses the
  disc: counter-clockwise about +z, the first from local +y to the disc's zero mark, the
  second from the mark to the beam. A disc hanging above the beam is `beam_angle = 180`.
- **`windows` on `DiscChopper`** — slit edges from the zero mark, two per opening, for a
  disc whose openings are neither identical nor evenly spaced.
- **Extras**: `niess[tof]`, `niess[examples]` for the documentation's notebooks, and
  `niess[brep]`, which had been needed by `niess.brep` all along with no way to ask for it
  by name.
- **Documentation**: how-to guides for
  [narrowing the wavelength band](https://mcdotstar.github.io/niess/how-to/narrow-the-wavelength-band/)
  and [simulating a chopper cascade](https://mcdotstar.github.io/niess/how-to/simulate-a-chopper-cascade/),
  an API page for `niess.tof`, and a notebook joining chopcal, niess and tof on BIFROST.

### Changed

- **Disc choppers are set with a delay in seconds, not a phase in degrees.** A delay is
  what a real chopper is set with, it is what McStas' `DiskChopper` acts on, and unlike a
  phase it does not depend on which way the disc turns. `Chopper.phase` is now
  `Chopper.delay`, and the emitted instrument parameter `{name}phase` is `{name}delay`.
- **A disc chopper's `position` is its spindle.** The emitted `AT` is the point the beam
  crosses the disc, computed from `zero_angle` and `beam_angle`, along with the rotation
  that puts the disc on the correct side of the beam. Both are recorded in provenance and
  taken back out by `niess.nexus`.
- **NeXus output for disc choppers has changed**, in three ways: an `NXdisk_chopper` is
  centred on the spindle rather than on the beam crossing, it no longer carries the McStas
  frame twist as a real rotation of the disc, and its `slit_edges` are ordered as the
  standard asks. Compare files across this release rather than assuming they match.
- **chopper-lib 3.0.0 or newer is required** by `niess.chopcalc`, pinned as
  `mcdotstar/mcstas-chopper-lib@v3.0.0`, with a `#error` in the emitted C for anyone who
  overrides the registry with something older.

### Removed

- `MultiSlitChopper` — `DiscChopper` takes `windows` and emits one `DiskChopper` per
  opening, grouped, exactly as `MultiSlitChopper` did.
- `DiscChopper.offset` — give `zero_angle` and `beam_angle` instead. A calibration that
  still sets an offset is refused rather than ignored: reading a placement instruction as
  though it were absent would move the disc off the beam, where it absorbs every neutron
  without saying so.
- `DiscChopper.chopper_lib_parameters` — `niess.chopcalc` builds the chopper-lib
  description from the emitted instrument.

### Fixed

- **Rotations near ±90°.** `mccode_ordered_angles` extracted McCode's three angles by hand,
  with a gimbal-lock guard written for a different Euler convention than the formulas it
  guarded. 7 of 20000 random orientations came back as a *different* rotation, and exactly
  ±90° was handled by neither branch. It uses scipy now.
- **Components that move.** A component positioned by an instrument parameter raised out of
  `to_tof_model()` instead of being skipped, because the check for "is this a number yet"
  caught only `AttributeError` while `Expr.value` raises `NotImplementedError`. Secondary
  spectrometers on a movable tank convert now.
- **Multi-opening discs narrowed the band too little.** Such a disc was approximated by the
  single angular envelope spanning its first and last edges, so one whose openings reach
  right round admitted everything and was dropped. Describing each opening gets it back:
  for the three-slit disc in the test suite, 0.75–30 Å goes from not narrowed at all to
  2.20–13.08 Å.
- **`slit_edges` ordering.** `NXdisk_chopper` wants positive increasing edges starting with
  an opening edge, with only the final edge allowed past 360. That reordering rotates which
  slit comes first rather than shifting the list, so `[-10, 10, 60, 90]` is written
  `[60, 90, 350, 370]`, not `[350, 370, 420, 450]`.
- **The test suite passes without the optional extras**, which is what optional was supposed
  to mean. The documentation examples and notebooks skip when an extra is absent, and only
  then — an example broken any other way still fails.

### Migrating from 0.5.0

| 0.5.0 | 0.6.0 |
| --- | --- |
| `DiscChopper(..., phase=...)` | `DiscChopper(..., delay=...)`, in seconds |
| `{name}phase` run-time parameter | `{name}delay` |
| `MultiSlitChopper(..., windows=...)` | `DiscChopper(..., windows=...)` |
| `DiscChopper(..., offset=...)` | `DiscChopper(..., zero_angle=..., beam_angle=...)` |
| `chopper.chopper_lib_parameters()` | `niess.chopcalc.build_train(instrument)` |

A calibration dictionary carrying `offset` is refused with a message naming the
replacement, so an instrument submodule that has not been converted says so on the first
build rather than quietly placing a disc in the wrong place.

If you keep reference NeXus files, regenerate them: disc chopper geometry moved, for the
reasons under **Changed**.
<!-- --8<-- [end:releases] -->
