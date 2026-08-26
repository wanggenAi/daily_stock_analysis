from __future__ import annotations

"""V3.1 PIT out-of-sample round 2.

LOCKED BEFORE RESULTS.

This round changes only the fixed research universe. It deliberately reuses the
same V3.1 valuation/execution rules tested in round 1:
- 2018-01-01 .. 2026-08-24
- trailing 756 trading-day PE/PB median anchor, shifted one day
- minimum 252 trading days of anchor history
- month-end rebalance
- one-way friction 0.10%
- BUY: <=0.85 50% cap, <=0.75 75% cap, <=0.65 100% cap
- SELL: >=1.20 max 75%, >=1.40 max 50%, >=1.70 max 25%
- entry cost never influences SELL

Universe is pre-declared here before any round-2 output is observed. All symbols
are Shanghai/Shenzhen main-board A shares.

As in round 1, this is an execution-layer test conditional on the companies being
in the research universe. It is NOT a historical reconstruction of qualitative
moat/hard-gate judgements.
"""

from pathlib import Path

import v31_pit_sector_backtest as core
import v31_pit_sector_backtest_resilient as transport

LOCKED_GROUPS = {
    "strategic_resources": ["601899", "603993", "600549", "000657"],
    "grid_equipment": ["600406", "600312", "000400"],
    "semiconductor": ["603986", "603501", "600460"],
    "combined": [
        "601899", "603993", "600549", "000657",
        "600406", "600312", "000400",
        "603986", "603501", "600460",
    ],
}

LOCKED_NAMES = {
    "601899": "紫金矿业",
    "603993": "洛阳钼业",
    "600549": "厦门钨业",
    "000657": "中钨高新",
    "600406": "国电南瑞",
    "600312": "平高电气",
    "000400": "许继电气",
    "603986": "兆易创新",
    "603501": "韦尔股份",
    "600460": "士兰微",
}


def main() -> None:
    # Universe/output transport are the ONLY overrides. Strategy thresholds,
    # valuation construction, transaction costs and rebalance logic stay in core.
    core.GROUPS = LOCKED_GROUPS
    core.NAMES = LOCKED_NAMES
    core.OUT = Path("artifacts/v31_pit_oos_round2")

    core.fetch_price = transport.resilient_fetch_price
    core.fetch_valuation = transport.resilient_fetch_valuation
    core.fetch_csi300 = transport.resilient_fetch_csi300

    core.main()

    # Correct the generic round-1 wording without touching computed numbers.
    report = core.OUT / "REPORT.md"
    if report.exists():
        text = report.read_text(encoding="utf-8")
        text = text.replace(
            "fixed five-stock research universe",
            "fixed pre-declared 10-stock out-of-sample research universe",
        )
        text = text.replace(
            "# V3.1 PIT sector backtest (locked rules)",
            "# V3.1 PIT out-of-sample round 2 (locked rules)",
        )
        report.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
