"""Metadata validation for vector upserts.

Enforces that every vector has user_id, doc_id, and tenant_id — required
for compliance (right-to-deletion, tenant isolation, audit trails).
"""
from __future__ import annotations

from typing import Any


class MetadataValidationError(Exception):
    """Raised when vector metadata fails compliance validation."""

    def __init__(self, vector_id: str, missing_fields: list[str]) -> None:
        self.vector_id = vector_id
        self.missing_fields = missing_fields
        super().__init__(
            f"Vector {vector_id} missing required metadata fields: {', '.join(missing_fields)}"
        )


REQUIRED_METADATA_FIELDS = ("user_id", "doc_id", "tenant_id")


def validate_vector_metadata(metadata: dict[str, Any], vector_id: str) -> None:
    """Validate that metadata contains all required compliance fields.

    Raises MetadataValidationError if any required field is missing or empty.
    """
    missing = [
        field
        for field in REQUIRED_METADATA_FIELDS
        if not metadata.get(field)
    ]
    if missing:
        raise MetadataValidationError(vector_id=vector_id, missing_fields=missing)
