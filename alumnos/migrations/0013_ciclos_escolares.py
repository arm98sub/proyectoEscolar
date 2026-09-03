from django.db import migrations, models
import django.db.models.deletion


def asignar_ciclo_inicial(apps, schema_editor):
    CicloEscolar = apps.get_model('alumnos', 'CicloEscolar')
    Materia = apps.get_model('alumnos', 'Materia')
    ciclo, _ = CicloEscolar.objects.get_or_create(
        nombre='2026-2027',
        defaults={'activo': True, 'cerrado': False},
    )
    Materia.objects.filter(ciclo__isnull=True).update(ciclo=ciclo)


class Migration(migrations.Migration):
    dependencies = [('alumnos', '0012_catalogo_materia_y_maestro_activo')]

    operations = [
        migrations.CreateModel(
            name='CicloEscolar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=20, unique=True)),
                ('activo', models.BooleanField(default=False)),
                ('cerrado', models.BooleanField(default=False)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
            ],
            options={'verbose_name': 'Ciclo escolar', 'verbose_name_plural': 'Ciclos escolares', 'ordering': ['-nombre']},
        ),
        migrations.AddField(
            model_name='materia',
            name='ciclo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='asignaciones', to='alumnos.cicloescolar'),
        ),
        migrations.RunPython(asignar_ciclo_inicial, migrations.RunPython.noop),
    ]
