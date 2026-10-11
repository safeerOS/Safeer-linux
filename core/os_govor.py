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
SPROTNO_VSAKIH = 0.9          # s novega zvoka med sprotnimi prepoznavami
FAKTOR_GOVORA = 2.5         # govor je vsaj toliko glasnejsi od hrupa ozadja (~8 dB)
#: Besede ukaza na zacetku (»odpri zaslon«): lupa isce z vsemi besedami hkrati, zato jih odstranimo.
UKAZI = {
    "sl": ("odpri", "odpre", "poišči", "poisci", "išči", "isci", "najdi", "predvajaj", "zaženi", "zazeni", "pokaži", "pokazi"),
    "en": ("open", "search for", "search", "find", "play", "launch", "start", "show"),
    "de": ("öffne", "suche nach", "suche", "finde", "spiele", "starte", "zeige"),
    "hr": ("otvori", "pretraži", "traži", "nađi", "pusti", "pokreni", "pokaži"),
    "es": ("abre", "abrir", "busca", "buscar", "encuentra", "reproduce", "pon", "inicia", "muestra"),
    "pt": ("abre", "abrir", "abra", "procura", "procurar", "pesquisa", "pesquisar", "encontra", "toca", "reproduz", "inicia", "mostra"),
    "fr": ("ouvre", "ouvrir", "cherche", "chercher", "trouve", "joue", "lance", "affiche"),
    "it": ("apri", "cerca", "trova", "riproduci", "avvia", "mostra"),
}
CLENI = {
    "en": ("the", "a", "an", "my"), "de": ("der", "die", "das", "den", "dem", "ein", "eine", "einen", "meine", "mein"),
    "es": ("el", "la", "los", "las", "un", "una", "mi", "mis"), "pt": ("o", "a", "os", "as", "um", "uma", "meu", "minha"),
    "fr": ("le", "la", "les", "un", "une", "mon", "ma", "mes"), "it": ("il", "lo", "la", "i", "gli", "le", "un", "una", "mio", "mia"),
}
#: Namig prepoznavi (whisper --prompt): pogoste besede iskanja v jeziku uporabnika. Na posnetkih lastnika (3 m od
#: prenosnika, ventilator) je namig popravil npr. »Sled« -> »Splet«; odstranjevanje suma (RNNoise, FFT) in vecji
#: modeli (medium, large-turbo, 5x pocasnejsa) niso pomagali (meritev 11. 10. 2026).
NAMIGI = {
    "sl": "Odpri datoteko. Poišči sliko. Predvajaj film. Glasba. Medijski center. Nastavitve zaslona. Zvok. Omrežje. Splet.",
    "en": "Open the file. Find a picture. Play the film. Music. Media center. Display settings. Sound. Network. Web.",
    "de": "Öffne die Datei. Suche ein Bild. Spiele den Film. Musik. Mediencenter. Bildschirm-Einstellungen. Ton. Netzwerk.",
    "es": "Abre el archivo. Busca una imagen. Reproduce la película. Música. Centro multimedia. Pantalla. Sonido. Red.",
    "pt": "Abre o ficheiro. Procura uma imagem. Reproduz o filme. Música. Centro multimédia. Ecrã. Som. Rede.",
    "fr": "Ouvre le fichier. Cherche une image. Joue le film. Musique. Centre multimédia. Écran. Son. Réseau.",
    "it": "Apri il file. Cerca un'immagine. Riproduci il film. Musica. Centro multimediale. Schermo. Suono. Rete.",
    "hr": "Otvori datoteku. Traži sliku. Pusti film. Glazba. Medijski centar. Zaslon. Zvuk. Mreža.",
}


def jezik_govora(privzeti: str = "en") -> str:
    """Jezik, v katerem uporabnik govori: jezik seje (LANGUAGE/LC_ALL/LC_MESSAGES/LANG), ce ga whisper pozna;
    sicer jezik vmesnika. Portugalec z angleskim vmesnikom Safeer OS govori portugalsko."""
    for kljuc in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = (os.environ.get(kljuc) or "").split(":")[0][:2].lower()
        if v.isalpha() and len(v) == 2 and v not in ("c", "po"):
            return v
    return (privzeti or "en")[:2].lower()


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
            # Clen za ukazom (»abre el archivo«) iskanje le moti: vse besede se morajo ujemati.
            prva, _, ostalo = b.partition(" ")
            if ostalo and prva.lower() in CLENI.get(jezik, ()) + CLENI["en"]:
                b = ostalo.strip()
            break
    return b


def _rms(podatki: bytes) -> float:
    vzorci = array.array("h")
    vzorci.frombytes(podatki[: len(podatki) // 2 * 2])
    if not vzorci:
        return 0.0
    return math.sqrt(sum(v * v for v in vzorci) / len(vzorci))


class ZaznavaGovora:
    """Konec govora po glasnosti. Hrup ozadja je 10. percentil glasnosti zadnjih ~3 s (premori med besedami ga drzijo
    pri tleh tudi med govorom); prvih ~0,2 s (mikrofon se odpira, nicle) ne steje. Govor je, kar je vsaj
    FAKTOR_GOVORA-krat glasnejse od hrupa (in nad NAJMANJ_GLASNOST) v treh zaporednih kosih - presojamo za nazaj,
    ker se hrup ustali sele po nekaj kosih in uporabnik pogosto spregovori takoj.
    Meritev 11. 10. 2026 (posnetek lastnika): hrup 530-830 RMS, govor 1500-14600, odpiranje mikrofona 0-121 RMS v
    prvih 0,18 s - fiksen prag in najtisji zacetni kos nista delovala (konec govora ni bil zaznan)."""

    OKNO = 100        # kosov (3 s)
    ZAGON = 7         # kosov (0,21 s) odpiranja mikrofona

    def __init__(self) -> None:
        self.kosov = 0
        self.zadnji = []
        self.trije = []
        self.najvec3 = 0.0     # najglasnejsi trije zaporedni kosi (njihov najtisji)
        self.hrup = None
        self.tihih = 0
        self.govor = False     # ko je govor enkrat zaznan, ostane (dolg govor dvigne hrup v oknu)

    @property
    def prag(self) -> float:
        return max(NAJMANJ_GLASNOST, FAKTOR_GOVORA * (self.hrup or 0))

    def kos(self, rms: float) -> Optional[str]:
        """Vrne None (nadaljuj), »konec« (govor koncan) ali »tisina« (uporabnik ni spregovoril)."""
        self.kosov += 1
        cas = self.kosov * KOS / VZORCI
        if self.kosov > self.ZAGON:
            if not self.govor or rms < self.prag:          # med govorom hrup ocenjujemo samo iz tisine
                self.zadnji.append(rms)
                del self.zadnji[:-self.OKNO]
            self.trije = (self.trije + [rms])[-3:]
            if len(self.trije) == 3:
                self.najvec3 = max(self.najvec3, min(self.trije))
            if len(self.zadnji) >= 8:
                urejeni = sorted(self.zadnji)
                self.hrup = urejeni[len(urejeni) // 10]
            self.tihih = self.tihih + 1 if rms < self.prag else 0
            if self.hrup is not None and self.najvec3 >= self.prag:
                self.govor = True
        if self.govor and self.tihih * KOS / VZORCI >= TISINA_PO_GOVORU:
            return "konec"
        if cas >= NAJDALJE:
            return "konec" if self.govor else "tisina"
        if not self.govor and cas >= ZACETNA_TISINA:
            return "tisina"
        return None


def raven(rms: float) -> float:
    """Glasnost za valove na zaslonu, 0..1 (logaritemsko: hrup ~600 RMS ~0,2, glasen govor ~10000 RMS ~1)."""
    if rms <= 1:
        return 0.0
    return round(max(0.0, min(1.0, (20 * math.log10(rms) - 50) / 30)), 2)


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
        self._ustavi_proces(s)
        return True

    def _delo(self, seja, jezik, dogodek) -> None:
        proc = subprocess.Popen(self.snemalnik(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        posneto = bytearray()
        javljeno = False
        zaznava = ZaznavaGovora()
        izid = None
        sprotno = {"nit": None, "dolzina": 0}
        try:
            while not seja["ustavi"].is_set():
                kos = proc.stdout.read(KOS * 2)
                if not kos:
                    izid = "napaka"
                    break
                posneto += kos
                r = _rms(kos)
                if not javljeno and (r >= 50 or len(posneto) >= VZORCI):
                    # Mikrofon res sprejema zvok (prvih ~0,15 s so nicle, ko se odpira): sele zdaj gumb zasveti.
                    # Posnetek lastnika: govor, zacet ob kliku, je izgubil prvi zlog (»Predvajaj« -> »Vajaj«).
                    dogodek("poslusam", {})
                    javljeno = True
                izid = zaznava.kos(r)
                if zaznava.kosov % 2 == 0:
                    dogodek("raven", {"r": raven(r)})        # valovi v polju (~16 na sekundo)
                if zaznava.govor:
                    self._sprotno(seja, sprotno, posneto, jezik, dogodek)
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
        self._ustavi_proces(seja)                            # sprotna prepoznava ni vec potrebna
        surovo = self.prepoznaj(bytes(posneto), jezik, seja)
        if seja["preklici"].is_set():
            dogodek("preklicano", {})
            return
        dogodek("besedilo", {"besedilo": ocisti(surovo, jezik), "surovo": surovo})

    def _sprotno(self, seja, sprotno, posneto, jezik, dogodek) -> None:
        """Med govorom: vsakic, ko je prejsnja prepoznava koncana in je prislo vsaj SPROTNO_VSAKIH s novega zvoka,
        prepoznamo dosedanji posnetek in ga pokazemo (»delno«) - kot narekovanje na telefonu."""
        nit = sprotno["nit"]
        if (nit is not None and nit.is_alive()) or len(posneto) - sprotno["dolzina"] < SPROTNO_VSAKIH * VZORCI * 2:
            return
        sprotno["dolzina"] = len(posneto)
        kopija = bytes(posneto)

        def delo():
            besedilo = self.prepoznaj(kopija, jezik, seja, kopiraj=False)
            if besedilo and not seja["ustavi"].is_set():
                dogodek("delno", {"besedilo": besedilo})
        sprotno["nit"] = threading.Thread(target=delo, daemon=True)
        sprotno["nit"].start()

    @staticmethod
    def _ustavi_proces(seja) -> None:
        proc = seja.get("proces")
        if proc is not None and proc.poll() is None:
            proc.kill()

    def prepoznaj(self, pcm: bytes, jezik: str, seja=None, kopiraj=True) -> str:
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
            if kopiraj and kopija and os.path.isdir(kopija):
                shutil.copy(pot, os.path.join(kopija, "govor-%d.wav" % int(time.time())))
            niti = str(max(1, min(4, os.cpu_count() or 2)))
            # -ac 512: enkoder obdela ~10 s namesto 30 s (posnetek najvec NAJDALJE s + 0,7 s tisine) - ~3x hitreje.
            ukaz = [self.pot_programa(), "-m", self.pot_modela(), "-f", pot, "-l", jezik, "-t", niti,
                    "-nt", "-np", "-nf", "-ac", "512"]
            if NAMIGI.get(jezik):
                ukaz += ["--prompt", NAMIGI[jezik]]
            proc = subprocess.Popen(ukaz, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            if seja is not None:
                seja["proces"] = proc                       # preklic ali koncna prepoznava ga ustavi
            try:
                izhod, _ = proc.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                izhod, _ = proc.communicate()
            if proc.returncode != 0:
                return ""
            return " ".join(v.strip() for v in izhod.splitlines() if v.strip())
        finally:
            try:
                os.remove(pot)
            except OSError:
                pass
