"""Live charts for mempool size, peer count, sovereignty score, and spam weight."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, Static

from oraculovision.data.bitcoin import BitcoinCLI, BitcoinCLIError

try:
    from textual_plotext import PlotextPlot
except ImportError:
    PlotextPlot = None  # type: ignore[misc, assignment]


MAX_POINTS = 120  # ~60 min at 30s interval


class LiveCharts(Static):
    """Rolling charts for mempool size, peer count, sovereignty score, and spam weight."""

    DEFAULT_CSS = """
    LiveCharts {
        height: 1fr;
        padding: 1 1;
    }
    LiveCharts PlotextPlot {
        height: 1fr;
    }
    """

    def __init__(self, cli: BitcoinCLI | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cli = cli or BitcoinCLI()
        self.border_title = "🔮 ORACLE VISION [v]"
        self._mempool: deque[float] = deque(maxlen=MAX_POINTS)
        self._peers: deque[float] = deque(maxlen=MAX_POINTS)
        self._score: deque[float] = deque(maxlen=MAX_POINTS)
        self._spam: deque[float] = deque(maxlen=MAX_POINTS)
        self._last_sample: str = ""
        self._mode: int = 0  # 0 = Sovereignty & Spam (Oracle), 1 = Mempool & Network (System)

    def compose(self) -> ComposeResult:
        if PlotextPlot is None:
            yield Label(
                "textual-plotext not installed. pip install textual-plotext",
                classes="chart-error",
            )
            return
        with Vertical():
            with Horizontal():
                yield PlotextPlot(id="mempool-chart")
                yield PlotextPlot(id="peers-chart")

    def on_mount(self) -> None:
        if PlotextPlot is None:
            return
        self._setup_charts()
        self.refresh_data()

    def _setup_charts(self) -> None:
        # Initial chart titles, will be dynamically updated by _redraw
        mp = self.query_one("#mempool-chart", PlotextPlot)
        peers = self.query_one("#peers-chart", PlotextPlot)
        mp.plt.theme("dark")
        peers.plt.theme("dark")

    def action_cycle_view(self) -> None:
        """Cycle between Sovereignty/Spam and Mempool/Network views."""
        self._mode = (self._mode + 1) % 2
        try:
            self._redraw()
        except Exception:
            pass

    def refresh_data(self, score: float | None = None, spam_pct: float | None = None) -> None:
        if PlotextPlot is None:
            return
        try:
            mempool = self.cli.get_mempool_info()
            network = self.cli.get_network_info()
        except BitcoinCLIError:
            return

        mb = mempool.get("bytes", 0) / 1_000_000
        peer_count = float(network.get("connections", 0))
        self._last_sample = datetime.now(timezone.utc).strftime("%H:%M UTC")

        self._mempool.append(mb)
        self._peers.append(peer_count)

        if score is None:
            score = 100.0
        if spam_pct is None:
            spam_pct = 0.0

        self._score.append(float(score))
        self._spam.append(float(spam_pct))

        try:
            self._redraw()
        except Exception:
            pass

    def _redraw(self) -> None:
        if len(self._mempool) < 2:
            return

        x = list(range(len(self._mempool)))
        mp = self.query_one("#mempool-chart", PlotextPlot)
        peers = self.query_one("#peers-chart", PlotextPlot)

        mp.plt.clear_figure()
        peers.plt.clear_figure()

        if self._mode == 0:
            # Mode 0: Sovereignty & Spam (Oracle theme)
            score_y = list(self._score)
            spam_y = list(self._spam)

            # Pad deques to align with x length
            while len(score_y) < len(x):
                score_y.insert(0, 100.0)
            while len(spam_y) < len(x):
                spam_y.insert(0, 0.0)

            mp.plt.title(f"Sovereignty Score  @{self._last_sample}")
            mp.plt.plot(x, score_y, marker="dot", color="cyan")
            mp.plt.xlabel("samples (~30s)")
            mp.plt.ylabel("score (0-100)")
            mp.plt.theme("dark")

            peers.plt.title(f"Template Spam (%)  @{self._last_sample}")
            peers.plt.plot(x, spam_y, marker="dot", color="red")
            peers.plt.xlabel("samples (~30s)")
            peers.plt.ylabel("spam %")
            peers.plt.theme("dark")
        else:
            # Mode 1: Mempool & Network (System theme)
            mempool_y = list(self._mempool)
            peers_y = list(self._peers)

            mp.plt.title(f"Mempool (MB)  @{self._last_sample}")
            mp.plt.plot(x, mempool_y, marker="dot", color="yellow")
            mp.plt.xlabel("samples (~30s)")
            mp.plt.ylabel("MB")
            mp.plt.theme("dark")

            peers.plt.title(f"Peers  @{self._last_sample}")
            peers.plt.plot(x, peers_y, marker="dot", color="green")
            peers.plt.xlabel("samples (~30s)")
            peers.plt.ylabel("count")
            peers.plt.theme("dark")

        mp.refresh()
        peers.refresh()