"""Blinking ● indicator showing whether panel data is fresh."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


class LiveIndicator(Static):
    """Small pulsing dot that shows live/stale data state.

    Call ``mark_fresh()`` after every successful data refresh.
    The indicator automatically fades to stale after ``stale_after`` seconds
    without a refresh.
    """

    is_fresh: reactive[bool] = reactive(True, layout=False)

    DEFAULT_CSS = """
    LiveIndicator {
        width: auto;
        height: 1;
        color: #3dd68c;
        padding: 0 1 0 0;
    }
    LiveIndicator.-stale {
        color: #888;
    }
    """

    def __init__(
        self,
        *,
        stale_after: float = 90.0,
        label: str = "●",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._stale_after = stale_after
        self._label = label
        self._pulse_timer = None
        self._stale_timer = None

    def on_mount(self) -> None:
        self._pulse_timer = self.set_interval(2.5, self._pulse)
        self.mark_fresh()

    def mark_fresh(self) -> None:
        """Call after every successful data fetch."""
        self.is_fresh = True
        self.remove_class("-stale")
        if self._stale_timer is not None:
            self._stale_timer.stop()
        self._stale_timer = self.set_timer(self._stale_after, self._go_stale)

    def _go_stale(self) -> None:
        self.is_fresh = False
        self.add_class("-stale")

    def _pulse(self) -> None:
        if not self.is_fresh:
            return
        self.styles.animate("opacity", 0.3, duration=0.4)
        self.set_timer(0.4, lambda: self.styles.animate("opacity", 1.0, duration=0.4))

    def render(self) -> str:
        return self._label
