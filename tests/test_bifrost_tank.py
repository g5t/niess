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
    from scipp import scalar
    from niess.bifrost import Tank
    from niess.bifrost.parameters import known_channel_params
    params = known_channel_params()
    tank = Tank.from_calibration(**params)

    dir(tank)
    assert len(tank.channels) == 9
    for channel in tank.channels:
        assert len(channel.pairs) == 5
        for index, (analyzer, triplet) in enumerate((arm.analyzer, arm.detector) for arm in channel.pairs):
            assert analyzer.count == params['blade_count']['analyzer', index]
            hor_cov, ver_cov = analyzer.coverage(params['sample'])
            # parameterized coverage is +/- value for lowest-energy analyzer
            # higher-energy analyzers have the same *Q* coverage, not angle coverage
            assert ver_cov <= 2 * params['coverage'].to(unit=ver_cov.unit)
            # the analyzers each cover ~ 5 degrees (but likely less for higher energy)
            assert hor_cov <= scalar(5., unit='deg').to(unit=hor_cov.unit)
            print(f"horizontal {hor_cov.to(unit='deg'):c}\tvertical {ver_cov.to(unit='deg'):c}")



