from scipp import Variable

def lengths_angle_circle(l0, l1, two_theta):
    from numpy import sqrt, cos, sin
    twice_sin_two_theta = 2 * sin(two_theta)
    radius = sqrt(l0**2 + l1**2 + l0 * l1 * cos(two_theta)) / twice_sin_two_theta
    z0 = l0 / 2
    x0 = (l0 * cos(2 * two_theta) - l1 * cos(two_theta)) / twice_sin_two_theta
    return x0, z0, radius


def three_point_circle(p0: Variable, p1: Variable, p2: Variable):
    from scipp import sqrt, dot, cross, scalar, isclose
    # vectors along each side of the triangle
    va, vb, vc = p1 - p0, p2 - p0, p2 - p1
    # and their lengths
    a, b, c = [sqrt(dot(x, x)) for x in (va, vb, vc)]
    # the semi-perimeter, s, defines the area sqrt(s(s-a)...)
    s = (a+b+c)/2
    # and the circumscribing circle has radius:
    r = a*b*c / (4*sqrt(s*(s-a)*(s-b)*(s-c)))
    # to find the center we must define the plane normal
    n = cross(vb, va) / a / b
    if sqrt(dot(n, n)) == scalar(0., unit=n.unit):
        raise RuntimeError("Points are collinear")
    n /= sqrt(dot(n, n))
    # the bisector of any one of the sides points to the center
    perp = [p / sqrt(dot(p,p)) for v in (-va, vb, -vc) for p in (cross(n, v),)]
    # the length of the bisector is given by the pythagorean theorem
    h = [sqrt(r*r - i*i/4) * p for p, i in zip(perp, (a, b, c))]
    # but whether each h should be positive or negative is determined by the distance
    # to the other two points
    z = []
    for x0, y0, z0, v, bi in zip((p0, p0, p1), (p1, p1, p2), (p2, p2, p0), (va, vb, vc), h):
      t = x0 + 0.5*v + bi
      if isclose(dot(t-y0, t-y0), r*r) and isclose(dot(t-z0, t-z0), r*r):
        z.append(t)
      else:
        z.append(x0 + 0.5*v - bi)

    # all three z points should be the same:
    if not isclose(z[0], z[1]) or not isclose(z[1], z[2]):
      raise RuntimeError(f"Mismatched central points,\n{p0=}\n{p1=}\n{p2=}\n{z = }")
    if z[0] != z[1] or z[1] != z[2]:
        # Only find the average of the three points if they are not identical to avoid division-by-three weirdness
        return (z[0]+z[1]+z[2])/3, r, n
    return z[0], r, n


def angle_between(a: Variable, b: Variable):
    from scipp import acos, dot, sqrt
    return acos(dot(a, b) / sqrt(dot(a, a)) / sqrt(dot(b, b)))


def rowland_blade_angles(beta: Variable, radius: Variable, count: int, width: Variable, gap=None):
    """
    Find the rotation angle needed for each crystal blade in a Rowland geometry

    :param beta:
        The angle subtended by the crystal array when viewed from the central axis of
        the Rowland cylinder
    :param radius:
        The radius of the Rowland cylinder
    :param count:
        The number of crystals in the array
    :param width:
        The width along the Rowland circumferential direction for any one crystal
    :param gap:
        The nominal spacing between crystals along the cylinder circumference
    :return:
    """
    # the crystals cover from (-beta/2, beta/2) *around the Rowland circle center point*, rho
    #   -beta/2                                        beta/2
    #  ----v------.------.------.------.------.------.---v----> rho
    #      |xxx|  |xxx|  |xxx|  |xxx|  |xxx|  |xxx|  |xxx|
    # So the angular range is broken up into N blade-width and (N-1) gap-width segments
    # The blade width is rho_blade ~= width / rowland_radius, so the gap width is given by
    #       rho_gap = (beta - N * rho_blade) / (N - 1)
    from scipp import atan2, isclose, scalar, arange
    if gap is None:
        r_width = 2 * atan2(y=0.5 * width, x=radius.to(unit=width.unit))
        r_gap = (beta - count * r_width) / (count - 1)
    else:
        # Follow the RTP method to calculate radial 'width' of each blade -- which might be greater than actual width
        from numpy import pi
        r_gap = gap / (2 * pi * radius.to(unit=gap.unit)) * scalar(2 * pi, unit='radian')
        # r_gap = 2 * atan2(y=0.5 * gap, x=radius.to(unit=gap.unit))
        r_width = (beta - (count - 1) * r_gap) / count

    half_count = count >> 1
    angles = (r_width + r_gap) * arange(start=-half_count, stop=half_count+1, dim='blade')
    if not isclose(angles['blade', half_count], scalar(0., unit='radian')):
        print(f"{beta = }\n{radius = }\n{count = }\n{width = }\n{r_width = }\n{r_gap = }\n{angles = :c}")
        raise RuntimeError(f"Central angle should be zero but is {angles[count>>1]}.")
    if gap is None and not isclose(angles[-1], beta/2 - 0.5 * r_width):
        raise RuntimeError("Last angle should be half a radial-width from the maximum coverage angle!")
    return angles


def rowland_blades(
        source: Variable,
        position: Variable,
        focus: Variable,
        alpha: Variable,
        width: Variable,
        count: int,
        tau: Variable,
        gap=None
):
    """
    Find the positions and normal vectors for the crystals arranged on the Rowland
    geometry cylinder connecting `source`, `position` and `focus`

    :param source:
        The position of the point-source from which all neutrons arrive
    :param position:
        The central on-cylinder position of this device; this is not the center of
        mass for the crystals since they are on the surface of the cylinder.
    :param focus:
        The position of the point-focus to which all neutrons are directed
    :param alpha:
        *Half* of the angular width of the crystals when viewed from the source
        (or focus) the angular size of the array viewed from the Rowland cylinder centre
        is exactly four times this value.
    :param width:
        The size of each crystal comprising the array, along the circumferential
        direction of the Rowland cylinder
    :param count:
        The number of crystals positioned along the Rowland cylinder circumference
    :param tau:
        The Q value of the reflection used by these crystals (2 pi / d_spacing)
    :param gap:
        The proposed spacing between successive crystals in the array
    :return:
    """
    from scipp.spatial import rotations_from_rotvecs

    center, radius, normal = three_point_circle(source, position, focus)
    angles = rowland_blade_angles(4.0 * alpha, radius, count, width, gap)

    # for each angle, create the rotation matrix needed to rotate (position - center)
    rotations = rotations_from_rotvecs(rotation_vectors=angles * normal)

    # *broadcast* the rotations to the center-to-analyzer-position vector
    blade_positions = rotations * (position - center) + center
    assert blade_positions.shape == rotations.shape

    # find the crystal-normal directions; the central one is set by Bragg's law, while the remaining ones
    # are rotated by half their Rowland angles
    rotations = rotations_from_rotvecs(rotation_vectors=0.5 * angles * normal)
    blade_taus = rotations * tau

    return blade_positions, blade_taus
