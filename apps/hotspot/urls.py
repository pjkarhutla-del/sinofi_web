from django.urls import path

from . import views

urlpatterns = [
    path("api/hotspot/", views.api_hotspot, name="api_hotspot"),
    path("api/hotspot/stats/", views.api_hotspot_stats, name="api_hotspot_stats"),
    path("hotspot/sinkron/", views.hotspot_sync, name="hotspot_sync"),
    path("hotspot/ekspor/<str:fmt>/", views.hotspot_export, name="hotspot_export"),
]
