"""Gledalec prostora v Safeer Controlu (Prostori, krog 2): vidna pot ven iz celozaslonskega prikaza in besedila vrstice.

Zaslon naprave iz Prostorov se odpre CELOZASLONSKO (lastnik: »kot da si na tisti napravi«). Ker gredo tipke napravi, mora
biti izhod viden in zanesljiv: vrstica na vrhu (pokaze se ob odprtju in ko kazalec pride na zgornji rob) z gumboma
»Izhod iz celega zaslona« in »Zapri«, in DRZAN Esc (kratek Esc gre napravi - na telefonu je to Nazaj, na racunalniku Esc).
Super+Tab in Super+Alt+levo/desno iz gledalca vrneta v preklopnik Prostori (ce Control tece v Safeer OS).

Ta modul je brez GTK (stanje tipke z zunanjo uro, besedila); okno je v safeer_control.py (_VrsticaGledalca).
"""
from __future__ import annotations

from typing import Optional

#: Toliko casa (s) mora biti Esc drzan, da zapusti cel zaslon. Krajse = tipka gre napravi.
DRZI_ESC_S = 0.8
#: Toliko casa (s) ostane vrstica vidna po odprtju ali po tem, ko kazalec zapusti zgornji rob.
VRSTICA_VIDNA_S = 3.0
#: Zgornji rob (px), ki pokaze vrstico v celozaslonskem nacinu.
ROB_PX = 6
#: Najvec znakov, ki jih »Prilepi besedilo« natipka na napravi (vnos gre znak po znak).
NAJVEC_BESEDILA = 4000
#: Najvec datotek naenkrat, spuscenih v gledalec.
NAJVEC_DATOTEK = 20


class DrzanaTipka:
    """Esc v celozaslonskem gledalcu: kratek pritisk -> "kratko" (poslji napravi), drzan -> izhod iz celega zaslona.

    `pritisk` ob vsakem key-pressed (samodejno ponavljanje se ne steje), `poteklo` iz casovnika (True enkrat, ko je
    tipka drzana dovolj dolgo), `spust` ob key-released: "kratko", "izhod" (dolgo, a casovnik se ni sprozil),
    "nic" (izhod je ze bil) ali "" (tipka ni bila pritisnjena v tem gledalcu)."""

    def __init__(self, drzi_s: float = DRZI_ESC_S) -> None:
        self.drzi_s = drzi_s
        self._od: Optional[float] = None
        self._porabljeno = False

    @property
    def drzana(self) -> bool:
        return self._od is not None

    def pritisk(self, t: float) -> None:
        if self._od is None:
            self._od = t
            self._porabljeno = False

    def poteklo(self, t: float) -> bool:
        if self._od is not None and not self._porabljeno and t - self._od >= self.drzi_s:
            self._porabljeno = True
            return True
        return False

    def spust(self, t: float) -> str:
        if self._od is None:
            return ""
        od, porabljeno = self._od, self._porabljeno
        self._od, self._porabljeno = None, False
        if porabljeno:
            return "nic"
        return "izhod" if t - od >= self.drzi_s else "kratko"

    def ponastavi(self) -> None:
        self._od, self._porabljeno = None, False


def poti_spuscenih(poti) -> list:
    """Spuscene datoteke za posiljanje: samo absolutne lokalne poti, brez podvojenih, najvec NAJVEC_DATOTEK."""
    izhod = []
    for p in poti or []:
        p = str(p or "")
        if p.startswith("/") and "\x00" not in p and p not in izhod:
            izhod.append(p)
        if len(izhod) >= NAJVEC_DATOTEK:
            break
    return izhod


BESEDILA = {
    "sl": {"celo": "Celozaslonsko", "izhod": "Izhod iz celega zaslona", "namig": "Drži Esc za izhod iz celega zaslona",
           "prilepi": "Prilepi besedilo", "prilepi_namig": "Na napravi napiše besedilo iz odložišča tega računalnika",
           "zapri": "Zapri", "prazno": "Odložišče tega računalnika nima besedila.", "prilepljeno": "Besedilo je poslano napravi.",
           "posiljam": "Pošiljam datoteke ({n}) …", "poslano": "Datoteke so poslane ({n}).",
           "ni_poslano": "Datotek ni bilo mogoče poslati.", "prostori": "Prostori (Super+Tab)"},
    "en": {"celo": "Full screen", "izhod": "Leave full screen", "namig": "Hold Esc to leave full screen",
           "prilepi": "Paste text", "prilepi_namig": "Types the text from this computer’s clipboard on the device",
           "zapri": "Close", "prazno": "This computer’s clipboard has no text.", "prilepljeno": "The text was sent to the device.",
           "posiljam": "Sending files ({n}) …", "poslano": "Files sent ({n}).",
           "ni_poslano": "The files could not be sent.", "prostori": "Spaces (Super+Tab)"},
    "de": {"celo": "Vollbild", "izhod": "Vollbild verlassen", "namig": "Esc gedrückt halten, um das Vollbild zu verlassen",
           "prilepi": "Text einfügen", "prilepi_namig": "Tippt den Text aus der Zwischenablage dieses Computers auf dem Gerät",
           "zapri": "Schließen", "prazno": "Die Zwischenablage dieses Computers enthält keinen Text.",
           "prilepljeno": "Der Text wurde an das Gerät gesendet.", "posiljam": "Dateien werden gesendet ({n}) …",
           "poslano": "Dateien gesendet ({n}).", "ni_poslano": "Die Dateien konnten nicht gesendet werden.",
           "prostori": "Bereiche (Super+Tab)"},
    "es": {"celo": "Pantalla completa", "izhod": "Salir de pantalla completa",
           "namig": "Mantén Esc pulsado para salir de pantalla completa", "prilepi": "Pegar texto",
           "prilepi_namig": "Escribe en el dispositivo el texto del portapapeles de este ordenador", "zapri": "Cerrar",
           "prazno": "El portapapeles de este ordenador no tiene texto.", "prilepljeno": "El texto se ha enviado al dispositivo.",
           "posiljam": "Enviando archivos ({n}) …", "poslano": "Archivos enviados ({n}).",
           "ni_poslano": "No se pudieron enviar los archivos.", "prostori": "Espacios (Super+Tab)"},
    "fr": {"celo": "Plein écran", "izhod": "Quitter le plein écran", "namig": "Maintiens Échap pour quitter le plein écran",
           "prilepi": "Coller le texte", "prilepi_namig": "Tape sur l’appareil le texte du presse-papiers de cet ordinateur",
           "zapri": "Fermer", "prazno": "Le presse-papiers de cet ordinateur ne contient pas de texte.",
           "prilepljeno": "Le texte a été envoyé à l’appareil.", "posiljam": "Envoi des fichiers ({n}) …",
           "poslano": "Fichiers envoyés ({n}).", "ni_poslano": "Les fichiers n’ont pas pu être envoyés.",
           "prostori": "Espaces (Super+Tab)"},
    "it": {"celo": "Schermo intero", "izhod": "Esci dallo schermo intero", "namig": "Tieni premuto Esc per uscire dallo schermo intero",
           "prilepi": "Incolla testo", "prilepi_namig": "Scrive sul dispositivo il testo degli appunti di questo computer",
           "zapri": "Chiudi", "prazno": "Gli appunti di questo computer non contengono testo.",
           "prilepljeno": "Il testo è stato inviato al dispositivo.", "posiljam": "Invio dei file ({n}) …",
           "poslano": "File inviati ({n}).", "ni_poslano": "Non è stato possibile inviare i file.",
           "prostori": "Spazi (Super+Tab)"},
}


def besedilo(jezik: Optional[str], kljuc: str, **vrednosti) -> str:
    b = BESEDILA.get(str(jezik or "en")[:2], BESEDILA["en"]).get(kljuc) or BESEDILA["en"][kljuc]
    for k, v in vrednosti.items():
        b = b.replace("{" + k + "}", str(v))
    return b
