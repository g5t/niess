# SPDX-FileCopyrightText: 2025-present Gregory Tucker <gregory.tucker@ess.eu>
#
# SPDX-License-Identifier: MIT
from operator import getitem


def get_mccode_registries():
    from mccode_antlr.reader import GitHubRegistry

    registries = ['mcstas-chopper-lib', 'mcstas-transformer', 'mcstas-detector-tubes',
                  'mcstas-epics-link', 'mcstas-frame-tof-monitor', 'mccode-mcpl-filter',
                  'mcstas-monochromator-rowland', 'mcstas-slit-radial']
    registries = [GitHubRegistry(
        name,
        url=f'https://github.com/mcdotstar/{name}',
        filename='pooch-registry.txt',
        version='main'
    ) for name in registries]

    return registries



def test_bifrost_whole():
    from niess.bifrost.parameters import primary_parameters, tank_parameters
    from niess.bifrost import Tank, Primary

    primary = Primary.from_calibration(primary_parameters())
    tank = Tank.from_calibration(tank_parameters())


def test_bifrost_mccode():
    from niess.bifrost.parameters import primary_parameters, tank_parameters
    from niess.bifrost import Tank, Primary
    from mccode_antlr import Flavor
    from mccode_antlr.assembler import Assembler
    from pathlib import Path

    bifrost = Assembler('bifrost', registries=get_mccode_registries(), flavor=Flavor.MCSTAS)

    primary = Primary.from_calibration(primary_parameters())
    primary.to_mccode(bifrost)

    # TODO insert pre- and post-sample things here
    #      e.g., the split_at location at the end of the guide
    #      any filters, e.g., a hits-the-sample MCPL filter, or a Be-transmission filter
    #      the radial collimator between sample and tank, etc.

    tank = Tank.from_calibration(tank_parameters())
    tank.to_mccode(bifrost, 'sample_origin')

    from mccode_antlr.io.json import load_json
    from msgspec.structs import fields

    # The loaded-from-state Instr should be equivalent across most niess changes
    # but may break with changes in mccode-antlr.
    # It is therefore up to you to decide if a new bifrost_assembler.json should be
    # minted -- Good luck!
    instr = load_json(Path(__file__).parent / "bifrost_assembler.json")

    # All members of the instrument should be the same, but registry equivalency
    # is too strict since the order is not terribly important for a built-instr.
    for par in fields(instr):
        if par.name != 'registries':
            assert getattr(instr, par.name) == getattr(bifrost.instrument, par.name)
    #
    # # If the above failed due to upstream changes, you probably want to stash any
    # # modifications you've made, then come back here, disable the above and enable
    # # the following:
    # from mccode_antlr.io.json import save_json
    # save_json(Path(__file__).parent / "bifrost_assembler.json", bifrost.instrument)
    # # Then restore your changes and re-enable the checks above.