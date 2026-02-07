from django.conf import settings
from django.contrib import auth
import time

# Tiempo de inactividad en segundos (1 hora)
AUTO_LOGOUT_DELAY = getattr(settings, 'AUTO_LOGOUT_DELAY', 3600)

class AutoLogoutMiddleware:
    """Middleware sencillo para cerrar sesión si el usuario ha estado inactivo más de AUTO_LOGOUT_DELAY segundos.

    - Debe estar colocado después de AuthenticationMiddleware en MIDDLEWARE.
    - Guarda la marca de tiempo de la última actividad en la sesión bajo '_last_activity'.
    - Si la diferencia supera AUTO_LOGOUT_DELAY, se cierra la sesión y se elimina la marca.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            if request.user.is_authenticated:
                now = int(time.time())
                last_activity = request.session.get('_last_activity')
                if last_activity is not None:
                    try:
                        last_activity = int(last_activity)
                    except Exception:
                        last_activity = None
                if last_activity and (now - last_activity) > AUTO_LOGOUT_DELAY:
                    # cerrar sesión y limpiar clave
                    try:
                        auth.logout(request)
                    except Exception:
                        pass
                    try:
                        del request.session['_last_activity']
                    except Exception:
                        pass
                else:
                    # actualizar timestamp
                    try:
                        request.session['_last_activity'] = now
                        request.session.modified = True
                    except Exception:
                        pass
        except Exception:
            # no fallar la petición por errores del middleware
            pass

        response = self.get_response(request)
        return response
