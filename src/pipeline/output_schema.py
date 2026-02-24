"""Output schema enforcement for LLM responses.

Validates that LLM outputs conform to a defined JSON schema per route.
When the output doesn't conform, returns a structured error response
instead of crashing.

Note: This enforces STRUCTURE only, not content. It does not detect
prompt injection in output content — that requires output safety checks.
"""
from __future__ import annotations

import json
from typing import Any

import structlog
from jsonschema import Draft7Validator

logger = structlog.get_logger()

# Default RAG response schema
RAG_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "sources_used": {"type": "array", "items": {"type": "string"}},
        "caveats": {"type": ["string", "null"]},
    },
    "required": ["answer"],
    "additionalProperties": True,
}

# Direct LLM route schema — no sources needed
DIRECT_LLM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["answer"],
    "additionalProperties": True,
}

# Route-to-schema mapping
DEFAULT_ROUTE_SCHEMAS: dict[str, dict[str, Any]] = {
    "rag_knowledge_base": RAG_RESPONSE_SCHEMA,
    "direct_llm": DIRECT_LLM_SCHEMA,
}


class OutputSchemaEnforcer:
    """Validates LLM output against per-route JSON schemas.

    When the LLM returns a plain string (not JSON), wraps it in the expected
    schema structure. When it returns invalid JSON, logs the raw output and
    returns a structured error.
    """

    def __init__(
        self,
        route_schemas: dict[str, dict[str, Any]] | None = None,
        strip_extra_fields: bool = False,
    ) -> None:
        self._schemas = route_schemas or DEFAULT_ROUTE_SCHEMAS
        self._strip_extra = strip_extra_fields
        # Pre-compile validators
        self._validators: dict[str, Draft7Validator] = {}
        for route, schema in self._schemas.items():
            self._validators[route] = Draft7Validator(schema)

    def enforce(
        self,
        raw_output: str,
        route: str = "rag_knowledge_base",
    ) -> dict[str, Any]:
        """Validate and normalize LLM output.

        Args:
            raw_output: The raw string output from the LLM.
            route: The pipeline route, determines which schema to apply.

        Returns:
            dict with "valid", "output" (parsed dict), and optionally "errors".
        """
        schema = self._schemas.get(route)
        if schema is None:
            # No schema for this route — pass through
            return {
                "valid": True,
                "output": {"answer": raw_output},
                "schema_applied": None,
            }

        # Try to parse as JSON
        parsed = self._try_parse_json(raw_output)

        if parsed is None:
            # Not JSON — wrap plain text as answer
            wrapped = {"answer": raw_output.strip()}
            return {
                "valid": True,
                "output": wrapped,
                "schema_applied": route,
                "wrapped": True,
            }

        # Validate against schema
        validator = self._validators.get(route)
        if validator is None:
            validator = Draft7Validator(schema)

        errors = list(validator.iter_errors(parsed))

        if errors:
            error_messages = [e.message for e in errors]
            logger.warning(
                "output_schema_violation",
                route=route,
                errors=error_messages,
                raw_output_length=len(raw_output),
            )
            return {
                "valid": False,
                "output": {"answer": raw_output.strip()},
                "errors": error_messages,
                "schema_applied": route,
                "raw_output": raw_output[:500],
            }

        # Valid — optionally strip extra fields
        if self._strip_extra:
            allowed = set(schema.get("properties", {}).keys())
            parsed = {k: v for k, v in parsed.items() if k in allowed}

        return {
            "valid": True,
            "output": parsed,
            "schema_applied": route,
        }

    def get_schema(self, route: str) -> dict[str, Any] | None:
        """Get the schema for a given route."""
        return self._schemas.get(route)

    @staticmethod
    def _try_parse_json(text: str) -> dict[str, Any] | None:
        """Try to parse text as JSON. Returns dict or None."""
        text = text.strip()
        if not text.startswith("{"):
            return None
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        return None
