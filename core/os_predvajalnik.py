"""En predvajalni servis in čakalna vrsta za neposredne medije Safeer OS.

GStreamer se naloži šele ob prvem predvajanju, zato sam zagon OS ne zahteva
predvajalnih vtičnikov. Vmesnik in baza knjižnice lahko uporabljata isto sejo.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlsplit

from core import predvajalnik_moznosti as _moznosti


@dataclass(frozen=True)
class Skladba:
    uri: str
    naslov: str
    vrsta: str = "medij"
    zacetek: int = 0
    #: Od kod je medij (ime naprave v Safeer Linku); prazno = ta racunalnik.
    izvor: str = ""
    #: Podnapisi ob videu: ((uri, ime, jezik, oznaka), ...) - datoteke ob videu, z naprave ali iz torrenta.
    podnapisi: tuple = ()
    #: Datoteka z druge naprave v Linku: id te naprave in oznaka datoteke na njej (za "Nadaljuj na drugi napravi":
    #: cilj dobi svoj zeton pri tisti napravi, kot pri Datotekah). Prazno = ta racunalnik ali spletni tok.
    naprava: str = ""
    oznaka: str = ""
    #: Naslov datoteke na tisti napravi (https://.../d/<oznaka>) - uri zgoraj je lokalni posrednik 127.0.0.1.
    izvirnik: str = ""
    #: Glave HTTP, ki jih streznik toka zahteva (dodatek jih poda ob toku, npr. Referer): ((ime, vrednost), ...).
    #: Brez njih nekateri strezniki toka vrnejo 429/403, ceprav tok dela (meritev 15. 10. 2026).
    glave: tuple = ()
    #: Druge razlicice istega naslova: ((uri, glave), ...). Ce se tok ne odpre (4xx, 5xx, cas, stran HTML), predvajalnik
    #: tiho poskusi naslednjo; napako pokaze sele, ko ne dela nobena.
    nadomestni: tuple = ()


#: Kode napak predvajanja (za dnevnik). Lastnik 18. 10. 2026: napak predvajalnika uporabniku ne kazemo - predvajalnik
#: tiho gre na naslednjo skladbo/postajo ali se ustavi, sled je v stderr (sled.log). Uporabnik vidi samo »dvd«:
#: zasciten disk ni napaka predvajanja, ampak pojasnilo, zakaj ga Safeer ne odklepa.
NAPAKE = {
    "tok": "Tok ni dosegljiv. Preveri naslov in povezavo.",
    "datoteka": "Datoteke ni mogoče prebrati.",
    "format": "Tega zapisa ni mogoče predvajati (manjka kodek ali datoteka ni medij).",
    "zascita": "Posnetek je zaščiten (DRM) in ga Safeer ne predvaja.",
    "dvd": "Diska ni mogoče prebrati. Zaščitenih diskov (CSS) Safeer ne odklepa.",
    "zacetek": "Predvajanja ni bilo mogoče začeti.",
    "splosno": "Predvajanje se je ustavilo zaradi napake.",
    "povezava": "Povezava s postajo se je prekinila in je ni bilo mogoče obnoviti. Preveri omrežje ali poskusi pozneje.",
}


def vrsta_napake(napaka, uri: str = "") -> str:
    """GLib.Error iz GStreamerja -> ena od kod v NAPAKE."""
    domena, koda = str(getattr(napaka, "domain", "") or ""), int(getattr(napaka, "code", 0) or 0)
    if uri.startswith("dvd://") and ("resource" in domena or "stream" in domena):
        return "dvd"
    omrezje = uri.startswith(("http://", "https://", "rtsp://", "rtmp://"))
    if "stream" in domena and koda in (12, 13):          # GST_STREAM_ERROR_DECRYPT(_NOKEY)
        return "zascita"
    if "stream" in domena and koda in (4, 5, 6, 7, 9, 11):  # TYPE_NOT_FOUND, WRONG_TYPE, CODEC, DECODE, DEMUX, FORMAT
        return "format"
    if "missing-plugin" in str(napaka).lower() or "core" in domena and koda == 12:
        return "format"
    if "resource" in domena or omrezje:
        return "tok" if omrezje else "datoteka"
    return "splosno"


def _dnevnik_napake(koda: str, vrsta: str) -> None:
    """Sled napake predvajanja (brez naslova vsebine) v stderr - zaganjalnik ga preusmeri v sled.log."""
    print("[SafeerOS] predvajanje: napaka %s (%s), tiho naprej" % (koda, vrsta or "medij"), file=sys.stderr, flush=True)


def medij(uri: str, vrsta: str = "medij") -> Skladba:
    """Sprejme spletni tok ali obstoječo lokalno datoteko."""
    uri = str(uri or "").strip()
    if vrsta not in ("medij", "video", "tv", "radio"):
        raise ValueError("Neznana vrsta medija")
    razcep = urlsplit(uri)
    if razcep.scheme in ("http", "https") and razcep.netloc:
        ime = Path(razcep.path).name or razcep.netloc
        return Skladba(uri, ime, vrsta)
    if razcep.scheme == "dvd":
        # DVD brez zaščite: slika ISO, mapa z VIDEO_TS ali optični pogon (core/os_dvd.py).
        pot = uri[len("dvd://"):]                     # nekodirana pot (tako jo bere resindvd)
        if pot.startswith("/dev/sr") or (pot and Path(pot).exists()):
            return Skladba(uri, Path(pot).stem.replace("_", " ") if not pot.startswith("/dev/") else "DVD", vrsta if vrsta != "medij" else "video")
        raise ValueError("DVD ni dosegljiv")
    if razcep.scheme == "file":
        from urllib.request import url2pathname
        pot = Path(url2pathname(razcep.path))
        if pot.is_file():
            return Skladba(pot.resolve().as_uri(), pot.name, vrsta)
    raise ValueError("Medij mora biti spletni tok ali obstoječa lokalna datoteka")


#: Glave, ki jih tok sme nastaviti: samo javne (Referer, Origin ...), nikoli prijava ali piskotki. GStreamer pred 1.28.7
#: (GStreamer-SA-2026-0080; runtime ima 1.26.11) ob preusmeritvi na drug izvor poslje extra-headers naprej - zato v njih
#: ni nicesar skrivnega (tests/test_prijava_streznikov.py). Host/Range doloci GStreamer sam.
_DOVOLJENE_GLAVE = {"referer", "origin", "user-agent", "accept", "accept-language", "x-requested-with"}


def cisti_glave(glave) -> tuple:
    """dict ali pari -> ((ime, vrednost), ...) brez nedovoljenih glav in brez prelomov vrstic."""
    pari = glave.items() if isinstance(glave, dict) else (glave or ())
    izid = []
    for par in list(pari)[:12]:
        try:
            ime, vrednost = (str(x or "") for x in par)
        except (TypeError, ValueError):
            continue
        if ime.lower() in _DOVOLJENE_GLAVE and "\n" not in vrednost and "\r" not in vrednost:
            izid.append((ime[:64], vrednost[:2048]))
    return tuple(izid)


def cisti_nadomestne(nadomestni) -> tuple:
    """Samo naslovi http(s), najvec 12."""
    izid = []
    for n in list(nadomestni or ())[:12]:
        try:
            uri, glave = (n[0], n[1]) if isinstance(n, (tuple, list)) else (n.get("url"), n.get("glave"))
        except (AttributeError, IndexError, TypeError):
            continue
        if urlsplit(str(uri or "")).scheme in ("http", "https"):
            izid.append((str(uri), cisti_glave(glave)))
    return tuple(izid)


def status_napake(razhroscevanje: str) -> int:
    """HTTP koda iz sporocila souphttpsrc (»... (429), URL: ...«); 0 = ni znana."""
    import re
    m = re.search(r"\((\d{3})\)", str(razhroscevanje or ""))
    return int(m.group(1)) if m else 0


def _cisti_podnapisi(podnapisi) -> tuple:
    """Samo lokalne datoteke in naslovi http(s) (tudi 127.0.0.1 za pretok z naprave ali torrent)."""
    izid = []
    for p in list(podnapisi or ())[:24]:
        try:
            uri, ime, jezik, oznaka = (str(x or "") for x in p)
        except (TypeError, ValueError):
            continue
        if urlsplit(uri).scheme in ("http", "https", "file"):
            izid.append((uri, ime[:120], jezik[:8], oznaka[:40]))
    return tuple(izid)


#: GST_PLAY_FLAG_TEXT - playbin prikaže podnapise.
ZASTAVICA_BESEDILO = 1 << 2
#: GST_PLAY_FLAG_BUFFERING - playbin medpomni tudi po demultipleksorju (samo radio v zivo).
ZASTAVICA_MEDPOMNJENJE = 1 << 8

# Radio v zivo (vrsta "radio", http/https): datoteke, video, YouTube in TV ostanejo pri privzetih nastavitvah playbina.
#: Najvec 10 s stisnjenega toka v queue2 (pri 128 kb/s je to ~160 KB) ...
ZIVO_MEDPOMNILNIK_S = 10
#: ... in najvec 1 MiB, da 10 s zadosti tudi za postaje do ~800 kb/s; pri 128 kb/s odloca cas, ne bajti.
ZIVO_MEDPOMNILNIK_B = 1 << 20
#: Zvocni tokovi radia ne presegajo 320 kb/s; pri prilagodljivih (HLS) postajah to omeji izbiro razlicice.
ZIVO_HITROST_KBPS = 320
#: Predvajanje se zacne (in po zastoju nadaljuje), ko je v zalogi 40 % od 10 s = 4 s; zaloga potem raste do 10 s,
#: kolikor omrezje prinese vec od hitrosti toka. Polnih 10 s bi pomenilo ~6-10 s tisine ob vsakem zagonu.
ZIVO_ZACETNA_ZALOGA = 0.4
#: Zvocni izhod (pulsesink/alsasink): 1 s zaloge namesto 0,2 s premosti kratko obremenitev procesorja,
#: 50 ms segmenti namesto 10 ms pomenijo petkrat manj prebujanj.
ZIVO_IZHOD_ZALOGA_US = 1_000_000
ZIVO_IZHOD_SEGMENT_US = 50_000
#: souphttpsrc: zastoj omrezja zaznamo po 8 s (privzeto 15 s); prekinjen tok sam znova odpre do 3-krat (neopazno).
ZIVO_HTTP_TIMEOUT_S = 8
ZIVO_HTTP_PONOVI = 3
#: Ko je predvajanje skupaj zaradi zastojev (ali premora) zaostalo za vec kot 15 s, skocimo nazaj na zivi rob.
ZIVO_ZAOSTANEK_MEJA_S = 15.0
#: Medpomnjenje, ki se 15 s ne zakljuci, pomeni mrtvo povezavo: povezemo se znova.
ZIVO_ZASTOJ_MEJA_S = 15.0
#: Odmiki pred ponovnimi povezavami ob ERROR/EOS; po zadnjem uporabnik vidi napako "povezava".
ZIVO_ODMIKI_S = (1, 2, 4, 8, 8)
#: Po toliko sekundah nemotenega predvajanja stejemo poskuse povezave znova od zacetka.
ZIVO_STABILNO_S = 30.0
#: Napake, ki jih ponovna povezava ne popravi (manjka kodek, DRM): brez ponovnih poskusov.
TRAJNE_NAPAKE = frozenset({"format", "zascita"})
#: Premor radia v zivo (lastnik, 18. 10. 2026: »premor zamuja, po nadaljevanju je nekaj casa tisina, po dolgem premoru
#: zaigra stara pesem, nato se tok pretrga«). Premor tok takoj utisa (playbin »mute«: tisina v trenutku, tudi za zvok, ki
#: je ze v zvocnem izhodu), tok pa tece naprej: nadaljevanje samo odstrani utisanje - zvok je takoj tu in je zivi program,
#: nic starega iz zaloge. Prej je premor ustavil cevovod (PAUSED), zaloga in vticnik sta ostala polna starega zvoka:
#: izmerjeno 18. 10. 2026 (krajevni preizkusni radio, scratchpad meri_radio.py) premor 5 s -> po nadaljevanju 5 s star
#: zvok (zaostanek 10,3 s namesto 5,3 s) do konca poslusanja, 12 s -> 12 s star, nad 15 s ponovna povezava s 1,2 s tisine
#: (brez zacetnega izbruha streznika 5,1 s). Po ZIVO_PREMOR_TOPLO_S tihega premora povezavo sprostimo (omrezje, mesto pri
#: strezniku); nadaljevanje se tedaj poveze znova na zivi rob.
ZIVO_PREMOR_TOPLO_S = 300.0
#: Nadaljevanje po sproscenem premoru caka uporabnik: predvajanje se zacne ze pri 10 % zaloge (1 s) namesto 40 %, nato
#: velja spet ZIVO_ZACETNA_ZALOGA (zastoj se polni do 4 s). Izmerjeno 18. 10. 2026: tisina po nadaljevanju z izbruhom
#: streznika (64 KB) 1,2 s -> glej meritev v sporocilu commita; brez izbruha 5,1 s -> ~1 s.
ZIVO_NADALJUJ_ZALOGA = 0.1
#: Tok brez znane dolzine, ki po nalaganju tece vsaj toliko sekund, je prenos v zivo (radio, ki je na seznamu kot skladba):
#: stran ga oznaci »V zivo« in ga samodejni prehod vrste preskoci (sicer bi vrsta na njem obstala - prenos nima konca).
ZIVO_PREPOZNAJ_S = 3.0


def je_zivi_tok(s: Skladba | None) -> bool:
    """Radio prek http(s): tok brez znane dolzine, ki ga medpomnimo in ob prekinitvi sami znova povezemo."""
    return bool(s and s.vrsta == "radio" and urlsplit(s.uri).scheme in ("http", "https"))


class Predvajalnik:
    def __init__(self, gst, sprememba=None, konec=None):
        self.gst = gst
        self.sprememba = sprememba or (lambda: None)
        self.konec = konec or (lambda _uri: None)
        self.vrsta: list[Skladba] = []
        self.indeks = -1
        self.stanje = "ustavljeno"
        self.napaka = ""
        self._cakaj_zacetek = 0
        #: Izbira podnapisov, ki velja za vse videe: {"izklop": None|bool, "jezik": ""}. None = samodejno
        #: (edini podnapis ob videu ali podnapis v jeziku sistema). Shrani jo klicatelj (shrani_podnapise).
        self.nastavitve_podnapisov = {"izklop": None, "jezik": ""}
        self.shrani_podnapise = lambda _n: None
        self.jezik_sistema = ""
        #: (uri, ime) -> uri popravljene kopije (core.podnapisi.pripravi); None = predvajalnik bere izvirnik.
        self.pripravi_podnapis = None
        self.v_glavni = lambda f: f()  # safeer_os: GLib.idle_add - playbin spreminjamo samo v glavni niti
        self.nit = True
        self._pripravljeni: dict = {}
        self._zunanji = -1           # izbrana datoteka podnapisov trenutnega videa (indeks v podnapisi)
        self._izberi_zunanji = False  # po nalaganju izberi dodani tok podnapisov
        self._samodejno_vgrajeni = False
        #: Zamik zvoka in podnapisov v ms za trenutni posnetek (core/predvajalnik_moznosti.py); nov posnetek = 0.
        self.zamik_zvoka = 0
        self.zamik_podnapisov = 0
        #: Zakasnitev izhoda v ms (zvok gre na zvocnik v omrezju, core/zvok_na_zvocnik.py): za toliko zamaknemo sliko,
        #: da se ustnice ujemajo. Velja za vse posnetke, dokler zvok ne pride nazaj (0); pri samem zvoku nima ucinka.
        self.zakasnitev_izhoda = 0
        #: {"zvok_jezik", "izenacevalnik", "po_meri"} - shrani jih klicatelj (shrani_moznosti).
        self.moznosti = _moznosti.privzete()
        self.shrani_moznosti = lambda _n: None
        self._samodejni_zvok = False
        self._obnovi_zvok = -1        # izbrani zvocni tok po ponovnem nalaganju (zamenjava podnapisov)
        self.izenacevalnik = None     # element equalizer-10bands; None = izenacevalnika ni (meni ga ne pokaze)
        self._predojacitev = None
        #: Odlozen klic (sekunde, f) za ponovne povezave radia; None = GLib.timeout_add v glavni zanki.
        self.cez = None
        self._ura = time.monotonic
        self._zivo = False             # trenutna skladba je radio v zivo (glej je_zivi_tok)
        self._zivo_nastavljeno = False  # playbin ima nastavitve za radio, ob datoteki jih povrnemo
        self._rod = 0                  # vsak nov zacetek/ustavitev razveljavi odlozene ponovne povezave
        self._poskus = 0               # zaporedni neuspeli poskusi povezave (ZIVO_ODMIKI_S)
        self._tihi_premor = False      # premor radia: tok tece utisan (ZIVO_PREMOR_TOPLO_S)
        self._hitro_nadaljuj = False   # prvo polnjenje po nadaljevanju z nizjo zalogo (ZIVO_NADALJUJ_ZALOGA)
        self._zivo_ponastavi()
        self.statistika = self._prazna_statistika()
        self.element = gst.ElementFactory.make("playbin", "safeer-media")
        if self.element is None:
            raise RuntimeError("GStreamer playbin ni na voljo")
        self._pripravi_izenacevalnik()
        self.vodilo = self.element.get_bus()
        self.vodilo.add_signal_watch()
        self.vodilo.connect("message", self._sporocilo)
        #: Poskusi trenutnega posnetka: [(uri, glave), ...] - prvi je izbrani tok, ostali njegove razlicice.
        self._poskusi: list = []
        self._razlicica = 0            # indeks v _poskusi (radio ima svoj stevec _poskus)
        self._glave: tuple = ()
        self._nalozeno = False
        #: Klic, ko se posnetek ne odpre z nobeno razlicico (Medijski center ga oznaci kot nepredvajljivega).
        self.neuspeh = lambda _skladba: None
        #: (ms, f): zakasnjen klic v glavni niti (safeer_os: GLib.timeout_add); privzeto takoj.
        self.zakasni = lambda _ms, f: f()
        try:
            # playbin ustvari vir sele ob odpiranju: glave toka (Referer ...) in nastavitve radia v zivo.
            self.element.connect("source-setup", self._izvor)
            self.element.connect("deep-element-added", self._zivo_element)
        except Exception:  # noqa: BLE001
            pass

    def _izvor(self, playbin, izvor) -> None:
        """source-setup: glave toka (Referer ...) za souphttpsrc in nastavitve radia v zivo."""
        self._nastavi_vir(playbin, izvor)
        self._zivo_izvor(playbin, izvor)

    @property
    def trenutna(self) -> Skladba | None:
        if 0 <= self.indeks < len(self.vrsta):
            return self.vrsta[self.indeks]
        return None

    def dodaj(self, uri: str, predvajaj: bool = False, vrsta: str = "medij", naslov: str = "",
              zacetek: int = 0) -> None:
        vnos = medij(uri, vrsta)
        if naslov:
            vnos = replace(vnos, naslov=str(naslov)[:80])
        if zacetek > 0 and vrsta in ("medij", "video"):
            vnos = replace(vnos, zacetek=max(0, int(zacetek)))
        if len(self.vrsta) >= 500:
            self.vrsta.pop(0)
            self.indeks = max(-1, self.indeks - 1)
        self.vrsta.append(vnos)
        if self.indeks < 0 or predvajaj or self.stanje in ("ustavljeno", "napaka"):
            self.predvajaj(len(self.vrsta) - 1)
        else:
            self.sprememba()

    def zamenjaj_vrsto(self, vnosi: list[Skladba], zacni: int = 0) -> bool:
        """Začni nov album ali seznam pri vnosu `zacni`; pred zamenjavo preveri vse vnose."""
        if not vnosi or len(vnosi) > 500 or not 0 <= zacni < len(vnosi):
            return False
        preverjeni = [replace(medij(v.uri, v.vrsta), naslov=v.naslov[:80],
                             zacetek=max(0, int(v.zacetek)), izvor=str(v.izvor or "")[:80],
                             podnapisi=_cisti_podnapisi(v.podnapisi),
                             naprava=str(v.naprava or "")[:80], oznaka=str(v.oznaka or "")[:1024],
                             izvirnik=str(v.izvirnik or "")[:2048], glave=cisti_glave(v.glave),
                             nadomestni=cisti_nadomestne(v.nadomestni)) for v in vnosi]
        self.vrsta = preverjeni
        self.indeks = -1
        return self.predvajaj(zacni)

    def predvajaj(self, indeks: int) -> bool:
        if not 0 <= indeks < len(self.vrsta):
            return False
        self.element.set_state(self.gst.State.NULL)
        self._zivo_konec()
        self._utisaj(False)            # tihi premor prejsnje postaje ne velja za nov posnetek
        self.indeks = indeks
        self.napaka = ""
        self._cakaj_zacetek = self.vrsta[indeks].zacetek
        if self._cakaj_zacetek:
            self.vrsta[indeks] = replace(self.vrsta[indeks], zacetek=0)
        if self.vrsta[indeks].uri.startswith("dvd://"):
            # Zaščitenih diskov (CSS) ne predvajamo - tudi če ima sistem knjižnico, ki bi jih odklenila.
            from core import os_dvd
            # Samo izrecno preverjen disk brez zaščite; če preverba ne uspe (None), ne predvajamo.
            if os_dvd.je_zasciten(self.vrsta[indeks].uri) is not False:
                self.napaka = "dvd"
                self.stanje = "napaka"
                self.sprememba()
                return False
        s = self.vrsta[indeks]
        self._poskusi = [(s.uri, tuple(s.glave or ()))] + [n for n in (s.nadomestni or ()) if n[0] != s.uri]
        self._razlicica, self._glave, self._nalozeno = 0, tuple(s.glave or ()), False
        self._dekoder, self._stari_dekoderji = "", set()
        self._nastavi_zivo(je_zivi_tok(s))
        self.element.set_property("uri", s.uri)
        self._pripravi_podnapise(self.vrsta[indeks])
        # Zamik velja za en posnetek (kot v VLC); jezik zvoka izberemo, ko playbin pozna tokove (ASYNC_DONE).
        self.nastavi_zamik("zvok", 0)
        self.nastavi_zamik("podnapisi", 0)
        self._samodejni_zvok, self._obnovi_zvok = True, -1
        rezultat = self.element.set_state(self.gst.State.PLAYING)
        if rezultat == self.gst.StateChangeReturn.FAILURE:
            # Tiho (lastnik 18. 10. 2026): brez naslednje skladbe tu - ta bi se v isti nit klicala rekurzivno.
            _dnevnik_napake("zacetek", self.vrsta[indeks].vrsta)
            self.element.set_state(self.gst.State.NULL)
            self._zivo_konec()
            self.stanje = "ustavljeno"
        else:
            self.stanje = "predvaja"
        self.sprememba()
        return self.stanje == "predvaja"

    # ------------------------------------------------------------------ podnapisi

    def _besedilo(self, vklop: bool) -> None:
        try:
            zastavice = int(self.element.get_property("flags"))
            zastavice = zastavice | ZASTAVICA_BESEDILO if vklop else zastavice & ~ZASTAVICA_BESEDILO
            self.element.set_property("flags", zastavice)
        except Exception:
            pass

    def _nastavi_zunanji(self, k: int) -> None:
        s = self.trenutna
        self._zunanji = k if s is not None and 0 <= k < len(s.podnapisi) else -1
        uri = s.podnapisi[self._zunanji][0] if self._zunanji >= 0 else None
        if uri and self.pripravi_podnapis is not None and uri not in self._pripravljeni:
            if not self.nit:
                self._pripravljeni[uri] = self.pripravi_podnapis(uri, s.podnapisi[self._zunanji][1])
            else:
                # Popravljeno kopijo pripravimo v ozadju (torrent ali naprava); ko je nared, jo naložimo.
                self._pripravi_v_ozadju(uri, s.podnapisi[self._zunanji][1], self.indeks, self._zunanji)
                uri = None
        try:
            self.element.set_property("suburi", self._pripravljeni.get(uri, uri) if uri else None)
        except Exception:
            self._zunanji = -1
        self._izberi_zunanji = uri is not None and self._zunanji >= 0

    def _pripravi_v_ozadju(self, uri: str, ime: str, indeks: int, k: int) -> None:
        import threading

        def delo():
            try:
                self._pripravljeni[uri] = self.pripravi_podnapis(uri, ime)
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] podnapisi:", ime, e, flush=True)
                self._pripravljeni[uri] = uri
            self.v_glavni(lambda: self._podnapis_pripravljen(indeks, k))
        threading.Thread(target=delo, name="safeer-podnapisi", daemon=True).start()

    def _podnapis_pripravljen(self, indeks: int, k: int) -> bool:
        """Podnapis je pripravljen: če ga uporabnik še vedno želi pri tem videu, ga naložimo na istem mestu."""
        if self.indeks == indeks and self._zunanji == k and self.stanje in ("predvaja", "premor"):
            self._znova_zazeni(k)
        return False

    def _pripravi_podnapise(self, s: Skladba) -> None:
        """Pred začetkom videa: zunanja datoteka po izbiri uporabnika ali samodejno (kot VLC)."""
        n = self.nastavitve_podnapisov
        k = -1
        if n.get("izklop") is not True and s.podnapisi:
            jeziki = [j for j in (n.get("jezik"), self.jezik_sistema) if j]
            for j in jeziki:
                k = next((i for i, p in enumerate(s.podnapisi) if p[2] == j), -1)
                if k >= 0:
                    break
            if k < 0 and (len(s.podnapisi) == 1 or n.get("izklop") is False):
                k = 0
        self._nastavi_zunanji(k)
        # Vgrajene podnapise pokažemo samo, če je uporabnik izrecno vklopil podnapise ali se jezik ujema.
        self._samodejno_vgrajeni = k < 0 and n.get("izklop") is not True
        self._besedilo(k >= 0 or n.get("izklop") is False)

    def _po_nalaganju_podnapisi(self) -> None:
        try:
            stevilo = int(self.element.get_property("n-text"))
        except Exception:
            return
        cakajoci = getattr(self, "_vgrajeni_po_nalaganju", -1)
        if cakajoci >= 0:
            self._vgrajeni_po_nalaganju = -1
            if cakajoci < stevilo:
                self.element.set_property("current-text", cakajoci)
                self._besedilo(True)
            return
        if self._izberi_zunanji:
            self._izberi_zunanji = False
            if stevilo > 0:
                # Zunanja datoteka je zadnji tok besedila v playbinu.
                self.element.set_property("current-text", stevilo - 1)
                self._besedilo(True)
            return
        if self._samodejno_vgrajeni:
            self._samodejno_vgrajeni = False
            jeziki = [j for j in (self.nastavitve_podnapisov.get("jezik"), self.jezik_sistema) if j]
            for i in range(stevilo):
                if self._jezik_toka(i) in jeziki:
                    self.element.set_property("current-text", i)
                    self._besedilo(True)
                    return

    def _jezik_toka(self, i: int) -> str:
        try:
            oznake = self.element.emit("get-text-tags", i)
            if oznake is not None:
                ok, koda = oznake.get_string("language-code")
                if ok and koda:
                    return str(koda)[:2].lower()
        except Exception:
            pass
        return ""

    def podnapisi(self) -> dict:
        """Možnosti za izbiro: vgrajeni tokovi ("v:<i>") in datoteke ob videu ("z:<i>")."""
        s = self.trenutna
        moznosti = []
        izbran = "izklop"
        try:
            stevilo = int(self.element.get_property("n-text"))
            trenutni = int(self.element.get_property("current-text"))
            vklop = bool(int(self.element.get_property("flags")) & ZASTAVICA_BESEDILO)
        except Exception:
            stevilo, trenutni, vklop = 0, -1, False
        # Zunanja datoteka je zadnji tok; med vgrajenimi je ne štejemo dvakrat.
        vgrajenih = stevilo - (1 if self._zunanji >= 0 and stevilo > 0 else 0)
        for i in range(max(0, vgrajenih)):
            moznosti.append({"kljuc": "v:%d" % i, "jezik": self._jezik_toka(i), "ime": "", "vgrajeni": True})
            if vklop and trenutni == i:
                izbran = "v:%d" % i
        if s is not None:
            for i, p in enumerate(s.podnapisi):
                moznosti.append({"kljuc": "z:%d" % i, "jezik": p[2], "ime": p[1], "oznaka": p[3], "vgrajeni": False})
            if vklop and self._zunanji >= 0 and (stevilo == 0 or trenutni == stevilo - 1):
                izbran = "z:%d" % self._zunanji
        return {"moznosti": moznosti, "izbran": izbran}

    def izberi_podnapise(self, kljuc: str) -> bool:
        s = self.trenutna
        if s is None:
            return False
        kljuc = str(kljuc or "")
        if kljuc == "izklop":
            self._besedilo(False)
            self.nastavitve_podnapisov = {"izklop": True, "jezik": self.nastavitve_podnapisov.get("jezik", "")}
        elif kljuc.startswith("v:"):
            i = int(kljuc[2:])
            if self._zunanji >= 0:
                self._znova_zazeni(-1)
                self._vgrajeni_po_nalaganju = i    # current-text velja šele, ko so tokovi znani
            self.element.set_property("current-text", i)
            self._besedilo(True)
            self.nastavitve_podnapisov = {"izklop": False, "jezik": self._jezik_toka(i) or self.nastavitve_podnapisov.get("jezik", "")}
        elif kljuc.startswith("z:"):
            i = int(kljuc[2:])
            if not 0 <= i < len(s.podnapisi):
                return False
            if i != self._zunanji:
                self._znova_zazeni(i)
            else:
                self._besedilo(True)
            self.nastavitve_podnapisov = {"izklop": False, "jezik": s.podnapisi[i][2] or self.nastavitve_podnapisov.get("jezik", "")}
        else:
            return False
        self.shrani_podnapise(dict(self.nastavitve_podnapisov))
        self.sprememba()
        return True

    def _znova_zazeni(self, zunanji: int) -> None:
        """playbin zamenja datoteko podnapisov samo ob ponovnem nalaganju: nadaljujemo na istem mestu."""
        try:
            ok, ns = self.element.query_position(self.gst.Format.TIME)
            pozicija = int(ns / self.gst.SECOND) if ok and ns != self.gst.CLOCK_TIME_NONE else 0
        except Exception:
            pozicija = 0
        igra = self.stanje == "predvaja"
        try:
            self._obnovi_zvok = int(self.element.get_property("current-audio"))
        except Exception:
            self._obnovi_zvok = -1
        self.element.set_state(self.gst.State.READY)
        self._nastavi_zunanji(zunanji)
        self._besedilo(zunanji >= 0)
        self._cakaj_zacetek = pozicija
        self.element.set_state(self.gst.State.PLAYING if igra else self.gst.State.PAUSED)
        if not igra:
            # Premor: skok opravimo takoj po nalaganju (poskusi_nadaljevati zahteva predvajanje).
            self._premor_skok = pozicija

    # ------------------------------------------------------------------ zvocni posnetki

    def _oznake_zvoka(self, i: int) -> dict:
        """Jezik, kodek, naslov (oznake toka) in stevilo kanalov (zmoznosti blazinice) zvocnega toka i."""
        izid = {"jezik": "", "kodek": "", "naslov": "", "kanali": 0}
        try:
            oznake = self.element.emit("get-audio-tags", i)
            if oznake is not None:
                for kljuc, ime in (("jezik", "language-code"), ("kodek", "audio-codec"), ("naslov", "title")):
                    ok, vrednost = oznake.get_string(ime)
                    if ok and vrednost:
                        izid[kljuc] = str(vrednost)[:80]
        except Exception:
            pass
        try:
            blazinica = self.element.emit("get-audio-pad", i)
            zmoznosti = blazinica.get_current_caps() if blazinica is not None else None
            if zmoznosti is not None and zmoznosti.get_size() > 0:
                ok, kanali = zmoznosti.get_structure(0).get_int("channels")
                if ok:
                    izid["kanali"] = int(kanali)
        except Exception:
            pass
        return izid

    def zvocni_toki(self, jezik_vmesnika: str = "sl", privzeto: str = "{n}") -> dict:
        """{"moznosti": [{"kljuc": i, "ime", "jezik"}], "izbran": i} - ime kot v Kodiju (»Slovenščina · AC3 5.1«)."""
        try:
            stevilo = int(self.element.get_property("n-audio") or 0)
            trenutni = int(self.element.get_property("current-audio"))
        except Exception:
            stevilo, trenutni = 0, -1
        moznosti = []
        for i in range(max(0, min(stevilo, 32))):
            o = self._oznake_zvoka(i)
            moznosti.append({"kljuc": i, "jezik": o["jezik"],
                             "ime": _moznosti.ime_zvocnega_toka(i, o["jezik"], o["kodek"], o["kanali"], o["naslov"],
                                                                jezik_vmesnika, privzeto)})
        return {"moznosti": moznosti, "izbran": trenutni if 0 <= trenutni < stevilo else (0 if stevilo else -1)}

    def izberi_zvok(self, i: int, zapomni: bool = True) -> bool:
        try:
            stevilo = int(self.element.get_property("n-audio") or 0)
        except Exception:
            stevilo = 0
        if self.trenutna is None or not 0 <= int(i) < stevilo:
            return False
        self.element.set_property("current-audio", int(i))
        if zapomni:
            from core import podnapisi as _pn
            jezik = _pn.iso1(self._oznake_zvoka(int(i))["jezik"])
            if jezik and jezik != self.moznosti.get("zvok_jezik"):
                self.moznosti = dict(self.moznosti, zvok_jezik=jezik)
                self.shrani_moznosti(dict(self.moznosti))
        self.sprememba()
        return True

    def naslednji_zvok(self) -> int:
        """Tipka B (kot v VLC): naslednji zvocni posnetek; -1, ce ga ni."""
        stanje = self.zvocni_toki()
        n = len(stanje["moznosti"])
        if n < 2:
            return -1
        i = (stanje["izbran"] + 1) % n
        return i if self.izberi_zvok(i) else -1

    def _po_nalaganju_zvok(self) -> None:
        if self._obnovi_zvok >= 0:
            i, self._obnovi_zvok = self._obnovi_zvok, -1
            self.izberi_zvok(i, zapomni=False)
            return
        if not self._samodejni_zvok:
            return
        self._samodejni_zvok = False
        zeleni = self.moznosti.get("zvok_jezik") or ""
        if not zeleni:
            return
        try:
            stevilo = int(self.element.get_property("n-audio") or 0)
            trenutni = int(self.element.get_property("current-audio"))
        except Exception:
            return
        if stevilo < 2:
            return
        i = _moznosti.izberi_po_jeziku([self._oznake_zvoka(k)["jezik"] for k in range(stevilo)], [zeleni])
        if i >= 0 and i != trenutni:
            self.element.set_property("current-audio", i)

    # ------------------------------------------------------------------ zamik zvoka in podnapisov

    def nastavi_zamik(self, vrsta: str, ms: int) -> int:
        """vrsta "zvok" (pozitivno = zvok kasneje) ali "podnapisi" (pozitivno = podnapisi kasneje)."""
        if vrsta == "zvok":
            self.zamik_zvoka = _moznosti.premakni_zamik(ms, 0, _moznosti.MEJA_ZVOK_MS)
            lastnost, vrednost = "av-offset", _moznosti.av_offset_ns(self.zamik_zvoka - self.zakasnitev_izhoda)
        elif vrsta == "podnapisi":
            self.zamik_podnapisov = _moznosti.premakni_zamik(ms, 0, _moznosti.MEJA_PODNAPISI_MS)
            lastnost, vrednost = "text-offset", _moznosti.text_offset_ns(self.zamik_podnapisov)
        else:
            return 0
        try:
            self.element.set_property(lastnost, vrednost)
        except Exception as e:  # noqa: BLE001 - starejsi GStreamer brez lastnosti: zamik ostane 0
            print("[SafeerOS] zamik:", lastnost, e, flush=True)
        return self.zamik_zvoka if vrsta == "zvok" else self.zamik_podnapisov

    def nastavi_zakasnitev_izhoda(self, ms: int) -> int:
        """Zvok zamuja za ms (zvocnik v omrezju): slika pocaka toliko (av-offset > 0); 0 = brez zamika slike."""
        try:
            self.zakasnitev_izhoda = max(0, int(ms))
        except (TypeError, ValueError):
            self.zakasnitev_izhoda = 0
        self.nastavi_zamik("zvok", self.zamik_zvoka)
        return self.zakasnitev_izhoda

    def premakni_zamik(self, vrsta: str, korak_ms: int) -> int:
        trenutni = self.zamik_zvoka if vrsta == "zvok" else self.zamik_podnapisov
        return self.nastavi_zamik(vrsta, trenutni + int(korak_ms))

    # ------------------------------------------------------------------ izenacevalnik

    def _pripravi_izenacevalnik(self) -> None:
        """equalizer-10bands kot audio-filter playbina (velja za vse posnetke). Obdelava v F32: dvig pasov ne poci,
        predojacitev (volume) pred izhodom odsteje najvecji dvig. Brez elementa izenacevalnika ni (meni ga skrije).
        Izmerjeno 14. 10. 2026 (600 s stereo 48 kHz, en procesor): Ravno +0,1 % CPU, Bas +1,1 % CPU."""
        try:
            if not hasattr(self.gst, "parse_bin_from_description") or self.gst.ElementFactory.find("equalizer-10bands") is None:
                return
            vreca = self.gst.parse_bin_from_description(
                "audioconvert ! audio/x-raw,format=F32LE ! equalizer-10bands name=safeer-eq ! "
                "volume name=safeer-eq-predojacitev ! audioconvert", True)
            self.element.set_property("audio-filter", vreca)
            self.izenacevalnik = vreca.get_by_name("safeer-eq")
            self._predojacitev = vreca.get_by_name("safeer-eq-predojacitev")
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] izenacevalnik ni na voljo:", e, flush=True)
            self.izenacevalnik = self._predojacitev = None
            return
        self.nastavi_izenacevalnik(self.moznosti.get("izenacevalnik", "ravno"), self.moznosti.get("po_meri"), shrani=False)

    def nastavi_izenacevalnik(self, izbira: str, po_meri=None, shrani: bool = True) -> list:
        """Prednastavitev (ali Po meri z desetimi vrednostmi v dB) takoj, tudi med predvajanjem."""
        if izbira not in _moznosti.IZBIRE_IZENACEVALNIKA:
            izbira = "ravno"
        if po_meri is None:
            po_meri = self.moznosti.get("po_meri")
        ojacitve = _moznosti.ojacitve(izbira, po_meri)
        if self.izenacevalnik is not None:
            for i, db in enumerate(ojacitve):
                self.izenacevalnik.set_property("band%d" % i, float(db))
            if self._predojacitev is not None:
                self._predojacitev.set_property("volume", _moznosti.predojacitev(ojacitve))
        self.moznosti = dict(self.moznosti, izenacevalnik=izbira)
        if izbira == _moznosti.PO_MERI:
            self.moznosti["po_meri"] = ojacitve
        if shrani:
            self.shrani_moznosti(dict(self.moznosti))
        return ojacitve

    # ------------------------------------------------------------------ podnapisi iz datoteke ali s spleta

    def dodaj_podnapis(self, uri: str, ime: str, jezik: str = "", oznaka: str = "") -> bool:
        """Uporabnik je izbral datoteko (ali prenos s spleta): dodamo jo k trenutnemu videu in jo takoj izberemo."""
        s = self.trenutna
        if s is None or urlsplit(str(uri or "")).scheme not in ("file", "https", "http"):
            return False
        podnapisi = list(s.podnapisi)
        k = next((i for i, p in enumerate(podnapisi) if p[0] == uri), -1)
        if k < 0:
            if len(podnapisi) >= 32:
                podnapisi.pop(0)
                self._zunanji = self._zunanji - 1 if self._zunanji > 0 else -1
            podnapisi.append((str(uri), str(ime or "")[:120], str(jezik or "")[:8], str(oznaka or "")[:40]))
            k = len(podnapisi) - 1
            self.vrsta[self.indeks] = replace(s, podnapisi=tuple(podnapisi))
        return self.izberi_podnapise("z:%d" % k)

    # ------------------------------------------------------------------ DVD meni

    def je_dvd(self) -> bool:
        return bool(self.trenutna and self.trenutna.uri.startswith("dvd://"))

    def navigacija(self, ukaz: str) -> bool:
        """Premik po meniju DVD (puščice, potrditev) in skok v meni - kot daljinec predvajalnika DVD."""
        if not self.je_dvd():
            return False
        try:
            import gi
            gi.require_version("GstVideo", "1.0")
            from gi.repository import GstVideo
            ukazi = {"gor": GstVideo.NavigationCommand.UP, "dol": GstVideo.NavigationCommand.DOWN,
                     "levo": GstVideo.NavigationCommand.LEFT, "desno": GstVideo.NavigationCommand.RIGHT,
                     "potrdi": GstVideo.NavigationCommand.ACTIVATE, "meni": GstVideo.NavigationCommand.DVD_MENU,
                     "naslovi": GstVideo.NavigationCommand.DVD_TITLE_MENU}
            if ukaz not in ukazi:
                return False
            return bool(self.element.send_event(GstVideo.Navigation.event_new_command(ukazi[ukaz])))
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] DVD meni:", e, flush=True)
            return False

    def premor(self) -> None:
        if self.trenutna is None:
            return
        if self._zivo:
            self._zivo_premor()
            return
        cilj = self.gst.State.PAUSED if self.stanje == "predvaja" else self.gst.State.PLAYING
        if self.element.set_state(cilj) != self.gst.StateChangeReturn.FAILURE:
            self.stanje = "premor" if cilj == self.gst.State.PAUSED else "predvaja"
            self.sprememba()

    def skok(self, sekunde: float) -> bool:
        if self.trenutna is None or self.trenutna.vrsta in ("tv", "radio"):
            return False
        dolzina = self.trajanje()
        if dolzina <= 0:
            return False
        cilj = max(0.0, min(float(sekunde), dolzina))
        return bool(self.element.seek_simple(self.gst.Format.TIME,
                    self.gst.SeekFlags.FLUSH | self.gst.SeekFlags.KEY_UNIT, int(cilj * self.gst.SECOND)))

    def poskusi_nadaljevati(self) -> bool:
        if not self._cakaj_zacetek or self.stanje != "predvaja":
            return False
        try:
            trajanje = self.trajanje()
            if trajanje <= 0:
                return False
            if trajanje < self._cakaj_zacetek + 20:
                self._cakaj_zacetek = 0
                return False
            if self.skok(self._cakaj_zacetek):
                self._cakaj_zacetek = 0
                return True
        except Exception:
            pass
        return False

    def trajanje(self) -> float:
        if self.trenutna is None:
            return 0.0
        ok, ns = self.element.query_duration(self.gst.Format.TIME)
        return max(0.0, ns / self.gst.SECOND) if ok and ns != self.gst.CLOCK_TIME_NONE else 0.0

    def podatki(self) -> dict:
        try:
            ok, ns = self.element.query_position(self.gst.Format.TIME)
            pozicija = max(0.0, ns / self.gst.SECOND) if ok and ns != self.gst.CLOCK_TIME_NONE else 0.0
            dolzina = self.trajanje()
        except Exception:
            pozicija, dolzina = 0.0, 0.0
        zacetek = max(0, self.indeks - 2)
        return {"stanje": self.stanje, "naslov": self.trenutna.naslov if self.trenutna else "",
                "vrsta": self.trenutna.vrsta if self.trenutna else "", "indeks": self.indeks,
                "izvor": self.trenutna.izvor if self.trenutna else "",
                "zacetniIndeks": zacetek,
                "skupaj": len(self.vrsta),
                "vrstaSeznam": [{"naslov": v.naslov, "vrsta": v.vrsta, "izvor": v.izvor}
                                for v in self.vrsta[zacetek:zacetek + 18]],
                "pozicija": pozicija, "trajanje": dolzina, "napaka": self.napaka,
                "zivo": self.je_v_zivo(pozicija, dolzina),
                "podnapisi": bool(self.trenutna and (self.trenutna.podnapisi or self._stevilo_besedil()))}

    def je_v_zivo(self, pozicija: float, dolzina: float) -> bool:
        """Trenutni posnetek je prenos v zivo: postaja ali TV, ali spletni tok, ki tece ZIVO_PREPOZNAJ_S brez dolzine."""
        s = self.trenutna
        if s is None:
            return False
        if s.vrsta in ("tv", "radio"):
            return True
        return bool(self._nalozeno and dolzina <= 0 and pozicija >= ZIVO_PREPOZNAJ_S
                    and urlsplit(s.uri).scheme in ("http", "https"))

    def _stevilo_besedil(self) -> int:
        try:
            return int(self.element.get_property("n-text"))
        except Exception:
            return 0

    def naslednja(self) -> bool:
        return self.predvajaj(self.indeks + 1)

    def _naslednja_samodejno(self) -> bool:
        """Samodejni prehod po koncu posnetka ali tihi napaki: postaj in TV v vrsti ne zacne (prenos nima konca, vrsta bi
        na njem obstala); izbere jih uporabnik sam. Iz prenosa v zivo (seznam postaj) gre naprej kot doslej."""
        s = self.trenutna
        i = self.indeks + 1
        if s is None or s.vrsta not in ("tv", "radio"):
            while i < len(self.vrsta) and self.vrsta[i].vrsta in ("tv", "radio"):
                i += 1
        return self.predvajaj(i)

    def prejsnja(self) -> bool:
        return self.predvajaj(self.indeks - 1)

    def ustavi(self) -> None:
        self._cakaj_zacetek = 0
        self.element.set_state(self.gst.State.NULL)
        self._zivo_konec()
        self._utisaj(False)
        self.stanje = "ustavljeno"
        self.sprememba()

    def zapri(self) -> None:
        self.ustavi()
        self.vodilo.remove_signal_watch()

    def _nastavi_vir(self, _playbin, vir) -> None:
        """playbin je ustvaril vir (souphttpsrc): glave, ki jih tok zahteva."""
        if not self._glave:
            return
        try:
            if vir.find_property("extra-headers") is None:
                return
            struktura = self.gst.Structure.new_empty("extra-headers")
            for ime, vrednost in self._glave:
                if ime.lower() == "user-agent" and vir.find_property("user-agent") is not None:
                    vir.set_property("user-agent", vrednost)
                else:
                    struktura.set_value(ime, vrednost)
            vir.set_property("extra-headers", struktura)
        except Exception as e:  # noqa: BLE001 - brez glav tok morda vseeno dela
            print("[SafeerOS] glave toka:", type(e).__name__, flush=True)

    def _naslednji_poskus(self, status: int) -> bool:
        """Tok se ni odprl: tiho naslednja razlicica. Po 429/403/401 (streznik zavraca ta naslov ali te glave) najprej
        razlicice z drugih streznikov, isti streznik sele nato (po 429 s kratkim premorom)."""
        if self._nalozeno or self._razlicica + 1 >= len(self._poskusi):
            return False
        neuspel = urlsplit(self._poskusi[self._razlicica][0]).hostname
        ostali = self._poskusi[self._razlicica + 1:]
        if status in (401, 403, 429):
            drugi = [p for p in ostali if urlsplit(p[0]).hostname != neuspel]
            isti = [p for p in ostali if urlsplit(p[0]).hostname == neuspel]
            ostali = drugi + isti
        self._poskusi[self._razlicica + 1:] = ostali
        self._razlicica += 1
        if self._dekoder:
            # Neuspeli vir poslje se kaksno napako (»streaming stopped«): ta ne velja za naslednjo razlicico.
            self._stari_dekoderji.add(self._dekoder)
        uri, glave = self._poskusi[self._razlicica]
        indeks = self.indeks
        print("[SafeerOS] predvajanje: tok %d/%d ni odprt (%s), poskusim naslednjo razlicico" % (
            self._razlicica, len(self._poskusi), status or "napaka"), flush=True)

        def zacni() -> bool:
            if self.indeks != indeks or self.stanje != "predvaja":
                return False
            self.element.set_state(self.gst.State.NULL)
            self._glave = tuple(glave or ())
            self.element.set_property("uri", uri)
            if self.element.set_state(self.gst.State.PLAYING) == self.gst.StateChangeReturn.FAILURE:
                if not self._naslednji_poskus(0):
                    self._koncna_napaka("zacetek")
            return False
        self.stanje = "predvaja"
        if status == 429 and urlsplit(uri).hostname == neuspel:
            self.zakasni(2000, zacni)      # isti streznik je rekel »prevec zahtev«: kratek premor
        else:
            zacni()
        return True

    def _koncna_napaka(self, koda: str) -> None:
        """Nobena razlicica ne dela. Samo tok, ki ga noben streznik ni dal (ne manjkajoci kodek na tem racunalniku):
        naslov ni predvajljiv in se ne prikaze vec. Nato tiho naprej (lastnik 18. 10. 2026: brez sporocila)."""
        if koda == "tok" and not self._nalozeno and self.trenutna is not None:
            try:
                self.neuspeh(self.trenutna)
            except Exception:  # noqa: BLE001
                pass
        self._tiho_naprej(koda)

    def _sporocilo(self, _vodilo, sporocilo) -> None:
        if self._zivo and self._zivo_sporocilo(sporocilo):
            return
        if sporocilo.type == self.gst.MessageType.EOS:
            if self.trenutna:
                self.konec(self.trenutna.uri)
            if not self._naslednja_samodejno():
                self.ustavi()
        elif sporocilo.type == self.gst.MessageType.ASYNC_DONE:
            self._nalozeno = True
            self._po_nalaganju_podnapisi()
            self._po_nalaganju_zvok()
            if getattr(self, "_premor_skok", 0):
                cilj, self._premor_skok = self._premor_skok, 0
                self._cakaj_zacetek = 0
                self.skok(cilj)
            self.poskusi_nadaljevati()
        elif sporocilo.type == self.gst.MessageType.ERROR:
            napaka, razhroscevanje = sporocilo.parse_error()
            import re
            dekoder = re.search(r"uridecodebin\d+", str(razhroscevanje or ""))
            if dekoder and dekoder.group(0) in getattr(self, "_stari_dekoderji", ()):
                return          # zakasnela napaka prejsnje (ze zamenjane) razlicice
            if dekoder:
                self._dekoder = dekoder.group(0)
            # Surova napaka GStreamerja gre v dnevnik (stderr = sled.log); uporabnik ne vidi nicesar (lastnik 18. 10. 2026).
            # Podpisani naslovi toka (sign=..., token ...) ne gredo v dnevnik: samo gostitelj.
            print("[SafeerOS] predvajanje:", napaka, re.sub(r"\?\S*", "?…", str(razhroscevanje or "")),
                  file=sys.stderr, flush=True)
            uri = self._poskusi[self._razlicica][0] if self._razlicica < len(self._poskusi) else (self.trenutna.uri if self.trenutna else "")
            koda = vrsta_napake(napaka, uri)
            # Tok z mrezo, ki se ni odprl: streznik ga ne da (tok) ali je namesto posnetka poslal stran HTML oziroma zapis,
            # ki ga ta racunalnik ne zna (format) - druga razlicica je morda v redu.
            if (koda == "tok" or (koda == "format" and uri.startswith(("http://", "https://")))) \
                    and self._naslednji_poskus(status_napake(razhroscevanje)):
                return
            self._koncna_napaka(koda)

    def _tiho_naprej(self, koda: str) -> None:
        """Napaka predvajanja brez sporocila uporabniku: sled v stderr, nato naslednja skladba v vrsti (radio:
        naslednja postaja, ce je v vrsti) ali tiha ustavitev. Rekurzije ni: napaka naslednje pride spet po vodilu."""
        s = self.trenutna
        _dnevnik_napake(koda, s.vrsta if s else "")
        self.element.set_state(self.gst.State.NULL)
        self._zivo_konec()
        self.napaka = ""
        naslednja = self.vrsta[self.indeks + 1] if 0 <= self.indeks + 1 < len(self.vrsta) else None
        if naslednja is not None and (s is None or s.vrsta != "radio" or naslednja.vrsta == "radio"):
            if self._naslednja_samodejno():
                return
        self.stanje = "ustavljeno"
        self.sprememba()

    # ------------------------------------------------------------------ radio v zivo: medpomnjenje in ponovna povezava

    @staticmethod
    def _prazna_statistika() -> dict:
        return {"medpomnjenja": 0, "podtoki": 0, "ponovne_povezave": 0, "skoki_na_zivo": 0, "zastoj_s": 0.0}

    def _zivo_ponastavi(self) -> None:
        """Stanje ene povezave z radiem (po vsaki ponovni povezavi od zacetka)."""
        self._polni = False            # queue2 se polni (BUFFERING < 100 %): playbin je zacasno v PAUSED
        self._polni_od = 0.0
        self._polnjenje = 0            # stevec za cuvaja dolgega medpomnjenja
        self._predvajal = False        # po tej povezavi je zvok ze tekel (naslednje medpomnjenje je zastoj)
        self._zaostanek = 0.0          # sekunde za zivim robom (zastoji in premori po tej povezavi)
        self._povezan_od = None        # kdaj je zvok po tej povezavi stekel
        self._premor_od = 0.0
        self._znova_ob_nadaljevanju = False
        self._cakam_povezavo = False   # povezava se je prekinila, ponovna je odlozena (_prekinjeno)

    def _dnevnik(self, *besedilo) -> None:
        print("[SafeerOS] radio:", *besedilo, file=sys.stderr, flush=True)      # stderr = sled.log

    def _cez_klic(self, sekunde: float, f) -> None:
        if self.cez is not None:
            self.cez(sekunde, f)
            return
        from gi.repository import GLib
        GLib.timeout_add(max(1, int(sekunde * 1000)), lambda: (f(), False)[1])

    def _lastnost(self, element, ime: str, vrednost) -> bool:
        """Nastavi lastnost, ce jo element ima (izvor ali izhod je lahko drug element kot pricakujemo)."""
        try:
            if element.find_property(ime) is None:
                return False
            element.set_property(ime, vrednost)
            return True
        except Exception:  # noqa: BLE001
            return False

    def _nastavi_zivo(self, zivo: bool) -> None:
        """Pred nastavitvijo uri (playbin je v NULL): medpomnjenje za radio, sicer privzete nastavitve playbina."""
        self._zivo = zivo
        self._zivo_ponastavi()
        if zivo:
            self.statistika = self._prazna_statistika()
        elif not self._zivo_nastavljeno:
            return                     # datoteke, video, TV: playbina se ne dotaknemo (kot doslej)
        try:
            zastavice = int(self.element.get_property("flags"))
            zastavice = zastavice | ZASTAVICA_MEDPOMNJENJE if zivo else zastavice & ~ZASTAVICA_MEDPOMNJENJE
            self.element.set_property("flags", zastavice)
            self.element.set_property("buffer-duration", ZIVO_MEDPOMNILNIK_S * self.gst.SECOND if zivo else -1)
            self.element.set_property("buffer-size", ZIVO_MEDPOMNILNIK_B if zivo else -1)
            self.element.set_property("connection-speed", ZIVO_HITROST_KBPS if zivo else 0)
        except Exception as e:  # noqa: BLE001
            self._dnevnik("nastavitve medpomnjenja niso uspele:", e)
        self._zivo_nastavljeno = zivo

    def _zivo_izvor(self, _playbin, izvor) -> None:
        """source-setup: souphttpsrc za radio. is-live ostane False, da playbin medpomni (zivi rob vodimo sami)."""
        if not self._zivo:
            return
        for ime, vrednost in (("timeout", ZIVO_HTTP_TIMEOUT_S), ("retries", ZIVO_HTTP_PONOVI),
                              ("keep-alive", True), ("is-live", False)):
            self._lastnost(izvor, ime, vrednost)

    def _zivo_element(self, _playbin, _vreca, element) -> None:
        """deep-element-added: queue2 zacne predvajati pri 4 s zaloge; zvocni izhod dobi vecjo zalogo."""
        if not self._zivo:
            return
        try:
            tovarna = element.get_factory()
            ime = tovarna.get_name() if tovarna is not None else ""
            vrsta = str(tovarna.get_metadata("klass") or "") if tovarna is not None else ""
        except Exception:  # noqa: BLE001
            return
        if ime in ("uridecodebin", "urisourcebin", "queue2"):
            self._lastnost(element, "use-buffering", True)
        if ime == "queue2":
            self._vrsta2 = element
            self._lastnost(element, "high-watermark", ZIVO_NADALJUJ_ZALOGA if self._hitro_nadaljuj else ZIVO_ZACETNA_ZALOGA)
        elif "Sink" in vrsta and "Audio" in vrsta:
            if self._lastnost(element, "buffer-time", ZIVO_IZHOD_ZALOGA_US):
                self._lastnost(element, "latency-time", ZIVO_IZHOD_SEGMENT_US)
                self._lastnost(element, "qos", True)   # pozne/izpuscene vzorce javi kot QOS (stejemo podtoke)
                self._dnevnik("izhod %s: zaloga %d ms, segment %d ms" % (
                    ime, ZIVO_IZHOD_ZALOGA_US // 1000, ZIVO_IZHOD_SEGMENT_US // 1000))

    def _zivo_sporocilo(self, sporocilo) -> bool:
        """Sporocila vodila za radio v zivo; True = obdelano (EOS in napako obravnavamo kot prekinitev povezave)."""
        vrste = self.gst.MessageType
        tip = sporocilo.type
        if tip == getattr(vrste, "BUFFERING", object()):
            self._medpomnjenje(int(sporocilo.parse_buffering()))
            return True
        if tip == getattr(vrste, "QOS", object()):
            izvor = getattr(sporocilo, "src", None)
            if izvor is not None and izvor.find_property("buffer-time") is not None:
                self.statistika["podtoki"] += 1
                if self.statistika["podtoki"] in (1, 10, 100) or self.statistika["podtoki"] % 1000 == 0:
                    self._dnevnik("podtok zvocnega izhoda (skupaj %d)" % self.statistika["podtoki"])
            return True
        if tip == vrste.ERROR:
            napaka, razhroscevanje = sporocilo.parse_error()
            self._dnevnik("napaka toka:", napaka, razhroscevanje or "")
            koda = vrsta_napake(napaka, self.trenutna.uri if self.trenutna else "")
            if koda in TRAJNE_NAPAKE:
                # Manjka kodek ali je tok zascite: ponovna povezava tega ne popravi (pregled 18. 10. 2026).
                self._dnevnik("trajna napaka %s, brez ponovnih poskusov" % koda)
                self._tiho_naprej(koda)          # _zivo_konec: odlozene povezave ne veljajo, statistika v dnevnik
                return True
            self._prekinjeno(koda)
            return True
        if tip == vrste.EOS:
            self._dnevnik("streznik je zaprl tok (EOS)")
            self._prekinjeno("tok")
            return True
        if tip == vrste.ASYNC_DONE and self._povezan_od is None and not self._polni and self._tece():
            self._povezan_od = self._ura()
        return False

    def _medpomnjenje(self, odstotek: int) -> None:
        """Pod 100 %: premor, dokler queue2 ni spet poln (zvok ne zastaja, ampak pocaka); nato nadaljevanje."""
        if odstotek < 100:
            if self._polni:
                return
            self._polni, self._polni_od = True, self._ura()
            self._polnjenje += 1
            if self._predvajal:
                self.statistika["medpomnjenja"] += 1
                self._dnevnik("medpomnjenje %d %% (dogodek %d)" % (odstotek, self.statistika["medpomnjenja"]))
            if self._tece():
                self.element.set_state(self.gst.State.PAUSED)
            rod, polnjenje = self._rod, self._polnjenje
            self._cez_klic(ZIVO_ZASTOJ_MEJA_S, lambda: self._cuvaj_zastoja(rod, polnjenje))
            return
        if self._hitro_nadaljuj:
            # Prvo polnjenje po nadaljevanju je koncano: naslednji zastoj se polni do obicajne zaloge.
            self._hitro_nadaljuj = False
            self._lastnost(getattr(self, "_vrsta2", None), "high-watermark", ZIVO_ZACETNA_ZALOGA)
        if self._polni:
            self._polni = False
            if self._predvajal:
                trajanje = max(0.0, self._ura() - self._polni_od)
                self._zaostanek += trajanje
                self.statistika["zastoj_s"] += trajanje
                if self._zaostanek > ZIVO_ZAOSTANEK_MEJA_S and self._tece():
                    self._skok_na_zivo("zaostanek %.1f s" % self._zaostanek)
                    return
        if self._tece():
            self.element.set_state(self.gst.State.PLAYING)
            if self._povezan_od is None:
                self._povezan_od = self._ura()
            self._predvajal = True

    def _cuvaj_zastoja(self, rod: int, polnjenje: int) -> None:
        if rod == self._rod and self._zivo and self._polni and polnjenje == self._polnjenje and self._tece():
            self._dnevnik("medpomnjenje traja vec kot %d s" % ZIVO_ZASTOJ_MEJA_S)
            self._prekinjeno("tok")

    def _skok_na_zivo(self, razlog: str) -> None:
        self.statistika["skoki_na_zivo"] += 1
        self._dnevnik("skok na zivi rob (%s)" % razlog)
        self._povezi_znova()

    def _prekinjeno(self, koda: str) -> None:
        """ERROR/EOS radia: tiho znova povezemo (1, 2, 4, 8, 8 s); potem tiho naslednja postaja v vrsti ali ustavitev
        (lastnik 18. 10. 2026: napak predvajalnika uporabniku ne kazemo, sled je v sled.log)."""
        self.element.set_state(self.gst.State.NULL)
        if self._povezan_od is not None and self._ura() - self._povezan_od >= ZIVO_STABILNO_S:
            self._poskus = 0
        poskus = self._poskus
        if poskus >= len(ZIVO_ODMIKI_S):
            self._dnevnik("povezave ni bilo mogoce obnoviti po %d poskusih" % poskus)
            self._tiho_naprej("povezava" if koda == "tok" else koda)
            return
        self._poskus = poskus + 1
        odmik = ZIVO_ODMIKI_S[poskus]
        self._dnevnik("ponovna povezava cez %d s (poskus %d/%d)" % (odmik, poskus + 1, len(ZIVO_ODMIKI_S)))
        self._rod += 1
        rod = self._rod
        self._zivo_ponastavi()
        if self.stanje == "premor" and not self._tihi_premor:
            self._znova_ob_nadaljevanju = True
            return
        self._cakam_povezavo = True
        self._cez_klic(odmik, lambda: rod == self._rod and self._povezi_znova())

    def _povezi_znova(self, hitro: bool = False) -> bool:
        """Isti naslov od zacetka: nova povezava je vedno na zivem robu. Stanje za uporabnika ostane "predvaja"."""
        s = self.trenutna
        if s is None or not self._zivo:
            return False
        self._rod += 1
        self.statistika["ponovne_povezave"] += 1
        self.element.set_state(self.gst.State.NULL)
        self._zivo_ponastavi()
        self._hitro_nadaljuj = hitro       # uporabnik caka na zvok: zacne ze pri ZIVO_NADALJUJ_ZALOGA
        self.element.set_property("uri", s.uri)
        self._utisaj(self._tihi_premor)    # ponovna povezava med tihim premorom ostane utisana
        if self.element.set_state(self.gst.State.PLAYING) == self.gst.StateChangeReturn.FAILURE:
            self._prekinjeno("tok")
            return False
        if not self._tihi_premor:
            self.stanje = "predvaja"
        self.napaka = ""
        return True

    def _utisaj(self, da: bool) -> None:
        try:
            self.element.set_property("mute", bool(da))
        except Exception:  # noqa: BLE001 - playbin brez lastnosti: premor brez utisanja je se vedno premor
            pass

    def _tece(self) -> bool:
        """Tok radia tece: predvaja ali je v tihem premoru (utisan, na zivem robu)."""
        return self.stanje == "predvaja" or (self.stanje == "premor" and self._tihi_premor)

    def _zivo_premor(self) -> None:
        """Premor radia (ZIVO_PREMOR_TOPLO_S): takoj utisa, tok tece naprej; nadaljevanje utisanje odstrani. Po
        ZIVO_PREMOR_TOPLO_S ali prekinjeni povezavi se nadaljevanje poveze znova - vedno na zivi rob, nikoli stara zaloga."""
        if self.stanje == "predvaja":
            self._utisaj(True)
            self.stanje, self._premor_od, self._tihi_premor = "premor", self._ura(), True
            rod = self._rod
            self._cez_klic(ZIVO_PREMOR_TOPLO_S, lambda: self._sprosti_premor(rod))
            self.sprememba()
            return
        if self.stanje != "premor":
            return
        tihi, self._tihi_premor = self._tihi_premor, False
        self.stanje = "predvaja"
        if tihi and not self._znova_ob_nadaljevanju and not self._cakam_povezavo:
            self._utisaj(False)              # tok je ves cas tekel: takoj zivi program
            if not self._polni:
                self.element.set_state(self.gst.State.PLAYING)
        else:
            self._dnevnik("nadaljevanje po sproscenem premoru: nova povezava na zivi rob")
            self._povezi_znova(hitro=True)
        self.sprememba()

    def _sprosti_premor(self, rod: int) -> None:
        """Tihi premor traja ZIVO_PREMOR_TOPLO_S: povezavo sprostimo, nadaljevanje se poveze znova."""
        if rod != self._rod or self.stanje != "premor" or not self._tihi_premor:
            return
        self._dnevnik("premor dalj kot %d s: povezava sproscena" % ZIVO_PREMOR_TOPLO_S)
        self._rod += 1                       # odlozene ponovne povezave ne veljajo vec
        self._tihi_premor = False
        self.element.set_state(self.gst.State.NULL)
        self._zivo_ponastavi()
        self._znova_ob_nadaljevanju = True

    def _izpisi_statistiko(self) -> None:
        st = self.statistika
        self._dnevnik("statistika: medpomnjenja=%d podtoki=%d ponovne_povezave=%d skoki_na_zivo=%d zastoj=%.1f s" % (
            st["medpomnjenja"], st["podtoki"], st["ponovne_povezave"], st["skoki_na_zivo"], st["zastoj_s"]))

    def _zivo_konec(self) -> None:
        """Uporabnik je ustavil ali zamenjal skladbo: odlozene povezave ne veljajo vec, statistika v dnevnik."""
        self._rod += 1
        self._poskus = 0
        self._tihi_premor = self._hitro_nadaljuj = False
        if self._zivo:
            self._izpisi_statistiko()
        self._zivo_ponastavi()
