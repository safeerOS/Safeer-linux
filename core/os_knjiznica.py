"""Lokalna medijska knjižnica Safeer OS.

Datotek ne kopira in ne pregleduje domače mape brez uporabnikove izbire.
SQLite hrani le poti in osnovne podatke; manjkajoče datoteke ostanejo vidne,
da jih uporabnik lahko odstrani ali ponovno priklopi disk.
"""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit


GLASBA = frozenset({".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".oga", ".opus", ".wma"})
VIDEO = frozenset({".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".ogv", ".ts"})
SLIKE = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"})
PODPRTE = GLASBA | VIDEO | SLIKE
NAJVEC_V_MAPI = 5000


def vrsta_datoteke(pot: Path) -> str:
    koncnica = pot.suffix.lower()
    # DVD brez zaščite: slika ISO z VIDEO_TS ali mapa diska (VIDEO_TS.IFO) je film (core/os_dvd.py).
    if koncnica == ".iso" or pot.name.upper() == "VIDEO_TS.IFO":
        from core import os_dvd
        return "filmi" if os_dvd.je_dvd(str(pot)) else ""
    if koncnica in GLASBA:
        return "glasba"
    if koncnica in SLIKE:
        return "slike"
    if koncnica in VIDEO:
        epizoda = r"(?i)(?:^|[^a-z0-9])(?:S\d{1,2}E\d{1,2}|\d{1,2}x\d{1,2})(?:$|[^a-z0-9])"
        return "serije" if re.search(epizoda, pot.stem) else "filmi"
    return ""


def naslov_datoteke(pot: Path) -> str:
    if pot.suffix.lower() == ".iso" or pot.name.upper() == "VIDEO_TS.IFO":
        from core import os_dvd
        return os_dvd.naslov(str(pot))
    return re.sub(r"[._]+", " ", pot.stem).strip() or pot.name


class Knjiznica:
    def __init__(self, pot: str | Path | None = None):
        if pot is None:
            xdg = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
            pot = xdg / "safeer-os" / "mediji.sqlite3"
        self.pot = Path(pot)
        self.pot.parent.mkdir(parents=True, exist_ok=True)
        with self._baza() as baza:
            baza.execute("""CREATE TABLE IF NOT EXISTS mediji (
                pot TEXT PRIMARY KEY, naslov TEXT NOT NULL, vrsta TEXT NOT NULL,
                dodano INTEGER NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER)), zadnjic INTEGER NOT NULL DEFAULT 0,
                pozicija INTEGER NOT NULL DEFAULT 0, trajanje INTEGER NOT NULL DEFAULT 0
            )""")
            stolpci = {v[1] for v in baza.execute("PRAGMA table_info(mediji)")}
            for ime in ("pozicija", "trajanje"):
                if ime not in stolpci:
                    baza.execute(f"ALTER TABLE mediji ADD COLUMN {ime} INTEGER NOT NULL DEFAULT 0")
            baza.execute("CREATE INDEX IF NOT EXISTS mediji_vrsta ON mediji(vrsta, dodano DESC)")
            baza.execute("""CREATE TABLE IF NOT EXISTS tokovi (
                url TEXT PRIMARY KEY, ime TEXT NOT NULL, vrsta TEXT NOT NULL
                CHECK(vrsta IN ('tv', 'radio')),
                dodano INTEGER NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER))
            )""")
            baza.execute("""CREATE TABLE IF NOT EXISTS mape (
                pot TEXT PRIMARY KEY, dodano INTEGER NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER))
            )""")

    @contextmanager
    def _baza(self):
        baza = sqlite3.connect(self.pot, timeout=5)
        baza.create_function("safeer_casefold", 1, lambda s: str(s or "").casefold(), deterministic=True)
        try:
            with baza:
                yield baza
        finally:
            baza.close()

    def dodaj(self, poti) -> int:
        vnosi = []
        for surova in list(poti)[:NAJVEC_V_MAPI]:
            pot = Path(surova).expanduser().resolve()
            vrsta = vrsta_datoteke(pot)
            if vrsta and pot.is_file():
                vnosi.append((str(pot), naslov_datoteke(pot), vrsta))
        if not vnosi:
            return 0
        with self._baza() as baza:
            baza.executemany("""INSERT INTO mediji(pot, naslov, vrsta) VALUES (?, ?, ?)
                ON CONFLICT(pot) DO UPDATE SET naslov=excluded.naslov, vrsta=excluded.vrsta""", vnosi)
        return len(vnosi)

    def dodaj_mapo(self, mapa: str | Path) -> int:
        koren = Path(mapa).expanduser().resolve()
        if not koren.is_dir():
            return 0
        najdene = []
        for trenutna, podmape, datoteke in os.walk(koren, followlinks=False):
            podmape[:] = [d for d in podmape if not d.startswith(".") and not (Path(trenutna) / d).is_symlink()]
            for ime in datoteke:
                if ime.startswith("."):
                    continue
                pot = Path(trenutna) / ime
                if vrsta_datoteke(pot) and not pot.is_symlink():
                    najdene.append(pot)
                    if len(najdene) >= NAJVEC_V_MAPI:
                        break
            if len(najdene) >= NAJVEC_V_MAPI:
                break
        stevilo = self.dodaj(najdene)
        with self._baza() as baza:
            baza.execute("INSERT OR IGNORE INTO mape(pot) VALUES (?)", (str(koren),))
        return stevilo

    def seznam_map(self) -> list[str]:
        with self._baza() as baza:
            return [v[0] for v in baza.execute("SELECT pot FROM mape ORDER BY dodano, pot")]

    def osvezi_mape(self) -> int:
        """Po uporabnikovem ukazu poišče nove datoteke v izbranih mapah in pozabi izbrisane.

        Mapa, ki je trenutno ni (odklopljen disk), ostane nedotaknjena: njeni vnosi so le
        označeni kot nedosegljivi, dokler se disk ne vrne."""
        dodanih = 0
        for pot in self.seznam_map():
            koren = Path(pot)
            if not koren.is_dir():
                continue
            dodanih += self.dodaj_mapo(koren)
            predpona = str(koren).rstrip("/") + "/"
            with self._baza() as baza:
                poti = [v[0] for v in baza.execute("SELECT pot FROM mediji WHERE substr(pot, 1, ?) = ?",
                                                     (len(predpona), predpona))]
                izbrisane = [(p,) for p in poti if not Path(p).exists()]
                if izbrisane:
                    baza.executemany("DELETE FROM mediji WHERE pot=?", izbrisane)
        return dodanih

    def mape_podrobno(self) -> list[dict]:
        """Izbrane mape za upravljanje: pot, število vnosov, ali je mapa dosegljiva."""
        izhod = []
        for pot in self.seznam_map():
            predpona = pot.rstrip("/") + "/"
            with self._baza() as baza:
                stevilo = baza.execute("SELECT count(*) FROM mediji WHERE substr(pot, 1, ?) = ?",
                                       (len(predpona), predpona)).fetchone()[0]
            izhod.append({"pot": pot, "stevilo": stevilo, "naVoljo": Path(pot).is_dir()})
        return izhod

    def odstrani_mapo(self, pot: str) -> int | None:
        """Mapo odstrani iz knjižnice skupaj z njenimi vnosi; datotek na disku se ne dotakne.

        Vnosi, ki jih pokriva še druga izbrana mapa (nadmapa), ostanejo. Vrne število odstranjenih
        vnosov ali None, če mapa ni bila izbrana."""
        mape = self.seznam_map()
        if pot not in mape:
            return None
        predpona = pot.rstrip("/") + "/"
        ostale = [m.rstrip("/") + "/" for m in mape if m != pot]
        with self._baza() as baza:
            baza.execute("DELETE FROM mape WHERE pot=?", (pot,))
            poti = [v[0] for v in baza.execute("SELECT pot FROM mediji WHERE substr(pot, 1, ?) = ?",
                                                 (len(predpona), predpona))]
            brisi = [(p,) for p in poti if not any(p.startswith(o) for o in ostale)]
            baza.executemany("DELETE FROM mediji WHERE pot=?", brisi)
        return len(brisi)

    def seznam(self, vrsta: str = "", iskanje: str = "", meja: int = 120, odmik: int = 0) -> list[dict]:
        if vrsta in ("tv", "radio"):
            return []
        meja = max(1, min(int(meja), 240))
        odmik = max(0, min(int(odmik), NAJVEC_V_MAPI))
        pogoji, vrednosti = [], []
        if vrsta == "video":
            pogoji.append("vrsta IN ('filmi', 'serije')")
        elif vrsta in ("glasba", "filmi", "serije", "slike"):
            pogoji.append("vrsta = ?")
            vrednosti.append(vrsta)
        if iskanje:
            pogoji.append("instr(safeer_casefold(naslov), ?) > 0")
            vrednosti.append(str(iskanje)[:100].casefold())
        where = " WHERE " + " AND ".join(pogoji) if pogoji else ""
        with self._baza() as baza:
            vrstice = baza.execute("SELECT pot, naslov, vrsta, zadnjic, pozicija, trajanje FROM mediji" + where +
                                   " ORDER BY safeer_casefold(naslov), pot LIMIT ? OFFSET ?",
                                   (*vrednosti, meja, odmik)).fetchall()
        return [{"pot": p, "ime": n, "vrsta": v, "zadnjic": z, "pozicija": po,
                 "trajanje": tr, "naVoljo": Path(p).is_file()}
                for p, n, v, z, po, tr in vrstice]

    def predvajano(self, pot: str) -> None:
        with self._baza() as baza:
            baza.execute("UPDATE mediji SET zadnjic=CAST(strftime('%s','now') AS INTEGER) WHERE pot=?", (pot,))

    def dobi(self, pot: str) -> dict | None:
        with self._baza() as baza:
            vnos = baza.execute("SELECT pot, naslov, vrsta, pozicija, trajanje FROM mediji WHERE pot=?", (pot,)).fetchone()
        return {"pot": vnos[0], "ime": vnos[1], "vrsta": vnos[2],
                "pozicija": vnos[3], "trajanje": vnos[4]} if vnos else None

    def skladbe_iz_mape(self, pot: str, meja: int = 500) -> list[dict]:
        """Vse indeksirane skladbe iz mape izbrane skladbe (album), urejene po naslovu.

        Vrne celo mapo (do `meja` skladb okoli izbrane), da gumba naprej/nazaj delujeta
        tudi pri zadnji ali prvi skladbi; kje začeti, pove `izbrana` pri izbrani skladbi."""
        mapa = Path(pot).parent
        with self._baza() as baza:
            vrstice = baza.execute("SELECT pot, naslov FROM mediji WHERE vrsta='glasba'").fetchall()
        skladbe = sorted(((p, naslov) for p, naslov in vrstice if Path(p).parent == mapa and Path(p).is_file()),
                         key=lambda v: (v[1].casefold(), v[0]))
        meja = max(1, min(meja, 500))
        for indeks, (p, _) in enumerate(skladbe):
            if p == pot:
                od = max(0, min(indeks - meja // 2, len(skladbe) - meja))
                return [{"pot": p, "ime": naslov, "izbrana": p == pot} for p, naslov in skladbe[od:od + meja]]
        return []

    def shrani_napredek(self, pot: str, pozicija: float, trajanje: float) -> None:
        """Na koncu posnetka naslednje odpiranje začne od začetka."""
        pozicija, trajanje = max(0, int(pozicija)), max(0, int(trajanje))
        if trajanje <= 0:
            return
        pozicija = 0 if pozicija >= trajanje - 20 else min(pozicija, trajanje)
        with self._baza() as baza:
            baza.execute("""UPDATE mediji SET pozicija=?, trajanje=?
                WHERE pot=? AND vrsta IN ('filmi', 'serije')""", (pozicija, trajanje, pot))

    def ponastavi_napredek(self, pot: str) -> None:
        with self._baza() as baza:
            baza.execute("UPDATE mediji SET pozicija=0 WHERE pot=?", (pot,))

    def zadnji_nedokoncan(self) -> dict | None:
        """Nazadnje gledani film ali epizoda s shranjenim mestom - za »Nadaljuj z druge naprave«, ko tu nic ne igra
        (racunalnik je film ugasnil pri 1:02, telefon nadaljuje). Samo datoteka, ki je se na disku."""
        with self._baza() as baza:
            vrstice = baza.execute("""SELECT pot, naslov, vrsta, zadnjic, pozicija, trajanje FROM mediji
                WHERE pozicija > 0 AND trajanje > 0 AND vrsta IN ('filmi', 'serije')
                ORDER BY zadnjic DESC LIMIT 5""").fetchall()
        for p, n, v, z, po, tr in vrstice:
            if Path(p).is_file():
                return {"pot": p, "ime": n, "vrsta": v, "zadnjic": z, "pozicija": po, "trajanje": tr}
        return None

    def odstrani(self, pot: str) -> None:
        with self._baza() as baza:
            baza.execute("DELETE FROM mediji WHERE pot=?", (pot,))

    def dodaj_tok(self, ime: str, url: str, vrsta: str) -> None:
        ime, url = str(ime).strip(), str(url).strip()
        razcep = urlsplit(url)
        if (vrsta not in ("tv", "radio") or not 1 <= len(ime) <= 80 or
                len(url) > 2048 or razcep.scheme not in ("http", "https") or
                not razcep.hostname or any(c.isspace() for c in url)):
            raise ValueError("Neveljaven TV/radijski tok")
        with self._baza() as baza:
            if (not baza.execute("SELECT 1 FROM tokovi WHERE url=?", (url,)).fetchone() and
                    baza.execute("SELECT COUNT(*) FROM tokovi").fetchone()[0] >= 300):
                raise ValueError("Največ 300 shranjenih postaj")
            baza.execute("""INSERT INTO tokovi(url, ime, vrsta) VALUES (?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET ime=excluded.ime, vrsta=excluded.vrsta""",
                (url, ime, vrsta))

    def tokovi(self) -> list[dict]:
        with self._baza() as baza:
            vrstice = baza.execute("SELECT url, ime, vrsta FROM tokovi ORDER BY dodano DESC, ime LIMIT 300").fetchall()
        return [{"url": url, "ime": ime, "vrsta": vrsta} for url, ime, vrsta in vrstice]

    def dobi_tok(self, url: str) -> dict | None:
        with self._baza() as baza:
            vnos = baza.execute("SELECT url, ime, vrsta FROM tokovi WHERE url=?", (url,)).fetchone()
        return {"url": vnos[0], "ime": vnos[1], "vrsta": vnos[2]} if vnos else None

    def odstrani_tok(self, url: str) -> bool:
        with self._baza() as baza:
            return bool(baza.execute("DELETE FROM tokovi WHERE url=?", (url,)).rowcount)
