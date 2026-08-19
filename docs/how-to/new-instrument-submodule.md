# Build a new instrument submodule

This guide builds `niess.teaching`, a complete but deliberately small instrument: a
moderator, two guide units in their own section, a chopper, a jaw, a monitor and a
sample position. It ships with niess, so you can read every file referenced here, and
it is assembled and converted by the test suite, so none of it can quietly stop working.

`niess.bifrost` is the real-world example. It is the same patterns at 358 components,
which is why this guide does not start there.

## What you are writing

```
src/niess/teaching/
├── __init__.py       what the submodule exports
├── parameters.py     the numbers: one calibration dictionary per section
└── primary.py        the structure: which components, in what order
```

The split matters. `parameters.py` holds measured quantities and nothing else;
`primary.py` holds structure and nothing else. A recalibration touches only the first,
and a design change touches only the second.

## 1. Declare the structure

A `Section` is an ordered list of typed fields. There is no method to write:

```python
--8<-- "src/niess/teaching/primary.py:sections"
```

Two rules that are easy to get wrong and quiet when you do:

!!! warning "Declaration order is beam order"

    `Section.from_calibration` constructs its fields **positionally**, in the order
    they are declared here, so the declaration order must match the physical beamline.

    The calibration dictionary's *key* order does not matter: each field is looked up
    by name. The dictionaries in this package happen to be written in beam order too,
    which makes them easier to read against the class, but nothing enforces it.

!!! note "Underscored fields are extras, not components"

    A field whose name starts with `_` is a per-class setting rather than a component,
    and is invisible to `parts()`, `types()`, `items()` and `field_types()`. Add as
    many as your section needs. They carry defaults, so msgspec requires them **after**
    the fields that do not — which is why `_flat` is declared last.

`_flat = True` means "emit into the assembler I was given". Without it a section nests
itself: `Guides` has no `_flat`, so it becomes an included sub-instrument called
`teaching_guides` — `assembler.included(f'{assembler.name}_guides')`.

## 2. Write the calibration

Every dimensional quantity is a scipp `Variable` with the unit the drawing uses.
Nothing converts to metres here; that happens once, in `__mccode__`.

A component's `position` and `orientation` are its placement in the instrument
coordinate system. How you arrive at them is up to you.

`niess.bifrost` chains them, because that is how its geometry is specified: each
element so far past the one before it. Each section builder takes the position and
orientation of what came before, places its own components relative to that with
`niess.spatial.at_relative`, and returns the reference for what comes next — the direct
analogue of `AT (0, 0, d) RELATIVE previous`:

```python
--8<-- "src/niess/teaching/parameters.py:chain"
```

Because the chain is computed rather than typed, moving the guide moves everything
downstream of it and no number is written twice.

!!! tip "Chaining is a convenience, not a requirement"

    If you already know where things are — from a survey, a CAD model, or an existing
    instrument definition — put those coordinates in the calibration directly and skip
    `at_relative` entirely:

    ```python
    --8<-- "direct_positions.py:direct"
    ```

    That produces the same instrument as the chained calibration, to the last bit.
    Chain when the geometry is genuinely specified as a chain of offsets, so that
    moving one element carries the rest with it; write coordinates out when they are
    known independently and a chain would only obscure them. The two styles can be
    mixed within one instrument.

Three quantities in the teaching instrument are *run-time* values rather than
constants, and each gets there differently:

- `source_lambda_min` / `source_lambda_max` — passed in the calibration as McCode
  parameter specification strings (`'source_lambda_min/"angstrom" = 0.75'`), which
  `ESSource` turns into `DEFINE INSTRUMENT` arguments.
- `chopperspeed` / `chopperphase` — `DiscChopper` declares these itself.
- `jaw_l` / `jaw_r` — `Jaw` declares these itself.

You only need `ensure_runtime_line(assembler, 'name/"unit" = default')` when writing
your own component that needs a knob no existing class provides.

## 3. Assemble it

```python
--8<-- "build_teaching.py:assemble"
```

That produces exactly seven McStas components and six instrument parameters. The
[example asserts both](https://github.com/mcdotstar/niess/blob/main/docs/examples/build_teaching.py),
so this page cannot drift from what the code does.

## Writing a component

If nothing in [the component reference](../reference/components.md) fits, a new
`Component` subclass is three things:

1. **Typed fields** for its calibrated properties, as scipp `Variable`s.
2. **`from_calibration(cls, cal)`** pulling each field out of the dictionary, with
   defaults and any accepted aliases.
3. **`__mccode__(self)`** returning `(component_type_name, parameters)` — and this is
   the *only* place units are converted, with `.to(unit='m').value`.

Optionally `__mccode_role__()` and `__mccode_extra__()`, which record what the thing is
in the provenance metadata that the CAD and NeXus adapters dispatch on.

### Contributing to the instrument around it

`__mccode__` says what the component *is* — one `COMPONENT` line and its parameters.
Real components often need more than that from the instrument they sit in: a knob the
operator can turn, a value worth computing once at start-up, a lookup table, a flag that
later components read.

Overriding `to_mccode` is the supported way to add those. Do the work, then delegate:

```python
--8<-- "component_to_mccode.py:component"
```

The helpers, and what each one writes into the generated instrument:

| call | lands in | use it for |
| --- | --- | --- |
| `ensure_runtime_line(a, 'name/"unit" = default')` | `DEFINE INSTRUMENT(...)` | a knob settable at run time |
| `ensure_runtime_parameter(a, parameter)` | `DEFINE INSTRUMENT(...)` | the same, from an `InstrumentParameter` you already hold |
| `a.declare('double name;')` | `DECLARE` | an internal variable with instrument scope |
| `a.initialize('name = ...;')` | `INITIALIZE` | computing that variable once, before the first neutron |
| `a.declare_array('double', name, values)` | `DECLARE` | a lookup table too large to inline |
| `ensure_user_var(a, 'int', name, description)` | `USERVARS` | a per-particle flag later components read |
| `ensure_registry(a, 'owner/repo@version')` | the component search path | a `.comp` McStas does not ship |
| `a.metadata(name, mimetype, value)` | a `METADATA` block | information for a downstream consumer, such as a stream configuration |

All of the `ensure_*` helpers are idempotent by name: two instances of the same class
can each ask for the same user variable or registry, and the second is a no-op. An
*inconsistent* repeat — the same parameter name with a different default or unit —
raises rather than silently picking one.

Anything derived from the component's own calibration should be computed in Python and
emitted as a literal. Reserve `DECLARE`/`INITIALIZE` for values that depend on a
run-time parameter, as `gate_window` does above, since those genuinely cannot be known
until the instrument runs.

Three worked patterns in the shipped library, in increasing order of involvement:

- `niess/components/aperture.py::Jaw` — declares two run-time parameters, then delegates.
- `niess/components/chopper.py::DiscChopper` — the same, plus the `offset` convention
  for a component whose centre is off the beam axis.
- `niess/components/guide.py::EllipticGuide` — emits its per-segment m-values as
  `DECLARE`d arrays when the guide is segmented.
- `niess/components/monitors.py::FrameMonitor` — pulls in an external component
  registry and attaches stream metadata.

## Composites: when one object is several components

A detector bank is one niess object and many McStas instances. Write a `Base` subclass
with its own `to_mccode` that calls `assembler.component(...)` directly — and then:

!!! danger "Tag every instance you build by hand"

    `Component.to_mccode` tags what it emits; hand-built instances are yours to tag:

    ```python
    add_niess_metadata(instance, self, role='physical-component')
    ```

    Forget it and nothing fails. The instance simply becomes invisible to every
    adapter — missing from the STEP assembly, missing from the NeXus file — with no
    error to notice. `tests/test_provenance_coverage.py` enforces this for niess's own
    composites.

Two more rules for composites:

- **`ensure_registry(assembler, 'owner/repo@version')`** for components McStas does not
  ship. Prefer a tag over `@main`: `@main` is not reproducible for anyone who builds
  your instrument later.
- **Never derive a name from `assembler.name`.** Inside a nested section that is the
  *section's* name. Use `instrument_name(assembler)`, which walks to the root. This is
  a real bug that shipped: monitors inside sections published to
  `bifrost_curved_beam_monitor`, a topic nothing subscribes to.

## Always pass `rotate=`

`to_mccode(assembler, at, rotate)` defaults an omitted `rotate` to `ABSOLUTE`. A
component positioned in a rotating frame but left rotated absolutely looks correct
until the frame turns, and then quietly points the wrong way. This shipped too — see
`tests/test_bifrost_tank.py::test_elastic_monitor_is_placed_and_rotated_in_the_tank_frame`.

## What you get for free

- **Serialisation** — `to_dict`/`from_dict` and `niess.io.json`, with scipp-aware
  equality. Register a top-level type in `MODEL_ENCODE` (`niess/io/utils.py`) to make
  it round-trip.
- **NeXus** — [conversion](nexus-structure.md) with no extra work, and
  [custom translators](custom-nexus-registry.md) when the defaults are not enough.
- **CAD** — a STEP assembly via `niess.brep`.

## Checklist

- [ ] `parameters.py` holds every number, as scipp `Variable`s, chained with `at_relative`
- [ ] Section fields are in beam order and match the calibration key order
- [ ] Underscored extras come after the component fields (msgspec requires it)
- [ ] Hand-built instances call `add_niess_metadata`
- [ ] Non-standard components call `ensure_registry`
- [ ] Names derive from `instrument_name(assembler)`, never `assembler.name`
- [ ] Every `to_mccode` call passes `rotate=`
- [ ] Top-level types registered in `MODEL_ENCODE` for JSON round-trip
- [ ] Tests mirroring `tests/test_bifrost_primary.py` and `tests/test_provenance_coverage.py`
