"""Izbira najlažje poti za spletno vsebino Safeer Media."""

from urllib.parse import urlsplit


NEPOSREDNE_KONCNICE = frozenset({
    ".mp4", ".m4v", ".m3u8", ".mpd", ".ts", ".mp3", ".m4a", ".aac", ".flac", ".wav",
    ".webm", ".ogg", ".oga", ".ogv", ".opus", ".mov", ".mkv", ".avi",
})


def je_spletni_naslov(naslov: str) -> bool:
    try:
        u = urlsplit(str(naslov or "").strip())
        return u.scheme.lower() in ("http", "https") and bool(u.netloc)
    except ValueError:
        return False


def je_neposredni_medij(naslov: str) -> bool:
    """Končnico preveri samo v poti, zato poizvedba in fragment ne motita."""
    if not je_spletni_naslov(naslov):
        return False
    pot = urlsplit(naslov).path.lower()
    return any(pot.endswith(koncnica) for koncnica in NEPOSREDNE_KONCNICE)


def izberi_nivo(naslov: str) -> str:
    """Vrne ``neposredno``, ``lahki_splet`` ali prazen niz za nedovoljen URL."""
    if not je_spletni_naslov(naslov):
        return ""
    return "neposredno" if je_neposredni_medij(naslov) else "lahki_splet"
