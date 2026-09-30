from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.hotspot import services


class Command(BaseCommand):
    help = "Ambil hotspot dari API SIPONGI, cocokkan dengan batas kawasan, simpan ke PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=2, help="Hari ini dan N hari ke belakang (default 2).")
        parser.add_argument("--from", dest="date_from", help="Tanggal awal YYYY-MM-DD (satu permintaan).")
        parser.add_argument("--to", dest="date_to", help="Tanggal akhir YYYY-MM-DD.")
        parser.add_argument("--latest", action="store_true", help="Pakai periode default server (tanpa filter tanggal).")
        parser.add_argument("--rematch", action="store_true", help="Hitung ulang kawasan semua hotspot tersimpan.")

    def handle(self, *args, **o):
        if o["rematch"]:
            total, changed = services.rematch_all()
            self.stdout.write(self.style.SUCCESS(f"Rematch: {total} hotspot diperiksa, {changed} berubah."))
            return
        try:
            if o["latest"]:
                logs = [services.sync_range(None, None)]
            elif o["date_from"] and o["date_to"]:
                logs = [services.sync_range(date.fromisoformat(o["date_from"]), date.fromisoformat(o["date_to"]))]
            else:
                logs = services.sync_days(o["days"])
        except Exception as exc:
            raise CommandError(f"Sinkronisasi gagal: {exc}") from exc
        for l in logs:
            self.stdout.write(f"{l.date_from or 'default'} → {l.message}")
        self.stdout.write(self.style.SUCCESS("Sinkronisasi hotspot selesai."))
