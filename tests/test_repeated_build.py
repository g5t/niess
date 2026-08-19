"""Building an instrument twice from one calibration gives the same instrument.

`Component.to_mccode` adds a component's `offset` to its position before emitting it.
Using `+=` did that in place, and since `self.position` *is* the scipp Variable held in
the calibration dictionary, every build shifted both the component and the calibration
it came from. The second build of a BIFROST primary moved its pulse-shaping choppers by
their offset; the third moved them again.

Nothing caught it because the test suite, and every example, built each instrument once.
"""
import pytest
from mccode_antlr import Flavor
from mccode_antlr.assembler import Assembler


def placements(section, calibration, instrument_name):
    assembler = Assembler(instrument_name, flavor=Flavor.MCSTAS)
    section.from_calibration(calibration).to_mccode(assembler)
    return {c.name: tuple(str(x) for x in c.at_relative[0])
            for c in assembler.instrument.components}


@pytest.fixture(scope='module')
def teaching():
    from niess.teaching import Primary, teaching_parameters
    return Primary, teaching_parameters(), 'teaching'


@pytest.fixture(scope='module')
def bifrost_primary():
    from niess.bifrost import Primary
    from niess.bifrost.parameters import primary_parameters
    return Primary, primary_parameters(), 'bifrost'


@pytest.mark.parametrize('fixture', ['teaching', 'bifrost_primary'])
def test_repeated_builds_are_identical(fixture, request):
    section, calibration, name = request.getfixturevalue(fixture)

    first = placements(section, calibration, name)
    second = placements(section, calibration, name)
    third = placements(section, calibration, name)

    assert first == second == third


def test_building_does_not_mutate_the_calibration(teaching):
    """The specific mechanism: the calibration's own Variables must survive a build."""
    from scipp import identical

    section, calibration, name = teaching
    before = calibration['chopper']['position'].copy()

    placements(section, calibration, name)

    assert identical(calibration['chopper']['position'], before)


def test_an_offset_is_applied_once(teaching):
    """...and exactly once, not zero times."""
    section, calibration, name = teaching
    emitted = placements(section, calibration, name)['chopper']

    # the chopper sits 0.35 m above the beam, so its disc centre is 0.35 m below the
    # position the beam passes through
    assert float(emitted[1]) == pytest.approx(-0.35)
