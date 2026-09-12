from django.db import connection
from django.http import JsonResponse


def health_check(request):
    """Confirma que Django y PostgreSQL están disponibles."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        return JsonResponse({'status': 'error'}, status=503)
    return JsonResponse({'status': 'ok'})
