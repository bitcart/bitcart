#!/usr/bin/env bash

set -e

# this script syncs your environment with the deterministic requirements files
# do this after changing those files

for file in requirements/deterministic/*.txt requirements/deterministic/daemons/*.txt; do
    pip install -r $file
done

set +e
