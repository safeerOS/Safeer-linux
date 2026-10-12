"""»Vsili temno« v Spletu: strani brez lastne temne razlicice se prikazejo temno (Dark Reader, MIT).

WebKitGTK nima vgrajenega samodejnega temnega nacina (Chrome ga ima). Obracanje barv pokvari slike in videe, zato
uporabimo Dark Reader (core/darkreader/, razlicica in SHA-256 spodaj; licenca MIT v core/darkreader/LICENSE).

- Tece v locenem svetu (stran ga ne vidi in ga ne more izklopiti), samo v glavnem okvirju (manj dela za oglase in
  vgrajene okvirje).
- Strani, ki so ze same temne (izmerjena svetlost ozadja), pusti pri miru - Dark Reader jih sicer pokvari.
- Do odlocitve je ozadje strani temno, da strani ne utripnejo belo.
- Nacini: "izklop", "samodejno" (ko je namizje temno - lastnik, 12. 10. 2026), "vedno". Izjeme po straneh (gostitelj).
"""
from __future__ import annotations

import hashlib
import os
from typing import Iterable, List, Optional

RAZLICICA = "4.9.133"
SHA256 = "82619e7a0bcabbea15a91488bc74fd0f9ba8f8f2a1cc67527f78166037cce166"
SVET = "safeer-temno"
NACINI = ("izklop", "samodejno", "vedno")
PRIVZETO = "samodejno"

BESEDILA = {
    "sl": {"nastavitev": "Temna tema za strani brez nje", "izklop": "Izklopljeno",
           "samodejno": "Ko je namizje temno", "vedno": "Vedno",
           "na_strani_izklopi": "Temno na tej strani: izklopi", "na_strani_vklopi": "Temno na tej strani: vklopi"},
    "en": {"nastavitev": "Dark theme for pages without one", "izklop": "Off",
           "samodejno": "When the desktop is dark", "vedno": "Always",
           "na_strani_izklopi": "Dark on this site: turn off", "na_strani_vklopi": "Dark on this site: turn on"},
    "de": {"nastavitev": "Dunkles Design für Seiten ohne eigenes", "izklop": "Aus",
           "samodejno": "Wenn der Desktop dunkel ist", "vedno": "Immer",
           "na_strani_izklopi": "Dunkel auf dieser Seite: aus", "na_strani_vklopi": "Dunkel auf dieser Seite: ein"},
    "es": {"nastavitev": "Tema oscuro para páginas sin él", "izklop": "Desactivado",
           "samodejno": "Cuando el escritorio es oscuro", "vedno": "Siempre",
           "na_strani_izklopi": "Oscuro en este sitio: desactivar", "na_strani_vklopi": "Oscuro en este sitio: activar"},
    "fr": {"nastavitev": "Thème sombre pour les pages qui n’en ont pas", "izklop": "Désactivé",
           "samodejno": "Quand le bureau est sombre", "vedno": "Toujours",
           "na_strani_izklopi": "Sombre sur ce site : désactiver", "na_strani_vklopi": "Sombre sur ce site : activer"},
    "it": {"nastavitev": "Tema scuro per le pagine che non lo hanno", "izklop": "Disattivato",
           "samodejno": "Quando il desktop è scuro", "vedno": "Sempre",
           "na_strani_izklopi": "Scuro su questo sito: disattiva", "na_strani_vklopi": "Scuro su questo sito: attiva"},
}

# Odlocitev ob DOMContentLoaded: ce je ozadje strani ze temno (svetlost < 0,35), Dark Reader ne tece.
KRMILNIK = r"""
;(function () {
  if (window.top !== window || window.__safeerTemno) return;
  window.__safeerTemno = true;
  var D = window.DarkReader; if (!D) return;
  var zgodaj = document.createElement('style');
  zgodaj.textContent = 'html{background:#181a1b!important;color-scheme:dark}';
  (document.head || document.documentElement).appendChild(zgodaj);
  function svetlost(el) {
    if (!el) return null;
    var m = (getComputedStyle(el).backgroundColor || '').match(/[\d.]+/g);
    if (!m || m.length < 3 || (m.length > 3 && +m[3] === 0)) return null;
    return 0.2126 * m[0] / 255 + 0.7152 * m[1] / 255 + 0.0722 * m[2] / 255;
  }
  function odloci() {
    zgodaj.remove();
    var s = svetlost(document.body);
    if (s === null) s = svetlost(document.documentElement);
    if (s === null) s = 1;
    if (s < 0.35) return;
    try { D.setFetchMethod(window.fetch.bind(window)); } catch (e) {}
    try { D.enable({ brightness: 100, contrast: 100, sepia: 0 }); } catch (e) {}
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', odloci, { once: true });
  else odloci();
})();
"""

_koda: Optional[str] = None


def besedilo(jezik: str, kljuc: str) -> str:
    return BESEDILA.get(jezik, BESEDILA["en"]).get(kljuc, BESEDILA["en"][kljuc])


def pot_skripte(koren_core: str) -> str:
    return os.path.join(koren_core, "darkreader", "darkreader.js")


def koda(koren_core: str) -> Optional[str]:
    """Dark Reader + krmilnik; None, ce datoteke ni ali se kontrolna vsota ne ujema (ne izvajamo spremenjene kode)."""
    global _koda
    if _koda is None:
        try:
            with open(pot_skripte(koren_core), "rb") as d:
                vsebina = d.read()
            if hashlib.sha256(vsebina).hexdigest() != SHA256:
                print("[Safeer OS Splet] Dark Reader: kontrolna vsota se ne ujema - vsili temno je izklopljen")
                _koda = ""
            else:
                _koda = vsebina.decode("utf-8") + KRMILNIK
        except OSError:
            _koda = ""
    return _koda or None


def gostitelj(uri: str) -> str:
    try:
        from urllib.parse import urlsplit
        return (urlsplit(uri or "").hostname or "").lower().removeprefix("www.")
    except Exception:
        return ""


def vzorci_izjem(izjeme: Iterable[str]) -> List[str]:
    out: List[str] = ["file://*", "about:*", "safeer:*"]
    for g in izjeme or ():
        g = str(g).strip().lower().removeprefix("www.")
        if g and "/" not in g and "*" not in g:
            out += ["*://%s/*" % g, "*://*.%s/*" % g]
    return out


def dejaven(nacin: str, namizje_temno: bool) -> bool:
    if nacin not in NACINI:
        nacin = PRIVZETO
    return nacin == "vedno" or (nacin == "samodejno" and namizje_temno)


def namesti(W, upravitelj, koren_core: str, nacin: str, namizje_temno: bool, izjeme: Iterable[str]):
    """Doda skripto v upravitelja vsebine pogleda; vrne UserScript (za kasnejso odstranitev) ali None."""
    if not dejaven(nacin, namizje_temno):
        return None
    k = koda(koren_core)
    if not k:
        return None
    skripta = W.UserScript.new_for_world(k, W.UserContentInjectedFrames.TOP_FRAME, W.UserScriptInjectionTime.START,
                                         SVET, None, vzorci_izjem(izjeme))
    upravitelj.add_script(skripta)
    return skripta


def odstrani(upravitelj, skripta) -> None:
    if skripta is not None:
        try:
            upravitelj.remove_script(skripta)
        except Exception:
            pass
