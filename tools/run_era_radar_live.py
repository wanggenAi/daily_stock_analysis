#!/usr/bin/env python3
"""Run the validated live Era Radar collector set and persist research-only truth."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.era_radar.live_miit import MiitPolicyCollector, MiitStatisticsCollector  # noqa: E402
from src.era_radar.live_nbs_investment import NbsFixedAssetInvestmentCollector  # noqa: E402
from src.era_radar.live_pbc import PbcFinancialStatisticsCollector  # noqa: E402
from src.era_radar.live_production import run_live_production  # noqa: E402
from src.era_radar.live_world_bank import WorldBankChinaStructuralCollector  # noqa: E402


def _persist_validation_heartbeat(output_dir: str | Path, result: dict) -> None:
    """Record successful source validation without mutating immutable Radar truth.

    A semantic NO_CHANGE still proves that all configured live collectors were
    successfully revalidated. The realtime data package uses this explicit
    heartbeat for wall-clock freshness; failed/partial collections never write it.
    """
    status = str(result.get("status") or "")
    if status.startswith("NO_PUBLISH"):
        return
    refreshed_at = str(result.get("research_as_of") or "").strip()
    if not refreshed_at:
        return
    health = result.get("health") or []
    if any(str(row.get("status") or "") != "SUCCESS" for row in health if isinstance(row, dict)):
        return

    target = Path(output_dir) / "validation" / "latest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract": "ERA_RADAR_SOURCE_VALIDATION_V1",
        "refreshed_at": refreshed_at,
        "validation_status": "SUCCESS",
        "semantic_state": status,
        "successful_collectors": sum(
            str(row.get("status") or "") == "SUCCESS" for row in health if isinstance(row, dict)
        ),
        "failed_collectors": sum(
            str(row.get("status") or "") == "FAILED" for row in health if isinstance(row, dict)
        ),
        "evidence_fingerprint": result.get("evidence_fingerprint"),
        "formal_trading_authority": False,
        "no_auto_trade": True,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Era & Capital Trend Radar live production")
    parser.add_argument("--output-dir", default="data/era_radar")
    args = parser.parse_args()

    result = run_live_production(
        [
            WorldBankChinaStructuralCollector(),
            MiitPolicyCollector(),
            MiitStatisticsCollector(),
            NbsFixedAssetInvestmentCollector(),
            PbcFinancialStatisticsCollector(),
        ],
        output_dir=args.output_dir,
    )
    _persist_validation_heartbeat(args.output_dir, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result["status"].startswith("NO_PUBLISH"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
