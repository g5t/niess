# Narrow the wavelength band to what the choppers pass

A source samples uniformly across the band it is given, and a chopper train throws most of
that away. Every neutron absorbed at the first chopper cost something to create, so
telling the source to only sample wavelengths that can reach the sample is free simulation
speed.

`niess.chopcalc` works that band out from the instrument itself.

```python
--8<-- "narrow_band.py:narrow"
```

Call it once the instrument is complete — after every section and every hand-added
component, and before writing it out. It needs the top-level `Assembler`: a child from
`assembler.included(...)` merges into its parent only when the block exits, so a section's
own choppers are not visible from inside it.

## Why this is C rather than Python

The band depends on chopper speeds and delays, and those are run-time parameters — the
whole point of emitting `chopperspeed` and `chopperdelay` rather than numbers. So the
calculation cannot happen when the instrument is built. `chopcalc` emits a call to
[chopper-lib](https://github.com/mcdotstar/mcstas-chopper-lib) into the instrument's
`INITIALIZE` instead, which McCode runs *before* every component's own initialisation.
The source therefore reads the narrowed values, and

```shell
./teaching -n 1e7 chopperdelay=0.006
```

recomputes the band without rebuilding anything. The instrument says what it did:

```
niess.chopcalc: sampling 0.5 to 2.51491 AA instead of 0.5 to 10 AA.
```

## What it needs from the source

The wavelength limits have to be **instrument parameters**, because the generated C writes
through their addresses. In a niess calibration that means giving them as parameter
specifications rather than values:

```python
'wavelength_minimum': 'source_lambda_min/"angstrom" = 0.75',
'wavelength_maximum': 'source_lambda_max/"angstrom" = 30.0',
```

A literal is refused, with that fix in the message.

The source is found from the beam path — it is the one component neutrons enter at, so it
is a root of the particle flow graph. That matters because a wavelength monitor is not a
source but looks like one: `L_monitor`, `TOFLambda_monitor`, `DivLambda_monitor`,
`PolLambda_monitor` and `MeanPolLambda_monitor` all take `Lmin` and `Lmax`. Pass
`source='...'` when an instrument has more than one entry point.

## What it leaves out, and why that is safe

Leaving a chopper out of the calculation can only make the band **wider**, never narrower,
so it never discards a neutron that would have passed. That is what makes the following
conservative rather than wrong:

| left out | because |
| --- | --- |
| a disc in a McStas `GROUP` with no niess provenance | grouped discs are alternatives, not a series, and there is nothing to reconstruct an envelope from |
| a Fermi chopper | chopper-lib's `chopper_parameters` cannot describe one |
| a disc whose speed, opening or delay is unset | there is no row to write |

A **multi-slit disc** is not left out but approximated. chopper-lib intersects chopper
acceptances, while a disc's openings are alternatives — so one row per opening would demand
a neutron clear every opening at once, giving a band too narrow, which is the one failure
that loses neutrons. `chopcalc` uses the disc's angular envelope instead, spanning its
first opening's edge to its last. That admits the gaps between openings too, so the band
comes out wider than the disc really passes, and it warns every time:

```
niess.chopcalc: multi-opening disc 'pack' (pack_slit_0, pack_slit_1) is modelled as its
50 degree angular envelope, ... Revisit when chopper-lib grows a
multi_chopper_inverse_velocity_limits.
```

A disc whose openings span a full revolution constrains nothing and is dropped outright.

One case stops the calculation altogether rather than approximating it: a chopper with
`isfirst=1` re-times neutrons instead of absorbing them, so every downstream delay is
measured from a different zero and the chopper-train model does not apply.

## Flight paths

Path lengths are walked along the beam — `Instr.build_flow_graph()`, then the summed
segments from the source — rather than measured straight, so a curved guide is followed
instead of cut across. A chopper's emitted `AT` is already the point where the beam crosses
its disc, which is what a niess `offset` converts to, so no further correction is needed.

If the beam has to turn sharply to arrive at a component, `chopcalc` says so: that usually
means the component is placed at its spindle rather than on the beam, which would also make
it absorb every neutron at run time. `path_lengths={'chopper': 15.02}` overrides a measured
path when the real one is known by other means.
