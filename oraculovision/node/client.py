"""Read-only and write-gated bitcoin-cli client."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from oraculovision.node.security import (
    resolve_bitcoin_cli,
    validate_rpc_host,
    validate_rpc_method,
    validate_safe_path_token,
    validate_ssh_target,
    validate_write_rpc_method,
)


class BitcoinCLIError(Exception):
    """Raised when bitcoin-cli fails or is unavailable."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        self.hint = hint
        super().__init__(message)


class NodeClient:
    """Thin wrapper around bitcoin-cli JSON-RPC.

    Read methods use ``call()``. Write methods use ``call_write()`` and should
    only be invoked through ``ControlGate`` after user confirmation.
    """

    def __init__(
        self,
        cli_path: str | None = None,
        datadir: str | None = None,
        *,
        rpcconnect: str | None = None,
        rpcport: int | None = None,
        rpcuser: str | None = None,
        rpcpassword: str | None = None,
        ssh_target: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        try:
            self._cli_inner = resolve_bitcoin_cli(
                cli_path or os.environ.get("BITCOIN_CLI", "bitcoin-cli"),
            )
            self.datadir = validate_safe_path_token(
                datadir or os.environ.get("BITCOIN_DATADIR") or "",
                name="datadir",
                allow_empty=True,
            )
            self.rpcconnect = validate_rpc_host(
                rpcconnect or os.environ.get("BITCOIN_RPCCONNECT") or "",
            )
            self.rpcport = int(rpcport) if rpcport else None
            if self.rpcport is not None and not (1 <= self.rpcport <= 65535):
                raise ValueError("rpcport must be between 1 and 65535")
            self.rpcuser = validate_safe_path_token(
                rpcuser or os.environ.get("BITCOIN_RPCUSER") or "",
                name="rpcuser",
                allow_empty=True,
            )
            self.rpcpassword = validate_safe_path_token(
                rpcpassword or os.environ.get("BITCOIN_RPCPASSWORD") or "",
                name="rpcpassword",
                allow_empty=True,
            )
            self.ssh_target = validate_ssh_target(
                ssh_target or os.environ.get("BITCOIN_SSH_TARGET") or "",
            )
        except ValueError as exc:
            raise BitcoinCLIError(str(exc)) from exc
        self.timeout = timeout

    @property
    def cli_path(self) -> str:
        """Executable shown in errors — SSH wrapper or local bitcoin-cli."""
        if self.ssh_target:
            return f"ssh {self.ssh_target} -- {self._cli_inner}"
        return self._cli_inner

    def _base_cmd(self) -> list[str]:
        cmd = [self._cli_inner]
        if self.datadir:
            cmd.extend(["-datadir", self.datadir])
        if self.rpcconnect:
            cmd.extend(["-rpcconnect", self.rpcconnect])
        if self.rpcport is not None:
            cmd.extend(["-rpcport", str(self.rpcport)])
        if self.rpcuser:
            cmd.extend(["-rpcuser", self.rpcuser])
        if self.rpcpassword:
            cmd.extend(["-rpcpassword", self.rpcpassword])
        if self.ssh_target:
            return ["ssh", self.ssh_target, "--", *cmd]
        return cmd

    def call(self, method: str, *params: Any) -> Any:
        """Execute a read-only RPC call."""
        try:
            method = validate_rpc_method(method)
        except ValueError as exc:
            raise BitcoinCLIError(str(exc)) from exc
        return self._execute(method, params)

    def call_write(self, method: str, *params: Any) -> Any:
        """Execute an allowlisted write RPC (requires ControlGate)."""
        try:
            method = validate_write_rpc_method(method)
        except ValueError as exc:
            raise BitcoinCLIError(str(exc)) from exc
        return self._execute(method, params)

    def _execute(self, method: str, params: tuple[Any, ...]) -> Any:
        cmd = self._base_cmd() + [method]
        for param in params:
            if isinstance(param, (dict, list)):
                cmd.append(json.dumps(param))
            elif isinstance(param, bool):
                cmd.append("true" if param else "false")
            else:
                cmd.append(str(param))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise BitcoinCLIError(
                f"Timeout calling {method} ({self.timeout}s)",
                hint="The node may be busy or unresponsive.",
            ) from exc
        except FileNotFoundError as exc:
            raise BitcoinCLIError(
                f"bitcoin-cli not found: {self.cli_path}",
                hint="Check your Knots/Core installation.",
            ) from exc

        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            hint = self._error_hint(stderr, method)
            raise BitcoinCLIError(stderr or f"Error in {method}", hint=hint)

        stdout = result.stdout.strip()
        if not stdout:
            return None
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return stdout

    @staticmethod
    def _error_hint(stderr: str, method: str) -> str | None:
        lower = stderr.lower()
        if "could not connect" in lower or "connection refused" in lower:
            return "Start bitcoind/knots and check RPC (bitcoin.conf)."
        if "verifying blocks" in lower or "initial block download" in lower:
            return "Node still syncing. Wait for IBD to finish."
        if "not available" in lower and method == "getblocktemplate":
            return "Enable mining RPC or use a node that supports getblocktemplate."
        if method == "getrawtransaction" and (
            "no such mempool transaction" in lower
            or "not found" in lower
            or "pruned" in lower
        ):
            return (
                "Pruned nodes need block context or txindex=1 on a full node. "
                "Inspect txs from Block Explorer/Mempool Glass when possible."
            )
        return None

    # --- Read-only convenience methods ---

    def get_blockchain_info(self) -> dict[str, Any]:
        return self.call("getblockchaininfo")

    def get_network_info(self) -> dict[str, Any]:
        return self.call("getnetworkinfo")

    def get_mempool_info(self) -> dict[str, Any]:
        return self.call("getmempoolinfo")

    def get_block_count(self) -> int:
        return int(self.call("getblockcount"))

    def get_block_hash(self, height: int) -> str:
        return str(self.call("getblockhash", height))

    def get_block(self, block_hash: str, verbosity: int = 2) -> dict[str, Any]:
        return self.call("getblock", block_hash, verbosity)

    def get_block_stats(self, block_hash: str) -> dict[str, Any]:
        try:
            return self.call("getblockstats", block_hash)
        except BitcoinCLIError:
            return {}

    def get_raw_mempool(self, verbose: bool = False) -> list[str] | dict[str, Any]:
        result = self.call("getrawmempool", verbose)
        if verbose:
            return result if isinstance(result, dict) else {}
        return result if isinstance(result, list) else []

    def get_raw_transaction(
        self,
        txid: str,
        verbose: bool = True,
        *,
        block_hash: str | None = None,
    ) -> dict[str, Any]:
        if block_hash:
            return self.call("getrawtransaction", txid, verbose, block_hash)
        return self.call("getrawtransaction", txid, verbose)

    def get_txoutset_info(self, timeout: float | None = None) -> dict[str, Any]:
        old_timeout = self.timeout
        if timeout is not None:
            self.timeout = timeout
        try:
            return self.call("gettxoutsetinfo")
        finally:
            self.timeout = old_timeout

    def get_index_info(self) -> dict[str, Any]:
        """Return index status (txindex, blockfilterindex, etc.).

        Available since Bitcoin Core 0.21 / Knots 21+.
        Returns an empty dict on older nodes or pruned nodes without txindex.
        """
        try:
            result = self.call("getindexinfo")
            return result if isinstance(result, dict) else {}
        except BitcoinCLIError:
            return {}

    def get_block_template(self) -> dict[str, Any]:
        return self.call("getblocktemplate", {"rules": ["segwit"]})

    def decode_raw_transaction(self, hex_data: str) -> dict[str, Any]:
        return self.call("decoderawtransaction", hex_data)

    def get_peer_info(self) -> list[dict[str, Any]]:
        result = self.call("getpeerinfo")
        return result if isinstance(result, list) else []

    def list_banned(self) -> list[dict[str, Any]]:
        result = self.call("listbanned")
        return result if isinstance(result, list) else []

    def get_node_info(self) -> dict[str, Any]:
        """Knots-specific node info (falls back gracefully on Core)."""
        try:
            return self.call("getnodeinfo")
        except BitcoinCLIError:
            return {}

    def validate_address(self, address: str) -> dict[str, Any]:
        result = self.call("validateaddress", address)
        return result if isinstance(result, dict) else {}

    def scantxoutset_address(
        self,
        address: str,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        old_timeout = self.timeout
        if timeout is not None:
            self.timeout = timeout
        try:
            result = self.call("scantxoutset", "start", [f"addr({address})"])
            return result if isinstance(result, dict) else {}
        finally:
            self.timeout = old_timeout

    def get_net_totals(self) -> dict[str, Any]:
        """Return cumulative network traffic stats (totalbytessent, totalbytesrecv)."""
        result = self.call("getnettotals")
        return result if isinstance(result, dict) else {}

    def is_available(self) -> tuple[bool, str | None]:
        try:
            self.get_block_count()
            return True, None
        except BitcoinCLIError as exc:
            msg = str(exc)
            if exc.hint:
                msg = f"{msg}\n→ {exc.hint}"
            return False, msg