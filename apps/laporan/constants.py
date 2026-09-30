"""Status laporan beserta warna/ikon yang konsisten di kartu, matriks, peta, dan formulir."""
from django.db import models


class Status(models.TextChoices):
    UPAYA = "Upaya Pemadaman", "Upaya Pemadaman"
    GROUNDCHECK = "Proses Groundcheck", "Proses Groundcheck"
    PADAM = "Sudah Padam", "Sudah Padam"
    KONFIRMASI = "Perlu Konfirmasi", "Perlu Konfirmasi"
    FALSE_HOTSPOT = "False Hotspot", "False Hotspot"


STATUS_META = {
    Status.UPAYA.value: {"css": "status-upaya", "badge": "bg-red-600", "icon": "♨", "color": "#dc2626"},
    Status.GROUNDCHECK.value: {"css": "status-groundcheck", "badge": "bg-amber-500", "icon": "⌖", "color": "#eab308"},
    Status.PADAM.value: {"css": "status-padam", "badge": "bg-blue-600", "icon": "✓", "color": "#2563eb"},
    Status.KONFIRMASI.value: {"css": "status-konfirmasi", "badge": "bg-purple-600", "icon": "!", "color": "#9333ea"},
    Status.FALSE_HOTSPOT.value: {"css": "status-false", "badge": "bg-gray-600", "icon": "×", "color": "#6b7280"},
}

OPEN_STATUSES = {Status.GROUNDCHECK.value, Status.UPAYA.value, Status.KONFIRMASI.value}
TERMINAL_STATUSES = {Status.PADAM.value, Status.FALSE_HOTSPOT.value}

# Batas wajar koordinat Indonesia (untuk validasi input & deteksi lat/lon tertukar)
LAT_RANGE = (-11.5, 6.5)
LON_RANGE = (94.0, 141.5)
