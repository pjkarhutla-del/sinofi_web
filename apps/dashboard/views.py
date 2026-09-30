from datetime import date

from django.conf import settings
from django.shortcuts import render
from django.utils import timezone

from apps.hotspot import queries as hq
from apps.hotspot.models import HotspotSyncLog
from apps.kawasan.models import Kawasan
from apps.laporan import services
from apps.laporan.constants import STATUS_META, Status

from .access import read_access


@read_access
def dashboard(request):
    rows = services.load_rows()
    today = timezone.localdate()
    d0, d1 = hq.default_range()
    active = services.active_extinction(rows)
    pending = services.pending_updates(rows, today)
    return render(request, "dashboard/dashboard.html", {
        "stats": services.card_stats(rows),
        "breakdown": services.status_breakdown(rows),
        "active": active,
        "pending": pending,
        "hotspot": hq.summary(d0, d1),
        "hotspot_range": (d0, d1),
        "unreported": hq.unreported_kawasan(d0, d1),
        "today": today,
        "now": timezone.localtime(),
    })


@read_access
def matriks(request):
    rows = services.load_rows()
    try:
        start = date.fromisoformat(request.GET.get("start", "")) if request.GET.get("start") else None
    except ValueError:
        start = None
    matrix = services.build_matrix(rows, timezone.localdate(), start, settings.MATRIX_WINDOW_DAYS)
    return render(request, "dashboard/matriks.html", {
        "m": matrix, "today": timezone.localdate(),
        "pulau_options": [g["npulau"] for g in matrix["groups"]],
        "status_meta": STATUS_META,
    })


@read_access
def peta(request):
    d0, d1 = hq.default_range()
    dari, sampai = hq.parse_range(request.GET) if request.GET.get("dari") else (d0, d1)
    kawasan = list(Kawasan.objects.values("id", "nupt", "nkws").order_by("nupt", "nkws"))
    return render(request, "dashboard/peta.html", {
        "dari": dari, "sampai": sampai, "kawasan": kawasan,
        "upt_list": sorted({k["nupt"] for k in kawasan}),
        "statuses": [{"name": s, **STATUS_META[s]} for s in Status.values],
    })


@read_access
def hotspot_monitor(request):
    dari, sampai = hq.parse_range(request.GET)
    upt_list = list(Kawasan.objects.order_by("nupt").values_list("nupt", flat=True).distinct())
    return render(request, "dashboard/hotspot.html", {
        "dari": dari, "sampai": sampai, "summary": hq.summary(dari, sampai), "upt_list": upt_list,
        "unreported": hq.unreported_kawasan(dari, sampai),
        "last_sync": HotspotSyncLog.objects.filter(success=True).first(),
    })
