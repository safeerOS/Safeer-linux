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
5. Izjema: ob vklopu televizorja HDMI-CEC/eARC zvocniku sam preklopi vhod na TV. Ce se je televizor v Safeer Linku
   pojavil v oknu TV_OKNO_S pred ali po preklopu, preklop ni uporabnikov - zvocnik vzamemo nazaj (isti tok, Play),
   najvec enkrat na dogodek televizorja; ce uporabnik nato spet izbere TV, zmaga uporabnik (odlocitev lastnika
   17. 10. 2026). JBL One ne javi ne izvora preklopa ne nastavitve samodejnega preklopa (getStatusEx, JBL_Soundbar).

Zamik je nekaj sekund (medpomnilnik zvocnika). Za video domaci predvajalnik za toliko zamakne sliko (playbin
av-offset, core/os_predvajalnik.py): zakasnitev ocenimo iz polozaja, ki ga zvocnik javi (GetPositionInfo), in jo
zapomnimo za vsak zvocnik posebej (zvocniki.json na tej napravi); uporabnik jo lahko popravi po 50 ms.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, List, Optional

from core import dlna_zvocniki as dlna, os_deskriptorji

IZHOD = "safeer_zvocnik"
PREDPONA = "dlna:"
OSVEZI_S = 60.0          # seznam zvocnikov iscemo najvec enkrat na minuto (v ozadju)
PREVERI_S = 5.0          # straza: ali zvocnik se predvaja nas tok
ZACETNI_ZAMIK_S = 10.0   # zvocnik po ukazu Play nekaj sekund polni medpomnilnik
#: Zakasnitev zvoka na zvocniku (ms), dokler je ne izmerimo: tipicen medpomnilnik toka MP3 pri zvocnikih DLNA.
PRIVZETA_ZAKASNITEV_MS = 2000
MEJA_ZAKASNITVE_MS = 8000
KORAK_ZAKASNITVE_MS = 50
MERI_S = 0.25            # meritev: kako pogosto beremo polozaj zvocnika
MERI_KROGOV = 40         # najvec 10 s merjenja
#: Kako pogosto tokove, ki so nastali po preklopu, premaknemo na zvocnik (en klic pactl, nekaj ms).
NOVI_TOKOVI_S = 1.0
#: Preklop zvocnika na drug vir v tem oknu (s) pred ali po pojavu televizorja v Linku je samodejen (HDMI-CEC).
TV_OKNO_S = 20.0
#: Ko zvocnik ne igra vec nasega toka, pogosteje gledamo, ali se je pojavil televizor (krajsa prekinitev).
ODHOD_PREVERI_S = 1.0


def televizorji_v_linku() -> set:
    """Id-ji prizganih televizorjev (platforma tv), ki so ta trenutek v Safeer Linku (stanje, ki ga pise Safeer Control).

    TV z ugasnjenim zaslonom ostane v Linku z zmoznostjo »standby« (Android TV 0.5.89, VklopTelevizorja) - ta ni
    prizgan: vklop zaznamo, ko »standby« izgine (prej je TV, ki je ostal v Linku, vklop skril)."""
    from core import os_zvok
    s = os_zvok._beri_stanje_linka()
    if not s.get("povezan"):
        return set()
    return {str(d.get("id") or "") for d in s.get("naprave") or []
            if isinstance(d, dict) and d.get("platforma") == "tv" and d.get("id")
            and "standby" not in (d.get("zmoznosti") or [])}


def _pot_zakasnitev() -> str:
    return os.path.join((os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")), "safeer-os", "zvocniki.json")


def omeji_zakasnitev(ms) -> int:
    """Na mrezo 50 ms, med 0 in MEJA_ZAKASNITVE_MS; neveljavno = privzeto."""
    try:
        ms = int(round(float(ms) / KORAK_ZAKASNITVE_MS)) * KORAK_ZAKASNITVE_MS
    except (TypeError, ValueError):
        return PRIVZETA_ZAKASNITEV_MS
    return max(0, min(MEJA_ZAKASNITVE_MS, ms))


def ocena_zakasnitve(meritve: List[tuple]) -> Optional[int]:
    """Zakasnitev iz zaporednih meritev (cas od prvega bajta toka v s, RelTime zvocnika v celih s).

    Zvocnik zaigra zvok, zajet ob prvem bajtu, z zakasnitvijo L; takrat je njegov RelTime 0. RelTime je zaokrozen
    navzdol na sekundo, zato natancnost dobimo na prehodih: ko RelTime med meritvama a in b skoci na n, je trenutek
    n v (a, b], torej L v (a - n, b - n]. Presek vseh intervalov -> sredina. Brez prehoda ali neskladja: None."""
    spodaj, zgoraj = None, None
    for (a, ra), (b, rb) in zip(meritve, meritve[1:]):
        if rb == ra + 1 and b > a:
            lo, hi = a - rb, b - rb
            spodaj = lo if spodaj is None else max(spodaj, lo)
            zgoraj = hi if zgoraj is None else min(zgoraj, hi)
    if spodaj is None or zgoraj is None or zgoraj < spodaj or zgoraj < 0:
        return None
    return omeji_zakasnitev((max(spodaj, 0.0) + zgoraj) / 2 * 1000)


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


#: Rok pisanja zivega toka MP3 po glavah (zvocnik toliko casa ne sprejme nicesar: povezava gre).
ROK_PISANJA_TOKA_S = 30.0


class _Tok:
    """HTTP streznik, ki na /<zeton>/safeer.mp3 vsakemu odjemalcu (zvocniku) poganja svoj ffmpeg."""

    def __init__(self, naslov: str, ukaz: List[str]) -> None:
        self.zeton = secrets.token_urlsafe(18)
        self.pot = "/%s/safeer.mp3" % self.zeton
        self.ukaz = ukaz
        self._procesi: List[subprocess.Popen] = []
        self._kljuc = threading.Lock()
        self._ustavljen = False
        #: time.monotonic() prvega kosa, ki ga je zvocnik dobil (za meritev zakasnitve); 0 = se ni.
        self.prvi_bajt = 0.0
        tok = self

        class Obdelava(os_deskriptorji.RokCakanjaZahteve, BaseHTTPRequestHandler):
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
                try:
                    # Rok pisanja: zvocnik, ki 30 s ne bere (izklopljen, izgubil Wi-Fi), ne drzi niti in ffmpeg.
                    self.connection.settimeout(ROK_PISANJA_TOKA_S)
                except OSError:
                    return
                # Zagon pod istim zaklepom kot ustavi(): GET, ki se zacne hkrati z ustavitvijo, ne pozene ffmpeg mimo
                # seznama (ta bi tekel naprej brez lastnika).
                with tok._kljuc:
                    if tok._ustavljen:
                        return
                    proc = subprocess.Popen(tok.ukaz, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                            env=_okolje())
                    tok._procesi.append(proc)
                try:
                    while True:
                        kos = proc.stdout.read(4096) if proc.stdout else b""
                        if not kos:
                            break
                        self.wfile.write(kos)
                        if not tok.prvi_bajt:
                            tok.prvi_bajt = time.monotonic()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass          # zvocnik je prekinil (drug vir, premor) - obicajno
                finally:
                    _koncaj(proc)
                    with tok._kljuc:
                        if proc in tok._procesi:
                            tok._procesi.remove(proc)

        self._streznik = _Streznik((naslov, 0), Obdelava)
        self._streznik.daemon_threads = True
        self.url = "http://%s:%d%s" % (naslov, self._streznik.server_port, self.pot)
        threading.Thread(target=self._streznik.serve_forever, name="safeer-zvocnik-tok", daemon=True).start()

    def ustavi(self) -> None:
        with self._kljuc:
            self._ustavljen = True
            procesi, self._procesi = list(self._procesi), []
        for p in procesi:
            _koncaj(p)
        try:
            self._streznik.shutdown()
            self._streznik.server_close()
        except Exception:
            pass
        # Povezave zahtev (zvocnik v premoru ne bere): brez tega so ostale z nitjo in vticnikom (pregled 18. 10. 2026).
        self._streznik.zapri_povezave()


class _Streznik(os_deskriptorji.SledenjePovezav, ThreadingHTTPServer):
    pass


def _koncaj(proc: subprocess.Popen) -> None:
    """Ustavi ffmpeg, pocaka nanj (brez zombija) in zapre cev (brez odprtega deskriptorja)."""
    try:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=2)
    except Exception:
        try:
            proc.kill()
            proc.wait(timeout=2)
        except Exception:
            pass
    for cev in (proc.stdout, proc.stderr, proc.stdin):
        try:
            if cev is not None:
                cev.close()
        except Exception:
            pass


class Zvocniki:
    """Zvocniki v omrezju za stran Zvok v Safeer OS: seznam (v ozadju) in ena seja naenkrat."""

    def __init__(self, najdi: Callable[..., list] = dlna.najdi, pactl: Callable[..., subprocess.CompletedProcess] = _pactl,
                 ffmpeg: Optional[str] = None, lan_naslov: Callable[[str], str] = dlna.lan_naslov_za,
                 pot_zakasnitev: str = "") -> None:
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
        self._pot_zakasnitev = pot_zakasnitev or _pot_zakasnitev()
        #: Ob vsaki spremembi zakasnitve aktivnega izhoda (ms; 0 = zvok je spet tu): safeer_os zamakne sliko videa.
        self.ob_zakasnitvi: Callable[[int], None] = lambda _ms: None
        self.cakaj = time.sleep
        #: Televizorji v Linku (zamenljivo v testih); pojav novega = televizor se je zbudil / prisel na splet.
        self.televizorji: Callable[[], set] = televizorji_v_linku
        self._tv_videni: set = set()
        self._tv_dogodek = 0.0       # time.monotonic() zadnjega pojava televizorja; 0 = ni bilo
        self._tv_porabljen = 0.0     # dogodek, ob katerem smo zvocnik ze vzeli nazaj
        self.ura = time.monotonic
        self.spi = time.sleep        # cakanje straze (loceno od self.cakaj, ki ga testi meritve pospesijo)

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
                    "stanje": self.stanje, "zakasnitev": self.zakasnitev() if self._id else 0}

    # ------------------------------------------------------------------ zakasnitev (usklajenost slike)
    def _shranjene(self) -> dict:
        try:
            with open(self._pot_zakasnitev, encoding="utf-8") as d:
                podatki = json.load(d)
            return podatki if isinstance(podatki, dict) else {}
        except (OSError, ValueError):
            return {}

    def _shrani(self, id_zvocnika: str, ms: int, rocno: bool) -> None:
        podatki = self._shranjene()
        podatki[id_zvocnika] = {"ms": omeji_zakasnitev(ms), "rocno": bool(rocno)}
        try:
            os.makedirs(os.path.dirname(self._pot_zakasnitev), exist_ok=True)
            with open(self._pot_zakasnitev + ".tmp", "w", encoding="utf-8") as d:
                json.dump(podatki, d)
            os.replace(self._pot_zakasnitev + ".tmp", self._pot_zakasnitev)
        except OSError:
            pass

    def zakasnitev(self, id_zvocnika: str = "") -> int:
        """Zakasnitev zvoka na zvocniku v ms (shranjena ali privzeta); brez seje 0."""
        id_zvocnika = id_zvocnika or self._id
        if not id_zvocnika:
            return 0
        zapis = self._shranjene().get(id_zvocnika)
        return omeji_zakasnitev(zapis.get("ms")) if isinstance(zapis, dict) else PRIVZETA_ZAKASNITEV_MS

    def nastavi_zakasnitev(self, id_zvocnika: str, ms) -> int:
        """Rocna nastavitev (drsnik »Zamik zvoka«): shranimo na to napravo; meritev je vec ne prepise."""
        ms = omeji_zakasnitev(ms)
        self._shrani(str(id_zvocnika or ""), ms, rocno=True)
        if id_zvocnika and id_zvocnika == self._id:
            self.ob_zakasnitvi(ms)
        return ms

    def _izmeri(self, seja: int) -> None:
        """Polozaj zvocnika (RelTime) glede na prvi bajt toka -> zakasnitev; ce je uporabnik ni nastavil rocno."""
        with self._kljuc:
            if seja != self._seja or self._tok is None:
                return
            zvocnik, tok, id_zvocnika = self._zvocnik, self._tok, self._id
        zapis = self._shranjene().get(id_zvocnika)
        if isinstance(zapis, dict) and zapis.get("rocno"):
            return
        meritve: List[tuple] = []
        for _ in range(MERI_KROGOV):
            with self._kljuc:
                if seja != self._seja:
                    return
            try:
                rel = zvocnik.polozaj().get("RelTimeSeconds")
            except Exception:
                return
            if tok.prvi_bajt and isinstance(rel, int) and rel >= 0:
                meritve.append((time.monotonic() - tok.prvi_bajt, rel))
            self.cakaj(MERI_S)
        ms = ocena_zakasnitve(meritve)
        if ms is None:
            return
        with self._kljuc:
            if seja != self._seja:
                return
        self._shrani(id_zvocnika, ms, rocno=False)
        self.ob_zakasnitvi(ms)

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
        self.ob_zakasnitvi(self.zakasnitev(id_zvocnika))
        threading.Thread(target=self._strazi, args=(seja,), name="safeer-zvocnik-straza", daemon=True).start()
        threading.Thread(target=self._premikaj_nove, args=(seja,), name="safeer-zvocnik-tokovi", daemon=True).start()
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

    def _premakni_tuje(self) -> int:
        """Tokove, ki ne gredo na navidezni izhod, premakne nanj; vrne stevilo premaknjenih.

        Privzeti izhod ne zadostuje: PipeWire (WirePlumber, restore-stream) in PulseAudio (module-stream-restore) nov
        tok programa pripneta na izhod, ki si ga je program zapomnil. Tako je Safeer DRM (Spotify, Electron) ob vsaki
        novi skladbi ali po premoru odprl nov tok na zvocnikih racunalnika (pregled 17. 10. 2026)."""
        nas = ""
        for vrstica in self._pactl("list", "short", "sinks").stdout.splitlines():
            stolpci = vrstica.split()
            if len(stolpci) > 1 and stolpci[1] == IZHOD:
                nas = stolpci[0]
        if not nas:
            return 0
        n = 0
        for vrstica in self._pactl("list", "short", "sink-inputs").stdout.splitlines():
            stolpci = vrstica.split()
            if len(stolpci) > 1 and stolpci[0].isdigit() and stolpci[1] != nas:
                self._pactl("move-sink-input", stolpci[0], IZHOD)
                n += 1
        return n

    def _premikaj_nove(self, seja: int) -> None:
        """Dokler seja tece, vsak nov tok (nova skladba, drug program) gre na zvocnik in ne na racunalnik."""
        while True:
            self.cakaj(NOVI_TOKOVI_S)
            # Pod kljucem: ustavi() ne sme vmes vrniti tokov na racunalnik, ki bi jih mi nato spet premaknili.
            with self._kljuc:
                if seja != self._seja or self._tok is None:
                    return
                try:
                    self._premakni_tuje()
                except Exception:
                    pass

    def _poglej_televizorje(self, zacetek: bool = False) -> None:
        try:
            zdaj = set(self.televizorji())
        except Exception:
            return
        with self._kljuc:
            if not zacetek and zdaj - self._tv_videni:
                self._tv_dogodek = self.ura()
            self._tv_videni = zdaj

    def _samodejen_preklop(self, odhod: float) -> bool:
        """Ali je preklop ob `odhod` prisel s televizorjem (CEC) in ga za ta dogodek se nismo vzeli nazaj."""
        with self._kljuc:
            d = self._tv_dogodek
            return bool(d) and d != self._tv_porabljen and abs(d - odhod) <= TV_OKNO_S

    def _vzemi_nazaj(self, seja: int) -> bool:
        """Zvocnik spet na nas tok (isti naslov, Play); tok in navidezni izhod tecejo ves cas naprej."""
        with self._kljuc:
            if seja != self._seja or self._zvocnik is None or self._tok is None:
                return False
            self._tv_porabljen = self._tv_dogodek
            zvocnik, url = self._zvocnik, self._tok.url
        try:
            zvocnik.predvajaj(url, "Safeer OS - " + (os.uname().nodename or "racunalnik"), "Safeer OS", "audio/mpeg")
            return True
        except Exception:
            return False

    def _strazi(self, seja: int) -> None:
        """Ce uporabnik na zvocniku izbere drug vir (ali ga ugasne), vrnemo zvok na racunalnik.

        Preklop, ki ga je ob vklopu sprozil televizor (HDMI-CEC), ni uporabnikova izbira: zvocnik vzamemo nazaj."""
        self._poglej_televizorje(zacetek=True)
        self.spi(ZACETNI_ZAMIK_S)
        napake = 0
        odhod = 0.0      # kdaj zvocnik ni vec igral nasega toka; 0 = igra
        while True:
            with self._kljuc:
                if seja != self._seja or self._zvocnik is None or self._tok is None:
                    return
                zvocnik, url = self._zvocnik, self._tok.url
            self._poglej_televizorje()
            try:
                st = zvocnik.stanje()
                uri = str(zvocnik.polozaj().get("TrackURI") or "")
                nas = uri == url or url.endswith(uri.split("://", 1)[-1][-40:]) if uri else False
                if st in ("PLAYING", "TRANSITIONING") and (nas or not uri):
                    napake, odhod = 0, 0.0
                    with self._kljuc:
                        prvic = seja == self._seja and self.stanje != "tece"
                        if seja == self._seja:
                            self.stanje = "tece"
                    if prvic:
                        threading.Thread(target=self._izmeri, args=(seja,), name="safeer-zvocnik-meri",
                                         daemon=True).start()
                else:
                    napake += 1
            except Exception:
                napake += 1
            if napake:
                odhod = odhod or self.ura()
                if self._samodejen_preklop(odhod):
                    if self._vzemi_nazaj(seja):
                        napake, odhod = 0, 0.0
                        self.spi(PREVERI_S)
                        continue
                # Televizor se v Linku pogosto pojavi sele nekaj sekund po preklopu: pocakamo do konca okna,
                # razen ce smo za zadnji dogodek zvocnik ze vzeli nazaj (spet TV = uporabnik).
                with self._kljuc:
                    porabljen = bool(self._tv_porabljen) and self._tv_porabljen == self._tv_dogodek
                if napake >= 3 and (porabljen or self.ura() - odhod >= TV_OKNO_S):
                    with self._kljuc:
                        if seja == self._seja:
                            self.ustavi(obnovi=True, zvocnik_tudi=False)
                    return
                self.spi(ODHOD_PREVERI_S)
                continue
            self.spi(PREVERI_S)

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
            if imel:
                self.ob_zakasnitvi(0)
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
