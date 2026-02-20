# from dataclasses import dataclass, fields
from __future__ import annotations

import msgspec
from networkx import DiGraph
from msgspec.structs import fields
from functools import lru_cache
from ..utilities import calibration

# TODO Consider whether it would be possible to use any one of:
#      datclass-wizzard: https://dataclass-wizard.readthedocs.io
#      pydantic: https://docs.pydantic.dev
#      dacite: https://github.com/konradhalas/dacite
#      to handle (de)serializing these nested dataclass objects from calibration data.

# @dataclass
class Section(msgspec.Struct, tag=True):

    @classmethod
    @lru_cache(maxsize=None)
    def parts(cls):
        """Get the ordered list of components which make up this Section"""
        return [fi.name for fi in fields(cls)]

    @classmethod
    @lru_cache(maxsize=None)
    def types(cls):
        """Get the ordered list of component types which make up this Section"""
        return [fi.type for fi in fields(cls)]

    @classmethod
    @lru_cache(maxsize=None)
    def items(cls):
        """Get the ordered list of component names and types which make up this Section"""
        return [(n, t) for n, t in zip(cls.parts(), cls.types())]

    @classmethod
    @lru_cache(maxsize=None)
    def field_types(cls):
        return {fi.name: fi.type for fi in fields(cls)}

    def to_mccode(self, *args, **kwargs):
        for part in self.parts():
            getattr(self, part).to_mccode(*args, **kwargs)

    @classmethod
    @calibration
    def from_calibration(cls, parameters: dict):
        for part in cls.parts():
            assert part in parameters

        def named_par(name):
            if 'name' not in parameters[name]:
                parameters[name]['name'] = name
            return parameters[name]

        def to_type(name):
            typ = cls.field_types()[name]
            if isinstance(parameters[name], typ):
                return parameters[name]
            return typ.from_calibration(named_par(name))

        return cls(*[to_type(n) for n in cls.parts()])

    def to_dict(self):
        return {f: getattr(self, f) for f in self.parts()}

    @classmethod
    def from_dict(cls, d):
        # TODO make a function to recurse through a dictionary and ensure
        #      scipp.Variable and mccode_antlr.? are converted
        return cls.from_calibration(d)

    def to_graph(self):
        from networkx import DiGraph
        graph = DiGraph()
        self.add_to_graph(None, '', graph)
        return graph

    def add_to_graph(self, upstream: str | None, unused_section_name: str, graph: DiGraph):
        last = upstream
        for name in self.__struct_fields__:
            names = getattr(self, name).add_to_graph(last, name, graph)
            if isinstance(names, list) and len(names) == 1:
                last = names[0]
        return [last]