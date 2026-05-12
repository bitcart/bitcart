"""Launcher for the Bitcart Admin panel. Used by PyCharm run configuration."""

import os
import subprocess
import sys

os.chdir("/home/user/LND/bitcart-admin")
os.environ["BITCART_ADMIN_API_URL"] = "http://127.0.0.1:8000"
os.environ["BITCART_STORE_HOST"] = "localhost:4001"

sys.exit(subprocess.call(["yarn", "start"]))
