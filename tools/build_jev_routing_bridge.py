"""Build an advisory Jev research-routing bridge from a shadow artifact."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.strategies.genge_opportunity_discovery.jev_routing_bridge import (
    build_routing_bridge,
    render_routing_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--shadow-json",
        type=Path,
        default=Path(".artifacts/jev-shadow/jev_shadow.json"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path(".artifacts/jev-shadow/jev_routing.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path(".artifacts/jev-shadow/jev_routing.md"),
    )
    parser.add_argument("--require-success", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.shadow_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Jev shadow artifact must be a JSON object")

    routing = build_routing_bridge(payload)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(routing, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_md.write_text(render_routing_markdown(routing), encoding="utf-8")
    print(json.dumps(routing.get("summary") or {}, ensure_ascii=False, sort_keys=True))

    if args.require_success and routing.get("execution_status") != "SUCCESS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
