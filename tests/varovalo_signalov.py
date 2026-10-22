"""Varovalo signalov: preizkus sme signal poslati samo procesom, ki so potomci procesa preizkusov.

Zakaj (22. 10. 2026): tek celotnega nabora na lastnikovem racunalniku je dvakrat ustavil njegov dock Plank in v pravi
dnevnik zapisal ~60 laznih sesutij (koda 137). Kodi, ki jo preizkus preizkusa (core/os_dock.osvezi: os.kill(pid, SIGTERM)),
je vseeno, cigav je proces. Varovalo ovije os.kill, os.killpg in podprocese `kill`/`pkill`/`killall`; cilj, ki ni
potomec (veriga PPid v /proc), dobi izjemo, signal pa NE odide. Signal 0 (preverba obstoja) je vedno dovoljen.
Krsitev se zapise v tests/_krsitve_signalov.log (preizkus + cilj), preizkus pa pade tudi, ce ga je izjema
v preizkusani kodi pogoltnila (conftest.py preveri seznam krsitev po vsakem preizkusu).
"""
import os
import re
import shlex
import signal
import subprocess
import time

_ORODJA = ("kill", "pkill", "killall")
_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_krsitve_signalov.log")


class KrsitevSignala(PermissionError):
    pass


def _ppid(pid):
    """PPid procesa iz /proc/<pid>/stat (ime procesa je v oklepaju in lahko vsebuje presledke); None, ce ne obstaja."""
    try:
        with open("/proc/%d/stat" % pid, "rb") as f:
            podatki = f.read().decode("utf-8", "replace")
        return int(podatki.rsplit(")", 1)[1].split()[1])
    except (OSError, ValueError, IndexError):
        return None


def _pgrp(pid):
    try:
        with open("/proc/%d/stat" % pid, "rb") as f:
            return int(f.read().decode("utf-8", "replace").rsplit(")", 1)[1].split()[2])
    except (OSError, ValueError, IndexError):
        return None


def _comm(pid):
    try:
        with open("/proc/%d/comm" % pid, encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return "?"


def _vsi_procesi():
    try:
        return [int(i) for i in os.listdir("/proc") if i.isdigit()]
    except OSError:
        return []


class Varovalo:
    def __init__(self, koren=None, dnevnik=_LOG):
        self.koren = koren or os.getpid()
        self.dnevnik = dnevnik
        self.krsitve = []
        self._orig = {}

    # --- odlocanje ---
    def potomec(self, pid):
        """Je proces koren sam ali njegov potomec? Proces, ki ga ni vec, je »ne potomec« (signal bi zadel tujo ponovno uporabo PID)."""
        for _ in range(64):
            if pid == self.koren:
                return True
            if pid <= 1:
                return False
            pid = _ppid(pid)
            if pid is None:
                return False
        return False

    def _skupina_dovoljena(self, pgid):
        clani = [p for p in _vsi_procesi() if _pgrp(p) == pgid]
        return all(self.potomec(p) for p in clani)

    def _krsitev(self, kaj, cilji):
        ime = os.environ.get("PYTEST_CURRENT_TEST", "?")
        opis = ", ".join("%d(%s)" % (p, _comm(p)) for p in cilji) or "?"
        vrstica = "%s | %s | %s | %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), ime, kaj, opis)
        self.krsitve.append(vrstica.strip())
        try:
            with open(self.dnevnik, "a", encoding="utf-8") as f:
                f.write(vrstica)
        except OSError:
            pass
        raise KrsitevSignala("Varovalo signalov: %s bi zadel proces, ki ni potomec preizkusov: %s (preizkus %s)"
                             % (kaj, opis, ime))

    def preveri_pid(self, pid, sig):
        if sig == 0:
            return
        if pid > 0:
            if not self.potomec(pid):
                self._krsitev("kill(%d)" % sig, [pid])
        else:
            skupina = os.getpgrp() if pid == 0 else -pid
            self.preveri_skupino(skupina, sig)

    def preveri_skupino(self, pgid, sig):
        if sig == 0:
            return
        if pgid <= 1 or not self._skupina_dovoljena(pgid):
            clani = [p for p in _vsi_procesi() if _pgrp(p) == pgid and not self.potomec(p)] or [pgid]
            self._krsitev("killpg(%d)" % sig, clani)

    def preveri_ukaz(self, ukaz, shell=False):
        """Podproces kill/pkill/killall: cilji iz ukazne vrstice (stevilke ali imena/vzorci), vsi morajo biti potomci."""
        if isinstance(ukaz, (bytes, str, os.PathLike)):
            try:
                lex = shlex.shlex(os.fsdecode(ukaz), posix=True, punctuation_chars=";&|")
                lex.whitespace_split = False
                zeton = list(lex)
            except ValueError:
                return
        else:
            zeton = [os.fsdecode(x) for x in ukaz]
        odseki, tekoci = [], []
        for z in zeton:
            if z in (";", "&&", "||", "|", "&"):
                odseki.append(tekoci)
                tekoci = []
            else:
                tekoci.append(z)
        odseki.append(tekoci)
        for odsek in odseki:
            while odsek and re.match(r"^\w+=", odsek[0]):
                odsek = odsek[1:]
            if not odsek or os.path.basename(odsek[0]) not in _ORODJA:
                continue
            self._preveri_odsek(os.path.basename(odsek[0]), odsek[1:])

    def _preveri_odsek(self, orodje, args):
        signal0 = any(a in ("-0", "-s0", "--signal=0") or a == "0" and i and args[i - 1] in ("-s", "--signal")
                      for i, a in enumerate(args))
        if signal0:
            return
        polno = any(a.startswith("-") and not a.startswith("--") and "f" in a[1:] and a[1:].isalpha() for a in args)
        pozicijski = []
        preskoci = False
        za_dvema = False
        for a in args:
            if preskoci:
                preskoci = False
                continue
            if a in ("-s", "-n", "-u", "-U", "-g", "-G", "-P", "-t", "-c"):
                preskoci = True
                continue
            if a == "--" and not za_dvema:
                za_dvema = True
                continue
            if a.startswith("-") and not za_dvema:
                continue
            pozicijski.append(a)
        cilji = []
        if orodje == "kill":
            for a in pozicijski:
                if re.match(r"^-?\d+$", a):
                    cilji.append(int(a))
                else:
                    self._krsitev("kill z neznanim ciljem %r" % a, [])
            for p in cilji:
                self.preveri_pid(p, signal.SIGTERM)
            return
        pids = []
        for vzorec in pozicijski:
            try:
                re_vz = re.compile(vzorec if orodje == "pkill" else "^%s$" % re.escape(vzorec))
            except re.error:
                self._krsitev("%s z neveljavnim vzorcem" % orodje, [])
            for p in _vsi_procesi():
                if p == os.getpid():
                    continue
                if polno and orodje == "pkill":
                    try:
                        with open("/proc/%d/cmdline" % p, "rb") as f:
                            besedilo = f.read().replace(b"\0", b" ").decode("utf-8", "replace")
                    except OSError:
                        continue
                else:
                    besedilo = _comm(p)
                if re_vz.search(besedilo):
                    pids.append(p)
        if not pozicijski:
            self._krsitev("%s brez cilja" % orodje, [])
        tuji = [p for p in pids if not self.potomec(p)]
        if tuji:
            self._krsitev("%s %s" % (orodje, " ".join(pozicijski)), tuji)

    # --- namestitev ---
    def namesti(self):
        if self._orig:
            return
        varovalo = self
        self._orig = {"kill": os.kill, "killpg": os.killpg, "popen": subprocess.Popen.__init__}

        def kill(pid, sig):
            varovalo.preveri_pid(pid, sig)
            return varovalo._orig["kill"](pid, sig)

        def killpg(pgid, sig):
            varovalo.preveri_skupino(pgid, sig)
            return varovalo._orig["killpg"](pgid, sig)

        orig_init = self._orig["popen"]

        def popen_init(self_, args, *a, **kw):
            varovalo.preveri_ukaz(args, kw.get("shell", False))
            return orig_init(self_, args, *a, **kw)

        os.kill, os.killpg, subprocess.Popen.__init__ = kill, killpg, popen_init

    def odstrani(self):
        if not self._orig:
            return
        os.kill, os.killpg, subprocess.Popen.__init__ = self._orig["kill"], self._orig["killpg"], self._orig["popen"]
        self._orig = {}

    def od(self, zacetek):
        return self.krsitve[zacetek:]
