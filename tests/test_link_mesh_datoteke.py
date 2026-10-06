"""Datoteke v Link Meshu: katero sredisce dobi oddajo in pri katerem se datoteka prevzame (link_mesh.sredisce_naprave).

V Link Meshu ima vsaka naprava svoje sredisce. Pot v `share.file` je relativna na sredisce, ki je datoteko sprejelo,
zato jo posiljatelj odda sredisci CILJNE naprave, prejemnik pa prevzame pri sredisci POSILJATELJA."""
import types
import unittest
import unittest.mock

from core import link_deljenje, link_mesh

KLJUC = "kljuc-telefona"
NASLOV = "wss://192.168.0.143:8990/cast/ws"


class Hub:
    def __init__(self, naprave):
        self.naprave = naprave

    def najdi(self, i):
        return self.naprave.get(i)


class Mesh:
    def __init__(self, znani):
        self.znani = znani

    def naslov_soseda(self, hid):
        return self.znani.get(hid, "")


def _naprava(sosed="", posredno=False):
    return types.SimpleNamespace(sosed=sosed, posredno=posredno)


class SredisceNaprave(unittest.TestCase):
    def setUp(self):
        self.hub = Hub({"n-tel": _naprava("n-tel"), "n-brskalnik": _naprava(""), "n-dalec": _naprava("n-tv", posredno=True),
                        "n-neznan-naslov": _naprava("n-x"), "n-zunaj": _naprava("n-zunaj")})
        self.mesh = Mesh({"n-tel": NASLOV, "n-tv": "wss://192.168.0.77:8990/cast/ws", "n-zunaj": "wss://127.0.0.1:41000/cast/ws"})
        self.clani = {"n-tel": {"kljuc": KLJUC}, "n-tv": {"kljuc": "kljuc-tv"}}
        self.potrdila = {NASLOV: ("ab" * 32, KLJUC)}

    def _sredisce(self, id_naprave, hub="privzet", mesh="privzet"):
        return link_mesh.sredisce_naprave(self.hub if hub == "privzet" else hub, self.mesh if mesh == "privzet" else mesh,
                                          id_naprave, potrdilo=lambda n: self.potrdila.get(n, ("", "")),
                                          clan_za_id=lambda i: self.clani.get(i))

    def test_naprava_pri_svojem_srediscu(self):
        self.assertEqual(self._sredisce("n-tel"), ((NASLOV, "ab" * 32), ""))

    def test_naprava_pri_nasem_srediscu_ali_neznana(self):
        self.assertEqual(self._sredisce("n-brskalnik"), (None, ""))
        self.assertEqual(self._sredisce("n-ni-je"), (None, ""))
        self.assertEqual(self._sredisce("n-tel", hub=None), (None, ""), "sredisca ne gostimo mi: ravnamo kot doslej")

    def test_dva_skoka_ali_neznan_naslov(self):
        self.assertEqual(self._sredisce("n-dalec"), (None, "naprava_pri_drugem_srediscu"))
        self.assertEqual(self._sredisce("n-neznan-naslov"), (None, "naprava_pri_drugem_srediscu"))
        self.assertEqual(self._sredisce("n-tel", mesh=None), (None, "naprava_pri_drugem_srediscu"))
        self.assertEqual(self._sredisce("n-zunaj"), (None, "naprava_pri_drugem_srediscu"),
                         "127.0.0.1 je rele Global Linka, ne naslov sredisca")

    def test_zaupanje_je_kljuc_clana_kroga(self):
        self.potrdila[NASLOV] = ("cd" * 32, "tuj-kljuc")
        self.assertEqual(self._sredisce("n-tel"), (None, "sredisce_naprave_ni_dosegljivo"), "potrdilo z drugim kljucem")
        self.potrdila[NASLOV] = ("", "")
        self.assertEqual(self._sredisce("n-tel"), (None, "sredisce_naprave_ni_dosegljivo"), "sredisca ni v tem omrezju")
        self.potrdila[NASLOV] = ("ab" * 32, KLJUC)
        del self.clani["n-tel"]
        self.assertEqual(self._sredisce("n-tel"), (None, "sredisce_naprave_ni_dosegljivo"), "ni vec clan kroga")

    def test_sporocili_za_obe_kodi(self):
        self.assertEqual(sorted(link_deljenje.SPOROCILA_SREDISCA), ["naprava_pri_drugem_srediscu", "sredisce_naprave_ni_dosegljivo"])


RELE = "wss://127.0.0.1:41000/cast/ws"


class MeshZRelejem(Mesh):
    """Sosednje sredisce je dosegljivo tudi prek Global Linka (krajevni konec releja do njega)."""

    def __init__(self, znani, releji):
        super().__init__(znani)
        self.releji = releji
        self.vprasani = []

    def naslov_prek_releja(self, hid):
        self.vprasani.append(hid)
        return self.releji.get(hid, "")


class SredisceNapraveZdoma(unittest.TestCase):
    """Naprava je zdoma: njeno sredisce dosezemo prek releja - oddaja datoteke, prevzem in zaslon delajo kot doma."""

    def setUp(self):
        self.hub = Hub({"n-tel": _naprava("n-tel"), "n-nov": _naprava("n-nov"), "n-dalec": _naprava("n-tv", posredno=True)})
        self.mesh = MeshZRelejem({"n-tel": NASLOV}, {"n-tel": RELE, "n-nov": "wss://127.0.0.1:41001/cast/ws"})
        self.clani = {"n-tel": {"kljuc": KLJUC}, "n-nov": {"kljuc": "kljuc-novega"}}
        self.potrdila = {NASLOV: ("ab" * 32, KLJUC), RELE: ("ab" * 32, KLJUC),
                         "wss://127.0.0.1:41001/cast/ws": ("ef" * 32, "kljuc-novega")}
        self.vprasana_potrdila = []
        self.doma = True

    def _sredisce(self, id_naprave):
        def potrdilo(n):
            self.vprasana_potrdila.append(n)
            return self.potrdila.get(n, ("", ""))
        return link_mesh.sredisce_naprave(self.hub, self.mesh, id_naprave, potrdilo=potrdilo,
                                          clan_za_id=lambda i: self.clani.get(i), dosegljiv=lambda _n: self.doma)

    def test_doma_neposredno_releja_se_ne_dotaknemo(self):
        self.assertEqual(self._sredisce("n-tel"), ((NASLOV, "ab" * 32), ""))
        self.assertEqual(self.vprasana_potrdila, [NASLOV])

    def test_zdoma_naravnost_prek_releja(self):
        self.doma = False
        self.assertEqual(self._sredisce("n-tel"), ((RELE, "ab" * 32), ""))
        self.assertEqual(self.vprasana_potrdila, [RELE], "na naslov, na katerem soseda ni, ne cakamo")

    def test_sosed_brez_zapomnjenega_naslova(self):
        self.assertEqual(self._sredisce("n-nov"), (("wss://127.0.0.1:41001/cast/ws", "ef" * 32), ""))

    def test_neposredno_odgovori_tujec_rele_pa_pravi(self):
        self.potrdila[NASLOV] = ("cd" * 32, "tuj-kljuc")       # na starem naslovu je zdaj druga naprava
        self.assertEqual(self._sredisce("n-tel"), ((RELE, "ab" * 32), ""))
        self.assertEqual(self.vprasana_potrdila, [NASLOV, RELE])

    def test_zaupanje_velja_tudi_prek_releja(self):
        self.doma = False
        self.potrdila[RELE] = ("cd" * 32, "tuj-kljuc")
        self.assertEqual(self._sredisce("n-tel"), (None, "sredisce_naprave_ni_dosegljivo"), "kljuc ni kljuc clana")
        self.potrdila[RELE] = ("", "")
        self.assertEqual(self._sredisce("n-tel"), (None, "sredisce_naprave_ni_dosegljivo"), "rele soseda ne doseze")
        del self.clani["n-tel"]
        self.assertEqual(self._sredisce("n-tel"), (None, "sredisce_naprave_ni_dosegljivo"), "ni vec clan kroga")

    def test_brez_releja_in_brez_naslova(self):
        self.mesh.releji.clear()
        self.assertEqual(self._sredisce("n-nov"), (None, "naprava_pri_drugem_srediscu"))
        self.assertEqual(self._sredisce("n-dalec"), (None, "naprava_pri_drugem_srediscu"), "dva skoka: releja ne vprasamo")
        self.assertNotIn("n-tv", self.mesh.vprasani)


class NaslovPrekReleja(unittest.TestCase):
    def _mesh(self, rele):
        m = link_mesh.MeshPovezovalec.__new__(link_mesh.MeshPovezovalec)
        m._rele = lambda hid: rele
        return m

    def test_krajevni_konec_releja(self):
        m = self._mesh(types.SimpleNamespace(vrata=41234))
        with unittest.mock.patch.object(link_mesh, "global_link_vklopljen", return_value=True):
            self.assertEqual(m.naslov_prek_releja("n-tel"), "wss://127.0.0.1:41234/cast/ws")
        with unittest.mock.patch.object(link_mesh, "global_link_vklopljen", return_value=False):
            self.assertEqual(m.naslov_prek_releja("n-tel"), "", "izklopljen Global Link")

    def test_sosed_ki_ga_rele_ne_pozna(self):
        m = self._mesh(None)
        with unittest.mock.patch.object(link_mesh, "global_link_vklopljen", return_value=True):
            self.assertEqual(m.naslov_prek_releja("n-neznan"), "")


class NaslovSoseda(unittest.TestCase):
    def test_iz_zapomnjenih(self):
        m = link_mesh.MeshPovezovalec.__new__(link_mesh.MeshPovezovalec)
        import threading
        m._zaklep = threading.Lock()
        m._znani = {"n-tel": {"id": "n-tel", "naslov": NASLOV}}
        self.assertEqual(m.naslov_soseda("n-tel"), NASLOV)
        self.assertEqual(m.naslov_soseda("n-drug"), "")
        self.assertEqual(m.naslov_soseda(""), "")


if __name__ == "__main__":
    unittest.main()
