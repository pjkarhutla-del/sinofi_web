from django.http import JsonResponse
from django.views.decorators.cache import cache_control

from apps.dashboard.access import api_read_access

from .models import Kawasan


@api_read_access
@cache_control(private=True, max_age=3600)
def kawasan_geojson(request):
    """Batas kawasan (versi disederhanakan) sebagai FeatureCollection untuk peta web."""
    features = [
        {
            "type": "Feature",
            "properties": {"id": k.id, "nkws": k.nkws, "nupt": k.nupt, "npulau": k.npulau},
            "geometry": k.geom_simplified or k.geom,
        }
        for k in Kawasan.objects.filter(geom__isnull=False).order_by("objectid", "id")
    ]
    return JsonResponse({"type": "FeatureCollection", "features": features},
                        json_dumps_params={"separators": (",", ":")})
