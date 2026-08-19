"""A disc with unevenly spaced openings, emitted as several components and rebuilt.

McStas' ``DiskChopper`` describes ``nslit`` identical, evenly spaced openings, so a disc
with neither has to be emitted as one ``DiskChopper`` per opening -- which is what
``DiscChopper.__mccode__`` refuses to do and points at instead. ``MultiSlitChopper``
does it, and tags the instances so an adapter can put the disc back together.
"""
import pytest
from mccode_antlr import Flavor
from mccode_antlr.assembler import Assembler
from scipp import array, scalar, vector
from scipp.spatial import rotations_from_rotvecs

from niess.components import MultiSlitChopper
from niess.nexus import find_child, get_attribute, to_nexus_structure
from niess.provenance import NiessProvenance

# Angles from the top-dead-centre mark, positive counter-clockwise facing +z, as
# NXdisk_chopper wants them. The last opening straddles the mark, so it closes beyond
# 360 rather than wrapping to a smaller number.
EDGES = [10.0, 30.0, 100.0, 140.0, 350.0, 370.0]
BEAM_POSITION = 90.0


def calibration(**overrides):
    cal = {
        'name': 'pack',
        'position': vector([0, 0, 5.0], unit='m'),
        'orientation': rotations_from_rotvecs(vector([0, 0, 0.0], unit='deg')),
        'radius': scalar(0.35, unit='m'),
        'height': scalar(0.06, unit='m'),
        'frequency': scalar(14.0, unit='Hz'),
        'windows': array(values=EDGES, dims=['edges'], unit='deg'),
        'top_dead_center': scalar(15.0, unit='deg'),
        'beam_position': scalar(BEAM_POSITION, unit='deg'),
    }
    cal.update(overrides)
    return cal


@pytest.fixture
def assembled():
    assembler = Assembler('chopped', flavor=Flavor.MCSTAS)
    assembler.component('origin', 'Arm', at=((0, 0, 0), 'ABSOLUTE'))
    MultiSlitChopper.from_calibration(calibration()).to_mccode(
        assembler, at='origin', rotate='origin')
    assembler.component('sample', 'Arm', at=((0, 0, 8), 'origin'))
    return assembler.instrument


def instances(instrument):
    return [c for c in instrument.components if c.name.startswith('pack_slit_')]


# -- what it emits -----------------------------------------------------------

def test_one_component_per_opening(assembled):
    assert [c.name for c in assembled.components] == [
        'origin', 'pack_slit_0', 'pack_slit_1', 'pack_slit_2', 'sample',
    ]
    assert all(c.type.name == 'DiskChopper' for c in instances(assembled))


def test_each_opening_carries_its_own_width(assembled):
    widths = [float(str(c.get_parameter('theta_0').value)) for c in instances(assembled)]
    assert widths == [20.0, 40.0, 20.0]


def test_each_opening_turns_to_the_beam_from_where_it_sits(assembled):
    """McStas phase is how far the disc turns before an opening reaches the beam.

    Openings are centred at 20, 120 and 360 degrees from the mark; the beam sits at 90,
    so the disc turns through the difference, wrapped into one revolution.
    """
    phases = [str(c.get_parameter('phase').value) for c in instances(assembled)]
    assert phases == [
        'packphase + 70.0',    # (90 - 20)
        'packphase + 330.0',   # (90 - 120) mod 360
        'packphase + 90.0',    # (90 - 360) mod 360 -- the opening straddling the mark
    ]


def test_the_disc_has_one_speed_and_one_phase(assembled):
    """One physical disc, so one pair of run-time parameters -- not one per opening."""
    assert sorted(p.name for p in assembled.parameters) == ['packphase', 'packspeed']
    assert all(str(c.get_parameter('nu').value) == 'packspeed'
               for c in instances(assembled))


@pytest.mark.parametrize('edges,message', [
    ([0.0, 10.0, 20.0], 'even number'),
    ([-5.0, 5.0], 'negative slit edge'),
    ([30.0, 10.0], 'strictly increase'),
    ([10.0, 10.0], 'strictly increase'),
    ([370.0, 380.0], 'within one revolution'),
    ([10.0, 20.0, 100.0, 380.0], 'overlap themselves'),
], ids=['odd', 'negative', 'decreasing', 'repeated', 'starts_past_360', 'overlapping'])
def test_edges_must_follow_the_convention(edges, message):
    cal = calibration(windows=array(values=edges, dims=['edges'], unit='deg'))
    with pytest.raises(ValueError, match=message):
        MultiSlitChopper.from_calibration(cal).slits()


def test_openings_may_just_touch():
    """A last edge exactly 360 beyond the first closes where the first opens."""
    cal = calibration(windows=array(values=[10.0, 30.0, 350.0, 370.0],
                                    dims=['edges'], unit='deg'))
    assert MultiSlitChopper.from_calibration(cal).slits() == [
        (10.0, 30.0), (350.0, 370.0),
    ]


def test_a_straddling_opening_keeps_its_edge_beyond_360(assembled):
    """[350, 370] rather than [350, 10]: the pairs stay ordered and widths stay simple."""
    from niess.provenance import NiessProvenance as P

    last = instances(assembled)[-1]
    assert P.from_instance(last).extra['slit_edges'] == [350.0, 370.0]
    assert float(str(last.get_parameter('theta_0').value)) == 20.0


def test_the_offset_moves_the_whole_disc(assembled):
    cal = calibration(offset=vector([0, -0.35, 0], unit='m'))
    assembler = Assembler('chopped', flavor=Flavor.MCSTAS)
    assembler.component('origin', 'Arm', at=((0, 0, 0), 'ABSOLUTE'))
    MultiSlitChopper.from_calibration(cal).to_mccode(
        assembler, at='origin', rotate='origin')

    for instance in instances(assembler.instrument):
        assert [str(x) for x in instance.at_relative[0]] == ['0', '-0.35', '5']


# -- what it records ---------------------------------------------------------

def test_every_instance_is_tagged_as_one_group(assembled):
    provenances = [NiessProvenance.from_instance(c) for c in instances(assembled)]

    assert all(p is not None for p in provenances)
    assert {p.extra['nexus_group_id'] for p in provenances} == {'pack'}
    assert [p.extra['nexus_group_index'] for p in provenances] == [0, 1, 2]
    assert [p.extra['slit_edges'] for p in provenances] == [
        [10.0, 30.0], [100.0, 140.0], [350.0, 370.0],
    ]
    assert {p.extra['top_dead_center'] for p in provenances} == {15.0}
    assert {p.extra['beam_position'] for p in provenances} == {BEAM_POSITION}


def test_exactly_one_instance_is_the_primary(assembled):
    roles = [NiessProvenance.from_instance(c).role for c in instances(assembled)]
    assert roles.count('nexus-group-primary') == 1
    assert roles == ['nexus-group-primary'] + ['nexus-group-member'] * 2


def test_tagging_can_be_declined(assembled):
    assembler = Assembler('chopped', flavor=Flavor.MCSTAS)
    assembler.component('origin', 'Arm', at=((0, 0, 0), 'ABSOLUTE'))
    MultiSlitChopper.from_calibration(calibration()).to_mccode(
        assembler, at='origin', rotate='origin', insert_provenance_metadata=False)

    assert all(NiessProvenance.from_instance(c) is None
               for c in instances(assembler.instrument))


# -- what it converts to -----------------------------------------------------

def instrument_group(structure):
    return structure['children'][0]['children'][0]


def test_the_openings_are_rebuilt_as_one_nexus_group(assembled):
    instrument = instrument_group(to_nexus_structure(assembled, origin='sample'))

    disc = find_child(instrument, 'pack_slit_0')
    assert get_attribute(disc, 'NX_class') == 'NXdisk_chopper'
    assert find_child(disc, 'slits')['config']['values'] == 3
    # the edges reach NeXus exactly as calibrated, straddling edge and all
    assert find_child(disc, 'slit_edges')['config']['values'] == EDGES
    assert find_child(disc, 'top_dead_center')['config']['values'] == 15.0
    assert find_child(disc, 'beam_position')['config']['values'] == BEAM_POSITION
    # the speed is a run-time parameter, so it links rather than holding a number
    assert get_attribute(find_child(disc, 'rotation_speed'), 'NX_class') == 'NXlog'

    for name in ('pack_slit_1', 'pack_slit_2'):
        assert find_child(instrument, name) is None


def test_rebuilding_follows_the_tags_not_the_instance_order(assembled):
    """The primary need not come first; siblings order by their recorded index."""
    components = list(assembled.components)
    reordered = [components[0], components[3], components[2], components[1],
                 components[4]]
    assembled.components = tuple(reordered)
    assert [c.name for c in assembled.components][1] == 'pack_slit_2'

    instrument = instrument_group(to_nexus_structure(assembled, origin='sample'))
    disc = find_child(instrument, 'pack_slit_0')
    assert find_child(disc, 'slit_edges')['config']['values'] == EDGES


def test_without_the_translator_the_mccode_view_survives(assembled):
    """A registry that does not know MultiSlitChopper still converts the instrument.

    It sees what the McStas file literally describes: three separate discs. Grouping is
    an enrichment, not a prerequisite.
    """
    from niess.nexus import NiessNexusRegistry
    from niess.nexus.translators import diskchopper_translator

    plain = NiessNexusRegistry()
    plain.register_component_type('DiskChopper')(diskchopper_translator)

    instrument = instrument_group(
        to_nexus_structure(assembled, origin='sample', registry=plain))

    for name in ('pack_slit_0', 'pack_slit_1', 'pack_slit_2'):
        node = find_child(instrument, name)
        assert get_attribute(node, 'NX_class') == 'NXdisk_chopper'
        assert find_child(node, 'slits')['config']['values'] == 1
