#!/usr/bin/env python3
"""PGO (profile-guided optimization) za nas WebKitGTK - razlicici modula in manifestov Flatpak v build/pgo/<ID>/.

WebKitGTK 2.54 (Source/cmake/WebKitCommon.cmake) ima PGO samo s Clangom, v dveh fazah:
  1) -DENABLE_LLVM_PROFILE_GENERATION=ON: knjiznice z -fprofile-generate; pomozni procesi (WebKitWebProcess,
     WebKitNetworkProcess) ob SIGTERM zapisejo profil (AuxiliaryProcessMain.cpp), pot doloci LLVM_PROFILE_FILE.
  2) -DUSE_PGO_PROFILE=ON -DPGO_PROFILE_PATH=<.profdata>: -fprofile-use pri prevodu in povezavi (ThinLTO).
Profil mora biti iz istega izvora, popravkov in prevajalnika; .profraw zato zdruzi llvm-profdata iz iste razsiritve
llvm22 v gradnji flatpak-builderja (modul webkitgtk6-safeer-pgo-profil pred WebKitom). Modul WebKita ima v obeh fazah
isto ime (MODUL_IME): flatpak-builder gradi v /run/build/<ime modula>, imena lokalnih (static) funkcij v profilu pa
vsebujejo pot izvorne datoteke - z razlicnima imenoma se profil teh funkcij ne bi ujemal.

  python3 packaging/webkit/pgo.py ucenje                          -> instrumentiran manifest brskalnika
  python3 packaging/webkit/pgo.py uporaba MAPA_PROFRAW [MANIFEST] -> manifest (privzeto brskalnik) s profilom
  python3 packaging/webkit/pgo.py kljuc [LLVM_RAZLICICA]          -> kljuc profila (izvor, popravki, ucni tek, Clang;
                                                                     brez razlicice iz namescene razsiritve llvm22)
  python3 packaging/webkit/pgo.py okolje                          -> commita SDK in llvm22 (za kljuc predpomnilnika)
  python3 packaging/webkit/pgo.py speedometer MAPA                -> pripeta lokalna kopija Speedometra 3.1
  python3 packaging/webkit/pgo.py trening VRATA                   -> "URL NAJDLJE_MINUT" za pgo_trening.py

Od 15. 10. 2026 (lastnik: "DA") sta Flatpaka Safeer Browser in Safeer OS v vsaki gradnji CI z WebKitom s PGO
(.github/workflows/linux-packages.yml: posli webkit-pgo-profil, webkit-pgo-ucenje, flatpak, flatpak-brskalnik).
Izmerjeno na testnem PC (Speedometer 3.1): sistemski WebKit 8.06, GCC 8.2, Clang+ThinLTO 9.2, Clang+ThinLTO+PGO 10.7.
Lokalna gradnja (packaging/build_flatpak.sh brez SAFEER_FLATPAK_MANIFEST) ostane brez PGO.
"""
import hashlib
import os
import pathlib
import re
import subprocess
import sys

KOREN = pathlib.Path(__file__).resolve().parents[2]
WEBKIT = KOREN / "packaging" / "webkit"
MODUL = WEBKIT / "webkitgtk6-safeer.yml"
TRENING = WEBKIT / "pgo_trening.py"
MANIFEST = KOREN / "io.github.memelandfaner.SafeerBrowser.yml"
PROFDATA = "/app/share/safeer-pgo/webkit.profdata"
# Povzetek profila v paketu (preveri ga CI): stevilo funkcij in poti lokalnih funkcij (/run/build/<ime modula>).
POVZETEK = "/app/share/webkitgtk-safeer/profil.txt"
MODUL_IME = "webkitgtk6-safeer-pgo"
SDK = "org.gnome.Sdk//50"
LLVM_RAZSIRITEV = "org.freedesktop.Sdk.Extension.llvm22//25.08"
LTO = "  - -DLTO_MODE=thin\n"
OPCIJE = {
    "ucenje": ("-DENABLE_LLVM_PROFILE_GENERATION=ON",),
    "uporaba": ("-DUSE_PGO_PROFILE=ON", "-DPGO_PROFILE_PATH=" + PROFDATA),
}
# Ucna obremenitev: pripeta kopija Speedometra 3.1 (brez omrezja), 5 ponovitev, najvec 150 minut.
SPEEDOMETER = ("https://github.com/WebKit/Speedometer.git", "release/3.1", "1386415be8fef2f6b6bbdbe1828872471c5d802a")
TRENING_POIZVEDBA = "?startAutomatically&iterationCount=5"
TRENING_MINUT = 150

PROFIL = """\
# Zdruzi .profraw iz ucnega teka (Speedometer 3.1) z llvm-profdata iste razlicice kot prevajalnik WebKita.
name: webkitgtk6-safeer-pgo-profil
buildsystem: simple
build-options:
  append-path: /usr/lib/sdk/llvm22/bin
  prepend-ld-library-path: /usr/lib/sdk/llvm22/lib
build-commands:
  - ls -l *.profraw
  - mkdir -p {mapa} {mapa_povzetka}
  - llvm-profdata merge --output={profdata} *.profraw
  - |
    {{
      echo "profraw: $(ls *.profraw | wc -l)"
      llvm-profdata show {profdata} | grep -E '^(Instrumentation level|Total functions|Maximum function count)'
      echo "poti lokalnih funkcij:"
      llvm-profdata show --all-functions {profdata} | grep -o '/run/build/[^/;:]*' | sort | uniq -c
    }} > {povzetek}
    cat {povzetek}
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


def _absolutno(besedilo: str, mapa: pathlib.Path) -> str:
    """Relativne poti (path: ... in vkljuceni moduli - ...yml) glede na mapo izvirne datoteke: razlicica je v build/pgo."""
    besedilo = re.sub(r"(?m)^(\s*(?:- )?path: )(?!/)(\S+)$",
                      lambda m: m.group(1) + os.path.normpath(str(mapa / m.group(2))), besedilo)
    return re.sub(r"(?m)^(\s*- )(?!/)(\S+\.ya?ml)$",
                  lambda m: m.group(1) + os.path.normpath(str(mapa / m.group(2))), besedilo)


def popravki() -> list:
    """Datoteke popravkov modula WebKita (type: patch), v vrstnem redu."""
    return [WEBKIT / p for p in re.findall(r"(?m)^    path: (\S+\.patch)$", MODUL.read_text(encoding="utf-8"))]


def modul(nacin: str) -> str:
    besedilo = MODUL.read_text(encoding="utf-8")
    besedilo = _zamenjaj(besedilo, "name: webkitgtk6-safeer\n", "name: %s\n" % MODUL_IME)
    besedilo = _zamenjaj(besedilo, LTO, LTO + "".join("  - %s\n" % o for o in OPCIJE[nacin]))
    return _absolutno(besedilo, WEBKIT)


def kljuc(llvm: str) -> str:
    """Kljuc profila: vse, od cesar je odvisen .profraw - izvor in popravki WebKita (modul), moznosti instrumentacije,
    ime modula (pot izvora), ucni program in obremenitev ter razlicica Clang/LLVM. Ne vsebuje libsoup (gradi se za
    WebKitom, na kodo WebKita ne vpliva), ostalih modulov, kode Safeerja in runtime-a (glave GNOME 50 se lahko
    spremenijo ob posodobitvi runtime-a: tedaj se del profila ne ujema, Clang pa to le opozori)."""
    if not re.fullmatch(r"\d+\.\d+(\.\d+)?", llvm):
        raise SystemExit("pgo.py: razlicica LLVM %r ni oblike 22.1.8" % llvm)
    h = hashlib.sha256()
    for pot in [MODUL] + popravki() + [TRENING]:
        h.update(pot.name.encode() + b"\0" + pot.read_bytes() + b"\0")
    h.update(repr((MODUL_IME, OPCIJE["ucenje"], SPEEDOMETER, TRENING_POIZVEDBA, TRENING_MINUT)).encode())
    return "%s-llvm%s" % (h.hexdigest()[:20], llvm)


def _flatpak_info(*argumenti) -> str:
    return subprocess.run(["flatpak", "info", "--user", *argumenti], check=True, capture_output=True,
                          text=True).stdout.strip()


def llvm_razlicica(mapa: "pathlib.Path | None" = None) -> str:
    """Razlicica LLVM v namesceni razsiritvi llvm22 (LLVMConfig.cmake, sicer ime knjiznice libLLVM.so.X.Y)."""
    mapa = mapa or pathlib.Path(_flatpak_info("--show-location", LLVM_RAZSIRITEV)) / "files"
    for cfg in sorted(mapa.glob("lib*/cmake/llvm/LLVMConfig*.cmake")):
        m = re.search(r'set\(\s*(?:LLVM_)?PACKAGE_VERSION\s+"?(\d+\.\d+\.\d+)"?\s*\)', cfg.read_text(errors="replace"))
        if m:
            return m.group(1)
    for knj in sorted(mapa.glob("lib*/libLLVM.so.*")):
        m = re.fullmatch(r"libLLVM\.so\.(\d+\.\d+(?:\.\d+)?)", knj.name)
        if m:
            return m.group(1)
    raise SystemExit("pgo.py: razlicice LLVM v %s ni mogoce prebrati" % mapa)


def okolje() -> str:
    """Commita runtime-a SDK in razsiritve llvm22: flatpak-builder ju ima v kljucu svojega predpomnilnika, zato ju mora
    imeti tudi kljuc actions/cache (sicer bi ob posodobitvi SDK vsak tek znova gradil WebKit, shranil pa nic)."""
    return "sdk%s-llvm%s" % (_flatpak_info("-c", SDK)[:12], _flatpak_info("-c", LLVM_RAZSIRITEV)[:12])


def manifest(nacin: str, profraw: "pathlib.Path | None", izhod: pathlib.Path,
             vir: pathlib.Path = MANIFEST) -> pathlib.Path:
    izhod.mkdir(parents=True, exist_ok=True)
    (izhod / "webkitgtk6-safeer-pgo.yml").write_text(modul(nacin), encoding="utf-8")
    besedilo = vir.read_text(encoding="utf-8")
    vrstica = "  - packaging/webkit/webkitgtk6-safeer.yml\n"
    novo = "  - %s\n" % (izhod / "webkitgtk6-safeer-pgo.yml")
    if nacin == "uporaba":
        datoteke = sorted(profraw.glob("*.profraw"))
        if not datoteke:
            raise SystemExit("pgo.py: v %s ni datotek .profraw" % profraw)
        (izhod / "webkitgtk6-safeer-pgo-profil.yml").write_text(
            PROFIL.format(mapa=PROFDATA.rsplit("/", 1)[0], profdata=PROFDATA, povzetek=POVZETEK,
                          mapa_povzetka=POVZETEK.rsplit("/", 1)[0], vir=profraw.resolve()), encoding="utf-8")
        novo = "  - %s\n" % (izhod / "webkitgtk6-safeer-pgo-profil.yml") + novo
    besedilo = _zamenjaj(besedilo, vrstica, novo)
    # Ostali moduli, popravki (npr. packaging/zypak) in izvor programa ostanejo v repozitoriju.
    besedilo = _absolutno(besedilo, vir.resolve().parent)
    pot = izhod / vir.name
    pot.write_text(besedilo, encoding="utf-8")
    return pot


def main(argv) -> int:
    ukaz = argv[0] if argv else ""
    if ukaz == "ucenje" and len(argv) == 1:
        print(manifest("ucenje", None, KOREN / "build" / "pgo" / MANIFEST.stem))
    elif ukaz == "uporaba" and len(argv) in (2, 3):
        vir = pathlib.Path(argv[2]).resolve() if len(argv) == 3 else MANIFEST
        print(manifest("uporaba", pathlib.Path(argv[1]), KOREN / "build" / "pgo" / vir.stem, vir))
    elif ukaz == "kljuc" and len(argv) in (1, 2):
        print(kljuc(argv[1] if len(argv) == 2 else llvm_razlicica()))
    elif ukaz == "okolje" and len(argv) == 1:
        print(okolje())
    elif ukaz == "speedometer" and len(argv) == 2:
        url, veja, commit = SPEEDOMETER
        subprocess.run(["git", "clone", "-q", "-b", veja, url, argv[1]], check=True)
        subprocess.run(["git", "-C", argv[1], "checkout", "-q", commit], check=True)
    elif ukaz == "trening" and len(argv) == 2 and argv[1].isdigit():
        print("http://127.0.0.1:%s/%s %d" % (argv[1], TRENING_POIZVEDBA, TRENING_MINUT))
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
