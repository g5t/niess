import msgspec
from scipp import Variable
from .component import Component
from mccode_antlr.instr import Instance
from mccode_antlr.assembler import Assembler


class Chopper(Component):
    """Any device which periodically opens a path that particles may traverse"""
    velocity: Variable  # angular velocity scalar or vector
    phase: Variable
    radius: Variable
    windows: Variable
    width: Variable  # the path width
    height: Variable  # the path height


class DiscChopper(Chopper):
    """Ideally infinitely thin material with rotation vector parallel to the path"""
    # `radius` is the outer dimension of the disc.
    # `windows` are ordered angular edges of the openings in the disc
    # `phase` is the time=0 angular orientation of the disc
    offset: Variable # the position of the path relative to the disc center

    @property
    def speed(self):
        from scipp import dot, vector
        from ..spatial import __is_vector__
        if not __is_vector__(self.velocity):
            return self.velocity.to(unit='Hz')
        # TODO verify the sense of this wrt the McStas definition
        return dot(vector(value=[0, 0, 1.]), self.velocity).to(unit='Hz')

    def chopper_lib_parameters(self):
        """Useful for specifying elements of a vector used by chopper-lib"""
        from scipp import max, min, norm
        speed_name = f'{self.name}speed'
        phase_name = f'{self.name}phase'
        if self.windows.size != 2:
            raise ValueError("chopper-lib expects only one window")
        angle = (max(self.windows) - min(self.windows)).to(unit='deg').value
        distance = norm(self.position).to(unit='m').value
        return '{' + f'{speed_name}, {phase_name}, {angle}, {distance}' + '}'

    @classmethod
    def from_calibration(cls, cal: dict):
        from scipp import scalar, array, vector
        name = cal['name']
        position = cal['position']
        orientation = cal['orientation']
        velocity = cal.get('velocity', cal.get('frequency'))
        if velocity is None:
            raise ValueError('velocity (or frequency) cannot be None')
        phase = cal.get('phase', scalar(0.0, unit='deg'))
        radius = cal['radius']
        if 'windows' not in cal:
            cal['windows'] = cal['angle'].to(unit='deg') / 2 * array(values=[-1, 1], dims=['edges'])
        windows = cal['windows']
        width = cal.get('width') # None is actually acceptable
        height = cal.get('height')  # None is acceptable, then slit extends to center
        offset = cal.get('offset', vector([0, 0, 0], unit='m'))
        return cls(
            name=name,
            position=position,
            orientation=orientation,
            velocity=velocity,
            phase=phase,
            radius=radius,
            windows=windows,
            width=width,
            height=height,
            offset=offset
        )


    def __mccode__(self) -> tuple[str, dict]:
        from scipp import max, min
        if self.windows.size != 2:
            # The McStas way of handling multiple windows is one of two options:
            #   1. if they are equally spaced and all the same size, use 'nslit'
            #   2. otherwise use a group of choppers all at the same position but
            #      rotated relative to one another by their slit difference. One per.
            raise ValueError("Currently only one window supported. Investigate using a group here")
        params = {
            'theta_0': (max(self.windows) - min(self.windows)).to(unit='deg').value,
            'nslit': 1,
            'radius': self.radius.to(unit='m').value,
            'nu': f'{self.name}speed',
            'phase': f'{self.name}phase',
        }
        # Only add width of height if provided:
        if self.width is not None:
            params['xwidth'] = self.width.to(unit='m').value
        if self.height is not None:
            params['yheight'] = self.height.to(unit='m').value
        return 'DiskChopper', params

    def to_mccode(
            self, assembler: Assembler,
            at: Instance | str | None = None, rotate: Instance | str | None = None,
            insert_provenance_metadata: bool = True,
    ):
        from ..mccode import ensure_runtime_line as ensure
        ensure(assembler, f'{self.name}speed/"Hz" = {self.speed.value}')
        ensure(assembler, f'{self.name}phase/"degree" = {self.phase.to(unit="deg").value}')
        # the offset is handled by super's to_mccode -- no problems.
        return super().to_mccode(assembler, at, rotate, insert_provenance_metadata=insert_provenance_metadata)


def _zero_degrees() -> Variable:
    from scipp import scalar
    return scalar(0.0, unit='deg')


class MultiSlitChopper(DiscChopper):
    """A disc whose openings are neither identical nor evenly spaced.

    McStas' ``DiskChopper`` describes ``nslit`` identical, evenly spaced openings, so a
    disc that has neither cannot be one of them. This is the alternative its docstring
    points at: a group of ``DiskChopper`` instances at the same place, one per opening.

    Geometry follows ``NXdisk_chopper`` so the calibration is the same description a
    NeXus file will carry:

    ``top_dead_center``
        Where the disc's reference mark sits, as an angle from the local **+y** axis.
    ``beam_position``
        Where the beam crosses the disc, as an angle from the reference mark.
    ``windows`` (``slit_edges``)
        The angular edges of the openings, measured from the reference mark: an even
        number of **positive**, increasing values, two per opening.

    Every angle is positive counter-clockwise viewed facing **+z**, i.e. looking
    downstream. An opening that straddles the reference mark at phase zero is written
    as a final edge beyond 360 degrees -- ``[350, 370]`` rather than ``[350, 10]`` --
    so the pairs stay ordered and each width is simply the difference.
    """
    # Both default to zero: a disc whose mark is on the +y axis with the beam passing
    # through it. msgspec needs defaulted fields last, which these are.
    top_dead_center: Variable = msgspec.field(default_factory=_zero_degrees)
    beam_position: Variable = msgspec.field(default_factory=_zero_degrees)

    @classmethod
    def from_calibration(cls, cal: dict):
        chopper = super().from_calibration(cal)
        chopper.top_dead_center = cal.get('top_dead_center', _zero_degrees())
        chopper.beam_position = cal.get('beam_position', _zero_degrees())
        return chopper

    def slits(self) -> list[tuple[float, float]]:
        """The ``(opening, closing)`` edge pair of each slit, in degrees from the mark.

        Validates the ``NXdisk_chopper`` conventions: an even number of positive,
        increasing edges, with only the final one permitted to reach beyond 360.
        """
        edges = [float(v) for v in self.windows.to(unit='deg').values]
        if len(edges) < 2 or len(edges) % 2:
            raise ValueError(
                f'{self.name} has {len(edges)} slit edges; an even number of at least '
                'two is required, two per opening'
            )
        if any(edge < 0 for edge in edges):
            raise ValueError(
                f'{self.name} has a negative slit edge; edges are measured from the '
                'top-dead-centre mark and increase counter-clockwise facing +z'
            )
        if any(b <= a for a, b in zip(edges, edges[1:])):
            raise ValueError(f'{self.name} slit edges must strictly increase: {edges}')
        if edges[0] >= 360.0:
            raise ValueError(
                f'{self.name} opens first at {edges[0]} degrees; the first edge must '
                'lie within one revolution of the mark'
            )
        if edges[-1] - edges[0] > 360.0:
            # Exactly 360 is the limiting case: the last opening closes precisely where
            # the first one opens. Beyond that they would overlap themselves.
            raise ValueError(
                f'{self.name} spans {edges[-1] - edges[0]} degrees; the openings would '
                'overlap themselves'
            )
        return [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2)]

    def __mccode__(self) -> tuple[str, dict]:
        """The disc-level parameters, shared by every opening it emits."""
        params = {
            'nslit': 1,
            'radius': self.radius.to(unit='m').value,
            'nu': f'{self.name}speed',
        }
        if self.width is not None:
            params['xwidth'] = self.width.to(unit='m').value
        if self.height is not None:
            params['yheight'] = self.height.to(unit='m').value
        return 'DiskChopper', params

    def group_name(self) -> str:
        """The McStas GROUP the emitted openings share.

        Instance names are unique within an instrument, so deriving the group from this
        disc's name makes it unique too.
        """
        return f'{self.name}_group'

    def _mccode_phase(self, opening: float, closing: float) -> float:
        """How far the disc turns before this opening reaches the beam, in degrees.

        McStas puts the centre of a ``DiskChopper``'s slit at the beam when the disc has
        turned by ``phase``. Here an opening's centre starts ``centre`` degrees from the
        mark and the beam sits ``beam_position`` degrees from it, so the disc turns
        through the difference. The result is wrapped into ``[0, 360)`` because a
        rotating disc reaches the same place every revolution.
        """
        centre = (opening + closing) / 2
        beam = self.beam_position.to(unit='deg').value
        return (beam - centre) % 360.0

    def to_mccode(
            self, assembler: Assembler,
            at: Instance | str | None = None, rotate: Instance | str | None = None,
            insert_provenance_metadata: bool = True,
    ) -> list[Instance]:
        """Emit one ``DiskChopper`` per opening, tagged as one disc."""
        from ..mccode import add_niess_metadata, ensure_runtime_line
        from ..spatial import mccode_ordered_angles

        ensure_runtime_line(assembler, f'{self.name}speed/"Hz" = {self.speed.value}')
        ensure_runtime_line(
            assembler, f'{self.name}phase/"degree" = {self.phase.to(unit="deg").value}'
        )

        position = self.position + self.offset
        placement = (position.to(unit='m').value, 'ABSOLUTE' if at is None else at)
        rotation = (mccode_ordered_angles(self.orientation),
                    'ABSOLUTE' if rotate is None else rotate)

        component, shared = self.__mccode__()
        slits = self.slits()

        instances = []
        for index, (opening, closing) in enumerate(slits):
            parameters = dict(shared)
            parameters['theta_0'] = closing - opening
            # every opening turns with the disc, so they share one run-time phase
            parameters['phase'] = f'{self.name}phase + {self._mccode_phase(opening, closing)}'

            instance = assembler.component(
                f'{self.name}_slit_{index}', component,
                at=placement, rotate=rotation, parameters=parameters,
            )
            # One disc, so a neutron passes if it clears *any* opening. Ungrouped,
            # each DiskChopper absorbs whatever misses its own slit, and a neutron
            # would have to be inside every opening at once to survive.
            instance.GROUP(self.group_name())
            if insert_provenance_metadata:
                add_niess_metadata(
                    instance, self,
                    source_name=f'{self.name}_slit_{index}',
                    role='nexus-group-primary' if index == 0 else 'nexus-group-member',
                    extra={
                        'nexus_group_id': self.name,
                        'nexus_group_index': index,
                        'slit_edges': [opening, closing],
                        'top_dead_center': self.top_dead_center.to(unit='deg').value,
                        'beam_position': self.beam_position.to(unit='deg').value,
                    },
                )
            instances.append(instance)
        return instances


class FermiChopper(Chopper):
    """Ideally infinitely tall cylinder with a group of curved channels through
    its center, rotation vector parallel to its axis, and perpendicular to the path"""
    # `radius` describes the cylinder dimension
    # `windows` are the edges of the channels, as offsets from the central line
    # `phase` is the t=0 angular orientation of the central line wrt the path
    curvature: Variable