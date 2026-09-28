"""Gesla in zetoni kanalov: samo v sistemski zbirki skrivnosti (libsecret / GNOME Keyring).

Nikoli v nastavitveni datoteki, bazi ali dnevniku. Brez zbirke skrivnosti ostane skrivnost samo v
pomnilniku, dokler Safeer OS tece - ob naslednjem zagonu jo Sporocila vprasajo znova.
"""

from __future__ import annotations

from typing import Callable, Optional

STORITEV = "safeer-sporocila"
_SHEMA = None


def _secret():
    global _SHEMA
    import gi
    gi.require_version("Secret", "1")
    from gi.repository import Secret  # noqa: WPS433
    if _SHEMA is None:
        _SHEMA = Secret.Schema.new("si.safeer.Sporocila", Secret.SchemaFlags.NONE,
                                   {"application": Secret.SchemaAttributeType.STRING,
                                    "key": Secret.SchemaAttributeType.STRING})
    return Secret


def shrani(kljuc: str, vrednost: str) -> bool:
    """True, ce je skrivnost shranjena v sistemsko zbirko; False = samo v pomnilniku."""
    try:
        Secret = _secret()
        return bool(Secret.password_store_sync(_SHEMA, {"application": STORITEV, "key": kljuc},
                                               Secret.COLLECTION_DEFAULT, "Safeer Sporočila", vrednost, None))
    except Exception:
        return False


def preberi(kljuc: str) -> Optional[str]:
    try:
        Secret = _secret()
        return Secret.password_lookup_sync(_SHEMA, {"application": STORITEV, "key": kljuc}, None)
    except Exception:
        return None


def pozabi(kljuc: str) -> None:
    try:
        Secret = _secret()
        Secret.password_clear_sync(_SHEMA, {"application": STORITEV, "key": kljuc}, None)
    except Exception:
        pass


class ManjkaSkrivnost(RuntimeError):
    """Kanal potrebuje geslo ali zeton, ki ga ni (ni zbirke skrivnosti ali je bil pozabljen)."""


def zahtevaj(kljuc: str, v_pomnilniku: Optional[str] = None,
             vnos: Optional[Callable[[], str]] = None) -> str:
    vrednost = v_pomnilniku or preberi(kljuc)
    if not vrednost and vnos is not None:
        vrednost = vnos()
    if not vrednost:
        raise ManjkaSkrivnost("Za povezavo je treba vnesti geslo ali žeton.")
    return vrednost
