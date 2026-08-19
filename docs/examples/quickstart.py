"""The landing-page example: build BIFROST, convert it to NeXus Structure JSON.

Also the README's example, asserted here so the two cannot diverge.
"""
from pathlib import Path


def main(outdir: Path) -> None:
    # --8<-- [start:quickstart]
    from mccode_antlr import Flavor
    from mccode_antlr.assembler import Assembler
    from niess.bifrost import Primary, Tank
    from niess.bifrost.parameters import primary_parameters, tank_parameters
    from niess.nexus import to_nexus_structure
    from niess.nexus.bifrost import BIFROST_REGISTRY

    assembler = Assembler('bifrost', flavor=Flavor.MCSTAS)
    Primary.from_calibration(primary_parameters()).to_mccode(assembler)
    Tank.from_calibration(tank_parameters()).to_mccode(assembler, 'sample_origin')

    structure = to_nexus_structure(
        assembler.instrument, origin='sample_origin', registry=BIFROST_REGISTRY,
    )
    # --8<-- [end:quickstart]

    assert len(assembler.instrument.components) == 358
    instrument = structure['children'][0]['children'][0]
    assert len(instrument['children']) > 350


if __name__ == '__main__':
    main(Path('.'))
