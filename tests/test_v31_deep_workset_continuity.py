from __future__ import annotations

import json

import pytest

from src.strategies.genge_opportunity_discovery.v31_deep_gap_closure import (
    resolve_requested_codes,
)


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _config(required):
    return {
        "contract": "GEN_GE_V31_EXPLICIT_DEEP_REVIEW_V1",
        "authority": "RESEARCH_ONLY",
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "continuity_required_codes": required,
        "profiles": {},
    }


def _terminal(codes):
    return {
        "contract": "GEN_GE_V31_TERMINAL_RESEARCH_DECISION_V1",
        "research_authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "terminal_rows": [{"code": code, "research_decision": "REJECT"} for code in codes],
    }


def test_live_workset_unions_terminal_and_bootstrap_continuity(tmp_path):
    config_path = tmp_path / "explicit.json"
    terminal_path = tmp_path / "terminal.json"
    _write_json(config_path, _config(["001316", "601899"]))
    _write_json(terminal_path, _terminal(["603233", "603993"]))

    requested = resolve_requested_codes(
        ["600406", "603993"],
        continuity_config=config_path,
        terminal_path=terminal_path,
    )

    assert requested == ["001316", "600406", "601899", "603233", "603993"]


def test_missing_continuity_sources_preserve_live_requests(tmp_path):
    requested = resolve_requested_codes(
        ["603993", "001316", "603993"],
        continuity_config=tmp_path / "missing-config.json",
        terminal_path=tmp_path / "missing-terminal.json",
    )
    assert requested == ["001316", "603993"]


def test_untrusted_terminal_authority_fails_closed(tmp_path):
    config_path = tmp_path / "explicit.json"
    terminal_path = tmp_path / "terminal.json"
    _write_json(config_path, _config(["601899"]))
    terminal = _terminal(["603233"])
    terminal["formal_trading_authority"] = True
    _write_json(terminal_path, terminal)

    with pytest.raises(ValueError, match="must not grant Formal authority"):
        resolve_requested_codes(
            ["603993"],
            continuity_config=config_path,
            terminal_path=terminal_path,
        )


def test_continuity_config_cannot_relax_unknown_gate(tmp_path):
    config_path = tmp_path / "explicit.json"
    terminal_path = tmp_path / "terminal.json"
    config = _config(["601899"])
    config["unknown_is_pass"] = True
    _write_json(config_path, config)
    _write_json(terminal_path, _terminal([]))

    with pytest.raises(ValueError, match="UNKNOWN != PASS"):
        resolve_requested_codes(
            ["603993"],
            continuity_config=config_path,
            terminal_path=terminal_path,
        )
