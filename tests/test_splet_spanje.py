"""Spanje zavihkov, safeer://procesi in obnova omreznega procesa (core/splet_spanje.py) - brez GTK.

Zivo v WebKitGTK 6.0: tests/test_splet_spanje_zivo.py (meritve pomnilnika, zbujanje, varnost sheme, piskotki seje).
"""
import os
import shutil
import subprocess
import time
import types

import pytest

from core import processes_page, splet_spanje
from core.splet_spanje import SpanjeZavihkov, proces_iz_sonde, razlogi_zascite, sme_spati
from core.tab_monitor import TabMonitor

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- lazni WebKit/GLib (samo kar modul uporablja)
W = types.SimpleNamespace(
    PolicyDecisionType=types.SimpleNamespace(NAVIGATION_ACTION="nav", NEW_WINDOW_ACTION="okno", RESPONSE="odziv"),
    NavigationType=types.SimpleNamespace(LINK_CLICKED="klik", OTHER="drugo", BACK_FORWARD="zgodovina", RELOAD="znova",
                                         FORM_SUBMITTED="obrazec"),
    LoadEvent=types.SimpleNamespace(STARTED="zacetek", REDIRECTED="preusmeritev", COMMITTED="potrjeno",
                                    FINISHED="konec"),
    MediaCaptureState=types.SimpleNamespace(NONE=0, ACTIVE=1, MUTED=2),
)


class _GLib:
    def __init__(self):
        self.idle = []

    def timeout_add_seconds(self, *_a):
        return 1

    def timeout_add(self, *_a):
        return 1

    def idle_add(self, f, *a):
        self.idle.append((f, a))
        return 1


class _Varnost:
    def __init__(self):
        self.oznake = []

    def __getattr__(self, ime):
        if ime.startswith("register_uri_scheme_as_"):
            return lambda shema: self.oznake.append((ime[len("register_uri_scheme_as_"):], shema))
        raise AttributeError(ime)


class _Kontekst:
    def __init__(self):
        self.shema = None
        self.varnost = _Varnost()

    def register_uri_scheme(self, ime, f):
        self.shema = (ime, f)

    def get_security_manager(self):
        return self.varnost


class _Pogled:
    def __init__(self, uri="https://primer.si/", naslov="Primer"):
        self.uri, self.naslov = uri, naslov
        self.konec = 0
        self.nalozeno = []
        self.znova = 0
        self.zvok = False
        self.vidno = False

    def get_uri(self): return self.uri
    def get_title(self): return self.naslov
    def get_favicon(self): return None
    def get_mapped(self): return self.vidno
    def is_loading(self): return False
    def is_playing_audio(self): return self.zvok
    def get_camera_capture_state(self): return 0
    def get_microphone_capture_state(self): return 0
    def get_display_capture_state(self): return 0
    def load_uri(self, uri): self.nalozeno.append(uri)
    def reload(self):
        self.znova += 1
        self.uri, self.naslov = getattr(self, "_prej", (self.uri, self.naslov))

    def terminate_web_process(self):
        self.konec += 1
        self._prej = (self.uri, self.naslov)       # WebKit: seznam nazaj/naprej ostane, naslov pogleda izgine
        self.uri, self.naslov = "", ""

    def get_back_forward_list(self):
        return types.SimpleNamespace(get_current_item=lambda: object())


class _Oznaka:
    def __init__(self, besedilo=""):
        self.besedilo, self.namig, self.razredi = besedilo, "", set()

    def get_text(self): return self.besedilo
    def set_text(self, b): self.besedilo = b
    def set_tooltip_text(self, b): self.namig = b
    def add_css_class(self, r): self.razredi.add(r)
    def remove_css_class(self, r): self.razredi.discard(r)
    def update_property(self, *_a): pass


class _Config:
    def __init__(self, **v):
        self.v = v
        self.config_dir = "/nikjer"

    def get(self, k, privzeto=None):
        return self.v.get(k, privzeto)


class _Splet:
    def __init__(self, **nastavitve):
        self.GLib = _GLib()
        self.WebKit2 = W
        self.Gtk = types.SimpleNamespace(AccessibleProperty=types.SimpleNamespace(DESCRIPTION=1))
        self.kontekst = _Kontekst()
        self.zavihki, self.aktivni, self.aplikacije, self.prenosi = [], None, {}, []
        self.config = _Config(**nastavitve)
        self.jezik = lambda: "sl"
        self.zaprti = []

    def _zavihek(self, pogled):
        return next((z for z in self.zavihki if z["pogled"] is pogled), None)

    def trenutni(self):
        return self.aktivni

    def zapri_zavihek(self, pogled):
        self.zaprti.append(pogled)


def _sestavi(**nastavitve):
    s = _Splet(**nastavitve)
    sp = SpanjeZavihkov(s)
    s.spanje = sp
    return s, sp


def _zavihek(s, sp, uri="https://primer.si/", povezan=None):
    p = _Pogled(uri)
    z = {"pogled": p, "naslov": _Oznaka(p.naslov), "vrstica": _Oznaka(), "ikona": _Oznaka()}
    s.zavihki.append(z)
    sp.nov(z, povezan)
    return p, z


@pytest.fixture(autouse=True)
def _brez_webkit_skript(monkeypatch):
    """nov() poveze skripto stanja in signale - lazni pogled jih nima, zato samo zabelezimo."""
    def nov(self, z, povezan=None):
        self._stevec += 1
        z["spanje"] = {"id": "z%d" % self._stevec, "neaktiven_od": None, "spi": False, "okvirji": {}, "post": False,
                       "post_cakajoc": "", "preusmerjen": False, "povezani": [], "sonda_po": 0.0, "sonde": 0}
        if povezan is not None:
            import weakref
            z["spanje"]["povezani"].append(weakref.ref(povezan))
            oz = self._splet()._zavihek(povezan)
            if oz is not None:
                oz["spanje"]["povezani"].append(weakref.ref(z["pogled"]))
    monkeypatch.setattr(SpanjeZavihkov, "nov", nov)


# ---------------------------------------------------------------- pravila
def test_pravila_spanja():
    osnova = {"uri": "https://primer.si/", "inactive_since": 1.0}
    assert sme_spati(osnova)
    assert sme_spati(dict(osnova, uri="file:///usr/lib/safeer/ui/splet.html"))     # nasa zacetna stran
    for kljuc in ("active", "visible", "audio", "sleeping", "app", "loading", "busy",
                  "media", "form", "post", "download", "capture", "linked"):
        assert not sme_spati(dict(osnova, **{kljuc: True})), kljuc
    assert not sme_spati(dict(osnova, uri="safeer://procesi"))      # nasa stran procesov ne zaspi
    assert not sme_spati(dict(osnova, uri=""))
    assert not sme_spati(dict(osnova, uri="about:blank"))
    assert razlogi_zascite({"form": True, "download": True, "media": True}) == ["media", "form", "download"]
    assert set(razlogi_zascite({k: True for k in processes_page.REASONS})) == set(processes_page.REASONS)


def test_sonda_izbere_jasen_proces():
    assert proces_iz_sonde({1: 100, 2: 50, 3: 7}, {1: 101, 2: 55, 3: 7}) == 2
    assert proces_iz_sonde({1: 100, 2: 50}, {1: 104, 2: 55}) == 0          # dva racunata: ni enoznacno, znova
    assert proces_iz_sonde({1: 100, 2: 50}, {1: 100, 2: 52}) == 0          # premalo
    assert proces_iz_sonde({1: 100}, {1: 100, 9: 900}) == 0                # nov proces (brez »pred«) ne steje
    assert proces_iz_sonde({}, {}) == 0


def test_par_v_nadzoru():
    m = TabMonitor(proc="/nikjer", root_pid=1)
    m.pair("z1", 4242)
    m.pair("z2", 0)
    assert m.pid_of("z1") == 4242 and m.pid_of("z2") == 0
    m.sample([("z1", None, False, False)])            # proces ne obstaja vec: par izgine
    assert m.pid_of("z1") == 0


def test_naslov_uspanega_in_meni():
    p = _Pogled("https://a.si/")
    assert splet_spanje.naslov_pogleda(p) == "https://a.si/"
    p.uri, p._safeer_spi_uri = "", "https://a.si/x"
    assert splet_spanje.naslov_pogleda(p) == "https://a.si/x"
    assert splet_spanje.naslov_menija("de") == "Prozesse"
    assert splet_spanje.naslov_menija(lambda: "sl") == "Procesi"
    assert splet_spanje.naslov_menija("xx") == "Processes"


def test_skripta_stanja_je_veljaven_js():
    node = shutil.which("node")
    if node is None:
        pytest.skip("brez node")
    r = subprocess.run([node, "-e", "new Function(process.argv[1])", splet_spanje.SKRIPTA_STANJA],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert "isTrusted" in splet_spanje.SKRIPTA_STANJA        # samo pravi vpis uporabnika, stran ga ne more ponarediti


# ---------------------------------------------------------------- spanje in zbujanje
def test_uspavaj_in_zbudi():
    s, sp = _sestavi()
    a, za = _zavihek(s, sp)
    b, _zb = _zavihek(s, sp, "https://b.si/")
    s.aktivni = b
    sp.izbran(b)
    assert za["spanje"]["neaktiven_od"] is not None
    assert not sp.uspavaj(_zb, "aktiven")                    # aktiven nikoli
    assert sp.uspavaj(za, "preizkus")
    assert a.konec == 1 and za["spanje"]["spi"]
    assert splet_spanje.naslov_pogleda(a) == "https://primer.si/"
    assert za["naslov"].get_text() == "Primer" and "splet-tab-spi" in za["vrstica"].razredi
    assert not sp.uspavaj(za, "znova")                       # ze spi
    s.aktivni = a
    sp.izbran(a)
    assert a.znova == 1 and not za["spanje"]["spi"] and "splet-tab-spi" not in za["vrstica"].razredi
    assert a.get_uri() == "https://primer.si/"


@pytest.mark.parametrize("nastavi", [
    lambda s, z: setattr(z["pogled"], "zvok", True),
    lambda s, z: setattr(z["pogled"], "vidno", True),
    lambda s, z: z["spanje"]["okvirji"].update(f1=(True, False)),
    lambda s, z: z["spanje"]["okvirji"].update(f1=(False, True)),
    lambda s, z: z["spanje"].update(post=True),
    lambda s, z: z.update(vprasanja=[("x",)]),
    lambda s, z: z.update(drm=object()),
    lambda s, z: s.prenosi.append({"stanje": "tece", "prenos": types.SimpleNamespace(get_web_view=lambda: z["pogled"])}),
])
def test_zasciteni_ne_zaspijo(nastavi):
    s, sp = _sestavi()
    _a, za = _zavihek(s, sp)
    b, _zb = _zavihek(s, sp, "https://b.si/")
    s.aktivni = b
    nastavi(s, za)
    assert not sp.uspavaj(za, "preizkus")
    assert za["pogled"].konec == 0


def test_koncan_prenos_ne_varuje():
    s, sp = _sestavi()
    a, za = _zavihek(s, sp)
    s.aktivni = _zavihek(s, sp, "https://b.si/")[0]
    s.prenosi.append({"stanje": "koncan", "prenos": types.SimpleNamespace(get_web_view=lambda: a)})
    assert sp.uspavaj(za, "preizkus")


def test_povezano_okno_varuje_oba_dokler_sta_odprta():
    s, sp = _sestavi()
    odp, zo = _zavihek(s, sp)
    okno, zk = _zavihek(s, sp, "https://accounts.example/", povezan=odp)
    s.aktivni = _zavihek(s, sp, "https://c.si/")[0]
    assert not sp.uspavaj(zo, "x") and not sp.uspavaj(zk, "x")
    s.zavihki.remove(zk)
    assert sp.uspavaj(zo, "x")


def test_post_samo_brez_preusmeritve():
    s, sp = _sestavi()
    p, z = _zavihek(s, sp, "https://trgovina.si/kosarica")
    zahteva = types.SimpleNamespace(get_uri=lambda: "https://trgovina.si/placaj", get_http_method=lambda: "POST")
    odl = types.SimpleNamespace(get_navigation_action=lambda: types.SimpleNamespace(
        get_request=lambda: zahteva, get_navigation_type=lambda: W.NavigationType.FORM_SUBMITTED))
    assert sp.politika(p, odl, W.PolicyDecisionType.NAVIGATION_ACTION) is False     # odlocitev ostane Spletu
    sp._nalaganje(p, W.LoadEvent.STARTED)
    p.uri = "https://trgovina.si/placaj"
    sp._nalaganje(p, W.LoadEvent.COMMITTED)
    assert z["spanje"]["post"] is True                     # reload bi obrazec poslal znova (izmerjeno)
    sp.politika(p, odl, W.PolicyDecisionType.NAVIGATION_ACTION)
    sp._nalaganje(p, W.LoadEvent.STARTED)
    sp._nalaganje(p, W.LoadEvent.REDIRECTED)               # POST -> 303 -> GET
    p.uri = "https://trgovina.si/hvala"
    sp._nalaganje(p, W.LoadEvent.COMMITTED)
    assert z["spanje"]["post"] is False


def test_neaktiven_10_min_zaspi_razen_ce_je_izklopljeno(monkeypatch):
    s, sp = _sestavi()
    a, za = _zavihek(s, sp)
    s.aktivni = _zavihek(s, sp, "https://b.si/")[0]
    za["spanje"]["neaktiven_od"] = time.monotonic() - 599
    sp._neaktivni(s, time.monotonic())
    assert a.konec == 0
    za["spanje"]["neaktiven_od"] = time.monotonic() - 601
    sp._neaktivni(s, time.monotonic())
    assert a.konec == 1
    s2, sp2 = _sestavi(tab_discard_after_s=0)
    a2, z2 = _zavihek(s2, sp2)
    s2.aktivni = _zavihek(s2, sp2, "https://b.si/")[0]
    z2["spanje"]["neaktiven_od"] = time.monotonic() - 10_000
    sp2._neaktivni(s2, time.monotonic())
    assert a2.konec == 0


def test_tezek_zavihek_v_ozadju_zaspi(monkeypatch):
    s, sp = _sestavi()
    a, za = _zavihek(s, sp)
    b, _zb = _zavihek(s, sp, "https://b.si/")
    s.aktivni = b
    monkeypatch.setattr(sp, "_sondiraj", lambda *_a: None)
    vzorec = types.SimpleNamespace(verdict="hog", active=False, cpu=0.9, rss_mb=1500, pid=7, threads=3)
    monkeypatch.setattr(sp.nadzor, "sample", lambda vrstice: {za["spanje"]["id"]: vzorec})
    sp._nadzor(s)
    assert a.konec == 1
    s2, sp2 = _sestavi(sleep_heavy_background_tabs=False)
    a2, z2 = _zavihek(s2, sp2)
    s2.aktivni = _zavihek(s2, sp2, "https://b.si/")[0]
    monkeypatch.setattr(sp2, "_sondiraj", lambda *_a: None)
    monkeypatch.setattr(sp2.nadzor, "sample", lambda vrstice: {z2["spanje"]["id"]: vzorec})
    sp2._nadzor(s2)
    assert a2.konec == 0


def test_pomanjkanje_pomnilnika_uspava_najstarejse(monkeypatch, tmp_path):
    s, sp = _sestavi()
    star, zs = _zavihek(s, sp, "https://star.si/")
    nov, zn = _zavihek(s, sp, "https://nov.si/")
    s.aktivni = _zavihek(s, sp, "https://c.si/")[0]
    zs["spanje"]["neaktiven_od"], zn["spanje"]["neaktiven_od"] = 10.0, 20.0
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal: 8000000 kB\nMemAvailable: 700000 kB\n")
    resnicni = open
    monkeypatch.setattr("builtins.open", lambda pot, *a, **k: resnicni(meminfo if pot == "/proc/meminfo" else pot, *a, **k))
    sp._pritisk(s)
    assert star.konec == 1 and nov.konec == 0              # manjka ~100 MB: dovolj je najstarejsi (ocena 128 MiB)


# ---------------------------------------------------------------- safeer://procesi
def test_shema_je_lokalna_in_izolirana():
    s, _sp = _sestavi()
    assert s.kontekst.shema[0] == "safeer"
    assert ("local", "safeer") in s.kontekst.varnost.oznake
    assert ("display_isolated", "safeer") in s.kontekst.varnost.oznake
    assert ("no_access", "safeer") not in s.kontekst.varnost.oznake   # nasa stran sicer ne more na svoje povezave


def _odlocitev(naslov, vrsta=W.NavigationType.LINK_CLICKED):
    stanje = {}
    zahteva = types.SimpleNamespace(get_uri=lambda: naslov, get_http_method=lambda: "GET")
    return stanje, types.SimpleNamespace(
        get_navigation_action=lambda: types.SimpleNamespace(get_request=lambda: zahteva,
                                                            get_navigation_type=lambda: vrsta),
        use=lambda: stanje.update(v="use"), ignore=lambda: stanje.update(v="ignore"))


def test_politika_sheme():
    s, sp = _sestavi()
    p, _z = _zavihek(s, sp, "https://napad.example/")
    st, odl = _odlocitev("safeer://procesi?zapri=z1&k=x")
    assert sp.politika(p, odl, W.PolicyDecisionType.NAVIGATION_ACTION) and st["v"] == "ignore"   # spletna stran
    st, odl = _odlocitev("safeer://procesi?zapri=z1&k=x")
    assert sp.politika(p, odl, W.PolicyDecisionType.NEW_WINDOW_ACTION) and st["v"] == "ignore"
    st, odl = _odlocitev("safeer://drugo")
    assert sp.politika(p, odl, W.PolicyDecisionType.NAVIGATION_ACTION) and st["v"] == "ignore"
    s.aktivni = p
    assert sp.odpri_procese("Procesi ") and p.nalozeno[-1] == "safeer://procesi"
    st, odl = _odlocitev("safeer://procesi", W.NavigationType.OTHER)
    assert sp.politika(p, odl, W.PolicyDecisionType.NAVIGATION_ACTION) and st["v"] == "use"      # uporabnik
    st, odl = _odlocitev("safeer://procesi?spi=z1&k=x", W.NavigationType.OTHER)
    assert sp.politika(p, odl, W.PolicyDecisionType.NAVIGATION_ACTION) and st["v"] == "ignore"   # samo enkrat
    p.uri = "safeer://procesi"
    st, odl = _odlocitev("safeer://procesi?spi=z1&k=x")
    assert sp.politika(p, odl, W.PolicyDecisionType.NAVIGATION_ACTION) and st["v"] == "use"      # nasa stran
    st, odl = _odlocitev("https://primer.si/")
    assert sp.politika(p, odl, W.PolicyDecisionType.NAVIGATION_ACTION) is False                   # ni nasa


def test_vpisi_procesov():
    s, sp = _sestavi()
    p, _z = _zavihek(s, sp)
    s.aktivni = p
    for vpis in ("procesi", "safeer://procesi", "SAFEER://PROCESI", "safeer://processes"):
        assert sp.odpri_procese(vpis)
    for vpis in ("procesi linux", "https://procesi.si", "", "safeer://home"):
        assert not sp.odpri_procese(vpis)


class _Zahteva:
    def __init__(self, uri, pogled):
        self.uri, self.pogled = uri, pogled
        self.koncano = self.napaka = None

    def get_uri(self): return self.uri
    def get_web_view(self): return self.pogled
    def finish(self, tok, dolzina, vrsta): self.koncano = (dolzina, vrsta)
    def finish_error(self, napaka): self.napaka = napaka


def test_dejanja_samo_z_enkratnim_kljucem(monkeypatch):
    s, sp = _sestavi()
    s.Gio = types.SimpleNamespace(MemoryInputStream=types.SimpleNamespace(new_from_bytes=lambda b: b))
    sp.GLib.Bytes = types.SimpleNamespace(new=lambda d: d)
    sp.GLib.Error = types.SimpleNamespace(new_literal=lambda *a: a)
    sp.GLib.quark_from_string = lambda x: x
    cilj, zc = _zavihek(s, sp)
    stran, _zs = _zavihek(s, sp, "safeer://procesi")
    s.aktivni = stran
    ident = zc["spanje"]["id"]
    z = _Zahteva("safeer://procesi?spi=%s&k=napacen" % ident, stran)
    sp._obdelaj_zahtevo(z)
    assert z.koncano and cilj.konec == 0                   # brez pravega kljuca: samo seznam
    kljuc = sp._kljuc
    z = _Zahteva("safeer://procesi?spi=%s&k=%s" % (ident, kljuc), stran)
    sp._obdelaj_zahtevo(z)
    assert cilj.konec == 1 and sp._kljuc != kljuc          # kljuc porabljen
    sp.zbudi(zc)
    z = _Zahteva("safeer://procesi?zapri=%s&k=%s" % (ident, kljuc), stran)
    sp._obdelaj_zahtevo(z)
    assert s.GLib.idle == []                               # star kljuc (Nazaj, osvezitev): nic
    z = _Zahteva("safeer://procesi?zapri=%s&k=%s" % (ident, sp._kljuc), stran)
    sp._obdelaj_zahtevo(z)
    assert len(s.GLib.idle) == 1
    s.GLib.idle[0][0]()
    assert s.zaprti == [cilj]
    tuj = _Pogled("https://klepet.example/")              # vdelana aplikacija ali tuj pogled: nic
    z = _Zahteva("safeer://procesi", tuj)
    sp._obdelaj_zahtevo(z)
    assert z.napaka is not None and z.koncano is None
    z = _Zahteva("safeer://home", stran)
    sp._obdelaj_zahtevo(z)
    assert z.napaka is not None


def test_stran_procesov_v_jeziku_spleta():
    s, sp = _sestavi(tab_discard_after_s=900)
    p, _z = _zavihek(s, sp)
    s.aktivni = p
    stran = sp.stran_procesov()
    assert "Procesi" in stran and "15 min" in stran and "Primer" in stran


# ---------------------------------------------------------------- omrezni proces
def _omrezni(monkeypatch, s, sp, pss=500.0):
    klici = []
    import core.os_splet as os_splet
    monkeypatch.setattr(splet_spanje, "RECIKLIRANJE_OMREZNEGA", True)   # v 1.0.129 izklopljeno; logika ostane preizkusena
    monkeypatch.setattr(os_splet, "omrezni_procesi_shrambe", lambda _p: [4321])
    monkeypatch.setattr(os_splet, "pss_mb", lambda _pid: pss)
    monkeypatch.setattr(os_splet, "libsoup_brez_puscanja", lambda: False)    # sistemski libsoup (pusca)
    monkeypatch.setattr(sp, "recikliraj_omrezni", lambda pid, v, ob_koncu=None: klici.append(pid))
    return klici


def _okno(aktivno):
    return types.SimpleNamespace(get_root=lambda: types.SimpleNamespace(get_visible=lambda: True,
                                                                        is_active=lambda: aktivno))


def test_omrezni_samo_med_mirovanjem(monkeypatch):
    s, sp = _sestavi()
    klici = _omrezni(monkeypatch, s, sp)
    s.gradnik = _okno(True)
    assert not sp._omrezni(s, 1000.0)                      # okno v uporabi
    s.gradnik = _okno(False)
    assert not sp._omrezni(s, 1000.0)                      # zacetek mirovanja
    assert not sp._omrezni(s, 1299.0)                      # se ne 5 min
    s.prenosi.append({"stanje": "tece"})
    assert not sp._omrezni(s, 1400.0)                      # prenos
    s.prenosi.clear()
    s.aplikacije[object()] = object()
    assert not sp._omrezni(s, 1400.0)                      # vdelani klepeti
    s.aplikacije.clear()
    p, z = _zavihek(s, sp)
    p.zvok = True
    assert not sp._omrezni(s, 1400.0)                      # zvok
    p.zvok = False
    assert sp._omrezni(s, 1400.0) and klici == [4321]
    s.gradnik = _okno(True)
    assert not sp._omrezni(s, 1500.0) and sp._okno_neaktivno_od is None


def test_omrezni_ne_ob_nasem_libsoup_ali_skritem_pogledu(monkeypatch):
    """Neodvisni pregled OpenAI 1.0.129: recikliranje je koncalo omrezni proces tudi z nasim libsoup (ne pusca, konec pa
    pokvari prvo nalaganje v novem zavihku - lupa 20. 10. 2026) in pod skritim pogledom sprotnih zadetkov lupe."""
    import core.os_splet as os_splet
    s, sp = _sestavi()
    klici = _omrezni(monkeypatch, s, sp)
    s.gradnik = _okno(False)
    sp._omrezni(s, 1000.0)
    s._skriti = lambda: [object()]
    assert not sp._omrezni(s, 1400.0) and klici == []       # skrit pogled lupe zivi
    s._skriti = lambda: []
    monkeypatch.setattr(os_splet, "libsoup_brez_puscanja", lambda: True)
    assert not sp._omrezni(s, 1400.0) and klici == []       # nas libsoup: nikoli
    monkeypatch.setattr(os_splet, "libsoup_brez_puscanja", lambda: False)
    assert sp._omrezni(s, 1400.0) and klici == [4321]       # sistemski libsoup nad mejo: kot prej


def test_omrezni_pod_mejo_ali_izklopljen(monkeypatch):
    s, sp = _sestavi()
    klici = _omrezni(monkeypatch, s, sp, pss=120.0)
    s.gradnik = _okno(False)
    sp._omrezni(s, 0.0)
    assert not sp._omrezni(s, 1000.0) and klici == []      # pod mejo 300 MB
    s2, sp2 = _sestavi(network_process_limit_mb=0)
    klici2 = _omrezni(monkeypatch, s2, sp2)
    s2.gradnik = _okno(False)
    sp2._omrezni(s2, 0.0)
    assert not sp2._omrezni(s2, 1000.0) and klici2 == []


def test_piskotki_seje_se_vrnejo(monkeypatch):
    monkeypatch.setattr(splet_spanje, "RECIKLIRANJE_OMREZNEGA", True)
    s, sp = _sestavi()
    seja_c = types.SimpleNamespace(get_expires=lambda: None)
    trajen = types.SimpleNamespace(get_expires=lambda: object())
    dodani = []
    upr = types.SimpleNamespace(
        get_all_cookies=lambda _c, cb, _u: cb(None, "rezultat"),
        get_all_cookies_finish=lambda r: [seja_c, trajen],
        add_cookie=lambda c, *_a: dodani.append(c))
    s.seja = types.SimpleNamespace(get_cookie_manager=lambda: upr)
    ubiti, casovniki = [], []
    import core.os_splet as os_splet
    monkeypatch.setattr(os_splet, "libsoup_brez_puscanja", lambda: False)
    monkeypatch.setattr(splet_spanje.os, "kill", lambda pid, sig: ubiti.append(pid))
    sp.GLib.timeout_add = lambda _ms, f: casovniki.append(f) or 1
    izid = []
    sp.recikliraj_omrezni(999999, 400.0, ob_koncu=izid.append)
    assert ubiti == [999999] and dodani == []              # najprej konec procesa
    assert casovniki and casovniki[0]() is False           # proces ne obstaja vec: piskotki nazaj
    assert dodani == [seja_c] and izid == [1]              # samo piskotek seje (trajni so v shrambi)
    assert sp._recikliranje is False


def test_recikliranje_preveri_znova_po_branju_piskotkov(monkeypatch):
    monkeypatch.setattr(splet_spanje, "RECIKLIRANJE_OMREZNEGA", True)
    """Ponovni pregled OpenAI 1.0.129 (C): kill je sledil asinhronemu branju piskotkov brez ponovne preverbe - medtem
    je lupa lahko odprla skrit pogled (ali se je zagnala vdelana aplikacija) in proces bi se koncal pod njim."""
    import core.os_splet as os_splet
    monkeypatch.setattr(os_splet, "libsoup_brez_puscanja", lambda: False)
    for zamenjaj in ("skrit", "aplikacija"):
        s, sp = _sestavi()
        cakajo = []
        upr = types.SimpleNamespace(get_all_cookies=lambda _c, cb, _u: cakajo.append(cb),
                                    get_all_cookies_finish=lambda r: [], add_cookie=lambda *_a: None)
        s.seja = types.SimpleNamespace(get_cookie_manager=lambda: upr)
        ubiti = []
        monkeypatch.setattr(splet_spanje.os, "kill", lambda pid, sig: ubiti.append(pid))
        sp.recikliraj_omrezni(999999, 400.0)
        assert cakajo and sp._recikliranje is True
        if zamenjaj == "skrit":
            s._skriti = lambda: [object()]                    # med cakanjem lupa odpre skrit pogled
        else:
            s.aplikacije[object()] = object()
        cakajo[0](None, "rezultat")
        assert ubiti == [] and sp._recikliranje is False, zamenjaj


def test_v_129_varuh_ne_konca_omreznega_procesa(monkeypatch):
    """Ponovni pregled OpenAI F: v 1.0.129 nobena pot ne konca omreznega procesa (dva Spleta z isto shrambo piskotkov)."""
    import core.os_splet as os_splet
    assert splet_spanje.RECIKLIRANJE_OMREZNEGA is False
    s, sp = _sestavi()
    monkeypatch.setattr(os_splet, "omrezni_procesi_shrambe", lambda _p: [4321])
    monkeypatch.setattr(os_splet, "pss_mb", lambda _pid: 5000.0)
    monkeypatch.setattr(os_splet, "libsoup_brez_puscanja", lambda: False)
    klici = []
    monkeypatch.setattr(sp, "recikliraj_omrezni", lambda pid, v, ob_koncu=None: klici.append(pid))
    s.gradnik = _okno(False)
    sp._omrezni(s, 0.0)
    assert not sp._omrezni(s, 10000.0) and klici == []


def test_novi_moduli_v_tovoru_safeer_os():
    with open(os.path.join(KOREN, "packaging", "install_os_payload.sh"), encoding="utf-8") as f:
        tovor = f.read()
    for modul in ("splet_spanje", "processes_page", "tab_monitor", "tab_lifecycle"):
        assert " %s " % modul in tovor, modul
