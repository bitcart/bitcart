import string

from bitcart import COINS as _COINS

VERSION = "0.6.6.0"  # Version, used for openapi schemas and update checks
WEBSITE = "https://bitcartcc.com"  # BitcartCC official site
GIT_REPO_URL = "https://github.com/bitcartcc/bitcart"  # BitcartCC github repository
DOCKER_REPO_URL = "https://github.com/bitcartcc/bitcart-docker"  # BitcartCC Docker Packaging repository
MAX_CONFIRMATION_WATCH = 6  # maximum number of confirmations to save
FEE_ETA_TARGETS = [25, 10, 5, 2, 1]  # supported target blocks confirmation ETA fee
EVENTS_CHANNEL = "events"  # default redis channel for event system (inter-process communication)
LOGSERVER_PORT = 9020  # port for logserver in the worker
ALPHABET = string.ascii_letters  # used by ID generator
SUPPORTED_CRYPTOS = {coin.lower(): obj.friendly_name for (coin, obj) in _COINS.items()}  # all cryptos supported by the SDK
HTTPS_REVERSE_PROXIES = [
    "nginx-https"
]  # reverse proxies supporting https; NOTE: maybe this could be used by accessing generator package?
ID_LENGTH = 32  # default length of IDs of all objects except for invoice
PUBLIC_ID_LENGTH = 22  # The length of invoice and products ids; should be shorter than usual for better UX
# as supported by backup.sh
BACKUP_PROVIDERS = ["local", "scp", "s3"]
BACKUP_FREQUENCIES = ["daily", "weekly", "monthly"]
STR_TO_BOOL_MAPPING = {
    "true": True,
    "yes": True,
    "1": True,
    "false": False,
    "no": False,
    "0": False,
}  # common str -> bool conversions
