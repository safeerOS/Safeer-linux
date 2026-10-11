"""Programi z GitHuba v Safeer OS za Linux (lastnik, 11. 10. 2026): uporabnik brska po javnih repozitorijih, vidi
datoteke zadnjih izdaj in jih shrani v mapo, ki si jo izbere sam. Safeer nic ne namesti sam in nic ne priporoca -
iskanje vrne, kar vrne GitHub (razvrsceno po zvezdicah). Dostop je samo branje javnega API-ja brez prijave; prenos
je dovoljen le z github.com / *.githubusercontent.com prek https, v izbrano mapo, z enolicnim imenom (nic se ne prepise).
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import threading
import time
import urllib.parse
import urllib.request
import uuid
from typing import Callable, Dict, List, Optional

API = "https://api.github.com"
AGENT = "SafeerOS"
_REPO = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
DOVOLJENI = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com",
             "github-releases.githubusercontent.com", "codeload.github.com")
#: Koncnice, ki jih na Linuxu oznacimo kot »za Linux« (prikaz; shraniti je mogoce vse).
LINUX = (".deb", ".appimage", ".flatpak", ".flatpakref", ".rpm", ".snap", ".tar.gz", ".tar.xz", ".tar.zst", ".tgz", ".zip")
NAJVEC_MB = 4096


def _beri(url: str, odpri: Callable = urllib.request.urlopen, cas: float = 15) -> object:
    zahteva = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/vnd.github+json"})
    with odpri(zahteva, timeout=cas) as o:
        return json.loads(o.read(4 * 1024 * 1024).decode("utf-8"))


#: Zvrsti programov (kljuc -> besede v temah in opisu repozitorija). Prva zvrst z najvec zadetki zmaga.
ZVRSTI = {
    "mediji": ("media", "video", "music", "audio", "player", "podcast", "stream", "iptv", "radio", "youtube", "jellyfin", "kodi", "mpv"),
    "ustvarjanje": ("editor", "image", "photo", "graphics", "drawing", "design", "3d", "animation", "daw", "music-production", "paint"),
    "pisarna": ("office", "document", "pdf", "spreadsheet", "notes", "markdown", "calendar", "todo", "productivity", "ebook"),
    "splet": ("browser", "web", "rss", "download", "torrent", "email", "mail", "http"),
    "komunikacija": ("chat", "messenger", "matrix", "telegram", "signal", "xmpp", "irc", "voip", "video-call", "airdrop", "file-sharing", "share"),
    "igre": ("game", "games", "gaming", "emulator", "steam", "retro"),
    "razvoj": ("ide", "developer", "programming", "compiler", "git", "terminal", "cli", "sdk", "api", "devtools"),
    "sistem": ("system", "monitor", "backup", "disk", "file-manager", "launcher", "utility", "tool", "driver", "desktop"),
    "varnost": ("security", "privacy", "vpn", "password", "encryption", "firewall", "adblock", "2fa"),
}


def zvrst(teme: List[str], opis: str) -> str:
    """Zvrst programa iz tem (topics) in opisa repozitorija; 'drugo', ce ne vemo."""
    besedila = " ".join(teme or []).lower() + " " + (opis or "").lower()
    besede = set(re.findall(r"[a-z0-9][a-z0-9-]+", besedila))
    najboljsa, tock = "drugo", 0
    for k, kljucne in ZVRSTI.items():
        n = sum(2 if t in (teme or []) else 1 for t in kljucne if t in besede)
        if n > tock:
            najboljsa, tock = k, n
    return najboljsa


def sistem_datoteke(ime: str) -> str:
    """Za kateri sistem je datoteka: linux, windows, macos, android, ios ali drugo (npr. izvorna koda)."""
    n = (ime or "").lower()
    if n.endswith((".apk", ".aab", ".apkm", ".xapk")) or "android" in n:
        return "android"
    if n.endswith(".ipa") or re.search(r"\bios\b", n):
        return "ios"
    if n.endswith((".exe", ".msi", ".msix", ".appx")) or re.search(_WINDOWS, n):
        return "windows"
    if n.endswith((".dmg", ".pkg")) or re.search(r"macos|darwin|\bmac\b|osx|apple", n):
        return "macos"
    if za_linux(n) and (re.search(r"linux|\.deb$|\.rpm$|\.appimage$|\.flatpak|\.snap$", n)):
        return "linux"
    return "drugo"


def isci(niz: str, odpri: Callable = urllib.request.urlopen) -> dict:
    """Javni repozitoriji, ki ustrezajo nizu (najvec 20, po zvezdicah)."""
    n = str(niz or "").strip()[:100]
    if not n:
        return {"ok": True, "repozitoriji": []}
    q = urllib.parse.quote(n)
    try:
        d = _beri(f"{API}/search/repositories?q={q}&sort=stars&order=desc&per_page=20", odpri)
    except Exception as e:  # noqa: BLE001 - omejitev API (403), brez omrezja ...
        return {"ok": False, "napaka": "omejitev" if "403" in str(e) or "429" in str(e) else "omrezje"}
    izid = []
    for r in (d.get("items") or [])[:20]:
        teme = [str(x).lower() for x in (r.get("topics") or [])][:20]
        izid.append({"repo": r.get("full_name", ""), "opis": (r.get("description") or "")[:200],
                     "zvrst": zvrst(teme, r.get("description") or ""),
                     "zvezdice": int(r.get("stargazers_count") or 0), "licenca": ((r.get("license") or {}).get("spdx_id") or ""),
                     "posodobljeno": (r.get("pushed_at") or "")[:10], "arhiviran": bool(r.get("archived"))})
    return {"ok": True, "repozitoriji": izid}


_WINDOWS = r"windows|win32|win64|\bwin\b|mingw|msvc|\bw64\b|\bw32\b|-w64-|-w32-|win-?x64|win-?x86|win-?arm"
_DRUGI_SISTEMI = re.compile(r"(" + _WINDOWS + r"|macos|darwin|\bmac\b|osx|android|\bios\b|freebsd|\.exe$|\.msi$|\.dmg$|\.apk$)")
_ARHITEKTURE = {"x86_64": ("x86_64", "x86-64", "amd64", "x64", "linux64"), "aarch64": ("aarch64", "arm64", "arm-64"),
                "armv7l": ("armv7", "armhf", "arm32", "arm-32")}


def za_linux(ime: str) -> bool:
    """Datoteka za Linux: koncnica paketa/arhiva in nobene oznake drugega sistema v imenu."""
    n = ime.lower()
    return n.endswith(LINUX) and not _DRUGI_SISTEMI.search(n)


def za_ta_racunalnik(ime: str, stroj: str = "") -> bool:
    """Za Linux in za arhitekturo tega racunalnika (ali brez oznake arhitekture)."""
    if sistem_datoteke(ime) != "linux":
        return False
    n = ime.lower()
    stroj = (stroj or platform.machine()).lower()
    nase = _ARHITEKTURE.get(stroj, (stroj,))
    tuje = [o for k, v in _ARHITEKTURE.items() if k != stroj for o in v]
    if any(o in n for o in nase):
        return True
    return not any(o in n for o in tuje)


def izdaje(repo: str, odpri: Callable = urllib.request.urlopen) -> dict:
    """Zadnje izdaje repozitorija (najvec 5) z datotekami: ime, velikost, prenosi, naslov."""
    if not _REPO.match(str(repo or "")):
        return {"ok": False, "napaka": "neveljaven"}
    try:
        d = _beri(f"{API}/repos/{repo}/releases?per_page=5", odpri)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "napaka": "omejitev" if "403" in str(e) or "429" in str(e) else "omrezje"}
    izid = []
    for r in d if isinstance(d, list) else []:
        if r.get("draft"):
            continue
        datoteke = []
        for a in r.get("assets") or []:
            ime = a.get("name", "")
            dig = str(a.get("digest") or "")
            datoteke.append({"ime": ime, "mb": round((a.get("size") or 0) / 1048576, 1), "prenosi": int(a.get("download_count") or 0),
                             "url": a.get("browser_download_url", ""), "linux": za_linux(ime), "nas": za_ta_racunalnik(ime),
                             "sistem": sistem_datoteke(ime),
                             "sha256": dig[7:] if dig.startswith("sha256:") and len(dig) == 71 else ""})
        # Najprej za ta racunalnik, nato za Linux, nato ostalo; znotraj po prenosih.
        datoteke.sort(key=lambda d: (not d["nas"], not d["linux"], -d["prenosi"]))
        izid.append({"oznaka": r.get("tag_name", ""), "ime": r.get("name") or r.get("tag_name", ""),
                     "datum": (r.get("published_at") or "")[:10], "predizdaja": bool(r.get("prerelease")), "datoteke": datoteke})
    return {"ok": True, "repo": repo, "izdaje": izid}


def dovoljen_naslov(url: str) -> bool:
    try:
        u = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    return u.scheme == "https" and (u.hostname or "") in DOVOLJENI


def varno_ime(ime: str) -> str:
    n = os.path.basename(str(ime or "")).replace("\x00", "")
    n = re.sub(r"[^\w.+@-]", "_", n)[:150].lstrip(".")
    return n or "datoteka"


def ciljna_pot(mapa: str, ime: str) -> str:
    """Enolicno ime v mapi (nic se ne prepise): ime.deb, ime (2).deb ..."""
    osnova = varno_ime(ime)
    pot = os.path.join(mapa, osnova)
    if not os.path.exists(pot):
        return pot
    k = osnova.lower()
    for dvojna in (".tar.gz", ".tar.xz", ".tar.zst"):
        if k.endswith(dvojna):
            deblo, konc = osnova[: -len(dvojna)], osnova[-len(dvojna):]
            break
    else:
        deblo, konc = os.path.splitext(osnova)
    for i in range(2, 1000):
        p = os.path.join(mapa, f"{deblo} ({i}){konc}")
        if not os.path.exists(p):
            return p
    return os.path.join(mapa, f"{deblo}-{uuid.uuid4().hex[:6]}{konc}")


class Prenosi:
    """Prenosi v ozadju; stran sprasuje po stanju (kot pri pretvorbi datotek)."""

    def __init__(self, odpri: Callable = urllib.request.urlopen):
        self._odpri = odpri
        self._dela: Dict[str, dict] = {}
        self._zaklep = threading.Lock()

    def zacni(self, url: str, ime: str, mapa: str, sha256: str = "") -> dict:
        if not dovoljen_naslov(url):
            return {"ok": False, "koda": "naslov"}
        mapa = os.path.abspath(os.path.expanduser(str(mapa or "")))
        if not os.path.isdir(mapa) or not os.access(mapa, os.W_OK):
            return {"ok": False, "koda": "mapa"}
        sha = str(sha256 or "").lower()
        delo = {"id": uuid.uuid4().hex, "stanje": "prenasam", "ime": varno_ime(ime), "mapa": mapa, "prebrano": 0,
                "skupaj": 0, "pot": "", "koda": "", "sha256": sha if re.fullmatch(r"[0-9a-f]{64}", sha) else "", "preverjeno": False}
        with self._zaklep:
            self._dela[delo["id"]] = delo
        threading.Thread(target=self._teci, args=(delo, url), daemon=True, name="safeer-github-prenos").start()
        return {"ok": True, "id": delo["id"]}

    def stanje(self, id_: str) -> dict:
        with self._zaklep:
            d = self._dela.get(str(id_ or ""))
            return {"ok": True, **d} if d else {"ok": False, "koda": "ni_prenosa"}

    def _teci(self, delo: dict, url: str) -> None:
        zacasna = ""
        try:
            zahteva = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with self._odpri(zahteva, timeout=30) as o:
                if not dovoljen_naslov(o.geturl() if hasattr(o, "geturl") else url):
                    raise ValueError("preusmeritev")
                delo["skupaj"] = int(o.headers.get("Content-Length") or 0) if getattr(o, "headers", None) else 0
                if delo["skupaj"] > NAJVEC_MB * 1048576:
                    raise ValueError("prevelika")
                cilj = ciljna_pot(delo["mapa"], delo["ime"])
                zacasna = cilj + ".safeer-delno"
                h = hashlib.sha256()
                with open(zacasna, "wb") as f:
                    while True:
                        kos = o.read(1 << 16)
                        if not kos:
                            break
                        f.write(kos)
                        h.update(kos)
                        delo["prebrano"] += len(kos)
                        if delo["prebrano"] > NAJVEC_MB * 1048576:
                            raise ValueError("prevelika")
            # GitHub objavi SHA-256 vsake datoteke; ce ga imamo, se mora ujemati (sicer datoteke ne obdrzimo).
            if delo["sha256"] and h.hexdigest() != delo["sha256"]:
                raise ValueError("kontrolna")
            os.replace(zacasna, cilj)
            zacasna = ""
            delo.update(stanje="koncano", pot=cilj, ime=os.path.basename(cilj), preverjeno=bool(delo["sha256"]))
        except Exception as e:  # noqa: BLE001 - prenos ne sme podreti Safeer OS
            e = str(e)
            delo.update(stanje="napaka", koda="prevelika" if "prevelika" in e else "naslov" if "preusmeritev" in e
                        else "kontrolna" if "kontrolna" in e else "omrezje")
        finally:
            if zacasna:
                try:
                    os.remove(zacasna)
                except OSError:
                    pass


_prenosi: Optional[Prenosi] = None


def prenosi() -> Prenosi:
    global _prenosi
    if _prenosi is None:
        _prenosi = Prenosi()
    return _prenosi
