"""Analisis spasial titik-dalam-poligon (menggantikan Turf.js di browser).

Menggunakan Shapely STRtree sehingga tidak butuh GDAL/PostGIS. Indeks dibangun
sekali per proses dan dibangun ulang otomatis jika data kawasan berubah.
"""
import logging
import threading

import numpy as np
import shapely
from django.db.models import Count, Max
from shapely.geometry import shape
from shapely.strtree import STRtree
from shapely.validation import make_valid

log = logging.getLogger(__name__)
_lock = threading.Lock()
_cache = {"key": None, "index": None}


class KawasanIndex:
    def __init__(self, items):
        """items: iterable (kawasan_id, geojson_geometry) sesuai urutan prioritas."""
        self.ids = []
        self.geoms = []
        self.pos = {}
        geoms = self.geoms
        for kid, geometry in items:
            if not geometry:
                continue
            try:
                g = shape(geometry)
                if not g.is_valid:
                    g = make_valid(g)
            except Exception:  # geometri rusak tidak boleh menggagalkan seluruh indeks
                log.warning("Geometri kawasan id=%s tidak valid, dilewati", kid)
                continue
            self.pos[kid] = len(self.ids)
            self.ids.append(kid)
            geoms.append(g)
        self.tree = STRtree(geoms) if geoms else None

    def __len__(self):
        return len(self.ids)

    def locate_many(self, points):
        """points: list[(lon, lat)] -> list[kawasan_id | None].

        Jika titik berada di irisan beberapa poligon, dipilih poligon dengan urutan
        terkecil (sama dengan perilaku aplikasi lama: poligon pertama yang cocok).
        Titik tepat di batas dianggap berada di dalam.
        """
        n = len(points)
        result = [None] * n
        if not n or self.tree is None:
            return result
        pts = shapely.points(np.array(points, dtype=float))
        input_idx, tree_idx = self.tree.query(pts, predicate="intersects")
        best = {}
        for i, t in zip(input_idx.tolist(), tree_idx.tolist()):
            if i not in best or t < best[i]:
                best[i] = t
        for i, t in best.items():
            result[i] = self.ids[t]
        return result

    def locate(self, lon, lat):
        return self.locate_many([(lon, lat)])[0]

    def covers(self, kawasan_id, lon, lat):
        """True/False bila kawasan punya geometri; None bila geometrinya tidak tersedia."""
        i = self.pos.get(kawasan_id)
        if i is None:
            return None
        return bool(self.geoms[i].intersects(shapely.Point(lon, lat)))


def get_index():
    """Indeks kawasan (cache per proses, otomatis diperbarui saat data berubah)."""
    from .models import Kawasan

    agg = Kawasan.objects.filter(geom__isnull=False).aggregate(n=Count("id"), t=Max("updated_at"))
    key = (agg["n"], agg["t"])
    with _lock:
        if _cache["key"] != key:
            rows = Kawasan.objects.filter(geom__isnull=False).order_by("objectid", "id").values_list("id", "geom")
            _cache["index"] = KawasanIndex(rows)
            _cache["key"] = key
            log.info("Indeks spasial kawasan dibangun: %s poligon", len(_cache["index"]))
        return _cache["index"]
