import json
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.dashboard.access import api_read_access, read_access
from apps.kawasan.models import Kawasan
from apps.kawasan.spatial import get_index

from .constants import STATUS_META, Status
from .forms import LaporanForm, PointFormSet
from .models import Laporan
from .parser import parse_report_text

COMMON_FIELDS = ("tanggal", "kawasan", "upaya", "rencana", "personel", "kendala", "kebutuhan", "gakkum", "laporan")


def _kawasan_tree():
    return list(Kawasan.objects.values("id", "npulau", "nupt", "nkws").order_by("npulau", "nupt", "nkws"))


def _form_context(form, formset, obj=None):
    return {
        "form": form, "formset": formset, "obj": obj,
        "kawasan_tree": _kawasan_tree(),
        "statuses": [{"value": s, **STATUS_META[s]} for s in Status.values],
    }


def _warn_outside(request, kawasan, points):
    """Peringatan (tidak memblokir) bila titik berada di luar batas kawasan terpilih."""
    if not kawasan.geom:
        return
    index = get_index()
    for n, p in enumerate(points, 1):
        if index.covers(kawasan.id, p["lon"], p["lat"]) is False:
            messages.warning(request, f"Titik ke-{n} ({p['lat']}, {p['lon']}) berada di luar batas kawasan {kawasan.nkws}. Pastikan koordinat & kawasan sudah benar.")


@login_required
@permission_required("laporan.add_laporan", raise_exception=True)
def laporan_create(request):
    if request.method == "POST":
        form, fs = LaporanForm(request.POST), PointFormSet(request.POST, prefix="pt")
        if form.is_valid() and fs.is_valid():
            base = form.cleaned_data
            points = [f.cleaned_data for f in fs.forms if f.cleaned_data]
            common = {k: base[k] for k in COMMON_FIELDS}
            with transaction.atomic():
                for p in points:
                    Laporan.objects.create(**common, **p, created_by=request.user, updated_by=request.user)
            messages.success(request, f"{len(points)} titik laporan berhasil disimpan.")
            _warn_outside(request, base["kawasan"], points)
            return redirect("matriks")
    else:
        form = LaporanForm(initial={
            "tanggal": _safe_date(request.GET.get("tanggal")) or timezone.localdate(),
            "kawasan": request.GET.get("kawasan") or None,
        })
        fs = PointFormSet(prefix="pt", initial=[{"status": Status.UPAYA, "luas": 0}])
    return render(request, "laporan/form.html", _form_context(form, fs))


@login_required
@permission_required("laporan.change_laporan", raise_exception=True)
def laporan_update(request, pk):
    obj = get_object_or_404(Laporan.objects.select_related("kawasan"), pk=pk)
    if request.method == "POST":
        form, fs = LaporanForm(request.POST), PointFormSet(request.POST, prefix="pt")
        if form.is_valid() and fs.is_valid():
            base = form.cleaned_data
            points = [f.cleaned_data for f in fs.forms if f.cleaned_data]
            common = {k: base[k] for k in COMMON_FIELDS}
            with transaction.atomic():
                # Baris = satu titik: titik pertama memperbarui laporan ini, titik tambahan menjadi baris baru.
                for k, v in {**common, **points[0]}.items():
                    setattr(obj, k, v)
                obj.updated_by = request.user
                obj.save()
                for p in points[1:]:
                    Laporan.objects.create(**common, **p, created_by=request.user, updated_by=request.user)
            messages.success(request, "Laporan berhasil diperbarui.")
            _warn_outside(request, base["kawasan"], points)
            return redirect("matriks")
    else:
        form = LaporanForm(initial={k: getattr(obj, k) for k in COMMON_FIELDS})
        fs = PointFormSet(prefix="pt", initial=[{"lat": obj.lat, "lon": obj.lon, "status": obj.status, "luas": obj.luas}])
    return render(request, "laporan/form.html", _form_context(form, fs, obj))


@login_required
@permission_required("laporan.delete_laporan", raise_exception=True)
@require_POST
def laporan_delete(request, pk):
    obj = get_object_or_404(Laporan, pk=pk)
    obj.delete()
    if request.accepts("application/json") and not request.accepts("text/html"):
        return JsonResponse({"deleted": str(pk)})
    messages.success(request, "Laporan dihapus.")
    nxt = request.POST.get("next", "")
    return redirect(nxt if url_has_allowed_host_and_scheme(nxt, {request.get_host()}) else "laporan_list")


@read_access
def laporan_list(request):
    qs = Laporan.objects.select_related("kawasan")
    g = request.GET
    if g.get("q"):
        qs = qs.filter(Q(kawasan__nkws__icontains=g["q"]) | Q(kawasan__nupt__icontains=g["q"]))
    if g.get("status") in Status.values:
        qs = qs.filter(status=g["status"])
    if g.get("pulau"):
        qs = qs.filter(kawasan__npulau=g["pulau"])
    if d := _safe_date(g.get("dari")):
        qs = qs.filter(tanggal__gte=d)
    if d := _safe_date(g.get("sampai")):
        qs = qs.filter(tanggal__lte=d)
    page = Paginator(qs, 50).get_page(g.get("page"))
    qd = g.copy()
    qd.pop("page", None)
    return render(request, "laporan/list.html", {
        "page": page, "querystring": qd.urlencode(), "statuses": Status.values,
        "status_meta": STATUS_META, "f": g,
        "pulau_list": Kawasan.objects.order_by().values_list("npulau", flat=True).distinct(),
    })


@login_required
@require_POST
def laporan_parse(request):
    try:
        text = json.loads(request.body or "{}").get("text", "")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Format permintaan tidak valid."}, status=400)
    kawasan = list(Kawasan.objects.values_list("id", "nkws"))
    return JsonResponse(parse_report_text(text, kawasan))


# ------------------------------------------------------------------ API
def _safe_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _point(l):
    k = l.kawasan
    return {"id": str(l.id), "tanggal": l.tanggal.isoformat(), "kawasan_id": k.id, "nkws": k.nkws,
            "nupt": k.nupt, "npulau": k.npulau, "status": l.status, "lat": l.lat, "lon": l.lon,
            "luas": float(l.luas)}


@api_read_access
def api_laporan(request):
    """Titik laporan untuk peta. Filter: upt, kawasan, tanggal, dari, sampai, status."""
    g = request.GET
    qs = Laporan.objects.select_related("kawasan")
    if g.get("upt"):
        qs = qs.filter(kawasan__nupt=g["upt"])
    if g.get("kawasan", "").isdigit():
        qs = qs.filter(kawasan_id=int(g["kawasan"]))
    if d := _safe_date(g.get("tanggal")):
        qs = qs.filter(tanggal=d)
    if d := _safe_date(g.get("dari")):
        qs = qs.filter(tanggal__gte=d)
    if d := _safe_date(g.get("sampai")):
        qs = qs.filter(tanggal__lte=d)
    if g.get("status") in Status.values:
        qs = qs.filter(status=g["status"])
    return JsonResponse({"results": [_point(l) for l in qs.order_by("tanggal", "updated_at")[:20000]]})


@api_read_access
def api_laporan_detail(request):
    """Seluruh titik pada satu kawasan & tanggal (untuk modal detail/carousel)."""
    kid, d = request.GET.get("kawasan", ""), _safe_date(request.GET.get("tanggal"))
    if not kid.isdigit() or not d:
        return JsonResponse({"error": "Parameter kawasan dan tanggal wajib."}, status=400)
    qs = Laporan.objects.select_related("kawasan").filter(kawasan_id=int(kid), tanggal=d).order_by("updated_at")
    user = request.user
    can_edit, can_delete = user.has_perm("laporan.change_laporan"), user.has_perm("laporan.delete_laporan")
    out = []
    for l in qs:
        out.append({
            **_point(l), "upaya": l.upaya, "rencana": l.rencana, "personel": l.personel,
            "kendala": l.kendala, "kebutuhan": l.kebutuhan, "gakkum": l.gakkum, "laporan": l.laporan,
            "updated_at": timezone.localtime(l.updated_at).strftime("%d/%m/%Y %H:%M"),
            "edit_url": reverse("laporan_update", args=[l.id]) if can_edit else None,
            "delete_url": reverse("laporan_delete", args=[l.id]) if can_delete else None,
        })
    return JsonResponse({"results": out})
