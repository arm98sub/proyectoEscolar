from ninja import NinjaAPI, Schema
from django.shortcuts import get_object_or_404
from typing import List
from datetime import datetime
from alumnos.models import Alumno, TareaPendiente, Materia, Grupo, Tutor

api = NinjaAPI(title="API PROBANDO CAMBIOS ALAN", version="1.0.0")

# --- SCHEMAS ---

class GrupoSchema(Schema):
    id: int
    grado: int
    seccion: str

class AlumnoOut(Schema):
    id: int
    nombre: str
    apellido: str
    grupo: GrupoSchema
    promedio_actual: float
    semaforo: str
    porcentaje_incumplimiento_tareas: float

class TareaIn(Schema):
    alumno_id: int
    materia_id: int
    nombre_tarea: str

class DetalleTareaOut(Schema):
    id: int
    nombre_tarea: str
    fecha_registro: datetime


# --- ENDPOINTS ---

@api.get("/alumnos", response=List[AlumnoOut])
def listar_alumnos(request):
    return Alumno.objects.select_related('grupo').all()

# --- COLOCADOS AQUÍ ABAJO PARA ASEGURAR SU REGISTRO ---

@api.get("/consultar-tutores/{tutor_id}/hijos", response=List[AlumnoOut])
def api_listar_hijos_tutor(request, tutor_id: int):
    tutor = get_object_or_404(Tutor, id=tutor_id)
    return tutor.hijos.select_related('grupo').all()

@api.get("/consultar-alumnos/{alumno_id}/tareas", response=List[DetalleTareaOut])
def api_listar_tareas_pendientes(request, alumno_id: int):
    return TareaPendiente.objects.filter(alumno_id=alumno_id)

# --- TUS OTROS ENDPOINTS ---

@api.get("/alerta-temprana")
def alumnos_en_riesgo(request):
    return Alumno.objects.filter(promedio_actual__lt=6.0)

@api.get("/estado/{alumno_id}")
def obtener_estatus_alumno(request, alumno_id: int):
    alumno = get_object_or_404(Alumno, id=alumno_id)
    return {"alumno": alumno.nombre, "semaforo": alumno.semaforo}

@api.get("/grupos/resumen")
def resumen_grupos(request):
    return {"status": "ok"}

@api.post("/tareas/reportar-falta")
def reportar_tarea_pendiente(request, payload: TareaIn):
    alumno = get_object_or_404(Alumno, id=payload.alumno_id)
    materia = get_object_or_404(Materia, id=payload.materia_id)
    
    TareaPendiente.objects.create(
        alumno=alumno,
        materia=materia,
        nombre_tarea=payload.nombre_tarea
    )
    
    alumno.total_tareas_encargadas += 1
    alumno.save()
    
    return {"success": True, "message": f"Falta registrada para {alumno.nombre}."}