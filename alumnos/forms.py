from django import forms
from .models import TareaEncargada, Materia, Grupo

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
            if user.is_superuser:
                self.fields['grupos'].queryset = Grupo.objects.all()
            else:
                self.fields['grupos'].queryset = Grupo.objects.filter(maestro=user)