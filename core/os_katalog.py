"""Katalog Medijskega centra na Linuxu: filmi, serije, glasba, radio, TV v zivo, seznami predvajanja in dodatki.

Jedro je isto kot v Safeer OS za Windows (core/os_media.py in moduli ob njem - katalog, zdruzevanje dvojnikov, izbira
toka, preverjanje, kaj se da predvajati, seznami predvajanja). Tu je samo most do Safeer OS za Linux:

- metode mostu `media*` imajo ista imena in iste odgovore kot na Windows (assets/os/os.js jih klice enako),
- predvajanje gre v domaci predvajalnik (GStreamer, core/os_predvajalnik.py): neposredni tokovi in datoteke; vdelani
  predvajalniki in spletne strani v lahki medijski pogled; skladbe s seznama predvajanja (YouTube) v vgradnem
  predvajalniku YouTuba v istem lahkem pogledu (locen spletni proces brez mostu Safeer OS - v stran Safeer OS tuje
  vsebine nikoli ne vgradimo, ker so njeni klici mostu dosegljivi vsem okvirjem strani),
- gesla osebnih streznikov hrani sistemska zbirka skrivnosti (libsecret); v media.json je samo oznaka.

Modul ne uvaza Gtk: vse, kar potrebuje okno, dobi kot funkcije (glej Katalog.__init__), zato ga preizkusi poganjajo
brez zaslona.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import secrets
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Optional

from . import jellyfin_vticniki, knjiznica_kroga, media_servers, os_media, os_police, samodejni_seznami, zakoniti_viri

#: Posnetek YouTube: natanko 11 znakov iz te abecede.
YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
ZVOK = ("glasba", "radio", "podcast", "podkast")
SHEMA_SKRIVNOSTI = "io.github.memelandfaner.SafeerOS.Media"
NAJVEC_NAPREDKOV = 200


# ---------------------------------------------------------------------------------------------- gesla streznikov

def _zbirka():
    """libsecret prek GObject Introspection; None, ce ga ni (takrat streznikov z geslom ni mogoce dodati)."""
    try:
        import gi
        gi.require_version("Secret", "1")
        from gi.repository import Secret
        shema = Secret.Schema.new(SHEMA_SKRIVNOSTI, Secret.SchemaFlags.NONE, {"id": Secret.SchemaAttributeType.STRING})
        return Secret, shema
    except Exception:  # noqa: BLE001 - brez libsecret (minimalno namizje, preizkusi)
        return None


def skrij(skrivnost: str) -> str:
    """Geslo ali zeton shrani v zbirko skrivnosti in vrne oznako zanj. Prazno ostane prazno (dodatki nimajo gesla)."""
    if not skrivnost:
        return ""
    z = _zbirka()
    if z is None:
        raise RuntimeError("Zbirka skrivnosti ni na voljo.")
    Secret, shema = z
    oznaka = secrets.token_hex(12)
    if not Secret.password_store_sync(shema, {"id": oznaka}, Secret.COLLECTION_DEFAULT, "Safeer OS – medijski strežnik",
                                      skrivnost, None):
        raise RuntimeError("Gesla ni bilo mogoče shraniti.")
    return "zbirka:" + oznaka


def razkrij(vrednost: str) -> str:
    if not vrednost:
        return ""
    if not vrednost.startswith("zbirka:"):
        raise RuntimeError("Zaščitene poverilnice niso dostopne v tej napravi.")
    z = _zbirka()
    if z is None:
        raise RuntimeError("Zbirka skrivnosti ni na voljo.")
    Secret, shema = z
    geslo = Secret.password_lookup_sync(shema, {"id": vrednost[len("zbirka:"):]}, None)
    if geslo is None:
        raise RuntimeError("Gesla ni v zbirki skrivnosti.")
    return geslo


def pozabi(vrednost: str) -> None:
    if not str(vrednost or "").startswith("zbirka:"):
        return
    z = _zbirka()
    if z is not None:
        try:
            z[0].password_clear_sync(z[1], {"id": vrednost[len("zbirka:"):]}, None)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------------------------- pravila (cista)

def nacin_predvajanja(item: dict, neposredni_zvok: Callable[[str], bool] = lambda _u: False) -> str:
    """Kako Linux predvaja razresen vnos kataloga:

    - "youtube":   skladba s seznama predvajanja - vgradni predvajalnik YouTuba v lahkem medijskem pogledu,
    - "neposredno": tok ali datoteka - domaci predvajalnik (GStreamer),
    - "vdelano":   vdelan predvajalnik ali spletna stran - lahki medijski pogled,
    - "":          nicesar ni mogoce predvajati (naslov ni http(s), datoteka ali DVD).
    """
    url = str(item.get("url") or "")
    if item.get("youtube") and str(item.get("id") or "").startswith("seznam:"):
        return "youtube" if YOUTUBE_ID.match(str(item.get("youtube"))) else ""
    if url.startswith("file:") or item.get("pot"):
        return "neposredno"
    if not url.startswith(("http://", "https://")):
        return ""
    nizko = url.lower()
    vdelano = (item.get("vrsta") == "embed" or "/embed/" in nizko
               or any(x in nizko for x in ("youtube", "vimeo", "dailymotion", "peertube")))
    pot = urllib.parse.urlsplit(url).path.lower()
    neposredno = (os.path.splitext(pot)[1] in os_media.MEDIA_EXT or pot.endswith((".m3u8", ".mpd", ".ts"))
                  or bool(item.get("glave")))
    if vdelano and not neposredno:
        return "vdelano"
    if neposredno:
        return "neposredno"
    # Zvocni tok brez koncnice (Jamendo, Icecast): streznik potrdi zvok - sicer je to spletna stran.
    if str(item.get("vrsta") or "") in ZVOK and neposredni_zvok(url):
        return "neposredno"
    return "vdelano"


def vrsta_predvajalnika(item: dict) -> str:
    """Vrsta za domaci predvajalnik: radio in TV sta prenos v zivo (brez premikanja), zvok ne odpre okna."""
    vrsta = str(item.get("vrsta") or "")
    if vrsta == "radio":
        return "radio"
    if vrsta == "tv-v-zivo":
        return "tv"
    return "medij" if vrsta in ZVOK else "video"


def naslov_za_predvajalnik(item: dict) -> str:
    naslov = str(item.get("naslov") or "").strip()
    if item.get("vrsta") == "serija" and (item.get("sezona") or item.get("epizoda")):
        naslov += " · S%02dE%02d" % (int(item.get("sezona") or 1), int(item.get("epizoda") or 1))
    izvajalec = str(item.get("izvajalec") or "").strip()
    if izvajalec and str(item.get("vrsta") or "") in ("glasba", "podcast", "podkast") and izvajalec.lower() not in naslov.lower():
        naslov = izvajalec + " – " + naslov
    return naslov[:80] or "Safeer"


def tok_za_predvajalnik(item: dict, url: str) -> dict:
    """Glave, ki jih zahteva izbrani tok (dodatek jih poda ob toku - brez njih streznik vrne npr. 429), in druge
    razlicice istega naslova, ki jih predvajalnik tiho poskusi, ce se izbrani tok ne odpre. Prazno = nic od tega."""
    razlicice = [r for r in (item.get("razlicice") or []) if isinstance(r, dict)]
    izbrana = next((r for r in razlicice if str(r.get("url") or "") == url), None)
    glave = (izbrana or {}).get("glave") or item.get("glave") or {}
    # Samo tokovi (datoteka, HLS, tok dodatka z glavami) - spletna stran z vdelanim predvajalnikom ni razlicica toka.
    nadomestni = [(str(r["url"]), r.get("glave") or {}) for r in razlicice
                  if str(r.get("url") or "").startswith(("http://", "https://")) and str(r.get("url")) != url
                  and (r.get("tok") or nacin_predvajanja({"url": r["url"], "glave": r.get("glave")}) == "neposredno")][:10]
    tok = {}
    if isinstance(glave, dict) and glave:
        tok["glave"] = dict(glave)
    if nadomestni:
        tok["nadomestni"] = nadomestni
    return tok


def podnapisi_vnosa(item: dict) -> tuple:
    """Podnapisi iz dodatka -> ((uri, ime, jezik, oznaka), ...) za os_predvajalnik.Skladba."""
    izhod = []
    for p in (item.get("podnapisi") or [])[:24]:
        if not isinstance(p, dict):
            continue
        url = str(p.get("uri") or p.get("url") or "")
        if not url.startswith(("https://", "http://127.0.0.1:", "file://")):
            continue
        jezik = str(p.get("jezik") or p.get("lang") or "")[:12]
        izhod.append((url, str(p.get("ime") or p.get("oznaka") or jezik or "Podnapisi")[:80], jezik, str(p.get("oznaka") or "")[:40]))
    return tuple(izhod)


#: Izvor, s katerim se Safeer predstavi vgradnemu predvajalniku YouTuba (isti kot v Safeer OS za Windows). Brez
#: veljavnega izvora YouTube vgradnje ne dovoli (napaka 153), izvor 127.0.0.1 pa zavrne pri glasbi (napaka 150).
IZVOR_VGRADNJE = "https://safeer.si/"
PREDPONA_VGRADNJE = "https://www.youtube.com/embed/"
#: Uporabniski skript se vstavi samo na strani vgradnega predvajalnika.
STRANI_SKRIPTA_SKLADBE = ("https://www.youtube.com/embed/*",)


def naslov_vgradnje(posnetek: str) -> str:
    """Naslov vgradnega predvajalnika za posnetek ali "" (neveljaven ID)."""
    posnetek = str(posnetek or "")
    if not YOUTUBE_ID.match(posnetek):
        return ""
    return PREDPONA_VGRADNJE + posnetek + "?autoplay=1&rel=0&playsinline=1"


def je_naslov_vgradnje(naslov: str) -> bool:
    naslov = str(naslov or "")
    if not naslov.startswith(PREDPONA_VGRADNJE):
        return False
    return bool(YOUTUBE_ID.match(naslov[len(PREDPONA_VGRADNJE):].split("?", 1)[0]))


#: Skript v lahkem medijskem pogledu: stanje predvajalnika (1 igra, 2 premor, 0 konec) in napako javi Safeer OS,
#: da ta ob koncu skladbe zacne naslednjo; od Safeer OS sprejme samo »predvajaj« in »premor«.
SKRIPT_SKLADBE = """
(function () {
  if (window.__safeerSkladba) return; window.__safeerSkladba = true;
  function javi(o) { try { window.webkit.messageHandlers.safeerSkladba.postMessage(JSON.stringify(o)); } catch (e) {} }
  function predvajalnik() { var p = document.getElementById("movie_player"); return p && typeof p.getPlayerState === "function" ? p : null; }
  var zadnje = null, napaka = false, napakaVidea = 0, zacetek = Date.now();
  function stanje() {
    var p = predvajalnik();
    if (p) { try { return p.getPlayerState(); } catch (e) {} }
    var v = document.querySelector("video");
    if (!v) return null;
    if (v.ended) return 0;
    return v.paused ? (v.currentTime > 0 ? 2 : -1) : (v.readyState > 2 ? 1 : 3);
  }
  function javiNapako(koda) { if (napaka) return; napaka = true; javi({ napaka: true, koda: String(koda).slice(0, 12) }); }
  document.addEventListener("error", function (e) {
    if (e.target && e.target.tagName === "VIDEO") napakaVidea = Date.now();
  }, true);
  setInterval(function () {
    if (napaka) return;
    var s = stanje();
    if (s === 1) napakaVidea = 0;
    if ((s === 0 || s === 1 || s === 2) && s !== zadnje) { zadnje = s; javi({ stanje: s }); }
    var e = document.querySelector(".ytp-error");
    if (e && e.offsetParent !== null) { javiNapako("vgradnja"); return; }
    // Posnetek se ne da dekodirati in predvajalnik si v nekaj sekundah ni opomogel.
    if (napakaVidea && zadnje !== 1 && Date.now() - napakaVidea > 6000) javiNapako("dekodiranje");
  }, 400);
  window.safeerUkaz = function (f) {
    if (f !== "playVideo" && f !== "pauseVideo") return;
    var p = predvajalnik();
    try {
      if (p && typeof p[f] === "function") { p[f](); return; }
      var v = document.querySelector("video");
      if (v) { if (f === "playVideo") v.play(); else v.pause(); }
    } catch (e) {}
  };
})();
"""


class Katalog:
    """Most med stranjo Safeer OS (metode media*) in jedrom kataloga.

    Funkcije okna (vse klicane v glavni niti prek `v_glavni`):
      predvajaj(uri, vrsta, ime, zacetek, podnapisi, prikazi) -> bool   domaci predvajalnik
      vdelano(url) -> bool                                             lahki medijski pogled
      youtube(naslov_vgradnje, ime) -> bool                            skladba v lahkem pogledu (vgradni predvajalnik)
      youtube_ukaz("playVideo" | "pauseVideo" | "zapri") -> bool        premor, nadaljuj, zapri pogled
    """

    def __init__(self, config_dir: str, dogodek: Callable[[str, Any], None], v_glavni: Callable[[Callable[[], Any]], Any],
                 predvajaj: Callable[..., bool], vdelano: Callable[[str], bool], youtube: Callable[[str, str], bool],
                 youtube_ukaz: Callable[[str], bool],
                 jezik: Callable[[], str] = lambda: "sl", visina_zaslona: int = 1080,
                 uskladi_sezname: Optional[Callable[[Callable], bool]] = None,
                 knjiznica: Optional[knjiznica_kroga.Knjiznica] = None, lokalna: Any = None) -> None:
        self.config_dir = Path(config_dir)
        self.dogodek = dogodek
        self.v_glavni = v_glavni
        self._predvajaj = predvajaj
        self._vdelano = vdelano
        self._youtube = youtube
        self._youtube_ukaz = youtube_ukaz
        #: Skladba, ki igra v vgradnem predvajalniku YouTuba: {"id", "igra", "ze_igral"} ali None.
        self._yt: Optional[dict] = None
        self.jezik = jezik
        self.visina_zaslona = int(visina_zaslona or 1080)
        self._uskladi_sezname = uskladi_sezname
        #: Polica »Na tvojih napravah« (core/knjiznica_kroga.py); None = brez Linka (preizkusi).
        self._knjiznica = knjiznica
        self._mc: Optional[os_media.MediaCenter] = None
        self._zaklep = threading.Lock()
        #: uri, ki ga igra domaci predvajalnik -> vnos kataloga (za napredek in "naslednja ob koncu").
        self._predvajano: dict[str, dict] = {}
        self._seznami_usklajeni = 0.0
        self._seznami_usklajujem = False
        self._motor_odstotek = -1
        #: Osebne police (core/os_police.py): priljubljene, stevci, ogledano - v isti mapi kot napredek.json.
        self.police = os_police.Police(self.config_dir)
        #: Krajevna knjiznica (core/os_knjiznica.py) za police; None = privzeta baza ob prvi rabi.
        self._lokalna = lokalna
        #: Ponujena naslednja epizoda: {"zeton", "cas", "kljuc", "tip", ...} ali None. Zeton porabi prvi pogled, ki
        #: jo zacne ali preklice (Medijski center je lahko odprt v dveh oknih - epizoda se ne sme zaceti dvakrat).
        self._ponudba: Optional[dict] = None
        self._zaklep_ponudbe = threading.Lock()
        #: (tmdb, sezona, epizoda) -> (cas, naslednja epizoda ali None) - glej _naslednja_epizoda_kataloga.
        self._naslednje: dict = {}
        #: Samodejni seznami (core/samodejni_seznami.py): izracunani v ozadju najvec enkrat na 10 minut.
        self._samodejni: dict = {"cas": 0.0, "seznami": [], "racunam": False}

    # ------------------------------------------------------------------ jedro
    @property
    def mc(self) -> os_media.MediaCenter:
        with self._zaklep:
            if self._mc is None:
                # Krajevne datoteke ima na Linuxu knjiznica Medijskega centra (core/os_knjiznica.py), zato tu brez map.
                self._mc = os_media.MediaCenter(str(self.config_dir), roots=[], secret_encryptor=skrij, secret_decryptor=razkrij)
                self._mc.visina_zaslona = self.visina_zaslona
                # Pred predvajanjem preverimo, da prvi tok res odgovori (mrtva povezava ne sme biti prva).
                self._mc.preveri_tokove = True
                # Iskanje in katalog: vsak vir najvec 2,5 s, pocasnejsi se doda z dogodkom mediaKatalogOsvezen (meritev
                # 15. 10. 2026: hitri dodatki 0,2-1,6 s, javni viri 1,2-3,4 s, pocasni dodatki 10-20 s).
                self._mc.rok_vira = 2.5
                # Film iz torrenta: branje torrenta traja - stran med tem pove, da ga pripravljamo.
                self._mc.ob_pripravi_torrenta = lambda item: self.dogodek(
                    "mediaTorrent", {"naslov": str(item.get("naslov") or "")})
                # Prvi film iz torrenta: enkratni prenos predvajalnega programa je viden in ga je mogoce preklicati.
                self._mc.preklic_motorja = threading.Event()
                self._mc.ob_prenosu_motorja = self._motor_napredek
                # Moji viri z drugih naprav v Linku (core/viri_sink.py): stran osvezi vire in katalog.
                self._mc.ob_virih = lambda: self.dogodek("mediaViriUsklajeni", None)
            return self._mc

    def _motor_napredek(self, preneseno: int, vse: int) -> None:
        odstotek = int(100 * preneseno / (vse or 1))
        if odstotek != self._motor_odstotek:          # stran dobi dogodek po odstotkih, ne po kosih
            self._motor_odstotek = odstotek
            self.dogodek("mediaMotor", {"n": int(preneseno), "vse": int(vse)})

    def _motor_preklici(self, a: list) -> bool:
        preklic = getattr(self.mc, "preklic_motorja", None)
        if preklic is not None:
            preklic.set()
        return True

    def _drzava(self) -> str:
        return str(self._nastavitve().get("media_watch_country") or "auto")

    def _nastavitve(self) -> dict:
        try:
            d = json.loads((self.config_dir / "nastavitve.json").read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    #: Branje-sprememba-zapis nastavitve.json iz delovnih niti (drzava, skriti meni): brez zaklepa bi hkratni spremembi
    #: druga drugo povozili (pregled 14. 10. 2026).
    _zaklep_nastavitev = threading.Lock()

    def _spremeni_nastavitve(self, sprememba: Callable[[dict], None]) -> None:
        with self._zaklep_nastavitev:
            d = self._nastavitve()
            sprememba(d)
            self._shrani_nastavitve(d)

    def _shrani_nastavitve(self, d: dict) -> None:
        """Atomaren zapis (zacasna datoteka v isti mapi + os.replace): izpad med pisanjem ne pusti pol datoteke."""
        zacasna = self.config_dir / (".nastavitve.json.%d.%d.tmp" % (os.getpid(), threading.get_ident()))
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            zacasna.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            os.replace(zacasna, self.config_dir / "nastavitve.json")
        except OSError:
            try:
                zacasna.unlink()
            except OSError:
                pass

    # ------------------------------------------------------------------ most
    def pozna(self, metoda: str) -> bool:
        return metoda in self.METODE

    def izvedi(self, metoda: str, a: list) -> Any:
        """Izvede metodo mostu (v delovni niti - katalog bere omrezje). Neznana metoda: KeyError."""
        return getattr(self, self.METODE[metoda])(a)

    METODE = {
        "mediaZvrsti": "_zvrsti", "mediaRadioDrzave": "_radio_drzave", "mediaKatalog": "_katalog", "mediaPredgrej": "_predgrej", "mediaIsciPredpomnilnik": "_isci_predpomnilnik",
        "mediaPodrobnosti": "_podrobnosti", "mediaWatchSettings": "_watch_settings", "mediaWatchCountry": "_watch_country",
        "mediaSezona": "_sezona", "mediaEpizoda": "_epizoda", "mediaFilm": "_film",
        # Razlicice naslova v podrobnostih (dodatki in strezniki, ki jih je dodal uporabnik): seznam in rocna izbira.
        "mediaRazlicice": "_razlicice", "mediaIzberiRazlicico": "_izberi_razlicico",
        "mediaViri": "_viri", "mediaDodajVir": "_dodaj_vir", "mediaDodajStreznik": "_dodaj_streznik",
        "mediaOdstraniVir": "_odstrani_vir", "mediaOsveziVir": "_osvezi_vir", "mediaOdkrijDlna": "_odkrij_dlna",
        "mediaSeznami": "_seznami", "mediaSeznam": "_seznam", "mediaUvoziSeznam": "_uvozi_seznam",
        "mediaOdstraniSeznam": "_odstrani_seznam", "mediaDodajNaSeznam": "_dodaj_na_seznam",
        "mediaOdstraniSSeznama": "_odstrani_s_seznama", "mediaSeznamZamenjava": "_seznam_zamenjava",
        "mediaPredvajaj": "_predvajaj_vnos", "mediaYtUkaz": "_yt_ukaz", "mediaStanje": "_stanje",
        "mediaKnjiznica": "_knjiznica_seznam", "mediaKnjiznicaPredvajaj": "_knjiznica_predvajaj",
        "mediaKnjiznicaOdstrani": "_knjiznica_odstrani", "mediaKnjiznicaObdrzi": "_knjiznica_obdrzi",
        "mediaMotorPreklici": "_motor_preklici", "mediaTokovi": "_tokovi",
        "mediaPolice": "_police", "mediaPriljubljena": "_priljubljena", "mediaOgledano": "_ogledano",
        "mediaPolicaPredvajaj": "_polica_predvajaj", "mediaPredvajanTok": "_predvajan_tok",
        "mediaNaslednjaPredvajaj": "_naslednja_predvajaj", "mediaNaslednjaPreklici": "_naslednja_preklici",
        "mediaSkrito": "_skrito", "mediaSkrij": "_skrij",
        "mediaSamodejniSeznami": "_samodejni_seznami", "mediaSamodejniSeznam": "_samodejni_seznam",
        "mediaSamodejniShrani": "_samodejni_shrani",
        "mediaJellyfinVticniki": "_jf_vticniki", "mediaJellyfinVticnik": "_jf_vticnik",
        "mediaJellyfinNamesti": "_jf_namesti", "mediaJellyfinZagon": "_jf_zagon",
    }

    @staticmethod
    def _niz(a: list, i: int, privzeto: str = "") -> str:
        return str(a[i]) if len(a) > i and a[i] is not None else privzeto

    def _zvrsti(self, a: list) -> Any:
        vrsta = self._niz(a, 0, "glasba")
        self.mc.izbrana_drzava = self._drzava()
        return self.mc.tv_drzave() if vrsta == "tv-v-zivo" else zakoniti_viri.zvrsti_za(vrsta)

    def _katalog(self, a: list) -> Any:
        mc = self.mc
        mc.izbrana_drzava = self._drzava()
        stran = int(a[3]) if len(a) > 3 and str(a[3]).isdigit() else 1
        izklopljeni = [str(x) for x in a[5]][:200] if len(a) > 5 and isinstance(a[5], list) else []
        izklopljeni_jeziki = [str(x) for x in a[7]][:100] if len(a) > 7 and isinstance(a[7], list) else []

        def prikazi(rezultat):
            # Cesar noben vir ne predvaja, ne kazemo; ostalo iz dodatkov preverimo v ozadju (dogodek mediaNiNaVoljo).
            rezultat = mc.brez_nerazpolozljivih(rezultat)
            if isinstance(rezultat, dict):
                mc.preveri_razpolozljivost(rezultat.get("vnosi"), lambda idji: self.dogodek("mediaNiNaVoljo", {"idji": idji}))
                # Stran pokaze gumbe zvrsti samo, kadar izbira zvrsti katalog res filtrira.
                rezultat = dict(rezultat, zvrsti=mc.zvrsti_filtrirajo(self._niz(a, 1, "vse"), izklopljeni))
            return rezultat

        return prikazi(mc.catalog_hitro(
            self._niz(a, 0), self._niz(a, 1, "vse"), self._niz(a, 2), stran,
            ob_osvezitvi=lambda _kljuc, rezultat: self.dogodek("mediaKatalogOsvezen", prikazi(rezultat)),
            razvrsti=self._niz(a, 4), izklopljeni=izklopljeni, samo_lokalno=False,
            izklopljeni_jeziki=izklopljeni_jeziki,
            # Izbran jezik vsebine (poleg zvrsti); neznana koda v jedru ne velja.
            jezik=self._niz(a, 8)[:8],
            # Izbrana drzava radia (lastnik 15. 10. 2026); jedro sprejme samo kodo ISO s 2 crkama.
            drzava_radia=self._niz(a, 9)[:2]))

    def _radio_drzave(self, _a: list) -> Any:
        """Drzave za izbiro pri radiu: uporabnikova najprej, nato po stevilu postaj. Imena napise stran (Intl)."""
        drzava = (self.mc._drzava_uporabnika() or "").upper()
        try:
            vse = self.mc._zakoniti_viri.radio_drzave()
        except Exception:  # noqa: BLE001 - brez omrezja: izbira ostane samo »Vse drzave«
            vse = []
        return {"uporabnik": drzava, "drzave": sorted(vse, key=lambda d: d.get("id") != drzava)}

    def _predgrej(self, _a: list) -> Any:
        """Ob odprtju Medijskega centra v ozadju pripravi prve strani glavnih zavihkov (Glasba, Filmi, Serije, Radio,
        TV v zivo), da je klik na zavihek takoj (lastnik 14. 10. 2026: cakanje na katalog filmov in serij). Enkrat na
        10 minut; ze sveze poglede predpomnilnik vrne takoj, brez omrezja."""
        zdaj = time.time()
        if zdaj - getattr(self, "_predgreto", 0) < 600:
            return False
        self._predgreto = zdaj
        mc = self.mc
        mc.izbrana_drzava = self._drzava()

        def delo():
            for vrsta in ("film", "serija", "glasba", "radio", "tv-v-zivo"):
                try:
                    mc.catalog_hitro("", vrsta, "", 1)
                except Exception as napaka:  # noqa: BLE001
                    print("[Katalog] predgrevanje %s: %s" % (vrsta, napaka), flush=True)
        threading.Thread(target=delo, name="katalog-predgrej", daemon=True).start()
        return True

    def _isci_predpomnilnik(self, a: list) -> Any:
        return self.mc.isci_v_predpomnilniku(self._niz(a, 0), 8)

    def _podrobnosti(self, a: list) -> Any:
        return self.mc.details(self._niz(a, 0), self._drzava(), self._niz(a, 1, self.jezik()))

    def _watch_settings(self, a: list) -> Any:
        return self.mc.watch_country_settings(self._drzava(), self._niz(a, 0, self.jezik()))

    def _watch_country(self, a: list) -> Any:
        drzava = self._niz(a, 0, "auto").strip().upper()
        if drzava != "AUTO" and not re.fullmatch(r"[A-Z]{2}", drzava):
            raise ValueError("Neveljavna koda države.")
        self._spremeni_nastavitve(lambda d: d.update(media_watch_country="auto" if drzava == "AUTO" else drzava))
        return True

    def _sezona(self, a: list) -> Any:
        return self.mc.season(int(a[0]) if a else 0, int(a[1]) if len(a) > 1 else 1)

    def _epizoda(self, a: list) -> Any:
        return self.mc.episode_item(int(a[0]) if a else 0, int(a[1]) if len(a) > 1 else 1,
                                    int(a[2]) if len(a) > 2 else 1, self._niz(a, 3))

    def _film(self, a: list) -> Any:
        return self.mc.movie_item(int(a[0]) if a else 0, self._niz(a, 1))

    def _razlicice(self, a: list) -> Any:
        """[id vnosa]: razlicice za seznam v podrobnostih (core/os_media.razlicice_naslova)."""
        return self.mc.razlicice_naslova(self._niz(a, 0))

    def _izberi_razlicico(self, a: list) -> bool:
        """[id vnosa, podpis]: rocna izbira se zapomni za ta naslov; podpis privzete izbiro pobrise."""
        return self.mc.izberi_razlicico(self._niz(a, 0), self._niz(a, 1))

    def _viri(self, _a: list) -> Any:
        # »vticniki«: ta most zna upravljati vticnike strežnika Jellyfin (stran sicer gumba ne pokaze).
        return [dict(v, vticniki=True) if v.get("ponudnik") == "jellyfin" else v for v in self.mc.sources()]

    def _dodaj_vir(self, a: list) -> Any:
        return self.mc.add_source(self._niz(a, 0), self._niz(a, 1))

    def _dodaj_streznik(self, a: list) -> Any:
        vrednosti = [str(v or "") for v in a[:5]] + [""] * 5
        return self.mc.add_server(*vrednosti[:5])

    def _odstrani_vir(self, a: list) -> Any:
        ident = self._niz(a, 0)
        skrivnost = ""
        try:   # geslo odstranjenega streznika ne ostane v zbirki skrivnosti
            skrivnost = next((str(s.get("secret_enc") or "") for s in self.mc._load().get("osebni_strezniki", [])
                              if isinstance(s, dict) and s.get("id") == ident), "")
        except Exception:  # noqa: BLE001
            pass
        ok = self.mc.remove_source(ident)
        if ok and skrivnost:
            pozabi(skrivnost)
        return ok

    def _osvezi_vir(self, a: list) -> Any:
        ident = self._niz(a, 0)
        return self.mc.refresh_source(ident) if ident else self.mc.refresh_all()

    def _odkrij_dlna(self, _a: list) -> Any:
        return media_servers.odkrij_dlna()

    # ------------------------------------------------------------------ vticniki strežnika Jellyfin
    @staticmethod
    def _jf_napaka(napaka: Exception) -> dict:
        if isinstance(napaka, jellyfin_vticniki.NapakaJellyfin):
            koda = napaka.koda
        elif isinstance(napaka, RuntimeError):
            koda = "skrivnost"      # zbirka skrivnosti zaklenjena ali brez gesla (razkrij)
        elif isinstance(napaka, ValueError):
            koda = "neveljavno"     # strežnika ni (vec) med viri
        else:
            koda = "omrezje"
        return {"ok": False, "napaka": koda}

    def _jf_vticniki(self, a: list) -> Any:
        """[id strežnika] -> namesceni vticniki, katalog, repozitoriji, priporoceno (samo branje za ne-skrbnika)."""
        try:
            base, zeton = self.mc.jellyfin_dostop(self._niz(a, 0))
            return jellyfin_vticniki.stanje(base, zeton)
        except Exception as napaka:  # noqa: BLE001 - stran pove razlog, ne sklad klicev
            return self._jf_napaka(napaka)

    def _jf_vticnik(self, a: list) -> Any:
        """[id strežnika, "vklopi" | "izklopi" | "odstrani", id vticnika, razlicica]."""
        dejanje = self._niz(a, 1)
        if dejanje not in ("vklopi", "izklopi", "odstrani"):
            return {"ok": False, "napaka": "neveljavno"}
        try:
            base, zeton = self.mc.jellyfin_dostop(self._niz(a, 0))
            if dejanje == "odstrani":
                return jellyfin_vticniki.odstrani(base, zeton, self._niz(a, 2), self._niz(a, 3))
            return jellyfin_vticniki.preklopi(base, zeton, self._niz(a, 2), self._niz(a, 3), dejanje == "vklopi")
        except Exception as napaka:  # noqa: BLE001
            return self._jf_napaka(napaka)

    def _jf_namesti(self, a: list) -> Any:
        """[id strežnika, ime paketa, guid, naslov repozitorija]."""
        try:
            base, zeton = self.mc.jellyfin_dostop(self._niz(a, 0))
            return jellyfin_vticniki.namesti(base, zeton, self._niz(a, 1), self._niz(a, 2), self._niz(a, 3))
        except Exception as napaka:  # noqa: BLE001
            return self._jf_napaka(napaka)

    def _jf_zagon(self, a: list) -> Any:
        """[id strežnika] -> ponovni zagon; napredek gre strani kot dogodek mediaJellyfinZagon {streznik, faza, sekund}."""
        ident = self._niz(a, 0)
        try:
            base, zeton = self.mc.jellyfin_dostop(ident)
            izid = jellyfin_vticniki.ponovni_zagon(
                base, zeton, lambda faza, sekund: self.dogodek("mediaJellyfinZagon", {"streznik": ident, "faza": faza,
                                                                                      "sekund": sekund}))
        except Exception as napaka:  # noqa: BLE001
            return self._jf_napaka(napaka)
        if izid.get("ok"):
            self.mc.streznik_spremenjen(ident)      # novi vticniki (kanali, metapodatki) se pokazejo v katalogu
        return izid

    # ------------------------------------------------------------------ prilagojen meni (skriti zavihki in viri)
    #: Kljuc skritega predmeta leve navigacije: "kat:<zavihek>" ali "vir:<id vira>" ("vir:mape" = Ta racunalnik).
    _SKRITO = re.compile(r"^(?:kat|vir):[\w:.\-]{1,200}$")
    NAJVEC_SKRITIH = 300

    def _skriti(self) -> list:
        vrednost = self._nastavitve().get("media_skrito")
        if not isinstance(vrednost, list):
            return []
        return sorted({str(k) for k in vrednost if self._SKRITO.match(str(k)) and str(k) != "kat:domov"})[:self.NAJVEC_SKRITIH]

    def _skrito(self, _a: list) -> list:
        """Kaj je uporabnik skril iz leve navigacije Medijskega centra (skupno glavnemu oknu in Safeer Playerju)."""
        return self._skriti()

    def _skrij(self, a: list) -> list:
        """[kljuc, da]: skrij ali spet pokazi zavihek oziroma vir v navigaciji. Samo videz menija - podatki, viri in
        iskanje ostanejo nespremenjeni. Domov se ne da skriti."""
        k, da = self._niz(a, 0), bool(a[1]) if len(a) > 1 else True
        if not self._SKRITO.match(k) or k == "kat:domov":
            raise ValueError("Neveljaven predmet menija.")
        def sprememba(d: dict) -> None:
            # Skriti iz istega branja kot zapis (pod zaklepom): hkraten klic iz druge niti se ne izgubi.
            skrito = {str(x) for x in (d.get("media_skrito") if isinstance(d.get("media_skrito"), list) else [])
                      if self._SKRITO.match(str(x)) and str(x) != "kat:domov"}
            if da:
                skrito.add(k)
            else:
                skrito.discard(k)
            d["media_skrito"] = sorted(skrito)[:self.NAJVEC_SKRITIH]
        self._spremeni_nastavitve(sprememba)
        izid = self._skriti()
        self.dogodek("mediaSkrito", izid)          # drugo okno (glavno ali Safeer Player) se uskladi takoj
        return izid

    # ------------------------------------------------------------------ samodejni seznami (core/samodejni_seznami.py)
    _NASLOVNICE = ("cover.jpg", "cover.png", "folder.jpg", "folder.png", "front.jpg", "front.png")

    def _naslovnica_mape(self, mapa: Path, predpomnilnik: dict) -> str:
        """Prava naslovnica albuma v mapi (cover.jpg, folder.jpg ...), ce obstaja; brez nje kartica pokaze znak."""
        kljuc = str(mapa)
        if kljuc not in predpomnilnik:
            najdeno = ""
            try:
                imena = {p.name.casefold(): p for p in mapa.iterdir() if p.is_file()}
                najdeno = next((imena[i].as_uri() for i in self._NASLOVNICE if i in imena), "")
            except OSError:
                pass
            predpomnilnik[kljuc] = najdeno
        return predpomnilnik[kljuc]

    @staticmethod
    def _oznake_datoteke(pot: str) -> tuple:
        """(izvajalec, zvrst) iz oznak datoteke, ce je mutagen namescen; sicer prazno (izvajalec iz imena datoteke)."""
        try:
            from mutagen import File as MutagenFile
            oznake = MutagenFile(pot, easy=True) or {}
            prvi = lambda *imena: next((str(oznake.get(i)[0]) for i in imena if oznake.get(i)), "")  # noqa: E731
            return prvi("artist", "albumartist"), prvi("genre")
        except Exception:  # noqa: BLE001 - brez mutagena ali pokvarjena datoteka: ime datoteke
            return "", ""

    def _zberi_skladbe(self) -> list:
        """Vsa uporabnikova glasba za samodejne sezname: krajevna knjiznica, skladbe osebnih streznikov (Navidrome,
        Funkwhale, Jellyfin, DLNA ...) in skladbe iz kataloga, ki jih je predvajal. Stevci predvajanj iz knjiznice in
        core/os_police.py. Bere disk in omrezje - samo v ozadni niti."""
        skladbe, vnosi, naslovnice = [], {}, {}
        oznake = getattr(self, "_oznake", {})
        try:
            for v in self.lokalna.glasba(3000):
                if not v["naVoljo"]:
                    continue
                pot = Path(v["pot"])
                try:
                    kljuc_oznak = (str(pot), int(pot.stat().st_mtime))
                except OSError:
                    continue
                if kljuc_oznak not in oznake:
                    oznake[kljuc_oznak] = self._oznake_datoteke(str(pot))
                izvajalec, zanr = oznake[kljuc_oznak]
                ime = str(v.get("ime") or pot.stem)
                izvajalec = izvajalec or samodejni_seznami.izvajalec_iz_imena(pot.name)
                if izvajalec and ime.casefold().startswith(izvajalec.casefold()):
                    ime = re.sub(r"^\s*[-–—]\s*", "", ime[len(izvajalec):]) or ime
                skladbe.append({"id": "pot:" + str(pot), "naslov": ime, "izvajalec": izvajalec, "zanr": zanr,
                                "slika": self._naslovnica_mape(pot.parent, naslovnice), "pot": str(pot), "url": pot.as_uri(),
                                "dodano": v.get("dodano"), "zadnjic": v.get("zadnjic"), "n": v.get("predvajanj"),
                                "sekund": v.get("trajanje")})
        except Exception as e:  # noqa: BLE001 - zaklenjena baza ne ustavi ostalih virov
            print("[SafeerMedia] samodejni seznami (knjiznica): %s" % type(e).__name__, flush=True)
        self._oznake = dict(list(oznake.items())[-5000:])
        stevci = {}
        for k, v in self.police.predvajanja().items():
            m = v.get("m") if isinstance(v.get("m"), dict) else {}
            if str(m.get("vrsta") or "") in os_police.ZVOCNE and m.get("id") and m.get("naslov"):
                stevci[str(m["id"])] = (int(v.get("n") or 0), int(v.get("t") or 0))
                if str(m.get("url") or "").startswith(("http://", "https://")):
                    skladbe.append({"id": str(m["id"]), "naslov": m["naslov"], "izvajalec": m.get("izvajalec"), "slika": m.get("slika"),
                                    "url": m["url"], "n": v.get("n"), "zadnjic": v.get("t")})
                    vnosi[str(m["id"])] = {"id": str(m["id"]), "naslov": m["naslov"], "izvajalec": m.get("izvajalec") or "",
                                           "slika": m.get("slika") or "", "vrsta": "glasba", "url": m["url"]}
        osebni = getattr(self.mc, "_personal_items", None)
        if osebni is not None:
            try:
                for item in osebni(""):
                    if not isinstance(item, dict) or item.get("vrsta") != "glasba" or not item.get("id") or not item.get("url"):
                        continue
                    n, t = stevci.get(str(item["id"]), (0, 0))
                    if str(item["url"]).startswith("stremio:") and not n:
                        # Katalog dodatka Stremio (npr. Flix-Music) ni uporabnikova glasba in pogosto nima toka: na
                        # testnem PC 14. 10. 2026 je bil »Odkrij« iz 25 takih vnosov in nobeden ni zaigral (ni_toka).
                        # Steje samo, kar je uporabnik ze predvajal.
                        continue
                    zanri = item.get("zanri")
                    skladbe.append({"id": str(item["id"]), "naslov": item.get("naslov"), "izvajalec": item.get("izvajalec"),
                                    "zanr": ", ".join(str(z) for z in zanri) if isinstance(zanri, list) else zanri,
                                    "slika": item.get("slika"), "url": item["url"], "n": n, "zadnjic": t,
                                    "sekund": item.get("trajanje")})
                    vnosi[str(item["id"])] = item
            except Exception as e:  # noqa: BLE001 - nedosegljiv streznik ne ustavi knjiznice
                print("[SafeerMedia] samodejni seznami (strezniki): %s" % type(e).__name__, flush=True)
        self._samodejni_vnosi = vnosi
        return skladbe

    def izracunaj_samodejne(self) -> list:
        seznami = samodejni_seznami.sestavi(self._zberi_skladbe(), time.time())
        with self._zaklep:
            spremenjeno = samodejni_seznami.povzetek(seznami) != samodejni_seznami.povzetek(self._samodejni["seznami"])
            self._samodejni.update(seznami=seznami, cas=time.time())
        if spremenjeno:
            self.dogodek("mediaSamodejniOsvezeni", None)
        return seznami

    def _samodejni_seznami(self, _a: list) -> dict:
        """Povzetek samodejnih seznamov iz predpomnilnika; starejse od 10 minut se v ozadju izracuna znova (stran dobi
        dogodek »mediaSamodejniOsvezeni«, ko so novi)."""
        with self._zaklep:
            star = time.time() - self._samodejni["cas"] >= samodejni_seznami.OSVEZI_S
            racuna = self._samodejni["racunam"]
            if star and not racuna:
                self._samodejni["racunam"] = racuna = True
            else:
                star = False
            seznami = samodejni_seznami.povzetek(self._samodejni["seznami"])

        def delo():
            try:
                self.izracunaj_samodejne()
            except Exception as e:  # noqa: BLE001
                print("[SafeerMedia] samodejni seznami: %s" % e, flush=True)
            finally:
                with self._zaklep:      # tudi po napaki (streznik ne odgovori): naslednji poskus cez 10 minut
                    self._samodejni.update(racunam=False, cas=time.time())
        if star:
            threading.Thread(target=delo, name="samodejni-seznami", daemon=True).start()
        return {"seznami": seznami, "racuna": racuna}

    def _najdi_samodejni(self, ident: str) -> Optional[dict]:
        with self._zaklep:
            return next((x for x in self._samodejni["seznami"] if x["id"] == ident), None)

    @staticmethod
    def _id_lokalne(pot: str) -> str:
        import hashlib
        return "samodejno-lokalno:" + hashlib.sha1(pot.encode("utf-8"), usedforsecurity=False).hexdigest()[:20]

    def _samodejni_seznam(self, a: list) -> dict:
        """Skladbe samodejnega seznama kot vnosi kataloga (vrsta predvajanja na strani, predvajanje kot katalog)."""
        sz = self._najdi_samodejni(self._niz(a, 0))
        if not sz:
            return {"vnosi": []}
        vnosi, mc = [], self.mc
        izvorni = getattr(self, "_samodejni_vnosi", {})
        for s in sz["skladbe"]:
            if s["pot"]:
                vnos = {"id": self._id_lokalne(s["pot"]), "naslov": s["naslov"], "izvajalec": s["izvajalec"], "slika": s["slika"],
                        "vrsta": "glasba", "url": s["url"], "pot": s["pot"], "vir": ""}
            else:
                vnos = dict(izvorni.get(s["id"]) or {"id": s["id"], "naslov": s["naslov"], "izvajalec": s["izvajalec"],
                                                       "slika": s["slika"], "vrsta": "glasba", "url": s["url"]})
            # Bogatejsi vnos kataloga (glave, referer, razlicice) ostane: skrcen vnos s seznama ga ne sme nadomestiti,
            # sicer poznejse predvajanje odpove (pregled 14. 10. 2026).
            vnos = mc._dynamic_items.setdefault(vnos["id"], vnos)
            vnosi.append({k: vnos.get(k) for k in ("id", "naslov", "izvajalec", "slika", "vrsta", "vir")})
        return {"id": sz["id"], "vnosi": vnosi}

    def _samodejni_shrani(self, a: list) -> dict:
        """»Shrani kot seznam«: samodejni seznam postane navaden seznam predvajanja (se ne spreminja vec)."""
        sz = self._najdi_samodejni(self._niz(a, 0))
        if not sz:
            return {"napaka": "ni_mogoce"}
        # Skladba osebnega streznika ima v naslovu prijavo (api_key, u/t/s): seznam hrani id streznika, naslov brez
        # prijave zapise MediaCenter._seznami_pisi, prijavo doda ob predvajanju (MediaCenter.s_prijavo).
        skladbe = [dict({"naslov": s["naslov"], "izvajalec": s["izvajalec"], "slika": s["slika"], "sekund": s["sekund"],
                         "url": s["url"]}, **({"streznik": media_servers.streznik_iz_id(s["id"])}
                                             if media_servers.streznik_iz_id(s["id"]) else {}))
                   for s in sz["skladbe"] if s["url"]]
        return self.mc.shrani_seznam(self._niz(a, 1), skladbe)

    # ------------------------------------------------------------------ seznami predvajanja
    def _seznami(self, _a: list) -> Any:
        self.uskladi_sezname()
        return self.mc.seznami()

    def _seznam(self, a: list) -> Any:
        return self.mc.seznam(self._niz(a, 0))

    def _uvozi_seznam(self, a: list) -> Any:
        izid = self.mc.uvozi_seznam(self._niz(a, 0))
        if isinstance(izid, dict) and izid.get("ime"):
            # Skladbam brez posnetka (Spotify) posnetke poiscemo v ozadju; ko so, pogled dobi slike skladb.
            self.mc.poisci_posnetke(izid["ime"], ob_koncu=lambda ime: self.dogodek("mediaSeznamOsvezen", {"ime": ime}))
        return izid

    def _odstrani_seznam(self, a: list) -> Any:
        return self.mc.odstrani_seznam(self._niz(a, 0))

    def _dodaj_na_seznam(self, a: list) -> Any:
        return self.mc.dodaj_na_seznam(self._niz(a, 0), self._niz(a, 1))

    def _odstrani_s_seznama(self, a: list) -> Any:
        return self.mc.odstrani_s_seznama(self._niz(a, 0), self._niz(a, 1))

    def _seznam_zamenjava(self, a: list) -> Any:
        return self.mc.seznam_posnetek(self._niz(a, 0), zamenjaj=True)

    def uskladi_sezname(self) -> None:
        """Sezname uskladi z napravami v Linku (najvec enkrat na 45 s, v ozadju); ob spremembi dogodek strani."""
        if self._uskladi_sezname is None or self._seznami_usklajujem or time.monotonic() - self._seznami_usklajeni < 45:
            return
        self._seznami_usklajujem = True
        self._seznami_usklajeni = time.monotonic()

        def delo() -> None:
            try:
                if self._uskladi_sezname(self.mc.seznami_uskladi):
                    self.dogodek("mediaSeznamiUsklajeni", None)
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] seznami:", e, flush=True)
            finally:
                self._seznami_usklajujem = False
        threading.Thread(target=delo, name="safeer-seznami", daemon=True).start()

    # ------------------------------------------------------------------ predvajanje
    def _yt_ukaz(self, a: list) -> bool:
        """Premor/nadaljevanje skladbe v vgradnem predvajalniku ali zapiranje pogleda (stran: vrstica vrste)."""
        ukaz = self._niz(a, 0)
        if ukaz not in ("playVideo", "pauseVideo", "zapri"):
            return False
        if ukaz == "zapri":
            self._yt = None
        return bool(self._v_glavni_pocakaj(lambda: self._youtube_ukaz(ukaz), 4.0))

    def yt_sporocilo(self, besedilo: str) -> None:
        """Stanje vgradnega predvajalnika (skript v lahkem pogledu -> safeer_os.py): konec skladbe sprozi naslednjo iz vrste."""
        yt = self._yt
        if yt is None:
            return
        try:
            d = json.loads(str(besedilo or "")[:400])
        except ValueError:
            return
        if not isinstance(d, dict):
            return
        if d.get("napaka") is True:
            # Lastnik posnetka vgradnje ne dovoli (ali posnetka ni vec): stran poisce drug posnetek ali gre naprej.
            self._yt = None
            print("[SafeerMedia] vgradni predvajalnik: napaka %s" % re.sub(r"[^\w.-]", "", str(d.get("koda") or ""))[:12], flush=True)
            self.dogodek("mediaYtNapaka", {"id": yt["id"]})
            return
        stanje = d.get("stanje")
        if stanje == 1 and not yt["igra"]:
            if not yt["ze_igral"] and yt.get("kljuc"):
                # Vgradni predvajalnik ne javlja mesta: skladba s seznama steje, ko res zaigra (prvic v tej izbiri).
                self.police.stej(yt["kljuc"])
            yt["igra"] = True
            self.dogodek("mediaYt", {"id": yt["id"], "igra": True})
        elif stanje == 2 and yt["igra"]:
            yt["igra"], yt["ze_igral"] = False, True
            self.dogodek("mediaYt", {"id": yt["id"], "igra": False})
        elif stanje == 0 and (yt["igra"] or yt["ze_igral"]):
            self._yt = None
            self.dogodek("mediaKonec", {"id": yt["id"]})

    def yt_podatki(self) -> Optional[dict]:
        """Skladba v vgradnem predvajalniku YouTuba (None, ce je ni): za namizje in sistem v obliki domacega predvajalnika.
        Dokler skladba prvic ne zaigra, velja za predvajano (stran jo tako tudi kaze); premor sele po pavzi."""
        yt = self._yt
        if yt is None:
            return None
        return {"stanje": "predvaja" if yt["igra"] or not yt["ze_igral"] else "premor", "naslov": yt.get("naslov") or "",
                "izvajalec": yt.get("izvajalec") or "", "slika": yt.get("slika") or "", "izvor": "YouTube", "vrsta": "medij"}

    def yt_zaprt(self) -> None:
        """Uporabnik je zaprl okno s skladbo: vrsta se ustavi."""
        yt, self._yt = self._yt, None
        if yt is not None:
            self.dogodek("mediaYtZaprt", {"id": yt["id"]})

    def _stanje(self, _a: list) -> dict:
        return {"na_voljo": True, "native": True, "predvajalnik": "GStreamer"}

    def _tokovi(self, a: list) -> Any:
        return self.mc.tokovi_postaje(self._niz(a, 0))

    def _predvajaj_vnos(self, a: list) -> Optional[dict]:
        ident = self._niz(a, 0)
        item = self.mc.uporabi_izbiro(self.mc.resolve(ident))     # rocno izbrana razlicica (podrobnosti) najprej
        if not item:
            return None
        return self._predvajaj_razresen(item, ident)

    def _predvajaj_razresen(self, item: dict, ident: str) -> Optional[dict]:
        if item.get("napaka_koda") or item.get("napaka") or item.get("sporocilo"):
            return item
        if item.get("stran") and str(item.get("url") or "") == str(item.get("stran")):
            return item       # prenos, ki ga izdajatelj ponuja samo na svoji strani: stran ga odpre v Spletu
        nacin = nacin_predvajanja(item, os_media.je_neposredni_zvok)
        self._yt = None       # nova izbira: prejsnja skladba v vgradnem predvajalniku ne sprozi vec nicesar
        if nacin:
            self._preklici_ponudbo()  # uporabnik je izbral drugo vsebino: ponujena epizoda se ne zacne sama
        kljuc = os_police.kljuc_vnosa(dict(item, id=str(item.get("id") or ident)))
        if str(item.get("id") or ident).startswith("samodejno-lokalno:") and item.get("pot"):
            # Datoteka s samodejnega seznama: predvajanje steje krajevna knjiznica (kot klik na skladbo), ne polica -
            # ista skladba ni dvakrat na policah.
            kljuc = ""
            try:
                self.lokalna.predvajano(str(item["pot"]))
            except Exception:  # noqa: BLE001
                pass
        if kljuc and nacin in ("youtube", "neposredno"):
            self.police.zapomni(kljuc, self._opis_vnosa(item, ident))
        # Dnevnik brez naslova vsebine: samo pot predvajanja in gostitelj (za iskanje napak, kot na Windows).
        print("[SafeerMedia] pot=%s vrsta=%s gostitelj=%s" % (nacin or "ni", item.get("vrsta") or "",
              urllib.parse.urlsplit(str(item.get("url") or "")).hostname or ""), flush=True)
        if nacin == "youtube":
            # Skladba s seznama predvajanja: vgradni predvajalnik YouTuba v lahkem medijskem pogledu.
            ident = str(item.get("id") or ident)
            naslov = naslov_za_predvajalnik(item)
            url = naslov_vgradnje(item["youtube"])
            # Naslov, izvajalec in slika: za pripomocek »Predvaja se« na namizju in sistem (MPRIS), ki ne poznata strani.
            self._yt = {"id": ident, "igra": False, "ze_igral": False, "kljuc": kljuc,
                        "naslov": str(item.get("naslov") or "")[:300], "izvajalec": str(item.get("izvajalec") or "")[:200],
                        "slika": str(item.get("slika") or "")[:2048]}
            if not url or not self._v_glavni_pocakaj(lambda: self._youtube(url, naslov)):
                self._yt = None
                return dict(item, native=True, napaka_koda="tok")
            return dict(item, native=True, zvok=True, okno_youtube=True)
        if nacin == "neposredno":
            url = str(item.get("url") or "")
            if item.get("pot") and not url.startswith("file:"):
                url = Path(str(item["pot"])).as_uri()
            vrsta = vrsta_predvajalnika(item)
            zacetek = self._zacetek(item, ident, kljuc) if vrsta in ("video", "medij") else 0
            argumenti = [url, vrsta, naslov_za_predvajalnik(item), zacetek, podnapisi_vnosa(item), vrsta in ("video", "tv")]
            tok = tok_za_predvajalnik(item, url)
            if tok:
                argumenti.append(tok)    # glave toka in druge razlicice (samo, ce jih vnos ima)
            ok = self._v_glavni_pocakaj(lambda: self._predvajaj(*argumenti))
            if not ok:
                return dict(item, native=True, napaka_koda="tok")
            if len(self._predvajano) > 50:
                self._predvajano.clear()
            # izvajalec in slika: za sistem (MPRIS - zvocni applet in medijske tipke pokazejo, kaj igra)
            self._predvajano[url] = {"id": str(item.get("id") or ident), "zvok": vrsta in ("medij", "radio"), "vrsta": vrsta,
                                     "kljuc": kljuc,
                                     "izvajalec": str(item.get("izvajalec") or "")[:200], "slika": str(item.get("slika") or "")[:2048]}
            if vrsta == "video":
                # IMDb oznaka za »Poisci podnapise na spletu« v predvajalniku (core/podnapisi_splet.py)
                from . import podnapisi_splet
                self._predvajano[url]["podnapisi_id"] = podnapisi_splet.id_vnosa(item)
            return dict(item, native=True, zvok=vrsta in ("medij", "radio"))
        if nacin == "vdelano":
            ok = self._v_glavni_pocakaj(lambda: self._vdelano(str(item.get("url") or "")))
            return dict(item, native=True) if ok else dict(item, native=True, napaka_koda="tok")
        return dict(item, napaka_koda="ni_toka")

    # ------------------------------------------------------------------ polica »Na tvojih napravah« (knjiznica kroga)
    def _knjiznica_seznam(self, _a: list) -> Any:
        return self._knjiznica.seznam() if self._knjiznica is not None else []

    def predvajanje_ni_uspelo(self, uri: str) -> bool:
        """Domaci predvajalnik ni odprl naslova z nobeno razlicico (vse so vrnile napako). Lastnik: »nimamo
        nedelujocih ikon« - naslov izgine iz kataloga (mediaNiNaVoljo) do ponovne preverbe (NI_NA_VOLJO_VELJA), naslednji
        klic pa tokove vprasa znova (razreseni vnos s starimi povezavami pozabimo)."""
        zapis = self._predvajano.get(str(uri or "")) or {}
        ident = str(zapis.get("id") or "")
        if not ident:
            return False
        mc = self.mc
        item = mc._dynamic_items.get(ident)
        if not isinstance(item, dict) or os_media.lastni_vir(item):   # na lastnem strezniku je vedno na voljo
            return False
        mc.oznaci_ni_na_voljo(item)
        if mc.znano_ni_na_voljo(item):
            mc._dynamic_items.pop(ident, None)
            self.dogodek("mediaNiNaVoljo", {"idji": [ident]})
            return True
        return False

    def _knjiznica_predvajaj(self, a: list) -> Optional[dict]:
        """Film s police: prenos motorja Safeer OS naravnost iz torrenta; film na drugi napravi pretaka naprava, ki ga
        hrani - predvajalnik ga bere skozi lokalni pretok (pripeto potrdilo in zeton, core/link_pretok.py)."""
        if self._knjiznica is None:
            return None
        r = self._knjiznica.predvajaj(self._niz(a, 0))
        if not r.get("ok"):
            return {"napaka_koda": str(r.get("koda") or "napaka")}
        if r.get("tukaj"):
            self.mc.knjiznica_vnos(r["tukaj"])
            return self._predvajaj_vnos(["knjiznica:" + r["tukaj"]["kljuc"]])
        from . import link_pretok
        v, tok = r["vnos"], r["tok"]
        vir = link_pretok.vir_toka(tok.get("server"), tok.get("path"), mimetypes.guess_type(str(tok.get("name") or ""))[0] or "")
        if vir is None:
            return {"napaka_koda": "napaka"}
        url = link_pretok.pretok().dodaj(vir)
        # Podnapisi iz istega torrenta: naprava, ki film hrani, jih pretaka kot film (krog 85).
        from . import knjiznica_kroga
        podnapisi = tuple(knjiznica_kroga.podnapisi_toka(tok))
        ident = str(v.get("ref") or "") or "knjiznica:" + v["kljuc"]
        naslov = str(v.get("naslov") or "")
        self._yt = None
        self._preklici_ponudbo()
        print("[SafeerMedia] pot=knjiznica vrsta=%s podnapisov=%d" % (v.get("vrsta") or "", len(podnapisi)), flush=True)
        zacetek = self.napredek_za(ident)
        if not self._v_glavni_pocakaj(lambda: self._predvajaj(url, "video", naslov, zacetek, podnapisi, True)):
            return {"napaka_koda": "tok"}
        if len(self._predvajano) > 50:
            self._predvajano.clear()
        kljuc = "id:" + ident
        self.police.zapomni(kljuc, {"id": ident, "naslov": naslov, "vrsta": "film" if v.get("vrsta") != "serija" else "serija",
                                    "slika": v.get("slika") or ""})
        self._predvajano[url] = {"id": ident, "zvok": False, "vrsta": "video", "kljuc": kljuc}
        return {"id": ident, "naslov": naslov, "native": True, "zvok": False}

    def _knjiznica_odstrani(self, a: list) -> bool:
        return bool(self._knjiznica is not None and self._knjiznica.odstrani(self._niz(a, 0)))

    def _knjiznica_obdrzi(self, a: list) -> bool:
        """»Obdrži«: prenos ne potece po 48 urah (oznako hrani naprava, ki film hrani)."""
        return bool(self._knjiznica is not None and self._knjiznica.obdrzi(self._niz(a, 0), bool(a[1]) if len(a) > 1 else True))

    def _v_glavni_pocakaj(self, delo: Callable[[], Any], cas: float = 12.0) -> Any:
        """Delo, ki potrebuje okno (Gtk), izvede v glavni niti in pocaka na izid."""
        konec, izid = threading.Event(), {}

        def naredi():
            try:
                izid["v"] = delo()
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] katalog predvajanje:", e, flush=True)
                izid["v"] = False
            konec.set()
            return False
        self.v_glavni(naredi)
        konec.wait(cas)
        return izid.get("v", False)

    # ------------------------------------------------------------------ napredek in konec (klice safeer_os.py)
    def vnos_predvajanega(self, uri: str) -> Optional[dict]:
        return self._predvajano.get(str(uri or ""))

    def _napredki(self) -> dict:
        try:
            d = json.loads((self.config_dir / "napredek.json").read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def napredek_za(self, ident: str) -> int:
        v = self._napredki().get(ident)
        return int(v[0]) if isinstance(v, list) and v and isinstance(v[0], (int, float)) and v[0] >= 15 else 0

    def shrani_napredek(self, uri: str, pozicija: float, trajanje: float) -> None:
        """Film ali epizoda iz kataloga (in dolg zvok - podcast): zapomnimo si, kje je uporabnik ostal; ne za skladbe
        in prenose v zivo. Klice se vsakih nekaj sekund med predvajanjem: tu tudi stejemo predvajanje in oznacimo
        video kot ogledan (core/os_police.py)."""
        vnos = self._predvajano.get(str(uri or ""))
        if not vnos:
            return
        self._stej_in_oznaci(vnos, pozicija, trajanje)
        dolg_zvok = vnos.get("vrsta") == "medij" and trajanje >= os_police.DOLG_ZVOK_S
        if (vnos.get("vrsta") != "video" and not dolg_zvok) or pozicija < 15 or trajanje <= 0:
            return
        d = self._napredki()
        # Tik pred koncem ali ogledano (90 %, odjavna spica): naslednjic od zacetka, ne »Nadaljuj« pri odjavni spici.
        if trajanje - pozicija < 20 or (vnos.get("vrsta") == "video" and os_police.je_ogledano(pozicija, trajanje)):
            d.pop(vnos["id"], None)
        else:
            d[vnos["id"]] = [int(pozicija), int(trajanje), int(time.time())]
        if len(d) > NAJVEC_NAPREDKOV:
            for k, _ in sorted(d.items(), key=lambda kv: kv[1][2] if isinstance(kv[1], list) and len(kv[1]) > 2 else 0)[:len(d) - NAJVEC_NAPREDKOV]:
                d.pop(k, None)
        self._pisi_napredke(d)

    def _stej_in_oznaci(self, vnos: dict, pozicija: float, trajanje: float) -> None:
        """Predvajanje steje enkrat na izbiro, ko je preteklo dovolj (os_police.prag_stetja); video pri 90 % je ogledan."""
        kljuc = vnos.get("kljuc")
        if not kljuc:
            return
        if not vnos.get("steto") and pozicija >= os_police.prag_stetja(trajanje):
            vnos["steto"] = True
            self.police.stej(kljuc)
        if vnos.get("vrsta") == "video" and not vnos.get("ogledan") and os_police.je_ogledano(pozicija, trajanje):
            vnos["ogledan"] = True
            self.police.nastavi_ogledano(kljuc, True)

    def konec(self, uri: str) -> None:
        """Domaci predvajalnik je vnos odigral do konca: film pozabi napredek in je ogledan, skladba sprozi naslednjo iz
        vrste, po epizodi Safeer ponudi naslednjo (dogodek mediaNaslednja). Datoteka iz krajevne knjiznice ni v
        _predvajano: zanjo velja _konec_lokalne."""
        vnos = self._predvajano.get(str(uri or ""))
        if not vnos:
            if str(uri or "").startswith("file://"):
                # Knjiznica (SQLite) in do 5000 epizod s preverbo datotek na NAS: v ozadju, glavna nit ne zamrzne.
                threading.Thread(target=self._konec_lokalne, args=(str(uri),), name="safeer-konec-lokalne",
                                 daemon=True).start()
            return
        if vnos.get("vrsta") in ("video", "medij"):
            d = self._napredki()
            if d.pop(vnos["id"], None) is not None:
                self._pisi_napredke(d)
        if vnos.get("vrsta") == "video" and vnos.get("kljuc"):
            self.police.nastavi_ogledano(vnos["kljuc"], True)
            epizoda = os_police.razcleni_kljuc_epizode(vnos["kljuc"])
            if epizoda is not None:
                # Naslednjo epizodo pove TMDB (omrezje): v ozadju, glavna nit (predvajalnik) ne caka.
                threading.Thread(target=self._ponudi_naslednjo_kataloga, args=(epizoda, vnos["kljuc"]),
                                 name="safeer-naslednja", daemon=True).start()
        if vnos.get("zvok"):
            self.dogodek("mediaKonec", {"id": vnos["id"]})

    def _pisi_napredke(self, d: dict) -> None:
        """Atomaren zapis napredek.json (zacasna datoteka + os.replace): izpad med pisanjem ne izgubi vseh mest."""
        zacasna = self.config_dir / (".napredek.json.%d.%d.tmp" % (os.getpid(), threading.get_ident()))
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            zacasna.write_text(json.dumps(d), encoding="utf-8")
            os.replace(zacasna, self.config_dir / "napredek.json")
        except OSError:
            try:
                zacasna.unlink()
            except OSError:
                pass

    def _zacetek(self, item: dict, ident: str, kljuc: str) -> int:
        """Kje nadaljevati: napredek po id vnosa; ce ga ni, po id, pod katerim je bil isti naslov (kljuc) predvajan
        prej (epizodo s police Safeer po ponovnem zagonu sestavi znova in ima lahko drug id)."""
        zacetek = self.napredek_za(str(item.get("id") or ident))
        if zacetek or not kljuc:
            return zacetek
        prej = str(self.police.opis(kljuc).get("id") or "")
        return self.napredek_za(prej) if prej and prej != str(item.get("id") or ident) else 0

    @staticmethod
    def _opis_vnosa(item: dict, ident: str) -> dict:
        """Kar kartica na polici potrebuje; naslov toka le pri prenosih in skladbah (rezerva, ce ga katalog izgubi)."""
        opis = {p: item.get(p) for p in ("naslov", "vrsta", "slika", "izvajalec", "tmdb_id", "sezona", "epizoda", "leto",
                                          "vir", "ozadje")}
        opis["id"] = str(item.get("id") or ident)
        zanri = item.get("zanri")
        if isinstance(zanri, list) and zanri:
            opis["zanr"] = zanri[0]
        if str(item.get("vrsta") or "") in ("radio", "tv-v-zivo", "glasba", "podcast"):
            opis["url"] = str(item.get("url") or "")
        return os_police.cisti_opis(opis)

    # ------------------------------------------------------------------ osebne police (core/os_police.py)
    @property
    def lokalna(self):
        if self._lokalna is None:
            from . import os_knjiznica
            self._lokalna = os_knjiznica.Knjiznica()
        return self._lokalna

    @staticmethod
    def _vnos_lokalni(v: dict) -> dict:
        return {"kljuc": "pot:" + v["pot"], "tip": "lokalno", "pot": v["pot"], "naslov": v.get("ime") or "",
                "vrsta": v.get("vrsta") or "", "pozicija": int(v.get("pozicija") or 0), "trajanje": int(v.get("trajanje") or 0),
                "ogledano": bool(v.get("ogledano")), "n": int(v.get("predvajanj") or 0), "t": int(v.get("zadnjic") or 0)}

    @staticmethod
    def _vnos_opisa(k: str, m: dict, ogledano: dict) -> dict:
        tip = "tok" if k.startswith("tok:") else "lokalno" if k.startswith("pot:") else "katalog"
        d = {"kljuc": k, "tip": tip, "naslov": str(m.get("naslov") or ""), "vrsta": str(m.get("vrsta") or ""),
             "ogledano": k in ogledano}
        for p in ("slika", "izvajalec", "podnaslov", "id", "url", "tmdb_id", "sezona", "epizoda", "leto", "vir", "ozadje", "zanr"):
            if m.get(p):
                d[p] = m[p]
        if tip == "tok":
            d["url"] = k[4:]
        elif tip == "lokalno":
            d["pot"] = k[4:]
        return d

    def _police(self, a: list) -> dict:
        """Police za zavihek Medijskega centra in stanje kartic (srcki in ogledano) za vse zavihke."""
        zavihek, iskanje = self._niz(a, 0), self._niz(a, 1)
        ogledano = self.police.ogledano()
        izhod = {"priljubljene": self.police.kljuci_priljubljenih(),
                 "ogledano": [k for k, _ in sorted(ogledano.items(), key=lambda kv: -kv[1])[:2000]], "police": []}
        vrste = os_police.POLICE_ZAVIHKOV.get(zavihek, ())
        if not vrste or iskanje.strip():
            return izhod
        viri = {}
        for ime in vrste:
            try:
                viri[ime] = getattr(self, "_polica_" + ime)(zavihek, ogledano)
            except Exception as e:  # noqa: BLE001 - polica, ki ne gre (baza zaklenjena, TMDB), ne podre ostalih
                print("[SafeerMedia] polica %s: %s" % (ime, type(e).__name__), flush=True)
                viri[ime] = []
        izhod["police"] = os_police.sestavi_police(zavihek, viri)
        self._ovitki_s_prijavo(izhod["police"])
        return izhod

    def _ovitki_s_prijavo(self, police: list) -> None:
        """Ovitek skladbe osebnega streznika (Navidrome, Plex) je na polici shranjen brez prijave (core/os_police.py,
        cisti_opis): za prikaz na tej napravi ga dopolni s prijavo, na disk ne gre."""
        s_prijavo = getattr(self.mc, "s_prijavo", None)
        vnosi = [v for p in police for v in p.get("vnosi") or []
                 if str(v.get("slika") or "").startswith(("http://", "https://")) and v.get("tip") == "katalog"]
        if not vnosi or s_prijavo is None:
            return
        try:
            prijave = self.mc._prijave_streznikov()
            if prijave:
                for v in vnosi:
                    v["slika"] = s_prijavo(v["slika"], media_servers.streznik_iz_id(v.get("id")), prijave)
        except Exception as e:  # noqa: BLE001 - brez zbirke skrivnosti ostane ovitek brez prijave
            print("[SafeerMedia] ovitki polic: %s" % type(e).__name__, flush=True)

    def _polica_nadaljuj(self, zavihek: str, ogledano: dict) -> list:
        """Nedokoncano iz kataloga in knjiznice ter naslednje epizode serij, nazadnje gledano prvo."""
        po_id = {}
        for k, v in self.police.predvajanja().items():
            m = v.get("m") if isinstance(v.get("m"), dict) else {}
            if m.get("id"):
                po_id[m["id"]] = (k, m)
        izhod, serije = [], set()
        for ident, v in self._napredki().items():
            if not (isinstance(v, list) and len(v) >= 2 and ident in po_id):
                continue
            k, m = po_id[ident]
            d = self._vnos_opisa(k, m, ogledano)
            d.update(pozicija=int(v[0] or 0), trajanje=int(v[1] or 0), t=int(v[2] or 0) if len(v) > 2 else 0)
            izhod.append(d)
            if m.get("vrsta") == "serija" and m.get("tmdb_id"):
                serije.add(int(m["tmdb_id"]))
        for v in self.lokalna.nedokoncane():
            izhod.append(self._vnos_lokalni(v))
        if zavihek in ("serije", "video", "domov"):
            for v, cas in os_police.naslednje_lokalne(self.lokalna.epizode()):
                izhod.append(self._vnos_naslednje_lokalne(v, cas))
            izhod += self._naslednje_kataloga(ogledano, serije)
        izhod.sort(key=lambda d: -int(d.get("t") or 0))
        return izhod

    def _vnos_naslednje_lokalne(self, v: dict, cas: int) -> dict:
        ep = os_police.epizoda_datoteke(v["pot"])
        d = dict(self._vnos_lokalni(v), naslednja=True, t=cas)
        if ep:
            d["podnaslov"] = "S%02dE%02d" % (ep[1], ep[2])
        return d

    def _polica_nazadnje(self, zavihek: str, ogledano: dict) -> list:
        """Nazadnje dodano v knjiznico. Glasba po albumih (mapah): nov album je ena kartica, ne dvajset skladb."""
        izhod, albumi = [], set()
        for v in self.lokalna.nazadnje_dodane(200):
            if not os_police.ustreza_zavihku(zavihek, v["vrsta"]):
                continue
            d = self._vnos_lokalni(v)
            if v["vrsta"] == "glasba":
                mapa = str(Path(v["pot"]).parent)
                if mapa in albumi:
                    continue
                albumi.add(mapa)
                d.update(naslov=Path(mapa).name or d["naslov"], podnaslov=d["naslov"], album=True)
            izhod.append(d)
        return izhod

    def _polica_glasba(self, zavihek: str, ogledano: dict) -> list:
        """Nazadnje predvajana glasba (Domov): skladbe z diska po albumih (mapah) in skladbe iz kataloga ali s seznamov,
        nazadnje predvajano prvo. Brez predvajanj police ni (prazne police izpadejo)."""
        izhod, albumi = [], set()
        for v in self.lokalna.nazadnje_predvajana_glasba(200):
            mapa = str(Path(v["pot"]).parent)
            if mapa in albumi:
                continue
            albumi.add(mapa)
            d = self._vnos_lokalni(v)
            d.update(naslov=Path(mapa).name or d["naslov"], podnaslov=d["naslov"], album=True)
            izhod.append(d)
        for k, v in self.police.predvajanja().items():
            m = v.get("m") if isinstance(v.get("m"), dict) else {}
            if str(m.get("vrsta") or "") in os_police.ZVOCNE and m.get("naslov") and int(v.get("t") or 0):
                izhod.append(dict(self._vnos_opisa(k, m, ogledano), t=int(v["t"])))
        izhod.sort(key=lambda d: -int(d.get("t") or 0))
        return izhod

    def _polica_najvec(self, zavihek: str, ogledano: dict) -> list:
        izhod = [self._vnos_lokalni(v) for v in self.lokalna.najveckrat()]
        for k, v in self.police.predvajanja().items():
            n = int(v.get("n") or 0)
            if n >= os_police.NAJMANJ_ZA_NAJVEC and isinstance(v.get("m"), dict) and v["m"].get("naslov"):
                izhod.append(dict(self._vnos_opisa(k, v["m"], ogledano), n=n, t=int(v.get("t") or 0)))
        izhod.sort(key=lambda d: (-int(d.get("n") or 0), -int(d.get("t") or 0)))
        return izhod

    def _polica_priljubljene(self, zavihek: str, ogledano: dict) -> list:
        """Priljubljene; datoteke in postaje le, ce so se v knjiznici (odstranjene ne obljubljajo predvajanja)."""
        izhod = []
        for x in self.police.priljubljene():
            k, m = x["k"], dict(x.get("m") or {})
            if k.startswith("pot:"):
                v = self.lokalna.dobi(k[4:])
                if not v or not v["naVoljo"]:
                    continue
                izhod.append(self._vnos_lokalni(v))
                continue
            if k.startswith("tok:"):
                tok = self.lokalna.dobi_tok(k[4:])
                if not tok:
                    continue
                m.update(naslov=tok["ime"], vrsta=tok["vrsta"])
            if m.get("naslov"):
                izhod.append(self._vnos_opisa(k, m, ogledano))
        return izhod

    def _priljubljena(self, a: list) -> bool:
        """Srcek: [kljuc, da, opis]. Datoteka in postaja morata biti v knjiznici; opis kataloga, ki ga je Safeer
        zapisal ob predvajanju, ima prednost pred opisom s strani."""
        k, da = self._niz(a, 0), bool(a[1]) if len(a) > 1 else True
        opis = a[2] if len(a) > 2 and isinstance(a[2], dict) else {}
        if da and k.startswith("pot:") and not self.lokalna.dobi(k[4:]):
            return False
        if da and k.startswith("tok:") and not self.lokalna.dobi_tok(k[4:]):
            return False
        if da and not k.startswith(("pot:", "tok:")):
            opis = dict(opis, **self.police.opis(k))
        return self.police.nastavi_priljubljeno(k, da, opis)

    def _ogledano(self, a: list) -> dict:
        """»Oznaci kot ogledano/neogledano«: [kljuc, da, opis] -> {"ok", "ogledano"}. Ogledan naslov pozabi mesto
        (naslednjic od zacetka, kot Jellyfin)."""
        k, da = self._niz(a, 0), bool(a[1]) if len(a) > 1 else True
        opis = os_police.cisti_opis(a[2]) if len(a) > 2 and isinstance(a[2], dict) else {}
        if k.startswith("pot:"):
            ok = bool(self.lokalna.nastavi_ogledano(k[4:], da))
            return {"ok": ok, "ogledano": da if ok else not da}
        if k.startswith("tok:") or not os_police.veljaven_kljuc(k):
            return {"ok": False, "ogledano": False}
        if da:
            ident = str(self.police.opis(k).get("id") or opis.get("id") or "")
            d = self._napredki()
            if ident and d.pop(ident, None) is not None:
                self._pisi_napredke(d)
            if opis and not self.police.opis(k):
                self.police.zapomni(k, opis)      # rocno oznacena epizoda: naslov serije za »Naslednja epizoda«
        return {"ok": True, "ogledano": self.police.nastavi_ogledano(k, da)}

    def _polica_predvajaj(self, a: list) -> Optional[dict]:
        """Vnos s police kataloga: [kljuc, opis s strani]. Najprej isti id kot prej (napredek je pod njim), sicer
        epizodo ali film znova sestavi po TMDB, za postajo ali skladbo pa uporabi shranjeni naslov toka."""
        k = self._niz(a, 0)
        if not os_police.veljaven_kljuc(k) or k.startswith(("pot:", "tok:")):
            return None
        stran = os_police.cisti_opis(a[1]) if len(a) > 1 and isinstance(a[1], dict) else {}
        m = self.police.opis(k) or stran
        ident = str(m.get("id") or "")
        if ident:
            izid = self._predvajaj_vnos([ident])
            if izid:
                return izid
        epizoda = os_police.razcleni_kljuc_epizode(k)
        item = None
        if epizoda is not None:
            naslov = str(m.get("naslov") or stran.get("naslov") or "")
            item = self.mc.episode_item(epizoda[0], epizoda[1], epizoda[2], naslov)
        elif k.startswith("tmdb:film:") and k[10:].isdigit():
            item = self.mc.movie_item(int(k[10:]), str(m.get("naslov") or ""))
        if item and item.get("id"):
            return self._predvajaj_vnos([str(item["id"])])
        if m.get("url"):
            # Naslov s streznika je na polici brez prijave (cisti_opis): prijavo doda Medijski center zdaj.
            s_prijavo = getattr(self.mc, "s_prijavo", None)
            url = s_prijavo(m["url"], media_servers.streznik_iz_id(ident)) if s_prijavo else m["url"]
            return self._predvajaj_razresen({"id": ident or k, "naslov": m.get("naslov") or "", "vrsta": m.get("vrsta") or "",
                                             "url": url, "izvajalec": m.get("izvajalec") or "",
                                             "slika": m.get("slika") or ""}, ident or k)
        return None

    def _predvajan_tok(self, a: list) -> int:
        """Shranjena postaja (Dodaj > TV/radio tok) se je zacela: steje za »Najveckrat predvajano«.
        Domaci predvajalnik za te postaje knjiznici ne javlja mesta, zato steje zacetek, ki ga je izbral uporabnik."""
        url = self._niz(a, 0)
        tok = self.lokalna.dobi_tok(url) if url else None
        if not tok:
            return 0
        return self.police.stej("tok:" + url, {"naslov": tok["ime"], "vrsta": tok["vrsta"]})

    # ------------------------------------------------------------------ naslednja epizoda
    def _epizod_v_sezoni(self, tmdb: int, predpomnilnik: dict) -> Callable[[int], int]:
        """Stevilo ze predvajanih epizod sezone po TMDB (prihodnje epizode se ne stejejo)."""
        danes = time.strftime("%Y-%m-%d")

        def epizod(s: int) -> int:
            if s not in predpomnilnik:
                epizode = (self.mc.season(tmdb, s) or {}).get("epizode") or []
                predpomnilnik[s] = [e for e in epizode if str(e.get("datum") or "9999") <= danes]
            return len(predpomnilnik[s])
        return epizod

    def _naslednja_epizoda_kataloga(self, tmdb: int, s: int, e: int, ogledano: dict) -> Optional[dict]:
        """Prva naslednja neogledana epizoda (najvec 12 korakov naprej) z naslovom in sliko iz TMDB.

        Izid (tudi »ni je« ali TMDB ni dosegljiv) velja 30 min: polica se nalozi ob vsaki menjavi zavihka in brez
        omrezja ne sme vsakic znova cakati na TMDB."""
        kljuc, zdaj = (tmdb, s, e), time.monotonic()
        prej = self._naslednje.get(kljuc)
        if prej and zdaj - prej[0] < 1800:
            return prej[1]
        izid = self._poisci_naslednjo(tmdb, s, e, ogledano)
        if len(self._naslednje) > 200:
            self._naslednje.clear()
        self._naslednje[kljuc] = (zdaj, izid)
        return izid

    def _poisci_naslednjo(self, tmdb: int, s: int, e: int, ogledano: dict) -> Optional[dict]:
        sezone: dict = {}
        epizod = self._epizod_v_sezoni(tmdb, sezone)
        for _ in range(12):
            naslednja = os_police.naslednja_kataloga(s, e, epizod)
            if naslednja is None:
                return None
            s, e = naslednja
            if "tmdb:tv:%d:%d:%d" % (tmdb, s, e) not in ogledano:
                podatki = next((x for x in sezone.get(s, []) if int(x.get("stevilka") or 0) == e), {})
                return {"sezona": s, "epizoda": e, "naslov": str(podatki.get("naslov") or ""),
                        "slika": str(podatki.get("slika") or "")}
        return None

    def _vnos_naslednje(self, tmdb: int, kljuc_prej: str, nasl: dict) -> dict:
        m = self.police.opis(kljuc_prej)
        serija = str(m.get("naslov") or "").split(" · ")[0]
        oznaka = "S%02dE%02d" % (nasl["sezona"], nasl["epizoda"])
        return {"kljuc": "tmdb:tv:%d:%d:%d" % (tmdb, nasl["sezona"], nasl["epizoda"]), "tip": "katalog",
                "naslov": serija or nasl["naslov"] or oznaka, "vrsta": "serija", "tmdb_id": tmdb,
                "sezona": nasl["sezona"], "epizoda": nasl["epizoda"], "naslednja": True, "ogledano": False,
                "podnaslov": oznaka + (" · " + nasl["naslov"] if nasl["naslov"] else ""),
                "slika": nasl["slika"] or str(m.get("slika") or "")}

    def _naslednje_kataloga(self, ogledano: dict, zasedene: set) -> list:
        """Naslednja epizoda za serije iz kataloga, gledane v zadnjih 180 dneh (najvec 6 - vsaka vprasa TMDB)."""
        zadnje: dict = {}
        meja = time.time() - os_police.NASLEDNJA_DNI * 86400
        for k, cas in ogledano.items():
            r = os_police.razcleni_kljuc_epizode(k)
            if r is None or cas < meja or r[0] in zasedene:
                continue
            if r[0] not in zadnje or (cas, r[1], r[2]) > zadnje[r[0]][0]:
                zadnje[r[0]] = ((cas, r[1], r[2]), k)
        izhod = []
        for tmdb, ((cas, s, e), k) in sorted(zadnje.items(), key=lambda kv: -kv[1][0][0])[:6]:
            nasl = self._naslednja_epizoda_kataloga(tmdb, s, e, ogledano)
            if nasl:
                izhod.append(dict(self._vnos_naslednje(tmdb, k, nasl), t=cas))
        return izhod

    def _ponudi(self, ponudba: dict) -> None:
        ponudba = dict(ponudba, zeton=secrets.token_hex(8), cas=time.monotonic())
        with self._zaklep_ponudbe:
            self._ponudba = ponudba
        self.dogodek("mediaNaslednja", {k: v for k, v in ponudba.items() if k != "cas"})

    def _vzemi_ponudbo(self, zeton: str) -> Optional[dict]:
        with self._zaklep_ponudbe:
            p = self._ponudba
            if not p or not zeton or p["zeton"] != zeton or time.monotonic() - p["cas"] > 600:
                return None
            self._ponudba = None
        self.dogodek("mediaNaslednjaKonec", {"zeton": zeton})
        return p

    def _preklici_ponudbo(self) -> None:
        with self._zaklep_ponudbe:
            p, self._ponudba = self._ponudba, None
        if p:
            self.dogodek("mediaNaslednjaKonec", {"zeton": p["zeton"]})

    def _naslednja_predvajaj(self, a: list) -> Optional[dict]:
        """Ponujeno epizodo zacne prvi pogled, ki to zahteva; datoteko iz knjiznice odpre stran (odpriLokalniMedij)."""
        p = self._vzemi_ponudbo(self._niz(a, 0))
        if p is None:
            return None
        if p.get("tip") == "lokalno":
            return {"tip": "lokalno", "pot": p.get("pot") or ""}
        return self._polica_predvajaj([p["kljuc"], p])

    def _naslednja_preklici(self, a: list) -> bool:
        return self._vzemi_ponudbo(self._niz(a, 0)) is not None

    def ponujena_naslednja(self) -> Optional[dict]:
        """Za okno predvajalnika (safeer_os.py): trenutna ponudba naslednje epizode ali None. Okno jo lahko pokaze samo
        in jo zacne z izvedi("mediaNaslednjaPredvajaj", [zeton]) - zeton jo porabi enkrat za vsa okna."""
        with self._zaklep_ponudbe:
            p = self._ponudba
            return {k: v for k, v in p.items() if k != "cas"} if p else None

    def _ponudi_naslednjo_kataloga(self, epizoda: tuple, kljuc: str) -> None:
        try:
            tmdb, s, e = epizoda
            nasl = self._naslednja_epizoda_kataloga(tmdb, s, e, self.police.ogledano())
            if nasl:
                self._ponudi(self._vnos_naslednje(tmdb, kljuc, nasl))
        except Exception as e:  # noqa: BLE001 - brez TMDB ni ponudbe; predvajanje je ze koncano
            print("[SafeerMedia] naslednja epizoda: %s" % type(e).__name__, flush=True)

    def _konec_lokalne(self, uri: str) -> None:
        """Film ali epizoda iz krajevne knjiznice je odigrana do konca: ogledana; po epizodi ponudimo naslednjo.
        Tece v ozadni niti (konec); ponudba gre na glavno nit (v_glavni)."""
        if not uri.startswith("file://"):
            return
        pot = urllib.parse.unquote(urllib.parse.urlsplit(uri).path)
        try:
            v = self.lokalna.dobi(pot)
            if not v or v["vrsta"] not in ("filmi", "serije"):
                return
            self.lokalna.nastavi_ogledano(pot, True)
            if v["vrsta"] != "serije":
                return
            epizode = {x["pot"]: x for x in self.lokalna.epizode()}
            naslednja = os_police.naslednja_lokalna(pot, epizode.keys())
            x = epizode.get(naslednja or "")
            if x and x["naVoljo"] and not x["ogledano"]:
                ponudba = self._vnos_naslednje_lokalne(x, int(time.time()))
                self.v_glavni(lambda: self._ponudi(ponudba) and False)
        except Exception as e:  # noqa: BLE001 - baza zaklenjena: predvajanje se konca brez ponudbe
            print("[SafeerMedia] konec datoteke: %s" % type(e).__name__, flush=True)

    def zapri(self) -> None:
        self._yt = None
