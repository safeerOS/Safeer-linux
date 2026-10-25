"""Varovalo signalov: preizkus sme signal poslati samo procesom, ki so potomci procesa preizkusov.

Zakaj (22. 10. 2026): tek celotnega nabora na lastnikovem racunalniku je dvakrat ustavil njegov dock Plank in v pravi
dnevnik zapisal ~60 laznih sesutij (koda 137). Kodi, ki jo preizkus preizkusa (core/os_dock.osvezi: os.kill(pid, SIGTERM)),
je vseeno, cigav je proces. Varovalo ovije os.kill, os.killpg, os.system in podprocese (subprocess.Popen, tudi
asyncio in os.popen, ki gresta skozenj); cilj, ki ni potomec (veriga PPid v /proc), dobi izjemo, signal pa NE odide.
Signal 0 (preverba obstoja) je vedno dovoljen. Krsitev se zapise v tests/_krsitve_signalov.log (preizkus + cilj),
preizkus pa pade tudi, ce ga je izjema v preizkusani kodi pogoltnila (conftest.py preveri seznam krsitev po vsakem
preizkusu).

Ukazi (naloga 48): niz za lupino (shell=True, os.system, ["sh"|"bash"|"dash", "-c", niz]) se razcleni kot lupinski
ukaz; kill/pkill/killall se isce v vsakem delu (; && || | & ( ) `...` $(...), nove vrstice, if/then/do ...) in tudi za
ovoji env, xargs, setsid, nohup, timeout, nice, ionice, stdbuf, command, exec, time. `xargs kill` je krsitev (cilji
pridejo s standardnega vhoda, vnaprej jih ne poznamo). pkill/killall isce cilje samo med potomci: istoimenski tuj
proces (npr. lastnikov `sleep`) zakonitega preizkusa ne zavrne - ukaz v obliki seznama se zamenja s `kill -s SIG <PID
potomcev>` (ali `false`, kot pkill brez zadetka), da pravi pkill tujca ne zadene. Niz za lupino s takim tujcem je
krsitev (prepisa niza ne delamo); prav tako pkill z izbirami, ki jih ne znamo posnemati (-P, -u, -g ...).

Omejitve (ni prestrezeno; zanesljivo bi bilo samo s seccomp/ptrace ali locenim imenskim prostorom PID):
- nizkonivojski klici mimo os.kill: ctypes (libc.kill, syscall), psutil.Process.send_signal/terminate/kill
  (psutil klice svoj C modul), signal.pidfd_send_signal, os.posix_spawn/os.exec*/os.spawn*/pty.spawn;
- skripte: `python -c "os.kill(...)"`, `sh skripta.sh`, `echo kill 5 | sh`, eval, ukaz iz spremenljivke ($UKAZ);
- tekma: pkill v nizu za lupino preverimo ob zagonu - tuj istoimenski proces, ki se zazene vmes, bi zadel;
- ponovna uporaba PID med hojo po verigi PPid in demoni z dvojnim fork() (niso vec potomci - signal zavrnjen).
"""
import os
import re
import shlex
import signal
import subprocess
import time

_ORODJA = ("kill", "pkill", "killall")
_LUPINE = ("sh", "bash", "dash", "zsh", "ksh", "mksh", "ash")
# Ovoji pred pravim ukazom: (izbire z argumentom, stevilo pozicijskih argumentov pred ukazom)
_OVOJI = {
    "env": ({"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}, 0),
    "xargs": ({"-a", "--arg-file", "-d", "--delimiter", "-E", "-I", "-L", "-n", "--max-args", "-P", "--max-procs",
               "-s", "--max-chars", "--process-slot-var"}, 0),
    "setsid": (set(), 0), "nohup": (set(), 0), "command": (set(), 0), "builtin": (set(), 0),
    "timeout": ({"-s", "--signal", "-k", "--kill-after"}, 1),
    "nice": ({"-n", "--adjustment"}, 0),
    "ionice": ({"-c", "--class", "-n", "--classdata"}, 0),
    "stdbuf": ({"-i", "-o", "-e", "--input", "--output", "--error"}, 0),
    "exec": ({"-a"}, 0), "time": ({"-f", "--format", "-o", "--output"}, 0),
}
_KLJUCNE = ("if", "then", "else", "elif", "do", "while", "until", "!", "{", "}", "fi", "done")
# Izbire pkill/killall z argumentom, ki jih prepis v kill ne posnema (filtri po starsu, uporabniku, skupini ...)
_Z_ARGUMENTOM = {
    "pkill": {"-s", "--session", "-g", "--pgroup", "-G", "--group", "-P", "--parent", "-u", "--euid", "-U", "--uid",
              "-t", "--terminal", "-F", "--pidfile", "--ns", "--nslist", "--cgroup", "-d", "--delimiter"},
    "killall": {"-u", "--user", "-o", "--older-than", "-y", "--younger-than", "-n", "--ns", "-Z", "--context"},
}
_PRIREDITEV = re.compile(r"^[A-Za-z_]\w*=")
# Preusmeritve (2>/dev/null, >&2, <<< 5, &>x): stevilka pred > ni cilj kill
_PREUSMERITEV = re.compile(r"\d*(?:&>>?|>>?|<<<|<<-?|<>|<|>\|)&?\s*(?:\d+-?|[^\s;&|()<>]+)?")
_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_krsitve_signalov.log")


# Pravi os.kill, shranjen ob uvozu (conftest uvozi modul pred namestitvijo): pospravljanje preizkusov varovala, ki
# mora res ubiti tujca, ki ga je preizkus sam zagnal.
PRAVI_KILL = os.kill


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


def _je_signal(ime):
    if re.match(r"^\d+$", ime):
        return True
    ime = ime[3:] if ime.startswith("SIG") else ime
    return ime.isupper() and (ime in signal.Signals.__members__ or "SIG" + ime in signal.Signals.__members__
                              or re.match(r"^RTM(IN|AX)([+-]\d+)?$", ime) is not None)


def _niz_za_c(args):
    """Niz za `sh -c` (tudi -ec, -lc, --norc -c); None, ce lupina bere skripto ali standardni vhod."""
    c, i = False, 0
    while i < len(args):
        a = args[i]
        i += 1
        if a in ("-o", "+o", "-O", "+O"):
            i += 1
        elif a == "--":
            break
        elif a.startswith("-") and not a.startswith("--") and "c" in a[1:]:
            c = True
        elif not a.startswith(("-", "+")):
            return a if c else None
    return args[i] if c and i < len(args) else None


def _ujema(orodje, vzorec, re_vz, pid, polno, tocno):
    if orodje == "pkill" and polno:
        try:
            with open("/proc/%d/cmdline" % pid, "rb") as f:
                besedilo = f.read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        except OSError:
            return False
    else:
        besedilo = _comm(pid)
    if orodje == "killall":       # comm je skrajsan na 15 znakov
        return besedilo == vzorec or (len(vzorec) > 15 and besedilo == vzorec[:15])
    return bool(re_vz.fullmatch(besedilo) if tocno else re_vz.search(besedilo))


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
        """Podproces: vrne ukaz za zagon (enak ali prepisan pkill/killall); krsitev, ce bi signal zadel tujca."""
        if isinstance(ukaz, (bytes, str, os.PathLike)):
            self._preveri_lupino(os.fsdecode(ukaz))
            return ukaz
        zeton = [os.fsdecode(x) for x in ukaz]
        if shell:
            if zeton:                  # ostali elementi so $0, $1 ... lupine, ne ukazi
                self._preveri_lupino(zeton[0])
            return ukaz
        prepisan = self._preveri_argv(zeton, prepis=True)
        return ukaz if prepisan is None else prepisan

    def _preveri_lupino(self, niz):
        """Niz kot lupinski ukaz: preusmeritve ven, nove vrstice in `...` kot locila, vsak del posebej."""
        niz = _PREUSMERITEV.sub(" ", niz.replace("\n", ";").replace("`", ";"))
        try:
            lex = shlex.shlex(niz, posix=True, punctuation_chars=True)
            lex.whitespace_split = True
            zeton = list(lex)
        except ValueError:            # nezaprt narekovaj: lupina bi ukaz zavrnila
            return
        odseki, tekoci = [], []
        for z in zeton:
            if z and set(z) <= set("();<>|&"):
                odseki.append(tekoci)
                tekoci = []
            else:
                tekoci.append(z)
        odseki.append(tekoci)
        for odsek in odseki:
            self._preveri_argv(odsek, prepis=False)

    def _odvij(self, z):
        """Preskoci VAR=, kljucne besede lupine in ovoje (env, xargs, timeout ...). Vrne (indeks programa, xargs)."""
        i, xargs = 0, False
        while i < len(z):
            ime = os.path.basename(z[i])
            if _PRIREDITEV.match(z[i]) or ime in _KLJUCNE:
                i += 1
                continue
            if ime not in _OVOJI:
                break
            z_argumentom, pozicijskih = _OVOJI[ime]
            xargs = xargs or ime == "xargs"
            i += 1
            while i < len(z) and z[i].startswith("-"):
                izbira = z[i]
                i += 1
                if izbira == "--":
                    break
                if ime == "env" and izbira in ("-S", "--split-string") and i < len(z):
                    self._preveri_lupino(z[i])
                elif ime == "env" and izbira.startswith(("--split-string=", "-S")) and len(izbira) > 2:
                    self._preveri_lupino(izbira.split("=", 1)[1] if "=" in izbira else izbira[2:])
                if izbira in z_argumentom:
                    i += 1
            i += pozicijskih
        return i, xargs

    def _preveri_argv(self, z, prepis):
        """En ukaz (argv). Vrne prepisan argv (samo za pkill/killall s tujim istoimenskim procesom) ali None."""
        i, xargs = self._odvij(z)
        if i >= len(z):
            return None
        ime = os.path.basename(z[i])
        if ime in _LUPINE:
            niz = _niz_za_c(z[i + 1:])
            if niz is not None:
                self._preveri_lupino(niz)
            return None
        if ime not in _ORODJA:
            return None
        rep = self._preveri_odsek(ime, z[i + 1:], xargs=xargs, prepis=prepis)
        return None if rep is None else z[:i] + rep

    def _preveri_odsek(self, orodje, args, xargs=False, prepis=False):
        signal0 = any(a in ("-0", "-s0", "--signal=0") or a == "0" and i and args[i - 1] in ("-s", "--signal")
                      for i, a in enumerate(args))
        if signal0:
            return None
        if xargs:
            self._krsitev("%s prek xargs (cilji pridejo s standardnega vhoda)" % orodje, [])
        if orodje == "kill":
            self._preveri_kill(args)
            return None
        return self._preveri_pkill(orodje, args, prepis)

    def _preveri_kill(self, args):
        """kill: prvi -SIG ali -s/-n SIG je signal, nadaljnji -N je skupina procesov (kot procps kill)."""
        pozicijski = []
        i, za_dvema, signal_dan = 0, False, False
        while i < len(args):
            a = args[i]
            i += 1
            if za_dvema or not a.startswith("-") or (signal_dan and re.match(r"^-\d+$", a)):
                pozicijski.append(a)
            elif a == "--":
                za_dvema = True
            elif a in ("-s", "-n", "--signal"):
                i += 1
                signal_dan = True
            elif a in ("-l", "-L", "--list", "--table"):
                return                  # samo izpis imen signalov
            else:
                signal_dan = signal_dan or _je_signal(a[1:]) or a.startswith("-s")
        for a in pozicijski:
            if not re.match(r"^-?\d+$", a):
                self._krsitev("kill z neznanim ciljem %r" % a, [])
        for a in pozicijski:
            self.preveri_pid(int(a), signal.SIGTERM)

    def _preveri_pkill(self, orodje, args, prepis):
        """pkill/killall: cilji samo med potomci; tuj istoimenski proces -> prepis v kill potomcev ali krsitev."""
        polno = tocno = False
        sig = "TERM"
        znane = True                    # samo izbire, ki jih prepis v kill natancno posnema
        pozicijski = []
        i, za_dvema = 0, False
        while i < len(args):
            a = args[i]
            i += 1
            if za_dvema or not a.startswith("-") or a == "-":
                pozicijski.append(a)
            elif a == "--":
                za_dvema = True
            elif a == "--signal" or (orodje == "killall" and a == "-s"):
                if i < len(args):
                    sig = args[i]
                    i += 1
            elif a.startswith("--signal="):
                sig = a.split("=", 1)[1]
            elif _je_signal(a[1:]):
                sig = a[1:]
            elif a in ("--full", "--exact") or (orodje == "killall" and a in ("--quiet",)):
                polno = polno or a == "--full"
                tocno = tocno or a == "--exact"
            elif not a.startswith("--") and set(a[1:]) <= set("xf" if orodje == "pkill" else "eq"):
                polno = polno or (orodje == "pkill" and "f" in a)
                tocno = tocno or "x" in a or "e" in a
            else:
                znane = False
                if a in _Z_ARGUMENTOM[orodje]:
                    i += 1
        if not pozicijski:
            self._krsitev("%s brez cilja" % orodje, [])
        vzorci = []
        for vzorec in pozicijski:
            try:
                vzorci.append(re.compile(vzorec) if orodje == "pkill" else None)
            except re.error:
                self._krsitev("%s z neveljavnim vzorcem %r" % (orodje, vzorec), [])
        nasi, tuji = [], []
        for p in _vsi_procesi():
            if p in (os.getpid(), self.koren):      # pkill ne zadene sebe; procesa preizkusov ne ubijamo
                continue
            if any(_ujema(orodje, vz, re_vz, p, polno, tocno) for vz, re_vz in zip(pozicijski, vzorci)):
                (nasi if self.potomec(p) else tuji).append(p)
        if not tuji:
            return None
        if prepis and znane:
            sig = sig[3:] if sig.upper().startswith("SIG") else sig
            return ["kill", "-s", sig] + [str(p) for p in nasi] if nasi else ["false"]
        self._krsitev("%s %s bi zadel tudi tuje istoimenske procese (v preizkusu uporabi PID ali seznam argumentov)"
                      % (orodje, " ".join(pozicijski)), tuji)
        return None

    # --- namestitev ---
    def namesti(self):
        if self._orig:
            return
        varovalo = self
        self._orig = {"kill": os.kill, "killpg": os.killpg, "system": os.system, "popen": subprocess.Popen.__init__}

        def kill(pid, sig):
            varovalo.preveri_pid(pid, sig)
            return varovalo._orig["kill"](pid, sig)

        def killpg(pgid, sig):
            varovalo.preveri_skupino(pgid, sig)
            return varovalo._orig["killpg"](pgid, sig)

        def system(ukaz):
            varovalo.preveri_ukaz(ukaz, shell=True)
            return varovalo._orig["system"](ukaz)

        orig_init = self._orig["popen"]

        def popen_init(self_, args, *a, **kw):
            args = varovalo.preveri_ukaz(args, kw.get("shell", False))
            return orig_init(self_, args, *a, **kw)

        os.kill, os.killpg, os.system, subprocess.Popen.__init__ = kill, killpg, system, popen_init

    def odstrani(self):
        if not self._orig:
            return
        os.kill, os.killpg, os.system = self._orig["kill"], self._orig["killpg"], self._orig["system"]
        subprocess.Popen.__init__ = self._orig["popen"]
        self._orig = {}

    def od(self, zacetek):
        return self.krsitve[zacetek:]
