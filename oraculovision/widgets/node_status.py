"""Node status widget — live Knots/Core metrics with Sparkline trends."""

from __future__ import annotations

import time
from collections import deque

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, Sparkline, Static

from oraculovision.config import AppConfig, BitcoinConfig
from oraculovision.data.bitcoin import BitcoinCLI, BitcoinCLIError
from oraculovision.ui.components.live_indicator import LiveIndicator


class NodeStatus(Static):
    """Displays live node sync, peers, mempool, UTXO set, and alerts."""

    DEFAULT_CSS = """
    NodeStatus {
        height: auto;
        border: solid #ffd700;
        padding: 1 2;
    }
    NodeStatus .ns-metric { color: #e0e0e0; }
    NodeStatus .error { color: #ff6b6b; }
    NodeStatus .ok { color: #3dd68c; }
    NodeStatus .alert-line { color: #ff6b6b; text-style: bold; height: auto; }
    NodeStatus.alert-peers { border: solid #ff6b6b; }
    NodeStatus.alert-mempool { border: solid #ffc800; }
    NodeStatus #ns-body { height: auto; }
    NodeStatus #ns-text { width: 1fr; }
    NodeStatus #ns-charts { width: 24; padding-left: 1; }
    NodeStatus .chart-label { color: #888; height: 1; }
    NodeStatus Sparkline { height: 3; }
    NodeStatus #ns-header { height: 1; }
    """

    def __init__(
        self,
        cli: BitcoinCLI | None = None,
        config: AppConfig | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.config = config or AppConfig()
        self.cli = cli or BitcoinCLI()
        self.border_title = "NODE STATUS"
        self._utxo_cache: dict | None = None
        self._utxo_fetched_at: float = 0.0
        self._utxo_updating: bool = False
        self._prev_utxo_count: int | None = None
        self._chain_data: dict | None = None
        self._network_data: dict | None = None
        self._mempool_data: dict | None = None
        self.alert_peers: bool = False
        self.alert_mempool: bool = False
        self.alert_message: str = ""
        _n = getattr(self.config, "ui", None)
        samples = _n.sparkline_samples if _n else 60
        self._peers_buf: deque[float] = deque(maxlen=samples)
        self._mempool_buf: deque[float] = deque(maxlen=samples)

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(id="ns-header"):
                yield LiveIndicator(id="ns-live", stale_after=90.0)
                yield Label("", id="alert-line", classes="alert-line")
            with Horizontal(id="ns-body"):
                yield Label("Loading…", id="node-content", classes="ns-metric")
                with Vertical(id="ns-charts"):
                    yield Label("Peers", classes="chart-label")
                    yield Sparkline(
                        [],
                        summary_function=max,
                        id="peers-sparkline",
                    )
                    yield Label("Mempool MB", classes="chart-label")
                    yield Sparkline(
                        [],
                        summary_function=max,
                        id="mempool-sparkline",
                    )

    def refresh_utxo(self) -> None:
        if self._utxo_updating:
            return
        self._utxo_updating = True
        self._update_display()
        self._fetch_utxo_background()

    def refresh_data(self) -> None:
        label = self.query_one("#node-content", Label)
        alert_line = self.query_one("#alert-line", Label)
        alerts = self.config.alerts

        try:
            self._chain_data = self.cli.get_blockchain_info()
            self._network_data = self.cli.get_network_info()
            self._mempool_data = self.cli.get_mempool_info()
        except BitcoinCLIError as exc:
            msg = str(exc)
            if exc.hint:
                msg += f"\n→ {exc.hint}"
            label.update(msg)
            label.remove_class("ok")
            label.add_class("error")
            alert_line.update("")
            self._clear_alerts()
            return

        self._update_display()

    def _update_display(self) -> None:
        if not self._chain_data or not self._network_data or not self._mempool_data:
            return

        label = self.query_one("#node-content", Label)
        alert_line = self.query_one("#alert-line", Label)
        alerts = self.config.alerts

        chain = self._chain_data
        network = self._network_data
        mempool = self._mempool_data

        blocks = chain.get("blocks", 0)
        headers = chain.get("headers", 0)
        progress = chain.get("verificationprogress", 0) * 100
        ibd = chain.get("initialblockdownload", False)
        subver = network.get("subversion", "unknown")
        peers = network.get("connections", 0)
        mempool_tx = mempool.get("size", 0)
        mempool_mb = mempool.get("bytes", 0) / 1_000_000

        self._peers_buf.append(float(peers))
        self._mempool_buf.append(mempool_mb)

        self._update_sparklines()

        utxo_line = self._utxo_line()
        is_knots = "knots" in subver.lower()
        sync_cls = "ok" if not ibd and progress > 99.9 else "ns-metric"

        lines = [
            f"Chain:     {blocks:,} / {headers:,} blocks",
            f"Sync:      {progress:.2f}%{'  [IBD]' if ibd else '  [synced]'}",
            f"Peers:     {peers}",
            f"Mempool:   {mempool_tx:,} tx  ({mempool_mb:.2f} MB)",
            utxo_line,
            f"Client:    {subver}",
            f"Knots:     {'YES' if is_knots else 'no'}",
        ]
        label.update("\n".join(lines))
        label.remove_class("error")
        label.add_class(sync_cls)

        prev_alert_peers = self.alert_peers
        prev_alert_mempool = self.alert_mempool

        self.alert_peers = peers < alerts.min_peers
        self.alert_mempool = (
            mempool_mb >= alerts.mempool_congested_mb
            or mempool_tx >= alerts.mempool_congested_tx
        )
        self._apply_border_alerts(
            changed=(self.alert_peers != prev_alert_peers or self.alert_mempool != prev_alert_mempool)
        )

        alerts_msgs: list[str] = []
        if self.alert_peers:
            alerts_msgs.append(f"⚠ Low peers ({peers} < {alerts.min_peers})")
        if self.alert_mempool:
            alerts_msgs.append(
                f"⚠ Congested mempool ({mempool_tx:,} tx / {mempool_mb:.1f} MB)"
            )
        self.alert_message = "  ·  ".join(alerts_msgs)
        alert_line.update(self.alert_message)

        try:
            self.query_one("#ns-live", LiveIndicator).mark_fresh()
        except Exception:
            pass

    def _update_sparklines(self) -> None:
        try:
            sp_peers = self.query_one("#peers-sparkline", Sparkline)
            sp_peers.data = list(self._peers_buf)
            sp_mempool = self.query_one("#mempool-sparkline", Sparkline)
            sp_mempool.data = list(self._mempool_buf)
        except Exception:
            pass

    def _utxo_line(self) -> str:
        if self._utxo_updating:
            return "UTXO set:  updating… (may take ~2 min, press u)"
        if self._utxo_cache:
            now = time.time()
            txouts = self._utxo_cache.get("txouts", 0)
            disk = self._utxo_cache.get("disk_size", 0) / 1_000_000_000
            age_min = int((now - self._utxo_fetched_at) / 60)
            if self._prev_utxo_count is not None and txouts:
                delta = txouts - self._prev_utxo_count
            self._prev_utxo_count = txouts
            return f"UTXO set:  {txouts:,}  ({disk:.2f} GB)  [dim](cached {age_min}m, u=refresh)[/]"
        return "UTXO set:  [dim]press u to refresh (slow RPC)[/]"

    @work(thread=True, exclusive=True)
    def _fetch_utxo_background(self) -> None:
        btc_cfg: BitcoinConfig = self.config.bitcoin
        try:
            cache = self.cli.get_txoutset_info(timeout=btc_cfg.utxo_timeout)
            self._utxo_cache = cache
            self._utxo_fetched_at = time.time()
        except BitcoinCLIError:
            pass
        finally:
            self._utxo_updating = False
            self.app.call_from_thread(self._update_display)

    def _apply_border_alerts(self, *, changed: bool = False) -> None:
        self.remove_class("alert-peers", "alert-mempool")
        if self.alert_peers:
            self.add_class("alert-peers")
        elif self.alert_mempool:
            self.add_class("alert-mempool")
        if changed and (self.alert_peers or self.alert_mempool):
            self.animate("opacity", 0.6, duration=0.15)
            self.set_timer(0.15, lambda: self.animate("opacity", 1.0, duration=0.25))

    def _clear_alerts(self) -> None:
        self.alert_peers = False
        self.alert_mempool = False
        self.alert_message = ""
        self.remove_class("alert-peers", "alert-mempool")
