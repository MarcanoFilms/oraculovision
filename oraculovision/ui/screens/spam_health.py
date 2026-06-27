"""Spam & Chain Health — historical trends and worst blocks."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Label, Static

from oraculovision.analysis.bip110 import BlockAnalysis
from oraculovision.analysis.chain_health import ChainHealthReport, render_summary
from oraculovision.config import AppConfig
from oraculovision.screens.block_detail_modal import BlockDetailModal
from oraculovision.services.health_service import HealthService
from oraculovision.ui.screens.base import BaseScreen

try:
    from textual_plotext import PlotextPlot
except ImportError:
    PlotextPlot = None  # type: ignore[misc, assignment]

_STATUS_STYLE = {
    "CLEAN": "green",
    "SUSPICIOUS": "yellow",
    "VIOLATION": "red bold",
}


class SpamHealthScreen(BaseScreen):
    """Historical spam trends, health score, and worst blocks."""

    screen_id = "spam_health"

    BINDINGS = [
        Binding("enter", "open_detail", "Detail", show=True),
    ]

    DEFAULT_CSS = """
    SpamHealthScreen {
        layout: vertical;
    }
    SpamHealthScreen #health-header {
        height: auto;
        text-style: bold;
        padding: 0 1;
    }
    SpamHealthScreen #health-summary {
        height: auto;
        padding: 1 2;
        margin: 0 1 1 1;
    }
    SpamHealthScreen #health-body {
        height: 1fr;
        padding: 0 1 1 1;
    }
    SpamHealthScreen #health-chart-panel {
        width: 45%;
        height: 100%;
        padding: 0 1;
    }
    SpamHealthScreen #health-worst-panel {
        width: 55%;
        height: 100%;
        padding-left: 1;
    }
    SpamHealthScreen #spam-chart {
        height: 1fr;
    }
    SpamHealthScreen #worst-table {
        height: 1fr;
    }
    SpamHealthScreen .panel-title {
        text-style: bold;
        padding: 1 0 0 0;
    }
    SpamHealthScreen #health-hint {
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        health_service: HealthService,
        config: AppConfig,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.health_service = health_service
        self.config = config
        self._report: ChainHealthReport | None = None
        self._blocks_by_height: dict[str, BlockAnalysis] = {}

    def export_context(self) -> ChainHealthReport | None:
        return self._report

    def compose(self) -> ComposeResult:
        yield Label("SPAM & CHAIN HEALTH", id="health-header")
        yield Static(
            "[dim]Open this screen to scan recent blocks from your node[/]",
            id="health-summary",
        )
        yield Label(
            "Enter open worst-block detail  ·  r refresh scan",
            id="health-hint",
        )
        with Horizontal(id="health-body"):
            with Vertical(id="health-chart-panel"):
                yield Label("SPAM SCORE TREND", classes="panel-title")
                if PlotextPlot is None:
                    yield Static(
                        "[yellow]Install textual-plotext for charts[/]",
                        id="chart-fallback",
                    )
                else:
                    yield PlotextPlot(id="spam-chart")
            with Vertical(id="health-worst-panel"):
                yield Label("WORST BLOCKS", classes="panel-title")
                yield DataTable(id="worst-table", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one("#worst-table", DataTable)
        table.add_columns(
            "Height", "Miner", "Spam", "Status", "Viol.", "Inscr.",
        )
        if PlotextPlot is not None:
            self._setup_chart()

    def _setup_chart(self) -> None:
        chart = self.query_one("#spam-chart", PlotextPlot)
        chart.plt.title("Spam score (recent blocks)")
        chart.plt.xlabel("block index (older → newer)")
        chart.plt.ylabel("score")
        chart.plt.ylim(0, 100)

    def refresh_screen(self, *, force: bool = False) -> None:
        self.query_one("#health-summary", Static).update(
            "[dim]Scanning recent blocks from your node…[/]"
        )
        self._scan(force=force)

    def action_open_detail(self) -> None:
        table = self.query_one("#worst-table", DataTable)
        if table.cursor_row is None:
            return
        if table.cursor_row >= len(self._report.worst_blocks if self._report else []):
            return
        block = self._report.worst_blocks[table.cursor_row] if self._report else None
        if block:
            self.app.push_screen(BlockDetailModal(block))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "worst-table" or not self._report:
            return
        block = self._blocks_by_height.get(str(event.row_key.value))
        if block:
            self.app.push_screen(BlockDetailModal(block))

    @work(thread=True, exclusive=True)
    def _scan(self, force: bool = False) -> None:
        report = self.health_service.scan(force=force)
        self.app.call_from_thread(self._update_ui, report)

    def _update_ui(self, report: ChainHealthReport) -> None:
        self._report = report
        self.remove_class("health-poor", "health-degraded")

        summary = self.query_one("#health-summary", Static)
        summary.update(render_summary(report))

        if report.error:
            return

        if report.health_score < 40:
            self.add_class("health-poor")
        elif report.health_score < 60:
            self.add_class("health-degraded")

        self._update_chart(report)
        self._update_worst_table(report)

    def _update_chart(self, report: ChainHealthReport) -> None:
        if PlotextPlot is None or not report.timeline:
            return
        chart = self.query_one("#spam-chart", PlotextPlot)
        scores = [score for _, score in report.timeline]
        chart.plt.clear_data()
        chart.plt.plot(scores, marker="braille")
        # Threshold line at config alert level
        threshold = self.config.alerts.spam_block_score
        chart.plt.hline(threshold)
        chart.plt.title(
            f"Spam score — {len(scores)} blocks "
            f"(threshold {threshold})"
        )
        chart.refresh()

    def _update_worst_table(self, report: ChainHealthReport) -> None:
        table = self.query_one("#worst-table", DataTable)
        table.clear()
        self._blocks_by_height.clear()

        for block in report.worst_blocks:
            self._blocks_by_height[str(block.height)] = block
            style = _STATUS_STYLE.get(block.status, "")
            status_cell = f"[{style}]{block.status}[/]" if style else block.status
            spam_cell = (
                f"[{style}]{block.spam_score}[/]"
                if block.spam_score >= self.config.alerts.spam_block_score
                else str(block.spam_score)
            )
            table.add_row(
                str(block.height),
                block.miner_tag[:18],
                spam_cell,
                status_cell,
                str(block.violation_count),
                str(block.inscription_count),
                key=str(block.height),
            )