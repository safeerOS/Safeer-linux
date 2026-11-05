"""Ena lupina namizja na sejo (lastnik, 5. 11. 2026): na testnem PC sta tekli dve lupini (stara od 05:50, 89 MB PSS), ker
streznik v Safeer OS ob novi povezavi zapre staro, stara pa se poveze nazaj. Nov zagon lupine prevzame sejo
(core/lupina_proces.prevzemi_sejo): staro konca, tujega procesa s ponovno uporabljenim PID ne."""
import fcntl
import os
import subprocess
import sys
import tempfile
import time

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import lupina_proces  # noqa: E402

STARA = """import sys, time
sys.path.insert(0, sys.argv[1])
from core import lupina_proces
z = lupina_proces.prevzemi_sejo(sys.argv[2])
print("zaklep" if z else "brez", flush=True)
time.sleep(60)
"""


def _konec(p, cas=5.0):
    konec = time.monotonic() + cas
    while time.monotonic() < konec:
        if p.poll() is not None:
            return True
        time.sleep(0.05)
    return False


def test_nova_lupina_prevzame_staro():
    with tempfile.TemporaryDirectory() as d:
        skripta = os.path.join(d, "lupina_proces.py")       # ime kot prava lupina (_je_lupina gleda ukazno vrstico)
        with open(skripta, "w", encoding="utf-8") as f:
            f.write(STARA)
        mapa = os.path.join(d, "seja")
        os.mkdir(mapa, 0o700)
        stara = subprocess.Popen([sys.executable, "-I", skripta, KOREN, mapa], stdout=subprocess.PIPE, text=True,
                                 env={"PATH": "/usr/bin:/bin"})
        try:
            assert stara.stdout.readline().strip() == "zaklep"
            z = lupina_proces.prevzemi_sejo(mapa, rok=2.0)
            assert z is not None, "nova lupina ni dobila seje"
            assert _konec(stara), "stara lupina tece naprej"
            with open(os.path.join(mapa, lupina_proces.ZAKLEP), encoding="utf-8") as f:
                assert f.read().split() == [str(os.getpid())]
            z.close()
        finally:
            if stara.poll() is None:
                stara.kill()
            stara.wait(5)
            stara.stdout.close()


def test_tuj_proces_s_pidom_iz_zaklepa_ostane():
    with tempfile.TemporaryDirectory() as mapa:
        tuj = subprocess.Popen(["sleep", "30"])
        drzi = open(os.path.join(mapa, lupina_proces.ZAKLEP), "a+b")  # noqa: SIM115
        try:
            fcntl.flock(drzi, fcntl.LOCK_EX | fcntl.LOCK_NB)
            drzi.write(b"%d\n" % tuj.pid)
            drzi.flush()
            assert lupina_proces.prevzemi_sejo(mapa, rok=0.3) is None
            assert tuj.poll() is None, "tuj proces s ponovno uporabljenim PID je bil ustavljen"
        finally:
            drzi.close()
            tuj.kill()
            tuj.wait(5)


def test_main_vzame_zaklep_pred_qt():
    with open(os.path.join(KOREN, "core", "lupina_proces.py"), encoding="utf-8") as f:
        koda = f.read()
    glavni = koda.split("def main()", 1)[1]
    assert glavni.index("prevzemi_sejo(") < glavni.index("os_lupina.pripravi(")
