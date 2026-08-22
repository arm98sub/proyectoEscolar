from django.contrib import admin
from .models import (
    Alumno,
    Grupo,
    Maestro,
    Materia,
    TareaEncargada,
    TareaPendiente,
    Tutor,
)

# Registramos los modelos para que aparezcan en el panel /admin/
@admin.register(Grupo)
class GrupoAdmin(admin.ModelAdmin):
    list_display = ('grado', 'seccion', 'maestro') # Columnas que verás en la lista
    list_filter = ('maestro',) # Filtro rápido lateral por maestro

@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'grupo', 'semaforo', 'porcentaje_incumplimiento_tareas')
    list_filter = ('grupo',)
    search_fields = ('nombre',)

# --- REGISTRAMOS TU NUEVO MODELO AQUÍ ---
@admin.register(TareaPendiente)
class TareaPendienteAdmin(admin.ModelAdmin):
    list_display = ('alumno', 'materia', 'nombre_tarea', 'fecha_registro')
    list_filter = ('materia', 'alumno__grupo')  # Te permite filtrar tareas por materia o por el grupo del alumno
    search_fields = ('alumno__nombre', 'nombre_tarea')

admin.site.register(Materia)
admin.site.register(TareaEncargada)
admin.site.register(Maestro)
admin.site.register(Tutor)
