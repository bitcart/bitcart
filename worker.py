import asyncio
import signal
import sys
import time
from multiprocessing import Process

import sqlalchemy

from alembic import config, script
from alembic.runtime import migration
from api import events, invoices
from api import settings as settings_module
from api import tasks
from api.ext import backups as backup_ext
from api.ext import configurator as configurator_ext
from api.ext import tor as tor_ext
from api.ext import update as update_ext
from api.logserver import main as start_logserver
from api.logserver import wait_for_port
from api.settings import Settings
from api.utils.common import run_repeated


def check_db():
    try:
        settings = settings_module.settings_ctx.get()
        if settings.test:
            return True
        engine = sqlalchemy.create_engine(settings.connection_str)
        alembic_cfg = config.Config("alembic.ini")
        script_ = script.ScriptDirectory.from_config(alembic_cfg)
        with engine.begin() as conn:
            context = migration.MigrationContext.configure(conn)
            if context.get_current_revision() != script_.get_current_head():
                return False
        return True
    except Exception:
        return False


async def main():
    settings = settings_module.settings_ctx.get()
    try:
        await settings_module.init()
        settings_module.log_startup_info()
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
    finally:
        await settings.shutdown()


def handler(signum, frame):
    process.terminate()
    sys.exit()


if __name__ == "__main__":
    settings = Settings()
    try:
        token = settings_module.settings_ctx.set(settings)
        process = Process(target=start_logserver)
        process.start()
        wait_for_port()
        signal.signal(signal.SIGINT, handler)
        # wait for db
        while True:
            if check_db():
                break
            print("Database not available/not migrated, waiting...")
            time.sleep(1)
        asyncio.run(main())
    finally:
        settings_module.settings_ctx.reset(token)
