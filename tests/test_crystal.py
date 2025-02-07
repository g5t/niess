# SPDX-FileCopyrightText: 2025-present Gregory Tucker <gregory.tucker@ess.eu>
#
# SPDX-License-Identifier: MIT


def test_ideal_crystal():
    from niess import IdealCrystal
    from scipp import scalar, array, vector, dot, norm, isclose

    pos = vector([0, 0, 0.], unit='m')
    tau = vector([0, 0, 1.], unit='1/m')

    crystal = IdealCrystal(pos, tau)

    # without any extent, the triangulated ideal crystal is a circle in the plane
    # perpendicular to tau, centered at pos
    vertices, triangle = crystal.triangulate()
    assert all(dot(v, tau) == scalar(0.) for v in vertices)
    assert isclose(norm(vertices.sum(dim='vertices')), scalar(0., unit='m'))

    assert isclose(crystal.momentum, scalar(1., unit='1/m'))

    x = crystal.scattering_angle(wavenumber=tau)
    assert isclose(x, scalar(60.0, unit='deg').to(unit=x.unit))


def box_edge_check(vs, x, y, z):
    from scipp import scalar, norm, isclose
    assert isclose(norm(vs['vertices', 1] - vs['vertices', 0]), scalar(x, unit='m'))
    assert isclose(norm(vs['vertices', 3] - vs['vertices', 2]), scalar(x, unit='m'))
    assert isclose(norm(vs['vertices', 5] - vs['vertices', 4]), scalar(x, unit='m'))
    assert isclose(norm(vs['vertices', 6] - vs['vertices', 7]), scalar(x, unit='m'))

    assert isclose(norm(vs['vertices', 2] - vs['vertices', 1]), scalar(y, unit='m'))
    assert isclose(norm(vs['vertices', 3] - vs['vertices', 0]), scalar(y, unit='m'))
    assert isclose(norm(vs['vertices', 6] - vs['vertices', 5]), scalar(y, unit='m'))
    assert isclose(norm(vs['vertices', 7] - vs['vertices', 4]), scalar(y, unit='m'))

    assert isclose(norm(vs['vertices', 4] - vs['vertices', 0]), scalar(z, unit='m'))
    assert isclose(norm(vs['vertices', 5] - vs['vertices', 1]), scalar(z, unit='m'))
    assert isclose(norm(vs['vertices', 6] - vs['vertices', 2]), scalar(z, unit='m'))
    assert isclose(norm(vs['vertices', 7] - vs['vertices', 3]), scalar(z, unit='m'))


def extent_check(corners, direction, extent):
    from scipp import norm, isclose, min, max, dot
    hat = direction / norm(direction)
    h_dot = dot(hat, corners).to(unit=extent.unit)
    assert isclose(max(h_dot) - min(h_dot), extent)


def extrema_check(crystal, horizontal, vertical, horizontal_extent, vertical_extent):
    corners = crystal.extreme_path_corners(horizontal, vertical)
    if horizontal_extent is not None:
        extent_check(corners, horizontal, horizontal_extent)
    if vertical_extent is not None:
        extent_check(corners, vertical, vertical_extent)


def test_crystal():
    from niess import Crystal
    from scipp import scalar, vector, dot, norm, isclose, allclose
    from scipp.spatial import rotations_from_rotvecs

    x, y, z = 1., 2., 0.01
    pos = vector([0, 0, 0.], unit='m')
    tau = vector([0, 0, 1.], unit='1/m')
    shape = vector([x, y, z], unit='m')
    orient = rotations_from_rotvecs(vector([0, 0, 0.], unit='deg'))

    crystal = Crystal(pos, tau, shape, orient)

    vs, triangles = crystal.triangulate()
    expected = [[-x/2, -y/2, -z/2], [x/2, -y/2, -z/2], [x/2, y/2, -z/2], [-x/2, y/2, -z/2],
                [-x/2, -y/2, z/2], [x/2, -y/2, z/2], [x/2, y/2, z/2], [-x/2, y/2, z/2],]
    for index, v in enumerate(expected):
        assert all(a == b for a, b in zip(v, vs['vertices', index].values))
    box_edge_check(vs, x, y, z)

    vx, vy, vz = [vector(vv, unit='m') for vv in ([1, 0, 0.], [0, 1, 0.], [0, 0, 1.])]
    extrema_check(crystal, vx, vy, scalar(x, unit='m'), scalar(y, unit='m'))
    extrema_check(crystal, vy, vz, scalar(y, unit='m'), scalar(z, unit='m'))
    extrema_check(crystal, vz, vx, scalar(z, unit='m'), scalar(x, unit='m'))
    extrema_check(crystal, vy, vx, scalar(y, unit='m'), scalar(x, unit='m'))
    extrema_check(crystal, vx, vz, scalar(x, unit='m'), scalar(z, unit='m'))
    extrema_check(crystal, vz, vy, scalar(z, unit='m'), scalar(y, unit='m'))


def test_rotated_crystal():
    from niess import Crystal
    from scipp import scalar, vector, cos, sin
    from scipp.spatial import rotations_from_rotvecs

    x, y, z, angle = 1., 2., 0.01, 25.0
    pos = vector([0, 0, 0.], unit='m')
    tau = vector([0, 0, 1.], unit='1/m')
    shape = vector([x, y, z], unit='m')
    orient = rotations_from_rotvecs(vector([0, angle, 0.], unit='deg'))

    crystal = Crystal(pos, tau, shape, orient)

    vs, triangles = crystal.triangulate()
    box_edge_check(vs, x, y, z)

    c, s = [fn(scalar(angle, unit='deg')) for fn in (cos, sin)]
    xz = scalar(x, unit='m') * c + scalar(z, unit='m') * s
    zx = scalar(z, unit='m') * c + scalar(x, unit='m') * s

    vx, vy, vz = [vector(vv, unit='m') for vv in ([1, 0, 0.], [0, 1, 0.], [0, 0, 1.])]
    extrema_check(crystal, vx, vy, xz, scalar(y, unit='m'))
    extrema_check(crystal, vy, vz, scalar(y, unit='m'), zx)
    extrema_check(crystal, vz, vx, zx, xz)
    extrema_check(crystal, vy, vx, scalar(y, unit='m'), xz)
    extrema_check(crystal, vx, vz, xz, zx)
    extrema_check(crystal, vz, vy, zx, scalar(y, unit='m'))



