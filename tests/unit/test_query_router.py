from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from src.pipeline.routing import QueryRouter

# ---------------------------------------------------------------------------
# Helpers: deterministic embedding function for tests
# ---------------------------------------------------------------------------

# Each route gets a distinct "direction" in a 32-dimensional space.
# Queries matching a route are generated close to that direction.
ROUTE_VECTORS: dict[str, np.ndarray] = {
    "rag_knowledge_base": np.array([1.0, 0.0, 0.0, 0.0, 0.0] + [0.0] * 27, dtype=np.float32),
    "sql_structured_data": np.array([0.0, 1.0, 0.0, 0.0, 0.0] + [0.0] * 27, dtype=np.float32),
    "direct_llm": np.array([0.0, 0.0, 1.0, 0.0, 0.0] + [0.0] * 27, dtype=np.float32),
    "api_lookup": np.array([0.0, 0.0, 0.0, 1.0, 0.0] + [0.0] * 27, dtype=np.float32),
    "escalate_human": np.array([0.0, 0.0, 0.0, 0.0, 1.0] + [0.0] * 27, dtype=np.float32),
}

# Phrases that should map to each route (used in the fake embedder).
PHRASE_ROUTE_MAP: dict[str, str] = {
    # rag_knowledge_base utterances/queries
    "What does our company policy say about remote work?": "rag_knowledge_base",
    "Find information about the onboarding process": "rag_knowledge_base",
    "What are the technical requirements listed in the architecture document?": "rag_knowledge_base",
    "Summarize the key points from the Q3 earnings report": "rag_knowledge_base",
    # sql_structured_data
    "How many active users do we have this month?": "sql_structured_data",
    "Show me the revenue breakdown by region for Q4": "sql_structured_data",
    "What is the average response time for API calls last week?": "sql_structured_data",
    "Compare sales figures between January and February": "sql_structured_data",
    # direct_llm
    "Write me a professional email to decline a meeting invitation": "direct_llm",
    "Help me brainstorm names for our new product feature": "direct_llm",
    "What are some best practices for conducting code reviews?": "direct_llm",
    "Draft a job description for a senior backend engineer": "direct_llm",
    # api_lookup
    "What is the current status of the production deployment?": "api_lookup",
    "Check if the payment gateway is operational right now": "api_lookup",
    "What is the latest stock price for AAPL?": "api_lookup",
    "Is the CI/CD pipeline currently running for the main branch?": "api_lookup",
    # escalate_human
    "I want to file a formal complaint about your service": "escalate_human",
    "This is a legal matter regarding our contract terms": "escalate_human",
    "I need to speak with a human representative immediately": "escalate_human",
    "I am considering legal action against the company": "escalate_human",
}


async def fake_embed_fn(texts: list[str]) -> list[list[float]]:
    """Deterministic embedding function for tests.

    Texts that appear in PHRASE_ROUTE_MAP get the vector for their route.
    Unknown texts get a vector with small random-looking but deterministic noise
    that is *not close* to any route (simulates an ambiguous query).
    """
    results: list[list[float]] = []
    for text in texts:
        route = PHRASE_ROUTE_MAP.get(text)
        if route is not None:
            # Strong signal: the route's basis vector + small noise
            vec = ROUTE_VECTORS[route].copy()
            vec += np.random.RandomState(hash(text) % 2**31).uniform(-0.05, 0.05, len(vec)).astype(np.float32)
            results.append(vec.tolist())
        else:
            # Weak / ambiguous: small uniform noise, no clear direction
            vec = np.random.RandomState(hash(text) % 2**31).uniform(-0.1, 0.1, 32).astype(np.float32)
            results.append(vec.tolist())
    return results


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def routes_yaml_path() -> Path:
    """Return the path to the real routes.yaml bundled with the module."""
    return Path(__file__).resolve().parents[2] / "src" / "pipeline" / "routing" / "routes.yaml"


@pytest.fixture
def minimal_routes_path(tmp_path: Path) -> Path:
    """Write a small routes YAML for focused tests and return the path."""
    data: dict[str, Any] = {
        "routes": [
            {
                "name": "rag_knowledge_base",
                "description": "Document Q&A",
                "utterances": [
                    "What does our company policy say about remote work?",
                    "Find information about the onboarding process",
                ],
            },
            {
                "name": "sql_structured_data",
                "description": "Structured data queries",
                "utterances": [
                    "How many active users do we have this month?",
                    "Show me the revenue breakdown by region for Q4",
                ],
            },
            {
                "name": "direct_llm",
                "description": "Creative / general chat",
                "utterances": [
                    "Write me a professional email to decline a meeting invitation",
                    "Help me brainstorm names for our new product feature",
                ],
            },
            {
                "name": "api_lookup",
                "description": "Real-time lookups",
                "utterances": [
                    "What is the current status of the production deployment?",
                    "Check if the payment gateway is operational right now",
                ],
            },
            {
                "name": "escalate_human",
                "description": "Escalation",
                "utterances": [
                    "I want to file a formal complaint about your service",
                    "This is a legal matter regarding our contract terms",
                ],
            },
        ],
    }
    path = tmp_path / "routes.yaml"
    with open(path, "w") as f:
        yaml.safe_dump(data, f)
    return path


@pytest.fixture
async def router(minimal_routes_path: Path) -> QueryRouter:
    """Return an initialised QueryRouter backed by the deterministic embedder."""
    r = QueryRouter(
        default_route="rag_knowledge_base",
        confidence_threshold=0.7,
        routes_path=minimal_routes_path,
        embed_fn=fake_embed_fn,
    )
    await r.initialize()
    return r


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRouteLoading:
    """Tests for loading route definitions from YAML."""

    def test_load_real_routes_file(self, routes_yaml_path: Path) -> None:
        """The bundled routes.yaml should parse and contain 5 routes."""
        with open(routes_yaml_path) as f:
            raw = yaml.safe_load(f)
        assert "routes" in raw
        assert len(raw["routes"]) == 5

    def test_all_five_routes_present(self, routes_yaml_path: Path) -> None:
        """All expected route names must be present in the routes file."""
        with open(routes_yaml_path) as f:
            raw = yaml.safe_load(f)
        names = {r["name"] for r in raw["routes"]}
        assert names == {
            "rag_knowledge_base",
            "sql_structured_data",
            "direct_llm",
            "api_lookup",
            "escalate_human",
        }

    def test_each_route_has_sufficient_utterances(self, routes_yaml_path: Path) -> None:
        """Each route should have at least 10 utterance examples."""
        with open(routes_yaml_path) as f:
            raw = yaml.safe_load(f)
        for route in raw["routes"]:
            assert len(route["utterances"]) >= 10, (
                f"Route {route['name']} has only {len(route['utterances'])} utterances"
            )

    async def test_router_loads_routes_on_init(self, minimal_routes_path: Path) -> None:
        """initialize() should populate the routes list."""
        r = QueryRouter(
            routes_path=minimal_routes_path,
            embed_fn=fake_embed_fn,
        )
        assert r.routes == []
        await r.initialize()
        assert len(r.routes) == 5

    async def test_missing_routes_file_raises(self, tmp_path: Path) -> None:
        """A missing YAML file should raise FileNotFoundError."""
        r = QueryRouter(
            routes_path=tmp_path / "nonexistent.yaml",
            embed_fn=fake_embed_fn,
        )
        with pytest.raises(FileNotFoundError):
            await r.initialize()


class TestRouting:
    """Tests for the actual query routing logic."""

    async def test_routes_rag_query_correctly(self, router: QueryRouter) -> None:
        """A clear knowledge-lookup query should route to rag_knowledge_base."""
        result = await router.route("What does our company policy say about remote work?")
        assert result["route"] == "rag_knowledge_base"
        assert result["confidence"] >= 0.7

    async def test_routes_sql_query_correctly(self, router: QueryRouter) -> None:
        """A structured-data query should route to sql_structured_data."""
        result = await router.route("How many active users do we have this month?")
        assert result["route"] == "sql_structured_data"
        assert result["confidence"] >= 0.7

    async def test_routes_direct_llm_query_correctly(self, router: QueryRouter) -> None:
        """A creative/general query should route to direct_llm."""
        result = await router.route(
            "Write me a professional email to decline a meeting invitation"
        )
        assert result["route"] == "direct_llm"
        assert result["confidence"] >= 0.7

    async def test_routes_api_lookup_query_correctly(self, router: QueryRouter) -> None:
        """A real-time status query should route to api_lookup."""
        result = await router.route(
            "What is the current status of the production deployment?"
        )
        assert result["route"] == "api_lookup"
        assert result["confidence"] >= 0.7

    async def test_routes_escalation_query_correctly(self, router: QueryRouter) -> None:
        """A complaint/legal query should route to escalate_human."""
        result = await router.route("I want to file a formal complaint about your service")
        assert result["route"] == "escalate_human"
        assert result["confidence"] >= 0.7


class TestFallbackBehavior:
    """Tests for default-route fallback when confidence is below threshold."""

    async def test_fallback_on_low_confidence(self, minimal_routes_path: Path) -> None:
        """An ambiguous query should fall back to the default route."""
        r = QueryRouter(
            default_route="rag_knowledge_base",
            confidence_threshold=0.7,
            routes_path=minimal_routes_path,
            embed_fn=fake_embed_fn,
        )
        # A query not in PHRASE_ROUTE_MAP gets near-zero vectors -> low similarity
        result = await r.route("xyzzy foobar nonsense gibberish")
        assert result["route"] == "rag_knowledge_base"
        assert result["confidence"] < 0.7

    async def test_high_threshold_forces_fallback(self, minimal_routes_path: Path) -> None:
        """Even a matching query should fall back when the threshold is set to 1.0."""
        r = QueryRouter(
            default_route="rag_knowledge_base",
            confidence_threshold=1.0,
            routes_path=minimal_routes_path,
            embed_fn=fake_embed_fn,
        )
        result = await r.route("How many active users do we have this month?")
        # With threshold 1.0, almost nothing will pass
        assert result["route"] == "rag_knowledge_base"


class TestResultStructure:
    """Tests for the shape / keys of the route result dict."""

    async def test_result_has_required_keys(self, router: QueryRouter) -> None:
        """The result dict must contain all keys the orchestrator depends on."""
        result = await router.route("test query")
        assert "route" in result
        assert "confidence" in result
        assert "matched_utterances" in result
        assert "scores" in result
        assert "skipped" in result

    async def test_skipped_is_false(self, router: QueryRouter) -> None:
        """The semantic router should never set skipped=True (that was the stub)."""
        result = await router.route("test query")
        assert result["skipped"] is False

    async def test_confidence_is_numeric(self, router: QueryRouter) -> None:
        """Confidence should be a float between 0 and 1."""
        result = await router.route("test query")
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0

    async def test_scores_contains_all_routes(self, router: QueryRouter) -> None:
        """The scores dict should have an entry for every loaded route."""
        result = await router.route("test query")
        assert set(result["scores"].keys()) == {
            "rag_knowledge_base",
            "sql_structured_data",
            "direct_llm",
            "api_lookup",
            "escalate_human",
        }


class TestConstructorValidation:
    """Tests for constructor argument validation."""

    def test_requires_embedding_source(self) -> None:
        """Constructing without embed_fn or embedding_service should raise."""
        with pytest.raises(ValueError, match="embed_fn or embedding_service"):
            QueryRouter()

    async def test_lazy_initialization(self, minimal_routes_path: Path) -> None:
        """The router should auto-initialize on the first route() call."""
        r = QueryRouter(
            routes_path=minimal_routes_path,
            embed_fn=fake_embed_fn,
        )
        assert not r._initialized
        await r.route("test")
        assert r._initialized
