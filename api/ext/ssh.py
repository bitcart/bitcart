import contextlib

from starlette.datastructures import CommaSeparatedStrings

from api import constants


def load_ssh_settings(config):
    from api.schemes import SSHSettings

    settings = SSHSettings()
    connection_string = config("SSH_CONNECTION", default="")
    settings.host, settings.port, settings.username = parse_connection_string(connection_string)
    settings.password = config("SSH_PASSWORD", default="")
    settings.key_file = config("SSH_KEY_FILE", default="")
    settings.key_file_password = config("SSH_KEY_FILE_PASSWORD", default="")
    settings.authorized_keys_file = config("SSH_AUTHORIZED_KEYS", default="")
    settings.bash_profile_script = config("BASH_PROFILE_SCRIPT", default="/etc/profile.d/bitcart-env.sh")
    return settings


def parse_connection_string(connection_string):
    username = ""
    port = 22
    host = connection_string
    if host:
        parts = host.split(":")
        host = parts[0]
        port = 22
        if len(parts) == 2:
            with contextlib.suppress(ValueError):
                port = int(parts[1])
        parts = host.split("@")
        if len(parts) == 2:
            username = parts[0]
            host = parts[1]
        else:
            username = "root"
    return host, port, username


def prepare_shell_command(command):
    escaped_command = command.replace("'", "'\"'\"'")
    return f"bash -c '{escaped_command}'"


def execute_ssh_command(client, command):
    return client.exec_command(prepare_shell_command(command))


class ServerEnv:  # pragma: no cover: no valid SSH configuration in CI environment
    def __init__(self, client):
        self.client = client
        self.env = {}
        self.preload_env()

    def _read_remote_file(self, file, require_export=True):
        _, stdout, _ = execute_ssh_command(self.client, f"cat {file}")
        output = stdout.read()
        result = {}
        if stdout.channel.recv_exit_status() == 0:
            valid_lines = output.decode().split("\n")
            valid_lines = filter(lambda s: "=" in s and "==" not in s and (not require_export or "export" in s), valid_lines)
            env = {}
            for line in valid_lines:
                parts = line.split("=")
                key = parts[0].replace("export ", "")
                value = ""
                if len(parts) > 1:
                    value = parts[1].strip('"')
                env[key] = value
            result = env
        return result

    def preload_env(self):
        self.env = self._read_remote_file("/etc/profile.d/bitcart-env.sh")
        env_file = self.get("BITCART_ENV_FILE", "")
        if env_file:
            self.env.update(self._read_remote_file(env_file, require_export=False))

    def get(self, key, default=None):
        value = self.env.get(key, default)
        if not value:
            value = default
        return value


def collect_server_settings(ssh_settings):  # pragma: no cover
    from api.schemes import (
        ConfiguratorAdvancedSettings,
        ConfiguratorCoinDescription,
        ConfiguratorDomainSettings,
        ConfiguratorServerSettings,
    )
    from api.utils.common import str_to_bool

    settings = ConfiguratorServerSettings()
    with contextlib.suppress(Exception):
        client = ssh_settings.create_ssh_client()
        env = ServerEnv(client)
        cryptos = CommaSeparatedStrings(env.get("BITCART_CRYPTOS", "btc"))
        for crypto in cryptos:
            symbol = crypto.upper()
            network = env.get(f"{symbol}_NETWORK", "mainnet")
            lightning = str_to_bool(env.get(f"{symbol}_LIGHTNING", "false"))
            settings.coins[crypto] = ConfiguratorCoinDescription(network=network, lightning=lightning)
        domain = env.get("BITCART_HOST", "")
        reverse_proxy = env.get("BITCART_REVERSEPROXY", "nginx-https")
        is_https = reverse_proxy in constants.HTTPS_REVERSE_PROXIES
        settings.domain_settings = ConfiguratorDomainSettings(domain=domain, https=is_https)
        installation_pack = env.get("BITCART_INSTALL", "all")
        additional_components = list(CommaSeparatedStrings(env.get("BITCART_ADDITIONAL_COMPONENTS", "")))
        settings.advanced_settings = ConfiguratorAdvancedSettings(
            installation_pack=installation_pack, additional_components=additional_components
        )
        client.close()
    return settings
