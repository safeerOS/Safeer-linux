"""Ucenje strani brez pospesevanja po padcu (core/os_splet.nauci_po_padcu, Splet in Safeer Browser GTK4)."""


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
