"""Data contoh agar sistem bisa dicoba tanpa data asli. JANGAN dijalankan di produksi."""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from shapely.geometry import shape

from apps.hotspot.models import Hotspot
from apps.hotspot.services import store_records
from apps.kawasan.models import Kawasan
from apps.laporan.constants import Status
from apps.laporan.models import Laporan

SCENARIOS = [
    [Status.KONFIRMASI, Status.GROUNDCHECK, Status.UPAYA, Status.UPAYA, Status.UPAYA],           # aktif
    [Status.GROUNDCHECK, Status.UPAYA, Status.UPAYA, Status.PADAM],                              # selesai
    [Status.KONFIRMASI, Status.FALSE_HOTSPOT],                                                   # false
    [Status.UPAYA, Status.UPAYA, Status.UPAYA, Status.UPAYA, Status.UPAYA, Status.UPAYA],        # aktif lama
    [Status.KONFIRMASI, Status.GROUNDCHECK],                                                     # pending
    [Status.UPAYA, Status.UPAYA],                                                                # tertunggak
    [Status.GROUNDCHECK, Status.PADAM],
    [Status.UPAYA, Status.PADAM, Status.KONFIRMASI, Status.UPAYA, Status.UPAYA],                 # dua kejadian
]


class Command(BaseCommand):
    help = "Isi data contoh: laporan, hotspot, dan pengguna demo (opsional)."

    def add_arguments(self, parser):
        parser.add_argument("--with-user", action="store_true", help="Buat superuser demo/demo12345.")

    def handle(self, *args, **o):
        rnd = random.Random(42)
        kaws = list(Kawasan.objects.filter(geom__isnull=False).order_by("objectid")[:80])
        if not kaws:
            raise CommandError("Kawasan kosong. Jalankan dulu: python manage.py import_kawasan")
        today = timezone.localdate()

        def point_in(k):
            g = shape(k.geom)
            for _ in range(50):
                minx, miny, maxx, maxy = g.bounds
                lon, lat = rnd.uniform(minx, maxx), rnd.uniform(miny, maxy)
                from shapely.geometry import Point
                if g.contains(Point(lon, lat)):
                    return round(lat, 6), round(lon, 6)
            p = g.representative_point()
            return round(p.y, 6), round(p.x, 6)

        Laporan.objects.filter(laporan__startswith="[DEMO]").delete()
        made = 0
        for k, steps in zip(rnd.sample(kaws, len(SCENARIOS)), SCENARIOS):
            lat, lon = point_in(k)
            # akhiri skenario pada hari ini (aktif) atau 2 hari lalu (tertunggak) bergantian
            end = today - timedelta(days=0 if rnd.random() < .6 else 2)
            for i, st in enumerate(steps):
                d = end - timedelta(days=len(steps) - 1 - i)
                Laporan.objects.create(
                    tanggal=d, kawasan=k, status=st, lat=lat, lon=lon,
                    luas=0 if st == Status.FALSE_HOTSPOT else round(rnd.uniform(1, 25), 2),
                    upaya="Pemadaman darat dan sekat bakar." if st == Status.UPAYA else "",
                    rencana="Patroli ulang esok hari.", personel=f"{rnd.randint(6, 25)} personel",
                    kendala=rnd.choice(["Akses berlumpur.", "Sumber air jauh.", "Sinyal lemah.", ""]),
                    laporan=f"[DEMO] {k.nkws} — {st} pada {d:%d/%m/%Y}.",
                )
                made += 1

        Hotspot.objects.filter(hs_id__startswith="DEMO-").delete()
        recs = []
        for n in range(120):
            k = rnd.choice(kaws[:40]) if n < 90 else None
            lat, lon = point_in(k) if k else (round(rnd.uniform(-8, 1), 5), round(rnd.uniform(101, 118), 5))
            d = today - timedelta(days=rnd.randint(0, 6))
            recs.append({"hs_id": f"DEMO-{d.isoformat()}-{n:04d}", "tanggal": d, "waktu": f"{d} {rnd.randint(0,23):02d}:00",
                         "confidence": rnd.choice(["high", "medium", "medium"]),
                         "satelit": rnd.choice(["NASA-SNPP", "NASA-NOAA20", "NASA-MODIS"]), "lat": lat, "lon": lon})
        stored, inside = store_records(recs)

        if o["with_user"]:
            U = get_user_model()
            u, _ = U.objects.get_or_create(username="demo", defaults={"is_staff": True, "is_superuser": True})
            u.set_password("demo12345")
            u.save()
            self.stdout.write("Pengguna demo: demo / demo12345")
        self.stdout.write(self.style.SUCCESS(f"{made} laporan demo, {stored} hotspot demo ({inside} di dalam kawasan)."))
