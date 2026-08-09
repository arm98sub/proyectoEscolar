from django.db import models
from django.contrib.auth.models import User

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

class Maestro(models.Model):
    # Vinculamos al maestro con el sistema de usuarios nativo de Django para el Login
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_maestro')
    telefono = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"Profe. {self.user.first_name} {self.user.last_name}"

class Tutor(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    correo = models.EmailField(unique=True)
    telefono = models.CharField(max_length=20)
    # Relación Muchos a Muchos: Un papá puede tener varios hijos y un alumno varios tutores
    hijos = models.ManyToManyField(Alumno, related_name='tutores')

    def __str__(self):
        return f"Tutor: {self.nombre} {self.apellido}"

class Materia(models.Model):
    nombre = models.CharField(max_length=100) # Ej: "Matemáticas I"
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