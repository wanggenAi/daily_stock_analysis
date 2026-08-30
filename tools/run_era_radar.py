#!/usr/bin/env python3
"""Run a deterministic Era Radar snapshot from normalized collector observations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.era_radar.collectors import JsonObservationCollector, collect_all  # noqa: E402
from src.era_radar.discovery import discover_hypotheses  # noqa: E402
from src.era_radar.persistence import persist_snapshot  # noqa: E402
from src.era_radar.pipeline import build_snapshot  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Era & Capital Trend Radar V1")
    parser.add_argument("--observations", required=True, help="normalized collector JSON")
    parser.add_argument("--research-as-of", required=True, help="PIT cutoff, ISO-8601 timezone-aware")
    parser.add_argument("--output-dir", default="data/era_radar")
    args = parser.parse_args()

    records = collect_all([JsonObservationCollector(args.observations)], args.research_as_of)
    hypotheses = discover_hypotheses(records)
    snapshot = build_snapshot(records, args.research_as_of)
    result = persist_snapshot(snapshot, args.output_dir, records)
    payload = {
        **result,
        "formal_trading_authority": False,
        "no_auto_trade": True,
        "evidence_count": snapshot.evidence_count,
        "hypotheses": [
            {
                "trend_id": item.trend_id,
                "evidence_families": item.evidence_families,
                "source_count": item.source_count,
                "research_priority": item.research_priority,
            }
            for item in hypotheses
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
