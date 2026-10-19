"""Priljubljene datoteke, mape in programi Safeer OS - en zapis za namizje QML in delovno povrsino WebKit.

Prej je delovna povrsina (assets/os/delovna.js) priljubljene hranila v localStorage svojega pogleda WebKit: namizje QML
jih ni videlo, vsak pogled je imel svoje (pregled 15. 10. 2026). Zdaj so v ~/.config/safeer-os/priljubljeno.json,
ki ga oba berejo prek mostu (priljubljenoSeznam …), spremembo pa SafeerOS sporoci obema z dogodkom »priljubljeno«.

Brez GTK (uporablja ga tudi preizkus). Pisanje je atomarno (zacasna datoteka + os.replace) pod zaklepom: klici mostu
tecejo v vec nitih, zaklep datoteke (fcntl) pa varuje pred drugim procesom Safeer OS istega uporabnika.

Lastnik, 15. 10. 2026: »nimamo nedelujocih ikon ali datotek«. Priljubljena datoteka ali mapa, ki je ni na njeni poti
(v Smeteh, izbrisana, na odklopljenem disku), se nikjer ne pokaze; zapis ostane skrit, zato se ob obnovitvi iz Smeti
(Obnovi ali Razveljavi) ali ponovnem priklopu diska vrne na isto mesto. Izpraznjene Smeti zapis izbrisejo; kar je
izginilo drugace (drug program, odklopljen USB), se pozabi sele, ko ga 30 dni ni (»videno«). Enako programi: namizji
pokazeta samo priljubljene, ki so namesceni - ob ponovni namestitvi se vrnejo.

Zapis:
    {"verzija": 1,
     "datoteke": [{"pot", "ime", "mapa", "videno"}],   vrstni red = uporabnikov; videno = nazadnje na poti (unix s)
     "programi": ["ta:gimp.desktop", ...],       kljuc kot kljucPrograma v delovna.js: naprava + ":" + id
     "kategorije": {"ta:gimp.desktop": "mediji"},
     "nastavitve": {"programiRazvrsti": "ime", "programiPogled": "mreza", "lupa": "zlozena"},
     "preseljeno": true}                         localStorage delovne povrsine je ze prenesen
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional

VERZIJA = 1
NAJVEC_DATOTEK = 200
NAJVEC_PROGRAMOV = 200
#: Najvec uporabnikovih kategorij programov (vec jih iz zapisa izpade - _preveri).
NAJVEC_KATEGORIJ = 1000
#: Najdaljsa pot (PATH_MAX na Linuxu); daljsa ni prava pot, samo bi napihnila zapis.
NAJDALJSA_POT = 4096
#: Skrita priljubljena (ni je na poti in ni v Smeteh) se pozabi po toliko casa.
POZABI_PO = 30 * 24 * 3600
#: Kako pogosto se zapise »videno« za vidne priljubljene (ne ob vsakem branju).
VIDENO_OSVEZI = 24 * 3600
#: Kategorije kataloga programov (iste kot KATEGORIJE v delovna.js, brez »vse« in »priljubljeni«).
KATEGORIJE = ("pisarna", "ustvarjanje", "mediji", "splet", "igre", "drugo")
#: Skupina iz metapodatkov programa (core/os_programi.skupina) -> kategorija kataloga (IZ_SKUPINE v delovna.js).
IZ_SKUPINE = {"pisarna": "pisarna", "ucenje": "pisarna", "programiranje": "ustvarjanje", "ustvarjanje": "ustvarjanje",
              "predstavnost": "mediji", "mediji": "mediji", "splet": "splet", "igre": "igre", "orodja": "drugo",
              "sistem": "drugo", "drugo": "drugo"}
#: Dovoljene nastavitve in njihove vrednosti (prva je privzeta). »lupa«: iskalna lupa na namizju je zlozena, dokler je ne
#: uporabis, ali vedno razsirjena (lastnik, 19. 10. 2026: »izven poti, a preprosto dosegljiva«).
NASTAVITVE = {"programiRazvrsti": ("ime", "nazadnje", "najveckrat"), "programiPogled": ("mreza", "seznam"),
              "lupa": ("zlozena", "razsirjena")}


def privzeta_pot() -> str:
    mapa = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "safeer-os")
    return os.path.join(mapa, "priljubljeno.json")


def _vrsta(ime: str, mapa: bool) -> str:
    try:
        from core.os_datoteke import vrsta_datoteke
        return vrsta_datoteke(ime, mapa)
    except Exception:  # noqa: BLE001 - brez os_datoteke (mimetypes je vedno na voljo, a za vsak primer)
        return "mapa" if mapa else "drugo"


def _prazno() -> dict:
    return {"verzija": VERZIJA, "datoteke": [], "programi": [], "kategorije": {}, "nastavitve": {}, "preseljeno": False}


def _cista_pot(pot: Any) -> str:
    p = str(pot or "").strip()
    if not p or "\0" in p:
        return ""
    p = os.path.expanduser(p)
    return os.path.normpath(p) if os.path.isabs(p) and len(p) <= NAJDALJSA_POT else ""


def _cist_kljuc(k: Any) -> str:
    k = str(k or "").strip()
    return k if k and len(k) <= 512 and "\0" not in k and ":" in k else ""


def _preveri(podatki: Any) -> dict:
    """Pokvarjen ali tuj zapis ne podre namizja: kar ni prave oblike, izpade."""
    z = _prazno()
    if not isinstance(podatki, dict):
        return z
    videne = set()
    for d in podatki.get("datoteke") or []:
        if not isinstance(d, dict):
            continue
        pot = _cista_pot(d.get("pot"))
        if not pot or pot in videne:
            continue
        videne.add(pot)
        videno = d.get("videno")
        z["datoteke"].append({"pot": pot, "ime": str(d.get("ime") or os.path.basename(pot) or pot)[:255],
                              "mapa": bool(d.get("mapa")),
                              "videno": float(videno) if isinstance(videno, (int, float)) and not isinstance(videno, bool) else 0.0})
    z["datoteke"] = z["datoteke"][:NAJVEC_DATOTEK]
    kljuci = []
    for k in podatki.get("programi") or []:
        k = _cist_kljuc(k)
        if k and k not in kljuci:
            kljuci.append(k)
    z["programi"] = kljuci[:NAJVEC_PROGRAMOV]
    kat = podatki.get("kategorije")
    if isinstance(kat, dict):
        z["kategorije"] = {k: v for k, v in ((_cist_kljuc(k), str(v)) for k, v in list(kat.items())[:NAJVEC_KATEGORIJ])
                           if k and v in KATEGORIJE}
    nas = podatki.get("nastavitve")
    if isinstance(nas, dict):
        z["nastavitve"] = {k: v for k, v in nas.items() if k in NASTAVITVE and v in NASTAVITVE[k]}
    z["preseljeno"] = bool(podatki.get("preseljeno"))
    return z


class Priljubljeno:
    """Shramba priljubljenih. ob_spremembi(stanje) poklice po vsaki shranjeni spremembi (SafeerOS -> dogodek)."""

    def __init__(self, pot: Optional[str] = None, ob_spremembi: Optional[Callable[[dict], None]] = None) -> None:
        self.pot = pot or privzeta_pot()
        self.ob_spremembi = ob_spremembi
        self._zaklep = threading.RLock()
        self._podpis: Optional[str] = None       # kar sta namizji nazadnje dobili (za osvezi)
        #: Rod stanja: vsaka shranjena sprememba ga poveca. Odgovori mostu tecejo v vec nitih in lahko pridejo pozneje
        #: kot dogodek novejse spremembe - namizje starejsega rodu ne uporabi (pregled 15. 10. 2026).
        self._rod = 0
        self._globina = 0                         # gnezdenje _zaklenjeno v niti, ki drzi zaklep
        self.cas: Callable[[], float] = time.time
        self.v_smeteh: Callable[[], List[str]] = _izvirne_v_smeteh

    # ------------------------------------------------------------------ branje in pisanje
    @contextlib.contextmanager
    def _zaklenjeno(self):
        """Zaklep niti + zaklep datoteke (drug proces istega uporabnika). Brez fcntl (ni Linux) samo zaklep niti."""
        with self._zaklep:
            fd = None
            self._globina += 1
            if self._globina > 1:
                # Gnezdeno v isti niti (osvezi -> stanje): datoteka je ze zaklenjena. Drugi flock na novem opisniku
                # istega procesa bi cakal sam nase.
                try:
                    yield
                finally:
                    self._globina -= 1
                return
            try:
                os.makedirs(os.path.dirname(self.pot), exist_ok=True)
                fd = os.open(self.pot + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX)
            except (OSError, ImportError):
                pass
            try:
                yield
            finally:
                self._globina -= 1
                if fd is not None:
                    try:
                        os.close(fd)          # zapre tudi flock
                    except OSError:
                        pass

    def _beri(self) -> dict:
        try:
            with open(self.pot, encoding="utf-8") as f:
                return _preveri(json.load(f))
        except ValueError:
            # Pokvarjen zapis (rocno urejen, poln disk pri drugem programu): namizje dela naprej s praznim, kopija
            # ostane ob njem - naslednje pisanje bi ga sicer prepisalo in priljubljene bi bile za vedno izgubljene.
            try:
                os.replace(self.pot, self.pot + ".pokvarjeno")
                print("[priljubljeno] pokvarjen zapis shranjen kot", os.path.basename(self.pot) + ".pokvarjeno", flush=True)
            except OSError:
                pass
            return _prazno()
        except OSError:
            return _prazno()

    def _pisi(self, z: dict) -> None:
        zacasna = "%s.%d.%d.tmp" % (self.pot, os.getpid(), threading.get_ident())
        try:
            # 0600: poti priljubljenih datotek so zasebne (drug uporabnik racunalnika jih ne bere).
            with os.fdopen(os.open(zacasna, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
                json.dump(z, f, ensure_ascii=False, indent=1)
                f.flush()
                os.fsync(f.fileno())
            os.replace(zacasna, self.pot)
        finally:
            if os.path.exists(zacasna):
                try:
                    os.remove(zacasna)
                except OSError:
                    pass

    def _spremeni(self, kaj: Callable[[dict], bool]) -> dict:
        """kaj(zapis) spremeni zapis in vrne, ali se je kaj spremenilo; shrani in sporoci samo takrat."""
        with self._zaklenjeno():
            z = self._beri()
            spremenjeno = bool(kaj(z))
            if spremenjeno:
                self._pisi(z)
                self._rod += 1
            # Stanje in dogodek pod zaklepom: dogodki dveh hkratnih sprememb gredo namizjema v pravem vrstnem redu.
            stanje = self.stanje(z)
            if spremenjeno:
                self._sporoci(stanje)
        return stanje

    def _sporoci(self, stanje: dict) -> None:
        self._podpis = self._podpis_stanja(stanje)
        if self.ob_spremembi is not None:
            try:
                self.ob_spremembi(stanje)
            except Exception as e:  # noqa: BLE001
                print("[priljubljeno] dogodek:", e, flush=True)

    @staticmethod
    def _podpis_stanja(stanje: dict) -> str:
        return json.dumps([[d["pot"], d["mapa"]] for d in stanje["datoteke"]] + [stanje["programi"], stanje["kategorije"],
                                                                                 stanje["nastavitve"]], sort_keys=True)

    def osvezi(self) -> dict:
        """Po dejanju z datotekami (Smeti, obnovitev, Razveljavi, premik) ali priklopu/odklopu diska: ce se je spremenilo,
        katere priljubljene so vidne, namizji dobita dogodek - seznam se osvezi brez ponovnega zagona."""
        with self._zaklenjeno():
            stanje = self.stanje()
            if self._podpis_stanja(stanje) != self._podpis:
                self._rod += 1
                stanje["rod"] = self._rod
                self._sporoci(stanje)
        return stanje

    def odstrani_poti(self, poti: Any) -> dict:
        """Trajno izbrisano (izpraznjene Smeti): zapisi za te poti in vse pod njimi gredo. Kar je na poti medtem
        spet (nova datoteka z istim imenom), ostane."""
        cisti = [x for x in (_cista_pot(p) for p in (poti if isinstance(poti, (list, tuple)) else [])) if x]
        if not cisti:
            return self.stanje()

        def kaj(z):
            pred = len(z["datoteke"])
            z["datoteke"] = [x for x in z["datoteke"] if os.path.lexists(x["pot"])
                             or not any(x["pot"] == a or x["pot"].startswith(a + os.sep) for a in cisti)]
            return len(z["datoteke"]) != pred
        return self._spremeni(kaj)

    def _pospravi(self, z: dict) -> bool:
        """Vidnim zapise cas, ko so bile nazadnje na poti; skrite, ki jih ni vec kot POZABI_PO in niso v Smeteh, pozabi."""
        zdaj, sprememba, stare = self.cas(), False, []
        for x in z["datoteke"]:
            if os.path.exists(x["pot"]):
                if zdaj - x.get("videno", 0) > VIDENO_OSVEZI:
                    x["videno"], sprememba = zdaj, True
            elif zdaj - x.get("videno", 0) > POZABI_PO:
                stare.append(x)
        brez_casa = [x for x in stare if not x.get("videno")]
        if brez_casa:
            # Zapis brez casa (prejsnja razlicica, preselitev): ura zacne teci zdaj, ne pozabimo ga takoj. Vsak zase -
            # prej je en zapis s casom med njimi povzrocil, da so bili pozabljeni tudi vsi brez casa.
            for x in brez_casa:
                x["videno"] = zdaj
            stare = [x for x in stare if x not in brez_casa]
            sprememba = True
        if stare:
            try:
                smeti = self.v_smeteh()
            except Exception:  # noqa: BLE001 - Smeti ni mogoce prebrati: raje nic ne pozabimo
                return sprememba
            ostanejo = [x for x in stare if any(x["pot"] == a or x["pot"].startswith(a + os.sep) for a in smeti)]
            pozabi = [x for x in stare if x not in ostanejo]
            if pozabi:
                z["datoteke"] = [x for x in z["datoteke"] if x not in pozabi]
                sprememba = True
        return sprememba

    # ------------------------------------------------------------------ za most
    def stanje(self, z: Optional[dict] = None) -> dict:
        """Za namizje: samo datoteke in mape, ki so na svoji poti (velikost, cas), v uporabnikovem vrstnem redu;
        programi v uporabnikovem vrstnem redu (namizje pokaze samo namescene), kategorije, nastavitve."""
        if z is None:
            with self._zaklenjeno():
                z = self._beri()
                if self._pospravi(z):
                    self._pisi(z)
        datoteke = []
        for d in z["datoteke"]:
            pot = d["pot"]
            try:
                st = os.stat(pot)
            except OSError:
                continue             # ni na poti: skrita, zapis pocaka (Smeti, odklopljen disk)
            mapa = os.path.isdir(pot)
            datoteke.append({"pot": pot, "ime": d["ime"], "mapa": mapa, "vrsta": _vrsta(d["ime"], mapa),
                             "velikost": 0 if mapa else st.st_size, "spremenjeno": st.st_mtime})
        nastavitve = {k: z["nastavitve"].get(k, v[0]) for k, v in NASTAVITVE.items()}
        return {"datoteke": datoteke, "programi": list(z["programi"]), "kategorije": dict(z["kategorije"]),
                "nastavitve": nastavitve, "preseljeno": z["preseljeno"], "rod": self._rod,
                "kategorijeProgramov": list(KATEGORIJE), "izSkupine": dict(IZ_SKUPINE)}

    def preklopi(self, vrsta: str, podatek: Any, vkljuci: Optional[bool] = None) -> dict:
        """vrsta "datoteka": podatek {pot, ime, mapa} ali pot; "datoteke": seznam takih (izbira vec datotek - ena
        sprememba, en dogodek; vkljuci None = dodaj vse, ce niso ze vse, sicer odstrani vse); "program": kljuc
        naprava:id. vkljuci None = preklopi."""
        if vrsta == "datoteke":
            vnosi = []
            for d in (podatek if isinstance(podatek, (list, tuple)) else [])[:NAJVEC_DATOTEK]:
                d = d if isinstance(d, dict) else {"pot": d}
                pot = _cista_pot(d.get("pot"))
                if pot and pot not in [v[0] for v in vnosi]:
                    vnosi.append((pot, d))
            if not vnosi:
                return self.stanje()

            def kaj_vec(z):
                je = {x["pot"] for x in z["datoteke"]}
                hoce = (not all(p in je for p, _ in vnosi)) if vkljuci is None else bool(vkljuci)
                if not hoce:
                    poti = {p for p, _ in vnosi}
                    pred = len(z["datoteke"])
                    z["datoteke"] = [x for x in z["datoteke"] if x["pot"] not in poti]
                    return len(z["datoteke"]) != pred
                novi = [(p, d) for p, d in vnosi if p not in je]
                for p, d in novi:
                    if len(z["datoteke"]) >= NAJVEC_DATOTEK:
                        z["datoteke"].pop(0)
                    z["datoteke"].append({"pot": p, "ime": str(d.get("ime") or os.path.basename(p) or p)[:255],
                                          "mapa": bool(d.get("mapa")) or os.path.isdir(p), "videno": self.cas()})
                return bool(novi)
            return self._spremeni(kaj_vec)
        if vrsta == "datoteka":
            d = podatek if isinstance(podatek, dict) else {"pot": podatek}
            pot = _cista_pot(d.get("pot"))
            if not pot:
                return self.stanje()

            def kaj(z):
                je = any(x["pot"] == pot for x in z["datoteke"])
                hoce = (not je) if vkljuci is None else bool(vkljuci)
                if hoce == je:
                    return False
                if hoce:
                    if len(z["datoteke"]) >= NAJVEC_DATOTEK:
                        z["datoteke"].pop(0)
                    z["datoteke"].append({"pot": pot, "ime": str(d.get("ime") or os.path.basename(pot) or pot)[:255],
                                          "mapa": bool(d.get("mapa")) or os.path.isdir(pot), "videno": self.cas()})
                else:
                    z["datoteke"] = [x for x in z["datoteke"] if x["pot"] != pot]
                return True
            return self._spremeni(kaj)
        if vrsta == "program":
            k = _cist_kljuc(podatek)
            if not k:
                return self.stanje()

            def kaj_p(z):
                je = k in z["programi"]
                hoce = (not je) if vkljuci is None else bool(vkljuci)
                if hoce == je:
                    return False
                if hoce:
                    if len(z["programi"]) >= NAJVEC_PROGRAMOV:
                        z["programi"].pop(0)
                    z["programi"].append(k)
                else:
                    z["programi"].remove(k)
                return True
            return self._spremeni(kaj_p)
        return self.stanje()

    def vrstni_red(self, vrsta: str, seznam: Any) -> dict:
        """Nov vrstni red (poti ali kljuci) za tiste, ki jih namizje vidi. Nepoznani izpadejo; izpusceni (skriti:
        v Smeteh, odstranjen program, druga naprava) ostanejo na svojih mestih - ob vrnitvi so tam, kjer so bili."""
        if not isinstance(seznam, list):
            return self.stanje()
        if vrsta == "datoteke":
            nov = [_cista_pot(p) for p in seznam]

            def kaj(z):
                po_poti = {x["pot"]: x for x in z["datoteke"]}
                vrsta_ = iter([po_poti[p] for p in dict.fromkeys(nov) if p in po_poti])
                izbrani = {p for p in nov if p in po_poti}
                urejeno = [next(vrsta_) if x["pot"] in izbrani else x for x in z["datoteke"]]
                if urejeno == z["datoteke"]:
                    return False
                z["datoteke"] = urejeno
                return True
            return self._spremeni(kaj)
        if vrsta == "programi":
            nov_k = [_cist_kljuc(k) for k in seznam]

            def kaj_p(z):
                vrsta_ = iter([k for k in dict.fromkeys(nov_k) if k in z["programi"]])
                izbrani = set(nov_k)
                urejeno = [next(vrsta_) if k in izbrani else k for k in z["programi"]]
                if urejeno == z["programi"]:
                    return False
                z["programi"] = urejeno
                return True
            return self._spremeni(kaj_p)
        return self.stanje()

    def kategorija(self, kljuc: Any, kategorija: Any) -> dict:
        """Uporabnik je program prestavil v drugo kategorijo; prazna kategorija vrne privzeto (iz metapodatkov)."""
        k, kat = _cist_kljuc(kljuc), str(kategorija or "")
        if not k or (kat and kat not in KATEGORIJE):
            return self.stanje()

        def kaj(z):
            if (z["kategorije"].get(k) or "") == kat:
                return False
            if kat:
                if k not in z["kategorije"] and len(z["kategorije"]) >= NAJVEC_KATEGORIJ:
                    z["kategorije"].pop(next(iter(z["kategorije"])))     # najstarejsa izbira
                z["kategorije"][k] = kat
            else:
                z["kategorije"].pop(k, None)
            return True
        return self._spremeni(kaj)

    def nastavi(self, kljuc: Any, vrednost: Any) -> dict:
        k = str(kljuc or "")
        if k not in NASTAVITVE or vrednost not in NASTAVITVE[k]:
            return self.stanje()

        def kaj(z):
            if z["nastavitve"].get(k) == vrednost:
                return False
            z["nastavitve"][k] = vrednost
            return True
        return self._spremeni(kaj)

    def preseli(self, stari: Any) -> dict:
        """Enkratni prenos iz localStorage delovne povrsine (N.priljubljeneDat, N.priljubljeniPrg, N.kategorije,
        N.pogled). Zdruzi brez podvajanja; kar je v shrambi, ima prednost. Vec pogledov WebKit z razlicnimi
        localStorage se zdruzi - nobena priljubljena se ne izgubi."""
        s = stari if isinstance(stari, dict) else {}

        def kaj(z):
            pred = json.dumps(z, sort_keys=True)
            ze = {x["pot"] for x in z["datoteke"]}
            for d in s.get("priljubljeneDat") or []:
                if isinstance(d, dict):
                    pot = _cista_pot(d.get("pot"))
                    if pot and pot not in ze and len(z["datoteke"]) < NAJVEC_DATOTEK:
                        ze.add(pot)
                        z["datoteke"].append({"pot": pot, "ime": str(d.get("ime") or os.path.basename(pot))[:255],
                                              "mapa": bool(d.get("mapa")), "videno": self.cas()})
            for k in s.get("priljubljeniPrg") or []:
                k = _cist_kljuc(k)
                if k and k not in z["programi"] and len(z["programi"]) < NAJVEC_PROGRAMOV:
                    z["programi"].append(k)
            kat = s.get("kategorije")
            if isinstance(kat, dict):
                for k, v in list(kat.items())[:1000]:
                    k = _cist_kljuc(k)
                    if k and v in KATEGORIJE and k not in z["kategorije"]:
                        z["kategorije"][k] = v
            pogled = s.get("pogled")
            if pogled in NASTAVITVE["programiPogled"] and "programiPogled" not in z["nastavitve"]:
                z["nastavitve"]["programiPogled"] = pogled
            z["preseljeno"] = True
            return json.dumps(z, sort_keys=True) != pred
        return self._spremeni(kaj)

    def premaknjeno(self, pari: Any) -> dict:
        """Datoteke ali mape so se premaknile/preimenovale v Safeer OS ([[staro, novo], ...]): priljubljene sledijo,
        tudi tiste znotraj premaknjene mape. Datoteka, ki je ni vec, ostane (kot nedosegljiva) - ne izgine tiho."""
        cisti = []
        for p in pari if isinstance(pari, (list, tuple)) else []:
            if isinstance(p, (list, tuple)) and len(p) == 2:
                a, b = _cista_pot(p[0]), _cista_pot(p[1])
                if a and b and a != b:
                    cisti.append((a, b))
        if not cisti:
            return self.stanje()

        def kaj(z):
            sprememba = False
            for x in z["datoteke"]:
                for a, b in cisti:
                    if x["pot"] == a:
                        x["pot"], sprememba = b, True
                        if x["ime"] == os.path.basename(a):
                            x["ime"] = os.path.basename(b)
                        break
                    if x["pot"].startswith(a + os.sep):
                        x["pot"], sprememba = b + x["pot"][len(a):], True
                        break
            if sprememba:     # dve priljubljeni na istem mestu: ena
                videne, nove = set(), []
                for x in z["datoteke"]:
                    if x["pot"] not in videne:
                        videne.add(x["pot"])
                        nove.append(x)
                z["datoteke"] = nove
            return sprememba
        return self._spremeni(kaj)


def _izvirne_v_smeteh() -> List[str]:
    """Izvirne poti vsega, kar je v Smeteh (Smeti tega uporabnika, kot jih pokaze Datoteke)."""
    from core import os_datoteke
    return [str(e.get("izvirna") or "") for e in os_datoteke.smeti().get("elementi") or [] if e.get("izvirna")]


_privzeta: Optional[Priljubljeno] = None
_privzeta_zaklep = threading.Lock()


def shramba(ob_spremembi: Optional[Callable[[dict], None]] = None) -> Priljubljeno:
    """Ena shramba na proces (Safeer OS, Control in Splet tecejo v istem procesu)."""
    global _privzeta
    with _privzeta_zaklep:
        if _privzeta is None:
            _privzeta = Priljubljeno()
        if ob_spremembi is not None:
            _privzeta.ob_spremembi = ob_spremembi
        return _privzeta


def premaknjeno_po_dejanju(metoda: str, a: List[Any], izid: Any) -> Optional[List[list]]:
    """Pari [staro, novo] iz izida dejanja mostu, po katerem naj priljubljene sledijo (ali None)."""
    if not isinstance(izid, dict) or not izid.get("ok", True):
        return None
    if metoda == "preimenujDatoteko" and izid.get("pot") and a:
        return [[str(a[0]), str(izid["pot"])]]
    if metoda == "prilepiDatoteke" and len(a) > 2 and a[2] and izid.get("pari"):
        return [list(p) for p in izid["pari"] if isinstance(p, (list, tuple)) and len(p) == 2]
    return None


def premaknjeno_po_razveljavitvi(zapis: Dict[str, Any], izid: Any) -> Optional[List[list]]:
    """Razveljavljen premik/preimenovanje vrne poti nazaj: priljubljene gredo z njimi (le tiste, ki so se res vrnile)."""
    if not isinstance(izid, dict) or not izid.get("narejeno"):
        return None
    if isinstance(zapis, dict) and zapis.get("vrsta") in ("premik", "preimenovanje"):
        return [[str(p[1]), str(p[0])] for p in zapis.get("pari") or []
                if isinstance(p, (list, tuple)) and len(p) == 2 and p[0] and not os.path.lexists(str(p[1]))
                and os.path.lexists(str(p[0]))]
    return None
