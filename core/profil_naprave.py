"""Profil naprave: en vir resnice, koliko si Splet (Safeer OS) in Safeer Browser privoscita (lastnik 21. 10. 2026).

Smernica lastnika: naprave z veliko RAM (racunalniki, telefon z 12 GB) - vec procesov, vec niti slikanja, boljsa raba
GPU; TV in naprave z malo RAM - varcno. Peskovnik in vecprocesnost WebKita delata na obeh (izmerjeno na testnem PC
21. 10. 2026: vsak spletni proces v bwrap) in ju profil ne spreminja.

»polni«: MemTotal >= PRAG_POLNI_MB. Prag ni 8192: racunalnik z 8 GB pokaze MemTotal 7,4-7,8 GiB (vgrajen GPU in
strojna programska oprema si vzameta svoje; testni PC z 12 GB kaze 11,6 GB). 7 GiB loci »8 GB in vec« od »6 GB in
manj«. »varcni«: vse pod tem - za njega veljajo NESPREMENJENE danasnje vrednosti (core/pomnilnik), brez regresije.

Kaj profil spremeni in zakaj (viri v izhod/profil-procesi-131.md):
* Model predpomnilnika (WebKitCacheModel) je v WebKitGTK GLOBALEN (webkit_web_context_set_cache_model klice
  LegacyGlobalSettings::setCacheModel) in ga WebProcessCache prebere ob nastanku vsakega WebContext: samo
  PrimaryWebBrowser (WEB_BROWSER) vklopi predpomnilnik procesov - do RAM/256 MB procesov (najvec 32) za 5 min (ne-Cocoa).
  Varcni: DOCUMENT_BROWSER - brez predpomnilnika procesov, predpomnilnik v pomnilniku 96 namesto 128 MB, back-forward
  cache ostane (2 strani). Polni: WEB_BROWSER (omejitev stevila in casa je WebKitova; API za drugo mejo ni).
* MemoryPressureSettings: varcni kot danes; polni sprosti predpomnilnike sele pri 2/3 meje ubijanja (manj praznjenja).
* Niti slikanja Skia (WEBKIT_SKIA_CPU_PAINTING_THREADS, prebere jih spletni proces ob zagonu - okolje mora biti
  nastavljeno pred nitmi): polni jedra-1 (najvec 8) namesto privzete polovice jeder; varcni privzeto (kot danes).
* Mehka meja spletnih procesov (samo varcni): nad njo nov zavihek iste registrirane domene deli proces (related-view).
"""
from __future__ import annotations

import os
import re
from typing import Dict, Iterable, NamedTuple, Optional

from core import pomnilnik

#: MemTotal (MB), od katerega je profil »polni« (glej opis modula).
PRAG_POLNI_MB = 7 * 1024
#: PSS zavihka (izmerjeno 21. 10. 2026, testni PC: zavihek Wikipedije 104 MB PSS) - za mehko mejo procesov.
PSS_ZAVIHKA_MB = 104
#: Spletni procesi zavihkov smejo skupaj porabiti najvec toliksen del RAM-a, preden zacnejo deliti procese.
DELEZ_ZA_ZAVIHKE = 0.25
#: Pripone z dvema oznakama (»co.uk«), pri katerih je registrirana domena tri oznake. Ni celoten Public Suffix List -
#: zmota pomeni samo, da dve strani ne delita procesa (varno), nikoli da ga delita napacno (glej je_obcutljiva).
DVOJNE_PRIPONE = frozenset(("co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au", "co.jp", "ne.jp",
                            "or.jp", "com.br", "com.cn", "com.tr", "co.nz", "co.za", "com.mx", "co.in", "com.ar",
                            "gov.si", "org.si", "co.kr", "com.tw", "com.sg", "github.io", "gitlab.io", "blogspot.com"))
#: Gostitelji s prijavo, ki ne delijo procesa z ničemer (e-posta, prijava, placila) - poleg seznama bank Scita.
OBCUTLJIVI = ("mail.", "accounts.", "login.", "auth.", "signin.", "id.", "pay.", "wallet.", "bank.", "posta.",
              "outlook.live.com", "proton.me", "paypal.com", "gmail.com")


class Profil(NamedTuple):
    ime: str                       # »polni« ali »varcni«
    ram_mb: int
    jedra: int
    meja_strani_mb: int            # nad tem WebKit proces strani ustavi (kill threshold)
    meja_sprostitve_mb: int        # nad tem WebKit sprosti predpomnilnike (memory limit)
    model_predpomnilnika: str      # ime WebKit.CacheModel
    niti_slikanja_cpu: Optional[int]   # WEBKIT_SKIA_CPU_PAINTING_THREADS ali None (privzeto WebKita)
    meja_procesov: Optional[int]   # mehka meja spletnih procesov zavihkov ali None (brez deljenja)

    @property
    def polni(self) -> bool:
        return self.ime == "polni"


def iz_podatkov(ram_mb: int, jedra: int) -> Profil:
    """Profil iz kolicine RAM (MB) in stevila jeder - cista funkcija (preizkusi)."""
    ram_mb = int(ram_mb) if ram_mb and ram_mb > 0 else 4096
    jedra = int(jedra) if jedra and jedra > 0 else 2
    meja = pomnilnik.meja_strani_mb(ram_mb)
    if ram_mb >= PRAG_POLNI_MB:
        return Profil("polni", ram_mb, jedra, meja, meja * 2 // 3, "WEB_BROWSER",
                      min(8, jedra - 1) if jedra >= 4 else None, None)
    return Profil("varcni", ram_mb, jedra, meja, pomnilnik.meja_sprostitve_mb(ram_mb), "DOCUMENT_BROWSER", None,
                  max(3, int(ram_mb * DELEZ_ZA_ZAVIHKE) // PSS_ZAVIHKA_MB))


def ram_iz_meminfo(besedilo: str) -> int:
    """MemTotal iz besedila /proc/meminfo v MB; -1, ce ga ni."""
    m = re.search(r"^MemTotal:\s+(\d+)\s*kB", besedilo or "", re.M)
    return int(m.group(1)) // 1024 if m else -1


_trenutni: Optional[Profil] = None


def trenutni(pot_meminfo: str = "/proc/meminfo") -> Profil:
    """Profil te naprave (izracunan enkrat na proces)."""
    global _trenutni
    if _trenutni is None:
        try:
            with open(pot_meminfo, encoding="ascii") as d:
                ram = ram_iz_meminfo(d.read())
        except OSError:
            ram = pomnilnik.skupaj() // (1024 * 1024) if pomnilnik.skupaj() > 0 else -1
        _trenutni = iz_podatkov(ram, os.cpu_count() or 2)
    return _trenutni


def okolje_pred_nitmi(okolje: Optional[Dict[str, str]] = None, profil: Optional[Profil] = None) -> Dict[str, str]:
    """Spremenljivke za spletne procese (niti slikanja Skia). Klicati PRED `import gi` (AGENTS.md: okolje procesa se
    po zagonu niti ne spreminja; core/okolje_procesa.py). Vrednosti, ki jo je uporabnik ze nastavil, ne prepise.
    Vrne nastavljene spremenljivke."""
    okolje = os.environ if okolje is None else okolje
    profil = profil or trenutni()
    nastavljeno: Dict[str, str] = {}
    if profil.niti_slikanja_cpu and "WEBKIT_SKIA_CPU_PAINTING_THREADS" not in okolje:
        okolje["WEBKIT_SKIA_CPU_PAINTING_THREADS"] = nastavljeno["WEBKIT_SKIA_CPU_PAINTING_THREADS"] = \
            str(profil.niti_slikanja_cpu)
    return nastavljeno


def model_predpomnilnika(WebKit, profil: Optional[Profil] = None):
    """WebKit.CacheModel za profil."""
    return getattr(WebKit.CacheModel, (profil or trenutni()).model_predpomnilnika)


def _ima_zaslon() -> bool:
    """GDK ima privzeti zaslon (Gtk ze uvozen z require_version 4.0 v programu, ki klice nastavi_model)."""
    try:
        from gi.repository import Gdk
        return Gdk.Display.get_default() is not None
    except Exception:  # noqa: BLE001 - brez GDK ni zaslona
        return False


def nastavi_model(WebKit, kontekst=None, profil: Optional[Profil] = None) -> bool:
    """Globalni model predpomnilnika WebKita. Klicati PRED prvim lastnim WebContext: WebProcessCache prebere model ob
    nastanku konteksta (zato samo enkrat in zgodaj; poznejsi klic spremeni samo back-forward cache)."""
    if kontekst is None and not _ima_zaslon():
        # Brez zaslona (ukazna vrstica, npr. safeer_os.py --back-to-cinnamon) WebContext.get_default() sesuje proces
        # (SIGSEGV v gdk_display_prepare_gl, CI 39570038399, 21. 10. 2026) - tam spletnih strani tako ni.
        return False
    try:
        (kontekst or WebKit.WebContext.get_default()).set_cache_model(model_predpomnilnika(WebKit, profil))
        return True
    except Exception as napaka:  # noqa: BLE001 - WebKit brez API: ostane privzeti model
        print("[Splet] model predpomnilnika:", napaka, flush=True)
        return False


def registrirana_domena(gostitelj: str) -> str:
    """Priblizek registrirane domene (eTLD+1): zadnji dve oznaki, pri DVOJNE_PRIPONE tri. IP in ime brez pike vrneta
    gostitelja samega (z nicemer drugim ga ne delita)."""
    g = (gostitelj or "").lower().strip(".")
    deli = g.split(".")
    if len(deli) < 2 or re.fullmatch(r"[0-9.]+", g) or ":" in g:
        return g
    n = 3 if ".".join(deli[-2:]) in DVOJNE_PRIPONE and len(deli) >= 3 else 2
    return ".".join(deli[-n:])


def je_obcutljiva(gostitelj: str, banke: Iterable[str] = ()) -> bool:
    """Stran s prijavo/gesli (banka, e-posta, prijava, placila): svoj proces, nikoli deljen."""
    g = (gostitelj or "").lower()
    if any(g == b or g.endswith("." + b) for b in banke if b):
        return True
    return any(g.startswith(o) or g == o or g.endswith("." + o) for o in OBCUTLJIVI)


def deli_proces(profil: Profil, st_procesov: int, nov_gostitelj: str, zavihki: Iterable[tuple],
                banke: Iterable[str] = ()):
    """Pogled, s katerim nov zavihek deli spletni proces (related-view), ali None.

    zavihki: (pogled, gostitelj, sme_deliti) odprtih zavihkov. Samo varcni profil, samo nad mehko mejo procesov, samo
    ista registrirana domena; obcutljive strani (banka, e-posta, prijava) in zavihki, ki ne smejo deliti (zaspali,
    povezano okno, obrazec), nikoli."""
    if profil.meja_procesov is None or st_procesov < profil.meja_procesov or not nov_gostitelj:
        return None
    banke = tuple(banke)
    if je_obcutljiva(nov_gostitelj, banke):
        return None
    cilj = registrirana_domena(nov_gostitelj)
    for pogled, gostitelj, sme in zavihki:
        if sme and gostitelj and registrirana_domena(gostitelj) == cilj and not je_obcutljiva(gostitelj, banke):
            return pogled
    return None
