"""Odločitve za lahek življenjski cikel zavihkov, brez odvisnosti od GTK-ja."""

from __future__ import annotations

from typing import Iterable, Optional


def dejanje_zavihka(*, neaktiven_od: Optional[float], zdaj: float, aktiven: bool,
                     zvok: bool, zasciten: bool, zamrznjen: bool,
                     zamrzni_po: float, zavrzi_po: float) -> str:
    """Vrne ``zamrzni``, ``zavrzi``, ``obnovi`` ali prazen niz.

    Nicelna meja posamezni korak izklopi. Aktivni, zvočni in drugače zaščiteni
    zavihki se vedno odmrznejo in se nikoli ne zavržejo.
    """
    if aktiven or zvok or zasciten:
        return "obnovi" if zamrznjen else ""
    if neaktiven_od is None:
        return ""
    starost = max(0.0, zdaj - neaktiven_od)
    if zavrzi_po > 0 and starost >= zavrzi_po:
        return "zavrzi"
    if zamrzni_po > 0 and starost >= zamrzni_po and not zamrznjen:
        return "zamrzni"
    return ""


def pomnilnik(proc_meminfo: str) -> tuple[int, int]:
    """Iz vsebine /proc/meminfo vrne (MemAvailable, MemTotal) v kB."""
    vrednosti = {}
    for vrstica in proc_meminfo.splitlines():
        deli = vrstica.replace(":", " ").split()
        if len(deli) >= 2 and deli[0] in ("MemAvailable", "MemTotal"):
            try:
                vrednosti[deli[0]] = int(deli[1])
            except ValueError:
                pass
    return vrednosti.get("MemAvailable", 0), vrednosti.get("MemTotal", 0)


def je_pomnilniski_pritisk(proc_meminfo: str, meja: float = 0.10) -> bool:
    razpolozljivo, skupaj = pomnilnik(proc_meminfo)
    return skupaj > 0 and razpolozljivo / skupaj < meja


def najstarejsi_neaktivni(zavihki: Iterable[dict]) -> list[dict]:
    """Za pritisk vrne varne neaktivne zavihke, najstarejše najprej."""
    kandidati = [z for z in zavihki
                 if not z.get("active") and not z.get("audio") and not z.get("protected")
                 and not z.get("sleeping") and z.get("inactive_since") is not None]
    return sorted(kandidati, key=lambda z: (z["inactive_since"], z.get("id", "")))


def izberi_za_sprostitev(zavihki: Iterable[dict], manjkajoce_kb: int) -> list[dict]:
    """Izbere najstarejše zavihke do ocenjenega 10-% pomnilniškega praga."""
    izbrani, sprosceno = [], 0
    cilj = max(1, int(manjkajoce_kb))
    for zavihek in najstarejsi_neaktivni(zavihki):
        izbrani.append(zavihek)
        # Proces še ni nujno vzorčen; zmernih 128 MiB prepreči, da bi zaradi
        # enega manjkajočega podatka takoj zavrgli vso sejo.
        sprosceno += max(128 * 1024, int(zavihek.get("rss_mb") or 0) * 1024)
        if sprosceno >= cilj:
            break
    return izbrani
