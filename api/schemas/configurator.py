from api.schemas.base import Schema


class ConfiguratorDomainSettings(Schema):
    domain: str | None = ""
    https: bool | None = True


class ConfiguratorCoinDescription(Schema):
    enabled: bool | None = True
    network: str | None = "mainnet"
    lightning: bool | None = False


class ConfiguratorAdvancedSettings(Schema):
    installation_pack: str | None = "all"
    bitcart_docker_repository: str | None = ""
    additional_components: list[str] = []


class ConfiguratorSSHSettings(Schema):
    host: str = ""
    username: str = ""
    password: str = ""
    root_password: str = ""


class ConfiguratorServerSettings(Schema):
    domain_settings: ConfiguratorDomainSettings = ConfiguratorDomainSettings()
    coins: dict[str, ConfiguratorCoinDescription] = {}
    additional_services: list[str] = []
    advanced_settings: ConfiguratorAdvancedSettings = ConfiguratorAdvancedSettings()


class ConfiguratorDeploySettings(ConfiguratorServerSettings):
    mode: str
    ssh_settings: ConfiguratorSSHSettings = ConfiguratorSSHSettings()
