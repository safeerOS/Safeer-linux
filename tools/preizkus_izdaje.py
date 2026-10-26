#!/usr/bin/env python3
"""Naloga 86: en ovoj za preizkus izdaje (Linux .deb in naprave Android), ki javi SAMO napake in opozorila.

Uporaba (po gradnji, en ukaz):
    python3 tools/preizkus_izdaje.py --linux-deb MAPA_Z_DEB --android NAPRAVA=PAKET:APK [--android ...] --izhod porocilo.json
        [--rok SEKUNDE] [--razpakirano] [--repo KOREN_REPOZITORIJA]

Koraki (obstojeci preizkusi se klicejo kot podprocesi, njihove logike ovoj ne podvaja):
  Linux:   razpakiranje vsakega .deb (dpkg-deb -x v zacasno mapo, brez korena),
           utrjenost: vsaka .so in vsak program v paketu ima PT_GNU_STACK RW brez E in BIND_NOW (readelf -lW / -dW),
           packaging/smoke_webkit_deb.py (in packaging/smoke_brskalnik.py, ce obstaja) za vsak koren programa
           (usr/lib/<program> s core/zasebni_webkit.py) - privzeto nad namescenim paketom, ce je namescena ravno
           razlicica iz .deb; z --razpakirano nad razpakiranim drevesom.
  Android: tests/preizkus_po_gradnji.py NAPRAVA=PAKET --apk APK za vsako napravo (naprave vzporedno, vsaka pod
           zaklepom /tmp/safeer-naprava-<ip>.lock, pred dotikom preverba, da je v ospredju si.safeer.*).
Izpis: samo NAPAKA/OPOZORILO (ukaz, izhodna koda, zadnjih 30 vrstic) in vrstica »OK N / NAPAKA M«; porocilo JSON.
Izhod: 0 = ni napak (opozorila so dovoljena), 1 = vsaj ena napaka, 2 = napacni argumenti, 130 = prekinjeno.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import fcntl
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback

VRSTIC_IZPISA = 30
PRIVZET_ROK = 900.0
ROK_READELF = 60.0
ROK_ADB = 30.0
# Pot zaklepa je dogovor z drugimi skriptami (flock(1) in fcntl.flock uporabljata isti flock(2), zato se izkljucujeta).
ZAKLEP = "/tmp/safeer-naprava-{}.lock"
PREDPONA_PAKETA = "si.safeer."
# Preizkusi ne smejo dobiti korena ali zagnati pravih sistemskih programov na lastnikovem racunalniku.
PREPOVEDANI = {"sudo", "pkexec", "doas", "su", "run0"}
PREPOVEDANA_POT = "/usr/bin/safeer-"

OK, NAPAKA, OPOZORILO = "OK", "NAPAKA", "OPOZORILO"

_GNU_STACK = re.compile(r"^\s*GNU_STACK\s+(?:0x[0-9a-fA-F]+\s+){5}([RWE ]{3})\s+0x", re.M)
_OSPREDJE = (
    re.compile(r"(?:topResumedActivity|mResumedActivity|ResumedActivity)[:=]\s*ActivityRecord\{\S+ \S+ ([\w.]+)/"),
    re.compile(r"mCurrentFocus=Window\{\S+ \S+ ([\w.]+)/"),
    re.compile(r"mFocusedApp=\S*ActivityRecord\{\S+ \S+ ([\w.]+)/"),
)


class PrepovedanUkaz(Exception):
    pass


# ---------------------------------------------------------------------- porocilo

class Porocilo:
    """Zbira samo napake in opozorila; uspesni koraki so samo steti (in imenovani v JSON), da izpis ostane kratek."""

    def __init__(self) -> None:
        self._kljuc = threading.Lock()   # koraki Android tecejo v nitih
        self.ok: list[str] = []
        self.najdbe: list[dict] = []

    def uspeh(self, korak: str) -> None:
        with self._kljuc:
            self.ok.append(korak)

    def najdba(self, stanje: str, korak: str, sporocilo: str, ukaz=None, koda=None, izpis=None) -> None:
        with self._kljuc:
            self.najdbe.append({
                "stanje": stanje, "korak": korak, "sporocilo": sporocilo,
                "ukaz": " ".join(shlex.quote(str(x)) for x in ukaz) if ukaz else "",
                "izhodna_koda": koda,
                "izpis": list(izpis or [])[-VRSTIC_IZPISA:],
            })

    def napake(self) -> list[dict]:
        return [n for n in self.najdbe if n["stanje"] == NAPAKA]

    def opozorila(self) -> list[dict]:
        return [n for n in self.najdbe if n["stanje"] == OPOZORILO]

    def povzetek(self) -> str:
        s = "OK %d / NAPAKA %d" % (len(self.ok), len(self.napake()))
        return s + (" (opozoril %d)" % len(self.opozorila()) if self.opozorila() else "")

    def izpisi(self, tok=None) -> None:
        tok = tok or sys.stdout
        # Napake najprej: vodja jih mora videti, opozorila so samo v vednost.
        for n in self.napake() + self.opozorila():
            print("%s [%s]: %s" % (n["stanje"], n["korak"], n["sporocilo"]), file=tok)
            if n["ukaz"]:
                print("  ukaz: %s" % n["ukaz"], file=tok)
            if n["izhodna_koda"] is not None:
                print("  izhodna koda: %s" % n["izhodna_koda"], file=tok)
            for v in n["izpis"]:
                print("  | %s" % v, file=tok)
        print(self.povzetek(), file=tok, flush=True)

    def json(self, zacetek: float, argumenti: list[str]) -> dict:
        return {
            "zacetek": datetime.datetime.fromtimestamp(zacetek).astimezone().isoformat(timespec="seconds"),
            "trajanje_s": round(time.time() - zacetek, 1),
            "argumenti": argumenti,
            "ok": len(self.ok), "napake": len(self.napake()), "opozorila": len(self.opozorila()),
            "uspesni_koraki": sorted(self.ok),
            "najdbe": self.napake() + self.opozorila(),
        }


# ---------------------------------------------------------------------- podprocesi

_ZIVI: dict[int, subprocess.Popen] = {}
_ZIVI_KLJUC = threading.Lock()
# Po prekinitvi niti Android ne smejo zagnati novih procesov, ki jih nihce vec ne bi pospravil.
_USTAVI = threading.Event()


def preveri_ukaz(ukaz: list[str]) -> None:
    """Zavrne sudo/pkexec in /usr/bin/safeer-* kjerkoli v ukazu (tudi kot argument ovoja, npr. flock ... sudo)."""
    for i, del_ in enumerate(str(x) for x in ukaz):
        polna = (shutil.which(del_) or del_) if i == 0 else del_
        if os.path.basename(del_) in PREPOVEDANI or del_.startswith(PREPOVEDANA_POT) \
                or os.path.realpath(polna).startswith(PREPOVEDANA_POT):
            raise PrepovedanUkaz("prepovedan ukaz (sudo/pkexec ali %s*): %s" % (PREPOVEDANA_POT, shlex.join(map(str, ukaz))))


def _potomci(pid: int) -> list[int]:
    """PID vseh potomcev iz /proc - otroci, ki zamenjajo skupino procesov (setsid), ne smejo ostati zivi."""
    starsi: dict[int, int] = {}
    for d in os.listdir("/proc") if os.path.isdir("/proc") else []:
        if d.isdigit():
            try:
                with open("/proc/%s/stat" % d) as f:
                    starsi[int(d)] = int(f.read().rsplit(")", 1)[1].split()[1])
            except (OSError, ValueError, IndexError):
                continue
    out, rob = [], [pid]
    while rob:
        p = rob.pop()
        otroci = [c for c, s in starsi.items() if s == p and c not in out]
        out += otroci
        rob += otroci
    return out


def pospravi(proc: subprocess.Popen) -> None:
    """Ubije proces, njegovo skupino in vse potomce po PID (najprej TERM, nato KILL)."""
    # Ze pobranega PID ne ubijamo vec posebej: jedro bi ga lahko ze dalo drugemu procesu.
    zrtve = ([proc.pid] if proc.returncode is None else []) + _potomci(proc.pid)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)   # start_new_session: PGID == PID, zajame tudi osirotele potomce
        except (ProcessLookupError, PermissionError):
            pass
        for p in zrtve:
            try:
                os.kill(p, sig)
            except (ProcessLookupError, PermissionError):
                pass
        try:
            proc.wait(timeout=3)
            if sig == signal.SIGTERM and not any(_zivi(p) for p in zrtve):
                break
        except subprocess.TimeoutExpired:
            continue


def _zivi(pid: int) -> bool:
    try:
        with open("/proc/%d/stat" % pid) as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return False


def pospravi_vse() -> None:
    with _ZIVI_KLJUC:
        procesi = list(_ZIVI.values())
    for p in procesi:
        pospravi(p)


class Izid:
    def __init__(self, ukaz, koda, vrstice, cas_potekel, trajanje):
        self.ukaz, self.koda, self.vrstice, self.cas_potekel, self.trajanje = ukaz, koda, vrstice, cas_potekel, trajanje


def pozeni(ukaz: list[str], rok: float, zacasna: str, cwd: str | None = None) -> Izid:
    """Pozene ukaz s casovno mejo; izpis gre v zacasno datoteko (cev bi se pri dolgem izpisu zamasila)."""
    preveri_ukaz(ukaz)
    if _USTAVI.is_set():
        raise RuntimeError("preizkus je prekinjen - ukaz %s ni zagnan" % shlex.join(map(str, ukaz)))
    fd, pot = tempfile.mkstemp(prefix="izpis-", suffix=".txt", dir=zacasna)
    zacetek = time.monotonic()
    with os.fdopen(fd, "w+b") as izpis:
        proc = subprocess.Popen([str(x) for x in ukaz], stdin=subprocess.DEVNULL, stdout=izpis, stderr=subprocess.STDOUT,
                                cwd=cwd, start_new_session=True)
        with _ZIVI_KLJUC:
            _ZIVI[proc.pid] = proc
        cas_potekel = False
        try:
            proc.wait(timeout=max(rok, 0.1))
        except subprocess.TimeoutExpired:
            cas_potekel = True
        finally:
            # Tudi ob uspehu: preizkus lahko pusti spletne procese WebKita ali adb v ozadju.
            pospravi(proc)
            with _ZIVI_KLJUC:
                _ZIVI.pop(proc.pid, None)
        izpis.seek(0)
        vrstice = izpis.read().decode(errors="replace").splitlines()
    os.unlink(pot)
    return Izid(ukaz, None if cas_potekel else proc.returncode, vrstice, cas_potekel, time.monotonic() - zacetek)


def korak(porocilo: Porocilo, ime: str, fn, *a, **k):
    """Vsaka izjema v koraku je NAPAKA tega koraka, ne konec celega preizkusa."""
    try:
        return fn(*a, **k)
    except PrepovedanUkaz as e:
        porocilo.najdba(NAPAKA, ime, str(e))
    except Exception as e:  # noqa: BLE001 - ovoj mora ujeti vse
        porocilo.najdba(NAPAKA, ime, "izjema %s: %s" % (type(e).__name__, e),
                        izpis=traceback.format_exc().splitlines())
    return None


def oceni_izid(porocilo: Porocilo, ime: str, izid: Izid, rok: float, potrdilo: str | None = None) -> bool:
    """Skupna ocena podprocesa: cas, izhodna koda, (neobvezno) obvezna vrstica uspeha; vrstice OPOZORILO so opozorila."""
    if izid.cas_potekel:
        porocilo.najdba(NAPAKA, ime, "casovna meja %.0f s prekoracena (procesi pospravljeni)" % rok,
                        izid.ukaz, None, izid.vrstice)
        return False
    if izid.koda != 0:
        porocilo.najdba(NAPAKA, ime, "izhodna koda %d" % izid.koda, izid.ukaz, izid.koda, izid.vrstice)
        return False
    # Izhod 0 brez vrstice uspeha ali z vrstico FAIL ni dokaz uspeha (npr. skripta se je koncala predcasno).
    if potrdilo and not any(v.startswith(potrdilo) for v in izid.vrstice):
        porocilo.najdba(NAPAKA, ime, "izhod 0, a brez vrstice %r" % potrdilo, izid.ukaz, izid.koda, izid.vrstice)
        return False
    if any(v.startswith("FAIL") for v in izid.vrstice):
        porocilo.najdba(NAPAKA, ime, "izhod 0, a izpis ima FAIL", izid.ukaz, izid.koda, izid.vrstice)
        return False
    opozorila = [v for v in izid.vrstice if "OPOZORILO" in v]
    if opozorila:
        porocilo.najdba(OPOZORILO, ime, "; ".join(o.strip() for o in opozorila)[:300], izid.ukaz, izid.koda, opozorila)
    porocilo.uspeh(ime)
    return True


# ---------------------------------------------------------------------- Linux: utrjenost ELF

def gnu_stack(readelf_l: str) -> str | None:
    """Zastavice GNU_STACK iz »readelf -lW« (npr. »RW «) ali None, ce segmenta ni."""
    m = _GNU_STACK.search(readelf_l)
    return m.group(1) if m else None


def bind_now(readelf_d: str) -> bool | None:
    """True/False iz »readelf -dW«; None, ce ELF nima dinamicnega odseka (staticen program)."""
    if "There is no dynamic section" in readelf_d or "(NEEDED)" not in readelf_d and "Dynamic section" not in readelf_d:
        return None
    for v in readelf_d.splitlines():
        if "(BIND_NOW)" in v:
            return True
        if "(FLAGS)" in v and "BIND_NOW" in v:
            return True
        if "(FLAGS_1)" in v and re.search(r"\bNOW\b", v):
            return True
    return False


def je_elf(pot: str) -> int | None:
    """Tip ELF (2 = program, 3 = deljena/PIE) ali None; objektne datoteke (.o, .ko) niso del pravila."""
    try:
        with open(pot, "rb") as f:
            glava = f.read(18)
    except OSError:
        return None
    if len(glava) < 18 or glava[:4] != b"\x7fELF":
        return None
    tip = int.from_bytes(glava[16:18], "little" if glava[5] == 1 else "big")
    return tip if tip in (2, 3) else None


def elf_datoteke(koren: str) -> list[str]:
    out = []
    for mapa, mape, datoteke in os.walk(koren):
        # Locene simbole za razhroscevanje izpustimo: niso nalozeni ob zagonu.
        mape[:] = [m for m in mape if os.path.join(mapa, m) != os.path.join(koren, "usr", "lib", "debug")]
        for d in datoteke:
            pot = os.path.join(mapa, d)
            if not os.path.islink(pot) and je_elf(pot):
                out.append(pot)
    return sorted(out)


def preveri_utrjenost(porocilo: Porocilo, ime: str, koren: str, zacasna: str, rok: float) -> None:
    konec = time.monotonic() + rok
    tezave: list[str] = []
    opozorila: list[str] = []
    datoteke = elf_datoteke(koren)
    for pot in datoteke:
        rel = "/" + os.path.relpath(pot, koren)
        ostane = konec - time.monotonic()
        if ostane <= 0:
            porocilo.najdba(NAPAKA, ime, "casovna meja %.0f s prekoracena po %d datotekah" % (rok, datoteke.index(pot)),
                            izpis=tezave)
            return
        izidi = []
        for stikalo in ("-lW", "-dW"):
            iz = pozeni(["readelf", stikalo, pot], min(ROK_READELF, ostane), zacasna)
            if iz.cas_potekel or iz.koda != 0:
                porocilo.najdba(NAPAKA, ime, "readelf %s ni uspel za %s" % (stikalo, rel), iz.ukaz, iz.koda, iz.vrstice)
                return
            izidi.append("\n".join(iz.vrstice))
        sklad = gnu_stack(izidi[0])
        if sklad is None:
            tezave.append("%s: PT_GNU_STACK manjka (glibc bi naredil izvrsljiv sklad)" % rel)
        elif "E" in sklad or sklad.replace(" ", "") != "RW":
            tezave.append("%s: GNU_STACK %r, mora biti RW brez E" % (rel, sklad.strip()))
        zdaj = bind_now(izidi[1])
        if zdaj is None:
            # Staticen program nima PLT/GOT za lene vezave - BIND_NOW tam nima pomena, a vodja naj ve zanj.
            opozorila.append("%s: brez dinamicnega odseka (staticen), BIND_NOW ni preverljiv" % rel)
        elif not zdaj:
            tezave.append("%s: brez BIND_NOW (-Wl,-z,now)" % rel)
    if opozorila:
        porocilo.najdba(OPOZORILO, ime, "%d opozoril utrjenosti" % len(opozorila), izpis=opozorila)
    if tezave:
        porocilo.najdba(NAPAKA, ime, "%d od %d ELF krsi pravilo utrjene gradnje" % (len(tezave), len(datoteke)), izpis=tezave)
    else:
        porocilo.uspeh(ime)


# ---------------------------------------------------------------------- Linux: paketi .deb

def polje_deb(deb: str, polje: str, zacasna: str) -> str:
    iz = pozeni(["dpkg-deb", "-f", deb, polje], ROK_ADB, zacasna)
    if iz.cas_potekel or iz.koda != 0:
        raise RuntimeError("dpkg-deb -f %s %s: %s" % (deb, polje, " ".join(iz.vrstice[-3:])))
    return "\n".join(iz.vrstice).strip()


def namescena_razlicica(paket: str, zacasna: str) -> str:
    iz = pozeni(["dpkg-query", "-W", "-f=${Status}|${Version}", paket], ROK_ADB, zacasna)
    stanje, _, razl = "\n".join(iz.vrstice).strip().partition("|")
    return razl if iz.koda == 0 and stanje.endswith(" installed") else ""


def koreni_programov(drevo: str) -> list[str]:
    """Imena programov (usr/lib/<ime>) s core/zasebni_webkit.py - samo te zna preizkusiti smoke_webkit_deb.py."""
    lib = os.path.join(drevo, "usr", "lib")
    if not os.path.isdir(lib):
        return []
    return sorted(d for d in os.listdir(lib) if os.path.isfile(os.path.join(lib, d, "core", "zasebni_webkit.py")))


def preizkus_linux(porocilo: Porocilo, mapa: str, repo: str, zacasna: str, rok: float, razpakirano: bool) -> None:
    debi = sorted(os.path.join(mapa, d) for d in os.listdir(mapa) if d.endswith(".deb")) if os.path.isdir(mapa) else []
    if not debi:
        porocilo.najdba(NAPAKA, "linux", "v %s ni paketov .deb" % mapa)
        return
    drevo = os.path.join(zacasna, "deb")    # vsi paketi v eno drevo: programi in skupni WebKit kot po namestitvi
    paketi: dict[str, tuple[str, str]] = {}  # ime paketa -> (razlicica, deb)
    programi: dict[str, str] = {}            # koren programa -> deb
    for deb in debi:
        ime = "deb " + os.path.basename(deb)
        lastno = os.path.join(zacasna, "en-" + os.path.basename(deb))

        def razpakiraj(deb=deb, ime=ime, lastno=lastno):
            # Skupno drevo potrebuje samo smoke nad razpakiranim; sicer bi velik paket WebKita razpakirali dvakrat.
            for cilj in (lastno, drevo) if razpakirano else (lastno,):
                iz = pozeni(["dpkg-deb", "-x", deb, cilj], rok, zacasna)
                if iz.cas_potekel or iz.koda != 0:
                    porocilo.najdba(NAPAKA, ime, "razpakiranje ni uspelo" + (" (casovna meja)" if iz.cas_potekel else ""),
                                    iz.ukaz, iz.koda, iz.vrstice)
                    return False
            paketi[polje_deb(deb, "Package", zacasna)] = (polje_deb(deb, "Version", zacasna), deb)
            return True
        if not korak(porocilo, ime, razpakiraj):
            continue
        # Utrjenost po paketih (vsak v svoji mapi): napaka pove, kateri .deb je treba popraviti.
        korak(porocilo, "utrjenost " + os.path.basename(deb), preveri_utrjenost, porocilo,
              "utrjenost " + os.path.basename(deb), lastno, zacasna, rok)
        for p in koreni_programov(lastno):
            programi[p] = deb
        shutil.rmtree(lastno, ignore_errors=True)   # ELF so preverjeni, drevo za smoke ostane v [drevo]
    if not programi:
        porocilo.najdba(NAPAKA, "smoke", "noben .deb nima usr/lib/<program>/core/zasebni_webkit.py - smoke ni mogoc")
        return
    if not razpakirano:
        # Namestitev potrebuje koren, ki ga ovoj ne sme imeti: preizkusimo namesceno, a samo ce je ravno ta izdaja.
        def razlicice():
            slabe = []
            for paket, (razl, deb) in sorted(paketi.items()):
                nam = namescena_razlicica(paket, zacasna)
                if nam != razl:
                    slabe.append("%s: namesceno %r, v .deb %r (%s)" % (paket, nam or "ni", razl, os.path.basename(deb)))
            if slabe:
                porocilo.najdba(NAPAKA, "namescene razlicice",
                                "namescen ni paket iz te izdaje - smoke preskocen (namesti sam, ovoj ne uporablja sudo; "
                                "ali pozeni z --razpakirano)", izpis=slabe)
                return False
            porocilo.uspeh("namescene razlicice")
            return True
        if not korak(porocilo, "namescene razlicice", razlicice):
            return
    skripte = [("smoke_webkit_deb", os.path.join(repo, "packaging", "smoke_webkit_deb.py"), None)]
    brskalnik = os.path.join(repo, "packaging", "smoke_brskalnik.py")
    if os.path.isfile(brskalnik):
        skripte.append(("smoke_brskalnik", brskalnik, "safeer-browser"))
    for oznaka, skripta, samo in skripte:
        for program in sorted(programi):
            if samo and program != samo:
                continue
            koren = os.path.join(drevo if razpakirano else "/", "usr", "lib", program)
            ime = "%s %s" % (oznaka, program)

            def smoke(skripta=skripta, koren=koren, ime=ime):
                if not os.path.isfile(skripta):
                    porocilo.najdba(NAPAKA, ime, "ni skripte %s" % skripta)
                    return
                iz = pozeni([sys.executable, skripta, koren], rok, zacasna, cwd=repo)
                oceni_izid(porocilo, ime, iz, rok, potrdilo="PASS")
            korak(porocilo, ime, smoke)


# ---------------------------------------------------------------------- Android

def razcleni_android(arg: str) -> tuple[str, str, str]:
    """»naprava=paket:apk« -> (naprava, paket, apk); naprava sme imeti vrata (192.168.1.5:5555), paket nima dvopicja."""
    naprava, enako, ostalo = arg.partition("=")
    paket, dvopicje, apk = ostalo.partition(":")
    if not enako or not dvopicje or not naprava.strip() or not paket.strip() or not apk.strip():
        raise argparse.ArgumentTypeError("--android mora biti NAPRAVA=PAKET:APK, dobil %r" % arg)
    return naprava.strip(), paket.strip(), apk.strip()


def ime_zaklepa(naprava: str) -> str:
    """IP brez vrat (ali serijska stevilka); druge znake zamenjamo, da ime ne more pobegniti iz /tmp."""
    gostitelj = naprava.rsplit(":", 1)[0] if re.fullmatch(r"[^:]+:\d+", naprava) else naprava
    return ZAKLEP.format(re.sub(r"[^A-Za-z0-9._-]", "_", gostitelj))


def ospredje(dumpsys: str) -> str:
    for vzorec in _OSPREDJE:
        m = vzorec.search(dumpsys)
        if m:
            return m.group(1)
    return ""


class Zaklep:
    """flock na /tmp/safeer-naprava-<ip>.lock s casovno mejo; drug preizkus iste naprave caka ali dobi napako."""

    def __init__(self, pot: str, rok: float) -> None:
        self.pot, self.rok, self.f = pot, rok, None

    def __enter__(self) -> bool:
        self.f = open(self.pot, "a")
        konec = time.monotonic() + self.rok
        while True:
            try:
                fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except BlockingIOError:
                if time.monotonic() >= konec:
                    return False
                time.sleep(0.2)

    def __exit__(self, *_a) -> None:
        if self.f:
            self.f.close()   # zapiranje sprosti flock


def preizkus_android(porocilo: Porocilo, naprava: str, paket: str, apk: str, repo: str, zacasna: str, rok: float) -> None:
    ime = "android %s=%s" % (naprava, paket)
    if not paket.startswith(PREDPONA_PAKETA):
        # Ovoj preizkusa samo nase aplikacije; tujih paketov na napravi ne namescamo in ne zaganjamo.
        porocilo.najdba(NAPAKA, ime, "paket %s ni %s* - naprave se ne dotaknem" % (paket, PREDPONA_PAKETA))
        return
    if not os.path.isfile(apk):
        porocilo.najdba(NAPAKA, ime, "APK %s ne obstaja - naprave se ne dotaknem" % apk)
        return
    skripta = os.path.join(repo, "tests", "preizkus_po_gradnji.py")
    if not os.path.isfile(skripta):
        porocilo.najdba(NAPAKA, ime, "ni skripte %s" % skripta)
        return
    zaklep = ime_zaklepa(naprava)
    konec = time.monotonic() + rok
    with Zaklep(zaklep, rok) as dobljen:
        if not dobljen:
            porocilo.najdba(NAPAKA, ime, "naprava zasedena: %s ni prost v %.0f s" % (zaklep, rok))
            return
        if ":" in naprava:   # omrezna naprava: brez povezave ne moremo prebrati ospredja
            pozeni(["adb", "connect", naprava], ROK_ADB, zacasna)
        iz = pozeni(["adb", "-s", naprava, "get-state"], ROK_ADB, zacasna)
        if iz.cas_potekel or iz.koda != 0 or "device" not in iz.vrstice[-1:]:
            porocilo.najdba(NAPAKA, ime, "naprava ni povezana", iz.ukaz, iz.koda, iz.vrstice)
            return
        # Samo branje: ce lastnik ravno uporablja drugo (zasebno) aplikacijo, je ne prekinemo in je ne snemamo.
        iz = pozeni(["adb", "-s", naprava, "shell", "dumpsys", "activity", "activities"], ROK_ADB, zacasna)
        spredaj = ospredje("\n".join(iz.vrstice)) if iz.koda == 0 else ""
        if not spredaj:
            iz2 = pozeni(["adb", "-s", naprava, "shell", "dumpsys", "window"], ROK_ADB, zacasna)
            spredaj = ospredje("\n".join(iz2.vrstice)) if iz2.koda == 0 else ""
        if not spredaj.startswith(PREDPONA_PAKETA):
            porocilo.najdba(NAPAKA, ime, "v ospredju je %s, ne %s* - preizkus preskocen, naprave se ne dotaknem"
                            % (spredaj or "neznano", PREDPONA_PAKETA), iz.ukaz, iz.koda)
            return
        ostane = max(konec - time.monotonic(), 1.0)
        iz = pozeni([sys.executable, skripta, "%s=%s" % (naprava, paket), "--apk", apk], ostane, zacasna, cwd=repo)
        oceni_izid(porocilo, ime, iz, ostane, potrdilo="PREIZKUS PO GRADNJI: OK")


# ---------------------------------------------------------------------- glavni

def argumenti(argv: list[str]) -> argparse.Namespace:
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--linux-deb", metavar="MAPA", help="mapa s paketi .deb te izdaje")
    a.add_argument("--android", metavar="NAPRAVA=PAKET:APK", action="append", default=[], type=razcleni_android,
                   help="naprava (naslov[:vrata] ali serijska), paket si.safeer.* in APK; ponovljivo")
    a.add_argument("--izhod", default="porocilo.json", help="porocilo JSON (privzeto porocilo.json)")
    a.add_argument("--rok", type=float, default=PRIVZET_ROK, help="casovna meja na korak v sekundah (privzeto 900)")
    a.add_argument("--razpakirano", action="store_true",
                   help="smoke nad razpakiranim .deb namesto nad namescenim paketom (npr. v vsebniku brez namestitve)")
    a.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   help="koren repozitorija s packaging/ in tests/ (privzeto nad tools/)")
    p = a.parse_args(argv)
    if not p.linux_deb and not p.android:
        a.error("podaj vsaj --linux-deb ali --android")
    if p.rok <= 0:
        a.error("--rok mora biti > 0")
    # Podprocesi tecejo s cwd=repo: relativne poti iz ukazne vrstice bi tam kazale drugam.
    p.repo = os.path.abspath(p.repo)
    p.android = [(n, pk, os.path.abspath(apk)) for n, pk, apk in p.android]
    return p


def zapisi_json(pot: str, vsebina: dict) -> None:
    # Najprej zacasna datoteka, nato preimenovanje: prekinjen zapis ne pusti pol porocila.
    mapa = os.path.dirname(os.path.abspath(pot))
    os.makedirs(mapa, exist_ok=True)
    fd, zac = tempfile.mkstemp(prefix=".porocilo-", dir=mapa)
    with os.fdopen(fd, "w") as f:
        json.dump(vsebina, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(zac, pot)


def main(argv: list[str]) -> int:
    try:
        p = argumenti(argv)
    except SystemExit as e:
        return int(e.code or 0)
    zacetek = time.time()
    _USTAVI.clear()
    porocilo = Porocilo()
    koda_prekinitve = None

    def ob_signalu(stevilka, _okvir):
        raise KeyboardInterrupt("signal %d" % stevilka)
    stari = signal.signal(signal.SIGTERM, ob_signalu) if threading.current_thread() is threading.main_thread() else None
    try:
        with tempfile.TemporaryDirectory(prefix="preizkus-izdaje-") as zacasna:
            try:
                if p.linux_deb:
                    korak(porocilo, "linux", preizkus_linux, porocilo, os.path.abspath(p.linux_deb), p.repo, zacasna,
                          p.rok, p.razpakirano)
                if p.android:
                    # Razlicne naprave vzporedno; isto napravo zaporedno uredi zaklep.
                    bazen = concurrent.futures.ThreadPoolExecutor(max_workers=len(p.android))
                    posli: list[concurrent.futures.Future] = []
                    try:
                        posli = [bazen.submit(korak, porocilo, "android %s=%s" % (n, pk), preizkus_android, porocilo,
                                              n, pk, apk, p.repo, zacasna, p.rok) for n, pk, apk in p.android]
                        for f in posli:
                            f.result()
                    finally:
                        # Ob prekinitvi najprej pospravimo procese, sicer bi shutdown cakal na niti do konca roka.
                        if any(not f.done() for f in posli):
                            _USTAVI.set()
                            pospravi_vse()
                        bazen.shutdown(wait=True, cancel_futures=True)
            except KeyboardInterrupt as e:
                _USTAVI.set()
                pospravi_vse()
                porocilo.najdba(NAPAKA, "ovoj", "prekinjeno (%s) - procesi pospravljeni" % (e or "Ctrl+C"))
                koda_prekinitve = 130
            finally:
                pospravi_vse()
    finally:
        if stari is not None:
            signal.signal(signal.SIGTERM, stari)
    try:
        zapisi_json(p.izhod, porocilo.json(zacetek, argv))
    except OSError as e:
        porocilo.najdba(NAPAKA, "porocilo", "JSON %s ni zapisan: %s" % (p.izhod, e))
    porocilo.izpisi()
    if koda_prekinitve:
        return koda_prekinitve
    return 1 if porocilo.napake() else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
