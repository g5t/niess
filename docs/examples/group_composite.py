"""One niess object, several McStas components, one NeXus group.

A disc with unevenly spaced slits cannot be a single McStas `DiskChopper`: that
component's `nslit` slits are identical and evenly spaced. So the disc becomes one
`DiskChopper` per slit -- and the metadata each one carries is what lets an adapter put
the disc back together as a single object.
"""
from pathlib import Path


def main(outdir: Path) -> None:
    # --8<-- [start:composite]
    from scipp import Variable
    from niess.components.component import Base
    from niess.mccode import add_niess_metadata


    class MultiSlitChopper(Base):
        """A chopper disc whose slits are not evenly spaced.

        Emitted as one DiskChopper per slit, tagged so the group can be recovered.
        """
        name: str
        position: Variable
        orientation: Variable
        radius: Variable
        height: Variable
        frequency: Variable
        # (centre angle, angular width) per slit, in degrees
        slits: tuple[tuple[float, float], ...]

        def to_mccode(self, assembler, at=None, rotate=None):
            from niess.spatial import mccode_ordered_angles

            placement = (self.position.to(unit='m').value,
                         'ABSOLUTE' if at is None else at)
            rotation = (mccode_ordered_angles(self.orientation),
                        'ABSOLUTE' if rotate is None else rotate)

            instances = []
            for index, (centre, width) in enumerate(self.slits):
                instance = assembler.component(
                    f'{self.name}_slit_{index}', 'DiskChopper',
                    at=placement, rotate=rotation,
                    parameters={
                        'radius': self.radius.to(unit='m').value,
                        'yheight': self.height.to(unit='m').value,
                        'nu': self.frequency.to(unit='Hz').value,
                        'nslit': 1,
                        'theta_0': width,
                        'phase': centre,
                    },
                )
                # Hand-built instances must be tagged, or no adapter can see them.
                # The extras here are what make the group recoverable: a shared id,
                # an explicit role, an order, and this slit's own geometry.
                add_niess_metadata(
                    instance, self,
                    source_name=f'{self.name}_slit_{index}',
                    role='nexus-group-primary' if index == 0 else 'nexus-group-member',
                    extra={
                        'nexus_group_id': self.name,
                        'nexus_group_index': index,
                        'slit_centre': centre,
                        'slit_width': width,
                    },
                )
                instances.append(instance)
            return instances
    # --8<-- [end:composite]

    # --8<-- [start:translator]
    from niess.nexus import (
        DEFAULT_NEXUS_REGISTRY, NiessNexusRegistry, component_body, dataset,
    )
    from niess.provenance import NiessProvenance

    CHOPPER_REGISTRY = NiessNexusRegistry(parent=DEFAULT_NEXUS_REGISTRY)


    @CHOPPER_REGISTRY.register_role('nexus-group-member')
    def suppress_member(t):
        """Emit nothing: this slit is folded into the group's primary instance."""
        return None


    @CHOPPER_REGISTRY.register_role('nexus-group-primary')
    def merge_group(t):
        """Rebuild the whole disc from the slits that were emitted separately."""
        edges = []
        for sibling in t.siblings_in_group():        # ordered by nexus_group_index
            extra = NiessProvenance.from_instance(sibling).extra
            centre, width = extra['slit_centre'], extra['slit_width']
            edges += [centre - width / 2, centre + width / 2]

        return component_body('NXdisk_chopper', [
            dataset('slits', len(edges) // 2),
            dataset('slit_edges', edges, dtype='double', attrs={'units': 'degrees'}),
            t.parameter_node('rotation_speed', source='nu', dtype=float,
                             attrs={'units': 'Hz'}),
            dataset('radius', t.parameter('radius', dtype=float), attrs={'units': 'm'}),
        ])
    # --8<-- [end:translator]

    from mccode_antlr import Flavor
    from mccode_antlr.assembler import Assembler
    from scipp import scalar, vector
    from scipp.spatial import rotations_from_rotvecs
    from niess.nexus import find_child, get_attribute, to_nexus_structure

    assembler = Assembler('chopped', flavor=Flavor.MCSTAS)
    assembler.component('origin', 'Arm', at=((0, 0, 0), 'ABSOLUTE'))
    MultiSlitChopper(
        name='pack', position=vector([0, 0, 5.0], unit='m'),
        orientation=rotations_from_rotvecs(vector([0, 0, 0.0], unit='deg')),
        radius=scalar(0.35, unit='m'), height=scalar(0.06, unit='m'),
        frequency=scalar(14.0, unit='Hz'),
        slits=((0.0, 10.0), (95.0, 20.0), (250.0, 5.0)),
    ).to_mccode(assembler, at='origin', rotate='origin')
    assembler.component('sample', 'Arm', at=((0, 0, 8), 'origin'))

    # Three McStas components...
    emitted = [c.name for c in assembler.instrument.components]
    assert emitted == ['origin', 'pack_slit_0', 'pack_slit_1', 'pack_slit_2',
                       'sample'], emitted

    # --8<-- [start:result]
    structure = to_nexus_structure(
        assembler.instrument, origin='sample', registry=CHOPPER_REGISTRY,
    )
    instrument = structure['children'][0]['children'][0]

    disc = find_child(instrument, 'pack_slit_0')
    assert get_attribute(disc, 'NX_class') == 'NXdisk_chopper'
    assert find_child(disc, 'slits')['config']['values'] == 3
    assert find_child(disc, 'slit_edges')['config']['values'] == [
        -5.0, 5.0, 85.0, 105.0, 247.5, 252.5,
    ]

    # ...and the other two slits are gone, folded into the one above
    assert find_child(instrument, 'pack_slit_1') is None
    assert find_child(instrument, 'pack_slit_2') is None
    # --8<-- [end:result]

    # Without the registry the same instrument still converts -- as three separate
    # NXdisk_chopper groups, which is what the McStas file literally describes.
    plain = to_nexus_structure(assembler.instrument, origin='sample')
    plain_instrument = plain['children'][0]['children'][0]
    assert all(find_child(plain_instrument, f'pack_slit_{i}') is not None
               for i in range(3))

    # The same tags drive the CAD adapter: niess.brep dispatches on role too, so one
    # role builder there would rebuild the disc as a single solid. (Resolving the
    # builder needs no CAD toolkit; building the geometry would.)
    from niess.brep.registry import NiessBRepRegistry

    brep = NiessBRepRegistry()

    @brep.register_role('nexus-group-primary')
    def whole_disc(provenance, instance, params):
        return f'one solid disc for {provenance.extra["nexus_group_id"]}'

    primary = next(c for c in assembler.instrument.components
                   if c.name == 'pack_slit_0')
    assert brep.resolve_builder(primary) is whole_disc


if __name__ == '__main__':
    main(Path('.'))
