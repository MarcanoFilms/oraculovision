"""BIP-110 spam detector widget with block table and tip analysis."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Static

from oraculovision.analysis.bip110 import BlockAnalysis
from oraculovision.config import AppConfig
from oraculovision.data.bitcoin import BitcoinCLI, BitcoinCLIError
from oraculovision.services.block_service import BlockQueryError, BlockService
from oraculovision.screens.block_detail_modal import BlockDetailModal
from oraculovision.utils.markup import safe_markup_text

_STATUS_STYLE = {
    "CLEAN": "green",
    "SUSPICIOUS": "yellow",
    "VIOLATION": "red bold",
}

RECENT_BLOCKS = 15


class Bip110Detector(Static):
    """Analyzes recent blocks for BIP-110 violations and spam patterns."""

    BINDINGS = [
        Binding("enter", "open_block_detail", "Detail", show=True),
    ]

    DEFAULT_CSS = """
    Bip110Detector {
        height: 1fr;
        border: solid #ffd700;
        padding: 1 1;
    }
    Bip110Detector:focus-within {
        border: solid #ffd700;
    }
    Bip110Detector #tip-panel {
        height: auto;
        padding-bottom: 1;
        border-bottom: solid #333;
    }
    Bip110Detector .tip-title { color: #ffd700; text-style: bold; }
    Bip110Detector .nav-hint { color: #666; }
    Bip110Detector DataTable { height: 1fr; }
    Bip110Detector.alert-spam-block { border: solid #ff6b6b; }
    """

    def __init__(
        self,
        cli: BitcoinCLI | None = None,
        config: AppConfig | None = None,
        block_service: BlockService | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.cli = cli or BitcoinCLI()
        self.config = config or AppConfig()
        self.block_service = block_service
        self.border_title = "BIP-110 DETECTOR"
        self._cache: dict[str, BlockAnalysis] = {}
        self._blocks: list[BlockAnalysis] = []
        self._blocks_by_height: dict[str, BlockAnalysis] = {}
        self._tip: BlockAnalysis | None = None
        self._last_tip_height: int | None = None
        self.alert_spam_block: bool = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Analyzing chain...", id="tip-panel", classes="tip-title")
            yield Label("↑↓ navigate  ·  Enter detail", classes="nav-hint")
            yield DataTable(id="blocks-table", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one("#blocks-table", DataTable)
        table.add_columns(
            "Height", "Miner", "Spam", "BIP-110", "Viol.", "Wit%",
        )
        table.focus()
        self.refresh_data()

    def refresh_data(self) -> None:
        try:
            tip_height = self.cli.get_block_count()
        except BitcoinCLIError:
            self._fetch_blocks()
            return
        if self._last_tip_height == tip_height and self._blocks:
            return
        self._last_tip_height = tip_height
        self._fetch_blocks()

    def action_open_block_detail(self) -> None:
        table = self.query_one("#blocks-table", DataTable)
        if table.cursor_row is None:
            return
        row = table.get_row_at(table.cursor_row)
        height = str(row[0]) if row else None
        block = self._blocks_by_height.get(height or "")
        if block:
            self.app.push_screen(BlockDetailModal(block))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        height = str(event.row_key.value)
        block = self._blocks_by_height.get(height)
        if block:
            self.app.push_screen(BlockDetailModal(block))

    @work(thread=True, exclusive=True)
    def _fetch_blocks(self) -> None:
        try:
            if self.block_service is not None:
                analyses = self.block_service.fetch_recent(RECENT_BLOCKS)
                for block in analyses:
                    self._cache[block.hash] = block
            else:
                from oraculovision.analysis.bip110 import analyze_block

                tip_height = self.cli.get_block_count()
                analyses = []
                for h in range(tip_height, max(tip_height - RECENT_BLOCKS, -1), -1):
                    block_hash = self.cli.get_block_hash(h)
                    if block_hash in self._cache:
                        analyses.append(self._cache[block_hash])
                        continue
                    block = self.cli.get_block(block_hash, 2)
                    analysis = analyze_block(block)
                    self._cache[block_hash] = analysis
                    analyses.append(analysis)
            self._blocks = analyses
            self._tip = analyses[0] if analyses else None
            self.app.call_from_thread(self._update_ui)
        except (BitcoinCLIError, BlockQueryError) as exc:
            msg = str(exc)
            if exc.hint:
                msg += f" | {exc.hint}"
            self.app.call_from_thread(self._show_error, msg)

    def _show_error(self, msg: str) -> None:
        self.query_one("#tip-panel", Label).update(f"[red]Error: {msg}[/]")
        self.query_one("#blocks-table", DataTable).clear()

    def _update_ui(self) -> None:
        tip_label = self.query_one("#tip-panel", Label)
        table = self.query_one("#blocks-table", DataTable)
        table.clear()
        self._blocks_by_height.clear()

        if not self._tip:
            tip_label.update("No block data available.")
            return

        t = self._tip
        signal = "YES" if t.bip110_signaling else "no"
        breakdown = (
            f"inscr:{t.inscription_count} runes:{t.runes_count} "
            f"brc20:{t.brc20_count} op_ret:{t.op_return_count} "
            f"viol_wt:{t.violation_weight:,}"
        )
        miner = safe_markup_text(t.miner_tag)
        tip_label.update(
            f"TIP #{t.height}  {t.hash[:16]}…  "
            f"Miner: {miner}  "
            f"BIP110 bit4: {signal}  "
            f"Spam: {t.spam_score}/100 [{t.status}]  "
            f"{breakdown}"
        )

        threshold = self.config.alerts.spam_block_score
        prev = self.alert_spam_block
        self.alert_spam_block = t.spam_score >= threshold or t.status == "VIOLATION"
        self.remove_class("alert-spam-block")
        if self.alert_spam_block:
            self.add_class("alert-spam-block")
        if self.alert_spam_block and not prev:
            self.animate("opacity", 0.5, duration=0.15)
            self.set_timer(0.15, lambda: self.animate("opacity", 1.0, duration=0.3))

        for block in self._blocks:
            self._blocks_by_height[str(block.height)] = block
            miner = block.miner_tag[:20]
            if block.spam_score > 60:
                miner = f"⚠ {miner}"
            style = _STATUS_STYLE.get(block.status, "")
            status_cell = f"[{style}]{block.status}[/]" if style else block.status
            spam_cell = (
                f"[{style}]{block.spam_score}[/]"
                if block.spam_score >= 45
                else str(block.spam_score)
            )
            table.add_row(
                str(block.height), miner, spam_cell, status_cell,
                str(block.violation_count), f"{block.witness_pct:.1f}",
                key=str(block.height),
            )