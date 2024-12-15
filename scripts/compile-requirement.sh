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
    SYSTEM_PYTHON=$(which python3.11) || printf ""
else
    SYSTEM_PYTHON=$(which $SYSTEM_PYTHON) || printf ""
fi
if [[ ! "$SYSTEM_PYTHON" ]]; then
    echo "Please specify which python to use in \$SYSTEM_PYTHON" && exit 1
fi

${SYSTEM_PYTHON} -m pip list | grep -E "^uv " >/dev/null 2>&1 || { ${SYSTEM_PYTHON} -m pip install uv; }
out_file=${1/requirements\//requirements/deterministic/}
$SYSTEM_PYTHON -m uv pip compile --generate-hashes -o $out_file $@
