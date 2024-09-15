import string

from bitcart import COINS as _COINS

VERSION = "0.8.0.0"  # Version, used for openapi schemas and update checks
WEBSITE = "https://bitcart.ai"  # Bitcart official site
GIT_REPO_URL = "https://github.com/bitcart/bitcart"  # Bitcart github repository
DOCKER_REPO_URL = "https://github.com/bitcart/bitcart-docker"  # Bitcart Docker Packaging repository
MAX_CONFIRMATION_WATCH = 6  # maximum number of confirmations to save
FEE_ETA_TARGETS = [25, 10, 5, 2, 1]  # supported target blocks confirmation ETA fee
EVENTS_CHANNEL = "events"  # default redis channel for event system (inter-process communication)
LOGSERVER_PORT = 9020  # port for logserver in the worker
SUPPORTED_CRYPTOS = {coin.lower(): obj.friendly_name for (coin, obj) in _COINS.items()}  # all cryptos supported by the SDK
HTTPS_REVERSE_PROXIES = [
    "nginx-https"
]  # reverse proxies supporting https; NOTE: maybe this could be used by accessing generator package?
ID_LENGTH = 26  # default length of IDs of all objects (ULID)
TOTP_LENGTH = 6  # for email verification and such
TOTP_ALPHABET = string.digits  # only numbers for ease of access
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
# due to many exchanges lacking more than 8 digits, we limit eth-based divisibility for invoices to 8
MAX_CONTRACT_DIVISIBILITY = 8
PLUGINS_SCHEMA_URL = "https://bitcart.ai/schemas/plugin/1.3.0/plugin.schema.json"
SHORT_EXPIRATION = 60 * 60  # used for temporary codes
TFA_RECOVERY_ALPHABET = "23456789BCDFGHJKMNPQRTVWXY".lower()  # avoid confusing chars
TFA_RECOVERY_LENGTH = 5  # each part has 5 chars
FIDO2_REGISTER_KEY = "fido2_register_cache"
FIDO2_LOGIN_KEY = "fido2_login_cache"
VERIFY_EMAIL_EXPIRATION = 60 * 60 * 24  # 1 day
DEFAULT_SENDMAIL_SUBJECT = "Thank you for your order"  # used in api/invoices.py
HTTPS_REVERSE_PROXIES = ["nginx-https"]
