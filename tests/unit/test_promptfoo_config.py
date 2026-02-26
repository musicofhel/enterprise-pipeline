"""Tests for Promptfoo configuration — 4 tests."""
from __future__ import annotations

import json
from pathlib import Path

import yaml


class TestPromptfooConfig:
    def test_config_file_exists(self) -> None:
        assert Path("promptfoo.config.yaml").exists()

    def test_config_has_required_keys(self) -> None:
        with open("promptfoo.config.yaml") as f:
            config = yaml.safe_load(f)
        assert "prompts" in config
        assert "providers" in config
        assert "tests" in config
        assert len(config["prompts"]) == 2

    def test_golden_dataset_jsonl_valid(self) -> None:
        path = Path("golden_dataset/promptfoo_tests.jsonl")
        assert path.exists()
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 20
        for line in lines:
            data = json.loads(line)
            assert "vars" in data
            assert "query" in data["vars"]
            assert "context" in data["vars"]

    def test_prompts_exist(self) -> None:
        assert Path("prompts/current.txt").exists()
        assert Path("prompts/candidate.txt").exists()
        # Candidate should have the extra "Think step by step" rule
        candidate = Path("prompts/candidate.txt").read_text()
        assert "step by step" in candidate.lower()
