"""NXoff_geometry construction.

A thin descriptive geometry layer: vertices plus per-face vertex indices, flattened
into the winding-order/face-offset pair NXoff_geometry stores.

This is deliberately independent of :mod:`niess.brep`'s ``build123d`` machinery.
The two describe shapes for different purposes -- OFF is a coarse polygonal hull
for file consumers, BRep is exact CAD solid geometry -- and factoring them onto a
shared description is a worthwhile follow-up, not a prerequisite for this port.
"""
from __future__ import annotations

from .nodes import dataset, group


class NXoff:
    """Object File Format geometry: a vertex list and polygonal faces."""

    def __init__(self, vertices, faces):
        self.vertices = vertices
        self.faces = faces

    @classmethod
    def from_wedge(cls, l, w1, h1, w2=None, h2=None):
        """A trapezoidal prism, origin at the centre of the entry face, +z downbeam."""
        if w2 is None:
            w2 = w1
        if h2 is None:
            h2 = h1
        x1, y1, x2, y2 = (float(v) / 2 for v in (w1, h1, w2, h2))
        vertices = [
            [-x1, -y1, 0], [-x1, y1, 0], [x1, y1, 0], [x1, -y1, 0],
            [-x2, -y2, l], [-x2, y2, l], [x2, y2, l], [x2, -y2, l],
        ]
        # Clockwise winding, facing out
        faces = [
            [0, 1, 2, 3], [1, 5, 6, 2], [5, 4, 7, 6],
            [6, 7, 3, 2], [7, 4, 0, 3], [1, 0, 4, 5],
        ]
        return cls(vertices, faces)

    @classmethod
    def sphere(cls, radius):
        from numpy import sqrt
        phi = (1 + sqrt(5)) / 2
        r = radius / sqrt(1 + phi)
        p = r * phi
        vertices = [
            [-r, p, 0], [r, p, 0], [-r, -p, 0], [r, -p, 0],
            [0, -r, p], [0, r, p], [0, -r, -p], [0, r, -p],
            [p, 0, -r], [p, 0, r], [-p, 0, -r], [-p, 0, r],
        ]
        faces = [
            [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
            [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
            [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
            [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
        ]
        return cls(vertices, faces)

    def to_nexus(self, name: str = 'OFF_GEOMETRY') -> dict:
        from numpy import cumsum

        winding_order = [index for face in self.faces for index in face]
        face_offsets = [0] + cumsum([len(f) for f in self.faces[:-1]]).tolist()
        vertices = [[float(c) for c in vertex] for vertex in self.vertices]
        return group(name, 'NXoff_geometry', children=[
            dataset('vertices', vertices, dtype='double', attrs={'units': 'm'}),
            dataset('winding_order', [int(w) for w in winding_order], dtype='int64'),
            dataset('faces', [int(f) for f in face_offsets], dtype='int64'),
        ])
