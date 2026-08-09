from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from .models import Alumno, Grupo, Materia, TareaPendiente, TareaEncargada
from .forms import TareaEncargadaForm
from django.contrib import messages  # <--- AGREGAR ESTA LÍNEA

@login_required(login_url='login')
def dashboard_maestro(request):
    # Obtener filtros de la URL (si existen)
    grupo_id = request.GET.get('grupo')
    if grupo_id == "":  # Si seleccionó "Todos los grupos", lo tratamos como None
        grupo_id = None
    nombre_buscar = request.GET.get('nombre', '').strip()
    
    # Base del QuerySet
    queryset = Alumno.objects.select_related('grupo').all()
    
    # Aplicar filtros dinámicos
    if nombre_buscar:
        queryset = queryset.filter(nombre__icontains=nombre_buscar)
    if grupo_id:
        queryset = queryset.filter(grupo_id=grupo_id)
        
    # Agrupamos y calculamos semáforos para las tarjetas de métricas
    alumnos_lista = list(queryset)
    verdes = sum(1 for a in alumnos_lista if a.semaforo == "VERDE")
    amarillos = sum(1 for a in alumnos_lista if a.semaforo == "AMARILLO")
    rojos = sum(1 for a in alumnos_lista if a.semaforo == "ROJO")
    total = len(alumnos_lista)
    
    # Datos para el selector de grupos en la interfaz
    grupos = Grupo.objects.all()
    
    context = {
        'alumnos': alumnos_lista,
        'grupos': grupos,
        'grupo_selected': grupo_id,   # <-- OBLIGATORIO para que el template sepa cuál grupo se filtró
        'cant_verdes': verdes,
        'cant_amarillos': amarillos,
        'cant_rojos': rojos,
        'total_alumnos': total,
        'nombre_buscar': nombre_buscar,
    }
    
    return render(request, 'alumnos/dashboard.html', context)



# 1. Vista para procesar el Inicio de Sesión
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_maestro')
        
    error = None
    if request.method == 'POST':
        usuario_txt = request.POST.get('username')
        clave_txt = request.POST.get('password')
        
        user = authenticate(request, username=usuario_txt, password=clave_txt)
        if user is not None:
            login(request, user)
            return redirect('dashboard_maestro')
        else:
            error = "Usuario o contraseña incorrectos."
            
    return render(request, 'alumnos/login.html', {'error': error})

# 2. Vista del Dashboard Protegida
@login_required(login_url='login')  # <-- Si no ha iniciado sesión, lo manda al login
def dashboard_maestro(request):
    grupo_id = request.GET.get('grupo')
    nombre_buscar = request.GET.get('nombre', '').strip()
    
    # CANDADO DE PRIVACIDAD: Traemos SOLO los grupos que tiene asignados el maestro actual
    grupos_del_maestro = Grupo.objects.filter(maestro=request.user)
    
    # Traemos solo los alumnos que pertenecen a los grupos de este maestro
    queryset = Alumno.objects.filter(grupo__in=grupos_del_maestro).select_related('grupo')
    
    # Aplicar filtros secundarios en la pantalla
    if nombre_buscar:
        queryset = queryset.filter(nombre__icontains=nombre_buscar)
    if grupo_id:
        queryset = queryset.filter(grupo_id=grupo_id)
        
    alumnos_lista = list(queryset)
    verdes = sum(1 for a in alumnos_lista if a.semaforo == "VERDE")
    amarillos = sum(1 for a in alumnos_lista if a.semaforo == "AMARILLO")
    rojos = sum(1 for a in alumnos_lista if a.semaforo == "ROJO")
    
    context = {
        'alumnos': alumnos_lista,
        'grupos': grupos_del_maestro,  # El selector solo mostrará sus grupos
        'cant_verdes': verdes,
        'cant_amarillos': amarillos,
        'cant_rojos': rojos,
        'total_alumnos': len(alumnos_lista),
        'grupo_seleccionado': int(grupo_id) if grupo_id else None,
        'nombre_buscar': nombre_buscar,
        'maestro_nombre': request.user.first_name or request.user.username
    }
    
    return render(request, 'alumnos/dashboard.html', context)

# 3. Vista rápida para salir
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required(login_url='login')
def detalle_alumno(request, alumno_id):
    # Si es superusuario/admin (alan), puede ver cualquier alumno. 
    # Si es un maestro normal (alan_profe), solo ve los de sus grupos asignados.
    if request.user.is_superuser:
        alumno = get_object_or_404(Alumno, id=alumno_id)
    else:
        alumno = get_object_or_404(Alumno, id=alumno_id, grupo__maestro=request.user)
    
    mis_tareas = TareaPendiente.objects.filter(alumno_id=alumno.id).order_by('-fecha_registro')
    
    materia_id = request.GET.get('materia')
    materia_seleccionada = None
    
    if materia_id:
        mis_tareas = mis_tareas.filter(materia_id=materia_id)
        materia_seleccionada = int(materia_id)
    
    materias = Materia.objects.all()
    
    context = {
        'alumno': alumno,
        'tareas': mis_tareas,  # Se pasa a la plantilla como 'tareas'
        'materias': materias,
        'materia_seleccionada': materia_seleccionada,
    }
    return render(request, 'alumnos/detalle.html', context)

@login_required(login_url='login')
def marcar_tarea_entregada(request, alumno_id, tarea_id):
    alumno = get_object_or_404(Alumno, id=alumno_id, group__maestro=request.user)
    
    # Buscamos la tarea usando tu relación real
    tarea = get_object_or_404(alumno.detalles_tareas, id=tarea_id)
    
    # Como esta tabla es de "Tareas Pendientes", al entregarse se ELIMINA del expediente
    tarea.delete()
    
    # Volvemos a guardar al alumno para que sus métodos @property recalculen el semáforo
    alumno.save()
    
    return redirect('detalle_alumno', alumno_id=alumno_id)


# ... tus otras funciones (detalle_alumno, marcar_tarea_entregada, etc.) ...

@login_required(login_url='login')
def agregar_tarea_pendiente(request, alumno_id):
    alumno = get_object_or_404(Alumno, id=alumno_id, grupo__maestro=request.user)
    
    if request.method == 'POST':
        materia_id = request.POST.get('materia')
        nombre_tarea = request.POST.get('nombre_tarea')
        
        if materia_id and nombre_tarea:
            materia = get_object_or_404(Materia, id=materia_id)
            TareaPendiente.objects.create(
                alumno=alumno,
                materia=materia,
                nombre_tarea=nombre_tarea
            )
            
    return redirect('detalle_alumno', alumno_id=alumno.id)


@login_required(login_url='login')
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

@login_required(login_url='login')
def lista_tareas_encargadas(request):
    """Muestra la lista de tareas encargadas registradas."""
    if request.user.is_superuser:
        tareas = TareaEncargada.objects.all().select_related('grupo', 'materia').order_by('-id')
    else:
        tareas = TareaEncargada.objects.filter(grupo__maestro=request.user).select_related('grupo', 'materia').order_by('-id')
        
    return render(request, 'alumnos/lista_tareas.html', {'tareas': tareas})


@login_required(login_url='login')
def editar_tarea_encargada(request, tarea_id):
    """Permite modificar el título o materia de una tarea ya registrada."""
    if request.user.is_superuser:
        tarea = get_object_or_404(TareaEncargada, pk=tarea_id)
    else:
        tarea = get_object_or_404(TareaEncargada, pk=tarea_id, grupo__maestro=request.user)

    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        materia_id = request.POST.get('materia')
        
        if titulo and materia_id:
            tarea.titulo = titulo
            tarea.materia_id = materia_id
            tarea.save()
            return redirect('lista_tareas_encargadas')

    materias = Materia.objects.all()
    return render(request, 'alumnos/editar_tarea.html', {
        'tarea': tarea,
        'materias': materias
    })


@login_required(login_url='login')
def eliminar_tarea_encargada(request, tarea_id):
    if request.user.is_superuser:
        tarea = get_object_or_404(TareaEncargada, pk=tarea_id)
    else:
        tarea = get_object_or_404(TareaEncargada, pk=tarea_id, grupo__maestro=request.user)

    tarea.delete()
    return redirect('lista_tareas_encargadas')


from .models import InasistenciaPeriodo

@login_required(login_url='login')
def registrar_faltas_periodo(request, grupo_id):
    if request.user.is_superuser:
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
    if request.method == 'POST':
        # Buscamos 'matricula' y si no viene, 'curp'
        identificador = request.POST.get('matricula') or request.POST.get('curp') or ''
        identificador = identificador.strip()
        
        print(f"\n--- INTENTO DE LOGIN TUTOR ---")
        print(f"VALOR RECIBIDO: '{identificador}'")
        
        try:
            alumno_id = int(identificador)
            alumno = Alumno.objects.get(pk=alumno_id)
            print(f"¡ALUMNO ENCONTRADO!: {alumno.nombre} {alumno.apellido}")
            
            request.session['alumno_tutor_id'] = alumno.id
            return redirect('tablero_tutor')
            
        except ValueError:
            messages.error(request, f'El valor "{identificador}" no es un número válido.')
        except Alumno.DoesNotExist:
            messages.error(request, f'No se encontró ningún alumno con el ID #{identificador}.')

    return render(request, 'alumnos/login_tutor.html')

def tablero_tutor(request):
    """
    Muestra el tablero visual en tarjetas con el semáforo por materia para el tutor.
    """
    alumno_id = request.session.get('alumno_tutor_id')
    
    if not alumno_id:
        return redirect('login_tutor')

    alumno = get_object_or_404(Alumno, pk=alumno_id)
    
    tablero_materias = []
    
    # Obtenemos los grupos o la materia asociada al alumno
    grupos = []
    if hasattr(alumno, 'grupo') and alumno.grupo:
        grupos.append(alumno.grupo)
    elif hasattr(alumno, 'grupos'):
        grupos = list(alumno.grupos.all())

    for grupo in grupos:
        semaforo_info = alumno.obtener_semaforo_materia(grupo)
        
        # Nombre de la materia o del grupo
        nombre_materia = f"{grupo.grado}°{grupo.seccion}"
        if hasattr(grupo, 'materia') and grupo.materia:
            nombre_materia = grupo.materia.nombre
        elif hasattr(grupo, 'nombre_materia'):
            nombre_materia = grupo.nombre_materia

        tablero_materias.append({
            'grupo': grupo,
            'materia': nombre_materia,
            'semaforo': semaforo_info,
        })

    context = {
        'alumno': alumno,
        'tablero_materias': tablero_materias,
    }
    return render(request, 'alumnos/tablero_tutor.html', context)


def tablero_tutor(request):
    """
    Muestra el tablero visual en tarjetas con el semáforo por materia para el tutor.
    """
    alumno_id = request.session.get('alumno_tutor_id')
    
    if not alumno_id:
        return redirect('login_tutor')

    alumno = get_object_or_404(Alumno, pk=alumno_id)
    
    tablero_materias = []
    
    # Obtenemos los grupos o la materia asociada al alumno
    grupos = []
    if hasattr(alumno, 'grupo') and alumno.grupo:
        grupos.append(alumno.grupo)
    elif hasattr(alumno, 'grupos'):
        grupos = list(alumno.grupos.all())

    for grupo in grupos:
        semaforo_info = alumno.obtener_semaforo_materia(grupo)
        
        # Nombre de la materia o del grupo
        nombre_materia = f"{grupo.grado}°{grupo.seccion}"
        if hasattr(grupo, 'materia') and grupo.materia:
            nombre_materia = grupo.materia.nombre
        elif hasattr(grupo, 'nombre_materia'):
            nombre_materia = grupo.nombre_materia

        tablero_materias.append({
            'grupo': grupo,
            'materia': nombre_materia,
            'semaforo': semaforo_info,
        })

    context = {
        'alumno': alumno,
        'tablero_materias': tablero_materias,
    }
    return render(request, 'alumnos/tablero_tutor.html', context)


def logout_tutor(request):
    """ Cierra la sesión del portal de tutores. """
    request.session.pop('alumno_tutor_id', None)
    return redirect('login_tutor')