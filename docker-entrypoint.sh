#!/bin/sh
set -e

# Aplica las migraciones antes de arrancar el servidor.
python manage.py migrate --noinput

# Carga datos de ejemplo si SEED_DEMO=true (idempotente: se puede dejar activado).
if [ "$SEED_DEMO" = "true" ]; then
    python manage.py seed_demo
fi

exec "$@"
