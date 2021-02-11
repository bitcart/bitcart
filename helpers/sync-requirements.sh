#!/usr/bin/env bash

# this script syncs your environment with the requirements files

for file in requirements/*.txt requirements/daemons/*.txt; do
    pip install -r $file
done