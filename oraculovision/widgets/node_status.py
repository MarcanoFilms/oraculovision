"""Node status widget — PyBlock-style dense Rich table."""

from __future__ import annotations

import time
from collections import deque

from rich.text import Text
from textual import work
from textual.widgets import Static

from oraculovision.config import AppConfig, BitcoinConfig
from oraculovision.node.client import BitcoinCLIError, NodeClient
from oraculovision.widgets.anim import diamond_meter, flowing_bar, pulse_dot, trend_arrow

_BARS = " ▁▂▃▄▅▆▇█"

_SYNC_FILL = "█"
_SYNC_EMPTY = "░"


def _sparkline_str(data: list[float], width: int = 10) -> str:
    if not data:
        return "─" * width
    max_v = max(data) or 1.0
    samples = list(data)[-width:]
    while len(samples) < width:
        samples.insert(0, 0.0)
    return "".join(_BARS[min(8, int(v / max_v * 8))] for v in samples)


def _sync_bar(pct: float, width: int = 20) -> str:
    filled = int(pct / 100 * width)
    return _SYNC_FILL * filled + _SYNC_EMPTY * (width - filled)


class NodeStatus(Static):
    """Dense Rich-table node status widget — PyBlock aesthetic."""

    DEFAULT_CSS = """
    NodeStatus {
        height: auto;
        max-height: 18;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        cli: NodeClient | None = None,
        config: AppConfig | None = None,
        **kwargs,
    ) -> None:
        # Initialize with loading text so Static never has None visual
        super().__init__(_build_loading(), **kwargs)
        self.config = config or AppConfig()
        self.cli = cli or NodeClient()
        self._utxo_cache: dict | None = None
        self._utxo_fetched_at: float = 0.0
        self._utxo_updating: bool = False
        self._prev_utxo_count: int | None = None
        self._chain_data: dict | None = None
        self._network_data: dict | None = None
        self._mempool_data: dict | None = None
        self._net_totals_data: dict | None = None
        self._peer_history: deque[float] = deque(maxlen=30)
        self._mempool_history: deque[float] = deque(maxlen=30)
        self.alert_peers: bool = False
        self.alert_mempool: bool = False
        self.alert_message: str = ""
        self._anim_frame: int = 0
        self.border_title = "🛡 NODE STATUS"

    def on_mount(self) -> None:
        # Drive a gentle 2 fps animation; re-renders only cached data so a
        # stalled node never causes work or crashes.
        self.set_interval(0.5, self._tick)

    def _tick(self) -> None:
        self._anim_frame += 1
        self._do_render()

    def refresh_utxo(self) -> None:
        """Fetch UTXO set in background (triggered by u key)."""
        if self._utxo_updating:
            return
        self._utxo_updating = True
        self._do_render()
        self._fetch_utxo_background()

    def refresh_data(self) -> None:
        """Fetch all node data and update display."""
        alerts = self.config.alerts

        try:
            self._chain_data = self.cli.get_blockchain_info()
            self._network_data = self.cli.get_network_info()
            self._mempool_data = self.cli.get_mempool_info()
            try:
                self._net_totals_data = self.cli.get_net_totals()
            except Exception:
                self._net_totals_data = {}
        except BitcoinCLIError as exc:
            msg = str(exc)
            if exc.hint:
                msg += f"  → {exc.hint}"
            self.update(_build_error(msg))
            self._clear_alerts()
            return

        # Gather metrics for sparklines
        peers = self._network_data.get("connections", 0)
        mempool_tx = self._mempool_data.get("size", 0)
        self._peer_history.append(float(peers))
        self._mempool_history.append(float(mempool_tx))

        # Compute alert states
        self.alert_peers = peers < alerts.min_peers
        mempool_mb = self._mempool_data.get("bytes", 0) / 1_000_000
        self.alert_mempool = (
            mempool_mb >= alerts.mempool_congested_mb
            or mempool_tx >= alerts.mempool_congested_tx
        )
        self._apply_border_alerts()

        alerts_msgs: list[str] = []
        if self.alert_peers:
            alerts_msgs.append(f"⚠ Low peers ({peers} < {alerts.min_peers})")
        if self.alert_mempool:
            alerts_msgs.append(
                f"⚠ Congested mempool ({mempool_tx:,} tx / {mempool_mb:.1f} MB)"
            )
        self.alert_message = "  ·  ".join(alerts_msgs)

        self._do_render()

    def _do_render(self) -> None:
        if not self._chain_data or not self._network_data or not self._mempool_data:
            return
        self.update(self._build_rich_text())

    def _build_rich_text(self) -> Text:
        chain = self._chain_data
        network = self._network_data
        mempool = self._mempool_data
        alerts = self.config.alerts

        blocks = chain.get("blocks", 0)
        headers = chain.get("headers", 0)
        progress = chain.get("verificationprogress", 0) * 100
        ibd = chain.get("initialblockdownload", False)
        pruned = chain.get("pruned", False)
        subver = network.get("subversion", "unknown")
        peers = network.get("connections", 0)
        mempool_tx = mempool.get("size", 0)
        mempool_mb = mempool.get("bytes", 0) / 1_000_000
        net_totals = self._net_totals_data or {}
        upload_bytes = net_totals.get("totalbytessent", 0)
        download_bytes = net_totals.get("totalbytesrecv", 0)

        is_knots = "knots" in subver.lower()
        is_synced = not ibd and progress > 99.9
        archival = "[ARCHIVAL]" if not pruned else "[PRUNED]"

        # Build version label
        ver_display = subver.strip("/")
        if len(ver_display) > 28:
            ver_display = ver_display[:26] + "…"

        # Sync bar
        sync_bar = flowing_bar(progress, self._anim_frame, 20)
        peer_spark = _sparkline_str(list(self._peer_history), width=10)
        mempool_spark = _sparkline_str(list(self._mempool_history), width=10)

        # Traffic formatting
        def fmt_bytes(b: int) -> str:
            if b >= 1_000_000_000:
                return f"{b / 1_000_000_000:.1f} GB"
            return f"{b / 1_000_000:.1f} MB"

        # Live indicator
        dot_color = "green" if is_synced else "yellow"
        live_label = "LIVE" if is_synced else "SYNC"

        t = Text()

        # Header line
        t.append(f"{pulse_dot(self._anim_frame)} ", style=f"bold {dot_color}")
        t.append(f"{live_label}  ", style=f"bold {dot_color}")
        t.append(ver_display, style="bold white")
        t.append("  ", style="")
        t.append(archival, style="dim cyan")
        t.append("\n")

        # Sync line
        t.append("  Sync    ", style="dim")
        t.append(f"{progress:.2f}%", style="bold cyan")
        t.append("  ", style="")
        t.append(sync_bar, style="green" if is_synced else "yellow")
        t.append("  ", style="")
        t.append(f"#{blocks:,}", style="bold white")
        t.append(f" / #{headers:,}", style="dim")
        t.append("\n")

        # Peers line — diamond capacity meter + trend arrow
        peer_ok = peers >= alerts.min_peers
        meter = diamond_meter(peers, capacity=10, width=10)
        if len(self._peer_history) >= 2:
            peer_trend = trend_arrow(self._peer_history[-1] - self._peer_history[-2])
        else:
            peer_trend = "→"
        t.append("  Peers   ", style="dim")
        t.append(str(peers), style="bold green" if peer_ok else "bold red")
        t.append(f" {peer_trend}  ", style="green" if peer_ok else "red")
        t.append(meter, style="cyan" if peer_ok else "red")
        t.append(f"  (min {alerts.min_peers})", style="dim")
        t.append("\n")

        # Mempool line
        mp_ok = not self.alert_mempool
        t.append("  Mempool ", style="dim")
        t.append(f"{mempool_tx:,} tx", style="bold cyan" if mp_ok else "bold yellow")
        t.append(f"  {mempool_mb:.2f} MB", style="white")
        t.append("  ", style="")
        t.append(mempool_spark, style="cyan" if mp_ok else "yellow")
        t.append("\n")

        # UTXO line
        t.append("  UTXO   ", style="dim")
        t.append(self._utxo_line_rich())
        t.append("\n")

        # Traffic line
        t.append("  Traffic ", style="dim")
        t.append("↑ ", style="dim")
        t.append(fmt_bytes(upload_bytes), style="cyan")
        t.append("  ↓ ", style="dim")
        t.append(fmt_bytes(download_bytes), style="cyan")
        t.append("  since uptime", style="dim")

        return t

    def _utxo_line_rich(self) -> Text:
        t = Text()
        if self._utxo_updating:
            t.append("updating… (may take ~2 min)", style="yellow")
            t.append("  [press u]", style="dim")
            return t

        if self._utxo_cache:
            now = time.time()
            txouts = self._utxo_cache.get("txouts", 0)
            disk = self._utxo_cache.get("disk_size", 0) / 1_000_000_000
            age_min = int((now - self._utxo_fetched_at) / 60)
            growth = ""
            if self._prev_utxo_count is not None and txouts:
                delta = txouts - self._prev_utxo_count
                if delta != 0:
                    growth = f"  ({delta:+,})"
            self._prev_utxo_count = txouts
            t.append(f"{txouts:,}", style="bold cyan")
            t.append(" outputs", style="dim")
            t.append(f"  ({disk:.2f} GB)", style="white")
            if growth:
                t.append(growth, style="green" if delta > 0 else "red")
            t.append(f"  [dim](cached {age_min}m, u=refresh)[/dim]", style="dim")
            return t

        t.append("press ", style="dim")
        t.append("u", style="bold cyan")
        t.append(" to refresh (slow RPC)", style="dim")
        return t

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
            self.app.call_from_thread(self._do_render)

    def _apply_border_alerts(self) -> None:
        self.remove_class("alert-peers", "alert-mempool")
        if self.alert_peers:
            self.add_class("alert-peers")
        elif self.alert_mempool:
            self.add_class("alert-mempool")

    def _clear_alerts(self) -> None:
        self.alert_peers = False
        self.alert_mempool = False
        self.alert_message = ""
        self.remove_class("alert-peers", "alert-mempool")


def _build_loading() -> Text:
    t = Text()
    t.append("● ", style="dim yellow")
    t.append("Connecting to node…", style="dim")
    return t


def _build_error(msg: str) -> Text:
    t = Text()
    t.append("● ", style="bold red")
    t.append("NODE ERROR  ", style="bold red")
    t.append(msg, style="red")
    return t
