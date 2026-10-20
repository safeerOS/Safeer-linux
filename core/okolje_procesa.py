"""Okolje procesa (os.environ) med tekom: samo zamenjava vrednosti, ki ze obstajajo - nikoli dodajanje ali brisanje.

Ze uvoz GTK zazene niti (gmain, pool-spawner, llvmpipe - izmerjeno 19. 10. 2026: 1 nit pred `from gi.repository import
Gtk`, 9 po njem), pozneje se GDBus, WebKit in nase. glibc setenv/unsetenv pri dodajanju ali brisanju tabelo environ
prestavi ali realocira, getenv v drugi niti pa jo bere brez zaklepa - to je lahko sesutje (polni tek preizkusov se je
19. 10. 2026 sesul ob Gio.TestDBus, ki dela isto). Zamenjava vrednosti obstojece spremenljivke pa tabele ne premakne:
glibc na mestu zamenja kazalec in stare vrednosti ne sprosti.

Zato: kar bo proces med tekom zacasno spreminjal, mora obstajati ze pred prvo nitjo (pred_nitmi(), klice ga safeer_os.py
pred `import gi`). Prazna vrednost je za Qt enaka nenastavljeni (qEnvironmentVariableIsEmpty), zato je mesto rezervirano
brez spremembe obnasanja; programom, ki jih zazenemo, prazne ne damo (core/zasebni_webkit.okolje_za_zunanje).
"""
from __future__ import annotations

import os
from typing import Optional

#: Qt jih bere ob ustvarjanju QApplication. V procesu Safeer OS se to zgodi na zahtevo (okno aplikacije, delovna
#: povrsina brez varuha - core/os_lupina.pripravi), ko niti ze tecejo.
QT = ("QT_QPA_PLATFORMTHEME", "QT_QPA_PLATFORM", "QT_XCB_GL_INTEGRATION")

#: Proces jih prebere enkrat in jih programom, ki jih zazene, ne da naprej (varuh: vticnica obvestil, vticnica lupine,
#: obnova po sesutju; ponovni zagon Controla z oknom). Prej so se odstranile iz okolja v main() ali ob uvozu
#: safeer_control v procesu Safeer OS, ko so niti ze tekle.
PREVZETE = ("NOTIFY_SOCKET", "SAFEER_LUPINA_VTIC", "SAFEER_OBNOVA", "SAFEER_CONTROL_ODPRI", "SAFEER_SCIT_VTIC")

_pripravljeno = False
_prevzeto: dict = {}


def pred_nitmi() -> None:
    """Rezervira mesta za spremenljivke, ki jih bomo med tekom zamenjevali, in prevzame PREVZETE. Klicati samo, dokler
    tece ena nit."""
    global _pripravljeno
    for ime in QT:
        os.environ.setdefault(ime, "")
    for ime in PREVZETE:
        if ime in os.environ:
            _prevzeto[ime] = os.environ.pop(ime)
    _pripravljeno = True


def prevzemi(ime: str) -> str:
    """Vrednost spremenljivke iz PREVZETE (prevzete pred nitmi); ce je takrat ni bilo, jo prebere in odstrani zdaj
    (proces brez pred_nitmi(), npr. locena lupina z eno nitjo)."""
    if ime in _prevzeto:
        return _prevzeto.pop(ime)
    return os.environ.pop(ime, "") if ime in os.environ else ""


def pripravljeno() -> bool:
    return _pripravljeno


def zamenjaj(ime: str, vrednost: str) -> Optional[str]:
    """Nastavi vrednost in vrne prejsnjo (None, ce spremenljivke ni bilo). Ce obstaja, je to zamenjava na mestu."""
    prej = os.environ.get(ime)
    os.environ[ime] = vrednost
    return prej


def povrni(ime: str, prej: Optional[str]) -> None:
    """Vrne vrednost, ki jo je vrnil zamenjaj(). Spremenljivko izbrise samo, ce je prej res ni bilo (proces brez
    pred_nitmi(), npr. locena lupina, kjer tece ena nit)."""
    if prej is None:
        os.environ.pop(ime, None)
    else:
        os.environ[ime] = prej


def prazne_rezervacije(okolje: dict) -> dict:
    """Okolje za program, ki ga zazenemo: brez praznih rezervacij iz pred_nitmi() (enako kot pred njimi)."""
    for ime in QT:
        if okolje.get(ime) == "":
            del okolje[ime]
    return okolje
