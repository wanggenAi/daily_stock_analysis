# -*- coding: utf-8 -*-
"""Regression tests for stock-index source authority and remote-cache safety."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.data import stock_index_loader
from src.services.stock_index_remote_service import (
    RemoteStockIndexSettings,
    refresh_remote_stock_index_cache,
    settings_from_config,
    validate_stock_index_payload,
)


def _index_item(code: str, name: str) -> list:
    return [code, code, name, "", "", [], "CN", "stock", True, 0]


class TestStockIndexSourceAuthority(unittest.TestCase):
    def tearDown(self) -> None:
        stock_index_loader.clear_stock_index_cache()

    def test_newer_remote_cache_cannot_override_bundled_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bundled = root / "bundled.json"
            remote = root / "remote.json"

            bundled.write_text(
                json.dumps([_index_item("300223", "北京君正")], ensure_ascii=False),
                encoding="utf-8",
            )
            remote_items = [_index_item(f"30{i:04d}", f"测试{i}") for i in range(100)]
            remote_items[0] = _index_item("300223", "君正股份")
            remote.write_text(json.dumps(remote_items, ensure_ascii=False), encoding="utf-8")

            os.utime(bundled, (1, 1))
            os.utime(remote, (2, 2))

            with patch.object(
                stock_index_loader,
                "get_stock_index_candidate_paths",
                return_value=(bundled, remote),
            ), patch.object(
                stock_index_loader,
                "get_remote_stock_index_cache_path",
                return_value=remote,
            ):
                stock_index_loader.clear_stock_index_cache()
                self.assertEqual(stock_index_loader.get_index_stock_name("300223"), "北京君正")


class TestRemoteStockIndexSafety(unittest.TestCase):
    def test_default_settings_do_not_attempt_network_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings = RemoteStockIndexSettings(cache_path=Path(tmp_dir) / "cache.json")
            with patch("src.services.stock_index_remote_service.requests.get") as request_get:
                result = refresh_remote_stock_index_cache(settings)

            self.assertTrue(result.skipped)
            self.assertFalse(result.refreshed)
            request_get.assert_not_called()

    def test_config_without_explicit_url_disables_remote_refresh(self) -> None:
        config = SimpleNamespace(stock_index_remote_update_enabled=True)
        with patch.dict(os.environ, {"DSA_STOCK_INDEX_URL": ""}, clear=False):
            settings = settings_from_config(config)

        self.assertFalse(settings.enabled)
        self.assertEqual(settings.url, "")

    def test_explicit_config_url_can_enable_remote_refresh(self) -> None:
        config = SimpleNamespace(
            stock_index_remote_update_enabled=True,
            stock_index_remote_url="https://example.invalid/stocks.index.json",
        )
        settings = settings_from_config(config)

        self.assertTrue(settings.enabled)
        self.assertEqual(settings.url, "https://example.invalid/stocks.index.json")

    def test_validator_rejects_conflicting_names_for_same_canonical_code(self) -> None:
        payload = [
            _index_item("300223", "北京君正"),
            _index_item("300223", "君正股份"),
        ]

        with self.assertRaisesRegex(ValueError, "code/name conflict"):
            validate_stock_index_payload(payload, min_items=2)


if __name__ == "__main__":
    unittest.main()
