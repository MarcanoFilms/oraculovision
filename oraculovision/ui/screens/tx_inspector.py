"""Transaction Inspector — deep tx analysis and address balances."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Input, Label, Static

from oraculovision.node.addresses import AddressQueryError, classify_query
from oraculovision.node.client import BitcoinCLIError
from oraculovision.services.address_service import (
    AddressInspection,
    AddressQueryError as AddrSvcError,
    AddressService,
    format_address_inspection,
)
from oraculovision.services.tx_service import (
    TxInspectContext,
    TxInspection,
    TxQueryError,
    TxService,
    format_inspection,
)
from oraculovision.ui.screens.base import BaseScreen
from oraculovision.utils.clipboard import copy_to_clipboard


class TxInspectorScreen(BaseScreen):
    """Inspect transactions by txid or addresses by UTXO balance."""

    screen_id = "tx_inspector"

    BINDINGS = [
        Binding("slash", "focus_search", "Search", show=True),
        Binding("c", "copy_selection", "Copy", show=True),
        Binding("a", "inspect_address", "Address", show=True),
    ]

    DEFAULT_CSS = """
    TxInspectorScreen {
        layout: vertical;
    }
    TxInspectorScreen #tx-header {
        height: auto;
        text-style: bold;
        padding: 0 1;
    }
    TxInspectorScreen #tx-search-row {
        height: auto;
        padding: 0 1 1 1;
    }
    TxInspectorScreen #tx-search {
        width: 1fr;
    }
    TxInspectorScreen #tx-status {
        height: auto;
        padding: 0 1;
    }
    TxInspectorScreen #tx-detail-scroll {
        height: 1fr;
        margin: 0 1 1 1;
        padding: 1 2;
    }
    TxInspectorScreen .search-label {
        width: auto;
        padding-right: 1;
        content-align: center middle;
    }
    """

    def __init__(
        self,
        tx_service: TxService,
        address_service: AddressService | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.tx_service = tx_service
        self.address_service = address_service
        self._mode: str = "none"
        self._last_query: str = ""
        self._last_context: TxInspectContext | None = None
        self._last_tx_inspection: TxInspection | None = None
        self._last_address_inspection: AddressInspection | None = None
        self._last_address_hint: str = ""

    def export_context(self) -> TxInspection | AddressInspection | None:
        if self._mode == "address":
            return self._last_address_inspection
        return self._last_tx_inspection

    def compose(self) -> ComposeResult:
        yield Label("TRANSACTION & ADDRESS INSPECTOR", id="tx-header")
        with Horizontal(id="tx-search-row"):
            yield Label("Query:", classes="search-label")
            yield Input(
                placeholder="txid (64 hex) or address (bc1… / 1… / 3…)",
                id="tx-search",
            )
        yield Static(
            "/ search  ·  Enter query  ·  a address from tx  ·  c copy  ·  e export",
            id="tx-status",
        )
        with VerticalScroll(id="tx-detail-scroll"):
            yield Static(
                "[dim]Enter a txid or Bitcoin address.[/]",
                id="tx-detail",
            )

    def refresh_screen(self, *, force: bool = False) -> None:
        if self._last_query:
            self._run_query(self._last_query, self._last_context)

    def action_focus_search(self) -> None:
        self.query_one("#tx-search", Input).focus()

    def inspect_txid(
        self,
        txid: str,
        *,
        context: TxInspectContext | None = None,
    ) -> None:
        query = txid.strip()
        if not query:
            return
        self._last_context = context
        self.query_one("#tx-search", Input).value = query
        self._run_query(query, context)

    def inspect_address(self, address: str) -> None:
        address = address.strip()
        if not address:
            return
        self._last_context = None
        self.query_one("#tx-search", Input).value = address
        self._run_query(address, None)

    def action_inspect_address(self) -> None:
        if self._last_address_hint:
            self.inspect_address(self._last_address_hint)
            return
        if self._last_tx_inspection and self._last_tx_inspection.flow:
            for addr in self._last_tx_inspection.flow.all_addresses:
                self.inspect_address(addr)
                return
        self.notify(
            "Load a transaction first, or enter an address in the search box",
            title="Address",
            severity="warning",
            timeout=4,
        )

    def action_copy_selection(self) -> None:
        text = ""
        if self._mode == "address" and self._last_address_inspection:
            text = self._last_address_inspection.address
        elif self._last_tx_inspection:
            text = self._last_tx_inspection.txid
        if not text:
            return
        if copy_to_clipboard(text):
            self.notify(f"Copied {text[:24]}…", title="Clipboard", timeout=3)
        else:
            self.notify("Clipboard unavailable", severity="warning", timeout=3)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "tx-search":
            return
        query = event.value.strip()
        if not query:
            return
        self._last_context = None
        self._run_query(query, None)

    def _run_query(self, query: str, context: TxInspectContext | None) -> None:
        try:
            kind, value = classify_query(query)
        except (AddressQueryError, ValueError) as exc:
            self._show_error(str(exc))
            return
        self._last_query = value
        if kind == "address":
            self._inspect_address(value)
        else:
            self._inspect_tx(value, context)

    @work(thread=True, exclusive=True)
    def _inspect_tx(
        self,
        query: str,
        context: TxInspectContext | None,
    ) -> None:
        try:
            result = self.tx_service.inspect(query, context=context)
            text = format_inspection(result)
            hint = ""
            if result.flow and result.flow.all_addresses:
                hint = result.flow.all_addresses[0]
            self.app.call_from_thread(
                self._update_tx_detail,
                text,
                result,
                hint,
            )
        except (TxQueryError, BitcoinCLIError) as exc:
            self.app.call_from_thread(self._show_error, str(exc))

    @work(thread=True, exclusive=True)
    def _inspect_address(self, address: str) -> None:
        if self.address_service is None:
            self.app.call_from_thread(
                self._show_error,
                "Address service not configured",
            )
            return
        self.app.call_from_thread(
            self._set_status,
            f"Scanning UTXO set for {address[:20]}…  (may take up to 90s)",
        )
        try:
            result = self.address_service.inspect_address(address)
            text = format_address_inspection(result)
            self.app.call_from_thread(self._update_address_detail, text, result)
        except (AddrSvcError, BitcoinCLIError) as exc:
            self.app.call_from_thread(self._show_error, str(exc))

    def _set_status(self, message: str) -> None:
        self.query_one("#tx-status", Static).update(message)

    def _show_error(self, message: str) -> None:
        self._mode = "none"
        self.query_one("#tx-status", Static).update(f"[red]{message}[/]")
        self.query_one("#tx-detail", Static).update("[dim]No data loaded.[/]")
        self.remove_class("violation", "spam-signal", "partial", "address-mode")

    def _update_tx_detail(
        self,
        text: str,
        result: TxInspection,
        address_hint: str,
    ) -> None:
        self._mode = "tx"
        self._last_tx_inspection = result
        self._last_address_inspection = None
        self._last_address_hint = address_hint
        status = f"Tx {result.txid[:20]}…"
        if result.partial:
            status += "  ·  partial (pruned)"
        elif result.source_note:
            status += f"  ·  {result.source_note[:50]}"
        self.query_one("#tx-status", Static).update(status)
        self.query_one("#tx-detail", Static).update(text)
        self.remove_class("violation", "spam-signal", "partial", "address-mode")
        if result.partial:
            self.add_class("partial")
        elif result.analysis.has_bip110_violation:
            self.add_class("violation")
        elif result.analysis.is_spam_signal:
            self.add_class("spam-signal")

    def _update_address_detail(
        self,
        text: str,
        result: AddressInspection,
    ) -> None:
        self._mode = "address"
        self._last_address_inspection = result
        self._last_tx_inspection = None
        self._last_address_hint = result.address
        status = f"Address {result.address[:24]}…"
        if result.error:
            status += f"  ·  [red]{result.error}[/]"
        else:
            status += f"  ·  {result.balance_btc:.8f} BTC confirmed"
        self.query_one("#tx-status", Static).update(status)
        self.query_one("#tx-detail", Static).update(text)
        self.remove_class("violation", "spam-signal", "partial")
        self.add_class("address-mode")