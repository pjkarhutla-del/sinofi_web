from django.db import models

from apps.kawasan.models import Kawasan


class Confidence(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"


class Hotspot(models.Model):
    """Titik panas dari API SIPONGI yang disimpan lokal dan dicocokkan dengan batas kawasan."""

    hs_id = models.CharField("ID hotspot", max_length=120, unique=True)
    tanggal = models.DateField(db_index=True)
    waktu = models.CharField("Waktu (mentah dari API)", max_length=60, blank=True)
    confidence = models.CharField(max_length=10, choices=Confidence.choices, db_index=True)
    satelit = models.CharField(max_length=60, blank=True)
    lat = models.FloatField()
    lon = models.FloatField()
    kawasan = models.ForeignKey(Kawasan, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="hotspots")
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-tanggal", "-id"]
        indexes = [
            models.Index(fields=["tanggal", "confidence"]),
            models.Index(fields=["kawasan", "tanggal"]),
        ]

    def __str__(self):
        return f"{self.hs_id} ({self.confidence})"


class HotspotSyncLog(models.Model):
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    fetched = models.PositiveIntegerField(default=0)
    stored = models.PositiveIntegerField(default=0)
    inside_kawasan = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=False)
    message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.started_at:%Y-%m-%d %H:%M} — {'OK' if self.success else 'GAGAL'}"
