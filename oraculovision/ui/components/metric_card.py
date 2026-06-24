"""Compact metric display card — with optional Digits hero number."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Digits, Label, Static


class MetricCard(Static):
    """Single metric: label, value (normal or Digits hero), optional subtitle."""

    def __init__(
        self,
        label: str = "",
        value: str = "—",
        subtitle: str = "",
        *,
        severity: str = "",
        use_digits: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._label = label
        self._value = value
        self._subtitle = subtitle
        self._severity = severity
        self._use_digits = use_digits

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._label, classes="metric-label")
            if self._use_digits:
                yield Digits(self._value, id="metric-value", classes="metric-digits")
            else:
                yield Label(self._value, classes="metric-value", id="metric-value")
            yield Static(self._subtitle, classes="metric-sub", id="metric-sub")

    def on_mount(self) -> None:
        self._apply_severity()

    def update_metric(
        self,
        value: str,
        *,
        subtitle: str | None = None,
        severity: str | None = None,
    ) -> None:
        if self._use_digits:
            try:
                self.query_one("#metric-value", Digits).update(value)
            except Exception:
                pass
        else:
            self.query_one("#metric-value", Label).update(value)
        if subtitle is not None:
            sub = self.query_one("#metric-sub", Static)
            sub.update(subtitle)
            sub.display = bool(subtitle)
        if severity is not None:
            self._severity = severity
            self._apply_severity()

    def _apply_severity(self) -> None:
        self.remove_class("-ok", "-warn", "-danger")
        if self._severity == "ok":
            self.add_class("-ok")
        elif self._severity == "warn":
            self.add_class("-warn")
        elif self._severity == "danger":
            self.add_class("-danger")
