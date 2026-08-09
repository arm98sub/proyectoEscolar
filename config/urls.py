
from django.contrib import admin
from django.urls import path
from .api import api  # Importamos el objeto 'api' que creaste en api.py
from alumnos.views import dashboard_maestro, login_view, logout_view,detalle_alumno, marcar_tarea_entregada,agregar_tarea_pendiente
from alumnos import views  # <-- Importamos el archivo views de la app alumnos
urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/", api.urls),
    # La nueva ruta visual para tu junta del viernes:
    path('dashboard/', dashboard_maestro, name='dashboard'),
    path('logout/', logout_view, name='logout'),
    # Nuevas rutas del Expediente:
    path('alumno/<int:alumno_id>/', detalle_alumno, name='detalle_alumno'),
    path('alumno/<int:alumno_id>/tarea/<int:tarea_id>/entregar/', marcar_tarea_entregada, name='marcar_tarea'),
    # --- NUEVA RUTA AQUÍ ---
    path('alumno/<int:alumno_id>/agregar-tarea/', agregar_tarea_pendiente, name='agregar_tarea_pendiente'),
    path('tarea-encargada/nueva/', views.registrar_tarea_encargada, name='registrar_tarea_encargada'),
]
