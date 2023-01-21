import os


def safe_remove(filename):
    try:
        os.remove(filename)
    except (TypeError, OSError):
        pass


def ensure_exists(path):
    os.makedirs(path, exist_ok=True)
