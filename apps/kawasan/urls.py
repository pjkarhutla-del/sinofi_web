from django.urls import path

from . import views

urlpatterns = [
    path("api/kawasan/geojson/", views.kawasan_geojson, name="api_kawasan_geojson"),
]
