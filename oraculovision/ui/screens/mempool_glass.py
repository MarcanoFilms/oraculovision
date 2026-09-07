"""Full-screen Mempool Glass — block template analysis."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Static

from oraculovision.analysis.mempool_compose import categorize_transaction
from oraculovision.config import AppConfig
from oraculovision.node.client import BitcoinCLIError, NodeClient
from oraculovision.services.template_service import TemplateService
from oraculovision.ui.screens.base import BaseScreen
from oraculovision.utils.clipboard import copy_to_clipboard


def _bar(pct: float, width: int = 40, char: str = "█") -> str:
    filled = int(round(pct / 100 * width))
    filled = max(0, min(width, filled))
    return char * filled + "░" * (width - filled)


_CATEGORY_STYLE = {
    "economic": "green",
    "consolidation": "cyan",
    "coinjoin": "blue",
    "spam": "red bold",
}

_FILTER_ORDER = ("all", "economic", "consolidation", "coinjoin", "spam")

_FILTER_LABELS = {
    "all": "All categories",
    "economic": "Economic / clean",
    "consolidation": "Consolidations",
    "coinjoin": "Coinjoins",
    "spam": "Spam / inscriptions",
}


class MempoolGlassScreen(BaseScreen):
    """Enhanced Mempool Glass with composition bars and tx table."""

    screen_id = "mempool_glass"

    BINDINGS = [
        Binding("c", "copy_txid", "Copy txid", show=True),
        Binding("i", "inspect_txid", "Inspect", show=True),
        Binding("enter", "inspect_txid", "Inspect", show=False),
        Binding("f", "cycle_filter", "Filter", show=True),
    ]

    DEFAULT_CSS = """
    MempoolGlassScreen #glass-summary {
        height: auto;
        padding: 1 2;
        margin-bottom: 1;
    }
    MempoolGlassScreen #glass-table {
        height: 1fr;
    }
    MempoolGlassScreen .glass-title {
        text-style: bold;
    }
    MempoolGlassScreen #glass-hint {
        height: auto;
        padding: 0 1;
    }
    MempoolGlassScreen #glass-status {
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        cli: NodeClient,
        config: AppConfig,
        template_service: TemplateService,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.cli = cli
        self.config = config
        self.template_service = template_service
        self._spam_pct: float = 0.0
        self._all_rows: list[tuple[str, str, str, int, int]] = []
        self._category_filter: str = "all"

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("MEMPOOL GLASS", classes="glass-title")
            yield Static("Analyzing block template...", id="glass-summary")
            yield Static(
                "↑↓ select  ·  [bold]c[/] copy  ·  [bold]i[/]/Enter inspect  ·  "
                "[bold]f[/] cycle category filter",
                id="glass-hint",
            )
            yield Static("", id="glass-status")
            yield DataTable(id="glass-table", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one("#glass-table", DataTable)
        table.add_columns("Category", "Txid", "Weight", "vsize")
        self.refresh_screen()

    def refresh_screen(self, *, force: bool = False) -> None:
        self._fetch_data(force=force)

    @work(thread=True, exclusive=True)
    def _fetch_data(self, force: bool = False) -> None:
        try:
            mempool = self.cli.get_mempool_info()
            snapshot = self.template_service.fetch(force=force)
            comp = snapshot.composition

            if comp.error:
                self.app.call_from_thread(self._show_error, comp.error)
                return

            mempool_tx = mempool.get("size", 0)
            mempool_mb = mempool.get("bytes", 0) / 1_000_000
            self._spam_pct = comp.pct(comp.spam_weight)

            summary_lines = [
                (
                    f"[bold #ffd700]Block Template #{comp.template_height}[/]  ·  "
                    f"{comp.analyzed_tx:,} txs  ·  {comp.fill_pct:.1f}% max weight"
                ),
                (
                    f"Mempool: {mempool_tx:,} tx ({mempool_mb:.2f} MB)  ·  "
                    f"template weight {comp.analyzed_weight:,}/{comp.weight_limit:,}"
                ),
                "",
            ]

            categories = [
                ("Economic / Clean", comp.economic_weight, comp.economic_count, "green"),
                ("Consolidations", comp.consolidation_weight, comp.consolidation_count, "cyan"),
                ("Coinjoins", comp.coinjoin_weight, comp.coinjoin_count, "blue"),
                ("Spam / Inscriptions", comp.spam_weight, comp.spam_count, "red bold"),
            ]
            for label, weight, count, style in categories:
                pct = comp.pct(weight)
                summary_lines.append(
                    f"[{style}]{label:20}[/] {pct:5.1f}%  ({count:,} tx)  [{style}]{_bar(pct)}[/]"
                )

            if self._spam_pct > 30:
                summary_lines.append("\n[red bold]⚠ Very dirty template — high BIP-110 impact[/]")
            elif self._spam_pct > 15:
                summary_lines.append("\n[yellow]⚠ Elevated spam in next block[/]")

            rows: list[tuple[str, str, str, int, int]] = []
            tmpl = snapshot.template
            for entry in tmpl.get("transactions", [])[:200]:
                hex_data = entry.get("data", "")
                if not hex_data:
                    continue
                try:
                    tx = self.cli.decode_raw_transaction(hex_data)
                    if entry.get("txid"):
                        tx["txid"] = entry["txid"]
                except Exception:
                    continue
                cat = categorize_transaction(tx)
                txid = tx.get("txid", "?")
                weight = int(entry.get("weight") or tx.get("weight") or 0)
                vsize = int(tx.get("vsize") or weight // 4)
                rows.append((cat, txid, txid[:20] + "…", weight, vsize))

            self.app.call_from_thread(
                self._update_ui,
                "\n".join(summary_lines),
                rows,
                self._spam_pct,
            )
        except BitcoinCLIError as exc:
            msg = str(exc)
            if exc.hint:
                msg += f"\n→ {exc.hint}"
            self.app.call_from_thread(self._show_error, msg)

    def _show_error(self, message: str) -> None:
        self.query_one("#glass-summary", Static).update(f"[red]{message}[/]")
        self.query_one("#glass-table", DataTable).clear()

    def _selected_txid(self) -> str | None:
        table = self.query_one("#glass-table", DataTable)
        coord = table.cursor_coordinate
        if coord is None:
            return None
        cell_key = table.coordinate_to_cell_key(coord)
        return str(cell_key.row_key.value)

    def _show_status(self, message: str, *, error: bool = False) -> None:
        status = self.query_one("#glass-status", Static)
        if error:
            status.update(f"[yellow]{message}[/]")
        else:
            status.update(message)

    def action_copy_txid(self) -> None:
        txid = self._selected_txid()
        if not txid:
            self._show_status("Select a transaction row first", error=True)
            return
        if copy_to_clipboard(txid):
            self._show_status(f"✓ Copied {txid[:20]}… to clipboard")
        else:
            self._show_status("Could not copy (install wl-copy or xclip)", error=True)

    def action_inspect_txid(self) -> None:
        txid = self._selected_txid()
        if not txid:
            self._show_status("Select a transaction row first", error=True)
            return
        if hasattr(self.app, "inspect_transaction"):
            self.app.inspect_transaction(txid)
        else:
            self._show_status("Tx Inspector unavailable", error=True)

    def action_cycle_filter(self) -> None:
        if not self._all_rows:
            self._show_status("No transactions loaded yet", error=True)
            return
        idx = _FILTER_ORDER.index(self._category_filter)
        nxt = _FILTER_ORDER[(idx + 1) % len(_FILTER_ORDER)]
        self._set_filter(nxt)

    def _set_filter(self, category: str) -> None:
        self._category_filter = category
        self._populate_table()

    def _populate_table(self) -> None:
        table = self.query_one("#glass-table", DataTable)
        table.clear()
        shown = 0
        for cat, txid, txid_short, weight, vsize in self._all_rows:
            if self._category_filter != "all" and cat != self._category_filter:
                continue
            style = _CATEGORY_STYLE.get(cat, "")
            table.add_row(
                f"[{style}]{cat}[/]" if style else cat,
                txid_short,
                f"{weight:,}",
                f"{vsize:,}",
                key=txid,
            )
            shown += 1
        label = _FILTER_LABELS.get(self._category_filter, self._category_filter)
        total = len(self._all_rows)
        self._show_status(f"Filter: {label} — showing {shown}/{total} txs")

    def _update_ui(
        self,
        summary: str,
        rows: list[tuple[str, str, str, int, int]],
        spam_pct: float,
    ) -> None:
        summary_widget = self.query_one("#glass-summary", Static)
        summary_widget.update(summary)
        summary_widget.remove_class("alert-spam")
        if spam_pct > 30:
            summary_widget.add_class("alert-spam")

        self._all_rows = rows
        self._populate_table()