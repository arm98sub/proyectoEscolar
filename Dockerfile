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

# Comando para correr el servidor
CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]