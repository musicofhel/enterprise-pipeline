
import pytest
from pydantic import ValidationError

from src.config.pipeline_config import PipelineConfig, load_pipeline_config


def test_default_config():
    config = PipelineConfig()
    assert config.version == "1.0.0"
    assert config.chunking.strategy == "by_title"
    assert config.retrieval.top_k == 20
    assert config.compression.max_total_tokens == 4000
    assert config.generation.model == "gpt-4o"


def test_load_config_from_yaml():
    config = load_pipeline_config(
        config_path="pipeline_config.yaml",
        env="development",
    )
    assert config.version == "1.0.0"
    assert config.chunking.max_characters == 1500


def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_pipeline_config(config_path="nonexistent.yaml")


def test_config_is_frozen():
    config = PipelineConfig()
    with pytest.raises(ValidationError):
        config.version = "2.0.0"  # type: ignore[misc]
