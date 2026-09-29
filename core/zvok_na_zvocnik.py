"""Zvok racunalnika na zvocniku v omrezju (DLNA) - »Predvajaj tukaj« kot pri napravah v Safeer Linku.

Zvocnik (npr. JBL BAR 300, Kodi, pametni TV) je navaden UPnP/DLNA MediaRenderer; nanj ne namescamo
nicesar in ne uporabljamo vmesnikov proizvajalcev (core/dlna_zvocniki.py).

1. Safeer OS ustvari navidezni izhod `safeer_zvocnik` (PipeWire/PulseAudio null-sink) z imenom zvocnika,
   ga nastavi za privzetega in nanj preusmeri vse programe.
2. Na domacem naslovu odpre majhen HTTP tok (MP3) samo pod nakljucnim zetonom; ffmpeg zajema monitor
   navideznega izhoda.
3. Zvocniku po DLNA poslje naslov toka (SetAVTransportURI + Play). Zvocnik tok potegne sam.
4. Konec (uporabnik izbere drug izhod ali na zvocniku preklopi vir): prejsnji izhod dobi nazaj
   privzetost in vse programe, navidezni izhod izgine.

Zamik je nekaj sekund (medpomnilnik zvocnika) - primerno za glasbo in radio, ne za film z ustnicami.
"""

from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, List, Optional

from core import dlna_zvocniki as dlna

IZHOD = "safeer_zvocnik"
PREDPONA = "dlna:"
OSVEZI_S = 60.0          # seznam zvocnikov iscemo najvec enkrat na minuto (v ozadju)
PREVERI_S = 5.0          # straza: ali zvocnik se predvaja nas tok
ZACETNI_ZAMIK_S = 10.0   # zvocnik po ukazu Play nekaj sekund polni medpomnilnik


def _okolje() -> dict:
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid())
    return env


def _pactl(*argumenti: str, cas: float = 4.0) -> subprocess.CompletedProcess:
    return subprocess.run(["pactl"] + list(argumenti), capture_output=True, text=True, timeout=cas, env=_okolje())


def ukaz_toka(vir: str, ffmpeg: str = "ffmpeg") -> List[str]:
    """ffmpeg: zajem monitorja navideznega izhoda -> MP3 256 kb/s na stdout, z najmanj medpomnjenja."""
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-fflags", "nobuffer",
            "-f", "pulse", "-fragment_size", "4096", "-i", vir,
            "-ac", "2", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "256k",
            "-flush_packets", "1", "-f", "mp3", "-"]


class _Tok:
    """HTTP streznik, ki na /<zeton>/safeer.mp3 vsakemu odjemalcu (zvocniku) poganja svoj ffmpeg."""

    def __init__(self, naslov: str, ukaz: List[str]) -> None:
        self.zeton = secrets.token_urlsafe(18)
        self.pot = "/%s/safeer.mp3" % self.zeton
        self.ukaz = ukaz
        self._procesi: List[subprocess.Popen] = []
        self._kljuc = threading.Lock()
        tok = self

        class Obdelava(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"   # tok brez dolzine: konec = zaprta povezava

            def log_message(self, *_a) -> None:
                pass

            def _glava(self) -> bool:
                if self.path.split("?", 1)[0] != tok.pot:
                    self.send_error(404)
                    return False
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("transferMode.dlna.org", "Streaming")
                self.send_header("contentFeatures.dlna.org",
                                 "DLNA.ORG_PN=MP3;DLNA.ORG_OP=00;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01700000000000000000000000000000")
                self.end_headers()
                return True

            def do_HEAD(self) -> None:
                self._glava()

            def do_GET(self) -> None:
                if not self._glava():
                    return
                proc = subprocess.Popen(tok.ukaz, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        env=_okolje())
                with tok._kljuc:
                    tok._procesi.append(proc)
                try:
                    while True:
                        kos = proc.stdout.read(4096) if proc.stdout else b""
                        if not kos:
                            break
                        self.wfile.write(kos)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass          # zvocnik je prekinil (drug vir, premor) - obicajno
                finally:
                    _koncaj(proc)
                    with tok._kljuc:
                        if proc in tok._procesi:
                            tok._procesi.remove(proc)

        self._streznik = ThreadingHTTPServer((naslov, 0), Obdelava)
        self._streznik.daemon_threads = True
        self.url = "http://%s:%d%s" % (naslov, self._streznik.server_port, self.pot)
        threading.Thread(target=self._streznik.serve_forever, name="safeer-zvocnik-tok", daemon=True).start()

    def ustavi(self) -> None:
        with self._kljuc:
            procesi, self._procesi = list(self._procesi), []
        for p in procesi:
            _koncaj(p)
        try:
            self._streznik.shutdown()
            self._streznik.server_close()
        except Exception:
            pass


def _koncaj(proc: subprocess.Popen) -> None:
    try:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=2)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


class Zvocniki:
    """Zvocniki v omrezju za stran Zvok v Safeer OS: seznam (v ozadju) in ena seja naenkrat."""

    def __init__(self, najdi: Callable[..., list] = dlna.najdi, pactl: Callable[..., subprocess.CompletedProcess] = _pactl,
                 ffmpeg: Optional[str] = None, lan_naslov: Callable[[str], str] = dlna.lan_naslov_za) -> None:
        self._najdi = najdi
        self._pactl = pactl
        self.ffmpeg = ffmpeg if ffmpeg is not None else (shutil.which("ffmpeg") or "")
        self._lan_naslov = lan_naslov
        self._zvocniki: Dict[str, object] = {}
        self._iskano = 0.0
        self._isce = False
        self._kljuc = threading.RLock()
        self._seja = 0
        self._zvocnik = None
        self._id = ""
        self._tok: Optional[_Tok] = None
        self._prejsnji = ""
        self._modul = ""
        self.stanje = ""        # "" / "caka" / "tece"

    # ------------------------------------------------------------------ seznam
    def mozno(self) -> bool:
        return bool(self.ffmpeg) and shutil.which("pactl") is not None

    def osvezi(self, pocakaj: bool = False) -> None:
        with self._kljuc:
            if self._isce:
                return
            self._isce = True

        def _isci() -> None:
            try:
                najdeni = {PREDPONA + z.udn: z for z in self._najdi(3.0)}
                with self._kljuc:
                    # Zvocnik, ki ta trenutek igra nas tok, obdrzimo, tudi ce ta krog ni odgovoril.
                    if self._id and self._id not in najdeni and self._zvocnik is not None:
                        najdeni[self._id] = self._zvocnik
                    self._zvocniki = najdeni
            except Exception:
                pass
            finally:
                with self._kljuc:
                    self._iskano = time.monotonic()
                    self._isce = False

        if pocakaj:
            _isci()
        else:
            threading.Thread(target=_isci, name="safeer-zvocniki-isci", daemon=True).start()

    def seznam(self) -> List[dict]:
        if time.monotonic() - self._iskano > OSVEZI_S:
            self.osvezi()
        with self._kljuc:
            return [{"id": k, "ime": z.ime or z.model or "Zvocnik", "model": z.model,
                     "proizvajalec": z.proizvajalec} for k, z in sorted(self._zvocniki.items(), key=lambda p: p[1].ime)]

    def opis(self) -> dict:
        with self._kljuc:
            return {"naprava": self._id, "ime": getattr(self._zvocnik, "ime", "") if self._zvocnik else "",
                    "stanje": self.stanje}

    # ------------------------------------------------------------------ seja
    def zacni(self, id_zvocnika: str, potrdi: bool = False) -> dict:
        """Zvok racunalnika na zvocnik. Ce zvocnik ta trenutek igra drug vir (npr. TV), brez potrditve
        ne preklopimo in vrnemo {"vir": ...} - uporabnik naj ne izgubi zvoka televizorja nevede."""
        if not self.mozno():
            return {"ok": False, "napaka": "ni_ffmpeg"}
        with self._kljuc:
            zvocnik = self._zvocniki.get(id_zvocnika)
        if zvocnik is None:
            return {"ok": False, "napaka": "ni_zvocnika"}
        if not potrdi:
            try:
                if zvocnik.stanje() == "PLAYING":
                    uri = str(zvocnik.polozaj().get("TrackURI") or "")
                    if uri and not uri.lower().startswith(("http://", "https://")):
                        return {"ok": False, "vir": uri}
            except Exception:
                pass
        self.ustavi(obnovi=False)
        with self._kljuc:
            self._seja += 1
            seja = self._seja
            try:
                if not self._prejsnji:
                    zdaj = self._pactl("get-default-sink").stdout.strip()
                    self._prejsnji = "" if zdaj == IZHOD else zdaj
                self._pripravi_izhod(zvocnik.ime)
                self._tok = _Tok(self._lan_naslov(zvocnik.naslov), ukaz_toka(IZHOD + ".monitor", self.ffmpeg))
                zvocnik.predvajaj(self._tok.url, "Safeer OS - " + (os.uname().nodename or "racunalnik"),
                                  "Safeer OS", "audio/mpeg")
            except Exception as e:
                self._pocisti()
                return {"ok": False, "napaka": str(e)[:200]}
            self._zvocnik, self._id, self.stanje = zvocnik, id_zvocnika, "caka"
        threading.Thread(target=self._strazi, args=(seja,), name="safeer-zvocnik-straza", daemon=True).start()
        return {"ok": True, "ime": zvocnik.ime}

    def _pripravi_izhod(self, ime: str) -> None:
        izhodi = self._pactl("list", "short", "sinks").stdout
        if IZHOD not in izhodi:
            opis = (ime or "Zvocnik").replace('"', "").replace("\\", "")[:60] + " (Safeer OS)"
            r = self._pactl("load-module", "module-null-sink", "sink_name=" + IZHOD,
                            'sink_properties=device.description="%s" device.icon_name=audio-speakers' % opis)
            if r.returncode != 0:
                raise RuntimeError("Navideznega izhoda ni bilo mogoce ustvariti")
            self._modul = r.stdout.strip()
            for _ in range(20):
                if IZHOD in self._pactl("list", "short", "sinks").stdout:
                    break
                time.sleep(0.05)
        self._pactl("set-default-sink", IZHOD)
        for vrstica in self._pactl("list", "short", "sink-inputs").stdout.splitlines():
            stolpci = vrstica.split()
            if stolpci:
                self._pactl("move-sink-input", stolpci[0], IZHOD)

    def _strazi(self, seja: int) -> None:
        """Ce uporabnik na zvocniku izbere drug vir (ali ga ugasne), vrnemo zvok na racunalnik."""
        time.sleep(ZACETNI_ZAMIK_S)
        napake = 0
        while True:
            with self._kljuc:
                if seja != self._seja or self._zvocnik is None or self._tok is None:
                    return
                zvocnik, url = self._zvocnik, self._tok.url
            try:
                st = zvocnik.stanje()
                uri = str(zvocnik.polozaj().get("TrackURI") or "")
                nas = uri == url or url.endswith(uri.split("://", 1)[-1][-40:]) if uri else False
                if st in ("PLAYING", "TRANSITIONING") and (nas or not uri):
                    napake = 0
                    with self._kljuc:
                        if seja == self._seja:
                            self.stanje = "tece"
                else:
                    napake += 1
            except Exception:
                napake += 1
            if napake >= 3:
                with self._kljuc:
                    if seja == self._seja:
                        self.ustavi(obnovi=True, zvocnik_tudi=False)
                return
            time.sleep(PREVERI_S)

    def ustavi(self, obnovi: bool = True, zvocnik_tudi: bool = True) -> bool:
        with self._kljuc:
            imel = self._zvocnik is not None
            zvocnik = self._zvocnik
            self._seja += 1
            if zvocnik is not None and zvocnik_tudi:
                try:
                    zvocnik.ustavi()
                except Exception:
                    pass
            if self._tok is not None:
                self._tok.ustavi()
            self._tok = None
            self._zvocnik, self._id, self.stanje = None, "", ""
            if obnovi:
                self._obnovi_izhod()
            return imel

    def _pocisti(self) -> None:
        if self._tok is not None:
            self._tok.ustavi()
        self._tok = None
        self._obnovi_izhod()

    def _obnovi_izhod(self) -> None:
        cilj = self._prejsnji
        self._prejsnji = ""
        try:
            if cilj:
                self._pactl("set-default-sink", cilj)
                for vrstica in self._pactl("list", "short", "sink-inputs").stdout.splitlines():
                    stolpci = vrstica.split()
                    if stolpci:
                        self._pactl("move-sink-input", stolpci[0], cilj)
            if self._modul:
                self._pactl("unload-module", self._modul)
                self._modul = ""
            else:
                for vrstica in self._pactl("list", "short", "modules").stdout.splitlines():
                    if "sink_name=" + IZHOD in vrstica:
                        self._pactl("unload-module", vrstica.split()[0])
        except Exception:
            pass
