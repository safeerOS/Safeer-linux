"""Preizkusi za samodejni rezervni nacin in izvolitev po zmogljivosti v Safeer Linku.

AGENTS.md vodilo:
- Safeer Link nima sredisca: vsaka naprava je lahko sredisce. Vloge so zacasne funkcije po zmogljivosti
  v trenutku, nikoli trajen rang.
- Rezervni nacin mora biti vedno na voljo, a ne sme izpodbijati najboljsega: vklopi se sam samo,
  ko najboljsi ne dela, in se vrne nanj, takoj ko spet dela.
"""

from __future__ import annotations

import io
import os
import unittest
from unittest import mock

from core import link_hub_streznik


class LazniStreznik:
    def __init__(self, uspe: bool = True):
        self.uspe = uspe
        self.zagoni = 0
        self.ustavitve = 0
        self._tece = False
        self.vrata = 8990
        self.odtis = "ab" * 32
        self.hub = None

    def tece(self) -> bool:
        return self._tece

    def zazeni(self) -> bool:
        self.zagoni += 1
        self._tece = self.uspe
        return self.uspe

    def ustavi(self) -> None:
        self.ustavitve += 1
        self._tece = False


class LazniOglas:
    def __init__(self):
        self.zacetki = []
        self.konci = 0
        self.posodobitve = []

    def zacni(self, vrata: int, odtis: str, id_naprave: str, ime: str, prioriteta: int = 80) -> bool:
        self.zacetki.append((vrata, odtis, id_naprave, ime, prioriteta))
        return True

    def koncaj(self) -> None:
        self.konci += 1

    def posodobi_prioriteto(self, nova_prio: int) -> bool:
        self.posodobitve.append(nova_prio)
        return True


class TestPrioritetaZmogljivosti(unittest.TestCase):
    """Izvolitev v rezervi po trenutni zmogljivosti (RAM, CPU, baterija)."""

    def test_polna_zmogljivost_racunalnika(self):
        # 4 GB prostega RAM-a, 0.1 load na jedro, priklopljen na omrezje (polni=True)
        bat = {"raven": 100, "polni": True}
        prio = link_hub_streznik.izracunaj_prioriteto(
            ram_prosto_mb=4096, cpu_obremenitev=0.1, baterija_info=bat, vrsta="racunalnik"
        )
        # Stopnja 80 + dodatek racunalnik 3 = 83
        self.assertEqual(prio, 83)

    def test_zmerna_zmogljivost(self):
        # 1.5 GB RAM, load 0.7, baterija na omrezju
        bat = {"raven": 100, "polni": True}
        prio = link_hub_streznik.izracunaj_prioriteto(
            ram_prosto_mb=1500, cpu_obremenitev=0.7, baterija_info=bat, vrsta="racunalnik"
        )
        # Stopnja 60 + dodatek 3 = 63
        self.assertEqual(prio, 63)

    def test_visoka_obremenitev_cpu(self):
        # Veliko RAM-a, a visoka obremenitev CPU (2.5) -> prioriteta pade
        bat = {"raven": 100, "polni": True}
        prio = link_hub_streznik.izracunaj_prioriteto(
            ram_prosto_mb=4096, cpu_obremenitev=2.5, baterija_info=bat, vrsta="racunalnik"
        )
        self.assertLess(prio, 65)
        self.assertEqual(prio, 43)

    def test_malo_prostega_pomnilnika(self):
        # Nizek CPU, a le 300 MB prostega RAM-a -> prioriteta pade
        bat = {"raven": 100, "polni": True}
        prio = link_hub_streznik.izracunaj_prioriteto(
            ram_prosto_mb=300, cpu_obremenitev=0.2, baterija_info=bat, vrsta="racunalnik"
        )
        self.assertLess(prio, 65)

    def test_baterija_pod_40_in_pod_30_odstotkov(self):
        # Na bateriji pod 30 % ne sme biti sredisce hise pred televizorjem (TV=60)
        bat_slaba = {"raven": 25, "polni": False}
        prio = link_hub_streznik.izracunaj_prioriteto(
            ram_prosto_mb=4096, cpu_obremenitev=0.1, baterija_info=bat_slaba, vrsta="racunalnik"
        )
        self.assertLess(prio, 60, "racunalnik na prazni bateriji mora imeti nizjo prioriteto kot TV (60)")

    def test_baterija_histereza(self):
        # Baterija med 30 % in 40 %: ce je prej ze tekla v redu (zadnja_prioriteta >= 50), ostane visja
        bat_vmesna = {"raven": 35, "polni": False}
        prio_s_histerezo = link_hub_streznik.izracunaj_prioriteto(
            ram_prosto_mb=4096, cpu_obremenitev=0.1, baterija_info=bat_vmesna,
            zadnja_prioriteta=83, vrsta="racunalnik"
        )
        # Brez predhodnega stanja (sveza ugotovitev med 30 in 40)
        prio_brez_histereze = link_hub_streznik.izracunaj_prioriteto(
            ram_prosto_mb=4096, cpu_obremenitev=0.1, baterija_info=bat_vmesna,
            zadnja_prioriteta=None, vrsta="racunalnik"
        )
        self.assertGreaterEqual(prio_s_histerezo, prio_brez_histereze)

    def test_izrecni_domaci_streznik(self):
        # Izrecna izbira domacega streznika vedno dobi prioriteto 100
        prio = link_hub_streznik.izracunaj_prioriteto(streznik=True)
        self.assertEqual(prio, 100)

    def test_prioriteta_brez_argumenta_streznik_nikoli_100(self):
        # 1. Funkcija je_domaci_streznik ne sme obstajati v modulu
        self.assertFalse(hasattr(link_hub_streznik, "je_domaci_streznik"),
                         "je_domaci_streznik() mora biti odstranjena")

        # 2. Nobena okoljska spremenljivka ne sme podeliti prioritete 100
        okolja = [
            {"SAFEER_DOMACI_STREZNIK": "1"},
            {"SAFEER_LINK_STREZNIK": "1"},
            {"SAFEER_STREZNIK": "1"},
            {"SAFEER_DOMACI_STREZNIK": "1", "SAFEER_LINK_STREZNIK": "1", "SAFEER_STREZNIK": "1"},
        ]
        for env in okolja:
            with mock.patch.dict(os.environ, env):
                prio_brez = link_hub_streznik.izracunaj_prioriteto()
                self.assertNotEqual(prio_brez, 100, f"okolje {env} ne sme podeliti prioritete 100")
                self.assertLessEqual(prio_brez, 84)

                prio_none = link_hub_streznik.izracunaj_prioriteto(streznik=None)
                self.assertNotEqual(prio_none, 100)

                prio_false = link_hub_streznik.izracunaj_prioriteto(streznik=False)
                self.assertNotEqual(prio_false, 100)

        # 3. Prioriteta 100 ostane SAMO prek izrecnega streznik=True
        prio_streznik = link_hub_streznik.izracunaj_prioriteto(streznik=True)
        self.assertEqual(prio_streznik, 100)

    def test_izenacenje_vrsta_naprave(self):
        # Ob enaki sistemski zmogljivosti vrsta naprave sluzi za prelom izenacenja
        bat = {"raven": 100, "polni": True}
        p_pc = link_hub_streznik.izracunaj_prioriteto(
            ram_prosto_mb=4096, cpu_obremenitev=0.1, baterija_info=bat, vrsta="racunalnik"
        )
        p_tv = link_hub_streznik.izracunaj_prioriteto(
            ram_prosto_mb=4096, cpu_obremenitev=0.1, baterija_info=bat, vrsta="tv"
        )
        p_tablica = link_hub_streznik.izracunaj_prioriteto(
            ram_prosto_mb=4096, cpu_obremenitev=0.1, baterija_info=bat, vrsta="tablica"
        )
        p_telefon = link_hub_streznik.izracunaj_prioriteto(
            ram_prosto_mb=4096, cpu_obremenitev=0.1, baterija_info=bat, vrsta="telefon"
        )
        self.assertGreater(p_pc, p_tv)
        self.assertGreater(p_tv, p_tablica)
        self.assertGreater(p_tablica, p_telefon)


class TestSamodejnaRezerva(unittest.TestCase):
    """Prehod med Mesh in rezervnim nacinom v HubGostitelj (samodejna rezerva je v 1.0.129 izklopljena - preizkusi
    jo vklopijo, da logika ostane preverjena za 1.0.130)."""

    def setUp(self):
        zaplata = mock.patch.object(link_hub_streznik, "SAMODEJNA_REZERVA", True)
        zaplata.start()
        self.addCleanup(zaplata.stop)

    def test_prehod_v_rezervo_ob_neuspesnem_zagonu_streznika(self):
        s = LazniStreznik(uspe=False)
        o = LazniOglas()
        ura_cas = [100.0]

        g = link_hub_streznik.HubGostitelj(
            poisci=lambda: None, streznik=s, oglas=o, ura=lambda: ura_cas[0]
        )
        with mock.patch("sys.stdout", new_callable=io.StringIO) as izhod:
            self.assertFalse(g.preveri())
            dnevnik = izhod.getvalue()

        self.assertTrue(g.v_rezervi(), "ob neuspehu zagona streznika mora preiti v rezervni nacin")
        self.assertIn("[SafeerLink]", dnevnik)
        self.assertIn("rezerv", dnevnik)

    def test_prehod_v_rezervo_ko_mdns_vidi_clana_brez_povezave_60s(self):
        # mDNS vidi televizor iz kroga zaupanja, vendar se Mesh nanj ne more povezati
        s = LazniStreznik(uspe=True)
        o = LazniOglas()
        ura_cas = [100.0]
        sosedje_mesh = []  # noben sosed ni povezan v Mesh
        tv_oglas = {"id": "tv1", "fp": "tvfp1", "prio": 60, "naslov": "wss://tv:8990/cast/ws"}

        g = link_hub_streznik.HubGostitelj(
            poisci=lambda: tv_oglas,
            hubi=lambda: [tv_oglas],
            clan=lambda id_naprave: True,
            nas_id=lambda: "pc1",
            streznik=s,
            oglas=o,
            sosedje=lambda: sosedje_mesh,
            ura=lambda: ura_cas[0],
        )

        # 0 s: prvi krog, zagon streznika v Mesh, se ne sme preiti v rezervo
        self.assertTrue(g.preveri())
        self.assertFalse(g.v_rezervi())
        self.assertEqual(g.nacin(), "mesh")

        # 30 s: se vedno v roku 60 s, se vedno v Mesh
        ura_cas[0] += 30.0
        self.assertTrue(g.preveri())
        self.assertFalse(g.v_rezervi())

        # 61 s skupaj (100 -> 161): minilo je 60 s brez povezave s sosedom kljub oglasu mDNS
        ura_cas[0] += 31.0
        with mock.patch("sys.stdout", new_callable=io.StringIO) as izhod:
            g.preveri()
            dnevnik = izhod.getvalue()

        self.assertTrue(g.v_rezervi(), "po 60 s brez dosezenega soseda mora preiti v rezervo")
        self.assertIn("[SafeerLink]", dnevnik)

    def test_brez_tujih_clanov_ostane_v_mesh(self):
        # Ce mDNS ne vidi nobenega clana (naprava je sama v omrezju), mora ostati v Mesh
        s = LazniStreznik(uspe=True)
        o = LazniOglas()
        ura_cas = [100.0]

        g = link_hub_streznik.HubGostitelj(
            poisci=lambda: None,
            hubi=lambda: [],
            clan=lambda id_naprave: True,
            nas_id=lambda: "pc1",
            streznik=s,
            oglas=o,
            sosedje=lambda: [],
            ura=lambda: ura_cas[0],
        )

        self.assertTrue(g.preveri())
        self.assertFalse(g.v_rezervi())

        # Cas tece dlje kot 60 s
        ura_cas[0] += 120.0
        self.assertTrue(g.preveri())
        self.assertFalse(g.v_rezervi(), "kadar tujih clanov ni videnih, ostane v Mesh kot samostojno vozlisce")

    def test_vrnitev_v_mesh_po_60s_in_uspeh(self):
        # Prehod v rezervo, nato po ~60 s poskus vrnitve v Mesh; sosed se poveze in ostanemo v Mesh
        s = LazniStreznik(uspe=True)
        o = LazniOglas()
        ura_cas = [100.0]
        sosedje_mesh = []
        tv_oglas = {"id": "tv1", "fp": "tvfp1", "prio": 60, "naslov": "wss://tv:8990/cast/ws"}

        g = link_hub_streznik.HubGostitelj(
            poisci=lambda: tv_oglas,
            hubi=lambda: [tv_oglas],
            clan=lambda id_naprave: True,
            nas_id=lambda: "pc1",
            streznik=s,
            oglas=o,
            sosedje=lambda: sosedje_mesh,
            ura=lambda: ura_cas[0],
        )

        # Zazenemo in pocakamo 65 s, da preide v rezervo
        g.preveri()
        ura_cas[0] += 65.0
        g.preveri()
        self.assertTrue(g.v_rezervi())

        # V rezervi cakamo se 65 s
        ura_cas[0] += 65.0
        # Zdaj sosedje uspesno vzpostavijo povezavo v Mesh
        sosedje_mesh.append("tv1")

        with mock.patch("sys.stdout", new_callable=io.StringIO) as izhod:
            g.preveri()
            dnevnik = izhod.getvalue()

        self.assertFalse(g.v_rezervi(), "ko Mesh sosed uspe, se mora vrniti v Mesh")
        self.assertEqual(g.nacin(), "mesh")
        self.assertIn("[SafeerLink]", dnevnik)

    def test_histereza_pri_poskusu_mesh(self):
        # Ob poskusu vrnitve v Mesh ne sme takoj v naslednji sekundi pasti nazaj v rezervo
        s = LazniStreznik(uspe=True)
        o = LazniOglas()
        ura_cas = [100.0]
        sosedje_mesh = []
        tv_oglas = {"id": "tv1", "fp": "tvfp1", "prio": 60, "naslov": "wss://tv:8990/cast/ws"}

        g = link_hub_streznik.HubGostitelj(
            poisci=lambda: tv_oglas,
            hubi=lambda: [tv_oglas],
            clan=lambda id_naprave: True,
            nas_id=lambda: "pc1",
            streznik=s,
            oglas=o,
            sosedje=lambda: sosedje_mesh,
            ura=lambda: ura_cas[0],
        )

        # Prehod v rezervo po 65 s
        g.preveri()
        ura_cas[0] += 65.0
        g.preveri()
        self.assertTrue(g.v_rezervi())

        # 65 s v rezervi -> poskus vrnitve v Mesh
        ura_cas[0] += 65.0
        g.preveri()
        self.assertTrue(g.v_preizkusu_mesh(), "po izteku intervala zacne preizkus Mesh v ozadju")
        self.assertTrue(g.v_rezervi(), "v_rezervi() mora ostati True med preizkusom")

        # 5 sekund kasneje povezave se ni: preizkus se vedno tece in ostajamo v rezervi
        ura_cas[0] += 5.0
        g.preveri()
        self.assertTrue(g.v_preizkusu_mesh(), "preizkus mora zdrzati celoten 60 s poskusni rok")
        self.assertTrue(g.v_rezervi())

    @mock.patch.dict(os.environ, {"SAFEER_LINK_MESH": "0"})
    def test_rocno_vsiljena_rezerva(self):
        s = LazniStreznik(uspe=True)
        o = LazniOglas()
        ura_cas = [100.0]

        g = link_hub_streznik.HubGostitelj(
            poisci=lambda: None, streznik=s, oglas=o, ura=lambda: ura_cas[0]
        )
        g.preveri()
        self.assertTrue(g.v_rezervi())

        # Tudi po 200 s ne poskusi Mesh, ker je SAFEER_LINK_MESH=0
        ura_cas[0] += 200.0
        g.preveri()
        self.assertTrue(g.v_rezervi())
        self.assertEqual(g.nacin(), "rezerva")

    def test_med_preizkusom_v_rezervi_ostane_true_in_odjemalec_ne_zamenja_huba(self):
        s = LazniStreznik(uspe=True)
        o = LazniOglas()
        ura_cas = [100.0]
        sosedje_mesh = []
        tv_oglas = {"id": "tv1", "fp": "tvfp1", "prio": 95, "naslov": "wss://tv:8990/cast/ws"}

        g = link_hub_streznik.HubGostitelj(
            poisci=lambda: tv_oglas,
            hubi=lambda: [tv_oglas],
            clan=lambda id_naprave: True,
            nas_id=lambda: "pc1",
            streznik=s,
            oglas=o,
            sosedje=lambda: sosedje_mesh,
            ura=lambda: ura_cas[0],
        )

        # 1. Zacetek: zagon in prehod v rezervo (65 s brez povezave z oglasenim sosedom)
        g.preveri()
        ura_cas[0] += 65.0
        g.preveri()
        self.assertTrue(g.v_rezervi())
        self.assertFalse(g.gostimo(), "zaradi TV z visjo prioriteto (95) PC v rezervi ne gosti")

        # 2. Cas v rezervi potece (65 s) -> zacne se preizkus v ozadju
        ura_cas[0] += 65.0
        g.preveri()

        # Med preizkusom:
        self.assertTrue(g.v_rezervi(), "v_rezervi() mora med preizkusom ostati True")
        self.assertTrue(g.v_preizkusu_mesh(), "v_preizkusu_mesh() mora biti True")
        self.assertEqual(g.nacin(), "rezerva")
        self.assertFalse(g.gostimo(), "PC med preizkusom se vedno ne gosti uradno za omrezje")

        # Preveri, da SafeerLink odjemalec (po pravilu iz core/safeer_link.py) med preizkusom NE zamenja Huba:
        # Odjemalec preklopi na lokalni Hub samo, ce mesh_vklopljen() in NOT g.v_rezervi()
        odjemalec_preklopi = link_hub_streznik.mesh_vklopljen() and not g.v_rezervi()
        self.assertFalse(odjemalec_preklopi, "odjemalec ne sme preklopiti na lokalni Hub med preizkusom")

    def test_30_min_neuspesnih_preizkusov_omejeno_in_zamik_raste(self):
        s = LazniStreznik(uspe=True)
        o = LazniOglas()
        ura_cas = [100.0]
        sosedje_mesh = []
        tv_oglas = {"id": "tv1", "fp": "tvfp1", "prio": 95, "naslov": "wss://tv:8990/cast/ws"}

        g = link_hub_streznik.HubGostitelj(
            poisci=lambda: tv_oglas,
            hubi=lambda: [tv_oglas],
            clan=lambda id_naprave: True,
            nas_id=lambda: "pc1",
            streznik=s,
            oglas=o,
            sosedje=lambda: sosedje_mesh,
            ura=lambda: ura_cas[0],
        )

        # Prehod v rezervo
        g.preveri()
        ura_cas[0] += 65.0
        g.preveri()
        self.assertTrue(g.v_rezervi())

        zacetni_zagoni = s.zagoni
        vloge_spremembe = 0
        prejsnja_v_rezervi = g.v_rezervi()

        # Simuliramo 30 minut (1800 s) z lazno uro, klicemo preveri() vsakih 10 s
        konec = ura_cas[0] + 1800.0
        while ura_cas[0] < konec:
            ura_cas[0] += 10.0
            g.preveri()
            trenutna_v_rezervi = g.v_rezervi()
            if trenutna_v_rezervi != prejsnja_v_rezervi:
                vloge_spremembe += 1
                prejsnja_v_rezervi = trenutna_v_rezervi

        # 1. Vloga se v 30 minutah neuspeha sploh ne sme zamenjati (ostane ves cas v rezervi!)
        self.assertEqual(vloge_spremembe, 0, "vloga v_rezervi() se med neuspesnimi preizkusi ne sme preklapljati")
        self.assertTrue(g.v_rezervi())

        # 2. Zaradi narascajocega zamika (60, 120, 240, 480, 960 ...) je stevilo zagonov strogo omejeno:
        # V 30 min je najvec 5 poskusov (60s preizkus + narascajoci premor)
        novi_zagoni = s.zagoni - zacetni_zagoni
        self.assertLessEqual(novi_zagoni, 5, "v 30 min se streznik sme zagnati najvec 5-krat (zamik raste)")
        # Zamik poskusa mora narasti do najvisjih stopenj (vsaj 960 ali 1800 s)
        self.assertGreaterEqual(g._zamik_poskusa_s, 960.0)

    def test_uspesen_preizkus_preklopi_v_mesh_in_ponastavi_zamik(self):
        s = LazniStreznik(uspe=True)
        o = LazniOglas()
        ura_cas = [100.0]
        sosedje_mesh = []
        tv_oglas = {"id": "tv1", "fp": "tvfp1", "prio": 95, "naslov": "wss://tv:8990/cast/ws"}

        g = link_hub_streznik.HubGostitelj(
            poisci=lambda: tv_oglas,
            hubi=lambda: [tv_oglas],
            clan=lambda id_naprave: True,
            nas_id=lambda: "pc1",
            streznik=s,
            oglas=o,
            sosedje=lambda: sosedje_mesh,
            ura=lambda: ura_cas[0],
        )

        # Prehod v rezervo
        g.preveri()
        ura_cas[0] += 65.0
        g.preveri()
        self.assertTrue(g.v_rezervi())

        # En neuspesen preizkus: 65 s do zacetka + 65 s v preizkusu brez sosedov
        ura_cas[0] += 65.0
        g.preveri()
        self.assertTrue(g.v_preizkusu_mesh())
        ura_cas[0] += 65.0
        g.preveri()
        self.assertFalse(g.v_preizkusu_mesh())
        # Zamik se je podvojil na 120 s
        self.assertEqual(g._zamik_poskusa_s, 120.0)

        # Pocakamo 125 s v rezervi do naslednjega preizkusa
        ura_cas[0] += 125.0
        g.preveri()
        self.assertTrue(g.v_preizkusu_mesh())

        # Sosed se uspesno poveze v Mesh
        sosedje_mesh.append("tv1")
        g.preveri()

        # Uspesen preizkus:
        self.assertFalse(g.v_rezervi(), "mora preklopiti iz rezerve v mesh")
        self.assertEqual(g.nacin(), "mesh")
        self.assertFalse(g.v_preizkusu_mesh())
        self.assertEqual(g._zamik_poskusa_s, link_hub_streznik.ROK_POSKUSA_MESH_S, "zamik se mora ponastaviti na 60 s")
        self.assertTrue(g.gostimo(), "po uspesnem prehodu v mesh racunalnik gosti svoj Hub")


if __name__ == "__main__":
    unittest.main()


def test_tuj_hub_brez_kroga_ne_sprozi_rezerve_v_129():
    """Neodvisni pregled OpenAI 1.0.129: SafeerLink ustvari HubGostitelj brez clan/hubi/nas_id - tuj Hub v istem
    omrezju (drug krog) bi po 60 s sprozil rezervo. V 1.0.129 je samodejna rezerva izklopljena: ostane Mesh."""
    s = LazniStreznik(uspe=True)
    o = LazniOglas()
    ura_cas = [100.0]
    tuj = {"id": "tuj1", "fp": "tujfp", "prio": 60, "naslov": "wss://tuj:8990/cast/ws"}
    g = link_hub_streznik.HubGostitelj(poisci=lambda: tuj, streznik=s, oglas=o, sosedje=lambda: [],
                                       ura=lambda: ura_cas[0])     # kot SafeerLink._gostitelj: brez clan/hubi/nas_id
    assert g.preveri()
    for _ in range(4):
        ura_cas[0] += 31.0
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            assert g.preveri(), "racunalnik ne sme nehati gostiti zaradi tujega Huba"
    assert not g.v_rezervi() and g.nacin() == "mesh" and s.tece()


def test_nova_prioriteta_res_v_zapisu_txt():
    """Pomocnik (pregled 1.0.129): posodobi_prioriteto je spremenil samo slovar properties, zapis TXT (ServiceInfo.text)
    je ostal star - izvolitev v rezervi je videla staro prioriteto. Pravi zeroconf.ServiceInfo, lazni Zeroconf."""
    import pytest
    zeroconf = pytest.importorskip("zeroconf")
    from core import link_hub_streznik as h

    class Zc:
        def __init__(self):
            self.posodobljeni = []

        def update_service(self, info):
            self.posodobljeni.append(info)
    o = h.Oglas()
    o._zc = Zc()
    o._info = zeroconf.ServiceInfo(h.STORITEV_MDNS, "safeer-x." + h.STORITEV_MDNS, addresses=[b"\x7f\x00\x00\x01"],
                                   port=4242, properties={b"id": b"x", b"prio": b"83"}, server="pc.local.")
    o._prioriteta = 83
    assert o.posodobi_prioriteto(13)
    objavljen = o._zc.posodobljeni[-1]
    assert b"prio=13" in objavljen.text and b"prio=83" not in objavljen.text
    assert b"id=x" in objavljen.text and objavljen.port == 4242 and objavljen.name == "safeer-x." + h.STORITEV_MDNS
