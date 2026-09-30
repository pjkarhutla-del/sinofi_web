from django.contrib import admin

from .models import Hotspot, HotspotSyncLog


@admin.register(Hotspot)
class HotspotAdmin(admin.ModelAdmin):
    list_display = ("hs_id", "tanggal", "confidence", "satelit", "kawasan", "lat", "lon")
    list_filter = ("confidence", "satelit", "tanggal")
    search_fields = ("hs_id", "kawasan__nkws", "kawasan__nupt")
    list_select_related = ("kawasan",)
    date_hierarchy = "tanggal"


@admin.register(HotspotSyncLog)
class HotspotSyncLogAdmin(admin.ModelAdmin):
    list_display = ("started_at", "date_from", "date_to", "fetched", "stored", "inside_kawasan", "success")
    readonly_fields = [f.name for f in HotspotSyncLog._meta.fields]
