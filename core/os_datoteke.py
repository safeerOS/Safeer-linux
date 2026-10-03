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

NAJVEC_V_MAPI = 5000
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


#: Malo prostora: manj kot 10 % diska ali manj kot 5 GB (kar nastopi prej).
MALO_DELEZ = 0.10
MALO_BAJTOV = 5 * 1024 ** 3
#: Najmanjsa datoteka, ki jo ponudimo za shranjevanje na drugo napravo.
NAJMANJ_VELIKA = 100 * 1024 ** 2


def prostor(dom: Optional[str] = None) -> dict:
    """Prostor na disku domace mape (takoj, brez pregledovanja): skupaj, prosto in ali ga je malo."""
    try:
        st = os.statvfs(dom or os.path.expanduser("~"))
    except OSError:
        return {"skupaj": 0, "prosto": -1, "malo": False}
    skupaj, prosto = st.f_blocks * st.f_frsize, st.f_bavail * st.f_frsize
    return {"skupaj": skupaj, "prosto": prosto, "malo": prosto < MALO_BAJTOV or (skupaj > 0 and prosto < skupaj * MALO_DELEZ)}


def najvecje(dom: Optional[str] = None, koliko: int = 12, rok: float = 1.5) -> List[dict]:
    """Najvecje datoteke v domaci mapi (vsaj 100 MB), za shranjevanje na drugo napravo v Linku.
    Kot isci(): brez skritih map in map s programsko kodo, najvec `rok` sekund - brez opaznega zastoja."""
    dom = dom or os.path.expanduser("~")
    konec = time.monotonic() + rok
    najdene: List[tuple] = []
    vrsta = deque([dom])
    while vrsta and time.monotonic() < konec:
        mapa = vrsta.popleft()
        try:
            vnosi = list(os.scandir(mapa))
        except OSError:
            continue
        for v in vnosi:
            if v.name.startswith("."):
                continue
            try:
                if v.is_dir(follow_symlinks=False):
                    if v.name not in PRESKOCI:
                        vrsta.append(v.path)
                elif v.is_file(follow_symlinks=False):
                    velikost = v.stat(follow_symlinks=False).st_size
                    if velikost >= NAJMANJ_VELIKA:
                        najdene.append((velikost, v.path, v.name))
            except OSError:
                continue
    najdene.sort(reverse=True)
    izid = []
    for _, pot, ime in najdene[:koliko]:
        e = _element(pot, ime)
        if e is not None:
            izid.append(e)
    return izid


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


# ====================================================================== upravljanje (kopiraj, premakni, smeti, nosilci)
# Safeer OS ne nadomesca Nema, a osnovna opravila z datotekami morajo biti na voljo tam, kjer uporabnik je:
# kopiraj/premakni, pogled v Smeti z obnovitvijo, nosilci (USB, drugi diski), lastnosti in slicice.

#: Najvec datotek ali map v enem lepljenju (zascita pred pomoto, npr. izbrana cela domaca mapa).
NAJVEC_NAENKRAT = 500


def _koda_napake(e: OSError) -> str:
    import errno
    if e.errno in (errno.ENOSPC, errno.EDQUOT):
        return "ni_prostora"
    if e.errno in (errno.EACCES, errno.EPERM, errno.EROFS):
        return "ni_dovoljenja"
    return "napaka"


def prilepi(viri, cilj_mapa: str, premakni: bool = False) -> dict:
    """Kopira ali premakne datoteke in mape v mapo `cilj_mapa`. Obstojecega nikoli ne prepise (dobi ime »ime (2)«),
    mape ne kopira same vase, domace mape in korena se ne dotakne. Vrne {"ok", "narejeno": [poti], "napake": [...]}."""
    from core import link_urejanje
    try:
        cilj = _preveri_mapo(cilj_mapa)
    except link_urejanje.NapakaUrejanja as e:
        return {"ok": False, "napaka": str(e), "narejeno": [], "napake": []}
    seznam = [os.path.abspath(os.path.expanduser(str(v))) for v in (viri if isinstance(viri, (list, tuple)) else [viri]) if v]
    if not seznam or len(seznam) > NAJVEC_NAENKRAT:
        return {"ok": False, "napaka": "prevec" if seznam else "ni_datoteke", "narejeno": [], "napake": []}
    dom = os.path.expanduser("~")
    narejeno, napake = [], []
    for vir in seznam:
        ime = os.path.basename(vir.rstrip(os.sep))
        if not os.path.lexists(vir):
            napake.append({"pot": vir, "napaka": "ni_datoteke"})
            continue
        if vir in ("/", dom) or not ime:
            napake.append({"pot": vir, "napaka": "ni_dovoljeno"})
            continue
        je_mapa = os.path.isdir(vir) and not os.path.islink(vir)
        prava_vir, prava_cilj = os.path.realpath(vir), os.path.realpath(cilj)
        if je_mapa and (prava_cilj == prava_vir or prava_cilj.startswith(prava_vir + os.sep)):
            napake.append({"pot": vir, "napaka": "vase"})
            continue
        if premakni and os.path.realpath(os.path.dirname(vir)) == prava_cilj:
            continue                                    # ze je v tej mapi: nic za narediti
        nova = os.path.join(cilj, _prosto_ime(cilj, ime))
        try:
            if premakni:
                shutil.move(vir, nova)
            elif je_mapa:
                shutil.copytree(vir, nova, symlinks=True)
            else:
                shutil.copy2(vir, nova, follow_symlinks=False)
            narejeno.append(nova)
        except (OSError, shutil.Error) as e:
            # Napol narejene kopije ne pustimo za sabo (izvirnik je pri kopiranju nedotaknjen).
            if not premakni and os.path.lexists(nova):
                try:
                    shutil.rmtree(nova) if os.path.isdir(nova) and not os.path.islink(nova) else os.remove(nova)
                except OSError:
                    pass
            napake.append({"pot": vir, "napaka": _koda_napake(e) if isinstance(e, OSError) else "napaka"})
    return {"ok": bool(narejeno) or not napake, "narejeno": narejeno, "napake": napake}


# ---------------------------------------------------------------------- vlecenje med programi (text/uri-list)
def poti_iz_naslovov(naslovi) -> list:
    """Poti datotek tega racunalnika iz seznama naslovov, ki ga program poslje ob vlecenju datotek (text/uri-list).
    Kar ni datoteka tega racunalnika (http..., file://drug-racunalnik/...), izpade; najvec NAJVEC_NAENKRAT."""
    import socket
    import urllib.parse
    tukaj = {"", "localhost", socket.gethostname().lower()}
    poti: list = []
    for naslov in list(naslovi or []):
        try:
            deli = urllib.parse.urlsplit(str(naslov).strip())
        except ValueError:
            continue
        if deli.scheme.lower() != "file" or (deli.netloc or "").lower() not in tukaj:
            continue
        pot = urllib.parse.unquote(deli.path, errors="surrogateescape")
        if not pot.startswith("/") or "\x00" in pot:
            continue
        pot = os.path.normpath(pot)
        if pot not in poti:
            poti.append(pot)
        if len(poti) >= NAJVEC_NAENKRAT:
            break
    return poti


def naslovi_iz_poti(poti) -> list:
    """Naslovi file:// obstojecih datotek in map (za vlecenje v drug program); cesar ni, izpade."""
    import urllib.parse
    naslovi: list = []
    for pot in list(poti or [])[:NAJVEC_NAENKRAT]:
        pot = str(pot)
        if os.path.isabs(pot) and os.path.lexists(pot):
            naslovi.append("file://" + urllib.parse.quote(os.path.normpath(pot), safe="/", errors="surrogateescape"))
    return naslovi


# ---------------------------------------------------------------------- Smeti (specifikacija freedesktop, domaca)
def _mapa_smeti() -> str:
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "Trash")


def _velikost_poti(pot: str, rok: float) -> int:
    """Velikost datoteke ali (do roka) vsebine mape."""
    try:
        if not os.path.isdir(pot) or os.path.islink(pot):
            return os.lstat(pot).st_size
    except OSError:
        return 0
    skupaj, konec = 0, time.monotonic() + rok
    for koren, _mape, datoteke in os.walk(pot):
        for d in datoteke:
            try:
                skupaj += os.lstat(os.path.join(koren, d)).st_size
            except OSError:
                pass
        if time.monotonic() > konec:
            break
    return skupaj


def smeti() -> dict:
    """Vsebina Smeti: najnovejse najprej; `id` je ime v Smeteh (za obnovitev), `izvirna` pot, kjer je bila datoteka."""
    import datetime
    import urllib.parse
    koren = _mapa_smeti()
    datoteke, info = os.path.join(koren, "files"), os.path.join(koren, "info")
    elementi = []
    try:
        imena = os.listdir(datoteke)
    except OSError:
        imena = []
    for ime in imena:
        pot = os.path.join(datoteke, ime)
        izvirna, izbrisano = "", 0.0
        try:
            with open(os.path.join(info, ime + ".trashinfo"), encoding="utf-8", errors="replace") as f:
                for v in f:
                    if v.startswith("Path="):
                        izvirna = urllib.parse.unquote(v[5:].strip())
                    elif v.startswith("DeletionDate="):
                        try:
                            izbrisano = datetime.datetime.strptime(v[13:].strip()[:19], "%Y-%m-%dT%H:%M:%S").timestamp()
                        except ValueError:
                            pass
        except OSError:
            pass
        if izvirna and not os.path.isabs(izvirna):
            izvirna = os.path.join(os.path.dirname(koren), izvirna)
        je_mapa = os.path.isdir(pot) and not os.path.islink(pot)
        prikaz = os.path.basename(izvirna) or ime
        elementi.append({"id": ime, "ime": prikaz, "pot": pot, "izvirna": izvirna, "izbrisano": izbrisano, "mapa": je_mapa,
                         "velikost": 0 if je_mapa else _velikost_poti(pot, 0), "vrsta": vrsta_datoteke(prikaz, je_mapa)})
    elementi.sort(key=lambda e: -e["izbrisano"])
    return {"skupaj": len(elementi), "elementi": elementi[:NAJVEC_V_MAPI]}


def _id_v_smeteh(id_: str) -> Optional[str]:
    ime = str(id_ or "")
    if not ime or "/" in ime or ime in (".", ".."):
        return None
    pot = os.path.join(_mapa_smeti(), "files", ime)
    return pot if os.path.lexists(pot) else None


def obnovi_iz_smeti(id_: str) -> dict:
    """Vrne datoteko tja, kjer je bila; ce je tam medtem nastala druga, dobi ime »ime (2)«."""
    import urllib.parse
    pot = _id_v_smeteh(id_)
    if pot is None:
        return {"ok": False, "napaka": "ni_datoteke"}
    opis = os.path.join(_mapa_smeti(), "info", os.path.basename(pot) + ".trashinfo")
    izvirna = ""
    try:
        with open(opis, encoding="utf-8", errors="replace") as f:
            for v in f:
                if v.startswith("Path="):
                    izvirna = urllib.parse.unquote(v[5:].strip())
    except OSError:
        pass
    if not izvirna:
        return {"ok": False, "napaka": "ni_izvirne_poti"}
    if not os.path.isabs(izvirna):
        izvirna = os.path.join(os.path.dirname(_mapa_smeti()), izvirna)
    mapa = os.path.dirname(izvirna)
    try:
        os.makedirs(mapa, exist_ok=True)
        cilj = os.path.join(mapa, _prosto_ime(mapa, os.path.basename(izvirna)))
        shutil.move(pot, cilj)
    except OSError as e:
        return {"ok": False, "napaka": _koda_napake(e)}
    try:
        os.remove(opis)
    except OSError:
        pass
    return {"ok": True, "pot": cilj}


def izprazni_smeti() -> dict:
    """TRAJNO izbrise vsebino Smeti. Klicatelj (Safeer OS) mora prej dobiti potrditev v sistemskem oknu."""
    koren = _mapa_smeti()
    izbrisano = 0
    for podmapa in ("files", "info"):
        mapa = os.path.join(koren, podmapa)
        try:
            imena = os.listdir(mapa)
        except OSError:
            continue
        for ime in imena:
            pot = os.path.join(mapa, ime)
            try:
                if os.path.isdir(pot) and not os.path.islink(pot):
                    shutil.rmtree(pot)
                else:
                    os.remove(pot)
                izbrisano += podmapa == "files"
            except OSError:
                pass
    return {"ok": True, "izbrisano": izbrisano}


# ---------------------------------------------------------------------- nosilci (USB, drugi diski, omrezna mesta)
_SISTEMSKE_TOCKE = ("/", "/boot", "/boot/efi", "/home", "/var", "/usr", "/tmp", "[SWAP]")


def _nosilci_lsblk(izpis: str, uporabnik: str) -> List[dict]:
    """Nosilci iz izpisa `lsblk -J -b -o NAME,PATH,LABEL,SIZE,TYPE,RM,HOTPLUG,MOUNTPOINT,FSTYPE` (cista funkcija)."""
    import json as _json
    try:
        drevo = _json.loads(izpis).get("blockdevices") or []
    except ValueError:
        return []
    izid = []

    def obisci(n: dict, odstranljiv: bool) -> None:
        odstranljiv = odstranljiv or bool(n.get("rm")) or bool(n.get("hotplug"))
        tocka = n.get("mountpoint") or ""
        if tocka and tocka not in _SISTEMSKE_TOCKE and not tocka.startswith(("/snap/", "/boot/", "/var/", "/sys", "/proc", "/dev")):
            mediji = tocka.startswith(("/media/" + uporabnik + "/", "/run/media/" + uporabnik + "/", "/mnt/", "/media/"))
            if mediji or odstranljiv:
                izid.append({"ime": str(n.get("label") or os.path.basename(tocka) or n.get("name") or ""), "pot": tocka,
                             "naprava": str(n.get("path") or ""), "odstranljiv": odstranljiv,
                             "velikost": int(n.get("size") or 0)})
        for o in n.get("children") or []:
            obisci(o, odstranljiv)

    for n in drevo:
        obisci(n, False)
    return izid


def nosilci() -> List[dict]:
    """Priklopljeni nosilci poleg sistemskega diska (USB kljuci, zunanji in drugi diski) ter omrezna mesta (gvfs)."""
    import getpass
    izid: List[dict] = []
    if shutil.which("lsblk"):
        try:
            r = subprocess.run(["lsblk", "-J", "-b", "-o", "NAME,PATH,LABEL,SIZE,TYPE,RM,HOTPLUG,MOUNTPOINT,FSTYPE"],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                izid = _nosilci_lsblk(r.stdout, getpass.getuser())
        except (OSError, subprocess.SubprocessError):
            pass
    for n in izid:
        try:
            st = os.statvfs(n["pot"])
            n["prosto"] = st.f_bavail * st.f_frsize
        except OSError:
            n["prosto"] = 0
    gvfs = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid(), "gvfs")
    try:
        for ime in sorted(os.listdir(gvfs)):
            izid.append({"ime": ime.split(",")[0].replace(":host=", " ").replace("smb-share:server=", ""), "pot": os.path.join(gvfs, ime),
                         "naprava": "", "odstranljiv": False, "velikost": 0, "prosto": 0, "omrezje": True})
    except OSError:
        pass
    return izid


def izvrzi(pot: str) -> dict:
    """Varno odstrani nosilec: odklopi datotecni sistem in (USB) izklopi napravo. Samo nosilci s seznama `nosilci()`."""
    cilj = next((n for n in nosilci() if n["pot"] == str(pot or "") and n.get("naprava")), None)
    if cilj is None or not shutil.which("udisksctl"):
        return {"ok": False, "napaka": "ni_nosilca"}
    try:
        r = subprocess.run(["udisksctl", "unmount", "-b", cilj["naprava"]], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return {"ok": False, "napaka": "zaseden" if "busy" in (r.stderr + r.stdout).lower() else "napaka"}
        if cilj.get("odstranljiv"):
            subprocess.run(["udisksctl", "power-off", "-b", cilj["naprava"]], capture_output=True, text=True, timeout=30)
        return {"ok": True}
    except (OSError, subprocess.SubprocessError):
        return {"ok": False, "napaka": "napaka"}


# ---------------------------------------------------------------------- lastnosti
def lastnosti(pot: str) -> dict:
    import pwd
    import stat as _stat
    pot = os.path.abspath(os.path.expanduser(str(pot or "")))
    try:
        st = os.lstat(pot)
    except OSError:
        return {"ok": False, "napaka": "ni_datoteke"}
    je_povezava = _stat.S_ISLNK(st.st_mode)
    je_mapa = os.path.isdir(pot) and not je_povezava
    try:
        lastnik = pwd.getpwuid(st.st_uid).pw_name
    except KeyError:
        lastnik = str(st.st_uid)
    izid = {"ok": True, "ime": os.path.basename(pot) or pot, "pot": pot, "mapa": je_mapa,
            "vrsta": vrsta_datoteke(os.path.basename(pot), je_mapa), "mime": "inode/directory" if je_mapa else (mimetypes.guess_type(pot)[0] or ""),
            "velikost": _velikost_poti(pot, 1.0), "spremenjeno": st.st_mtime, "pravice": _stat.filemode(st.st_mode),
            "lastnik": lastnik, "pisljivo": os.access(pot, os.W_OK)}
    if je_povezava:
        try:
            izid["povezava"] = os.readlink(pot)
        except OSError:
            izid["povezava"] = ""
    if je_mapa:
        try:
            izid["vsebuje"] = len(os.listdir(pot))
        except OSError:
            izid["vsebuje"] = 0
    return izid


# ---------------------------------------------------------------------- slicice
SLICICA_VELIKOST = 256
_SLIKE = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff")


def _mapa_slicic() -> str:
    return os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "safeer-os", "slicice")


def slicica(pot: str) -> str:
    """Pot do slicice (PNG/JPEG) za sliko ali video; prazno, ce je ni mogoce dobiti. Najprej skupni predpomnilnik
    namizja (~/.cache/thumbnails, ki ga polni Nemo - tam so tudi slicice videov), sicer sliko pomanjsamo sami."""
    import hashlib
    import urllib.parse
    pot = os.path.abspath(str(pot or ""))
    try:
        st = os.stat(pot)
    except OSError:
        return ""
    if not os.path.isfile(pot):
        return ""
    uri = "file://" + urllib.parse.quote(pot)
    md5 = hashlib.md5(uri.encode("utf-8")).hexdigest()
    skupni = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "thumbnails")
    for podmapa in ("large", "normal", "x-large"):
        kandidat = os.path.join(skupni, podmapa, md5 + ".png")
        try:
            if os.stat(kandidat).st_mtime >= st.st_mtime - 1:
                return kandidat
        except OSError:
            pass
    if not pot.lower().endswith(_SLIKE) or st.st_size > 60 * 1024 * 1024:
        return ""
    cilj = os.path.join(_mapa_slicic(), md5 + ".jpg")
    try:
        if os.stat(cilj).st_mtime >= st.st_mtime:
            return cilj
    except OSError:
        pass
    try:
        from PIL import Image, ImageOps
        Image.MAX_IMAGE_PIXELS = 120_000_000
        os.makedirs(os.path.dirname(cilj), exist_ok=True)
        with Image.open(pot) as s:
            s = ImageOps.exif_transpose(s)
            s.thumbnail((SLICICA_VELIKOST, SLICICA_VELIKOST))
            if s.mode not in ("RGB", "L"):
                ozadje = Image.new("RGB", s.size, (16, 26, 43))
                ozadje.paste(s.convert("RGBA"), mask=s.convert("RGBA").split()[3])
                s = ozadje
            s.save(cilj + ".tmp", "JPEG", quality=82)
        os.replace(cilj + ".tmp", cilj)
        return cilj
    except Exception:  # noqa: BLE001 - poskodovana slika ali brez Pillow: brez slicice
        try:
            os.remove(cilj + ".tmp")
        except OSError:
            pass
        return ""


def slicice(poti, rok: float = 4.0) -> dict:
    """Slicice za vec datotek naenkrat (do roka): {pot: pot_slicice}; brez vnosa = slicice ni."""
    izid, konec = {}, time.monotonic() + rok
    for pot in list(poti or [])[:120]:
        if time.monotonic() > konec:
            break
        s = slicica(str(pot))
        if s:
            izid[str(pot)] = s
    return izid
