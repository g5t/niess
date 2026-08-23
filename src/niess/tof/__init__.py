"""Set up a ``tof.Model`` from an instrument niess emitted.

``tof`` (from the scipp developers) is a lightweight straight-line Monte Carlo for chopper
cascade diagrams. It needs the same description of a chopper train that ``niess.chopcalc``
already extracts for chopper-lib, with one difference: chopcalc emits parameter *names*, so
a band recomputes at run time, while ``tof`` configures one specific machine and needs
numbers. So this evaluates them, and says afterwards which ones it used.

    from mccode_antlr import Flavor
    from mccode_antlr.assembler import Assembler
    from niess.teaching import Primary
    import niess.tof

    assembler = Assembler('teaching', flavor=Flavor.MCSTAS)
    Primary.from_calibration().to_mccode(assembler)

    setup = niess.tof.to_tof_model(assembler)
    setup                      # in a notebook: what it used, and what you may override
    setup.model.run().plot()

Note that ``import tof`` inside this package is an absolute import and reaches the scipp
package, not ``niess.tof``; every use goes through ``components._tof`` so it is never in
doubt.
"""
from __future__ import annotations

from .components import TofSetup, to_tof_model
from .mapping import ChopperSpec, delay_to_phase, spec_from_windows
from .parameters import ParameterValues, Use
from .registry import DEFAULT_TOF_REGISTRY, NiessTofRegistry

__all__ = [
    'ChopperSpec',
    'DEFAULT_TOF_REGISTRY',
    'NiessTofRegistry',
    'ParameterValues',
    'TofSetup',
    'Use',
    'delay_to_phase',
    'spec_from_windows',
    'to_tof_model',
]
