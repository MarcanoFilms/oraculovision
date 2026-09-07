"""Policies screen — Knots policy display and template simulation."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import DataTable, Label, Static

from oraculovision.analysis.policies import (
    KnotsPolicySnapshot,
    PolicyPreset,
    build_conf_adjustments,
    fetch_knots_policies,
    render_conf_preview,
    simulate_policy_presets,
)
from oraculovision.analysis.policies.simulator import POLICY_LIMITS, PRESET_META
from oraculovision.config import AppConfig
from oraculovision.node.client import BitcoinCLIError, NodeClient
from oraculovision.services.template_service import TemplateService
from oraculovision.ui.components.explain_box import ExplainBox
from oraculovision.ui.components.sovereign_panel import SovereignPanel
from oraculovision.ui.screens.base import BaseScreen

BIP110_EXPLAIN = (
    "BIP-110 marks certain transactions as consensus-invalid — oversized witness data, "
    "bad tapscript patterns, and abuse of OP_RETURN. Your Knots node enforces these rules "
    "locally. Simulation shows how many template txs would be rejected under stricter presets."
)


def _render_policy_snapshot(lines: list[str], read_only: bool) -> str:
    mode = "[green]READ-ONLY[/]" if read_only else "[yellow]CONTROL ENABLED[/]"
    header = [
        "[bold #ffd700]Live Knots Policy Snapshot[/]",
        f"Mode: {mode}",
        "",
    ]
    if not lines:
        header.append("[dim]No policy data available[/]")
        return "\n".join(header)

    body = []
    for line in lines[:20]:
        body.append(f"  {line}")
    if len(lines) > 20:
        body.append(f"  … +{len(lines) - 20} more")

    limits = (
        f"\n[dim]BIP-110 limits: pushdata≤{POLICY_LIMITS['max_pushdata']}B · "
        f"op_return≤{POLICY_LIMITS['max_opreturn']}B[/]"
    )
    return "\n".join(header + body) + limits


def _render_simulation_intro(height: int, tx_count: int) -> str:
    return (
        f"[bold]Template Simulation[/]  ·  height #{height}  ·  {tx_count:,} txs\n"
        "[dim]Simulates stricter rules against your node's current block template. "
        "Does not change node policy.[/]"
    )


class PoliciesScreen(BaseScreen):
    """Show Knots policies and simulate stricter enforcement."""

    screen_id = "policies"

    DEFAULT_CSS = """
    PoliciesScreen {
        layout: vertical;
    }
    PoliciesScreen #policies-header {
        height: auto;
        text-style: bold;
        padding: 0 1;
    }
    PoliciesScreen #policy-explain {
        margin: 0 1 1 1;
    }
    PoliciesScreen #policies-body {
        height: 1fr;
    }
    PoliciesScreen #policy-snapshot {
        width: 42%;
        height: 100%;
    }
    PoliciesScreen #conf-preview {
        margin-top: 1;
        max-height: 14;
    }
    PoliciesScreen SovereignPanel {
        height: 100%;
    }
    PoliciesScreen #simulation-panel {
        width: 58%;
        height: 100%;
        padding-left: 1;
    }
    PoliciesScreen #sim-intro {
        height: auto;
        padding-bottom: 1;
    }
    PoliciesScreen #sim-table {
        height: 1fr;
    }
    PoliciesScreen #sim-detail {
        height: auto;
        max-height: 10;
        padding: 1 1;
        margin-top: 1;
    }
    PoliciesScreen .panel-title {
        text-style: bold;
        padding-bottom: 1;
    }
    """

    def __init__(
        self,
        cli: NodeClient,
        config: AppConfig,
        template_service: TemplateService,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.cli = cli
        self.config = config
        self.template_service = template_service
        self._selected_preset: PolicyPreset = PolicyPreset.CURRENT_BIP110
        self._sim_results: dict[PolicyPreset, object] = {}
        self._policy_snapshot: KnotsPolicySnapshot | None = None

    def compose(self) -> ComposeResult:
        yield Label("POLICIES & RULES", id="policies-header")
        yield ExplainBox(
            title="Why this matters",
            text=BIP110_EXPLAIN,
            id="policy-explain",
        )
        with Horizontal(id="policies-body"):
            with VerticalScroll(id="policy-snapshot"):
                yield SovereignPanel(title="NODE POLICIES", id="policy-panel")
                yield SovereignPanel(
                    title="BITCOIN.CONF PREVIEW",
                    id="conf-preview",
                )
            with Vertical(id="simulation-panel"):
                yield Static("", id="sim-intro")
                yield DataTable(id="sim-table", zebra_stripes=True, cursor_type="row")
                yield Static("↑↓ select preset for detail", id="sim-detail")

    def on_mount(self) -> None:
        table = self.query_one("#sim-table", DataTable)
        table.add_columns("Preset", "Rejected", "By Count", "By Weight")
        table.cursor_type = "row"
        self.query_one("#policy-panel", SovereignPanel).update_content(
            "[dim]Loading policies from your node…[/]"
        )
        self.query_one("#conf-preview", SovereignPanel).update_content(
            "[dim]Loading adjustment preview…[/]"
        )
        self.refresh_screen()

    def refresh_screen(self, *, force: bool = False) -> None:
        self._load_data(force=force)

    @work(thread=True, exclusive=True)
    def _load_data(self, force: bool = False) -> None:
        try:
            snapshot = fetch_knots_policies(self.cli)
            text = _render_policy_snapshot(
                snapshot.lines(),
                self.config.control.read_only,
            )
            self.app.call_from_thread(self._update_policy_content, text, snapshot)
        except BitcoinCLIError as exc:
            msg = str(exc)
            if exc.hint:
                msg += f"\n→ {exc.hint}"
            self.app.call_from_thread(self._update_policy_content, f"[red]{msg}[/]")

        try:
            snap = self.template_service.fetch(force=force)
            if snap.error:
                self.app.call_from_thread(self._update_sim_error, snap.error)
                return

            tmpl = snap.template
            results = simulate_policy_presets(
                tmpl,
                self.cli.decode_raw_transaction,
            )
            height = int(tmpl.get("height", 0))
            tx_count = len(tmpl.get("transactions", []))
            self.app.call_from_thread(
                self._update_sim_table,
                results,
                height,
                tx_count,
            )
        except BitcoinCLIError as exc:
            msg = str(exc)
            if exc.hint:
                msg += f"\n→ {exc.hint}"
            self.app.call_from_thread(self._update_sim_error, msg)

    def _update_policy_content(
        self,
        text: str,
        snapshot: KnotsPolicySnapshot | None = None,
    ) -> None:
        if snapshot is not None:
            self._policy_snapshot = snapshot
        panel = self.query_one("#policy-panel", SovereignPanel)
        panel.update_content(text)
        if "CONTROL ENABLED" in text:
            panel.set_severity("warn")
        else:
            panel.set_severity("ok")
        self._refresh_conf_preview()

    def _update_sim_error(self, message: str) -> None:
        self.query_one("#sim-intro", Static).update(f"[red]{message}[/]")
        self.query_one("#sim-detail", Static).update("")

    def _update_sim_table(
        self,
        results: list,
        height: int,
        tx_count: int,
    ) -> None:
        self._sim_results = {r.preset: r for r in results}
        self.query_one("#sim-intro", Static).update(
            _render_simulation_intro(height, tx_count)
        )
        table = self.query_one("#sim-table", DataTable)
        table.clear()
        for r in results:
            if r.error:
                table.add_row(r.label, "—", "—", r.error[:24])
                continue
            table.add_row(
                r.label,
                f"{r.rejected_tx:,}",
                f"{r.reject_pct_by_count:.1f}%",
                f"{r.reject_pct_by_weight:.1f}%",
                key=r.preset.value,
            )
        if results and not results[0].error:
            self._selected_preset = results[0].preset
            self._show_preset_detail(results[0])
        self._refresh_conf_preview()

    def _refresh_conf_preview(self) -> None:
        panel = self.query_one("#conf-preview", SovereignPanel)
        snap = self._policy_snapshot
        if snap is None or snap.error:
            panel.update_content("[dim]Waiting for live policy snapshot…[/]")
            panel.set_severity("")
            return

        adjustments = build_conf_adjustments(snap, self._sim_results)
        panel.update_content(
            render_conf_preview(
                adjustments,
                knots_detected=snap.knots_detected,
            )
        )
        if adjustments:
            panel.set_severity("warn")
        else:
            panel.set_severity("ok")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "sim-table":
            return
        row_key = event.row_key
        if row_key is None:
            return
        preset_val = str(row_key.value) if hasattr(row_key, "value") else str(row_key)
        try:
            preset = PolicyPreset(preset_val)
        except ValueError:
            return
        self._selected_preset = preset
        result = self._sim_results.get(preset)
        if result:
            self._show_preset_detail(result)

    def _show_preset_detail(self, result) -> None:
        if result.error:
            self.query_one("#sim-detail", Static).update(f"[red]{result.error}[/]")
            return

        label, desc = PRESET_META.get(result.preset, (result.label, result.description))
        lines = [
            f"[bold]{label}[/] — {desc}",
            result.impact_summary,
        ]
        if result.top_reasons:
            reasons = ", ".join(f"{k}({v})" for k, v in result.top_reasons[:5])
            lines.append(f"Top reasons: {reasons}")
        if result.sample_rejects:
            sample = result.sample_rejects[0]
            lines.append(
                f"Example reject: {sample.txid}… [{', '.join(sample.reject_reasons[:3])}]"
            )
        self.query_one("#sim-detail", Static).update("\n".join(lines))