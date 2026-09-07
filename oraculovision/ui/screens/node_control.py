"""Node Control — peer management and policy controls (gated)."""

from __future__ import annotations

import time

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Input, Label, Static

from oraculovision.config import AppConfig
from oraculovision.node.client import BitcoinCLIError, NodeClient
from oraculovision.node.control.actions import ControlAction
from oraculovision.node.control.gate import ControlGate, ControlResult
from oraculovision.node.peers import (
    peer_address,
    peer_ban_subnet,
    peer_client,
    peer_direction,
    peer_height,
)
from oraculovision.ui.control_runner import run_control_action
from oraculovision.ui.screens.base import BaseScreen


def _mode_banner(read_only: bool) -> str:
    if read_only:
        return (
            "[yellow bold]READ-ONLY MODE[/] — control disabled. "
            "Set [control] read_only = false in config.toml to enable."
        )
    return "[red bold]CONTROL ENABLED[/] — actions require confirmation (Y/N)."


class NodeControlScreen(BaseScreen):
    """Peer ban/disconnect and mempool limit controls."""

    screen_id = "node_control"

    DEFAULT_CSS = """
    NodeControlScreen {
        layout: vertical;
    }
    NodeControlScreen #control-header {
        height: auto;
        text-style: bold;
        padding: 0 1;
    }
    NodeControlScreen #control-mode {
        height: auto;
        padding: 0 1 1 1;
    }
    NodeControlScreen #control-feedback {
        height: auto;
        padding: 0 1;
        min-height: 1;
    }
    NodeControlScreen #control-hint {
        height: auto;
        padding: 0 1;
    }
    NodeControlScreen #control-body {
        height: 1fr;
        padding: 0 1;
    }
    NodeControlScreen #peers-panel {
        width: 65%;
        height: 100%;
        padding: 0 1;
    }
    NodeControlScreen #bans-panel {
        width: 35%;
        height: 100%;
        padding-left: 1;
    }
    NodeControlScreen #peers-table {
        height: 1fr;
    }
    NodeControlScreen #bans-table {
        height: 1fr;
    }
    NodeControlScreen .panel-title {
        text-style: bold;
        padding: 1 0 0 0;
    }
    NodeControlScreen #mempool-row {
        height: auto;
        padding: 1 0 0 0;
    }
    NodeControlScreen #mempool-limit-input {
        width: 1fr;
    }
    NodeControlScreen .field-label {
        width: auto;
        padding-right: 1;
        content-align: center middle;
    }
    """

    def __init__(
        self,
        client: NodeClient,
        gate: ControlGate,
        config: AppConfig,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.gate = gate
        self.config = config
        self._peers: list[dict] = []
        self._selected: dict | None = None
        self._default_mempool_mb: int = 300

    def compose(self) -> ComposeResult:
        yield Label("NODE CONTROL", id="control-header")
        yield Static(_mode_banner(self.config.control.read_only), id="control-mode")
        yield Static("", id="control-feedback")
        yield Label(
            "d disconnect · b ban 24h · c clear bans · m set mempool limit",
            id="control-hint",
        )
        with Horizontal(id="control-body"):
            with Vertical(id="peers-panel"):
                yield Label("CONNECTED PEERS", classes="panel-title")
                yield DataTable(id="peers-table", zebra_stripes=True, cursor_type="row")
                with Horizontal(id="mempool-row"):
                    yield Label("Mempool MB:", classes="field-label")
                    yield Input(placeholder="300", id="mempool-limit-input")
            with Vertical(id="bans-panel"):
                yield Label("ACTIVE BANS", classes="panel-title")
                yield DataTable(id="bans-table", zebra_stripes=True)
        yield Label(
            "↑↓ select peer · all writes require Y confirmation",
            id="control-hint-bottom",
        )

    def on_mount(self) -> None:
        peers = self.query_one("#peers-table", DataTable)
        peers.add_columns("Address", "Dir", "Client", "Height", "Ping")
        bans = self.query_one("#bans-table", DataTable)
        bans.add_columns("Subnet", "Until")
        self.query_one("#control-feedback", Static).update(
            "Select this screen to load peers from your node."
        )

    def action_focus_search(self) -> None:
        self.query_one("#mempool-limit-input", Input).focus()

    def refresh_screen(self, *, force: bool = False) -> None:
        self.query_one("#control-mode", Static).update(
            _mode_banner(self.config.control.read_only)
        )
        self.query_one("#control-feedback", Static).update(
            "[dim]Loading peers and bans…[/]"
        )
        self._load_data()

    def action_disconnect_peer(self) -> None:
        peer = self._selected
        if not peer:
            self._feedback("[yellow]Select a peer first[/]")
            return
        addr = peer_address(peer)
        if not addr:
            self._feedback("[red]Peer has no address[/]")
            return
        self._run_control(ControlAction.disconnect_peer(addr))

    def action_ban_peer(self) -> None:
        peer = self._selected
        if not peer:
            self._feedback("[yellow]Select a peer first[/]")
            return
        addr = peer_address(peer)
        try:
            subnet = peer_ban_subnet(addr)
        except ValueError as exc:
            self._feedback(f"[red]{exc}[/]")
            return
        self._run_control(ControlAction.ban_peer(subnet))

    def action_clear_bans(self) -> None:
        self._run_control(ControlAction.clear_bans())

    def action_set_mempool_limit(self) -> None:
        raw = self.query_one("#mempool-limit-input", Input).value.strip()
        if not raw:
            raw = str(self._default_mempool_mb)
        try:
            limit_mb = int(raw)
            if limit_mb < 1:
                raise ValueError
        except ValueError:
            self._feedback("[red]Enter a valid mempool limit in MB (e.g. 300)[/]")
            return
        self._run_control(ControlAction.set_mempool_limit(limit_mb))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "peers-table":
            return
        row_idx = event.cursor_row
        if row_idx is None and event.row_key is not None:
            try:
                row_idx = int(str(event.row_key.value))
            except ValueError:
                row_idx = None
        if row_idx is None or row_idx >= len(self._peers):
            return
        self._selected = self._peers[row_idx]

    def _run_control(self, action: ControlAction) -> None:
        run_control_action(
            self.app,
            self.gate,
            action,
            on_blocked=self._feedback,
            on_cancelled=lambda: self._feedback("[dim]Action cancelled[/]"),
            on_complete=self._on_control_complete,
        )

    def _on_control_complete(self, result: ControlResult) -> None:
        if result.success:
            self._feedback(f"[green]{result.message}[/]")
            self.refresh_screen(force=True)
        else:
            self._feedback(f"[red]{result.message}[/]")

    def _feedback(self, message: str) -> None:
        self.query_one("#control-feedback", Static).update(message)

    @work(thread=True, exclusive=True)
    def _load_data(self) -> None:
        try:
            peers = self.client.get_peer_info()
            banned = self.client.list_banned()
            mempool = self.client.get_mempool_info()
            max_mb = int(mempool.get("maxmempool", 300))
            self.app.call_from_thread(self._update_ui, peers, banned, max_mb)
        except BitcoinCLIError as exc:
            msg = str(exc)
            if exc.hint:
                msg += f" → {exc.hint}"
            self.app.call_from_thread(self._feedback, f"[red]{msg}[/]")

    def _update_ui(
        self,
        peers: list[dict],
        banned: list[dict],
        max_mb: int,
    ) -> None:
        self._peers = peers
        self._default_mempool_mb = max_mb
        self.query_one("#mempool-limit-input", Input).value = str(max_mb)

        peers_table = self.query_one("#peers-table", DataTable)
        peers_table.clear()
        for i, peer in enumerate(peers):
            addr = peer_address(peer)[:28]
            ping = peer.get("pingtime")
            ping_s = f"{float(ping):.2f}s" if ping is not None else "—"
            peers_table.add_row(
                addr,
                peer_direction(peer),
                peer_client(peer),
                peer_height(peer),
                ping_s,
                key=str(i),
            )

        bans_table = self.query_one("#bans-table", DataTable)
        bans_table.clear()
        now = int(time.time())
        for entry in banned:
            addr = str(entry.get("address", "?"))
            until = int(entry.get("banned_until", 0))
            if until > 0:
                remaining = max(0, until - now)
                hours = remaining // 3600
                until_s = f"{hours}h left" if hours else "<1h"
            else:
                until_s = "permanent"
            bans_table.add_row(addr[:22], until_s)

        self._selected = peers[0] if peers else None
        self._feedback(
            f"[green]Loaded {len(peers)} peer(s), {len(banned)} ban(s)[/]  ·  "
            f"mempool limit {max_mb} MB"
        )