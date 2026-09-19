"""Safeer Link v linuxovem brskalniku.

Ista stran kot na telefonu in televizorju (assets/link/), zato je vedenje povsod
enako. Stran je del programa in ne pride z omrezja; z aplikacijo se pogovarja samo
prek mostu, ki je pripet izkljucno njenemu pogledu -- nobena spletna stran ga ne vidi.

Zeton naprave ostane v ~/.config/safeer-browser/link.json (0600). Stran ga nikoli ne
dobi: vsak klic proti Hubu opravi ta modul.

WebKitGTK ne pozna sinhronicnih klicev iz strani v program, zato most sestavimo iz
dveh delov: stanje program vstavi v stran vnaprej (sinhroni bralci berejo to), dejanja
pa gredo v program prek postMessage in se vrnejo kot odziv.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gtk, WebKit2, GLib  # noqa: E402

from core import link_deljenje, link_hub, link_tls  # noqa: E402

KATEGORIJA_ZAZNAMKI = "bookmarks"

# Skripta, ki v strani naredi window.SafeerLink. Sinhroni bralci berejo stanje, ki
# ga program vstavi vnaprej; dejanja gredo v program.
MOST_JS = """
(function () {
  if (window.SafeerLink) return;
  window.__safeerLink = window.__safeerLink || {
    stanje: {"znan": false, "seznanjen": false},
    naprave: [],
    stran: {"url": "", "naslov": "", "posljiva": false},
    sinhronizacija: {"zaznamki": {"vklopljena": false, "stevilo": 0}},
    konzola: "",
    jezik: "",
    deljenje: {"tece": false, "cilj": "", "ime": "", "napaka": ""}
  };
  function poslji(metoda, argumenti) {
    try {
      window.webkit.messageHandlers.safeerLink.postMessage(
        JSON.stringify({ m: metoda, a: argumenti || [] })
      );
    } catch (e) {}
  }
  window.SafeerLink = {
    jeTelevizor: function () { return false; },
    stanje: function () { return JSON.stringify(window.__safeerLink.stanje); },
    naprave: function () { return JSON.stringify(window.__safeerLink.naprave); },
    trenutnaStranJson: function () { return JSON.stringify(window.__safeerLink.stran); },
    sinhronizacijaStanje: function () { return JSON.stringify(window.__safeerLink.sinhronizacija); },
    naslovKonzole: function () { return window.__safeerLink.konzola; },
    jezik: function () { return window.__safeerLink.jezik || ""; },
    potrdiNovNaslov: function () { poslji("potrdiNovNaslov"); },
    pozabiNapravo: function () { poslji("pozabiNapravo"); },
    poisciHub: function () { poslji("poisciHub"); },
    seznani: function () { poslji("seznani"); },
    potrdiKodo: function (koda) { poslji("potrdiKodo", [String(koda || "")]); },
    prekiniSeznanitev: function () { poslji("prekiniSeznanitev"); },
    poveziSe: function () { poslji("poveziSe"); },
    posljiTrenutno: function (id) { poslji("posljiTrenutno", [id]); },
    poslji: function (id, url, naslov) { poslji("poslji", [id, url, naslov]); },
    nadzor: function (id, ukaz, vrednost) { poslji("nadzor", [id, ukaz, vrednost]); },
    ukaz: function (id, dejanje, parametri, ref) { poslji("ukaz", [id, dejanje, String(parametri || "{}"), String(ref || "")]); },
    dodajDeljenoMapo: function () { poslji("dodajDeljenoMapo", []); },
    odstraniDeljenoMapo: function (i) { poslji("odstraniDeljenoMapo", [i]); },
    deliStandardneMape: function () { poslji("deliStandardneMape", []); },
    znaGovor: function () { return false; },
    lahkoVOspredje: function () { return true; },
    dovoliOspredje: function () {},
    poslusaj: function (jezik) {},
    nehajPoslusati: function () {},
    posljiBesedilo: function (id, besedilo) { poslji("posljiBesedilo", [id, String(besedilo || "")]); },
    izberiDatoteko: function (id) { poslji("izberiDatoteko", [id]); },
    zacniDeljenjeZaslona: function (id, ime) { poslji("zacniDeljenjeZaslona", [id, String(ime || "")]); },
    koncajDeljenjeZaslona: function () { poslji("koncajDeljenjeZaslona"); },
    deljenjeZaslonaStanje: function () { return JSON.stringify(window.__safeerLink.deljenje || {tece: false}); },
    preimenujNapravo: function (id, ime) { poslji("preimenujNapravo", [id, String(ime || "")]); },
    vzdevki: function () { return JSON.stringify(window.__safeerLink.vzdevki || {}); },
    shraniVzdevek: function (id, ime) {
      var v = window.__safeerLink.vzdevki || {};
      if (ime) v[id] = String(ime); else delete v[id];
      window.__safeerLink.vzdevki = v;
      poslji("shraniVzdevek", [id, String(ime || "")]);
    },
    nastaviSinhronizacijo: function (vklop) { poslji("nastaviSinhronizacijo", [!!vklop]); },
    odpri: function (url) { poslji("odpri", [url]); },
    zapri: function () { poslji("zapri"); }
  };
})();
"""


class SafeerLink:
    """Okno Safeer Linka in ves pogovor s Hubom."""

    def __init__(self, starsevsko: Optional[Gtk.Window], config,
                 trenutna_stran: Callable[[], Dict[str, str]],
                 odpri_naslov: Callable[[str], None],
                 koren_programa: str,
                 dovoli_potrdilo: Optional[Callable[[str, str], None]] = None,
                 nastavitve: Optional[link_hub.Nastavitve] = None,
                 identiteta: Optional[Tuple[str, str]] = None,
                 control: bool = False,
                 ob_zaprtju: Optional[Callable[[], None]] = None) -> None:
        self.starsevsko = starsevsko
        # Safeer Control: ista stran in isti Link, a brez brskalnika (svoja identiteta in shramba,
        # okno je glavno okno programa, prejete strani odpre sistemski brskalnik).
        self.control = control
        self.ob_zaprtju = ob_zaprtju
        self._identiteta = identiteta
        self.config = config
        self.trenutna_stran = trenutna_stran
        self.odpri_naslov = odpri_naslov
        self.koren = koren_programa
        # Brskalnik naj Hubovo samopodpisano potrdilo sprejme za stran gledalca zaslona
        # (pem, gostitelj). Brez tega WebKit stran s Huba zavrne.
        self.dovoli_potrdilo = dovoli_potrdilo
        self.deljenje_zaslona: Optional[link_deljenje.DeljenjeZaslona] = None
        # Safeer Control: deljene mape za televizor (core/link_datoteke.Datoteke); brskalnik jih nima.
        self.datoteke = None
        self.programi = None
        self.zaslon = None

        self.nastavitve = nastavitve if nastavitve is not None else link_hub.Nastavitve()
        self.povezava: Optional[link_hub.Povezava] = None
        self.naprave: List[dict] = []
        self.okno: Optional[Gtk.Window] = None
        self.pogled: Optional[WebKit2.WebView] = None
        self._seznanjanje = False
        # Odprta prijava na Hubu (pair_id, hub_id, odtis); caka na vnos kode.
        self._prijava: Optional[dict] = None
        # Naslov, ki se je javil namesto potrjenega; caka na en uporabnikov dotik.
        self._predlagani_naslov = ""
        # Da iskanje po neuspeli povezavi ne tece v krogu.
        self._po_neuspehu = False
        # Povezovanje sprozi vec poti (nalozena stran, iskanje, seznanitev,
        # vklop sinhronizacije). Brez kljucavnice nastaneta dve povezavi hkrati
        # in Hub vidi napravo dvakrat.
        self._zaklep_povezave = threading.Lock()
        self._dovoljeni_koren = ""
        # Kdor Link gosti brez okna (Safeer Control v pladnju), zeli vedeti, ali je povezan.
        self.ob_povezavi: Optional[Callable[[bool], None]] = None

    # ------------------------------------------------------------------
    # Stanje
    # ------------------------------------------------------------------

    def _hub(self) -> str:
        return str(self.nastavitve.get("hub_url", "") or "")

    def _id(self) -> str:
        return self._identiteta[0] if self._identiteta else link_hub.id_naprave()

    def _ime(self) -> str:
        if self._identiteta:
            return self._identiteta[1]
        return "Safeer (" + link_hub._ime_naprave().split(".")[0] + ")"

    def _zeton(self) -> Optional[str]:
        z = self.nastavitve.get("control_token")
        return z if isinstance(z, str) and z else None

    def _odtis(self) -> Optional[str]:
        """Odtis Hubovega potrdila, pripet ob seznanitvi. Brez njega se ne povezemo."""
        o = self.nastavitve.get("hub_fp")
        return o if isinstance(o, str) and o else None

    def _stanje(self) -> dict:
        return {
            "hub": self._hub(),
            "znan": bool(self._hub()),
            # Seznanjena je naprava z zetonom IN odtisom Hubovega potrdila; stara
            # seznanitev brez odtisa (pred TLS) ne velja vec - stran ponudi novo.
            "seznanjen": self._zeton() is not None and self._odtis() is not None,
            "naprava": self._ime(),
            "id": self._id(),
            "control": self.control,
            "deljeneMape": self._deljene_mape(),
            "standardneDeljene": self._standardne_deljene(),
        }

    def _deljene_mape(self) -> list:
        """Deljene mape za stran: ime in pot (stran pot le izpise, nikamor je ne poslje)."""
        if self.datoteke is None:
            return []
        dom = os.path.expanduser("~")
        return [{"ime": os.path.basename(p) or p, "pot": ("~" + p[len(dom):]) if p.startswith(dom + os.sep) else p}
                for p in self.datoteke.poti()]

    @staticmethod
    def _standardne_mape() -> List[str]:
        """Videi, Glasba, Slike tega uporabnika (XDG), kolikor jih obstaja."""
        mape = []
        for vrsta in (GLib.UserDirectory.DIRECTORY_VIDEOS, GLib.UserDirectory.DIRECTORY_MUSIC,
                      GLib.UserDirectory.DIRECTORY_PICTURES):
            try:
                p = GLib.get_user_special_dir(vrsta)
            except Exception:
                p = None
            if p and os.path.isdir(p) and os.path.realpath(p) != os.path.realpath(os.path.expanduser("~")):
                mape.append(p)
        return mape

    def _standardne_deljene(self) -> bool:
        if self.datoteke is None:
            return True
        std = [os.path.realpath(p) for p in self._standardne_mape()]
        return not std or all(p in self.datoteke.poti() for p in std)

    def _odziv_mape(self) -> None:
        self._odziv("deljeneMape", {"mape": self._deljene_mape(), "standardne": self._standardne_deljene()})

    def _deli_standardne_mape(self) -> None:
        if self.datoteke is None:
            return
        self.datoteke.nastavi(self.datoteke.poti() + self._standardne_mape())
        self._odziv_mape()

    def _sinhronizacija(self) -> dict:
        try:
            portali = self.config.get_portals() or []
        except Exception:
            portali = []
        return {
            "zaznamki": {
                "vklopljena": bool(self.nastavitve.get("sync_bookmarks", False)),
                "stevilo": len(portali),
            }
        }

    def _stran(self) -> dict:
        try:
            podatki = self.trenutna_stran() or {}
        except Exception:
            podatki = {}
        url = str(podatki.get("url", "") or "")
        posljiva = url.startswith("http://") or url.startswith("https://")
        return {"url": url, "naslov": str(podatki.get("naslov", "") or ""), "posljiva": posljiva}

    def _jezik(self) -> str:
        """Jezik, ki ga ima uporabnik v brskalniku -- stran govori v njem.

        Najprej vprasamo brskalnikovo nastavitev, sicer okolje (LANG). Vrnemo samo
        dvocrkovno oznako; stran zna slovensko in anglesko, drugo pade na anglesko.
        """
        oznaka = ""
        try:
            oznaka = str(self.config.get("ui_language", "") or "")
        except Exception:
            oznaka = ""
        if not oznaka:
            for kljuc in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
                vrednost = os.environ.get(kljuc, "")
                if vrednost:
                    oznaka = vrednost
                    break
        oznaka = oznaka.replace("-", "_").split(".")[0].split("_")[0].strip().lower()
        return oznaka[:2]

    def _konzola(self) -> str:
        hub = self._hub()
        if not hub:
            return ""
        return link_hub._osnova(hub) + "/console"

    # ------------------------------------------------------------------
    # Okno
    # ------------------------------------------------------------------

    def pokazi(self) -> None:
        if self.okno is not None:
            self.okno.present()
            return

        upravitelj = WebKit2.UserContentManager()
        upravitelj.register_script_message_handler("safeerLink")
        upravitelj.connect("script-message-received::safeerLink", self._na_sporocilo)
        upravitelj.add_script(WebKit2.UserScript(
            MOST_JS,
            WebKit2.UserContentInjectedFrames.TOP_FRAME,
            WebKit2.UserScriptInjectionTime.START,
            None, None,
        ))

        pogled = WebKit2.WebView.new_with_user_content_manager(upravitelj)
        nastavitve = pogled.get_settings()
        nastavitve.set_property("enable-javascript", True)
        nastavitve.set_property("enable-developer-extras", False)
        # Stran je nasa in ne potrebuje omrezja; vse gre skozi most.
        nastavitve.set_property("enable-webgl", False)
        pogled.set_background_color(_barva(0x0b, 0x10, 0x17))

        okno = Gtk.Window(title="Safeer Control" if self.control else "Safeer Link")
        okno.set_default_size(560, 760 if not self.control else 820)
        if self.control:
            okno.set_wmclass("safeer-control", "Safeer Control")
            okno.set_icon_name("safeer-control")
        if self.starsevsko is not None:
            okno.set_transient_for(self.starsevsko)
        okno.add(pogled)
        okno.connect("destroy", self._na_zaprtje)

        self.okno = okno
        self.pogled = pogled

        pot = os.path.join(self.koren, "assets", "link", "index.html")
        self._dovoljeni_koren = "file://" + os.path.join(self.koren, "assets", "link")
        pogled.connect("decide-policy", self._na_politiko)
        pogled.load_uri("file://" + pot)
        pogled.connect("load-changed", self._na_nalozeno)

        okno.show_all()

    def _na_politiko(self, pogled, odlocitev, vrsta) -> bool:
        """Ta pogled sme prikazati samo stran Safeer Linka.

        Most je pripet pogledu, ne dokumentu: ce bi pogled kdaj odplul na spletno
        stran, bi `window.SafeerLink` dobila tudi ona. Danes stran nikamor ne vodi,
        a varovalo mora biti tu, preden ga bo kdo potreboval -- Android ga ze ima.
        """
        try:
            if vrsta not in (WebKit2.PolicyDecisionType.NAVIGATION_ACTION,
                             WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
                return False
            naslov = odlocitev.get_navigation_action().get_request().get_uri() or ""
            if self._dovoljeni_koren and naslov.startswith(self._dovoljeni_koren):
                return False
            odlocitev.ignore()
            return True
        except Exception:
            try:
                odlocitev.ignore()
            except Exception:
                pass
            return True

    def _na_zaprtje(self, *_args) -> None:
        # Okno se zapre, povezava s Hubom pa ostane: racunalnik sprejema besedila, datoteke
        # in zaslon tudi, ko Safeer Link ni odprt - kot telefon s storitvijo.
        self.okno = None
        self.pogled = None
        if self.ob_zaprtju is not None:
            try:
                self.ob_zaprtju()
            except Exception:
                pass

    def povezi_v_ozadju(self) -> None:
        """Ob zagonu brskalnika: ce je racunalnik seznanjen, se poveze brez okna."""
        if self._hub() and self._zeton() and self._odtis():
            self._v_ozadju(self._povezi)

    def _na_nalozeno(self, pogled, dogodek) -> None:
        if dogodek != WebKit2.LoadEvent.FINISHED:
            return
        # Stran je svoje prvo stanje prebrala ze ob DOMContentLoaded (pred tem vstavkom): povemo ji,
        # naj ga prebere znova, sicer do prvega dogodka kaze »ni nastavljeno«.
        self._odziv("stanje", None)
        # Ce Huba se ne poznamo, ga poiscemo sami -- uporabniku ni treba nicesar vedeti.
        if not self._hub():
            self._v_ozadju(self._poisci_hub)
        elif self._zeton():
            self._v_ozadju(self._povezi)

    # ------------------------------------------------------------------
    # Most
    # ------------------------------------------------------------------

    def _js(self, koda: str) -> None:
        pogled = self.pogled
        if pogled is None:
            return
        try:
            pogled.run_javascript(koda, None, None, None)
        except Exception:
            pass

    def _osvezi_stanje_v_strani(self) -> None:
        stanje = {
            "stanje": self._stanje(),
            "naprave": self.naprave,
            "stran": self._stran(),
            "sinhronizacija": self._sinhronizacija(),
            "konzola": self._konzola(),
            "jezik": self._jezik(),
            "deljenje": self._deljenje_stanje(),
            "vzdevki": self._vzdevki(),
        }
        # ensure_ascii=True: imena naprav pridejo z omrezja, U+2028/U+2029 pa sta
        # v JavaScriptu ločilnika vrstic. Ubezimo vsemu, kar ni ASCII.
        self._js("window.__safeerLink = " + json.dumps(stanje, ensure_ascii=True) + ";")

    def _odziv(self, vrsta: str, podatki) -> None:
        """Odziv strani. Vedno na glavni niti in vedno po osvezitvi stanja."""
        def naredi():
            self._osvezi_stanje_v_strani()
            self._js("window.safeerLinkOdziv && window.safeerLinkOdziv("
                     + json.dumps(vrsta) + ", " + json.dumps(podatki, ensure_ascii=True) + ");")
            return False
        GLib.idle_add(naredi)

    def _na_sporocilo(self, upravitelj, rezultat) -> None:
        try:
            besedilo = rezultat.get_js_value().to_string()
            sporocilo = json.loads(besedilo)
        except Exception:
            return
        metoda = sporocilo.get("m")
        argumenti = sporocilo.get("a") or []
        obravnava = {
            "poisciHub": lambda: self._v_ozadju(self._poisci_hub),
            "seznani": lambda: self._v_ozadju(self._seznani),
            "potrdiKodo": lambda: self._v_ozadju(
                lambda: self._potrdi_kodo(str(argumenti[0]) if argumenti else "")),
            "prekiniSeznanitev": lambda: self._prekini_seznanitev(),
            "poveziSe": lambda: self._v_ozadju(self._povezi),
            "posljiTrenutno": lambda: self._poslji_trenutno(*argumenti[:1]),
            "poslji": lambda: self._poslji(*argumenti[:3]),
            "nadzor": lambda: self._nadzor(*argumenti[:3]),
            "ukaz": lambda: self._ukaz(*argumenti[:4]),
            "nastaviSinhronizacijo": lambda: self._v_ozadju(
                lambda: self._nastavi_sinhronizacijo(bool(argumenti[0]) if argumenti else False)),
            "odpri": lambda: self._odpri(*argumenti[:1]),
            "posljiBesedilo": lambda: self._v_ozadju(lambda: self._poslji_besedilo(*argumenti[:2])),
            "izberiDatoteko": lambda: self._izberi_datoteko(*argumenti[:1]),
            "zacniDeljenjeZaslona": lambda: self._v_ozadju(lambda: self._zacni_deljenje_zaslona(*argumenti[:2])),
            "koncajDeljenjeZaslona": lambda: self._koncaj_deljenje_zaslona(),
            "preimenujNapravo": lambda: self._v_ozadju(lambda: self._preimenuj_napravo(*argumenti[:2])),
            "shraniVzdevek": lambda: self._shrani_vzdevek(*argumenti[:2]),
            "pozabiNapravo": lambda: self._v_ozadju(self._pozabi_napravo),
            "potrdiNovNaslov": lambda: self._v_ozadju(self._potrdi_nov_naslov),
            "dodajDeljenoMapo": lambda: self._dodaj_deljeno_mapo(),
            "odstraniDeljenoMapo": lambda: self._odstrani_deljeno_mapo(argumenti[0] if argumenti else -1),
            "deliStandardneMape": lambda: self._deli_standardne_mape(),
            "zapri": lambda: self.okno.destroy() if self.okno is not None else None,
        }.get(metoda)
        if obravnava is not None:
            try:
                obravnava()
            except Exception as e:  # noqa: BLE001 - stran ne sme podreti brskalnika
                self._odziv("napaka", str(e))

    # Krajevna imena naprav: uporabnik tega racunalnika poimenuje druge naprave po svoje;
    # imena ostanejo tu (nastavitve), ne na Safeer Linku, zato prezivijo zamenjavo gostitelja.
    def _vzdevki(self) -> dict:
        try:
            v = self.config.get("link_vzdevki", {}) or {}
            return v if isinstance(v, dict) else {}
        except Exception:
            return {}

    def _shrani_vzdevek(self, id_naprave: str = "", ime: str = "") -> None:
        if not id_naprave:
            return
        v = dict(self._vzdevki())
        cisto = str(ime or "").strip()[:64]
        if cisto:
            v[str(id_naprave)] = cisto
        else:
            v.pop(str(id_naprave), None)
        try:
            self.config.set("link_vzdevki", v)
        except Exception as e:  # noqa: BLE001
            print(f"[SafeerLink] Vzdevka ni bilo mogoče shraniti: {e}")

    @staticmethod
    def _v_ozadju(funkcija: Callable[[], None]) -> None:
        threading.Thread(target=funkcija, daemon=True).start()

    # ------------------------------------------------------------------
    # Dejanja
    # ------------------------------------------------------------------

    def _potrdi_nov_naslov(self) -> None:
        """Uporabnik je potrdil, da je Safeer Link na novem naslovu res njegov."""
        naslov = self._predlagani_naslov
        self._predlagani_naslov = ""
        if not naslov:
            return
        self.nastavitve.set("hub_url", naslov)
        self._odziv("hub", {"najden": True, "naslov": naslov})
        if self._zeton():
            self._povezi()

    def _pozabi_napravo(self) -> None:
        """Odklopi TO napravo od Huba: pozabi zeton in naslov.

        Namenoma ne posegamo v druge naprave -- to je uporabnikova odlocitev za
        napravo, ki jo drzi v roki. Ostale se odstrani v Safeer Controlu.
        """
        povezava = self.povezava
        self.povezava = None
        if povezava is not None:
            try:
                povezava.zapri()
            except Exception:
                pass
        for kljuc in ("control_token", "hub_url", "hub_fp", "seznanitve", "sync_bookmarks",
                      "sync_bookmarks_version"):
            try:
                self.nastavitve.podatki.pop(kljuc, None)
            except Exception:
                pass
        self.nastavitve.shrani()
        self._odziv("pozabljeno", True)

    def _seznanitve(self) -> dict:
        """Seznanitve po Hubih: odtis potrdila -> {token, hub_url}. V hisi je lahko vec sredisc
        (televizor, telefon, racunalnik); ko eno ugasne, se povezemo na drugo brez nove kode."""
        s = self.nastavitve.get("seznanitve")
        return s if isinstance(s, dict) else {}

    def _zapomni_seznanitev(self) -> None:
        if self._zeton() and self._odtis():
            s = self._seznanitve()
            s[self._odtis()] = {"token": self._zeton(), "hub_url": self._hub()}
            self.nastavitve.podatki["seznanitve"] = s

    def _poisci_hub(self) -> None:
        znani = self._hub()
        najden = link_hub.poisci_hub_z_odtisom(znani, self._odtis())
        if not najden:
            self._odziv("hub", {"najden": False, "naslov": ""})
            return
        naslov, fp = najden["naslov"], najden.get("fp") or ""
        if najden.get("isti"):
            # Isti Hub (isti naslov ali isti odtis na novem naslovu): naslov posodobimo, zeton velja.
            self.nastavitve.set("hub_url", naslov)
            self._odziv("hub", {"najden": True, "naslov": naslov})
            if self._zeton():
                self._povezi()
            return
        # Drug Hub. Trenutno seznanitev shranimo, morebitno prejsnjo s tem Hubom pa vrnemo -
        # sicer se uporabnik seznani s tem Hubom s kodo, kot vedno.
        self._zapomni_seznanitev()
        znana = self._seznanitve().get(fp) if fp else None
        self.nastavitve.podatki["hub_url"] = naslov
        if znana and znana.get("token"):
            self.nastavitve.podatki["control_token"] = znana["token"]
            self.nastavitve.podatki["hub_fp"] = fp
        else:
            self.nastavitve.podatki.pop("control_token", None)
            self.nastavitve.podatki.pop("hub_fp", None)
        self.nastavitve.shrani()
        self._odziv("hub", {"najden": True, "naslov": naslov})
        if self._zeton():
            self._povezi()

    def _seznani(self) -> None:
        if self._seznanjanje:
            return
        naslov = self._hub()
        if not naslov:
            self._odziv("napaka", "Hub ni znan. Najprej ga poišči.")
            return
        self._seznanjanje = True
        self._prijava = None
        try:
            zacetek = link_hub.zacni_seznanitev(
                naslov, self._id(), self._ime())
            if not zacetek:
                self._odziv("napaka", {"koda": "seznanitev_ni_stekla",
                                       "sporocilo": "Seznanitve ni bilo mogoče začeti."})
                return
            if zacetek.get("napaka"):
                # Hub brez TLS ali s starim postopkom bi kodo prejel po omrezju.
                self._odziv("napaka", {"koda": "hub_star",
                                       "sporocilo": "Safeer na gostitelju je prestar za varno "
                                                    "seznanitev. Posodobi ga."})
                return
            # Kodo pokaze gostitelj; stran ponudi vnos, ki pride v _potrdi_kodo.
            self._prijava = zacetek
            self._odziv("nacin", {"nacin": "koda_na_gostitelju", "koda": ""})
        finally:
            self._seznanjanje = False

    def _potrdi_kodo(self, koda: str) -> None:
        """Uporabnik je vtipkal kodo z gostiteljevega zaslona. Koda ne gre po omrezju:
        Hubu jo dokazemo s SPAKE2, ob uspehu si zapomnimo zeton in odtis potrdila."""
        prijava = self._prijava
        naslov = self._hub()
        if not prijava or not naslov:
            self._odziv("kodaNiSprejeta", {"razlog": "prijava_ne_obstaja"})
            return
        zeton, razlog = link_hub.potrdi_kodo(naslov, prijava, self._id(), koda)
        if not zeton:
            if razlog in ("prevec_poskusov", "prijava_ne_obstaja"):
                self._prijava = None
            self._odziv("kodaNiSprejeta", {"razlog": razlog or "napacna_koda"})
            return
        self._prijava = None
        self.nastavitve.podatki["control_token"] = zeton
        self.nastavitve.podatki["hub_fp"] = str(prijava.get("odtis", ""))
        self._zapomni_seznanitev()
        self.nastavitve.shrani()
        self._odziv("seznanitev", True)
        self._povezi()

    def _prekini_seznanitev(self) -> None:
        self._prijava = None

    def _povezi(self) -> None:
        with self._zaklep_povezave:
            uspelo = self._povezi_zaklenjeno()
        if uspelo or self._po_neuspehu:
            return
        # Znani naslov se ne oglasi. Preden uporabniku karkoli recemo, poglejmo, ali
        # se Safeer Link javlja kje drugje -- najpogosteje je dobil nov naslov od
        # usmerjevalnika. Sele ce ga ni nikjer, je to zares napaka.
        self._po_neuspehu = True
        try:
            self._poisci_hub()
        finally:
            self._po_neuspehu = False

    def _povezi_zaklenjeno(self) -> bool:
        naslov = self._hub()
        zeton = self._zeton()
        if not naslov or not zeton or not self._odtis():
            return True  # ni kaj povezati; to ni neuspeh, ki bi ga bilo treba iskati
        if self.povezava is not None:
            self.povezava.zapri()
            self.povezava = None

        povezava = link_hub.Povezava(
            naslov, zeton, self._id(), self._ime(),
            sinhronizira=bool(self.nastavitve.get("sync_bookmarks", False)),
            odtis=self._odtis(),
            dodatne_zmoznosti=(["files"] if self.datoteke is not None else [])
            + (["apps"] if self.programi is not None and self.programi.vklopljeno else [])
            + (["desktop"] if self.zaslon is not None and self.zaslon.na_voljo().get("dovoljeno") else []),
        )
        povezava.ob_sporocilu = self._na_sporocilo_huba
        povezava.ob_stanju = self._na_stanje_povezave
        if povezava.poveži():
            self.povezava = povezava
            return True
        if povezava.zavrnjena:
            # Sredisce te naprave ne pozna vec (ponastavitev, odstranitev): stara seznanitev
            # ne velja, stran ponudi novo s kodo - namesto vecnega »Povezujem …«.
            self._pozabi_zeton()
            self._odziv("stanje", None)
            self._odziv("napaka", {"koda": "naprava_ni_znana",
                                   "sporocilo": "Safeer Link te naprave ne pozna več. Poveži jo znova."})
            return True  # iskanje drugih sredisc tu ne pomaga
        return False

    def _pozabi_zeton(self) -> None:
        """Zeton in odtis odpadeta, naslov sredisca ostane - nova seznanitev gre tja."""
        s = self._seznanitve()
        s.pop(self._odtis() or "", None)
        self.nastavitve.podatki["seznanitve"] = s
        for kljuc in ("control_token", "hub_fp"):
            self.nastavitve.podatki.pop(kljuc, None)
        self.nastavitve.shrani()

    def _na_stanje_povezave(self, povezan: bool) -> None:
        self._odziv("povezava", povezan)
        if self.ob_povezavi is not None:
            try:
                self.ob_povezavi(povezan)
            except Exception:
                pass
        if povezan:
            return
        # Sredisce je ugasnilo ali dobilo nov naslov. Cez nekaj sekund pogledamo, ali se
        # Safeer Link javlja kje drugje - npr. telefon prevzame, ko televizor ugasne. Ce je
        # bila ta naprava z njim ze seznanjena, se poveze brez nove kode.

        def preveri() -> None:
            p = self.povezava
            if p is not None and p.tece:
                return
            zdaj = time.time()
            if zdaj - getattr(self, "_zadnje_iskanje", 0.0) < 30:
                return
            self._zadnje_iskanje = zdaj
            self._v_ozadju(self._poisci_hub)

        threading.Timer(8.0, preveri).start()

    def _na_sporocilo_huba(self, sporocilo: dict) -> None:
        vrsta = sporocilo.get("type")
        if vrsta == "cast.devices":
            naprave = []
            for d in sporocilo.get("devices") or []:
                naprave.append({
                    "id": d.get("id", ""),
                    "ime": d.get("name", ""),
                    "vloga": d.get("role", "receiver"),
                    "zmoznosti": d.get("capabilities") or [],
                    "naslov": d.get("ip") or "",
                })
            self.naprave = naprave
            self._odziv("naprave", naprave)
        elif vrsta == "cast.status":
            telo = sporocilo.get("payload") or {}
            self._odziv("predvajanje", {
                "naprava": sporocilo.get("device_id", ""),
                "stanje": telo.get("state", "idle"),
                "naslov": telo.get("title", ""),
                "url": telo.get("current_url", ""),
                "polozaj": telo.get("position", 0.0),
                "trajanje": telo.get("duration", 0.0),
            })
        elif vrsta == "sync.data":
            self._prejmi_zaznamke(sporocilo.get("payload") or {})
        elif vrsta in ("share.text", "share.file", "share.screen"):
            self._prejmi_deljenje(vrsta, sporocilo)
        elif vrsta == "cast.url":
            # Stran s televizorja ali druge naprave: odpremo jo v novem zavihku.
            self._prejmi_stran(sporocilo)
        elif vrsta == "control.command":
            # Daljinec Safeer Controla: ukaz izvede brskalnik, odgovor gre nazaj posiljatelju.
            self._prejmi_ukaz(sporocilo)
        elif vrsta in ("control.result", "control.ack"):
            self._ukaz_odziv(sporocilo)

    def _prejmi_ukaz(self, sporocilo: dict) -> None:
        from core import link_daljinec
        posiljatelj = str(sporocilo.get("sender", "") or "")
        ref_id = str(sporocilo.get("id", "") or "")
        telo = sporocilo.get("payload") or {}
        dejanje = str(telo.get("action", "") or "")
        parametri = telo.get("params") if isinstance(telo.get("params"), dict) else telo

        def koncaj(izid: dict) -> None:
            povezava = self.povezava
            if povezava is not None and posiljatelj:
                try:
                    povezava.poslji(link_daljinec.sporocilo_izida(posiljatelj, ref_id, dejanje, izid))
                except Exception as e:  # noqa: BLE001
                    print(f"[SafeerLink] Odgovora na ukaz ni bilo mogoče poslati: {e}")

        def izvedi() -> bool:
            if self.control:
                link_daljinec.izvedi_control(dejanje, parametri, self.odpri_naslov, koncaj,
                                             datoteke=self.datoteke, posiljatelj=posiljatelj, hub_url=self._hub(),
                                             programi=self.programi, zaslon=self.zaslon)
                return False
            if self.starsevsko is None:
                koncaj(link_daljinec.izid(False, "Brskalnik ni odprt"))
                return False
            link_daljinec.izvedi(self.starsevsko, dejanje, parametri, self.odpri_naslov, koncaj)
            return False
        GLib.idle_add(izvedi)

    # ------------------------------------------------------------------
    # Deljenje: sprejem
    # ------------------------------------------------------------------

    def _prejmi_stran(self, sporocilo: dict) -> None:
        od = str(sporocilo.get("sender_name") or sporocilo.get("sender") or "naprava")
        telo = sporocilo.get("payload") or {}
        url = str(telo.get("url", "") or "").strip()
        sprejeto = url.startswith("http://") or url.startswith("https://")
        povezava = self.povezava
        if povezava is not None:
            try:
                povezava.poslji({
                    "id": str(int(time.time() * 1000)),
                    "type": "cast.ack",
                    "ref_id": str(sporocilo.get("id", "") or ""),
                    "status": "accepted" if sprejeto else "rejected",
                })
            except Exception:
                pass
        if not sprejeto:
            return
        self._odziv("prejeto", {"vrsta": "stran", "od": od, "url": url, "naslov": str(telo.get("title", "") or "")})

        def odpri():
            try:
                self.odpri_naslov(url)
            except Exception as e:  # noqa: BLE001
                print(f"[SafeerLink] Strani ni bilo mogoče odpreti: {e}")
            return False
        GLib.idle_add(odpri)

    def _prejmi_deljenje(self, vrsta: str, sporocilo: dict) -> None:
        od = str(sporocilo.get("sender_name") or sporocilo.get("sender") or "naprava")
        telo = sporocilo.get("payload") or {}
        if vrsta == "share.text":
            besedilo = str(telo.get("text", "") or "")
            self._odziv("prejeto", {"vrsta": "besedilo", "od": od, "besedilo": besedilo})
            GLib.idle_add(self._pokazi_besedilo, od, besedilo)
        elif vrsta == "share.screen":
            dejanje = str(telo.get("action", "") or "")
            if dejanje == "start":
                pot = str(telo.get("path", "") or "")
                url = (link_hub._osnova(self._hub()) + pot) if pot.startswith("/") else str(telo.get("url", "") or "")
                if url:
                    self._v_ozadju(lambda: self._odpri_zaslon_s_huba(url))
            self._odziv("prejeto", {"vrsta": "zaslon", "od": od, "dejanje": dejanje})
        elif vrsta == "share.file":
            ime = str(telo.get("name", "") or "datoteka")
            pot = str(telo.get("path", "") or "")
            odtis = str(telo.get("sha256", "") or "")
            if not pot:
                return
            def prenesi():
                cilj, razlog = link_deljenje.prevzemi_datoteko(self._hub(), self._odtis() or "", pot, ime, odtis)
                if cilj:
                    self._odziv("prejeto", {"vrsta": "datoteka", "od": od, "ime": os.path.basename(cilj),
                                            "mapa": os.path.dirname(cilj)})
                    GLib.idle_add(self._obvesti, "📁 " + od, f"Datoteka {os.path.basename(cilj)} je v mapi {os.path.dirname(cilj)}.")
                else:
                    GLib.idle_add(self._obvesti, "📁 " + od, f"Datoteke {ime} ni bilo mogoče prevzeti: {razlog}")
            self._v_ozadju(prenesi)

    def _odpri_zaslon_s_huba(self, url: str) -> None:
        """Stran gledalca prihaja s Huba (https, samopodpisano): brskalniku najprej povemo, da
        temu potrdilu - in samo temu - zaupa, potem odpremo zavihek."""
        try:
            from urllib.parse import urlparse
            gostitelj = urlparse(url).hostname or ""
            if self.dovoli_potrdilo is not None:
                pem = link_tls.potrdilo_pem(self._hub(), self._odtis() or "")
                if pem:
                    GLib.idle_add(lambda: (self.dovoli_potrdilo(pem, gostitelj), False)[1])
        except Exception as e:  # noqa: BLE001
            print(f"[SafeerLink] Potrdila Huba ni bilo mogoče dovoliti: {e}")
        def odpri():
            try:
                self.odpri_naslov(url)
            except Exception as e:  # noqa: BLE001
                print(f"[SafeerLink] Zaslona ni bilo mogoče odpreti: {e}")
            return False
        GLib.idle_add(odpri)

    def _pokazi_besedilo(self, od: str, besedilo: str) -> bool:
        try:
            cisto = besedilo.strip()
            je_povezava = (cisto.startswith("http://") or cisto.startswith("https://")) and " " not in cisto
            okno = Gtk.MessageDialog(transient_for=self.starsevsko, modal=False,
                                     message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.NONE,
                                     text="💬 " + od)
            okno.format_secondary_text(besedilo[:4000])
            okno.add_button("Kopiraj", 1)
            if je_povezava:
                okno.add_button("Odpri", 2)
            okno.add_button("V redu", Gtk.ResponseType.OK)
            def odgovor(d, r):
                if r == 1:
                    try:
                        from gi.repository import Gdk
                        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(besedilo, -1)
                    except Exception:
                        pass
                elif r == 2:
                    try:
                        self.odpri_naslov(cisto)
                    except Exception:
                        pass
                d.destroy()
            okno.connect("response", odgovor)
            okno.show_all()
        except Exception as e:  # noqa: BLE001
            print(f"[SafeerLink] Besedila ni bilo mogoče pokazati: {e}")
        return False

    def _obvesti(self, naslov: str, besedilo: str) -> bool:
        try:
            okno = Gtk.MessageDialog(transient_for=self.starsevsko, modal=False,
                                     message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK, text=naslov)
            okno.format_secondary_text(besedilo)
            okno.connect("response", lambda d, r: d.destroy())
            okno.show_all()
        except Exception:
            pass
        return False

    # ------------------------------------------------------------------
    # Deljenje: posiljanje
    # ------------------------------------------------------------------

    def _deljenje_stanje(self) -> dict:
        d = self.deljenje_zaslona
        if d is None:
            return {"tece": False, "cilj": "", "ime": "", "napaka": ""}
        return d.stanje()

    def _deljenje(self, vrsta: str, stanje: str, cilj: str, ime: str = "", sporocilo: str = "",
                  odstotek: int = -1, koda: str = "", zasedena_od: str = "") -> None:
        podatki = {"vrsta": vrsta, "stanje": stanje, "cilj": cilj, "ime": ime, "sporocilo": sporocilo,
                   "koda": koda, "zasedenaOd": zasedena_od}
        if odstotek >= 0:
            podatki["odstotek"] = odstotek
        self._odziv("deljenje", podatki)

    def _poslji_besedilo(self, id_naprave: str = "", besedilo: str = "") -> None:
        cisto = (besedilo or "").strip()
        if not cisto:
            return
        if not (self._hub() and self._zeton() and self._odtis()):
            self._odziv("napaka", {"koda": "hub_ni_znan", "sporocilo": "Hub ni znan."})
            return
        self._deljenje("besedilo", "posiljam", id_naprave)
        ok, n = link_deljenje.poslji_besedilo(self._hub(), self._zeton() or "", self._odtis() or "",
                                              self._id(), id_naprave, cisto)
        if ok:
            self._deljenje("besedilo", "poslano", id_naprave)
        else:
            self._deljenje("besedilo", "napaka", id_naprave, sporocilo=n["sporocilo"], koda=n["koda"], zasedena_od=n["zasedenaOd"])

    def _izberi_datoteko(self, id_naprave: str = "") -> None:
        if not (self._hub() and self._zeton() and self._odtis()):
            self._odziv("napaka", {"koda": "hub_ni_znan", "sporocilo": "Hub ni znan."})
            return
        okno = Gtk.FileChooserDialog(title="Pošlji datoteko — Safeer Link", transient_for=self.okno or self.starsevsko,
                                     action=Gtk.FileChooserAction.OPEN)
        okno.add_button("Prekliči", Gtk.ResponseType.CANCEL)
        okno.add_button("Pošlji", Gtk.ResponseType.OK)
        def odgovor(d, r):
            pot = d.get_filename() if r == Gtk.ResponseType.OK else None
            d.destroy()
            if pot:
                self._v_ozadju(lambda: self._poslji_datoteko(id_naprave, pot))
        okno.connect("response", odgovor)
        okno.show()

    # Deljene mape (Safeer Control): stran pokaze seznam, uporabnik doda ali odstrani mapo.
    def dodaj_deljeno_mapo(self, starsevsko: Optional[Gtk.Window] = None) -> None:
        """Izbira map (lahko vec hkrati), ki jih sme televizor videti. Klice stran ali pladenj."""
        if self.datoteke is None:
            return
        okno = Gtk.FileChooserDialog(title="Mape za televizor — Safeer Control",
                                     transient_for=starsevsko or self.okno or self.starsevsko,
                                     action=Gtk.FileChooserAction.SELECT_FOLDER)
        okno.set_select_multiple(True)
        okno.add_button("Prekliči", Gtk.ResponseType.CANCEL)
        okno.add_button("Deli", Gtk.ResponseType.OK)

        def odgovor(d, r):
            poti = list(d.get_filenames() or []) if r == Gtk.ResponseType.OK else []
            d.destroy()
            if poti:
                self.datoteke.nastavi(self.datoteke.poti() + poti)
                self._odziv_mape()
        okno.connect("response", odgovor)
        okno.show()

    def _dodaj_deljeno_mapo(self) -> None:
        self.dodaj_deljeno_mapo()

    def _odstrani_deljeno_mapo(self, i) -> None:
        if self.datoteke is None:
            return
        try:
            self.datoteke.odstrani(int(i))
        except (TypeError, ValueError):
            return
        self._odziv_mape()

    def _poslji_datoteko(self, id_naprave: str, pot: str) -> None:
        ime = os.path.basename(pot)
        self._deljenje("datoteka", "posiljam", id_naprave, ime, odstotek=0)
        ok, n = link_deljenje.poslji_datoteko(
            self._hub(), self._zeton() or "", self._odtis() or "", self._id(), id_naprave, pot,
            napredek=lambda o: self._deljenje("datoteka", "posiljam", id_naprave, ime, odstotek=o))
        if ok:
            self._deljenje("datoteka", "poslano", id_naprave, ime, odstotek=100)
        else:
            self._deljenje("datoteka", "napaka", id_naprave, ime, n["sporocilo"], koda=n["koda"], zasedena_od=n["zasedenaOd"])

    def _zacni_deljenje_zaslona(self, id_naprave: str = "", ime_naprave: str = "") -> None:
        if not (self._hub() and self._zeton() and self._odtis()):
            self._odziv("napaka", {"koda": "hub_ni_znan", "sporocilo": "Hub ni znan."})
            return
        na_voljo, razlog = link_deljenje.DeljenjeZaslona.zajem_na_voljo()
        if not na_voljo:
            self._deljenje("zaslon", "napaka", id_naprave, ime_naprave, razlog, koda="ni_zajema")
            return
        if self.deljenje_zaslona is not None and self.deljenje_zaslona.tece:
            self.deljenje_zaslona.ustavi()
        d = link_deljenje.DeljenjeZaslona(self._hub(), self._zeton() or "", self._odtis() or "",
                                          self._id(), id_naprave, ime_naprave,
                                          ob_spremembi=self._na_spremembo_zaslona)
        self.deljenje_zaslona = d
        d.zacni()

    def _na_spremembo_zaslona(self, s: dict) -> None:
        self._deljenje("zaslon", "tece" if s.get("tece") else "koncano", s.get("cilj", ""), s.get("ime", ""),
                       s.get("napaka", ""), koda=s.get("koda", ""), zasedena_od=s.get("zasedenaOd", ""))

    def _koncaj_deljenje_zaslona(self) -> None:
        if self.deljenje_zaslona is not None:
            self.deljenje_zaslona.ustavi()

    def _preimenuj_napravo(self, id_naprave: str = "", ime: str = "") -> None:
        if not (self._hub() and self._zeton() and self._odtis()):
            self._odziv("napaka", {"koda": "hub_ni_znan", "sporocilo": "Hub ni znan."})
            return
        ok, novo, n = link_deljenje.preimenuj_napravo(self._hub(), self._zeton() or "", self._odtis() or "", id_naprave, ime)
        if ok:
            self._odziv("preimenovano", {"id": id_naprave, "ime": novo})
        else:
            self._odziv("napaka", {"koda": "preimenovanje_ni_uspelo", "sporocilo": n["sporocilo"]})

    def _ukaz(self, id_naprave: str = "", dejanje: str = "", parametri_json: str = "{}", ref: str = "") -> None:
        """Ukaz daljinca drugi napravi (control.command); odgovor pride kot odziv "ukaz" z istim ref."""
        povezava = self.povezava
        if povezava is None or not povezava.tece:
            self._odziv("ukaz", {"ref": ref, "ok": False, "message": "Ni povezave s Safeer Linkom."})
            return
        try:
            parametri = json.loads(parametri_json or "{}")
            if not isinstance(parametri, dict):
                parametri = {}
        except Exception:
            parametri = {}
        poslano = povezava.poslji({
            "id": ref or str(int(time.time() * 1000)),
            "type": "control.command",
            "target": id_naprave,
            "payload": {"action": dejanje, "params": parametri},
        })
        if not poslano:
            self._odziv("ukaz", {"ref": ref, "ok": False, "message": "Ukaza ni bilo mogoče poslati."})

    def _ukaz_odziv(self, sporocilo: dict) -> None:
        """Odgovor naprave (control.result) ali zavrnitev sredisca (control.ack) -> stran."""
        telo = sporocilo.get("payload") or {}
        o = {"ref": str(sporocilo.get("ref_id", "") or ""), "naprava": str(sporocilo.get("sender", "") or "")}
        if sporocilo.get("type") == "control.ack":
            if sporocilo.get("status") == "accepted":
                return
            o["ok"] = False
            o["message"] = str(sporocilo.get("error") or "Središče je ukaz zavrnilo.")
            o["koda"] = str(sporocilo.get("error_code") or "")
        else:
            o["ok"] = bool(telo.get("ok"))
            o["message"] = str(telo.get("message") or "")
            o["action"] = str(telo.get("action") or "")
            o["koda"] = str(telo.get("code") or "")
            if isinstance(telo.get("data"), dict):
                o["data"] = telo["data"]
        self._odziv("ukaz", o)

    def _poslji_trenutno(self, id_naprave: str = "") -> None:
        stran = self._stran()
        if not stran["posljiva"]:
            self._odziv("napaka", "Ta stran ni primerna za pošiljanje.")
            return
        self._poslji(id_naprave, stran["url"], stran["naslov"])

    def _poslji(self, id_naprave: str = "", url: str = "", naslov: str = "") -> None:
        if self.povezava is None:
            self._odziv("napaka", "Povezave s Hubom ni.")
            return
        cist = (url or "").strip()
        if not (cist.startswith("http://") or cist.startswith("https://")):
            self._odziv("napaka", "Poslati je mogoče samo naslove http in https.")
            return
        if self.povezava.poslji_url(id_naprave, cist, naslov or None):
            self._odziv("poslano", {"naprava": id_naprave, "url": cist})
        else:
            self._odziv("napaka", "Pošiljanje ni uspelo.")

    def _nadzor(self, id_naprave: str = "", ukaz: str = "", vrednost: float = 0.0) -> None:
        if self.povezava is None:
            return
        if ukaz == "seek":
            self.povezava.nadzor(id_naprave, "seek", polozaj=float(vrednost or 0))
        elif ukaz == "volume":
            self.povezava.nadzor(id_naprave, "volume", glasnost=float(vrednost or 0))
        else:
            self.povezava.nadzor(id_naprave, ukaz)

    def _odpri(self, url: str = "") -> None:
        cist = (url or "").strip()
        if not (cist.startswith("http://") or cist.startswith("https://")):
            return
        def naredi():
            if self.okno is not None and not self.control:
                self.okno.destroy()
            try:
                self.odpri_naslov(cist)
            except Exception:
                pass
            return False
        GLib.idle_add(naredi)

    # ------------------------------------------------------------------
    # Sinhronizacija zaznamkov
    # ------------------------------------------------------------------

    def _izvozi_zaznamke(self) -> dict:
        try:
            portali = self.config.get_portals() or []
        except Exception:
            portali = []
        elementi = []
        for p in portali:
            url = str(p.get("url", "") or "").strip()
            if url.startswith("http://") or url.startswith("https://"):
                elementi.append({
                    "title": str(p.get("title", "") or ""),
                    "url": url,
                    "icon": str(p.get("mark", "") or "⭐"),
                })
        return {"items": elementi}

    def _prejmi_zaznamke(self, telo: dict) -> None:
        if telo.get("category") != KATEGORIJA_ZAZNAMKI:
            return
        if not self.nastavitve.get("sync_bookmarks", False):
            return
        vsebina = telo.get("data") or {}
        elementi = vsebina.get("items") or []
        pripravljeni = []
        for e in elementi:
            url = str(e.get("url", "") or "").strip()
            if url.startswith("http://") or url.startswith("https://"):
                pripravljeni.append({
                    "title": str(e.get("title", "") or url),
                    "url": url,
                    "mark": str(e.get("icon", "") or "⭐"),
                })
        if not pripravljeni:
            return

        # Ta klic pride z niti vticnika, zapis zaznamkov pa je uporabnikova baza,
        # ki jo bere tudi vmesnik. Zato ga opravimo na glavni niti.
        def zdruzi():
            try:
                dodanih, _ = self.config.import_bookmarks_items(pripravljeni)
            except Exception as e:  # noqa: BLE001
                self._odziv("napaka",
                            f"Združevanja zaznamkov ni bilo mogoče končati: {e}")
                return False
            razlicica = telo.get("version")
            if isinstance(razlicica, int) and razlicica > int(
                    self.nastavitve.get("sync_bookmarks_version", 0) or 0):
                self.nastavitve.set("sync_bookmarks_version", razlicica)
            self._odziv("sinhronizacija", {
                "kategorija": KATEGORIJA_ZAZNAMKI,
                "vklopljena": True,
                "dodanih": dodanih,
            })
            return False

        GLib.idle_add(zdruzi)

    def _nastavi_sinhronizacijo(self, vklopljena: bool) -> None:
        self.nastavitve.set("sync_bookmarks", bool(vklopljena))
        if self.povezava is not None:
            self.povezava.zapri()
            self.povezava = None
        if not vklopljena:
            self._odziv("sinhronizacija", {"kategorija": KATEGORIJA_ZAZNAMKI,
                                           "vklopljena": False, "dodanih": 0})
            self._povezi()
            return
        self._povezi()
        if self.povezava is None:
            self._odziv("napaka", "Povezave s Hubom ni.")
            return
        self.povezava.zahtevaj_sync(KATEGORIJA_ZAZNAMKI)
        razlicica = int(self.nastavitve.get("sync_bookmarks_version", 0) or 0) + 1
        self.nastavitve.set("sync_bookmarks_version", razlicica)
        self.povezava.poslji_sync(KATEGORIJA_ZAZNAMKI, razlicica, self._izvozi_zaznamke())
        self._odziv("sinhronizacija", {"kategorija": KATEGORIJA_ZAZNAMKI,
                                       "vklopljena": True, "dodanih": 0})


def _barva(r: int, g: int, b: int):
    from gi.repository import Gdk
    barva = Gdk.RGBA()
    barva.red = r / 255.0
    barva.green = g / 255.0
    barva.blue = b / 255.0
    barva.alpha = 1.0
    return barva
