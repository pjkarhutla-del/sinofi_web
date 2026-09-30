"""Impor data lama dari Supabase (ekspor CSV tabel `reports`, opsional tabel `kawasan`)."""
import csv
import re
import uuid
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.kawasan.models import Kawasan
from apps.kawasan.utils import canonical_pulau, norm_text
from apps.laporan.models import Laporan
from apps.laporan.parser import normalize_status


def _num(value, default=None):
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(value or ""))
    return float(m.group(0).replace(",", ".")) if m else default


class Command(BaseCommand):
    help = "Impor laporan lama dari CSV ekspor Supabase (tabel reports)."

    def add_arguments(self, parser):
        parser.add_argument("reports_csv")
        parser.add_argument("--kawasan-csv", help="CSV ekspor tabel kawasan lama (id,npulau,nupt,nkws) untuk memetakan kawasan_id lama.")
        parser.add_argument("--create-missing", action="store_true", help="Buat kawasan baru (tanpa batas wilayah) bila tidak ditemukan.")
        parser.add_argument("--match-nkws-only", action="store_true",
                            help="Izinkan pencocokan hanya berdasar nama kawasan (NKWS) bila unik, walau UPT berbeda. "
                                 "Default mati karena bisa salah atribusi ke UPT lain.")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--skipped-out", default="import_dilewati.csv", help="File CSV baris yang dilewati.")

    def handle(self, *args, **o):
        by_name = {(norm_text(k.nupt), norm_text(k.nkws)): k for k in Kawasan.objects.all()}
        by_nkws = {}
        for k in by_name.values():
            by_nkws.setdefault(norm_text(k.nkws), []).append(k)

        old_ids = {}
        if o["kawasan_csv"]:
            with open(o["kawasan_csv"], newline="", encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    k = by_name.get((norm_text(r.get("nupt")), norm_text(r.get("nkws"))))
                    if k:
                        old_ids[str(r["id"]).strip()] = k

        def resolve(r):
            if r.get("kawasan_id") and str(r["kawasan_id"]).strip() in old_ids:
                return old_ids[str(r["kawasan_id"]).strip()]
            key = (norm_text(r.get("nupt")), norm_text(r.get("nkws")))
            if key in by_name:
                return by_name[key]
            cands = by_nkws.get(key[1], [])
            if o["match_nkws_only"] and len(cands) == 1:
                return cands[0]
            if o["create_missing"] and key[0] and key[1]:
                k = Kawasan.objects.create(npulau=canonical_pulau(r.get("npulau") or r.get("nupt")),
                                           nupt=r["nupt"].strip(), nkws=r["nkws"].strip())
                by_name[key] = k
                by_nkws.setdefault(key[1], []).append(k)
                return k
            return None

        try:
            fh = open(o["reports_csv"], newline="", encoding="utf-8-sig")
        except OSError as exc:
            raise CommandError(str(exc)) from exc

        objs, stamps, skipped = [], {}, []
        with fh:
            existing = set(Laporan.objects.values_list("id", flat=True))
            existing_legacy = set(Laporan.objects.exclude(legacy_id__isnull=True).values_list("legacy_id", flat=True))
            for n, r in enumerate(csv.DictReader(fh), start=2):
                try:
                    pk = uuid.UUID(str(r.get("report_uuid") or "").strip()) if r.get("report_uuid") else uuid.uuid4()
                except ValueError:
                    pk = uuid.uuid4()
                legacy = int(r["id"]) if str(r.get("id") or "").strip().isdigit() else None
                if pk in existing or (legacy is not None and legacy in existing_legacy):
                    skipped.append((n, "sudah ada (UUID/ID lama sama)"))
                    continue
                k = resolve(r)
                lat, lon = _num(r.get("lat")), _num(r.get("lon"))
                try:
                    tgl = date.fromisoformat(str(r.get("tanggal") or "")[:10])
                except ValueError:
                    tgl = None
                if k is None:
                    skipped.append((n, f"kawasan tidak ditemukan: {r.get('nupt')} / {r.get('nkws')} (cek ejaan, atau pakai --match-nkws-only)"))
                    continue
                if tgl is None or lat is None or lon is None:
                    skipped.append((n, "tanggal/koordinat tidak valid"))
                    continue
                objs.append(Laporan(
                    id=pk, legacy_id=legacy,
                    tanggal=tgl, kawasan=k, status=normalize_status(r.get("status")), lat=lat, lon=lon,
                    luas=_num(r.get("luas"), 0) or 0, upaya=r.get("upaya") or "", rencana=r.get("rencana") or "",
                    personel=(r.get("personel") or "")[:500], kendala=r.get("kendala") or "",
                    kebutuhan=r.get("kebutuhan") or "", laporan=r.get("laporan") or "", gakkum=r.get("gakkum") or "",
                ))
                created = parse_datetime(r.get("created_at") or "") or timezone.now()
                stamps[pk] = (created, parse_datetime(r.get("updated_at") or "") or created)
                existing.add(pk)
                if legacy is not None:
                    existing_legacy.add(legacy)

        if not o["dry_run"] and objs:
            with transaction.atomic():
                Laporan.objects.bulk_create(objs, batch_size=1000)
                for obj in objs:  # pertahankan cap waktu asli (auto_now menimpa saat insert)
                    obj.created_at, obj.updated_at = stamps[obj.id]
                Laporan.objects.bulk_update(objs, ["created_at", "updated_at"], batch_size=1000)

        if skipped:
            with open(o["skipped_out"], "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["baris_csv", "alasan"])
                w.writerows(skipped)
        verb = "akan diimpor" if o["dry_run"] else "diimpor"
        self.stdout.write(self.style.SUCCESS(f"{len(objs)} laporan {verb}; {len(skipped)} dilewati" +
                                             (f" (lihat {o['skipped_out']})." if skipped else ".")))
