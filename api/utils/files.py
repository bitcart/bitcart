import contextlib
import os
import shutil


def safe_remove(filename):
    with contextlib.suppress(TypeError, OSError):
        os.remove(filename)


def ensure_exists(path):
    os.makedirs(path, exist_ok=True)


def remove_tree(path):  # pragma: no cover
    if os.path.islink(path):
        os.unlink(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)
