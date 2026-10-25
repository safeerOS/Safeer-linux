"""Pytest: zacasne datoteke preizkusov gredo v eno mapo, ki po koncu teka izgine.

Preizkusi ustvarjajo zacasne mape (tempfile.mkdtemp na vec kot 80 mestih) in vseh ne pobrisejo. Kjer je /tmp na disku
in se sprazni sele ob ponovnem zagonu racunalnika, se je tako v stirih dneh nabralo 5700 map (najdeno 5. 10. 2026).
Vsak tek zato dobi svojo korensko mapo (tempfile.tempdir in TMPDIR, ki ga podedujejo tudi podprocesi); pytest jo ob
koncu pobrise. Ostanke prekinjenih tekov (njihov proces ne obstaja vec) pobrise naslednji tek.
"""
import os
import re
import shutil
import tempfile

_PREDPONA = "safeer-testi-"
_stanje = {}
# Pravi HOME in mape XDG se v preizkusih ne smejo pisati (22. 10. 2026: tek na lastnikovem prenosniku je ustavil dock
# Plank in zapisal lazna sesutja v pravi ~/.cache/safeer-os/dnevnik.log). Preizkus, ki namerno nastavi svoje mape,
# ostane kot je (monkeypatch/patch.dict zamenja vrednost za cas preizkusa).
_IZOLIRANE = (("HOME", ""), ("XDG_CONFIG_HOME", "config"), ("XDG_CACHE_HOME", "cache"),
              ("XDG_DATA_HOME", "share"), ("XDG_STATE_HOME", "state"))


def _pocisti_zapuscene(koren: str) -> None:
    """Mape prejsnjih tekov, katerih proces ne obstaja vec (prekinjen tek). Samo tam, kjer je /proc."""
    if not os.path.isdir("/proc"):
        return
    for ime in os.listdir(koren):
        m = re.match(r"^%s(\d+)-" % re.escape(_PREDPONA), ime)
        if not m or os.path.exists("/proc/" + m.group(1)):
            continue
        pot = os.path.join(koren, ime)
        try:
            if os.lstat(pot).st_uid == os.getuid() and os.path.isdir(pot) and not os.path.islink(pot):
                shutil.rmtree(pot, ignore_errors=True)
        except OSError:
            pass


def _izoliraj() -> None:
    """Zacasna mapa teka ter HOME/XDG/GSETTINGS_BACKEND. Klice se ob uvozu tega conftest.py (naloga 48): pytest
    ga uvozi pred tests/conftest.py, ta pa ze ob uvozu nalozi varovalo_niti, varovalo_signalov in core/ - v
    pytest_configure je bilo to prepozno (moduli bi si zapomnili pravi HOME). Kavelj pytest_load_initial_conftests
    v conftest.py ne pride (pytest ga klice samo vticnikom, ki so nalozeni pred conftest)."""
    if "mapa" in _stanje:
        return
    koren = tempfile.gettempdir()
    try:
        _pocisti_zapuscene(koren)
    except OSError:
        pass
    mapa = tempfile.mkdtemp(prefix="%s%d-" % (_PREDPONA, os.getpid()), dir=koren)
    _stanje.update(mapa=mapa, tempdir=tempfile.tempdir, okolje=os.environ.get("TMPDIR"))
    tempfile.tempdir = mapa
    os.environ["TMPDIR"] = mapa
    dom = os.path.join(mapa, "dom")
    prej = {}
    for ime, pod in _IZOLIRANE:
        prej[ime] = os.environ.get(ime)
        pot = os.path.join(dom, pod) if pod else dom
        os.makedirs(pot, exist_ok=True)
        os.environ[ime] = pot
    # Pravi dconf ostane nedotaknjen: gsettings brez nastavljenega zaledja pise v uporabnikov dconf.
    prej["GSETTINGS_BACKEND"] = os.environ.get("GSETTINGS_BACKEND")
    if not prej["GSETTINGS_BACKEND"]:
        os.environ["GSETTINGS_BACKEND"] = "memory"
    _stanje["okolje_prej"] = prej


# Okolje spreminjamo ob uvozu: pred tests/conftest.py, pred uvozom core/ in pred nitmi (core/okolje_procesa.py).
_izoliraj()


def pytest_configure(config):
    _izoliraj()            # ce je pytest_unconfigure ze pospravil (vec sej v istem procesu, pytester)


def pytest_unconfigure(config):
    mapa = _stanje.pop("mapa", None)
    if not mapa:
        return
    tempfile.tempdir = _stanje.pop("tempdir", None)
    for ime, vrednost in _stanje.pop("okolje_prej", {}).items():
        if vrednost is None:
            os.environ.pop(ime, None)
        else:
            os.environ[ime] = vrednost
    staro = _stanje.pop("okolje", None)
    if staro is None:
        os.environ.pop("TMPDIR", None)
    else:
        os.environ["TMPDIR"] = staro
    shutil.rmtree(mapa, ignore_errors=True)


try:
    import pytest as _pytest

    @_pytest.fixture(autouse=True)
    def _pozabi_manifeste_stremio():
        """Manifesti dodatkov Stremio so v pomnilniku (core/media_servers.py); vsak preizkus zacne brez njih."""
        import sys
        ms = sys.modules.get("core.media_servers")
        if ms is not None and hasattr(ms, "_MANIFESTI"):
            ms._MANIFESTI.clear()
        yield
except ImportError:  # pragma: no cover
    pass
