from __future__ import annotations

from dataclasses import dataclass

@dataclass
class Pack:
    from mccode_antlr.assembler import Assembler
    from scipp import Variable
    from ..components import He3Tube

    tubes: tuple[He3Tube, ...]
    resistances: Variable

    @staticmethod
    def from_calibration(position: Variable, length: Variable, **params):
        from numpy import tile
        from scipp import vector, scalar, Variable, concat, ones
        from scipp.spatial import rotations
        from ..spatial import is_scipp_vector
        from ..utilities import is_type, is_scalar
        from ..components import He3Tube

        is_scipp_vector(position, 'position')
        if position.ndim != 1 or 'tube' not in position.dims:
            raise RuntimeError("Expected a 1-D list of 'tube' positions")

        ori = params.get('orient', None)
        ori = rotations(values=tile([0, 0, 0, 1], (position.sizes['tube'], 1)), dims=['tube']) if ori is None else ori

        pressure = params.get('pressure', scalar(1., unit='atm'))
        radius = params.get('radius', scalar(25.4/2, unit='mm'))
        elements = params.get('elements', 100)
        resistivity = params.get('resistivity', scalar(140., unit='Ohm/in').to(unit='Ohm/m'))

        map(lambda x: is_type(*x), ((pressure, Variable, 'pressure'), (length, Variable, 'length'),
                                    (radius, Variable, 'radius'), (elements, int, elements),
                                    (resistivity, Variable, 'resistivity')))
        pack = elements, radius, pressure

        if is_scalar(resistivity):
            resistivity = resistivity * ones(shape=(position.sizes['tube'], ), dims=['tube'])

        # Make the oriented tube axis vector(s)
        axis = ori * (length.to(unit=position.unit) * vector([0, 0, 1.]))  # may be a 0-D or 1-D tube vector array
        tube_at = position - 0.5 * axis
        tube_to = position + 0.5 * axis
        tubes = tuple(He3Tube(at, to, rho, *pack) for at, to, rho in zip(tube_at, tube_to, resistivity))

        # Define the contact resistance for the wires
        resistance = params.get('resistance', scalar(2, unit='Ohm'))
        if is_scalar(resistance):
            resistance = resistance * ones(shape=(position.sizes['tube'], 2), dims=['tube', 'end'])
        # allow overriding specific resistances ... somehow
        return Pack(tubes, resistance)

    def mcstas_parameters(self) -> dict:
        from scipp import sqrt, dot
        # length vector (from one end of each tube to the other)
        lv = [tube.to - tube.at for tube in self.tubes]
        # central vector (the position of the center, relative to defining sample position)
        cv = [(tube.to + tube.at) / 2 for tube in self.tubes]
        # average length -- they *should* all be identical, but maybe they're not?
        length = sum([sqrt(dot(x, x)).to(unit='m').value for x in lv]) / len(self.tubes)
        # average radius -- ditto, if they're not identical this is wrong and a vector in the instrument is better
        radius = sum([tube.radius.to(unit='m').value for tube in self.tubes]) / len(self.tubes)
        # The distance between the first and last tube centres plus twice the radius is the assembly width
        width = sqrt(dot(cv[-1] - cv[0], cv[-1] - cv[0])).to(unit='m').value + 2 * radius
        params = dict(
            charge_a='"event_charge_top"',
            charge_b='"event_charge_bottom"',
            detection_time='"event_time"',
            tube_index_name='"TUBE"',
            N=len(self.tubes),
            width=width,
            height=length,
            radius=radius,
            wires_in_series=0,
        )
        return params

    def to_mccode(
            self,
            assembler: Assembler,
            relative: str,
            distance: float,
            name: str,
            when: str | None = None,
            extend: str | None = None,
            add_metadata: bool = False,
            component: str | None = None,
            group: str | None = None,
            **kwargs
    ):
        if component is None:
            component = 'Detector_tubes'
        params = self.mcstas_parameters()
        #TODO Ensure that one of the provided parameters is 'first_wire_index'
        #     Another useful parameter would be 'pack_filename', to save the McStas
        #     2-D histogram directly
        params.update(kwargs)
        tubes = assembler.component(name, component, at=((0, 0, distance), relative), parameters=params)
        if when:
            tubes.WHEN(when)
        if extend:
            tubes.EXTEND(extend)
        if group:
            tubes.GROUP(group)
