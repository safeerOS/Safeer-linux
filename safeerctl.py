#!/usr/bin/env python3
"""safeerctl - Safeer Link iz ukazne vrstice.

    safeerctl devices                       naprave v Safeer Linku
    safeerctl capabilities NAPRAVA          kaj naprava zna
    safeerctl info NAPRAVA                  procesor, pomnilnik, prostor, baterija (kar naprava pove o sebi);
                                            drugo ime: resources
    safeerctl apps NAPRAVA                  programi naprave
    safeerctl run PROGRAM --on NAPRAVA      zazeni program na napravi
    safeerctl send DATOTEKA... --to NAPRAVA poslji datoteke napravi
    safeerctl text BESEDILO --to NAPRAVA    poslji besedilo ali povezavo napravi
    safeerctl rename NAPRAVA IME            preimenuj napravo (za vse naprave v Linku)
    safeerctl internet [status]             internet prek telefona v Safeer Linku: stanje
    safeerctl internet mode off|failover|always [--via NAPRAVA] [--system-proxy on|off]
    safeerctl internet test [--via NAPRAVA] resnicna zahteva skozi telefon (pove, po katerem omrezju je sla)
    safeerctl internet env                  spremenljivke okolja za programe v tej lupini (eval "$(safeerctl internet env)")

Vsak ukaz pozna --json (pred ukazom ali za njim): strojno berljiv izpis za skripte in agente. NAPRAVA je id ali ime (dovolj je enolicen del
imena, brez sumnikov in velikih crk).

safeerctl nicesar ne pocne sam: govori s Safeer Controlom, ki tece v ozadju (D-Bus, vmesnik Naprave) - istim, ki ga
uporablja Safeer OS. Brez Controla pove, da ne tece, in konca z izhodno kodo 3.

Izhodne kode: 0 uspeh, 1 dejanje ni uspelo (razlog je izpisan), 2 napacna raba, 3 Safeer Control ne tece ali je
starejsi in ukaza se ne pozna.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Callable, List, Optional

KOREN = os.path.dirname(os.path.abspath(__file__))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

from core import link_zmoznosti  # noqa: E402
from core.iskalni_kljuc import kljuc as _kljuc  # noqa: E402

CONTROL_ID = "io.github.memelandfaner.SafeerControl"
CONTROL_POT = "/io/github/memelandfaner/SafeerControl"

IZHOD_OK, IZHOD_NEUSPEH, IZHOD_RABA, IZHOD_CONTROL = 0, 1, 2, 3

BESEDILA = {
    "sl": {
        "ni_controla": "Safeer Control ne teče. Zaženi ga (safeer-control --ozadje) in poskusi znova.",
        "stari_control": "Teče starejši Safeer Control, ki tega ukaza še ne pozna. Zaženi ga znova.",
        "ni_naprave": "Naprave »{ime}« ni v Safeer Linku.",
        "vec_naprav": "»{ime}« ustreza več napravam: {seznam}. Napiši več imena ali uporabi id.",
        "brez_naprav": "V Safeer Linku ni naprav.",
        "ta": "ta računalnik", "naprava": "NAPRAVA", "vrsta": "VRSTA", "id": "ID",
        "ni_zmoznosti": "Naprava ni povedala, kaj zna.",
        "ni_odgovora": "Naprava ni odgovorila.", "ni_programov": "Naprava ne deli programov.",
        "ni_programa": "Programa »{ime}« na napravi ni.", "vec_programov": "»{ime}« ustreza več programom: {seznam}.",
        "zagnano": "Zagnano na napravi {naprava}: {ime}", "ni_uspelo": "Ni uspelo: {razlog}",
        "posiljam": "Pošiljam napravi {naprava}: {ime} … {odst} %",
        "poslano": "Poslano napravi {naprava}: {n}", "mape_ne": " (mape niso poslane)",
        "besedilo_poslano": "Besedilo je poslano napravi {naprava}.",
        "preimenovano": "Naprava se zdaj imenuje »{ime}«.",
        "ne_sprejme": "Naprava {naprava} tega ne sprejme (manjka zmožnost »{zmoznost}«).",
        "procesor": "procesor", "pomnilnik": "pomnilnik", "prostor": "prostor", "baterija": "baterija", "sistem": "sistem",
        "grafika": "grafika", "pomoc": "sme pomagati", "da": "da", "ne": "ne", "prosto": "prosto", "jeder": "jeder",
        "obremenitev": "obremenitev", "polni": "se polni",
        "i_nacin": "način", "i_telefon": "telefon", "i_doma": "domači internet", "i_zdaj": "zdaj", "i_posrednik": "posrednik",
        "i_sistemski": "sistemski posrednik", "i_poraba": "skozi telefon", "i_mobilni": "mobilni podatki telefona",
        "i_izklopljeno": "izklopljeno", "i_izpad": "ob izpadu domačega interneta", "i_vedno": "vedno skozi telefon",
        "i_dela": "dela", "i_ne_dela": "ne dela", "i_neposredno": "neposredno", "i_prek": "skozi telefon",
        "i_ni_telefona": "v Safeer Linku ni telefona, ki deli internet",
        "i_dovoljeno": "dovoljeno", "i_caka": "čaka – na telefonu odpri Safeer OS in dovoli ta računalnik", "i_zavrnjeno": "telefon je ta računalnik zavrnil",
        "i_ne_deli": "deljenje je na telefonu izklopljeno", "i_stari": "na telefonu je starejši Safeer OS (posodobi ga)",
        "i_neznano": "telefon še ni odgovoril",
        "i_vklopljen": "vklopljen", "i_nastavljen": "vklopljen (zdaj nastavljen)", "i_izklopljen": "izklopljen",
        "i_ni_podprt": "to namizje ga ne podpira", "i_ne_tece": "ne teče",
        "i_danes": "danes", "i_mesec": "ta mesec", "i_od": "od", "i_brez_omejitve": "brez omejitve",
        "i_test_ok": "Deluje: zahteva je šla skozi telefon ({pot}), javni naslov {naslov}{drzava}. {ms} ms, {bajtov}.",
        "i_test_druga": "Javni naslov tega računalnika je drugačen ({naslov}) – promet res zapusti telefon po drugi poti.",
        "i_test_ista": "Javni naslov je enak kot neposredno ({naslov}): telefon je zahtevo poslal po istem omrežju kot ta računalnik.",
        "i_test_brez": "Neposredno ta računalnik zdaj nima interneta.",
        "i_pot_cellular": "mobilno omrežje", "i_pot_wifi": "Wi-Fi telefona", "i_pot_ethernet": "žično omrežje telefona",
        "i_pot_vpn": "VPN telefona", "i_pot_other": "drugo omrežje telefona",
        "i_nastavljeno": "Nastavljeno: {nacin}.",
        "i_env_ne_tece": "Posrednik ne teče (način je izklopljen). Vklopi ga: safeerctl internet mode failover",
        "r_ni_telefona": "v Safeer Linku ni telefona, ki deli internet (na telefonu: Nastavitve › Internet prek Safeer Linka)",
        "r_old_provider": "na telefonu je starejši Safeer OS; posodobi ga",
        "r_disabled": "deljenje interneta je na telefonu izklopljeno",
        "r_permission_required": "na telefonu odpri Safeer OS in dovoli temu računalniku uporabo interneta",
        "r_denied": "telefon je temu računalniku uporabo interneta zavrnil",
        "r_not_trusted": "telefon temu računalniku ne zaupa (ni v istem Safeer Linku)",
        "r_no_path": "telefon zdaj nima interneta", "r_mobile_off": "mobilni podatki na telefonu niso dovoljeni za deljenje",
        "r_no_mobile": "telefon nima mobilnega omrežja (kartica SIM, mobilni podatki)",
        "r_roaming": "telefon gostuje v tujem omrežju, deljenje v gostovanju ni dovoljeno",
        "r_limit": "mesečna omejitev mobilnih podatkov na telefonu je dosežena",
        "r_busy": "telefon ima odprtih preveč povezav", "r_busy_local": "odprtih je preveč povezav",
        "r_private_destination": "cilj je v zasebnem omrežju", "r_port_blocked": "ta vrata telefon ne posreduje",
        "r_dns_failed": "imena strežnika ni bilo mogoče razrešiti", "r_connect_failed": "strežnik se ni odzval",
        "r_timeout": "telefon ni odgovoril pravočasno", "r_link": "telefon ni dosegljiv v Safeer Linku",
        "r_sistemski": "sistemskega posrednika ni bilo mogoče nastaviti", "r_vrata": "posrednik ni dobil vrat",
        "r_ni_na_voljo": "Safeer Control še ni pripravljen", "r_napacna_zahteva": "napačna zahteva",
    },
    "en": {
        "ni_controla": "Safeer Control is not running. Start it (safeer-control --ozadje) and try again.",
        "stari_control": "An older Safeer Control is running and does not know this command yet. Restart it.",
        "ni_naprave": "There is no device “{ime}” in Safeer Link.",
        "vec_naprav": "“{ime}” matches several devices: {seznam}. Type more of the name or use the id.",
        "brez_naprav": "There are no devices in Safeer Link.",
        "ta": "this computer", "naprava": "DEVICE", "vrsta": "TYPE", "id": "ID",
        "ni_zmoznosti": "The device did not say what it can do.",
        "ni_odgovora": "The device did not answer.", "ni_programov": "The device does not share its apps.",
        "ni_programa": "There is no app “{ime}” on the device.", "vec_programov": "“{ime}” matches several apps: {seznam}.",
        "zagnano": "Started on {naprava}: {ime}", "ni_uspelo": "Failed: {razlog}",
        "posiljam": "Sending to {naprava}: {ime} … {odst} %",
        "poslano": "Sent to {naprava}: {n}", "mape_ne": " (folders were not sent)",
        "besedilo_poslano": "The text was sent to {naprava}.",
        "preimenovano": "The device is now called “{ime}”.",
        "ne_sprejme": "{naprava} does not accept this (capability “{zmoznost}” is missing).",
        "procesor": "processor", "pomnilnik": "memory", "prostor": "storage", "baterija": "battery", "sistem": "system",
        "grafika": "graphics", "pomoc": "may help", "da": "yes", "ne": "no", "prosto": "free", "jeder": "cores",
        "obremenitev": "load", "polni": "charging",
        "i_nacin": "mode", "i_telefon": "phone", "i_doma": "home internet", "i_zdaj": "now", "i_posrednik": "proxy",
        "i_sistemski": "system proxy", "i_poraba": "through the phone", "i_mobilni": "phone's mobile data",
        "i_izklopljeno": "off", "i_izpad": "when home internet is down", "i_vedno": "always through the phone",
        "i_dela": "works", "i_ne_dela": "down", "i_neposredno": "direct", "i_prek": "through the phone",
        "i_ni_telefona": "no phone in Safeer Link shares its internet",
        "i_dovoljeno": "allowed", "i_caka": "waiting – open Safeer OS on the phone and allow this computer", "i_zavrnjeno": "the phone refused this computer",
        "i_ne_deli": "sharing is switched off on the phone", "i_stari": "the phone runs an older Safeer OS (update it)",
        "i_neznano": "the phone has not answered yet",
        "i_vklopljen": "on", "i_nastavljen": "on (set right now)", "i_izklopljen": "off",
        "i_ni_podprt": "not supported on this desktop", "i_ne_tece": "not running",
        "i_danes": "today", "i_mesec": "this month", "i_od": "of", "i_brez_omejitve": "no limit",
        "i_test_ok": "Works: the request went through the phone ({pot}), public address {naslov}{drzava}. {ms} ms, {bajtov}.",
        "i_test_druga": "This computer's own public address is different ({naslov}) - the traffic really leaves the phone another way.",
        "i_test_ista": "The public address is the same as direct ({naslov}): the phone sent the request over the same network as this computer.",
        "i_test_brez": "This computer has no direct internet right now.",
        "i_pot_cellular": "mobile network", "i_pot_wifi": "the phone's Wi-Fi", "i_pot_ethernet": "the phone's wired network",
        "i_pot_vpn": "the phone's VPN", "i_pot_other": "another network of the phone",
        "i_nastavljeno": "Set: {nacin}.",
        "i_env_ne_tece": "The proxy is not running (the mode is off). Turn it on: safeerctl internet mode failover",
        "r_ni_telefona": "no phone in Safeer Link shares its internet (on the phone: Settings › Internet over Safeer Link)",
        "r_old_provider": "the phone runs an older Safeer OS; update it",
        "r_disabled": "internet sharing is switched off on the phone",
        "r_permission_required": "open Safeer OS on the phone and allow this computer to use its internet",
        "r_denied": "the phone refused to share its internet with this computer",
        "r_not_trusted": "the phone does not trust this computer (not in the same Safeer Link)",
        "r_no_path": "the phone has no internet right now", "r_mobile_off": "mobile data is not allowed for sharing on the phone",
        "r_no_mobile": "the phone has no mobile network (SIM card, mobile data)",
        "r_roaming": "the phone is roaming and sharing while roaming is not allowed",
        "r_limit": "the phone's monthly mobile data limit is reached",
        "r_busy": "the phone has too many open connections", "r_busy_local": "too many open connections",
        "r_private_destination": "the destination is in a private network", "r_port_blocked": "the phone does not forward this port",
        "r_dns_failed": "the server name could not be resolved", "r_connect_failed": "the server did not respond",
        "r_timeout": "the phone did not answer in time", "r_link": "the phone is not reachable in Safeer Link",
        "r_sistemski": "the system proxy could not be set", "r_vrata": "the proxy could not get a port",
        "r_ni_na_voljo": "Safeer Control is not ready yet", "r_napacna_zahteva": "bad request",
    },
}


def jezik() -> str:
    okolje = os.environ.get("SAFEER_OS_JEZIK") or os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or ""
    return "sl" if okolje.lower().startswith("sl") else "en"


def t(kljuc: str, **zamenjave) -> str:
    b = BESEDILA[jezik()].get(kljuc) or BESEDILA["en"].get(kljuc) or kljuc
    for k, v in zamenjave.items():
        b = b.replace("{" + k + "}", str(v))
    return b


class Napaka(Exception):
    """Dejanje ni uspelo; `izhod` je izhodna koda, `koda` kratka oznaka za --json."""

    def __init__(self, sporocilo: str, izhod: int = IZHOD_NEUSPEH, koda: str = "") -> None:
        super().__init__(sporocilo)
        self.izhod = izhod
        self.koda = koda


# ---------------------------------------------------------------------- Safeer Control (D-Bus)

def nastavi_vodilo_seje(okolje=None, obstaja: Callable[[str], bool] = os.path.exists) -> None:
    """Naslov vodila seje, kadar ga okolje nima (SSH-seja, cron, agent): pod systemd je vedno na /run/user/UID/bus.
    Brez tega bi ukaz v taki lupini trdil, da Safeer Control ne tece, ceprav tece."""
    okolje = os.environ if okolje is None else okolje
    if okolje.get("DBUS_SESSION_BUS_ADDRESS"):
        return
    pot = os.path.join(okolje.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid(), "bus")
    if obstaja(pot):
        okolje["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=" + pot


def klic_controla(metoda: str, *argumenti: str) -> dict:
    """Klic vmesnika Naprave v Safeer Controlu. Controla ne zaganja - ce ne tece, to pove."""
    try:
        nastavi_vodilo_seje()
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib
        vodilo = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        ima = vodilo.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "NameHasOwner",
                               GLib.Variant("(s)", (CONTROL_ID,)), GLib.VariantType("(b)"), Gio.DBusCallFlags.NONE, 3000, None)
        if not ima.unpack()[0]:
            raise Napaka(t("ni_controla"), IZHOD_CONTROL, "ni_controla")
        r = vodilo.call_sync(CONTROL_ID, CONTROL_POT + "/naprave", CONTROL_ID + ".Naprave", metoda,
                             GLib.Variant("(" + "s" * len(argumenti) + ")", tuple(argumenti)) if argumenti else None,
                             GLib.VariantType("(s)"), Gio.DBusCallFlags.NONE, 60000, None)
        izid = json.loads(r.unpack()[0])
        return izid if isinstance(izid, dict) else {"ok": False}
    except Napaka:
        raise
    except Exception as e:  # noqa: BLE001
        if "UnknownMethod" in str(e) or "No such method" in str(e):
            raise Napaka(t("stari_control"), IZHOD_CONTROL, "stari_control")
        raise Napaka(t("ni_controla"), IZHOD_CONTROL, "ni_controla")


# ---------------------------------------------------------------------- naprave

def naprave(klic: Callable[..., dict]) -> List[dict]:
    izid = klic("Seznam")
    return [n for n in (izid.get("naprave") or []) if isinstance(n, dict) and n.get("id")]


def najdi_napravo(seznam: List[dict], ime: str) -> dict:
    """Naprava po id-ju ali imenu: natancen id, natancno ime, sicer enolicen del imena (brez sumnikov in velikih crk)."""
    iskano = str(ime or "").strip()
    for n in seznam:
        if n.get("id") == iskano:
            return n
    k = _kljuc(iskano)
    natancne = [n for n in seznam if _kljuc(n.get("ime", "")) == k]
    delne = natancne or [n for n in seznam if k and k in _kljuc(n.get("ime", ""))]
    if len(delne) == 1:
        return delne[0]
    if not delne:
        raise Napaka(t("ni_naprave", ime=iskano), IZHOD_NEUSPEH, "ni_naprave")
    raise Napaka(t("vec_naprav", ime=iskano, seznam=", ".join(str(n.get("ime") or n["id"]) for n in delne)),
                 IZHOD_NEUSPEH, "vec_naprav")


def zahtevaj_zmoznost(n: dict, zmoznost: str) -> None:
    if zmoznost not in (n.get("zmoznosti") or []):
        raise Napaka(t("ne_sprejme", naprava=n.get("ime") or n["id"], zmoznost=zmoznost), IZHOD_NEUSPEH, "ni_zmoznosti")


def razlog(izid: dict) -> str:
    return str(izid.get("sporocilo") or izid.get("message") or izid.get("koda") or izid.get("napaka") or "?")


def tabela(vrstice: List[List[str]]) -> str:
    if not vrstice:
        return ""
    sirine = [max(len(str(v[i])) for v in vrstice) for i in range(len(vrstice[0]))]
    return "\n".join("  ".join(str(c).ljust(sirine[i]) for i, c in enumerate(v)).rstrip() for v in vrstice)


def velikost(bajtov) -> str:
    try:
        b = float(bajtov)
    except (TypeError, ValueError):
        return "?"
    for enota in ("B", "KiB", "MiB", "GiB", "TiB"):
        if b < 1024 or enota == "TiB":
            niz = ("%.0f %s" % (b, enota)) if enota == "B" else ("%.1f %s" % (b, enota))
            return niz.replace(".", ",") if jezik() == "sl" else niz
        b /= 1024
    return "?"


# ---------------------------------------------------------------------- ukazi

def ukaz_devices(a, klic, izpis) -> int:
    seznam = naprave(klic)
    if a.json:
        izpis(json.dumps({"ok": True, "devices": [
            {"id": n["id"], "name": n.get("ime", ""), "platform": n.get("platforma", ""), "kind": n.get("vrsta", ""),
             "capabilities": link_zmoznosti.znane(n.get("zmoznosti")), "this": bool(n.get("ta"))} for n in seznam]},
            ensure_ascii=False))
        return IZHOD_OK
    if not seznam:
        izpis(t("brez_naprav"))
        return IZHOD_OK
    vrstice = [[t("naprava"), t("vrsta"), t("id")]]
    for n in seznam:
        vrstice.append([str(n.get("ime") or n["id"]) + (" (" + t("ta") + ")" if n.get("ta") else ""),
                        str(n.get("platforma") or n.get("vrsta") or ""), n["id"]])
    izpis(tabela(vrstice))
    return IZHOD_OK


def ukaz_capabilities(a, klic, izpis) -> int:
    n = najdi_napravo(naprave(klic), a.naprava)
    zmoznosti = link_zmoznosti.znane(n.get("zmoznosti"))
    if a.json:
        izpis(json.dumps({"ok": True, "id": n["id"], "name": n.get("ime", ""), "capabilities": [
            {"name": z, "description": link_zmoznosti.opis(z, "en"), "known": z in link_zmoznosti.ZMOZNOSTI} for z in zmoznosti]},
            ensure_ascii=False))
        return IZHOD_OK
    if not zmoznosti:
        izpis(t("ni_zmoznosti"))
        return IZHOD_OK
    izpis(tabela([[z, link_zmoznosti.opis(z, jezik())] for z in zmoznosti]))
    return IZHOD_OK


def ukaz_info(a, klic, izpis) -> int:
    n = najdi_napravo(naprave(klic), a.naprava)
    izid = klic("Ukaz", n["id"], "host.info", "{}")
    d = izid.get("data") if izid.get("ok") else None
    if not isinstance(d, dict):
        raise Napaka(t("ni_odgovora") if not izid.get("message") else t("ni_uspelo", razlog=razlog(izid)), IZHOD_NEUSPEH,
                     str(izid.get("koda") or "ni_odgovora"))
    if a.json:
        izpis(json.dumps({"ok": True, "id": n["id"], "name": n.get("ime", ""), "info": d}, ensure_ascii=False))
        return IZHOD_OK
    vrstice = []
    if d.get("sistem") or d.get("hostname"):
        vrstice.append([t("sistem"), " · ".join(str(x) for x in (d.get("sistem"), d.get("hostname")) if x)])
    cpu = d.get("cpu") if isinstance(d.get("cpu"), dict) else {}
    if cpu:
        deli = [str(cpu.get("model") or "").strip(), ("%s %s" % (cpu.get("jedra"), t("jeder"))) if cpu.get("jedra") else "",
                ("%s %s" % (t("obremenitev"), cpu.get("obremenitev"))) if cpu.get("obremenitev") is not None else ""]
        vrstice.append([t("procesor"), " · ".join(x for x in deli if x)])
    for kljuc, ime in (("ram", "pomnilnik"), ("disk", "prostor")):
        x = d.get(kljuc) if isinstance(d.get(kljuc), dict) else {}
        if x:
            vrstice.append([t(ime), "%s %s / %s" % (velikost(x.get("prosto")), t("prosto"), velikost(x.get("skupaj")))])
    gpu = d.get("gpu")
    if isinstance(gpu, dict) and (gpu.get("model") or gpu.get("ime")):
        vrstice.append([t("grafika"), str(gpu.get("model") or gpu.get("ime"))])
    elif isinstance(gpu, str) and gpu:
        vrstice.append([t("grafika"), gpu])
    bat = d.get("baterija") if isinstance(d.get("baterija"), dict) else {}
    if bat.get("raven") is not None:
        vrstice.append([t("baterija"), "%s %%" % bat.get("raven") + (" (" + t("polni") + ")" if bat.get("polni") else "")])
    pomoc = d.get("pomoc") if isinstance(d.get("pomoc"), dict) else {}
    if "lahko" in pomoc:
        vrstice.append([t("pomoc"), t("da") if pomoc.get("lahko") else t("ne") + (" (%s)" % pomoc.get("razlog") if pomoc.get("razlog") else "")])
    izpis(tabela(vrstice) if vrstice else json.dumps(d, ensure_ascii=False, indent=2))
    return IZHOD_OK


def _programi(klic, n: dict) -> List[dict]:
    izid = klic("Aplikacije", n["id"])
    if not izid.get("ok"):
        raise Napaka(t("ni_uspelo", razlog=razlog(izid)), IZHOD_NEUSPEH, str(izid.get("koda") or "napaka"))
    return [{"id": str(p.get("id")), "name": str(p.get("name") or p.get("id")), "group": str(p.get("group") or "")}
            for p in (izid.get("items") or []) if isinstance(p, dict) and p.get("id")]


def ukaz_apps(a, klic, izpis) -> int:
    n = najdi_napravo(naprave(klic), a.naprava)
    programi = _programi(klic, n)
    if a.json:
        izpis(json.dumps({"ok": True, "id": n["id"], "name": n.get("ime", ""), "apps": programi}, ensure_ascii=False))
        return IZHOD_OK
    if not programi:
        izpis(t("ni_programov"))
        return IZHOD_OK
    izpis(tabela([[p["name"], p["id"]] for p in sorted(programi, key=lambda p: _kljuc(p["name"]))]))
    return IZHOD_OK


def ukaz_run(a, klic, izpis) -> int:
    n = najdi_napravo(naprave(klic), a.on)
    programi = _programi(klic, n)
    k = _kljuc(a.program)
    ujemanja = [p for p in programi if p["id"] == a.program] or [p for p in programi if _kljuc(p["name"]) == k] \
        or [p for p in programi if k and k in _kljuc(p["name"])]
    if not ujemanja:
        raise Napaka(t("ni_programa", ime=a.program), IZHOD_NEUSPEH, "ni_programa")
    if len(ujemanja) > 1:
        raise Napaka(t("vec_programov", ime=a.program, seznam=", ".join(p["name"] for p in ujemanja[:8])), IZHOD_NEUSPEH, "vec_programov")
    p = ujemanja[0]
    izid = klic("Zazeni", n["id"], p["id"])
    if not izid.get("ok"):
        raise Napaka(t("ni_uspelo", razlog=razlog(izid)), IZHOD_NEUSPEH, str(izid.get("koda") or "napaka"))
    izpis(json.dumps({"ok": True, "id": n["id"], "app": p}, ensure_ascii=False) if a.json
          else t("zagnano", naprava=n.get("ime") or n["id"], ime=p["name"]))
    return IZHOD_OK


def ukaz_send(a, klic, izpis, napredek: Optional[Callable[[str], None]] = None, spi: Callable[[float], None] = time.sleep) -> int:
    n = najdi_napravo(naprave(klic), a.to)
    zahtevaj_zmoznost(n, "file")
    poti = [os.path.abspath(os.path.expanduser(p)) for p in a.datoteke]
    izid = klic("Poslji", n["id"], json.dumps(poti))
    if not izid.get("ok"):
        raise Napaka(t("ni_uspelo", razlog=razlog(izid)), IZHOD_NEUSPEH, str(izid.get("koda") or "napaka"))
    ime = n.get("ime") or n["id"]
    brez_odgovora = 0
    while izid.get("stanje") == "posiljam":
        if napredek and not a.json:
            napredek(t("posiljam", naprava=ime, ime=izid.get("ime", ""), odst=izid.get("odstotek", 0)))
        spi(0.4)
        novo = klic("PosljiStanje", str(izid.get("id") or ""))
        if not novo.get("ok"):
            brez_odgovora += 1
            if brez_odgovora > 5:
                raise Napaka(t("ni_uspelo", razlog=razlog(novo)), IZHOD_NEUSPEH, str(novo.get("koda") or "napaka"))
            continue
        brez_odgovora, izid = 0, novo
    if izid.get("stanje") != "poslano":
        raise Napaka(t("ni_uspelo", razlog=razlog(izid)), IZHOD_NEUSPEH, str(izid.get("koda") or "napaka"))
    if a.json:
        izpis(json.dumps({"ok": True, "id": n["id"], "name": ime, "files": izid.get("datotek"), "sent": izid.get("poslanih"),
                          "skipped_folders": izid.get("mape", 0)}, ensure_ascii=False))
    else:
        izpis(t("poslano", naprava=ime, n=izid.get("poslanih")) + (t("mape_ne") if izid.get("mape") else ""))
    return IZHOD_OK


def ukaz_text(a, klic, izpis) -> int:
    n = najdi_napravo(naprave(klic), a.to)
    zahtevaj_zmoznost(n, "text")
    izid = klic("Besedilo", n["id"], a.besedilo)
    if not izid.get("ok"):
        raise Napaka(t("ni_uspelo", razlog=razlog(izid)), IZHOD_NEUSPEH, str(izid.get("koda") or "napaka"))
    izpis(json.dumps({"ok": True, "id": n["id"], "name": n.get("ime", "")}, ensure_ascii=False) if a.json
          else t("besedilo_poslano", naprava=n.get("ime") or n["id"]))
    return IZHOD_OK


def ukaz_rename(a, klic, izpis) -> int:
    n = najdi_napravo(naprave(klic), a.naprava)
    izid = klic("Preimenuj", n["id"], a.ime)
    if not izid.get("ok"):
        raise Napaka(t("ni_uspelo", razlog=razlog(izid)), IZHOD_NEUSPEH, str(izid.get("koda") or "napaka"))
    novo = str(izid.get("ime") or a.ime)
    izpis(json.dumps({"ok": True, "id": n["id"], "name": novo}, ensure_ascii=False) if a.json else t("preimenovano", ime=novo))
    return IZHOD_OK


# ---------------------------------------------------------------------- internet prek telefona

NACINI_INTERNETA = {"off": "izklopljeno", "failover": "izpad", "always": "vedno"}


def razlog_interneta(koda: str) -> str:
    b = t("r_" + str(koda or ""))
    return str(koda or "?") if b.startswith("r_") else b


def _dovoljenje(stanje: dict) -> str:
    p = stanje.get("ponudnik")
    if not stanje.get("telefon"):
        return t("i_ni_telefona")
    if not isinstance(p, dict):
        return t("i_stari") if stanje.get("napaka") == "old_provider" or stanje.get("brez_odgovora") else t("i_neznano")
    if not p.get("enabled", True):
        return t("i_ne_deli")
    return {"allowed": t("i_dovoljeno"), "pending": t("i_caka"), "denied": t("i_zavrnjeno")}.get(str(p.get("permission")), t("i_neznano"))


def _izpis_stanja_interneta(s: dict) -> str:
    nacin = {"izklopljeno": t("i_izklopljeno"), "izpad": t("i_izpad"), "vedno": t("i_vedno")}.get(s.get("nacin"), str(s.get("nacin")))
    ime = next((x.get("ime") or x.get("id") for x in s.get("telefoni") or [] if x.get("id") == s.get("telefon")), "")
    vrstice = [[t("i_nacin"), nacin],
               [t("i_telefon"), (ime + " – " if ime else "") + _dovoljenje(s)]]
    if s.get("nacin") == "izpad":
        vrstice.append([t("i_doma"), t("i_dela") if (s.get("fiksna") or {}).get("dela") else t("i_ne_dela")])
    if s.get("nacin") != "izklopljeno":
        vrstice.append([t("i_zdaj"), t("i_prek") if s.get("prek_telefona") else t("i_neposredno")])
    p = s.get("posrednik") or {}
    vrstice.append([t("i_posrednik"), "%s:%s (SOCKS5, HTTP)" % (p.get("naslov"), p.get("vrata")) if p.get("tece") else t("i_ne_tece")])
    sis = s.get("sistemski") or {}
    vrstice.append([t("i_sistemski"), t("i_ni_podprt") if not sis.get("podprt") else
                    t("i_nastavljen") if sis.get("nastavljen") else t("i_vklopljen") if sis.get("vklopljen") else t("i_izklopljen")])
    por = s.get("poraba") or {}
    vrstice.append([t("i_poraba"), "%s %s · %s %s" % (t("i_danes"), velikost(por.get("danes", 0)), t("i_mesec"), velikost(por.get("mesec", 0)))])
    mob = (s.get("ponudnik") or {}).get("cellular") if isinstance(s.get("ponudnik"), dict) else None
    if isinstance(mob, dict):
        meja = mob.get("limit_bytes") or 0
        vrstice.append([t("i_mobilni"), "%s %s · %s %s %s" % (
            t("i_danes"), velikost(mob.get("used_today", 0)), t("i_mesec"), velikost(mob.get("used_month", 0)),
            (t("i_od") + " " + velikost(meja)) if meja else "(" + t("i_brez_omejitve") + ")")])
    if s.get("napaka"):
        vrstice.append(["!", razlog_interneta(s["napaka"])])
    return tabela(vrstice)


def ukaz_internet(a, klic, izpis) -> int:
    dejanje = a.dejanje or "status"
    if dejanje == "status":
        s = klic("Internet", "stanje", json.dumps({"vprasaj": True}))
        if not s.get("ok"):
            raise Napaka(t("ni_uspelo", razlog=razlog_interneta(s.get("koda"))), IZHOD_NEUSPEH, str(s.get("koda") or "napaka"))
        izpis(json.dumps(s, ensure_ascii=False) if a.json else _izpis_stanja_interneta(s))
        return IZHOD_OK
    if dejanje == "mode":
        if a.vrednost not in NACINI_INTERNETA:
            raise Napaka("mode: off | failover | always", IZHOD_RABA, "raba")
        p = {"nacin": NACINI_INTERNETA[a.vrednost]}
        if a.via is not None:
            p["naprava"] = najdi_napravo(naprave(klic), a.via)["id"] if a.via else ""
        if a.system_proxy is not None:
            p["sistemski"] = a.system_proxy == "on"
        s = klic("Internet", "nastavi", json.dumps(p))
        if not s.get("ok"):
            raise Napaka(t("ni_uspelo", razlog=razlog_interneta(s.get("koda"))), IZHOD_NEUSPEH, str(s.get("koda") or "napaka"))
        izpis(json.dumps(s, ensure_ascii=False) if a.json else _izpis_stanja_interneta(s))
        return IZHOD_OK
    if dejanje == "test":
        p = {"pot": a.path or "", "stari": bool(a.legacy)}
        if a.via:
            p["naprava"] = najdi_napravo(naprave(klic), a.via)["id"]
        s = klic("Internet", "preizkus", json.dumps(p))
        if a.json:
            izpis(json.dumps(s, ensure_ascii=False))
            return IZHOD_OK if s.get("ok") else IZHOD_NEUSPEH
        if not s.get("ok"):
            raise Napaka(t("ni_uspelo", razlog=razlog_interneta(s.get("koda"))), IZHOD_NEUSPEH, str(s.get("koda") or "napaka"))
        pot = t("i_pot_" + (str(s.get("vrsta_poti") or "other")))
        izpis(t("i_test_ok", pot=pot if not pot.startswith("i_pot_") else str(s.get("vrsta_poti") or "?"),
                naslov=s.get("naslov_prek_telefona") or "?", drzava=(", " + s["drzava"]) if s.get("drzava") else "",
                ms=s.get("skupaj_ms", "?"), bajtov=velikost(s.get("bajtov", 0))))
        if not s.get("naslov_neposredno"):
            izpis(t("i_test_brez"))
        else:
            izpis(t("i_test_druga" if s.get("druga_pot") else "i_test_ista", naslov=s["naslov_neposredno"]))
        return IZHOD_OK
    if dejanje == "env":
        s = klic("Internet", "okolje", "{}")
        if not s.get("ok"):
            raise Napaka(t("ni_uspelo", razlog=razlog_interneta(s.get("koda"))), IZHOD_NEUSPEH, str(s.get("koda") or "napaka"))
        if a.json:
            izpis(json.dumps(s, ensure_ascii=False))
            return IZHOD_OK
        if not s.get("tece"):
            raise Napaka(t("i_env_ne_tece"), IZHOD_NEUSPEH, "ne_tece")
        izpis("\n".join("export %s=%s" % (k, v) for k, v in sorted((s.get("okolje") or {}).items())))
        return IZHOD_OK
    raise Napaka("internet: status | mode | test | env", IZHOD_RABA, "raba")


# ---------------------------------------------------------------------- vhod

def razclenjevalnik() -> argparse.ArgumentParser:
    skupno = argparse.ArgumentParser(add_help=False)
    skupno.add_argument("--json", action="store_true", help="machine-readable output")
    p = argparse.ArgumentParser(prog="safeerctl", description="Safeer Link from the command line (talks to Safeer Control).")
    p.add_argument("--version", action="store_true", help="print the version and exit")
    # Isto stikalo kot pri ukazih; svoj cilj, ker bi ga privzeta vrednost podukaza sicer prepisala.
    p.add_argument("--json", dest="json_zgoraj", action="store_true", help="machine-readable output (also accepted after the command)")
    ukazi = p.add_subparsers(dest="ukaz", metavar="COMMAND")
    ukazi.add_parser("devices", parents=[skupno], help="list the devices in Safeer Link").set_defaults(f=ukaz_devices)
    u = ukazi.add_parser("capabilities", parents=[skupno], help="what a device can do")
    u.add_argument("naprava", metavar="DEVICE")
    u.set_defaults(f=ukaz_capabilities)
    u = ukazi.add_parser("info", aliases=["resources"], parents=[skupno], help="processor, memory, storage, battery of a device")
    u.add_argument("naprava", metavar="DEVICE")
    u.set_defaults(f=ukaz_info)
    u = ukazi.add_parser("apps", parents=[skupno], help="apps a device shares")
    u.add_argument("naprava", metavar="DEVICE")
    u.set_defaults(f=ukaz_apps)
    u = ukazi.add_parser("run", parents=[skupno], help="start an app on a device")
    u.add_argument("program", metavar="APP")
    u.add_argument("--on", required=True, metavar="DEVICE")
    u.set_defaults(f=ukaz_run)
    u = ukazi.add_parser("send", parents=[skupno], help="send files to a device")
    u.add_argument("datoteke", metavar="FILE", nargs="+")
    u.add_argument("--to", required=True, metavar="DEVICE")
    u.set_defaults(f=ukaz_send)
    u = ukazi.add_parser("text", parents=[skupno], help="send text or a link to a device")
    u.add_argument("besedilo", metavar="TEXT")
    u.add_argument("--to", required=True, metavar="DEVICE")
    u.set_defaults(f=ukaz_text)
    u = ukazi.add_parser("rename", parents=[skupno], help="rename a device for every device in Safeer Link")
    u.add_argument("naprava", metavar="DEVICE")
    u.add_argument("ime", metavar="NAME")
    u.set_defaults(f=ukaz_rename)
    u = ukazi.add_parser("internet", parents=[skupno], help="internet through a phone in Safeer Link: status, mode, test, env")
    u.add_argument("dejanje", metavar="ACTION", nargs="?", choices=["status", "mode", "test", "env"],
                   help="status (default) | mode off|failover|always | test | env")
    u.add_argument("vrednost", metavar="VALUE", nargs="?", help="for mode: off, failover or always")
    u.add_argument("--via", metavar="DEVICE", help="the phone to use (default: the first one that shares its internet)")
    u.add_argument("--system-proxy", choices=["on", "off"], help="for mode: set the desktop proxy while traffic goes through the phone")
    u.add_argument("--path", choices=["mobile", "any", "wifi"], help="for test: which network of the phone (default: the configured one)")
    u.add_argument("--legacy", action="store_true", help="for test: also try a phone with an older Safeer OS (diagnostics)")
    u.set_defaults(f=ukaz_internet)
    return p


def razlicica() -> str:
    try:
        with open(os.path.join(KOREN, "packaging", "VERSION_CONTROL"), encoding="utf-8") as d:
            return d.read().strip()
    except OSError:
        return "?"


def main(argv: Optional[List[str]] = None, klic: Callable[..., dict] = klic_controla,
         izpis: Callable[[str], None] = print, napaka: Optional[Callable[[str], None]] = None) -> int:
    napaka = napaka or (lambda s: print(s, file=sys.stderr))
    p = razclenjevalnik()
    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        return IZHOD_RABA if e.code not in (0, None) else IZHOD_OK
    if a.version:
        izpis("safeerctl " + razlicica())
        return IZHOD_OK
    if not getattr(a, "f", None):
        p.print_help()
        return IZHOD_RABA
    a.json = bool(getattr(a, "json", False) or getattr(a, "json_zgoraj", False))
    kot_json = a.json
    try:
        if a.f is ukaz_send:
            # Napredek v eni vrstici na stderr (samo v terminalu); na koncu jo pocistimo, da izid ostane cist.
            v_terminalu = sys.stderr.isatty() and not kot_json

            def napredek(s: str) -> None:
                sys.stderr.write("\r\033[K" + s)
                sys.stderr.flush()
            try:
                return ukaz_send(a, klic, izpis, napredek=napredek if v_terminalu else None)
            finally:
                if v_terminalu:
                    sys.stderr.write("\r\033[K")
                    sys.stderr.flush()
        return a.f(a, klic, izpis)
    except Napaka as e:
        if kot_json:
            izpis(json.dumps({"ok": False, "error": str(e), "code": e.koda}, ensure_ascii=False))
        else:
            napaka(str(e))
        return e.izhod


if __name__ == "__main__":
    sys.exit(main())
