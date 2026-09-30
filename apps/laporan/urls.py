from django.urls import path

from . import views

urlpatterns = [
    path("laporan/", views.laporan_list, name="laporan_list"),
    path("laporan/baru/", views.laporan_create, name="laporan_create"),
    path("laporan/parse/", views.laporan_parse, name="laporan_parse"),
    path("laporan/<uuid:pk>/ubah/", views.laporan_update, name="laporan_update"),
    path("laporan/<uuid:pk>/hapus/", views.laporan_delete, name="laporan_delete"),
    path("api/laporan/", views.api_laporan, name="api_laporan"),
    path("api/laporan/detail/", views.api_laporan_detail, name="api_laporan_detail"),
]
