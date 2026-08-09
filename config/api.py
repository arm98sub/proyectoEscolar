from ninja import NinjaAPI, Schema
from django.shortcuts import get_object_or_404
from typing import List
from datetime import datetime
# Importamos los modelos apuntando correctamente a la app alumnos
from alumnos.models import Alumno, TareaPendiente, Materia, Grupo, Tutor
from ninja.errors import HttpError
from django.utils import timezone
import csv
import io
from ninja import File
from ninja.files import UploadedFile
from django.http import JsonResponse
from django.http import HttpResponse
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

api = NinjaAPI(title="API Proyecto Escuela", version="1.0.0")

# --- AGREGA AQUÍ LOS SCHEMAS NUEVOS SI NO ESTABAN ---

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


class ResumenSemaforoGrupo(Schema):
    grupo_id: int
    grado: int
    seccion: str
    materia_nombre: str
    materia_id: int
    total_alumnos: int
    verdes: int
    amarillos: int
    rojos: int

class MaestroOut(Schema):
    id: int
    nombre_completo: str
    # Si tu modelo tiene apellido, puedes descomentar la siguiente línea:
    # apellido: str


class AlumnoAlertaOut(Schema):
    id: int
    nombre_completo: str
    grado: int
    seccion: str
    total_tareas_encargadas: int
    porcentaje_incumplimiento: int
    semaforo: str

class HistorialTareaOut(Schema):
    materia_nombre: str
    fecha: str  # O 'date' según guardes la fecha del reporte
    entrego: bool
    observaciones: str


class ReporteTutorOut(Schema):
    alumno_id: int
    nombre_completo: str
    mensaje_whatsapp: str

# --- TUS ENDPOINTS ORIGINALES (Los que ya veías) ---



# GET /api/alumnos con filtros avanzados (Nombre, Grupo y Semáforo)
@api.get("/alumnos", response=List[AlumnoOut])  # Asegúrate de usar tu Schema 'AlumnoOut'
def listar_alumnos_con_filtros(
    request, 
    nombre: str = None, 
    grupo_id: int = None, 
    semaforo: str = None
):
    # Empezamos con todos los alumnos de la base de datos
    queryset = Alumno.objects.select_related('grupo').all()
    
    # 1. Filtro por nombre (busca coincidencias parciales sin importar mayúsculas/minúsculas)
    if nombre:
        queryset = queryset.filter(nombre__icontains=nombre.strip())
        
    # 2. Filtro por grupo específico
    if grupo_id:
        queryset = queryset.filter(grupo_id=grupo_id)
        
    # Si se filtró por semáforo, evaluamos dinámicamente el color
    if semaforo:
        color_filtro = semaforo.upper().strip()
        # Filtramos en memoria los que coincidan con el color del semáforo
        resultado = [alumno for alumno in queryset if alumno.semaforo == color_filtro]
    else:
        # Si no hay filtro de semáforo, pasamos el queryset directo
        resultado = list(queryset)
        
    return resultado

@api.get("/alerta-temprana")
def alumnos_en_riesgo(request):
    return Alumno.objects.filter(promedio_actual__lt=6.0)

@api.get("/estado/{alumno_id}")
def obtener_estatus_alumno(request, alumno_id: int):
    get_object_or_404(Alumno, id=alumno_id)
    return {"alumno": alumno.nombre, "semaforo": alumno.semaforo}

@api.get("/grupos/resumen")
def resumen_grupos(request):
    return {"status": "ok"}

@api.post("/tareas/reportar-falta")
def reportar_tarea_pendiente(request, payload: TareaIn):
    # 1. Validación de existencia con manejo de errores limpio
    alumno = get_object_or_404(Alumno, id=payload.alumno_id)
    materia = get_object_or_404(Materia, id=payload.materia_id)
    
    # Limpiamos el nombre de la tarea (quitamos espacios extras al inicio o final)
    nombre_tarea_limpio = payload.nombre_tarea.strip()
    
    if not nombre_tarea_limpio:
        raise HttpError(400, "El nombre de la tarea no puede estar vacío.")

    # 2. Protección contra registros duplicados el mismo día
    hoy = timezone.now().date()
    tarea_duplicada = TareaPendiente.objects.filter(
        alumno=alumno,
        materia=materia,
        nombre_tarea__iexact=nombre_tarea_limpio, # 'iexact' ignora mayúsculas/minúsculas
        fecha_registro__date=hoy
    ).exists()
    
    if tarea_duplicada:
        raise HttpError(
            400, 
            f"Atención: Ya se reportó la tarea '{nombre_tarea_limpio}' para el alumno {alumno.nombre} el día de hoy."
        )
    
    # 3. Si todo está bien, registramos la incidencia en la base de datos
    TareaPendiente.objects.create(
        alumno=alumno,
        materia=materia,
        nombre_tarea=nombre_tarea_limpio
    )
    
    # Modificamos el denominador quincenal del Alerta Temprana (SDD)
    alumno.total_tareas_encargadas += 1
    alumno.save()
    
    return {
        "success": True, 
        "message": f"Falta registrada con éxito para {alumno.nombre}.",
        "nuevo_semaforo": alumno.semaforo,
        "porcentaje_incumplimiento": f"{alumno.porcentaje_incumplimiento_tareas}%"
    }

# 1. Obtener las materias y grupos que imparte un maestro
@api.get("/maestros/{maestro_id}/resumen-grupos", response=List[ResumenSemaforoGrupo])
def obtener_resumen_maestro(request, maestro_id: int):
    # 1. Buscamos las materias de este maestro
    materias = Materia.objects.filter(maestro_id=maestro_id)
    
    resumen = []
    
    for materia in materias:
        # 2. En lugar de filtros cruzados complejos, vamos directo a los grupos:
        # Si tu escuela maneja grupos generales, los recorremos todos para armar el reporte
        grupos = Grupo.objects.all()
        
        for grupo in grupos:
            # Filtramos los alumnos que pertenecen a este grupo específico
            alumnos_grupo = Alumno.objects.filter(grupo=grupo)
            
            # Si el grupo está vacío en el sistema, lo saltamos
            if not alumnos_grupo.exists():
                continue
                
            # Contamos cuántos alumnos del grupo están en cada color del semáforo quincenal
            verdes = sum(1 for a in alumnos_grupo if a.semaforo == "VERDE")
            amarillos = sum(1 for a in alumnos_grupo if a.semaforo == "AMARILLO")
            rojos = sum(1 for a in alumnos_grupo if a.semaforo == "ROJO")
            
            resumen.append({
                "grupo_id": grupo.id,
                "grado": grupo.grado,
                "seccion": grupo.seccion,
                "materia_nombre": materia.nombre,
                "materia_id": materia.id,
                "total_alumnos": alumnos_grupo.count(),
                "verdes": verdes,
                "amarillos": amarillos,
                "rojos": rojos
            })
            
    return resumen

# --- ¡LOS DOS NUEVOS ENDPOINTS POR FIN EN EL LUGAR CORRECTO! ---

@api.get("/tutores/{tutor_id}/hijos", response=List[AlumnoOut])
def listar_hijos_tutor(request, tutor_id: int):
    tutor = get_object_or_404(Tutor, id=tutor_id)
    return tutor.hijos.select_related('grupo').all()

@api.get("/alumnos/{alumno_id}/tareas-pendientes", response=List[DetalleTareaOut])
def listar_tareas_pendientes_alumno(request, alumno_id: int):
    return TareaPendiente.objects.filter(alumno_id=alumno_id)

# Endpoint rápido para conocer los IDs de los profesores
@api.get("/maestros", response=List[MaestroOut])
def listar_maestros(request):
    from alumnos.models import Maestro
    maestros = Maestro.objects.select_related('user').all()
    
    resultado = []
    for m in maestros:
        # Armamos el nombre completo usando los datos del User de Django
        nombre = f"{m.user.first_name} {m.user.last_name}".strip()
        # Si por alguna razón no tienen nombre capturado, usamos el username
        if not nombre:
            nombre = m.user.username
            
        resultado.append({
            "id": m.id,
            "nombre_completo": f"Profe. {nombre}"
        })
        
    return resultado

# Endpoint de Alerta Temprana para el ATP / Dirección
@api.get("/atp/alumnos-alerta", response=List[AlumnoAlertaOut])
def obtener_alumnos_en_alerta(request, color: str = "ROJO"):
    # Aseguramos que el filtro sea en mayúsculas para que coincida con el modelo
    color_filtro = color.upper().strip()
    
    # Traemos todos los alumnos para evaluar sus semáforos dinámicos
    todos_alumnos = Alumno.objects.select_related('grupo').all()
    
    alumnos_en_alerta = []
    
    for alumno in todos_alumnos:
        # Evaluamos si el semáforo del alumno coincide con el color solicitado
        if alumno.semaforo == color_filtro:
            alumnos_en_alerta.append({
                "id": alumno.id,
                "nombre_completo": alumno.nombre, # Usamos el campo nombre de tu modelo
                "grado": alumno.grupo.grado,
                "seccion": alumno.grupo.seccion,
                "total_tareas_encargadas": alumno.total_tareas_encargadas,
                "porcentaje_incumplimiento": alumno.porcentaje_incumplimiento_tareas,
                "semaforo": alumno.semaforo
            })
            
    # Los ordenamos de mayor a menor porcentaje de incumplimiento para poner los más graves al principio
    alumnos_en_alerta = sorted(
        alumnos_en_alerta, 
        key=lambda x: x["porcentaje_incumplimiento"], 
        reverse=True
    )
    
    return alumnos_en_alerta


# GET /api/alumnos/{alumno_id}/historial
@api.get("/alumnos/{alumno_id}/historial", response=List[HistorialTareaOut])
def obtener_historial_alumno(request, alumno_id: int):
    # Validamos que el alumno exista usando el HttpError de Ninja
    from alumnos.models import Alumno
    alumno_existe = Alumno.objects.filter(id=alumno_id).exists()
    if not alumno_existe:
        raise HttpError(404, "No Alumno matches the given query.")
        
    # Importamos tu modelo exacto
    from alumnos.models import TareaPendiente 
    
    # Filtramos las tareas pendientes de este alumno y las ordenamos por fecha_registro (más recientes primero)
    registros = TareaPendiente.objects.filter(alumno_id=alumno_id).select_related('materia').order_by('-fecha_registro')
    
    historial = []
    for r in registros:
        historial.append({
            "materia_nombre": r.materia.nombre,
            # Formateamos la fecha_registro (DateTimeField) a un texto limpio AAAA-MM-DD
            "fecha": r.fecha_registro.strftime("%Y-%m-%d") if r.fecha_registro else "", 
            "entrego": False,  # Como está en esta tabla, sabemos que NO la entregó
            "observaciones": r.nombre_tarea  # Usamos el nombre de la tarea como la observación de qué debe
        })
        
    return historial



@api.post("/atp/cargar-alumnos-csv")
def cargar_alumnos_csv(request, file: UploadedFile = File(...)):
    from alumnos.models import Alumno, Grupo
    
    # Leemos el archivo subido en memoria
    csv_file = file.read().decode('utf-8')
    io_string = io.StringIO(csv_file)
    
    # El lector de CSV se salta la primera línea si tiene encabezados (Nombre, Grado, Seccion)
    reader = csv.reader(io_string, delimiter=',')
    header = next(reader, None) 
    
    alumnos_creados = 0
    errores = []
    
    for fila_num, fila in enumerate(reader, start=2):
        # Validamos que la fila tenga los datos mínimos (Nombre, Grado, Sección)
        if len(fila) < 3:
            errores.append(f"Fila {fila_num}: Faltan datos necesarios.")
            continue
            
        nombre_alumno = fila[0].strip()
        try:
            grado = int(fila[1].strip())
            seccion = fila[2].strip().upper()
        except ValueError:
            errores.append(f"Fila {fila_num}: El grado debe ser un número entero.")
            continue
            
        # 1. Buscamos o creamos el grupo para que no truene si el grupo es nuevo
        grupo, _ = Grupo.objects.get_or_create(grado=grado, seccion=seccion)
        
        # 2. Evitamos duplicar al alumno si ya existe en ese mismo grupo
        alumno_existe = Alumno.objects.filter(nombre=nombre_alumno, grupo=grupo).exists()
        
        if not alumno_existe:
            Alumno.objects.create(
                nombre=nombre_alumno,
                grupo=grupo
                # Nota: tus campos dinámicos (semaforo, total_tareas) se calculan 
                # por defecto en tu modelo, así que entran en VERDE automáticamente.
            )
            alumnos_creados += 1
        else:
            errores.append(f"Fila {fila_num}: El alumno '{nombre_alumno}' ya está registrado en {grado}°{seccion}.")

    return {
        "status": "Proceso terminado",
        "alumnos_importados_con_exito": alumnos_creados,
        "detalles_o_errores": errores
    }

@api.get("/atp/exportar-alertas-excel")
def exportar_alertas_excel(request, color: str = "ROJO"):
    from alumnos.models import Alumno
    
    color_filtro = color.upper().strip()
    todos_alumnos = Alumno.objects.select_related('grupo').all()
    
    # Crear libro de Excel en memoria
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte Alertas ATP"
    ws.views.sheetView[0].showGridLines = True # Mantener cuadrícula visible
    
    # Diseñar Estilos Visuales
    font_title = Font(name="Calibri", size=14, bold=True, color="1B365D")
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_body = Font(name="Calibri", size=11)
    font_bold = Font(name="Calibri", size=11, bold=True)
    
    fill_header = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
    fill_red = PatternFill(start_color="FF8A8A", end_color="FF8A8A", fill_type="solid")
    fill_yellow = PatternFill(start_color="FFF275", end_color="FFF275", fill_type="solid")
    
    thin_border = Border(
        left=Side(style='thin', color='D3D3D3'), right=Side(style='thin', color='D3D3D3'),
        top=Side(style='thin', color='D3D3D3'), bottom=Side(style='thin', color='D3D3D3')
    )
    
    # 1. Título del Reporte
    ws.merge_cells("A1:G1")
    ws["A1"] = f"ALUMNOS EN ALERTA TEMPRANA - SEMÁFORO {color_filtro}"
    ws["A1"].font = font_title
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 35
    
    # 2. Encabezados de la Tabla
    headers = ["ID Alumno", "Nombre Completo", "Grado", "Sección", "Tareas Encargadas", "Incumplimiento", "Estado Semáforo"]
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_idx, value=header)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    ws.row_dimensions[3].height = 25
    
    # 3. Inyectar los datos filtrados
    row_idx = 4
    for alumno in todos_alumnos:
        if alumno.semaforo == color_filtro:
            ws.cell(row=row_idx, column=1, value=alumno.id).alignment = Alignment(horizontal="center")
            ws.cell(row=row_idx, column=2, value=alumno.nombre).alignment = Alignment(horizontal="left")
            ws.cell(row=row_idx, column=3, value=alumno.grupo.grado).alignment = Alignment(horizontal="center")
            ws.cell(row=row_idx, column=4, value=alumno.grupo.seccion).alignment = Alignment(horizontal="center")
            ws.cell(row=row_idx, column=5, value=alumno.total_tareas_encargadas).alignment = Alignment(horizontal="center")
            
            # Porcentaje
            cell_pct = ws.cell(row=row_idx, column=6, value=alumno.porcentaje_incumplimiento_tareas / 100)
            cell_pct.number_format = '0%'
            cell_pct.alignment = Alignment(horizontal="right")
            
            # Semáforo con color dinámico en la celda
            cell_sem = ws.cell(row=row_idx, column=7, value=alumno.semaforo)
            cell_sem.alignment = Alignment(horizontal="center")
            cell_sem.font = font_bold
            if color_filtro == "ROJO":
                cell_sem.fill = fill_red
            elif color_filtro == "AMARILLO":
                cell_sem.fill = fill_yellow
                
            # Aplicar bordes a toda la fila
            for c in range(1, 8):
                ws.cell(row=row_idx, column=c).border = thin_border
                ws.cell(row=row_idx, column=c).font = font_body
                
            row_idx += 1
            
    # Ajustar el ancho automático de las columnas
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
        
    # Preparar respuesta de descarga HTTP para Django
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f"attachment; filename=Reporte_Alertas_{color_filtro}.xlsx"
    wb.save(response)
    return response

# GET /api/alumnos/{alumno_id}/reporte-tutor
@api.get("/alumnos/{alumno_id}/reporte-tutor", response=ReporteTutorOut)
def obtener_reporte_tutor(request, alumno_id: int):
    from alumnos.models import Alumno
    alumno = Alumno.objects.filter(id=alumno_id).select_related('grupo').first()
    if not alumno:
        raise HttpError(404, "Alumno no encontrado")
        
    # Personalizamos el emoji y la severidad según el semáforo actual
    if alumno.semaforo == "ROJO":
        emoji = "🚨 ALERTA CRÍTICA"
        accion = "Se requiere su presencia de manera urgente en el plantel para firmar una carta compromiso académico."
    elif alumno.semaforo == "AMARILLO":
        emoji = "⚠️ AVISO PREVENTIVO"
        accion = "Le solicitamos revisar diariamente los cuadernos de su hijo(a) y apoyar en la regularización de las tareas pendientes."
    else:
        emoji = "✅ RECONOCIMIENTO"
        accion = "¡Muchas felicidades! Sigan manteniendo ese excelente ritmo de trabajo."

    # Estructuramos el mensaje de texto automatizado
    mensaje = (
        f"Estimado padre de familia o tutor,\n\n"
        f"Se le informa sobre la situación académica actual de su hijo(a):\n"
        f"👤 Alumno: *{alumno.nombre}*\n"
        f"🏫 Grupo: *{alumno.grupo.grado}°{alumno.grupo.seccion}*\n\n"
        f"📊 Estado del Semáforo Quincenal: *{alumno.semaforo}* {emoji}\n"
        f"📉 Porcentaje de Tareas NO Entregadas: *{alumno.porcentaje_incumplimiento_tareas}%*\n"
        f"📝 Total de tareas adeudadas en el periodo: *{alumno.detalles_tareas.count()}* tareas.\n\n"
        f"👉 *Próxima acción:* {accion}\n\n"
        f"Agradecemos de antemano su valioso apoyo en la formación educativa de su hijo(a).\n"
        f"Atentamente,\n"
        f"Dirección y Cuerpo Docente."
    )
    
    return {
        "alumno_id": alumno.id,
        "nombre_completo": alumno.nombre,
        "mensaje_whatsapp": mensaje
    }