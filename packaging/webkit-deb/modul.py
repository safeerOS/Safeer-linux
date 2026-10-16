#!/usr/bin/env python3
"""Izvor, popravki in moznosti gradnje iz modulov Flatpak (packaging/webkit, packaging/libsoup) za pakete .deb.

En vir resnice: paketa .deb (packaging/webkit-deb/zgradi.sh) gradita WebKitGTK in libsoup iz istih arhivov (URL in
SHA-256), z istimi popravki in istimi moznostmi CMake/meson kot Flatpak. Ko se spremeni modul Flatpaka, se spremeni
tudi .deb - nicesar ni treba prepisovati na dve mesti.

  python3 packaging/webkit-deb/modul.py packaging/webkit/webkitgtk6-safeer.yml

Izpise JSON: {"ime", "url", "sha256", "popravki": [absolutne poti], "moznosti": [...], "cflags", "cxxflags", "okolje"}.
Poti orodij iz razsiritve Flatpak llvm22 (/usr/lib/sdk/llvm22/bin) zamenja s potmi paketov apt.llvm.org
(/usr/lib/llvm-22/bin) - isti prevajalnik, druga namestitev.
"""
import json
import pathlib
import sys

import yaml

SDK_LLVM = "/usr/lib/sdk/llvm22/bin"
APT_LLVM = "/usr/lib/llvm-22/bin"


def preberi(pot: pathlib.Path) -> dict:
    modul = yaml.safe_load(pot.read_text(encoding="utf-8"))
    arhivi = [v for v in modul.get("sources", []) if v.get("type") == "archive"]
    if len(arhivi) != 1:
        raise SystemExit("modul.py: %s nima natanko enega arhiva" % pot)
    popravki = [str((pot.parent / v["path"]).resolve()) for v in modul["sources"] if v.get("type") == "patch"]
    for p in popravki:
        if not pathlib.Path(p).is_file():
            raise SystemExit("modul.py: popravek %s ne obstaja" % p)
    moznosti = [str(m).replace(SDK_LLVM, APT_LLVM) for m in modul.get("config-opts", [])]
    gradnja = modul.get("build-options", {}) or {}
    return {
        "ime": modul["name"],
        "url": arhivi[0]["url"],
        "sha256": arhivi[0]["sha256"],
        "popravki": popravki,
        "moznosti": moznosti,
        "cflags": gradnja.get("cflags", ""),
        "cxxflags": gradnja.get("cxxflags", ""),
        "okolje": {k: str(v) for k, v in (gradnja.get("env", {}) or {}).items()},
    }


def main(argv) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    print(json.dumps(preberi(pathlib.Path(argv[0]).resolve()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
