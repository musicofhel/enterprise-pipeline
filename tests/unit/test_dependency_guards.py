"""Version guards for critical dependency constraints.

These tests fail fast if a dependency drifts outside its required range,
preventing silent regressions like the transformers v5 → HHEM breakage.
"""
from __future__ import annotations


def test_transformers_version_pinned() -> None:
    """transformers >=5 breaks HHEM (all_tied_weights_keys rename)."""
    import transformers

    major = int(transformers.__version__.split(".")[0])
    assert major < 5, (
        f"transformers {transformers.__version__} breaks HHEM — pin to <5.0.0 in pyproject.toml"
    )
