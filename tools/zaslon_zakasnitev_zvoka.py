#!/usr/bin/env python3
"""Merjenje zakasnitve zvoka v zajemu zaslona (najdba Z1).

Metoda (privzeto, po NALOGA):
  1. pactl ustvari locen null sink `safeer_merjenje` (ne motimo privzetega izhoda).
  2. Zajem ISTO kot core: Popen(ukaz_zvok("safeer_merjenje.monitor", ffmpeg), stdout=PIPE,
     stderr=DEVNULL, stdin=DEVNULL, bufsize=0), branje proces.stdout.read(1920) in takoj
     zatem ura_ms() (oboje uvozeno iz core.link_zaslon).
  3. N (privzeto 40) LOCENIH zagonov paplay/pw-play; vsak predvaja kratek WAV z enim impulzom
     (en okvir, vsi kanali 0x7FFF) na poziciji 0, nato kratka tisina. cas_predvajanja = ura_ms()
     tik pred vsakim Popen. Na pozicijo predvajalnika ne cakamo; pred naslednjim zagonom
     pocakamo razmik in konec predvajalnika (brez prekrivanja in ostalih procesov).
  4. Cas zaznave = cas_branja_kosa - (konec_kosa - indeks_impulza) / 192 B/ms.
     Zakasnitev = cas zaznave - cas_predvajanja; zaznava sodi k impulzu k, ce je v
     [cas_predvajanja_k, cas_predvajanja_k+1).
  5. Izpis mediana/p5/p95/max/n v eni vrstici.

Moznost --en-predvajalnik: en WAV z vsemi impulzi in en zagon predvajalnika.

POZOR: v privzetem nacinu je zagon predvajalnika (exec, povezava na streznik, vzpostavitev
toka) VSEBOVAN v vsaki meritvi -> rezultat je zgornja meja. Glej merjenje-zvoka-izhod.md.

Samo standardna knjiznica ter zunanji ukazi pactl, paplay/pw-play in ffmpeg.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import List, NoReturn, Optional, Sequence, Tuple

IME_SINKA = "safeer_merjenje"
VIR_ZAJEMA = IME_SINKA + ".monitor"
BAJTOV_NA_VZOREC = 2  # s16le
NAJVECJI_VZOREC = 0x7FFF
KOS_BRANJA = 1920  # kot core: branje po 1920 B

# ---------------------------------------------------------------------------
# Cisti del (brez zunanjih ukazov, testabilno)
# ---------------------------------------------------------------------------


def bajtov_na_ms(hz: int, kanali: int) -> float:
    """Stevilo bajtov s16le toka na milisekundo (48000 Hz, 2 kanala -> 192.0)."""
    return hz * kanali * BAJTOV_NA_VZOREC / 1000.0


def indeks_v_ms(indeks_bajta: int, bpms: float) -> float:
    """Polozaj bajta v toku pretvorjen v ms od zacetka toka."""
    return indeks_bajta / bpms


def okvir_impulza(kanali: int) -> bytes:
    """En okvir (vsi kanali) z vrednostjo 0x7FFF v s16le."""
    return NAJVECJI_VZOREC.to_bytes(2, "little", signed=True) * kanali


def ustvari_pcm(hz: int, kanali: int, n: int, razmik_ms: int, uvod_ms: int, rep_ms: int) -> bytes:
    """PCM s16le: uvod tisine, n impulzov (vsak en okvir) z razmikom razmik_ms, rep tisine.

    Polozaji so v celih okvirjih, zato so impulzi vedno poravnani na okvir in kanal.
    """
    if n < 1 or razmik_ms <= 0 or uvod_ms < 0 or rep_ms < 0:
        raise ValueError("neveljavni parametri")
    okvir = BAJTOV_NA_VZOREC * kanali
    okvirjev_razmik = hz * razmik_ms // 1000
    okvirjev_uvod = hz * uvod_ms // 1000
    okvirjev_rep = hz * rep_ms // 1000
    skupaj = okvirjev_uvod + (n - 1) * okvirjev_razmik + 1 + okvirjev_rep
    pcm = bytearray(skupaj * okvir)
    imp = okvir_impulza(kanali)
    for k in range(n):
        zac = (okvirjev_uvod + k * okvirjev_razmik) * okvir
        pcm[zac:zac + okvir] = imp
    return bytes(pcm)


def pisi_wav(pot: str, pcm: bytes, hz: int, kanali: int) -> None:
    """Zapise PCM s16le v WAV z modulom wave."""
    with wave.open(pot, "wb") as w:
        w.setnchannels(kanali)
        w.setsampwidth(BAJTOV_NA_VZOREC)
        w.setframerate(hz)
        w.writeframes(pcm)


class IskalnikImpulza:
    """Isce impulze v s16le toku, ki prihaja v kosih poljubne dolzine.

    - Ostanek, ki ni cel okvir, se prenese v naslednji kos (meja kosov, sticni kosi).
    - Okvir je impulz, ce ima katerikoli kanal |vrednost| >= prag.
    - Po zaznavi se `mrtvih_okvirjev` okvirjev ne zazna nic (odzvanjanje po prevzorcenju).
    - dodaj() vrne absolutne indekse BAJTA (zacetek okvirja) od zacetka toka.
    """

    def __init__(self, kanali: int, prag: int = 0x4000, mrtvih_okvirjev: int = 0) -> None:
        if kanali < 1 or not (0 < prag <= 0x8000) or mrtvih_okvirjev < 0:
            raise ValueError("neveljavni parametri")
        self.kanali = kanali
        self.okvir = BAJTOV_NA_VZOREC * kanali
        self.prag = prag
        self.mrtvih = mrtvih_okvirjev
        self._ostanek = b""
        self._zacetek_ostanka = 0  # absolutni indeks prvega bajta v self._ostanek
        self._blokiran_do = -1  # absolutni indeks okvirja, do katerega (vkljucno) ne zaznavamo

    @property
    def prebranih_bajtov(self) -> int:
        return self._zacetek_ostanka + len(self._ostanek)

    def dodaj(self, kos: bytes) -> List[int]:
        podatki = self._ostanek + kos
        baza = self._zacetek_ostanka
        celih = len(podatki) // self.okvir * self.okvir
        najdeni: List[int] = []
        mv = memoryview(podatki)[:celih].cast("h") if celih else None
        if mv is not None and sys.byteorder != "little":
            # s16le na big-endian: preberi rocno
            vzorci = [int.from_bytes(podatki[i:i + 2], "little", signed=True) for i in range(0, celih, 2)]
        else:
            vzorci = mv if mv is not None else []
        for i_okv in range(celih // self.okvir):
            abs_okv = baza // self.okvir + i_okv
            if abs_okv <= self._blokiran_do:
                continue
            zac = i_okv * self.kanali
            for c in range(self.kanali):
                if abs(vzorci[zac + c]) >= self.prag:
                    najdeni.append(abs_okv * self.okvir)
                    self._blokiran_do = abs_okv + self.mrtvih
                    break
        if mv is not None:
            mv.release()
        self._ostanek = podatki[celih:]
        self._zacetek_ostanka = baza + celih
        return najdeni


def cas_bajta_ms(indeks_bajta: int, prejeto_ms: float, konec_kosa: int, bpms: float) -> float:
    """Cas, ko je bil bajt na voljo bralcu.

    konec_kosa je absolutni indeks za zadnjim bajtom kosa, prejetega ob prejeto_ms. Bajt, ki je
    v toku (konec_kosa - indeks_bajta) bajtov pred koncem, je zvocno tolikokrat 1/bpms ms prej.
    """
    return prejeto_ms - (konec_kosa - indeks_bajta) / bpms


def pricakovani_casi(zacetek_ms: float, uvod_ms: int, razmik_ms: int, n: int) -> List[float]:
    return [zacetek_ms + uvod_ms + k * razmik_ms for k in range(n)]


def zdruzi(pricakovani: Sequence[float], zaznani: Sequence[float], najvec_ms: float) -> List[float]:
    """Vsakemu pricakovanemu impulzu pripise prvo zaznavo v [t, t + najvec_ms).

    najvec_ms mora biti manjsi od razmika, da zaznave ni mogoce pripisati napacnemu impulzu.
    Vsaka zaznava se porabi najvec enkrat. Manjkajoci impulzi so izpusceni.
    """
    zaz = sorted(zaznani)
    zakasnitve: List[float] = []
    j = 0
    for t in sorted(pricakovani):
        while j < len(zaz) and zaz[j] < t:
            j += 1  # zaznava pred impulzom (motnja) - preskoci
        if j < len(zaz) and zaz[j] < t + najvec_ms:
            zakasnitve.append(zaz[j] - t)
            j += 1
    return zakasnitve


def zdruzi_okna(casi_predvajanja: Sequence[float], zaznani: Sequence[float],
                zadnje_okno_ms: float) -> List[float]:
    """Nacin z locenimi zagoni: zaznava sodi k impulzu k, ce je v [t_k, t_k+1).

    Za zadnji impulz je okno [t_k, t_k + zadnje_okno_ms). V vsakem oknu se uporabi prva
    zaznava (ostale so odzvanjanje ali motnja). Zaznave pred prvim t so izpuscene.
    """
    t = sorted(casi_predvajanja)
    zaz = sorted(zaznani)
    zakasnitve: List[float] = []
    j = 0
    for k, zac in enumerate(t):
        konec = t[k + 1] if k + 1 < len(t) else zac + zadnje_okno_ms
        while j < len(zaz) and zaz[j] < zac:
            j += 1
        if j < len(zaz) and zaz[j] < konec:
            zakasnitve.append(zaz[j] - zac)
        while j < len(zaz) and zaz[j] < konec:
            j += 1  # porabi preostale zaznave v tem oknu
    return zakasnitve


def percentil(vrednosti: Sequence[float], p: float) -> float:
    """Percentil z linearno interpolacijo (kot numpy 'linear'); p v [0, 100]."""
    if not vrednosti:
        return float("nan")
    if not 0 <= p <= 100:
        raise ValueError("p mora biti v [0, 100]")
    s = sorted(vrednosti)
    poz = (len(s) - 1) * p / 100.0
    spodaj = int(poz)
    zgoraj = min(spodaj + 1, len(s) - 1)
    return s[spodaj] + (s[zgoraj] - s[spodaj]) * (poz - spodaj)


def vrstica_izpisa(zakasnitve: Sequence[float]) -> str:
    def f(x: float) -> str:
        return "nan" if x != x else f"{x:.1f}"
    najvec = max(zakasnitve) if zakasnitve else float("nan")
    return (f"ZAKASNITEV_ZVOKA_MS mediana={f(percentil(zakasnitve, 50))} p5={f(percentil(zakasnitve, 5))} "
            f"p95={f(percentil(zakasnitve, 95))} max={f(najvec)} n={len(zakasnitve)}")


def zaznave_iz_kosov(kosi: Sequence[Tuple[float, bytes]], iskalnik: IskalnikImpulza, bpms: float) -> List[float]:
    """Iz (cas_prejema_ms, kos) izracuna case zaznav impulzov."""
    casi: List[float] = []
    for prejeto, kos in kosi:
        konec = iskalnik.prebranih_bajtov + len(kos)
        for idx in iskalnik.dodaj(kos):
            casi.append(cas_bajta_ms(idx, prejeto, konec, bpms))
    return casi


# ---------------------------------------------------------------------------
# Necisti del (pactl, predvajalnik, ffmpeg)
# ---------------------------------------------------------------------------


def _napaka(sporocilo: str, koda: int = 2) -> NoReturn:
    print(sporocilo, file=sys.stderr)
    sys.exit(koda)


def _uvozi_core():
    """Uvozi ukaz_zvok, ura_ms in format iz core, da je zajem ISTI kot v core."""
    koren = Path(__file__).resolve().parent.parent
    if str(koren) not in sys.path:
        sys.path.insert(0, str(koren))
    try:
        from core.link_zaslon import ukaz_zvok, ura_ms, ZVOK_HZ, ZVOK_KANALI  # noqa: WPS433
    except Exception as e:  # uvoz core lahko pade tudi zaradi odvisnosti core
        _napaka(f"NAPAKA: ne morem uvoziti core.link_zaslon (ukaz_zvok, ura_ms, ZVOK_HZ, ZVOK_KANALI): {e!r}. "
                "Zazeni iz korena repozitorija.")
    return ukaz_zvok, ura_ms, int(ZVOK_HZ), int(ZVOK_KANALI)


def _predvajalnik() -> List[str]:
    """Zacetek ukaza predvajalnika (pot WAV se doda na konec)."""
    if shutil.which("paplay"):
        return ["paplay", f"--device={IME_SINKA}"]
    if shutil.which("pw-play"):
        return ["pw-play", "--target", IME_SINKA]
    _napaka("NAPAKA: manjka paplay (in pw-play). Namesti pulseaudio-utils ali pipewire.")


def _ustavi(proces: Optional[subprocess.Popen]) -> None:
    if proces is None or proces.poll() is not None:
        return
    proces.terminate()
    try:
        proces.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proces.kill()
        proces.wait(timeout=2)


def _bralec(proces: subprocess.Popen, ura_ms, kosi: List[Tuple[float, bytes]], stop: threading.Event) -> None:
    """Kot core _crpaj: proces.stdout.read(1920) in takoj zatem ura_ms()."""
    while not stop.is_set():
        try:
            podatki = proces.stdout.read(KOS_BRANJA)
        except (OSError, ValueError):
            break
        prebrano_ms = ura_ms()
        if not podatki:
            break
        kosi.append((prebrano_ms, podatki))


def _pocakaj_do(ura_ms, cas_ms: float) -> None:
    ostane = cas_ms - ura_ms()
    if ostane > 0:
        time.sleep(ostane / 1000.0)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=40, help="stevilo impulzov")
    ap.add_argument("--razmik-ms", type=int, default=1000, help="razmik med zacetki impulzov")
    ap.add_argument("--tisina-ms", type=int, default=100, help="tisina za impulzom v WAV (locen nacin)")
    ap.add_argument("--uvod-ms", type=int, default=500, help="tisina pred prvim impulzom (--en-predvajalnik)")
    ap.add_argument("--prag", type=int, default=1500, help="prag zaznave |vzorec| (pulse null sink zmanjsa glasnost na ~1/3, izmerjeno 22. 11. 2026)")
    ap.add_argument("--en-predvajalnik", action="store_true",
                    help="en WAV z vsemi impulzi in en zagon predvajalnika (zagon = enkraten odmik)")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    a = ap.parse_args(argv)
    if a.n < 1 or a.razmik_ms < 200 or a.tisina_ms < 0 or a.tisina_ms >= a.razmik_ms:
        _napaka("NAPAKA: --n >= 1, --razmik-ms >= 200, 0 <= --tisina-ms < --razmik-ms")

    for ukaz in ("pactl", a.ffmpeg):
        if not shutil.which(ukaz):
            _napaka(f"NAPAKA: manjka ukaz {ukaz}.")
    predvajalnik = _predvajalnik()
    ukaz_zvok, ura_ms, hz, kanali = _uvozi_core()
    bpms = bajtov_na_ms(hz, kanali)
    najvec_ms = a.razmik_ms * 0.9  # --en-predvajalnik: okno, manjse od razmika
    rep_ms = int(najvec_ms) + 200

    modul: Optional[str] = None
    zajem: Optional[subprocess.Popen] = None
    pred: Optional[subprocess.Popen] = None
    stop = threading.Event()
    kosi: List[Tuple[float, bytes]] = []
    casi_predvajanja: List[float] = []
    nit: Optional[threading.Thread] = None
    tmp = tempfile.NamedTemporaryFile(prefix="zakasnitev_", suffix=".wav", delete=False)
    tmp.close()
    try:
        if a.en_predvajalnik:
            pcm = ustvari_pcm(hz, kanali, a.n, a.razmik_ms, a.uvod_ms, rep_ms)
        else:
            pcm = ustvari_pcm(hz, kanali, 1, a.razmik_ms, 0, a.tisina_ms)  # impulz na poziciji 0
        pisi_wav(tmp.name, pcm, hz, kanali)
        r = subprocess.run(["pactl", "load-module", "module-null-sink", f"sink_name={IME_SINKA}",
                            f"rate={hz}", f"channels={kanali}"], text=True, capture_output=True, timeout=5)
        if r.returncode != 0:
            _napaka(f"NAPAKA: pactl load-module: {r.stderr.strip()}")
        modul = r.stdout.strip()

        # kot core: Popen(ukaz_zvok(...), stdout=PIPE, stderr=DEVNULL, stdin=DEVNULL, bufsize=0)
        zajem = subprocess.Popen(ukaz_zvok(VIR_ZAJEMA, a.ffmpeg), stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, bufsize=0)
        nit = threading.Thread(target=_bralec, args=(zajem, ura_ms, kosi, stop), daemon=True)
        nit.start()
        # ogrevanje: pocakaj na prve podatke, nato se 500 ms, da se zajem ustali
        rok = ura_ms() + 5000
        while not kosi and ura_ms() < rok and zajem.poll() is None:
            time.sleep(0.01)
        if not kosi:
            _napaka("NAPAKA: zajem (ffmpeg) ne vraca podatkov.")
        time.sleep(0.5)

        if a.en_predvajalnik:
            zacetek = ura_ms()  # tik pred zagonom: zagon predvajalnika je enkraten odmik
            pred = subprocess.Popen(predvajalnik + [tmp.name], stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
            pred.wait(timeout=(a.uvod_ms + a.n * a.razmik_ms + rep_ms) / 1000.0 + 10)
            pred = None
            time.sleep(najvec_ms / 1000.0)
            casi_predvajanja = pricakovani_casi(zacetek, a.uvod_ms, a.razmik_ms, a.n)
        else:
            for _ in range(a.n):
                t = ura_ms()  # tik pred zacetkom predvajanja (NALOGA tocka 2)
                pred = subprocess.Popen(predvajalnik + [tmp.name], stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
                casi_predvajanja.append(t)
                _pocakaj_do(ura_ms, t + a.razmik_ms)  # razmik, na pozicijo ne cakamo
                try:
                    pred.wait(timeout=5)  # brez prekrivanja: predvajalnik mora koncati pred naslednjim
                except subprocess.TimeoutExpired:
                    _ustavi(pred)
                pred = None
            time.sleep(0.2)  # se zadnji kosi zajema
    finally:
        stop.set()
        _ustavi(pred)
        _ustavi(zajem)
        if nit is not None:
            nit.join(timeout=2)
        if modul:
            subprocess.run(["pactl", "unload-module", modul], capture_output=True, timeout=5)
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    okvirjev_mrtvih = hz * 50 // 1000  # 50 ms mrtvega casa po zaznavi
    zaznani = zaznave_iz_kosov(list(kosi), IskalnikImpulza(kanali, a.prag, okvirjev_mrtvih), bpms)
    if a.en_predvajalnik:
        zak = zdruzi(casi_predvajanja, zaznani, najvec_ms)
    else:
        zak = zdruzi_okna(casi_predvajanja, zaznani, a.razmik_ms)
    print(vrstica_izpisa(zak))
    return 0 if zak else 1


if __name__ == "__main__":
    sys.exit(main())
