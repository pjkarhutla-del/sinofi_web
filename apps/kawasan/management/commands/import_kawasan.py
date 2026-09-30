import json
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid

from apps.kawasan.models import Kawasan
from apps.kawasan.utils import canonical_pulau


def _round_coords(obj, nd):
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(float(v), nd) for v in obj[:2]]  # buang koordinat Z
        return [_round_coords(o, nd) for o in obj]
    return obj


def _polygonal(geom):
    """Pastikan hasil perbaikan geometri hanya berisi Polygon/MultiPolygon."""
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    parts = [g for g in getattr(geom, "geoms", []) if g.geom_type in ("Polygon", "MultiPolygon")]
    return unary_union(parts) if parts else geom


class Command(BaseCommand):
    help = "Impor/perbarui master kawasan beserta batas wilayahnya dari file GeoJSON."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(settings.KAWASAN_GEOJSON_FILE))
        parser.add_argument("--tolerance", type=float, default=0.0003,
                            help="Toleransi penyederhanaan geometri untuk peta web (derajat).")

    @transaction.atomic
    def handle(self, *args, **opts):
        path = Path(opts["file"])
        if not path.exists():
            raise CommandError(f"File tidak ditemukan: {path}")
        started = time.time()
        data = json.loads(path.read_text(encoding="utf-8"))
        created = updated = repaired = 0

        for feat in data["features"]:
            p = feat.get("properties") or {}
            nkws = (p.get("NKWS") or p.get("nama") or "").strip()
            nupt = (p.get("NUPT") or p.get("upt") or "").strip()
            if not nkws or not nupt:
                self.stderr.write(f"Dilewati (NKWS/NUPT kosong): {p}")
                continue

            geometry = dict(feat["geometry"])
            geometry["coordinates"] = _round_coords(geometry["coordinates"], 6)
            geom = shape(geometry)
            if not geom.is_valid:
                geom = _polygonal(make_valid(geom))
                repaired += 1
            simple = _polygonal(geom.simplify(opts["tolerance"], preserve_topology=True))
            simple_geojson = mapping(simple)
            simple_geojson = {"type": simple_geojson["type"],
                              "coordinates": _round_coords(simple_geojson["coordinates"], 5)}
            minx, miny, maxx, maxy = geom.bounds

            _, was_created = Kawasan.objects.update_or_create(
                nupt=nupt, nkws=nkws,
                defaults=dict(
                    objectid=p.get("OBJECTID_1"),
                    npulau=canonical_pulau(p.get("NPULAU")),
                    geom=geometry,
                    geom_simplified=simple_geojson,
                    min_lon=minx, min_lat=miny, max_lon=maxx, max_lat=maxy,
                ),
            )
            created += was_created
            updated += not was_created

        self.stdout.write(self.style.SUCCESS(
            f"Selesai dalam {time.time() - started:.1f} dtk: {created} kawasan baru, {updated} diperbarui, "
            f"{repaired} geometri diperbaiki otomatis."))
