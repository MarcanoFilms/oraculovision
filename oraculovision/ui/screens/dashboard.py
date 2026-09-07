"""Dashboard screen — PyBlock aesthetic: dense two-column layout."""

from __future__ import annotations

from datetime import datetime, timezone

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Label, Static

from oraculovision.analysis.policies import fetch_knots_policies
from oraculovision.config import AppConfig
from oraculovision.node.client import NodeClient
from oraculovision.presentation.sovereignty import (
    build_sovereignty_brief,
    fetch_sovereignty_snapshot,
)
from oraculovision.services.block_service import BlockService
from oraculovision.services.template_service import TemplateService
from oraculovision.ui.components.explain_box import ExplainBox
from oraculovision.ui.screens.base import BaseScreen
from oraculovision.widgets.bip110_detector import Bip110Detector
from oraculovision.widgets.block_template import BlockTemplatePanel
from oraculovision.widgets.datum_mining import DatumMining
from oraculovision.widgets.live_charts import LiveCharts
from oraculovision.widgets.mempool_glass import MempoolGlass
from oraculovision.widgets.node_status import NodeStatus

DASH_EXPLAIN = (
    "Your dashboard summarizes node sovereignty at a glance. Metric cards pull live "
    "RPC data from your Knots node — no third-party APIs. Press [bold]x[/] to show or "
    "hide the explain box. Use [bold]3[/] for full Mempool Glass and [bold]i[/] there "
    "to inspect any template transaction."
)


class DashboardScreen(BaseScreen):
    """Overview: dense two-column PyBlock layout."""

    screen_id = "dashboard"

    BINDINGS = [
        Binding("x", "toggle_explain", "Explain", show=True),
        Binding("v", "cycle_charts", "Vision", show=True),
    ]

    DEFAULT_CSS = """
    DashboardScreen {
        layout: vertical;
    }
    DashboardScreen #dash-headline {
        height: 1;
        padding: 0 1;
    }
    DashboardScreen #dash-alert {
        height: auto;
        min-height: 1;
        padding: 0 1;
    }
    DashboardScreen #dash-explain {
        margin: 0 1 1 1;
    }
    DashboardScreen #dash-body {
        height: 1fr;
    }
    DashboardScreen #left-col {
        width: 57%;
        height: 1fr;
    }
    DashboardScreen #right-col {
        width: 43%;
        height: 1fr;
        padding-left: 1;
    }
    DashboardScreen #dash-hint {
        height: 1;
        padding: 0 1;
    }
    #node-status {
        height: auto;
        max-height: 18;
    }
    #bip110 {
        height: 1fr;
        min-height: 10;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        cli: NodeClient,
        config: AppConfig,
        template_service: TemplateService,
        block_service: BlockService | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.cli = cli
        self.config = config
        self.template_service = template_service
        self.block_service = block_service
        self._explain_visible = False
        # cached snap for headline
        self._snap = None
        self._score: int = 0
        self._grade: str = "?"
        self._spam_pct: float = 0.0

    def compose(self) -> ComposeResult:
        yield Static("", id="dash-headline")
        yield Label("", id="dash-alert")
        yield ExplainBox(
            "How to read this",
            DASH_EXPLAIN,
            id="dash-explain",
            classes="hidden",
        )
        with Horizontal(id="dash-body"):
            with Vertical(id="left-col"):
                yield NodeStatus(id="node-status", cli=self.cli, config=self.config)
                yield Bip110Detector(
                    id="bip110",
                    cli=self.cli,
                    config=self.config,
                    block_service=self.block_service,
                )
            with VerticalScroll(id="right-col"):
                yield DatumMining(id="datum", config=self.config)
                yield MempoolGlass(
                    id="mempool-glass",
                    template_service=self.template_service,
                    cli=self.cli,
                    config=self.config,
                )
                yield BlockTemplatePanel(
                    id="block-template",
                    template_service=self.template_service,
                )
                yield LiveCharts(id="charts", cli=self.cli)
        yield Static(
            "[dim]"
            "[bold]r[/] refresh  "
            "[bold]t[/] template  "
            "[bold]u[/] utxo  "
            "[bold]o[/] ocean  "
            "[bold]x[/] explain  "
            "[bold]1-8[/] screens"
            "[/]",
            id="dash-hint",
        )

    def on_mount(self) -> None:
        self.refresh_screen()

    def action_toggle_explain(self) -> None:
        self._explain_visible = not self._explain_visible
        box = self.query_one("#dash-explain")
        if self._explain_visible:
            box.remove_class("hidden")
        else:
            box.add_class("hidden")

    def action_cycle_charts(self) -> None:
        try:
            self.query_one("#charts", LiveCharts).action_cycle_view()
        except Exception:
            pass

    def refresh_screen(self, *, force: bool = False) -> None:
        self._update_headline()
        self._refresh_brief_and_metrics(force=force)
        self.query_one("#node-status", NodeStatus).refresh_data()
        self.query_one("#bip110", Bip110Detector).refresh_data()
        self.query_one("#datum", DatumMining).refresh_data()
        self.query_one("#mempool-glass", MempoolGlass).refresh_data(force=force)
        self.query_one("#block-template", BlockTemplatePanel).refresh_data(force=force)
        try:
            self.query_one("#charts", LiveCharts).refresh_data(
                score=self._score,
                spam_pct=self._spam_pct,
            )
        except Exception:
            pass
        self.set_timer(2.0, self._update_global_alerts)

    def refresh_template(self) -> None:
        self.template_service.invalidate()
        self.query_one("#mempool-glass", MempoolGlass).refresh_data(force=True)
        self.query_one("#block-template", BlockTemplatePanel).refresh_data(force=True)
        self._refresh_brief_and_metrics(force=True)
        self.set_timer(2.0, self._update_global_alerts)

    def refresh_utxo(self) -> None:
        self.query_one("#node-status", NodeStatus).refresh_utxo()

    @work(thread=True, exclusive=True)
    def _refresh_brief_and_metrics(self, force: bool = False) -> None:
        snap = fetch_sovereignty_snapshot(self.cli, self.config)
        policy = fetch_knots_policies(self.cli)

        template_spam_pct = 0.0
        try:
            snapshot = self.template_service.fetch(force=force)
            comp = snapshot.composition
            if not comp.error:
                template_spam_pct = comp.pct(comp.spam_weight)
        except Exception:
            pass

        self.app.call_from_thread(
            self._apply_brief_and_metrics,
            snap,
            policy,
            template_spam_pct,
        )

    def _apply_brief_and_metrics(
        self,
        snap,
        policy,
        template_spam_pct: float,
    ) -> None:
        tip_spam: int | None = None
        tip_miner = ""
        try:
            bip = self.query_one("#bip110", Bip110Detector)
            if bip._tip:
                tip_spam = bip._tip.spam_score
                tip_miner = bip._tip.miner_tag
        except Exception:
            pass

        brief = build_sovereignty_brief(
            snap,
            self.config,
            template_spam_pct=template_spam_pct,
            tip_spam_score=tip_spam,
            tip_miner=tip_miner,
        )

        # Compute a simple sovereignty score (0-100)
        score = 100
        if snap.error:
            score = 0
        else:
            if not snap.knots:
                score -= 20
            if not snap.is_synced:
                score -= 15
            peer_ok = snap.peer_count >= self.config.alerts.min_peers
            if not peer_ok:
                score -= 20
            if snap.mempool_tx >= self.config.alerts.mempool_congested_tx:
                score -= 10
            if template_spam_pct > 30:
                score -= 15
            elif template_spam_pct > 15:
                score -= 5
            if tip_spam is not None and tip_spam >= 50:
                score -= 10
        score = max(0, score)

        if score >= 90:
            grade = "A+"
        elif score >= 80:
            grade = "A"
        elif score >= 70:
            grade = "B"
        elif score >= 60:
            grade = "C"
        else:
            grade = "F"

        self._snap = snap
        self._score = score
        self._grade = grade
        self._spam_pct = template_spam_pct

        if snap and not snap.error and snap.chain_height:
            try:
                self.app.check_height_milestone(snap.chain_height)  # type: ignore[attr-defined]
            except Exception:
                pass

        self._update_headline()
        try:
            self.query_one("#charts", LiveCharts).refresh_data(
                score=score,
                spam_pct=template_spam_pct,
            )
        except Exception:
            pass

    def _update_headline(self) -> None:
        utc = datetime.now(timezone.utc).strftime("%H:%M UTC")
        snap = self._snap
        score = self._score
        grade = self._grade
        spam_pct = self._spam_pct

        if snap is None or snap.error:
            peers = 0
            height = 0
            version_short = "offline"
            mempool_tx = 0
            peer_ok = False
            spam_high = False
        else:
            peers = snap.peer_count
            height = snap.chain_height
            subver = snap.client_label
            version_short = "Knots" if snap.knots else "Core"
            mempool_tx = snap.mempool_tx
            peer_ok = peers >= self.config.alerts.min_peers
            spam_high = spam_pct > 30

        peer_color = "green" if peer_ok else "red"
        spam_color = "red" if spam_high else "dim"

        text = (
            f"[bold rgb(255,102,0)]◉[/]  "
            f"[bold white]Score:[/] [bold cyan]{score}[/][dim]/{grade}[/]  "
            f"[dim]·[/]  Block [bold white]#{height:,}[/]  "
            f"[dim]·[/]  {version_short}  "
            f"[dim]·[/]  Peers [bold {peer_color}]{peers}[/]  "
            f"[dim]·[/]  Mempool [white]{mempool_tx:,}[/][dim] tx[/]  "
            f"[dim]·[/]  Spam [{spam_color}]{spam_pct:.0f}%[/]  "
            f"[dim]{utc}[/]"
        )
        try:
            self.query_one("#dash-headline", Static).update(text)
        except Exception:
            pass

    def _update_global_alerts(self) -> None:
        alert = self.query_one("#dash-alert", Label)
        node = self.query_one("#node-status", NodeStatus)
        bip = self.query_one("#bip110", Bip110Detector)
        glass = self.query_one("#mempool-glass", MempoolGlass)

        msgs: list[str] = []
        if node.alert_message:
            msgs.append(node.alert_message)
        if bip.alert_spam_block and bip._tip:
            msgs.append(
                f"⚠ Dirty tip block: spam {bip._tip.spam_score}/100 "
                f"({bip._tip.miner_tag[:24]})"
            )
        if glass.spam_pct > 30:
            msgs.append(f"⚠ Template: {glass.spam_pct:.0f}% spam weight")

        if msgs:
            alert.update("[bold red]" + "  ·  ".join(msgs) + "[/]")
        else:
            alert.update("")
