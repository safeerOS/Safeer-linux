"""Pomoc preizkusom: besedila delovne povrsine in namizja QML so v enem slovarju assets/os/besedila-namizja.js
(sl, en, de, es, fr, it - pregled celovitosti 15. 10. 2026). Prej je imel vsak slovar svoja sl in en v delovna.js
oziroma Namizje.qml, zato so preizkusi steli »kljuc:« dvakrat; zdaj je vsak kljuc v vseh sestih jezikih."""
import os
import re

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JEZIKOV = 6


def besedila() -> str:
    with open(os.path.join(KOREN, "assets", "os", "besedila-namizja.js"), encoding="utf-8") as f:
        return f.read()


def stevilo(kljuc: str) -> int:
    """V koliko jezikih je kljuc (natancno to ime, ne qml_/win_ razlicica)."""
    return len(re.findall(r"^    %s: " % re.escape(kljuc), besedila(), re.M))
