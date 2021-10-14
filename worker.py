import asyncio
import signal
import sys
from multiprocessing import Process

from api import events, invoices, settings, tasks
from api.ext import backups as backup_ext
from api.ext import configurator as configurator_ext
from api.ext import tor as tor_ext
from api.ext import update as update_ext
from api.logserver import main as start_logserver
from api.logserver import wait_for_port
from api.utils.common import run_repeated


async def main():
    await settings.init()
    settings.log_startup_info()
    await tor_ext.refresh(log=False)  # to pre-load data for initial requests
    await update_ext.refresh()
    await configurator_ext.refresh_pending_deployments()
    await backup_ext.manager.start()
    asyncio.ensure_future(run_repeated(tor_ext.refresh, 60 * 10, 10))
    asyncio.ensure_future(run_repeated(update_ext.refresh, 60 * 60 * 24))
    settings.manager.add_event_handler("new_payment", invoices.new_payment_handler)
    settings.manager.add_event_handler("new_block", invoices.new_block_handler)
    await invoices.create_expired_tasks()  # to ensure invoices get expired actually
    coro = events.start_listening(tasks.event_handler)  # to avoid deleted task errors
    asyncio.ensure_future(coro)
    await settings.manager.start_websocket(reconnect_callback=invoices.check_pending, force_connect=True)


def handler(signum, frame):
    process.terminate()
    sys.exit()


if __name__ == "__main__":
    process = Process(target=start_logserver)
    process.start()
    wait_for_port()
    signal.signal(signal.SIGINT, handler)
    asyncio.run(main())
