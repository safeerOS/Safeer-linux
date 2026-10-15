"""Most med razdelkom Sporocila v Safeer OS in jedrom zdruzenih sporocil (core/sporocila)."""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from .sporocila import ponudniki as _ponudniki
from .sporocila.chatwoot import ChatwootAdapter
from .sporocila.email import EmailAdapter, ocisti_geslo
from .sporocila.adapter import varen_streznik
from .sporocila.matrix import MatrixAdapter
from .sporocila.telegram_bot import TelegramBotAdapter
from .sporocila.model import Kanal
from .sporocila.storitev import StoritevSporocil
from . import predogled_datotek, splet_prenosi
from .sporocila import predpomnilnik
from .sporocila import slike as _slike

# Znani ponudniki: IMAP/SMTP streznik in namig za prijavo (vecina zahteva "geslo za aplikacije").
PONUDNIKI = {
    "gmail.com": ("imap.gmail.com", "smtp.gmail.com", "aplikacije"),
    "googlemail.com": ("imap.gmail.com", "smtp.gmail.com", "aplikacije"),
    "yahoo.com": ("imap.mail.yahoo.com", "smtp.mail.yahoo.com", "aplikacije"),
    "icloud.com": ("imap.mail.me.com", "smtp.mail.me.com", "aplikacije"),
    "me.com": ("imap.mail.me.com", "smtp.mail.me.com", "aplikacije"),
    "gmx.net": ("imap.gmx.net", "mail.gmx.net", ""),
    "gmx.com": ("imap.gmx.com", "mail.gmx.com", ""),
    "siol.net": ("imap.siol.net", "mail.siol.net", ""),
    "t-2.net": ("imap.t-2.net", "smtp.t-2.net", ""),
    "outlook.com": ("outlook.office365.com", "smtp.office365.com", "oauth"),
    "hotmail.com": ("outlook.office365.com", "smtp.office365.com", "oauth"),
    "live.com": ("outlook.office365.com", "smtp.office365.com", "oauth"),
}
#: Poizvedba za kanale brez potiska (Chatwoot). E-posta (IMAP IDLE), Matrix in Telegram (dolga poizvedba) sporocilo
#: dobijo v trenutku (core/sporocila/sprotno.py); prej so vsi kanali brali zaporedoma vsakih 120 s.
INTERVAL_S = 30
#: Safeer Chat: sporocila med napravami v Safeer Linku (en pogovor na napravo).
KANAL_LINKA = "safeer-link"
VRSTA_LINKA = "safeer"
NAJVEC_KLEPET = 16 * 1024
NAPAKE_KLEPETA = {
    "ni_povezave": "Safeer Link ni povezan.",
    "ni_controla": "Safeer Control ne teče.",
    "ni_naprave": "Te naprave ni več v Safeer Linku.",
    "meja": "Sporočilo je predolgo.",
    "potek": "Središče Safeer Linka ni odgovorilo.",
}


#: Napake pri prilogah in priponkah: notranja koda -> koda za stran (os.js jo prevede v jezik vmesnika).
NAPAKE_PRILOG = {
    "priloge_prevelike": "priloge_prevelike",
    "prilog_ni": "prilog_ni",
    "priloge_ni_podprto": "priloge_ni_podprto",
    "ni_pisma": "priponka_ni_pisma",
    "ni_povezave": "priponka_ni_povezave",
    "prevelik": "priponka_prevelika",
    "ni_podprto": "priloge_ni_podprto",
    "ni_varno": "priponka_ni_povezave",
    "napaka": "priponka_napaka",
}


def kljuc_priponke(p: dict, indeks: int) -> str:
    """Kljuc priponke znotraj sporocila: stevilka dela IMAP ali zaporedna stevilka (drugi kanali)."""
    return str(p.get("del") or "#%d" % indeks)


def opis_priponke(p: dict, indeks: int) -> dict:
    """Priponka za stran: brez lokalnih poti in zetonov, s kljucem, vrsto predogleda in oznako nevarnosti (en vir)."""
    ime, tip = str(p.get("ime") or "priponka"), str(p.get("tip") or "")
    return {"kljuc": kljuc_priponke(p, indeks), "ime": ime, "tip": tip, "velikost": int(p.get("velikost") or 0),
            "inline": bool(p.get("inline")), "cid": bool(p.get("cid")),
            "predogled": predogled_datotek.vrsta_predogleda(ime, tip),
            "nevarna": predogled_datotek.je_nevarna(ime, tip)}


def mapa_prejemov() -> str:
    """Mapa za prenose po XDG (~/.config/user-dirs.dirs: na slovenskem namizju »Prejemi«), sicer kot v Spletu."""
    dom = os.path.expanduser("~")
    try:
        with open(os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(dom, ".config"), "user-dirs.dirs"),
                  encoding="utf-8") as f:
            for vrstica in f:
                m = re.match(r'\s*XDG_DOWNLOAD_DIR\s*=\s*"(.*)"\s*$', vrstica)
                if m:
                    pot = m.group(1).replace("$HOME", dom)
                    if os.path.isabs(pot) and os.path.isdir(pot) and os.path.realpath(pot) != os.path.realpath(dom):
                        return pot
    except OSError:
        pass
    return splet_prenosi.mapa_prenosov(None)


#: En naslov prejemnika (brez imena, brez vec naslovov in brez novih vrstic - glava To ne sme dobiti vrinjenih glav).
_NASLOV = re.compile(r"[^@\s<>,;\"]+@[^@\s<>,;\"]+\.[^@\s<>,;\"]+")


def _cas_zdaj() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _cas_klepeta(vrednost: str) -> str:
    """Cas posiljatelja v nasi obliki (UTC do sekunde); nerazumljiv cas -> cas prejema."""
    try:
        d = datetime.fromisoformat(str(vrednost).replace("Z", "+00:00"))
        if d.tzinfo is None:
            raise ValueError
        return d.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except (TypeError, ValueError):
        return _cas_zdaj()


#: Poslusalci sprememb neprebranih (kuverta v pultu Safeer OS): klic brez argumentov, iz katerekoli niti. Dogodek
#: namesto periodicnega branja baze (lastnik, 15. 10. 2026: kuverta je prej brala bazo vsakih 30 s).
_poslusalci: List[Callable[[], None]] = []


def ob_spremembi(klic: Callable[[], None]) -> None:
    """Prijava poslusalca: novo sporocilo, prebran pogovor ali koncana sinhronizacija."""
    if klic not in _poslusalci:
        _poslusalci.append(klic)


def _sporoci() -> None:
    for klic in list(_poslusalci):
        try:
            klic()
        except Exception as e:  # noqa: BLE001 - poslusalec ne sme podreti prejema sporocila
            print("[Sporocila] poslusalec:", e, flush=True)


class SporocilaOS:
    #: Osnutke shranjujejo, brisejo in usklajujejo locene niti mostu (safeer_os.py, ozadje): brez zaklepa
    #: branje-sprememba-zapis osnutki.json in IMAP APPEND/brisanje izgubijo, podvojijo ali obudijo osnutek
    #: (pregled 14. 10. 2026). En zaklep za razred: ena datoteka osnutki.json, en primerek na proces.
    _osnutki_klj = threading.RLock()

    def __init__(self, pot=None, zazeni: bool = True):
        self.storitev = StoritevSporocil(pot, interval=INTERVAL_S)
        #: Posiljanje po Linku (nastavi gostitelj): (naprava, besedilo, cas) -> "accepted"/"queued"/koda napake
        self.poslji_klepet: Optional[Callable[[str, str, str], str]] = None
        #: Naprave v Linku, ki znajo klepet (nastavi gostitelj): [{"id", "ime"}]
        self.naprave_klepeta: Optional[Callable[[], List[dict]]] = None
        self.storitev.ob_sinhronizaciji = self._po_sinhronizaciji
        self._samodejno = bool(zazeni)
        self._nalozi()
        if zazeni and self.storitev.adapterji:
            self.storitev.zazeni()

    # ------------------------------------------------------------------ kanali
    def _adapter(self, kid: str, vrsta: str, n: dict, skrivnost: str = ""):
        if vrsta == "email":
            return EmailAdapter(kid, n.get("naslov", ""), n.get("imap", ""), n.get("smtp", ""),
                                int(n.get("imap_vrata") or 993), int(n.get("smtp_vrata") or 465),
                                n.get("uporabnik", ""), skrivnost)
        if vrsta == "chatwoot":
            return ChatwootAdapter(kid, n.get("url", ""), int(n.get("account_id") or 0), skrivnost)
        if vrsta == "matrix":
            return MatrixAdapter(kid, n.get("streznik", ""), skrivnost)
        if vrsta == "telegram_bot":
            return TelegramBotAdapter(kid, skrivnost)
        return None

    def _nalozi(self):
        for r in self.storitev.db.execute("SELECT * FROM kanali").fetchall():
            try:
                a = self._adapter(r["id"], r["vrsta"], json.loads(r["nastavitve"] or "{}"))
            except Exception:
                a = None
            if a is not None:
                self.storitev.adapterji[r["id"]] = a

    @staticmethod
    def privzeta_streznika(naslov: str) -> dict:
        p = _ponudniki.iz_naslova(naslov)
        if p:
            return {"imap": p["imap"], "smtp": p["smtp"], "imap_vrata": p["imap_vrata"], "smtp_vrata": p["smtp_vrata"],
                    "namig": "" if p["geslo"] == "navadno" else p["geslo"], "ponudnik": p["id"]}
        domena = naslov.rsplit("@", 1)[-1].lower().strip()
        imap, smtp, namig = PONUDNIKI.get(domena, ("imap." + domena, "smtp." + domena, ""))
        return {"imap": imap, "smtp": smtp, "imap_vrata": 993, "smtp_vrata": 465, "namig": namig, "ponudnik": "drug"}

    @staticmethod
    def ponudniki() -> dict:
        """Seznam ponudnikov in aplikacij za carovnik »Dodaj kanal«."""
        return _ponudniki.za_vmesnik()

    def dodaj_kanal(self, podatki: dict) -> dict:
        """Doda kanal SAMO, ce se prijava posreci - uporabnik takoj ve, ali je vse prav."""
        vrsta = str(podatki.get("vrsta", ""))
        kid = str(uuid.uuid4())
        if vrsta == "email":
            naslov = str(podatki.get("naslov", "")).strip()
            if "@" not in naslov or "." not in naslov.rsplit("@", 1)[-1]:
                raise ValueError("Vnesi veljaven e-poštni naslov.")
            p = self.privzeta_streznika(naslov)
            izbrani = _ponudniki.po_id(str(podatki.get("ponudnik") or ""))
            if izbrani and izbrani["id"] != "drug":
                p = {"imap": izbrani["imap"], "smtp": izbrani["smtp"], "imap_vrata": izbrani["imap_vrata"], "smtp_vrata": izbrani["smtp_vrata"],
                     "namig": "" if izbrani["geslo"] == "navadno" else izbrani["geslo"], "ponudnik": izbrani["id"]}
            if p["namig"] == "oauth":
                raise ValueError("Outlook in Hotmail ne dovolita več prijave z geslom (samo Microsoftova prijava). Ta vrsta prijave pride v naslednji različici.")
            geslo = ocisti_geslo(str(podatki.get("geslo") or ""), brez_presledkov=p["namig"] == "aplikacije")
            if not geslo:
                raise ValueError("Vnesi geslo.")
            nastavitve = {"naslov": naslov, "uporabnik": str(podatki.get("uporabnik") or naslov),
                          "imap": str(podatki.get("imap") or p["imap"]), "smtp": str(podatki.get("smtp") or p["smtp"]),
                          "imap_vrata": int(podatki.get("imap_vrata") or p.get("imap_vrata") or 993),
                          "smtp_vrata": int(podatki.get("smtp_vrata") or p.get("smtp_vrata") or 465)}
            for kljuc in ("imap", "smtp"):   # "gostitelj:vrata" iz rocnega vnosa
                g, _, vr = nastavitve[kljuc].rpartition(":")
                if g and vr.isdigit():
                    nastavitve[kljuc], nastavitve[kljuc + "_vrata"] = g, int(vr)
            if p.get("ponudnik"):
                nastavitve["ponudnik"] = p["ponudnik"]
            a = self._adapter(kid, "email", nastavitve, geslo)
            try:
                a.povezi()
            except Exception as e:
                ime, napaka_povezave = type(e).__name__, e
                # Nekateri ponudniki hocejo uporabnisko ime brez domene: poskusimo se tako, preden obupamo.
                brez = naslov.rsplit("@", 1)[0]
                if ime == "NapakaPrijave" and nastavitve["uporabnik"] == naslov and brez:
                    nastavitve["uporabnik"] = brez
                    a = self._adapter(kid, "email", nastavitve, geslo)
                    try:
                        a.povezi(); ime = ""
                    except Exception as e2:
                        ime, napaka_povezave = type(e2).__name__, e2; nastavitve["uporabnik"] = naslov
                if ime == "NapakaPrijave":
                    namig = " Pri tem ponudniku potrebuješ »geslo za aplikacije« (nastaviš ga v varnostnih nastavitvah računa)." if p["namig"] == "aplikacije" else ""
                    raise ValueError("Prijava ni uspela - preveri naslov in geslo." + namig)
                if ime and isinstance(napaka_povezave, OSError):
                    raise ValueError("Strežnika %s ni mogoče doseči." % nastavitve["imap"])
                if ime:
                    # Ne omrezje: povemo, kaj je streznik odgovoril, namesto zavajajocega »ni mogoce doseci«.
                    raise ValueError("Povezava z %s ni uspela (%s)." % (nastavitve["imap"], ime))
            a.shrani_geslo(geslo)
            ime = naslov
        elif vrsta == "chatwoot":
            nastavitve = {"url": str(podatki.get("url", "")).strip().rstrip("/"), "account_id": int(podatki.get("account_id") or 0)}
            zeton = str(podatki.get("zeton") or "")
            if not nastavitve["url"].startswith("https://") or not nastavitve["account_id"] or not zeton:
                raise ValueError("Vnesi naslov https://, številko računa in žeton Chatwoot.")
            a = self._adapter(kid, "chatwoot", nastavitve, zeton)
            try:
                a.povezi()
            except Exception:
                raise ValueError("Chatwoot ni sprejel povezave - preveri naslov, račun in žeton.")
            a.shrani_zeton(zeton)
            ime = str(podatki.get("ime") or "Chatwoot")
        elif vrsta == "matrix":
            # Lastni API: Matrix (Element, Beeper, Synapse ...) - naslov domacega streznika + dostopni zeton.
            streznik = str(podatki.get("streznik", "")).strip().rstrip("/")
            if streznik and "://" not in streznik:
                streznik = "https://" + streznik
            zeton = str(podatki.get("zeton") or "").strip()
            # http:// le na tem racunalniku (ime tocno localhost ali povratni IP) - sicer gre zeton v cistopisu po mrezi.
            if not varen_streznik(streznik) or not zeton:
                raise ValueError("Vnesi naslov strežnika (https://…) in dostopni žeton.")
            nastavitve = {"streznik": streznik}
            a = self._adapter(kid, "matrix", nastavitve, zeton)
            try:
                a.povezi()
            except Exception as e:
                if type(e).__name__ == "NapakaPrijave":
                    raise ValueError("Matrix žetona ni sprejel - preveri, da je dostopni žeton prepisan v celoti.")
                raise ValueError("Strežnika %s ni mogoče doseči." % streznik)
            a.shrani_zeton(zeton)
            nastavitve["uporabnik"] = a.uporabnik
            ime = str(podatki.get("ime") or a.uporabnik or "Matrix")
        elif vrsta == "telegram_bot":
            # Lastni API: Telegram Bot API - zeton od @BotFather; sporocila ljudi, ki pisejo botu.
            zeton = str(podatki.get("zeton") or "").strip()
            if ":" not in zeton or len(zeton) < 20:
                raise ValueError("Vnesi žeton bota (oblika 123456:ABC…), ki ti ga da @BotFather.")
            nastavitve = {}
            a = self._adapter(kid, "telegram_bot", nastavitve, zeton)
            try:
                a.povezi()
            except Exception as e:
                if type(e).__name__ == "NapakaPrijave":
                    raise ValueError("Telegram žetona ni sprejel - preveri, da je prepisan v celoti.")
                raise ValueError("Telegrama ni mogoče doseči.")
            a.shrani_zeton(zeton)
            uime = (a.bot or {}).get("username", "")
            nastavitve["bot"] = uime
            ime = str(podatki.get("ime") or ("Telegram @" + uime if uime else "Telegram bot"))
        else:
            raise ValueError("Nepodprta vrsta kanala")
        self.storitev.registriraj(Kanal(kid, vrsta, ime, "povezan"), a, nastavitve)
        threading.Thread(target=self._prvic, args=(kid,), daemon=True).start()
        return {"id": kid, "vrsta": vrsta, "ime": ime, "stanje": "povezan"}

    def _prvic(self, kid: str) -> None:
        self.storitev.sinhroniziraj(kid)
        if getattr(self, "_samodejno", False):
            self.storitev.zazeni_kanal(kid)     # od zdaj v realnem casu (nit kanala)

    def nastavi_skrivnost(self, kanal_id: str, skrivnost: str) -> dict:
        """Ponovni vnos gesla/zetona (npr. brez zbirke skrivnosti po ponovnem zagonu)."""
        a = self.storitev.adapterji.get(kanal_id)
        if a is None or not skrivnost:
            raise ValueError("Ni kanala")
        (a.shrani_geslo if hasattr(a, "shrani_geslo") else a.shrani_zeton)(str(skrivnost))
        self.storitev.sinhroniziraj(kanal_id)
        if getattr(self, "_samodejno", False) and kanal_id in self.storitev.delavci():
            self.storitev.zazeni_kanal(kanal_id)     # nit takoj na novo (ne caka zamika po napaki prijave)
        return self.seznam()

    def _po_sinhronizaciji(self) -> None:
        """Nova UIDVALIDITY mape (streznik je mapo na novo ostevilcil): stari vnosi predpomnilnika ne veljajo."""
        for kid, a in list(self.storitev.adapterji.items()):
            uidv = getattr(a, "uidvalidity_priponk", "")
            if uidv:
                try:
                    predpomnilnik.velja(kid, getattr(a, "MAPA_PRIPONK", "INBOX"), uidv)
                except OSError:
                    pass
        _sporoci()

    def odstrani_kanal(self, kanal_id: str) -> dict:
        self.storitev.odstrani_kanal(str(kanal_id))
        predpomnilnik.odstrani_kanal(str(kanal_id))      # priponke odstranjenega racuna ne ostanejo na disku
        return self.seznam()

    # ------------------------------------------------------------------ branje/pisanje
    def seznam(self, kanal: str = "") -> dict:
        skupine = self.storitev.zdruzeni_pogovori(kanal)
        kanali = {k.id: k.slovar() for k in self.storitev.kanali()}
        try:
            smeri = self.storitev.zadnje_smeri()
        except Exception:
            smeri = {}
        try:
            s_priponkami = self.storitev.pogovori_s_priponkami()
        except Exception:
            s_priponkami = set()
        for kid, k in kanali.items():
            # Gumb »Prilozi« samo v kanalih, ki priloge res posljejo (brez nedelujocih gumbov).
            k["priloge"] = "priloge" in getattr(self.storitev.adapterji.get(kid), "zmore", set())
        for s in skupine:
            for p in s["pogovori"]:
                p["kanal"] = kanali.get(p["kanal_id"], {})
                p["zadnji_ven"] = smeri.get((p["kanal_id"], p["id"])) == "ven"
                # Vsebina pogovora se je spremenila brez novega sporocila (celotno besedilo, poslano iz vrste):
                # odprt pogovor se osvezi (os.js uskladiOdprtPogovor).
                p["razlicica"] = self.storitev.razlicica(p["kanal_id"], p["id"])
                p["priponke"] = (p["kanal_id"], p["id"]) in s_priponkami
        return {"kanali": list(kanali.values()), "skupine": skupine, "oznake": self.storitev.vse_oznake(),
                "slike_od": self.slike_od.seznam()}

    # ---- osebe in oznake (uporabnikovo urejanje) ----
    def preimenuj_osebo(self, oseba_id: str, ime: str) -> dict:
        if not self.storitev.graf.preimenuj(str(oseba_id), str(ime)):
            raise ValueError("Oseba ne obstaja.")
        return self.seznam()

    def zdruzi_osebi(self, cilj_id: str, drugi_id: str) -> dict:
        if cilj_id == drugi_id:
            raise ValueError("Izberi drugo osebo.")
        self.storitev.zdruzi_osebi(str(cilj_id), str(drugi_id))
        return self.seznam()

    def razdruzi_osebo(self, oseba_id: str, identiteta) -> dict:
        if not isinstance(identiteta, (list, tuple)) or len(identiteta) != 2:
            raise ValueError("Neveljavna identiteta.")
        self.storitev.razdruzi_osebo(str(oseba_id), (str(identiteta[0]), str(identiteta[1])))
        return self.seznam()

    def nastavi_oznake(self, kanal_id: str, pogovor_id: str, oznake) -> dict:
        self.storitev.nastavi_oznake(str(kanal_id), str(pogovor_id), list(oznake or []))
        return self.seznam()

    def osebe(self) -> list:
        return [o.slovar() for o in self.storitev.graf.vse()]

    def pogovor(self, kanal_id: str, pogovor_id: str) -> list:
        self.storitev.oznaci_prebrano(kanal_id, pogovor_id)
        _sporoci()
        sporocila = self.storitev.sporocila(kanal_id, pogovor_id)
        ids = [s.id for s in sporocila if s.id.startswith("uid:")]
        if ids and getattr(self.storitev.adapterji.get(kanal_id), "vrsta", "") == "email":
            # Dolga pisma (prirezana na 64 KB): celotno besedilo v ozadju, enkrat; dogodek osvezi odprt pogovor.
            threading.Thread(target=self._dopolni, args=(kanal_id, ids), name="safeer-sporocila-celotno",
                             daemon=True).start()
        izid = []
        for s in sporocila:
            d = s.slovar()
            d["priponke"] = [opis_priponke(p, i) for i, p in enumerate(s.priponke or []) if isinstance(p, dict)]
            izid.append(d)
        return izid

    def _dopolni(self, kanal_id: str, ids: list) -> None:
        try:
            self.storitev.dopolni_besedila(kanal_id, ids)
        except Exception as e:  # noqa: BLE001 - brez povezave ostane prirezano besedilo; poskus ob naslednjem odprtju
            print("[Sporocila] celotno besedilo:", type(e).__name__, flush=True)

    def preklici(self, kanal_id: str, pogovor_id: str, sporocilo_id: str) -> list:
        """Neposlano sporocilo (stanje »caka« ali »napaka«) uporabnik preklice; vrne pogovor brez njega."""
        if not self.storitev.preklici_cakajoce(str(kanal_id), str(sporocilo_id)):
            raise ValueError("Sporočilo se že pošilja ali je poslano.")
        return self.pogovor(str(kanal_id), str(pogovor_id))

    def neprebrano_skupaj(self) -> int:
        """Stevilo za kuverto v pultu: iz baze (pravo ze ob zagonu), brez branja celega nabiralnika."""
        return self.storitev.neprebrano_skupaj()

    def zazeni_kanal(self, kanal_id: str) -> dict:
        self.storitev.zazeni_kanal(str(kanal_id))
        return self.seznam()

    def ustavi_kanal(self, kanal_id: str) -> dict:
        self.storitev.ustavi_kanal(str(kanal_id))
        return self.seznam()

    def poslji(self, kanal_id: str, pogovor_id: str, besedilo: str, priloge=None) -> dict:
        besedilo = str(besedilo).strip()
        priloge = self._priloge(kanal_id, priloge)
        if not besedilo and not priloge:
            raise ValueError("Prazno sporočilo")
        if kanal_id == KANAL_LINKA:
            return self._poslji_po_linku(str(pogovor_id), besedilo)
        s = self.storitev.poslji(kanal_id, pogovor_id, besedilo, priloge)
        d = s.slovar()
        d["priponke"] = [opis_priponke(p, i) for i, p in enumerate(s.priponke or []) if isinstance(p, dict)]
        # Brez povezave: sporocilo (s prilogami) caka v odhodni vrsti in odide samo, ko se kanal spet poveze.
        d["caka"] = s.stanje == "caka"
        return d

    def _priloge(self, kanal_id: str, priloge) -> list:
        """Poti prilog s strani -> [{"pot"}]. Priloge zna zdaj poslati e-posta; drug kanal jih jasno zavrne."""
        poti = [str(p.get("pot") if isinstance(p, dict) else p) for p in (priloge or []) if p]
        if not poti:
            return []
        adapter = self.storitev.adapterji.get(str(kanal_id))
        if "priloge" not in getattr(adapter, "zmore", set()):
            raise ValueError(NAPAKE_PRILOG["priloge_ni_podprto"])
        return [{"pot": p} for p in poti[:50]]

    # ------------------------------------------------------------------ novo sporocilo in osnutki
    def novo(self, kanal_id: str, prejemnik: str, zadeva: str, besedilo: str, osnutek_id: str = "",
             priloge=None) -> dict:
        """Novo e-sporocilo (lastnik, 14. 10. 2026: v Sporocilih je manjkalo). Vrne nabiralnik in poslan pogovor."""
        prejemnik, zadeva, besedilo = str(prejemnik).strip(), str(zadeva).strip(), str(besedilo).strip()
        if not _NASLOV.fullmatch(prejemnik):
            raise ValueError("Naslov prejemnika ni veljaven")
        priloge = self._priloge(kanal_id, priloge)
        if not besedilo and not priloge:
            raise ValueError("Prazno sporočilo")
        if "\n" in zadeva or "\r" in zadeva:
            raise ValueError("Zadeva ne sme imeti novih vrstic")
        self.storitev.novo(str(kanal_id), prejemnik, zadeva, besedilo, priloge)
        if osnutek_id:
            self.odstrani_osnutek(osnutek_id)
        return dict(self.seznam(), poslano={"kanal_id": str(kanal_id), "id": prejemnik})

    def _pot_osnutkov(self) -> Path:
        return Path(self.storitev.pot).with_name("osnutki.json")

    def uskladi_osnutke(self, najmanj_s: float = 60.0) -> list:
        """Osnutek, ki ga je uporabnik v Gmailu (telefon) poslal ali izbrisal, izgine tudi tukaj (najvec enkrat na minuto)."""
        with self._osnutki_klj:
            return self._uskladi_osnutke(najmanj_s)

    def _uskladi_osnutke(self, najmanj_s: float) -> list:
        import time
        if time.monotonic() - getattr(self, "_osnutki_uskl", -1e9) < najmanj_s:
            return self.osnutki()
        self._osnutki_uskl = time.monotonic()
        seznam = self.osnutki()
        po_kanalu: dict = {}
        for o in seznam:
            if o.get("mid"):
                po_kanalu.setdefault(str(o.get("kanal_id") or ""), []).append(o)
        odstrani = []
        for kid, osn in po_kanalu.items():
            a = self.storitev.adapterji.get(kid)
            if a is None or not hasattr(a, "osnutki_na_strezniku"):
                continue
            try:
                ostali = a.osnutki_na_strezniku([o["mid"] for o in osn])
            except Exception as e:  # noqa: BLE001 - brez omrezja ali gesla: nic ne spremenimo
                print("[Sporocila] uskladitev osnutkov:", e, flush=True)
                continue
            odstrani += [o["id"] for o in osn if o["mid"] not in ostali]
        if not odstrani:
            return seznam
        nov = [x for x in seznam if x.get("id") not in odstrani]
        pot = self._pot_osnutkov()
        zacasna = pot.with_suffix(".tmp")
        zacasna.write_text(json.dumps(nov, ensure_ascii=False, indent=1), "utf-8")
        os.chmod(zacasna, 0o600)
        os.replace(zacasna, pot)
        return nov

    def osnutki(self) -> list:
        try:
            podatki = json.loads(self._pot_osnutkov().read_text("utf-8"))
        except (OSError, ValueError):
            return []
        return [o for o in podatki if isinstance(o, dict) and o.get("id")] if isinstance(podatki, list) else []

    def shrani_osnutek(self, o: dict) -> list:
        """Osnutek ostane na tem racunalniku (z isto zasebnostjo kot baza sporocil); najvec 50."""
        with self._osnutki_klj:
            return self._shrani_osnutek(o)

    def _shrani_osnutek(self, o: dict) -> list:
        o = o if isinstance(o, dict) else {}
        cist = {"id": str(o.get("id") or uuid.uuid4().hex[:12]), "kanal_id": str(o.get("kanal_id") or "")[:200],
                "za": str(o.get("za") or "")[:320], "zadeva": str(o.get("zadeva") or "")[:300].replace("\n", " "),
                "besedilo": str(o.get("besedilo") or "")[:200000], "cas": _cas_zdaj(),
                # Priloge osnutka (poti na tem racunalniku): ob ponovnem odprtju so spet pod pismom.
                "priloge": [os.path.realpath(str(p)) for p in (o.get("priloge") or [])[:50]
                            if isinstance(p, str) and os.path.isfile(os.path.expanduser(p))]}
        prejsnji = next((x for x in self.osnutki() if x.get("id") == cist["id"]), {})
        # Tudi v mapo Osnutki e-postnega racuna (lastnik, 14. 10. 2026: osnutek naj bo viden v Gmailu na telefonu).
        cist["mid"] = self._osnutek_na_streznik(cist, str(prejsnji.get("mid") or "")) or str(prejsnji.get("mid") or "")
        ostali = [x for x in self.osnutki() if x.get("id") != cist["id"]]
        seznam = ([cist] + ostali)[:50]
        pot = self._pot_osnutkov()
        zacasna = pot.with_suffix(".tmp")
        zacasna.write_text(json.dumps(seznam, ensure_ascii=False, indent=1), "utf-8")
        os.chmod(zacasna, 0o600)
        os.replace(zacasna, pot)
        return seznam

    def _osnutek_na_streznik(self, o: dict, prejsnji_mid: str) -> str:
        a = self.storitev.adapterji.get(str(o.get("kanal_id") or ""))
        if a is None or not hasattr(a, "shrani_osnutek"):
            return ""
        try:
            return a.shrani_osnutek(o.get("za", ""), o.get("zadeva", ""), o.get("besedilo", ""), prejsnji_mid,
                                    [{"pot": p} for p in o.get("priloge") or []])
        except Exception as e:  # noqa: BLE001 - osnutek ostane vsaj na tem racunalniku
            print("[Sporocila] osnutek na strezniku:", e, flush=True)
            return ""

    def _osnutek_s_streznika(self, o: dict) -> None:
        a = self.storitev.adapterji.get(str(o.get("kanal_id") or ""))
        if a is None or not o.get("mid") or not hasattr(a, "odstrani_osnutek"):
            return
        try:
            a.odstrani_osnutek(str(o["mid"]))
        except Exception as e:  # noqa: BLE001
            print("[Sporocila] odstranitev osnutka na strezniku:", e, flush=True)

    def odstrani_osnutek(self, osnutek_id: str) -> list:
        with self._osnutki_klj:
            return self._odstrani_osnutek(osnutek_id)

    def _odstrani_osnutek(self, osnutek_id: str) -> list:
        for o in self.osnutki():
            if o.get("id") == str(osnutek_id):
                self._osnutek_s_streznika(o)     # poslan ali izbrisan osnutek izgine tudi iz Gmaila
        seznam = [x for x in self.osnutki() if x.get("id") != str(osnutek_id)]
        pot = self._pot_osnutkov()
        zacasna = pot.with_suffix(".tmp")
        zacasna.write_text(json.dumps(seznam, ensure_ascii=False, indent=1), "utf-8")
        os.chmod(zacasna, 0o600)
        os.replace(zacasna, pot)
        return seznam

    # ------------------------------------------------------------------ Safeer Chat (Link)
    def _zagotovi_kanal_linka(self) -> None:
        st = self.storitev
        with st._zaklep, st.db:
            st.db.execute("INSERT OR IGNORE INTO kanali VALUES(?,?,?,?,?)",
                          (KANAL_LINKA, VRSTA_LINKA, "Safeer Link", "povezan", "{}"))

    def _pogovor_linka(self, naprava_id: str, ime: str, zadnje: str, cas: str, novih: int) -> None:
        st = self.storitev
        oseba = st.graf.dodaj(ime.strip() or naprava_id, [(VRSTA_LINKA, naprava_id)]).id
        with st._zaklep, st.db:
            prej = st.db.execute("SELECT neprebrano, zadnje_sporocilo, cas FROM pogovori WHERE id=? AND kanal_id=?",
                                 (naprava_id, KANAL_LINKA)).fetchone()
            neprebrano = (int(prej["neprebrano"] or 0) if prej else 0) + novih
            if prej and not zadnje:
                zadnje, cas = prej["zadnje_sporocilo"] or "", prej["cas"] or cas
            st.db.execute("INSERT OR REPLACE INTO pogovori(id,kanal_id,oseba_id,zadeva,zadnje_sporocilo,neprebrano,cas,identiteta) VALUES(?,?,?,?,?,?,?,?)",
                          (naprava_id, KANAL_LINKA, oseba, "", zadnje[:240], neprebrano, cas, naprava_id))

    def prejmi_klepet(self, od: str, ime: str, besedilo: str, cas: str = "", sid: str = "") -> bool:
        """chat.send z druge naprave; vrne True, ce je sporocilo novo (ne ponovljena dostava)."""
        od, besedilo = str(od or "").strip(), str(besedilo or "")[:NAJVEC_KLEPET]
        if not od or not besedilo.strip():
            return False
        self._zagotovi_kanal_linka()
        sid = "chat:" + (str(sid) or uuid.uuid4().hex)
        st = self.storitev
        with st._zaklep:
            if st.db.execute("SELECT 1 FROM sporocila WHERE id=? AND kanal_id=?", (sid, KANAL_LINKA)).fetchone():
                return False
        cas = _cas_klepeta(cas)
        with st._zaklep, st.db:
            st.db.execute("INSERT OR REPLACE INTO sporocila(id,pogovor_id,kanal_id,smer,besedilo,cas,priponke,stanje) "
                          "VALUES(?,?,?,?,?,?,?,?)",
                          (sid, od, KANAL_LINKA, "noter", besedilo, cas, "[]", "prejeto"))
        self._pogovor_linka(od, ime, besedilo.replace("\n", " "), cas, 1)
        _sporoci()
        return True

    def zacni_klepet(self, naprava_id: str, ime: str) -> dict:
        """Uporabnik pise napravi prvi: pogovor obstaja, preden je kaj poslano."""
        naprava_id = str(naprava_id or "").strip()
        if not naprava_id:
            raise ValueError("Ni naprave")
        self._zagotovi_kanal_linka()
        self._pogovor_linka(naprava_id, str(ime or ""), "", _cas_zdaj(), 0)
        return self.seznam()

    def naprave_za_klepet(self) -> list:
        try:
            return list(self.naprave_klepeta() if self.naprave_klepeta else [])
        except Exception:
            return []

    def _poslji_po_linku(self, naprava_id: str, besedilo: str) -> dict:
        if len(besedilo.encode("utf-8")) > NAJVEC_KLEPET:
            raise ValueError(NAPAKE_KLEPETA["meja"])
        if self.poslji_klepet is None:
            raise ValueError(NAPAKE_KLEPETA["ni_controla"])
        cas = _cas_zdaj()
        izid = str(self.poslji_klepet(naprava_id, besedilo, cas) or "")
        if izid not in ("accepted", "queued"):
            raise ValueError(NAPAKE_KLEPETA.get(izid, "Sporočila ni bilo mogoče poslati."))
        sid = "chat:ven:" + uuid.uuid4().hex
        st = self.storitev
        with st._zaklep, st.db:
            st.db.execute("INSERT OR REPLACE INTO sporocila(id,pogovor_id,kanal_id,smer,besedilo,cas,priponke,stanje) "
                          "VALUES(?,?,?,?,?,?,?,?)",
                          (sid, naprava_id, KANAL_LINKA, "ven", besedilo, cas, "[]",
                           "caka" if izid == "queued" else "poslano"))
            st.db.execute("UPDATE pogovori SET zadnje_sporocilo=?,cas=? WHERE id=? AND kanal_id=?",
                          (besedilo[:240], cas, naprava_id, KANAL_LINKA))
        return {"id": sid, "pogovor_id": naprava_id, "smer": "ven", "besedilo": besedilo, "cas": cas,
                "stanje": "caka" if izid == "queued" else "poslano", "caka": izid == "queued"}

    # ------------------------------------------------------------------ priponke (prenos, predogled, slicice)
    def _najdi_priponko(self, kanal_id: str, sporocilo_id: str, kljuc: str):
        """(adapter, sporocilo, priponka) iz predpomnilnika sporocil - stran poda samo kljuc, ne podatkov priponke."""
        s = self.storitev.sporocilo(str(kanal_id), str(sporocilo_id))
        if s is None:
            raise ValueError(NAPAKE_PRILOG["ni_pisma"])
        for i, p in enumerate(s.priponke or []):
            if isinstance(p, dict) and kljuc_priponke(p, i) == str(kljuc):
                return self.storitev.adapterji.get(str(kanal_id)), s, p
        raise ValueError(NAPAKE_PRILOG["ni_pisma"])

    def _vnos(self, kanal_id: str, s, p: dict, kljuc: str) -> str:
        """Mapa vnosa v predpomnilniku s kljucem (kanal_id, mapa, UIDVALIDITY, UID, del) - core/sporocila/predpomnilnik.py.
        Kanali brez map IMAP: mapa "", UID = id sporocila, del = kljuc priponke."""
        uid = s.id[4:] if str(s.id).startswith("uid:") else str(s.id)
        return predpomnilnik.mapa_vnosa(str(kanal_id), str(p.get("mapa") or ""), p.get("uidvalidity") or "", uid, kljuc)

    def _prenesi_v(self, adapter, s, p, cilj: str, napredek: Optional[Callable[[float], None]] = None) -> str:
        """Prenese priponko v datoteko `cilj` (prek .part: nedokoncan prenos ne pusti pokvarjene datoteke)."""
        lokalno = str(p.get("lokalno") or "")
        if lokalno and os.path.isfile(lokalno):          # poslano iz Safeerja: priloga je na tem racunalniku
            if os.path.realpath(lokalno) != os.path.realpath(cilj):
                shutil.copyfile(lokalno, cilj)
            return cilj
        if adapter is None:
            raise ValueError(NAPAKE_PRILOG["ni_povezave"])
        skupaj = int(p.get("kodirano") or 0) or int(p.get("velikost") or 0)
        zadnji = [0.0]

        def javi(preneseno: int) -> None:
            if napredek is None or not skupaj:
                return
            zdaj = time.monotonic()
            if zdaj - zadnji[0] >= 0.2:               # najvec 5 dogodkov na sekundo
                zadnji[0] = zdaj
                napredek(min(0.99, preneseno / skupaj))
        zacasna = cilj + ".part"
        try:
            with open(zacasna, "wb") as f:
                os.chmod(zacasna, 0o600)
                adapter.prenesi_priponko(s.id, p, f.write, javi)
            os.replace(zacasna, cilj)
        except NotImplementedError as e:
            raise ValueError(NAPAKE_PRILOG["priloge_ni_podprto"]) from e
        except ValueError as e:
            raise ValueError(NAPAKE_PRILOG.get(str(e), NAPAKE_PRILOG["napaka"])) from e
        except Exception as e:  # noqa: BLE001 - omrezje, streznik: koda za uporabnika, ne sled (lahko nosi naslov)
            raise ValueError(NAPAKE_PRILOG["ni_pisma"] if "ni_pisma" in str(e) else NAPAKE_PRILOG["ni_povezave"]) from e
        finally:
            if os.path.exists(zacasna):
                try:
                    os.remove(zacasna)
                except OSError:
                    pass
        if napredek is not None:
            napredek(1.0)
        return cilj

    def priponka_v_predpomnilnik(self, kanal_id: str, sporocilo_id: str, kljuc: str,
                                 napredek: Optional[Callable[[float], None]] = None) -> tuple:
        """Priponka na disku za predogled, slicico in »Odpri v programu«. Vrne (pot, priponka). Najprej iz Prejemov
        (ce jo je uporabnik prenesel in je tam nespremenjena), nato iz predpomnilnika; sele potem z omrezja."""
        adapter, s, p = self._najdi_priponko(kanal_id, sporocilo_id, kljuc)
        lokalno = str(p.get("lokalno") or "")
        if lokalno and os.path.isfile(lokalno):
            return lokalno, p
        vnos = self._vnos(kanal_id, s, p, kljuc)
        v_prejemih = predpomnilnik.prejeto(vnos)
        if v_prejemih:
            predpomnilnik.uporabi(os.path.join(vnos, "prejeto.json"))
            return v_prejemih, p
        cilj = os.path.join(vnos, predogled_datotek.varno_ime(p.get("ime", "")))
        if not (os.path.isfile(cilj) and os.path.getsize(cilj) > 0):
            self._prenesi_v(adapter, s, p, cilj, napredek)
            predpomnilnik.pocisti()                      # meja velikosti (LRU) po vsakem novem vnosu
        predpomnilnik.uporabi(cilj)
        return cilj, p

    def mapa_vnosa(self, kanal_id: str, sporocilo_id: str, kljuc: str) -> str:
        """Mapa vnosa priponke (za PDF pretvorbe predogleda, ki ostanejo ob priponki)."""
        _a, s, p = self._najdi_priponko(kanal_id, sporocilo_id, kljuc)
        return self._vnos(kanal_id, s, p, kljuc)

    def priponka_prenesi(self, kanal_id: str, sporocilo_id: str, kljuc: str,
                         napredek: Optional[Callable[[float], None]] = None, mapa: str = "") -> dict:
        """»Prenesi«: v mapo Prejemi (XDG), z varnim in edinstvenim imenom. Vrne {"pot", "ime", "mapa"}.
        Kopija iz predpomnilnika se premakne v Prejemi (ne hranimo je dvakrat); vnos si zapomni pot v Prejemih."""
        adapter, s, p = self._najdi_priponko(kanal_id, sporocilo_id, kljuc)
        mapa = mapa or mapa_prejemov()
        cilj = splet_prenosi.edinstvena_pot(mapa, predogled_datotek.varno_ime(p.get("ime", "")))
        lokalno = str(p.get("lokalno") or "")
        if lokalno and os.path.isfile(lokalno):
            shutil.copyfile(lokalno, cilj)
            return {"ok": True, "pot": cilj, "ime": os.path.basename(cilj), "mapa": mapa}
        vnos = self._vnos(kanal_id, s, p, kljuc)
        predpomnjeno = os.path.join(vnos, predogled_datotek.varno_ime(p.get("ime", "")))
        if os.path.isfile(predpomnjeno) and os.path.getsize(predpomnjeno) > 0:
            shutil.move(predpomnjeno, cilj)              # ze v predogledu: brez omrezja in brez dvojnika
            os.chmod(cilj, 0o644)
            if napredek is not None:
                napredek(1.0)
        else:
            self._prenesi_v(adapter, s, p, cilj, napredek)
            os.chmod(cilj, 0o644)                        # v Prejemih kot vsak drug prenos
        predpomnilnik.zapisi_prejeto(vnos, cilj)
        return {"ok": True, "pot": cilj, "ime": os.path.basename(cilj), "mapa": mapa}

    def priponke_prenesi_vse(self, kanal_id: str, sporocilo_id: str,
                             napredek: Optional[Callable[[str, float], None]] = None) -> dict:
        """»Prenesi vse«: vse prave priponke pisma (ne slike v vrstici HTML) v Prejemi."""
        s = self.storitev.sporocilo(str(kanal_id), str(sporocilo_id))
        if s is None:
            raise ValueError(NAPAKE_PRILOG["ni_pisma"])
        poti, napake = [], 0
        for i, p in enumerate(s.priponke or []):
            if not isinstance(p, dict) or p.get("inline"):
                continue
            kljuc = kljuc_priponke(p, i)
            try:
                poti.append(self.priponka_prenesi(kanal_id, sporocilo_id, kljuc,
                                                  (lambda d, k=kljuc: napredek(k, d)) if napredek else None)["pot"])
            except ValueError:
                napake += 1
        if not poti:
            raise ValueError(NAPAKE_PRILOG["ni_povezave"] if napake else NAPAKE_PRILOG["ni_pisma"])
        return {"ok": not napake, "poti": poti, "napake": napake, "mapa": mapa_prejemov()}

    def priponka_slicica(self, kanal_id: str, sporocilo_id: str, kljuc: str) -> str:
        """Slicica slike za mehurcek (pot datoteke; "" ce je ni). Samo slike do 10 MB - kot Gmail, brez cakanja."""
        _a, _s, p = self._najdi_priponko(kanal_id, sporocilo_id, kljuc)
        if predogled_datotek.vrsta_predogleda(p.get("ime", ""), p.get("tip", "")) != "slika" or \
                int(p.get("velikost") or 0) > 10 * 1024 * 1024:
            return ""
        pot, _p = self.priponka_v_predpomnilnik(kanal_id, sporocilo_id, kljuc)
        if pot.lower().endswith((".svg", ".gif", ".avif", ".ico")) or os.path.getsize(pot) <= 300 * 1024:
            return pot                       # majhna slika ali vektor: brez pomanjsevanja (animacija GIF ostane)
        # Slicica ostane v vnosu priponke (drugic brez branja velike slike).
        return predpomnilnik.slicica(pot, self.mapa_vnosa(kanal_id, sporocilo_id, kljuc)) or pot

    def html_pisma(self, kanal_id: str, sporocilo_id: str, jezik: str = "sl", slike: bool = False,
                   je_blokirano: Optional[Callable[[str], bool]] = None,
                   posrednik: Optional[Callable[[str], str]] = None) -> dict:
        """HTML telo pisma (»Prikaži izvirnik«) s slikami v vrstici (cid:) iz predpomnilnika. Oddaljene slike so skrite,
        razen ce jih uporabnik pokaze (slike=True) ali jih vedno dovoli za tega posiljatelja; takrat jih prenese
        zascita Safeer (core/sporocila/slike.py). Vrne {"html", "skritih", "posiljatelj", "prikazane"}."""
        s = self.storitev.sporocilo(str(kanal_id), str(sporocilo_id))
        adapter = self.storitev.adapterji.get(str(kanal_id))
        if s is None or not s.html or adapter is None or not hasattr(adapter, "html_pisma"):
            raise ValueError(NAPAKE_PRILOG["ni_pisma"])
        try:
            vsebina = adapter.html_pisma(s.id, s.html)
        except Exception as e:  # noqa: BLE001
            raise ValueError(NAPAKE_PRILOG["ni_povezave"]) from e
        cid = {}
        for i, p in enumerate(s.priponke or []):
            if isinstance(p, dict) and p.get("cid") and str(p.get("tip", "")).startswith("image/") \
                    and p.get("tip") != "image/svg+xml" and int(p.get("velikost") or 0) <= 10 * 1024 * 1024:
                try:
                    pot, _p = self.priponka_v_predpomnilnik(kanal_id, sporocilo_id, kljuc_priponke(p, i))
                except ValueError:
                    continue
                from urllib.parse import quote
                cid[str(p["cid"])] = "file://" + quote(os.path.abspath(pot))
        posiljatelj = str(s.pogovor_id) if s.smer == "noter" and "@" in str(s.pogovor_id) else ""
        prikazane = bool(slike) or (bool(posiljatelj) and self.slike_od.dovoljen(posiljatelj))
        oddaljene = None
        if prikazane:
            naslovi = predogled_datotek.oddaljene_slike(vsebina)
            if naslovi:
                vnos = predpomnilnik.mapa_vnosa(str(kanal_id), "", "", str(sporocilo_id), "slike-s-spleta")
                oddaljene = _slike.prenesi_slike(naslovi, vnos, je_blokirano,
                                                 posrednik=posrednik or _slike.posrednik_okolja)
            else:
                oddaljene = {}
        html, skritih = predogled_datotek.html_pisma(vsebina, cid, jezik, oddaljene)
        return {"html": html, "skritih": skritih, "posiljatelj": posiljatelj, "prikazane": prikazane}

    # ---- »Vedno prikazi slike od …« (lokalno, po naslovu posiljatelja; preklic v podoknu osebe)
    @property
    def slike_od(self) -> "_slike.DovoljeniPosiljatelji":
        if getattr(self, "_slike_od", None) is None:
            self._slike_od = _slike.DovoljeniPosiljatelji(str(Path(self.storitev.pot).with_name("slike_posiljateljev.json")))
        return self._slike_od

    def html_posiljatelj(self, kanal_id: str, sporocilo_id: str) -> str:
        s = self.storitev.sporocilo(str(kanal_id), str(sporocilo_id))
        return str(s.pogovor_id) if s is not None and s.smer == "noter" and "@" in str(s.pogovor_id) else ""

    def nastavi_slike_od(self, naslov: str, dovoli: bool) -> list:
        return self.slike_od.nastavi(str(naslov), bool(dovoli))

    def isci(self, niz: str) -> list:
        n = str(niz).casefold().strip()
        if not n:
            return []
        return [s for s in self.storitev.zdruzeni_pogovori()
                if n in (s["oseba"]["ime"] + " " + s["oseba"].get("privzeto_ime", "") + " " +
                         " ".join(p["zadnje_sporocilo"] + " " + p["zadeva"] + " " + p["id"] + " " + " ".join(p.get("oznake", []))
                                  for p in s["pogovori"])).casefold()][:20]

    def isci_pri_osebi(self, oseba_id: str, niz: str, kanal_id: str = "", pogovor_id: str = "") -> list:
        """Iskanje po vsebini sporocil ene osebe (vsi njeni kanali) ali enega pogovora; za pano v nabiralniku."""
        kanali = {k.id: k.slovar() for k in self.storitev.kanali()}
        izid = self.storitev.isci_sporocila(niz, str(oseba_id or ""), str(kanal_id or ""), str(pogovor_id or ""))
        for z in izid:
            z["kanal"] = kanali.get(z["kanal_id"], {})
        return izid

    def sinhroniziraj(self) -> dict:
        # Kanali z nitjo se osvezijo v njej (vmesnik ne caka na dolgo poizvedbo Matrixa); spremembo javi dogodek.
        self.storitev.osvezi()
        return self.seznam()

    def zapri(self) -> None:
        self.storitev.zapri()
