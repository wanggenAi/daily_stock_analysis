"""Authority tests for the compatibility production CLI."""
from __future__ import annotations

from src.strategies.genge_opportunity_discovery import production_decision_scan
from src.strategies.genge_opportunity_discovery import v311_production_bridge


def test_legacy_production_cli_delegates_to_strict_pit_bridge(monkeypatch, tmp_path) -> None:
    candidate = tmp_path / "candidates.csv"
    candidate.write_text("code\n600000\n", encoding="utf-8")
    holdings = tmp_path / "holdings.md"
    holdings.write_text("# holdings\n", encoding="utf-8")
    output = tmp_path / "production"
    captured: dict[str, list[str]] = {}

    def fake_bridge_main(argv: list[str] | None = None) -> int:
        captured["argv"] = list(argv or [])
        return 0

    monkeypatch.setattr(v311_production_bridge, "main", fake_bridge_main)

    result = production_decision_scan.main(
        [
            "--candidate-csv", str(candidate),
            "--holdings-md", str(holdings),
            "--output-dir", str(output),
            "--as-of", "2026-08-27",
        ]
    )

    assert result == 0
    argv = captured["argv"]
    assert argv[:2] == ["--source-csv", str(candidate)]
    assert ["--output-dir", str(output)] == argv[2:4]
    assert "--holdings-md" in argv
    assert "--as-of" in argv
    assert "--candidate-csv" not in argv
