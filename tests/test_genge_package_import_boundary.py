from __future__ import annotations

import subprocess
import sys


def test_actions_provenance_import_does_not_eager_load_discovery_pipeline() -> None:
    code = """
import sys
import src.strategies.genge_opportunity_discovery.actions_provenance  # noqa: F401
assert 'src.strategies.genge_opportunity_discovery.pipeline' not in sys.modules
"""
    subprocess.run([sys.executable, "-c", code], check=True)
