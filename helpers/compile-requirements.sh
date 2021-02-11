#!/usr/bin/env bash

# this script re-compiles requirements files

for file in requirements/src/*.txt requirements/src/daemons/*.txt; do
    pip-compile --generate-hashes --allow-unsafe $file -o ${file/\/src/}
done