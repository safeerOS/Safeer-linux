"""Deljene mape Safeer Controla za televizor (Safeer OS) in druge naprave v Safeer Linku.

Uporabnik na racunalniku izbere mape, ki jih sme videti televizor (privzeto nobene). Seznam map
gre prek Safeer Linka (ukaz daljinca `files.list`), same datoteke pa neposredno z racunalnika po
HTTPS: Control ima majhen streznik datotek s samopodpisanim potrdilom, katerega odtis dobi
naprava skupaj z naslovom in enkratnim zetonom v odgovoru na `files.list`. Streznik se zazene
sele ob prvi zahtevi in poslusa na nakljucnih vratih; brez zetona ne vrne nicesar.

Naprava nikoli ne vidi poti na racunalniku: mape in datoteke imajo navidezne oznake
`share:<st. mape>:<relativna pot>` (zamisel iz PoC-ja Safeer OS). Pot se vedno razresi znotraj
izbrane mape (simbolne povezave navzven ne pridejo skozi), skrite datoteke se ne kazejo.
"""

from __future__ import annotations

import collections
import hashlib
import hmac
import io
import http.client
import http.server
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple

from core import budnost, link_obramba, link_tls, link_urejanje, os_deskriptorji

NAJVEC_VNOSOV = 500
NAJVEC_TELESA = 64 * 1024
#: Kaj naprava sme narediti z datoteko racunalnika (POST /d/<id>, telo JSON {"op": ...}).
UKAZI = ("delete", "rename", "move", "rotate")
VELIKOST_KOSA = 256 * 1024
#: Med posiljanjem datoteke ali toka tako pogosto preverimo, ali zeton in dovoljenje naprave se veljata: odvzem dostopa
#: (umik iz ozjega kroga) konca tudi prenos, ki ze tece - ne sele naslednjo zahtevo (sedmi pregled, 25. 10. 2026).
PREVERI_MED_POSILJANJEM_S = 1.0
#: Zeton za prenos velja 12 ur od zadnje rabe; nato mora naprava znova po seznam.
ZETON_VELJA_S = 12 * 3600.0
#: Na NAPRAVO najvec toliko zivih zetonov (izpade njen najdlje nerabljen). Skupne meje ni vec (lastnik, 18. 10. 2026:
#: prej 64 skupaj - v vecjem krogu je naprava, ki je pravkar brskala, izgubila zeton zaradi drugih in dobila 401).
NAJVEC_ZETONOV_NA_NAPRAVO = 8
#: Zgornja meja zivljenja zetona, tudi ce ga naprava ves cas rabi.
NAJDLJE_S = 7 * 24 * 3600.0


def _umaknjena_iz_kroga(id_naprave: str) -> bool:
    try:
        from core import link_krog
        return link_krog.je_umaknjen(id_naprave)
    except Exception:
        return False


def _sme_naprava(id_naprave: str, zmoznost: str) -> bool:
    """Ali je napravi na tem racunalniku odprta zmoznost (core/link_dostop); napaka pomeni ne."""
    try:
        from core import link_dostop
        return link_dostop.sme(id_naprave, zmoznost)
    except Exception:  # noqa: BLE001
        return False


def _v_ozjem_krogu(id_naprave: str) -> bool:
    """Ali naprava sme do domace mape (link_dostop.sme_domaco_mapo): ozji krog z izrecno privolitvijo za domaco mapo -
    zapis d+z iz prejsnje razlicice je nima, dokler je uporabnik ne dovoli (vodja 25. 10. 2026). Napaka pomeni ne."""
    try:
        from core import link_dostop
        return link_dostop.sme_domaco_mapo(id_naprave)
    except Exception:  # noqa: BLE001
        return False


def _v_domacem_drevesu(pot: str) -> bool:
    """Ali je razresena absolutna pot domaca mapa, mapa domacih map (/home - tam so tudi domace mape drugih
    uporabnikov) ali kaj pod njima; tudi mapa nad njima razen korena (njen seznam vodi do domacih map)."""
    dom = os.path.realpath(os.path.expanduser("~"))
    nad = os.path.dirname(dom)
    meja = dom if os.path.dirname(nad) == nad else nad        # /root (tik pod korenom): samo domaca mapa
    if pot == meja or pot.startswith(meja.rstrip(os.sep) + os.sep):
        return True
    return os.path.dirname(pot) != pot and meja.startswith(pot.rstrip(os.sep) + os.sep)


def _je_dom(oznaka) -> bool:
    """Oznaka, ki jo vidi samo ozji krog: domaca mapa (dom:) in del vsega diska (disk:) z domacimi mapami
    (_v_domacem_drevesu). Pregled 11 (V8) je ozjemu krogu zaprl ves disk; pregled 17 (M3): televizor brez ozjega kroga
    je s tem izgubil zunanje diske in USB, nastavitev »ves disk« zanj pa ni vec delala. Zunanji diski in druge particije
    (/media, /mnt) ostanejo vsaki napravi z dovoljenjem datotek, domace mape samo ozjemu krogu."""
    if not isinstance(oznaka, str):
        return False
    if oznaka.startswith("dom:"):
        return True
    if not oznaka.startswith("disk:"):
        return False
    try:
        return _v_domacem_drevesu(os.path.realpath(oznaka[len("disk:"):] or os.sep))
    except (OSError, ValueError):
        return True             # poti ni mogoce razresiti: samo ozjemu krogu


def _jedro_naprave(id_naprave: str) -> str:
    """Kljuc shrambe izrecnih dovoljenj (link_dostop.kljuc_shrambe): jedro naprave; oznaka, pod katero je v krogu
    drug kljuc, dobi kljuc, ki ni enak nobenemu jedru - dovoljenje prave naprave zanjo ne velja in obratno."""
    try:
        from core import link_dostop
        return link_dostop.kljuc_shrambe(id_naprave)
    except Exception:  # noqa: BLE001
        return "brez-jedra:" + str(id_naprave or "")


#: Zmoznost, ki jo mora imeti naprava za datoteke deljenih map (prenos, slicice, urejanje).
ZMOZNOST_DATOTEKE = "d"
#: Zmoznost predvajalnika (core/link_dostop.PREDVAJALNIK): tok torrenta (magnet.stream) in sprotna pretvorba
#: (video.stream) - tudi vsaka zahteva toka jo preveri, da odvzem velja takoj, ne sele ob izteku zetona (12 h).
ZMOZNOST_PREDVAJALNIK = "v"
#: Izrecno poslane datoteke (uporabnik tega racunalnika jih je poslal napravi) brez stevilske meje: prej 512 - mapa z
#: vec datotekami ali vec naprav je izrinila dovoljenja prvih. Zapis nastane samo z dejanjem uporabnika tega
#: racunalnika in izpade po NAJDLJE_S.


def _zeton_zivi(izdan: float, rabljen: float, zdaj: float) -> bool:
    return zdaj - rabljen < ZETON_VELJA_S and zdaj - izdan < NAJDLJE_S
TLS_MAPA = os.path.join((os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")), "safeer-control", "tls")

# Kaj televizor zna predvajati ali pokazati; drugo se kaze kot navadna datoteka.
VRSTE = {
    "video": {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".ts", ".m2ts", ".mpg", ".mpeg", ".3gp"},
    "audio": {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".wma"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"},
}


def vrsta_datoteke(ime: str) -> str:
    k = os.path.splitext(ime)[1].lower()
    for vrsta, koncnice in VRSTE.items():
        if k in koncnice:
            return vrsta
    return "file"


def _skrita(pot: str) -> bool:
    """Ali pot vodi skozi skrito mapo ali do skrite datoteke (`.ssh`, `.gnupg`, `.mozilla` ...).

    Seznam jih ne kaze; tudi ce naprava ime ugane, jih ne damo: tam so kljuci, gesla in piskotki."""
    return any(del_.startswith(".") for del_ in pot.replace(os.sep, "/").split("/") if del_)


#: Sistemska drevesa (jedro, naprave, procesi, nastavitve sistema, skrbnikova mapa): v njih ni nicesar za uporabnika, so
#: pa okolja procesov z zetoni (/proc/<pid>/environ), vticnice in nastavitve. Ne dajemo jih nobeni napravi - ne pri
#: »vsem disku« ne v deljeni mapi (tudi ce uporabnik deli /). Zunanji pregled kode 8. 10. 2026: seznam korena jih je
#: skril, oznaka disk:/proc/self/environ pa je veljala.
SISTEMSKA_DREVESA = frozenset({"proc", "sys", "dev", "run", "etc", "root", "lost+found"})


def _sistemska(pot: str) -> bool:
    """Ali je razresena absolutna pot v sistemskem drevesu ([SISTEMSKA_DREVESA]); koren / sam ni."""
    deli = [d for d in str(pot).replace(os.sep, "/").split("/") if d]
    return bool(deli) and deli[0] in SISTEMSKA_DREVESA


#: Pri »vsem disku« (oznake disk:) se /var: posta uporabnika (/var/mail), dnevniki, podatki storitev - v izbrani deljeni
#: mapi ostane, ker jo je uporabnik izbral sam (sedmi pregled, naloga 6, 25. 10. 2026). Predpomnilnik Kerberos v /tmp
#: (krb5cc_<uid>) je skrivnost po imenu (_skrivnost); cel /tmp ni zaprt - tam so tudi prenosi in mape programov.
SISTEMSKA_DREVESA_DISKA = frozenset({"var"})


def _sistemska_disk(pot: str) -> bool:
    deli = [d for d in str(pot).replace(os.sep, "/").split("/") if d]
    return _sistemska(pot) or (bool(deli) and deli[0] in SISTEMSKA_DREVESA_DISKA)


#: Windows skrite datoteke ne oznaci s piko, ampak z atributom (AppData s piskotki in gesli brskalnikov, ProgramData,
#: $Recycle.Bin, pagefile.sys). Na Linuxu stat teh atributov nima - tam se nic ne preverja in ni dodatnega klica.
_IMA_ATRIBUTE = hasattr(os.stat_result, "st_file_attributes")
_SKRITO_ALI_SISTEMSKO = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0x2) | getattr(stat, "FILE_ATTRIBUTE_SYSTEM", 0x4)


def _atributi(pot: str) -> int:
    try:
        return int(getattr(os.stat(pot, follow_symlinks=False), "st_file_attributes", 0) or 0)
    except (OSError, ValueError):
        return 0


def _skrita_windows(pot: str, koren: Optional[str] = None) -> bool:
    """Windows: ali ima pot ali katera nadrejena mapa (do deljene mape `koren`, brez nje) atribut Skrito ali
    Sistemsko. Koren diska (C:\\ ima oba atributa) ne steje; mapo, ki jo je uporabnik izrecno delil, deli naprej."""
    if not _IMA_ATRIBUTE:
        return False
    pot = os.path.abspath(pot)
    meja = os.path.normcase(os.path.abspath(koren)) if koren else None
    while True:
        oce = os.path.dirname(pot)
        if oce == pot or (meja is not None and os.path.normcase(pot) == meja):
            return False
        if _atributi(pot) & _SKRITO_ALI_SISTEMSKO:
            return True
        pot = oce


#: Zacetek datoteke, ki je program: ELF, Windows PE (MZ), skripta (#!). Pri imenu brez znane koncnice privzeti program
#: namizja vrsto ugane po vsebini (gio: MZ -> application/x-ms-dos-executable -> Wine) in program zazene.
_GLAVE_PROGRAMOV = (b"\x7fELF", b"MZ", b"#!")
#: Zaganjalnik namizja (.desktop) po vsebini, tudi z BOM ali praznimi vrsticami na zacetku.
_GLAVA_ZAGANJALNIKA = b"[Desktop Entry]"


def _koncnica(ime: str) -> str:
    return os.path.splitext(str(ime or "").strip().lower().rstrip(". "))[1]


def je_nevarno_ime(ime: str) -> bool:
    """Program, skripta, zaganjalnik ali namestitveni paket po imenu (.desktop, .exe, .sh, .jar, .AppImage, .py ...).
    En vir s prilogami Sporocil in prenosi Spleta (core/predogled_datotek.NEVARNE_KONCNICE)."""
    from core import predogled_datotek
    return predogled_datotek.je_nevarna(os.path.basename(str(ime or "")))


def nevarna_za_odpiranje(pot: str) -> bool:
    """Ali `files.open` te datoteke NE sme odpreti s privzetim programom: naprava z dostopom do datotek bi sicer s
    preimenovanjem ali poslano datoteko zagnala program na tem racunalniku (pregled 19. 10. 2026).

    Ne odpremo: nevarnega imena, vsebine programa (ELF, MZ, #!, [Desktop Entry]) in datoteke z izvrsljivim bitom, ki
    nima znane vrste. Izvrsljiv bit sam ni dovolj za zavrnitev: na diskih NTFS/exFAT/FAT (udisks) ga ima VSAKA
    datoteka, pa bi daljinec ne odprl nobenega videa z zunanjega diska - znano vrsto (video.mp4) privzeti program
    izbere po koncnici in je ne izvede. Mapa se odpre v upravitelju datotek."""
    try:
        st = os.stat(pot)
    except (OSError, ValueError):
        return True
    if stat.S_ISDIR(st.st_mode):
        return False
    if not stat.S_ISREG(st.st_mode) or je_nevarno_ime(pot):
        return True
    try:
        with open(pot, "rb") as f:
            glava = f.read(64)
    except OSError:
        return True
    if glava.startswith(_GLAVE_PROGRAMOV) or glava.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(_GLAVA_ZAGANJALNIKA):
        return True
    return bool(st.st_mode & 0o111) and not mimetypes.guess_type(os.path.basename(pot))[0]


def _realna(pot: str) -> Optional[str]:
    """os.path.realpath brez izjeme: pot, ki je ni mogoce razresiti (npr. /proc/1/root brez pravic), ne velja."""
    try:
        return os.path.realpath(pot)
    except (OSError, ValueError):
        return None


#: Datoteke s skrivnostmi, ki jih domaca mapa in ves disk ne dajata napravam (zasebni kljuci SSH, potrdila s kljucem,
#: zbirke gesel) - tudi, ce niso v skriti mapi (koordinator 25. 10. 2026: ozji krog dobi domaco mapo BREZ skrivnosti).
#: Sedmi pregled (naloga 6, 25. 10. 2026): tudi kopije in drugace poimenovani kljuci (id_rsa.bak, github_rsa), zbirke
#: gesel in piskotkov brskalnikov z znanimi imeni (Login Data, Cookies, logins.json, key4.db), izvozi gesel in vsebina
#: (glej _vsebina_skrivnost) - seznam imen sam ne zadostuje.
_SKRIVNOSTI_IMENA = frozenset(("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "id_ecdsa_sk", "id_ed25519_sk",
                               "wallet.dat", "credentials", "credentials.json", "client_secret.json", "deploy_key",
                               "netrc", "_netrc", "pgpass", "git-credentials", "login data", "login data for account",
                               "key3.db", "key4.db", "logins.json", "logins-backup.json", "signons.sqlite",
                               "cookies.sqlite", "cert9.db", "accesskeys.csv", "credentials.csv", "krb5.keytab",
                               "secrets.json", "secrets.yaml", "secrets.yml"))
#: Imena profila brskalnika, ki so tudi obicajne besede (mapa receptov »Cookies«): skrivnost samo po vsebini (SQLite,
#: os_crypt) - pregled 11, N8.
_IMENA_PROFILA = frozenset(("cookies", "web data", "local state"))
#: Spremljajoce datoteke SQLite profila (Login Data-journal, cookies.sqlite-wal): iste skrivnosti kot glavna (N9).
_PRIPONE_PROFILA = ("-journal", "-wal", "-shm")
#: .key (tudi predstavitev Keynote) in .asc (tudi javni kljuc ali podpis) nista vec skrivnost po koncnici - odloci
#: vsebina (N8); .pem ostane po koncnici (potrdilo brez kljuca skrito po pomoti ni skoda).
_SKRIVNOSTI_KONCNICE = frozenset((".pem", ".p12", ".pfx", ".kdbx", ".kdb", ".jks", ".keystore", ".ppk",
                                  ".gpg", ".pgp", ".ovpn", ".kbx", ".keychain", ".keychain-db", ".opvault",
                                  ".1pif", ".psafe3", ".keytab", ".p8", ".pkcs8", ".pkcs12", ".jwk", ".tfstate",
                                  ".tfvars", ".env"))
#: Kljuc SSH in kopija (id_rsa, id_rsa.bak, github_rsa, deploy_ed25519~); ne dokumenti (vaje_dsa.pdf, id_dsa_porocilo.pdf
#: - pregled 11, N8). Drugace poimenovane kljuce brez koncnice (id_ed25519_delo) najde vsebina.
_KLJUC_SSH = re.compile(r"^(?:id_(?:rsa|dsa|ecdsa|ed25519)(?:_sk)?|[\w.-]+_(?:rsa|dsa|ecdsa|ed25519)(?:_sk)?)"
                        r"(?:\.(?:bak|old|orig|save|copy|key|pem|priv))?~?$")
#: Izvozi gesel (Chrome Passwords.csv, bitwarden_export_*.json, gesla.txt, Gesla.docx): ime + vrsta besedila ali tabele.
_IZVOZ_GESEL = re.compile(r"password|passwort|mot.de.passe|contrase|geslo|gesla|bitwarden|lastpass|1password|keepass|"
                          r"dashlane|nordpass|enpass")
_KONCNICE_IZVOZA = frozenset((".csv", ".json", ".txt", ".xml", ".xlsx", ".xls", ".ods", ".tsv", ".docx", ".doc",
                              ".odt", ".pdf"))
#: Zacetek datoteke s skrivnostjo, ne glede na ime: PuTTY, KeePass, OpenSSH (surov), Java KeyStore (FEEDFEED).
_GLAVE_SKRIVNOSTI = (b"PuTTY-User-Key-File", b"\x03\xd9\xa2\x9a", b"openssh-key-v1", b"\xfe\xed\xfe\xed")
#: Koliko vsebine beremo: kljuc je lahko za dolgo verigo potrdil (N9) - pri datotekah potrdil in besedila vec.
_GLAVA_B = 4096
_GLAVA_KLJUCEV_B = 256 * 1024
_KONCNICE_KLJUCEV = frozenset((".key", ".asc", ".crt", ".cer", ".der", ".txt", ".conf", ".cfg", ".yaml", ".yml", ""))
#: Seznam mape vsebine ne bere pri datotekah teh vrst in vecjih od NAJVEC_ZA_SEZNAM_B (tisoc fotografij = tisoc branj,
#: FUSE/omrezni disk, prebujanje USB - pregled 11, N5); prenos, slicico in odprtje pa preveri razresi pri vsaki datoteki.
_VARNE_KONCNICE = frozenset((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".avif", ".tif", ".tiff",
                             ".raw", ".cr2", ".nef", ".dng", ".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".ts",
                             ".m2ts", ".mpg", ".mpeg", ".3gp", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".oga",
                             ".opus", ".wav", ".wma", ".svg", ".epub", ".iso"))
NAJVEC_ZA_SEZNAM_B = 64 * 1024
#: Glave spremljajocih datotek SQLite: WAL (oba vrstna reda bajtov) in dnevnik (journal).
_GLAVE_SQLITE_SPREMLJAJOCE = (b"\x37\x7f\x06\x82", b"\x37\x7f\x06\x83", b"\xd9\xd5\x05\xf9\x20\xa1\x63\xd7")
#: Koncnice, pri katerih je zasebni kljuc lahko binaren (DER) - pregled 17, M6: .key ni vec skrivnost po koncnici.
_KONCNICE_DER = frozenset((".key", ".der", ""))
#: PBES2 in PKCS#12 PBE: sifriran zasebni kljuc PKCS#8 (EncryptedPrivateKeyInfo).
_OID_SIFRIRAN_KLJUC = (b"\x2a\x86\x48\x86\xf7\x0d\x01\x05\x0d", b"\x2a\x86\x48\x86\xf7\x0d\x01\x0c\x01")


def _der_zasebni(glava: bytes) -> bool:
    """Zasebni kljuc DER: PKCS#1, PKCS#8 in SEC1 so SEQUENCE, ki se zacne z INTEGER 0 ali 1; sifriran PKCS#8 ima na
    zacetku OID PBES2/PKCS#12. Potrdilo DER se zacne s SEQUENCE (tbsCertificate), zato ni skrivnost."""
    if len(glava) < 8 or glava[0] != 0x30:
        return False
    if glava[1] < 0x80:
        zacetek = 2
    elif 0x81 <= glava[1] <= 0x84:
        zacetek = 2 + (glava[1] & 0x7F)
    else:
        return False
    if glava[zacetek:zacetek + 3] in (b"\x02\x01\x00", b"\x02\x01\x01"):
        return True
    return any(oid in glava[:48] for oid in _OID_SIFRIRAN_KLJUC)


_vsebina_spomin: "collections.OrderedDict[tuple, bool]" = collections.OrderedDict()
_vsebina_kljuc = threading.Lock()
_NAJVEC_SPOMINA = 8192


def _ime_skrivnosti(ime: str) -> bool:
    """Skrivnost po imenu datoteke (ne mape): kljuc, zbirka gesel, izvoz gesel, Kerberos."""
    ime = ime.lower()
    for pripona in _PRIPONE_PROFILA:
        if ime.endswith(pripona):
            ime = ime[:-len(pripona)]
            break
    koncnica = os.path.splitext(ime)[1]
    if ime in _SKRIVNOSTI_IMENA or koncnica in _SKRIVNOSTI_KONCNICE:
        return True
    if not ime.endswith(".pub") and _KLJUC_SSH.match(ime):
        return True
    if koncnica in _KONCNICE_IZVOZA and _IZVOZ_GESEL.search(ime):
        return True
    return ime.startswith("krb5cc")     # predpomnilnik vstopnic Kerberos (/tmp/krb5cc_<uid>)


def _vsebina_skrivnost(pot: str, hitro: bool = False) -> bool:
    """Ali je datoteka po vsebini skrivnost: zasebni kljuc (PEM, OpenSSH, PuTTY, PGP, kubeconfig), KeePass, JKS, kljuci
    AWS, profil brskalnika (SQLite, os_crypt). Odpre se brez sledenja povezavi in brez cakanja (cev FIFO, N10), vrsta se
    preveri na odprti datoteki. Napaka branja razen »ni« in »ni pravic« pomeni »ne vem« = skrivnost (N9). `hitro`
    (seznam mape): brez branja pri varnih vrstah in vecjih datotekah (N5). Izid je v spominu po (naprava, inode, cas,
    velikost)."""
    ime = os.path.basename(pot).lower()
    koncnica = os.path.splitext(ime)[1]
    # Cookies-journal, Web Data-wal: profil po imenu brez pripone, kot v _ime_skrivnosti (pregled 17, M6).
    osnova = next((ime[:-len(p)] for p in _PRIPONE_PROFILA if ime.endswith(p)), ime)
    profil = osnova in _IMENA_PROFILA
    spremljajoca = profil and osnova != ime
    try:
        st = os.stat(pot)
    except (FileNotFoundError, PermissionError, NotADirectoryError):
        return False
    except (OSError, ValueError):
        return True
    if not stat.S_ISREG(st.st_mode):
        return False
    if hitro and not profil and (koncnica in _VARNE_KONCNICE or st.st_size > NAJVEC_ZA_SEZNAM_B):
        return False
    kljuc = (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size)
    with _vsebina_kljuc:
        znano = _vsebina_spomin.get(kljuc)
    if znano is not None:
        return znano
    koliko = _GLAVA_KLJUCEV_B if koncnica in _KONCNICE_KLJUCEV else _GLAVA_B
    zastavice = (os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_BINARY", 0))
    try:
        rocaj = os.open(pot, zastavice)
        try:
            st_odprte = os.fstat(rocaj)
            if not stat.S_ISREG(st_odprte.st_mode):
                return False
            glava = os.read(rocaj, koliko)
        finally:
            os.close(rocaj)
    except (FileNotFoundError, PermissionError):
        return False
    except (OSError, ValueError):
        return True
    nizka = glava.lower()
    izid = (glava.startswith(_GLAVE_SKRIVNOSTI) or b"PRIVATE KEY-----" in glava or b"PGP PRIVATE KEY BLOCK" in glava
            or b"aws_secret_access_key" in nizka or b"client-key-data:" in glava
            or (profil and (glava.startswith(b"SQLite format 3\x00") or b'"os_crypt"' in glava))
            or (spremljajoca and (glava.startswith(_GLAVE_SQLITE_SPREMLJAJOCE)
                                  or os.path.isfile(pot[:len(pot) - (len(ime) - len(osnova))])))
            or (koncnica in _KONCNICE_DER and _der_zasebni(glava)))
    # Izid v spomin pod odtisom ODPRTE datoteke (zamenjava med stat in open ne da tujega izida) in ne za datoteko,
    # ki se je pravkar spremenila, ali brez stalne stevilke (FAT/exFAT, FUSE: cas na 2 s) - pregled 17, M8.
    kljuc = (st_odprte.st_dev, st_odprte.st_ino, st_odprte.st_mtime_ns, st_odprte.st_size)
    if st_odprte.st_ino == 0 or time.time() - st_odprte.st_mtime < 2.0:
        return izid
    with _vsebina_kljuc:
        _vsebina_spomin[kljuc] = izid
        while len(_vsebina_spomin) > _NAJVEC_SPOMINA:
            _vsebina_spomin.popitem(last=False)
    return izid


def _skrivnost(pot: str, hitro: bool = False) -> bool:
    """Datoteka s skrivnostjo po imenu in - kadar je `pot` absolutna pot - po vsebini (_vsebina_skrivnost). Mape niso
    skrivnost po imenu (pregled 11, N8: mapa »projekt_rsa« je izginila, njene datoteke pa so ostale dosegljive); v njih
    se preveri vsaka datoteka posebej. `hitro`: za seznam mape (glej _vsebina_skrivnost)."""
    pot = str(pot or "")
    if os.path.isabs(pot) and os.path.isdir(pot):
        return False
    if _ime_skrivnosti(os.path.basename(pot)):
        return True
    return os.path.isabs(pot) and _vsebina_skrivnost(pot, hitro)


#: Mape s profili programov brez pike v imenu (gesla, piskotki): ~/snap/<program>/... - Chromium iz snapa hrani Login
#: Data in Cookies v ~/snap/chromium/common/chromium/Default (sedmi pregled, naloga 6, 25. 10. 2026).
_ZASEBNE_MAPE_DOMA = frozenset(("snap",))
#: Windows (disk NTFS na Linuxu in Windows sam): profili programov, kos, zacasne mape namestitve - ne glede na atribut
#: Skrito, ki ga na Linuxu ne vidimo. Registri uporabnika (NTUSER.DAT) in sistema (Windows/System32/config: SAM).
_ZASEBNE_WINDOWS = frozenset(("appdata", "programdata", "$recycle.bin", "system volume information", "config.msi",
                              "$windows.~bt", "$windows.~ws", "$sysreset"))
_ZASEBNA_IMENA_WINDOWS = ("ntuser.dat", "usrclass.dat")
_SISTEMSKE_DATOTEKE_WINDOWS = frozenset(("pagefile.sys", "hiberfil.sys", "swapfile.sys"))


def _zasebna(pot: str) -> bool:
    """Ali absolutna (razresena) pot vodi skozi mapo s profili programov (~/snap) ali zasebni del Windows."""
    deli = [d.lower() for d in str(pot or "").replace("\\", "/").replace(os.sep, "/").split("/") if d]
    if any(d in _ZASEBNE_WINDOWS for d in deli):
        return True
    if any(deli[i:i + 3] == ["windows", "system32", "config"] for i in range(len(deli))):
        return True
    if deli and (deli[-1] in _SISTEMSKE_DATOTEKE_WINDOWS or deli[-1].startswith(_ZASEBNA_IMENA_WINDOWS)):
        return True
    dom = os.path.realpath(os.path.expanduser("~"))
    if pot != dom and str(pot).startswith(dom + os.sep):
        prvi = os.path.relpath(pot, dom).split(os.sep)[0]
        return prvi in _ZASEBNE_MAPE_DOMA
    return False


#: Ime domace mape v seznamu za naprave: nevtralno, ne ime mape (to je navadno uporabnisko ime; sedmi pregled, naloga
#: 6, 25. 10. 2026). Jezik je jezik vmesnika tega racunalnika (DeljeneMape.jezik).
IME_DOMA = {"sl": "Domača mapa", "en": "Home", "de": "Persönlicher Ordner", "es": "Carpeta personal",
            "fr": "Dossier personnel", "it": "Cartella home"}


def ime_doma(jezik: Optional[str]) -> str:
    return IME_DOMA.get(str(jezik or "en")[:2].lower(), IME_DOMA["en"])


class DeljeneMape:
    """Izbrane mape (absolutne poti) in navidezne oznake.

    Poleg izbranih map zna - **samo ce uporabnik to izrecno vklopi** - pokazati tudi cel
    datotecni sistem tega racunalnika (oznake `disk:<absolutna pot>`). Privzeto je izklopljeno:
    televizor brez te izbire vidi natanko tiste mape, ki mu jih je uporabnik dal.
    """

    #: Mape, ki na korenu niso za uporabnika (jedro, naprave, nastavitve sistema) in jih ne kazemo ne dajemo.
    SISTEMSKE = SISTEMSKA_DREVESA

    def __init__(self, poti: Optional[List[str]] = None, ves_disk: bool = False, dom: bool = False) -> None:
        self.poti: List[str] = []
        self.ves_disk = bool(ves_disk)
        #: Domaca mapa za ozji krog (oznake `dom:<rel>`): ena privolitev v Linku (lastnik 25. 10. 2026 10:49) da
        #: napravi v ozjem krogu tudi uporabnikove mape - brez skritih map (.ssh, .gnupg, .config, profili brskalnikov,
        #: zbirka kljucev v .local) in brez datotek s skrivnostmi (_skrivnost) ter sistemskih map. Seznam in prenos
        #: dobi samo naprava z zmoznostjo datotek (link_dostop, ozji krog) - preveri se ob vsaki zahtevi.
        self.dom = bool(dom)
        #: Jezik vmesnika tega racunalnika (ime domace mape v seznamu); nastavi ga Control.
        self.jezik: Optional[str] = None
        self.nastavi(poti or [])

    @staticmethod
    def _domaca() -> str:
        return os.path.realpath(os.path.expanduser("~"))

    def nastavi(self, poti: List[str]) -> None:
        cista: List[str] = []
        for p in poti:
            p = os.path.realpath(os.path.expanduser(str(p)))
            if os.path.isdir(p) and p not in cista:
                cista.append(p)
        self.poti = cista

    def koren(self) -> List[dict]:
        vnosi = [{"id": f"share:{i}:", "name": os.path.basename(p) or p, "type": "folder"}
                 for i, p in enumerate(self.poti)]
        if self.ves_disk:
            dom = os.path.realpath(os.path.expanduser("~"))
            vnosi.append({"id": "disk:" + dom, "name": ime_doma(self.jezik), "type": "folder"})
            vnosi.append({"id": "disk:/", "name": "/", "type": "folder"})
        elif self.dom:
            vnosi.append({"id": "dom:", "name": ime_doma(self.jezik), "type": "folder"})
        return vnosi

    def razresi(self, oznaka: str) -> Optional[Tuple[int, str]]:
        """`share:<i>:<rel>` -> (i, absolutna pot) ali None, ce oznaka ni veljavna ali kaze ven iz mape.

        `disk:<absolutna pot>` -> (-1, pot), a samo kadar je brskanje po celem racunalniku
        vklopljeno; sicer oznaka ne pomeni nicesar.
        """
        oznaka = str(oznaka or "")
        if oznaka.startswith("disk:"):
            if not self.ves_disk:
                return None
            pot = _realna(oznaka[len("disk:"):] or "/")
            if (pot is None or _skrita(pot) or _sistemska_disk(pot) or _skrita_windows(pot) or _skrivnost(pot)
                    or _zasebna(pot)):
                return None
            return (-1, pot) if os.path.exists(pot) else None
        if oznaka.startswith("dom:"):
            if not self.dom:
                return None
            koren = self._domaca()
            rel = oznaka[len("dom:"):].replace("\\", "/").lstrip("/")
            pot = _realna(os.path.join(koren, rel)) if rel else koren
            if pot is None or (pot != koren and not pot.startswith(koren + os.sep)):
                return None         # .. ali simbolna povezava ven iz domace mape
            if pot != koren and (_skrita(os.path.relpath(pot, koren)) or _skrita_windows(pot, koren) or _skrivnost(pot)
                                 or _zasebna(pot)):
                return None
            if _sistemska(pot):
                return None
            return (-2, pot) if os.path.exists(pot) else None
        deli = str(oznaka or "").split(":", 2)
        if len(deli) != 3 or deli[0] != "share":
            return None
        try:
            i = int(deli[1])
            if i < 0 or deli[1] != str(i):      # samo 0, 1, 2 …: »-1« ali »01« bi izbrala drugo mapo kot oznaka_poti
                return None
            koren = self.poti[i]
        except (ValueError, IndexError):
            return None
        rel = deli[2].replace("\\", "/").lstrip("/")
        pot = _realna(os.path.join(koren, rel)) if rel else koren
        if pot is None:
            return None
        if pot != koren and not pot.startswith(koren + os.sep):
            return None
        if pot != koren and (_skrita(os.path.relpath(pot, koren)) or _skrita_windows(pot, koren)):
            return None
        # Tudi v izbrani deljeni mapi ne damo skrivnosti in profilov programov (enako kot domaca mapa; sedmi pregled,
        # naloga 6) - razen ce je uporabnik delil prav tako mapo (koren sam).
        if pot != koren and (_skrivnost(pot) or (_zasebna(pot) and not _zasebna(koren))):
            return None
        if _sistemska(pot):
            return None
        return (i, pot) if os.path.exists(pot) else None

    def oznaka_poti(self, pot: str) -> str:
        """Obratno od `razresi`: absolutna pot -> `share:<i>:<rel>` (ali `disk:<pot>`, ce je ves disk vklopljen)."""
        pot = os.path.realpath(pot)
        for i, koren in enumerate(self.poti):
            if pot == koren:
                return f"share:{i}:"
            if pot.startswith(koren + os.sep):
                return f"share:{i}:" + os.path.relpath(pot, koren).replace(os.sep, "/")
        if self.ves_disk:
            return "disk:" + pot
        dom = self._domaca()
        if self.dom and (pot == dom or pot.startswith(dom + os.sep)):
            return "dom:" + ("" if pot == dom else os.path.relpath(pot, dom).replace(os.sep, "/"))
        return ""

    def podnapisi(self, oznaka_videa: str) -> List[dict]:
        """Podnapisi ob videu (ista mapa ali podmapa Subs), vsak s svojo oznako znotraj deljene mape."""
        from core import podnapisi as pn
        r = self.razresi(oznaka_videa)
        if r is None or not os.path.isfile(r[1]):
            return []
        izid = []
        for pot in pn.podnapisi_mape(r[1]):
            oz = self.oznaka_poti(pot)
            if oz and self.razresi(oz) is not None:
                izid.append(pn.opis(r[1], pot, oz))
        return izid

    def dodaj_podnapise(self, vnosi: List[dict]) -> List[dict]:
        """Videom v seznamu pripne `subtitles` (starejše naprave polje preprosto prezrejo)."""
        for v in vnosi:
            if v.get("type") == "video":
                try:
                    p = self.podnapisi(v["id"])
                except OSError:
                    p = []
                if p:
                    v["subtitles"] = p
        return vnosi

    def seznam(self, oznaka: str) -> Optional[List[dict]]:
        if oznaka in ("", "root"):
            return self.koren()
        r = self.razresi(oznaka)
        if r is None:
            return None
        i, pot = r
        if not os.path.isdir(pot):
            return None
        if i == -2:
            return self._seznam_doma(pot)
        if i < 0:
            return self._seznam_diska(pot)
        koren = self.poti[i]
        try:
            imena = sorted(os.listdir(pot), key=lambda s: s.lower())
        except OSError:
            return None
        vnosi: List[dict] = []
        zasebni_koren = _zasebna(koren)
        for ime in imena:
            if ime.startswith("."):
                continue
            cela = os.path.join(pot, ime)
            if _skrita_windows(cela, pot):
                continue                  # Windows: atribut Skrito/Sistemsko (razresi je tudi ne da)
            try:
                mapa = os.path.isdir(cela)
                if not mapa and not os.path.isfile(cela):
                    continue
                realna = os.path.realpath(cela)
                if _sistemska(realna):
                    continue  # /proc, /etc ... (deljen koren ali povezava tja)
                if (not mapa and _skrivnost(realna, hitro=True)) or (_zasebna(realna) and not zasebni_koren):
                    continue  # razresi je tudi ne da
                rel = os.path.relpath(realna, koren).replace(os.sep, "/")
                if rel.startswith(".."):
                    continue  # simbolna povezava ven iz deljene mape
                v = {"id": f"share:{i}:{rel}", "name": ime, "type": "folder" if mapa else vrsta_datoteke(ime),
                     "modified": int(os.path.getmtime(cela))}
                if not mapa:
                    v["size"] = os.path.getsize(cela)
                    v["mime"] = mimetypes.guess_type(ime)[0] or "application/octet-stream"
                vnosi.append(v)
            except OSError:
                continue
        # Mape najprej, potem datoteke; najvec NAJVEC_VNOSOV.
        vnosi.sort(key=lambda v: (v["type"] != "folder", v["name"].lower()))
        return vnosi[:NAJVEC_VNOSOV]

    def _seznam_doma(self, pot: str) -> Optional[List[dict]]:
        """Vsebina mape v domaci mapi (oznake `dom:`): brez skritih, brez skrivnosti, brez povezav ven."""
        koren = self._domaca()
        try:
            imena = sorted(os.listdir(pot), key=lambda s: s.lower())
        except OSError:
            return None
        vnosi: List[dict] = []
        for ime in imena:
            if ime.startswith("."):
                continue
            cela = os.path.join(pot, ime)
            if _skrita_windows(cela, pot):
                continue
            try:
                mapa = os.path.isdir(cela)
                if not mapa and not os.path.isfile(cela):
                    continue
                realna = os.path.realpath(cela)
                if realna != koren and not realna.startswith(koren + os.sep):
                    continue          # povezava ven iz domace mape
                rel = os.path.relpath(realna, koren).replace(os.sep, "/")
                if _skrita(rel) or _sistemska(realna) or _zasebna(realna) or (not mapa and _skrivnost(realna, hitro=True)):
                    continue
                v = {"id": "dom:" + rel, "name": ime, "type": "folder" if mapa else vrsta_datoteke(ime),
                     "modified": int(os.path.getmtime(cela))}
                if not mapa:
                    v["size"] = os.path.getsize(cela)
                    v["mime"] = mimetypes.guess_type(ime)[0] or "application/octet-stream"
                vnosi.append(v)
            except OSError:
                continue
        vnosi.sort(key=lambda v: (v["type"] != "folder", v["name"].lower()))
        return vnosi[:NAJVEC_VNOSOV]

    def _seznam_diska(self, pot: str) -> Optional[List[dict]]:
        """Vsebina mape kjerkoli na racunalniku (oznake `disk:`). Skrite datoteke ostanejo skrite,
        na korenu pa izpustimo mape jedra in naprav - tam za uporabnika ni nicesar."""
        try:
            imena = sorted(os.listdir(pot), key=lambda s: s.lower())
        except OSError:
            return None
        na_korenu = os.path.realpath(pot) == os.sep
        vnosi: List[dict] = []
        for ime in imena:
            if ime.startswith("."):
                continue
            if na_korenu and (ime in self.SISTEMSKE or ime in SISTEMSKA_DREVESA_DISKA):
                continue
            cela = os.path.join(pot, ime)
            if _skrita_windows(cela, pot):
                continue
            try:
                mapa = os.path.isdir(cela)
                if not mapa and not os.path.isfile(cela):
                    continue
                realna = os.path.realpath(cela)
                if (_skrita(realna) or _sistemska_disk(realna) or _zasebna(realna)
                        or (not mapa and _skrivnost(realna, hitro=True))):
                    continue  # povezava v skrito mapo ali sistemsko drevo, skrivnost: oznaka ne bi veljala
                v = {"id": "disk:" + realna, "name": ime,
                     "type": "folder" if mapa else vrsta_datoteke(ime), "modified": int(os.path.getmtime(cela))}
                if not mapa:
                    v["size"] = os.path.getsize(cela)
                    v["mime"] = mimetypes.guess_type(ime)[0] or "application/octet-stream"
                vnosi.append(v)
            except OSError:
                continue
        vnosi.sort(key=lambda v: (v["type"] != "folder", v["name"].lower()))
        return vnosi[:NAJVEC_VNOSOV]


# ------------------------------------------------------------------ TLS

def zagotovi_potrdilo(mapa: str = TLS_MAPA) -> Tuple[str, str, str]:
    """Samopodpisano potrdilo Controla (kljuc, potrdilo, odtis SHA-256 DER). Ustvari ga ob prvi rabi (core.link_kripto)."""
    os.makedirs(mapa, exist_ok=True)
    try:
        os.chmod(mapa, 0o700)
    except OSError:
        pass
    kljuc, potrdilo = os.path.join(mapa, "kljuc.pem"), os.path.join(mapa, "potrdilo.pem")
    if not (os.path.isfile(kljuc) and os.path.isfile(potrdilo)):
        ime = socket.gethostname().split(".")[0] or "safeer-control"
        from core import link_kripto
        link_kripto.ustvari_kljuc_in_potrdilo(kljuc, potrdilo, ime)
        try:
            os.chmod(kljuc, 0o600)
        except OSError:
            pass
    with open(potrdilo, "rb") as d:
        der = ssl.PEM_cert_to_DER_cert(d.read().decode("ascii"))
    return kljuc, potrdilo, hashlib.sha256(der).hexdigest()


# ------------------------------------------------------------------ streznik

class _Obravnava(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "SafeerControl"
    sys_version = ""

    def log_message(self, oblika, *argumenti):  # noqa: D401 - tiho
        return

    def _vir(self) -> str:
        return str(self.client_address[0]) if self.client_address else ""

    def handle_one_request(self):  # noqa: N802
        # Naslednja zahteva iste povezave (keep-alive): rok za glave tece znova (prva je prijavljena ob sprejemu).
        cuvaj = getattr(self.server, "cuvaj", None)
        if cuvaj is not None:
            cuvaj.zacni(self.connection, self._vir())
        try:
            super().handle_one_request()
        finally:
            if cuvaj is not None:
                cuvaj.koncaj(self.connection)

    def parse_request(self):  # noqa: N802
        try:
            uspeh = super().parse_request()           # prebere vrstico zahteve in vse glave
        finally:
            cuvaj = getattr(self.server, "cuvaj", None)
            if cuvaj is not None:
                cuvaj.koncaj(self.connection)
        if uspeh:
            # Veljaven zeton: vir je naprava kroga - njene povezave obramba ne steje kot poplavo (link_obramba.zaupaj).
            obramba = getattr(self.server, "obramba", None)
            streznik = getattr(self.server, "streznik", None)
            if obramba is not None and streznik is not None and streznik.naprava_zetona(self._zeton()):
                obramba.zaupaj(self._vir())
        return uspeh

    def _zeton(self) -> Optional[str]:
        # Samo glava: zeton v naslovu (?t=) bi ostal v dnevnikih, zgodovini in glavi Referer.
        z = self.headers.get("X-Safeer-Token")
        return z.strip() if z else None

    def do_HEAD(self):  # noqa: N802
        self._datoteka(samo_glava=True)

    def do_GET(self):  # noqa: N802
        self._datoteka(samo_glava=False)

    def do_POST(self):  # noqa: N802
        """Urejanje datoteke z naprave: `{"op": "delete"|"rename"|"move"|"rotate", ...}` z istim zetonom kot prenos."""
        streznik: StreznikDatotek = self.server.streznik  # type: ignore[attr-defined]
        u = urllib.parse.urlparse(self.path)
        try:
            dolzina = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            dolzina = -1
        if u.path.startswith("/d/") and streznik.zeton_velja(self._zeton()) and (dolzina < 0 or dolzina > NAJVEC_TELESA):
            # Preveliko telo: odgovor mora priti do naprave, zato preberemo in zavrzemo, kar se posilja.
            self._napaka(413, "predolgo telo")
            self._zavrzi_telo(dolzina)
            return
        if u.path.startswith("/popravek/"):
            sprejmi_popravek(self, streznik, urllib.parse.unquote(u.path[len("/popravek/"):]))
            return
        uredi_pot(self, streznik, u.path)

    def _zavrzi_telo(self, dolzina: int, najvec: int = 4 * NAJVEC_TELESA, rok_s: float = 1.0) -> None:
        """Po zavrnitvi prevelikega telesa prebere in zavrze, kar odjemalec se posilja - najvec `najvec` bajtov in
        `rok_s` sekund. Brez tega zaprtje povezave med posiljanjem odjemalcu unici odgovor (RST): namesto »413«
        vidi prekinjeno povezavo."""
        ostane = min(max(int(dolzina), 0), najvec)
        konec = time.monotonic() + rok_s
        try:
            while ostane > 0 and time.monotonic() < konec:
                self.connection.settimeout(max(0.05, konec - time.monotonic()))
                kos = self.rfile.read1(min(ostane, 16384)) if hasattr(self.rfile, "read1") else self.rfile.read(min(ostane, 16384))
                if not kos:
                    break
                ostane -= len(kos)
        except (OSError, ValueError):
            pass

    def _napaka(self, koda: int, besedilo: str) -> None:
        telo = json.dumps({"napaka": besedilo}).encode("utf-8")
        self.send_response(koda)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(telo)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(telo)

    def _datoteka(self, samo_glava: bool) -> None:
        streznik: StreznikDatotek = self.server.streznik  # type: ignore[attr-defined]
        postrezi_pot(self, streznik, urllib.parse.urlparse(self.path).path, samo_glava)


def _napaka_http(obravnava, koda: int, besedilo: str) -> None:
    telo = json.dumps({"napaka": besedilo}).encode("utf-8")
    obravnava.send_response(koda)
    obravnava.send_header("Content-Type", "application/json")
    obravnava.send_header("Content-Length", str(len(telo)))
    obravnava.send_header("Connection", "close")
    obravnava.end_headers()
    if getattr(obravnava, "command", "") != "HEAD":
        obravnava.wfile.write(telo)


def postrezi_datoteko(obravnava, streznik: "StreznikDatotek", oznaka: str, samo_glava: bool) -> None:
    """Datoteka deljene mape z zetonom v glavi in podporo za `Range` (previjanje v predvajalniku).

    Isto za lastni streznik datotek (/d/<id>) in za Hub (/cast/d/<id>), prek katerega gre tok tudi
    po Global Linku: rele prinese samo povezavo do vrat Huba."""
    z = obravnava.headers.get("X-Safeer-Token")
    if not streznik.zeton_velja(z.strip() if z else None, zmoznost=ZMOZNOST_DATOTEKE, oznaka=oznaka):
        _napaka_http(obravnava, 401, "manjka ali napacen zeton")
        return
    r = streznik.mape.razresi(oznaka)
    if r is None or not os.path.isfile(r[1]):
        _napaka_http(obravnava, 404, "datoteke ni")
        return
    zeton = z.strip() if z else None
    _poslji_datoteko(obravnava, r[1], samo_glava,
                     se_velja=lambda: streznik.zeton_velja(zeton, zmoznost=ZMOZNOST_DATOTEKE, oznaka=oznaka))


class _Straza:
    """Med posiljanjem: `se_velja()` najvec enkrat na PREVERI_MED_POSILJANJEM_S (zeton in dovoljenje naprave)."""

    def __init__(self, se_velja) -> None:
        self._se_velja = se_velja
        self._naslednja = time.monotonic() + PREVERI_MED_POSILJANJEM_S

    def velja(self) -> bool:
        if self._se_velja is None or time.monotonic() < self._naslednja:
            return True
        self._naslednja = time.monotonic() + PREVERI_MED_POSILJANJEM_S
        try:
            return bool(self._se_velja())
        except Exception:  # noqa: BLE001 - »ne vem« ni »da«
            return False


def _poslji_datoteko(obravnava, pot: str, samo_glava: bool, se_velja=None) -> None:
    """Datoteka z diska s podporo za `Range` (zeton je ze preverjen). `se_velja()`: ali naprava datoteko se sme dobiti
    (preverba med posiljanjem, glej _Straza); ko ne vec, se posiljanje prekine in povezava zapre."""
    velikost = os.path.getsize(pot)
    vrsta = mimetypes.guess_type(pot)[0] or "application/octet-stream"
    zacetek, konec = 0, velikost - 1
    obseg = obravnava.headers.get("Range")
    delni = False
    if obseg and obseg.startswith("bytes="):
        try:
            a, b = obseg[6:].split(",", 1)[0].split("-", 1)
            if a == "" and b:
                zacetek = max(0, velikost - int(b))
            else:
                zacetek = int(a)
                if b:
                    konec = min(velikost - 1, int(b))
            delni = True
        except ValueError:
            delni = False
        if delni and (zacetek > konec or zacetek >= velikost):
            obravnava.send_response(416)
            obravnava.send_header("Content-Range", f"bytes */{velikost}")
            obravnava.send_header("Content-Length", "0")
            obravnava.end_headers()
            return
    dolzina = konec - zacetek + 1
    obravnava.send_response(206 if delni else 200)
    obravnava.send_header("Content-Type", vrsta)
    obravnava.send_header("Accept-Ranges", "bytes")
    obravnava.send_header("Content-Length", str(dolzina))
    if delni:
        obravnava.send_header("Content-Range", f"bytes {zacetek}-{konec}/{velikost}")
    obravnava.send_header("Cache-Control", "private, max-age=0")
    obravnava.end_headers()
    if samo_glava:
        return
    straza = _Straza(se_velja)
    try:
        with open(pot, "rb") as d:
            d.seek(zacetek)
            ostane = dolzina
            while ostane > 0:
                if not straza.velja():
                    print("[SafeerDatoteke] prenos prekinjen: naprava nima vec dostopa", flush=True)
                    obravnava.close_connection = True
                    break
                kos = d.read(min(VELIKOST_KOSA, ostane))
                if not kos:
                    break
                obravnava.wfile.write(kos)
                ostane -= len(kos)
                budnost.dotik()      # naprava bere datoteko: racunalnik medtem ne zaspi sam
    except (BrokenPipeError, ConnectionResetError, ssl.SSLError, socket.timeout):
        # Predvajalnik na napravi med predvajanjem zapira povezave sredi obsega (nov Range): ni napaka,
        # prej je vsaka taka pustila sled v dnevniku (SSLEOFError).
        pass


# ------------------------------------------------------------------ slicice
#: Slicica za mrezni pogled na napravah: daljsa stranica v tockah (dovolj za ploscico na televizorju, da je ni treba
#: povecevati), kakovost JPEG in koliko slicic drzimo v pomnilniku.
SLICICA_ROB = 512
SLICICA_KAKOVOST = 85
NAJVEC_SLICIC = 300
#: Najvec hkratnih slicic iz videa (ffmpeg): mapa s sto videi ne sme zasesti vseh jeder.
_SLICICE_VIDEA = threading.BoundedSemaphore(2)
#: Najvec hkratnih slicic slik (Pillow): slika se pred pomanjsanjem razsiri v pomnilnik (sirina x visina x 3-4 B), zato
#: vzporedne zahteve brez meje izcrpajo pomnilnik procesa (pregled 19. 10. 2026). Na mesto zahteva caka najvec
#: CAKAJ_NA_SLICICO_S, nato slicice ni (404, naprava pokaze ikono).
_SLICICE_SLIK = threading.BoundedSemaphore(2)
CAKAJ_NA_SLICICO_S = 30.0
#: Najvec pik, ki jih slicica dekodira (po pomanjsanju JPEG z draft): 50 MP je ~200 MB RGBA. Pillow sam zavrne sele
#: nad ~179 MP, globalne meje Image.MAX_IMAGE_PIXELS pa ne spreminjamo - Pillow uporablja ves proces Safeer OS.
NAJVEC_PIK_SLICICE = 50_000_000
#: Za slike brez pomanjsanega dekodiranja (PNG, WebP, GIF ...) nizja meja: dekodirajo se v polni velikosti (sedmi pregled,
#: naloga 6: 50 MP RGBA je ~200 MB na zahtevo).
NAJVEC_PIK_SLICICE_BREZ_DRAFT = 24_000_000
#: Formati, ki jih Pillow za slicico sploh poskusi odpreti - po VSEBINI, ne po koncnici. Brez EPS/PS (Ghostscript kot
#: podproces: slika.jpg z vsebino %!PS bi ga zagnala - CVE-2023-36664, CVE-2024-29510) in brez redkih, manj pregledanih
#: dekodirnikov (FLI, PCX, SGI, TGA ...). HEIF/AVIF samo, ce je vticnik namescen (sicer ime ne pomeni nicesar).
FORMATI_SLICIC = ("JPEG", "PNG", "WEBP", "GIF", "BMP", "HEIF", "AVIF")
_slicice: "collections.OrderedDict[tuple, bytes]" = collections.OrderedDict()
_slicice_kljuc = threading.Lock()


def _slicica_slike(pot: str, rob: int) -> Optional[bytes]:
    try:
        from PIL import Image, ImageOps
    except Exception:  # noqa: BLE001 - brez Pillow slicic slik ni; naprava si pomaga sama
        return None
    if not _SLICICE_SLIK.acquire(timeout=CAKAJ_NA_SLICICO_S):
        return None
    try:
        Image.init()
        # Samo formati, ki so v tem Pillow res registrirani (neznano ime bi pri neprepoznani datoteki vrglo KeyError).
        with Image.open(pot, formats=[f for f in FORMATI_SLICIC if f in Image.OPEN]) as im:
            try:
                im.draft("RGB", (rob * 2, rob * 2))      # JPEG se dekodira ze pomanjsan
            except Exception:  # noqa: BLE001
                pass
            sirina, visina = im.size
            meja = NAJVEC_PIK_SLICICE if im.format == "JPEG" else NAJVEC_PIK_SLICICE_BREZ_DRAFT
            if sirina * visina > meja:
                return None                              # prevelika za slicico: brez dekodiranja
            # Najprej pomanjsamo, sele nato obrnemo po EXIF: obracanje polne slike bi naredilo se eno polno kopijo.
            im.thumbnail((rob, rob))
            im = ImageOps.exif_transpose(im)             # pokoncna fotografija ostane pokoncna
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            izhod = io.BytesIO()
            im.save(izhod, "JPEG", quality=SLICICA_KAKOVOST)
            return izhod.getvalue()
    except Exception:  # noqa: BLE001 - pokvarjena ali nepodprta slika (tudi DecompressionBombError): slicice ni
        return None
    finally:
        _SLICICE_SLIK.release()


def _slicica_videa(pot: str, rob: int) -> Optional[bytes]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    # Na mesto caka najvec CAKAJ_NA_SLICICO_S (kot slike): mapa s sto videi ne nabira niti brez konca.
    if not _SLICICE_VIDEA.acquire(timeout=CAKAJ_NA_SLICICO_S):
        return None
    try:
        # Slika s tretje sekunde (zacetek je pogosto crn); krajsi posnetek da prvo sliko. Samo protokol file: .mp4, ki
        # je v resnici seznam HLS, ne odpre omreznih naslovov (sedmi pregled, naloga 6).
        for zamik in ("3", "0"):
            try:
                r = subprocess.run(
                    [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-protocol_whitelist", "file",
                     "-ss", zamik, "-i", pot,
                     "-frames:v", "1", "-vf", "scale='min(%d,iw)':-2" % rob, "-f", "image2pipe",
                     "-vcodec", "mjpeg", "-q:v", "4", "-"],
                    stdin=subprocess.DEVNULL, capture_output=True, timeout=15)
            except Exception:  # noqa: BLE001 - ffmpeg obstane ali ga ni mogoce zagnati
                return None
            if r.returncode == 0 and len(r.stdout) > 200:
                return r.stdout
    finally:
        _SLICICE_VIDEA.release()
    return None


def naredi_slicico(pot: str, rob: int = SLICICA_ROB) -> Optional[bytes]:
    """Pomanjsan JPEG slike (Pillow, obrnjen po EXIF) ali slike iz videa (ffmpeg). None, kadar slicice ni mogoce
    narediti - naprava takrat pokaze ikono ali si sliko prenese sama. Slicica se naredi enkrat za isto datoteko
    (pot, cas spremembe, velikost) in ostane v pomnilniku."""
    try:
        s = os.stat(pot)
    except OSError:
        return None
    kljuc = (pot, int(s.st_mtime), s.st_size, rob)
    with _slicice_kljuc:
        znana = _slicice.get(kljuc)
        if znana is not None:
            _slicice.move_to_end(kljuc)
            return znana
    vrsta = vrsta_datoteke(pot)
    slicica = _slicica_slike(pot, rob) if vrsta == "image" else _slicica_videa(pot, rob) if vrsta == "video" else None
    if slicica:
        with _slicice_kljuc:
            _slicice[kljuc] = slicica
            while len(_slicice) > NAJVEC_SLICIC:
                _slicice.popitem(last=False)
    return slicica


def postrezi_slicico(obravnava, streznik: "StreznikDatotek", oznaka: str, samo_glava: bool) -> None:
    """Slicica slike ali videa iz deljene mape (`/thumb/<id>`, prek Huba `/cast/thumb/<id>`), z istim zetonom kot
    datoteka. 404, kadar slicice ni mogoce narediti."""
    z = obravnava.headers.get("X-Safeer-Token")
    if not streznik.zeton_velja(z.strip() if z else None, zmoznost=ZMOZNOST_DATOTEKE, oznaka=oznaka):
        _napaka_http(obravnava, 401, "manjka ali napacen zeton")
        return
    r = streznik.mape.razresi(oznaka)
    if r is None or not os.path.isfile(r[1]):
        _napaka_http(obravnava, 404, "datoteke ni")
        return
    slicica = naredi_slicico(r[1])
    if not slicica:
        _napaka_http(obravnava, 404, "slicice ni")
        return
    obravnava.send_response(200)
    obravnava.send_header("Content-Type", "image/jpeg")
    obravnava.send_header("Content-Length", str(len(slicica)))
    obravnava.send_header("Cache-Control", "private, max-age=0")
    obravnava.end_headers()
    if samo_glava:
        return
    try:
        # Slicica je drobna zahteva med brskanjem: budnosti racunalnika ne podaljsuje (to delata datoteka in tok).
        obravnava.wfile.write(slicica)
    except (BrokenPipeError, ConnectionResetError, ssl.SSLError, socket.timeout):
        pass


# ------------------------------------------------------------------ opis kosov (»Nadaljuj na drugi napravi«)
#: Najvec toliko opisov datotek drzimo v pomnilniku (najdlje neuporabljeni izpadejo).
NAJVEC_OPISOV = 32
#: Najvec toliko opisov hkrati se racuna (vsak prebere celo datoteko): mapa s sto zahtevami ne zasede vseh jeder in diska.
_OPISI_HKRATI = threading.BoundedSemaphore(2)
#: Na mesto za racunanje opisa zahteva pocaka najvec toliko, nato 503 (zasedeno; odjemalec prenese celo datoteko).
#: Prej je cakala brez roka: dva opisa pocasnih datotek (zaspan disk USB, omrezna mapa) sta za vedno ustavila vse
#: naslednje zahteve /kosi/ (pregled 18. 10. 2026). 30 s kot mesto za popravek Teamworka (_POPRAVKI_HKRATI).
CAKAJ_NA_OPIS_S = 30.0
#: Opis se racuna najvec toliko: odjemalec (core/link_nadaljuj.ROK_OPISA_S) dlje ne caka, delo po roku bi bilo zaman.
#: Izmerjeno 18. 10. 2026 (256 MiB, 2 deljeni jedri): z numpy 35-38 MB/s (4 GiB v ~120 s), cisti Python 5-6 MB/s
#: (v roku ~1,6 GB; vecja datoteka brez opisa pride v celoti - kot prej, ko je odjemalec po 300 s nehal cakati).
ROK_RACUNANJA_OPISA_S = 300.0
#: Rok tisine pri pisanju odgovora (opis datoteke 4 GiB je nekaj MB JSON): naprava, ki ne bere vec, ne drzi niti za
#: vedno - enako kot ROK_BRANJA_POPRAVKA_S pri sprejemu popravka.
ROK_PISANJA_OPISA_S = 60.0


class OpisZaseden(Exception):
    """Mesta za racunanje opisa ni bilo v CAKAJ_NA_OPIS_S."""
_opisi: "collections.OrderedDict[tuple, bytes]" = collections.OrderedDict()
_opisi_kljuc = threading.Lock()


def _kljuc_opisa(pot: str) -> Optional[tuple]:
    try:
        s = os.stat(pot)
    except OSError:
        return None
    return (pot, s.st_size, s.st_mtime_ns, s.st_ino)


def opis_kosov(pot: str) -> Optional[bytes]:
    """Opis datoteke za prenos samo spremenjenih kosov (core/link_delta.manifest) kot JSON. Opis velja za
    (pot, velikost, cas spremembe v ns, inode) - ob vsaki spremembi datoteke se izracuna znova. None, ce datoteka
    med branjem ni mirovala ali je prevelika."""
    from core import link_delta
    kljuc = _kljuc_opisa(pot)
    if kljuc is None or kljuc[1] > link_delta.NAJVEC_VELIKOST:
        return None
    with _opisi_kljuc:
        znan = _opisi.get(kljuc)
        if znan is not None:
            _opisi.move_to_end(kljuc)
            return znan
    if not _OPISI_HKRATI.acquire(timeout=CAKAJ_NA_OPIS_S):
        raise OpisZaseden("ni mesta za opis kosov")
    try:
        # Budnosti tu ne podaljsujemo: opis je kratko branje, kose naprava nato prenese z /d/ (ta jo podaljsa).
        opis = link_delta.manifest(pot, konec=time.monotonic() + ROK_RACUNANJA_OPISA_S)
    finally:
        _OPISI_HKRATI.release()
    if _kljuc_opisa(pot) != kljuc or opis["velikost"] != kljuc[1]:
        return None                      # datoteka se je med branjem spremenila: opis ne velja
    telo = json.dumps(opis, separators=(",", ":")).encode("utf-8")
    with _opisi_kljuc:
        _opisi[kljuc] = telo
        _opisi.move_to_end(kljuc)
        while len(_opisi) > NAJVEC_OPISOV:
            _opisi.popitem(last=False)
    return telo


def postrezi_kose(obravnava, streznik: "StreznikDatotek", oznaka: str, samo_glava: bool) -> None:
    """Opis kosov datoteke (`/kosi/<id>`, prek Huba `/cast/kosi/<id>`): ISTI zeton in ISTA pravica kot prenos datoteke
    (zmoznost "d" ali izrecno poslana datoteka). Same kose naprava nato prenese z obicajnim `Range` GET /d/<id>."""
    z = obravnava.headers.get("X-Safeer-Token")
    if not streznik.zeton_velja(z.strip() if z else None, zmoznost=ZMOZNOST_DATOTEKE, oznaka=oznaka):
        _napaka_http(obravnava, 401, "manjka ali napacen zeton")
        return
    r = streznik.mape.razresi(oznaka)
    if r is None or not os.path.isfile(r[1]):
        _napaka_http(obravnava, 404, "datoteke ni")
        return
    telo = None
    zacetek = time.monotonic()
    for _ in range(2):
        try:
            telo = opis_kosov(r[1])
        except (OpisZaseden, TimeoutError):
            # Ni mesta ali opis ni koncan v roku: odjemalec brez opisa prenese celo datoteko (link_nadaljuj).
            _napaka_http(obravnava, 503, "zasedeno")
            return
        except OSError:
            telo = None
        if telo is not None or time.monotonic() - zacetek > ROK_RACUNANJA_OPISA_S / 2:
            break
    if telo is None:
        _napaka_http(obravnava, 409, "datoteka se spreminja ali je prevelika")
        return
    try:
        # Prek Huba po glavah povezava nima roka (link_hub_streznik.parse_request): odgovor brez roka bi drzal nit.
        obravnava.connection.settimeout(ROK_PISANJA_OPISA_S)
    except (OSError, AttributeError):
        pass
    try:
        obravnava.send_response(200)
        obravnava.send_header("Content-Type", "application/json")
        obravnava.send_header("Content-Length", str(len(telo)))
        obravnava.send_header("Cache-Control", "no-store")
        obravnava.end_headers()
        if samo_glava:
            return
        obravnava.wfile.write(telo)
    except (BrokenPipeError, ConnectionResetError, ssl.SSLError, socket.timeout, TimeoutError):
        obravnava.close_connection = True


# ------------------------------------------------------------------ ena vrata za streznik datotek in Hub
#: Poti streznika datotek. Hub jih streze pod /cast (Global Link pripelje samo do vrat Huba), zato mora biti
#: seznam en sam: kar dela doma, dela zdoma.
POTI_STREZNIKA = ("/d/", "/thumb/", "/m/", "/live/", "/kosi/")


def je_pot_streznika(pot: str) -> bool:
    return any(pot.startswith(p) for p in POTI_STREZNIKA)


def postrezi_pot(obravnava, streznik: "StreznikDatotek", pot: str, samo_glava: bool) -> None:
    """GET/HEAD katerekoli poti streznika datotek (`pot` brez /cast): datoteka, slicica, tok torrenta, sprotni tok."""
    if pot.startswith("/m/"):
        # Torrent, ki ga za napravo (npr. televizor) prenasa in pretaka ta racunalnik.
        deli = pot.split("/")
        posreduj_tok(obravnava, streznik, deli[2] if len(deli) > 2 else "", samo_glava)
        return
    if pot.startswith("/live/"):
        # Sprotno pretvorjeni tok za napravo, ki izvirnika ne zna predvajati (link_sprotno): zeton kot pri datotekah in
        # zmoznost predvajalnika, s katero je naprava tok narocila (video.stream) - odvzem velja za vsako zahtevo.
        z = obravnava.headers.get("X-Safeer-Token")
        if not streznik.zeton_velja(z.strip() if z else None, zmoznost=ZMOZNOST_PREDVAJALNIK):
            _napaka_http(obravnava, 401, "manjka ali napacen zeton")
            return
        # Tok tece dolgo: med posiljanjem se preveri, ali naprava predvajalnik se ima (odvzem konca tudi tekoci tok).
        zeton_toka = z.strip() if z else None
        obravnava.safeer_se_velja = _Straza(lambda: streznik.zeton_velja(zeton_toka, zmoznost=ZMOZNOST_PREDVAJALNIK)).velja
        from core import link_sprotno
        (getattr(streznik, "sprotno", None) or link_sprotno.sprotno()).postrezi(obravnava, pot[6:].split("/")[0], samo_glava)
        return
    if pot.startswith("/thumb/"):
        postrezi_slicico(obravnava, streznik, urllib.parse.unquote(pot[7:]), samo_glava)
        return
    if pot.startswith("/kosi/"):
        postrezi_kose(obravnava, streznik, urllib.parse.unquote(pot[6:]), samo_glava)
        return
    if not pot.startswith("/d/"):
        _napaka_http(obravnava, 404, "ni take poti")
        return
    postrezi_datoteko(obravnava, streznik, urllib.parse.unquote(pot[3:]), samo_glava)


def _mape_zagona() -> set:
    """Mape, iz katerih se ob prijavi kaj zazene: koren domace mape (zagonske datoteke lupine), ~/bin in ~/.local/bin
    (tudi kot simbolna povezava) in vse mape na PATH znotraj domace mape (pregled 11, N11)."""
    dom = os.path.realpath(os.path.expanduser("~"))
    mape = {dom, os.path.realpath(os.path.join(dom, "bin")), os.path.realpath(os.path.join(dom, ".local", "bin"))}
    # PATH tega procesa ni PATH prijave (~/.bashrc doda svoje): pogoste mape orodij so na PATH skoraj vedno (M9).
    mape |= {os.path.realpath(os.path.join(dom, *d)) for d in (("go", "bin"), (".cargo", "bin"), (".deno", "bin"))}
    for p in (os.environ.get("PATH") or "").split(os.pathsep):
        if p:
            r = os.path.realpath(os.path.expanduser(p))
            if r.startswith(dom + os.sep):
                mape.add(r)
    return mape


def _namizje_xdg() -> str:
    """Namizje iz ~/.config/user-dirs.dirs (XDG_DESKTOP_DIR) - ime je v jeziku namestitve (Schreibtisch, Bureau ...);
    prazno, ce ga ni (pregled 17, M9)."""
    dom = os.path.realpath(os.path.expanduser("~"))
    try:
        with open(os.path.join(dom, ".config", "user-dirs.dirs"), "r", encoding="utf-8", errors="replace") as d:
            vrstice = d.read(16384).splitlines()
    except OSError:
        return ""
    for v in vrstice:
        v = v.strip()
        if v.startswith("XDG_DESKTOP_DIR="):
            vrednost = v.split("=", 1)[1].strip().strip('"')
            if vrednost.startswith("$HOME"):
                vrednost = dom + vrednost[len("$HOME"):]
            return os.path.realpath(vrednost) if os.path.isabs(vrednost) else ""
    return ""


def _mapa_namizja(mapa: str) -> bool:
    """Namizje (zaganjalniki .desktop se tam pokazejo in jim namizje lahko zaupa)."""
    dom = os.path.realpath(os.path.expanduser("~"))
    r = os.path.realpath(mapa)
    if os.path.dirname(r) == dom and os.path.basename(r).lower() in ("desktop", "namizje"):
        return True
    xdg = _namizje_xdg()
    return bool(xdg) and r == xdg


def _ime_za_zagon(ime: str, mapa: str) -> bool:
    """Ime, ki ga naprava ne sme dati: skrita datoteka ali mapa (.bash_profile, .xprofile, .config ...), ime s
    skrivnostjo in ~/bin (na PATH ob prijavi). Prej je naprava z urejanjem lahko naredila datoteko, ki se izvede ob
    naslednji prijavi (sedmi pregled, naloga 6, 25. 10. 2026)."""
    ime = os.path.basename(str(ime or "").strip())
    if not ime or ime.startswith(".") or _skrivnost(ime):
        return True
    return os.path.realpath(mapa) == os.path.realpath(os.path.expanduser("~")) and ime.lower() == "bin"


def _mapa_za_zagon(mapa: str) -> bool:
    """Mape, v katere naprava nicesar ne premakne (_mape_zagona)."""
    return os.path.realpath(mapa) in _mape_zagona()


def uredi_pot(obravnava, streznik: "StreznikDatotek", pot: str) -> None:
    """POST `/d/<id>` (prek Huba `/cast/d/<id>`): urejanje datoteke z naprave - `{"op": "delete"|"rename"|"move"|"rotate",
    ...}` z istim zetonom kot prenos."""
    if not pot.startswith("/d/"):
        _napaka_http(obravnava, 404, "ni take poti")
        return
    z = obravnava.headers.get("X-Safeer-Token")
    # Urejanje (brisanje, preimenovanje, premik) samo z odprtimi datotekami - izrecno poslana datoteka je samo za branje.
    if not streznik.zeton_velja(z.strip() if z else None, zmoznost=ZMOZNOST_DATOTEKE):
        _napaka_http(obravnava, 401, "manjka ali napacen zeton")
        return
    try:
        dolzina = int(obravnava.headers.get("Content-Length") or 0)
    except ValueError:
        dolzina = -1
    if dolzina < 0 or dolzina > NAJVEC_TELESA:
        _napaka_http(obravnava, 413, "predolgo telo")
        return
    try:
        zahteva = json.loads(obravnava.rfile.read(dolzina).decode("utf-8") or "{}")
        if not isinstance(zahteva, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        _napaka_http(obravnava, 400, "telo ni JSON")
        return
    koda, odgovor = streznik.uredi(urllib.parse.unquote(pot[3:]), zahteva,
                                   naprava=streznik.naprava_zetona((z or "").strip()) or None)
    telo = json.dumps(odgovor).encode("utf-8")
    obravnava.send_response(koda)
    obravnava.send_header("Content-Type", "application/json")
    obravnava.send_header("Content-Length", str(len(telo)))
    obravnava.send_header("Connection", "close")
    obravnava.end_headers()
    obravnava.wfile.write(telo)


#: Najvec toliko popravkov Teamworka hkrati (vsak gre v zacasno datoteko na disk tega racunalnika).
_POPRAVKI_HKRATI = threading.BoundedSemaphore(2)
#: Rezerva diska poleg popravka (in sestavljene datoteke) je ista kot drugod v Linku: link_viri.rezerva_diska (2 %
#: diska, 1-10 GiB; tudi kopija razlicice v link_teamwork). Prej je bila tu REZERVA_DISKA = 512 MiB, ki jo je spodnja
#: istoimenska meja pomoci (2 GiB) ob uvozu modula tiho povozila - komentar in delovanje se nista ujemala.
#: Rok tisine med branjem popravka (kot ROK_BRANJA_S Huba): prek Huba povezava po glavah nima roka - naprava, ki je
#: sredi oddaje izgubila omrezje, je za vedno drzala nit, eno od dveh mest za popravke in zacasno datoteko.
ROK_BRANJA_POPRAVKA_S = 60.0


def sprejmi_popravek(obravnava, streznik: "StreznikDatotek", oznaka: str) -> None:
    """POST `/popravek/<id>` (prek Huba `/cast/popravek/<id>`): Teamwork - shranitev datoteke z naprave, ki jo ureja
    (core/link_teamwork). Isti zeton in ista pravica kot urejanje (odprte datoteke, ne samo izrecno poslana), naprava
    pa mora biti prijavljena v sejo te datoteke. Telo gre v zacasno datoteko, sestavi ga Teamwork."""
    from core import link_teamwork
    obravnava.close_connection = True
    z = obravnava.headers.get("X-Safeer-Token")
    z = z.strip() if z else None
    tw = getattr(streznik, "teamwork", None)
    if not streznik.zeton_velja(z, zmoznost=ZMOZNOST_DATOTEKE):
        _napaka_http(obravnava, 401, "manjka ali napacen zeton")
        return
    naprava = streznik.naprava_zetona(z)
    if tw is None or not naprava:
        _napaka_http(obravnava, 404, "teamwork ni na voljo")
        return
    if _je_dom(oznaka) and not getattr(streznik, "v_ozjem_krogu", _v_ozjem_krogu)(naprava):
        _napaka_http(obravnava, 404, "datoteke ni")       # domaca mapa samo ozjemu krogu
        return
    try:
        dolzina = int(obravnava.headers.get("Content-Length") or -1)
    except ValueError:
        dolzina = -1
    if dolzina <= 0 or dolzina > link_teamwork.NAJVEC_POPRAVKA:
        _napaka_http(obravnava, 413, "napacna dolzina")
        return
    from core import link_viri
    try:
        # Popravek in iz njega sestavljena datoteka: dvakratna velikost + rezerva, sicer 507 (naprava ne poskusa
        # vsakih nekaj sekund znova - core/link_teamwork.PREMOR_PO_NAPAKI_S).
        mapa = tw._mapa_zacasnih()
        prosto = shutil.disk_usage(mapa).free
        rezerva = link_viri.rezerva_diska(mapa)
    except OSError:
        prosto, rezerva = 0, link_viri.NAJMANJ_REZERVE_DISKA
    if prosto < 2 * dolzina + rezerva:
        _napaka_http(obravnava, 507, "ni prostora")
        return
    try:
        obravnava.connection.settimeout(ROK_BRANJA_POPRAVKA_S)
    except (OSError, AttributeError):
        pass
    if not _POPRAVKI_HKRATI.acquire(timeout=30):
        _napaka_http(obravnava, 503, "zasedeno")
        return
    try:
        _sprejmi_popravek(obravnava, tw, naprava, oznaka, dolzina)
    except Exception as e:  # noqa: BLE001 - naprava je odsla (odgovora ni komu poslati); mesto se sprosti spodaj
        print("[Teamwork] popravek:", e, file=sys.stderr)
    finally:
        _POPRAVKI_HKRATI.release()


def _sprejmi_popravek(obravnava, tw, naprava: str, oznaka: str, dolzina: int) -> None:
    fd, telo = tempfile.mkstemp(prefix=".popravek-", dir=tw._mapa_zacasnih())
    try:
        with os.fdopen(fd, "wb") as f:
            ostane = dolzina
            while ostane > 0:
                kos = obravnava.rfile.read(min(ostane, 1024 * 1024))
                if not kos:
                    break
                f.write(kos)
                ostane -= len(kos)
        if ostane > 0:
            _napaka_http(obravnava, 400, "telo ni celo")
            return
        koda, odgovor = tw.popravek(naprava, oznaka, telo)
    except (socket.timeout, ConnectionError, ssl.SSLError) as e:
        # Naprava je med oddajo utihnila ali odsla: odgovora ni komu poslati.
        print("[Teamwork] popravek prekinjen:", e, file=sys.stderr)
        obravnava.close_connection = True
        return
    except Exception as e:  # noqa: BLE001 - naprava dobi odgovor, ne prekinjene povezave
        # Podrobnosti (poti, besedilo izjeme) samo v krajevni dnevnik: napravi ne povemo, kje so datoteke tega racunalnika.
        print("[Teamwork] popravek ni uspel:", type(e).__name__, e, file=sys.stderr)
        koda, odgovor = 500, {"ok": False, "koda": "napaka"}
    finally:
        try:
            os.remove(telo)
        except OSError:
            pass
    podatki = json.dumps(odgovor).encode("utf-8")
    try:
        obravnava.send_response(koda)
        obravnava.send_header("Content-Type", "application/json")
        obravnava.send_header("Content-Length", str(len(podatki)))
        obravnava.send_header("Connection", "close")
        obravnava.end_headers()
        obravnava.wfile.write(podatki)
    except (OSError, ssl.SSLError, socket.timeout):
        pass


def posreduj_tok(obravnava, streznik: "StreznikDatotek", skrivnost: str, samo_glava: bool) -> None:
    """Tok torrenta, ki ga prenasa racunalnik, za napravo v krogu: zeton v glavi, `Range` gre naprej.

    Naprava (televizor s sibkim pomnilnikom) tako nicesar ne prenasa in ne shranjuje: dobi le
    sproten tok, kot pri spletnem videu. Lokalni tok (127.0.0.1) je dosegljiv samo prek tega
    posrednika in samo s skrivnostjo, ki jo je racunalnik izdal za ta tok."""
    z = obravnava.headers.get("X-Safeer-Token")
    tok = streznik.tok(skrivnost)
    # Tok, ki ga je naprava narocila z zmoznostjo (magnet.stream: predvajalnik), jo zahteva pri vsaki zahtevi. Tok, ki ga
    # je dal ta racunalnik sam (pretvorba, shramba), samo zeton - tako kot prej.
    if not streznik.zeton_velja(z.strip() if z else None, zmoznost=tok[1] if tok else None):
        _napaka_http(obravnava, 401, "manjka ali napacen zeton")
        return
    if tok is None:
        _napaka_http(obravnava, 404, "toka ni")
        return
    zeton, zmoznost_toka = (z.strip() if z else None), tok[1]

    def se_velja() -> bool:
        return streznik.tok(skrivnost) is not None and streznik.zeton_velja(zeton, zmoznost=zmoznost_toka)
    cilj = tok[0]
    if cilj.startswith("file://"):
        # Film je na tem racunalniku ze v celoti (npr. prenesen v Safeer OS): postrezemo ga z diska.
        pot = cilj[len("file://"):]
        if not os.path.isfile(pot):
            _napaka_http(obravnava, 404, "datoteke ni")
            return
        _poslji_datoteko(obravnava, pot, samo_glava, se_velja=se_velja)
        return
    u = urllib.parse.urlparse(cilj)
    glave = {"Range": obravnava.headers["Range"]} if obravnava.headers.get("Range") else {}
    povezava = http.client.HTTPConnection(u.hostname or "127.0.0.1", u.port or 80, timeout=120)
    try:
        povezava.request("HEAD" if samo_glava else "GET", u.path, headers=glave)
        r = povezava.getresponse()
        obravnava.send_response(r.status)
        for ime in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
            if r.getheader(ime):
                obravnava.send_header(ime, r.getheader(ime))
        obravnava.send_header("Cache-Control", "no-store")
        obravnava.send_header("Connection", "close")
        obravnava.end_headers()
        if samo_glava:
            return
        straza = _Straza(se_velja)
        while True:
            if not straza.velja():
                print("[SafeerDatoteke] tok prekinjen: naprava nima vec dostopa", flush=True)
                obravnava.close_connection = True
                break
            kos = r.read(VELIKOST_KOSA)
            if not kos:
                break
            obravnava.wfile.write(kos)
            budnost.dotik()          # naprava gleda tok: racunalnik medtem ne zaspi sam
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        povezava.close()


#: Streznik poslusa na vseh vmesnikih, a je samo za domace omrezje (kot Hub, link_hub_streznik._je_krajevni_naslov):
#: zanka, zasebni IPv4 (RFC 1918), link-local in IPv6 ULA. Zdoma pridejo naprave do datotek prek Huba (/cast/...).
KRAJEVNA_OMREZJA = tuple(ipaddress.ip_network(o) for o in (
    "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16",
    "::1/128", "fe80::/10", "fc00::/7"))


def je_krajevni_vir(naslov: str) -> bool:
    """Ali je naslov vira povezave iz domacega omrezja (ali ta naprava)."""
    try:
        ip = ipaddress.ip_address(str(naslov or "").split("%", 1)[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return any(ip in o for o in KRAJEVNA_OMREZJA if o.version == ip.version)


#: Skupni rok za glave: od sprejema povezave (rokovanje TLS + vrstica zahteve + glave) oziroma od konca prejsnje
#: zahteve (keep-alive). Rok na posamezen recv (120 s) tega ne omeji - kdor poslje en bajt na nekaj sekund
#: (slowloris), bi drzal nit in deskriptor za vedno (pregled 19. 10. 2026). Telefon v slabem Wi-Fi rabi < 2 s.
ROK_GLAV_S = 20.0
#: Fiksni meji samo za povezave PRED glavami (kot nepreverjene v core/link_neposredno): naprave z zetonom, ki tok
#: berejo, ne omejuje nobena stevilka. Nad mejo izpade najstarejsa cakajoca (najprej istega vira) - nova ni nikoli
#: zavrnjena, zato tihe povezave ne zasedejo mest pravim napravam. Android (OkHttp) odpre najvec 5 povezav na streznik.
NAJVEC_PRED_GLAVAMI = 128
NAJVEC_PRED_GLAVAMI_NA_VIR = 32


class _CuvajGlav:
    """Ena nit za vse povezave streznika: povezavo, ki do roka ne poslje celih glav, zapre (shutdown zbudi nit, ki na
    njej bere, in ta jo pospravi). Nit brez povezav spi brez bujenja (kot BrezBujenja)."""

    def __init__(self, rok_s: Optional[float] = None, najvec: Optional[int] = None,
                 najvec_na_vir: Optional[int] = None) -> None:
        self.rok_s = ROK_GLAV_S if rok_s is None else rok_s
        self.najvec = NAJVEC_PRED_GLAVAMI if najvec is None else najvec
        self.najvec_na_vir = NAJVEC_PRED_GLAVAMI_NA_VIR if najvec_na_vir is None else najvec_na_vir
        self._pogoj = threading.Condition()
        self._cakajo: "collections.OrderedDict[int, tuple]" = collections.OrderedDict()   # id -> (vticnik, vir, rok)
        self._na_vir: Dict[str, int] = {}
        self._nit: Optional[threading.Thread] = None
        self._konec = False
        #: Koliko povezav smo zaprli (za dnevnik in preizkuse).
        self.zaprtih = 0

    def zacni(self, vticnik, vir: str) -> None:
        """Povezava caka na glave. Ce ze caka (prva zahteva, prijavljena ob sprejemu), rok ostane od sprejema."""
        odvec = []
        with self._pogoj:
            if self._konec or id(vticnik) in self._cakajo:
                return
            self._cakajo[id(vticnik)] = (vticnik, vir, time.monotonic() + self.rok_s)
            self._na_vir[vir] = self._na_vir.get(vir, 0) + 1
            if self._na_vir[vir] > self.najvec_na_vir:
                odvec.append(self._odstrani(next(k for k, z in self._cakajo.items() if z[1] == vir)))
            while len(self._cakajo) > self.najvec:
                najvec_vir = max(self._na_vir, key=lambda v: self._na_vir[v])
                odvec.append(self._odstrani(next(k for k, z in self._cakajo.items() if z[1] == najvec_vir)))
            self._zazeni_nit()
            self._pogoj.notify()
        self._zapri(odvec)

    def zazeni(self) -> None:
        """Nit cuvaja tece od zagona streznika do ustavi() (ena nit, brez bujenja, dokler ni povezav)."""
        with self._pogoj:
            self._zazeni_nit()

    def _zazeni_nit(self) -> None:
        if self._nit is None and not self._konec:
            self._nit = threading.Thread(target=self._zanka, name="safeer-datoteke-rok", daemon=True)
            self._nit.start()

    def koncaj(self, vticnik) -> None:
        """Glave so prisle (ali je povezave konec)."""
        with self._pogoj:
            if id(vticnik) in self._cakajo:
                self._odstrani(id(vticnik))

    def cakajocih(self, vir: Optional[str] = None) -> int:
        with self._pogoj:
            return len(self._cakajo) if vir is None else self._na_vir.get(vir, 0)

    def ustavi(self) -> None:
        with self._pogoj:
            self._konec = True
            self._cakajo.clear()
            self._na_vir.clear()
            self._pogoj.notify()

    def _odstrani(self, k: int) -> tuple:
        z = self._cakajo.pop(k)
        ostane = self._na_vir.get(z[1], 1) - 1
        if ostane > 0:
            self._na_vir[z[1]] = ostane
        else:
            self._na_vir.pop(z[1], None)
        return z

    def _zapri(self, povezave: list) -> None:
        # Obrambi tega ne javljamo posebej: povezava, zaprta med rokovanjem TLS, steje kot neuspelo rokovanje
        # (ob_neuspelem_rokovanju) - dvojno stetje bi zaprlo tudi pravo napravo v slabem Wi-Fi.
        for z in povezave:
            self.zaprtih += 1
            os_deskriptorji.zapri_vticnik(z[0])

    def _zanka(self) -> None:
        while True:
            with self._pogoj:
                while True:
                    if self._konec:
                        self._nit = None
                        return
                    if not self._cakajo:
                        self._pogoj.wait()
                        continue
                    zdaj = time.monotonic()
                    najblizji = min(z[2] for z in self._cakajo.values())
                    if najblizji <= zdaj:
                        break
                    self._pogoj.wait(najblizji - zdaj)
                izteklo = [self._odstrani(k) for k, z in list(self._cakajo.items()) if z[2] <= zdaj]
            self._zapri(izteklo)


class _Streznik(os_deskriptorji.BrezBujenja, link_tls.RokovanjeVNiti, http.server.ThreadingHTTPServer):
    daemon_threads = True
    #: Predvajalnik, ki obstane (pavza), ne drzi niti v nedogled (rok na recv/send PO glavah; glave ima _CuvajGlav).
    rok_po_rokovanju = 120.0
    allow_reuse_address = True
    #: Obramba (core/link_obramba.Obramba, zivi v StreznikDatotek) in cuvaj glav; None v preizkusih brez njiju.
    obramba = None
    cuvaj: Optional[_CuvajGlav] = None

    def verify_request(self, request, client_address) -> bool:
        """Tuj vir (ne domace omrezje) in vir, ki ga je obramba zaprla, ne prideta niti do rokovanja TLS."""
        vir = str(client_address[0]) if client_address else ""
        if not je_krajevni_vir(vir):
            return False
        if self.obramba is not None and not self.obramba.dovoli(vir):
            return False
        if self.cuvaj is not None:
            self.cuvaj.zacni(request, vir)
        return True

    def ob_neuspelem_rokovanju(self, client_address) -> None:
        if self.obramba is not None:
            self.obramba.dogodek(str(client_address[0]) if client_address else "", "rokovanje")

    def shutdown_request(self, request) -> None:
        if self.cuvaj is not None:
            self.cuvaj.koncaj(request)
        super().shutdown_request(request)

    def handle_error(self, request, client_address) -> None:
        # Prekinjena povezava (naprava je odsla, cuvaj glav jo je zaprl) ni napaka streznika in ne sodi v dnevnik.
        if isinstance(sys.exc_info()[1], OSError):
            return
        super().handle_error(request, client_address)


def _ob_zapori_datotek(vir: str, trajanje_s: float, razlog: str) -> None:
    print("[Datoteke] obramba: %s zaprt za %d min (%s)" % (vir, int(trajanje_s // 60), razlog), file=sys.stderr, flush=True)


#: Najvec toliko objavljenih tokov hkrati (film in njegovi podnapisi so vsak svoj tok); najstarejsi izpadejo.
NAJVEC_TOKOV = 256
#: Najvec toliko podnapisov ponudimo napravi ob enem filmu.
NAJVEC_PODNAPISOV_TOKA = 12


class StreznikDatotek:
    """HTTPS streznik datotek Controla: zazene se ob prvi rabi, na nakljucnih vratih, samo za naprave z zetonom."""

    def __init__(self, mape: DeljeneMape, tls_mapa: str = TLS_MAPA) -> None:
        self.mape = mape
        self.tls_mapa = tls_mapa
        self.odtis = ""
        #: Teamwork (core/link_teamwork) za POST /popravek/<id>; brez njega pot vrne 404.
        self.teamwork = None
        self.vrata = 0
        self._zetoni: Dict[str, Tuple[str, float, float]] = {}   # zeton -> (id naprave, izdan, zadnja raba)
        #: Ali je naprava umaknjena iz kroga zaupanja: njeni zetoni takoj prenehajo veljati (ne sele po 12 h).
        self.umaknjena = _umaknjena_iz_kroga
        #: Ali je napravi odprta zmoznost na tem racunalniku (core/link_dostop); preizkusi ga zamenjajo.
        self.sme = _sme_naprava
        #: Ali je naprava v ozjem krogu (domaca mapa, oznake dom:); preizkusi ga zamenjajo.
        self.v_ozjem_krogu = _v_ozjem_krogu
        #: Kar je uporabnik TEGA racunalnika napravi sam poslal ali kar naprava z odprtim predvajalnikom nadaljuje:
        #: (jedro naprave, oznaka datoteke) -> do kdaj. Ta ena datoteka je napravi dosegljiva tudi brez odprtih datotek.
        self._izrecno: Dict[Tuple[str, str], float] = {}
        self._streznik: Optional[_Streznik] = None
        #: Torrenti, ki jih racunalnik pretaka napravam: skrivnost -> (lokalni naslov toka (127.0.0.1) ali file://,
        #: zmoznost, ki jo tok zahteva pri vsaki zahtevi, ali None).
        self._tokovi: Dict[str, Tuple[str, Optional[str]]] = {}
        self._nit: Optional[threading.Thread] = None
        self._kljucavnica = threading.Lock()
        #: Kje streznik poslusa: vsi vmesniki (naprave v domacem omrezju), preizkusi samo zanka.
        self.naslov_poslusanja = "0.0.0.0"
        #: Obramba (core/link_obramba, ista pravila kot Hub): vir, ki tipa ali ne zna TLS, se za nekaj casa zapre.
        #: Zivi dlje kot streznik - zapora velja tudi po ponovnem zagonu streznika v istem procesu.
        self.obramba = link_obramba.Obramba(ob_zapori=_ob_zapori_datotek)

    def tece(self) -> bool:
        return self._streznik is not None

    def zazeni(self) -> None:
        with self._kljucavnica:
            if self._streznik is not None:
                return
            kljuc, potrdilo, self.odtis = zagotovi_potrdilo(self.tls_mapa)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(potrdilo, kljuc)
            s = _Streznik((self.naslov_poslusanja, 0), _Obravnava)
            try:
                s.socket = ctx.wrap_socket(s.socket, server_side=True, do_handshake_on_connect=False)
            except Exception:
                s.server_close()        # kot Hub (link_hub_streznik): ponovni zagon ne sme pustiti odprtih vrat
                raise
            s.streznik = self  # type: ignore[attr-defined]
            s.obramba = self.obramba
            s.cuvaj = _CuvajGlav()
            s.cuvaj.zazeni()
            self.vrata = s.server_address[1]
            self._streznik = s
            self._nit = threading.Thread(target=s.serve_forever, name="safeer-datoteke", daemon=True)
            self._nit.start()

    def ustavi(self) -> None:
        with self._kljucavnica:
            s = self._streznik
            self._streznik = None
        if s is not None:
            try:
                s.shutdown()
                s.server_close()
            except Exception:
                pass
            if s.cuvaj is not None:
                s.cuvaj.ustavi()              # nit cuvaja ne ostane po ustavitvi streznika
        self._zetoni.clear()
        self._tokovi.clear()
        self.vrata = 0

    def zeton_za(self, id_naprave: str, zdaj: Optional[float] = None) -> str:
        """Zeton naprave za prenos in predvajanje.

        Velja ZETON_VELJA_S od zadnje rabe (tok, ki tece, ga drzi pri zivljenju - album s ponavljanjem ali
        dolga pavza ne padeta), a najvec NAJDLJE_S od izdaje. Naprava, ki znova vpraša za seznam, po polovici
        roka dobi novega; prejsnji velja naprej do svojega roka."""
        zdaj = time.monotonic() if zdaj is None else zdaj
        with self._kljucavnica:
            for z, (n, izdan, rabljen) in list(self._zetoni.items()):
                if not _zeton_zivi(izdan, rabljen, zdaj):
                    self._zetoni.pop(z, None)
                elif n == id_naprave and zdaj - izdan < ZETON_VELJA_S / 2:
                    return z
            z = secrets.token_urlsafe(24)
            self._zetoni[z] = (id_naprave, zdaj, zdaj)
            njeni = [k for k, v in self._zetoni.items() if v[0] == id_naprave]
            while len(njeni) > NAJVEC_ZETONOV_NA_NAPRAVO:
                star = min(njeni, key=lambda k: self._zetoni[k][2])
                njeni.remove(star)
                self._zetoni.pop(star, None)
            return z

    def zeton_velja(self, zeton: Optional[str], zdaj: Optional[float] = None, zmoznost: Optional[str] = None,
                    oznaka: Optional[str] = None) -> bool:
        """Ali zeton velja. Z `zmoznost` tudi, ali ima naprava zetona to zmoznost na tem racunalniku SE ZDAJ odprto
        (dostop, ki ga uporabnik vzame, neha veljati takoj, ne sele ob izteku zetona) - ali pa ji je bila prav ta
        datoteka (`oznaka`) izrecno poslana. Brez `zmoznost` se preveri samo zeton (tokovi z lastno skrivnostjo)."""
        # Primerjava v stalnem casu: iz casa odgovora se ne da uganiti, koliko znakov se ujema.
        if not zeton:
            return False
        zdaj = time.monotonic() if zdaj is None else zdaj
        naprava: Optional[str] = None
        najden = ""
        with self._kljucavnica:
            for z, (n, izdan, rabljen) in list(self._zetoni.items()):
                if hmac.compare_digest(zeton.encode(), z.encode()) and _zeton_zivi(izdan, rabljen, zdaj):
                    if self.umaknjena(n):
                        self._zetoni.pop(z, None)
                        return False
                    naprava, najden = n, z
                    break
        if naprava is None:
            return False
        izrecno = self.izrecno_dovoljena(naprava, oznaka, zdaj)
        if zmoznost is not None and not self.sme(naprava, zmoznost) and not izrecno:
            return False
        if _je_dom(oznaka) and not izrecno and not self.v_ozjem_krogu(naprava):
            return False            # domaca mapa samo ozjemu krogu, ne vsaki napravi z »d« (sedmi pregled, naloga 6)
        with self._kljucavnica:
            v = self._zetoni.get(najden)
            if v is not None:
                self._zetoni[najden] = (v[0], v[1], zdaj)
        return True

    def naprava_zetona(self, zeton: Optional[str], zdaj: Optional[float] = None) -> str:
        """Naprava, ki ji je bil zeton izdan (ce se velja), sicer "". Za popravke Teamworka: datoteko sme spremeniti
        samo naprava, ki je prijavljena v sejo te datoteke."""
        if not zeton:
            return ""
        zdaj = time.monotonic() if zdaj is None else zdaj
        with self._kljucavnica:
            for z, (n, izdan, rabljen) in self._zetoni.items():
                if hmac.compare_digest(zeton.encode(), z.encode()) and _zeton_zivi(izdan, rabljen, zdaj):
                    return n
        return ""

    def dovoli_izrecno(self, id_naprave: str, oznaka: str, zdaj: Optional[float] = None) -> None:
        """Ta datoteka je napravi dosegljiva tudi brez odprtih datotek: uporabnik tega racunalnika ji jo je sam
        poslal ali pa jo naprava z odprtim predvajalnikom nadaljuje. Velja, dokler bi veljal zeton."""
        if not id_naprave or not oznaka:
            return
        zdaj = time.monotonic() if zdaj is None else zdaj
        with self._kljucavnica:
            for k in [k for k, rok in self._izrecno.items() if rok <= zdaj]:
                self._izrecno.pop(k, None)
            self._izrecno[(_jedro_naprave(id_naprave), oznaka)] = zdaj + NAJDLJE_S

    def izrecno_dovoljena(self, id_naprave: str, oznaka: Optional[str], zdaj: Optional[float] = None) -> bool:
        if not id_naprave or not oznaka:
            return False
        zdaj = time.monotonic() if zdaj is None else zdaj
        with self._kljucavnica:
            rok = self._izrecno.get((_jedro_naprave(id_naprave), oznaka))
        return rok is not None and zdaj < rok

    def preklici(self, id_naprave: str) -> int:
        """Preklice vse zetone naprave (npr. ko ji vzamemo dostop do celega diska). Vrne stevilo."""
        with self._kljucavnica:
            stari = [z for z, v in self._zetoni.items() if v[0] == id_naprave]
            for z in stari:
                self._zetoni.pop(z, None)
        return len(stari)

    def preklici_jedro(self, jedro_naprave: str) -> int:
        """Preklice zetone VSEH oznak naprave s tem jedrom (Safeer OS, Control, brskalnik na njej): odvzem dostopa ali
        umik iz kroga (sedmi pregled, 25. 10. 2026). Prenosi in tokovi, ki tecejo, se koncajo ob naslednji preverbi
        (PREVERI_MED_POSILJANJEM_S); naprava, ki dostop se ima, dobi nov zeton ob naslednjem seznamu. Vrne stevilo."""
        if not jedro_naprave:
            return 0
        with self._kljucavnica:
            naprave = {v[0] for v in self._zetoni.values()}
        njene = {n for n in naprave if _jedro_naprave(n) == jedro_naprave}
        with self._kljucavnica:
            stari = [z for z, v in self._zetoni.items() if v[0] in njene]
            for z in stari:
                self._zetoni.pop(z, None)
        return len(stari)

    def dodaj_tok(self, lokalni_url: str, zmoznost: Optional[str] = None) -> str:
        """Lokalni tok (samo 127.0.0.1) objavi za naprave z zetonom; vrne pot `/m/<skrivnost>/<ime>`. `zmoznost`: tok je
        naprava narocila s to zmoznostjo in jo mora imeti odprto tudi ob vsaki zahtevi toka."""
        u = urllib.parse.urlparse(lokalni_url)
        if u.scheme != "http" or u.hostname not in ("127.0.0.1", "localhost"):
            raise ValueError("samo lokalni tok")
        skrivnost = secrets.token_urlsafe(18)
        with self._kljucavnica:
            self._tokovi[skrivnost] = (lokalni_url, zmoznost)
            while len(self._tokovi) > NAJVEC_TOKOV:
                self._tokovi.pop(next(iter(self._tokovi)))
        return "/m/%s/%s" % (skrivnost, u.path.rsplit("/", 1)[-1])

    def pozabi_tokove(self) -> None:
        with self._kljucavnica:
            self._tokovi.clear()

    def dodaj_datoteko_toka(self, pot: str, zmoznost: Optional[str] = None) -> str:
        """Ze preneseno datoteko (samo pot, ki jo poda racunalnik sam) objavi kot tok `/m/<skrivnost>/<ime>`.
        Brez `zmoznost` jo je dal ta racunalnik sam (pretvorba, shramba): dovolj je zeton."""
        pot = os.path.realpath(pot)
        if not os.path.isfile(pot):
            raise ValueError("ni datoteke")
        skrivnost = secrets.token_urlsafe(18)
        with self._kljucavnica:
            self._tokovi[skrivnost] = ("file://" + pot, zmoznost)
            while len(self._tokovi) > NAJVEC_TOKOV:
                self._tokovi.pop(next(iter(self._tokovi)))
        return "/m/%s/%s" % (skrivnost, urllib.parse.quote(os.path.basename(pot)))

    def tok(self, skrivnost: str) -> Optional[Tuple[str, Optional[str]]]:
        """(lokalni naslov toka, zmoznost ali None) za skrivnost toka; None, ce toka ni."""
        with self._kljucavnica:
            for k, v in self._tokovi.items():
                if hmac.compare_digest(k.encode(), str(skrivnost or "").encode()):
                    return v
        return None

    def lokalni_tok(self, skrivnost: str) -> Optional[str]:
        t = self.tok(skrivnost)
        return t[0] if t else None

    def osnova(self, naslov_racunalnika: str) -> str:
        return f"https://{naslov_racunalnika}:{self.vrata}"

    def uredi(self, oznaka: str, zahteva: dict, naprava: Optional[str] = None) -> Tuple[int, dict]:
        """Izvede ukaz nad datoteko; vrne (HTTP koda, odgovor). Napake so kratke kode za napravo. `naprava` (iz zetona):
        domaco mapo (oznake dom:) ureja samo naprava v ozjem krogu."""
        ukaz = str(zahteva.get("op") or "")
        if ukaz not in UKAZI:
            return 400, {"ok": False, "napaka": "neznan_ukaz"}
        if (_je_dom(oznaka) or _je_dom(zahteva.get("folder"))) and not (naprava and self.v_ozjem_krogu(naprava)):
            return 404, {"ok": False, "napaka": "ni_datoteke"}     # neznana naprava: ne (pregled 11, N12)
        r = self.mape.razresi(oznaka)
        if r is None:
            return 404, {"ok": False, "napaka": "ni_datoteke"}
        i, pot = r
        if i >= 0 and pot == self.mape.poti[i]:
            return 403, {"ok": False, "napaka": "ni_dovoljeno"}  # deljene mape same ne brisemo in ne preimenujemo
        dom = os.path.realpath(os.path.expanduser("~"))
        if i < 0 and pot in (os.sep, dom):
            return 403, {"ok": False, "napaka": "ni_dovoljeno"}
        if i < 0 and os.path.isdir(pot) and os.path.dirname(pot) == dom:
            # Mape neposredno v domaci mapi (Dokumenti, Slike, Prejemi ...) so mape namizja: naprava jih ne brise, ne
            # preimenuje in ne premika (sedmi pregled, naloga 6) - njihovo vsebino pa ureja.
            return 403, {"ok": False, "napaka": "ni_dovoljeno"}
        try:
            if ukaz == "delete":
                link_urejanje.v_smeti(pot)
                return 200, {"ok": True, "op": ukaz}
            if ukaz == "rename":
                novo_ime = str(zahteva.get("name") or "")
                # Naprava datoteke ne sme narediti za program (film.mp4 -> film.exe / .desktop / .sh): dvoklik ali
                # files.open bi ga zagnal. Program, ki je ze bil, pa sme preimenovati z isto koncnico (skripta.sh ->
                # skripta-stara.sh). Mape niso zaganjalniki.
                if not os.path.isdir(pot) and je_nevarno_ime(novo_ime) and _koncnica(novo_ime) != _koncnica(pot):
                    return 403, {"ok": False, "napaka": "nevarna_vrsta"}
                if _ime_za_zagon(novo_ime, os.path.dirname(pot)):
                    return 403, {"ok": False, "napaka": "nevarna_vrsta"}
                if os.path.isdir(pot) and _mapa_za_zagon(os.path.join(os.path.dirname(pot), novo_ime)):
                    return 403, {"ok": False, "napaka": "ni_dovoljeno"}     # preimenovanje v mapo PATH (M9)
                nova = link_urejanje.preimenuj(pot, novo_ime)
            elif ukaz == "move":
                cilj = self.mape.razresi(str(zahteva.get("folder") or ""))
                if cilj is None:
                    return 404, {"ok": False, "napaka": "ni_mape"}
                if _mapa_za_zagon(cilj[1]) or _ime_za_zagon(os.path.basename(pot), cilj[1]):
                    return 403, {"ok": False, "napaka": "ni_dovoljeno"}
                if os.path.isdir(pot) and _mapa_za_zagon(os.path.join(cilj[1], os.path.basename(pot))):
                    return 403, {"ok": False, "napaka": "ni_dovoljeno"}     # mapa s premikom postane mapa PATH (M9)
                if _mapa_namizja(cilj[1]) and not os.path.isdir(pot) and je_nevarno_ime(os.path.basename(pot)):
                    return 403, {"ok": False, "napaka": "nevarna_vrsta"}
                nova = link_urejanje.premakni(pot, cilj[1])
            else:
                if os.path.isdir(pot) or vrsta_datoteke(pot) != "image":
                    return 400, {"ok": False, "napaka": "ni_slike"}
                nacin = link_urejanje.zavrti(pot, int(zahteva.get("degrees") or 0))
                return 200, {"ok": True, "op": ukaz, "id": oznaka, "how": nacin, "size": os.path.getsize(pot)}
        except link_urejanje.NapakaUrejanja as e:
            return 409 if str(e) == "obstaja" else 400, {"ok": False, "napaka": str(e)}
        except (ValueError, TypeError):
            return 400, {"ok": False, "napaka": "napacna_zahteva"}
        return 200, {"ok": True, "op": ukaz, "id": self.mape.oznaka_poti(nova), "name": os.path.basename(nova)}


class Datoteke:
    """Vse, kar Safeer Control potrebuje za deljenje datotek: izbrane mape, streznik, odgovor na `files.list`."""

    ZMOZNOST = "files"

    def __init__(self, poti: Optional[List[str]] = None, tls_mapa: str = TLS_MAPA,
                 ves_disk: bool = False, dom: bool = False) -> None:
        self.mape = DeljeneMape(poti, ves_disk=ves_disk, dom=dom)
        self.streznik = StreznikDatotek(self.mape, tls_mapa)
        #: Teamwork (core/link_teamwork): Control ga poveze - ukaz files.session in popravki na strezniku.
        self.teamwork = None
        # Klicatelj (Control) ga nastavi, da spremembo map shrani in stran osvezi.
        self.ob_spremembi: Optional[callable] = None
        #: Knjiznica kroga: gledanje() vrne prenose, ki jih je Safeer OS na tem racunalniku zaradi gledanja prenesel
        #: sam (core/knjiznica_kroga.lokalni), odstrani_gledanje(hash) tak prenos odstrani. Nastavi ju Control.
        self.gledanje: Optional[callable] = None
        self.odstrani_gledanje: Optional[callable] = None
        #: »Obdrži« za prenos Safeer OS: obdrzi_gledanje(hash, bool) -> bool (core/knjiznica_kroga.nastavi_obdrzi).
        self.obdrzi_gledanje: Optional[callable] = None

    def poti(self) -> List[str]:
        return list(self.mape.poti)

    def nastavi(self, poti: List[str]) -> None:
        self.mape.nastavi(poti)
        if self.ob_spremembi is not None:
            try:
                self.ob_spremembi(self.poti())
            except Exception:
                pass

    def dodaj(self, pot: str) -> None:
        self.nastavi(self.poti() + [pot])

    def odstrani(self, i: int) -> None:
        p = self.poti()
        if 0 <= i < len(p):
            del p[i]
            self.nastavi(p)

    def pot(self, oznaka: str) -> str:
        """Pot do datoteke z oznako, ki jo naprava sme videti (sicer prazno)."""
        r = self.mape.razresi(str(oznaka or ""))
        return r[1] if r is not None and os.path.exists(r[1]) else ""

    def sme_oznako(self, oznaka: str, id_naprave: str) -> bool:
        """Ali sme naprava do oznake: domaca mapa (dom:) samo v ozjem krogu (link_dostop.v_ozjem_krogu); drugo po
        dovoljenju datotek, ki ga preveri ze ukaz (sedmi pregled, naloga 6: prej je »dom« veljal za ves racunalnik)."""
        return not _je_dom(oznaka) or _v_ozjem_krogu(id_naprave)

    def odpri(self, oznaka: str) -> bool:
        """Odpre datoteko ali mapo **na racunalniku**, s programom, ki ga ima uporabnik zanjo
        (xdg-open). Dovoljene so samo oznake, ki jih naprava ze sme videti - drugega ne odpremo,
        in nikoli ne izvajamo ukazov, ki bi jih naprava poslala."""
        r = self.mape.razresi(str(oznaka or ""))
        if r is None:
            return False
        pot = r[1]
        if not os.path.exists(pot) or nevarna_za_odpiranje(pot):
            return False                      # programov in skript na daljavo ne zaganjamo (nevarna_za_odpiranje)
        from core import varuh_procesov, zasebni_webkit
        odpiralnik = shutil.which("gio") or shutil.which("xdg-open")
        if odpiralnik:
            ukaz = [odpiralnik, "open", pot] if odpiralnik.endswith("gio") else [odpiralnik, pot]
            try:
                pid = varuh_procesov.zazeni_program(ukaz, zasebni_webkit.okolje_za_zunanje())
                if pid:
                    return True
            except Exception:
                pass
        if zasebni_webkit.odpri_privzeto(pot):        # v procesu (Gio), xdg-open/gio sta rezerva
            return True
        if not odpiralnik:
            return False
        ukaz = [odpiralnik, pot] if odpiralnik.endswith("xdg-open") else [odpiralnik, "open", pot]
        try:
            subprocess.Popen(ukaz, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True, env=zasebni_webkit.okolje_za_zunanje())
            return True
        except Exception:
            return False

    def nastavi_ves_disk(self, vklopljeno: bool) -> None:
        """Televizor sme (ali ne sme vec) brskati po celem racunalniku. Velja takoj."""
        self.mape.ves_disk = bool(vklopljeno)

    def ustavi(self) -> None:
        self.streznik.ustavi()

    def preklici_napravo(self, jedro_naprave: str) -> None:
        """Napravi je bil dostop vzet (core/link_dostop.ob_odvzemu): njeni zetoni ne veljajo vec (tekoci prenosi se
        prekinejo) in iz sej Teamwork gre takoj (sourednik, ki ga ni vec)."""
        n = self.streznik.preklici_jedro(jedro_naprave)
        tw = self.teamwork
        odjavljen = 0
        if tw is not None and hasattr(tw, "odjavi_napravo"):
            odjavljen = tw.odjavi_napravo(lambda i: _jedro_naprave(i) == jedro_naprave)
        if n or odjavljen:
            print(f"[SafeerDatoteke] odvzem dostopa: {n} zetonov preklicanih, {odjavljen} sej Teamwork koncanih", flush=True)

    def seznam(self, oznaka: str, id_naprave: str, hub_url: str = "") -> dict:
        """Odgovor na ukaz `files.list` (podatki v `control.result`).

        `items` je seznam vnosov (mape najprej), `folder` oznaka mape, `shared` pove, ali je
        na racunalniku sploh izbrana kaksna mapa; `server` (naslov, odtis, zeton) je tu samo,
        ce je kaj datotek za prenasati - streznik se zazene sele takrat.
        """
        oznaka = str(oznaka or "")
        # Domaco mapo (tudi v »vsem disku«) vidi samo naprava v ozjem krogu: drugim je, kot da je ni (pregledi 6, 11 in
        # 17). Zunanje diske pri »vsem disku« vidi vsaka naprava z dovoljenjem datotek (pregled 17, M3).
        ozji = _v_ozjem_krogu(id_naprave)
        dom, disk = self.mape.dom and ozji, self.mape.ves_disk
        # Brez izbranih map, brez dovoljenja za cel racunalnik in brez domace mape za ozji krog ni kaj pokazati.
        if not self.mape.poti and not disk and not dom:
            return {"items": [], "folder": "", "shared": False}
        if _je_dom(oznaka) and not ozji:
            raise FileNotFoundError("Te mape ni (vec) med deljenimi")
        vnosi = self.mape.seznam(oznaka)
        if vnosi is None:
            raise FileNotFoundError("Te mape ni (vec) med deljenimi")
        if not ozji:
            vnosi = [v for v in vnosi if not _je_dom(v.get("id"))]
        self.mape.dodaj_podnapise(vnosi)
        # `edit`: naprava sme datoteke te mape brisati (v Smeti), preimenovati, premakniti in vrteti slike (POST /d/<id>).
        o: dict = {"items": vnosi, "folder": oznaka if oznaka != "root" else "", "shared": True, "edit": oznaka not in ("", "root")}
        if any(v.get("type") != "folder" for v in vnosi):
            o["server"] = self.streznik_za(id_naprave, hub_url)
        return o

    def streznik_za(self, id_naprave: str, hub_url: str = "") -> dict:
        """Naslov, odtis in zeton streznika datotek za napravo (zazene streznik, ce se ne tece)."""
        self.streznik.zazeni()
        naslov = naslov_do_huba(hub_url) if hub_url else krajevni_naslov()
        return {
            "base_url": self.streznik.osnova(naslov),
            "fp": self.streznik.odtis,
            "token": self.streznik.zeton_za(id_naprave or "naprava"),
            # Hub tega racunalnika streze iste poti pod /cast (Global Link): urejanje, slicice, tokovi.
            # Starejsi Control tega polja nima - naprava zdoma takrat ponudi samo branje.
            "hub": 2,
        }


    def tok_torrenta(self, uri: str, id_naprave: str, hub_url: str = "", datoteka: Optional[int] = None,
                     torrenti=None, zmogljivost=None, mape_stanja=None, pot_rabe: Optional[str] = None,
                     opis_naprave: Optional[dict] = None) -> dict:
        """`magnet.stream`: racunalnik prenasa torrent in ga pretaka napravi (televizorju), ki tako
        nicesar ne shranjuje. Vrne {server, path, name, file} ali vrze os_torrent.NapakaTorrenta.

        `opis_naprave` (opis_iz_parametrov): naslov in plakat, ki ju pove naprava - za polico »Preneseno« na vseh napravah.

        Izbere zahtevano datoteko ali najvecji video; programov (nevarno) nikoli ne predvaja."""
        from core import os_torrent
        m = os_torrent.razcleni_magnet(uri)
        if m is None:
            raise os_torrent.NapakaTorrenta("ni_magnet")
        # Nadzornik: film, ki je na tem racunalniku ze v celoti prenesen (Safeer OS ali prej za drugo
        # napravo), postrezemo takoj z diska - brez zagona torrenta in brez ponovnega prenosa.
        # Zapis o zadnji rabi (za samodejno ciscenje): v preizkusih z vstavljenimi torrenti samo, ce je pot podana.
        if pot_rabe is None and torrenti is None and mape_stanja is None:
            pot_rabe = privzeta_pot_rabe()
        obstojeca, indeks = ze_preneseno(m["hash"], datoteka, mape_stanja)
        if obstojeca:
            zabelezi_rabo(m["hash"], pot_rabe)
            zabelezi_opis(m["hash"], opis_naprave, id_naprave, pot_rabe)
            _osvezi_rabo_gledanja(m["hash"], pot_rabe)
            self.streznik.zazeni()
            naslov = naslov_do_huba(hub_url) if hub_url else krajevni_naslov()
            return {"server": {"base_url": self.streznik.osnova(naslov), "fp": self.streznik.odtis,
                               "token": self.streznik.zeton_za(id_naprave or "naprava")},
                    "path": self.streznik.dodaj_datoteko_toka(obstojeca, ZMOZNOST_PREDVAJALNIK),
                    "name": os.path.basename(obstojeca),
                    "file": indeks, "size": os.path.getsize(obstojeca), "local": True,
                    "subs": self._podnapisi_z_diska(obstojeca, ZMOZNOST_PREDVAJALNIK)}
        if torrenti is None:
            if not os_torrent.program_na_voljo():
                os_torrent.prenesi_program()
            torrenti = torrenti_za_naprave()
        torrenti.zazeni()
        opis = torrenti.preberi(uri)
        videi = [d for d in opis["datoteke"] if d.get("vrsta") == "video"]
        if datoteka is not None:
            izbrana = next((d for d in opis["datoteke"] if d["i"] == int(datoteka) and d.get("vrsta") in ("video", "audio")), None)
        else:
            izbrana = max(videi, key=lambda d: int(d.get("velikost") or 0)) if videi else None
        if izbrana is None:
            raise os_torrent.NapakaTorrenta("ni_predvajljivo")
        # Solidarnost brez preobremenitve: racunalnik pomaga, kolikor zmore - ce je sam zaseden ali nima
        # prostora, to pove in naprava vprasa naslednjega v Linku.
        # Pretakanje torrenta je delo omrezja in diska, ne procesorja: racunalnik ga zmore tudi med prevajanjem
        # (tablica 1. 10. 2026: med gradnjo aplikacije je dobila "preobremenjen" in filma ni bilo).
        # Kar je racunalnik prenesel za naprave in tega 12 ur nihce ni predvajal, odstranimo (lastnik, 3. 10. 2026:
        # "ce uporabnik torrenta ne uporablja vec, ga naprava samodejno odstrani"). Film, ki ga pravkar hocejo, ostane.
        pot_rabe = pot_rabe or _pot_rabe_za(torrenti)
        zabelezi_rabo(m["hash"], pot_rabe)
        zabelezi_opis(m["hash"], opis_naprave, id_naprave, pot_rabe)
        pocisti_neuporabljene(torrenti, pot_rabe)
        mapa_diska = os.path.dirname(getattr(torrenti, "mapa_prenosov", "") or "") or os.path.expanduser("~")
        preveri = zmogljivost or zmogljivost_za_tok
        razlog = preveri(mapa_diska, int(izbrana.get("velikost") or 0))
        if razlog == "ni_prostora":
            # Prostor za nov film naredimo sami: najdlje neuporabljeni prenosi za naprave gredo prvi.
            pocisti_neuporabljene(torrenti, pot_rabe, dovolj=lambda: preveri(mapa_diska, int(izbrana.get("velikost") or 0)) != "ni_prostora",
                                  obdrzi=m["hash"])
            razlog = preveri(mapa_diska, int(izbrana.get("velikost") or 0))
        if razlog:
            raise os_torrent.NapakaTorrenta(razlog)
        tid = torrenti.dodaj(uri, [izbrana["i"]])
        pot = self.streznik.dodaj_tok(torrenti.tok(tid, izbrana["i"]), ZMOZNOST_PREDVAJALNIK)
        self.streznik.zazeni()
        naslov = naslov_do_huba(hub_url) if hub_url else krajevni_naslov()
        return {"server": {"base_url": self.streznik.osnova(naslov), "fp": self.streznik.odtis,
                           "token": self.streznik.zeton_za(id_naprave or "naprava")},
                "path": pot, "name": os.path.basename(str(izbrana.get("ime") or "")), "file": izbrana["i"],
                "size": int(izbrana.get("velikost") or 0),
                "subs": self._podnapisi_torrenta(torrenti, tid, izbrana["i"]) if izbrana.get("vrsta") == "video" else []}

    def _podnapisi_z_diska(self, pot_videa: str, zmoznost: Optional[str] = None) -> List[dict]:
        """Podnapisi ob filmu, ki je ze na disku (ista mapa ali podmapa Subs): vsak svoj tok, kot film."""
        izid: List[dict] = []
        try:
            from core import podnapisi as pn
            for p in pn.podnapisi_mape(pot_videa)[:NAJVEC_PODNAPISOV_TOKA]:
                izid.append({"path": self.streznik.dodaj_datoteko_toka(p, zmoznost), "name": os.path.basename(p)})
        except Exception:  # noqa: BLE001 - podnapisi niso nujni za predvajanje
            pass
        return izid

    def _podnapisi_torrenta(self, torrenti, tid: int, indeks: int) -> List[dict]:
        """Podnapisi iz istega torrenta kot film (`subs` v odgovoru `magnet.stream`): naprava, ki film samo gleda, jih
        dobi kot tokove z istega streznika. Ime pove jezik (Film.en.srt) - razbere ga naprava."""
        izid: List[dict] = []
        try:
            for j, pot_p in list(torrenti.podnapisi_za(tid, indeks))[:NAJVEC_PODNAPISOV_TOKA]:
                ime = os.path.basename(str(pot_p))
                izid.append({"path": self.streznik.dodaj_tok(torrenti.tok(tid, j), ZMOZNOST_PREDVAJALNIK), "name": ime})
        except Exception:  # noqa: BLE001 - podnapisi niso nujni za predvajanje
            pass
        return izid


    def prenosi_za_naprave(self, torrenti=None, pot_rabe: Optional[str] = None, id_naprave: str = "") -> dict:
        """`magnet.list`: kar racunalnik hrani za naprave - knjiznica kroga (polica »Preneseno« na vseh napravah) in
        seznam, s katerega uporabnik prenos odstrani. Kjer je naprava povedala naslov in plakat, ju vrnemo zraven;
        zaseben prenos dobi samo naprava, ki ga je prosila (`id_naprave`)."""
        torrenti = torrenti if torrenti is not None else torrenti_za_naprave()
        pot_opisov = _pot_opisov(pot_rabe or _pot_rabe_za(torrenti))
        opisi = _beri_opise(pot_opisov) if pot_opisov else {}
        zivi = set()
        izid = []
        if not torrenti.tece():
            torrenti.seznam()   # zazene rqbit, ce ima shranjeno stanje
        odstranjeni = set(pocisti_neuporabljene(torrenti, pot_rabe))
        for t in torrenti.seznam():
            if str(t.get("hash") or "").lower() in odstranjeni:
                continue
            videi = [d for d in t.get("datoteke") or [] if d.get("vkljucena") and d.get("vrsta") == "video"]
            try:
                magnet = torrenti.magnet(int(t["id"]))
            except Exception:  # noqa: BLE001
                magnet = ""
            vnos = {"id": int(t["id"]), "name": t.get("ime") or "", "size": int(t.get("skupaj") or 0),
                    "done": int(t.get("preneseno") or 0), "finished": bool(t.get("koncano")),
                    "speed_mibs": t.get("hitrost_mibs") or 0, "magnet": magnet,
                    "file": videi[0]["i"] if videi else None}
            hash_ = _hash_torrenta(torrenti, t) if opisi else ""
            opis = opisi.get(hash_) or {}
            zivi.add(hash_)
            # »Obdrži«: prenos ne potece (polje je vedno tu - naprava po njem ve, da racunalnik zna `magnet.keep`).
            vnos["keep"] = bool(opis.get("keep"))
            if opis.get("private"):
                if not id_naprave or id_naprave not in (opis.get("narocniki") or []):
                    continue                    # zasebno: samo napravi, ki je prenos prosila
                vnos["private"] = True
            elif opis.get("title"):
                vnos.update({k: opis[k] for k in ("title", "poster", "kind", "ref") if opis.get(k)})
            izid.append(vnos)
        # Kar je Safeer OS na tem racunalniku zaradi gledanja prenesel sam in je ze v celoti na disku: ena naprava
        # hrani, vse predvajajo. Zasebnih in tistih brez naslova tu ni (core/knjiznica_kroga.lokalni).
        if self.gledanje is not None:
            try:
                for v in self.gledanje():
                    if not v.get("finished") or v.get("hash") in zivi:
                        continue
                    vnos = {"id": oznaka_gledanja(v["hash"]), "name": v.get("name") or "", "size": int(v.get("size") or 0),
                            "done": int(v.get("size") or 0), "finished": True, "speed_mibs": 0, "magnet": v.get("magnet") or "",
                            "file": v.get("file")}
                    if self.obdrzi_gledanje is not None:
                        vnos["keep"] = bool(v.get("keep"))
                    vnos.update({k: v[k] for k in ("title", "poster", "kind", "ref") if v.get(k)})
                    izid.append(vnos)
            except Exception:  # noqa: BLE001 - polica Controla ne sme pasti zaradi zapisov Safeer OS
                pass
        # Opisi prenosov, ki jih ni vec (odstranjeni rocno ali s ciscenjem), ne ostajajo.
        odvec = [h for h in opisi if h not in zivi]
        if odvec and pot_opisov:
            with _RABA_ZAKLEP:
                sveze = _beri_opise(pot_opisov)
                for h in odvec:
                    sveze.pop(h, None)
                _pisi_rabo(pot_opisov, sveze)
        return {"items": izid}

    def odstrani_prenos(self, tid: int, torrenti=None) -> bool:
        """`magnet.remove`: torrent in njegove prenesene datoteke z racunalnika (samo iz mape prenosov za naprave).
        Negativna oznaka: prenos, ki ga je Safeer OS zaradi gledanja prenesel sam ([oznaka_gledanja])."""
        if int(tid) < 0:
            if self.gledanje is None or self.odstrani_gledanje is None:
                return False
            hash_ = next((str(v.get("hash") or "") for v in self.gledanje() if oznaka_gledanja(str(v.get("hash") or "")) == int(tid)), "")
            if not hash_:
                return False
            self.streznik.pozabi_tokove()
            return bool(self.odstrani_gledanje(hash_))
        torrenti = torrenti if torrenti is not None else torrenti_za_naprave()
        if not torrenti.tece():
            torrenti.seznam()   # zazene rqbit, ce ima shranjeno stanje
        self.streznik.pozabi_tokove()
        return torrenti.odstrani(int(tid), z_datotekami=True)


    def obdrzi_prenos(self, tid: int, obdrzi: bool, torrenti=None, pot_rabe: Optional[str] = None,
                      id_naprave: str = "") -> bool:
        """`magnet.keep`: prenos, ki ga uporabnik hoce obdrzati, ne potece po 12 urah in ne gre ob pomanjkanju prostora
        (odstrani ga samo uporabnik). Zasebnega sme oznaciti le naprava, ki ga je prosila."""
        if int(tid) < 0:
            if self.gledanje is None or self.obdrzi_gledanje is None:
                return False
            hash_ = next((str(v.get("hash") or "") for v in self.gledanje() if oznaka_gledanja(str(v.get("hash") or "")) == int(tid)), "")
            return bool(hash_ and self.obdrzi_gledanje(hash_, bool(obdrzi)))
        torrenti = torrenti if torrenti is not None else torrenti_za_naprave()
        if not torrenti.tece():
            torrenti.seznam()   # zazene rqbit, ce ima shranjeno stanje
        t = next((x for x in torrenti.seznam() if int(x.get("id", -1)) == int(tid)), None)
        hash_ = _hash_torrenta(torrenti, t) if t is not None else ""
        pot_opisov = _pot_opisov(pot_rabe or _pot_rabe_za(torrenti))
        if not hash_ or not pot_opisov or t.get("lastna"):
            return False
        opis = _beri_opise(pot_opisov).get(hash_) or {}
        if opis.get("private") and (not id_naprave or id_naprave not in (opis.get("narocniki") or [])):
            return False
        return nastavi_obdrzi(pot_opisov, hash_, bool(obdrzi))


def obdrzani(pot_opisov: str) -> set:
    """Hashi prenosov, ki jih je uporabnik oznacil z »Obdrži« (zapis opisov ob zapisu rabe)."""
    return {h for h, o in _beri_opise(pot_opisov).items() if o.get("keep")} if pot_opisov else set()


def nastavi_obdrzi(pot_opisov: str, hash_: str, obdrzi: bool) -> bool:
    """Oznaci (ali odznaci) prenos kot obdrzan. Opis prenosa (naslov, zasebnost, narocniki) ostane, kot je."""
    hash_ = str(hash_ or "").lower()
    if not pot_opisov or not re.fullmatch(r"[0-9a-f]{40}", hash_):
        return False
    with _RABA_ZAKLEP:
        opisi = _beri_opise(pot_opisov)
        vnos = dict(opisi.get(hash_) or {})
        if obdrzi:
            vnos["keep"] = True
        else:
            vnos.pop("keep", None)
        if vnos:
            opisi[hash_] = vnos
        else:
            opisi.pop(hash_, None)
        _pisi_rabo(pot_opisov, opisi)
    return True


def oznaka_gledanja(hash_: str) -> int:
    """Oznaka prenosa Safeer OS v `magnet.list`: negativna (motor za naprave ima oznake od 0 navzgor), ista ob vsakem klicu."""
    try:
        return -1 - int(str(hash_)[:7], 16)
    except ValueError:
        return -1


def _osvezi_rabo_gledanja(hash_: str, pot_rabe_naprave: Optional[str]) -> None:
    """Film, ki ga je prenesel Safeer OS in ga zdaj z diska gleda naprava: rok do samodejne odstranitve tece od tega
    predvajanja (zapis rabe Safeer OS stoji ob zapisu rabe Controla)."""
    if not pot_rabe_naprave:
        return
    pot = os.path.join(os.path.dirname(pot_rabe_naprave), "raba-gledanje.json")
    with _RABA_ZAKLEP:
        raba = _beri_rabo(pot)
        if str(hash_).lower() in raba:
            raba[str(hash_).lower()] = float(time.time())
            _pisi_rabo(pot, raba)


def _bdekodiraj(b: bytes, i: int = 0):
    """Najmanjsi bencode bralnik (za .torrent iz stanja rqbit). Vrne (vrednost, naslednji indeks)."""
    c = b[i:i + 1]
    if c == b"i":
        k = b.index(b"e", i)
        return int(b[i + 1:k]), k + 1
    if c == b"l":
        i, izid = i + 1, []
        while b[i:i + 1] != b"e":
            v, i = _bdekodiraj(b, i)
            izid.append(v)
        return izid, i + 1
    if c == b"d":
        i, izid = i + 1, {}
        while b[i:i + 1] != b"e":
            k, i = _bdekodiraj(b, i)
            v, i = _bdekodiraj(b, i)
            izid[k] = v
        return izid, i + 1
    d = b.index(b":", i)
    n = int(b[i:d])
    return b[d + 1:d + 1 + n], d + 1 + n


def ze_preneseno(hash_: str, indeks: Optional[int], mape_stanja=None) -> Tuple[str, int]:
    """Nadzornik: pot do datoteke `indeks` torrenta `hash_`, ce jo je rqbit na tem racunalniku ze v celoti
    prenesel (Safeer OS ali pomoc napravam), sicer "". indeks None = najvecji video. Vrne (pot, indeks). Odloca bitno polje kosov (<hash>.bitv), ne velikost
    datoteke - rqbit datoteko vnaprej razsiri, zato velikost sama ne pove, da je prenos koncan."""
    from core import os_torrent
    if not re.fullmatch(r"[0-9a-fA-F]{40}", hash_ or ""):
        return "", -1
    hash_ = hash_.lower()
    if mape_stanja is None:
        osnova = os.path.dirname(os_torrent.mapa_stanja())
        mape_stanja = [os_torrent.mapa_stanja(), os.path.join(osnova, "stanje-naprave")]
    for mapa in mape_stanja:
        try:
            with open(os.path.join(mapa, "session.json"), encoding="utf-8") as d:
                seja = json.load(d)
            izhod = next((str(t.get("output_folder") or "") for t in (seja.get("torrents") or {}).values()
                          if str(t.get("info_hash") or "").lower() == hash_), "")
            if not izhod:
                continue
            with open(os.path.join(mapa, hash_ + ".torrent"), "rb") as d:
                meta, _ = _bdekodiraj(d.read())
            info = meta[b"info"]
            dolzina_kosa = int(info[b"piece length"])
            if b"files" in info:
                datoteke = [(int(f[b"length"]), [x.decode("utf-8", "replace") for x in f[b"path"]]) for f in info[b"files"]]
            else:
                datoteke = [(int(info[b"length"]), [info[b"name"].decode("utf-8", "replace")])]
            if indeks is None:
                videi = [k for k, (_, deli) in enumerate(datoteke) if os_torrent.vrsta_datoteke(deli[-1]) == "video"]
                if not videi:
                    continue
                izbran = max(videi, key=lambda k: datoteke[k][0])
            else:
                izbran = int(indeks)
            if not 0 <= izbran < len(datoteke):
                continue
            zacetek = sum(d for d, _ in datoteke[:izbran])
            dolzina, deli = datoteke[izbran]
            if dolzina <= 0 or any(x in ("", ".", "..") or "/" in x or "\\" in x for x in deli):
                continue
            with open(os.path.join(mapa, hash_ + ".bitv"), "rb") as d:
                biti = d.read()
            prvi, zadnji = zacetek // dolzina_kosa, (zacetek + dolzina - 1) // dolzina_kosa
            if zadnji // 8 >= len(biti) or not all(biti[k // 8] & (0x80 >> (k % 8)) for k in range(prvi, zadnji + 1)):
                continue
            pot = os.path.join(izhod, *deli)
            if os.path.isfile(pot) and os.path.getsize(pot) == dolzina:
                return pot, izbran
        except (OSError, ValueError, KeyError, TypeError, StopIteration):
            continue
    return "", -1


#: Meje, nad katerimi racunalnik ne prevzame novega dela za druge naprave (ostane odziven za uporabnika).
NAJVEC_OBREMENITVE_NA_JEDRO = 0.85
NAJMANJ_PROSTEGA_RAM = 512 * 1024 * 1024
#: Pomoc drugim napravam (pretvorba, sprotno) vzame prostor samo, ce ostane toliko (svoje ime: prej REZERVA_DISKA, isto
#: ime kot rezerva popravkov Teamworka zgoraj, ki jo je povozilo).
REZERVA_DISKA_POMOCI = 2 * 1024 * 1024 * 1024


def prosti_pomnilnik() -> int:
    """Prosti pomnilnik v bajtih ali -1, ce ga sistem ne pove (Linux: MemAvailable, Windows: GlobalMemoryStatusEx).
    Brez podatka raje pomagamo, kot zavrnemo. Isto merjenje kot meje Safeer Linka (core/pomnilnik.na_voljo)."""
    from core import pomnilnik
    return pomnilnik.na_voljo()


def prosta_zmogljivost(mapa: str, potrebno: int, procesor: bool = True) -> str:
    """"" ce racunalnik delo zmore brez preobremenitve, sicer kratek razlog (preobremenjen, malo_pomnilnika,
    ni_prostora). Disk: velikost datoteke + rezerva, da uporabniku nikoli ne zapolnimo diska.
    `procesor=False` preskoci obremenitev procesorja (delo, ki ga ne potrebuje: pretakanje torrenta)."""
    try:
        jedra = os.cpu_count() or 1
        if procesor and os.getloadavg()[0] / jedra > NAJVEC_OBREMENITVE_NA_JEDRO:
            return "preobremenjen"
    except (OSError, AttributeError):
        pass
    pomnilnik = prosti_pomnilnik()
    if 0 <= pomnilnik < NAJMANJ_PROSTEGA_RAM:
        return "malo_pomnilnika"
    try:
        os.makedirs(mapa, exist_ok=True)
        # shutil.disk_usage dela na Linuxu in na Windows (os.statvfs na Windows ne obstaja - brez tega bi
        # racunalnik z Windows sprejel film, ki nanj ne gre, in zapolnil disk).
        if shutil.disk_usage(mapa).free < potrebno + REZERVA_DISKA_POMOCI:
            return "ni_prostora"
    except OSError:
        pass
    return ""


def zmogljivost_za_tok(mapa: str, potrebno: int) -> str:
    """Zmogljivost za pretakanje torrenta napravi: samo pomnilnik in disk, procesor ni pogoj."""
    return prosta_zmogljivost(mapa, potrebno, procesor=False)


# Samodejno ciscenje prenosov za naprave: po toliko casu brez predvajanja torrent in njegove datoteke izginejo
# (lastnik 25. 10. 2026: 12 ur po zadnjem predvajanju na vseh napravah - prej 48 ur).
RABA_VELJA_S = 12 * 3600
# Ob pomanjkanju prostora odstranimo tudi mlajse, a ne tistih, ki jih je kdo predvajal v zadnjih urah (film se tece).
RABA_V_TEKU_S = 6 * 3600
_RABA_ZAKLEP = threading.Lock()


def privzeta_pot_rabe() -> str:
    from core import os_torrent
    return os.path.join(os.path.dirname(os_torrent.mapa_stanja()), "raba-naprave.json")


def _pot_rabe_za(torrenti) -> str:
    """Zapis o rabi stoji ob mapi stanja torrentov za naprave; brez nje (preizkus z nadomestkom) ga ni."""
    stanje = str(getattr(torrenti, "mapa_stanja", "") or "")
    return os.path.join(os.path.dirname(stanje), "raba-naprave.json") if stanje else ""


def _beri_rabo(pot: str) -> dict:
    try:
        with open(pot, encoding="utf-8") as d:
            raba = json.load(d)
        return {str(k).lower(): float(v) for k, v in raba.items()} if isinstance(raba, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _pisi_rabo(pot: str, raba: dict) -> None:
    try:
        os.makedirs(os.path.dirname(pot), exist_ok=True)
        zacasna = pot + ".tmp"
        with open(zacasna, "w", encoding="utf-8") as d:
            json.dump(raba, d)
        os.replace(zacasna, pot)
    except OSError:
        pass


def zabelezi_rabo(hash_: str, pot: Optional[str] = None, zdaj: Optional[float] = None) -> None:
    """Naprava je torrent pravkar zahtevala (magnet.stream): od zdaj tece rok do samodejne odstranitve."""
    if not pot or not re.fullmatch(r"[0-9a-fA-F]{40}", hash_ or ""):
        return
    with _RABA_ZAKLEP:
        raba = _beri_rabo(pot)
        raba[hash_.lower()] = float(time.time() if zdaj is None else zdaj)
        _pisi_rabo(pot, raba)


def _hash_torrenta(torrenti, t: dict) -> str:
    h = str(t.get("hash") or "").lower()
    if re.fullmatch(r"[0-9a-f]{40}", h):
        return h
    try:
        m = re.search(r"btih:([0-9a-fA-F]{40})", torrenti.magnet(int(t["id"])) or "")
    except Exception:  # noqa: BLE001
        m = None
    return m.group(1).lower() if m else ""


def v_seji_motorja(torrenti, hash_: str) -> bool:
    """Ali ima motor torrent v svojem shranjenem stanju (session.json), tudi ce ga (se) ne nasteje: takoj po zagonu
    motor stanje se bere (pocasen disk). Dokler je torrent v seji, njegovega zapisa ne zavrzemo."""
    mapa = str(getattr(torrenti, "mapa_stanja", "") or "")
    if not mapa or not hash_:
        return False
    try:
        with open(os.path.join(mapa, "session.json"), encoding="utf-8") as d:
            seja = json.load(d)
        return any(str(t.get("info_hash") or "").lower() == str(hash_).lower() for t in (seja.get("torrents") or {}).values())
    except (OSError, ValueError, AttributeError):
        return False


def pocisti_neuporabljene(torrenti, pot: Optional[str] = None, zdaj: Optional[float] = None,
                          dovolj=None, obdrzi: str = "") -> List[str]:
    """Odstrani prenose za naprave (torrent in datoteke), ki jih [RABA_VELJA_S] nihce ni predvajal. Vrne njihove hashe.

    `dovolj` (klic brez argumentov -> bool): prostora zmanjkuje - dokler ne vrne True, gredo tudi mlajsi prenosi,
    najdlje neuporabljeni prvi, a ne tisti, ki jih je kdo predvajal v zadnjih [RABA_V_TEKU_S], in ne `obdrzi`.
    Torrent, ki ga se ne poznamo (prenesen pred to razlicico), dobi rok od zdaj. Uporabnikovih datotek, ki jih deli
    (`lastna`), se ne dotikamo; rqbita samo zaradi ciscenja ne zaganjamo."""
    pot = pot or _pot_rabe_za(torrenti)
    if not pot:
        return []
    zdaj = float(time.time() if zdaj is None else zdaj)
    try:
        if not torrenti.tece():
            return []
        vsi = torrenti.seznam()
    except Exception:  # noqa: BLE001
        return []
    odstranjeni: List[str] = []
    # Kar je uporabnik oznacil z »Obdrži«, ne potece in ne gre niti ob pomanjkanju prostora.
    drzimo = obdrzani(_pot_opisov(pot))
    with _RABA_ZAKLEP:
        raba = _beri_rabo(pot)
        spremenjeno = False
        znani = []
        zivi_vsi = set()
        for t in vsi:
            h = _hash_torrenta(torrenti, t)
            if not h or t.get("lastna"):
                continue
            if h not in raba:
                raba[h] = zdaj
                spremenjeno = True
            zivi_vsi.add(h)
            if h in drzimo:
                continue
            znani.append((raba[h], h, t))

        def odstrani(h: str, t: dict) -> bool:
            try:
                ok = bool(torrenti.odstrani(int(t["id"]), z_datotekami=True))
            except Exception:  # noqa: BLE001
                ok = False
            if ok:
                raba.pop(h, None)
                odstranjeni.append(h)
            return ok

        for cas, h, t in sorted(znani):
            if h != obdrzi.lower() and zdaj - cas > RABA_VELJA_S:
                spremenjeno = odstrani(h, t) or spremenjeno
        if dovolj is not None:
            for cas, h, t in sorted(znani):
                if dovolj():
                    break
                if h in odstranjeni or h == obdrzi.lower() or zdaj - cas < RABA_V_TEKU_S:
                    continue
                spremenjeno = odstrani(h, t) or spremenjeno
        # Zapisi o torrentih, ki jih ni vec (uporabnik jih je odstranil sam), ne ostajajo.
        zivi = zivi_vsi - set(odstranjeni)
        for h in [h for h in raba if h not in zivi and h != obdrzi.lower()]:
            if zdaj - raba[h] > RABA_VELJA_S and not v_seji_motorja(torrenti, h):
                raba.pop(h)
                spremenjeno = True
        if spremenjeno:
            _pisi_rabo(pot, raba)
    return odstranjeni


_CISCENJE_TECE = False


def zazeni_ciscenje(razmik_s: float = 3 * 3600, zamik_s: float = 180) -> None:
    """Control: prenose za naprave pregleda kmalu po zagonu in nato vsake tri ure. Ce je rqbit ugasnjen in ima
    shranjene prenose, ga za pregled prizge in potem spet ugasne (ne ostane v ozadju samo zaradi ciscenja).
    Hisno opravilo ure storitev (core/storitve_na_zahtevo) namesto niti, ki je ves dan spala."""
    global _CISCENJE_TECE
    if _CISCENJE_TECE:
        return
    _CISCENJE_TECE = True

    def delo() -> None:
        t = torrenti_za_naprave()
        tekel = t.tece()
        if not tekel:
            t.seznam()      # zazene rqbit le, ce ima shranjeno stanje
        odstranjeni = pocisti_neuporabljene(t)
        if odstranjeni:
            from core import os_stabilnost
            os_stabilnost.zapisi("safeer-control", f"prenosi za naprave: samodejno odstranjenih {len(odstranjeni)} (12 h brez predvajanja)")
        if not tekel and t.tece():
            t.ustavi_motor()
    from core import storitve_na_zahtevo
    storitve_na_zahtevo.opravilo("ciscenje_prenosov", delo, razmik_s, zamik_s)


_ZA_NAPRAVE = None
_ZA_NAPRAVE_ZAKLEP = threading.Lock()


def torrenti_za_naprave():
    """Lasten rqbit za pomoc napravam: svoja mapa stanja (ne deli in ne ustavlja tistega v Safeer OS)
    in svoja mapa Prejemi/Safeer/Za naprave, da je jasno, kaj je racunalnik prenesel za televizor."""
    global _ZA_NAPRAVE
    from core import os_torrent
    with _ZA_NAPRAVE_ZAKLEP:
        if _ZA_NAPRAVE is None:
            _ZA_NAPRAVE = os_torrent.Torrenti(os.path.join(os_torrent.mapa_prenosov(), "Za naprave"),
                                              os.path.join(os.path.dirname(os_torrent.mapa_stanja()), "stanje-naprave"),
                                              svoj_dht=True)
            # Ob izhodu Controla ustavimo tudi rqbit (sicer ostane do naslednjega zagona, ko ga pocisti _ustavi_sirote).
            import atexit
            atexit.register(_ZA_NAPRAVE.ustavi)
        return _ZA_NAPRAVE


# --- knjiznica kroga: kar je naprava povedala o filmu, ki ga je prosila ------------------------------------------------
#: Narocniki enega prenosa (naprave, ki jih obvestimo, ko je film nalozen): vse, ki so ga prosile - brez stevilske meje
#: (prej 16), vsaka naprava enkrat.


def opis_iz_parametrov(parametri) -> Optional[dict]:
    """Opis filma iz zahteve `magnet.stream` (title, poster, kind, ref, private) ali None, ce ga naprava ni poslala
    (starejsa razlicica). Zaseben naslov pride brez naslova in plakata: racunalnik ve samo, da ga drugim ne pokaze."""
    if not isinstance(parametri, dict):
        return None
    if parametri.get("private") is True:
        return {"private": True}
    naslov = str(parametri.get("title") or "").strip()[:200]
    if not naslov:
        return None
    plakat = str(parametri.get("poster") or "").strip()[:600]
    vrsta = str(parametri.get("kind") or "")
    return {"title": naslov, "poster": plakat if plakat.startswith("https://") else "",
            "kind": vrsta if vrsta in ("movie", "series") else "", "ref": str(parametri.get("ref") or "")[:400], "private": False}


def _pot_opisov(pot_rabe: Optional[str]) -> str:
    return os.path.join(os.path.dirname(pot_rabe), "opisi-naprave.json") if pot_rabe else ""


def _beri_opise(pot: str) -> dict:
    try:
        with open(pot, encoding="utf-8") as d:
            opisi = json.load(d)
        return {str(k).lower(): v for k, v in opisi.items() if isinstance(v, dict)} if isinstance(opisi, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def zabelezi_opis(hash_: str, opis: Optional[dict], id_naprave: str, pot_rabe: Optional[str]) -> None:
    """Zapomni si, kaj je naprava povedala o prenosu, in kdo ga je prosil. Kar je enkrat zasebno, ostane zasebno."""
    pot = _pot_opisov(pot_rabe)
    if not pot or not opis or not re.fullmatch(r"[0-9a-fA-F]{40}", hash_ or ""):
        return
    with _RABA_ZAKLEP:
        opisi = _beri_opise(pot)
        vnos = dict(opisi.get(hash_.lower()) or {})
        if opis.get("private") or vnos.get("private"):
            vnos = dict({"private": True, "narocniki": vnos.get("narocniki") or []}, **({"keep": True} if vnos.get("keep") else {}))
        else:
            for k in ("title", "poster", "kind", "ref"):
                if opis.get(k):
                    vnos[k] = opis[k]
            vnos["private"] = False
        narocniki = [n for n in (vnos.get("narocniki") or []) if isinstance(n, str) and n != id_naprave]
        if id_naprave:
            narocniki.append(str(id_naprave))
        vnos["narocniki"] = narocniki
        opisi[hash_.lower()] = vnos
        _pisi_rabo(pot, opisi)


def krajevni_naslov() -> str:
    """Naslov tega racunalnika v domacem omrezju (tisti, prek katerega pridemo do sredisca)."""
    for cilj in ("192.0.2.1", "10.255.255.255"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((cilj, 9))
                naslov = s.getsockname()[0]
            if naslov and not naslov.startswith("127."):
                return naslov
        except OSError:
            continue
    return "127.0.0.1"


def naslov_do_huba(hub_url: str) -> str:
    """Naslov tega racunalnika, kot ga vidi sredisce: vticnica proti hubu pove, kateri vmesnik je pravi."""
    try:
        u = urllib.parse.urlparse(hub_url)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:     # zaprta tudi, ce connect ne uspe
            s.connect((u.hostname or "127.0.0.1", u.port or 443))
            naslov = s.getsockname()[0]
        if naslov and not naslov.startswith("127."):
            return naslov
    except OSError:
        pass
    return krajevni_naslov()
