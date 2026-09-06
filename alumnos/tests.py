from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import date, datetime

from .models import (
    Alumno, Grupo, Maestro, Materia, Tutor, CatalogoMateria, CicloEscolar, PeriodoReporte, TareaPendiente, RegistroTareasPeriodo,
    RegistroInasistenciasPeriodo,
)


class ControlAccesoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('admin', password='test-pass')
        cls.usuario_sin_rol = User.objects.create_user('sin-rol', password='test-pass')

        cls.user_1 = User.objects.create_user('maestro-1', password='test-pass')
        cls.user_2 = User.objects.create_user('maestro-2', password='test-pass')
        cls.maestro_1 = Maestro.objects.create(
            user=cls.user_1,
            nombre='Ada',
            apellido_paterno='Lovelace',
        )
        cls.maestro_2 = Maestro.objects.create(
            user=cls.user_2,
            nombre='Alan',
            apellido_paterno='Turing',
        )
        cls.grupo_1 = Grupo.objects.create(grado=1, seccion='A', maestro=cls.user_1)
        cls.grupo_2 = Grupo.objects.create(grado=2, seccion='B', maestro=cls.user_2)
        cls.catalogo_matematicas = CatalogoMateria.objects.create(nombre='Matemáticas')
        cls.catalogo_historia = CatalogoMateria.objects.create(nombre='Historia')
        cls.ciclo, _ = CicloEscolar.objects.get_or_create(nombre='2026-2027')
        cls.ciclo.activo = True
        cls.ciclo.save(update_fields=['activo'])
        cls.materia_1 = Materia.objects.create(
            nombre='Matemáticas', catalogo=cls.catalogo_matematicas,
            maestro=cls.maestro_1, grupo=cls.grupo_1, ciclo=cls.ciclo
        )
        cls.materia_2 = Materia.objects.create(
            nombre='Historia', catalogo=cls.catalogo_historia,
            maestro=cls.maestro_2, grupo=cls.grupo_2, ciclo=cls.ciclo
        )
        cls.alumno_1 = Alumno.objects.create(
            nombre='Ana', apellido='Uno', grupo=cls.grupo_1
        )
        cls.alumno_2 = Alumno.objects.create(
            nombre='Beto', apellido='Dos', grupo=cls.grupo_2
        )

    def test_anonimo_es_redirigido_al_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_usuario_sin_rol_recibe_403(self):
        self.client.force_login(self.usuario_sin_rol)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 403)

    def test_maestro_solo_ve_sus_alumnos(self):
        self.client.force_login(self.user_1)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, self.materia_1.nombre)
        self.assertNotContains(response, self.materia_2.nombre)

    def test_maestro_no_abre_objetos_ajenos(self):
        self.client.force_login(self.user_1)
        self.assertEqual(
            self.client.get(reverse('detalle_alumno', args=[self.alumno_2.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse('centro_mando_materia', args=[self.materia_2.pk])
            ).status_code,
            404,
        )

    def test_maestro_no_accede_a_rutas_administrativas(self):
        self.client.force_login(self.user_1)
        self.assertEqual(self.client.get(reverse('registrar_maestro')).status_code, 403)
        self.assertEqual(self.client.get(reverse('registrar_materia')).status_code, 403)
        self.assertEqual(self.client.get('/admin/').status_code, 302)

    def test_admin_accede_a_rutas_administrativas(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('registrar_maestro')).status_code, 200)
        self.assertEqual(self.client.get(reverse('registrar_materia')).status_code, 200)
        self.assertEqual(self.client.get('/admin/').status_code, 200)

    def test_quitar_tarea_exige_post_y_propiedad(self):
        tarea_1 = TareaPendiente.objects.create(
            alumno=self.alumno_1,
            materia=self.materia_1,
            nombre_tarea='Ejercicios',
        )
        tarea_2 = TareaPendiente.objects.create(
            alumno=self.alumno_2,
            materia=self.materia_2,
            nombre_tarea='Ensayo',
        )
        self.client.force_login(self.user_1)

        url_1 = reverse('marcar_tarea', args=[self.alumno_1.pk, tarea_1.pk])
        self.assertEqual(self.client.get(url_1).status_code, 405)
        self.assertEqual(self.client.post(url_1).status_code, 302)
        self.assertFalse(TareaPendiente.objects.filter(pk=tarea_1.pk).exists())

        url_2 = reverse('marcar_tarea', args=[self.alumno_2.pk, tarea_2.pk])
        self.assertEqual(self.client.post(url_2).status_code, 404)
        self.assertTrue(TareaPendiente.objects.filter(pk=tarea_2.pk).exists())

    def test_registro_periodo_rechaza_anonimo_y_materia_ajena(self):
        propia = reverse(
            'registrar_tareas_periodo', args=[self.grupo_1.pk, self.materia_1.pk]
        )
        ajena = reverse(
            'registrar_tareas_periodo', args=[self.grupo_2.pk, self.materia_2.pk]
        )
        self.assertEqual(self.client.get(propia).status_code, 302)
        self.client.force_login(self.user_1)
        self.assertEqual(self.client.get(ajena).status_code, 404)


class ApiControlAccesoTests(ControlAccesoTests):
    def test_api_rechaza_anonimo(self):
        self.assertEqual(self.client.get('/api/alumnos').status_code, 401)

    def test_api_por_sesion_exige_csrf_en_post(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user_1)
        response = client.post(
            '/api/tareas/reportar-falta',
            data={
                'alumno_id': self.alumno_1.pk,
                'materia_id': self.materia_1.pk,
                'nombre_tarea': 'Ejercicios',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_api_filtra_alumnos_por_maestro(self):
        self.client.force_login(self.user_1)
        response = self.client.get('/api/alumnos')
        self.assertEqual(response.status_code, 200)
        ids = {item['id'] for item in response.json()}
        self.assertEqual(ids, {self.alumno_1.pk})
        self.assertEqual(
            self.client.get(f'/api/estado/{self.alumno_2.pk}').status_code,
            404,
        )

    def test_api_administrativa_rechaza_maestro(self):
        self.client.force_login(self.user_1)
        self.assertEqual(self.client.get('/api/maestros').status_code, 403)
        self.assertEqual(
            self.client.get('/api/atp/exportar-alertas-excel').status_code,
            403,
        )

    def test_api_administrativa_permite_admin(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/api/maestros').status_code, 200)
        self.assertEqual(
            self.client.get('/api/atp/exportar-alertas-excel').status_code,
            200,
        )


class AdminDashboardCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ControlAccesoTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_dashboard_agrupa_materias_y_las_ordena(self):
        Materia.objects.create(nombre='Matemáticas', catalogo=self.catalogo_matematicas, maestro=self.maestro_2, grupo=self.grupo_2, ciclo=self.ciclo)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        agrupadas = response.context['materias_agrupadas']
        self.assertEqual([item['nombre'] for item in agrupadas], ['Historia', 'Matemáticas'])
        matematicas = next(item for item in agrupadas if item['nombre'] == 'Matemáticas')
        self.assertEqual(matematicas['total_grupos'], 2)

    def test_grupos_de_materia_estan_ordenados_y_enlazan_centro_mando(self):
        Materia.objects.create(nombre='Matemáticas', catalogo=self.catalogo_matematicas, maestro=self.maestro_2, grupo=self.grupo_2, ciclo=self.ciclo)
        response = self.client.get(reverse('admin_materia_grupos', args=['matematicas']))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['materias'].values_list('grupo__grado', flat=True)), [1, 2])
        self.assertContains(response, reverse('centro_mando_materia', args=[self.materia_1.pk]))

    def test_rutas_administrativas_rechazan_maestro(self):
        self.client.force_login(self.user_1)
        urls = [
            reverse('admin_dashboard'),
            reverse('admin_materia_grupos', args=['matematicas']),
            reverse('editar_maestro', args=[self.maestro_1.pk]),
            reverse('eliminar_materia', args=[self.materia_1.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_editar_maestro_conserva_password_si_se_deja_vacio(self):
        response = self.client.post(reverse('editar_maestro', args=[self.maestro_1.pk]), {
            'username': 'ada-editada', 'password': '', 'nombre': 'Ada María',
            'apellido_paterno': 'Lovelace', 'apellido_materno': '',
        })
        self.assertRedirects(response, reverse('registrar_maestro'))
        self.user_1.refresh_from_db()
        self.maestro_1.refresh_from_db()
        self.assertEqual(self.user_1.username, 'ada-editada')
        self.assertTrue(self.user_1.check_password('test-pass'))
        self.assertEqual(self.maestro_1.nombre, 'Ada María')

    def test_no_elimina_maestro_con_historial(self):
        url = reverse('eliminar_maestro', args=[self.maestro_1.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(Maestro.objects.filter(pk=self.maestro_1.pk).exists())
        self.client.post(url)
        self.assertTrue(Maestro.objects.filter(pk=self.maestro_1.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.user_1.pk).exists())

    def test_elimina_maestro_sin_asignaciones_tras_confirmacion(self):
        user = User.objects.create_user('sin-asignaciones', password='test-pass')
        maestro = Maestro.objects.create(user=user, nombre='Sin', apellido_paterno='Asignaciones')
        self.client.post(reverse('eliminar_maestro', args=[maestro.pk]))
        self.assertFalse(Maestro.objects.filter(pk=maestro.pk).exists())
        self.assertFalse(User.objects.filter(pk=user.pk).exists())

    def test_editar_materia_modifica_solo_una_instancia(self):
        otra = Materia.objects.create(nombre='Matemáticas', catalogo=self.catalogo_matematicas, maestro=self.maestro_2, grupo=self.grupo_2, ciclo=self.ciclo)
        response = self.client.post(reverse('editar_materia', args=[self.materia_1.pk]), {
            'catalogo': self.catalogo_historia.pk, 'maestro': self.maestro_1.pk,
            'grupo': self.grupo_1.pk,
        })
        self.assertRedirects(response, reverse('registrar_materia'))
        self.materia_1.refresh_from_db()
        otra.refresh_from_db()
        self.assertEqual(self.materia_1.nombre, 'Historia')
        self.assertEqual(otra.nombre, 'Matemáticas')

    def test_eliminar_materia_requiere_post(self):
        url = reverse('eliminar_materia', args=[self.materia_1.pk])
        self.client.get(url)
        self.assertTrue(Materia.objects.filter(pk=self.materia_1.pk).exists())
        self.client.post(url)
        self.assertFalse(Materia.objects.filter(pk=self.materia_1.pk).exists())

    def test_formulario_usa_catalogo_y_solo_docentes_activos(self):
        self.maestro_2.activo = False
        self.maestro_2.save(update_fields=['activo'])
        response = self.client.get(reverse('registrar_materia'))
        form = response.context['form']
        self.assertIn(self.catalogo_matematicas, form.fields['catalogo'].queryset)
        self.assertIn(self.maestro_1, form.fields['maestro'].queryset)
        self.assertNotIn(self.maestro_2, form.fields['maestro'].queryset)

    def test_reasignacion_masiva_exige_confirmacion(self):
        datos = {
            'catalogo': self.catalogo_matematicas.pk,
            'maestro': self.maestro_2.pk,
            'grupos': [self.grupo_1.pk],
        }
        response = self.client.post(reverse('registrar_materia'), datos)
        self.assertEqual(response.status_code, 200)
        self.materia_1.refresh_from_db()
        self.assertEqual(self.materia_1.maestro, self.maestro_1)
        datos['confirmar_reasignaciones'] = 'on'
        self.client.post(reverse('registrar_materia'), datos)
        self.materia_1.refresh_from_db()
        self.assertEqual(self.materia_1.maestro, self.maestro_2)

    def test_desactivar_maestro_bloquea_acceso_sin_borrar_historial(self):
        self.client.post(reverse('cambiar_estado_maestro', args=[self.maestro_1.pk]))
        self.maestro_1.refresh_from_db()
        self.user_1.refresh_from_db()
        self.assertFalse(self.maestro_1.activo)
        self.assertFalse(self.user_1.is_active)
        self.assertTrue(Materia.objects.filter(pk=self.materia_1.pk).exists())

    def test_crear_ciclo_puede_copiar_asignaciones_y_activarlo(self):
        response = self.client.post(reverse('gestionar_ciclos'), {
            'nombre': '2027-2028', 'copiar_asignaciones': self.ciclo.pk, 'activar': 'on',
        })
        self.assertRedirects(response, reverse('gestionar_ciclos'))
        nuevo = CicloEscolar.objects.get(nombre='2027-2028')
        self.ciclo.refresh_from_db()
        self.assertTrue(nuevo.activo)
        self.assertFalse(self.ciclo.activo)
        self.assertEqual(nuevo.asignaciones.count(), self.ciclo.asignaciones.count())

    def test_cerrar_ciclo_conserva_sus_asignaciones(self):
        self.client.post(reverse('cerrar_ciclo', args=[self.ciclo.pk]))
        self.ciclo.refresh_from_db()
        self.assertTrue(self.ciclo.cerrado)
        self.assertFalse(self.ciclo.activo)
        self.assertEqual(self.ciclo.asignaciones.count(), 2)

    def test_tablero_atp_marca_reporte_completo_entregado_tarde(self):
        periodo = PeriodoReporte.objects.create(
            ciclo=self.ciclo, nombre='Quincena', fecha_inicio='2026-09-01',
            fecha_fin='2026-09-15', fecha_limite='2026-09-16', activo=True,
        )
        registro = RegistroTareasPeriodo.objects.create(
            materia=self.materia_1, grupo=self.grupo_1, periodo_reporte=periodo,
            fecha_inicio=date(2026, 9, 1), fecha_fin=date(2026, 9, 15), total_tareas_encargadas=1,
        )
        RegistroTareasPeriodo.objects.filter(pk=registro.pk).update(
            fecha_creacion=timezone.make_aware(datetime(2026, 9, 17, 12, 0))
        )
        response = self.client.get(reverse('tablero_reportes_atp'))
        fila = next(f for f in response.context['filas'] if f['maestro'] == self.maestro_1)
        self.assertEqual(fila['estado_actividades'], 'tarde')
        self.assertEqual(response.context['resumen']['maestros'], 2)
        self.assertEqual(response.context['resumen']['actividades_entregadas'], 1)
        self.assertEqual(response.context['resumen']['asistencias_entregadas'], 0)


class PortalTutoresTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ControlAccesoTests.setUpTestData.__func__(cls)
        cls.usuario_tutor = User.objects.create_user('familia-ana', password='ClaveSegura!2026')
        cls.tutor = Tutor.objects.create(
            user=cls.usuario_tutor,
            nombre='María',
            apellido='Pérez',
            correo='maria@example.com',
            telefono='4920000000',
        )
        cls.tutor.hijos.add(cls.alumno_1)

    def test_tutor_solo_consulta_sus_alumnos(self):
        self.client.force_login(self.usuario_tutor)
        response = self.client.get(reverse('tablero_tutor'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['alumno'], self.alumno_1)
        self.assertEqual(self.client.get(reverse('tablero_tutor') + f'?alumno={self.alumno_2.pk}').status_code, 404)

    def test_tutor_puede_cambiar_entre_varios_hijos(self):
        self.tutor.hijos.add(self.alumno_2)
        self.client.force_login(self.usuario_tutor)
        response = self.client.get(reverse('tablero_tutor') + f'?alumno={self.alumno_2.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['alumno'], self.alumno_2)
        self.assertContains(response, self.alumno_1.nombre)
        self.assertContains(response, self.alumno_2.nombre)

    def test_administrador_crea_tutor_con_cuenta_y_varios_alumnos(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('registrar_tutor'), {
            'username': 'familia-nueva',
            'password': 'ClaveSegura!2026',
            'nombre': 'Claudia',
            'apellido': 'Ramírez',
            'correo': 'claudia@example.com',
            'telefono': '4921111111',
            'hijos': [self.alumno_1.pk, self.alumno_2.pk],
        })
        self.assertRedirects(response, reverse('registrar_tutor'))
        tutor = Tutor.objects.get(correo='claudia@example.com')
        self.assertTrue(tutor.user.check_password('ClaveSegura!2026'))
        self.assertEqual(set(tutor.hijos.values_list('pk', flat=True)), {self.alumno_1.pk, self.alumno_2.pk})

    def test_gestion_tutores_exige_administrador(self):
        self.client.force_login(self.user_1)
        self.assertEqual(self.client.get(reverse('registrar_tutor')).status_code, 403)


class CentroMandoValidacionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ControlAccesoTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.client.force_login(self.user_1)
        self.url = reverse('centro_mando_materia', args=[self.materia_1.pk])
        self.periodo = PeriodoReporte.objects.create(
            ciclo=self.ciclo,
            nombre='Reporte de prueba',
            fecha_inicio='2026-09-01',
            fecha_fin='2026-09-15',
            fecha_limite='2026-09-18',
            activo=True,
        )

    def test_tareas_rechaza_numeros_invalidos_sin_crear_registro(self):
        response = self.client.post(self.url, {
            'tipo_formulario': 'guardar_tareas',
            'fecha_inicio_tareas': '2026-06-01', 'fecha_fin_tareas': '2026-06-15',
            'total_tareas_encargadas': '2', f'tareas_alumno_{self.alumno_1.pk}': '3',
        })
        self.assertRedirects(response, self.url)
        self.assertFalse(RegistroTareasPeriodo.objects.exists())

    def test_tareas_rechaza_valor_no_numerico(self):
        self.client.post(self.url, {
            'tipo_formulario': 'guardar_tareas',
            'fecha_inicio_tareas': '2026-06-01', 'fecha_fin_tareas': '2026-06-15',
            'total_tareas_encargadas': 'dos', f'tareas_alumno_{self.alumno_1.pk}': '0',
        })
        self.assertFalse(RegistroTareasPeriodo.objects.exists())

    def test_inasistencias_usa_fechas_del_periodo_activo(self):
        self.client.post(self.url, {
            'tipo_formulario': 'guardar_inasistencias',
            'fecha_inicio_faltas': '2026-06-15', 'fecha_fin_faltas': '2026-06-01',
            f'faltas_alumno_{self.alumno_1.pk}': '1',
        })
        registro = RegistroInasistenciasPeriodo.objects.get()
        self.periodo.refresh_from_db()
        self.assertEqual(registro.fecha_inicio, self.periodo.fecha_inicio)
        self.assertEqual(registro.fecha_fin, self.periodo.fecha_fin)

    def test_post_valido_crea_registros_atomicos(self):
        self.client.post(self.url, {
            'tipo_formulario': 'guardar_tareas',
            'fecha_inicio_tareas': '2026-06-01', 'fecha_fin_tareas': '2026-06-15',
            'total_tareas_encargadas': '5', f'tareas_alumno_{self.alumno_1.pk}': '2',
        })
        registro = RegistroTareasPeriodo.objects.get()
        self.assertEqual(registro.detalles_alumnos.get().tareas_no_entregadas, 2)
        self.assertEqual(registro.periodo_reporte, self.periodo)

    def test_rechaza_captura_si_no_hay_periodo_activo(self):
        self.periodo.activo = False
        self.periodo.save(update_fields=['activo'])
        self.client.post(self.url, {
            'tipo_formulario': 'guardar_tareas',
            'fecha_inicio_tareas': '2026-09-01', 'fecha_fin_tareas': '2026-09-15',
            'total_tareas_encargadas': '2', f'tareas_alumno_{self.alumno_1.pk}': '0',
        })
        self.assertFalse(RegistroTareasPeriodo.objects.exists())
