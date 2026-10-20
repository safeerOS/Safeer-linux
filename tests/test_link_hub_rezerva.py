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

        with mock.patch.dict(os.environ, {"SAFEER_DOMACI_STREZNIK": "1"}):
            prio_env = link_hub_streznik.izracunaj_prioriteto()
            self.assertEqual(prio_env, 100)

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
    """Prehod med Mesh in rezervnim nacinom v HubGostitelj."""

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
        self.assertEqual(g.nacin(), "mesh", "po izteku intervala poskusi Mesh")

        # 5 sekund kasneje povezave se ni: se NE sme pasti nazaj v rezervo zaradi histereze (polni 60 s rok)
        ura_cas[0] += 5.0
        g.preveri()
        self.assertEqual(g.nacin(), "mesh", "histereza mora zdrzati celoten 60 s poskusni rok")

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


if __name__ == "__main__":
    unittest.main()
