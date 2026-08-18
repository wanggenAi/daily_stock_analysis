from __future__ import annotations

import unittest
from unittest.mock import patch

from src.strategies.genge_opportunity_discovery.all_a_progress_runner import (
    _ProgressIterable,
    _eta_text,
)


class AllAProgressRunnerTest(unittest.TestCase):
    def test_eta_format(self):
        self.assertEqual(_eta_text(3661), "01:01:01")
        self.assertEqual(_eta_text(None), "NA")

    def test_progress_iterable_preserves_rows_and_logs(self):
        rows = [{"code": "000001"}, {"code": "000002"}]
        with patch("builtins.print") as mocked:
            result = list(_ProgressIterable(rows, "QUANT"))
        self.assertEqual(result, rows)
        text = "\n".join(" ".join(str(x) for x in call.args) for call in mocked.call_args_list)
        self.assertIn("[ALL-A][QUANT]", text)
        self.assertIn("2/2", text)
        self.assertIn("current=000002", text)


if __name__ == "__main__":
    unittest.main()
