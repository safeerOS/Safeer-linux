"""Sistemski posrednik namizja za cas, ko gre internet skozi telefon (core/link_internet_posrednik.py).

Brskalniki in programi GTK berejo posrednika iz gsettings sheme `org.gnome.system.proxy`. Firefox ji
sledi povsod, kjer shema obstaja; brskalniki na osnovi Chromiuma na namizjih GNOME, Cinnamon in tistih,
ki jih Chromium obravnava enako (Unity, Pantheon, Deepin, UKUI, COSMIC, seja »mate«) - na Xfce in LXQt
berejo samo spremenljivke okolja (Chromium: net/proxy_resolution/proxy_config_service_linux.cc).
Safeer shemo za cas izpada nastavi na svoj krajevni posrednik in jo potem vrne TOCNO taksno, kot je bila:

  * prejsnje vrednosti se pred prvo spremembo zapisejo na disk - ce Safeer Control med izpadom pade,
    jih naslednji zagon vrne (`ob_zagonu`);
  * vrne se samo kljuc, ki ima se naso vrednost. Kar je uporabnik medtem sam spremenil, ostane njegovo.

KDE (kioslaverc) in programi, ki sistemskega posrednika ne berejo (apt, ukazna vrstica), niso pokriti:
`podprt()` na takem namizju vrne False in vmesnik stikala ne ponudi.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from typing import Callable, Dict, List, Optional, Tuple

SHEMA = "org.gnome.system.proxy"
GOSTITELJ = "127.0.0.1"
#: (shema, kljuc) v vrstnem redu nastavljanja; `mode` gre ob vklopu zadnji, ob izklopu prvi.
KLJUCI: Tuple[Tuple[str, str], ...] = (
    (SHEMA + ".http", "host"), (SHEMA + ".http", "port"),
    (SHEMA + ".https", "host"), (SHEMA + ".https", "port"),
    (SHEMA + ".socks", "host"), (SHEMA + ".socks", "port"),
    (SHEMA, "mode"),
)


def _gsettings(*argumenti: str) -> Optional[str]:
    """Pozene gsettings. Vrne izpis ali None ob napaki."""
    try:
        o = subprocess.run(["gsettings", *argumenti], capture_output=True, text=True, timeout=6)
    except (OSError, subprocess.SubprocessError):
        return None
    if o.returncode != 0:
        return None
    return o.stdout.strip()


def _v_flatpaku() -> bool:
    return bool(os.environ.get("FLATPAK_ID")) or os.path.exists("/.flatpak-info")


def _ime(shema: str, kljuc: str) -> str:
    return shema + " " + kljuc


class SistemskiPosrednik:
    def __init__(self, pot_stanja: str, gsettings: Callable[..., Optional[str]] = _gsettings,
                 okolje: Optional[Dict[str, str]] = None) -> None:
        self.pot_stanja = pot_stanja
        self._gsettings = gsettings
        self._okolje = os.environ if okolje is None else okolje
        self._zaklep = threading.Lock()
        self._podprt: Optional[bool] = None
        self._vrata = 0                      # vrata, ki so trenutno nastavljena (0 = nismo nastavili)

    # ------------------------------------------------------------------ podpora

    def podprt(self) -> bool:
        """Ali ima to namizje shemo, ki jo programi berejo, in jo lahko nastavimo."""
        if self._podprt is None:
            self._podprt = self._preveri_podporo()
        return self._podprt

    def _preveri_podporo(self) -> bool:
        if self._gsettings is _gsettings:
            pot = shutil.which("gsettings")
            if not pot:
                return False
            if _v_flatpaku() and "/host-bin/" not in pot:
                return False                  # gsettings v peskovniku ne nastavlja namizja gostitelja
        namizje = str(self._okolje.get("XDG_CURRENT_DESKTOP") or "").lower()
        if "kde" in namizje:
            return False                      # Plasma bere kioslaverc, ne te sheme
        return self._gsettings("get", SHEMA, "mode") is not None

    def _vrednosti(self, vrata: int) -> Dict[str, str]:
        return {_ime(s, k): ("'manual'" if k == "mode" else "'%s'" % GOSTITELJ if k == "host" else str(int(vrata)))
                for s, k in KLJUCI}

    # ------------------------------------------------------------------ stanje na disku

    def _preberi_stanje(self) -> Optional[dict]:
        try:
            with open(self.pot_stanja, "r", encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            return None
        return d if isinstance(d, dict) and isinstance(d.get("prej"), dict) else None

    def _zapisi_stanje(self, d: dict) -> bool:
        try:
            os.makedirs(os.path.dirname(self.pot_stanja), exist_ok=True)
            zacasna = self.pot_stanja + ".tmp"
            with open(zacasna, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            os.replace(zacasna, self.pot_stanja)
            return True
        except OSError:
            return False

    def nastavljen(self) -> bool:
        """Ali je sistemski posrednik zdaj nas (hitro: brez klica gsettings)."""
        return self._vrata > 0 or os.path.exists(self.pot_stanja)

    # ------------------------------------------------------------------ vklop in izklop

    def vklopi(self, vrata: int) -> bool:
        """Nastavi sistemski posrednik na 127.0.0.1:vrata. Prejsnje vrednosti prej zapise na disk."""
        if not self.podprt() or not 1 <= int(vrata) <= 65535:
            return False
        with self._zaklep:
            if self._vrata == int(vrata):
                return True
            stanje = self._preberi_stanje()
            if stanje is None:
                prej: Dict[str, str] = {}
                for s, k in KLJUCI:
                    v = self._gsettings("get", s, k)
                    if v is None:
                        return False
                    prej[_ime(s, k)] = v
                # Brez zapisa prejsnjih vrednosti ne spremenimo nicesar: sicer jih ne bi znali vrniti.
                if not self._zapisi_stanje({"prej": prej, "vrata": int(vrata)}):
                    return False
            else:
                stanje["vrata"] = int(vrata)
                self._zapisi_stanje(stanje)
            nase = self._vrednosti(int(vrata))
            for s, k in KLJUCI:
                if self._gsettings("set", s, k, nase[_ime(s, k)]) is None:
                    self._vrata = int(vrata)       # delno nastavljeno: izklop naj pospravi
                    self._izklopi_zaklenjeno()
                    return False
            self._vrata = int(vrata)
            return True

    def izklopi(self) -> bool:
        """Vrne prejsnje vrednosti (samo kljucem, ki imajo se naso vrednost)."""
        with self._zaklep:
            return self._izklopi_zaklenjeno()

    def _izklopi_zaklenjeno(self) -> bool:
        if self._vrata == 0 and not os.path.exists(self.pot_stanja):
            return True
        stanje = self._preberi_stanje()
        if stanje is None:
            # Datoteka je pokvarjena ali je ni: nimamo cesa vrniti. Nacin posrednika vsaj ne sme ostati nas.
            self._vrata = 0
            try:
                os.remove(self.pot_stanja)
            except OSError:
                pass
            return False
        try:
            vrata = int(stanje.get("vrata") or self._vrata or 0)
        except (TypeError, ValueError):
            vrata = self._vrata
        nase = self._vrednosti(vrata) if vrata else {}
        prej = stanje["prej"]
        ok = True
        for s, k in reversed(KLJUCI):
            ime = _ime(s, k)
            stara = prej.get(ime)
            if not isinstance(stara, str):
                continue
            trenutna = self._gsettings("get", s, k)
            if trenutna is None:
                ok = False
                continue
            if nase and trenutna != nase.get(ime):
                continue                       # uporabnik je medtem nastavil svoje: ne prepisujemo
            if trenutna != stara and self._gsettings("set", s, k, stara) is None:
                ok = False
        if ok:
            self._vrata = 0
            try:
                os.remove(self.pot_stanja)
            except OSError:
                pass
        return ok

    def ob_zagonu(self) -> None:
        """Po sesutju med izpadom: vrne, kar je ostalo nastavljeno."""
        if os.path.exists(self.pot_stanja) and self.podprt():
            self.izklopi()

    def opis(self) -> List[str]:
        """Trenutne vrednosti (za diagnostiko)."""
        return ["%s = %s" % (_ime(s, k), self._gsettings("get", s, k)) for s, k in KLJUCI]
