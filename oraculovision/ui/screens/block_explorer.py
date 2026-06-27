"""Block Explorer — search and inspect blocks with spam analysis."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Input, Label, Static

from oraculovision.analysis.bip110 import BlockAnalysis
from oraculovision.config import AppConfig
from oraculovision.node.client import BitcoinCLIError
from oraculovision.screens.block_detail_modal import BlockDetailModal
from oraculovision.services.block_service import BlockQueryError, BlockService
from oraculovision.ui.screens.base import BaseScreen
from oraculovision.utils.markup import format_pool_badge, safe_markup_text

_STATUS_STYLE = {
    "CLEAN": "green",
    "SUSPICIOUS": "yellow",
    "VIOLATION": "red bold",
}

RECENT_BLOCK_COUNT = 25


def _flagged_count(block: BlockAnalysis) -> int:
    return sum(
        1
        for t in block.transactions
        if t.has_bip110_violation or t.is_spam_signal
    )


def _summary_line(block: BlockAnalysis) -> str:
    signal = "YES" if block.bip110_signaling else "no"
    style = _STATUS_STYLE.get(block.status, "")
    status = f"[{style}]{block.status}[/]" if style else block.status
    flagged = _flagged_count(block)
    flagged_note = ""
    if flagged:
        flagged_note = (
            f"  ·  [yellow]{flagged} flagged tx[/] "
            f"(Enter expand · i inspect)"
        )
    miner = safe_markup_text(block.miner_tag)
    return (
        f"#{block.height}  {block.hash[:20]}…  "
        f"Miner: {miner}  "
        f"Spam: {block.spam_score}/100  {status}  "
        f"BIP-110 bit4: {signal}  "
        f"Violations: {block.violation_count}  "
        f"Witness: {block.witness_pct:.1f}%"
        f"{flagged_note}"
    )


class BlockExplorerScreen(BaseScreen):
    """Search blocks by height/hash and inspect spam compliance."""

    screen_id = "block_explorer"

    BINDINGS = [
        Binding("slash", "focus_search", "Search", show=True),
        Binding("enter", "open_detail", "Detail", show=True),
    ]

    DEFAULT_CSS = """
    BlockExplorerScreen {
        layout: vertical;
    }
    BlockExplorerScreen #explorer-header {
        height: auto;
        text-style: bold;
        padding: 0 1;
    }
    BlockExplorerScreen #explorer-search-row {
        height: auto;
        padding: 0 1 1 1;
    }
    BlockExplorerScreen #block-search {
        width: 1fr;
    }
    BlockExplorerScreen #explorer-status {
        height: auto;
        padding: 0 1;
    }
    BlockExplorerScreen #explorer-summary {
        height: auto;
        padding: 1 1;
        margin: 0 1;
    }
    BlockExplorerScreen #explorer-hint {
        height: auto;
        padding: 0 1;
    }
    BlockExplorerScreen #explorer-body {
        height: 1fr;
        padding: 0 1;
    }
    BlockExplorerScreen #explorer-table {
        height: 1fr;
    }
    BlockExplorerScreen .search-label {
        width: auto;
        padding-right: 1;
        content-align: center middle;
    }
    """

    def __init__(
        self,
        block_service: BlockService,
        config: AppConfig,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.block_service = block_service
        self.config = config
        self._blocks: list[BlockAnalysis] = []
        self._blocks_by_height: dict[str, BlockAnalysis] = {}
        self._selected: BlockAnalysis | None = None
        self._tip_height: int | None = None

    def export_context(self) -> BlockAnalysis | None:
        return self._selected

    def compose(self) -> ComposeResult:
        yield Label("BLOCK EXPLORER", id="explorer-header")
        with Horizontal(id="explorer-search-row"):
            yield Label("Search:", classes="search-label")
            yield Input(
                placeholder="height or 64-char hash",
                id="block-search",
            )
        yield Static("Loading chain tip…", id="explorer-status")
        yield Static("", id="explorer-summary")
        yield Label(
            "/ search  ·  Enter block detail  ·  ↑↓ navigate  ·  "
            "in detail: i inspect flagged tx",
            id="explorer-hint",
        )
        yield DataTable(id="explorer-table", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one("#explorer-table", DataTable)
        table.add_columns(
            "Height", "Hash", "Miner", "Spam", "Status", "Viol.", "Wit%",
        )
        self.query_one("#explorer-status", Static).update(
            "Press [bold]4[/] or select from sidebar · [bold]/[/] to search"
        )

    def refresh_screen(self, *, force: bool = False) -> None:
        if force:
            self._tip_height = None
        self.query_one("#explorer-status", Static).update(
            "[dim]Loading blocks from your node…[/]"
        )
        self._load_recent()

    def action_focus_search(self) -> None:
        self.query_one("#block-search", Input).focus()

    def action_open_detail(self) -> None:
        block = self._selected
        if not block:
            table = self.query_one("#explorer-table", DataTable)
            if table.cursor_row is not None and 0 <= table.cursor_row < len(self._blocks):
                block = self._blocks[table.cursor_row]
        if block:
            self.app.push_screen(BlockDetailModal(block))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "block-search":
            return
        query = event.value.strip()
        if not query:
            self.refresh_screen(force=True)
            return
        self._search_block(query)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "explorer-table":
            return
        if event.row_key is None:
            return
        block = self._blocks_by_height.get(str(event.row_key.value))
        if block:
            self._selected = block
            self.query_one("#explorer-summary", Static).update(_summary_line(block))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "explorer-table":
            return
        block = self._blocks_by_height.get(str(event.row_key.value))
        if block:
            self._selected = block
            self.app.push_screen(BlockDetailModal(block))

    @work(thread=True, exclusive=True)
    def _load_recent(self) -> None:
        try:
            tip = self.block_service.client.get_block_count()
            if self._tip_height == tip and self._blocks:
                return
            self._tip_height = tip
            blocks = self.block_service.fetch_recent(RECENT_BLOCK_COUNT)
            self._blocks = blocks
            self.app.call_from_thread(self._update_table, blocks, tip, None)
        except (BitcoinCLIError, BlockQueryError) as exc:
            self.app.call_from_thread(self._show_error, str(exc))

    @work(thread=True, exclusive=True)
    def _search_block(self, query: str) -> None:
        try:
            block = self.block_service.fetch_query(query)
            tip = self.block_service.client.get_block_count()
            # Show searched block first, then nearby recent blocks.
            recent = self.block_service.fetch_recent(RECENT_BLOCK_COUNT)
            seen = {block.hash}
            merged = [block]
            for b in recent:
                if b.hash not in seen:
                    merged.append(b)
                    seen.add(b.hash)
            self._blocks = merged
            self.app.call_from_thread(
                self._update_table,
                merged,
                tip,
                str(block.height),
            )
        except (BitcoinCLIError, BlockQueryError) as exc:
            self.app.call_from_thread(self._show_error, str(exc))

    def _show_error(self, message: str) -> None:
        self.query_one("#explorer-status", Static).update(f"[red]{message}[/]")
        self.query_one("#explorer-summary", Static).update("")

    def _update_table(
        self,
        blocks: list[BlockAnalysis],
        tip: int,
        highlight_height: str | None,
    ) -> None:
        status = self.query_one("#explorer-status", Static)
        summary = self.query_one("#explorer-summary", Static)
        table = self.query_one("#explorer-table", DataTable)

        status.update(
            f"Chain tip: #{tip:,}  ·  showing {len(blocks)} block(s)  ·  "
            f"verified via your node"
        )

        table.clear()
        self._blocks_by_height.clear()
        self._selected = blocks[0] if blocks else None

        for block in blocks:
            self._blocks_by_height[str(block.height)] = block
            style = _STATUS_STYLE.get(block.status, "")
            status_cell = f"[{style}]{block.status}[/]" if style else block.status
            spam_cell = (
                f"[{style}]{block.spam_score}[/]"
                if block.spam_score >= self.config.alerts.spam_block_score
                else str(block.spam_score)
            )
            marker = "▶ " if highlight_height == str(block.height) else ""
            table.add_row(
                f"{marker}{block.height}",
                f"{block.hash[:12]}…",
                format_pool_badge(block.miner_tag),
                spam_cell,
                status_cell,
                str(block.violation_count),
                f"{block.witness_pct:.1f}",
                key=str(block.height),
            )

        if self._selected:
            summary.update(_summary_line(self._selected))
            target = highlight_height or str(self._selected.height)
            try:
                row_idx = next(
                    i for i, b in enumerate(blocks) if str(b.height) == target
                )
                table.cursor_coordinate = table.cursor_coordinate._replace(row=row_idx)
            except (StopIteration, AttributeError, TypeError):
                pass
        else:
            summary.update("[dim]No blocks loaded[/]")