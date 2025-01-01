#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, ".")

from alembic.config import CommandLine, Config
from api import settings  # noqa: F401: to avoid circular import
from api.plugins import PluginsManager

if len(sys.argv) < 3:
    sys.exit("Usage: pluginmigrate.py <plugin_name> <alembic commands>")

plugin_name = sys.argv[1]

manager = PluginsManager()
if plugin_name not in manager.plugins:
    sys.exit(f"Plugin {plugin_name} not found")

cmd = CommandLine(prog="pluginmigrate")
plugin = manager.plugins[plugin_name]
config = Config("alembic.ini")
config.set_main_option("plugin_name", plugin.name)
config.set_main_option("version_locations", os.path.join(plugin.path, "versions"))
options = cmd.parser.parse_args(sys.argv[2:])
cmd.run_cmd(config, options)
