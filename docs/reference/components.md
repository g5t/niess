# Components

Everything in `niess.components`, and the McStas component each one emits. Use this
when mapping a `.instr` `TRACE` onto niess classes.

Every class takes at least `name`, `position` (a scipp vector) and `orientation` (a
scipp quaternion), and is built from a calibration dictionary with
`SomeClass.from_calibration({...})`.

## Sources

| niess class | emits | calibration keys |
| --- | --- | --- |
| `ESSource` | `ESS_butterfly` | `sector`, `beamline`, `height`, `cold_fraction`, `focus_distance`, `focus_width`, `focus_height`, `cold_performance`, `thermal_performance`, `wavelength_minimum`, `wavelength_maximum`, `latest_emission_time`, `n_pulses`, `accelerator_power` |

`wavelength_minimum` and `wavelength_maximum` accept a McCode instrument-parameter
specification string such as `'source_lambda_min/"angstrom" = 0.75'` instead of a
value, which turns them into run-time arguments of the generated instrument.

## Guides

| niess class | emits | calibration keys |
| --- | --- | --- |
| `StraightGuide` | `Guide_gravity` | `length`, `width`, `height`, `m` (or `left`/`right`/`top`/`bottom`) |
| `TaperedGuide` | `Guide_gravity` | `length`, `in_width`, `out_width`, `in_height`, `out_height` (or `width`/`height` for both ends), m-values as above |
| `EllipticGuide` | `Elliptic_guide_gravity` | `length`, `horizontal`, `vertical` (each `{major, minor, offset}` or `{in, out, midpoint\|entry\|exit}`), m-values as above |
| `StraightGuides`, `TaperedGuides` | one instance per segment | a dictionary of segment dictionaries |

`EllipticGuide` also accepts an array `length` with tuple m-values, which emits a
segmented guide with `DECLARE`d arrays.

## Apertures

| niess class | emits | calibration keys |
| --- | --- | --- |
| `Jaw` | `Slit` | `width`, `height` |
| `Slit` | `Slit` | `width`, `height` |

Both are *run-time adjustable*, which is the point of them: `Jaw` declares the
instrument parameters `{name}_l` and `{name}_r`, and `Slit` declares those plus
`{name}_b` and `{name}_t`. Their openings become links in the NeXus output rather than
fixed numbers.

## Choppers

| niess class | emits | calibration keys |
| --- | --- | --- |
| `DiscChopper` | `DiskChopper` | `radius`, `angle` or `windows`, `frequency` or `velocity`, `delay`, `width`, `height`, `zero_angle`, `beam_angle` |
| `MultiSlitChopper` | one `DiskChopper` **per opening** | as `DiscChopper`, with `windows` holding two edges per opening |

A disc chopper's `position` is its **spindle**; the emitted `AT` is the point the beam
crosses the disc. `zero_angle` and `beam_angle` say where that point is — measured
counter-clockwise about +z, the first from the local +y axis to the disc's zero mark and
the second from the mark to the beam — and the vector between the two follows from them,
along with the rotation the emitted component carries so the disc ends up on the correct
side of the beam. Both default to zero, which puts the beam at the top of the disc; a disc
hanging above the beam has `beam_angle = 180`.

There is no `offset` to give. It was a field until the angles replaced it, and a
calibration that still sets one is refused rather than ignored — reading a placement
instruction as though it were absent would move the disc off the beam, where it absorbs
every neutron without saying so. `disc_beam_offset` is the one formula, and calibration
code that knows where the beam runs and needs the spindle negates what the chopper
derives going the other way.

`DiscChopper` declares `{name}speed` and `{name}delay` as instrument parameters, and
accepts a single opening only. A disc whose openings are neither identical nor evenly
spaced is a `MultiSlitChopper`: it emits one `DiskChopper` per opening, sharing one
speed and delay, places them in one McStas `GROUP` so a neutron passes if it clears any
opening, and tags them so `niess.nexus` rebuilds them as a single `NXdisk_chopper`. Its geometry follows that NeXus class: angles positive
counter-clockwise facing +z, slit edges positive and increasing from the disc's
top-dead-centre mark, and a final edge beyond 360 where the last opening straddles the
mark. See
[composites](../how-to/new-instrument-submodule.md#composites-when-one-object-is-several-components).
Only a single window is supported per emitted `DiskChopper`, which is why a disc with
several openings emits one apiece.

`delay` is a time, not an angle: it is when an opening's centre is at the beam, which is
what McStas' `DiskChopper` acts on and what a real chopper is set with. The component
also accepts a `phase` in degrees, but only converts it to a delay and then ignores it
([McCode#2347](https://github.com/mccode-dev/McCode/issues/2347) covers the two not being
exact inverses), so niess emits `delay` and never `phase`.

## Monitors

All monitors emit `Frame_monitor` and attach a da00 histogram-stream configuration as
`METADATA`, published to `{instrument}_beam_monitor` unless
[told otherwise](../how-to/nexus-structure.md#choosing-how-a-monitor-streams).

| niess class | calibration keys |
| --- | --- |
| `FissionChamber` | `width`, `height`, `thickness` |
| `He3Monitor` | `radius`, `length`, `pressure` |
| `BeamCurrentMonitor` | `width`, `height`, `thickness`, `sample_rate` |
| `GEM2D` | `width`, `height`, `thickness`, `x_strips`, `y_strips` |

`BeamCurrentMonitor`'s `sample_rate` sets its time binning. `GEM2D`'s strip counts are
accepted but not yet used in the emitted component.

## Filters and attenuators

| niess class | emits | calibration keys |
| --- | --- | --- |
| `NCrystalFilter` | `Filter_sample` | `width`, `height`, `length`, `composition`, `temperature` |
| `Attenuator` | `Filter_sample` | as `NCrystalFilter` |
| `OrderedFilter` | `Filter_sample` | as `NCrystalFilter`, plus `tau` |
| `RadialFilterCollimator` | `Radial_col_filter` | radii, `composition`, `temperature` |

`Attenuator` adds an `int {name}_in = 0` instrument parameter and a matching `WHEN`, so
it can be moved in and out of the beam at run time. `RadialFilterCollimator` needs the
`mcdotstar/mcstas-radial-filter-collimator@main` component registry.

## Declared but not implemented

!!! warning "These emit an `Arm`"

    The classes below have no `__mccode__`, so they inherit `Component`'s, which emits
    an `Arm`. Some are abstract bases you are meant to subclass; the rest are simply
    unfinished. Either way, placing one in an instrument silently gives you a bare
    coordinate frame where you expected a component.

| niess class | why |
| --- | --- |
| `Aperture`, `Chopper`, `Guide`, `Filter` | abstract bases — use a concrete subclass |
| `Moderator` | a stub |
| `Collimator`, `SollerCollimator`, `RadialCollimator` | declared, not implemented |
| `FermiChopper` | declared, not implemented |

If you need one of the unimplemented ones, writing it is three methods — see
[Build a new instrument submodule](../how-to/new-instrument-submodule.md#writing-a-component).

## Not placed directly

`Wire`, `DiscreteWire`, `DiscreteTube`, `He3Tube`, `IdealCrystal` and `Crystal` are
building blocks used *inside* composites such as `niess.bifrost`'s detector triplets,
rather than placed in a beamline themselves. `DirectSecondary` and `IndirectSecondary`
are data-reduction views produced by `Tank.to_secondary()`, not conversion targets.
