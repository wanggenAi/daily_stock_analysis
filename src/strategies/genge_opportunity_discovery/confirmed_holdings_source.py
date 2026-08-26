"""Freshness contract for manually confirmed V3.1.1 production holdings.

Holdings are an execution-state input, not a research inference.  Production
may evaluate holding-specific SELL/REDUCE actions only when every parsed row is
explicitly confirmed for the decision date and has a positive quantity.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from .production_decision_scan import read_holdings_markdown


STABLE_HOLDINGS_PATH = Path("data/user_supplied/manual_confirmed_holdings.md")


@dataclass(frozen=True)
class HoldingsSourceAssessment:
    enabled: bool
    status: str
    reason: str
    source: str
    row_count: int
    as_of: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def assess_confirmed_holdings_source(
    path: Path = STABLE_HOLDINGS_PATH,
    *,
    as_of: date,
) -> HoldingsSourceAssessment:
    """Validate the stable holdings file against a strict same-day contract."""
    if not path.exists():
        return HoldingsSourceAssessment(
            False,
            "HOLDINGS_NOT_EVALUATED_NO_FRESH_SOURCE",
            "stable confirmed-holdings file missing",
            "",
            0,
            as_of.isoformat(),
        )

    rows = read_holdings_markdown(path)
    if not rows:
        return HoldingsSourceAssessment(
            False,
            "HOLDINGS_NOT_EVALUATED_INVALID_SOURCE",
            "confirmed-holdings file exists but has no parseable rows",
            str(path),
            0,
            as_of.isoformat(),
        )

    expected_date = as_of.isoformat()
    evidence_dates = {str(row.get("holding_evidence_date") or "").strip() for row in rows}
    if evidence_dates != {expected_date}:
        return HoldingsSourceAssessment(
            False,
            "HOLDINGS_NOT_EVALUATED_STALE_SOURCE",
            f"holding evidence dates {sorted(evidence_dates)} do not equal {expected_date}",
            str(path),
            len(rows),
            expected_date,
        )

    invalid_codes: list[str] = []
    for row in rows:
        try:
            quantity = float(str(row.get("confirmed_quantity") or "").replace(",", "").strip())
        except (TypeError, ValueError):
            quantity = 0.0
        if quantity <= 0:
            invalid_codes.append(str(row.get("code") or "UNKNOWN"))
    if invalid_codes:
        return HoldingsSourceAssessment(
            False,
            "HOLDINGS_NOT_EVALUATED_INVALID_SOURCE",
            "non-positive or invalid confirmed quantity: " + ",".join(invalid_codes),
            str(path),
            len(rows),
            expected_date,
        )

    return HoldingsSourceAssessment(
        True,
        "HOLDINGS_EVALUATED_FRESH_CONFIRMED_SOURCE",
        f"{len(rows)} holdings confirmed for {expected_date}",
        str(path),
        len(rows),
        expected_date,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=STABLE_HOLDINGS_PATH)
    parser.add_argument("--as-of")
    args = parser.parse_args(argv)
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    assessment = assess_confirmed_holdings_source(args.path, as_of=as_of)
    print(json.dumps(assessment.as_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
