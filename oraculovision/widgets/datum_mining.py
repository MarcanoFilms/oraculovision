"""DATUM mining panel widget."""

from __future__ import annotations

import time

from textual import work
from textual.app import ComposeResult
from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual.widgets import Static

from oraculovision.analysis.profitability import compute_profitability
from oraculovision.config import AppConfig
from oraculovision.services.worker_monitor import WorkerMonitor
from oraculovision.widgets.anim import energy_glyph, trend_arrow
from oraculovision.data.datum import DatumJob, DatumStatus, fetch_datum_job, fetch_datum_status
from oraculovision.data.pyblock import fetch_community_blocks, fetch_datum_network
from oraculovision.widgets.treemap import render_block_treemap
from oraculovision.data.ocean import (
    OceanAccountStats,
    OceanEarnings,
    fetch_ocean_account_stats,
    format_ocean_address,
    invalidate_ocean_cache,
)

class DatumMining(Static):
    """Shows DATUM gateway status, workers, hashrate, and shares."""

    DEFAULT_CSS = """
    DatumMining {
        height: auto;
        min-height: 14;
        padding: 1 2;
    }
    DatumMining #datum-content {
        height: auto;
    }
    """

    def __init__(
        self, config: AppConfig | None = None, *, show_treemap: bool = False, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.config = config or AppConfig()
        self.border_title = "⚡ DATUM MINING"
        self._session_ocean_address: str | None = None
        self._anim_frame: int = 0
        self._gateway_active: bool = False
        self._prev_shares: int | None = None
        # Tracks worker online/offline transitions to raise toast notifications.
        self._worker_monitor = WorkerMonitor()
        # The block-template treemap only renders on the dedicated mining
        # screen; on the compact dashboard it would crowd the gateway info.
        self._show_treemap = show_treemap

    @property
    def active_ocean_address(self) -> str:
        """Session override, else config.toml [ocean].address."""
        if self._session_ocean_address is not None:
            return self._session_ocean_address
        return self.config.ocean.address

    def set_ocean_address(self, address: str) -> None:
        """Set session Ocean address (empty string hides the section)."""
        previous = self.active_ocean_address
        self._session_ocean_address = address.strip()
        if previous and previous != self._session_ocean_address:
            invalidate_ocean_cache(previous)
        if self._session_ocean_address:
            invalidate_ocean_cache(self._session_ocean_address)
        # Don't replay the new account's workers as "came online".
        self._worker_monitor.reset()

    def on_mount(self) -> None:
        self.set_interval(0.5, self._tick_title)

    def _tick_title(self) -> None:
        self._anim_frame += 1
        glyph = energy_glyph(self._anim_frame, active=self._gateway_active)
        self.border_title = f"{glyph} DATUM MINING"

    def compose(self) -> ComposeResult:
        yield Static("Querying DATUM...", id="datum-content", classes="datum-metric")

    def _render_job_lines(self, job: DatumJob) -> list[str]:
        if not job.available:
            return ["", "[bold #ffd700]⛏  CURRENT JOB[/]", "  [dim]No active stratum job[/]"]

        prev = job.prev_block_hash
        if len(prev) > 20:
            prev = f"{prev[:16]}…"

        target = job.target[:24] + "…" if len(job.target) > 24 else job.target
        lines = [
            "",
            "[bold #ffd700]⛏  ──── CURRENT JOB ────[/]",
            f"  🆔 Job ID     [white]{job.job_id}[/]",
            f"  📏 Height     [white]{job.height}[/]",
            f"  💰 Value      [#ffd700]{job.coinbase_value_btc}[/]",
            f"  ⛓  Prev block [dim]{prev}[/]",
            f"  🎯 Target     [dim]{target}[/]",
            f"  🧮 Difficulty [white]{job.difficulty}[/]",
            f"  📦 Txs        {job.tx_count}  [dim]wt {job.weight}  sz {job.size}[/]",
            f"  🔖 Version    {job.version}  [dim]bits {job.bits}[/]",
            f"  ⏱  Time       [dim]{job.time_info}[/]",
            f"  📐 Limits     [dim]{job.limits}[/]",
        ]
        if job.coinbase_outputs:
            lines.append(f"  🪙 Coinbase   {job.coinbase_outputs} outputs [dim](/coinbaser)[/]")
        return lines

    def _shares_with_trend(self, accepted) -> str:
        """Format accepted shares with a +delta ↑ since the last refresh."""
        try:
            current = int(accepted)
        except (TypeError, ValueError):
            return str(accepted)
        suffix = ""
        if self._prev_shares is not None:
            delta = current - self._prev_shares
            if delta > 0:
                suffix = f"  [#3dd68c](+{delta} {trend_arrow(delta)})[/]"
        self._prev_shares = current
        return f"{current}{suffix}"

    def _render_datum_lines(self, status: DatumStatus) -> list[str]:
        workers = status.workers
        if status.worker_names:
            worker_detail = ", ".join(status.worker_names[:5])
            if len(status.worker_names) > 5:
                worker_detail += f" +{len(status.worker_names) - 5}"
        else:
            worker_detail = str(workers)

        shares_str = self._shares_with_trend(status.shares_accepted)
        state_lower = status.gateway_state.lower()
        state_emoji = "🟢" if ("ready" in state_lower or "connected" in state_lower) else (
            "🔴" if ("error" in state_lower or "not" in state_lower) else "🟡"
        )
        lines = [
            f"🛰  Gateway   {state_emoji} [bold]{status.gateway_state}[/]",
            f"👷 Workers   [white]{worker_detail}[/]",
            f"⚡ Hashrate  [bold #ffd700]{status.hashrate}[/]",
            f"✅ Shares    [#3dd68c]{shares_str}[/]",
            f"❌ Rejected  [#ff6b6b]{status.shares_rejected}[/]",
            f"🏊 Pool      [dim]{status.pool_host}[/]",
            f"🏷  Tag       [dim]{status.miner_tag}[/]",
            f"📦 Job h     {status.job_height}  [dim]uptime {status.uptime}[/]",
        ]
        if status.last_events:
            lines.append("[dim]— recent events —[/]")
            lines.extend(f"  [dim]· {e[:70]}[/]" for e in status.last_events[-4:])
        return lines

    def _render_ocean_prompt(self) -> list[str]:
        return [
            "",
            "[bold #00bcd4]🌊 ──── OCEAN ACCOUNT ────[/]",
            "  [dim]Press [/][bold]o[/][dim] to enter a payout address 💧[/]",
        ]

    @staticmethod
    def _btc_str_to_sats(btc_str: str) -> int | None:
        """Parse 'X.XXXXXXXX BTC' (with optional ~ prefix / suffix) into sats."""
        if not btc_str or btc_str == "—":
            return None
        token = btc_str.strip().lstrip("~").split()[0]
        try:
            return round(float(token) * 100_000_000)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _to_sats(cls, btc_str: str) -> str:
        """Convert an 'X.XXXXXXXX BTC' string into a grouped sats string."""
        sats = cls._btc_str_to_sats(btc_str)
        if sats is None:
            return btc_str if (btc_str and btc_str != "—") else "—"
        return f"{sats:,} sats"

    def _net_earnings_lines(self, earnings: OceanEarnings) -> list[str]:
        """Pool-fee / electricity-adjusted net figures (DeepSea-style).

        Returns an empty list unless [mining] economics are configured, so
        users who don't set them see no change.
        """
        mining = getattr(self.config, "mining", None)
        if mining is None:
            return []
        has_fee = mining.pool_fee_pct > 0
        has_power = mining.power_watts > 0 and mining.power_cost_per_kwh > 0
        if not (has_fee or has_power):
            return []
        gross = self._btc_str_to_sats(earnings.est_per_day)
        if not gross:
            return []

        p = compute_profitability(
            gross_sats_day=gross,
            power_watts=mining.power_watts,
            power_cost_per_kwh=mining.power_cost_per_kwh,
            pool_fee_pct=mining.pool_fee_pct,
            btc_price=mining.btc_price,
            currency=mining.currency,
        )
        lines = ["  [dim]────────────────[/]"]
        if has_fee:
            lines.append(
                f"  💵 Net/day   [bold #3dd68c]{p.net_sats_day:,} sats[/]"
                f"  [dim](fee {mining.pool_fee_pct:g}%)[/]"
            )
        if has_power:
            lines.append(
                f"  🔌 Power/day [#ff6600]{p.power_cost_day:.2f} {p.currency}[/]"
            )
            if p.has_fiat:
                sign = "+" if p.net_fiat_day >= 0 else ""
                color = "#3dd68c" if p.profitable else "#ff6b6b"
                lines.append(
                    f"  📈 Profit/day [bold {color}]{sign}{p.net_fiat_day:.2f} {p.currency}[/]"
                )
        return lines

    def _hashrate_column(self, stats: OceanAccountStats) -> list[str]:
        lines = ["[bold #00bcd4]📡 HASHRATE[/]"]
        for interval in stats.intervals:
            pct = interval.hash_pct if interval.hash_pct != "—" else "—"
            lines.append(f"  [bold]⏱ {interval.label}[/]")
            lines.append(f"   👤 You  [bold #3dd68c]{interval.miner_hashrate}[/]")
            lines.append(f"   🌊 Pool [#00bcd4]{interval.pool_hashrate}[/]")
            lines.append(f"   📊 [dim]{pct} · {interval.shares} sh[/]")
        lines.append(f"  🪟 TIDES  [white]{stats.tides_shares_pct}[/]")
        earnings = stats.earnings
        if earnings.workers_hashing:
            names = ", ".join(earnings.worker_names[:3])
            if len(earnings.worker_names) > 3:
                names += f" +{len(earnings.worker_names) - 3}"
            lines.append(f"  🔥 [bold #3dd68c]{earnings.workers_hashing}[/] hashing  [dim]{names}[/]")
        else:
            lines.append("  💤 [dim]0 hashing[/]")
        return lines

    def _sats_column(self, earnings: OceanEarnings) -> list[str]:
        lines = ["[bold #ffd700]💰 EARNINGS[/]"]
        if earnings.error:
            lines.append(f"  [yellow]⚠ {earnings.error}[/]")
            return lines
        lines.append(f"  📅 Per day   [bold #3dd68c]{self._to_sats(earnings.est_per_day)}[/]")
        lines.append(f"  ⏳ Unpaid    [bold #ffd700]{self._to_sats(earnings.unpaid)}[/]")

        # Payout progress bar - use API threshold if parsed and not default, otherwise config
        api_threshold = getattr(earnings, "payout_threshold", 0.0)
        threshold = api_threshold if api_threshold > 0 and api_threshold != 0.001 else getattr(self.config.ocean, "payout_threshold", 0.001)
        if threshold > 0:
            pct = (earnings.unpaid_value / threshold) * 100
            pct_cap = min(100.0, pct)
            filled = int(round(pct_cap / 100 * 12))
            bar = "█" * filled + "░" * (12 - filled)
            color = "#3dd68c" if pct >= 100 else "#ff6600"
            lines.append(f"  [bold {color}]Progress[/]  [[bold {color}]{bar}[/]] {pct:.1f}%")

        lines.append(f"  🎯 Next pay  [white]{self._to_sats(earnings.est_next_block)}[/]")
        lines.append(f"  🏆 Earned 30d [bold #ffd700]{self._to_sats(earnings.lifetime)}[/]")
        lines.extend(self._net_earnings_lines(earnings))
        lines.append("  [dim]────────────────[/]")

        # Blocks found by my worker (30d)
        your_blocks = f"[bold #3dd68c]{earnings.blocks_found_by_you}[/] [dim](30d)[/]"
        if earnings.blocks_found_by_you > 0 and earnings.found_worker_names:
            names = ", ".join(earnings.found_worker_names[:2])
            your_blocks += f"  [#3dd68c]🎉 {names}[/]"
        lines.append(f"  💎 Your blocks  {your_blocks}")

        # Blocks found by the pool (TIDES 30d window)
        lines.append(f"  🧱 Pool 30d  [bold]{earnings.blocks_earned_tides}[/] [dim](TIDES)[/]")
        return lines

    def _build_ocean_section(self, stats: OceanAccountStats) -> Group:
        parts: list = [
            Text.from_markup(""),
            Text.from_markup("[bold #00bcd4]🌊 ──── OCEAN ACCOUNT ────[/]"),
            Text.from_markup(
                f"  📍 [white]{format_ocean_address(stats.address)}[/]  [dim](o = change)[/]"
            ),
        ]
        if stats.error:
            parts.append(Text.from_markup(f"  [yellow]⚠ {stats.error}[/]"))
            return Group(*parts)
        if not stats.available:
            parts.append(Text.from_markup("  [yellow]⚠ Ocean data unavailable[/]"))
            return Group(*parts)

        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        grid.add_row(
            Text.from_markup("\n".join(self._hashrate_column(stats))),
            Text.from_markup("\n".join(self._sats_column(stats.earnings))),
            Text.from_markup("\n".join(self._pool_column(stats))),
        )
        parts.append(grid)

        # Active Workers Table (with ASIC Detection)
        if stats.workers:
            worker_table = Table(
                box=None,
                expand=True,
                padding=(0, 1),
                show_header=True,
                border_style="dim",
            )
            worker_table.add_column("Worker Name", style="bold cyan")
            worker_table.add_column("Detected ASIC", style="white")
            worker_table.add_column("60s HR", justify="right", style="green")
            worker_table.add_column("5m HR", justify="right", style="green")
            worker_table.add_column("3h HR", justify="right", style="green")
            worker_table.add_column("24h HR", justify="right", style="green")
            worker_table.add_column("Status", justify="center")

            for w in stats.workers:
                status_str = "[bold green]Online[/]" if w.is_active else "[bold red]Offline[/]"
                worker_table.add_row(
                    w.name,
                    w.detected_asic,
                    w.hashrate_60s,
                    w.hashrate_300s,
                    w.hashrate_10800s,
                    w.hashrate_86400s,
                    status_str,
                )
            parts.append(Text.from_markup("\n[bold #00bcd4]👷 ACTIVE WORKERS (ASIC DETECTION) ────[/]"))
            parts.append(worker_table)

        return Group(*parts)

    def _ocean_renderable(self):
        address = self.active_ocean_address
        if not address:
            return Text.from_markup("\n".join(self._render_ocean_prompt()))
        stats = fetch_ocean_account_stats(address)
        self._check_worker_transitions(stats)
        return self._build_ocean_section(stats)

    def _check_worker_transitions(self, stats: OceanAccountStats) -> None:
        """Diff the active-worker set and toast any online/offline changes.

        Runs on the fetch worker thread, so notifications are marshalled back
        to the UI thread via call_from_thread.
        """
        if not stats.available or not stats.workers:
            return
        active = [w.name for w in stats.workers if w.is_active]
        transitions = self._worker_monitor.update(active)
        if not transitions:
            return
        self.app.call_from_thread(self._notify_worker_transitions, transitions)

    def _notify_worker_transitions(self, transitions) -> None:
        for name in transitions.came_online:
            self.app.notify(
                f"Worker back online: {name}",
                title="✅ Worker online",
                severity="information",
                timeout=6,
            )
        for name in transitions.went_offline:
            self.app.notify(
                f"Worker stopped hashing: {name}",
                title="⚠ Worker offline",
                severity="warning",
                timeout=8,
            )

    @staticmethod
    def _age_since(ts: int) -> str:
        """Human 'how long ago' for a unix timestamp."""
        if not ts:
            return ""
        delta = int(time.time()) - ts
        if delta < 0:
            return ""
        days = delta // 86_400
        if days >= 1:
            return f"{days}d ago"
        hours = delta // 3_600
        if hours >= 1:
            return f"{hours}h ago"
        return f"{delta // 60}m ago"

    def _pool_column(self, stats: OceanAccountStats) -> list[str]:
        """Third column: Stacked PyBLOCK stats and Last Ocean Pool Block."""
        lines = []
        cfg = getattr(self.config, "pyblock", None)
        if cfg is None or cfg.community_blocks:
            net = fetch_datum_network()
            blocks = fetch_community_blocks()
            if not net.error or not blocks.error:
                lines.extend(["[bold #00bcd4]🛰  PYBLOCK POOL[/]"])
                if not net.error:
                    lines.append(f"  ⚡ [bold #ffd700]{net.hashrate_human}[/]  👷 [white]{net.workers}[/] [dim]workers[/]")
                if not blocks.error and blocks.blocks:
                    b = max(blocks.blocks, key=lambda x: x.height)
                    age = self._age_since(b.timestamp)
                    lines.append(f"  🧱 [bold #3dd68c]#{b.height}[/]  [dim]{age}[/]")
                lines.append("  [dim]────────────────[/]")

        # Bottom half: Last Ocean block
        lines.append("[bold #00bcd4]🧱 LAST POOL BLOCK[/]")
        ob = getattr(stats, "last_pool_block", None)
        if not ob or not ob.height:
            lines.append("  [dim]No block data[/]")
            return lines

        lines.append(f"  📦 Block    [bold #3dd68c]#{ob.height:,}[/]")
        lines.append(f"  📅 Time     [white]{ob.timestamp}[/]")
        finder = format_ocean_address(ob.miner_address)
        lines.append(f"  👤 Finder   [bold #ffd700]{finder}[/]")
        return lines

    def refresh_data(self) -> None:
        # Network I/O runs off the UI thread so the panel never freezes.
        self._fetch_and_render()

    def _head_with_treemap(self, text_lines: list[str]):
        """Status/job text on the left, live block-template treemap on the right."""
        head_text = Text.from_markup("\n".join(text_lines))
        if not self._show_treemap:
            return head_text
        treemap = render_block_treemap(width=44, height=15)
        if treemap is None:
            return head_text
        grid = Table.grid(expand=True)
        grid.add_column(ratio=1)
        grid.add_column(width=44, justify="right")
        grid.add_row(head_text, treemap)
        return grid

    @work(thread=True, exclusive=True)
    def _fetch_and_render(self) -> None:
        status = fetch_datum_status()
        if not status.available:
            self._gateway_active = False
            head = Text.from_markup(status.setup_hint or "DATUM unavailable.")
            body = Group(head, self._ocean_renderable())
            self.app.call_from_thread(self._apply, body, "datum-warn")
            return

        state_lower = status.gateway_state.lower()
        if "ready" in state_lower or "connected" in state_lower:
            state_cls = "datum-ok"
            self._gateway_active = True
        elif "error" in state_lower or "not" in state_lower:
            state_cls = "datum-err"
            self._gateway_active = False
        else:
            state_cls = "datum-warn"
            self._gateway_active = False

        text_lines = self._render_datum_lines(status)
        text_lines.extend(self._render_job_lines(fetch_datum_job()))
        head = self._head_with_treemap(text_lines)
        body = Group(head, self._ocean_renderable())
        self.app.call_from_thread(self._apply, body, state_cls)

    def _apply(self, body: Group, state_cls: str) -> None:
        static = self.query_one("#datum-content", Static)
        static.update(body)
        static.remove_class("datum-ok", "datum-warn", "datum-err")
        static.add_class(state_cls)
