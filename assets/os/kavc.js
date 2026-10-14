/* Nacin za kavc (lastnik, 11. 10. 2026): Medijski center z daljincem, telefonom ali igralnim ploscekom - puscice,
 * OK in Nazaj - in na racunalniku VEDNO tudi z misko. Ko premaknes misko, izbor sledi njej; ko pritisnes tipko ali
 * gumb, se vrne izbor s puscicami. Nic ni treba preklapljati.
 *
 * - Premikanje s puscicami po zaslonu (prostorsko: najblizji gumb v smeri puscice) v Safeer Playerju in v Medijskem
 *   centru; v polju za vnos puscici gor/dol (in levo/desno na robu besedila) zapustita polje.
 * - OK (Enter) izbere; Nazaj (Escape, Backspace zunaj polja, tipka Nazaj na daljincu) zapre okno ali podrobnosti.
 * - Igralni plosek (Gamepad API, ce ga sistem ponuja): smerni gumbi in levi palcek = puscice, A = OK, B = Nazaj,
 *   Y = meni izbrane kartice (srcek, ogledano).
 * - Nacin za kavc: vecje pisave in kartice, jasen okvir izbora, okno cez cel zaslon; kazalec miske se skrije, ko
 *   miska miruje, in se vrne ob premiku.
 */
(function () {
  "use strict";

  var most = window.SafeerOS || null;
  var PREDVAJALNIK = /[?&]predvajalnik=1(&|$)/.test(location.search);
  var html = document.documentElement;
  var KLJUC = "safeer_kavc";

  function besedilo(kljuc) {
    var j = (html.getAttribute("lang") || "sl").slice(0, 2);
    var b = window.BESEDILA_OS || {};
    return (b[j] && b[j][kljuc]) || (b.en && b.en[kljuc]) || kljuc;
  }
  function klic(metoda, argumenti) {
    try { return most ? Promise.resolve(most.klic(metoda, argumenti || [])) : Promise.resolve(null); }
    catch (e) { return Promise.resolve(null); }
  }

  // ------------------------------------------------------------------ kaj se da izbrati
  var IZBIRNO = "button, a[href], input:not([type=hidden]), select, textarea, [tabindex]:not([tabindex='-1']), [role=button], [role=tab]";

  function viden(el) {
    if (!el || el.disabled || el.hidden || el.closest("[hidden]") || el.getAttribute("aria-hidden") === "true") return false;
    var r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    var s = window.getComputedStyle(el);
    if (s.visibility === "hidden" || s.display === "none") return false;
    return true;
  }
  // Odprto okno (sloj, meni, podrobnosti naslova) ujame izbor: s puscicami ne pridemo na stran pod njim.
  function obmocje() {
    var sloji = Array.prototype.filter.call(document.querySelectorAll(".sloj.viden, [role=dialog]:not([hidden]), [role=menu]:not([hidden])"), viden);
    if (sloji.length) return sloji[sloji.length - 1];
    var p = document.getElementById("mediaPodrobnosti");
    if (p && !p.hidden && viden(p)) return p;
    return document.body;
  }
  function kandidati() {
    return Array.prototype.filter.call(obmocje().querySelectorAll(IZBIRNO), viden);
  }
  function sredina(r) { return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }

  // Prostorsko premikanje: najblizji kandidat v smeri; kandidat v isti vrsti ali stolpcu ima prednost pred diagonalo.
  function naslednji(od, smer, vsi) {
    var a = od.getBoundingClientRect(), ca = sredina(a), najboljsi = null, najmanj = Infinity;
    vsi.forEach(function (el) {
      if (el === od || el.contains(od) || od.contains(el)) return;
      var b = el.getBoundingClientRect(), cb = sredina(b), naprej, postrani;
      if (smer === "desno") { if (cb.x <= ca.x + 1) return; naprej = b.left - a.right; postrani = Math.abs(cb.y - ca.y); }
      else if (smer === "levo") { if (cb.x >= ca.x - 1) return; naprej = a.left - b.right; postrani = Math.abs(cb.y - ca.y); }
      else if (smer === "dol") { if (cb.y <= ca.y + 1) return; naprej = b.top - a.bottom; postrani = Math.abs(cb.x - ca.x); }
      else { if (cb.y >= ca.y - 1) return; naprej = a.top - b.bottom; postrani = Math.abs(cb.x - ca.x); }
      var prekriva = (smer === "levo" || smer === "desno") ? (b.bottom > a.top && b.top < a.bottom) : (b.right > a.left && b.left < a.right);
      var tocke = Math.max(0, naprej) + postrani * (prekriva ? 0.5 : 2.5);
      if (tocke < najmanj) { najmanj = tocke; najboljsi = el; }
    });
    return najboljsi;
  }
  function prvi(vsi) {
    var v = vsi.filter(function (el) { var r = el.getBoundingClientRect(); return r.bottom > 0 && r.top < window.innerHeight; });
    v.sort(function (x, y) { var a = x.getBoundingClientRect(), b = y.getBoundingClientRect(); return (a.top - b.top) || (a.left - b.left); });
    return v[0] || vsi[0] || null;
  }
  // Zadnji izbor na strani (ne v oknu): ko se okno ali podrobnosti zaprejo, se izbor vrne tja, od koder smo prisli.
  var zadnjiNaStrani = null;
  document.addEventListener("focusin", function (e) {
    if (e.target && e.target !== document.body && obmocje() === document.body) zadnjiNaStrani = e.target;
  });
  function vrniIzbor() {
    setTimeout(function () {
      var zdaj = document.activeElement;
      if ((!zdaj || zdaj === document.body || !viden(zdaj)) && zadnjiNaStrani && viden(zadnjiNaStrani)) izberi(zadnjiNaStrani);
    }, 120);
  }
  function izberi(el) {
    if (!el) return;
    try { el.focus({ preventScroll: true }); } catch (e) { el.focus(); }
    try { el.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" }); } catch (e) { el.scrollIntoView(false); }
  }
  function premakni(smer) {
    var vsi = kandidati();
    if (!vsi.length) return false;
    var zdaj = document.activeElement;
    if (!zdaj || zdaj === document.body || vsi.indexOf(zdaj) < 0) { izberi(prvi(vsi)); return true; }
    var cilj = naslednji(zdaj, smer, vsi);
    if (cilj) izberi(cilj);
    return true;
  }

  // ------------------------------------------------------------------ Nazaj
  function nazaj() {
    // Escape ze zna zapreti okna in podrobnosti (os.js): posljemo ga strani, kot da bi ga pritisnil uporabnik.
    var cilj = document.activeElement && document.activeElement !== document.body ? document.activeElement : document;
    cilj.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", code: "Escape", keyCode: 27, which: 27, bubbles: true, cancelable: true }));
    vrniIzbor();
  }

  // ------------------------------------------------------------------ tipke
  function vPolju(el) {
    return !!el && (el.tagName === "TEXTAREA" || el.isContentEditable ||
      (el.tagName === "INPUT" && !/^(button|submit|checkbox|radio|range|color|file)$/i.test(el.type || "")));
  }
  var SMERI = { ArrowLeft: "levo", ArrowRight: "desno", ArrowUp: "gor", ArrowDown: "dol" };
  // Puscice premikajo izbor v Safeer Playerju vedno, v glavnem oknu v Medijskem centru ali v nacinu za kavc.
  // Delovna povrsina (delovna.html, <html data-kavc="namizje">): vedno - namizje na TV z daljincem ali ploskom.
  function aktivno() {
    if (PREDVAJALNIK || kavc() || html.getAttribute("data-kavc") === "namizje") return true;
    var r = document.getElementById("r-media");
    return !!(r && viden(r));
  }
  function naTipko(e) {
    if (e.ctrlKey || e.altKey || e.metaKey || !e.isTrusted) return;
    nacinTipk();
    var el = document.activeElement;
    // Tipko, ki jo je stran ze obdelala (npr. Backspace = mapa navzgor v Datotekah), pustimo strani.
    if (aktivno() && !e.defaultPrevented && (e.key === "BrowserBack" || e.key === "GoBack" || (e.key === "Backspace" && !vPolju(el)))) {
      e.preventDefault(); nazaj(); return;
    }
    if (e.key === "Escape" && aktivno()) vrniIzbor();
    var smer = SMERI[e.key];
    if (!smer || e.defaultPrevented || e.shiftKey || !aktivno()) return;
    if (vPolju(el)) {
      // Besedilo: levo/desno premikata kazalec, razen na robu; gor/dol zapustita polje (razen v vecvrsticnem).
      if (el.tagName === "TEXTAREA" && (smer === "gor" || smer === "dol")) return;
      var dolzina = String(el.value || "").length, zacetek = el.selectionStart, konec = el.selectionEnd;
      if (smer === "levo" && !(zacetek === 0 && konec === 0)) return;
      if (smer === "desno" && !(zacetek === dolzina && konec === dolzina)) return;
    }
    if (el && el.type === "range" && (smer === "levo" || smer === "desno")) return;
    if (premakni(smer)) e.preventDefault();
  }

  // ------------------------------------------------------------------ miska in tipke
  var skrijKazalec = null;
  function nacinTipk() {
    clearTimeout(skrijKazalec);
    html.classList.add("kavc-tipke"); html.classList.remove("kavc-miska");
  }
  function nacinMiske() {
    html.classList.add("kavc-miska"); html.classList.remove("kavc-tipke");
    clearTimeout(skrijKazalec);
    // V nacinu za kavc se kazalec skrije, ko miska miruje (kot pri predvajalnikih); ob premiku se takoj vrne.
    if (kavc()) skrijKazalec = setTimeout(function () { html.classList.remove("kavc-miska"); }, 4000);
  }
  var zadnjiX = -1, zadnjiY = -1, spremenjeno = 0;
  document.addEventListener("mousemove", function (e) {
    if (Math.abs(e.clientX - zadnjiX) + Math.abs(e.clientY - zadnjiY) < 3) return;   // drobni tresljaji niso premik
    zadnjiX = e.clientX; zadnjiY = e.clientY;
    nacinMiske();
  }, { passive: true });
  // V nacinu za kavc izbor sledi miski: gumb pod kazalcem dobi okvir izbora, puscica gre od tam naprej.
  document.addEventListener("mouseover", function (e) {
    // Ob spremembi velikosti (vklop nacina, cel zaslon) brskalnik javi mouseover brez premika miske - to ni izbira.
    if (!kavc() || !html.classList.contains("kavc-miska") || Date.now() - spremenjeno < 800) return;
    var el = e.target && e.target.closest ? e.target.closest(IZBIRNO) : null;
    if (el && viden(el) && el !== document.activeElement && !vPolju(document.activeElement)) {
      try { el.focus({ preventScroll: true }); } catch (x) { /* ni mogoce */ }
    }
  });
  document.addEventListener("keydown", naTipko);

  // ------------------------------------------------------------------ igralni plosek
  var plosek = { stanje: {}, cas: {} };
  function gumbPloska(ime, pritisnjen, dejanje) {
    var zdaj = Date.now(), prej = plosek.stanje[ime];
    plosek.stanje[ime] = pritisnjen;
    if (!pritisnjen) return;
    // Prvi pritisk takoj, drzanje ponavlja (po 400 ms vsakih 130 ms).
    if (!prej) { plosek.cas[ime] = zdaj + 400; nacinTipk(); dejanje(); }
    else if (zdaj >= plosek.cas[ime]) { plosek.cas[ime] = zdaj + 130; dejanje(); }
  }
  function beriPlosek() {
    var ploski = navigator.getGamepads ? navigator.getGamepads() : [];
    for (var i = 0; i < ploski.length; i++) {
      var p = ploski[i];
      if (!p || !p.buttons) continue;
      var g = function (n) { return !!(p.buttons[n] && p.buttons[n].pressed); };
      var x = p.axes && p.axes.length > 1 ? p.axes[0] : 0, y = p.axes && p.axes.length > 1 ? p.axes[1] : 0;
      gumbPloska("gor", g(12) || y < -0.6, function () { premakni("gor"); });
      gumbPloska("dol", g(13) || y > 0.6, function () { premakni("dol"); });
      gumbPloska("levo", g(14) || x < -0.6, function () { premakni("levo"); });
      gumbPloska("desno", g(15) || x > 0.6, function () { premakni("desno"); });
      gumbPloska("ok", g(0), function () { var el = document.activeElement; if (el && el !== document.body) el.click(); });
      gumbPloska("nazaj", g(1), nazaj);
      // Y: meni izbrane kartice (srcek, ogledano) - kot tipka Meni na tipkovnici.
      gumbPloska("meni", g(3), function () {
        var el = document.activeElement;
        if (el && el !== document.body) el.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true }));
      });
      break;
    }
    requestAnimationFrame(beriPlosek);
  }
  var plosekTece = false;
  window.addEventListener("gamepadconnected", function () {
    if (plosekTece) return;
    plosekTece = true; requestAnimationFrame(beriPlosek);
  });

  // ------------------------------------------------------------------ nacin za kavc
  function kavc() { return html.classList.contains("kavc"); }
  // Gumb je ikona (lastnik, 14. 10. 2026): stanje pove aria-pressed, namig pove, kaj klik naredi.
  function napisGumba(vklop) {
    var g = document.getElementById("medijiKavc");
    if (!g) return;
    g.setAttribute("aria-pressed", vklop ? "true" : "false");
    g.setAttribute("aria-label", besedilo("kavcVklop"));
    g.title = besedilo(vklop ? "kavcIzklop" : "kavcVklop");
  }
  function nastaviKavc(vklop) {
    vklop = !!vklop;
    if (vklop === kavc()) { napisGumba(vklop); return; }
    spremenjeno = Date.now();
    html.classList.toggle("kavc", vklop);
    try { localStorage.setItem(KLJUC, vklop ? "1" : "0"); } catch (e) { /* ni shrambe */ }
    napisGumba(vklop);
    // Cel zaslon naredi Safeer OS (okno GTK): Escape tako ostane tipka Nazaj in ne zapusti celega zaslona.
    klic("kavcCelZaslon", [vklop]);
    // Ob vklopu je izbrana prva vsebina (na Domov gumb Predvajaj junaka, sicer kartica kataloga ali knjiznice), ne gumb v glavi.
    if (vklop) setTimeout(function () {
      var prva = Array.prototype.filter.call(document.querySelectorAll("#mediaJunakPredvajaj, .kat-kartica, .media-kartica-odpri, .media-skladba-odpri"), viden)[0];
      if (prva) izberi(prva); else premakni("dol");
    }, 300);
  }
  function zacni() {
    var g = document.getElementById("medijiKavc");
    if (g) g.addEventListener("click", function () { nastaviKavc(!kavc()); });
    var shranjeno = "0";
    try { shranjeno = localStorage.getItem(KLJUC) || "0"; } catch (e) { /* ni shrambe */ }
    // Safeer Player se odpre v nacinu, v katerem ga je uporabnik zapustil.
    if (shranjeno === "1" && PREDVAJALNIK) nastaviKavc(true); else napisGumba(false);
  }
  window.SafeerKavc = { premakni: premakni, nazaj: nazaj, nastavi: nastaviKavc, vklopljen: kavc,
                       napis: function () { napisGumba(kavc()); } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", zacni); else zacni();
})();
