"""A small, complete instrument, written to be read.

`niess.bifrost` is the real thing, but it is 358 McStas components across nested
sections -- too much to learn from. This module is the same patterns at a size you can
hold in your head: a moderator, a nested guide section, a chopper, a jaw, a monitor,
and a sample position.

    from mccode_antlr import Flavor
    from mccode_antlr.assembler import Assembler
    from niess.teaching import Primary

    assembler = Assembler('teaching', flavor=Flavor.MCSTAS)
    Primary.from_calibration().to_mccode(assembler)

It is documented step by step in the "Build a new instrument submodule" guide.
"""
from .parameters import teaching_parameters
from .primary import Guides, Primary

__all__ = [
    'Guides',
    'Primary',
    'teaching_parameters',
]
