"""Safeer Browser: stran s seznama puscanja (24ur.com) v novem zavihku z izrisom brez pospesevanja - funkcijo beremo iz
safeer_mint.py brez uvoza modula (ta ob uvozu zahteva GTK)."""
import ast
import os
import textwrap
import types

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _funkcija():
    drevo = ast.parse(open(os.path.join(KOREN, "safeer_mint.py"), encoding="utf-8").read())
    for razred in drevo.body:
        if isinstance(razred, ast.ClassDef) and razred.name == "SafeerMintBrowser":
            for f in razred.body:
                if isinstance(f, ast.FunctionDef) and f.name == "zamenjaj_za_pospesevanje":
                    return textwrap.dedent(ast.get_source_segment(open(os.path.join(KOREN, "safeer_mint.py"), encoding="utf-8").read(), f))
    raise AssertionError("ni funkcije")


class _Nast:
    def __init__(self, p): self.p = p
    def get_hardware_acceleration_policy(self): return self.p


class _Pogled:
    def __init__(self, p): self.n = _Nast(p)
    def get_settings(self): return self.n


def test_zamenjava_zavihka():
    W = types.SimpleNamespace(HardwareAccelerationPolicy=types.SimpleNamespace(NEVER="NEVER", ALWAYS="ALWAYS"))
    G = types.SimpleNamespace(idle_add=lambda f: f())
    ns = {"WebKit2": W, "GLib": G}
    exec(_funkcija(), ns)
    zamenjaj = ns["zamenjaj_za_pospesevanje"]

    class Box:
        def __init__(self): self.o = []
        def reorder_child(self, x, i): self.o.remove(x); self.o.insert(i, x)

    b = types.SimpleNamespace(config={}, tabs=[], tabs_box=Box(), closed_tabs_stack=[], zaprti=[])
    nast = {"splet_skia_kompozitor": True}       # pri Skia kompozitorju velja staticni seznam (24ur.com)
    b.config = types.SimpleNamespace(get=lambda k, d=None: nast.get(k, d))

    def new_tab(uri, switch=True):
        tid = "t%d" % (len(b.tabs) + 10)
        pol = getattr(b, "_naslednja_politika", None) or "ALWAYS"
        t = {"id": tid, "webview": _Pogled(pol), "event_box": object(), "uri": uri}
        b.tabs.append(t); b.tabs_box.o.append(t["event_box"]); return tid

    def close_tab(tid):
        t = next(x for x in b.tabs if x["id"] == tid)
        b.closed_tabs_stack.append({"uri": t["uri"]}); b.tabs.remove(t); b.tabs_box.o.remove(t["event_box"]); b.zaprti.append(tid)

    b.new_tab, b.close_tab = new_tab, close_tab
    prvi = new_tab("https://www.rtvslo.si/"); drugi = new_tab("https://github.com/")
    pogled = b.tabs[0]["webview"]
    assert zamenjaj(b, pogled, "https://www.rtvslo.si/novice") is False
    assert zamenjaj(b, pogled, "https://www.24ur.com/") is True
    assert [t["uri"] for t in b.tabs] == ["https://www.24ur.com/", "https://github.com/"]
    assert b.tabs[0]["webview"].n.p == "NEVER" and b.zaprti == [prvi] and b.closed_tabs_stack == []
    assert getattr(b, "_naslednja_politika", None) is None


def test_texturemapper_24ur_ostane_pospesen():
    W = types.SimpleNamespace(HardwareAccelerationPolicy=types.SimpleNamespace(NEVER="NEVER", ALWAYS="ALWAYS"))
    ns = {"WebKit2": W, "GLib": types.SimpleNamespace(idle_add=lambda f: f())}
    exec(_funkcija(), ns)
    b = types.SimpleNamespace(tabs=[], config=types.SimpleNamespace(get=lambda k, d=None: d))
    assert ns["zamenjaj_za_pospesevanje"](b, _Pogled("ALWAYS"), "https://www.24ur.com/") is False


def test_brskalnik_ima_izboljsave_spleta():
    """Parity s Spletom (lastnik, 14. 10. 2026): meja procesa strani, varuh, ucenje, obnova, bfcache, predpomnilnik."""
    import os
    koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(koren, "safeer_mint.py"), encoding="utf-8") as f:
        koda = f.read()
    assert "GLib.timeout_add_seconds(5, self._varuh_tik)" in koda
    assert "splet_varuh.preglej(" in koda
    assert "nauci_po_padcu(" in koda and "ucene_brez_pospesevanja(self.config)" in koda
    assert "os_stabilnost.obnovi_ob_padcu(" in koda and "ob_odpovedi=" in koda
    assert "set_enable_page_cache(True)" in koda and "set_enable_page_cache(False)" not in koda
    assert "self._omeji_predpomnilnik()" in koda and "splet_predpomnilnik_meja_mb" in koda


def test_nauci_po_padcu():
    import types
    from core.os_splet import nauci_po_padcu
    R = types.SimpleNamespace(EXCEEDED_MEMORY_LIMIT=2, CRASHED=0, TERMINATED_BY_API=1)
    W = types.SimpleNamespace(WebProcessTerminationReason=R)
    assert nauci_po_padcu(W, 2, "https://a.primer.si/x", [], False, 99) == ["a.primer.si"]
    assert nauci_po_padcu(W, 0, "https://a.primer.si/x", [], False, 2) == ["a.primer.si"]   # varuh pred 2 s
    assert nauci_po_padcu(W, 0, "https://a.primer.si/x", [], False, 30) is None             # navadno sesutje
    assert nauci_po_padcu(W, 1, "https://a.primer.si/x", [], False, 0) is None              # API (spanje)
    assert nauci_po_padcu(W, 2, "https://a.primer.si/x", ["primer.si"], False, 99) is None  # ze na seznamu
    assert len(nauci_po_padcu(W, 2, "https://z.si", ["d%d.si" % i for i in range(60)], False, 99)) == 50
