"""Safeer OS -> Scit v svojem procesu (core/scit_proces.py): isti vmesnik kot core/os_scit.Scit za safeer_os.py.

Klici gredo prek vticnice scit.sock (en JSON v vrstici). Kar safeer_os klice na glavni niti (stanje_pulta(preveri=False),
naprej(), twitch_brez_oglasov()), vrne zadnje znano stanje brez cakanja. Ce proces Scit ravno ni dosegljiv (ponovni
zagon), klic vrne zadnje znano stanje - vmesnik se ne zatakne in ne pokaze lazne napake.
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
from typing import Any, Optional, Tuple

#: Rok klica (s). Vklop Scita lahko caka na geslo (pkexec, do 180 s v os_scit.namesti_pravilo); ostalo zazene najvec
#: nekaj kratkih podprocesov (resolvectl, pkcheck).
ROK_S = 30.0
ROK_VKLOPA_S = 200.0


class ScitOdjemalec:
    def __init__(self, shramba, pot: str) -> None:
        self.shramba = shramba
        self.pot = pot
        self._kljuc = threading.Lock()
        self._stanje: dict = {}
        self._cas = 0.0
        from core import os_scit
        os_scit.zunanje_nesifrirano = lambda: bool(self._stanje.get("nesifrirano"))

    # ------------------------------------------------------------------ prenos
    def _klic(self, metoda: str, rok: float = ROK_S, **argumenti) -> Optional[Any]:
        zahteva = json.dumps({"m": metoda, "a": argumenti}, ensure_ascii=False).encode("utf-8") + b"\n"
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC) as s:
                s.settimeout(rok)
                s.connect(self.pot)
                s.sendall(zahteva)
                podatki = b""
                while not podatki.endswith(b"\n"):
                    del_ = s.recv(65536)
                    if not del_:
                        break
                    podatki += del_
            odgovor = json.loads(podatki.decode("utf-8"))
        except (OSError, ValueError, UnicodeError) as e:
            print("[SafeerOS] scit (proces) %s: %s" % (metoda, e), flush=True)
            return None
        if not isinstance(odgovor, dict) or "ok" not in odgovor:
            print("[SafeerOS] scit (proces) %s: %s" % (metoda, odgovor), flush=True)
            return None
        return odgovor["ok"]

    def _stanje_iz(self, izid: Optional[Any], spremenjeno: bool = False) -> dict:
        """Novo stanje (ali zadnje znano, ce klic ni uspel); po spremembi tudi kljuce os.json iz procesa Scit."""
        if isinstance(izid, dict):
            with self._kljuc:
                self._stanje = dict(self._stanje, **izid)
                self._cas = time.monotonic()
        if spremenjeno:
            try:
                self.shramba.osvezi()
            except Exception:  # noqa: BLE001
                pass
        return dict(self._stanje) if not isinstance(izid, dict) else izid

    # ------------------------------------------------------------------ isti vmesnik kot os_scit.Scit
    def stanje(self) -> dict:
        return self._stanje_iz(self._klic("stanje"))

    def stanje_pulta(self, preveri: bool = True) -> dict:
        if not preveri:
            return dict(self._stanje)
        return self._stanje_iz(self._klic("stanje_pulta"))

    def razlog_svez(self) -> bool:
        """Pult naj stanje vedno vprasa v svoji niti (klic v proces), ne na glavni niti."""
        return False

    def nastavi(self, vklop: bool) -> dict:
        return self._stanje_iz(self._klic("nastavi", ROK_VKLOPA_S, vklop=bool(vklop)), True)

    def dovoli(self, domena, dovoli: bool = True) -> dict:
        return self._stanje_iz(self._klic("dovoli", domena=str(domena or ""), dovoli=bool(dovoli)), True)

    def premor(self, minut) -> dict:
        minut = minut if isinstance(minut, (int, float)) and not isinstance(minut, bool) else 0
        return self._stanje_iz(self._klic("premor", minut=minut))

    def nastavi_twitch(self, vklop: bool) -> dict:
        return self._stanje_iz(self._klic("nastavi_twitch", vklop=bool(vklop)), True)

    def nastavi_naprej(self, izbira, po_meri="") -> dict:
        stanje = self._stanje_iz(self._klic("nastavi_naprej", izbira=str(izbira or ""), po_meri=str(po_meri or "")),
                                 True)
        doh = sys.modules.get("core.doh_proxy")
        if doh is not None:
            try:
                doh.osvezi_naprej()       # isti streznik naprej takoj tudi v Spletu (en vir nastavitve)
            except Exception:  # noqa: BLE001
                pass
        return stanje

    def naprej(self) -> Tuple[str, str]:
        from core import os_scit
        if "naprej" in self._stanje:
            izbira, po_meri = str(self._stanje.get("naprej") or ""), str(self._stanje.get("naprejPoMeri") or "")
        else:
            izbira = str(self.shramba.get("scit_naprej", os_scit.PRIVZETI_NAPREJ) or "")
            po_meri = str(self.shramba.get("scit_naprej_po_meri", "") or "")
        return (izbira if izbira in os_scit.IZBIRE_NAPREJ else os_scit.PRIVZETI_NAPREJ), po_meri

    def twitch_brez_oglasov(self) -> bool:
        if "twitchOglasi" in self._stanje:
            return self._stanje["twitchOglasi"] is not False
        return self.shramba.get("scit_twitch_oglasi", True) is not False

    @property
    def vklopljen(self) -> bool:
        return bool(self._stanje.get("vklop", self.shramba.get("scit", False)))

    def zacni_ce_vklopljen(self) -> None:
        """Proces Scit se zazene sam (varuh); tu samo prvo stanje v ozadju - pult in Splet ga imata takoj."""
        threading.Thread(target=self.stanje_pulta, name="safeer-scit-prvo", daemon=True).start()

    def koncaj(self) -> None:
        """Konec Safeer OS ne ustavi Scita: DNS vrne proces Scit, ko ga varuh ob koncu seje ustavi."""
