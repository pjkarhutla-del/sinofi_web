from django.conf import settings

from apps.laporan.constants import STATUS_META, Status


def siaga(request):
    return {
        "PUBLIC_READ": settings.SIAGA_PUBLIC_READ,
        "STATUS_LEGEND": [{"name": s, **STATUS_META[s]} for s in Status.values],
    }
