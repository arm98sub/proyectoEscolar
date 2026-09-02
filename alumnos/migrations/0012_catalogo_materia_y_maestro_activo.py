from django.db import migrations, models
import django.db.models.deletion


def crear_catalogo(apps, schema_editor):
    Materia = apps.get_model('alumnos', 'Materia')
    CatalogoMateria = apps.get_model('alumnos', 'CatalogoMateria')
    for materia in Materia.objects.all().iterator():
        catalogo, _ = CatalogoMateria.objects.get_or_create(nombre=materia.nombre.strip())
        materia.catalogo_id = catalogo.pk
        materia.save(update_fields=['catalogo'])


class Migration(migrations.Migration):
    dependencies = [('alumnos', '0011_tutor_user')]

    operations = [
        migrations.AddField(
            model_name='maestro',
            name='activo',
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name='CatalogoMateria',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, unique=True)),
                ('activa', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Materia del catálogo',
                'verbose_name_plural': 'Catálogo de materias',
                'ordering': ['nombre'],
            },
        ),
        migrations.AddField(
            model_name='materia',
            name='catalogo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='asignaciones', to='alumnos.catalogomateria'),
        ),
        migrations.RunPython(crear_catalogo, migrations.RunPython.noop),
    ]
