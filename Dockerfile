# Usamos una imagen de Python oficial
FROM python:3.12-slim

# Evita archivos .pyc y permite ver logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Directorio de trabajo
WORKDIR /code

# Instalamos dependencias del sistema necesarias para psycopg2 y curl
RUN apt-get update && apt-get install -y \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Instalamos uv usando el script oficial
ADD https://astral.sh/uv/install.sh /install.sh
RUN chmod +x /install.sh && /install.sh && rm /install.sh
ENV PATH="/root/.local/bin/:$PATH"

# Copiamos archivos de dependencias
COPY pyproject.toml uv.lock ./

# Instalamos las dependencias del proyecto
RUN uv sync --frozen

# Copiamos el resto del código
COPY . .

# Servidor de producción. Docker Compose reemplaza este comando en desarrollo.
CMD ["sh", "-c", "uv run python manage.py migrate && uv run python manage.py collectstatic --noinput && uv run python manage.py seed_demo && uv run gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120"]
