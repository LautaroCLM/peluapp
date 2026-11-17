FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Primero solo las dependencias: así Docker reutiliza la capa si el código cambia.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# collectstatic no toca la base; las variables son valores de relleno solo para el build.
RUN SECRET_KEY=build-only-not-a-real-secret-key-0000 \
    DATABASE_URL=postgres://u:p@localhost/db \
    python manage.py collectstatic --noinput

# Usuario sin privilegios: el contenedor no corre como root.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
