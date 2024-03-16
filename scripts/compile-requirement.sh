#!/usr/bin/env bash

# this script re-compiles requirements files
# run this when updating something, when doing maintenance releases
# afterwards run sync-requirements.sh to get deterministic environment, the same as to be used on builds

# note: we should use the same version of python (major.minor at least) that is used in docker images

if [ -z "$1" ]; then
    echo "Usage: $0 requirements/file.txt"
    exit 1
fi

if [[ ! "$SYSTEM_PYTHON" ]]; then
    SYSTEM_PYTHON=$(which python3.9) || printf ""
else
    SYSTEM_PYTHON=$(which $SYSTEM_PYTHON) || printf ""
fi
if [[ ! "$SYSTEM_PYTHON" ]]; then
    echo "Please specify which python to use in \$SYSTEM_PYTHON" && exit 1
fi

${SYSTEM_PYTHON} -m piptools --help >/dev/null 2>&1 || { ${SYSTEM_PYTHON} -m pip install pip-tools; }
out_file=${1/requirements\//requirements/deterministic/}
$SYSTEM_PYTHON -m piptools compile --generate-hashes --allow-unsafe --resolver=legacy -o $out_file $@
