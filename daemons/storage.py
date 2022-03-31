# Thanks to https://github.com/spesmilo/electrum storage implementation
import copy
import json
import os
import stat
import threading
from decimal import Decimal
from functools import singledispatch


class DBFileException(Exception):
    pass


def standardize_path(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(os.path.expanduser(path))))


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return decimal_to_string(obj)
        if hasattr(obj, "to_json") and callable(obj.to_json):
            return obj.to_json()
        return super().default(obj)


class Storage:
    def __init__(self, path):
        self.path = standardize_path(path)
        self._file_exists = bool(self.path and os.path.exists(self.path))
        if self.file_exists():
            with open(self.path, encoding="utf-8") as f:
                self.raw = f.read()
        else:
            self.raw = ""

    def read(self):
        return self.raw

    def write(self, data: str) -> None:
        # write in temporary first to not corrupt the main file
        s = data
        temp_path = f"{self.path}.tmp.{os.getpid()}"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(s)
            f.flush()
            os.fsync(f.fileno())
        try:
            mode = os.stat(self.path).st_mode
        except FileNotFoundError:
            mode = stat.S_IREAD | stat.S_IWRITE
        if not self.file_exists():
            assert not os.path.exists(self.path)
        os.replace(temp_path, self.path)
        os.chmod(self.path, mode)
        self._file_exists = True

    def file_exists(self) -> bool:
        return self._file_exists


def modifier(func):
    def wrapper(self, *args, **kwargs):
        with self.lock:
            self._modified = True
            return func(self, *args, **kwargs)

    return wrapper


def locked(func):
    def wrapper(self, *args, **kwargs):
        with self.lock:
            return func(self, *args, **kwargs)

    return wrapper


def decimal_to_string(d, precision=18):
    return f"{d:.{precision}f}"


def obj_to_string(obj):
    if isinstance(obj, Decimal):
        return decimal_to_string(obj)
    return str(obj)


@singledispatch
def string_keys(obj):
    return obj


@string_keys.register(dict)
def _(d):
    return {obj_to_string(k): string_keys(v) for k, v in d.items()}


@string_keys.register(list)
def _(lst):
    return [string_keys(v) for v in lst]


class JsonDB:
    def __init__(self, data):
        self.lock = threading.RLock()
        self.data = data
        self._modified = False

    def set_modified(self, b):
        with self.lock:
            self._modified = b

    def modified(self):
        return self._modified

    @locked
    def get(self, key, default=None):
        v = self.data.get(key)
        if v is None:
            v = default
        return v

    @modifier
    def put(self, key, value):
        try:
            json.dumps(key, cls=JSONEncoder)
            json.dumps(value, cls=JSONEncoder)
        except Exception:
            return False
        if value is not None:
            if self.data.get(key) != value:
                self.data[key] = copy.deepcopy(value)
                return True
        elif key in self.data:
            self.data.pop(key)
            return True
        return False

    @locked
    def dump(self) -> str:
        return json.dumps(string_keys(self.data), cls=JSONEncoder)

    def _should_convert_to_stored_dict(self, key) -> bool:
        return True


class StoredObject:

    db = None

    def __setattr__(self, key, value):
        if self.db:
            self.db.set_modified(True)
        super().__setattr__(key, value)

    def set_db(self, db):
        self.db = db

    def to_json(self):
        d = dict(vars(self))
        d.pop("db", None)
        d = {k: v for k, v in d.items() if not k.startswith("_")}
        return d


class StoredDBProperty:
    def __init__(self, name, default):
        self.name = name
        self.default = default

    def __set__(self, obj, value):
        obj.db.put(self.name, value)
        obj.db.set_modified(True)
        obj.save_db()

    def __get__(self, obj, objtype=None):
        if not hasattr(obj, "db"):
            return None
        return obj.db.get(self.name, self.default)


class StoredProperty:
    def __init__(self, name, default):
        self.name = name
        self.default = default

    def __set__(self, obj, value):
        obj.config.set_config(self.name, value)

    def __get__(self, obj, objtype=None):
        if not hasattr(obj, "config"):
            return None
        return obj.config.get(self.name, self.default)


_RaiseKeyError = object()


class StoredDict(dict):
    def __init__(self, data, db, path):
        self.db = db
        self.lock = self.db.lock if self.db else threading.RLock()
        self.path = path
        # recursively convert dicts to StoredDict
        for k, v in list(data.items()):
            self.__setitem__(k, v)

    @locked
    def __setitem__(self, key, v):
        is_new = key not in self
        # early return to prevent unnecessary disk writes
        if not is_new and self[key] == v:
            return
        # recursively set db and path
        if isinstance(v, StoredDict):
            v.db = self.db
            v.path = self.path + [key]
            for k, vv in v.items():
                v[k] = vv
        # recursively convert dict to StoredDict.
        # _convert_dict is called breadth-first
        elif isinstance(v, dict):
            if self.db:
                v = self.db._convert_dict(self.path, key, v)
            if not self.db or self.db._should_convert_to_stored_dict(key):
                v = StoredDict(v, self.db, self.path + [key])
        # set parent of StoredObject
        if isinstance(v, StoredObject):
            v.set_db(self.db)
        # set item
        super().__setitem__(key, v)
        if self.db:
            self.db.set_modified(True)

    @locked
    def __delitem__(self, key):
        super().__delitem__(key)
        if self.db:
            self.db.set_modified(True)

    @locked
    def pop(self, key, v=_RaiseKeyError):
        if v is _RaiseKeyError:
            r = super().pop(key)
        else:
            r = super().pop(key, v)
        if self.db:
            self.db.set_modified(True)
        return r

    @locked
    def clear(self):
        super().clear()
        if self.db:
            self.db.set_modified(True)


class WalletDB(JsonDB):
    STORAGE_VERSION: int
    NAME: str = "wallet"

    def __init__(self, raw):
        super().__init__({})
        self.upgraded = False
        if raw:
            self.load_data(raw)
        else:
            self.put("version", self.STORAGE_VERSION)
        self._after_upgrade_tasks()

    def load_data(self, s):
        try:
            self.data = json.loads(s)
        except Exception as e:
            raise DBFileException(f"Cannot read {self.NAME} file. (parsing failed)") from e
        if not isinstance(self.data, dict):
            raise DBFileException(f"Malformed {self.NAME} file (not dict)")
        if self.requires_upgrade():
            self.upgrade()

    def requires_upgrade(self):
        return self.get_version() < self.STORAGE_VERSION

    def upgrade(self):
        # future upgrade code here
        self.put("version", self.STORAGE_VERSION)
        self._after_upgrade_tasks()

    def _after_upgrade_tasks(self):
        self.upgraded = True
        self.data = StoredDict(self.data, self, [])

    def _is_upgrade_method_needed(self, min_version, max_version):
        assert min_version <= max_version
        cur_version = self.get_version()
        if cur_version > max_version:
            return False
        elif cur_version < min_version:
            raise DBFileException(f"storage upgrade: unexpected version {cur_version} (should be {min_version}-{max_version})")
        else:
            return True

    @locked
    def get_version(self):
        version = self.get("version")
        if not version:
            version = self.STORAGE_VERSION
        if version > self.STORAGE_VERSION:
            raise DBFileException(
                f"This version of BitcartCC ETH daemon is too old to open this {self.NAME}.\n"
                f"(highest supported storage version: {self.STORAGE_VERSION}, version of this file: {version})"
            )
        return version

    @locked
    def get_dict(self, name) -> dict:
        # Warning: interacts un-intuitively with 'put': certain parts
        # of 'data' will have pointers saved as separate variables.
        if name not in self.data:
            self.data[name] = {}
        return self.data[name]

    def _convert_dict(self, path, key, v):
        return v

    def _should_convert_to_stored_dict(self, key) -> bool:
        return True

    def write(self, storage):
        with self.lock:
            self._write(storage)

    def _write(self, storage):
        if not self.modified():
            return
        storage.write(self.dump())
        self.set_modified(False)

    def is_ready_to_be_used(self):
        return not self.requires_upgrade() and self.upgraded


class ConfigDB(WalletDB):
    NAME = "config"

    def __init__(self, path):
        self.storage = Storage(path)
        super().__init__(self.storage.read())
        self.data = StoredDict(self.data, self, [])

    def set_config(self, key, value):
        super().put(key, value)
        self.set_modified(True)
        self.write(self.storage)
