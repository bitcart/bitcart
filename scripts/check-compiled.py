#!/usr/bin/env python3

import argparse
import concurrent.futures
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

DETERMINISTIC_PATTERN = re.compile(r"^.*requirements/deterministic/.*txt$")


def get_root(script_path):
    folder = script_path.resolve().parent
    while not (folder / ".git").exists():
        folder = folder.parent
        if folder == folder.anchor:
            raise RuntimeError("git repo not found")
    return folder


def sha256sum(filename):
    h = hashlib.sha256()
    b = bytearray(128 * 1024)
    mv = memoryview(b)
    with open(filename, "rb", buffering=0) as f:
        while n := f.readinto(mv):
            h.update(mv[:n])
    return h.hexdigest()


def pip_compile(root, req, failed, cache_dir):  # returns (success, skip)
    script_name = root / "scripts" / "compile-requirement.sh"
    cache_dir = Path(cache_dir) / sha256sum(req)
    relative_name = str(req.relative_to(root)) if req.is_absolute() else req
    proc = subprocess.run([script_name, relative_name, "--cache-dir", cache_dir], capture_output=True, text=True)
    if proc.returncode:
        if "Please specify which python to use" in proc.stdout:
            return True, True
        if not failed:
            print()
        print(f"Error occured running pip-compile:\nStdout:\n{proc.stdout}Stderr:\n{proc.stderr}", end="", file=sys.stderr)
        return False, False
    return True, False


def main():
    parser = argparse.ArgumentParser(description="Check if requirements are up to date")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    if not args.verbose:
        sys.stdout = open(os.devnull, "w")
    print("Check compiled piptools requirements... ", end="", flush=True)
    root = get_root(Path(sys.argv[0]))
    requirements_dir = str(root / "requirements")
    failed = False
    with tempfile.TemporaryDirectory() as tmpdirname:
        futures = []
        max_workers = (os.cpu_count() or 1) + 4
        if os.getenv("CIRCLCI"):
            max_workers = 2
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            for req in args.files:
                req = Path(req).absolute()
                if not str(req).startswith(requirements_dir) or DETERMINISTIC_PATTERN.match(str(req)):
                    continue
                futures.append(executor.submit(pip_compile, root, req, failed, tmpdirname))
        for f in futures:
            try:
                success, skip = f.result()
                if skip:
                    print("Skipping due to missing python required for compilation")
                    return 0
                failed |= not success
            except Exception:
                if not failed:
                    print()
                print(traceback.format_exc(), end="")
                failed = True
    print("OK" if not failed else "Failed")
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
