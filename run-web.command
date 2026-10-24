#!/bin/sh
set -u
cd "$(dirname "$0")" || exit 1

sh ./run-web.sh "$@"
status=$?
echo
printf 'Press Return to close... '
read -r _
exit "$status"
