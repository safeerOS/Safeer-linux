"""»Poslji na …« v upravitelju datotek Nemo (Linux Mint): desni klik na datoteke ali mapo -> naprava v Safeer Linku.

Lastnik, 18. 10. 2026: posiljanje datotek med napravami mora biti lazje - en klik iz Nema, zadnja naprava prva.

Nemo pozna samo stalna dejanja (datoteke *.nemo_action), brez podmenija z imeni, ki se spreminjajo. Zato Safeer
Control ob vsakem novem seznamu naprav zapise eno dejanje na napravo, ki sprejme datoteke, v uporabnikovo mapo dejanj
($XDG_DATA_HOME/nemo/actions; Nemo jo spremlja in meni osvezi sam). Preverjeno v izvorni kodi Nema (linuxmint/nemo,
14. 10. 2026): vrstni red v meniju je po imenu datoteke (nemo-action-manager.c, sort_actions po uuid = ime datoteke
brez .nemo_action), Name[jezik] je podprt, pogoj »dbus <ime>« dejanje pokaze samo, ko ime na vodilu obstaja.

  - safeer-poslji-NN.nemo_action: NN je mesto v meniju (zadnja uporabljena naprava prva - link_posiljanje.razvrsti);
  - Exec: safeerctl send --notify --to <id> %F (Safeer Control poslje in obvesti; posiljanje caka na napravo, ce je
    zdaj ni - link_posiljanje.PREHODNE);
  - Conditions=dbus io.github.memelandfaner.SafeerControl: brez tecocega Controla vnosov ni (ne bi delovali);
  - Dependencies=safeerctl: po odstranitvi paketa vnosi izginejo sami, tudi ce datoteke ostanejo.

Pisemo samo svoje datoteke (predpona safeer-poslji-) in samo, ce se je vsebina spremenila (Nemo ob vsaki spremembi
mape meni nalozi znova). Brez Nema na racunalniku ne pisemo nicesar.
"""
from __future__ import annotations

import os
import re
import shutil
from typing import Dict, List, Optional

PREDPONA = "safeer-poslji-"
KONCNICA = ".nemo_action"
#: Toliko naprav pokazemo v meniju (vec jih uporabnik doseze v Safeer Linku ali Datotekah Safeer OS).
NAJVEC = 8
DBUS_CONTROL = "io.github.memelandfaner.SafeerControl"
#: Oznaka naprave iz kljuca (link_dostop.je_id_iz_kljuca) in starejse oznake: samo varni znaki - gre v ukazno vrstico.
_VARNA_OZNAKA = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

IMENA = {
    "sl": "Pošlji na »{ime}«", "en": "Send to “{ime}”", "de": "An „{ime}“ senden",
    "es": "Enviar a «{ime}»", "fr": "Envoyer à « {ime} »", "it": "Invia a «{ime}»",
}
OPISI = {
    "sl": "Safeer Link: pošlje izbrane datoteke in mape na to napravo",
    "en": "Safeer Link: sends the selected files and folders to this device",
    "de": "Safeer Link: sendet die ausgewählten Dateien und Ordner an dieses Gerät",
    "es": "Safeer Link: envía los archivos y carpetas seleccionados a este dispositivo",
    "fr": "Safeer Link : envoie les fichiers et dossiers sélectionnés vers cet appareil",
    "it": "Safeer Link: invia i file e le cartelle selezionati a questo dispositivo",
}


def mapa_dejanj() -> str:
    """$XDG_DATA_HOME/nemo/actions (privzeto mapa .local/share/nemo/actions v domaci mapi)."""
    osnova = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(osnova, "nemo", "actions")


def _ime_za_meni(ime: str) -> str:
    """Ime naprave v Name: brez prelomov, % (Nemo ga bere kot znacko, npr. %N) in _ (GTK ga bere kot bliznjico)."""
    cisto = " ".join(str(ime or "").split())[:64]
    return cisto.replace("%", "%%").replace("_", "__")


def vsebina(naprava: dict) -> str:
    ime = _ime_za_meni(naprava.get("ime") or naprava.get("id") or "")
    vrstice = ["[Nemo Action]", "Name=" + IMENA["en"].format(ime=ime)]
    vrstice += ["Name[%s]=%s" % (j, IMENA[j].format(ime=ime)) for j in ("sl", "de", "es", "fr", "it")]
    vrstice.append("Comment=" + OPISI["en"])
    vrstice += ["Comment[%s]=%s" % (j, OPISI[j]) for j in ("sl", "de", "es", "fr", "it")]
    vrstice += [
        "Exec=safeerctl send --notify --to %s %%F" % naprava["id"],
        "Icon-Name=document-send",
        "Selection=notnone",
        "Extensions=any;",
        "UriScheme=file",
        "Dependencies=safeerctl;",
        "Conditions=dbus %s;" % DBUS_CONTROL,
    ]
    return "\n".join(vrstice) + "\n"


def dejanja(naprave: List[dict]) -> Dict[str, str]:
    """{ime datoteke: vsebina} za naprave v danem vrstnem redu (prva je zgoraj v meniju)."""
    izid: Dict[str, str] = {}
    for n in naprave:
        if len(izid) >= NAJVEC:
            break
        oznaka = str(n.get("id") or "")
        if not _VARNA_OZNAKA.match(oznaka) or oznaka.startswith("-"):
            continue
        izid["%s%02d%s" % (PREDPONA, len(izid) + 1, KONCNICA)] = vsebina(n)
    return izid


def zapisi(naprave: List[dict], mapa: Optional[str] = None, nemo: Optional[bool] = None) -> bool:
    """Uskladi dejanja v mapi z napravami. Vrne True, ce se je kaj spremenilo. Napake gredo v dnevnik."""
    if nemo is None:
        nemo = shutil.which("nemo") is not None
    mapa = mapa or mapa_dejanj()
    zelene = dejanja(naprave) if nemo else {}
    spremenjeno = False
    try:
        obstojece = [i for i in os.listdir(mapa) if i.startswith(PREDPONA) and i.endswith(KONCNICA)]
    except OSError:
        obstojece = []
    if not zelene and not obstojece:
        return False
    try:
        if zelene:
            os.makedirs(mapa, exist_ok=True)
        for ime, besedilo in zelene.items():
            pot = os.path.join(mapa, ime)
            try:
                with open(pot, encoding="utf-8") as f:
                    if f.read() == besedilo:
                        continue
            except OSError:
                pass
            zacasna = os.path.join(mapa, "." + ime + ".tmp")
            with open(zacasna, "w", encoding="utf-8") as f:
                f.write(besedilo)
            os.replace(zacasna, pot)
            spremenjeno = True
        for ime in obstojece:
            if ime not in zelene:
                # Nasa datoteka za napravo, ki je ni vec (ali je zdaj nizje na seznamu).
                os.remove(os.path.join(mapa, ime))
                spremenjeno = True
    except OSError as e:
        print("[SafeerLink] dejanj za Nemo ni bilo mogoce zapisati:", e, flush=True)
    return spremenjeno


__all__ = ["zapisi", "dejanja", "vsebina", "mapa_dejanj"]
