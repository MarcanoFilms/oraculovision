"""Mempool Glass — block template composition visualization."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.widgets import Label, Static

from oraculovision.analysis.mempool_compose import MempoolComposition
from oraculovision.config import AppConfig
from oraculovision.data.bitcoin import BitcoinCLI, BitcoinCLIError
from oraculovision.services.template_service import TemplateService


def _bar(pct: float, width: int = 28, char: str = "█") -> str:
    filled = int(round(pct / 100 * width))
    filled = max(0, min(width, filled))
    return char * filled + "░" * (width - filled)


def _render_glass(comp: MempoolComposition, mempool_tx: int, mempool_mb: float) -> str:
    if comp.error:
        return f"[red]{comp.error}[/]"

    lines = [
        (
            f"[gold bold]Based on Block Template[/]  "
            f"#{comp.template_height}  ·  {comp.analyzed_tx:,} txs  ·  "
            f"{comp.fill_pct:.1f}% max weight"
        ),
        (
            f"Mempool total: {mempool_tx:,} tx ({mempool_mb:.2f} MB)  ·  "
            f"template wt {comp.analyzed_weight:,}/{comp.weight_limit:,}"
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
        lines.append(f"[{style}]{label:20}[/] {pct:5.1f}%  ({count:,} tx)")
        lines.append(f"  [{style}]{_bar(pct)}[/]")

    spam_pct = comp.pct(comp.spam_weight)
    if spam_pct > 30:
        lines.append("\n[red bold]⚠ Very dirty template — high BIP-110 impact[/]")
    elif spam_pct > 15:
        lines.append("\n[yellow]⚠ Elevated spam in next block[/]")

    return "\n".join(lines)


class MempoolGlass(Static):
    """Visual composition of the node's current block template."""

    DEFAULT_CSS = """
    MempoolGlass {
        height: auto;
        min-height: 12;
        padding: 1 2;
    }
    """

    def __init__(
        self,
        template_service: TemplateService,
        cli: BitcoinCLI | None = None,
        config: AppConfig | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.template_service = template_service
        self.cli = cli or template_service.cli
        self.config = config or AppConfig()
        self.border_title = "🧊 MEMPOOL GLASS"
        self._last_spam_pct: float = 0.0

    def compose(self) -> ComposeResult:
        yield Label("Analyzing block template...", id="glass-content", classes="glass-content")

    def refresh_data(self, *, force: bool = False) -> None:
        self._fetch_composition(force=force)

    @property
    def spam_pct(self) -> float:
        return self._last_spam_pct

    @work(thread=True, exclusive=True)
    def _fetch_composition(self, force: bool = False) -> None:
        try:
            mempool = self.cli.get_mempool_info()
            snapshot = self.template_service.fetch(force=force)
            comp = snapshot.composition
            mempool_tx = mempool.get("size", 0)
            mempool_mb = mempool.get("bytes", 0) / 1_000_000
            text = _render_glass(comp, mempool_tx, mempool_mb)
            self._last_spam_pct = comp.pct(comp.spam_weight)
            self.app.call_from_thread(self._update_ui, text, self._last_spam_pct)
        except BitcoinCLIError as exc:
            msg = str(exc)
            if exc.hint:
                msg += f"\n→ {exc.hint}"
            self.app.call_from_thread(self._update_ui, f"[red]{msg}[/]", 0.0)

    def _update_ui(self, text: str, spam_pct: float) -> None:
        self.query_one("#glass-content", Label).update(text)
        self.remove_class("alert-mempool", "alert-spam")
        if spam_pct > 30:
            self.add_class("alert-spam")
        elif spam_pct > 15:
            self.add_class("alert-mempool")