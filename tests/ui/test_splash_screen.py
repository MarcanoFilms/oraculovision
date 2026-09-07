"""Tests for SplashScreen dismiss behaviour.

Regression guard for: ScreenError: Can't await screen.dismiss() from the
screen's message handler (Textual 0.82 — dismiss() returns AwaitComplete;
passing it to invoke() triggered pre_await while active_message_pump == splash).
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from oraculovision.config import AppConfig, UIConfig
from oraculovision.node.client import BitcoinCLIError
from oraculovision.ui.app import SovereignApp
from oraculovision.ui.screens.splash import SplashScreen


def _make_app(*, splash: bool = True) -> SovereignApp:
    cfg = AppConfig()
    cfg.ui = UIConfig(splash=splash)
    return SovereignApp(config=cfg)


def _patch_node():
    def _fail(self, method, *a, **kw):
        raise BitcoinCLIError("no node (test)")

    return patch("oraculovision.node.client.NodeClient.call", _fail)


def test_splash_keypress_dismiss_no_screen_error() -> None:
    """Any keypress must dismiss the splash without raising ScreenError."""
    app = _make_app(splash=True)

    async def _run() -> None:
        with _patch_node():
            async with app.run_test(size=(120, 40)) as pilot:
                # Splash should be the active screen (top of stack)
                assert any(isinstance(s, SplashScreen) for s in app.screen_stack)
                # Press any key — must NOT raise ScreenError
                await pilot.press("space")
                await pilot.pause()
                # Splash should be gone
                assert not any(isinstance(s, SplashScreen) for s in app.screen_stack)

    asyncio.run(_run())


def test_splash_escape_dismiss_no_screen_error() -> None:
    """Escape binding must dismiss splash without raising ScreenError."""
    app = _make_app(splash=True)

    async def _run() -> None:
        with _patch_node():
            async with app.run_test(size=(120, 40)) as pilot:
                assert any(isinstance(s, SplashScreen) for s in app.screen_stack)
                await pilot.press("escape")
                await pilot.pause()
                assert not any(isinstance(s, SplashScreen) for s in app.screen_stack)

    asyncio.run(_run())


def test_splash_auto_dismiss_fires() -> None:
    """SplashScreen timer auto-dismiss must complete without error."""
    app = _make_app(splash=True)
    # Shorten the delay so the test doesn't take 3 s
    SplashScreen.AUTO_DISMISS_SECONDS = 0.05

    async def _run() -> None:
        with _patch_node():
            async with app.run_test(size=(120, 40)) as pilot:
                assert any(isinstance(s, SplashScreen) for s in app.screen_stack)
                # Wait long enough for the timer + fade-out timer
                await pilot.pause(delay=0.6)
                assert not any(isinstance(s, SplashScreen) for s in app.screen_stack)

    try:
        asyncio.run(_run())
    finally:
        SplashScreen.AUTO_DISMISS_SECONDS = 2.5  # restore
