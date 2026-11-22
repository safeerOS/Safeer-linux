#!/usr/bin/env python3
"""Meritev zajema zaslona: x11grab (pot, ki jo Zaslon uporablja privzeto) proti KMS (pomocnik).

Zaporedoma zazene (A) x11grab z ukazom iz core.link_zaslon.ukaz_ffmpeg in (B) zajem prek pomocnika
KMS (core.link_zaslon.slika_kms), samo ce je pomocnik namescen. Izhod ffmpeg (gol H.264 Annex-B) bere
lokalno, brez omrezja, in meri: CPU, stevilo slik in dejanski fps, razmik med slikami (cas BRANJA iz
cevi, ne cas zajema), velikost slik in prekinitve (razmik > 2/fps).

Samo standardna knjiznica. Pozeni iz korena projekta v seji X (DISPLAY mora biti nastavljen):
    python3 tools/zaslon_primerjava_zajema.py              # 1920x1080, 60 slik/s, 20 s na pot
    python3 tools/zaslon_primerjava_zajema.py --4k --fps 30 --trajanje 30
Nicesar ne brise; procese pospravi v finally.
"""

from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional, Sequence, Tuple

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

from core import link_zaslon as lz  # noqa: E402

#: Kos branja kot v Zaslon._streci (_crpaj slike bere po 32 KB).
KOS_BRANJA = 32 * 1024
#: Prve sekunde po zagonu (odpiranje naprave, prvi IDR) ne stejemo v statistiko.
OGREVANJE_S = 1.0
#: Pot do porabe CPU celotne storitve pomocnika (cgroup v2); berljiva je obicajno vsem.
CGROUP_KMS = "/sys/fs/cgroup/system.slice/safeer-kms.service/cpu.stat"
#: Imena procesa X streznika (comm); del stroska x11grab nosi streznik (kopija slike v SHM).
IMENA_X = ("Xorg", "X")
#: Varovalo meritve: rezerva po koncu meritve in cakanje na konec po SIGTERM, preden posljemo SIGKILL.
VAROVALO_REZERVA_S, VAROVALO_KILL_S = 10.0, 3.0
NI = "na"


# ------------------------------------------------------------------ cisti del (preizkus brez sistema)

def razcleni_stat(vrstica: str) -> Dict[str, object]:
    """Ena vrstica /proc/PID/stat -> pid, comm, stanje, utime, stime (v tikih).

    comm je v oklepajih in lahko vsebuje presledke in oklepaje, zato ga omejimo s PRVIM "(" in
    ZADNJIM ")". Po njem: 3. polje stanje, 14. utime, 15. stime (proc(5)).
    """
    zacetek = vrstica.index("(")
    konec = vrstica.rindex(")")
    if konec < zacetek:
        raise ValueError("stat: oklepaji")
    polja = vrstica[konec + 1:].split()
    if len(polja) < 13:
        raise ValueError("stat: premalo polj")
    return {"pid": int(vrstica[:zacetek].strip()), "comm": vrstica[zacetek + 1:konec],
            "stanje": polja[0], "utime": int(polja[11]), "stime": int(polja[12])}


def razcleni_proc_stat(besedilo: str) -> Tuple[int, int]:
    """Vrstica "cpu" iz /proc/stat -> (zasedeni tiki, vsi tiki), sestevek vseh jeder.

    Steti se user nice system idle iowait irq softirq steal (guest je ze v user); prosto = idle+iowait.
    """
    for vrstica in besedilo.splitlines():
        deli = vrstica.split()
        if deli and deli[0] == "cpu":
            vrednosti = [int(v) for v in deli[1:9]]
            if len(vrednosti) < 5:
                raise ValueError("/proc/stat: premalo polj")
            vsi = sum(vrednosti)
            return vsi - (vrednosti[3] + vrednosti[4]), vsi
    raise ValueError("/proc/stat: ni vrstice cpu")


def razcleni_cpu_stat(besedilo: str) -> int:
    """cpu.stat (cgroup v2) -> usage_usec."""
    for vrstica in besedilo.splitlines():
        deli = vrstica.split()
        if len(deli) == 2 and deli[0] == "usage_usec":
            return int(deli[1])
    raise ValueError("cpu.stat: ni usage_usec")


def delez_jedra(cpu_s: float, stena_s: float) -> Optional[float]:
    """Porabljen cas CPU kot odstotek enega jedra (100 = eno jedro ves cas)."""
    if stena_s <= 0 or cpu_s < 0:
        return None
    return 100.0 * cpu_s / stena_s


def je_ffmpeg_kms(argv: Sequence[str], sirina: int, visina: int) -> bool:
    """Ali je ukazna vrstica ffmpeg pomocnika za to zahtevo (link_kms_pomocnik.ukaz_kms)."""
    if not argv or not os.path.basename(argv[0]).startswith("ffmpeg"):
        return False
    filter_ = "hwmap=derive_device=vaapi,scale_vaapi=w=%d:h=%d:format=nv12" % (sirina, visina)
    return "kmsgrab" in argv and filter_ in argv


def percentil(urejeni: Sequence[float], p: float) -> Optional[float]:
    """Percentil po najblizjem rangu (urejen seznam): p95 = vrednost, pod katero je vsaj 95 %."""
    if not urejeni:
        return None
    # p * n / 100 (ne p / 100 * n): pri celih p in n je deljenje tocno, ceil brez napake zaokrozitve.
    rang = max(1, math.ceil(p * len(urejeni) / 100.0))
    return urejeni[min(rang, len(urejeni)) - 1]


def mediana(urejeni: Sequence[float]) -> Optional[float]:
    n = len(urejeni)
    if n == 0:
        return None
    return urejeni[n // 2] if n % 2 else (urejeni[n // 2 - 1] + urejeni[n // 2]) / 2.0


class MejeSlik:
    """Meje slik v golem H.264 po ZigiSlike.zacetki (isto pravilo kot zigi v Zaslon._crpaj).

    Za vsak zacetek slike zapise absolutni odmik v toku in cas branja kosa, v katerem je bil najden.
    Velikost slike = razlika do naslednjega zacetka (zadnja, nedokoncana slika nima velikosti).
    """

    def __init__(self) -> None:
        self._zigi = lz.ZigiSlike(None)
        self._poz = 0
        self.zacetki: List[Tuple[int, float]] = []
        self.velikosti: List[int] = []

    def dodaj(self, podatki: bytes, cas_ms: float) -> int:
        novih = 0
        for odmik in self._zigi.zacetki(podatki):
            zacetek = self._poz + odmik          # odmik je lahko negativen (koda med kosoma)
            if self.zacetki:
                self.velikosti.append(zacetek - self.zacetki[-1][0])
            self.zacetki.append((zacetek, cas_ms))
            novih += 1
        self._poz += len(podatki)
        return novih


def statistika(casi_ms: Sequence[float], velikosti: Sequence[int], fps: int) -> Dict[str, Optional[float]]:
    """Statistika slik: casi branja zacetkov in velikosti (bajti) slik v merjenem oknu."""
    razmiki = sorted(b - a for a, b in zip(casi_ms, casi_ms[1:]))
    meja = 2000.0 / fps
    izid: Dict[str, Optional[float]] = {
        "slik": float(len(casi_ms)),
        "fps": ((len(casi_ms) - 1) * 1000.0 / (casi_ms[-1] - casi_ms[0])
                if len(casi_ms) >= 2 and casi_ms[-1] > casi_ms[0] else None),
        "razmik_med_ms": mediana(razmiki),
        "razmik_p95_ms": percentil(razmiki, 95),
        "razmik_p99_ms": percentil(razmiki, 99),
        "razmik_max_ms": razmiki[-1] if razmiki else None,
        "prekinitev": float(sum(1 for r in razmiki if r > meja)),
        "slika_povp_b": (sum(velikosti) / len(velikosti)) if velikosti else None,
        "slika_max_b": float(max(velikosti)) if velikosti else None,
    }
    return izid


def povzetek_meja(meje: MejeSlik, od_ms: float, fps: int) -> Dict[str, Optional[float]]:
    """Statistika samo za slike, katerih zacetek je bil prebran ob od_ms ali pozneje (po ogrevanju)."""
    casi, velikosti = [], []
    for i, (_, cas) in enumerate(meje.zacetki):
        if cas < od_ms:
            continue
        casi.append(cas)
        if i < len(meje.velikosti):
            velikosti.append(meje.velikosti[i])
    return statistika(casi, velikosti, fps)


#: Vrstni red in oznake vrstic preglednice (kljuc, oznaka, decimalke).
VRSTICE = [
    ("ffmpeg_cpu_pct", "CPU ffmpeg (% enega jedra)", 1),
    ("storitev_cpu_pct", "CPU storitve KMS (cgroup, % jedra)", 1),
    ("x_cpu_pct", "CPU X streznika (% jedra)", 1),
    ("sistem_cpu_pct", "CPU sistema skupaj (% jedra)", 1),
    ("slik", "stevilo slik", 0),
    ("fps", "dejanski fps (cas branja)", 2),
    ("razmik_med_ms", "razmik mediana (ms)", 2),
    ("razmik_p95_ms", "razmik p95 (ms)", 2),
    ("razmik_p99_ms", "razmik p99 (ms)", 2),
    ("razmik_max_ms", "razmik najvec (ms)", 2),
    ("slika_povp_b", "velikost slike povp. (B)", 0),
    ("slika_max_b", "velikost slike najvec (B)", 0),
    ("prekinitev", "prekinitev (razmik > 2/fps)", 0),
]


def _oblika(vrednost: Optional[float], decimalke: int) -> str:
    if vrednost is None:
        return NI
    return ("%." + str(decimalke) + "f") % vrednost


def preglednica(a: Dict[str, Optional[float]], b: Optional[Dict[str, Optional[float]]]) -> str:
    """Ena preglednica z obema potema; brez poti B je stolpec B "na"."""
    sirina = max(len(o) for _, o, _ in VRSTICE)
    vrstice = ["%-*s  %14s  %14s" % (sirina, "meritev", "A x11grab", "B KMS")]
    for kljuc, oznaka, dec in VRSTICE:
        vb = _oblika(b.get(kljuc), dec) if b else NI
        vrstice.append("%-*s  %14s  %14s" % (sirina, oznaka, _oblika(a.get(kljuc), dec), vb))
    return "\n".join(vrstice)


def vrstica_strojna(nastavitve: Dict[str, object], a: Dict[str, Optional[float]],
                    b: Optional[Dict[str, Optional[float]]], stanje_kms: str) -> str:
    """Vrstica "KMS_PRIMERJAVA kljuc=vrednost ..." (brez presledkov v vrednostih, "na" = ni podatka)."""
    deli = ["KMS_PRIMERJAVA"]
    for kljuc in ("w", "h", "fps", "trajanje_s", "kodirnik", "izvor"):
        deli.append("%s=%s" % (kljuc, str(nastavitve.get(kljuc, NI)).replace(" ", "_")))
    deli.append("kms=%s" % stanje_kms)
    for predpona, izid in (("x11", a), ("kms", b)):
        for kljuc, _, dec in VRSTICE:
            deli.append("%s_%s=%s" % (predpona, kljuc, _oblika(izid.get(kljuc) if izid else None, dec)))
    return " ".join(deli)


# ------------------------------------------------------------------ branje sistema

def _beri(pot: str) -> Optional[str]:
    try:
        with open(pot, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def tiki_procesa(pid: Optional[int]) -> Optional[int]:
    """utime + stime procesa v tikih ali None (proces ni viden ali ni berljiv)."""
    if pid is None:
        return None
    besedilo = _beri("/proc/%d/stat" % pid)
    if not besedilo:
        return None
    try:
        s = razcleni_stat(besedilo)
    except ValueError:
        return None
    return int(s["utime"]) + int(s["stime"])


def _ukazna_vrstica(pid: int) -> List[str]:
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            surovo = f.read()
    except OSError:
        return []
    return [d.decode("utf-8", "replace") for d in surovo.split(b"\0") if d]


def _pidi() -> List[int]:
    return [int(ime) for ime in os.listdir("/proc") if ime.isdigit()]


def najdi_ffmpeg_kms(sirina: int, visina: int) -> Tuple[Optional[int], str]:
    """PID ffmpeg v storitvi pomocnika: pomocnik ga ne sporoci (le fd prek SCM_RIGHTS), zato ga
    iscemo po ukazni vrstici. Pomocnik dovoli en zajem naenkrat, zato je zadetek enolicen ali nic."""
    zadetki = [pid for pid in _pidi() if je_ffmpeg_kms(_ukazna_vrstica(pid), sirina, visina)]
    if len(zadetki) == 1:
        if tiki_procesa(zadetki[0]) is None:
            return None, "stat_ni_berljiv"
        return zadetki[0], "najden_v_proc"
    if not zadetki:
        return None, "ni_viden_v_proc"
    return None, "vec_kandidatov"


def je_x_za_display(argv: Sequence[str], display: str) -> bool:
    """Ali je ukazna vrstica streznika X za ta DISPLAY (":0" ali ":0.0" -> argument ":0")."""
    zaslon = display.split(".", 1)[0] if display.startswith(":") else ""
    return bool(zaslon) and zaslon in argv[1:]


def najdi_x_streznik(display: str) -> Optional[int]:
    """PID streznika X za ta DISPLAY; ob vec streznikih (prijavni zaslon, druga seja) samo tisti z njegovim
    argumentom. Vrstni red v /proc ni dolocen, zato prvi zadetek po imenu ni dovolj."""
    po_imenu, za_display = [], []
    for pid in _pidi():
        besedilo = _beri("/proc/%d/stat" % pid)
        if not besedilo:
            continue
        try:
            if razcleni_stat(besedilo)["comm"] not in IMENA_X:
                continue
        except ValueError:
            continue
        po_imenu.append(pid)
        if je_x_za_display(_ukazna_vrstica(pid), display):
            za_display.append(pid)
    if len(za_display) == 1:
        return za_display[0]
    return po_imenu[0] if len(po_imenu) == 1 else None


def _sistem() -> Optional[int]:
    besedilo = _beri("/proc/stat")
    try:
        return razcleni_proc_stat(besedilo)[0] if besedilo else None
    except ValueError:
        return None


def _storitev_usec() -> Optional[int]:
    besedilo = _beri(CGROUP_KMS)
    try:
        return razcleni_cpu_stat(besedilo) if besedilo else None
    except ValueError:
        return None


class Posnetek:
    """Stanje stevcev CPU v enem trenutku (None = ni na voljo)."""

    def __init__(self, ffmpeg_pid: Optional[int], x_pid: Optional[int], storitev: bool) -> None:
        self.cas = time.monotonic()
        self.ffmpeg = tiki_procesa(ffmpeg_pid)
        self.x = tiki_procesa(x_pid)
        self.sistem = _sistem()
        self.storitev = _storitev_usec() if storitev else None


def _razlika_pct(prej: Optional[int], potem: Optional[int], enota_s: float, stena_s: float) -> Optional[float]:
    if prej is None or potem is None:
        return None
    return delez_jedra((potem - prej) * enota_s, stena_s)


# ------------------------------------------------------------------ meritev ene poti

def izmeri(slika, ffmpeg_pid: Optional[int], x_pid: Optional[int], fps: int, trajanje_s: float,
           storitev: bool) -> Dict[str, Optional[float]]:
    """Bere sliko trajanje_s (po OGREVANJE_S) in vrne statistiko; slike ne ustavi (to stori klicatelj)."""
    tik = 1.0 / os.sysconf("SC_CLK_TCK")
    meje = MejeSlik()
    zacetek = time.monotonic()
    konec_ogrevanja = zacetek + OGREVANJE_S
    konec = konec_ogrevanja + trajanje_s
    prej: Optional[Posnetek] = None
    # Branje blokira: ce ffmpeg obstane, ga varovalo ustavi (SIGTERM, nato SIGKILL; read nato vrne EOF).
    varovalo = threading.Timer(OGREVANJE_S + trajanje_s + VAROVALO_REZERVA_S, _ustavi_obstalo, args=(slika,))
    varovalo.daemon = True
    varovalo.start()
    try:
        while True:
            podatki = slika.read(KOS_BRANJA)
            if not podatki:
                print("opozorilo: ffmpeg je koncal pred koncem meritve", file=sys.stderr)
                break
            zdaj_ms = lz.ura_ms()                 # ista ura kot zigi v Zaslon._crpaj
            meje.dodaj(podatki, zdaj_ms)
            if prej is None and zdaj_ms >= konec_ogrevanja * 1000.0:
                prej = Posnetek(ffmpeg_pid, x_pid, storitev)
            if zdaj_ms >= konec * 1000.0:
                break
    finally:
        varovalo.cancel()
    potem = Posnetek(ffmpeg_pid, x_pid, storitev)
    izid = povzetek_meja(meje, konec_ogrevanja * 1000.0, fps)
    if prej is not None:
        stena = potem.cas - prej.cas
        izid["ffmpeg_cpu_pct"] = _razlika_pct(prej.ffmpeg, potem.ffmpeg, tik, stena)
        izid["x_cpu_pct"] = _razlika_pct(prej.x, potem.x, tik, stena)
        izid["sistem_cpu_pct"] = _razlika_pct(prej.sistem, potem.sistem, tik, stena)
        izid["storitev_cpu_pct"] = _razlika_pct(prej.storitev, potem.storitev, 1e-6, stena)
    return izid


def _ustavi_obstalo(slika) -> None:
    """Varovalo: ffmpeg, ki visi (gonilnik, X), SIGTERM lahko prezre; po VAROVALO_KILL_S zato SIGKILL."""
    try:
        slika.terminate()
    except Exception:
        pass
    try:
        slika.wait(timeout=VAROVALO_KILL_S)
    except Exception:
        try:
            slika.kill()
        except Exception:
            pass


def pospravi(slika) -> None:
    """Ustavi proces slike (x11grab: SIGTERM, KMS: zapre vticnik, pomocnik ustavi ffmpeg)."""
    if slika is None:
        return
    try:
        slika.terminate()
    except Exception:
        pass
    try:
        slika.wait(timeout=3)
    except Exception:
        try:
            slika.kill()
        except Exception:
            pass
    try:
        slika._p.stdout.close()              # bralec smo mi (ta nit), zato je zapiranje varno
    except Exception:
        pass


# ------------------------------------------------------------------ glavni del

def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Primerjava zajema x11grab in KMS (CPU, enakomernost slik).")
    ap.add_argument("--4k", dest="stirik", action="store_true", help="3840x2160 namesto 1920x1080")
    ap.add_argument("--fps", type=int, default=60, choices=(30, 60),
                    help="slik na sekundo (pomocnik KMS dovoli samo 30 in 60)")
    ap.add_argument("--trajanje", type=float, default=20.0, help="sekund merjenja na pot (privzeto 20)")
    ap.add_argument("--ffmpeg", default=None, help="pot do ffmpeg za pot A (privzeto kot Zaslon)")
    ap.add_argument("--display", default=os.environ.get("DISPLAY", ""))
    arg = ap.parse_args(argv)
    if not arg.display:
        print("napaka: DISPLAY ni nastavljen (pozeni v seji X)", file=sys.stderr)
        return 2
    if not math.isfinite(arg.trajanje) or arg.trajanje <= 0:
        # nan in inf bi sicer obsla preverbo: varovalo (Timer) bi padlo, zanka meritve pa ne bi koncala.
        print("napaka: --trajanje mora biti koncno stevilo > 0", file=sys.stderr)
        return 2
    ffmpeg = arg.ffmpeg or (shutil.which("ffmpeg") or "")          # kot Zaslon.__init__
    if not ffmpeg:
        print("napaka: ffmpeg ni namescen", file=sys.stderr)
        return 2

    # Velikost, kakovost in ukaz natanko kot Zaslon.zacni (desktop): izvor, _prilagodi, KAKOVOSTI.
    cilj = (3840, 2160) if arg.stirik else (1920, 1080)
    k = lz.KAKOVOSTI[lz.PRIVZETA_KAKOVOST]
    izvor_znan = lz._zaslon_geometrija(arg.display)
    izvor = izvor_znan or (lz.NAJVEC_SIRINA, lz.NAJVEC_VISINA)
    if not izvor_znan:
        print("opozorilo: velikost zaslona ni znana (xdotool), primerjava A in B ni enakovredna", file=sys.stderr)
    sirina, visina = lz.Zaslon._prilagodi(izvor, cilj[0], cilj[1])
    if (sirina, visina) != cilj:
        print("opozorilo: zaslon je %dx%d, merimo %dx%d (brez povecave)" % (izvor[0], izvor[1], sirina, visina),
              file=sys.stderr)
    vaapi = lz.vaapi_naprava()
    ukaz = lz.ukaz_ffmpeg(arg.display, sirina, visina, izvor[0], izvor[1], arg.fps, str(k["bitrate"]),
                          vaapi, ffmpeg, int(k["qp"]))
    nastavitve = {"w": sirina, "h": visina, "fps": arg.fps, "trajanje_s": arg.trajanje,
                  "kodirnik": "h264_vaapi" if vaapi else "libx264",
                  # Brez xdotool velikost zaslona ni znana: x11grab zajame samo zgornji levi del, KMS ves zaslon.
                  "izvor": "%dx%d" % izvor if izvor_znan else NI}

    def zazeni_x11():
        # Kot Zaslon._streci (okolje None = nase, kot pri namizju).
        return subprocess.Popen(ukaz, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL, bufsize=0, env=None)

    x_pid = najdi_x_streznik(arg.display)
    if x_pid is None:
        print("opozorilo: procesa X streznika (Xorg) ni v /proc: CPU X streznika ni na voljo", file=sys.stderr)

    # (A) x11grab
    print("A: x11grab %dx%d@%d (%s), %.0f s ..." % (sirina, visina, arg.fps, nastavitve["kodirnik"], arg.trajanje),
          file=sys.stderr)
    slika = None
    try:
        slika, _ = lz.odpri_sliko(zazeni_x11, None, 0)
        a = izmeri(slika, slika._p.pid, x_pid, arg.fps, arg.trajanje, storitev=False)
    finally:
        pospravi(slika)

    # (B) KMS
    b: Optional[Dict[str, Optional[float]]] = None
    if not lz.kms_na_voljo():
        print("KMS ni na voljo: pomocnik ni namescen")
        stanje_kms = "ni_pomocnika"
    elif not vaapi:
        print("KMS preskocen: ni naprave VAAPI (Zaslon KMS brez VAAPI ne uporabi)")
        stanje_kms = "ni_vaapi"
    elif lz.kms_monitorji() != 1:
        print("KMS preskocen: prizganih monitorjev ni natanko 1 (kmsgrab zajame samo prvi CRTC)")
        stanje_kms = "vec_monitorjev"
    else:
        time.sleep(2.0)                     # sistem se umiri po poti A
        zahteva = {"sirina": sirina, "visina": visina, "fps": arg.fps, "kodek": "h264", "qp": int(k["qp"])}
        slika = None
        try:
            slika = lz.slika_kms(zahteva, 0)
            if slika is None:
                print("KMS zavrnjen: razlog je v vrstici kms_zavrnjen na stderr")
                stanje_kms = "zavrnjen"
            else:
                pid, kako = najdi_ffmpeg_kms(sirina, visina)
                if pid is None:
                    print("opozorilo: CPU ffmpeg pri KMS ni na voljo (%s)" % kako, file=sys.stderr)
                b = izmeri(slika, pid, x_pid, arg.fps, arg.trajanje, storitev=True)
                stanje_kms = "izmerjen_pid" if pid is not None else "izmerjen_brez_pid_%s" % kako
        finally:
            pospravi(slika)

    print("Razmik med slikami je cas BRANJA iz cevi (ura_ms), ne cas zajema; vkljucuje kodiranje in cev.")
    print(preglednica(a, b))
    print(vrstica_strojna(nastavitve, a, b, stanje_kms))
    return 0


if __name__ == "__main__":
    sys.exit(main())
