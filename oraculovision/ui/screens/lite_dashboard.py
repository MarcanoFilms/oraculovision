"""Lite Dashboard — single-screen overview for first-time node operators."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, Static

from oraculovision.analysis.sovereignty_score import compute_sovereignty_score
from oraculovision.config import AppConfig
from oraculovision.node.client import NodeClient
from oraculovision.presentation.sovereignty import (
    fetch_sovereignty_snapshot,
)
from oraculovision.ui.components.metric_card import MetricCard
from oraculovision.ui.screens.base import BaseScreen
from oraculovision.widgets.datum_mining import DatumMining


class LiteDashboard(BaseScreen):
    """Simplified single-screen view: alerts + key metrics + DATUM."""

    screen_id = "lite_dashboard"

    DEFAULT_CSS = """
    LiteDashboard { layout: vertical; padding: 0 1; }
    LiteDashboard #lite-header {
        text-style: bold;
        text-align: center;
        padding: 0 1 1 1;
        height: auto;
    }
    LiteDashboard #lite-alert {
        text-align: center;
        height: auto;
        min-height: 1;
        padding: 0 1;
    }
    LiteDashboard #lite-metrics { height: auto; padding: 0 0 1 0; }
    LiteDashboard #lite-datum   { height: auto; max-height: 20; margin-top: 1; }
    LiteDashboard #lite-upgrade-hint {
        text-align: center;
        height: auto;
        padding: 1;
    }
    """

    def __init__(
        self,
        cli: NodeClient,
        config: AppConfig,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.cli = cli
        self.config = config

    def compose(self) -> ComposeResult:
        yield Label("ORACULOVISION  ·  Lite Mode", id="lite-header")
        yield Label("", id="lite-alert")
        with Horizontal(id="lite-metrics"):
            yield MetricCard("Score", "—", id="lite-score", use_digits=False)
            yield MetricCard("Sync", "—", id="lite-sync")
            yield MetricCard("Peers", "—", id="lite-peers")
            yield MetricCard("Mempool", "—", id="lite-mempool")
        with Vertical(id="lite-datum"):
            yield DatumMining(id="lite-datum-widget", config=self.config)
        yield Static(
            "[dim]Lite Mode · Ctrl+P → 'Toggle Pro mode' for full dashboard · [r] refresh[/]",
            id="lite-upgrade-hint",
        )

    def on_mount(self) -> None:
        self.refresh_screen()

    def refresh_screen(self, *, force: bool = False) -> None:
        self._load_data()
        try:
            self.query_one("#lite-datum-widget", DatumMining).refresh_data()
        except Exception:
            pass

    @work(thread=True, exclusive=True)
    def _load_data(self) -> None:
        snap = fetch_sovereignty_snapshot(self.cli, self.config)
        self.app.call_from_thread(self._apply, snap)

    def _apply(self, snap) -> None:
        alert = self.query_one("#lite-alert", Label)

        if snap.error:
            alert.update(f"[bold red]⚠ Node offline: {snap.error[:60]}[/]")
            for card_id in ("lite-score", "lite-sync", "lite-peers", "lite-mempool"):
                try:
                    self.query_one(f"#{card_id}", MetricCard).update_metric("—", severity="danger")
                except Exception:
                    pass
            return

        score_result = compute_sovereignty_score(
            is_synced=snap.is_synced,
            sync_pct=snap.sync_pct,
            peer_count=snap.peer_count,
            min_peers=self.config.alerts.min_peers,
            knots=snap.knots,
        )
        sev = "ok" if score_result.score >= 80 else ("warn" if score_result.score >= 60 else "danger")
        self.query_one("#lite-score", MetricCard).update_metric(
            f"{score_result.score}",
            subtitle=score_result.grade,
            severity=sev,
        )

        sync_sev = "ok" if snap.is_synced else "warn"
        self.query_one("#lite-sync", MetricCard).update_metric(
            f"{snap.sync_pct:.1f}%",
            subtitle=f"#{snap.chain_height:,}",
            severity=sync_sev,
        )

        peer_sev = "ok" if snap.peer_count >= self.config.alerts.min_peers else "danger"
        self.query_one("#lite-peers", MetricCard).update_metric(
            str(snap.peer_count),
            subtitle=f"min {self.config.alerts.min_peers}",
            severity=peer_sev,
        )

        mp_sev = "warn" if snap.mempool_tx >= self.config.alerts.mempool_congested_tx else "ok"
        self.query_one("#lite-mempool", MetricCard).update_metric(
            f"{snap.mempool_tx:,}",
            subtitle=f"{snap.mempool_mb:.1f} MB",
            severity=mp_sev,
        )

        msgs: list[str] = []
        if not snap.is_synced:
            msgs.append(f"⚠ Syncing {snap.sync_pct:.1f}%")
        if snap.peer_count < self.config.alerts.min_peers:
            msgs.append(f"⚠ Low peers ({snap.peer_count})")
        if snap.mempool_tx >= self.config.alerts.mempool_congested_tx:
            msgs.append(f"⚠ Congested mempool ({snap.mempool_tx:,} tx)")
        alert.update("[bold red]" + "  ·  ".join(msgs) + "[/]" if msgs else "")
