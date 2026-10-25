"""Razvrstitev preizkusov CI po WebKitu (lastnik 21. in 25. 10. 2026): napake v minutah, WebKit samo nas.

Hitra vrata (posel hitra-vrata, ``--safeer-webkit=brez``): preizkusi, ki WebKita ne nalozijo, tecejo takoj ob potisku,
razdeljeni na vec vzporednih poslov (``--safeer-del=i/n``), na sistemu BREZ WebKitGTK in libsoup (AGENTS.md: preizkus s
sistemskim WebKitGTK ni veljaven). Preizkusi, ki WebKit nalozijo (``--safeer-webkit=samo``), tecejo v poslu
preizkusi-webkit po gradnji, z NASIM WebKitom iz paketa safeer-webkit (/usr/lib/safeer-webkit); ob koncu teka vticnik
preveri, da je vsaka preslikana knjiznica WebKit, JavaScriptCore in libsoup iz nase predpone.

Katere datoteke rabijo WebKit, pove staticna analiza uvozov (razvrsti): neposredna raba (gi.require_version, uvoz iz
gi.repository), uvoz modula, ki WebKit nalozi ob uvozu (tudi posredno), in podproces z zagonom takega programa. Lenobne
uvoze v funkcijah modulov core analiza ne vidi: zato v nacinu brez straza vsak poskus nalaganja WebKit, JavaScriptCore
ali Soup zabelezi in preizkus PODRE - tudi ce ga je koda ujela in sla po nadomestni poti (nic ne zdrsne tiho). Taksno
datoteko dopisi v tests/webkit_preizkusi.txt (povzetek teka izpise vrstice).

Padli najprej (lastnik 25. 10. 2026: »nadaljuj od tam, kjer je preizkus padel«): ``--safeer-padli=POT`` ob koncu
zapise node id padlih preizkusov tega dela; CI datoteko hrani v predpomnilniku veje. Naslednji tek iste veje jih z
``--safeer-najprej-padli`` pozene prve in samo njih (zbere le njihove datoteke) - ce padejo znova, del pade v sekundah;
sele nato tece cel del. Lokalno ostane -p no:cacheprovider in brez teh moznosti.

Brez izbire nacina je vticnik nedejaven (lokalni tek, tools/pre_push_testi.sh: vsi preizkusi v enem procesu). Okolja
procesa ne spreminja (AGENTS.md) in ob uvozu ne uvozi gi.

Uporaba:  python3 -m pytest -p razvrstitev_webkit --safeer-webkit=brez --safeer-del=1/6 tests/
          python3 tests/razvrstitev_webkit.py [--deli N]          izpis razvrstitve in razdelitve
          python3 tests/razvrstitev_webkit.py zdruzi TRAJANJA.json...  nove ocene trajanja (tests/trajanja_preizkusov.json)
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import pytest

#: Imenski prostori GI nasega spletnega pogona: v hitrih vratih jih ni, v poslu preizkusi-webkit so iz nase predpone.
IMENSKI_PROSTORI = frozenset(("WebKit", "WebKit2", "JavaScriptCore", "Soup", "WebKitWebProcessExtension",
                              "WebKit2WebExtension"))
#: Knjiznice, ki morajo biti v poslu preizkusi-webkit vse iz nase gradnje (enako kot core/zasebni_webkit.NASE_KNJIZNICE).
NASE_KNJIZNICE = ("libwebkitgtk-6.0", "libjavascriptcoregtk-6.0", "libsoup-3.0")
NAS_WEBKIT = "/usr/lib/safeer-webkit"
ROCNI_SEZNAM = "tests/webkit_preizkusi.txt"
TRAJANJA = "tests/trajanja_preizkusov.json"
#: Ocena za datoteko brez meritve: povprecje teka 40153444414 (5533 preizkusov v 2102 s, 25. 10. 2026).
PRIVZETO_NA_PREIZKUS = 0.4
#: Mape, ki jih preizkusi dodajo v sys.path (moduli se uvozijo z golim imenom).
MAPE_GOLIH_IMEN = ("tests", "tools", "packaging", "packaging/webkit", "packaging/webkit-deb", "packaging/rqbit")


def _je_datoteka_preizkusov(ime: str) -> bool:
    return ime.endswith(".py") and (ime.startswith("test_") or ime.endswith("_test.py"))


# ------------------------------------------------------------------------------------------------ staticna analiza
class _Obisk(ast.NodeVisitor):
    """Raba WebKita in uvozi modula, loceno: ob uvozu (vrh, tudi telo razreda) in kjerkoli (tudi v funkcijah)."""

    def __init__(self) -> None:
        self.globina = 0
        self.webkit_vrh = False
        self.webkit_kjerkoli = False
        self.uvozi_vrh: Set[str] = set()
        self.uvozi_kjerkoli: Set[str] = set()
        self.podprocesi: Set[str] = set()    # moduli in skripte '*.py' v argumentih zagona podprocesa
        self.preizkusov = 0
        # Klic funkcije ob uvozu (core/safeer_link.py: »Gdk, Gtk, WebKit2 = _nalozi_gtk()«) nalozi WebKit ob uvozu, ceprav
        # je require_version v funkciji: funkcije z WebKitom, klici v njih in klici na vrhu modula.
        self.funkcija: Optional[str] = None
        self.funkcije_webkit: Set[str] = set()
        self.klici_v_funkciji: Dict[str, Set[str]] = {}
        self.uvozi_v_funkciji: Dict[str, Set[str]] = {}
        self.klici_vrh: Set[str] = set()
        self.uvozena_imena: Dict[str, str] = {}     # ime v modulu -> polno ime (modul ali modul.funkcija)

    def _funkcija(self, n) -> None:
        if getattr(n, "name", "").startswith("test"):
            self.preizkusov += 1
        prej = self.funkcija
        if not self.globina and not isinstance(n, ast.Lambda):
            self.funkcija = n.name
            self.klici_v_funkciji.setdefault(n.name, set())
            self.uvozi_v_funkciji.setdefault(n.name, set())
        self.globina += 1
        self.generic_visit(n)
        self.globina -= 1
        self.funkcija = prej

    visit_FunctionDef = visit_AsyncFunctionDef = visit_Lambda = _funkcija

    def _webkit(self) -> None:
        self.webkit_kjerkoli = True
        if not self.globina:
            self.webkit_vrh = True
        elif self.funkcija:
            self.funkcije_webkit.add(self.funkcija)

    def _uvoz(self, ime: str) -> None:
        if not ime:
            return
        self.uvozi_kjerkoli.add(ime)
        if not self.globina:
            self.uvozi_vrh.add(ime)
        elif self.funkcija:
            self.uvozi_v_funkciji[self.funkcija].add(ime)
        deli = ime.split(".")
        if len(deli) >= 3 and deli[0] == "gi" and deli[1] == "repository" and deli[2] in IMENSKI_PROSTORI:
            self._webkit()

    def visit_Import(self, n: ast.Import) -> None:
        for a in n.names:
            self._uvoz(a.name)
            if not self.globina:
                self.uvozena_imena[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]

    def visit_ImportFrom(self, n: ast.ImportFrom) -> None:
        modul = "." * (n.level or 0) + (n.module or "")
        if modul == "gi.repository" and any(a.name in IMENSKI_PROSTORI for a in n.names):
            self._webkit()
        self._uvoz(modul)
        for a in n.names:
            if a.name != "*":
                polno = modul + ("" if modul.endswith(".") else ".") + a.name
                self._uvoz(polno)
                if not self.globina:
                    self.uvozena_imena[a.asname or a.name] = polno

    def visit_Call(self, n: ast.Call) -> None:
        f = n.func
        ime = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
        klican = (f.id if isinstance(f, ast.Name) else
                  "%s.%s" % (f.value.id, f.attr) if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else "")
        if klican:
            if not self.globina:
                self.klici_vrh.add(klican)
            elif self.funkcija:
                self.klici_v_funkciji[self.funkcija].add(klican)
        prvi = n.args[0] if n.args else None
        if ime == "require_version" and isinstance(prvi, ast.Constant) and prvi.value in IMENSKI_PROSTORI:
            self._webkit()
        elif ime == "require_versions" and isinstance(prvi, ast.Dict):
            if any(isinstance(k, ast.Constant) and k.value in IMENSKI_PROSTORI for k in prvi.keys):
                self._webkit()
        elif ime in ("import_module", "__import__") and isinstance(prvi, ast.Constant) and isinstance(prvi.value, str):
            self._uvoz(prvi.value)
        elif ime in ("spec_from_file_location", "run_path"):
            for niz in _nizi(n):
                if niz.endswith(".py"):
                    self._uvoz(os.path.basename(niz)[:-3])
        elif ime in _ZAGONI and isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) \
                and f.value.id in ("subprocess", "os", "pty", "asyncio"):
            # Samo nizi v argumentih zagona: skripta (»safeer_os.py«) ali koda za -c (»import safeer_os«). Branje izvorne
            # kode kot besedila (open(.../safeer_os.py)) ni zagon.
            for niz in _nizi(n):
                if niz.endswith(".py") and "\n" not in niz:
                    self.podprocesi.add(os.path.basename(niz)[:-3])
                for m in _RE_UVOZ_V_KODI.finditer(niz):
                    self.podprocesi.add(m.group(1))
        self.generic_visit(n)


_ZAGONI = frozenset(("Popen", "run", "check_call", "check_output", "call", "spawn", "execv", "execvp", "execve",
                     "create_subprocess_exec"))
_RE_UVOZ_V_KODI = re.compile(r"(?:^|[\s;])(?:import|from)\s+([A-Za-z_][\w.]*)")


def _nizi(klic: ast.Call):
    for arg in list(klic.args) + [k.value for k in klic.keywords]:
        for v in ast.walk(arg):
            if isinstance(v, ast.Constant) and isinstance(v.value, str) and len(v.value) < 4000:
                yield v.value


def _moduli(koren: Path) -> Dict[str, Path]:
    """{ime modula: pot}: programi v korenu, paket core in mape, ki jih preizkusi dodajo v sys.path."""
    m: Dict[str, Path] = {}
    for p in sorted(koren.glob("*.py")):
        m.setdefault(p.stem, p)
    for p in sorted((koren / "core").rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        deli = p.relative_to(koren).with_suffix("").parts
        if deli[-1] == "__init__":
            deli = deli[:-1]
        m.setdefault(".".join(deli), p)
    for mapa in MAPE_GOLIH_IMEN:
        for p in sorted((koren / mapa).glob("*.py")):
            m.setdefault(p.stem, p)
    return m


def _paket(ime: str, pot: Path) -> List[str]:
    deli = ime.split(".") if ime else []
    return deli if pot.name == "__init__.py" else deli[:-1]


def _razresi(surovo: str, paket: List[str], moduli: Dict[str, Path]) -> Set[str]:
    """Moduli repozitorija, ki se izvedejo ob uvozu imena (z nadrejenimi paketi)."""
    if surovo.startswith("."):
        tock = len(surovo) - len(surovo.lstrip("."))
        osnova = paket[: len(paket) - (tock - 1)] if tock > 1 else list(paket)
        ostanek = surovo[tock:]
        surovo = ".".join(osnova + ([ostanek] if ostanek else []))
    izid: Set[str] = set()
    deli = surovo.split(".")
    for i in range(1, len(deli) + 1):
        kand = ".".join(deli[:i])
        if kand in moduli:
            izid.add(kand)
    return izid


def _beri(pot: Path) -> Optional[_Obisk]:
    try:
        drevo = ast.parse(pot.read_text(encoding="utf-8", errors="replace"), filename=str(pot))
    except (SyntaxError, ValueError, OSError):
        return None
    o = _Obisk()
    o.visit(drevo)
    return o


def _ob_uvozu(analiza: Dict[str, "_Obisk"], moduli: Dict[str, Path], vrh: Dict[str, Set[str]]) -> Set[str]:
    """Moduli, ki WebKit nalozijo ze ob uvozu - negibna tocka treh pravil: (1) WebKit na vrhu ali uvoz takega modula na
    vrhu, (2) funkcija z WebKitom: neposredno, s klicem take funkcije ali z lenobnim uvozom modula iz (1), (3) klic take
    funkcije na vrhu modula (svoje ali uvozene iz drugega modula)."""
    def razresi_klic(ime_modula: str, a: "_Obisk", klic: str) -> Optional[Tuple[str, str]]:
        glava, _, rep = klic.partition(".")
        if not rep and glava in a.klici_v_funkciji:
            return ime_modula, glava
        polno = a.uvozena_imena.get(glava)
        if not polno:
            return None
        cilj = polno + ("." + rep if rep else "")
        modul, _, funkcija = cilj.rpartition(".")
        kand = _razresi(modul, _paket(ime_modula, moduli[ime_modula]), moduli)
        return (max(kand, key=len), funkcija) if kand else None

    ob_uvozu = {m for m, a in analiza.items() if a.webkit_vrh}
    webkit = {(m, f) for m, a in analiza.items() for f in a.funkcije_webkit}
    uvozi_fn = {(m, f): set().union(*[_razresi(u, _paket(m, moduli[m]), moduli) for u in uv] or [set()])
                for m, a in analiza.items() for f, uv in a.uvozi_v_funkciji.items()}
    sprememba = True
    while sprememba:
        sprememba = False
        for m, a in analiza.items():
            for f, klici in a.klici_v_funkciji.items():
                if (m, f) not in webkit and (uvozi_fn[(m, f)] & ob_uvozu
                                             or any(razresi_klic(m, a, k) in webkit for k in klici)):
                    webkit.add((m, f))
                    sprememba = True
            if m not in ob_uvozu and (vrh[m] & ob_uvozu or any(razresi_klic(m, a, k) in webkit for k in a.klici_vrh)):
                ob_uvozu.add(m)
                sprememba = True
    return ob_uvozu


def rocni_seznam(koren: Path) -> Set[str]:
    pot = koren / ROCNI_SEZNAM
    if not pot.is_file():
        return set()
    return {v.strip() for v in pot.read_text(encoding="utf-8").splitlines() if v.strip() and not v.startswith("#")}


_ZE_RAZVRSCENO: Dict[str, Tuple[Dict[str, Optional[str]], Dict[str, int]]] = {}


def razvrsti(koren: Path) -> Tuple[Dict[str, Optional[str]], Dict[str, int]]:
    """({datoteka preizkusov: razlog, zakaj rabi WebKit, ali None}, {datoteka: stevilo preizkusov}). Poti od korena.

    Analiza ~12 MB kode traja ~7 s: v istem procesu (vticnik in preizkusi) se izracuna enkrat na koren."""
    kljuc = str(Path(koren).resolve())
    if kljuc not in _ZE_RAZVRSCENO:
        _ZE_RAZVRSCENO[kljuc] = _razvrsti(Path(koren))
    razvrstitev, stevila = _ZE_RAZVRSCENO[kljuc]
    return dict(razvrstitev), dict(stevila)


def _razvrsti(koren: Path) -> Tuple[Dict[str, Optional[str]], Dict[str, int]]:
    moduli = _moduli(koren)
    analiza = {ime: _beri(pot) for ime, pot in moduli.items()}
    analiza = {ime: a for ime, a in analiza.items() if a is not None}
    vrh = {ime: set().union(*[_razresi(u, _paket(ime, moduli[ime]), moduli) for u in a.uvozi_vrh] or [set()])
           for ime, a in analiza.items()}
    kjerkoli = {ime: set().union(*[_razresi(u, _paket(ime, moduli[ime]), moduli) for u in a.uvozi_kjerkoli] or [set()])
                for ime, a in analiza.items()}
    ob_uvozu = _ob_uvozu(analiza, moduli, vrh)
    rocno = rocni_seznam(koren)
    izid: Dict[str, Optional[str]] = {}
    stevila: Dict[str, int] = {}
    for p in sorted((koren / "tests").rglob("*.py")):
        if not _je_datoteka_preizkusov(p.name) or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(koren).as_posix()
        a = analiza.get(p.stem)
        stevila[rel] = a.preizkusov if a else 0
        razlog: Optional[str] = None
        if a is None:
            razlog = None                         # napaka skladnje: pytest jo pokaze v hitrih vratih
        elif a.webkit_kjerkoli:
            razlog = "neposredno"
        elif p.stem in ob_uvozu or kjerkoli[p.stem] & ob_uvozu:
            razlog = "uvoz " + sorted((kjerkoli[p.stem] | vrh[p.stem]) & ob_uvozu)[0]
        elif {x for u in a.podprocesi for x in _razresi(u, [], moduli)} & ob_uvozu:
            razlog = "podproces " + sorted({x for u in a.podprocesi for x in _razresi(u, [], moduli)} & ob_uvozu)[0]
        if razlog is None and rel in rocno:
            razlog = "rocno (%s)" % ROCNI_SEZNAM
        izid[rel] = razlog
    return izid, stevila


def trajanja(koren: Path) -> Dict[str, float]:
    try:
        podatki = json.loads((Path(koren) / TRAJANJA).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: float(v) for k, v in podatki.get("datoteke", {}).items()}


def razdeli(datoteke: Iterable[str], n: int, stevila: Dict[str, int], ocene: Dict[str, float]) -> Dict[str, int]:
    """{datoteka: del 1..n}: pozresno po oceni trajanja (najdaljsa najprej v najmanj zaseden del), deterministicno."""
    teze = {f: ocene.get(f, PRIVZETO_NA_PREIZKUS * max(1, stevila.get(f, 1))) for f in datoteke}
    deli = [[0.0, i] for i in range(1, n + 1)]
    izid: Dict[str, int] = {}
    for f in sorted(teze, key=lambda x: (-teze[x], x)):
        najmanj = min(deli)
        izid[f] = najmanj[1]
        najmanj[0] += teze[f]
    return izid


def ocena_delov(razdelitev: Dict[str, int], stevila: Dict[str, int], ocene: Dict[str, float]) -> Dict[int, float]:
    vsote: Dict[int, float] = {}
    for f, d in razdelitev.items():
        vsote[d] = vsote.get(d, 0.0) + ocene.get(f, PRIVZETO_NA_PREIZKUS * max(1, stevila.get(f, 1)))
    return vsote


# ------------------------------------------------------------------------------------------------ straza (nacin brez)
class _OvojNalagalnika:
    """Nalagalnik modula gi: po izvedbi zamenja gi.require_version s strazo (pred prvo uporabo v kodi)."""

    def __init__(self, pravi, straza: "Straza") -> None:
        self._pravi = pravi
        self._straza = straza

    def create_module(self, spec):
        return self._pravi.create_module(spec)

    def exec_module(self, modul) -> None:
        self._pravi.exec_module(modul)
        self._straza.zakrpaj_gi(modul)

    def __getattr__(self, ime):
        return getattr(self._pravi, ime)


class Straza:
    """Zabelezi vsak poskus nalaganja imenskih prostorov IMENSKI_PROSTORI in ga zavrne kot manjkajoc prostor."""

    def __init__(self) -> None:
        self.kje = "zagon"
        self._poskusi: List[Tuple[str, str, str]] = []      # (kje, prostor, nacin)
        self._gi_zakrpan = False

    # -- importlib (sys.meta_path)
    def find_spec(self, ime, pot=None, cilj=None):
        if ime.startswith("gi.repository."):
            prostor = ime.split(".")[2]
            if prostor in IMENSKI_PROSTORI:
                self.zabelezi(prostor, "uvoz gi.repository.%s" % prostor)
                raise ImportError("%s: v hitrih vratih ni WebKita (tests/razvrstitev_webkit.py)" % ime, name=ime)
        if ime == "gi" and not self._gi_zakrpan:
            for iskalnik in sys.meta_path:
                if iskalnik is self or not hasattr(iskalnik, "find_spec"):
                    continue
                spec = iskalnik.find_spec(ime, pot, cilj)
                if spec is not None:
                    if spec.loader is not None and hasattr(spec.loader, "exec_module"):
                        spec.loader = _OvojNalagalnika(spec.loader, self)
                    return spec
        return None

    def zakrpaj_gi(self, gi) -> None:
        pravi = gi.require_version
        if getattr(pravi, "_safeer_straza", False):
            self._gi_zakrpan = True
            return
        straza = self

        def require_version(namespace, version):
            if namespace in IMENSKI_PROSTORI:
                straza.zabelezi(namespace, "gi.require_version('%s', '%s')" % (namespace, version))
                raise ValueError("Namespace %s not available (hitra vrata Safeer: preizkus brez WebKita, "
                                 "tests/razvrstitev_webkit.py)" % namespace)
            return pravi(namespace, version)

        require_version._safeer_straza = True
        gi.require_version = require_version
        self._gi_zakrpan = True

    def namesti(self) -> "Straza":
        if self not in sys.meta_path:
            sys.meta_path.insert(0, self)
        if "gi" in sys.modules:
            self.zakrpaj_gi(sys.modules["gi"])
        return self

    def zabelezi(self, prostor: str, nacin: str) -> None:
        self._poskusi.append((self.kje, prostor, nacin))

    def vzemi(self) -> List[Tuple[str, str, str]]:
        poskusi, self._poskusi = self._poskusi, []
        return poskusi


def preslikane_knjiznice(maps: Optional[str] = None) -> Dict[str, Set[str]]:
    """{ime iz NASE_KNJIZNICE: poti} iz /proc/self/maps (kot core/zasebni_webkit.nalozene_knjiznice)."""
    if maps is None:
        try:
            with open("/proc/self/maps", encoding="utf-8", errors="replace") as f:
                maps = f.read()
        except OSError:
            return {}
    izid: Dict[str, Set[str]] = {}
    for vrstica in maps.splitlines():
        deli = vrstica.split(None, 5)
        if len(deli) < 6 or not deli[5].startswith("/"):
            continue
        pot = deli[5].strip()
        if pot.endswith(" (deleted)"):
            pot = pot[: -len(" (deleted)")]
        for k in NASE_KNJIZNICE:
            if os.path.basename(pot).startswith(k + ".so"):
                izid.setdefault(k, set()).add(pot)
    return izid


def tuje_knjiznice(preslikane: Dict[str, Set[str]], predpona: str) -> List[str]:
    koren = os.path.realpath(predpona).rstrip(os.sep) + os.sep
    return sorted(p for poti in preslikane.values() for p in poti if not os.path.realpath(p).startswith(koren))


# ------------------------------------------------------------------------------------------------ vticnik pytest
def beri_padle(pot: Optional[str]) -> Set[str]:
    """Node id padlih preizkusov prejsnjega teka (JSON seznam nizov); manjkajoca ali pokvarjena datoteka = noben."""
    if not pot:
        return set()
    try:
        with open(pot, encoding="utf-8") as f:
            podatki = json.load(f)
    except (OSError, ValueError):
        return set()
    return {x for x in podatki if isinstance(x, str) and x.startswith("tests/")} if isinstance(podatki, list) else set()


class _Stanje:
    def __init__(self, nacin: str, koren: Path, del_: Optional[Tuple[int, int]], nas_webkit: str,
                 pot_trajanj: Optional[str], pot_padlih: Optional[str] = None, najprej_padli: bool = False) -> None:
        self.nacin = nacin
        self.koren = koren
        self.del_ = del_
        self.nas_webkit = nas_webkit
        self.pot_trajanj = pot_trajanj
        self.pot_padlih = pot_padlih
        self.najprej_padli = najprej_padli
        self.prej_padli = beri_padle(pot_padlih)
        self.padli: Set[str] = set()
        self.razvrstitev, self.stevila = razvrsti(koren)
        self.webkit = {f for f, r in self.razvrstitev.items() if r}
        self.razdelitev: Dict[str, int] = {}
        if del_:
            izbrane = [f for f in self.razvrstitev if (f in self.webkit) == (nacin == "samo")]
            self.razdelitev = razdeli(izbrane, del_[1], self.stevila, trajanja(koren))
        self.straza: Optional[Straza] = None
        self.krsitve: Dict[str, List[str]] = {}
        self.napake_seje: List[str] = []
        self.knjiznice_zaznane = False
        self.izpusceno = 0
        self.trajanja: Dict[str, float] = {}


_stanje: Optional[_Stanje] = None


def pytest_addoption(parser) -> None:
    g = parser.getgroup("safeer", "Safeer: razvrstitev preizkusov po WebKitu (CI)")
    g.addoption("--safeer-webkit", choices=("brez", "samo"), default=None,
                help="brez: preizkusi brez WebKita (hitra vrata, straza); samo: preizkusi z WebKitom (nas WebKit)")
    g.addoption("--safeer-del", default=None, help="i/n: samo i-ti od n delov izbranih datotek")
    g.addoption("--safeer-padli", default=None, help="JSON s padlimi preizkusi: prebere prejsnje, ob koncu zapise nove")
    g.addoption("--safeer-najprej-padli", action="store_true", default=False,
                help="pozeni samo preizkuse, ki so v --safeer-padli (prejsnji tek iste veje), in koncaj")
    g.addoption("--safeer-koren", default=None, help="koren repozitorija (privzeto mapa nad tests/)")
    g.addoption("--safeer-nas-webkit", default=NAS_WEBKIT, help="predpona nasega WebKita v nacinu samo")
    g.addoption("--safeer-trajanja", default=None, help="zapisi trajanje po datotekah v JSON (za trajanja_preizkusov)")


def _del(vrednost: Optional[str]) -> Optional[Tuple[int, int]]:
    if not vrednost:
        return None
    try:
        i, n = (int(x) for x in vrednost.split("/", 1))
    except ValueError:
        raise SystemExit("--safeer-del mora biti i/n, ne %r" % vrednost) from None
    if not 1 <= i <= n:
        raise SystemExit("--safeer-del: i mora biti med 1 in n (%r)" % vrednost)
    return i, n


def _rel(stanje: _Stanje, pot) -> Optional[str]:
    try:
        return Path(pot).resolve().relative_to(stanje.koren.resolve()).as_posix()
    except ValueError:
        return None


def pytest_load_initial_conftests(early_config, parser, args) -> None:
    """Pred uvozom conftest.py: razvrstitev in (nacin brez) straza, da je vidi ze prvi uvoz gi."""
    global _stanje
    ns = early_config.known_args_namespace
    nacin = getattr(ns, "safeer_webkit", None)
    if not nacin:
        return
    koren = Path(getattr(ns, "safeer_koren", None) or Path(__file__).resolve().parents[1])
    _stanje = _Stanje(nacin, koren, _del(getattr(ns, "safeer_del", None)),
                      getattr(ns, "safeer_nas_webkit", None) or NAS_WEBKIT, getattr(ns, "safeer_trajanja", None),
                      getattr(ns, "safeer_padli", None), bool(getattr(ns, "safeer_najprej_padli", False)))
    if nacin == "brez":
        _stanje.straza = Straza().namesti()


def pytest_ignore_collect(collection_path, config):
    st = _stanje
    if st is None or not _je_datoteka_preizkusov(Path(collection_path).name):
        return None
    rel = _rel(st, collection_path)
    if rel is None or rel not in st.razvrstitev:
        return None
    izpusti = (rel in st.webkit) if st.nacin == "brez" else (rel not in st.webkit)
    if not izpusti and st.del_ and st.razdelitev.get(rel) != st.del_[0]:
        izpusti = True
    if not izpusti and st.najprej_padli and not any(p == rel or p.startswith(rel + "::") for p in st.prej_padli):
        izpusti = True                            # najprej padli: samo datoteke s prej padlimi preizkusi
    if izpusti:
        st.izpusceno += 1
        return True
    return None


def pytest_collectstart(collector) -> None:
    if _stanje is not None and _stanje.straza is not None:
        _stanje.straza.kje = "zbiranje " + (collector.nodeid or "seja")


def _sporocilo(poskusi) -> str:
    vrstice = ["Straza hitrih vrat: preizkus je poskusil naloziti spletni pogon, ki ga v hitrih vratih ni "
               "(lastnik 21. 10. 2026: preizkus s sistemskim WebKitGTK ni veljaven)."]
    vrstice += ["  %s: %s" % (kje, nacin) for kje, _, nacin in poskusi[:5]]
    vrstice.append("Datoteko dopisi v %s - tece v poslu preizkusi-webkit z nasim WebKitom." % ROCNI_SEZNAM)
    return "\n".join(vrstice)


#: Razlog preskoka, ki pomeni »WebKita ni« (ne npr. »WebKit brez WebRTC«): tak preskok bi bil tih zdrs - v hitrih vratih
#: preizkus WebKit rabi (dopisi ga na seznam), v poslu preizkusi-webkit pa nas WebKit ne dela.
_RE_PRESKOK = re.compile(r"(?i)(webkit|javascriptcore|libsoup|\bsoup\b)")
_RE_PRESKOK_ZAKAJ = re.compile(r"(?i)(potreb|ni na voljo|not installed|not available|is missing|\bni webkit|\bni wpe)")


def _razlog_preskoka(porocilo) -> Optional[str]:
    if not porocilo.skipped or hasattr(porocilo, "wasxfail"):
        return None
    dolgo = porocilo.longrepr
    razlog = str(dolgo[2]) if isinstance(dolgo, tuple) and len(dolgo) == 3 else str(dolgo or "")
    if _RE_PRESKOK.search(razlog) and _RE_PRESKOK_ZAKAJ.search(razlog):
        return razlog
    return None


def _sporocilo_preskoka(nacin: str, razlog: str) -> str:
    if nacin == "brez":
        return ("Straza hitrih vrat: preizkus je preskocen, ker WebKita ni (%s). V hitrih vratih ne sme tiho izpasti: "
                "datoteko dopisi v %s - tece v poslu preizkusi-webkit z nasim WebKitom." % (razlog, ROCNI_SEZNAM))
    return ("Posel preizkusi-webkit: preizkus je preskocen, ker WebKita ni (%s), ceprav je nas WebKit namescen - "
            "preveri GI_TYPELIB_PATH in paket safeer-webkit." % razlog)


def _zabelezi_krsitev(st: _Stanje, pot: str, poskusi) -> None:
    st.krsitve.setdefault(pot, []).extend("%s: %s" % (kje, nacin) for kje, _, nacin in poskusi)


def _uveljavi(st: _Stanje, porocilo, pot: str) -> None:
    """Poskus nalaganja (nacin brez) ali preskok zaradi manjkajocega WebKita (oba nacina) porocilo spremeni v padec."""
    poskusi = st.straza.vzemi() if st.straza is not None else []
    if poskusi:
        _zabelezi_krsitev(st, pot, poskusi)
        if porocilo.outcome == "failed":
            porocilo.sections.append(("straza WebKit", _sporocilo(poskusi)))
        else:
            porocilo.outcome = "failed"
            porocilo.longrepr = _sporocilo(poskusi)
        return
    razlog = _razlog_preskoka(porocilo)
    if razlog:
        _zabelezi_krsitev(st, pot, [(porocilo.nodeid, "", "preskok: " + razlog)])
        porocilo.outcome = "failed"
        porocilo.longrepr = _sporocilo_preskoka(st.nacin, razlog)
        return
    # Nacin brez: knjiznica spletnega pogona v procesu tudi mimo gi (npr. vticnik GStreamer souphttpsrc nalozi libsoup):
    # po vsakem preizkusu, dokler je ni (en pregled /proc/self/maps na preizkus), da je padec pripisan pravemu preizkusu.
    if st.nacin == "brez" and getattr(porocilo, "when", None) == "teardown" and not st.knjiznice_zaznane:
        preslikane = preslikane_knjiznice()
        if preslikane:
            st.knjiznice_zaznane = True
            poti = sorted(p for vse in preslikane.values() for p in vse)
            _zabelezi_krsitev(st, pot, [(porocilo.nodeid, "", "preslikana knjiznica " + ", ".join(poti))])
            porocilo.outcome = "failed"
            porocilo.longrepr = ("Straza hitrih vrat: po tem preizkusu je v procesu knjiznica spletnega pogona (%s). "
                                 "Datoteko dopisi v %s." % (", ".join(poti), ROCNI_SEZNAM))


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    izid = yield
    st = _stanje
    if st is None:
        return
    _uveljavi(st, izid.get_result(), _rel(st, getattr(collector, "path", "")) or collector.nodeid)


def pytest_runtest_logstart(nodeid, location) -> None:
    if _stanje is not None and _stanje.straza is not None:
        _stanje.straza.kje = nodeid


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    izid = yield
    st = _stanje
    if st is None:
        return
    _uveljavi(st, izid.get_result(), _rel(st, item.path) or item.nodeid)


def pytest_collection_modifyitems(session, config, items) -> None:
    st = _stanje
    if st is None or not st.najprej_padli:
        return
    izbrani = [i for i in items if i.nodeid in st.prej_padli or i.nodeid.split("::", 1)[0] in st.prej_padli]
    ostali = [i for i in items if i not in izbrani]
    if ostali:
        config.hook.pytest_deselected(items=ostali)
    items[:] = izbrani
    if not izbrani:
        pytest.exit("V tem delu ni prej padlih preizkusov (premaknjeni ali odstranjeni) - tece cel del.", returncode=0)


def pytest_runtest_logreport(report) -> None:
    st = _stanje
    if st is None:
        return
    if report.failed:
        st.padli.add(report.nodeid)
    if st.pot_trajanj:
        pot = report.nodeid.split("::", 1)[0]
        st.trajanja[pot] = st.trajanja.get(pot, 0.0) + float(getattr(report, "duration", 0.0) or 0.0)


def pytest_collectreport(report) -> None:
    """Napaka zbiranja datoteke: naslednji tek najprej pozene celo datoteko."""
    st = _stanje
    if st is not None and report.failed and report.nodeid.startswith("tests/"):
        st.padli.add(report.nodeid.split("::", 1)[0])


def pytest_sessionstart(session) -> None:
    """Nacin samo: pred prvim preizkusom nas WebKit iz nase predpone z odtisom gradnje, sicer tek ne zacne."""
    st = _stanje
    if st is None or st.nacin != "samo" or session.config.option.collectonly:
        return
    try:
        import gi
        gi.require_version("WebKit", "6.0")
        from gi.repository import WebKit
        razlicica = (WebKit.get_major_version(), WebKit.get_minor_version(), WebKit.get_micro_version())
    except (ImportError, ValueError) as e:
        pytest.exit("Nas WebKit se ni nalozil (%s): GI_TYPELIB_PATH mora kazati na %s/lib/girepository-1.0"
                    % (e, st.nas_webkit), returncode=3)
    preslikane = preslikane_knjiznice()
    tuje = tuje_knjiznice(preslikane, st.nas_webkit)
    odtis = os.path.join(st.nas_webkit, "share", "webkitgtk-safeer", "odtis")
    if not preslikane.get("libwebkitgtk-6.0") or tuje or not os.path.isfile(odtis):
        pytest.exit("Ni nas WebKit: preslikane %s, tuje %s, odtis %s" % (sorted(preslikane), tuje, os.path.isfile(odtis)),
                    returncode=3)
    session.config._safeer_webkit = "WebKitGTK %d.%d.%d iz %s" % (razlicica + (sorted(preslikane["libwebkitgtk-6.0"])[0],))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtestloop(session):
    yield
    st = _stanje
    if st is None or session.config.option.collectonly or not session.testscollected:
        return
    if st.straza is not None:
        ostanek = st.straza.vzemi()
        if ostanek:
            _zabelezi_krsitev(st, "zunaj preizkusa", ostanek)
            st.napake_seje.append(_sporocilo(ostanek))
    preslikane = preslikane_knjiznice()
    if st.nacin == "brez" and preslikane and not st.knjiznice_zaznane:
        st.napake_seje.append("V hitrih vratih je bila preslikana knjiznica spletnega pogona: %s"
                              % sorted(p for poti in preslikane.values() for p in poti))
    if st.nacin == "samo":
        tuje = tuje_knjiznice(preslikane, st.nas_webkit)
        if tuje:
            st.napake_seje.append("Preizkusi so nalozili tuj WebKit/libsoup (ne iz %s): %s" % (st.nas_webkit, tuje))
    if st.napake_seje:
        # Izhodna koda iz stevila padlih: tests/conftest.py konca proces z os._exit(izhodna koda seje).
        session.testsfailed += 1


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    st = _stanje
    if st is None:
        return
    w = terminalreporter
    w.write_sep("-", "razvrstitev WebKit (tests/razvrstitev_webkit.py)")
    opis = "nacin %s" % st.nacin
    if st.del_:
        opis += ", del %d/%d" % st.del_
    if st.najprej_padli:
        opis += ", najprej padli prejsnjega teka (%d)" % len(st.prej_padli)
    w.write_line("%s: %d datotek z WebKitom, %d brez, izpusceno v tem teku %d" % (
        opis, len(st.webkit), len(st.razvrstitev) - len(st.webkit), st.izpusceno))
    if getattr(config, "_safeer_webkit", None):
        w.write_line(config._safeer_webkit)
    try:
        import resource
        jaz, otroci = (resource.getrusage(x).ru_maxrss // 1024 for x in (resource.RUSAGE_SELF, resource.RUSAGE_CHILDREN))
        w.write_line("najvecji RSS: proces preizkusov %d MiB, najvecji otrok %d MiB" % (jaz, otroci))
    except (ImportError, OSError, ValueError):
        pass
    if st.krsitve:
        w.write_line("Poskusi nalaganja WebKita (dopisi v %s):" % ROCNI_SEZNAM, red=True)
        for pot in sorted(st.krsitve):
            w.write_line(pot, red=True)
            for k in st.krsitve[pot][:3]:
                w.write_line("    " + k)
    for napaka in st.napake_seje:
        w.write_line(napaka, red=True)


def pytest_sessionfinish(session, exitstatus) -> None:
    st = _stanje
    if st is None:
        return
    if st.pot_trajanj:
        with open(st.pot_trajanj, "w", encoding="utf-8") as f:
            json.dump({k: round(v, 2) for k, v in sorted(st.trajanja.items())}, f, indent=0)
    if st.pot_padlih:
        # Tudi prazen seznam: naslednji tek ne sme vzeti starejsega (ze popravljenih) padcev.
        with open(st.pot_padlih, "w", encoding="utf-8") as f:
            json.dump(sorted(st.padli), f, indent=0)


# ------------------------------------------------------------------------------------------------ ukazna vrstica
def _glavni(argv: List[str]) -> int:
    koren = Path(__file__).resolve().parents[1]
    if argv and argv[0] == "zdruzi":
        vsote: Dict[str, float] = {}
        for pot in argv[1:]:
            for k, v in json.loads(Path(pot).read_text(encoding="utf-8")).items():
                vsote[k] = vsote.get(k, 0.0) + float(v)
        json.dump({"opis": "Trajanje preizkusov po datotekah v CI (s), za enakomerno razdelitev hitrih vrat "
                           "(tests/razvrstitev_webkit.py zdruzi).", "datoteke": {k: round(v, 1) for k, v in sorted(vsote.items())}},
                  sys.stdout, indent=1, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    n = int(argv[argv.index("--deli") + 1]) if "--deli" in argv else 6
    razvrstitev, stevila = razvrsti(koren)
    webkit = {f: r for f, r in razvrstitev.items() if r}
    brez = [f for f in razvrstitev if f not in webkit]
    ocene = trajanja(koren)
    print("Z WebKitom (posel preizkusi-webkit): %d datotek, %d preizkusov" % (len(webkit), sum(stevila[f] for f in webkit)))
    for f, r in sorted(webkit.items()):
        print("  %-55s %s" % (f, r))
    razdelitev = razdeli(brez, n, stevila, ocene)
    print("Brez WebKita (hitra vrata): %d datotek, %d preizkusov, ocena po delih (s):" % (
        len(brez), sum(stevila[f] for f in brez)))
    for d, s in sorted(ocena_delov(razdelitev, stevila, ocene).items()):
        print("  del %d/%d: %4.0f s, %d datotek" % (d, n, s, sum(1 for x in razdelitev.values() if x == d)))
    return 0


if __name__ == "__main__":
    sys.exit(_glavni(sys.argv[1:]))
