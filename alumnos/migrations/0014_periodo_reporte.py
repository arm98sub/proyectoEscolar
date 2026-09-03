from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('alumnos', '0013_ciclos_escolares')]
    operations = [
        migrations.CreateModel(name='PeriodoReporte', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('nombre', models.CharField(max_length=100)), ('fecha_inicio', models.DateField()), ('fecha_fin', models.DateField()), ('fecha_limite', models.DateField()), ('activo', models.BooleanField(default=False)), ('cerrado', models.BooleanField(default=False)),
            ('ciclo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='periodos_reportes', to='alumnos.cicloescolar')),
        ], options={'ordering': ['-fecha_inicio']}),
        migrations.AddField(model_name='registroinasistenciasperiodo', name='periodo_reporte', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reportes_asistencias', to='alumnos.periodoreporte')),
        migrations.AddField(model_name='registrotareasperiodo', name='periodo_reporte', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reportes_actividades', to='alumnos.periodoreporte')),
    ]
