#!/usr/bin/env python3
"""PGO (profile-guided optimization) za nas WebKitGTK - razlicici modula in manifesta brskalnika v build/pgo/.

WebKitGTK 2.54 (Source/cmake/WebKitCommon.cmake) ima PGO samo s Clangom, v dveh fazah:
  1) -DENABLE_LLVM_PROFILE_GENERATION=ON: knjiznice z -fprofile-generate; pomozni procesi (WebKitWebProcess,
     WebKitNetworkProcess) ob SIGTERM zapisejo profil (AuxiliaryProcessMain.cpp), pot doloci LLVM_PROFILE_FILE.
  2) -DUSE_PGO_PROFILE=ON -DPGO_PROFILE_PATH=<.profdata>: -fprofile-use pri prevodu in povezavi (ThinLTO).
Profil mora biti iz istega izvora, popravkov in prevajalnika; .profraw zato zdruzi llvm-profdata iz iste razsiritve
llvm22 v gradnji flatpak-builderja (modul webkitgtk6-safeer-pgo-profil pred WebKitom).

  python3 packaging/webkit/pgo.py ucenje                -> build/pgo/io.github.memelandfaner.SafeerBrowser.yml
  python3 packaging/webkit/pgo.py uporaba MAPA_PROFRAW  -> isto, s profilom iz MAPA_PROFRAW/*.profraw

Izpise pot do manifesta. Uporablja ga le rocni tek CI (linux-packages.yml, workflow_dispatch z vhodom pgo);
privzeta gradnja izdaje ostane en posel brez PGO.
"""
import pathlib
import re
import sys

KOREN = pathlib.Path(__file__).resolve().parents[2]
WEBKIT = KOREN / "packaging" / "webkit"
MODUL = WEBKIT / "webkitgtk6-safeer.yml"
MANIFEST = KOREN / "io.github.memelandfaner.SafeerBrowser.yml"
PROFDATA = "/app/share/safeer-pgo/webkit.profdata"
LTO = "  - -DLTO_MODE=thin\n"

PROFIL = """\
# Zdruzi .profraw iz ucnega teka (Speedometer 3.1) z llvm-profdata iste razlicice kot prevajalnik WebKita.
name: webkitgtk6-safeer-pgo-profil
buildsystem: simple
build-options:
  append-path: /usr/lib/sdk/llvm22/bin
  prepend-ld-library-path: /usr/lib/sdk/llvm22/lib
build-commands:
  - ls -l *.profraw
  - mkdir -p {mapa}
  - llvm-profdata merge --output={profdata} *.profraw
  - llvm-profdata show --detailed-summary {profdata} | head -n 30
cleanup:
  - /share/safeer-pgo
sources:
  - type: dir
    path: {vir}
"""


def _zamenjaj(besedilo: str, staro: str, novo: str) -> str:
    if besedilo.count(staro) != 1:
        raise SystemExit("pgo.py: %r ni natanko enkrat" % staro.strip())
    return besedilo.replace(staro, novo)


def modul(nacin: str) -> str:
    besedilo = MODUL.read_text(encoding="utf-8")
    besedilo = _zamenjaj(besedilo, "name: webkitgtk6-safeer\n", "name: webkitgtk6-safeer-pgo-%s\n" % nacin)
    if nacin == "ucenje":
        dodatek = "  - -DENABLE_LLVM_PROFILE_GENERATION=ON\n"
    else:
        dodatek = "  - -DUSE_PGO_PROFILE=ON\n  - -DPGO_PROFILE_PATH=%s\n" % PROFDATA
    besedilo = _zamenjaj(besedilo, LTO, LTO + dodatek)
    # Popravki (type: patch, path: x.patch) so ob modulu; razlicica je v build/pgo, zato absolutne poti.
    return re.sub(r"(?m)^(    path: )(?!/)(\S+)$", lambda m: m.group(1) + str(WEBKIT / m.group(2)), besedilo)


def manifest(nacin: str, profraw: "pathlib.Path | None", izhod: pathlib.Path) -> pathlib.Path:
    izhod.mkdir(parents=True, exist_ok=True)
    (izhod / "webkitgtk6-safeer-pgo.yml").write_text(modul(nacin), encoding="utf-8")
    besedilo = MANIFEST.read_text(encoding="utf-8")
    vrstica = "  - packaging/webkit/webkitgtk6-safeer.yml\n"
    novo = "  - %s\n" % (izhod / "webkitgtk6-safeer-pgo.yml")
    if nacin == "uporaba":
        datoteke = sorted(profraw.glob("*.profraw"))
        if not datoteke:
            raise SystemExit("pgo.py: v %s ni datotek .profraw" % profraw)
        (izhod / "webkitgtk6-safeer-pgo-profil.yml").write_text(
            PROFIL.format(mapa=PROFDATA.rsplit("/", 1)[0], profdata=PROFDATA, vir=profraw.resolve()), encoding="utf-8")
        novo = "  - %s\n" % (izhod / "webkitgtk6-safeer-pgo-profil.yml") + novo
    besedilo = _zamenjaj(besedilo, vrstica, novo)
    # Ostali moduli in izvor programa ostanejo v repozitoriju (absolutne poti, ker je manifest v build/pgo).
    besedilo = re.sub(r"(?m)^(  - )(packaging/\S+\.yml)$", lambda m: m.group(1) + str(KOREN / m.group(2)), besedilo)
    besedilo = _zamenjaj(besedilo, "        path: .\n", "        path: %s\n" % KOREN)
    pot = izhod / MANIFEST.name
    pot.write_text(besedilo, encoding="utf-8")
    return pot


def main(argv) -> int:
    if not argv or argv[0] not in ("ucenje", "uporaba") or (argv[0] == "uporaba") != (len(argv) == 2):
        print(__doc__, file=sys.stderr)
        return 2
    profraw = pathlib.Path(argv[1]) if len(argv) == 2 else None
    print(manifest(argv[0], profraw, KOREN / "build" / "pgo"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
