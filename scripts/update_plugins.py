#!/usr/bin/env python3

import sys

sys.path.insert(0, ".")

import asyncio

from api.ioc import build_container
from api.plugins import PluginObjects
from api.services.plugin_manager import PluginManager
from api.settings import Settings


async def main() -> None:
    container = build_container(Settings(), include_plugins=False, context_overrides={PluginObjects: {}})
    try:
        results = await (await container.get(PluginManager)).update_plugins()
    finally:
        await container.close()
    if not results:
        print("Plugins are up to date")
    for name, result in results.items():
        print(f"{name}: {result}")


if __name__ == "__main__":
    asyncio.run(main())
