"""Default per-component-type NeXus translators.

Each is registered against the raw McCode component-type name -- the third and
least specific dispatch tier -- so a niess component that wants different handling
can override it by registering against its own source type or role.

Ported from ``moreniius.mccode.comp`` with ``nexusformat`` classes replaced by the
plain node dicts of :mod:`niess.nexus.nodes`.
"""
from __future__ import annotations

import logging

from .instrument import component_body
from .nodes import dataset, group
from .off import NXoff
from .registry import DEFAULT_NEXUS_REGISTRY
from .streams import resolve_stream

logger = logging.getLogger(__name__)


@DEFAULT_NEXUS_REGISTRY.register_component_type('Slit')
def slit_translator(t):
    """Slit defines either (xmin, xmax, ymin, ymax) or (xwidth, yheight)."""
    if all(t.defines(x) for x in ('xwidth', 'yheight')):
        shape = 'straight slit'
    elif any(t.defines(x) for x in ('xmin', 'xmax', 'ymin', 'ymax')):
        shape = 'bladed'
    else:
        shape = 'open'

    children = [
        dataset('description', f'McStas slit {t.name}'),
        dataset('shape', shape),
    ]
    for name in ('xmin', 'xmax', 'ymin', 'ymax', 'xwidth', 'yheight'):
        children.append(group(name, 'NXpositioner', children=[
            dataset('name', name),
            t.parameter_node('value', source=name, dtype=float, attrs={'units': 'm'}),
        ]))
    return component_body('NXaperture', children)


@DEFAULT_NEXUS_REGISTRY.register_component_type(
    'Guide', 'Guide_channeled', 'Guide_gravity', 'Guide_simple', 'Guide_wavy',
)
def guide_translator(t):
    off_pars = {k: t.parameter(k, dtype=float, default=0.0) for k in ('l', 'w1', 'h1', 'w2', 'h2')}
    for k in ('w', 'h'):
        if not off_pars[f'{k}2']:
            off_pars[f'{k}2'] = off_pars[f'{k}1']
    return component_body('NXguide', [
        NXoff.from_wedge(**off_pars).to_nexus(),
        t.parameter_node('m_value', source='m', dtype=float, attrs={'units': ''}),
    ])


@DEFAULT_NEXUS_REGISTRY.register_component_type('Collimator_linear')
def collimator_linear_translator(t):
    off_pars = {
        'l': t.parameter('length', dtype=float, default=0.0),
        'w1': t.parameter('xwidth', dtype=float, default=0.0),
        'h1': t.parameter('yheight', dtype=float, default=0.0),
    }
    return component_body('NXcollimator', [
        NXoff.from_wedge(**off_pars).to_nexus(),
        t.parameter_node('divergence_x', source='divergence', dtype=float),
        t.parameter_node('divergence_y', source='divergenceV', dtype=float),
    ])


@DEFAULT_NEXUS_REGISTRY.register_component_type('DiskChopper')
def diskchopper_translator(t):
    nslit = t.parameter('nslit', dtype=int, default=1)
    theta_0 = t.parameter('theta_0', dtype=float, default=0.0)
    radius = t.parameter('radius', dtype=float, default=0.0)
    yheight = t.parameter('yheight', dtype=float, default=0.0)

    delta = theta_0 / 2.0
    slit_edges = [y * 360.0 / nslit + x for y in range(int(nslit)) for x in (-delta, delta)]

    return component_body('NXdisk_chopper', [
        dataset('slit_edges', slit_edges, dtype='double', attrs={'units': 'degrees'}),
        dataset('slits', int(nslit)),
        t.parameter_node('rotation_speed', source='nu', dtype=float, attrs={'units': 'Hz'}),
        dataset('radius', radius, attrs={'units': 'm'}),
        dataset('slit_angle', theta_0, attrs={'units': 'degrees'}),
        t.parameter_node('delay', dtype=float, attrs={'units': 's'}),
        dataset('slit_height', yheight if yheight else radius, attrs={'units': 'm'}),
    ])


def _ellipse_vertices_faces(*, major_x, minor_x, offset_x, major_y, minor_y, offset_y,
                            m_left, m_top, m_right, m_bottom, l, n=10):
    """Vertices, quad faces and per-face m-values for an elliptic guide.

    Only the guide's inner side surfaces are described -- the entry and exit
    openings are not faces.
    """
    from numpy import arange, sqrt

    def ellipse_width(minor, major, at):
        return 0 if abs(at) > major else minor * sqrt(1 - (at / major) ** 2)

    vertices, faces, m_values = [], [], []
    for fraction in arange(n + 1) / n:
        z = fraction * l
        w = ellipse_width(minor_x, major_x, offset_x - minor_x + z)
        h = ellipse_width(minor_y, major_y, offset_y - minor_y + z)
        vertices.extend([[-w, -h, z], [-w, h, z], [w, h, z], [w, -h, z]])

    for i in range(n):
        j0, j1, j2, j3, j4, j5, j6, j7 = [4 * i + k for k in range(8)]
        faces.extend([[j0, j1, j5, j4], [j1, j2, j6, j5], [j2, j3, j7, j6], [j3, j0, j4, j7]])
        m_values.extend([m_left, m_top, m_right, m_bottom])

    return vertices, faces, m_values


def _ellipse_parameters_from_widths(t):
    from numpy import sqrt

    def parameters(which, w, i, o, l):
        foci = i + l + o
        offset = foci / 2 - i
        if 'mid' in which:
            minor = w / 2
            major = sqrt(foci ** 2 + minor ** 2) / 2
        else:
            near, far = (o, i) if 'entrance' in which else (i, o)
            near += l
            w /= 2
            far = sqrt(far * far + w * w / 4) + sqrt(near * near + w * w / 4)
            major = far / 2
            minor = sqrt(far * far - foci * foci) / 2
        return major, minor, offset

    names = dict(xw='xwidth', xi='linxw', xo='loutxw', yw='yheight', yi='linyh', yo='loutyh', l='l')
    p = {k: t.parameter(v, dtype=float, default=0.0) for k, v in names.items()}

    dimensions_at = str(t.instance.get_parameter('dimensionsAt').value)
    major_x, minor_x, offset_x = parameters(dimensions_at, p['xw'], p['xi'], p['xo'], p['l'])
    major_y, minor_y, offset_y = parameters(dimensions_at, p['yw'], p['yi'], p['yo'], p['l'])
    return {
        'major_x': major_x, 'minor_x': minor_x, 'offset_x': offset_x,
        'major_y': major_y, 'minor_y': minor_y, 'offset_y': offset_y,
        'l': p['l'],
    }


def _elliptic_guide_gravity_m_values(t):
    sides = ('left', 'top', 'right', 'bottom')
    for side in sides:
        if t.defines(f'mvalues{side}'):
            logger.warning(
                f'{t.name} defines mvalues{side}, which is not handled; '
                'expect incorrect m-values in the output'
            )

    names = tuple(f'm_{side}' for side in sides)
    values = {k: t.parameter(k.replace('_', ''), dtype=float, default=-1.0) for k in ('m',) + names}
    # Mirror the component's own priority logic: -1 means "use the global m"
    return {name: (values['m'] if values[name] == -1 else values[name]) for name in names}


@DEFAULT_NEXUS_REGISTRY.register_component_type('Elliptic_guide_gravity')
def elliptic_guide_gravity_translator(t):
    # Parameter names verified against the component definition:
    # mccode-dev/McCode/mcstas-comps/optics/Elliptic_guide_gravity.comp
    bases = {'major': 'majorAxis', 'minor': 'minorAxis', 'offset': 'majorAxisoffset'}
    extensions = {'x': 'xw', 'y': 'yh'}
    names = {f'{a}_{b}': f'{f}{s}' for a, f in bases.items() for b, s in extensions.items()}

    pars = {
        key: t.parameter(mccode, dtype=float) if t.defines(mccode) else None
        for key, mccode in names.items()
    }
    undefined = [v for v in pars.values() if v is None]
    if not undefined:
        pars['l'] = t.parameter('l', dtype=float, default=0.0)
    elif len(undefined) < len(pars):
        logger.warning(
            f'Only {len(pars) - len(undefined)} of {len(pars)} axis parameters are defined '
            f'on {t.name}; falling back on the guide widths'
        )
    if undefined:
        pars = _ellipse_parameters_from_widths(t)

    pars = pars | _elliptic_guide_gravity_m_values(t)
    vertices, faces, m_values = _ellipse_vertices_faces(**pars, n=10)

    return component_body('NXguide', [
        NXoff(vertices, faces).to_nexus(),
        dataset('m_value', [float(m) for m in m_values], dtype='double', attrs={'units': ''}),
    ])


@DEFAULT_NEXUS_REGISTRY.register_component_type('TOF_monitor', 'PSD_monitor', 'Frame_monitor')
def monitor_translator(t, default_stream: dict | None = None):
    """A monitor's sensitive face, as a thin wedge, plus whatever it streams.

    The stream protocol is resolved from the instrument, never chosen here -- see
    :func:`niess.nexus.streams.resolve_stream`.
    """
    width = t.parameter('xwidth', dtype=float, default=0.0)
    height = t.parameter('yheight', dtype=float, default=0.0)
    geometry = NXoff.from_wedge(l=0.005, w1=width, h1=height)

    children = [geometry.to_nexus()]
    stream = resolve_stream(t, default=default_stream)
    if stream is not None:
        children.append(stream)
    return component_body('NXmonitor', children)


# Registered by niess source type rather than by McStas component type: a disc with
# several openings emits several plain DiskChoppers, and only the provenance says they
# are one disc. Naming the source type as a string keeps niess.components out of this
# module's imports.
#
# The bare-DiskChopper translator above still serves instruments niess did not build,
# where `theta_0` is all there is to go on.
@DEFAULT_NEXUS_REGISTRY.register('niess.components.chopper.DiscChopper')
def disc_chopper_translator(t):
    """Write a disc chopper, rebuilding one that was split across several components.

    A disc with several openings emits one DiskChopper apiece; one of them carries the
    whole disc here and the rest emit nothing. Which is which comes from the provenance
    role, so it does not depend on the order the instances appear in the instrument. A
    disc with a single opening is one component and is simply itself.
    """
    from . import expression
    from ..provenance import NiessProvenance

    if t.provenance is None:
        return None
    if t.provenance.role == 'nexus-group-member':
        # An opening folded into the primary instance above -- emit nothing at all
        return None

    siblings = t.siblings_in_group()
    if siblings:
        edges = []
        for sibling in siblings:
            extra = NiessProvenance.from_instance(sibling).extra
            edges.extend(extra['slit_edges'])
    else:
        # a single-opening disc: its own provenance is the whole story
        edges = list(t.provenance.extra['slit_edges'])

    # NXdisk_chopper geometry: angles measured from the top-dead-centre mark, positive
    # counter-clockwise facing +z, with a final edge beyond 360 where the last opening
    # straddles the mark. The component allows an opening written across the mark as a
    # negative first edge, which is clearer to read; the standard wants them positive,
    # so shift the pairs into [0, 360) here, where the standard is what applies.
    if edges and edges[0] < 0.0:
        edges = [edge + 360.0 for edge in edges]

    children = [
        dataset('slits', len(edges) // 2),
        dataset('slit_edges', edges, dtype='double', attrs={'units': 'degrees'}),
    ]
    # `slit_angle` is one angular opening, so it only means something when the openings
    # are all the same size -- which every single-opening disc trivially is, and which is
    # what the bare-DiskChopper translator assumes for all of them.
    widths = {round(b - a, 12) for a, b in zip(edges[::2], edges[1::2])}
    if len(widths) == 1:
        children.append(dataset('slit_angle', widths.pop(), attrs={'units': 'degrees'}))
    children += [
        t.parameter_node('rotation_speed', source='nu', dtype=float,
                         attrs={'units': 'Hz'}),
        dataset('radius', t.parameter('radius', dtype=float, default=0.0),
                attrs={'units': 'm'}),
        dataset('slit_height', t.parameter('yheight', dtype=float, default=0.0),
                attrs={'units': 'm'}),
    ]

    extra = t.provenance.extra

    # The disc's own delay, not this instance's: each emitted opening carries the shared
    # delay plus its own fixed offset, and that offset is already in ``slit_edges``.
    delay_parameter = extra.get('delay_parameter')
    if delay_parameter is None and extra.get('nexus_group_id') is not None:
        delay_parameter = f'{extra["nexus_group_id"]}delay'
    if delay_parameter is not None:
        children.append(expression.parameter_node(
            'delay',
            expression.LinkedLog(
                delay_parameter, f'{t.context.nxlog_root}/{delay_parameter}'),
            attrs={'units': 's'},
        ))

    if 'top_dead_center' in extra:
        children.append(dataset('top_dead_center', float(extra['top_dead_center']),
                                attrs={'units': 'degrees'}))
    if 'beam_position' in extra:
        children.append(dataset('beam_position', float(extra['beam_position']),
                                attrs={'units': 'degrees'}))

    # The group carries the disc's own name: "_slit_0" is an artefact of splitting it
    # across McStas components, and means nothing to a reader of the NeXus file.
    return component_body('NXdisk_chopper', children,
                          name=t.provenance.extra.get('nexus_group_id'))
