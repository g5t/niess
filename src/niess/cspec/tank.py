from dataclasses import dataclass


def combined_parameters(user_params: dict, default_params: dict):
    combined = {k: user_params.get(k, default_params[k]) for k in default_params}
    return combined


@dataclass
class Tank:
    from .pack import Pack

    packs: tuple[Pack, ...]

    @staticmethod
    def from_calibration(**params):
        from scipp import vector
        from scipp.spatial import rotations_from_rotvecs
        from .pack import Pack
        from .parameters import known_pack_params, tube_xy_displacement_to_quaternion
        combined = combined_parameters(params, known_pack_params())

        sample = combined['sample']  # the origin of the detector positions
        # (,), (tube,), (pack,)  or (pack, tube)
        detector_vector = vector([1, 0, 0]) * combined['sample_detector_distance']

        length = combined['detector_length'].to(unit='m')
        resistance = combined['resistance']
        resistivity = combined['resistivity']

        # (tube,)
        tube_rotations = rotations_from_rotvecs(combined['tube_angles'] * vector([0, 0, 1]))
        # (pack, )
        pack_rotations = rotations_from_rotvecs(combined['pack_angles'] * vector([0, 0, 1]))
        # (pack, tube)
        tube_positions = sample + pack_rotations * tube_rotations * detector_vector
        # (,), or (pack, tube)
        tube_orient = tube_xy_displacement_to_quaternion(length, combined['detector_orient'].to(unit='m'))
        # (pack, tube)
        tube_orient = pack_rotations * tube_rotations * tube_orient

        # we need to define (position: Variable, length: Variable, **params) for each pack
        n_packs = tube_positions.sizes['pack']

        orient_per, resistance_per, resistivity_per, length_per = ['pack' in x.dims for x in (tube_orient, resistance, resistivity, length)]

        pack_list = []
        for n in range(n_packs):
            pp = dict(sample=sample, orient=tube_orient['pack', n] if orient_per else tube_orient,
                      resistivity=resistivity['pack', n] if resistivity_per else resistivity,
                      resistance=resistance['pack', n] if resistance_per else resistance)
            pp['radius'] = combined['detector_radius']
            p = Pack.from_calibration(tube_positions['pack', n], length['pack', n] if length_per else length, **pp)
            pack_list.append(p)

        return Tank(tuple(pack_list))

    def to_mccode(self, assembler, sample, **kwargs):
        from ..mccode import ensure_user_var
        ensure_user_var(assembler, 'int', 'flag', 'Indicate detection in a monitor')

        group = 'packs_group'
        for index, pack in enumerate(self.packs):
            name = f'pack_{1+index:02d}'
            extend = "flag = (SCATTERED) ? 1 : 0;"
            pack.to_mccode(
                assembler,
                sample,
                name=name,
                extend=extend,
                group=group,
                first_wire_index=index * 24,
                **kwargs
            )
