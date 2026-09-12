import os
from datetime import date

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from alumnos.models import (
    Alumno,
    CatalogoMateria,
    CicloEscolar,
    DetalleInasistenciaAlumno,
    DetalleTareaAlumno,
    Grupo,
    Maestro,
    Materia,
    PeriodoReporte,
    RegistroInasistenciasPeriodo,
    RegistroTareasPeriodo,
    Tutor,
)


def env_true(name):
    return os.getenv(name, '').lower() in {'1', 'true', 'yes'}


class Command(BaseCommand):
    help = 'Crea un escenario demostrativo ficticio sin borrar información existente.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Permite ejecutarlo localmente aunque DJANGO_LOAD_DEMO_DATA no esté activo.',
        )

    def handle(self, *args, **options):
        if not options['force'] and not env_true('DJANGO_LOAD_DEMO_DATA'):
            self.stdout.write('Datos demo desactivados; no se realizó ningún cambio.')
            return

        passwords = {
            'atp.demo': os.getenv('DEMO_ADMIN_PASSWORD'),
            'docente.demo': os.getenv('DEMO_TEACHER_PASSWORD'),
            'familia.demo': os.getenv('DEMO_TUTOR_PASSWORD'),
        }
        missing = [name for name, value in passwords.items() if not value]
        if missing:
            raise CommandError(
                'Faltan contraseñas de demostración para: ' + ', '.join(missing)
            )

        with transaction.atomic():
            self._create_demo(passwords)

        self.stdout.write(self.style.SUCCESS(
            'Escenario ficticio listo. Usuarios: atp.demo, docente.demo y familia.demo.'
        ))

    def _user(self, username, password=None, **defaults):
        user, _ = User.objects.update_or_create(username=username, defaults=defaults)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def _create_demo(self, passwords):
        admin = self._user(
            'atp.demo', passwords['atp.demo'], first_name='ATP', last_name='Demostración',
            is_staff=True, is_superuser=True, is_active=True,
        )
        docente_user = self._user(
            'docente.demo', passwords['docente.demo'], first_name='Elena',
            last_name='Demostración', is_staff=False, is_superuser=False, is_active=True,
        )
        auxiliar_user = self._user(
            'docente.pendiente.demo', first_name='Miguel', last_name='Ejemplo',
            is_staff=False, is_superuser=False, is_active=True,
        )
        tutor_user = self._user(
            'familia.demo', passwords['familia.demo'], first_name='Laura',
            last_name='Ejemplo', is_staff=False, is_superuser=False, is_active=True,
        )

        docente, _ = Maestro.objects.update_or_create(
            user=docente_user,
            defaults={'nombre': 'Elena', 'apellido_paterno': 'Demostración', 'activo': True},
        )
        auxiliar, _ = Maestro.objects.update_or_create(
            user=auxiliar_user,
            defaults={'nombre': 'Miguel', 'apellido_paterno': 'Ejemplo', 'activo': True},
        )

        grupo_1a, _ = Grupo.objects.update_or_create(
            grado=1, seccion='A DEMO', defaults={'maestro': docente_user}
        )
        grupo_1b, _ = Grupo.objects.update_or_create(
            grado=1, seccion='B DEMO', defaults={'maestro': docente_user}
        )

        alumnos_1a = []
        for nombre, apellido in [
            ('Sofía', 'Alerta Roja'),
            ('Diego', 'Atención Amarilla'),
            ('Valeria', 'Al Día'),
            ('Mateo', 'Ejemplo Uno'),
            ('Camila', 'Ejemplo Dos'),
            ('Sebastián', 'Ejemplo Tres'),
        ]:
            alumno, _ = Alumno.objects.update_or_create(
                nombre=nombre, apellido=apellido, grupo=grupo_1a
            )
            alumnos_1a.append(alumno)

        for nombre, apellido in [('Renata', 'Ejemplo'), ('Emiliano', 'Ejemplo')]:
            Alumno.objects.update_or_create(nombre=nombre, apellido=apellido, grupo=grupo_1b)

        ciclo, _ = CicloEscolar.objects.update_or_create(
            nombre='2026-2027 DEMO',
            defaults={'activo': True, 'cerrado': False},
        )
        CicloEscolar.objects.exclude(pk=ciclo.pk).filter(nombre__contains='DEMO').update(activo=False)
        periodo, _ = PeriodoReporte.objects.update_or_create(
            ciclo=ciclo,
            nombre='Reporte de demostración',
            defaults={
                'fecha_inicio': date(2026, 9, 1),
                'fecha_fin': date(2026, 9, 15),
                'fecha_limite': date(2026, 9, 18),
                'activo': True,
                'cerrado': False,
            },
        )

        catalogos = {}
        for nombre in ['Matemáticas 1 DEMO', 'Ciencias 1 DEMO', 'Tecnología 1 DEMO']:
            catalogos[nombre], _ = CatalogoMateria.objects.update_or_create(
                nombre=nombre, defaults={'activa': True}
            )

        matematicas, _ = Materia.objects.update_or_create(
            catalogo=catalogos['Matemáticas 1 DEMO'], ciclo=ciclo, grupo=grupo_1a,
            defaults={'nombre': 'Matemáticas 1 DEMO', 'maestro': docente},
        )
        Materia.objects.update_or_create(
            catalogo=catalogos['Tecnología 1 DEMO'], ciclo=ciclo, grupo=grupo_1a,
            defaults={'nombre': 'Tecnología 1 DEMO', 'maestro': docente},
        )
        Materia.objects.update_or_create(
            catalogo=catalogos['Tecnología 1 DEMO'], ciclo=ciclo, grupo=grupo_1b,
            defaults={'nombre': 'Tecnología 1 DEMO', 'maestro': docente},
        )
        Materia.objects.update_or_create(
            catalogo=catalogos['Ciencias 1 DEMO'], ciclo=ciclo, grupo=grupo_1a,
            defaults={'nombre': 'Ciencias 1 DEMO', 'maestro': auxiliar},
        )

        registro_tareas, _ = RegistroTareasPeriodo.objects.update_or_create(
            periodo_reporte=periodo, materia=matematicas, grupo=grupo_1a,
            defaults={
                'fecha_inicio': periodo.fecha_inicio,
                'fecha_fin': periodo.fecha_fin,
                'total_tareas_encargadas': 10,
            },
        )
        registro_faltas, _ = RegistroInasistenciasPeriodo.objects.update_or_create(
            periodo_reporte=periodo, materia=matematicas, grupo=grupo_1a,
            defaults={'fecha_inicio': periodo.fecha_inicio, 'fecha_fin': periodo.fecha_fin},
        )
        tareas = [5, 2, 0, 1, 0, 3]
        faltas = [5, 3, 0, 1, 0, 2]
        for alumno, tareas_no_entregadas, total_faltas in zip(alumnos_1a, tareas, faltas):
            DetalleTareaAlumno.objects.update_or_create(
                registro_periodo=registro_tareas,
                alumno=alumno,
                defaults={'tareas_no_entregadas': tareas_no_entregadas},
            )
            DetalleInasistenciaAlumno.objects.update_or_create(
                registro_periodo=registro_faltas,
                alumno=alumno,
                defaults={'total_faltas': total_faltas},
            )

        tutor, _ = Tutor.objects.update_or_create(
            user=tutor_user,
            defaults={
                'nombre': 'Laura', 'apellido': 'Ejemplo',
                'correo': 'familia.demo@example.invalid', 'telefono': '0000000000',
            },
        )
        tutor.hijos.set([alumnos_1a[0], alumnos_1a[2]])

        # Mantiene la variable viva y deja explícito que la cuenta ATP fue creada.
        assert admin.pk
