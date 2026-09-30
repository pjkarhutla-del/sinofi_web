from django.contrib import admin

from .models import Kawasan


@admin.register(Kawasan)
class KawasanAdmin(admin.ModelAdmin):
    list_display = ("nkws", "nupt", "npulau", "has_geometry", "updated_at")
    list_filter = ("npulau", "nupt")
    search_fields = ("nkws", "nupt")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(boolean=True, description="Batas wilayah")
    def has_geometry(self, obj):
        return obj.has_geometry
