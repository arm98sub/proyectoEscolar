from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from .models import Alumno, Grupo, Materia, TareaPendiente, TareaEncargada
from .forms import TareaEncargadaForm

@login_required(login_url='login')
def dashboard_maestro(request):
    # Obtener filtros de la URL (si existen)
    grupo_id = request.GET.get('grupo')
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
        'cant_verdes': verdes,
        'cant_amarillos': amarillos,
        'cant_rojos': rojos,
        'total_alumnos': total,
        'grupo_seleccionado': int(grupo_id) if grupo_id else None,
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