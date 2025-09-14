import contextlib
import json
import os
import shutil
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError

from api.schemas.base import Schema


def safe_remove(filename: str) -> None:
    with contextlib.suppress(TypeError, OSError):
        os.remove(filename)


def ensure_exists(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def remove_tree(path: str) -> None:  # pragma: no cover
    if os.path.islink(path):
        os.unlink(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def parse_data[T: Schema](data: str, scheme: type[T]) -> T:
    try:
        parsed_data: dict[str, Any] = json.loads(data)
    except json.JSONDecodeError:
        raise HTTPException(422, "Invalid JSON") from None
    try:
        result = scheme(**parsed_data)
    except ValidationError as e:
        raise HTTPException(422, e.errors()) from None
    return result
