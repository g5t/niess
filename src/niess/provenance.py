from __future__ import annotations
from typing import Any
from dataclasses import dataclass

from .mccode import read_niess_metadata


@dataclass(frozen=True)
class NiessProvenance:
    namespace: str
    schema_version: int
    source_type: str
    source_name: str
    role: str
    extra: dict[str, Any]

    @classmethod
    def from_instance(cls, instance) -> NiessProvenance | None:
        payload = read_niess_metadata(instance)
        if payload is None:
            return None
        return cls(
            namespace=payload['namespace'],
            schema_version=payload['schema_version'],
            source_type=payload['source_type'],
            source_name=payload['source_name'],
            role=payload.get('role', 'physical-component'),
            extra=payload.get('extra', {}),
        )
