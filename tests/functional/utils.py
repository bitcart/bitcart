import os
import subprocess


def run_shell(args=[], timeout=30):
    process = subprocess.Popen(["tests/functional/regtest.sh"] + args, stdout=subprocess.PIPE, universal_newlines=True)
    process.wait(timeout=timeout)
    assert process.returncode == 0
    return process.stdout.read().strip()


def start_worker():
    env = os.environ.copy()
    env["TEST"] = "true"
    env["BITCART_CRYPTOS"] = "bch"
    return subprocess.Popen(["python3", "worker.py"], env=env)
