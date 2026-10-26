#!/usr/bin/env python3

import argparse
import asyncio
import sys

from fastapi import FastAPI
from starlette.routing import BaseRoute

sys.path.insert(0, ".")

from api.bootstrap import configure_production_app
from api.openapi import DumpError, dump_openapi, get_dump_schema
from api.services.plugin_registry import PluginRegistry

DEFAULT_DESTINATION = "openapi.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dump the OpenAPI schema")
    parser.add_argument("destination", nargs="?", default=DEFAULT_DESTINATION, help="output file, - for stdout")
    parser.add_argument("--private", action="store_true", help="include private routes")
    parser.add_argument("--plugin", help="dump only the routes of this plugin")
    parser.add_argument(
        "--tags",
        type=lambda value: value.split(","),
        action="extend",
        default=[],
        help="comma-separated group tags to keep",
    )
    return parser.parse_args()


async def setup_plugins(app: FastAPI) -> dict[str, list[BaseRoute]]:
    container = app.state.dishka_container
    try:
        plugin_registry = await container.get(PluginRegistry)
        plugin_registry.setup_app(app)
        return plugin_registry.plugin_routes
    finally:
        await container.close()


args = parse_args()
app = configure_production_app()
try:
    schema = get_dump_schema(
        app,
        include_private=args.private,
        plugin=args.plugin,
        plugin_routes=asyncio.run(setup_plugins(app)) if args.plugin else None,
        groups=args.tags,
    )
except DumpError as e:
    sys.exit(str(e))
payload = dump_openapi(schema)

if args.destination == "-":
    sys.stdout.write(payload)
else:
    with open(args.destination, "w") as f:
        f.write(payload)
    print(f"Wrote {len(schema['paths'])} paths to {args.destination}", file=sys.stderr)
