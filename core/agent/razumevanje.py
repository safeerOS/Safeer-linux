"""Stavek -> seznam nalog (JSON po shemi). Jezikovni model je zamenljiv (klic_modela), privzeto llama-server
(OpenAI-zdruzljiv /v1/chat/completions) na napravi v domacem omrezju. Prototip (lokalni-agent/agent_vprasaj.py):
Gemma 3 4B na OnePlusu, 28/30 pravilnih, ~6 s na ukaz."""
from __future__ import annotations

import json
import os
import unicodedata
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, List, Optional

DEJANJA = ["predvajaj", "odpri_stran", "odpri_aplikacijo", "glasnost_gor", "glasnost_dol", "utisaj", "pavza",
           "nadaljuj", "ustavi", "nadaljuj_na_napravi", "isci", "ni_ukaz"]
NAPRAVE = ["tv", "tablica", "telefon", "racunalnik", "tukaj"]
NAJVEC_NALOG = 5

NALOGA = {"type": "object", "properties": {
    "dejanje": {"type": "string", "enum": DEJANJA},
    "naprava": {"type": "string", "enum": NAPRAVE},
    "kaj": {"type": "string", "maxLength": 80}},
    "required": ["dejanje", "naprava", "kaj"]}
SHEMA = {"type": "object", "properties": {
    "naloge": {"type": "array", "items": NALOGA, "minItems": 1, "maxItems": NAJVEC_NALOG}},
    "required": ["naloge"]}

SISTEM = """Si pretvornik ukazov za Safeer Link. Uporabnik napise ali izgovori stavek (slovensko ali anglesko), ti vrnes JSON
s seznamom nalog. Ce stavek vsebuje vec ukazov (npr. "in", "potem", vejica), je vsak ukaz svoja naloga, v istem vrstnem redu.
Dejanja: predvajaj (glasba, film, serija, radio, TV program), odpri_stran (spletna stran ali naslov), odpri_aplikacijo, glasnost_gor,
glasnost_dol, utisaj, pavza, nadaljuj, ustavi, nadaljuj_na_napravi (to, kar zdaj igra, naj se nadaljuje na drugi napravi), isci (isci
vsebino), ni_ukaz (vprasanje ali pogovor, ki ni ukaz za napravo).
Naprave: tv (televizor, televizija), tablica, telefon (mobitel), racunalnik (PC, prenosnik), tukaj (ce naprava ni omenjena).
"kaj" je vsebina ukaza (ime pesmi, filma, postaje, strani, aplikacije ali iskalni niz), brez imena naprave; prazno, ce je ni.
Pozor: "stisaj", "tisje", "manj glasno" = glasnost_dol; "utisaj", "izklopi zvok", "mute" = utisaj; "ustavi", "stop" = ustavi;
"nadaljuj" (film, serijo, glasbo) brez druge naprave = nadaljuj. Ne dodajaj nalog, ki jih uporabnik ni izrekel."""

# Zgledi (prejsnji pogovor). Zadnji zgledi so "tukaj": zadnji zgled doloca nagnjenje modela (meritev 3. 10. 2026).
ZGLEDI = [
    ("Predvajaj Radio Center na tablici", [("predvajaj", "tablica", "Radio Center")]),
    ("tišje na televizorju", [("glasnost_dol", "tv", "")]),
    ("izklopi zvok na računalniku", [("utisaj", "racunalnik", "")]),
    ("odpri siol.net na tablici", [("odpri_stran", "tablica", "siol.net")]),
    ("daj to na tablico", [("nadaljuj_na_napravi", "tablica", "")]),
    ("utišaj televizor in na tablici odpri YouTube", [("utisaj", "tv", ""), ("odpri_aplikacijo", "tablica", "YouTube")]),
    ("zavrti Big Foot Mamo na telefonu", [("predvajaj", "telefon", "Big Foot Mama")]),
    ("stišaj tablico", [("glasnost_dol", "tablica", "")]),
    ("ustavi radio na računalniku, nato na televizorju odpri delo.si", [("ustavi", "racunalnik", ""), ("odpri_stran", "tv", "delo.si")]),
    ("daj na pavzo na tablici", [("pavza", "tablica", "")]),
    ("nadaljuj serijo", [("nadaljuj", "tukaj", "")]),
    ("glasneje", [("glasnost_gor", "tukaj", "")]),
    ("odpri Spotify", [("odpri_aplikacijo", "tukaj", "Spotify")]),
    ("nadaljuj", [("nadaljuj", "tukaj", "")]),
    ("kdo je predsednik Slovenije?", [("ni_ukaz", "tukaj", "")]),
    ("poišči risanke", [("isci", "tukaj", "risanke")]),
    ("stop", [("ustavi", "tukaj", "")]),
    ("turn it down", [("glasnost_dol", "tukaj", "")]),
]


@dataclass
class Naloga:
    dejanje: str
    naprava: str
    kaj: str = ""

    def slovar(self) -> dict:
        return {"dejanje": self.dejanje, "naprava": self.naprava, "kaj": self.kaj}


@dataclass
class Razumevanje:
    naloge: List[Naloga] = field(default_factory=list)
    napaka: str = ""


def sporocila(besedilo: str) -> list:
    s = [{"role": "system", "content": SISTEM}]
    for stavek, naloge in ZGLEDI:
        s.append({"role": "user", "content": stavek})
        s.append({"role": "assistant", "content": json.dumps(
            {"naloge": [{"dejanje": d, "naprava": n, "kaj": k} for d, n, k in naloge]}, ensure_ascii=False)})
    s.append({"role": "user", "content": besedilo})
    return s


def preveri(odgovor) -> List[Naloga]:
    """Odgovor modela -> veljavne naloge (neznano dejanje ali naprava se zavrze; najvec NAJVEC_NALOG)."""
    if isinstance(odgovor, dict) and "naloge" not in odgovor and "dejanje" in odgovor:
        odgovor = {"naloge": [odgovor]}          # model je vrnil eno nalogo brez seznama
    if not isinstance(odgovor, dict) or not isinstance(odgovor.get("naloge"), list):
        return []
    izid = []
    for n in odgovor["naloge"][:NAJVEC_NALOG]:
        if not isinstance(n, dict):
            continue
        d, nap = str(n.get("dejanje") or ""), str(n.get("naprava") or "tukaj")
        if d in DEJANJA and nap in NAPRAVE:
            izid.append(Naloga(d, nap, str(n.get("kaj") or "")[:80].strip()))
    return izid


def naslov_modela() -> str:
    """Kje tece jezikovni model: SAFEER_AGENT ali ~/.config/safeer-agent/naslov (npr. http://telefon:8085)."""
    n = os.environ.get("SAFEER_AGENT", "").strip()
    if not n:
        try:
            with open(os.path.expanduser("~/.config/safeer-agent/naslov"), encoding="utf-8") as f:
                n = f.read().strip()
        except OSError:
            n = ""
    return n if n.startswith(("http://", "https://")) else ""


def llama_server(naslov: str = "", kljuc: str = "", cas: float = 60.0) -> Callable[[list, dict], dict]:
    """Klic llama-serverja (OpenAI-zdruzljiv) z izhodom, omejenim na JSON shemo."""
    naslov = naslov or naslov_modela()
    if not kljuc:
        try:
            with open(os.path.expanduser("~/.config/safeer-agent/kljuc"), encoding="utf-8") as f:
                kljuc = f.read().strip()
        except OSError:
            kljuc = ""

    def klic(sporocila_: list, shema: dict) -> dict:
        if not naslov:
            raise OSError("ni naslova modela (SAFEER_AGENT)")
        telo = {"messages": sporocila_, "temperature": 0, "max_tokens": 200, "cache_prompt": True,
                "response_format": {"type": "json_schema", "json_schema": {"name": "naloge", "strict": True, "schema": shema}}}
        glave = {"Content-Type": "application/json"}
        if kljuc:
            glave["Authorization"] = "Bearer " + kljuc
        z = urllib.request.Request(naslov.rstrip("/") + "/v1/chat/completions", json.dumps(telo).encode(), glave)
        with urllib.request.urlopen(z, timeout=cas) as o:
            d = json.load(o)
        return json.loads(d["choices"][0]["message"]["content"])
    return klic


def _brez_sumnikov(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


def popravi(besedilo: str, naloge: List[Naloga]) -> List[Naloga]:
    """Majhen model (Gemma 4B) zamenjuje "stisaj" (tisje) in "utisaj" (brez zvoka) - meritev 13. 10. 2026: 3 od 9
    napak. Ce stavek vsebuje samo eno od obeh zahtev, vse naloge glasnosti dobijo to dejanje."""
    t = _brez_sumnikov(besedilo)
    brez_u = t.replace("utisa", "")
    tisje = "stisa" in brez_u or any(k in t for k in ("tisje", "manj glasno", "turn it down", "quieter"))
    brez = any(k in t for k in ("utisa", "izklopi zvok", "ugasni zvok", "brez zvoka", "mute"))
    if tisje == brez:
        return naloge
    zeleno = "glasnost_dol" if tisje else "utisaj"
    for n in naloge:
        if n.dejanje in ("glasnost_dol", "utisaj"):
            n.dejanje = zeleno
    return naloge


def razumi(besedilo: str, klic_modela: Optional[Callable[[list, dict], dict]] = None) -> Razumevanje:
    besedilo = " ".join(str(besedilo or "").split())[:300]
    if not besedilo:
        return Razumevanje(napaka="prazno")
    try:
        odgovor = (klic_modela or llama_server())(sporocila(besedilo), SHEMA)
    except Exception as e:  # noqa: BLE001
        return Razumevanje(napaka="model ni dosegljiv: " + (str(e) or type(e).__name__)[:120])
    naloge = popravi(besedilo, preveri(odgovor))
    return Razumevanje(naloge=naloge, napaka="" if naloge else "ni razumljivo")
