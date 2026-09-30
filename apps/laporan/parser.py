"""Parser teks laporan WhatsApp/tempelan -> field formulir.

Pengembangan dari parser aplikasi lama. Selain koordinat, luas, dan status, parser
kini juga mengambil tanggal, personel, upaya, rencana, kendala, kebutuhan, serta
menebak kawasan. Urutan koordinat dideteksi otomatis dari besaran angkanya
(lintang Indonesia -11..6, bujur 94..141) sehingga "X/Y" atau "lat/lon" tertukar
tetap terbaca benar.
"""
import re
from datetime import date

from .constants import LAT_RANGE, LON_RANGE, Status

BULAN = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7,
    "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
}


def normalize_status(value=""):
    """Padanan normalizeStatus() lama. Nilai tak dikenal dianggap Upaya Pemadaman."""
    x = str(value or "").lower()
    if re.search(r"false|bukan titik|bukan api", x):
        return Status.FALSE_HOTSPOT.value
    if re.search(r"sudah padam|telah padam|pendinginan selesai", x):
        return Status.PADAM.value
    if re.search(r"ground\s*check|groundcheck|cek lapangan|verifikasi lapangan", x):
        return Status.GROUNDCHECK.value
    if re.search(r"konfirmasi|belum.*status|menunggu.*(info|verifikasi)", x):
        return Status.KONFIRMASI.value
    return Status.UPAYA.value


def in_indonesia(lat, lon):
    return LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]


def assign_lat_lon(a, b):
    """Tentukan (lat, lon) dari dua angka dengan urutan tak diketahui. None jika tak masuk akal."""
    if in_indonesia(a, b):
        return a, b
    if in_indonesia(b, a):
        return b, a
    return None


def parse_date(text):
    m = re.search(r"\b(\d{1,2})\s+(" + "|".join(BULAN) + r")\s+(20\d{2})\b", text, re.I)
    if m:
        try:
            return date(int(m.group(3)), BULAN[m.group(2).lower()], int(m.group(1)))
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-]((?:20)?\d{2})\b", text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y += 2000 if y < 100 else 0
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    return None


_NUM = r"[+-]?\d{1,3}[.,]\d{3,}"
_PAIR = re.compile(rf"({_NUM})[^\d\n]{{1,20}}?({_NUM})")


def parse_coordinates(text):
    points = []
    for m in _PAIR.finditer(text):
        a, b = (float(m.group(i).replace(",", ".")) for i in (1, 2))
        ll = assign_lat_lon(a, b)
        if ll and ll not in points:
            points.append(ll)
    return [{"lat": lat, "lon": lon} for lat, lon in points]


def parse_luas(text):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:ha|hektar)\b", text, re.I)
    return float(m.group(1).replace(",", ".")) if m else None


_LABELS = {
    "personel": r"personel|jumlah personel|personil|tim",
    "upaya": r"upaya|upaya pemadaman|tindakan",
    "rencana": r"rencana(?: tindak lanjut)?|tindak lanjut|rtl",
    "kendala": r"kendala|hambatan",
    "kebutuhan": r"kebutuhan|saran|kebutuhan/saran",
}


def parse_labeled_fields(text):
    """Ambil isi baris berlabel, mis. 'Kendala: akses berlumpur' (dukung isi multi-baris)."""
    out = {}
    all_labels = "|".join(v for v in _LABELS.values()) + r"|lokasi|koordinat|status|luas(?: terbakar)?|tanggal|hari"
    for key, pattern in _LABELS.items():
        m = re.search(
            rf"(?im)^\s*(?:[-*•\d.)]+\s*)?(?:{pattern})\s*[:\-–]\s*(.+?)(?=\n\s*(?:[-*•\d.)]+\s*)?(?:{all_labels})\s*[:\-–]|\Z)",
            text, re.S,
        )
        if m:
            out[key] = re.sub(r"\s*\n\s*", " ", m.group(1)).strip()
    return out


def guess_kawasan(text, kawasan_list):
    """kawasan_list: iterable (id, nkws). Kembalikan id jika tepat satu nama kawasan muncul di teks."""
    low = text.lower()
    hits = [kid for kid, nkws in kawasan_list if nkws and nkws.lower() in low]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:  # ambil nama terpanjang bila saling mengandung (mis. "TN X" vs "TN X Barat")
        names = {kid: nk for kid, nk in kawasan_list if kid in hits}
        longest = max(names.values(), key=len)
        winners = [k for k, v in names.items() if v == longest]
        return winners[0] if len(winners) == 1 else None
    return None


def parse_report_text(text, kawasan_list=()):
    text = text or ""
    status = normalize_status(text)
    luas = parse_luas(text)
    coords = parse_coordinates(text)
    d = parse_date(text)
    fields = parse_labeled_fields(text)
    points = [
        {**c, "status": status, "luas": (luas if i == 0 and luas is not None else 0)}
        for i, c in enumerate(coords)
    ]
    return {
        "tanggal": d.isoformat() if d else None,
        "status": status,
        "luas": luas,
        "points": points,
        "kawasan_id": guess_kawasan(text, kawasan_list) if kawasan_list else None,
        **fields,
    }
