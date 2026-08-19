"""Target-neutral registry dispatch over the assembled ``Instance`` tree.

Conversion targets (STEP/CAD geometry in :mod:`niess.brep`, NeXus Structure JSON
in :mod:`niess.nexus`) resolve a builder for each ``mccode_antlr`` ``Instance``
using three tiers, most specific first:

1. the niess ``source_type`` recorded in the instance's provenance metadata,
2. the niess ``role`` recorded there,
3. the raw McCode component-type name, which every ``Instance`` carries whether
   or not niess produced it.

The registry only *resolves* builders; each target invokes them with whatever
signature it needs. Keeping resolution and invocation separate lets a caller
distinguish "no builder registered" from "a builder ran and declined to emit
anything" -- a distinction :mod:`niess.nexus` depends on for group suppression.
"""
from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

from .mccode import niess_source_type
from .provenance import NiessProvenance

B = TypeVar('B', bound=Callable[..., Any])


class NiessRegistry(Generic[B]):
    """Three-tier builder lookup keyed on provenance metadata or component type.

    A registry may extend another by naming it as ``parent``: lookups that find
    nothing locally fall through to the parent's own three tiers. That is how an
    instrument-specific registry adds its translators without touching the shared
    default one, so which translators apply is a property of a single conversion
    rather than of whatever the process happened to import.
    """

    def __init__(self, parent: 'NiessRegistry[B] | None' = None) -> None:
        self.parent = parent
        self._source_type_builders: dict[str, B] = {}
        self._role_builders: dict[str, B] = {}
        self._component_type_builders: dict[str, B] = {}

    def register(self, source: type | str):
        """Register against a niess class (or its dotted ``source_type`` name)."""
        source_type = source if isinstance(source, str) else niess_source_type(source)

        def decorator(func: B) -> B:
            self._source_type_builders[source_type] = func
            return func

        return decorator

    def register_role(self, role: str):
        """Register against a provenance ``role``."""
        def decorator(func: B) -> B:
            self._role_builders[role] = func
            return func

        return decorator

    def register_component_type(self, *comp_type_names: str):
        """Register against one or more raw McCode component-type names."""
        def decorator(func: B) -> B:
            for name in comp_type_names:
                self._component_type_builders[name] = func
            return func

        return decorator

    def resolve_builder(self, instance) -> B | None:
        """Return the builder for ``instance``, or ``None`` if none is registered.

        This registry's own three tiers are tried first, in full, before any parent
        is consulted: the more specific registry wins outright.

        ``None`` means *unhandled* -- it never means "handled, emit nothing".
        Callers that need that distinction must invoke the returned builder
        themselves and interpret its return value.
        """
        provenance = NiessProvenance.from_instance(instance)
        builder = self._resolve_local(instance, provenance)
        if builder is not None:
            return builder
        return None if self.parent is None else self.parent.resolve_builder(instance)

    def _resolve_local(self, instance, provenance) -> B | None:
        if provenance is not None:
            if provenance.source_type in self._source_type_builders:
                return self._source_type_builders[provenance.source_type]
            if provenance.role in self._role_builders:
                return self._role_builders[provenance.role]

        return self._component_type_builders.get(component_type_name(instance))

    def registered_component_types(self) -> frozenset[str]:
        """Component-type names this registry handles, inherited ones included."""
        inherited = frozenset() if self.parent is None else self.parent.registered_component_types()
        return frozenset(self._component_type_builders) | inherited


def component_type_name(instance) -> str:
    return getattr(instance.type, 'name', str(instance.type))


def component_type_category(instance) -> str | None:
    return getattr(instance.type, 'category', None)


def expr_float(value):
    if isinstance(value, (int, float)):
        return float(value)
    simplified = value.simplify() if hasattr(value, 'simplify') else value
    if hasattr(simplified, 'value') and isinstance(simplified.value, (int, float)):
        return float(simplified.value)
    return float(simplified)


def merged_params(instance, params: dict[str, float] | None = None) -> dict[str, float]:
    """Instance parameters evaluated to floats, layered over ``params``.

    Parameters that cannot be reduced to a float (they depend on a runtime
    instrument parameter, say) are skipped rather than raising.
    """
    merged = dict(params or {})
    for component_parameter in instance.parameters:
        try:
            evaluated = component_parameter.value.evaluate(merged)
            merged[component_parameter.name] = expr_float(evaluated)
        except Exception:
            continue
    return merged
