from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

admin.site.site_header = "SIAGA Karhutla — Administrasi"
admin.site.site_title = "SIAGA Karhutla"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("masuk/", auth_views.LoginView.as_view(), name="login"),
    path("keluar/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("apps.dashboard.urls")),
    path("", include("apps.laporan.urls")),
    path("", include("apps.hotspot.urls")),
    path("", include("apps.kawasan.urls")),
]
