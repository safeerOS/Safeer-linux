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

from . import knjiznica_kroga, media_servers, os_media, zakoniti_viri

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
                 knjiznica: Optional[knjiznica_kroga.Knjiznica] = None) -> None:
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

    # ------------------------------------------------------------------ jedro
    @property
    def mc(self) -> os_media.MediaCenter:
        with self._zaklep:
            if self._mc is None:
                # Krajevne datoteke ima na Linuxu knjiznica Medijskega centra (core/os_knjiznica.py), zato tu brez map.
                self._mc = os_media.MediaCenter(str(self.config_dir), roots=[], secret_encryptor=skrij, secret_decryptor=razkrij)
                self._mc.visina_zaslona = self.visina_zaslona
                # Film iz torrenta: branje torrenta traja - stran med tem pove, da ga pripravljamo.
                self._mc.ob_pripravi_torrenta = lambda item: self.dogodek(
                    "mediaTorrent", {"naslov": str(item.get("naslov") or "")})
            return self._mc

    def _drzava(self) -> str:
        return str(self._nastavitve().get("media_watch_country") or "auto")

    def _nastavitve(self) -> dict:
        try:
            d = json.loads((self.config_dir / "nastavitve.json").read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _shrani_nastavitve(self, d: dict) -> None:
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            (self.config_dir / "nastavitve.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    # ------------------------------------------------------------------ most
    def pozna(self, metoda: str) -> bool:
        return metoda in self.METODE

    def izvedi(self, metoda: str, a: list) -> Any:
        """Izvede metodo mostu (v delovni niti - katalog bere omrezje). Neznana metoda: KeyError."""
        return getattr(self, self.METODE[metoda])(a)

    METODE = {
        "mediaZvrsti": "_zvrsti", "mediaKatalog": "_katalog", "mediaIsciPredpomnilnik": "_isci_predpomnilnik",
        "mediaPodrobnosti": "_podrobnosti", "mediaWatchSettings": "_watch_settings", "mediaWatchCountry": "_watch_country",
        "mediaSezona": "_sezona", "mediaEpizoda": "_epizoda", "mediaFilm": "_film",
        "mediaViri": "_viri", "mediaDodajVir": "_dodaj_vir", "mediaDodajStreznik": "_dodaj_streznik",
        "mediaOdstraniVir": "_odstrani_vir", "mediaOsveziVir": "_osvezi_vir", "mediaOdkrijDlna": "_odkrij_dlna",
        "mediaSeznami": "_seznami", "mediaSeznam": "_seznam", "mediaUvoziSeznam": "_uvozi_seznam",
        "mediaOdstraniSeznam": "_odstrani_seznam", "mediaDodajNaSeznam": "_dodaj_na_seznam",
        "mediaOdstraniSSeznama": "_odstrani_s_seznama", "mediaSeznamZamenjava": "_seznam_zamenjava",
        "mediaPredvajaj": "_predvajaj_vnos", "mediaYtUkaz": "_yt_ukaz", "mediaStanje": "_stanje",
        "mediaKnjiznica": "_knjiznica_seznam", "mediaKnjiznicaPredvajaj": "_knjiznica_predvajaj",
        "mediaKnjiznicaOdstrani": "_knjiznica_odstrani",
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
            return rezultat

        return prikazi(mc.catalog_hitro(
            self._niz(a, 0), self._niz(a, 1, "vse"), self._niz(a, 2), stran,
            ob_osvezitvi=lambda _kljuc, rezultat: self.dogodek("mediaKatalogOsvezen", prikazi(rezultat)),
            razvrsti=self._niz(a, 4), izklopljeni=izklopljeni, samo_lokalno=False,
            izklopljeni_jeziki=izklopljeni_jeziki))

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
        d = self._nastavitve()
        d["media_watch_country"] = "auto" if drzava == "AUTO" else drzava
        self._shrani_nastavitve(d)
        return True

    def _sezona(self, a: list) -> Any:
        return self.mc.season(int(a[0]) if a else 0, int(a[1]) if len(a) > 1 else 1)

    def _epizoda(self, a: list) -> Any:
        return self.mc.episode_item(int(a[0]) if a else 0, int(a[1]) if len(a) > 1 else 1,
                                    int(a[2]) if len(a) > 2 else 1, self._niz(a, 3))

    def _film(self, a: list) -> Any:
        return self.mc.movie_item(int(a[0]) if a else 0, self._niz(a, 1))

    def _viri(self, _a: list) -> Any:
        return self.mc.sources()

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
            yt["igra"] = True
            self.dogodek("mediaYt", {"id": yt["id"], "igra": True})
        elif stanje == 2 and yt["igra"]:
            yt["igra"], yt["ze_igral"] = False, True
            self.dogodek("mediaYt", {"id": yt["id"], "igra": False})
        elif stanje == 0 and (yt["igra"] or yt["ze_igral"]):
            self._yt = None
            self.dogodek("mediaKonec", {"id": yt["id"]})

    def yt_zaprt(self) -> None:
        """Uporabnik je zaprl okno s skladbo: vrsta se ustavi."""
        yt, self._yt = self._yt, None
        if yt is not None:
            self.dogodek("mediaYtZaprt", {"id": yt["id"]})

    def _stanje(self, _a: list) -> dict:
        return {"na_voljo": True, "native": True, "predvajalnik": "GStreamer"}

    def _predvajaj_vnos(self, a: list) -> Optional[dict]:
        ident = self._niz(a, 0)
        item = self.mc.resolve(ident)
        if not item:
            return None
        if item.get("napaka_koda") or item.get("napaka") or item.get("sporocilo"):
            return item
        if item.get("stran") and str(item.get("url") or "") == str(item.get("stran")):
            return item       # prenos, ki ga izdajatelj ponuja samo na svoji strani: stran ga odpre v Spletu
        nacin = nacin_predvajanja(item, os_media.je_neposredni_zvok)
        self._yt = None       # nova izbira: prejsnja skladba v vgradnem predvajalniku ne sprozi vec nicesar
        # Dnevnik brez naslova vsebine: samo pot predvajanja in gostitelj (za iskanje napak, kot na Windows).
        print("[SafeerMedia] pot=%s vrsta=%s gostitelj=%s" % (nacin or "ni", item.get("vrsta") or "",
              urllib.parse.urlsplit(str(item.get("url") or "")).hostname or ""), flush=True)
        if nacin == "youtube":
            # Skladba s seznama predvajanja: vgradni predvajalnik YouTuba v lahkem medijskem pogledu.
            ident = str(item.get("id") or ident)
            naslov = naslov_za_predvajalnik(item)
            url = naslov_vgradnje(item["youtube"])
            self._yt = {"id": ident, "igra": False, "ze_igral": False}
            if not url or not self._v_glavni_pocakaj(lambda: self._youtube(url, naslov)):
                self._yt = None
                return dict(item, native=True, napaka_koda="tok")
            return dict(item, native=True, zvok=True, okno_youtube=True)
        if nacin == "neposredno":
            url = str(item.get("url") or "")
            if item.get("pot") and not url.startswith("file:"):
                url = Path(str(item["pot"])).as_uri()
            vrsta = vrsta_predvajalnika(item)
            zacetek = self.napredek_za(str(item.get("id") or ident)) if vrsta == "video" else 0
            ok = self._v_glavni_pocakaj(lambda: self._predvajaj(url, vrsta, naslov_za_predvajalnik(item), zacetek,
                                                                 podnapisi_vnosa(item), vrsta in ("video", "tv")))
            if not ok:
                return dict(item, native=True, napaka_koda="tok")
            if len(self._predvajano) > 50:
                self._predvajano.clear()
            self._predvajano[url] = {"id": str(item.get("id") or ident), "zvok": vrsta in ("medij", "radio"), "vrsta": vrsta}
            return dict(item, native=True, zvok=vrsta in ("medij", "radio"))
        if nacin == "vdelano":
            ok = self._v_glavni_pocakaj(lambda: self._vdelano(str(item.get("url") or "")))
            return dict(item, native=True) if ok else dict(item, native=True, napaka_koda="tok")
        return dict(item, napaka_koda="ni_toka")

    # ------------------------------------------------------------------ polica »Na tvojih napravah« (knjiznica kroga)
    def _knjiznica_seznam(self, _a: list) -> Any:
        return self._knjiznica.seznam() if self._knjiznica is not None else []

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
        ident = str(v.get("ref") or "") or "knjiznica:" + v["kljuc"]
        naslov = str(v.get("naslov") or "")
        self._yt = None
        print("[SafeerMedia] pot=knjiznica vrsta=%s" % (v.get("vrsta") or ""), flush=True)
        zacetek = self.napredek_za(ident)
        if not self._v_glavni_pocakaj(lambda: self._predvajaj(url, "video", naslov, zacetek, (), True)):
            return {"napaka_koda": "tok"}
        if len(self._predvajano) > 50:
            self._predvajano.clear()
        self._predvajano[url] = {"id": ident, "zvok": False, "vrsta": "video"}
        return {"id": ident, "naslov": naslov, "native": True, "zvok": False}

    def _knjiznica_odstrani(self, a: list) -> bool:
        return bool(self._knjiznica is not None and self._knjiznica.odstrani(self._niz(a, 0)))

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
        """Film ali epizoda iz kataloga: zapomnimo si, kje je uporabnik ostal (ne za zvok in prenose v zivo)."""
        vnos = self._predvajano.get(str(uri or ""))
        if not vnos or vnos.get("vrsta") != "video" or pozicija < 15 or trajanje <= 0:
            return
        d = self._napredki()
        if trajanje - pozicija < 20:        # tik pred koncem: naslednjic od zacetka
            d.pop(vnos["id"], None)
        else:
            d[vnos["id"]] = [int(pozicija), int(trajanje), int(time.time())]
        if len(d) > NAJVEC_NAPREDKOV:
            for k, _ in sorted(d.items(), key=lambda kv: kv[1][2] if isinstance(kv[1], list) and len(kv[1]) > 2 else 0)[:len(d) - NAJVEC_NAPREDKOV]:
                d.pop(k, None)
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            (self.config_dir / "napredek.json").write_text(json.dumps(d), encoding="utf-8")
        except OSError:
            pass

    def konec(self, uri: str) -> None:
        """Domaci predvajalnik je vnos odigral do konca: film pozabi napredek, skladba sprozi naslednjo iz vrste."""
        vnos = self._predvajano.get(str(uri or ""))
        if not vnos:
            return
        if vnos.get("vrsta") == "video":
            d = self._napredki()
            if d.pop(vnos["id"], None) is not None:
                try:
                    (self.config_dir / "napredek.json").write_text(json.dumps(d), encoding="utf-8")
                except OSError:
                    pass
        if vnos.get("zvok"):
            self.dogodek("mediaKonec", {"id": vnos["id"]})

    def zapri(self) -> None:
        self._yt = None
