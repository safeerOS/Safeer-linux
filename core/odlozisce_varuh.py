"""Varuh odložišča za poglede WebKitGTK.

WebKitGTK ob ukazu Kopiraj (Ctrl+C, Ctrl+Insert) brez izbranega besedila v odložišče zapiše prazno vsebino: kar je
uporabnik kopiral prej, je izgubljeno. Izmerjeno na 2.52.6 s stranjo brez ene same skripte; v izvorni kodi je
vzrok od 2.48 (`Editor::canCopy` vrne true tudi za kazalko zunaj polja za vnos, zapis praznega izbora pa na GTK
odložišče počisti).

Skripta posluša dogodek `copy`. Kadar ni ničesar izbranega in fokus ni v polju za vnos, privzeto dejanje prekliče;
preklican dogodek brez podatkov odložišča ne spremeni (v izvorni kodi vsaj od 2.38). Na starejših izdajah brez
napake se zato nič ne spremeni.

Strani, ki dogodek `copy` obdelajo same (preglednice, risalniki), delujejo kot prej: varuh pride na vrsto za
njihovimi poslušalci in se umakne, če so privzeto dejanje že preklicale. Kjer ne more zanesljivo vedeti, ali je
kaj izbrano (polje za vnos, element z morda zaprto senco, samostojna slika), ne naredi ničesar. Izbor, ki je ostal v
skritem delu strani (brez besedila in brez česarkoli narisanega), šteje kot »nič izbranega«.

Teče v svojem svetu skript: stran ga ne vidi in mu ne more podtakniti svojih funkcij.
"""

SVET = "SafeerVaruhOdlozisca"

SKRIPTA = r"""(function () {
  "use strict";
  // Zastavica zivi v svetu skripte (stran je ne vidi); sorodni pogledi si delijo upravitelja, skripta pride veckrat.
  if (window.__safeerVaruhOdlozisca) return;
  window.__safeerVaruhOdlozisca = true;
  var dodaj = window.addEventListener.bind(window);
  var NI_BESEDILO = { button: 1, checkbox: 1, color: 1, file: 1, image: 1, radio: 1, range: 1, reset: 1, submit: 1 };

  function aktiven() {
    var a = document.activeElement;
    while (a && a.shadowRoot && a.shadowRoot.activeElement) a = a.shadowRoot.activeElement;
    return a;
  }
  function vUrejanju(el) {
    if (!el || el.nodeType !== 1) return false;
    if (el.isContentEditable === true) return true;
    var ime = String(el.tagName || "").toUpperCase();
    if (ime === "TEXTAREA") return true;
    return ime === "INPUT" && !NI_BESEDILO[String(el.type || "").toLowerCase()];
  }
  // Lasten element brez dostopne sence ima lahko zaprto senco s poljem za vnos, ki ga od zunaj ne vidimo.
  function mordaZaprtaSenca(el) {
    return !!el && el.nodeType === 1 && String(el.tagName || "").indexOf("-") > 0 && !el.shadowRoot;
  }
  // Besedilo izbora pove resnico tudi tam, kjer vrsta in obseg ne (izbor v senci je navzven videti strnjen).
  function imaBesedilo(s) { try { return String(s) !== ""; } catch (x) { return false; } }
  // Izbor, ki ga ni kaj kopirati: brez besedila in brez cesarkoli narisanega. Tak ostane v delu strani, ki se je
  // medtem skril (izmerjeno na 2.52.6: type=Range, besedilo prazno; Kopiraj je odlozisce izpraznil). Izbor brez
  // besedila z narisano vsebino (slika) ni tak. Kjer obsegov ne moremo pregledati, ne ugibamo.
  function izborBrezVsebine(s) {
    try {
      if (String(s) !== "" || !(s.rangeCount > 0)) return false;
      for (var i = 0; i < s.rangeCount; i++) {
        var r = s.getRangeAt(i);
        if (!r.collapsed && r.getClientRects().length > 0) return false;
      }
      return true;
    } catch (x) { return false; }
  }
  function niKajKopirati(e) {
    if (e.defaultPrevented) return false;
    if (document.designMode === "on") return false;
    if (String(document.contentType || "").indexOf("image/") === 0) return false;
    var s = window.getSelection ? window.getSelection() : null;
    if (s && (s.type === "Range" || (s.rangeCount > 0 && !s.isCollapsed) || imaBesedilo(s)) && !izborBrezVsebine(s)) return false;
    var a = aktiven(), pot = e.composedPath ? e.composedPath() : [];
    if (vUrejanju(a) || vUrejanju(e.target) || vUrejanju(pot[0])) return false;
    if (mordaZaprtaSenca(a) || mordaZaprtaSenca(e.target)) return false;
    return true;
  }
  function varuh(e) { if (niKajKopirati(e)) e.preventDefault(); }
  // Zadnji na vrsti: poslusalca za fazo vzpenjanja dodamo sele med razposiljanjem dogodka, da tece za poslusalci strani.
  dodaj("copy", function () { dodaj("copy", varuh, { once: true }); }, true);
})();"""


def dodaj(WebKit2, upravitelj) -> bool:
    """Vgradi varuha v vse okvire pogledov s tem upraviteljem vsebine. Vrne False, če vgradnja ni uspela."""
    okviri = WebKit2.UserContentInjectedFrames.ALL_FRAMES
    cas = WebKit2.UserScriptInjectionTime.START
    try:
        try:
            skripta = WebKit2.UserScript.new_for_world(SKRIPTA, okviri, cas, SVET, None, None)
        except (AttributeError, TypeError):
            skripta = WebKit2.UserScript(SKRIPTA, okviri, cas, None, None)   # starejši WebKitGTK brez svetov skript
        upravitelj.add_script(skripta)
        return True
    except Exception:
        return False
