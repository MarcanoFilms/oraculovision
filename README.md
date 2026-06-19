# OraculoVision
<img width="1920" height="1056" alt="image" src="https://github.com/user-attachments/assets/31233dd5-727b-44ec-90f8-2bb2b4364287" />

Terminal dashboard (TUI) for sovereign operators running **Bitcoin Knots** with **BIP-110** enabled and **DATUM** for solo mining.

Philosophy: **Don't Trust, Verify**.

## Features

| Panel | Description |
|-------|-------------|
| **Node Status** | Sync, peers, mempool, UTXO set + growth, alerts |
| **BIP-110 Detector** | Spam score, status, miner tags, navigable table |
| **Block Detail Modal** | Full per-block detail (Enter) |
| **DATUM Mining** | Gateway, workers, hashrate, shares |
| **Mempool Glass** | **Real Block Template** composition (all GBT txs) |
| **Block Template** | Compact GBT summary + top 5 fee rates |
| **Live Metrics** | Mempool and peer charts |

## Requirements

- Python 3.11+
- [Bitcoin Knots](https://bitcoinknots.org/) with RPC available via `bitcoin-cli`
- (Optional) [DATUM Gateway](https://github.com/OCEAN-xyz/datum_gateway) for the mining panel

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

### Global

| Key | Action |
|-----|--------|
| `r` | Refresh all panels |
| `t` | Refresh Block Template + Mempool Glass |
| `q` | Quit |
| `?` | Full help screen |
| `Tab` | Move focus between panels |

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

## Visual alerts

- **Red border** on Node Status — low peer count
- **Yellow border** on Node Status — congested mempool
- **Red border** on BIP-110 — high-spam tip block
- **Red border** on Mempool Glass — >30% spam weight
- **Top banner** — summary of active alerts

## Configuration

OraculoVision looks for configuration in this order:

1. `ORACULOVISION_CONFIG` environment variable
2. `~/.config/oraculovision/config.toml`
3. `config.toml` in the project root

See `config.example.toml` for all available options.

### Environment variables

| Variable | Description |
|----------|-------------|
| `BITCOIN_CLI` | Path to `bitcoin-cli` |
| `BITCOIN_DATADIR` | Node data directory |
| `DATUM_API_URL` | DATUM API (default `http://127.0.0.1:7152`) |
| `DATUM_CONFIG` | Path to DATUM gateway JSON config |
| `ORACULOVISION_CONFIG` | Path to `config.toml` |

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
    ├── data/               # bitcoin-cli and DATUM
    ├── screens/            # Modals and help
    ├── services/           # Block template service
    ├── utils/              # Utilities (clipboard)
    └── widgets/            # Dashboard panels
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `bitcoin-cli not found` | Install Knots or set `BITCOIN_CLI` |
| Slow UTXO set | `gettxoutsetinfo` takes ~2 min; cached for 30 min |
| Slow Mempool Glass | Normal with ~1000 GBT txs (~2s); use `t` only when needed |
| Copy hash fails | Install `wl-copy` or `xclip` |

## License

MIT — see [LICENSE](LICENSE).
