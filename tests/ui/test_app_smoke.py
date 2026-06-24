"""Headless smoke tests for multi-screen navigation."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from oraculovision.config import AppConfig, UIConfig
from oraculovision.node.client import BitcoinCLIError
from oraculovision.ui.app import SovereignApp


def test_sovereign_app_mounts_all_screens() -> None:
    cfg = AppConfig()
    cfg.ui = UIConfig(splash=False)  # avoid ModalScreen blocking key navigation
    app = SovereignApp(config=cfg)

    # Patch node calls so worker threads return instantly (no real Bitcoin node needed)
    def _fake_call(self, method, *params, **kwargs):
        raise BitcoinCLIError("node unavailable (test)")

    async def _exercise() -> None:
        with patch("oraculovision.node.client.NodeClient.call", _fake_call):
            async with app.run_test(size=(120, 40)) as pilot:
                for key in "12345678":
                    await pilot.press(key)
                await pilot.pause()
                switcher = app.query_one("#screen-switcher")
                assert switcher.current in {
                    "dashboard",
                    "policies",
                    "mempool_glass",
                    "block_explorer",
                    "tx_inspector",
                    "spam_health",
                    "mining",
                    "node_control",
                }

    asyncio.run(_exercise())