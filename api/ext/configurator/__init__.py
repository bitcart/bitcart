import re
import time

import paramiko

from api.constants import DOCKER_REPO_URL

COLOR_PATTERN = re.compile(r"\x1b[^m]*m")
BASH_INTERMEDIATE_COMMAND = 'echo "end-of-command $(expr 1 + 1)"'
INTERMEDIATE_OUTPUT = "end-of-command 2"
MAX_OUTPUT_WAIT = 10
OUTPUT_INTERVAL = 0.5
BUFFER_SIZE = 17640


def install_package(package):
    return f"apt-get update && apt-get install -y {package}"


def create_bash_script(settings):
    git_repo = settings.advanced_settings.bitcart_docker_repository or DOCKER_REPO_URL
    root_password = settings.ssh_settings.root_password
    reverseproxy = "nginx-https" if settings.domain_settings.https else "nginx"
    cryptos_str = ",".join(settings.coins.keys())
    installation_pack = settings.advanced_settings.installation_pack
    additional_components = sorted(set(settings.additional_services + settings.advanced_settings.additional_components))
    domain = settings.domain_settings.domain or "bitcart.local"
    script = ""
    if not root_password:
        script += "sudo su -"
    else:
        script += f'echo "{root_password}" | sudo -S sleep 1 && sudo su -'
    script += "\n"
    script += f"{install_package('git')}\n"
    script += (
        'if [ -d "bitcart-docker" ]; then echo "existing bitcart-docker folder found, pulling instead of cloning.";'
        " git pull; fi\n"
    )
    script += f'if [ ! -d "bitcart-docker" ]; then echo "cloning bitcart-docker"; git clone {git_repo} bitcart-docker; fi\n'
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


def create_ssh_client(ssh_settings):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=ssh_settings.host, username=ssh_settings.username, password=ssh_settings.password)
    return client


def remove_intermediate_lines(output):
    newoutput = ""
    for line in output.splitlines():
        if BASH_INTERMEDIATE_COMMAND in line or INTERMEDIATE_OUTPUT in line:
            continue
        newoutput += line + "\n"
    return newoutput


def remove_colors(output):
    return "\n".join([COLOR_PATTERN.sub("", line) for line in output.split("\n")])


def send_command(channel, command):
    channel.sendall(command + "\n")
    channel.sendall(f"{BASH_INTERMEDIATE_COMMAND}\n")  # To find command end
    finished = False
    counter = 0
    output = ""
    while not finished:
        if counter > MAX_OUTPUT_WAIT:
            counter = 0
            channel.sendall(f"{BASH_INTERMEDIATE_COMMAND}\n")
        while channel.recv_ready():
            data = channel.recv(BUFFER_SIZE).decode()
            output += data
            if INTERMEDIATE_OUTPUT in data:
                finished = True
        time.sleep(OUTPUT_INTERVAL)
        counter += 1
    return output


def execute_ssh_commands(commands, ssh_settings):
    try:
        client = create_ssh_client(ssh_settings)
        channel = client.invoke_shell()
        output = ""
        for command in commands.splitlines():
            output += send_command(channel, command)
        output = remove_intermediate_lines(output)
        output = remove_colors(output)
        channel.close()
        client.close()
        return True, output
    except Exception as e:
        error_message = ""
        try:
            error_message = e.strerror
        except Exception:
            pass
        return False, error_message
