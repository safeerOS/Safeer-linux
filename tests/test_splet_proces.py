"""Proces strani se sesuje ali preseze mejo pomnilnika: Splet stran nalozi znova ali razlozi (ne ostane bela)."""
import types

from core import os_splet, pomnilnik


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
    s.WebKit2 = types.SimpleNamespace(WebProcessTerminationReason=types.SimpleNamespace(
        CRASHED=0, EXCEEDED_MEMORY_LIMIT=1, TERMINATED_BY_API=2))
    s.GLib = types.SimpleNamespace(idle_add=lambda f: f())
    s.jezik = lambda: "sl"
    return s


def test_prvic_znova_drugic_razlaga():
    s, p = _splet(), _Pogled("https://primer.si/stran")
    s._proces_koncan(p, 1)
    assert p.znova == 1 and p.html is None
    s._proces_koncan(p, 1)                          # v 30 s spet: ne vrtimo se v krogu
    assert p.znova == 1 and p.html[1] == "https://primer.si/stran"
    assert "Naloži znova" in p.html[0] and 'href="https://primer.si/stran"' in p.html[0]


def test_api_in_interne_strani_brez_ukrepa():
    s = _splet()
    p = _Pogled("https://primer.si/")
    s._proces_koncan(p, 2)                          # ustavili smo ga sami
    q = _Pogled("about:blank")
    s._proces_koncan(q, 0)
    assert p.znova == q.znova == 0 and p.html is None and q.html is None


def test_stran_ubezi_znake():
    h = os_splet.stran_procesa_koncana("<b>", "a&b", "x", 'https://e.si/"><script>')
    assert "<b>" not in h and "&lt;b&gt;" in h and "<script>" not in h
