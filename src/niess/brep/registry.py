from __future__ import annotations


from typing import Any, Callable

from ..dispatch import NiessRegistry, component_type_name, merged_params
from ..provenance import NiessProvenance

_BRepBuilder = Callable[[NiessProvenance | None, Any, dict[str, float]], Any | None]


class NiessBRepRegistry(NiessRegistry[_BRepBuilder]):
    """Registry of BRep shape builders, dispatched over the assembled Instance tree."""

    def register_component_type(self, comp_type_name: str):
        return super().register_component_type(comp_type_name)

    def build_shape(self, instance, params: dict[str, float] | None = None):
        builder = self.resolve_builder(instance)
        if builder is None:
            return None
        provenance = NiessProvenance.from_instance(instance)
        return builder(provenance, instance, merged_params(instance, params))

    def to_brep_registry(self, instr):
        from mccode_antlr.display.render.brep import BRepRegistry

        registry = BRepRegistry()
        comp_types = {component_type_name(instance) for instance in instr.components}
        for comp_type in comp_types:
            @registry.register(comp_type)
            def wrapper(instance, params, _self=self):
                return _self.build_shape(instance, params)
        return registry


DEFAULT_BREP_REGISTRY = NiessBRepRegistry()
