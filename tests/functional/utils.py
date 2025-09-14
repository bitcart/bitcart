import os
import subprocess
from typing import IO, cast


def run_shell(args: list[str] | None = None, timeout: int = 30) -> str:
    if args is None:
        args = []
    process = subprocess.Popen(["tests/functional/regtest.sh"] + args, stdout=subprocess.PIPE, universal_newlines=True)
    process.wait(timeout=timeout)
    assert process.returncode == 0
    return cast(IO[str], process.stdout).read().strip()


def start_worker() -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    os.environ["BITCART_ENV"] = "testing"
    return subprocess.Popen(["python3", "worker.py"], env=env)
