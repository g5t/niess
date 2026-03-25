from __future__ import annotations


from typing import Any, Callable

from niess.mccode import niess_source_type
from .provenance import NiessProvenance

_BRepBuilder = Callable[[NiessProvenance | None, Any, dict[str, float]], Any | None]


class NiessBRepRegistry:
    def __init__(self) -> None:
        self._source_type_builders: dict[str, _BRepBuilder] = {}
        self._role_builders: dict[str, _BRepBuilder] = {}
        self._component_type_builders: dict[str, _BRepBuilder] = {}

    def register(self, source: type | str):
        source_type = source if isinstance(source, str) else niess_source_type(source)

        def decorator(func: _BRepBuilder) -> _BRepBuilder:
            self._source_type_builders[source_type] = func
            return func

        return decorator

    def register_role(self, role: str):
        def decorator(func: _BRepBuilder) -> _BRepBuilder:
            self._role_builders[role] = func
            return func

        return decorator

    def register_component_type(self, comp_type_name: str):
        def decorator(func: _BRepBuilder) -> _BRepBuilder:
            self._component_type_builders[comp_type_name] = func
            return func

        return decorator

    def resolve_builder(self, instance) -> _BRepBuilder | None:
        provenance = NiessProvenance.from_instance(instance)
        if provenance is not None:
            if provenance.source_type in self._source_type_builders:
                return self._source_type_builders[provenance.source_type]
            if provenance.role in self._role_builders:
                return self._role_builders[provenance.role]

        comp_type_name = getattr(instance.type, 'name', str(instance.type))
        return self._component_type_builders.get(comp_type_name)

    def build_shape(self, instance, params: dict[str, float] | None = None):
        builder = self.resolve_builder(instance)
        if builder is None:
            return None
        provenance = NiessProvenance.from_instance(instance)
        return builder(provenance, instance, _merged_params(instance, params))

    def to_brep_registry(self, instr):
        from mccode_antlr.display.render.brep import BRepRegistry

        registry = BRepRegistry()
        comp_types = {getattr(instance.type, 'name', str(instance.type)) for instance in instr.components}
        for comp_type in comp_types:
            @registry.register(comp_type)
            def wrapper(instance, params, _self=self):
                return _self.build_shape(instance, params)
        return registry


DEFAULT_BREP_REGISTRY = NiessBRepRegistry()


def _expr_float(value):
    if isinstance(value, (int, float)):
        return float(value)
    simplified = value.simplify() if hasattr(value, 'simplify') else value
    if hasattr(simplified, 'value') and isinstance(simplified.value, (int, float)):
        return float(simplified.value)
    return float(simplified)


def _merged_params(instance, params: dict[str, float] | None = None):
    merged = dict(params or {})
    for component_parameter in instance.parameters:
        try:
            evaluated = component_parameter.value.evaluate(merged)
            merged[component_parameter.name] = _expr_float(evaluated)
        except Exception:
            continue
    return merged

