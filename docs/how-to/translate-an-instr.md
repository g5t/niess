# Translate a McStas `.instr`

You have a working McStas model and want it as a `niess.{instrument}` submodule. This
guide walks through
[`teaching_hand_written.instr`](https://github.com/mcdotstar/niess/blob/main/docs/examples/teaching_hand_written.instr) —
a plain seven-component instrument — and ends at `niess.teaching`.

## What you gain, and what it costs

You gain calibration: quantities keep the units they were measured in, positions are
chained instead of repeated, and the same object emits McStas, NeXus and CAD. You also
gain a place to record things McStas has no concept of, such as which Kafka topic a
monitor publishes on.

The cost is real. The `.instr` file stops being the source of truth. If someone edits
it directly afterwards, the change is lost the next time the module is built. Decide
that up front.

## 1. Inventory the original

Read the instrument rather than the file — placements are already resolved for you:

```python
--8<-- "inventory_instr.py:inventory"
```

For the teaching instrument that prints seven components and four run-time parameters.
Write down, for each component: its McStas type, what it is placed relative to, and
which of its arguments are instrument parameters rather than numbers. Those three
things determine everything that follows.

## 2. Map each component onto a niess class

Work down [the component reference](../reference/components.md).

| in the `.instr` | niess class |
| --- | --- |
| `ESS_butterfly` | `ESSource` |
| `Guide_gravity` | `StraightGuide` (or `TaperedGuide`, `EllipticGuide`) |
| `DiskChopper` | `DiscChopper` |
| `Slit` with run-time `xmin`/`xmax` | `Jaw` |
| `TOF_monitor` | a `FrameMonitor` subclass — `FissionChamber` here |
| `Arm` | `Component` |

Two things to notice while mapping:

- **The jaw's opening was already run-time.** `xmin = jaw_l` in the original becomes
  free: `Jaw` declares `{name}_l` and `{name}_r` itself, so you delete those instrument
  parameters from your list rather than re-declaring them. The same goes for the
  chopper's `nu` and `phase`.
- **Nothing may fit.** If so, that component needs a `Component` subclass — three
  methods, described in
  [Writing a component](new-instrument-submodule.md#writing-a-component).

## 3. Group into sections, in beam order

Contiguous components that do one job become a `Section`. Here the two guide units
become `Guides`, and everything becomes `Primary`. Section field order must be beam
order — `Section.from_calibration` constructs positionally.

The declaration and the rules are covered in
[Build a new instrument submodule](new-instrument-submodule.md#1-declare-the-structure);
the rest of this page is the part specific to translating.

## 4. Turn the `AT` chain into a calibration

This is the actual translation work. Each `AT (0, 0, d) RELATIVE previous` becomes an
`at_relative(ref_p, ref_r, d * z)` call, and each section builder returns the reference
for the next:

| `.instr` | `parameters.py` |
| --- | --- |
| `AT (0, 0, 1.5) RELATIVE source` | `at_relative(ref_p, ref_r, 1500 * mm * z)` |
| `AT (0, 0, 2.01) RELATIVE unit_1` | chained from the previous unit's exit |
| `ROTATED (0, 3, 0) RELATIVE prev` | `mccode_quaternion(0, 3, 0)` |

Numbers keep the units the drawing uses — `1500 * mm`, `scalar(170.0, unit='deg')` —
and are converted exactly once, inside `__mccode__`.

!!! warning "Watch for offsets in the original's placement chain"

    The hand-written file places the chopper at `(0, -0.35, 3.25)`: the disc *centre*
    sits below the beam. In niess that is the chopper's `offset`, and the beam-axis
    position stays on the axis, so everything downstream chains from the axis rather
    than inheriting the drop. Translating the `AT` lines literally, component by
    component, would carry `-0.35` into every component after the chopper.

    This is exactly the class of error step 5 catches.

## 5. Prove it

Do not diff the generated text against the original — it will never match, and should
not: different names, different ordering, added metadata. Compare where the components
actually *are*:

```python
--8<-- "verify_translation.py:verify"
```

`resolve_orientations()` gives each component's absolute placement, so this asserts the
one thing that must be true: the translation puts everything in the same place as the
instrument it replaces. This example runs in niess's own test suite, which is how the
guide stays honest.

## 6. Keep the original

Commit the `.instr` you translated from as a test fixture, and keep the comparison in
step 5 as a test. It is the only thing that will tell you if a later refactor moves a
component by a millimetre.

## Checklist

- [ ] Every `COMPONENT` line mapped to a niess class, or a new subclass written
- [ ] Instrument parameters that components generate themselves removed from your list
- [ ] `AT`/`ROTATED` chains expressed with `at_relative` / `mccode_quaternion`
- [ ] Offsets modelled as `offset`, not folded into downstream positions
- [ ] Absolute placements verified against the original
- [ ] The original `.instr` kept as a fixture
