"""Govor v iskalni lupi namizja: mikrofon -> besedilo, v celoti na tem racunalniku (nic ne gre na splet).

Prepoznava je whisper.cpp (MIT) z vecjezicnim modelom »small« (q5_1, 190 MB): na prenosniku lastnika
(i5, 4 niti) za 3,5 s govora ~1,8 s, ~470 MB pomnilnika samo med prepoznavo (meritev 11. 10. 2026,
-ac 512). Program in model se prenesemo sele, ko uporabnik prvic pritisne mikrofon in prenos potrdi;
oba preverimo s SHA-256 (spodaj), sicer ju zavrzemo.

Snemanje: parecord / pw-record / arecord (kar je na voljo), 16 kHz mono. Konec govora zaznamo po glasnosti:
ko uporabnik po govoru ~1 s molci, najvec po NAJDALJE sekundah; ce v ZACETNA_TISINA sekundah ne spregovori,
koncamo brez prepoznave. Posnetek je v XDG_RUNTIME_DIR in ga po prepoznavi izbrisemo."""
import array
import hashlib
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import wave
from typing import Callable, Optional

MAPA = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "safeer-os", "govor")

#: Model: vecjezicni whisper »small«, kvantiziran q5_1. Naslov je pripet na zapis repozitorija (ne spreminja se).
MODEL = {
    "ime": "ggml-small-q5_1.bin",
    "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/5359861c739e955e79d9a303bcbc70fb988958b1/"
           "ggml-small-q5_1.bin",
    "sha256": "ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb",
    "velikost": 190085487,
}
#: Program whisper-cli (whisper.cpp v1.9.5), zgrajen v nasem CI (ubuntu-22.04, GGML_NATIVE=OFF, brez OpenMP) in
#: objavljen v izdaji »govor-1«. Dokler sha256 ni vpisan, se program ne prenasa (velja samo ze namescen).
IZDAJA_PROGRAMA = "https://github.com/safeerOS/Safeer-linux/releases/download/govor-1/"
PROGRAMI = {
    "x86_64-v3": {"ime": "whisper-cli-x86_64-v3", "sha256": "", "velikost": 0},
    "x86_64": {"ime": "whisper-cli-x86_64", "sha256": "", "velikost": 0},
}
VZORCI = 16000
NAJDALJE = 8.0              # s posnetka
ZACETNA_TISINA = 5.0        # s brez govora -> konec
TISINA_PO_GOVORU = 1.0      # s tisine po govoru -> konec
KOS = 480                   # vzorcev na kos (30 ms)
NAJMANJ_GLASNOST = 400      # RMS (int16), pod tem ni govora ne glede na hrup
FAKTOR_GOVORA = 2.5         # govor je vsaj toliko glasnejsi od hrupa ozadja (~8 dB)
#: Besede ukaza na zacetku (»odpri zaslon«): lupa isce z vsemi besedami hkrati, zato jih odstranimo.
UKAZI = {
    "sl": ("odpri", "odpre", "poišči", "poisci", "išči", "isci", "najdi", "predvajaj", "zaženi", "zazeni", "pokaži", "pokazi"),
    "en": ("open", "search for", "search", "find", "play", "launch", "start", "show"),
    "de": ("öffne", "suche nach", "suche", "finde", "spiele", "starte", "zeige"),
    "hr": ("otvori", "pretraži", "traži", "nađi", "pusti", "pokreni", "pokaži"),
}


def razlicica_cpu() -> Optional[str]:
    """Kateri program ustreza procesorju: x86_64-v3 (AVX2, FMA, F16C), x86_64 (osnovni) ali None (ni podprto)."""
    if os.uname().machine not in ("x86_64", "amd64"):
        return None
    zastavice = set()
    try:
        with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as f:
            for vrstica in f:
                if vrstica.startswith("flags"):
                    zastavice = set(vrstica.split(":", 1)[1].split())
                    break
    except OSError:
        pass
    return "x86_64-v3" if {"avx2", "fma", "f16c"} <= zastavice else "x86_64"


def ocisti(besedilo: str, jezik: str = "sl") -> str:
    """Izhod prepoznave -> iskalni niz: brez oznak [BLANK_AUDIO] / (glasba), locil na koncu in besede ukaza."""
    b = re.sub(r"\[[^\]]*\]|\([^)]*\)|\*[^*]*\*", " ", str(besedilo or ""))
    b = " ".join(b.split()).strip(" .,!?;:\"'„“”…-")
    nizko = b.lower()
    for ukaz in sorted(UKAZI.get(jezik, ()) + UKAZI["en"], key=len, reverse=True):
        if nizko == ukaz:
            return ""
        if nizko.startswith(ukaz + " "):
            b = b[len(ukaz) + 1:].strip()
            break
    return b


def _rms(podatki: bytes) -> float:
    vzorci = array.array("h")
    vzorci.frombytes(podatki[: len(podatki) // 2 * 2])
    if not vzorci:
        return 0.0
    return math.sqrt(sum(v * v for v in vzorci) / len(vzorci))


class ZaznavaGovora:
    """Konec govora po glasnosti. Hrup ozadja je mediana prvih ~0,3 s (brez nicel, ko se mikrofon sele odpira) in se
    med tisino pocasi prilagaja; govor je, kar je vsaj FAKTOR_GOVORA-krat glasnejse (in nad NAJMANJ_GLASNOST) v
    vsaj treh zaporednih kosih. Meritev 11. 10. 2026: hrup mikrofona prenosnika lastnika ~690 RMS, zato fiksen prag
    ne zadosca."""

    def __init__(self) -> None:
        self.kosov = 0
        self.zacetni = []
        self.hrup = None
        self.glasnih = 0
        self.govor = False
        self.tihih = 0

    @property
    def prag(self) -> float:
        return max(NAJMANJ_GLASNOST, FAKTOR_GOVORA * (self.hrup or 0))

    def kos(self, rms: float) -> Optional[str]:
        """Vrne None (nadaljuj), »konec« (govor koncan) ali »tisina« (uporabnik ni spregovoril)."""
        self.kosov += 1
        cas = self.kosov * KOS / VZORCI
        if self.hrup is None:
            if rms >= 20:                       # mikrofon se odpira: prvi kosi so tisina iz nicel
                self.zacetni.append(rms)
            if len(self.zacetni) >= 10:
                # Najtisji kos: uporabnik pogosto spregovori takoj, ko mikrofon zasveti.
                self.hrup = min(self.zacetni)
            return None if cas < ZACETNA_TISINA else "tisina"
        if rms >= self.prag:
            self.glasnih += 1
            self.tihih = 0
            if self.glasnih >= 3:
                self.govor = True
        else:
            self.glasnih = 0
            self.tihih += 1
            if not self.govor:
                self.hrup = 0.95 * self.hrup + 0.05 * rms
        if self.govor and self.tihih * KOS / VZORCI >= TISINA_PO_GOVORU:
            return "konec"
        if cas >= NAJDALJE:
            return "konec" if self.govor else "tisina"
        if not self.govor and cas >= ZACETNA_TISINA:
            return "tisina"
        return None


class Govor:
    def __init__(self, mapa: Optional[str] = None) -> None:
        self.mapa = mapa or MAPA
        self._zaklep = threading.Lock()
        self._seja = None          # {"ustavi": Event, "preklici": Event}
        self._namescanje = None    # Event za preklic prenosa

    # ------------------------------------------------------------------ namestitev
    def pot_modela(self) -> str:
        return os.path.join(self.mapa, MODEL["ime"])

    def pot_programa(self) -> Optional[str]:
        """Nas program (prenesen), program iz SAFEER_GOVOR_PROGRAM ali whisper-cli v sistemu."""
        lastni = os.path.join(self.mapa, "whisper-cli")
        for pot in (lastni, os.environ.get("SAFEER_GOVOR_PROGRAM", ""), shutil.which("whisper-cli") or ""):
            if pot and os.path.isfile(pot) and os.access(pot, os.X_OK):
                return pot
        return None

    def _manjka(self) -> list:
        """Datoteke, ki jih je treba prenesti: [(url, cilj, sha256, velikost)]; None = programa za ta racunalnik ni."""
        manjka = []
        if not self.pot_programa():
            p = PROGRAMI.get(razlicica_cpu() or "")
            if p and p["sha256"]:
                manjka.append((IZDAJA_PROGRAMA + p["ime"], os.path.join(self.mapa, "whisper-cli"), p["sha256"], p["velikost"]))
            else:
                manjka.append(None)
        if not os.path.isfile(self.pot_modela()):
            manjka.append((MODEL["url"], self.pot_modela(), MODEL["sha256"], MODEL["velikost"]))
        return manjka

    @staticmethod
    def snemalnik() -> Optional[list]:
        if shutil.which("parecord"):
            return ["parecord", "--raw", "--format=s16le", "--rate=%d" % VZORCI, "--channels=1", "--latency-msec=30"]
        if shutil.which("pw-record"):
            return ["pw-record", "--format", "s16", "--rate", str(VZORCI), "--channels", "1", "-"]
        if shutil.which("arecord"):
            return ["arecord", "-q", "-f", "S16_LE", "-r", str(VZORCI), "-c", "1", "-t", "raw"]
        return None

    def stanje(self) -> dict:
        manjka = self._manjka()
        podprto = None not in manjka and self.snemalnik() is not None
        return {
            "podprto": podprto,
            "namesceno": podprto and not manjka,
            "prenos": sum(m[3] for m in manjka if m) if podprto else 0,
            "namescam": self._namescanje is not None,
            "poslusam": self._seja is not None,
        }

    def namesti(self, dogodek: Callable[[str, dict], None]) -> bool:
        """Prenese manjkajoce datoteke v ozadju; dogodki: »namescam« {odstotek}, »namesceno«, »napaka» {razlog}."""
        with self._zaklep:
            if self._namescanje is not None:
                return True
            manjka = self._manjka()
            if None in manjka:
                return False
            self._namescanje = threading.Event()
            preklic = self._namescanje

        def delo():
            try:
                os.makedirs(self.mapa, exist_ok=True)
                skupaj = sum(m[3] for m in manjka) or 1
                preneseno = 0
                for url, cilj, sha, _velikost in manjka:
                    preneseno = self._prenesi(url, cilj, sha, preneseno, skupaj, preklic, dogodek)
                    if cilj.endswith("whisper-cli"):
                        os.chmod(cilj, 0o755)
                dogodek("namesceno", {})
            except Exception as e:  # noqa: BLE001
                dogodek("napaka", {"razlog": "preklicano" if preklic.is_set() else "prenos", "podrobno": str(e)[:200]})
            finally:
                with self._zaklep:
                    self._namescanje = None
        threading.Thread(target=delo, daemon=True).start()
        return True

    def preklici_namestitev(self) -> bool:
        with self._zaklep:
            if self._namescanje is None:
                return False
            self._namescanje.set()
        return True

    @staticmethod
    def _prenesi(url, cilj, sha, preneseno, skupaj, preklic, dogodek) -> int:
        zacasna = cilj + ".part"
        h = hashlib.sha256()
        zadnji = -1
        try:
            with urllib.request.urlopen(url, timeout=30) as odziv, open(zacasna, "wb") as f:
                while True:
                    if preklic.is_set():
                        raise RuntimeError("preklicano")
                    blok = odziv.read(1 << 16)
                    if not blok:
                        break
                    f.write(blok)
                    h.update(blok)
                    preneseno += len(blok)
                    odstotek = min(99, int(100 * preneseno / skupaj))
                    if odstotek != zadnji:
                        zadnji = odstotek
                        dogodek("namescam", {"odstotek": odstotek})
            if h.hexdigest() != sha:
                raise RuntimeError("SHA-256 se ne ujema: " + os.path.basename(cilj))
            os.replace(zacasna, cilj)
        finally:
            if os.path.exists(zacasna):
                os.remove(zacasna)
        return preneseno

    # ------------------------------------------------------------------ poslusanje
    def poslusaj(self, jezik: str, dogodek: Callable[[str, dict], None]) -> bool:
        """Snema in prepozna v ozadju; dogodki: »poslusam«, »prepoznavam«, »besedilo« {besedilo, surovo},
        »tisina«, »napaka« {razlog}, »preklicano«."""
        jezik = (str(jezik or "sl")[:2] or "sl").lower()
        with self._zaklep:
            if self._seja is not None or not self.stanje()["namesceno"]:
                return False
            seja = {"ustavi": threading.Event(), "preklici": threading.Event()}
            self._seja = seja

        def delo():
            try:
                self._delo(seja, jezik, dogodek)
            except Exception as e:  # noqa: BLE001
                dogodek("napaka", {"razlog": "prepoznava", "podrobno": str(e)[:200]})
            finally:
                with self._zaklep:
                    self._seja = None
        threading.Thread(target=delo, daemon=True).start()
        return True

    def ustavi(self) -> bool:
        """Konec govora zdaj (drugi pritisk na mikrofon): posneto se prepozna."""
        s = self._seja
        if s is None:
            return False
        s["ustavi"].set()
        return True

    def preklici(self) -> bool:
        """Esc: brez prepoznave."""
        s = self._seja
        if s is None:
            return False
        s["preklici"].set()
        s["ustavi"].set()
        return True

    def _delo(self, seja, jezik, dogodek) -> None:
        proc = subprocess.Popen(self.snemalnik(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        posneto = bytearray()
        javljeno = False
        zaznava = ZaznavaGovora()
        izid = None
        try:
            while not seja["ustavi"].is_set():
                kos = proc.stdout.read(KOS * 2)
                if not kos:
                    izid = "napaka"
                    break
                posneto += kos
                if not javljeno:
                    # Mikrofon je odprt (prvi kos je tu): sele zdaj gumb zasveti - prej bi se zacetek govora izgubil.
                    dogodek("poslusam", {})
                    javljeno = True
                izid = zaznava.kos(_rms(kos))
                if izid:
                    break
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        if seja["preklici"].is_set():
            dogodek("preklicano", {})
            return
        if izid == "napaka" and not posneto:
            dogodek("napaka", {"razlog": "mikrofon"})
            return
        # Brez zaznanega govora ne prepoznavamo (whisper si v tisini izmisli besedilo); rocni »ustavi« po
        # vsaj 0,5 s posnetka pa prepoznamo - uporabnik je govoril, zaznava ga morda ni ujela.
        if not zaznava.govor and not (seja["ustavi"].is_set() and len(posneto) >= VZORCI):
            dogodek("tisina", {})
            return
        dogodek("prepoznavam", {})
        surovo = self.prepoznaj(bytes(posneto), jezik)
        if seja["preklici"].is_set():
            dogodek("preklicano", {})
            return
        dogodek("besedilo", {"besedilo": ocisti(surovo, jezik), "surovo": surovo})

    def prepoznaj(self, pcm: bytes, jezik: str) -> str:
        mapa = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        fd, pot = tempfile.mkstemp(prefix="safeer-govor-", suffix=".wav", dir=mapa)
        os.close(fd)
        try:
            with wave.open(pot, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(VZORCI)
                # Tisina pred in po govoru: whisper pri govoru od prve milisekunde rad izpusti zacetek besede.
                w.writeframes(bytes(int(VZORCI * 0.4) * 2) + pcm + bytes(int(VZORCI * 0.3) * 2))
            kopija = os.environ.get("SAFEER_GOVOR_POSNETKI", "")      # samo za razvoj: mapa za kopije posnetkov
            if kopija and os.path.isdir(kopija):
                shutil.copy(pot, os.path.join(kopija, "govor-%d.wav" % int(time.time())))
            niti = str(max(1, min(4, os.cpu_count() or 2)))
            # -ac 512: enkoder obdela ~10 s namesto 30 s (posnetek najvec NAJDALJE s + 0,7 s tisine) - ~3x hitreje.
            ukaz = [self.pot_programa(), "-m", self.pot_modela(), "-f", pot, "-l", jezik, "-t", niti,
                    "-nt", "-np", "-nf", "-ac", "512"]
            r = subprocess.run(ukaz, capture_output=True, text=True, timeout=60)
            return " ".join(v.strip() for v in r.stdout.splitlines() if v.strip())
        finally:
            try:
                os.remove(pot)
            except OSError:
                pass
