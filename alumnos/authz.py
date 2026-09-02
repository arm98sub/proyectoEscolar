from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def es_administrador(user):
    """Administradores del sistema: superusuarios o miembros del staff."""
    return user.is_authenticated and (user.is_superuser or user.is_staff)


def es_maestro(user):
    """Un maestro debe tener un perfil Maestro asociado y no ser administrador."""
    return (
        user.is_authenticated
        and not es_administrador(user)
        and hasattr(user, "maestro")
        and user.maestro.activo
    )


def role_required(predicate):
    """Exige autenticación y después responde 403 cuando el rol no corresponde."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), "login")
            if not predicate(request.user):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


admin_required = role_required(es_administrador)
maestro_required = role_required(es_maestro)


def docente_o_admin_required(view_func):
    return role_required(lambda user: es_administrador(user) or es_maestro(user))(
        view_func
    )
