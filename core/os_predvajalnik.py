"""En predvajalni servis in čakalna vrsta za neposredne medije Safeer OS.

GStreamer se naloži šele ob prvem predvajanju, zato sam zagon OS ne zahteva
predvajalnih vtičnikov. Vmesnik in baza knjižnice lahko uporabljata isto sejo.
"""

from __future__ import annotations

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


#: Kode napak predvajanja; stran jih prevede (mediaNapaka_<koda>), okno predvajalnika uporabi NAPAKE.
NAPAKE = {
    "tok": "Tok ni dosegljiv. Preveri naslov in povezavo.",
    "datoteka": "Datoteke ni mogoče prebrati.",
    "format": "Tega zapisa ni mogoče predvajati (manjka kodek ali datoteka ni medij).",
    "zascita": "Posnetek je zaščiten (DRM) in ga Safeer ne predvaja.",
    "dvd": "Diska ni mogoče prebrati. Zaščitenih diskov (CSS) Safeer ne odklepa.",
    "zacetek": "Predvajanja ni bilo mogoče začeti.",
    "splosno": "Predvajanje se je ustavilo zaradi napake.",
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
        #: {"zvok_jezik", "izenacevalnik", "po_meri"} - shrani jih klicatelj (shrani_moznosti).
        self.moznosti = _moznosti.privzete()
        self.shrani_moznosti = lambda _n: None
        self._samodejni_zvok = False
        self._obnovi_zvok = -1        # izbrani zvocni tok po ponovnem nalaganju (zamenjava podnapisov)
        self.izenacevalnik = None     # element equalizer-10bands; None = izenacevalnika ni (meni ga ne pokaze)
        self._predojacitev = None
        self.element = gst.ElementFactory.make("playbin", "safeer-media")
        if self.element is None:
            raise RuntimeError("GStreamer playbin ni na voljo")
        self._pripravi_izenacevalnik()
        self.vodilo = self.element.get_bus()
        self.vodilo.add_signal_watch()
        self.vodilo.connect("message", self._sporocilo)
        #: Poskusi trenutnega posnetka: [(uri, glave), ...] - prvi je izbrani tok, ostali njegove razlicice.
        self._poskusi: list = []
        self._poskus = 0
        self._glave: tuple = ()
        self._nalozeno = False
        #: Klic, ko se posnetek ne odpre z nobeno razlicico (Medijski center ga oznaci kot nepredvajljivega).
        self.neuspeh = lambda _skladba: None
        #: (ms, f): zakasnjen klic v glavni niti (safeer_os: GLib.timeout_add); privzeto takoj.
        self.zakasni = lambda _ms, f: f()
        povezi = getattr(self.element, "connect", None)
        if povezi is not None:
            # Glave toka (Referer ...) za souphttpsrc: playbin ustvari vir sele ob odpiranju.
            povezi("source-setup", self._nastavi_vir)

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
        self._poskus, self._glave, self._nalozeno = 0, tuple(s.glave or ()), False
        self._dekoder, self._stari_dekoderji = "", set()
        self.element.set_property("uri", s.uri)
        self._pripravi_podnapise(self.vrsta[indeks])
        # Zamik velja za en posnetek (kot v VLC); jezik zvoka izberemo, ko playbin pozna tokove (ASYNC_DONE).
        self.nastavi_zamik("zvok", 0)
        self.nastavi_zamik("podnapisi", 0)
        self._samodejni_zvok, self._obnovi_zvok = True, -1
        rezultat = self.element.set_state(self.gst.State.PLAYING)
        self.stanje = "napaka" if rezultat == self.gst.StateChangeReturn.FAILURE else "predvaja"
        if self.stanje == "napaka":
            self.napaka = "zacetek"
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
            lastnost, vrednost = "av-offset", _moznosti.av_offset_ns(self.zamik_zvoka)
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
                "podnapisi": bool(self.trenutna and (self.trenutna.podnapisi or self._stevilo_besedil()))}

    def _stevilo_besedil(self) -> int:
        try:
            return int(self.element.get_property("n-text"))
        except Exception:
            return 0

    def naslednja(self) -> bool:
        return self.predvajaj(self.indeks + 1)

    def prejsnja(self) -> bool:
        return self.predvajaj(self.indeks - 1)

    def ustavi(self) -> None:
        self._cakaj_zacetek = 0
        self.element.set_state(self.gst.State.NULL)
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
        if self._nalozeno or self._poskus + 1 >= len(self._poskusi):
            return False
        neuspel = urlsplit(self._poskusi[self._poskus][0]).hostname
        ostali = self._poskusi[self._poskus + 1:]
        if status in (401, 403, 429):
            drugi = [p for p in ostali if urlsplit(p[0]).hostname != neuspel]
            isti = [p for p in ostali if urlsplit(p[0]).hostname == neuspel]
            ostali = drugi + isti
        self._poskusi[self._poskus + 1:] = ostali
        self._poskus += 1
        if self._dekoder:
            # Neuspeli vir poslje se kaksno napako (»streaming stopped«): ta ne velja za naslednjo razlicico.
            self._stari_dekoderji.add(self._dekoder)
        uri, glave = self._poskusi[self._poskus]
        indeks = self.indeks
        print("[SafeerOS] predvajanje: tok %d/%d ni odprt (%s), poskusim naslednjo razlicico" % (
            self._poskus, len(self._poskusi), status or "napaka"), flush=True)

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
        self.napaka = koda
        self.element.set_state(self.gst.State.NULL)
        self.stanje = "napaka"
        # Samo tok, ki ga noben streznik ni dal (ne manjkajoci kodek na tem racunalniku): naslov ni predvajljiv.
        if koda == "tok" and not self._nalozeno and self.trenutna is not None:
            try:
                self.neuspeh(self.trenutna)
            except Exception:  # noqa: BLE001
                pass
        self.sprememba()

    def _sporocilo(self, _vodilo, sporocilo) -> None:
        if sporocilo.type == self.gst.MessageType.EOS:
            if self.trenutna:
                self.konec(self.trenutna.uri)
            if not self.naslednja():
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
            # Uporabnik vidi razumljivo, prevedeno sporočilo (koda); surovo napako GStreamerja damo v dnevnik.
            # Podpisani naslovi toka (sign=..., token ...) ne gredo v dnevnik: samo gostitelj.
            print("[SafeerOS] predvajanje:", napaka, re.sub(r"\?\S*", "?…", str(razhroscevanje or "")), flush=True)
            uri = self._poskusi[self._poskus][0] if self._poskus < len(self._poskusi) else (self.trenutna.uri if self.trenutna else "")
            koda = vrsta_napake(napaka, uri)
            # Tok z mrezo, ki se ni odprl: streznik ga ne da (tok) ali je namesto posnetka poslal stran HTML oziroma zapis,
            # ki ga ta racunalnik ne zna (format) - druga razlicica je morda v redu.
            if (koda == "tok" or (koda == "format" and uri.startswith(("http://", "https://")))) \
                    and self._naslednji_poskus(status_napake(razhroscevanje)):
                return
            self._koncna_napaka(koda)
