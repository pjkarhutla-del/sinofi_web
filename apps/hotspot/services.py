import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.kawasan.spatial import get_index

from .models import Hotspot, HotspotSyncLog
from .sipongi import fetch_features, parse_feature

log = logging.getLogger(__name__)
CHUNK = 2000


def store_records(records):
    """Upsert hotspot (kunci hs_id) sambil menentukan kawasan lewat analisis spasial.
    Mengembalikan (jumlah_disimpan, jumlah_dalam_kawasan)."""
    unique = {r["hs_id"]: r for r in records}  # hs_id ganda dalam satu respons
    records = list(unique.values())
    if not records:
        return 0, 0
    kawasan_ids = get_index().locate_many([(r["lon"], r["lat"]) for r in records])
    objs = [Hotspot(**r, kawasan_id=kid) for r, kid in zip(records, kawasan_ids)]
    with transaction.atomic():
        for i in range(0, len(objs), CHUNK):
            Hotspot.objects.bulk_create(
                objs[i:i + CHUNK], update_conflicts=True, unique_fields=["hs_id"],
                update_fields=["tanggal", "waktu", "confidence", "satelit", "lat", "lon", "kawasan"],
            )
    return len(objs), sum(1 for k in kawasan_ids if k)


def sync_range(date_from=None, date_to=None, fetcher=fetch_features):
    """Ambil hotspot SIPONGI untuk satu rentang (None = periode default server) lalu simpan."""
    log_row = HotspotSyncLog.objects.create(date_from=date_from, date_to=date_to)
    try:
        features = fetcher(date_from, date_to)
        keep = set(settings.HOTSPOT_STORE_CONFIDENCE)
        records = [r for f in features if (r := parse_feature(f)) and r["confidence"] in keep]
        stored, inside = store_records(records)
        log_row.fetched, log_row.stored, log_row.inside_kawasan, log_row.success = len(features), stored, inside, True
        log_row.message = f"{len(features)} titik diterima, {stored} disimpan, {inside} di dalam kawasan."
    except Exception as exc:  # catat lalu lempar ulang agar cron/command tahu gagal
        log_row.message = f"{type(exc).__name__}: {exc}"
        log.exception("Sinkronisasi hotspot gagal")
        raise
    finally:
        log_row.finished_at = timezone.now()
        log_row.save()
    return log_row


def sync_days(days, fetcher=fetch_features):
    """Sinkron per hari (hari ini mundur `days` hari) agar respons API tetap kecil."""
    today = timezone.localdate()
    logs = []
    for offset in range(days, -1, -1):
        d = today - timedelta(days=offset)
        logs.append(sync_range(d, d, fetcher))
    return logs


def rematch_all(batch=5000):
    """Hitung ulang kawasan seluruh hotspot (jalankan setelah batas kawasan berubah)."""
    index = get_index()
    changed = total = 0
    qs = Hotspot.objects.order_by("id").only("id", "lat", "lon", "kawasan_id")
    buf = []

    def flush(items):
        nonlocal changed, total
        ids = index.locate_many([(h.lon, h.lat) for h in items])
        upd = []
        for h, kid in zip(items, ids):
            total += 1
            if h.kawasan_id != kid:
                h.kawasan_id = kid
                upd.append(h)
        if upd:
            Hotspot.objects.bulk_update(upd, ["kawasan"])
            changed += len(upd)

    for h in qs.iterator(chunk_size=batch):
        buf.append(h)
        if len(buf) >= batch:
            flush(buf)
            buf = []
    if buf:
        flush(buf)
    return total, changed
