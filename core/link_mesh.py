"""Link Mesh (docs/LINK-MESH.md): nas Hub se sam poveze s Hubi drugih naprav iz kroga zaupanja.

Hub na tej napravi tece vedno. Ta modul poisce druge Hube (mDNS), preveri, da potrdilo nosi
kljuc clana kroga, se prijavi s podpisom nasega kljuca in odpre **sosednjo povezavo**. Od tam naprej
vse dela Hub.obdelaj_soseda: izmenjava lokalnih naprav, usmerjanje, krog.

Global Link: kadar soseda neposredno ni (naprava je zunaj doma), ga poklicemo od zunaj: najprej neposredno na javni
naslov njegovega doma, ce ga je sosed objavil in preveril (core/link_neposredno.py, INTERNET_DIRECT), sicer prek
link.safeer.si (SAFEER_RELAY). Rele prenasa samo sifrirane bajte; TLS s kljucem iz kroga in prijava s podpisom
ostaneta enaka kot v LAN. Nas Hub se na releju tudi sam objavi (AgentHuba), da ga clani kroga dosezejo od zunaj.

Da nastane za vsak par ena povezava, prvi klice manjsi id; vecji pocaka in klice sam sele, ce ga
manjsi dolgo ne doseze (npr. pozarni zid na eni strani). Ce vseeno nastaneta dve, Hub obdrzi tisto,
ki jo je odprl manjsi id (Hub.dodaj_soseda).
"""

from __future__ import annotations

import collections
import json
import os
import threading
import time
from typing import Callable, Dict, List, Optional

from core import link_hub, link_krog, link_pot, link_tls, link_vticnik

#: Kako pogosto iscemo sosede in kdaj vecji id klice sam.
ISCI_VSAKIH_S = 15.0
VECJI_CAKA_S = 40.0
#: Srcni utrip sosednje povezave (streznik na drugi strani pinga sam; to je nasa stran).
UTRIP_S = 10.0
#: Po izgubi soseda poskusimo znova hitro (on se je morda le znova zagnal).
PONOVNO_PO_S = 2.0
#: Vrata Huba, kadar naslov soseda poznamo samo iz dohodne povezave (IP brez oglasa mDNS).
PRIVZETA_VRATA = 8990
#: Zapomnjeni naslovi sosedov: za clane kroga brez stevilske meje (lastnik, 18. 10. 2026: prej 32 - v podjetju bi
#: sredisca izgubljala naslove drugih in jih iskala znova); naslove iz oglasov mDNS, ki jih lahko objavi kdorkoli v
#: omrezju (ne clan kroga), samo do te meje.
NAJVEC_ZNANIH = 32
#: Najvec cakajocih sporocil na sosednjo povezavo, preden jo zapremo (sosed ne bere).
NAJVEC_V_VRSTI = 512
#: Po toliko zaporednih neuspelih neposrednih klicih soseda poskusimo prek releja (Global Link).
RELE_PO_NEUSPEHIH = 2
#: Premor po neuspelem klicu prek releja (raste do NAJDALJSI_PREMOR_RELEJA_S): varuje dnevno kvoto releja.
PREMOR_RELEJA_S = 60.0
NAJDALJSI_PREMOR_RELEJA_S = 600.0
#: Meritev poti dohodnih sosednjih povezav (link_ws.Povezava.izmeri): najvec tako pogosto v domacem omrezju in prek
#: releja. Odhodne povezave merijo v svojem utripu (UTRIP_S).
IZMERI_LAN_S = 30.0
IZMERI_RELE_S = 60.0
#: Kako pogosto zapisemo meritve poti sosedov (vrstica na soseda v dnevnik in mesh-poti.json).
POROCILO_POTI_S = 300.0

#: En agent Global Linka na proces (vec MeshPovezovalcev bi se na releju izrinjalo); vrata trenutnega Huba.
_agent = None
_agent_vrata: list = [None]
_agent_zaklep = threading.Lock()


class OdhodnaSosednja:
    """Povezava, ki smo jo odprli mi. Pise v svoji niti, da pocasen sosed ne ustavi nasega Huba."""

    def __init__(self, ws: "link_hub.WsOdjemalec", naslov: str) -> None:
        self.ws = ws
        self.naslov = naslov
        self.podatki: dict = {}
        self._vrsta: collections.deque = collections.deque()
        self._ima = threading.Event()
        self._zaprta = False
        #: Meritev poti do soseda (zamik, nihanje, izgube) iz srcnega utripa. Samo opazovanje: zaradi nje
        #: povezave ne zapremo (to je sele 4. faza).
        # Zanka je lahko rele ali neposredna pot od zunaj: razlikuje ju oznaka krajevnih vrat (core/link_neposredno).
        self.meritev = link_pot.MeritevPoti(link_pot.pot_vticnika(naslov, getattr(ws, "vticnik", None), "getsockname"))
        try:
            ws.ob_pongu = self.meritev.pong
        except Exception:  # noqa: BLE001 - odjemalec brez tega (stari, lazni) ostane brez meritve
            pass
        threading.Thread(target=self._pisi, name="safeer-mesh-pisec", daemon=True).start()

    def poslji(self, besedilo: str) -> bool:
        if self._zaprta:
            return False
        if len(self._vrsta) >= NAJVEC_V_VRSTI:
            print("[SafeerLink] mesh: sosed %s ne bere (%d sporocil v vrsti) - povezavo zapiram" % (self.naslov, len(self._vrsta)),
                  flush=True)
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
                if not self._zaprta and not self._utrip():
                    self.zapri()
                continue
            while self._vrsta and not self._zaprta:
                besedilo = self._vrsta.popleft()
                try:
                    self.ws.poslji(besedilo)
                except Exception:
                    self.zapri()
                    return

    def _utrip(self) -> bool:
        """Srcni utrip ob mirovanju (kot doslej), ping pa nosi zaporedno stevilko in cas (link_pot.paket): sosed
        ga vrne v pongu in tako dobimo zamik poti. Vrne False, ce povezave ni vec."""
        tovor = b""
        try:
            self.meritev.preveri()
            self.meritev.tcp(link_vticnik.tcp_info(getattr(self.ws, "vticnik", None)))
            tovor = self.meritev.sonda(zaseden=bool(self._vrsta))
        except Exception:  # noqa: BLE001 - brez meritve gre utrip kot prej
            pass
        return self.ws.ping(tovor)

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
                 poisci: Optional[Callable[[], List[dict]]] = None, pot_znanih: str = "",
                 vrata: Optional[Callable[[], int]] = None) -> None:
        self.hub = hub
        self.nas_id = nas_id
        self.ime = ime
        self.poisci = poisci or (lambda: link_hub.poisci_hube_mdns(2.0))
        self._klicem: set = set()
        self._prvic_videni: Dict[str, float] = {}
        #: Sosed, ki nas je zavrnil: id -> (do kdaj ga ne klicemo, zadnji premor). Premor raste do 10 min.
        self._zavrnjeni: Dict[str, tuple] = {}
        self._ustavljen = threading.Event()
        self._zbudi = threading.Event()
        self._zaklep = threading.Lock()
        self._nit: Optional[threading.Thread] = None
        #: Zapomnjeni naslovi sosedov (id -> oglas): za naprave, ki jih mDNS ne vidi (pozarni zid,
        #: izolacija), in za hiter ponovni priklop po ponovnem zagonu.
        self._pot_znanih = pot_znanih
        self._znani: Dict[str, dict] = self._nalozi_znane()
        #: Sosedje iz prejsnjega teka: v prvem krogu po zagonu jih poklicemo sami, tudi ce imajo manjsi id. Sosed za
        #: nas ponovni zagon ne ve in nas najde sele v svojem naslednjem krogu iskanja (izmerjeno 5. 10. 2026:
        #: racunalnik je bil po zagonu programa v Safeer Linku cez 26 in cez 51 s, njegov Hub pa je tekel ze po 10 s).
        #: Ce medtem poklice tudi sosed, Hub obdrzi povezavo, ki jo je odprl manjsi id (dodaj_soseda).
        self._po_zagonu: set = set(self._znani)
        #: Global Link: vrata nasega Huba (za agenta), zaporedni neuspehi neposrednih klicev in releji.
        self._vrata = vrata
        self._neuspehi: Dict[str, int] = {}
        self._premor_releja: Dict[str, tuple] = {}
        self._releji: Dict[str, object] = {}
        #: Sosedje, povezani prek releja, do katerih je na voljo neposredna pot od zunaj (kandidati, en krog).
        self._nadgradi: set = set()
        #: Meritve poti: kdaj je bila katera dohodna povezava nazadnje izmerjena (id -> (povezava, cas)) in kam ter
        #: kdaj zapisemo porocilo (mesh-poti.json ob zapomnjenih sosedih; brez te poti samo dnevnik).
        self._izmerjeno: Dict[str, tuple] = {}
        self._pot_poti = os.path.join(os.path.dirname(pot_znanih), "mesh-poti.json") if pot_znanih else ""
        self._porocilo_poti_ob = time.monotonic()
        hub.ob_sosedu = self._ob_sosedu

    def zazeni(self) -> None:
        if self._nit is not None:
            return
        self._nit = threading.Thread(target=self._zanka, name="safeer-mesh", daemon=True)
        self._nit.start()
        self._zazeni_agenta()

    def ustavi(self) -> None:
        self._ustavljen.set()
        self._zbudi.set()
        with _agent_zaklep:
            if _agent_vrata[0] is self._vrata:
                _agent_vrata[0] = None       # agent neha sprejemati kanale, dokler Hub ne tece znova
        for rele in list(self._releji.values()):
            try:
                rele.zapri()
            except Exception:
                pass
        self._releji.clear()

    # -- Global Link

    def _zazeni_agenta(self) -> None:
        """Nas Hub objavi na link.safeer.si, da ga clani kroga dosezejo tudi zunaj doma."""
        global _agent
        if self._vrata is None or not global_link_vklopljen():
            return
        from core import link_rele
        with _agent_zaklep:
            _agent_vrata[0] = self._vrata
            if _agent is not None:
                return

            def vrata() -> int:
                f = _agent_vrata[0]
                try:
                    return int(f()) if f is not None else 0
                except Exception:
                    return 0

            # Neposredna povezava od zunaj (neobvezna nastavitev, privzeto izklopljena): vhod in podpisan oglas, ki ga
            # agent doda v prisotnost - vidijo ga samo clani kroga.
            from core import link_neposredno
            link_neposredno.zazeni_na_sredisci(vrata)
            _agent = link_rele.AgentHuba(vrata=vrata, vklopljen=global_link_vklopljen,
                                         krog_json=lambda: link_krog.krog().json(),
                                         namigi=link_neposredno.namigi_sredisca)
            _agent.zazeni()

    def _rele(self, hid: str):
        """Lokalna vrata do soseda zunaj doma (eno na soseda): vsaka povezava najprej neposredno (ce je sosed objavil
        preverjen javni naslov), nato prek releja - core/link_neposredno.LokalniOdZunaj. None, ce ga ne moremo doseci."""
        from core import link_neposredno, link_rele
        clan = link_krog.krog().clan_za_id(hid)
        try:
            # Rele pozna napravo po id-ju iz njenega kljuca (Hub se lahko oglasa z id-jem s pripono,
            # npr. `n-...-control`); zaupanje da kljuc v potrdilu, ne id.
            cilj = link_rele.id_iz_kljuca(clan["kljuc"]) if clan else ""
        except Exception:
            cilj = ""
        if not cilj or not hid.startswith(cilj):
            return None
        with self._zaklep:
            rele = self._releji.get(hid)
            if rele is None:
                rele = link_neposredno.od_zunaj(cilj)
                self._releji[hid] = rele
        return rele

    def _klici_prek_releja(self, h: dict) -> bool:
        hid = str(h["id"])
        zdaj = time.time()
        if self._premor_releja.get(hid, (0.0, 0.0))[0] > zdaj:
            return False
        rele = self._rele(hid)
        if rele is None:
            return False
        naslov = "wss://127.0.0.1:%d/cast/ws" % rele.vrata
        try:
            dosegljiv = self._odpri(dict(h, naslov=naslov))
        except Exception as e:  # noqa: BLE001
            print("[SafeerLink] mesh: %s prek releja ni dosegljiv (%s)" % (hid, e))
            dosegljiv = False
        if dosegljiv:
            self._premor_releja.pop(hid, None)
            return True
        prej = self._premor_releja.get(hid, (0.0, 0.0))[1]
        premor = min(NAJDALJSI_PREMOR_RELEJA_S, prej * 2 if prej else PREMOR_RELEJA_S)
        self._premor_releja[hid] = (time.time() + premor, premor)
        napaka = getattr(rele, "zadnja_napaka", "")
        print("[SafeerLink] mesh: %s prek releja ni dosegljiv%s; znova cez %d s"
              % (hid, " (%s)" % napaka if napaka else "", premor))
        return False

    def _klici_neposredno(self, h: dict) -> bool:
        hid = str(h["id"])
        with self._zaklep:
            o = self._releji.get(hid)
        vrata = int(getattr(o, "vrata_neposredno", 0) or 0)
        if not vrata:
            return False
        try:
            return self._odpri(dict(h, naslov="wss://127.0.0.1:%d/cast/ws" % vrata))
        except Exception as e:  # noqa: BLE001
            print("[SafeerLink] mesh: %s neposredno od zunaj ni dosegljiv (%s)" % (hid, e))
            return False

    # -- zapomnjeni naslovi

    def _nalozi_znane(self) -> Dict[str, dict]:
        if not self._pot_znanih:
            return {}
        try:
            with open(self._pot_znanih, encoding="utf-8") as d:
                zapis = json.load(d)
            return {str(k): v for k, v in zapis.items() if isinstance(v, dict) and str(v.get("naslov", "")).startswith("wss://")}
        except Exception:
            return {}

    def _shrani_znane(self) -> None:
        if not self._pot_znanih:
            return
        try:
            os.makedirs(os.path.dirname(self._pot_znanih), exist_ok=True)
            zacasna = self._pot_znanih + ".tmp"
            with open(zacasna, "w", encoding="utf-8") as d:
                json.dump(self._znani, d)
            os.replace(zacasna, self._pot_znanih)
        except Exception:
            pass

    def zapomni(self, hid: str, naslov: str) -> None:
        """Naslov soseda si zapomnimo (iz oglasa ali dohodne povezave; IP brez vrat = privzeta vrata)."""
        if not hid or hid == self.nas_id or not naslov or _je_zanka(naslov):
            return               # 127.0.0.1 je rele (Global Link), ne naslov soseda
        if not naslov.startswith("wss://"):
            naslov = "wss://%s:%d/cast/ws" % (naslov, PRIVZETA_VRATA)
        with self._zaklep:
            if self._znani.get(hid, {}).get("naslov") == naslov:
                return
            self._znani[hid] = {"id": hid, "naslov": naslov, "tls": True, "mesh": link_hub_streznik_mesh(),
                                "clan": self._kljuc_clana(hid) is not None}
            while len(self._znani) > NAJVEC_ZNANIH:
                tuj = next((h for h, z in self._znani.items() if not self._je_clan_zapis(h, z)), None)
                if tuj is None:
                    break               # sami clani kroga: brez stevilske meje
                self._znani.pop(tuj)
        self._shrani_znane()

    def _je_clan_zapis(self, hid: str, zapis: dict) -> bool:
        """Ali je zapomnjeni sosed clan kroga (oznaka v zapisu; starejsi zapisi z diska je nimajo)."""
        if "clan" not in zapis:
            zapis["clan"] = self._kljuc_clana(hid) is not None
        return bool(zapis["clan"])

    def naslov_prek_releja(self, hid: str) -> str:
        """Naslov sosednjega sredisca prek Global Linka: krajevni konec releja (wss://127.0.0.1:vrata/cast/ws) ali
        '' (Global Link je izklopljen ali sosed ni clan kroga s kljucem). Skozenj tece TLS do sosedovega
        sredisca; zaupanje da kljuc v njegovem potrdilu, kot pri neposredni povezavi."""
        if not global_link_vklopljen():
            return ""
        rele = self._rele(str(hid or ""))
        return "wss://127.0.0.1:%d/cast/ws" % rele.vrata if rele is not None else ""

    def naslov_soseda(self, hid: str) -> str:
        """Naslov (wss://ip:vrata/cast/ws) sosednjega sredisca, kot ga poznamo iz oglasa ali povezave; '' = ne poznamo."""
        with self._zaklep:
            return str(self._znani.get(str(hid or ""), {}).get("naslov", "") or "")

    def _ob_sosedu(self, hid: str, naslov: str) -> None:
        if naslov:
            # Naslov iz odhodne povezave je pravi (z vrati); iz dohodne je samo IP.
            znan = self._znani.get(hid, {}).get("naslov", "")
            if not (znan and naslov in znan):
                self.zapomni(hid, naslov)
            return
        # Sosed je odsel: hitro poskusimo znova (morda se je le znova zagnal ali zamenjal omrezje).
        threading.Timer(PONOVNO_PO_S, self._zbudi.set).start()

    def _zanka(self) -> None:
        if self._po_zagonu:
            # Znane sosede poklicemo takoj; na oglase mDNS (cakanje in iskanje vzameta 4 s) ne cakamo.
            try:
                self.en_krog(isci=False)
            except Exception as e:  # noqa: BLE001
                print("[SafeerLink] mesh:", e)
        self._ustavljen.wait(2.0)
        while not self._ustavljen.is_set():
            try:
                self.en_krog()
            except Exception as e:  # noqa: BLE001
                print("[SafeerLink] mesh:", e)
            self._zbudi.wait(ISCI_VSAKIH_S)
            self._zbudi.clear()

    def kandidati(self, oglasi: List[dict], zdaj: Optional[float] = None) -> List[dict]:
        """Oglasi Hubov, ki jih moramo zdaj poklicati (brez omrezja - preizkusljivo)."""
        zdaj = time.time() if zdaj is None else zdaj
        povezani = set(self.hub.sosedje())
        # Sosedje, povezani prek Global Linka: ce jih mDNS zdaj oglasa v domacem omrezju, jih poklicemo neposredno -
        # lokalna povezava ima prednost (lastnik, 13. 10. 2026); Hub nato zapre pot prek releja (dodaj_soseda).
        povezave = getattr(self.hub, "povezave_sosedov", None)
        povezave_zdaj = povezave() if callable(povezave) else {}
        prek_releja = {hid for hid, p in povezave_zdaj.items()
                       if _je_zanka(str(getattr(p, "naslov", "") or ""))}
        # Povezani prek releja, do katerih je zdaj na voljo neposredna pot od zunaj: poklicemo jih neposredno (boljsa pot
        # zamenja slabso - Hub.dodaj_soseda), vendar samo neposredno, brez novega kanala releja.
        self._nadgradi = {hid for hid in prek_releja
                          if self._pot_povezave(povezave_zdaj.get(hid)) == "rele" and self._neposredno_na_voljo(hid)}
        izbrani = []
        # Isti Hub je lahko v krogu pod dvema id-jema (npr. `n-x` in `n-x-control`, isti kljuc, isti naslov).
        # Ce smo z njim ze povezani ali ga ze klicemo pod drugim id-jem, ga ne klicemo znova: Hub bi drugo povezavo
        # z istim kljucem zamenjal s prvo in povezava bi nihala vsakih ~10 s (meritev na telefonu, 13. 10. 2026).
        with self._zaklep:
            zasedeni = povezani | set(self._klicem)
        zasedeni_kljuci = {k for k in (self._kljuc_clana(i) for i in zasedeni) if k}
        for h in oglasi:
            hid = str(h.get("id") or "")
            domov = (hid in prek_releja and bool(h.get("mdns")) and not _je_zanka(str(h.get("naslov") or ""))) \
                or hid in self._nadgradi
            if not hid or hid == self.nas_id or not h.get("tls") or (hid in povezani and not domov):
                continue
            if h.get("mesh") != link_hub_streznik_mesh():
                continue            # star Hub: sosednje povezave ne razume
            if hid in brez_neposredne():
                continue            # preizkus poti prek vmesnega vozlisca
            with self._zaklep:
                if hid in self._klicem:
                    continue
                prvic = self._prvic_videni.setdefault(hid, zdaj)
            kljuc = self._kljuc_clana(hid)
            if kljuc is None:
                continue            # ni v krogu zaupanja
            if kljuc and kljuc in zasedeni_kljuci and not domov:
                continue            # isti Hub pod drugim id-jem: ze povezan ali ga ze klicemo
            if self._zavrnjeni.get(hid, (0.0, 0.0))[0] > zdaj:
                continue            # nas je zavrnil; pocakamo
            if hid < self.nas_id and zdaj - prvic < VECJI_CAKA_S and hid not in self._po_zagonu \
                    and hid not in self._nadgradi:
                continue            # manjsi id klice prvi; pocakamo nanj (razen takoj po nasem zagonu in razen
                #                     nadgradnje releja na neposredno pot: do nas zdoma sosed ne more klicati sam)
            izbrani.append(h)
            if kljuc:
                zasedeni_kljuci.add(kljuc)   # isti Hub pod drugim id-jem v tem krogu: enkrat
        return izbrani

    @staticmethod
    def _pot_povezave(p) -> str:
        if p is None:
            return ""
        from core import link_hub_streznik
        return link_hub_streznik._pot_povezave(p)

    def _neposredno_na_voljo(self, hid: str) -> bool:
        with self._zaklep:
            o = self._releji.get(hid)
        f = getattr(o, "neposredno_na_voljo", None)
        try:
            return bool(f()) if callable(f) else False
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _kljuc_clana(hid: str) -> Optional[str]:
        """Kljuc clana kroga za id ("" = clan brez kljuca, None = ni clan ali napaka)."""
        try:
            clan = link_krog.krog().clan_za_id(hid)
        except Exception:  # noqa: BLE001
            return None
        if clan is None:
            return None
        return str((clan.get("kljuc") if isinstance(clan, dict) else getattr(clan, "kljuc", "")) or "")

    def en_krog(self, isci: bool = True) -> None:
        """En krog iskanja in klicanja sosedov. isci=False: samo zapomnjeni sosedje, brez iskanja oglasov mDNS."""
        # Polodprte sosednje povezave (tablica v varcevanju, zamenjano omrezje) zapremo; zaprte poklicemo znova.
        zapri_tihe = getattr(self.hub, "zapri_tihe_sosede", None)
        if callable(zapri_tihe):
            zapri_tihe()
        oglasi = [dict(h, mdns=True) for h in (self.poisci() or []) if isinstance(h, dict)] if isci else []
        for h in oglasi:
            if h.get("mesh") == link_hub_streznik_mesh() and h.get("tls"):
                self.zapomni(str(h.get("id") or ""), str(h.get("naslov") or ""))
        # Kogar mDNS ta hip ne vidi, poskusimo na zapomnjenem naslovu.
        videni = {str(h.get("id") or "") for h in oglasi}
        with self._zaklep:
            oglasi += [dict(z) for hid, z in self._znani.items() if hid not in videni]
        kandidati = self.kandidati(oglasi)
        if kandidati:
            # Stevila sosedov ne omejuje stevilka (lastnik, 18. 10. 2026; prej 16): novega poklicemo, ce ima racunalnik
            # vire za njegovo povezavo (core/link_viri) - sicer v tem krogu nikogar novega, uporabnik izve zakaj.
            from core import link_hub_streznik, link_viri
            razlog = link_viri.preveri(link_hub_streznik.DESKRIPTORJEV_NAPRAVE, link_hub_streznik.POMNILNIK_NAPRAVE)
            if razlog:
                link_viri.zabelezi(razlog, "sosed")
                kandidati = []
        for h in kandidati:
            with self._zaklep:
                self._klicem.add(h["id"])
            threading.Thread(target=self._klici, args=(h,), name="safeer-mesh-klic", daemon=True).start()
        # Prednost po zagonu velja en krog: kogar takrat nismo dosegli, ga caka obicajno pravilo.
        self._po_zagonu.clear()
        try:
            self.izmeri_poti()
        except Exception as e:  # noqa: BLE001 - meritev je samo opazovanje
            print("[SafeerLink] mesh: meritev poti:", e)

    # -- meritve poti (core/link_pot.py; samo opazovanje)

    def izmeri_poti(self, zdaj: Optional[float] = None) -> None:
        """Dohodne sosednje povezave izmerimo sami (ping s tovorom): najvec vsakih IZMERI_LAN_S v domacem omrezju in
        IZMERI_RELE_S prek releja. Odhodne merijo v svojem utripu. Vsakih POROCILO_POTI_S vrstica na soseda v dnevnik
        in mesh-poti.json. Nobene povezave zaradi meritve ne zapremo."""
        zdaj = time.monotonic() if zdaj is None else zdaj
        povezave = getattr(self.hub, "povezave_sosedov", None)
        povezave = povezave() if callable(povezave) else {}
        for hid, p in povezave.items():
            if isinstance(p, OdhodnaSosednja) or not callable(getattr(p, "izmeri", None)):
                continue
            meritev = getattr(p, "meritev", None)
            pot = getattr(meritev, "pot", "") or link_pot.pot_naslova(str(getattr(p, "naslov", "") or ""))
            razmik = IZMERI_RELE_S if pot == "rele" else IZMERI_LAN_S
            prej = self._izmerjeno.get(hid)
            if prej is not None and prej[0] is p and zdaj - prej[1] < razmik:
                continue
            self._izmerjeno[hid] = (p, zdaj)
            try:
                p.izmeri()
            except Exception:  # noqa: BLE001
                pass
        for hid in [h for h in self._izmerjeno if h not in povezave]:
            del self._izmerjeno[hid]
        if zdaj - self._porocilo_poti_ob >= POROCILO_POTI_S:
            self._porocilo_poti_ob = zdaj
            self._porocaj_poti()

    def _porocaj_poti(self) -> None:
        poti = getattr(self.hub, "poti_sosedov", None)
        poti = poti() if callable(poti) else {}
        for hid, s in sorted(poti.items()):
            print("[SafeerLink] mesh: pot do %s: %s, zamik %s ms (najmanj %s, nihanje %s), izgube %s/%s%s"
                  % (hid, s.get("pot"), s.get("rtt_ms"), s.get("min_ms"), s.get("jitter_ms"), s.get("izgube"),
                     s.get("sond"), "" if s.get("odgovoril") else ", se ni odgovoril"), flush=True)
        if not self._pot_poti:
            return
        try:
            os.makedirs(os.path.dirname(self._pot_poti), exist_ok=True)
            zacasna = self._pot_poti + ".tmp"
            with open(zacasna, "w", encoding="utf-8") as d:
                json.dump({"cas": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "sosedje": poti}, d)
            os.replace(zacasna, self._pot_poti)
        except Exception:
            pass

    def _klici(self, h: dict) -> None:
        hid = str(h["id"])
        try:
            dosegljiv = False
            if hid in self._nadgradi and hid in self.hub.sosedje():
                # Povezan prek releja, neposredna pot od zunaj je na voljo: samo neposredno (brez LAN, brez releja).
                self._klici_neposredno(h)
                return
            if hid not in samo_prek_releja():
                try:
                    dosegljiv = self._odpri(h)
                except Exception as e:  # noqa: BLE001
                    print("[SafeerLink] mesh: %s ni dosegljiv (%s)" % (hid, e))
                if dosegljiv:
                    self._neuspehi.pop(hid, None)
                    return
                self._neuspehi[hid] = self._neuspehi.get(hid, 0) + 1
            if self._ustavljen.is_set() or not global_link_vklopljen():
                return
            if hid in self.hub.sosedje():
                return              # ze povezan (prek releja): domov ni uspelo, rele ostane - ne klicemo ga znova
            # Neposredno ga ni (zunaj doma ali za pozarnim zidom): prek link.safeer.si.
            if hid in samo_prek_releja() or self._neuspehi.get(hid, 0) >= RELE_PO_NEUSPEHIH:
                self._klici_prek_releja(h)
        finally:
            with self._zaklep:
                self._klicem.discard(hid)

    def _odpri(self, h: dict) -> bool:
        """Poveze se s sosedom in bere do konca povezave. Vrne True, ce je bil sosed na tem naslovu
        dosegljiv (pravi kljuc in vstopnica) - tudi ce nas je nato zavrnil, ker ze ima drugo povezavo."""
        hid, naslov = str(h["id"]), str(h["naslov"])
        clan = link_krog.krog().clan_za_id(hid)
        if clan is None:
            return False
        # Zaupanje: kljuc v potrdilu mora biti kljuc tega clana v krogu (oglas mDNS ne velja nic).
        odtis, kljuc = link_tls.potrdilo_huba(naslov)
        if not odtis or not kljuc or kljuc != clan.get("kljuc"):
            return False
        vstopnica, _ = link_hub.vzemi_vstopnico_s_podpisom(naslov, self.nas_id, odtis, self.ime)
        if not vstopnica:
            return False
        dosegljiv = True
        locilo = "&" if "?" in naslov else "?"
        ws = link_hub.WsOdjemalec(f"{naslov}{locilo}ticket={vstopnica}", odtis=odtis)
        ws.odpri()
        # Prijava gre prva (sinhrono), sele nato pisec: sosed mora vedeti, da smo Hub, preden
        # dobi karkoli drugega.
        ws.poslji(json.dumps({"id": str(int(time.time() * 1000)), "type": "cast.register",
                              "payload": {"device_id": self.nas_id, "name": self.ime, "role": "hub",
                                          "capabilities": [link_hub_streznik_mesh()], "protocol": "1"}}))
        povezava = OdhodnaSosednja(ws, naslov)
        if not self.hub.dodaj_soseda(hid, povezava, self.nas_id):
            povezava.zapri()
            return dosegljiv
        pot = povezava.meritev.pot if _je_zanka(naslov) else ""
        print("[SafeerLink] mesh: sosed %s (%s%s)" % (hid, naslov, ", Global Link %s" % (
            "neposredno" if pot == "neposredno" else "prek releja") if pot else ""))
        # Premor po zavrnitvi pobrisemo sele, ko nas sosed res sprejme (prvo sporocilo, ki ni zavrnitev);
        # zavrnitev pride sele po odprtju, zato bi ga brisanje tu vedno vrnilo na 30 s.
        self._beri(hid, povezava)
        return dosegljiv

    def _beri(self, hid: str, povezava: OdhodnaSosednja) -> bool:
        """Bere sosedova sporocila do konca povezave; vrne True, ce nas je sosed sprejel."""
        sprejet = False
        try:
            while not povezava.zaprta:
                try:
                    surovo = povezava.ws.prejmi()
                except TimeoutError:
                    continue
                except Exception as e:  # noqa: BLE001
                    if not povezava.zaprta:
                        print("[SafeerLink] mesh: branje s soseda %s se je koncalo: %s: %s" % (hid, type(e).__name__, str(e)[:120]),
                              flush=True)
                    break
                if surovo is None:
                    break
                try:
                    sporocilo = json.loads(surovo)
                except Exception:
                    continue
                if isinstance(sporocilo, dict) and sporocilo.get("type") == "cast.ack" \
                        and sporocilo.get("status") == "rejected":
                    print("[SafeerLink] mesh: %s nas ni sprejel (%s)" % (hid, sporocilo.get("error_code", "")))
                    prej = self._zavrnjeni.get(hid, (0.0, 0.0))[1]
                    premor = min(600.0, prej * 2 if prej else 30.0)
                    self._zavrnjeni[hid] = (time.time() + premor, premor)
                    # Sosed nas ne sprejme (npr. ze ima povezavo, ki jo je odprl on).
                    break
                if not sprejet:
                    sprejet = True
                    self._zavrnjeni.pop(hid, None)
                odgovor = self.hub.obdelaj(povezava, surovo)
                if odgovor:
                    povezava.poslji(odgovor)
        finally:
            povezava.zapri()
            self.hub.odklopi(povezava)
        return sprejet


def sredisce_naprave(hub, mesh, id_naprave: str, potrdilo: Optional[Callable] = None,
                     clan_za_id: Optional[Callable] = None, dosegljiv: Optional[Callable] = None) -> tuple:
    """Sredisce, pri katerem je prijavljena druga naprava, kadar to NI nase (Link Mesh: vsaka naprava ima svoje).

    Datoteke ne grejo cez sosede kot sporocila: pot v `share.file` je relativna na sredisce, ki je datoteko sprejelo.
    Zato jo posiljatelj odda sredisci ciljne naprave, prejemnik pa jo prevzame pri sredisci posiljatelja.

    Soseda, ki ga v tem omrezju ni (naprava je zdoma), dosezemo prek Global Linka: naslov je takrat krajevni konec
    releja do NJEGOVEGA sredisca (`mesh.naslov_prek_releja`); skozenj tece TLS do soseda, zato velja isto zaupanje.

    Vrne ((naslov, odtis), "")  - naprava je pri sosedu, ki ga dosezemo in nosi kljuc clana kroga;
         (None, "")             - naprava je pri nasem sredisci (ali sredisca ne gostimo mi);
         (None, koda)           - "naprava_pri_drugem_srediscu" (dva skoka ali soseda ne poznamo po naslovu),
                                  "sredisce_naprave_ni_dosegljivo" (ni ga v tem omrezju ali kljuc ni iz kroga).
    Zaupanje je isto kot pri sosednji povezavi (MeshPovezovalec._odpri): kljuc v potrdilu mora biti kljuc clana."""
    if hub is None:
        return None, ""
    naprava = hub.najdi(str(id_naprave or ""))
    hid = str(getattr(naprava, "sosed", "") or "") if naprava is not None else ""
    if not hid:
        return None, ""
    if getattr(naprava, "posredno", False) or mesh is None:
        return None, "naprava_pri_drugem_srediscu"
    naslov = mesh.naslov_soseda(hid)
    if naslov and _je_zanka(naslov):
        naslov = ""                     # zapomnjen 127.x ni naslov soseda (star konec releja)
    prek = getattr(mesh, "naslov_prek_releja", None)
    rele = str(prek(hid) or "") if callable(prek) else ""
    if not naslov and not rele:
        return None, "naprava_pri_drugem_srediscu"
    clan = (clan_za_id or link_krog.krog().clan_za_id)(hid)
    if not clan or not clan.get("kljuc"):
        return None, "sredisce_naprave_ni_dosegljivo"
    kandidati = [n for n in (naslov, rele) if n]
    if naslov and rele:
        # Kratek poskus pove, ali je sosed v tem omrezju. Ce ga ni (naprava je zdoma), gremo naravnost prek
        # releja - brez cakanja na rok povezave na naslov, na katerem ga ni.
        if dosegljiv is None:
            dosegljiv = _tcp_dosegljiv if potrdilo is None else (lambda _n: True)
        if not dosegljiv(naslov):
            kandidati = [rele]
    for n in kandidati:
        odtis, kljuc = (potrdilo or link_tls.potrdilo_huba)(n)
        if odtis and kljuc and kljuc == clan.get("kljuc"):
            return (n, odtis), ""
    return None, "sredisce_naprave_ni_dosegljivo"


#: Toliko casa ima sosed v istem omrezju, da sprejme povezavo; kdor ne odgovori, je zdoma (gremo prek releja).
SONDA_SOSEDA_S = 0.7


def _tcp_dosegljiv(naslov: str, rok_s: float = SONDA_SOSEDA_S) -> bool:
    """Kratek poskus povezave TCP na naslov sosednjega sredisca (brez podatkov in brez TLS)."""
    import socket
    from urllib.parse import urlparse
    u = urlparse(naslov)
    try:
        s = socket.create_connection((u.hostname or "", u.port or 443), rok_s)
    except (OSError, ValueError):
        return False
    try:
        s.close()
    except OSError:
        pass
    return True


# ------------------------------------------------------------------ pomoc drugim napravam pri povezavi
#: »Pomagaj drugim napravam v Linku pri povezavi« (pregled 18. 10. 2026). Pomoc je v kodi natanko dvoje (LINK-MESH.md,
#: »Dostava prek vmesnega vozlisca«): nas Hub sosedom predstavi naprave svojih neposrednih sosedov (`relay` v
#: mesh.devices) in sporocilo `mesh.route` z `relay: true` preda naprej (en vmesni skok, samo med clani kroga, vsebina
#: ostane sifrirana do cilja). Brez tega se napravi, ki druga druge ne dosezeta neposredno (pozarni zid, druga podmreza,
#: ena je zdoma), prek te naprave ne vidita. Privzeto vklopljeno; uporabnika vprasamo ob seznanitvi (stran Linka).
#: Na lastno povezavo te naprave nastavitev ne vpliva: njej drugi se vedno pomagajo, ce sami to dovolijo.
DATOTEKA_POMOCI = "link-pomoc.json"
_pomoc_predpomnilnik: dict = {}


def _pot_pomoci() -> str:
    return os.path.join(link_krog._mapa_nastavitev(), DATOTEKA_POMOCI)


def nastavitve_pomoci(pot: Optional[str] = None) -> dict:
    """{"vklopljeno": bool, "vprasano": bool} - privzeto vklopljeno, uporabnik se ni bil vprasan."""
    try:
        with open(pot or _pot_pomoci(), encoding="utf-8") as d:
            v = json.load(d)
    except (OSError, ValueError):
        v = {}
    if not isinstance(v, dict):
        v = {}
    return {"vklopljeno": v.get("vklopljeno") is not False, "vprasano": bool(v.get("vprasano"))}


def shrani_pomoc(vklopljeno: bool, pot: Optional[str] = None) -> dict:
    """Uporabnikova izbira (stran Linka ali vprasanje ob seznanitvi): velja takoj, vprasanje se ne ponovi."""
    pot = pot or _pot_pomoci()
    os.makedirs(os.path.dirname(pot), exist_ok=True)
    zacasna = pot + ".tmp"
    with open(zacasna, "w", encoding="utf-8") as d:
        json.dump({"vklopljeno": bool(vklopljeno), "vprasano": True}, d)
    os.replace(zacasna, pot)
    _pomoc_predpomnilnik.clear()
    return nastavitve_pomoci(pot)


def pomaga_pri_povezavi(pot: Optional[str] = None) -> bool:
    """Ali Hub te naprave pomaga drugim napravam pri povezavi. Bere se ob vsakem seznamu za sosede, zato si vrednost
    zapomnimo do spremembe datoteke (cas spremembe)."""
    pot = pot or _pot_pomoci()
    try:
        kljuc = (pot, os.stat(pot).st_mtime_ns)
    except OSError:
        kljuc = (pot, None)
    if _pomoc_predpomnilnik.get("kljuc") != kljuc:
        _pomoc_predpomnilnik.clear()
        _pomoc_predpomnilnik.update(kljuc=kljuc, vrednost=nastavitve_pomoci(pot)["vklopljeno"])
    return bool(_pomoc_predpomnilnik.get("vrednost", True))


def brez_neposredne() -> set:
    """Samo za preizkus dostave prek vmesnega vozlisca: SAFEER_MESH_BREZ=id1,id2 (brez neposredne povezave)."""
    return {i.strip() for i in os.environ.get("SAFEER_MESH_BREZ", "").split(",") if i.strip()}


def samo_prek_releja() -> set:
    """Samo za preizkus Global Linka doma: SAFEER_MESH_RELE=id1,id2 (te sosede klicemo samo prek releja)."""
    return {i.strip() for i in os.environ.get("SAFEER_MESH_RELE", "").split(",") if i.strip()}


def global_link_vklopljen() -> bool:
    """Global Link (rele link.safeer.si) je privzeto vklopljen; SAFEER_GLOBAL_LINK=0 ga izklopi."""
    return os.environ.get("SAFEER_GLOBAL_LINK", "1").strip() != "0"


def _je_zanka(naslov: str) -> bool:
    """Ali naslov kaze na to napravo (127.x, ::1, localhost) - tam je lokalni konec releja."""
    from urllib.parse import urlparse
    gostitelj = (urlparse(naslov).hostname if "://" in naslov else naslov.strip("[]")) or ""
    return gostitelj == "localhost" or gostitelj == "::1" or gostitelj.startswith("127.")


def link_hub_streznik_mesh() -> str:
    from core import link_hub_streznik
    return link_hub_streznik.MESH
