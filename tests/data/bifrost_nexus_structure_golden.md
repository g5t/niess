# BIFROST NeXus Structure golden baseline

`bifrost_nexus_structure_golden.json.gz` is the output of `moreniius` (the package
`niess/nexus/` replaces) for the BIFROST instrument in `bifrost.instr.json.gz`, captured
before the port so there is a regression target that outlives `moreniius`.

Regenerated with:

```python
from moreniius import MorEniius
from moreniius import additions          # registers the BIFROST-specific translators
me = MorEniius.from_mccode(instr, origin='sample_origin', only_nx=False,
                           absolute_depends_on=False)
json.dumps(me.to_nexus_structure(), indent=2, sort_keys=True)
```

Importing `moreniius.additions` matters: it is imported only inside
`moreniius.nexus_structure.to_nexus_structure()`, so a golden captured through
`MorEniius.from_mccode` alone silently omits every BIFROST translator, leaving all 45
analyzers and 45 detector triplets as empty `NXcoordinate_system` groups. `moreniius`'s
own `tests/test_bifrost_nexus_structure.py` calls `from_mccode` directly and therefore
never exercised those translators either.

## Parity

`niess.nexus.to_nexus_structure` reproduces this file's structure: identical component
names in identical order, and an identical `NX_class` census (132 `NXcoordinate_system`,
119 `NXguide`, 45 `NXcrystal`, 45 `NXdetector`, 6 `NXdisk_chopper`, 5 `NXmonitor`,
5 `NXaperture`, 1 `NXmoderator`, 2 datasets).

766 leaf differences remain. Every one falls into a category below; none is unexplained.
`tests/test_nexus_bifrost_golden.py` asserts exactly this classification, so a new
difference fails the suite rather than passing unnoticed.

## Classified differences

### 1. Flattened `OFF_GEOMETRY` groups — 540 differences (90 `Guide_gravity` × 6 keys)

**A `moreniius` bug that this port fixes.** `moreniius.mccode.instr.NXInstr.expr2nx`
contains

```python
if not isinstance(expr, str) and hasattr(expr, '__iter__'):
    return [self.expr2nx(x) for x in expr]
```

and a `nexusformat` group *is* iterable — over its child **names**. Any group routed
through `make_nx` is therefore replaced by a list of strings. `guide_translator` passes
its `NXoff_geometry` through `make_nx`, so the golden records

```json
{"module": "dataset", "config": {"name": "OFF_GEOMETRY", "type": "string",
                                 "values": ["vertices", "winding_order", "faces"]}}
```

— the geometry itself is gone. This port emits the real `NXoff_geometry` group with its
`vertices`, `winding_order` and `faces` datasets.

Only translators that go through `make_nx` are affected. `elliptic_guide_gravity_translator`
and `monitor_translator` construct their group directly, so the 29 elliptic guides and
5 frame monitors kept real geometry — and this port reproduces those 34 groups exactly,
byte for byte. The asymmetry is visible within the golden itself: 34 components carry
real `NXoff_geometry` groups while the 90 `Guide_gravity` instances carry a list of
three strings.

### 2. Flattened `NXpositioner` groups — 180 differences (5 `Slit` × 6 positioners × 6 keys)

Same root cause. `slit_translator` builds one `NXpositioner` per aperture dimension and
passes them through `make_nx`, so each collapses to `{"values": ["value"]}`. This port
emits proper `NXpositioner` groups containing `name` and `value`.

The golden lists only `value`, not `name`: `nexusformat` took the translator's `name`
field for the group's own name rather than storing it as a child, so that dataset was
lost before the flattening even happened. This port emits both.

### 3. `detector_number` dtype — 45 differences (one per detector triplet)

The golden says `int64`, this port says `int32`. `moreniius`'s own translator writes
`np.array(detector_number).astype('int32')`, so int32 is the author's stated intent; its
writer then discarded it, because `convert_types` calls `.tolist()` and reads the dtype
off the resulting Python `int`. This port honours the declared dtype.

`cylinders` is deliberately **not** narrowed: the registered translator passes a plain
Python list, expressing no int32 intent, so it stays `int64` and matches the golden.

### 4. `mcstas` instrument source — 1 difference

The verbatim `str(instr)` dump differs by a single trailing newline, which `nexusformat`
stripped. Cosmetic.

## Not represented here

The BIFROST instrument parameterises its components with *instrument* parameters, not
DECLARE'd variables, so it does not exercise the DECLARE constant-folding fix. That is
covered by `tests/test_nexus_declare_variables.py`.
