from __future__ import annotations

import json

from src.strategies.genge_opportunity_discovery import risk_capped_complete_event_scan as wrapper


def test_repository_execution_capital_config_is_loaded(monkeypatch, tmp_path):
    config = tmp_path / "execution_portfolio.json"
    config.write_text(json.dumps({"portfolio_capital": 250000}), encoding="utf-8")
    monkeypatch.setattr(wrapper, "EXECUTION_PORTFOLIO_CONFIG", config)
    monkeypatch.delenv("GENGE_PORTFOLIO_CAPITAL", raising=False)

    assert wrapper._portfolio_capital() == 250000.0


def test_environment_execution_capital_overrides_repository_config(monkeypatch, tmp_path):
    config = tmp_path / "execution_portfolio.json"
    config.write_text(json.dumps({"portfolio_capital": 250000}), encoding="utf-8")
    monkeypatch.setattr(wrapper, "EXECUTION_PORTFOLIO_CONFIG", config)
    monkeypatch.setenv("GENGE_PORTFOLIO_CAPITAL", "300000")

    assert wrapper._portfolio_capital() == 300000.0


def test_invalid_execution_capital_fails_to_unknown_without_affecting_policy(monkeypatch, tmp_path):
    config = tmp_path / "execution_portfolio.json"
    config.write_text("not-json", encoding="utf-8")
    monkeypatch.setattr(wrapper, "EXECUTION_PORTFOLIO_CONFIG", config)
    monkeypatch.setenv("GENGE_PORTFOLIO_CAPITAL", "invalid")

    assert wrapper._portfolio_capital() is None
