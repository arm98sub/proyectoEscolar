from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('alumnos', '0014_periodo_reporte')]

    operations = [
        migrations.AddField(
            model_name='tutor',
            name='debe_cambiar_password',
            field=models.BooleanField(default=False),
        ),
    ]
