"""Configuration loader for oraculovision."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from oraculovision.node.profiles import NodeProfile, load_profiles


def _config_paths() -> list[Path]:
    env = os.environ.get("ORACULOVISION_CONFIG")
    paths: list[Path] = []
    if env:
        paths.append(Path(env))
    paths.extend([
        Path.home() / ".config" / "oraculovision" / "config.toml",
        Path(__file__).resolve().parent.parent / "config.toml",
    ])
    return paths


@dataclass
class RefreshConfig:
    interval_seconds: int = 30


@dataclass
class AlertsConfig:
    min_peers: int = 8
    mempool_congested_mb: float = 50.0
    mempool_congested_tx: int = 5000
    spam_block_score: int = 45


@dataclass
class MempoolGlassConfig:
    sample_size: int = 120


@dataclass
class BitcoinConfig:
    cli_path: str = "bitcoin-cli"
    datadir: str = ""
    utxo_timeout: float = 120.0
    active_profile: str = "local"


@dataclass
class OceanConfig:
    address: str = ""
    payout_threshold: float = 0.001


@dataclass
class MiningConfig:
    """Local mining economics for net-earnings estimates (all opt-in).

    Left at defaults (zeros) the dashboard shows gross earnings only and
    nothing changes. Fill these in to see pool-fee-adjusted and
    electricity-adjusted net figures, DeepSea-style.
    """

    power_watts: float = 0.0
    power_cost_per_kwh: float = 0.0
    currency: str = "USD"
    pool_fee_pct: float = 0.0
    btc_price: float = 0.0


@dataclass
class ControlConfig:
    """Node control safety settings."""

    read_only: bool = True


@dataclass
class ChainHealthConfig:
    """Spam & chain health scan settings."""

    scan_blocks: int = 48


@dataclass
class BlockIndexConfig:
    """Persistent block analysis cache settings."""

    enabled: bool = True
    path: str = ""
    max_entries: int = 5000


@dataclass
class DetectorsConfig:
    """Enabled transaction detector plugins."""

    enabled: list[str] = field(default_factory=lambda: ["builtin"])


@dataclass
class AddressConfig:
    """Address inspector settings."""

    scantxoutset_timeout: float = 90.0
    max_vin_lookups: int = 4
    mempool_scan_limit: int = 30


@dataclass
class ExportConfig:
    """Audit export settings."""

    directory: str = ""
    json: bool = True
    csv: bool = True


@dataclass
class UIConfig:
    """UI presentation and UX settings."""

    mode: str = "pro"
    theme: str = "oracle"
    screen_transitions: bool = True
    splash: bool = True
    tooltips: bool = True
    sparkline_samples: int = 60


@dataclass
class PyblockConfig:
    """PyBLOCK community pool integration (third-party, opt-out)."""

    community_blocks: bool = True
    api_url: str = "https://pyblock.xyz:8443"


@dataclass
class AppConfig:
    refresh: RefreshConfig = field(default_factory=RefreshConfig)
    alerts: AlertsConfig = field(default_factory=AlertsConfig)
    mempool_glass: MempoolGlassConfig = field(default_factory=MempoolGlassConfig)
    bitcoin: BitcoinConfig = field(default_factory=BitcoinConfig)
    ocean: OceanConfig = field(default_factory=OceanConfig)
    mining: MiningConfig = field(default_factory=MiningConfig)
    control: ControlConfig = field(default_factory=ControlConfig)
    chain_health: ChainHealthConfig = field(default_factory=ChainHealthConfig)
    block_index: BlockIndexConfig = field(default_factory=BlockIndexConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    address: AddressConfig = field(default_factory=AddressConfig)
    detectors: DetectorsConfig = field(default_factory=DetectorsConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    pyblock: PyblockConfig = field(default_factory=PyblockConfig)
    profiles: dict[str, NodeProfile] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.profiles:
            self.profiles = {
                "local": NodeProfile(
                    name="local",
                    cli_path=self.bitcoin.cli_path,
                    datadir=self.bitcoin.datadir,
                ),
            }
        elif self.bitcoin.active_profile not in self.profiles:
            self.bitcoin.active_profile = next(iter(self.profiles))


def config_source() -> tuple[Path | None, float]:
    """Return the active config file path and its modification time."""
    for path in _config_paths():
        if path.is_file():
            try:
                return path, path.stat().st_mtime
            except OSError:
                return path, 0.0
    return None, 0.0


def load_config() -> AppConfig:
    cfg = AppConfig()
    data: dict = {}

    for path in _config_paths():
        if path.is_file():
            try:
                data = tomllib.loads(path.read_text())
                break
            except (OSError, tomllib.TOMLDecodeError):
                continue

    if refresh := data.get("refresh"):
        cfg.refresh = RefreshConfig(
            interval_seconds=int(refresh.get("interval_seconds", 30)),
        )
    if alerts := data.get("alerts"):
        cfg.alerts = AlertsConfig(
            min_peers=int(alerts.get("min_peers", 8)),
            mempool_congested_mb=float(alerts.get("mempool_congested_mb", 50)),
            mempool_congested_tx=int(alerts.get("mempool_congested_tx", 5000)),
            spam_block_score=int(alerts.get("spam_block_score", 45)),
        )
    if glass := data.get("mempool_glass"):
        cfg.mempool_glass = MempoolGlassConfig(
            sample_size=int(glass.get("sample_size", 120)),
        )
    if btc := data.get("bitcoin"):
        cfg.bitcoin = BitcoinConfig(
            cli_path=str(btc.get("cli_path", "bitcoin-cli")),
            datadir=str(btc.get("datadir", "")),
            utxo_timeout=float(btc.get("utxo_timeout", 120)),
            active_profile=str(btc.get("active_profile", "local")),
        )
    if ocean := data.get("ocean"):
        cfg.ocean = OceanConfig(
            address=str(ocean.get("address", "")).strip(),
            payout_threshold=float(ocean.get("payout_threshold", 0.001)),
        )
    if mining := data.get("mining"):
        cfg.mining = MiningConfig(
            power_watts=max(0.0, float(mining.get("power_watts", 0))),
            power_cost_per_kwh=max(0.0, float(mining.get("power_cost_per_kwh", 0))),
            currency=str(mining.get("currency", "USD")),
            pool_fee_pct=min(100.0, max(0.0, float(mining.get("pool_fee_pct", 0)))),
            btc_price=max(0.0, float(mining.get("btc_price", 0))),
        )
    if control := data.get("control"):
        cfg.control = ControlConfig(
            read_only=bool(control.get("read_only", True)),
        )
    if health := data.get("chain_health"):
        cfg.chain_health = ChainHealthConfig(
            scan_blocks=int(health.get("scan_blocks", 48)),
        )
    if block_index := data.get("block_index"):
        cfg.block_index = BlockIndexConfig(
            enabled=bool(block_index.get("enabled", True)),
            path=str(block_index.get("path", "")),
            max_entries=int(block_index.get("max_entries", 5000)),
        )
    if export := data.get("export"):
        cfg.export = ExportConfig(
            directory=str(export.get("directory", "")),
            json=bool(export.get("json", True)),
            csv=bool(export.get("csv", True)),
        )
    if address := data.get("address"):
        cfg.address = AddressConfig(
            scantxoutset_timeout=float(address.get("scantxoutset_timeout", 90)),
            max_vin_lookups=int(address.get("max_vin_lookups", 4)),
            mempool_scan_limit=int(address.get("mempool_scan_limit", 30)),
        )
    if detectors := data.get("detectors"):
        enabled = detectors.get("enabled", ["builtin"])
        if isinstance(enabled, list):
            cfg.detectors = DetectorsConfig(
                enabled=[str(name) for name in enabled],
            )

    if ui := data.get("ui"):
        mode = str(ui.get("mode", "pro")).lower()
        if mode not in ("lite", "pro"):
            mode = "pro"
        theme = str(ui.get("theme", "oracle")).lower()
        if theme not in ("oracle", "stream", "dark"):
            theme = "oracle"
        cfg.ui = UIConfig(
            mode=mode,
            theme=theme,
            screen_transitions=bool(ui.get("screen_transitions", True)),
            splash=bool(ui.get("splash", True)),
            tooltips=bool(ui.get("tooltips", True)),
            sparkline_samples=max(10, int(ui.get("sparkline_samples", 60))),
        )

    if pyblock := data.get("pyblock"):
        cfg.pyblock = PyblockConfig(
            community_blocks=bool(pyblock.get("community_blocks", True)),
            api_url=str(pyblock.get("api_url", "https://pyblock.xyz:8443")),
        )

    # Remember the Ocean payout address across restarts when config.toml
    # doesn't pin one (the user can always change it from the UI).
    if not cfg.ocean.address:
        from oraculovision.state import load_ocean_address
        saved = load_ocean_address()
        if saved:
            cfg.ocean.address = saved

    cfg.profiles = load_profiles(data)
    cfg.__post_init__()

    return cfg