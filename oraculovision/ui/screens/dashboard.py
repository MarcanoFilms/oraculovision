"""Dashboard screen — sovereignty brief, metrics, and expert panels."""

from __future__ import annotations

from datetime import datetime, timezone

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Label, Static

from oraculovision.analysis.policies import (
    fetch_knots_policies,
    format_mempool_policy_metric,
)
from oraculovision.analysis.sovereignty_score import compute_sovereignty_score
from oraculovision.config import AppConfig
from oraculovision.node.client import NodeClient
from oraculovision.presentation.sovereignty import (
    build_sovereignty_brief,
    fetch_sovereignty_snapshot,
)
from oraculovision.services.block_service import BlockService
from oraculovision.services.template_service import TemplateService
from oraculovision.ui.components.explain_box import ExplainBox
from oraculovision.ui.components.metric_card import MetricCard
from oraculovision.ui.components.sovereign_panel import SovereignPanel
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
    "hide expert panels (BIP-110 blocks, DATUM, charts). Use [bold]3[/] for full "
    "Mempool Glass and [bold]i[/] there to inspect any template transaction. "
    "The [bold]Score[/] card is a 0-100 composite (Ctrl+P → help for formula)."
)


class DashboardScreen(BaseScreen):
    """Overview: sovereignty brief, metric cards, collapsible expert panels."""

    screen_id = "dashboard"

    BINDINGS = [
        Binding("x", "toggle_expert", "Expert", show=True),
    ]

    DEFAULT_CSS = """
    DashboardScreen { layout: vertical; }
    DashboardScreen #dash-tagline {
        color: #ffd700;
        text-align: center;
        padding: 0 1;
        text-style: bold;
        height: auto;
    }
    DashboardScreen #dash-alert {
        color: #ff6b6b;
        text-align: center;
        padding: 0 1;
        height: auto;
        min-height: 1;
    }
    DashboardScreen #sov-brief { margin: 0 1 1 1; }
    DashboardScreen #metric-row { height: auto; padding: 0 1; margin-bottom: 1; }
    DashboardScreen #dash-explain { margin: 0 1 1 1; }
    DashboardScreen #dash-hint {
        height: auto;
        color: #888;
        text-align: center;
        padding: 0 1 1 1;
    }
    DashboardScreen #expert-section { height: 1fr; }
    DashboardScreen #dash-body { height: 1fr; }
    DashboardScreen #left-col  { width: 52%; height: 1fr; }
    DashboardScreen #right-col { width: 48%; height: 1fr; padding-left: 1; }
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
        self._expert_visible = True
        self._tip_spam: int | None = None
        self._tip_miner: str = ""
        self._template_spam_pct: float = 0.0

    def compose(self) -> ComposeResult:
        yield Label("", id="dash-tagline")
        yield Label("", id="dash-alert")
        yield SovereignPanel("SOVEREIGNTY BRIEF", id="sov-brief")
        with Horizontal(id="metric-row"):
            yield MetricCard("Score", "—", id="metric-score", use_digits=False)
            yield MetricCard("Sync", "—", id="metric-sync")
            yield MetricCard("Peers", "—", id="metric-peers")
            yield MetricCard("Mempool", "—", id="metric-mempool")
            yield MetricCard("Policy", "—", id="metric-policy")
        yield ExplainBox("How to read this", DASH_EXPLAIN, id="dash-explain")
        yield Static(
            "[dim]Expert panels visible · [bold]x[/] toggle · "
            "[bold]r[/] refresh · [bold]t[/] template · [bold]u[/] utxo[/]",
            id="dash-hint",
        )
        with Vertical(id="expert-section"):
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

    def on_mount(self) -> None:
        self.refresh_screen()

    def action_toggle_expert(self) -> None:
        self._expert_visible = not self._expert_visible
        expert = self.query_one("#expert-section")
        if self._expert_visible:
            expert.remove_class("hidden")
            hint = (
                "[dim]Expert panels visible · [bold]x[/] toggle · "
                "[bold]r[/] refresh · [bold]t[/] template · [bold]u[/] utxo[/]"
            )
        else:
            expert.add_class("hidden")
            hint = "[dim]Expert panels hidden · [bold]x[/] show · [bold]r[/] refresh[/]"
        self.query_one("#dash-hint", Static).update(hint)

    def refresh_screen(self, *, force: bool = False) -> None:
        self._update_tagline()
        self._refresh_brief_and_metrics(force=force)
        self.query_one("#node-status", NodeStatus).refresh_data()
        self.query_one("#bip110", Bip110Detector).refresh_data()
        self.query_one("#datum", DatumMining).refresh_data()
        self.query_one("#mempool-glass", MempoolGlass).refresh_data(force=force)
        self.query_one("#block-template", BlockTemplatePanel).refresh_data(force=force)
        try:
            self.query_one("#charts", LiveCharts).refresh_data()
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

    def _apply_brief_and_metrics(self, snap, policy, template_spam_pct: float) -> None:
        tip_spam: int | None = None
        tip_miner = ""
        try:
            bip = self.query_one("#bip110", Bip110Detector)
            if bip._tip:
                tip_spam = bip._tip.spam_score
                tip_miner = bip._tip.miner_tag
        except Exception:
            pass

        self._tip_spam = tip_spam
        self._tip_miner = tip_miner
        self._template_spam_pct = template_spam_pct

        brief = build_sovereignty_brief(
            snap,
            self.config,
            template_spam_pct=template_spam_pct,
            tip_spam_score=tip_spam,
            tip_miner=tip_miner,
        )
        panel = self.query_one("#sov-brief", SovereignPanel)
        panel.update_content(brief.text)
        panel.set_severity(brief.severity)

        # Sovereignty Score
        score_result = compute_sovereignty_score(
            is_synced=snap.is_synced,
            sync_pct=snap.sync_pct,
            peer_count=snap.peer_count,
            min_peers=self.config.alerts.min_peers,
            knots=snap.knots,
            template_spam_pct=template_spam_pct,
            tip_spam_score=tip_spam,
        )
        score_sev = (
            "ok" if score_result.score >= 80
            else ("warn" if score_result.score >= 60 else "danger")
        )
        score_card = self.query_one("#metric-score", MetricCard)
        score_card.update_metric(
            f"{score_result.score}",
            subtitle=score_result.grade,
            severity=score_sev,
        )

        sync_card = self.query_one("#metric-sync", MetricCard)
        if snap.error:
            sync_card.update_metric("—", subtitle="offline", severity="danger")
        elif snap.is_synced:
            sync_card.update_metric(
                f"{snap.sync_pct:.1f}%",
                subtitle=f"#{snap.chain_height:,}",
                severity="ok",
            )
        else:
            sync_card.update_metric(
                f"{snap.sync_pct:.1f}%",
                subtitle=f"#{snap.chain_height:,} syncing",
                severity="warn",
            )

        peers_card = self.query_one("#metric-peers", MetricCard)
        min_peers = self.config.alerts.min_peers
        peer_sev = "ok" if snap.peer_count >= min_peers else "danger"
        peers_card.update_metric(
            str(snap.peer_count),
            subtitle=f"min {min_peers}",
            severity=peer_sev,
        )

        mempool_card = self.query_one("#metric-mempool", MetricCard)
        mempool_alert = self.config.alerts.mempool_congested_tx
        mp_sev = "warn" if snap.mempool_tx >= mempool_alert else "ok"
        mempool_card.update_metric(
            f"{snap.mempool_tx:,}",
            subtitle=f"{snap.mempool_mb:.1f} MB",
            severity=mp_sev,
        )

        policy_card = self.query_one("#metric-policy", MetricCard)
        pol_value, pol_sub, pol_sev = format_mempool_policy_metric(policy)
        policy_card.update_metric(pol_value, subtitle=pol_sub, severity=pol_sev)

        # Milestone: check block height celebrations via app
        try:
            self.app.check_height_milestone(snap.chain_height)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _update_tagline(self) -> None:
        utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        self.query_one("#dash-tagline", Label).update(
            f"ORACULOVISION  ·  {utc}  ·  "
            "[r] refresh  [t] template  [u] utxo  [o] ocean  [x] expert  [Ctrl+P] commands"
        )

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
