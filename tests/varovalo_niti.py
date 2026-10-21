"""Varovalo preizkusov: vmesnik (Gtk, Gdk, Gsk, WebKit in Qt lupine QML) samo iz glavne niti (nacrt stabilnosti P1,
naloga 42). Samo v preizkusih - izdelek ga nima.

GTK, GDK in WebKitGTK niso varni za niti: klic iz delovne niti (Link, DoH, katalog ...) se navadno »posreci« in sesuje
sele kasneje (zgodovina: RELEASE_ASSERT(isMainThread) -> SIGTRAP, 18. 10. 2026). Varovalo ovije metode razredov in
funkcije imenskih prostorov, ki so v procesu ze nalozeni, in zapise vsak klic izven glavne niti (z mestom klica).
conftest.py preizkus ob takem klicu podre (SAFEER_VAROVALO_NITI=strogo, privzeto) ali ga samo zapise v povzetek teka
(=porocilo, za meritev) ali je izklopljeno (=0).

Ovije se lenobno: imenski prostor sele, ko ga je kaksen preizkus uvozil (sicer bi conftest izbral typelib WebKit pred
preizkusom, ki nastavi nas GI_TYPELIB_PATH). Klici v istem preizkusu PRED prvim ovijanjem niso vidni - povzetek pove,
kdaj je bil prostor ovit.
"""
from __future__ import annotations

import functools
import os
import re
import sys
import threading
import traceback
from typing import Callable, List, Optional

#: Imenski prostori GI, ki jih sme klicati samo glavna nit.
PROSTORI_GI = ("Gtk", "Gdk", "Gsk", "WebKit", "GdkX11", "GdkWayland")
#: Razredi PySide6, ki jih sme klicati samo glavna nit Qt (lupina QML: okno, kontekst QML, aplikacija, zasloni).
#: Oddaja signala (Most.odgovor.emit) iz niti JE varna - Qt jo dostavi v glavno nit - in se ne ovija.
RAZREDI_QT = (("PySide6.QtQuick", "QQuickView"), ("PySide6.QtQuick", "QQuickWindow"), ("PySide6.QtQuick", "QQuickItem"),
              ("PySide6.QtQml", "QQmlContext"), ("PySide6.QtQml", "QQmlEngine"), ("PySide6.QtGui", "QWindow"),
              ("PySide6.QtGui", "QGuiApplication"), ("PySide6.QtGui", "QScreen"))
#: Funkcije, ki ne dotaknejo stanja vmesnika (samo razlicica knjiznice).
VARNE = re.compile(r"^(get_(major|minor|micro|binary_age|interface_age)_version|check_version|get_.*_version)$")
#: Razhrosceni pripomocki GObject in Python, ki jih ne ovijamo.
PRESKOCI = re.compile(r"^(do_.*|__.*__|_.*)$")


def je_glavna_nit() -> bool:
    return threading.current_thread() is threading.main_thread()


class Krsitev:
    __slots__ = ("klic", "nit", "mesto")

    def __init__(self, klic: str, nit: str, mesto: str) -> None:
        self.klic, self.nit, self.mesto = klic, nit, mesto

    def __str__(self) -> str:
        return "%s iz niti %r\n%s" % (self.klic, self.nit, self.mesto)


def _mesto() -> str:
    """Zadnji okvirji klica izven varovala in knjiznic gi/PySide6 (kje v nasi kodi je klic)."""
    okvirji = [o for o in traceback.extract_stack()[:-3]
               if os.path.basename(o.filename) not in ("varovalo_niti.py", "threading.py") and "/gi/" not in o.filename]
    return "".join(traceback.format_list(okvirji[-4:]))


def _je_gi(izv, vprasanje: str) -> bool:
    """gi.FunctionInfo.is_method() / is_constructor(); False za druge klicne predmete."""
    try:
        return bool(getattr(izv, vprasanje)())
    except (AttributeError, TypeError):
        return False


class _Varovano:
    """Opisnik (descriptor) okoli izvirnega atributa razreda: veze kot izvirnik, klic izven glavne niti zapise."""

    def __init__(self, izvirnik, oznaka: str, varovalo: "Varovalo") -> None:
        self.izvirnik, self.oznaka, self.varovalo = izvirnik, oznaka, varovalo

    def __get__(self, obj, owner=None):
        izv = self.izvirnik
        if hasattr(izv, "__get__"):
            vezan = izv.__get__(obj, owner)
        elif obj is not None and _je_gi(izv, "is_method"):
            # gi.FunctionInfo veze v C (tp_descr_get brez __get__ v Pythonu): metodi damo predmet kot prvi argument.
            vezan = functools.partial(izv, obj)
        elif _je_gi(izv, "is_constructor"):
            vezan = functools.partial(izv, owner if obj is None else type(obj))   # konstruktor dobi razred
        else:
            vezan = izv
        varovalo, oznaka = self.varovalo, self.oznaka

        def klic(*a, **k):
            if not varovalo.je_glavna():
                varovalo.zapisi(oznaka)
            return vezan(*a, **k)
        klic.__name__ = oznaka.rsplit(".", 1)[-1]
        klic.__doc__ = getattr(izv, "__doc__", None)
        return klic


class Varovalo:
    def __init__(self, nacin: str = "strogo", je_glavna: Callable[[], bool] = je_glavna_nit) -> None:
        self.nacin = nacin
        self.je_glavna = je_glavna
        self._zaklep = threading.Lock()
        self.krsitve: List[Krsitev] = []
        self.oviti: dict = {}              # ime prostora ali razreda -> stevilo ovitih atributov
        self._razredi: set = set()
        self.neoviti: List[str] = []       # atributi, ki jih ni bilo mogoce oviti (za povzetek)

    @classmethod
    def iz_okolja(cls, okolje=None) -> "Varovalo":
        nacin = (okolje if okolje is not None else os.environ).get("SAFEER_VAROVALO_NITI", "strogo").strip().lower()
        return cls(nacin if nacin in ("strogo", "porocilo", "0") else "strogo")

    @property
    def vklopljeno(self) -> bool:
        return self.nacin != "0"

    # ---------------------------------------------------------------------------------------- zapis
    def zapisi(self, oznaka: str) -> None:
        k = Krsitev(oznaka, threading.current_thread().name, _mesto())
        with self._zaklep:
            self.krsitve.append(k)

    def oznaci(self) -> int:
        with self._zaklep:
            return len(self.krsitve)

    def od(self, oznaka: int) -> List[Krsitev]:
        with self._zaklep:
            return list(self.krsitve[oznaka:])

    # ---------------------------------------------------------------------------------------- ovijanje
    def ovij_razred(self, razred: type, pripada: Callable[[type], bool], predpona: str) -> int:
        """Ovije klicne atribute razreda in njegovih prednikov, ki pripadajo istemu prostoru (pripada)."""
        stevilo = 0
        for c in razred.__mro__:
            if c in self._razredi or not pripada(c):
                continue
            self._razredi.add(c)
            for ime, vrednost in list(vars(c).items()):
                if PRESKOCI.match(ime) or isinstance(vrednost, _Varovano) or VARNE.match(ime):
                    continue
                if not (callable(vrednost) or isinstance(vrednost, (staticmethod, classmethod))):
                    continue
                # Ugnezdeni razredi (nastevanja Qt: QQuickView.ResizeMode) in signali Qt niso klici vmesnika - ovoj bi
                # iz njih naredil funkcijo (QQuickView.ResizeMode.SizeRootObjectToView, signal.connect padeta).
                if isinstance(vrednost, type) or type(vrednost).__name__ in ("Signal", "SignalInstance"):
                    continue
                try:
                    setattr(c, ime, _Varovano(vrednost, "%s.%s.%s" % (predpona, c.__name__, ime), self))
                    stevilo += 1
                except (AttributeError, TypeError):
                    self.neoviti.append("%s.%s" % (c.__name__, ime))     # vgrajen ali zaklenjen atribut
            # Gradnja predmeta (Gtk.Button(...), WebKit.WebView()) gre skozi __init__ prednika iz GObject: ovijemo ga
            # na razredu prostora, ce ga ta se ne doseze ovitega.
            # Odloca prvi __init__ po MRO (pri vmesnikih, npr. Gio.Action, je GObject.Object pred njim).
            izvirnik = next(vars(b)["__init__"] for b in c.__mro__ if "__init__" in vars(b))
            # object.__init__ (C) ni klic vmesnika; ovit bi dobil argumente konstruktorja in padel (TypeError).
            if not isinstance(izvirnik, _Varovano) and izvirnik is not object.__init__:
                try:
                    setattr(c, "__init__", _Varovano(izvirnik, "%s.%s()" % (predpona, c.__name__), self))
                    stevilo += 1
                except (AttributeError, TypeError):
                    self.neoviti.append("%s.__init__" % c.__name__)
        return stevilo

    def _ovij_funkcijo(self, funkcija, oznaka: str):
        varovalo = self

        def klic(*a, **k):
            if not varovalo.je_glavna():
                varovalo.zapisi(oznaka)
            return funkcija(*a, **k)
        klic.__name__ = oznaka.rsplit(".", 1)[-1]
        klic.__doc__ = getattr(funkcija, "__doc__", None)
        klic._safeer_varovano = True
        return klic

    def ovij_prostor_gi(self, ime: str) -> int:
        """Ovije ves nalozen imenski prostor GI (razrede in funkcije). Vrne stevilo ovitih atributov."""
        if ime in self.oviti:
            return 0
        modul = sys.modules.get("gi.repository." + ime)
        if modul is None:
            return 0
        import gi
        repo = gi.Repository.get_default()
        stevilo = 0
        moduli = {"gi.repository." + ime, "gi.overrides." + ime}

        def pripada(c: type) -> bool:
            return getattr(c, "__module__", "") in moduli

        for info in repo.get_infos(ime):
            ime_info = info.get_name()
            try:
                atribut = getattr(modul, ime_info)
            except Exception:  # noqa: BLE001 - nekateri vnosi typeliba v Pythonu niso na voljo (npr. zastareli)
                continue
            if isinstance(atribut, type):
                stevilo += self.ovij_razred(atribut, pripada, ime)
            elif callable(atribut) and not VARNE.match(ime_info) and not PRESKOCI.match(ime_info) \
                    and not getattr(atribut, "_safeer_varovano", False):
                setattr(modul, ime_info, self._ovij_funkcijo(atribut, "%s.%s" % (ime, ime_info)))
                stevilo += 1
        self.oviti[ime] = stevilo
        return stevilo

    def ovij_qt(self) -> int:
        stevilo = 0
        for modul_ime, razred_ime in RAZREDI_QT:
            kljuc = modul_ime + "." + razred_ime
            modul = sys.modules.get(modul_ime)
            if kljuc in self.oviti or modul is None or not hasattr(modul, razred_ime):
                continue
            razred = getattr(modul, razred_ime)
            ime_prostora = modul_ime.split(".", 1)[1]
            self.oviti[kljuc] = self.ovij_razred(razred, lambda c, r=razred: c is r, ime_prostora)
            stevilo += self.oviti[kljuc]
        return stevilo

    def namesti_nalozene(self) -> int:
        """Ovije vse, kar je od prejsnjega klica nalozeno (klice conftest pred in po vsakem preizkusu)."""
        if not self.vklopljeno:
            return 0
        if "gi.repository" not in sys.modules and "PySide6" not in sys.modules:
            return 0
        stevilo = 0
        for ime in PROSTORI_GI:
            stevilo += self.ovij_prostor_gi(ime)
        stevilo += self.ovij_qt()
        return stevilo

    def povzetek(self, najvec: int = 40) -> Optional[str]:
        with self._zaklep:
            krsitve = list(self.krsitve)
        if not krsitve:
            return None
        po_klicu: dict = {}
        for k in krsitve:
            po_klicu.setdefault(k.klic, []).append(k)
        vrstice = ["Vmesnik izven glavne niti: %d klicev, %d razlicnih (varovalo_niti, SAFEER_VAROVALO_NITI=%s)"
                   % (len(krsitve), len(po_klicu), self.nacin)]
        for klic, ks in sorted(po_klicu.items(), key=lambda x: -len(x[1]))[:najvec]:
            vrstice.append("- %dx %s (nit %r)\n%s" % (len(ks), klic, ks[0].nit, ks[0].mesto))
        return "\n".join(vrstice)


__all__ = ["Varovalo", "Krsitev", "PROSTORI_GI", "RAZREDI_QT", "je_glavna_nit"]
