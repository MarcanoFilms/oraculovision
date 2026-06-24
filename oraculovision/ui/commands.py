"""Textual Command Palette provider for OraculoVision.

Exposes power-user actions via Ctrl+P fuzzy search instead of
cluttering the footer with rarely-used keybindings.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from textual.command import Hit, Hits, Provider

if TYPE_CHECKING:
    from oraculovision.ui.app import SovereignApp


class OracleCommandProvider(Provider):
    """Commands surfaced in Ctrl+P command palette."""

    @property
    def _sovereign_app(self) -> "SovereignApp":
        return self.app  # type: ignore[return-value]

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)

        commands = [
            ("Switch to Dashboard (1)", self._go_dashboard),
            ("Switch to Policies (2)", self._go_policies),
            ("Switch to Mempool Glass (3)", self._go_mempool),
            ("Switch to Block Explorer (4)", self._go_explorer),
            ("Switch to Tx Inspector (5)", self._go_tx),
            ("Switch to Spam & Health (6)", self._go_health),
            ("Switch to Mining (7)", self._go_mining),
            ("Switch to Node Control (8)", self._go_control),
            ("Toggle Lite / Pro mode", self._toggle_mode),
            ("Toggle stream theme", self._toggle_stream),
            ("Switch node profile", self._switch_profile),
            ("Change Ocean payout address", self._ocean_address),
            ("Export current screen data", self._export),
            ("Force refresh block template", self._refresh_template),
            ("Refresh UTXO set (slow)", self._refresh_utxo),
            ("Show help screen", self._show_help),
        ]

        for label, callback in commands:
            score = matcher.match(label)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(label),
                    partial(self._run, callback),
                )

    async def _run(self, callback) -> None:
        callback()

    def _go_dashboard(self) -> None:
        self._sovereign_app.action_goto_dashboard()

    def _go_policies(self) -> None:
        self._sovereign_app.action_goto_policies()

    def _go_mempool(self) -> None:
        self._sovereign_app.action_goto_mempool()

    def _go_explorer(self) -> None:
        self._sovereign_app.action_goto_explorer()

    def _go_tx(self) -> None:
        self._sovereign_app.action_goto_tx_inspector()

    def _go_health(self) -> None:
        self._sovereign_app.action_goto_health()

    def _go_mining(self) -> None:
        self._sovereign_app.action_goto_mining()

    def _go_control(self) -> None:
        self._sovereign_app.action_goto_control()

    def _toggle_mode(self) -> None:
        self._sovereign_app.action_toggle_ui_mode()

    def _toggle_stream(self) -> None:
        self._sovereign_app.action_cycle_theme()

    def _switch_profile(self) -> None:
        self._sovereign_app.action_switch_profile()

    def _ocean_address(self) -> None:
        self._sovereign_app.action_ocean_address()

    def _export(self) -> None:
        self._sovereign_app.action_export_data()

    def _refresh_template(self) -> None:
        self._sovereign_app.action_refresh_template()

    def _refresh_utxo(self) -> None:
        self._sovereign_app.action_refresh_utxo()

    def _show_help(self) -> None:
        self._sovereign_app.action_show_help()
