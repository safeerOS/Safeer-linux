"""Prejem datotek iz Safeer Linka na tem racunalniku: kdaj brez vprasanja, kdaj z vprasanjem, in obvestilo o prejetem.

Lastnik, 18. 10. 2026 (»pri Safeer Linku pogresam lazje posiljanje datotek med napravami«):
  - od naprave iz OZJEGA kroga zaupanja tega racunalnika (core/link_dostop.prejem_brez_vprasanja) gre datoteka brez
    vprasanja v mapo prenosov (XDG: na slovenskem namizju »Prejemi«);
  - od druge naprave v Safeer Linku (sirsi krog) najprej vprasamo: obvestilo »… ti posilja datoteke« z gumboma Sprejmi
    in Zavrni. Odgovor velja za vse datoteke iste posiljke (cela mapa pride kot vec sporocil share.file);
  - o prejetem obvesti eno obvestilo na posiljatelja (ne eno na datoteko) z gumboma »Odpri« in »Pokazi v mapi«.

Prej je vsaka prejeta datoteka - od kogarkoli v Linku - odprla svoje modalno okno »V redu« (izmerjeno v kodi
18. 10. 2026: _obvesti -> _vprasaj), pri poslani mapi s 50 datotekami 50 oken. Napake gredo v dnevnik (stderr), ne v
okno (lastnik, 18. 10. 2026).

Brez GTK in brez omrezja: prevzem, obvestila in odpiranje dobi od klicatelja, zato je preizkusljiv sam.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

#: Datoteka pocaka na sredisci eno uro (link_hub_streznik, PUT /cast/file); ponudbo drzimo malo manj.
PONUDBA_VELJA_S = 50 * 60.0
#: Odgovor (Sprejmi/Zavrni) velja tudi za datoteke iste posiljke, ki pridejo za njim (poslana mapa), dokler prihajajo.
ODGOVOR_VELJA_S = 120.0
#: Prejete datoteke istega posiljatelja v tem razmiku gredo v isto obvestilo (»Prejetih datotek: 12«).
ZBIRKA_S = 90.0
#: Najvec cakajocih datotek na posiljatelja (ena poslana mapa jih ima lahko vec tisoc - link_posiljanje.NAJVEC_DATOTEK).
NAJVEC_CAKAJOCIH = 5000
#: Isto obvestilo (stevec datotek) najvec enkrat na toliko sekund; zadnje stanje pride z zamikom. Mapa s 1000 datotekami
#: bi sicer streznik obvestil zamenjal 1000-krat v nekaj sekundah.
OBVESTILO_RAZMIK_S = 1.0

BESEDILA = {
    "sl": {"prejeto_naslov": "Prejeto od {od}", "prejeto_ena": "{ime} je v mapi {mapa}",
           "prejeto_vec": "Prejetih datotek: {n} · mapa {mapa}", "odpri": "Odpri", "odpri_mapo": "Odpri mapo",
           "pokazi": "Pokaži v mapi", "ponudba_naslov": "{od} ti pošilja datoteke",
           "ponudba_ena": "{ime} ({velikost}). Naprava ni v tvojem ožjem krogu zaupanja.",
           "ponudba_vec": "Datotek: {n} ({velikost}), prva je {ime}. Naprava ni v tvojem ožjem krogu zaupanja.",
           "sprejmi": "Sprejmi", "zavrni": "Zavrni"},
    "en": {"prejeto_naslov": "Received from {od}", "prejeto_ena": "{ime} is in {mapa}",
           "prejeto_vec": "Files received: {n} · folder {mapa}", "odpri": "Open", "odpri_mapo": "Open folder",
           "pokazi": "Show in folder", "ponudba_naslov": "{od} wants to send you files",
           "ponudba_ena": "{ime} ({velikost}). This device is not in your inner circle of trust.",
           "ponudba_vec": "Files: {n} ({velikost}), the first is {ime}. This device is not in your inner circle of trust.",
           "sprejmi": "Accept", "zavrni": "Decline"},
    "de": {"prejeto_naslov": "Empfangen von {od}", "prejeto_ena": "{ime} liegt in {mapa}",
           "prejeto_vec": "Empfangene Dateien: {n} · Ordner {mapa}", "odpri": "Öffnen", "odpri_mapo": "Ordner öffnen",
           "pokazi": "Im Ordner zeigen", "ponudba_naslov": "{od} möchte dir Dateien senden",
           "ponudba_ena": "{ime} ({velikost}). Dieses Gerät ist nicht in deinem engeren Vertrauenskreis.",
           "ponudba_vec": "Dateien: {n} ({velikost}), die erste ist {ime}. Dieses Gerät ist nicht in deinem engeren "
                          "Vertrauenskreis.",
           "sprejmi": "Annehmen", "zavrni": "Ablehnen"},
    "es": {"prejeto_naslov": "Recibido de {od}", "prejeto_ena": "{ime} está en {mapa}",
           "prejeto_vec": "Archivos recibidos: {n} · carpeta {mapa}", "odpri": "Abrir", "odpri_mapo": "Abrir carpeta",
           "pokazi": "Mostrar en la carpeta", "ponudba_naslov": "{od} quiere enviarte archivos",
           "ponudba_ena": "{ime} ({velikost}). Este dispositivo no está en tu círculo de confianza cercano.",
           "ponudba_vec": "Archivos: {n} ({velikost}), el primero es {ime}. Este dispositivo no está en tu círculo de "
                          "confianza cercano.",
           "sprejmi": "Aceptar", "zavrni": "Rechazar"},
    "fr": {"prejeto_naslov": "Reçu de {od}", "prejeto_ena": "{ime} se trouve dans {mapa}",
           "prejeto_vec": "Fichiers reçus : {n} · dossier {mapa}", "odpri": "Ouvrir", "odpri_mapo": "Ouvrir le dossier",
           "pokazi": "Afficher dans le dossier", "ponudba_naslov": "{od} veut t'envoyer des fichiers",
           "ponudba_ena": "{ime} ({velikost}). Cet appareil n'est pas dans ton cercle de confiance proche.",
           "ponudba_vec": "Fichiers : {n} ({velikost}), le premier est {ime}. Cet appareil n'est pas dans ton cercle de "
                          "confiance proche.",
           "sprejmi": "Accepter", "zavrni": "Refuser"},
    "it": {"prejeto_naslov": "Ricevuto da {od}", "prejeto_ena": "{ime} è in {mapa}",
           "prejeto_vec": "File ricevuti: {n} · cartella {mapa}", "odpri": "Apri", "odpri_mapo": "Apri cartella",
           "pokazi": "Mostra nella cartella", "ponudba_naslov": "{od} vuole inviarti dei file",
           "ponudba_ena": "{ime} ({velikost}). Questo dispositivo non è nella tua cerchia ristretta di fiducia.",
           "ponudba_vec": "File: {n} ({velikost}), il primo è {ime}. Questo dispositivo non è nella tua cerchia ristretta "
                          "di fiducia.",
           "sprejmi": "Accetta", "zavrni": "Rifiuta"},
}


def besedilo(jezik: str, kljuc: str, **polja) -> str:
    slovar = BESEDILA.get(str(jezik or "")[:2].lower()) or BESEDILA["en"]
    return (slovar.get(kljuc) or BESEDILA["en"][kljuc]).format(**polja)


def velikost(bajtov: int, jezik: str = "sl") -> str:
    """12,3 MB (decimalna vejica razen v anglescini)."""
    try:
        b = max(0, int(bajtov))
    except (TypeError, ValueError):
        b = 0
    for enota, meja in (("GB", 1e9), ("MB", 1e6), ("kB", 1e3)):
        if b >= meja:
            niz = ("%.1f" % (b / meja)).rstrip("0").rstrip(".")
            return (niz if str(jezik).startswith("en") else niz.replace(".", ",")) + " " + enota
    return "%d B" % b


def _ident(posiljatelj: str, vrsta: str) -> str:
    """Stalen id obvestila na posiljatelja (novo obvestilo istega posiljatelja zamenja starega); brez oznake v besedilu."""
    return "safeer-%s-%s" % (vrsta, hashlib.sha256(str(posiljatelj or "").encode("utf-8")).hexdigest()[:12])


class _Ponudba:
    def __init__(self, od: str) -> None:
        self.od = od
        self.datoteke: List[dict] = []
        self.odgovor = ""            # "" | "sprejeto" | "zavrnjeno"
        self.cas = 0.0               # zadnja prispela datoteka ali odgovor


class _Zbirka:
    def __init__(self) -> None:
        self.poti: List[str] = []
        self.korenine: List[str] = []    # vrhnja mapa vsake poslane mape (dir) ali "" za samo datoteko
        self.cas = 0.0


Gumb = Tuple[str, str, Callable[[], None]]


class Prejem:
    def __init__(self, prevzemi: Callable[[dict], Tuple[Optional[str], str]],
                 obvesti: Callable[..., object],
                 brez_vprasanja: Callable[[str, Optional[str]], bool],
                 odpri: Callable[[str], object], pokazi: Callable[[str], object],
                 jezik: Callable[[], str] = lambda: "sl",
                 umakni: Callable[[str], object] = lambda ident: None,
                 v_ozadju: Optional[Callable[[Callable[[], None]], object]] = None,
                 ob_prejemu: Optional[Callable[[str, str], None]] = None,
                 ura: Callable[[], float] = time.monotonic) -> None:
        """`prevzemi(tovor)` -> (pot, razlog): prenos s sredisca (klice se v delovni niti). `obvesti(ident, naslov,
        besedilo, gumbi=[(kljuc, napis, klic)], privzeto=klic)`: namizno obvestilo. `ob_prejemu(od, pot)`: za stran
        Linka (»Prejeta datoteka … v mapi …«)."""
        self._prevzemi = prevzemi
        self._obvesti = obvesti
        self._brez_vprasanja = brez_vprasanja
        self._odpri = odpri
        self._pokazi = pokazi
        self._jezik = jezik
        self._umakni = umakni
        self._v_ozadju = v_ozadju or (lambda f: threading.Thread(target=f, name="safeer-prejem", daemon=True).start())
        self._ob_prejemu = ob_prejemu
        self._ura = ura
        self._zaklep = threading.Lock()
        self._ponudbe: Dict[str, _Ponudba] = {}
        self._zbirke: Dict[str, _Zbirka] = {}
        #: ident -> [cas zadnjega obvestila, cakajoce (args, kw) ali None, casovnik]
        self._omejitev: Dict[str, list] = {}

    def _obvesti_omejeno(self, ident: str, *args, **kw) -> None:
        """Obvestilo z id `ident` najvec enkrat na OBVESTILO_RAZMIK_S; vmesna se zdruzijo v zadnje (z zamikom)."""
        zdaj = time.monotonic()
        with self._zaklep:
            z = self._omejitev.setdefault(ident, [0.0, None, None])
            if zdaj - z[0] >= OBVESTILO_RAZMIK_S and z[2] is None:
                z[0], z[1] = zdaj, None
                takoj = True
            else:
                z[1] = (args, kw)
                takoj = False
                if z[2] is None:
                    z[2] = threading.Timer(max(0.0, OBVESTILO_RAZMIK_S - (zdaj - z[0])), self._poslji_cakajoce, (ident,))
                    z[2].daemon = True
                    z[2].start()
            if len(self._omejitev) > 256:
                for k in [k for k, v in self._omejitev.items() if v[2] is None][:64]:
                    self._omejitev.pop(k, None)
        if takoj:
            self._obvesti(ident, *args, **kw)

    def _poslji_cakajoce(self, ident: str) -> None:
        with self._zaklep:
            z = self._omejitev.get(ident)
            if z is None:
                return
            cakajoce, z[1], z[2], z[0] = z[1], None, None, time.monotonic()
        if cakajoce is not None:
            self._obvesti(ident, *cakajoce[0], **cakajoce[1])

    def _preklici_omejeno(self, ident: str) -> None:
        with self._zaklep:
            z = self._omejitev.pop(ident, None)
        if z is not None and z[2] is not None:
            z[2].cancel()

    def _jez(self) -> str:
        try:
            return str(self._jezik() or "sl")
        except Exception:  # noqa: BLE001
            return "sl"

    def _t(self, kljuc: str, **polja) -> str:
        return besedilo(self._jez(), kljuc, **polja)

    # ------------------------------------------------------------------ prispela datoteka (share.file)
    def prispela(self, posiljatelj: str, od: str, tovor: dict, zascita: Optional[str] = None) -> str:
        """Sredisce je napovedalo datoteko. Vrne, kaj se je zgodilo: "prenos" | "vprasano" | "zavrnjeno" | "prezrto".
        Klice se iz delovne niti; prenos tece v njej."""
        if not isinstance(tovor, dict) or not str(tovor.get("path") or ""):
            return "prezrto"
        od = str(od or posiljatelj or "")
        try:
            zaupa = bool(self._brez_vprasanja(posiljatelj, zascita))
        except Exception:  # noqa: BLE001 - ob dvomu vprasamo
            zaupa = False
        if zaupa:
            self._prenesi(posiljatelj, od, tovor)
            return "prenos"
        zdaj = self._ura()
        with self._zaklep:
            self._pocisti(zdaj)
            ponudba = self._ponudbe.get(posiljatelj)
            if ponudba is not None and ponudba.odgovor and zdaj - ponudba.cas <= ODGOVOR_VELJA_S:
                ponudba.cas = zdaj
                odgovor = ponudba.odgovor
            else:
                if ponudba is None or ponudba.odgovor:
                    ponudba = self._ponudbe[posiljatelj] = _Ponudba(od)
                if len(ponudba.datoteke) < NAJVEC_CAKAJOCIH:
                    ponudba.datoteke.append(dict(tovor))
                ponudba.cas = zdaj
                odgovor = ""
                kopija = list(ponudba.datoteke)
        if odgovor == "sprejeto":
            self._prenesi(posiljatelj, od, tovor)
            return "prenos"
        if odgovor == "zavrnjeno":
            print("[SafeerLink] datoteka od %s zavrnjena (posiljka je bila zavrnjena)" % od, flush=True)
            return "zavrnjeno"
        self._vprasaj(posiljatelj, od, kopija)
        return "vprasano"

    def _pocisti(self, zdaj: float) -> None:
        for k in [k for k, p in self._ponudbe.items()
                  if zdaj - p.cas > (ODGOVOR_VELJA_S if p.odgovor else PONUDBA_VELJA_S)]:
            self._ponudbe.pop(k, None)
        for k in [k for k, z in self._zbirke.items() if zdaj - z.cas > ZBIRKA_S]:
            self._zbirke.pop(k, None)

    def _vprasaj(self, posiljatelj: str, od: str, datoteke: List[dict]) -> None:
        jezik_velikost = self._jez()
        skupaj = sum(int(d.get("size") or 0) for d in datoteke if str(d.get("size") or "0").isdigit())
        prva = os.path.basename(str(datoteke[0].get("name") or "")) if datoteke else ""
        if len(datoteke) == 1:
            telo = self._t("ponudba_ena", ime=prva, velikost=velikost(skupaj, jezik_velikost))
        else:
            telo = self._t("ponudba_vec", n=len(datoteke), ime=prva, velikost=velikost(skupaj, jezik_velikost))
        # Varna izbira prva (levo, prva za tipkovnico in daljinec - core/link_fokus), klik na obvestilo ne sprejme nicesar
        # (privzeto=None): datoteke naprave zunaj ozjega kroga sprejme samo izrecen pritisk na »Sprejmi«.
        self._obvesti_omejeno(_ident(posiljatelj, "ponudba"), self._t("ponudba_naslov", od=od), telo,
                              gumbi=[("zavrni", self._t("zavrni"), lambda: self.odgovori(posiljatelj, False)),
                                     ("sprejmi", self._t("sprejmi"), lambda: self.odgovori(posiljatelj, True))],
                              privzeto=None, prioriteta="high")

    def odgovori(self, posiljatelj: str, sprejmi: bool) -> int:
        """Uporabnik je pritisnil Sprejmi ali Zavrni (samo gumb obvestila - nic iz sporocila). Vrne stevilo datotek."""
        with self._zaklep:
            ponudba = self._ponudbe.get(posiljatelj)
            if ponudba is None or ponudba.odgovor:
                return 0
            ponudba.odgovor = "sprejeto" if sprejmi else "zavrnjeno"
            ponudba.cas = self._ura()
            datoteke, ponudba.datoteke = ponudba.datoteke, []
            od = ponudba.od
        self._preklici_omejeno(_ident(posiljatelj, "ponudba"))
        try:
            self._umakni(_ident(posiljatelj, "ponudba"))
        except Exception:  # noqa: BLE001
            pass
        if not sprejmi:
            print("[SafeerLink] uporabnik je zavrnil %d datotek od %s" % (len(datoteke), od), flush=True)
            return len(datoteke)

        def vse() -> None:
            for tovor in datoteke:
                self._prenesi(posiljatelj, od, tovor)
        self._v_ozadju(vse)
        return len(datoteke)

    # ------------------------------------------------------------------ prenos in obvestilo o prejetem
    def _prenesi(self, posiljatelj: str, od: str, tovor: dict) -> Optional[str]:
        try:
            pot, razlog = self._prevzemi(tovor)
        except Exception as e:  # noqa: BLE001
            pot, razlog = None, str(e) or type(e).__name__
        if not pot:
            # Brez okna z napako (lastnik, 18. 10. 2026): v dnevnik.
            print("[SafeerLink] datoteke %s od %s ni bilo mogoce prevzeti: %s"
                  % (os.path.basename(str(tovor.get("name") or "")), od, razlog), flush=True)
            return None
        if self._ob_prejemu is not None:
            try:
                self._ob_prejemu(od, pot)
            except Exception:  # noqa: BLE001
                pass
        self._zabelezi_prejeto(posiljatelj, od, pot, str(tovor.get("dir") or ""))
        return pot

    @staticmethod
    def _korenina(pot: str, podmapa: str) -> str:
        """Vrhnja prejeta mapa pri poslani mapi: pot do prve ravni `dir` (Prejemi/Pocitnice), sicer ""."""
        deli = [d for d in str(podmapa or "").replace("\\", "/").split("/") if d and d not in (".", "..")]
        if not deli:
            return ""
        mapa = os.path.dirname(pot)
        for _ in range(len(deli) - 1):
            mapa = os.path.dirname(mapa)
        return mapa

    def _zabelezi_prejeto(self, posiljatelj: str, od: str, pot: str, podmapa: str) -> None:
        zdaj = self._ura()
        with self._zaklep:
            z = self._zbirke.get(posiljatelj)
            if z is None or zdaj - z.cas > ZBIRKA_S:
                z = self._zbirke[posiljatelj] = _Zbirka()
            z.poti.append(pot)
            z.korenine.append(self._korenina(pot, podmapa))
            z.cas = zdaj
            poti, korenine = list(z.poti), list(z.korenine)
        naslov = self._t("prejeto_naslov", od=od)
        gumbi: List[Gumb] = []
        mape = sorted({k for k in korenine if k})
        if len(poti) == 1:
            telo = self._t("prejeto_ena", ime=os.path.basename(pot), mapa=os.path.dirname(pot))
            gumbi = [("odpri", self._t("odpri"), lambda: self._odpri(pot)),
                     ("pokazi", self._t("pokazi"), lambda: self._pokazi(pot))]
            privzeto = lambda: self._odpri(pot)  # noqa: E731
        else:
            try:
                skupna = os.path.commonpath([os.path.dirname(p) for p in poti])
            except ValueError:
                skupna = os.path.dirname(pot)
            if len(mape) == 1 and all(k == mape[0] for k in korenine):
                # Ena poslana mapa: Odpri jo odpre, Pokazi v mapi jo pokaze v mapi, kjer je.
                vrh = mape[0]
                telo = self._t("prejeto_vec", n=len(poti), mapa=vrh)
                gumbi = [("odpri", self._t("odpri_mapo"), lambda: self._odpri(vrh)),
                         ("pokazi", self._t("pokazi"), lambda: self._pokazi(vrh))]
                privzeto = lambda: self._odpri(vrh)  # noqa: E731
            else:
                prva = poti[0]
                telo = self._t("prejeto_vec", n=len(poti), mapa=skupna)
                gumbi = [("pokazi", self._t("pokazi"), lambda: self._pokazi(prva))]
                privzeto = lambda: self._pokazi(prva)  # noqa: E731
        self._obvesti_omejeno(_ident(posiljatelj, "prejem"), naslov, telo, gumbi=gumbi, privzeto=privzeto,
                              prioriteta="normal")


__all__ = ["Prejem", "BESEDILA", "besedilo", "velikost"]
