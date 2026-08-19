"""Convert the teaching instrument to ESS NeXus Structure JSON."""
import json
from pathlib import Path


def main(outdir: Path) -> None:
    from mccode_antlr import Flavor
    from mccode_antlr.assembler import Assembler
    from niess.teaching import Primary

    assembler = Assembler('teaching', flavor=Flavor.MCSTAS)
    Primary.from_calibration().to_mccode(assembler)

    # --8<-- [start:convert]
    from niess.nexus import to_nexus_structure

    structure = to_nexus_structure(assembler.instrument, origin='sample_origin')
    # --8<-- [end:convert]

    # --8<-- [start:inspect]
    from niess.nexus import find_child, get_attribute

    instrument = structure['children'][0]['children'][0]
    classes = {
        get_attribute(child, 'NX_class')
        for child in instrument['children'] if child.get('type') == 'group'
    }
    # --8<-- [end:inspect]
    assert classes == {
        'NXmoderator', 'NXguide', 'NXdisk_chopper',
        'NXaperture', 'NXmonitor', 'NXcoordinate_system',
    }, classes

    # A constant becomes a value; a run-time instrument parameter becomes a link to
    # the NXlog where its value will be published.
    chopper = find_child(instrument, 'chopper')
    assert abs(find_child(chopper, 'radius')['config']['values'] - 0.35) < 1e-9
    assert get_attribute(find_child(chopper, 'rotation_speed'), 'NX_class') == 'NXlog'

    # The monitor carries its histogram stream configuration
    monitor = find_child(instrument, 'monitor')
    stream = find_child(monitor, 'data')['children'][0]
    assert stream['module'] == 'da00'
    assert stream['config']['topic'] == 'teaching_beam_monitor'

    (outdir / 'teaching_nexus_structure.json').write_text(json.dumps(structure, indent=2))


if __name__ == '__main__':
    main(Path('.'))
