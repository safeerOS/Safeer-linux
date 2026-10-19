"""Nastavitve Safeer Agenta na tem racunalniku (Nastavitve Safeer OS -> Safeer Agent).

Prej je bil naslov jezikovnega modela mogoce nastaviti samo rocno v datoteki ~/.config/safeer-agent/naslov (lastnik,
19. 10. 2026: to mora biti v Nastavitvah, upravljanje agenta mora biti preprosto in prijetno). Ista datoteka ostane vir
za razumevanje.naslov_modela in za zmoznost 'agent' v Safeer Linku, zato rocno vpisan naslov velja naprej.

* naslov: https, http samo v domacem omrezju (zasebni IP, zanka, .local/.lan/.home.arpa, ime brez pike); brez
  uporabniskega imena ali gesla v naslovu (kljuc je v svoji datoteki »kljuc«), brez lupine. Na naslov gre besedilo
  ukaza in glava Authorization, zato zahteve ne sledijo preusmeritvam (drugi neodvisni pregled, 19. 10. 2026);
* izklop: datoteka »izklopljen« - naslov ostane shranjen, agent pa ne dela (Link ne oglasa zmoznosti 'agent');
* trajanje: privzeto trajanje nove seje v minutah (0 = neomejeno), kadar ga naprava ne pove sama;
* dosegljivost: preverba, ali na naslovu res odgovarja streznik OpenAI-zdruzljivega API-ja (llama-server) - brez
  laznih podatkov: ce ne odgovori, je »ni dosegljiv«.
Brez GTK; pisanje je atomarno (zacasna datoteka + os.replace)."""
from __future__ import annotations

import ipaddress
import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

#: Mapa nastavitev; prazno = ~/.config/safeer-agent (ista kot do zdaj, HOME se bere ob vsakem klicu). Preizkusi jo zamenjajo.
MAPA = ""
#: Izbire trajanja seje v minutah (0 = neomejeno) - lastnik, 13. 10. 2026: od 1 minute do neomejeno.
TRAJANJA = (1, 5, 15, 30, 60, 0)
PRIVZETO_TRAJANJE = 0
NAJDALJSI_NASLOV = 200


def mapa() -> str:
    return MAPA or os.path.expanduser("~/.config/safeer-agent")


def _pot(ime: str) -> str:
    return os.path.join(mapa(), ime)


def _beri(ime: str) -> str:
    try:
        with open(_pot(ime), encoding="utf-8") as f:
            return f.read(4096).strip()
    except OSError:
        return ""


def _pisi(ime: str, vsebina: str) -> None:
    os.makedirs(mapa(), mode=0o700, exist_ok=True)
    fd, zacasna = tempfile.mkstemp(prefix="." + ime + "-", dir=mapa())
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(vsebina + ("\n" if vsebina else ""))
        os.replace(zacasna, _pot(ime))
    except BaseException:
        try:
            os.unlink(zacasna)
        except OSError:
            pass
        raise


def _odstrani(ime: str) -> None:
    try:
        os.unlink(_pot(ime))
    except FileNotFoundError:
        pass


class _BrezPreusmeritev(urllib.request.HTTPRedirectHandler):
    """Preusmeritev je napaka: urllib bi glavo Authorization (kljuc) in besedilo ukaza poslal tudi novemu gostitelju."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "preusmeritev ni dovoljena", headers, fp)


def odpri(zahteva, cas: float):
    """urlopen brez sledenja preusmeritvam (za vse zahteve na naslov modela)."""
    return urllib.request.build_opener(_BrezPreusmeritev()).open(zahteva, timeout=cas)  # nosec B310 - preveri_naslov


def domace_omrezje(gostitelj: str) -> bool:
    """http je dovoljen samo tja: zasebni IP, zanka, lokalna imena (.local, .lan, .home.arpa, .internal, localhost) ali
    ime brez pike (npr. telefon) - isto kot os_vgrajeni_viri.je_zasebni_gostitelj, ki ga tovor Controla nima."""
    g = (gostitelj or "").strip().strip("[]").rstrip(".").lower()
    if not g:
        return False
    try:
        ip = ipaddress.ip_address(g)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        pass
    return ("." not in g and ":" not in g) or g.endswith((".localhost", ".local", ".lan", ".home.arpa", ".internal"))


def preveri_naslov(naslov) -> str:
    """Pocisten naslov modela ali ValueError s kodo napake (»shema«, »naslov«, »geslo«, »dolzina«, »http«). Prazen niz
    je dovoljen (izbrise naslov). https, http samo v domacem omrezju - isto pravilo kot razumevanje.llama_server."""
    n = str(naslov or "").strip()
    if not n:
        return ""
    if len(n) > NAJDALJSI_NASLOV:
        raise ValueError("dolzina")
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in n):
        raise ValueError("naslov")
    deli = urllib.parse.urlsplit(n)
    if deli.scheme.lower() not in ("http", "https"):
        raise ValueError("shema")
    if deli.username is not None or deli.password is not None:
        raise ValueError("geslo")
    try:
        deli.port                      # neveljavna vrata sprozijo ValueError
    except ValueError:
        raise ValueError("naslov") from None
    if not deli.hostname or deli.query or deli.fragment:
        raise ValueError("naslov")
    if deli.scheme.lower() == "http" and not domace_omrezje(deli.hostname):
        raise ValueError("http")
    return urllib.parse.urlunsplit((deli.scheme.lower(), deli.netloc, deli.path.rstrip("/"), "", ""))


def naslov_shranjen() -> str:
    """Naslov iz datoteke (ne glede na izklop); neveljaven naslov steje kot prazen."""
    try:
        return preveri_naslov(_beri("naslov"))
    except ValueError:
        return ""


def vklopljen() -> bool:
    return not os.path.exists(_pot("izklopljen"))


def trajanje() -> int:
    """Privzeto trajanje seje v minutah (0 = neomejeno)."""
    try:
        m = int(_beri("trajanje") or PRIVZETO_TRAJANJE)
    except ValueError:
        return PRIVZETO_TRAJANJE
    return m if m in TRAJANJA else PRIVZETO_TRAJANJE


def stanje() -> dict:
    okolje = os.environ.get("SAFEER_AGENT", "").strip()
    return {"naslov": naslov_shranjen(), "vklopljen": vklopljen(), "trajanje": trajanje(), "trajanja": list(TRAJANJA),
            "kljuc": bool(_beri("kljuc")), "okolje": okolje if okolje.startswith(("http://", "https://")) else "",
            "na_voljo": _na_voljo()}


def _na_voljo() -> bool:
    from core.agent.razumevanje import naslov_modela
    return bool(naslov_modela())


def nastavi_naslov(naslov) -> dict:
    try:
        n = preveri_naslov(naslov)
    except ValueError as e:
        return dict(stanje(), ok=False, napaka=str(e))
    if n:
        _pisi("naslov", n)
    else:
        _odstrani("naslov")
    return dict(stanje(), ok=True)


def nastavi_vklop(vklop: bool) -> dict:
    if vklop:
        _odstrani("izklopljen")
    else:
        _pisi("izklopljen", "1")
    return dict(stanje(), ok=True)


def nastavi_trajanje(minute) -> dict:
    try:
        m = int(minute)
    except (TypeError, ValueError):
        return dict(stanje(), ok=False, napaka="trajanje")
    if isinstance(minute, bool) or m not in TRAJANJA:
        return dict(stanje(), ok=False, napaka="trajanje")
    _pisi("trajanje", str(m))
    return dict(stanje(), ok=True)


def dosegljivost(naslov: Optional[str] = None, cas: float = 3.0) -> dict:
    """Ali na naslovu modela odgovarja streznik: GET /v1/models (OpenAI-zdruzljiv, llama-server), sicer /health.
    Vrne {"dosegljiv": bool, "model": ime ali "", "napaka": kratek razlog}. Nic se ne ugiba: brez odgovora ni dosegljiv."""
    from core.agent.razumevanje import naslov_modela
    try:
        n = preveri_naslov(naslov if naslov is not None else naslov_modela())
    except ValueError as e:
        return {"dosegljiv": False, "model": "", "napaka": str(e)}
    if not n:
        return {"dosegljiv": False, "model": "", "napaka": "ni_naslova"}
    glave = {"Accept": "application/json"}
    kljuc = _beri("kljuc")
    if kljuc:
        glave["Authorization"] = "Bearer " + kljuc
    napaka = ""
    for pot in ("/v1/models", "/health"):
        zahteva = urllib.request.Request(n + pot, headers=glave)
        try:
            with odpri(zahteva, cas) as o:
                telo = o.read(65536)
        except urllib.error.HTTPError as e:
            napaka = "http_%d" % e.code
            if e.code in (401, 403):
                return {"dosegljiv": False, "model": "", "napaka": "kljuc"}
            continue
        except (OSError, ValueError) as e:
            return {"dosegljiv": False, "model": "", "napaka": (str(getattr(e, "reason", "")) or type(e).__name__)[:80]}
        model = ""
        try:
            d = json.loads(telo.decode("utf-8", "replace"))
            if isinstance(d, dict) and isinstance(d.get("data"), list) and d["data"] and isinstance(d["data"][0], dict):
                model = str(d["data"][0].get("id") or "")[:80]
        except ValueError:
            pass
        return {"dosegljiv": True, "model": os.path.basename(model) if "/" in model else model, "napaka": ""}
    return {"dosegljiv": False, "model": "", "napaka": napaka or "ni_odgovora"}
