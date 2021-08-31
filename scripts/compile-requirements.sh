#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

for file in requirements/*.txt requirements/daemons/*.txt; do
    $SCRIPT_DIR/compile-requirement.sh "$file"
done
