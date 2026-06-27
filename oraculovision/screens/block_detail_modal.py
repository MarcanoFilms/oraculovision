"""Block detail modal for BIP-110 detector and block explorer."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Label, Static

from oraculovision.analysis.bip110 import BlockAnalysis, TxAnalysis
from oraculovision.utils.clipboard import copy_to_clipboard
from oraculovision.utils.markup import format_pool_badge, safe_markup_text


def _flagged_transactions(block: BlockAnalysis) -> list[TxAnalysis]:
    bad = [
        t for t in block.transactions
        if t.has_bip110_violation or t.is_spam_signal
    ]
    bad.sort(key=lambda t: t.weight, reverse=True)
    return bad


def _tx_type(tx: TxAnalysis) -> str:
    if tx.has_bip110_violation and tx.is_spam_signal:
        return "viol+spam"
    if tx.has_bip110_violation:
        return "bip-110"
    return "spam"


class BlockDetailModal(ModalScreen[None]):
    """Shows block analysis with selectable flagged transactions."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("c", "copy_hash", "Copy hash"),
        Binding("t", "copy_txid", "Copy txid"),
        Binding("i", "inspect_txid", "Inspect tx"),
    ]

    DEFAULT_CSS = """
    BlockDetailModal {
        align: center middle;
    }
    #block-dialog {
        width: 88;
        height: 88%;
        padding: 1 2;
    }
    #block-meta-scroll {
        height: auto;
        max-height: 14;
    }
    #block-tx-header {
        text-style: bold;
        padding: 1 0 0 0;
    }
    #block-tx-table {
        height: 1fr;
        min-height: 8;
    }
    #block-hint {
        height: auto;
        padding-top: 1;
    }
    #action-status {
        height: 1;
    }
    .detail-title {
        text-style: bold;
    }
    """

    def __init__(self, block: BlockAnalysis) -> None:
        super().__init__()
        self.block = block
        self._flagged = _flagged_transactions(block)

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="block-dialog"):
            yield Label(self._title(), classes="detail-title")
            yield Label("", id="action-status")
            with VerticalScroll(id="block-meta-scroll"):
                yield Static(self._meta_text(), id="block-meta")
            yield Label(self._tx_section_title(), id="block-tx-header")
            yield DataTable(
                id="block-tx-table",
                zebra_stripes=True,
                cursor_type="row",
            )
            yield Label(self._hint_text(), id="block-hint")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#block-tx-table", DataTable)
        table.add_columns("Txid", "Weight", "Type", "Flags / Signals")
        for tx in self._flagged[:50]:
            flags = ", ".join(sorted(tx.bip110_flags)) or "—"
            signals = ", ".join(sorted(tx.signals)) or "—"
            detail = flags if flags != "—" else signals
            if flags != "—" and signals != "—":
                detail = f"{flags} · {signals}"
            detail = detail[:48] + ("…" if len(detail) > 48 else "")
            table.add_row(
                f"{tx.txid[:18]}…",
                f"{tx.weight:,}",
                _tx_type(tx),
                detail,
                key=tx.txid,
            )
        if self._flagged:
            table.move_cursor(row=0)

    def _title(self) -> str:
        b = self.block
        sig = "YES" if b.bip110_signaling else "no"
        return (
            f"Block #{b.height}  ·  Spam {b.spam_score}/100  ·  "
            f"{b.status}  ·  BIP110 bit4: {sig}"
        )

    def _meta_text(self) -> str:
        b = self.block
        miner = format_pool_badge(b.miner_tag)
        return "\n".join([
            f"Hash:     {b.hash}",
            f"Miner:   {miner}",
            f"Weight:  {b.weight:,}  ({b.tx_count} txs)  ·  "
            f"Witness {b.witness_pct:.1f}%",
            "",
            "Spam breakdown:",
            f"  Inscriptions {b.inscription_count}  ·  BRC-20 {b.brc20_count}  ·  "
            f"Runes {b.runes_count}  ·  OP_RETURN {b.op_return_count}",
            f"  BIP-110 violations: {b.violation_count} tx "
            f"({b.violation_weight:,} wt)",
        ])

    def _tx_section_title(self) -> str:
        n = len(self._flagged)
        if n == 0:
            return "Flagged transactions — none detected"
        return f"Flagged transactions — {n} tx (top {min(n, 50)} by weight)"

    def _hint_text(self) -> str:
        if not self._flagged:
            return "c copy hash · Esc close"
        return (
            "↑↓ select tx · i or Enter inspect in Tx Inspector · "
            "t copy txid · c copy hash · Esc close"
        )

    def _selected_txid(self) -> str | None:
        table = self.query_one("#block-tx-table", DataTable)
        coord = table.cursor_coordinate
        if coord is None:
            return None
        cell_key = table.coordinate_to_cell_key(coord)
        return str(cell_key.row_key.value)

    def _show_status(self, message: str, *, warn: bool = False) -> None:
        status = self.query_one("#action-status", Label)
        if warn:
            status.update(f"[yellow]{message}[/]")
        else:
            status.update(message)

    def action_copy_hash(self) -> None:
        if copy_to_clipboard(self.block.hash):
            self._show_status("✓ Block hash copied to clipboard")
        else:
            self._show_status("Could not copy hash (install wl-copy/xclip)", warn=True)

    def action_copy_txid(self) -> None:
        txid = self._selected_txid()
        if not txid:
            self._show_status("Select a flagged transaction first", warn=True)
            return
        if copy_to_clipboard(txid):
            self._show_status(f"✓ Txid copied ({txid[:20]}…)")
        else:
            self._show_status("Could not copy txid (install wl-copy/xclip)", warn=True)

    def _selected_tx_analysis(self) -> TxAnalysis | None:
        txid = self._selected_txid()
        if not txid:
            return None
        for tx in self._flagged:
            if tx.txid == txid:
                return tx
        return None

    def action_inspect_txid(self) -> None:
        txid = self._selected_txid()
        if not txid:
            self._show_status("Select a flagged transaction first", warn=True)
            return
        raw_tx = self.block.flagged_raw.get(txid)
        cached = self._selected_tx_analysis()
        self.dismiss()
        if hasattr(self.app, "inspect_transaction"):
            self.app.inspect_transaction(
                txid,
                block_hash=self.block.hash,
                block_height=self.block.height,
                raw_tx=raw_tx,
                cached_analysis=cached,
            )

    def action_dismiss(self) -> None:
        self.dismiss()