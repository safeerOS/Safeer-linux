"""Orkestracija adapterjev, lokalni predpomnilnik in sinhronizacija v realnem casu.

Vsak kanal ima svojo nit (core/sporocila/sprotno.py, imap_sprotno.py): e-posta IMAP IDLE, Matrix in Telegram dolga
poizvedba, ostalo poizvedba vsakih 30 s. Vse gre v zasebno bazo SQLite (0600), vmesnik bere samo iz nje.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from .adapter import Adapter
from .identiteta import IdentitetniGraf, PRIVZETA_POT, zasebna_baza
from .model import Kanal, Pogovor, Sporocilo


#: Lokalni predpomnilnik (nikoli streznik): sporocila, starejsa od tega, in nad velikostjo baze se brisejo.
HRANI_DNI = 365
NAJVEC_MB = 256


#: Iskanje znotraj osebe/pogovora: do toliko sporocil jih preverimo neposredno (glej isci_sporocila).
PREGLED_NAJVEC = 5000
_BESEDA = re.compile(r"[^\W_]+")


def _zlozi(niz: str) -> str:
    """Brez strešic in naglasov, male crke (č -> c, É -> e) - kot tokenizator FTS5 unicode61 remove_diacritics.
    Crka s strešico ostane ena crka, zato polozaj zadetka velja tudi v izvirnem besedilu (izsek)."""
    import unicodedata
    if niz.isascii():
        return niz.lower()
    return "".join(z for z in unicodedata.normalize("NFKD", niz) if not unicodedata.combining(z)).lower()


def _ujema(besede, besedilo: str) -> bool:
    """Vsaka iskana beseda je zacetek kake besede v besedilu."""
    v = _BESEDA.findall(_zlozi(besedilo))
    return all(any(w.startswith(b) for w in v) for b in besede)


def _je_omrezna(napaka: Exception) -> bool:
    """Ali poslano sporocilo pocaka v vrsti (ni povezave, streznik zacasno ne odgovori) - ali pa je zavrnjeno
    (napacen prejemnik, prijava): tega ponovni poskus ne popravi, uporabnik mora izvedeti takoj."""
    ime = type(napaka).__name__
    if ime in ("NapakaPrijave", "ManjkaSkrivnost", "SMTPAuthenticationError", "SMTPRecipientsRefused",
               "SMTPSenderRefused", "SMTPNotSupportedError"):
        return False
    koda = getattr(napaka, "smtp_code", None)
    if isinstance(koda, int):
        return 400 <= koda < 500
    koda = getattr(napaka, "code", None)
    if isinstance(koda, int):
        return koda == 429 or koda >= 500
    return isinstance(napaka, (OSError, TimeoutError))


class StoritevSporocil:
    def __init__(self, pot: Optional[Path] = None, interval: float = 30):
        self.pot = Path(pot or PRIVZETA_POT)
        zasebna_baza(self.pot)
        self.db = sqlite3.connect(str(self.pot), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.graf = IdentitetniGraf(self.pot)
        self.adapterji: Dict[str, Adapter] = {}
        self.interval = max(1, float(interval))
        self._ustavi = threading.Event()
        self._zaklep = threading.RLock()
        # REPLACE izbrise staro vrstico: brez tega se sprozilec brisanja (indeks iskanja) ne sprozi.
        self.db.execute("PRAGMA recursive_triggers=ON")
        with self.db:
            self.db.executescript("""
              CREATE TABLE IF NOT EXISTS kanali(id TEXT PRIMARY KEY,vrsta TEXT,ime TEXT,stanje TEXT,nastavitve TEXT);
              CREATE TABLE IF NOT EXISTS pogovori(id TEXT,kanal_id TEXT,oseba_id TEXT,zadeva TEXT,
                zadnje_sporocilo TEXT,neprebrano INTEGER,cas TEXT,PRIMARY KEY(id,kanal_id));
              CREATE TABLE IF NOT EXISTS sporocila(id TEXT,pogovor_id TEXT,kanal_id TEXT,smer TEXT,
                besedilo TEXT,cas TEXT,priponke TEXT,stanje TEXT,PRIMARY KEY(id,kanal_id));
              CREATE TABLE IF NOT EXISTS kanal_stanje(id TEXT PRIMARY KEY, podatki TEXT);
              CREATE TABLE IF NOT EXISTS oznake(kanal_id TEXT,pogovor_id TEXT,oznaka TEXT,PRIMARY KEY(kanal_id,pogovor_id,oznaka));
              CREATE INDEX IF NOT EXISTS sporocila_pogovor ON sporocila(kanal_id,pogovor_id,cas);
              -- Odhodna vrsta: sporocilo, poslano brez povezave, se poslje samo, ko se povezava vrne (v vrstnem redu,
              -- enkrat; idem = Message-ID / Matrix txn, da ponovljen poskus ni dvojnik).
              CREATE TABLE IF NOT EXISTS odhodni(id TEXT PRIMARY KEY,kanal_id TEXT,pogovor_id TEXT,besedilo TEXT,
                priponke TEXT,idem TEXT,ustvarjeno REAL,stanje TEXT,poskus REAL NOT NULL DEFAULT 0);
              -- Pisma, katerih celotno besedilo je ze tu (prirezana na 64 KB so prenesena znova enkrat).
              CREATE TABLE IF NOT EXISTS sporocila_polno(kanal_id TEXT,id TEXT,PRIMARY KEY(kanal_id,id));
              -- Zadnje znano stevilo neprebranih za kanale, ki jih ne steje ta baza (vgrajen spletni klepet).
              CREATE TABLE IF NOT EXISTS kanal_neprebrano(kanal_id TEXT PRIMARY KEY,stevilo INTEGER,cas TEXT);
            """)
            # Surova identiteta pogovora (naslov/racun pri kanalu) - potrebna za razdruzitev oseb.
            if "identiteta" not in {r[1] for r in self.db.execute("PRAGMA table_info(pogovori)")}:
                self.db.execute("ALTER TABLE pogovori ADD COLUMN identiteta TEXT NOT NULL DEFAULT ''")
        with self._zaklep, self.db:
            # Posiljanje, ki ga je prekinil konec programa: idem (Message-ID/txn) ostane, poskus se ponovi. Samo staro
            # (> 10 min): bazo odpre tudi drug primerek (Safeer Link za klepet), ki ne sme vzeti sporocila, ki ga
            # glavni primerek ravno posilja.
            self.db.execute("UPDATE odhodni SET stanje='caka' WHERE stanje='posiljam' AND poskus<?", (time.time() - 600,))
        self.fts = self._pripravi_fts()
        self._obnovljeni = set()
        self._zaklepi_kanalov: Dict[str, threading.RLock] = {}
        self._zaklepi_odhodnih: Dict[str, threading.Lock] = {}
        self._delavci: Dict[str, object] = {}
        #: Kanali, ki jih je uporabnik izklopil (zazeni() jih ne zbudi, dokler ni zazeni_kanal).
        self._izklopljeni: set = set()
        self._stanje_zapisano: Dict[str, float] = {}
        self._tece = False
        self._ciscenje = threading.Event()
        #: (kanal, pogovor) -> stevec sprememb vsebine brez novega sporocila (celotno besedilo, poslano iz vrste);
        #: vmesnik po njem ve, da mora odprt pogovor prebrati znova.
        self._razlicice: Dict[tuple, int] = {}
        self._omrezje = None
        #: Klic ob spremembi (novo sporocilo, oznake, stanje kanala): kuverta v pultu in odprt razdelek Sporocila se
        #: osvezita takoj, brez periodicnega branja. Klic pride iz niti kanala.
        self.ob_sinhronizaciji: Optional[Callable[[], None]] = None

    # ------------------------------------------------------------------ iskalni indeks (FTS5)
    _SPROZILCI_FTS = (
        """CREATE TRIGGER IF NOT EXISTS sporocila_fts_dodaj AFTER INSERT ON sporocila BEGIN
            INSERT INTO sporocila_fts(rowid,besedilo,zadeva,ime) VALUES(new.rowid,new.besedilo,
              COALESCE((SELECT zadeva FROM pogovori WHERE id=new.pogovor_id AND kanal_id=new.kanal_id),''),
              COALESCE((SELECT o.ime FROM pogovori p JOIN osebe o ON o.id=p.oseba_id
                        WHERE p.id=new.pogovor_id AND p.kanal_id=new.kanal_id),''));
          END""",
        """CREATE TRIGGER IF NOT EXISTS sporocila_fts_brisi AFTER DELETE ON sporocila BEGIN
            DELETE FROM sporocila_fts WHERE rowid=old.rowid;
          END""",
        """CREATE TRIGGER IF NOT EXISTS sporocila_fts_spremeni AFTER UPDATE OF besedilo ON sporocila BEGIN
            UPDATE sporocila_fts SET besedilo=new.besedilo WHERE rowid=new.rowid;
          END""",
    )

    def _pripravi_fts(self) -> bool:
        """Indeks FTS5 nad besedilom, zadevo in imenom posiljatelja; sprozilci ga drzijo uskladenega. Brez FTS5
        (star SQLite) iskanje ostane LIKE."""
        try:
            with self._zaklep, self.db:
                nova = not self.db.execute("SELECT 1 FROM sqlite_master WHERE name='sporocila_fts'").fetchone()
                try:
                    self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS sporocila_fts USING fts5(besedilo, zadeva, ime, "
                                    "tokenize='unicode61 remove_diacritics 2')")
                except sqlite3.OperationalError:
                    self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS sporocila_fts USING fts5(besedilo, zadeva, ime)")
                for ukaz in self._SPROZILCI_FTS:
                    self.db.execute(ukaz)
                if nova:
                    self.db.execute("""INSERT INTO sporocila_fts(rowid,besedilo,zadeva,ime)
                        SELECT s.rowid, s.besedilo, COALESCE(p.zadeva,''), COALESCE(o.ime,'') FROM sporocila s
                        LEFT JOIN pogovori p ON p.id=s.pogovor_id AND p.kanal_id=s.kanal_id
                        LEFT JOIN osebe o ON o.id=p.oseba_id""")
            return True
        except sqlite3.OperationalError:
            return False

    # ------------------------------------------------------------------ zaklepi in obvestila
    def _zaklep_kanala(self, kanal_id: str) -> threading.RLock:
        """En kanal hkrati sinhronizira ena nit; e-posta si deli eno povezavo IMAP (ukazi se ne smejo prepletati)."""
        with self._zaklep:
            return self._zaklepi_kanalov.setdefault(kanal_id, threading.RLock())

    def razlicica(self, kanal_id: str, pogovor_id: str) -> int:
        return self._razlicice.get((kanal_id, pogovor_id), 0)

    def _nova_razlicica(self, kanal_id: str, pogovor_id: str) -> None:
        k = (kanal_id, pogovor_id)
        self._razlicice[k] = self._razlicice.get(k, 0) + 1

    def _sporoci(self) -> None:
        if self.ob_sinhronizaciji is not None:
            try:
                self.ob_sinhronizaciji()
            except Exception:  # noqa: BLE001 - poslusalec ne sme ustaviti niti kanala
                pass

    def registriraj(self, kanal: Kanal, adapter: Adapter, nastavitve: Optional[dict] = None) -> None:
        nastavitve = dict(nastavitve or {})
        prepovedano = {"geslo", "password", "zeton", "token", "api_access_token", "secret"}
        if any(str(k).lower() in prepovedano for k in nastavitve):
            raise ValueError("Skrivnosti ne sodijo v nastavitveno datoteko")
        self.adapterji[kanal.id] = adapter
        with self._zaklep, self.db:
            self.db.execute("INSERT OR REPLACE INTO kanali VALUES(?,?,?,?,?)",
                            (kanal.id, kanal.vrsta, kanal.ime, kanal.stanje,
                             json.dumps(nastavitve, ensure_ascii=False)))

    dodaj_adapter = registriraj

    def kanali(self):
        with self._zaklep:
            return [Kanal(r["id"], r["vrsta"], r["ime"], r["stanje"])
                    for r in self.db.execute("SELECT * FROM kanali ORDER BY ime COLLATE NOCASE")]

    def sinhroniziraj(self, kanal_id: Optional[str] = None) -> int:
        """Prenese novo zdaj (v klicoci niti). Vsak kanal posebej pod svojim zaklepom - pocasen kanal ne zadrzi drugih."""
        skupaj = 0
        for kid in ([kanal_id] if kanal_id else list(self.adapterji)):
            n, uspeh, _sprememba = self._sinhroniziraj_en(kid)
            skupaj += n
            if uspeh:
                self.poslji_cakajoce(kid)
        self._sporoci()
        return skupaj

    def sinhroniziraj_kanal(self, kanal_id: str) -> bool:
        """Korak niti kanala: prenese novo, ob spremembi takoj obvesti vmesnik, ob uspehu poslje cakajoca sporocila."""
        _n, uspeh, sprememba = self._sinhroniziraj_en(kanal_id)
        if uspeh and self.poslji_cakajoce(kanal_id):
            sprememba = True
        if sprememba:
            self._sporoci()
        return uspeh

    @staticmethod
    def _razlog(napaka: Exception) -> str:
        ime = type(napaka).__name__
        if ime == "ManjkaSkrivnost":
            return "napaka:geslo"
        if ime in ("NapakaPrijave", "SMTPAuthenticationError") or "AUTH" in str(napaka).upper():
            return "napaka:prijava"
        if isinstance(napaka, (OSError, TimeoutError)) or ime == "NapakaIdle":
            return "napaka:omrezje"
        return "napaka"

    def oznaci_stanje(self, kanal_id: str, stanje: str) -> bool:
        """Stanje kanala (povezan, napaka:omrezje ...); ob spremembi obvesti vmesnik."""
        with self._zaklep, self.db:
            c = self.db.execute("UPDATE kanali SET stanje=? WHERE id=? AND stanje IS NOT ?", (stanje, kanal_id, stanje))
            spremenjeno = c.rowcount > 0
        if spremenjeno:
            self._sporoci()
        return spremenjeno

    def pozabi_povezavo(self, kanal_id: str) -> None:
        """Mrtva povezava adapterja (spanje, novo omrezje) se zapre brez cakanja na odgovor streznika."""
        adapter = self.adapterji.get(kanal_id)
        if getattr(adapter, "_imap", None) is None:
            return
        with self._zaklep_kanala(kanal_id):
            imap = adapter._imap
            adapter._imap = None
            try:
                imap.shutdown()
            except Exception:  # noqa: BLE001
                pass

    def _znani_uidi(self, kanal_id: str) -> List[int]:
        with self._zaklep:
            vrstice = self.db.execute("SELECT id FROM sporocila WHERE kanal_id=? AND id LIKE 'uid:%' AND smer='noter'",
                                      (kanal_id,)).fetchall()
        izid = []
        for r in vrstice:
            try:
                izid.append(int(r[0][4:]))
            except ValueError:
                pass
        return izid

    def _sinhroniziraj_en(self, kid: str):
        """(stevilo pogovorov, uspeh, spremenjeno)."""
        adapter = self.adapterji.get(kid)
        if not adapter:
            return 0, False, False
        with self._zaklep_kanala(kid):
            try:
                if kid not in self._obnovljeni and hasattr(adapter, "obnovi"):
                    with self._zaklep:
                        vrstica = self.db.execute("SELECT podatki FROM kanal_stanje WHERE id=?", (kid,)).fetchone()
                    if vrstica:
                        adapter.obnovi(json.loads(vrstica["podatki"] or "{}"))
                    self._obnovljeni.add(kid)
                adapter.povezi()
                pogovori = list(adapter.pogovori())
                pripravljeni = []
                for p in pogovori:
                    ime = adapter.ime_osebe(p.oseba_id) if hasattr(adapter, "ime_osebe") else ""
                    oseba_id = self._oseba(adapter.vrsta, p.oseba_id, ime)
                    pripravljeni.append((p, oseba_id, list(adapter.sporocila(p.id, najvec=50))))
                oznake = {}
                ponastavljen = bool(getattr(adapter, "ponastavljen", False))
                if getattr(adapter, "vrsta", "") == "email" and getattr(adapter, "_imap", None) is not None \
                        and hasattr(adapter, "modseq") and not ponastavljen:
                    from . import imap_sprotno
                    try:
                        oznake = imap_sprotno.uskladi_oznake(adapter, self._znani_uidi(kid))
                    except Exception as e:  # noqa: BLE001 - nova pisma so ze prenesena; oznake ob naslednji
                        print("[Sporocila] oznake:", type(e).__name__, flush=True)
                na_strezniku = None
                if getattr(adapter, "vrsta", "") == "email" and getattr(adapter, "_imap", None) is not None \
                        and hasattr(adapter, "modseq"):
                    from . import imap_sprotno
                    try:
                        # Znacka kanala = stevilo na strezniku (kot Gmail za INBOX); seznam pogovorov steje predpomnilnik.
                        na_strezniku = imap_sprotno.neprebrano_na_strezniku(adapter)
                    except Exception as e:  # noqa: BLE001
                        print("[Sporocila] STATUS:", type(e).__name__, flush=True)
                inkrementalno = hasattr(adapter, "obnovi")
                with self._zaklep, self.db:
                    if self.adapterji.get(kid) is not adapter:
                        return 0, False, False          # kanal je medtem odstranjen: izid zavrzemo
                    prej = self.db.total_changes
                    if ponastavljen:
                        # UIDVALIDITY se je spremenil: stari UID-ji kazejo na druga (ali nobena) pisma.
                        self.db.execute("DELETE FROM sporocila WHERE kanal_id=? AND id LIKE 'uid:%'", (kid,))
                        self.db.execute("DELETE FROM sporocila_polno WHERE kanal_id=? AND id LIKE 'uid:%'", (kid,))
                        adapter.ponastavljen = False
                    self.db.execute("UPDATE kanali SET stanje='povezan' WHERE id=? AND stanje IS NOT 'povezan'", (kid,))
                    for p, oseba_id, sporocila in pripravljeni:
                        self._shrani_pogovor(kid, p, oseba_id, None if inkrementalno else p.neprebrano)
                        for s in sporocila:
                            self._shrani_sporocilo(kid, s)
                    for uid, prebrano in oznake.items():
                        novo = "prebrano" if prebrano else "prejeto"
                        self.db.execute("UPDATE sporocila SET stanje=? WHERE id=? AND kanal_id=? AND smer='noter' "
                                        "AND stanje IN ('prejeto','prebrano') AND stanje IS NOT ?",
                                        (novo, "uid:%d" % uid, kid, novo))
                    if inkrementalno:
                        self._preracunaj_neprebrano(kid)
                    if na_strezniku is not None:
                        self._zapisi_neprebrano_kanala(kid, na_strezniku)
                    spremenjeno = self.db.total_changes != prej
                    # Stanje kanala (Matrix: sobe z zadnjimi sporocili) ob vsaki dolgi poizvedbi (30 s) bi pomenilo
                    # stalno pisanje na disk brez novic: zapisemo ob spremembi ali najkasneje vsakih 5 min.
                    zdaj = time.monotonic()
                    if hasattr(adapter, "stanje") and (spremenjeno or ponastavljen or
                                                       zdaj - self._stanje_zapisano.get(kid, -1e9) > 300):
                        self._stanje_zapisano[kid] = zdaj
                        self.db.execute("INSERT OR REPLACE INTO kanal_stanje VALUES(?,?)",
                                        (kid, json.dumps(adapter.stanje(), ensure_ascii=False)))
                return len(pripravljeni), True, spremenjeno
            except Exception as napaka:
                # Brez skrivnosti/omrezja kanal ostane uporaben po predpomnilniku. Izjeme namenoma
                # ne zapisujemo: lahko bi vsebovala uporabnisko ime ali odgovor streznika.
                razlog = self._razlog(napaka)
                with self._zaklep, self.db:
                    if self.adapterji.get(kid) is not adapter:
                        return 0, False, False
                    c = self.db.execute("UPDATE kanali SET stanje=? WHERE id=? AND stanje IS NOT ?", (razlog, kid, razlog))
                return 0, False, c.rowcount > 0

    def _shrani_pogovor(self, kid: str, p: Pogovor, oseba_id: str, neprebrano: Optional[int]) -> None:
        """Zapise samo, kar se je spremenilo (sprememba = dogodek za vmesnik). neprebrano=None: steje baza."""
        brez = neprebrano is None
        self.db.execute("""INSERT INTO pogovori(id,kanal_id,oseba_id,zadeva,zadnje_sporocilo,neprebrano,cas,identiteta)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id,kanal_id) DO UPDATE SET oseba_id=excluded.oseba_id,
              zadeva=excluded.zadeva, zadnje_sporocilo=excluded.zadnje_sporocilo, cas=excluded.cas,
              identiteta=excluded.identiteta, neprebrano=CASE WHEN ? THEN pogovori.neprebrano ELSE excluded.neprebrano END
            WHERE pogovori.oseba_id IS NOT excluded.oseba_id OR pogovori.zadeva IS NOT excluded.zadeva
              OR pogovori.zadnje_sporocilo IS NOT excluded.zadnje_sporocilo OR pogovori.cas IS NOT excluded.cas
              OR pogovori.identiteta IS NOT excluded.identiteta
              OR (NOT ? AND pogovori.neprebrano IS NOT excluded.neprebrano)""",
            (p.id, kid, oseba_id, p.zadeva, p.zadnje_sporocilo, int(neprebrano or 0), p.cas, str(p.oseba_id), brez, brez))

    def _preracunaj_neprebrano(self, kanal_id: str) -> None:
        """Neprebrana iz oznak sporocil v predpomnilniku - ne sestevek po sinhronizacijah, ki je lezel stran od
        resnice, ko je uporabnik pismo prebral na telefonu."""
        stevec = """(SELECT COUNT(*) FROM sporocila s WHERE s.kanal_id=pogovori.kanal_id AND s.pogovor_id=pogovori.id
                     AND s.smer='noter' AND s.stanje='prejeto')"""
        self.db.execute("UPDATE pogovori SET neprebrano=%s WHERE kanal_id=? AND neprebrano IS NOT %s" % (stevec, stevec),
                        (kanal_id,))

    def oznaci_prebrano(self, kanal_id: str, pogovor_id: str) -> None:
        with self._zaklep, self.db:
            self.db.execute("UPDATE pogovori SET neprebrano=0 WHERE id=? AND kanal_id=?", (pogovor_id, kanal_id))
            c = self.db.execute("UPDATE sporocila SET stanje='prebrano' WHERE kanal_id=? AND pogovor_id=? AND smer='noter' "
                                "AND stanje='prejeto'", (kanal_id, pogovor_id))
            if c.rowcount:
                # Znacka takoj (streznik potrdi ob naslednji uskladitvi, pri IDLE v delcu sekunde).
                self.db.execute("UPDATE kanal_neprebrano SET stevilo=MAX(0, stevilo-?) WHERE kanal_id=?",
                                (c.rowcount, kanal_id))
        adapter = self.adapterji.get(kanal_id)
        if not adapter:
            return

        def na_strezniku():
            try:
                with self._zaklep_kanala(kanal_id):
                    adapter.oznaci_prebrano(pogovor_id)
            except Exception:
                pass
        if self._delavci:
            # Niti kanalov tecejo: streznik izve v ozadju, vmesnik ne caka na morebitno sinhronizacijo kanala.
            threading.Thread(target=na_strezniku, name="safeer-sporocila-prebrano", daemon=True).start()
        else:
            na_strezniku()

    def odstrani_kanal(self, kanal_id: str) -> None:
        self.ustavi_kanal(kanal_id)
        adapter = self.adapterji.pop(kanal_id, None)
        for metoda in ("pozabi_geslo", "pozabi_zeton", "zapri"):
            if adapter is not None and hasattr(adapter, metoda):
                try:
                    getattr(adapter, metoda)()
                except Exception:
                    pass
        with self._zaklep, self.db:
            for tabela in ("kanali", "kanal_stanje"):
                self.db.execute("DELETE FROM %s WHERE id=?" % tabela, (kanal_id,))
            self.db.execute("DELETE FROM pogovori WHERE kanal_id=?", (kanal_id,))
            self.db.execute("DELETE FROM sporocila WHERE kanal_id=?", (kanal_id,))   # sprozilec pocisti tudi iskalni indeks
            for tabela in ("odhodni", "sporocila_polno", "kanal_neprebrano", "oznake"):
                self.db.execute("DELETE FROM %s WHERE kanal_id=?" % tabela, (kanal_id,))
        self._izklopljeni.discard(kanal_id)
        # Osebe, ki so ostale brez vsakega pogovora, izginejo skupaj s kanalom.
        with self.graf._zaklep, self.graf._db:
            self.graf._db.execute("DELETE FROM identitete WHERE oseba_id NOT IN (SELECT DISTINCT oseba_id FROM pogovori)")
            self.graf._db.execute("DELETE FROM osebe WHERE id NOT IN (SELECT DISTINCT oseba_id FROM pogovori)")

    def _oseba(self, vrsta: str, vrednost: str, ime: str = "") -> str:
        tip = "email" if vrsta == "email" and "@" in vrednost else ("telefon" if vrednost.startswith("+") else vrsta)
        return self.graf.dodaj(ime.strip(), [(tip, vrednost)]).id

    def _shrani_sporocilo(self, kanal_id: str, s: Sporocilo):
        """Vstavi ali posodobi (vrstica obdrzi rowid - indeks iskanja ostane uskladen). Prebrano tu ostane prebrano:
        Matrix in Telegram ob vsaki sinhronizaciji vrneta tudi starejsa sporocila z oznako »prejeto«; stanje iz
        streznika (oznake IMAP) gre posebej v _sinhroniziraj_en."""
        priponke = json.dumps(s.priponke, ensure_ascii=False)
        self.db.execute("""INSERT INTO sporocila(id,pogovor_id,kanal_id,smer,besedilo,cas,priponke,stanje) VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(id,kanal_id) DO UPDATE SET pogovor_id=excluded.pogovor_id, smer=excluded.smer,
              besedilo=excluded.besedilo, cas=excluded.cas, priponke=excluded.priponke,
              stanje=CASE WHEN sporocila.stanje='prebrano' AND excluded.stanje='prejeto' THEN 'prebrano' ELSE excluded.stanje END
            WHERE sporocila.pogovor_id IS NOT excluded.pogovor_id OR sporocila.smer IS NOT excluded.smer
              OR sporocila.besedilo IS NOT excluded.besedilo OR sporocila.cas IS NOT excluded.cas
              OR sporocila.priponke IS NOT excluded.priponke
              OR (sporocila.stanje IS NOT excluded.stanje AND NOT (sporocila.stanje='prebrano' AND excluded.stanje='prejeto'))""",
            (s.id, s.pogovor_id, kanal_id, s.smer, s.besedilo, s.cas, priponke, s.stanje))

    def pogovori(self, kanal: str = ""):
        sql = "SELECT * FROM pogovori"
        args = ()
        if kanal: sql += " WHERE kanal_id=?"; args = (kanal,)
        sql += " ORDER BY CASE WHEN cas='' THEN 1 ELSE 0 END,cas DESC"
        with self._zaklep:
            return [Pogovor(r["id"], r["kanal_id"], r["oseba_id"], r["zadeva"],
                             r["zadnje_sporocilo"], r["neprebrano"], r["cas"])
                    for r in self.db.execute(sql, args)]

    # ---- oznake pogovorov (uporabnikove; lokalno) ----
    def oznake_pogovorov(self) -> dict:
        with self._zaklep:
            izid: dict = {}
            for r in self.db.execute("SELECT kanal_id,pogovor_id,oznaka FROM oznake ORDER BY oznaka COLLATE NOCASE"):
                izid.setdefault((r["kanal_id"], r["pogovor_id"]), []).append(r["oznaka"])
            return izid

    def vse_oznake(self) -> list:
        with self._zaklep:
            return [r[0] for r in self.db.execute("SELECT DISTINCT oznaka FROM oznake ORDER BY oznaka COLLATE NOCASE")]

    def nastavi_oznake(self, kanal_id: str, pogovor_id: str, oznake) -> list:
        ciste = []
        for o in oznake or []:
            o = str(o).strip()[:40]
            if o and o.casefold() not in {c.casefold() for c in ciste}:
                ciste.append(o)
        with self._zaklep, self.db:
            self.db.execute("DELETE FROM oznake WHERE kanal_id=? AND pogovor_id=?", (kanal_id, pogovor_id))
            self.db.executemany("INSERT OR IGNORE INTO oznake VALUES(?,?,?)", [(kanal_id, pogovor_id, o) for o in ciste])
        return ciste

    def zdruzi_osebi(self, cilj_id: str, drugi_id: str):
        """Drugo osebo zdruzi v cilj; njeni pogovori se preselijo k cilju."""
        oseba = self.graf.zdruzi(cilj_id, drugi_id)
        with self._zaklep, self.db:
            self.db.execute("UPDATE pogovori SET oseba_id=? WHERE oseba_id=?", (cilj_id, drugi_id))
        return oseba

    def razdruzi_osebo(self, oseba_id: str, identiteta, novo_ime: str = ""):
        """Identiteto (vrsta, naslov) izloci v novo osebo; pogovori te identitete gredo z njo."""
        nova = self.graf.razdruzi(oseba_id, [tuple(identiteta)], novo_ime)
        with self._zaklep, self.db:
            self.db.execute("UPDATE pogovori SET oseba_id=? WHERE oseba_id=? AND (identiteta=? OR id=?)",
                            (nova.id, oseba_id, str(identiteta[1]), str(identiteta[1])))
        return nova

    def zdruzeni_pogovori(self, kanal: str = ""):
        skupine = []
        po_osebi = {}
        oznake = self.oznake_pogovorov()
        for p in self.pogovori(kanal):
            if p.oseba_id not in po_osebi:
                oseba = self.graf.oseba(p.oseba_id)
                vnos = {"oseba": oseba.slovar() if oseba else {"id": p.oseba_id, "ime": p.oseba_id, "identitete": []},
                        "pogovori": [], "cas": p.cas, "neprebrano": 0}
                po_osebi[p.oseba_id] = vnos; skupine.append(vnos)
            slovar = p.slovar(); slovar["oznake"] = oznake.get((p.kanal_id, p.id), [])
            po_osebi[p.oseba_id]["pogovori"].append(slovar)
            po_osebi[p.oseba_id]["neprebrano"] += p.neprebrano
        return skupine

    def isci_sporocila(self, niz: str, oseba_id: str = "", kanal_id: str = "", pogovor_id: str = "", najvec: int = 60) -> list:
        """Iskanje po besedilu sporocil (in zadevi ter imenu posiljatelja): znotraj ene osebe (vsi njeni pogovori po
        kanalih) ali enega pogovora. Vrne najnovejsa najprej, z zadetkom v 'izsek'.

        Iskanje po besedah in njihovih zacetkih, brez razlike c/č (kot FTS5 unicode61 remove_diacritics). Znotraj
        osebe ali pogovora (do PREGLED_NAJVEC sporocil) preverimo kar sporocila te osebe - hitreje od indeksa, ki bi
        nasel vse zadetke v bazi; sicer indeks FTS5, od najnovejsih naprej. Meritev na 50 000 sporocilih
        (15. 10. 2026): v sporocilu commita. Brez FTS5 ali brez besed v nizu (samo locila) ostane LIKE."""
        n = str(niz).strip()
        if not n:
            return []
        besede = [_zlozi(b) for b in _BESEDA.findall(n)]
        meja = max(1, min(int(najvec), 200))
        filtri, fargs = "", []
        if oseba_id: filtri += " AND p.oseba_id=?"; fargs.append(str(oseba_id))
        if kanal_id: filtri += " AND s.kanal_id=?"; fargs.append(str(kanal_id))
        if pogovor_id: filtri += " AND s.pogovor_id=?"; fargs.append(str(pogovor_id))
        izbor = "SELECT s.*, p.oseba_id AS oseba_id, p.zadeva AS zadeva"
        zdruzi = " JOIN pogovori p ON p.id=s.pogovor_id AND p.kanal_id=s.kanal_id"
        vrstice = None
        if self.fts and besede and filtri:
            with self._zaklep:
                kandidatov = self.db.execute("SELECT COUNT(*) FROM sporocila s" + zdruzi + " WHERE 1" + filtri, fargs).fetchone()[0]
                if kandidatov <= PREGLED_NAJVEC:
                    vse = self.db.execute(izbor + ", COALESCE(o.ime,'') AS ime_osebe FROM sporocila s" + zdruzi +
                                          " LEFT JOIN osebe o ON o.id=p.oseba_id WHERE 1" + filtri +
                                          " ORDER BY s.cas DESC, s.rowid DESC", fargs).fetchall()
                    vrstice = []
                    for r in vse:
                        if _ujema(besede, (r["besedilo"] or "") + " " + (r["zadeva"] or "") + " " + r["ime_osebe"]):
                            vrstice.append(r)
                            if len(vrstice) >= meja:
                                break
        if vrstice is None and self.fts and besede:
            poizvedba = " ".join('"%s"*' % b.replace('"', '""') for b in besede)
            try:
                with self._zaklep:
                    # ORDER BY rowid: indeks vrne zadetke od najnovejsih in se ustavi pri meji (2 ms namesto 80 ms za
                    # pogosto besedo); rowid sledi prihodu, koncni vrstni red po casu uredimo spodaj.
                    vrstice = self.db.execute(izbor + " FROM sporocila_fts f JOIN sporocila s ON s.rowid=f.rowid" + zdruzi +
                                              " WHERE sporocila_fts MATCH ?" + filtri + " ORDER BY f.rowid DESC LIMIT ?",
                                              [poizvedba] + fargs + [meja]).fetchall()
                vrstice.sort(key=lambda r: r["cas"] or "", reverse=True)     # stabilno: enak cas ostane po prihodu
            except sqlite3.OperationalError:
                vrstice = None
        if vrstice is None:
            vzorec = "%" + n.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            with self._zaklep:
                vrstice = self.db.execute(izbor + " FROM sporocila s" + zdruzi + " WHERE s.besedilo LIKE ? ESCAPE '\\'"
                                          + filtri + " ORDER BY s.cas DESC, s.rowid DESC LIMIT ?", [vzorec] + fargs + [meja]).fetchall()
        izid = []
        for r in vrstice:
            b = r["besedilo"] or ""
            mali = b.casefold()
            i = mali.find(n.casefold())
            if i < 0 and besede:
                i = _zlozi(b).find(besede[0])
            zac = max(0, i - 40) if i >= 0 else 0
            izid.append({"id": r["id"], "pogovor_id": r["pogovor_id"], "kanal_id": r["kanal_id"], "oseba_id": r["oseba_id"],
                         "smer": r["smer"], "cas": r["cas"], "zadeva": r["zadeva"] or "",
                         "izsek": ("…" if zac else "") + b[zac:zac + 160] + ("…" if len(b) > zac + 160 else "")})
        return izid

    # ------------------------------------------------------------------ predpomnilnik: neprebrana, celotna pisma, ciscenje
    def neprebrano_po_kanalih(self) -> Dict[str, int]:
        """Zadnje znano stevilo neprebranih po kanalih - iz baze, zato je kuverta prava ze ob zagonu, preden se
        katerikoli kanal poveze. Kanali, ki jih ne steje ta baza (vgrajen spletni klepet), ga sporocijo z
        nastavi_neprebrano_kanala."""
        with self._zaklep:
            izid = {r[0]: int(r[1] or 0) for r in self.db.execute(
                "SELECT kanal_id, SUM(neprebrano) FROM pogovori GROUP BY kanal_id")}
            for r in self.db.execute("SELECT kanal_id, stevilo FROM kanal_neprebrano"):
                izid[r[0]] = int(r[1] or 0)
        return izid

    def neprebrano_skupaj(self) -> int:
        return sum(self.neprebrano_po_kanalih().values())

    def nastavi_neprebrano_kanala(self, kanal_id: str, stevilo: int) -> None:
        with self._zaklep, self.db:
            c = self._zapisi_neprebrano_kanala(kanal_id, stevilo)
        if c.rowcount > 0:
            self._sporoci()

    def _zapisi_neprebrano_kanala(self, kanal_id: str, stevilo: int):
        return self.db.execute("""INSERT INTO kanal_neprebrano VALUES(?,?,?) ON CONFLICT(kanal_id) DO UPDATE SET
            stevilo=excluded.stevilo, cas=excluded.cas WHERE kanal_neprebrano.stevilo IS NOT excluded.stevilo""",
            (str(kanal_id), max(0, int(stevilo or 0)), datetime.now(timezone.utc).replace(microsecond=0).isoformat()))

    def dopolni_besedila(self, kanal_id: str, ids: Iterable[str]) -> int:
        """Pisma, prirezana ob sinhronizaciji na 64 KB: celotno besedilo prenese enkrat in shrani, da je pismo
        pozneje berljivo tudi brez povezave. Vrne stevilo dopolnjenih."""
        adapter = self.adapterji.get(kanal_id)
        if getattr(adapter, "vrsta", "") != "email" or not hasattr(adapter, "imap_streznik"):
            return 0
        with self._zaklep:
            ze = {r[0] for r in self.db.execute("SELECT id FROM sporocila_polno WHERE kanal_id=?", (kanal_id,))}
        uidi = {}
        for sid in ids:
            if sid.startswith("uid:") and sid not in ze and sid[4:].isdigit():
                uidi[int(sid[4:])] = sid
        if not uidi:
            return 0
        from . import imap_sprotno
        with self._zaklep_kanala(kanal_id):
            besedila = imap_sprotno.polna_besedila(adapter, uidi)
        dopolnjeno = 0
        with self._zaklep, self.db:
            if self.adapterji.get(kanal_id) is not adapter:
                return 0
            for uid, besedilo in besedila.items():
                sid = uidi[uid]
                if besedilo:
                    c = self.db.execute("UPDATE sporocila SET besedilo=? WHERE id=? AND kanal_id=? AND besedilo IS NOT ?",
                                        (besedilo, sid, kanal_id, besedilo))
                    dopolnjeno += c.rowcount
                    if c.rowcount:
                        r = self.db.execute("SELECT pogovor_id FROM sporocila WHERE id=? AND kanal_id=?", (sid, kanal_id)).fetchone()
                        if r:
                            self._nova_razlicica(kanal_id, r[0])
                self.db.execute("INSERT OR IGNORE INTO sporocila_polno VALUES(?,?)", (kanal_id, sid))
        if dopolnjeno:
            self._sporoci()
        return dopolnjeno

    def pocisti_predpomnilnik(self, dni: int = HRANI_DNI, najvec_mb: float = NAJVEC_MB) -> int:
        """Samo lokalni predpomnilnik (na strezniku ostane vse): sporocila, starejsa od `dni`, in najstarejsa, dokler
        baza ne pade pod `najvec_mb`. Cakajoca (neposlana) sporocila ostanejo. Vrne stevilo izbrisanih."""
        meja = (datetime.now(timezone.utc) - timedelta(days=int(dni))).replace(microsecond=0).isoformat()
        izbrisano = 0
        with self._zaklep, self.db:
            izbrisano += self.db.execute("DELETE FROM sporocila WHERE cas<>'' AND cas<? AND stanje NOT IN ('caka','napaka')",
                                         (meja,)).rowcount
        while True:
            with self._zaklep:
                strani = self.db.execute("PRAGMA page_count").fetchone()[0] - self.db.execute("PRAGMA freelist_count").fetchone()[0]
                velikost = strani * self.db.execute("PRAGMA page_size").fetchone()[0]
            if velikost <= najvec_mb * 1024 * 1024:
                break
            with self._zaklep, self.db:
                n = self.db.execute("""DELETE FROM sporocila WHERE rowid IN (SELECT rowid FROM sporocila
                    WHERE stanje NOT IN ('caka','napaka') ORDER BY cas LIMIT 1000)""").rowcount
            if not n:
                break
            izbrisano += n
        if izbrisano:
            with self._zaklep, self.db:
                self.db.execute("DELETE FROM sporocila_polno WHERE NOT EXISTS (SELECT 1 FROM sporocila s "
                                "WHERE s.kanal_id=sporocila_polno.kanal_id AND s.id=sporocila_polno.id)")
                for kid in [r[0] for r in self.db.execute("SELECT id FROM kanali")]:
                    if hasattr(self.adapterji.get(kid), "obnovi"):
                        self._preracunaj_neprebrano(kid)
        return izbrisano

    def zadnje_smeri(self) -> dict:
        """(kanal_id, pogovor_id) -> smer zadnjega sporocila ('noter'/'ven'); za mapo Poslano v nabiralniku."""
        with self._zaklep:
            vrstice = self.db.execute("""SELECT kanal_id, pogovor_id, smer FROM sporocila WHERE rowid IN
                (SELECT MAX(rowid) FROM sporocila GROUP BY kanal_id, pogovor_id)""").fetchall()
        return {(r["kanal_id"], r["pogovor_id"]): r["smer"] for r in vrstice}

    def sporocila(self, kanal_id: str, pogovor_id: str, najvec: int = 50):
        with self._zaklep:
            # Enak cas (e-posta ima natancnost sekunde): vrstni red prihoda (rowid) odloci.
            vrstice = self.db.execute("""SELECT * FROM sporocila WHERE kanal_id=? AND pogovor_id=?
                ORDER BY cas DESC, rowid DESC LIMIT ?""", (kanal_id, pogovor_id, max(1, min(int(najvec), 200)))).fetchall()
        return [Sporocilo(r["id"], r["pogovor_id"], r["smer"], r["besedilo"], r["cas"],
                          json.loads(r["priponke"] or "[]"), r["stanje"]) for r in reversed(vrstice)]

    # ------------------------------------------------------------------ posiljanje in odhodna vrsta
    @staticmethod
    def _nov_idem(adapter) -> str:
        if getattr(adapter, "vrsta", "") == "email":
            from email.utils import make_msgid
            return make_msgid(domain=str(getattr(adapter, "naslov", "")).rsplit("@", 1)[-1] or None)
        return "safeer-" + uuid.uuid4().hex

    @staticmethod
    def _klic_poslji(adapter, pogovor_id: str, besedilo: str, priponke, idem: str) -> Sporocilo:
        import inspect
        try:
            zna_idem = "idem" in inspect.signature(adapter.poslji).parameters
        except (TypeError, ValueError):
            zna_idem = False
        if zna_idem:
            return adapter.poslji(pogovor_id, besedilo, priponke, idem=idem)
        return adapter.poslji(pogovor_id, besedilo, priponke)

    def _zaklep_odhodnih(self, kanal_id: str) -> threading.Lock:
        with self._zaklep:
            return self._zaklepi_odhodnih.setdefault(kanal_id, threading.Lock())

    def poslji(self, kanal_id: str, pogovor_id: str, besedilo: str, priponke=()):
        """Poslje takoj; brez povezave sporocilo pocaka v odhodni vrsti (stanje »caka«, v pogovoru z uro) in odide
        samo, ko se kanal spet poveze - v vrstnem redu in enkrat. Zavrnjeno (prejemnik, prijava) gre takoj nazaj."""
        adapter = self.adapterji[kanal_id]
        with self._zaklep:
            ze_caka = self.db.execute("SELECT 1 FROM odhodni WHERE kanal_id=? LIMIT 1", (kanal_id,)).fetchone()
        idem = self._nov_idem(adapter)
        if ze_caka:
            # Ze cakajoca sporocila morajo oditi prej (vrstni red v pogovoru).
            s = self._v_vrsto(kanal_id, pogovor_id, besedilo, priponke, idem)
            self._zbudi_kanal(kanal_id)
            return s
        try:
            s = self._klic_poslji(adapter, pogovor_id, besedilo, priponke, idem)
        except Exception as napaka:
            if not _je_omrezna(napaka):
                raise
            s = self._v_vrsto(kanal_id, pogovor_id, besedilo, priponke, idem)
            self.oznaci_stanje(kanal_id, "napaka:omrezje")
            self._zbudi_kanal(kanal_id)
            return s
        with self._zaklep, self.db:
            self._shrani_sporocilo(kanal_id, s)
            self.db.execute("UPDATE pogovori SET zadnje_sporocilo=?,cas=? WHERE id=? AND kanal_id=?",
                            (besedilo[:240], s.cas, pogovor_id, kanal_id))
        return s

    def _v_vrsto(self, kanal_id: str, pogovor_id: str, besedilo: str, priponke, idem: str) -> Sporocilo:
        oid = uuid.uuid4().hex
        cas = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        s = Sporocilo("caka:" + oid, pogovor_id, "ven", besedilo, cas, list(priponke or []), "caka")
        with self._zaklep, self.db:
            self.db.execute("INSERT INTO odhodni(id,kanal_id,pogovor_id,besedilo,priponke,idem,ustvarjeno,stanje) "
                            "VALUES(?,?,?,?,?,?,?,?)",
                            (oid, kanal_id, pogovor_id, besedilo, json.dumps(list(priponke or []), ensure_ascii=False),
                             idem, time.time(), "caka"))
            self._shrani_sporocilo(kanal_id, s)
            self.db.execute("UPDATE pogovori SET zadnje_sporocilo=?,cas=? WHERE id=? AND kanal_id=?",
                            (besedilo[:240], cas, pogovor_id, kanal_id))
        return s

    def cakajoca(self, kanal_id: str = "") -> list:
        with self._zaklep:
            vrstice = self.db.execute("SELECT * FROM odhodni WHERE (?='' OR kanal_id=?) ORDER BY ustvarjeno, rowid",
                                      (kanal_id, kanal_id)).fetchall()
        return [dict(r) for r in vrstice]

    def preklici_cakajoce(self, kanal_id: str, sporocilo_id: str) -> bool:
        """Uporabnik preklice neposlano sporocilo. Ce se ze posilja, je prepozno (False)."""
        oid = str(sporocilo_id)[5:] if str(sporocilo_id).startswith("caka:") else ""
        if not oid:
            return False
        with self._zaklep, self.db:
            c = self.db.execute("DELETE FROM odhodni WHERE id=? AND kanal_id=? AND stanje='caka'", (oid, kanal_id))
            if c.rowcount == 0:
                # Ze zavrnjeno (stanje 'napaka'): sporocilo samo odstranimo iz pogovora.
                c2 = self.db.execute("DELETE FROM sporocila WHERE id=? AND kanal_id=? AND stanje='napaka'",
                                     (str(sporocilo_id), kanal_id))
                return c2.rowcount > 0
            r = self.db.execute("SELECT pogovor_id FROM sporocila WHERE id=? AND kanal_id=?", (str(sporocilo_id), kanal_id)).fetchone()
            self.db.execute("DELETE FROM sporocila WHERE id=? AND kanal_id=?", (str(sporocilo_id), kanal_id))
            if r:
                self._nova_razlicica(kanal_id, r[0])
        self._sporoci()
        return True

    def poslji_cakajoce(self, kanal_id: str) -> int:
        """Odpre vrsto kanala: sporocila v vrstnem redu, vsako enkrat. Ob prvi omrezni napaki se ustavi (naslednja
        povezava nadaljuje); zavrnjeno sporocilo dobi stanje »napaka« in ne zadrzi ostalih. Vrne stevilo poslanih
        in zavrnjenih (sprememb v pogovorih)."""
        adapter = self.adapterji.get(kanal_id)
        if adapter is None:
            return 0
        zaklep = self._zaklep_odhodnih(kanal_id)
        if not zaklep.acquire(blocking=False):
            return 0                        # vrsto ze prazni druga nit
        poslanih = 0
        try:
            while True:
                with self._zaklep, self.db:
                    r = self.db.execute("SELECT * FROM odhodni WHERE kanal_id=? AND stanje='caka' "
                                        "ORDER BY ustvarjeno, rowid LIMIT 1", (kanal_id,)).fetchone()
                    if r is None:
                        return poslanih
                    self.db.execute("UPDATE odhodni SET stanje='posiljam', poskus=? WHERE id=?", (time.time(), r["id"]))
                try:
                    s = self._klic_poslji(adapter, r["pogovor_id"], r["besedilo"], json.loads(r["priponke"] or "[]"), r["idem"])
                except Exception as napaka:
                    with self._zaklep, self.db:
                        if _je_omrezna(napaka):
                            self.db.execute("UPDATE odhodni SET stanje='caka' WHERE id=?", (r["id"],))
                            return poslanih
                        self.db.execute("DELETE FROM odhodni WHERE id=?", (r["id"],))
                        self.db.execute("UPDATE sporocila SET stanje='napaka' WHERE id=? AND kanal_id=?",
                                        ("caka:" + r["id"], kanal_id))
                        self._nova_razlicica(kanal_id, r["pogovor_id"])
                    poslanih += 1
                    continue
                with self._zaklep, self.db:
                    self.db.execute("DELETE FROM odhodni WHERE id=?", (r["id"],))
                    self.db.execute("DELETE FROM sporocila WHERE id=? AND kanal_id=?", ("caka:" + r["id"], kanal_id))
                    if self.adapterji.get(kanal_id) is adapter:
                        self._shrani_sporocilo(kanal_id, s)
                    self._nova_razlicica(kanal_id, r["pogovor_id"])
                poslanih += 1
        finally:
            zaklep.release()

    def _zbudi_kanal(self, kanal_id: str) -> None:
        d = self._delavci.get(kanal_id)
        if d is not None:
            try:
                d.zbudi()
            except Exception:  # noqa: BLE001
                pass

    def novo(self, kanal_id: str, prejemnik: str, zadeva: str, besedilo: str):
        """Novo e-sporocilo osebi, s katero morda se ni pogovora: poslje ga in pogovor doda v nabiralnik."""
        adapter = self.adapterji[kanal_id]
        if getattr(adapter, "vrsta", "") != "email":
            raise ValueError("Novo sporočilo zna samo e-pošta")
        s = adapter.poslji(prejemnik, besedilo, (), zadeva_nova=zadeva)
        oseba_id = self._oseba("email", prejemnik, "")
        with self._zaklep, self.db:
            self.db.execute("INSERT OR IGNORE INTO pogovori(id,kanal_id,oseba_id,zadeva,zadnje_sporocilo,neprebrano,cas,identiteta) "
                            "VALUES(?,?,?,?,?,0,?,?)", (prejemnik, kanal_id, oseba_id, zadeva, "", s.cas, prejemnik))
            self._shrani_sporocilo(kanal_id, s)
            self.db.execute("UPDATE pogovori SET zadeva=?,zadnje_sporocilo=?,cas=? WHERE id=? AND kanal_id=?",
                            (zadeva, besedilo[:240], s.cas, prejemnik, kanal_id))
            if hasattr(adapter, "stanje"):
                self.db.execute("INSERT OR REPLACE INTO kanal_stanje VALUES(?,?)",
                                (kanal_id, json.dumps(adapter.stanje(), ensure_ascii=False)))
        return s

    # ------------------------------------------------------------------ niti kanalov
    def zazeni(self) -> None:
        """Zazene nit vsakega kanala (razen izklopljenih), spremljanje omrezja in dnevno ciscenje predpomnilnika."""
        self._tece = True
        for kid in list(self.adapterji):
            if kid not in self._izklopljeni:
                self._zazeni_delavca(kid, na_novo=False)
        self._spremljaj_omrezje()
        if not getattr(self, "_nit_ciscenja", None) or not self._nit_ciscenja.is_alive():
            self._ciscenje.clear()

            def ciscenje():
                while not self._ciscenje.wait(60 if not getattr(self, "_ociscen", False) else 24 * 3600):
                    try:
                        self.pocisti_predpomnilnik()
                    except Exception as e:  # noqa: BLE001
                        print("[Sporocila] ciscenje:", type(e).__name__, flush=True)
                    self._ociscen = True
            self._nit_ciscenja = threading.Thread(target=ciscenje, name="safeer-sporocila-ciscenje", daemon=True)
            self._nit_ciscenja.start()

    def _zazeni_delavca(self, kanal_id: str, na_novo: bool = True) -> None:
        from . import sprotno
        adapter = self.adapterji.get(kanal_id)
        if adapter is None:
            return
        d = self._delavci.get(kanal_id)
        if d is not None and d.tece() and d.adapter is adapter:
            if na_novo:
                d.ponovno_povezi()
            return
        if d is not None:
            d.ustavi(0.5)
        d = sprotno.ustvari(self, kanal_id, adapter, self.interval)
        self._delavci[kanal_id] = d
        d.zazeni()

    def zazeni_kanal(self, kanal_id: str) -> None:
        """Vklopi kanal (stikalo v nastavitvah): nit se zazene in takoj sinhronizira."""
        self._izklopljeni.discard(kanal_id)
        self._zazeni_delavca(kanal_id)

    def ustavi_kanal(self, kanal_id: str) -> None:
        """Izklopi kanal: nit se ustavi, povezave se zaprejo. Predpomnilnik ostane (berljiv brez povezave)."""
        self._izklopljeni.add(kanal_id)
        d = self._delavci.pop(kanal_id, None)
        if d is not None:
            d.ustavi()
        adapter = self.adapterji.get(kanal_id)
        if adapter is not None and hasattr(adapter, "zapri"):
            self._zapri_adapter(kanal_id, adapter)

    def _zapri_adapter(self, kanal_id: str, adapter) -> None:
        """Zapre povezavo adapterja. Ce kanal se sinhronizira (pocasen streznik), povezavo zapremo brez cakanja."""
        zaklep = self._zaklep_kanala(kanal_id)
        if zaklep.acquire(timeout=1.0):
            try:
                adapter.zapri()
            except Exception:  # noqa: BLE001
                pass
            finally:
                zaklep.release()
            return
        imap = getattr(adapter, "_imap", None)
        if imap is not None:
            try:
                imap.shutdown()
            except Exception:  # noqa: BLE001
                pass

    def osvezi(self) -> None:
        """Gumb »Osvezi«: kanali z nitjo se sinhronizirajo v njej (vmesnik ne caka), ostali takoj."""
        for kid in list(self.adapterji):
            d = self._delavci.get(kid)
            if d is not None and d.tece():
                d.zbudi()
            elif kid not in self._izklopljeni:
                n, uspeh, _s = self._sinhroniziraj_en(kid)
                if uspeh:
                    self.poslji_cakajoce(kid)
        self._sporoci()

    def ob_spremembi_omrezja(self) -> None:
        """Novo omrezje ali prebujenje: vsi kanali takoj na novo (brez cakanja na zamik po napaki)."""
        for d in list(self._delavci.values()):
            try:
                d.ponovno_povezi()
            except Exception:  # noqa: BLE001
                pass

    def _spremljaj_omrezje(self) -> None:
        if self._omrezje is not None:
            return
        try:
            from gi.repository import Gio
            monitor = Gio.NetworkMonitor.get_default()
            stanje = {"dosegljivo": monitor.get_network_available(), "ob": -1e9}

            def sprememba(_m, dosegljivo):
                # Signal pride ob vsaki spremembi poti (tudi VPN, vsebniki): ob vrnitvi omrezja takoj, sicer najvec
                # enkrat na 15 s - nove povezave so poceni (TLS + prijava), pozabljena mrtva pa bi zadrzala sporocila.
                zdaj = time.monotonic()
                if dosegljivo and (not stanje["dosegljivo"] or zdaj - stanje["ob"] >= 15):
                    stanje["ob"] = zdaj
                    self.ob_spremembi_omrezja()
                stanje["dosegljivo"] = dosegljivo
            self._omrezje = (monitor, monitor.connect("network-changed", sprememba))
        except Exception:  # noqa: BLE001 - brez GLib zanke ali Gio: zaznava spanja v niti IMAP ostane
            self._omrezje = None

    def ustavi(self) -> None:
        """Ustavi vse niti in zapre povezave (Sporocila izklopljena ali konec programa)."""
        self._tece = False
        self._ciscenje.set()
        delavci, self._delavci = list(self._delavci.items()), {}
        for _kid, d in delavci:
            d.ustavi()
        for kid, adapter in list(self.adapterji.items()):
            if hasattr(adapter, "zapri"):
                self._zapri_adapter(kid, adapter)
            # Zadnje stanje (Matrix since, IMAP modseq) - med delom se zapisuje najvec vsakih 5 min. Samo kanali,
            # ki so stanje ze prebrali: prazno stanje novega adapterja ne sme prepisati shranjenega.
            if kid in self._obnovljeni and hasattr(adapter, "stanje"):
                try:
                    with self._zaklep, self.db:
                        self.db.execute("INSERT OR REPLACE INTO kanal_stanje VALUES(?,?)",
                                        (kid, json.dumps(adapter.stanje(), ensure_ascii=False)))
                except Exception:  # noqa: BLE001 - baza je morda ze zaprta
                    pass
        if self._omrezje is not None:
            try:
                self._omrezje[0].disconnect(self._omrezje[1])
            except Exception:  # noqa: BLE001
                pass
            self._omrezje = None

    def delavci(self) -> Dict[str, str]:
        """{kanal_id: vrsta niti} za kanale, katerih nit tece (preizkusi, diagnostika)."""
        return {k: d.vrsta for k, d in self._delavci.items() if d.tece()}

    def zapri(self):
        self.ustavi(); self.graf.zapri(); self.db.close()


Storitev = StoritevSporocil
