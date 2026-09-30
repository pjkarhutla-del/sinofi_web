from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

ROLES = {
    "Operator Laporan": ["add_laporan", "change_laporan"],
    "Pengelola Laporan": ["add_laporan", "change_laporan", "delete_laporan"],
}


class Command(BaseCommand):
    help = "Buat grup peran: Operator Laporan (tambah/ubah) dan Pengelola Laporan (tambah/ubah/hapus)."

    def handle(self, *args, **opts):
        for name, codenames in ROLES.items():
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.set(Permission.objects.filter(content_type__app_label="laporan", codename__in=codenames))
            self.stdout.write(self.style.SUCCESS(f"Grup '{name}': {', '.join(codenames)}"))
        self.stdout.write("Baca (dashboard/matriks/peta) cukup dengan login; tambahkan pengguna ke grup lewat /admin/.")
