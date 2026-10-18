#!/usr/bin/env python3
"""Node.js 22 LTS v zasebno mapo paketa safeer-os: packaging/node_vendor.py <cilj> [mapa_predpomnilnika].

Lastnik (nacin »deb«): Safeer OS prinese svoj Node.js v paketu .deb, ne prenasa ga ob prvi rabi in ne zahteva sistemskega.
Razlicica in SHA-256 sta pripeta tu; arhiv z nodejs.org se pred uporabo preveri (napacna vrednost ustavi gradnjo).
SHA-256 je iz SHASUMS256.txt izdaje, katerega podpis je bil preverjen s kljucem izdajatelja Node.js
(5BE8A3F6C8A5C01D106C0AD820B1A390B168D356, seznam v README nodejs/node) - 18. 10. 2026.

V <cilj> (/usr/lib/safeer-os/node) gre samo, kar program potrebuje: bin/node (brez simbolov za razhroscevanje, -17 MiB),
LICENSE (licenca Node.js z licencami vseh vgrajenih knjiznic: V8, OpenSSL, ICU, libuv ...) in RAZLICICA. Brez npm,
npx in corepack ter brez povezave v /usr/bin: sistemski node (paket nodejs) ostane nedotaknjen, nasi programi ga
najdejo prek core/node_izvajalnik.py.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAZLICICA = "22.23.3"
SHA256 = "df450af89261115ef9f9e3830c3eeb2cc9213b63c720b1af623cb5dcbe2e02de"
IME = "node-v%s-linux-x64" % RAZLICICA
URL = "https://nodejs.org/dist/v%s/%s.tar.xz" % (RAZLICICA, IME)
#: Clani arhiva, ki jih vzamemo (vse drugo - npm, glave, dokumentacija - ostane zunaj).
CLANI = {IME + "/bin/node": ("bin/node", 0o755), IME + "/LICENSE": ("LICENSE", 0o644)}


def _sha(pot: str) -> str:
    h = hashlib.sha256()
    with open(pot, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def prenesi(mapa: str, url: str = URL, sha: str = SHA256) -> str:
    """Arhiv v predpomnilniku, preverjen s pripeto SHA-256 (ob neujemanju se izbrise in gradnja konca)."""
    os.makedirs(mapa, exist_ok=True)
    pot = os.path.join(mapa, url.rsplit("/", 1)[1])
    if os.path.isfile(pot) and _sha(pot) == sha:
        return pot
    zacasna = pot + ".part"
    with urllib.request.urlopen(url, timeout=300) as o, open(zacasna, "wb") as f:   # nosec B310 - pripet https
        shutil.copyfileobj(o, f, 1 << 20)
    dobljeno = _sha(zacasna)
    if dobljeno != sha:
        os.remove(zacasna)
        raise SystemExit("Node.js: napacna SHA-256 arhiva %s (%s, pricakovana %s)" % (url, dobljeno, sha))
    os.replace(zacasna, pot)
    return pot


def razpakiraj(arhiv: str, cilj: str, sha: str = SHA256) -> None:
    """Samo clani CLANI, kot navadne datoteke (brez poti iz arhiva - nic ne more pisati mimo cilja)."""
    if _sha(arhiv) != sha:
        raise SystemExit("Node.js: arhiv %s ni pripeti (SHA-256)" % arhiv)
    najdeni = set()
    with tarfile.open(arhiv, "r:xz") as t:
        for clan in t:
            if clan.name not in CLANI:
                continue
            if not clan.isreg():
                raise SystemExit("Node.js: %s v arhivu ni navadna datoteka" % clan.name)
            ime, nacin = CLANI[clan.name]
            pot = os.path.join(cilj, ime)
            os.makedirs(os.path.dirname(pot), exist_ok=True)
            with t.extractfile(clan) as vir, open(pot, "wb") as f:
                shutil.copyfileobj(vir, f, 1 << 20)
            os.chmod(pot, nacin)
            najdeni.add(clan.name)
    manjka = set(CLANI) - najdeni
    if manjka:
        raise SystemExit("Node.js: v arhivu manjka " + ", ".join(sorted(manjka)))
    with open(os.path.join(cilj, "RAZLICICA"), "w", encoding="ascii") as f:
        f.write(RAZLICICA + "\n")
    os.chmod(os.path.join(cilj, "RAZLICICA"), 0o644)


def oskubi(cilj: str) -> None:
    """Odstrani simbole za razhroscevanje (119 -> 102 MiB, izmerjeno 18. 10. 2026); brez orodja strip ostane, kot je."""
    strip = shutil.which("strip")
    if strip:
        subprocess.run([strip, "--strip-unneeded", os.path.join(cilj, "bin", "node")], check=True)


def preveri(cilj: str) -> None:
    """Node se zazene in pove pripeto razlicico (tudi v gradnji: arhiv za drugo arhitekturo bi tu padel)."""
    izid = subprocess.run([os.path.join(cilj, "bin", "node"), "--version"], capture_output=True, text=True,
                          timeout=60, env={"PATH": "/usr/bin:/bin"})
    if izid.returncode != 0 or izid.stdout.strip() != "v" + RAZLICICA:
        raise SystemExit("Node.js se ne zazene: %r %r" % (izid.stdout, izid.stderr))


def main() -> None:
    cilj = sys.argv[1]
    mapa = sys.argv[2] if len(sys.argv) > 2 else os.path.join(KOREN, "build", "cache", "node")
    shutil.rmtree(cilj, ignore_errors=True)
    razpakiraj(prenesi(mapa), cilj)
    oskubi(cilj)
    preveri(cilj)
    print("Node.js %s -> %s" % (RAZLICICA, cilj))


if __name__ == "__main__":
    main()
