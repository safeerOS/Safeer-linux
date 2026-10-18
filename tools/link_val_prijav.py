#!/usr/bin/env python3
"""Meritev vala prijav na sredisce Safeer Linka: koliko bajtov seznamov naprav poslje sredisce, kdaj imajo vsi
odjemalci cel seznam in koliko procesorja porabi sredisce (core/link_spremembe.py, docs/LINK-MESH.md).

Dva nacina:

  obdelaj   pravi Hub.obdelaj in prave prijave brez omrezja (isti preizkus kot 18. 10. 2026 pred spremembo):
            povezava samo steje bajte in hrani, kar bo odjemalec potreboval za preverjanje.
  zanka     pravo sredisce (TLS, WebSocket, izhodne vrste) v svojem procesu na 127.0.0.1, N pravih odjemalcev v
            drugem procesu, vsi hkrati. Cas do konvergence: dokler VSAK odjemalec nima vseh N naprav.

    python3.12 tools/link_val_prijav.py obdelaj 32 100 200 400 [--okno 0.15] [--razpon 2] [--stari 0.5]
    python3.12 tools/link_val_prijav.py zanka 32 100 200 400 [--okno 0.15] [--stari 0.5] [--rok 180]

Isti ukaz dela tudi na starejsi kodi (brez core/link_spremembe): takrat so vsi odjemalci stari in okna ni.
Nic ne ostane za sabo: sredisce je podproces, ki se konca z meritvijo; zacasne datoteke v mapi mktemp.
"""
import argparse
import json
import os
import resource
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

try:
    from core import link_spremembe  # noqa: E402
except ImportError:      # starejsa koda (pred 1.0.127): samo celi seznami
    link_spremembe = None

ZMOZNOSTI = ["url", "text", "file", "screen", "remote", "e2e1"]


def _id(i: int) -> str:
    return "val-%04d" % i


def _prijava(did: str, nova: bool) -> str:
    zm = list(ZMOZNOSTI) + (["devdelta1"] if nova else [])
    return json.dumps({"id": "r-" + did, "type": "cast.register",
                       "payload": {"device_id": did, "name": "Naprava " + did[-4:], "role": "sender",
                                   "capabilities": zm, "platform": "linux", "protocol": "1", "kind": "desktop",
                                   "version": "1.0.127"}})


def _cpu() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF)
    return r.ru_utime + r.ru_stime


def _berljivo(b: float) -> str:
    for enota in ("B", "kB", "MB", "GB"):
        if b < 1000 or enota == "GB":
            return ("%d %s" % (b, enota)) if enota == "B" else ("%.1f %s" % (b, enota))
        b /= 1000.0
    return str(b)


class _Odjemalec:
    """Kar odjemalec dobi; za stare samo zadnji posnetek (pri 400 napravah bi vseh bilo 5 GB)."""

    def __init__(self, did: str, nov: bool):
        self.did = did
        self.nov = nov
        self.zaklep = threading.Lock()
        self.bajtov = 0
        self.bajtov_seznamov = 0
        self.sporocil = 0
        self.zahtev = 0
        self.prejemnik = link_spremembe.Prejemnik() if (nov and link_spremembe) else None
        self.seznam = []
        self.cas_celega = None

    def sprejmi(self, besedilo: str, cas: float, vseh: int):
        with self.zaklep:
            n = len(besedilo.encode("utf-8"))
            self.bajtov += n
            self.sporocil += 1
            s = json.loads(besedilo)
            if s.get("type") not in ("cast.devices", "cast.devices.delta"):
                return None
            self.bajtov_seznamov += n
            if self.prejemnik is not None:
                s, zahtevaj = self.prejemnik.sprejmi(s)
                if zahtevaj:
                    self.zahtev += 1
                    return "zahteva"
                if s is None:
                    return None
            self.seznam = s.get("devices") or []
            if len(self.seznam) == vseh and self.cas_celega is None:
                self.cas_celega = cas
            elif len(self.seznam) != vseh:
                self.cas_celega = None
        return None


# ---------------------------------------------------------------------------------------------- nacin obdelaj

class _LaznaPovezava:
    def __init__(self, did: str, naslov: str):
        self.naslov = naslov
        self.podatki = {"id": did}
        self.dnevnik = []       # (cas, besedilo) - samo seznami; staremu samo zadnji posnetek
        self.bajtov = 0
        self.bajtov_seznamov = 0

    def poslji(self, besedilo: str) -> bool:
        n = len(besedilo.encode("utf-8"))
        self.bajtov += n
        glava = besedilo[:48]
        if '"cast.devices.delta"' in glava:
            self.bajtov_seznamov += n
            self.dnevnik.append((time.monotonic(), besedilo))
        elif '"cast.devices"' in glava:
            self.bajtov_seznamov += n
            self.dnevnik = [(time.monotonic(), besedilo)]       # posnetek nadomesti vse prej
        return True

    def zapri(self, *_a, **_k):
        pass


def nacin_obdelaj(n: int, okno: float, razpon: float, stari: float) -> dict:
    from core import link_hub_streznik as lhs
    k = {"okno_s": okno} if link_spremembe else {}
    hub = lhs.Hub(odtis="ab" * 32, nas_id="n-sredisce", **k)
    povezave = []
    novih = int(round(n * (1.0 - stari))) if link_spremembe else 0
    cpu0, t0 = _cpu(), time.monotonic()
    for i in range(n):
        did = _id(i)
        p = _LaznaPovezava(did, "10.1.%d.%d" % (i // 250, i % 250 + 1))
        povezave.append((p, i >= n - novih))
        odgovor = json.loads(hub.obdelaj(p, _prijava(did, i >= n - novih)))
        assert odgovor["status"] == "accepted", odgovor
        if razpon > 0:
            cilj = t0 + razpon * (i + 1) / n
            while time.monotonic() < cilj:
                time.sleep(max(0.0, min(0.01, cilj - time.monotonic())))
    # Konec vala: zadnja objava po oknu.
    time.sleep(max(0.3, 3 * okno))
    cpu = _cpu() - cpu0
    # Preverjanje: vsak odjemalec sestavi seznam iz tega, kar je dobil, in ga primerja s celim seznamom sredisca.
    konec = 0.0
    neujemanj = 0
    for p, nov in povezave:
        o = _Odjemalec(p.podatki["id"], nov)
        for cas, besedilo in p.dnevnik:
            o.sprejmi(besedilo, cas, n)
        pricakovano = [{k2: v for k2, v in d.items() if k2 != "last_seen"} for d in json.loads(hub.seznam_json(p))["devices"]]
        dobljeno = [{k2: v for k2, v in d.items() if k2 != "last_seen"} for d in o.seznam]
        if dobljeno != pricakovano or o.zahtev:
            neujemanj += 1
        if p.dnevnik:
            konec = max(konec, p.dnevnik[-1][0])
    try:
        hub.ustavi_objave()
    except AttributeError:
        pass
    return {"naprav": n, "novih": novih, "okno_s": okno if link_spremembe else None, "razpon_s": razpon,
            "bajtov_seznamov": sum(p.bajtov_seznamov for p, _ in povezave),
            "bajtov_vseh": sum(p.bajtov for p, _ in povezave),
            "sporocil_seznamov": None,
            "konvergenca_s": round(konec - t0, 3), "cpu_s": round(cpu, 3), "neujemanj": neujemanj}


# ---------------------------------------------------------------------------------------------- nacin zanka

def sredisce(mapa: str, okno: float) -> None:
    """Podproces: pravo sredisce na 127.0.0.1. Na stdin bere ukaze, na stdout odgovarja z JSON."""
    # Odgovori gredo po svojem izhodu; kar sredisce izpise samo (npr. »naprava ne bere«), gre v dnevnik (stderr).
    odgovori = os.fdopen(os.dup(1), "w")
    sys.stdout = sys.stderr
    from core import link_datoteke, link_hub_streznik as lhs, link_ws, link_viri
    link_viri.POSLUSALCI[:] = []
    stevec = {"bajtov": 0, "seznamov": 0, "sporocil_seznamov": 0, "zaprtih_zaradi_vrste": 0}
    zaklep = threading.Lock()
    izvirni = link_ws.Povezava.poslji

    def poslji(self, besedilo, **k):
        ok = izvirni(self, besedilo, **k)
        n = len(besedilo.encode("utf-8"))
        glava = besedilo[:48]
        with zaklep:
            stevec["bajtov"] += n
            if '"cast.devices' in glava:
                stevec["seznamov"] += n
                stevec["sporocil_seznamov"] += 1
            if not ok:
                stevec["zaprtih_zaradi_vrste"] += 1
        return ok
    link_ws.Povezava.poslji = poslji
    # Vstopnica "t-<id>" velja (preizkus meri objavo seznamov, ne prijave s podpisom).
    lhs.Hub.porabi_vstopnico_s_podpisom = lambda self, v: ((v[2:], True) if str(v or "").startswith("t-") else ("", False))
    kljuc, potrdilo, odtis = link_datoteke.zagotovi_potrdilo(mapa)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(potrdilo, kljuc)
    k = {"okno_s": okno} if link_spremembe else {}
    hub = lhs.Hub(odtis=odtis, nas_id="n-sredisce", **k)
    streznik = lhs._Streznik(("127.0.0.1", 0), lhs._Obravnava)
    streznik.socket = ctx.wrap_socket(streznik.socket, server_side=True, do_handshake_on_connect=False)
    streznik.hub = hub
    streznik.obramba = lhs.link_obramba.Obramba()
    streznik.obramba.zaupan = hub.ima_povezavo_z
    streznik.datoteke = lambda: None
    streznik.zaslon = lambda: None
    threading.Thread(target=streznik.serve_forever, daemon=True).start()
    print(json.dumps({"vrata": streznik.server_address[1], "odtis": odtis}), file=odgovori, flush=True)
    for vrstica in sys.stdin:
        ukaz = vrstica.strip()
        if ukaz == "stanje":
            with zaklep:
                print(json.dumps(dict(stevec, cpu_s=_cpu(), povezanih=len(hub.povezane()))), file=odgovori, flush=True)
        elif ukaz == "konec":
            break
    try:
        hub.ustavi_objave()
    except AttributeError:
        pass
    streznik.shutdown()
    streznik.server_close()


def nacin_zanka(n: int, okno: float, stari: float, rok: float) -> dict:
    from core import link_hub
    mapa = tempfile.mkdtemp(prefix="safeer-val-")
    okolje = dict(os.environ, XDG_CONFIG_HOME=mapa, PYTHONPATH=KOREN)
    dnevnik = open(os.path.join(mapa, "sredisce.log"), "w")
    proces = subprocess.Popen([sys.executable, os.path.abspath(__file__), "_sredisce", mapa, str(okno)],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=dnevnik, text=True, env=okolje, cwd=mapa)
    try:
        zacetek = json.loads(proces.stdout.readline())
        vrata, odtis = zacetek["vrata"], zacetek["odtis"]

        def stanje() -> dict:
            proces.stdin.write("stanje\n")
            proces.stdin.flush()
            return json.loads(proces.stdout.readline())

        novih = int(round(n * (1.0 - stari))) if link_spremembe else 0
        odjemalci = [_Odjemalec(_id(i), i >= n - novih) for i in range(n)]
        start = threading.Event()
        izpadli = []
        niti = []

        def tek(o: _Odjemalec) -> None:
            start.wait()
            try:
                ws = link_hub.WsOdjemalec("wss://127.0.0.1:%d/cast/ws?ticket=t-%s" % (vrata, o.did), timeout=rok,
                                          odtis=odtis)
                ws.odpri()
                ws.poslji(_prijava(o.did, o.nov))
                while True:
                    besedilo = ws.prejmi()
                    if besedilo is None:
                        izpadli.append(o.did)
                        return
                    if o.sprejmi(besedilo, time.monotonic(), n) == "zahteva":
                        ws.poslji(json.dumps({"id": "z", "type": "cast.devices.sync"}))
            except Exception as e:  # noqa: BLE001
                if not ustavi.is_set():
                    izpadli.append("%s: %s" % (o.did, type(e).__name__))

        ustavi = threading.Event()
        for o in odjemalci:
            t = threading.Thread(target=tek, args=(o,), daemon=True)
            t.start()
            niti.append(t)
        cpu0 = stanje()["cpu_s"]
        t0 = time.monotonic()
        start.set()
        konec = None
        while time.monotonic() - t0 < rok:
            time.sleep(0.05)
            if all(o.cas_celega is not None for o in odjemalci):
                konec = max(o.cas_celega for o in odjemalci)
                break
            if len(izpadli) + sum(1 for o in odjemalci if o.cas_celega is not None) >= n and izpadli:
                break
        time.sleep(max(0.5, 3 * okno))          # zadnje spremembe po oknu (bajti)
        s = stanje()
        ustavi.set()
        dnevnik.flush()
        with open(os.path.join(mapa, "sredisce.log")) as f:
            ne_bere = sum(1 for v in f if "ne bere" in v)
        return {"naprav": n, "novih": novih, "okno_s": okno if link_spremembe else None,
                "bajtov_seznamov": s["seznamov"], "bajtov_vseh": s["bajtov"], "sporocil_seznamov": s["sporocil_seznamov"],
                "konvergenca_s": round(konec - t0, 3) if konec else None, "cpu_s": round(s["cpu_s"] - cpu0, 3),
                "prejeto_seznamov": sum(o.bajtov_seznamov for o in odjemalci),
                "izpadlih": len(izpadli), "odklopov_ne_bere": ne_bere, "zahtev_posnetka": sum(o.zahtev for o in odjemalci),
                "neujemanj": sum(1 for o in odjemalci if o.cas_celega is None)}
    finally:
        try:
            proces.stdin.write("konec\n")
            proces.stdin.flush()
            proces.wait(timeout=20)
        except Exception:  # noqa: BLE001
            proces.kill()
            proces.wait(timeout=10)
        dnevnik.close()
        shutil.rmtree(mapa, ignore_errors=True)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "_sredisce":
        sredisce(sys.argv[2], float(sys.argv[3]))
        return 0
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("nacin", choices=("obdelaj", "zanka"))
    ap.add_argument("naprav", type=int, nargs="+")
    ap.add_argument("--okno", type=float, default=(link_spremembe.OKNO_S if link_spremembe else 0.0))
    ap.add_argument("--razpon", type=float, default=0.0, help="obdelaj: prijave enakomerno v toliko sekundah")
    ap.add_argument("--stari", type=float, default=0.0, help="delez odjemalcev brez zmoznosti (mesan krog)")
    ap.add_argument("--rok", type=float, default=180.0, help="zanka: najdlje toliko sekund do konvergence")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    for n in a.naprav:
        if a.nacin == "obdelaj":
            r = nacin_obdelaj(n, a.okno, a.razpon, a.stari)
        else:
            r = nacin_zanka(n, a.okno, a.stari, a.rok)
        if a.json:
            print(json.dumps(r), flush=True)
        else:
            print("%4d naprav (novih %3d, okno %s): seznami %s, vse %s, konvergenca %s s, CPU sredisca %.2f s, "
                  "neujemanj %d%s" % (n, r["novih"], r["okno_s"], _berljivo(r.get("prejeto_seznamov", r["bajtov_seznamov"])),
                                      _berljivo(r["bajtov_vseh"]), r["konvergenca_s"], r["cpu_s"], r["neujemanj"],
                                      (", izpadlih %d, zahtev posnetka %d, sporocil seznamov %d" % (
                                          r["izpadlih"], r["zahtev_posnetka"], r["sporocil_seznamov"]))
                                      if "izpadlih" in r else ""), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
