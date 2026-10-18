#!/usr/bin/env python3
"""Nas rqbit (motor torrentov Safeer OS) v paketu .deb: uradni vir s pripetim odtisom in nasim popravkom.

Lastnik, 18. 10. 2026: napako v odprti kodi popravimo, popravek takoj vkljucimo v nase pakete (ne cakamo na novo izdajo)
in ga predlagamo skupnosti. Uradni rqbit 9.0.1 se na jedru brez IPv6 (ipv6.disable=1, nekateri vsebniki) ne zazene:
poslusalec TCP, DHT, LSD in odjemalec sledilnikov UDP vezejo [::] in dobijo EAFNOSUPPORT - odjemalec sledilnikov UDP
tudi z --ipv4-only (izmerjeno 18. 10. 2026). Popravek ipv4-fallback-without-ipv6.patch: ce jedro IPv6 nima, rqbit
uporabi samo IPv4 (0.0.0.0); z IPv6 se nic ne spremeni.

Uporaba:
  rqbit_paket.py zgradi CILJ
      Klonira oznako iz rqbit.json, preveri commit in SHA-256 drevesa, uveljavi popravke (SHA-256 iz rqbit.json) in zgradi
      staticen program (musl; cargo --locked preveri kontrolne vsote vseh odvisnosti). V CILJ zapise rqbit, LICENSE,
      OBVESTILO.txt, LICENSES-THIRD-PARTY.txt (licence knjiznic v programu), popravke in gradnja.json. Potrebuje git, rustup, musl-gcc (musl-tools) in omrezje.
      CARGO_TARGET_DIR (neobvezno) - mapa za vmesne datoteke cargo; sicer zacasna mapa, ki se na koncu pobrise.
  rqbit_paket.py preveri MAPA
      Gradnja ustreza pinu, program ima zapisani SHA-256, je staticen in je prava razlicica.
  rqbit_paket.py namesti MAPA KOREN PAKET
      Preveri in namesti v KOREN/usr/lib/PAKET/rqbit/rqbit, obvestila v KOREN/usr/share/doc/PAKET/rqbit.
  rqbit_paket.py dim PROGRAM [--brez-ipv6]
      Preizkus brez interneta: lokalni sledilnik UDP, seme in prenos z motorjem Safeer (core/os_torrent.py) ter tok
      predvajalnika z Range. --brez-ipv6: socket(AF_INET6) vrne EAFNOSUPPORT (seccomp, python3-seccomp), kot na jedru
      z ipv6.disable=1 - tako CI na runnerju z IPv6 preveri prav pot, ki je bila pokvarjena.
  rqbit_paket.py drevo-sha256 MAPA
      SHA-256 drevesa izvorne kode (za rqbit.json ob novi razlicici).

Samo standardna knjiznica Pythona (dim --brez-ipv6 potrebuje se python3-seccomp).
"""
from __future__ import annotations

import errno
import hashlib
import http.client
import json
import os
import platform
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path

MAPA = Path(__file__).resolve().parent
KOREN = MAPA.parent.parent
PIN = MAPA / "rqbit.json"
GRADNJA = "gradnja.json"
OBVESTILO = """rqbit {razlicica} v paketu Safeer / rqbit {razlicica} in the Safeer package
================================================================

rqbit (https://github.com/ikatson/rqbit) je odjemalec BitTorrent avtorja Igorja Katsona, licenca Apache 2.0 (datoteka
LICENSE v tej mapi, celotno besedilo licence v /usr/share/common-licenses/Apache-2.0). Safeer ga uporablja kot motor za
magnet povezave (prenos in predvajanje med prenosom). Licence knjiznic v programu: LICENSES-THIRD-PARTY.txt.

Program je zgrajen iz uradnega vira (oznaka {oznaka}, commit {commit}) z naslednjimi spremembami projekta Safeer
(datoteke v tej mapi, predlagane tudi avtorju):
{seznam}
rqbit (https://github.com/ikatson/rqbit) is a BitTorrent client by Igor Katson, licensed under the Apache License 2.0
(file LICENSE in this folder, full licence text in /usr/share/common-licenses/Apache-2.0). Safeer uses it as the engine
for magnet links (download and playback while downloading). Licences of the libraries in the program:
LICENSES-THIRD-PARTY.txt.

The program is built from the official source (tag {oznaka}, commit {commit}) with the following changes made by the
Safeer project (files in this folder, also proposed upstream):
{seznam}
Gradnja / build: {rustc}, {cilj}, cargo --locked, lastnosti / features: {lastnosti}.
"""
DOKUMENTI = ("LICENSE", "OBVESTILO.txt", "LICENSES-THIRD-PARTY.txt")


def pin() -> dict:
    return json.loads(PIN.read_text(encoding="utf-8"))


def _sha256(pot: Path) -> str:
    h = hashlib.sha256()
    with open(pot, "rb") as f:
        for kos in iter(lambda: f.read(1 << 20), b""):
            h.update(kos)
    return h.hexdigest()


def drevo_sha256(koren: Path) -> str:
    """SHA-256 drevesa izvorne kode, neodvisen od razlicice gita in oblike arhiva.

    Vrstica na datoteko, urejeno po poti (UTF-8): »f <644|755> <sha256 vsebine> <pot>« ali »l <sha256 cilja> <pot>« za
    simbolno povezavo; mapa .git na vrhu se izpusti. Odtis je SHA-256 vseh vrstic."""
    koren = Path(koren)
    vrstice = []
    for mapa, mape, datoteke in os.walk(koren):
        rel_mapa = Path(mapa).relative_to(koren)
        if rel_mapa == Path("."):
            mape[:] = [m for m in mape if m != ".git"]
        for ime in list(mape) + datoteke:
            pot = Path(mapa) / ime
            rel = (rel_mapa / ime).as_posix()
            if pot.is_symlink():
                cilj = os.readlink(pot).encode("utf-8")
                vrstice.append((rel, "l %s %s\n" % (hashlib.sha256(cilj).hexdigest(), rel)))
            elif ime in datoteke:
                x = "755" if os.stat(pot).st_mode & 0o111 else "644"
                vrstice.append((rel, "f %s %s %s\n" % (x, _sha256(pot), rel)))
    h = hashlib.sha256()
    for _, vrstica in sorted(vrstice, key=lambda v: v[0].encode("utf-8")):
        h.update(vrstica.encode("utf-8"))
    return h.hexdigest()


def _napaka(sporocilo: str) -> SystemExit:
    return SystemExit("rqbit_paket: " + sporocilo)


def _git(vir: Path, *argumenti: str) -> str:
    return subprocess.run(["git", "-C", str(vir), *argumenti], check=True, capture_output=True,
                          text=True).stdout.strip()


_LICENCA = re.compile(r"^(licen[cs]e|copying|notice|unlicense|copyright)", re.I)
LICENCE_KNJIZNIC = DOKUMENTI[2]
MUSL_COPYRIGHT = Path("/usr/share/doc/musl/copyright")


def licence_knjiznic(vir: Path, p: dict, okolje: dict) -> str:
    """Besedila licenc vseh knjiznic, ki so v programu (staticno povezan: MIT, BSD ... zahtevajo obvestilo ob vsaki
    kopiji). Nabor iz `cargo tree` za isti cilj in lastnosti kot gradnja, datoteke licenc iz izvora knjiznic; enaka
    besedila samo enkrat."""
    cargo = ["cargo", "+" + p["rust"]]
    drevo = subprocess.run(cargo + ["tree", "--locked", "-e", "normal", "--target", p["cilj"], "-p", "rqbit",
                                    "--no-default-features", "--features", p["lastnosti"], "--prefix", "none",
                                    "--format", "{p}"], cwd=vir, env=okolje, check=True, capture_output=True,
                           text=True).stdout
    v_programu = {(m.group(1), m.group(2)) for m in re.finditer(r"^(\S+) v(\S+)", drevo, re.M)}
    meta = json.loads(subprocess.run(cargo + ["metadata", "--locked", "--format-version", "1", "--filter-platform",
                                              p["cilj"]], cwd=vir, env=okolje, check=True, capture_output=True,
                                     text=True).stdout)
    paketi = sorted((x for x in meta["packages"] if x["source"] and (x["name"], x["version"]) in v_programu),
                    key=lambda x: (x["name"], x["version"]))
    besedila: dict = {}
    seznam = []
    for x in paketi:
        mapa = Path(x["manifest_path"]).parent
        stevilke = []
        for ime in sorted(f for f in os.listdir(mapa) if _LICENCA.match(f) and (mapa / f).is_file()):
            besedilo = (mapa / ime).read_text(encoding="utf-8", errors="replace").strip()
            kljuc = hashlib.sha256(besedilo.encode("utf-8")).hexdigest()
            if kljuc not in besedila:
                besedila[kljuc] = (len(besedila) + 1, "%s %s/%s" % (x["name"], x["version"], ime), besedilo)
            stevilke.append("#%d" % besedila[kljuc][0])
        seznam.append("%s %s - %s - %s" % (x["name"], x["version"], x.get("license") or "?",
                                           ", ".join(stevilke) or "brez datoteke licence v izvoru / no licence file"))
    deli = [
        "Licence knjiznic v programu rqbit / Licences of the libraries in the rqbit program",
        "=" * 80,
        "",
        "Program rqbit je staticno povezan s spodnjimi knjiznicami (crates.io; izvorna koda vsake je na crates.io pod",
        "navedenim imenom in razlicico) ter s standardno knjiznico Rust (MIT OR Apache-2.0), knjiznico C musl (MIT) in",
        "LLVM libunwind (Apache-2.0 WITH LLVM-exception) iz Rust %s za %s." % (p["rust"], p["cilj"]),
        "The rqbit program is statically linked with the libraries below (source of each on crates.io under the given",
        "name and version), the Rust standard library (MIT OR Apache-2.0), the musl C library (MIT) and LLVM libunwind",
        "(Apache-2.0 WITH LLVM-exception) from Rust %s for %s." % (p["rust"], p["cilj"]),
        "",
        "Knjiznice / libraries (%d): ime razlicica - licenca - besedila / name version - licence - texts" % len(seznam),
        "",
        *seznam,
    ]
    for stevilka, izvor, besedilo in besedila.values():
        deli += ["", "-" * 80, "#%d (%s)" % (stevilka, izvor), "-" * 80, besedilo]
    if MUSL_COPYRIGHT.is_file():
        deli += ["", "-" * 80, "musl (%s)" % MUSL_COPYRIGHT, "-" * 80, MUSL_COPYRIGHT.read_text(encoding="utf-8").strip()]
    return "\n".join(deli) + "\n"


def _staticen(program: Path) -> bool:
    glave = subprocess.run(["readelf", "-lW", str(program)], check=True, capture_output=True, text=True).stdout
    dinamicno = subprocess.run(["readelf", "-dW", str(program)], check=True, capture_output=True, text=True).stdout
    return "program interpreter" not in glave and "(NEEDED)" not in dinamicno


def zgradi(cilj: Path) -> None:
    p = pin()
    if not shutil.which("musl-gcc"):
        raise _napaka("ni musl-gcc (paket musl-tools): aws-lc-sys za cilj musl potrebuje prevajalnik C")
    subprocess.run(["rustup", "toolchain", "install", p["rust"], "--profile", "minimal", "--target", p["cilj"],
                    "--no-self-update"], check=True, stdout=sys.stderr)
    with tempfile.TemporaryDirectory(prefix="safeer-rqbit-") as delo:
        vir = Path(delo) / "rqbit"
        subprocess.run(["git", "clone", "--quiet", "--depth", "1", "--no-tags", "--branch", p["oznaka"],
                        "-c", "advice.detachedHead=false", p["repozitorij"], str(vir)], check=True)
        commit = _git(vir, "rev-parse", "HEAD")
        if commit != p["commit"]:
            raise _napaka("oznaka %s kaze na %s, pripet je %s" % (p["oznaka"], commit, p["commit"]))
        drevo = drevo_sha256(vir)
        if drevo != p["drevo_sha256"]:
            raise _napaka("SHA-256 drevesa %s ni pripeti %s" % (drevo, p["drevo_sha256"]))
        for ime, odtis in p["popravki"].items():
            popravek = MAPA / ime
            if _sha256(popravek) != odtis:
                raise _napaka("%s nima pripetega SHA-256 (rqbit.json)" % ime)
            subprocess.run(["git", "-C", str(vir), "apply", "--check", str(popravek)], check=True)
            subprocess.run(["git", "-C", str(vir), "apply", str(popravek)], check=True)
        okolje = dict(os.environ, CARGO_INCREMENTAL="0", CARGO_PROFILE_RELEASE_DEBUG="0")
        tarca = Path(os.environ.get("CARGO_TARGET_DIR") or Path(delo) / "target")
        okolje["CARGO_TARGET_DIR"] = str(tarca)
        subprocess.run(["cargo", "+" + p["rust"], "build", "--locked", "--profile", p["profil"],
                        "--target", p["cilj"], "-p", "rqbit", "--no-default-features", "--features", p["lastnosti"]],
                       cwd=vir, env=okolje, check=True, stdout=sys.stderr)
        zgrajen = tarca / p["cilj"] / p["profil"] / "rqbit"
        rustc = subprocess.run(["rustc", "+" + p["rust"], "--version"], check=True, capture_output=True,
                               text=True).stdout.strip()
        cilj.mkdir(parents=True, exist_ok=True)
        program = cilj / "rqbit"
        shutil.copyfile(zgrajen, program)
        # Brez simbolov (Safeer izpis rqbita zavrze, sledi sklada ne potrebuje): manjsi paket.
        subprocess.run(["strip", "--strip-all", str(program)], check=True)
        os.chmod(program, 0o755)
        shutil.copyfile(vir / "LICENSE", cilj / "LICENSE")
        for ime in p["popravki"]:
            shutil.copyfile(MAPA / ime, cilj / ime)
        seznam = "".join("- %s\n" % ime for ime in p["popravki"])
        (cilj / "OBVESTILO.txt").write_text(OBVESTILO.format(
            razlicica=p["razlicica"], oznaka=p["oznaka"], commit=p["commit"], seznam=seznam, rustc=rustc,
            cilj=p["cilj"], lastnosti=p["lastnosti"]), encoding="utf-8")
        (cilj / LICENCE_KNJIZNIC).write_text(licence_knjiznic(vir, p, okolje), encoding="utf-8")
        zapis = {k: p[k] for k in ("razlicica", "oznaka", "commit", "drevo_sha256", "popravki", "rust", "cilj",
                                   "lastnosti", "profil")}
        zapis.update(rustc=rustc, program_sha256=_sha256(program), velikost=program.stat().st_size,
                     staticen=_staticen(program))
        (cilj / GRADNJA).write_text(json.dumps(zapis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        for ime in [*DOKUMENTI, GRADNJA, *p["popravki"]]:
            os.chmod(cilj / ime, 0o644)
    preveri(cilj)


def preveri(mapa: Path) -> dict:
    """Gradnja v MAPI ustreza pinu (vir, popravki, Rust, cilj), program ima zapisani SHA-256, je staticen in pravi."""
    p = pin()
    try:
        g = json.loads((mapa / GRADNJA).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise _napaka("%s: ni zapisa gradnje (%s)" % (mapa, e))
    for k in ("razlicica", "oznaka", "commit", "drevo_sha256", "popravki", "rust", "cilj", "lastnosti", "profil"):
        if g.get(k) != p[k]:
            raise _napaka("gradnja ima %s=%r, pin %r (stara gradnja?)" % (k, g.get(k), p[k]))
    if not str(g.get("rustc", "")).startswith("rustc %s " % p["rust"]):
        raise _napaka("gradnja z %r, pripet je Rust %s" % (g.get("rustc"), p["rust"]))
    program = mapa / "rqbit"
    if not program.is_file() or program.stat().st_size != g["velikost"] or _sha256(program) != g["program_sha256"]:
        raise _napaka("%s se ne ujema z zapisom gradnje (SHA-256)" % program)
    if not os.access(program, os.X_OK):
        raise _napaka("%s ni izvrsljiv" % program)
    if not g.get("staticen") or not _staticen(program):
        raise _napaka("%s ni staticen (interpreter ali NEEDED)" % program)
    for ime, odtis in p["popravki"].items():
        if not (mapa / ime).is_file() or _sha256(mapa / ime) != odtis:
            raise _napaka("popravek %s manjka ali ni pripeti" % ime)
    for ime in DOKUMENTI:
        if not (mapa / ime).is_file():
            raise _napaka("manjka %s" % ime)
    if sys.platform.startswith("linux") and platform.machine() in ("x86_64", "amd64") and \
            p["cilj"].startswith("x86_64-"):
        izpis = subprocess.run([str(program), "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
        if izpis != "rqbit " + p["razlicica"]:
            raise _napaka("%s --version: %r" % (program, izpis))
    return g


def namesti(mapa: Path, koren: Path, paket: str) -> None:
    preveri(mapa)
    p = pin()
    lib = koren / "usr" / "lib" / paket / "rqbit"
    doc = koren / "usr" / "share" / "doc" / paket / "rqbit"
    lib.mkdir(parents=True, exist_ok=True)
    doc.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(mapa / "rqbit", lib / "rqbit")
    os.chmod(lib / "rqbit", 0o755)
    for ime in [*DOKUMENTI, GRADNJA, *p["popravki"]]:
        shutil.copyfile(mapa / ime, doc / ime)
        os.chmod(doc / ime, 0o644)


# ------------------------------------------------------------------ dim: preizkus brez interneta

def _bencode(x) -> bytes:
    if isinstance(x, int):
        return b"i%de" % x
    if isinstance(x, str):
        x = x.encode("utf-8")
    if isinstance(x, bytes):
        return b"%d:%s" % (len(x), x)
    if isinstance(x, list):
        return b"l" + b"".join(_bencode(v) for v in x) + b"e"
    return b"d" + b"".join(_bencode(k) + _bencode(v) for k, v in sorted(x.items())) + b"e"


class _Sledilnik(threading.Thread):
    """Najmanjsi sledilnik UDP (BEP 15) na 127.0.0.1: vsakemu vrne ostale vire istega torrenta."""

    def __init__(self) -> None:
        super().__init__(name="sledilnik", daemon=True)
        self.vticnica = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.vticnica.bind(("127.0.0.1", 0))
        self.vticnica.settimeout(0.2)
        self.vrata = self.vticnica.getsockname()[1]
        self.viri: dict = {}
        self.najave: list = []
        self.konec = threading.Event()

    def run(self) -> None:
        while not self.konec.is_set():
            try:
                podatki, naslov = self.vticnica.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                return
            if len(podatki) >= 16 and struct.unpack(">QII", podatki[:16])[:2] == (0x41727101980, 0):
                tid = struct.unpack(">I", podatki[12:16])[0]
                self.vticnica.sendto(struct.pack(">IIQ", 0, tid, 0x5AFE5AFE), naslov)
            elif len(podatki) >= 98 and struct.unpack(">I", podatki[8:12])[0] == 1:
                tid = struct.unpack(">I", podatki[12:16])[0]
                info_hash, vrata = podatki[16:36], struct.unpack(">H", podatki[96:98])[0]
                vir = (naslov[0], vrata)
                self.najave.append(vir)
                drugi = [v for v in self.viri.setdefault(info_hash, set()) if v != vir]
                self.viri[info_hash].add(vir)
                odgovor = struct.pack(">IIIII", 1, tid, 5, 0, len(drugi)) + b"".join(
                    socket.inet_aton(ip) + struct.pack(">H", v) for ip, v in drugi)
                self.vticnica.sendto(odgovor, naslov)

    def ustavi(self) -> None:
        self.konec.set()
        self.join(timeout=2)
        self.vticnica.close()


def _brez_ipv6() -> None:
    """Ta proces in vsi njegovi otroci: socket(AF_INET6, ...) vrne EAFNOSUPPORT (kot jedro z ipv6.disable=1)."""
    import seccomp  # python3-seccomp
    f = seccomp.SyscallFilter(defaction=seccomp.ALLOW)
    f.add_rule(seccomp.ERRNO(errno.EAFNOSUPPORT), "socket", seccomp.Arg(0, seccomp.EQ, socket.AF_INET6))
    f.load()


def _ipv6_na_voljo() -> bool:
    try:
        socket.socket(socket.AF_INET6, socket.SOCK_DGRAM).close()
        return True
    except OSError as e:
        if e.errno != errno.EAFNOSUPPORT:
            raise
        return False


def dim(program: Path, brez_ipv6: bool) -> dict:
    if brez_ipv6:
        _brez_ipv6()
        if _ipv6_na_voljo():
            raise _napaka("filter seccomp ni zaprl IPv6")
    sys.path.insert(0, str(KOREN))
    from core import os_torrent as ot

    izid = {"ipv6": _ipv6_na_voljo(), "program": str(program)}
    delo = Path(tempfile.mkdtemp(prefix="safeer-rqbit-dim-"))
    sledilnik = _Sledilnik()
    motorji = []
    try:
        for xdg in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
            os.environ[xdg] = str(delo / xdg.lower())       # stanje DHT rqbita ne gre v uporabnikov ~/.cache
        sledilnik.start()
        seme_mapa, prenos_mapa = delo / "seme", delo / "prenos"
        seme_mapa.mkdir()
        vsebina = os.urandom(6 * 1024 * 1024 + 12345)
        (seme_mapa / "preizkus.mp4").write_bytes(vsebina)
        kos = 256 * 1024
        info = {"name": "preizkus.mp4", "length": len(vsebina), "piece length": kos,
                "pieces": b"".join(hashlib.sha1(vsebina[i:i + kos]).digest() for i in range(0, len(vsebina), kos))}
        torrent = _bencode({"announce": "udp://127.0.0.1:%d/announce" % sledilnik.vrata, "info": info})
        info_hash = hashlib.sha1(_bencode(info)).hexdigest()

        # Seme: motor za naprave (svoj DHT, sosednja vrata), torrent z ze preneseno datoteko, deljenje izrecno vklopljeno.
        seme = ot.Torrenti(str(seme_mapa), str(delo / "seme-stanje"), program=str(program), svoj_dht=True)
        motorji.append(seme)
        t = time.monotonic()
        seme.zazeni()
        izid["zagon_s"] = round(time.monotonic() - t, 3)
        seme.deli_naprej(info_hash, True)
        koda, telo = seme._api("POST", "/torrents?overwrite=true", torrent, cas=60)
        if koda != 200:
            raise _napaka("seme: dodajanje %d %s" % (koda, telo[:200]))

        prenos = ot.Torrenti(str(prenos_mapa), str(delo / "prenos-stanje"), program=str(program))
        motorji.append(prenos)
        prenos.zazeni()
        t = time.monotonic()
        koda, telo = prenos._api("POST", "/torrents?overwrite=true", torrent, cas=60)
        if koda != 200:
            raise _napaka("prenos: dodajanje %d %s" % (koda, telo[:200]))
        tid = int(json.loads(telo)["id"])
        stanje: dict = {}
        while time.monotonic() - t < 120:
            stanje = prenos._json("GET", "/torrents/%d/stats/v1" % tid)
            if stanje.get("finished"):
                break
            time.sleep(0.2)
        else:
            raise _napaka("prenos v 120 s ni koncan: %s, najave sledilniku %s" % (stanje, sledilnik.najave))
        izid["prenos_s"] = round(time.monotonic() - t, 3)
        prenesena = prenos_mapa / "preizkus.mp4"
        if hashlib.sha256(prenesena.read_bytes()).digest() != hashlib.sha256(vsebina).digest():
            raise _napaka("prenesena datoteka se ne ujema z izvirnikom")
        # Tok predvajalnika (Range) iz istega torrenta.
        naslov = urllib.parse.urlsplit(prenos.tok(tid, 0))
        povezava = http.client.HTTPConnection(naslov.hostname, naslov.port, timeout=30)
        povezava.request("GET", naslov.path, headers={"Range": "bytes=1000000-1065535"})
        odgovor = povezava.getresponse()
        del_toka = odgovor.read()
        povezava.close()
        if odgovor.status != 206 or del_toka != vsebina[1000000:1065536]:
            raise _napaka("tok: %d, %d B" % (odgovor.status, len(del_toka)))
        izid["najave"] = sorted({v for v in sledilnik.najave})
        if len(izid["najave"]) < 2:
            raise _napaka("sledilnik UDP ni dobil najav obeh motorjev: %s" % izid["najave"])
        izid["bajtov"] = len(vsebina)
        izid["info_hash"] = info_hash
        return izid
    finally:
        for m in motorji:
            m.ustavi()
        sledilnik.ustavi()
        shutil.rmtree(delo, ignore_errors=True)


def main(argv: list) -> int:
    if len(argv) >= 2 and argv[0] == "zgradi":
        zgradi(Path(argv[1]).resolve())
    elif len(argv) >= 2 and argv[0] == "preveri":
        g = preveri(Path(argv[1]).resolve())
        print("rqbit %s: %s B, sha256 %s, %s" % (g["razlicica"], g["velikost"], g["program_sha256"], g["rustc"]))
    elif len(argv) >= 4 and argv[0] == "namesti":
        namesti(Path(argv[1]).resolve(), Path(argv[2]).resolve(), argv[3])
    elif len(argv) >= 2 and argv[0] == "dim":
        print(json.dumps(dim(Path(argv[1]).resolve(), "--brez-ipv6" in argv[2:]), indent=2))
    elif len(argv) >= 2 and argv[0] == "drevo-sha256":
        print(drevo_sha256(Path(argv[1])))
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
