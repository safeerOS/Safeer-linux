"""Pretvorba datotek v Datotekah Safeer OS: slike, zvok in dokumenti - na tem racunalniku, brez spleta.

Zamisel iz VERT (pretvornik v brskalniku; lastnik, 11. 10. 2026), koda nasa in z istimi prostimi orodji:
ImageMagick (slike, tudi HEIC/AVIF na vhodu), ffmpeg (zvok), LibreOffice brez okna (dokumenti, preglednice,
predstavitve). Video ima svojo pot (Pretvori za televizor - naprave v Linku). Nic ne gre na splet.

Izvirnik ostane; pretvorjena datoteka pristane ob njem (enolicno ime). Hkrati tecejo najvec NAJVEC_HKRATI pretvorbe,
vsaka z omejenim casom; orodje dobi samo pot izvirnika in izhoda (brez lupine).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from typing import Callable, Dict, List, Optional

NAJVEC_HKRATI = 2
NAJVEC_SHRANJENIH = 50
CAS_S = {"slika": 120, "zvok": 1800, "dokument": 300}

#: Skupine vhodov (koncnica -> skupina) in cilji skupine. Cilj je koncnica izhoda.
SLIKE = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif", ".avif", ".jfif", ".ico")
ZVOK = (".mp3", ".ogg", ".oga", ".opus", ".flac", ".m4a", ".aac", ".wav", ".wma", ".aiff", ".aif", ".mka")
BESEDILA = (".docx", ".doc", ".odt", ".rtf", ".txt", ".html", ".htm")
PREGLEDNICE = (".xlsx", ".xls", ".ods", ".csv")
PREDSTAVITVE = (".pptx", ".ppt", ".odp")
CILJI = {
    "slika": ("jpg", "png", "webp", "tiff", "bmp", "gif", "pdf"),
    "zvok": ("mp3", "ogg", "opus", "flac", "m4a", "wav"),
    "besedilo": ("pdf", "docx", "odt", "rtf", "txt", "html"),
    "preglednica": ("xlsx", "ods", "csv", "pdf"),
    "predstavitev": ("pptx", "odp", "pdf"),
}
#: ffmpeg: kodek in kakovost za vsak zvocni cilj.
ZVOK_KODEK = {
    "mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "5"],
    "opus": ["-c:a", "libopus", "-b:a", "128k"],
    "flac": ["-c:a", "flac"],
    "m4a": ["-c:a", "aac", "-b:a", "192k"],
    "wav": ["-c:a", "pcm_s16le"],
}
#: LibreOffice: ime filtra za cilje, kjer sama koncnica ni dovolj enoznacna.
LO_FILTER = {"txt": "txt:Text (encoded):UTF8", "csv": "csv:Text - txt - csv (StarCalc):44,34,76,1"}


def skupina(pot: str) -> str:
    konc = os.path.splitext(pot)[1].lower()
    if konc in SLIKE:
        return "slika"
    if konc in ZVOK:
        return "zvok"
    if konc in BESEDILA:
        return "besedilo"
    if konc in PREGLEDNICE:
        return "preglednica"
    if konc in PREDSTAVITVE:
        return "predstavitev"
    return ""


def _gostitelj_ima(ime: str, pot: Optional[str]) -> Optional[str]:
    """V Flatpaku je ovoj v /app/host-bin vedno najden; velja le, ce ima program res racunalnik (/run/host/usr/bin)."""
    if pot and os.environ.get("FLATPAK_ID") and pot.startswith("/app/host-bin/"):
        # lexists: na Mintu je /usr/bin/convert absolutna povezava na /etc/alternatives, ki je v peskovniku ni.
        return pot if os.path.lexists("/run/host/usr/bin/" + ime) else None
    return pot


def orodje(sk: str, najdi: Callable[[str], Optional[str]] = shutil.which) -> str:
    """Pot orodja za skupino ("" = ni namesceno). V Flatpaku LibreOffice in ImageMagick tecejo na racunalniku."""
    def n(ime: str) -> Optional[str]:
        return _gostitelj_ima(ime, najdi(ime))
    if sk == "slika":
        return n("magick") or n("convert") or ""
    if sk == "zvok":
        return n("ffmpeg") or ""
    if sk in ("besedilo", "preglednica", "predstavitev"):
        return n("soffice") or n("libreoffice") or ""
    return ""


def _zazeni_s_koncem(u: List[str], cas: float) -> int:
    """Kot subprocess.run s casovno omejitvijo, a ob prekoracitvi najprej SIGTERM: flatpak-spawn ga posreduje programu
    na racunalniku (SIGKILL ne - soffice bi ostal ziv brez profila; pregled 14. 10. 2026)."""
    p = subprocess.Popen(u, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        return p.wait(timeout=cas)
    except subprocess.TimeoutExpired:
        p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
        raise


def _zacasna_mapa() -> str:
    """Zacasna mapa, ki jo vidi tudi program na racunalniku (v Flatpaku je /tmp peskovnika zaseben)."""
    if os.environ.get("FLATPAK_ID"):
        koren = os.path.join(os.path.expanduser("~"), ".cache", "safeer-pretvorba")
        os.makedirs(koren, exist_ok=True)
        return tempfile.mkdtemp(prefix="safeer-pretvorba-", dir=koren)
    return tempfile.mkdtemp(prefix="safeer-pretvorba-")


def moznosti(pot: str, najdi: Callable[[str], Optional[str]] = shutil.which) -> dict:
    """Kaj lahko iz te datoteke naredimo: {"skupina", "cilji": [...], "orodje": bool}. Lastna oblika ni med cilji."""
    sk = skupina(pot)
    if not sk:
        return {"skupina": "", "cilji": [], "orodje": False}
    lastna = os.path.splitext(pot)[1].lower().lstrip(".")
    lastna = {"jpeg": "jpg", "jfif": "jpg", "tif": "tiff", "oga": "ogg", "htm": "html"}.get(lastna, lastna)
    return {"skupina": sk, "cilji": [c for c in CILJI[sk] if c != lastna], "orodje": bool(orodje(sk, najdi))}


def izhodna_pot(pot: str, konc: str) -> str:
    """Ob izvirniku, z enolicnim imenom: »Slika.png« -> »Slika.webp« ali »Slika (1).webp«."""
    mapa, ime = os.path.split(pot)
    osnova = os.path.splitext(ime)[0]
    kandidat = os.path.join(mapa, f"{osnova}.{konc}")
    n = 1
    while os.path.exists(kandidat):
        kandidat = os.path.join(mapa, f"{osnova} ({n}).{konc}")
        n += 1
    return kandidat


def ukaz(pot: str, konc: str, izhod: str, orodje_pot: str, profil: str = "", zacasna: str = "") -> List[str]:
    """Ukaz brez lupine. Pri dokumentih LibreOffice pise v `zacasna` (ime izhoda doloci sam) z lastnim profilom
    (`profil`), da ne trci z odprtim LibreOffice uporabnika."""
    sk = skupina(pot)
    if sk == "slika":
        # [0]: prva slicica (animiran GIF, vecstranski TIFF); -auto-orient: slika s telefona ostane pokonci.
        vhod = pot + "[0]" if konc != "gif" else pot
        u = [orodje_pot, vhod, "-auto-orient"]
        if konc == "jpg":
            u += ["-background", "white", "-alpha", "remove", "-quality", "90"]
        return u + [izhod]
    if sk == "zvok":
        return [orodje_pot, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", pot, "-vn", "-map", "0:a:0",
                "-map_metadata", "0"] + ZVOK_KODEK[konc] + [izhod]
    return [orodje_pot, "--headless", "--norestore", "--nolockcheck", f"-env:UserInstallation=file://{profil}",
            "--convert-to", LO_FILTER.get(konc, konc), "--outdir", zacasna, pot]


class Pretvorbe:
    """Pretvorbe, ki tecejo ali so se koncale (stran jih bere s `stanje`)."""

    def __init__(self, najdi: Callable[[str], Optional[str]] = shutil.which,
                 zazeni: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> None:
        self._najdi = najdi
        self._zazeni = zazeni
        self._zaklep = threading.Lock()
        self._dela: Dict[str, dict] = {}
        self._omejitev = threading.Semaphore(NAJVEC_HKRATI)

    def zacni(self, pot: str, konc: str) -> dict:
        pot = os.path.realpath(str(pot or ""))
        konc = str(konc or "").lower().lstrip(".")
        if not os.path.isfile(pot):
            return {"ok": False, "koda": "ni_datoteke"}
        m = moznosti(pot, self._najdi)
        if konc not in m["cilji"]:
            return {"ok": False, "koda": "ni_mogoce"}
        orodje_pot = orodje(m["skupina"], self._najdi)
        if not orodje_pot:
            return {"ok": False, "koda": "ni_orodja", "skupina": m["skupina"]}
        delo = {"id": uuid.uuid4().hex, "stanje": "caka", "ime": os.path.basename(pot), "izhod": "", "pot_izhoda": "",
                "koda": "", "cilj": konc, "zacetek": time.time()}
        with self._zaklep:
            koncana = [i for i, d in self._dela.items() if d["stanje"] in ("koncano", "napaka")]
            for i in koncana[:max(0, len(koncana) - NAJVEC_SHRANJENIH + 1)]:
                self._dela.pop(i, None)
            self._dela[delo["id"]] = delo
        threading.Thread(target=self._teci, args=(delo, pot, konc, m["skupina"], orodje_pot),
                         name="safeer-pretvorba-datoteke", daemon=True).start()
        return {"ok": True, **delo}

    def stanje(self, id_: str) -> dict:
        with self._zaklep:
            d = self._dela.get(str(id_ or ""))
            return {"ok": True, **d} if d else {"ok": False, "koda": "ni_pretvorbe"}

    def _teci(self, delo: dict, pot: str, konc: str, sk: str, orodje_pot: str) -> None:
        with self._omejitev:
            delo["stanje"] = "pretvarjam"
            izhod = izhodna_pot(pot, konc)
            try:
                zacasna = _zacasna_mapa()
            except OSError:
                delo.update(stanje="napaka", koda="ni_uspelo")
                return
            try:
                profil = os.path.join(zacasna, "profil")
                cilj_v_zacasni = os.path.join(zacasna, "izhod." + konc)
                u = ukaz(pot, konc, cilj_v_zacasni, orodje_pot, profil=profil, zacasna=zacasna)
                try:
                    cas = CAS_S.get("dokument" if sk not in CAS_S else sk, 300)
                    if self._zazeni is subprocess.run:
                        koda = _zazeni_s_koncem(u, cas)
                    else:
                        r = self._zazeni(u, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                         timeout=cas)
                        koda = r.returncode
                except subprocess.TimeoutExpired:
                    koda = -1
                    delo["koda"] = "prepocasi"
                except OSError:
                    koda = -1
                    delo["koda"] = "ni_orodja"
                # LibreOffice izhod poimenuje po izvirniku (»Porocilo.pdf«): poiscemo ga v zacasni mapi.
                narejeno = cilj_v_zacasni if os.path.isfile(cilj_v_zacasni) else next(
                    (os.path.join(zacasna, f) for f in os.listdir(zacasna)
                     if f.lower().endswith("." + konc) and os.path.isfile(os.path.join(zacasna, f))), "")
                if koda != 0 or not narejeno or os.path.getsize(narejeno) == 0:
                    delo["koda"] = delo["koda"] or "ni_uspelo"
                    delo["stanje"] = "napaka"
                    return
                shutil.move(narejeno, izhod)
                delo.update(stanje="koncano", izhod=os.path.basename(izhod), pot_izhoda=izhod,
                            velikost=os.path.getsize(izhod))
            except Exception:  # noqa: BLE001 - pretvorba ne sme podreti Safeer OS
                delo["koda"] = delo["koda"] or "ni_uspelo"
                delo["stanje"] = "napaka"
            finally:
                shutil.rmtree(zacasna, ignore_errors=True)


_pretvorbe: Optional[Pretvorbe] = None


def pretvorbe() -> Pretvorbe:
    global _pretvorbe
    if _pretvorbe is None:
        _pretvorbe = Pretvorbe()
    return _pretvorbe
