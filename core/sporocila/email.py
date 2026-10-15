"""E-posta (IMAP + SMTP) kot kanal Safeer Sporocil - samo standardna knjiznica.

Pogovor je oseba (njen e-naslov), ne posamezno pismo: vsa pisma z isto osebo so ena nit, kot v
klepetu. Pisma beremo z BODY.PEEK, zato jih sinhronizacija NE oznaci kot prebrana; prenesemo le
nova pisma (UID vecji od zadnjega) in iz vsakega najvec prvih 64 KB - lahko za pomnilnik in omrezje. Priponke pove
zgradba pisma (BODYSTRUCTURE) ne glede na velikost; prenese se samo del, ki ga uporabnik odpre (core/sporocila/priponke.py).
"""

from __future__ import annotations

from datetime import datetime, timezone
from email import message_from_bytes, policy
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr, parsedate_to_datetime
import imaplib
import re
import smtplib
import ssl
import threading
from contextlib import contextmanager
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from .adapter import Adapter
from .model import Pogovor, Sporocilo
from . import skrivnosti
from . import priponke as _priponke_mod

PRVIC_NAJVEC = 200        # ob prvi povezavi zadnjih 200 pisem
NAJVEC_BAJTOV = 65536     # iz vsakega pisma prvih 64 KB (besedilo, ne priponke)
MAPA = "INBOX"
CASOVNA_OMEJITEV = 20


def _navedi(mapa: str) -> str:
    """Ime mape IMAP v narekovajih (presledki, krajevna imena v spremenjenem UTF-7)."""
    return '"%s"' % mapa.replace("\\", "\\\\").replace('"', '\\"')


class NapakaPrijave(RuntimeError):
    """Streznik je zavrnil uporabnisko ime ali geslo."""


# Presledki, ki jih prinese kopiranje s spletne strani ali telefona (nedeljivi, ozki ...), in nevidni znaki.
_TUJI_PRESLEDKI = re.compile(r"[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]")
_NEVIDNI = re.compile(r"[\u200b-\u200d\u2060\ufeff]")


def ocisti_geslo(geslo: str, brez_presledkov: bool = False) -> str:
    """Geslo, kot ga uporabnik prilepi: brez nevidnih znakov, z navadnimi presledki, brez presledkov na robu.
    brez_presledkov: gesla za aplikacije (Gmail, Yahoo, iCloud) so crke v skupinah - presledki niso del gesla."""
    g = _TUJI_PRESLEDKI.sub(" ", _NEVIDNI.sub("", str(geslo or ""))).strip()
    return re.sub(r"\s+", "", g) if brez_presledkov else g


def _ascii(*nizi: str) -> bool:
    try:
        for n in nizi:
            n.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _plain_utf8(uporabnik: str, geslo: str) -> bytes:
    return b"\0" + uporabnik.encode("utf-8") + b"\0" + geslo.encode("utf-8")


def _glava(vrednost) -> str:
    try:
        return str(make_header(decode_header(str(vrednost or ""))))
    except Exception:
        return str(vrednost or "")


def _cas(msg) -> str:
    try:
        dt = parsedate_to_datetime(msg.get("Date"))
        if dt.tzinfo is None:          # "-0000" (RFC 5322: pas neznan) - vzamemo UTC, ne krajevni cas
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _brez_html(besedilo: str) -> str:
    besedilo = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", besedilo)
    besedilo = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", besedilo)
    besedilo = re.sub(r"<[^>]+>", " ", besedilo)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        besedilo = besedilo.replace(a, b)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", besedilo)).strip()


def _brez_citata(besedilo: str) -> str:
    """Odgovor brez citiranega prejsnjega pisma (vrstice z > in vse po 'On ... wrote:')."""
    vrstice = []
    for v in besedilo.splitlines():
        if re.match(r"^\s*(On|Dne|Am|Le|El|Il)\b.{0,200}(wrote|napisal|schrieb|écrit|escribió|scritto)", v, re.I):
            break
        if v.lstrip().startswith(">"):
            continue
        vrstice.append(v)
    return "\n".join(vrstice).strip() or besedilo.strip()


def telo_pisma(msg) -> str:
    deli = msg.walk() if msg.is_multipart() else (msg,)
    html = ""
    for del_ in deli:
        if del_.get_content_disposition() == "attachment":
            continue
        tip = del_.get_content_type()
        if tip not in ("text/plain", "text/html"):
            continue
        try:
            vrednost = str(del_.get_content())
        except Exception:
            vrednost = (del_.get_payload(decode=True) or b"").decode(del_.get_content_charset() or "utf-8", "replace")
        if tip == "text/plain" and vrednost.strip():
            return _brez_citata(vrednost.strip())
        if tip == "text/html" and not html:
            html = _brez_citata(_brez_html(vrednost))
    return html


def _priponke(msg) -> List[dict]:
    """Rezerva za streznik brez BODYSTRUCTURE: samo priponke v prebranem delu pisma (brez stevilke dela)."""
    out = []
    for d in msg.walk():
        if d.get_content_disposition() == "attachment":
            out.append({"ime": _glava(d.get_filename() or "priponka"), "tip": d.get_content_type()})
    return out


def _besedilo_dela(surovo: bytes, opis: dict) -> str:
    """Besedilo dela (BODY.PEEK[<del>]) v pravem kodiranju in naboru znakov."""
    podatki = _priponke_mod.dekodiraj(surovo or b"", opis.get("kodiranje", ""))
    nabor = (opis.get("charset") or "utf-8").strip().lower() or "utf-8"
    try:
        return podatki.decode(nabor, "replace")
    except LookupError:
        return podatki.decode("utf-8", "replace")


class EmailAdapter(Adapter):
    vrsta = "email"
    zmore = {"poslji"}
    MAPA_PRIPONK = MAPA

    def __init__(self, kanal_id: str, naslov: str, imap_streznik: str, smtp_streznik: str,
                 imap_vrata: int = 993, smtp_vrata: int = 465, uporabnik: str = "",
                 geslo: str = "", vnos_gesla: Optional[Callable[[], str]] = None):
        self.kanal_id, self.naslov = kanal_id, naslov.strip()
        self.imap_streznik, self.smtp_streznik = imap_streznik, smtp_streznik
        self.imap_vrata, self.smtp_vrata = int(imap_vrata), int(smtp_vrata)
        self.uporabnik = uporabnik or self.naslov
        self._geslo, self._vnos_gesla = geslo, vnos_gesla
        self._imap: Optional[imaplib.IMAP4_SSL] = None
        self.zadnji_uid = 0
        # Sporocila zadnje sinhronizacije po osebi (storitev jih shrani v bazo).
        self._nova: Dict[str, List[Sporocilo]] = {}
        self._zadnja_niti: Dict[str, dict] = {}   # oseba -> {"zadeva", "message_id", "uidi"}
        # Povezava za prenos priponk (lastna: glavno povezavo uporablja sinhronizacija v drugi niti).
        self._prenosna: Optional[imaplib.IMAP4_SSL] = None
        self._prenosna_klj = threading.Lock()
        #: UIDVALIDITY mape ob zadnji sinhronizaciji (kljuc predpomnilnika priponk; nova vrednost = stari UID-ji ne veljajo).
        self.uidvalidity_priponk = ""

    # --------------------------------------------------------------- skrivnost
    @property
    def kljuc_skrivnosti(self) -> str:
        return "email:" + self.kanal_id

    def shrani_geslo(self, geslo: str) -> bool:
        self._geslo = geslo
        return skrivnosti.shrani(self.kljuc_skrivnosti, geslo)

    def pozabi_geslo(self) -> None:
        self._geslo = ""
        skrivnosti.pozabi(self.kljuc_skrivnosti)

    def _skrivnost(self) -> str:
        return skrivnosti.zahtevaj(self.kljuc_skrivnosti, self._geslo, self._vnos_gesla)

    # --------------------------------------------------------------- povezava
    def povezi(self) -> None:
        if self._imap is not None:
            try:
                if self._imap.noop()[0] == "OK":
                    return
            except Exception:
                pass
            self._imap = None
        imap = imaplib.IMAP4_SSL(self.imap_streznik, self.imap_vrata,
                                 ssl_context=ssl.create_default_context(), timeout=CASOVNA_OMEJITEV)
        try:
            geslo = self._skrivnost()
            if _ascii(self.uporabnik, geslo):
                imap.login(self.uporabnik, geslo)
            else:
                # imaplib.login poslje samo ASCII (sicer UnicodeEncodeError, ki je bil prikazan kot »streznika ni mogoce
                # doseci«); AUTHENTICATE PLAIN (RFC 4616) nosi UTF-8.
                imap.authenticate("PLAIN", lambda _izziv: _plain_utf8(self.uporabnik, geslo))
        except imaplib.IMAP4.error as e:
            try:
                imap.logout()
            except Exception:
                pass
            raise NapakaPrijave("Prijava ni uspela") from e
        imap.select("INBOX", readonly=False)
        self._imap = imap

    # --------------------------------------------------------------- osnutki na strezniku (IMAP Drafts)
    def _locena_povezava(self) -> imaplib.IMAP4_SSL:
        """Kratka lastna povezava za osnutke: glavna (INBOX) ostane sinhronizaciji, ki tece v drugi niti."""
        imap = imaplib.IMAP4_SSL(self.imap_streznik, self.imap_vrata,
                                 ssl_context=ssl.create_default_context(), timeout=CASOVNA_OMEJITEV)
        geslo = self._skrivnost()
        try:
            if _ascii(self.uporabnik, geslo):
                imap.login(self.uporabnik, geslo)
            else:
                imap.authenticate("PLAIN", lambda _izziv: _plain_utf8(self.uporabnik, geslo))
        except imaplib.IMAP4.error as e:
            try:
                imap.logout()
            except Exception:
                pass
            raise NapakaPrijave("Prijava ni uspela") from e
        return imap

    @staticmethod
    def _mapa_osnutkov(imap) -> str:
        """Mapa z oznako \\Drafts (RFC 6154; Gmail: »[Gmail]/Drafts« ali krajevno ime), sicer »Drafts«."""
        try:
            status, vrstice = imap.list()
            for v in vrstice or []:
                v = v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)
                if "\\Drafts" in v:
                    m = re.search(r'"([^"]*)"\s*$', v) or re.search(r"(\S+)\s*$", v)
                    if m:
                        return m.group(1)
        except Exception:
            pass
        return "Drafts"

    def _izbrisi_osnutek(self, imap, mapa: str, message_id: str) -> None:
        if not message_id:
            return
        if imap.select(_navedi(mapa))[0] != "OK":
            return
        status, odg = imap.uid("search", None, "HEADER", "Message-ID", message_id)
        uidi = (odg[0] or b"").split() if status == "OK" and odg else []
        for uid in uidi:
            imap.uid("store", uid, "+FLAGS", "(\\Deleted)")
        if not uidi:
            return
        # Navadni EXPUNGE bi trajno izbrisal VSA sporocila z \Deleted v Osnutkih (tudi tuja, ki jih je drug odjemalec
        # samo oznacil). UID EXPUNGE (RFC 4315, UIDPLUS) izbrise le nase; brez UIDPLUS samo, ce drugih oznacenih ni
        # (pregled 14. 10. 2026).
        if self._ima_uidplus(imap):
            imap.uid("expunge", b",".join(uidi).decode("ascii"))
            return
        status, odg = imap.uid("search", None, "DELETED")
        oznaceni = set((odg[0] or b"").split()) if status == "OK" and odg else None
        if oznaceni is not None and oznaceni <= set(uidi):
            imap.expunge()

    @staticmethod
    def _ima_uidplus(imap) -> bool:
        """Zmoznosti po prijavi (Gmail UIDPLUS oglasi sele po prijavi; imaplib hrani le tiste pred njo)."""
        zmoznosti = set(getattr(imap, "capabilities", ()) or ())
        try:
            status, odg = imap.capability()
            if status == "OK" and odg and odg[0]:
                v = odg[0].decode("ascii", "replace") if isinstance(odg[0], bytes) else str(odg[0])
                zmoznosti |= set(v.upper().split())
        except Exception:  # noqa: BLE001
            pass
        return "UIDPLUS" in {str(z).upper() for z in zmoznosti}

    def shrani_osnutek(self, za: str, zadeva: str, besedilo: str, prejsnji_mid: str = "",
                       priloge: Sequence[dict] = ()) -> str:
        """Osnutek tudi v mapo Osnutki na strezniku (Gmail na telefonu ga vidi in lahko poslje). Vrne Message-ID;
        prejsnja razlicica istega osnutka se odstrani. Priloge gredo zraven, da jih ima tudi osnutek na telefonu."""
        msg = EmailMessage()
        msg["From"] = self.naslov
        if za:
            msg["To"] = za
        msg["Subject"] = zadeva or ""
        msg["Message-ID"] = make_msgid(domain=self.naslov.split("@")[-1] or None)
        msg["Date"] = datetime.now(timezone.utc)
        msg.set_content(besedilo or "")
        try:
            _priponke_mod.dodaj_priloge(msg, priloge)
        except ValueError:
            pass          # prevelike ali izginule priloge: osnutek brez njih (na tem racunalniku ostanejo v osnutku)
        imap = self._locena_povezava()
        try:
            mapa = self._mapa_osnutkov(imap)
            status, _ = imap.append(_navedi(mapa), "(\\Draft)", imaplib.Time2Internaldate(datetime.now(timezone.utc)),
                                    msg.as_bytes(policy=policy.SMTP))
            if status != "OK":
                raise RuntimeError("Streznik osnutka ni shranil")
            self._izbrisi_osnutek(imap, mapa, prejsnji_mid)
        finally:
            try:
                imap.logout()
            except Exception:
                pass
        return str(msg["Message-ID"])

    def osnutki_na_strezniku(self, message_ids) -> set:
        """Kateri od teh osnutkov so se v mapi Osnutki (osnutek, poslan ali izbrisan v Gmailu, tam izgine)."""
        ids = [m for m in message_ids if m]
        if not ids:
            return set()
        imap = self._locena_povezava()
        try:
            if imap.select(_navedi(self._mapa_osnutkov(imap)), readonly=True)[0] != "OK":
                return set(ids)          # mape ne poznamo: nicesar ne brisemo
            ostali = set()
            for mid in ids:
                # UNDELETED: osnutek z oznako \Deleted (se ne izbrisan) je za uporabnika ze izbrisan.
                status, odg = imap.uid("search", None, "UNDELETED", "HEADER", "Message-ID", mid)
                if status != "OK" or (odg and odg[0] and odg[0].split()):
                    ostali.add(mid)      # ob napaki iskanja raje ohranimo
            return ostali
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def odstrani_osnutek(self, message_id: str) -> None:
        if not message_id:
            return
        imap = self._locena_povezava()
        try:
            self._izbrisi_osnutek(imap, self._mapa_osnutkov(imap), message_id)
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def zapri(self) -> None:
        if self._imap is not None:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None
        with self._prenosna_klj:
            if self._prenosna is not None:
                try:
                    self._prenosna.logout()
                except Exception:
                    pass
                self._prenosna = None

    # --------------------------------------------------------------- priponke (prenos enega dela)
    @contextmanager
    def _povezava_prenosa(self):
        """Povezava z izbranim INBOX samo za branje (EXAMINE: prenos ne spremeni oznak). Ce jo ze uporablja drug
        prenos (velika priponka), dobi ta svojo kratko povezavo - slicica ne caka na konec prenosa."""
        if self._prenosna_klj.acquire(blocking=False):
            try:
                imap = self._prenosna
                if imap is not None:
                    try:
                        if imap.noop()[0] != "OK":
                            imap = None
                    except Exception:  # noqa: BLE001
                        imap = None
                if imap is None:
                    imap = self._locena_povezava()
                    if imap.select(MAPA, readonly=True)[0] != "OK":
                        raise RuntimeError("Mape ni mogoce odpreti")
                    self._prenosna = imap
                try:
                    yield imap
                except (imaplib.IMAP4.abort, OSError):
                    self._prenosna = None
                    raise
            finally:
                self._prenosna_klj.release()
            return
        imap = self._locena_povezava()
        try:
            if imap.select(MAPA, readonly=True)[0] != "OK":
                raise RuntimeError("Mape ni mogoce odpreti")
            yield imap
        finally:
            try:
                imap.logout()
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _uidvalidity(imap) -> str:
        """UIDVALIDITY izbrane mape: iz odgovora na SELECT/EXAMINE, sicer STATUS. "" ce je streznik ne pove."""
        try:
            v = (getattr(imap, "untagged_responses", None) or {}).get("UIDVALIDITY")
            v = v[-1] if isinstance(v, list) and v else v
            if isinstance(v, (bytes, str)):
                v = v.decode("ascii", "replace") if isinstance(v, bytes) else v
                if v.strip().isdigit():
                    return v.strip()
            status, odg = imap.status(MAPA, "(UIDVALIDITY)")
            if status == "OK" and odg and isinstance(odg[0], (bytes, str)):
                m = re.search(r"UIDVALIDITY (\d+)", odg[0].decode("ascii", "replace") if isinstance(odg[0], bytes) else odg[0])
                if m:
                    return m.group(1)
        except Exception:  # noqa: BLE001
            pass
        return ""

    @staticmethod
    def uid_sporocila(sporocilo_id: str) -> int:
        if not str(sporocilo_id).startswith("uid:"):
            raise ValueError("ni_na_strezniku")       # poslano iz Safeerja: priloga je na tem racunalniku
        return int(str(sporocilo_id)[4:])

    def zgradba_pisma(self, uid: int) -> dict:
        """BODYSTRUCTURE enega pisma (za priponke, shranjene pred 15. 10. 2026 brez stevilke dela)."""
        with self._povezava_prenosa() as imap:
            status, podatki = imap.uid("fetch", str(int(uid)), "(UID BODYSTRUCTURE)")
        if status == "OK":
            for odg in _priponke_mod.razcleni_fetch(podatki):
                if isinstance(odg.get("BODYSTRUCTURE"), list):
                    return _priponke_mod.zgradba(odg["BODYSTRUCTURE"])
        raise RuntimeError("ni_pisma")

    def prenesi_del(self, uid: int, del_: str, kodiranje: str, pisi: Callable[[bytes], None],
                    napredek: Optional[Callable[[int], None]] = None, uidvalidity: str = "") -> int:
        """Prenese en del pisma po kosih (BODY.PEEK[del]<odmik.dolzina>), sproti dekodira in poda pisi(); vrne
        stevilo zapisanih bajtov. napredek(prenesenih kodiranih bajtov) po vsakem kosu. uidvalidity: ce jo ima mapa
        zdaj drugo, UID ne pomeni vec istega pisma - prenos se zavrne (ni_pisma)."""
        if not re.fullmatch(r"\d+(\.\d+)*", str(del_ or "")):
            raise ValueError("ni_dela")
        dek = _priponke_mod.Dekodirnik(kodiranje)
        zapisano, odmik = 0, 0
        with self._povezava_prenosa() as imap:
            if uidvalidity:
                zdaj = self._uidvalidity(imap)
                if zdaj and zdaj != str(uidvalidity):
                    raise RuntimeError("ni_pisma")
            while odmik < _priponke_mod.NAJVEC_DEL:
                status, podatki = imap.uid("fetch", str(int(uid)), "(BODY.PEEK[%s]<%d.%d>)"
                                           % (del_, odmik, _priponke_mod.KOS_PRENOSA))
                if status != "OK":
                    raise RuntimeError("ni_pisma")
                kos = None
                for odg in _priponke_mod.razcleni_fetch(podatki):
                    kos = _priponke_mod.vsebina_dela(odg)
                    if kos is not None:
                        break
                if kos is None:
                    if odmik == 0:
                        raise RuntimeError("ni_pisma")      # pismo je bilo izbrisano ali premaknjeno
                    break
                odmik += len(kos)
                izhod = dek.vnesi(kos)
                if izhod:
                    pisi(izhod)
                    zapisano += len(izhod)
                if napredek is not None:
                    napredek(odmik)
                if len(kos) < _priponke_mod.KOS_PRENOSA:
                    break
        konec = dek.koncaj()
        if konec:
            pisi(konec)
            zapisano += len(konec)
        return zapisano

    def prenesi_priponko(self, sporocilo_id: str, priponka: dict, pisi: Callable[[bytes], None],
                         napredek: Optional[Callable[[int], None]] = None) -> int:
        uid = self.uid_sporocila(sporocilo_id)
        del_, kodiranje = str(priponka.get("del") or ""), str(priponka.get("kodiranje") or "")
        if not del_:
            # Priponka iz starejse sinhronizacije (brez stevilke dela): poiscemo jo po imenu in vrsti.
            for p in self.zgradba_pisma(uid)["priponke"]:
                if p["ime"] == priponka.get("ime") and (not priponka.get("tip") or p["tip"] == priponka.get("tip")):
                    del_, kodiranje = p["del"], p["kodiranje"]
                    break
            if not del_:
                raise RuntimeError("ni_pisma")
        return self.prenesi_del(uid, del_, kodiranje, pisi, napredek, str(priponka.get("uidvalidity") or ""))

    def html_pisma(self, sporocilo_id: str, del_: str) -> str:
        """HTML telo pisma (do 2 MB) za pogled s slikami v vrstici."""
        uid = self.uid_sporocila(sporocilo_id)
        zg = self.zgradba_pisma(uid)
        opis = zg.get("html") or {}
        if not opis or (del_ and opis.get("del") != del_):
            raise RuntimeError("ni_pisma")
        deli: List[bytes] = []
        velikost = [0]

        def pisi(b: bytes) -> None:
            velikost[0] += len(b)
            if velikost[0] > 2 * 1024 * 1024:
                raise ValueError("prevelik")
            deli.append(b)
        self.prenesi_del(uid, opis["del"], "", pisi)
        return _besedilo_dela(b"".join(deli), opis)

    # --------------------------------------------------------------- branje
    def _nova_pisma(self):
        self.povezi()
        if self.zadnji_uid:
            status, odg = self._imap.uid("search", None, "UID", "%d:*" % (self.zadnji_uid + 1))
        else:
            status, odg = self._imap.uid("search", None, "ALL")
        if status != "OK" or not odg or not odg[0]:
            return []
        uidi = sorted(int(u) for u in odg[0].split() if int(u) > self.zadnji_uid)
        if not self.zadnji_uid:
            uidi = uidi[-PRVIC_NAJVEC:]
        pisma = []
        uidv = self._uidvalidity(self._imap)
        if uidv:
            self.uidvalidity_priponk = uidv
        for i in range(0, len(uidi), 25):
            skupina = ",".join(str(u) for u in uidi[i:i + 25])
            # BODYSTRUCTURE: priponke in deli pisma ne glede na velikost (prvih 64 KB jih pogosto nima).
            status, podatki = self._imap.uid("fetch", skupina, "(UID FLAGS BODYSTRUCTURE BODY.PEEK[]<0.%d>)" % NAJVEC_BAJTOV)
            if status != "OK":
                continue
            for odg_ in _priponke_mod.razcleni_fetch(podatki):
                try:
                    uid = int(str(odg_.get("UID") or ""))
                except ValueError:
                    continue                      # nenaroceni FETCH (sprememba oznak) nima UID
                zastavice = odg_.get("FLAGS") or []
                prebrano = any(str(z).lower() == "\\seen" for z in zastavice) if isinstance(zastavice, list) else False
                surovo = _priponke_mod.vsebina_dela(odg_) or b""
                bs = odg_.get("BODYSTRUCTURE")
                zg = _priponke_mod.zgradba(bs) if isinstance(bs, list) else None
                for pr in (zg or {}).get("priponke", []):
                    pr["mapa"], pr["uidvalidity"] = MAPA, uidv       # kljuc predpomnilnika in preverba ob prenosu
                pisma.append((uid, prebrano, message_from_bytes(surovo, policy=policy.default), zg))
        return pisma

    def _telo_iz_dela(self, uid: int, opis: dict) -> str:
        """Besedilo pisma, ki ga ni v prvih 64 KB (pred njim je velika priponka ali dolga glava): samo ta del."""
        try:
            status, podatki = self._imap.uid("fetch", str(uid), "(BODY.PEEK[%s]<0.%d>)" % (opis["del"], NAJVEC_BAJTOV))
            if status != "OK":
                return ""
            for odg_ in _priponke_mod.razcleni_fetch(podatki):
                surovo = _priponke_mod.vsebina_dela(odg_)
                if surovo:
                    return _besedilo_dela(surovo, opis)
        except Exception:  # noqa: BLE001 - brez besedila pismo ostane (s priponkami)
            pass
        return ""

    def pogovori(self, od: Optional[str] = None) -> Iterable[Pogovor]:
        self._nova = {}
        pogovori: Dict[str, Pogovor] = {}
        lasten = self.naslov.casefold()
        for uid, prebrano, msg, zg in sorted(self._nova_pisma(), key=lambda x: x[0]):
            self.zadnji_uid = max(self.zadnji_uid, uid)
            od_koga = parseaddr(str(msg.get("From", "")))
            komu = parseaddr(str(msg.get("To", "")))
            moje = od_koga[1].casefold() == lasten
            ime, naslov = (komu if moje else od_koga)
            oseba = (naslov or "neznan").casefold()
            zadeva = _glava(msg.get("Subject"))
            cas = _cas(msg)
            besedilo = telo_pisma(msg)
            if not besedilo and zg:
                if zg.get("besedilo"):
                    besedilo = _brez_citata(self._telo_iz_dela(uid, zg["besedilo"]).strip())
                elif zg.get("html"):
                    besedilo = _brez_citata(_brez_html(self._telo_iz_dela(uid, zg["html"])))
            mid = str(msg.get("Message-ID") or "").strip()
            s = Sporocilo("uid:%d" % uid, oseba, "ven" if moje else "noter", besedilo, cas,
                          zg["priponke"] if zg is not None else _priponke(msg),
                          "poslano" if moje else ("prebrano" if prebrano else "prejeto"),
                          (zg.get("html") or {}).get("del", "") if zg is not None else "")
            self._nova.setdefault(oseba, []).append(s)
            nit = self._zadnja_niti.setdefault(oseba, {"uidi": []})
            nit.update({"zadeva": zadeva, "message_id": mid, "ime": _glava(ime)})
            nit["uidi"].append(uid)
            p = pogovori.get(oseba) or Pogovor(oseba, self.kanal_id, oseba, zadeva, "", 0, cas)
            prave = [a["ime"] for a in s.priponke if not a.get("inline")]
            povzetek = besedilo.replace("\n", " ").strip() or ("📎 " + ", ".join(prave) if prave else "")
            p.zadeva, p.zadnje_sporocilo, p.cas = zadeva, povzetek[:240], cas
            if not moje and not prebrano:
                p.neprebrano += 1
            pogovori[oseba] = p
        return list(pogovori.values())

    def ime_osebe(self, oseba: str) -> str:
        return (self._zadnja_niti.get(oseba) or {}).get("ime", "")

    def sporocila(self, pogovor_id: str, pred: Optional[str] = None,
                  najvec: int = 50) -> Iterable[Sporocilo]:
        return list(self._nova.get(pogovor_id, []))[-max(1, int(najvec)):]

    # --------------------------------------------------------------- pisanje
    def poslji(self, pogovor_id: str, besedilo: str,
               priponke: Sequence[dict] = (), zadeva_nova: str = "") -> Sporocilo:
        """Odgovor v zadnji niti z osebo; zadeva_nova: novo sporocilo (nova nit s to zadevo, brez In-Reply-To).
        priponke: [{"pot": datoteka}] - skupaj najvec 25 MB (ValueError »priloge_prevelike«)."""
        prejemnik = pogovor_id if "@" in pogovor_id else ""
        if not prejemnik:
            raise ValueError("Ni naslova prejemnika")
        nit = {} if zadeva_nova else (self._zadnja_niti.get(pogovor_id) or {})
        zadeva = nit.get("zadeva") or ""
        msg = EmailMessage()
        msg["From"], msg["To"] = self.naslov, prejemnik
        if zadeva_nova:
            msg["Subject"] = zadeva_nova.strip()
        else:
            msg["Subject"] = zadeva if zadeva.lower().startswith(("re:", "odg:", "aw:")) else ("Re: " + zadeva if zadeva else "Sporočilo")
        if nit.get("message_id"):
            msg["In-Reply-To"] = nit["message_id"]
            msg["References"] = nit["message_id"]
        msg["Message-ID"] = make_msgid(domain=self.naslov.rsplit("@", 1)[-1] or None)
        msg.set_content(besedilo)
        # Pred povezavo: prevelike ali manjkajoce priloge zavrnemo, preden kaj gre na streznik.
        opis_prilog = _priponke_mod.dodaj_priloge(msg, priponke)
        kontekst = ssl.create_default_context()
        # 587 in 25 = STARTTLS, vse drugo (465 in nestandardna vrata) = neposreden TLS.
        if self.smtp_vrata not in (587, 25):
            smtp = smtplib.SMTP_SSL(self.smtp_streznik, self.smtp_vrata, context=kontekst, timeout=CASOVNA_OMEJITEV)
        else:
            smtp = smtplib.SMTP(self.smtp_streznik, self.smtp_vrata, timeout=CASOVNA_OMEJITEV)
            smtp.starttls(context=kontekst)
        try:
            try:
                geslo = self._skrivnost()
                if _ascii(self.uporabnik, geslo):
                    smtp.login(self.uporabnik, geslo)
                else:
                    # smtplib kodira prijavo kot ASCII: AUTH PLAIN z UTF-8 posljemo sami.
                    import base64
                    smtp.ehlo_or_helo_if_needed()
                    koda, odg = smtp.docmd("AUTH", "PLAIN " + base64.b64encode(_plain_utf8(self.uporabnik, geslo)).decode("ascii"))
                    if koda != 235:
                        raise smtplib.SMTPAuthenticationError(koda, odg)
            except smtplib.SMTPAuthenticationError as e:
                raise NapakaPrijave("Prijava ni uspela") from e
            smtp.send_message(msg)
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
        cas = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        if zadeva_nova:
            # Odgovor na to sporocilo (iz te aplikacije) nadaljuje novo nit.
            prej = self._zadnja_niti.get(pogovor_id) or {}
            self._zadnja_niti[pogovor_id] = dict(prej, zadeva=zadeva_nova.strip(), message_id=str(msg["Message-ID"]))
        return Sporocilo("mid:" + str(msg["Message-ID"]).strip("<>"), pogovor_id, "ven", besedilo, cas, opis_prilog, "poslano")

    def oznaci_prebrano(self, pogovor_id: str) -> None:
        uidi = (self._zadnja_niti.get(pogovor_id) or {}).get("uidi") or []
        if not uidi:
            return
        self.povezi()
        self._imap.uid("store", ",".join(str(u) for u in uidi[-200:]), "+FLAGS", "(\\Seen)")

    # --------------------------------------------------------------- stanje med zagoni
    def stanje(self) -> dict:
        """Kar mora ostati med zagoni (brez skrivnosti in brez vsebine pisem)."""
        return {"zadnji_uid": self.zadnji_uid,
                "niti": {o: {"zadeva": n.get("zadeva", ""), "message_id": n.get("message_id", ""),
                             "ime": n.get("ime", ""), "uidi": n.get("uidi", [])[-50:]}
                         for o, n in list(self._zadnja_niti.items())[-500:]}}

    def obnovi(self, stanje: dict) -> None:
        self.zadnji_uid = int(stanje.get("zadnji_uid") or 0)
        self._zadnja_niti = {str(o): dict(n) for o, n in (stanje.get("niti") or {}).items()}
