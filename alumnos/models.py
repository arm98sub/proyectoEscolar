from django.db import models
from django.contrib.auth.models import User
import datetime
from django.db import models
from django.db.models import Sum


class Grupo(models.Model):
    grado = models.IntegerField() # Ej: 1, 2, 3
    seccion = models.CharField(max_length=10) # Ej: "A", "B"
    # Nuevo campo: Cada grupo tiene un maestro asignado. 
    # Si se borra el usuario, el grupo no se borra, solo queda en blanco (null=True).
    maestro = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='grupos_asignados')

    def __str__(self):
        return f"{self.grado}°{self.seccion}"

class Alumno(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE, related_name='alumnos')
    promedio_actual = models.FloatField(default=0.0)
    asistencias_totales = models.IntegerField(default=0)
    clases_totales = models.IntegerField(default=30)
    total_tareas_encargadas = models.IntegerField(default=0) # Denominador para el %

    def __str__(self):
        return f"{self.nombre} {self.apellido}"
    
    @property
    def total_tareas_pendientes(self):
        # Cuenta cuántas tareas debe el alumno actualmente
        return self.detalles_tareas.count()

    @property
    def porcentaje_incumplimiento_tareas(self):
        # Contamos cuántas tareas en total ha encargado el maestro a este grupo
        total_encargadas = TareaEncargada.objects.filter(grupo=self.grupo).count()        
        # Si aún no se ha registrado ninguna tarea en el sistema, evitamos división entre cero
        if total_encargadas == 0:
            return 0.0
        
        faltas = self.total_tareas_pendientes

        # 2. Calculamos el porcentaje directo
        porcentaje = (faltas / total_encargadas) * 100

        # 3. Topamos el valor a 100.0% para evitar inconsistencias en la interfaz/semáforos
        porcentaje_final = min(porcentaje, 100.0)
        
        return round(porcentaje_final, 1)

    @property
    def semaforo(self):
        # Lógica oficial de SisAT basada en el porcentaje de incumplimiento
        porcentaje = self.porcentaje_incumplimiento_tareas
        
        if porcentaje == 0:
            return 'VERDE'  # Si no debe nada, está a salvo
        elif porcentaje <= 20:
            return 'VERDE'  # 1 o 2 tareas debidas de 10
        elif porcentaje <= 40:
            return 'AMARILLO'  # 3 o 4 tareas debidas de 10
        else:
            return 'ROJO'  # 5 o más tareas debidas (Alerta Crítica)
        
    # En alumnos/models.py dentro de la clase Alumno:

    def obtener_semaforo_materia(self, materia):
        """
        Calcula el semáforo y métricas acumuladas de un alumno en una materia específica
        sumando todos los periodos registrados hasta la fecha.
        """
        # 1. Total de tareas encargadas en todos los periodos de esta materia
        total_encargadas = RegistroTareasPeriodo.objects.filter(
            materia=materia,
            grupo=self.grupo
        ).aggregate(total=Sum('total_tareas_encargadas'))['total'] or 0

        # 2. Total de tareas NO entregadas por el alumno en esta materia
        tareas_no_entregadas = DetalleTareaAlumno.objects.filter(
            registro_periodo__materia=materia,
            alumno=self
        ).aggregate(total=Sum('tareas_no_entregadas'))['total'] or 0

        # 3. Cálculo de porcentaje de cumplimiento acumulado
        if total_encargadas > 0:
            tareas_entregadas = max(0, total_encargadas - tareas_no_entregadas)
            porcentaje_cumplimiento = round((tareas_entregadas / total_encargadas) * 100, 1)
        else:
            porcentaje_cumplimiento = 100.0 if tareas_no_entregadas == 0 else 0.0

        # 4. Total de inasistencias acumuladas en esta materia por periodos
        total_faltas = DetalleInasistenciaAlumno.objects.filter(
            registro_periodo__materia=materia,
            alumno=self
        ).aggregate(total=Sum('total_faltas'))['total'] or 0

        # 5. Determinación de color y niveles del Semáforo
        if tareas_no_entregadas >= 3 or total_faltas >= 5 or porcentaje_cumplimiento < 70:
            color_data = {
                'color': 'rojo',
                'etiqueta': 'Riesgo Alto',
                'bg_class': 'bg-red-500',
                'text_class': 'text-red-700',
                'bg_light': 'bg-red-50',
                'border_class': 'border-red-200',
            }
        elif (1 <= tareas_no_entregadas <= 2) or (3 <= total_faltas <= 4) or (70 <= porcentaje_cumplimiento < 85):
            color_data = {
                'color': 'amarillo',
                'etiqueta': 'Atención',
                'bg_class': 'bg-amber-500',
                'text_class': 'text-amber-700',
                'bg_light': 'bg-amber-50',
                'border_class': 'border-amber-200',
            }
        else:
            color_data = {
                'color': 'verde',
                'etiqueta': 'Al Día',
                'bg_class': 'bg-emerald-500',
                'text_class': 'text-emerald-700',
                'bg_light': 'bg-emerald-50',
                'border_class': 'border-emerald-200',
            }

        color_data.update({
            'porcentaje_tareas': porcentaje_cumplimiento,
            'tareas_pendientes': tareas_no_entregadas,
            'total_encargadas': total_encargadas,
            'faltas': total_faltas
        })

        return color_data

class Maestro(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='maestro', null=True, blank=True)
    nombre = models.CharField(max_length=100)
    apellido_paterno = models.CharField(max_length=100)
    apellido_materno = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} {self.apellido_paterno} {self.apellido_materno}".strip()

class Tutor(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='tutor',
        null=True,
        blank=True,
    )
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    correo = models.EmailField(unique=True)
    telefono = models.CharField(max_length=20)
    # Relación Muchos a Muchos: Un papá puede tener varios hijos y un alumno varios tutores
    hijos = models.ManyToManyField(Alumno, related_name='tutores')

    def __str__(self):
        return f"Tutor: {self.nombre} {self.apellido}"

class CatalogoMateria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = "Materia del catálogo"
        verbose_name_plural = "Catálogo de materias"

    def __str__(self):
        return self.nombre


class Materia(models.Model):
    nombre = models.CharField(max_length=100) # Ej: "Matemáticas I"
    catalogo = models.ForeignKey(
        CatalogoMateria,
        on_delete=models.PROTECT,
        related_name='asignaciones',
        null=True,
        blank=True,
    )
    maestro = models.ForeignKey(Maestro, on_delete=models.CASCADE, related_name='materias')
    grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE, related_name='materias')

    def __str__(self):
        return f"{self.nombre} - {self.grupo}"

class TareaPendiente(models.Model):
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name='detalles_tareas')
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='tareas_no_entregadas')
    nombre_tarea = models.CharField(max_length=200) # Ej: "Contestar pág 45"
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Falta: {self.alumno.nombre} - {self.nombre_tarea} ({self.materia.nombre})"
    

class TareaEncargada(models.Model):
    grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE, related_name='tareas_encargadas')
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='tareas_encargadas')
    titulo = models.CharField(max_length=200)
    fecha_encargo = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.materia.nombre} - {self.titulo} ({self.grupo})"
    
class InasistenciaPeriodo(models.Model):
    grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE, related_name='inasistencias_periodo')
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='inasistencias', null=True, blank=True)
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name='inasistencias')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    total_faltas = models.PositiveIntegerField(default=0)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Inasistencia por Periodo"
        verbose_name_plural = "Inasistencias por Periodo"

    def __str__(self):
        materia_str = f" - {self.materia.nombre}" if self.materia else ""
        return f"{self.alumno}{materia_str} - {self.total_faltas} faltas"

# Para gestionar las tareas no entregadas
MESES_ESPANOL = {
    1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
    5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
    9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
}

def formatear_rango_fechas(fecha_inicio, fecha_fin):
    """
    Construye un nombre amigable para el periodo.
    Ejemplo: 'Del 13 de mayo al 23 de junio' o 'Del 13 de mayo al 23 de mayo de 2026'
    """
    if not fecha_inicio or not fecha_fin:
        return "Periodo no especificado"

    dia_ini = fecha_inicio.day
    mes_ini = MESES_ESPANOL.get(fecha_inicio.month, '')
    
    dia_fin = fecha_fin.day
    mes_fin = MESES_ESPANOL.get(fecha_fin.month, '')

    if mes_ini == mes_fin:
        return f"Del {dia_ini} al {dia_fin} de {mes_fin}"
    else:
        return f"Del {dia_ini} de {mes_ini} al {dia_fin} de {mes_fin}"


# ==========================================
# 1. MODELOS DE TAREAS POR PERIODO
# ==========================================

class RegistroTareasPeriodo(models.Model):
    materia = models.ForeignKey('Materia', on_delete=models.CASCADE, related_name='registros_tareas')
    grupo = models.ForeignKey('Grupo', on_delete=models.CASCADE, related_name='registros_tareas')
    nombre_periodo = models.CharField(max_length=150, blank=True, help_text="Se genera automáticamente según las fechas")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    total_tareas_encargadas = models.PositiveIntegerField(default=0, help_text="Total de tareas encargadas en este periodo")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de Tareas por Periodo"
        verbose_name_plural = "Registros de Tareas por Periodo"
        ordering = ['-fecha_inicio']

    def save(self, *args, **kwargs):
        # Generación automática del nombre del periodo
        self.nombre_periodo = formatear_rango_fechas(self.fecha_inicio, self.fecha_fin)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.materia.nombre} - {self.nombre_periodo} ({self.grupo})"


class DetalleTareaAlumno(models.Model):
    registro_periodo = models.ForeignKey(RegistroTareasPeriodo, on_delete=models.CASCADE, related_name='detalles_alumnos')
    alumno = models.ForeignKey('Alumno', on_delete=models.CASCADE, related_name='detalles_tareas_periodo')
    tareas_no_entregadas = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Detalle de Tarea por Alumno"
        verbose_name_plural = "Detalles de Tareas por Alumno"
        unique_together = ('registro_periodo', 'alumno')

    def __str__(self):
        return f"{self.alumno} | {self.registro_periodo.nombre_periodo}: {self.tareas_no_entregadas} no entregadas"


# ==========================================
# 2. MODELOS DE INASISTENCIAS POR PERIODO
# ==========================================

class RegistroInasistenciasPeriodo(models.Model):
    materia = models.ForeignKey('Materia', on_delete=models.CASCADE, related_name='registros_inasistencias')
    grupo = models.ForeignKey('Grupo', on_delete=models.CASCADE, related_name='registros_inasistencias')
    nombre_periodo = models.CharField(max_length=150, blank=True, help_text="Se genera automáticamente según las fechas")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de Inasistencias por Periodo"
        verbose_name_plural = "Registros de Inasistencias por Periodo"
        ordering = ['-fecha_inicio']

    def save(self, *args, **kwargs):
        # Generación automática del nombre del periodo
        self.nombre_periodo = formatear_rango_fechas(self.fecha_inicio, self.fecha_fin)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Inasistencias {self.materia.nombre} - {self.nombre_periodo} ({self.grupo})"


class DetalleInasistenciaAlumno(models.Model):
    registro_periodo = models.ForeignKey(RegistroInasistenciasPeriodo, on_delete=models.CASCADE, related_name='detalles_alumnos')
    alumno = models.ForeignKey('Alumno', on_delete=models.CASCADE, related_name='detalles_inasistencias_periodo')
    total_faltas = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Detalle de Inasistencia por Alumno"
        verbose_name_plural = "Detalles de Inasistencias por Alumno"
        unique_together = ('registro_periodo', 'alumno')

    def __str__(self):
        return f"{self.alumno} | {self.registro_periodo.nombre_periodo}: {self.total_faltas} faltas"
    
    
