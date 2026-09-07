# OraculoVision
<img width="1920" height="1056" alt="image" src="https://github.com/user-attachments/assets/31233dd5-727b-44ec-90f8-2bb2b4364287" />

Terminal dashboard (TUI) for sovereign operators running **Bitcoin Knots** with **BIP-110** enabled and **DATUM** for solo mining.

Philosophy: **Don't Trust, Verify**.

**v2.4** — DeepSea-inspired mining suite: net-earnings economics (electricity + pool fee, optional fiat profit/day), worker online/offline toast alerts, a payout-progress bar, per-worker ASIC detection, and a higher-definition (sextant, btop-grade) block-template treemap.

**v2.3** — adds Sparkline trend charts, Sovereignty Score, animated alerts, Lite/Pro mode, stream recording theme, Command Palette, splash screen, and archival node awareness.

## Features

| Panel / Feature | Description |
|----------------|-------------|
| **Node Status** | Sync, peers, mempool, UTXO set — with rolling **Sparkline** trend charts for peers and mempool |
| **Mining Economics** | Net sat/day after pool fee + electricity, with optional fiat profit/day (`[mining]` config) |
| **Worker Alerts** | Toast notifications when an Ocean worker stops hashing or comes back online |
| **Payout Progress** | Visual bar tracking your unpaid balance toward the Ocean payout threshold |
| **Worker ASIC Detection** | Per-worker table inferring the rig model (S19/S21/Whatsminer…) from worker names |
| **Block Template Treemap** | mempool.space-style fee-rate treemap with btop-grade sextant rendering |
| **Sovereignty Score** | Composite 0-100 headline metric (sync + peers + Knots + spam) with letter grade (A+…F) |
| **BIP-110 Detector** | Spam score, status, miner tags, navigable table — animated red flash on new violation |
| **Block Detail Modal** | Full per-block detail (Enter) |
| **DATUM Mining** | Gateway, workers, hashrate, shares |
| **Ocean Account** | Pool hashrate, TIDES, earnings, blocks found |
| **Mempool Glass** | **Real Block Template** composition (all GBT txs) |
| **Block Template** | Compact GBT summary + top 5 fee rates |
| **Live Metrics** | Mempool and peer charts (textual-plotext) |
| **Lite Mode** | Single-screen overview for first-time node operators |
| **Command Palette** | `Ctrl+P` fuzzy-search access to all actions |
| **Stream Theme** | High-contrast recording theme (`Ctrl+T`) optimised for 1080p |
| **Splash Screen** | ASCII-art oracle splash on startup (auto-dismisses, configurable) |
| **[PRUNED] / [ARCHIVAL]** | Status bar badge detects node type via `getblockchaininfo` + `getindexinfo` |
| **Milestone Celebrations** | `notify()` toast on round-number block heights (debounced, no repeat) |

## Requirements

- Python 3.11+
- [Bitcoin Knots](https://bitcoinknots.org/) with RPC available via `bitcoin-cli`
- (Optional) [DATUM Gateway](https://github.com/OCEAN-xyz/datum_gateway) for the mining panel
- (Optional) Ocean payout address for pool account stats (no API key required)

## Installation

### From the repository

```bash
git clone https://github.com/MarcanoFilms/oraculovision.git
cd oraculovision
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Configuration

```bash
mkdir -p ~/.config/oraculovision
cp config.example.toml ~/.config/oraculovision/config.toml
# Edit the file for your environment
```

You can also place `config.toml` in the project root for local development.

### Run

```bash
oraculovision
# or
python main.py
```

### Global shortcut (optional)

```bash
./install-shortcut.sh
```

This creates `~/.local/bin/oraculovision` pointing at the project's virtual environment.

## Keyboard shortcuts

### Screen navigation (v2)

| Key | Screen |
|-----|--------|
| `1` | Dashboard — sovereignty brief, metrics, expert panels |
| `2` | Policies — Knots policies + simulation |
| `3` | Mempool Glass — full block template analysis |
| `4` | Block Explorer — search blocks by height/hash |
| `5` | Tx & Address Inspector — flows, fees, UTXO balance |
| `6` | Spam & Health — chain health trends |
| `7` | Mining — DATUM + Ocean |
| `8` | Node Control — peers/bans (gated) |

### Global

| Key | Action |
|-----|--------|
| `r` | Refresh current screen |
| `t` | Refresh Block Template + Mempool Glass (full GBT) |
| `u` | Refresh UTXO set stats (slow RPC, ~2 min, background) |
| `e` | Export JSON/CSV audit trail (Health, Explorer, Tx Inspector) |
| `p` | Cycle node profile (local / remote RPC / SSH) |
| `o` | Enter or change Ocean payout address |
| `/` | Focus search (Explorer, Tx Inspector, Control) |
| `q` | Quit |
| `?` | Full help screen |
| `Ctrl+P` | Command Palette — fuzzy-search all actions |
| `Ctrl+T` | Cycle theme: Oracle ↔ Stream (recording) |

### Command Palette (`Ctrl+P`)

Type any part of an action name to jump to it:

- Switch to any screen by name
- **Toggle Lite / Pro mode** — switch between single-screen and full 8-screen UI
- **Toggle stream theme** — high-contrast 1080p recording mode
- Switch node profile, change Ocean address, export, refresh template, UTXO

### Tx & Address Inspector

| Key | Action |
|-----|--------|
| `Enter` | Inspect txid (64 hex) or address (`bc1…`, `1…`, `3…`) |
| `a` | Open UTXO balance for address from loaded transaction |
| `c` | Copy txid or address to clipboard |

**Tx view** shows inputs/outputs, BTC amounts, fees, senders and recipients.  
**Address view** shows confirmed UTXO balance via `scantxoutset` on your node.  
On **pruned nodes**, inspect txs from Block Explorer (`i` on flagged tx) for full block-cache context.

### BIP-110 Detector
<img width="968" height="599" alt="image" src="https://github.com/user-attachments/assets/509b9eac-7ccf-4b8c-8cb5-cb1c858b1625" />


| Key | Action |
|-----|--------|
| `↑` `↓` | Navigate block table |
| `Enter` | Open block detail modal |

### Block modal

<img width="1912" height="1031" alt="image" src="https://github.com/user-attachments/assets/81f9ee7e-d941-44a5-8b2a-21caac40cd9e" />

| Key | Action |
|-----|--------|
| `c` | Copy hash to clipboard |
| `Esc` | Close |

### Ocean address modal

| Key | Action |
|-----|--------|
| `Enter` | Apply address (empty clears session address) |
| `Esc` | Cancel without changes |

## Visual alerts

- **Red border** on Node Status — low peer count
- **Yellow border** on Node Status — congested mempool
- **Red border** on BIP-110 — high-spam tip block
- **Red border** on Mempool Glass — >30% spam weight
- **Top banner** — summary of active alerts

## Lite vs Pro mode

| Mode | What you see |
|------|-------------|
| **Pro** (default) | All 8 screens, full expert panels, BIP-110 table |
| **Lite** | Single dashboard: Score, Sync, Peers, Mempool + DATUM |

Switch at runtime via `Ctrl+P → Toggle Lite / Pro mode`, or set in config:

```toml
[ui]
mode = "lite"   # or "pro" (default)
```

Lite mode is ideal for a first-time node runner or a wall-mounted display.

## Themes

| Theme | Description |
|-------|-------------|
| `oracle` | Default cyberpunk dark palette (orange + cyan + gold) |
| `stream` | High-contrast black/white optimised for 1080p screen recording |

Toggle with `Ctrl+T` at runtime or `[ui] theme = "stream"` in config.

## Sovereignty Score

The **Score** metric card on the dashboard is a 0–100 composite:

| Penalty | Condition |
|---------|-----------|
| Up to 25 pts | Not fully synced |
| Up to 20 pts | Peer count below `min_peers` |
| 10 pts | Not running Bitcoin Knots |
| 5–20 pts | Template spam weight (5 / 10 / 20 pts at >5% / >15% / >30%) |
| 8–15 pts | Tip block spam score (8 pts >40, 15 pts >60) |
| 5–10 pts | Chain health violation % (5 pts >10%, 10 pts >20%) |

Grades: **A+** (96–100) · **A** (90–95) · **B** (80–89) · **C** (70–79) · **D** (60–69) · **F** (<60)

The formula is isolated in `oraculovision/analysis/sovereignty_score.py` and fully unit-tested.

## Configuration

OraculoVision looks for configuration in this order:

1. `ORACULOVISION_CONFIG` environment variable
2. `~/.config/oraculovision/config.toml`
3. `config.toml` in the project root

See `config.example.toml` for all available options with documentation.

### UI configuration (`[ui]`)

```toml
[ui]
mode                = "pro"     # "lite" | "pro"
theme               = "oracle"  # "oracle" | "stream" | "dark"
screen_transitions  = true      # opacity fade when switching screens
splash              = true      # ASCII-art splash on launch
tooltips            = true      # first-open panel tips (stored in ~/.local/share/…)
sparkline_samples   = 60        # rolling buffer (~30 min at 30 s interval)
```

All keys are optional — existing `config.toml` files work without changes.

### Environment variables

| Variable | Description |
|----------|-------------|
| `BITCOIN_CLI` | Path to `bitcoin-cli` |
| `BITCOIN_DATADIR` | Node data directory |
| `DATUM_API_URL` | DATUM API (default `http://127.0.0.1:7152`) |
| `DATUM_CONFIG` | Path to DATUM gateway JSON config |
| `OCEAN_API_URL` | Ocean API base URL (default `https://api.ocean.xyz`) |
| `ORACULOVISION_CONFIG` | Path to `config.toml` |

### Ocean account

Set a default payout address in `config.toml`:

```toml
[ocean]
address = "bc1q..."
```

Or press **`o`** in the dashboard to enter or change the address for the current session (session override takes priority over config).

The **DATUM Mining** panel shows:

- **Hashrate** — your 60s / 5min hashrate vs pool, shares, and % of pool
- **TIDES window** — your share of the current TIDES window
- **Earnings & Payouts** — est. per day, unpaid balance, next block estimate, lifetime (30d)
- **Blocks earned (TIDES)** — pool blocks you earned from in the last 30 days
- **Blocks found by you** — blocks your workers actually solved (paginated Ocean API)
- **Workers hashing** — active workers with non-zero hashrate

Ocean stats are fetched from the public [Ocean API](https://api.ocean.xyz) and cached for 60 seconds. The blocks-found count uses a separate 5-minute cache to avoid hammering the API on every refresh.

## Performance

Auto-refresh is tuned to stay responsive on a live node:

| Resource | Auto-refresh | Manual |
|----------|--------------|--------|
| UTXO set (`gettxoutsetinfo`) | Skipped | `u` (background thread, ~2 min) |
| Block Template / Mempool Glass | 30s cache | `t` (full GBT fetch) |
| BIP-110 block table | Only when chain tip changes | `r` |
| Ocean blocks-found count | 5 min cache | `r` after cache expires |

Press **`r`** for a light refresh of sync, peers, mempool, DATUM, and Ocean hashrate. Use **`t`** and **`u`** only when you need heavy RPC data.

## Mempool Glass
<img width="901" height="368" alt="image" src="https://github.com/user-attachments/assets/b4e40f9a-1614-4047-b687-a853fed352d8" />

Analyzes the **current Block Template** (`getblocktemplate`) — the transactions your Knots+BIP-110 node would include in the next block. It does not sample the mempool.

Categories:

- **Economic / Clean** — no spam signals
- **Consolidations** — many inputs, few outputs
- **Coinjoins** — coinjoin patterns
- **Spam / Inscriptions** — inscriptions, large witness, OP_RETURN, BIP-110 violations

Displays: `Based on Block Template #HEIGHT · N txs · X% max weight`

## Block Template
<img width="892" height="255" alt="image" src="https://github.com/user-attachments/assets/d5d7818e-3903-4dc4-8479-de010e2581db" />


Compact GBT summary (height, txs, weight, coinbase, fees) and **top 5** transactions by fee rate. Press `t` to refresh.

## DATUM
<img width="895" height="390" alt="image" src="https://github.com/user-attachments/assets/ff5df15e-edae-4610-8936-0f49849d9fbf" />


```bash
sudo systemctl enable --now datum
```

In `bitcoin.conf`:

```
blocknotify=killall -USR1 datum_gateway
```

## tmux

```bash
tmux new -s oraculo 'oraculovision'
```

## Project structure

```
oraculovision/
├── main.py                 # Entry point
├── pyproject.toml          # Package metadata and install
├── config.example.toml     # Example configuration
├── requirements.txt        # Dependencies (reference)
├── install-shortcut.sh     # Global shortcut script
└── oraculovision/          # Python package
    ├── app.py              # Main Textual application
    ├── config.py           # Configuration loader
    ├── analysis/           # BIP-110, spam score, mempool
    ├── data/               # bitcoin-cli, DATUM, Ocean API
    ├── screens/            # Modals and help
    ├── services/           # Block template service
    ├── utils/              # Utilities (clipboard)
    └── widgets/            # Dashboard panels
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `bitcoin-cli not found` | Install Knots or set `BITCOIN_CLI` |
| Slow UTXO set | `gettxoutsetinfo` takes ~2 min; press `u` only when needed |
| Dashboard stutters on refresh | Use `r` for light refresh; reserve `t` and `u` for heavy RPCs |
| Slow Mempool Glass | Normal with ~1000 GBT txs (~2s); use `t` only when needed |
| Ocean stats missing | Set `[ocean].address` or press `o`; check network to api.ocean.xyz |
| Copy hash fails | Install `wl-copy` or `xclip` |
| Node uses ~5–8 GB RAM | Normal for a full Knots node with active mempool |

## License

MIT — see [LICENSE](LICENSE).
