#!/usr/bin/env python3
"""Ali je WebKitGTK, ki ga vgradimo v Flatpak (/app), se najnovejsa stabilna izdaja?

Nas WebKitGTK v /app (packaging/webkit/*.yml) prekrije knjiznico iz runtima org.gnome.Platform - zato varnostni
popravki runtima (WebKitGTK izda varnostne popravke kot nove stabilne izdaje 2.x.y) do nas ne pridejo sami. Ta preizkus
(tedenski tek .github/workflows/webkit-razlicica.yml) postane rdec, ko je na https://webkitgtk.org/releases/ novejsa
stabilna izdaja od pripete; takrat posodobimo url in sha256 v manifestih (pregled 14. 10. 2026).

Stabilne izdaje imajo sodo manjso stevilko (2.54.x); lihe (2.53.x) so razvojne.
Izhod: 0 = pripeto je najnovejse, 1 = zaostajamo, 2 = vira ni bilo mogoce prebrati ali razumeti.
Uporaba: python3 tools/webkit_razlicica.py [--html datoteka]   (--html za preizkus brez omrezja)
"""
import re
import sys
import urllib.request
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
MANIFESTI = sorted((KOREN / "packaging" / "webkit").glob("*.yml"))
VIR = "https://webkitgtk.org/releases/"
_IZDAJA = re.compile(r"webkitgtk-(\d+)\.(\d+)\.(\d+)\.tar\.xz")


def pripete(manifesti=MANIFESTI) -> dict:
    """manifest -> (x, y, z) iz url-ja izvorne kode."""
    izid = {}
    for pot in manifesti:
        m = _IZDAJA.search(Path(pot).read_text(encoding="utf-8"))
        if m:
            izid[Path(pot).name] = tuple(int(x) for x in m.groups())
    return izid


def najnovejsa_stabilna(html: str):
    izdaje = {tuple(int(x) for x in m) for m in _IZDAJA.findall(html)}
    stabilne = [r for r in izdaje if r[1] % 2 == 0]
    return max(stabilne) if stabilne else None


def niz(r) -> str:
    return ".".join(str(x) for x in r)


def main(argv) -> int:
    if len(argv) >= 2 and argv[0] == "--html":
        html = Path(argv[1]).read_text(encoding="utf-8")
    else:
        try:
            with urllib.request.urlopen(VIR, timeout=30) as odg:   # nosec: stalen naslov https
                html = odg.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print("Seznama izdaj WebKitGTK ni bilo mogoce prebrati:", e)
            return 2
    zadnja = najnovejsa_stabilna(html)
    pripeto = pripete()
    if zadnja is None or not pripeto:
        print("Ni podatka o izdajah ali o pripeti razlicici - preveri", VIR, "in packaging/webkit/*.yml")
        return 2
    zaostaja = {ime: r for ime, r in pripeto.items() if r < zadnja}
    for ime, r in sorted(pripeto.items()):
        print("%-28s %s%s" % (ime, niz(r), "  <- zaostaja" if ime in zaostaja else ""))
    print("Najnovejsa stabilna WebKitGTK:", niz(zadnja))
    if zaostaja:
        print("::error::WebKitGTK %s je izsel - posodobi url in sha256 v %s (varnostni popravki runtima nas ne "
              "dosezejo, ker /app prekrije runtime)." % (niz(zadnja), ", ".join(sorted(zaostaja))))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
