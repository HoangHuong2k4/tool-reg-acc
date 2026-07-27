#!/bin/sh
set -e

# Migration logic (creating tables) is handled in src/web/app.py upon start.
exec "$@"
