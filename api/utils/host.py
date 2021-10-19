from api import settings
from api.ext.ssh import execute_ssh_command


def run_host(command):
    try:
        client = settings.settings.ssh_settings.create_ssh_client()
    except Exception as e:
        return False, f"Connection problem: {e}"
    try:
        execute_ssh_command(
            client,
            f'. {settings.settings.ssh_settings.bash_profile_script}; cd "$BITCART_BASE_DIRECTORY"'
            f"; nohup {command} > /dev/null 2>&1 & disown",
        )
    except Exception:  # pragma: no cover
        pass
    finally:
        client.close()
    return True, None


def run_host_output(command, ok_output):
    ok, error = run_host(command)
    if ok:
        return {"status": "success", "message": ok_output}
    return {"status": "error", "message": error}
