"""Filter vira Usenet - primeri 1:1 iz Androidovega tests/FilterViraPravilaTest.kt (TV je vzorec, lastnik 10. 11. 2026).

Vsak preveriEnako iz Kotlina je tu ena trditev z istim opisom in istimi podatki; TV Zmoznosti() so zapisane izrecno
(namizje z libmpv privzeto zna vse dekodirnike, TV pa ne). Ce se TV pravilo spremeni, mora ta datoteka slediti.
"""
import os
import sys
import unittest
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import filter_vira_pravila as F  # noqa: E402
from core import kakovost_oznake as K  # noqa: E402
from core import tok_izbira  # noqa: E402
from core.filter_vira_pravila import Izdaja, Izid, Izidi, Odgovor, Pogoj, Pogoji  # noqa: E402

#: TokIzbira.Zmoznosti() na TV: hevc da, av1/hdr/dv/eac3/ac3/dts/truehd ne, hevc10 da.
Z_TV = tok_izbira.Zmoznosti(visina=1080, hevc=True, av1=False, hdr=False, dolby_vision=False, eac3=False, ac3=False,
                            dts=False, truehd=False, hevc10=True)
MIN = 60_000
T0 = 1_000_000_000


class PogojiInIzid(unittest.TestCase):
    def setUp(self):
        self.p = Pogoji(F.VIR_USENET)
        self.z = Z_TV
        self.dobra = Izdaja("Abbott.Elementary.S01E01.1080p.WEB.h264-GRP", 1.2)
        self.racun = Izid.NA_VOLJO

    def test_primer_iz_prijave(self):
        p, z, racun, dobra = self.p, self.z, self.racun, self.dobra
        self.assertFalse(F.lahko_gleda(p, Izidi(racun, Odgovor([])), z), "debrid/torrent da, Usenet 0 zadetkov -> ni v filtru")
        self.assertEqual(F.izid(Izidi(racun, Odgovor([])), p, z), Izid.NI, "Usenet 0 zadetkov je izid NI")
        self.assertTrue(F.lahko_gleda(p, Izidi(racun, Odgovor([dobra])), z), "Usenet z ustrezno izdajo -> v filtru")

    def test_vsak_pogoj(self):
        p, z, racun, dobra = self.p, self.z, self.racun, self.dobra
        self.assertFalse(F.lahko_gleda(p, Izidi(Izid.NI, Odgovor([dobra])), z), "RACUN: ni nastavljen")
        self.assertEqual(F.izid(Izidi(Izid.NE_VEMO, Odgovor([dobra])), p, z), Izid.NE_VEMO, "RACUN: neznano")
        self.assertEqual(F.izid(Izidi(racun, Odgovor(None)), p, z), Izid.NE_VEMO, "ODGOVOR: napaka/rok -> ne vemo")
        self.assertFalse(F.lahko_gleda(p, Izidi(racun, None), z), "ODGOVOR: se ni preverjeno")
        self.assertFalse(F.lahko_gleda(p, Izidi(racun, Odgovor([replace(dobra, geslo=True)])), z), "GESLO: indeksator pove geslo")
        self.assertEqual(F.pogoji_izdaje(dobra, p, z)[Pogoj.GESLO], Izid.NA_VOLJO, "GESLO: indeksator ne pove")
        self.assertFalse(F.lahko_gleda(p, Izidi(racun, Odgovor([replace(dobra, manjka=True)])), z), "MANJKA")
        hevc10 = Izdaja("Film.2023.2160p.UHD.HDR.10bit.x265-GRP", 12.0)
        self.assertFalse(F.lahko_gleda(p, Izidi(racun, Odgovor([hevc10])), replace(z, hevc10=False)), "10-bit brez Main10")
        self.assertTrue(F.lahko_gleda(p, Izidi(racun, Odgovor([hevc10])), z), "10-bit z Main10")
        self.assertFalse(F.lahko_gleda(p, Izidi(racun, Odgovor([Izdaja("Film.2020.1080p.BluRay.TrueHD.7.1.x264", 9.0)])), z),
                         "TrueHD brez dekodirnika")
        self.assertFalse(F.lahko_gleda(p, Izidi(racun, Odgovor([Izdaja("Film.2020.COMPLETE.BLURAY-GRP", 40.0)])), z),
                         "slika diska")
        self.assertFalse(F.lahko_gleda(p, Izidi(racun, Odgovor([Izdaja("Film.2024.1080p.WEB.AV1", 2.0)])), z), "AV1 brez dekoderja")
        p_jezik = replace(p, jezik_zvoka="de")
        self.assertEqual(F.pogoji_izdaje(dobra, p_jezik, z)[Pogoj.JEZIK_ZVOKA], Izid.NE_VEMO, "JEZIK_ZVOKA: ime ne pove")
        self.assertTrue(F.lahko_gleda(p_jezik, Izidi(racun, Odgovor([Izdaja("Film.2020.German.1080p.WEB.h264", 2.0)])), z),
                        "JEZIK_ZVOKA: GERMAN")
        self.assertIsNone(F.pogoji_izdaje(dobra, p, z).get(Pogoj.JEZIK_ZVOKA), "JEZIK_ZVOKA: ni zahtevan")
        p_pod = replace(p, jezik_podnapisov="sl")
        self.assertFalse(F.lahko_gleda(p_pod, Izidi(racun, Odgovor([dobra])), z), "PODNAPISI: ime jih ne navede")
        self.assertTrue(F.lahko_gleda(p_pod, Izidi(racun, Odgovor([Izdaja("Film.2020.1080p.WEB.SLSUBS.h264", 2.0)])), z),
                        "PODNAPISI: SLSUBS")
        p_loc = replace(p, najmanj_visina=2160)
        self.assertFalse(F.lahko_gleda(p_loc, Izidi(racun, Odgovor([dobra])), z), "LOCLJIVOST: 4K proti 1080p")
        self.assertEqual(F.pogoji_izdaje(Izdaja("Film.2020.WEB.h264", 2.0), p_loc, z)[Pogoj.LOCLJIVOST], Izid.NE_VEMO)
        p_gb = replace(p, najvec_gb=15.0)
        self.assertFalse(F.lahko_gleda(p_gb, Izidi(racun, Odgovor([Izdaja("Film.2020.2160p.REMUX.x265", 60.0)])), z),
                         "VELIKOST: samo REMUX 60 GB")
        self.assertEqual(F.pogoji_izdaje(Izdaja("Film.1080p", 0.0), p_gb, z)[Pogoj.VELIKOST], Izid.NE_VEMO, "VELIKOST: neznana")
        self.assertTrue(F.lahko_gleda(p_gb, Izidi(racun, Odgovor([Izdaja("Film.2020.2160p.REMUX", 60.0), dobra])), z),
                        "AND: ena izdaja zadosca")
        self.assertFalse(F.lahko_gleda(replace(p_gb, jezik_zvoka="de"), Izidi(racun, Odgovor([
            Izdaja("Film.2020.German.2160p.REMUX", 60.0), dobra])), z), "AND: pogoja izpolnita razlicni izdaji")

    def test_znacka(self):
        p, z, dobra = self.p, self.z, self.dobra
        self.assertEqual(F.oznaka([Izdaja("Film.2020.720p.WEB.h264", 1.0)], p, z), K.Oznaka.HD)
        self.assertEqual(F.oznaka([Izdaja("Film.2020.2160p.10bit.x265", 10.0), dobra], p, replace(z, hevc10=False)),
                         K.Oznaka.FULL_HD, "neustrezna 4K izdaja ne steje")
        self.assertIsNone(F.oznaka([], p, z))


class SerijeInZapisi(unittest.TestCase):
    def test_epizoda_za_preverbo(self):
        self.assertEqual(F.epizoda_za_preverbo("tt1:2:3", "tt1:1:1"), "tt1:2:3")
        self.assertEqual(F.epizoda_za_preverbo(None, "tt1:1:1"), "tt1:1:1")
        self.assertIsNone(F.epizoda_za_preverbo("", None))

    def test_predpomnilnik_in_ponovitve(self):
        ni = F.zapisi(None, Izid.NI, None, T0)
        self.assertEqual(ni.izid, Izid.NI)
        self.assertFalse(F.vprasati(ni, T0 + 5 * 60 * MIN), "NI: 5 h ne")
        self.assertTrue(F.vprasati(ni, T0 + 6 * 60 * MIN + 1), "NI: po 6 h znova")
        napaka1 = F.zapisi(None, Izid.NE_VEMO, None, T0)
        self.assertEqual(napaka1.izid, Izid.NE_VEMO)
        self.assertFalse(F.pokazi(napaka1, T0))
        self.assertTrue(F.se_iscemo(napaka1, T0))
        self.assertFalse(F.vprasati(napaka1, T0 + MIN))
        self.assertTrue(F.vprasati(napaka1, T0 + 2 * MIN))
        napaka2 = F.zapisi(napaka1, Izid.NE_VEMO, None, T0 + 2 * MIN)
        self.assertEqual((F.vprasati(napaka2, T0 + 5 * MIN), F.vprasati(napaka2, T0 + 6 * MIN)), (False, True))
        z3 = F.zapisi(napaka2, Izid.NE_VEMO, None, T0 + 6 * MIN)
        self.assertFalse(F.vprasati(z3, T0 + 60 * MIN), "NE_VEMO 3x: konec ponovitev")
        self.assertFalse(F.se_iscemo(z3, T0 + 60 * MIN))
        self.assertTrue(F.vprasati(z3, T0 + 6 * MIN + 6 * 60 * MIN + 1))
        je = F.zapisi(None, Izid.NA_VOLJO, K.Oznaka.FULL_HD, T0)
        self.assertTrue(F.pokazi(je, T0 + MIN))
        self.assertEqual(F.zapisi(je, Izid.NE_VEMO, None, T0 + MIN), je, "NE_VEMO ne povozi svezega NA_VOLJO")
        k = F.StevecKlikov()
        k.zacni(); k.zacni()
        self.assertFalse(k.konec())
        self.assertTrue(k.konec())
        self.assertTrue(k.konec())
        self.assertTrue(F.pokazi(je, T0 + 7 * 60 * MIN), "NA_VOLJO po 7 h")
        self.assertTrue(F.pokazi(je, T0 + 30 * 24 * 60 * MIN), "NA_VOLJO po 30 dneh")
        self.assertFalse(F.pokazi(je, T0 - MIN), "iz prihodnosti")
        self.assertFalse(F.vprasati(je, T0 + 7 * 60 * MIN))
        self.assertTrue(F.vprasati(F.Zapis(Izid.NI, T0), T0 + 6 * 60 * MIN + 1))
        self.assertEqual(F.iz_niza(F.v_niz(je)), je)
        self.assertIsNone(F.iz_niza("NA_VOLJO;x;;0"))
        self.assertEqual(F.kljuc("usenet", "ab12", "series|tt1"), "usenet|ab12|series|tt1")

    def test_zakon_solidarnosti(self):
        p, z = Pogoji(F.VIR_USENET), Z_TV
        racun = Izid.NA_VOLJO
        hevc10 = Izdaja("Film.2023.2160p.UHD.HDR.10bit.x265-GRP", 12.0)
        dobra = Izdaja("Abbott.Elementary.S01E01.1080p.WEB.h264-GRP", 1.2)
        sam_pomoc = Izidi(racun, Odgovor([hevc10]))
        brez_main10 = replace(z, hevc10=False)
        self.assertFalse(F.lahko_gleda(p, sam_pomoc, brez_main10))
        self.assertTrue(F.lahko_gleda(p, sam_pomoc, brez_main10, pomocnik=True))
        self.assertTrue(F.lahko_gleda(p, Izidi(racun, Odgovor([Izdaja("Film.2020.1080p.BluRay.TrueHD.7.1.x264", 9.0)])), z,
                                      pomocnik=True))
        self.assertFalse(F.lahko_gleda(p, Izidi(racun, Odgovor([Izdaja("Film.2020.COMPLETE.BLURAY-GRP", 40.0)])), z,
                                       pomocnik=True))
        self.assertFalse(F.lahko_gleda(p, Izidi(racun, Odgovor([replace(hevc10, geslo=True)])), brez_main10, pomocnik=True))
        self.assertEqual([F.pot(i, brez_main10) for i in (dobra, hevc10, Izdaja("Film.BDMV", 1.0))],
                         [F.Pot.TV, F.Pot.POMOCNIK, F.Pot.NE])
        pv = F.preverba(sam_pomoc, p, brez_main10)
        self.assertEqual((pv.izid, pv.pomoc, pv.oznaka), (Izid.NI, True, K.Oznaka.UHD))
        self.assertFalse(F.preverba(Izidi(racun, Odgovor([])), p, z).pomoc)
        pv2 = F.preverba(Izidi(racun, Odgovor([dobra, hevc10])), p, brez_main10)
        self.assertEqual((pv2.izid, pv2.pomoc), (Izid.NA_VOLJO, False))
        pv3 = F.preverba(Izidi(racun, Odgovor(None)), p, brez_main10)
        self.assertEqual((pv3.izid, pv3.pomoc), (Izid.NE_VEMO, False))
        zp = F.zapisi(None, pv.izid, pv.oznaka, T0, pv.pomoc)
        ni = F.zapisi(None, Izid.NI, None, T0)
        self.assertFalse(F.pokazi(zp, T0 + MIN, pomocnik=False))
        self.assertTrue(F.pokazi(zp, T0 + MIN, pomocnik=True))
        self.assertFalse(F.pokazi(zp, T0 + 2 * MIN, pomocnik=False))
        self.assertFalse(F.pokazi(ni, T0 + MIN, pomocnik=True))
        self.assertFalse(F.pokazi(zp, T0 + 6 * 60 * MIN + 1, pomocnik=True))
        self.assertEqual(F.iz_niza(F.v_niz(zp)), zp)
        self.assertEqual(F.iz_niza("NI;5;;0"), F.Zapis(Izid.NI, 5, None, 0, False))
        self.assertIsNone(F.iz_niza("NI;5;;0;x"))
        self.assertFalse(F.iz_niza("NA_VOLJO;5;;0;1").pomoc)


class Kvota(unittest.TestCase):
    def test_omejevalnik(self):
        om = F.Omejevalnik(3, prvi_premor_ms=10 * MIN, najvec_premor_ms=10 * MIN)
        self.assertEqual([om.smem(T0 + i) for i in range(4)], [True, True, True, False])
        self.assertTrue(om.smem(T0 + MIN))
        om.meja(T0 + MIN)
        self.assertFalse(om.smem(T0 + 2 * MIN))
        self.assertTrue(om.smem(T0 + 12 * MIN))
        om2 = F.Omejevalnik(2)
        self.assertEqual([om2.lahko(T0) for _ in range(3)], [True, True, True])
        self.assertEqual([om2.smem(T0) for _ in range(3)], [True, True, False])
        self.assertFalse(om2.lahko(T0 + 1))
        self.assertFalse(F.poslji(Izid.NE_VEMO, "tt1", True))
        self.assertFalse(F.poslji(Izid.NA_VOLJO, None, True))
        self.assertFalse(F.poslji(Izid.NA_VOLJO, "tt1", False))
        self.assertTrue(F.poslji(Izid.NA_VOLJO, "tt1", True))
        om3 = F.Omejevalnik(2)
        om3.zabelezi(T0); om3.zabelezi(T0 + 1)
        self.assertFalse(om3.smem(T0 + 2))
        om3.zabelezi(T0 + 3)
        self.assertTrue(om3.smem(T0 + 3 + MIN))
        self.assertEqual(F.prazno(True, True), F.Prazno.ISCEM)
        self.assertEqual(F.prazno(False, True), F.Prazno.NE_ODGOVARJA)
        self.assertEqual(F.prazno(False, False), F.Prazno.NI_NASLOVOV)

    def test_ogled_in_id(self):
        E = F.Epizoda
        ep = [E("tt9:1:1", 1, 1), E("tt9:1:2", 1, 2), E("tt9:1:3", 1, 3), E("tt9:2:1", 2, 1)]
        self.assertEqual(F.epizoda_za_ogled(ep, None).id, "tt9:1:1")
        self.assertEqual(F.epizoda_za_ogled(ep, F.Ogled(1, 3, False)).id, "tt9:1:3")
        self.assertEqual(F.epizoda_za_ogled(ep, F.Ogled(1, 3, True)).id, "tt9:2:1")
        self.assertEqual(F.epizoda_za_ogled(ep, F.Ogled(2, 1, True)).id, "tt9:1:1")
        self.assertIsNone(F.epizoda_za_ogled([], F.Ogled(1, 3, False)))
        kb = F.kljuc(F.VIR_USENET, "odtis", "series|tt9")
        self.assertEqual(F.kljuc_ogleda(kb, None), kb)
        self.assertNotEqual(F.kljuc_ogleda(kb, F.Ogled(1, 3, False)), F.kljuc_ogleda(kb, F.Ogled(1, 1, False)))
        self.assertNotEqual(F.kljuc_ogleda(kb, F.Ogled(1, 3, True)), F.kljuc_ogleda(kb, F.Ogled(1, 3, False)))
        self.assertEqual(F.id_iskanja_epizode(E("tmdb:55:1:3", 1, 3), "tt123"), "tt123:1:3")
        self.assertEqual(F.id_iskanja_epizode(E("tt123:1:3", 1, 3), "tt123"), "tt123:1:3")
        self.assertIsNone(F.id_iskanja_epizode(E("kitsu:7:3", 1, 3), None))
        self.assertEqual(F.id_iskanja(["kitsu:1", "tt1:1:2", "tt2"]), "tt1:1:2")
        self.assertEqual(F.ROK_MS, 8_000, "rok: isti kot predvajanje (UsenetPravila.ISKANJE_ROK_MS)")
        self.assertEqual(F.razlog_ne_vemo(Izid.NE_VEMO, "tt1", True, False, None), "ni_racuna")
        self.assertEqual(F.razlog_ne_vemo(Izid.NA_VOLJO, None, False, False, None), "ni_iden")
        self.assertEqual(F.razlog_ne_vemo(Izid.NA_VOLJO, "kitsu:1", False, False, None), "ni_imdb")
        self.assertEqual(F.razlog_ne_vemo(Izid.NA_VOLJO, "tt1", True, True, "http_503"), "http_503")

    def test_proracun(self):
        zacetni = F.proracun(None, True, 0)
        self.assertEqual(zacetni.ostalo, F.PRORACUN_MREZE)
        vnaprej = F.proracun(replace(zacetni, ostalo=0), True, 0)
        self.assertEqual((vnaprej.ostalo, vnaprej.vnaprej), (F.VNAPREJ_MREZE, True))
        self.assertEqual(F.proracun(replace(vnaprej, ostalo=0), True, 0).ostalo, 0)
        self.assertEqual(F.proracun(replace(vnaprej, ostalo=0), True, 1).ostalo, F.PRORACUN_MREZE)
        self.assertEqual(F.proracun(replace(vnaprej, ostalo=0), False, 0).ostalo, F.PRORACUN_MREZE)
        self.assertEqual(F.proracun(replace(zacetni, ostalo=7), True, 0).ostalo, 7)

    def test_meje_indeksatorja(self):
        self.assertEqual(F.NA_MINUTO, 60)
        self.assertEqual(F.HKRATI, 2)
        self.assertTrue(1 <= F.RAZMIK_MS <= 999)
        om4 = F.Omejevalnik(F.NA_MINUTO)
        self.assertEqual(om4.razmik(T0), 0)
        self.assertTrue(all(om4.smem(T0 + i) for i in range(60)))
        self.assertFalse(om4.smem(T0 + 140))
        self.assertTrue(1 <= om4.razmik(T0 + 99) <= F.RAZMIK_MS)
        om5 = F.Omejevalnik(F.NA_MINUTO)
        om5.meja(T0)
        self.assertEqual((om5.lahko(T0 + 4_999), om5.lahko(T0 + 5_000)), (False, True))
        om5.meja(T0 + 5_000)
        self.assertEqual((om5.lahko(T0 + 14_999), om5.lahko(T0 + 15_000)), (False, True))
        om5.uspeh(T0 + 20_000); om5.meja(T0 + 20_000)
        self.assertTrue(om5.lahko(T0 + 25_000))
        om5b = F.Omejevalnik(F.NA_MINUTO)
        om5b.meja(T0); om5b.meja(T0 + 300)
        self.assertTrue(om5b.lahko(T0 + 5_000))
        om5b.meja(T0 + 5_000)
        self.assertEqual((om5b.lahko(T0 + 14_999), om5b.lahko(T0 + 15_000)), (False, True))
        om6 = F.Omejevalnik(F.NA_MINUTO)
        cas = T0
        for _ in range(30):
            om6.meja(cas)
            cas += om6.premor_se(cas)
        self.assertEqual(om6.premor_se(cas - 15 * MIN), 15 * MIN)
        om7 = F.Omejevalnik(F.NA_MINUTO)
        self.assertEqual(om7.rezerviraj(T0), 0)
        self.assertEqual(om7.rezerviraj(T0), F.RAZMIK_MS)
        self.assertEqual(om7.rezerviraj(T0), 2 * F.RAZMIK_MS)
        om8 = F.Omejevalnik(F.NA_MINUTO)
        om8.meja(T0); om8.uspeh(T0 + 1); om8.meja(T0 + 5_000)
        self.assertFalse(om8.lahko(T0 + 14_999))
        self.assertIsNone(om8.rezerviraj(T0 + 6_000))

    def test_prednost_klika(self):
        om9 = F.Omejevalnik(10, zadrzano=5)
        self.assertEqual([om9.smem(T0 + i) for i in range(6)], [True, True, True, True, True, False])
        self.assertIsNotNone(om9.rezerviraj_uporabniku(T0 + 10))
        om10 = F.Omejevalnik(10, zadrzano=5)
        for i in range(5):
            om10.smem(T0 + i)
        self.assertEqual(sum(1 for i in range(5) if om10.rezerviraj_uporabniku(T0 + 20 + i) is not None), 5)
        self.assertIsNone(om10.rezerviraj_uporabniku(T0 + 30))
        om11 = F.Omejevalnik(F.NA_MINUTO, zadrzano=F.REZERVIRANO_UPORABNIKU)
        om11.ustavi_preverbe(T0, F.PREMOR_PREVERB_MS)
        self.assertEqual((om11.smem(T0 + 1_000), om11.lahko(T0 + 1_000)), (False, False))
        self.assertIsNotNone(om11.rezerviraj_uporabniku(T0 + 1_000))
        self.assertTrue(om11.smem(T0 + F.PREMOR_PREVERB_MS + 1))
        om12 = F.Omejevalnik(F.NA_MINUTO, zadrzano=F.REZERVIRANO_UPORABNIKU)
        om12.ustavi_preverbe(T0, F.PREMOR_PREVERB_MS)
        self.assertFalse(om12.smem(T0 + 1_000))
        om12.sprosti_preverbe()
        self.assertTrue(om12.smem(T0 + 2_000))


class Predvajanje(unittest.TestCase):
    """OsPravila.samoUsenetIzbran in UsenetIskanjePravila (razlog, pozabi zapis) - kot na TV."""

    def test_samo_usenet(self):
        self.assertTrue(F.samo_usenet_izbran(True, False, False))
        self.assertFalse(F.samo_usenet_izbran(True, True, False), "Vsi viri: Usenet + debrid")
        self.assertFalse(F.samo_usenet_izbran(True, False, True), "rocna izbira toka")
        self.assertFalse(F.samo_usenet_izbran(False, False, False))

    def test_razlog_iskanja(self):
        R = F.RazlogIskanja
        self.assertEqual(F.razlog_iskanja(None, True), R.MEJA)
        self.assertEqual(F.razlog_iskanja(None, False), R.NI_ODGOVORA)
        self.assertEqual(F.razlog_iskanja(0, False), R.NI_IZDAJ)
        self.assertEqual(F.razlog_iskanja(3, False), R.OK)
        self.assertEqual([F.pozabi_zapis(r) for r in R], [r == R.NI_IZDAJ for r in R])


if __name__ == "__main__":
    unittest.main()
