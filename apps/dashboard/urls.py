from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("matriks/", views.matriks, name="matriks"),
    path("peta/", views.peta, name="peta"),
    path("hotspot/", views.hotspot_monitor, name="hotspot"),
]
