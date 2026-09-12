# Proyecto Escolar — Colegio del Centro

Sistema Django para que docentes registren actividades no entregadas e inasistencias,
la ATP supervise el cumplimiento de los reportes y las familias consulten el avance de
sus hijos.

## Ejecutar localmente con Docker

Desde Ubuntu, dentro de `/home/sub0/proyecto-escuela`:

```bash
docker compose up -d --build
docker compose exec web uv run python manage.py migrate
docker compose exec web uv run python manage.py test
```

La aplicación queda disponible en <http://localhost:8000/>. Docker utiliza PostgreSQL
y conserva su volumen existente; estos comandos no reemplazan ni borran los datos.

## Crear el escenario ficticio local

La carga es idempotente: puede ejecutarse más de una vez y sólo crea o actualiza los
registros marcados como `DEMO`. No elimina información real.

```bash
docker compose exec \
  -e DEMO_ADMIN_PASSWORD='CAMBIAR-ATP' \
  -e DEMO_TEACHER_PASSWORD='CAMBIAR-DOCENTE' \
  -e DEMO_TUTOR_PASSWORD='CAMBIAR-FAMILIA' \
  web uv run python manage.py seed_demo --force
```

Usuarios creados: `atp.demo`, `docente.demo` y `familia.demo`. Las contraseñas son las
que se indiquen en el comando y no se muestran ni se almacenan en Git.

## Demostración en Render + Neon

El archivo `render.yaml` contiene la configuración de la aplicación. Para publicarla:

1. Crear un proyecto PostgreSQL gratuito en Neon y copiar su cadena de conexión.
2. En Render, elegir **New > Blueprint** y conectar este repositorio.
3. Proporcionar `DATABASE_URL` con la cadena de Neon.
4. Definir contraseñas distintas y seguras para `DEMO_ADMIN_PASSWORD`,
   `DEMO_TEACHER_PASSWORD` y `DEMO_TUTOR_PASSWORD`.
5. Crear el servicio y esperar a que `/health/` responda `{"status": "ok"}`.

Render configura automáticamente HTTPS, la clave secreta, los archivos estáticos, las
migraciones y la carga ficticia. No deben cargarse datos reales de alumnos en este
entorno gratuito de demostración.

## Variables de producción

- `DATABASE_URL`: conexión PostgreSQL externa.
- `DJANGO_SECRET_KEY`: valor secreto y aleatorio.
- `DJANGO_ALLOWED_HOSTS`: nombres permitidos, separados por comas.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: direcciones HTTPS permitidas, separadas por comas.
- `DJANGO_SECURE_SSL_REDIRECT=True`: obliga a utilizar HTTPS.
- `DJANGO_LOAD_DEMO_DATA=True`: habilita exclusivamente la carga ficticia.

El servidor de producción usa Gunicorn y WhiteNoise. Docker Compose conserva el
servidor de desarrollo para el trabajo cotidiano en Ubuntu.
