"""GenGe V2 full-A scan entrypoint.

Reuse the mature all-A scanner and its progress instrumentation, but deliberately
do not install the legacy V3.1 formal BUY guard. V2 consumes scan facts, price
plans and research rows, then makes BUY/NEAR_BUY/WATCH decisions in stock_v2.
"""
from __future__ import annotations

from src.strategies.genge_opportunity_discovery import all_a_full_scan as scan
from src.strategies.genge_opportunity_discovery.all_a_progress_runner import install_progress_hooks


def main(argv: list[str] | None = None) -> int:
    install_progress_hooks()
    print("[V2][ALL-A] progress-instrumentation=enabled", flush=True)
    print("[V2][ALL-A] legacy-formal-buy-guard=disabled", flush=True)
    return scan.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
