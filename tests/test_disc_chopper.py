"""Where a disc chopper is, and which side of the beam its spindle sits on.

A niess `DiscChopper`'s `position` is the spindle; a McStas `DiskChopper`'s origin is the
point the beam crosses the disc. Two angles say where that point is -- `zero_angle` from
the local +y axis to the disc's zero mark, `beam_angle` from the mark to the beam, both
counter-clockwise about +z -- and everything else follows from them: the vector between
the two points, and the rotation the emitted component needs so the disc ends up on the
right side of the beam.

Getting this wrong does not warn or transmit less. McStas absorbs every neutron outside
the disc radius, silently, so a chopper placed off the beam counts nothing at all.
"""
import pytest
from mccode_antlr import Flavor
from mccode_antlr.assembler import Assembler
from scipp import scalar, vector
from scipp.spatial import rotations_from_rotvecs

from niess.components import DiscChopper

UPRIGHT = rotations_from_rotvecs(vector([0, 0, 0.0], unit='deg'))
RADIUS, HEIGHT = 0.35, 0.06
DELTA_Y = RADIUS - HEIGHT / 2      # McStas' delta_y: the beam runs mid-slit


def calibration(**overrides):
    cal = {
        'name': 'chopper',
        'position': vector([0, 0, 5.0], unit='m'),
        'orientation': UPRIGHT,
        'radius': scalar(RADIUS, unit='m'),
        'height': scalar(HEIGHT, unit='m'),
        'angle': scalar(170.0, unit='deg'),
        'frequency': scalar(14.0, unit='Hz'),
        'delay': scalar(0.0, unit='s'),
    }
    cal.update(overrides)
    return cal


def emitted(chopper):
    assembler = Assembler('chopped', flavor=Flavor.MCSTAS)
    chopper.to_mccode(assembler)
    instance = assembler.instrument.components[-1]
    return ([float(str(x)) for x in instance.at_relative[0]],
            [float(str(x)) for x in instance.rotate_relative[0]])


# -- where the beam crosses the disc ------------------------------------------

def test_the_default_angles_put_the_beam_at_the_top_of_the_disc():
    """Which is the arrangement McStas' DiskChopper already assumes.

    Its `delta_y = radius - yheight/2` sets the spindle *below* the component origin and
    it measures opening angles as `atan2(x, y + delta_y)`, zero on the beam. So a disc
    that takes the defaults needs no turning, and emits the rotation it always did.
    """
    disc = DiscChopper.from_calibration(calibration())
    assert disc.beam_offset().to(unit='m').value == pytest.approx([0.0, DELTA_Y, 0.0])
    at, rotated = emitted(disc)
    assert at == pytest.approx([0.0, DELTA_Y, 5.0])
    assert rotated == pytest.approx([0.0, 0.0, 0.0])


def test_a_disc_hanging_above_the_beam_is_half_a_turn_round():
    """The usual arrangement, and the one BIFROST has.

    The beam crosses at the bottom of the disc, so the spindle is above it and the emitted
    component turns half a turn about z -- which is what puts McStas' disc, which is
    always drawn below its own origin, above the beam instead.
    """
    disc = DiscChopper.from_calibration(
        calibration(beam_angle=scalar(180.0, unit='deg')))
    assert disc.beam_offset().to(unit='m').value == pytest.approx([0.0, -DELTA_Y, 0.0])
    at, rotated = emitted(disc)
    assert at == pytest.approx([0.0, -DELTA_Y, 5.0])
    assert rotated == pytest.approx([0.0, 0.0, 180.0])


def test_the_two_angles_add():
    """`zero_angle` reaches the mark and `beam_angle` carries on from there."""
    from math import cos, radians, sin
    disc = DiscChopper.from_calibration(calibration(
        zero_angle=scalar(30.0, unit='deg'), beam_angle=scalar(75.0, unit='deg')))
    turn = radians(105.0)
    assert disc.beam_offset().to(unit='m').value == pytest.approx(
        [-DELTA_Y * sin(turn), DELTA_Y * cos(turn), 0.0])
    assert emitted(disc)[1] == pytest.approx([0.0, 0.0, 105.0])


def test_a_disc_with_no_slit_height_is_centred_on_half_its_radius():
    """McStas takes an unset `yheight` as the full radius, so the beam runs at radius/2."""
    cal = calibration()
    cal.pop('height')
    disc = DiscChopper.from_calibration(cal)
    assert disc.beam_offset().to(unit='m').value == pytest.approx([0.0, RADIUS / 2, 0.0])


# -- offset and angles have to agree ------------------------------------------

def test_an_offset_that_the_angles_agree_with_is_kept():
    disc = DiscChopper.from_calibration(calibration(
        beam_angle=scalar(180.0, unit='deg'),
        offset=vector([0, -DELTA_Y, 0], unit='m')))
    assert disc.offset is not None
    assert disc.beam_offset().to(unit='m').value == pytest.approx([0.0, -DELTA_Y, 0.0])


def test_an_offset_the_angles_contradict_is_refused():
    """And refused where the calibration is, not inside an emitted instrument."""
    with pytest.raises(ValueError, match='absorbs every neutron'):
        DiscChopper.from_calibration(
            calibration(offset=vector([0, -DELTA_Y, 0], unit='m')))  # angles still default


def test_the_offset_may_be_left_out_entirely():
    """Which is the point: the angles are the description, the vector is derived."""
    disc = DiscChopper.from_calibration(calibration(beam_angle=scalar(180.0, unit='deg')))
    assert disc.offset is None
    assert emitted(disc)[0] == pytest.approx([0.0, -DELTA_Y, 5.0])


# -- the names the calibration may use ----------------------------------------

def test_the_nexus_names_are_accepted():
    """`top_dead_center` and `beam_position` are what NXdisk_chopper calls these."""
    disc = DiscChopper.from_calibration(calibration(
        top_dead_center=scalar(30.0, unit='deg'),
        beam_position=scalar(75.0, unit='deg')))
    assert disc.zero_angle.to(unit='deg').value == pytest.approx(30.0)
    assert disc.beam_angle.to(unit='deg').value == pytest.approx(75.0)


def test_reading_a_calibration_does_not_change_it():
    """Calibrations are reused across builds, so a build must not write back into one."""
    cal = calibration(top_dead_center=scalar(30.0, unit='deg'))
    before = dict(cal)
    DiscChopper.from_calibration(cal)
    assert cal == before
    assert 'zero_angle' not in cal


# -- the instrument this is for -----------------------------------------------

def test_every_bifrost_chopper_lands_on_the_beam():
    """And its spindle above, which is where BIFROST's discs actually hang.

    The emitted rotation used to be missing the half turn, so McStas put every disc below
    the beam and ran them through the top -- a mirror image of the real instrument.
    """
    from niess.bifrost import Primary
    from niess.components import DiscChopper as Disc

    def discs(section, prefix=''):
        for name, kind in section.items():
            member = getattr(section, name)
            if isinstance(member, Disc):
                yield f'{prefix}{name}', member
            elif hasattr(member, 'items'):
                yield from discs(member, f'{prefix}{name}.')

    found = dict(discs(Primary.from_calibration()))
    assert len(found) == 6
    for name, disc in found.items():
        assert disc.beam_angle.to(unit='deg').value == pytest.approx(180.0), name
        # the spindle is above the beam, and the emitted AT is on it
        assert disc.position.fields.y.to(unit='m').value > 0, name
        assert (disc.position + disc.beam_offset()).fields.y.to(unit='m').value == \
            pytest.approx(0.0, abs=1e-9), name


def test_bifrost_can_stop_saying_its_offsets():
    """The explicit offsets agree with the angles, so they are now redundant.

    Which is the evidence for dropping them from the calibration: nothing changes.
    """
    from niess.bifrost import Primary
    from niess.components import DiscChopper as Disc

    def discs(section):
        for name, kind in section.items():
            member = getattr(section, name)
            if isinstance(member, Disc):
                yield member
            elif hasattr(member, 'items'):
                yield from discs(member)

    for disc in discs(Primary.from_calibration()):
        explicit = disc.offset
        assert explicit is not None
        disc.offset = None
        assert disc.beam_offset().to(unit='m').value == \
            pytest.approx(explicit.to(unit='m').value, abs=1e-12)
