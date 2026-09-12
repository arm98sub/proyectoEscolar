
from django.contrib import admin
from django.urls import path
from .api import api  # Importamos el objeto 'api' que creaste en api.py
from alumnos.views import dashboard_maestro, login_view, logout_view,detalle_alumno, marcar_tarea_entregada,agregar_tarea_pendiente
from alumnos import views  # <-- Importamos el archivo views de la app alumnos
from config.views import health_check
urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('', login_view, name='home'),
    path('login/', login_view, name='login'),
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
    path('tareas-encargadas/', views.lista_tareas_encargadas, name='lista_tareas_encargadas'),
    path('tareas-encargadas/<int:tarea_id>/editar/', views.editar_tarea_encargada, name='editar_tarea_encargada'),
    path('tareas-encargadas/<int:tarea_id>/eliminar/', views.eliminar_tarea_encargada, name='eliminar_tarea_encargada'),
    path('grupo/<int:grupo_id>/faltas-periodo/', views.registrar_faltas_periodo, name='registrar_faltas_periodo'),
    path('tutor/login/', views.login_tutor, name='login_tutor'),
    path('tutor/tablero/', views.tablero_tutor, name='tablero_tutor'),
    path('tutor/logout/', views.logout_tutor, name='logout_tutor'),
    path('grupo/<int:grupo_id>/materia/<int:materia_id>/registrar-tareas/', views.registrar_tareas_periodo, name='registrar_tareas_periodo'),
    path('docente/dashboard/', views.dashboard_maestro, name='dashboard_maestro'),
    path('materia/<int:materia_id>/centro-mando/', views.centro_mando_materia, name='centro_mando_materia'),
    path('admin-panel/maestros/nuevo/', views.registrar_maestro, name='registrar_maestro'),
    path('admin-panel/tutores/', views.registrar_tutor, name='registrar_tutor'),
    path('admin-panel/tutores/<int:tutor_id>/editar/', views.editar_tutor, name='editar_tutor'),
    path('admin-panel/tutores/<int:tutor_id>/estado/', views.cambiar_estado_tutor, name='cambiar_estado_tutor'),
    path('admin-panel/tutores/<int:tutor_id>/eliminar/', views.eliminar_tutor, name='eliminar_tutor'),
    path('admin-panel/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/ciclos/', views.gestionar_ciclos, name='gestionar_ciclos'),
    path('admin-panel/ciclos/<int:ciclo_id>/activar/', views.activar_ciclo, name='activar_ciclo'),
    path('admin-panel/ciclos/<int:ciclo_id>/cerrar/', views.cerrar_ciclo, name='cerrar_ciclo'),
    path('admin-panel/reportes/periodos/', views.gestionar_periodos_reportes, name='gestionar_periodos_reportes'),
    path('admin-panel/reportes/', views.tablero_reportes_atp, name='tablero_reportes_atp'),
    path('admin-panel/materia/<slug:identificador>/grupos/', views.admin_materia_grupos, name='admin_materia_grupos'),
    path('admin-panel/maestros/<int:maestro_id>/editar/', views.editar_maestro, name='editar_maestro'),
    path('admin-panel/maestros/<int:maestro_id>/eliminar/', views.eliminar_maestro, name='eliminar_maestro'),
    path('admin-panel/maestros/<int:maestro_id>/estado/', views.cambiar_estado_maestro, name='cambiar_estado_maestro'),
    path('admin-panel/materias/nueva/', views.registrar_materia, name='registrar_materia'),
    path('admin-panel/materias/catalogo/nueva/', views.registrar_catalogo_materia, name='registrar_catalogo_materia'),
    path('admin-panel/materias/<int:materia_id>/editar/', views.editar_materia, name='editar_materia'),
    path('admin-panel/materias/<int:materia_id>/eliminar/', views.eliminar_materia, name='eliminar_materia'),
]
