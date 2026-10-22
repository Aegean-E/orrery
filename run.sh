#!/usr/bin/env sh
set -u
cd -- "$(dirname -- "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    echo "Python 3.10 or newer was not found." >&2
    exit 127
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
    echo "Python 3.10 or newer is required." >&2
    exit 1
fi

if [ "$#" -eq 0 ]; then
    exec "$PYTHON" -m orrery run solar
fi
exec "$PYTHON" -m orrery run "$@"
