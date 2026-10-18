"""Safeer DRM je od 1.0.127 v paketu: ob zagonu se nic ne prenese vnaprej, v ozadju se samo pospravi stara kopija."""
import threading

from core import safeer_drm


def _pocakaj(ime: str) -> None:
    for t in threading.enumerate():
        if t.name == ime:
            t.join(5)


def test_ni_vec_prenosa_vnaprej():
    """Prej je pripravi_vnaprej() 45 s po zagonu tiho prenesel ~120 MB (lastnik, 18. 10. 2026: nic med delovanjem)."""
    assert not hasattr(safeer_drm, "pripravi_vnaprej")
    assert not hasattr(safeer_drm, "prenesi")


def test_v_ozadju_samo_pospravi(monkeypatch):
    klici = []
    monkeypatch.setattr(safeer_drm, "pospravi_staro", lambda *a, **k: klici.append(a) or [])
    safeer_drm.pospravi_staro_v_ozadju()
    _pocakaj("safeer-drm-selitev")
    assert klici == [()]


def test_napaka_pri_pospravljanju_ne_ustavi_zagona(monkeypatch):
    def napaka(*_a, **_k):
        raise OSError("samo za branje")
    monkeypatch.setattr(safeer_drm, "pospravi_staro", napaka)
    safeer_drm.pospravi_staro_v_ozadju()
    _pocakaj("safeer-drm-selitev")
