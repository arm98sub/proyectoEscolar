from django import forms
from .models import TareaEncargada, Materia, Grupo, Maestro, CatalogoMateria, CicloEscolar, PeriodoReporte
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password


INPUT_CLASS = 'w-full px-3 py-2 border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'


class TareaEncargadaForm(forms.Form):
    grupos = forms.ModelMultipleChoiceField(
        queryset=Grupo.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 h-4 w-4'
        }),
        label="Selecciona los Grupos"
    )
    materia = forms.ModelChoiceField(
        queryset=Materia.objects.all(),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm'
        })
    )
    titulo = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm',
            'placeholder': 'Ej. Ejercicios de Ecuaciones de Primer Grado'
        }),
        label="Título o Descripción Corta"
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            if user.is_superuser or user.is_staff:
                self.fields['grupos'].queryset = Grupo.objects.all()
                self.fields['materia'].queryset = Materia.objects.filter(ciclo__activo=True)
            else:
                self.fields['grupos'].queryset = Grupo.objects.filter(maestro=user)
                self.fields['materia'].queryset = Materia.objects.filter(maestro__user=user, ciclo__activo=True)

    def clean(self):
        cleaned_data = super().clean()
        materia = cleaned_data.get('materia')
        grupos = cleaned_data.get('grupos')
        if materia and grupos and any(grupo.pk != materia.grupo_id for grupo in grupos):
            raise forms.ValidationError(
                "La materia debe pertenecer a cada grupo seleccionado."
            )
        return cleaned_data
                
                
                
class CrearMaestroForm(forms.Form):
    username = forms.CharField(
        label="Nombre de Usuario",
        widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'})
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={'class': 'w-full px-3 py-2 border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'})
    )
    nombre = forms.CharField(
        label="Nombre(s)",
        widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'})
    )
    apellido_paterno = forms.CharField(
        label="Apellido Paterno",
        widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'})
    )
    apellido_materno = forms.CharField(
        label="Apellido Materno",
        required=False,
        widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'})
    )

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Este nombre de usuario ya está registrado.")
        return username

    def clean_password(self):
        password = self.cleaned_data.get('password')
        validate_password(password)
        return password
    
class CrearMateriaForm(forms.ModelForm):
    catalogo = forms.ModelChoiceField(
        queryset=CatalogoMateria.objects.none(),
        label="Materia",
        widget=forms.Select(attrs={'class': INPUT_CLASS}),
    )
    confirmar_reasignaciones = forms.BooleanField(
        required=False,
        label="Confirmo reemplazar al docente en grupos que ya tengan esta materia",
    )
    # Usamos grado y seccion para ordenar correctamente
    grupos = forms.ModelMultipleChoiceField(
        queryset=Grupo.objects.all().order_by('grado', 'seccion'),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Grupos"
    )

    class Meta:
        model = Materia
        fields = ['catalogo', 'maestro', 'grupos']
        labels = {
            'maestro': 'Docente Asignado',
        }
        widgets = {
            'maestro': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.ciclo = kwargs.pop('ciclo', None)
        super().__init__(*args, **kwargs)
        self.fields['catalogo'].queryset = CatalogoMateria.objects.filter(activa=True).order_by('nombre')
        self.fields['maestro'].queryset = Maestro.objects.filter(activo=True).order_by('nombre', 'apellido_paterno')
        self.fields['maestro'].empty_label = "-- Seleccionar Docente --"

    def clean(self):
        cleaned_data = super().clean()
        catalogo = cleaned_data.get('catalogo')
        maestro = cleaned_data.get('maestro')
        grupos = cleaned_data.get('grupos')
        if catalogo and maestro and grupos:
            conflictos = Materia.objects.filter(
                grupo__in=grupos,
                catalogo=catalogo,
                ciclo=self.ciclo,
            ).exclude(maestro=maestro)
            if conflictos.exists() and not cleaned_data.get('confirmar_reasignaciones'):
                self.add_error(
                    'confirmar_reasignaciones',
                    "Hay grupos con otro docente. Confirma la reasignación para continuar.",
                )
        return cleaned_data


class CatalogoMateriaForm(forms.ModelForm):
    class Meta:
        model = CatalogoMateria
        fields = ['nombre']
        widgets = {'nombre': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej. Matemáticas 1'})}

    def clean_nombre(self):
        nombre = self.cleaned_data['nombre'].strip()
        if CatalogoMateria.objects.filter(nombre__iexact=nombre).exists():
            raise forms.ValidationError("Esta materia ya existe en el catálogo.")
        return nombre


class CicloEscolarForm(forms.ModelForm):
    copiar_asignaciones = forms.ModelChoiceField(
        queryset=CicloEscolar.objects.none(),
        required=False,
        label="Copiar asignaciones de",
        help_text="Opcional: crea las mismas materias, grupos y docentes del ciclo seleccionado.",
    )
    activar = forms.BooleanField(required=False, initial=True, label="Activar este ciclo al crearlo")

    class Meta:
        model = CicloEscolar
        fields = ['nombre']
        widgets = {'nombre': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej. 2027-2028'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['copiar_asignaciones'].queryset = CicloEscolar.objects.order_by('-nombre')
        self.fields['copiar_asignaciones'].widget.attrs['class'] = INPUT_CLASS

    def clean_nombre(self):
        nombre = self.cleaned_data['nombre'].strip()
        if not __import__('re').fullmatch(r'\d{4}-\d{4}', nombre):
            raise forms.ValidationError("Usa el formato AAAA-AAAA, por ejemplo 2026-2027.")
        inicio, fin = map(int, nombre.split('-'))
        if fin != inicio + 1:
            raise forms.ValidationError("El segundo año debe ser consecutivo al primero.")
        return nombre


class PeriodoReporteForm(forms.ModelForm):
    class Meta:
        model = PeriodoReporte
        fields = ['nombre', 'fecha_inicio', 'fecha_fin', 'fecha_limite']
        widgets = {field: forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}) for field in ['fecha_inicio', 'fecha_fin', 'fecha_limite']}
        widgets['nombre'] = forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej. Reporte septiembre'})

    def clean(self):
        data = super().clean()
        if data.get('fecha_inicio') and data.get('fecha_fin') and data['fecha_inicio'] > data['fecha_fin']:
            self.add_error('fecha_fin', 'La fecha final no puede ser anterior al inicio.')
        return data


class EditarMaestroForm(forms.ModelForm):
    username = forms.CharField(label="Nombre de Usuario", widget=forms.TextInput(attrs={'class': INPUT_CLASS}))
    password = forms.CharField(
        label="Nueva contraseña",
        required=False,
        help_text="Déjala vacía para conservar la contraseña actual.",
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASS}),
    )

    class Meta:
        model = Maestro
        fields = ['nombre', 'apellido_paterno', 'apellido_materno']
        widgets = {field: forms.TextInput(attrs={'class': INPUT_CLASS}) for field in fields}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].initial = self.instance.user.username

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.exclude(pk=self.instance.user_id).filter(username=username).exists():
            raise forms.ValidationError("Este nombre de usuario ya está registrado.")
        return username

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            validate_password(password, self.instance.user)
        return password

    def save(self, commit=True):
        maestro = super().save(commit=False)
        user = maestro.user
        user.username = self.cleaned_data['username']
        user.first_name = maestro.nombre
        user.last_name = maestro.apellido_paterno
        if self.cleaned_data.get('password'):
            user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            maestro.save()
        return maestro


class EditarMateriaForm(forms.ModelForm):
    catalogo = forms.ModelChoiceField(queryset=CatalogoMateria.objects.none(), label="Materia")
    confirmar_reasignacion = forms.BooleanField(
        required=False,
        label="Confirmo el cambio de docente responsable",
    )

    class Meta:
        model = Materia
        fields = ['catalogo', 'maestro', 'grupo']
        widgets = {
            'maestro': forms.Select(attrs={'class': INPUT_CLASS}),
            'grupo': forms.Select(attrs={'class': INPUT_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['catalogo'].queryset = CatalogoMateria.objects.filter(activa=True).order_by('nombre')
        self.fields['catalogo'].widget.attrs['class'] = INPUT_CLASS
        self.fields['maestro'].queryset = Maestro.objects.filter(activo=True).order_by('nombre', 'apellido_paterno')
        self.fields['grupo'].queryset = Grupo.objects.order_by('grado', 'seccion')

    def clean(self):
        cleaned_data = super().clean()
        catalogo = cleaned_data.get('catalogo')
        grupo = cleaned_data.get('grupo')
        maestro = cleaned_data.get('maestro')
        if catalogo and grupo and Materia.objects.exclude(pk=self.instance.pk).filter(
            catalogo=catalogo, grupo=grupo
        ).exists():
            raise forms.ValidationError("Ya existe una materia con este nombre para el grupo seleccionado.")
        if maestro and self.instance.pk and maestro.pk != self.instance.maestro_id and not cleaned_data.get('confirmar_reasignacion'):
            self.add_error('confirmar_reasignacion', "Debes confirmar la reasignación del docente.")
        return cleaned_data

    def save(self, commit=True):
        materia = super().save(commit=False)
        materia.nombre = self.cleaned_data['catalogo'].nombre
        if commit:
            materia.save()
        return materia


class PeriodoBaseForm(forms.Form):
    fecha_inicio = forms.DateField()
    fecha_fin = forms.DateField()

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get('fecha_inicio')
        fin = cleaned_data.get('fecha_fin')
        if inicio and fin and inicio > fin:
            raise forms.ValidationError("La fecha de inicio no puede ser posterior a la fecha final.")
        return cleaned_data


class RegistroTareasCentroForm(PeriodoBaseForm):
    total_tareas_encargadas = forms.IntegerField(min_value=1)

    def __init__(self, *args, alumnos=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.alumnos = list(alumnos)
        for alumno in self.alumnos:
            self.fields[f'alumno_{alumno.pk}'] = forms.IntegerField(min_value=0, initial=0)

    def clean(self):
        cleaned_data = super().clean()
        total = cleaned_data.get('total_tareas_encargadas')
        if total is not None:
            for alumno in self.alumnos:
                cantidad = cleaned_data.get(f'alumno_{alumno.pk}')
                if cantidad is not None and cantidad > total:
                    self.add_error(
                        f'alumno_{alumno.pk}',
                        "Las tareas no entregadas no pueden superar el total encargado.",
                    )
        return cleaned_data


class RegistroInasistenciasCentroForm(PeriodoBaseForm):
    def __init__(self, *args, alumnos=(), **kwargs):
        super().__init__(*args, **kwargs)
        for alumno in alumnos:
            self.fields[f'alumno_{alumno.pk}'] = forms.IntegerField(min_value=0, initial=0)
