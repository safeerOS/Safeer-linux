"""Vgrajeni kanali v Sporocilih Safeer OS: spletni klepeti (WhatsApp, Messenger, Telegram ...) in namizni programi
(Viber, Signal Desktop) kot del namizja - v istem procesu in v oknu Sporocil, ne v drugem oknu (lastnik, 15. 10. 2026:
»celovitost - vse je en proces«).

  * Spletni kanal je SpletnaAplikacija vgrajenega Spleta (core/os_splet.py): ista seja (ena prijava), zascita in
    dovoljenja kot Splet; pojavna okna za prijavo pri aplikaciji, navadne povezave v Splet, prenosi v Prejeme.
  * Namizni program se zazene (ce ze tece, se uporabi njegovo okno) in njegovo okno se vstavi v Sporocila
    (core/vstavi_okno.py, X11). Na Waylandu vgradnja ni mogoca: program ostane v svojem oknu in vmesnik to pove.
  * Kanali se nalozijo ob zagonu namizja (ko je namizje izrisano, zaporedoma po dva) in tecejo ves cas v realnem casu
    (brez dusenja skritih strani); izklopljen kanal ali izklopljena Sporocila: nic se ne nalozi, nic ne tece.
  * Vsi spletni kanali so v enem spletnem procesu (os_splet.SKUPNI_PROCES, meritev tam); po padcu procesa vsi kanali
    tiho dobijo nov pogled, spet v skupnem procesu.
  * Neprebrano: naslov strani (spletni_klepeti.neprebrano) oziroma splosni viri D-Bus za programe
    (core/znacke_programov.py); zadnje znano stevilo se shrani, da je znacka pravilna ze ob zagonu.
  * Mesto v oknu: stran Sporocil (HTML) pove pravokotnik vsebine (CSS px); kanal je v Gtk.Stack nad stranjo
    (Gtk.Overlay okna Sporocil) na tem mestu. Ko je odprt sloj strani (pogovorno okno), se kanal skrije.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Callable, Dict, Optional

from core import namizni_programi, spletni_klepeti
from core.sporocila import vklop

#: Najvec kanalov, ki se hkrati nalagajo ob zagonu (lastnik: »zaporedoma ali po dva hkrati«).
HKRATI_OB_ZAGONU = 2
#: Ce kanal ne javi konca nalaganja, naslednji pride na vrsto po tem casu.
NALAGANJE_NAJDLJE_S = 12
#: Koliko casa iscemo okno zagnanega programa.
OKNO_PROGRAMA_S = 60
#: Viri stevila neprebranih (manjse = prednost).
VIR_ZNACKA, VIR_PLADENJ, VIR_OBVESTILA, VIR_NASLOV = 1, 2, 3, 4


class _Kanal:
    """Zivi kanal (ustvarjen pogled ali zagnan program)."""

    def __init__(self, podatki: dict) -> None:
        self.podatki = podatki
        self.aplikacija = None          # SpletnaAplikacija
        self.program: Optional[dict] = None   # najdba (namizni_programi.najdi)
        self.okno = None                # VstavljenoOkno
        self.gradnik = None             # kar gre v sklad nad stranjo
        self.nalozen = False
        self.vgrajeno = True            # namizni program na Waylandu: False
        self.vir = VIR_NASLOV + 1
        self.obvestil = 0               # vir 3: obvestila programa od zadnjega odprtja kanala
        self.iskanje = 0


class KanaliSporocil:
    def __init__(self, Gtk, GLib, Gio, jedro: Callable[[], object], shramba, jezik: Callable[[], str],
                 dogodek: Callable[[str, object], None], odpri_kanal: Callable[[str], None],
                 obvestila=None) -> None:
        self.Gtk, self.GLib, self.Gio = Gtk, GLib, Gio
        self.jedro, self.jezik, self.dogodek, self.odpri_kanal = jedro, jezik, dogodek, odpri_kanal
        if obvestila is None:
            from core import obvestila as _o
            obvestila = _o
        self.obvestila = obvestila
        self.kanali = spletni_klepeti.Kanali(shramba)
        self.zivi: Dict[str, _Kanal] = {}
        #: id(pogled strani) -> {"prekrivanje", "sklad", "pogled", "kanal"}
        self.plasti: Dict[int, dict] = {}
        self._vrsta: list = []
        self._nalaga: set = set()
        self._znacke = None
        self._ikone_tecejo = False
        self._ikone_poskusene: set = set()
        #: Cas zacetka nalaganja posameznega kanala (meritev casa do vsebine).
        self.casi: Dict[str, dict] = {}

    # ------------------------------------------------------------------ stanje
    @staticmethod
    def vklopljena() -> bool:
        return vklop.sporocila_vklopljena()

    def seznam(self) -> list:
        """Kanali za stran: shranjeni podatki + ali je nalozen, vgrajen, namescen, ikona."""
        izid = []
        from core import ikone_strani
        manjkajo = []
        for k in self.kanali.seznam():
            z = self.zivi.get(k["id"])
            vnos = spletni_klepeti.po_id(k["katalog"]) or {}
            program = spletni_klepeti.je_program(vnos)
            d = dict(k, vrsta="program" if program else "splet", nalozen=bool(z and z.nalozen),
                     vgrajeno=bool(z.vgrajeno) if z else namizni_programi.x11_seja() or not program,
                     ikona="")
            if program:
                d["namescen"] = namizni_programi.najdi(vnos["program"], k.get("pot", "")) is not None
            elif k["url"]:
                d["ikona"] = ikone_strani.iz_predpomnilnika(k["url"])
                if not d["ikona"]:
                    manjkajo.append(k["url"])
            izid.append(d)
        manjkajo = [u for u in manjkajo if u not in self._ikone_poskusene]
        if manjkajo:
            self._prenesi_ikone(manjkajo)
        return izid

    def katalog(self) -> list:
        """Katalog za carovnik (spletni_klepeti.za_vmesnik) z »namescen« za namizne programe."""
        izid = []
        for v in spletni_klepeti.za_vmesnik(self.jezik()):
            if v.get("program"):
                v = dict(v, namescen=namizni_programi.najdi(v["program"]) is not None)
            izid.append(v)
        return izid

    def neprebrano_skupaj(self) -> int:
        if not self.vklopljena():
            return 0
        return sum(int(k.get("neprebrano") or 0) for k in self.kanali.seznam() if k.get("vklopljen"))

    def zasciteni(self) -> set:
        """Registrirane domene dodanih spletnih kanalov: njihove prijave in shrambe brisanje Spleta ne izbrise."""
        from core import pojavna_okna
        return {pojavna_okna.osnova(pojavna_okna.gostitelj(k["url"])) for k in self.kanali.seznam() if k.get("url")}

    def _sporoci(self) -> None:
        try:
            self.dogodek("kanaliSporocil", self.seznam())
        except Exception as e:  # noqa: BLE001
            print("[Sporocila] dogodek kanalov:", e, flush=True)

    # ------------------------------------------------------------------ urejanje (most strani)
    def dodaj(self, katalog: str = "", url: str = "", ime: str = "", pot: str = "") -> list:
        if not self.vklopljena():
            raise ValueError("izklopljeno")
        if pot and not namizni_programi.je_izvrsljiva(pot):
            raise ValueError("pot")
        k = self.kanali.dodaj(katalog=katalog, url=url, ime_kanala=ime, jezik=self.jezik(), pot=pot)
        self._ustvari(k)
        self._sporoci()
        return self.seznam()

    def odstrani(self, kid: str, izbrisi_podatke: bool = False) -> list:
        k = self.kanali.najdi(kid)
        self._unici_in_sprosti(kid)
        if k is not None and izbrisi_podatke and k.get("url"):
            self._izbrisi_podatke_strani(k["url"])
        self.kanali.odstrani(kid)
        self._sporoci()
        return self.seznam()

    def preimenuj(self, kid: str, ime: str) -> list:
        self.kanali.preimenuj(kid, ime)
        self._sporoci()
        return self.seznam()

    def premakni(self, kid: str, smer: int) -> list:
        self.kanali.premakni(kid, smer)
        self._sporoci()
        return self.seznam()

    def vklopi(self, kid: str, vklopljen: bool) -> list:
        """Vklop ga takoj nalozi; izklop ga sprosti (pogled unicen, ne le skrit)."""
        k = self.kanali.vklopi(kid, bool(vklopljen))
        if vklopljen and self.vklopljena():
            self._ustvari(k)
        else:
            self._unici_in_sprosti(kid)
            self.kanali.zapomni_neprebrano(kid, 0)
        self._sporoci()
        return self.seznam()

    def izbrisi_podatke(self, kid: str) -> list:
        """»Izbrisi podatke kanala«: prijava, shranjena sporocila in predpomnilnik te strani; kanal se nalozi znova."""
        k = self.kanali.najdi(kid)
        if k is None or not k.get("url"):
            raise ValueError("kanal")

        def znova():
            z = self.zivi.get(kid)
            if z is not None and z.aplikacija is not None:
                z.aplikacija.domov()
        self._izbrisi_podatke_strani(k["url"], znova)
        return self.seznam()

    def _izbrisi_podatke_strani(self, url: str, ob_koncu=None) -> None:
        from core import pojavna_okna
        splet = self.jedro()
        if splet is None:
            return
        domena = pojavna_okna.osnova(pojavna_okna.gostitelj(url))
        splet.izbrisi_strani(0, lambda ime: ime == domena, ob_koncu)

    # ------------------------------------------------------------------ nalaganje ob zagonu
    def zazeni_vse(self) -> None:
        """Vsi vklopljeni kanali, zaporedoma po HKRATI_OB_ZAGONU z nizko prednostjo (namizje je ze izrisano)."""
        if not self.vklopljena():
            return
        self._vrsta = [k["id"] for k in self.kanali.seznam() if k.get("vklopljen") and k["id"] not in self.zivi]
        self._naslednji()

    def _naslednji(self) -> None:
        while self._vrsta and len(self._nalaga) < HKRATI_OB_ZAGONU:
            kid = self._vrsta.pop(0)
            self._nalaga.add(kid)

            def zdaj(kid=kid):
                k = self.kanali.najdi(kid)
                if k is not None and k.get("vklopljen") and self.vklopljena():
                    self._ustvari(k)
                else:
                    self._nalozeno(kid)
                return False
            self.GLib.idle_add(zdaj, priority=self.GLib.PRIORITY_LOW)

            def rok(kid=kid):
                self._nalozeno(kid)
                return False
            self.GLib.timeout_add_seconds(NALAGANJE_NAJDLJE_S, rok)

    def _nalozeno(self, kid: str) -> None:
        if kid in self._nalaga:
            self._nalaga.discard(kid)
            self._naslednji()

    def ustavi_vse(self) -> None:
        """Sporocila izklopljena: vsi kanali se sprostijo."""
        self._vrsta = []
        for kid in list(self.zivi):
            self._unici(kid)

    # ------------------------------------------------------------------ ustvarjanje in unicenje
    def _ustvari(self, k: dict) -> Optional[_Kanal]:
        if k["id"] in self.zivi:
            return self.zivi[k["id"]]
        vnos = spletni_klepeti.po_id(k.get("katalog", "")) or {}
        z = _Kanal(k)
        self.casi[k["id"]] = {"zacetek": time.monotonic()}
        if spletni_klepeti.je_program(vnos):
            if not self._ustvari_program(z, vnos):
                self._nalozeno(k["id"])
                return None
        else:
            splet = self.jedro()
            if splet is None:      # brez peskovnika WebKit ni vgrajenega Spleta (glej safeer_os._peskovnik_na_voljo)
                self._nalozeno(k["id"])
                return None
            kid = k["id"]
            z.aplikacija = splet.aplikacija(k["url"], ob_naslovu=lambda n, kid=kid: self._naslov(kid, n, VIR_NASLOV),
                                            ob_obvestilu=lambda n, b, klik, kid=kid: self._obvestilo(kid, n, b, klik))
            z.aplikacija.povezi("load-changed", lambda p, d, kid=kid: self._nalaganje(kid, p, d))
            z.gradnik = z.aplikacija.gradnik
        self.zivi[k["id"]] = z
        return z

    def _nalaganje(self, kid: str, _pogled, dogodek) -> None:
        if getattr(dogodek, "value_nick", "") != "finished":
            return
        z = self.zivi.get(kid)
        if z is not None and not z.nalozen:
            z.nalozen = True
            c = self.casi.get(kid)
            if c is not None and "vsebina_s" not in c:
                c["vsebina_s"] = round(time.monotonic() - c["zacetek"], 2)
            self._nalozeno(kid)
            self._sporoci()

    def _unici_in_sprosti(self, kid: str) -> None:
        """Izklop ali odstranitev spletnega kanala: v skupnem procesu (os_splet.SKUPNI_PROCES) bi njegov pomnilnik
        ostal procesu (meritev 15. 10. 2026: izklop 2 od 3 kanalov le 777,9 -> 704,8 MiB), zato ostali kanali dobijo
        nov proces in stari se konca."""
        z = self.zivi.get(kid)
        spletni = z is not None and z.aplikacija is not None
        self._unici(kid)
        splet = self.jedro() if spletni else None
        if splet is not None and any(x.aplikacija is not None for x in self.zivi.values()):
            splet.sprosti_proces_aplikacij()

    def _unici(self, kid: str) -> None:
        z = self.zivi.pop(kid, None)
        self._nalaga.discard(kid)
        if kid in self._vrsta:
            self._vrsta.remove(kid)
        if z is None:
            return
        for plast in self.plasti.values():
            if plast.get("kanal") == kid:
                plast["kanal"] = None
                plast["sklad"].set_visible(False)
        if z.aplikacija is not None:
            z.aplikacija.unici()
        if z.okno is not None:
            stars = z.gradnik.get_parent() if z.gradnik is not None else None
            z.okno.unici()          # okno programa nazaj na namizje (program se ne ustavi)
            if stars is not None:
                stars.remove(z.gradnik)
        if z.iskanje:
            self.GLib.source_remove(z.iskanje)
        try:
            from core import pomnilnik
            pomnilnik.obrezuj()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ namizni programi
    def _ustvari_program(self, z: _Kanal, vnos: dict) -> bool:
        from core import vstavi_okno
        najdba = namizni_programi.najdi(vnos["program"], z.podatki.get("pot", ""))
        if najdba is None:
            return False
        z.program = najdba
        kid = z.podatki["id"]
        self._zacni_znacke()
        if not namizni_programi.x11_seja():
            # Wayland: okna drugega programa ni mogoce vstaviti - program v svojem oknu, vmesnik to pove (nikoli lazna
            # vgradnja). Zazene se samo, ce se ne tece.
            z.vgrajeno = False
            namizni_programi.zazeni(najdba)
            z.nalozen = True
            return True
        z.gradnik = self.Gtk.DrawingArea()
        z.gradnik.set_hexpand(True)
        z.gradnik.set_vexpand(True)
        z.okno = vstavi_okno.VstavljenoOkno(self.Gtk, self.GLib, z.gradnik,
                                            ob_naslovu=lambda n, kid=kid: self._naslov(kid, n, VIR_NASLOV),
                                            ob_koncu=lambda kid=kid: self._program_zaprl_okno(kid))
        try:
            x11 = vstavi_okno.X11()
        except OSError:
            z.vgrajeno = False
            namizni_programi.zazeni(najdba)
            z.nalozen = True
            return True
        okno = x11.najdi(najdba["razredi"])
        x11.zapri()
        if not okno:
            namizni_programi.zazeni(najdba)      # ce program ze tece v pladnju, navadno pokaze svoje okno
        z.iskanje = self.GLib.timeout_add(500, self._isci_okno, kid, time.monotonic(), bool(okno))
        return True

    def _isci_okno(self, kid: str, zacetek: float, takoj: bool) -> bool:
        from core import vstavi_okno
        z = self.zivi.get(kid)
        if z is None or z.okno is None:
            return False
        try:
            x11 = vstavi_okno.X11()
            okno = x11.najdi(z.program["razredi"])
            x11.zapri()
        except OSError:
            okno = 0
        if okno:
            z.iskanje = 0
            z.okno.vstavi(okno)
            z.nalozen = True
            c = self.casi.get(kid)
            if c is not None:
                c["vsebina_s"] = round(time.monotonic() - c["zacetek"], 2)
            self._naslov(kid, z.okno.naslov(), VIR_NASLOV)
            self._nalozeno(kid)
            self._sporoci()
            return False
        if time.monotonic() - zacetek > OKNO_PROGRAMA_S:
            z.iskanje = 0
            print("[Sporocila] okna programa ni:", z.podatki.get("ime"), flush=True)
            self._nalozeno(kid)
            return False
        return True

    def _program_zaprl_okno(self, kid: str) -> None:
        """Program je zaprl (unicil) svoje okno: ob naslednjem prikazu kanala ga poiscemo ali zazenemo znova."""
        z = self.zivi.get(kid)
        if z is not None:
            z.nalozen = False
            self._sporoci()

    def _zacni_znacke(self) -> None:
        if self._znacke is not None:
            return
        from core import znacke_programov
        self._znacke = znacke_programov.Poslusalec(self.Gio, self.GLib, ob_znacki=self._znacka,
                                                   ob_pladnju=self._pladenj, ob_obvestilu=self._obvestilo_programa)

    def _kanali_programa(self):
        for kid, z in self.zivi.items():
            if z.program is not None:
                yield kid, z, (spletni_klepeti.po_id(z.podatki.get("katalog", "")) or {})

    @staticmethod
    def _imena(z: _Kanal, vnos: dict) -> set:
        p = vnos.get("program") or {}
        imena = {str(x).casefold() for x in list(p.get("razredi") or []) + list(p.get("ukazi") or []) + [vnos.get("ime", "")]}
        imena |= {os.path.basename(str(x)).casefold() for x in p.get("ukazi") or []}
        if z.program and z.program.get("ukaz"):
            imena.add(os.path.basename(z.program["ukaz"][0]).casefold())
        return {i for i in imena if i}

    def _znacka(self, desktop_id: str, n: int) -> None:
        for kid, z, vnos in self._kanali_programa():
            vnosi = set((vnos.get("program") or {}).get("vnosi") or [])
            if desktop_id in vnosi or (z.program and os.path.basename(z.program.get("vnos", "")) == desktop_id):
                self._stevilo(kid, n, VIR_ZNACKA)

    def _pladenj(self, ime: str, pozornost: bool) -> None:
        for kid, z, vnos in self._kanali_programa():
            if str(ime).casefold() in self._imena(z, vnos) and z.vir >= VIR_PLADENJ:
                self._stevilo(kid, max(1, int(self.kanali.najdi(kid).get("neprebrano") or 0)) if pozornost else 0,
                              VIR_PLADENJ)

    def _obvestilo_programa(self, app: str, _povzetek: str, _besedilo: str) -> None:
        for kid, z, vnos in self._kanali_programa():
            if str(app).casefold() in self._imena(z, vnos) and z.vir >= VIR_OBVESTILA:
                z.obvestil += 1
                self._stevilo(kid, z.obvestil, VIR_OBVESTILA)

    # ------------------------------------------------------------------ neprebrano in obvestila
    def _naslov(self, kid: str, naslov: str, vir: int) -> None:
        self._stevilo(kid, spletni_klepeti.neprebrano(naslov), vir)

    def _stevilo(self, kid: str, n: int, vir: int) -> None:
        z = self.zivi.get(kid)
        if z is None:
            return
        if vir > z.vir:
            return             # boljsi vir ze javlja stevilo (npr. LauncherEntry pred naslovom okna)
        z.vir = vir
        if self.kanali.zapomni_neprebrano(kid, n):
            self._sporoci()

    def _obvestilo(self, kid: str, naslov: str, besedilo: str, klik) -> None:
        """Spletno obvestilo kanala gre skozi obvestila Safeer OS; klik odpre Sporocila na tem kanalu."""
        k = self.kanali.najdi(kid)
        if k is None or not k.get("vklopljen") or not self.vklopljena():
            return
        ime = k.get("ime") or ""
        glava = naslov if (not ime or ime.casefold() in naslov.casefold()) else "%s · %s" % (ime, naslov)

        def kliknjeno():
            try:
                klik()
            except Exception:  # noqa: BLE001 - obvestilo strani je ze zaprto
                pass
            self.odpri_kanal(kid)
        self.obvestila.poslji(glava or ime, besedilo, "safeer-kanal-" + kid, privzeto=kliknjeno)

    def odprt(self, kid: str) -> None:
        """Uporabnik je odprl kanal: stevec obvestil (vir 3) se ponastavi."""
        z = self.zivi.get(kid)
        if z is not None and z.vir == VIR_OBVESTILA:
            z.obvestil = 0
            self._stevilo(kid, 0, VIR_OBVESTILA)

    # ------------------------------------------------------------------ mesto nad stranjo
    def plast(self, pogled, prekrivanje) -> dict:
        p = self.plasti.get(id(pogled))
        if p is None:
            sklad = self.Gtk.Stack()
            sklad.set_transition_type(self.Gtk.StackTransitionType.NONE)
            # Izrecno: sklad ne sme razsiriti prekrivanja (glavno okno zozi stran za Splet, glej _pokazi_spletni_nacin).
            sklad.set_hexpand(False)
            sklad.set_vexpand(False)
            sklad.set_halign(self.Gtk.Align.FILL)
            sklad.set_valign(self.Gtk.Align.FILL)
            sklad.set_visible(False)
            prekrivanje.add_overlay(sklad)
            p = self.plasti[id(pogled)] = {"prekrivanje": prekrivanje, "sklad": sklad, "pogled": pogled, "kanal": None}
            pogled.connect("destroy", lambda *_: self.plasti.pop(id(pogled), None))
        return p

    def pokazi(self, pogled, prekrivanje, kid: str, pravokotnik: dict) -> dict:
        """Kanal na mestu vsebine strani. Kanal, ki se ni nalozen (izklopljen in vklopljen, zagon se tece), se ustvari."""
        if not self.vklopljena():
            return {"ok": False, "razlog": "izklopljeno"}
        k = self.kanali.najdi(kid)
        if k is None or not k.get("vklopljen"):
            return {"ok": False, "razlog": "kanal"}
        z = self.zivi.get(kid) or self._ustvari(k)
        if z is None:
            vnos = spletni_klepeti.po_id(k.get("katalog", "")) or {}
            return {"ok": False, "razlog": "program" if spletni_klepeti.je_program(vnos) else "splet"}
        self.odprt(kid)
        if not z.vgrajeno:
            if z.program is not None:
                namizni_programi.zazeni(z.program)     # okno programa pride naprej (program z enim primerkom)
            return {"ok": True, "vgrajeno": False}
        if z.okno is not None and not z.okno.okno and not z.iskanje:
            self._ustvari_program_okno(z)   # program je medtem zaprl okno: poiscemo ga ali ga zazenemo znova
        p = self.plast(pogled, prekrivanje)
        stars = z.gradnik.get_parent()
        if stars is not p["sklad"]:
            if stars is not None:
                stars.remove(z.gradnik)
            p["sklad"].add_named(z.gradnik, kid)
        p["sklad"].set_visible_child(z.gradnik)
        p["kanal"] = kid
        self.polozaj(pogled, pravokotnik)
        p["sklad"].set_visible(True)
        if z.aplikacija is not None:
            z.aplikacija.pogled.grab_focus()
        return {"ok": True, "vgrajeno": True}

    def _ustvari_program_okno(self, z: _Kanal) -> bool:
        if z.program is None:
            return False
        namizni_programi.zazeni(z.program)
        z.iskanje = self.GLib.timeout_add(500, self._isci_okno, z.podatki["id"], time.monotonic(), False)
        return True

    def polozaj(self, pogled, r: dict) -> None:
        p = self.plasti.get(id(pogled))
        if p is None or not isinstance(r, dict):
            return
        try:
            merilo = float(r.get("dpr") or 1) / max(1, int(pogled.get_scale_factor() or 1))
            x, y, w, h = (float(r.get(k) or 0) for k in ("x", "y", "w", "h"))
            vw, vh = float(r.get("vw") or 0), float(r.get("vh") or 0)
        except (TypeError, ValueError):
            return
        s = p["sklad"]
        s.set_margin_start(max(0, round(x * merilo)))
        s.set_margin_top(max(0, round(y * merilo)))
        s.set_margin_end(max(0, round((vw - x - w) * merilo)))
        s.set_margin_bottom(max(0, round((vh - y - h) * merilo)))

    def skrij(self, pogled) -> None:
        p = self.plasti.get(id(pogled))
        if p is not None:
            p["sklad"].set_visible(False)
            p["kanal"] = None

    def ukaz(self, kid: str, ukaz: str) -> bool:
        z = self.zivi.get(kid)
        if z is None or z.aplikacija is None:
            return False
        a = z.aplikacija
        if ukaz == "nazaj":
            a.nazaj()
        elif ukaz == "osvezi":
            a.osvezi()
        elif ukaz == "domov":
            a.domov()
        elif ukaz == "splet":
            self.jedro().odpri_zunaj(a.uri() or z.podatki["url"])
        else:
            return False
        return True

    def koncaj(self) -> None:
        """Konec Safeer OS: okna programov nazaj na namizje (programi tecejo naprej), poslusalec D-Bus ustavljen."""
        for z in list(self.zivi.values()):
            if z.okno is not None:
                z.okno.unici()
        if self._znacke is not None:
            self._znacke.ustavi()

    # ------------------------------------------------------------------ ikone
    def _prenesi_ikone(self, naslovi: list) -> None:
        if self._ikone_tecejo:
            return
        self._ikone_tecejo = True
        self._ikone_poskusene.update(naslovi)

        def delo():
            from core import ikone_strani
            novih = 0
            for url in naslovi[:20]:
                ikona = ikone_strani.ikona_strani(url)
                if ikona:
                    ikone_strani.shrani(url, ikona)
                    novih += 1
            self.GLib.idle_add(lambda: (self._ikone_konec(novih), False)[1])
        threading.Thread(target=delo, name="safeer-ikone-kanalov", daemon=True).start()

    def _ikone_konec(self, novih: int) -> None:
        self._ikone_tecejo = False
        if novih:
            self._sporoci()
