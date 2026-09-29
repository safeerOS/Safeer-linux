"""En predvajalni servis in čakalna vrsta za neposredne medije Safeer OS.

GStreamer se naloži šele ob prvem predvajanju, zato sam zagon OS ne zahteva
predvajalnih vtičnikov. Vmesnik in baza knjižnice lahko uporabljata isto sejo.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Skladba:
    uri: str
    naslov: str
    vrsta: str = "medij"
    zacetek: int = 0


#: Kode napak predvajanja; stran jih prevede (mediaNapaka_<koda>), okno predvajalnika uporabi NAPAKE.
NAPAKE = {
    "tok": "Tok ni dosegljiv. Preveri naslov in povezavo.",
    "datoteka": "Datoteke ni mogoče prebrati.",
    "format": "Tega zapisa ni mogoče predvajati (manjka kodek ali datoteka ni medij).",
    "zascita": "Posnetek je zaščiten (DRM) in ga Safeer ne predvaja.",
    "zacetek": "Predvajanja ni bilo mogoče začeti.",
    "splosno": "Predvajanje se je ustavilo zaradi napake.",
}


def vrsta_napake(napaka, uri: str = "") -> str:
    """GLib.Error iz GStreamerja -> ena od kod v NAPAKE."""
    domena, koda = str(getattr(napaka, "domain", "") or ""), int(getattr(napaka, "code", 0) or 0)
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
    if razcep.scheme == "file":
        from urllib.request import url2pathname
        pot = Path(url2pathname(razcep.path))
        if pot.is_file():
            return Skladba(pot.resolve().as_uri(), pot.name, vrsta)
    raise ValueError("Medij mora biti spletni tok ali obstoječa lokalna datoteka")


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
        self.element = gst.ElementFactory.make("playbin", "safeer-media")
        if self.element is None:
            raise RuntimeError("GStreamer playbin ni na voljo")
        self.vodilo = self.element.get_bus()
        self.vodilo.add_signal_watch()
        self.vodilo.connect("message", self._sporocilo)

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
                             zacetek=max(0, int(v.zacetek))) for v in vnosi]
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
        self.element.set_property("uri", self.vrsta[indeks].uri)
        rezultat = self.element.set_state(self.gst.State.PLAYING)
        self.stanje = "napaka" if rezultat == self.gst.StateChangeReturn.FAILURE else "predvaja"
        if self.stanje == "napaka":
            self.napaka = "zacetek"
        self.sprememba()
        return self.stanje == "predvaja"

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
                "zacetniIndeks": zacetek,
                "skupaj": len(self.vrsta),
                "vrstaSeznam": [{"naslov": v.naslov, "vrsta": v.vrsta} for v in self.vrsta[zacetek:zacetek + 18]],
                "pozicija": pozicija, "trajanje": dolzina, "napaka": self.napaka}

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

    def _sporocilo(self, _vodilo, sporocilo) -> None:
        if sporocilo.type == self.gst.MessageType.EOS:
            if self.trenutna:
                self.konec(self.trenutna.uri)
            if not self.naslednja():
                self.ustavi()
        elif sporocilo.type == self.gst.MessageType.ASYNC_DONE:
            self.poskusi_nadaljevati()
        elif sporocilo.type == self.gst.MessageType.ERROR:
            napaka, razhroscevanje = sporocilo.parse_error()
            # Uporabnik vidi razumljivo, prevedeno sporočilo (koda); surovo napako GStreamerja damo v dnevnik.
            print("[SafeerOS] predvajanje:", napaka, razhroscevanje or "", flush=True)
            self.napaka = vrsta_napake(napaka, self.trenutna.uri if self.trenutna else "")
            self.element.set_state(self.gst.State.NULL)
            self.stanje = "napaka"
            self.sprememba()
