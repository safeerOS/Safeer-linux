"""Poizvedbe DoH tecejo na stalnih nitih (topla povezava), ne v niti vsake povezave brskalnika."""
import threading

from core.doh_proxy import DoHResolver


def test_hkratne_poizvedbe_istega_imena_ena():
    r = DoHResolver()
    klici = []

    def lazna(h, timeout):
        klici.append(h)
        threading.Event().wait(0.1)
        return "93.184.216.34", 300

    r._query_doh = lazna
    niti = [threading.Thread(target=r.resolve, args=("isto.example.com",)) for _ in range(10)]
    [t.start() for t in niti]; [t.join() for t in niti]
    assert klici == ["isto.example.com"]


def test_napaka_delavca_je_neuspela_poizvedba():
    r = DoHResolver()

    def pade(h, timeout):
        raise RuntimeError("x")

    r._query_doh = pade
    assert r.resolve("napaka.example.com") is None


def test_zastavica_idempotent_v_kodi():
    import inspect
    from core import doh_proxy
    assert "MessageFlags.IDEMPOTENT" in inspect.getsource(doh_proxy._ZankaDoH.poslji)


def test_poizvedba_gre_skozi_eno_zanko(monkeypatch):
    from core import doh_proxy
    poslano = []

    class Lazna:
        def poslji(self, url, telo, timeout):
            poslano.append(url)
            return None

    monkeypatch.setattr(doh_proxy, "_zanka_doh", lambda: Lazna())
    r = DoHResolver()
    assert r._poizvedba("a.example.com", 1.0) == (None, 15)
    assert poslano == [doh_proxy.DOH_PROVIDERS["cloudflare"]["url"]]


import time as _time


def test_star_naslov_takoj_in_osvezitev_v_ozadju():
    r = DoHResolver()
    klici = []

    def lazna(h, timeout):
        klici.append(h)
        return "198.51.100.7", 300

    r._query_doh = lazna
    r._cache["star.example.com"] = ("203.0.113.5", _time.time() - 10)   # iztekel pred 10 s
    t = _time.perf_counter()
    assert r.resolve("star.example.com") == "203.0.113.5"            # star, takoj
    assert _time.perf_counter() - t < 0.05
    for _ in range(50):
        if r._cache["star.example.com"][0] == "198.51.100.7":
            break
        _time.sleep(0.02)
    assert r._cache["star.example.com"][0] == "198.51.100.7" and klici == ["star.example.com"]


def test_prestar_naslov_ni_uporabljen():
    r = DoHResolver()
    r._query_doh = lambda h, t: ("198.51.100.8", 300)
    r._cache["zelo.example.com"] = ("203.0.113.5", _time.time() - DoHResolver.STARO_S - 5)
    assert r.resolve("zelo.example.com") == "198.51.100.8"


def test_neuspela_osvezitev_obdrzi_star_naslov():
    r = DoHResolver()
    r._query_doh = lambda h, t: (None, 15)
    r._cache["x.example.com"] = ("203.0.113.5", _time.time() - 1)
    assert r.resolve("x.example.com") == "203.0.113.5"
    _time.sleep(0.2)
    assert r._cache["x.example.com"][0] == "203.0.113.5"


def test_povezava_na_star_naslov_ne_uspe_novo_razresevanje(monkeypatch):
    import socket
    from core import doh_proxy
    from core.doh_proxy import LocalDoHProxy
    monkeypatch.setattr(doh_proxy, "je_dovoljen_cilj", lambda n, l=False: True)   # zanka 127.0.0.x samo v preizkusu
    streznik = socket.socket(); streznik.bind(("127.0.0.1", 0)); streznik.listen(1)
    vrata = streznik.getsockname()[1]
    r = DoHResolver()
    r._query_doh = lambda h, t: ("127.0.0.1", 300)
    p = LocalDoHProxy(r, dovoli_lokalno=True)
    a, b = socket.socketpair()
    try:
        s = p._povezi_z_osvezitvijo(a, "t.example.com", "127.0.0.2", vrata)   # 127.0.0.2:vrata - nihce ne poslusa
        assert s is not None and s.getpeername()[0] == "127.0.0.1"
        s.close()
    finally:
        a.close(); b.close(); streznik.close()


def test_isti_naslov_ne_poskusa_znova(monkeypatch):
    import socket
    from core import doh_proxy
    monkeypatch.setattr(doh_proxy, "je_dovoljen_cilj", lambda n, l=False: True)
    r = DoHResolver()
    r._query_doh = lambda h, t: ("127.0.0.2", 300)
    p = doh_proxy.LocalDoHProxy(r, dovoli_lokalno=True)
    klici = []
    resnicna = socket.create_connection
    monkeypatch.setattr(doh_proxy.socket, "create_connection", lambda *a, **k: (klici.append(a), resnicna(*a, **k))[1])
    a, b = socket.socketpair()
    try:
        assert p._povezi_z_osvezitvijo(a, "t.example.com", "127.0.0.2", 9) is None
        assert len(klici) == 1
        assert b.recv(100).startswith(b"HTTP/1.1 502")
    finally:
        a.close(); b.close()
