#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ ! -x .venv/bin/python ]; then
    printf '%s\n' 'First run: python3 -m venv .venv && .venv/bin/python -m pip install -e ".[gui]"'
    exit 1
fi
exec .venv/bin/python -m leafpress gui
