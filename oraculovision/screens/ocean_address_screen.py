"""Modal screen for entering an Ocean payout address."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, Static

from oraculovision.data.ocean import format_ocean_address, normalize_address


class OceanAddressScreen(ModalScreen[str | None]):
    """Prompt for a Bitcoin payout address registered on Ocean."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
    ]

    DEFAULT_CSS = """
    OceanAddressScreen {
        align: center middle;
    }
    #ocean-dialog {
        width: 78;
        height: auto;
        max-height: 14;
        padding: 1 2;
    }
    #ocean-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #ocean-hint {
        margin-bottom: 1;
    }
    #ocean-address-input {
        margin-bottom: 1;
    }
    #ocean-error {
        height: 1;
    }
    #ocean-status {
        height: 1;
    }
    """

    def __init__(self, current_address: str = "") -> None:
        super().__init__()
        self.current_address = current_address

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="ocean-dialog"):
            yield Static("OCEAN ACCOUNT", id="ocean-title")
            yield Static(
                "Enter your Bitcoin payout address (bc1…, 1…, or 3…). "
                "Leave empty and press Enter to clear.",
                id="ocean-hint",
            )
            yield Input(
                placeholder="bc1…",
                value=self.current_address,
                id="ocean-address-input",
            )
            yield Label("", id="ocean-error")
            yield Label("Enter = apply · Esc = cancel", id="ocean-status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#ocean-address-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        if not raw:
            self.dismiss("")
            return

        normalized = normalize_address(raw)
        if not normalized:
            self.query_one("#ocean-error", Label).update("Invalid Bitcoin address")
            self.query_one("#ocean-status", Label).update("")
            return

        self.query_one("#ocean-error", Label).update("")
        self.query_one("#ocean-status", Label).update(
            f"✓ {format_ocean_address(normalized)}"
        )
        self.dismiss(normalized)

    def action_dismiss(self) -> None:
        self.dismiss(None)