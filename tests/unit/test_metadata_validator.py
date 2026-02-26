"""Tests for vector metadata validation."""
from __future__ import annotations

import pytest

from src.pipeline.retrieval.metadata_validator import (
    MetadataValidationError,
    validate_vector_metadata,
)


class TestValidateVectorMetadata:
    def test_valid_metadata_passes(self) -> None:
        metadata = {"user_id": "u1", "doc_id": "d1", "tenant_id": "t1"}
        validate_vector_metadata(metadata, "vec-1")  # Should not raise

    def test_missing_user_id_raises(self) -> None:
        metadata = {"doc_id": "d1", "tenant_id": "t1"}
        with pytest.raises(MetadataValidationError) as exc_info:
            validate_vector_metadata(metadata, "vec-1")
        assert "user_id" in exc_info.value.missing_fields

    def test_missing_multiple_fields_raises(self) -> None:
        metadata = {"tenant_id": "t1"}
        with pytest.raises(MetadataValidationError) as exc_info:
            validate_vector_metadata(metadata, "vec-1")
        assert set(exc_info.value.missing_fields) == {"user_id", "doc_id"}

    def test_empty_string_treated_as_missing(self) -> None:
        metadata = {"user_id": "", "doc_id": "d1", "tenant_id": "t1"}
        with pytest.raises(MetadataValidationError) as exc_info:
            validate_vector_metadata(metadata, "vec-1")
        assert "user_id" in exc_info.value.missing_fields

    def test_all_fields_missing(self) -> None:
        with pytest.raises(MetadataValidationError) as exc_info:
            validate_vector_metadata({}, "vec-1")
        assert len(exc_info.value.missing_fields) == 3

    def test_extra_fields_allowed(self) -> None:
        metadata = {
            "user_id": "u1", "doc_id": "d1", "tenant_id": "t1",
            "extra_field": "ok",
        }
        validate_vector_metadata(metadata, "vec-1")  # Should not raise
