"""Sovereignty status snapshot for the status bar and dashboard brief."""

from __future__ import annotations

from dataclasses import dataclass

from oraculovision.config import AppConfig
from oraculovision.node.client import BitcoinCLIError, NodeClient


@dataclass
class SovereigntyBrief:
    """Auto-generated sovereignty summary for the dashboard."""

    text: str
    severity: str = "ok"
    alerts: list[str] | None = None

    def __post_init__(self) -> None:
        if self.alerts is None:
            self.alerts = []


@dataclass
class SovereigntySnapshot:
    knots: bool = False
    client_label: str = "Bitcoin"
    chain_height: int = 0
    sync_pct: float = 0.0
    peer_count: int = 0
    control_mode: str = "READ-ONLY"
    mempool_tx: int = 0
    mempool_mb: float = 0.0
    pruned: bool = False
    prune_height: int = 0
    tx_index: bool = False
    network_hashrate_ehs: float = 0.0
    error: str | None = None

    @property
    def is_synced(self) -> bool:
        return self.sync_pct >= 99.9 and not self.error


def fetch_sovereignty_snapshot(
    client: NodeClient,
    config: AppConfig,
) -> SovereigntySnapshot:
    """Collect lightweight node sovereignty metrics for the status bar."""
    snap = SovereigntySnapshot(
        control_mode="READ-ONLY" if config.control.read_only else "CONTROL",
    )
    try:
        chain = client.get_blockchain_info()
        network = client.get_network_info()
        mempool = client.get_mempool_info()
    except BitcoinCLIError as exc:
        snap.error = str(exc)
        return snap

    subversion = str(network.get("subversion", ""))
    snap.knots = "knots" in subversion.lower()
    snap.client_label = "KNOTS" if snap.knots else "CORE"

    snap.chain_height = int(chain.get("blocks", 0))
    headers = int(chain.get("headers", snap.chain_height))
    if headers > 0:
        snap.sync_pct = min(100.0, (snap.chain_height / headers) * 100)
    else:
        snap.sync_pct = 100.0 if not chain.get("initialblockdownload") else 0.0

    snap.peer_count = int(network.get("connections", 0))
    snap.mempool_tx = int(mempool.get("size", 0))
    snap.mempool_mb = float(mempool.get("bytes", 0)) / 1_000_000
    snap.pruned = bool(chain.get("pruned"))
    snap.prune_height = int(chain.get("pruneheight", 0) or 0)

    try:
        index_info = client.get_index_info()
        snap.tx_index = bool(index_info.get("txindex", {}).get("synced", False))
    except Exception:
        snap.tx_index = False

    try:
        mining = client.call("getmininginfo")
        snap.network_hashrate_ehs = float(mining.get("networkhashps", 0.0)) / 1e18
    except Exception:
        snap.network_hashrate_ehs = 0.0

    return snap


def build_sovereignty_brief(
    snap: SovereigntySnapshot,
    config: AppConfig,
    *,
    template_spam_pct: float = 0.0,
    tip_spam_score: int | None = None,
    tip_miner: str = "",
) -> SovereigntyBrief:
    """Compose a plain-language sovereignty brief from live node metrics."""
    alerts: list[str] = []
    lines: list[str] = []

    if snap.error:
        return SovereigntyBrief(
            text=f"[red]Node unreachable: {snap.error}[/]",
            severity="danger",
            alerts=[snap.error],
        )

    client = snap.client_label
    if snap.knots:
        lines.append(
            f"[bold green]{client}[/] node enforcing local policy — "
            "BIP-110 rules applied before relay."
        )
    else:
        lines.append(
            f"[yellow]{client}[/] detected — Knots recommended for full "
            "BIP-110 + spam policy control."
        )
        alerts.append("Non-Knots client")

    if snap.is_synced:
        lines.append(
            f"Chain at [bold]#{snap.chain_height:,}[/] — "
            f"[green]{snap.sync_pct:.1f}% synced[/]."
        )
    else:
        lines.append(
            f"Syncing [bold]#{snap.chain_height:,}[/] — "
            f"[yellow]{snap.sync_pct:.1f}%[/] (headers catching up)."
        )
        alerts.append("Node still syncing")

    min_peers = config.alerts.min_peers
    if snap.peer_count >= min_peers:
        lines.append(
            f"[green]{snap.peer_count} peers[/] connected — "
            "network view is healthy."
        )
    else:
        lines.append(
            f"[red]{snap.peer_count} peers[/] — below minimum ({min_peers}). "
            "Connectivity may be degraded."
        )
        alerts.append(f"Low peers ({snap.peer_count})")

    mempool_alert = config.alerts.mempool_congested_tx
    if snap.mempool_tx >= mempool_alert:
        lines.append(
            f"Mempool [yellow]{snap.mempool_tx:,} tx[/] "
            f"({snap.mempool_mb:.1f} MB) — elevated congestion."
        )
        alerts.append("Congested mempool")
    else:
        lines.append(
            f"Mempool {snap.mempool_tx:,} tx ({snap.mempool_mb:.1f} MB)."
        )

    if template_spam_pct > 30:
        lines.append(
            f"Next block template is [red bold]{template_spam_pct:.0f}% spam[/] "
            "by weight — miners may propagate dirty blocks."
        )
        alerts.append(f"Dirty template ({template_spam_pct:.0f}% spam)")
    elif template_spam_pct > 15:
        lines.append(
            f"Template spam weight [yellow]{template_spam_pct:.0f}%[/] — "
            "worth monitoring."
        )

    if tip_spam_score is not None and tip_spam_score >= 50:
        miner = f" ({tip_miner[:28]})" if tip_miner else ""
        lines.append(
            f"Chain tip block spam score [red]{tip_spam_score}/100[/]{miner}."
        )
        alerts.append(f"Dirty tip block (spam {tip_spam_score})")

    mode = snap.control_mode
    if mode == "READ-ONLY":
        lines.append("[dim]Control: READ-ONLY — peer writes disabled.[/]")
    else:
        lines.append("[yellow]Control: WRITE ENABLED — peer actions available.[/]")

    severity = "ok"
    if any(
        a.startswith(("Node", "Low peers", "Dirty template", "Dirty tip"))
        for a in alerts
    ):
        severity = "danger"
    elif alerts:
        severity = "warn"

    return SovereigntyBrief(
        text="\n".join(lines),
        severity=severity,
        alerts=alerts,
    )