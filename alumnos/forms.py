from django import forms
from .models import TareaEncargada, Materia, Grupo, Maestro
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password


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
                self.fields['materia'].queryset = Materia.objects.all()
            else:
                self.fields['grupos'].queryset = Grupo.objects.filter(maestro=user)
                self.fields['materia'].queryset = Materia.objects.filter(maestro__user=user)

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
    # Usamos grado y seccion para ordenar correctamente
    grupos = forms.ModelMultipleChoiceField(
        queryset=Grupo.objects.all().order_by('grado', 'seccion'),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Grupos"
    )

    class Meta:
        model = Materia
        fields = ['nombre', 'maestro', 'grupos']
        labels = {
            'nombre': 'Nombre de la Materia',
            'maestro': 'Docente Asignado',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500',
                'placeholder': 'Ej. Tecnologías, Matemáticas, Educación Física...'
            }),
            'maestro': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['maestro'].queryset = Maestro.objects.all().order_by('nombre', 'apellido_paterno')
        self.fields['maestro'].empty_label = "-- Seleccionar Docente --"
