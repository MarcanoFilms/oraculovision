"""Full help screen with keyboard shortcuts."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static

HELP_TEXT = """
[bold #ffd700]ORACULOVISION — HELP[/]

[bold]Screen navigation (v2)[/]
  [yellow]1[/]     Dashboard — overview panels
  [yellow]2[/]     Policies — live policy + bitcoin.conf preview + simulation
  [yellow]3[/]     Mempool Glass — full template analysis
  [yellow]4[/]     Block Explorer — search blocks by height/hash
  [yellow]5[/]     Tx & Address Inspector — txid or address lookup
  [yellow]6[/]     Spam & Health — chain health score + trends
  [yellow]7[/]     Mining — DATUM + Ocean panel
  [yellow]8[/]     Node Control — peer management (gated)
  [yellow]Tab[/]   Focus sidebar or panels

[bold]Global actions[/]
  [yellow]r[/]     Refresh current screen (light RPCs + cached template)
  [yellow]t[/]     Refresh Block Template + Mempool Glass (full GBT)
  [yellow]u[/]     Refresh UTXO set stats (slow RPC, ~2 min, background)
  [yellow]e[/]     Export audit trail (JSON/CSV) from Health, Explorer, or Tx Inspector
  [yellow]p[/]     Cycle node profile (local / remote RPC / SSH)
  [yellow]o[/]     Enter or change Ocean payout address
  [yellow]q[/]     Quit the dashboard
  [yellow]?[/]     Open/close this help screen

[bold]Dashboard[/]
  [yellow]x[/]     Toggle expert panels (BIP-110, DATUM, charts)
  [yellow]r[/]     Refresh  ·  [yellow]t[/] template  ·  [yellow]u[/] utxo

[bold]Policies[/]
  [yellow]2[/]     Open Policies screen
  [dim]Left: live Knots RPC policy + bitcoin.conf adjustment preview[/]
  [dim]Right: template simulation presets (↑↓ for impact detail)[/]
  [dim]Preview is read-only — edit bitcoin.conf and restart Knots to apply[/]

[bold]Mempool Glass[/]
  [yellow]↑ ↓[/]   Select transaction in template table
  [yellow]c[/]     Copy full txid to clipboard
  [yellow]i[/]     Inspect selected tx in Tx Inspector
  [yellow]Enter[/]  Same as [yellow]i[/] — open in Tx Inspector
  [yellow]f[/]     Cycle category filter (all → economic → … → spam)

[bold]Block Explorer[/]
  [yellow]/[/]     Focus search (Explorer, Tx Inspector, or Control)
  [yellow]↑ ↓[/]   Navigate the block table
  [yellow]Enter[/] Open block detail (expand flagged transactions)
  [yellow]i[/]     Inspect selected flagged tx in Tx Inspector
  [yellow]t[/]     Copy selected txid  ·  [yellow]c[/] copy block hash

[bold]Tx & Address Inspector[/]
  [yellow]/[/]     Focus search (txid or address)
  [yellow]Enter[/]  Inspect txid (64 hex) or address (bc1… / 1… / 3…)
  [yellow]a[/]     Drill into address from loaded tx (UTXO balance)
  [yellow]c[/]     Copy txid or address
  [dim]Tx view: inputs/outputs, BTC amounts, fees, senders/recipients[/]
  [dim]Address view: UTXO balance via scantxoutset (confirmed only)[/]
  [dim]Pruned nodes: use Block Explorer → i for txs with block cache[/]

[bold]Spam & Health[/]
  [yellow]r[/]     Rescan recent blocks (uses chain_health.scan_blocks)
  [yellow]Enter[/]  Open detail for worst block in table

[bold]Node Control[/] (requires read_only = false for writes)
  [yellow]d[/]     Disconnect selected peer
  [yellow]b[/]     Ban selected peer (24h)
  [yellow]c[/]     Clear all bans
  [yellow]m[/]     Set mempool limit (MB, uses input field)
  [yellow]Y[/]     Confirm control action  ·  [yellow]N[/] cancel

[bold]Block detail modal[/]
  [yellow]↑ ↓[/]   Select flagged transaction
  [yellow]i[/]     Inspect selected tx in Tx Inspector
  [yellow]t[/]     Copy selected txid  ·  [yellow]c[/] copy block hash
  [yellow]Esc[/]   Close modal

[bold]Ocean address modal[/]
  [yellow]Enter[/]  Apply address (empty clears session address)
  [yellow]Esc[/]    Cancel without changes

[bold]Screens[/]
  [cyan]Dashboard[/]         Sovereignty brief, metric cards, expert panels
  [cyan]Policies[/]          Live Knots policy snapshot + template simulation
  [cyan]Mempool Glass[/]     Full GBT composition + tx table
  [cyan]Block Explorer[/]    Search blocks, spam scores, violation detail
  [cyan]Tx & Address[/]      Flow, fees, addresses, UTXO balance lookup
  [cyan]Spam & Health[/]      Health score, spam trend chart, worst blocks
  [cyan]Mining[/]            DATUM gateway + Ocean account stats
  [cyan]Node Control[/]      Peers, bans, mempool limit (gated writes)

[bold]Control safety[/]
  Node write actions require confirmation and [control] read_only = false
  in config.toml (default: read-only mode). Dangerous RPCs are allowlisted.

[bold]Visual alerts[/]
  [red]Red[/] border       — low peers or recent spam block
  [yellow]Yellow[/] border — congested mempool

[bold]Performance notes[/]
  Auto-refresh skips slow RPCs: UTXO set ([yellow]u[/] only),
  Block Template (use [yellow]t[/] or 30s cache), BIP-110 blocks
  (only when chain tip changes), Ocean blocks-found (5 min cache).

[bold]Configuration[/]
  config.toml in the project or ~/.config/oraculovision/config.toml
  ORACULOVISION_CONFIG for a custom path

[dim]Don't Trust, Verify — BIP-110 + Knots + DATUM[/]
"""


class HelpScreen(ModalScreen):
    """Modal help screen."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-dialog {
        width: 72;
        height: 85%;
        padding: 1 2;
    }
    #help-content {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="help-dialog"):
            yield Static(HELP_TEXT, id="help-content")
        yield Footer()

    def action_dismiss(self) -> None:
        self.dismiss()