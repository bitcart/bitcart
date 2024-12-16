import os
import subprocess


def run_shell(args=None, timeout=30):
    if args is None:
        args = []
    process = subprocess.Popen(["tests/functional/regtest.sh"] + args, stdout=subprocess.PIPE, universal_newlines=True)
    process.wait(timeout=timeout)
    assert process.returncode == 0
    return process.stdout.read().strip()


def start_worker():
    env = os.environ.copy()
    env["TEST"] = "true"
    return subprocess.Popen(["python3", "worker.py"], env=env)
