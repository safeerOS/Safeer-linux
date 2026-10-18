"""Global Link - neposredna pot od zunaj (INTERNET_DIRECT): naprava zdoma do domacega sredisca brez releja.

Zakaj: telefon na mobilnih podatkih je za simetricnim CGNAT-om, zato luknjanje UDP ne uspe (safeerOS/webrtc-raziskava,
POROCILO.md: 0/11). Ce pa ena stran sprejema dohodne povezave - doma je javni IPv4 in na usmerjevalniku ENA
preusmerjena vrata -, telefon odpre navadno odhodno povezavo TCP naravnost do doma. Rele (link.safeer.si) ostane
rezerva: kadar neposredne poti ni, gre vse kot doslej.

Vrstni red poti (odjemalec): LAN_DIRECT -> INTERNET_DIRECT -> SAFEER_RELAY.

Vhod na sredisci (VhodNeposredno) - vse, kar pride z interneta, gre skozi tri vrata, preden doseze sredisce:
  1. Trk (pred TLS): odjemalec najprej poslje kratek podpisan paket - id iz svojega kljuca, cas, nakljucni nonce in
     podpis ECDSA (kljuc naprave, isti kot v krogu zaupanja) nad id-jem SREDISCA, svojim id-jem, casom in noncem.
     Sredisce poisce kljuc clana kroga za ta id (neznan id: brez kriptografije ven), preveri cas (+-120 s), nonce
     (enkrat) in podpis. Kdor trka ne zna, ne dobi niti enega bajta odgovora - pregledovalnik vrat ne vidi ne TLS
     ne potrdila (to nosi ime racunalnika), ne Safeerja.
  2. TLS (1.3, najmanj 1.2) s potrdilom sredisca (kljuc naprave); odjemalec sprejme samo potrdilo s kljucem tega clana kroga.
  3. Izziv: sredisce poslje 32 nakljucnih bajtov, odjemalec podpise izziv + odtis potrdila, ki ga je videl, +
     namen. Podpis veze odjemalcev kljuc na TO sejo TLS (odtis) - posnet trk sam ne odpre nicesar.
Sele nato sredisce povezavo prevezi na krajevna vrata Huba (127.0.0.1), kot to dela agent releja. Skozi tece
nespremenjen TLS Safeer Linka s pripetim kljucem in prijava s podpisom/vstopnico; pravila dostopa (link_dostop:
"o vsebinah te naprave odloca samo ta naprava") veljajo enako kot doma in prek releja. Novih koncnih tock ni.

Napake se ne opisujejo: vsaka zavrnitev je tiho zaprta povezava. Viri, ki trkajo narobe, gredo v core/link_obramba
(lastna instanca, brez izjeme za zanko), hkratnih rokovanj in tunelov je omejeno stevilo.

Oglas: sredisce svoj javni IPv4 izve s STUN pri Cloudflaru (stun.cloudflare.com - isti ponudnik kot rele, brez
tretjih storitev), in ga objavi v svoji prisotnosti na link.safeer.si kot `candidate_hints` - samo clanom svojega
kroga (Worker: seznam `allow`). Oglas je podpisan s kljucem sredisca (odjemalec ga preveri s kljucem iz kroga, ne
zaupa releju) in ima rok. Dosegljivost se NE trdi brez prave preizkusnje: sredisce oglas oznaci kot preverjen
sele, ko je od zunaj (z javnega naslova) prisla prava overjena povezava - preizkus (namen 2), ki ga v ozadju sama
naredi seznanjena naprava, ko je zdoma in vidi nepreverjen oglas, ali pravi tunel. Nepreverjen oglas odjemalec
uporabi samo za preizkus v ozadju, nikoli na poti, na katero uporabnik caka.

Odjemalec (LokalniOdZunaj): ena krajevna vrata 127.0.0.1 do sredisca zunaj doma, enako kot doslej LokalniRele.
Vsaka povezava nanje gre najprej neposredno (rok povezave ROK_POVEZAVE_S), ob neuspehu takoj prek releja. Po
neuspehu neposredne poti jo do konca premora (ali do spremembe omrezja) preskocimo - uporabnik caka kvecjemu enkrat.
Zadnja delujoca pot za vsako sredisce se zapomni (global-link-poti.json).

Nastavitev "Neposredna povezava od zunaj" je privzeto IZKLOPLJENA (global-link-neposredno.json ob nastavitvah Linka).
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import re
import socket
import ssl
import struct
import threading
import time
import urllib.request
from collections import OrderedDict
from typing import Callable, Dict, List, Optional, Tuple

from core import link_pot
from core import os_deskriptorji

PROTOKOL = "safeer-neposredno-v1"
#: Privzeta zunanja (in notranja) vrata. Visoka in neobicajna: manj pregledovalnikov, ki tipajo znana vrata.
PRIVZETA_VRATA = 48990
#: Odjemalec: rok za TCP do javnega naslova. Uporabnik zaradi neposrednega poskusa caka kvecjemu toliko (in rokovanje).
ROK_POVEZAVE_S = 1.5
#: Odjemalec: rok za trk + TLS + izziv po vzpostavljeni povezavi TCP.
ROK_ROKOVANJA_S = 3.0
#: Sredisce: rok za trk, TLS in odgovor na izziv (pocasen mobilni odjemalec).
ROK_VHODA_S = 6.0
#: Cas v trku in prisotnosti: dovoljen odmik ur.
OKNO_CASA_S = 120
#: Oglas velja toliko (sredisce ga obnavlja ob vsaki objavi prisotnosti, vsako minuto).
TTL_OGLASA_S = 900
#: Oglas z rokom dlje v prihodnosti zavrnemo (pokvarjena ura ali ponaredek).
NAJDALJSI_TTL_S = 3600
#: Preverjena dosegljivost velja toliko; vsaka nova povezava od zunaj jo podaljsa.
PREVERJENO_VELJA_S = 7 * 86400
#: Javni IPv4 (STUN) osvezimo tako pogosto; ob spremembi naslova preverjanje velja znova od zacetka.
STUN_VSAKIH_S = 600
STUN_STREZNIKI = (("stun.cloudflare.com", 3478),)
#: Odjemalec: oglas iz prisotnosti osvezimo najvec tako pogosto (dnevna kvota Workerja).
PRISOTNOST_VSAKIH_S = 600
#: Ob prvi povezavi pocakamo na iskanje oglasa najvec toliko (sicer gre ta povezava prek releja).
CAKAJ_OGLAS_S = 1.0
#: Po neuspeli neposredni poti jo toliko casa preskocimo (podvaja se do NAJDALJSI_PREMOR_S); sprememba omrezja ga izbrise.
PREMOR_S = 300.0
NAJDALJSI_PREMOR_S = 1800.0
#: Meje vhoda.
NAJVEC_ROKOVANJ = 16
#: En naslov ne sme zasesti vseh mest za rokovanje (pocasen trk drzi mesto do ROK_VHODA_S): najvec toliko hkrati.
#: Prava naprava jih odpre najvec ~6 hkrati (OkHttp: 5 na gostitelja + WebSocket); 8 dopusti se dve napravi za istim
#: javnim naslovom brez cakanja. Zavrnjeno rokovanje odjemalca za PREMOR_S vrne na rele - zato meja ni nizja.
NAJVEC_ROKOVANJ_NA_VIR = 8
#: Toliko mest je samo za naslove, ki so se v zadnjih link_obramba.ZAUPANJE_S izkazali kot clani kroga: tudi veliko
#: tujih naslovov hkrati ne izrine naprave, ki se po kratkem izpadu vraca z istega naslova.
REZERVA_ZAUPANIM = 4
NAJVEC_TUNELOV = 64
NAJVEC_NONCEV = 4096
KOS = 64 * 1024

MAGIJA = b"SFN1"
NAMEN_TUNEL = 1
NAMEN_PREIZKUS = 2
POTRDITEV = b"\x01"
_ID = re.compile(r"^n-[0-9a-f]{16}$")
_DOLZINA_ID = 18

#: Oznake poti za vmesnik in meritve (link_pot): LAN_DIRECT, INTERNET_DIRECT, SAFEER_RELAY.
POT_LAN = "lan"
POT_NEPOSREDNO = "neposredno"
POT_RELE = "rele"


# ------------------------------------------------------------------ nastavitve

def _mapa() -> str:
    from core import link_krog
    return link_krog._mapa_nastavitev()


def _pot_nastavitev() -> str:
    return os.path.join(_mapa(), "global-link-neposredno.json")


def _pot_stanja() -> str:
    return os.path.join(_mapa(), "global-link-neposredno-stanje.json")


def _pot_poti() -> str:
    return os.path.join(_mapa(), "global-link-poti.json")


def _beri_json(pot: str) -> dict:
    try:
        with open(pot, encoding="utf-8") as d:
            v = json.load(d)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _pisi_json(pot: str, vsebina: dict) -> None:
    try:
        os.makedirs(os.path.dirname(pot), exist_ok=True)
        zacasna = pot + ".tmp"
        with open(zacasna, "w", encoding="utf-8") as d:
            json.dump(vsebina, d)
        os.chmod(zacasna, 0o600)
        os.replace(zacasna, pot)
    except Exception:
        pass


def nastavitve(pot: Optional[str] = None) -> dict:
    """{"vklopljeno": bool, "vrata": int}. Privzeto izklopljeno. SAFEER_NEPOSREDNO=0 izklopi ne glede na nastavitev."""
    s = _beri_json(pot or _pot_nastavitev())
    vrata = s.get("vrata", PRIVZETA_VRATA)
    try:
        vrata = int(vrata)
    except (TypeError, ValueError):
        vrata = PRIVZETA_VRATA
    if not 1024 <= vrata <= 65535:
        vrata = PRIVZETA_VRATA
    vklop = bool(s.get("vklopljeno", False)) and os.environ.get("SAFEER_NEPOSREDNO", "1").strip() != "0"
    return {"vklopljeno": vklop, "vrata": vrata}


def shrani_nastavitve(vklopljeno: bool, vrata: Optional[int] = None, pot: Optional[str] = None) -> dict:
    prej = nastavitve(pot)
    v = prej["vrata"] if vrata is None else int(vrata)
    if not 1024 <= v <= 65535:
        raise ValueError("vrata morajo biti med 1024 in 65535")
    _pisi_json(pot or _pot_nastavitev(), {"vklopljeno": bool(vklopljeno), "vrata": v})
    return nastavitve(pot)


# ------------------------------------------------------------------ pomozno

def jedro(device_id: str) -> str:
    """Id iz kljuca brez pripone (`n-<16 hex>`) ali ''."""
    d = str(device_id or "")[:_DOLZINA_ID]
    return d if _ID.match(d) else ""


def id_iz_kljuca(kljuc_b64: str) -> str:
    return "n-" + hashlib.sha256(base64.b64decode(kljuc_b64)).hexdigest()[:16]


def odtis_kljuca(kljuc_b64: str) -> str:
    return hashlib.sha256(base64.b64decode(kljuc_b64)).hexdigest()


def je_javni_ipv4(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(str(ip or ""))
    except ValueError:
        return False
    return a.version == 4 and a.is_global


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64u_d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _beri_tocno(s, n: int, rok: float) -> bytes:
    """Natanko n bajtov ali izjema (rok velja za vse branje skupaj)."""
    konec = time.monotonic() + rok
    out = b""
    while len(out) < n:
        ostane = konec - time.monotonic()
        if ostane <= 0:
            raise TimeoutError("rok")
        s.settimeout(ostane)
        kos = s.recv(n - len(out))
        if not kos:
            raise ConnectionError("konec")
        out += kos
    return out


def _zapri(s) -> None:
    if s is None:
        return
    try:
        s.close()
    except Exception:
        pass


# ------------------------------------------------------------------ podpisani podatki (isti na Androidu)

def podatki_trka(hub_id: str, odjemalec_id: str, cas: int, nonce: bytes) -> bytes:
    return ("safeer-neposredno-trk-v1\n%s\n%s\n%d\n%s" % (hub_id, odjemalec_id, cas, nonce.hex())).encode("ascii")


def podatki_izziva(hub_id: str, odjemalec_id: str, izziv: bytes, odtis_potrdila: str, namen: int) -> bytes:
    return ("safeer-neposredno-izziv-v1\n%s\n%s\n%s\n%s\n%d"
            % (hub_id, odjemalec_id, izziv.hex(), odtis_potrdila.lower(), namen)).encode("ascii")


def sestavi_trk(hub_id: str, odjemalec_id: str, podpisi: Callable[[bytes], bytes],
                cas: Optional[int] = None, nonce: Optional[bytes] = None) -> bytes:
    """MAGIJA(4) | id odjemalca (18, ascii) | cas (8, BE) | nonce (16) | dolzina podpisa (1) | podpis DER."""
    cas = int(time.time()) if cas is None else int(cas)
    nonce = os.urandom(16) if nonce is None else nonce
    podpis = podpisi(podatki_trka(hub_id, odjemalec_id, cas, nonce))
    if not 8 <= len(podpis) <= 80:
        raise ValueError("podpis ni ECDSA P-256")
    return MAGIJA + odjemalec_id.encode("ascii") + struct.pack(">Q", cas) + nonce + bytes([len(podpis)]) + podpis


# ------------------------------------------------------------------ oglas v prisotnosti

def podatki_oglasa(tovor_b64: str) -> bytes:
    return ("safeer-neposredno-oglas-v1\n" + tovor_b64).encode("ascii")


def sestavi_oglas(hub_id: str, ip: str, vrata: int, kljuc_b64: str, podpisi: Callable[[bytes], bytes],
                  preverjeno: float = 0.0, zdaj: Optional[float] = None, ttl: int = TTL_OGLASA_S) -> str:
    """Niz za `candidate_hints` (najvec 512 znakov): sdv1.<tovor>.<podpis> - podpisan s kljucem sredisca."""
    zdaj = time.time() if zdaj is None else zdaj
    tovor = {"v": 1, "hub": hub_id, "ip": ip, "port": int(vrata), "fp": odtis_kljuca(kljuc_b64),
             "exp": int(zdaj + ttl), "ok": int(preverjeno or 0)}
    t = _b64u(json.dumps(tovor, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return "sdv1.%s.%s" % (t, _b64u(podpisi(podatki_oglasa(t))))


def preveri_oglas(niz: str, hub_id: str, kljuc_b64: str, preveri: Callable[[bytes, bytes, bytes], bool],
                  zdaj: Optional[float] = None, je_javni: Optional[Callable[[str], bool]] = None) -> Optional[dict]:
    """Tovor oglasa ali None. Kljuc sredisca pride iz kroga zaupanja, NIKOLI iz oglasa ali releja."""
    zdaj = time.time() if zdaj is None else zdaj
    try:
        oznaka, t, p = str(niz).split(".")
        if oznaka != "sdv1" or len(niz) > 512:
            return None
        if not preveri(base64.b64decode(kljuc_b64), podatki_oglasa(t), _b64u_d(p)):
            return None
        tovor = json.loads(_b64u_d(t).decode("utf-8"))
        if not isinstance(tovor, dict) or tovor.get("v") != 1:
            return None
        if tovor.get("hub") != hub_id or tovor.get("fp") != odtis_kljuca(kljuc_b64):
            return None
        exp = int(tovor.get("exp", 0))
        if exp <= zdaj or exp - zdaj > NAJDALJSI_TTL_S:
            return None
        vrata = int(tovor.get("port", 0))
        if not (je_javni or je_javni_ipv4)(str(tovor.get("ip"))) or not 1024 <= vrata <= 65535:
            return None
        ok = int(tovor.get("ok", 0) or 0)
        return {"ip": str(tovor["ip"]), "vrata": vrata, "exp": exp,
                "preverjeno": bool(ok and zdaj - ok < PREVERJENO_VELJA_S)}
    except Exception:
        return None


# ------------------------------------------------------------------ STUN (javni IPv4 sredisca)

def _stun_zahteva() -> Tuple[bytes, bytes]:
    tid = os.urandom(12)
    return struct.pack(">HHI", 0x0001, 0, 0x2112A442) + tid, tid


def razberi_stun(odgovor: bytes, tid: bytes) -> Optional[Tuple[str, int]]:
    """XOR-MAPPED-ADDRESS (ali MAPPED-ADDRESS) iz odgovora STUN Binding (RFC 8489) za IPv4."""
    if len(odgovor) < 20:
        return None
    vrsta, dolzina, magija = struct.unpack(">HHI", odgovor[:8])
    if vrsta != 0x0101 or magija != 0x2112A442 or odgovor[8:20] != tid or len(odgovor) < 20 + dolzina:
        return None
    i, najden = 20, None
    while i + 4 <= 20 + dolzina:
        a_vrsta, a_dolz = struct.unpack(">HH", odgovor[i:i + 4])
        v = odgovor[i + 4:i + 4 + a_dolz]
        if a_vrsta in (0x0020, 0x0001) and len(v) >= 8 and v[1] == 0x01:
            vrata = struct.unpack(">H", v[2:4])[0]
            ip = bytes(v[4:8])
            if a_vrsta == 0x0020:
                vrata ^= 0x2112
                ip = bytes(b ^ m for b, m in zip(ip, struct.pack(">I", 0x2112A442)))
                return socket.inet_ntoa(ip), vrata
            najden = (socket.inet_ntoa(ip), vrata)
        i += 4 + a_dolz + (-a_dolz % 4)
    return najden


def javni_ipv4_stun(strezniki=STUN_STREZNIKI, rok_s: float = 1.5, poskusov: int = 2,
                    je_javni: Optional[Callable[[str], bool]] = None) -> str:
    """Javni IPv4, kot ga vidi Cloudflarov STUN; '' ob neuspehu."""
    for gostitelj, vrata in strezniki:
        for _ in range(poskusov):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.settimeout(rok_s)
                zahteva, tid = _stun_zahteva()
                s.sendto(zahteva, (gostitelj, vrata))
                odg, _ = s.recvfrom(2048)
                r = razberi_stun(odg, tid)
                if r and (je_javni or je_javni_ipv4)(r[0]):
                    return r[0]
            except (OSError, ValueError):
                pass
            finally:
                s.close()
    return ""


# ------------------------------------------------------------------ oznacitev krajevnih povezav (meritve, vmesnik)

def _oznaci(vrata: int, pot: str) -> None:
    link_pot.oznaci_zanko(vrata, pot)


def _odznaci(vrata: int) -> None:
    link_pot.odznaci_zanko(vrata)


# ------------------------------------------------------------------ prepoved (sredisce)

def _pipe(a, b, ob_koncu: Optional[Callable[[], None]] = None) -> None:
    """Bajti v obe smeri; ob koncu ene smeri zapre obe. `a`, `b`: vticnici (TLS ovita z link_vticnik.zavaruj)."""
    def ena(iz, v):
        try:
            while True:
                kos = iz.recv(KOS)
                if not kos:
                    break
                v.sendall(kos)
        except Exception:
            pass
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass

    nit = threading.Thread(target=ena, args=(b, a), name="safeer-neposredno-cev", daemon=True)
    nit.start()
    ena(a, b)
    nit.join(15)
    _zapri(a)
    _zapri(b)
    if ob_koncu is not None:
        try:
            ob_koncu()
        except Exception:
            pass


class VhodNeposredno:
    """Poslusa na preusmerjenih vratih; overjene clane kroga prevezi na krajevni Hub (127.0.0.1)."""

    def __init__(self, vrata: int, hub_vrata: Callable[[], int], hub_id: str,
                 pot_kljuca: str, pot_potrdila: str,
                 kljuc_clana: Callable[[str], Optional[str]],
                 preveri: Optional[Callable[[bytes, bytes, bytes], bool]] = None,
                 ob_zunanji: Optional[Callable[[str], None]] = None,
                 naslov: str = "0.0.0.0", ura: Callable[[], float] = time.time,
                 obramba=None) -> None:
        self.vrata_nastavljena = int(vrata)
        self.hub_vrata = hub_vrata
        self.hub_id = jedro(hub_id)
        if not self.hub_id:
            raise ValueError("id sredisca ni id iz kljuca")
        self.kljuc_clana = kljuc_clana
        if preveri is None:
            from core import link_kripto
            preveri = link_kripto.preveri
        self.preveri = preveri
        self.ob_zunanji = ob_zunanji
        self.ura = ura
        if obramba is None:
            from core import link_obramba
            # Vhod gleda na internet: tudi zanka (preizkus prek usmerjevalnika) nima izjeme.
            obramba = link_obramba.Obramba(izvzet=lambda _v: False)
        self.obramba = obramba
        self._ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        # TLS 1.2 je spodnja meja zaradi Androida 9 (minSdk 28: TLS 1.3 sele od Androida 10); izziv je enak.
        self._ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        self._ctx.load_cert_chain(pot_potrdila, pot_kljuca)
        with open(pot_potrdila, "rb") as d:
            der = ssl.PEM_cert_to_DER_cert(d.read().decode("ascii"))
        self.odtis = hashlib.sha256(der).hexdigest()
        self._nonci: "OrderedDict[bytes, float]" = OrderedDict()
        self._zaklep = threading.Lock()
        self._rokovanj = 0
        #: Tekoca rokovanja po naslovu (NAJVEC_ROKOVANJ_NA_VIR).
        self._rokovanj_vira: Dict[str, int] = {}
        self._tunelov = 0
        self.zavrnjenih = 0
        self.sprejetih = 0
        self._streznik = socket.create_server((naslov, self.vrata_nastavljena), backlog=32, reuse_port=False)
        self.vrata = self._streznik.getsockname()[1]
        self._tece = True
        self._nit = threading.Thread(target=self._sprejemaj, name="safeer-neposredno-vhod", daemon=True)
        self._nit.start()

    def zapri(self) -> None:
        self._tece = False
        _zapri(self._streznik)

    @property
    def tece(self) -> bool:
        return self._tece

    def _sprejemaj(self) -> None:
        while self._tece:
            try:
                s, naslov = self._streznik.accept()
            except OSError:
                if not self._tece:
                    return
                time.sleep(0.05)
                continue
            vir = naslov[0] if naslov else ""
            if not self.obramba.dovoli(vir):
                self.zavrnjenih += 1
                _zapri(s)
                continue
            zaupan = self._zaupan(vir)
            with self._zaklep:
                meja = NAJVEC_ROKOVANJ if zaupan else NAJVEC_ROKOVANJ - REZERVA_ZAUPANIM
                na_viru = self._rokovanj_vira.get(vir, 0)
                if self._rokovanj >= meja or na_viru >= NAJVEC_ROKOVANJ_NA_VIR or self._tunelov >= NAJVEC_TUNELOV:
                    polno = True
                else:
                    polno = False
                    self._rokovanj += 1
                    self._rokovanj_vira[vir] = na_viru + 1
            if polno:
                self.zavrnjenih += 1
                _zapri(s)
                continue
            threading.Thread(target=self._obdelaj, args=(s, vir), name="safeer-neposredno-rokovanje",
                             daemon=True).start()

    def _zavrni(self, s, vir: str, vrsta: str) -> None:
        """Tiho: brez odgovora, brez razloga."""
        self.zavrnjenih += 1
        try:
            self.obramba.dogodek(vir, vrsta)
        except Exception:
            pass
        _zapri(s)

    def _sprejmi_nonce(self, nonce: bytes, zdaj: float) -> bool:
        with self._zaklep:
            for n, do in list(self._nonci.items()):
                if do > zdaj:
                    break
                del self._nonci[n]
            if nonce in self._nonci:
                return False
            self._nonci[nonce] = zdaj + 2 * OKNO_CASA_S
            while len(self._nonci) > NAJVEC_NONCEV:
                self._nonci.popitem(last=False)
            return True

    def _obdelaj(self, s: socket.socket, vir: str) -> None:
        tunel = False
        try:
            tunel = self._rokovanje(s, vir)
        except Exception:
            _zapri(s)
        finally:
            with self._zaklep:
                self._rokovanj -= 1
                ostane = self._rokovanj_vira.get(vir, 1) - 1
                if ostane > 0:
                    self._rokovanj_vira[vir] = ostane
                else:
                    self._rokovanj_vira.pop(vir, None)

    def _zaupan(self, vir: str) -> bool:
        """Ali se je vir v zadnjem casu izkazal kot clan kroga (rezervirana mesta za rokovanje)."""
        try:
            return bool(self.obramba.zaupa(vir))
        except Exception:  # noqa: BLE001 - starejsa ali lazna obramba: brez rezerve
            return False

    def _rokovanje(self, s: socket.socket, vir: str) -> bool:
        konec = time.monotonic() + ROK_VHODA_S
        from core import link_vticnik
        # Rokovanje so majhni zapisi (izziv za vstopnicami TLS 1.3): z Naglovim algoritmom bi vsak cakal na potrditev
        # prejsnjega (do 40 ms vsak - izmerjeno na zanki).
        link_vticnik.brez_zamika(s)

        def ostane() -> float:
            return max(0.01, konec - time.monotonic())

        # 1. trk
        try:
            glava = _beri_tocno(s, 4 + _DOLZINA_ID + 8 + 16 + 1, ostane())
        except Exception:
            self._zavrni(s, vir, "rokovanje")
            return False
        if glava[:4] != MAGIJA:
            self._zavrni(s, vir, "tipanje")
            return False
        try:
            odjemalec = glava[4:4 + _DOLZINA_ID].decode("ascii")
        except UnicodeDecodeError:
            odjemalec = ""
        cas = struct.unpack(">Q", glava[22:30])[0]
        nonce = glava[30:46]
        dolzina = glava[46]
        if not _ID.match(odjemalec) or odjemalec == self.hub_id or not 8 <= dolzina <= 80:
            self._zavrni(s, vir, "brez_zaupanja")
            return False
        kljuc = self.kljuc_clana(odjemalec)
        if not kljuc:
            self._zavrni(s, vir, "brez_zaupanja")        # ni clan kroga (ali umaknjen): brez kriptografije ven
            return False
        zdaj = self.ura()
        if abs(zdaj - cas) > OKNO_CASA_S:
            self._zavrni(s, vir, "brez_zaupanja")
            return False
        try:
            podpis = _beri_tocno(s, dolzina, ostane())
            der = base64.b64decode(kljuc)
        except Exception:
            self._zavrni(s, vir, "rokovanje")
            return False
        if not self.preveri(der, podatki_trka(self.hub_id, odjemalec, cas, nonce), podpis):
            self._zavrni(s, vir, "brez_zaupanja")
            return False
        if not self._sprejmi_nonce(nonce, zdaj):
            self._zavrni(s, vir, "brez_zaupanja")        # ponovljen trk
            return False
        # 2. TLS
        try:
            s.settimeout(ostane())
            t = self._ctx.wrap_socket(s, server_side=True)
        except Exception:
            self._zavrni(s, vir, "rokovanje")
            return False
        # 3. izziv
        izziv = os.urandom(32)
        try:
            t.settimeout(ostane())
            t.sendall(izziv)
            g = _beri_tocno(t, 2, ostane())
            namen, dolzina = g[0], g[1]
            if namen not in (NAMEN_TUNEL, NAMEN_PREIZKUS) or not 8 <= dolzina <= 80:
                self._zavrni(t, vir, "brez_zaupanja")
                return False
            podpis = _beri_tocno(t, dolzina, ostane())
        except Exception:
            self._zavrni(t, vir, "rokovanje")
            return False
        if not self.preveri(der, podatki_izziva(self.hub_id, odjemalec, izziv, self.odtis, namen), podpis):
            self._zavrni(t, vir, "brez_zaupanja")
            return False
        try:
            self.obramba.zaupaj(vir)
        except Exception:
            pass
        self.sprejetih += 1
        if je_javni_ipv4(vir) and self.ob_zunanji is not None:
            try:
                self.ob_zunanji(vir)            # prava overjena povezava od zunaj: vrata so res dosegljiva
            except Exception:
                pass
        if namen == NAMEN_PREIZKUS:
            try:
                t.sendall(POTRDITEV)
            except Exception:
                pass
            _zapri(t)
            return False
        hub_vrata = int(self.hub_vrata() or 0)
        if hub_vrata <= 0:
            _zapri(t)
            return False
        # Krajevna vrata oznacimo, PREDEN se povezemo: Hub vidi 127.0.0.1 in mora ze ob sprejemu vedeti, da je to
        # neposredna pot (meritve, vmesnik, izbira boljse poti).
        h = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lokalna = 0
        try:
            h.bind(("127.0.0.1", 0))
            lokalna = h.getsockname()[1]
            _oznaci(lokalna, POT_NEPOSREDNO)
            h.settimeout(5)
            h.connect(("127.0.0.1", hub_vrata))
            h.settimeout(None)
        except OSError:
            _odznaci(lokalna)
            _zapri(h)
            _zapri(t)
            return False
        try:
            t.sendall(POTRDITEV)
            t.settimeout(None)
        except Exception:
            _odznaci(lokalna)
            _zapri(t)
            _zapri(h)
            return False
        from core import link_vticnik
        link_vticnik.brez_zamika(h)
        link_vticnik.brez_zamika(t)
        # Tunel je brez roka (WebSocket sme dolgo molcati): mrtvo drugo stran zazna keepalive in mesto se sprosti.
        link_vticnik.ohrani_zivost(t)
        with self._zaklep:
            self._tunelov += 1

        def konec_tunela() -> None:
            _odznaci(lokalna)
            with self._zaklep:
                self._tunelov -= 1

        threading.Thread(target=_pipe, args=(link_vticnik.zavaruj(t), h, konec_tunela),
                         name="safeer-neposredno-tunel", daemon=True).start()
        return True


# ------------------------------------------------------------------ odjemalec: neposredna povezava

class NapakaNeposredne(ConnectionError):
    """Neposredna pot ni uspela (ni povezave, napacen kljuc, zavrnjen)."""


def _kontekst_odjemalca() -> ssl.SSLContext:
    k = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    k.check_hostname = False
    k.verify_mode = ssl.CERT_NONE           # zaupanje da kljuc v potrdilu = kljuc clana kroga (spodaj), ne overitelj
    k.minimum_version = ssl.TLSVersion.TLSv1_2
    return k


def _kljuc_potrdila(der: bytes) -> str:
    from core import link_tls
    return link_tls.javni_kljuc_potrdila(der)


def odpri_neposredno(ip: str, vrata: int, hub_id: str, kljuc_huba_b64: str, nas_id: str,
                     podpisi: Callable[[bytes], bytes], namen: int = NAMEN_TUNEL,
                     rok_povezave: float = ROK_POVEZAVE_S, rok_rokovanja: float = ROK_ROKOVANJA_S):
    """Trk + TLS (kljuc sredisca iz kroga) + izziv. Vrne (TLS vticnica, ms do TCP, ms skupaj) ali dvigne NapakaNeposredne."""
    hub_id, nas_id = jedro(hub_id), jedro(nas_id)
    if not hub_id or not nas_id:
        raise NapakaNeposredne("ni id iz kljuca")
    t0 = time.monotonic()
    try:
        s = socket.create_connection((ip, int(vrata)), timeout=rok_povezave)
    except OSError as e:
        raise NapakaNeposredne("ni povezave") from e
    t_tcp = (time.monotonic() - t0) * 1000.0
    t = None
    try:
        from core import link_vticnik
        link_vticnik.brez_zamika(s)
        s.settimeout(rok_rokovanja)
        s.sendall(sestavi_trk(hub_id, nas_id, podpisi))
        t = _kontekst_odjemalca().wrap_socket(s, server_hostname=None)
        der = t.getpeercert(binary_form=True) or b""
        if not der or _kljuc_potrdila(der) != kljuc_huba_b64:
            raise NapakaNeposredne("kljuc sredisca se ne ujema s krogom")
        odtis = hashlib.sha256(der).hexdigest()
        izziv = _beri_tocno(t, 32, rok_rokovanja)
        podpis = podpisi(podatki_izziva(hub_id, nas_id, izziv, odtis, namen))
        t.sendall(bytes([namen, len(podpis)]) + podpis)
        if _beri_tocno(t, 1, rok_rokovanja) != POTRDITEV:
            raise NapakaNeposredne("zavrnjeno")
        t.settimeout(None)
        return t, t_tcp, (time.monotonic() - t0) * 1000.0
    except NapakaNeposredne:
        _zapri(t or s)
        raise
    except Exception as e:
        _zapri(t or s)
        raise NapakaNeposredne("rokovanje ni uspelo") from e


def preizkusi(ip: str, vrata: int, hub_id: str, kljuc_huba_b64: str, nas_id: str,
              podpisi: Callable[[bytes], bytes]) -> Optional[float]:
    """Preizkus dosegljivosti (namen 2): ms do potrditve ali None. Sredisce ga steje kot preverjanje od zunaj."""
    try:
        t, _tcp, skupaj = odpri_neposredno(ip, vrata, hub_id, kljuc_huba_b64, nas_id, podpisi, NAMEN_PREIZKUS)
    except NapakaNeposredne:
        return None
    _zapri(t)
    return skupaj


# ------------------------------------------------------------------ odjemalec: iskanje oglasa (prisotnost)

def poisci_oglas(hub_id: str, kljuc_huba_b64: str, rok_s: float = 5.0,
                 prenesi: Optional[Callable[[str], dict]] = None,
                 preveri: Optional[Callable[[bytes, bytes, bytes], bool]] = None) -> Optional[dict]:
    """Prisotnost sredisca na link.safeer.si (vidi jo samo clan njegovega kroga) -> preverjen oglas ali None."""
    if preveri is None:
        from core import link_kripto
        preveri = link_kripto.preveri
    try:
        if prenesi is None:
            from core import link_rele
            pot = "/v1/presence?device_id=%s" % hub_id
            z = urllib.request.Request("https://%s%s" % (link_rele.GOSTITELJ, pot),
                                       headers=dict(link_rele.podpisane_glave("GET", pot), **{"User-Agent": link_rele.UA}))
            with urllib.request.urlopen(z, timeout=rok_s) as r:
                odgovor = json.loads(r.read(65536).decode("utf-8"))
        else:
            odgovor = prenesi(hub_id)
        namigi = ((odgovor or {}).get("presence") or {}).get("candidate_hints") or []
    except Exception:
        return None
    for n in namigi[:32]:
        oglas = preveri_oglas(str(n), hub_id, kljuc_huba_b64, preveri)
        if oglas is not None:
            oglas["niz"] = str(n)
            return oglas
    return None


def _krajevni_naslov_proti(ip: str) -> str:
    """Nas naslov na poti do `ip` (brez prometa): sprememba pomeni drugo omrezje."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((ip, 9))
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


# ------------------------------------------------------------------ odjemalec: ena krajevna vrata, dve poti

_registri_poti: Dict[str, "LokalniOdZunaj"] = {}
_registri_zaklep = threading.Lock()


class LokalniOdZunaj:
    """127.0.0.1:vrata do sredisca `cilj` zunaj doma: vsaka povezava najprej neposredno, nato prek releja.

    Isti vmesnik kot link_rele.LokalniRele (`vrata`, `zadnja_napaka`, `zapri`), zato ga uporabljajo vsi, ki so prej
    uporabljali rele (Link Mesh, tokovi datotek in slike): skozi tece nespremenjen TLS Linka s pripetim kljucem."""

    def __init__(self, cilj: str, kljuc_huba: Optional[str] = None,
                 rele: Optional[Callable[[str], object]] = None,
                 nas_id: Optional[Callable[[], str]] = None,
                 podpisi: Optional[Callable[[bytes], bytes]] = None,
                 poisci: Optional[Callable[[str, str], Optional[dict]]] = None,
                 omrezje: Optional[Callable[[str], str]] = None,
                 pot_spomina: Optional[str] = None,
                 ura: Callable[[], float] = time.time) -> None:
        self.cilj = jedro(cilj) or cilj
        self._kljuc = kljuc_huba
        self._rele_tovarna = rele
        self._rele = None
        self._nas_id = nas_id
        self._podpisi = podpisi
        self._poisci = poisci or (lambda h, k: poisci_oglas(h, k))
        self._omrezje = omrezje or _krajevni_naslov_proti
        self._pot_spomina = pot_spomina
        self.ura = ura
        self._zaklep = threading.Lock()
        self.zadnja_napaka = ""
        self.zadnja_pot = ""
        self.zadnji_ms: Optional[float] = None
        self._oglas: Optional[dict] = None
        self._oglas_ob = 0.0
        self._iskanje: Optional[threading.Thread] = None
        self._premor_do = 0.0
        self._premor = 0.0
        self._omrezje_ob_neuspehu = ""
        self._preizkuseno: Dict[tuple, str] = {}     # (ip, vrata) -> omrezje, kjer je preizkus ze tekel
        self._nas_uspeh: Dict[tuple, float] = {}     # (ip, vrata) -> cas: neposredno smo ze uspeli mi
        self._nalozi_spomin()
        self.streznik = socket.create_server(("127.0.0.1", 0))
        self.vrata = self.streznik.getsockname()[1]
        #: Druga krajevna vrata: SAMO neposredno, brez releja (zamenjava obstojece povezave prek releja z neposredno -
        #: ob neuspehu se ne sme odpreti se en kanal releja).
        self.streznik_neposredno = socket.create_server(("127.0.0.1", 0))
        self.vrata_neposredno = self.streznik_neposredno.getsockname()[1]
        self._tece = True
        threading.Thread(target=self._sprejemaj, args=(self.streznik, self.vrata, False), name="safeer-od-zunaj",
                         daemon=True).start()
        threading.Thread(target=self._sprejemaj, args=(self.streznik_neposredno, self.vrata_neposredno, True),
                         name="safeer-od-zunaj-neposredno", daemon=True).start()
        with _registri_zaklep:
            _registri_poti[self.cilj] = self
        self._isci_v_ozadju()

    # -- odvisnosti

    def kljuc(self) -> str:
        if self._kljuc:
            return self._kljuc
        try:
            from core import link_krog
            self._kljuc = link_krog.krog().kljuc_za_jedro(self.cilj) or ""
        except Exception:
            self._kljuc = ""
        return self._kljuc

    def nas_id(self) -> str:
        if self._nas_id is not None:
            return self._nas_id()
        from core import link_krog
        return link_krog.id_iz_kljuca(link_krog.javni_kljuc_b64())

    def podpisi(self, podatki: bytes) -> bytes:
        if self._podpisi is not None:
            return self._podpisi(podatki)
        from core import link_krog
        return base64.b64decode(link_krog.podpisi(podatki))

    def rele(self):
        with self._zaklep:
            if self._rele is None:
                if self._rele_tovarna is not None:
                    self._rele = self._rele_tovarna(self.cilj)
                else:
                    from core import link_rele
                    self._rele = link_rele.LokalniRele(self.cilj, poslusaj=False)
            return self._rele

    # -- spomin zadnje delujoce poti

    def _nalozi_spomin(self) -> None:
        if not self._pot_spomina:
            return
        z = _beri_json(self._pot_spomina).get(self.cilj) or {}
        niz = str(z.get("oglas") or "")
        if niz and self.kljuc():
            from core import link_kripto
            oglas = preveri_oglas(niz, self.cilj, self.kljuc(), link_kripto.preveri, self.ura())
            if oglas is not None:
                oglas["niz"] = niz
                self._oglas = oglas
                if z.get("pot") == POT_NEPOSREDNO:
                    self._nas_uspeh[(oglas["ip"], oglas["vrata"])] = float(z.get("ob") or 0)
        self.zadnja_pot = str(z.get("pot") or "")

    def _zapomni(self) -> None:
        if not self._pot_spomina:
            return
        vse = _beri_json(self._pot_spomina)
        vse[self.cilj] = {"pot": self.zadnja_pot, "ob": int(self.ura()),
                          "ms": None if self.zadnji_ms is None else round(self.zadnji_ms, 1),
                          "oglas": (self._oglas or {}).get("niz", "")}
        _pisi_json(self._pot_spomina, vse)

    # -- oglas

    def _isci_v_ozadju(self) -> None:
        with self._zaklep:
            if self._iskanje is not None and self._iskanje.is_alive():
                return
            if self.ura() - self._oglas_ob < PRISOTNOST_VSAKIH_S and self._oglas_ob:
                return
            self._oglas_ob = self.ura()
            self._iskanje = threading.Thread(target=self._isci, name="safeer-od-zunaj-oglas", daemon=True)
            self._iskanje.start()

    def _isci(self) -> None:
        kljuc = self.kljuc()
        if not kljuc:
            return
        try:
            oglas = self._poisci(self.cilj, kljuc)
        except Exception:
            oglas = None
        with self._zaklep:
            if oglas is not None:
                self._oglas = oglas
            elif self._oglas is not None and self._oglas.get("exp", 0) <= self.ura():
                self._oglas = None
        if oglas is not None and not oglas.get("preverjeno"):
            self._preizkus_v_ozadju(oglas)

    def _preizkus_v_ozadju(self, oglas: dict) -> None:
        """Nepreverjen oglas: preizkus v ozadju (namen 2). Sredisce ob uspehu oznaci vrata kot preverjena; mi pa
        neposredno pot uporabimo sele, ko je preverjena (pri sredisci ali z nasim uspehom)."""
        k = (oglas["ip"], oglas["vrata"])
        omrezje = self._omrezje(oglas["ip"])
        with self._zaklep:
            if self._preizkuseno.get(k) == omrezje:
                return
            self._preizkuseno[k] = omrezje

        def teci():
            ms = preizkusi(oglas["ip"], oglas["vrata"], self.cilj, self.kljuc(), self.nas_id(), self.podpisi)
            if ms is not None:
                with self._zaklep:
                    self._nas_uspeh[k] = self.ura()
                print("[SafeerLink] neposredna pot do %s preverjena (%.0f ms)" % (self.cilj, ms), flush=True)
        threading.Thread(target=teci, name="safeer-od-zunaj-preizkus", daemon=True).start()

    def konec(self, cakaj_s: float = 0.0) -> Optional[Tuple[str, int]]:
        """(ip, vrata) neposredne poti, ce jo smemo poskusiti zdaj, sicer None."""
        self._isci_v_ozadju()
        if cakaj_s > 0 and self._oglas is None:
            it = self._iskanje
            if it is not None:
                it.join(cakaj_s)
        with self._zaklep:
            oglas = self._oglas
            if oglas is None or oglas.get("exp", 0) <= self.ura():
                return None
            k = (oglas["ip"], oglas["vrata"])
            if not (oglas.get("preverjeno") or k in self._nas_uspeh):
                return None
            if self._premor_do > self.ura():
                # Sprememba omrezja (drug krajevni naslov) premor izbrise: morda smo zdaj tam, od koder gre.
                if self._omrezje(oglas["ip"]) == self._omrezje_ob_neuspehu:
                    return None
                self._premor_do, self._premor = 0.0, 0.0
            return k

    # -- povezave

    def _sprejemaj(self, streznik: socket.socket, vrata: int, samo_neposredno: bool) -> None:
        from core import link_rele
        while self._tece:
            try:
                tcp, naslov = streznik.accept()
            except OSError as e:
                if self._tece and os_deskriptorji.prehodna_napaka_accept(e):
                    time.sleep(os_deskriptorji.PREMOR_PO_NAPAKI_ACCEPT_S)
                    continue
                return
            if hasattr(os, "getuid") and isinstance(naslov, tuple):
                # Drug uporabnik tega racunalnika ne sme uporabljati poti, podpisane z nasim kljucem.
                uid = link_rele._uid_lokalne_povezave(int(naslov[1]), vrata)
                if uid is not None and uid != os.getuid():
                    self.zadnja_napaka = "tuj_uporabnik"
                    _zapri(tcp)
                    continue
            threading.Thread(target=self._povezava, args=(tcp, naslov, samo_neposredno), name="safeer-od-zunaj-kanal",
                             daemon=True).start()

    def neposredno_na_voljo(self) -> bool:
        """Ali bi nova povezava zdaj sla neposredno (preverjen oglas, brez premora)."""
        return self.konec() is not None

    def _povezava(self, tcp: socket.socket, naslov, samo_neposredno: bool = False) -> None:
        vrata_odjemalca = int(naslov[1]) if isinstance(naslov, tuple) and len(naslov) > 1 else 0
        # Na oglas pocakamo (najvec CAKAJ_OGLAS_S) samo, ce je bila zadnja delujoca pot neposredna in oglasa se ni
        # (npr. po ponovnem zagonu je zapomnjeni potekel). Sicer ta povezava ne caka: gre prek releja, iskanje tece.
        cakaj = CAKAJ_OGLAS_S if (self._oglas is None and self.zadnja_pot == POT_NEPOSREDNO) else 0.0
        k = self.konec(cakaj_s=cakaj)
        kljuc = self.kljuc()
        if k is not None and kljuc:
            try:
                t, ms_tcp, _ms = odpri_neposredno(k[0], k[1], self.cilj, kljuc, self.nas_id(), self.podpisi)
            except NapakaNeposredne as e:
                with self._zaklep:
                    self._premor = min(NAJDALJSI_PREMOR_S, self._premor * 2 if self._premor else PREMOR_S)
                    self._premor_do = self.ura() + self._premor
                    self._omrezje_ob_neuspehu = self._omrezje(k[0])
                self.zadnja_napaka = str(e)
                print("[SafeerLink] neposredna pot do %s ni uspela (%s); prek releja, neposredno znova cez %d s"
                      % (self.cilj, e, self._premor), flush=True)
            else:
                with self._zaklep:
                    self._premor_do, self._premor = 0.0, 0.0
                    self._nas_uspeh[k] = self.ura()
                spremenjena = self.zadnja_pot != POT_NEPOSREDNO
                self.zadnja_pot, self.zadnji_ms = POT_NEPOSREDNO, ms_tcp
                if spremenjena:
                    self._zapomni()
                _oznaci(vrata_odjemalca, POT_NEPOSREDNO)
                from core import link_vticnik
                link_vticnik.brez_zamika(tcp)
                link_vticnik.ohrani_zivost(t)
                _pipe(link_vticnik.zavaruj(t), tcp, lambda: _odznaci(vrata_odjemalca))
                return
        if samo_neposredno:
            _zapri(tcp)
            return
        spremenjena = self.zadnja_pot != POT_RELE
        self.zadnja_pot = POT_RELE
        if spremenjena:
            self._zapomni()
        _oznaci(vrata_odjemalca, POT_RELE)
        try:
            rele = self.rele()
            rele.kanal(tcp)
            napaka = getattr(rele, "zadnja_napaka", "")
            if napaka:
                self.zadnja_napaka = napaka
        finally:
            _odznaci(vrata_odjemalca)

    def stanje(self) -> dict:
        return {"pot": self.zadnja_pot, "ms": None if self.zadnji_ms is None else round(self.zadnji_ms, 1),
                "oglas": self._oglas is not None, "premor": self._premor_do > self.ura()}

    def zapri(self) -> None:
        self._tece = False
        _zapri(self.streznik)
        _zapri(self.streznik_neposredno)
        with _registri_zaklep:
            if _registri_poti.get(self.cilj) is self:
                del _registri_poti[self.cilj]
        r = self._rele
        if r is not None:
            try:
                r.zapri()
            except Exception:
                pass


def od_zunaj(cilj: str):
    """Tovarna za klicatelje, ki so prej delali link_rele.LokalniRele(cilj)."""
    try:
        pot = _pot_poti()
    except Exception:
        pot = None
    return LokalniOdZunaj(cilj, pot_spomina=pot)


def poti_od_zunaj(samo_zive: bool = False) -> Dict[str, dict]:
    """Zadnja pot do vsakega sredisca zunaj doma: v tem procesu, sicer iz spomina na disku (drug proces).
    `samo_zive`: samo krajevni konci, ki v tem procesu zdaj obstajajo (vmesnik ne kaze starih zapisov)."""
    izid: Dict[str, dict] = {}
    if not samo_zive:
        try:
            for hid, z in _beri_json(_pot_poti()).items():
                if isinstance(z, dict):
                    izid[hid] = {"pot": z.get("pot", ""), "ms": z.get("ms")}
        except Exception:
            pass
    with _registri_zaklep:
        for hid, o in _registri_poti.items():
            izid[hid] = o.stanje()
    return izid


# ------------------------------------------------------------------ sredisce: vzdrzevanje vhoda in oglasa

class NeposrednoHuba:
    """Na sredisci: po nastavitvi odpre/zapre vhod, izve javni IPv4 (STUN), vodi preverjanje in da oglas za prisotnost."""

    def __init__(self, hub_vrata: Callable[[], int],
                 nastavitve_fn: Callable[[], dict] = nastavitve,
                 stun: Callable[[], str] = javni_ipv4_stun,
                 vhod_tovarna: Optional[Callable[..., VhodNeposredno]] = None,
                 pot_stanja: Optional[str] = None,
                 ura: Callable[[], float] = time.time) -> None:
        self.hub_vrata = hub_vrata
        self._nastavitve = nastavitve_fn
        self._stun = stun
        self._vhod_tovarna = vhod_tovarna or self._nov_vhod
        self._pot_stanja = pot_stanja
        self.ura = ura
        self.vhod: Optional[VhodNeposredno] = None
        self._zaklep = threading.Lock()
        self._stanje = _beri_json(pot_stanja) if pot_stanja else {}
        self._stun_ob = 0.0
        self.napaka = ""
        self._nit: Optional[threading.Thread] = None
        self._ustavljen = threading.Event()
        self._korak_zaklep = threading.Lock()

    # -- identiteta te naprave (link_krog / link_datoteke)

    @staticmethod
    def _nov_vhod(vrata: int, hub_vrata: Callable[[], int], ob_zunanji: Callable[[str], None]) -> VhodNeposredno:
        from core import link_datoteke, link_krog
        kljuc, potrdilo, _odtis = link_datoteke.zagotovi_potrdilo()
        hub_id = link_krog.id_iz_kljuca(link_krog.javni_kljuc_b64())

        def kljuc_clana(cid: str) -> Optional[str]:
            k = link_krog.krog().kljuc_za_jedro(cid)
            return k if k and id_iz_kljuca(k) == cid else None
        return VhodNeposredno(vrata, hub_vrata, hub_id, kljuc, potrdilo, kljuc_clana, ob_zunanji=ob_zunanji)

    def zazeni(self) -> None:
        if self._nit is None:
            self._nit = threading.Thread(target=self._zanka, name="safeer-neposredno-sredisce", daemon=True)
            self._nit.start()

    def ustavi(self) -> None:
        self._ustavljen.set()
        with self._zaklep:
            v, self.vhod = self.vhod, None
        if v is not None:
            v.zapri()

    def _zanka(self) -> None:
        while not self._ustavljen.is_set():
            try:
                self.korak()
            except Exception as e:  # noqa: BLE001
                self.napaka = str(e)[:120]
            self._ustavljen.wait(30.0)

    def korak(self) -> None:
        """En pregled: nastavitev, vhod, javni naslov. Brez cakanja na mrezo, razen STUN (najvec ~3 s, redko).
        Klice ga nit vzdrzevanja in vmesnik (takoj po spremembi nastavitve) - po en naenkrat."""
        with self._korak_zaklep:
            self._korak()

    def _korak(self) -> None:
        n = self._nastavitve()
        with self._zaklep:
            vhod = self.vhod
        hub_vrata = int(self.hub_vrata() or 0)
        if not n["vklopljeno"] or hub_vrata <= 0:
            if vhod is not None:
                self.ustavi_vhod()
            return
        if vhod is not None and vhod.vrata_nastavljena != n["vrata"]:
            self.ustavi_vhod()
            vhod = None
        if vhod is None:
            try:
                vhod = self._vhod_tovarna(n["vrata"], self.hub_vrata, self._ob_zunanji)
            except OSError as e:
                self.napaka = "vrata %d niso prosta (%s)" % (n["vrata"], e.strerror or e)
                return
            with self._zaklep:
                self.vhod = vhod
            self.napaka = ""
            print("[SafeerLink] neposredna povezava od zunaj: vhod na vratih %d" % vhod.vrata, flush=True)
        if self.ura() - self._stun_ob >= STUN_VSAKIH_S or not self._stanje.get("ip"):
            self._stun_ob = self.ura()
            ip = self._stun()
            if ip and ip != self._stanje.get("ip"):
                # Nov javni naslov: prejsnja preverba ne velja vec.
                self._stanje = {"ip": ip, "preverjeno": 0, "vrata": n["vrata"]}
                self._shrani()
            elif not ip and not self._stanje.get("ip"):
                self.napaka = "javnega naslova ni bilo mogoce ugotoviti"

    def ustavi_vhod(self) -> None:
        with self._zaklep:
            v, self.vhod = self.vhod, None
        if v is not None:
            v.zapri()
            print("[SafeerLink] neposredna povezava od zunaj: vhod zaprt", flush=True)

    def _ob_zunanji(self, vir: str) -> None:
        zdaj = self.ura()
        with self._zaklep:
            prej = float(self._stanje.get("preverjeno") or 0)
            self._stanje["preverjeno"] = zdaj
            vhod = self.vhod
            if vhod is not None:
                self._stanje["vrata"] = vhod.vrata_nastavljena
        if zdaj - prej > 600:
            self._shrani()
        if not prej:
            print("[SafeerLink] neposredna povezava od zunaj je preverjena (prva overjena povezava z interneta)", flush=True)

    def _shrani(self) -> None:
        if self._pot_stanja:
            _pisi_json(self._pot_stanja, dict(self._stanje))

    def preverjeno(self) -> bool:
        with self._zaklep:
            p = float(self._stanje.get("preverjeno") or 0)
            vhod = self.vhod
            ista_vrata = vhod is not None and self._stanje.get("vrata") == vhod.vrata_nastavljena
        return bool(p) and ista_vrata and self.ura() - p < PREVERJENO_VELJA_S

    def namigi(self, kljuc_b64: Optional[str] = None, podpisi: Optional[Callable[[bytes], bytes]] = None) -> List[str]:
        """`candidate_hints` za prisotnost: podpisan oglas, ce vhod tece in je javni naslov znan; sicer []."""
        with self._zaklep:
            vhod = self.vhod
            ip = str(self._stanje.get("ip") or "")
        if vhod is None or not vhod.tece or not je_javni_ipv4(ip):
            return []
        from core import link_krog
        kljuc_b64 = kljuc_b64 or link_krog.javni_kljuc_b64()
        if podpisi is None:
            def podpisi(p: bytes) -> bytes:
                return base64.b64decode(link_krog.podpisi(p))
        p = float(self._stanje.get("preverjeno") or 0) if self.preverjeno() else 0.0
        return [sestavi_oglas(id_iz_kljuca(kljuc_b64), ip, vhod.vrata_nastavljena, kljuc_b64, podpisi, preverjeno=p,
                              zdaj=self.ura())]

    def stanje(self) -> dict:
        """Za vmesnik (brez naslova IP): vklopljeno, vrata, tece, javni naslov znan, preverjeno, napaka."""
        n = self._nastavitve()
        with self._zaklep:
            vhod = self.vhod
            znan = je_javni_ipv4(str(self._stanje.get("ip") or ""))
            p = float(self._stanje.get("preverjeno") or 0)
        return {"vklopljeno": n["vklopljeno"], "vrata": n["vrata"], "tece": vhod is not None and vhod.tece,
                "javni_naslov": znan, "preverjeno": self.preverjeno(), "preverjeno_ob": int(p) if p else 0,
                "napaka": self.napaka}


_sredisce: Optional[NeposrednoHuba] = None
_sredisce_zaklep = threading.Lock()


def zazeni_na_sredisci(hub_vrata: Callable[[], int]) -> NeposrednoHuba:
    """En vzdrzevalec na proces (kot agent releja)."""
    global _sredisce
    with _sredisce_zaklep:
        if _sredisce is None:
            try:
                pot = _pot_stanja()
            except Exception:
                pot = None
            _sredisce = NeposrednoHuba(hub_vrata, pot_stanja=pot)
            _sredisce.zazeni()
        else:
            _sredisce.hub_vrata = hub_vrata
        return _sredisce


def sredisce() -> Optional[NeposrednoHuba]:
    return _sredisce


def namigi_sredisca() -> List[str]:
    s = _sredisce
    try:
        return s.namigi() if s is not None else []
    except Exception:
        return []


def stanje_za_vmesnik() -> dict:
    """Stanje za Safeer Link (nastavitve): vhod te naprave in pot do vsakega sredisca zunaj doma."""
    s = _sredisce
    if s is not None:
        vhod = s.stanje()
    else:
        n = nastavitve()
        st = _beri_json(_pot_stanja())
        vhod = {"vklopljeno": n["vklopljeno"], "vrata": n["vrata"], "tece": False,
                "javni_naslov": je_javni_ipv4(str(st.get("ip") or "")), "preverjeno": False,
                "preverjeno_ob": int(st.get("preverjeno") or 0), "napaka": ""}
    return {"vhod": vhod, "poti": poti_od_zunaj()}


__all__ = ["VhodNeposredno", "LokalniOdZunaj", "NeposrednoHuba", "odpri_neposredno", "preizkusi", "sestavi_oglas",
           "preveri_oglas", "sestavi_trk", "javni_ipv4_stun", "razberi_stun", "nastavitve", "shrani_nastavitve",
           "od_zunaj", "zazeni_na_sredisci", "namigi_sredisca", "stanje_za_vmesnik", "poti_od_zunaj",
           "POT_LAN", "POT_NEPOSREDNO", "POT_RELE", "PRIVZETA_VRATA"]
