"""Samodejna rezerva Linka (SAMODEJNA_REZERVA, odlozeno od 1.0.130; lastnik 25. 10. 2026 »da« za ta krog).

Neodvisni pregled OpenAI 1.0.129 je nasel dve vrzeli: (1) SafeerLink._gostitelj je ustvaril HubGostitelj brez
hubi/clan/nas_id - tuj Hub v istem omrezju (drug krog) bi po 60 s sprozil rezervo in racunalnik bi nehal gostiti;
(2) iz rezerve se ni vrnil, ker preveri() ni klical nihce (_mesh_lastni_hub se je v rezervi vrnil takoj, rednega
pregleda ni bilo). Tu: preverjeni oglasi clanov (kljuc potrdila = kljuc v krogu), reden pregled (zacni_nadzor) in
odziv odjemalca na spremembo (na izvoljeni Hub in nazaj na svojega). Brez omrezja: streznik, oglas in mDNS so lazni."""
import threading
import time
from unittest import mock

import pytest

from core import link_hub_streznik as H

TV_KLJUC = "a2V5LXR2" * 4
TV = {"id": "tv1", "fp": "tvfp", "prio": 95, "naslov": "wss://192.168.0.20:8990/cast/ws", "tls": True}
TUJ = {"id": "tuj1", "fp": "tujfp", "prio": 99, "naslov": "wss://192.168.0.30:8990/cast/ws", "tls": True}


class Streznik:
    def __init__(self):
        self._tece = False
        self.vrata = 8990
        self.odtis = "ab" * 32
        self.hub = None
        self.zagoni = 0

    def tece(self):
        return self._tece

    def zazeni(self):
        self.zagoni += 1
        self._tece = True
        return True

    def ustavi(self):
        self._tece = False


class Oglas:
    def zacni(self, *a, **k):
        return True

    def koncaj(self):
        pass

    def posodobi_prioriteto(self, p):
        return True


@pytest.fixture
def vklopljena():
    with mock.patch.object(H, "SAMODEJNA_REZERVA", True):
        yield


def _pocakaj(pogoj, cas=5.0):
    konec = time.monotonic() + cas
    while time.monotonic() < konec:
        if pogoj():
            return True
        time.sleep(0.01)
    return pogoj()


# ---------------------------------------------------------------------------- preverjeni oglasi

def test_preverjeni_hubi_samo_clan_s_kljucem_iz_kroga():
    klici = []

    def potrdilo(naslov):
        klici.append(naslov)
        return ("tvfp", TV_KLJUC) if "0.20" in naslov else ("tujfp", "drug-kljuc")

    ponaredek = dict(TV, naslov="wss://192.168.0.66:8990/cast/ws", fp="x")    # oglasi id clana, potrdilo ni njegovo
    p = H.PreverjeniHubi(lambda hid: TV_KLJUC if hid == "tv1" else "", potrdilo=potrdilo, ura=lambda: 100.0)
    assert p.filtriraj([TV, TUJ, ponaredek, dict(TV, naslov="ws://192.168.0.20:8990/cast/ws")]) == [TV]
    assert p.filtriraj([TV]) == [TV]
    assert klici.count(TV["naslov"]) == 1, "preverjen oglas velja 10 min - brez rokovanja TLS ob vsakem pregledu"
    assert "wss://192.168.0.30:8990/cast/ws" not in klici, "nepoznan id: potrdila sploh ne preverjamo"


def test_nedosegljiv_oglas_ne_steje_in_se_preveri_znova():
    odgovor = {"v": ("", "")}
    p = H.PreverjeniHubi(lambda hid: TV_KLJUC, potrdilo=lambda n: odgovor["v"], ura=lambda: 100.0)
    assert p.filtriraj([TV]) == []
    odgovor["v"] = ("tvfp", TV_KLJUC)
    assert p.filtriraj([TV]) == [TV]


# ---------------------------------------------------------------------------- reden pregled (zacni_nadzor)

def _gostitelj(oglasi, sosedje, ura):
    return H.HubGostitelj(poisci=lambda: None, hubi=lambda: list(oglasi), clan=lambda hid: hid == "tv1",
                          nas_id=lambda: "pc1", streznik=Streznik(), oglas=Oglas(), sosedje=lambda: list(sosedje),
                          ura=lambda: ura[0])


def test_nadzor_v_rezervo_in_nazaj(vklopljena):
    ura, sosedje, spremembe = [100.0], [], []
    g = _gostitelj([TV], sosedje, ura)
    assert g.preveri() and g.nacin() == "mesh"
    prvotni = g.preveri

    def tik():
        ura[0] += 31.0                       # vsak pregled je 31 s pozneje (lazna ura)
        return prvotni()
    g.preveri = tik
    g.zacni_nadzor(ob_spremembi=lambda prej, zdaj: spremembe.append((prej, zdaj)), razmik_s=0.01)
    try:
        assert _pocakaj(lambda: (("mesh", True), ("rezerva", False)) in spremembe), spremembe
        sosedje.append("tv1")                # Mesh spet dela: preizkus v ozadju uspe
        assert _pocakaj(lambda: any(z == ("mesh", True) and p[0] == "rezerva" for p, z in spremembe)), spremembe
    finally:
        g.ustavi_nadzor()
    assert g.nacin() == "mesh" and g.gostimo()


def test_nadzor_se_ustavi_s_koncaj():
    g = _gostitelj([], [], [100.0])
    g.zacni_nadzor(razmik_s=0.01)
    nit = g._nadzor
    g.koncaj()
    nit.join(2.0)
    assert not nit.is_alive()


def test_brez_samodejne_rezerve_ostane_mesh():
    ura = [100.0]
    g = _gostitelj([TV], [], ura)
    with mock.patch.object(H, "SAMODEJNA_REZERVA", False):
        for _ in range(6):
            ura[0] += 31.0
            assert g.preveri()
    assert g.nacin() == "mesh"


# ---------------------------------------------------------------------------- SafeerLink (odjemalec)

def _link():
    from core.safeer_link import SafeerLink
    link = SafeerLink.__new__(SafeerLink)
    link.control = True
    link.povezava = None
    link.datoteke = None
    link.zaslon = None
    return link


def _gostitelj_linka(link, oglasi, kljuci):
    """SafeerLink._gostitelj, kot ga naredi Control, z laznim mDNS, potrdili in krogom; nadzor ustavimo (testi ga
    poganjajo sami)."""
    from core import link_hub
    with mock.patch.object(link_hub, "poisci_hube_mdns", lambda cas=2.0: list(oglasi)), \
            mock.patch.object(type(link), "_kljuc_clana_kroga", staticmethod(lambda hid: kljuci.get(hid, ""))):
        g = link._gostitelj()
    g.ustavi_nadzor()
    g.streznik, g.oglas = Streznik(), Oglas()
    g.poisci = lambda: None
    return g


def test_link_poda_hubi_clan_in_nas_id(vklopljena):
    link = _link()
    g = _gostitelj_linka(link, [TV], {"tv1": TV_KLJUC})
    try:
        assert g.hubi is not None and g.clan is not None and g.nas_id_fn is H.id_za_oglas
        assert g._nadzor is None
        with mock.patch.object(type(link), "_kljuc_clana_kroga", staticmethod(lambda hid: TV_KLJUC if hid == "tv1" else "")):
            assert g.clan("tv1") and not g.clan("tuj1")
    finally:
        g.koncaj()


def test_link_tuj_hub_ne_sprozi_rezerve(vklopljena):
    """Vrzel (1): tuj Hub (drug krog, visja prioriteta) v istem omrezju - racunalnik gosti naprej, ostane Mesh."""
    from core import link_hub, link_tls
    # Kot prej (brez clan/hubi/nas_id): tuj Hub z id-jem iz iskanja sprozi rezervo in racunalnik neha gostiti.
    ura = [100.0]
    star = H.HubGostitelj(poisci=lambda: dict(TUJ), streznik=Streznik(), oglas=Oglas(), sosedje=lambda: [],
                          ura=lambda: ura[0])
    star.preveri()
    for _ in range(3):
        ura[0] += 31.0
        star.preveri()
    assert star.v_rezervi() and not star.streznik.tece(), "vrzel (1) iz pregleda: brez clan tuj Hub odloca"
    link = _link()
    g = _gostitelj_linka(link, [TUJ], {})
    g.poisci = lambda: dict(TUJ)
    g.ura = lambda: ura[0]
    g.sosedje_fn = lambda: []
    try:
        with mock.patch.object(link_hub, "poisci_hube_mdns", lambda cas=2.0: [TUJ]), \
                mock.patch.object(link_tls, "potrdilo_huba", lambda n, timeout=4.0: ("tujfp", "tuj-kljuc")), \
                mock.patch.object(type(link), "_kljuc_clana_kroga", staticmethod(lambda hid: "")):
            for _ in range(6):
                ura[0] += 31.0
                assert g.preveri(), "racunalnik ne sme nehati gostiti zaradi tujega Huba"
        assert g.nacin() == "mesh" and g.streznik.tece()
    finally:
        g.koncaj()


def test_link_rezerva_na_izvoljeni_hub_in_nazaj(vklopljena):
    """Vrzel (2): v rezervi se odjemalec poveze na izvoljeni Hub (TV z visjo prioriteto), ob vrnitvi Mesha spet na svoj."""
    from core import link_hub, link_tls
    link = _link()
    g = _gostitelj_linka(link, [TV], {"tv1": TV_KLJUC})
    ura, sosedje = [100.0], []
    g.ura = lambda: ura[0]
    g.sosedje_fn = lambda: list(sosedje)
    iskanja, na_lastnega = [], []
    zaplate = [mock.patch.object(link_hub, "poisci_hube_mdns", lambda cas=2.0: [TV]),
               mock.patch.object(link_tls, "potrdilo_huba", lambda n, timeout=4.0: ("tvfp", TV_KLJUC)),
               mock.patch.object(type(link), "_kljuc_clana_kroga", staticmethod(lambda hid: TV_KLJUC if hid == "tv1" else "")),
               mock.patch.object(type(link), "_poisci_hub", lambda self, tiho=False: iskanja.append(tiho) or True),
               mock.patch.object(type(link), "_na_lastni_hub", lambda self: na_lastnega.append(1)),
               mock.patch.object(type(link), "_v_ozadju", staticmethod(lambda f: f()))]
    for z in zaplate:
        z.start()
    try:
        assert g.preveri()
        prvotni = g.preveri

        def tik():
            ura[0] += 31.0
            return prvotni()
        g.preveri = tik
        g.zacni_nadzor(ob_spremembi=link._ob_spremembi_gostovanja, razmik_s=0.01)
        assert _pocakaj(lambda: bool(iskanja)), "po 60 s brez soseda: rezerva, izvoljen TV - odjemalec ga poisce"
        assert g.v_rezervi() and not g.gostimo()
        sosedje.append("tv1")
        assert _pocakaj(lambda: bool(na_lastnega)), "Mesh spet dela: odjemalec nazaj na svoj Hub"
        assert g.nacin() == "mesh" and g.gostimo()
    finally:
        g.ustavi_nadzor()
        for z in reversed(zaplate):
            z.stop()
        g.koncaj()


def test_mesh_lastni_hub_v_rezervi_poklice_preveri(vklopljena):
    """Vrzel (2): prej se je _mesh_lastni_hub v rezervi vrnil brez preveri() - preizkus Mesha se ni nikoli zacel."""
    link = _link()
    g = _gostitelj_linka(link, [], {})
    klici = []
    g._nacin, g._samodejna_rezerva = "rezerva", True
    g.preveri = lambda: klici.append(1) or False
    with mock.patch.object(H, "mesh_vklopljen", lambda: True), \
            mock.patch.object(type(link), "_clan_kroga", lambda self: True):
        link._mesh_lastni_hub()
    assert klici == [1]
    g.koncaj()


def test_nadzor_zacne_samo_control_s_samodejno_rezervo():
    from core import link_hub
    for control, vklop, pricakovano in ((True, True, True), (False, True, False), (True, False, False)):
        link = _link()
        link.control = control
        with mock.patch.object(H, "SAMODEJNA_REZERVA", vklop), \
                mock.patch.object(link_hub, "poisci_hube_mdns", lambda cas=2.0: []):
            g = link._gostitelj()
        try:
            assert (g._nadzor is not None) is pricakovano, (control, vklop)
        finally:
            g.koncaj()
    assert threading.active_count() >= 1


def test_redni_pregled_v_mesh_brez_iskanja_tujega_huba(vklopljena):
    """Pregled vsakih 20 s v Mesh ne isce tujega Huba (mDNS + preverbe HTTP/TLS, vec sekund): clane povedo oglasi."""
    klici = []
    g = H.HubGostitelj(poisci=lambda: klici.append(1), hubi=lambda: [], clan=lambda hid: True, nas_id=lambda: "pc1",
                       streznik=Streznik(), oglas=Oglas(), sosedje=lambda: [], ura=lambda: 100.0)
    assert g.preveri() and g.preveri()
    assert klici == []
    g._nacin = "rezerva"                     # v rezervi iskanje ostane (naj_gostimo brez oglasov)
    g.preveri()
    assert klici == [1]
    g.koncaj()
