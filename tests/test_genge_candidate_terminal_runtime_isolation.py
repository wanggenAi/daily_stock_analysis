from __future__ import annotations

import subprocess
import sys


def test_candidate_terminal_import_does_not_require_yaml() -> None:
    code = r'''
import builtins
original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == "yaml" or name.startswith("yaml."):
        raise ModuleNotFoundError("yaml intentionally unavailable in terminal runtime isolation test")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
from src.strategies.genge_opportunity_discovery.candidate_terminal_decision import FORMAL_BUY_MAX_PRICE_TO_NEUTRAL
assert FORMAL_BUY_MAX_PRICE_TO_NEUTRAL == 0.80
'''
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
