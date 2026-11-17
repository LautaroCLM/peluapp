#!/bin/sh
set -e

# Aplica las migraciones antes de arrancar el servidor.
python manage.py migrate --noinput

exec "$@"
