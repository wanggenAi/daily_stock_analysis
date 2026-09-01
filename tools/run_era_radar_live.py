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
from src.era_radar.live_production import run_live_production  # noqa: E402
from src.era_radar.live_world_bank import WorldBankChinaStructuralCollector  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Era & Capital Trend Radar live production")
    parser.add_argument("--output-dir", default="data/era_radar")
    args = parser.parse_args()

    result = run_live_production(
        [WorldBankChinaStructuralCollector(), MiitPolicyCollector(), MiitStatisticsCollector()],
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result["status"].startswith("NO_PUBLISH"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
