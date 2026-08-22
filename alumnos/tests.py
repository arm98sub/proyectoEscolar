from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import Alumno, Grupo, Maestro, Materia, TareaPendiente


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
        cls.materia_1 = Materia.objects.create(
            nombre='Matemáticas', maestro=cls.maestro_1, grupo=cls.grupo_1
        )
        cls.materia_2 = Materia.objects.create(
            nombre='Historia', maestro=cls.maestro_2, grupo=cls.grupo_2
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
