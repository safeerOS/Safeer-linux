#!/usr/bin/env python3
"""Preveri arhiv tar (na standardnem vhodu, ze razsirjen), preden ga root razpakira v / (nadaljuj.sh).

Tedenski pregled 4. 11. 2026 (N5): nadaljuj.sh kot root razpakira arhiv iz predpomnilnika CI v korenski imenik. Clan z
absolutno potjo, z »..« ali zunaj nameravanih map bi prepisal karkoli v sistemu. Dovoljeni so samo clani pod mapami,
podanimi kot argumenti (relativno na /), vrste navadna datoteka, mapa, simbolna in trda povezava; cilj povezave mora
ostati v isti mapi. Izhodna koda 0 = arhiv je v redu, 1 = ni (razlog na stderr).

    zstd -dc ARHIV | preveri_arhiv.py usr/lib/safeer-webkit pot/do/predbolt
"""
import posixpath
import sys
import tarfile


def _cist(ime: str) -> str:
    while ime.startswith("./"):
        ime = ime[2:]
    return ime.rstrip("/")


def _v_mapi(pot: str, mape) -> str:
    """Mapa iz `mape`, v kateri je pot (enaka ali pod njo), sicer ''."""
    for mapa in mape:
        if pot == mapa or pot.startswith(mapa + "/"):
            return mapa
    return ""


def napaka_clana(clan: tarfile.TarInfo, mape) -> str:
    ime = _cist(clan.name)
    if not ime or ime.startswith("/") or ".." in ime.split("/") or "\\" in ime:
        return "nevarna pot: %r" % clan.name
    mapa = _v_mapi(ime, mape)
    if not mapa:
        return "zunaj dovoljenih map: %r" % clan.name
    if not (clan.isreg() or clan.isdir() or clan.issym() or clan.islnk()):
        return "nedovoljena vrsta clana: %r" % clan.name
    if clan.mode & 0o6000:
        # Root razpakira s tar (nadaljuj.sh): datoteka setuid/setgid v /usr/lib/safeer-webkit iz zastrupljenega
        # predpomnilnika CI bi dala lokalni root. Nasa gradnja takih datotek nima (CodeRabbit, 4. 11. 2026).
        return "bit setuid/setgid: %r" % clan.name
    if clan.issym() or clan.islnk():
        cilj = clan.linkname
        if not cilj or "\\" in cilj:
            return "nevaren cilj povezave: %r -> %r" % (clan.name, cilj)
        if clan.issym():
            cilj = posixpath.normpath(cilj.lstrip("/") if cilj.startswith("/")
                                      else posixpath.join(posixpath.dirname(ime), cilj))
        else:
            cilj = posixpath.normpath(_cist(cilj))
        if cilj.startswith("../") or cilj == ".." or _v_mapi(cilj, [mapa]) != mapa:
            return "povezava ven iz %s: %r -> %r" % (mapa, clan.name, clan.linkname)
    return ""


def preveri(tok, mape) -> str:
    mape = [_cist(m.lstrip("/")) for m in mape]
    if not mape or any(not m or ".." in m.split("/") for m in mape):
        return "neveljavne dovoljene mape"
    n = 0
    with tarfile.open(fileobj=tok, mode="r|") as arhiv:
        for clan in arhiv:
            n += 1
            razlog = napaka_clana(clan, mape)
            if razlog:
                return razlog
    return "" if n else "prazen arhiv"


def main(argv) -> int:
    if len(argv) < 2:
        print("Uporaba: zstd -dc ARHIV | preveri_arhiv.py MAPA [MAPA ...]", file=sys.stderr)
        return 2
    try:
        razlog = preveri(sys.stdin.buffer, argv[1:])
    except (tarfile.TarError, OSError, EOFError) as e:
        razlog = "arhiv ni berljiv: %s" % e
    if razlog:
        print("preveri_arhiv.py: " + razlog, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
