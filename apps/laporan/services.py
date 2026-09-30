"""Logika bisnis pemantauan karhutla (port dari JavaScript aplikasi Laporan Harian).

Semua fungsi bekerja pada daftar `Row` ringan sehingga mudah diuji tanpa database.

Konsep utama
- Rantai status (chain): rangkaian laporan satu kawasan sampai muncul status akhir
  (Sudah Padam / False Hotspot). Klasifikasi rantai ditentukan status terakhirnya.
- Gelombang pemadaman (wave): dipakai untuk daftar "Pemadaman Aktif" — Groundcheck,
  Upaya, dan Konfirmasi dalam satu gelombang terbuka dihitung sebagai satu durasi,
  tetapi kawasan hanya masuk daftar bila gelombang itu pernah memuat Upaya Pemadaman.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from apps.kawasan.utils import PULAU_LIST

from .constants import OPEN_STATUSES, STATUS_META, TERMINAL_STATUSES, Status
from .models import Laporan


@dataclass(slots=True)
class Row:
    id: str
    tanggal: date
    stamp: datetime
    kawasan_id: int
    npulau: str
    nupt: str
    nkws: str
    status: str
    lat: float
    lon: float
    luas: float

    @property
    def sort_key(self):
        return (self.tanggal, self.stamp, str(self.id))


def load_rows(qs=None):
    qs = Laporan.objects.all() if qs is None else qs
    fields = ("id", "tanggal", "updated_at", "kawasan_id", "kawasan__npulau", "kawasan__nupt",
              "kawasan__nkws", "status", "lat", "lon", "luas")
    return [
        Row(str(i), t, st, kid, np_, nu, nk, s, la, lo, float(lu or 0))
        for i, t, st, kid, np_, nu, nk, s, la, lo, lu in qs.values_list(*fields)
    ]


def days_between(start, end):
    """Selisih hari tanggal-saja, minimum 0 (padanan daysBetweenDateOnly)."""
    if not start or not end:
        return 0
    return max(0, (end - start).days)


def days_inclusive(start, end):
    if not start or not end:
        return 0
    return max(0, (end - start).days + 1)


# ------------------------------------------------------------------ rantai status
@dataclass
class Chain:
    kawasan_id: int
    npulau: str
    nupt: str
    nkws: str
    started_at: date
    ended_at: date | None = None
    reports: list = field(default_factory=list)
    latest: Row | None = None
    has_fire_effort: bool = False
    has_resolved: bool = False
    has_false_hotspot: bool = False

    def append(self, r: Row):
        self.reports.append(r)
        self.latest = r
        if r.status == Status.UPAYA:
            self.has_fire_effort = True
        elif r.status == Status.PADAM:
            self.has_resolved, self.ended_at = True, r.tanggal
        elif r.status == Status.FALSE_HOTSPOT:
            self.has_false_hotspot, self.ended_at = True, r.tanggal

    @property
    def classification(self):
        s = self.latest.status if self.latest else ""
        if self.has_false_hotspot and s == Status.FALSE_HOTSPOT:
            return "false_hotspot"
        return {
            Status.PADAM: "sudah_padam",
            Status.UPAYA: "upaya_aktif",
            Status.GROUNDCHECK: "groundcheck_pending",
            Status.KONFIRMASI: "konfirmasi_pending",
        }.get(s, "tidak_diklasifikasi")

    def first_date_of(self, status):
        for r in self.reports:
            if r.status == status:
                return r.tanggal
        return self.started_at


def _group_by_kawasan(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r.kawasan_id, []).append(r)
    for lst in groups.values():
        lst.sort(key=lambda r: r.sort_key)
    return groups


def build_chains(rows):
    chains = []
    for lst in _group_by_kawasan(rows).values():
        current = None
        for r in lst:
            if current is None:
                current = Chain(r.kawasan_id, r.npulau, r.nupt, r.nkws, r.tanggal)
            current.append(r)
            if r.status in TERMINAL_STATUSES:
                chains.append(current)
                current = None
        if current is not None:
            chains.append(current)
    return chains


# ------------------------------------------------------------------ statistik kartu
def affected_kawasan_count(rows):
    return len({r.kawasan_id for r in rows if r.status in (Status.UPAYA, Status.PADAM)})


def card_stats(rows):
    chains = build_chains(rows)
    s = dict(total_kejadian=0, upaya_aktif=0, sudah_padam=0, groundcheck_pending=0,
             konfirmasi_pending=0, false_hotspot=0)
    for c in chains:
        k = c.classification
        if k == "false_hotspot":
            s["false_hotspot"] += 1
        elif k in s:
            s[k] += 1
            s["total_kejadian"] += 1
    s["pending_verifikasi"] = s["groundcheck_pending"] + s["konfirmasi_pending"]
    s["persen_padam"] = round(s["sudah_padam"] * 100 / s["total_kejadian"]) if s["total_kejadian"] else 0
    s["total_baris"] = len(rows)
    s["jumlah_chain"] = len(chains)
    s["kawasan_terdampak"] = affected_kawasan_count(rows)
    return s


def status_breakdown(rows):
    total = len(rows) or 1
    out = []
    for status in Status.values:
        n = sum(1 for r in rows if r.status == status)
        out.append({"status": status, "count": n, "percent": round(n * 100 / total, 1), **STATUS_META[status]})
    return out


# ------------------------------------------------------------------ pemadaman aktif & perlu update
def active_extinction(rows, reference_date=None):
    """Kawasan yang gelombang operasional terakhirnya masih terbuka dan pernah ada Upaya Pemadaman."""
    out = []
    for kid, lst in _group_by_kawasan(rows).items():
        wave = None
        for r in lst:
            if r.status in TERMINAL_STATUSES:
                wave = None
                continue
            if r.status in OPEN_STATUSES:
                if wave is None:
                    wave = {"sejak": r.tanggal, "reports": [], "upaya": False}
                wave["last"] = r.tanggal
                wave["reports"].append(r)
                wave["upaya"] |= r.status == Status.UPAYA
        if not wave or not wave["upaya"]:
            continue
        latest = wave["reports"][-1]
        end = reference_date or wave["last"]
        out.append({
            "kawasan_id": kid, "npulau": latest.npulau, "nupt": latest.nupt, "nkws": latest.nkws,
            "sejak_tanggal": wave["sejak"], "tanggal_laporan_terakhir": wave["last"],
            "status_terakhir": latest.status, "jumlah_hari": days_inclusive(wave["sejak"], end),
            "jumlah_laporan": len(wave["reports"]),
            "jumlah_upaya": sum(1 for r in wave["reports"] if r.status == Status.UPAYA),
            "lat": latest.lat, "lon": latest.lon,
        })
    out.sort(key=lambda x: (-x["jumlah_hari"], x["nkws"].lower()))
    return out


def pending_updates(rows, reference_date, minimum_days_late=1):
    """Status masih terbuka namun belum diperbarui sampai `reference_date`."""
    pending = {"upaya_aktif", "groundcheck_pending", "konfirmasi_pending"}
    out = []
    for c in build_chains(rows):
        if c.classification not in pending:
            continue
        last = c.latest.tanggal
        late = days_between(last, reference_date)
        if late >= minimum_days_late:
            out.append({
                "kawasan_id": c.kawasan_id, "npulau": c.npulau, "nupt": c.nupt, "nkws": c.nkws,
                "status_terakhir": c.latest.status, "sejak_tanggal": last,
                "jumlah_hari_terlambat": late, "jumlah_laporan": len(c.reports),
            })
    out.sort(key=lambda x: (-x["jumlah_hari_terlambat"], x["nkws"].lower()))
    return out


def sort_items(items, key, direction="asc"):
    reverse = direction == "desc"
    text_keys = {"nkws", "status_terakhir"}
    return sorted(
        items,
        key=lambda x: (str(x.get(key) or "").lower() if key in text_keys else (x.get(key) or 0)),
        reverse=reverse,
    )


# ------------------------------------------------------------------ matriks kawasan x tanggal
def matrix_date_bounds(rows, today):
    dates = [r.tanggal for r in rows]
    default_start, default_end = today - timedelta(days=30), today + timedelta(days=7)
    start = min([default_start, *dates]) if dates else default_start
    end = max([default_end, *dates]) if dates else default_end
    return start, end


def build_matrix(rows, today, start=None, window=14):
    lo, hi = matrix_date_bounds(rows, today)
    default_start = today - timedelta(days=window - 1)
    if start is None or not (lo <= start <= hi):
        start = max(lo, min(default_start, hi - timedelta(days=window - 1)))
    dates = [start + timedelta(days=i) for i in range(window) if start + timedelta(days=i) <= hi]

    buckets = {}
    for r in rows:
        node = buckets.setdefault(r.kawasan_id, {
            "kawasan_id": r.kawasan_id, "npulau": r.npulau or "LAINNYA", "nupt": r.nupt, "nkws": r.nkws,
            "by_date": {},
        })
        cell = node["by_date"].setdefault(r.tanggal, {"last": r, "count": 0})
        cell["count"] += 1
        if (r.stamp, str(r.id)) >= (cell["last"].stamp, str(cell["last"].id)):
            cell["last"] = r

    order = [*PULAU_LIST, "LAINNYA"]
    groups = []
    for pulau in order:
        items = sorted((n for n in buckets.values() if n["npulau"] == pulau),
                       key=lambda n: (n["nupt"].lower(), n["nkws"].lower()))
        if not items:
            continue
        for n in items:
            n["cells"] = []
            for d in dates:
                c = n["by_date"].get(d)
                n["cells"].append({
                    "date": d,
                    "status": c["last"].status if c else None,
                    "css": STATUS_META.get(c["last"].status, STATUS_META[Status.KONFIRMASI])["css"] if c else "",
                    "symbol": {Status.KONFIRMASI: "!", Status.FALSE_HOTSPOT: "×"}.get(c["last"].status, "") if c else "",
                    "count": c["count"] if c else 0,
                })
        groups.append({"npulau": pulau, "items": items})

    step = timedelta(days=window)
    last_start = hi - timedelta(days=window - 1)
    return {
        "dates": dates, "groups": groups, "start": start,
        "end": dates[-1] if dates else start,
        "prev_start": max(lo, start - step) if start > lo else None,
        "next_start": min(start + step, max(lo, last_start)) if start < last_start else None,
    }
