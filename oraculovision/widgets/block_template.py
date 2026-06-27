"""Compact block template (GBT) summary panel."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Label, Static

from oraculovision.services.template_service import TemplateService


class BlockTemplatePanel(Static):
    """Shows current getblocktemplate summary (compact)."""

    BINDINGS = [
        Binding("t", "refresh_template", "Refresh GBT", show=True),
    ]

    DEFAULT_CSS = """
    BlockTemplatePanel {
        height: auto;
        max-height: 11;
        padding: 0 2;
    }
    BlockTemplatePanel .template-hint {
        height: 1;
    }
    """

    def __init__(self, template_service: TemplateService, **kwargs) -> None:
        super().__init__(**kwargs)
        self.template_service = template_service
        self.border_title = "BLOCK TEMPLATE"

    def compose(self) -> ComposeResult:
        yield Label("[t] refresh", classes="template-hint")
        yield Label("Loading...", id="template-content", classes="template-content")

    def refresh_data(self, *, force: bool = False) -> None:
        self._fetch_template(force=force)

    def action_refresh_template(self) -> None:
        self.refresh_data(force=True)
        glass = self.app.query_one("#mempool-glass")
        glass.refresh_data(force=True)

    @work(thread=True, exclusive=True)
    def _fetch_template(self, force: bool = False) -> None:
        snapshot = self.template_service.fetch(force=force)
        if snapshot.error:
            self.app.call_from_thread(self._update_ui, f"[red]{snapshot.error}[/]")
            return
        self.app.call_from_thread(self._update_ui, self._format(snapshot.template))

    def _format(self, tmpl: dict) -> str:
        if not tmpl:
            return "[yellow]Template unavailable[/]"

        height = tmpl.get("height", "?")
        txs = tmpl.get("transactions", [])
        tx_count = len(txs)
        weight = sum(int(t.get("weight", 0)) for t in txs)
        limit = int(tmpl.get("weightlimit", 4_000_000))
        fill_pct = (weight / limit * 100) if limit else 0
        coinbase_btc = tmpl.get("coinbasevalue", 0) / 1e8
        total_fees = sum(t.get("fee", 0) for t in txs) / 1e8

        lines = [
            (
                f"#{height}  {tx_count:,}tx  "
                f"{weight:,}w ({fill_pct:.1f}%)  "
                f"cb {coinbase_btc:.4f}  fees {total_fees:.4f} BTC"
            ),
            "[gold bold]Top fee (sat/vB)[/]",
        ]

        ranked = sorted(
            txs,
            key=lambda t: t.get("fee", 0) / max(t.get("weight", 1) / 4, 1),
            reverse=True,
        )[:5]

        for tx in ranked:
            vsize = max(tx.get("weight", 0) // 4, 1)
            rate = tx.get("fee", 0) / vsize
            txid = (tx.get("txid") or "")[:10]
            lines.append(f"  {txid}  {rate:5.0f}  {tx.get('fee', 0)/1e8:.5f}")

        if not ranked:
            lines.append("  (empty)")

        return "\n".join(lines)

    def _update_ui(self, text: str) -> None:
        self.query_one("#template-content", Label).update(text)