from django.contrib import admin

from .models import Laporan


@admin.register(Laporan)
class LaporanAdmin(admin.ModelAdmin):
    list_display = ("tanggal", "kawasan", "status", "luas", "lat", "lon", "updated_at")
    list_filter = ("status", "tanggal", "kawasan__npulau", "kawasan__nupt")
    search_fields = ("kawasan__nkws", "kawasan__nupt", "laporan")
    date_hierarchy = "tanggal"
    autocomplete_fields = ("kawasan",)
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by", "legacy_id")
    list_select_related = ("kawasan",)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
