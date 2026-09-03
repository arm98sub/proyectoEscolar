from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseNotAllowed
from django.http import Http404
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from .models import Maestro, Materia, Grupo, Alumno, CatalogoMateria, CicloEscolar, PeriodoReporte, RegistroTareasPeriodo, DetalleTareaAlumno, RegistroInasistenciasPeriodo, DetalleInasistenciaAlumno
from .forms import (
    TareaEncargadaForm, CrearMaestroForm, CrearMateriaForm, EditarMaestroForm,
    EditarMateriaForm, CatalogoMateriaForm, CicloEscolarForm, PeriodoReporteForm, RegistroTareasCentroForm, RegistroInasistenciasCentroForm,
)
from django.contrib import messages  # <--- AGREGAR ESTA LÍNEA
from .models import Grupo, Materia, Alumno, RegistroTareasPeriodo, DetalleTareaAlumno
from .authz import admin_required, docente_o_admin_required, es_administrador, maestro_required


@admin_required
def admin_dashboard(request):
    ciclos = CicloEscolar.objects.all()
    ciclo = get_object_or_404(ciclos, pk=request.GET['ciclo']) if request.GET.get('ciclo') else ciclos.filter(activo=True).first()
    base = Materia.objects.filter(ciclo=ciclo) if ciclo else Materia.objects.none()
    nombres = base.order_by('nombre').values_list('nombre', flat=True).distinct()
    agrupadas = []
    vistos = set()
    for nombre in sorted(nombres, key=str.casefold):
        clave = nombre.casefold()
        if clave in vistos:
            continue
        vistos.add(clave)
        instancias = base.filter(nombre__iexact=nombre)
        agrupadas.append({
            'nombre': nombre,
            'identificador': slugify(nombre),
            'total_grupos': instancias.count(),
            'total_alumnos': Alumno.objects.filter(grupo__materias__in=instancias).distinct().count(),
        })
    return render(request, 'alumnos/admin_dashboard.html', {'materias_agrupadas': agrupadas, 'ciclo': ciclo, 'ciclos': ciclos})


def _materias_por_identificador(identificador, ciclo):
    base = Materia.objects.filter(ciclo=ciclo)
    nombres = base.values_list('nombre', flat=True).distinct()
    coincidencias = [nombre for nombre in nombres if slugify(nombre) == identificador]
    if len(coincidencias) != 1:
        raise Http404("Materia no encontrada")
    return coincidencias[0], base.filter(nombre=coincidencias[0]).select_related(
        'grupo', 'maestro'
    ).order_by('grupo__grado', 'grupo__seccion')


@admin_required
def admin_materia_grupos(request, identificador):
    ciclos = CicloEscolar.objects.all()
    ciclo = get_object_or_404(ciclos, pk=request.GET['ciclo']) if request.GET.get('ciclo') else ciclos.filter(activo=True).first()
    if not ciclo:
        raise Http404("No hay ciclo escolar")
    nombre, materias = _materias_por_identificador(identificador, ciclo)
    return render(request, 'alumnos/admin_materia_grupos.html', {
        'nombre_materia': nombre,
        'materias': materias, 'ciclo': ciclo,
    })

@admin_required
def registrar_maestro(request):
    """
    Vista exclusiva para administradores: registrar y listar docentes.
    """
    if request.method == 'POST':
        form = CrearMaestroForm(request.POST)
        if form.is_valid():
            # 1. Extraer datos limpios
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            nombre = form.cleaned_data['nombre']
            apellido_paterno = form.cleaned_data['apellido_paterno']
            apellido_materno = form.cleaned_data.get('apellido_materno', '')

            # 2. Crear usuario ENCRIPTANDO la contraseña obligatoriamente con create_user
            with transaction.atomic():
                nuevo_usuario = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=nombre,
                    last_name=apellido_paterno,
                )
                Maestro.objects.create(
                    user=nuevo_usuario,
                    nombre=nombre,
                    apellido_paterno=apellido_paterno,
                    apellido_materno=apellido_materno
                )

            messages.success(request, f"Maestro '{username}' registrado correctamente con acceso al sistema.")
            return redirect('registrar_maestro')
    else:
        form = CrearMaestroForm()

    maestros = Maestro.objects.select_related('user').all().order_by('apellido_paterno', 'nombre')
    return render(request, 'alumnos/registrar_maestro.html', {'form': form, 'maestros': maestros})


@admin_required
def editar_maestro(request, maestro_id):
    maestro = get_object_or_404(Maestro.objects.select_related('user'), pk=maestro_id)
    form = EditarMaestroForm(request.POST or None, instance=maestro)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, "Los datos del maestro se actualizaron correctamente.")
        return redirect('registrar_maestro')
    return render(request, 'alumnos/admin_form.html', {
        'form': form, 'titulo': 'Editar maestro', 'volver': 'registrar_maestro'
    })


@require_POST
@admin_required
def cambiar_estado_maestro(request, maestro_id):
    maestro = get_object_or_404(Maestro.objects.select_related('user'), pk=maestro_id)
    maestro.activo = not maestro.activo
    maestro.user.is_active = maestro.activo
    with transaction.atomic():
        maestro.save(update_fields=['activo'])
        maestro.user.save(update_fields=['is_active'])
    estado = 'activado' if maestro.activo else 'desactivado'
    messages.success(request, f"El maestro '{maestro}' fue {estado}.")
    return redirect('registrar_maestro')


@admin_required
def eliminar_maestro(request, maestro_id):
    maestro = get_object_or_404(Maestro.objects.select_related('user'), pk=maestro_id)
    if request.method == 'POST':
        if maestro.materias.exists():
            messages.error(
                request,
                "No se puede eliminar un maestro con materias asignadas. Desactívalo para conservar el historial.",
            )
            return redirect('registrar_maestro')
        nombre = str(maestro)
        with transaction.atomic():
            maestro.user.delete()
        messages.success(request, f"El maestro '{nombre}' fue eliminado.")
        return redirect('registrar_maestro')
    return render(request, 'alumnos/admin_confirmar_eliminar.html', {
        'objeto': maestro,
        'tipo': 'maestro',
        'volver': 'registrar_maestro',
        'advertencia': 'Solo se puede eliminar definitivamente si no tiene materias asignadas. Si tiene historial, utiliza Desactivar.',
    })


@admin_required
def registrar_materia(request):
    """
    Vista exclusiva para administradores/ATP: dar de alta materias en masa para múltiples grupos.
    """
    ciclo = CicloEscolar.objects.filter(activo=True, cerrado=False).first()
    if request.method == 'POST':
        form = CrearMateriaForm(request.POST, ciclo=ciclo)
        if form.is_valid():
            if not ciclo:
                messages.error(request, "Debes crear y activar un ciclo escolar antes de asignar materias.")
                return redirect('gestionar_ciclos')
            catalogo = form.cleaned_data['catalogo']
            nombre = catalogo.nombre
            maestro = form.cleaned_data['maestro']
            grupos_seleccionados = form.cleaned_data['grupos']

            creadas = 0
            for grupo in grupos_seleccionados:
                obj, created = Materia.objects.get_or_create(
                    catalogo=catalogo,
                    grupo=grupo,
                    ciclo=ciclo,
                    defaults={'nombre': nombre, 'maestro': maestro}
                )
                if not created and (obj.maestro != maestro or obj.nombre != nombre):
                    obj.maestro = maestro
                    obj.nombre = nombre
                    obj.save(update_fields=['maestro', 'nombre'])
                creadas += 1

            docente_nom = f"{maestro.nombre} {maestro.apellido_paterno}" if maestro else "Sin asignar"
            messages.success(request, f"Materia '{nombre}' guardada y asignada a {creadas} grupo(s) para el docente {docente_nom}.")
            return redirect('registrar_materia')
    else:
        form = CrearMateriaForm(ciclo=ciclo)

    # Ordenamos por grado y seccion del grupo
    materias_qs = Materia.objects.select_related('grupo', 'maestro').filter(ciclo=ciclo).order_by('grupo__grado', 'grupo__seccion', 'nombre')
    materias = list(materias_qs)

    context = {
        'form': form,
        'materias': materias, 'ciclo': ciclo,
    }
    return render(request, 'alumnos/registrar_materia.html', context)


@admin_required
def registrar_catalogo_materia(request):
    form = CatalogoMateriaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        materia = form.save()
        messages.success(request, f"'{materia.nombre}' se agregó al catálogo.")
        return redirect('registrar_materia')
    return render(request, 'alumnos/admin_form.html', {
        'form': form, 'titulo': 'Agregar materia al catálogo', 'volver': 'registrar_materia'
    })


@admin_required
def gestionar_ciclos(request):
    form = CicloEscolarForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            ciclo = form.save(commit=False)
            ciclo.activo = form.cleaned_data['activar']
            if ciclo.activo:
                CicloEscolar.objects.update(activo=False)
            ciclo.save()
            origen = form.cleaned_data.get('copiar_asignaciones')
            if origen:
                Materia.objects.bulk_create([
                    Materia(nombre=m.nombre, catalogo=m.catalogo, maestro=m.maestro, grupo=m.grupo, ciclo=ciclo)
                    for m in origen.asignaciones.select_related('catalogo', 'maestro', 'grupo')
                ])
        messages.success(request, f"Ciclo {ciclo.nombre} creado correctamente.")
        return redirect('gestionar_ciclos')
    return render(request, 'alumnos/gestionar_ciclos.html', {'form': form, 'ciclos': CicloEscolar.objects.all()})


@require_POST
@admin_required
def activar_ciclo(request, ciclo_id):
    ciclo = get_object_or_404(CicloEscolar, pk=ciclo_id, cerrado=False)
    with transaction.atomic():
        CicloEscolar.objects.update(activo=False)
        ciclo.activo = True
        ciclo.save(update_fields=['activo'])
    messages.success(request, f"El ciclo {ciclo.nombre} ahora está activo.")
    return redirect('gestionar_ciclos')


@require_POST
@admin_required
def cerrar_ciclo(request, ciclo_id):
    ciclo = get_object_or_404(CicloEscolar, pk=ciclo_id)
    ciclo.activo = False
    ciclo.cerrado = True
    ciclo.save(update_fields=['activo', 'cerrado'])
    messages.success(request, f"El ciclo {ciclo.nombre} fue cerrado y permanece disponible para consulta.")
    return redirect('gestionar_ciclos')


@admin_required
def gestionar_periodos_reportes(request):
    ciclo = CicloEscolar.objects.filter(activo=True, cerrado=False).first()
    form = PeriodoReporteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid() and ciclo:
        periodo = form.save(commit=False); periodo.ciclo = ciclo; periodo.activo = True
        PeriodoReporte.objects.filter(ciclo=ciclo).update(activo=False)
        periodo.save(); messages.success(request, 'Periodo de reporte activado.')
        return redirect('gestionar_periodos_reportes')
    return render(request, 'alumnos/gestionar_periodos_reportes.html', {'form': form, 'ciclo': ciclo, 'periodos': PeriodoReporte.objects.filter(ciclo=ciclo) if ciclo else []})


@admin_required
def tablero_reportes_atp(request):
    periodo = PeriodoReporte.objects.filter(ciclo__activo=True, activo=True, cerrado=False).first()
    filas = []
    if periodo:
        for maestro in Maestro.objects.filter(activo=True).prefetch_related('materias'):
            asignaciones = maestro.materias.filter(ciclo=periodo.ciclo)
            actividades = RegistroTareasPeriodo.objects.filter(materia__in=asignaciones, periodo_reporte=periodo)
            asistencias = RegistroInasistenciasPeriodo.objects.filter(materia__in=asignaciones, periodo_reporte=periodo)
            pendientes_actividades = [m for m in asignaciones if not actividades.filter(materia=m).exists()]
            pendientes_asistencias = [m for m in asignaciones if not asistencias.filter(materia=m).exists()]
            def estado(registros, pendientes):
                if pendientes or not asignaciones.exists():
                    return 'incompleto'
                return 'tarde' if any(r.fecha_creacion.date() > periodo.fecha_limite for r in registros) else 'completado'
            filas.append({'maestro': maestro, 'pendientes_actividades': pendientes_actividades, 'pendientes_asistencias': pendientes_asistencias, 'estado_actividades': estado(actividades, pendientes_actividades), 'estado_asistencias': estado(asistencias, pendientes_asistencias)})
    return render(request, 'alumnos/tablero_reportes_atp.html', {'periodo': periodo, 'filas': filas})


@admin_required
def editar_materia(request, materia_id):
    materia = get_object_or_404(Materia, pk=materia_id)
    form = EditarMateriaForm(request.POST or None, instance=materia)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "La instancia de materia se actualizó correctamente.")
        return redirect('registrar_materia')
    return render(request, 'alumnos/admin_form.html', {
        'form': form, 'titulo': 'Editar materia y grupo', 'volver': 'registrar_materia'
    })


@admin_required
def eliminar_materia(request, materia_id):
    materia = get_object_or_404(Materia.objects.select_related('grupo'), pk=materia_id)
    if request.method == 'POST':
        nombre = str(materia)
        materia.delete()
        messages.success(request, f"La instancia '{nombre}' fue eliminada.")
        return redirect('registrar_materia')
    return render(request, 'alumnos/admin_confirmar_eliminar.html', {
        'objeto': materia,
        'tipo': 'materia',
        'volver': 'registrar_materia',
        'advertencia': 'Se eliminarán sus registros dependientes. Las otras instancias de la misma materia no cambiarán.',
    })

@docente_o_admin_required
def centro_mando_materia(request, materia_id):
    """
    Centro de mando único con pestañas:
    Pestaña 1: Semáforos / Alumnos
    Pestaña 2: Tareas por Periodo (Registro y Consulta)
    Pestaña 3: Inasistencias por Periodo (Registro y Consulta)
    """
    materias = Materia.objects.select_related('grupo', 'maestro__user')
    if not es_administrador(request.user):
        materias = materias.filter(maestro__user=request.user)
    materia = get_object_or_404(materias, pk=materia_id)
    grupo = materia.grupo
    alumnos = grupo.alumnos.all().order_by('apellido', 'nombre')
    periodo_reporte = PeriodoReporte.objects.filter(ciclo=materia.ciclo, activo=True, cerrado=False).first()

    # Procesamiento de Formularios POST
    if request.method == 'POST':
        if materia.ciclo and materia.ciclo.cerrado:
            messages.error(request, "Este ciclo está cerrado y solo puede consultarse.")
            return redirect('centro_mando_materia', materia_id=materia.id)
        tipo_form = request.POST.get('tipo_formulario')

        # --- A) REGISTRO DE TAREAS POR PERIODO ---
        if tipo_form == 'guardar_tareas':
            if not periodo_reporte:
                messages.error(request, 'No hay un periodo de reporte activo para este ciclo.')
                return redirect('centro_mando_materia', materia_id=materia.id)
            datos = request.POST.copy()
            datos['fecha_inicio'] = periodo_reporte.fecha_inicio.isoformat()
            datos['fecha_fin'] = periodo_reporte.fecha_fin.isoformat()
            for alumno in alumnos:
                datos[f'alumno_{alumno.pk}'] = request.POST.get(f'tareas_alumno_{alumno.pk}', '')
            form = RegistroTareasCentroForm(datos, alumnos=alumnos)
            if not form.is_valid():
                for errores in form.errors.values():
                    for error in errores:
                        messages.error(request, error)
                return redirect('centro_mando_materia', materia_id=materia.id)

            with transaction.atomic():
                registro_t = RegistroTareasPeriodo.objects.create(
                    materia=materia,
                    grupo=grupo,
                    periodo_reporte=periodo_reporte,
                    fecha_inicio=form.cleaned_data['fecha_inicio'],
                    fecha_fin=form.cleaned_data['fecha_fin'],
                    total_tareas_encargadas=form.cleaned_data['total_tareas_encargadas']
                )

                for alumno in alumnos:
                    DetalleTareaAlumno.objects.create(
                        registro_periodo=registro_t,
                        alumno=alumno,
                        tareas_no_entregadas=form.cleaned_data[f'alumno_{alumno.pk}']
                    )

            messages.success(request, f"Periodo de tareas '{registro_t.nombre_periodo}' guardado correctamente.")
            return redirect('centro_mando_materia', materia_id=materia.id)

        # --- B) REGISTRO DE INASISTENCIAS POR PERIODO ---
        elif tipo_form == 'guardar_inasistencias':
            if not periodo_reporte:
                messages.error(request, 'No hay un periodo de reporte activo para este ciclo.')
                return redirect('centro_mando_materia', materia_id=materia.id)
            datos = request.POST.copy()
            datos['fecha_inicio'] = periodo_reporte.fecha_inicio.isoformat()
            datos['fecha_fin'] = periodo_reporte.fecha_fin.isoformat()
            for alumno in alumnos:
                datos[f'alumno_{alumno.pk}'] = request.POST.get(f'faltas_alumno_{alumno.pk}', '')
            form = RegistroInasistenciasCentroForm(datos, alumnos=alumnos)
            if not form.is_valid():
                for errores in form.errors.values():
                    for error in errores:
                        messages.error(request, error)
                return redirect('centro_mando_materia', materia_id=materia.id)

            with transaction.atomic():
                registro_f = RegistroInasistenciasPeriodo.objects.create(
                    materia=materia,
                    grupo=grupo,
                    periodo_reporte=periodo_reporte,
                    fecha_inicio=form.cleaned_data['fecha_inicio'],
                    fecha_fin=form.cleaned_data['fecha_fin']
                )

                for alumno in alumnos:
                    DetalleInasistenciaAlumno.objects.create(
                        registro_periodo=registro_f,
                        alumno=alumno,
                        total_faltas=form.cleaned_data[f'alumno_{alumno.pk}']
                    )

            messages.success(request, f"Periodo de inasistencias '{registro_f.nombre_periodo}' guardado correctamente.")
            return redirect('centro_mando_materia', materia_id=materia.id)

    # Cargar datos para el renderizado
    alumnos_resumen = []
    for alum in alumnos:
        semaforo = alum.obtener_semaforo_materia(materia)
        alumnos_resumen.append({
            'alumno': alum,
            'semaforo': semaforo
        })

    periodos_tareas = RegistroTareasPeriodo.objects.filter(materia=materia, grupo=grupo)
    periodos_inasistencias = RegistroInasistenciasPeriodo.objects.filter(materia=materia, grupo=grupo)

    context = {
        'materia': materia,
        'grupo': grupo,
        'alumnos': alumnos,
        'alumnos_resumen': alumnos_resumen,
        'periodos_tareas': periodos_tareas,
        'periodos_inasistencias': periodos_inasistencias,
        'periodo_reporte': periodo_reporte,
    }
    return render(request, 'alumnos/centro_mando_materia.html', context)

# 1. Vista para procesar el Inicio de Sesión
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_maestro')
        
    error = None
    if request.method == 'POST':
        usuario_txt = request.POST.get('username')
        clave_txt = request.POST.get('password')
        
        user = authenticate(request, username=usuario_txt, password=clave_txt)
        if user is not None and (es_administrador(user) or hasattr(user, 'maestro')):
            login(request, user)
            return redirect('dashboard_maestro')
        else:
            error = "Usuario o contraseña incorrectos."
            
    return render(request, 'alumnos/login.html', {'error': error})

# 2. Vista del Dashboard Protegida
@docente_o_admin_required
def dashboard_maestro(request):
    materias = Materia.objects.select_related('grupo', 'maestro__user').filter(ciclo__activo=True)
    if not es_administrador(request.user):
        materias = materias.filter(maestro__user=request.user)

    materias_data = []
    for materia in materias:
        alumnos = list(materia.grupo.alumnos.all())
        colores = [alumno.obtener_semaforo_materia(materia)['color'] for alumno in alumnos]
        materias_data.append({
            'materia': materia,
            'total_alumnos': len(alumnos),
            'rojos': colores.count('rojo'),
            'amarillos': colores.count('amarillo'),
            'verdes': colores.count('verde'),
        })

    return render(
        request,
        'alumnos/dashboard.html',
        {'materias_data': materias_data},
    )

# 3. Vista rápida para salir
@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')


@docente_o_admin_required
def detalle_alumno(request, alumno_id):
    # Si es superusuario/admin (alan), puede ver cualquier alumno. 
    # Si es un maestro normal (alan_profe), solo ve los de sus grupos asignados.
    if es_administrador(request.user):
        alumno = get_object_or_404(Alumno, id=alumno_id)
    else:
        alumno = get_object_or_404(Alumno, id=alumno_id, grupo__maestro=request.user)
    
    mis_tareas = TareaPendiente.objects.filter(alumno_id=alumno.id).order_by('-fecha_registro')
    
    materia_id = request.GET.get('materia')
    materia_seleccionada = None
    
    if materia_id:
        mis_tareas = mis_tareas.filter(materia_id=materia_id)
        materia_seleccionada = int(materia_id)
    
    materias = Materia.objects.filter(grupo=alumno.grupo, ciclo__activo=True)
    if not es_administrador(request.user):
        materias = materias.filter(maestro__user=request.user)
    
    context = {
        'alumno': alumno,
        'tareas': mis_tareas,  # Se pasa a la plantilla como 'tareas'
        'materias': materias,
        'materia_seleccionada': materia_seleccionada,
    }
    return render(request, 'alumnos/detalle.html', context)

@require_POST
@docente_o_admin_required
def marcar_tarea_entregada(request, alumno_id, tarea_id):
    alumnos = Alumno.objects.all()
    if not es_administrador(request.user):
        alumnos = alumnos.filter(grupo__maestro=request.user)
    alumno = get_object_or_404(alumnos, id=alumno_id)
    
    # Buscamos la tarea usando tu relación real
    tarea = get_object_or_404(alumno.detalles_tareas, id=tarea_id)
    
    # Como esta tabla es de "Tareas Pendientes", al entregarse se ELIMINA del expediente
    tarea.delete()
    
    # Volvemos a guardar al alumno para que sus métodos @property recalculen el semáforo
    alumno.save()
    
    return redirect('detalle_alumno', alumno_id=alumno_id)


# ... tus otras funciones (detalle_alumno, marcar_tarea_entregada, etc.) ...

@require_POST
@docente_o_admin_required
def agregar_tarea_pendiente(request, alumno_id):
    alumnos = Alumno.objects.all()
    if not es_administrador(request.user):
        alumnos = alumnos.filter(grupo__maestro=request.user)
    alumno = get_object_or_404(alumnos, id=alumno_id)
    
    if request.method == 'POST':
        materia_id = request.POST.get('materia')
        nombre_tarea = request.POST.get('nombre_tarea')
        
        if materia_id and nombre_tarea:
            materias = Materia.objects.filter(grupo=alumno.grupo)
            if not es_administrador(request.user):
                materias = materias.filter(maestro__user=request.user)
            materia = get_object_or_404(materias, id=materia_id)
            TareaPendiente.objects.create(
                alumno=alumno,
                materia=materia,
                nombre_tarea=nombre_tarea
            )
            
    return redirect('detalle_alumno', alumno_id=alumno.id)


@docente_o_admin_required
def registrar_tarea_encargada(request):
    if request.method == 'POST':
        form = TareaEncargadaForm(request.POST, user=request.user)
        if form.is_valid():
            grupos_seleccionados = form.cleaned_data['grupos']
            materia = form.cleaned_data['materia']
            titulo = form.cleaned_data['titulo']
            
            # Crea un registro individual para cada grupo seleccionado
            for grupo in grupos_seleccionados:
                TareaEncargada.objects.create(
                    grupo=grupo,
                    materia=materia,
                    titulo=titulo
                )
                
            return redirect('dashboard')
    else:
        form = TareaEncargadaForm(user=request.user)

    return render(request, 'alumnos/registrar_tarea.html', {'form': form})

# --- GESTIÓN DE TAREAS ENCARGADAS ---

@docente_o_admin_required
def lista_tareas_encargadas(request):
    """Muestra la lista de tareas encargadas registradas."""
    if es_administrador(request.user):
        tareas = TareaEncargada.objects.all().select_related('grupo', 'materia').order_by('-id')
    else:
        tareas = TareaEncargada.objects.filter(grupo__maestro=request.user).select_related('grupo', 'materia').order_by('-id')
        
    return render(request, 'alumnos/lista_tareas.html', {'tareas': tareas})


@docente_o_admin_required
def editar_tarea_encargada(request, tarea_id):
    """Permite modificar el título o materia de una tarea ya registrada."""
    if es_administrador(request.user):
        tarea = get_object_or_404(TareaEncargada, pk=tarea_id)
    else:
        tarea = get_object_or_404(TareaEncargada, pk=tarea_id, grupo__maestro=request.user)

    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        materia_id = request.POST.get('materia')
        
        if titulo and materia_id:
            tarea.titulo = titulo
            materias = Materia.objects.filter(grupo=tarea.grupo)
            if not es_administrador(request.user):
                materias = materias.filter(maestro__user=request.user)
            tarea.materia = get_object_or_404(materias, pk=materia_id)
            tarea.save()
            return redirect('lista_tareas_encargadas')

    materias = Materia.objects.filter(grupo=tarea.grupo)
    if not es_administrador(request.user):
        materias = materias.filter(maestro__user=request.user)
    return render(request, 'alumnos/editar_tarea.html', {
        'tarea': tarea,
        'materias': materias
    })


@docente_o_admin_required
def eliminar_tarea_encargada(request, tarea_id):
    if es_administrador(request.user):
        tarea = get_object_or_404(TareaEncargada, pk=tarea_id)
    else:
        tarea = get_object_or_404(TareaEncargada, pk=tarea_id, grupo__maestro=request.user)

    if request.method == 'POST':
        tarea.delete()
        return redirect('lista_tareas_encargadas')
    return render(request, 'alumnos/confirmar_eliminar_tarea.html', {'tarea': tarea})


from .models import InasistenciaPeriodo

@docente_o_admin_required
def registrar_faltas_periodo(request, grupo_id):
    if es_administrador(request.user):
        grupo = get_object_or_404(Grupo, pk=grupo_id)
    else:
        grupo = get_object_or_404(Grupo, pk=grupo_id, maestro=request.user)

    alumnos = grupo.alumnos.all().order_by('apellido', 'nombre')

    if request.method == 'POST':
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')

        if fecha_inicio and fecha_fin:
            for alumno in alumnos:
                # Lee el número de faltas ingresado para cada alumno
                faltas_str = request.POST.get(f'faltas_{alumno.id}', '0')
                total_faltas = int(faltas_str) if faltas_str.isdigit() else 0

                if total_faltas > 0:
                    InasistenciaPeriodo.objects.create(
                        grupo=grupo,
                        alumno=alumno,
                        fecha_inicio=fecha_inicio,
                        fecha_fin=fecha_fin,
                        total_faltas=total_faltas
                    )

            return redirect('dashboard')

    return render(request, 'alumnos/registrar_faltas_periodo.html', {
        'grupo': grupo,
        'alumnos': alumnos,
    })
    
    
# En alumnos/models.py dentro del modelo Alumno (o en un servicio/helper)

def obtener_semaforo_materia(self, grupo):
    """
    Calcula el semáforo para un alumno en una materia/grupo específico
    evaluando el porcentaje de entregas de tareas y las faltas acumuladas.
    """
    # 1. Obtener total de tareas del grupo y cuántas ha cumplido/entregado el alumno
    # (Adaptar según la relación exacta de tus modelos de Tarea/DetalleTarea)
    tareas_grupo = grupo.tareas.count()
    
    if tareas_grupo > 0:
        # Contamos las tareas registradas/cumplidas por el alumno en este grupo
        tareas_entregadas = self.detalles_tareas.filter(
            tarea__grupo=grupo, 
            entregada=True
        ).count()
        porcentaje_cumplimiento = (tareas_entregadas / tareas_grupo) * 100
    else:
        porcentaje_cumplimiento = 100.0  # Si no hay tareas asignadas aún, no hay riesgo

    # 2. Obtener total de faltas en el periodo para esta materia/grupo
    # Sumamos el campo 'total_faltas' de los registros del periodo
    total_faltas = self.inasistencias.filter(grupo=grupo).aggregate(
        total=models.Sum('total_faltas')
    )['total'] or 0

    # 3. Aplicar las reglas del semáforo combinando ambas variables
    if porcentaje_cumplimiento < 70 or total_faltas >= 5:
        return {
            'color': 'rojo',
            'codigo_hex': '#EF4444',
            'bg_class': 'bg-red-500',
            'text_class': 'text-red-700',
            'bg_light': 'bg-red-50',
            'border_class': 'border-red-200',
            'etiqueta': 'Riesgo Alto',
            'porcentaje_tareas': round(porcentaje_cumplimiento, 1),
            'faltas': total_faltas
        }
    elif (70 <= porcentaje_cumplimiento < 85) or (3 <= total_faltas <= 4):
        return {
            'color': 'amarillo',
            'codigo_hex': '#F59E0B',
            'bg_class': 'bg-amber-500',
            'text_class': 'text-amber-700',
            'bg_light': 'bg-amber-50',
            'border_class': 'border-amber-200',
            'etiqueta': 'Atención',
            'porcentaje_tareas': round(porcentaje_cumplimiento, 1),
            'faltas': total_faltas
        }
    else:
        return {
            'color': 'verde',
            'codigo_hex': '#10B981',
            'bg_class': 'bg-emerald-500',
            'text_class': 'text-emerald-700',
            'bg_light': 'bg-emerald-50',
            'border_class': 'border-emerald-200',
            'etiqueta': 'Al Día',
            'porcentaje_tareas': round(porcentaje_cumplimiento, 1),
            'faltas': total_faltas
        }
        
        
def obtener_tablero_alumno(alumno):
    tablero = []
    # Recorremos todos los grupos/materias en los que está inscrito el alumno
    for grupo in alumno.grupos.all():
        semaforo_data = alumno.obtener_semaforo_materia(grupo)
        
        tablero.append({
            'materia_nombre': grupo.materia.nombre if hasattr(grupo, 'materia') else f"{grupo.grado}°{grupo.seccion}",
            'maestro': grupo.maestro.get_full_name() if grupo.maestro else 'Docente asignado',
            'semaforo': semaforo_data,
        })
    return tablero

def login_tutor(request):
    if request.user.is_authenticated and hasattr(request.user, 'tutor'):
        return redirect('tablero_tutor')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None and hasattr(user, 'tutor'):
            login(request, user)
            return redirect('tablero_tutor')

        messages.error(request, 'Usuario o contraseña de tutor incorrectos.')

    return render(request, 'alumnos/login_tutor.html')



def tablero_tutor(request):
    if not request.user.is_authenticated or not hasattr(request.user, 'tutor'):
        return redirect('login_tutor')

    alumno_id = request.GET.get('alumno')
    hijos = request.user.tutor.hijos.select_related('grupo').all()
    alumno = get_object_or_404(hijos, pk=alumno_id) if alumno_id else hijos.first()
    if alumno is None:
        messages.info(request, 'Este tutor todavía no tiene alumnos asociados.')
        return render(request, 'alumnos/tablero_tutor.html', {'hijos': hijos})
    tablero_materias = []

    if alumno.grupo:
        # 1. Buscar materias directamente vinculadas al grupo del alumno
        materias = list(Materia.objects.filter(grupo=alumno.grupo, ciclo__activo=True))
        
        # 2. Si no encuentra por ID de grupo, buscar por grado y sección (por si hay grupos duplicados)
        if not materias:
            materias = list(Materia.objects.filter(
                grupo__grado=alumno.grupo.grado, 
                grupo__seccion=alumno.grupo.seccion,
                ciclo__activo=True,
            ))

        # 3. Si aún no encuentra, buscar las materias de las tareas que deba el alumno
        if not materias:
            materias_ids = alumno.detalles_tareas.values_list('materia_id', flat=True).distinct()
            materias = list(Materia.objects.filter(id__in=materias_ids, ciclo__activo=True))

        # Construir información de las tarjetas
        for materia in materias:
            semaforo_info = alumno.obtener_semaforo_materia(materia)

            # Extraer el porcentaje si viene dentro de semaforo_info o asignarlo directamente
            porcentaje = semaforo_info.get('porcentaje_tareas', 100.0)
            
            tablero_materias.append({
                'materia_nombre': materia.nombre,
                'semaforo': semaforo_info,
                'porcentaje_cumplimiento': porcentaje,
                'maestro_nombre': str(materia.maestro),
                'grupo_label': str(materia.grupo),
            })

    total_materias = len(tablero_materias)
    promedio_cumplimiento = round(
        sum(item['porcentaje_cumplimiento'] for item in tablero_materias) / total_materias,
        1,
    ) if total_materias else 0
    materias_atencion = sum(item['semaforo']['color'] != 'verde' for item in tablero_materias)

    context = {
        'alumno': alumno,
        'tablero_materias': tablero_materias,
        'hijos': hijos,
        'total_materias': total_materias,
        'promedio_cumplimiento': promedio_cumplimiento,
        'materias_atencion': materias_atencion,
    }
    return render(request, 'alumnos/tablero_tutor.html', context)

@require_POST
def logout_tutor(request):
    """
    Limpia la sesión del tutor y lo redirige a la pantalla de inicio de sesión.
    """
    logout(request)
    messages.info(request, 'Has cerrado sesión correctamente.')
    return redirect('login_tutor')

@docente_o_admin_required
def registrar_tareas_periodo(request, grupo_id, materia_id):
    materias = Materia.objects.select_related('grupo', 'maestro__user').filter(
        pk=materia_id,
        grupo_id=grupo_id,
    )
    if not es_administrador(request.user):
        materias = materias.filter(maestro__user=request.user)
    materia = get_object_or_404(materias)
    grupo = materia.grupo
    alumnos = grupo.alumnos.all().order_by('apellido', 'nombre')

    if request.method == 'POST':
        nombre_periodo = request.POST.get('nombre_periodo')
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        total_encargadas = int(request.POST.get('total_tareas_encargadas', 0))

        with transaction.atomic():
            registro = RegistroTareasPeriodo.objects.create(
                materia=materia,
                grupo=grupo,
                nombre_periodo=nombre_periodo,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                total_tareas_encargadas=total_encargadas
            )

            for alumno in alumnos:
                no_entregadas = int(request.POST.get(f'alumno_{alumno.id}', 0))
                DetalleTareaAlumno.objects.create(
                    registro_periodo=registro,
                    alumno=alumno,
                    tareas_no_entregadas=no_entregadas
                )

        messages.success(request, f"Registro de tareas para '{nombre_periodo}' guardado correctamente.")
        return redirect('registrar_tareas_periodo', grupo_id=grupo.id, materia_id=materia.id)

    # Historial de periodos previamente registrados en esta materia y grupo
    periodos_anteriores = RegistroTareasPeriodo.objects.filter(grupo=grupo, materia=materia).order_by('-fecha_creacion')

    context = {
        'grupo': grupo,
        'materia': materia,
        'alumnos': alumnos,
        'periodos_anteriores': periodos_anteriores,
    }
    return render(request, 'alumnos/registrar_tareas_periodo.html', context)
