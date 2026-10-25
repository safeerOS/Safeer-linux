"""Varovalo programov: preizkus ne sme zagnati pravega programa za skrbniske pravice (pkexec, sudo, su, doas, run0) ne
namescenega Safeerja (/usr/bin/safeer*, /usr/lib/safeer*, Flatpak io.github.memelandfaner.*). Izjema so samo pomozni
procesi nasega spletnega motorja (WebKit*Process v SPLETNI_MOTOR_MAPE), s katerim tecejo vsi zivi preizkusi.

Zakaj (25. 10. 2026 14:25): tests/test_sistemski_programi.py::OvojiFlatpak je na lastnikovem prenosniku prek ovoja
Flatpak (packaging/flatpak_host_wrappers.sh) zagnal pravi /usr/bin/safeer-cinnamon --od-vklopa -> pkexec: dvakrat okno
»Zahtevana je overitev« (skrbnisko geslo) na zaslonu, procesa sta po izteku casa ostala sirota.

Dve plasti:
1. Python: subprocess.Popen (tudi run/call/check_output, asyncio, os.popen, ki gredo skozenj), os.system,
   os.posix_spawn(p). Ukaz, ki bi zagnal prepovedan program (sam, kot program lupine -c ali kot skripta tolmaca),
   dobi izjemo KrsitevPrograma - program se NE zazene.
2. Potomci (Linux): nit vsakih PREGLED_S pregleda potomce procesa preizkusov (/proc/<pid>/task/*/children). Potomca, ki
   je prepovedan program (exe, ali skripta, ki jo tolmac izvaja), takoj ubije (SIGKILL) in zapise krsitev. To ujame tudi
   program, ki ga zazene skripta (sh -> exec /usr/bin/...), GLib.spawn ali Gio.Subprocess - mimo Pythona.
Lazni programi v zacasni mapi teka (tempfile.gettempdir(), ki jo nastavi korenski conftest.py) so dovoljeni - tako
preizkusi podtikajo programe (z absolutno potjo ali na zacetku PATH). Krsitev se zapise v tests/_krsitve_programov.log,
preizkus pa GLASNO pade (conftest.py), tudi ce je izjemo pogoltnila preizkusana koda.

Omejitve: nit potomcev ujame program sele ob naslednjem pregledu (do PREGLED_S po zagonu) - zato Python plast ustavi,
kar gre skozi Python, ze pred zagonom. Dvojni fork() (demon, ki ni vec potomec) in os.exec* procesa preizkusov nista
prestrezena.
"""
import os
import re
import shlex
import shutil
import signal
import subprocess
import tempfile
import threading
import time

#: Programi, ki dajo skrbniske pravice (in vprasajo za geslo): pravih se v preizkusu nikoli ne zazene.
IMENA = frozenset(("pkexec", "sudo", "su", "doas", "run0"))
#: Namesceni Safeer (paket .deb, rocna namestitev, Flatpak): preizkus dela s kodo repozitorija, ne z namescenim.
PREDPONE = ("/usr/bin/safeer", "/usr/sbin/safeer", "/usr/local/bin/safeer", "/usr/local/sbin/safeer", "/usr/lib/safeer",
            "/usr/libexec/safeer", "/usr/local/lib/safeer", "/usr/share/safeer", "/opt/safeer")
FLATPAK_ID = "io.github.memelandfaner."
#: Izjema: pomozni procesi NASEGA spletnega motorja. Preizkusi tecejo samo z nasim WebKitom (AGENTS.md, lastnik 21. 10.
#: 2026; tools/nas_webkit.sh -> /usr/lib/safeer-webkit), WebKitGTK pa za vsako stran zazene WebKitWebProcess in
#: WebKitNetworkProcess iz libexec. Skrbniskih pravic in stanja namescenega Safeerja nimajo. 25. 10. 2026 15:12 jih je
#: varovalo ubijalo: vsak zivi preizkus z WebKitom je padel (»Connection: failed to receive credentials«, SIGTRAP).
#: Dovoljeni so samo ti programi v teh mapah (realpath); jsc in vse drugo pod PREDPONE ostane prepovedano.
SPLETNI_MOTOR_MAPE = ("/usr/lib/safeer-webkit/libexec/webkitgtk-6.0",
                      "/usr/lib/safeer-browser/webkit-vgrajen/libexec/webkitgtk-6.0",
                      "/usr/lib/safeer-os/webkit-vgrajen/libexec/webkitgtk-6.0")
SPLETNI_MOTOR_PROGRAMI = frozenset(("WebKitWebProcess", "WebKitNetworkProcess", "WebKitGPUProcess"))
_LUPINE = ("sh", "bash", "dash", "zsh", "ksh", "mksh", "ash")
_TOLMACI = re.compile(r"^(python[0-9.]*|perl|ruby|node|lua[0-9.]*)$")
_OVOJI = {
    "env": {"-u", "--unset", "-C", "--chdir"}, "xargs": {"-a", "-d", "-E", "-I", "-L", "-n", "-P", "-s"},
    "setsid": set(), "nohup": set(), "command": set(), "builtin": set(), "exec": {"-a"}, "time": {"-f", "-o"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"}, "nice": {"-n"}, "ionice": {"-c", "-n"},
    "stdbuf": {"-i", "-o", "-e"}, "flatpak-spawn": set(),
}
_POZICIJSKI = {"timeout": 1}
_KLJUCNE = ("if", "then", "else", "elif", "do", "while", "until", "!", "{", "}", "fi", "done")
_PRIREDITEV = re.compile(r"^[A-Za-z_]\w*=")
_PREUSMERITEV = re.compile(r"\d*(?:&>>?|>>?|<<<|<<-?|<>|<|>\|)&?\s*(?:\d+-?|[^\s;&|()<>]+)?")
_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_krsitve_programov.log")
#: Kako pogosto nit pregleda potomce.
PREGLED_S = 0.05


class KrsitevPrograma(PermissionError):
    pass


def _niz_za_c(args):
    """Niz za `sh -c` (tudi -ec, -lc); None, ce lupina bere skripto ali standardni vhod."""
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


def _prvi_argument(args):
    """Prvi argument, ki ni izbira (skripta tolmaca ali lupine)."""
    for a in args:
        if a == "--":
            continue
        if not a.startswith("-"):
            return a
    return None


class Varovalo:
    def __init__(self, dovoljeno=None, dnevnik=_LOG, koren=None):
        #: Zacasna mapa teka: lazni programi v njej so dovoljeni (tudi z imenom pkexec).
        self.dovoljeno = os.path.realpath(dovoljeno or tempfile.gettempdir())
        self.dnevnik = dnevnik
        self.koren = koren or os.getpid()
        self.krsitve = []
        self._orig = {}
        self._zaklep = threading.Lock()
        self._ustavi = threading.Event()
        self._nit = None

    # --- odlocanje ---
    def _v_zacasni(self, pot):
        return pot == self.dovoljeno or pot.startswith(self.dovoljeno + os.sep)

    @staticmethod
    def spletni_motor(pravi):
        """Je program (realpath) pomozni proces nasega WebKita (SPLETNI_MOTOR_MAPE)?"""
        return os.path.dirname(pravi) in SPLETNI_MOTOR_MAPE and os.path.basename(pravi) in SPLETNI_MOTOR_PROGRAMI

    def prepovedana_pot(self, pot):
        """Razlog, ce je program na tej poti prepovedan, sicer None. Pot je absolutna (realpath)."""
        if not pot:
            return None
        pravi = os.path.realpath(pot)
        if self._v_zacasni(pravi) or self.spletni_motor(pravi):
            return None
        for p in (pot, pravi):
            if os.path.basename(p) in IMENA:
                return "program za skrbniske pravice %s" % p
            if p.startswith(PREDPONE) or FLATPAK_ID in p:
                return "namesceni Safeer %s" % p
        return None

    @staticmethod
    def _poisci(ime, path):
        if os.sep in ime:
            return os.path.abspath(ime)
        return shutil.which(ime, path=path)

    def razlog_ukaza(self, argv, path=None, globina=0):
        """Razlog, ce bi ukaz (argv) zagnal prepovedan program, sicer None."""
        if globina > 8 or not argv:
            return None
        i = 0
        while i < len(argv):
            ime = os.path.basename(argv[i])
            if _PRIREDITEV.match(argv[i]) or ime in _KLJUCNE:
                i += 1
                continue
            if ime not in _OVOJI:
                break
            z_argumentom = _OVOJI[ime]
            i += 1
            while i < len(argv) and argv[i].startswith("-"):
                izbira = argv[i]
                i += 1
                if izbira == "--":
                    break
                if izbira in z_argumentom:
                    i += 1
            i += _POZICIJSKI.get(ime, 0)
        if i >= len(argv):
            return None
        program = argv[i]
        ime = os.path.basename(program)
        if ime in IMENA and os.sep not in program:
            pot = self._poisci(program, path)
            if pot is None or not self._v_zacasni(os.path.realpath(pot)):
                return "program za skrbniske pravice %s" % (pot or program)
            return None
        pot = self._poisci(program, path)
        razlog = self.prepovedana_pot(pot) if pot else None
        if razlog:
            return razlog
        rep = argv[i + 1:]
        if ime == "flatpak" and "run" in rep and any(FLATPAK_ID in a for a in rep):
            return "namesceni Safeer (flatpak run %s)" % " ".join(a for a in rep if FLATPAK_ID in a)
        if ime in _LUPINE:
            niz = _niz_za_c(rep)
            if niz is not None:
                return self.razlog_lupine(niz, path, globina + 1)
            skripta = _prvi_argument(rep)
            return self.prepovedana_pot(self._poisci(skripta, None) if skripta and os.sep in skripta else None)
        if _TOLMACI.match(ime):
            skripta = _prvi_argument(rep)
            if skripta and os.sep in skripta:
                return self.prepovedana_pot(os.path.abspath(skripta))
        return None

    def razlog_lupine(self, niz, path=None, globina=0):
        """Niz kot lupinski ukaz: vsak del (; && || | & ( ) `...` nove vrstice) posebej."""
        niz = _PREUSMERITEV.sub(" ", niz.replace("\n", ";").replace("`", ";").replace("$(", ";"))
        try:
            lex = shlex.shlex(niz, posix=True, punctuation_chars=True)
            lex.whitespace_split = True
            zeton = list(lex)
        except ValueError:
            return None
        odseki, tekoci = [], []
        for z in zeton:
            if z and set(z) <= set("();<>|&"):
                odseki.append(tekoci)
                tekoci = []
            else:
                tekoci.append(z)
        odseki.append(tekoci)
        for odsek in odseki:
            razlog = self.razlog_ukaza(odsek, path, globina)
            if razlog:
                return razlog
        return None

    def _zapisi(self, kaj):
        ime = os.environ.get("PYTEST_CURRENT_TEST", "?")
        vrstica = "%s | %s | %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), ime, kaj)
        with self._zaklep:
            self.krsitve.append(vrstica)
        try:
            with open(self.dnevnik, "a", encoding="utf-8") as f:
                f.write(vrstica + "\n")
        except OSError:
            pass
        return ime

    def preveri(self, ukaz, shell=False, env=None, executable=None):
        """Podproces: krsitev (izjema), ce bi ukaz zagnal prepovedan program."""
        okolje = env if env is not None else os.environ
        path = okolje.get("PATH") if hasattr(okolje, "get") else None
        if isinstance(ukaz, (bytes, str, os.PathLike)):
            ukaz_s = os.fsdecode(ukaz)
            razlog = self.razlog_lupine(ukaz_s, path) if shell else self.razlog_ukaza([ukaz_s], path)
        else:
            argv = [os.fsdecode(x) for x in ukaz]
            if shell:
                razlog = self.razlog_lupine(argv[0], path) if argv else None
            else:
                razlog = self.razlog_ukaza(argv, path)
        if razlog is None and executable:
            razlog = self.prepovedana_pot(self._poisci(os.fsdecode(executable), path))
        if razlog:
            ime = self._zapisi("zagon: %s" % razlog)
            raise KrsitevPrograma("Varovalo programov: preizkus %s bi zagnal %s - podtakni lazen program v zacasni "
                                  "mapi (tests/varovalo_programov.py)" % (ime, razlog))

    # --- potomci (Linux) ---
    @staticmethod
    def _otroci(pid):
        izid = []
        try:
            niti = os.listdir("/proc/%d/task" % pid)
        except OSError:
            return izid
        for t in niti:
            try:
                with open("/proc/%d/task/%s/children" % (pid, t), encoding="ascii") as f:
                    izid.extend(int(x) for x in f.read().split())
            except (OSError, ValueError):
                continue
        return izid

    def potomci(self):
        videni, vrsta = set(), [self.koren]
        while vrsta:
            p = vrsta.pop()
            for o in self._otroci(p):
                if o not in videni:
                    videni.add(o)
                    vrsta.append(o)
        return videni

    def razlog_procesa(self, pid):
        """Razlog, ce je potomec prepovedan program, sicer None (proces, ki ga ni vec: None)."""
        try:
            with open("/proc/%d/cmdline" % pid, "rb") as f:
                argv = [os.fsdecode(x) for x in f.read().split(b"\0") if x]
        except OSError:
            return None
        try:
            exe = os.readlink("/proc/%d/exe" % pid)
        except OSError:
            exe = None          # program s setuid (pkexec, sudo): exe ni berljiv - odloca ime iz cmdline
        if exe is not None:
            if exe.endswith(" (deleted)"):
                exe = exe[:-len(" (deleted)")]
            razlog = self.prepovedana_pot(exe)
            if razlog:
                return razlog
        elif argv and os.path.basename(argv[0]) in IMENA:
            return "program za skrbniske pravice %s" % argv[0]
        if not argv:
            return None
        ime = os.path.basename(exe or argv[0])
        if ime in _LUPINE or _TOLMACI.match(ime) or ime.startswith("python"):
            skripta = _prvi_argument(argv[1:])
            if skripta and os.path.isabs(skripta):
                return self.prepovedana_pot(skripta)
        return None

    def _pregled(self):
        while not self._ustavi.wait(PREGLED_S):
            try:
                for pid in self.potomci():
                    razlog = self.razlog_procesa(pid)
                    if razlog:
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except OSError:
                            pass
                        self._zapisi("potomec %d ubit: %s" % (pid, razlog))
            except Exception:  # noqa: BLE001 - nit varovala ne sme pasti
                continue

    # --- namestitev ---
    def namesti(self):
        if self._orig:
            return
        varovalo = self
        self._orig = {"system": os.system, "popen": subprocess.Popen.__init__}
        orig_init = self._orig["popen"]

        def popen_init(self_, args, *a, **kw):
            varovalo.preveri(args, kw.get("shell", False), kw.get("env"), kw.get("executable"))
            return orig_init(self_, args, *a, **kw)

        def system(ukaz):
            varovalo.preveri(ukaz, shell=True)
            return varovalo._orig["system"](ukaz)

        subprocess.Popen.__init__, os.system = popen_init, system
        for ime in ("posix_spawn", "posix_spawnp"):
            orig = getattr(os, ime, None)
            if orig is None:
                continue
            self._orig[ime] = orig

            def spawn(path, argv, *a, _orig=orig, **kw):
                env = a[0] if a else kw.get("env")
                varovalo.preveri([os.fsdecode(path)] + [os.fsdecode(x) for x in list(argv)[1:]], env=env)
                return _orig(path, argv, *a, **kw)
            setattr(os, ime, spawn)
        if os.path.isdir("/proc/%d/task" % self.koren):
            self._ustavi.clear()
            self._nit = threading.Thread(target=self._pregled, name="varovalo-programov", daemon=True)
            self._nit.start()

    def odstrani(self):
        if not self._orig:
            return
        subprocess.Popen.__init__ = self._orig["popen"]
        os.system = self._orig["system"]
        for ime in ("posix_spawn", "posix_spawnp"):
            if ime in self._orig:
                setattr(os, ime, self._orig[ime])
        self._orig = {}
        self._ustavi.set()

    def od(self, zacetek):
        with self._zaklep:
            return self.krsitve[zacetek:]

    def stevilo(self):
        with self._zaklep:
            return len(self.krsitve)
