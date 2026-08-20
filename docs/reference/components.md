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
| `DiscChopper` | `DiskChopper` | `radius`, `angle` or `windows`, `frequency` or `velocity`, `delay`, `width`, `height`, `offset` |
| `MultiSlitChopper` | one `DiskChopper` **per opening** | as `DiscChopper`, plus `top_dead_center` and `beam_position`, with `windows` holding two edges per opening |

`DiscChopper` declares `{name}speed` and `{name}delay` as instrument parameters, and
accepts a single opening only. A disc whose openings are neither identical nor evenly
spaced is a `MultiSlitChopper`: it emits one `DiskChopper` per opening, sharing one
speed and delay, places them in one McStas `GROUP` so a neutron passes if it clears any
opening, and tags them so `niess.nexus` rebuilds them as a single `NXdisk_chopper`. Its geometry follows that NeXus class: angles positive
counter-clockwise facing +z, slit edges positive and increasing from the disc's
top-dead-centre mark, and a final edge beyond 360 where the last opening straddles the
mark. See
[composites](../how-to/new-instrument-submodule.md#composites-when-one-object-is-several-components).
`offset` shifts the disc centre off the beam axis; `Component.to_mccode` adds it to the
position. Only a single window is supported.

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
