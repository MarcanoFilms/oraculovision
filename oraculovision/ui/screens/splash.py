"""ASCII-art splash screen — auto-dismisses or on any keypress."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static

_EYE_ART = """\
     ╭──────────────────────────────────────╮
    ╱                                        ╲
   │   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
   │  ░                                  ░  │
   │  ░   ╔══════════════════════════╗   ░  │
   │  ░   ║  ◉   O R A C U L O      ║   ░  │
   │  ░   ║      V I S I O N   ◉    ║   ░  │
   │  ░   ╚══════════════════════════╝   ░  │
   │  ░                                  ░  │
   │   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
    ╲                                        ╱
     ╰──────────────────────────────────────╯\
"""


class SplashScreen(ModalScreen):
    """Full-screen oracle splash, dismisses after delay or any keypress."""

    AUTO_DISMISS_SECONDS = 2.5

    BINDINGS = [
        Binding("escape", "dismiss", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="splash-box"):
            yield Static(_EYE_ART, id="splash-art")
            yield Label(
                "[bold rgb(255,102,0)]OraculoVision[/]  [dim]v2.3[/]",
                id="splash-title",
            )
            yield Label(
                "[bold white]Sovereign Bitcoin Dashboard[/]",
                id="splash-tagline",
            )
            yield Label(
                "[dim cyan]BIP-110 · DATUM · Knots · Don't Trust, Verify[/]",
                id="splash-hint",
            )
            yield Label(
                "[dim]press any key to continue[/]",
                id="splash-key-hint",
                classes="splash-hint",
            )

    def on_mount(self) -> None:
        self.set_timer(self.AUTO_DISMISS_SECONDS, self._auto_dismiss)
        self.styles.animate("opacity", 1.0, duration=0.6)

    def _auto_dismiss(self) -> None:
        self.styles.animate("opacity", 0.0, duration=0.4)
        self.set_timer(0.4, self._safe_dismiss)

    def _safe_dismiss(self) -> None:
        # dismiss() returns an AwaitComplete. Discarding it here (returning None)
        # prevents Textual's invoke() from awaiting it while this screen is still
        # the active message pump, which would trigger ScreenError.
        self.dismiss()

    async def on_key(self, event) -> None:
        # action_dismiss (built into Screen) calls self.dismiss() without awaiting
        # the AwaitComplete, which is the only safe way from a message handler.
        await self.action_dismiss()
