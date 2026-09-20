"""Safeer Hub na racunalniku: da televizor ni vec pogoj, da se naprave vidijo.

Doslej je bil racunalnik v Safeer Linku samo odjemalec - `cast.register` je znal poslati, nikoli
obravnavati. Zato je ugasnjen televizor pomenil, da telefon in tablica izgubita racunalnik, ceprav
je ta ves cas prizgan. Tu je druga stran: isti protokol, kot ga govori HubUsmerjevalnik na
televizorju, da odjemalcev ni treba spreminjati.

Kaj ta Hub zna in cesa namenoma ne:

  * **zna** prijavo naprav iz kroga zaupanja (podpis kljuca, brez kode), seznam naprav,
    posredovanje sporocil (cast., share., control., sync.) in stanje;
  * **ne zna** seznanitve nove naprave s kodo (SPAKE2). Nova naprava se se vedno seznani na
    televizorju; ko je enkrat v krogu, jo sprejme tudi racunalnik. Tako ta korak ne odpira nove
    poti do hise, dokler ni preizkusena.

Zaupanje: Hub ima isto potrdilo TLS kot Controlov streznik datotek, torej **isti kljuc**, ki je
v krogu zaupanja. Naprava zato ta Hub prepozna po kljucu v potrdilu in se prijavi s podpisom,
brez nove kode - tocno tako, kot bi se na drugem televizorju.

Meje so v zasnovi, ne v zaupanju v naprave: najvec naprav, najvecje sporocilo, izhodna vrsta na
povezavo in izmet naprave, ki ne bere (glej core/link_ws.py).
"""

from __future__ import annotations

import http.server
import json
import ssl
import threading
import time
from typing import Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from core import link_krog, link_ws

#: Vrata Huba. Najprej privzeta (naprave jih poznajo tudi brez mDNS), sicer katerakoli prosta.
PRIVZETA_VRATA = 8990
POT_WS = "/cast/ws"

NAJVEC_NAPRAV = 32
NAJVEC_IMENA = 64
#: Izziv za podpis velja kratko in samo enkrat.
IZZIV_VELJA_S = 60.0
NAJVEC_IZZIVOV = 64
#: Vstopnica je enkratna in kratkoziva: iz nje nastane ena povezava WebSocket.
VSTOPNICA_VELJA_S = 60.0
NAJVEC_VSTOPNIC = 64
#: Protokol, ki ga govorimo (isto kot HubUsmerjevalnik).
RAZLICICA_PROTOKOLA = "1"
IDENTITETA_HUBA = "safeer-link-hub"


def _zdaj() -> float:
    return time.time()


def _json(telo: dict) -> bytes:
    return json.dumps(telo, ensure_ascii=False).encode("utf-8")


class Naprava:
    """Ena povezana naprava, kakor jo vidi Hub."""

    def __init__(self, id_naprave: str, ime: str, vloga: str, zmoznosti: List[str], naslov: str) -> None:
        self.id = id_naprave
        self.ime = ime
        self.vloga = vloga
        self.zmoznosti = zmoznosti
        self.naslov = naslov
        self.zadnjic = _zdaj()
        self.povezava: Optional[link_ws.Povezava] = None
        # Protocol v1
        self.protokol = ""
        self.platforma = ""
        self.vrsta = ""
        self.razlicica = ""
        self.prioriteta = 0
        self.aplikacije: dict = {}

    def json(self) -> dict:
        zapis = {
            "id": self.id,
            "name": self.ime,
            "role": self.vloga,
            "capabilities": list(self.zmoznosti),
            "ip": self.naslov,
            "port": None,
            "last_seen": self.zadnjic,
        }
        if self.protokol:
            zapis["protocol"] = self.protokol
        if self.platforma:
            zapis["platform"] = self.platforma
        if self.vrsta:
            zapis["kind"] = self.vrsta
        if self.razlicica:
            zapis["version"] = self.razlicica
        if self.prioriteta:
            zapis["priority"] = self.prioriteta
        if self.aplikacije:
            zapis["apps"] = self.aplikacije
        return zapis


class Hub:
    """Register naprav in usmerjanje sporocil. Brez omrezja - to je HubStreznik.

    Loceno zato, ker je prav tu vsa logika, ki mora biti pravilna: kdo sme noter, kam gre
    sporocilo in kaj dobi posiljatelj nazaj. Tako je preizkusljiva brez vticnikov in TLS.
    """

    def __init__(self, odtis: str = "", nas_id: str = "", ura: Callable[[], float] = _zdaj) -> None:
        self.odtis = (odtis or "").lower()
        self.nas_id = nas_id
        self.ura = ura
        self._zaklep = threading.RLock()
        self._naprave: Dict[str, Naprava] = {}
        self._izzivi: Dict[str, tuple] = {}        # nonce -> (device_id, cas)
        self._vstopnice: Dict[str, tuple] = {}     # vstopnica -> (device_id, cas)
        self.ob_spremembi: Optional[Callable[[], None]] = None

    # ------------------------------------------------------------------ prijava s podpisom

    def izziv(self, device_id: str) -> Optional[dict]:
        """Enkratni izziv za napravo, ki se hoce prijaviti s podpisom kljuca."""
        device_id = (device_id or "").strip()[:NAJVEC_IMENA]
        if not device_id:
            return None
        nonce = link_ws.nakljucni(18)
        with self._zaklep:
            self._pocisti_izzive()
            if len(self._izzivi) >= NAJVEC_IZZIVOV:
                return None
            self._izzivi[nonce] = (device_id, self.ura())
        return {"nonce": nonce, "fp": self.odtis, "hub_id": IDENTITETA_HUBA}

    def _pocisti_izzive(self) -> None:
        meja = self.ura() - IZZIV_VELJA_S
        for n in [n for n, (_, ko) in self._izzivi.items() if ko < meja]:
            self._izzivi.pop(n, None)

    def vstopnica_s_podpisom(self, device_id: str, nonce: str, podpis: str,
                             ime: str = "", platforma: str = "") -> Optional[dict]:
        """Preveri podpis proti kljucu iz kroga zaupanja in izda enkratno vstopnico.

        Izziv je enkraten: porabimo ga, ne glede na izid. Sicer bi lahko kdo na istem izzivu
        poskusal podpise, dokler eden ne bi ustrezal.
        """
        device_id = (device_id or "").strip()[:NAJVEC_IMENA]
        with self._zaklep:
            self._pocisti_izzive()
            vnos = self._izzivi.pop((nonce or "").strip(), None)
        if not vnos or not device_id or vnos[0] != device_id:
            return None
        clan = None
        try:
            clan = link_krog.krog().clan_za_id(device_id)
        except Exception:
            clan = None
        if not clan or not clan.get("kljuc"):
            return None
        podatki = link_krog.podatki_za_podpis(self.odtis, nonce, device_id)
        if not link_krog.preveri_podpis(str(clan["kljuc"]), podatki, podpis or ""):
            return None
        vstopnica = link_ws.nakljucni(24)
        with self._zaklep:
            self._pocisti_vstopnice()
            if len(self._vstopnice) >= NAJVEC_VSTOPNIC:
                najstarejsa = min(self._vstopnice, key=lambda k: self._vstopnice[k][1])
                self._vstopnice.pop(najstarejsa, None)
            self._vstopnice[vstopnica] = (device_id, self.ura())
        odgovor = {"ticket": vstopnica, "hub_id": IDENTITETA_HUBA, "fp": self.odtis}
        try:
            odgovor["ring"] = link_krog.krog().json()
        except Exception:
            pass
        return odgovor

    def _pocisti_vstopnice(self) -> None:
        meja = self.ura() - VSTOPNICA_VELJA_S
        for v in [v for v, (_, ko) in self._vstopnice.items() if ko < meja]:
            self._vstopnice.pop(v, None)

    def porabi_vstopnico(self, vstopnica: str) -> Optional[str]:
        """Id naprave, ki ji vstopnica pripada. Velja natanko enkrat."""
        with self._zaklep:
            self._pocisti_vstopnice()
            vnos = self._vstopnice.pop((vstopnica or "").strip(), None)
        return vnos[0] if vnos else None

    # ------------------------------------------------------------------ register

    def povezane(self) -> List[Naprava]:
        with self._zaklep:
            return [n for n in self._naprave.values() if n.povezava is not None]

    def stevilo(self) -> int:
        return len(self.povezane())

    def najdi(self, device_id: str) -> Optional[Naprava]:
        with self._zaklep:
            return self._naprave.get(device_id)

    def id_povezave(self, povezava) -> Optional[str]:
        with self._zaklep:
            for i, n in self._naprave.items():
                if n.povezava is povezava:
                    return i
        return None

    def seznam_json(self) -> str:
        return json.dumps({"type": "cast.devices",
                           "devices": [n.json() for n in self.povezane()]}, ensure_ascii=False)

    def objavi_naprave(self) -> None:
        sporocilo = self.seznam_json()
        for n in self.povezane():
            p = n.povezava
            if p is not None:
                p.poslji(sporocilo)
        if self.ob_spremembi is not None:
            try:
                self.ob_spremembi()
            except Exception:
                pass

    def registriraj(self, povezava, tovor: dict, dovoljeni_id: str) -> tuple:
        """(status, koda_napake). Vstopnica je vezana na en id: druge naprave z njo ni mogoce vpisati."""
        device_id = str(tovor.get("device_id") or "").strip()[:NAJVEC_IMENA]
        if not device_id:
            return "rejected", "manjka_device_id"
        if dovoljeni_id and device_id != dovoljeni_id:
            return "rejected", "vstopnica_ni_za_to_napravo"
        ime = str(tovor.get("name") or device_id).strip()[:NAJVEC_IMENA]
        vloga = str(tovor.get("role") or "receiver")[:16]
        zmoznosti = [str(z)[:24] for z in (tovor.get("capabilities") or [])][:24]
        stara = None
        with self._zaklep:
            obstojeca = self._naprave.get(device_id)
            if obstojeca is not None and obstojeca.povezava is not None and obstojeca.povezava is not povezava:
                # Nova povezava iste naprave zamenja staro; sicer naprava ostane "povezana", a nevidna.
                stara = obstojeca.povezava
                obstojeca.povezava = None
            if obstojeca is None:
                if len([n for n in self._naprave.values() if n.povezava is not None]) >= NAJVEC_NAPRAV:
                    return "rejected", "prevec_naprav"
                obstojeca = Naprava(device_id, ime, vloga, zmoznosti, getattr(povezava, "naslov", ""))
                self._naprave[device_id] = obstojeca
            obstojeca.ime = ime
            obstojeca.vloga = vloga
            obstojeca.zmoznosti = zmoznosti
            obstojeca.naslov = getattr(povezava, "naslov", "")
            obstojeca.zadnjic = self.ura()
            obstojeca.povezava = povezava
            obstojeca.protokol = str(tovor.get("protocol") or "")[:8]
            obstojeca.platforma = str(tovor.get("platform") or "")[:16]
            obstojeca.vrsta = str(tovor.get("kind") or "")[:16]
            obstojeca.razlicica = str(tovor.get("version") or "")[:32]
            try:
                obstojeca.prioriteta = max(0, min(1000, int(tovor.get("priority") or 0)))
            except Exception:
                obstojeca.prioriteta = 0
            if isinstance(tovor.get("apps"), dict):
                obstojeca.aplikacije = tovor["apps"]
        if stara is not None:
            # Zunaj kljucavnice: zapiranje je omrezje in ne sme zadrzati registra.
            try:
                stara.zapri(1000, "nova povezava iste naprave")
            except Exception:
                pass
        return "accepted", ""

    def odklopi(self, povezava) -> None:
        spremenjeno = False
        with self._zaklep:
            for n in self._naprave.values():
                if n.povezava is povezava:
                    n.povezava = None
                    spremenjeno = True
        if spremenjeno:
            self.objavi_naprave()

    # ------------------------------------------------------------------ sporocila

    @staticmethod
    def prostor(tip: str) -> str:
        if not tip or "." not in tip:
            return "cast"
        return tip.split(".", 1)[0]

    def _potrditev(self, id_sporocila: str, prostor: str, status: str, napaka: str = "", koda: str = "") -> str:
        zapis = {"id": str(int(self.ura() * 1000)), "type": prostor + ".ack",
                 "ref_id": id_sporocila, "status": status}
        if napaka:
            zapis["error"] = napaka
        if koda:
            zapis["error_code"] = koda
        return json.dumps(zapis, ensure_ascii=False)

    def obdelaj(self, povezava, surovo: str) -> Optional[str]:
        """Eno sporocilo naprave. Vrne odgovor (potrditev) ali None."""
        try:
            sporocilo = json.loads(surovo)
        except Exception:
            return self._potrditev("", "cast", "rejected", "Sporočila ni mogoče prebrati.", "pokvarjeno")
        if not isinstance(sporocilo, dict):
            return self._potrditev("", "cast", "rejected", "Sporočila ni mogoče prebrati.", "pokvarjeno")
        tip = str(sporocilo.get("type") or "")
        id_sporocila = str(sporocilo.get("id") or "")
        prostor = self.prostor(tip)

        if tip == "cast.register":
            tovor = sporocilo.get("payload")
            tovor = tovor if isinstance(tovor, dict) else {}
            status, koda = self.registriraj(povezava, tovor, getattr(povezava, "podatki", {}).get("id", ""))
            if status == "accepted":
                self.objavi_naprave()
                p = povezava
                try:
                    p.poslji(json.dumps({"type": "trust.update", "payload": link_krog.krog().json()},
                                        ensure_ascii=False))
                except Exception:
                    pass
            return self._potrditev(id_sporocila, "cast", status, "" if status == "accepted" else "Prijava zavrnjena.", koda)

        if tip == "cast.ping":
            return json.dumps({"id": id_sporocila, "type": "cast.pong"}, ensure_ascii=False)

        moj_id = self.id_povezave(povezava)
        if moj_id is None:
            # Vticnica brez prijave (npr. po zamenjavi povezave): odjemalec to prepozna in se vrne.
            return self._potrditev(id_sporocila, prostor, "rejected", "Naprava ni povezana.", "naprava_ni_povezana")

        cilj = str(sporocilo.get("target") or "")
        if cilj and cilj != "all":
            if cilj == moj_id:
                return self._potrditev(id_sporocila, prostor, "rejected", "Ista naprava.", "isti_naprava")
            naprava = self.najdi(cilj)
            if naprava is None or naprava.povezava is None:
                return self._potrditev(id_sporocila, prostor, "rejected", "Naprave ni na Safeer Linku.", "ni_naprave")
            sporocilo["sender"] = moj_id
            naprava.povezava.poslji(json.dumps(sporocilo, ensure_ascii=False))
            self._osvezi(moj_id)
            if tip.endswith(".result") or tip.endswith(".ack"):
                return None          # odgovorov in potrditev Hub ne potrjuje
            return self._potrditev(id_sporocila, prostor, "accepted")

        if tip == "apps.announce":
            tovor = sporocilo.get("payload")
            if isinstance(tovor, dict) and isinstance(tovor.get("apps"), dict):
                with self._zaklep:
                    naprava = self._naprave.get(moj_id)
                    if naprava is not None:
                        naprava.aplikacije = tovor["apps"]
                self.objavi_naprave()
            return self._potrditev(id_sporocila, "apps", "accepted")

        # Brez cilja (ali target=all): vsem drugim.
        sporocilo["sender"] = moj_id
        besedilo = json.dumps(sporocilo, ensure_ascii=False)
        for n in self.povezane():
            if n.id != moj_id and n.povezava is not None:
                n.povezava.poslji(besedilo)
        self._osvezi(moj_id)
        if tip.endswith(".result") or tip.endswith(".ack"):
            return None
        return self._potrditev(id_sporocila, prostor, "accepted")

    def _osvezi(self, device_id: str) -> None:
        with self._zaklep:
            naprava = self._naprave.get(device_id)
            if naprava is not None:
                naprava.zadnjic = self.ura()

    # ------------------------------------------------------------------ stanje

    def zdravje(self) -> dict:
        povezane = self.povezane()
        return {"status": "ok", "protocol": RAZLICICA_PROTOKOLA,
                "receivers": len([n for n in povezane if n.vloga == "receiver"]),
                "senders": len([n for n in povezane if n.vloga != "receiver"]),
                "sync_peers": len([n for n in povezane if "sync" in n.zmoznosti]),
                "sync_categories": []}


# ---------------------------------------------------------------------- omrezje

class _Obravnava(http.server.BaseHTTPRequestHandler):
    """Koncne tocke Huba. Namenoma jih je malo - vse drugo tece po WebSocketu."""

    protocol_version = "HTTP/1.1"
    server_version = "SafeerHub"
    sys_version = ""

    # Dnevnik vticnika bi ob vsaki zahtevi pisal v terminal; Safeer pise sam, kadar je kaj vredno.
    def log_message(self, *_a) -> None:
        pass

    # ------------------------------------------------------------------ pomozno
    @property
    def _hub(self) -> "Hub":
        return self.server.hub          # type: ignore[attr-defined]

    def _je_krajevni(self) -> bool:
        naslov = self.client_address[0] if self.client_address else ""
        return _je_krajevni_naslov(naslov)

    def _odgovori(self, koda: int, telo: dict) -> None:
        podatki = _json(telo)
        self.send_response(koda)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(podatki)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(podatki)
        except Exception:
            pass

    def _napaka(self, koda: int, sporocilo: str, oznaka: str) -> None:
        self._odgovori(koda, {"error": sporocilo, "error_code": oznaka})

    def _telo(self) -> dict:
        try:
            dolzina = int(self.headers.get("Content-Length") or 0)
        except Exception:
            return {}
        if dolzina <= 0 or dolzina > 64 * 1024:
            return {}
        try:
            return json.loads(self.rfile.read(dolzina).decode("utf-8")) or {}
        except Exception:
            return {}

    # ------------------------------------------------------------------ GET
    def do_GET(self) -> None:
        pot = urlparse(self.path).path
        if not self._je_krajevni():
            self._napaka(403, "Safeer Link deluje samo v krajevnem omrežju.", "samo_krajevno")
            return
        if pot == POT_WS:
            self._nadgradi()
            return
        if pot == "/cast/health":
            # Samo stevila, nikoli imena naprav: to je preverba, da tu res tece Safeer Hub.
            self._odgovori(200, self._hub.zdravje())
            return
        if pot == "/cast/trust/ring":
            try:
                self._odgovori(200, link_krog.krog().json())
            except Exception:
                self._napaka(500, "Kroga ni mogoče prebrati.", "krog_ni_berljiv")
            return
        if pot == "/cast/devices":
            # Seznam naprav gre po WebSocketu (cast.devices) napravam, ki so se prijavile.
            # Po HTTP ga ta Hub ne daje: zetonov za HTTP (se) ne izdaja.
            self._napaka(401, "Naprava ni seznanjena.", "naprava_ni_seznanjena")
            return
        if pot in ("/cast/ticket", "/cast/pair/start", "/cast/pair/spake", "/cast/pair/finish"):
            # Pot obstaja, a ne kot GET. Po tem naprava loci Safeer Hub od poljubnega streznika.
            self._napaka(405, "Ta način za to pot ni dovoljen.", "metoda_ni_dovoljena")
            return
        self._napaka(404, "Ni te poti.", "ni_poti")

    # ------------------------------------------------------------------ POST
    def do_POST(self) -> None:
        pot = urlparse(self.path).path
        if not self._je_krajevni():
            self._napaka(403, "Safeer Link deluje samo v krajevnem omrežju.", "samo_krajevno")
            return
        if pot == "/cast/auth/challenge":
            telo = self._telo()
            izziv = self._hub.izziv(str(telo.get("device_id") or ""))
            if izziv is None:
                self._napaka(429, "Preveč prijav; poskusite čez nekaj minut.", "prevec_prijav")
                return
            self._odgovori(200, izziv)
            return
        if pot == "/cast/auth/ticket":
            telo = self._telo()
            odgovor = self._hub.vstopnica_s_podpisom(
                str(telo.get("device_id") or ""), str(telo.get("nonce") or ""),
                str(telo.get("signature") or ""), str(telo.get("name") or ""),
                str(telo.get("platform") or ""))
            if odgovor is None:
                # 401 pomeni: te naprave (s tem kljucem) v krogu nimamo. Odjemalec to razume.
                self._napaka(401, "Naprave ni v krogu zaupanja.", "ni_v_krogu")
                return
            self._odgovori(200, odgovor)
            return
        if pot == "/cast/ticket":
            # Seznanitev z zetonom in kodo tece na televizorju; racunalnik sprejema samo krog.
            self._napaka(401, "Ta Hub sprejema samo naprave iz kroga zaupanja.", "samo_krog")
            return
        self._napaka(404, "Ni te poti.", "ni_poti")

    # ------------------------------------------------------------------ WebSocket
    def _nadgradi(self) -> None:
        glave = {k: v for k, v in self.headers.items()}
        if not link_ws.je_nadgradnja(glave):
            self._napaka(400, "Manjka nadgradnja na WebSocket.", "ni_nadgradnje")
            return
        vstopnica = (parse_qs(urlparse(self.path).query).get("ticket") or [""])[0]
        device_id = self._hub.porabi_vstopnico(vstopnica)
        if not device_id:
            self._napaka(401, "Neveljavna ali potekla vstopnica.", "ni_vstopnice")
            return
        try:
            self.wfile.write(link_ws.odgovor_rokovanja(link_ws.kljuc_iz_glav(glave)))
            self.wfile.flush()
        except Exception:
            return
        self.close_connection = True
        vticnik = self.connection
        try:
            vticnik.settimeout(link_ws.PING_VSAKIH_S)
        except Exception:
            pass
        hub = self._hub
        povezava = link_ws.Povezava(
            vticnik, self.client_address[0] if self.client_address else "",
            ob_sporocilu=lambda p, s: _na_sporocilo(hub, p, s),
            ob_koncu=hub.odklopi)
        # Vstopnica je vezana na en id: prijava z drugim id-jem se zavrne (glej registriraj).
        povezava.podatki["id"] = device_id
        povezava.zanka_branja()


def _na_sporocilo(hub: "Hub", povezava, surovo: str) -> None:
    odgovor = hub.obdelaj(povezava, surovo)
    if odgovor:
        povezava.poslji(odgovor)


def _je_krajevni_naslov(naslov: str) -> bool:
    """Ali je naslov iz domacega omrezja? Hub se ne pogovarja z internetom."""
    if not naslov:
        return False
    if naslov.startswith("::ffff:"):
        naslov = naslov[7:]
    if naslov in ("127.0.0.1", "::1", "localhost"):
        return True
    deli = naslov.split(".")
    if len(deli) == 4 and all(d.isdigit() for d in deli):
        a, b = int(deli[0]), int(deli[1])
        if a == 10:
            return True
        if a == 192 and b == 168:
            return True
        if a == 172 and 16 <= b <= 31:
            return True
        if a == 169 and b == 254:
            return True
        return False
    # IPv6 krajevno omrezje: fe80::/10 (link-local) in fc00::/7 (unique local).
    nizko = naslov.lower()
    return nizko.startswith("fe8") or nizko.startswith("fe9") or nizko.startswith("fea") \
        or nizko.startswith("feb") or nizko.startswith("fc") or nizko.startswith("fd")


class _Streznik(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address) -> None:
        """Naprava, ki prekine povezavo, ni napaka Huba in ne sodi v uporabnikov terminal.

        Privzeto bi socketserver ob vsakem prekinjenem rokovanju TLS izpisal celo sled - ob
        ugasnjeni tablici ali zaprtem pokrovu bi bil dnevnik poln sledi, ki ne pomenijo nicesar.
        """
        return


class HubStreznik:
    """Hub racunalnika na omrezju: TLS, HTTP koncne tocke in WebSocket.

    Potrdilo je isto kot pri Controlovem strezniku datotek, torej isti kljuc, ki je v krogu
    zaupanja - naprava ta Hub prepozna po kljucu v potrdilu in se prijavi s podpisom, brez kode.
    """

    def __init__(self, tls_mapa: Optional[str] = None) -> None:
        self.tls_mapa = tls_mapa
        self.odtis = ""
        self.vrata = 0
        self.hub: Optional[Hub] = None
        self._streznik: Optional[_Streznik] = None
        self._nit: Optional[threading.Thread] = None
        self._zaklep = threading.Lock()

    def tece(self) -> bool:
        return self._streznik is not None

    def zazeni(self) -> bool:
        with self._zaklep:
            if self._streznik is not None:
                return True
            from core import link_datoteke
            if self.tls_mapa:
                kljuc, potrdilo, self.odtis = link_datoteke.zagotovi_potrdilo(self.tls_mapa)
            else:
                kljuc, potrdilo, self.odtis = link_datoteke.zagotovi_potrdilo()
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(potrdilo, kljuc)
            nas_id = ""
            try:
                nas_id = link_krog.id_iz_kljuca(link_krog.javni_kljuc_b64())
            except Exception:
                pass
            self.hub = Hub(odtis=self.odtis, nas_id=nas_id)
            streznik = None
            # Privzeta vrata naprave poznajo tudi brez mDNS; ce so zasedena, vzamemo katerakoli.
            for vrata in (PRIVZETA_VRATA, 0):
                try:
                    streznik = _Streznik(("0.0.0.0", vrata), _Obravnava)
                    break
                except OSError:
                    streznik = None
            if streznik is None:
                return False
            streznik.socket = ctx.wrap_socket(streznik.socket, server_side=True)
            streznik.hub = self.hub          # type: ignore[attr-defined]
            self.vrata = streznik.server_address[1]
            self._streznik = streznik
            self._nit = threading.Thread(target=streznik.serve_forever, name="safeer-hub", daemon=True)
            self._nit.start()
            return True

    def ustavi(self) -> None:
        with self._zaklep:
            streznik = self._streznik
            self._streznik = None
        if streznik is not None:
            for n in (self.hub.povezane() if self.hub else []):
                if n.povezava is not None:
                    try:
                        n.povezava.zapri(1001, "hub se ustavlja")
                    except Exception:
                        pass
            try:
                streznik.shutdown()
                streznik.server_close()
            except Exception:
                pass
        self.vrata = 0
        self.hub = None


# ---------------------------------------------------------------------- oglas in prevzem

#: Ime storitve mDNS, po kateri naprave iscejo Safeer Hub (isto kot na Androidu).
STORITEV_MDNS = "_safeercast._tcp.local."
#: Prioriteta racunalnika pri izvolitvi huba (IzvolitevHuba.PRIORITETA_LINUX).
PRIORITETA_LINUX = 80


class Oglas:
    """Oglas Huba prek mDNS. Brez zeroconfa mirno ne naredi nicesar - paket ostane brez nove
    obvezne odvisnosti, naprave pa Hub najdejo tudi po privzetem imenu in vratih."""

    def __init__(self) -> None:
        self._zc = None
        self._info = None

    def zacni(self, vrata: int, odtis: str, id_naprave: str, ime: str) -> bool:
        if self._info is not None:
            return True
        try:
            import socket as _s
            from zeroconf import ServiceInfo, Zeroconf   # type: ignore
        except Exception:
            return False
        try:
            lastnosti = {
                b"ws": POT_WS.encode(),
                b"tls": b"1",
                b"fp": (odtis or "").encode(),
                b"name": (ime or "").encode("utf-8")[:63],
                b"id": (id_naprave or "").encode(),
                b"prio": str(PRIORITETA_LINUX).encode(),
            }
            naslov = _s.inet_aton(_krajevni_ip())
            ime_storitve = ("safeer-%s.%s" % ((id_naprave or "pc")[-8:], STORITEV_MDNS))
            info = ServiceInfo(STORITEV_MDNS, ime_storitve, addresses=[naslov], port=vrata,
                               properties=lastnosti, server=_s.gethostname().rstrip(".") + ".local.")
            zc = Zeroconf()
            zc.register_service(info)
            self._zc, self._info = zc, info
            return True
        except Exception:
            self._zc, self._info = None, None
            return False

    def koncaj(self) -> None:
        zc, info = self._zc, self._info
        self._zc, self._info = None, None
        if zc is None:
            return
        try:
            if info is not None:
                zc.unregister_service(info)
        except Exception:
            pass
        try:
            zc.close()
        except Exception:
            pass


def _krajevni_ip() -> str:
    """Nas naslov v domacem omrezju (brez posiljanja cesarkoli)."""
    import socket as _s
    v = _s.socket(_s.AF_INET, _s.SOCK_DGRAM)
    try:
        v.connect(("192.168.0.1", 9))     # samo izbira poti, paket ne gre nikamor
        return v.getsockname()[0]
    except Exception:
        try:
            return _s.gethostbyname(_s.gethostname())
        except Exception:
            return "127.0.0.1"
    finally:
        try:
            v.close()
        except Exception:
            pass


def naj_gostimo(najden_hub: Optional[dict], nas_id: str = "", nas_odtis: str = "") -> bool:
    """Ali naj racunalnik zdaj sam gosti Hub?

    Pravilo je namenoma zadrzano: gostimo **samo, kadar drugega Huba ni**. Televizor, ki tece,
    ostane sredisce kot doslej - nocemo, da bi posodobitev cez noc premaknila sredisce hise.
    Ko televizor ugasne, racunalnik prevzame in telefon ter tablica ga najdeta; ko se televizor
    vrne, se naprave vrnejo k njemu, nas Hub pa se umakne (glej HubGostitelj.preveri).

    Nas lastni Hub seveda ni razlog za umik. Prepoznamo ga po dvojem, ker oglas ne pove vedno
    obojega: po id-ju iz oglasa in po odtisu potrdila. Brez tega bi se racunalnik ugasnil takoj,
    ko bi nasel samega sebe.
    """
    if najden_hub is None:
        return True
    if nas_id and str(najden_hub.get("id") or "") == nas_id:
        return True
    if nas_odtis and str(najden_hub.get("fp") or "").lower() == nas_odtis.lower():
        return True
    return False



def id_za_oglas() -> str:
    """Id, s katerim se Hub racunalnika oglasi prek mDNS.

    Mora biti id, pod katerim je nas kljuc **res v krogu zaupanja**: naprava oglasu ne verjame,
    ampak poisce tega clana v krogu in primerja njegov kljuc s kljucem v nasem potrdilu TLS. Ce bi
    oglasili id, ki ga v krogu ni (npr. svez id iz kljuca, ko je naprava vpisana pod imenom
    `...-control`), nam nihce ne bi zaupal in racunalnik bi gostil Hub, ki bi ostal prazen.
    """
    try:
        znan = link_krog.znan_id_za_nas_kljuc()
        if znan:
            return znan
    except Exception:
        pass
    try:
        return link_krog.id_iz_kljuca(link_krog.javni_kljuc_b64())
    except Exception:
        return ""

class HubGostitelj:
    """Zdruzi Hub, oglas in pravilo »gosti samo, kadar drugega ni«.

    `poisci()` naj vrne isto kot link_hub.poisci_hub_z_odtisom (ali None). Loceno zato, da je
    pravilo preizkusljivo brez omrezja.
    """

    def __init__(self, poisci: Callable[[], Optional[dict]], ime: str = "Safeer Control",
                 streznik: Optional["HubStreznik"] = None, oglas: Optional["Oglas"] = None) -> None:
        self.poisci = poisci
        self.ime = ime
        self.streznik = streznik or HubStreznik()
        self.oglas = oglas or Oglas()
        self.nas_id = ""
        self._zaklep = threading.Lock()

    def gostimo(self) -> bool:
        return self.streznik.tece()

    def preveri(self) -> bool:
        """En pregled: ce Huba ni, ga zazenemo; ce se je vrnil boljsi, se umaknemo."""
        try:
            najden = self.poisci()
        except Exception:
            najden = None
        with self._zaklep:
            if naj_gostimo(najden, self.nas_id, self.streznik.odtis if self.streznik.tece() else ""):
                if self.streznik.tece():
                    return True
                if not self.streznik.zazeni():
                    return False
                self.nas_id = id_za_oglas()
                self.oglas.zacni(self.streznik.vrata, self.streznik.odtis, self.nas_id, self.ime)
                print("[SafeerLink] računalnik gosti Safeer Link (vrata %d)" % self.streznik.vrata)
                return True
            if self.streznik.tece():
                # Drug Hub je spet tu: umaknemo se, da hisa nima dveh sredisc.
                print("[SafeerLink] drug Safeer Link je spet na voljo; računalnik neha gostiti")
                self.oglas.koncaj()
                self.streznik.ustavi()
            return False

    def koncaj(self) -> None:
        with self._zaklep:
            self.oglas.koncaj()
            self.streznik.ustavi()
