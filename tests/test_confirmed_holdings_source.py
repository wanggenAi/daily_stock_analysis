"""Tests for the strict confirmed-holdings production source contract."""

from datetime import date

from src.strategies.genge_opportunity_discovery.confirmed_holdings_source import (
    assess_confirmed_holdings_source,
)


def _write_holdings(path, *, evidence_date: str, quantity: str = "1000") -> None:
    path.write_text(
        "\n".join(
            [
                "# Confirmed Holdings",
                "",
                "| Code | Name | Quantity | Average Cost | Status | Evidence Date |",
                "| --- | --- | ---: | ---: | --- | --- |",
                f"| 601899 | fixture | {quantity} | 20.00 | CONFIRMED | {evidence_date} |",
            ]
        ),
        encoding="utf-8",
    )


def test_missing_holdings_source_is_not_enabled(tmp_path) -> None:
    assessment = assess_confirmed_holdings_source(
        tmp_path / "missing.md", as_of=date(2026, 8, 27)
    )

    assert assessment.enabled is False
    assert assessment.status == "HOLDINGS_NOT_EVALUATED_NO_FRESH_SOURCE"


def test_same_day_positive_confirmed_holdings_are_enabled(tmp_path) -> None:
    path = tmp_path / "holdings.md"
    _write_holdings(path, evidence_date="2026-08-27", quantity="1,000")

    assessment = assess_confirmed_holdings_source(path, as_of=date(2026, 8, 27))

    assert assessment.enabled is True
    assert assessment.status == "HOLDINGS_EVALUATED_FRESH_CONFIRMED_SOURCE"
    assert assessment.row_count == 1


def test_previous_day_holdings_are_rejected_as_stale(tmp_path) -> None:
    path = tmp_path / "holdings.md"
    _write_holdings(path, evidence_date="2026-08-26")

    assessment = assess_confirmed_holdings_source(path, as_of=date(2026, 8, 27))

    assert assessment.enabled is False
    assert assessment.status == "HOLDINGS_NOT_EVALUATED_STALE_SOURCE"


def test_zero_or_negative_quantity_is_rejected(tmp_path) -> None:
    for quantity in ("0", "-100", "not-a-number"):
        path = tmp_path / f"holdings-{quantity.replace('/', '_')}.md"
        _write_holdings(path, evidence_date="2026-08-27", quantity=quantity)

        assessment = assess_confirmed_holdings_source(path, as_of=date(2026, 8, 27))

        assert assessment.enabled is False
        assert assessment.status == "HOLDINGS_NOT_EVALUATED_INVALID_SOURCE"
