import os

if os.getenv("BITCART_OTEL_ENABLED", "false").lower() == "true":
    from api.otel import initialize

    initialize()

import asyncio
from multiprocessing import Process

from api.logserver import main as start_logserver
from api.logserver import wait_for_port

# TODO: use CLI from taskiq
if __name__ == "__main__":
    process = Process(target=start_logserver)
    process.daemon = True
    process.start()
    # imported after start(): otherwise the log server process re-runs this module's imports
    from api.worker import get_app, start_broker, wait_loop

    wait_for_port()
    asyncio.run(wait_loop())
    broker = get_app(process)
    asyncio.run(start_broker(broker))
