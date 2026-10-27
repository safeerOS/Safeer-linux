"""Lasten pogon Usenet, korak 1 (25. 10. 2026): varna razclenitev NZB (XXE, meje, imena, message-id).

Skupna pravila z Androidom so v tests/skupni-primeri/usenet-pogon.json; tu so meje (z zmanjsanimi konstantami),
napadi, ki bi brali datoteke, in nakljucno preverjanje imen in message-id.
"""
import os
import random
import tempfile
import unittest
from unittest import mock

from core import usenet_nzb as NZ, usenet_pravila as U


def nzb(datotek=1, segmentov=1, predpona=""):
    deli = []
    for d in range(datotek):
        seg = "".join('<segment bytes="10" number="%d">s%d.%d@primer.invalid</segment>' % (s + 1, d, s)
                      for s in range(segmentov))
        deli.append('<file subject="&quot;f%d.mkv&quot; yEnc (1/%d)"><segments>%s</segments></file>'
                    % (d, segmentov, seg))
    return (predpona + "<nzb>" + "".join(deli) + "</nzb>").encode()


class Nzb(unittest.TestCase):
    def izid(self, podatki):
        try:
            NZ.razcleni(podatki)
        except NZ.NapakaNzb as e:
            return e.izid
        return NZ.OK

    def test_xxe_ne_prebere_datoteke(self):
        with tempfile.TemporaryDirectory() as mapa:
            pot = os.path.join(mapa, "skrivnost.txt")
            with open(pot, "w") as f:
                f.write("SKRIVNOST-LASTNIKA")
            for xml in ('<!DOCTYPE nzb [<!ENTITY x SYSTEM "file://%s">]><nzb><file subject="&x;"><segments>'
                        '<segment number="1">a@primer.invalid</segment></segments></file></nzb>' % pot,
                        '<!DOCTYPE nzb SYSTEM "file://%s"><nzb><file subject="a.mkv"><segments>'
                        '<segment number="1">a@primer.invalid</segment></segments></file></nzb>' % pot):
                try:
                    n = NZ.razcleni(xml.encode())
                    besedilo = repr(n) + "".join(str(d.ime) for d in n.datoteke)
                except NZ.NapakaNzb as e:
                    besedilo = str(e)
                self.assertNotIn("SKRIVNOST", besedilo)

    def test_dogodki_ob_koncu_niso_izgubljeni(self):
        # Grok 37 C5: expat >= 2.6 odlozi delni zeton - dogodki pridejo sele ob flush()/close(). Po 7 znakov.
        xml = ('<nzb><file subject="a.mkv"><segments><segment bytes="1" number="1">a@primer.invalid</segment>'
               '</segments></file><file subject="b.mkv"><segments><segment bytes="1" number="1">b@primer.invalid'
               '</segment></segments></file></nzb>')
        for kos in (7, 13, 64):
            with mock.patch.object(NZ, "_KOS", kos):
                self.assertEqual([d.ime for d in NZ.razcleni(xml.encode()).datoteke], ["a.mkv", "b.mkv"], kos)

    def test_meje_stevila(self):
        self.assertEqual(self.izid(nzb(4, 2)), NZ.OK)
        with mock.patch.object(NZ, "NAJVEC_DATOTEK", 3):
            self.assertEqual(self.izid(nzb(4, 2)), NZ.PREVELIK)
        with mock.patch.object(NZ, "NAJVEC_SEGMENTOV", 7):
            self.assertEqual(self.izid(nzb(4, 2)), NZ.PREVELIK)
        with mock.patch.object(NZ, "NAJVEC_ELEMENTOV", 100):
            self.assertEqual(self.izid(b"<nzb>" + b"<x/>" * 200 + b"</nzb>"), NZ.PREVELIK)

    def test_meja_velikosti(self):
        self.assertEqual(self.izid(nzb() + b" " * (U.NAJVEC_NZB_BAJTOV - len(nzb()))), NZ.OK)
        self.assertEqual(self.izid(nzb() + b" " * (U.NAJVEC_NZB_BAJTOV - len(nzb()) + 1)), NZ.PREVELIK)

    def test_veliko_datotek_sproti(self):
        n = NZ.razcleni(nzb(2000, 3))
        self.assertEqual(len(n.datoteke), 2000)
        self.assertEqual(n.datoteke[1999].ime, "f1999.mkv")
        self.assertEqual([s.stevilka for s in n.datoteke[5].segmenti], [1, 2, 3])

    def test_repr_brez_id_in_gesla(self):
        n = NZ.razcleni(b'<nzb><head><meta type="password">GESLO-ARHIVA</meta></head><file subject="a.mkv"><segments>'
                        b'<segment number="1" bytes="5">tajni-id-9@primer.invalid</segment></segments></file></nzb>')
        self.assertTrue(n.ima_geslo)
        self.assertEqual(n.geslo, "GESLO-ARHIVA")
        besedilo = repr(n) + repr(n.datoteke) + repr(n.datoteke[0].segmenti)
        self.assertNotIn("GESLO-ARHIVA", besedilo)
        self.assertNotIn("tajni-id", besedilo)

    def test_varno_ime_nakljucno(self):
        r = random.Random(3)
        abeceda = "ab./\\..: \t\x00<>|?*\"\u010d\U0001F3AC-_"
        for _ in range(3000):
            s = "".join(r.choice(abeceda) for _ in range(r.randrange(0, 30)))
            ime = NZ.varno_ime(s)
            if ime is None:
                continue
            self.assertNotIn("/", ime)
            self.assertNotIn("\\", ime)
            self.assertNotIn(ime, (".", ".."))
            self.assertFalse(ime.endswith((".", " ")) or ime.startswith(" "))
            self.assertFalse(any(z in ime for z in '<>:"|?*\x00\t'))
            self.assertLessEqual(len(ime), NZ.NAJVEC_IME_ZNAKOV + 1)

    def test_id_nikoli_ukaza(self):
        r = random.Random(5)
        abeceda = "a@.<> \r\n\t\x00\u010d-$"
        for _ in range(3000):
            mid = NZ.id_clanka("".join(r.choice(abeceda) for _ in range(r.randrange(0, 20))))
            if mid is not None:
                self.assertTrue(all("\x21" <= z <= "\x7e" and z not in "<>" for z in mid), repr(mid))


if __name__ == "__main__":
    unittest.main()
