"""Persistent sovereignty status bar (PyBlock-inspired)."""

from __future__ import annotations

from textual import work
from textual.reactive import reactive
from textual.widgets import Static
from rich.text import Text

from oraculovision.config import AppConfig
from oraculovision.node.client import BitcoinCLIError, NodeClient
from oraculovision.presentation.sovereignty import (
    SovereigntySnapshot,
    fetch_sovereignty_snapshot,
)


class SovereignStatusBar(Static):
    """Top bar: client, height, sync, peers, mempool, control mode."""

    snapshot: reactive[SovereigntySnapshot | None] = reactive(None)

    def __init__(
        self,
        client: NodeClient,
        config: AppConfig,
        *,
        profile_name: str = "local",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.config = config
        self.profile_name = profile_name

    def set_profile_name(self, name: str) -> None:
        self.profile_name = name
        self.refresh()

    def on_mount(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        self._fetch_snapshot()

    def render(self) -> Text:
        snap = self.snapshot
        if snap is None:
            return Text(" Loading sovereignty status… ", style="dim")

        if snap.error:
            text = Text()
            text.append(" NODE ", style="bold rgb(255,80,80) on rgb(30,20,20)")
            text.append(f" {snap.error[:60]} ", style="rgb(255,80,80) on rgb(20,20,24)")
            return text

        # ── Line 1: header — height (left) · BITCOIN KNOTS (center) · network security (right)
        width = self.size.width or 80
        client_name = "BITCOIN KNOTS" if snap.knots else "BITCOIN CORE"
        title = f"₿ {client_name}"
        left_s = f"#{snap.chain_height:,}"
        if snap.network_hashrate_ehs >= 1.0:
            net_s = f"Network Security {snap.network_hashrate_ehs:.0f} EH/s"
        elif snap.network_hashrate_ehs > 0:
            net_s = f"Network Security {snap.network_hashrate_ehs * 1000:.0f} PH/s"
        else:
            net_s = "Network Security —"
        right_s = f"🛡 {net_s}"

        gap = width - len(left_s) - len(title) - len(right_s) - 2
        if gap < 2:
            gap = 2
        left_gap = gap // 2
        right_gap = gap - left_gap

        header = Text()
        header.append(f" {left_s}", style="bold rgb(0,220,255) on rgb(20,20,24)")
        header.append(" " * left_gap, style="on rgb(20,20,24)")
        header.append(title, style="bold rgb(247,147,26) on rgb(20,20,24)")
        header.append(" " * right_gap, style="on rgb(20,20,24)")
        header.append(f"{right_s} ", style="bold rgb(61,214,140) on rgb(20,20,24)")
        header.append("\n")

        # ── Line 2: existing dense badge strip
        text = Text()
        text.append_text(header)
        client_color = "bold rgb(255,102,0)" if snap.knots else "bold yellow"
        text.append(f" {snap.client_label} ", style=f"{client_color} on rgb(30,30,30)")
        text.append("  ", style="on rgb(20,20,24)")
        text.append(" #", style="dim on rgb(20,20,24)")
        text.append(f"{snap.chain_height:,} ", style="bold white on rgb(20,20,24)")
        sync_style = "bold rgb(61,214,140)" if snap.is_synced else "bold yellow"
        text.append(f" {snap.sync_pct:.1f}% sync ", style=f"{sync_style} on rgb(20,20,24)")
        peer_style = (
            "bold rgb(61,214,140)"
            if snap.peer_count >= self.config.alerts.min_peers
            else "bold rgb(255,80,80)"
        )
        text.append(f" {snap.peer_count} peers ", style=f"{peer_style} on rgb(20,20,24)")
        text.append(
            f" {snap.mempool_tx:,} mempool ",
            style="bold rgb(0,220,255) on rgb(20,20,24)",
        )
        mode_style = (
            "bold dim white"
            if snap.control_mode == "READ-ONLY"
            else "bold rgb(255,200,0)"
        )
        text.append(f" {snap.control_mode} ", style=f"{mode_style} on rgb(20,20,24)")
        text.append(
            f" {self.profile_name} ",
            style="bold rgb(0,220,255) on rgb(20,20,24)",
        )
        if snap.pruned:
            text.append(
                f" PRUNED #{snap.prune_height:,} ",
                style="bold yellow on rgb(20,20,24)",
            )
        elif snap.tx_index:
            text.append(
                " ARCHIVAL ",
                style="bold rgb(61,214,140) on rgb(20,20,24)",
            )
        return text

    def watch_snapshot(self, snap: SovereigntySnapshot | None) -> None:
        if snap and snap.error:
            self.add_class("-alert")
        else:
            self.remove_class("-alert")

    @work(thread=True, exclusive=True)
    def _fetch_snapshot(self) -> None:
        try:
            snap = fetch_sovereignty_snapshot(self.client, self.config)
            self.app.call_from_thread(self._set_snapshot, snap)
        except BitcoinCLIError as exc:
            self.app.call_from_thread(
                self._set_snapshot,
                SovereigntySnapshot(error=str(exc)),
            )

    def _set_snapshot(self, snap: SovereigntySnapshot) -> None:
        self.snapshot = snap