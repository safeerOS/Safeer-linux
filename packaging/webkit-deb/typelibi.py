#!/usr/bin/env python3
"""Typelibi nasega WebKitGTK in libsoup z absolutno potjo do knjiznic v zasebni predponi (paketi .deb).

  python3 packaging/webkit-deb/typelibi.py PREDPONA

Typelib v atributu shared-library nosi samo soname (npr. libwebkitgtk-6.0.so.4). libgirepository ga odpre z dlopen
brez nase poti in bi vzel sistemsko knjiznico (paket libwebkitgtk-6.0-4) ali nobene. Z absolutno potjo (PREDPONA/lib/...)
Python nalozi prav nase knjiznice ne glede na LD_LIBRARY_PATH; njihove odvisnosti (libsoup, libjavascriptcoregtk) resi
DT_RPATH, ki ga ima knjiznica WebKita. Vsak PREDPONA/share/gir-1.0/*.gir se prepise in prevede z g-ir-compiler v
PREDPONA/lib/girepository-1.0/*.typelib.
"""
import pathlib
import re
import subprocess
import sys

_KNJIZNICA = re.compile(r'shared-library="([^"]+)"')


def absolutno(besedilo: str, lib: str) -> "tuple[str, int]":
    """Vsako soname v shared-library="a,b" zamenja z lib/a,lib/b (absolutne poti ostanejo)."""
    def zamenjaj(m):
        return 'shared-library="%s"' % ",".join(
            k if k.startswith("/") else "%s/%s" % (lib.rstrip("/"), k) for k in m.group(1).split(","))
    return _KNJIZNICA.subn(zamenjaj, besedilo)


def main(argv) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    predpona = pathlib.Path(argv[0])
    gir = predpona / "share" / "gir-1.0"
    cilj = predpona / "lib" / "girepository-1.0"
    cilj.mkdir(parents=True, exist_ok=True)
    giri = sorted(gir.glob("*.gir"))
    if not giri:
        print("typelibi.py: v %s ni datotek .gir" % gir, file=sys.stderr)
        return 1
    for g in giri:
        novo, n = absolutno(g.read_text(encoding="utf-8"), str(predpona / "lib"))
        g.write_text(novo, encoding="utf-8")
        typelib = cilj / (g.stem + ".typelib")
        subprocess.run(["g-ir-compiler", "--includedir=%s" % gir, "--output=%s" % typelib, str(g)], check=True)
        print("typelib:", typelib.name, _KNJIZNICA.findall(novo) if n else "(brez knjiznice)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
