from api import settings
from api.ext.ssh import execute_ssh_command
from api.logger import get_exception_message, get_logger

logger = get_logger(__name__)


def run_host(command, env={}, disown=True):
    try:
        client = settings.settings.ssh_settings.create_ssh_client()
    except Exception as e:
        return False, f"Connection problem: {e}"
    env_vars = " ".join([f"{k}={v}" for k, v in env.items()])
    try:
        output = execute_ssh_command(
            client,
            f'. {settings.settings.ssh_settings.bash_profile_script}; cd "$BITCART_BASE_DIRECTORY"; {env_vars} nohup {command}'
            + (" & disown" if disown else ""),
        )
        if disown:
            return True, None
        else:  # pragma: no cover
            final_out = output[1].read().decode() + "\n" + output[2].read().decode()
            final_out = final_out.strip()
            exitcode = output[1].channel.recv_exit_status()
            if exitcode != 0:
                return False, final_out
            return True, final_out
    except Exception as e:  # pragma: no cover
        logger.error(get_exception_message(e))
        return False, f"Command execution problem: {e}"
    finally:
        client.close()


def run_host_output(command, ok_output, env={}):
    ok, error = run_host(command, env=env)
    if ok:
        return {"status": "success", "message": ok_output}
    return {"status": "error", "message": error}
