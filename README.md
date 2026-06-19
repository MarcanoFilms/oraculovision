# OraculoVision

Dashboard de terminal (TUI) para operadores soberanos que corren **Bitcoin Knots** con **BIP-110** activado y **DATUM** para mining propio.

Filosofía: **Don't Trust, Verify**.

## Características

| Panel | Descripción |
|-------|-------------|
| **Node Status** | Sync, peers, mempool, UTXO set + crecimiento, alertas |
| **BIP-110 Detector** | Spam score, status, miner tags, tabla navegable |
| **Block Detail Modal** | Detalle completo por bloque (Enter) |
| **DATUM Mining** | Gateway, workers, hashrate, shares |
| **Mempool Glass** | Composición del **Block Template real** (todas las txs GBT) |
| **Block Template** | Resumen GBT compacto + top 5 fee rates |
| **Live Metrics** | Gráficos mempool y peers |

## Requisitos

- Python 3.11+
- [Bitcoin Knots](https://bitcoinknots.org/) con RPC accesible vía `bitcoin-cli`
- (Opcional) [DATUM Gateway](https://github.com/OCEAN-xyz/datum_gateway) para el panel de mining

## Instalación

### Desde el repositorio

```bash
git clone https://github.com/MarcanoFilms/oraculovision.git
cd oraculovision
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Configuración

```bash
cp config.example.toml ~/.config/oraculovision/config.toml
# Edita el archivo según tu entorno
mkdir -p ~/.config/oraculovision   # si el directorio no existe
```

También puedes colocar `config.toml` en la raíz del proyecto para desarrollo local.

### Ejecución

```bash
oraculovision
# o
python main.py
```

### Atajo global (opcional)

```bash
./install-shortcut.sh
```

Esto crea `~/.local/bin/oraculovision` apuntando al entorno virtual del proyecto.

## Atajos de teclado

### Global

| Tecla | Acción |
|-------|--------|
| `r` | Refrescar todos los paneles |
| `t` | Refrescar Block Template + Mempool Glass |
| `q` | Salir |
| `?` | Pantalla de ayuda completa |
| `Tab` | Cambiar foco entre paneles |

### BIP-110 Detector

| Tecla | Acción |
|-------|--------|
| `↑` `↓` | Navegar tabla de bloques |
| `Enter` | Abrir modal de detalle del bloque |

### Modal de bloque

| Tecla | Acción |
|-------|--------|
| `c` | Copiar hash al portapapeles |
| `Esc` | Cerrar |

## Alertas visuales

- **Borde rojo** en Node Status — pocos peers
- **Borde amarillo** en Node Status — mempool congestionado
- **Borde rojo** en BIP-110 — bloque tip con alto spam
- **Borde rojo** en Mempool Glass — >30% peso spam
- **Banner superior** — resumen de alertas activas

## Configuración

OraculoVision busca configuración en este orden:

1. Variable de entorno `ORACULOVISION_CONFIG`
2. `~/.config/oraculovision/config.toml`
3. `config.toml` en la raíz del proyecto

Consulta `config.example.toml` para todas las opciones disponibles.

### Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `BITCOIN_CLI` | Ruta a `bitcoin-cli` |
| `BITCOIN_DATADIR` | Datadir del nodo |
| `DATUM_API_URL` | API DATUM (default `http://127.0.0.1:7152`) |
| `DATUM_CONFIG` | Ruta al JSON de configuración de DATUM |
| `ORACULOVISION_CONFIG` | Ruta al `config.toml` |

## Mempool Glass

Analiza el **Block Template actual** (`getblocktemplate`) — las transacciones que tu nodo Knots+BIP-110 incluiría en el próximo bloque. No usa muestra del mempool.

Categorías:

- **Economic / Clean** — sin señales spam
- **Consolidations** — muchas entradas, pocas salidas
- **Coinjoins** — patrones coinjoin
- **Spam / Inscriptions** — inscriptions, witness grande, OP_RETURN, violaciones BIP-110

Muestra: `Basado en Block Template #HEIGHT · N txs · X% peso máximo`

## Block Template

Panel compacto con resumen GBT (height, txs, weight, coinbase, fees) y **top 5** transacciones por fee rate. Refrescar con `t`.

## DATUM

```bash
sudo systemctl enable --now datum
```

En `bitcoin.conf`:

```
blocknotify=killall -USR1 datum_gateway
```

## tmux

```bash
tmux new -s oraculo 'oraculovision'
```

## Estructura del proyecto

```
oraculovision/
├── main.py                 # Punto de entrada
├── pyproject.toml          # Metadatos e instalación
├── config.example.toml     # Configuración de ejemplo
├── requirements.txt        # Dependencias (referencia)
├── install-shortcut.sh     # Script de atajo global
└── oraculovision/          # Paquete Python
    ├── app.py              # Aplicación Textual principal
    ├── config.py           # Cargador de configuración
    ├── analysis/           # BIP-110, spam score, mempool
    ├── data/               # bitcoin-cli y DATUM
    ├── screens/            # Modales y ayuda
    ├── services/           # Block template service
    ├── utils/              # Utilidades (clipboard)
    └── widgets/            # Paneles del dashboard
```

## Troubleshooting

| Problema | Solución |
|----------|----------|
| `bitcoin-cli no encontrado` | Instala Knots o define `BITCOIN_CLI` |
| UTXO set lento | `gettxoutsetinfo` tarda ~2min; se cachea 30min |
| Mempool Glass lento | Normal con ~1000 txs GBT (~2s); usa `t` solo cuando necesites |
| Copiar hash falla | Instala `wl-copy` o `xclip` |

## Licencia

MIT — ver [LICENSE](LICENSE) si está incluido en el repositorio.