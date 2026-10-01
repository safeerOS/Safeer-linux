"""Datoteke za Safeer OS na Linuxu: uporabnikove mape, pregled mape, iskanje in odpiranje.

Datoteke odpira program, ki ga ima uporabnik v Mintu nastavljenega za to vrsto (xdg-open /
Gio), mape pa Nemo, ce zeli vec, kot pokaze Safeer OS. Ustvari mapo ali datoteko in preimenuje
na uporabnikovo zahtevo; nicesar ne prepise, brisanje gre samo v Smeti.
"""

from __future__ import annotations

import mimetypes
import os
import re
import shutil
import subprocess
import time
from collections import deque
from typing import List, Optional

NAJVEC_V_MAPI = 600
NAJVEC_ZADETKOV = 60

#: Uporabnikove mape XDG v vrstnem redu, kot jih pokaze Safeer OS.
MAPE = ("DESKTOP", "DOCUMENTS", "DOWNLOAD", "PICTURES", "MUSIC", "VIDEOS")
PRIVZETO = {"DESKTOP": "Desktop", "DOCUMENTS": "Documents", "DOWNLOAD": "Downloads", "PICTURES": "Pictures",
            "MUSIC": "Music", "VIDEOS": "Videos"}


def uporabniske_mape(dom: Optional[str] = None) -> List[dict]:
    dom = dom or os.path.expanduser("~")
    nastavljene = {}
    try:
        with open(os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(dom, ".config"),
                               "user-dirs.dirs"), encoding="utf-8") as f:
            for vrstica in f:
                m = re.match(r'\s*XDG_([A-Z]+)_DIR="(.*)"\s*$', vrstica)
                if m:
                    nastavljene[m.group(1)] = m.group(2).replace("$HOME", dom)
    except Exception:
        pass
    izhod = [{"vrsta": "HOME", "pot": dom, "ime": os.path.basename(dom)}]
    for vrsta in MAPE:
        pot = nastavljene.get(vrsta) or os.path.join(dom, PRIVZETO[vrsta])
        if os.path.isdir(pot) and os.path.realpath(pot) != os.path.realpath(dom):
            izhod.append({"vrsta": vrsta, "pot": pot, "ime": os.path.basename(pot.rstrip("/"))})
    return izhod


def vrsta_datoteke(ime: str, je_mapa: bool = False) -> str:
    """Groba vrsta za ikono na strani: mapa, slika, video, zvok, dokument, arhiv, program, drugo."""
    if je_mapa:
        return "mapa"
    mime = mimetypes.guess_type(ime)[0] or ""
    if mime.startswith("image/"):
        return "slika"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "zvok"
    konc = os.path.splitext(ime)[1].lower()
    if konc in (".zip", ".tar", ".gz", ".xz", ".bz2", ".7z", ".rar", ".zst", ".deb"):
        return "arhiv"
    if konc in (".appimage", ".sh", ".run", ".exe"):
        return "program"
    if mime.startswith("text/") or konc in (".pdf", ".odt", ".ods", ".odp", ".doc", ".docx", ".xls", ".xlsx",
                                            ".ppt", ".pptx", ".md", ".rtf", ".epub", ".json", ".csv"):
        return "dokument"
    return "drugo"


def _element(pot: str, ime: str) -> Optional[dict]:
    try:
        st = os.stat(pot)
    except OSError:
        return None
    je_mapa = os.path.isdir(pot)
    return {"ime": ime, "pot": pot, "mapa": je_mapa, "velikost": 0 if je_mapa else st.st_size,
            "spremenjeno": st.st_mtime, "vrsta": vrsta_datoteke(ime, je_mapa)}


def preglej(pot: str, skrite: bool = False) -> dict:
    """Vsebina mape: mape najprej, nato datoteke; oboje po abecedi."""
    pot = os.path.abspath(os.path.expanduser(str(pot or "~")))
    if not os.path.isdir(pot):
        return {"pot": pot, "napaka": "ni_mape", "elementi": []}
    try:
        imena = os.listdir(pot)
    except PermissionError:
        return {"pot": pot, "napaka": "ni_dovoljenja", "elementi": []}
    except OSError:
        return {"pot": pot, "napaka": "ni_mape", "elementi": []}
    elementi = []
    for ime in imena:
        if not skrite and ime.startswith("."):
            continue
        e = _element(os.path.join(pot, ime), ime)
        if e is not None:
            elementi.append(e)
    elementi.sort(key=lambda e: (not e["mapa"], e["ime"].lower()))
    stars = os.path.dirname(pot) if pot != "/" else ""
    return {"pot": pot, "stars": stars, "napaka": "", "skupaj": len(elementi),
            "elementi": elementi[:NAJVEC_V_MAPI]}


#: Mape, v katerih so datoteke programov, ne uporabnikove (iskanje jih preskoci).
PRESKOCI = {"node_modules", "__pycache__", "snap", "site-packages", "dist-packages", "venv", ".venv", "build", "dist",
            "Applications", "go", "resources", "target", "vendor"}


def isci(niz: str, dom: Optional[str] = None, rok: float = 1.5) -> List[dict]:
    """Datoteke in mape v domaci mapi, katerih ime vsebuje niz: najprej plitve (po sirini),
    brez skritih in brez map s programsko kodo; najvec 1,5 s."""
    niz = str(niz or "").strip().lower()
    if len(niz) < 2:
        return []
    dom = dom or os.path.expanduser("~")
    konec = time.monotonic() + rok
    zadetki: List[dict] = []
    vrsta = deque([dom])
    while vrsta and time.monotonic() < konec:
        mapa = vrsta.popleft()
        try:
            vnosi = sorted(os.scandir(mapa), key=lambda v: v.name.lower())
        except OSError:
            continue
        for v in vnosi:
            if v.name.startswith("."):
                continue
            try:
                je_mapa = v.is_dir(follow_symlinks=False)
            except OSError:
                continue
            if je_mapa and v.name not in PRESKOCI:
                vrsta.append(v.path)
            if niz in v.name.lower():
                e = _element(v.path, v.name)
                if e is not None:
                    zadetki.append(e)
                    if len(zadetki) >= NAJVEC_ZADETKOV:
                        return zadetki
    return zadetki


def odpri(pot: str) -> bool:
    """Odpre datoteko s privzetim programom oz. mapo v Nemu."""
    pot = os.path.abspath(os.path.expanduser(str(pot or "")))
    if not os.path.exists(pot):
        return False
    for ukaz in (["xdg-open", pot], ["gio", "open", pot]):
        if shutil.which(ukaz[0]) is None:
            continue
        try:
            subprocess.Popen(ukaz, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return True
        except Exception:
            continue
    return False


def pokazi_v_mapi(pot: str) -> bool:
    """Odpre Nemo z oznaceno datoteko."""
    pot = os.path.abspath(os.path.expanduser(str(pot or "")))
    if not os.path.exists(pot) or shutil.which("nemo") is None:
        return False
    try:
        subprocess.Popen(["nemo", pot], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ ustvarjanje (desni klik v Datotekah)
# Kot v Nemu: nova mapa in nova datoteka (prazna, besedilna, dokument/preglednica/predstavitev
# LibreOffice ali predloga iz mape Predloge). Nic obstojecega se ne prepise; brisanje gre v Smeti.

#: Vrste novih datotek: kljuc -> (koncnica, MIME za ODF ali None).
NOVE_VRSTE = {
    "prazna": ("", None),
    "besedilo": (".txt", None),
    "dokument": (".odt", "application/vnd.oasis.opendocument.text"),
    "preglednica": (".ods", "application/vnd.oasis.opendocument.spreadsheet"),
    "predstavitev": (".odp", "application/vnd.oasis.opendocument.presentation"),
}
_ODF_TELO = {
    "application/vnd.oasis.opendocument.text": "<office:text><text:p/></office:text>",
    "application/vnd.oasis.opendocument.spreadsheet":
        "<office:spreadsheet><table:table table:name=\"List1\"><table:table-row><table:table-cell/>"
        "</table:table-row></table:table></office:spreadsheet>",
    "application/vnd.oasis.opendocument.presentation":
        "<office:presentation><draw:page draw:name=\"page1\"/></office:presentation>",
}


def _prosto_ime(mapa: str, ime: str) -> str:
    """Ime, ki v mapi se ne obstaja: »Nova mapa«, »Nova mapa (2)« ..."""
    koren, konc = os.path.splitext(ime) if not os.path.isdir(os.path.join(mapa, ime)) else (ime, "")
    kandidat, n = ime, 2
    while os.path.lexists(os.path.join(mapa, kandidat)):
        kandidat = "%s (%d)%s" % (koren, n, konc)
        n += 1
    return kandidat


def _preveri_mapo(mapa: str) -> str:
    from core import link_urejanje
    mapa = os.path.abspath(os.path.expanduser(str(mapa or "")))
    if not os.path.isdir(mapa):
        raise link_urejanje.NapakaUrejanja("ni_mape")
    if not os.access(mapa, os.W_OK | os.X_OK):
        raise link_urejanje.NapakaUrejanja("ni_dovoljenja")
    return mapa


def _odf(pot: str, mime: str) -> None:
    import zipfile
    ns = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
          'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
          'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
          'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" office:version="1.3"')
    vsebina = ('<?xml version="1.0" encoding="UTF-8"?><office:document-content %s><office:body>%s'
               '</office:body></office:document-content>' % (ns, _ODF_TELO[mime]))
    manifest = ('<?xml version="1.0" encoding="UTF-8"?><manifest:manifest '
                'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3">'
                '<manifest:file-entry manifest:full-path="/" manifest:media-type="%s"/>'
                '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
                '</manifest:manifest>' % mime)
    with zipfile.ZipFile(pot, "x") as z:
        # mimetype mora biti prvi in nestisnjen (specifikacija ODF).
        z.writestr(zipfile.ZipInfo("mimetype"), mime, compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/manifest.xml", manifest, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("content.xml", vsebina, compress_type=zipfile.ZIP_DEFLATED)


def predloge() -> List[dict]:
    """Datoteke iz uporabnikove mape Predloge (XDG TEMPLATES) - kot »Ustvari nov dokument« v Nemu."""
    mapa = ""
    try:
        r = subprocess.run(["xdg-user-dir", "TEMPLATES"], capture_output=True, text=True, timeout=3)
        mapa = r.stdout.strip()
    except Exception:
        pass
    if not mapa or mapa == os.path.expanduser("~") or not os.path.isdir(mapa):
        return []
    izid = []
    for ime in sorted(os.listdir(mapa), key=str.lower)[:40]:
        pot = os.path.join(mapa, ime)
        if not ime.startswith(".") and os.path.isfile(pot):
            izid.append({"ime": os.path.splitext(ime)[0], "pot": pot, "vrsta": vrsta_datoteke(ime)})
    return izid


def ustvari_mapo(mapa: str, ime: str) -> dict:
    """{"ok", "pot"} ali {"ok": False, "napaka"}; obstojecega imena ne prepise (doda (2), (3) ...)."""
    from core import link_urejanje
    try:
        mapa = _preveri_mapo(mapa)
        ime = _prosto_ime(mapa, link_urejanje.varno_ime(ime or "Nova mapa"))
        pot = os.path.join(mapa, ime)
        os.mkdir(pot)
        return {"ok": True, "pot": pot, "ime": ime}
    except link_urejanje.NapakaUrejanja as e:
        return {"ok": False, "napaka": str(e)}
    except OSError:
        return {"ok": False, "napaka": "ni_dovoljenja"}


def ustvari_datoteko(mapa: str, ime: str, vrsta: str = "prazna", predloga: str = "") -> dict:
    """Nova datoteka: prazna, besedilna, prazen dokument ODF ali kopija predloge iz mape Predloge."""
    from core import link_urejanje
    try:
        mapa = _preveri_mapo(mapa)
        ime = link_urejanje.varno_ime(ime or "Nova datoteka")
        if predloga:
            dovoljene = {p["pot"] for p in predloge()}
            if predloga not in dovoljene:
                raise link_urejanje.NapakaUrejanja("ni_predloge")
            konc = os.path.splitext(predloga)[1]
        else:
            konc, mime = NOVE_VRSTE.get(vrsta, NOVE_VRSTE["prazna"])
        if konc and not ime.lower().endswith(konc.lower()):
            ime += konc
        ime = _prosto_ime(mapa, ime)
        pot = os.path.join(mapa, ime)
        if predloga:
            with open(predloga, "rb") as v, open(pot, "xb") as c:
                shutil.copyfileobj(v, c)
        elif mime:
            _odf(pot, mime)
        else:
            with open(pot, "x", encoding="utf-8"):
                pass
        return {"ok": True, "pot": pot, "ime": ime}
    except link_urejanje.NapakaUrejanja as e:
        return {"ok": False, "napaka": str(e)}
    except FileExistsError:
        return {"ok": False, "napaka": "obstaja"}
    except OSError:
        return {"ok": False, "napaka": "ni_dovoljenja"}


def preimenuj(pot: str, novo_ime: str) -> dict:
    from core import link_urejanje
    try:
        nova = link_urejanje.preimenuj(os.path.abspath(os.path.expanduser(str(pot or ""))), novo_ime)
        return {"ok": True, "pot": nova}
    except link_urejanje.NapakaUrejanja as e:
        return {"ok": False, "napaka": str(e)}


def v_smeti(pot: str) -> dict:
    """Nikoli trajno: v Smeti, od koder se datoteka obnovi (Nemo -> Smeti)."""
    from core import link_urejanje
    pot = os.path.abspath(os.path.expanduser(str(pot or "")))
    if pot in ("/", os.path.expanduser("~")):
        return {"ok": False, "napaka": "ni_dovoljeno"}
    try:
        link_urejanje.v_smeti(pot)
        return {"ok": True}
    except link_urejanje.NapakaUrejanja as e:
        return {"ok": False, "napaka": str(e)}
