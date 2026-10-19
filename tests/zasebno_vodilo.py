"""Zasebno vodilo D-Bus za preizkuse: lasten dbus-daemon kot navaden podproces, brez Gio.TestDBus.

Zakaj ne Gio.TestDBus (19. 10. 2026): up() v vecnitnem procesu naredi dvoje, kar tam ni varno - fork() brez exec
(proces-cuvaj, ki dbus-daemon pobije, ko nas proces umre) in g_setenv naslova vodila (down() pa g_unsetenv), medtem ko
niti prejsnjih preizkusov (strezniki, GDBus, WebKit) tecejo in okolje berejo. Vsi preizkusi tecejo v enem procesu:
lokalni polni tek se je sesul v test_obvestila.setUp ob up() (Fatal Python error: Segmentation fault), CI pa je od
19. 10. na koncu teka izpisoval Fatal Python error iz procesa-cuvaja. Tu je dbus-daemon navaden podproces (fork+exec
prek subprocess), okolja procesa nihce ne spreminja: naslov dobi samo, kdor ga zahteva (povezava(), okolje()).

Uporablja ga tudi conftest.py (vodilo seje za ves tek).
"""
import os
import shutil
import subprocess
import tempfile

#: Nastavitev zasebnega vodila: brez storitvenih map (nic se ne zazene samo ob klicu imena, zato po teku ne ostane
#: noben proces), dovoljeno vse - enako kot Gio.TestDBus.
NASTAVITEV = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:tmpdir=%s</listen>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


def _s_cuvajem(ukaz: list) -> list:
    """Ce pytest umre (tudi SIGKILL), jedro vodilu poslje SIGTERM (PR_SET_PDEATHSIG) - nic ne ostane teci. Nastavi ga
    setpriv (util-linux) pred exec, ne preexec_fn: ta bi v otroku vecnitnega procesa izvajal Python (mrtva zanka)."""
    setpriv = shutil.which("setpriv")
    return [setpriv, "--pdeathsig", "TERM"] + ukaz if setpriv else ukaz


def na_voljo() -> bool:
    return shutil.which("dbus-daemon") is not None


class ZasebnoVodilo:
    """dbus-daemon za en preizkus ali ves tek. `naslov` je prazen, ce dbus-daemon ni na voljo.

        with ZasebnoVodilo() as vodilo:
            povezava = vodilo.povezava(Gio)
    """

    def __init__(self) -> None:
        self.mapa = tempfile.mkdtemp(prefix="safeer-vodilo-")
        self.naslov = ""
        self._proces = None
        program = shutil.which("dbus-daemon")
        if not program:
            return
        nastavitev = os.path.join(self.mapa, "vodilo.conf")
        with open(nastavitev, "w", encoding="utf-8") as d:
            d.write(NASTAVITEV % self.mapa)
        self._proces = subprocess.Popen(
            _s_cuvajem([program, "--config-file=" + nastavitev, "--nofork", "--nopidfile", "--print-address=1"]),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.naslov = (self._proces.stdout.readline() or "").strip()
        if not self.naslov:
            self.ustavi()

    def povezava(self, Gio):
        """Nova povezava na to vodilo (lastna, ne deljena Gio.bus_get): zapre jo klicatelj (close_sync)."""
        return Gio.DBusConnection.new_for_address_sync(
            self.naslov, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)

    def okolje(self) -> dict:
        """Okolje za podproces (npr. gdbus --session), ki naj govori s tem vodilom - okolje tega procesa ostane."""
        return dict(os.environ, DBUS_SESSION_BUS_ADDRESS=self.naslov)

    def ustavi(self) -> None:
        proces, self._proces = self._proces, None
        if proces is not None:
            proces.terminate()
            try:
                proces.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proces.kill()
                proces.wait(timeout=5)
            if proces.stdout is not None:
                proces.stdout.close()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *_a) -> None:
        self.ustavi()
