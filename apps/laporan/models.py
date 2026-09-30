import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.kawasan.models import Kawasan

from .constants import Status


class Laporan(models.Model):
    """Satu baris = satu titik koordinat pada satu tanggal untuk satu kawasan
    (sama dengan struktur tabel `reports` pada aplikasi lama)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legacy_id = models.BigIntegerField("ID lama (Supabase)", null=True, blank=True, db_index=True)

    tanggal = models.DateField(db_index=True)
    kawasan = models.ForeignKey(Kawasan, on_delete=models.PROTECT, related_name="laporan")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.UPAYA, db_index=True)
    lat = models.FloatField("Lintang", validators=[MinValueValidator(-90), MaxValueValidator(90)])
    lon = models.FloatField("Bujur", validators=[MinValueValidator(-180), MaxValueValidator(180)])
    luas = models.DecimalField("Luas terbakar (ha)", max_digits=12, decimal_places=2, default=0,
                               validators=[MinValueValidator(0)])

    upaya = models.TextField(blank=True)
    rencana = models.TextField("Rencana tindak lanjut", blank=True)
    personel = models.CharField("Jumlah personel", max_length=500, blank=True)
    kendala = models.TextField(blank=True)
    kebutuhan = models.TextField("Kebutuhan / saran", blank=True)
    laporan = models.TextField("Narasi laporan", blank=True)
    gakkum = models.TextField("Penegakan hukum (Gakkum)", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+", editable=False)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+", editable=False)

    class Meta:
        verbose_name = "laporan"
        verbose_name_plural = "laporan"
        ordering = ["-tanggal", "-updated_at"]
        indexes = [
            models.Index(fields=["kawasan", "tanggal"]),
            models.Index(fields=["tanggal", "status"]),
        ]

    def __str__(self):
        return f"{self.tanggal} · {self.kawasan.nkws} · {self.status}"
