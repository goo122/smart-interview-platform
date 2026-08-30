#!/bin/sh
set -eu

if [ -d /app/storage ]; then
  chown -R appuser:appuser /app/storage
fi

exec runuser --user appuser -- "$@"
