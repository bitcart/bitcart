import fnmatch
import os
import re
from enum import StrEnum
from typing import Annotated

from pydantic import Field, PostgresDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from starlette.config import Config
from starlette.datastructures import CommaSeparatedStrings

from api.constants import HTTPS_REVERSE_PROXIES
from api.ext.ssh import load_ssh_settings
from api.schemas.misc import SSHSettings


class Environment(StrEnum):
    development = "development"
    testing = "testing"
    sandbox = "sandbox"
    production = "production"


class Settings(BaseSettings):
    ENV: Environment = Field(Environment.development, validation_alias="BITCART_ENV")
    DEBUG: bool = False
    LOG_LEVEL: str = "DEBUG"

    DOCKER_ENV: bool = Field(False, validation_alias="IN_DOCKER")

    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 5432
    DB_DATABASE: str = Field(default="bitcart", validation_alias="DB_DATABASE")
    DB_POOL_SIZE: int = 5
    DB_POOL_RECYCLE_SECONDS: int = 600

    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    SENTRY_DSN: str | None = None

    ENABLED_CRYPTOS: Annotated[CommaSeparatedStrings, NoDecode] = Field(
        CommaSeparatedStrings("btc"), validation_alias="BITCART_CRYPTOS"
    )

    COINGECKO_API_KEY: str | None = Field(None, validation_alias="COINGECKO_API_KEY")

    IS_WORKER: bool = False

    OPENAPI_PATH: str | None = Field(None, validation_alias="OPENAPI_PATH")
    API_TITLE: str = Field("Bitcart", validation_alias="API_TITLE")

    DATADIR: str = Field("data", validation_alias="BITCART_DATADIR")
    BACKUPS_DIR: str = Field("data/backups", validation_alias="BITCART_BACKUPS_DIR")
    BACKEND_PLUGINS_DIR: str = Field("modules", validation_alias="BITCART_BACKEND_PLUGINS_DIR")
    ADMIN_PLUGINS_DIR: str = Field("data/admin_plugins", validation_alias="BITCART_ADMIN_PLUGINS_DIR")
    STORE_PLUGINS_DIR: str = Field("data/store_plugins", validation_alias="BITCART_STORE_PLUGINS_DIR")
    DAEMON_PLUGINS_DIR: str = Field("data/daemon_plugins", validation_alias="BITCART_DAEMON_PLUGINS_DIR")
    DOCKER_PLUGINS_DIR: str = Field("data/docker_plugins", validation_alias="BITCART_DOCKER_PLUGINS_DIR")
    STATIC_DIR: str = Field("static", validation_alias="BITCART_STATIC_DIR")

    ROOT_PATH: str = Field("", validation_alias="BITCART_BACKEND_ROOTPATH")
    API_HOST: str = Field("localhost:8000", validation_alias="BITCART_HOST")
    ADMIN_HOST: str = Field("localhost:3000", validation_alias="BITCART_ADMIN_HOST")
    ADMIN_ROOTPATH: str = Field("/", validation_alias="BITCART_ADMIN_ROOTPATH")
    REVERSE_PROXY: str = Field("nginx-https", validation_alias="BITCART_REVERSEPROXY")
    HTTPS_ENABLED: bool = Field(False, validation_alias="BITCART_HTTPS_ENABLED")

    TORRC_FILE: str | None = Field(None, validation_alias="TORRC_FILE")
    UPDATE_URL: str | None = Field(None, validation_alias="UPDATE_URL")

    LOG_FILE_NAME: str | None = Field(None, validation_alias="LOG_FILE")

    LICENSE_SERVER_URL: str = Field("https://licensing.bitcart.ai", validation_alias="LICENSE_SERVER_URL")

    PROMETHEUS_METRICS_ENABLED: bool = Field(False, validation_alias="BITCART_PROMETHEUS_METRICS_ENABLED")

    ssh_settings: SSHSettings = Field(
        default_factory=lambda: load_ssh_settings(Config("conf/.env" if os.path.exists("conf/.env") else None))
    )

    model_config = SettingsConfigDict(
        env_file="conf/.env",
        extra="ignore",
    )

    config: Config = Field(default_factory=lambda: Config("conf/.env" if os.path.exists("conf/.env") else None))

    @property
    def log_file(self) -> str | None:
        if not self.LOG_FILE_NAME:
            return None
        return os.path.join(self.log_dir, self.LOG_FILE_NAME)

    @property
    def log_file_regex(self) -> re.Pattern[str] | None:
        if not self.LOG_FILE_NAME:
            return None
        filename_no_ext, _, file_extension = self.LOG_FILE_NAME.partition(".")
        return re.compile(fnmatch.translate(f"{filename_no_ext}*{file_extension}"))

    @property
    def logserver_client_host(self) -> str:
        return "worker" if self.DOCKER_ENV else "localhost"

    @property
    def logserver_host(self) -> str:
        return "0.0.0.0" if self.DOCKER_ENV else "localhost"

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @field_validator("DB_DATABASE")
    @classmethod
    def validate_db_database(cls, v: str, info: ValidationInfo) -> str:
        if info.data["ENV"] == Environment.testing:
            return f"{v}_test"
        return v

    @field_validator("ENABLED_CRYPTOS", mode="before")
    @classmethod
    def validate_enabled_cryptos(cls, v: str) -> CommaSeparatedStrings:
        return CommaSeparatedStrings(v)

    @field_validator("DATADIR", mode="before")
    @classmethod
    def set_datadir(cls, path: str) -> str:
        from api.utils.files import ensure_exists

        path = os.path.abspath(path)
        ensure_exists(path)
        return path

    @field_validator("BACKUPS_DIR", mode="before")
    @classmethod
    def set_backups_dir(cls, path: str) -> str:
        from api.utils.files import ensure_exists

        path = os.path.abspath(path)
        ensure_exists(path)
        return path

    @field_validator("BACKEND_PLUGINS_DIR", mode="before")
    @classmethod
    def set_backend_plugins_dir(cls, path: str) -> str:
        from api.utils.files import ensure_exists

        path = os.path.abspath(path)
        ensure_exists(path)
        return path

    @field_validator("ADMIN_PLUGINS_DIR", mode="before")
    @classmethod
    def set_admin_plugins_dir(cls, path: str) -> str:
        from api.utils.files import ensure_exists

        path = os.path.abspath(path)
        ensure_exists(path)
        return path

    @field_validator("STORE_PLUGINS_DIR", mode="before")
    @classmethod
    def set_store_plugins_dir(cls, path: str) -> str:
        from api.utils.files import ensure_exists

        path = os.path.abspath(path)
        ensure_exists(path)
        return path

    @field_validator("DAEMON_PLUGINS_DIR", mode="before")
    @classmethod
    def set_daemon_plugins_dir(cls, path: str) -> str:
        from api.utils.files import ensure_exists

        path = os.path.abspath(path)
        ensure_exists(path)
        return path

    @field_validator("DOCKER_PLUGINS_DIR", mode="before")
    @classmethod
    def set_docker_plugins_dir(cls, path: str) -> str:
        from api.utils.files import ensure_exists

        path = os.path.abspath(path)
        ensure_exists(path)
        return path

    @property
    def images_dir(self) -> str:
        from api.utils.files import ensure_exists

        path = os.path.join(self.DATADIR, "images")
        ensure_exists(path)
        return path

    @property
    def products_image_dir(self) -> str:
        from api.utils.files import ensure_exists

        path = os.path.join(self.images_dir, "products")
        ensure_exists(path)
        return path

    @property
    def files_dir(self) -> str:
        from api.utils.files import ensure_exists

        path = os.path.join(self.DATADIR, "files")
        ensure_exists(path)
        return path

    @property
    def log_dir(self) -> str:
        from api.utils.files import ensure_exists

        path = os.path.join(self.DATADIR, "logs")
        ensure_exists(path)
        return path

    @property
    def plugins_dir(self) -> str:
        from api.utils.files import ensure_exists

        path = os.path.join(self.DATADIR, "plugins")
        ensure_exists(path)
        return path

    def get_plugin_data_dir(self, plugin_name: str) -> str:
        from api.utils.files import ensure_exists

        path = os.path.join(self.DATADIR, "plugin_data", plugin_name)
        ensure_exists(path)
        return path

    def build_postgres_dsn(self, db_name: str | None = None, driver: str = "asyncpg") -> str:
        return str(
            PostgresDsn.build(
                scheme=f"postgresql+{driver}",
                username=self.DB_USER,
                password=self.DB_PASSWORD,
                host=self.DB_HOST,
                port=self.DB_PORT,
                path=self.DB_DATABASE if db_name is None else db_name,
            )
        )

    @property
    def postgres_dsn(self) -> str:
        return self.build_postgres_dsn()

    @property
    def protocol(self) -> str:
        if self.ADMIN_HOST.startswith("localhost"):
            return "http"
        return "https" if self.HTTPS_ENABLED or self.REVERSE_PROXY in HTTPS_REVERSE_PROXIES else "http"

    @property
    def admin_url(self) -> str:
        rootpath = "" if self.ADMIN_ROOTPATH == "/" else self.ADMIN_ROOTPATH
        return f"{self.protocol}://{self.ADMIN_HOST}{rootpath}"

    @property
    def api_url(self) -> str:
        rootpath = "" if self.ROOT_PATH == "/" else self.ROOT_PATH
        return f"{self.protocol}://{self.API_HOST}{rootpath}"

    @property
    def coingecko_api_url(self) -> str:
        if self.COINGECKO_API_KEY:
            return "https://pro-api.coingecko.com/api/v3"
        return "https://api.coingecko.com/api/v3"

    @property
    def coingecko_headers(self) -> dict[str, str]:
        if self.COINGECKO_API_KEY:
            return {"x-cg-pro-api-key": self.COINGECKO_API_KEY}
        return {}

    def is_environment(self, environments: set[Environment]) -> bool:
        return self.ENV in environments

    def is_development(self) -> bool:
        return self.is_environment({Environment.development})

    def is_testing(self) -> bool:
        return self.is_environment({Environment.testing})

    def is_sandbox(self) -> bool:
        return self.is_environment({Environment.sandbox})

    def is_production(self) -> bool:
        return self.is_environment({Environment.production})
