"""Navigation sidebar with tier grouping and Lite/Pro mode support."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import ListItem, ListView, Static

from oraculovision.ui.navigation import TIER_LABELS, screens_by_tier


class Sidebar(Static):
    """Keyboard-navigable screen selector with OVERVIEW / ANALYZE / OPERATE tiers."""

    class ScreenSelected(Message):
        def __init__(self, screen_id: str) -> None:
            self.screen_id = screen_id
            super().__init__()

    def __init__(
        self,
        active_id: str = "dashboard",
        *,
        lite_mode: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._active_id = active_id
        self._lite_mode = lite_mode
        self._specs_by_id: dict[str, object] = {}

    def compose(self) -> ComposeResult:
        with Vertical():
            brand = "ORACULOVISION" + (" · LITE" if self._lite_mode else "")
            yield Static(brand, classes="sov-nav-brand")
            items: list[ListItem] = []
            for tier, specs in screens_by_tier(lite_mode=self._lite_mode):
                for i, spec in enumerate(specs):
                    self._specs_by_id[spec.id] = spec
                    marker = "●" if spec.id == self._active_id else "○"
                    
                    widgets = []
                    if i == 0:
                        widgets.append(Static(TIER_LABELS.get(tier, tier.upper()), classes="sov-nav-tier-inline"))
                    widgets.append(Static(f"[{spec.key}] {marker} {spec.label}", classes="sov-nav-item-text"))
                    
                    items.append(
                        ListItem(
                            *widgets,
                            id=f"nav-{spec.id}",
                        )
                    )
            yield ListView(*items, id="nav-list")
            hint = "1-8 · keys" if not self._lite_mode else "1,7 · keys"
            yield Static(hint, classes="sov-nav-hint")

    def on_mount(self) -> None:
        self._highlight_active()

    def set_active(self, screen_id: str) -> None:
        self._active_id = screen_id
        self._highlight_active()

    def _highlight_active(self) -> None:
        for spec_id in self._specs_by_id:
            try:
                item = self.query_one(f"#nav-{spec_id}", ListItem)
            except Exception:
                continue
            spec = self._specs_by_id[spec_id]
            marker = "●" if spec_id == self._active_id else "○"
            item.query_one(".sov-nav-item-text", Static).update(f"[{spec.key}] {marker} {spec.label}")
            if spec_id == self._active_id:
                item.add_class("-active")
            else:
                item.remove_class("-active")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        if item_id.startswith("nav-"):
            screen_id = item_id[4:]
            self.set_active(screen_id)
            self.post_message(self.ScreenSelected(screen_id))
