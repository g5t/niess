"""McCode to ESS NeXus Structure JSON conversion.

Dispatches translators over the assembled ``mccode_antlr`` ``Instance`` tree, the
same handoff point :mod:`niess.brep` uses, and builds NeXus Structure JSON dicts
directly -- there is no intermediate NeXus object model.

    from niess.nexus import to_nexus_structure
    structure = to_nexus_structure(assembler.instrument, origin='sample_origin')
"""
from .instrument import (
    DEFAULT_NXLOG_ROOT,
    NexusContext,
    Translation,
    component_body,
    to_nexus_structure,
)
from .cli import load_instr
from .off import NXoff
from .registry import DEFAULT_NEXUS_REGISTRY, NiessNexusRegistry

# Both register translators on DEFAULT_NEXUS_REGISTRY at import time
from . import translators as _translators  # noqa: F401
from . import bifrost as _bifrost  # noqa: F401

__all__ = [
    'DEFAULT_NEXUS_REGISTRY',
    'DEFAULT_NXLOG_ROOT',
    'NXoff',
    'load_instr',
    'NexusContext',
    'NiessNexusRegistry',
    'Translation',
    'component_body',
    'to_nexus_structure',
]
