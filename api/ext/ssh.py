import paramiko
from paramiko.channel import ChannelFile, ChannelStderrFile, ChannelStdinFile

from api.schemas.configurator import ConfiguratorSSHSettings


def create_ssh_client(settings: ConfiguratorSSHSettings) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=settings.host,
        username=settings.username,
        password=settings.password,
        allow_agent=False,
        look_for_keys=False,
        timeout=10,
    )
    return client


def prepare_shell_command(command: str) -> str:
    escaped_command = command.replace("'", "'\"'\"'")
    return f"bash -c '{escaped_command}'"


def execute_ssh_command(client: paramiko.SSHClient, command: str) -> tuple[ChannelStdinFile, ChannelFile, ChannelStderrFile]:
    return client.exec_command(prepare_shell_command(command))


class ServerEnv:  # pragma: no cover: no valid SSH configuration in CI environment
    def __init__(self, client: paramiko.SSHClient) -> None:
        self.client = client
        self.env: dict[str, str] = {}
        self.preload_env()

    def _read_remote_file(self, file: str, require_export: bool = True) -> dict[str, str]:
        _, stdout, _ = execute_ssh_command(self.client, f"cat {file}")
        output = stdout.read()
        result = {}
        if stdout.channel.recv_exit_status() == 0:
            valid_lines = output.decode().split("\n")
            valid_lines = list(
                filter(lambda s: "=" in s and "==" not in s and (not require_export or "export" in s), valid_lines)
            )
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

    def preload_env(self) -> None:
        self.env = self._read_remote_file("/etc/profile.d/bitcart-env.sh")
        env_file = self.get("BITCART_ENV_FILE", "")
        if env_file:
            self.env.update(self._read_remote_file(env_file, require_export=False))

    def get(self, key: str, default: str = "") -> str:
        value = self.env.get(key, default)
        if not value:
            value = default
        return value
