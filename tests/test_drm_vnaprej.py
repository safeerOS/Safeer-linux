"""Safeer DRM je vdelan: po zagonu se paket tiho prenese vnaprej."""
from core import safeer_drm


def test_pripravi_vnaprej_prenese_ce_ni(monkeypatch):
    klici = []
    monkeypatch.setattr(safeer_drm, "izvrsljiva", lambda: None)
    monkeypatch.setattr(safeer_drm, "prenesi", lambda *a, **k: klici.append(1) or True)
    safeer_drm.pripravi_vnaprej(0)
    import threading
    for t in threading.enumerate():
        if t.name == "safeer-drm-vnaprej":
            t.join(5)
    assert klici == [1]


def test_pripravi_vnaprej_ne_prenasa_ce_je(monkeypatch):
    klici = []
    monkeypatch.setattr(safeer_drm, "izvrsljiva", lambda: object())
    monkeypatch.setattr(safeer_drm, "prenesi", lambda *a, **k: klici.append(1) or True)
    safeer_drm.pripravi_vnaprej(0)
    import threading
    for t in threading.enumerate():
        if t.name == "safeer-drm-vnaprej":
            t.join(5)
    assert klici == []
