"""Vgradnja zajema KMS v core/link_zaslon.py: lazen pomocnik na Unix vticniku, brez ffmpeg.

Lazen pomocnik za vsako povezavo vzame naslednji odgovor s seznama: "ok" (fd s pretokom,
"zajem" tece, dokler klicatelj ne zapre vticnika), "ok_konec" (ok, nato "ffmpeg" takoj konca)
ali besedilo napake. Lazen x11grab je kratek Python, ki izpise oznako X11 in caka.
Pozeni iz korena projekta: python3 -m pytest -q tests/test_link_zaslon_kms.py
"""

from __future__ import annotations

import io
import itertools
import json
import os
import signal
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import link_zaslon as lz  # noqa: E402

KMS_PRETOK = b"\x00\x00\x00\x01KMS"
X11_PRETOK = b"\x00\x00\x00\x01X11"
ZAHTEVA = {"sirina": 1920, "visina": 1080, "fps": 60, "kodek": "h264", "qp": 16}
LAZNI_X11 = [sys.executable, "-c",
             "import sys, time; sys.stdout.buffer.write(%r); sys.stdout.flush(); time.sleep(30)"
             % X11_PRETOK]
#: Pravi pretok ima veliko enot NAL; ena sama enota skrije, ali se stari pretok res zavrze
#: (zadrzi jo ze _rep), zato preizkusi KMS-2 uporabijo tri.
KMS_VEC_NAL = KMS_PRETOK + b"\x00\x00\x01KMS2" + b"\x00\x00\x01KMS3"


class LazniPomocnik:
    def __init__(self, pot: str, odgovori, pretok: bytes = KMS_PRETOK) -> None:
        self.pretok = pretok
        self.odgovori = list(odgovori)
        self.zahteve = []
        #: Nastavi se, ko klicatelj zapre vticnik in "ffmpeg" konca.
        self.ustavljen = threading.Event()
        self.posluh = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.posluh.bind(pot)
        self.posluh.listen(8)
        threading.Thread(target=self._streci, daemon=True).start()

    def _streci(self) -> None:
        while self.odgovori:
            try:
                povezava, _ = self.posluh.accept()
            except OSError:
                return
            odgovor = self.odgovori.pop(0)
            povezava.settimeout(5)
            zahteva = b""
            while not zahteva.endswith(b"\n"):
                kos = povezava.recv(512)
                if not kos:
                    break
                zahteva += kos
            self.zahteve.append(json.loads(zahteva))
            if odgovor in ("ok", "ok_konec"):
                bralni, pisalni = os.pipe()
                socket.send_fds(povezava, [b"ok\n"], [bralni])
                os.close(bralni)
                if odgovor == "ok_konec":
                    os.close(pisalni)
                    povezava.close()
                    continue
                os.write(pisalni, self.pretok)
                threading.Thread(target=self._drzi, args=(povezava, pisalni), daemon=True).start()
            else:
                povezava.sendall(odgovor.encode("utf-8") + b"\n")
                povezava.close()

    def _drzi(self, povezava: socket.socket, pisalni: int) -> None:
        # Kot pravi pomocnik: zajem tece, dokler klicatelj ne zapre vticnika.
        povezava.settimeout(None)
        try:
            while povezava.recv(64):
                pass
        except OSError:
            pass
        os.close(pisalni)
        povezava.close()
        self.ustavljen.set()

    def zapri(self) -> None:
        try:
            self.posluh.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.posluh.close()


@pytest.fixture
def okolje(tmp_path, monkeypatch):
    pot = str(tmp_path / "kms.sock")
    monkeypatch.setattr(lz, "KMS_VTICNIK", pot)
    pomocniki, slike = [], []

    def pomocnik(*odgovori, pretok=KMS_PRETOK):
        p = LazniPomocnik(pot, odgovori, pretok)
        pomocniki.append(p)
        return p

    def zazeni_x11():
        return subprocess.Popen(LAZNI_X11, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL, bufsize=0)

    yield pomocnik, zazeni_x11, slike
    for s in slike:
        s.kill()
    for p in pomocniki:
        p.zapri()


def beri_do(slika, oznaka: bytes) -> bytes:
    zbrano = b""
    while oznaka not in zbrano:
        kos = slika.stdout.read(64)
        if not kos:
            break
        zbrano += kos
    return zbrano


def test_ok_in_fd_zajem_prek_kms(okolje, capsys):
    pomocnik, zazeni_x11, slike = okolje
    lazni = pomocnik("ok")
    slika, na_kms = lz.odpri_sliko(zazeni_x11, dict(ZAHTEVA), seja=7)
    slike.append(slika)
    assert na_kms is True
    assert lazni.zahteve == [{"w": 1920, "h": 1080, "fps": 60, "kodek": "h264", "qp": 16}]
    assert slika.stdout.read(64) == KMS_PRETOK
    assert slika.poll() is None
    kms = slika._p
    with pytest.raises(subprocess.TimeoutExpired):
        kms.wait(timeout=0.05)
    slika.terminate()
    assert kms.returncode == -signal.SIGKILL
    assert slika.stdout.read(64) == b""          # pomocnik je ustavil "ffmpeg": EOF
    assert lazni.ustavljen.wait(2)
    assert "dogodek=kms_odprt t_ms=" in capsys.readouterr().err


def test_wayland_ostane_x11grab(okolje, capsys):
    pomocnik, zazeni_x11, slike = okolje
    pomocnik("napaka: seja wayland (kms samo x11)")
    slika, na_kms = lz.odpri_sliko(zazeni_x11, dict(ZAHTEVA), seja=7)
    slike.append(slika)
    assert na_kms is False
    assert beri_do(slika, b"X11") == X11_PRETOK
    err = capsys.readouterr().err
    assert "dogodek=kms_zavrnjen" in err and "razlog=seja_wayland_(kms_samo_x11)" in err


def test_brez_vticnika_ostane_x11grab(okolje, capsys):
    _, zazeni_x11, slike = okolje           # pomocnika ni: vticnik ne obstaja
    slika, na_kms = lz.odpri_sliko(zazeni_x11, dict(ZAHTEVA), seja=7)
    slike.append(slika)
    assert na_kms is False
    assert beri_do(slika, b"X11") == X11_PRETOK
    assert "razlog=ni_pomocnika" in capsys.readouterr().err


def test_brez_zahteve_kms_pomocnika_ne_vprasa(okolje, capsys):
    pomocnik, zazeni_x11, slike = okolje
    lazni = pomocnik("ok")
    slika, na_kms = lz.odpri_sliko(zazeni_x11, None, seja=7)
    slike.append(slika)
    assert na_kms is False
    assert beri_do(slika, b"X11") == X11_PRETOK
    assert lazni.zahteve == []
    assert "kms_" not in capsys.readouterr().err


def test_ffmpeg_takoj_konca_ostane_x11grab(okolje, capsys):
    pomocnik, zazeni_x11, slike = okolje
    pomocnik("ok_konec")
    slika, na_kms = lz.odpri_sliko(zazeni_x11, dict(ZAHTEVA), seja=7)
    slike.append(slika)
    assert na_kms is False
    assert beri_do(slika, b"X11") == X11_PRETOK
    assert "razlog=ffmpeg_koncal" in capsys.readouterr().err


def test_kms7_idr_na_kms_ne_sprasuje_pomocnika_ostane_stari(okolje, capsys):
    # Pomocnik dovoli en zajem: nov zahtevek med zajemom bi bil vedno zavrnjen ("zajem ze tece"),
    # IDR pride z -g fps. Drugi odgovor je tu samo zato, da bi ga klic pomocnika porabil.
    pomocnik, zazeni_x11, slike = okolje
    lazni = pomocnik("ok", "napaka: zajem ze tece")
    slika, na_kms = lz.odpri_sliko(zazeni_x11, dict(ZAHTEVA), seja=7)
    slike.append(slika)
    assert na_kms is True
    assert slika.idr_na_zahtevo is False
    stari = slika._p
    assert slika.znova() is False
    assert slika.znova() is False
    # Zaporedje zamenjav za zige je nedotaknjeno: isti proces, brez zamenjave, brez "po zamenjavi".
    assert slika._p is stari and slika._bran is stari and slika.zamenjav == 0 and slika.poll() is None
    assert slika._po_zamenjavi is False
    assert slika.stdout.read(64) == KMS_PRETOK and slika.svez is True
    assert len(lazni.zahteve) == 1
    assert "dogodek=kms_zavrnjen" not in capsys.readouterr().err


def test_menjava_seje_preklopi_na_x11grab(okolje, capsys):
    pomocnik, zazeni_x11, slike = okolje
    lazni = pomocnik("ok")
    slika, na_kms = lz.odpri_sliko(zazeni_x11, dict(ZAHTEVA), seja=7)
    slike.append(slika)
    assert na_kms is True
    stanja = iter([(True, 1, (1920, 1080)), (False, 1, (1920, 1080))])
    assert lz.strazi_kms(slika, zazeni_x11, lambda: next(stanja), lambda: True, seja=7,
                         premor=0.01) is True
    assert slika.zamenjav == 1
    zbrano = beri_do(slika, b"X11")
    assert zbrano.endswith(X11_PRETOK) and b"KMS" not in zbrano
    assert lazni.ustavljen.wait(2)
    assert "dogodek=kms_preklop" in capsys.readouterr().err


def test_brez_menjave_ni_preklopa(okolje):
    pomocnik, zazeni_x11, slike = okolje
    pomocnik("ok")
    slika, _ = lz.odpri_sliko(zazeni_x11, dict(ZAHTEVA), seja=7)
    slike.append(slika)
    tece = itertools.chain([True] * 4, itertools.repeat(False))
    assert lz.strazi_kms(slika, zazeni_x11, lambda: (True, 1, (1920, 1080)), lambda: next(tece),
                         seja=7, premor=0.01) is False
    assert slika.zamenjav == 0
    assert slika.stdout.read(64) == KMS_PRETOK


# --- KMS-2: po menjavi seje se ostanek starega (tujega) pretoka zavrze -------------------------

def test_kms2_menjava_seje_stari_pretok_z_vec_nal_ne_gre_na_tv(okolje):
    pomocnik, zazeni_x11, slike = okolje
    pomocnik("ok", pretok=KMS_VEC_NAL)
    slika, na_kms = lz.odpri_sliko(zazeni_x11, dict(ZAHTEVA), seja=7)
    slike.append(slika)
    assert na_kms is True
    stanja = iter([(True, 1, (1920, 1080)), (False, 1, (1920, 1080))])
    assert lz.strazi_kms(slika, zazeni_x11, lambda: next(stanja), lambda: True, seja=7,
                         premor=0.01) is True
    assert slika.idr_na_zahtevo is True                     # x11grab zna IDR na zahtevo
    zbrano = beri_do(slika, b"X11")
    assert zbrano == X11_PRETOK                             # niti ena enota NAL tujega zaslona
    assert slika.svez is False                              # prvi kos novega procesa: brez ziga


def test_kms2_menjava_seje_brez_x11_konca_brez_tujega_pretoka(okolje, capsys):
    pomocnik, _, slike = okolje
    lazni = pomocnik("ok", pretok=KMS_VEC_NAL)
    slika, _ = lz.odpri_sliko(lambda: None, dict(ZAHTEVA), seja=7)
    slike.append(slika)

    def x11_pade():
        raise OSError("x11grab ne stece")

    stanja = iter([(True, 1, (1920, 1080)), (False, 1, (1920, 1080))])
    assert lz.strazi_kms(slika, x11_pade, lambda: next(stanja), lambda: True, seja=7,
                         premor=0.01) is False
    assert slika.stdout.read(64) == b""                     # seja konca, tuj pretok zavrzen
    assert lazni.ustavljen.wait(2)
    assert "razlog=seja_konec" in capsys.readouterr().err


def test_kms2_menjava_monitorja_stari_pretok_se_izprazni(okolje):
    # Kontrola: isti uporabnik, drug monitor - pretok je nas in se izprazni kot prej (brez zadnje
    # enote NAL, ker _KmsProces.terminate javi SIGKILL).
    pomocnik, zazeni_x11, slike = okolje
    pomocnik("ok", pretok=KMS_VEC_NAL)
    slika, _ = lz.odpri_sliko(zazeni_x11, dict(ZAHTEVA), seja=7)
    slike.append(slika)
    stanja = iter([(True, 1, (1920, 1080)), (True, 2, (1920, 1080))])
    assert lz.strazi_kms(slika, zazeni_x11, lambda: next(stanja), lambda: True, seja=7,
                         premor=0.01) is True
    zbrano = beri_do(slika, b"X11")
    assert zbrano == KMS_PRETOK + b"\x00\x00\x01KMS2" + X11_PRETOK


# --- KMS-8: pri KMS je zig slike izrecno None ---------------------------------------------------

class _Vticnica:
    def __init__(self, vrstica: bytes) -> None:
        self.klici = []
        self._vhod = io.BytesIO(vrstica)

    def sendall(self, b):
        self.klici.append(bytes(b))

    def recv(self, n):
        return self._vhod.read(n)

    def settimeout(self, t):
        pass

    def shutdown(self, how):
        pass

    def close(self):
        pass


def test_kms8_na_kms_brez_ziga_slike_izrecno(monkeypatch):
    z = lz.Zaslon()
    z._zeton = "zeton"
    z._slika = {"width": 1920, "height": 1080, "fps": 60}
    z._zakasnitev_slike = 13.5          # kot da bi bil vaapi nekoc izmerjen

    class _Vnos:
        mozno = False

        def sprosti_vse(self):
            pass

    class _Plosek:
        def mozno(self):
            return False

        def zapri(self):
            pass

    class _Slika:
        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

        def kill(self):
            pass

    class _Posluh:
        def __init__(self, v):
            self.v = v

        def accept(self):
            return self.v, None

    class _Ctx:
        def wrap_socket(self, s, server_side):
            return s

    z._vnos, z._plosek = _Vnos(), _Plosek()
    v = _Vticnica(b"SAFEER-ZASLON zeton\n")
    videno = []
    monkeypatch.setattr(lz, "odpri_sliko", lambda zazeni, kms, seja=0: (_Slika(), True))
    monkeypatch.setattr(lz, "strazi_kms", lambda *a, **k: False)
    monkeypatch.setattr(lz.Zaslon, "_crpaj",
                        lambda self, proces, vrsta, odjemalec, kos: videno.append(self._zakasnitev_slike))
    z._streci(_Posluh(v), _Ctx(), ["nic"], kms=dict(ZAHTEVA), display=":0")
    assert videno == [None]
    assert json.loads(v.klici[0].decode("utf-8"))["zig"] == lz.ZIG_GLAVA     # glava nespremenjena
