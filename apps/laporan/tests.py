import json
from datetime import date, datetime, timedelta, timezone as dt_tz

from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.kawasan.tests import make_kawasan

from . import services
from .constants import Status
from .models import Laporan
from .parser import assign_lat_lon, normalize_status, parse_report_text

D = date(2026, 9, 10)


def row(kid, day, status, n=0, nkws=None):
    return services.Row(id=f"{kid}-{day}-{n}", tanggal=D + timedelta(days=day),
                        stamp=datetime(2026, 9, 1, 0, 0, n, tzinfo=dt_tz.utc), kawasan_id=kid,
                        npulau="KALIMANTAN", nupt="UPT", nkws=nkws or f"K{kid}", status=status,
                        lat=-2.0, lon=110.0, luas=1.0)


class ChainAndStatsTests(TestCase):
    def test_terminal_closes_chain_and_reopens(self):
        rows = [row(1, 0, Status.UPAYA), row(1, 1, Status.PADAM), row(1, 5, Status.UPAYA), row(1, 6, Status.UPAYA)]
        chains = services.build_chains(rows)
        self.assertEqual([c.classification for c in chains], ["sudah_padam", "upaya_aktif"])
        s = services.card_stats(rows)
        self.assertEqual((s["total_kejadian"], s["sudah_padam"], s["upaya_aktif"]), (2, 1, 1))
        self.assertEqual(s["persen_padam"], 50)

    def test_false_hotspot_not_counted_as_incident(self):
        rows = [row(1, 0, Status.KONFIRMASI), row(1, 1, Status.FALSE_HOTSPOT)]
        s = services.card_stats(rows)
        self.assertEqual((s["total_kejadian"], s["false_hotspot"]), (0, 1))

    def test_pending_categories(self):
        rows = [row(1, 0, Status.GROUNDCHECK), row(2, 0, Status.KONFIRMASI)]
        s = services.card_stats(rows)
        self.assertEqual((s["groundcheck_pending"], s["konfirmasi_pending"], s["pending_verifikasi"]), (1, 1, 2))

    def test_affected_kawasan_unique(self):
        rows = [row(1, 0, Status.UPAYA), row(1, 1, Status.PADAM), row(2, 0, Status.GROUNDCHECK), row(3, 0, Status.PADAM)]
        self.assertEqual(services.affected_kawasan_count(rows), 2)

    def test_order_independent_of_input_order(self):
        rows = [row(1, 1, Status.PADAM), row(1, 0, Status.UPAYA)]
        self.assertEqual(services.card_stats(rows)["sudah_padam"], 1)


class ActiveExtinctionTests(TestCase):
    def test_wave_counts_groundcheck_before_upaya(self):
        rows = [row(1, 0, Status.KONFIRMASI), row(1, 1, Status.GROUNDCHECK), row(1, 3, Status.UPAYA)]
        [a] = services.active_extinction(rows)
        self.assertEqual(a["sejak_tanggal"], D)
        self.assertEqual(a["jumlah_hari"], 4)
        self.assertEqual(a["jumlah_upaya"], 1)

    def test_padam_after_upaya_not_active(self):
        self.assertEqual(services.active_extinction([row(1, 0, Status.UPAYA), row(1, 1, Status.PADAM)]), [])

    def test_no_upaya_no_active(self):
        self.assertEqual(services.active_extinction([row(1, 0, Status.GROUNDCHECK)]), [])

    def test_new_wave_after_terminal_restarts_duration(self):
        rows = [row(1, 0, Status.UPAYA), row(1, 1, Status.PADAM), row(1, 4, Status.UPAYA), row(1, 5, Status.UPAYA)]
        [a] = services.active_extinction(rows)
        self.assertEqual(a["sejak_tanggal"], D + timedelta(days=4))
        self.assertEqual(a["jumlah_hari"], 2)

    def test_reference_date_extends_duration_and_sorting(self):
        rows = [row(1, 0, Status.UPAYA), row(2, 3, Status.UPAYA)]
        res = services.active_extinction(rows, reference_date=D + timedelta(days=5))
        self.assertEqual([r["kawasan_id"] for r in res], [1, 2])
        self.assertEqual([r["jumlah_hari"] for r in res], [6, 3])


class PendingUpdateTests(TestCase):
    def test_late_days_and_terminal_excluded(self):
        rows = [row(1, 0, Status.UPAYA), row(2, 0, Status.PADAM), row(3, 4, Status.GROUNDCHECK)]
        res = services.pending_updates(rows, D + timedelta(days=5))
        self.assertEqual([(r["kawasan_id"], r["jumlah_hari_terlambat"]) for r in res], [(1, 5), (3, 1)])

    def test_same_day_not_late(self):
        self.assertEqual(services.pending_updates([row(1, 5, Status.UPAYA)], D + timedelta(days=5)), [])

    def test_minimum_days_late(self):
        rows = [row(1, 4, Status.UPAYA)]
        self.assertEqual(len(services.pending_updates(rows, D + timedelta(days=5), 2)), 0)
        self.assertEqual(len(services.pending_updates(rows, D + timedelta(days=6), 2)), 1)


class MatrixTests(TestCase):
    def test_window_groups_and_last_report_per_day(self):
        today = D + timedelta(days=5)
        rows = [row(1, 4, Status.UPAYA, n=1), row(1, 4, Status.PADAM, n=2), row(2, 5, Status.KONFIRMASI)]
        m = services.build_matrix(rows, today, window=14)
        self.assertEqual(len(m["dates"]), 14)
        self.assertEqual(m["groups"][0]["npulau"], "KALIMANTAN")
        k1 = next(i for i in m["groups"][0]["items"] if i["kawasan_id"] == 1)
        cell = next(c for c in k1["cells"] if c["date"] == D + timedelta(days=4))
        self.assertEqual((cell["status"], cell["count"]), (Status.PADAM, 2))
        k2 = next(i for i in m["groups"][0]["items"] if i["kawasan_id"] == 2)
        self.assertEqual(next(c for c in k2["cells"] if c["date"] == today)["symbol"], "!")

    def test_navigation(self):
        today = D + timedelta(days=5)
        m = services.build_matrix([row(1, -60, Status.UPAYA)], today, window=14)
        self.assertIn(today, m["dates"])
        self.assertIsNotNone(m["prev_start"])
        m2 = services.build_matrix([row(1, -60, Status.UPAYA)], today, start=m["prev_start"], window=14)
        self.assertLess(m2["start"], m["start"])

    def test_empty(self):
        m = services.build_matrix([], date(2026, 9, 30), window=14)
        self.assertEqual(m["groups"], [])
        self.assertEqual(len(m["dates"]), 14)


class ParserTests(TestCase):
    TEXT = ("Sabtu, 26 September 2026\nLokasi: TN Sebangau, BKSDA Kalteng\nKoordinat: X: -2.321 | Y: 113.921\n"
            "Status: Upaya Pemadaman\nLuas terbakar: 12,5 Ha\nPersonel: 8 Manggala Agni dan 12 MPA\n"
            "Upaya: pemadaman darat dan sekat bakar\nRencana tindak lanjut: patroli ulang besok\nKendala: akses berlumpur")

    def test_full_text(self):
        r = parse_report_text(self.TEXT, [(1, "TN Sebangau"), (2, "TN Baluran")])
        self.assertEqual(r["tanggal"], "2026-09-26")
        self.assertEqual(r["status"], Status.UPAYA)
        self.assertEqual(r["luas"], 12.5)
        self.assertEqual(r["points"][0]["lat"], -2.321)
        self.assertEqual(r["points"][0]["lon"], 113.921)
        self.assertEqual(r["kawasan_id"], 1)
        self.assertIn("8 Manggala Agni", r["personel"])
        self.assertIn("sekat bakar", r["upaya"])
        self.assertEqual(r["rencana"], "patroli ulang besok")
        self.assertEqual(r["kendala"], "akses berlumpur")

    def test_swapped_coordinates_detected(self):
        r = parse_report_text("Koordinat: 113.921, -2.321")
        self.assertEqual((r["points"][0]["lat"], r["points"][0]["lon"]), (-2.321, 113.921))

    def test_multiple_points_and_dedupe(self):
        r = parse_report_text("Titik 1: -2.321, 113.921\nTitik 2: -2.400, 113.950\nUlang: -2.321, 113.921")
        self.assertEqual(len(r["points"]), 2)

    def test_low_precision_numbers_are_not_coordinates(self):
        self.assertEqual(parse_report_text("luas 5.5 ha, 100.5 personel")["points"], [])

    def test_out_of_indonesia_ignored(self):
        self.assertEqual(parse_report_text("Koordinat: 40.7128, -74.0060")["points"], [])
        self.assertIsNone(assign_lat_lon(40.7, -74.0))

    def test_status_variants(self):
        self.assertEqual(normalize_status("api sudah padam"), Status.PADAM)
        self.assertEqual(normalize_status("false hotspot"), Status.FALSE_HOTSPOT)
        self.assertEqual(normalize_status("proses ground check"), Status.GROUNDCHECK)
        self.assertEqual(normalize_status("perlu konfirmasi"), Status.KONFIRMASI)
        self.assertEqual(normalize_status(""), Status.UPAYA)

    def test_numeric_date_and_no_kawasan_ambiguity(self):
        self.assertEqual(parse_report_text("tgl 05/09/2026")["tanggal"], "2026-09-05")
        r = parse_report_text("di TN X Barat", [(1, "TN X"), (2, "TN X Barat")])
        self.assertEqual(r["kawasan_id"], 2)


class ViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.k = make_kawasan("TN A", "BKSDA X", box=(110, -3, 111, -2))
        call_command("setup_roles", verbosity=0)
        cls.viewer = User.objects.create_user("viewer", password="pw12345678")
        cls.op = User.objects.create_user("op", password="pw12345678")
        cls.op.groups.add(Group.objects.get(name="Operator Laporan"))
        cls.mgr = User.objects.create_user("mgr", password="pw12345678")
        cls.mgr.groups.add(Group.objects.get(name="Pengelola Laporan"))

    def payload(self, **kw):
        d = {"tanggal": "2026-09-10", "kawasan": self.k.id, "upaya": "x", "rencana": "", "personel": "5",
             "kendala": "", "kebutuhan": "", "gakkum": "", "laporan": "narasi",
             "pt-TOTAL_FORMS": "1", "pt-INITIAL_FORMS": "0", "pt-MIN_NUM_FORMS": "1", "pt-MAX_NUM_FORMS": "1000",
             "pt-0-lat": "-2.5", "pt-0-lon": "110.5", "pt-0-status": Status.UPAYA, "pt-0-luas": "3.5"}
        d.update(kw)
        return d

    def test_login_required_for_pages_and_api(self):
        for name in ("dashboard", "matriks", "peta", "hotspot", "laporan_list"):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn("/masuk/", r["Location"])
        self.assertEqual(self.client.get(reverse("api_laporan")).status_code, 401)
        self.assertEqual(self.client.get(reverse("api_hotspot")).status_code, 401)

    def test_public_read_setting(self):
        with self.settings(SIAGA_PUBLIC_READ=True):
            self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
            self.assertEqual(self.client.get(reverse("api_laporan")).status_code, 200)
            self.assertEqual(self.client.get(reverse("laporan_create")).status_code, 302)  # input tetap wajib login

    def test_all_pages_render_for_viewer(self):
        Laporan.objects.create(tanggal=date.today(), kawasan=self.k, status=Status.UPAYA, lat=-2.5, lon=110.5, luas=2)
        self.client.force_login(self.viewer)
        for name in ("dashboard", "matriks", "peta", "hotspot", "laporan_list"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.get(reverse("api_kawasan_geojson")).status_code, 200)

    def test_viewer_cannot_write(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("laporan_create")).status_code, 403)
        self.assertEqual(self.client.post(reverse("laporan_create"), self.payload()).status_code, 403)
        self.assertEqual(Laporan.objects.count(), 0)

    def test_operator_create_multi_point_and_audit(self):
        self.client.force_login(self.op)
        data = self.payload(**{"pt-TOTAL_FORMS": "2", "pt-1-lat": "-2.6", "pt-1-lon": "110.6",
                               "pt-1-status": Status.GROUNDCHECK, "pt-1-luas": "0"})
        r = self.client.post(reverse("laporan_create"), data)
        self.assertRedirects(r, reverse("matriks"))
        self.assertEqual(Laporan.objects.count(), 2)
        l = Laporan.objects.get(status=Status.UPAYA)
        self.assertEqual((l.created_by, l.kawasan), (self.op, self.k))
        self.assertEqual(float(l.luas), 3.5)

    def test_coordinate_validation(self):
        self.client.force_login(self.op)
        r = self.client.post(reverse("laporan_create"), self.payload(**{"pt-0-lat": "110.5", "pt-0-lon": "-2.5"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "tertukar")
        r = self.client.post(reverse("laporan_create"), self.payload(**{"pt-0-lat": "40.7", "pt-0-lon": "-74.0"}))
        self.assertContains(r, "luar wilayah Indonesia")
        r = self.client.post(reverse("laporan_create"), self.payload(**{"pt-0-luas": "-5"}))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Laporan.objects.count(), 0)

    def test_point_outside_kawasan_warns_but_saves(self):
        self.client.force_login(self.op)
        r = self.client.post(reverse("laporan_create"), self.payload(**{"pt-0-lat": "-5.0", "pt-0-lon": "115.0"}), follow=True)
        self.assertEqual(Laporan.objects.count(), 1)
        self.assertContains(r, "berada di luar batas kawasan")

    def test_update_extra_point_becomes_new_row(self):
        l = Laporan.objects.create(tanggal=D, kawasan=self.k, status=Status.UPAYA, lat=-2.5, lon=110.5, luas=1)
        self.client.force_login(self.op)
        data = self.payload(**{"pt-TOTAL_FORMS": "2", "pt-INITIAL_FORMS": "1", "pt-0-status": Status.PADAM,
                               "pt-1-lat": "-2.7", "pt-1-lon": "110.7", "pt-1-status": Status.UPAYA, "pt-1-luas": "1"})
        self.client.post(reverse("laporan_update", args=[l.id]), data)
        l.refresh_from_db()
        self.assertEqual(l.status, Status.PADAM)
        self.assertEqual(l.updated_by, self.op)
        self.assertEqual(Laporan.objects.count(), 2)

    def test_delete_requires_permission(self):
        l = Laporan.objects.create(tanggal=D, kawasan=self.k, status=Status.UPAYA, lat=-2.5, lon=110.5, luas=1)
        self.client.force_login(self.op)
        self.assertEqual(self.client.post(reverse("laporan_delete", args=[l.id])).status_code, 403)
        self.assertEqual(self.client.get(reverse("laporan_delete", args=[l.id])).status_code, 403)
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("laporan_delete", args=[l.id])).status_code, 405)  # GET tidak boleh menghapus
        r = self.client.post(reverse("laporan_delete", args=[l.id]), headers={"accept": "application/json"})
        self.assertEqual(r.json(), {"deleted": str(l.id)})
        self.assertEqual(Laporan.objects.count(), 0)

    def test_open_redirect_blocked_on_delete(self):
        l = Laporan.objects.create(tanggal=D, kawasan=self.k, status=Status.UPAYA, lat=-2.5, lon=110.5, luas=1)
        self.client.force_login(self.mgr)
        r = self.client.post(reverse("laporan_delete", args=[l.id]), {"next": "https://evil.example/"})
        self.assertRedirects(r, reverse("laporan_list"))

    def test_detail_api_gates_edit_links_by_permission(self):
        l = Laporan.objects.create(tanggal=D, kawasan=self.k, status=Status.UPAYA, lat=-2.5, lon=110.5, luas=1, laporan="<b>x</b>")
        url = f"{reverse('api_laporan_detail')}?kawasan={self.k.id}&tanggal={D}"
        self.client.force_login(self.viewer)
        [r] = self.client.get(url).json()["results"]
        self.assertIsNone(r["edit_url"])
        self.assertIsNone(r["delete_url"])
        self.client.force_login(self.mgr)
        [r] = self.client.get(url).json()["results"]
        self.assertTrue(r["edit_url"] and r["delete_url"])
        self.assertEqual(self.client.get(reverse("api_laporan_detail")).status_code, 400)

    def test_api_filters(self):
        k2 = make_kawasan("TN B", "BKSDA Y", box=(120, 0, 121, 1))
        Laporan.objects.create(tanggal=D, kawasan=self.k, status=Status.UPAYA, lat=-2.5, lon=110.5, luas=1)
        Laporan.objects.create(tanggal=D, kawasan=k2, status=Status.PADAM, lat=.5, lon=120.5, luas=1)
        self.client.force_login(self.viewer)
        n = lambda q: len(self.client.get(reverse("api_laporan") + q).json()["results"])
        self.assertEqual((n(""), n("?upt=BKSDA Y"), n(f"?kawasan={self.k.id}"), n("?status=Sudah Padam"), n("?tanggal=2030-01-01")), (2, 1, 1, 1, 0))

    def test_parse_endpoint(self):
        self.client.force_login(self.op)
        r = self.client.post(reverse("laporan_parse"), json.dumps({"text": "TN A\n-2.512345, 110.512345\n5 ha"}), content_type="application/json")
        j = r.json()
        self.assertEqual((j["kawasan_id"], j["luas"], len(j["points"])), (self.k.id, 5.0, 1))
        self.assertEqual(self.client.post(reverse("laporan_parse"), "{bad", content_type="application/json").status_code, 400)

    def test_dashboard_shows_computed_numbers(self):
        today = date.today()
        Laporan.objects.create(tanggal=today - timedelta(days=2), kawasan=self.k, status=Status.UPAYA, lat=-2.5, lon=110.5, luas=1)
        self.client.force_login(self.viewer)
        c = self.client.get(reverse("dashboard")).context
        self.assertEqual(len(c["active"]), 1)
        self.assertEqual(len(c["pending"]), 1)
        self.assertEqual(c["pending"][0]["jumlah_hari_terlambat"], 2)


class ImportSupabaseTests(TestCase):
    HEADER = "report_uuid,id,tanggal,npulau,nupt,nkws,status,lat,lon,luas,upaya,rencana,personel,kendala,kebutuhan,laporan,kawasan_id,gakkum,created_at,updated_at\n"

    def _csv(self, body):
        import tempfile
        f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        f.write(self.HEADER + body)
        f.close()
        self.addCleanup(__import__("os").unlink, f.name)
        return f.name

    def _run(self, path, *extra):
        import os
        import tempfile
        skip = os.path.join(tempfile.mkdtemp(), "skip.csv")
        call_command("import_supabase", path, "--skipped-out", skip, *extra, verbosity=0)

    def setUp(self):
        self.k = make_kawasan("TN A", "BKSDA X")

    def test_import_is_idempotent_even_without_uuid(self):
        path = self._csv(",7,2026-09-02,KALIMANTAN,bksda x,tn a,sudah padam,-2.5,110.5,\"4,5\",,,,,,n,,,2026-09-02T03:00:00+00:00,2026-09-02T03:00:00+00:00\n")
        self._run(path)
        self._run(path)
        [l] = Laporan.objects.all()
        self.assertEqual((l.legacy_id, l.status, float(l.luas), l.kawasan), (7, Status.PADAM, 4.5, self.k))
        self.assertEqual(l.created_at.isoformat(), "2026-09-02T03:00:00+00:00", "cap waktu asli dipertahankan")

    def test_same_name_other_upt_is_not_silently_matched(self):
        path = self._csv(",8,2026-09-02,KALIMANTAN,BKSDA LAIN,TN A,Upaya Pemadaman,-2.5,110.5,1,,,,,,n,,,,\n")
        self._run(path)
        self.assertEqual(Laporan.objects.count(), 0)
        self._run(path, "--match-nkws-only")
        self.assertEqual(Laporan.objects.count(), 1)

    def test_invalid_rows_skipped_without_aborting(self):
        path = self._csv(",9,rusak,KALIMANTAN,BKSDA X,TN A,Upaya Pemadaman,-2.5,110.5,1,,,,,,n,,,,\n"
                         ",10,2026-09-03,KALIMANTAN,BKSDA X,TN A,Upaya Pemadaman,-2.5,110.5,1,,,,,,n,,,,\n")
        self._run(path)
        self.assertEqual(list(Laporan.objects.values_list("legacy_id", flat=True)), [10])
