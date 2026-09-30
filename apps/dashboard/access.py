"""Kontrol akses baca: login wajib, kecuali SIAGA_PUBLIC_READ=1."""
from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse


def read_access(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if settings.SIAGA_PUBLIC_READ or request.user.is_authenticated:
            return view(request, *args, **kwargs)
        return redirect_to_login(request.get_full_path())
    return wrapper


def api_read_access(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if settings.SIAGA_PUBLIC_READ or request.user.is_authenticated:
            return view(request, *args, **kwargs)
        return JsonResponse({"error": "Login diperlukan."}, status=401)
    return wrapper
