"""Prove a translation: compare absolute placements, not text.

A niess submodule will never emit byte-identical McStas to the file it replaces --
different names, different ordering, extra metadata. What must match is where the
components actually are.
"""
from pathlib import Path

INSTR = Path(__file__).parent / 'teaching_hand_written.instr'


def main(outdir: Path) -> None:
    # --8<-- [start:verify]
    from mccode_antlr import Flavor
    from mccode_antlr.assembler import Assembler
    from niess.nexus import load_instr
    from niess.teaching import Primary

    original = load_instr(INSTR)

    assembler = Assembler('teaching', flavor=Flavor.MCSTAS)
    Primary.from_calibration().to_mccode(assembler)
    translated = assembler.instrument

    # resolve_orientations() gives each component's absolute placement
    before = original.resolve_orientations()
    after = translated.resolve_orientations()

    for name in (c.name for c in original.components):
        assert name in after, f'{name} missing from the translation'
        assert before[name].position() == after[name].position(), name
    # --8<-- [end:verify]

    assert len(before) == len(after) == 7


if __name__ == '__main__':
    main(Path('.'))
