from api.constants import DOCKER_REPO_URL


def install_package(package):
    return f"apt-get update && apt-get install -y {package}"


def create_bash_script(settings):
    git_repo = settings.advanced_settings.bitcart_docker_repository or DOCKER_REPO_URL
    reverseproxy = "nginx-https" if settings.domain_settings.https else "nginx"
    cryptos_str = ",".join(settings.coins.keys())
    installation_pack = settings.advanced_settings.installation_pack
    additional_components = list(set(settings.additional_services + settings.advanced_settings.additional_components))
    domain = settings.domain_settings.domain or "bitcart.local"
    script = ""
    script += "sudo su -\n"
    script += f"{install_package('git')}\n"
    script += 'if [ -d "bitcart-docker" ]; then echo "existing bitcart-docker folder found, pulling instead of cloning."; git pull; fi\n'
    if git_repo != DOCKER_REPO_URL:
        script += 'export BITCARTGEN_DOCKER_IMAGE="bitcartcc/docker-compose-generator:local"\n'
    script += f"export BITCART_HOST={domain}\n"
    if reverseproxy != "nginx-https":
        script += f"export BITCART_REVERSEPROXY={reverseproxy}\n"
    script += f"export BITCART_CRYPTOS={cryptos_str}\n"
    for symbol, coin in settings.coins.items():
        if coin.network != "mainnet":
            script += f"export {symbol.upper()}_NETWORK={coin.network}\n"
        if coin.lightning:
            script += f"export {symbol.upper()}_LIGHTNING={coin.lightning}\n"
    if installation_pack != "all":
        script += f"export BITCART_INSTALL={installation_pack}\n"
    if additional_components:
        script += f"export BITCART_ADDITIONAL_COMPONENTS={','.join(additional_components)}\n"
    script += "cd bitcart-docker\n"
    script += "./setup.sh\n"
    return script
