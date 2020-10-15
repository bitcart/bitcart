import asyncio

from api import invoices, settings


async def main():
    await settings.init_db()
    settings.manager.add_event_handler("new_payment", invoices.new_payment_handler)
    await settings.manager.start_websocket(reconnect_callback=invoices.check_pending, force_connect=True)


asyncio.get_event_loop().run_until_complete(main())
