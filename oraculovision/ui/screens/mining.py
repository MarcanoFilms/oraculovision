"""Full-screen DATUM + Ocean mining panel."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Label

from oraculovision.config import AppConfig
from oraculovision.ui.screens.base import BaseScreen
from oraculovision.widgets.datum_mining import DatumMining


class MiningScreen(BaseScreen):
    """DATUM gateway and Ocean account stats."""

    screen_id = "mining"

    DEFAULT_CSS = """
    MiningScreen .mining-title {
        text-style: bold;
        padding: 0 1 1 1;
    }
    MiningScreen DatumMining {
        height: auto;
        margin: 0 1;
    }
    """

    def __init__(self, config: AppConfig, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        yield Label("DATUM MINING", classes="mining-title")
        with VerticalScroll():
            yield DatumMining(id="datum-full", config=self.config, show_treemap=True)

    def on_mount(self) -> None:
        self.refresh_screen()

    def refresh_screen(self, *, force: bool = False) -> None:
        self.query_one("#datum-full", DatumMining).refresh_data()

    def set_ocean_address(self, address: str) -> None:
        widget = self.query_one("#datum-full", DatumMining)
        widget.set_ocean_address(address)
        widget.refresh_data()
