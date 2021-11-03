from api import settings
from api.ext.ssh import execute_ssh_command
from api.logger import get_exception_message, get_logger

logger = get_logger(__name__)


def run_host(command, env={}):
    try:
        client = settings.settings.ssh_settings.create_ssh_client()
    except Exception as e:
        return False, f"Connection problem: {e}"
    env_vars = " ".join([f"{k}={v}" for k, v in env.items()])
    try:
        execute_ssh_command(
            client,
            f'. {settings.settings.ssh_settings.bash_profile_script}; cd "$BITCART_BASE_DIRECTORY"'
            f"; {env_vars} nohup {command} > /dev/null 2>&1 & disown",
        )
    except Exception as e:  # pragma: no cover
        logger.error(get_exception_message(e))
    finally:
        client.close()
    return True, None


def run_host_output(command, ok_output, env={}):
    ok, error = run_host(command, env=env)
    if ok:
        return {"status": "success", "message": ok_output}
    return {"status": "error", "message": error}
