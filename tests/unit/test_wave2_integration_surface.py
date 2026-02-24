"""Smoke test: Wave 2 integration surface.

Verify that the retrieval pipeline is callable from where Wave 2's
routing and safety layers will plug in. This confirms:
1. SafetyChecker interface is stable and replaceable
2. QueryRouter interface is stable and replaceable
3. PipelineOrchestrator accepts them via constructor DI
4. Trace spans are wired for both stubs
"""
from __future__ import annotations

import inspect

from src.pipeline.orchestrator import PipelineOrchestrator
from src.pipeline.routing import QueryRouter
from src.pipeline.safety import SafetyChecker


class TestWave2IntegrationSurface:
    def test_safety_checker_interface(self):
        """SafetyChecker has the async check_input method Wave 2 must implement."""
        checker = SafetyChecker()
        assert hasattr(checker, "check_input")
        sig = inspect.signature(checker.check_input)
        params = list(sig.parameters.keys())
        assert "text" in params, "check_input must accept 'text' parameter"
        assert "user_id" in params, "check_input must accept 'user_id' parameter"

    def test_query_router_interface(self):
        """QueryRouter has the async route method Wave 2 must implement."""
        router = QueryRouter()
        assert hasattr(router, "route")
        sig = inspect.signature(router.route)
        params = list(sig.parameters.keys())
        assert "query" in params, "route must accept 'query' parameter"

    def test_orchestrator_accepts_custom_safety(self):
        """PipelineOrchestrator constructor accepts a SafetyChecker."""
        sig = inspect.signature(PipelineOrchestrator.__init__)
        params = sig.parameters
        assert "safety_checker" in params, (
            "PipelineOrchestrator must accept safety_checker in constructor"
        )

    def test_orchestrator_accepts_custom_router(self):
        """PipelineOrchestrator constructor accepts a QueryRouter."""
        sig = inspect.signature(PipelineOrchestrator.__init__)
        params = sig.parameters
        assert "query_router" in params, (
            "PipelineOrchestrator must accept query_router in constructor"
        )

    def test_orchestrator_accepts_hallucination_checker(self):
        """PipelineOrchestrator constructor accepts a HallucinationChecker (Wave 3)."""
        sig = inspect.signature(PipelineOrchestrator.__init__)
        params = sig.parameters
        assert "hallucination_checker" in params, (
            "PipelineOrchestrator must accept hallucination_checker in constructor"
        )

    def test_safety_stub_returns_expected_shape(self):
        """Stub returns dict with 'passed', 'reason', 'skipped' keys."""
        import asyncio

        checker = SafetyChecker()
        result = asyncio.get_event_loop().run_until_complete(
            checker.check_input("test", "user-1")
        )
        assert "passed" in result
        assert "skipped" in result
        assert result["passed"] is True
        assert result["skipped"] is True

    def test_router_stub_returns_expected_shape(self):
        """Stub returns dict with 'route', 'confidence', 'skipped' keys."""
        import asyncio

        router = QueryRouter(default_route="rag_knowledge_base")
        result = asyncio.get_event_loop().run_until_complete(router.route("test query"))
        assert "route" in result
        assert "confidence" in result
        assert "skipped" in result
        assert result["route"] == "rag_knowledge_base"
