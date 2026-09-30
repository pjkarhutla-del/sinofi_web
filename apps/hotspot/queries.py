"""Query agregasi hotspot yang dipakai dashboard, halaman monitor, dan API."""
from datetime import date, timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from apps.laporan.models import Laporan

from .models import Confidence, Hotspot

MONITORED = (Confidence.HIGH, Confidence.MEDIUM)


def safe_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def default_range():
    today = timezone.localdate()
    return today - timedelta(days=settings.HOTSPOT_DASHBOARD_DAYS), today


def parse_range(params):
    dari, sampai = safe_date(params.get("dari")), safe_date(params.get("sampai"))
    d0, d1 = default_range()
    dari, sampai = dari or d0, sampai or d1
    return (sampai, dari) if dari > sampai else (dari, sampai)


def monitored(dari, sampai):
    return Hotspot.objects.filter(tanggal__range=(dari, sampai), confidence__in=MONITORED)


def summary(dari, sampai):
    """Hitungan High/Medium di dalam kawasan konservasi."""
    agg = monitored(dari, sampai).filter(kawasan__isnull=False).aggregate(
        high=Count("id", filter=Q(confidence=Confidence.HIGH)),
        medium=Count("id", filter=Q(confidence=Confidence.MEDIUM)),
    )
    agg["total"] = agg["high"] + agg["medium"]
    return agg


def top_kawasan(dari, sampai, limit=10):
    rows = (monitored(dari, sampai).filter(kawasan__isnull=False)
            .values("kawasan_id", "kawasan__nkws", "kawasan__nupt")
            .annotate(high=Count("id", filter=Q(confidence=Confidence.HIGH)),
                      medium=Count("id", filter=Q(confidence=Confidence.MEDIUM)),
                      total=Count("id"))
            .order_by("-total", "kawasan__nkws")[:limit])
    return [{"kawasan_id": r["kawasan_id"], "nkws": r["kawasan__nkws"], "nupt": r["kawasan__nupt"],
             "high": r["high"], "medium": r["medium"], "total": r["total"]} for r in rows]


def weekly_by_upt(today=None, days=7):
    """{'dates': [...], 'series': {UPT: {NKWS: [n per hari]}}} untuk `days` hari terakhir."""
    today = today or timezone.localdate()
    dates = [today - timedelta(days=days - 1 - i) for i in range(days)]
    rows = (monitored(dates[0], today).filter(kawasan__isnull=False)
            .values("kawasan__nupt", "kawasan__nkws", "tanggal").annotate(n=Count("id")))
    series = {}
    for r in rows:
        counts = series.setdefault(r["kawasan__nupt"], {}).setdefault(r["kawasan__nkws"], [0] * days)
        counts[dates.index(r["tanggal"])] = r["n"]
    return {"dates": [d.isoformat() for d in dates], "series": dict(sorted(series.items()))}


def unreported_kawasan(dari, sampai):
    """Kawasan yang terdeteksi hotspot (High/Medium) tetapi belum ada laporan pada rentang yang sama."""
    reported = Laporan.objects.filter(tanggal__range=(dari, sampai)).values("kawasan_id")
    rows = (monitored(dari, sampai).filter(kawasan__isnull=False).exclude(kawasan_id__in=reported)
            .values("kawasan_id", "kawasan__nkws", "kawasan__nupt", "kawasan__npulau")
            .annotate(high=Count("id", filter=Q(confidence=Confidence.HIGH)),
                      medium=Count("id", filter=Q(confidence=Confidence.MEDIUM)),
                      total=Count("id"))
            .order_by("-high", "-total", "kawasan__nkws"))
    return [{"kawasan_id": r["kawasan_id"], "nkws": r["kawasan__nkws"], "nupt": r["kawasan__nupt"],
             "npulau": r["kawasan__npulau"], "high": r["high"], "medium": r["medium"], "total": r["total"]}
            for r in rows]
