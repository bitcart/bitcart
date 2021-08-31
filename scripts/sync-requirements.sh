#!/usr/bin/env bash

# this script syncs your environment with the deterministic requirements files
# do this after changing those files

for file in requirements/deterministic/*.txt requirements/deterministic/daemons/*.txt; do
    pip install -r $file
done
