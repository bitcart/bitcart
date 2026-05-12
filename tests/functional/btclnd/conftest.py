"""Shared fixtures for BTCLND functional tests (API and browser).

Automatically starts the full regtest environment:
- bitcoind (regtest)
- merchant LND, customer LND, receiver LND
- BTCLND daemon
- Bitcart API
- Bitcart Worker
- Bitcart Admin panel (for browser tests)

All services are started once per pytest session and torn down at exit.
Uses a separate test database to avoid touching production data.
"""

import asyncio
import hashlib
import json
import os
import signal
import subprocess
import sys
import time

import pytest

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
REGTEST_DIR = os.path.join(PROJECT_DIR, ".regtest")
BOOTSTRAP_SCRIPT = os.path.join(PROJECT_DIR, "tests", "functional", "btclnd", "bootstrap.sh")
TEST_DB_NAME = "bitcart_btclnd_test"

# Track spawned processes for cleanup
_spawned_procs = []


def _wait_for_port(port, timeout=30):
    """Wait for a port to become available."""
    import socket
    for _ in range(timeout * 2):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(("127.0.0.1", port))
                return True
        except ConnectionRefusedError:
            time.sleep(0.5)
    return False


def _kill_procs():
    """Kill all spawned subprocesses."""
    for proc in _spawned_procs:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass
    time.sleep(2)
    for proc in _spawned_procs:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
    _spawned_procs.clear()


def _spawn(cmd, env=None, log_file=None):
    """Spawn a background process in a new process group."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    stdout = open(log_file, "w") if log_file else subprocess.DEVNULL
    stderr = subprocess.STDOUT if log_file else subprocess.DEVNULL
    proc = subprocess.Popen(
        cmd, env=merged_env, stdout=stdout, stderr=stderr,
        preexec_fn=os.setsid,
    )
    _spawned_procs.append(proc)
    return proc


@pytest.fixture(scope="session", autouse=True)
def regtest_environment():
    """Start the full regtest environment for the test session.

    This fixture is autouse — it runs automatically for all tests in this directory.
    """
    os.chdir(PROJECT_DIR)

    common_env = {
        "BITCART_CRYPTOS": "btc,btclnd",
        "BTCLND_NETWORK": "regtest",
        "BTC_NETWORK": "regtest",
        "BTC_LIGHTNING": "true",
        "BTCLND_TOR": "false",
        "PYTHONPATH": os.path.join(PROJECT_DIR, "daemons"),
        "DB_DATABASE": TEST_DB_NAME,
        "DB_PASSWORD": os.environ.get("DB_PASSWORD", "123456"),
    }

    try:
        # --- 1. Start regtest bitcoind + LND nodes ---
        print("\n>>> Starting regtest environment...")
        subprocess.run(["bash", BOOTSTRAP_SCRIPT, "start"], check=True, timeout=120)
        assert os.path.exists(os.path.join(REGTEST_DIR, "ports.env")), "Bootstrap failed"

        # --- 2. Reset test database ---
        print(">>> Resetting test database...")
        db_password = common_env["DB_PASSWORD"]
        for sql in [
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{TEST_DB_NAME}' AND pid != pg_backend_pid();",
            f"DROP DATABASE IF EXISTS {TEST_DB_NAME};",
            f"CREATE DATABASE {TEST_DB_NAME};",
        ]:
            subprocess.run(
                ["psql", "-U", "postgres", "-h", "localhost", "-c", sql],
                env={**os.environ, "PGPASSWORD": db_password},
                capture_output=True, timeout=10,
            )

        # Run migrations
        subprocess.run(
            [os.path.join(PROJECT_DIR, ".venv", "bin", "alembic"), "upgrade", "head"],
            env={**os.environ, **common_env},
            cwd=PROJECT_DIR, capture_output=True, timeout=60,
        )

        # --- 3. Start BTCLND daemon ---
        print(">>> Starting BTCLND daemon...")
        daemon_env = {
            **common_env,
            "BTCLND_DATA_PATH": os.path.join(REGTEST_DIR, "daemon"),
            "BTCLND_NEUTRINO_PEERS": "127.0.0.1:18444",
            "BTCLND_DEBUG": "true",
        }
        _spawn(
            [os.path.join(PROJECT_DIR, ".venv", "bin", "python"), "daemons/btclnd.py"],
            env=daemon_env,
            log_file=os.path.join(REGTEST_DIR, "daemon.log"),
        )
        assert _wait_for_port(5012, timeout=30), "BTCLND daemon failed to start"

        # --- 4. Start BTC/Electrum daemon ---
        print(">>> Starting BTC Electrum daemon...")
        btc_env = {
            **common_env,
            "BTC_DEBUG": "true",
        }
        _spawn(
            [os.path.join(PROJECT_DIR, ".venv", "bin", "python"), "daemons/btc.py"],
            env=btc_env,
            log_file=os.path.join(REGTEST_DIR, "btc_daemon.log"),
        )
        # Electrum daemon may take a moment; don't hard-fail if port 5000 is slow
        _wait_for_port(5000, timeout=15)

        # --- 5. Generate seed and set env ---
        print(">>> Generating wallet seed...")
        import requests
        for _ in range(30):
            try:
                r = requests.post("http://localhost:5012",
                    auth=("electrum", "electrumz"),
                    json={"method": "make_seed", "id": 1}, timeout=10)
                seed = r.json().get("result")
                if seed:
                    break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError("Failed to generate seed")

        os.environ["BTCLND_TEST_SEED"] = seed
        with open(os.path.join(REGTEST_DIR, "test_seed.txt"), "w") as f:
            f.write(seed)

        # --- 6. Start API ---
        print(">>> Starting API...")
        _spawn(
            [os.path.join(PROJECT_DIR, ".venv", "bin", "uvicorn"),
             "main:app", "--port", "8000"],
            env=common_env,
            log_file=os.path.join(REGTEST_DIR, "api.log"),
        )
        assert _wait_for_port(8000, timeout=15), "API failed to start"

        # --- 7. Start Worker ---
        print(">>> Starting Worker...")
        _spawn(
            [os.path.join(PROJECT_DIR, ".venv", "bin", "python"), "worker.py"],
            env=common_env,
            log_file=os.path.join(REGTEST_DIR, "worker.log"),
        )
        time.sleep(3)

        # --- 8. Start Admin panel ---
        print(">>> Starting Admin panel...")
        _spawn(
            ["yarn", "start"],
            env={**os.environ, "PORT": "3000"},
            log_file=os.path.join(REGTEST_DIR, "admin.log"),
        )
        _wait_for_port(3000, timeout=15)

        # --- 9. Create test user ---
        print(">>> Creating test user...")
        for _ in range(10):
            try:
                r = requests.post("http://localhost:8000/users",
                    json={"email": "test@test.com", "password": "password"}, timeout=5)
                if r.status_code in (200, 201, 422):  # 422 = already exists
                    break
            except Exception:
                time.sleep(1)

        # --- 10. Create wallets and stores ---
        print(">>> Creating wallets and stores...")
        token_resp = requests.post("http://localhost:8000/token",
            json={"email": "test@test.com", "password": "password", "permissions": ["full_control"]})
        headers = {"Authorization": f"Bearer {token_resp.json()['access_token']}"}

        # Create BTCLND wallet
        lnd_wallet = requests.post("http://localhost:8000/wallets", headers=headers,
            json={"name": "LND Test Wallet", "xpub": seed, "currency": "btclnd",
                  "lightning_enabled": True,
                  "additional_xpub_data": {"zero_conf_monitoring": True}},
            timeout=120).json()
        print(f"  LND wallet: {lnd_wallet.get('id', 'FAILED')}")

        # Create Electrum wallet (hot wallet via make_seed on the BTC daemon)
        btc_seed = None
        try:
            r = requests.post("http://localhost:5000",
                auth=("electrum", "electrumz"),
                json={"method": "make_seed", "id": 1}, timeout=30)
            btc_seed = r.json().get("result")
        except Exception:
            print("  WARNING: Could not generate Electrum seed (BTC daemon may not be ready)")

        if btc_seed:
            btc_wallet = requests.post("http://localhost:8000/wallets", headers=headers,
                json={"name": "Electrum Test Wallet", "xpub": btc_seed, "currency": "btc",
                      "lightning_enabled": True},
                timeout=120).json()
            print(f"  Electrum wallet: {btc_wallet.get('id', 'FAILED')}")

            # Create store with Electrum wallet
            btc_store = requests.post("http://localhost:8000/stores", headers=headers,
                json={"name": "Electrum Test Store", "wallets": [btc_wallet["id"]]},
                timeout=30).json()
            print(f"  Electrum store: {btc_store.get('id', 'FAILED')}")

        # Create store with LND wallet
        lnd_store = requests.post("http://localhost:8000/stores", headers=headers,
            json={"name": "LND Test Store", "wallets": [lnd_wallet["id"]]},
            timeout=30).json()
        print(f"  LND store: {lnd_store.get('id', 'FAILED')}")

        print(">>> Regtest environment ready!\n")
        yield

    finally:
        print("\n>>> Tearing down regtest environment...")
        _kill_procs()
        subprocess.run(["bash", BOOTSTRAP_SCRIPT, "stop"], capture_output=True, timeout=30)
        # Clean test database
        db_password = common_env.get("DB_PASSWORD", "123456")
        subprocess.run(
            ["psql", "-U", "postgres", "-h", "localhost", "-c",
             f"DROP DATABASE IF EXISTS {TEST_DB_NAME};"],
            env={**os.environ, "PGPASSWORD": db_password},
            capture_output=True, timeout=10,
        )


@pytest.fixture(scope="session")
def anyio_backend():
    return ("asyncio", {"use_uvloop": True})


@pytest.fixture(scope="session")
def ports():
    """Load regtest port configuration."""
    from tests.functional.btclnd.utils import load_ports
    p = load_ports()
    if not p:
        pytest.skip("Regtest environment not running")
    return p


@pytest.fixture(scope="session")
def seed():
    """Get the test wallet seed."""
    s = os.environ.get("BTCLND_TEST_SEED")
    if not s:
        pytest.skip("BTCLND_TEST_SEED not set")
    return s
