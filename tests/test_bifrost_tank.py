# SPDX-FileCopyrightText: 2025-present Gregory Tucker <gregory.tucker@ess.eu>
#
# SPDX-License-Identifier: MIT


def test_bifrost_tank_importable():
    from importlib.util import find_spec
    if not find_spec('niess'):
        raise RuntimeError('No niess available!')
    if not find_spec('niess.bifrost'):
        raise RuntimeError('No niess.bifrost available!')
    from niess.bifrost import Tank


def test_bifrost_tank_constructable():
    from niess.bifrost import Tank
    tank = Tank.from_calibration()
    assert len(tank.channels) == 9


def test_bifrost_tank_calibratable():
    from scipp import scalar, isclose
    from niess.bifrost import Tank
    from niess.bifrost.parameters import known_channel_params
    params = known_channel_params()
    tank = Tank.from_calibration(**params)

    assert len(tank.channels) == 9

    vertical = 4.0, 3.674467758121384, 3.372105326299701, 3.1338895319560107, 2.9399369139099463
    horizontal = scalar(5.2, unit='deg')

    for channel in tank.channels:
        assert len(channel.pairs) == 5
        for index, (analyzer, triplet) in enumerate((arm.analyzer, arm.detector) for arm in channel.pairs):
            assert analyzer.count == params['blade_count']['analyzer', index]
            hor_cov, ver_cov = analyzer.coverage(params['sample'], unit='deg')

            # The coverage should approximately match that specified in the calibration
            # For 2.7 meV, the vertical coverage is +/- 2 degrees (e.g., 4 degrees)
            # Higher final energies are smaller to have constant Q-perpendicular
            # coverage, with exact values following `vertical` above ... or calculated
            # from the ratio of kf values
            expected = scalar(vertical[index], unit='deg').to(unit=ver_cov.unit)
            assert 2 * ver_cov >= expected
            assert isclose(2 * ver_cov, expected, atol=scalar(0.1, unit='deg'))
            # The analyzers have sufficient width to fully illuminate their detector
            # tubes, which means they are _wider_ than the detectors to account for
            # the finite crystal mosaic.
            mosaic = analyzer.central_blade.mosaic.to(unit='deg')
            # The detectors each cover (at least) 5.2 degrees horizontally for all energies
            # So the analyzer should be at least 5.2 + mosaic
            expected = mosaic + horizontal.to(unit=hor_cov.unit)
            assert 2 * hor_cov >= expected
            assert isclose(2 * hor_cov, expected, atol=scalar(1.2, unit='deg'))

            # We can also extract the detector effective horizontal coverage
            # since we know the sample-to-analyzer and analyzer-to-detector distances:
            arm_hor, arm_ver = channel.pairs[index].coverage(params['sample'], unit='deg')
            # these should actually be identical
            assert isclose(arm_ver, ver_cov)
            # and the horizontal coverage is calculated from the tube length,
            # which should be much closer to the expected value of 5.2 degrees
            # but since the current parameters are the total length instead of the
            # _active_ length, this coverage is slightly too big
            assert isclose(2 * arm_hor, horizontal, atol=scalar(0.6, unit='deg'))






