from django.db import models

from .utils import PULAU_LIST


class Pulau(models.TextChoices):
    SUMATERA = "SUMATERA", "Sumatera"
    KALIMANTAN = "KALIMANTAN", "Kalimantan"
    JAWA = "JAWA", "Jawa"
    BALI_NUSRA = "BALI NUSRA", "Bali Nusra"
    SULAWESI = "SULAWESI", "Sulawesi"
    MALUKU = "MALUKU", "Maluku"
    PAPUA = "PAPUA", "Papua"


class Kawasan(models.Model):
    """Master kawasan konservasi (NKWS) beserta UPT pengelola (NUPT) dan batas wilayahnya."""

    objectid = models.IntegerField("OBJECTID sumber", null=True, blank=True, db_index=True)
    npulau = models.CharField("Pulau", max_length=20, choices=Pulau.choices, db_index=True)
    nupt = models.CharField("UPT", max_length=255, db_index=True)
    nkws = models.CharField("Kawasan", max_length=255)

    # Geometri GeoJSON (2D, EPSG:4326). geom = resolusi penuh (untuk analisis spasial),
    # geom_simplified = disederhanakan untuk ditampilkan di peta web.
    geom = models.JSONField(null=True, blank=True, editable=False)
    geom_simplified = models.JSONField(null=True, blank=True, editable=False)
    min_lon = models.FloatField(null=True, blank=True, editable=False)
    min_lat = models.FloatField(null=True, blank=True, editable=False)
    max_lon = models.FloatField(null=True, blank=True, editable=False)
    max_lat = models.FloatField(null=True, blank=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "kawasan"
        verbose_name_plural = "kawasan"
        ordering = ["npulau", "nupt", "nkws"]
        constraints = [
            models.UniqueConstraint(fields=["nupt", "nkws"], name="uniq_kawasan_nupt_nkws"),
        ]

    def __str__(self):
        return f"{self.nkws} — {self.nupt}"

    @property
    def has_geometry(self):
        return bool(self.geom)


PULAU_ORDER = {name: i for i, name in enumerate(PULAU_LIST)}
