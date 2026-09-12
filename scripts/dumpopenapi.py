#!/usr/bin/env python3

import sys

sys.path.insert(0, ".")

from api.bootstrap import configure_production_app
from api.openapi import dump_openapi

DEFAULT_DESTINATION = "openapi.json"

destination = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DESTINATION
schema = configure_production_app().openapi()
payload = dump_openapi(schema)

if destination == "-":
    sys.stdout.write(payload)
else:
    with open(destination, "w") as f:
        f.write(payload)
    print(f"Wrote {len(schema['paths'])} paths to {destination}", file=sys.stderr)
