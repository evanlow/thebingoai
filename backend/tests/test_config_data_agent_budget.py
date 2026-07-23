"""Phase 1: the DATA_AGENT_QUERY_BUDGET config knob.

Default is 5; env override wins; .env.example documents it.
"""
from pathlib import Path


def test_query_budget_defaults_to_5(monkeypatch):
    monkeypatch.delenv("DATA_AGENT_QUERY_BUDGET", raising=False)
    from backend.config import Settings

    # openai_api_key is the one required field; supply it so a fresh Settings loads.
    assert Settings(openai_api_key="test-key").data_agent_query_budget == 5


def test_query_budget_env_override(monkeypatch):
    monkeypatch.setenv("DATA_AGENT_QUERY_BUDGET", "3")
    from backend.config import Settings

    assert Settings(openai_api_key="test-key").data_agent_query_budget == 3


def test_env_example_documents_budget():
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".env.example"
        if candidate.exists():
            assert "DATA_AGENT_QUERY_BUDGET=" in candidate.read_text()
            return
    raise AssertionError(".env.example not found in any parent directory")
