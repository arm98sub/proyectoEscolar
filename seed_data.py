import os
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from alumnos.models import Alumno, Grupo

def run():
    # 1. Limpiamos datos viejos para no duplicar
    print("Limpiando base de datos...")
    Alumno.objects.all().delete()
    Grupo.objects.all().delete()

    # 2. Creamos los Grupos
    print("Creando grupos...")
    grupos_db = []
    secciones = ['A', 'B', 'C']
    for grado in [1, 2, 3]:
        for sec in secciones:
            g = Grupo.objects.create(grado=grado, seccion=sec)
            grupos_db.append(g)
    
    # 3. Datos para alumnos
    nombres = ["Juan", "Maria", "Pedro", "Ana", "Luis", "Elena", "Diego", "Carmen", "Sofía", "Javier"]
    apellidos = ["Garcia", "Rodriguez", "Lopez", "Martinez", "Perez", "Sánchez", "Gómez", "Díaz"]

    print(f"Generando 100 alumnos repartidos en {len(grupos_db)} grupos...")
    
    for _ in range(100):
        grupo_asignado = random.choice(grupos_db)
        
        a = Alumno.objects.create(
            nombre=random.choice(nombres),
            apellido=random.choice(apellidos),
            grupo=grupo_asignado,  # <--- Aquí sucede la relación (Foreign Key)
            asistencias_totales=random.randint(10, 30),
            clases_totales=30,
            promedio_actual=round(random.uniform(5.0, 10.0), 1)
        )
    
    print("¡Proceso completado exitosamente!")

if __name__ == "__main__":
    run()