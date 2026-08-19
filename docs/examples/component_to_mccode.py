"""A component that needs more than a TRACE line.

`__mccode__` says what the component *is*. Overriding `to_mccode` is how a component
contributes everything else it needs to the instrument around it: run-time parameters,
internal variables computed once at start-up, lookup arrays, per-particle flags.
"""
from pathlib import Path


def main(outdir: Path) -> None:
    # --8<-- [start:component]
    from scipp import Variable
    from niess.components import Component
    from niess.mccode import ensure_runtime_line, ensure_user_var

    class ChoppedMonitor(Component):
        """A monitor gated on a chopper window, with a run-time delay."""
        width: Variable
        height: Variable
        frequency: Variable

        @classmethod
        def from_calibration(cls, cal: dict):
            return cls(name=cal['name'], position=cal['position'],
                       orientation=cal['orientation'], width=cal['width'],
                       height=cal['height'], frequency=cal['frequency'])

        def __mccode__(self) -> tuple[str, dict]:
            # What the component *is*: its TRACE line and parameters
            return 'TOF_monitor', {
                'xwidth': self.width.to(unit='m').value,
                'yheight': self.height.to(unit='m').value,
                'nt': 512,
                'tmin': 0,
                'tmax': f'{self.name}_window * 1e6',
                'restore_neutron': 1,
            }

        def to_mccode(self, assembler, at=None, rotate=None,
                      insert_provenance_metadata=True):
            # ...and what it needs the instrument to provide.

            # A knob the operator can turn, without editing the instrument
            ensure_runtime_line(assembler, f'{self.name}_delay/"s" = 0.0')

            # A value worth computing once at start-up rather than per neutron.
            # DECLARE gives it instrument scope; INITIALIZE fills it in.
            period = 1.0 / self.frequency.to(unit='Hz').value
            assembler.declare(f'double {self.name}_window;')
            assembler.initialize(
                f'{self.name}_window = {period} - {self.name}_delay;'
            )

            # A per-particle flag, so later components can see what this one did
            ensure_user_var(assembler, 'int', 'chopped',
                            'Set when a neutron reached the chopped monitor')

            return super().to_mccode(
                assembler, at, rotate,
                insert_provenance_metadata=insert_provenance_metadata,
            )
    # --8<-- [end:component]

    from mccode_antlr import Flavor
    from mccode_antlr.assembler import Assembler
    from scipp import scalar, vector
    from scipp.spatial import rotations_from_rotvecs

    assembler = Assembler('gated', flavor=Flavor.MCSTAS)
    assembler.component('origin', 'Arm', at=((0, 0, 0), 'ABSOLUTE'))
    ChoppedMonitor.from_calibration({
        'name': 'gate', 'position': vector([0, 0, 2.0], unit='m'),
        'orientation': rotations_from_rotvecs(vector([0, 0, 0.0], unit='deg')),
        'width': scalar(50.0, unit='mm'), 'height': scalar(50.0, unit='mm'),
        'frequency': scalar(14.0, unit='Hz'),
    }).to_mccode(assembler, at='origin', rotate='origin')
    assembler.component('sample', 'Arm', at=((0, 0, 5), 'origin'))

    instrument = assembler.instrument
    text = str(instrument)

    # the run-time parameter reached DEFINE INSTRUMENT(...)
    assert 'gate_delay' in {p.name for p in instrument.parameters}
    # the internal variable reached DECLARE, and its value INITIALIZE
    assert 'double gate_window;' in text
    assert 'gate_window = 0.07142857142857142 - gate_delay;' in text
    # the per-particle flag reached USERVARS
    assert 'int chopped;' in text

    (outdir / 'gated.instr').write_text(text)


if __name__ == '__main__':
    main(Path('.'))
