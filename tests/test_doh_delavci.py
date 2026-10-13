"""Poizvedbe DoH tecejo na stalnih nitih (topla povezava), ne v niti vsake povezave brskalnika."""
import threading

from core.doh_proxy import DoHResolver


def test_poizvedbe_na_stalnih_nitih():
    r = DoHResolver()
    niti = []

    def lazna(h, timeout):
        niti.append(threading.current_thread().name)
        return "93.184.216.34", 300

    r._query_doh = lazna
    for i in range(10):
        t = threading.Thread(target=r.resolve, args=(f"s{i}.example.com",))
        t.start(); t.join()
    assert len(niti) == 10
    assert all(n.startswith("safeer-doh") for n in niti)
    assert len(set(niti)) <= DoHResolver.DELAVCEV


def test_napaka_delavca_je_neuspela_poizvedba():
    r = DoHResolver()

    def pade(h, timeout):
        raise RuntimeError("x")

    r._query_doh = pade
    assert r.resolve("napaka.example.com") is None


def test_zastavica_idempotent_v_kodi():
    import inspect
    from core import doh_proxy
    assert "MessageFlags.IDEMPOTENT" in inspect.getsource(doh_proxy.DoHResolver._poizvedba)
