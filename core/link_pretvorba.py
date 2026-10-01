"""Pretvorba videa v Safeer Linku (zakon solidarnosti, korak 3: grafika).

Racunalnik s sibko grafiko da video pretvoriti napravi v Linku, ki ima najboljsi strojni kodirnik
H.264 (`host.info` -> `gpu.kodirniki`) in ta trenutek sme pomagati (`pomoc`). Naprava izvirnik
prenese sama s tega racunalnika (HTTPS, pripeto potrdilo, zeton), ga pretvori v H.264/AAC MP4 do
1080p - obliko, ki jo predvaja vsak televizor - in ga shrani v Prenosi/Safeer Shramba
(`video.transcode` / `video.status`, Android Pretvorba.kt).

Izvirnik na racunalniku ostane nedotaknjen. Ko je pretvorba koncana, uporabnik izbere: pretvorjeni
video prenese na ta racunalnik (zraven izvirnika) ali ga pusti na napravi (tam ga vidi v Datotekah).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse

#: Naprava mora imeti prostor za izvirnik + pretvorjeni video + rezervo (enako kot Pretvorba.kt).
REZERVA = 2 * 1024 * 1024 * 1024
NAMIZNE = ("linux", "windows", "macos")
VIDEO = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".wmv", ".flv", ".ts", ".mpg", ".mpeg", ".3gp")


def je_video(pot: str) -> bool:
    return os.path.splitext(pot)[1].lower() in VIDEO


def ocena_kodirnika(info: dict) -> Tuple[int, int, int]:
    """(najvecja sirina H.264 kodirnika, ima HEVC, jedra); (0, ...) = ne zna kodirati H.264."""
    gpu = info.get("gpu") or {}
    sirina, hevc = 0, 0
    for k in gpu.get("kodirniki") or []:
        vrsta = str(k.get("vrsta") or "").lower()
        if vrsta in ("avc", "h264"):
            sirina = max(sirina, int(k.get("sirina") or 1920))
        elif vrsta in ("hevc", "h265"):
            hevc = 1
    jedra = int((info.get("cpu") or {}).get("jedra") or 0)
    return sirina, hevc, jedra


#: ffprobe ime kodeka -> Android MIME (MediaCodec).
MIME = {"h264": "video/avc", "hevc": "video/hevc", "vp9": "video/x-vnd.on2.vp9", "vp8": "video/x-vnd.on2.vp8",
        "av1": "video/av01", "mpeg4": "video/mp4v-es", "mpeg2video": "video/mpeg2", "h263": "video/3gpp"}


def sonda(pot: str) -> Optional[dict]:
    """Oblika izvirnika {"mime", "width", "height"} (ffprobe); None, ce ffprobe ni ali ne ve."""
    if not shutil.which("ffprobe"):
        return None
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=codec_name,width,height", "-of", "json", pot],
                           capture_output=True, text=True, timeout=10)
        tok = (json.loads(r.stdout or "{}").get("streams") or [{}])[0]
        mime = MIME.get(str(tok.get("codec_name") or ""))
        if not mime or not tok.get("width") or not tok.get("height"):
            return None
        return {"mime": mime, "width": int(tok["width"]), "height": int(tok["height"])}
    except Exception:  # noqa: BLE001
        return None


def zna_prebrati(info: dict, oblika: Optional[dict]) -> bool:
    """Ali ima naprava dekodirnik za izvirnik (vrsta in velikost). Brez podatkov: naprava preveri sama."""
    dek = (info.get("gpu") or {}).get("dekodirniki")
    if not oblika or dek is None:
        return True
    vrsta = oblika["mime"].removeprefix("video/")
    w, h = sorted((oblika["width"], oblika["height"]), reverse=True)
    for d in dek:
        if str(d.get("vrsta")) == vrsta:
            dw, dh = sorted((int(d.get("sirina") or 0), int(d.get("visina") or 0)), reverse=True)
            if w <= dw and h <= dh:
                return True
    return False


def _izlocitev(d: Optional[dict], velikost: int, oblika: Optional[dict]) -> str:
    """Zakaj naprava ne more pretvoriti ("" = lahko)."""
    if d is None:
        return "ne odgovori"
    if (d.get("pomoc") or {}).get("lahko") is False:
        return "ne sme pomagati (" + str((d.get("pomoc") or {}).get("razlog") or "") + ")"
    if not (d.get("gpu") or {}).get("strojno") or ocena_kodirnika(d)[0] < 1920:
        return "nima strojnega kodirnika H.264 za 1080p"
    prosto = int((d.get("disk") or {}).get("prosto", -1))
    if 0 <= prosto < 2 * velikost + REZERVA:
        return "premalo prostora"
    if not zna_prebrati(d, oblika):
        return "ne zna prebrati " + str((oblika or {}).get("mime")) + " " + str((oblika or {}).get("width")) + "x" + \
            str((oblika or {}).get("height")) + " (dekodirniki: " + json.dumps((d.get("gpu") or {}).get("dekodirniki")) + ")"
    return ""


def izberi_napravo(naprave: List[dict], vprasaj: Callable[[str, str, dict], dict],
                   velikost: int, oblika: Optional[dict] = None) -> Optional[dict]:
    r = razvrsti_naprave(naprave, vprasaj, velikost, oblika)
    return r[0] if r else None


def razvrsti_naprave(naprave: List[dict], vprasaj: Callable[[str, str, dict], dict],
                     velikost: int, oblika: Optional[dict] = None) -> List[dict]:
    """Naprave, ki zmorejo pretvorbo, od najboljsega strojnega kodirnika H.264 (vsaj 1080p) navzdol:
    smejo pomagati, imajo prostor in znajo prebrati izvirnik. Vse vprasamo hkrati (brez cakanja po vrsti)."""
    kandidati = [n for n in naprave if not n.get("ta") and "files" in (n.get("zmoznosti") or [])
                 and n.get("platforma") not in NAMIZNE]
    if not kandidati:
        return []

    def info(n: dict) -> Optional[dict]:
        try:
            r = vprasaj(n["id"], "host.info", {})
        except Exception:  # noqa: BLE001
            return None
        d = r.get("data") if r.get("ok") else None
        return d if isinstance(d, dict) else None

    with ThreadPoolExecutor(max_workers=min(8, len(kandidati))) as bazen:
        podatki = list(bazen.map(info, kandidati))
    primerne = []
    for n, d in zip(kandidati, podatki):
        razlog = _izlocitev(d, velikost, oblika)
        if razlog:
            print(f"[Pretvorba] {n.get('ime') or n['id']}: {razlog}", flush=True)
            continue
        primerne.append((ocena_kodirnika(d), n))
    primerne.sort(key=lambda x: x[0], reverse=True)
    return [n for _, n in primerne]


def ime_pretvorjenega(ime: str) -> str:
    osnova = os.path.splitext(ime)[0] or ime
    return osnova + "-1080p.mp4"


def prosta_pot(mapa: str, ime: str) -> str:
    pot = os.path.join(mapa, ime)
    osnova, konc = os.path.splitext(pot)
    i = 2
    while os.path.exists(pot):
        pot = f"{osnova} ({i}){konc}"
        i += 1
    return pot


class Opravilo:
    def __init__(self, pot: str) -> None:
        self.id = uuid.uuid4().hex
        self.pot = os.path.realpath(pot)
        self.ime = os.path.basename(self.pot)
        self.velikost = os.path.getsize(self.pot)
        # isceno | prenasam | pretvarjam | shranjujem | koncano | prenasam_nazaj | na_racunalniku | pusceno | napaka
        self.stanje = "isceno"
        self.odstotek = 0
        self.napaka = ""
        self.cilj = ""
        self.cilj_ime = ""
        self.kje = ""
        self.oznaka = ""
        self.izhod_ime = ""
        self.izhod_velikost = 0
        self.lokalno = ""

    def slovar(self) -> dict:
        return {"id": self.id, "ime": self.ime, "pot": self.pot, "velikost": self.velikost, "stanje": self.stanje,
                "odstotek": self.odstotek, "napaka": self.napaka, "naprava": self.cilj_ime, "kje": self.kje,
                "izhod": self.izhod_ime, "izhod_velikost": self.izhod_velikost, "lokalno": self.lokalno}


class Pretvorba:
    """Pretvorbe videov na drugih napravah; klice jih Safeer OS prek Controla (D-Bus Naprave.Pretvorba*)."""

    def __init__(self, naprave: Callable[[], List[dict]], vprasaj: Callable[[str, str, dict], dict],
                 datoteke, hub_url: Callable[[], str] = lambda: "", cakaj: float = 2.0,
                 prenesi: Optional[Callable[[dict, str, str, "Opravilo"], None]] = None,
                 sonda: Callable[[str], Optional[dict]] = sonda) -> None:
        self.naprave = naprave
        self.vprasaj = vprasaj
        self.datoteke = datoteke
        self.hub_url = hub_url
        self.cakaj = cakaj
        self._prenesi = prenesi or prenesi_z_naprave
        self._sonda = sonda
        self.opravila: Dict[str, Opravilo] = {}

    def zacni(self, pot: str) -> dict:
        if not pot or not os.path.isfile(pot):
            return {"ok": False, "koda": "ni_datoteke"}
        if not je_video(pot):
            return {"ok": False, "koda": "ni_video"}
        o = Opravilo(pot)
        self.opravila[o.id] = o
        threading.Thread(target=self._pretvori, args=(o,), name="safeer-pretvorba", daemon=True).start()
        return {"ok": True, **o.slovar()}

    def _ena_bi_zmogla(self, velikost: int) -> bool:
        """Ali bi kaksna naprava pomagala, ce ne bi slo za obliko (za razumljivo sporocilo)."""
        return bool(razvrsti_naprave(self.naprave(), self.vprasaj, velikost, None))

    def stanje(self, id_: str) -> dict:
        o = self.opravila.get(id_)
        return {"ok": True, **o.slovar()} if o else {"ok": False, "koda": "ni_opravila"}

    def prenesi(self, id_: str) -> dict:
        """Uporabnik zeli pretvorjeni video na tem racunalniku: shranimo ga zraven izvirnika."""
        o = self.opravila.get(id_)
        if o is None or o.stanje != "koncano":
            return {"ok": False, "koda": "ni_koncano"}
        o.stanje, o.odstotek = "prenasam_nazaj", 0
        threading.Thread(target=self._nazaj, args=(o,), name="safeer-pretvorba-nazaj", daemon=True).start()
        return {"ok": True, **o.slovar()}

    def pusti(self, id_: str) -> dict:
        o = self.opravila.get(id_)
        if o is None:
            return {"ok": False, "koda": "ni_opravila"}
        if o.stanje == "koncano":
            o.stanje = "pusceno"
        return {"ok": True, **o.slovar()}

    def _nazaj(self, o: Opravilo) -> None:
        try:
            r = self.vprasaj(o.cilj, "files.list", {"folder": "media:shramba"})
            d = r.get("data") or {}
            streznik = d.get("server") or {}
            if not r.get("ok") or not d.get("shared") or not streznik.get("base_url"):
                raise _Napaka("naprava_ne_deli")
            if not any(str(e.get("id")) == o.oznaka for e in d.get("items") or []):
                raise _Napaka("ni_datoteke")
            cilj = prosta_pot(os.path.dirname(o.pot), o.izhod_ime or ime_pretvorjenega(o.ime))
            self._prenesi(streznik, o.oznaka, cilj, o)
            o.lokalno, o.odstotek, o.stanje = cilj, 100, "na_racunalniku"
        except _Napaka as e:
            o.napaka, o.stanje = str(e), "koncano"   # pretvorjeni video ostaja na napravi
        except Exception as e:  # noqa: BLE001
            o.napaka, o.stanje = str(e) or type(e).__name__, "koncano"

    def _pretvori(self, o: Opravilo) -> None:
        try:
            oblika = self._sonda(o.pot)
            kandidati = razvrsti_naprave(self.naprave(), self.vprasaj, o.velikost, oblika)
            if not kandidati:
                raise _Napaka("ne_zna_dekodirati" if oblika is not None and self._ena_bi_zmogla(o.velikost) else "ni_naprave")
            s = self.datoteke.streznik
            s.zazeni()
            from core import link_datoteke
            hub = self.hub_url() or ""
            naslov = link_datoteke.naslov_do_huba(hub) if hub else link_datoteke.krajevni_naslov()
            url = s.osnova(naslov) + s.dodaj_datoteko_toka(o.pot)
            r, zavrnitev = {}, "ni_naprave"
            for n in kandidati:   # naprava lahko vseeno reče ne (npr. medtem ni vec moci): naslednja najboljsa
                o.cilj, o.cilj_ime = n["id"], n.get("ime") or n["id"]
                parametri = {"url": url, "fp": s.odtis, "token": s.zeton_za(o.cilj), "name": o.ime, "size": o.velikost}
                parametri.update(oblika or {})
                r = self.vprasaj(o.cilj, "video.transcode", parametri)
                if r.get("ok"):
                    break
                zavrnitev = str(r.get("koda") or "zavrnjeno")
            if not r.get("ok"):
                raise _Napaka(zavrnitev)
            opravilo = str((r.get("data") or {}).get("id") or "")
            o.stanje = "prenasam"
            brez_odgovora = 0
            while True:
                time.sleep(self.cakaj)
                r = self.vprasaj(o.cilj, "video.status", {"id": opravilo})
                d = r.get("data") or {}
                if not r.get("ok") and not d:
                    brez_odgovora += 1
                    if brez_odgovora > 60:
                        raise _Napaka("naprava_ne_odgovori")
                    continue
                brez_odgovora = 0
                faza = str(d.get("state") or "")
                o.odstotek = int(d.get("percent") or 0)
                if faza == "koncano":
                    o.kje = str(d.get("where") or "")
                    o.oznaka = str(d.get("file_id") or "")
                    o.izhod_ime = str(d.get("name") or "")
                    o.izhod_velikost = int(d.get("size") or 0)
                    o.stanje = "koncano"
                    return
                if faza == "napaka":
                    raise _Napaka(str(d.get("error") or "napaka"))
                if faza in ("prenasam", "pretvarjam", "shranjujem"):
                    o.stanje = faza
        except _Napaka as e:
            o.napaka, o.stanje = str(e), "napaka"
        except Exception as e:  # noqa: BLE001 - pretvorba ne sme podreti Controla
            o.napaka, o.stanje = str(e) or type(e).__name__, "napaka"


def prenesi_z_naprave(streznik: dict, oznaka: str, cilj: str, o: Opravilo) -> None:
    """GET <base_url>/d/<oznaka> s pripetim potrdilom naprave; zapise v .part in na koncu preimenuje."""
    from core import link_tls
    u = urlparse(str(streznik.get("base_url")))
    if u.scheme != "https" or not u.hostname:
        raise _Napaka("napacen_streznik")
    povezava = link_tls._PripetaHttps(u.hostname, u.port or 443, str(streznik.get("fp") or ""), 30.0)
    zacasna = cilj + ".part"
    try:
        povezava.request("GET", "/d/" + quote(oznaka, safe=""), headers={"X-Safeer-Token": str(streznik.get("token") or "")})
        odgovor = povezava.getresponse()
        if odgovor.status != 200:
            raise _Napaka(f"naprava je vrnila {odgovor.status}")
        skupaj = int(odgovor.getheader("content-length") or 0) or o.izhod_velikost
        dobljeno = 0
        with open(zacasna, "wb") as f:
            while True:
                kos = odgovor.read(256 * 1024)
                if not kos:
                    break
                f.write(kos)
                dobljeno += len(kos)
                if skupaj:
                    o.odstotek = min(99, dobljeno * 100 // skupaj)
        if skupaj and dobljeno != skupaj:
            raise _Napaka("prenos_prekinjen")
        os.replace(zacasna, cilj)
    finally:
        try:
            povezava.close()
        except Exception:
            pass
        if os.path.exists(zacasna):
            try:
                os.remove(zacasna)
            except OSError:
                pass


class _Napaka(Exception):
    pass
