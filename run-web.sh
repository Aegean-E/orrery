#!/usr/bin/env sh
set -u
cd "$(dirname "$0")" || exit 1

PYTHON=
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
            PYTHON=$candidate
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Python 3.10 or newer was not found." >&2
    exit 1
fi

if [ "$#" -eq 0 ]; then
    exec "$PYTHON" -m orrery web solar
fi
exec "$PYTHON" -m orrery web "$@"
