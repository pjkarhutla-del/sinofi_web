from django.test import TestCase

from .models import Kawasan
from .spatial import KawasanIndex, get_index
from .utils import canonical_pulau


def square(x0, y0, x1, y1):
    return {"type": "MultiPolygon", "coordinates": [[[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]]}


def make_kawasan(nkws="TN A", nupt="BKSDA X", pulau="KALIMANTAN", box=(110, -3, 111, -2), objectid=None):
    return Kawasan.objects.create(nkws=nkws, nupt=nupt, npulau=pulau, objectid=objectid, geom=square(*box))


class CanonicalPulauTests(TestCase):
    def test_variants(self):
        self.assertEqual(canonical_pulau("Kalimantan"), "KALIMANTAN")
        self.assertEqual(canonical_pulau("bali-nusra"), "BALI NUSRA")
        self.assertEqual(canonical_pulau("Papua Barat"), "PAPUA")
        self.assertEqual(canonical_pulau("Maluku"), "MALUKU")
        self.assertEqual(canonical_pulau("Sumatera"), "SUMATERA")
        self.assertEqual(canonical_pulau(""), "LAINNYA")


class SpatialTests(TestCase):
    def test_locate_inside_outside_and_boundary(self):
        idx = KawasanIndex([(1, square(110, -3, 111, -2)), (2, square(120, 0, 121, 1))])
        self.assertEqual(idx.locate(110.5, -2.5), 1)
        self.assertEqual(idx.locate(120.5, 0.5), 2)
        self.assertIsNone(idx.locate(115, -1))
        self.assertEqual(idx.locate(110, -2.5), 1, "titik di batas dianggap di dalam")

    def test_overlap_prefers_first(self):
        idx = KawasanIndex([(7, square(0, 0, 2, 2)), (8, square(1, 1, 3, 3))])
        self.assertEqual(idx.locate(1.5, 1.5), 7)

    def test_locate_many_empty_and_covers(self):
        self.assertEqual(KawasanIndex([]).locate_many([(1, 1)]), [None])
        idx = KawasanIndex([(1, square(0, 0, 1, 1))])
        self.assertEqual(idx.locate_many([]), [])
        self.assertTrue(idx.covers(1, .5, .5))
        self.assertFalse(idx.covers(1, 5, 5))
        self.assertIsNone(idx.covers(99, .5, .5))

    def test_get_index_rebuilds_after_change(self):
        k = make_kawasan(box=(110, -3, 111, -2))
        self.assertEqual(get_index().locate(110.5, -2.5), k.id)
        k.geom = square(130, -3, 131, -2)
        k.save()
        self.assertIsNone(get_index().locate(110.5, -2.5))
        self.assertEqual(get_index().locate(130.5, -2.5), k.id)
