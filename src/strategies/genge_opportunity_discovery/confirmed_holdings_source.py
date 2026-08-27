"""Durable confirmation contract for GenGe V3.1.1 production holdings.

Holdings are execution-state input, not a research inference.  The repository
``CURRENT_HOLDINGS.md`` is updated only from explicit user confirmation or
user-provided broker evidence and remains authoritative until the user reports
a transaction or supplies newer evidence. Daily production refreshes market,
filing and valuation evidence; it does not require the user to re-confirm an
unchanged position every morning.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from .production_decision_scan import read_holdings_markdown


STABLE_HOLDINGS_PATH = Path("CURRENT_HOLDINGS.md")


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
    """Validate durable confirmed holdings without inventing daily transactions.

    Evidence dates prove when the position was last explicitly confirmed. They
    may precede ``as_of`` because unchanged holdings remain confirmed until the
    user reports a trade. Future/invalid evidence dates and non-positive
    quantities fail closed.
    """
    if not path.exists():
        return HoldingsSourceAssessment(
            False,
            "HOLDINGS_NOT_EVALUATED_NO_CONFIRMED_SOURCE",
            "durable confirmed-holdings file missing",
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

    parsed_dates: list[date] = []
    invalid_date_codes: list[str] = []
    future_date_codes: list[str] = []
    invalid_quantity_codes: list[str] = []
    for row in rows:
        code = str(row.get("code") or "UNKNOWN")
        raw_date = str(row.get("holding_evidence_date") or "").strip()
        try:
            evidence_date = date.fromisoformat(raw_date)
        except ValueError:
            invalid_date_codes.append(code)
        else:
            parsed_dates.append(evidence_date)
            if evidence_date > as_of:
                future_date_codes.append(code)

        try:
            quantity = float(str(row.get("confirmed_quantity") or "").replace(",", "").strip())
        except (TypeError, ValueError):
            quantity = 0.0
        if quantity <= 0:
            invalid_quantity_codes.append(code)

    problems: list[str] = []
    if invalid_date_codes:
        problems.append("invalid evidence date: " + ",".join(invalid_date_codes))
    if future_date_codes:
        problems.append("future evidence date: " + ",".join(future_date_codes))
    if invalid_quantity_codes:
        problems.append("non-positive or invalid confirmed quantity: " + ",".join(invalid_quantity_codes))
    if problems:
        return HoldingsSourceAssessment(
            False,
            "HOLDINGS_NOT_EVALUATED_INVALID_SOURCE",
            "; ".join(problems),
            str(path),
            len(rows),
            as_of.isoformat(),
        )

    oldest = min(parsed_dates).isoformat()
    newest = max(parsed_dates).isoformat()
    return HoldingsSourceAssessment(
        True,
        "HOLDINGS_EVALUATED_DURABLE_CONFIRMED_SOURCE",
        (
            f"{len(rows)} holdings explicitly confirmed; evidence range {oldest}..{newest}; "
            "state remains valid until explicit user-reported transaction/newer broker evidence"
        ),
        str(path),
        len(rows),
        as_of.isoformat(),
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
