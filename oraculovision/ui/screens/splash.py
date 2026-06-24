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
        Binding("escape", "dismiss_splash", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="splash-box"):
            yield Static(_EYE_ART, id="splash-art")
            yield Label("OraculoVision  v2.3", id="splash-title")
            yield Label("Sovereign Bitcoin Dashboard", id="splash-tagline")
            yield Label(
                "[dim]Don't Trust, Verify.[/]",
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
        self.set_timer(0.4, self.dismiss)

    def action_dismiss_splash(self) -> None:
        self.call_after_refresh(self.dismiss)

    def on_key(self, event) -> None:
        self.call_after_refresh(self.dismiss)
