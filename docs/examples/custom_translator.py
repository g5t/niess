"""Write a translator for a component niess.nexus does not know, and register it.

The teaching instrument's jaw converts to a generic NXaperture. Suppose this
instrument's jaw is really a beam-defining diaphragm that downstream tooling expects
as an NXslit with its own opening datasets: that is a translator plus a registry.
"""
from pathlib import Path


def main(outdir: Path) -> None:
    from mccode_antlr import Flavor
    from mccode_antlr.assembler import Assembler
    from niess.teaching import Primary

    # --8<-- [start:registry]
    from niess.nexus import (
        DEFAULT_NEXUS_REGISTRY, NiessNexusRegistry, component_body, dataset,
    )

    # Extend the default registry rather than modifying it, so these translators
    # apply only to conversions that ask for this registry.
    TEACHING_REGISTRY = NiessNexusRegistry(parent=DEFAULT_NEXUS_REGISTRY)


    @TEACHING_REGISTRY.register_component_type('Slit')
    def diaphragm_translator(t):
        """Translate a Slit into an NXslit carrying its run-time opening."""
        return component_body('NXslit', [
            dataset('description', f'beam-defining diaphragm {t.name}'),
            # x_gap is driven at run time, so this emits a link, not a number
            t.parameter_node('x_gap', source='xmax', attrs={'units': 'm'}),
            t.parameter_node('y_gap', source='yheight', dtype=float, attrs={'units': 'm'}),
        ])
    # --8<-- [end:registry]

    assembler = Assembler('teaching', flavor=Flavor.MCSTAS)
    Primary.from_calibration().to_mccode(assembler)

    # --8<-- [start:use]
    from niess.nexus import to_nexus_structure

    structure = to_nexus_structure(
        assembler.instrument, origin='sample_origin', registry=TEACHING_REGISTRY,
    )
    # --8<-- [end:use]

    from niess.nexus import find_child, get_attribute
    instrument = structure['children'][0]['children'][0]
    jaw = find_child(instrument, 'jaw')
    assert get_attribute(jaw, 'NX_class') == 'NXslit'
    assert find_child(jaw, 'description') is not None
    # jaw_r is an instrument parameter, so x_gap became a link to its NXlog
    assert get_attribute(find_child(jaw, 'x_gap'), 'NX_class') == 'NXlog'

    # The default registry is untouched: the same instrument still converts the old way
    plain = to_nexus_structure(assembler.instrument, origin='sample_origin')
    plain_jaw = find_child(plain['children'][0]['children'][0], 'jaw')
    assert get_attribute(plain_jaw, 'NX_class') == 'NXaperture'


if __name__ == '__main__':
    main(Path('.'))
