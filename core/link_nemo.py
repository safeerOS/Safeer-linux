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

Naprava, ki je zdaj ni v Linku, a je ze sprejemala datoteke (`dosegljiva: False`, link_posiljanje.za_meni), ima v
meniju pripis »(ko bo dosegljiva)«: posiljka pocaka nanjo in se nadaljuje, ko se vrne (pregled 18. 10. 2026).

Flatpak (pregled 18. 10. 2026): v peskovniku je XDG_DATA_HOME zasebna mapa (~/.var/app/<id>/data), safeerctl pa je
v /app/bin - Nemo na racunalniku ne bi videl ne dejanj ne ukaza. Zato:
  - dejanja gredo v mapo podatkov RACUNALNIKA (core/gostitelj.podatki_gostitelja; dovoljenje --filesystem=home);
  - Exec: flatpak run --file-forwarding --command=safeerctl <id aplikacije> send --notify --to <id> @@ %F @@
    (Dependencies=flatpak). Datoteke, ki jih peskovnik ne vidi (zunaj domace mape, /media, /mnt), Flatpak preda prek
    portala dokumentov (/run/user/<uid>/doc/...); te Control bere, ker imata isto id aplikacije;
  - Nemo na racunalniku prepoznamo po /run/host/usr/bin/nemo (dovoljenje --filesystem=host-os:ro).
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
IMENA_CAKA = {
    "sl": "Pošlji na »{ime}« (ko bo dosegljiva)", "en": "Send to “{ime}” (when it is back)",
    "de": "An „{ime}“ senden (sobald erreichbar)", "es": "Enviar a «{ime}» (cuando vuelva)",
    "fr": "Envoyer à « {ime} » (à son retour)", "it": "Invia a «{ime}» (quando torna)",
}
OPISI_CAKA = {
    "sl": "Safeer Link: naprave zdaj ni – datoteke se pošljejo same, ko bo spet v Linku",
    "en": "Safeer Link: the device is not here now – the files are sent by themselves when it is back in Link",
    "de": "Safeer Link: das Gerät ist gerade nicht da – die Dateien werden gesendet, sobald es wieder in Link ist",
    "es": "Safeer Link: el dispositivo no está ahora – los archivos se envían solos cuando vuelva a Link",
    "fr": "Safeer Link : l'appareil n'est pas là – les fichiers partent tout seuls dès qu'il revient dans Link",
    "it": "Safeer Link: il dispositivo ora non c'è – i file partono da soli quando torna in Link",
}
#: Id aplikacije Flatpak (gre v ukazno vrstico): samo varni znaki.
_VARNO_ID_APLIKACIJE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*(\.[A-Za-z0-9_-]+){2,}$")
OPISI = {
    "sl": "Safeer Link: pošlje izbrane datoteke in mape na to napravo",
    "en": "Safeer Link: sends the selected files and folders to this device",
    "de": "Safeer Link: sendet die ausgewählten Dateien und Ordner an dieses Gerät",
    "es": "Safeer Link: envía los archivos y carpetas seleccionados a este dispositivo",
    "fr": "Safeer Link : envoie les fichiers et dossiers sélectionnés vers cet appareil",
    "it": "Safeer Link: invia i file e le cartelle selezionati a questo dispositivo",
}


def flatpak_id() -> str:
    """Id aplikacije, ce Control tece v Flatpaku (sicer "")."""
    try:
        from core import gostitelj
        if not gostitelj.v_flatpaku():
            return ""
    except Exception:  # noqa: BLE001
        return ""
    i = os.environ.get("FLATPAK_ID", "")
    return i if _VARNO_ID_APLIKACIJE.match(i) else ""


def mapa_dejanj(flatpak: str = "") -> str:
    """$XDG_DATA_HOME/nemo/actions (privzeto mapa .local/share/nemo/actions v domaci mapi). V Flatpaku mapa podatkov
    racunalnika (HOST_XDG_DATA_HOME), ne peskovnika - tam Nemo isce dejanja."""
    if flatpak:
        from core import gostitelj
        return os.path.join(gostitelj.podatki_gostitelja(), "nemo", "actions")
    osnova = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(osnova, "nemo", "actions")


def ima_nemo(flatpak: str = "") -> bool:
    """Ali je na racunalniku Nemo. V Flatpaku je /app/host-bin/nemo ovoj (obstaja vedno), zato gledamo /usr racunalnika."""
    if flatpak:
        return os.path.exists("/run/host/usr/bin/nemo")
    return shutil.which("nemo") is not None


def _ime_za_meni(ime: str) -> str:
    """Ime naprave v Name: brez prelomov, % (Nemo ga bere kot znacko, npr. %N) in _ (GTK ga bere kot bliznjico)."""
    cisto = " ".join(str(ime or "").split())[:64]
    return cisto.replace("%", "%%").replace("_", "__")


def vsebina(naprava: dict, flatpak: str = "") -> str:
    ime = _ime_za_meni(naprava.get("ime") or naprava.get("id") or "")
    caka = naprava.get("dosegljiva") is False
    imena, opisi = (IMENA_CAKA, OPISI_CAKA) if caka else (IMENA, OPISI)
    vrstice = ["[Nemo Action]", "Name=" + imena["en"].format(ime=ime)]
    vrstice += ["Name[%s]=%s" % (j, imena[j].format(ime=ime)) for j in ("sl", "de", "es", "fr", "it")]
    vrstice.append("Comment=" + opisi["en"])
    vrstice += ["Comment[%s]=%s" % (j, opisi[j]) for j in ("sl", "de", "es", "fr", "it")]
    if flatpak:
        ukaz = "flatpak run --file-forwarding --command=safeerctl %s send --notify --to %s @@ %%F @@" % (
            flatpak, naprava["id"])
        odvisnost = "flatpak"
    else:
        ukaz = "safeerctl send --notify --to %s %%F" % naprava["id"]
        odvisnost = "safeerctl"
    vrstice += [
        "Exec=" + ukaz,
        "Icon-Name=document-send",
        "Selection=notnone",
        "Extensions=any;",
        "UriScheme=file",
        "Dependencies=%s;" % odvisnost,
        "Conditions=dbus %s;" % DBUS_CONTROL,
    ]
    return "\n".join(vrstice) + "\n"


def dejanja(naprave: List[dict], flatpak: str = "") -> Dict[str, str]:
    """{ime datoteke: vsebina} za naprave v danem vrstnem redu (prva je zgoraj v meniju)."""
    izid: Dict[str, str] = {}
    for n in naprave:
        if len(izid) >= NAJVEC:
            break
        oznaka = str(n.get("id") or "")
        if not _VARNA_OZNAKA.match(oznaka) or oznaka.startswith("-"):
            continue
        izid["%s%02d%s" % (PREDPONA, len(izid) + 1, KONCNICA)] = vsebina(n, flatpak)
    return izid


def zapisi(naprave: List[dict], mapa: Optional[str] = None, nemo: Optional[bool] = None,
           flatpak: Optional[str] = None) -> bool:
    """Uskladi dejanja v mapi z napravami. Vrne True, ce se je kaj spremenilo. Napake gredo v dnevnik.
    `flatpak`: id aplikacije, kadar Control tece v Flatpaku (None = ugotovi sam)."""
    if flatpak is None:
        flatpak = flatpak_id()
    if flatpak and not _VARNO_ID_APLIKACIJE.match(flatpak):
        flatpak = ""
    if nemo is None:
        nemo = ima_nemo(flatpak)
    mapa = mapa or mapa_dejanj(flatpak)
    zelene = dejanja(naprave, flatpak) if nemo else {}
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


__all__ = ["zapisi", "dejanja", "vsebina", "mapa_dejanj", "flatpak_id", "ima_nemo"]
