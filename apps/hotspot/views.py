import csv
import io
import zipfile

from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from openpyxl import Workbook

from apps.dashboard.access import api_read_access, read_access

from . import queries

EXPORT_HEADERS = ["HS_ID", "Confidence", "Waktu", "Tanggal", "NUPT", "NKWS", "Longitude_X", "Latitude_Y", "Satelit"]
WGS84_PRJ = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
             'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')


@api_read_access
def api_hotspot(request):
    """Titik hotspot High/Medium pada rentang tanggal (untuk peta). kid=null berarti di luar kawasan."""
    dari, sampai = queries.parse_range(request.GET)
    qs = queries.monitored(dari, sampai)
    if request.GET.get("upt"):
        qs = qs.filter(kawasan__nupt=request.GET["upt"])
    if request.GET.get("kawasan", "").isdigit():
        qs = qs.filter(kawasan_id=int(request.GET["kawasan"]))
    rows = qs.values_list("hs_id", "tanggal", "waktu", "confidence", "satelit", "lat", "lon", "kawasan_id")[:60000]
    return JsonResponse({
        "dari": dari.isoformat(), "sampai": sampai.isoformat(),
        "summary": queries.summary(dari, sampai),
        "results": [{"id": h, "tanggal": t.isoformat(), "waktu": w, "conf": c, "sat": s,
                     "lat": la, "lon": lo, "kid": k} for h, t, w, c, s, la, lo, k in rows],
    })


@api_read_access
def api_hotspot_stats(request):
    dari, sampai = queries.parse_range(request.GET)
    return JsonResponse({
        "dari": dari.isoformat(), "sampai": sampai.isoformat(),
        "summary": queries.summary(dari, sampai),
        "top": queries.top_kawasan(dari, sampai),
        "weekly": queries.weekly_by_upt(),
    })


def _export_rows(dari, sampai, scope):
    qs = queries.monitored(dari, sampai).select_related("kawasan").order_by("tanggal", "hs_id")
    if scope != "semua":
        qs = qs.filter(kawasan__isnull=False)
    for h in qs.iterator():
        k = h.kawasan
        yield [h.hs_id, h.confidence.capitalize(), h.waktu, h.tanggal, k.nupt if k else "-",
               k.nkws if k else "-", h.lon, h.lat, h.satelit or "-"]


@read_access
def hotspot_export(request, fmt):
    dari, sampai = queries.parse_range(request.GET)
    scope = request.GET.get("scope", "dalam")
    name = f"hotspot_kawasan_{dari}_{sampai}"
    rows = list(_export_rows(dari, sampai, scope))

    if fmt == "csv":
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{name}.csv"'
        resp.write("\ufeff")  # BOM agar Excel membaca UTF-8
        w = csv.writer(resp)
        w.writerow(EXPORT_HEADERS)
        w.writerows(rows)
        return resp

    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "DataHotspotKawasan"
        ws.append(EXPORT_HEADERS)
        for r in rows:
            ws.append(r)
        buf = io.BytesIO()
        wb.save(buf)
        resp = HttpResponse(buf.getvalue(),
                            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = f'attachment; filename="{name}.xlsx"'
        return resp

    if fmt == "shp":
        import shapefile

        shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
        with shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POINT, encoding="utf-8") as w:
            for fld in (("HS_ID", "C", 60), ("CONF", "C", 10), ("WAKTU", "C", 40), ("TANGGAL", "C", 10),
                        ("NUPT", "C", 150), ("NKWS", "C", 150), ("SATELIT", "C", 40)):
                w.field(*fld)
            for hs_id, conf, waktu, tgl, nupt, nkws, lon, lat, sat in rows:
                w.point(lon, lat)
                w.record(hs_id, conf, waktu, str(tgl), nupt, nkws, sat)
        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(f"{name}/hotspot_points.shp", shp.getvalue())
            z.writestr(f"{name}/hotspot_points.shx", shx.getvalue())
            z.writestr(f"{name}/hotspot_points.dbf", dbf.getvalue())
            z.writestr(f"{name}/hotspot_points.prj", WGS84_PRJ)
        resp = HttpResponse(zbuf.getvalue(), content_type="application/zip")
        resp["Content-Disposition"] = f'attachment; filename="{name}_shp.zip"'
        return resp

    raise Http404("Format ekspor tidak dikenal.")


@require_POST
def hotspot_sync(request):
    """Sinkronisasi manual dari SIPONGI (khusus staf)."""
    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({"error": "Hanya staf yang dapat menjalankan sinkronisasi."}, status=403)
    from . import services

    try:
        logs = services.sync_days(2)
    except Exception as exc:
        return JsonResponse({"error": f"Sinkronisasi gagal: {exc}"}, status=502)
    return JsonResponse({"ok": True, "message": " | ".join(l.message for l in logs)})
