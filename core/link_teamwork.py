"""Teamwork: ista datoteka odprta na vec napravah hkrati - za vse programe, ne samo za enega.

Lastnik (14. 10. 2026): »Ce na obeh racunalnikih hkrati poteka urejanje enake datoteke, mora biti avtomatsko vkljucen
nacin Teamwork. Mora delovati v vseh napravah; tudi ce na Androidu zazenem datoteko, ki jo urejas na drugem
racunalniku, ne sme biti napake.« in »Kadar napravi nimata istega programa, se datoteka odpre v programu, ki ta format
podpira; ce ga ni, se odpre neposreden prenos programa z naprave, ki ima datoteko.«

Zasnova (splosna, brez znanja o programih):

  * Vir resnice je NAPRAVA, KI IMA DATOTEKO (lastnik). Druge naprave (udelezenci) urejajo delovno kopijo, ki jo je
    prinesel »Nadaljuj tukaj« (core/link_nadaljuj). Udelezenec lastniku vsakih nekaj sekund pove, ali je datoteka pri
    njem odprta (ukaz Linka `files.session`); odgovor pove trenutno razlicico in kdo jo se ureja.
  * Teamwork je vklopljen sam, ko datoteko ureja vec kot ena naprava (lastnik steje, ce jo ima odprto sam). Vse naprave
    dobijo obvestilo, kdo jo se ureja.
  * Odprtost zaznamo brez pomoci programa: naslov okna vsebuje ime datoteke (GIMP, PhotoCraft, LibreOffice, urejevalniki
    besedila ...), zaklepna datoteka LibreOffice ali proces, ki ima datoteko odprto.
  * Shranjevanje: ko program shrani delovno kopijo, udelezenec lastniku poslje samo kose, ki jih lastnik se nima
    (`POST /popravek/<id>`, core/link_delta - isti razrez kot pri prenosu), in razlicico, iz katere je program zacel
    (osnova). Lastnik razlicice steje.
  * Nicesar se ne izgubi (optimisticno usklajevanje): ce je medtem shranil nekdo drug (osnova ni vec trenutna), se
    zadnja shranitev NE zapise cez glavno datoteko, ampak ob njej kot »ime (naprava).koncnica«; vsi dobijo obvestilo.
    Ce program na lastniku shrani cez razlicico z druge naprave, ki je ni nalozil, ostane razlicica druge naprave
    ohranjena kot kopija (zgodovina razlicic pri lastniku).
  * Nova razlicica pride do udelezencev sama (prenos samo sprememb); ce je program odprt, obvestilo pove, naj datoteko
    znova odpre (splosnega nacina, da program sam naloži novo vsebino, ni).
  * Program: isti kot na napravi lastnika, ce je namescen; sicer program, ki format podpira; ce ga ni, se datoteka odpre
    na napravi lastnika in se pokaze njen zaslon (izberi_program).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import tempfile
import threading
import time
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from core import link_delta

#: Udelezenec z odprto datoteko javlja tako pogosto (obvestilo o novi razlicici pride najkasneje v tem casu).
PING_ODPRTO_S = 5.0
#: Zaprta datoteka, ki je bila v zadnjem dnevu odprta: redkeje (nova razlicica je pripravljena, ko jo spet odpres).
PING_SPREMLJAM_S = 60.0
SPREMLJAJ_S = 24 * 3600.0
#: Udelezenec brez javljanja toliko casa pri lastniku ne steje vec (naprava je izginila iz omrezja).
POTECE_S = 30.0
#: Datoteka mora toliko casa mirovati, preden jo posljemo: programi pisejo v vec korakih.
MIRUJE_S = 1.5
#: Najvecji popravek, ki ga lastnik sprejme (glava z opisom + manjkajoci kosi).
NAJVEC_POPRAVKA = 2 * 1024 * 1024 * 1024
NAJVEC_GLAVE = 48 * 1024 * 1024
#: Zgodovina razlicic pri lastniku: toliko zadnjih na datoteko, skupaj najvec toliko bajtov; vecje datoteke brez nje.
NAJVEC_VERZIJ = 10
NAJVEC_ZGODOVINE = 2 * 1024 * 1024 * 1024
NAJVEC_ZA_ZGODOVINO = 1024 * 1024 * 1024
#: Udelezbe, ki jih toliko casa ni nihce odprl, pozabimo (delovna kopija ostane, kjer je).
UDELEZBA_VELJA_S = 30 * 24 * 3600.0
#: Seja pri lastniku brez udelezencev toliko casa izgine.
SEJA_VELJA_S = 600.0
TIK_S = 2.0
#: Najvec toliko kopij ob sporu na sejo (ista vsebina se nikoli ne zapise dvakrat).
NAJVEC_KOPIJ = 20
#: Po trajni napaki (prevelika datoteka, ni prostora pri lastniku) udelezenec toliko casa ne posilja znova.
PREMOR_PO_NAPAKI_S = 300.0
MAGIJA = b"SFTW1\n"
#: Okna teh programov pokazejo ime mape, ne odprte datoteke (upravitelji datotek) - in nasa lastna.
NI_UREJEVALNIK = ("nemo", "nautilus", "thunar", "caja", "pcmanfm", "dolphin", "safeer", "plank", "cinnamon")

BESEDILA = {
    "sl": {
        "zacetek": ("Teamwork", "»{ime}« zdaj ureja tudi {kdo}."),
        "konec": ("Teamwork končan", "»{ime}« zdaj urejaš samo ti."),
        "nova": ("Nova različica", "{kdo} je shranil »{ime}«. Zapri in znova odpri datoteko, da vidiš spremembe."),
        "nova_zaprta": ("Nova različica", "{kdo} je shranil »{ime}«. Ko jo odpreš, imaš njegove spremembe."),
        "spor": ("Teamwork: obe različici sta ohranjeni", "{kdo} je shranil »{ime}« medtem ko si ga urejal ti. "
                 "Tvoja različica je shranjena kot »{kopija}«."),
        "spor_drugi": ("Teamwork: obe različici sta ohranjeni", "{kdo} je shranil »{ime}« iz starejše različice. "
                       "Njegova različica je shranjena kot »{kopija}«."),
        "spor_brez_kopije": ('Teamwork: različica ni ohranjena', 'Različice »{ime}« z naprave {kdo} ni bilo mogoče ohraniti kot kopije (ni je več v zgodovini).'),
        "tukaj": "ta računalnik",
    },
    "en": {
        "zacetek": ("Teamwork", "“{ime}” is now also being edited on {kdo}."),
        "konec": ("Teamwork ended", "Only you are editing “{ime}” now."),
        "nova": ("New version", "{kdo} saved “{ime}”. Close and reopen the file to see the changes."),
        "nova_zaprta": ("New version", "{kdo} saved “{ime}”. You'll have the changes when you open it."),
        "spor": ("Teamwork: both versions kept", "{kdo} saved “{ime}” while you were editing it. "
                 "Your version is saved as “{kopija}”."),
        "spor_drugi": ("Teamwork: both versions kept", "{kdo} saved “{ime}” from an older version. "
                       "Their version is saved as “{kopija}”."),
        "spor_brez_kopije": ('Teamwork: version not kept', 'The version of “{ime}” from {kdo} could not be kept as a copy (it is no longer in the history).'),
        "tukaj": "this computer",
    },
    "de": {
        "zacetek": ("Teamwork", "„{ime}“ wird jetzt auch auf {kdo} bearbeitet."),
        "konec": ("Teamwork beendet", "Nur du bearbeitest „{ime}“ jetzt."),
        "nova": ("Neue Version", "{kdo} hat „{ime}“ gespeichert. Schließe die Datei und öffne sie erneut, um die Änderungen zu sehen."),
        "nova_zaprta": ("Neue Version", "{kdo} hat „{ime}“ gespeichert. Beim Öffnen hast du die Änderungen."),
        "spor": ("Teamwork: beide Versionen behalten", "{kdo} hat „{ime}“ gespeichert, während du es bearbeitet hast. "
                 "Deine Version ist als „{kopija}“ gespeichert."),
        "spor_drugi": ("Teamwork: beide Versionen behalten", "{kdo} hat „{ime}“ aus einer älteren Version gespeichert. "
                       "Diese Version ist als „{kopija}“ gespeichert."),
        "spor_brez_kopije": ('Teamwork: Version nicht behalten', 'Die Version von „{ime}“ von {kdo} konnte nicht als Kopie behalten werden (nicht mehr im Verlauf).'),
        "tukaj": "diesem Computer",
    },
    "es": {
        "zacetek": ("Teamwork", "«{ime}» ahora también se edita en {kdo}."),
        "konec": ("Teamwork terminado", "Ahora solo tú editas «{ime}»."),
        "nova": ("Nueva versión", "{kdo} guardó «{ime}». Cierra y vuelve a abrir el archivo para ver los cambios."),
        "nova_zaprta": ("Nueva versión", "{kdo} guardó «{ime}». Al abrirlo tendrás sus cambios."),
        "spor": ("Teamwork: se conservan ambas versiones", "{kdo} guardó «{ime}» mientras lo editabas. "
                 "Tu versión se guardó como «{kopija}»."),
        "spor_drugi": ("Teamwork: se conservan ambas versiones", "{kdo} guardó «{ime}» desde una versión anterior. "
                       "Su versión se guardó como «{kopija}»."),
        "spor_brez_kopije": ('Teamwork: versión no conservada', 'La versión de «{ime}» de {kdo} no se pudo conservar como copia (ya no está en el historial).'),
        "tukaj": "este ordenador",
    },
    "fr": {
        "zacetek": ("Teamwork", "« {ime} » est maintenant aussi modifié sur {kdo}."),
        "konec": ("Teamwork terminé", "Tu es maintenant seul à modifier « {ime} »."),
        "nova": ("Nouvelle version", "{kdo} a enregistré « {ime} ». Ferme puis rouvre le fichier pour voir les modifications."),
        "nova_zaprta": ("Nouvelle version", "{kdo} a enregistré « {ime} ». Tu auras ses modifications à l'ouverture."),
        "spor": ("Teamwork : les deux versions sont conservées", "{kdo} a enregistré « {ime} » pendant que tu le modifiais. "
                 "Ta version est enregistrée sous « {kopija} »."),
        "spor_drugi": ("Teamwork : les deux versions sont conservées", "{kdo} a enregistré « {ime} » depuis une version "
                       "plus ancienne. Sa version est enregistrée sous « {kopija} »."),
        "spor_brez_kopije": ('Teamwork : version non conservée', "La version de « {ime} » de {kdo} n'a pas pu être conservée en copie (elle n'est plus dans l'historique)."),
        "tukaj": "cet ordinateur",
    },
    "it": {
        "zacetek": ("Teamwork", "«{ime}» ora è modificato anche su {kdo}."),
        "konec": ("Teamwork terminato", "Ora solo tu stai modificando «{ime}»."),
        "nova": ("Nuova versione", "{kdo} ha salvato «{ime}». Chiudi e riapri il file per vedere le modifiche."),
        "nova_zaprta": ("Nuova versione", "{kdo} ha salvato «{ime}». Quando lo apri avrai le sue modifiche."),
        "spor": ("Teamwork: entrambe le versioni conservate", "{kdo} ha salvato «{ime}» mentre lo modificavi. "
                 "La tua versione è salvata come «{kopija}»."),
        "spor_drugi": ("Teamwork: entrambe le versioni conservate", "{kdo} ha salvato «{ime}» da una versione precedente. "
                       "La sua versione è salvata come «{kopija}»."),
        "spor_brez_kopije": ('Teamwork: versione non conservata', 'La versione di «{ime}» da {kdo} non è stata conservata come copia (non è più nella cronologia).'),
        "tukaj": "questo computer",
    },
}


def besedilo(jezik: str, koda: str, **p) -> Tuple[str, str]:
    """(naslov, besedilo) obvestila v jeziku uporabnika (angleščina, ce jezika ni)."""
    b = BESEDILA.get(str(jezik or "")[:2]) or BESEDILA["en"]
    naslov, telo = b.get(koda) or BESEDILA["en"][koda]
    return naslov, telo.format(**{k: str(v) for k, v in p.items()})


def _sha(pot: str) -> str:
    h = hashlib.sha256()
    with open(pot, "rb") as d:
        for blok in iter(lambda: d.read(1024 * 1024), b""):
            h.update(blok)
    return h.hexdigest()


def _stat(pot: str) -> Optional[Tuple[int, int, int]]:
    try:
        s = os.stat(pot)
        return (s.st_size, s.st_mtime_ns, s.st_ino)
    except OSError:
        return None


def _kljuc(*deli: str) -> str:
    return hashlib.sha256("\n".join(deli).encode("utf-8")).hexdigest()[:32]


def privzeta_mapa() -> str:
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "safeer", "teamwork")


def kratko_ime(ime: str) -> str:
    """»Safeer OS (OnePlus)« -> »OnePlus«, »Safeer Control (ime-racunalnika)« -> »ime-racunalnika«; drugo ostane."""
    m = re.fullmatch(r"\s*Safeer [^()]*\((.+)\)\s*", str(ime or ""))
    return m.group(1).strip() if m else str(ime or "").strip()


def ime_kopije(pot: str, kdo: str) -> str:
    """Prosto ime ob datoteki: »ime (kdo).koncnica«, »ime (kdo 2).koncnica« ..."""
    mapa, ime = os.path.split(pot)
    osnova, konc = os.path.splitext(ime)
    kdo = re.sub(r"[\x00-\x1f/\\:()]", "", kratko_ime(kdo)).strip()[:60] or "Teamwork"
    for i in range(1, 1000):
        kandidat = os.path.join(mapa, "%s (%s%s)%s" % (osnova, kdo, "" if i == 1 else " %d" % i, konc))
        if not os.path.lexists(kandidat):
            return kandidat
    return os.path.join(mapa, "%s (%s %d)%s" % (osnova, kdo, int(time.time()), konc))


# ------------------------------------------------------------------ ali je datoteka odprta

def _normaliziraj(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").lower()).strip()


def program_okna(pot: str, okna: Iterable[dict]) -> Optional[str]:
    """Razred programa, katerega okno ima v naslovu ime te datoteke (ali ime brez koncnice kot samostojno besedo),
    ali None. Upravitelji datotek in nasa okna ne stejejo (pokazejo ime mape, ne odprte datoteke)."""
    ime = _normaliziraj(os.path.basename(pot))
    osnova = _normaliziraj(os.path.splitext(os.path.basename(pot))[0])
    vzorec = re.compile(r"(^|[^\w])" + re.escape(osnova) + r"($|[^\w])") if len(osnova) >= 3 else None
    for o in okna or ():
        program = str(o.get("program") or "")
        if any(x in program.lower() for x in NI_UREJEVALNIK):
            continue
        naslov = _normaliziraj(o.get("ime") or "")
        if not naslov:
            continue
        if ime and ime in naslov:
            return program or "?"
        if vzorec is not None and vzorec.search(naslov):
            return program or "?"
    return None


def odprte_poti(najvec_procesov: int = 2000) -> set:
    """Poti datotek, ki jih imajo odprte procesi tega uporabnika (/proc/*/fd). V peskovniku Flatpak so vidni samo
    procesi peskovnika - takrat je dovolj naslov okna."""
    izid = set()
    uid = os.getuid()
    try:
        pidi = [p for p in os.listdir("/proc") if p.isdigit()][:najvec_procesov]
    except OSError:
        return izid
    for pid in pidi:
        mapa = "/proc/%s/fd" % pid
        try:
            if os.stat("/proc/" + pid).st_uid != uid:
                continue
            for fd in os.listdir(mapa):
                try:
                    cilj = os.readlink(os.path.join(mapa, fd))
                except OSError:
                    continue
                if cilj.startswith("/"):
                    izid.add(cilj)
        except OSError:
            continue
    return izid


def je_odprta(pot: str, okna: Iterable[dict], poti_procesov: Optional[set] = None) -> Optional[str]:
    """Program (razred okna ali opis), ki ima datoteko odprto, ali None."""
    if not pot:
        return None
    mapa, ime = os.path.split(pot)
    if os.path.exists(os.path.join(mapa, ".~lock." + ime + "#")):
        return "libreoffice"
    p = program_okna(pot, okna)
    if p is not None:
        return p
    if poti_procesov and os.path.realpath(pot) in poti_procesov:
        return "?"
    return None


def izberi_program(pot: str, razred: str, programi_za: Callable[[str], dict]) -> dict:
    """Kako odpreti datoteko na tej napravi: {"nacin": "isti"|"podprt"|"pretok", "program": id .desktop, "ime"}.

    isti   - program, s katerim jo ureja lastnik (razred okna), je namescen tudi tukaj;
    podprt - drug program, ki ta format odpre (privzeti za to vrsto, sicer prvi);
    pretok - tukaj ni nobenega: datoteka se odpre na napravi lastnika, tu se pokaze njen zaslon.
    `programi_za(pot)` je core/os_odpri_z.programi_za (Safeer OS; Control ga ne potrebuje)."""
    try:
        r = programi_za(pot) or {}
    except Exception:  # noqa: BLE001 - brez seznama programov ostane privzeto odpiranje
        r = {}
    programi = [p for p in (r.get("programi") or []) if isinstance(p, dict) and p.get("id")]
    if not programi:
        return {"nacin": "pretok", "program": "", "ime": ""}
    kljuc = re.sub(r"[^a-z0-9]", "", str(razred or "").lower())
    kljuc = re.sub(r"\d+$", "", kljuc)          # »gimp-2.10« -> gimp
    if len(kljuc) >= 3:
        for p in programi:
            if kljuc in re.sub(r"[^a-z0-9]", "", (str(p.get("id")) + str(p.get("ime") or "")).lower()):
                return {"nacin": "isti", "program": str(p["id"]), "ime": str(p.get("ime") or "")}
    izbran = next((p for p in programi if p.get("privzet")), programi[0])
    return {"nacin": "podprt", "program": str(izbran["id"]), "ime": str(izbran.get("ime") or "")}


# ------------------------------------------------------------------ popravek (samo spremenjeni kosi)

def naredi_popravek(pot: str, opis_lastnika: Optional[dict], osnova: str, izhod: str) -> dict:
    """Zapise popravek v `izhod`: MAGIJA, dolzina glave (4 B), glava JSON {opis, osnova, obsegi}, nato bajti obsegov
    nove datoteke, ki jih lastnik po svojem opisu nima. Razrez s povprecjem lastnikovega opisa (sicer se kosi ne
    ujemajo). Vrne {opis, podatki (bajti kosov), velikost, dolzina (vse telo)}."""
    pred = _stat(pot)
    if opis_lastnika is not None and link_delta.preveri_manifest(opis_lastnika):
        opis = link_delta.manifest(pot, povprecno=link_delta.povprecno_opisa(opis_lastnika))
        znani = {k[2] for k in opis_lastnika["kosi"]}
    else:
        opis = link_delta.manifest(pot)
        znani = set()
    manjkajoci = [(int(k[0]), int(k[1])) for k in opis["kosi"] if k[2] not in znani]
    obsegi = link_delta.zdruzi_obsege(manjkajoci, najvec=1 << 62)
    glava = json.dumps({"opis": opis, "osnova": str(osnova or ""), "obsegi": obsegi}, separators=(",", ":")).encode("utf-8")
    podatki = 0
    with open(izhod, "wb") as f, open(pot, "rb") as v:
        f.write(MAGIJA + struct.pack(">I", len(glava)) + glava)
        for odmik, dolzina in obsegi:
            v.seek(odmik)
            ostane = dolzina
            while ostane > 0:
                blok = v.read(min(ostane, 1024 * 1024))
                if not blok:
                    raise link_delta.NapakaDelte("datoteka_se_spreminja")
                f.write(blok)
                ostane -= len(blok)
            podatki += dolzina
    if _stat(pot) != pred:
        raise link_delta.NapakaDelte("datoteka_se_spreminja")
    return {"opis": opis, "podatki": podatki, "velikost": int(opis["velikost"]), "dolzina": os.path.getsize(izhod)}


def preberi_glavo(pot_telesa: str) -> Tuple[dict, int]:
    """(glava, odmik podatkov) ali NapakaDelte. Preveri obliko, opis in obsege (urejeni, brez prekrivanja, znotraj
    datoteke, skupaj natanko toliko bajtov, kot jih je v telesu)."""
    velikost = os.path.getsize(pot_telesa)
    with open(pot_telesa, "rb") as t:
        if t.read(len(MAGIJA)) != MAGIJA:
            raise link_delta.NapakaDelte("ni_popravek")
        n = struct.unpack(">I", t.read(4) or b"\0\0\0\0")[0]
        if n <= 0 or n > NAJVEC_GLAVE:
            raise link_delta.NapakaDelte("napacna_glava")
        try:
            glava = json.loads(t.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise link_delta.NapakaDelte("napacna_glava") from None
        zacetek = t.tell()
    if not isinstance(glava, dict):
        raise link_delta.NapakaDelte("napacna_glava")
    if glava.get("celota") is True:
        # Naprava brez razreza po vsebini (Android): cela datoteka z vrednostjo sha256 - preveri jo uporabi_popravek.
        try:
            vel = int(glava.get("velikost"))
        except (TypeError, ValueError):
            raise link_delta.NapakaDelte("napacna_glava") from None
        if not link_delta._hex64(glava.get("sha256")) or vel < 0 or zacetek + vel != velikost:
            raise link_delta.NapakaDelte("napacna_dolzina")
        glava["opis"] = {"v": 1, "velikost": vel, "sha256": glava["sha256"], "kosi": []}
        glava["obsegi"] = [(0, vel)] if vel else []
        return glava, zacetek
    if not link_delta.preveri_manifest(glava.get("opis")):
        raise link_delta.NapakaDelte("napacen_opis")
    vel = int(glava["opis"]["velikost"])
    skupaj, konec = 0, 0
    try:
        obsegi = [(int(a), int(b)) for a, b in glava.get("obsegi") or []]
    except (TypeError, ValueError):
        raise link_delta.NapakaDelte("napacni_obsegi") from None
    for odmik, dolzina in obsegi:
        if odmik < konec or dolzina <= 0 or odmik + dolzina > vel:
            raise link_delta.NapakaDelte("napacni_obsegi")
        konec = odmik + dolzina
        skupaj += dolzina
    if zacetek + skupaj != velikost:
        raise link_delta.NapakaDelte("napacna_dolzina")
    glava["obsegi"] = obsegi
    return glava, zacetek


def uporabi_popravek(pot_telesa: str, lokalni: List[str], cilj: str) -> Tuple[dict, dict]:
    """Iz popravka in lokalnih virov (trenutna datoteka, zgodovina) sestavi novo datoteko v `cilj`. Kos, ki ga ni ne v
    popravku ne v lokalnih virih -> NapakaDelte (udelezenec poskusi znova z novim opisom). Vrne (glava, meritve)."""
    glava, zacetek = preberi_glavo(pot_telesa)
    if glava.get("celota") is True:
        return glava, _cela(pot_telesa, zacetek, glava, cilj)
    kazalo = []                                    # (odmik v novi datoteki, dolzina, odmik v telesu)
    pos = zacetek
    for odmik, dolzina in glava["obsegi"]:
        kazalo.append((odmik, dolzina, pos))
        pos += dolzina
    telo = open(pot_telesa, "rb")

    def obseg(odmik: int, dolzina: int) -> bytes:
        deli = []
        trenutni, ostane = odmik, dolzina
        for o, d, p in kazalo:
            if ostane <= 0:
                break
            if o + d <= trenutni:
                continue
            if o > trenutni:
                break
            zamik = trenutni - o
            koliko = min(d - zamik, ostane)
            telo.seek(p + zamik)
            deli.append(telo.read(koliko))
            trenutni += koliko
            ostane -= koliko
        if ostane > 0:
            raise link_delta.NapakaDelte("manjka_v_popravku")
        return b"".join(deli)

    try:
        meritve = link_delta.sestavi(glava["opis"], [p for p in lokalni if p and os.path.isfile(p)], obseg, cilj,
                                     polno_ob_napaki=False)
    finally:
        telo.close()
    return glava, meritve


def _cela(pot_telesa: str, zacetek: int, glava: dict, cilj: str) -> dict:
    """Cela datoteka iz popravka »celota«: prepise jo v cilj in preveri sha256 (sicer NapakaDelte, cilja ni)."""
    meritve = link_delta.nove_meritve()
    h = hashlib.sha256()
    zacasna = cilj + ".part"
    try:
        with open(pot_telesa, "rb") as t, open(zacasna, "wb") as f:
            t.seek(zacetek)
            for blok in iter(lambda: t.read(1024 * 1024), b""):
                h.update(blok)
                f.write(blok)
        if h.hexdigest() != glava["sha256"]:
            raise link_delta.NapakaDelte("celota_se_ne_ujema")
        os.replace(zacasna, cilj)
    finally:
        _odstrani(zacasna)
    meritve.update(velikost=int(glava["velikost"]), podatki=int(glava["velikost"]), polno=True, razlog="celota")
    return meritve


# ------------------------------------------------------------------ zgodovina razlicic pri lastniku

class Zgodovina:
    """Zadnje razlicice datotek, ki jih ureja vec naprav (lastnik). Brez nje bi shranitev programa na lastniku
    nepreklicno prepisala razlicico, ki jo je pravkar poslala druga naprava."""

    def __init__(self, mapa: str) -> None:
        self.mapa = mapa
        #: Razlicice, ki jih seje se potrebujejo (trenutne): ciscenje jih ne odstrani.
        self.ohrani: Callable[[], set] = lambda: set()

    def _mapa(self, kljuc: str) -> str:
        return os.path.join(self.mapa, "verzije", kljuc)

    def pot(self, kljuc: str, sha: str) -> str:
        p = os.path.join(self._mapa(kljuc), sha)
        return p if sha and os.path.isfile(p) else ""

    def poti(self, kljuc: str) -> List[str]:
        try:
            m = self._mapa(kljuc)
            return [os.path.join(m, x) for x in os.listdir(m) if re.fullmatch(r"[0-9a-f]{64}", x)]
        except OSError:
            return []

    def shrani(self, kljuc: str, sha: str, vir: str) -> str:
        """Kopija vsebine `vir` (z vrednostjo sha) - ce je ze ni in datoteka ni prevelika. Vrne pot ali ""."""
        if not sha or self.pot(kljuc, sha):
            return self.pot(kljuc, sha)
        try:
            if os.path.getsize(vir) > NAJVEC_ZA_ZGODOVINO:
                return ""
            m = self._mapa(kljuc)
            os.makedirs(m, exist_ok=True)
            fd, zac = tempfile.mkstemp(prefix=".", dir=m)
            with os.fdopen(fd, "wb") as f, open(vir, "rb") as v:
                shutil.copyfileobj(v, f, 1024 * 1024)
            os.replace(zac, os.path.join(m, sha))
            os.utime(os.path.join(m, sha))
        except OSError:
            return ""
        self.pocisti(kljuc)
        return self.pot(kljuc, sha)

    def prevzemi(self, kljuc: str, sha: str, vir: str) -> str:
        """Kot shrani, a `vir` (zacasna datoteka) premakne namesto kopiranja."""
        if self.pot(kljuc, sha):
            os.remove(vir)
            return self.pot(kljuc, sha)
        m = self._mapa(kljuc)
        os.makedirs(m, exist_ok=True)
        os.replace(vir, os.path.join(m, sha))
        self.pocisti(kljuc)
        return self.pot(kljuc, sha)

    def pocisti(self, kljuc: str, ohrani: Iterable[str] = ()) -> None:
        ohrani = set(ohrani)
        try:
            ohrani |= set(self.ohrani())
        except Exception:  # noqa: BLE001
            pass
        verzije = sorted(self.poti(kljuc), key=lambda p: os.path.getmtime(p), reverse=True)
        for p in verzije[NAJVEC_VERZIJ:]:
            if os.path.basename(p) not in ohrani:
                try:
                    os.remove(p)
                except OSError:
                    pass
        # Skupna meja: najstarejse razlicice vseh datotek gredo prve.
        vse = []
        try:
            for k in os.listdir(os.path.join(self.mapa, "verzije")):
                vse.extend(self.poti(k))
        except OSError:
            return
        vse.sort(key=lambda p: os.path.getmtime(p))
        skupaj = sum(os.path.getsize(p) for p in vse)
        for p in vse:
            if skupaj <= NAJVEC_ZGODOVINE:
                break
            if os.path.basename(p) in ohrani:
                continue
            skupaj -= os.path.getsize(p)
            try:
                os.remove(p)
            except OSError:
                pass


# ------------------------------------------------------------------ stanje

class _Seja:
    """Datoteka TE naprave, ki jo ureja vsaj ena druga naprava."""

    def __init__(self, oznaka: str, pot: str) -> None:
        self.oznaka = oznaka
        self.pot = pot
        self.kljuc = _kljuc("lastnik", os.path.realpath(pot))
        self.sha = ""
        self.stat: Optional[tuple] = None
        self.verzija = 1
        self.udelezenci: Dict[str, dict] = {}       # id naprave -> {ime, program, odprto, cas}
        self.lokalno = {"odprto": False, "program": "", "osnova": ""}
        self.zadnji = {"naprava": "", "ime": "", "cas": 0.0}
        self.spori: List[dict] = []                 # {kopija, naprava (cigava razlicica), kdo (kdo je shranil cez)}
        self.kopije: Dict[str, str] = {}            # sha vsebine -> ime kopije (ista vsebina samo enkrat)
        self.teamwork = False
        self.spremenjeno_od: Optional[Tuple[tuple, float]] = None
        self.zaklep = threading.RLock()
        self.zadnja_raba = time.time()


class _Udelezba:
    """Delovna kopija datoteke z druge naprave na TEJ napravi."""

    def __init__(self, podatki: dict) -> None:
        self.naprava = str(podatki.get("naprava") or "")
        self.ime_naprave = str(podatki.get("ime_naprave") or "")
        self.oznaka = str(podatki.get("oznaka") or "")
        self.pot_imen = [str(x) for x in podatki.get("pot_imen") or []][:32]
        self.pot = str(podatki.get("pot") or "")
        self.sha = str(podatki.get("sha") or "")
        st = podatki.get("stat")
        self.stat: Optional[tuple] = tuple(st) if isinstance(st, list) else None
        self.osnova = str(podatki.get("osnova") or self.sha)
        self.zadnja_raba = float(podatki.get("zadnja_raba") or time.time())
        self.streznik: Optional[dict] = podatki.get("streznik") if isinstance(podatki.get("streznik"), dict) else None
        self.odprto = False
        self.program = ""
        self.naslednji_ping = 0.0
        self.teamwork = False
        self.drugi: List[str] = []
        self.spremenjeno_od: Optional[Tuple[tuple, float]] = None
        self.podprto = True
        self.videni_spori: Optional[set] = None
        self.poslano_spor = ""                      # kopija, o kateri je obvestil ze odgovor na popravek
        self.premor_do = 0.0                        # po trajni napaki lastnika do takrat ne posiljamo
        self.zaklep = threading.Lock()

    @property
    def kljuc(self) -> str:
        return _kljuc(self.naprava, self.oznaka)

    def zapis(self) -> dict:
        return {"naprava": self.naprava, "ime_naprave": self.ime_naprave, "oznaka": self.oznaka, "pot_imen": self.pot_imen,
                "pot": self.pot, "sha": self.sha, "stat": list(self.stat) if self.stat else None, "osnova": self.osnova,
                "zadnja_raba": self.zadnja_raba}


class Teamwork:
    """Obe vlogi na eni napravi: lastnik (seje datotek te naprave) in udelezenec (delovne kopije z drugih naprav).

    Odvisnosti so podane (Safeer Control jih poveze, preizkusi jih zamenjajo):
      razresi(oznaka) -> pot datoteke, ki jo naprava sme videti, ali ""
      ime_naprave(id) -> ime v Linku
      obvesti(koda, podatki) -> obvestilo uporabniku (besedilo() v jeziku uporabnika)
      ukaz(id, dejanje, parametri) -> odgovor naprave {ok, data, koda}
      okna() -> [{ime: naslov, program: razred}] odprtih oken
      prenesi(udelezba) -> dict: nova razlicica z naprave lastnika v delovno kopijo (link_nadaljuj)
      poslji(udelezba, pot_telesa, dolzina) -> (koda HTTP, odgovor) popravka lastniku
      opis_lastnika(udelezba) -> opis kosov datoteke pri lastniku ali None
      usklajeno(udelezba) -> delovna kopija je enaka razlicici pri lastniku (zapis link_nadaljuj, brez Smeti ob prenosu)
    """

    def __init__(self, razresi: Callable[[str], str], ime_naprave: Callable[[str], str],
                 obvesti: Callable[[str, dict], None], ukaz: Callable[[str, str, dict], dict],
                 okna: Callable[[], List[dict]], prenesi: Optional[Callable] = None, poslji: Optional[Callable] = None,
                 opis_lastnika: Optional[Callable] = None, usklajeno: Optional[Callable] = None,
                 mapa: Optional[str] = None,
                 procesi: Optional[Callable[[], set]] = odprte_poti, zdaj: Callable[[], float] = time.time) -> None:
        self.razresi = razresi
        self.ime_naprave = ime_naprave
        self.obvesti = obvesti
        self.ukaz = ukaz
        self.okna = okna
        self.prenesi = prenesi
        self.poslji = poslji
        self.opis_lastnika = opis_lastnika
        self.usklajeno = usklajeno
        self.procesi = procesi
        self.zdaj = zdaj
        self.mapa = mapa or privzeta_mapa()
        self.zgodovina = Zgodovina(self.mapa)
        self.zgodovina.ohrani = lambda: {x.sha for x in list(self._seje.values())}
        self._seje: Dict[str, _Seja] = {}
        self._udelezbe: Dict[str, _Udelezba] = {}
        self._zaklep = threading.RLock()
        self._nit: Optional[threading.Thread] = None
        self._ustavi = threading.Event()
        self._tik_st = 0
        self._nalozi()

    # -------------------------------------------------------------- shramba udelezb (brez zetonov)
    def _pot_zapisa(self) -> str:
        return os.path.join(self.mapa, "udelezbe.json")

    def _nalozi(self) -> None:
        try:
            with open(self._pot_zapisa(), encoding="utf-8") as d:
                vnosi = json.load(d)
        except (OSError, ValueError):
            return
        zdaj = self.zdaj()
        for v in vnosi if isinstance(vnosi, list) else []:
            if not isinstance(v, dict):
                continue
            u = _Udelezba(v)
            if u.naprava and u.oznaka and u.pot and zdaj - u.zadnja_raba < UDELEZBA_VELJA_S and os.path.isfile(u.pot):
                self._udelezbe[u.kljuc] = u

    def _shrani(self) -> None:
        with self._zaklep:
            vnosi = [u.zapis() for u in self._udelezbe.values()]
        try:
            os.makedirs(self.mapa, exist_ok=True)
            zac = self._pot_zapisa() + ".tmp"
            with open(zac, "w", encoding="utf-8") as d:
                json.dump(vnosi, d, separators=(",", ":"))
            os.replace(zac, self._pot_zapisa())
        except OSError:
            pass

    def _ime_tega(self) -> str:
        return "@tukaj"

    # -------------------------------------------------------------- lastnik
    def _seja(self, oznaka: str, ustvari: bool) -> Optional[_Seja]:
        with self._zaklep:
            s = self._seje.get(oznaka)
            if s is not None or not ustvari:
                return s
        # Branje cele datoteke (zgoscena vrednost, kopija v zgodovino) ne sme drzati skupne kljucavnice: sicer caka
        # D-Bus (TeamworkStanje) in vsak tik, dokler se velika datoteka ne prebere.
        pot = self.razresi(oznaka) or ""
        if not pot or not os.path.isfile(pot):
            return None
        nova = _Seja(oznaka, pot)
        nova.stat = _stat(pot)
        nova.sha = _sha(pot)
        self.zgodovina.shrani(nova.kljuc, nova.sha, pot)
        with self._zaklep:
            return self._seje.setdefault(oznaka, nova)

    def _urejajo(self, s: _Seja) -> List[Tuple[str, str]]:
        """(id, ime) naprav, ki imajo datoteko zdaj odprto; "" = ta naprava."""
        zdaj = self.zdaj()
        izid = [(i, u.get("ime") or i) for i, u in s.udelezenci.items() if u.get("odprto") and zdaj - u.get("cas", 0) < POTECE_S]
        if s.lokalno["odprto"]:
            izid.append(("", ""))
        return izid

    def prijava(self, posiljatelj: str, p: dict) -> dict:
        """Ukaz `files.session` z udelezenca: {id, odprto, program, osnova}. Vrne stanje seje (za odgovor)."""
        oznaka = str(p.get("id") or "")
        s = self._seja(oznaka, ustvari=True)
        if s is None:
            return {"ok": False, "koda": "ni_datoteke"}
        with s.zaklep:
            self._preveri_lokalno(s)
            zdaj = self.zdaj()
            s.udelezenci[posiljatelj] = {"ime": kratko_ime(self.ime_naprave(posiljatelj) or posiljatelj), "odprto": bool(p.get("odprto")),
                                         "program": str(p.get("program") or "")[:80], "cas": zdaj}
            s.zadnja_raba = zdaj
            self._posodobi_teamwork(s)
            return self._stanje_seje(s, posiljatelj)

    def _stanje_seje(self, s: _Seja, za: str) -> dict:
        urejajo = self._urejajo(s)
        return {"ok": True, "sha256": s.sha, "verzija": s.verzija, "ime": os.path.basename(s.pot),
                "teamwork": len(urejajo) >= 2,
                "drugi": [ime or "@tukaj" for i, ime in urejajo if i != za],
                "program": s.lokalno["program"] or next((u.get("program") for i, u in s.udelezenci.items()
                                                         if i != za and u.get("odprto") and u.get("program")), ""),
                "zadnji": {"naprava": s.zadnji["naprava"], "ime": s.zadnji["ime"] or "@tukaj", "cas": s.zadnji["cas"]}
                if s.zadnji["cas"] else None,
                "spori": [{"kopija": x["kopija"], "tvoj": x["naprava"] == za, "kdo": x["kdo"]} for x in s.spori[-5:]]}

    def _posodobi_teamwork(self, s: _Seja) -> None:
        """Obvestilo na TEJ napravi (lastnik), ko se Teamwork zacne ali konca - samo, ce datoteko ureja tudi ta."""
        urejajo = self._urejajo(s)
        tw = len(urejajo) >= 2
        if tw != s.teamwork:
            s.teamwork = tw
            if s.lokalno["odprto"]:
                drugi = ", ".join(ime for i, ime in urejajo if i)
                self.obvesti("zacetek" if tw else "konec", {"ime": os.path.basename(s.pot), "kdo": drugi})

    def _preveri_lokalno(self, s: _Seja, okna: Optional[List[dict]] = None, procesi: Optional[set] = None) -> None:
        """Ali ima datoteko odprto program na tej napravi. Ob odprtju zapomni razlicico, ki jo je program nalozil."""
        if okna is None:
            okna = self._okna()
            if okna is None:
                return
        program = je_odprta(s.pot, okna, procesi)
        if program is not None and not s.lokalno["odprto"]:
            s.lokalno.update(odprto=True, program=program, osnova=s.sha)
            print("[Teamwork] tukaj odprto:", os.path.basename(s.pot), program)
        elif program is None and s.lokalno["odprto"]:
            s.lokalno.update(odprto=False, osnova="", program="")
            print("[Teamwork] tukaj zaprto:", os.path.basename(s.pot))
        elif program is not None:
            s.lokalno["program"] = program

    def popravek(self, posiljatelj: str, oznaka: str, pot_telesa: str) -> Tuple[int, dict]:
        """`POST /popravek/<id>`: shranitev z druge naprave. Udelezenec mora biti prijavljen v sejo te datoteke."""
        s = self._seja(oznaka, ustvari=False)
        if s is None or posiljatelj not in s.udelezenci:
            return 409, {"ok": False, "koda": "ni_seje"}
        ime = s.udelezenci[posiljatelj].get("ime") or posiljatelj
        with s.zaklep:
            self._zaznaj_lokalno_shranitev(s, takoj=True)
            fd, prihaja = tempfile.mkstemp(prefix=".prihaja-", dir=self._mapa_zacasnih())
            os.close(fd)
            try:
                lokalni = [s.pot] + self.zgodovina.poti(s.kljuc)
                glava, meritve = uporabi_popravek(pot_telesa, lokalni, prihaja)
            except link_delta.NapakaDelte as e:
                _odstrani(prihaja)
                return 409, {"ok": False, "koda": "ponovi", "razlog": str(e), "sha256": s.sha}
            except OSError as e:
                _odstrani(prihaja)
                return 500, {"ok": False, "koda": "disk", "razlog": str(e)}
            nova = str(glava["opis"]["sha256"])
            osnova = str(glava.get("osnova") or "")
            # Program na tej napravi je lahko shranil, medtem ko se je popravek sestavljal (velika datoteka): njegova
            # shranitev je nova trenutna razlicica, popravek pa zato pride v spor (nic se ne prepise).
            self._zaznaj_lokalno_shranitev(s, takoj=True)
            if nova == s.sha:
                _odstrani(prihaja)
                return 200, {"ok": True, "sha256": s.sha, "verzija": s.verzija, "spor": False, "podatki": meritve["podatki"]}
            if osnova == s.sha:
                # Hitro naprej: nova razlicica postane glavna (prejsnja je v zgodovini). Zamenjava samo, ce se datoteka
                # do zadnjega trenutka ni spremenila - sicer spor.
                self.zgodovina.shrani(s.kljuc, s.sha, s.pot)
                kopija_zgodovine = os.path.join(self._mapa_zacasnih(), ".z-" + nova)
                try:
                    shutil.copyfile(prihaja, kopija_zgodovine)
                    _namesti(prihaja, s.pot, s.pot, pred=s.stat)
                    self.zgodovina.prevzemi(s.kljuc, nova, kopija_zgodovine)
                except _SpremenjenaMedTem:
                    _odstrani(kopija_zgodovine)
                    self._zaznaj_lokalno_shranitev(s, takoj=True)
                except OSError as e:
                    _odstrani(prihaja)
                    _odstrani(kopija_zgodovine)
                    return 500, {"ok": False, "koda": "disk", "razlog": str(e)}
                else:
                    s.sha, s.stat = nova, _stat(s.pot)
                    s.verzija += 1
                    s.zadnji = {"naprava": posiljatelj, "ime": ime, "cas": self.zdaj()}
                    s.spremenjeno_od = None
                    if s.lokalno["odprto"]:
                        self.obvesti("nova", {"ime": os.path.basename(s.pot), "kdo": ime})
                    return 200, {"ok": True, "spor": False, "sha256": s.sha, "verzija": s.verzija,
                                 "podatki": meritve["podatki"]}
            # Spor: nekdo je shranil vmes - glavna datoteka ostane, ta razlicica gre zraven (ista vsebina samo enkrat).
            obstojeca = s.kopije.get(nova)
            if obstojeca and os.path.isfile(os.path.join(os.path.dirname(s.pot), obstojeca)):
                _odstrani(prihaja)
                return 200, {"ok": True, "spor": True, "kopija": obstojeca, "sha256": s.sha, "verzija": s.verzija,
                             "podatki": meritve["podatki"]}
            if len(s.kopije) >= NAJVEC_KOPIJ:
                _odstrani(prihaja)
                return 409, {"ok": False, "koda": "prevec_kopij", "sha256": s.sha}
            kopija = ime_kopije(s.pot, ime)
            try:
                _namesti(prihaja, kopija, s.pot)
            except OSError as e:
                _odstrani(prihaja)
                return 500, {"ok": False, "koda": "disk", "razlog": str(e)}
            s.kopije[nova] = os.path.basename(kopija)
            kdo_prej = s.zadnji["ime"] or self._ime_tega()
            s.spori.append({"kopija": os.path.basename(kopija), "naprava": posiljatelj, "kdo": kdo_prej})
            if s.lokalno["odprto"]:
                self.obvesti("spor_drugi", {"ime": os.path.basename(s.pot), "kdo": ime, "kopija": os.path.basename(kopija)})
            return 200, {"ok": True, "spor": True, "kopija": os.path.basename(kopija), "sha256": s.sha,
                         "verzija": s.verzija, "podatki": meritve["podatki"]}
        return 500, {"ok": False, "koda": "napaka"}

    def _mapa_zacasnih(self) -> str:
        m = os.path.join(self.mapa, "zacasno")
        os.makedirs(m, exist_ok=True)
        return m

    def _zaznaj_lokalno_shranitev(self, s: _Seja, takoj: bool = False) -> None:
        """Datoteko je spremenil program na tej napravi. Ce program ni nalozil zadnje razlicice z druge naprave, ta
        razlicica ostane kot kopija ob datoteki (vsebina je v zgodovini)."""
        st = _stat(s.pot)
        if st is None or st == s.stat:
            s.spremenjeno_od = None
            return
        zdaj = self.zdaj()
        # Stanje programa ob PRVI opazeni spremembi: »shrani in zapri« zapre okno, preden datoteka miruje - takrat je
        # trenutno stanje ze »zaprto« in brez osnove, pa bi spor (program ni nalozil razlicice z druge naprave) zgresili.
        if s.spremenjeno_od is None:
            s.spremenjeno_od = (st, zdaj, dict(s.lokalno))
        elif s.spremenjeno_od[0] != st:
            s.spremenjeno_od = (st, zdaj, s.spremenjeno_od[2])
        if not takoj and zdaj - s.spremenjeno_od[1] < MIRUJE_S:
            return
        lokalno = s.spremenjeno_od[2]
        s.spremenjeno_od = None
        try:
            nova = _sha(s.pot)
        except OSError:
            return
        if nova == s.sha:
            s.stat = st
            return
        prejsnja, prejsnji = s.sha, dict(s.zadnji)
        zastarela = lokalno["odprto"] and lokalno["osnova"] and lokalno["osnova"] != prejsnja and prejsnji["naprava"]
        if zastarela:
            vir = self.zgodovina.pot(s.kljuc, prejsnja)
            ohranjena = False
            if vir and prejsnja not in s.kopije:
                kopija = ime_kopije(s.pot, prejsnji["ime"] or prejsnji["naprava"])
                try:
                    shutil.copyfile(vir, kopija)
                    s.kopije[prejsnja] = os.path.basename(kopija)
                    s.spori.append({"kopija": os.path.basename(kopija), "naprava": prejsnji["naprava"], "kdo": "@tukaj"})
                    self.obvesti("spor", {"ime": os.path.basename(s.pot), "kdo": prejsnji["ime"], "kopija": os.path.basename(kopija)})
                    ohranjena = True
                except OSError:
                    ohranjena = False
            elif prejsnja in s.kopije:
                ohranjena = True
            if not ohranjena:
                # Uporabnik mora izvedeti, da razlicica z druge naprave ni ohranjena - ne sme izginiti potiho.
                self.obvesti("spor_brez_kopije", {"ime": os.path.basename(s.pot), "kdo": prejsnji["ime"] or prejsnji["naprava"]})
        s.sha, s.stat = nova, st
        s.verzija += 1
        s.zadnji = {"naprava": "", "ime": "", "cas": zdaj}
        s.lokalno["osnova"] = nova
        self.zgodovina.shrani(s.kljuc, nova, s.pot)

    # -------------------------------------------------------------- udelezenec
    def udelezi(self, podatki: dict) -> dict:
        """Safeer OS po »Nadaljuj tukaj«: delovno kopijo spremljamo. Vrne stanje lastnika (program, drugi) - ali
        {"podprto": False}, ce naprava lastnika Teamworka ne zna."""
        u = _Udelezba(podatki)
        if not u.naprava or not u.oznaka or not u.pot or not os.path.isfile(u.pot):
            return {"ok": False, "koda": "napacna_zahteva"}
        if not u.sha:
            u.sha = _sha(u.pot)
        u.osnova = u.sha
        u.stat = _stat(u.pot)
        u.zadnja_raba = self.zdaj()
        with self._zaklep:
            stara = self._udelezbe.get(u.kljuc)
            if stara is not None and stara.streznik and not u.streznik:
                u.streznik = stara.streznik
            self._udelezbe[u.kljuc] = u
        self._shrani()
        odgovor = self._ping(u, odprto=False)
        return {"ok": True, "podprto": u.podprto, "program": (odgovor or {}).get("program", ""),
                "drugi": (odgovor or {}).get("drugi", [])}

    def _ping(self, u: _Udelezba, odprto: bool) -> Optional[dict]:
        r = self.ukaz(u.naprava, "files.session", {"id": u.oznaka, "odprto": bool(odprto), "program": u.program,
                                                    "osnova": u.osnova})
        u.naslednji_ping = self.zdaj() + (PING_ODPRTO_S if odprto else PING_SPREMLJAM_S)
        if not r.get("ok"):
            # Naprava lastnika Teamworka ne zna (starejsa razlicica) ali ji datotek ne dovoli: delovna kopija ostane
            # navadna kopija (kot pred Teamworkom), nic se ne posilja.
            if r.get("koda") in ("ni_dovoljeno", "neznano", "neznano_dejanje", "unknown_action", "ni_datoteke"):
                u.podprto = False
            return None
        d = r.get("data") if isinstance(r.get("data"), dict) else {}
        if not d.get("ok", True):
            return None
        u.podprto = True
        if isinstance(d.get("streznik"), dict):
            u.streznik = d["streznik"]
        self._iz_odgovora(u, d)
        return d

    def _iz_odgovora(self, u: _Udelezba, d: dict) -> None:
        ime = os.path.basename(u.pot)
        drugi = [self._ime(u, x) for x in d.get("drugi") or [] if isinstance(x, str)]
        tw = bool(d.get("teamwork")) and u.odprto
        if tw and not u.teamwork:
            self.obvesti("zacetek", {"ime": ime, "kdo": ", ".join(drugi)})
        elif u.teamwork and not tw and u.odprto:
            self.obvesti("konec", {"ime": ime})
        u.teamwork, u.drugi = tw, drugi
        obvescen_spor = False
        spori = [x for x in d.get("spori") or [] if isinstance(x, dict) and x.get("kopija")]
        if u.videni_spori is None:
            u.videni_spori = {str(x["kopija"]) for x in spori}            # stare spore ob prvem odgovoru le zabelezimo
        for x in spori:
            if str(x["kopija"]) in u.videni_spori:
                continue
            u.videni_spori.add(str(x["kopija"]))
            if x.get("tvoj") and not u.poslano_spor == str(x["kopija"]):
                self.obvesti("spor", {"ime": ime, "kdo": self._ime(u, str(x.get("kdo") or "@tukaj")),
                                      "kopija": str(x["kopija"])})
                obvescen_spor = True
        sha = str(d.get("sha256") or "")
        if sha and sha != u.sha and _stat(u.pot) == u.stat and self.prenesi is not None:
            # Lastnik ima novejso razlicico, tu ni nic neposlanega: prenesemo samo spremembe.
            try:
                r = self.prenesi(u) or {}
            except Exception:  # noqa: BLE001 - poskusimo ob naslednjem javljanju
                r = {}
            if r.get("ok"):
                u.sha = sha
                u.stat = _stat(u.pot)
                if not u.odprto:
                    u.osnova = sha
                zadnji = d.get("zadnji") if isinstance(d.get("zadnji"), dict) else {}
                if not obvescen_spor:            # obvestilo o sporu ze pove, da je glavna razlicica druga
                    self.obvesti("nova" if u.odprto else "nova_zaprta",
                                 {"ime": ime, "kdo": self._ime(u, str(zadnji.get("ime") or "@tukaj"))})
                self._shrani()

    @staticmethod
    def _ime(u: _Udelezba, x: str) -> str:
        """»@tukaj« v odgovoru lastnika pomeni napravo lastnika same."""
        return kratko_ime(u.ime_naprave if x == "@tukaj" else x)

    def _poslji(self, u: _Udelezba) -> None:
        """Delovna kopija je shranjena in miruje: lastniku samo spremenjene kose (najvec trikrat, ce se vmes spremeni)."""
        if self.poslji is None:
            return
        try:
            nova = _sha(u.pot)
        except OSError:
            return
        st = _stat(u.pot)
        if nova == u.sha:
            u.stat = st
            return
        if self.zdaj() < u.premor_do:
            return
        ime = os.path.basename(u.pot)
        for _ in range(3):
            opis = None
            if self.opis_lastnika is not None:
                try:
                    opis = self.opis_lastnika(u)
                except Exception:  # noqa: BLE001 - brez opisa gre cela datoteka
                    opis = None
            fd, telo = tempfile.mkstemp(prefix=".popravek-", dir=self._mapa_zacasnih())
            os.close(fd)
            try:
                try:
                    info = naredi_popravek(u.pot, opis, u.osnova, telo)
                except link_delta.NapakaDelte:
                    return                                   # program se pise: naslednji tik
                koda, odgovor = self.poslji(u, telo, info["dolzina"])
            except Exception:  # noqa: BLE001 - naprava ni dosegljiva: poskusimo ob naslednjem tiku
                return
            finally:
                _odstrani(telo)
            if koda == 200 and odgovor.get("ok"):
                if odgovor.get("spor"):
                    if u.poslano_spor != str(odgovor.get("kopija", "")):
                        self.obvesti("spor", {"ime": ime, "kdo": self._kdo_zadnji(u), "kopija": odgovor.get("kopija", "")})
                    u.poslano_spor = str(odgovor.get("kopija", ""))
                    # Ta vsebina je pri lastniku (kopija): ne posiljamo je znova. Glavno razlicico prenesemo zdaj ali ob
                    # naslednjem javljanju (delovna kopija je takrat enaka poslani, zato jo _iz_odgovora sme zamenjati).
                    u.stat = st
                    if self.prenesi is not None:
                        try:
                            if (self.prenesi(u) or {}).get("ok"):
                                u.sha = str(odgovor.get("sha256") or "")
                                u.stat = _stat(u.pot)
                        except Exception:  # noqa: BLE001
                            pass
                    return
                u.sha = nova
                u.osnova = nova
                u.stat = st
                if self.usklajeno is not None:
                    try:
                        self.usklajeno(u)
                    except Exception:  # noqa: BLE001
                        pass
                self._shrani()
                return
            if koda == 409 and odgovor.get("koda") == "ni_seje":
                self._ping(u, odprto=u.odprto)
                continue
            if koda == 409 and odgovor.get("koda") == "ponovi":
                continue
            if koda in (413, 500, 507) or odgovor.get("koda") in ("prevec_kopij", "disk", "ni_prostora"):
                # Trajna napaka pri lastniku: ne posiljamo vsakih nekaj sekund znova cele datoteke.
                u.premor_do = self.zdaj() + PREMOR_PO_NAPAKI_S
            return

    def _kdo_zadnji(self, u: _Udelezba) -> str:
        return ", ".join(u.drugi) or u.ime_naprave

    # -------------------------------------------------------------- tik
    def _okna(self) -> Optional[List[dict]]:
        """Seznam oken ali None, ce ga ta trenutek ni (glavna nit zasedena): takrat stanja odprtosti ne spreminjamo -
        sicer bi prazen seznam pomenil »zaprto« in Teamwork bi utripal."""
        try:
            o = self.okna()
        except Exception:  # noqa: BLE001
            return None
        return None if o is None else list(o)

    def tik(self) -> None:
        with self._zaklep:
            seje = list(self._seje.values())
            udelezbe = list(self._udelezbe.values())
        if not seje and not udelezbe:
            return
        self._tik_st += 1
        okna = self._okna()
        procesi = None
        if self.procesi is not None and self._tik_st % 3 == 1:
            try:
                procesi = self.procesi()
            except Exception:  # noqa: BLE001
                procesi = None
        zdaj = self.zdaj()
        for s in seje:
            with s.zaklep:
                self._zaznaj_lokalno_shranitev(s)
                if okna is not None:
                    self._preveri_lokalno(s, okna, procesi)
                for i, u in list(s.udelezenci.items()):
                    if zdaj - u.get("cas", 0) > POTECE_S:
                        u["odprto"] = False
                self._posodobi_teamwork(s)
                if s.lokalno["odprto"] or any(u.get("odprto") for u in s.udelezenci.values()):
                    s.zadnja_raba = zdaj
                if zdaj - s.zadnja_raba > SEJA_VELJA_S:
                    with self._zaklep:
                        self._seje.pop(s.oznaka, None)
        spremenjeno = False
        for u in udelezbe:
            if not u.zaklep.acquire(blocking=False):
                continue
            try:
                if not os.path.isfile(u.pot):
                    continue
                program = je_odprta(u.pot, okna, procesi) if okna is not None else (u.program if u.odprto else None)
                odprto = program is not None
                if odprto and not u.odprto:
                    u.odprto, u.program = True, program or ""
                    u.zadnja_raba = zdaj
                    if _stat(u.pot) == u.stat:
                        u.osnova = u.sha
                    spremenjeno = True
                    self._ping(u, odprto=True)
                elif not odprto and u.odprto:
                    u.odprto = False
                    self._ping(u, odprto=False)
                    if u.teamwork:
                        u.teamwork = False
                # Shranitev: datoteka se je spremenila od zadnje uskladitve in miruje.
                st = _stat(u.pot)
                if st is not None and st != u.stat:
                    if u.spremenjeno_od is None or u.spremenjeno_od[0] != st:
                        u.spremenjeno_od = (st, zdaj)
                    elif zdaj - u.spremenjeno_od[1] >= MIRUJE_S:
                        u.spremenjeno_od = None
                        if u.podprto:
                            if not u.streznik:
                                self._ping(u, odprto=u.odprto)     # po ponovnem zagonu: naslov in zeton lastnika
                            self._poslji(u)
                # Javljanje tudi, ce shranitev caka (sicer bi naprava, ki je bila nedosegljiva, ostala brez zetona).
                if zdaj >= u.naslednji_ping and (u.odprto or zdaj - u.zadnja_raba < SPREMLJAJ_S):
                    self._ping(u, odprto=u.odprto)
            finally:
                u.zaklep.release()
        if spremenjeno:
            self._shrani()

    def zazeni(self) -> None:
        if self._nit is not None:
            return
        self._ustavi.clear()

        def zanka() -> None:
            while not self._ustavi.wait(TIK_S):
                try:
                    self.tik()
                except Exception as e:  # noqa: BLE001 - Teamwork ne sme ustaviti Controla
                    print("[Teamwork]", e)
        self._nit = threading.Thread(target=zanka, name="safeer-teamwork", daemon=True)
        self._nit.start()

    def ustavi(self) -> None:
        self._ustavi.set()
        self._nit = None

    def stanje(self) -> dict:
        """Za stran: kaj ta naprava ureja skupaj z drugimi."""
        with self._zaklep:
            izid = []
            for u in self._udelezbe.values():
                if u.odprto:
                    izid.append({"ime": os.path.basename(u.pot), "naprava": u.ime_naprave, "teamwork": u.teamwork,
                                 "drugi": list(u.drugi)})
            for s in self._seje.values():
                ur = self._urejajo(s)
                if ur:
                    izid.append({"ime": os.path.basename(s.pot), "naprava": "", "teamwork": len(ur) >= 2,
                                 "drugi": [ime for i, ime in ur if i]})
        return {"ok": True, "datoteke": izid}


def _odstrani(pot: str) -> None:
    try:
        os.remove(pot)
    except OSError:
        pass


class _SpremenjenaMedTem(OSError):
    """Cilj se je spremenil po zadnji preverbi (shranil ga je program na tej napravi): zamenjave ni bilo."""


def _namesti(vir: str, cilj: str, vzorec: str, pred: Optional[tuple] = None) -> None:
    """Atomsko: vir (v drugi mapi) -> zacasna ob cilju (pravice kot `vzorec`) -> cilj. S `pred` samo, ce ima cilj
    tik pred zamenjavo se to stanje (sicer _SpremenjenaMedTem, vir ostane)."""
    mapa = os.path.dirname(os.path.abspath(cilj))
    fd, zac = tempfile.mkstemp(prefix=".safeer-teamwork-", suffix=".part", dir=mapa)
    try:
        with os.fdopen(fd, "wb") as f, open(vir, "rb") as v:
            shutil.copyfileobj(v, f, 1024 * 1024)
            f.flush()
            os.fsync(f.fileno())
        try:
            shutil.copymode(vzorec, zac)
        except OSError:
            pass
        if pred is not None and _stat(cilj) != pred:
            raise _SpremenjenaMedTem("cilj se je spremenil")
        os.replace(zac, cilj)
    except BaseException:
        _odstrani(zac)
        raise
    _odstrani(vir)
