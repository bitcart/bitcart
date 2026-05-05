"""LND process lifecycle management, binary management, and port allocation.

This module handles:
- Starting/stopping LND subprocesses with proper command-line arguments
- Downloading the LND binary if not found on PATH
- Allocating and persisting port assignments for multiple LND instances
"""

import asyncio
import hashlib
import json
import os
import platform
import shutil
import signal
import tarfile
import tempfile

from logger import get_logger

logger = get_logger(__name__)

LND_VERSION = "v0.20.1-beta"

# GitHub release URL pattern for LND binaries
LND_RELEASE_URL = (
    "https://github.com/lightningnetwork/lnd/releases/download/{version}/"
    "lnd-{os}-{arch}-{version}.tar.gz"
)


def seed_to_wallet_key(seed: str) -> str:
    """Derive a deterministic wallet key from a seed phrase.

    Uses SHA-256 hash truncated to 16 hex characters. This serves as
    the directory name and dictionary key for the wallet.

    Args:
        seed: The mnemonic seed phrase (space-separated words)

    Returns:
        16-character hex string derived from the seed
    """
    return hashlib.sha256(seed.strip().encode("utf-8")).hexdigest()[:16]


class LNDBinaryManager:
    """Manages the LND binary: finds on PATH or downloads from GitHub releases."""

    def __init__(self, data_path: str, version: str = LND_VERSION):
        self.data_path = data_path
        self.version = version
        self.bin_dir = os.path.join(data_path, ".lnd-bin")

    def _get_platform_info(self) -> tuple[str, str]:
        """Detect OS and architecture for binary download.

        Returns:
            Tuple of (os_name, arch) matching LND release naming convention
        """
        system = platform.system().lower()
        machine = platform.machine().lower()
        os_name = {"linux": "linux", "darwin": "darwin", "windows": "windows"}.get(system)
        if not os_name:
            raise RuntimeError(f"Unsupported OS: {system}")
        arch_map = {
            "x86_64": "amd64",
            "amd64": "amd64",
            "aarch64": "arm64",
            "arm64": "arm64",
        }
        arch = arch_map.get(machine)
        if not arch:
            raise RuntimeError(f"Unsupported architecture: {machine}")
        return os_name, arch

    async def find_or_download(self) -> str:
        """Find LND binary on PATH or download it.

        Returns:
            Absolute path to the lnd binary

        Raises:
            RuntimeError: If download fails or binary is not functional
        """
        # Check if already downloaded to our bin dir
        local_bin = os.path.join(self.bin_dir, "lnd")
        if os.path.isfile(local_bin) and os.access(local_bin, os.X_OK):
            logger.info(f"Using cached LND binary: {local_bin}")
            return local_bin
        # Check PATH
        system_bin = shutil.which("lnd")
        if system_bin:
            logger.info(f"Found LND on PATH: {system_bin}")
            return system_bin
        # Download
        logger.info(f"LND binary not found, downloading {self.version}...")
        return await self._download()

    async def _download(self) -> str:
        """Download LND binary from GitHub releases.

        Returns:
            Path to the downloaded and extracted binary
        """
        os_name, arch = self._get_platform_info()
        url = LND_RELEASE_URL.format(version=self.version, os=os_name, arch=arch)
        os.makedirs(self.bin_dir, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            # Use asyncio subprocess to download with curl
            proc = await asyncio.create_subprocess_exec(
                "curl", "-sL", "-o", tmp_path, url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"Failed to download LND: {stderr.decode()}")
            # Extract the lnd binary from the tarball
            with tarfile.open(tmp_path, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith("/lnd") or member.name == "lnd":
                        member.name = "lnd"  # flatten path
                        tar.extract(member, self.bin_dir)
                        break
                else:
                    raise RuntimeError("lnd binary not found in tarball")
        finally:
            os.unlink(tmp_path)
        bin_path = os.path.join(self.bin_dir, "lnd")
        os.chmod(bin_path, 0o755)
        # Verify the binary works
        proc = await asyncio.create_subprocess_exec(
            bin_path, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        logger.info(f"Downloaded LND: {stdout.decode().strip()}")
        return bin_path


class PortManager:
    """Allocates and persists port assignments for LND wallet instances.

    Port mappings are stored in a JSON file so they survive daemon restarts.
    Each wallet gets three ports: gRPC, REST, and P2P (lightning peer).
    On initialization, stale entries (wallet dirs that no longer exist) are pruned.
    Port allocation checks that ports are not already bound by another process.
    """

    BASE_GRPC_PORT = 10009
    BASE_REST_PORT = 8080
    BASE_P2P_PORT = 9735

    def __init__(self, data_path: str):
        self.data_path = data_path
        self.port_map_path = os.path.join(data_path, "port_map.json")
        self.port_map: dict[str, dict[str, int]] = {}
        self.lock = asyncio.Lock()
        self._load()
        self._prune_stale_entries()

    def _load(self):
        """Load port allocations from disk."""
        if os.path.exists(self.port_map_path):
            try:
                with open(self.port_map_path) as f:
                    self.port_map = json.load(f)
            except (json.JSONDecodeError, OSError):
                logger.warning("Failed to load port_map.json, starting fresh")
                self.port_map = {}

    def _prune_stale_entries(self):
        """Remove port allocations for wallets whose data directories no longer exist.

        Also removes entries for temporary seed-generation keys (prefixed with _).
        """
        wallets_dir = os.path.join(self.data_path, "wallets")
        stale_keys = []
        for wallet_key in list(self.port_map.keys()):
            # Always remove temp keys from seed generation
            if wallet_key.startswith("_"):
                stale_keys.append(wallet_key)
                continue
            # Remove if wallet directory no longer exists
            wallet_dir = os.path.join(wallets_dir, wallet_key)
            if not os.path.isdir(wallet_dir):
                stale_keys.append(wallet_key)
        if stale_keys:
            for key in stale_keys:
                del self.port_map[key]
            self._save()
            logger.info(f"Pruned {len(stale_keys)} stale port allocations")

    def _save(self):
        """Persist port allocations to disk."""
        os.makedirs(os.path.dirname(self.port_map_path), exist_ok=True)
        with open(self.port_map_path, "w") as f:
            json.dump(self.port_map, f, indent=2)

    @staticmethod
    def _is_port_in_use(port: int) -> bool:
        """Check if a port is currently bound by any process."""
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return False
            except OSError:
                return True

    def _next_available(self, base: int, used: set[int], max_attempts: int = 100) -> int:
        """Find the next available port starting from base.

        Skips ports that are in the used set or already bound by another process.
        Limits search to max_attempts to avoid infinite loops.
        """
        port = base
        for _ in range(max_attempts):
            if port not in used and not self._is_port_in_use(port):
                return port
            port += 1
        raise RuntimeError(f"Could not find available port after {max_attempts} attempts starting from {base}")

    async def allocate(self, wallet_key: str) -> dict[str, int]:
        """Allocate ports for a wallet instance.

        If the wallet already has ports assigned, returns them (after
        verifying they are not in use by another process).
        Otherwise assigns the next available ports.

        Args:
            wallet_key: Unique identifier for the wallet

        Returns:
            Dict with keys: grpc, rest, p2p, tor_socks, tor_control
        """
        async with self.lock:
            if wallet_key in self.port_map:
                entry = self.port_map[wallet_key]
                check_keys = [k for k in ("grpc", "rest", "p2p") if k in entry]
                if not any(self._is_port_in_use(entry[k]) for k in check_keys):
                    # Ensure tor ports exist (for wallets created before tor support)
                    if "tor_socks" not in entry:
                        used_socks = {v.get("tor_socks", 0) for v in self.port_map.values()}
                        used_ctrl = {v.get("tor_control", 0) for v in self.port_map.values()}
                        entry["tor_socks"] = self._next_available(TorProcess.BASE_SOCKS_PORT, used_socks)
                        entry["tor_control"] = self._next_available(TorProcess.BASE_CONTROL_PORT, used_ctrl)
                        self._save()
                    return entry
                logger.warning(
                    f"Ports for {wallet_key} are in use, reallocating"
                )
                del self.port_map[wallet_key]
            used_grpc = {v["grpc"] for v in self.port_map.values()}
            used_rest = {v["rest"] for v in self.port_map.values()}
            used_p2p = {v["p2p"] for v in self.port_map.values()}
            used_socks = {v.get("tor_socks", 0) for v in self.port_map.values()}
            used_ctrl = {v.get("tor_control", 0) for v in self.port_map.values()}
            entry = {
                "grpc": self._next_available(self.BASE_GRPC_PORT, used_grpc),
                "rest": self._next_available(self.BASE_REST_PORT, used_rest),
                "p2p": self._next_available(self.BASE_P2P_PORT, used_p2p),
                "tor_socks": self._next_available(TorProcess.BASE_SOCKS_PORT, used_socks),
                "tor_control": self._next_available(TorProcess.BASE_CONTROL_PORT, used_ctrl),
            }
            self.port_map[wallet_key] = entry
            self._save()
            return entry

    async def release(self, wallet_key: str):
        """Release port allocation for a wallet."""
        async with self.lock:
            if wallet_key in self.port_map:
                del self.port_map[wallet_key]
                self._save()


def is_tor_available() -> bool:
    """Check if the Tor binary is available on the system."""
    return shutil.which("tor") is not None


class TorProcess:
    """Manages a Tor subprocess for a single LND wallet instance.

    Each LND wallet gets its own Tor instance with a dedicated data directory,
    SOCKS port, and control port. This provides isolation between wallets.
    """

    # Use well-separated ranges so SOCKS and control ports never collide
    BASE_SOCKS_PORT = 19050     # SOCKS ports: 19050, 19051, 19052, ...
    BASE_CONTROL_PORT = 19150   # Control ports: 19150, 19151, 19152, ...

    def __init__(self, data_dir: str, socks_port: int, control_port: int, p2p_port: int):
        self.data_dir = data_dir
        self.tor_dir = os.path.join(data_dir, "tor")
        self.socks_port = socks_port
        self.control_port = control_port
        self.p2p_port = p2p_port
        self.hidden_service_dir = os.path.join(self.tor_dir, "hidden_service")
        self.process: asyncio.subprocess.Process | None = None
        from collections import deque

        self.log_buffer: deque[dict] = deque(maxlen=200)

    def _write_torrc(self) -> str:
        """Write torrc with a hidden service that forwards to LND's P2P port.

        The hidden service is configured directly in the torrc so that LND
        does not need any --tor.* flags. This avoids the issue where LND's
        --tor.socks routes DNS seed resolution through Tor, preventing
        neutrino from discovering peers.
        """
        os.makedirs(self.tor_dir, exist_ok=True)
        os.makedirs(self.hidden_service_dir, mode=0o700, exist_ok=True)
        # Tor requires HiddenServiceDir to be 0700
        os.chmod(self.hidden_service_dir, 0o700)
        torrc_path = os.path.join(self.tor_dir, "torrc")
        with open(torrc_path, "w") as f:
            f.write(
                f"SocksPort {self.socks_port}\n"
                f"ControlPort {self.control_port}\n"
                f"DataDirectory {self.tor_dir}/data\n"
                f"CookieAuthentication 1\n"
                f"Log notice stderr\n"
                f"HiddenServiceDir {self.hidden_service_dir}\n"
                f"HiddenServicePort {self.p2p_port} 127.0.0.1:{self.p2p_port}\n"
            )
        return torrc_path

    def get_onion_hostname(self) -> str:
        """Read the .onion hostname generated by Tor for this hidden service.

        Returns:
            The .onion hostname string, or empty string if not available.
        """
        hostname_file = os.path.join(self.hidden_service_dir, "hostname")
        try:
            with open(hostname_file) as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""

    async def start(self) -> bool:
        """Start the Tor subprocess.

        Kills any stale process occupying our ports before starting.

        Returns:
            True if Tor bootstrapped successfully, False otherwise.
        """
        # Kill any stale process on our ports from a previous run
        self._kill_stale_port_holders()
        torrc_path = self._write_torrc()
        os.makedirs(os.path.join(self.tor_dir, "data"), exist_ok=True)
        self.process = await asyncio.create_subprocess_exec(
            "tor", "-f", torrc_path,
            stdout=asyncio.subprocess.DEVNULL,  # Tor logs to stderr; ignore stdout to prevent pipe blocking
            stderr=asyncio.subprocess.PIPE,
        )
        # Wait for Tor to bootstrap
        logger.info(f"Starting Tor (SOCKS={self.socks_port}, Control={self.control_port})...")
        return await self._wait_for_bootstrap()

    def _kill_stale_port_holders(self):
        """Kill any previous Tor process using our data directory or ports.

        Tor locks its data directory, so a stale process from a previous run
        will prevent a new Tor from starting even if ports are free.
        """
        import subprocess

        # Kill by data directory match (covers cases where port is released but lock held)
        torrc_path = os.path.join(self.tor_dir, "torrc")
        try:
            result = subprocess.run(
                ["pgrep", "-f", f"tor.*-f.*{torrc_path}"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                for pid in result.stdout.strip().split("\n"):
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                    except (ProcessLookupError, ValueError):
                        pass
                import time
                time.sleep(1)  # give it time to exit
                # Force kill if still alive
                for pid in result.stdout.strip().split("\n"):
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                    except (ProcessLookupError, ValueError):
                        pass
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        # Also kill by port
        for port in (self.socks_port, self.control_port):
            try:
                result = subprocess.run(
                    ["lsof", "-ti", f":{port}"],
                    capture_output=True, text=True, timeout=5
                )
                if result.stdout.strip():
                    for pid in result.stdout.strip().split("\n"):
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                        except (ProcessLookupError, ValueError):
                            pass
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        # Remove stale lock file if it exists
        lock_file = os.path.join(self.tor_dir, "data", "lock")
        if os.path.exists(lock_file):
            try:
                os.unlink(lock_file)
            except OSError:
                pass

    async def _wait_for_bootstrap(self, timeout: int = 120) -> bool:
        """Wait for Tor to fully bootstrap (100% circuit establishment).

        Reads Tor's stderr output to detect the "Bootstrapped 100%" message,
        which indicates Tor has established circuits and is ready to proxy traffic.
        This is critical because LND will crash if it tries to use Tor's SOCKS
        proxy before circuits are established.

        Returns:
            True if bootstrap completed, False if timed out or failed.
        """
        logger.info("Waiting for Tor to fully bootstrap...")
        bootstrap_complete = asyncio.Event()

        async def _read_tor_output():
            """Read Tor's stderr and detect bootstrap completion."""
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    logger.debug(f"Tor: {text}")
                    self.log_buffer.append({
                        "text": text,
                        "level": self._parse_tor_log_level(text),
                        "source": "tor",
                    })
                    if "Bootstrapped 100%" in text:
                        bootstrap_complete.set()
                        return

        reader_task = asyncio.create_task(_read_tor_output())
        success = False
        try:
            await asyncio.wait_for(bootstrap_complete.wait(), timeout=timeout)
            logger.info("Tor is ready (fully bootstrapped)")
            success = True
        except asyncio.TimeoutError:
            logger.warning(f"Tor bootstrap did not complete within {timeout}s, killing Tor process")
            await self.stop()
        finally:
            reader_task.cancel()
            if success:
                # Continue reading stderr in background (don't block)
                asyncio.create_task(self._drain_tor_output())
        return success

    def _parse_tor_log_level(self, text: str) -> str:
        """Extract log level from a Tor log line."""
        if "[err]" in text:
            return "ERR"
        if "[warn]" in text:
            return "WRN"
        if "[notice]" in text:
            return "INF"
        return "INF"

    async def _drain_tor_output(self):
        """Continue reading Tor's stderr in background, buffering for the status UI."""
        try:
            while self.process and self.process.returncode is None:
                line = await self.process.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    self.log_buffer.append({
                        "text": text,
                        "level": self._parse_tor_log_level(text),
                        "source": "tor",
                    })
        except (asyncio.CancelledError, Exception):
            pass

    async def stop(self, timeout: int = 10):
        """Stop the Tor subprocess."""
        if not self.process or self.process.returncode is not None:
            return
        try:
            self.process.terminate()
            await asyncio.wait_for(self.process.wait(), timeout=timeout)
        except (asyncio.TimeoutError, ProcessLookupError):
            try:
                self.process.kill()
                await self.process.wait()
            except ProcessLookupError:
                pass

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.returncode is None


class LNDProcess:
    """Manages a single LND subprocess.

    Handles starting LND with the correct command-line arguments,
    waiting for it to be ready (TLS cert + macaroon files exist),
    graceful shutdown, and crash monitoring with restart.
    When Tor is available, runs in hybrid mode (clearnet + Tor).
    """

    MAX_RESTARTS = 5
    RESTART_BACKOFF_BASE = 2  # seconds, doubles each restart

    def __init__(
        self,
        lnd_binary: str,
        data_dir: str,
        network: str,
        grpc_port: int,
        rest_port: int,
        p2p_port: int,
        neutrino_peers: list[str],
        extra_args: str = "",
        debug: bool = False,
        external_ip: str = "",
        tor_onion_hostname: str = "",
    ):
        self.lnd_binary = lnd_binary
        self.data_dir = data_dir
        self.network = network
        self.grpc_port = grpc_port
        self.rest_port = rest_port
        self.p2p_port = p2p_port
        self.neutrino_peers = neutrino_peers
        self.extra_args = extra_args
        self.debug = debug
        self.external_ip = external_ip
        self.tor_onion_hostname = tor_onion_hostname
        self.process: asyncio.subprocess.Process | None = None
        self.restart_count = 0
        self._monitor_task: asyncio.Task | None = None
        self._should_run = False
        # Circular buffer of recent log lines for the status UI
        from collections import deque

        self.log_buffer: deque[dict] = deque(maxlen=500)

    def _build_command(self) -> list[str]:
        """Build the LND command-line arguments.

        Returns:
            List of command-line arguments for the LND binary
        """
        # Map network name to LND bitcoin flag
        network_flags = {
            "mainnet": "--bitcoin.mainnet",
            "testnet3": "--bitcoin.testnet",
            "testnet4": "--bitcoin.testnet4",
            "signet": "--bitcoin.signet",
            "regtest": "--bitcoin.regtest",
        }
        network_flag = network_flags.get(self.network)
        if not network_flag:
            raise ValueError(f"Invalid LND network: {self.network}. Valid: {', '.join(network_flags)}")

        cmd = [
            self.lnd_binary,
            "--bitcoin.active",
            network_flag,
            "--bitcoin.node=neutrino",
            f"--rpclisten=127.0.0.1:{self.grpc_port}",
            "--norest",
            f"--listen=0.0.0.0:{self.p2p_port}",
            f"--lnddir={self.data_dir}",
            "--accept-keysend",
            "--accept-amp",
            "--gc-canceled-invoices-on-startup",
            "--gc-canceled-invoices-on-the-fly",
            "--tlsextradomain=localhost",
            "--tlsextraip=127.0.0.1",
            # Neutrino performance: persist filters to avoid re-download on restart
            "--neutrino.persistfilters",
            # Database: compact on startup to prevent unbounded growth
            "--db.bolt.auto-compact",
            # Disable LND's own file logging (we capture stdout/stderr)
            "--logging.file.disable",
            # Autopilot is disabled by default in LND — no flag needed
            # Enable wumbo channels (allows channels larger than ~0.167 BTC)
            "--protocol.wumbo-channels",
            # Fee estimation (required for neutrino on mainnet)
            "--fee.url=https://nodes.lightning.computer/fees/v1/btc-fee-estimates.json",
        ]
        # Tor onion service is managed externally by TorProcess (via torrc
        # HiddenServiceDir), so LND needs NO --tor.* flags. This avoids the
        # issue where --tor.socks routes DNS seed resolution through the Tor
        # SOCKS proxy, preventing neutrino from discovering peers.
        # The .onion address is advertised via --externalip instead.
        if self.tor_onion_hostname:
            cmd.append(f"--externalip={self.tor_onion_hostname}:{self.p2p_port}")
        # External IP/hostname for clearnet advertising
        if self.external_ip:
            cmd.append(f"--externalip={self.external_ip}:{self.p2p_port}")
        elif self.tor_onion_hostname:
            # With Tor onion, also enable NAT traversal so LND advertises
            # both the .onion and a clearnet address
            cmd.append("--nat")
        # Add neutrino peers
        for peer in self.neutrino_peers:
            if peer.strip():
                cmd.append(f"--neutrino.connect={peer.strip()}")
        # Debug level
        if self.debug:
            cmd.append("--debuglevel=debug")
        else:
            cmd.append("--debuglevel=info")
        # Extra args passed by user
        if self.extra_args:
            cmd.extend(self.extra_args.split())
        return cmd

    @property
    def tls_cert_path(self) -> str:
        """Path to the TLS certificate file."""
        return os.path.join(self.data_dir, "tls.cert")

    @property
    def macaroon_path(self) -> str:
        """Path to the admin macaroon file."""
        return os.path.join(
            self.data_dir, "data", "chain", "bitcoin", self.network, "admin.macaroon"
        )

    @property
    def wallet_db_path(self) -> str:
        """Path to the wallet database file."""
        return os.path.join(
            self.data_dir, "data", "chain", "bitcoin", self.network, "wallet.db"
        )

    @property
    def is_running(self) -> bool:
        """Check if the LND process is currently running."""
        return self.process is not None and self.process.returncode is None

    async def start(self):
        """Start the LND subprocess.

        Creates the data directory if needed and launches LND with
        stdout/stderr captured for logging.
        """
        os.makedirs(self.data_dir, exist_ok=True)
        cmd = self._build_command()
        logger.info(f"Starting LND: {' '.join(cmd[:5])}... (port {self.grpc_port})")
        self._should_run = True
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # Start background log reader tasks
        asyncio.create_task(self._read_output(self.process.stdout, "stdout"))
        asyncio.create_task(self._read_output(self.process.stderr, "stderr"))

    def _parse_lnd_log_level(self, text: str) -> str:
        """Extract log level from an LND log line."""
        for level in ("CRT", "ERR", "WRN", "INF", "DBG", "TRC"):
            if f"[{level}]" in text:
                return level
        return "INF"

    async def _read_output(self, stream, name: str):
        """Read and log output from LND subprocess, buffering for the status UI."""
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                level = self._parse_lnd_log_level(text)
                self.log_buffer.append({
                    "text": text,
                    "level": level,
                    "source": "lnd",
                })
                if self.debug:
                    logger.debug(f"LND [{name}]: {text}")
                elif level in ("ERR", "CRT"):
                    logger.error(f"LND: {text}")

    async def wait_for_ready(self, timeout: int = 180) -> bool:
        """Wait for LND to be ready (TLS cert exists and gRPC port is accepting connections).

        Checks both that the TLS cert file exists and that the gRPC port
        is actually accepting TCP connections. This avoids the race condition
        where the cert is written but LND crashes shortly after.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if LND is ready, False if timeout
        """
        import socket

        logger.info(f"Waiting for LND to be ready (timeout={timeout}s)...")
        cert_found = False
        for _ in range(timeout * 2):  # check every 0.5s
            if not self.is_running:
                logger.error("LND process exited before becoming ready")
                return False
            if not cert_found and os.path.exists(self.tls_cert_path):
                cert_found = True
                logger.info("LND TLS cert found, waiting for gRPC port...")
            if cert_found:
                # Verify gRPC port is actually accepting connections
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(1)
                        s.connect(("127.0.0.1", self.grpc_port))
                        logger.info(f"LND gRPC port {self.grpc_port} is ready")
                        return True
                except (ConnectionRefusedError, OSError):
                    pass  # port not ready yet
            await asyncio.sleep(0.5)
        logger.error(f"LND failed to become ready within {timeout}s")
        return False

    async def stop(self, timeout: int = 30):
        """Gracefully stop the LND process.

        Sends SIGTERM first, waits for the timeout, then SIGKILL if needed.
        """
        self._should_run = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
        if not self.process or self.process.returncode is not None:
            return
        logger.info(f"Stopping LND process (pid={self.process.pid})...")
        try:
            self.process.send_signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(self.process.wait(), timeout=timeout)
                logger.info("LND stopped gracefully")
            except asyncio.TimeoutError:
                logger.warning("LND did not stop gracefully, sending SIGKILL")
                self.process.kill()
                await self.process.wait()
        except ProcessLookupError:
            pass  # already dead

    def start_monitor(self):
        """Start the background crash monitor task."""
        self._monitor_task = asyncio.create_task(self._monitor())

    async def _monitor(self):
        """Monitor the LND process and restart on unexpected exit.

        Uses exponential backoff between restart attempts, up to MAX_RESTARTS.
        """
        while self._should_run:
            if self.process is None:
                await asyncio.sleep(1)
                continue
            returncode = await self.process.wait()
            if not self._should_run:
                break  # intentional shutdown
            if self.restart_count >= self.MAX_RESTARTS:
                logger.critical(
                    f"LND crashed {self.restart_count} times, giving up. "
                    f"Last exit code: {returncode}"
                )
                break
            backoff = self.RESTART_BACKOFF_BASE * (2 ** self.restart_count)
            self.restart_count += 1
            logger.error(
                f"LND exited unexpectedly (code={returncode}), "
                f"restarting in {backoff}s (attempt {self.restart_count}/{self.MAX_RESTARTS})"
            )
            await asyncio.sleep(backoff)
            if self._should_run:
                await self.start()
