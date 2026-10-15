"""Poraba strojne opreme posameznih kanalov Sporocil (gumb »Info«, lastnik 15. 10. 2026: »da se lazje odloci, kateri
kanal potrebuje«). Cisti izracuni brez GTK in WebKit - vzorcenje in pripis procesov je v core/os_poraba_kanalov.py.

Merila (nic izmisljenega):
  * pomnilnik = PSS (Proportional Set Size) iz /proc/<pid>/smaps_rollup: deljene strani so razdeljene med procese, ki
    jih delijo, zato se vsota ne sesteva dvakrat (RSS bi knjiznice WebKita stel pri vsakem procesu znova);
  * procesor = utime + stime iz /proc/<pid>/stat med dvema vzorcema, v odstotkih enega jedra (100 % = eno jedro);
  * povprecje = povprecje vzorcev (vsakih 30 s) v drsecem oknu zadnje ure in od zagona Safeer OS.
"""
from __future__ import annotations

import os
import time
from collections import deque
from typing import Dict, Iterable, List, Optional

#: Vzorec vsakih toliko sekund (nizka prednost; brez kanalov se ne meri nic).
VZOREC_S = 30
#: Drsece okno povprecja.
OKNO_S = 3600


class Proc:
    """Branje /proc (koren je nastavljiv za preizkuse z laznim /proc)."""

    def __init__(self, koren: str = "/proc") -> None:
        self.koren = koren
        #: V peskovniku Flatpaka je v nasem imenskem prostoru procesov samo Safeer OS s svojimi procesi.
        self.flatpak = os.path.exists("/.flatpak-info")
        try:
            self.hz = os.sysconf("SC_CLK_TCK") or 100
        except (ValueError, OSError, AttributeError):
            self.hz = 100

    def _beri(self, pid: int, ime: str) -> str:
        try:
            with open(os.path.join(self.koren, str(int(pid)), ime), encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    def _stat(self, pid: int) -> List[str]:
        s = self._beri(pid, "stat")
        if ")" not in s:
            return []
        return s.rsplit(")", 1)[1].split()

    def zivi(self, pid: int) -> bool:
        return bool(pid) and bool(self._stat(pid))

    def ime(self, pid: int) -> str:
        return self._beri(pid, "comm").strip()

    def stars(self, pid: int) -> int:
        d = self._stat(pid)
        try:
            return int(d[1])
        except (IndexError, ValueError):
            return 0

    def tiki(self, pid: int) -> int:
        """utime + stime (v tikih ure, SC_CLK_TCK na sekundo)."""
        d = self._stat(pid)
        try:
            return int(d[11]) + int(d[12])
        except (IndexError, ValueError):
            return 0

    def pomnilnik(self, pid: int) -> tuple:
        """(KiB, natancno): PSS iz smaps_rollup; ce ga ni mogoce brati (staro jedro, proces v drugem uporabniskem
        imenskem prostoru - podpeskovnik Flatpaka, kjer smaps zahteva pravico ptrace), RSS iz status: priblizek
        (deljene knjiznice steje v celoti), vmesnik ga oznaci z »≈«."""
        for vrstica in self._beri(pid, "smaps_rollup").splitlines():
            if vrstica.startswith("Pss:"):
                try:
                    return int(vrstica.split()[1]), True
                except (IndexError, ValueError):
                    return 0, True
        for vrstica in self._beri(pid, "status").splitlines():
            if vrstica.startswith("VmRSS:"):
                try:
                    return int(vrstica.split()[1]), False
                except (IndexError, ValueError):
                    return 0, False
        return 0, False

    def pss_kib(self, pid: int) -> int:
        return self.pomnilnik(pid)[0]

    def starsi(self) -> Dict[int, int]:
        """pid -> stars za vse vidne procese (en prehod cez /proc)."""
        izid: Dict[int, int] = {}
        try:
            imena = os.listdir(self.koren)
        except OSError:
            return izid
        for ime in imena:
            if ime.isdigit() and self._stat(int(ime)):
                izid[int(ime)] = self.stars(int(ime))
        return izid

    def otroci(self, starsi: Optional[Dict[int, int]] = None) -> Dict[int, List[int]]:
        """stars -> otroci za vse procese (en prehod cez /proc)."""
        izid: Dict[int, List[int]] = {}
        for pid, s in (starsi if starsi is not None else self.starsi()).items():
            if s:
                izid.setdefault(s, []).append(pid)
        return izid

    @staticmethod
    def koren_verige(pid: int, starsi: Dict[int, int]) -> int:
        """Prvi prednik, katerega stars ni viden v tem imenskem prostoru procesov (stars 0)."""
        videni = set()
        while pid in starsi and starsi[pid] and pid not in videni and len(videni) < 256:
            videni.add(pid)
            pid = starsi[pid]
        return pid

    def nasi(self, koren_pid: int, ime: str, starsi: Optional[Dict[int, int]] = None) -> tuple:
        """Procesi z imenom `ime`, ki pripadajo programu `koren_pid`: (v drevesu, v podpeskovniku).

        Zunaj Flatpaka so spletni procesi WebKita potomci programa (bwrap je otrok); procesi drugih programov se
        koncajo v pid 1 in niso nasi, nas je se proces, katerega veriga se konca v korenu z nevidnim starsem.
        V Flatpaku (/.flatpak-info) jih WebKit zazene prek flatpak-spawn --sandbox: zivo drevo s testnega PC
        (15. 10. 2026) je WebKitWebProcess -> bwrap podpeskovnika -> 1 (bwrap nasega peskovnika), ne do Safeer OS.
        V nasem imenskem prostoru procesov so samo nasi procesi, zato je tam vsak tak proces nas."""
        starsi = starsi if starsi is not None else self.starsi()
        drevo = set(self.drevo(koren_pid, self.otroci(starsi)))
        nas_koren = self.koren_verige(koren_pid, starsi)
        v_drevesu, podpeskovnik = [], []
        for pid in starsi:
            if self.ime(pid) != ime:
                continue
            if pid in drevo:
                v_drevesu.append(pid)
                continue
            if self.flatpak:
                podpeskovnik.append(pid)       # v Flatpaku je vsak tak proces v nasem imenskem prostoru nas
                continue
            k = self.koren_verige(pid, starsi)
            if k not in (1, 2, nas_koren) and starsi.get(k, 0) == 0:
                podpeskovnik.append(pid)
        return sorted(v_drevesu), sorted(podpeskovnik)

    def drevo(self, pid: int, otroci: Optional[Dict[int, List[int]]] = None) -> List[int]:
        """pid in vsi potomci (ziv proces); prazno, ce procesa ni."""
        if not self.zivi(pid):
            return []
        otroci = otroci if otroci is not None else self.otroci()
        izid, vrsta = [], [int(pid)]
        while vrsta:
            p = vrsta.pop()
            if p in izid:
                continue
            izid.append(p)
            vrsta.extend(otroci.get(p, []))
        return izid

    def koren_programa(self, pid: int) -> int:
        """Okno programa ima lahko podproces z istim imenom (zaganjalnik, Electron): navzgor, dokler je ime enako."""
        ime = self.ime(pid)
        while ime:
            s = self.stars(pid)
            if s <= 1 or self.ime(s) != ime:
                break
            pid = s
        return pid


def cpu_odstotek(tiki_prej: int, tiki_zdaj: int, sekund: float, hz: int) -> Optional[float]:
    """Odstotek enega jedra med vzorcema; None, ce ni mogoce (premalo casa, stevec se je zmanjsal = drug proces)."""
    if sekund <= 0 or hz <= 0 or tiki_zdaj < tiki_prej:
        return None
    return round((tiki_zdaj - tiki_prej) / float(hz) / sekund * 100.0, 1)


class Zgodovina:
    """Vzorci po kljucu (kanal): pomnilnik (MiB) in procesor (%) - drsece okno zadnje ure in vsota od zagona."""

    def __init__(self, okno_s: int = OKNO_S) -> None:
        self.okno_s = okno_s
        self._ura: Dict[str, deque] = {}
        self._zagon: Dict[str, list] = {}       # [vsota_mem, n_mem, vsota_cpu, n_cpu, prvi_cas]

    def dodaj(self, kljuc: str, cas: float, mem_mib: Optional[float], cpu: Optional[float]) -> None:
        d = self._ura.setdefault(kljuc, deque())
        d.append((cas, mem_mib, cpu))
        while d and cas - d[0][0] > self.okno_s:
            d.popleft()
        z = self._zagon.setdefault(kljuc, [0.0, 0, 0.0, 0, cas])
        if mem_mib is not None:
            z[0] += mem_mib
            z[1] += 1
        if cpu is not None:
            z[2] += cpu
            z[3] += 1

    def pozabi(self, kljuc: str) -> None:
        self._ura.pop(kljuc, None)
        self._zagon.pop(kljuc, None)

    def povzetek(self, kljuc: str, zdaj: Optional[float] = None) -> dict:
        zdaj = time.monotonic() if zdaj is None else zdaj
        vzorci = [v for v in self._ura.get(kljuc, ()) if zdaj - v[0] <= self.okno_s]
        mem = [v[1] for v in vzorci if v[1] is not None]
        cpu = [v[2] for v in vzorci if v[2] is not None]
        z = self._zagon.get(kljuc)
        return {
            "mem_ura": round(sum(mem) / len(mem), 1) if mem else None,
            "cpu_ura": round(sum(cpu) / len(cpu), 1) if cpu else None,
            "mem_zagon": round(z[0] / z[1], 1) if z and z[1] else None,
            "cpu_zagon": round(z[2] / z[3], 1) if z and z[3] else None,
            "vzorcev": len(vzorci),
            "od_s": round(zdaj - z[4]) if z else 0,
        }


def velikost_mape(pot: str, najvec_datotek: int = 200000) -> int:
    """Bajti datotek v mapi (brez sledenja povezavam); 0, ce mape ni."""
    skupaj, n, vrsta = 0, 0, [pot]
    while vrsta and n < najvec_datotek:
        try:
            vnosi = list(os.scandir(vrsta.pop()))
        except OSError:
            continue
        for v in vnosi:
            try:
                if v.is_dir(follow_symlinks=False):
                    vrsta.append(v.path)
                elif v.is_file(follow_symlinks=False):
                    skupaj += v.stat(follow_symlinks=False).st_size
                    n += 1
            except OSError:
                continue
    return skupaj


def sestej(vrstice: Iterable[dict], polja=("mem_trenutno", "mem_ura", "mem_zagon", "cpu_trenutno", "cpu_ura",
                                          "cpu_zagon", "disk")) -> dict:
    """Vrstica SKUPAJ: vsota merljivih vrednosti. »<polje>_delno«: vsaj en vklopljen kanal tega ni merljiv locno
    (vrstica ima polje v »ni_merljivo«) - vsota je spodnja meja, vmesnik to pove."""
    vrstice = list(vrstice)
    izid: dict = {}
    for polje in polja:
        stevila = [v[polje] for v in vrstice if isinstance(v.get(polje), (int, float))]
        izid[polje] = round(sum(stevila), 1) if stevila else None
        izid[polje + "_delno"] = any(polje in (v.get("ni_merljivo") or ()) and v.get("vklopljen", True)
                                     for v in vrstice)
    return izid
