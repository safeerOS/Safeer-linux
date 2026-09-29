"""Link Mesh (docs/LINK-MESH.md): nas Hub se sam poveze s Hubi drugih naprav iz kroga zaupanja.

Hub na tej napravi tece vedno. Ta modul poisce druge Hube (mDNS), preveri, da potrdilo nosi
kljuc clana kroga, se prijavi s podpisom nasega kljuca in odpre **sosednjo povezavo**. Od tam naprej
vse dela Hub.obdelaj_soseda: izmenjava lokalnih naprav, usmerjanje, krog.

Da nastane za vsak par ena povezava, prvi klice manjsi id; vecji pocaka in klice sam sele, ce ga
manjsi dolgo ne doseze (npr. pozarni zid na eni strani). Ce vseeno nastaneta dve, Hub obdrzi tisto,
ki jo je odprl manjsi id (Hub.dodaj_soseda).
"""

from __future__ import annotations

import collections
import json
import threading
import time
from typing import Callable, Dict, List, Optional

from core import link_hub, link_krog, link_tls

#: Kako pogosto iscemo sosede in kdaj vecji id klice sam.
ISCI_VSAKIH_S = 15.0
VECJI_CAKA_S = 40.0
#: Srcni utrip sosednje povezave (streznik na drugi strani pinga sam; to je nasa stran).
UTRIP_S = 25.0
#: Najvec cakajocih sporocil na sosednjo povezavo, preden jo zapremo (sosed ne bere).
NAJVEC_V_VRSTI = 512


class OdhodnaSosednja:
    """Povezava, ki smo jo odprli mi. Pise v svoji niti, da pocasen sosed ne ustavi nasega Huba."""

    def __init__(self, ws: "link_hub.WsOdjemalec", naslov: str) -> None:
        self.ws = ws
        self.naslov = naslov
        self.podatki: dict = {}
        self._vrsta: collections.deque = collections.deque()
        self._ima = threading.Event()
        self._zaprta = False
        threading.Thread(target=self._pisi, name="safeer-mesh-pisec", daemon=True).start()

    def poslji(self, besedilo: str) -> bool:
        if self._zaprta:
            return False
        if len(self._vrsta) >= NAJVEC_V_VRSTI:
            self.zapri(1008, "sosed ne bere")
            return False
        self._vrsta.append(besedilo)
        self._ima.set()
        return True

    def _pisi(self) -> None:
        while not self._zaprta:
            self._ima.wait(UTRIP_S)
            self._ima.clear()
            if not self._vrsta:
                if not self._zaprta and not self.ws.ping():
                    self.zapri()
                continue
            while self._vrsta and not self._zaprta:
                besedilo = self._vrsta.popleft()
                try:
                    self.ws.poslji(besedilo)
                except Exception:
                    self.zapri()
                    return

    def zapri(self, *_a, **_k) -> None:
        if self._zaprta:
            return
        self._zaprta = True
        self._ima.set()
        try:
            self.ws.zapri()
        except Exception:
            pass

    @property
    def zaprta(self) -> bool:
        return self._zaprta


class MeshPovezovalec:
    """Poisce in vzdrzuje sosednje povezave nasega Huba."""

    def __init__(self, hub, nas_id: str, ime: str = "Safeer",
                 poisci: Optional[Callable[[], List[dict]]] = None) -> None:
        self.hub = hub
        self.nas_id = nas_id
        self.ime = ime
        self.poisci = poisci or (lambda: link_hub.poisci_hube_mdns(2.0))
        self._klicem: set = set()
        self._prvic_videni: Dict[str, float] = {}
        self._ustavljen = threading.Event()
        self._zaklep = threading.Lock()
        self._nit: Optional[threading.Thread] = None

    def zazeni(self) -> None:
        if self._nit is not None:
            return
        self._nit = threading.Thread(target=self._zanka, name="safeer-mesh", daemon=True)
        self._nit.start()

    def ustavi(self) -> None:
        self._ustavljen.set()

    def _zanka(self) -> None:
        self._ustavljen.wait(2.0)
        while not self._ustavljen.is_set():
            try:
                self.en_krog()
            except Exception as e:  # noqa: BLE001
                print("[SafeerLink] mesh:", e)
            self._ustavljen.wait(ISCI_VSAKIH_S)

    def kandidati(self, oglasi: List[dict], zdaj: Optional[float] = None) -> List[dict]:
        """Oglasi Hubov, ki jih moramo zdaj poklicati (brez omrezja - preizkusljivo)."""
        zdaj = time.time() if zdaj is None else zdaj
        povezani = set(self.hub.sosedje())
        izbrani = []
        for h in oglasi:
            hid = str(h.get("id") or "")
            if not hid or hid == self.nas_id or not h.get("tls") or hid in povezani:
                continue
            if h.get("mesh") != link_hub_streznik_mesh():
                continue            # star Hub: sosednje povezave ne razume
            with self._zaklep:
                if hid in self._klicem:
                    continue
                prvic = self._prvic_videni.setdefault(hid, zdaj)
            try:
                if link_krog.krog().clan_za_id(hid) is None:
                    continue
            except Exception:
                continue
            if hid < self.nas_id and zdaj - prvic < VECJI_CAKA_S:
                continue            # manjsi id klice prvi; pocakamo nanj
            izbrani.append(h)
        return izbrani

    def en_krog(self) -> None:
        for h in self.kandidati(self.poisci()):
            with self._zaklep:
                self._klicem.add(h["id"])
            threading.Thread(target=self._klici, args=(h,), name="safeer-mesh-klic", daemon=True).start()

    def _klici(self, h: dict) -> None:
        hid = str(h["id"])
        try:
            self._odpri(h)
        except Exception as e:  # noqa: BLE001
            print("[SafeerLink] mesh: %s ni dosegljiv (%s)" % (hid, e))
        finally:
            with self._zaklep:
                self._klicem.discard(hid)

    def _odpri(self, h: dict) -> None:
        hid, naslov = str(h["id"]), str(h["naslov"])
        clan = link_krog.krog().clan_za_id(hid)
        if clan is None:
            return
        # Zaupanje: kljuc v potrdilu mora biti kljuc tega clana v krogu (oglas mDNS ne velja nic).
        odtis, kljuc = link_tls.potrdilo_huba(naslov)
        if not odtis or not kljuc or kljuc != clan.get("kljuc"):
            return
        vstopnica, _ = link_hub.vzemi_vstopnico_s_podpisom(naslov, self.nas_id, odtis, self.ime)
        if not vstopnica:
            return
        locilo = "&" if "?" in naslov else "?"
        ws = link_hub.WsOdjemalec(f"{naslov}{locilo}ticket={vstopnica}", odtis=odtis)
        ws.odpri()
        # Prijava gre prva (sinhrono), sele nato pisec: sosed mora vedeti, da smo Hub, preden
        # dobi karkoli drugega.
        ws.poslji(json.dumps({"id": str(int(time.time() * 1000)), "type": "cast.register",
                              "payload": {"device_id": self.nas_id, "name": self.ime, "role": "hub",
                                          "capabilities": [link_hub_streznik_mesh()], "protocol": "1"}}))
        povezava = OdhodnaSosednja(ws, naslov.split("//", 1)[-1].split(":", 1)[0])
        if not self.hub.dodaj_soseda(hid, povezava, self.nas_id):
            povezava.zapri()
            return
        print("[SafeerLink] mesh: sosed %s (%s)" % (hid, naslov))
        self._beri(hid, povezava)

    def _beri(self, hid: str, povezava: OdhodnaSosednja) -> None:
        try:
            while not povezava.zaprta:
                try:
                    surovo = povezava.ws.prejmi()
                except TimeoutError:
                    continue
                except Exception:
                    break
                if surovo is None:
                    break
                try:
                    sporocilo = json.loads(surovo)
                except Exception:
                    continue
                if isinstance(sporocilo, dict) and sporocilo.get("type") == "cast.ack" \
                        and sporocilo.get("status") == "rejected":
                    # Sosed nas ne sprejme (npr. ze ima povezavo, ki jo je odprl on).
                    break
                odgovor = self.hub.obdelaj(povezava, surovo)
                if odgovor:
                    povezava.poslji(odgovor)
        finally:
            povezava.zapri()
            self.hub.odklopi(povezava)


def link_hub_streznik_mesh() -> str:
    from core import link_hub_streznik
    return link_hub_streznik.MESH
