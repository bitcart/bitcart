"""Launcher for the Bitcart Store. Used by PyCharm run configuration."""

import os
import subprocess
import sys

os.chdir("/home/user/LND/bitcart-store")
os.environ["NUXT_PORT"] = "4001"
os.environ["BITCART_STORE_API_URL"] = "http://127.0.0.1:8000"

sys.exit(subprocess.call(["yarn", "start"]))
