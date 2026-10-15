"""Most med razdelkom Sporocila v Safeer OS in jedrom zdruzenih sporocil (core/sporocila)."""

from __future__ import annotations

import json
import os
import re
import threading
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
from .sporocila import vklop as _vklop

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
INTERVAL_S = 120
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
        self.storitev.ob_sinhronizaciji = _sporoci
        self._nalozi()
        # Izklopljena Sporocila (core/sporocila/vklop.py): storitev ne tece, nic ne preverja poste.
        if zazeni and self.storitev.adapterji and _vklop.sporocila_vklopljena():
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
        izklopljeni = _vklop.izklopljeni_kanali()
        for r in self.storitev.db.execute("SELECT * FROM kanali").fetchall():
            if r["id"] in izklopljeni:
                continue            # izklopljen kanal se ne nalozi (nastavitve in prijava ostanejo)
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
    def ponudniki(jezik: str = "sl") -> dict:
        """Seznam ponudnikov, aplikacij in vgradljivih kanalov (imena v jeziku vmesnika) za carovnik »Dodaj kanal«."""
        return _ponudniki.za_vmesnik(jezik)

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
        self.storitev.zazeni()

    def nastavi_skrivnost(self, kanal_id: str, skrivnost: str) -> dict:
        """Ponovni vnos gesla/zetona (npr. brez zbirke skrivnosti po ponovnem zagonu)."""
        a = self.storitev.adapterji.get(kanal_id)
        if a is None or not skrivnost:
            raise ValueError("Ni kanala")
        (a.shrani_geslo if hasattr(a, "shrani_geslo") else a.shrani_zeton)(str(skrivnost))
        self.storitev.sinhroniziraj(kanal_id)
        return self.seznam()

    def odstrani_kanal(self, kanal_id: str) -> dict:
        self.storitev.odstrani_kanal(str(kanal_id))
        _vklop.pozabi_kanal(str(kanal_id))
        return self.seznam()

    # ------------------------------------------------------------------ vklop (lastnik, 15. 10. 2026)
    def vklopi_kanal(self, kanal_id: str, vklop: bool) -> dict:
        """Izklopljen kanal se ne povezuje, ne steje in ne obvesca; ostane na seznamu. Vklop ga takoj nalozi."""
        kid = str(kanal_id)
        if not any(k.id == kid for k in self.storitev.kanali()):
            raise ValueError("Ni kanala")
        _vklop.nastavi_kanal(kid, bool(vklop))
        if not vklop:
            a = self.storitev.adapterji.pop(kid, None)
            if a is not None and hasattr(a, "zapri"):
                try:
                    a.zapri()
                except Exception:  # noqa: BLE001
                    pass
        elif kid not in self.storitev.adapterji and kid != KANAL_LINKA:
            r = self.storitev.db.execute("SELECT * FROM kanali WHERE id=?", (kid,)).fetchone()
            a = self._adapter(kid, r["vrsta"], json.loads(r["nastavitve"] or "{}")) if r else None
            if a is not None:
                self.storitev.adapterji[kid] = a
                if _vklop.sporocila_vklopljena():
                    threading.Thread(target=self._prvic, args=(kid,), daemon=True).start()
        _sporoci()
        return self.seznam()

    def ustavi(self) -> None:
        """Sporocila izklopljena: storitev ne tece vec (brez preverjanja poste, Telegrama, Matrixa)."""
        self.storitev.ustavi()
        _sporoci()

    def nadaljuj(self) -> None:
        """Sporocila spet vklopljena: storitev tece, brez ponovnega zagona Safeer OS."""
        if self.storitev.adapterji:
            self.storitev.zazeni()
        _sporoci()

    # ------------------------------------------------------------------ branje/pisanje
    def seznam(self, kanal: str = "") -> dict:
        skupine = self.storitev.zdruzeni_pogovori(kanal)
        izklopljeni = _vklop.izklopljeni_kanali()
        kanali = {k.id: dict(k.slovar(), vklopljen=k.id not in izklopljeni) for k in self.storitev.kanali()}
        if izklopljeni:
            # Pogovori izklopljenih kanalov niso v nabiralniku in se ne stejejo med neprebrane.
            for s in skupine:
                s["pogovori"] = [p for p in s["pogovori"] if p["kanal_id"] not in izklopljeni]
                s["neprebrano"] = sum(int(p.get("neprebrano") or 0) for p in s["pogovori"])
            skupine = [s for s in skupine if s["pogovori"]]
        try:
            smeri = self.storitev.zadnje_smeri()
        except Exception:
            smeri = {}
        for s in skupine:
            for p in s["pogovori"]:
                p["kanal"] = kanali.get(p["kanal_id"], {})
                p["zadnji_ven"] = smeri.get((p["kanal_id"], p["id"])) == "ven"
        return {"kanali": list(kanali.values()), "skupine": skupine, "oznake": self.storitev.vse_oznake()}

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
        return [s.slovar() for s in self.storitev.sporocila(kanal_id, pogovor_id)]

    def poslji(self, kanal_id: str, pogovor_id: str, besedilo: str) -> dict:
        besedilo = str(besedilo).strip()
        if not besedilo:
            raise ValueError("Prazno sporočilo")
        if kanal_id == KANAL_LINKA:
            return self._poslji_po_linku(str(pogovor_id), besedilo)
        return self.storitev.poslji(kanal_id, pogovor_id, besedilo).slovar()

    # ------------------------------------------------------------------ novo sporocilo in osnutki
    def novo(self, kanal_id: str, prejemnik: str, zadeva: str, besedilo: str, osnutek_id: str = "") -> dict:
        """Novo e-sporocilo (lastnik, 14. 10. 2026: v Sporocilih je manjkalo). Vrne nabiralnik in poslan pogovor."""
        prejemnik, zadeva, besedilo = str(prejemnik).strip(), str(zadeva).strip(), str(besedilo).strip()
        if not _NASLOV.fullmatch(prejemnik):
            raise ValueError("Naslov prejemnika ni veljaven")
        if not besedilo:
            raise ValueError("Prazno sporočilo")
        if "\n" in zadeva or "\r" in zadeva:
            raise ValueError("Zadeva ne sme imeti novih vrstic")
        self.storitev.novo(str(kanal_id), prejemnik, zadeva, besedilo)
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
                "besedilo": str(o.get("besedilo") or "")[:200000], "cas": _cas_zdaj()}
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
            return a.shrani_osnutek(o.get("za", ""), o.get("zadeva", ""), o.get("besedilo", ""), prejsnji_mid)
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
        # Izklopljen Safeer Chat ali izklopljena Sporocila: sporocilo se shrani (ne izgubi), a ne steje in ne obvesca.
        tiho = not _vklop.kanal_vklopljen(KANAL_LINKA)
        self._zagotovi_kanal_linka()
        sid = "chat:" + (str(sid) or uuid.uuid4().hex)
        st = self.storitev
        with st._zaklep:
            if st.db.execute("SELECT 1 FROM sporocila WHERE id=? AND kanal_id=?", (sid, KANAL_LINKA)).fetchone():
                return False
        cas = _cas_klepeta(cas)
        with st._zaklep, st.db:
            st.db.execute("INSERT OR REPLACE INTO sporocila VALUES(?,?,?,?,?,?,?,?)",
                          (sid, od, KANAL_LINKA, "noter", besedilo, cas, "[]", "prejeto"))
        self._pogovor_linka(od, ime, besedilo.replace("\n", " "), cas, 0 if tiho else 1)
        _sporoci()
        return not tiho

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
            st.db.execute("INSERT OR REPLACE INTO sporocila VALUES(?,?,?,?,?,?,?,?)",
                          (sid, naprava_id, KANAL_LINKA, "ven", besedilo, cas, "[]",
                           "caka" if izid == "queued" else "poslano"))
            st.db.execute("UPDATE pogovori SET zadnje_sporocilo=?,cas=? WHERE id=? AND kanal_id=?",
                          (besedilo[:240], cas, naprava_id, KANAL_LINKA))
        return {"id": sid, "pogovor_id": naprava_id, "smer": "ven", "besedilo": besedilo, "cas": cas,
                "stanje": "caka" if izid == "queued" else "poslano", "caka": izid == "queued"}

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
        self.storitev.sinhroniziraj()
        return self.seznam()

    def zapri(self) -> None:
        self.storitev.zapri()
