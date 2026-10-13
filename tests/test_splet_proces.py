"""Proces strani se sesuje ali preseze mejo pomnilnika: Splet stran nalozi znova ali razlozi (ne ostane bela)."""
import types

from core import os_splet, pomnilnik


def test_meja_sprostitve():
    assert pomnilnik.meja_sprostitve_mb(12 * 1024) == 1536
    assert pomnilnik.meja_sprostitve_mb(4096) == 768
    assert pomnilnik.meja_sprostitve_mb() == pomnilnik.meja_strani_mb() // 2


def test_meja_strani():
    assert pomnilnik.meja_strani_mb(4096) == 1536
    assert pomnilnik.meja_strani_mb(12 * 1024) == 3072
    assert pomnilnik.meja_strani_mb(64 * 1024) == 4096
    assert 1536 <= pomnilnik.meja_strani_mb() <= 4096


class _Nastavitve:
    def __init__(self):
        self.v = {}

    def set_memory_limit(self, x): self.v["meja"] = x
    def set_kill_threshold(self, x): self.v["ubij"] = x
    def set_poll_interval(self, x): self.v["poll"] = x


def test_tlak_z_ubijanjem():
    n = _Nastavitve()
    W = types.SimpleNamespace(MemoryPressureSettings=types.SimpleNamespace(new=lambda: n))
    assert pomnilnik.tlak_webkit(W, 350, 3500) is n
    assert n.v == {"meja": 350, "ubij": 10.0, "poll": 5.0}
    n2 = _Nastavitve()
    W2 = types.SimpleNamespace(MemoryPressureSettings=types.SimpleNamespace(new=lambda: n2))
    pomnilnik.tlak_webkit(W2, 220)
    assert "ubij" not in n2.v          # brez ubij_mb kot prej


class _Pogled:
    def __init__(self, uri):
        self.uri, self.znova, self.html = uri, 0, None

    def get_uri(self): return self.uri
    def reload(self): self.znova += 1
    def load_alternate_html(self, html, uri, _b): self.html = (html, uri)


def _splet():
    s = object.__new__(os_splet.VdelaniSplet)
    s.jezik = lambda: "sl"
    return s


def test_razlaga_ob_odpovedi():
    s, p = _splet(), _Pogled("https://primer.si/stran")
    s._proces_koncan(p, "pomnilnik")
    assert p.html[1] == "https://primer.si/stran"
    assert "Naloži znova" in p.html[0] and 'href="https://primer.si/stran"' in p.html[0]
    q = _Pogled("about:blank")
    s._proces_koncan(q, "sesutje")
    assert q.html is None


class _Ura:
    t = 0.0

    def __call__(self):
        return self.t


def test_pomnilnik_le_enkrat_znova(monkeypatch):
    from core import os_stabilnost as st
    monkeypatch.setattr(st, "zapisi", lambda *a, **k: None)
    ura = _Ura()
    o = st.ObnovaPogleda("x", "y", ura=ura)
    assert o.odlocitev("pomnilnik") is True
    ura.t = 60
    assert o.odlocitev("pomnilnik") is False          # drugic v 10 min: razlaga, ne vrtenje v krogu
    assert o.odlocitev("sesutje") is True             # sesutje se vedno do NAJVEC_OBNOV
    ura.t = 60 + st.OKNO_SESUTIJ_S + 1
    assert o.odlocitev("pomnilnik") is True           # po oknu spet


def test_ob_odpovedi_klican(monkeypatch):
    import types
    from core import os_stabilnost as st
    monkeypatch.setattr(st, "zapisi", lambda *a, **k: None)
    W = types.SimpleNamespace(WebProcessTerminationReason=types.SimpleNamespace(CRASHED=0, EXCEEDED_MEMORY_LIMIT=1, TERMINATED_BY_API=2))
    klici, znova = [], []
    G = types.SimpleNamespace(timeout_add=lambda ms, f: znova.append(f))

    class P:
        def connect(self, ime, f): self.f = f
        def reload(self): pass
    p = P()
    st.obnovi_ob_padcu(W, G, p, "x", "y", ob_odpovedi=lambda pg, r: klici.append(r))
    p.f(p, 1); p.f(p, 1); p.f(p, 2)
    assert len(znova) == 1 and klici == ["pomnilnik"]


def test_stran_ubezi_znake():
    h = os_splet.stran_procesa_koncana("<b>", "a&b", "x", 'https://e.si/"><script>')
    assert "<b>" not in h and "&lt;b&gt;" in h and "<script>" not in h


def test_predpomnilnik_strani_vklopljen():
    import inspect
    koda = inspect.getsource(os_splet.VdelaniSplet._nov_pogled)
    assert "set_enable_page_cache(True)" in koda and "set_enable_page_cache(False)" not in koda


def test_brez_pospesevanja_seznam():
    assert os_splet.brez_pospesevanja("https://www.24ur.com/novice") is True
    assert os_splet.brez_pospesevanja("https://24ur.com/") is True
    assert os_splet.brez_pospesevanja("https://ne24ur.com/") is False
    assert os_splet.brez_pospesevanja("https://www.rtvslo.si/") is False
    assert os_splet.brez_pospesevanja("https://x.primer.si/", ["primer.si"]) is True
    assert os_splet.brez_pospesevanja("about:blank") is False


class _Nast:
    def __init__(self): self.p = "ALWAYS"
    def get_hardware_acceleration_policy(self): return self.p
    def set_hardware_acceleration_policy(self, p): self.p = p


class _PogledN(_Pogled):
    def __init__(self, uri):
        super().__init__(uri); self.n = _Nast()
    def get_settings(self): return self.n


class _Cfg(dict):
    def set(self, k, v): self[k] = v


def _splet_w():
    import types
    s = object.__new__(os_splet.VdelaniSplet)
    s.WebKit2 = types.SimpleNamespace(
        HardwareAccelerationPolicy=types.SimpleNamespace(NEVER="NEVER", ALWAYS="ALWAYS"),
        WebProcessTerminationReason=types.SimpleNamespace(CRASHED=0, EXCEEDED_MEMORY_LIMIT=1, TERMINATED_BY_API=2))
    s.config = _Cfg()
    return s


def test_zelena_politika():
    s = _splet_w()
    assert s._zelena_politika("https://www.24ur.com/") == "NEVER"
    assert s._zelena_politika("https://www.rtvslo.si/") == "ALWAYS"
    s.config["hardware_acceleration"] = "never"
    assert s._zelena_politika("https://www.rtvslo.si/") == "NEVER"


class _Box:
    def __init__(self): self.otroci = []
    def reorder_child(self, o, i): self.otroci.remove(o); self.otroci.insert(i, o)
    def remove(self, o): self.otroci.remove(o)


def test_zamenjava_zavihka_na_istem_mestu():
    s = _splet_w()
    s.skatla_zavihkov, s.sklad = _Box(), _Box()
    izbran = []
    s.izberi = lambda p: izbran.append(p)
    s.trenutni = lambda: izbran[-1] if izbran else None
    s.zavihki = []

    def nov_zavihek(naslov):
        p = _PogledN(naslov); p.n.p = getattr(s, "_naslednja_politika", None) or "ALWAYS"; p.destroy = lambda: None
        d = object(); s.skatla_zavihkov.otroci.append(d); s.sklad.otroci.append(p)
        s.zavihki.append({"pogled": p, "dogodek": d}); return p
    s.nov_zavihek = nov_zavihek
    a = nov_zavihek("https://www.rtvslo.si/"); b = nov_zavihek("https://github.com/")
    assert s._zamenjaj_za_pospesevanje(a, "https://www.rtvslo.si/novice") is False       # isti izris: nic
    assert s._zamenjaj_za_pospesevanje(a, "https://www.24ur.com/") is True
    nov = s.zavihki[0]["pogled"]
    assert nov is not a and nov.uri == "https://www.24ur.com/" and nov.n.p == "NEVER"
    assert [z["pogled"] for z in s.zavihki] == [nov, b] and len(s.skatla_zavihkov.otroci) == 2
    assert izbran[-1] is nov and s._naslednja_politika is None


def test_pomnilnik_nauci_stran():
    import types
    s = _splet_w()
    zamenjave = []
    s.GLib = types.SimpleNamespace(idle_add=lambda f: f())
    s._zamenjaj_za_pospesevanje = lambda p, u: zamenjave.append(u)
    p = _PogledN("https://novice.primer.si/clanek")
    s._proces_pomnilnik(p, 0)                                          # sesutje: nic
    assert "splet_brez_pospesevanja" not in s.config and p.n.p == "ALWAYS"
    s._proces_pomnilnik(p, 1)                                          # pomnilnik: zapomni in zamenja zavihek
    assert s.config["splet_brez_pospesevanja"] == ["novice.primer.si"] and len(zamenjave) == 1
    s._proces_pomnilnik(p, 1)
    assert s.config["splet_brez_pospesevanja"] == ["novice.primer.si"]   # ne podvaja


def test_varuh_sesutje_takoj_po_ubijanju_je_pomnilnik():
    import time, types
    s = _splet_w()
    s.GLib = types.SimpleNamespace(idle_add=lambda f: None)
    p = _PogledN("https://puscajoca.primer.si/")
    s._varuh_ubil = time.monotonic()
    s._proces_pomnilnik(p, 0)                       # CRASHED, ker ga je ubil varuh
    assert s.config["splet_brez_pospesevanja"] == ["puscajoca.primer.si"]
    q = _PogledN("https://drugo.primer.si/")
    s._varuh_ubil = time.monotonic() - 60
    s._proces_pomnilnik(q, 0)                       # navadno sesutje: ne ucimo
    assert s.config["splet_brez_pospesevanja"] == ["puscajoca.primer.si"]
