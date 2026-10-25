/* Safeer OS za racunalnik: domaci zaslon, programi, datoteke, naprave, nastavitve.
 * Vse sistemsko gre skozi most window.SafeerOS.klic(metoda, argumenti) -> Promise (safeer_os.py).
 * Brez mosta (predogled v brskalniku) stran pokaze prazno, a delujoco lupino. */
(function () {
  "use strict";

  // ------------------------------------------------------------------ ikone (24 x 24, crte)
  var IK = {
    domov: "M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z",
    programi: "M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z",
    mapa: "M3 6a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z",
    povezava: "M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1 M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1",
    drsniki: "M4 7h10 M18 7h2 M4 17h4 M12 17h8 M16 5v4 M10 15v4",
    napajanje: "M12 3v8 M6.3 6.3a8 8 0 1 0 11.4 0",
    isci: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z M20 20l-4-4",
    splet: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M3 12h18 M12 3c2.5 2.5 3.8 5.5 3.8 9s-1.3 6.5-3.8 9 M12 3C9.5 5.5 8.2 8.5 8.2 12s1.3 6.5 3.8 9",
    desno: "M9 6l6 6-6 6",
    nazaj: "M15 6l-6 6 6 6",
    vrstica: "M4 5h16v14H4z M9 5v14 M15.5 9.5L13 12l2.5 2.5",
    naprave: "M2 5h14v10H2z M6 19h6 M9 15v4 M17 9h4a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1z",
    qr: "M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h2v2h-2z M18 14h2 M14 18h2 M18 18h2v2",
    poslji: "M4 12l16-8-6 16-2-7z",
    zaslon: "M3 4h18v12H3z M8 20h8 M12 16v4 M10 8l4 2-4 2z",
    // Standardni ikoni za cel zaslon (vogali navzven / navznoter), lastnik 15. 10. 2026.
    celZaslon: "M4 9V4h5 M15 4h5v5 M20 15v5h-5 M9 20H4v-5",
    celZaslonIzhod: "M9 4v5H4 M15 4v5h5 M20 15h-5v5 M4 15h5v5",
    daljinec: "M8 2h8a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z M12 6v.1 M10 11h4 M12 9v4 M10 17h4",
    celozaslonsko: "M4 9V4h5 M15 4h5v5 M20 15v5h-5 M9 20H4v-5",
    namizje: "M3 4h18v13H3z M3 14h18 M9 21h6",
    zvok: "M4 9v6h4l5 4V5L8 9z M16 9a4 4 0 0 1 0 6 M18.5 6.5a8 8 0 0 1 0 11",
    utisan: "M4 9v6h4l5 4V5L8 9z M17 9l5 6 M22 9l-5 6",
    wifi: "M2 9a15 15 0 0 1 20 0 M5 12.5a10 10 0 0 1 14 0 M8.5 16a5 5 0 0 1 7 0 M12 19.5v.1",
    ethernet: "M4 10h16v8H4z M8 18v2 M12 18v2 M16 18v2 M9 10V6h6v4",
    brezOmrezja: "M2 9a15 15 0 0 1 20 0 M8.5 16a5 5 0 0 1 7 0 M3 3l18 18",
    baterija: "M3 8h15v8H3z M20 11v2",
    polni: "M3 8h15v8H3z M20 11v2 M11 9l-2 3h3l-2 3",
    svetlost: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M12 2v2 M12 20v2 M4.9 4.9l1.4 1.4 M17.7 17.7l1.4 1.4 M2 12h2 M20 12h2 M4.9 19.1l1.4-1.4 M17.7 6.3l1.4-1.4",
    luna: "M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z",
    zakleni: "M6 11h12v9H6z M8 11V8a4 4 0 0 1 8 0v3",
    odjava: "M14 4h5v16h-5 M10 16l-4-4 4-4 M6 12h10",
    ponovno: "M20 12a8 8 0 1 1-2.3-5.7 M20 4v5h-5",
    zvezda: "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z",
    x: "M6 6l12 12 M18 6L6 18",
    plus: "M12 5v14 M5 12h14",
    slika: "M4 4h16v16H4z M4 16l5-5 4 4 3-3 4 4 M15 8.5v.1",
    video: "M3 6h13v12H3z M16 10l5-3v10l-5-3",
    glasba: "M9 18V5l11-2v13 M9 18a3 3 0 1 1-3-3 3 3 0 0 1 3 3z M20 16a3 3 0 1 1-3-3 3 3 0 0 1 3 3z",
    radio: "M5 7h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2z M7 7l9-4 M8 13a2 2 0 1 0 0 4 2 2 0 0 0 0-4z M14 12h4 M14 16h4",
    dokument: "M6 3h8l4 4v14H6z M14 3v4h4 M9 12h6 M9 16h6",
    arhiv: "M4 4h16v4H4z M5 8v12h14V8 M10 12h4",
    program: "M4 5h16v14H4z M4 9h16 M8 13l2 2-2 2 M12 17h4",
    datoteka: "M6 3h8l4 4v14H6z M14 3v4h4",
    paleta: "M12 3a9 9 0 1 0 0 18c1 0 1.5-.8 1.5-1.5 0-.9-.7-1.2-.7-2 0-.8.7-1.5 1.5-1.5H16a5 5 0 0 0 5-5c0-4.4-4-8-9-8z M7.5 11v.1 M10 7.5v.1 M14 7.5v.1",
    scit: "M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z",
    twitch: "M5 3h15v10l-4 4h-4l-3 3H7v-3H4V6z M11 7v4 M15 7v4",
    tipkovnica: "M3 6h18v12H3z M7 10h.1 M11 10h.1 M15 10h.1 M7 14h10",
    miska: "M12 3a6 6 0 0 1 6 6v6a6 6 0 0 1-12 0V9a6 6 0 0 1 6-6z M12 7v3",
    bluetooth: "M7 7l10 10-5 4V3l5 4L7 17",
    tiskalnik: "M6 9V3h12v6 M6 18H4v-7h16v7h-2 M6 14h12v7H6z",
    uporabnik: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4 21a8 8 0 0 1 16 0",
    zvonec: "M6 16v-5a6 6 0 0 1 12 0v5l2 2H4z M10 20a2 2 0 0 0 4 0",
    ura: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 7v5l3 2",
    disk: "M4 6h16v12H4z M4 13h16 M16 16v.1",
    slusalke: "M4 15v-3a8 8 0 0 1 16 0v3 M4 15h3v5H5a1 1 0 0 1-1-1z M20 15h-3v5h2a1 1 0 0 0 1-1z",
    mikrofon: "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z M5 11a7 7 0 0 0 14 0 M12 18v3"
    ,sporocila: "M4 5h16v11H9l-5 4z M8 9h8 M8 12h6"
    ,uredi: "M12 20h9 M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"
    ,sporocilo: "M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"
    ,telefon: "M8 3h8a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z M11 18h2"
    // Prostori (Safeer Link Spaces): trije zasloni drug ob drugem; tablica za ploscico prostora
    ,prostori: "M8 5h8v14H8z M3 8h3v8H3z M18 8h3v8h-3z"
    ,tablica: "M5 3h14a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z M11 18h2"
    ,srce: "M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.3a4.3 4.3 0 0 1 7.5 2.5C19.5 15.4 12 20 12 20z"
    ,kljukica: "M5 12.5l4.5 4.5L19 7.5"
    ,vec: "M5 12h.01 M12 12h.01 M19 12h.01"
    // Spodnja vrstica predvajanja (14. 10. 2026)
    ,premesaj: "M16 4h4v4 M4 20 20 4 M20 16v4h-4 M15 15l5 5 M4 4l5 5"
    ,prejsnja: "M6 5v14 M19 5 9 12l10 7z"
    ,naslednja: "M18 5v14 M5 5l10 7-10 7z"
    ,ponovi: "M17 2l3 3-3 3 M4 11V9a4 4 0 0 1 4-4h12 M7 22l-3-3 3-3 M20 13v2a4 4 0 0 1-4 4H4"
    ,predvajaj: "M7 4.5v15l12.5-7.5z"
    ,premor: "M7 5h3.5v14H7z M13.5 5H17v14h-3.5z"
    ,seznam: "M4 6h12 M4 12h12 M4 18h8 M19 15v6 M16 18h6"
    // »Predvajaj na …« (oddajanje na drugo napravo ali zvocnik)
    ,oddajaj: "M3 8V6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-5 M3 12a8 8 0 0 1 8 8 M3 16a4 4 0 0 1 4 4 M3 20h.01"
    // Priponke v Sporocilih (15. 10. 2026)
    ,sponka: "M20.5 11.5l-8.2 8.2a5 5 0 0 1-7.1-7.1l8.6-8.6a3.4 3.4 0 0 1 4.8 4.8l-8.6 8.6a1.8 1.8 0 0 1-2.5-2.5l7.9-7.9"
    ,prenos: "M12 4v11 M7 10l5 5 5-5 M5 20h14"
    ,kos: "M4 7h16 M9 7V4h6v3 M6 7l1 13h10l1-13 M10 11v6 M14 11v6"
    // Nabiralnik (prenova 16. 10. 2026): filter in znaki kanalov (brez logotipov blagovnih znamk - samo splosni znaki)
    ,filter: "M4 5h16l-6 7.5V19l-4 2v-8.5z"
    ,eposta: "M3 6h18v12H3z M3.5 6.5l8.5 6.5 8.5-6.5"
    ,matrix: "M7 4H4v16h3 M17 4h3v16h-3 M9 15v-5 M9 11c0-1.5 3-1.5 3 0v4 M12 11c0-1.5 3-1.5 3 0v4"
    // Safeer Agent (AI asistent v iskalni lupi, 19. 10. 2026): iskra
    ,iskra: "M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z M18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"
  };
  window.SafeerIkone = IK;   // kavc.js zamenja ikono gumba za cel zaslon
  function svg(ime) {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + (IK[ime] || IK.datoteka) + '"/></svg>';
  }

  // ------------------------------------------------------------------ most
  var most = window.SafeerOS || null;
  function klic(metoda, argumenti) {
    if (!most) return Promise.reject("brez mosta");
    return most.klic(metoda, argumenti || []);
  }
  // Safeer Player (safeer_os.py --predvajalnik, »Odpri Medijski center« na delovni povrsini): ista stran v svojem
  // oknu, samo Medijski center - brez stranske vrstice, glave in noge Safeer OS. Most, katalog in predvajalnik so isti.
  var PREDVAJALNIK = /[?&]predvajalnik=1(&|$)/.test(location.search);
  // Okno enega razdelka na delovni povrsini (safeer_os.py _odpri_okno_razdelka, lastnik 12. 10. 2026): namizno okolje
  // ne odpira vec cele stare lupine Safeer OS - Zapiski, Sporocila in Nastavitve se odprejo vsak v svojem oknu.
  // Safeer Scit (lastnik, 18. 10. 2026) je svoj program z istim blokom nastavitev (#blokScit) in statistiko.
  var RAZDELEK = (location.search.match(/[?&]razdelek=(zapiski|sporocila|nastavitve|scit)(?:&|$)/) || [])[1] || "";
  // Razdelek, ki ga to okno edini kaze ("" = glavno okno z vsemi razdelki).
  var EN_RAZDELEK = PREDVAJALNIK ? "media" : RAZDELEK;
  // Podstrani okna razdelka: Nastavitve pokazejo Omrezje in Zvok v svojem oknu (ploscici in gumb Nazaj). Prej je klik nanju
  // z namizja odprl staro glavno okno Safeer OS (popis 3.1, 18. 10. 2026; isti seznam v safeer_os.PODSTRANI_NASTAVITEV).
  var PODSTRANI_OKNA = { nastavitve: ["omrezje", "zvok"] };
  function vTemOknu(razdelek) {
    return !EN_RAZDELEK || razdelek === EN_RAZDELEK || (PODSTRANI_OKNA[EN_RAZDELEK] || []).indexOf(razdelek) >= 0;
  }

  // ------------------------------------------------------------------ besedila
  var jezik = "sl";
  function t(kljuc, zamenjave) {
    var b = (BESEDILA_OS[jezik] && BESEDILA_OS[jezik][kljuc]);
    if (b == null) b = BESEDILA_OS.en[kljuc];
    if (b == null) b = kljuc;
    if (zamenjave) Object.keys(zamenjave).forEach(function (k) { b = b.split("{" + k + "}").join(zamenjave[k]); });
    return b;
  }
  // Slovenscina ima dvojino: 2 razlicici, 3-4 razlicice, 5+ razlicic (prej povsod »2 različic«).
  function kljucRazlicic(n) {
    if (jezik !== "sl") return "katRazlicic";
    var z = n % 100;
    if (z === 2) return "katRazlicic2";
    if (z === 3 || z === 4) return "katRazlicic34";
    return "katRazlicic";
  }
  var LOKALE = { sl: "sl-SI", en: "en-GB", de: "de-DE", es: "es-ES", fr: "fr-FR", it: "it-IT" };
  function prevedi() {
    document.documentElement.lang = jezik;
    document.querySelectorAll("[data-t]").forEach(function (el) { el.textContent = t(el.getAttribute("data-t")); });
    document.querySelectorAll("[data-ph]").forEach(function (el) { el.placeholder = t(el.getAttribute("data-ph")); });
    document.querySelectorAll("[data-naslov]").forEach(function (el) {
      el.title = t(el.getAttribute("data-naslov"));
      // Gumb samo z ikono: bralnik zaslona prebere isti napis kot namig.
      if (!el.textContent.trim()) el.setAttribute("aria-label", el.title);
    });
    if (window.SafeerKavc && window.SafeerKavc.napis) window.SafeerKavc.napis();
    document.querySelectorAll("svg[data-ikona]").forEach(function (el) {
      el.setAttribute("viewBox", "0 0 24 24");
      el.innerHTML = '<path d="' + (IK[el.getAttribute("data-ikona")] || "") + '"/>';
    });
    vrsticaUredi();
    lupaUredi();
    navNapisi();
    prevediKatalog();
    if ($("bliznjice")) narisiBliznjice();
  }

  /* Stranska vrstica (lastnik, 19. 10. 2026: »mora ostati izven poti, a preprosto dosegljiva, ko jo potrebujes«).
   * Ena moznost, kot meni Medijskega centra (lastnik, 18. 10. 2026: brez podvajanja): vrstica je razsirjena ali skrcena
   * na ozek trak z ikonami, ki ostane viden - izbrani razdelek je oznacen, ime v namigu. Gumb na vrhu traku ali Ctrl+B.
   * Samodejno (privzeto): v sirokem oknu razsirjena, v ozkem (pod VRSTICA_MEJA px) trak. Razsiritev v ozkem oknu je
   * zacasna in plava nad vsebino (vsebina se ne premakne); zapre jo izbira razdelka, Escape ali klik mimo. V sirokem oknu
   * gumb shrani izbiro (»skrcena« ali samodejno) za naslednji zagon. Dotik: poteg z levega roba odpre, v levo zapre. */
  var VRSTICA_KLJUC = "safeer_vrstica", VRSTICA_MEJA = 1200;
  var vrsticaIzbira = "";                 // "" = samodejno, "skrcena" = vedno trak
  var vrsticaPlava = false;               // zacasno razsirjena nad vsebino (ozko okno)
  function vrsticaOzko() { return window.innerWidth < VRSTICA_MEJA; }
  function vrsticaBeri() {
    try {
      var v = localStorage.getItem(VRSTICA_KLJUC);
      if (v === null) {
        // Prej: dve izbiri (skrcena, povsem skrita z rocajem). Skrita postane skrcena - meni ostane dosegljiv.
        v = localStorage.getItem("safeer_vrstica_skrcena") === "1" || localStorage.getItem("safeer_vrstica_skrita") === "1" ? "skrcena" : "";
        localStorage.setItem(VRSTICA_KLJUC, v);
        localStorage.removeItem("safeer_vrstica_skrcena"); localStorage.removeItem("safeer_vrstica_skrita");
      }
      return v === "skrcena" ? "skrcena" : "";
    } catch (e) { return ""; }
  }
  function vrsticaSkrcena() { return vrsticaIzbira === "skrcena" || vrsticaOzko(); }
  function vrsticaUredi() {
    var gumb = document.getElementById("gumbVrstica");
    if (!gumb || EN_RAZDELEK) return;     // Safeer Player in okna razdelkov nimajo stranske vrstice
    if (vrsticaPlava && !vrsticaSkrcena()) vrsticaPlava = false;     // okno je spet siroko
    var trak = vrsticaSkrcena() && !vrsticaPlava;
    document.body.classList.toggle("vrstica-skrcena", vrsticaSkrcena());
    document.body.classList.toggle("vrstica-plava", vrsticaPlava);
    gumb.setAttribute("aria-expanded", trak ? "false" : "true");
    gumb.title = t(trak ? "vrsticaRazsiri" : "vrsticaSkrci");
    gumb.setAttribute("aria-label", gumb.title);
    // V traku je ime razdelka samo v namigu - bralnik zaslona ga dobi iz aria-label (span je skrit).
    document.querySelectorAll("#meni button").forEach(function (b) {
      var ime = (b.querySelector("span") || b).textContent.trim();
      b.setAttribute("aria-label", ime);
      if (trak) b.title = ime; else b.removeAttribute("title");
    });
    if (gumb.dataset.vezan) return;
    gumb.dataset.vezan = "1";
    gumb.addEventListener("click", vrsticaPreklopi);
    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && (e.key === "b" || e.key === "B")) {
        e.preventDefault();
        vrsticaPreklopi();
        // Fokus na izbrani razdelek, razen med pisanjem v polje: tam ostane (naslednja crka bi sla v lupo).
        var a = document.activeElement, vPolju = a && (a.tagName === "INPUT" || a.tagName === "TEXTAREA" || a.tagName === "SELECT" || a.isContentEditable);
        if (!vPolju && (vrsticaPlava || !vrsticaSkrcena())) { var izbran = document.querySelector("#meni button.izbran"); if (izbran) izbran.focus(); }
      } else if (e.key === "Escape" && vrsticaPlava) {
        e.preventDefault(); e.stopImmediatePropagation();
        vrsticaZapriPlavajoco(true);
      }
    }, true);
    // Klik mimo plavajoce vrstice jo zapre in se na vsebini ne izvede (kot klik ob odprt meni).
    var pogoltniKlik = 0;
    document.addEventListener("pointerdown", function (e) {
      if (!vrsticaPlava) return;
      var stranska = document.getElementById("stranska");
      if (stranska && !stranska.contains(e.target)) { e.preventDefault(); pogoltniKlik = Date.now(); vrsticaZapriPlavajoco(false); }
    }, true);
    document.addEventListener("click", function (e) {
      if (pogoltniKlik && Date.now() - pogoltniKlik < 600) { e.preventDefault(); e.stopPropagation(); }
      pogoltniKlik = 0;
    }, true);
    document.querySelectorAll("#meni button").forEach(function (b) {
      b.addEventListener("click", function () { if (vrsticaPlava) vrsticaZapriPlavajoco(false); });
    });
    // Poteg z levega roba (dotik ali pisalo): v desno razsiri, v levo skrci.
    var poteg = null;
    document.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "mouse") return;
      poteg = e.clientX < 32 || (vrsticaPlava && document.getElementById("stranska").contains(e.target)) ? { x: e.clientX, y: e.clientY } : null;
    });
    document.addEventListener("pointerup", function (e) {
      if (!poteg) return;
      var dx = e.clientX - poteg.x, dy = Math.abs(e.clientY - poteg.y);
      poteg = null;
      if (dy > 60) return;
      if (dx > 60 && vrsticaSkrcena() && !vrsticaPlava) vrsticaPreklopi();
      else if (dx < -60 && vrsticaPlava) vrsticaZapriPlavajoco(false);
    });
    window.addEventListener("resize", vrsticaUredi);
    // Izbira v drugem oknu iste strani (npr. drugo okno Safeer OS) velja takoj.
    window.addEventListener("storage", function (e) { if (e.key === VRSTICA_KLJUC) { vrsticaIzbira = vrsticaBeri(); vrsticaUredi(); } });
  }
  function vrsticaZapriPlavajoco(fokus) {
    vrsticaPlava = false;
    vrsticaUredi();
    if (fokus) document.getElementById("gumbVrstica").focus();
  }
  function vrsticaPreklopi() {
    if (document.body.classList.contains("nacin-splet")) return;      // v nacinu Splet je vrstica vedno razsirjena
    if (vrsticaOzko()) {
      vrsticaPlava = !vrsticaPlava;      // ozko okno: zacasno, nic se ne shrani
    } else {
      vrsticaIzbira = vrsticaIzbira === "skrcena" ? "" : "skrcena";
      try { localStorage.setItem(VRSTICA_KLJUC, vrsticaIzbira); } catch (e) {}
    }
    vrsticaUredi();
  }
  if (!EN_RAZDELEK) {
    vrsticaIzbira = vrsticaBeri();
    if (vrsticaSkrcena()) document.body.classList.add("vrstica-skrcena");   // prvi izris brez skoka
    requestAnimationFrame(function () { requestAnimationFrame(function () { document.body.classList.add("vrstica-gibanje"); }); });
  }

  function $(id) { return document.getElementById(id); }
  // Plavajoc meni ob gumbu: koordinate zaslona (getBoundingClientRect) v CSS px strani - v nacinu za kavc je stran
  // povecana (zoom 1,25), sicer bi bil meni zamaknjen in odrezan (izmerjeno 14. 10. 2026 v WebKitGTK 6.0). Ce pod gumbom
  // ni prostora, gre nad gumb [nadY].
  function postaviPlavajoce(m, x, y, nadY, rob) {
    var z = parseFloat(window.getComputedStyle(document.body).zoom) || 1;
    rob = rob == null ? 12 : rob;
    var sirina = window.innerWidth / z, visina = window.innerHeight / z, h = m.offsetHeight;
    var vrh = y / z;
    if (vrh + h > visina - rob && nadY != null && nadY / z - h >= rob) vrh = nadY / z - h;
    m.style.left = Math.max(rob, Math.min(sirina - m.offsetWidth - rob, x / z)) + "px";
    m.style.top = Math.max(rob, Math.min(visina - h - rob, vrh)) + "px";
  }
  function el(oznaka, razred, html) {
    var e = document.createElement(oznaka);
    if (razred) e.className = razred;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function ubezi(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (z) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[z];
    });
  }
  var obvestiloCas = 0;
  function obvesti(besedilo) {
    var o = $("obvestilo");
    o.textContent = besedilo;
    o.classList.remove("z-gumbom");
    o.classList.add("viden");
    clearTimeout(obvestiloCas);
    obvestiloCas = setTimeout(function () { o.classList.remove("viden"); }, 2600);
  }
  // Prvi film iz torrenta: Safeer enkrat prenese odprtokodni predvajalni program. To je viden korak - z napredkom
  // in moznostjo preklica -, ne tiho cakanje.
  function motorNapredek(p) {
    var o = $("obvestilo"), odstotek = Math.floor(100 * (p.n || 0) / (p.vse || 1));
    var besedilo = t("mediaMotorPrenasam", { mb: Math.round((p.vse || 0) / 1048576), odstotek: odstotek });
    var vrstica = o.classList.contains("z-gumbom") ? o.querySelector("span") : null;
    if (odstotek >= 100) {
      o.textContent = besedilo;
      o.classList.remove("z-gumbom");
    } else if (vrstica) {
      vrstica.textContent = besedilo;       // gumb ostane isti: klik ne sme pasti med dvema dogodkoma napredka
    } else {
      o.textContent = "";
      o.appendChild(el("span", "", ubezi(besedilo)));
      var g = el("button", "", ubezi(t("preklici")));
      g.type = "button";
      g.addEventListener("click", function () {
        klic("mediaMotorPreklici").then(function () {}, function () {});
        o.classList.remove("viden", "z-gumbom");
      });
      o.appendChild(g);
      o.classList.add("z-gumbom");
    }
    o.classList.add("viden");
    clearTimeout(obvestiloCas);
    obvestiloCas = setTimeout(function () { o.classList.remove("viden", "z-gumbom"); }, odstotek < 100 ? 20000 : 2600);
  }
  // Barvna ploscica s prvo crko (program brez ikone, spletna aplikacija).
  function barva(ime) {
    var h = 0;
    for (var i = 0; i < ime.length; i++) h = (h * 31 + ime.charCodeAt(i)) >>> 0;
    var barve = ["#1f7a5c", "#2d5f9a", "#8a3d7a", "#a4492f", "#5a4aa0", "#2f7f8a", "#8a6d1f", "#3b6e2f"];
    return barve[h % barve.length];
  }
  function crka(ime) {
    var c = el("div", "crka", ubezi((ime || "?").trim().charAt(0).toUpperCase()));
    c.style.background = barva(ime || "?");
    return c;
  }
  function slikaAliCrka(pot, ime) {
    if (!pot) return crka(ime);
    var img = document.createElement("img");
    img.alt = "";
    img.src = pot;
    img.onerror = function () { img.replaceWith(crka(ime)); };
    return img;
  }

  // ------------------------------------------------------------------ stanje
  // Zadnji izbrani pogled Medijskega centra (ob naslednjem odprtju isti); privzeto Domov (lastnik, 14. 10. 2026).
  function zadnjaMedijskaKategorija() {
    try {
      var k = localStorage.getItem("safeer.mediaKategorija");
      if (["domov", "glasba", "video", "filmi", "serije", "tv", "twitch", "radio", "slike"].indexOf(k) >= 0) return k;
    } catch (_) {}
    return "domov";
  }
  function izberiMedijskoKategorijo(k) {
    S.mediaFilter = k;
    narisiVgrajenePloscice();            // ploscice lastnih strani so samo na Domov
    try { localStorage.setItem("safeer.mediaKategorija", k); } catch (_) {}
  }
  var S = {
    zacetek: null, programi: [], skupina: "vse", razdelek: "domov", pot: "", stanje: null,
    sporocilaSkupine: [], sporocilaKanali: [], sporocilaFilter: "", sporocilaAktivni: null,
    // Dejanja v seznamu: izbrane vrstice, skriti (cakajo na »Razveljavi«), hitri odgovor, nedavno poslani odgovori.
    izbraniPogovori: {}, skritiPogovori: {}, hitriOdgovor: null, poslaniOdgovori: {}, vrsticeSeznama: [], fokusPo: "",
    // Multi-host: programi drugih naprav v Safeer Linku (id naprave -> seznam), izbrana naprava ("" = ta racunalnik).
    naprave: [], vseNaprave: [], programiNaprav: {}, nalagam: {}, naprava: "",
    povezava: { stanje: "nov", control: true }, spletne: null, nedavne: [], mediaFilter: "domov",   // ob odprtju vedno Domov (lastnik, 18. 10. 2026)
    mediaLokalno: [], mediaTokovi: [], mediaMape: [], galerija: null, mediaOsvezuje: false, mediaPredvajalnik: null,
    mediaOffset: 0, mediaHasMore: false, mediaRequest: 0,
    mediaQueueKey: "", mediaDragging: false, glasnostDotik: 0, mediaZasebno: { vklopljeno: false, skriti: 0 },
    mediaSkrito: {}, mediaSkritoNalozeno: false, samodejni: [],
    programIskanje: "", mediaIskanje: "", napraveIskanje: "", datotekeIskanje: "", iskalneDatoteke: []
  };
  var PRIVZETE_SPLETNE = [
    { ime: "YouTube", url: "https://www.youtube.com" },
    { ime: "RTV 365", url: "https://365.rtvslo.si" },
    { ime: "Gmail", url: "https://mail.google.com" },
    { ime: "Wikipedia", url: "https://www.wikipedia.org" }
  ];

  // ------------------------------------------------------------------ navigacija
  function pojdi(razdelek) {
    if (razdelek === "sporocila" && !sporocilaVklopljena()) { obvesti(t("sporocilaIzklopljena")); return; }
    if (!vTemOknu(razdelek)) {
      // Drugi razdelki niso del tega okna: odpre jih Safeer OS (z delovne povrsine vsakega v svojem oknu).
      klic("odpriRazdelek", [razdelek]).catch(function () {});
      return;
    }
    S.razdelek = razdelek;
    vrsticaUredi();                 // po nacinu Splet (tam je vrstica vedno razsirjena) spet trak, ce je izbran
    zapriMeniSporocila();
    if (razdelek !== "sporocila") zapriVgrajenKanal();
    // Gostitelj pokaze ali skrije desni vdelani brskalnik. Klic je idempotenten, zato
    // tudi programaticni safeerOsPojdi vedno obnovi pravilno postavitev.
    klic("razdelek", [razdelek]).catch(function () {});
    document.querySelectorAll("#meni button").forEach(function (b) {
      b.classList.toggle("izbran", b.getAttribute("data-razdelek") === razdelek);
    });
    document.querySelectorAll(".razdelek").forEach(function (r) { r.classList.toggle("viden", r.id === "r-" + razdelek); });
    // Medijski center ima mirno, temno podlago (slika namizja skoraj skrita): berljivo tudi na televizorju.
    document.body.classList.toggle("v-mediji", razdelek === "media");
    if (razdelek !== "media") zapriMeniDodaj(false);
    $("vsebina").scrollTop = 0;
    if (razdelek === "datoteke" && !S.pot) odpriNedavne();
    if (razdelek === "naprave") { osveziPovezavo(); napraveZanka(); }
    if (razdelek === "sporocila") { sporocilaVrnitev = true; naloziSporocila(); sporocilaZanka(); }
    if (razdelek === "sporocila") naloziVgrajeneKanale();     // vgrajeni kanali (blok »Vgrajeni kanali Sporocil«)
    if (razdelek === "nastavitve") { premakniScit("scitMestoNastavitve"); narisiNastavitve(); nalozScit(); scitZanka(); nalozPosodobitve(false); }
    if (razdelek === "scit") { premakniScit("scitMesto"); nalozScit(); scitZanka(); }
    if (razdelek === "programi") nalozNaprave();
    if (razdelek === "media") naloziMedije();
    prikaziMediaBar();
    if (razdelek === "splet") narisiSpletnoZacetno();
    if (razdelek === "zapiski") naloziZapiske(function (seznam) {
      if (!Z.aktivni && seznam.length) odpriZapisek(seznam[0].id);
    });
    if (razdelek === "omrezje") { nalozOmrezje(false); nalozInternet(false); internetZanka(); }
    if (razdelek === "zvok") { nalozZvok(); zvokZanka(); if (!jblStanje) nalozJbl(); }
    // Vrnitev v Datoteke z odprto mapo: med tem je nismo spremljali, zato jo tiho preberemo znova.
    if (razdelek === "datoteke" && S.pot && S.datPogled === "mapa") odpriMapo(S.pot, true);
    spremljajDatoteke();
  }
  window.safeerOsPojdi = function (kam) {
    kam = String(kam || "");
    // Safeer Player sprejme samo Medijski center; ukazi za glavno okno (zapiski, iskanje ...) niso zanj.
    if (PREDVAJALNIK && kam !== "media" && kam.indexOf("mediji:") !== 0) return;
    // Okno enega razdelka: drugo gre skozi pojdi (ta ga preda Safeer OS), zapisek samo v oknu Zapiskov.
    if (RAZDELEK && kam.indexOf("zapisek:") === 0 && RAZDELEK !== "zapiski") return;
    if (RAZDELEK && (kam.indexOf("pogovor:") === 0 || kam.indexOf("sporocila:novo") === 0 || kam.indexOf("kanal:") === 0) && RAZDELEK !== "sporocila") return;
    if (kam.indexOf("iskanje:") === 0) {
      pojdi("domov");
      $("iskanje").value = kam.slice(8);
      $("iskanje").focus();
      isci();
      return;
    }
    if (kam.indexOf("zazeni:") === 0) {
      var p = S.programi.find(function (x) { return x.id === kam.slice(7); });
      if (p) zazeni(p);
      return;
    }
    if (kam === "media") {
      // Odprtje Medijskega centra (z namizja ali iz menija) vedno pokaze Domov, ne zadnjega zavihka (lastnik, 18. 10. 2026).
      S.mediaIskanje = ""; if ($("mediaIskanje")) $("mediaIskanje").value = "";
      izberiMedijskoKategorijo("domov");
    }
    // Vodnik ob prvem zagonu na namizju Safeer: glavnega okna tam ni, odpre ga okno Nastavitve (popis 3.1, 18. 10. 2026).
    if (kam === "vodnik") {
      if (vodnikKorak >= 0) return;                 // ze odprt: ne zacnemo znova pri prvem koraku
      if (S.zacetek) odpriVodnik(); else S.vodnikPoZacetku = true;
      return;
    }
    if (kam === "hitro") { odpriHitro(); return; }
    if (kam === "napajanje") { odpriNapajanje(); return; }
    if (kam === "mint") { odpriMint(); return; }
    if (kam.indexOf("mediji:") === 0) {
      // Z delovne povrsine: Medijski center z iskanjem po tem nizu (krajevna knjiznica in katalog).
      var iskano = kam.slice(7).trim();
      S.mediaIskanje = iskano; $("mediaIskanje").value = iskano; S.mediaFilter = "vse";
      pojdi("media"); narisiMedije();
      return;
    }
    if (kam.indexOf("kanal:") === 0) {
      // Obvestilo vgrajenega kanala: Sporocila na tem kanalu.
      var idKanala = kam.slice(6);
      if (S.razdelek !== "sporocila") pojdi("sporocila");
      klic("kanaliSeznam").then(function (s) { VK.kanali = s || []; narisiKanale(); odpriVgrajenKanal(idKanala); }).catch(function () {});
      return;
    }
    if (kam.indexOf("pogovor:") === 0) {
      // Plosca sporocil na delovni povrsini: »pogovor:<kanal>:<id>« (id lahko vsebuje dvopicje, kanal ne).
      var ostalo = kam.slice(8), dv = ostalo.indexOf(":");
      S.sporocilaOdpri = dv > 0 ? { kanal: ostalo.slice(0, dv), id: ostalo.slice(dv + 1) } : null;
      if (S.razdelek === "sporocila") naloziSporocila(); else pojdi("sporocila");
      return;
    }
    if (kam === "sporocila:novo" || kam === "sporocila:novo-email") {
      // Plosca na namizju: »Novo sporocilo« na zavihku E-posta odpre novo e-sporocilo, na zavihku Sporocila klepet z napravo.
      pojdi("sporocila");
      if (kam === "sporocila:novo-email") odpriNovo(null);
      else if ($("sporocilaPisi")) $("sporocilaPisi").click();
      return;
    }
    if (kam.indexOf("zapisek:") === 0) {
      // Zadetek iskanja na delovni povrsini: Zapiski pri tem zapisku (seznam zato ne odpre prvega).
      Z.aktivni = { id: kam.slice(8) };
      pojdi("zapiski");
      odpriZapisek(kam.slice(8));
      return;
    }
    // Iskanje na delovni povrsini odpre razdelek tudi pri dolocenem bloku (npr. »nastavitve#blokScit«).
    var sidro = "";
    if (kam.indexOf("#") > 0) { sidro = kam.slice(kam.indexOf("#") + 1); kam = kam.slice(0, kam.indexOf("#")); }
    pojdi(kam);
    if (/^blok[A-Za-z]+$/.test(sidro)) setTimeout(function () {
      var blok = $(sidro);
      if (blok) blok.scrollIntoView({ block: "center" });
    }, 400);
  };

  // ------------------------------------------------------------------ ura in pozdrav
  // Skrito okno (zaprto okno razdelka ali glavno okno se ob delovni povrsini samo skrije): brez periodicnega dela -
  // testni PC 19. 10. 2026: skriti okni Nastavitev in Safeer OS sta v mirovanju porabili ~1 % jedra (ura vsako sekundo,
  // stevec Scita), safeer_os pa je odgovarjal na njune klice. Ob ponovnem prikazu se osvezi takoj (visibilitychange).
  function skrito() { return document.visibilityState === "hidden"; }
  function osveziUro() {
    var zdaj = new Date();
    var lok = LOKALE[jezik] || "en-GB";
    $("ura").textContent = zdaj.toLocaleTimeString(lok, { hour: "2-digit", minute: "2-digit" });
    $("datum").textContent = zdaj.toLocaleDateString(lok, { weekday: "short", day: "numeric", month: "short" });
    var h = zdaj.getHours();
    var ime = S.zacetek ? String(S.zacetek.ime || "").split(" ")[0] : "";
    var kljuc = h < 11 ? "jutro" : (h < 18 ? "dan" : "vecer");
    var pozdrav = t(kljuc, { ime: ime });
    if (!ime) pozdrav = pozdrav.replace(/,\s*!/, "!");
    $("pozdrav").textContent = pozdrav;
  }

  // ------------------------------------------------------------------ programi
  function nalozPrograme() {
    return klic("programi").then(function (seznam) {
      S.programi = seznam || [];
      narisiPrograme();
      narisiDomov();
      narisiMedije();
    }, function () {});
  }
  function zazeni(p) {
    if (p.naprava) {
      odpriTukaj(p);
      return;
    }
    obvesti(t("odpiram", { ime: p.ime }));
    klic("zazeni", [p.id]).then(function (ok) {
      if (!ok) { obvesti(t("niUspelo")); return; }
      p.uporaba = (p.uporaba || 0) + 1;
      p.zadnjic = Date.now() / 1000;
      setTimeout(narisiDomov, 400);
    }, function () { obvesti(t("niUspelo")); });
  }
  function odpriTukaj(p) {
    var n = S.naprave.find(function (x) { return x.id === p.naprava; }) || { ime: "" };
    obvesti(t("potrdiNaNapravi", { ime: p.ime, naprava: n.ime }));
    klic("odpriTukaj", [p.naprava, p.id]).then(function (r) {
      if (!r || !r.ok) { obvesti(sporociloProsnje(r, n.ime) || (r && r.message ? r.message : t("niUspelo"))); return; }
      if (!r.tu) obvesti(t("napravaNePretaka", { ime: p.ime, naprava: n.ime }));
    }, function () { obvesti(t("niUspelo")); });
  }
  function zazeniNaSamiNapravi(p) {
    var n = S.naprave.find(function (x) { return x.id === p.naprava; }) || { ime: "" };
    obvesti(t("zaganjamNa", { ime: p.ime, naprava: n.ime }));
    klic("zazeniNaNapravi", [p.naprava, p.id]).then(function (r) {
      var ok = r === true || !!(r && r.ok);
      if (!ok) obvesti(sporociloProsnje(r, n.ime) || (r && r.message ? r.message : t("niUspelo")));
    }, function () { obvesti(t("niUspelo")); });
  }
  /** Druga naprava je ukaz zavrnila: prosnja za dostop caka na njej ali jo je zavrnila (core/link_dostop). */
  function sporociloProsnje(r, ime) {
    var s = r && typeof r === "object" ? r.access_request : "";
    if (s === "pending") return t("dostopProsnjaPoslana", { naprava: ime || "" });
    if (s === "declined") return t("dostopZavrnjen", { naprava: ime || "" });
    return "";
  }
  function ploscicaPrograma(p, zPripenjanjem, naDomacem) {
    var b = el("button", "ploscica");
    b.title = p.opis || p.ime;
    b.appendChild(slikaAliCrka(p.ikona, p.ime));
    b.appendChild(el("span", "ime", ubezi(p.ime)));
    b.addEventListener("click", function () { zazeni(p); });
    if (p.naprava) {
      var tam = el("span", "pripni", svg("zaslon"));
      tam.title = t("zazeniNaNapravi");
      tam.addEventListener("click", function (e) { e.stopPropagation(); zazeniNaSamiNapravi(p); });
      b.appendChild(tam);
    }
    if (zPripenjanjem) {
      var pr = el("span", "pripni" + (p.pripet ? " pripet" : "") + (naDomacem ? " levo" : ""), svg("zvezda"));
      pr.title = p.pripet ? t("odpni") : t("pripni");
      pr.addEventListener("click", function (e) {
        e.stopPropagation();
        p.pripet = !p.pripet;
        if (p.pripet) p.skrit = false;
        klic("pripni", [p.id, p.pripet]).then(function () { narisiPrograme(); narisiDomov(); });
      });
      b.appendChild(pr);
    }
    if (naDomacem) {
      // Vsaka ploscica na domacem zaslonu gre stran: pripeta se odpne, pogosta ali privzeta se skrije.
      var x = el("span", "pripni odstrani", svg("x"));
      x.title = t("odstraniZDomacega");
      x.addEventListener("click", function (e) {
        e.stopPropagation();
        p.pripet = false; p.skrit = true;
        klic("pripni", [p.id, false]).then(function () { return klic("skrijDomov", [p.id, true]); })
          .then(function () { narisiPrograme(); narisiDomov(); });
      });
      b.appendChild(x);
    }
    return b;
  }
  var SKUPINE = ["splet", "pisarna", "predstavnost", "igre", "ucenje", "programiranje", "orodja", "sistem", "drugo"];
  // ---- multi-host: naprave v Linku in njihovi programi
  function programiIzbrane() {
    return S.naprava ? (S.programiNaprav[S.naprava] || []) : S.programi;
  }
  function vsiProgramiNaprav() {
    var vsi = [];
    Object.keys(S.programiNaprav).forEach(function (id) { vsi = vsi.concat(S.programiNaprav[id]); });
    return vsi;
  }
  function nalozNaprave() {
    if (S.povezava.stanje !== "povezan") { S.naprave = []; narisiPrograme(); return; }
    return klic("napraveSProgrami").then(function (n) {
      S.naprave = n || [];
      if (S.naprava && !S.naprave.some(function (x) { return x.id === S.naprava; })) S.naprava = "";
      narisiPrograme();
      S.naprave.forEach(function (x) { if (!S.programiNaprav[x.id]) nalozProgrameNaprave(x.id); });
    }, function () {});
  }
  function nalozProgrameNaprave(id) {
    if (S.nalagam[id]) return;
    S.nalagam[id] = true;
    klic("programiNaprave", [id]).then(function (r) {
      S.nalagam[id] = false;
      S.programiNaprav[id] = (r && r.programi) || [];
      if (r && !r.ok) S.programiNaprav[id].napaka = r.koda || "napaka";
      else if (r && r.deli === false) {
        // Naprava je dostop zavrnila; ce caka prosnja, jo uporabnik odobri NA napravi (core/link_dostop).
        S.programiNaprav[id].napaka = r.access_request === "pending" ? "prosnja" : (r.access_request === "declined" ? "zavrnjeno" : "ne_deli");
      }
      narisiPrograme();
    }, function () { S.nalagam[id] = false; narisiPrograme(); });
  }
  function ikonaNaprave(n) {
    return n.platforma === "tv" ? "zaslon" : (n.platforma === "linux" || n.platforma === "windows" ? "namizje" : "naprave");
  }
  function narisiPrograme() {
    var fn = $("filtriNaprav");
    fn.innerHTML = "";
    fn.hidden = !S.naprave.length;
    if (S.naprave.length) {
      var ta = el("button", S.naprava === "" ? "izbran" : "", svg("namizje") + ubezi(t("taRacunalnik")) + "<span>" + S.programi.length + "</span>");
      ta.addEventListener("click", function () { S.naprava = ""; S.skupina = "vse"; narisiPrograme(); });
      fn.appendChild(ta);
      S.naprave.forEach(function (n) {
        var seznam = S.programiNaprav[n.id];
        var st = seznam ? seznam.length : (S.nalagam[n.id] ? "…" : "");
        var b = el("button", S.naprava === n.id ? "izbran" : "", svg(ikonaNaprave(n)) + ubezi(n.ime) + (st !== "" ? "<span>" + st + "</span>" : ""));
        b.addEventListener("click", function () {
          S.naprava = n.id; S.skupina = "vse"; narisiPrograme();
          // Ob cakajoci prosnji vprasamo znova: uporabnik jo je morda medtem odobril na napravi.
          if (!S.programiNaprav[n.id] || S.programiNaprav[n.id].napaka === "prosnja") nalozProgrameNaprave(n.id);
        });
        fn.appendChild(b);
      });
    }
    var programi = programiIzbrane();
    var stevci = {};
    programi.forEach(function (p) { stevci[p.skupina] = (stevci[p.skupina] || 0) + 1; });
    var izbranaNaprava = S.naprave.find(function (x) { return x.id === S.naprava; });
    $("programiPod").textContent = S.naprava
      ? t("programiNaprave", { n: programi.length, naprava: izbranaNaprava ? izbranaNaprava.ime : "" })
      : (S.naprave.length ? t("programiPodNaprave", { n: S.programi.length, k: S.naprave.length }) : t("programiPod", { n: S.programi.length }));
    var filtri = $("filtri");
    filtri.innerHTML = "";
    ["vse"].concat(SKUPINE).forEach(function (s) {
      if (s !== "vse" && !stevci[s]) return;
      var b = el("button", s === S.skupina ? "izbran" : "",
                 ubezi(t("sk_" + s)) + "<span>" + (s === "vse" ? programi.length : stevci[s]) + "</span>");
      b.addEventListener("click", function () { S.skupina = s; narisiPrograme(); });
      filtri.appendChild(b);
    });
    var mreza = $("vsiProgrami");
    mreza.innerHTML = "";
    if (S.naprava) {
      var seznamN = S.programiNaprav[S.naprava];
      if (!seznamN) { mreza.appendChild(el("div", "programi-obvestilo", ubezi(t("nalagamPrograme")))); return; }
      if (seznamN.napaka) {
        var imeN = izbranaNaprava ? izbranaNaprava.ime : "";
        var obvestiloN = seznamN.napaka === "prosnja" ? t("dostopProsnjaPoslana", { naprava: imeN })
          : seznamN.napaka === "zavrnjeno" ? t("dostopZavrnjen", { naprava: imeN })
          : t(seznamN.napaka === "ne_deli" ? "napravaNeDeli" : "napravaNiOdgovorila");
        mreza.appendChild(el("div", "programi-obvestilo", ubezi(obvestiloN)));
        if (["ne_deli", "prosnja", "zavrnjeno"].indexOf(seznamN.napaka) < 0) return;
      }
    }
    var iskano = String(S.programIskanje || "").trim();
    programi.filter(function (p) {
      return (S.skupina === "vse" || p.skupina === S.skupina) &&
        (!iskano || Math.max(SafeerIskanje.oceni(p.ime, iskano), SafeerIskanje.oceni(p.splosno, iskano),
          SafeerIskanje.oceni((p.kljucne || []).join(" "), iskano), SafeerIskanje.oceni(p.opis, iskano)) > 0);
    })
      .forEach(function (p) { mreza.appendChild(ploscicaPrograma(p, !p.naprava)); });
  }
  // Programi, ki jih ima vsak Mint, kot zacetni izbor, dokler uporabnik se nicesar ne odpira.
  var PRIVZETI = ["safeer-browser.desktop", "firefox.desktop", "nemo.desktop", "org.gnome.Terminal.desktop",
    "libreoffice-writer.desktop", "xed.desktop", "mintinstall.desktop", "org.gnome.Calculator.desktop",
    "celluloid.desktop", "io.github.celluloid_player.Celluloid.desktop", "rhythmbox.desktop",
    "org.gnome.Rhythmbox3.desktop", "thunderbird.desktop", "xviewer.desktop", "mintupdate.desktop"];
  function domaciProgrami() {
    var izbrani = S.programi.filter(function (p) { return p.pripet; });
    var uporabljeni = S.programi.filter(function (p) { return !p.pripet && !p.skrit && p.uporaba > 0; })
      .sort(function (a, b) { return (b.uporaba - a.uporaba) || (b.zadnjic - a.zadnjic); });
    izbrani = izbrani.concat(uporabljeni);
    PRIVZETI.forEach(function (id) {
      var p = S.programi.find(function (x) { return x.id === id; });
      if (p && !p.skrit && izbrani.indexOf(p) < 0) izbrani.push(p);
    });
    return izbrani.slice(0, 11);
  }
  // Ena vrsta ploscic kot na televizorju: programi (pripeti, pogosti), nato spletne aplikacije, na koncu »Dodaj«.
  // Koliko jih gre v vrsto, je odvisno od sirine zaslona.
  function ploscicaSpletne(a, i, kotMedij) {
    var b = el("button", "ploscica");
    b.title = a.url;
    b.appendChild(crka(a.ime));
    b.appendChild(el("span", "ime", ubezi(a.ime)));
    var x = el("span", "pripni odstrani", svg("x"));
    x.title = t("odstrani");
    x.addEventListener("click", function (e) {
      e.stopPropagation();
      var nove = spletne().slice();
      nove.splice(i, 1);
      shraniSpletne(nove);
    });
    b.appendChild(x);
    b.addEventListener("click", function () {
      obvesti(t("odpiram", { ime: a.ime }));
      klic(kotMedij ? "medij" : "splet", [a.url]);
    });
    return b;
  }
  function narisiDomov() {
    var vrsta = $("domaciProgrami");
    var sirina = vrsta.clientWidth || 1000;
    var mest = Math.max(4, Math.floor((sirina + 12) / (116 + 12)));
    var programi = domaciProgrami(), splet = spletne();
    var nSpletnih = Math.min(splet.length, Math.max(1, Math.floor((mest - 1) / 3)));
    var nProgramov = Math.min(programi.length, mest - 1 - nSpletnih);
    nSpletnih = Math.min(splet.length, mest - 1 - nProgramov);
    vrsta.innerHTML = "";
    programi.slice(0, nProgramov).forEach(function (p) { vrsta.appendChild(ploscicaPrograma(p, true, true)); });
    splet.slice(0, nSpletnih).forEach(function (a, i) { vrsta.appendChild(ploscicaSpletne(a, i)); });
    var dodaj = el("button", "ploscica dodaj", svg("plus") + '<span class="ime">' + ubezi(t("dodaj")) + "</span>");
    dodaj.addEventListener("click", odpriDodaj);
    vrsta.appendChild(dodaj);
    narisiHitriDostop();
  }
  function narisiHitriDostop() {
    var cilj = $("hitriDostop");
    cilj.innerHTML = "";
    var r = (S.zacetek && S.zacetek.razpolozljivo) || { orodja: [] };
    var elementi = [
      ["splet", t("splet"), function () { $("kBrskalnik").click(); }],
      ["mapa", t("datoteke"), function () { pojdi("datoteke"); }],
      ["drsniki", t("nastavitve"), function () { pojdi("nastavitve"); }]
    ];
    if (r.orodja.indexOf("posodobitve") >= 0) {
      elementi.push(["ponovno", t("o_posodobitve"), function () { odpriNastavitev({ modul: "posodobitve", ime: t("o_posodobitve") }); }]);
    }
    elementi.forEach(function (e) {
      var b = el("button", "hiter", svg(e[0]) + "<span>" + ubezi(e[1]) + "</span>");
      b.addEventListener("click", e[2]);
      cilj.appendChild(b);
    });
  }
  var zamikVelikosti = 0;
  window.addEventListener("resize", function () { clearTimeout(zamikVelikosti); zamikVelikosti = setTimeout(narisiDomov, 150); });

  // ------------------------------------------------------------------ spletne aplikacije
  function spletne() { return Array.isArray(S.spletne) ? S.spletne : PRIVZETE_SPLETNE; }
  function shraniSpletne(seznam) {
    S.spletne = seznam;
    narisiDomov();
    narisiMedije();
    klic("shraniSpletne", [seznam]).then(function (cisti) {
      if (Array.isArray(cisti)) S.spletne = cisti;
      narisiDomov();
      narisiMedije();
    }).catch(function () {});
  }
  function normalizirajNaslov(s) {
    s = String(s || "").trim();
    if (!s) return "";
    var imelProtokol = /^https?:\/\//i.test(s);
    if (!/^https?:\/\//i.test(s)) s = "https://" + s;
    try { var u = new URL(s); return (imelProtokol || /\./.test(u.hostname)) ? u.href : ""; } catch (e) { return ""; }
  }
  function kljucNaslova(s) {
    try {
      var u = new URL(s);
      u.hash = "";
      u.hostname = u.hostname.toLowerCase();
      if ((u.protocol === "https:" && u.port === "443") || (u.protocol === "http:" && u.port === "80")) u.port = "";
      u.pathname = u.pathname.replace(/\/+$/, "");
      return u.href.replace(/\/$/, "");
    } catch (e) { return ""; }
  }

  // ------------------------------------------------------------------ Safeer Media
  // Brez zavihka »Vse« (lastnik, 14. 10. 2026): v njem so zvrsti (Akcija, Komedija …) veljale le za filme, pod njimi pa so
  // ostale radijske postaje in glasba - uporabnik ni vedel, kaj se dogaja. »Vse« ostane le notranje za rezultate iskanja.
  // Domov (zacetna stran: junak in police) je prvi; ostalo so vrste vsebin, ki jih Medijski center ze ima.
  var MEDIA_KATEGORIJE = [
    ["domov", "domov"], ["glasba", "glasba"], ["video", "video"], ["filmi", "video"],
    ["serije", "video"], ["tv", "video"], ["twitch", "twitch"], ["radio", "radio"], ["slike", "slika"],
    // »Zasebno« (lastnik, 17. 10. 2026): vsebina zasebnih dodatkov, samo ce jo uporabnik vklopi v Dodatkih in virih.
    ["zasebno", "zakleni"]
  ];
  function kategorijaVidna(k) { return k[0] !== "zasebno" || !!S.mediaZasebno.vklopljeno; }
  var MEDIA_PREDLOGI = [
    { ime: "Jamendo", url: "https://www.jamendo.com", vrsta: "glasba", obmocje: "world" },
    { ime: "Free Music Archive", url: "https://freemusicarchive.org", vrsta: "glasba", obmocje: "world" },
    { ime: "Radio Browser", url: "https://www.radio-browser.info", vrsta: "radio", obmocje: "world" },
    { ime: "Blender Open Movies", url: "https://studio.blender.org/films/", vrsta: "filmi", obmocje: "world" },
    { ime: "PeerTube", url: "https://joinpeertube.org", vrsta: "video", obmocje: "world" },
    { ime: "NASA+", url: "https://plus.nasa.gov", vrsta: "serije", obmocje: "world" },
    { ime: "NASA Live", url: "https://www.nasa.gov/live/", vrsta: "tv", obmocje: "world" },
    { ime: "Euronews Live", url: "https://www.euronews.com/live", vrsta: "tv", obmocje: "world" },
    { ime: "ARTE", url: "https://www.arte.tv/en/", vrsta: "serije", obmocje: "region" },
    { ime: "RTV 365", url: "https://365.rtvslo.si", vrsta: "tv", obmocje: "region" }
  ];
  // ---- glavni gumb »Dodaj« in njegov meni (mapa, datoteke, TV/radio, spletni vir, magnet, dodatki in viri)
  function predmetiMenija() { return Array.prototype.slice.call($("medijiDodajMeni").querySelectorAll("[role=menuitem]")); }
  function odpriMeniDodaj(prvi) {
    var meni = $("medijiDodajMeni"); if (!meni) return;
    meni.hidden = false;
    $("medijiDodajMeniGumb").setAttribute("aria-expanded", "true");
    var predmeti = predmetiMenija();
    var cilj = prvi === "zadnji" ? predmeti[predmeti.length - 1] : predmeti[0];
    if (cilj) cilj.focus();
  }
  function zapriMeniDodaj(nazajNaGumb) {
    var meni = $("medijiDodajMeni"); if (!meni || meni.hidden) return false;
    meni.hidden = true;
    $("medijiDodajMeniGumb").setAttribute("aria-expanded", "false");
    if (nazajNaGumb) $("medijiDodajMeniGumb").focus();
    return true;
  }
  function poveziMeniDodaj() {
    var gumb = $("medijiDodajMeniGumb"), meni = $("medijiDodajMeni");
    if (!gumb || !meni) return;
    gumb.addEventListener("click", function () { if (meni.hidden) odpriMeniDodaj(); else zapriMeniDodaj(true); });
    gumb.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); odpriMeniDodaj(e.key === "ArrowUp" ? "zadnji" : ""); }
    });
    // Tipkovnica v meniju (WAI-ARIA menu): gor/dol, Home/End, Tab zapre; izbira katerega koli predmeta zapre meni.
    meni.addEventListener("keydown", function (e) {
      var predmeti = predmetiMenija(), i = predmeti.indexOf(document.activeElement);
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        predmeti[(i + (e.key === "ArrowDown" ? 1 : -1) + predmeti.length) % predmeti.length].focus();
      } else if (e.key === "Home" || e.key === "End") {
        e.preventDefault(); predmeti[e.key === "Home" ? 0 : predmeti.length - 1].focus();
      } else if (e.key === "Tab") zapriMeniDodaj(false);
      else if (e.key === "ArrowLeft" || e.key === "ArrowRight") e.preventDefault();
    });
    meni.addEventListener("click", function (e) { if (e.target.closest("[role=menuitem]")) zapriMeniDodaj(false); });
    document.addEventListener("click", function (e) { if (!e.target.closest(".media-dodaj")) zapriMeniDodaj(false); });
    // Escape (tudi tipka Nazaj na daljincu) zapre samo meni, ne celega Medijskega centra.
    window.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && zapriMeniDodaj(true)) { e.preventDefault(); e.stopImmediatePropagation(); }
    }, true);
  }
  function naloziMedije(veckrat) {
    // Prve strani drugih zavihkov v ozadju (klik na Filmi/Serije je potem takoj; enkrat na 10 min, odloci jedro).
    if (most && !naloziMedije.predgreto) { naloziMedije.predgreto = true; klic("mediaPredgrej", []).catch(function () {}); }
    if (!veckrat) naloziPolice();
    if (!veckrat && S.mediaFilter === "domov") naloziOdkrivanje();
    // DVD v pogonu (brez zaščite): gumb se pokaže samo, kadar je disk vstavljen.
    if (!veckrat && most) klic("dvdPogoni").then(function (pogoni) {
      var disk = (Array.isArray(pogoni) ? pogoni : []).filter(function (p) { return p.vstavljen; })[0];
      $("medijiDisk").hidden = !disk;
      S.dvdPogon = disk ? disk.naprava : "";
      if (disk) $("medijiDiskIme").textContent = t("predvajajDisk") + (disk.ime && disk.ime !== "DVD" ? " · " + disk.ime : "");
    }).catch(function () {});
    if (!veckrat && most) klic("medijskeMape").then(function (mape) {
      S.mediaMape = Array.isArray(mape) ? mape : [];
      $("mediaOsvezi").disabled = !S.mediaMape.length || S.mediaOsvezuje;
      if ($("slojMediaMape").classList.contains("viden")) narisiMedijskeMape();
    }).catch(function () {});
    // Skriti predmeti menija (nastavitve Medijskega centra) in samodejni seznami (predpomnjeni, racunajo se v ozadju).
    if (!veckrat && most) klic("mediaSkrito").then(function (seznam) { nastaviSkrito(seznam, true); }).catch(function () {});
    if (!veckrat && most) klic("mediaZasebno").then(nastaviZasebno).catch(function () {});
    if (!veckrat) naloziSamodejne();
    if (!veckrat && most) klic("tokoviMedijev").then(function (vnosi) {
      S.mediaTokovi = Array.isArray(vnosi) ? vnosi : [];
      narisiMedije();
    }).catch(function () {});
    if (S.mediaFilter === "tv" || S.mediaFilter === "twitch" || S.mediaFilter === "radio" || S.mediaFilter === "domov" || S.mediaFilter === "zasebno") {
      S.mediaRequest++;
      S.mediaLokalno = []; S.mediaHasMore = false;
      narisiMedije();
      if (!veckrat) klic("predvajalnikStanje").then(osveziPredvajalnik).catch(function () {});
      return;
    }
    if (!veckrat) { S.mediaOffset = 0; S.mediaLokalno = []; S.mediaHasMore = false; }
    narisiMedije();
    if (!most) return;
    var zahteva = ++S.mediaRequest;
    klic("knjiznicaMedijev", [S.mediaFilter, S.mediaIskanje, S.mediaOffset]).then(function (seznam) {
      if (zahteva !== S.mediaRequest) return;
      seznam = Array.isArray(seznam) ? seznam : [];
      S.mediaLokalno = veckrat ? S.mediaLokalno.concat(seznam) : seznam;
      S.mediaOffset += seznam.length;
      S.mediaHasMore = seznam.length === 120;
      narisiMedije();
    }).catch(function () {});
    if (!veckrat) klic("predvajalnikStanje").then(osveziPredvajalnik).catch(function () {});
  }
  function vrstaMedija(vnos) {
    if (vnos.vrsta) return vnos.vrsta;
    var s = ((vnos.ime || "") + " " + (vnos.url || "") + " " + (vnos.id || "") + " " + (vnos.opis || "")).toLowerCase();
    if (/rtv|live.?tv|watch tv|televiz|nasa.*live|euronews|france.?24/.test(s)) return "tv";
    if (/radio|podcast|tunein|radioplayer/.test(s)) return "radio";
    if (/glasb|music|spotify|deezer|soundcloud|rhythmbox|audacious|clementine/.test(s)) return "glasba";
    if (/serij|series|episode|arte|netflix/.test(s)) return "serije";
    if (/video|youtube|youtu\.be|peertube|vlc|mpv|kodi/.test(s)) return "video";
    return "";
  }
  function medijskiVnosi() {
    var vnosi = [];
    // Samo predvajalniki (XDG Player/TV, radio); urejevalniki slik in skenerji ostanejo v Programih.
    S.programi.filter(function (p) { return p.skupina === "predstavnost" && p.medij; }).forEach(function (p) {
      vnosi.push({ vrsta: vrstaMedija(p) || (p.zvok ? "glasba" : "video"), program: p });
    });
    spletne().forEach(function (a, i) {
      // Tuje spletne aplikacije ne zasedajo prostora v Medijskem centru.
      var vrsta = vrstaMedija(a);
      if (vrsta) vnosi.push({ vrsta: vrsta, spletna: a, indeks: i });
    });
    return vnosi;
  }
  // Ista pravila kot knjiznica (core/os_knjiznica.py): brez sumnikov, vec besed. Sicer bi stran zavrgla zadetke,
  // ki jih je knjiznica nasla (»zur« -> »Žur«).
  function mediaUstreza(v, iskanje) {
    return SafeerIskanje.ujemaBesede((v && v.ime) || "", iskanje);
  }
  function mediaVrsta(v) { return t("media_" + v); }
  function datotekaUrl(pot) {
    return "file://" + String(pot).split("/").map(encodeURIComponent).join("/");
  }
  // Pregledovalnik slik: celozaslonski sloj, puščice/tipke za naprej-nazaj, klik = povečava.
  function odpriGalerijo(seznam, i) {
    if (!seznam.length) return;
    S.galerija = { seznam: seznam, i: i };
    $("slojGalerija").classList.add("viden");
    prikaziSliko();
  }
  function prikaziSliko() {
    var g = S.galerija; if (!g) return;
    var v = g.seznam[g.i];
    document.querySelector(".galerija").classList.remove("povecano");
    $("galerijaSlika").src = datotekaUrl(v.pot);
    $("galerijaSlika").alt = v.ime;
    $("galerijaNapis").textContent = v.ime;
    $("galerijaStevec").textContent = (g.i + 1) + " / " + g.seznam.length;
    $("galerijaNazaj").disabled = g.i <= 0;
    $("galerijaNaprej").disabled = g.i >= g.seznam.length - 1;
    // Sosednji sliki naložimo vnaprej, da je listanje takojšnje.
    [g.i - 1, g.i + 1].forEach(function (j) { if (g.seznam[j]) new Image().src = datotekaUrl(g.seznam[j].pot); });
  }
  function premakniSliko(korak) {
    var g = S.galerija; if (!g) return;
    var j = g.i + korak;
    if (j < 0 || j >= g.seznam.length) return;
    g.i = j; prikaziSliko();
  }
  function zapriGalerijo() {
    $("slojGalerija").classList.remove("viden");
    $("galerijaSlika").removeAttribute("src");   // sprosti pomnilnik velike slike
    S.galerija = null;
  }
  function narisiMedijskeMape() {
    var seznam = $("mediaMapeSeznam"); seznam.innerHTML = "";
    if (!S.mediaMape.length) { seznam.appendChild(el("p", "drobno", ubezi(t("mediaMapeNi")))); return; }
    S.mediaMape.forEach(function (m) {
      var vrstica = el("div", "media-mapa" + (m.naVoljo ? "" : " nedosegljiva"),
        svg("mapa") + '<div title="' + ubezi(m.pot) + '"><b>' + ubezi(m.pot.replace(/\/+$/, "").split("/").pop() || m.pot) +
        '</b><small>' + ubezi(m.pot) + ' · ' +
        ubezi(m.naVoljo ? t("mediaMapaVnosov", { n: m.stevilo }) : t("mediaMapaNedosegljiva")) + '</small></div>');
      var gumb = el("button", "", ubezi(t("odstrani"))); gumb.type = "button";
      gumb.addEventListener("click", function () {
        gumb.disabled = true;
        klic("odstraniMedijskoMapo", [m.pot]).then(function (ok) {
          if (!ok) { gumb.disabled = false; obvesti(t("niUspelo")); return; }
          obvesti(t("mediaMapaOdstranjena"));
          naloziMedijskeMape();
        }).catch(function () { gumb.disabled = false; obvesti(t("niUspelo")); });
      });
      vrstica.appendChild(gumb);
      seznam.appendChild(vrstica);
    });
  }
  // ------------------------------------------------------------------ Safeer Media: z drugih naprav
  // Naprave v Linku, ki delijo datoteke -> njihove mape -> glasba in video. Predvajanje takoj, brez
  // prenosa: Safeer OS bere z naprave po šifrirani povezavi (doma neposredno, zunaj doma prek Global Linka).
  S.mediaNaprava = null;   // {id, ime, pot:[{id, ime}], streznik, kljuc, vnosi}
  function mediaNapraveSporocilo(besedilo) {
    var seznam = $("mediaNapraveSeznam"); seznam.innerHTML = "";
    seznam.appendChild(el("p", "drobno", ubezi(besedilo)));
  }
  function mediaNapraveVrstica(ikona, naslov, pod, dejanje) {
    var b = el("button", "media-mapa", svg(ikona) + '<div><b>' + ubezi(naslov) + '</b>' +
      (pod ? '<small>' + ubezi(pod) + '</small>' : '') + '</div>');
    b.type = "button";
    b.addEventListener("click", dejanje);
    return b;
  }
  function mediaNapraveOsveziGlavo() {
    var n = S.mediaNaprava;
    $("mediaNapraveNazaj").hidden = !n;
    $("mediaNapraveNaslov").textContent = n ? n.ime : t("mediaNaprave");
    $("mediaNapravePot").textContent = n ? n.pot.map(function (p) { return p.ime; }).join(" / ") : t("mediaNapraveOpis");
  }
  function odpriMediaNaprave() {
    S.mediaNaprava = null;
    mediaNapraveOsveziGlavo();
    $("slojMediaNaprave").classList.add("viden");
    $("mediaNapraveZapri").focus();
    mediaNapraveSporocilo(t("mediaNapravaNalagam"));
    klic("napraveZDatotekami").then(function (naprave) {
      if (S.mediaNaprava) return;
      naprave = Array.isArray(naprave) ? naprave : [];
      var seznam = $("mediaNapraveSeznam"); seznam.innerHTML = "";
      // "Nadaljuj z druge naprave": kar druga naprava igra ali je nazadnje gledala, tu pri isti sekundi (na zahtevo).
      seznam.appendChild(mediaNapraveVrstica("naprave", t("mediaPredaja"), t("mediaPredajaOpis"), prikaziPredajo));
      if (!naprave.length) { seznam.appendChild(el("p", "drobno", ubezi(t("mediaNapraveNi")))); return; }
      naprave.forEach(function (n) {
        seznam.appendChild(mediaNapraveVrstica("naprave", n.ime || n.id, "", function () {
          S.mediaNaprava = { id: n.id, ime: n.ime || n.id, pot: [], streznik: null, kljuc: "", vnosi: [] };
          naloziMapoNaprave("", n.ime || n.id);
        }));
      });
    }).catch(function () { mediaNapraveSporocilo(t("mediaNapraveNi")); });
  }
  function prikaziPredajo() {
    // Vse naprave vprasamo hkrati (Control: play.state, 3 s); izvor igra naprej, razen ce uporabnik izbere "ustavi tam".
    var zahteva = { id: "predaja", ime: t("mediaPredaja"), pot: [], streznik: null, kljuc: "", vnosi: [] };
    S.mediaNaprava = zahteva;
    mediaNapraveOsveziGlavo();
    mediaNapraveSporocilo(t("mediaPredajaVprasam"));
    klic("predajaPoizvedi").then(function (r) {
      if (S.mediaNaprava !== zahteva) return;
      var ponudbe = r && Array.isArray(r.ponudbe) ? r.ponudbe : [];
      if (!ponudbe.length) { mediaNapraveSporocilo(t("mediaPredajaNic")); return; }
      var seznam = $("mediaNapraveSeznam"); seznam.innerHTML = "";
      ponudbe.forEach(function (p) {
        var pod = p.opis + " · " + t(p.igra ? "mediaPredajaIgra" : "mediaPredajaNazadnje");
        var vrstica = mediaNapraveVrstica("naprave", (p.naprava && p.naprava.ime) || "", pod, function () {
          if (!p.igra) { prevzemiPredajo(p, false); return; }
          // Izvor ne ustavi sam: uporabnik izbere, ali tam tece naprej (druga oseba gleda) ali se ustavi.
          var izbira = el("div", "media-predaja-izbira");
          var tukaj = el("button", "media-mapa", "<div><b>" + ubezi(t("mediaPredajaTukaj")) + "</b></div>"); tukaj.type = "button";
          tukaj.addEventListener("click", function () { prevzemiPredajo(p, false); });
          var ustavi = el("button", "media-mapa", "<div><b>" + ubezi(t("mediaPredajaTukajUstavi")) + "</b></div>"); ustavi.type = "button";
          ustavi.addEventListener("click", function () { prevzemiPredajo(p, true); });
          izbira.appendChild(tukaj); izbira.appendChild(ustavi);
          if (vrstica.nextSibling && vrstica.nextSibling.className === "media-predaja-izbira") vrstica.parentNode.removeChild(vrstica.nextSibling);
          else vrstica.parentNode.insertBefore(izbira, vrstica.nextSibling);
        });
        seznam.appendChild(vrstica);
      });
    }).catch(function () { if (S.mediaNaprava === zahteva) mediaNapraveSporocilo(t("mediaPredajaNapaka")); });
  }
  function prevzemiPredajo(p, ustaviTam) {
    klic("predajaPrevzemi", [p.naprava.id, p.podatki, !!ustaviTam]).then(function (ok) {
      if (!ok) { obvesti(t("mediaPredajaNapaka")); return; }
      $("slojMediaNaprave").classList.remove("viden");
      S.mediaNaprava = null;
    }).catch(function () { obvesti(t("mediaPredajaNapaka")); });
  }
  function naloziMapoNaprave(mapa, ime) {
    var n = S.mediaNaprava; if (!n) return;
    if (mapa || !n.pot.length) n.pot.push({ id: mapa, ime: ime });
    mediaNapraveOsveziGlavo();
    mediaNapraveSporocilo(t("mediaNapravaNalagam"));
    var zahteva = n;
    klic("datotekeNaprave", [n.id, mapa]).then(function (r) {
      if (S.mediaNaprava !== zahteva) return;
      if (!r || !r.ok) { mediaNapraveSporocilo(t("mediaNapravaNeOdgovori")); return; }
      if (r.shared === false) { mediaNapraveSporocilo(sporociloProsnje(r, n.ime) || t("mediaNapravaNeDeli")); return; }
      if (r.server) { n.streznik = r.server; n.kljuc = r.kljuc || ""; }
      // Samo mape, glasba in video (zbirka slik telefona/TV sem ne sodi).
      var vnosi = (r.items || []).filter(function (v) {
        return (v.type === "folder" && v.id !== "media:image") || v.type === "audio" || v.type === "video";
      });
      n.vnosi = vnosi.filter(function (v) { return v.type !== "folder"; });
      if (!vnosi.length) { mediaNapraveSporocilo(t("mediaNapravaPrazno")); return; }
      var seznam = $("mediaNapraveSeznam"); seznam.innerHTML = "";
      vnosi.forEach(function (v) {
        var ikona = v.type === "folder" ? "mapa" : v.type === "audio" ? "glasba" : "video";
        var pod = v.type === "folder" ? "" : (v.size ? velikostMedija(v.size) : "");
        seznam.appendChild(mediaNapraveVrstica(ikona, v.name || v.id, pod, function () {
          if (v.type === "folder") { naloziMapoNaprave(v.id, v.name || v.id); return; }
          if (!n.streznik) { obvesti(t("mediaNapravaNeOdgovori")); return; }
          var i = n.vnosi.indexOf(v);
          klic("predvajajZNaprave", [n.streznik, n.kljuc, n.vnosi, i, n.ime, n.id]).then(function (ok) {
            if (!ok) { obvesti(t("niUspelo")); return; }
            if (v.type === "video") zapriSloje();
          }).catch(function () { obvesti(t("niUspelo")); });
        }));
      });
    }).catch(function () { if (S.mediaNaprava === zahteva) mediaNapraveSporocilo(t("mediaNapravaNeOdgovori")); });
  }
  function nazajMediaNaprave() {
    var n = S.mediaNaprava; if (!n) return;
    n.pot.pop();
    if (!n.pot.length) { odpriMediaNaprave(); return; }
    var zadnja = n.pot.pop();
    naloziMapoNaprave(zadnja.id, zadnja.ime);
  }
  function velikostMedija(b) {
    if (b >= 1073741824) return (b / 1073741824).toFixed(1).replace(".", ",") + " GB";
    if (b >= 1048576) return Math.round(b / 1048576) + " MB";
    return Math.max(1, Math.round(b / 1024)) + " kB";
  }
  // ------------------------------------------------------------------ Safeer Media: magnet povezave
  // Magnet (BitTorrent): prikaz vsebine, predvajanje že med prenosom, prenos, pošiljanje na napravo in
  // deljenje lastnih datotek. Motor je rqbit na 127.0.0.1 z geslom (core/os_torrent.py).
  S.magnet = { opis: null, casovnik: 0 };
  function magnetNapaka(koda) {
    var k = "magnetNapaka_" + (koda || "napaka"), s = t(k);
    return s === k ? t("magnetNapaka_napaka") : s;
  }
  function magnetSporocilo(besedilo, razred) {
    var v = $("magnetVsebina"); v.innerHTML = "";
    if (besedilo) v.appendChild(el("p", razred || "drobno", ubezi(besedilo)));
  }
  function magnetGumb(besedilo, dejanje, razred) {
    var g = el("button", razred || "", ubezi(besedilo)); g.type = "button";
    g.addEventListener("click", function (e) { e.stopPropagation(); dejanje(g); });
    return g;
  }
  function odpriMagnet(uri, samodejno) {
    if (window.safeerOsPojdi && S.razdelek !== "media") window.safeerOsPojdi("media");
    $("slojMagnet").classList.add("viden");
    magnetSporocilo("");
    if (uri) $("magnetPolje").value = uri;
    klic("magnetPrivzeto", [false]).then(function (je) { $("magnetPrivzeto").hidden = !!je; }).catch(function () {});
    magnetOsveziPrenose();
    if (!S.magnet.casovnik) S.magnet.casovnik = setInterval(function () {
      if (!$("slojMagnet").classList.contains("viden")) { clearInterval(S.magnet.casovnik); S.magnet.casovnik = 0; return; }
      magnetOsveziPrenose();
    }, 2000);
    // Samo povezava z naprave v krogu se prebere in predvaja sama; iz brskalnika čaka na uporabnika.
    if (uri && samodejno) preberiMagnet(uri, true);
    else if (uri) { magnetSporocilo(t("magnetPritisniOdpri")); $("magnetOdpri").focus(); }
    else $("magnetPolje").focus();
  }
  function zagotoviProgram() {
    return klic("magnetProgram").then(function (p) {
      if (!p || !p.podprto) { magnetSporocilo(t("magnetNiPodprto")); return false; }
      if (p.na_voljo) return true;
      // Enkratni prenos odprtokodnega motorja: uporabnik ve, kaj in od kod se prenaša.
      return new Promise(function (koncano) {
        var v = $("magnetVsebina"); v.innerHTML = "";
        v.appendChild(el("p", "drobno", ubezi(t("magnetProgramOpis", { mb: p.mb }))));
        v.appendChild(magnetGumb(t("magnetProgramPrenesi"), function (g) {
          g.disabled = true; g.textContent = t("magnetProgramPrenasam", { odstotek: 0 });
          S.magnet.gumbPrograma = g;
          klic("magnetPrenesiProgram").then(function (r) {
            S.magnet.gumbPrograma = null;
            if (r && r.ok) koncano(true); else { magnetSporocilo(magnetNapaka(r && r.koda)); koncano(false); }
          }).catch(function () { magnetSporocilo(magnetNapaka("prenos_programa")); koncano(false); });
        }, "gumb glavni"));
      });
    });
  }
  function preberiMagnet(uri, samodejno) {
    zagotoviProgram().then(function (ok) {
      if (!ok) return;
      magnetSporocilo(t("magnetBerem"));
      klic("magnetPreberi", [uri]).then(function (r) {
        if (!r || !r.ok) { magnetSporocilo(magnetNapaka(r && r.koda)); return; }
        S.magnet.opis = r;
        narisiMagnetOpis(r, samodejno);
      }).catch(function () { magnetSporocilo(magnetNapaka("napaka")); });
    });
  }
  function magnetIkona(vrsta) {
    return vrsta === "video" ? "video" : vrsta === "audio" ? "glasba" : vrsta === "slika" ? "slika" : vrsta === "nevarno" ? "scit" : "datoteka";
  }
  function narisiMagnetOpis(r, samodejno) {
    var v = $("magnetVsebina"); v.innerHTML = "";
    v.appendChild(el("p", "", "<b>" + ubezi(r.ime || r.hash) + "</b>"));
    if (r.sumljiv) v.appendChild(el("div", "magnet-opozorilo", ubezi(t("magnetSumljiv"))));
    var seznam = el("div", "media-mape-seznam");
    var izbire = [];
    r.datoteke.forEach(function (f) {
      var vrstica = el("div", "media-mapa");
      var izbira = el("input"); izbira.type = "checkbox"; izbira.checked = !!f.izbrana;
      izbira.setAttribute("aria-label", f.ime);
      var zapis = { f: f, el: izbira, potrjena: false };
      izbire.push(zapis);
      // Morda program: privzeto ne. Prepoznava se lahko zmoti, zato uporabnik po opozorilu vseeno izbere.
      if (f.vrsta === "nevarno") izbira.addEventListener("change", function () {
        var staro = vrstica.nextSibling && vrstica.nextSibling.classList && vrstica.nextSibling.classList.contains("magnet-opozorilo") ? vrstica.nextSibling : null;
        if (staro) staro.remove();
        if (!izbira.checked) { zapis.potrjena = false; return; }
        if (zapis.potrjena) return;
        izbira.checked = false;
        var o = el("div", "magnet-opozorilo", ubezi(t("magnetNevarnoOpis", { ime: f.ime.split("/").pop() })));
        var d = el("div", "magnet-dejanja");
        d.appendChild(magnetGumb(t("magnetVseeno"), function () { zapis.potrjena = true; izbira.checked = true; o.remove(); izbira.focus(); }));
        d.appendChild(magnetGumb(t("preklici"), function () { o.remove(); izbira.focus(); }));
        o.appendChild(d);
        vrstica.parentNode.insertBefore(o, vrstica.nextSibling);
      });
      vrstica.appendChild(izbira);
      vrstica.insertAdjacentHTML("beforeend", svg(magnetIkona(f.vrsta)) + '<div><b title="' + ubezi(f.ime) + '">' + ubezi(f.ime) +
        '</b><small>' + ubezi(velikostMedija(f.velikost)) + '</small></div>');
      vrstica.appendChild(el("span", "magnet-oznaka" + (f.vrsta === "nevarno" ? " nevarno" : ""), ubezi(t("magnetVrsta_" + f.vrsta))));
      if (f.predvajljivo) vrstica.appendChild(magnetGumb("▶ " + t("magnetPredvajaj"), function () { predvajajMagnet(r.uri, f); }));
      seznam.appendChild(vrstica);
    });
    v.appendChild(seznam);
    var dejanja = el("div", "magnet-dejanja");
    dejanja.appendChild(magnetGumb(t("magnetPrenesiIzbrane"), function (g) {
      var izbrane = izbire.filter(function (x) { return x.el.checked && (x.f.vrsta !== "nevarno" || x.potrjena); }).map(function (x) { return x.f.i; });
      var potrjene = izbire.filter(function (x) { return x.potrjena && x.el.checked; }).map(function (x) { return x.f.i; });
      if (!izbrane.length) { obvesti(magnetNapaka("ni_izbranih")); return; }
      g.disabled = true;
      klic("magnetDodaj", [r.uri, izbrane, potrjene]).then(function (d) {
        g.disabled = false;
        obvesti(d && d.ok ? t("magnetPrenasam") : magnetNapaka(d && d.koda));
        magnetOsveziPrenose();
      }).catch(function () { g.disabled = false; obvesti(magnetNapaka("napaka")); });
    }));
    magnetPosiljanje(dejanja, function () { return r.uri; });
    v.appendChild(dejanja);
    if (samodejno) {
      // Z druge naprave ali iz brskalnika: en sam posnetek (ali ena skladba) se začne predvajati takoj.
      var predvajljive = r.datoteke.filter(function (f) { return f.predvajljivo; });
      var videi = predvajljive.filter(function (f) { return f.vrsta === "video"; });
      if (predvajljive.length === 1) predvajajMagnet(r.uri, predvajljive[0]);
      else if (videi.length === 1) predvajajMagnet(r.uri, videi[0]);
    }
  }
  function magnetPosiljanje(dejanja, uri) {
    // Pošlji na drugo napravo v Linku (tam se odpre v predvajalniku) ali kopiraj za deljenje z drugimi.
    var izbor = el("select"); izbor.setAttribute("aria-label", t("magnetPoslji"));
    izbor.appendChild(el("option", "", ubezi(t("magnetPosljiNa"))));
    klic("magnetNaprave").then(function (naprave) {
      (naprave || []).forEach(function (n) { var o = el("option", "", ubezi(n.ime || n.id)); o.value = n.id; izbor.appendChild(o); });
      if (!(naprave || []).length) izbor.disabled = true;
    }).catch(function () { izbor.disabled = true; });
    izbor.addEventListener("change", function () {
      var id = izbor.value, ime = izbor.options[izbor.selectedIndex].textContent;
      if (!id) return;
      klic("magnetNaNapravo", [id, uri()]).then(function (r) {
        obvesti(r && r.ok ? t("magnetPoslano", { naprava: ime }) : t("magnetNiPoslano"));
      }).catch(function () { obvesti(t("magnetNiPoslano")); });
      izbor.selectedIndex = 0;
    });
    dejanja.appendChild(izbor);
    dejanja.appendChild(magnetGumb(t("magnetKopiraj"), function () {
      klic("kopiraj", [uri()]).then(function () { obvesti(t("magnetKopirano")); });
    }));
  }
  function predvajajMagnet(uri, f) {
    obvesti(t("magnetZaganjam"));
    klic("magnetDodaj", [uri, [f.i]]).then(function (d) {
      if (!d || !d.ok) { obvesti(magnetNapaka(d && d.koda)); return; }
      klic("magnetPredvajaj", [d.id, f.i, f.ime]).then(function (p) {
        if (!p || !p.ok) { obvesti(magnetNapaka(p && p.koda)); return; }
        if (f.vrsta === "video") zapriSloje();
        magnetOsveziPrenose();
      });
    }).catch(function () { obvesti(magnetNapaka("napaka")); });
  }
  function magnetOsveziPrenose() {
    klic("magnetSeznam").then(narisiMagnetPrenose).catch(function () {});
  }
  function narisiMagnetPrenose(seznam) {
    var v = $("magnetPrenosi");
    seznam = Array.isArray(seznam) ? seznam : [];
    var podpis = JSON.stringify(seznam.map(function (x) { return [x.id, x.stanje, x.deli_naprej, x.koncano]; }));
    if (!seznam.length) { v.innerHTML = ""; v.appendChild(el("p", "drobno", ubezi(t("magnetNiPrenosov")))); S.magnet.podpis = ""; return; }
    if (podpis !== S.magnet.podpis) {
      S.magnet.podpis = podpis; v.innerHTML = "";
      seznam.forEach(function (x) { v.appendChild(magnetVrsticaPrenosa(x)); });
    }
    seznam.forEach(function (x) {
      var vr = v.querySelector('[data-prenos="' + x.id + '"]'); if (!vr) return;
      var odst = x.skupaj ? Math.floor(100 * x.preneseno / x.skupaj) : 0;
      vr.querySelector("i").style.width = odst + "%";
      vr.querySelector("small").textContent = x.koncano ? t("magnetKoncano") + " · " + velikostMedija(x.skupaj) :
        odst + " % · " + x.hitrost_mibs.toFixed(1) + " MiB/s · " + t("magnetPovezav", { n: x.povezave }) +
        (x.stanje === "paused" ? " · " + t("magnetPremor") : "");
    });
  }
  function magnetVrsticaPrenosa(x) {
    var vr = el("div", "media-mapa"); vr.setAttribute("data-prenos", x.id);
    vr.innerHTML = svg("povezava") + '<div><b title="' + ubezi(x.ime) + '">' + ubezi(x.ime) + '</b><small></small></div>';
    vr.appendChild(el("div", "magnet-merilo", "<i></i>"));
    var d = el("div", "magnet-dejanja");
    var prva = (x.datoteke || []).filter(function (f) { return f.predvajljivo && f.vkljucena; })[0];
    if (prva) d.appendChild(magnetGumb("▶ " + t("magnetPredvajaj"), function () {
      klic("magnetPredvajaj", [x.id, prva.i, prva.ime]).then(function (p) {
        if (p && p.ok && prva.vrsta === "video") zapriSloje(); else if (!p || !p.ok) obvesti(magnetNapaka(p && p.koda));
      });
    }));
    d.appendChild(magnetGumb(x.stanje === "paused" ? t("magnetNadaljuj") : t("magnetPremor"), function () {
      klic(x.stanje === "paused" ? "magnetNadaljuj" : "magnetPremor", [x.id]).then(magnetOsveziPrenose);
    }));
    d.appendChild(magnetGumb(t("magnetDeliNaprej"), function () {
      klic("magnetDeliNaprej", [x.hash, !x.deli_naprej]).then(function () {
        if (!x.deli_naprej) klic("magnetNadaljuj", [x.id]);
        magnetOsveziPrenose();
      });
    }, x.deli_naprej ? "vklopljen" : ""));
    magnetPosiljanje(d, function () { return "magnet:?xt=urn:btih:" + x.hash + "&dn=" + encodeURIComponent(x.ime); });
    d.appendChild(magnetGumb(t("magnetMapa"), function () { klic("magnetMapa", [x.mapa]); }));
    d.appendChild(magnetGumb(t("magnetOdstrani"), function () { klic("magnetOdstrani", [x.id, false]).then(magnetOsveziPrenose); }));
    if (!x.lastna) d.appendChild(magnetGumb(t("magnetIzbrisi"), function (g) {
      // Dva koraka: brisanje prenesenih datotek je nepovratno.
      if (!g.dataset.potrdi) { g.dataset.potrdi = "1"; g.textContent = t("magnetIzbrisiRes"); return; }
      klic("magnetOdstrani", [x.id, true]).then(magnetOsveziPrenose);
    }));
    vr.appendChild(d);
    return vr;
  }
  function naloziMedijskeMape() {
    return klic("medijskeMape").then(function (mape) {
      S.mediaMape = Array.isArray(mape) ? mape : [];
      if ($("slojMediaMape").classList.contains("viden")) narisiMedijskeMape();
    }).catch(function () {});
  }
  function mediaKartica(v) {
    var ovoj = el("article", "media-kartica" + (v.naVoljo ? "" : " nedosegljiva"));
    var b = el("button", "media-kartica-odpri");
    b.type = "button";
    b.title = v.pot;
    var nadaljuj = (v.vrsta === "filmi" || v.vrsta === "serije") &&
      v.pozicija >= 15 && v.trajanje > v.pozicija + 20;
    var napredek = nadaljuj ? '<span class="media-kartica-nadaljuj">' + ubezi(t("mediaNadaljuj")) +
      ' · ' + casMedija(v.pozicija) + '</span><span class="media-kartica-merilo"><i style="width:' +
      Math.min(100, Math.round(v.pozicija / v.trajanje * 100)) + '%"></i></span>' : '';
    // Slika v knjižnici pokaže sebe; nalaganje odložimo, dokler kartica ni na zaslonu.
    var slicica = v.vrsta === "slike" && v.naVoljo ? '<img loading="lazy" decoding="async" alt="" src="' + ubezi(datotekaUrl(v.pot)) + '">' : "";
    b.innerHTML = '<span class="media-kartica-art ' + ubezi(v.vrsta) + '">' + svg(v.vrsta === "glasba" ? "glasba" : v.vrsta === "slike" ? "slika" : "video") +
      slicica + napredek +
      '</span><span class="media-kartica-pod"><b>' + ubezi(v.ime) + '</b><small>' + ubezi(mediaVrsta(v.vrsta)) +
      (v.naVoljo ? "" : " · " + ubezi(t("mediaManjka"))) + '</small></span>';
    b.disabled = !v.naVoljo;
    b.addEventListener("click", function () {
      if (v.vrsta === "slike") {
        var slike = S.mediaLokalno.filter(function (x) { return x.vrsta === "slike" && x.naVoljo; });
        odpriGalerijo(slike, Math.max(0, slike.findIndex(function (x) { return x.pot === v.pot; })));
        return;
      }
      odpriLokalno(v.pot);
    });
    b.setAttribute("data-ime", v.ime + " — " + mediaVrsta(v.vrsta));
    b.setAttribute("data-ogledano", v.ogledano ? "1" : "");
    if (v.naVoljo) poveziMeniKartice(b, { kljuc: "pot:" + v.pot, naslov: v.ime, ogledljivo: v.vrsta === "filmi" || v.vrsta === "serije",
                                          opis: { naslov: v.ime, vrsta: v.vrsta, pot: v.pot } });
    ovoj.appendChild(b);
    var odstrani = el("button", "media-kartica-odstrani", svg("x"));
    odstrani.type = "button"; odstrani.title = t("odstrani");
    odstrani.addEventListener("click", function () {
      klic("odstraniLokalniMedij", [v.pot]).then(function (ok) { if (ok) naloziMedije(); });
    });
    ovoj.appendChild(odstrani);
    return ovoj;
  }
  // Skladba z diska: ime datoteke je pogosto »Izvajalec - Naslov«. Velik naslov, izvajalec pod njim.
  function mediaSkladbaImena(ime) {
    var cisto = String(ime || "").replace(/\.[a-z0-9]{2,4}$/i, "").replace(/_/g, " ").trim();
    var m = cisto.match(/^(.{1,80}?)\s+[-\u2013\u2014]\s+(.+)$/);
    return m ? { naslov: m[2].trim(), izvajalec: m[1].trim() } : { naslov: cisto, izvajalec: "" };
  }
  // Glasba z diska kot vrstica (ne velika kartica z enako ikono za vsako skladbo - lastnik, 11. 10. 2026).
  function mediaSkladba(v) {
    var imena = mediaSkladbaImena(v.ime);
    var ovoj = el("article", "media-skladba" + (v.naVoljo ? "" : " nedosegljiva"));
    var b = el("button", "media-skladba-odpri",
      '<span class="media-skladba-znak">' + svg("glasba") + '</span><span class="media-skladba-besedilo"><b>' + ubezi(imena.naslov) +
      '</b><small>' + ubezi(imena.izvajalec || mediaVrsta(v.vrsta)) + (v.naVoljo ? "" : " · " + ubezi(t("mediaManjka"))) + '</small></span>' +
      (v.trajanje ? '<span class="media-skladba-cas">' + casMedija(v.trajanje) + '</span>' : ""));
    b.type = "button"; b.title = v.pot; b.disabled = !v.naVoljo;
    b.addEventListener("click", function () { odpriLokalno(v.pot); });
    b.setAttribute("data-ime", imena.naslov + (imena.izvajalec ? " — " + imena.izvajalec : ""));
    if (v.naVoljo) poveziMeniKartice(b, { kljuc: "pot:" + v.pot, naslov: imena.naslov, ogledljivo: false,
                                          opis: { naslov: v.ime, vrsta: v.vrsta, pot: v.pot } });
    ovoj.appendChild(b);
    var odstrani = el("button", "media-kartica-odstrani", svg("x"));
    odstrani.type = "button"; odstrani.title = t("odstrani");
    odstrani.addEventListener("click", function () {
      klic("odstraniLokalniMedij", [v.pot]).then(function (ok) { if (ok) naloziMedije(); });
    });
    ovoj.appendChild(odstrani);
    return ovoj;
  }
  function narisiLokalnoGlasbo(skladbe, vrsta) {
    var c = $("katLokalnaGlasba"); if (!c) return;
    c.innerHTML = "";
    var vidno = skladbe.length && (vrsta === "vse" || vrsta === "glasba");
    // Razdelek je del pregleda Glasbe, ne odprtega seznama predvajanja: v seznamu (Spotify, YouTube, svoj) so samo
    // njegove skladbe (lastnik, 18. 10. 2026: nad seznamom Spotify je bil »Na tem računalniku«). Narisan ostane za
    // »← Vsi seznami«; vidnost ob odprtju in zaprtju seznama uskladi narisiKatalog.
    c.hidden = !vidno || (typeof kat !== "undefined" && !!kat.seznam);
    if (!vidno) return;
    var glava = el("div", "kat-knjiznica-glava");
    glava.appendChild(el("h3", "", ubezi(t("katNaTemRacunalniku")) + ' <small>' + skladbe.length + '</small>'));
    c.appendChild(glava);
    var seznamSkladb = el("div", "media-skladbe");
    var omejeno = vrsta === "vse" && skladbe.length > 8;
    (omejeno ? skladbe.slice(0, 8) : skladbe).forEach(function (v) { seznamSkladb.appendChild(mediaSkladba(v)); });
    if (omejeno) {
      var vse = el("button", "media-skladbe-vse", ubezi(t("mediaVseSkladbe", { n: skladbe.length })) + svg("desno"));
      vse.type = "button";
      vse.addEventListener("click", function () { izberiMedijskoKategorijo("glasba"); naloziMedije(); });
      seznamSkladb.appendChild(vse);
    }
    c.appendChild(seznamSkladb);
  }
  function mediaVir(v) {
    var x = v.program || v.spletna;
    var b = el("button", "media-vir", '<span class="media-vir-znak">' + svg(v.vrsta === "glasba" ? "glasba" : v.vrsta === "radio" ? "radio" : "video") +
      '</span><span><b>' + ubezi(x.ime) + '</b><small>' + ubezi(mediaVrsta(v.vrsta)) +
      ' · ' + ubezi(v.program ? t("mediaLokalniProgram") : t("mediaSpletniVir")) + '</small></span>' + svg("desno"));
    b.type = "button";
    b.addEventListener("click", function () {
      if (v.program) zazeni(v.program);
      else klic("medij", [v.spletna.url]).catch(function () { obvesti(t("niUspelo")); });
    });
    return b;
  }
  function mediaTok(v) {
    var ovoj = el("div", "media-tok");
    var b = el("button", "media-vir", '<span class="media-vir-znak">' + svg(v.vrsta === "radio" ? "radio" : "video") +
      '</span><span><b>' + ubezi(v.ime) + '</b><small>' + ubezi(mediaVrsta(v.vrsta)) + ' · ' + ubezi(t("mediaVZivo")) + '</small></span>');
    b.type = "button"; b.title = v.url;
    b.addEventListener("click", function () { odpriTok(v.url); });
    b.setAttribute("data-ime", v.ime + " — " + mediaVrsta(v.vrsta));
    poveziMeniKartice(b, { kljuc: "tok:" + v.url, naslov: v.ime, ogledljivo: false, opis: { naslov: v.ime, vrsta: v.vrsta } });
    ovoj.appendChild(b);
    var odstrani = el("button", "media-tok-odstrani", svg("x"));
    odstrani.type = "button"; odstrani.title = t("odstrani");
    odstrani.addEventListener("click", function () {
      klic("odstraniMedijskiTok", [v.url]).then(function (ok) { if (ok) naloziMedije(); });
    });
    ovoj.appendChild(odstrani);
    return ovoj;
  }
  function mediaPredlog(v) {
    var b = el("button", "media-predlog", '<span class="media-predlog-znak">' + svg(v.vrsta === "glasba" ? "glasba" : v.vrsta === "radio" ? "radio" : "video") +
      '</span><b>' + ubezi(v.ime) + '</b><small>' + ubezi(t("mediaSpletnaStran")) + ' · ' +
      ubezi(v.obmocje === "world" ? t("mediaSvetovno") : t("mediaPoRegiji")) + '</small>');
    // Predlog odpre spletno stran ponudnika – ni neposredni tok in ne obljublja predvajanja brez pogojev ponudnika.
    b.title = t("mediaSpletnaStranNamig");
    b.type = "button";
    b.addEventListener("click", function () { odpriVSpletu(v.url); });
    return b;
  }
  function narisiMedije() {
    var kategorije = $("mediaKategorije"), mreza = $("mediaMreza");
    if (!kategorije || !mreza) return;
    var vsi = medijskiVnosi(), lokalni = S.mediaLokalno;
    // Isti zavihki dvakrat: vodoravno (ozek prostor) in v levi navigaciji (namizje); vidna je ena postavitev (CSS).
    [[kategorije, "media-kategorija"], [$("mediaNavKategorije"), "media-nav-kategorija"]].forEach(function (cilj) {
      if (!cilj[0]) return;
      cilj[0].innerHTML = "";
      cilj[0].setAttribute("aria-label", t("mediji"));
      // Skriti zavihki niso v meniju; odprt zavihek (npr. prek »Vse →«) ostane viden, da uporabnik ve, kje je.
      MEDIA_KATEGORIJE.filter(function (k) { return kategorijaVidna(k) && (k[0] === S.mediaFilter || !jeSkrito("kat:" + k[0])); }).forEach(function (k) {
        var b = el("button", cilj[1] + (S.mediaFilter === k[0] ? " izbrana" : ""),
          svg(k[1]) + '<span>' + ubezi(t("media_" + k[0])) + '</span>');
        b.type = "button"; b.setAttribute("role", "tab");
        b.setAttribute("aria-selected", S.mediaFilter === k[0] ? "true" : "false");
        b.setAttribute("data-kategorija", k[0]);
        b.addEventListener("click", function () { izberiZavihekMedijev(k[0]); });
        // Skrcena navigacija kaze samo ikone: ime ostane bralniku zaslona in namigu.
        if (cilj[1] === "media-nav-kategorija") { b.setAttribute("aria-label", t("media_" + k[0])); b.title = t("media_" + k[0]); }
        poveziMeniNav(b, "kat:" + k[0], t("media_" + k[0]));
        cilj[0].appendChild(b);
      });
    });
    $("mediaNav").setAttribute("aria-label", t("mediji"));
    narisiSamodejne();
    var domov = S.mediaFilter === "domov";
    $("r-media").classList.toggle("domov", domov);
    if (!domov) narisiOdkrivanje();      // police odkrivanja so samo na Domov: skrije jih takoj, ne sele po odgovoru polic
    if (domov) {
      $("mediaVec").hidden = true;
      $("r-media").classList.remove("brez-krajevnega");      // pravila prejsnjega zavihka ne skrijejo praznega stanja
      narisiMediaDomov();
      osveziPredvajalnik(S.mediaPredvajalnik);
      uskladiKatalog();
      return;
    }
    $("mediaJunak").hidden = true;
    var iskano = String(S.mediaIskanje || "").trim().toLocaleLowerCase();
    var vrsta = S.mediaFilter;
    var prikaz = lokalni.filter(function (v) { return (vrsta === "vse" || v.vrsta === vrsta ||
      vrsta === "video" && (v.vrsta === "filmi" || v.vrsta === "serije")) && mediaUstreza(v, iskano); });
    var viri = vsi.filter(function (v) { return (vrsta === "vse" || v.vrsta === vrsta) && mediaUstreza(v.program || v.spletna, iskano); });
    var tokovi = S.mediaTokovi.filter(function (v) { return (vrsta === "vse" || v.vrsta === vrsta) && mediaUstreza(v, iskano); });
    var dodani = spletne().map(function (v) { return kljucNaslova(v.url); });
    var predlogi = MEDIA_PREDLOGI.filter(function (v) { return (vrsta === "vse" || v.vrsta === vrsta) && mediaUstreza(v, iskano) && dodani.indexOf(kljucNaslova(v.url)) < 0; });
    $("mediaStevec").textContent = prikaz.length ? String(prikaz.length) : "";
    $("mediaNaslovZbirke").textContent = vrsta === "vse" ? t("katRezultati") : mediaVrsta(vrsta);
    var samoViri = vrsta === "tv" || vrsta === "twitch" || vrsta === "radio";
    $("mediaMreza").previousElementSibling.hidden = samoViri;
    $("mediaMreza").hidden = samoViri;
    mreza.innerHTML = "";
    // Filmi, serije in slike kot kartice; glasba kot seznam skladb. V »Vse« najvec 8 skladb, ostale so v Glasbi.
    // Glasba s tega racunalnika je del kataloga Glasba (in Vse): seznam skladb v katalogu, ne svoj razdelek nad njim.
    var skladbe = prikaz.filter(function (v) { return v.vrsta === "glasba"; });
    var neGlasba = prikaz.filter(function (v) { return v.vrsta !== "glasba"; });
    neGlasba.forEach(function (v) { mreza.appendChild(mediaKartica(v)); });
    narisiLokalnoGlasbo(skladbe, vrsta);
    // Eno prazno stanje na zavihek (lastnik, 14. 10. 2026): kjer je katalog, prazno stanje pokaze on (z enim dejanjem);
    // prazna krajevna knjiznica s svojim gumbom ostane samo pri Slikah, ki kataloga nimajo.
    var imaKatalog = !!KAT_VRSTE[vrsta];
    $("mediaPrazno").hidden = samoViri || prikaz.length !== 0 || imaKatalog;
    $("mediaPraznoZnak").innerHTML = svg(vrsta === "slike" ? "slika" : vrsta === "glasba" ? "glasba" : "video");
    // Knjiznica nad katalogom je samo za filme, serije in slike; glasba je v katalogu.
    var samoGlasba = prikaz.length > 0 && !neGlasba.length;
    var brezKrajevnih = imaKatalog && !neGlasba.length;
    $("mediaMreza").previousElementSibling.hidden = samoViri || samoGlasba || brezKrajevnih;
    $("mediaMreza").hidden = samoViri || samoGlasba || brezKrajevnih;
    $("mediaVec").hidden = samoViri || !S.mediaHasMore;
    $("mediaOsvezi").disabled = !S.mediaMape.length || S.mediaOsvezuje;
    $("mediaPraznoNaslov").textContent = iskano ? t("niZadetkov") : t("mediaPraznoNaslov");
    $("mediaPraznoOpis").textContent = iskano ? "" : t("mediaPraznoOpis");
    $("medijiDodajPrazno").hidden = !!iskano;
    var seznamTokov = $("mediaTokovi"); seznamTokov.innerHTML = "";
    tokovi.forEach(function (v) { seznamTokov.appendChild(mediaTok(v)); });
    $("mediaTokoviGlava").hidden = !tokovi.length;
    seznamTokov.hidden = !tokovi.length;
    var vrsticaVirov = $("mediaViri"); vrsticaVirov.innerHTML = "";
    viri.forEach(function (v) { vrsticaVirov.appendChild(mediaVir(v)); });
    $("mediaViri").previousElementSibling.hidden = !viri.length;
    $("mediaViri").hidden = !viri.length;
    var odkrij = $("mediaOdkrij"); odkrij.innerHTML = "";
    predlogi.forEach(function (v) { odkrij.appendChild(mediaPredlog(v)); });
    $("mediaOdkrij").previousElementSibling.hidden = !predlogi.length;
    $("mediaOdkrij").hidden = !predlogi.length;
    osveziPredvajalnik(S.mediaPredvajalnik);
    // Brez krajevnih vsebin v izbrani kategoriji gre katalog pred prazno knjižnico (sicer bi ga odrivala navzdol).
    $("r-media").classList.toggle("brez-krajevnega", samoViri || neGlasba.length === 0);
    uskladiKatalog();
  }
  // Klik na zavihek (vodoravni ali v levi navigaciji) ali na »Vse →« police na Domov.
  function izberiZavihekMedijev(k) {
    // Klik na zavihek med iskanjem: iskanje se konca, pokaze se zavihek (ne mesanica vseh vrst).
    if (S.mediaFilter === "vse") { S.mediaIskanje = ""; $("mediaIskanje").value = ""; }
    izberiMedijskoKategorijo(k); naloziMedije();
  }
  // ---- leva navigacija: gumb na vrhu jo skrci na ikone in razsiri nazaj (ime v namigu). Lastnik 18. 10. 2026: samo ena
  // moznost (»Skrij meni« in rocaj odstranjena, brez podvajanja). Tipke: v glavnem oknu Ctrl+Shift+B (Ctrl+B je stranska
  // vrstica), v Safeer Playerju tudi Ctrl+B. Zapomni si vsaka vrsta okna posebej (udobje tega uporabnika: localStorage).
  var NAV_KLJUC = "safeer_media_nav_" + (PREDVAJALNIK ? "player" : "glavno");
  function navTipka() { return PREDVAJALNIK ? "Ctrl+B" : "Ctrl+Shift+B"; }
  function navSkrcena() { var r = $("r-media"); return !!r && r.classList.contains("nav-skrcena"); }
  function navNastavi(skrcena) {
    var r = $("r-media"); if (!r) return;
    r.classList.toggle("nav-skrcena", !!skrcena);
    try { localStorage.setItem(NAV_KLJUC, skrcena ? "skrcena" : ""); } catch (e) {}
    navNapisi();
  }
  function navNapisi() {
    var s = navSkrcena(), g = $("mediaNavSkrci"), pril = $("mediaNavPrilagodi");
    if (!g) return;
    g.title = t(s ? "mediaNavRazsiri" : "mediaNavSkrci", { tipka: navTipka() });
    g.setAttribute("aria-label", g.title);
    g.setAttribute("aria-expanded", s ? "false" : "true");
    pril.setAttribute("aria-label", t("mediaPrilagodiMeni")); pril.title = t("mediaPrilagodiMeni");
  }
  function poveziNav() {
    if (!$("mediaNavSkrci")) return;
    // Prej shranjena »skrita« (odstranjena moznost) se pokaze kot skrcena: meni ostane dosegljiv.
    try { var shranjeno = localStorage.getItem(NAV_KLJUC); if (shranjeno === "skrcena" || shranjeno === "skrita") navNastavi(true); } catch (e) {}
    navNapisi();
    $("mediaNavSkrci").addEventListener("click", function () { navNastavi(!navSkrcena()); });
    document.addEventListener("keydown", function (e) {
      if (!(e.ctrlKey || e.metaKey) || e.altKey || (e.key !== "b" && e.key !== "B")) return;
      if (!(e.shiftKey || PREDVAJALNIK)) return;          // Ctrl+B v glavnem oknu ostane stranski vrstici
      var r = $("r-media"); if (!r || r.offsetParent === null || (!PREDVAJALNIK && S.razdelek !== "media")) return;
      e.preventDefault();
      navNastavi(!navSkrcena());
    });
  }

  // ---- prilagojen meni (lastnik, 14. 10. 2026: »skrij, kar uporabnik ne potrebuje«): vsak zavihek razen Domov in vsak
  // vir v levi navigaciji (in v vodoravnih zavihkih) se da skriti - desni klik, tipka Meni, Shift+F10, dolg pritisk ali
  // gumb Y na ploscku, ali v plosci »Prilagodi meni«. Skrito je samo v meniju: podatki in viri ostanejo, iskanje najde
  // vse. Shranjeno v nastavitvah Medijskega centra (core/os_katalog.py), skupno glavnemu oknu in Safeer Playerju.
  // ---- kategorija »Zasebno« (lastnik, 17. 10. 2026): stanje in stevilo zasebnih dodatkov pove jedro (core/os_katalog.py).
  function nastaviZasebno(z) {
    var prej = !!S.mediaZasebno.vklopljeno;
    S.mediaZasebno = { vklopljeno: !!(z && z.vklopljeno), skriti: (z && z.skriti) || 0 };
    var g = $("katZasebno"); if (g) g.setAttribute("aria-checked", S.mediaZasebno.vklopljeno ? "true" : "false");
    if (prej === S.mediaZasebno.vklopljeno) return;
    if (!S.mediaZasebno.vklopljeno && S.mediaFilter === "zasebno") { izberiMedijskoKategorijo("domov"); naloziMedije(); return; }
    narisiMedije();
  }
  function jeSkrito(kljuc) { return kljuc !== "kat:domov" && !!S.mediaSkrito[kljuc]; }
  function nastaviSkrito(seznam, ob_nalaganju) {
    var prej = S.mediaSkritoNalozeno;
    S.mediaSkrito = {};
    (Array.isArray(seznam) ? seznam : []).forEach(function (k) { S.mediaSkrito[k] = 1; });
    S.mediaSkritoNalozeno = true;
    // Zapomnjen zavihek je skrit: Medijski center se odpre na Domov (samo ob odprtju; »Vse →« ga se vedno odpre).
    if (ob_nalaganju && !prej && jeSkrito("kat:" + S.mediaFilter)) { izberiMedijskoKategorijo("domov"); naloziMedije(); return; }
    narisiMedije();
    osveziPoliceSkrite();
    if ($("slojPrilagodi").classList.contains("viden")) narisiPrilagodi();
  }
  // Police na Domov, ki jih je uporabnik skril (»polica:samodejni«, »polica:nazadnje«): ne naloze se in ne narisejo
  // (kartice, naslovnice in podatki ne zasedajo pomnilnika); ob ponovnem vklopu se naloze znova.
  var SKRIVNE_POLICE = [["polica:samodejni", "samNaslov"], ["polica:nazadnje", "policaNazadnje"]];
  // ---- skripte, ki jih uporabnik sam uvozi (core/uporabniske_skripte.py): JavaScript v strani Spotify, shell na ukaz.
  // Safeer skript ne dostavlja; uporabnik jih uvozi iz datoteke po opozorilu, vklopi ali zazene sam.
  var SKR = { seznam: null, cakajoca: null, izpis: null };
  function naloziSkripte() {
    klic("mediaSkripte").then(function (r) {
      SKR.seznam = (r && r.skripte) || [];
      SKR.primer = (r && r.primer) || "";
      if ($("slojPrilagodi") && $("slojPrilagodi").classList.contains("viden")) narisiPrilagodi();
    }, function () { SKR.seznam = SKR.seznam || []; });
  }
  function skriptaNapaka(r) {
    var k = r && r.napaka;
    obvesti(t(k === "vrsta" ? "skriptaNapakaVrsta" : k === "velikost" ? "skriptaNapakaVelikost" : (k === "pot" || k === "ni_datoteke") ? "skriptaNapakaPot" : k === "cas" ? "skriptaCas" : "skriptaNapaka"));
  }
  function narisiSkripte(cilj) {
    if (SKR.seznam === null) { SKR.seznam = []; naloziSkripte(); }
    var g = el("fieldset", "prilagodi-skupina prilagodi-skripte");
    g.appendChild(el("legend", "", ubezi(t("skriptePrilagodi"))));
    g.appendChild(el("p", "drobno", ubezi(t("skripteOpis"))));
    SKR.seznam.forEach(function (s) {
      var v = el("div", "media-mapa prilagodi-vrstica skripta-vrstica");
      // Kje tece JavaScript, pove glava skripte (core/uporabniske_skripte.kje): brez glave samo Spotify, z glavo tudi Splet.
      var kjeJs = { splet: "skriptaJsSplet", oboje: "skriptaJsOboje", ne: "skriptaJsNe" }[s.kje] || "skriptaJs";
      v.appendChild(el("div", "", "<b>" + ubezi(s.ime) + "</b><small>" + ubezi(t(s.vrsta === "js" ? kjeJs : "skriptaSh")) + "</small>"));
      if (s.vrsta === "js") {
        var cb = document.createElement("input"); cb.type = "checkbox"; cb.checked = !!s.vklopljena;
        cb.setAttribute("aria-label", t("skriptaVklop") + ": " + s.ime);
        cb.addEventListener("change", function () {
          klic("mediaSkriptaVklop", [s.id, cb.checked]).then(function (r) {
            if (r && r.ok) { s.vklopljena = cb.checked; obvesti(s.kje === "spotify" || !s.kje ? t("skriptaJsObvestilo") : s.kje === "oboje" ? t("skriptaJsObvestilo") + " " + t("skriptaJsSpletObvestilo") : t("skriptaJsSpletObvestilo")); } else { skriptaNapaka(r); cb.checked = !cb.checked; }
          }, function () { skriptaNapaka(null); cb.checked = !cb.checked; });
        });
        v.appendChild(cb);
      } else {
        var z = el("button", "media-polica-vse", "<span>" + ubezi(t("skriptaZazeni")) + "</span>"); z.type = "button";
        z.addEventListener("click", function () {
          z.disabled = true;
          klic("mediaSkriptaZazeni", [s.id]).then(function (r) {
            SKR.izpis = { ime: s.ime, r: r || {} }; narisiPrilagodi();
          }, function () { z.disabled = false; skriptaNapaka(null); });
        });
        v.appendChild(z);
      }
      var o = el("button", "media-polica-vse", "<span>" + ubezi(t("skriptaOdstrani")) + "</span>"); o.type = "button";
      o.setAttribute("aria-label", t("skriptaOdstrani") + ": " + s.ime);
      o.addEventListener("click", function () {
        klic("mediaSkriptaOdstrani", [s.id]).then(function () { if (SKR.izpis && SKR.izpis.ime === s.ime) SKR.izpis = null; naloziSkripte(); }, function () { skriptaNapaka(null); });
      });
      v.appendChild(o);
      g.appendChild(v);
    });
    if (SKR.izpis) {
      var r = SKR.izpis.r, glava = SKR.izpis.ime + " - " + (r.napaka === "cas" ? t("skriptaCas") : t("skriptaKonec", { koda: String(r.koda) }));
      g.appendChild(el("small", "", ubezi(glava)));
      var pre = el("pre", "skripta-izpis", ubezi(String(r.izpis || "")));
      g.appendChild(pre);
    }
    if (SKR.cakajoca) {
      var c = el("div", "skripta-opozorilo");
      c.appendChild(el("p", "drobno", ubezi(t("skriptaOpozorilo", { ime: SKR.cakajoca.ime }))));
      var da = el("button", "media-polica-vse", "<span>" + ubezi(t("skriptaPotrdi")) + "</span>"); da.type = "button";
      da.addEventListener("click", function () {
        var p = SKR.cakajoca; SKR.cakajoca = null;
        klic("mediaSkriptaUvozi", [p.ime, p.vsebina]).then(function (r) {
          if (r && r.ok) { obvesti(t("skriptaUvozena")); naloziSkripte(); } else { skriptaNapaka(r); narisiPrilagodi(); }
        }, function () { skriptaNapaka(null); narisiPrilagodi(); });
      });
      var ne = el("button", "media-polica-vse", "<span>" + ubezi(t("skriptaPreklici")) + "</span>"); ne.type = "button";
      ne.addEventListener("click", function () { SKR.cakajoca = null; narisiPrilagodi(); });
      c.appendChild(da); c.appendChild(ne); g.appendChild(c);
    }
    var datoteka = document.createElement("input"); datoteka.type = "file"; datoteka.accept = ".js,.sh,text/plain,application/javascript"; datoteka.hidden = true;
    datoteka.addEventListener("change", function () {
      var f = datoteka.files && datoteka.files[0]; if (!f) return;
      if (f.size > 256 * 1024) { skriptaNapaka({ napaka: "velikost" }); return; }
      var bralec = new FileReader();
      bralec.onload = function () { SKR.cakajoca = { ime: f.name, vsebina: String(bralec.result || "") }; narisiPrilagodi(); };
      bralec.onerror = function () { skriptaNapaka(null); };
      bralec.readAsText(f);
    });
    var uvozi = el("button", "media-polica-vse", "<span>" + ubezi(t("skriptaUvozi")) + "</span>"); uvozi.type = "button";
    uvozi.addEventListener("click", function () { datoteka.click(); });
    g.appendChild(uvozi); g.appendChild(datoteka);
    // Pot vpisana rocno (lastnik, 18. 10. 2026): kdor datoteke v oknu za izbiro ne najde, jo vpise, npr. ~/Prejemi/x.js.
    var vrsticaPot = el("div", "skripta-pot");
    var pot = document.createElement("input"); pot.type = "text"; pot.spellcheck = false; pot.autocomplete = "off";
    pot.placeholder = SKR.primer ? t("skriptaPotPrimerPot", { pot: SKR.primer }) : t("skriptaPotPrimer"); pot.setAttribute("aria-label", t("skriptaPot"));
    var poPoti = el("button", "media-polica-vse", "<span>" + ubezi(t("skriptaUvoziPot")) + "</span>"); poPoti.type = "button";
    function uvoziSPoti() {
      var v = String(pot.value || "").trim(); if (!v) { pot.focus(); return; }
      klic("mediaSkriptaPreberi", [v]).then(function (r) {
        if (r && r.ok) { SKR.cakajoca = { ime: r.ime, vsebina: r.vsebina }; narisiPrilagodi(); } else skriptaNapaka(r);
      }, function () { skriptaNapaka(null); });
    }
    poPoti.addEventListener("click", uvoziSPoti);
    pot.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); uvoziSPoti(); } });
    vrsticaPot.appendChild(el("small", "drobno", ubezi(t("skriptaPot"))));
    vrsticaPot.appendChild(pot); vrsticaPot.appendChild(poPoti); g.appendChild(vrsticaPot);
    cilj.appendChild(g);
  }
  // Plakat z naslovom http:// (vir brez TLS, npr. goli IP): CSP strani dovoli samo https/file/data, zato sliko prenese
  // Safeer OS (core/plakati_predpomnilnik.py) in stran dobi pot do datoteke. Najvec 4 hkratni prenosi.
  var PLAKATI = { vrsta: [], teko: 0 };
  function plakatNaprej() {
    while (PLAKATI.teko < 4 && PLAKATI.vrsta.length) {
      var p = PLAKATI.vrsta.shift(); PLAKATI.teko++;
      klic("mediaPlakat", [p.url]).then(function (r) { return r; }, function () { return null; }).then(function (r) {
        PLAKATI.teko--;
        if (r && r.pot) p.img.src = "file://" + encodeURI(r.pot); else if (p.img.onerror) p.img.onerror();
        plakatNaprej();
      });
    }
  }
  function nastaviSliko(img, url) {
    if (typeof url === "string" && /^http:\/\//i.test(url)) { PLAKATI.vrsta.push({ img: img, url: url }); plakatNaprej(); }
    else img.src = url;
  }
  function osveziPoliceSkrite() {
    try {
      var sam = jeSkrito("polica:samodejni");
      if (sam) S.samodejni = [];
      else if (!(S.samodejni || []).length) naloziSamodejne();
      if (typeof POL !== "undefined") {
        POL.podpis = ""; POL.odkrPodpis = ""; narisiPolice(); narisiOdkrivanje();
        // Jedro skritih polic ne nalozi (core/os_katalog._police, _odkrivanje): ob spremembi police nalozimo znova -
        // spet vklopljena se pokaze, skrita sprosti pomnilnik tudi v jedru.
        if (POL.nalozeno) naloziPolice();
        if (S.mediaFilter === "domov") naloziOdkrivanje();
      }
      narisiSamodejne();
    } catch (e) { /* stran se se ne izrisuje */ }
  }
  function skrijPredmet(kljuc, da, ime) {
    return klic("mediaSkrij", [kljuc, !!da]).then(function (seznam) {
      // Skrit je zavihek, ki je odprt: pokaze se Domov.
      if (da && kljuc === "kat:" + S.mediaFilter) izberiMedijskoKategorijo("domov");
      nastaviSkrito(seznam, false);
      if (da && S.mediaFilter === "domov" && kljuc.indexOf("kat:") === 0) naloziMedije();
      if (da && ime) obvesti(t("mediaSkritoObvestilo", { ime: ime }));
      return true;
    }, function () { obvesti(t("niUspelo")); return false; });
  }
  // Meni predmeta navigacije: isti kot meni kartice (#mediaKarticaMeni - tipkovnica, Escape, klik drugam ga zapre).
  function odpriMeniNav(gumb, kljuc, ime) {
    var m = $("mediaKarticaMeni"); if (!m) return;
    m.innerHTML = ""; m._kartica = gumb;
    m.setAttribute("aria-label", ime);
    var naslov = el("b", "", ubezi(ime)); naslov.setAttribute("aria-hidden", "true"); m.appendChild(naslov);
    var postavka = function (ikona, besedilo, dejanje) {
      var b = el("button", "", svg(ikona) + "<span>" + ubezi(besedilo) + "</span>");
      b.type = "button"; b.setAttribute("role", "menuitem");
      b.addEventListener("click", function () { zapriMeniKartice(false); dejanje(); });
      m.appendChild(b);
    };
    if (kljuc !== "kat:domov") postavka("x", t("mediaSkrijIzMenija"), function () {
      skrijPredmet(kljuc, true, ime).then(function () {
        // Izbor ostane v meniju (tipkovnica, daljinec): na zavihku Domov.
        var prvi = document.querySelector(".media-nav-kategorija, .media-kategorija");
        var vidni = Array.prototype.filter.call(document.querySelectorAll(".media-nav-kategorija, .media-kategorija"), function (b) { return b.offsetParent; });
        (vidni[0] || prvi || document.body).focus();
      });
    });
    postavka("drsniki", t("mediaPrilagodiMeni"), function () { odpriPrilagodi(gumb); });
    m.hidden = false;
    var r = gumb.getBoundingClientRect();
    postaviPlavajoce(m, r.left + 12, r.bottom + 4, r.top - 4);
    m.querySelector("[role=menuitem]").focus();
  }
  // Desni klik, tipka Meni, Shift+F10, dolg pritisk (dotik) in gumb Y na ploscku (kavc.js poslje »contextmenu«).
  function poveziMeniNav(gumb, kljuc, ime) {
    gumb.addEventListener("contextmenu", function (e) { e.preventDefault(); e.stopPropagation(); odpriMeniNav(gumb, kljuc, ime); });
    gumb.addEventListener("keydown", function (e) {
      if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) { e.preventDefault(); e.stopPropagation(); odpriMeniNav(gumb, kljuc, ime); }
    });
    var ura = 0;
    gumb.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "mouse") return;
      clearTimeout(ura);
      ura = setTimeout(function () { gumb._dolgo = true; odpriMeniNav(gumb, kljuc, ime); }, 600);
    });
    ["pointerup", "pointerleave", "pointercancel"].forEach(function (d) { gumb.addEventListener(d, function () { clearTimeout(ura); }); });
    // Klik, ki konca dolg pritisk, ne odpre zavihka (meni je ze odprt).
    gumb.addEventListener("click", function (e) { if (gumb._dolgo) { gumb._dolgo = false; e.stopImmediatePropagation(); e.preventDefault(); } }, true);
  }
  // Plosca »Prilagodi meni«: potrditvena polja za vse zavihke (razen Domov) in vse vire - skrite tudi, da se vrnejo.
  function narisiPrilagodi() {
    var seznam = $("prilagodiSeznam"); if (!seznam) return;
    var aktivni = document.activeElement && document.activeElement.getAttribute ? document.activeElement.getAttribute("data-kljuc") : null;
    seznam.innerHTML = "";
    var skupina = function (naslovKljuc, predmeti) {
      if (!predmeti.length) return;
      var g = el("fieldset", "prilagodi-skupina");
      g.appendChild(el("legend", "", ubezi(t(naslovKljuc))));
      predmeti.forEach(function (p) {
        var vrstica = el("label", "media-mapa prilagodi-vrstica"), cb = document.createElement("input");
        cb.type = "checkbox"; cb.checked = !jeSkrito(p.kljuc); cb.setAttribute("data-kljuc", p.kljuc);
        cb.addEventListener("change", function () { skrijPredmet(p.kljuc, !cb.checked); });
        vrstica.appendChild(cb);
        vrstica.insertAdjacentHTML("beforeend", svg(p.ikona) + '<div><b>' + ubezi(p.ime) + '</b>' + (p.pod ? '<small>' + ubezi(p.pod) + '</small>' : "") + '</div>');
        g.appendChild(vrstica);
      });
      seznam.appendChild(g);
    };
    skupina("mediaPrilagodiVrste", MEDIA_KATEGORIJE.filter(function (k) { return k[0] !== "domov" && kategorijaVidna(k); }).map(function (k) {
      return { kljuc: "kat:" + k[0], ime: t("media_" + k[0]), ikona: k[1] };
    }));
    // Vse police Domov (tudi odkrivanje): skrito polico tu uporabnik spet vklopi.
    var police = SKRIVNE_POLICE.map(function (p) { return { kljuc: p[0], ime: t(p[1]), ikona: "glasba" }; });
    Object.keys(POLICE_NASLOVI).forEach(function (id) {
      if (id !== "nazadnje") police.push({ kljuc: "polica:" + id, ime: naslovPolice(id, "domov"), ikona: id.indexOf("odkrij_") === 0 ? "zvezda" : "glasba" });
    });
    skupina("policaPrilagodi", police);
    narisiSkripte(seznam);
    // Viri niso vec v levem stolpcu (lastnik, 17. 10. 2026), zato jih tu ni kaj skrivati.
    if (aktivni) { var cilj = seznam.querySelector('[data-kljuc="' + aktivni.replace(/"/g, "") + '"]'); if (cilj) cilj.focus(); }
  }
  function odpriPrilagodi(odkod) {
    var sloj = $("slojPrilagodi"); if (!sloj) return;
    sloj._odkod = odkod || document.activeElement;
    narisiPrilagodi();
    sloj.classList.add("viden");
    var prvi = sloj.querySelector("input[type=checkbox]") || $("prilagodiZapri");
    prvi.focus();
  }
  function zapriPrilagodi() {
    var sloj = $("slojPrilagodi"); if (!sloj || !sloj.classList.contains("viden")) return false;
    sloj.classList.remove("viden");
    var nazaj = sloj._odkod && document.contains(sloj._odkod) ? sloj._odkod : $("mediaNavPrilagodi");
    if (nazaj && nazaj.focus) nazaj.focus();
    return true;
  }
  function poveziPrilagodi() {
    $("mediaNavPrilagodi").addEventListener("click", function () { odpriPrilagodi(this); });
    $("prilagodiZapri").addEventListener("click", zapriPrilagodi);
    $("slojPrilagodi").querySelector(".tancica").addEventListener("click", zapriPrilagodi);
    // Escape (Nazaj na daljincu) zapre samo plosco, izbor se vrne tja, od koder je bila odprta.
    window.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && zapriPrilagodi()) { e.preventDefault(); e.stopImmediatePropagation(); }
    }, true);
  }

  // ---- samodejni seznami (core/samodejni_seznami.py): na Domov in na vrhu Glasbe; krajevno iz uporabnikove glasbe.
  // Kartica: kolaz iz pravih naslovnic, ime in stevilo skladb; klik predvaja (vrsta strani, kot seznam predvajanja),
  // »Shrani kot seznam« ga kopira med navadne sezname (od tedaj se ne spreminja vec).
  function imeSamodejnega(sz) {
    if (sz.vrsta === "izvajalec") return t("samMesanica", { ime: sz.ime });
    if (sz.vrsta === "zanr") return sz.ime;
    return t({ najvec: "samNajvec", nazadnje: "samNazadnje", dolgo: "samDolgo", odkrij: "samOdkrij" }[sz.vrsta] || "samNaslov");
  }
  function naloziSamodejne() {
    if (!most) return;
    if (jeSkrito("polica:samodejni")) { S.samodejni = []; return; }
    klic("mediaSamodejniSeznami", []).then(function (r) {
      S.samodejni = r && Array.isArray(r.seznami) ? r.seznami : [];
      narisiSamodejne();
    }).catch(function () {});
  }
  function predvajajSamodejni(sz) {
    klic("mediaSamodejniSeznam", [sz.id]).then(function (r) {
      var vnosi = (r && r.vnosi) || [];
      // Seznama ni vec (izracunan znova): brez sporocila, kartica se osvezi (lastnik 18. 10. 2026: kar ne gre, ne kazemo).
      if (!vnosi.length) { naloziSamodejne(); return; }
      prekliciNaslednjo();
      // Vrsta strani v stalnem vrstnem redu; mesa samo gumb »Nakljucno« (premesajVrsto).
      novaVrsta(vnosi, 0, { tip: "samodejni", ref: sz.id, vrsta: sz.vrsta, ime: sz.ime || "" });
      zacniOdZacetka();
      narisiVrsto();
      odpriKatalogVnos(kat.vrsta[kat.vrstaMesto]);
    }, function () {});
  }
  function shraniSamodejni(sz) {
    var ime = imeSamodejnega(sz);
    klic("mediaSamodejniShrani", [sz.id, ime]).then(function (r) {
      if (r && r.ok) { obvesti(t("samShranjen", { ime: r.ime })); naloziSeznamePredvajanja(); }
      else obvesti(t("seznamNiMogoce"));
    }, function () { obvesti(t("seznamNiMogoce")); });
  }
  // Kolaz 2 x 2 iz stirih pravih naslovnic; z manj naslovnicami prva cez celo kartico (kot Spotify), brez nje znak.
  function kolaz(slike) {
    var n = slike.length >= 4 ? 4 : slike.length ? 1 : 0;
    var k = el("span", "media-kolaz" + (n === 4 ? "" : n ? " ena" : " prazen")); k.setAttribute("aria-hidden", "true");
    if (!n) { k.innerHTML = svg("glasba"); return k; }
    slike.slice(0, n).forEach(function (pot) {
      var img = document.createElement("img"); img.alt = ""; img.loading = "lazy"; img.src = pot;
      img.onerror = function () { this.remove(); if (!k.querySelector("img")) { k.className = "media-kolaz prazen"; k.innerHTML = svg("glasba"); } };
      k.appendChild(img);
    });
    return k;
  }
  function gumbSkrijPolico(kljuc, ime) {
    var b = el("button", "media-polica-vse", "<span>" + ubezi(t("policaSkrij")) + "</span>");
    b.type = "button"; b.setAttribute("aria-label", t("policaSkrij") + ": " + ime);
    b.addEventListener("click", function () { skrijPredmet(kljuc, true, ime); });
    return b;
  }
  function narisiSamodejne() {
    var c = $("mediaSamodejni"); if (!c) return;
    var seznami = S.samodejni || [];
    var vidno = (S.mediaFilter === "domov" || S.mediaFilter === "glasba") && !String(S.mediaIskanje || "").trim() && seznami.length > 0 && !jeSkrito("polica:samodejni");
    c.hidden = !vidno;
    if (jeSkrito("polica:samodejni") && c._podpis) { c.innerHTML = ""; c._podpis = ""; }
    if (S.mediaFilter === "domov" && typeof POL !== "undefined") narisiMediaDomov();      // prazno stanje Domov je odvisno tudi od samodejnih seznamov
    var podpis = JSON.stringify(seznami) + "|" + jezik;
    if (!vidno || c._podpis === podpis) return;
    c._podpis = podpis;
    var izbran = document.activeElement && c.contains(document.activeElement) ? document.activeElement.getAttribute("data-id") : null;
    c.innerHTML = "";
    var glava = el("h3", "media-polica-naslov", ubezi(t("samNaslov"))); glava.id = "mediaSamodejniNaslov";
    var vrhSam = el("div", "media-polica-glava");
    vrhSam.appendChild(glava);
    vrhSam.appendChild(gumbSkrijPolico("polica:samodejni", t("samNaslov")));
    c.appendChild(vrhSam);
    var vrsta = el("div", "media-polica-vrsta media-samodejni-vrsta"); vrsta.setAttribute("role", "list");
    seznami.forEach(function (sz) {
      var ime = imeSamodejnega(sz);
      var ovoj = el("div", "media-samodejni-ovoj"); ovoj.setAttribute("role", "listitem");
      var kartica = el("button", "kat-kartica media-samodejni-kartica"); kartica.type = "button";
      kartica.setAttribute("data-id", sz.id);
      kartica.setAttribute("aria-label", t("samPredvajaj", { ime: ime }) + ", " + stSkladb(sz.stevilo));
      kartica.appendChild(kolaz(sz.slike || []));
      var podatki = el("span", "kat-podatki");
      var b = el("b", "", ubezi(ime)); b.title = ime; podatki.appendChild(b);
      podatki.appendChild(el("span", "kat-meta", "<span>" + ubezi(stSkladb(sz.stevilo)) + "</span>"));
      kartica.appendChild(podatki);
      kartica.addEventListener("click", function () { predvajajSamodejni(sz); });
      var shrani = el("button", "media-samodejni-shrani", svg("plus") + "<span>" + ubezi(t("samShrani")) + "</span>");
      shrani.type = "button"; shrani.setAttribute("data-id", sz.id + "|shrani");
      shrani.setAttribute("aria-label", t("samShrani") + ": " + ime);
      shrani.addEventListener("click", function () { shraniSamodejni(sz); });
      ovoj.appendChild(kartica); ovoj.appendChild(shrani);
      vrsta.appendChild(ovoj);
    });
    c.appendChild(vrsta);
    if (izbran) { var e = c.querySelector('[data-id="' + izbran.replace(/"/g, "") + '"]'); if (e) e.focus({ preventScroll: true }); }
  }
  function casMedija(sekunde) {
    sekunde = Math.max(0, Math.floor(Number(sekunde) || 0));
    return Math.floor(sekunde / 60) + ":" + String(sekunde % 60).padStart(2, "0");
  }
  // Spodnja vrstica »Predvaja se« (lastnik, 14. 10. 2026: kot v glasbenih aplikacijah) nadomesti desni stolpec in trak
  // kataloga. Vidna je samo, ko se kaj predvaja: domaci predvajalnik (premor steje, ustavljeno ne) ali skladba iz kataloga
  // oziroma s seznama (tudi v oknu YouTube). Drsnik polozaja samo, kadar predvajalnik pozna dolzino (ne tok v zivo, ne okno
  // YouTube) - sicer ga ni, namesto laznega. Glasnost je sistemska (ista kot v hitrih nastavitvah), samo ce jo sistem javi.
  function skladbaKataloga() { return typeof kat !== "undefined" && kat.aktivni && kat.aktivni.zvok ? kat.aktivni : null; }
  function uskladiTrak() {
    var p = S.mediaPredvajalnik, bar = $("mediaPlayerBar"); if (!bar) return false;
    var domaci = !!(p && p.naslov && p.stanje !== "ustavljeno");
    var vidno = domaci || !!skladbaKataloga() || spNaTraku();
    var prej = !bar.hidden;
    bar.hidden = !vidno;
    document.body.classList.toggle("ima-trak", vidno);
    if (!vidno) { zapriVrstoPlosco(false); zapriIzhode(false); }
    else if (!prej && most) naloziIzhode();     // ali zvok ze gre na drugo napravo (znak na gumbu »Predvajaj na …«)
    return vidno;
  }
  function prikaziMediaBar() { uskladiTrak(); }
  function znakTraku(item, p) {
    if (item) return "glasba";
    return p.vrsta === "radio" ? "radio" : /^(tv|video|filmi|serije)$/.test(p.vrsta || "") ? "video" : "glasba";
  }
  // Odprt seznam skladb: vrstica, ki igra, ima aria-current (poudarek v katalog.css) - na TV se vidi, kje v seznamu si.
  // Skladba iz kataloga po id-ju; Spotify (igra skrit Safeer DRM, id-ja ne vrne) po naslovu.
  function oznaciTrenutnoSkladbo() {
    var m = $("katMreza");
    if (!m || typeof kat === "undefined" || !m.classList.contains("kat-skladbe")) return;
    var akt = kat.aktivni, sp = !akt && spNaTraku() ? spTrenutna() : null;
    var naslov = sp ? String(sp.naslov || "").trim().toLowerCase() : "", najden = false;
    Array.prototype.forEach.call(m.querySelectorAll(".kat-kartica"), function (k) {
      var x = k._skladba, da = false;
      if (!najden && x) da = akt ? !!akt.id && akt.id === x.id : !!naslov && String(x.naslov || "").trim().toLowerCase() === naslov;
      if (da) { najden = true; k.setAttribute("aria-current", "true"); } else k.removeAttribute("aria-current");
    });
  }
  function narisiTrak() {
    oznaciTrenutnoSkladbo();
    if (!uskladiTrak()) return;
    if (spNaTraku()) { narisiSpTrak(); return; }
    var p = S.mediaPredvajalnik || {}, item = skladbaKataloga();
    var zivo = !item && (p.vrsta === "tv" || p.vrsta === "radio");
    var naslov, opis, igra, slika = "";
    if (item) {
      naslov = item.naslov || "";
      opis = !kat.igra && item.okno_youtube ? t("mediaPremor") : [item.izvajalec, kat.seznam && kat.seznam.ime, item.vir].filter(Boolean).join(" · ");
      igra = !!kat.igra;
      slika = item.slika || "";
    } else {
      naslov = p.naslov || "";
      // Napak predvajanja ne kazemo (lastnik 18. 10. 2026, sled je v sled.log); ostane samo pojasnilo za zasciten disk.
      opis = p.stanje === "napaka" && p.napaka === "dvd" ? t("mediaNapaka_dvd") : p.stanje === "premor" ? t("mediaPremor") :
        zivo ? t("mediaVZivo") : (p.izvor || t("mediaTaRacunalnik"));
      igra = p.stanje === "predvaja";
      if (opis === t("mediaTaRacunalnik")) opis = "";
    }
    // Zvok gre na drugo napravo ali zvocnik (»Predvajaj na …«): vrstica to pove, namesto »Ta racunalnik«.
    var izh = IZ && IZ.z && SafeerIzhod.aktivna(IZ.z);
    if (izh && izh.vrsta !== "racunalnik") opis = [opis, t("predvajaNa", { ime: izh.ime })].filter(Boolean).join(" · ");
    else if (!item && !opis) opis = t("mediaTaRacunalnik");
    $("mediaBarNaslov").textContent = naslov; $("mediaBarNaslov").title = naslov;
    $("mediaBarVrsta").textContent = opis;
    var znak = $("mediaBarZnak"), ikona = znakTraku(item, p);
    if (znak._slika !== slika || znak._ikona !== ikona) {
      znak._slika = slika; znak._ikona = ikona;
      znak.innerHTML = svg(ikona);
      if (slika) {
        var img = document.createElement("img"); img.alt = ""; nastaviSliko(img, slika);
        img.onerror = function () { img.remove(); };
        znak.appendChild(img);
      }
    }
    var premor = $("mediaKatPremor");
    premor.innerHTML = svg(igra ? "premor" : "predvajaj");
    premor.setAttribute("aria-pressed", igra ? "true" : "false");
    // Prejšnja/naslednja: vrsta strani (skladba iz kataloga) ali vrsta domačega predvajalnika.
    var dolzina = item ? (kat.vrsta || []).length : (p.skupaj || (p.vrstaSeznam || []).length || 0);
    $("mediaPrejsnja").disabled = item ? dolzina < 2 : !(p.indeks > 0);
    $("mediaNaslednja").disabled = item ? dolzina < 2 : !(p.indeks < dolzina - 1);
    var vrstaStrani = !!item && dolzina > 1;
    [["mediaPremesaj", "premesaj"], ["mediaPonovi", "ponovi"]].forEach(function (x) {
      var g = $(x[0]), vklop = vrstaNastavitev(x[1], "0") === "1";
      g.hidden = !vrstaStrani;
      g.classList.toggle("vklopljen", vklop);
      g.setAttribute("aria-pressed", vklop ? "true" : "false");
    });
    // Položaj: samo če ga predvajalnik res pozna.
    var polozaj = !(item && item.okno_youtube) && !!p.naslov && p.stanje !== "ustavljeno" && !zivo && Number(p.trajanje) > 0;
    $("mediaBarPolozaj").hidden = !polozaj;
    if (polozaj) {
      $("mediaBarCas").textContent = casMedija(p.pozicija);
      $("mediaBarTrajanje").textContent = casMedija(p.trajanje);
      var drsnik = $("mediaBarNapredek");
      if (!S.mediaDragging) drsnik.value = Math.round(1000 * Math.min(1, (Number(p.pozicija) || 0) / p.trajanje));
      drsnik.setAttribute("aria-valuetext", casMedija(p.pozicija) + " / " + casMedija(p.trajanje));
    }
    $("mediaBarVrstaGumb").hidden = dolzina < 2;
    if (dolzina < 2) zapriVrstoPlosco(false);
    narisiGlasnostTraku();
    narisiVrstoTraku(item, p);
  }
  function narisiGlasnostTraku() {
    var z = S.stanje && S.stanje.zvok, ovoj = $("mediaBarGlasnost"); if (!ovoj) return;
    ovoj.hidden = !z;
    if (!z) return;
    var u = $("mediaBarUtisaj");
    u.innerHTML = svg(z.utisan ? "utisan" : "zvok");
    u.setAttribute("aria-pressed", z.utisan ? "true" : "false");
    var d = $("mediaBarGlasnostDrsnik"), v = Math.max(0, Math.min(100, Number(z.glasnost) || 0));
    if (Date.now() - S.glasnostDotik > 1500) d.value = v;          // med vlecenjem ne skace nazaj
    d.setAttribute("aria-valuetext", (z.utisan ? t("utisaj") + " · " : "") + d.value + " %");
  }
  // Čakalna vrsta v plošči nad vrstico: vrsta strani (skladbe iz kataloga, s seznama) ali domačega predvajalnika.
  function narisiVrstoTraku(item, p) {
    var vrstaEl = $("mediaVrsta"); if (!vrstaEl) return;
    if (item) {
      // Vrstni red predvajanja (ob »Nakljucno« premesan, lastnik 18. 10. 2026): plosca kaze, kar bo res igralo, z
      // oznako nacina v glavi; skladba, ki igra, je poudarjena in plosca se pomakne do nje. Prenos v zivo ima »V zivo«.
      var imaVrsto = (kat.vrsta || []).length > 0, vnosi = imaVrsto ? (kat.vrstaVnosi || []) : [item];
      var mesto = Math.max(0, Math.min(vnosi.length - 1, kat.vrstaMesto || 0));
      var red = imaVrsto ? redVrste() : [0], poz = Math.max(0, red.indexOf(mesto)), nakljucno = imaVrsto && !!kat.vrstaRed;
      var od = Math.max(0, Math.min(poz - 100, red.length - 200)), prikaz = red.slice(od, od + 200);
      $("mediaCakalnaStevec").textContent = String(vnosi.length);
      $("mediaVrstaNacin").hidden = !nakljucno;
      var podpis = "kat|" + mesto + "|" + od + "|" + vnosi.length + "|" + (vnosi[0] && vnosi[0].id) + "|" + prikaz.join(",") + "|" + jezik;
      if (podpis === S.mediaQueueKey) return;
      S.mediaQueueKey = podpis;
      // Tipkovnica in daljinec: izbira ostane v plosci (na skladbi, ki igra), ko se plosca na novo narise.
      var fokusVPlosci = !!document.activeElement && vrstaEl.contains(document.activeElement);
      vrstaEl.innerHTML = "";
      vrstaEl.classList.toggle("nakljucno", nakljucno);
      prikaz.forEach(function (indeks, i) {
        var v = vnosi[indeks] || {}, zdaj = indeks === mesto, zivo = jeVZivo(v);
        var b = el("button", "media-vrsta-vnos" + (zdaj ? " izbran" : "") + (zivo ? " zivo" : ""),
          '<span class="media-vrsta-stevilka">' + (zdaj ? "♫" : String(od + i + 1)) + '</span><span><b>' + ubezi(v.naslov || "") +
          '</b><small>' + ubezi(zivo ? t("mediaVZivo") + (v.izvajalec ? " · " + v.izvajalec : "") : (v.izvajalec || v.vir || "")) + '</small></span>');
        b.type = "button";
        if (zdaj) b.setAttribute("aria-current", "true");
        b.addEventListener("click", function () {
          if (indeks === kat.vrstaMesto) return;
          zapomniMestoVrste();
          // Rocna izbira skladbe: uporabnik vodi vrsto (ob koncu seznama Safeer ne izbere sam naslednjega).
          kat.vrstaMesto = indeks; kat.izVrste = true; kat.vrstaSpremenjena = true; kat.vrstaSamodejno = false;
          narisiVrsto(); odpriKatalogVnos(v.id);
        });
        vrstaEl.appendChild(b);
      });
      var trenutna = fokusVPlosci && vrstaEl.querySelector(".media-vrsta-vnos.izbran");
      if (trenutna) { try { trenutna.focus({ preventScroll: true }); } catch (e) { trenutna.focus(); } }
      pomakniNaTrenutno();
      return;
    }
    var seznam = p.vrstaSeznam || [];
    $("mediaVrstaNacin").hidden = true;
    vrstaEl.classList.remove("nakljucno");
    $("mediaCakalnaStevec").textContent = String(p.skupaj || seznam.length);
    var kljuc = p.indeks + "|" + (p.zacetniIndeks || 0) + "|" + seznam.map(function (v) { return v.naslov + v.vrsta; }).join("|");
    if (kljuc === S.mediaQueueKey) return;
    S.mediaQueueKey = kljuc;
    vrstaEl.innerHTML = "";
    if (!seznam.length) vrstaEl.appendChild(el("p", "media-vrsta-prazna", ubezi(t("mediaVrstaPrazna"))));
    seznam.forEach(function (v, i) {
      var stevilka = i + (p.zacetniIndeks || 0);
      var b = el("button", "media-vrsta-vnos" + (stevilka === p.indeks ? " izbran" : ""),
        '<span class="media-vrsta-stevilka">' + (stevilka === p.indeks ? "♫" : String(stevilka + 1)) + '</span><span><b>' + ubezi(v.naslov) +
        '</b><small>' + ubezi(v.vrsta === "tv" || v.vrsta === "radio" ? t("mediaVZivo") : (v.izvor || t("mediaTaRacunalnik"))) + '</small></span>');
      b.type = "button";
      if (stevilka === p.indeks) b.setAttribute("aria-current", "true");
      b.addEventListener("click", function () { klic("predvajalnikUkaz", ["predvajaj", stevilka]).catch(function () {}); });
      vrstaEl.appendChild(b);
    });
  }
  // Plosca vrste se pomakne do skladbe, ki igra (na sredino, brez animacije): ob odprtju in ob vsaki naslednji skladbi.
  function pomakniNaTrenutno() {
    var plosca = $("mediaVrstaPlosca"), izbran = plosca && plosca.querySelector(".media-vrsta-vnos.izbran");
    if (!plosca || plosca.hidden || !izbran) return;
    var p = plosca.getBoundingClientRect(), r = izbran.getBoundingClientRect(), glava = plosca.querySelector(".media-cakalna-glava");
    var vrh = p.top + (glava ? glava.getBoundingClientRect().height : 0);      // pod lepljivo glavo
    plosca.scrollTop += (r.top + r.height / 2) - (vrh + (p.bottom - vrh) / 2);
  }
  function odpriVrstoPlosco() {
    var plosca = $("mediaVrstaPlosca"); if (!plosca) return;
    plosca.hidden = false;
    $("mediaBarVrstaGumb").setAttribute("aria-expanded", "true");
    pomakniNaTrenutno();
    var izbran = plosca.querySelector(".media-vrsta-vnos.izbran") || plosca.querySelector("button");
    if (izbran) { try { izbran.focus({ preventScroll: true }); } catch (e) { izbran.focus(); } }
  }
  function zapriVrstoPlosco(nazajNaGumb) {
    var plosca = $("mediaVrstaPlosca"); if (!plosca || plosca.hidden) return false;
    plosca.hidden = true;
    $("mediaBarVrstaGumb").setAttribute("aria-expanded", "false");
    if (nazajNaGumb) $("mediaBarVrstaGumb").focus();
    return true;
  }
  // ---- »Predvajaj na …« (lastnik, 14. 10. 2026): kam gre zvok - ta racunalnik, naprava v Safeer Linku ali zvocnik v
  // omrezju. Logika in privolitev za zaseden zvocnik sta skupni s hitrimi nastavitvami zvoka (izhod.js).
  var IZ = { z: null, st: SafeerIzhod.novoStanje(), cas: 0 };
  function izhodGost() { return izhodGostitelj(naloziIzhode, narisiIzhode); }
  function naloziIzhode() {
    return klic("zvok").then(function (z) { IZ.z = z || {}; narisiIzhode(); narisiTrak(); }, function () { narisiIzhode(); });
  }
  function ikonaIzhoda(m) {
    return m.vrsta === "racunalnik" ? "namizje" : m.vrsta === "zvocnik" ? "zvok" : (m.platforma === "tablet" || m.platforma === "phone") ? "naprave" : "zaslon";
  }
  function narisiIzhode() {
    var g = $("mediaBarIzhod"), c = $("mediaIzhodi"); if (!g || !c) return;
    var z = IZ.z, st = IZ.st, a = z && SafeerIzhod.aktivna(z), drugje = !!(a && a.vrsta !== "racunalnik");
    g.classList.toggle("vklopljen", drugje);
    g.title = drugje ? t("predvajaNa", { ime: a.ime }) : t("predvajajNa");
    g.setAttribute("aria-label", g.title);
    if ($("mediaIzhodPlosca").hidden) return;
    if (document.activeElement && document.activeElement.id === "mediaIzhodZamik") return;   // med premikanjem drsnika ne risemo
    var fokus = document.activeElement && c.contains(document.activeElement) ? document.activeElement.getAttribute("data-id") : null;
    c.innerHTML = "";
    $("mediaIzhodIsci").disabled = !!st.isce;
    if (!z) { $("mediaIzhodStanje").textContent = t("izhodNalagam"); return; }
    SafeerIzhod.moznosti(z).forEach(function (m) {
      var caka = !!st.caka && st.caka === m.id && !m.aktiven, potrdi = st.potrdi[m.id];
      var ime = m.vrsta === "racunalnik" ? t("taRacunalnik") : m.ime;
      var pod = m.vrsta === "racunalnik" ? m.pod : m.vrsta === "zvocnik" ? t("zvokZvocnik") + (m.model ? " · " + m.model : "") : "Safeer Link";
      if (caka) pod = t("zvokPovezujem");
      else if (m.aktiven && m.stanje) pod = t(m.stanje === "tece" ? "zvokPredvaja" : "zvokPovezujem") + " · " + pod;
      else if (potrdi) pod = t("zvokZvocnikPreklopi", { vir: potrdi });
      var b = el("button", "media-izhod" + (m.aktiven ? " izbran" : ""), svg(ikonaIzhoda(m)) + "<span><b>" + ubezi(ime) + "</b>" +
        (pod ? "<small>" + ubezi(pod) + "</small>" : "") + "</span>" + (m.aktiven ? svg("kljukica") : ""));
      b.type = "button";
      b.setAttribute("data-id", m.vrsta + ":" + m.id);
      b.setAttribute("aria-pressed", m.aktiven ? "true" : "false");
      b.addEventListener("click", function () { SafeerIzhod.izberi(st, m, z, izhodGost()); });
      c.appendChild(b);
      if (m.vrsta === "zvocnik" && m.aktiven) c.appendChild(zamikZvocnika(m));
    });
    $("mediaIzhodStanje").textContent = st.isce ? t("zvokIscem") : (SafeerIzhod.imaDruge(z) ? "" : t("zvokNiIzhodov"));
    if (fokus) { var f = c.querySelector('[data-id="' + fokus.replace(/"/g, "") + '"]'); if (f) f.focus({ preventScroll: true }); }
  }
  // Zamik zvoka na aktivnem zvocniku: slika videa pocaka zvocnik (ocena samodejno, tu fina nastavitev po 50 ms).
  function zamikZvocnika(m) {
    var v = el("div", "media-izhod-zamik", ""), ms = m.zakasnitev || 0;
    var napis = el("label", "", ""), d = document.createElement("input");
    napis.htmlFor = "mediaIzhodZamik";
    function besedilo(x) { napis.textContent = t("zvokZamik") + ": " + x + " ms"; }
    besedilo(ms);
    d.type = "range"; d.id = "mediaIzhodZamik"; d.min = "0"; d.max = "8000"; d.step = "50"; d.value = String(ms);
    d.setAttribute("data-id", "zamik");
    d.addEventListener("input", function () { besedilo(d.value); });
    d.addEventListener("change", function () { SafeerIzhod.zakasnitev(m, +d.value, izhodGost()); });
    v.appendChild(napis); v.appendChild(d);
    v.appendChild(el("small", "", ubezi(t("zvokZamikSplet"))));
    return v;
  }
  function odpriIzhode() {
    zapriVrstoPlosco(false);
    $("mediaIzhodPlosca").hidden = false;
    $("mediaBarIzhod").setAttribute("aria-expanded", "true");
    narisiIzhode();
    naloziIzhode().then(function () {
      var c = $("mediaIzhodi"), prvi = c.querySelector(".media-izhod.izbran") || c.querySelector("button");
      if (prvi && !c.contains(document.activeElement)) prvi.focus({ preventScroll: true });
      // Zvocnikov se ni na seznamu: poiscemo jih takoj (iskanje traja nekaj sekund, stanje se kaze spodaj).
      if (IZ.z && !((IZ.z.link || {}).zvocniki || []).length && !IZ.st.isce) SafeerIzhod.isci(IZ.st, izhodGost());
    });
    clearInterval(IZ.cas);
    IZ.cas = setInterval(function () {
      if ($("mediaIzhodPlosca").hidden) { clearInterval(IZ.cas); return; }
      naloziIzhode();
    }, 3000);
  }
  function zapriIzhode(nazajNaGumb) {
    var plosca = $("mediaIzhodPlosca"); if (!plosca || plosca.hidden) return false;
    plosca.hidden = true;
    clearInterval(IZ.cas);
    $("mediaBarIzhod").setAttribute("aria-expanded", "false");
    if (nazajNaGumb) $("mediaBarIzhod").focus();
    return true;
  }
  function poveziIzhode() {
    $("mediaBarIzhod").addEventListener("click", function () { if ($("mediaIzhodPlosca").hidden) odpriIzhode(); else zapriIzhode(true); });
    $("mediaIzhodIsci").addEventListener("click", function () { if (!IZ.st.isce) SafeerIzhod.isci(IZ.st, izhodGost()); });
    document.addEventListener("click", function (e) {
      if (!e.target.closest("#mediaIzhodPlosca") && !e.target.closest("#mediaBarIzhod")) zapriIzhode(false);
    });
    // Puscice gor/dol, Home in End med izbirami; Escape (tipka Nazaj) zapre samo plosco.
    $("mediaIzhodPlosca").addEventListener("keydown", function (e) {
      var vsi = Array.prototype.slice.call(this.querySelectorAll("button:not(:disabled)")), i = vsi.indexOf(document.activeElement);
      var j = e.key === "ArrowDown" ? i + 1 : e.key === "ArrowUp" ? i - 1 : e.key === "Home" ? 0 : e.key === "End" ? vsi.length - 1 : null;
      if (j === null || !vsi.length) return;
      e.preventDefault();
      vsi[Math.max(0, Math.min(vsi.length - 1, j))].focus();
    });
    window.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && zapriIzhode(true)) { e.preventDefault(); e.stopImmediatePropagation(); }
    }, true);
  }
  function poveziTrak() {
    poveziIzhode();
    $("mediaBarVrstaGumb").addEventListener("click", function () { zapriIzhode(false); if ($("mediaVrstaPlosca").hidden) odpriVrstoPlosco(); else zapriVrstoPlosco(true); });
    document.addEventListener("click", function (e) {
      // Klik na vrstico vrste plosco na novo narise (vrstica ni vec v dokumentu): plosca ostane odprta, poudarjena je
      // nova skladba (pregled 18. 10. 2026 - prej se je plosca ob vsaki izbiri zaprla).
      if (!document.contains(e.target)) return;
      if (!e.target.closest("#mediaVrstaPlosca") && !e.target.closest("#mediaBarVrstaGumb")) zapriVrstoPlosco(false);
    });
    // Escape (tipka Nazaj na daljincu) zapre samo ploščo vrste, ne celega Medijskega centra.
    window.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && zapriVrstoPlosco(true)) { e.preventDefault(); e.stopImmediatePropagation(); }
    }, true);
    var zamik = 0;
    $("mediaBarGlasnostDrsnik").addEventListener("input", function () {
      var v = parseInt(this.value, 10) || 0;
      S.glasnostDotik = Date.now();
      this.setAttribute("aria-valuetext", v + " %");
      clearTimeout(zamik);
      zamik = setTimeout(function () {
        klic("glasnost", [v]).then(function () {
          if (S.stanje && S.stanje.zvok) { S.stanje.zvok.glasnost = v; S.stanje.zvok.utisan = false; narisiStanje(S.stanje); }
        }).catch(function () {});
      }, 120);
    });
    $("mediaBarUtisaj").addEventListener("click", function () {
      klic("utisaj").then(function () { setTimeout(osveziStanje, 200); }).catch(function () {});
    });
  }
  function osveziPredvajalnik(p) {
    if (!p) return;
    // Spotify ima v Medijskem centru svoj trak (kat.sp): stanje gostitelja ga javi samo za pripomocke na namizju in
    // MPRIS (18. 10. 2026) - tu ni domace predvajanje (sicer bi ga spOdDomacega ustavil).
    if (p.spotify) p = { stanje: "ustavljeno", naslov: "", vrsta: "", indeks: -1, zacetniIndeks: 0, skupaj: 0,
                         vrstaSeznam: [], pozicija: 0, trajanje: 0, napaka: "" };
    S.mediaPredvajalnik = p;
    spOdDomacega(p);
    narisiTrak();
  }
  function odpriDodaj() {
    $("dodajIme").value = "";
    $("dodajNaslov").value = "";
    $("dodajMedijskaVrstaPolje").hidden = S.razdelek !== "media";
    $("dodajMedijskaVrsta").value = ["video", "glasba", "filmi", "serije", "tv", "radio"].indexOf(S.mediaFilter) >= 0 ? S.mediaFilter : "video";
    $("slojDodaj").classList.add("viden");
    setTimeout(function () { $("dodajIme").focus(); }, 30);
  }

  // ------------------------------------------------------------------ splet
  var brezPeskovnikaOb = 0;   // kdaj je gostitelj nazadnje pojasnil, da vsebine brez peskovnika ne odpre
  function pravkarBrezPeskovnika() { return Date.now() - brezPeskovnikaOb < 1000; }
  /* Odpre naslov v vgrajenem brskalniku; obljuba pove, ali se je odprl. Kadar se ne, uporabnik to izve: do Safeer OS
     0.4.65 je klik ostal brez odziva, ce je gostitelj naslov zavrnil (odgovor false ni napaka obljube).
     novZavihek: stran, ki jo ima uporabnik odprto v brskalniku, ostane (povezava iz sporocila). */
  function odpriVSpletu(naslov, novZavihek) {
    if (EN_RAZDELEK) {
      // Safeer Player in okna razdelkov so samostojna okna: spletno stran (ponudnik, »Kje gledati«) odpre privzeti brskalnik, kot na
      // delovni povrsini - ne glavno okno Safeer OS.
      return klic("odpriVBrskalniku", [naslov]).then(function (ok) {
        if (ok === false) obvesti(t("niUspelo"));
        return ok !== false;
      }, function () { obvesti(t("niUspelo")); return false; });
    }
    return klic("splet", novZavihek ? [naslov, true] : [naslov]).then(function (ok) {
      // Pojasnilo o peskovniku je gostitelj pravkar poslal sam (dogodek spletBrezPeskovnika): splosno ga ne prekrije.
      if (ok === false && !pravkarBrezPeskovnika()) obvesti(t("niUspelo"));
      return ok !== false;
    }, function () { obvesti(t("niUspelo")); return false; });
  }
  function odpriSplet(naslov, ime) { odpriVSpletu(naslov); }
  function narisiSpletnoZacetno() {
    var cilj = $("spletneAplikacije");
    if (!cilj) return;
    cilj.innerHTML = "";
    spletne().forEach(function (a) {
      var b = el("button", "spletna-bliznjica");
      b.appendChild(el("span", "spletna-bliznjica-znak", ubezi((a.ime || "S").charAt(0).toUpperCase())));
      b.appendChild(el("span", "spletna-bliznjica-podatki", "<b>" + ubezi(a.ime) + "</b><small>" + ubezi(a.url) + "</small>"));
      b.appendChild(el("span", "spletna-bliznjica-puscica", "›"));
      b.addEventListener("click", function () { odpriSplet(a.url, a.ime); });
      cilj.appendChild(b);
    });
  }

  // ------------------------------------------------------------------ zapiski
  var Z = { aktivni: null, casovnik: 0, pogled: false, iskano: "", omembe: [], izbranaOmemba: 0, izbrisPotrdi: 0 };
  var OMEMBA_RE = /\[@([^\]]{1,160})\]\(([^)\s]{1,2048})\)/g;

  function naloziZapiske(potem) {
    klic("zapiskiSeznam", [Z.iskano]).then(function (seznam) {
      var mesto = $("zapiskiVrstice");
      mesto.innerHTML = "";
      (seznam || []).forEach(function (z) {
        var b = el("button", "zapisek-vrstica" + (Z.aktivni && Z.aktivni.id === z.id ? " izbran" : ""));
        b.innerHTML = "<b>" + (z.pripet ? "📌 " : "") + ubezi(z.naslov) + "</b><small>" + ubezi(z.odlomek || t("zapisekPrazen")) + "</small>";
        b.addEventListener("click", function () { odpriZapisek(z.id); });
        mesto.appendChild(b);
      });
      if (!(seznam || []).length) mesto.appendChild(el("div", "prazno", ubezi(Z.iskano ? t("niZadetkov") : t("zapiskiPrazni"))));
      if (potem) potem(seznam || []);
    });
  }
  function odpriZapisek(id) {
    klic("zapisekDobi", [id]).then(function (z) {
      if (!z) return;
      Z.aktivni = z;
      $("zapisekUrejevalnik").hidden = false;
      $("zapisekNaslov").value = z.naslov || "";
      $("zapisekBesedilo").value = z.besedilo || "";
      $("zapisekPripni").textContent = t(z.pripet ? "zapisekOdpni" : "zapisekPripni");
      $("zapisekStanje").textContent = "";
      narisiViriZapiska(z);
      if (Z.pogled) narisiPogledZapiska();
      naloziZapiske();
    });
  }
  function cipOmembe(ime, cilj) {
    var c = el("button", "zapisek-cip"); c.type = "button";
    var ikona = /^https?:/.test(cilj) ? "🌐" : cilj.indexOf("safeer:datoteka:") === 0 ? "📄" :
      cilj.indexOf("safeer:zapisek:") === 0 ? "📝" : cilj.indexOf("safeer:program:") === 0 ? "▶" : "@";
    c.textContent = ikona + " " + ime; c.title = cilj;
    c.addEventListener("click", function () { odpriCiljZapiska(cilj); });
    return c;
  }
  function narisiViriZapiska(z) {
    var viri = $("zapisekViri"), povratne = $("zapisekPovratne");
    viri.innerHTML = ""; povratne.innerHTML = "";
    (z.omembe || []).forEach(function (o) { viri.appendChild(cipOmembe(o.ime, o.cilj)); });
    (z.povratne || []).forEach(function (p) { povratne.appendChild(cipOmembe(p.naslov, "safeer:zapisek:" + p.id)); });
    if (!viri.childNodes.length) viri.appendChild(el("span", "namig", ubezi(t("zapisekBrezVirov"))));
    if (!povratne.childNodes.length) povratne.appendChild(el("span", "namig", ubezi(t("zapisekBrezPovratnih"))));
  }
  function odpriCiljZapiska(cilj) {
    if (/^https?:\/\//.test(cilj)) { odpriSplet(cilj); return; }
    var deli = cilj.split(":"), vrsta = deli[1], vrednost = deli.slice(2).join(":");
    if (vrsta === "datoteka") {
      try { vrednost = decodeURIComponent(vrednost); } catch (e) {}
      klic("odpriDatoteko", [vrednost]);
    }
    else if (vrsta === "zapisek") odpriZapisek(vrednost);
    else if (vrsta === "program") {
      var p = S.programi.find(function (x) { return x.id === vrednost; });
      if (p) zazeni(p); else obvesti(t("zapisekNiPrograma"));
    }
  }
  function shraniZapisekKmalu() {
    clearTimeout(Z.casovnik); $("zapisekStanje").textContent = "…";
    Z.casovnik = setTimeout(shraniZapisek, 600);
  }
  function shraniZapisek() {
    if (!Z.aktivni) return;
    var naslov = $("zapisekNaslov").value, besedilo = $("zapisekBesedilo").value;
    klic("zapisekShrani", [Z.aktivni.id, naslov, besedilo, null]).then(function () {
      Z.aktivni.naslov = naslov; Z.aktivni.besedilo = besedilo;
      $("zapisekStanje").textContent = t("zapisekShranjeno");
      klic("zapisekDobi", [Z.aktivni.id]).then(function (z) { if (z) narisiViriZapiska(z); });
      naloziZapiske();
    }, function () { $("zapisekStanje").textContent = t("zapisekNiShranjeno"); });
  }
  function narisiPogledZapiska() {
    var mesto = $("zapisekPrikaz"); mesto.innerHTML = "";
    $("zapisekBesedilo").value.split("\n").forEach(function (vrstica) {
      var odstavek = el(vrstica.indexOf("> ") === 0 ? "blockquote" : "div"), besedilo = vrstica.replace(/^> /, ""), zadnji = 0, m;
      OMEMBA_RE.lastIndex = 0;
      while ((m = OMEMBA_RE.exec(besedilo))) {
        odstavek.appendChild(document.createTextNode(besedilo.slice(zadnji, m.index)));
        odstavek.appendChild(cipOmembe(m[1], m[2])); zadnji = m.index + m[0].length;
      }
      odstavek.appendChild(document.createTextNode(besedilo.slice(zadnji))); mesto.appendChild(odstavek);
    });
  }
  function iskanjeOmembe() {
    var ta = $("zapisekBesedilo"), pred = ta.value.slice(0, ta.selectionStart), m = /(^|\s)@([^@\n\]\[()]{0,40})$/.exec(pred);
    return m ? { niz: m[2], zacetek: ta.selectionStart - m[2].length - 1 } : null;
  }
  function zapriOmembe() { $("zapisekOmembeOkno").hidden = true; Z.omembe = []; }
  function ponudiOmembe() {
    var q = iskanjeOmembe(); if (!q) { zapriOmembe(); return; }
    var niz = q.niz.trim().toLocaleLowerCase(), predlogi = [];
    function ujema(ime) { return !niz || String(ime || "").toLocaleLowerCase().indexOf(niz) >= 0; }
    S.programi.filter(function (p) { return niz.length >= 2 && ujema(p.ime); }).slice(0, 5)
      .forEach(function (p) { predlogi.push({ ime: p.ime, cilj: "safeer:program:" + p.id, vrsta: t("programi") }); });
    var zahteva = (Z.omembeZahteva = (Z.omembeZahteva || 0) + 1);
    Promise.all([
      klic("zapiskiSeznam", [niz]).catch(function () { return []; }),
      niz.length >= 2 ? klic("isciDatoteke", [niz]).catch(function () { return []; }) : Promise.resolve([])
    ]).then(function (rezultati) {
      rezultati[0].filter(function (z) { return !Z.aktivni || z.id !== Z.aktivni.id; }).slice(0, 5)
        .forEach(function (z) { predlogi.push({ ime: z.naslov, cilj: "safeer:zapisek:" + z.id, vrsta: t("zapiski") }); });
      rezultati[1].filter(function (d) { return !d.mapa; }).slice(0, 6)
        .forEach(function (d) { predlogi.push({ ime: d.ime, cilj: "safeer:datoteka:" + d.pot, vrsta: t("datoteke") }); });
      if (zahteva !== Z.omembeZahteva) return;
      var videni = {}; Z.omembe = predlogi.filter(function (p) { if (videni[p.cilj]) return false; videni[p.cilj] = true; return true; }).slice(0, 12);
      Z.izbranaOmemba = 0; narisiOmembe();
    });
  }
  function narisiOmembe() {
    var okno = $("zapisekOmembeOkno"); okno.innerHTML = "";
    Z.omembe.forEach(function (p, i) {
      var b = el("button", i === Z.izbranaOmemba ? "izbran" : ""); b.type = "button";
      b.appendChild(document.createTextNode(p.ime)); b.appendChild(el("small", "", ubezi(p.vrsta)));
      b.addEventListener("mousedown", function (e) { e.preventDefault(); vstaviOmembo(p); }); okno.appendChild(b);
    });
    okno.hidden = !Z.omembe.length;
  }
  function vstaviOmembo(p) {
    var q = iskanjeOmembe(), ta = $("zapisekBesedilo"); if (!q) return;
    var ime = String(p.ime || "").replace(/[\[\]]/g, "").slice(0, 120);
    var vstavek = "[@" + ime + "](" + String(p.cilj).replace(/\s/g, "%20").replace(/\)/g, "%29") + ") ";
    ta.value = ta.value.slice(0, q.zacetek) + vstavek + ta.value.slice(ta.selectionStart);
    var poz = q.zacetek + vstavek.length; ta.setSelectionRange(poz, poz); ta.focus(); zapriOmembe(); shraniZapisekKmalu();
  }

  // ------------------------------------------------------------------ odprta okna
  function osveziOkna() {
    klic("odprtaOkna").then(narisiOkna, function () {});
  }
  function narisiOkna(okna) {
    {
      okna = okna || [];
      $("blokOkna").hidden = okna.length === 0;
      var vrsta = $("okna");
      vrsta.innerHTML = "";
      okna.slice(0, 12).forEach(function (o) {
        var b = el("button", "okno");
        b.appendChild(slikaAliCrka(o.ikona, o.program || o.ime));
        b.appendChild(el("div", "", "<b>" + ubezi(o.program || o.ime) + "</b><span>" + ubezi(o.ime) + "</span>"));
        var z = el("span", "zapri", svg("x"));
        z.addEventListener("click", function (e) {
          e.stopPropagation();
          klic("zapriOkno", [o.id]).then(function () { setTimeout(osveziOkna, 500); });
        });
        b.appendChild(z);
        b.addEventListener("click", function () { klic("aktivirajOkno", [o.id]); });
        vrsta.appendChild(b);
      });
    }
  }

  // ------------------------------------------------------------------ datoteke
  function velikost(b) {
    if (b < 1024) return b + " B";
    var e = ["kB", "MB", "GB", "TB"], i = -1;
    do { b /= 1024; i++; } while (b >= 1024 && i < e.length - 1);
    return (b < 10 ? b.toFixed(1) : Math.round(b)) + " " + e[i];
  }
  function datum(s) {
    if (!s) return "";
    return new Date(s * 1000).toLocaleDateString(LOKALE[jezik] || "en-GB", { day: "numeric", month: "short", year: "numeric" });
  }
  var IKONA_VRSTE = { mapa: "mapa", slika: "slika", video: "video", zvok: "glasba", dokument: "dokument",
                      arhiv: "arhiv", program: "program", drugo: "datoteka" };
  function podatkiDatoteke(d) { return (d.mapa ? "" : velikost(d.velikost || 0) + " · ") + datum(d.spremenjeno || d.cas); }
  function vrsticaDatoteke(d, zPotjo, nedavna) {
    var b = el("button", "vrstica");
    b.setAttribute("data-pot", d.pot || "");
    b.innerHTML = svg(IKONA_VRSTE[d.vrsta] || "datoteka") + '<span class="ime">' + ubezi(d.ime) + "</span>" +
      (zPotjo ? '<span class="pod pot">' + ubezi(skrajsajPot(d.pot.replace(/\/[^\/]*$/, "") || "/")) + "</span>" : "") +
      '<span class="pod podatki">' + ubezi(podatkiDatoteke(d)) + "</span>";
    b.addEventListener("click", function () {
      if (d.mapa) { pojdi("datoteke"); odpriMapo(d.pot); }
      else { obvesti(t("odpiram", { ime: d.ime })); klic("odpriDatoteko", [d.pot]); }
    });
    if (nedavna) {
      // Iz seznama nedavnih (datoteka ostane): X na vsaki vrstici.
      var x = el("span", "pozabi", svg("x"));
      x.title = t("pozabiNedavno");
      x.addEventListener("click", function (e) {
        e.stopPropagation();
        klic("nedavnePozabi", [d.pot]).then(function () { b.remove(); osveziNedavne(); });
      });
      b.appendChild(x);
    }
    return b;
  }
  function osveziNedavne() {
    narisiNedavneDomov();
    if (S.razdelek === "datoteke" && !S.pot) odpriNedavne();
  }
  // Safeer OS spremlja, kar razdelek Datoteke kaze (mapo ali nedavne; na domacem zaslonu nedavne): sprememba drugega
  // programa (prenos, Nemo, datoteka z druge naprave) pride kot dogodek »datoteke« in seznam preberemo znova.
  function spremljajDatoteke() {
    var kaj = S.razdelek === "datoteke" ? (S.datPogled === "mapa" ? S.pot : S.datPogled === "nedavne" ? "@nedavno" : "")
      : S.razdelek === "domov" ? "@nedavno" : "";
    if (kaj === S.spremljano) return;
    S.spremljano = kaj;
    klic("spremljajMapo", [kaj]).catch(function () {});
  }
  function datotekeSpremenjene(pogled) {
    if (pogled === "@nedavno") {
      if (S.razdelek === "domov") narisiNedavneDomov();
      else if (S.razdelek === "datoteke" && S.datPogled === "nedavne") odpriNedavne(true);
    } else if (S.razdelek === "datoteke" && S.datPogled === "mapa" && pogled === S.pot) odpriMapo(S.pot, true);
  }
  function odtisDatotek(seznam) {
    return (seznam || []).map(function (e) {
      return (e.pot || "") + "|" + (e.velikost || 0) + "|" + Math.round(e.spremenjeno || e.cas || 0);
    }).join("\n");
  }
  // Ista mapa z istimi datotekami, spremenile so se le velikosti ali casi (datoteka se prenasa): popravimo samo
  // besedilo teh vrstic. Stari vnosi dobijo nove vrednosti (iz njih se risejo tudi vrstice, ki se niso narisane).
  function posodobiVrstice(stari, novi) {
    if (!stari || stari.length !== novi.length) return false;
    for (var i = 0; i < novi.length; i++) if (stari[i].pot !== novi[i].pot || stari[i].mapa !== novi[i].mapa) return false;
    var spremenjeni = {};
    for (var j = 0; j < novi.length; j++) {
      if (stari[j].velikost !== novi[j].velikost || stari[j].spremenjeno !== novi[j].spremenjeno) {
        stari[j].velikost = novi[j].velikost; stari[j].spremenjeno = novi[j].spremenjeno;
        spremenjeni[novi[j].pot] = stari[j];
      }
    }
    Array.prototype.forEach.call($("vsebinaMape").querySelectorAll("button.vrstica"), function (v) {
      var d = spremenjeni[v.getAttribute("data-pot")], polje = d && v.querySelector(".podatki");
      if (polje) polje.textContent = podatkiDatoteke(d);
    });
    return true;
  }
  // Po tihi osvezitvi: iste vrstice ostanejo na istem mestu zaslona (tudi ce se je nad njimi kaj pojavilo ali je izginilo),
  // in vrstica, ki je imela fokus, ga dobi nazaj.
  function poTihiOsvezitvi(prej) {
    var drsnik = $("vsebina"), vrstice = $("vsebinaMape").querySelectorAll("button.vrstica"), sidro = null, vFokusu = null;
    for (var i = 0; i < vrstice.length && (!sidro || !vFokusu); i++) {
      var pot = vrstice[i].getAttribute("data-pot");
      if (prej.sidro && pot === prej.sidro) sidro = vrstice[i];
      if (prej.pot && pot === prej.pot) vFokusu = vrstice[i];
    }
    if (drsnik) {
      drsnik.scrollTop = prej.odmik;
      if (sidro) drsnik.scrollTop += sidro.getBoundingClientRect().top - prej.sidroVrh;
    }
    if (vFokusu) { try { vFokusu.focus({ preventScroll: true }); } catch (x) {} }
  }
  function stanjePredOsvezitvijo() {
    var drsnik = $("vsebina"), vrh = drsnik ? drsnik.getBoundingClientRect().top : 0;
    var v = document.activeElement && document.activeElement.closest ? document.activeElement.closest("#vsebinaMape button.vrstica") : null;
    var stanje = { odmik: drsnik ? drsnik.scrollTop : 0, pot: v ? v.getAttribute("data-pot") : "", sidro: "", sidroVrh: 0 };
    // Sidro: prva vrstica, ki je (vsaj delno) vidna.
    var vrstice = $("vsebinaMape").querySelectorAll("button.vrstica");
    for (var i = 0; i < vrstice.length; i++) {
      var r = vrstice[i].getBoundingClientRect();
      if (r.bottom > vrh) { stanje.sidro = vrstice[i].getAttribute("data-pot") || ""; stanje.sidroVrh = r.top; break; }
    }
    return stanje;
  }
  function pocistiNedavne() {
    klic("nedavnePocisti").then(function () { obvesti(t("seznamPocisten")); osveziNedavne(); });
  }
  function dom() { return (S.zacetek && S.zacetek.mape && S.zacetek.mape[0] && S.zacetek.mape[0].pot) || ""; }
  function skrajsajPot(p) { var d = dom(); return d && p.indexOf(d) === 0 ? "~" + p.slice(d.length) : p; }
  function narisiMape() {
    var seznam = $("mapeSeznam");
    seznam.innerHTML = "";
    var ned = el("button", S.pot === "" ? "izbran" : "", svg("ura") + "<span>" + ubezi(t("nedavno")) + "</span>");
    ned.addEventListener("click", odpriNedavne);
    seznam.appendChild(ned);
    var IK_MAPE = { HOME: "domov", DESKTOP: "namizje", DOCUMENTS: "dokument", DOWNLOAD: "arhiv", PICTURES: "slika",
                    MUSIC: "glasba", VIDEOS: "video" };
    ((S.zacetek && S.zacetek.mape) || []).forEach(function (m) {
      var b = el("button", S.pot === m.pot ? "izbran" : "", svg(IK_MAPE[m.vrsta] || "mapa") + "<span>" + ubezi(m.ime) + "</span>");
      b.addEventListener("click", function () { odpriMapo(m.pot); });
      seznam.appendChild(b);
    });
    // Diski (lastnik, 24. 10. 2026: »kje in na katerem disku imam koliko prostora«): vsak z zasedenostjo, tudi
    // nepriklopljeni z gumbom Priklopi (core/sistem_podatki.py). Nosilci, ki so ze med diski, se ne ponovijo.
    var naDiskih = {};
    if ((S.diski || []).length) {
      seznam.appendChild(el("h3", "mape-naslov", ubezi(t("diski"))));
      S.diski.forEach(function (d) { if (d.pot) naDiskih[d.pot] = 1; seznam.appendChild(vrsticaDiska(d)); });
    }
    // Nosilci (USB kljuci, zunanji in drugi diski, omrezna mesta) so mape kot vse druge.
    (S.nosilci || []).forEach(function (n) {
      if (naDiskih[n.pot]) return;
      var g = el("button", S.pot === n.pot ? "izbran" : "", svg("arhiv") + "<span>" + ubezi(n.ime) + "</span>");
      g.addEventListener("click", function () { odpriMapo(n.pot); });
      seznam.appendChild(g);
    });
    if (!S.diskiNalagam && (!S.diskiCas || Date.now() - S.diskiCas > 30000)) {
      S.diskiNalagam = true;
      klic("diski").then(function (d) {
        var prej = JSON.stringify(S.diski || []);
        S.diski = Array.isArray(d) ? d.filter(function (x) { return x && x.naprava; }) : [];
        S.diskiNalagam = false; S.diskiCas = Date.now();
        opozoriMaloProstora(S.diski);
        if (JSON.stringify(S.diski) !== prej) narisiMape();
      }, function () { S.diskiNalagam = false; S.diskiCas = Date.now(); });
    }
    if (!S.nosilciNalagam) {
      S.nosilciNalagam = true;
      klic("nosilci").then(function (n) {
        var prej = JSON.stringify((S.nosilci || []).map(function (x) { return x.pot; }));
        S.nosilci = Array.isArray(n) ? n.filter(function (x) { return x && x.pot; }) : [];
        S.nosilciNalagam = false;
        if (JSON.stringify(S.nosilci.map(function (x) { return x.pot; })) !== prej) narisiMape();
      }, function () { S.nosilciNalagam = false; });
    }
  }
  function imeDiska(d) {
    // Windows: crka pogona kot v Raziskovalcu (»Sistemski disk (C:)«, »Podatki (D:)«); Linux (/dev/...) nespremenjen.
    var crka = /^[A-Za-z]:\\?$/.test(d.naprava || "") ? d.naprava.slice(0, 2).toUpperCase() : "";
    if (d.sistem) return t("diskSistem") + (crka ? " (" + crka + ")" : "");
    if (crka) return d.oznaka ? d.oznaka + " (" + crka + ")" : crka;
    return d.oznaka || (d.model ? d.model + " · " + velikost(d.velikost) : (d.naprava || "").replace(/^\/dev\//, ""));
  }
  function vrsticaDiska(d) {
    var deluje = d.priklopljen && d.velikost > 0, delez = deluje ? Math.max(0, Math.min(1, 1 - (d.prosto || 0) / d.velikost)) : 0;
    var pod = deluje ? t("diskProsto", { prosto: velikost(d.prosto || 0), skupaj: velikost(d.velikost) })
      : t("diskNiPriklopljen", { skupaj: velikost(d.velikost) });
    var b = el("button", "disk" + (S.pot && d.pot && S.pot === d.pot ? " izbran" : "") + (d.malo_prostora ? " malo" : ""),
      svg(d.odstranljiv ? "arhiv" : "namizje") + "<span class=\"disk-opis\"><span>" + ubezi(imeDiska(d)) + "</span><small>" + ubezi(pod) +
      "</small>" + (deluje ? "<i class=\"disk-vrstica\"><b style=\"width:" + Math.round(delez * 100) + "%\"></b></i>" : "") + "</span>");
    b.type = "button";
    b.title = imeDiska(d) + (d.datotecni_sistem ? " · " + d.datotecni_sistem : "") + " · " + pod;
    b.setAttribute("aria-label", b.title);
    b.addEventListener("click", function () {
      if (d.priklopljen && d.pot) { odpriMapo(d.pot); return; }
      obvesti(t("diskPriklapljam", { ime: imeDiska(d) }));
      klic("priklopiDisk", [d.naprava]).then(function (o) {
        S.diskiCas = 0;
        if (o && o.ok && o.pot) { odpriMapo(o.pot); narisiMape(); }
        else obvesti(t(o && o.napaka === "zavrnjeno" ? "diskPriklopZavrnjen" : "diskPriklopNi", { ime: imeDiska(d) }));
      }, function () { obvesti(t("diskPriklopNi", { ime: imeDiska(d) })); });
    });
    return b;
  }
  // Enkrat na sejo za vsak disk: malo prostora (manj kot 5 GB, ali manj kot 10 % in hkrati manj kot 15 GB).
  function opozoriMaloProstora(diski) {
    S.diskiOpozorjeni = S.diskiOpozorjeni || {};
    (diski || []).forEach(function (d) {
      if (!d.malo_prostora || S.diskiOpozorjeni[d.naprava]) return;
      S.diskiOpozorjeni[d.naprava] = 1;
      obvesti(t("diskMalo", { ime: imeDiska(d), prosto: velikost(d.prosto || 0) }));
    });
  }
  // O tem racunalniku (Nastavitve): strojna in programska oprema, diski. Samo prikaz - nic ne gre z racunalnika.
  function narisiORacunalniku() {
    var dl = $("oRacunalniku"); if (!dl) return;
    klic("sistemPodatki").then(function (p) {
      if (!p) return;
      dl.innerHTML = "";
      function vrsta(k, v) { if (!v) return; var d = el("div", "bliznjica", ""); d.appendChild(el("dt", "", ubezi(t(k)))); d.appendChild(el("dd", "", ubezi(v))); dl.appendChild(d); }
      var ram = p.pomnilnik || {}, sek = p.cas_delovanja_s || 0, ure = Math.floor(sek / 3600);
      vrsta("racRacunalnik", p.racunalnik);
      vrsta("racSistem", p.sistem + (p.arhitektura ? " (" + p.arhitektura + ")" : ""));
      vrsta("racJedro", p.jedro);
      // Namizje samo, ce pove kaj novega (na Windows je »Windows« ze v vrstici Sistem).
      if (p.namizje && String(p.sistem || "").toLowerCase().indexOf(String(p.namizje).toLowerCase()) < 0) vrsta("racNamizje", p.namizje);
      vrsta("racProcesor", p.procesor ? p.procesor + (p.jeder ? " · " + t("racJeder", { n: p.jeder }) : "") : "");
      vrsta("racPomnilnik", ram.skupaj ? t("racPomnilnikVr", { skupaj: velikost(ram.skupaj), prosto: velikost(ram.na_voljo || 0) }) : "");
      vrsta("racGraficna", (p.graficne || []).join(", "));
      (p.diski || []).forEach(function (d) {
        vrsta("racDisk", imeDiska(d) + " · " + (d.priklopljen ? t("diskProsto", { prosto: velikost(d.prosto || 0), skupaj: velikost(d.velikost) })
          : t("diskNiPriklopljen", { skupaj: velikost(d.velikost) })) + (d.datotecni_sistem ? " · " + d.datotecni_sistem : ""));
      });
      vrsta("racCas", ure >= 24 ? t("racDni", { d: Math.floor(ure / 24), h: ure % 24 })
        : ure >= 1 ? t("racUr", { h: ure }) : t("racMin", { m: Math.floor(sek / 60) }));
      vrsta("racSafeer", (S.zacetek && S.zacetek.razlicica) || "");
    }, function () {});
  }
  // tiho = seznam nedavnih se je spremenil zunaj Safeer OS: preberemo ga znova, drsnik in fokus ostaneta.
  function odpriNedavne(tiho) {
    tiho = tiho === true;               // klik na gumb poda dogodek, ne zastavice
    var prej = tiho ? stanjePredOsvezitvijo() : null;
    if (!tiho) {
      S.pot = ""; S.datPogled = "nedavne";
      spremljajDatoteke();
      narisiMape();
      var dr = $("drobtine");
      dr.innerHTML = "";
      dr.appendChild(el("button", "", ubezi(t("nedavno"))));
      var desnoN = el("div", "desno");
      var poc = el("button", "gumb", svg("x") + "<span>" + ubezi(t("pocistiSeznam")) + "</span>");
      poc.addEventListener("click", pocistiNedavne);
      desnoN.appendChild(poc);
      dr.appendChild(desnoN);
    }
    klic("nedavne").then(function (seznam) {
      if (S.datPogled !== "nedavne") return;
      if (tiho && odtisDatotek(seznam) === odtisDatotek(S.nedavne)) return;     // nic novega: brez prerisovanja
      S.nedavne = seznam || [];
      var v = $("vsebinaMape");
      v.innerHTML = "";
      if (!S.nedavne.length) { v.appendChild(el("div", "prazno", ubezi(t("prazno")))); return; }
      S.nedavne.forEach(function (d) { v.appendChild(vrsticaDatoteke(d, true, true)); });
      if (prej) poTihiOsvezitvi(prej);
    }, function () {});
  }
  function prikaziIskanjeDatotek(niz, znani) {
    S.datotekeIskanje = String(niz || "").trim();
    S.pot = ""; S.datPogled = "iskanje";
    spremljajDatoteke();
    narisiMape();
    var dr = $("drobtine");
    dr.innerHTML = "";
    dr.appendChild(el("span", "", ubezi(t("rezultatiZa", { niz: S.datotekeIskanje }))));
    var v = $("vsebinaMape");
    v.innerHTML = "";
    if (Array.isArray(znani)) {
      S.iskalneDatoteke = znani;
      znani.forEach(function (d) { v.appendChild(vrsticaDatoteke(d, true, false)); });
      if (!znani.length) v.appendChild(el("div", "prazno", ubezi(t("niZadetkov"))));
      fokusPrvegaV("vsebinaMape");
      return;
    }
    v.appendChild(el("div", "prazno", ubezi(t("iscem"))));
    klic("isciDatoteke", [S.datotekeIskanje, 200]).then(function (seznam) {
      if ($("datotekeIskanje").value.trim() !== S.datotekeIskanje) return;
      prikaziIskanjeDatotek(S.datotekeIskanje, seznam || []);
    }, function () { v.innerHTML = ""; v.appendChild(el("div", "prazno", ubezi(t("niZadetkov")))); });
  }
  // tiho = mapa se je spremenila zunaj Safeer OS: preberemo jo znova, drsnik in fokus ostaneta; brez spremembe nic.
  function odpriMapo(pot, tiho) {
    tiho = tiho === true;
    klic("mapa", [pot]).then(function (r) {
      if (tiho && (S.razdelek !== "datoteke" || S.datPogled !== "mapa" || S.pot !== r.pot)) return;
      if (tiho && !r.napaka && odtisDatotek(r.elementi) === S.mapaOdtis) return;
      if (tiho && !r.napaka && posodobiVrstice(S.mapaElementi, r.elementi)) { S.mapaOdtis = odtisDatotek(r.elementi); return; }
      var prej = tiho ? stanjePredOsvezitvijo() : null, prejNarisano = tiho ? (S.mapaNarisano || 0) : 0;
      S.pot = r.pot; S.datPogled = "mapa"; S.mapaOdtis = r.napaka ? "" : odtisDatotek(r.elementi); S.mapaNarisano = 0;
      S.mapaElementi = r.napaka ? null : r.elementi;
      spremljajDatoteke();
      if (!tiho) narisiMape();
      var dr = $("drobtine");
      dr.innerHTML = "";
      var d = dom();
      var zacetek = d && r.pot.indexOf(d) === 0 ? d : "/";
      var deli = r.pot.slice(zacetek.length).split("/").filter(Boolean);
      var koren = el("button", "", ubezi(zacetek === "/" ? "/" : (S.zacetek.mape[0].ime || "~")));
      koren.addEventListener("click", function () { odpriMapo(zacetek); });
      dr.appendChild(koren);
      var sproti = zacetek.replace(/\/$/, "");
      deli.forEach(function (del) {
        sproti += "/" + del;
        var cilj = sproti;
        dr.appendChild(el("span", "loc", "›"));
        var b = el("button", "", ubezi(del));
        b.addEventListener("click", function () { odpriMapo(cilj); });
        dr.appendChild(b);
      });
      var desno = el("div", "desno");
      var vDat = el("button", "gumb", svg("mapa") + "<span>" + ubezi(t("odpriVDatotekah")) + "</span>");
      vDat.addEventListener("click", function () { klic("pokaziVMapi", [r.pot]); });
      desno.appendChild(vDat);
      dr.appendChild(desno);
      var v = $("vsebinaMape");
      v.innerHTML = "";
      if (r.napaka) { v.appendChild(el("div", "prazno", ubezi(t(r.napaka === "ni_dovoljenja" ? "niDovoljenja" : "prazno")))); return; }
      if (!r.elementi.length) { v.appendChild(el("div", "prazno", ubezi(t("prazno")))); return; }
      // Velika mapa (do 5000 vnosov): vrstice dodajamo po delih, ko se uporabnik pomakne proti koncu - stran ostane odzivna.
      var narisano = 0, KOS = 300, straza = el("div", "");
      var opazovalec = new IntersectionObserver(function (z) {
        if (!z[0].isIntersecting || S.pot !== r.pot) return;
        dodajKos();
        if (narisano < r.elementi.length) { opazovalec.unobserve(straza); opazovalec.observe(straza); }
      }, { rootMargin: "800px" });
      function dodajKos() {
        r.elementi.slice(narisano, narisano + KOS).forEach(function (e) { v.insertBefore(vrsticaDatoteke(e, false), straza); });
        narisano += KOS;
        S.mapaNarisano = Math.min(narisano, r.elementi.length);
        if (narisano >= r.elementi.length) { opazovalec.disconnect(); straza.remove(); }
      }
      v.appendChild(straza);
      dodajKos();
      // Tiha osvezitev: narisemo toliko vrstic, kot jih je bilo (uporabnik je morda globoko v veliki mapi).
      while (narisano < r.elementi.length && narisano < prejNarisano) dodajKos();
      if (narisano < r.elementi.length) opazovalec.observe(straza);
      if (prej) poTihiOsvezitvi(prej);
    }, function () {});
  }
  function narisiNedavneDomov() {
    klic("nedavne").then(function (seznam) {
      seznam = (seznam || []).slice(0, 5);
      $("blokNedavne").hidden = !seznam.length;
      var v = $("nedavneDomov");
      v.innerHTML = "";
      seznam.forEach(function (d) { v.appendChild(vrsticaDatoteke(d, true, true)); });
    }, function () {});
  }

  // ------------------------------------------------------------------ naprave
  var odjavaPotrjujem = false, odjavaCas = 0;
  function osveziPovezavo() {
    return klic("povezava").then(function (p) { S.povezava = p || S.povezava; narisiPovezavo(); }, function () { narisiPovezavo(); });
  }
  // V Napravah nepovezan racunalnik isce Safeer Link naprej: ko ga uporabnik vklopi na televizorju
  // ali telefonu, se kartica posodobi sama - brez klikanja »poišči znova«.
  var napraveCas = null;
  function napraveZanka() {
    clearInterval(napraveCas);
    napraveCas = setInterval(function () {
      if (S.razdelek !== "naprave") { clearInterval(napraveCas); return; }
      if (skrito()) return;
      if (S.povezava.stanje !== "povezan") osveziPovezavo();
    }, 12000);
  }
  function narisiPovezavo() {
    var p = S.povezava;
    if (S.stanje) setTimeout(function () { narisiStanje(S.stanje); }, 0);
    var povezan = p.stanje === "povezan";
    if (!povezan) S.vseNaprave = [];
    $("napravePika").className = "pika" + (povezan ? "" : " siva");
    $("napraveNaslov").textContent = t(povezan ? "povezanNaslov" : (p.stanje === "brez" ? "brezNaslov" : "novNaslov"));
    // Nepovezan racunalnik: povemo, ali je v omrezju Safeer Link (in kateri) - uporabnik takoj ve, kaj sledi.
    var hubi = p.hubi || [];
    $("napraveBesedilo").textContent = !p.control ? t("niControla") : povezan ? t("povezanOpis") :
      (hubi.length ? t("novOpisHub", { ime: hubi[0].ime }) : (p.hubi ? t("novOpisBrezHuba") : t("novOpis")));
    var namig = $("napraveNamig");
    namig.hidden = povezan || !p.control || hubi.length > 0 || !p.hubi;
    namig.textContent = t("napraveNamig");
    narisiSeznamNaprav(povezan && !!p.control);
    $("gumbControl").hidden = !p.control;
    $("gumbControlBesedilo").textContent = t(povezan ? "odpriControl" : "poveziNaprave");
    $("gumbControl").querySelector("svg").innerHTML = '<path d="' + IK[povezan ? "naprave" : "qr"] + '"/>';
    $("kNapravePod").textContent = t(povezan ? "napravePodPovezan" : "napravePodNov");
    $("blokZaupanje").hidden = !povezan;
    $("gumbOdjava").hidden = !povezan || !p.control;
    $("gumbOdjava").classList.toggle("opozorilo", odjavaPotrjujem);
    $("gumbOdjavaBesedilo").textContent = t(odjavaPotrjujem ? "odjavaPotrdi" : "odjaviRacunalnik");
    $("stikaloZaupaj").setAttribute("aria-checked", p.zaupana ? "true" : "false");
    $("zaupajPod").textContent = t(p.zaupana ? "zaupajDa" : "zaupajNe");
    if (typeof p.predajanje === "boolean") $("stikaloPredaja").setAttribute("aria-checked", p.predajanje ? "true" : "false");
    $("domNapravaStanje").innerHTML = '<i class="pika' + (povezan ? "" : " siva") + '"></i><span>' +
      ubezi(t(povezan ? "povezanKratko" : "niPovezano")) + "</span>";
    $("domControl").hidden = !p.control;
    $("domControlBesedilo").textContent = t(povezan ? "odpriControl" : "poveziNaprave");
    $("domControl").querySelector("svg").innerHTML = '<path d="' + IK[povezan ? "naprave" : "qr"] + '"/>';
    var sp = $("stanjePovezava");
    sp.innerHTML = '<i class="pika' + (povezan ? "" : " siva") + '"></i><span>' + ubezi(povezan ? t("povezano") : t("brezNaprav")) + "</span>";
  }

  // Naprave v Linku s preimenovanjem: ime hrani sredisce, zato ga vidijo vse naprave (telefon, TV, tablica).
  var preimenujem = null;
  // Ena naprava ima lahko v Linku vec vnosov (TV: sprejemnik zaslona "n-x" in Safeer OS "n-x-os";
  // racunalnik: "pc-y" in "pc-y-control"). Uporabnik vidi eno napravo: zdruzimo jih po osnovnem id-ju,
  // obdrzimo osnovni vnos (ta zna daljinec in zaslon) in zdruzimo zmoznosti. Ta racunalnik je prvi.
  function zdruziSorodnike(naprave) {
    var poOsnovi = {}, vrstniRed = [];
    (naprave || []).forEach(function (n) {
      if (!n || !n.id) return;
      var osnova = String(n.id).replace(/-(os|control)$/, "");
      var obstojec = poOsnovi[osnova];
      if (!obstojec) { poOsnovi[osnova] = Object.assign({}, n); vrstniRed.push(osnova); return; }
      var jeOsnovni = n.id === osnova;
      var glavni = jeOsnovni ? Object.assign({}, n) : obstojec, drugi = jeOsnovni ? obstojec : n;
      var zm = (glavni.zmoznosti || []).slice();
      (drugi.zmoznosti || []).forEach(function (z) { if (zm.indexOf(z) < 0) zm.push(z); });
      glavni.zmoznosti = zm;
      glavni.ta = !!(glavni.ta || drugi.ta);
      glavni.ozji = !!(glavni.ozji || drugi.ozji);
      poOsnovi[osnova] = glavni;
    });
    var izid = vrstniRed.map(function (k) { return poOsnovi[k]; });
    return izid.filter(function (n) { return n.ta; }).concat(izid.filter(function (n) { return !n.ta; }));
  }
  function narisiSeznamNaprav(pokaziSeznam) {
    var blok = $("blokSeznamNaprav");
    blok.hidden = !pokaziSeznam;
    if (!pokaziSeznam) { preimenujem = null; return; }
    klic("vseNaprave").then(function (naprave) {
      var ul = $("seznamNaprav"); ul.innerHTML = "";
      S.vseNaprave = zdruziSorodnike(naprave);
      var iskano = String(S.napraveIskanje || "").trim();
      S.vseNaprave.filter(function (n) {
        return !iskano || Math.max(SafeerIskanje.oceni(n.ime, iskano), SafeerIskanje.oceni(n.platforma, iskano),
          SafeerIskanje.oceni(n.vrsta, iskano)) > 0;
      }).forEach(function (n) {
        var li = el("li");
        li.tabIndex = 0;
        var opis = n.ta ? t("taRacunalnik") : (n.platforma ? t("plat_" + n.platforma) : (n.vrsta || ""));
        if (preimenujem === n.id) {
          li.innerHTML = svg(ikonaNaprave(n)) + '<input class="vnosImena" maxlength="64"><button class="gumb glavni majhen"></button><button class="gumb majhen"></button>';
          var vnos = li.querySelector("input"); vnos.value = n.ime; vnos.placeholder = t("vnesiIme");
          var gumbi = li.querySelectorAll("button");
          gumbi[0].textContent = t("shraniIme"); gumbi[1].textContent = t("preklici");
          gumbi[0].addEventListener("click", function () { shraniIme(n.id, vnos.value); });
          gumbi[1].addEventListener("click", function () { preimenujem = null; narisiSeznamNaprav(true); });
          vnos.addEventListener("keydown", function (e) {
            if (e.key === "Enter") shraniIme(n.id, vnos.value);
            if (e.key === "Escape") { preimenujem = null; narisiSeznamNaprav(true); }
          });
          setTimeout(function () { vnos.focus(); vnos.select(); }, 0);
        } else {
          // Upravljanje zaslona samo za naprave v ozjem krogu zaupanja (lastnik, 17. 10. 2026).
          var jeRacunalnik = !n.ta && n.ozji && (n.vrsta === "computer" || n.vrsta === "control" ||
            n.platforma === "linux" || n.platforma === "windows" || n.platforma === "macos");
          li.innerHTML = svg(ikonaNaprave(n)) + "<div><b></b><small></small></div>" +
            (jeRacunalnik ? "<button class=\"gumb glavni majhen upravljaj\"></button>" : "") +
            "<button class=\"gumb majhen preimenuj\"></button>";
          li.querySelector("b").textContent = n.ime || n.id;
          li.querySelector("small").textContent = opis;
          if (jeRacunalnik) {
            var u = li.querySelector("button.upravljaj");
            u.textContent = t("upravljajRacunalnik");
            u.addEventListener("click", function () {
              u.disabled = true;
              klic("upravljajRacunalnik", [n.id]).then(function (r) {
                u.disabled = false;
                if (!r || !r.ok) obvesti((r && r.message) || t("oddaljeniNapaka"));
              }, function (e) { u.disabled = false; obvesti(String(e || t("oddaljeniNapaka"))); });
            });
          }
          var g = li.querySelector("button.preimenuj"); g.textContent = "✎ " + t("preimenuj"); g.title = t("preimenuj");
          g.addEventListener("click", function () { preimenujem = n.id; narisiSeznamNaprav(true); });
        }
        ul.appendChild(li);
      });
      $("seznamNapravNamig").textContent = t("preimenujNamig");
      if (iskano) fokusPrvegaV("seznamNaprav");
    }, function () {});
  }
  // Zakaj imena ni bilo mogoce shraniti: znano kodo povemo z besedo (napIme_<koda>), neznana ostane pri splosnem.
  function razlogImena(r) {
    var kljuc = "napIme_" + String((r && r.koda) || "");
    var b = t(kljuc);
    return b === kljuc ? "" : " " + b;
  }
  function shraniIme(id, ime) {
    klic("preimenujNapravo", [id, ime]).then(function (r) {
      preimenujem = null;
      obvesti(r && r.ok ? t("preimenovano") : t("napPreimenovanje") + razlogImena(r));
      narisiSeznamNaprav(true);
      nalozNaprave();
    }, function () { obvesti(t("napPreimenovanje")); });
  }

  // ------------------------------------------------------------------ stanje sistema (vrstica zgoraj)
  function narisiStanje(s) {
    if (!s) return;
    S.stanje = s;
    var o = s.omrezje || {};
    var ikona = o.vrsta === "wifi" ? "wifi" : (o.vrsta === "ethernet" ? "ethernet" : "brezOmrezja");
    var ime = o.vrsta === "ethernet" ? t("zicna") : (o.ime || t("brezOmrezja"));
    $("stanjeOmrezje").innerHTML = svg(ikona) + "<span>" + ubezi(ime) + "</span>";
    $("stanjeOmrezje").title = o.ime || "";
    var z = s.zvok;
    $("stanjeZvok").innerHTML = z ? svg(z.utisan ? "utisan" : "zvok") + "<span>" + (z.utisan ? "" : z.glasnost + " %") + "</span>" : "";
    narisiGlasnostTraku();
    var b = s.baterija;
    $("stanjeBaterija").innerHTML = b ? svg(b.polni ? "polni" : "baterija") + "<span>" + b.odstotek + " %</span>" : "";
    var podatki = [[t("omrezje"), ime, !!o.vrsta]];
    if (b) podatki.push([t("baterija"), b.odstotek + " %" + (b.polni && !b.polna ? " · " + t("polni") : ""), true]);
    podatki.push(["Safeer Link", t(S.povezava.stanje === "povezan" ? "povezanKratko" : "niPovezano"), S.povezava.stanje === "povezan"]);
    $("sistemPodatki").innerHTML = podatki.map(function (v) {
      return "<dt>" + ubezi(v[0]) + '</dt><dd><i class="pika' + (v[2] ? "" : " siva") + '"></i>' + ubezi(v[1]) + "</dd>";
    }).join("");
    if ($("slojHitro").classList.contains("viden")) narisiHitro();
  }
  function osveziStanje() { klic("stanje").then(narisiStanje, function () {}); }

  // Drsniki in stikala (hitra plosca in nastavitve)
  var zamik = {};
  function drsnik(kljuc, ikona, vrednost, ob) {
    var d = el("div", "drsnik");
    d.innerHTML = svg(ikona) + "<label>" + ubezi(t(kljuc)) + '</label><input type="range" min="0" max="100" step="1"><output></output>';
    var vhod = d.querySelector("input"), izhod = d.querySelector("output");
    vhod.value = vrednost;
    izhod.textContent = vrednost + " %";
    vhod.setAttribute("aria-label", t(kljuc));
    vhod.addEventListener("input", function () {
      izhod.textContent = vhod.value + " %";
      clearTimeout(zamik[kljuc]);
      zamik[kljuc] = setTimeout(function () { ob(parseInt(vhod.value, 10)); }, 120);
    });
    return d;
  }
  function stikalo(kljuc, ikona, vklop, ob, pod) {
    var b = el("button", "stikalo");
    b.setAttribute("role", "switch");
    b.setAttribute("aria-checked", vklop ? "true" : "false");
    b.innerHTML = svg(ikona) + "<div><span>" + ubezi(t(kljuc)) + "</span>" + (pod ? "<small>" + ubezi(pod) + "</small>" : "") + "</div><i></i>";
    b.addEventListener("click", function () {
      var nov = b.getAttribute("aria-checked") !== "true";
      b.setAttribute("aria-checked", nov ? "true" : "false");
      ob(nov);
    });
    return b;
  }
  function kontrole(cilj, kompaktno) {
    var s = S.stanje || {};
    cilj.innerHTML = "";
    if (s.zvok) {
      cilj.appendChild(drsnik("glasnost", s.zvok.utisan ? "utisan" : "zvok", Math.min(100, s.zvok.glasnost), function (v) {
        klic("glasnost", [v]).then(function () { s.zvok.glasnost = v; s.zvok.utisan = false; narisiStanje(s); });
      }));
    }
    if (s.svetlost != null) {
      cilj.appendChild(drsnik("svetlost", "svetlost", s.svetlost, function (v) { klic("svetlost", [v]); s.svetlost = v; }));
    }
    var mreza = kompaktno ? el("div", "hitro-mreza") : cilj;
    var o = s.omrezje || {};
    if (o.wifi_obstaja) {
      mreza.appendChild(stikalo("wifi", "wifi", !!o.wifi_vklopljen, function (v) {
        klic("wifi", [v]).then(function () { setTimeout(osveziStanje, 1500); });
      }, kompaktno ? "" : (o.vrsta === "wifi" ? o.ime : (o.wifi_vklopljen ? "" : t("wifiIzklopljen")))));
    }
    if (s.nocna != null) mreza.appendChild(stikalo("nocna", "luna", !!s.nocna, function (v) { klic("nocna", [v]); s.nocna = v; }));
    if (s.zvok) {
      mreza.appendChild(stikalo("utisaj", "utisan", !!s.zvok.utisan, function () {
        klic("utisaj").then(function () { setTimeout(osveziStanje, 200); });
      }));
    }
    if (!kompaktno && cilj.id === "hitreNastavitve") {
      // Racunalnik brez zvoka, svetlosti in Wi-Fi (namizni PC): prazen razdelek skrijemo skupaj z naslovom.
      var prazno = !cilj.children.length, naslov = cilj.previousElementSibling;
      cilj.hidden = prazno;
      if (naslov && naslov.tagName === "H2") naslov.hidden = prazno;
    }
    if (kompaktno) {
      cilj.appendChild(mreza);
      var vec = el("button", "gumb", svg("drsniki") + "<span>" + ubezi(t("nastavitve")) + "</span>");
      vec.addEventListener("click", function () { zapriSloje(); pojdi("nastavitve"); });
      cilj.appendChild(vec);
    }
  }
  function narisiHitro() { kontrole($("hitro"), true); }
  function odpriHitro() { zapriSloje(); narisiHitro(); $("slojHitro").classList.add("viden"); osveziStanje(); }

  // ------------------------------------------------------------------ internet prek telefona (Safeer Internet Gateway)
  // Promet tega racunalnika gre skozi telefon v Safeer Linku. Vse naredi Safeer Control (posrednik, preklop ob
  // izpadu); tu so samo nastavitve in stanje. Telefon mora racunalniku uporabo dovoliti - vprasanje se pokaze na njem.
  var internetS = null, internetCas = 0, internetPreizkusa = false;
  function nalozInternet(vprasaj) {
    klic("internetStanje", [!!vprasaj]).then(function (s) {
      var prvic = !internetS;
      internetS = s || null;
      narisiInternet();
      // Prvi prikaz je iz tega, kar Control ze ve (takoj); nato telefon vprasamo, kaj dovoli.
      if (prvic && !vprasaj && s && s.ok !== false && s.telefon) nalozInternet(true);
    }, function () {});
  }
  function internetZanka() {
    clearInterval(internetCas);
    internetCas = setInterval(function () {
      if (S.razdelek !== "omrezje") { clearInterval(internetCas); return; }
      if (skrito()) return;
      if (!internetPreizkusa) nalozInternet(false);
    }, 5000);
  }
  function internetNastavi(sprememba) {
    klic("internetNastavi", [sprememba]).then(function (s) {
      if (s && s.nacin) {
        internetS = s;
        narisiInternet();
        // Telefon se enkrat vprasamo: ob prvem vklopu se na njem pokaze vprasanje za dovoljenje.
        setTimeout(function () { nalozInternet(true); }, 500);
      } else {
        obvesti(t("intNiUspelo"));
        nalozInternet(false);
      }
    }, function () { obvesti(t("intNiUspelo")); });
  }
  /** [kljuc besedila, ali je v redu] za izbrani telefon. */
  function internetDovoljenje(s) {
    var p = s.ponudnik;
    if (!p) return [s.brez_odgovora ? "intDov_stari" : "intDov_caka", false];
    if (p.enabled === false) return ["intDov_disabled", false];
    var d = String(p.permission || "allowed");
    if (["allowed", "pending", "denied", "not_trusted"].indexOf(d) < 0) d = "caka";
    return ["intDov_" + d, d === "allowed"];
  }
  function internetVrstica(ikona, ime, pod, dobro) {
    return el("div", "vrstica", svg(ikona) + '<span class="ime">' + ubezi(ime) + '</span><span class="pod">' +
      (dobro == null ? "" : '<i class="pika' + (dobro ? "" : " siva") + '"></i> ') + ubezi(pod) + "</span>");
  }
  function narisiInternet() {
    var blok = $("blokInternet"), s = internetS;
    if (!blok) return;
    // Starejsi Safeer Control (brez te zmoznosti) ali napaka: plosce ne kazemo.
    if (!s || (s.ok === false && s.koda !== "ni_controla")) { blok.hidden = true; return; }
    blok.hidden = false;
    var nacini = $("internetNacin"), vrstice = $("internetVrstice"), stikala = $("internetStikala"), namig = $("internetNamig");
    var gumb = $("gumbInternetPreizkus");
    nacini.innerHTML = ""; vrstice.innerHTML = ""; stikala.innerHTML = "";
    if (s.ok === false) {
      // Safeer Control ne tece: Linka ni, telefona ne vidimo. Ponudimo zagon.
      namig.textContent = t("intNiControla"); namig.hidden = false;
      gumb.hidden = true; $("internetIzid").hidden = true;
      var z = el("button", "gumb", ubezi(t("intZazeni")));
      z.addEventListener("click", function () { z.disabled = true; internetNastavi({}); });
      stikala.appendChild(z);
      return;
    }
    ["izklopljeno", "izpad", "vedno"].forEach(function (n) {
      var b = el("button", s.nacin === n ? "izbran" : "", ubezi(t("intNacin_" + n)));
      b.type = "button";
      b.addEventListener("click", function () { if (s.nacin !== n) internetNastavi({ nacin: n }); });
      nacini.appendChild(b);
    });
    var telefoni = s.telefoni || [];
    namig.textContent = telefoni.length ? t("intNacinPod_" + s.nacin) : t("intNiTelefona");
    namig.hidden = false;
    telefoni.forEach(function (tel) {
      var izbran = tel.id === s.telefon;
      var dov = izbran ? internetDovoljenje(s) : null;
      var v = internetVrstica("telefon", tel.ime || tel.id, izbran ? t(dov[0]) : "", izbran ? dov[1] : null);
      if (!izbran) {
        var desno = el("span", "dejanja");
        var g = el("button", "gumb", ubezi(t("intUporabi")));
        g.addEventListener("click", function () { internetNastavi({ naprava: tel.id }); });
        desno.appendChild(g);
        v.appendChild(desno);
      }
      vrstice.appendChild(v);
    });
    var vklopljeno = s.nacin !== "izklopljeno";
    if (vklopljeno) {
      // »Skozi telefon« sele, ko telefon to res dovoli; do takrat povezave skozi njega ne uspejo.
      var sme = !!s.telefon && internetDovoljenje(s)[1];
      // Pomoc ob gneci: domaca linija je zasicena, nove povezave (ali samo velika posiljanja) gredo skozi telefon.
      var gn = s.gneca || {};
      var obGneci = !s.prek_telefona && !!gn.dejavna;
      var zdaj = !s.telefon ? "intZdaj_brez" : (obGneci ? (gn.nastavitev === "vse" ? "intZdaj_gneca" : "intZdaj_gnecaOddaje") :
        (!s.prek_telefona ? "intZdaj_doma" : (sme ? "intZdaj_telefon" : "intZdaj_ne")));
      vrstice.appendChild(internetVrstica("povezava", t("intZdaj"), t(zdaj), (!!s.prek_telefona && sme) || obGneci));
    }
    var por = s.poraba || {};
    if (vklopljeno || por.mesec) {
      vrstice.appendChild(internetVrstica("disk", t("intPoraba"),
        t("intPorabaVrednost", { danes: velikost(por.danes || 0), mesec: velikost(por.mesec || 0) }), null));
    }
    var mob = s.ponudnik && s.ponudnik.cellular;
    if (mob && s.telefon) {
      var besedilo = mob.allowed === false ? t("intMobilniIzklop")
        : t("intPorabaVrednost", { danes: velikost(mob.used_today || 0), mesec: velikost(mob.used_month || 0) }) +
          (mob.limit_bytes ? t("intMobilniOd", { omejitev: velikost(mob.limit_bytes) }) : "");
      vrstice.appendChild(internetVrstica("telefon", t("intMobilni"), besedilo, null));
    }
    var pos = s.posrednik || {}, naslov = (pos.naslov || "127.0.0.1") + ":" + (pos.vrata || "");
    if (vklopljeno && pos.tece) {
      vrstice.appendChild(internetVrstica("program", t("intPosrednik"), t("intPosrednikPod", { naslov: naslov }), null));
    }
    var sis = s.sistemski || {};
    if (!vklopljeno) {
      // Izklopljeno: sistema se ne dotikamo, stikala ne kazemo.
    } else if (sis.podprt) {
      stikala.appendChild(stikalo("intSistemski", "drsniki", !!sis.vklopljen, function (v) { internetNastavi({ sistemski: v }); },
        t("intSistemskiPod")));
    } else if (pos.tece) {
      stikala.appendChild(el("p", "namig", ubezi(t("intSistemskiNi", { naslov: naslov }))));
    }
    if (s.nacin === "izpad" && s.gneca) {
      // Privzeto izklopljeno; vklop pomeni tudi nove povezave programov (»vse«), drugo stikalo jih lahko izkljuci.
      var gneca = s.gneca.nastavitev || "izklopljeno";
      stikala.appendChild(stikalo("intGneca", "telefon", gneca !== "izklopljeno",
        function (v) { internetNastavi({ gneca: v ? "vse" : "izklopljeno" }); }, t("intGnecaPod")));
      if (gneca !== "izklopljeno") {
        stikala.appendChild(stikalo("intGnecaVse", "program", gneca === "vse",
          function (v) { internetNastavi({ gneca: v ? "vse" : "oddaje" }); }, t("intGnecaVsePod")));
      }
    }
    gumb.hidden = !s.telefon;
  }
  function internetPreizkus() {
    if (internetPreizkusa) return;
    internetPreizkusa = true;
    var izid = $("internetIzid");
    izid.hidden = false;
    izid.textContent = t("intPreizkusam");
    var konec = function (besedilo) { internetPreizkusa = false; izid.textContent = besedilo; nalozInternet(false); };
    klic("internetPreizkus", []).then(function (r) {
      if (r && r.ok) {
        var kljucPoti = "intPot_" + (r.vrsta_poti || "other");
        var pot = t(kljucPoti) === kljucPoti ? t("intPot_other") : t(kljucPoti);
        konec(t("intPreizkusOk", { pot: pot, naslov: r.naslov_prek_telefona || "?", ms: r.skupaj_ms || 0 }) +
          (r.naslov_neposredno ? " " + t(r.druga_pot ? "intPreizkusDruga" : "intPreizkusIsta") : ""));
      } else {
        var k = "intRazlog_" + ((r && r.koda) || "napaka");
        konec(t("intPreizkusNi", { razlog: t(k) === k ? t("intRazlog_napaka") : t(k) }));
      }
    }, function () { konec(t("intPreizkusNi", { razlog: t("intRazlog_napaka") })); });
  }

  // ------------------------------------------------------------------ omrezje
  var omrezjeGeslo = "", omrezjePozabi = "", omrezjeZaposleno = false;
  function signalIkona(n) { return n >= 67 ? 3 : (n >= 34 ? 2 : 1); }
  function nalozOmrezje(osvezi) {
    if (osvezi) $("omrezjeStanje").textContent = t("iscemOmrezja");
    klic("omrezje", [!!osvezi]).then(narisiOmrezje, function () {});
  }
  function narisiOmrezje(o) {
    o = o || { naprave: [], omrezja: [], shranjene: [] };
    var wifi = o.naprave.filter(function (n) { return n.vrsta === "wifi"; });
    var trenutne = $("omrezjeTrenutno");
    trenutne.innerHTML = "";
    o.naprave.forEach(function (n) {
      var povezana = n.stanje === "connected";
      var ime = n.vrsta === "ethernet" ? t("zicna") : "Wi-Fi";
      var v = el("div", "vrstica", svg(n.vrsta === "ethernet" ? "ethernet" : "wifi") + '<span class="ime">' + ubezi(ime) +
        (povezana && n.povezava ? " · " + ubezi(n.povezava) : "") + '</span><span class="pod"><i class="pika' + (povezana ? "" : " siva") +
        '"></i> ' + ubezi(t(povezana ? "povezanKratko" : "niPovezano")) + "</span>");
      trenutne.appendChild(v);
    });
    if (!o.naprave.length) trenutne.appendChild(el("div", "prazno", ubezi(t("brezOmrezja"))));
    var st = $("stikaloWifiOmrezje");
    st.hidden = !wifi.length;
    st.setAttribute("aria-checked", o.wifi_vklopljen ? "true" : "false");
    $("blokWifi").hidden = !wifi.length || !o.wifi_vklopljen;
    $("omrezjeStanje").textContent = !wifi.length ? t("niWifi") : (o.wifi_vklopljen ? "" : t("wifiIzklopljen"));
    var seznam = $("omrezjaSeznam");
    seznam.innerHTML = "";
    if (o.wifi_vklopljen && !o.omrezja.length) seznam.appendChild(el("div", "prazno", ubezi(t("niOmrezij"))));
    o.omrezja.forEach(function (w) {
      var v = el("div", "vrstica omrezje" + (w.povezano ? " povezano" : ""));
      v.innerHTML = '<span class="signal s' + signalIkona(w.signal) + '">' + svg("wifi") + "</span>" +
        '<span class="ime">' + ubezi(w.ime) + (w.zasciteno ? " " + '<svg class="kljucavnica" viewBox="0 0 24 24"><path d="' + IK.zakleni + '"/></svg>' : "") + "</span>";
      var desno = el("span", "dejanja");
      if (w.povezano) {
        desno.appendChild(el("span", "znacka", ubezi(t("povezanKratko"))));
        var odk = el("button", "gumb", ubezi(t("odklopi")));
        odk.addEventListener("click", function () {
          klic("omrezjeOdklopi", [w.ime]).then(function () { setTimeout(function () { nalozOmrezje(false); }, 800); });
        });
        desno.appendChild(odk);
      } else if (omrezjeGeslo === w.ime) {
        var vnos = el("input", "vnosGesla");
        vnos.type = "password"; vnos.placeholder = t("vnesiGeslo"); vnos.autocomplete = "off";
        var pov = el("button", "gumb glavni", ubezi(t("povezi")));
        var posl = function () {
          if (omrezjeZaposleno) return;
          omrezjeZaposleno = true;
          pov.textContent = t("povezujemSe");
          klic("omrezjePovezi", [w.ime, vnos.value]).then(function (r) {
            omrezjeZaposleno = false;
            if (r && r.ok) { omrezjeGeslo = ""; obvesti(t("povezanKratko") + ": " + w.ime); }
            else obvesti(t(r && r.napaka === "geslo" ? "napacnoGeslo" : "niUspelo"));
            nalozOmrezje(false);
          });
        };
        pov.addEventListener("click", posl);
        vnos.addEventListener("keydown", function (e) { if (e.key === "Enter") posl(); if (e.key === "Escape") { omrezjeGeslo = ""; nalozOmrezje(false); } });
        desno.appendChild(vnos); desno.appendChild(pov);
        setTimeout(function () { vnos.focus(); }, 30);
      } else {
        var p = el("button", "gumb", ubezi(t("povezi")));
        p.addEventListener("click", function () {
          if (w.zasciteno && !w.shranjeno) { omrezjeGeslo = w.ime; narisiOmrezje(o); return; }
          p.textContent = t("povezujemSe");
          klic("omrezjePovezi", [w.ime, ""]).then(function (r) {
            if (r && r.ok) obvesti(t("povezanKratko") + ": " + w.ime);
            else if (r && r.napaka === "geslo") { omrezjeGeslo = w.ime; }
            else obvesti(t("niUspelo"));
            nalozOmrezje(false);
          });
        });
        desno.appendChild(p);
      }
      v.appendChild(desno);
      seznam.appendChild(v);
    });
    var sh = $("omrezjaShranjena");
    sh.innerHTML = "";
    o.shranjene.forEach(function (c) {
      var v = el("div", "vrstica", svg(c.vrsta === "wifi" ? "wifi" : "ethernet") + '<span class="ime">' + ubezi(c.ime) + "</span>");
      var desno = el("span", "dejanja");
      if (c.aktivna) desno.appendChild(el("span", "znacka", ubezi(t("povezanKratko"))));
      else {
        var akt = el("button", "gumb", ubezi(t("povezi")));
        akt.addEventListener("click", function () {
          akt.textContent = t("povezujemSe");
          klic("omrezjeAktiviraj", [c.ime]).then(function (ok) { if (!ok) obvesti(t("niUspelo")); nalozOmrezje(false); });
        });
        desno.appendChild(akt);
      }
      var poz = el("button", "gumb" + (omrezjePozabi === c.ime ? " opozorilo" : ""), ubezi(t(omrezjePozabi === c.ime ? "potrdiPozabi" : "pozabiOmrezje")));
      poz.addEventListener("click", function () {
        if (omrezjePozabi !== c.ime) { omrezjePozabi = c.ime; narisiOmrezje(o); return; }
        omrezjePozabi = "";
        klic("omrezjePozabi", [c.ime]).then(function () { nalozOmrezje(false); });
      });
      desno.appendChild(poz);
      v.appendChild(desno);
      sh.appendChild(v);
    });
    $("blokShranjene").hidden = !o.shranjene.length;
    $("gumbOmrezjeNapredno").hidden = !o.napredno;
  }

  // ------------------------------------------------------------------ zvok
  var zvokStanje = null, zvokCas = 0, zvokDotik = 0, zvokIzbira = SafeerIzhod.novoStanje();
  // Gostitelj za izhod.js: most, obvestila v jeziku strani, casovniki.
  function izhodGostitelj(osvezi, narisi) {
    return { klic: function (m, a, ok, napaka) { klic(m, a).then(ok, napaka || function () {}); },
             obvesti: function (k, z) { obvesti(t(k, z)); }, osvezi: osvezi, narisi: narisi,
             pozneje: function (ms, fn) { setTimeout(fn, ms); } };
  }
  var IKONA_ZVOKA = { zvocniki: "zvok", slusalke: "slusalke", hdmi: "zaslon", bluetooth: "bluetooth", usb: "zvok", mikrofon: "mikrofon" };
  var jblStanje = null, jblZaposleno = false;
  function nalozJbl() {
    klic("jbl").then(function (j) { jblStanje = j; narisiJbl(); }, function () {});
  }
  function narisiJbl() {
    var c = $("zvokJbl");
    c.innerHTML = "";
    var j = jblStanje;
    if (!j || !(j.vklop || j.najdena)) return;
    var pod = jblZaposleno ? t("jblPrenasam") : (j.napaka ? t("jblNapaka_" + j.napaka) : t("jblOpis"));
    var st = stikalo("jblStikalo", "zvok", !!j.vklop, function (v) {
      if (jblZaposleno) return;
      jblZaposleno = true;
      narisiJbl();
      klic("jblVklop", [v]).then(function (r) {
        jblZaposleno = false;
        jblStanje = r;
        if (r && r.napaka) obvesti(t("jblNapaka_" + r.napaka));
        else if (v) obvesti(t("jblVklopljeno", { ime: r.ime || "JBL" }));
        narisiJbl();
      }, function () { jblZaposleno = false; narisiJbl(); });
    }, pod);
    st.querySelector("span").textContent = t("jblStikalo", { ime: j.ime || "JBL" });
    c.appendChild(st);
  }

  // ---- Scit: filtriranje DNS za ves racunalnik (stikalo in stanje v Nastavitvah) ----
  var scitStanje = null, scitZaposleno = false, scitCas = null, scitSpotify = null;
  function nalozScit() {
    klic("scit").then(function (s) { scitStanje = s; narisiScit(); }, function () {});
    if (scitSpotify === null) klic("mediaSpScit").then(function (r) { scitSpotify = !!(r && r.scit); narisiScit(); }, function () {});
  }
  function scitZanka() {
    clearInterval(scitCas);
    scitCas = setInterval(function () {
      if (S.razdelek !== "nastavitve" && S.razdelek !== "scit") { clearInterval(scitCas); return; }
      if (skrito()) return;
      // Seznam nazadnje blokiranih naj ne skoci izpod kazalca ali izbranega gumba (»Dovoli« bi zadel napacno domeno).
      var blok = $("blokScit");
      if (blok && blok.querySelector(".scit-zadnje:hover, .scit-zadnje button:focus, .scit-naprej select:focus, .scit-naprej input:focus")) return;
      if (!scitZaposleno) nalozScit();
    }, 5000);
  }
  // En blok nastavitev Scita na stran: v Nastavitvah ali v oknu Safeer Scit (premakne se, ne podvaja - obe mesti ne
  // moreta pokazati razlicnih nastavitev; vir je en sam, Scit v Safeer OS).
  function premakniScit(mesto) {
    var b = $("blokScit"), m = $(mesto);
    if (b && m && b.parentNode !== m && vodnikKorak < 0) m.appendChild(b);
  }
  function narisiScit() {
    var c = $("blokScit");
    c.innerHTML = "";
    var s = scitStanje;
    if (!s) return;
    if (S.razdelek === "scit") nalozScitStatistiko();
    var pod;
    if (scitZaposleno) pod = t("scitPripravljam");
    else if (!s.mozno) pod = t(s.razlog === "lastni_dns" ? "scitNapaka_lastni_dns" : "scitNiMozno");
    else if (s.napaka) pod = t("scitNapaka_" + s.napaka);
    else if (s.vklop && s.tece) pod = s.domen ? t("scitTece", { n: s.blokiranih, p: s.poizvedb, d: s.domen }) : t("scitSeznami");
    else pod = t("scitOpis");
    var st = stikalo("scitStikalo", "scit", !!(s.vklop && s.tece) || (scitZaposleno && !s.vklop), function (v) {
      if (scitZaposleno || !s.mozno) { narisiScit(); return; }
      scitZaposleno = true;
      narisiScit();
      klic("scitVklop", [v]).then(function (r) {
        scitZaposleno = false;
        scitStanje = r;
        if (r && r.napaka) obvesti(t("scitNapaka_" + r.napaka));
        else obvesti(t(v ? "scitVklopljen" : "scitIzklopljen"));
        narisiScit();
      }, function () { scitZaposleno = false; nalozScit(); });
    }, pod);
    if (!s.mozno) st.classList.add("onemogoceno");
    c.appendChild(st);
    // Tiha izguba sifriranja (pregled 18. 10. 2026): mirna vrstica stanja, brez okna in brez rdece barve.
    if (s.vklop && s.tece && s.nesifrirano) {
      var ns = el("div", "scit-zadnje scit-nesifrirano", ubezi(t("scitNesifrirano")));
      ns.setAttribute("role", "status");
      c.appendChild(ns);
    }
    // Spotify v Safeer DRM (core/spotify_racun.py): oglasi brezplačnega računa, neodvisno od filtriranja DNS.
    if (scitSpotify !== null) {
      c.appendChild(stikalo("scitSpotify", "scit", scitSpotify, function (v) {
        klic("mediaSpScit", [v]).then(function (r) { scitSpotify = !!(r && r.scit); }, function () {});
      }, t("scitSpotifyOpis") + " " + t("spScitObvestilo")));
    }
    function poScitu(r) { if (r) scitStanje = r; narisiScit(); }
    // Twitch brez oglasov (core/twitch_hls.py): velja v Medijskem centru, tudi kadar filtra DNS ni mogoce vklopiti.
    c.appendChild(stikalo("scitTwitch", "twitch", s.twitchOglasi !== false, function (v) {
      klic("scitTwitch", [v]).then(function (r) { obvesti(t(v ? "scitTwitchVklopljen" : "scitTwitchIzklopljen")); poScitu(r); },
                                   function () { nalozScit(); });
    }, t("scitTwitchOpis")));
    if (s.mozno) c.appendChild(scitNaprej(s, poScitu));
    if (s.vklop && s.tece) {
      // Premor: ko stran ali program brez blokirane domene ne dela, uporabniku ni treba izklopiti celega Scita.
      var pr = el("div", "scit-zadnje scit-premor");
      var gp = el("button", "", ubezi(t(s.premor > 0 ? "scitNadaljuj" : "scitPremor")));
      gp.type = "button";
      gp.addEventListener("click", function () { klic("scitPremor", [s.premor > 0 ? 0 : 15]).then(poScitu, function () {}); });
      pr.appendChild(gp);
      if (s.premor > 0) pr.appendChild(el("span", "", ubezi(t("scitPremorTece", { n: Math.ceil(s.premor / 60) }))));
      c.appendChild(pr);
    }
    if (s.vklop && s.tece && s.zadnje && s.zadnje.length) {
      var z = el("div", "scit-zadnje", "<b>" + ubezi(t("scitZadnje")) + "</b>");
      s.zadnje.slice(0, 6).forEach(function (x) {
        var vr = el("span", "", ubezi(x.ime) + " <i>" + ubezi(t("scitKat_" + x.kategorija)) + "</i> ");
        // Dovoli: izjema za to domeno in njene poddomene (odstrani se spodaj, med dovoljenimi).
        var gd = el("button", "", ubezi(t("scitDovoli")));
        gd.type = "button";
        gd.addEventListener("click", function () {
          // Lazna stran, zlonamerna koda ...: en sam klik je premalo.
          if (x.kategorija !== "oglasi" && !gd.dataset.potrdi) {
            gd.dataset.potrdi = "1";
            gd.textContent = t("scitDovoliRes");
            gd.classList.add("nevarno");
            return;
          }
          klic("scitDovoli", [x.ime, true]).then(function (r) {
            if (r && (r.izjeme || []).indexOf(x.ime) >= 0) obvesti(t("scitDovoljeno", { ime: x.ime }));
            poScitu(r);
          }, function () {});
        });
        vr.appendChild(gd);
        z.appendChild(vr);
      });
      c.appendChild(z);
    }
    if (s.izjeme && s.izjeme.length) {
      var iz = el("div", "scit-zadnje", "<b>" + ubezi(t("scitIzjeme")) + "</b>");
      s.izjeme.forEach(function (d) {
        var vi = el("span", "", ubezi(d) + " ");
        var go = el("button", "", ubezi(t("scitBlokirajSpet")));
        go.type = "button";
        go.addEventListener("click", function () { klic("scitDovoli", [d, false]).then(poScitu, function () {}); });
        vi.appendChild(go);
        iz.appendChild(vi);
      });
      c.appendChild(iz);
    }
  }
  // Statistika v oknu Safeer Scit: DNS za ves racunalnik, seznami, Splet in Sporocila, pravila proti sledenju.
  var scitStatCas = 0;
  function nalozScitStatistiko() {
    if (Date.now() - scitStatCas < 4000) return;
    scitStatCas = Date.now();
    klic("scitStatistika").then(narisiScitStatistiko, function () {});
  }
  function scitDatum(sek) {
    if (!sek) return t("scitStatNikoli");
    try { return new Date(sek * 1000).toLocaleString(LOKALE[jezik] || "en-GB", { dateStyle: "short", timeStyle: "short" }); }
    catch (_) { return new Date(sek * 1000).toLocaleString(); }
  }
  function narisiScitStatistiko(st) {
    var dl = $("scitStatistika");
    if (!dl || !st) return;
    var s = st.scit || {}, p = st.pravila || {}, sp = st.splet || {};
    var vrstice = [
      ["scitStatDns", s.vklop && s.tece ? t("scitStatDnsVrednost", { n: s.blokiranih || 0, p: s.poizvedb || 0 }) : t("scitStatIzklopljen")],
      ["scitStatSeznami", t("scitStatSeznamiVrednost", { d: s.domen || 0, cas: scitDatum(s.posodobljeno) })],
      ["scitStatGroznje", t("scitStatGroznjeVrednost", { n: s.pravil || 0 })],
      ["scitStatNesifrirano", t("scitStatNesifriranoVrednost", { n: s.rezerv || 0 })],
      ["scitStatSplet", t("scitStatSpletVrednost", { n: (sp.oglasi || 0) + (sp.groznje || 0) })],
      ["scitStatPravila", t("scitStatPravilaVrednost", { n: p.pravil || 0, v: p.verzija || 0, vir: t("scitVir_" + (p.vir || "vgrajena")) })]
    ];
    dl.innerHTML = "";
    vrstice.forEach(function (v) {
      dl.appendChild(el("dt", "", ubezi(t(v[0]))));
      dl.appendChild(el("dd", "", ubezi(v[1])));
    });
  }
  // Streznik naprej: kam Scit poslje dovoljena imena (privzeto Cloudflare prek DoH) in kdo jih vidi - po resnici.
  var SCIT_NAPREJ = ["cloudflare", "quad9", "google", "adguard", "opendns", "custom", "router"];
  var SCIT_IMENA = { cloudflare: "Cloudflare", quad9: "Quad9", google: "Google", adguard: "AdGuard", opendns: "Cisco OpenDNS" };
  function scitNaprej(s, poScitu) {
    var izbrano = SCIT_NAPREJ.indexOf(s.naprej) >= 0 ? s.naprej : "cloudflare";
    var o = el("div", "scit-zadnje scit-naprej", "<b>" + ubezi(t("scitNaprej")) + "</b>");
    var izbor = el("select");
    izbor.setAttribute("aria-label", t("scitNaprej"));
    SCIT_NAPREJ.forEach(function (k) {
      var op = el("option", "", ubezi(t("scitNaprej_" + k)));
      op.value = k;
      if (k === izbrano) op.selected = true;
      izbor.appendChild(op);
    });
    var vnos = el("input");
    vnos.type = "text";
    vnos.placeholder = t("scitNaprejNamig");
    vnos.value = s.naprejPoMeri || "";
    vnos.setAttribute("aria-label", t("scitNaprej_custom"));
    var shrani = el("button", "", ubezi(t("scitNaprejShrani")));
    shrani.type = "button";
    var kdo = el("span", "");
    function osvezi() {
      var k = izbor.value;
      vnos.hidden = shrani.hidden = k !== "custom";
      kdo.textContent = SCIT_IMENA[k] ? t("scitKdo_ponudnik", { ime: SCIT_IMENA[k] }) : t("scitKdo_" + k);
    }
    function poslji() {
      klic("scitNaprej", [izbor.value, vnos.value]).then(function (r) {
        if (r && r.napaka) obvesti(t("scitNapaka_" + r.napaka));
        poScitu(r);
      }, function () {});
    }
    izbor.addEventListener("change", function () { osvezi(); if (izbor.value !== "custom") poslji(); });
    shrani.addEventListener("click", poslji);
    vnos.addEventListener("keydown", function (e) { if (e.key === "Enter") poslji(); });
    o.appendChild(izbor); o.appendChild(vnos); o.appendChild(shrani); o.appendChild(kdo);
    osvezi();
    return o;
  }
  function nalozZvok() {
    klic("zvok").then(function (z) {
      zvokStanje = z;
      // Med vlecenjem drsnika ali izbiro v meniju ne risemo znova - sicer bi uporabniku ukradli miško.
      var a = document.activeElement;
      if (a && (a.type === "range" || a.tagName === "SELECT") && $("r-zvok").contains(a)) return;
      if (Date.now() - zvokDotik < 1200) return;
      narisiZvok(z);
    }, function () {});
  }
  function zvokZanka() {
    clearInterval(zvokCas);
    zvokCas = setInterval(function () {
      if (S.razdelek !== "zvok") { clearInterval(zvokCas); return; }
      if (skrito()) return;
      nalozZvok();
    }, 2000);
  }
  function zvokDrsnik(kljuc, ikona, vrednost, utisan, naGlasnost, naUtisaj) {
    var ovoj = el("div", "zvok-glasnost");
    var d = drsnik(kljuc, utisan ? "utisan" : ikona, Math.min(100, vrednost), function (v) { zvokDotik = Date.now(); naGlasnost(v); });
    d.querySelector("input").addEventListener("input", function () { zvokDotik = Date.now(); });
    var u = el("button", "gumb-utisaj" + (utisan ? " utisan" : ""), svg(utisan ? "utisan" : "zvok"));
    u.title = t("utisaj");
    u.addEventListener("click", function () { zvokDotik = 0; naUtisaj(!utisan); });
    ovoj.appendChild(d);
    ovoj.appendChild(u);
    return ovoj;
  }
  function zvokVrstica(ikona, ime, pod, izbran, desno) {
    var v = el("div", "vrstica" + (izbran ? " izbran" : ""));
    v.tabIndex = 0;
    v.innerHTML = svg(ikona) + '<span class="besedilo"><b>' + ubezi(ime) + "</b>" + (pod ? "<small>" + ubezi(pod) + "</small>" : "") + "</span>";
    var d = el("span", "dejanja");
    if (desno) d.appendChild(desno);
    v.appendChild(d);
    return v;
  }
  function narisiZvok(z) {
    z = z || { izhodi: [], vhodi: [], programi: [], link: { naprave: [], zvok: {} } };
    var link = z.link || { naprave: [], zvok: {} }, naLinku = (link.zvok || {}).naprava || "";
    // Izhodi racunalnika
    var c = $("zvokIzhodi");
    c.innerHTML = "";
    z.izhodi.forEach(function (i) {
      var izbran = i.privzeti && !naLinku;
      var pod = [t("tip_" + i.vrsta), i.podnapis].filter(function (x, k, a) {
        return x && a.indexOf(x) === k && x.toLowerCase() !== String(i.ime).toLowerCase();
      }).join(" · ");
      var v = zvokVrstica(IKONA_ZVOKA[i.vrsta] || "zvok", i.ime, pod, izbran, izbran ? el("span", "znacka", ubezi(t("vUporabi"))) : null);
      var izberi = function () {
        if (izbran) return;
        zvokDotik = 0;
        klic("zvokIzhod", [i.id]).then(function (ok) {
          if (!ok) obvesti(t("niUspelo")); else if (naLinku) obvesti(t("zvokNazaj"));
          nalozZvok(); osveziStanje();
        });
      };
      v.addEventListener("click", izberi);
      v.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); izberi(); } });
      c.appendChild(v);
    });
    if (!z.izhodi.length) c.appendChild(el("div", "prazno", ubezi(t("niUspelo"))));
    var g = $("zvokGlasnostIzhoda");
    g.innerHTML = "";
    var privzeti = z.izhodi.filter(function (i) { return i.privzeti; })[0];
    if (privzeti && !naLinku) {
      g.appendChild(zvokDrsnik("glasnost", "zvok", privzeti.glasnost, privzeti.utisan,
        function (v) { klic("zvokGlasnostIzhoda", [privzeti.id, v]).then(osveziStanje); },
        function (u) { klic("zvokUtisajIzhod", [privzeti.id, u]).then(function () { nalozZvok(); osveziStanje(); }); }));
    }
    // Naprave v Safeer Linku in zvocniki v omrezju (DLNA, npr. JBL): zvok racunalnika gre nanje. Dejanja in privolitev
    // za zaseden zvocnik so skupna z »Predvajaj na …« v Medijskem centru (izhod.js).
    var l = $("zvokLink");
    l.innerHTML = "";
    var gost = izhodGostitelj(nalozZvok, function () { narisiZvok(zvokStanje || z); });
    SafeerIzhod.moznosti(z).forEach(function (m) {
      if (m.vrsta === "racunalnik") return;
      var tece = m.aktiven, caka = zvokIzbira.caka === m.id && !tece, potrdi = zvokIzbira.potrdi[m.id];
      var gumb;
      if (tece) {
        gumb = el("span", "dejanja");
        gumb.appendChild(el("span", "znacka" + (m.stanje === "tece" ? " tece" : ""), ubezi(t(m.stanje === "tece" ? "zvokPredvaja" : "zvokPovezujem"))));
        var ust = el("button", "gumb", ubezi(t("ustavi")));
        ust.addEventListener("click", function (e) { e.stopPropagation(); SafeerIzhod.nazaj(zvokIzbira, z, gost); });
        gumb.appendChild(ust);
      } else {
        gumb = el("button", "gumb" + (caka ? "" : " glavni"),
          ubezi(caka ? t("zvokPovezujem") : (potrdi ? t("zvokZvocnikPreklopi", { vir: potrdi }) : t("predvajajTukaj"))));
        gumb.addEventListener("click", function (e) { e.stopPropagation(); SafeerIzhod.izberi(zvokIzbira, m, z, gost); });
      }
      var ikona = m.vrsta === "zvocnik" ? "zvok" : (m.platforma === "tablet" || m.platforma === "phone") ? "naprave" : "zaslon";
      var pod = m.vrsta === "zvocnik" ? t("zvokZvocnik") + (m.model ? " · " + m.model : "") : "Safeer Link";
      l.appendChild(zvokVrstica(ikona, m.ime, pod, tece, gumb));
    });
    if (!link.naprave.length && !(link.zvocniki || []).length)
      l.appendChild(el("div", "prazno", ubezi(t(link.povezan ? "zvokBrezNaprav" : "zvokBrezLinka"))));
    // Programi
    var p = $("zvokProgrami");
    p.innerHTML = "";
    var izbire = z.izhodi.map(function (i) { return [i.id, i.ime]; });
    if (naLinku) izbire.push(["safeer_link_zvok", link.zvok.ime || "Safeer Link"]);
    z.programi.forEach(function (pr) {
      var v = el("div", "vrstica program" + (pr.predvaja ? "" : " tiho"));
      v.appendChild(el("span", "crka", ubezi(String(pr.ime || "?").charAt(0).toUpperCase())));
      v.appendChild(el("span", "besedilo", "<b>" + ubezi(pr.ime) + "</b><small>" + ubezi(pr.predvaja ? (pr.naslov || "") : t("zvokUstavljeno")) + "</small>"));
      var r = el("input");
      r.type = "range"; r.min = 0; r.max = 100; r.value = Math.min(100, pr.glasnost);
      r.setAttribute("aria-label", t("glasnost") + " · " + pr.ime);
      var o = el("output", "", Math.min(100, pr.glasnost) + " %");
      var zam = 0;
      r.addEventListener("input", function () {
        zvokDotik = Date.now();
        o.textContent = r.value + " %";
        clearTimeout(zam);
        zam = setTimeout(function () { klic("zvokGlasnostPrograma", [pr.id, parseInt(r.value, 10)]); }, 120);
      });
      var u = el("button", "gumb-utisaj" + (pr.utisan ? " utisan" : ""), svg(pr.utisan ? "utisan" : "zvok"));
      u.title = t("utisaj");
      u.addEventListener("click", function () { klic("zvokUtisajProgram", [pr.id, !pr.utisan]).then(nalozZvok); });
      var s = el("select");
      s.title = t("zvokIzhodPrograma");
      izbire.forEach(function (i) {
        var op = el("option", "", ubezi(i[1]));
        op.value = i[0];
        if (i[0] === pr.izhod) op.selected = true;
        s.appendChild(op);
      });
      s.addEventListener("change", function () {
        klic("zvokPremakniProgram", [pr.id, s.value]).then(function (ok) { if (!ok) obvesti(t("niUspelo")); s.blur(); nalozZvok(); });
      });
      v.appendChild(r); v.appendChild(o); v.appendChild(u);
      if (izbire.length > 1) v.appendChild(s);
      p.appendChild(v);
    });
    $("blokZvokProgrami").hidden = !z.programi.length;
    // Vhod
    var vh = $("zvokVhodi");
    vh.innerHTML = "";
    z.vhodi.forEach(function (i) {
      var v = zvokVrstica(IKONA_ZVOKA[i.vrsta] || "mikrofon", i.ime, i.podnapis, i.privzeti, i.privzeti ? el("span", "znacka", ubezi(t("vUporabi"))) : null);
      v.addEventListener("click", function () {
        if (i.privzeti) return;
        klic("zvokVhod", [i.id]).then(function (ok) { if (!ok) obvesti(t("niUspelo")); nalozZvok(); });
      });
      vh.appendChild(v);
    });
    var gv = $("zvokGlasnostVhoda");
    gv.innerHTML = "";
    var vhod = z.vhodi.filter(function (i) { return i.privzeti; })[0];
    if (vhod) {
      gv.appendChild(zvokDrsnik("mikrofon", "mikrofon", vhod.glasnost, vhod.utisan,
        function (v) { klic("zvokGlasnostVhoda", [vhod.id, v]); },
        function (u) { klic("zvokUtisajVhod", [vhod.id, u]).then(nalozZvok); }));
    }
    $("blokZvokVhod").hidden = !z.vhodi.length;
    $("gumbZvokNapredno").hidden = !z.napredno;
  }

  // ------------------------------------------------------------------ nastavitve
  // Nastavitve sistema (lastnik, 19. 10. 2026: »Nastavitve morajo odrazati celotne nastavitve operacijskega sistema«):
  // vsak modul Cinnamona, orodje Minta (o:) in plosca Nastavitev GNOME (p:), ki jih racunalnik RES ima - kaj ima, pove
  // core/os_sistem.razpolozljivo. Plosca GNOME, ki je Safeer se ne pozna, gre v Sistem z imenom iz sistema.
  var SKUPINE_NASTAVITEV = [
    ["g_videz", "paleta", ["backgrounds", "themes", "fonts", "effects", "desktop", "panel", "applets", "desklets", "extensions",
                          "o:urejevalnik-menija", "p:background", "p:ubuntu"]],
    ["g_zaslon", "zaslon", ["display", "nightlight", "screensaver", "sound", "power", "o:posnetek-zaslona",
                           "p:display", "p:sound", "p:power", "p:color"]],
    ["g_naprave", "naprave", ["o:omrezje", "o:bluetooth", "mouse", "keyboard", "gestures", "o:tiskalniki", "thunderbolt",
                             "p:wifi", "p:network", "p:wwan", "p:bluetooth", "p:mouse", "p:keyboard", "p:printers",
                             "p:wacom", "p:thunderbolt", "p:removable-media", "p:sharing"]],
    ["g_osebno", "uporabnik", ["user", "o:uporabniki", "o:prijavno-okno", "privacy", "online-accounts", "o:spletni-racuni",
                              "o:gesla", "notifications", "p:users", "p:user-accounts", "p:online-accounts", "p:privacy",
                              "p:lock", "p:location", "p:camera", "p:microphone", "p:usage", "p:diagnostics",
                              "p:notifications", "p:search", "p:applications"]],
    ["g_sistem", "drsniki", ["startup", "default", "calendar", "accessibility", "windows", "tiling", "workspaces", "hotcorner",
                            "general", "actions", "o:jezik", "o:vnosna-metoda", "info", "p:multitasking", "p:default-apps",
                            "p:universal-access", "p:region", "p:datetime", "p:system", "p:about", "p:info-overview"]],
    ["g_vzdrzevanje", "scit", ["o:posodobitve", "o:programska-oprema", "o:paketi", "o:viri-programov", "o:gonilniki",
                               "o:varnostne-kopije", "o:kopije-datotek", "o:pozarni-zid", "o:opravila", "o:diski",
                               "o:poraba-diska", "o:usb-slika", "o:usb-formatiranje", "o:sistemsko-porocilo",
                               "o:dobrodoslica", "o:terminal", "o:datoteke"]]
  ];
  var IKONA_NASTAVITVE = {
    backgrounds: "slika", themes: "paleta", fonts: "dokument", display: "zaslon", nightlight: "luna", screensaver: "zakleni",
    sound: "zvok", power: "napajanje", mouse: "miska", keyboard: "tipkovnica", user: "uporabnik", privacy: "scit",
    notifications: "zvonec", calendar: "ura", startup: "ponovno", "posodobitve": "ponovno", "programska-oprema": "programi",
    "gonilniki": "program", "varnostne-kopije": "ura", "kopije-datotek": "arhiv", "opravila": "drsniki", "diski": "disk",
    "omrezje": "ethernet", "bluetooth": "bluetooth", "tiskalniki": "tiskalnik", "terminal": "program", "datoteke": "mapa",
    "posnetek-zaslona": "slika", "jezik": "splet", "viri-programov": "arhiv", "sistemsko-porocilo": "dokument",
    windows: "namizje", workspaces: "programi", desktop: "namizje", panel: "namizje", accessibility: "uporabnik",
    info: "info", tiling: "programi", "online-accounts": "splet", "poraba-diska": "disk", "vnosna-metoda": "tipkovnica",
    "paketi": "arhiv", "uporabniki": "uporabnik", "prijavno-okno": "zakleni", "pozarni-zid": "scit", "spletni-racuni": "splet",
    "gesla": "zakleni", "urejevalnik-menija": "seznam", "usb-slika": "disk", "usb-formatiranje": "disk", "dobrodoslica": "domov",
    "p:wifi": "wifi", "p:network": "ethernet", "p:wwan": "telefon", "p:bluetooth": "bluetooth", "p:display": "zaslon",
    "p:sound": "zvok", "p:power": "napajanje", "p:color": "paleta", "p:background": "slika", "p:ubuntu": "namizje",
    "p:mouse": "miska", "p:keyboard": "tipkovnica", "p:printers": "tiskalnik", "p:wacom": "uredi", "p:sharing": "povezava",
    "p:users": "uporabnik", "p:user-accounts": "uporabnik", "p:online-accounts": "splet", "p:privacy": "scit", "p:lock": "zakleni",
    "p:location": "splet", "p:camera": "video", "p:microphone": "mikrofon", "p:usage": "ura", "p:notifications": "zvonec",
    "p:search": "isci", "p:applications": "programi", "p:multitasking": "programi", "p:default-apps": "programi",
    "p:universal-access": "uporabnik", "p:region": "splet", "p:datetime": "ura", "p:system": "drsniki", "p:about": "info",
    "p:info-overview": "info", "p:removable-media": "disk", "p:thunderbolt": "povezava", "p:diagnostics": "dokument"
  };
  // Dodatne kljucne besede (vse jezike hkrati), da iskanje najde vnos po besedi, ki jo ljudje res vpisejo: »wifi« najde
  // omrezje (preizkus 19. 10. 2026: »wifi« ni nasel nicesar, ceprav polje za primer navaja Wi-Fi).
  var KLJUCNE_NASTAVITEV = {
    "o:omrezje": "wifi wi-fi wlan wireless brezzicno brezžično internet ethernet lan vpn",
    "p:wifi": "wifi wi-fi wlan wireless brezzicno brezžično internet", "p:network": "ethernet lan vpn proxy internet",
    "o:bluetooth": "bt slusalke slušalke headphones", "sound": "zvok audio glasnost volume", "display": "monitor resolution locljivost ločljivost",
    "o:tiskalniki": "printer tiskalnik", "power": "baterija battery napajanje spanje sleep"
  };
  // Kljuc besedila za vnos: modul »m_<id>«, orodje »o_<id>«, plosca GNOME »p_<id>«.
  function kljucNastavitve(k) {
    return k.indexOf("o:") === 0 ? "o_" + k.slice(2) : k.indexOf("p:") === 0 ? "p_" + k.slice(2) : "m_" + k;
  }
  function imaBesedilo(kljuc) { return !!((BESEDILA_OS[jezik] && BESEDILA_OS[jezik][kljuc]) || BESEDILA_OS.en[kljuc]); }
  function seznamNastavitev() {
    var r = (S.zacetek && S.zacetek.razpolozljivo) || { moduli: [], orodja: [] };
    var imena = r.imena || {}, izhod = [], znani = {};
    SKUPINE_NASTAVITEV.forEach(function (g) {
      var elementi = [];
      g[2].forEach(function (k) {
        znani[k] = 1;
        var vrsta = k.indexOf("o:") === 0 ? "o" : k.indexOf("p:") === 0 ? "p" : "m", kljuc = vrsta === "m" ? k : k.slice(2);
        var seznam = vrsta === "o" ? r.orodja : vrsta === "p" ? r.plosce : r.moduli;
        if (!seznam || seznam.indexOf(kljuc) < 0) return;
        var b = kljucNastavitve(k);
        elementi.push({ modul: vrsta === "p" ? k : kljuc, ime: t(b), en: BESEDILA_OS.en[b] || "", kljucne: KLJUCNE_NASTAVITEV[k] || "",
                        ikona: IKONA_NASTAVITVE[vrsta === "p" ? k : kljuc] || g[1] });
      });
      if (g[0] === "g_sistem") {
        // Plosce, ki jih Safeer se ne pozna (nova razlicica GNOME): ime iz sistema, ne mrtev gumb.
        (r.plosce || []).forEach(function (p) {
          var k = "p:" + p, ime = imaBesedilo("p_" + p) ? t("p_" + p) : (imena[k] && imena[k].ime);
          if (znani[k] || !ime) return;
          elementi.push({ modul: k, ime: ime, en: "", kljucne: (imena[k] && imena[k].kljucne) || "", ikona: "drsniki" });
        });
      }
      if (elementi.length) izhod.push({ naslov: t(g[0]), elementi: elementi });
    });
    return izhod;
  }
  function odpriNastavitev(n) {
    // Omrezje ima Safeer OS svojo stran; Mintovo okno (ali GNOME) ostane pod »Napredno«.
    if (n.modul === "omrezje" || n.modul === "p:network" || n.modul === "p:wifi") { pojdi("omrezje"); return; }
    // Zvok ima Safeer OS svojo stran (izhodi, programi, naprave v Linku); Mintovo okno je pod »Napredno«.
    if (n.modul === "sound" || n.modul === "p:sound") { pojdi("zvok"); return; }
    obvesti(t("odpiram", { ime: n.ime }));
    klic("nastavitve", [n.modul]).then(function (ok) { if (!ok) obvesti(t("niUspelo")); });
  }

  // ---- iskanje po Nastavitvah (lastnik, 19. 10. 2026): vsaka nastavitev - Safeer OS, Ščit, deli Safeerja in sistem - je
  // dosegljiva po imenu. Iskanje gleda ime in opis v jeziku vmesnika, angleško ime in ključne besede sistema; skupina, ki
  // ji ustreza naslov, ostane cela. Stikala, ki jih skrije logika strani (hidden), ostanejo skrita.
  // .drsnik: glasnost in svetlost v Hitrih nastavitvah (preizkus na testnem PC 19. 10. 2026: »wifi« je pokazal »ni nastavitve«
  // in hkrati Glasnost, ker drsnik iskanje ni skrilo).
  var NASTAVITVE_ELEMENTI = ".stikalo, .nastavitev, .drsnik, [data-iskanje-blok]";
  function besediloZaIskanje(e) {
    var deli = [e.textContent || "", e.getAttribute("data-kljucne") || "", e.getAttribute("aria-label") || ""];
    if (e.dataset && e.dataset.nastavitev) deli.push(BESEDILA_OS.en[e.dataset.nastavitev] || "", BESEDILA_OS.en[e.dataset.nastavitev + "Pod"] || "");
    e.querySelectorAll("[data-t]").forEach(function (x) { deli.push(BESEDILA_OS.en[x.getAttribute("data-t")] || ""); });
    return deli.join(" ");
  }
  function filtrirajNastavitve() {
    var polje = $("nastavitveIskanje"), r = $("r-nastavitve");
    if (!polje || !r) return;
    var niz = polje.value.trim(), zadetkov = 0, naslov = null, naslovUstreza = false, vSkupini = 0;
    r.classList.toggle("isce", !!niz);
    function zakljuci() { if (naslov) naslov.classList.toggle("ni-zadetek", !!niz && !vSkupini); }
    r.querySelectorAll("h2, " + NASTAVITVE_ELEMENTI).forEach(function (e) {
      if (e.tagName === "H2") {
        zakljuci();
        naslov = e; vSkupini = 0;
        naslovUstreza = !!niz && window.SafeerIskanje.ujemaBesede(e.textContent + " " + (BESEDILA_OS.en[e.getAttribute("data-t")] || ""), niz);
        return;
      }
      var vBloku = e.parentElement && e.parentElement.closest("[data-iskanje-blok]");
      if (vBloku) return;                        // blok (npr. Scit) se iskanju kaze ali skrije v celoti
      var ustreza = !niz || naslovUstreza || window.SafeerIskanje.ujemaBesede(besediloZaIskanje(e), niz);
      e.classList.toggle("ni-zadetek", !ustreza);
      if (ustreza && !e.hidden) { vSkupini++; zadetkov++; }
    });
    zakljuci();
    var prazno = $("nastavitveNiZadetkov");
    if (prazno) { prazno.hidden = !niz || zadetkov > 0; prazno.textContent = t("nastavitveNiZadetkov", { niz: niz }); }
  }
  function prvaNajdenaNastavitev() {
    var vidni = Array.prototype.filter.call(document.querySelectorAll("#r-nastavitve .stikalo, #r-nastavitve .nastavitev"),
      function (e) { return !e.hidden && !e.classList.contains("ni-zadetek") && e.offsetParent !== null && !e.disabled; });
    // Najprej vnos, ki ustreza sam: skupina, ki ustreza po naslovu (»Zaslon in zvok«), ostane cela, a »zvok« je Zvok.
    var niz = ($("nastavitveIskanje") || {}).value || "";
    return vidni.filter(function (e) { return window.SafeerIskanje.ujemaBesede(besediloZaIskanje(e), niz.trim()); })[0] || vidni[0] || null;
  }
  function poveziIskanjeNastavitev() {
    var polje = $("nastavitveIskanje");
    if (!polje) return;
    polje.addEventListener("input", filtrirajNastavitve);
    polje.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && polje.value) { e.preventDefault(); e.stopPropagation(); polje.value = ""; filtrirajNastavitve(); }
      // Enter odpre najdeno nastavitev; stikala in dejanja (Wi-Fi, beta kanal, posodobitev, nazaj v Mint) ne sprozi -
      // fokus gre nanje, potrdi jih uporabnik (pregled 19. 10. 2026: »wifi« + Enter je izklopil Wi-Fi).
      else if (e.key === "Enter") { var p = prvaNajdenaNastavitev(); if (p) { e.preventDefault(); if (p.classList.contains("nastavitev")) p.click(); else p.focus(); } }
      else if (e.key === "ArrowDown") { var q = prvaNajdenaNastavitev(); if (q) { e.preventDefault(); q.focus(); } }
    });
  }
  // ---- Safeer Agent v Nastavitvah (core/agent/nastavitve.py): naslov modela, stanje, izklop, trajanje seje. Stanje je
  // vedno izmerjeno (agentDosegljivost) - »dosegljiv« samo, ce je streznik res odgovoril.
  var AG = { stanje: null, preverjam: 0 };
  function minuteAgenta(m) { return m === 0 ? t("agentNeomejeno") : m === 60 ? t("agentUra") : t("agentMin", { n: m }); }
  function narisiAgenta(st, dosegljivost) {
    if (!$("blokAgent") || !st) return;
    AG.stanje = st;
    var vnos = $("agentNaslovVnos"), stikalo = $("stikaloAgent"), izbira = $("agentTrajanje");
    stikalo.setAttribute("aria-checked", st.vklopljen ? "true" : "false");
    if (document.activeElement !== vnos) vnos.value = st.okolje || st.naslov || st.neveljaven_naslov || "";
    vnos.disabled = !!st.okolje;
    // Shranjen naslov, ki ga ta razlicica ne sprejme vec (npr. http:// zunaj domacega omrezja): pokazi razlog.
    if (!st.okolje && st.napaka_naslova) agentNapaka(st.napaka_naslova);
    $("agentNaslovNamig").textContent = st.okolje ? t("agentOkolje") : t("agentNaslovNamig");
    izbira.innerHTML = "";                // vedno v jeziku vmesnika (jezik se lahko spremeni med delom)
    (st.trajanja || []).forEach(function (m) { var o = el("option", "", ubezi(minuteAgenta(m))); o.value = String(m); izbira.appendChild(o); });
    izbira.value = String(st.trajanje);
    var napis = $("agentStanje");
    if (!st.vklopljen) napis.textContent = t("agentStIzklopljen");
    else if (!(st.okolje || st.naslov)) napis.textContent = t("agentStNiNaslova");
    else if (dosegljivost === "preverjam") napis.textContent = t("agentStPreverjam");
    else if (dosegljivost && dosegljivost.dosegljiv) napis.textContent = dosegljivost.model ? t("agentStDosegljivModel", { model: dosegljivost.model }) : t("agentStDosegljiv");
    else if (dosegljivost && dosegljivost.napaka === "kljuc") napis.textContent = t("agentStKljuc");
    else if (dosegljivost) napis.textContent = t("agentStNedosegljiv");
  }
  function preveriAgenta() {
    var st = AG.stanje;
    if (!st || !st.vklopljen || !(st.okolje || st.naslov)) { narisiAgenta(st); return; }
    var moj = ++AG.preverjam;
    narisiAgenta(st, "preverjam");
    klic("agentDosegljivost").then(function (d) { if (moj === AG.preverjam) narisiAgenta(AG.stanje, d || { dosegljiv: false }); },
      function () { if (moj === AG.preverjam) narisiAgenta(AG.stanje, { dosegljiv: false }); });
  }
  function nalozAgenta() {
    if (!$("blokAgent") || !most) return;
    klic("agentStanje").then(function (st) { narisiAgenta(st); preveriAgenta(); }, function () {});
  }
  function agentNapaka(koda) {
    var p = $("agentNapaka");
    p.hidden = !koda;
    p.textContent = koda ? t("agentNapaka_" + koda) : "";
  }
  function agentShranjeno(r) {
    if (!r) { obvesti(t("niUspelo")); return; }
    if (r.ok === false) { agentNapaka(r.napaka || "naslov"); return; }
    agentNapaka("");
    S.agent = { na_voljo: !!r.na_voljo }; lupaUredi(); narisiBliznjice();
    narisiAgenta(r); preveriAgenta();
  }
  function poveziAgenta() {
    if (!$("blokAgent")) return;
    $("agentObrazec").addEventListener("submit", function (e) {
      e.preventDefault();
      klic("agentNastavi", [$("agentNaslovVnos").value]).then(function (r) {
        agentShranjeno(r);
        if (r && r.ok) obvesti(t(r.naslov ? "agentShranjeno" : "agentIzbrisano"));
      }, function () { obvesti(t("niUspelo")); });
    });
    $("agentNaslovVnos").addEventListener("input", function () { agentNapaka(""); });
    $("agentPreveri").addEventListener("click", preveriAgenta);
    $("stikaloAgent").addEventListener("click", function () {
      var b = $("stikaloAgent"), nov = b.getAttribute("aria-checked") !== "true";
      b.setAttribute("aria-checked", nov ? "true" : "false");
      klic("agentVklop", [nov]).then(agentShranjeno, function () { b.setAttribute("aria-checked", nov ? "false" : "true"); obvesti(t("niUspelo")); });
    });
    $("agentTrajanje").addEventListener("change", function () {
      klic("agentTrajanje", [parseInt($("agentTrajanje").value, 10)]).then(agentShranjeno, function () { obvesti(t("niUspelo")); });
    });
  }

  // ---- Bliznjice na tipkovnici (Nastavitve): samo tiste, ki v tem oknu in na namizju Safeer OS res delujejo.
  function narisiBliznjice() {
    var dl = $("bliznjice");
    if (!dl) return;
    var vrstice = [["Ctrl+K", "blzLupa"], ["Aa", "blzTipkaj"], ["↑ ↓ · Enter", "blzZadetki"], ["Shift+Enter", "blzSplet"]];
    if (agentNaVoljo()) vrstice.push(["Ctrl+Enter", "blzAgent"]);
    vrstice.push(["Ctrl+B", "blzVrstica"], ["Ctrl+Shift+B", "blzMediji"], ["Esc", "blzEsc"], ["F11", "blzCelZaslon"]);
    if (!EN_RAZDELEK) vrstice.push(["Super+Tab", "blzProstori"], ["Super+Alt+← / →", "blzProstoriSosednji"]);
    dl.innerHTML = "";
    vrstice.forEach(function (v) {
      var d = el("div", "bliznjica");
      d.setAttribute("data-iskanje-blok", "");
      d.appendChild(el("dt", "", v[0].split(" · ").map(function (k) { return "<kbd>" + ubezi(k === "Aa" ? t("blzCrke") : k) + "</kbd>"; }).join(" ")));
      d.appendChild(el("dd", "", ubezi(t(v[1]))));
      d.setAttribute("data-kljucne", BESEDILA_OS.en[v[1]] || "");
      dl.appendChild(d);
    });
    filtrirajNastavitve();
  }

  // ------------------------------------------------------------------ posodobitve (safeer.si/os/razlicice.json)
  S.posodobitve = { stanje: null, zanka: 0 };
  function narisiKanal(kanal) {
    // Stikalo kaze kanal, ki ga je shranil Safeer OS (ne zeljenega); med shranjevanjem ga ne prepisemo.
    var b = $("stikaloBeta");
    if (!b || !kanal || b.getAttribute("aria-busy") === "true") return;
    b.setAttribute("aria-checked", kanal === "beta" ? "true" : "false");
  }
  function preklopiBeto() {
    var b = $("stikaloBeta");
    if (!b || b.getAttribute("aria-busy") === "true") return;
    var nov = b.getAttribute("aria-checked") !== "true";
    b.setAttribute("aria-busy", "true");
    b.setAttribute("aria-checked", nov ? "true" : "false");
    klic("posodobitveKanal", [nov ? "beta" : "stabilno"]).then(function (r) {
      b.removeAttribute("aria-busy");
      narisiKanal(r && r.kanal);
      nalozPosodobitve(true);   // takoj pokaze, kaj je v izbranem kanalu na voljo (namesti se samo z gumbom)
    }).catch(function () {
      b.removeAttribute("aria-busy");
      b.setAttribute("aria-checked", nov ? "false" : "true");
      obvesti(t("niUspelo"));
    });
  }
  function narisiPosodobitve(st) {
    S.posodobitve.stanje = st;
    if (st) narisiKanal(st.kanal);
    var fp = $("gumbFlatpak");
    if (fp) { fp.hidden = !(st && st.flatpak_preklop) || !!(st.posodabljanje && st.posodabljanje.tece); }
    var naslov = $("posodobitveNaslov"), pod = $("posodobitvePod"), gumb = $("gumbPosodobi");
    if (!naslov) return;
    var p = st && st.posodabljanje;
    if (p && p.tece) {
      naslov.textContent = p.faza === "namescanje" ? t("posodobitevNamescam") : t("posodobitevPrenasam", { ime: p.sporocilo || "", odstotek: p.odstotek || 0 });
      pod.textContent = "";
      gumb.disabled = true;
      return;
    }
    gumb.disabled = false;
    if (p && p.faza === "koncano") { naslov.textContent = t("posodobitevKoncano", { opis: p.sporocilo || "" }); pod.textContent = ""; return; }
    if (p && p.faza === "napaka" && p.sporocilo !== "prekinjeno") { naslov.textContent = t("posodobitevNapaka", { napaka: p.sporocilo || "" }); pod.textContent = t("posodobitevNajnovejsaPod"); return; }
    if (st && st.nove && st.nove.length) {
      naslov.textContent = t("posodobitevNaVoljo", { opis: st.opis });
      var novo = st.novo && (st.novo[jezik] || st.novo.en) ? (st.novo[jezik] || st.novo.en) + " " : "";
      // Brez paketa za ta nacin (st.rocno, AppImage od 1.0.132): povemo, kje je nova razlicica, gumb odpre stran.
      pod.textContent = novo + (st.rocno ? t(st.nacin === "appimage" ? "posodobitevAppImagePod" : "posodobitevRocnoPod") :
        (st.nacin === "deb" || st.nacin === "flatpak+deb" || st.nacin === "windows") ? t("posodobitevNaVoljoPod") : (st.nacin === "flatpak" || st.nacin === "appimage") ? t("posodobitevNaVoljoFlatpak") : t("posodobitevRocnoPod"));
      return;
    }
    naslov.textContent = t("posodobitevNajnovejsa", { v: (st && st.nasa) || (S.zacetek && S.zacetek.razlicica) || "" });
    // Beta izklopljena, a tece beta: povemo, da ostane, dokler stabilna ne dohiti (nikoli zamenjava na starejso).
    pod.textContent = st && st.napaka ? t("posodobitevNapaka", { napaka: st.napaka }) :
      (st && st.kanal === "beta") ? t("posodobitevNajnovejsaBetaPod") :
      (st && st.na_beti) ? t("posodobitevNaBetiPod") : t("posodobitevNajnovejsaPod");
  }
  function nalozPosodobitve(vsiljeno) {
    if (vsiljeno) { $("posodobitveNaslov").textContent = t("posodobitevPreverjam"); $("posodobitvePod").textContent = ""; }
    klic("posodobitveStanje", [!!vsiljeno]).then(narisiPosodobitve, function () { narisiPosodobitve(S.posodobitve.stanje); });
  }
  function posodobitveZanka() {
    if (S.posodobitve.zanka) return;
    S.posodobitve.zanka = setInterval(function () {
      klic("posodobitveStanje", [false]).then(function (st) {
        narisiPosodobitve(st);
        if (!(st.posodabljanje && st.posodabljanje.tece)) { clearInterval(S.posodobitve.zanka); S.posodobitve.zanka = 0; if (st.posodabljanje && st.posodabljanje.faza === "koncano") $("domPosodobitev").hidden = true; }
      }).catch(function () {});
    }, 1000);
  }
  function flatpakPreklop() {
    var st = S.posodobitve.stanje || {};
    klic("flatpakPreklop").then(function (r) {
      if (r && r.ok) { narisiPosodobitve({ nasa: st.nasa, nove: st.nove || [], opis: st.opis, nacin: st.nacin, posodabljanje: { tece: true, faza: "prenos", odstotek: 0, sporocilo: "" } }); posodobitveZanka(); }
      else nalozPosodobitve(true);
    }).catch(function () { obvesti(t("niUspelo")); });
  }
  function posodobi() {
    var st = S.posodobitve.stanje;
    if (!st || !st.nove || !st.nove.length) { nalozPosodobitve(true); return; }
    if (st.rocno || (st.nacin !== "deb" && st.nacin !== "flatpak+deb" && st.nacin !== "flatpak" && st.nacin !== "appimage" && st.nacin !== "windows")) { klic("splet", [st.stran || "https://safeer.si/os/"]); return; }
    klic("posodobi").then(function (r) {
      if (r && r.ok) { narisiPosodobitve({ nasa: st.nasa, nove: st.nove, opis: st.opis, nacin: st.nacin, posodabljanje: { tece: true, faza: "prenos", odstotek: 0, sporocilo: "" } }); posodobitveZanka(); }
      else if (r && r.koda === "rocno") klic("splet", [r.stran || "https://safeer.si/os/"]);
      else nalozPosodobitve(true);
    }).catch(function () { obvesti(t("niUspelo")); });
  }
  // Z domacega zaslona na gumb Posodobitve v Nastavitvah. Nastavitve se narisejo v vec korakih (teme, hitre
  // nastavitve, brskalnik, viri), zato gumb v pogled premaknemo veckrat - sicer ga pozneje nalozena vsebina
  // odrine in uporabnik pristane sredi strani brez gumba.
  function naPosodobitve() {
    pojdi("nastavitve");
    [0, 250, 700, 1500].forEach(function (ms) {
      setTimeout(function () {
        var g = $("gumbPosodobi");
        if (!g || S.razdelek !== "nastavitve") return;
        if (ms === 0) { try { g.focus({ preventScroll: true }); } catch (e) { g.focus(); } }
        g.scrollIntoView({ block: "center" });
      }, ms);
    });
  }
  function pokaziPosodobitevDoma(st) {
    // Tiha opomba na domacem zaslonu, dokler uporabnik nove razlicice ne namesti (Nastavitve -> Posodobitve).
    S.posodobitve.stanje = st;
    var b = $("domPosodobitev");
    if (!b) return;
    b.hidden = !(st && st.nove && st.nove.length);
    if (!b.hidden) $("domPosodobitevNaslov").textContent = t("posodobitevNaVoljo", { opis: st.opis });
  }

  function narisiNastavitve() {
    kontrole($("hitreNastavitve"), false);
    $("stikaloCelozaslonsko").setAttribute("aria-checked", S.zacetek && S.zacetek.celozaslonsko ? "true" : "false");
    $("stikaloSamozagon").setAttribute("aria-checked", S.zacetek && S.zacetek.samozagon ? "true" : "false");
    // Safeer Cinnamon: Safeer OS je vedno v oknu, ob delovni povrsini ga ob prijavi zazene seja safeer-cinnamon.
    // Wayland (GNOME na Ubuntu …): celozaslonskega namizja pod okni ni - Safeer OS je vedno v oknu.
    $("stikaloCelozaslonsko").hidden = !!(S.zacetek && (S.zacetek.safeerCinnamon || S.zacetek.wayland));
    $("stikaloSamozagon").hidden = !!(S.zacetek && S.zacetek.samozagonNamizje);
    // Safeer od vklopa (zagonski in prijavni zaslon): samo, ce je namescen paket safeer-cinnamon s pomocnikom.
    var odVklopa = S.zacetek && S.zacetek.odVklopa;
    $("stikaloOdVklopa").hidden = !(odVklopa && odVklopa.na_voljo);
    $("stikaloOdVklopa").setAttribute("aria-checked", odVklopa && odVklopa.vklopljeno ? "true" : "false");
    narisiNastavitveDelov();
    nalozAgenta();
    narisiBliznjice();
    var cilj = $("skupineNastavitev");
    cilj.innerHTML = "";
    seznamNastavitev().forEach(function (g) {
      cilj.appendChild(el("h2", "", ubezi(g.naslov)));
      var m = el("div", "nastavitve-mreza");
      g.elementi.forEach(function (n) {
        var b = el("button", "nastavitev", svg(n.ikona) + "<span>" + ubezi(n.ime) + "</span>");
        b.type = "button";
        // Iskanje po Nastavitvah najde vnos tudi po angleskem imenu in kljucnih besedah sistema.
        b.setAttribute("data-kljucne", [n.en, n.kljucne || "", n.modul.replace(/^p:/, "")].join(" "));
        b.addEventListener("click", function () { odpriNastavitev(n); });
        m.appendChild(b);
      });
      cilj.appendChild(m);
    });
    filtrirajNastavitve();
    narisiORacunalniku();
    $("oSistemu").textContent = t("razlicica", { v: (S.zacetek && S.zacetek.razlicica) || "" }) +
      (S.zacetek ? " · " + S.zacetek.racunalnik : "");
    if (!S.stanje) klic("stanje").then(function (s) { narisiStanje(s); kontrole($("hitreNastavitve"), false); }, function () {});
  }

  // Nastavitve delov Safeerja na enem mestu (lastnik, 15. 10. 2026: »vse je en proces«): kar je bilo prej samo v
  // pladnju Controla, v meniju Spleta ali v desnem kliku na namizje. Most pove, kateri del tece; skupine dela, ki ne
  // tece, ne pokazemo (brez mrtvih gumbov). Stikala kazejo stanje, ki ga vrne Control (ne zeljenega).
  function narisiNastavitveDelov() {
    var cilj = $("nastavitveDelov");
    if (!cilj) return;
    klic("nastavitveDelov").then(function (d) {
      cilj.innerHTML = "";
      if (!d) return;
      function skupina(naslov, gumbi) {
        cilj.appendChild(el("h2", "", ubezi(naslov)));
        var m = el("div", "hitre");
        gumbi.forEach(function (g) { m.appendChild(g); });
        cilj.appendChild(m);
      }
      function gumb(ikona, kljuc, preklop, ob) {
        var b = el("button", "stikalo", svg(ikona) + "<div><span>" + ubezi(t(kljuc)) + "</span><small>" +
          ubezi(t(kljuc + "Pod")) + "</small></div>" + (preklop === null ? "" : "<i></i>"));
        b.dataset.nastavitev = kljuc;
        if (preklop !== null) {
          b.setAttribute("role", "switch");
          b.setAttribute("aria-checked", preklop ? "true" : "false");
        }
        b.addEventListener("click", function () { ob(b); });
        return b;
      }
      function stikalo(ikona, kljuc, ime, stanje) {
        return gumb(ikona, kljuc, !!stanje, function (b) {
          var nov = b.getAttribute("aria-checked") !== "true";
          b.setAttribute("aria-checked", nov ? "true" : "false");
          klic("nastavitevDela", [ime, nov]).then(function (zdaj) {
            if (typeof zdaj === "boolean") b.setAttribute("aria-checked", zdaj ? "true" : "false");
          }).catch(function () { b.setAttribute("aria-checked", nov ? "false" : "true"); });
        });
      }
      var c = d.control;
      if (c) {
        skupina(t("gNapraveLink"), [
          gumb("mapa", "ndMape", null, function () { klic("nastavitevDela", ["mape"]); }),
          stikalo("disk", "ndVesDisk", "vesDisk", c.vesDisk),
          stikalo("programi", "ndProgrami", "programi", c.programi),
          stikalo("zaslon", "ndZaslon", "zaslon", c.zaslon),
          stikalo("naprave", "predajaStikalo", "predajanje", c.predajanje)
        ].concat(
          // Pod Safeer Cinnamon Control zazene namizje v istem procesu - lastnega samozagona ni (en proces).
          "samozagon" in c ? [stikalo("ponovno", "ndSamozagon", "samozagon", c.samozagon)] : []));
      }
      if (d.splet) skupina(t("gSplet"), [gumb("splet", "ndSplet", null, function () { klic("nastavitevDela", ["splet"]); })]);
      if ("sporocila" in d) skupina(t("sporocila"), [stikalo("sporocila", "ndSporocila", "sporocila", d.sporocila)]);
      if (d.namizje) skupina(t("gNamizje"), [gumb("paleta", "ndNamizje", null, function () { klic("nastavitevDela", ["namizje"]); }),
        // Iskalna lupa na namizju (lastnik, 19. 10. 2026): zlozena, dokler je ne uporabis (core/priljubljeno »lupa«).
        stikalo("isci", "ndLupa", "lupa", d.lupa !== "razsirjena")]);
      filtrirajNastavitve();
    }, function () { cilj.innerHTML = ""; });
  }

  // ------------------------------------------------------------------ napajanje
  var potrjuje = null, potrjujeCas = 0;
  function odpriNapajanje() {
    zapriSloje();
    potrjuje = null;
    narisiNapajanje();
    $("slojNapajanje").classList.add("viden");
  }
  function narisiNapajanje() {
    var p = $("napajanje");
    p.innerHTML = "";
    var mint = el("button", "", svg("namizje") + "<span>" + ubezi(t("nazajVMint")) + "</span>");
    mint.addEventListener("click", odpriMint);
    p.appendChild(mint);
    [["zakleni", "zakleni", false], ["spanje", "luna", false], ["odjava", "odjava", true],
     ["ponovni-zagon", "ponovno", true], ["izklop", "napajanje", true]].forEach(function (d) {
      var kljuc = d[0] === "ponovni-zagon" ? "ponovniZagon" : d[0];
      var b = el("button", potrjuje === d[0] ? "potrdi" : "", svg(d[1]) + "<span>" +
        ubezi(potrjuje === d[0] ? t("potrdi") : t(kljuc)) + "</span>");
      b.addEventListener("click", function () {
        if (d[2] && potrjuje !== d[0]) {
          potrjuje = d[0];
          clearTimeout(potrjujeCas);
          potrjujeCas = setTimeout(function () { potrjuje = null; narisiNapajanje(); }, 4000);
          narisiNapajanje();
          return;
        }
        zapriSloje();
        klic("napajanje", [d[0]]);
      });
      p.appendChild(b);
    });
  }

  // ------------------------------------------------------------------ nazaj v Linux Mint
  // »Nazaj na Cinnamon« je vedno na voljo (lastnik, 17. 10. 2026): vrne tudi pult, dock in videz, ne samo zagon ob prijavi.
  function odpriMint() {
    zapriSloje();
    $("slojMint").classList.add("viden");
    setTimeout(function () { $("mintSamoTokrat").focus(); }, 30);
  }

  // Safeer OS iz menija po »Nazaj na Cinnamon«: enkrat vprasamo, ali naj se spet zaganja ob prijavi.
  function odpriVrnitev() {
    zapriSloje();
    $("slojVrnitev").classList.add("viden");
    setTimeout(function () { $("vrnitevDa").focus(); }, 30);
  }
  function odgovoriVrnitev(da) {
    if (S.zacetek) S.zacetek.vrnitev = false;
    zapriSloje();
    klic("vrniSafeerOs", [da]).then(function (ok) {
      if (!ok) return;
      if (S.zacetek) S.zacetek.samozagon = true;
      obvesti(t("vrVrnjeno"));
    }, function () { obvesti(t("niUspelo")); });
  }

  // ------------------------------------------------------------------ vodnik ob prvem zagonu
  // Lastnik, 17. 10. 2026: jezik, racuni, Scit, Safeer Link in konec; vsak korak je preskocljiv. Vodnik sam nicesar ne
  // obdeluje: prijave so obstojece (Splet, Medijski center), Scit je obstojeci blok #blokScit, ki ga za ta korak
  // premaknemo v vodnik, Link je prijavno okno Safeer Control (QR / koda).
  var JEZIKI_VODNIKA = [["sl", "Slovenščina"], ["en", "English"], ["de", "Deutsch"], ["es", "Español"], ["fr", "Français"], ["it", "Italiano"]];
  var KORAKI_VODNIKA = ["Jezik", "Racuni", "Scit", "Link", "Konec"];
  var vodnikKorak = -1, scitMesto = null;
  function odpriVodnik() {
    zapriSloje();
    vodnikKorak = 0;
    $("slojVodnik").classList.add("viden");
    narisiVodnik();
  }
  function vrniScitIzVodnika() {
    var b = $("blokScit");
    if (scitMesto && b.parentNode !== scitMesto.mapa) scitMesto.mapa.insertBefore(b, scitMesto.za);
  }
  function zapriVodnik() {
    if (vodnikKorak < 0) return;
    vodnikKorak = -1;
    vrniScitIzVodnika();
    $("slojVodnik").classList.remove("viden");
    if (S.zacetek) S.zacetek.vodnik = false;
    klic("vodnikKoncaj").catch(function () {});
  }
  function korakVodnika(premik) {
    vodnikKorak += premik;
    if (vodnikKorak >= KORAKI_VODNIKA.length) { zapriVodnik(); return; }
    narisiVodnik();
  }
  function narisiVodnik() {
    var k = KORAKI_VODNIKA[vodnikKorak], v = $("vodnikVsebina"), konec = k === "Konec";
    vrniScitIzVodnika();
    v.innerHTML = "";
    $("vodnikKorak").textContent = t("vdKorak", { n: vodnikKorak + 1, m: KORAKI_VODNIKA.length });
    $("vodnikNaslov").textContent = t("vd" + k + "Naslov");
    $("vodnikOpis").textContent = t("vd" + k + "Opis");
    $("vodnikNazaj").hidden = vodnikKorak === 0;
    $("vodnikPreskoci").hidden = konec;
    $("vodnikPreskoci").textContent = t(k === "Link" ? "vdPozneje" : "vdPreskoci");
    $("vodnikPreskociVse").hidden = konec;
    $("vodnikNaprej").textContent = t(konec ? "vdKoncaj" : "vdNaprej");
    var izbire = el("div", "vodnik-izbire");
    function gumb(besedilo, ob) {
      var g = el("button", "gumb", ubezi(besedilo)); g.type = "button"; g.addEventListener("click", ob); izbire.appendChild(g); return g;
    }
    if (k === "Jezik") {
      JEZIKI_VODNIKA.forEach(function (j) {
        var g = gumb(j[1], function () { izberiJezik(j[0]); });
        g.lang = j[0];
        g.classList.toggle("izbran", jezik === j[0]);
        g.setAttribute("aria-pressed", jezik === j[0] ? "true" : "false");
      });
    } else if (k === "Racuni") {
      gumb(t("vdYoutube"), function () { klic("splet", [YT_PRIJAVA, true]); cakajYtPrijavo(); });
      gumb(t("vdSpotify"), spPrijava);
      gumb(t("vdTwitch"), function () { klic("splet", [TW_PRIJAVA, true]); cakajTwitchPrijavo(); });
    } else if (k === "Scit") {
      var b = $("blokScit");
      if (!scitMesto) scitMesto = { mapa: b.parentNode, za: b.nextSibling };
      v.appendChild(b);
      nalozScit();
    } else if (k === "Link") {
      gumb(t("vdLinkPovezi"), function () { klic("prijava"); });
    } else {
      var deli = t("vdKonecUkaz").split("{ukaz}");
      v.appendChild(el("p", "drobno", ubezi(deli[0]) + "<code>safeer-os --nazaj-na-cinnamon</code>" + ubezi(deli[1] || "")));
    }
    if (izbire.childNodes.length) v.appendChild(izbire);
    setTimeout(function () {
      var izbran = v.querySelector(".gumb.izbran") || v.querySelector("button") || $("vodnikNaprej");
      izbran.focus();
    }, 30);
  }
  // Jezik iz vodnika velja takoj: to okno ga zamenja samo, druga okna in lupina QML dobijo dogodek »jezik«.
  function izberiJezik(j) {
    uporabiJezik(j);
    klic("nastaviJezik", [j]).catch(function () {});
  }
  function uporabiJezik(j) {
    if (!BESEDILA_OS[j] || j === jezik) return;
    jezik = j;
    if (S.zacetek) S.zacetek.jezik = j;
    prevedi();
    narisiDomov();
    if (S.razdelek === "nastavitve") narisiNastavitve();
    if (vodnikKorak >= 0) narisiVodnik();
  }

  // ------------------------------------------------------------------ iskanje
  var iskanjeZamik = 0, iskanjeMedijiZamik = 0, iskanjeStevec = 0, iskanjeDatotekNiz = "", ciljnoDatotekeZamik = 0;
  function ujemanje(besedilo, niz) {
    return SafeerIskanje.oceni(besedilo, niz);
  }
  function zadetek(ikonaEl, naslov, pod, ob) {
    var b = el("button", "zadetek");
    if (typeof ikonaEl === "string") b.innerHTML = svg(ikonaEl); else b.appendChild(ikonaEl);
    b.appendChild(el("div", "", "<b>" + ubezi(naslov) + "</b>" + (pod ? "<span>" + ubezi(pod) + "</span>" : "")));
    b.addEventListener("click", function () { zapriSloje(); ob(); });
    return b;
  }

  // ------------------------------------------------------------------ zdruzeni nabiralnik
  function naloziSporocila() {
    if (!most) { narisiSporocila(); return; }
    klic("sporocilaSeznam").then(function (p) {
      S.sporocilaSkupine = p.skupine || []; S.sporocilaKanali = p.kanali || []; S.sporocilaOznakeVse = p.oznake || []; S.slikeOd = p.slike_od || S.slikeOd || [];
      narisiSporocila(); uskladiOdprtPogovor(); odpriCakajociPogovor(); naloziOsnutke();
    }).catch(function () { narisiSporocila(); });
  }
  // Plosca sporocil na delovni povrsini (sporocila-plosca.html): klik na pogovor odpre okno Sporocila pri njem.
  function odpriCakajociPogovor() {
    var c = S.sporocilaOdpri; if (!c) return;
    S.sporocilaOdpri = null;
    (S.sporocilaSkupine || []).some(function (skupina) {
      return (skupina.pogovori || []).some(function (p) {
        if (p.kanal_id !== c.kanal || p.id !== c.id) return false;
        odpriPogovor(skupina.oseba, p); return true;
      });
    });
  }
  /* Znak kanala (prenova nabiralnika 16. 10. 2026): splosni znak po vrsti adapterja (core/sporocila/*.py), barva iz
     tokens.css (--kanal-*). Logotipov storitev ne risemo; ime kanala pove namig in bralnik zaslona. */
  var ZNAKI_KANALOV = { email: "eposta", telegram: "poslji", telegram_bot: "poslji", matrix: "matrix", safeer: "povezava",
                        chatwoot: "sporocilo" };
  function kanalIkona(vrsta) { return ZNAKI_KANALOV[vrsta] || "sporocila"; }
  function znakKanala(kanal, razred) {
    var k = kanal || {}, vrsta = ZNAKI_KANALOV[k.vrsta] ? k.vrsta : "drugo";
    return '<span class="znak-kanala ' + (razred || "") + '" data-vrsta="' + ubezi(vrsta) + '" title="' + ubezi(k.ime || "") +
      '" aria-hidden="true">' + svg(kanalIkona(k.vrsta)) + '</span>';
  }
  var BARVE_AVATARJA = ["splet", "slika", "video", "zvok", "dokument", "mapa", "arhiv", "naprava"];
  function barvaAvatarja(kljuc) { return "var(--vrsta-" + BARVE_AVATARJA[barvaIzImena(kljuc) % BARVE_AVATARJA.length] + ")"; }
  function avatarHtml(ime, kljuc) {
    return '<span class="avatar" aria-hidden="true" style="background:' + barvaAvatarja(kljuc || ime) + '">' + ubezi(zacetnice(ime)) + '</span>';
  }
  /* Cas v seznamu pogovorov: »zdaj«, »16 min«, danes ura, »vceraj«, ta teden dan, sicer datum (kot klepetalniki). */
  function relativniCas(cas, zdaj) {
    if (!cas) return "";
    var d = new Date(cas); if (isNaN(d.getTime())) return "";
    zdaj = zdaj || new Date();
    var lok = LOKALE[jezik] || jezik, min = Math.floor((zdaj.getTime() - d.getTime()) / 60000);
    if (min >= 0 && min < 1) return t("casZdaj");
    if (min >= 1 && min < 60) return t("casMin", { n: min });
    if (d.toDateString() === zdaj.toDateString()) return d.toLocaleTimeString(lok, { hour: "2-digit", minute: "2-digit" });
    var vceraj = new Date(zdaj.getFullYear(), zdaj.getMonth(), zdaj.getDate() - 1);
    if (d.toDateString() === vceraj.toDateString()) return t("casVceraj");
    var polnoc = new Date(zdaj.getFullYear(), zdaj.getMonth(), zdaj.getDate()).getTime();
    if (d.getTime() < polnoc && polnoc - d.getTime() < 6 * 86400000) return d.toLocaleDateString(lok, { weekday: "short" });
    return d.toLocaleDateString(lok, d.getFullYear() === zdaj.getFullYear() ? { day: "numeric", month: "short" }
      : { day: "numeric", month: "short", year: "numeric" });
  }
  function kratekCas(cas) {
    if (!cas) return "";
    var d = new Date(cas); if (isNaN(d.getTime())) return "";
    var lok = LOKALE[jezik] || jezik, danes = new Date();
    if (d.toDateString() === danes.toDateString()) return d.toLocaleTimeString(lok, { hour: "2-digit", minute: "2-digit" });
    return d.toLocaleDateString(lok, d.getFullYear() === danes.getFullYear() ? { day: "numeric", month: "short" }
      : { day: "numeric", month: "short", year: "numeric" });
  }
  function stanjeKanala(k) {
    var st = String(k.stanje || "");
    if (st === "napaka:geslo") return t("kanalVnesiGeslo");
    if (st === "napaka:prijava") return t("kanalPrijavaNi");
    if (st === "napaka:omrezje") return t("kanalNiDosegljiv");
    if (st.indexOf("napaka") === 0) return t("niUspelo");
    return "";
  }
  function narisiKanale() {
    var cilj = $("sporocilaKanali"); if (!cilj) return; cilj.innerHTML = "";
    cilj.setAttribute("aria-label", t("kanaliNaslov"));
    S.sporocilaKanali.forEach(function (k) {
      var izkl = k.vklopljen === false;
      var opis = izkl ? t("kanalIzklopljen") : stanjeKanala(k);
      var b = el("button", "kanal-cip" + (izkl ? " izklopljen" : opis ? " napaka" : ""));
      b.type = "button"; b.title = k.ime + (opis ? " · " + opis : "");
      // Napaka (geslo, omrezje) je vidna kot opozorilni znak; celo besedilo je v namigu in v urejanju kanala.
      b.innerHTML = znakKanala(k) + '<span class="kanal-ime">' + ubezi(k.ime) + "</span>" + (opis ? '<small class="kanal-opozorilo">!</small>' : "");
      if (opis) b.setAttribute("aria-label", b.title);
      b.addEventListener("click", function () { if (k.vrsta === "safeer" && !izkl) odpriPisiNapravi(); else odpriUrejanjeKanala(k); });
      b.addEventListener("contextmenu", function (e) { e.preventDefault(); odpriUrejanjeKanala(k); });
      cilj.appendChild(b);
    });
    narisiVgrajeneKanale(cilj);
  }
  /* Novo e-sporocilo in osnutki: osnutek ostane na tem racunalniku; poslje se sele ob kliku na Poslji. */
  function naloziOsnutke() {
    if (!most) return;
    klic("sporocilaOsnutki").then(function (o) { S.osnutki = o || []; narisiSporocila(); }).catch(function () {});
  }
  function narisiOsnutke(cilj) {
    var n = (S.sporocilaNiz || "").trim().toLowerCase();
    (S.osnutki || []).forEach(function (o) {
      if (n && ((o.za || "") + " " + (o.zadeva || "") + " " + (o.besedilo || "")).toLowerCase().indexOf(n) < 0) return;
      var b = el("button", "vrstica-pogovora"); b.type = "button";
      var kanal = (S.sporocilaKanali || []).filter(function (k) { return k.id === o.kanal_id; })[0] || { vrsta: "email", ime: t("osnutek") };
      b.innerHTML = vrsticaHtml({ ime: o.za || t("novoBrezPrejemnika"), kljuc: o.za || "", cas: o.cas, oznaka: t("osnutek"),
        predogled: (o.zadeva ? o.zadeva + " – " : "") + String(o.besedilo || "").slice(0, 160), kanal: kanal });
      b.addEventListener("click", function () { odpriNovo(o); });
      cilj.appendChild(b);
    });
    if (!cilj.children.length) cilj.appendChild(el("p", "prazno", ubezi(t("niOsnutkov"))));
  }
  function epostniKanali() {
    return (S.sporocilaKanali || []).filter(function (k) { return k.vrsta === "email"; });
  }
  function odpriNovo(osnutek) {
    zapriSloje();
    var o = osnutek || {}, kanali = epostniKanali(), sel = $("novoOd");
    S.novoOsnutek = o.id || "";
    sel.innerHTML = "";
    kanali.forEach(function (k) { var op = document.createElement("option"); op.value = k.id; op.textContent = k.ime; sel.appendChild(op); });
    if (o.kanal_id && kanali.some(function (k) { return k.id === o.kanal_id; })) sel.value = o.kanal_id;
    $("novoZa").value = o.za || ""; $("novoZadeva").value = o.zadeva || ""; $("novoBesedilo").value = o.besedilo || "";
    $("novoOdstrani").hidden = !S.novoOsnutek;
    S.priloge.novo = []; narisiPriloge("novo");
    // Osnutek s prilogami: datoteke, ki so se na racunalniku, so spet pod pismom (z aktualno velikostjo).
    if (Array.isArray(o.priloge) && o.priloge.length) {
      var osnutekId = S.novoOsnutek;
      klic("opisPrilog", [o.priloge]).then(function (p) { if (S.novoOsnutek === osnutekId) dodajPriloge("novo", p); }, function () {});
    }
    var napaka = $("novoNapaka");
    napaka.hidden = !!kanali.length; napaka.textContent = kanali.length ? "" : t("niEpostnegaKanala");
    $("slojNovo").classList.add("viden");
    (o.za ? $("novoBesedilo") : $("novoZa")).focus();
  }
  function podatkiNovega() {
    return { id: S.novoOsnutek || "", kanal_id: $("novoOd").value || "", za: $("novoZa").value.trim(),
             zadeva: $("novoZadeva").value.trim(), besedilo: $("novoBesedilo").value,
             priloge: S.priloge.novo.map(function (x) { return x.pot; }) };
  }
  function shraniNovoKotOsnutek() {
    klic("sporocilaShraniOsnutek", [podatkiNovega()]).then(function (o) {
      S.osnutki = o || []; zapriSloje(); obvesti(t("osnutekShranjen")); narisiSporocila();
    }).catch(function (e) { obvesti(typeof e === "string" && e ? e : t("niUspelo")); });
  }
  function posljiNovo(dogodek) {
    if (dogodek) dogodek.preventDefault();
    var d = podatkiNovega(), napaka = $("novoNapaka");
    if (!d.kanal_id) { napaka.hidden = false; napaka.textContent = t("niEpostnegaKanala"); return; }
    var priloge = S.priloge.novo.map(function (x) { return x.pot; });
    if (!d.besedilo.trim() && !priloge.length) { napaka.hidden = false; napaka.textContent = t("praznoSporocilo"); $("novoBesedilo").focus(); return; }
    if (prilogePrevelike("novo")) { napaka.hidden = false; napaka.textContent = t("priloge_prevelike"); return; }
    var gumb = $("obrazecNovo").querySelector('button[type="submit"]'); gumb.disabled = true;
    klic("sporocilaNovo", [d.kanal_id, d.za, d.zadeva, d.besedilo, d.id, priloge]).then(function (p) {
      gumb.disabled = false; S.priloge.novo = []; narisiPriloge("novo"); zapriSloje(); obvesti(t("sporociloPoslano"));
      posodobiSeznamIzOdgovora(p); naloziOsnutke();
    }).catch(function (e) {
      gumb.disabled = false; napaka.hidden = false; napaka.textContent = napakaSporocil(e);
    });
  }
  /* Safeer Chat: napisi napravi v Linku (telefon, tablica, TV, drug racunalnik). */
  function odpriPisiNapravi() {
    zapriSloje();
    var cilj = $("pisiNaprave"); cilj.innerHTML = "";
    cilj.appendChild(el("p", "drobno", ubezi(t("povezujem"))));
    $("slojPisi").classList.add("viden");
    klic("sporocilaNaprave").then(function (naprave) {
      cilj.innerHTML = "";
      if (!(naprave || []).length) { cilj.appendChild(el("p", "drobno", ubezi(t("niNapravKlepet")))); $("pisiPreklici").focus(); return; }
      naprave.forEach(function (n, i) {
        var b = el("button", "pogovor-vrstica");
        b.type = "button";
        b.innerHTML = '<span class="kanal-ikona">' + svg("povezava") + '</span><span><b>' + ubezi(n.ime || n.id) + '</b></span>';
        b.addEventListener("click", function () {
          klic("sporocilaZacni", [n.id, n.ime || ""]).then(function (p) {
            zapriSloje();
            S.sporocilaSkupine = p.skupine || []; S.sporocilaKanali = p.kanali || [];
            var najden = null, oseba = null;
            S.sporocilaSkupine.forEach(function (sk) { (sk.pogovori || []).forEach(function (x) {
              if (x.kanal_id === "safeer-link" && x.id === n.id) { najden = x; oseba = sk.oseba; } }); });
            narisiSporocila();
            if (najden) { odpriPogovor(oseba, najden); setTimeout(function () { $("sporocilaBesedilo").focus(); }, 30); }
          }).catch(function (e) { obvesti(typeof e === "string" ? e : t("niUspelo")); });
        });
        cilj.appendChild(b);
        if (i === 0) setTimeout(function () { b.focus(); }, 30);
      });
    }).catch(function () { cilj.innerHTML = ""; cilj.appendChild(el("p", "drobno", ubezi(t("niNapravKlepet")))); });
  }
  function odpriUrejanjeKanala(k) {
    zapriSloje(); S.urejaniKanal = k;
    $("kanalUrediNaslov").textContent = k.ime;
    $("kanalUrediOpis").textContent = stanjeKanala(k) || t("kanalPovezan");
    $("kanalUrediGeslo").value = ""; $("kanalUrediGeslo").hidden = k.vrsta !== "email" && k.vrsta !== "chatwoot";
    $("kanalUrediVklop").setAttribute("aria-checked", k.vklopljen === false ? "false" : "true");
    $("slojKanalUredi").classList.add("viden"); $("kanalUrediGeslo").focus();
  }
  function jeKlepet(vrsta) { return vrsta === "chatwoot" || vrsta === "safeer" || vrsta === "matrix" || vrsta === "telegram_bot"; }
  function zacetnice(ime) {
    var deli = String(ime || "").split(/\s+/).map(function (x) { return x.replace(/[^\p{L}\p{N}]/gu, ""); }).filter(Boolean);
    return deli.slice(0, 2).map(function (x) { return x.charAt(0).toUpperCase(); }).join("") || "?";
  }
  function pogovorUstreza(skupina, p) {
    var vrsta = (p.kanal || {}).vrsta || "";
    var f = S.sporocilaFilter || "";
    if (f === "email" && vrsta !== "email") return false;
    if (f === "klepet" && !jeKlepet(vrsta)) return false;
    if (f.indexOf("kanal:") === 0 && p.kanal_id !== f.slice(6)) return false;
    var mapa = S.sporocilaMapa || "vse";
    if (mapa === "osnutki") return false;      // osnutki niso pogovori (narisiOsnutke)
    if (mapa === "neprebrano" && !p.neprebrano) return false;
    if (mapa === "zvezdica" && !p.zvezdica) return false;
    if (mapa === "poslano" && !p.zadnji_ven) return false;
    if (mapa.indexOf("oznaka:") === 0 && (p.oznake || []).indexOf(mapa.slice(7)) < 0) return false;
    var n = (S.sporocilaNiz || "").trim().toLowerCase();
    if (n) {
      var besedilo = (skupina.oseba.ime + " " + (skupina.oseba.privzeto_ime || "") + " " + (p.zadeva || "") + " " + (p.zadnje_sporocilo || "") + " " + ((p.kanal || {}).ime || "") + " " + (p.oznake || []).join(" ")).toLowerCase();
      if (besedilo.indexOf(n) < 0) return false;
    }
    return true;
  }
  /* Vrstica seznama (prenova 16. 10. 2026): pika za neprebrano, avatar, ime in cas v prvi vrsti, predogled in znak kanala
     v drugi. Ime ni vec prirezano zaradi znack (kanal, oznake): kanal je znak na desni, oznake so v panu in filtru. */
  function vrsticaHtml(v) {
    return '<span class="neprebrano-pika" aria-hidden="true"></span>' + avatarHtml(v.ime, v.kljuc) +
      '<span class="vrstica-telo"><span class="vrstica-vrh">' +
      (v.zvezdica ? '<span class="zvezdica-pogovora" title="' + ubezi(t("mapaZvezdica")) + '">' + svg("zvezda") + '</span>' : '') +
      '<b class="vrstica-ime">' + ubezi(v.ime) + '</b>' +
      (v.oznaka ? '<span class="vrstica-oznaka">' + ubezi(v.oznaka) + '</span>' : '') +
      '<time>' + ubezi(relativniCas(v.cas)) + '</time></span>' +
      '<span class="vrstica-dno"><small class="vrstica-predogled">' + ubezi(v.predogled || "") + '</small>' +
      (v.poslano ? '<em class="poslano-oznaka">' + ubezi(v.poslano) + '</em>' : '') +
      (v.priponke ? '<span class="sponka" title="' + ubezi(t("imaPriponke")) + '">' + svg("sponka") + '</span>' : '') +
      (v.neprebrano > 1 ? '<span class="vrstica-stevilo" aria-hidden="true">' + (v.neprebrano > 99 ? "99+" : Number(v.neprebrano)) + '</span>' : '') +
      znakKanala(v.kanal) + '</span></span>';
  }
  function filterAktiven() {
    return (S.sporocilaMapa || "vse") !== "vse" || !!S.sporocilaFilter;
  }
  function imeFiltraKanala(f) {
    if (!f) return t("vsiKanali");
    if (f === "email") return t("eposta");
    if (f === "klepet") return t("filterKlepeti");
    var k = (S.sporocilaKanali || []).filter(function (x) { return "kanal:" + x.id === f; })[0];
    return k ? k.ime : f.slice(6);
  }
  function imeMape(m) {
    m = m || "vse";
    if (m.indexOf("oznaka:") === 0) return "#" + m.slice(7);
    return t({ vse: "mapaPrejeto", neprebrano: "mapaNeprebrano", zvezdica: "mapaZvezdica", poslano: "mapaPoslano", osnutki: "mapaOsnutki" }[m] || "mapaPrejeto");
  }
  // Filter po posameznem kanalu: gumb za vsak kanal z adapterjem (vgrajeni kanali nimajo pogovorov v nabiralniku).
  function narisiFiltreKanalov() {
    var cilj = $("sporocilaFiltri"); if (!cilj) return;
    // Gumbi se narisejo znova samo, ko se kanali spremenijo (osvezitev ne vzame fokusa gumbu v odprti plosci).
    var podpis = (S.sporocilaKanali || []).map(function (k) { return k.id + "\u0001" + k.ime + "\u0001" + k.vrsta; }).join("\u0002");
    if (cilj._podpis !== podpis) {
      cilj._podpis = podpis;
      Array.prototype.slice.call(cilj.querySelectorAll("[data-kanal-id]")).forEach(function (b) { cilj.removeChild(b); });
      (S.sporocilaKanali || []).forEach(function (k) {
        var b = el("button", "", znakKanala(k) + "<span>" + ubezi(k.ime) + "</span>"); b.type = "button";
        b.setAttribute("data-kanal-vrsta", "kanal:" + k.id); b.setAttribute("data-kanal-id", k.id);
        cilj.appendChild(b);
      });
    }
    var f = S.sporocilaFilter || "";
    // Kanal je bil odstranjen: filter po njem ne sme skriti vseh pogovorov brez razloga.
    if (f.indexOf("kanal:") === 0 && !(S.sporocilaKanali || []).some(function (k) { return "kanal:" + k.id === f; })) S.sporocilaFilter = f = "";
    cilj.querySelectorAll("button").forEach(function (x) {
      var da = (x.getAttribute("data-kanal-vrsta") || "") === f;
      x.classList.toggle("izbran", da); x.setAttribute("aria-pressed", da ? "true" : "false");
    });
  }
  // Izbrani filtri so vidni pod iskanjem kot cipi z »×« (en klik nazaj na vse), gumb filtra ima piko.
  function narisiAktivneFiltre() {
    var cilj = $("sporocilaAktivniFiltri"); if (!cilj) return;
    cilj.innerHTML = "";
    var mapa = S.sporocilaMapa || "vse";
    if (mapa !== "vse") cilj.appendChild(cipFiltra(imeMape(mapa), function () { izberiMapo("vse"); }));
    if (S.sporocilaFilter) cilj.appendChild(cipFiltra(imeFiltraKanala(S.sporocilaFilter), function () { izberiFilterKanala(""); }));
    cilj.hidden = !cilj.children.length;
    var g = $("sporocilaFilterGumb");
    if (g) { g.classList.toggle("aktiven", filterAktiven()); g.querySelector(".filter-pika").hidden = !filterAktiven(); }
    var poc = $("sporocilaPocisti"); if (poc) poc.hidden = !filterAktiven();
    var naslov = $("sporocilaMapaNaslov"); if (naslov) naslov.textContent = imeMape(mapa);
  }
  function cipFiltra(besedilo, odstrani) {
    var b = el("button", "cip-filtra", "<span>" + ubezi(besedilo) + "</span>" + svg("x")); b.type = "button";
    b.setAttribute("aria-label", t("spOdstraniFilter", { ime: besedilo }));
    b.addEventListener("click", function () {
      odstrani();
      // Fokus ne pade na telo strani: na naslednji cip ali na gumb filtra.
      var n = document.querySelector("#sporocilaAktivniFiltri .cip-filtra") || $("sporocilaFilterGumb"); if (n) n.focus();
    });
    return b;
  }
  function izberiMapo(mapa) {
    S.sporocilaMapa = mapa || "vse";
    zapriVgrajenKanal();
    $("sporocilaMape").querySelectorAll("button").forEach(function (x) {
      var da = x.getAttribute("data-mapa") === S.sporocilaMapa;
      x.classList.toggle("izbran", da); x.setAttribute("aria-pressed", da ? "true" : "false");
    });
    narisiSporocila();
  }
  function izberiFilterKanala(f) {
    S.sporocilaFilter = f || "";
    narisiSporocila();
  }
  function odpriFilter(odpri) {
    var pl = $("sporocilaFilterPlosca"), g = $("sporocilaFilterGumb"); if (!pl || !g) return false;
    if (odpri === undefined) odpri = pl.hidden;
    if (!odpri && pl.hidden) return false;
    pl.hidden = !odpri; g.setAttribute("aria-expanded", odpri ? "true" : "false");
    if (odpri) { var prvi = pl.querySelector("button.izbran") || pl.querySelector("button"); if (prvi) prvi.focus(); }
    return true;
  }
  function narisiSporocila() {
    narisiKanale(); narisiFiltreKanalov();
    var cilj = $("sporocilaSeznam"); if (!cilj) return;
    // Osvezitev (sinhronizacija, dejanje) ne sme vzeti fokusa ali besedila hitrega odgovora.
    var fokus = document.activeElement, fokusOvoj = fokus && cilj.contains(fokus) ? fokus.closest(".pogovor-ovoj") : null;
    var fokusKljuc = S.fokusPo || (fokusOvoj ? fokusOvoj.getAttribute("data-kljuc") : "");
    var vHitrem = fokusOvoj && fokus.tagName === "TEXTAREA" ? [fokus.selectionStart, fokus.selectionEnd] : null;
    var fokusVSeznamu = !!(fokusOvoj || (S.fokusPo && fokus && cilj.contains(fokus)) || (S.fokusPo && fokus === document.body));
    S.fokusPo = "";
    cilj.innerHTML = "";
    var neprebrano = 0, vseh = 0, vrstice = [];
    S.sporocilaSkupine.forEach(function (skupina) {
      (skupina.pogovori || []).forEach(function (p) {
        vseh++; if (p.neprebrano) neprebrano += Number(p.neprebrano);
        if (S.skritiPogovori[kljucPogovora(p)]) return;      // arhiv/izbris caka na »Razveljavi« (5 s)
        if (pogovorUstreza(skupina, p)) vrstice.push({ skupina: skupina, p: p });
      });
    });
    vrstice.sort(function (a, b) { return String(b.p.cas || "").localeCompare(String(a.p.cas || "")); });
    S.vrsticeSeznama = vrstice;
    var izbranih = vrstice.filter(function (v) { return S.izbraniPogovori[kljucPogovora(v.p)]; }).length;
    cilj.classList.toggle("izbiranje", izbranih > 0);
    var a = S.sporocilaAktivni;
    vrstice.forEach(function (v) {
      var skupina = v.skupina, p = v.p, vrsta = (p.kanal || {}).vrsta || "", k = kljucPogovora(p), n = Number(p.neprebrano) || 0;
      var izbran = !!(a && a.id === p.id && a.kanal_id === p.kanal_id);
      // Ovoj: potrditveno polje (vec izbranih), vrstica, orodja ob prehodu in hitri odgovor (dejanja, 17. 10. 2026);
      // vrstica sama je iz prenove nabiralnika (16. 10. 2026): pika, avatar, ime in cas, predogled, znak kanala.
      var ovoj = el("div", "pogovor-ovoj" + (S.izbraniPogovori[k] ? " oznacen" : "") + (n ? " neprebran" : ""));
      ovoj.setAttribute("data-kljuc", k);
      var b = el("button", "vrstica-pogovora" + (izbran ? " izbran" : "") + (n ? " neprebrano" : "")); b.type = "button";
      b.setAttribute("data-kljuc", k);
      if (izbran) b.setAttribute("aria-current", "true");
      b.setAttribute("aria-keyshortcuts", "E Delete U S R X");
      var poslano = S.poslaniOdgovori[k] ? t(S.poslaniOdgovori[k] === "caka" ? "hitriOdgovorCaka" : "hitriOdgovorPoslano") : "";
      b.innerHTML = vrsticaHtml({ ime: skupina.oseba.ime, kljuc: skupina.oseba.id, cas: p.cas, kanal: p.kanal, neprebrano: n,
        priponke: p.priponke, zvezdica: !!p.zvezdica, poslano: poslano,
        predogled: p.zadeva && vrsta === "email" ? p.zadeva + " – " + (p.zadnje_sporocilo || "") : (p.zadnje_sporocilo || p.zadeva || "") });
      // Bralnik zaslona prebere tudi to, kar je v vrstici vidno samo z obliko (pika, znak kanala, zvezdica).
      b.setAttribute("aria-label", [skupina.oseba.ime, (p.kanal || {}).ime || "", n ? t("spNeprebranih", { n: n }) : "",
        p.zvezdica ? t("mapaZvezdica") : "", relativniCas(p.cas), b.querySelector(".vrstica-predogled").textContent,
        poslano].filter(Boolean).join(", "));
      b.addEventListener("click", function (e) {
        if (e.ctrlKey || e.metaKey) { preklopiIzbor(k, false); return; }
        if (e.shiftKey) { preklopiIzbor(k, true); return; }
        S.izbraniPogovori = {}; odpriPogovor(skupina.oseba, p);
      });
      b.addEventListener("contextmenu", function (e) {
        e.preventDefault();
        pokaziMeniPogovora(ciljiDejanja(v), e.clientX, e.clientY, false, b);
      });
      var izbor = el("input", "pogovor-izbor"); izbor.type = "checkbox"; izbor.checked = !!S.izbraniPogovori[k];
      izbor.setAttribute("aria-label", t("dejanjeIzberi") + ": " + skupina.oseba.ime);
      izbor.addEventListener("click", function (e) { e.stopPropagation(); preklopiIzbor(k, e.shiftKey); });
      ovoj.appendChild(izbor); ovoj.appendChild(b); ovoj.appendChild(orodjaPogovora(v, b));
      cilj.appendChild(ovoj);
      if (S.hitriOdgovor && S.hitriOdgovor.kljuc === k) ovoj.appendChild(hitriOdgovorOkno(v));
      if (fokusVSeznamu && fokusKljuc === k) {
        var tf = vHitrem ? ovoj.querySelector("textarea") : null;
        if (tf) { tf.focus(); try { tf.setSelectionRange(vHitrem[0], vHitrem[1]); } catch (napaka) {} }
        else if (!S.hitriOdgovor || S.hitriOdgovor.kljuc !== k || !S.hitriOdgovor.fokus) b.focus({ preventScroll: true });
      }
      if (S.hitriOdgovor && S.hitriOdgovor.kljuc === k && S.hitriOdgovor.fokus) {
        S.hitriOdgovor.fokus = false; var tn = ovoj.querySelector("textarea"); if (tn) tn.focus();
      }
    });
    if (izbranih) cilj.insertBefore(vrsticaMnozicno(izbranih), cilj.firstChild);
    if (S.sporocilaMapa === "osnutki") narisiOsnutke(cilj);
    else if (!cilj.children.length) cilj.appendChild(el("p", "prazno", ubezi(t(vseh ? "niZadetkov" : "niPogovorov"))));
    var so = $("stOsnutki"); if (so) { so.textContent = (S.osnutki || []).length; so.hidden = !(S.osnutki || []).length; }
    var sn = $("stNeprebrano"), sp = $("stPrejeto");
    if (sn) { sn.textContent = neprebrano; sn.hidden = !neprebrano; }
    if (sp) { sp.textContent = neprebrano; sp.hidden = !neprebrano; }
    narisiOznakeMape();
    narisiAktivneFiltre();
  }
  // ------------------------------------------------------------------ dejanja v seznamu pogovorov
  // Lastnik, 17. 10. 2026: urejanje e-poste ze v seznamu (ikone ob prehodu, desni klik, tipke kot v Gmailu/Outlooku,
  // vec izbranih) in hitri odgovor pod vrstico. Streznik (IMAP) dela v niti ozadja Safeer OS; seznam se spremeni
  // takoj, ob napaki se vrne. Arhiv/izbris/premik odide sele po 5 s - do takrat ga »Razveljavi« preprosto preklice.
  var DEJANJA_PREMIK = { arhiv: "dejanjeArhivirano", izbrisi: "dejanjeIzbrisano", nezeleno: "dejanjeNezelenoOk", mapa: "dejanjePremaknjeno" };
  var razveljaviZadnje = null;
  function kljucPogovora(p) { return p.kanal_id + "\u0001" + p.id; }
  function zmoreDejanje(p, dejanje) { return ((p.kanal || {}).dejanja || []).indexOf(dejanje) >= 0; }
  function izbraneVrstice() { return S.vrsticeSeznama.filter(function (v) { return S.izbraniPogovori[kljucPogovora(v.p)]; }); }
  // Dejanje na vrstici, ki je med izbranimi, velja za vse izbrane; sicer samo zanjo.
  function ciljiDejanja(v) {
    var izbrane = izbraneVrstice();
    return v && !S.izbraniPogovori[kljucPogovora(v.p)] ? [v] : (izbrane.length ? izbrane : (v ? [v] : []));
  }
  function preklopiIzbor(k, obmocje) {
    var kljuci = S.vrsticeSeznama.map(function (v) { return kljucPogovora(v.p); });
    if (obmocje && S.zadnjiIzbor && kljuci.indexOf(S.zadnjiIzbor) >= 0) {
      var a = kljuci.indexOf(S.zadnjiIzbor), b = kljuci.indexOf(k);
      kljuci.slice(Math.min(a, b), Math.max(a, b) + 1).forEach(function (x) { S.izbraniPogovori[x] = true; });
    } else if (S.izbraniPogovori[k]) delete S.izbraniPogovori[k];
    else S.izbraniPogovori[k] = true;
    S.zadnjiIzbor = k; S.fokusPo = k;
    narisiSporocila();
  }
  function gumbDejanja(ikona, naslov, tipka, ob) {
    var g = el("button", "dejanje-gumb", svg(ikona)); g.type = "button";
    g.title = naslov + (tipka ? " (" + tipka + ")" : ""); g.setAttribute("aria-label", naslov);
    if (tipka) g.setAttribute("aria-keyshortcuts", tipka);
    g.tabIndex = -1;          // tipkovnica: tipke na vrstici (E, #, U, S, R) in meni (Shift+F10) - brez 6 postankov Tab
    g.addEventListener("click", function (e) { e.stopPropagation(); ob(e, g); });
    return g;
  }
  // Ikone ob prehodu z misko ali fokusu vrstice: samo, kar kanal res zmore (klepeti nimajo arhiva in Kosa).
  function orodjaPogovora(v, vrstica) {
    var p = v.p, o = el("div", "pogovor-dejanja");
    var dodaj = function (dejanje, ikona, naslov, tipka) {
      if (zmoreDejanje(p, dejanje)) o.appendChild(gumbDejanja(ikona, t(naslov), tipka, function () { izvediDejanje(ciljiDejanja(v), dejanje); }));
    };
    o.appendChild(gumbDejanja("poslji", t("dejanjeOdgovori"), "R", function () { odpriHitriOdgovor(v); }));
    dodaj("arhiv", "arhiv", "dejanjeArhiviraj", "E");
    dodaj("izbrisi", "kos", "dejanjeIzbrisi", "Delete");
    if (p.neprebrano) dodaj("prebrano", "kljukica", "dejanjePrebrano", "U");
    else dodaj("neprebrano", "sporocila", "dejanjeNeprebrano", "U");
    // Zvezdica, neželeno, mapa in oznake so v meniju »Vec« (stolpec seznama je ozek: ime in cas ostaneta vidna).
    o.appendChild(gumbDejanja("vec", t("dejanjeVec"), "Shift+F10", function (e, g) {
      var r = g.getBoundingClientRect(); pokaziMeniPogovora(ciljiDejanja(v), r.left, r.bottom + 4, e.detail === 0, vrstica);
    }));
    return o;
  }
  function vrsticaMnozicno(n) {
    var o = el("div", "pogovori-mnozicno");
    o.setAttribute("role", "toolbar"); o.setAttribute("aria-label", t("dejanjeIzbranih", { n: n }));
    o.appendChild(el("span", "", ubezi(t("dejanjeIzbranih", { n: n }))));
    var izbrane = izbraneVrstice();
    var vsi = function (d) { return izbrane.some(function (v) { return zmoreDejanje(v.p, d); }); };
    [["arhiv", "arhiv", "dejanjeArhiviraj", "E"], ["izbrisi", "kos", "dejanjeIzbrisi", "Delete"],
     ["prebrano", "kljukica", "dejanjePrebrano", ""], ["zvezdica", "zvezda", "dejanjeZvezdica", "S"]].forEach(function (d) {
      if (!vsi(d[0])) return;
      var g = gumbDejanja(d[1], t(d[2]), d[3], function () { izvediDejanje(izbraneVrstice(), d[0]); }); g.tabIndex = 0; o.appendChild(g);
    });
    var vec = gumbDejanja("vec", t("dejanjeVec"), "", function (e, g) {
      var r = g.getBoundingClientRect(); pokaziMeniPogovora(izbraneVrstice(), r.left, r.bottom + 4, e.detail === 0, g);
    }); vec.tabIndex = 0; o.appendChild(vec);
    var pocisti = gumbDejanja("x", t("dejanjePocistiIzbor"), "Esc", function () { S.izbraniPogovori = {}; narisiSporocila(); });
    pocisti.tabIndex = 0; o.appendChild(pocisti);
    return o;
  }
  function obvestiRazveljavi(besedilo, razveljavi) {
    var o = $("obvestilo");
    o.textContent = ""; o.appendChild(el("span", "", ubezi(besedilo)));
    var g = el("button", "", ubezi(t("dejanjeRazveljavi"))); g.type = "button";
    g.title = t("dejanjeRazveljavi") + " (Ctrl+Z)";
    g.addEventListener("click", function () { o.classList.remove("viden", "z-gumbom"); razveljavi(); });
    o.appendChild(g); o.classList.add("z-gumbom", "viden");
    clearTimeout(obvestiloCas);
    obvestiloCas = setTimeout(function () { o.classList.remove("viden", "z-gumbom"); }, 5000);
  }
  function javiNapakeDejanja(p) {
    var napake = (p && p.napake) || [];
    if (!napake.length) return false;
    var koda = napake[0].koda;
    obvesti(t(koda === "ni_mape" ? "dejanjeNiMape" : koda === "prijava" ? "dejanjePrijava" : "dejanjeNapaka"));
    return true;
  }
  function izvediDejanje(vrstice, dejanje, mapa) {
    vrstice = (vrstice || []).filter(function (v) { return zmoreDejanje(v.p, dejanje); });
    if (!vrstice.length) return;
    var cilji = vrstice.map(function (v) { return [v.p.kanal_id, v.p.id]; });
    var kljuci = vrstice.map(function (v) { return kljucPogovora(v.p); });
    if (DEJANJA_PREMIK[dejanje]) {
      // Fokus gre na naslednjo vrstico (kot v Gmailu), ne na zacetek strani.
      var vse = S.vrsticeSeznama.map(function (v) { return kljucPogovora(v.p); }), zadnji = -1;
      kljuci.forEach(function (k) { zadnji = Math.max(zadnji, vse.indexOf(k)); });
      var naslednji = vse.slice(zadnji + 1).concat(vse.slice(0, zadnji).reverse()).filter(function (k) { return kljuci.indexOf(k) < 0; })[0] || "";
      kljuci.forEach(function (k) { S.skritiPogovori[k] = true; delete S.izbraniPogovori[k]; });
      if (S.hitriOdgovor && kljuci.indexOf(S.hitriOdgovor.kljuc) >= 0) S.hitriOdgovor = null;
      S.fokusPo = naslednji; narisiSporocila();
      var preklicano = false, vrni = function () { kljuci.forEach(function (k) { delete S.skritiPogovori[k]; }); };
      var ura = setTimeout(function () {
        if (razveljaviZadnje === razveljavi) razveljaviZadnje = null;
        klic("sporocilaDejanje", [cilji, dejanje, mapa || ""]).then(function (p) {
          vrni(); posodobiSeznamIzOdgovora(p); javiNapakeDejanja(p);
        }).catch(function () { vrni(); narisiSporocila(); obvesti(t("dejanjeNapaka")); });
      }, 5000);
      var razveljavi = function () {
        if (preklicano) return;
        preklicano = true; clearTimeout(ura); vrni(); razveljaviZadnje = null;
        S.fokusPo = kljuci[0]; narisiSporocila();
      };
      razveljaviZadnje = razveljavi;
      obvestiRazveljavi(t(DEJANJA_PREMIK[dejanje], { n: kljuci.length }), razveljavi);
      return;
    }
    // Oznake (prebrano, zvezdica): takoj v seznamu, streznik potrdi v ozadju; ob napaki se vrne.
    var prej = vrstice.map(function (v) { return { p: v.p, neprebrano: v.p.neprebrano, zvezdica: v.p.zvezdica }; });
    vrstice.forEach(function (v) {
      if (dejanje === "prebrano") v.p.neprebrano = 0;
      else if (dejanje === "neprebrano") v.p.neprebrano = Math.max(1, Number(v.p.neprebrano) || 0);
      else if (dejanje === "zvezdica") v.p.zvezdica = true;
      else if (dejanje === "brez_zvezdice") v.p.zvezdica = false;
    });
    narisiSporocila();
    klic("sporocilaDejanje", [cilji, dejanje, mapa || ""]).then(function (p) {
      posodobiSeznamIzOdgovora(p); javiNapakeDejanja(p);
    }).catch(function () {
      prej.forEach(function (x) { x.p.neprebrano = x.neprebrano; x.p.zvezdica = x.zvezdica; });
      narisiSporocila(); obvesti(t("dejanjeNapaka"));
    });
  }
  // Meni vrstice (desni klik, tipka Meni, Shift+F10, gumb »Vec«): vsa dejanja, ki jih kanali izbranih zmorejo.
  function pokaziMeniPogovora(vrstice, x, y, sTipkovnico, za) {
    var m = $("sporocilaMeni"); if (!m || !vrstice.length) return;
    zapriMeniSporocila();
    m.innerHTML = ""; m._za = za || null; meniSporocilaOb = Date.now();
    var vsaj = function (d) { return vrstice.some(function (v) { return zmoreDejanje(v.p, d); }); };
    var postavka = function (besedilo, tipka, ob) {
      var g = el("button", "", "<span>" + ubezi(besedilo) + "</span>" + (tipka ? "<kbd>" + ubezi(tipka) + "</kbd>" : ""));
      g.type = "button"; g.setAttribute("role", "menuitem");
      g.addEventListener("click", function () {
        var sTipk = m.contains(document.activeElement), zaj = m._za;
        zapriMeniSporocila();
        if (sTipk && zaj && document.contains(zaj)) zaj.focus();
        ob();
      });
      m.appendChild(g); return g;
    };
    var ena = vrstice.length === 1 ? vrstice[0] : null;
    if (ena) postavka(t("dejanjeOdgovori"), "R", function () { odpriHitriOdgovor(ena); });
    var neprebrani = vrstice.some(function (v) { return v.p.neprebrano; });
    if (neprebrani && vsaj("prebrano")) postavka(t("dejanjePrebrano"), "U", function () { izvediDejanje(vrstice, "prebrano"); });
    if (!neprebrani && vsaj("neprebrano")) postavka(t("dejanjeNeprebrano"), "U", function () { izvediDejanje(vrstice, "neprebrano"); });
    var vsiZvezda = vrstice.every(function (v) { return v.p.zvezdica; });
    if (vsaj("zvezdica")) postavka(t(vsiZvezda ? "dejanjeBrezZvezdice" : "dejanjeZvezdica"), "S", function () { izvediDejanje(vrstice, vsiZvezda ? "brez_zvezdice" : "zvezdica"); });
    if (vsaj("arhiv")) postavka(t("dejanjeArhiviraj"), "E", function () { izvediDejanje(vrstice, "arhiv"); });
    if (vsaj("izbrisi")) postavka(t("dejanjeIzbrisi"), "#", function () { izvediDejanje(vrstice, "izbrisi"); });
    if (vsaj("nezeleno")) postavka(t("dejanjeNezeleno"), "", function () { izvediDejanje(vrstice, "nezeleno"); });
    var kanali = {}; vrstice.forEach(function (v) { kanali[v.p.kanal_id] = 1; });
    if (vsaj("mapa") && Object.keys(kanali).length === 1) postavka(t("dejanjePremakni"), "", function () { meniMap(vrstice, x, y, za); });
    // Oznake (lokalne, nastavi_oznake): obstojece kot stikala za vse izbrane, nova v podoknu osebe.
    (S.sporocilaOznakeVse || []).slice(0, 12).forEach(function (o) {
      var imajo = vrstice.every(function (v) { return (v.p.oznake || []).indexOf(o) >= 0; });
      postavka((imajo ? "✓ " : "") + t("dejanjeOznaka", { oznaka: o }), "", function () {
        vrstice.forEach(function (v) {
          var nove = (v.p.oznake || []).filter(function (y) { return y !== o; });
          if (!imajo) nove.push(o);
          shraniOznake(v.p, nove);
        });
      });
    });
    if (ena) postavka(t("dejanjeNovaOznaka"), "", function () {
      odpriPogovor(ena.skupina.oseba, ena.p); setTimeout(function () { var i = $("panoOznakaVnos"); if (i) i.focus(); }, 60);
    });
    m.hidden = false;
    m.style.left = Math.max(8, Math.min(window.innerWidth - m.offsetWidth - 8, x)) + "px";
    m.style.top = Math.max(8, Math.min(window.innerHeight - m.offsetHeight - 8, y)) + "px";
    if (sTipkovnico && m.firstChild) m.firstChild.focus();
  }
  function meniMap(vrstice, x, y, za) {
    var kanal = vrstice[0].p.kanal_id, m = $("sporocilaMeni");
    m.innerHTML = ""; m._za = za || null; m.appendChild(el("p", "drobno", ubezi(t("povezujem")))); m.hidden = false;
    m.style.left = Math.max(8, Math.min(window.innerWidth - m.offsetWidth - 8, x)) + "px";
    m.style.top = Math.max(8, Math.min(window.innerHeight - m.offsetHeight - 8, y)) + "px";
    klic("sporocilaMapeRacuna", [kanal]).then(function (mape) {
      if (m.hidden) return;
      m.innerHTML = "";
      mape = (mape || []).filter(function (x) { return x.posebna !== "drafts" && x.posebna !== "sent"; });
      if (!mape.length) { m.appendChild(el("p", "drobno", ubezi(t("dejanjeNiMap")))); return; }
      mape.forEach(function (mp) {
        var g = el("button", "", "<span>" + ubezi(mp.prikaz || mp.ime) + "</span>"); g.type = "button"; g.setAttribute("role", "menuitem");
        g.addEventListener("click", function () { zapriMeniSporocila(); izvediDejanje(vrstice, "mapa", mp.ime); });
        m.appendChild(g);
      });
      m.style.top = Math.max(8, Math.min(window.innerHeight - m.offsetHeight - 8, y)) + "px";
      m.firstChild.focus();
    }).catch(function () { zapriMeniSporocila(); obvesti(t("dejanjeNapaka")); });
  }
  // Hitri odgovor: majhno polje pod vrstico (zadnje sporocilo na kratko, besedilo, Poslji = Ctrl+Enter, Esc = preklici).
  // Gre po obstojecem sporocilaPoslji: e-posta kot pravi odgovor (Re:, In-Reply-To, References - core/sporocila/email.py).
  function odpriHitriOdgovor(v) {
    var k = kljucPogovora(v.p);
    if (!S.hitriOdgovor || S.hitriOdgovor.kljuc !== k) S.hitriOdgovor = { kljuc: k, besedilo: "" };
    S.hitriOdgovor.fokus = true; narisiSporocila();
  }
  function zapriHitriOdgovor() {
    var k = S.hitriOdgovor && S.hitriOdgovor.kljuc;
    S.hitriOdgovor = null; S.fokusPo = k || ""; narisiSporocila();
  }
  function hitriOdgovorOkno(v) {
    var h = S.hitriOdgovor, p = v.p;
    var okno = el("div", "hitri-odgovor"); okno.setAttribute("role", "group");
    okno.setAttribute("aria-label", t("dejanjeOdgovori") + ": " + v.skupina.oseba.ime);
    var zadnje = String(p.zadnje_sporocilo || p.zadeva || "").replace(/\s+/g, " ").trim();
    if (zadnje) okno.appendChild(el("p", "hitri-zadnje", ubezi(zadnje.length > 220 ? zadnje.slice(0, 220) + " …" : zadnje)));
    var vnos = el("textarea"); vnos.rows = 3; vnos.value = h.besedilo || ""; vnos.maxLength = 20000;
    vnos.placeholder = t("hitriOdgovorPh"); vnos.setAttribute("aria-label", t("hitriOdgovorPh"));
    var napaka = el("p", "hitri-napaka"); napaka.hidden = true; napaka.setAttribute("role", "alert");
    var gumbi = el("div", "hitri-gumbi");
    var poslji = el("button", "gumb glavni", ubezi(t("hitriOdgovorPoslji"))); poslji.type = "button"; poslji.title = t("hitriOdgovorPoslji") + " (Ctrl+Enter)";
    var preklici = el("button", "gumb", ubezi(t("preklici"))); preklici.type = "button"; preklici.title = t("preklici") + " (Esc)";
    var poslji_ = function () {
      var besedilo = vnos.value.trim();
      if (!besedilo || h.posiljam) { vnos.focus(); return; }
      h.posiljam = true; poslji.disabled = true; vnos.disabled = true;
      klic("sporocilaPoslji", [p.kanal_id, p.id, besedilo]).then(function (d) {
        var k = kljucPogovora(p);
        if (S.hitriOdgovor === h) S.hitriOdgovor = null;
        S.poslaniOdgovori[k] = d && d.caka ? "caka" : "poslano";
        setTimeout(function () { delete S.poslaniOdgovori[k]; narisiSporocila(); }, 6000);
        S.fokusPo = k; narisiSporocila();
      }).catch(function (e) {
        h.posiljam = false; poslji.disabled = false; vnos.disabled = false;
        napaka.hidden = false; napaka.textContent = napakaSporocil(e); vnos.focus();
      });
    };
    vnos.addEventListener("input", function () { h.besedilo = vnos.value; });
    vnos.addEventListener("keydown", function (e) {
      e.stopPropagation();          // E, U, S, R ... so tu crke besedila, ne dejanja seznama
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); poslji_(); }
      else if (e.key === "Escape") { e.preventDefault(); zapriHitriOdgovor(); }
    });
    poslji.addEventListener("click", poslji_);
    preklici.addEventListener("click", zapriHitriOdgovor);
    gumbi.appendChild(preklici); gumbi.appendChild(poslji);
    okno.appendChild(vnos); okno.appendChild(napaka); okno.appendChild(gumbi);
    return okno;
  }
  // Tipke na vrstici seznama (kot Gmail/Outlook): E arhiv, # ali Delete Kos, U (ne)prebrano, S zvezdica, R odgovor,
  // X izberi, puscici gor/dol, Shift+F10 ali tipka Meni = meni, Esc pocisti izbor, Ctrl+Z razveljavi.
  function tipkeSeznama(e) {
    if (e.target && (e.target.tagName === "TEXTAREA" || (e.target.tagName === "INPUT" && e.target.type !== "checkbox"))) return;
    if ((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === "z" || e.key === "Z")) {
      if (razveljaviZadnje) { e.preventDefault(); $("obvestilo").classList.remove("viden", "z-gumbom"); razveljaviZadnje(); }
      return;
    }
    var ovoj = e.target && e.target.closest ? e.target.closest(".pogovor-ovoj") : null;
    if (!ovoj && !e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey && e.target && e.target.classList &&
        e.target.classList.contains("vrstica-pogovora")) {
      // Osnutki (vrstice brez dejanj): samo premikanje med vrsticami.
      var vr = Array.prototype.slice.call($("sporocilaSeznam").querySelectorAll(".vrstica-pogovora"));
      var i = vr.indexOf(e.target), n = { ArrowDown: i + 1, ArrowUp: i - 1, Home: 0, End: vr.length - 1 }[e.key];
      if (n !== undefined) { e.preventDefault(); vr[Math.max(0, Math.min(vr.length - 1, n))].focus(); }
      return;
    }
    if (!ovoj || e.altKey || e.ctrlKey || e.metaKey) return;
    var k = ovoj.getAttribute("data-kljuc"), v = S.vrsticeSeznama.filter(function (x) { return kljucPogovora(x.p) === k; })[0];
    if (!v) return;
    var cilji = ciljiDejanja(v), kljucTipke = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    var prvi = cilji[0] ? cilji[0].p : v.p, opravljeno = true;
    if (kljucTipke === "e") izvediDejanje(cilji, "arhiv");
    else if (e.key === "#" || e.key === "Delete") izvediDejanje(cilji, "izbrisi");
    else if (kljucTipke === "u") izvediDejanje(cilji, prvi.neprebrano ? "prebrano" : "neprebrano");
    else if (kljucTipke === "s") izvediDejanje(cilji, prvi.zvezdica ? "brez_zvezdice" : "zvezdica");
    else if (kljucTipke === "r") odpriHitriOdgovor(v);
    else if (kljucTipke === "x") preklopiIzbor(k, e.shiftKey);
    else if (e.key === "Escape" && Object.keys(S.izbraniPogovori).length) { S.izbraniPogovori = {}; S.fokusPo = k; narisiSporocila(); }
    else if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) {
      var r = ovoj.getBoundingClientRect(); pokaziMeniPogovora(cilji, r.left + 24, r.bottom - 6, true, ovoj.querySelector(".vrstica-pogovora"));
    } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      var vrstice = Array.prototype.slice.call($("sporocilaSeznam").querySelectorAll(".pogovor-ovoj"));
      var sosed = vrstice[vrstice.indexOf(ovoj) + (e.key === "ArrowDown" ? 1 : -1)];
      if (sosed) {
        if (e.shiftKey) { S.izbraniPogovori[k] = true; S.izbraniPogovori[sosed.getAttribute("data-kljuc")] = true; S.fokusPo = sosed.getAttribute("data-kljuc"); narisiSporocila(); }
        else sosed.querySelector(".vrstica-pogovora").focus();
      }
    } else if ((e.key === "Home" || e.key === "End") && !e.shiftKey) {
      var vse = $("sporocilaSeznam").querySelectorAll(".vrstica-pogovora");
      if (vse.length) vse[e.key === "Home" ? 0 : vse.length - 1].focus();
    } else opravljeno = false;
    if (opravljeno) { e.preventDefault(); e.stopPropagation(); }
  }
  function narisiOznakeMape() {
    var cilj = $("sporocilaOznake"); if (!cilj) return; cilj.innerHTML = "";
    var oznake = S.sporocilaOznakeVse || [];
    var dl = $("seznamOznak"); if (dl) { dl.innerHTML = ""; oznake.forEach(function (o) { var op = document.createElement("option"); op.value = o; dl.appendChild(op); }); }
    cilj.parentNode.querySelector('[data-t="oznakeNaslov"]').hidden = !oznake.length;
    oznake.forEach(function (o) {
      var da = S.sporocilaMapa === "oznaka:" + o;
      var b = el("button", da ? "izbran" : ""); b.type = "button"; b.setAttribute("aria-pressed", da ? "true" : "false");
      b.innerHTML = "<span>" + ubezi(o) + "</span>";
      b.addEventListener("click", function () { izberiMapo(S.sporocilaMapa === "oznaka:" + o ? "vse" : "oznaka:" + o); });
      cilj.appendChild(b);
    });
  }
  function shraniOznake(pogovor, oznake) {
    klic("sporocilaOznake", [pogovor.kanal_id, pogovor.id, oznake]).then(function (p) {
      posodobiSeznamIzOdgovora(p);
    }).catch(function (e) { obvesti(typeof e === "string" && e ? e : t("niUspelo")); });
  }
  function odpriOsebaSloj(nacin) {
    var o = S.sporocilaOseba; if (!o) return;
    zapriSloje(); S.osebaNacin = nacin;
    $("osebaIme").hidden = nacin !== "preimenuj"; $("osebaIzbira").hidden = nacin !== "zdruzi";
    if (nacin === "preimenuj") {
      $("osebaNaslov").textContent = t("osebaPreimenujNaslov"); $("osebaOpis").textContent = t("osebaPreimenujOpis", { privzeto: o.privzeto_ime || o.ime });
      $("osebaIme").value = o.lastno_ime || "";
    } else {
      $("osebaNaslov").textContent = t("osebaZdruziNaslov"); $("osebaOpis").textContent = t("osebaZdruziOpis", { ime: o.ime });
      var sel = $("osebaIzbira"); sel.innerHTML = "";
      S.sporocilaSkupine.forEach(function (sk) {
        if (sk.oseba.id === o.id) return;
        var op = document.createElement("option"); op.value = sk.oseba.id;
        var naslovi = (sk.oseba.identitete || []).map(function (i) { return Array.isArray(i) ? i[1] : i.naslov; }).filter(Boolean).join(", ");
        op.textContent = sk.oseba.ime + (naslovi ? " (" + naslovi + ")" : "");
        sel.appendChild(op);
      });
    }
    $("slojOseba").classList.add("viden"); (nacin === "preimenuj" ? $("osebaIme") : $("osebaIzbira")).focus();
  }
  function posodobiSeznamIzOdgovora(p) {
    S.sporocilaSkupine = p.skupine || []; S.sporocilaKanali = p.kanali || []; S.sporocilaOznakeVse = p.oznake || []; S.slikeOd = p.slike_od || S.slikeOd || [];
    // Oseba je lahko dobila novo ime ali se zdruzila: pano in naslov kazeta novo stanje.
    var a = S.sporocilaAktivni, nova = null, svez = null;
    S.sporocilaSkupine.forEach(function (sk) { (sk.pogovori || []).forEach(function (x) { if (a && x.id === a.id && x.kanal_id === a.kanal_id) { nova = sk.oseba; svez = x; } }); });
    if (nova) {
      S.sporocilaOseba = nova; S.sporocilaAktivni = svez; $("sporocilaNaslov").textContent = nova.ime;
      narisiPano(nova, svez, S.sporocilaZadnjaVsebina || []); narisiKanalOdgovora(nova, svez);
    }
    narisiSporocila();
  }
  // Vsi pogovori te osebe (en na kanal): »Povezani viri« v panu in izbira kanala za odgovor. Samo pravi pogovori iz
  // nabiralnika - kanal, prek katerega oseba se ni pisala, ni ponujen (nimamo naslova, ki bi ga kanal sprejel).
  function pogovoriOsebe(oseba) {
    var sk = (S.sporocilaSkupine || []).filter(function (x) { return oseba && x.oseba && x.oseba.id === oseba.id; })[0];
    return sk ? (sk.pogovori || []) : [];
  }
  // »Poslji« je dejaven samo, ko je kaj poslati (besedilo ali priloga) - prazen gumb ni ponujen kot dejanje.
  function posodobiPoslji() {
    var vnos = $("sporocilaBesedilo"), gumb = $("sporocilaVnos") && $("sporocilaVnos").querySelector('button[type="submit"]');
    if (!vnos || !gumb) return;
    gumb.disabled = !S.sporocilaAktivni || (!vnos.value.trim() && !(S.priloge.odgovor || []).length);
  }
  function narisiKanalOdgovora(oseba, pogovor) {
    var cilj = $("sporocilaVnosKanal"); if (!cilj) return;
    cilj.innerHTML = "";
    var vsi = pogovoriOsebe(oseba);
    cilj.appendChild(el("span", "", ubezi(t("spOdgovarjasPrek"))));
    cilj.insertAdjacentHTML("beforeend", znakKanala(pogovor.kanal));
    if (vsi.length < 2) { cilj.appendChild(el("b", "", ubezi((pogovor.kanal || {}).ime || ""))); return; }
    // Oseba je dosegljiva po vec kanalih: izbira preklopi na pogovor v tem kanalu (napisano besedilo ostane).
    var sel = document.createElement("select"); sel.id = "sporocilaKanalOdgovora"; sel.setAttribute("aria-label", t("spKanalOdgovora"));
    vsi.forEach(function (p, i) {
      var op = document.createElement("option"); op.value = String(i);
      op.textContent = ((p.kanal || {}).ime || p.kanal_id) + (p.zadeva && (p.kanal || {}).vrsta === "email" ? " · " + p.zadeva : "");
      if (p.id === pogovor.id && p.kanal_id === pogovor.kanal_id) op.selected = true;
      sel.appendChild(op);
    });
    sel.addEventListener("change", function () {
      var p = vsi[Number(sel.value)]; if (!p) return;
      odpriPogovor(oseba, p);
      var s2 = $("sporocilaVnosKanal").querySelector("select"); if (s2) s2.focus();   // izbira je narisana znova
    });
    cilj.appendChild(sel);
  }
  function odpriPogovor(oseba, pogovor) {
    zapriVgrajenKanal();
    S.sporocilaAktivni = pogovor; S.sporocilaOseba = oseba; narisiSporocila();
    $("sporocilaNaslov").textContent = oseba.ime;
    // Status »na spletu« ni prikazan: noben kanal (e-posta, Matrix, Telegram Bot, Chatwoot, Link) ga ne sporoca zanesljivo.
    $("sporocilaPodnaslov").textContent = t("spPrek", { kanal: (pogovor.kanal || {}).ime || "" }) + (pogovor.zadeva ? " · " + pogovor.zadeva : "");
    var av = $("sporocilaAvatar");
    if (av) { av.hidden = false; av.textContent = zacetnice(oseba.ime); av.style.background = barvaAvatarja(oseba.id || oseba.ime); }
    var okno = document.querySelector("#r-sporocila .pogovor-okno"); if (okno) okno.classList.remove("brez-pogovora");
    var nab = document.querySelector("#r-sporocila .nabiralnik"); if (nab) nab.classList.add("pogovor-odprt");
    var vsebina = $("sporocilaVsebina");
    // Avatar ob dohodnih mehurckih (CSS ::before, ni v izboru besedila).
    vsebina.style.setProperty("--zacetnice", JSON.stringify(zacetnice(oseba.ime)));
    vsebina.style.setProperty("--avatar", barvaAvatarja(oseba.id || oseba.ime));
    var vnos = $("sporocilaBesedilo");
    vnos.disabled = false;
    var kljucP = pogovor.kanal_id + "\u0001" + pogovor.id;
    if (S.prilogeZa !== kljucP) { S.prilogeZa = kljucP; S.priloge.odgovor = []; narisiPriloge("odgovor"); }
    // Gumb samo v kanalih, ki priloge res posljejo (e-posta, Telegram, Matrix - pove Safeer OS).
    $("sporocilaPrilozi").hidden = !(pogovor.kanal || {}).priloge;
    var pano = $("sporocilaPano"); pano.hidden = false; pano.title = t("pokaziPano"); pano.setAttribute("aria-label", t("pokaziPano"));
    pano.setAttribute("aria-pressed", S.sporocilaPanoOdprt ? "true" : "false");
    $("sporocilaPanoVsebina").hidden = !S.sporocilaPanoOdprt;
    narisiKanalOdgovora(oseba, pogovor);
    posodobiPoslji();
    narisiPano(oseba, pogovor, []);
    naloziVsebinoPogovora(pogovor, true);
  }
  // Ozko okno (en stolpec): nazaj na seznam, fokus na vrstico pogovora, ki je bil odprt.
  function nazajNaSeznam() {
    var nab = document.querySelector("#r-sporocila .nabiralnik"); if (nab) nab.classList.remove("pogovor-odprt");
    zapriVgrajenKanal();
    var a = S.sporocilaAktivni, cilj = $("sporocilaSeznam");
    var v = a && cilj ? Array.prototype.filter.call(cilj.querySelectorAll(".vrstica-pogovora[data-kljuc]"), function (x) {
      return x.getAttribute("data-kljuc") === a.kanal_id + "\u0001" + a.id; })[0] : null;
    if (v) v.focus(); else if ($("sporocilaIskanje")) $("sporocilaIskanje").focus();
  }
  function narisiPano(oseba, pogovor, sporocila) {
    S.sporocilaZadnjaVsebina = sporocila || [];
    if (S.sporocilaPanoOseba !== oseba.id) { S.sporocilaPanoOseba = oseba.id; $("panoIskanjeVnos").value = ""; $("panoZadetki").innerHTML = ""; }
    $("panoAvatar").textContent = zacetnice(oseba.ime); $("panoIme").textContent = oseba.ime;
    $("panoPrivzeto").textContent = (oseba.lastno_ime && oseba.privzeto_ime && oseba.privzeto_ime !== oseba.ime) ? t("privzetoIme", { ime: oseba.privzeto_ime }) : "";
    $("panoAvatar").style.background = barvaAvatarja(oseba.id || oseba.ime);
    // Povezani viri: kanali, po katerih je ta oseba res dosegljiva (njeni pogovori v nabiralniku); klik odpre pogovor.
    var viri = $("panoViri"); viri.innerHTML = "";
    pogovoriOsebe(oseba).forEach(function (p) {
      var zdaj = p.id === pogovor.id && p.kanal_id === pogovor.kanal_id, n = Number(p.neprebrano) || 0;
      var b = el("button", "povezan-vir" + (zdaj ? " izbran" : ""), znakKanala(p.kanal) + '<span><b>' + ubezi((p.kanal || {}).ime || p.kanal_id) +
        '</b><small>' + ubezi(p.zadeva && (p.kanal || {}).vrsta === "email" ? p.zadeva : relativniCas(p.cas)) + '</small></span>' +
        (n ? '<i class="neprebrano-pika" aria-hidden="true"></i>' : ''));
      b.type = "button";
      if (zdaj) b.setAttribute("aria-current", "true");
      if (n) b.setAttribute("aria-label", b.textContent + ", " + t("spNeprebranih", { n: n }));
      b.addEventListener("click", function () { if (!zdaj) odpriPogovor(oseba, p); });
      viri.appendChild(b);
    });
    var oz = $("panoOznake"); oz.innerHTML = "";
    (pogovor.oznake || []).forEach(function (o) {
      var c = el("span", "", ubezi(o)); var x = el("button", "", "×"); x.type = "button"; x.title = t("odstrani");
      x.addEventListener("click", function () { shraniOznake(pogovor, (pogovor.oznake || []).filter(function (y) { return y !== o; })); });
      c.appendChild(x); oz.appendChild(c);
    });
    var idn = $("panoIdentitete"); idn.innerHTML = "";
    var identitete = oseba.identitete || [];
    if (!identitete.length && pogovor.id && (pogovor.kanal || {}).vrsta === "email") identitete = [["email", pogovor.id]];
    identitete.forEach(function (i) {
      var v = Array.isArray(i) ? i : [i.vrsta, i.naslov];
      var vr = el("span", "identiteta", ubezi((v[0] ? v[0] + ": " : "") + (v[1] || "")));
      if (identitete.length > 1) {
        var r = el("button", "", ubezi(t("osebaRazdruzi"))); r.type = "button"; r.className = "gumb"; r.style.cssText = "padding:2px 8px;font-size:11px";
        r.addEventListener("click", function () { klic("sporocilaRazdruzi", [oseba.id, [v[0], v[1]]]).then(posodobiSeznamIzOdgovora).catch(function (e) { obvesti(typeof e === "string" && e ? e : t("niUspelo")); }); });
        vr.appendChild(r);
      }
      idn.appendChild(vr);
    });
    if (!idn.children.length) idn.appendChild(el("span", "identiteta", ubezi(pogovor.id || "")));
    // »Vedno prikazi slike od …« (izbrano v oknu izvirnika): tu se preklice.
    var slikeVedno = (pogovor.kanal || {}).vrsta === "email" && (S.slikeOd || []).indexOf(String(pogovor.id || "").toLowerCase()) >= 0;
    $("panoSlikeSkupina").hidden = !slikeVedno;
    $("panoSlikePreklici").onclick = function () {
      klic("sporocilaSlikeOd", [pogovor.id, false]).then(function (seznam) { S.slikeOd = seznam || []; narisiPano(oseba, pogovor, S.sporocilaZadnjaVsebina); },
        function (e) { obvesti(napakaSporocil(e)); });
    };
    var pr = $("panoPriponke"); pr.innerHTML = "";
    var priponke = [];
    (sporocila || []).forEach(function (s) { pravePriponke(s).forEach(function (a) { priponke.push([s, a]); }); });
    if (!priponke.length) pr.appendChild(el("p", "drobno", ubezi(t("panoNiPriponk"))));
    var seznamP = el("div", "priponke priponke-pano");
    priponke.slice(-12).reverse().forEach(function (x) { seznamP.appendChild(cipPriponke(pogovor.kanal_id, x[0], x[1])); });
    if (priponke.length) pr.appendChild(seznamP);
  }
  /* ---- Sporocila: kopiranje ----------------------------------------------------------------------------------
     Besedilo sporocila se da oznaciti z misko in kopirati (Ctrl+C); desni klik, tipka Meni ali Shift+F10 na mehurcku
     odpre meni (Kopiraj izbrano / Kopiraj sporocilo / Odpri povezavo). Do Safeer OS 0.4.65 je bila vsa stran
     neizberljiva (user-select: none), sistemski meni pogleda je izklopljen, svojega menija pa mehurcek ni imel -
     sporocila ni bilo mogoce kopirati. */
  // Podpis sporocila: po njem ob osvezitvi pogovora vemo, ali je ze narisani mehurcek se pravi.
  function podpisSporocila(s) {
    return String(s.id == null ? "" : s.id) + "\u0001" + (s.smer || "") + "\u0001" + (s.cas || "") + "\u0001" + (s.besedilo || "") +
      "\u0001" + (s.stanje === "caka" || s.stanje === "napaka" ? s.stanje : "");
  }
  // Sporocilo je ena sama spletna povezava: meni ponudi se »Odpri povezavo« (kot Safeer OS na telefonu).
  // Besedilo pride od drugod (e-posta, klepet, druga naprava), zato ponudimo samo naslov, pri katerem uporabnik vidi,
  // kam vodi - meni ob postavki pokaze gostitelja, kot ga razume brskalnik:
  //   - samo http in https (velikost crk v shemi ni pomembna: telefonske tipkovnice pisejo »Https://«);
  //   - brez uporabniskega imena ali gesla pred gostiteljem (https://banka.example@drugje.example/ vodi na drugje.example);
  //   - brez posevnice nazaj, nevidnih znakov in znakov za smer pisanja (naslov bi se bral drugace, kot ga razume brskalnik).
  // Vrne { naslov, gostitelj } - naslov v obliki, kot ga je razclenil brskalnik - ali null.
  var SPOR_NEVIDNI_ZNAKI = /[\u0000-\u0020\u007f-\u00a0\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f\u2000-\u200f\u2028-\u202f\u205f-\u206f\u3000\u3164\ufe00-\ufe0f\ufeff\uffa0\ufff0-\uffff]|\ud834[\udd73-\udd7a]|\udb40[\udc00-\uddef]/;
  function povezavaSporocila(besedilo) {
    var b = String(besedilo == null ? "" : besedilo).trim(), u;
    if (!b || b.length > 2048 || !/^https?:\/\/[^\s<>"'`\\]+$/i.test(b) || SPOR_NEVIDNI_ZNAKI.test(b)) return null;
    try { u = new URL(b); } catch (e) { return null; }
    if ((u.protocol !== "http:" && u.protocol !== "https:") || !u.hostname || u.username || u.password) return null;
    return { naslov: u.href, gostitelj: u.host };
  }
  // Gostitelj za napis v meniju: pri zelo dolgem ostane viden konec (domena), ne zacetek, ki ga doloca posiljatelj.
  function gostiteljZaNapis(g) {
    g = String(g || "");
    return g.length > 48 ? "…" + g.slice(g.length - 47) : g;
  }
  // Postavke menija mehurcka: [kljuc besedila, dejanje, podatek, dodatek k napisu].
  function postavkeMenijaSporocila(besedilo, izbrano) {
    var p = [], url = povezavaSporocila(besedilo);
    if (izbrano && izbrano !== besedilo) p.push(["sporKopirajIzbrano", "kopiraj", izbrano]);
    if (besedilo) p.push(["sporKopiraj", "kopiraj", besedilo]);
    if (url) p.push(["sporOdpriPovezavo", "odpri", url.naslov, gostiteljZaNapis(url.gostitelj)]);
    return p;
  }
  function mehurcekSporocila(s) {
    var m = el("div", "mehurcek " + (s.smer === "ven" ? "ven" : "noter")), b = el("span", "mehurcek-besedilo");
    m._besedilo = s.besedilo || ""; m._podpis = podpisSporocila(s); m._id = s.id; m.tabIndex = -1;
    var deli = razdeliKodo(m._besedilo);
    b.textContent = deli[0];
    if (deli[0]) m.appendChild(b);
    if (deli[1]) {
      // Popravek (git format-patch, diff) v pismu: pisava enake sirine, vrstice se ne lomijo, drsnik v mehurcku.
      var k = el("pre", "mehurcek-koda"); k.textContent = deli[1];
      m.classList.add("s-kodo"); m.appendChild(k);
    }
    dodajPriponke(m, s, (S.sporocilaAktivni || {}).kanal_id || "");
    if (s.stanje === "caka" || s.stanje === "napaka") {
      // Neposlano (ni povezave ali zavrnjeno): ura namesto casa in »Preklici« - poslje se samo, ko se povezava vrne.
      m.classList.add(s.stanje === "caka" ? "caka" : "napaka");
      var st = el("div", "mehurcek-stanje");
      st.appendChild(el("time", "", ubezi(s.stanje === "caka" ? "\u23F1 " + t("sporCaka") : t("sporNiPoslano"))));
      var pr = el("button", "mehurcek-preklici", ubezi(t("sporPreklici"))); pr.type = "button";
      pr.addEventListener("click", function (e) {
        e.stopPropagation();
        var a = S.sporocilaAktivni; if (!a) return;
        pr.disabled = true;
        klic("sporocilaPreklici", [a.kanal_id, a.id, s.id]).then(function () {
          obvesti(t("sporPreklicano")); naloziVsebinoPogovora(a); naloziSporocila();
        }, function (napaka) { pr.disabled = false; obvesti(typeof napaka === "string" && napaka ? napaka : t("niUspelo")); });
      });
      st.appendChild(pr);
      m.appendChild(st);
      return m;
    }
    var ura = el("time", "", ubezi(kratekCas(s.cas)));
    // Ena kljukica = streznik kanala je sporocilo sprejel (stanje »poslano«). »Prebrano« pri prejemniku ne sporoca noben
    // kanal v Safeerju, zato dvojne kljukice ni.
    if (s.smer === "ven" && s.stanje === "poslano") {
      var kl = el("span", "kljukica", svg("kljukica")); kl.setAttribute("role", "img"); kl.setAttribute("aria-label", t("spPoslano"));
      ura.appendChild(kl);
    }
    m.appendChild(ura);
    return m;
  }
  /* ---- Sporocila: priponke ---------------------------------------------------------------------------------
     Lastnik, 15. 10. 2026: »Sporocila morajo znati zaznati priloge in jih tudi prenesti. Ce je pdf dokument ali doc se
     pripravi predogled. Uporabnik ne sme pogresati na primer Gmail ali Outlook.« Pod mehurckom so cipi priponk (ikona po
     vrsti, ime, velikost): klik odpre predogled v oknu Safeer OS (core/os_predogled.py), gumb ob cipu prenese v Prejemi
     z napredkom. Slike dobijo slicico; slike v vrstici HTML (logotipi v podpisu) so v »Prikazi izvirnik«. Kaj se da
     predogledati in kaj je nevarno, pove Safeer OS (core/predogled_datotek.py) - ena pravila za vse. */
  var NAJVEC_PRILOG = 25 * 1024 * 1024;           // Gmail, Outlook.com: 25 MB na pismo (core/sporocila/priponke.py)
  S.priloge = { odgovor: [], novo: [] };
  var CIPI_PRIPONK = Object.create(null);          // kanal|sporocilo|kljuc -> cipi (napredek prenosa)
  function kljucCipa(kanal, sid, kljuc) { return kanal + "\u0001" + sid + "\u0001" + kljuc; }
  function napakaSporocil(e) {
    var k = typeof e === "string" ? e : "";
    if (k && BESEDILA_OS.en[k] != null) return t(k);
    return k || t("niUspelo");
  }
  function pravePriponke(s) { return (s.priponke || []).filter(function (a) { return !a.inline; }); }
  // Slika, prilepljena v pismo (ne drobni logotip v podpisu): v mehurcku kot slicica, sicer bi jo besedilo skrilo.
  function slikeVVrstici(s) {
    return (s.priponke || []).filter(function (a) { return a.inline && a.predogled === "slika" && a.velikost >= 20480; });
  }
  function ikonaPriponke(a) {
    if (a.nevarna) return "program";
    if (/^video\//.test(a.tip)) return "video";
    if (/^audio\//.test(a.tip)) return "glasba";
    if (/zip|rar|7z|x-tar|gzip|compressed/.test(a.tip) || /\.(zip|rar|7z|tar|gz|tgz|xz|bz2)$/i.test(a.ime)) return "arhiv";
    return { slika: "slika", pdf: "dokument", dokument: "dokument", besedilo: "dokument", tabela: "dokument",
             html: "datoteka", posta: "sporocila" }[a.predogled] || "datoteka";
  }
  function dodajPriponke(m, s, kanal) {
    var prave = pravePriponke(s), slike = slikeVVrstici(s);
    if (!prave.length && !slike.length && !s.html) return;
    var okvir = el("div", "priponke");
    slike.concat(prave).forEach(function (a) { okvir.appendChild(cipPriponke(kanal, s, a)); });
    var dejanja = el("div", "priponke-dejanja");
    if (prave.length > 1) {
      var vse = el("button", "gumb", svg("prenos") + "<span>" + ubezi(t("priponkePrenesiVse")) + "</span>"); vse.type = "button";
      vse.addEventListener("click", function (e) { e.stopPropagation(); prenesiVse(kanal, s, prave, vse); });
      dejanja.appendChild(vse);
    }
    if (s.html) {
      var izv = el("button", "gumb", ubezi(t("priponkaIzvirnik"))); izv.type = "button";
      izv.title = t("priponkaIzvirnikNamig");
      izv.addEventListener("click", function (e) {
        e.stopPropagation();
        var naslov = ((S.sporocilaAktivni || {}).zadeva || "") || $("sporocilaNaslov").textContent;
        klic("sporocilaIzvirnik", [kanal, s.id, naslov]).catch(function (x) { obvesti(napakaSporocil(x)); });
      });
      dejanja.appendChild(izv);
    }
    if (okvir.children.length) m.appendChild(okvir);
    if (dejanja.children.length) m.appendChild(dejanja);
  }
  function cipPriponke(kanal, s, a) {
    // Slicica: slike in prva stran PDF (kot Gmail; lastnik 15. 10. 2026: »PDF nima predogleda«). Meje so iste kot v
    // core/os_sporocila.priponka_slicica; brez slicice (npr. brez pdftoppm) cip ostane z ikono.
    var pdf = a.predogled === "pdf" && !a.nevarna && a.velikost <= 25 * 1024 * 1024;
    var slika = pdf || (a.predogled === "slika" && !a.nevarna && a.velikost <= 10 * 1024 * 1024);
    var c = el("div", "priponka" + (a.nevarna ? " nevarna" : "") + (slika ? " s-sliko" : "") + (pdf ? " s-stranjo" : ""));
    var glavni = el("button", "priponka-odpri"); glavni.type = "button";
    glavni.innerHTML = '<span class="priponka-ikona">' + svg(ikonaPriponke(a)) + '</span><span class="priponka-besedilo"><b>' +
      ubezi(a.ime) + '</b><small>' + ubezi((a.velikost ? velikost(a.velikost) : "") + (a.nevarna ? " · " + t("priponkaNevarna") : "")) + "</small></span>";
    glavni.title = a.nevarna ? t("priponkaNevarna") : t(a.predogled ? "priponkaPredogled" : "priponkaPrenesi");
    glavni.addEventListener("click", function (e) { e.stopPropagation(); odpriPriponko(kanal, s, a, c); });
    var prenos = el("button", "gumb-ikona priponka-prenesi", svg("prenos")); prenos.type = "button";
    prenos.title = t("priponkaPrenesi"); prenos.setAttribute("aria-label", prenos.title + ": " + a.ime);
    prenos.addEventListener("click", function (e) { e.stopPropagation(); prenesiPriponko(kanal, s, a, c); });
    c.appendChild(glavni); c.appendChild(prenos); c.appendChild(el("span", "priponka-napredek"));
    var k = kljucCipa(kanal, s.id, a.kljuc);
    (CIPI_PRIPONK[k] = (CIPI_PRIPONK[k] || []).filter(function (x) { return x.isConnected; })).push(c);
    if (slika) slicicaKoVidna(c, function () {
      klic("sporocilaSlicicaPriponke", [kanal, s.id, a.kljuc]).then(function (uri) {
        if (!uri) return;
        var img = el("img"); img.alt = ""; img.src = uri; img.decoding = "async";
        var ik = c.querySelector(".priponka-ikona"); if (ik) { ik.innerHTML = ""; ik.appendChild(img); }
      }, function () {});
    });
    return c;
  }
  // Slicica se nalozi sele, ko je cip na zaslonu (dolg pogovor ne prenese vseh slik naenkrat).
  var opazovalecSlicic = null;
  function slicicaKoVidna(c, nalozi) {
    if (!window.IntersectionObserver) { nalozi(); return; }
    if (!opazovalecSlicic) opazovalecSlicic = new IntersectionObserver(function (vnosi) {
      vnosi.forEach(function (v) {
        if (!v.isIntersecting || !v.target._nalozi) return;
        var f = v.target._nalozi; v.target._nalozi = null; opazovalecSlicic.unobserve(v.target); f();
      });
    }, { rootMargin: "200px" });
    c._nalozi = nalozi; opazovalecSlicic.observe(c);
  }
  function potrdiNevarno(ime, nadaljuj) {
    $("nevarnoOpis").textContent = t("priponkaNevarnaOpis", { ime: ime });
    S.nevarnoNadaljuj = nadaljuj; $("slojNevarno").classList.add("viden");
    setTimeout(function () { $("nevarnoPreklici").focus(); }, 30);
  }
  function odpriPriponko(kanal, s, a, c) {
    // Program ali skripta: brez predogleda; ponudimo prenos po potrditvi (kot Gmail, ki jih ne odpre).
    if (a.nevarna && a.predogled === "nevarno") { prenesiPriponko(kanal, s, a, c); return; }
    if (!a.predogled) { prenesiPriponko(kanal, s, a, c); return; }
    klic("sporocilaPredogled", [kanal, s.id, a.kljuc]).catch(function (e) { obvesti(napakaSporocil(e)); });
  }
  function nastaviNapredek(c, delez) {
    c.style.setProperty("--napredek", Math.round(Math.max(0, Math.min(1, delez)) * 100) + "%");
  }
  function napredekPriponke(d) {
    (CIPI_PRIPONK[kljucCipa(d.kanal, d.sid, d.kljuc)] || []).forEach(function (c) {
      if (!c.classList.contains("prenasam")) return;
      nastaviNapredek(c, Number(d.delez) || 0);
      var g = c.querySelector(".priponka-prenesi"); if (g) g.title = t("priponkaPrenasam", { odstotek: Math.round(100 * (Number(d.delez) || 0)) });
    });
  }
  function priponkaShranjena(d) {
    (CIPI_PRIPONK[kljucCipa(d.kanal, d.sid, d.kljuc)] || []).forEach(function (c) { c.classList.add("shranjeno"); c._pot = d.pot; });
  }
  function prenesiPriponko(kanal, s, a, c) {
    function zacni() {
      if (c.classList.contains("prenasam")) return;
      c.classList.add("prenasam"); nastaviNapredek(c, 0);
      klic("sporocilaPrenesiPriponko", [kanal, s.id, a.kljuc]).then(function (r) {
        c.classList.remove("prenasam");
        priponkaShranjena({ kanal: kanal, sid: s.id, kljuc: a.kljuc, pot: r.pot });
        obvestiShranjeno(t("priponkaShranjena", { ime: r.ime }), r.pot, a.nevarna);
      }, function (e) { c.classList.remove("prenasam"); obvesti(napakaSporocil(e)); });
    }
    if (a.nevarna) potrdiNevarno(a.ime, zacni); else zacni();
  }
  function prenesiVse(kanal, s, prave, gumb) {
    function zacni() {
      gumb.disabled = true;
      prave.forEach(function (a) { (CIPI_PRIPONK[kljucCipa(kanal, s.id, a.kljuc)] || []).forEach(function (c) { c.classList.add("prenasam"); nastaviNapredek(c, 0); }); });
      klic("sporocilaPrenesiVse", [kanal, s.id]).then(function (r) {
        gumb.disabled = false;
        prave.forEach(function (a) { (CIPI_PRIPONK[kljucCipa(kanal, s.id, a.kljuc)] || []).forEach(function (c) { c.classList.remove("prenasam"); c.classList.add("shranjeno"); }); });
        var poti = (r && r.poti) || [];
        obvestiShranjeno(t(r && r.napake ? "priponkeShranjeneDelno" : "priponkeShranjene", { n: poti.length }), poti[0] || "", true);
      }, function (e) {
        gumb.disabled = false;
        prave.forEach(function (a) { (CIPI_PRIPONK[kljucCipa(kanal, s.id, a.kljuc)] || []).forEach(function (c) { c.classList.remove("prenasam"); }); });
        obvesti(napakaSporocil(e));
      });
    }
    if (prave.some(function (a) { return a.nevarna; })) potrdiNevarno(prave.filter(function (a) { return a.nevarna; }).map(function (a) { return a.ime; }).join(", "), zacni);
    else zacni();
  }
  // Obvestilo po prenosu z gumboma »Odpri« in »Pokazi v mapi« (8 s). Nevarne datoteke ne ponudimo odpreti.
  function obvestiShranjeno(besedilo, pot, brezOdpri) {
    var o = $("obvestilo");
    o.textContent = ""; o.appendChild(el("span", "", ubezi(besedilo)));
    if (pot && !brezOdpri) {
      var g1 = el("button", "", ubezi(t("priponkaOdpri"))); g1.type = "button";
      g1.addEventListener("click", function () { klic("odpriDatoteko", [pot]); o.classList.remove("viden", "z-gumbom"); });
      o.appendChild(g1);
    }
    if (pot) {
      var g2 = el("button", "", ubezi(t("priponkaMapa"))); g2.type = "button";
      g2.addEventListener("click", function () { klic("pokaziVMapi", [pot]); o.classList.remove("viden", "z-gumbom"); });
      o.appendChild(g2);
    }
    o.classList.add("viden", "z-gumbom");
    clearTimeout(obvestiloCas);
    obvestiloCas = setTimeout(function () { o.classList.remove("viden", "z-gumbom"); }, 8000);
  }
  // ---- priloge pri pisanju (»Prilozi«, povleci in spusti)
  function skupajPrilog(kje) { return S.priloge[kje].reduce(function (v, p) { return v + (Number(p.velikost) || 0); }, 0); }
  function prilogePrevelike(kje) { return skupajPrilog(kje) > NAJVEC_PRILOG; }
  function narisiPriloge(kje) {
    var cilj = $(kje === "novo" ? "novoPriloge" : "sporocilaPriloge"); if (!cilj) return;
    cilj.innerHTML = "";
    S.priloge[kje].forEach(function (p, i) {
      var c = el("span", "priloga", svg("sponka") + "<b>" + ubezi(p.ime) + "</b><small>" + ubezi(velikost(p.velikost || 0)) + "</small>");
      var x = el("button", "", "×"); x.type = "button"; x.title = t("prilogaOdstrani"); x.setAttribute("aria-label", t("prilogaOdstrani") + ": " + p.ime);
      x.addEventListener("click", function () { S.priloge[kje].splice(i, 1); narisiPriloge(kje); });
      c.appendChild(x); cilj.appendChild(c);
    });
    if (prilogePrevelike(kje)) cilj.appendChild(el("span", "priloge-napaka", ubezi(t("priloge_prevelike"))));
    cilj.hidden = !S.priloge[kje].length;
    if (kje === "odgovor") posodobiPoslji();
  }
  function dodajPriloge(kje, nove) {
    (nove || []).forEach(function (p) {
      if (p && p.pot && !S.priloge[kje].some(function (x) { return x.pot === p.pot; })) S.priloge[kje].push(p);
    });
    narisiPriloge(kje);
  }
  function izberiPriloge(kje) {
    klic("izberiPriloge", [t("prilozi"), t("prilozi")]).then(function (p) { dodajPriloge(kje, p); }, function (e) { obvesti(napakaSporocil(e)); });
  }
  function sprejemPrilog(element, kje, dovoljeno) {
    function datoteke(ev) {
      var vrste = ev.dataTransfer && ev.dataTransfer.types ? Array.prototype.slice.call(ev.dataTransfer.types) : [];
      return vrste.indexOf("Files") >= 0 || vrste.indexOf("text/uri-list") >= 0;
    }
    element.addEventListener("dragover", function (ev) {
      if (!dovoljeno() || !datoteke(ev)) return;
      ev.preventDefault(); ev.dataTransfer.dropEffect = "copy"; element.classList.add("spusti-prilogo");
    });
    element.addEventListener("dragleave", function () { element.classList.remove("spusti-prilogo"); });
    element.addEventListener("drop", function (ev) {
      element.classList.remove("spusti-prilogo");
      if (!dovoljeno() || !datoteke(ev)) return;
      ev.preventDefault();
      // Poti datotek iz Nema WebKitGTK strani ne pove; Safeer OS si jih zapomni ob vstopu vlecenja (spusceneDatoteke).
      klic("spusceneDatoteke").then(function (poti) {
        if (!Array.isArray(poti) || !poti.length) return;
        return klic("opisPrilog", [poti]).then(function (p) { dodajPriloge(kje, p); });
      }).catch(function () {});
    });
  }
  // [besedilo, koda]: koda se zacne pri prvi vrstici popravka (lastnik, 14. 10. 2026: popravek v pismu se je bral
  // kot zmeda prelomljenih vrstic). Brez popravka je koda "".
  var ZACETEK_KODE = /^(From [0-9a-f]{40} |diff --git |Index: |--- a\/|@@ -\d)/m;
  function razdeliKodo(besedilo) {
    var t = String(besedilo || ""), i = t.search(ZACETEK_KODE);
    if (i < 0) return [t, ""];
    return [t.slice(0, i).replace(/\s+$/, ""), t.slice(i).replace(/\s+$/, "")];
  }
  // Besedilo, oznaceno znotraj pogovora ("" = nic ali izbor drugje na strani).
  function izbranoVSporocilih() {
    var izbor = window.getSelection ? window.getSelection() : null, cilj = $("sporocilaVsebina");
    if (!izbor || izbor.isCollapsed || !izbor.rangeCount || !cilj) return "";
    if (!cilj.contains(izbor.anchorNode) || !cilj.contains(izbor.focusNode)) return "";
    var b = String(izbor);
    return b.trim() ? b : "";
  }
  function kopirajBesedilo(besedilo) {
    if (!besedilo) return;
    klic("kopiraj", [besedilo]).then(function (ok) { obvesti(t(ok === false ? "sporNiKopirano" : "sporKopirano")); },
      function () { obvesti(t("sporNiKopirano")); });
  }
  // »Odpri povezavo«: v vgrajenem brskalniku, v novem zavihku (stran, ki jo ima uporabnik tam odprto, ostane).
  function odpriPovezavoSporocila(naslov) {
    return odpriVSpletu(naslov, true).then(function (odprto) {
      // Brskalnik zdaj prekriva vsebino. Dokler bi stran mislila, da je odprt razdelek Sporocila, bi ga zanka
      // osvezevala naprej in nova sporocila odprtega pogovora oznacila kot prebrana, ne da bi jih uporabnik videl.
      // (Samo ce je uporabnik se v Sporocilih: medtem je lahko ze kliknil drug razdelek.)
      if (odprto && S.razdelek === "sporocila") S.razdelek = "splet";
      return odprto;
    });
  }
  var meniSporocilaOb = 0;
  function zapriMeniSporocila() {
    var m = $("sporocilaMeni");
    if (!m || m.hidden) return false;
    m.hidden = true; m.innerHTML = ""; m._za = null;
    return true;
  }
  function pokaziMeniSporocila(mehurcek, x, y, sTipkovnico) {
    var m = $("sporocilaMeni"); if (!m || !mehurcek) return;
    var postavke = postavkeMenijaSporocila(mehurcek._besedilo || "", izbranoVSporocilih());
    m.innerHTML = ""; m._za = mehurcek; meniSporocilaOb = Date.now();
    if (!postavke.length) { m.hidden = true; return; }
    postavke.forEach(function (p) {
      var g = el("button", "", ubezi(t(p[0]) + (p[3] ? " · " + p[3] : ""))); g.type = "button"; g.setAttribute("role", "menuitem");
      // Pritisk na postavko ne sme podreti izbora v sporocilu, dokler dejanje ni izvedeno.
      g.addEventListener("mousedown", function (e) { e.preventDefault(); });
      g.addEventListener("click", function () {
        // S tipkovnico je fokus na postavki, ki z menijem izgine: vrnemo ga na sporocilo (sicer pade na telo strani
        // in puscice ne hodijo vec po sporocilih). Z misko fokusa ne premikamo - izbor cez vec sporocil ostane.
        var za = m._za, sTipk = m.contains(document.activeElement);
        zapriMeniSporocila();
        if (sTipk) fokusNaMehurcek(null, za);
        if (p[1] === "odpri") odpriPovezavoSporocila(p[2]);
        else kopirajBesedilo(p[2]);
      });
      m.appendChild(g);
    });
    m.hidden = false;
    m.style.left = Math.max(8, Math.min(window.innerWidth - m.offsetWidth - 8, x)) + "px";
    m.style.top = Math.max(8, Math.min(window.innerHeight - m.offsetHeight - 8, y)) + "px";
    if (sTipkovnico && m.firstChild) m.firstChild.focus();
  }
  // Fokus na sporocilo s tipkovnico: premaknemo samo seznam sporocil. Brskalnikov focus() visok mehurcek sredini
  // in pri tem premakne tudi celo stran (glava Safeer OS je sla delno z zaslona) - zato brez njegovega pomika.
  function fokusNaMehurcek(cilj, m) {
    if (!m || !m.focus) return;
    // Po kliku z misko brskalnik obrobe fokusa (:focus-visible) ne pokaze vec, zato jo oznacimo sami.
    if (m.classList) m.classList.add("fokus-tipke");
    m.focus({ preventScroll: true });
    if (!cilj || !m.getBoundingClientRect) return;
    var rc = cilj.getBoundingClientRect(), rm = m.getBoundingClientRect();
    if (rm.top < rc.top) cilj.scrollTop -= rc.top - rm.top + 8;
    else if (rm.bottom > rc.bottom) cilj.scrollTop += Math.max(0, Math.min(rm.top - rc.top - 8, rm.bottom - rc.bottom + 8));
  }
  // Tab pride na zadnje sporocilo (med sporocili puscici gor/dol), ne na vsako posebej.
  function uskladiTabMehurckov(cilj) {
    var zadnji = cilj.lastElementChild;
    Array.prototype.forEach.call(cilj.children, function (m) { m.tabIndex = m === zadnji ? 0 : -1; });
  }
  // Kaj od narisanega ostane: mehurcki z enakim podpisom ostanejo ISTI elementi (izbor besedila in meni se ne podreta),
  // novi se naredijo, odvecni odpadejo. Pogovor kaze zadnjih 50 sporocil: z vrha lahko kaksno odpade, na dnu pridejo
  // nova, pozno dostavljeno sporocilo (cakalo je v vrsti) pa se po casu uvrsti vmes.
  function nacrtMehurckov(cilj, seznam) {
    var stari = Object.create(null), novi = [], odvec = [];
    Array.prototype.forEach.call(cilj.children, function (m) { (stari[m._podpis] = stari[m._podpis] || []).push(m); });
    seznam.forEach(function (s) {
      var isti = stari[podpisSporocila(s)];
      novi.push(isti && isti.length ? isti.shift() : mehurcekSporocila(s));
    });
    Object.keys(stari).forEach(function (k) { odvec = odvec.concat(stari[k]); });
    return { novi: novi, odvec: odvec };
  }
  function enakiMehurcki(cilj, novi) {
    if (cilj.children.length !== novi.length) return false;
    for (var i = 0; i < novi.length; i++) if (cilj.children[i] !== novi[i]) return false;
    return true;
  }
  // Sidro pogleda: prvi mehurcek, ki sega v vidni del seznama in po osvezitvi ostane. Ko se vsebina nad njim spremeni
  // (z vrha odpade staro sporocilo, vmes se uvrsti pozno dostavljeno), ga vrnemo na isto mesto. Racunamo iz polozaja na
  // zaslonu, ne iz visin: brskalnik pomik ob krajsanju vsebine omeji sam, zato bi odstranjeno visino sicer odsteli dvakrat.
  function sidroSporocil(cilj, ostane) {
    var vrh = cilj.getBoundingClientRect().top, i, m, r;
    for (i = 0; i < cilj.children.length; i++) {
      m = cilj.children[i];
      if (!ostane(m)) continue;
      r = m.getBoundingClientRect();
      if (r.bottom > vrh) return { m: m, odmik: r.top - vrh };
    }
    return null;
  }
  var sporocilaLastenPomikOb = 0;      // kdaj smo pomik seznama nazadnje popravili sami (dogodek scroll pride za tem)
  function vrniSidroSporocil(cilj, sidro) {
    if (!sidro || sidro.m.parentNode !== cilj) return;
    var premik = sidro.m.getBoundingClientRect().top - cilj.getBoundingClientRect().top - sidro.odmik;
    if (Math.abs(premik) >= 1) { sporocilaLastenPomikOb = Date.now(); cilj.scrollTop += premik; }
  }
  // Pomik seznama zapre meni sporocila - razen kadar smo pomik pravkar popravili sami: sporocilo z menijem je ostalo na
  // istem mestu, uporabnik pa sredi izbire.
  function obPomikuSporocil() {
    if (Date.now() - sporocilaLastenPomikOb > 150) zapriMeniSporocila();
  }
  var sporocilaZahteva = 0, sporocilaNaDno = "";
  // odpiranje = uporabnik je pogovor odprl sam (klik, poslano sporocilo): pogled gre na zadnje sporocilo.
  function uporabnikVidi() {
    return document.visibilityState !== "hidden" && (typeof document.hasFocus !== "function" || document.hasFocus());
  }
  // Vrnitev v okno z odprtim pogovorom, ki ima medtem prispela neprebrana pisma: zdaj jih uporabnik vidi.
  if (typeof window.addEventListener === "function") window.addEventListener("focus", function () {
    var a = S.sporocilaAktivni;
    if (S.razdelek === "sporocila" && a && Number(a.neprebrano) > 0) naloziVsebinoPogovora(a, false);
  });
  function naloziVsebinoPogovora(pogovor, odpiranje) {
    var kljuc = pogovor.kanal_id + "\u0001" + pogovor.id, zahteva = ++sporocilaZahteva;
    // Velja do prvega izrisa TEGA pogovora, tudi ce ga narise odgovor na poznejso zahtevo: po poslanem sporocilu
    // osvezitev seznama pogovor zahteva se enkrat (brez »odpiranje«), odgovor na prvo zahtevo pa se zavrze.
    if (odpiranje) sporocilaNaDno = kljuc;
    // Branje pogovora ga oznaci kot prebranega (tudi na strezniku). Osvezitev v ozadju - okno ni v ospredju ali je
    // skrito - pisem, ki jih uporabnik ni videl, ne sme oznaciti: ostanejo neprebrana z znacko in obvestilom, kot v
    // Gmailu in Outlooku (lastnik, 15. 10. 2026: novo pismo je prislo brez znacke). Oznaci jih vrnitev v okno.
    klic("sporocilaPogovor", [pogovor.kanal_id, pogovor.id, !!odpiranje || uporabnikVidi()]).then(function (seznam) {
      // Uporabnik je medtem odprl drug pogovor, ali pa je za tega ze poslana novejsa zahteva (odgovori ne pridejo
      // nujno v vrstnem redu zahtev - starejsi ne sme povoziti novejsega).
      if (S.sporocilaAktivni !== pogovor || zahteva !== sporocilaZahteva) return;
      seznam = seznam || [];
      var cilj = $("sporocilaVsebina"), meni = $("sporocilaMeni"), i;
      var naDno = sporocilaNaDno === kljuc;
      if (naDno) sporocilaNaDno = "";
      if (cilj._kljuc !== kljuc || !cilj.children.length) {
        // Drug pogovor: narisemo vse in pokazemo zadnje sporocilo.
        zapriMeniSporocila(); cilj.innerHTML = ""; cilj._kljuc = kljuc;
        seznam.forEach(function (s) { cilj.appendChild(mehurcekSporocila(s)); });
        naDno = true;
      } else {
        var nacrt = nacrtMehurckov(cilj, seznam);
        if (!enakiMehurcki(cilj, nacrt.novi)) {
          var naDnu = cilj.scrollHeight - cilj.scrollTop - cilj.clientHeight < 60;
          var sidro = naDno ? null : sidroSporocil(cilj, function (m) { return nacrt.odvec.indexOf(m) < 0; });
          nacrt.odvec.forEach(function (m) {
            if (meni && meni._za === m) zapriMeniSporocila();
            cilj.removeChild(m);
          });
          // Mehurcki, ki ostanejo, so ze v pravem medsebojnem redu (seznam je urejen po casu): vstavijo se samo novi.
          for (i = 0; i < nacrt.novi.length; i++) {
            if (cilj.children[i] !== nacrt.novi[i]) cilj.insertBefore(nacrt.novi[i], cilj.children[i] || null);
          }
          // Sprememba pomakne pogled na zadnje sporocilo samo, ce uporabnik bere zadnja sporocila in nicesar ne
          // oznacuje ali izbira v meniju; sicer ostane to, kar bere, na istem mestu.
          if (naDnu && !izbranoVSporocilih() && (!meni || meni.hidden)) naDno = true;
          else vrniSidroSporocil(cilj, sidro);
        }
      }
      var oznacen = null;
      if (S.sporocilaOznaciId != null) {
        Array.prototype.forEach.call(cilj.children, function (m) { if (!oznacen && m._id === S.sporocilaOznaciId) oznacen = m; });
        S.sporocilaOznaciId = null;
      }
      if (oznacen) { oznacen.classList.add("zadetek-iskanja"); oznacen.scrollIntoView({ block: "center" }); }
      else if (naDno) cilj.scrollTop = cilj.scrollHeight;
      uskladiTabMehurckov(cilj);
      if (S.sporocilaOseba) narisiPano(S.sporocilaOseba, pogovor, seznam);
      if (pogovor.neprebrano) { pogovor.neprebrano = 0; naloziSporocila(); }
    }, function () {
      // Zahteva je odpovedala: »pogled na zadnje sporocilo« ne caka na naslednjo osvezitev v ozadju.
      if (zahteva === sporocilaZahteva && sporocilaNaDno === kljuc) sporocilaNaDno = "";
    });
  }
  /* Po osvezitvi seznama: odprt pogovor dobi nova sporocila, izginul (odstranjen kanal) se zapre.
     Prej je desna stran ostala na starem stanju, dokler pogovora nisi znova odprl. */
  var sporocilaVrnitev = false;      // uporabnik se je pravkar vrnil v razdelek Sporocila (pojdi)
  function uskladiOdprtPogovor() {
    var vrnitev = sporocilaVrnitev; sporocilaVrnitev = false;
    var a = S.sporocilaAktivni; if (!a) return;
    var nov = null;
    S.sporocilaSkupine.forEach(function (s) {
      (s.pogovori || []).forEach(function (p) { if (p.id === a.id && p.kanal_id === a.kanal_id) nov = p; });
    });
    if (!nov) {
      S.sporocilaAktivni = null; S.sporocilaOseba = null;
      $("sporocilaNaslov").textContent = t("izberiPogovor"); $("sporocilaPodnaslov").textContent = "";
      $("sporocilaPano").hidden = true; $("sporocilaPanoVsebina").hidden = true;
      $("sporocilaVsebina").innerHTML = ""; $("sporocilaVsebina")._kljuc = "";
      $("sporocilaBesedilo").disabled = true; $("sporocilaVnos").querySelector('button[type="submit"]').disabled = true;
      $("sporocilaAvatar").hidden = true;
      var okno = document.querySelector("#r-sporocila .pogovor-okno"); if (okno) okno.classList.add("brez-pogovora");
      var nab = document.querySelector("#r-sporocila .nabiralnik"); if (nab) nab.classList.remove("pogovor-odprt");
      narisiSporocila();
      return;
    }
    if (nov.cas !== a.cas || nov.zadnje_sporocilo !== a.zadnje_sporocilo || nov.razlicica !== a.razlicica) {
      // Ob vrnitvi v razdelek pokazemo nova sporocila odprtega pogovora: branje pogovora jih oznaci kot prebrana, zato
      // jih mora uporabnik tudi videti. Osvezitev v ozadju pogleda ne premika.
      S.sporocilaAktivni = nov; narisiSporocila(); naloziVsebinoPogovora(nov, vrnitev && Number(nov.neprebrano) > 0);
    }
  }
  // Vec dogodkov v kratkem (20 novih pisem naenkrat) = eno branje seznama.
  var sporocilaDogodekCas = 0;
  function sporocilaSpremenjena() {
    if (sporocilaDogodekCas || !most) return;
    sporocilaDogodekCas = setTimeout(function () {
      sporocilaDogodekCas = 0;
      if (S.razdelek === "sporocila") { naloziSporocila(); return; }
      klic("sporocilaSeznam").then(function (p) {
        S.sporocilaSkupine = p.skupine || []; S.sporocilaKanali = p.kanali || []; S.sporocilaOznakeVse = p.oznake || [];
      }).catch(function () {});
    }, 120);
  }
  var sporocilaCasovnik = 0;
  function sporocilaZanka() {
    if (sporocilaCasovnik) return;
    sporocilaCasovnik = setInterval(function () {
      if (S.razdelek !== "sporocila") { clearInterval(sporocilaCasovnik); sporocilaCasovnik = 0; return; }
      if (skrito()) return;
      naloziSporocila();
    }, 30000);
  }
  function barvaIzImena(s) {
    var h = 0; s = String(s || "");
    for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360;
    return h;
  }
  var kanalPonudnikiPodatki = null;
  function odpriCarovnikKanala() {
    zapriSloje(); $("kanalNapaka").hidden = true; $("kanalPonudnik").value = "";
    $("kanalVrsta").value = "email";
    $("kanalVrstaIzbira").querySelectorAll("button").forEach(function (x) { x.classList.toggle("izbran", x.getAttribute("data-vrsta") === "email"); });
    preklopiKanalPolja(); $("slojKanal").classList.add("viden");
    vkOsveziKatalog();
    if (kanalPonudnikiPodatki) { narisiPonudnike(); return; }
    klic("sporocilaPonudniki", [jezik]).then(function (p) {
      kanalPonudnikiPodatki = p || { ponudniki: [], aplikacije: [] };
      if (VK.katalog) kanalPonudnikiPodatki.klepeti = VK.katalog;
      narisiPonudnike();
    })
      .catch(function () { kanalPonudnikiPodatki = { ponudniki: [{ id: "drug", ime: "", domene: [], geslo: "navadno", navodila: "drug" }], aplikacije: [], klepeti: VK.katalog || [] }; narisiPonudnike(); });
  }
  function navodilaZa(kljuc) {
    var k = { gmail: "navGmail", yahoo: "navYahoo", icloud: "navIcloud", gmx: "navGmx", zoho: "navZoho", fastmail: "navFastmail", arnes: "navArnes", oauth: "navOauth", drug: "navDrug" }[kljuc] || "navNavadno";
    return t(k);
  }
  function narisiPonudnike() {
    var m = $("kanalPonudnikiMreza"); m.textContent = "";
    (kanalPonudnikiPodatki.ponudniki || []).forEach(function (p) {
      var b = document.createElement("button"); b.type = "button"; b.setAttribute("data-id", p.id);
      var drug = p.id === "drug", oauth = p.geslo === "oauth";
      if (oauth) b.classList.add("ni-na-voljo");
      var ime = document.createElement("b"); ime.textContent = drug ? t("kanalDrugPonudnikIme") : p.ime + (oauth ? "  · " + t("kanalNiNaVoljo") : "");
      var opis = document.createElement("small");
      opis.textContent = drug ? t("kanalDrugPonudnikOpis") : oauth ? "" : (p.domene || []).slice(0, 2).map(function (d) { return "@" + d; }).join(", ");
      var znak = document.createElement("span"); znak.className = "ponudnik-znak"; znak.setAttribute("aria-hidden", "true");
      znak.textContent = drug ? "@" : (p.ime || "?").replace(/[^A-Za-z0-9]/g, "").charAt(0).toUpperCase();
      znak.style.background = drug ? "" : "hsl(" + barvaIzImena(p.id) + ", 45%, 40%)";
      var besedilo = document.createElement("span"); besedilo.className = "ponudnik-besedilo";
      besedilo.appendChild(ime); besedilo.appendChild(opis);
      b.appendChild(znak); b.appendChild(besedilo);
      if (p.geslo === "aplikacije") { var cip = document.createElement("i"); cip.className = "ponudnik-cip"; cip.textContent = t("kanalCipGeslo"); besedilo.appendChild(cip); }
      b.addEventListener("click", function () { izberiPonudnika(p); });
      m.appendChild(b);
    });
    narisiKatalogKanalov($("kanalAplikacijeMreza"));     // vgrajeni kanali (blok »Vgrajeni kanali Sporocil«)
  }
  function izberiPonudnika(p) {
    $("kanalPonudnik").value = p.id; $("kanalNapaka").hidden = true;
    var drug = p.id === "drug";
    $("kanalPonudniki").hidden = true; $("kanalEmail").hidden = false;
    $("kanalNaslov").placeholder = drug ? t("epostniNaslov") : t("kanalNaslovPri", { ime: p.ime });
    $("kanalGeslo").placeholder = p.geslo === "aplikacije" ? t("kanalGesloAplikacije16") : t("kanalNavadnoGeslo");
    $("kanalNavodila").textContent = navodilaZa(p.navodila);
    // Kje najdes geslo za aplikacije: gumb odpre pravo stran ponudnika (uradne strani, glej core/sporocila/ponudniki.py).
    $("kanalStranGesla").hidden = !p.geslo_stran;
    $("kanalStranGesla").setAttribute("data-url", p.geslo_stran || "");
    $("kanalStranGesla").textContent = t("kanalStranGesla", { ime: p.ime || "" });
    $("kanalStrezniki").hidden = !drug; $("kanalNapredno").hidden = drug;
    $("kanalImap").value = drug ? "" : (p.imap + (p.imap_vrata && p.imap_vrata !== 993 ? ":" + p.imap_vrata : ""));
    $("kanalSmtp").value = drug ? "" : (p.smtp + (p.smtp_vrata && p.smtp_vrata !== 465 ? ":" + p.smtp_vrata : ""));
    $("kanalImap").removeAttribute("data-rocno"); $("kanalSmtp").removeAttribute("data-rocno");
    preklopiKanalPolja();
    $("kanalPovezi").disabled = p.geslo === "oauth";
    $("kanalNaslov").focus();
  }
  function preklopiKanalPolja() {
    var v = $("kanalVrsta").value, email = v === "email", ponudnik = $("kanalPonudnik").value;
    $("kanalPonudniki").hidden = !email || !!ponudnik; $("kanalEmail").hidden = !email || !ponudnik;
    $("kanalChatwoot").hidden = v !== "chatwoot"; $("kanalAplikacijeSeznam").hidden = v !== "aplikacije";
    $("kanalApi").hidden = v !== "api"; if (v === "api") preklopiApiProtokol();
    $("kanalPovezi").hidden = v === "aplikacije" || (email && !ponudnik);
    $("kanalSkrivnostOpis").hidden = v === "aplikacije";
    if (v !== "email" || ponudnik) $("kanalPovezi").disabled = false;
  }
  /* Lastni API: Matrix potrebuje streznik + zeton, Telegram Bot samo zeton. Navodila povedo, kje ju dobis. */
  function preklopiApiProtokol() {
    var pr = $("kanalProtokol").value;
    $("kanalApiStreznik").hidden = pr !== "matrix";
    $("kanalApiZeton").placeholder = pr === "matrix" ? t("apiZeton") : "123456:ABC…";
    $("kanalApiNavodila").textContent = t(pr === "matrix" ? "navMatrix" : "navTelegramBot");
  }
  function skupinaZadetkov(cilj, naslov, razred) {
    var g = el("div", "skupina-zadetkov " + (razred || ""));
    g.appendChild(el("h4", "", ubezi(naslov)));
    cilj.appendChild(g);
    return g;
  }
  function fokusPrvegaV(id) {
    setTimeout(function () {
      var prvi = $(id) && $(id).querySelector("button:not([hidden]):not(:disabled), [tabindex='0']");
      if (prvi) prvi.focus();
    }, 230);
  }
  function podatkiNamere(niz) {
    return {
      spletne: spletne(),
      programi: S.programi.concat(vsiProgramiNaprav()),
      datoteke: iskanjeDatotekNiz === niz ? S.iskalneDatoteke : [],
      mediji: medijskiVnosi(),
      naprave: S.vseNaprave.length ? S.vseNaprave : S.naprave,
      sporocila: S.sporocilaSkupine
    };
  }
  function izvediNamero(niz, prisilna) {
    var namera = prisilna || SafeerIskanje.nameraIskanja(niz, podatkiNamere(niz));
    zapriSloje();
    if (namera.vrsta === "splet") {
      pojdi("splet");
      $("spletVnos").value = niz;
      var spletniNaslov = namera.zadetek && namera.zadetek.url;
      if (!spletniNaslov && namera.razlog === "naslov") spletniNaslov = normalizirajNaslov(niz);
      setTimeout(function () {
        if (spletniNaslov) odpriSplet(spletniNaslov);
        else klic("iskanjeSplet", [niz]).catch(function () { obvesti(t("niUspelo")); });
      }, 200);
      return;
    }
    if (namera.vrsta === "programi") {
      S.programIskanje = niz; $("programiIskanje").value = niz; S.skupina = "vse";
      pojdi("programi"); narisiPrograme(); fokusPrvegaV("vsiProgrami"); return;
    }
    if (namera.vrsta === "datoteke") {
      $("datotekeIskanje").value = niz; pojdi("datoteke");
      prikaziIskanjeDatotek(niz, iskanjeDatotekNiz === niz ? S.iskalneDatoteke : null); return;
    }
    if (namera.vrsta === "media") {
      S.mediaIskanje = niz; $("mediaIskanje").value = niz; S.mediaFilter = "vse";
      pojdi("media"); narisiMedije(); fokusPrvegaV("mediaMreza"); return;
    }
    if (namera.vrsta === "naprave") {
      S.napraveIskanje = niz; $("napraveIskanje").value = niz;
      pojdi("naprave"); narisiSeznamNaprav(true); fokusPrvegaV("seznamNaprav");
      return;
    }
    if (namera.vrsta === "sporocila") {
      pojdi("sporocila");
      if (namera.zadetek && namera.zadetek.pogovori && namera.zadetek.pogovori[0]) {
        setTimeout(function () { odpriPogovor(namera.zadetek.oseba, namera.zadetek.pogovori[0]); }, 100);
      }
    }
  }
  function isci() {
    var niz = $("iskanje").value.trim();
    var sloj = $("slojIskanje");
    clearTimeout(iskanjeZamik);
    clearTimeout(iskanjeMedijiZamik);
    if (!niz) { ++iskanjeStevec; sloj.classList.remove("viden"); return; }
    $("slojHitro").classList.remove("viden");
    $("slojNapajanje").classList.remove("viden");
    sloj.classList.add("viden");
    // Plosca zadetkov pod lupo, kjerkoli je (razsirjena ali trak stranske vrstice, ozko okno).
    var lupa = $("iskanjeLupa"), plosca = $("zadetki");
    if (lupa && plosca) {
      var r = lupa.getBoundingClientRect(), z0 = parseFloat(window.getComputedStyle(document.body).zoom) || 1;
      plosca.style.left = Math.max(12, r.left / z0) + "px";
      plosca.style.top = (r.bottom / z0 + 10) + "px";
      // Sirina kot razsirjena lupa (najvec 760 px) - lupa se med tem se razsirja, zato ne njena trenutna sirina.
      plosca.style.width = Math.max(320, Math.min(760, window.innerWidth / z0 - r.left / z0 - 16)) + "px";
    }
    var n = niz.toLowerCase();
    var z = $("zadetki");
    z.innerHTML = "";
    var mestoLokalnihMedijev = el("div", "skupina-zadetkov");
    z.appendChild(mestoLokalnihMedijev);
    // Spletne aplikacije (ime, domena in kratice, npr. yt).
    var spletni = spletne().map(function (a) { return { a: a, ocena: SafeerIskanje.oceniSpletno(a, n) }; })
      .filter(function (x) { return x.ocena > 0; }).sort(function (a, b) { return b.ocena - a.ocena; }).slice(0, 5);
    if (spletni.length) {
      var gSpletne = skupinaZadetkov(z, t("zSpletneAplikacije"));
      spletni.forEach(function (x) {
        gSpletne.appendChild(zadetek(crka(x.a.ime), x.a.ime, x.a.url, function () {
          izvediNamero(niz, { vrsta: "splet", razlog: "aplikacija", zadetek: x.a });
        }));
      });
    }
    // Programi
    var programi = S.programi.concat(vsiProgramiNaprav()).map(function (p) {
      var ocena = ujemanje(p.ime, n) * 10 + ujemanje(p.splosno, n) * 3 + ujemanje((p.kljucne || []).join(" "), n) * 2 +
        ujemanje(p.opis, n);
      if (ocena && p.naprava) ocena -= 1;          // program tega racunalnika ima prednost pred istim na napravi
      return { p: p, ocena: ocena + (ocena ? Math.min(5, p.uporaba || 0) : 0) };
    }).filter(function (x) { return x.ocena > 0; }).sort(function (a, b) { return b.ocena - a.ocena; }).slice(0, 6);
    if (programi.length) {
      var gProgrami = skupinaZadetkov(z, t("zProgrami"));
      programi.forEach(function (x) {
        var n2 = x.p.naprava ? S.naprave.find(function (y) { return y.id === x.p.naprava; }) : null;
        gProgrami.appendChild(zadetek(slikaAliCrka(x.p.ikona, x.p.ime), x.p.ime, n2 ? n2.ime : x.p.opis, function () {
          izvediNamero(niz, { vrsta: "programi", zadetek: x.p });
        }));
      });
    }

    var sporocila = S.sporocilaSkupine.map(function (s) {
      return { s: s, ocena: Math.max(ujemanje(s.oseba.ime, n), ujemanje((s.pogovori || []).map(function (p) {
        return (p.zadeva || "") + " " + (p.zadnje_sporocilo || ""); }).join(" "), n)) };
    }).filter(function (x) { return x.ocena > 0; }).slice(0, 5);
    if (sporocila.length) {
      var gSporocila = skupinaZadetkov(z, t("zSporocila"));
      sporocila.forEach(function (x) {
        gSporocila.appendChild(zadetek("sporocila", x.s.oseba.ime,
          (x.s.pogovori[0] && x.s.pogovori[0].zadnje_sporocilo) || "", function () {
            izvediNamero(niz, { vrsta: "sporocila", zadetek: x.s });
          }));
      });
    }

    // Datoteke so edini diskovni klic in so zamaknjene; mesto ostane pred drugimi skupinami.
    var mestoDatotek = el("div", "skupina-zadetkov");
    z.appendChild(mestoDatotek);

    // Medijski katalog je ze v pomnilniku (programi + shranjeni spletni viri).
    var mediji = medijskiVnosi().map(function (v) {
      var x = v.program || v.spletna;
      return { v: v, x: x, ocena: Math.max(ujemanje(x.ime, n), ujemanje(x.url, n), ujemanje(x.opis, n)) };
    }).filter(function (x) { return x.ocena > 0; }).sort(function (a, b) { return b.ocena - a.ocena; }).slice(0, 5);
    if (mediji.length) {
      var gMediji = skupinaZadetkov(z, t("zMediji"));
      mediji.forEach(function (x) {
        gMediji.appendChild(zadetek(x.v.program ? slikaAliCrka(x.x.ikona, x.x.ime) : crka(x.x.ime),
          x.x.ime, t("mediji"), function () { izvediNamero(niz, { vrsta: "media", zadetek: x.v }); }));
      });
    }

    var naprave = (S.vseNaprave.length ? S.vseNaprave : S.naprave).map(function (naprava) {
      return { n: naprava, ocena: Math.max(ujemanje(naprava.ime, n), ujemanje(naprava.platforma, n), ujemanje(naprava.vrsta, n)) };
    }).filter(function (x) { return x.ocena > 0; }).sort(function (a, b) { return b.ocena - a.ocena; }).slice(0, 5);
    if (naprave.length) {
      var gNaprave = skupinaZadetkov(z, t("zNaprave"));
      naprave.forEach(function (x) {
        gNaprave.appendChild(zadetek(ikonaNaprave(x.n), x.n.ime, "Safeer Link", function () {
          izvediNamero(niz, { vrsta: "naprave", zadetek: x.n });
        }));
      });
    }

    // Safeer Agent (ce je nastavljen): ukaz z besedami, npr. »daj to na TV« - Ctrl+Enter ali ta vrstica.
    if (agentNaVoljo() && niz.length >= 2) {
      skupinaZadetkov(z, t("agentNaslov")).appendChild(zadetek("iskra", t("agentVprasajNiz", { niz: niz }), t("agentZadetekPod"), function () {
        vprasajAgenta(niz);
        $("iskanje").value = ""; zapriSloje(); lupaUredi();
      }));
    }
    // Splet je vedno zadnja skupina.
    var gSplet = skupinaZadetkov(z, t("zSplet"), "spletni-zadetki");
    if (SafeerIskanje.jeNaslov(niz)) {
      var naslov = normalizirajNaslov(niz);
      gSplet.appendChild(zadetek("splet", t("odpriNiz", { naslov: naslov }), naslov, function () {
        izvediNamero(niz, { vrsta: "splet", razlog: "naslov" });
      }));
    }
    gSplet.appendChild(zadetek("isci", t("isciNaSpletuNiz", { niz: niz }), t("splet"), function () {
      izvediNamero(niz, { vrsta: "splet", razlog: "iskanje" });
    }));

    var moj = ++iskanjeStevec;
    if (n.length >= 2) {
      mestoLokalnihMedijev.appendChild(el("h4", "", ubezi(t("zMediji")) +
        ' <span style="opacity:.6;letter-spacing:0;text-transform:none">' + ubezi(t("iscem")) + "</span>"));
      iskanjeMedijiZamik = setTimeout(function () {
        Promise.all([klic("knjiznicaMedijev", ["vse", niz, 0]), klic("tokoviMedijev")]).then(function (rezultati) {
          if (moj !== iskanjeStevec) return;
          mestoLokalnihMedijev.innerHTML = "";
          var datoteke = (rezultati[0] || []).filter(function (v) { return v.naVoljo; }).slice(0, 6);
          var tokovi = (rezultati[1] || []).filter(function (v) { return mediaUstreza(v, n); }).slice(0, 4);
          if (!datoteke.length && !tokovi.length) return;
          mestoLokalnihMedijev.appendChild(el("h4", "", ubezi(t("mediaMojaZbirka"))));
          datoteke.forEach(function (v) {
            mestoLokalnihMedijev.appendChild(zadetek(v.vrsta === "glasba" ? "glasba" : v.vrsta === "slike" ? "slika" : "video",
              v.ime, mediaVrsta(v.vrsta), function () {
                pojdi("media");
                odpriLokalno(v.pot, v.vrsta);
              }));
          });
          tokovi.forEach(function (v) {
            mestoLokalnihMedijev.appendChild(zadetek(v.vrsta === "radio" ? "radio" : "video", v.ime,
              mediaVrsta(v.vrsta), function () {
                pojdi("media");
                odpriTok(v.url);
              }));
          });
        }).catch(function () { if (moj === iskanjeStevec) mestoLokalnihMedijev.innerHTML = ""; });
      }, 200);
      mestoDatotek.appendChild(el("h4", "", ubezi(t("zDatoteke")) + ' <span style="opacity:.6;letter-spacing:0;text-transform:none">' + ubezi(t("iscem")) + "</span>"));
      iskanjeZamik = setTimeout(function () {
        klic("isciDatoteke", [niz]).then(function (seznam) {
          if (moj !== iskanjeStevec) return;
          mestoDatotek.innerHTML = "";
          seznam = (seznam || []).slice(0, 8);
          S.iskalneDatoteke = seznam;
          iskanjeDatotekNiz = niz;
          if (!seznam.length) return;
          mestoDatotek.appendChild(el("h4", "", ubezi(t("zDatoteke"))));
          seznam.forEach(function (d) {
            mestoDatotek.appendChild(zadetek(IKONA_VRSTE[d.vrsta] || "datoteka", d.ime, skrajsajPot(d.pot), function () {
              izvediNamero(niz, { vrsta: "datoteke", zadetek: d });
            }));
          });
        }, function () { mestoDatotek.innerHTML = ""; });
      }, 250);
    }
  }
  function zadetki() { return Array.prototype.slice.call(document.querySelectorAll("#zadetki .zadetek")); }
  function premakniIzbiro(smer) {
    var vsi = zadetki();
    if (!vsi.length) return;
    var i = vsi.findIndex(function (b) { return b.classList.contains("aktiven"); });
    i = i < 0 ? (smer > 0 ? 0 : vsi.length - 1) : Math.max(0, Math.min(vsi.length - 1, i + smer));
    vsi.forEach(function (b, j) { b.classList.toggle("aktiven", j === i); });
    vsi[i].scrollIntoView({ block: "nearest" });
  }

  // ------------------------------------------------------------------ naloga 131: debrid storitve
  // Izbira »Debrid« ob zvrsteh: prek katere storitve (TorBox, Real-Debrid, AllDebrid) gredo torrenti; privzeto tista,
  // za katero je vpisan kljuc. Kljuci se vpisejo v oknu »Debrid storitve«; jedro jih hrani sifrirane, v vmesnik ne pridejo.
  // debridPrazno: cas, ko je most vrnil prazno (null). Takrat pokazemo prazen izbor, a ga NE shranimo: nov poskus ob
  // naslednjem izrisu po vsaj 30 s ali ob zaprtju okna Debrid (pregled 25. 10. 2026 - prej je »Dodaj« ostal do odprtja okna).
  var debridStanje = null, debridNalagam = false, debridPrazno = 0;
  function narisiDebrid(vidno) {
    var polje = $("mediaDebridPolje"), izbira = $("mediaDebrid"); if (!polje || !izbira) return;
    polje.hidden = !vidno;
    if (!vidno) return;
    if (!debridStanje && !(debridPrazno && Date.now() - debridPrazno < 30000)) {
      if (debridNalagam) return;
      debridNalagam = true;
      // Brez stanja (null) ne klicemo znova v neskoncnost - to je zamrznilo stran; pokazemo prazen izbor (»Dodaj«).
      klic("mediaDebrid", []).then(function (s) {
        debridNalagam = false;
        if (s && typeof s === "object") { debridStanje = s; debridPrazno = 0; } else debridPrazno = Date.now();
        narisiDebrid(true);
      }).catch(function () { debridNalagam = false; });
      return;
    }
    var s = debridStanje || { storitve: [] }, z = (s.storitve || []).filter(function (x) { return x.kljuc; });
    izbira.innerHTML = "";
    if (!z.length) izbira.add(new Option(t("debridDodaj"), ""));
    z.forEach(function (x) { izbira.add(new Option((s.oznaka || "⚡") + " " + x.ime, x.id)); });
    if (z.length) izbira.add(new Option(t("debridBrez"), "brez"));
    izbira.add(new Option(t("debridNastavitve"), "nastavitve"));
    izbira.value = z.length ? (s.aktivna || "brez") : "";
    izbira.setAttribute("aria-label", t("debridIzbira")); izbira.title = t("debridIzbira");
    polje.classList.toggle("izbran", !!s.aktivna);
  }
  function izbranDebrid(v) {
    if (v === "nastavitve" || v === "") { narisiDebrid(true); odpriDebrid(); return; }
    klic("mediaDebrid", ["aktivna", v === "brez" ? "" : v]).then(function (s) { debridStanje = s; narisiDebrid(true); })
      .catch(function () {});
  }
  function odpriDebrid() {
    $("slojDebrid").classList.add("viden");
    klic("mediaDebrid", []).then(narisiDebridOkno).catch(function () {});
  }
  function narisiDebridOkno(s) {
    if (!s) return;
    debridStanje = s; narisiDebrid(!$("mediaDebridPolje").hidden);
    var sez = $("debridSeznam"); sez.innerHTML = "";
    (s.storitve || []).forEach(function (x) {
      var vrsta = el("div", "debrid-vrstica");
      var opis = el("div", "debrid-opis");
      opis.appendChild(el("strong", "", ubezi(x.ime)));
      opis.appendChild(el("small", "", ubezi(x.kljuc ? t("debridVpisan") + (x.meritev ? " · " + x.meritev : "") : t("debridKje", { kje: x.kje }))));
      vrsta.appendChild(opis);
      var polje = el("input", ""); polje.type = "password"; polje.autocomplete = "off"; polje.spellcheck = false;
      polje.placeholder = t("debridKljuc"); polje.setAttribute("aria-label", t("debridKljuc") + " – " + x.ime);
      var shrani = el("button", "gumb", ubezi(t("debridShrani"))); shrani.type = "button";
      function shraniKljuc() {
        klic("mediaDebrid", ["kljuc", x.id, polje.value]).then(function (o) {
          polje.value = "";
          obvesti(t(o && o.ok ? "debridShranjen" : "debridNiKljuc", { ime: x.ime }));
          narisiDebridOkno(o);
        }).catch(function () {});
      }
      shrani.addEventListener("click", shraniKljuc);
      polje.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); shraniKljuc(); } });
      vrsta.appendChild(polje); vrsta.appendChild(shrani);
      if (x.kljuc) {
        var odstrani = el("button", "gumb", ubezi(t("debridOdstrani"))); odstrani.type = "button";
        odstrani.addEventListener("click", function () { klic("mediaDebrid", ["pozabi", x.id]).then(narisiDebridOkno).catch(function () {}); });
        vrsta.appendChild(odstrani);
      }
      sez.appendChild(vrsta);
    });
    // Usenet prek TorBoxa: uporabnikov indeksator (Newznab). Naslov in kljuc ostaneta sifrirana na tem racunalniku;
    // nazaj dobimo samo gostitelja.
    var u = s.usenet || {}, uv = el("div", "debrid-vrstica");
    var uo = el("div", "debrid-opis");
    uo.appendChild(el("strong", "", ubezi(t("usenetIme"))));
    uo.appendChild(el("small", "", ubezi(u.gostitelj ? t("usenetVpisan", { gostitelj: u.gostitelj }) + (u.torbox ? "" : " · " + t("usenetBrezTorbox"))
      : t("usenetPojasnilo"))));
    uv.appendChild(uo);
    var un = el("input", ""); un.type = "url"; un.autocomplete = "off"; un.spellcheck = false;
    un.placeholder = t("usenetNaslov"); un.setAttribute("aria-label", t("usenetNaslov"));
    var uk = el("input", ""); uk.type = "password"; uk.autocomplete = "off"; uk.spellcheck = false;
    uk.placeholder = t("usenetKljuc"); uk.setAttribute("aria-label", t("usenetKljuc"));
    var us = el("button", "gumb", ubezi(t("debridShrani"))); us.type = "button";
    function shraniUsenet() {
      klic("mediaDebrid", ["usenet", un.value, uk.value]).then(function (o) {
        uk.value = "";
        obvesti(t(o && o.ok ? "usenetShranjen" : "usenetNiVeljaven"));
        if (o && o.ok) un.value = "";
        narisiDebridOkno(o);
      }).catch(function () {});
    }
    us.addEventListener("click", shraniUsenet);
    [un, uk].forEach(function (p) { p.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); shraniUsenet(); } }); });
    uv.appendChild(un); uv.appendChild(uk); uv.appendChild(us);
    if (u.gostitelj) {
      var uod = el("button", "gumb", ubezi(t("debridOdstrani"))); uod.type = "button";
      uod.addEventListener("click", function () { klic("mediaDebrid", ["pozabi_usenet"]).then(narisiDebridOkno).catch(function () {}); });
      uv.appendChild(uod);
    }
    sez.appendChild(uv);
    $("debridSamoTakoj").checked = !!s.samo_takoj;
  }

  function zapriSloje() {
    debridPrazno = 0;          // zaprto okno Debrid: naslednji izris stanje vprasa znova
    // Prostori najprej po svoji poti (aria-expanded gumba, zanka osvezitve, fokus nazaj) - tudi klik na temno ozadje
    // gre sem, ker ga ujame splosni poslusalec vseh .tancica (pregled 25. 10. 2026).
    zapriProstore();
    zapriVodnik();                 // tudi klik ob plosco ali Escape: vodnik je preskocen (Nastavitve ga odprejo znova)
    if (S.galerija) zapriGalerijo();
    zapriMeniSporocila();
    document.querySelectorAll(".sloj").forEach(function (s) { s.classList.remove("viden"); });
    if ($("iskanje").value && document.activeElement !== $("iskanje")) $("iskanje").value = "";
    lupaUredi();
  }

  // ------------------------------------------------------------------ Safeer Media: katalog
  // Filmi, serije, glasba, radio, TV v živo, seznami predvajanja in dodatki – isto jedro (core/os_media.py) in isti
  // klici mostu (media*) kot Safeer OS za Windows; krajevna knjižnica zgoraj ostane taka, kot je. Razlika je samo
  // predvajanje: stran sama ne predvaja ničesar (tuje vsebine v stran Safeer OS ne vgrajujemo). Tok in datoteko
  // predvaja domači predvajalnik (GStreamer), skladbo s seznama predvajanja vgradni predvajalnik YouTuba v lahkem
  // medijskem pogledu; ob koncu skladbe safeer_os.py pošlje dogodek »mediaKonec« in stran iz vrste izbere naslednjo.
  // Katalog se nalaga po straneh od zgoraj navzdol (neskoncno drsenje): kat.strani so nalozene strani v vrstnem redu
  // ({kljuc, vnosi}), kat.katalog je njihova zdruzena vsebina. Kljuc strani pride z dogodkom mediaKatalogOsvezen.
  var kat = { katalog: [], strani: [], viri: [], filter: "vse", genre: "", query: "", page: 1, skupaj_strani: 1, skupaj: null,
              nalagaVec: false, napakaVec: false, zvrsti: false,
              aktivni: null, zahteva: 0, timer: 0, kljuc: "", razvrsti: "", izklopljeni: {}, znaniViri: {},
              jezikVsebine: "", jezikiZa: null, seznami: [], seznam: null,
              drzavaRadia: "", radioDrzave: null, radioDrzaveZa: "",
              vrsta: [], vrstaMesto: 0, vrstaZgodovina: [], vrstaNapake: 0, izVrste: false,
              // vrstaRed: vrstni red predvajanja ob »Nakljucno« (indeksi vrste); vrstaIzvor: seznam, iz katerega je vrsta
              // (Nazadnje predvajano); zivi: id skladb, ki so prenos v zivo; vrstaSamodejno: do skladbe je prisel samodejni prehod.
              vrstaRed: null, vrstaIzvor: null, vrstaSpremenjena: false, vrstaSamodejno: false, vrstaIzSafeerja: false,
              vrstaZeton: 0, zivi: {},
              igra: false, nalozen: false, zanri: null, zahtevaPredvajanja: 0, knjiznica: [], zahtevaKnjiznice: 0 };
  // Kategorije Medijskega centra (zgoraj) -> vrsta v katalogu; slike so samo krajevne.
  var KAT_VRSTE = { vse: "vse", glasba: "glasba", video: "video", filmi: "film", serije: "serija", tv: "tv-v-zivo", twitch: "twitch", radio: "radio", zasebno: "zasebno", slike: "", domov: "" };
  var KAT_FILMSKI_ZANRI = [["28", "katZanr_akcija"], ["878", "katZanr_scifi"], ["35", "katZanr_komedija"], ["27", "katZanr_grozljivka"],
                           ["18", "katZanr_drama"], ["53", "katZanr_triler"], ["16", "katZanr_animirani"], ["10749", "katZanr_romantika"]];
  // Serije imajo pri TMDB svoje stevilke zvrsti (grozljivke, trilerja in romantike tam ni) - s filmskimi bi gumb
  // pri serijah vrnil prazen ali napacen seznam (lastnik, 14. 10. 2026).
  var KAT_SERIJSKI_ZANRI = [["10759", "katZanr_akcija"], ["10765", "katZanr_scifi"], ["35", "katZanr_komedija"],
                            ["18", "katZanr_drama"], ["16", "katZanr_animirani"]];
  // Jezik vsebine (izbira poleg zvrsti): isti seznam kot core/izvirni_jezik.py - enakost varuje preizkus.
  var KAT_JEZIKI = ["sl", "en", "de", "fr", "es", "it", "pt", "hr", "sr", "bs", "mk", "ru", "pl", "cs", "sk", "hu", "nl", "sv", "da",
                    "no", "fi", "is", "tr", "el", "ro", "bg", "sq", "uk", "ja", "ko", "zh", "hi", "ta", "te", "th", "ar", "he", "fa"];
  function jezikVelja(filter) { return filter === "vse" || filter === "film" || filter === "serija" || filter === "video" || filter === "glasba"; }
  // Izbrani jezik vsebine za pogled, ki ga katalog kaze ("" = vsi jeziki ali pogled brez te izbire).
  function izbranJezik() { return !kat.seznam && jezikVelja(kat.filter) ? (kat.jezikVsebine || "") : ""; }
  // Izbrana drzava radijskih postaj ("" = vse drzave); velja samo v pogledu Radio (lastnik, 15. 10. 2026).
  function izbranaDrzavaRadia() { return !kat.seznam && kat.filter === "radio" ? (kat.drzavaRadia || "") : ""; }
  function imeDrzave(koda) {
    try { return new Intl.DisplayNames([LOKALE[jezik] || "sl-SI"], { type: "region" }).of(koda) || koda; }
    catch (_) { return koda; }
  }
  function katIkona(vrsta) { return vrsta === "glasba" || vrsta === "podcast" ? "glasba" : vrsta === "radio" ? "radio" : "video"; }
  function katOznaka(vrsta) {
    if (vrsta === "twitch") return t("media_twitch");
    if (vrsta === "twitch-kanal" || vrsta === "twitch-posnetek") return "Twitch";
    var k = { glasba: "media_glasba", video: "media_video", radio: "media_radio", "tv-v-zivo": "media_tv", serija: "media_serije",
              film: "media_filmi", slika: "media_slike" }[vrsta];
    return k ? t(k) : (vrsta === "podcast" ? "Podcast" : t("media_filmi"));
  }
  function katVidno() { return S.razdelek === "media"; }
  function katSplet(url) { if (url) odpriVSpletu(url); }

  // Prazen katalog: kratko, zakaj je prazno, in eno dejanje, ki pomaga (vsi jeziki, vse zvrsti ali dodaj vir).
  function narisiPrazenKatalog(skrij) {
    var blok = $("katPrazno"); if (!blok) return;
    blok.hidden = skrij;
    if (skrij) return;
    // Prazen katalog pri izbranem jeziku: povemo, da je prazno zaradi izbire (ne »ni zadetkov«).
    $("katPraznoBesedilo").textContent = izbranJezik() ? t("katPraznoJezik", { jezik: imeJezika(kat.jezikVsebine, true) })
      : izbranaDrzavaRadia() ? t("katPraznoDrzava", { drzava: imeDrzave(kat.drzavaRadia) }) : t("katPrazno");
    var gumb = $("katPraznoDejanje"), vseZvrsti = $("mediaZanri").querySelector('[data-media-genre=""]');
    gumb.hidden = false;
    if (izbranJezik()) {
      gumb.textContent = t("katVsiJeziki");
      gumb.onclick = function () { $("mediaJezik").value = ""; $("mediaJezik").dispatchEvent(new Event("change")); };
    } else if (izbranaDrzavaRadia()) {
      gumb.textContent = t("katVseDrzave");
      gumb.onclick = function () { $("mediaDrzava").value = ""; $("mediaDrzava").dispatchEvent(new Event("change")); };
    } else if (kat.genre && vseZvrsti) {
      gumb.textContent = vseZvrsti.textContent;
      gumb.onclick = function () { izberiZanr(vseZvrsti); };
    } else if (!kat.seznam && !kat.query) {
      gumb.textContent = t("katDodatki");
      gumb.onclick = odpriKatViri;
    } else gumb.hidden = true;          // iskanje brez zadetkov: uporabnik spremeni iskani niz
  }
  // ---- neskoncno drsenje: ko je konec mreze blizu, se sama nalozi naslednja stran (brez gumbov za strani)
  function katImaVec() { return !kat.seznam && kat.nalozen && kat.page < kat.skupaj_strani; }
  function narisiNalaganje() {
    var c = $("katNalaganje"); if (!c) return;
    var vidno = katImaVec() && kat.katalog.length > 0;
    c.hidden = !vidno;
    c.classList.toggle("napaka", kat.napakaVec);
    $("katNalaganjeBesedilo").textContent = kat.napakaVec ? t("katNiNalozeno") : t("katNalagamVec");
    $("katNalaganjeZnova").hidden = !kat.napakaVec;
    // Opazovalec javi le spremembo; ce je konec mreze se vedno blizu (nizka stran), ga s ponovnim opazovanjem vprasamo znova.
    if (vidno && !kat.napakaVec && katOpazovalec) { katOpazovalec.unobserve(c); katOpazovalec.observe(c); }
  }
  var katOpazovalec = null;
  function zacniNeskoncnoDrsenje() {
    var c = $("katNalaganje");
    if (!c || !("IntersectionObserver" in window)) return;
    katOpazovalec = new IntersectionObserver(function (vnosi) {
      if (vnosi.some(function (v) { return v.isIntersecting; }) && katImaVec() && !kat.nalagaVec && !kat.napakaVec) naloziKatalog(true);
    }, { root: $("vsebina"), rootMargin: "0px 0px 700px 0px" });
    katOpazovalec.observe(c);
  }
  // Prvi viden plakat (ali izbrani) je sidro: po ponovnem izrisu ostane na istem mestu zaslona, izbor ostane na njem.
  function katSidro() {
    var drsnik = $("vsebina"), mreza = $("katMreza");
    if (!drsnik || !mreza) return null;
    var izbran = document.activeElement && document.activeElement.closest ? document.activeElement.closest("#katMreza .kat-kartica") : null;
    var vrh = drsnik.getBoundingClientRect().top, kartica = izbran;
    if (!kartica) kartica = Array.prototype.filter.call(mreza.querySelectorAll(".kat-kartica"), function (k) {
      return k.getBoundingClientRect().bottom > vrh;
    })[0];
    if (!kartica) return null;
    return { id: kartica.getAttribute("data-id"), y: kartica.getBoundingClientRect().top, izbran: !!izbran, odmik: drsnik.scrollTop };
  }
  function katPovrniSidro(sidro) {
    if (!sidro) return;
    var drsnik = $("vsebina");
    // #vsebina ima scroll-behavior: smooth - obnovitev mora biti takojsnja, sicer animacija vleče pogled nazaj navzdol,
    // ko uporabnik z miško drsi navzgor.
    var prej = drsnik.style.scrollBehavior;
    drsnik.style.scrollBehavior = "auto";
    drsnik.scrollTop = sidro.odmik;
    var kartica = Array.prototype.filter.call($("katMreza").querySelectorAll(".kat-kartica"), function (k) {
      return k.getAttribute("data-id") === sidro.id;
    })[0];
    if (!kartica) { drsnik.style.scrollBehavior = prej; return; }
    drsnik.scrollTop += kartica.getBoundingClientRect().top - sidro.y;
    drsnik.style.scrollBehavior = prej;
    if (sidro.izbran) { try { kartica.focus({ preventScroll: true }); } catch (_) { kartica.focus(); } }
  }

  function narisiKatalog() {
    var mreza = $("katMreza"); if (!mreza) return; mreza.innerHTML = "";
    var zanriEl = $("mediaZanri");
    var izSeznama = !!kat.seznam;
    if (zanriEl) zanriEl.hidden = izSeznama || !zanriVidni();
    narisiJezikVsebine();
    narisiDebrid(!kat.seznam && (kat.filter === "film" || kat.filter === "serija" || kat.filter === "vse"));
    narisiDrzavoRadia();
    // Twitch: razvrstitve in virov ni (vrstni red da Twitch: najbolj gledani najprej).
    $("mediaRazvrsti").parentNode.hidden = kat.filter === "twitch";
    $("mediaViriFilterGumb").parentNode.hidden = kat.filter === "twitch";
    narisiSeznamePredvajanja();
    narisiKnjiznico();
    // Glasba s tega racunalnika: skrita, dokler je seznam odprt (narise jo narisiMedije, ta pot je ne bi skrila).
    var lokalnaGlasba = $("katLokalnaGlasba");
    if (lokalnaGlasba) lokalnaGlasba.hidden = izSeznama || !lokalnaGlasba.firstChild;
    // Odprt seznam predvajanja: mreža kaže njegove skladbe v vrstnem redu seznama (brez združevanja po izvajalcu).
    var list = izSeznama ? kat.seznam.vnosi.slice() : kat.katalog.slice();
    narisiPrazenKatalog(!!list.length || !kat.nalozen);
    // Stevilo vsebin je drobno ob naslovu (brez »Stran 1 od 3« - strani se nalagajo same).
    $("mediaPovzetek").textContent = izSeznama ? "" : !kat.nalozen ? t("katNalagam") :
      list.length ? t("katZadetkov", { n: kat.skupaj != null ? kat.skupaj : list.length }) : "";
    var zdruzi = !izSeznama && !kat.razvrsti && (kat.filter === "radio" || kat.filter === "video" || kat.filter === "glasba");
    if (zdruzi) {
      // Naslov skupine ima smisel, ko skupine res združujejo. Kjer ima skoraj vsak izvajalec eno samo skladbo, bi
      // bila v vsaki vrstici ena kartica in ob njej prazen prostor – takrat ostane navadna mreža.
      var skupine = {};
      list.forEach(function (x) { var s = x.skupina || (kat.filter === "glasba" ? x.izvajalec : ""); if (s) skupine[s] = 1; });
      var stSkupin = Object.keys(skupine).length;
      if (!stSkupin || list.length / stSkupin < 2) zdruzi = false;
    }
    if (zdruzi) list.sort(function (a, b) {
      return (a.skupina || a.izvajalec || "").localeCompare(b.skupina || b.izvajalec || "");
    });
    kat.prikazano = list;       // vrsta predvajanja sledi vrstnemu redu, ki ga uporabnik vidi
    // Odprt seznam skladb (Spotify, YouTube, svoj): vrstice s stevilko, majhnim ovitkom in dolzino, ne plakati - skladbe
    // z istega albuma imajo isti ovitek in velike kartice so bile videti enake (lastnik, 17. 10. 2026).
    mreza.classList.toggle("kat-skladbe", izSeznama && list.length > 0 && list.every(function (x) { return x.vrsta === "glasba" || x.vrsta === "podcast"; }));
    var zadnjaSkupina = "", neznanOznacen = false;
    list.forEach(function (x) {
      // Izbran jezik: najprej vsebina v njem, nato vsebina, katere jezika vir ne pove (core/os_media._samo_jezik).
      if (x.jezik_neznan && !neznanOznacen) {
        neznanOznacen = true;
        var g = el("div", "kat-jezik-neznan");
        g.appendChild(el("h3", "", ubezi(t("katJezikNeznan"))));
        g.appendChild(el("p", "drobno", ubezi(t("katJezikNeznanOpis"))));
        mreza.appendChild(g);
      }
      var skupina = izSeznama ? "" : (x.skupina || (kat.filter === "glasba" ? x.izvajalec : ""));
      if (zdruzi && skupina && skupina !== zadnjaSkupina) {
        zadnjaSkupina = skupina;
        mreza.appendChild(el("h3", "kat-skupina", ubezi(zadnjaSkupina)));
      }
      var card = el("button", "kat-kartica"); card.type = "button"; card.setAttribute("data-id", x.id || "");
      card._skladba = x;          // oznaciTrenutnoSkladbo: katera vrstica seznama igra
      card.setAttribute("aria-label", (x.naslov || "") + " — " + katOznaka(x.vrsta));
      // Slika v ovoju .kat-plakat: srcek, »ogledano« in merilo se drzijo njenega spodnjega roba pri vsaki sirini mreze.
      var plakat = el("span", "kat-plakat"); card.appendChild(plakat);
      if (x.slika) {
        var image = document.createElement("img"); image.alt = ""; image.loading = "lazy"; nastaviSliko(image, x.slika);
        image.onerror = function () { image.replaceWith(el("span", "kat-brez-slike", svg(katIkona(x.vrsta)))); };
        // Logotip TV kanala ali postaje (ne plakat): cel, na svetli podlagi - temni logotipi (RTV) so bili na temni
        // kartici nevidni, siroki (France 24) obrezani (preizkus 14. 10. 2026).
        if (x.vrsta === "tv-v-zivo" || x.vrsta === "radio") plakat.classList.add("kat-logotip");
        // Twitch: predogled prenosa ali posnetka je sirok (16:9), slika kanala kvadratna - ne plakat 2:3.
        if (x.vrsta === "twitch" || x.vrsta === "twitch-posnetek") plakat.classList.add("kat-siroko");
        if (x.vrsta === "twitch-kanal") plakat.classList.add("kat-kvadrat");
        plakat.appendChild(image);
      } else plakat.appendChild(el("span", "kat-brez-slike", svg(katIkona(x.vrsta))));
      var data = el("span", "kat-podatki");
      var naslovKartice = el("b", "", ubezi(x.naslov || "")); naslovKartice.title = x.naslov || "";
      data.appendChild(naslovKartice);
      var meta = el("span", "kat-meta");
      // Kakovost, jezik in vir v eni diskretni vrstici (lastnik, 17. 10. 2026); kar ni znano, izpade.
      var vrsticaVira = izSeznama || /^twitch/.test(x.vrsta || "") ? null : katVrsticaVira(x);
      // Vrsta (»Filmi«, »Radio«) le, kadar ni ze ime zavihka - v zavihku Radio je »Radio« na vsaki kartici odvec.
      var metaOznaka = kat.filter === x.vrsta ? "" : katOznaka(x.vrsta);
      // »V živo« enkrat: TV v živo ga že nosi kot značko na plakatu.
      if (x.v_zivo && !(x.vrsta === "tv-v-zivo" && (!x.kakovost || vrsticaVira))) metaOznaka += " · " + t("katVZivo");
      if (x.codec || x.bitrate) metaOznaka += " · " + [x.codec, x.bitrate ? x.bitrate + " kb/s" : ""].filter(Boolean).join(" ");
      if (x.vrsta === "serija" && (x.sezona || x.epizoda)) {
        metaOznaka += " · S" + String(x.sezona || 1).padStart(2, "0") + "E" + String(x.epizoda || 1).padStart(2, "0");
      }
      if (x.leto) metaOznaka += " · " + x.leto;
      metaOznaka = metaOznaka.replace(/^ · /, "");
      // Skladba: pod naslovom izvajalec (koga pričakovati), ne splošna oznaka »Glasba«.
      if ((izSeznama || x.vrsta === "glasba") && x.izvajalec) metaOznaka = x.izvajalec;
      if (/^twitch/.test(x.vrsta || "")) metaOznaka = twitchOpis(x);
      meta.appendChild(el("span", "", ubezi(metaOznaka)));
      if (x.stevilo_razlicic > 1) meta.appendChild(el("span", "", ubezi(t(kljucRazlicic(x.stevilo_razlicic), { n: x.stevilo_razlicic }))));
      data.appendChild(meta);
      if (vrsticaVira) { var vv = el("span", "kat-vir-vrstica", ubezi(vrsticaVira.besedilo)); vv.title = vrsticaVira.namig; data.appendChild(vv); }
      card.appendChild(data);
      if (izSeznama && Number(x.sekund) > 0) {
        var sek = Math.round(Number(x.sekund));
        card.appendChild(el("span", "kat-trajanje", Math.floor(sek / 60) + ":" + String(sek % 60).padStart(2, "0")));
      }
      // Kakovost pokažemo le, če jo poznamo – »HD« na filmu iz leta 1938 bi bil zavajajoč. Znana je v vrstici vira.
      // Skladba s seznama, ki je prenos v zivo (core/nazadnje_predvajano: znani prenosi), ima znacko »V zivo«.
      var znacka = vrsticaVira ? "" : x.kakovost || (x.vrsta === "tv-v-zivo" || x.vrsta === "twitch" || (izSeznama && jeVZivo(x)) ? t("katVZivo") : "");
      if (vrsticaVira && x.vrsta === "tv-v-zivo") znacka = t("katVZivo");
      if (znacka) card.appendChild(el("span", "kat-kakovost", ubezi(znacka)));
      if (Number(x.ocena || 0) > 0) card.appendChild(el("span", "kat-ocena", "★ " + Number(x.ocena).toFixed(1)));
      if (izSeznama && !kat.seznam.yt && !kat.seznam.twitch && !kat.seznam.sp) {
        var odstraniSkladbo = el("span", "kat-odstrani", "✕"); odstraniSkladbo.title = t("seznamOdstraniSkladbo");
        odstraniSkladbo.onclick = function (e) {
          e.stopPropagation();
          var ime = kat.seznam.ime;
          klic("mediaOdstraniSSeznama", [ime, x.id]).then(function () {
            naloziSeznamePredvajanja();
            klic("mediaSeznam", [ime]).then(function (sz) { kat.seznam = sz && sz.vnosi && sz.vnosi.length ? sz : null; narisiKatalog(); });
          });
        };
        card.appendChild(odstraniSkladbo);
      } else if (x.vrsta === "glasba" || x.vrsta === "podcast") {
        // Svoj seznam predvajanja nastaja med poslušanjem: skladbo dodaš z enim klikom.
        var naSeznam = el("span", "kat-na-seznam", "＋"); naSeznam.title = t("katNaSeznam");
        naSeznam.onclick = function (e) { e.stopPropagation(); pokaziSeznamMeni(x, naSeznam); };
        card.appendChild(naSeznam);
      }
      card.setAttribute("data-ime", card.getAttribute("aria-label"));
      // Twitch brez menija kartice (priljubljene in »ogledano« so police, ki gredo v Link): kaj kdo gleda, ostane tu.
      poveziMeniKartice(card, { kljuc: /^twitch/.test(x.vrsta || "") ? "" : kljucVnosa(x), naslov: x.naslov || "",
                                ogledljivo: !!OGLEDLJIVE[x.vrsta], opis: opisVnosa(x) });
      card.onclick = function () {
        if (x.vrsta === "twitch-kanal") {
          odpriTwitchKanal(x.login, x.naslov);
        } else if (x.tmdb_id || x.vrsta === "serija" || (x.vrsta === "film" && !x.peertube_uuid)) {
          odpriKatalogPodrobnosti(x.id);
        } else if (x.vrsta === "glasba" || x.vrsta === "podcast") {
          nastaviVrsto(x);
          odpriKatalogVnos(x.id);
        } else {
          kat.vrsta = []; narisiVrsto();
          odpriKatalogVnos(x.id);
        }
      };
      mreza.appendChild(card);
    });
    oznaciTrenutnoSkladbo();
    narisiNalaganje();
    // Dokler ima katalog vsebino, velika uvodna plošča ne odriva vsebine navzdol. Med nalaganjem (druga kategorija,
    // drug jezik) postavitev ostane, kot je bila - sicer se plošča za hip pokaže in katalog skoči navzdol in nazaj.
    // Pri izbranem jeziku brez zadetkov plošče ni: prazno je zaradi izbire, ne zato, ker uporabnik nima vsebine.
    if (kat.nalozen || list.length) $("r-media").classList.toggle("ima-katalog", list.length > 0 || !!izbranJezik());
  }

  // ---- polica »Na tvojih napravah«: kar je prenesla katera koli naprava v Safeer Linku (knjižnica kroga)
  // Film predvaja naprava, ki ga hrani; zasebnih naslovov in prenosov brez naslova na polici ni (odloči jedro).
  function knjiznicaVidna() {
    return (kat.filter === "vse" || kat.filter === "video" || kat.filter === "film" || kat.filter === "serija") &&
      !kat.query.trim() && !kat.seznam;
  }
  function naloziKnjiznico() {
    if (!knjiznicaVidna()) { narisiKnjiznico(); return; }
    var zahteva = ++kat.zahtevaKnjiznice;
    klic("mediaKnjiznica").then(function (s) {
      if (zahteva !== kat.zahtevaKnjiznice) return;
      kat.knjiznica = s || []; narisiKnjiznico();
    }, function () {});
  }
  function knjiznicaKje(x) { return x.naprava && x.naprava.tukaj ? t("knjiznicaTukaj") : ((x.naprava && x.naprava.ime) || ""); }
  // »Na tvojih napravah« je mreza kot katalog (ne polica, ki bi jo bilo treba pomikati v desno): dve vrstici;
  // ce je vsebine vec, zadnje mesto zasede »Pokaži vse«. Koliko stolpcev ima mreza, pove brskalnik (slog z auto-fill
  // pozna stolpce tudi v prazni mrezi). Racun iz sirine je rezerva, kadar sloga se ni (razdelek ni prikazan): stolpec
  // je sirok najmanj 145, razmik 14, mreza ima levo in desno 2 px roba (katalog.css).
  function knjiznicaNaVrsto(sirina) {
    var s = Number(sirina) || 0;
    return s > 0 ? Math.max(1, Math.floor((s - 4 + 14) / (145 + 14))) : 6;
  }
  function knjiznicaStolpcev(vrsta) {
    var n = 0;
    try {
      n = String(window.getComputedStyle(vrsta).gridTemplateColumns || "").split(/\s+/)
        .filter(function (x) { return /px$/.test(x); }).length;
    } catch (e) { n = 0; }
    return n > 0 ? n : knjiznicaNaVrsto(vrsta.clientWidth);
  }
  function knjiznicaVidnih(stevilo, naVrsto, vse) {
    var mest = Math.max(1, naVrsto) * 2;
    return (vse || stevilo <= mest) ? stevilo : Math.max(1, mest - 1);
  }
  // Sirina mreze se spremeni tudi brez spremembe okna: stran dobi drsnik, ko se pod knjiznico narise katalog (ta pride
  // na vrsto ZA knjiznico), ali pa razdelek sele postane viden. Ce se pri tem spremeni stevilo stolpcev, knjiznico
  // narisemo znova, da ostaneta dve vrstici.
  var opazovalecKnjiznice = null, risiKnjiznice = [];
  function opazujKnjiznico(vrsta, naVrsto) {
    if (opazovalecKnjiznice) { opazovalecKnjiznice.disconnect(); opazovalecKnjiznice = null; }
    if (kat.knjiznicaVse || typeof ResizeObserver !== "function") return;
    opazovalecKnjiznice = new ResizeObserver(function () {
      if (kat.knjiznicaVse || knjiznicaStolpcev(vrsta) === naVrsto) return;
      // Varovalka: stran, ki bi z drsnikom nihala, ne sme vrteti risanja (najvec trije risi v sekundi).
      var zdaj = Date.now();
      risiKnjiznice = risiKnjiznice.filter(function (cas) { return zdaj - cas < 1000; });
      if (risiKnjiznice.length >= 3) return;
      risiKnjiznice.push(zdaj);
      narisiKnjiznico();
    });
    opazovalecKnjiznice.observe(vrsta);
  }
  function narisiKnjiznico() {
    var c = $("mediaKnjiznica"); if (!c) return; c.innerHTML = "";
    var vnosi = knjiznicaVidna() ? (kat.knjiznica || []) : [];
    c.hidden = !vnosi.length;
    if (!vnosi.length) return;
    var glava = el("div", "kat-knjiznica-glava"); glava.appendChild(el("h3", "", ubezi(t("knjiznicaNaslov"))));
    c.appendChild(glava);
    var vrsta = el("div", "kat-knjiznica-vrsta");
    c.appendChild(vrsta);                               // najprej v stran, da ima sirino
    var naVrsto = knjiznicaStolpcev(vrsta), vidnih = knjiznicaVidnih(vnosi.length, naVrsto, kat.knjiznicaVse);
    if (kat.knjiznicaVse && vnosi.length > naVrsto * 2) {
      var manj = el("button", "", ubezi(t("knjiznicaPokaziManj"))); manj.type = "button";
      manj.onclick = function () { kat.knjiznicaVse = false; narisiKnjiznico(); };
      glava.appendChild(manj);
    }
    vnosi.slice(0, vidnih).forEach(function (x) {
      var card = el("button", "kat-kartica"); card.type = "button";
      var kje = knjiznicaKje(x);
      card.setAttribute("aria-label", (x.naslov || "") + " — " + kje);
      card.title = (x.naslov || "") + " · " + kje;
      if (x.slika) {
        var image = document.createElement("img"); image.alt = ""; image.loading = "lazy"; nastaviSliko(image, x.slika);
        image.onerror = function () { image.replaceWith(el("span", "kat-brez-slike", svg("video"))); };
        card.appendChild(image);
      } else card.appendChild(el("span", "kat-brez-slike", svg("video")));
      var data = el("span", "kat-podatki");
      var naslovKartice = el("b", "", ubezi(x.naslov || "")); naslovKartice.title = x.naslov || "";
      data.appendChild(naslovKartice);
      var meta = el("span", "kat-meta");
      meta.appendChild(el("span", "", ubezi(kje)));
      var stanje = x.koncano ? (x.velikost ? velikost(x.velikost) : "") : t("knjiznicaSePrenasa");
      if (stanje) meta.appendChild(el("span", "", ubezi(stanje)));
      data.appendChild(meta); card.appendChild(data);
      // Odstranitev v dveh korakih (prvi klik vpraša), brez sistemskega okna – kot pri seznamih predvajanja.
      var odstrani = el("span", "kat-odstrani", "✕"), potrjeno = false; odstrani.title = t("knjiznicaOdstrani");
      odstrani.onclick = function (e) {
        e.stopPropagation();
        if (!potrjeno) { potrjeno = true; odstrani.classList.add("potrdi"); odstrani.textContent = t("knjiznicaOdstraniRes"); return; }
        card.classList.add("kat-caka");
        klic("mediaKnjiznicaOdstrani", [x.kljuc]).then(function (ok) {
          if (!ok) { card.classList.remove("kat-caka"); obvesti(t("knjiznicaOdstraniNiUspelo")); return; }
          kat.knjiznica = (kat.knjiznica || []).filter(function (y) { return y.kljuc !== x.kljuc; });
          narisiKnjiznico(); obvesti(t("knjiznicaOdstranjeno"));
        }, function () { card.classList.remove("kat-caka"); obvesti(t("knjiznicaOdstraniNiUspelo")); });
      };
      card.onmouseleave = function () { if (potrjeno) { potrjeno = false; odstrani.classList.remove("potrdi"); odstrani.textContent = "✕"; } };
      card.appendChild(odstrani);
      // »Obdrži«: prenos ne poteče po 48 urah. Samo pri napravi, ki to zna (jedro pove true/false; sicer null).
      if (x.obdrzi === true || x.obdrzi === false) {
        if (x.obdrzi) meta.appendChild(el("span", "kat-obdrzano", ubezi(t("knjiznicaObdrzanoOznaka"))));
        var obdrzi = el("span", "kat-obdrzi" + (x.obdrzi ? " je" : ""),
          '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M6 3h12v18l-6-4-6 4z" fill="' +
          (x.obdrzi ? "currentColor" : "none") + '" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>');
        obdrzi.title = t(x.obdrzi ? "knjiznicaNeObdrzi" : "knjiznicaObdrzi");
        obdrzi.onclick = function (e) {
          e.stopPropagation();
          var novo = !x.obdrzi; card.classList.add("kat-caka");
          klic("mediaKnjiznicaObdrzi", [x.kljuc, novo]).then(function (ok) {
            card.classList.remove("kat-caka");
            if (!ok) { obvesti(t("knjiznicaObdrziNiUspelo")); return; }
            x.obdrzi = novo; narisiKnjiznico(); obvesti(t(novo ? "knjiznicaObdrzano" : "knjiznicaNiVecObdrzano"));
          }, function () { card.classList.remove("kat-caka"); obvesti(t("knjiznicaObdrziNiUspelo")); });
        };
        card.appendChild(obdrzi);
      }
      card.onclick = function () { predvajajIzKnjiznice(x); };
      vrsta.appendChild(card);
    });
    if (vidnih < vnosi.length) {
      var vse = el("button", "kat-kartica kat-vse", "<span>" + ubezi(t("knjiznicaPokaziVse")) + "</span><small>" + vnosi.length + "</small>");
      vse.type = "button";
      vse.onclick = function () { kat.knjiznicaVse = true; narisiKnjiznico(); };
      vrsta.appendChild(vse);
    }
    opazujKnjiznico(vrsta, naVrsto);
  }
  // Sirina okna doloca, koliko plakatov gre v dve vrstici.
  var zamikKnjiznice = 0;
  window.addEventListener("resize", function () {
    clearTimeout(zamikKnjiznice);
    zamikKnjiznice = setTimeout(function () { if (!kat.knjiznicaVse && kat.knjiznica && kat.knjiznica.length) narisiKnjiznico(); }, 200);
  });
  function predvajajIzKnjiznice(x) {
    var zahteva = ++kat.zahtevaPredvajanja;
    // Film, ki ni še v celoti na disku ali ga pretaka druga naprava, se ne začne v hipu: uporabnik vidi, da se pripravlja.
    if (x.naprava && x.naprava.id !== "tukaj") obvesti(t("knjiznicaPripravljam", { ime: x.naslov || "", naprava: knjiznicaKje(x) }));
    else if (!x.koncano) obvesti(t("mediaTorrentPripravljam", { ime: x.naslov || "" }));
    klic("mediaKnjiznicaPredvajaj", [x.kljuc]).then(function (item) {
      if (zahteva !== kat.zahtevaPredvajanja) return;
      if (!item || item.napaka_koda || item.napaka) {
        var koda = item && item.napaka_koda;
        obvesti(t(koda === "ni_prostora" || koda === "malo_pomnilnika" ? "mediaNapaka_" + koda : "knjiznicaNiUspelo"));
        if (koda === "ni_prenosa") naloziKnjiznico();       // prenosa ni več (odstranjen drugje): polica se osveži
        return;
      }
      kat.vrsta = []; narisiVrsto();
    }, function () { if (zahteva === kat.zahtevaPredvajanja) obvesti(t("knjiznicaNiUspelo")); });
  }

  // ---- seznami predvajanja
  // »1 skladba, 2 skladbi, 3 skladbe, 5 skladb« (slovenska dvojina in množina); drugi jeziki ednina in množina.
  function stSkladb(n) {
    n = Number(n) || 0;
    if (n === 1) return t("seznamSkladba");
    if (jezik === "sl") {
      var o = n % 100;
      if (o === 2) return t("seznamSkladbi").replace("2", String(n));
      if (o === 3 || o === 4) return t("seznamSkladbe", { n: n });
      if (o === 1) return t("seznamSkladba").replace("1", String(n));
    }
    return t("seznamSkladb", { n: n });
  }
  function seznamiVidni() { return (kat.filter === "glasba" || kat.filter === "vse") && !kat.query.trim(); }
  function naloziSeznamePredvajanja() {
    if (kat.filter === "twitch") { naloziTwitchRacun(false); return Promise.resolve(); }
    naloziYtRacun(false);
    naloziSpotify(false);
    return klic("mediaSeznami").then(function (s) { kat.seznami = s || []; narisiSeznamePredvajanja(); }, function () {});
  }
  // ---- račun YouTube (core/youtube_racun.py): prijava samo, če jo uporabnik želi, in samo v Spletu
  var YT_PRIJAVA = "https://accounts.google.com/ServiceLogin?service=youtube&continue=https://www.youtube.com/";
  var YT_ODJAVA = "https://www.youtube.com/logout";
  var YT_DODAJ_RACUN = "https://accounts.google.com/AddSession?service=youtube&continue=https://www.youtube.com/";
  function naloziYtRacun(vsiljeno) {
    if (!vsiljeno && kat.ytRacunCas && Date.now() - kat.ytRacunCas < 60000) return Promise.resolve(kat.ytRacun);
    kat.ytRacunCas = Date.now();
    return klic("mediaYtRacun").then(function (r) {
      var prej = kat.ytRacun;
      kat.ytRacun = r || null;
      if (r && r.potekla && !(prej && prej.potekla)) obvesti(t("ytPotekla"));
      if (r && r.prijavljen && kat.ytCakanje) {
        // Prijava je uspela: stran za prijavo v Spletu se zapre, uporabnik je spet v Medijskem centru.
        klic("spletKonecPrijave", [["accounts.google.com", "youtube.com"]]);
      }
      if (r && r.prijavljen) ustaviYtCakanje();
      narisiSeznamePredvajanja();
      return r;
    }, function () { return null; });
  }
  // Po kliku »Prijava« Medijski center vsakih 5 s pogleda shrambo piškotkov (samo branje, brez omrežja, dokler
  // prijave ni) - ko se uporabnik v Spletu prijavi, se pokažejo njegovi seznami. Največ 10 minut.
  function cakajYtPrijavo() {
    ustaviYtCakanje();
    var konec = Date.now() + 600000;
    kat.ytCakanje = setInterval(function () { if (Date.now() > konec) ustaviYtCakanje(); else naloziYtRacun(true); }, 5000);
  }
  function ustaviYtCakanje() { if (kat.ytCakanje) { clearInterval(kat.ytCakanje); kat.ytCakanje = 0; } }
  function ytImeSeznama(x) {
    return x.posebni === "LL" ? t("ytVseckani") : x.posebni === "WL" ? t("ytPozneje") : x.posebni === "LM" ? t("ytMusicVseckani") : x.ime;
  }
  function odpriYtSeznam(x) {
    obvesti(t("ytNalagam"));
    klic("mediaYtSeznam", [x.id, x.racun || 0]).then(function (sz) {
      if (sz && sz.napaka === "potekla") { obvesti(t("ytPotekla")); naloziYtRacun(true); return; }
      if (!sz || !sz.vnosi || !sz.vnosi.length) { obvesti(t("seznamNiUspel")); return; }
      if (x.posebni) sz.ime = ytImeSeznama(x);
      kat.seznam = sz; narisiKatalog();
      $("katalog").scrollIntoView({ block: "start" });
    }, function () { obvesti(t("seznamNiUspel")); });
  }
  function narisiYtRacun(c) {
    var r = kat.ytRacun || {}, blok = el("div", "kat-yt-racun");
    var glava = el("div", "kat-seznam-glava");
    glava.appendChild(el("h3", "", ubezi(t("ytRacunNaslov"))));
    if (r.prijavljen) {
      glava.appendChild(el("small", "", ubezi(r.ime ? t("ytPrijavljen", { ime: r.ime }) : t("ytPrijavljenBrezImena"))));
      var odjava = el("button", "gumb", ubezi(t("ytOdjava"))); odjava.type = "button";
      // Odjava v Spletu: YouTube in Google sama izbrišeta prijavo v naši seji (WebKit), drugi piškotki ostanejo.
      odjava.onclick = function () {
        // Odjava znotraj Safeer OS: izbrišejo se samo piškotki youtube.com v seji Spleta (brez odpiranja Spleta).
        klic("odjavaStoritve", ["youtube"]).then(function () { kat.ytRacun = null; kat.ytRacunCas = 0; naloziYtRacun(true); });
        kat.ytRacun = null; narisiSeznamePredvajanja();
      };
      glava.appendChild(odjava);
      var dodaj = el("button", "gumb", ubezi(t("ytDodajRacun"))); dodaj.type = "button";
      // Drug račun Google v isti prijavi (Google dovoli več računov hkrati) – vsi seznami so potem tukaj.
      dodaj.onclick = function () { klic("splet", [YT_DODAJ_RACUN, true]); cakajYtPrijavo(); };
      glava.appendChild(dodaj);
    } else {
      glava.appendChild(el("small", "", ubezi(r.potekla ? t("ytPotekla") : t("ytPrijavaNamig"))));
      var prijava = el("button", "gumb", ubezi(t("ytPrijava"))); prijava.type = "button";
      prijava.onclick = function () { klic("splet", [YT_PRIJAVA, true]); cakajYtPrijavo(); };
      glava.appendChild(prijava);
    }
    blok.appendChild(glava);
    if (r.prijavljen) {
      if (r.napaka) blok.appendChild(el("small", "", ubezi(t("ytNiUspelo"))));
      var racuni = (r.racuni && r.racuni.length) ? r.racuni : [{ racun: 0, ime: r.ime, seznami: r.seznami || [] }];
      racuni.forEach(function (ra) {
        // Več računov: vsak ima svojo vrsto z imenom računa (lastnik 17. 10. 2026).
        if (racuni.length > 1) blok.appendChild(el("small", "kat-yt-racun-ime", ubezi(ra.ime || "YouTube")));
        var vrsta = el("div", "kat-seznami-vrsta");
        (ra.seznami || []).forEach(function (x) {
          var k = el("button", "kat-seznam-kartica"); k.type = "button";
          k.appendChild(el("span", "kat-brez-slike", svg("glasba")));
          var opis = el("span"); opis.appendChild(el("b", "", ubezi(ytImeSeznama(x))));
          opis.appendChild(el("small", "", ubezi(racuni.length > 1 ? "YouTube · " + (ra.ime || "") : "YouTube")));
          k.appendChild(opis);
          k.onclick = function () { odpriYtSeznam(x); };
          vrsta.appendChild(k);
        });
        blok.appendChild(vrsta);
      });
      blok.appendChild(el("small", "kat-yt-namig", ubezi(t("ytNaVsehNapravah"))));
    }
    c.appendChild(blok);
  }
  // ---- Twitch (core/twitch.py): prenosi v živo v našem predvajalniku, oglase izloči Ščit (core/twitch_hls.py).
  // Prijava je neobvezna in samo v Spletu; kanali, ki jim uporabnik sledi, se ne shranjujejo in ne gredo v Link.
  var TW_PRIJAVA = "https://www.twitch.tv/login";
  var TW_ODJAVA = "https://www.twitch.tv/logout";
  var TW_KAKOVOSTI = ["auto", "1080", "720", "480", "360", "160", "audio_only"];
  function twitchOpis(x) {
    if (x.vrsta === "twitch-posnetek") {
      var ure = Math.floor((x.trajanje || 0) / 3600), min = Math.floor(((x.trajanje || 0) % 3600) / 60);
      var datum = x.objavljeno ? new Date(x.objavljeno) : null;
      return [datum && !isNaN(datum) ? datum.toLocaleDateString(LOKALE[jezik] || "sl-SI") : "",
              x.trajanje ? (ure ? ure + " h " : "") + min + " min" : ""].filter(Boolean).join(" · ");
    }
    if (x.vrsta === "twitch-kanal") return t("twitchNiVZivo");
    return [x.kanal, x.igra, x.gledalcev ? t("twitchGledalcev", { n: Number(x.gledalcev).toLocaleString(LOKALE[jezik] || "sl-SI") }) : ""]
      .filter(Boolean).join(" · ");
  }
  function naloziTwitchRacun(vsiljeno) {
    if (!vsiljeno && kat.twRacunCas && Date.now() - kat.twRacunCas < 60000) return Promise.resolve(kat.twRacun);
    kat.twRacunCas = Date.now();
    if (!kat.twKakovost) klic("mediaTwitchKakovost", []).then(function (k) { kat.twKakovost = k || "auto"; narisiSeznamePredvajanja(); }, function () {});
    return klic("mediaTwitchRacun").then(function (r) {
      var prej = kat.twRacun;
      kat.twRacun = r || null;
      if (r && r.potekla && !(prej && prej.potekla)) obvesti(t("twitchPotekla"));
      if (r && r.prijavljen && kat.twCakanje) klic("spletKonecPrijave", [["twitch.tv"]]);
      if (r && r.prijavljen) ustaviTwitchCakanje();
      if (kat.filter === "twitch") narisiSeznamePredvajanja();
      return r;
    }, function () { return null; });
  }
  // Po kliku »Prijava« Medijski center vsakih 5 s pogleda shrambo piškotkov (samo branje, brez omrežja, dokler
  // prijave ni) – ko se uporabnik v Spletu prijavi, se pokažejo kanali, ki jim sledi. Največ 10 minut.
  function cakajTwitchPrijavo() {
    ustaviTwitchCakanje();
    var konec = Date.now() + 600000;
    kat.twCakanje = setInterval(function () { if (Date.now() > konec) ustaviTwitchCakanje(); else naloziTwitchRacun(true); }, 5000);
  }
  function ustaviTwitchCakanje() { if (kat.twCakanje) { clearInterval(kat.twCakanje); kat.twCakanje = 0; } }
  function odpriTwitchKanal(login, ime) {
    obvesti(t("twitchNalagam"));
    klic("mediaTwitchPosnetki", [login]).then(function (sz) {
      if (!sz || sz.napaka || !sz.vnosi || !sz.vnosi.length) {
        obvesti(sz && sz.napaka === "ni_posnetkov" ? t("twitchNiPosnetkov", { ime: sz.ime || ime || login }) : t("twitchNiUspelo"));
        return;
      }
      kat.seznam = sz; narisiKatalog();
      $("katalog").scrollIntoView({ block: "start" });
    }, function () { obvesti(t("twitchNiUspelo")); });
  }
  function narisiTwitch(c) {
    var r = kat.twRacun || {}, blok = el("div", "kat-yt-racun");
    var glava = el("div", "kat-seznam-glava");
    glava.appendChild(el("h3", "", ubezi(t("twitchRacunNaslov"))));
    if (r.prijavljen) {
      glava.appendChild(el("small", "", ubezi(r.ime ? t("twitchPrijavljen", { ime: r.ime }) : t("twitchPrijavljenBrezImena"))));
      var odjava = el("button", "gumb", ubezi(t("twitchOdjava"))); odjava.type = "button";
      // Odjava v Spletu: Twitch sam izbriše prijavo v naši seji (WebKit), drugi piškotki ostanejo.
      odjava.onclick = function () {
        klic("odjavaStoritve", ["twitch"]).then(function () { kat.twRacun = null; kat.twRacunCas = 0; naloziTwitchRacun(true); });
        kat.twRacun = null; narisiSeznamePredvajanja();
      };
      glava.appendChild(odjava);
    } else {
      glava.appendChild(el("small", "", ubezi(r.potekla ? t("twitchPotekla") : t("twitchPrijavaNamig"))));
      var prijava = el("button", "gumb", ubezi(t("twitchPrijava"))); prijava.type = "button";
      prijava.onclick = function () { klic("splet", [TW_PRIJAVA, true]); cakajTwitchPrijavo(); };
      glava.appendChild(prijava);
    }
    // Kakovost prenosa: samodejno (največ ločljivost zaslona) ali izbrana; velja za naslednji prenos.
    var kakovost = el("label", "kat-razvrsti"); kakovost.appendChild(el("span", "", ubezi(t("twitchKakovost"))));
    var izbira = document.createElement("select"); izbira.setAttribute("aria-label", t("twitchKakovost"));
    TW_KAKOVOSTI.forEach(function (k) {
      izbira.add(new Option(k === "auto" ? t("twitchSamodejno") : k === "audio_only" ? t("twitchSamoZvok") : k + "p", k));
    });
    izbira.value = kat.twKakovost || "auto";
    izbira.onchange = function () {
      var k = izbira.value;
      klic("mediaTwitchKakovost", [k]).then(function (v) {
        kat.twKakovost = v || "auto";
        // Prenos, ki že teče, se znova odpre v novi kakovosti.
        if (kat.aktivni && kat.aktivni.vrsta === "twitch" && kat.igra) odpriKatalogVnos(kat.aktivni.id);
      }, function () {});
    };
    kakovost.appendChild(izbira);
    glava.appendChild(kakovost);
    blok.appendChild(glava);
    if (r.prijavljen) {
      if (r.napaka) blok.appendChild(el("small", "", ubezi(t("twitchNiUspelo"))));
      var kanali = r.kanali || [], vZivo = kanali.filter(function (x) { return x.v_zivo; });
      blok.appendChild(el("small", "", ubezi(kanali.length ? t("twitchSledis", { n: vZivo.length }) : t("twitchNiSledenih"))));
      var vrsta = el("div", "kat-seznami-vrsta");
      // V živo najprej (jedro jih uredi po gledalcih), nato kanali brez prenosa (klik odpre njihove posnetke).
      kanali.slice(0, 60).forEach(function (x) {
        var k = el("button", "kat-seznam-kartica"); k.type = "button";
        if (x.ikona || x.slika) {
          var slika = document.createElement("img"); slika.alt = ""; slika.loading = "lazy"; nastaviSliko(slika, x.ikona || x.slika);
          slika.onerror = function () { slika.replaceWith(el("span", "kat-brez-slike", svg("twitch"))); };
          k.appendChild(slika);
        } else k.appendChild(el("span", "kat-brez-slike", svg("twitch")));
        var opis = el("span"); opis.appendChild(el("b", "", ubezi(x.kanal || x.naslov)));
        opis.appendChild(el("small", "", ubezi(x.v_zivo ? t("katVZivo") + (x.igra ? " · " + x.igra : "") : t("twitchNiVZivo"))));
        k.appendChild(opis);
        k.title = x.v_zivo ? x.naslov : (x.kanal || x.naslov);
        k.onclick = function () {
          if (x.v_zivo) { kat.vrsta = []; narisiVrsto(); odpriKatalogVnos(x.id); }
          else odpriTwitchKanal(x.login, x.kanal);
        };
        vrsta.appendChild(k);
      });
      blok.appendChild(vrsta);
    }
    c.appendChild(blok);
  }

  // ---- Spotify (core/spotify_racun.py): predvaja skrit Safeer DRM, Medijski center pokaže sezname in upravljanje.
  // Prijava samo, če jo uporabnik želi, v oknu Safeer DRM na strani Spotifyja; brez prijave ostane uvoz javnih seznamov.
  function naloziSpotify(vsiljeno) {
    if (!vsiljeno && kat.spCas && Date.now() - kat.spCas < 60000) return Promise.resolve(kat.sp);
    kat.spCas = Date.now();
    return klic("mediaSpStanje").then(function (r) {
      var prej = kat.sp;
      kat.sp = r || null;
      // Lastnik 17. 10.: o pogojih Spotifyja ne obvescamo z oknom – vrstica je diskretno v opisu stikala v Ščitu.
      if (r && r.potekla && !(prej && prej.potekla)) obvesti(t("spPotekla"));
      if (r && r.prijavljen && !r.okno && kat.spCakanje) { ustaviSpCakanje(); kat.spPokazi = true; }
      if (r) { spUskladiTrak(r); if (spNaTraku()) spZanka(); }
      if (r && r.prijavljen && r.drm && !r.okno && !kat.spSeznami && !kat.spBerem && !kat.spNapaka) naloziSpSezname();
      narisiSeznamePredvajanja();
      return r;
    }, function () { return null; });
  }
  function naloziSpSezname() {
    kat.spBerem = true;
    return klic("mediaSpSeznami").then(function (r) {
      kat.spBerem = false;
      kat.spNapaka = r && r.napaka ? r.napaka : "";
      kat.spSeznami = r && !r.napaka ? r : null;
      if (kat.spNapaka === "potekla") obvesti(t("spPotekla"));
      if (kat.spSeznami) spZanka();
      narisiSeznamePredvajanja();
    }, function () { kat.spBerem = false; });
  }
  // Po kliku »Prijava« Medijski center vsake 3 s vpraša, ali je prijava končana (okno se takrat samo skrije). Največ 10 min.
  function cakajSpPrijavo() {
    ustaviSpCakanje();
    var konec = Date.now() + 600000;
    kat.spCakanje = setInterval(function () { if (Date.now() > konec) ustaviSpCakanje(); else naloziSpotify(true); }, 3000);
  }
  function cakajSpPrijavoSplet() {
    ustaviSpCakanje();
    var konec = Date.now() + 600000;
    kat.spCakanje = setInterval(function () {
      if (Date.now() > konec) { ustaviSpCakanje(); return; }
      klic("mediaSpPrijavaSplet").then(function (r) {
        if (!r || !r.prijavljen) return;
        ustaviSpCakanje();
        klic("spletKonecPrijave", [["accounts.spotify.com", "spotify.com", "accounts.google.com"]]);
        kat.spCas = 0; kat.spSeznami = null; spPokaziRazdelek(true); naloziSpotify(true);
      }, function () {});
    }, 3000);
  }
  // Prijava v Spotify (Medijski center in vodnik ob prvem zagonu).
  function spPrijava() {
    klic("mediaSpPrijava").then(function (x) {
      if (x && x.napaka) { spNapaka(x.napaka); return; }
      // Prijava v Spletu (Google tam deluje); Medijski center vsakih 3 s pogleda, ali je prijava koncana.
      if (x && x.splet) { klic("splet", [x.splet, true]); cakajSpPrijavoSplet(); return; }
      kat.sp = Object.assign({}, kat.sp, { okno: true }); narisiSeznamePredvajanja(); cakajSpPrijavo();
    }, function () { spNapaka("ni_odziva"); });
  }
  function ustaviSpCakanje() { if (kat.spCakanje) { clearInterval(kat.spCakanje); kat.spCakanje = 0; } }
  // predvajanje: napaka med predvajanjem ali upravljanjem - tiho (lastnik 18. 10. 2026; sled zapise os_katalog v
  // sled.log). Ostanejo le sporocila, ki niso napaka predvajalnika, ampak uporabnik mora nekaj storiti: Safeer DRM
  // prenesti, se prijaviti (SP_UKREPAJ). Brskanje (odpiranje seznama) in prijava kazeta vse kot doslej.
  var SP_UKREPAJ = { ni_drm: 1, potekla: 1, ni_prijave: 1 };
  function spNapaka(koda, predvajanje) {
    if (predvajanje && !SP_UKREPAJ[koda]) return;
    var k = "spNapaka_" + koda;
    obvesti(t(k) !== k ? t(k) : t("spNapaka_stran"));
  }
  function odpriSpSeznam(ident, ime) {
    if (kat.spOdpiram === ident) return;           // seznam se ze bere (dvoklik, ponovljen OK na daljincu)
    kat.spOdpiram = ident;
    obvesti(t("spNalagam"));
    klic("mediaSpSeznam", [ident, ime]).then(function (sz) {
      kat.spOdpiram = "";
      if (!sz || sz.napaka) { spNapaka(sz ? sz.napaka : "ni_odziva"); if (sz && sz.napaka === "potekla") naloziSpotify(true); return; }
      kat.seznam = sz; narisiKatalog();
      $("katalog").scrollIntoView({ block: "start" });
    }, function () { kat.spOdpiram = ""; spNapaka("ni_odziva"); });
  }
  function spKartica(ime, opis, slika, ikona, ob) {
    var k = el("button", "kat-seznam-kartica"); k.type = "button";
    if (slika) { var im = el("img"); nastaviSliko(im, slika); im.alt = ""; im.loading = "lazy"; k.appendChild(im); }
    else k.appendChild(el("span", "kat-brez-slike", svg(ikona)));
    var o = el("span"); o.appendChild(el("b", "", ubezi(ime))); o.appendChild(el("small", "", ubezi(opis)));
    k.appendChild(o); k.onclick = ob;
    return k;
  }
  function narisiSpotify(c) {
    var r = kat.sp; if (!r) return;
    var blok = el("div", "kat-yt-racun kat-sp-racun"), glava = el("div", "kat-seznam-glava");
    glava.appendChild(el("h3", "", ubezi(t("spNaslov"))));
    function gumb(besedilo, ob) { var g = el("button", "gumb", ubezi(besedilo)); g.type = "button"; g.onclick = ob; glava.appendChild(g); return g; }
    if (!r.drm) {
      // Safeer DRM je od 1.0.127 del paketa (nič se ne prenaša); brez njega je namestitev iz izvorne kode - samo pojasnilo.
      glava.appendChild(el("small", "", ubezi(t("spNiDrm"))));
    } else if (!r.prijavljen || r.okno) {
      glava.appendChild(el("small", "", ubezi(r.okno ? t("spPrijavaOkno") : r.potekla ? t("spPotekla") : t("spPrijavaNamig"))));
      if (!r.okno) gumb(t("spPrijava"), spPrijava);
    } else {
      glava.appendChild(el("small", "", ubezi(r.ime ? t("spPrijavljen", { ime: r.ime }) : t("spPrijavljenBrezImena"))));
      // Odjava v dveh korakih: izbriše prijavo Spotifyja na tej napravi (profil Safeer DRM za Spotify).
      var potrdi = false, odjava = gumb(t("spOdjava"), function () {
        if (!potrdi) { potrdi = true; odjava.textContent = t("spOdjavaRes"); return; }
        klic("odjavaStoritve", ["spotify"]);      // tudi prijava Spotifyja v Spletu, da se ne vrne sama
        klic("mediaSpOdjava").then(function () { kat.spSeznami = null; kat.spNapaka = ""; kat.spCas = 0; naloziSpotify(true); }, function () {});
      });
    }
    blok.appendChild(glava);
    if (r.prijavljen && !r.okno && kat.spNapaka && kat.spNapaka !== "potekla") {
      var k = "spNapaka_" + kat.spNapaka, vr = el("div", "kat-seznam-glava");
      vr.appendChild(el("small", "", ubezi(t(k) !== k ? t(k) : t("spNapaka_stran"))));
      var znova = el("button", "gumb", ubezi(t("spZnova"))); znova.type = "button";
      znova.onclick = function () { kat.spNapaka = ""; naloziSpSezname(); };
      vr.appendChild(znova); blok.appendChild(vr);
    }
    var sz = kat.spSeznami;
    if (r.prijavljen && !r.okno && kat.spBerem && !sz) blok.appendChild(el("p", "namig", ubezi(t("spNalagam"))));
    if (r.prijavljen && sz) {
      var vrsta = el("div", "kat-seznami-vrsta");
      vrsta.appendChild(spKartica(t("spVseckane"), "Spotify", "", "glasba", function () { odpriSpSeznam("vseckane", t("spVseckane")); }));
      (sz.seznami || []).forEach(function (x) {
        vrsta.appendChild(spKartica(x.ime, x.stevilo ? stSkladb(x.stevilo) : "Spotify", x.slika, "glasba", function () { odpriSpSeznam(x.id, x.ime); }));
      });
      blok.appendChild(vrsta);
      if ((sz.oddaje || []).length) {
        blok.appendChild(el("h4", "", ubezi(t("spPodkasti"))));
        var oddaje = el("div", "kat-seznami-vrsta");
        sz.oddaje.forEach(function (x) {
          oddaje.appendChild(spKartica(x.ime, x.avtor || t("spPodkasti"), x.slika, "mikrofon", function () { odpriSpSeznam("show:" + x.id, x.ime); }));
        });
        blok.appendChild(oddaje);
      }
    }
    var pr = el("div", "kat-sp-predvajalnik"); pr.id = "spPredvajalnik";
    blok.appendChild(pr);
    c.appendChild(blok);
    narisiSpPredvajalnik();
    if (kat.spPokazi && sz) {
      // Pravkar prijavljen: Medijski center pokaže sezname, fokus na prvem (tudi za daljinec).
      kat.spPokazi = false;
      blok.scrollIntoView({ block: "start" });
      var prvi = blok.querySelector(".kat-seznam-kartica"); if (prvi) prvi.focus({ preventScroll: true });
    }
  }
  // Trenutna skladba in upravljanje (skrit Safeer DRM); posodablja se na mestu, da drsnik ne skoči izpod kazalca.
  function narisiSpPredvajalnik() {
    var c = $("spPredvajalnik"); if (!c) return;
    var p = (kat.sp && kat.sp.predvajanje) || {};
    if (!p.naslov || spNaTraku()) { c.hidden = true; c.innerHTML = ""; return; }
    var a = document.activeElement;
    if (a && a.type === "range" && c.contains(a)) return;
    c.hidden = false; c.innerHTML = "";
    if (p.slika) { var im = el("img"); nastaviSliko(im, p.slika); im.alt = ""; c.appendChild(im); }
    var opis = el("div", "kat-sp-opis");
    opis.appendChild(el("b", "", ubezi(p.naslov)));
    opis.appendChild(el("small", "", ubezi(p.oglas ? t("spOglas") : p.izvajalec || "")));
    c.appendChild(opis);
    var gumbi = el("div", "kat-sp-gumbi");
    [["nazaj", "⏮", "spNazaj"], ["premor", p.igra ? "⏸" : "▶", p.igra ? "spPremor" : "spPredvajaj"], ["naprej", "⏭", "spNaprej"]].forEach(function (g) {
      var b = el("button", "gumb", g[1]); b.type = "button"; b.title = t(g[2]); b.setAttribute("aria-label", t(g[2]));
      b.onclick = function () { klic("mediaSpUkaz", [g[0]]).then(function (x) { if (x && x.napaka) spNapaka(x.napaka, true); setTimeout(osveziSp, 400); }, function () {}); };
      gumbi.appendChild(b);
    });
    c.appendChild(gumbi);
    function drsnik(oznaka, vrednost, ukaz) {
      var d = el("input"); d.type = "range"; d.min = "0"; d.max = "1000"; d.value = String(Math.round((vrednost || 0) * 1000));
      d.setAttribute("aria-label", t(oznaka)); d.title = t(oznaka);
      d.onchange = function () { klic("mediaSpUkaz", [ukaz, Number(d.value) / 1000]).then(function () { d.blur(); setTimeout(osveziSp, 400); }, function () {}); };
      return d;
    }
    if (p.trajanje > 0) {
      var cas = el("div", "kat-sp-cas");
      cas.appendChild(el("small", "", ubezi(fmtCasSp(p.polozaj))));
      cas.appendChild(drsnik("spCas", p.polozaj / p.trajanje, "cas"));
      cas.appendChild(el("small", "", ubezi(fmtCasSp(p.trajanje))));
      c.appendChild(cas);
    }
    if (typeof p.glasnost === "number") c.appendChild(drsnik("spGlasnost", p.glasnost, "glasnost"));
  }
  function fmtCasSp(s) { s = Math.max(0, Math.round(s || 0)); return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2); }
  function osveziSp() {
    return klic("mediaSpStanje").then(function (r) {
      if (!r) return;
      var prej = kat.sp; kat.sp = r;
      spUskladiTrak(r);
      if (r.potekla && !(prej && prej.potekla)) { obvesti(t("spPotekla")); narisiSeznamePredvajanja(); return; }
      narisiSpPredvajalnik();
    }, function () {});
  }
  // Med predvajanjem vsake 1,5 s, dokler je razdelek viden ali Spotify kaže spodnji trak; Safeer DRM se zaradi tega ne
  // zažene (samo prebere stanje) in se po mirovanju ustavi sam - takrat se ustavi tudi zanka.
  function spZanka() {
    if (kat.spZanka) return;
    kat.spZanka = setInterval(function () {
      var c = $("spPredvajalnik");
      if (!(kat.sp && kat.sp.tece) || (!kat.spTrak && !(c && c.offsetParent))) { clearInterval(kat.spZanka); kat.spZanka = 0; return; }
      osveziSp();
    }, 1500);
  }
  // ---- Spotify v spodnjem traku (lastnik, 17. 10. 2026: mini predvajalnik na dnu in »Predvajaj na …«). Trak kaže en
  // vir: Spotify ga prevzame, ko začne igrati, in ga odda, ko začne drug vir (domači predvajalnik, katalog, YouTube).
  function spTrenutna() {
    var p = kat.sp && kat.sp.tece && kat.sp.predvajanje;
    return kat.spZacetna || (p && p.naslov ? p : null);
  }
  function spNaTraku() {
    return typeof kat !== "undefined" && !!kat.spTrak && !!spTrenutna();
  }
  function drugVirIgra() {
    var p = S.mediaPredvajalnik;
    return !!(p && p.naslov && p.stanje === "predvaja") || !!(kat.aktivni && kat.igra);
  }
  // Stanje iz mediaSpStanje: trak prevzame Spotify, ki igra (tudi po ponovnem nalaganju strani), in ga odda, ko Safeer
  // DRM ne teče več. Začetni vnos (naslov s kartice) velja, dokler Spotify ne javi skladbe, največ 20 s.
  function spUskladiTrak(r) {
    var p = (r && r.tece && r.predvajanje) || {};
    var z = kat.spZacetna, cas = Date.now() - (kat.spOd || 0);
    // Prvi odgovor ima lahko še prejšnjo skladbo: kartica velja, dokler Spotify ne javi nje ali ne minejo 4 s.
    if (z && ((p.naslov && (p.naslov === z.naslov || cas > 4000)) || cas > 20000)) kat.spZacetna = null;
    if (!r || !r.tece || r.potekla) { kat.spTrak = false; kat.spZacetna = null; }
    else if (p.igra && !kat.spTrak && !drugVirIgra()) kat.spTrak = true;
    narisiTrak();
  }
  // Isti trak kot za druge vire (narisiTrak): naslov, izvajalec, ovitek, premor/naprej/nazaj, položaj, »Predvajaj na …«.
  function narisiSpTrak() {
    var p = spTrenutna() || {};
    var opis = p.oglas ? t("spOglas") : [p.izvajalec, "Spotify"].filter(Boolean).join(" · ");
    var izh = IZ && IZ.z && SafeerIzhod.aktivna(IZ.z);
    if (izh && izh.vrsta !== "racunalnik") opis += " · " + t("predvajaNa", { ime: izh.ime });
    $("mediaBarNaslov").textContent = p.naslov || ""; $("mediaBarNaslov").title = p.naslov || "";
    $("mediaBarVrsta").textContent = opis;
    var znak = $("mediaBarZnak"), slika = p.slika || "";
    if (znak._slika !== slika || znak._ikona !== "glasba") {
      znak._slika = slika; znak._ikona = "glasba";
      znak.innerHTML = svg("glasba");
      if (slika) {
        var img = document.createElement("img"); img.alt = ""; nastaviSliko(img, slika);
        img.onerror = function () { img.remove(); };
        znak.appendChild(img);
      }
    }
    var premor = $("mediaKatPremor");
    premor.innerHTML = svg(p.igra ? "premor" : "predvajaj");
    premor.setAttribute("aria-pressed", p.igra ? "true" : "false");
    $("mediaPrejsnja").disabled = false; $("mediaNaslednja").disabled = false;
    $("mediaPremesaj").hidden = true; $("mediaPonovi").hidden = true;
    $("mediaBarVrstaGumb").hidden = true; zapriVrstoPlosco(false);
    var polozaj = Number(p.trajanje) > 0 && !p.oglas;
    $("mediaBarPolozaj").hidden = !polozaj;
    if (polozaj) {
      $("mediaBarCas").textContent = casMedija(p.polozaj);
      $("mediaBarTrajanje").textContent = casMedija(p.trajanje);
      var drsnik = $("mediaBarNapredek");
      if (!S.mediaDragging) drsnik.value = Math.round(1000 * Math.min(1, (Number(p.polozaj) || 0) / p.trajanje));
      drsnik.setAttribute("aria-valuetext", casMedija(p.polozaj) + " / " + casMedija(p.trajanje));
    }
    narisiGlasnostTraku();
  }
  function spZacni(item) {
    // Spotify je začel: drug vir se ustavi (nikoli dva hkrati), trak takoj pokaže skladbo s kartice.
    if (kat.aktivni) ustaviKatPredvajanje();
    else if (S.mediaPredvajalnik && S.mediaPredvajalnik.naslov && S.mediaPredvajalnik.stanje !== "ustavljeno")
      klic("predvajalnikUkaz", ["ustavi"]).catch(function () {});
    kat.spTrak = true; kat.spOd = Date.now();
    kat.spZacetna = { naslov: item.naslov || "", izvajalec: item.izvajalec || "", slika: item.slika || "", igra: true };
    if (kat.sp && kat.sp.predvajanje) kat.sp.predvajanje = {};       // prejšnja skladba ne utripne na traku
    narisiTrak();
    if (item.sp_delno) obvesti(t("spDelno"));
    osveziSp().then(spZanka);
    setTimeout(osveziSp, 1200);
  }
  function spUkazTraka(u, vrednost) {
    var p = kat.sp && kat.sp.predvajanje;
    if (u === "premor" && p && p.naslov) { p.igra = !p.igra; narisiTrak(); }      // takoj, stanje potrdi zanka
    klic("mediaSpUkaz", vrednost == null ? [u] : [u, vrednost]).then(function (x) {
      if (x && x.napaka === "ne_tece") { kat.spTrak = false; narisiTrak(); }
      if (x && x.napaka) spNapaka(x.napaka, true);
      setTimeout(osveziSp, 400);
    }, function () {});
    if (u === "premor") spZanka();
  }
  function spUstaviTrak() {
    klic("mediaSpUkaz", ["ustavi"]).then(function () { setTimeout(osveziSp, 400); }, function () {});
    kat.spTrak = false; kat.spZacetna = null;
    narisiTrak();
  }
  // Drug vir je prevzel predvajanje: trak ni več Spotifyjev. ustavi = Spotify tudi ustavimo (gostitelj ga ustavi sam,
  // ko vsebina pride iz kataloga; »ustavi« je pri njem varen tudi dvakrat zapored).
  function spOpusti(ustavi) {
    var tece = !!(kat.sp && kat.sp.tece);
    kat.spTrak = false; kat.spZacetna = null;
    if (ustavi && tece) klic("mediaSpUkaz", ["ustavi"]).then(function () { setTimeout(osveziSp, 400); }, function () {});
  }
  // Domači predvajalnik (datoteka, radio, Twitch) je začel ali nadaljeval: Spotify se ustavi. Prve 3 s po zagonu
  // Spotifyja ne štejejo - takrat še pride staro stanje predvajalnika, ki ga je Spotify pravkar ustavil.
  function spOdDomacega(p) {
    if (typeof kat === "undefined") return;
    var podpis = p && p.naslov && p.stanje === "predvaja" ? p.naslov + "|" + (p.indeks || 0) : "";
    var nov = !!podpis && podpis !== kat.spDomaci;
    kat.spDomaci = podpis;
    if (!nov || Date.now() - (kat.spOd || 0) < 3000) return;
    if (kat.spTrak || (kat.sp && kat.sp.tece)) spOpusti(true);
  }
  // Razdelek Spotify v Medijskem centru (Glasba): po prijavi v Spletu in ob kliku na ovitek v traku.
  function spPokaziRazdelek(poPrijavi) {
    pojdi("media");                         // tudi iz načina Splet (gostitelj ga ob tem skrije)
    if (!seznamiVidni() || kat.seznam) {
      kat.seznam = null; S.mediaIskanje = "";
      if ($("mediaIskanje")) $("mediaIskanje").value = "";
      izberiMedijskoKategorijo("glasba"); narisiMedije();
    }
    kat.spPokazi = true;
    if (poPrijavi) obvesti(t("spPrijavaKoncana"));
    else narisiSeznamePredvajanja();
  }
  function odpriSeznamPredvajanja(ime) {
    klic("mediaSeznam", [ime]).then(function (sz) {
      if (!sz || !sz.vnosi || !sz.vnosi.length) { obvesti(t("seznamNiUspel")); return; }
      kat.seznam = sz; narisiKatalog();
      $("katalog").scrollIntoView({ block: "start" });
    }, function () { obvesti(t("seznamNiUspel")); });
  }
  function uvoziSeznamPredvajanja(povezava) {
    povezava = String(povezava || "").trim(); if (!povezava) return;
    obvesti(t("seznamUvazam"));
    klic("mediaUvoziSeznam", [povezava]).then(function (r) {
      if (r && r.napaka === "zaseben") { obvesti(t("seznamZaseben") + " " + t("ytZasebenPrijava")); return; }
      if (r && r.napaka === "potekla") { obvesti(t("ytPotekla")); naloziYtRacun(true); return; }
      if (!r || r.napaka) { obvesti(t(r && r.napaka === "ni_seznam" ? "seznamNiSeznam" : "seznamNiUspel")); return; }
      obvesti(t("seznamUvozen", { ime: r.ime, n: r.stevilo }));
      naloziSeznamePredvajanja().then(function () { odpriSeznamPredvajanja(r.ime); });
    }, function () { obvesti(t("seznamNiUspel")); });
  }
  function narisiSeznamePredvajanja() {
    var c = $("mediaSeznami"); if (!c) return; c.innerHTML = "";
    if (kat.seznam) {
      c.hidden = false;
      var sz = kat.seznam, glava = el("div", "kat-seznam-glava");
      var nazaj = el("button", "gumb", ubezi(t("seznamNazaj"))); nazaj.type = "button";
      nazaj.onclick = function () { kat.seznam = null; narisiKatalog(); };
      glava.appendChild(nazaj);
      glava.appendChild(el("h3", "", ubezi(sz.ime)));
      if (sz.twitch) {
        // Posnetki kanala Twitch: vsak se predvaja posebej (brez »Predvajaj vse« in brez urejanja seznama).
        glava.appendChild(el("small", "", ubezi(t("twitchPosnetkov", { n: sz.vnosi.length }))));
        c.appendChild(glava);
        return;
      }
      glava.appendChild(el("small", "", ubezi(stSkladb(sz.vnosi.length) + (sz.vir ? " · " + sz.vir : ""))));
      var vse = el("button", "gumb glavni", ubezi("▶ " + t("seznamPredvajajVse"))); vse.type = "button";
      vse.onclick = function () { var prvi = sz.vnosi[0]; if (prvi) { nastaviVrsto(prvi); zacniOdZacetka(); narisiVrsto(); odpriKatalogVnos(kat.vrsta[kat.vrstaMesto]); } };
      glava.appendChild(vse);
      if (sz.sp) {
        // Seznam računa Spotify: predvaja skrit Safeer DRM; shrani ga uporabnik sam (ostane samo na tej napravi).
        var spShrani = el("button", "gumb", ubezi(t("spShrani"))); spShrani.type = "button";
        spShrani.onclick = function () {
          klic("mediaSpShrani", [sz.sp]).then(function (r) {
            if (!r || !r.ok) { obvesti(t("seznamNiMogoce")); return; }
            obvesti(t("spShranjeno", { ime: r.ime })); naloziSeznamePredvajanja();
          }, function () { obvesti(t("seznamNiMogoce")); });
        };
        glava.appendChild(spShrani);
        c.appendChild(glava);
        return;
      }
      if (sz.yt) {
        // Seznam računa YouTube: predvaja se takoj; shrani ga uporabnik sam (ostane samo na tej napravi).
        var shrani = el("button", "gumb", ubezi(t("ytShrani"))); shrani.type = "button";
        shrani.onclick = function () {
          klic("mediaYtShrani", [sz.yt, sz.yt_racun || 0, sz.ime || ""]).then(function (r) {
            if (!r || !r.ok) { obvesti(t("seznamNiMogoce")); return; }
            obvesti(t("ytShranjeno", { ime: r.ime })); naloziSeznamePredvajanja();
          }, function () { obvesti(t("seznamNiMogoce")); });
        };
        glava.appendChild(shrani);
        c.appendChild(glava);
        return;
      }
      // Odstranitev v dveh korakih (prvi klik vpraša), brez sistemskega okna.
      var odstrani = el("button", "gumb", ubezi(t("seznamOdstrani"))), potrjeno = false; odstrani.type = "button";
      odstrani.onclick = function () {
        if (!potrjeno) { potrjeno = true; odstrani.textContent = t("seznamOdstraniRes"); return; }
        klic("mediaOdstraniSeznam", [sz.ime]).then(function () { kat.seznam = null; naloziSeznamePredvajanja().then(narisiKatalog); });
      };
      glava.appendChild(odstrani);
      c.appendChild(glava);
      return;
    }
    if (kat.filter === "twitch" && !kat.query.trim()) { c.hidden = false; narisiTwitch(c); return; }
    if (!seznamiVidni()) { c.hidden = true; return; }
    c.hidden = false;
    c.appendChild(el("h3", "", ubezi(t("seznamiNaslov"))));
    var vrsta = el("div", "kat-seznami-vrsta");
    (kat.seznami || []).forEach(function (sz) {
      var k = el("button", "kat-seznam-kartica"); k.type = "button";
      if (sz.slika) {
        var slika = document.createElement("img"); slika.alt = ""; slika.loading = "lazy"; slika.src = sz.slika;
        slika.onerror = function () { slika.replaceWith(el("span", "kat-brez-slike", svg("glasba"))); };
        k.appendChild(slika);
      } else k.appendChild(el("span", "kat-brez-slike", svg("glasba")));
      var opis = el("span"); opis.appendChild(el("b", "", ubezi(sz.ime)));
      opis.appendChild(el("small", "", ubezi(stSkladb(sz.stevilo) + (sz.vir ? " · " + sz.vir : ""))));
      k.appendChild(opis);
      k.onclick = function () { odpriSeznamPredvajanja(sz.ime); };
      vrsta.appendChild(k);
    });
    var obrazec = el("form", "kat-seznam-uvoz"), polje = document.createElement("input");
    polje.type = "text"; polje.placeholder = t("seznamUvoziNamig"); polje.autocomplete = "off";
    var gumb = el("button", "gumb", ubezi(t("seznamUvozi"))); gumb.type = "submit";
    obrazec.appendChild(polje); obrazec.appendChild(gumb);
    obrazec.onsubmit = function (e) { e.preventDefault(); var v = polje.value; polje.value = ""; uvoziSeznamPredvajanja(v); };
    vrsta.appendChild(obrazec);
    c.appendChild(vrsta);
    narisiYtRacun(c);
    narisiSpotify(c);
  }
  // »Na seznam«: skladbo dodaš na obstoječ seznam predvajanja ali na novega. Meni se odpre ob gumbu, ki ga je odprl.
  function pokaziSeznamMeni(item, ob) {
    var m = $("mediaSeznamMeni"); if (!m || !item) return;
    if (!m.hidden && m._za === item.id) { m.hidden = true; return; }
    m.innerHTML = ""; m._za = item.id;
    var dodaj = function (ime) {
      ime = String(ime || "").trim(); if (!ime) return;
      klic("mediaDodajNaSeznam", [ime, item.id]).then(function (r) {
        m.hidden = true;
        obvesti(r && r.ok ? t("seznamDodano", { ime: ime }) : (r && r.ze ? t("seznamZe", { ime: ime }) : t("seznamNiMogoce")));
        naloziSeznamePredvajanja();
      }, function () { obvesti(t("seznamNiMogoce")); });
    };
    m.appendChild(el("b", "", ubezi(item.naslov || "")));
    (kat.seznami || []).forEach(function (sz) {
      var g = el("button", "gumb", ubezi(sz.ime)); g.type = "button"; g.onclick = function () { dodaj(sz.ime); }; m.appendChild(g);
    });
    var obrazec = document.createElement("form"), polje = document.createElement("input");
    polje.type = "text"; polje.maxLength = 60; polje.placeholder = t("seznamNovIme");
    var nov = el("button", "gumb", ubezi(t("seznamNov"))); nov.type = "submit";
    obrazec.appendChild(polje); obrazec.appendChild(nov);
    obrazec.onsubmit = function (e) { e.preventDefault(); if (!polje.value.trim()) { polje.focus(); return; } dodaj(polje.value); };
    m.appendChild(obrazec);
    m.hidden = false;
    var r = ob.getBoundingClientRect();
    postaviPlavajoce(m, r.left, r.bottom + 6, r.top - 6);
  }
  document.addEventListener("click", function (e) {
    var m = $("mediaSeznamMeni");
    if (m && !m.hidden && !e.target.closest("#mediaSeznamMeni") && !e.target.closest(".kat-na-seznam")) m.hidden = true;
    var plosca = $("mediaViriFilter");
    if (plosca && !plosca.hidden && !e.target.closest(".kat-filter-viri")) {
      plosca.hidden = true; $("mediaViriFilterGumb").setAttribute("aria-expanded", "false");
    }
  });

  // ---- skladba iz kataloga ali s seznama: v spodnji vrstici (naslov, prejšnja/premor/naslednja, premešaj, ponovi, vrsta)
  function osveziKatTrak() {
    narisiTrak();
    if (S.mediaFilter === "domov" && POL.zadnjiSeznam) narisiMediaDomov();     // junak: »Nadaljuj« ali »Predvaja se«
  }
  function skrijKatTrak() { kat.aktivni = null; kat.igra = false; osveziKatTrak(); }
  // Datoteka ali postaja v domacem predvajalniku zamenja skladbo iz kataloga: vrsta kataloga se ustavi (zahteva v teku
  // se ne zacne), spodnja vrstica pokaze, kar res igra, in »Naslednja« ne vzame naslednje skladbe kataloga namesto filma
  // (pregled 14. 10. 2026). Domaci predvajalnik ustavi gostitelj z novo vsebino; vgradni YouTube zapremo sami.
  function opustiKatVrsto() {
    var item = kat.aktivni;
    kat.vrsta = []; kat.zahtevaPredvajanja++;
    if (item && item.okno_youtube) klic("mediaYtUkaz", ["zapri"]).catch(function () {});
    skrijKatTrak();
  }
  function ustaviKatPredvajanje() {
    var item = kat.aktivni;
    kat.vrsta = []; kat.zahtevaPredvajanja++;
    skrijKatTrak();
    if (!item) return;
    if (item.okno_youtube) klic("mediaYtUkaz", ["zapri"]).catch(function () {});
    else klic("predvajalnikUkaz", ["ustavi"]).catch(function () {});
  }
  function premorKatPredvajanja() {
    var item = kat.aktivni; if (!item) return;
    if (item.okno_youtube) { klic("mediaYtUkaz", [kat.igra ? "pauseVideo" : "playVideo"]).catch(function () {}); return; }
    var p = S.mediaPredvajalnik;
    // Domači predvajalnik je ustavljen (konec ali »Ustavi« v vrstici): gumb skladbo zažene znova.
    if (p && (p.stanje === "ustavljeno" || p.stanje === "napaka")) { kat.izVrste = true; odpriKatalogVnos(item.id); return; }
    klic("predvajalnikUkaz", ["premor"]).catch(function () {});
  }

  // ---- čakalna vrsta glasbe (ideja po Tauonu, koda je naša): po koncu skladbe naslednja, premešaj, ponovi
  function vrstaNastavitev(kljuc, privzeto) {
    try { var v = localStorage.getItem("safeer_glasba_" + kljuc); return v == null ? privzeto : v; } catch (e) { return privzeto; }
  }
  function vrstaShrani(kljuc, vrednost) { try { localStorage.setItem("safeer_glasba_" + kljuc, String(vrednost)); } catch (e) {} }
  // Odprt seznam (kat.seznam) -> izvor za »Nazadnje predvajano« (core/nazadnje_predvajano.py). Spotify vodi svoj
  // kontekst (skrit Safeer DRM), Twitch ni seznam skladb: ne nadaljujeta se z Domov.
  function izvorSeznama(sz) {
    if (!sz || sz.sp || sz.twitch || !sz.ime) return null;
    if (sz.yt) return { tip: "yt", ref: String(sz.yt), racun: sz.yt_racun || 0, ime: sz.ime };
    return { tip: "seznam", ref: sz.ime, ime: sz.ime };
  }
  function novaVrsta(seznam, mesto, izvor) {
    kat.vrsta = seznam.map(function (x) { return x.id; });
    kat.vrstaVnosi = seznam;
    kat.vrstaMesto = Math.max(0, Math.min(seznam.length - 1, mesto || 0));
    kat.vrstaZgodovina = []; kat.vrstaNapake = 0;
    kat.vrstaIzvor = izvor || null; kat.vrstaSpremenjena = false; kat.vrstaSamodejno = false; kat.vrstaIzSafeerja = false;
    kat.vrstaZeton++;
    seznam.forEach(function (x) { if (x.v_zivo) kat.zivi[x.id] = 1; });
    premesajVrsto();
  }
  function nastaviVrsto(zacetni, iz) {
    // Skladba z odprtega seznama predvajanja: vrsta je seznam (v njegovem vrstnem redu), ne katalog; s police na Domov polica.
    var izSeznama = !iz && !!kat.seznam && kat.seznam.vnosi.some(function (x) { return x.id === zacetni.id; });
    var osnova = iz ? iz : izSeznama ? kat.seznam.vnosi : (kat.prikazano || kat.katalog || []);
    var seznam = osnova.filter(function (x) { return x.vrsta === zacetni.vrsta && !x.stran; });
    novaVrsta(seznam, seznam.map(function (x) { return x.id; }).indexOf(zacetni.id), izSeznama ? izvorSeznama(kat.seznam) : null);
    narisiVrsto();
  }
  // »Nakljucno« (lastnik, 18. 10. 2026: pokazi pravi vrstni red): ob vklopu dobi vrsta en premesan red - skladba, ki igra,
  // prva, nato vse ostale po enkrat (Fisher-Yates). Plosca vrste kaze ta red. Prej je bila vsaka naslednja skladba
  // izzrebana posebej (lahko tudi ista dvakrat), vrstnega reda pa ni bilo nikjer videti.
  function nakljucnoVklopljeno() { return vrstaNastavitev("premesaj", "0") === "1"; }
  function premesaj(indeksi) {
    for (var j = indeksi.length - 1; j > 0; j--) { var r = Math.floor(Math.random() * (j + 1)), x = indeksi[j]; indeksi[j] = indeksi[r]; indeksi[r] = x; }
    return indeksi;
  }
  // »Predvajaj vse« z vklopljenim »Nakljucno«: zacne s prvo skladbo premesanega reda (ne vedno s prvo s seznama).
  function zacniOdZacetka() {
    var n = (kat.vrsta || []).length, vsi = [];
    if (!nakljucnoVklopljeno() || n < 2) return;
    for (var i = 0; i < n; i++) vsi.push(i);
    kat.vrstaRed = premesaj(vsi);
    kat.vrstaMesto = kat.vrstaRed[0];
  }
  function premesajVrsto() {
    var n = (kat.vrsta || []).length, ostali = [];
    if (!nakljucnoVklopljeno() || n < 2) { kat.vrstaRed = null; return; }
    for (var i = 0; i < n; i++) if (i !== kat.vrstaMesto) ostali.push(i);
    kat.vrstaRed = [kat.vrstaMesto].concat(premesaj(ostali));
  }
  // Vrstni red predvajanja (indeksi vrste): premesan ali naraven.
  function redVrste() {
    var n = (kat.vrsta || []).length, red = [];
    if (kat.vrstaRed && kat.vrstaRed.length === n) return kat.vrstaRed;
    for (var i = 0; i < n; i++) red.push(i);
    return red;
  }
  // Prenos v zivo (postaja, TV, Twitch ali skladba s seznama, ki se je izkazala za tok brez konca): nima konca, zato ga
  // samodejni prehod v vrsti skladb preskoci - sicer bi vrsta na njem obstala (lastnik, 18. 10. 2026).
  function jeVZivo(v) { return !!v && (!!(kat.zivi || {})[v.id] || !!v.v_zivo || /^(radio|tv-v-zivo|twitch)$/.test(v.vrsta || "")); }
  // Vrsta postaj (zavihek Radio, TV): samodejni prehod gre na naslednjo postajo kot doslej (npr. po napaki postaje).
  function vrstaPostaj() {
    var v = kat.vrstaVnosi || [];
    return v.length > 0 && v.every(function (x) { return /^(radio|tv-v-zivo|twitch)$/.test(x.vrsta || ""); });
  }
  function naslednjiVVrsti(smer, samodejno) {
    var n = (kat.vrsta || []).length;
    if (!n) return null;
    var red = redVrste(), poz = red.indexOf(kat.vrstaMesto);
    if (smer < 0) {
      if (kat.vrstaZgodovina && kat.vrstaZgodovina.length) return kat.vrstaZgodovina.pop();
      return red[(poz - 1 + n) % n];
    }
    if (vrstaNastavitev("ponovi", "0") === "1") return kat.vrstaMesto;          // ponovi skladbo
    var preskoci = samodejno && !vrstaPostaj(), vnosi = kat.vrstaVnosi || [];
    for (var k = poz + 1; k < n; k++) if (!(preskoci && jeVZivo(vnosi[red[k]]))) return red[k];
    return null;                                 // konec vrste (predvajajIzVrste: podoben seznam ali znova od zacetka)
  }
  // »Ponovi vse« (privzeto): vrsta znova od zacetka; ob »Nakljucno« z novim premesanim redom, ki se ne zacne s skladbo,
  // ki je pravkar igrala.
  function zacetekKroga(samodejno) {
    var n = (kat.vrsta || []).length, vnosi = kat.vrstaVnosi || [];
    if (n < 2 || vrstaNastavitev("ponoviVse", "1") !== "1") return null;
    if (nakljucnoVklopljeno()) {
      var vsi = []; for (var i = 0; i < n; i++) vsi.push(i);
      kat.vrstaRed = premesaj(vsi);
      if (kat.vrstaRed[0] === kat.vrstaMesto) { kat.vrstaRed[0] = kat.vrstaRed[1]; kat.vrstaRed[1] = kat.vrstaMesto; }
    }
    var red = redVrste(), preskoci = samodejno && !vrstaPostaj();
    for (var k = 0; k < n; k++) if (!(preskoci && jeVZivo(vnosi[red[k]]))) return red[k];
    return null;
  }
  // samodejno: prehod brez uporabnika (konec skladbe, napaka, preskok prenosa v zivo) - ne izbira uporabnika.
  function predvajajIzVrste(smer, samodejno) {
    var mesto = naslednjiVVrsti(smer, samodejno);
    if (mesto == null && smer > 0 && (kat.vrsta || []).length) {
      // Seznam je odigran do konca in uporabnik med poslusanjem ni nicesar spremenil (Nakljucno, Ponovi, rocna izbira
      // skladbe): Safeer sam nadaljuje s seznamom, ki je po zvrsti najblizji (core/nazadnje_predvajano.py).
      if (kat.vrstaIzvor && !kat.vrstaSpremenjena) { nadaljujPodobni(samodejno); return true; }
      mesto = zacetekKroga(samodejno);
    }
    if (mesto == null) return false;
    if (smer > 0) zapomniMestoVrste();
    kat.vrstaMesto = mesto;
    kat.vrstaSamodejno = !!samodejno;
    narisiVrsto();
    kat.izVrste = true;
    odpriKatalogVnos(kat.vrsta[mesto]);
    return true;
  }
  // Vrsta s seznama, ki ga da jedro (»Nadaljuj« na Domov ali podoben seznam): od skladbe `mesto` naprej.
  function zacniSeznam(r, mesto, odSafeerja) {
    var vnosi = (r && r.vnosi) || [];
    if (!vnosi.length) return false;
    prekliciNaslednjo();
    novaVrsta(vnosi, mesto, r.izvor);
    if (nakljucnoVklopljeno() && Array.isArray(r.red) && r.red.length === vnosi.length && r.red[0] !== undefined) {
      kat.vrstaRed = r.red.slice();         // nadaljevanje v istem premesanem redu, kot je bil
      if (kat.vrstaRed.indexOf(kat.vrstaMesto) < 0) premesajVrsto();
    } else if (odSafeerja) zacniOdZacetka();  // podoben seznam ob »Nakljucno«: od prve skladbe premesanega reda
    if (odSafeerja && !vrstaPostaj()) {
      // Seznam, ki ga je izbral Safeer, se ne zacne s prenosom v zivo (vrsta bi na njem obstala).
      var red = redVrste(), poz = red.indexOf(kat.vrstaMesto);
      while (poz < red.length && jeVZivo(vnosi[red[poz]])) poz++;
      if (poz >= red.length) return false;
      kat.vrstaMesto = red[poz];
    }
    kat.vrstaIzSafeerja = !!odSafeerja; kat.vrstaSamodejno = !!odSafeerja;
    narisiVrsto();
    kat.izVrste = !!odSafeerja;
    odpriKatalogVnos(vnosi[kat.vrstaMesto].id);
    return true;
  }
  function nadaljujPodobni(samodejno) {
    var zeton = kat.vrstaZeton;
    klic("mediaNazadnje", ["naslednji"]).then(function (r) { return r; }, function () { return null; }).then(function (r) {
      if (zeton !== kat.vrstaZeton) return;              // uporabnik je medtem izbral drugo vsebino
      if (r && r.vnosi && r.vnosi.length && zacniSeznam(r, 0, true)) return;
      // Ni podobnega seznama (npr. en sam seznam): kot doslej znova od zacetka; brez sporocila uporabniku.
      kat.vrstaSpremenjena = true;
      if (!predvajajIzVrste(1, samodejno)) skrijKatTrak();
    });
  }
  // Skladba s seznama je zacela igrati: zapomnimo si jo za »Nazadnje predvajano« na Domov (mesto v njej javlja jedro).
  function zapomniZadnjiSeznam() {
    var vnosi = kat.vrstaVnosi || [], v = vnosi[kat.vrstaMesto] || {}, slike = [];
    vnosi.forEach(function (x) { if (x.slika && slike.indexOf(x.slika) < 0 && slike.length < 4) slike.push(x.slika); });
    var izvor = Object.assign({}, kat.vrstaIzvor, { slike: slike }), skladba = { id: v.id, naslov: v.naslov, izvajalec: v.izvajalec, slika: v.slika };
    klic("mediaNazadnje", ["zapomni", izvor, kat.vrstaMesto, skladba, vnosi.length, kat.vrstaRed || null, kat.vrstaIzSafeerja]).catch(function () {});
    POL.zadnjiSeznam = { izvor: izvor, mesto: kat.vrstaMesto, poz: redVrste().indexOf(kat.vrstaMesto), skupaj: vnosi.length,
                         skladba: skladba, pozicija: 0 };
    if (S.mediaFilter === "domov") narisiMediaDomov();
  }
  // Skladba v vrsti se je izkazala za prenos v zivo (domaci predvajalnik: tok brez dolzine; YouTube: prenos): oznaka
  // »V zivo« (vrsta, seznam) in - ce jo je zacel samodejni prehod - takoj naslednja.
  function oznaciZivo() {
    var id = kat.aktivniId;          // skladba, ki res igra (vrstaMesto se ob izbiri premakne ze pred zacetkom)
    if (!id || jeVZivo({ id: id }) || vrstaPostaj()) return;
    kat.zivi[id] = 1;
    klic("mediaNazadnje", ["zivo", id]).catch(function () {});
    var k = document.querySelector('#katMreza .kat-kartica[data-id="' + String(id).replace(/"/g, "") + '"]');
    if (k && !k.querySelector(".kat-kakovost")) k.appendChild(el("span", "kat-kakovost", ubezi(t("katVZivo"))));
    S.mediaQueueKey = ""; narisiVrsto();
    if (kat.vrstaSamodejno && kat.vrsta[kat.vrstaMesto] === id) predvajajIzVrste(1, true);
  }
  // Zgodovina za »prejsnja« je omejena: dolgo poslusanje s »ponovi vse« je sicer rasla brez meje (pregled 18. 10. 2026).
  var VRSTA_ZGODOVINA_NAJVEC = 200;
  function zapomniMestoVrste() {
    var z = kat.vrstaZgodovina = kat.vrstaZgodovina || [];
    z.push(kat.vrstaMesto);
    if (z.length > VRSTA_ZGODOVINA_NAJVEC) z.splice(0, z.length - VRSTA_ZGODOVINA_NAJVEC);
  }
  // Skladba v vrsti se ne da predvajati: tiho naprej. Steje zaporedne napake brez uspesnega predvajanja (pregled
  // 18. 10. 2026): s »ponovi vse« ali »ponovi skladbo« bi vrsta, v kateri nic ne gre, sicer tiho krozila v nedogled.
  // Ko pade vsaka skladba vrste (ponovi skladbo: dvakrat zapored), se vrsta tiho ustavi - lastnik: napak predvajalnika
  // uporabniku ne izpisujemo; napake so v sled.log (core/os_katalog.yt_sporocilo).
  function naprejPoNapaki() {
    kat.vrstaNapake = (kat.vrstaNapake || 0) + 1;
    var meja = vrstaNastavitev("ponovi", "0") === "1" ? 2 : Math.max(1, (kat.vrsta || []).length);
    if (kat.vrstaNapake >= meja || !predvajajIzVrste(1, true)) { kat.vrstaNapake = 0; ustaviKatPredvajanje(); }
  }
  // Premešaj in ponovi veljata za vrsto, ki jo vodi stran (vsaj dve skladbi); stanje kaže spodnja vrstica (narisiTrak).
  function narisiVrsto() { narisiTrak(); }

  // predvajanje: [metoda, argumenti, tiho] namesto »mediaPredvajaj« z id (polica, naslednja epizoda); tiho = brez
  // obvestila, ce ni nicesar (ponudbo epizode je medtem ze zacelo ali preklicalo drugo okno).
  function odpriKatalogVnos(id, predvajanje) {
    if (!kat.izVrste) kat.vrstaNapake = 0;      // izbira uporabnika (ne naslednja iz vrste): stevec napak od zacetka
    kat.izVrste = false;
    // Prenos, ki ga izdajatelj ponuja samo na svoji strani (npr. RTV SLO): odpremo ga v Spletu.
    var znan = id ? (kat.katalog || []).filter(function (x) { return x.id === id; })[0] : null;
    if (znan && znan.stran) { katSplet(znan.stran); return; }
    var zahteva = ++kat.zahtevaPredvajanja;
    klic(predvajanje ? predvajanje[0] : "mediaPredvajaj", predvajanje ? predvajanje[1] : [id]).then(function (item) {
      if (zahteva !== kat.zahtevaPredvajanja) return;       // uporabnik je medtem izbral drugo vsebino
      if (!item) return;            // vira ni bilo mogoce razresiti: tiho (sled v sled.log, os_katalog)
      if (item.spotify) {
        // Skladba računa Spotify: predvaja skrit Safeer DRM; upravljanje je v razdelku Spotify (ne v traku predvajalnika).
        if (item.sp_napaka) { spNapaka(item.sp_napaka, true); return; }
        spZacni(item);
        return;
      }
      if (item.tip === "lokalno" && item.pot) { odpriLokalno(item.pot); return; }     // naslednja epizoda z diska
      if (item.napaka_koda === "ni_toka") {
        // Noben vir tega ne predvaja: brez okna, brez strani in brez sporocila (lastnik 18. 10. 2026) – film izgine iz mreže.
        if (item.vrsta === "film") {
          var prej = (kat.katalog || []).length;
          kat.katalog = (kat.katalog || []).filter(function (x) {
            return !(x.vrsta === "film" && (x.id === item.id || x.id === id || (item.tmdb_id && x.tmdb_id === item.tmdb_id)));
          });
          if (typeof kat.skupaj === "number") kat.skupaj = Math.max(kat.katalog.length, kat.skupaj - (prej - kat.katalog.length));
          zapriKatalogPodrobnosti(); narisiKatalog();
        }
        return;
      }
      // Napake predvajanja (tok, napaka, motor ...) so tihe, sled je v sled.log (lastnik 18. 10. 2026). Ostanejo samo
      // stanja, ko mora uporabnik nekaj storiti ali izvedeti (MEDIA_UKREPAJ: prostor na disku, pomnilnik, Twitch ne oddaja).
      if (item.napaka_koda) { if (MEDIA_UKREPAJ[item.napaka_koda]) obvesti(t("mediaNapaka_" + item.napaka_koda)); return; }
      if (item.napaka) { obvesti(item.napaka); return; }
      if (item.sporocilo) { obvesti(item.sporocilo); return; }
      // »stran« ob predvajljivem toku je le izvor (npr. stran filma v arhivu); v Splet gre samo, kar nima toka.
      if (item.stran && !item.native) { katSplet(item.stran); return; }
      kat.aktivni = item; kat.igra = true;
      spOpusti(false);
      kat.aktivniId = id || item.id;
      if (kat.vrstaIzvor && id && kat.vrsta[kat.vrstaMesto] === id) zapomniZadnjiSeznam();
      osveziKatTrak();
    }, function () {});            // most se ni odzval: tiho (napaka predvajanja)
  }
  var MEDIA_UKREPAJ = { ni_prostora: 1, malo_pomnilnika: 1, twitch_ni_v_zivo: 1, twitch_ni_posnetka: 1 };

  // ---- osebne police (lastnik, 14. 10. 2026: najboljse iz Jellyfina, Kodija, Stremia, Ampacha in Serviia)
  // Nadaljuj (z naslednjo epizodo), Nazadnje dodano, Najvec predvajano in Priljubljene na vrhu zavihka - samo police z
  // vsebino in samo na zavihkih, kjer imajo smisel (pravila, stevci in shramba: core/os_police.py). Srcek in »ogledano«
  // sta na vsaki kartici (katalog, knjiznica, postaje); meni kartice odpre desni klik, tipka Meni ali Shift+F10,
  // igralni plosek Y in z misko »⋯« na kartici.
  var POL = { priljubljene: {}, ogledano: {}, police: [], zahteva: 0, podpis: "", stanje: null, nalozeno: "",
              odkrivanje: [], odkrZahteva: 0, odkrPodpis: "", odkrOd: 0, zadnjiSeznam: null };
  var POLICE_NASLOVI = { nadaljuj: "policaNadaljujGledanje", nazadnje: "policaNazadnje", najvec: "policaNajvec", priljubljene: "policaPriljubljene",
                        glasba: "policaGlasba", odkrij_filmi: "odkrijFilmi", odkrij_serije: "odkrijSerije", odkrij_glasba: "odkrijGlasba",
                        odkrij_youtube: "odkrijYoutube", odkrij_spotify: "odkrijSpotify", odkrij_twitch: "odkrijTwitch", odkrij_radio: "odkrijRadio" };
  var OGLEDLJIVE = { filmi: 1, serije: 1, film: 1, serija: 1, video: 1 };
  // Isti kljuc kot core/os_police.kljuc_vnosa (enakost varuje tests/test_os_police.py).
  function kljucVnosa(x) {
    var tmdb = Number(x && x.tmdb_id) || 0, s = Number(x && x.sezona) || 0, e = Number(x && x.epizoda) || 0;
    if (tmdb && x.vrsta === "serija") return s && e ? "tmdb:tv:" + tmdb + ":" + s + ":" + e : "tmdb:tv:" + tmdb;
    if (tmdb && x.vrsta === "film") return "tmdb:film:" + tmdb;
    return x && x.id ? ("id:" + x.id).slice(0, 400) : "";
  }
  // Kar kartica na polici potrebuje, ce naslova ni vec v katalogu (naslov toka samo pri prenosih in skladbah).
  function opisVnosa(x) {
    var o = { id: x.id, naslov: x.naslov, vrsta: x.vrsta, slika: x.slika, izvajalec: x.izvajalec, tmdb_id: x.tmdb_id,
              sezona: x.sezona, epizoda: x.epizoda, leto: x.leto };
    if (/^(radio|tv-v-zivo|glasba|podcast)$/.test(x.vrsta || "") && /^https?:\/\//.test(x.url || "")) o.url = x.url;
    return o;
  }
  function jePriljubljena(k) { return !!(k && POL.priljubljene[k]); }
  function jeOgledano(card) {
    var k = card.getAttribute("data-kljuc") || "";
    return k.indexOf("pot:") === 0 ? card.getAttribute("data-ogledano") === "1" : !!POL.ogledano[k];
  }
  function naloziPolice() {
    if (!most) return;
    var zahteva = ++POL.zahteva;
    klic("mediaPolice", [S.mediaFilter, S.mediaIskanje]).then(function (r) {
      if (zahteva !== POL.zahteva || !r) return;
      var stanje = (r.priljubljene || []).join("\n") + "|" + (r.ogledano || []).join("\n");
      POL.priljubljene = {}; (r.priljubljene || []).forEach(function (k) { POL.priljubljene[k] = 1; });
      POL.ogledano = {}; (r.ogledano || []).forEach(function (k) { POL.ogledano[k] = 1; });
      POL.police = Array.isArray(r.police) ? r.police : [];
      if (S.mediaFilter === "domov") POL.zadnjiSeznam = r.nazadnje_seznam || null;    // Nazadnje predvajano (junak)
      POL.nalozeno = S.mediaFilter;
      narisiPolice();
      narisiVgrajenePloscice();          // ploscice lastnih strani (samo na Domov)
      if (stanje !== POL.stanje) { POL.stanje = stanje; osveziOznakeKartic(); }
    }).catch(function () {});
  }
  // Srcek in znak »ogledano« na kartici (brez ponovnega risanja: izbor in drsnik ostaneta); dostopno ime pove oboje.
  function oznaciKartico(card) {
    var k = card.getAttribute("data-kljuc"); if (!k) return;
    var mesto = card.querySelector(".kat-plakat, .media-kartica-art") || card, fav = jePriljubljena(k), og = jeOgledano(card);
    var znak = function (razred, da, ikona) {
      var z = mesto.querySelector(":scope > ." + razred);
      if (da && !z) { z = el("span", razred, svg(ikona)); z.setAttribute("aria-hidden", "true"); mesto.appendChild(z); }
      else if (!da && z) z.remove();
    };
    znak("kat-srce", fav, "srce");
    znak("kat-ogledano", og, "kljukica");
    var ime = card.getAttribute("data-ime");
    if (ime) card.setAttribute("aria-label", ime + (fav ? ", " + t("policaPriljubljena") : "") + (og ? ", " + t("ogledanoOznaka") : ""));
  }
  function osveziOznakeKartic() { document.querySelectorAll("[data-kljuc]").forEach(oznaciKartico); }
  function poveziMeniKartice(card, opis) {
    if (!opis.kljuc) return;
    card.setAttribute("data-kljuc", opis.kljuc);
    card._opis = opis;
    card.addEventListener("contextmenu", function (e) { e.preventDefault(); e.stopPropagation(); odpriMeniKartice(card); });
    // Z misko: »⋯« na kartici (ni posebna tarca tipkovnice - ta ima tipko Meni, kartica ostane en korak puscice).
    var vec = el("span", "kat-vec", svg("vec")); vec.title = t("karticaMeni"); vec.setAttribute("aria-hidden", "true");
    vec.addEventListener("click", function (e) { e.stopPropagation(); e.preventDefault(); odpriMeniKartice(card, vec); });
    card.appendChild(vec);
    oznaciKartico(card);
  }
  function odpriMeniKartice(card, ob) {
    var m = $("mediaKarticaMeni"), o = card && card._opis; if (!m || !o) return;
    m.innerHTML = ""; m._kartica = card;
    m.setAttribute("aria-label", o.naslov || t("karticaMeni"));
    var naslov = el("b", "", ubezi(o.naslov || "")); naslov.setAttribute("aria-hidden", "true"); m.appendChild(naslov);
    var postavka = function (ikona, besedilo, dejanje) {
      var b = el("button", "", svg(ikona) + "<span>" + ubezi(besedilo) + "</span>");
      b.type = "button"; b.setAttribute("role", "menuitem");
      b.addEventListener("click", function () { zapriMeniKartice(true); dejanje(); });
      m.appendChild(b);
    };
    var fav = jePriljubljena(o.kljuc);
    if (!o.brezSrca) postavka("srce", t(fav ? "priljubljenaOdstrani" : "priljubljenaDodaj"), function () { preklopiPriljubljeno(o, !fav); });
    if (o.ogledljivo) {
      var og = jeOgledano(card);
      postavka("kljukica", t(og ? "ogledanoOdznaci" : "ogledanoOznaci"), function () { preklopiOgledano(o, !og); });
    }
    if (!m.querySelector("[role=menuitem]")) return;
    m.hidden = false;
    var r = (ob || card).getBoundingClientRect();
    postaviPlavajoce(m, r.left, ob ? r.bottom + 6 : r.top + 24, ob ? r.top - 6 : null);
    m.querySelector("[role=menuitem]").focus();
  }
  function zapriMeniKartice(vrniFokus) {
    var m = $("mediaKarticaMeni"); if (!m || m.hidden) return false;
    m.hidden = true;
    if (vrniFokus && m._kartica && document.contains(m._kartica)) { try { m._kartica.focus({ preventScroll: true }); } catch (e) { m._kartica.focus(); } }
    return true;
  }
  function preklopiPriljubljeno(o, da) {
    return klic("mediaPriljubljena", [o.kljuc, da, o.opis || {}]).then(function (stanje) {
      if (stanje) POL.priljubljene[o.kljuc] = 1; else delete POL.priljubljene[o.kljuc];
      obvesti(stanje === da ? t(da ? "priljubljenaDodano" : "priljubljenaOdstranjeno") : t("niUspelo"));
      osveziOznakeKartic(); naloziPolice();
      return !!stanje;
    }, function () { obvesti(t("niUspelo")); return jePriljubljena(o.kljuc); });
  }
  function preklopiOgledano(o, da) {
    return klic("mediaOgledano", [o.kljuc, da, o.opis || {}]).then(function (r) {
      if (!r || !r.ok) { obvesti(t("niUspelo")); return !da; }
      if (o.kljuc.indexOf("pot:") === 0) {
        document.querySelectorAll("[data-kljuc]").forEach(function (c) { if (c.getAttribute("data-kljuc") === o.kljuc) c.setAttribute("data-ogledano", da ? "1" : ""); });
        naloziMedije();                 // ogledan film zacne od zacetka: merilo na kartici izgine
      } else if (da) POL.ogledano[o.kljuc] = 1; else delete POL.ogledano[o.kljuc];
      osveziOznakeKartic(); naloziPolice();
      return da;
    }, function () { obvesti(t("niUspelo")); return !da; });
  }
  // Srcek in ogledano v podrobnostih filma ali serije: prava gumba (aria-pressed), dosegljiva s tipkovnico in daljincem.
  function dejanjaPodrobnosti(item) {
    var vrstica = el("div", "kat-detail-dejanja"), k = kljucVnosa(item), opis = opisVnosa(item);
    if (!k) return vrstica;
    var srce = el("button", "gumb kat-gumb-srce"); srce.type = "button";
    var narisi = function () {
      var da = jePriljubljena(k);
      srce.setAttribute("aria-pressed", da ? "true" : "false");
      srce.innerHTML = svg("srce") + "<span>" + ubezi(t(da ? "priljubljenaOdstrani" : "priljubljenaDodaj")) + "</span>";
    };
    srce.onclick = function () { preklopiPriljubljeno({ kljuc: k, opis: opis }, !jePriljubljena(k)).then(narisi); };
    narisi(); vrstica.appendChild(srce);
    if (item.vrsta === "film") {
      var og = el("button", "gumb kat-gumb-ogledano"); og.type = "button";
      var narisiOg = function () {
        var da = !!POL.ogledano[k];
        og.setAttribute("aria-pressed", da ? "true" : "false");
        og.innerHTML = svg("kljukica") + "<span>" + ubezi(t(da ? "ogledanoOdznaci" : "ogledanoOznaci")) + "</span>";
      };
      og.onclick = function () { preklopiOgledano({ kljuc: k, opis: opis }, !POL.ogledano[k]).then(narisiOg); };
      narisiOg(); vrstica.appendChild(og);
    }
    return vrstica;
  }
  function gumbOgledanoEpizode(item, sezona, ep, vrstica) {
    var k = "tmdb:tv:" + item.tmdb_id + ":" + sezona + ":" + ep.stevilka;
    var opis = { naslov: (item.naslov || "") + " · " + (ep.naslov || ""), vrsta: "serija", tmdb_id: item.tmdb_id,
                 sezona: sezona, epizoda: ep.stevilka, slika: ep.slika || item.slika };
    var g = el("button", "gumb-ikona kat-epizoda-ogledano", svg("kljukica")); g.type = "button";
    var narisi = function () {
      var da = !!POL.ogledano[k];
      g.setAttribute("aria-pressed", da ? "true" : "false");
      g.title = t(da ? "ogledanoOdznaci" : "ogledanoOznaci");
      g.setAttribute("aria-label", g.title + " – E" + String(ep.stevilka).padStart(2, "0"));
      vrstica.classList.toggle("ogledana", da);
    };
    g.onclick = function () { preklopiOgledano({ kljuc: k, opis: opis }, !POL.ogledano[k]).then(narisi); };
    narisi();
    return g;
  }
  function naslovPolice(id, zavihek) {
    if (id === "nadaljuj") return t((zavihek || S.mediaFilter) === "glasba" ? "policaNadaljujPoslusanje" : "policaNadaljujGledanje");
    return t(POLICE_NASLOVI[id] || id);
  }
  function ikonaPolice(v) {
    return v.vrsta === "glasba" || v.vrsta === "podcast" ? "glasba" : v.vrsta === "radio" ? "radio" : v.vrsta === "slike" ? "slika" : "video";
  }
  function karticaPolice(v, polica) {
    var card = el("button", "kat-kartica media-polica-kartica" + (v.naslednja ? " naslednja" : "")); card.type = "button";
    card.setAttribute("role", "listitem");
    var plakat = el("span", "kat-plakat"); card.appendChild(plakat);
    if (v.slika) {
      var image = document.createElement("img"); image.alt = ""; image.loading = "lazy"; image.src = v.slika;
      image.onerror = function () { image.replaceWith(el("span", "kat-brez-slike", svg(ikonaPolice(v)))); };
      plakat.appendChild(image);
    } else plakat.appendChild(el("span", "kat-brez-slike", svg(ikonaPolice(v))));
    var napredek = v.pozicija > 0 && v.trajanje > v.pozicija;
    if (napredek) plakat.appendChild(el("span", "kat-merilo", '<i style="width:' + Math.max(2, Math.min(100, Math.round(100 * v.pozicija / v.trajanje))) + '%"></i>'));
    var data = el("span", "kat-podatki"), naslov = el("b", "", ubezi(v.naslov || "")); naslov.title = v.naslov || "";
    data.appendChild(naslov);
    // Naslednja epizoda ima oznako na plakatu, pod naslovom pa katero (S02E01 · naslov); nedokoncano pove, koliko je se.
    if (v.naslednja) plakat.appendChild(el("span", "kat-naslednja", ubezi(t("policaNaslednja"))));
    var meta = v.naslednja ? (v.podnaslov || t("policaNaslednja")) :
      napredek ? t("policaOstane", { n: Math.max(1, Math.round((v.trajanje - v.pozicija) / 60)) }) :
      polica === "najvec" && v.n ? t("policaPredvajano", { n: v.n }) : (v.podnaslov || v.izvajalec || katOznaka(v.vrsta) || mediaVrsta(v.vrsta));
    var vrsticaMeta = el("span", "kat-meta"); vrsticaMeta.appendChild(el("span", "", ubezi(meta)));
    data.appendChild(vrsticaMeta); card.appendChild(data);
    card.setAttribute("data-ime", (v.naslov || "") + " — " + meta);
    card.setAttribute("data-ogledano", v.ogledano ? "1" : "");
    card.title = (v.naslov || "") + " · " + meta;
    poveziMeniKartice(card, { kljuc: v.kljuc, naslov: v.naslov || "", ogledljivo: !!OGLEDLJIVE[v.vrsta] && !v.album, brezSrca: !!v.album,
                              opis: { id: v.id, naslov: v.naslov, vrsta: v.vrsta, slika: v.slika, izvajalec: v.izvajalec, tmdb_id: v.tmdb_id,
                                      sezona: v.sezona, epizoda: v.epizoda, url: v.url, pot: v.pot } });
    card.addEventListener("click", function () { predvajajSPolice(v, polica); });
    return card;
  }
  function narisiPolice() {
    var c = $("mediaPolice"); if (!c) return;
    // Samo police tega zavihka: po menjavi zavihka police prejsnjega (npr. Filmi na Domov) ne ostanejo vidne, dokler
    // odgovor (lahko caka na TMDB) ne pride (pregled 14. 10. 2026).
    var police = POL.nalozeno === S.mediaFilter ? (POL.police || []).filter(function (p) { return !jeSkrito("polica:" + p.id); }) : [];
    var podpis = JSON.stringify(police) + "|" + jezik + "|" + S.mediaFilter;
    if (podpis === POL.podpis) return;          // isti podatki: izbor in polozaj police ostaneta
    POL.podpis = podpis;
    var izbran = document.activeElement && c.contains(document.activeElement) ? document.activeElement.getAttribute("data-kljuc") : null;
    var odmiki = {};
    c.querySelectorAll(".media-polica").forEach(function (p) { odmiki[p.getAttribute("data-polica")] = p.querySelector(".media-polica-vrsta").scrollLeft; });
    c.innerHTML = "";
    c.hidden = !police.length;
    var domov = S.mediaFilter === "domov";
    police.forEach(function (p) {
      // Zavihek, ki ga odpre »Vse →« na Domov: vrsta, ki je na polici najpogostejsa (polica glasbe: Glasba).
      var zavihek = domov ? zavihekPolice(p) : S.mediaFilter;
      // Glasba, radio in TV: kvadratne kartice (manj visine, katalog ostane blizu); video: plakati kot v katalogu.
      var zvok = zavihek === "glasba" || zavihek === "radio" || zavihek === "tv";
      var sekcija = el("section", "media-polica" + (zvok ? " zvok" : "")); sekcija.setAttribute("data-polica", p.id);
      var naslov = naslovPolice(p.id, zavihek);
      var glava = el("h3", "media-polica-naslov", ubezi(naslov));
      glava.id = "mediaPolica_" + p.id;
      sekcija.setAttribute("aria-labelledby", glava.id);
      if (domov) {
        var vrhPolice = el("div", "media-polica-glava");
        vrhPolice.appendChild(glava);
        var vse = el("button", "media-polica-vse", '<span>' + ubezi(t("domovVse")) + '</span>' + svg("desno"));
        vse.type = "button";
        vse.setAttribute("aria-label", t("domovVseOznaka", { polica: naslov, zavihek: t("media_" + zavihek) }));
        vse.setAttribute("data-zavihek", zavihek);
        vse.addEventListener("click", function () { izberiZavihekMedijev(zavihek); $("vsebina").scrollTop = 0; });
        vrhPolice.appendChild(vse);
        vrhPolice.appendChild(gumbSkrijPolico("polica:" + p.id, naslov));   // vsako polico na Domov lahko skrije (lastnik, 18. 10.)
        sekcija.appendChild(vrhPolice);
      } else sekcija.appendChild(glava);
      var vrsta = el("div", "media-polica-vrsta"); vrsta.setAttribute("role", "list");
      (p.vnosi || []).forEach(function (v) { vrsta.appendChild(karticaPolice(v, p.id)); });
      sekcija.appendChild(vrsta); c.appendChild(sekcija);
      if (odmiki[p.id]) vrsta.scrollLeft = odmiki[p.id];
    });
    if (izbran) {
      var enaka = Array.prototype.filter.call(c.querySelectorAll("[data-kljuc]"), function (k) { return k.getAttribute("data-kljuc") === izbran; })[0];
      if (enaka) { try { enaka.focus({ preventScroll: true }); } catch (e) { enaka.focus(); } }
    }
    if (domov) narisiMediaDomov();
  }
  // ---- police odkrivanja na Domov (lastnik, 17. 10. 2026: »Domov deluje zelo prazno in neprijetno«): pod osebnimi
  // policami vsebina iz virov, ki jih Medijski center ze ima - priljubljeni filmi in serije, glasba, seznami YouTuba in
  // Spotifyja (ce je uporabnik prijavljen), Twitch v zivo in radio. Pravila (ena kartica za isto vsebino, brez
  // zasebnih dodatkov, prazne police izpadejo) so v core/os_police.sestavi_odkrivanje; tu se izloci se, kar je ze na
  // osebni polici (police se nalagata vzporedno). Kliki gredo po obstojecih poteh kataloga - brez nove logike predvajanja.
  function naloziOdkrivanje() {
    if (!most) return;
    var zahteva = ++POL.odkrZahteva;
    POL.odkrOd = POL.odkrOd || (window.performance ? performance.now() : Date.now());
    var kljuci = [];
    if (POL.nalozeno === "domov") (POL.police || []).forEach(function (p) { (p.vnosi || []).forEach(function (v) { if (v.kljuc) kljuci.push(v.kljuc); }); });
    klic("mediaOdkrivanje", [kat.drzavaRadia || "", kljuci]).then(function (r) {
      if (zahteva === POL.odkrZahteva && r) prevzemiOdkrivanje(r);
    }).catch(function () {});
  }
  function prevzemiOdkrivanje(r) {
    POL.odkrivanje = Array.isArray(r.police) ? r.police : [];
    if (POL.odkrOd && POL.odkrivanje.length) {
      // Meritev (AGENTS.md: trditve o hitrosti podpre meritev): od odprtja Domov do prvih polic odkrivanja.
      console.info("[Domov] police odkrivanja v " + Math.round((window.performance ? performance.now() : Date.now()) - POL.odkrOd) + " ms");
      POL.odkrOd = 0;
    }
    if (S.mediaFilter === "domov") narisiMediaDomov();
  }
  // Police odkrivanja, kot jih Domov pokaze: brez skritih zavihkov (Prilagodi meni) in brez kartic z osebnih polic.
  function odkrivanjeVidno() {
    var osebni = {};
    (POL.police || []).forEach(function (p) { (p.vnosi || []).forEach(function (v) { if (v.kljuc) osebni[v.kljuc] = 1; }); });
    return (POL.odkrivanje || []).map(function (p) {
      return { id: p.id, zavihek: p.zavihek, vnosi: (p.vnosi || []).filter(function (v) { return !osebni[v.kljuc]; }) };
    }).filter(function (p) { return p.vnosi.length && !jeSkrito("kat:" + p.zavihek) && !jeSkrito("polica:" + p.id); });
  }
  function junakOdkrivanja() {
    var police = odkrivanjeVidno().filter(function (p) { return p.id === "odkrij_filmi" || p.id === "odkrij_serije"; });
    var vsi = [];
    police.forEach(function (p) { p.vnosi.forEach(function (v) { vsi.push({ v: v, polica: p.id }); }); });
    var izbor = vsi.filter(function (x) { return x.v.ozadje; })[0] || vsi.filter(function (x) { return x.v.slika; })[0];
    if (!izbor) return null;
    var v = izbor.v;
    return { v: Object.assign({}, v, { zanr: Array.isArray(v.zanri) && v.zanri.length ? v.zanri[0] : v.zanr }), polica: izbor.polica, odkrij: true };
  }
  function naslovOdkrivanja(v) {
    if (v.tip === "yt-seznam" && v.posebni) return ytImeSeznama({ posebni: v.posebni, ime: v.naslov });
    if (v.tip === "sp-seznam" && v.posebni === "vseckane") return t("spVseckane");
    return v.naslov || "";
  }
  function metaOdkrivanja(v) {
    if (v.tip === "yt-seznam" || v.tip === "sp-seznam") return v.stevilo ? stSkladb(v.stevilo) : (v.podnaslov || "");
    if (/^twitch/.test(v.vrsta || "")) return twitchOpis(v);
    if (v.vrsta === "glasba" && v.izvajalec) return v.izvajalec;
    return [v.leto, v.ocena ? "★ " + Number(v.ocena).toFixed(1) : ""].filter(Boolean).join(" · ") || katOznaka(v.vrsta);
  }
  function kliknOdkrivanje(v, polica) {
    if (v.tip === "yt-seznam") {
      izberiZavihekMedijev("glasba");
      odpriYtSeznam({ id: v.id, racun: v.racun || 0, posebni: v.posebni || "", ime: v.naslov });
      return;
    }
    if (v.tip === "sp-seznam") { izberiZavihekMedijev("glasba"); odpriSpSeznam(v.id, naslovOdkrivanja(v)); return; }
    if (v.vrsta === "twitch-kanal") { izberiZavihekMedijev("twitch"); odpriTwitchKanal(v.login, v.naslov); return; }
    if (v.tmdb_id || v.vrsta === "serija" || (v.vrsta === "film" && !v.peertube_uuid)) { odpriKatalogPodrobnosti(v.id); return; }
    if (v.vrsta === "glasba" || v.vrsta === "podcast") {
      // Vrsta skladb je polica (kot v katalogu je vrsta mreza): naslednja skladba je naslednja kartica.
      var p = (POL.odkrivanje || []).filter(function (x) { return x.id === polica; })[0];
      nastaviVrsto(v, p ? p.vnosi : [v]);
      odpriKatalogVnos(v.id);
      return;
    }
    kat.vrsta = []; narisiVrsto();
    odpriKatalogVnos(v.id);
  }
  function karticaOdkrivanja(v, polica) {
    var card = el("button", "kat-kartica media-polica-kartica"); card.type = "button";
    card.setAttribute("role", "listitem");
    var seznam = v.tip === "yt-seznam" || v.tip === "sp-seznam";
    var plakat = el("span", "kat-plakat"); card.appendChild(plakat);
    if (v.vrsta === "radio" || v.vrsta === "tv-v-zivo") plakat.classList.add("kat-logotip");
    if (/^twitch/.test(v.vrsta || "")) plakat.classList.add("kat-siroko");
    var ikona = seznam ? "glasba" : katIkona(v.vrsta);
    if (v.slika) {
      var image = document.createElement("img"); image.alt = ""; image.loading = "lazy"; image.src = v.slika;
      image.onerror = function () { image.replaceWith(el("span", "kat-brez-slike", svg(ikona))); };
      plakat.appendChild(image);
    } else plakat.appendChild(el("span", "kat-brez-slike", svg(ikona)));
    if (v.vrsta === "twitch") card.appendChild(el("span", "kat-kakovost", ubezi(t("katVZivo"))));      // kot v katalogu
    var naslov = naslovOdkrivanja(v), meta = metaOdkrivanja(v);
    var data = el("span", "kat-podatki"), b = el("b", "", ubezi(naslov)); b.title = naslov;
    data.appendChild(b);
    var vrsticaMeta = el("span", "kat-meta"); vrsticaMeta.appendChild(el("span", "", ubezi(meta)));
    data.appendChild(vrsticaMeta); card.appendChild(data);
    card.setAttribute("data-ime", naslov + (meta ? " — " + meta : ""));
    card.setAttribute("aria-label", card.getAttribute("data-ime"));
    card.title = naslov + (meta ? " · " + meta : "");
    // Srcek in »ogledano« kot v katalogu (isti kljuc); seznami racunov in Twitch ga nimajo (ne gredo v Link).
    if (!seznam && !/^twitch/.test(v.vrsta || "")) {
      poveziMeniKartice(card, { kljuc: v.kljuc, naslov: naslov, ogledljivo: !!OGLEDLJIVE[v.vrsta], opis: opisVnosa(v) });
    }
    card.addEventListener("click", function () { kliknOdkrivanje(v, polica); });
    return card;
  }
  function narisiOdkrivanje() {
    var c = $("mediaOdkrivanje"); if (!c || typeof POL === "undefined") return;      // POL: narisiMedije tece ze ob zagonu
    var police = S.mediaFilter === "domov" ? odkrivanjeVidno() : [];
    var podpis = JSON.stringify(police) + "|" + jezik;
    c.hidden = !police.length;
    if (podpis === POL.odkrPodpis) return;          // isti podatki: izbor in polozaj vrst ostaneta
    POL.odkrPodpis = podpis;
    var izbran = document.activeElement && c.contains(document.activeElement) ? document.activeElement.getAttribute("data-kljuc") : null;
    var odmiki = {};
    c.querySelectorAll(".media-polica").forEach(function (p) { odmiki[p.getAttribute("data-polica")] = p.querySelector(".media-polica-vrsta").scrollLeft; });
    c.innerHTML = "";
    c.hidden = !police.length;
    police.forEach(function (p) {
      var zvok = p.zavihek === "glasba" || p.zavihek === "radio";
      var sekcija = el("section", "media-polica" + (zvok ? " zvok" : "") + (p.zavihek === "twitch" ? " siroko" : ""));
      sekcija.setAttribute("data-polica", p.id);
      var naslov = naslovPolice(p.id, p.zavihek);
      var glava = el("h3", "media-polica-naslov", ubezi(naslov)); glava.id = "mediaPolica_" + p.id;
      sekcija.setAttribute("aria-labelledby", glava.id);
      var vrh = el("div", "media-polica-glava"); vrh.appendChild(glava);
      var vse = el("button", "media-polica-vse", '<span>' + ubezi(t("domovVse")) + '</span>' + svg("desno"));
      vse.type = "button";
      vse.setAttribute("aria-label", t("domovVseOznaka", { polica: naslov, zavihek: t("media_" + p.zavihek) }));
      vse.setAttribute("data-zavihek", p.zavihek);
      vse.addEventListener("click", function () { izberiZavihekMedijev(p.zavihek); $("vsebina").scrollTop = 0; });
      vrh.appendChild(vse); vrh.appendChild(gumbSkrijPolico("polica:" + p.id, naslov)); sekcija.appendChild(vrh);
      var vrsta = el("div", "media-polica-vrsta"); vrsta.setAttribute("role", "list");
      p.vnosi.forEach(function (v) { vrsta.appendChild(karticaOdkrivanja(v, p.id)); });
      sekcija.appendChild(vrsta); c.appendChild(sekcija);
      if (odmiki[p.id]) vrsta.scrollLeft = odmiki[p.id];
    });
    if (izbran) {
      var enaka = Array.prototype.filter.call(c.querySelectorAll("[data-kljuc]"), function (k) { return k.getAttribute("data-kljuc") === izbran; })[0];
      if (enaka) { try { enaka.focus({ preventScroll: true }); } catch (e) { enaka.focus(); } }
    }
  }
  // ---- Domov (lastnik, 14. 10. 2026, skica Safeer Playerja): zacetna stran Medijskega centra - junak z eno pravo
  // vsebino, pod njim osebne police (core/os_police.py, zavihek »domov«) z »Vse →«. Prazne police se ne narisejo; brez
  // vsake police ostane prazno stanje z gumbom Dodaj. Junak kaze samo podatke, ki jih vnos res ima (leto, dolzina,
  // zvrst, vir) - brez izmisljenih oznak (4K, Dolby, ocene).
  var ZAVIHEK_VRSTE = { filmi: "filmi", film: "filmi", serije: "serije", serija: "serije", video: "video", glasba: "glasba",
                        podcast: "glasba", podkast: "glasba", radio: "radio", tv: "tv", "tv-v-zivo": "tv", slike: "slike" };
  function zavihekPolice(p) {
    if (p.id === "glasba") return "glasba";
    var stevci = {}, najvec = "", n = 0;
    (p.vnosi || []).forEach(function (v) {
      var z = ZAVIHEK_VRSTE[v.vrsta]; if (!z) return;
      stevci[z] = (stevci[z] || 0) + 1;
      if (stevci[z] > n) { n = stevci[z]; najvec = z; }
    });
    return najvec || "filmi";
  }
  // Glavno mesto na Domov (lastnik, 18. 10. 2026: »Nazadnje predvajano« namesto »Nazadnje dodano«): zadnji seznam z
  // »Nadaljuj«; brez njega, kar je uporabnik nazadnje gledal ali poslusal, sele nato odkrivanje.
  function izbiraJunaka() {
    var police = POL.police || [];
    var prvi = function (id) {
      var p = police.filter(function (x) { return x.id === id; })[0];
      return p && p.vnosi && p.vnosi[0] ? { v: p.vnosi[0], polica: id } : null;
    };
    if (POL.zadnjiSeznam && POL.zadnjiSeznam.izvor) return { seznam: POL.zadnjiSeznam, polica: "predvajano" };
    return prvi("nadaljuj") || prvi("glasba") || junakOdkrivanja();
  }
  function imeZvrsti(id) {
    var z = KAT_FILMSKI_ZANRI.concat(KAT_SERIJSKI_ZANRI).filter(function (x) { return Number(x[0]) === Number(id); })[0];
    return z ? t(z[1]) : "";
  }
  function trajanjeBesedilo(sekunde) {
    var m = Math.round((Number(sekunde) || 0) / 60);
    if (m < 1) return "";
    return m >= 60 ? t("domovUre", { h: Math.floor(m / 60), m: m % 60 }) : t("domovMinut", { n: m });
  }
  // Podatki junaka: samo polja, ki jih ima vnos (core/os_katalog._vnos_opisa ali krajevna knjiznica).
  function podatkiJunaka(v) {
    var napredek = v.pozicija > 0 && v.trajanje > v.pozicija;
    var meta = [];
    if (Number(v.leto) >= 1900) meta.push(String(v.leto));
    if (napredek) meta.push(t("policaOstane", { n: Math.max(1, Math.round((v.trajanje - v.pozicija) / 60)) }));
    else if (!v.album && v.trajanje > 0 && v.vrsta !== "glasba") meta.push(trajanjeBesedilo(v.trajanje));
    var zvrst = v.zanr ? imeZvrsti(v.zanr) : "";
    if (zvrst) meta.push(zvrst);
    var vrsta = ZAVIHEK_VRSTE[v.vrsta];
    if (vrsta) meta.push(t("media_" + vrsta));
    return {
      naslov: v.naslov || "",
      pod: v.naslednja ? (v.podnaslov || t("policaNaslednja")) : (v.podnaslov || v.izvajalec || ""),
      meta: meta.filter(Boolean),
      vir: v.vir || (v.tip === "lokalno" ? t("mediaTaRacunalnik") : ""),
      napredek: napredek ? Math.max(2, Math.min(100, Math.round(100 * v.pozicija / v.trajanje))) : 0,
      slika: v.slika || "",
      ozadje: v.ozadje || ""
    };
  }
  // ---- Nazadnje predvajano (core/nazadnje_predvajano.py): zadnji seznam kot junak na Domov z »Nadaljuj«.
  function imeIzvora(izvor) {
    if (!izvor) return "";
    return izvor.tip === "samodejni" ? imeSamodejnega({ vrsta: izvor.vrsta, ime: izvor.ime || "" }) : (izvor.ime || "");
  }
  // Zadnji seznam je ta trenutek nalozen v vrsti strani (igra ali je na premoru).
  function seznamVVrsti(rec) {
    var a = kat.vrstaIzvor, b = rec && rec.izvor;
    return !!(a && b && kat.aktivni && kat.vrsta.length && kat.aktivniId === kat.vrsta[kat.vrstaMesto] &&
              a.tip === b.tip && a.ref === b.ref && (a.racun || 0) === (b.racun || 0));
  }
  function nadaljujZadnjiSeznam() {
    var rec = POL.zadnjiSeznam;
    if (seznamVVrsti(rec)) { if (!kat.igra) premorKatPredvajanja(); return; }
    klic("mediaNazadnje", ["nadaljuj"]).then(function (r) {
      if (r && r.vnosi && r.vnosi.length) { zacniSeznam(r, r.mesto || 0, false); return; }
      // Seznama ni vec ali ga ni mogoce prebrati: tiho izgine z Domov (lastnik 18. 10. 2026), sled je v sled.log.
      POL.zadnjiSeznam = null; narisiMediaDomov();
    }, function () {});
  }
  function narisiJunakaSeznama(junak, rec) {
    var izvor = rec.izvor, sk = rec.skladba || {}, igra = seznamVVrsti(rec) && kat.igra;
    // Mesto v vrstnem redu predvajanja (ob »Nakljucno« premesan red, kot ga kaze plosca vrste).
    var slike = (izvor.slike || []).slice(0, 4), skupaj = Number(rec.skupaj) || 0, mesto = Math.max(0, Number(rec.poz != null ? rec.poz : rec.mesto) || 0);
    var podpis = JSON.stringify(["seznam", rec, igra, jezik]);
    if (junak._podpis === podpis) return;
    junak._podpis = podpis;
    var prejFokus = document.activeElement && junak.contains(document.activeElement);
    junak.innerHTML = "";
    junak.classList.toggle("z-ozadjem", slike.length > 0);
    if (slike.length) {
      var oz = el("div", "media-junak-ozadje zamegljeno"); oz.setAttribute("aria-hidden", "true");
      var slikaOzadja = document.createElement("img"); slikaOzadja.alt = ""; slikaOzadja.src = slike[0];
      slikaOzadja.onerror = function () { oz.remove(); junak.classList.remove("z-ozadjem"); };
      oz.appendChild(slikaOzadja); junak.appendChild(oz);
    }
    var plakat = el("div", "media-junak-plakat kvadrat media-junak-seznam"); plakat.setAttribute("aria-hidden", "true");
    plakat.appendChild(kolaz(slike));
    if (skupaj > 1) plakat.appendChild(el("span", "kat-merilo", '<i style="width:' + Math.max(2, Math.min(100, Math.round(100 * (mesto + 1) / skupaj))) + '%"></i>'));
    junak.appendChild(plakat);
    var besedilo = el("div", "media-junak-besedilo");
    besedilo.appendChild(el("span", "media-junak-oznaka", ubezi(t("policaNazadnjePredvajano"))));
    var h = el("h2", "", ubezi(imeIzvora(izvor))); h.id = "mediaJunakNaslov"; besedilo.appendChild(h);
    var pod = [sk.naslov, sk.izvajalec].filter(Boolean).join(" — ");
    if (pod) besedilo.appendChild(el("p", "media-junak-pod", ubezi(pod)));
    var meta = [];
    if (skupaj > 0) meta.push(t("nazSkladbaOd", { i: Math.min(mesto + 1, skupaj), n: skupaj }));
    if (rec.pozicija > 0 && !igra) meta.push(casMedija(rec.pozicija));
    if (izvor.tip === "yt") meta.push("YouTube");
    if (meta.length) besedilo.appendChild(el("p", "media-junak-meta", meta.map(ubezi).join('<span aria-hidden="true"> · </span>')));
    var dejanja = el("div", "media-junak-dejanja");
    if (igra) {
      // Ze igra: upravljanje je v spodnji vrstici (brez podvojenega gumba), tu samo stanje.
      dejanja.appendChild(el("span", "media-junak-vir", svg("glasba") + '<span>' + ubezi(t("nazPredvajaSe")) + '</span>'));
    } else {
      var gumb = el("button", "gumb glavni", svg("predvajaj") + '<span>' + ubezi(t("domovNadaljuj")) + '</span>');
      gumb.type = "button"; gumb.id = "mediaJunakPredvajaj";
      gumb.setAttribute("aria-describedby", "mediaJunakNaslov");
      gumb.addEventListener("click", nadaljujZadnjiSeznam);
      dejanja.appendChild(gumb);
    }
    besedilo.appendChild(dejanja);
    junak.appendChild(besedilo);
    if (prejFokus) { var f = junak.querySelector("button"); if (f) f.focus({ preventScroll: true }); }
  }
  function narisiMediaDomov() {
    var junak = $("mediaJunak"), prazno = $("mediaPrazno"); if (!junak) return;
    narisiOdkrivanje();                  // brez kartic, ki so ze na osebnih policah (te so lahko prisle sele zdaj)
    var nalozeno = POL.nalozeno === "domov";
    var ima = (POL.police || []).length > 0 || odkrivanjeVidno().length > 0 || !!POL.zadnjiSeznam;
    // Prazno stanje sele, ko je odgovor za Domov prisel (ne utripa ob odprtju); ena poteza: Dodaj mapo. Samodejni
    // seznami so tudi knjiznica: z njimi »Tvoja knjiznica se zacne tukaj« ni res (pregled 14. 10. 2026).
    prazno.hidden = !nalozeno || ima || (S.samodejni || []).length > 0;
    if (!ima) { $("mediaPraznoNaslov").textContent = t("mediaPraznoNaslov"); $("mediaPraznoOpis").textContent = t("mediaPraznoOpis");
                $("medijiDodajPrazno").hidden = false; $("mediaPraznoZnak").innerHTML = svg("glasba"); }
    var izbor = nalozeno && ima ? izbiraJunaka() : null;
    junak.hidden = !izbor;
    if (!izbor) { junak.innerHTML = ""; junak._podpis = ""; return; }
    if (izbor.seznam) { narisiJunakaSeznama(junak, izbor.seznam); return; }
    var d = podatkiJunaka(izbor.v);
    var podpis = JSON.stringify([d, izbor.polica, jezik]);
    if (junak._podpis === podpis) return;
    junak._podpis = podpis;
    junak.innerHTML = "";
    junak.classList.toggle("z-ozadjem", !!(d.ozadje || d.slika));
    if (d.ozadje || d.slika) {
      // Brez ozadja (backdrop) zamegljen plakat: ista slika naslova, nic tujega.
      var oz = el("div", "media-junak-ozadje" + (d.ozadje ? "" : " zamegljeno")); oz.setAttribute("aria-hidden", "true");
      var slikaOzadja = document.createElement("img"); slikaOzadja.alt = ""; slikaOzadja.src = d.ozadje || d.slika;
      slikaOzadja.onerror = function () { oz.remove(); junak.classList.remove("z-ozadjem"); };
      oz.appendChild(slikaOzadja); junak.appendChild(oz);
    }
    var plakat = el("div", "media-junak-plakat" + (izbor.v.vrsta === "glasba" || izbor.v.album ? " kvadrat" : ""));
    plakat.setAttribute("aria-hidden", "true");
    if (d.slika) {
      var img = document.createElement("img"); img.alt = ""; img.src = d.slika;
      img.onerror = function () { img.replaceWith(el("span", "kat-brez-slike", svg(ikonaPolice(izbor.v)))); };
      plakat.appendChild(img);
    } else plakat.appendChild(el("span", "kat-brez-slike", svg(ikonaPolice(izbor.v))));
    if (d.napredek) plakat.appendChild(el("span", "kat-merilo", '<i style="width:' + d.napredek + '%"></i>'));
    junak.appendChild(plakat);
    var besedilo = el("div", "media-junak-besedilo");
    besedilo.appendChild(el("span", "media-junak-oznaka", ubezi(naslovPolice(izbor.polica, ZAVIHEK_VRSTE[izbor.v.vrsta]))));
    var h = el("h2", "", ubezi(d.naslov)); h.id = "mediaJunakNaslov"; besedilo.appendChild(h);
    if (d.pod) besedilo.appendChild(el("p", "media-junak-pod", ubezi(d.pod)));
    if (d.meta.length) besedilo.appendChild(el("p", "media-junak-meta", d.meta.map(ubezi).join('<span aria-hidden="true"> · </span>')));
    var dejanja = el("div", "media-junak-dejanja");
    var gumb = el("button", "gumb glavni", svg(izbor.odkrij ? "vec" : "predvajaj") + '<span>' +
      ubezi(t(d.napredek ? "domovNadaljuj" : izbor.odkrij ? "domovVec" : "domovPredvajaj")) + '</span>');
    gumb.type = "button"; gumb.id = "mediaJunakPredvajaj";
    gumb.setAttribute("aria-describedby", "mediaJunakNaslov");
    gumb.addEventListener("click", function () {
      if (izbor.odkrij) kliknOdkrivanje(izbor.v, izbor.polica); else predvajajSPolice(izbor.v, izbor.polica);
    });
    dejanja.appendChild(gumb);
    if (d.vir) dejanja.appendChild(el("span", "media-junak-vir", svg(izbor.v.tip === "lokalno" ? "mapa" : "splet") + '<span>' + ubezi(d.vir) + '</span>'));
    besedilo.appendChild(dejanja);
    junak.appendChild(besedilo);
  }

  function odpriLokalno(pot, vrsta) {
    // Slika se odpre v pregledovalniku slik: glasba iz kataloga igra naprej.
    if (vrsta !== "slike") { prekliciNaslednjo(); opustiKatVrsto(); }
    klic("odpriLokalniMedij", [pot]).then(function (ok) { if (!ok) obvesti(t("niUspelo")); }).catch(function () { obvesti(t("niUspelo")); });
  }
  function odpriTok(url) {
    prekliciNaslednjo(); opustiKatVrsto();
    klic("odpriMedijskiTok", [url]).then(function (ok) {
      if (!ok) { obvesti(t("niUspelo")); return; }
      // Domaci predvajalnik shranjenih postaj ne javlja knjiznici: zacetek steje za »Najvec predvajano«.
      klic("mediaPredvajanTok", [url]).catch(function () {});
    }).catch(function () { obvesti(t("niUspelo")); });
  }
  function predvajajSPolice(v, polica) {
    if (v.tip === "lokalno") {
      if (v.vrsta === "slike") { odpriGalerijo([{ pot: v.pot, ime: v.naslov }], 0); return; }
      odpriLokalno(v.pot); return;
    }
    if (v.tip === "tok") { odpriTok(v.url); return; }
    var predvajaj = function () { kat.vrsta = []; narisiVrsto(); odpriKatalogVnos(null, ["mediaPolicaPredvajaj", [v.kljuc, opisVnosa(v)]]); };
    // Film ali serija (ne »Nadaljuj«): podrobnosti kot v katalogu (izbira epizode, kje gledati); ce naslova ni vec, predvajaj.
    if (polica !== "nadaljuj" && v.id && ((v.vrsta === "serija" && !v.epizoda) || v.vrsta === "film")) {
      odpriKatalogPodrobnosti(v.id, v.vrsta === "film" ? predvajaj : function () { obvesti(t("katNapakaVira")); });
      return;
    }
    predvajaj();
  }
  // ---- naslednja epizoda: ponudba z odstevanjem (kot Jellyfin in Netflix); Nazaj ali »Ne zdaj« jo preklice
  var NASL = { ponudba: null, ostane: 0, ura: 0, od: 0 };
  var NASL_SEKUND = 12;
  function pokaziNaslednjo(p) {
    NASL.ponudba = p; NASL.ostane = NASL_SEKUND; NASL.od = Date.now();
    $("naslEpNaslov").textContent = p.naslov || "";
    $("naslEpPod").textContent = p.podnaslov || "";
    var slika = $("naslEpSlika"); slika.innerHTML = "";
    if (p.slika) { var img = document.createElement("img"); img.alt = ""; img.src = p.slika; img.onerror = function () { img.replaceWith(el("span", "", svg("video"))); }; slika.appendChild(img); }
    else slika.innerHTML = svg("video");
    $("naslEpPlosca").hidden = false;
    osveziOdstevanje();
    clearInterval(NASL.ura);
    NASL.ura = setInterval(function () {
      NASL.ostane -= 1;
      if (NASL.ostane <= 0) predvajajNaslednjo(); else osveziOdstevanje();
    }, 1000);
    // V nacinu za kavc je izbran »Predvajaj zdaj«: OK zacne, Nazaj preklice.
    if (document.documentElement.classList.contains("kavc")) $("naslEpZdaj").focus();
  }
  function osveziOdstevanje() { $("naslEpCas").textContent = t("naslednjaCez", { s: NASL.ostane }); }
  function skrijNaslednjo() {
    clearInterval(NASL.ura); NASL.ponudba = null;
    var b = $("naslEpPlosca"); if (b) b.hidden = true;
  }
  function predvajajNaslednjo() {
    var p = NASL.ponudba; skrijNaslednjo(); if (!p) return;
    kat.vrsta = []; narisiVrsto();
    odpriKatalogVnos(null, ["mediaNaslednjaPredvajaj", [p.zeton], true]);
  }
  function prekliciNaslednjo() {
    var p = NASL.ponudba; if (!p) return;
    skrijNaslednjo();
    klic("mediaNaslednjaPreklici", [p.zeton]).catch(function () {});
  }
  function poveziPolice() {
    var ob = function (id, fn) { var e = $(id); if (e) e.addEventListener("click", fn); };
    ob("naslEpZdaj", predvajajNaslednjo);
    ob("naslEpNe", prekliciNaslednjo);
    var m = $("mediaKarticaMeni");
    if (m) m.addEventListener("keydown", function (e) {
      var postavke = Array.prototype.slice.call(m.querySelectorAll("[role=menuitem]")), i = postavke.indexOf(document.activeElement);
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        postavke[(i + (e.key === "ArrowDown" ? 1 : -1) + postavke.length) % postavke.length].focus();
      } else if (e.key === "Home" || e.key === "End") {
        e.preventDefault(); postavke[e.key === "Home" ? 0 : postavke.length - 1].focus();
      } else if (e.key === "Tab") zapriMeniKartice(false);
    });
    document.addEventListener("click", function (e) { if (!e.target.closest("#mediaKarticaMeni")) zapriMeniKartice(false); });
    // Tipka Meni in Shift+F10 na izbrani kartici odpreta njen meni (ne sistemskega).
    document.addEventListener("keydown", function (e) {
      var k = document.activeElement;
      if ((e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) && k && k._opis) { e.preventDefault(); odpriMeniKartice(k); }
    });
    document.addEventListener("scroll", function () { zapriMeniKartice(false); }, true);
    // Escape (tudi Nazaj na daljincu): najprej meni kartice, nato ponudba epizode - ne podrobnosti ali razdelek pod njima.
    window.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      if (zapriMeniKartice(true) || (NASL.ponudba && (prekliciNaslednjo(), true))) { e.preventDefault(); e.stopImmediatePropagation(); }
    }, true);
  }

  // ---- zvrsti pod kategorijami: pri filmih in serijah filmske (TMDB), pri glasbi, radiu in TV iz kataloga
  function skupinaZanrov(filter) {
    if (filter === "film" || filter === "serija") return filter;      // rezultati iskanja (»vse«) brez zvrsti
    if (filter === "glasba" || filter === "radio" || filter === "tv-v-zivo" || filter === "twitch") return filter;
    return "";
  }
  // Gumbi zvrsti so vidni samo, kjer izbira res filtrira: glasba in radio (zvrsti), TV v zivo (drzave), filmi in
  // serije samo s ponudnikom TMDB (jedro to pove v odgovoru kataloga kot »zvrsti«). Video in slike jih nimajo.
  function zanriVidni() {
    var skupina = skupinaZanrov(kat.filter);
    return skupina === "film" || skupina === "serija" ? (kat.zvrsti || !!kat.genre) : !!skupina;
  }
  function izberiZanr(b) {
    kat.genre = b.getAttribute("data-media-genre") || "";
    $("mediaZanri").querySelectorAll("[data-media-genre]").forEach(function (q) {
      q.classList.toggle("izbran", q === b); q.setAttribute("aria-pressed", q === b ? "true" : "false");
    });
    // Druga zvrst: kartice prejsnje takoj izginejo (izbira vidno spremeni seznam, ne sele cez nekaj sekund).
    kat.katalog = []; kat.strani = []; kat.nalozen = false; kat.skupaj = null; kat.skupaj_strani = 1;
    narisiKatalog(); naloziKatalog();
  }
  function narisiZanre() {
    var vrstica = $("mediaZanri"); if (!vrstica) return;
    var skupina = skupinaZanrov(kat.filter);
    if (kat.zanri === skupina + "|" + jezik) return;
    kat.zanri = skupina + "|" + jezik;
    kat.genre = "";
    vrstica.innerHTML = "";
    vrstica.setAttribute("aria-label", t("katZvrsti"));
    vrstica.hidden = !zanriVidni();
    if (!skupina) return;
    var gumb = function (id, napis, izbran) {
      var b = el("button", izbran ? "izbran" : ""); b.type = "button"; b.setAttribute("data-media-genre", id); b.textContent = napis;
      b.setAttribute("aria-pressed", izbran ? "true" : "false");
      b.onclick = function () { izberiZanr(b); };
      vrstica.appendChild(b);
    };
    gumb("", t(skupina === "radio" ? "katVsePostaje" : skupina === "tv-v-zivo" ? "katVseDrzave" : skupina === "glasba" ? "katVsaGlasba" :
               skupina === "twitch" ? "twitchVseKategorije" : "katVseVsebine"), true);
    if (skupina === "film" || skupina === "serija") {
      (skupina === "serija" ? KAT_SERIJSKI_ZANRI : KAT_FILMSKI_ZANRI).forEach(function (z) { gumb(z[0], t(z[1]), false); });
      return;
    }
    klic("mediaZvrsti", [skupina]).then(function (zvrsti) {
      if (kat.zanri !== skupina + "|" + jezik) return;
      (zvrsti || []).forEach(function (z) { gumb(z.id, z.ime, false); });
    }).catch(function () {});
  }

  // ---- začasen izklop virov in jezikov (velja do ponovnega zagona, namenoma ne shranjujemo)
  function zapomniKatViri(response) {
    ((response && response.vnosi) || []).forEach(function (x) {
      var razl = (x.razlicice && x.razlicice.length) ? x.razlicice : [x];
      razl.forEach(function (r) { if (r.vir_id && r.vir_id !== "lokalno") kat.znaniViri[r.vir_id] = r.vir || r.vir_id; });
    });
    ((response && response.viri) || []).forEach(function (v) { if (v.id) kat.znaniViri[v.id] = v.ime || v.id; });
  }
  // vStavku: ime, kot ga pise jezik vmesnika (slovensko z malo zacetnico, nemsko z veliko); sicer za seznam z veliko.
  function imeJezika(koda, vStavku) {
    try { var ime = new Intl.DisplayNames([LOKALE[jezik] || "sl-SI"], { type: "language" }).of(koda);
          return !ime ? koda : vStavku ? ime : ime.charAt(0).toLocaleUpperCase() + ime.slice(1); }
    catch (_) { return koda; }
  }
  // Izbira jezika vsebine: »Vsi jeziki«, nato jezik vmesnika in anglescina, ostali po abecedi (imena v jeziku
  // vmesnika). Kaze se pri Vse, Filmi, Serije, Video in Glasba; izbira ostane, dokler je Safeer OS odprt.
  function narisiJezikVsebine() {
    var polje = $("mediaJezikPolje"), izbira = $("mediaJezik"); if (!polje || !izbira) return;
    polje.hidden = !!kat.seznam || !jezikVelja(kat.filter);
    if (kat.jezikiZa !== jezik) {
      kat.jezikiZa = jezik;
      var prvi = [jezik, "en"].filter(function (k, i, vsi) { return KAT_JEZIKI.indexOf(k) >= 0 && vsi.indexOf(k) === i; });
      var ostali = KAT_JEZIKI.filter(function (k) { return prvi.indexOf(k) < 0; })
        .sort(function (a, b) { return imeJezika(a).localeCompare(imeJezika(b), LOKALE[jezik] || "sl-SI"); });
      izbira.innerHTML = "";
      izbira.add(new Option(t("katVsiJeziki"), ""));
      prvi.concat(ostali).forEach(function (k) { izbira.add(new Option(imeJezika(k), k)); });
      izbira.setAttribute("aria-label", t("katJezikVsebine"));
      izbira.title = t("katJezikVsebine");
    }
    izbira.value = kat.jezikVsebine || "";
    polje.classList.toggle("izbran", !!kat.jezikVsebine);
  }
  // Izbira drzave pri radiu: »Vse drzave«, nato uporabnikova, ostale po abecedi v jeziku vmesnika (s stevilom
  // postaj). Seznam drzav da Radio Browser (samo drzave z vsaj 3 delujocimi postajami); nalozi se ob prvem ogledu.
  function narisiDrzavoRadia() {
    var polje = $("mediaDrzavaPolje"), izbira = $("mediaDrzava"); if (!polje || !izbira) return;
    var vidno = !kat.seznam && kat.filter === "radio";
    polje.hidden = !vidno || !kat.radioDrzave || !kat.radioDrzave.drzave.length;
    if (!vidno) return;
    if (!kat.radioDrzave) {
      if (kat.radioDrzaveZa === "nalagam") return;
      kat.radioDrzaveZa = "nalagam";
      klic("mediaRadioDrzave", []).then(function (odg) {
        kat.radioDrzave = { uporabnik: (odg && odg.uporabnik) || "", drzave: (odg && odg.drzave) || [] };
        kat.radioDrzaveZa = ""; narisiDrzavoRadia();
      }).catch(function () { kat.radioDrzaveZa = ""; });
      return;
    }
    if (kat.radioDrzaveZa !== jezik) {
      kat.radioDrzaveZa = jezik;
      var lok = LOKALE[jezik] || "sl-SI", upor = kat.radioDrzave.uporabnik;
      var vse = kat.radioDrzave.drzave.slice().sort(function (a, b) {
        return (a.id === upor ? -1 : b.id === upor ? 1 : 0) || imeDrzave(a.id).localeCompare(imeDrzave(b.id), lok);
      });
      izbira.innerHTML = "";
      izbira.add(new Option(t("katVseDrzave"), ""));
      vse.forEach(function (d) { izbira.add(new Option(imeDrzave(d.id) + " (" + d.postaj + ")", d.id)); });
      izbira.setAttribute("aria-label", t("katDrzavaPostaj"));
      izbira.title = t("katDrzavaPostaj");
    }
    izbira.value = kat.drzavaRadia || "";
    polje.classList.toggle("izbran", !!kat.drzavaRadia);
  }
  function osveziGumbViri() {
    var gumb = $("mediaViriFilterGumb"); if (!gumb) return;
    var n = Object.keys(kat.izklopljeni).length;
    gumb.textContent = n ? t("katViriIzklopljeni", { n: n }) : t("katViriVsi");
    gumb.classList.toggle("aktiven", n > 0);
  }
  function narisiViriFilter() {
    var napolni = function (cilj, kljuci, ime, izklopljeni, prazno) {
      cilj.innerHTML = "";
      if (!kljuci.length) cilj.appendChild(el("small", "", ubezi(t(prazno))));
      kljuci.forEach(function (id) {
        var vrstica = el("label"), cb = el("input");
        cb.type = "checkbox"; cb.checked = !izklopljeni[id];
        cb.onchange = function () {
          if (cb.checked) delete izklopljeni[id]; else izklopljeni[id] = 1;
          osveziGumbViri(); naloziKatalog();
        };
        var besedilo = el("span"); besedilo.appendChild(el("b", "", ubezi(ime(id))));
        vrstica.appendChild(cb); vrstica.appendChild(besedilo); cilj.appendChild(vrstica);
      });
    };
    napolni($("mediaViriFilterSeznam"), Object.keys(kat.znaniViri).sort(function (a, b) { return String(kat.znaniViri[a]).localeCompare(String(kat.znaniViri[b])); }),
            function (id) { return kat.znaniViri[id]; }, kat.izklopljeni, "katViriNamig");
  }

  // Katalog pride najprej iz predpomnilnika (takoj); ko v ozadju prispejo sveži podatki, jih safeer_os.py pošlje kot
  // dogodek »mediaKatalogOsvezen« in pogled tiho posodobimo (drsnik ostane, kjer je).
  // Odgovor za stran: prva stran zamenja katalog, naslednje se dodajo na konec (dvojnikov ne kazemo dvakrat).
  // Tiha osvezitev zamenja samo stran z istim kljucem; izbor in polozaj na zaslonu ostaneta (sidro).
  function prevzemiKatalog(response, tiho, stran) {
    zapomniKatViri(response);
    if (!$("mediaViriFilter").hidden) narisiViriFilter();
    var vnosi = (response && response.vnosi) || [], kljuc = (response && response.kljuc) || "";
    if (tiho) {
      var mesto = kat.strani.map(function (s) { return s.kljuc; }).indexOf(kljuc);
      if (mesto < 0) return;
      kat.strani[mesto].vnosi = vnosi;
    } else if (stran > 1) kat.strani.push({ kljuc: kljuc, vnosi: vnosi });
    else kat.strani = [{ kljuc: kljuc, vnosi: vnosi }];
    var videni = {};
    kat.katalog = [];
    kat.strani.forEach(function (s) {
      s.vnosi.forEach(function (x) { var id = x.id || JSON.stringify([x.naslov, x.vrsta]); if (!videni[id]) { videni[id] = 1; kat.katalog.push(x); } });
    });
    kat.kljuc = kat.strani.length ? kat.strani[0].kljuc : "";
    if (response && response.viri) kat.viri = response.viri;
    if (!tiho) {
      kat.page = Math.max(1, stran || 1);
      kat.skupaj_strani = (response && response.skupaj_strani) || 1;
      kat.skupaj = (response && typeof response.skupaj === "number") ? response.skupaj : null;
    }
    if (response && typeof response.zvrsti === "boolean") kat.zvrsti = response.zvrsti;
    kat.nalozen = true;
    var sidro = (tiho || stran > 1) ? katSidro() : null;
    narisiKatalog();
    katPovrniSidro(sidro);
  }
  // naloziKatalog() nalozi katalog od zacetka (prva stran); naloziKatalog(true) doda naslednjo stran na konec.
  function naloziKatalog(vec) {
    var blok = $("katalog"); if (!blok || !most) return;
    blok.hidden = !kat.filter;
    if (!kat.filter) { $("r-media").classList.remove("ima-katalog"); return; }
    if (vec && (!katImaVec() || kat.nalagaVec)) return;
    if (!vec) {
      $("katNaslov").textContent = kat.filter === "vse" ? t("katRezultati") : katOznaka(kat.filter);
      narisiZanre();
      naloziSeznamePredvajanja();
      naloziKnjiznico();
    }
    var zahteva = vec ? kat.zahteva : ++kat.zahteva, stran = vec ? kat.page + 1 : 1;
    kat.nalagaVec = !!vec; kat.napakaVec = false;
    if (vec) narisiNalaganje();
    else if (!kat.katalog.length) $("mediaPovzetek").textContent = t("katNalagam");
    klic("mediaKatalog", [kat.query, kat.filter, kat.genre, stran, kat.razvrsti, Object.keys(kat.izklopljeni), false,
                          [], izbranJezik(), izbranaDrzavaRadia()]).then(function (response) {
      if (zahteva !== kat.zahteva) return;
      kat.nalagaVec = false;
      prevzemiKatalog(response, false, stran);
    }, function () {
      if (zahteva !== kat.zahteva) return;
      kat.nalagaVec = false;
      if (vec) { kat.napakaVec = true; narisiNalaganje(); return; }
      kat.katalog = []; kat.strani = []; kat.nalozen = true; narisiKatalog();
    });
  }
  // Kakovost (HD/4K le, ce jo vir pove), jezik in podnapisi (ce so znani) ter vir za vrstico pod naslovom kartice.
  function katKakovost(x) {
    var visina = Number(x.locljivost || 0), k = String(x.kakovost || "");
    if (visina >= 2160 || /\b(4k|2160p?|uhd)\b/i.test(k)) return "4K";
    if (visina >= 720 || /\b(1080p?|720p?|hd|fhd)\b/i.test(k)) return "HD";
    return "";
  }
  function katVrsticaVira(x) {
    var deli = [], namig = [];
    var kakovost = katKakovost(x);
    if (kakovost) deli.push(kakovost);
    var jez = String(x.jezik || "").toLowerCase();
    if (/^[a-z]{2,3}$/.test(jez)) {
      deli.push(jez.toUpperCase());
      try { namig.push(new Intl.DisplayNames([LOKALE[jezik] || "en-GB"], { type: "language" }).of(jez)); } catch (_) { namig.push(jez); }
    }
    if (Array.isArray(x.podnapisi) && x.podnapisi.length) { deli.push(t("katPodnapisi")); namig.push(t("katPodnapisi")); }
    var viri = (Array.isArray(x.viri) && x.viri.length ? x.viri : [x.vir]).filter(Boolean);
    if (viri.length) { deli.push(viri[0] + (viri.length > 1 ? " +" + (viri.length - 1) : "")); namig.push(viri.join(", ")); }
    return deli.length ? { besedilo: deli.join(" · "), namig: namig.join(" · ") } : null;
  }
  // Krajevna knjižnica je pravkar narisana (izbrana kategorija ali iskanje): katalog sledi isti izbiri.
  function uskladiKatalog() {
    var filter = KAT_VRSTE[S.mediaFilter] == null ? "vse" : KAT_VRSTE[S.mediaFilter];
    var query = String(S.mediaIskanje || "").trim();
    if (kat.nalozen && filter === kat.filter && query === kat.query && kat.jezik === jezik) return;
    var samoIskanje = kat.nalozen && filter === kat.filter && kat.jezik === jezik;
    // Isti zavihek in iskanje (npr. drugi klic, preden katalog odgovori): seznam, odprt s police Domov, ostane.
    if (filter !== kat.filter || query !== kat.query) kat.seznam = null;
    kat.filter = filter; kat.query = query; kat.jezik = jezik; kat.page = 1;
    clearTimeout(kat.timer);
    // Med tipkanjem se ne nalaga naslednja stran starega iskanja (nalaganje, ki ze tece, se zavrze).
    kat.skupaj_strani = 1; kat.zahteva++; kat.nalagaVec = false;
    // Druga kategorija: kartice prejšnje takoj izginejo (sicer bi do odgovora kazali filme pod naslovom »Radio«).
    // Ali zvrsti filtrirajo, pove sele odgovor za novo vrsto (do takrat jih pri filmih in serijah ne kazemo).
    if (!samoIskanje) { kat.katalog = []; kat.strani = []; kat.nalozen = false; kat.skupaj = null; kat.skupaj_strani = 1; kat.zvrsti = false; narisiKatalog(); }
    // Med tipkanjem počakamo, da uporabnik neha (vsaka črka bi sicer vprašala vse vire).
    if (samoIskanje) kat.timer = setTimeout(naloziKatalog, 350); else naloziKatalog();
  }

  // ---- podrobnosti filma ali serije
  function zapriKatalogPodrobnosti() { var panel = $("mediaPodrobnosti"); if (panel) panel.hidden = true; }
  function imeDrzave(code, fallback) {
    try { return new Intl.DisplayNames([LOKALE[jezik] || "en-GB"], { type: "region" }).of(code) || fallback || code; }
    catch (_) { return fallback || code; }
  }
  function narisiKjeGledati(item) {
    var target = $("mediaWatchProviders"); if (!target) return;
    target.innerHTML = "";
    var data = item.kje_gledati || {};
    var countryName = imeDrzave(data.drzava, data.ime_drzave);
    var groups = data.skupine || [];
    // Brez države in brez ponudnikov (npr. vsebina iz dodatka brez podatkov TMDB) okvirja ne kažemo.
    target.hidden = !groups.length && !String(countryName || "").replace(/[\s,()]/g, "");
    if (target.hidden) return;
    target.appendChild(el("h3", "", ubezi(t("mediaWatchTitle", { country: countryName }))));
    if (!groups.length) target.appendChild(el("p", "", ubezi(t("mediaWatchNone", { country: countryName }))));
    var groupLabels = { "naročnina": "mediaWatchSubscription", "brezplačno": "mediaWatchFree", "izposoja": "mediaWatchRent", "nakup": "mediaWatchBuy" };
    groups.forEach(function (group) {
      var section = el("div", "kat-kje-gledati-skupina");
      section.appendChild(el("h4", "", ubezi(t(groupLabels[group.id] || group.id))));
      var providers = el("div", "kat-ponudniki");
      (group.ponudniki || []).forEach(function (provider) {
        var button = el("button", "kat-ponudnik", ""); button.type = "button";
        if (provider.logo) { var logo = document.createElement("img"); logo.src = provider.logo; logo.alt = ""; logo.loading = "lazy"; button.appendChild(logo); }
        button.appendChild(el("span", "", ubezi(provider.ime || "")));
        button.onclick = function () { if (provider.povezava) { zapriKatalogPodrobnosti(); katSplet(provider.povezava); } };
        providers.appendChild(button);
      });
      section.appendChild(providers); target.appendChild(section);
    });
    target.appendChild(el("p", "kat-kje-gledati-vira", ubezi(t("mediaWatchSource"))));
  }
  function naloziKatalogSezono(item, season, button) {
    $("mediaSezone").querySelectorAll("button").forEach(function (b) { b.classList.toggle("izbran", b === button); });
    var cilj = $("mediaEpizode"); cilj.innerHTML = "";
    cilj.appendChild(el("div", "prazno", ubezi(t("katNalagamEpizode"))));
    klic("mediaSezona", [item.tmdb_id, season]).then(function (response) {
      cilj.innerHTML = "";
      var episodes = (response && response.epizode) || [];
      $("mediaEpizodeNaslov").textContent = t("katEpizode") + " · " + (button ? button.textContent : t("katSezona", { n: season }));
      episodes.forEach(function (ep) {
        var row = el("article", "kat-epizoda");
        if (ep.slika) { var img = document.createElement("img"); img.src = ep.slika; img.alt = ""; img.loading = "lazy"; row.appendChild(img); }
        else row.classList.add("brez-slike");
        var info = el("div", "kat-epizoda-info");
        info.appendChild(el("b", "", "E" + String(ep.stevilka).padStart(2, "0") + "  " + ubezi(ep.naslov || t("katEpizoda"))));
        info.appendChild(el("small", "", ubezi([ep.datum, ep.trajanje ? ep.trajanje + " min" : "", ep.ocena ? "★ " + ep.ocena : ""].filter(Boolean).join(" · "))));
        if (ep.opis) info.appendChild(el("p", "", ubezi(ep.opis)));
        row.appendChild(info);
        if (item.tmdb_id) row.appendChild(gumbOgledanoEpizode(item, season, ep, row));
        var play = el("button", "gumb glavni", ubezi(t("katPredvajaj"))); play.type = "button";
        play.onclick = function () {
          klic("mediaEpizoda", [item.tmdb_id, season, ep.stevilka, item.naslov + " · " + ep.naslov]).then(function (entry) {
            // Epizode noben vir ne predvaja: tiho (lastnik 18. 10. 2026; sled v sled.log, os_katalog._epizoda).
            if (entry && entry.id) { zapriKatalogPodrobnosti(); kat.vrsta = []; narisiVrsto(); odpriKatalogVnos(entry.id); }
          }, function () {});
        };
        row.appendChild(play);
        // Viri epizode (razlicice): seznam se odpre pod vrstico, ko ga uporabnik zahteva - dodatkov ne sprasujemo za
        // vsako epizodo vnaprej.
        var viri = el("button", "gumb-ikona kat-epizoda-viri", svg("drsniki")); viri.type = "button";
        viri.title = t("razlViri"); viri.setAttribute("aria-label", t("razlViri") + " – E" + String(ep.stevilka).padStart(2, "0"));
        viri.setAttribute("aria-expanded", "false");
        var seznamEp = el("section", "kat-razlicice kat-razlicice-epizoda"); seznamEp.hidden = true;
        viri.onclick = function () {
          if (viri.getAttribute("aria-expanded") === "true") { viri.setAttribute("aria-expanded", "false"); seznamEp.hidden = true; return; }
          viri.setAttribute("aria-expanded", "true");
          var vnosEp = klic("mediaEpizoda", [item.tmdb_id, season, ep.stevilka, item.naslov + " · " + ep.naslov])
            .then(function (entry) { return entry && entry.id ? entry.id : ""; });
          narisiRazlicice(seznamEp, vnosEp, item, season, ep.stevilka, function (vnosId) {
            zapriKatalogPodrobnosti(); kat.vrsta = []; narisiVrsto(); odpriKatalogVnos(vnosId);
          }, true);
        };
        row.appendChild(viri); cilj.appendChild(row); cilj.appendChild(seznamEp);
      });
      if (!episodes.length) cilj.appendChild(el("div", "prazno", ubezi(t("katBrezEpizod"))));
    }, function () { cilj.innerHTML = ""; cilj.appendChild(el("div", "prazno", ubezi(t("katBrezEpizod")))); });
  }
  // ---- razlicice naslova (lastnik, 15. 10. 2026): v podrobnostih filma ali epizode je en seznam vseh moznosti
  // predvajanja - toki iz dodatkov in streznikov, ki jih je dodal uporabnik (ime vira, kakovost, odziv), in lastni
  // vgrajeni viri, ce jih ima. Prva je samodejna izbira (privzeta); rocna izbira se zapomni za ta naslov.
  // ponudniki: dodatne moznosti predvajanja v istem seznamu (npr. lastni vgrajeni viri): function (item, sezona, epizoda,
  // naslov) -> Promise([{ ime, ms, privzeta, oznaka, odpri: function () {} }]). Tako ni drugih, podvojenih gumbov.
  var RAZL = { ura: 0, ponudniki: [] };
  function vrsticaRazlicice(r, oznake, ob) {
    var b = el("button", "kat-razlicica" + (r.izbrana ? " izbrana" : "")); b.type = "button"; b.setAttribute("role", "listitem");
    var ime = el("span", "kat-razlicica-ime", ubezi(r.vir || r.ime || t("razlVir")));
    // Opis dodatka pogosto ze vsebuje kakovost (»1080p · WEB«): ne ponavljamo je.
    var podatki = r.opis && r.kakovost && r.opis.indexOf(r.kakovost) >= 0 ? r.opis
      : [r.kakovost, r.opis && r.opis !== r.kakovost ? r.opis : ""].filter(Boolean).join(" · ");
    b.appendChild(ime);
    if (podatki) b.appendChild(el("span", "kat-razlicica-opis", ubezi(podatki)));
    var desno = el("span", "kat-razlicica-oznake");
    oznake.forEach(function (o) { desno.appendChild(el("span", "kat-razlicica-znacka " + o[0], ubezi(o[1]))); });
    if (r.ping != null) desno.appendChild(el("span", "kat-razlicica-ping", ubezi(t("razlMs", { ms: r.ping }))));
    b.appendChild(desno);
    b.setAttribute("aria-pressed", r.izbrana ? "true" : "false");
    b.title = [r.vir || r.ime || "", podatki, r.ping != null ? t("razlMs", { ms: r.ping }) : ""].filter(Boolean).join(" · ");
    b.onclick = ob;
    return b;
  }
  // cilj: prazen <section>; vnos: Promise z id-jem vnosa za predvajanje; predvajaj(id): obstojeca pot predvajanja.
  function narisiRazlicice(cilj, vnos, item, sezona, epizoda, predvajaj, vedno) {
    // Ob novi meritvi virov (dogodek) se zadnji odprti seznam narise znova.
    RAZL.osvezi = function () { if (document.contains(cilj)) narisiRazlicice(cilj, vnos, item, sezona, epizoda, predvajaj, vedno); };
    var ura = ++RAZL.ura;
    cilj.innerHTML = ""; cilj.hidden = !vedno;
    if (vedno) cilj.appendChild(el("p", "drobno", ubezi(t("razlIscem"))));
    var naslov = (item.naslov || "") + (sezona ? " · S" + String(sezona).padStart(2, "0") + "E" + String(epizoda).padStart(2, "0") : "");
    var vgrajeni = Promise.all(RAZL.ponudniki.map(function (ponudnik) {
      try { return Promise.resolve(ponudnik(item, sezona || 0, epizoda || 0, naslov)).then(function (m) { return Array.isArray(m) ? m : []; },
                                                                                          function () { return []; }); }
      catch (e) { return Promise.resolve([]); }
    })).then(function (skupine) { return [].concat.apply([], skupine); });
    var toki = Promise.resolve(vnos).then(function (id) {
      if (!id) return { id: "", razlicice: [] };
      return klic("mediaRazlicice", [id]).then(function (r) { return r || { id: id, razlicice: [] }; },
                                               function () { return { id: id, razlicice: [] }; });
    }, function () { return { id: "", razlicice: [] }; });
    Promise.all([toki, vgrajeni]).then(function (izid) {
      if (ura !== RAZL.ura && !vedno) return;
      var r = izid[0], moznosti = izid[1], razl = r.razlicice || [];
      cilj.innerHTML = "";
      // En sam tok brez drugih moznosti: izbire ni, seznam ostane skrit (gumb Predvajaj zadostuje). Vgrajen vir je
      // viden vedno - drugje ga ni mogoce odpreti.
      if (!moznosti.length && razl.length < 2) {
        if (vedno) cilj.appendChild(el("p", "drobno", ubezi(razl.length || moznosti.length ? t("razlEna") : t("razlNi"))));
        cilj.hidden = !vedno; return;
      }
      // »Najhitrejsi« je en sam v celem seznamu: najnizji izmerjeni odziv med tistimi, ki jih je vir oznacil (tok na
      // vec streznikih, vec izmerjenih vgrajenih virov), in samo ce noben drug ni hitrejsi.
      var vsi = razl.map(function (x) { return x.ping; }).concat(moznosti.map(function (m) { return m.ms; }))
        .filter(function (p) { return p != null; });
      var najmanj = vsi.length > 1 ? Math.min.apply(null, vsi) : null, oznacen = false;
      var najhitrejsi = function (x, p) {
        if (oznacen || !x.najhitrejsi || p == null || najmanj == null || Math.round(p) > Math.round(najmanj)) return false;
        oznacen = true; return true;
      };
      var glava = el("h4", "", ubezi(t("razlNaslov"))); cilj.appendChild(glava);
      var seznam = el("div", "kat-razlicice-seznam"); seznam.setAttribute("role", "list");
      razl.forEach(function (x) {
        var oznake = [];
        if (x.izbrana) oznake.push(["izbrana", t("razlIzbrana")]);
        else if (x.privzeta && !r.izbira) oznake.push(["privzeta", t("razlPrivzeta")]);
        if (najhitrejsi(x, x.ping)) oznake.push(["najhitrejsi", t("razlNajhitrejsi")]);
        if (x.lastni) oznake.push(["lastni", t("razlLastni")]);
        seznam.appendChild(vrsticaRazlicice(x, oznake, function () {
          klic("mediaIzberiRazlicico", [r.id, x.privzeta && !x.izbrana ? "" : x.podpis]).then(function () { predvajaj(r.id); },
                                                                                          function () { predvajaj(r.id); });
        }));
      });
      moznosti.forEach(function (m) {
        var oznake = [["vgrajeno", m.oznaka || t("razlVgrajeno")]];
        if (m.izbrana) oznake.unshift(["izbrana", t("razlIzbrana")]);
        else if (m.privzeta && !razl.length) oznake.unshift(["privzeta", t("razlPrivzeta")]);
        if (najhitrejsi(m, m.ms)) oznake.push(["najhitrejsi", t("razlNajhitrejsi")]);
        seznam.appendChild(vrsticaRazlicice({ vir: m.ime, opis: m.opis || "", ping: m.ms != null ? Math.round(m.ms) : null,
                                              izbrana: !!m.izbrana },
                                            oznake, function () { if (typeof m.odpri === "function") m.odpri(); }));
      });
      cilj.appendChild(seznam); cilj.hidden = false;
    });
  }
  // rezerva: kaj narediti, ce naslova ni vec v katalogu (polica Priljubljene po ponovnem zagonu): predvajaj ga.
  function odpriKatalogPodrobnosti(id, rezerva) {
    klic("mediaPodrobnosti", [id, jezik]).then(function (item) {
      if (!item || !item.naslov) { if (rezerva) rezerva(); return; }
      var panel = $("mediaPodrobnosti"); panel.hidden = false;
      var hero = $("mediaPodrobnostiJunak"); hero.innerHTML = "";
      if (item.slika) { var poster = document.createElement("img"); poster.src = item.slika; poster.alt = ""; hero.appendChild(poster); }
      var info = el("div"); info.appendChild(el("h2", "", ubezi(item.naslov || "")));
      info.appendChild(el("p", "kat-detail-meta", ubezi([item.leto, item.ocena ? "★ " + item.ocena : "", t(item.vrsta === "serija" ? "katSerija" : "katFilm")].filter(Boolean).join(" · "))));
      if (item.opis) info.appendChild(el("p", "", ubezi(item.opis)));
      info.appendChild(dejanjaPodrobnosti(item));
      hero.appendChild(info);
      narisiKjeGledati(item);
      RAZL.podrobnosti = item;
      var seasons = $("mediaSezone"); seasons.innerHTML = "";
      var episodes = $("mediaEpizode"); episodes.innerHTML = "";
      var jeSerija = item.vrsta === "serija";
      $("mediaSezoneNaslov").hidden = !jeSerija; seasons.hidden = !jeSerija;
      $("mediaSezoneNaslov").textContent = t("katSezone");
      if (!jeSerija) {
        $("mediaEpizodeNaslov").textContent = t("katPredvajanje");
        var playBtn = el("button", "gumb glavni kat-predvajaj-film", ubezi(t("katPredvajaj"))); playBtn.type = "button";
        playBtn.onclick = function () {
          var pojdi2 = function (vnosId) { zapriKatalogPodrobnosti(); kat.vrsta = []; narisiVrsto(); odpriKatalogVnos(vnosId); };
          if (item.tmdb_id) klic("mediaFilm", [item.tmdb_id, item.naslov]).then(function (entry) { pojdi2(entry && entry.id ? entry.id : item.id); }, function () { pojdi2(item.id); });
          else pojdi2(item.id);
        };
        episodes.appendChild(playBtn);
        // Vse moznosti predvajanja na enem mestu: razlicice iz dodatkov in streznikov (ter lastni vgrajeni viri).
        var seznamFilma = el("section", "kat-razlicice"); seznamFilma.hidden = true;
        episodes.appendChild(seznamFilma);
        var vnosFilma = item.tmdb_id ? klic("mediaFilm", [item.tmdb_id, item.naslov]).then(function (e) { return e && e.id ? e.id : item.id; },
                                                                                              function () { return item.id; })
                                     : Promise.resolve(item.id);
        narisiRazlicice(seznamFilma, vnosFilma, item, 0, 0, function (vnosId) {
          zapriKatalogPodrobnosti(); kat.vrsta = []; narisiVrsto(); odpriKatalogVnos(vnosId);
        });
      } else {
        $("mediaEpizodeNaslov").textContent = t("katEpizode");
        (item.sezone || []).forEach(function (season, index) {
          var b = el("button", index === 0 ? "izbran" : "", ubezi(season.ime || t("katSezona", { n: season.stevilka }))); b.type = "button";
          b.onclick = function () { naloziKatalogSezono(item, season.stevilka, b); }; seasons.appendChild(b);
          if (index === 0) setTimeout(function () { naloziKatalogSezono(item, season.stevilka, b); }, 0);
        });
        if (!(item.sezone || []).length) episodes.appendChild(el("div", "prazno", ubezi(t("katSezoneNi"))));
      }
      panel.scrollTop = 0;
    }, function () { if (rezerva) rezerva(); else obvesti(t("katNapakaVira")); });
  }

  // ---- dodatki in viri (dodatek Stremio, osebni strežnik, spletni vir)
  function narisiKatViri() {
    var cilj = $("katViri"); if (!cilj) return; cilj.innerHTML = "";
    // Zasebni dodatki so skriti, dokler »Zasebno« ni vklopljeno: le diskretna vrstica s stevilom.
    var skriti = !S.mediaZasebno.vklopljeno && S.mediaZasebno.skriti ? el("p", "drobno kat-zasebni-skriti",
      ubezi(t("katZasebniSkriti", { n: S.mediaZasebno.skriti }))) : null;
    if (!kat.viri.length) { cilj.appendChild(skriti || el("p", "drobno", ubezi(t("katBrezVirov")))); return; }
    kat.viri.forEach(function (source) {
      var row = el("div", "kat-vir"); row.innerHTML = svg("splet");
      var info = el("div"); info.appendChild(el("b", "", ubezi(source.ime || source.url)));
      var status = source.napaka ? source.napaka : (source.vrsta === "streznik"
        ? t("katOsebniStreznik") + " · " + (source.ponudnik || "")
        : t("katVirElementov", { n: source.stevilo || 0 }));
      info.appendChild(el("small", source.napaka ? "kat-vir-napaka" : "", ubezi(status + " · " + source.url)));
      row.appendChild(info);
      var refresh = el("button", "gumb-ikona", svg("ponovno")); refresh.type = "button"; refresh.title = t("katOsvezi");
      refresh.onclick = function () {
        $("katVirSporocilo").textContent = t("katOsvezi") + " …";
        klic("mediaOsveziVir", [source.id]).then(function () { $("katVirSporocilo").textContent = t("katOsvezeno"); naloziKatViri(); naloziKatalog(); },
                                                function () { $("katVirSporocilo").textContent = t("katNapakaVira"); });
      };
      row.appendChild(refresh);
      // Vticniki strežnika Jellyfin (samo, ce most to zna - core/os_katalog.py doda oznako »vticniki«).
      if (source.ponudnik === "jellyfin" && source.vticniki) {
        var plugins = el("button", "gumb kat-vir-vticniki", svg("program") + "<span>" + ubezi(t("jfVticniki")) + "</span>");
        plugins.type = "button"; plugins.title = t("jfVticnikiNamig");
        plugins.onclick = function () { odpriJellyfin(source); };
        row.appendChild(plugins);
      }
      var remove = el("button", "gumb-ikona", svg("x")); remove.type = "button"; remove.title = t("odstrani");
      // Vir, ki je enak na vseh napravah v Safeer Linku, se izbriše povsod: prvi klik vpraša (brez sistemskega okna).
      var povsod = (source.ponudnik === "stremio" && source.zaseben === false) ||
        (source.vrsta !== "streznik" && source.tip !== "predvajalni_vir" && (!!source.link_tip || (source.stevilo || 0) > 0)), potrjeno = false;
      remove.onclick = function () {
        if (povsod && !potrjeno) { potrjeno = true; remove.classList.add("potrdi"); remove.textContent = t("virOdstraniPovsod"); return; }
        klic("mediaOdstraniVir", [source.id]).then(function () { naloziKatViri(); naloziKatalog(); });
      };
      row.onmouseleave = function () { if (potrjeno) { potrjeno = false; remove.classList.remove("potrdi"); remove.innerHTML = svg("x"); } };
      row.appendChild(remove);
      cilj.appendChild(row);
    });
    if (skriti) cilj.appendChild(skriti);
  }
  function naloziKatViri() {
    klic("mediaZasebno").then(function (z) { nastaviZasebno(z); narisiKatViri(); }, function () {});
    return klic("mediaViri").then(function (viri) { kat.viri = Array.isArray(viri) ? viri : []; narisiKatViri(); }, function () {});
  }
  function preklopiZasebno() {
    var g = $("katZasebno"); if (!g || g.getAttribute("aria-busy") === "true") return;
    g.setAttribute("aria-busy", "true");
    klic("mediaZasebno", [!S.mediaZasebno.vklopljeno]).then(function (z) {
      g.removeAttribute("aria-busy");
      nastaviZasebno(z); naloziKatViri(); naloziKatalog();
    }, function () { g.removeAttribute("aria-busy"); });
  }

  // ---- lastni vgrajeni viri (core/os_vgrajeni_viri.py, assets/os/vgrajeno.js; lastnik, 15. 10. 2026): uporabnik vgradi
  // katerokoli stran ali svojo komponento React; Safeer ne prinasa nobenega vira (seznam je prazen). Viri ne dodajo
  // kartic v katalog - so le dodatni gumbi »Predvajaj prek« na eni (zdruzeni) kartici; nedosegljivih ni (meritve v
  // ozadju, core/meritve_virov.py), najhitrejsi je privzet. Navadna stran (brez znack) je ploscica na Domov.
  var VGR = { viri: [], obvestilo: false, ploscice: [], ureja: null, podrobnosti: null, ura: 0 };
  function vgrStarost(cas) {
    var s = Math.max(0, Date.now() / 1000 - Number(cas || 0));
    var f = new Intl.RelativeTimeFormat(LOKALE[jezik] || "en-GB", { numeric: "auto", style: "short" });
    if (s < 60) return f.format(0, "second");
    if (s < 3600) return f.format(-Math.round(s / 60), "minute");
    if (s < 86400) return f.format(-Math.round(s / 3600), "hour");
    return f.format(-Math.round(s / 86400), "day");
  }
  function vgrMeritev(m) {
    if (!m) return t("vgrMerim");
    return (m.ok ? t("vgrMs", { ms: Math.round(m.ms) }) : t("vgrNiDosegljiv")) + " · " + vgrStarost(m.cas);
  }
  function naloziVgrajene() {
    if (!most) return Promise.resolve();
    return klic("mediaVgrajeniViri").then(function (r) {
      VGR.viri = (r && r.viri) || []; VGR.obvestilo = !!(r && r.obvestilo); VGR.ploscice = (r && r.ploscice) || [];
      narisiVgrajeneNastavitve(); narisiVgrajenePloscice();
      // Meritve virov so se spremenile: odprt seznam moznosti v podrobnostih se narise znova (nedosegljivih ni).
      if (RAZL.osvezi && !$("mediaPodrobnosti").hidden) RAZL.osvezi();
    }, function () {});
  }
  function vgrKnjiznica(ime) { return klic("mediaVgrajenaKnjiznica", [ime]); }
  function vgrProps(podatki, url, naslov) {
    var p = podatki || {};
    return { url: url || "", title: naslov || p.title || "", imdb: p.imdb || "", tmdb: p.tmdb || "", tvdb: p.tvdb || "",
             type: p.type || "", season: p.season || "", episode: p.episode || "", year: p.year || "" };
  }
  // Odpre moznost; nedosegljiv vir (preverba tik pred odprtjem) tiho zamenja naslednji najhitrejsi.
  function vgrOdpri(moznosti, i, naslov) {
    var m = moznosti[i]; if (!m) { obvesti(t("vgrNiDosegljivih")); return; }
    if (m.vrsta === "komponenta") {
      var vir = VGR.viri.filter(function (v) { return v.id === m.id; })[0];
      if (!vir) return;
      SafeerVgrajeno.komponenta({ koda: vir.koda, props: vgrProps(m.podatki, "", naslov), title: m.ime, knjiznica: vgrKnjiznica,
                                  onError: function (s) { obvesti(t("vgrNapakaKomponente", { napaka: s })); } });
      return;
    }
    klic("mediaVgrajenoPreveri", [m.url]).then(function (ok) {
      if (!ok) { vgrOdpri(moznosti, i + 1, naslov); return; }
      SafeerVgrajeno.odpri({ url: m.url, title: m.ime + (naslov ? " · " + naslov : ""), allowFullscreen: true, allowPopups: !!m.pojavna });
    }, function () { vgrOdpri(moznosti, i + 1, naslov); });
  }
  function vgrImaPredloge() {
    return VGR.viri.some(function (v) { return v.vklopljen && !v.navadna; });
  }
  // Lastni vgrajeni viri so vrstice v istem seznamu kot razlicice dodatkov in streznikov (narisiRazlicice) - edino
  // mesto za moznosti predvajanja v podrobnostih (lastnik, 15. 10. 2026: brez podvojenih gumbov). Nedosegljivih ni
  // (core/os_vgrajeni_viri.moznosti_za); »Najhitrejsi« samo, ce je izmerjenih vec virov.
  function vgrPonudnik(item, sezona, epizoda, naslov) {
    if (!vgrImaPredloge()) return [];
    return klic("mediaVgrajeneMoznosti", [item, sezona || 0, epizoda || 0]).then(function (moznosti) {
      if (!Array.isArray(moznosti)) return [];
      var izmerjeni = moznosti.filter(function (m) { return m.ms != null; }).length;
      return moznosti.map(function (m, i) {
        return { ime: m.ime, ms: m.ms, privzeta: !!m.privzeta, izbrana: !!m.izbrana,
                 najhitrejsi: !!m.privzeta && !m.izbrana && m.ms != null && izmerjeni > 1,
                 opis: m.tudi && m.tudi.length ? t("vgrTudi", { imena: m.tudi.join(", ") }) : "",
                 odpri: function () {
                   // Rocna izbira (ne privzeta) se zapomni za ta naslov; nedosegljiv vir zamenja naslednji iste vrste.
                   if (!m.privzeta) klic("mediaVgrajenaIzbira", [item, sezona || 0, epizoda || 0, m.id]);
                   vgrOdpri([m].concat(moznosti.filter(function (x, j) { return j > i && x.vrsta === m.vrsta; })), 0, naslov);
                 } };
      });
    }, function () { return []; });
  }
  function narisiVgrajenePloscice() {
    var c = $("mediaVgrajenePloscice"); if (!c) return;
    c.innerHTML = "";
    c.hidden = !(VGR.ploscice.length && S.mediaFilter === "domov");
    if (c.hidden) return;
    var glava = el("h3", "media-polica-naslov", ubezi(t("vgrPolica"))); glava.id = "mediaVgrajenePlosciceNaslov";
    c.appendChild(glava);
    var vrsta = el("div", "media-polica-vrsta"); vrsta.setAttribute("role", "list");
    VGR.ploscice.forEach(function (p) {
      var k = el("button", "kat-kartica media-polica-kartica vgr-ploscica"); k.type = "button"; k.setAttribute("role", "listitem");
      k.appendChild(el("span", "kat-plakat", '<span class="kat-brez-slike">' + svg("splet") + "</span>"));
      var podatki = el("span", "kat-podatki"); podatki.appendChild(el("b", "", ubezi(p.ime)));
      var gost = ""; try { gost = new URL(p.url).hostname; } catch (e) { /* */ }
      podatki.appendChild(el("span", "kat-meta", "<span>" + ubezi(gost) + "</span>"));
      k.appendChild(podatki); k.title = p.ime + " · " + gost;
      k.addEventListener("click", function () { vgrOdpri([{ id: p.id, ime: p.ime, vrsta: "url", url: p.url, pojavna: p.pojavna }], 0, ""); });
      vrsta.appendChild(k);
    });
    c.appendChild(vrsta);
  }
  // ---- nastavitve: seznam (z meritvijo), dodaj/uredi/odstrani/vklopi, »Preizkusi«
  function narisiVgrajeneNastavitve() {
    var cilj = $("vgrSeznam"); if (!cilj) return;
    cilj.innerHTML = "";
    if (!VGR.viri.length) { cilj.appendChild(el("p", "drobno", ubezi(t("vgrPrazno")))); return; }
    VGR.viri.forEach(function (v) {
      var row = el("div", "kat-vir vgr-vir" + (v.vklopljen ? "" : " izklopljen")); row.setAttribute("role", "listitem");
      row.innerHTML = svg(v.vrsta === "komponenta" ? "program" : "splet");
      var info = el("div"); info.appendChild(el("b", "", ubezi(v.ime)));
      var opis = v.vrsta === "komponenta" ? t("vgrVrstaKomponenta") : v.url;
      var stanje = v.vrsta === "url" ? " · " + vgrMeritev(v.meritev) : "";
      info.appendChild(el("small", v.meritev && !v.meritev.ok ? "kat-vir-napaka" : "", ubezi(opis + stanje)));
      row.appendChild(info);
      var vklop = el("button", "gumb-ikona vgr-vklop", svg(v.vklopljen ? "kljukica" : "x")); vklop.type = "button";
      vklop.setAttribute("role", "switch"); vklop.setAttribute("aria-checked", v.vklopljen ? "true" : "false");
      vklop.title = t(v.vklopljen ? "vgrIzklopi" : "vgrVklopi"); vklop.setAttribute("aria-label", vklop.title + " " + v.ime);
      vklop.onclick = function () { vgrShrani({ id: v.id, ime: v.ime, vrsta: v.vrsta, url: v.url, koda: v.koda, pojavna: v.pojavna, vklopljen: !v.vklopljen }); };
      var uredi = el("button", "gumb-ikona", svg("drsniki")); uredi.type = "button"; uredi.title = t("vgrUredi");
      uredi.setAttribute("aria-label", t("vgrUredi") + " " + v.ime);
      uredi.onclick = function () { vgrUredi(v); };
      var odstrani = el("button", "gumb-ikona", svg("x")); odstrani.type = "button"; odstrani.title = t("odstrani");
      odstrani.setAttribute("aria-label", t("odstrani") + " " + v.ime);
      var potrjeno = false;
      odstrani.onclick = function () {
        if (!potrjeno) { potrjeno = true; odstrani.classList.add("potrdi"); odstrani.textContent = t("odstrani"); return; }
        klic("mediaVgrajenVirOdstrani", [v.id]).then(naloziVgrajene);
      };
      odstrani.addEventListener("blur", function () { if (potrjeno) { potrjeno = false; odstrani.classList.remove("potrdi"); odstrani.innerHTML = svg("x"); } });
      row.appendChild(vklop); row.appendChild(uredi); row.appendChild(odstrani);
      cilj.appendChild(row);
    });
  }
  function vgrObrazecVrsta() {
    var komp = $("vgrVrsta").value === "komponenta";
    $("vgrUrl").hidden = komp; $("vgrKoda").hidden = !komp; $("vgrPojavnaPolje").hidden = komp;
    $("vgrNamig").textContent = t(komp ? "vgrKomponentaNamig" : "vgrZnacke");
  }
  function vgrPocisti() {
    VGR.ureja = null;
    $("vgrVrsta").value = "url"; $("vgrVrsta").disabled = false;
    $("vgrIme").value = ""; $("vgrUrl").value = ""; $("vgrKoda").value = ""; $("vgrPojavna").checked = false;
    $("vgrShrani").textContent = t("vgrDodaj"); $("vgrPreklici").hidden = true;
    vgrObrazecVrsta();
  }
  function vgrUredi(v) {
    VGR.ureja = v;
    $("vgrVrsta").value = v.vrsta; $("vgrVrsta").disabled = true;
    $("vgrIme").value = v.ime; $("vgrUrl").value = v.url || ""; $("vgrKoda").value = v.koda || ""; $("vgrPojavna").checked = !!v.pojavna;
    $("vgrShrani").textContent = t("shrani"); $("vgrPreklici").hidden = false;
    $("vgrSporocilo").textContent = "";
    vgrObrazecVrsta(); $("vgrIme").focus();
  }
  function vgrVnos() {
    var v = { ime: $("vgrIme").value.trim(), vrsta: $("vgrVrsta").value };
    if (v.vrsta === "komponenta") v.koda = $("vgrKoda").value; else { v.url = $("vgrUrl").value.trim(); v.pojavna = $("vgrPojavna").checked; }
    if (VGR.ureja) { v.id = VGR.ureja.id; v.vklopljen = VGR.ureja.vklopljen; }
    return v;
  }
  function vgrNapaka(koda) { return t("vgrNapaka_" + koda) || t("niUspelo"); }
  function vgrShrani(vnos, poUspehu) {
    // Prvi vir: enkrat obvestilo »na lastno odgovornost«, potrdi ga en gumb; sele nato se vir shrani.
    if (!vnos.id && !VGR.obvestilo) {
      var sloj = $("slojVgrOdgovornost"), gumb = $("vgrOdgPotrdi");
      sloj.classList.add("viden"); gumb.focus();
      gumb.onclick = function () {
        sloj.classList.remove("viden");
        klic("mediaVgrajeniObvestilo").then(function () { VGR.obvestilo = true; vgrShrani(vnos, poUspehu); });
      };
      return;
    }
    klic("mediaVgrajenVirShrani", [vnos]).then(function (r) {
      if (!r || !r.ok) { $("vgrSporocilo").textContent = vgrNapaka(r && r.napaka); return; }
      $("vgrSporocilo").textContent = t(vnos.id ? "vgrShranjeno" : "vgrDodano", { ime: r.vir.ime });
      if (poUspehu) poUspehu();
      naloziVgrajene();
    }, function () { $("vgrSporocilo").textContent = t("niUspelo"); });
  }
  function vgrPreizkusi() {
    var v = vgrVnos(), msg = $("vgrSporocilo");
    if (v.vrsta === "komponenta") {
      if (!v.koda.trim()) { msg.textContent = vgrNapaka("koda"); return; }
      msg.textContent = "";
      var p = { imdb: "tt0111161", tmdb: "278", tvdb: "190", type: "movie", title: "The Shawshank Redemption", year: "1994" };
      SafeerVgrajeno.komponenta({ koda: v.koda, props: vgrProps(p, "", p.title), title: (v.ime || t("vgrVrstaKomponenta")) + " · " + t("vgrPreizkusi"),
                                  knjiznica: vgrKnjiznica,
                                  onReady: function () { msg.textContent = t("vgrKomponentaDela"); },
                                  onError: function (s) { msg.textContent = t("vgrNapakaKomponente", { napaka: s }); } });
      return;
    }
    klic("mediaVgrajenVirPreizkusi", [v]).then(function (r) {
      if (!r || !r.ok) { msg.textContent = vgrNapaka(r && r.napaka); return; }
      msg.textContent = [r.film ? t("vgrPrimerFilm", { url: r.film }) : "", r.serija ? t("vgrPrimerSerija", { url: r.serija }) : ""].filter(Boolean).join("  ·  ");
    }, function () { msg.textContent = t("niUspelo"); });
  }
  function poveziVgrajene() {
    if (RAZL.ponudniki.indexOf(vgrPonudnik) < 0) RAZL.ponudniki.push(vgrPonudnik);
    if (!$("vgrObrazec") || !window.SafeerVgrajeno) return;
    SafeerVgrajeno.nastavi({ aktivno: function (da) { return klic("vgrajenoAktivno", [da]); },
                             besedila: { nazaj: t("nazaj"), celZaslon: t("vgrCelZaslon") } });
    $("vgrVrsta").addEventListener("change", vgrObrazecVrsta);
    $("vgrPreklici").addEventListener("click", function () { vgrPocisti(); $("vgrSporocilo").textContent = ""; });
    $("vgrPreizkusi").addEventListener("click", vgrPreizkusi);
    $("vgrObrazec").addEventListener("submit", function (e) {
      e.preventDefault();
      vgrShrani(vgrVnos(), vgrPocisti);
    });
    $("slojVgrOdgovornost").querySelector(".tancica").addEventListener("click", function () { $("slojVgrOdgovornost").classList.remove("viden"); });
    vgrObrazecVrsta();
    naloziVgrajene();
    // Nedosegljive vire preverjamo v ozadju vsakih 15 min, ob spremembi omrezja vse (core/meritve_virov.py).
    setInterval(function () { if (document.visibilityState !== "hidden") klic("mediaVgrajeniOsvezi", [false]); }, 15 * 60 * 1000);
    window.addEventListener("online", function () { klic("mediaVgrajeniOsvezi", [true]); });
  }

  // ---- vticniki strežnika Jellyfin (core/jellyfin_vticniki.py): tecejo na strežniku, Safeer jih le upravlja.
  // Ne-skrbnik vidi samo branje in razlog; gumba, ki ne bi delal, ni (lastnik: nobenih nedelujocih gumbov).
  // spremenjeni: strežniki, kjer je bil vticnik spremenjen in zagon se ni bil narejen (izklop ne da stanja Restart).
  var jf = { vir: null, stanje: null, zaganjam: false, potrjeno: null, spremenjeni: {} };
  var JF_KATEGORIJE = { administration: "jfKatAdministracija", anime: "jfKatAnime", authentication: "jfKatPrijava", books: "jfKatKnjige",
    channels: "jfKatKanali", general: "jfKatSplosno", livetv: "jfKatTv", "live tv": "jfKatTv", metadata: "jfKatMetapodatki",
    moviesandshows: "jfKatFilmi", music: "jfKatGlasba", notifications: "jfKatObvestila", subtitles: "jfKatPodnapisi", other: "jfKatDrugo" };
  function jfKategorija(k) { var kljuc = JF_KATEGORIJE[String(k || "").toLowerCase()]; return kljuc ? t(kljuc) : String(k || ""); }
  function jfSporocilo(besedilo) { $("jfSporocilo").textContent = besedilo || ""; }
  function jfNapaka(r) { return t("jfNapaka_" + ((r && r.napaka) || "omrezje")); }
  function odpriJellyfin(vir) {
    jf.vir = vir; jf.stanje = null; jf.potrjeno = null;
    $("jfNaslov").textContent = t("jfVticniki") + " · " + (vir.ime || vir.url || "Jellyfin");
    $("jfZagon").hidden = true;
    $("jfVsebina").innerHTML = "";
    $("slojJellyfin").classList.add("viden");
    $("jfZapri").focus({ preventScroll: true });
    naloziJellyfin();
  }
  // ohrani: sporocilo o pravkar izvedeni spremembi ostane vidno (ne »Nalagam …«).
  function naloziJellyfin(ohrani) {
    if (!jf.vir) return;
    var vir = jf.vir;
    if (ohrani !== true) jfSporocilo(t("jfNalagam"));
    klic("mediaJellyfinVticniki", [vir.id]).then(function (r) {
      if (jf.vir !== vir) return;
      if (!r || !r.ok) { jf.stanje = null; $("jfVsebina").innerHTML = ""; $("jfZagon").hidden = true; jfSporocilo(jfNapaka(r)); return; }
      jf.stanje = r; if (ohrani !== true) jfSporocilo("");
      var plosca = $("slojJellyfin").querySelector(".plosca"), vrh = plosca.scrollTop;
      narisiJellyfin();
      plosca.scrollTop = ohrani === true ? vrh : 0;        // ob odprtju od vrha, po spremembi ostane, kjer je bil
    }, function () { jfSporocilo(t("jfNapaka_omrezje")); });
  }
  // Gumb z dvema korakoma (kot Odstrani vir): prvi klik vpraša, drugi izvede; drugam z miško prekliče.
  function jfPotrdi(gumb, besedilo, potrdilo, dejanje) {
    gumb.textContent = besedilo;
    gumb.addEventListener("click", function () {
      if (jf.potrjeno !== gumb) {
        if (jf.potrjeno) { jf.potrjeno.textContent = jf.potrjeno._besedilo; jf.potrjeno.classList.remove("potrdi"); }
        jf.potrjeno = gumb; gumb._besedilo = besedilo; gumb.textContent = potrdilo; gumb.classList.add("potrdi"); return;
      }
      jf.potrjeno = null; gumb.classList.remove("potrdi"); dejanje();
    });
    gumb.addEventListener("blur", function () {
      if (jf.potrjeno === gumb) { jf.potrjeno = null; gumb.textContent = besedilo; gumb.classList.remove("potrdi"); }
    });
  }
  function jfIzvedi(metoda, argumenti, gumb) {
    if (gumb) gumb.disabled = true;
    jfSporocilo(t("jfIzvajam"));
    return klic(metoda, [jf.vir.id].concat(argumenti)).then(function (r) {
      if (gumb) gumb.disabled = false;
      if (!r || !r.ok) { jfSporocilo(jfNapaka(r)); return; }
      jf.spremenjeni[jf.vir.id] = true;
      jfSporocilo(t("jfVeljaPoZagonu"));
      naloziJellyfin(true);
    }, function () { if (gumb) gumb.disabled = false; jfSporocilo(t("jfNapaka_omrezje")); });
  }
  function jfPaketGumb(p) {
    // Namesti ali posodobi (ista pot: strežnik izbere najnovejšo združljivo različico).
    if (p.namescen && !p.posodobitev) return null;
    var g = el("button", "gumb" + (p.priporocen ? " glavni" : "")); g.type = "button";
    g.textContent = t(p.namescen ? "jfPosodobi" : "jfNamesti");
    g.setAttribute("aria-label", g.textContent + " " + p.ime);
    g.addEventListener("click", function () { jfIzvedi("mediaJellyfinNamesti", [p.ime, p.guid, p.repozitorij_url || ""], g); });
    return g;
  }
  function jfZnacke(p) {
    var z = el("span", "jf-znacke");
    if (p.namescen) z.appendChild(el("span", "jf-znacka", ubezi(t("jfNamescen", { v: p.namescena_razlicica || "" }).trim())));
    if (!p.uradni) z.appendChild(el("span", "jf-znacka jf-tretja", ubezi(t("jfTretjaOseba"))));
    if (p.safeer_zna) z.appendChild(el("span", "jf-znacka jf-zna", ubezi(t("jfSafeerZna"))));
    if (p.ni_v_safeerju) z.appendChild(el("span", "jf-znacka", ubezi(t("jfNiVSafeerju"))));
    return z;
  }
  function jfVrsticaPaketa(p, razlogKljuc) {
    var row = el("div", "kat-vir jf-paket"); row.innerHTML = svg("program");
    var info = el("div");
    var naslov = el("b", "", ubezi(p.ime) + (p.razlicica ? " <small>" + ubezi(p.razlicica) + "</small>" : ""));
    info.appendChild(naslov);
    info.appendChild(jfZnacke(p));
    var opis = razlogKljuc ? t(razlogKljuc) : (p.opis || "");
    if (p.safeer_zna && !razlogKljuc) opis = t(p.safeer_zna);
    if (opis) info.appendChild(el("small", "jf-opis", ubezi(opis)));
    if (p.repozitorij) info.appendChild(el("small", "", ubezi(t("jfIzRepozitorija", { ime: p.repozitorij }))));
    row.appendChild(info);
    return row;
  }
  function narisiJellyfin() {
    var r = jf.stanje, cilj = $("jfVsebina"); if (!r) return;
    cilj.innerHTML = "";
    var streznik = [r.streznik && r.streznik.ime, r.streznik && r.streznik.razlicica ? "Jellyfin " + r.streznik.razlicica : ""].filter(Boolean).join(" · ");
    if (streznik) cilj.appendChild(el("p", "drobno", ubezi(streznik)));
    var skrbnik = !!r.skrbnik;
    $("jfZagon").hidden = !(skrbnik && (r.potreben_zagon || jf.spremenjeni[jf.vir.id])) || jf.zaganjam;
    if (!skrbnik) cilj.appendChild(el("p", "jf-opozorilo", ubezi(t("jfNiSkrbnik"))));

    // Priporočeno: kratek izbor z uporabnikove strani; kar Safeer že zna, je označeno in ni ponujeno za namestitev.
    var prip = (r.priporoceno || []), sekcija = el("section", "jf-sekcija");
    sekcija.appendChild(el("h4", "", ubezi(t("jfPriporoceno"))));
    prip.filter(function (p) { return !p.safeer_zna; }).forEach(function (p) {
      var paket = p.paket || { ime: p.ime, guid: p.guid, uradni: true, namescen: p.namescen };
      var row = jfVrsticaPaketa(paket, p.razlog);
      if (skrbnik && p.paket) { var g = jfPaketGumb(p.paket); if (g) row.appendChild(g); }
      else if (skrbnik && !p.namescen) row.appendChild(el("small", "jf-ni", ubezi(t("jfNiVKatalogu"))));
      sekcija.appendChild(row);
    });
    var zna = prip.filter(function (p) { return p.safeer_zna; });
    if (zna.length) {
      sekcija.appendChild(el("h5", "", ubezi(t("jfSafeerZnaNaslov"))));
      zna.forEach(function (p) {
        var row = jfVrsticaPaketa({ ime: p.ime, guid: p.guid, uradni: true, namescen: p.namescen,
                                    namescena_razlicica: p.paket ? p.paket.namescena_razlicica : "" }, p.razlog);
        sekcija.appendChild(row);
      });
    }
    cilj.appendChild(sekcija);
    if (!skrbnik) return;

    // Nameščeni vtičniki: stikalo vklop/izklop, stanje, Odstrani (s potrditvijo).
    var namesceni = el("section", "jf-sekcija");
    namesceni.appendChild(el("h4", "", ubezi(t("jfNamesceni"))));
    if (!(r.namesceni || []).length) namesceni.appendChild(el("p", "drobno", ubezi(t("jfBrezNamescenih"))));
    (r.namesceni || []).forEach(function (v) {
      var row = el("div", "kat-vir jf-paket"); row.innerHTML = svg("program");
      var info = el("div");
      info.appendChild(el("b", "", ubezi(v.ime) + " <small>" + ubezi(v.razlicica) + "</small>"));
      info.appendChild(el("small", "jf-stanje jf-stanje-" + ubezi(v.stanje), ubezi(t("jfStanje_" + v.stanje))));
      if (v.opis) info.appendChild(el("small", "jf-opis", ubezi(v.opis)));
      row.appendChild(info);
      if (v.lahko_preklopi) {
        var stikalo = el("label", "jf-stikalo"), cb = document.createElement("input");
        cb.type = "checkbox"; cb.checked = !!v.vklopljen; cb.setAttribute("role", "switch");
        cb.setAttribute("aria-label", t(v.vklopljen ? "jfIzklopi" : "jfVklopi") + " " + v.ime);
        cb.addEventListener("change", function () {
          jfIzvedi("mediaJellyfinVticnik", [cb.checked ? "vklopi" : "izklopi", v.id, v.razlicica], cb);
        });
        stikalo.appendChild(cb); stikalo.appendChild(el("span", "", ubezi(t("jfVklopljen"))));
        row.appendChild(stikalo);
      }
      if (v.lahko_odstrani) {
        var odstrani = el("button", "gumb jf-odstrani"); odstrani.type = "button";
        jfPotrdi(odstrani, t("jfOdstrani"), t("jfOdstraniRes"), function () {
          jfIzvedi("mediaJellyfinVticnik", ["odstrani", v.id, v.razlicica], odstrani);
        });
        row.appendChild(odstrani);
      }
      namesceni.appendChild(row);
    });
    cilj.appendChild(namesceni);

    // Katalog strežnika po kategorijah (iz repozitorijev, ki jih je skrbnik vklopil na strežniku).
    var katalog = el("section", "jf-sekcija");
    katalog.appendChild(el("h4", "", ubezi(t("jfKatalog"))));
    var repo = (r.repozitoriji || []).filter(function (x) { return x.vklopljen; });
    if (repo.length) katalog.appendChild(el("p", "drobno", ubezi(t("jfRepozitoriji") + ": " + repo.map(function (x) {
      return x.ime + (x.uradni ? "" : " (" + t("jfTretjaOseba") + ")");
    }).join(", "))));
    if (r.napaka_kataloga) katalog.appendChild(el("p", "drobno", ubezi(t("jfNapaka_" + r.napaka_kataloga))));
    var skupine = {};
    (r.katalog || []).forEach(function (p) { (skupine[p.kategorija] = skupine[p.kategorija] || []).push(p); });
    Object.keys(skupine).sort(function (a, b) { return jfKategorija(a).localeCompare(jfKategorija(b)); }).forEach(function (k) {
      var d = document.createElement("details"); d.className = "jf-kategorija";
      d.appendChild(el("summary", "", ubezi(jfKategorija(k)) + " <small>" + skupine[k].length + "</small>"));
      skupine[k].forEach(function (p) {
        var row = jfVrsticaPaketa(p, "");
        var g = jfPaketGumb(p); if (g) row.appendChild(g);
        d.appendChild(row);
      });
      katalog.appendChild(d);
    });
    cilj.appendChild(katalog);
  }
  function jfZazeniZnova() {
    var gumb = $("jfZagonGumb");
    if (!jf.vir || jf.zaganjam) return;
    if (!gumb.classList.contains("potrdi")) {
      gumb.classList.add("potrdi"); gumb.querySelector("span").textContent = t("jfZazeniZnovaRes"); return;
    }
    gumb.classList.remove("potrdi"); gumb.querySelector("span").textContent = t("jfZazeniZnova");
    jf.zaganjam = true; $("jfZagon").hidden = true;
    var vir = jf.vir;
    jfSporocilo(t("jfZagon_ustavljam"));
    klic("mediaJellyfinZagon", [vir.id]).then(function (r) {
      jf.zaganjam = false;
      if (jf.vir !== vir) return;
      if (r && r.ok) { delete jf.spremenjeni[vir.id]; jfSporocilo(t("jfZagon_pripravljen")); naloziKatalog(); naloziJellyfin(true); }
      else { jfSporocilo(r && r.napaka === "cas" ? t("jfZagon_napaka") : jfNapaka(r)); $("jfZagon").hidden = false; }
    }, function () { jf.zaganjam = false; jfSporocilo(t("jfNapaka_omrezje")); $("jfZagon").hidden = false; });
  }
  function jfNapredekZagona(p) {
    if (!p || !jf.vir || p.streznik !== jf.vir.id || !jf.zaganjam) return;
    jfSporocilo(t("jfZagon_" + p.faza, { s: p.sekund || 0 }));
  }
  function poveziJellyfin() {
    if (!$("slojJellyfin")) return;
    $("jfZapri").addEventListener("click", function () { $("slojJellyfin").classList.remove("viden"); jf.vir = null; });
    $("jfOsvezi").addEventListener("click", function () { naloziJellyfin(); });
    $("jfZagonGumb").addEventListener("click", jfZazeniZnova);
    $("jfZagonGumb").addEventListener("blur", function () {
      if (this.classList.contains("potrdi")) { this.classList.remove("potrdi"); this.querySelector("span").textContent = t("jfZazeniZnova"); }
    });
  }
  function odpriKatViri() {
    $("katVirSporocilo").textContent = "";
    $("slojKatViri").classList.add("viden");
    naloziKatViri();
    naloziVgrajene();
    $("mediaStreznikUrl").focus();
  }
  // Gumb "Install" na strani z dodatki Stremio (stremio://): okno Dodatki z naslovom dodatka; doda se sele na Poveži.
  function pokaziStremioDodatek(url) {
    if (!url) return;
    odpriKatViri();
    $("mediaStreznikVrsta").value = "stremio";
    katPrilagodiObrazec();
    $("mediaStreznikUrl").value = url;
    var gostitelj = url;
    try { gostitelj = new URL(url).hostname; } catch (e) { /* naslov ostane, kot je */ }
    $("katVirSporocilo").textContent = t("katStremioPotrdi", { gostitelj: gostitelj });
    var gumb = document.querySelector("#mediaDodajStreznik button[type=submit]");
    if (gumb) gumb.focus();
  }
  // Prilepi: naslov iz odlozisca (samo na klik); naslov dodatka Stremio izbere vrsto Dodatek Stremio.
  function katPrilepi() {
    klic("odlozisceBesedilo").then(function (besedilo) {
      besedilo = String(besedilo || "").trim();
      if (!besedilo) { $("katVirSporocilo").textContent = t("katOdloziscePrazno"); return; }
      if (/^stremio:\/\//i.test(besedilo) || /\/manifest\.json$|\/configure\/?$/i.test(besedilo)) {
        $("mediaStreznikVrsta").value = "stremio";
        katPrilagodiObrazec();
      }
      $("mediaStreznikUrl").value = besedilo;
      $("katVirSporocilo").textContent = "";
      $("mediaStreznikUrl").focus();
    }).catch(function () { $("katVirSporocilo").textContent = t("katOdloziscePrazno"); });
  }
  function katPrilagodiObrazec() {
    // Dodatek in DLNA nimata prijave; polji za uporabnika in geslo pokažemo samo strežnikom, ki ju potrebujejo.
    var p = $("mediaStreznikVrsta").value, brez = p === "stremio" || p === "dlna";
    $("mediaStreznikUporabnik").hidden = brez; $("mediaStreznikSkrivnost").hidden = brez;
    $("mediaStreznikUrl").placeholder = t(p === "stremio" ? "katNaslovDodatka" : "katNaslovStreznika");
  }
  function poveziKatalog() {
    poveziPolice();       // prvi: Escape zapre meni kartice ali ponudbo epizode, preden zapre podrobnosti
    poveziJellyfin();
    poveziVgrajene();
    var ob = function (id, dogodek, fn) { var e = $(id); if (e) e.addEventListener(dogodek, fn); };
    ob("mediaRazvrsti", "change", function () { kat.razvrsti = this.value; naloziKatalog(); });
    ob("mediaDebrid", "change", function () { izbranDebrid(this.value); });
    ob("debridZapri", "click", zapriSloje);
    ob("debridSamoTakoj", "change", function () {
      klic("mediaDebrid", ["samo_takoj", this.checked]).then(narisiDebridOkno).catch(function () {});
    });
    ob("mediaJezik", "change", function () {
      kat.jezikVsebine = this.value; kat.page = 1;
      // Drug jezik: kartice prejsnjega takoj izginejo (jezik naslovov iz dodatkov se prvic poisce - to lahko traja).
      kat.katalog = []; kat.strani = []; kat.nalozen = false; kat.skupaj = null; kat.skupaj_strani = 1;
      narisiKatalog(); naloziKatalog();
    });
    ob("mediaDrzava", "change", function () {
      kat.drzavaRadia = this.value; kat.page = 1;
      kat.katalog = []; kat.strani = []; kat.nalozen = false; kat.skupaj = null; kat.skupaj_strani = 1;
      narisiKatalog(); naloziKatalog();
    });
    ob("mediaViriFilterGumb", "click", function (event) {
      event.stopPropagation();
      var plosca = $("mediaViriFilter"), odpri = plosca.hidden;
      plosca.hidden = !odpri; this.setAttribute("aria-expanded", odpri ? "true" : "false");
      if (odpri) narisiViriFilter();
    });
    ob("mediaViriFilterPonastavi", "click", function () {
      kat.izklopljeni = {};
      narisiViriFilter(); osveziGumbViri(); naloziKatalog();
    });
    ob("mediaPodrobnostiNazaj", "click", zapriKatalogPodrobnosti);
    ob("mediaPodrobnostiZapri", "click", zapriKatalogPodrobnosti);
    // Isti gumbi za skladbo iz kataloga (vrsto vodi stran) in za domaci predvajalnik (njegova vrsta datotek).
    var ukaz = function (u) { klic("predvajalnikUkaz", [u]).catch(function () {}); };
    ob("mediaPrejsnja", "click", function () { if (spNaTraku()) spUkazTraka("nazaj"); else if (skladbaKataloga()) predvajajIzVrste(-1); else ukaz("prejsnja"); });
    ob("mediaNaslednja", "click", function () { if (spNaTraku()) spUkazTraka("naprej"); else if (skladbaKataloga()) predvajajIzVrste(1); else ukaz("naslednja"); });
    // Nakljucno in Ponovi: uporabnik je vrsto spremenil - ob koncu seznama Safeer ne izbere sam naslednjega.
    ob("mediaPremesaj", "click", function () {
      vrstaShrani("premesaj", nakljucnoVklopljeno() ? "0" : "1"); kat.vrstaSpremenjena = true; premesajVrsto();
      S.mediaQueueKey = ""; narisiVrsto();
    });
    ob("mediaPonovi", "click", function () { vrstaShrani("ponovi", vrstaNastavitev("ponovi", "0") === "1" ? "0" : "1"); kat.vrstaSpremenjena = true; narisiVrsto(); });
    ob("mediaKatPremor", "click", function () { if (spNaTraku()) spUkazTraka("premor"); else if (skladbaKataloga()) premorKatPredvajanja(); else ukaz("premor"); });
    ob("mediaZapri", "click", function () { if (spNaTraku()) spUstaviTrak(); else if (kat.aktivni) ustaviKatPredvajanje(); else ukaz("ustavi"); });
    ob("medijiDodatki", "click", function () { zapriMeniDodaj(false); odpriKatViri(); });
    ob("katNalaganjeZnova", "click", function () { kat.napakaVec = false; naloziKatalog(true); });
    ob("katViriZapri", "click", zapriSloje);
    ob("katZasebno", "click", preklopiZasebno);
    ob("katPrilepi", "click", katPrilepi);
    // Imenik dodatkov Stremio: Install na strani doda dodatek v Safeer (stremio:// -> okno Dodatki, potrdi Poveži).
    ob("katPoisciDodatke", "click", function () { odpriVSpletu("https://stremio-addons.net/"); });
    ob("mediaStreznikVrsta", "change", katPrilagodiObrazec);
    ob("mediaDodajStreznik", "submit", function (event) {
      event.preventDefault();
      var provider = $("mediaStreznikVrsta").value, url = $("mediaStreznikUrl").value.trim(), secret = $("mediaStreznikSkrivnost").value;
      var sporocilo = $("katVirSporocilo");
      if (!url) return;
      if ({ jellyfin: 1, emby: 1, navidrome: 1, plex: 1 }[provider] && !secret) { sporocilo.textContent = t("katPotrebujeGeslo"); return; }
      sporocilo.textContent = t("katPovezujem");
      klic("mediaDodajStreznik", [provider, $("mediaStreznikIme").value.trim(), url, $("mediaStreznikUporabnik").value.trim(), secret]).then(function (result) {
        $("mediaStreznikSkrivnost").value = "";
        if (result && result.ok) {
          $("mediaStreznikUrl").value = ""; $("mediaStreznikIme").value = "";
          sporocilo.textContent = t("katPovezano");
          naloziKatViri(); naloziKatalog();
        } else sporocilo.textContent = (result && (result.sporocilo || result.napaka)) || t("katNapakaVira");
      }, function () { $("mediaStreznikSkrivnost").value = ""; sporocilo.textContent = t("katNapakaVira"); });
    });
    ob("mediaDodajVir", "submit", function (event) {
      event.preventDefault();
      var url = $("mediaVirUrl").value.trim(), sporocilo = $("katVirSporocilo");
      if (!url) return;
      sporocilo.textContent = t("katDodajam");
      klic("mediaDodajVir", [url, $("mediaVirIme").value.trim()]).then(function (result) {
        if (result && result.ok) { $("mediaVirUrl").value = ""; $("mediaVirIme").value = ""; sporocilo.textContent = t("katVirDodan"); }
        else sporocilo.textContent = (result && result.napaka === "podvojen") ? t("katVirPodvojen")
          : (result && result.sporocilo) ? result.sporocilo : t("katVirNiDodan");
        naloziKatViri(); naloziKatalog();
      }, function () { sporocilo.textContent = t("katVirNiDodan"); });
    });
    // DLNA/UPnP (Gerbera, MiniDLNA, NAS): poiščemo jih v domačem omrežju in ponudimo povezavo z enim klikom.
    ob("mediaOdkrijDlna", "click", function () {
      var sporocilo = $("katVirSporocilo");
      sporocilo.textContent = t("katDlnaIscem");
      klic("mediaOdkrijDlna").then(function (najdeni) {
        var seznam = najdeni || [];
        if (!seznam.length) { sporocilo.textContent = t("katDlnaNi"); return; }
        sporocilo.textContent = t("katDlnaNajdeni");
        seznam.forEach(function (n) {
          var g = el("button", "gumb"); g.type = "button"; g.textContent = t("katDlnaPovezi", { ime: n.ime });
          g.addEventListener("click", function () {
            sporocilo.textContent = t("katPovezujem");
            klic("mediaDodajStreznik", ["dlna", n.ime, n.url, "", ""]).then(function (r) {
              sporocilo.textContent = r && r.ok ? t("katPovezano") : ((r && r.napaka) || t("katNapakaVira"));
              naloziKatViri(); naloziKatalog();
            });
          });
          sporocilo.appendChild(document.createElement("br"));
          sporocilo.appendChild(g);
        });
      }, function () { sporocilo.textContent = t("katNapakaVira"); });
    });
    window.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      var panel = $("mediaPodrobnosti");
      if (panel && !panel.hidden) { zapriKatalogPodrobnosti(); e.stopPropagation(); e.preventDefault(); }
    }, true);
    katPrilagodiObrazec(); osveziGumbViri(); narisiVrsto();
    zacniNeskoncnoDrsenje();
  }
  // Besedila ob menjavi jezika: napisi, ki jih ne nosi data-t (izbirnik razvrstitve, gumb virov, zvrsti).
  function prevediKatalog() {
    var r = $("mediaRazvrsti"); if (!r) return;
    [["", "katRazPriporoceno"], ["novo", "katRazNovo"], ["staro", "katRazStaro"], ["az", "katRazAZ"], ["za", "katRazZA"]].forEach(function (o, i) {
      if (!r.options[i]) r.add(new Option("", o[0]));
      r.options[i].textContent = t(o[1]);
    });
    kat.jezikiZa = null; narisiJezikVsebine();
    if (debridStanje) narisiDebrid(!$("mediaDebridPolje").hidden);
    if (kat.radioDrzave) kat.radioDrzaveZa = ""; narisiDrzavoRadia();      // imena jezikov v novem jeziku vmesnika
    POL.podpis = ""; narisiPolice();                // naslovi polic in napisi na karticah v novem jeziku
    osveziGumbViri(); katPrilagodiObrazec();
  }
  function katDogodek(vrsta, podatki) {
    if (vrsta === "mediaOdkrivanje" && podatki) prevzemiOdkrivanje(podatki);
    if (vrsta === "mediaKatalogOsvezen" && podatki && katVidno() && podatki.kljuc &&
        kat.strani.some(function (s) { return s.kljuc === podatki.kljuc; })) prevzemiKatalog(podatki, true);
    if (vrsta === "mediaNiNaVoljo" && podatki && podatki.idji && kat.katalog) {
      var prejKartic = kat.katalog.length;
      kat.katalog = kat.katalog.filter(function (x) { return podatki.idji.indexOf(x.id) < 0; });
      kat.strani.forEach(function (s) { s.vnosi = s.vnosi.filter(function (x) { return podatki.idji.indexOf(x.id) < 0; }); });
      if (kat.katalog.length !== prejKartic) {
        if (typeof kat.skupaj === "number") kat.skupaj = Math.max(kat.katalog.length, kat.skupaj - (prejKartic - kat.katalog.length));
        if (katVidno()) { var sidro = katSidro(); narisiKatalog(); katPovrniSidro(sidro); }
      }
    }
    if ((vrsta === "mediaSeznamiUsklajeni") || (vrsta === "mediaSeznamOsvezen" && podatki && podatki.ime)) {
      naloziSeznamePredvajanja();
      if (kat.seznam && kat.seznam.ime && (vrsta === "mediaSeznamiUsklajeni" || kat.seznam.ime === podatki.ime)) {
        var ime = kat.seznam.ime;
        klic("mediaSeznam", [ime]).then(function (sz) {
          if (!kat.seznam || kat.seznam.ime !== ime) return;
          kat.seznam = sz && sz.vnosi && sz.vnosi.length ? sz : null; narisiKatalog();
        }, function () {});
      }
    }
    // Naprava v krogu je odstranila film, ki ga hrani ta računalnik: polica se osveži.
    if (vrsta === "mediaKnjiznicaSpremenjena" && katVidno()) naloziKnjiznico();
    // Moji viri so se uskladili z drugo napravo v Linku (dodan ali izbrisan dodatek, podkast ...): viri in katalog se osvežijo.
    if (vrsta === "mediaViriUsklajeni" && katVidno()) { naloziKatViri(); naloziKatalog(); }
    // Meritev vgrajenega vira se je spremenila (spet dosegljiv ali ne vec): seznam, ploscice in gumbi se osvezijo.
    if (vrsta === "mediaVgrajeniMeritve") naloziVgrajene();
    var zaAktivno = kat.aktivni && podatki && podatki.id === kat.aktivni.id;
    // Skladba je odigrana do konca (domači predvajalnik ali vgradni predvajalnik YouTuba): naslednja iz vrste.
    if (vrsta === "mediaKonec" && zaAktivno && !predvajajIzVrste(1, true)) skrijKatTrak();
    // Naslednja epizoda (core/os_katalog.py): ponudba z odstevanjem; konec ponudbe (zacelo ali preklicalo jo je
    // drugo okno, uporabnik je izbral drugo vsebino) jo skrije povsod.
    if (vrsta === "mediaNaslednja" && podatki && podatki.zeton) { pokaziNaslednjo(podatki); naloziPolice(); }
    if (vrsta === "mediaNaslednjaKonec" && podatki && NASL.ponudba && NASL.ponudba.zeton === podatki.zeton) skrijNaslednjo();
    if (vrsta === "predvajalnik" && NASL.ponudba && podatki && podatki.stanje === "predvaja" && Date.now() - NASL.od > 2500) prekliciNaslednjo();
    if (vrsta === "mediaKonec") naloziPolice();
    // Tipka ali daljinec »naslednja/prejšnja« pri skladbi iz kataloga: vrsto vodi stran.
    if (vrsta === "mediaVrstaUkaz" && kat.aktivni) predvajajIzVrste(Number(podatki) < 0 ? -1 : 1);
    if (vrsta === "mediaYt" && zaAktivno) {
      kat.igra = !!podatki.igra; if (kat.igra) kat.vrstaNapake = 0; osveziKatTrak();
      if (podatki.zivo && kat.vrsta.length) oznaciZivo();
    }
    if (vrsta === "mediaYtZaprt" && zaAktivno) { kat.vrsta = []; skrijKatTrak(); }
    if (vrsta === "mediaYtNapaka" && zaAktivno) {
      // Lastnik posnetka vgradnje ne dovoli (ali posnetka ni več): poiščemo drug posnetek iste skladbe, sicer naslednja.
      var skladba = kat.aktivni;
      if (podatki && podatki.zamenjaj === false) {
        // Napaka dekoderja ali nastavitve: posnetka ne zamenjamo (18. 10. 2026), tiho naprej na naslednjo skladbo -
        // lastnik: napak predvajalnika uporabniku ne izpisujemo, lovilci napak poskrbijo za vsebino (sled je v sled.log).
        naprejPoNapaki();
        return;
      }
      klic("mediaSeznamZamenjava", [skladba.id]).then(function (nova) {
        if (kat.aktivni !== skladba) return;
        if (nova && nova.youtube && nova.youtube !== skladba.youtube) { kat.izVrste = true; odpriKatalogVnos(skladba.id); return; }
        naprejPoNapaki();
      }, function () { if (kat.aktivni === skladba) naprejPoNapaki(); });
    }
    // Stanje domačega predvajalnika: znak premora v traku sledi resničnemu stanju.
    if (vrsta === "predvajalnik" && kat.aktivni && kat.aktivni.zvok && !kat.aktivni.okno_youtube && podatki) {
      var igra = podatki.stanje === "predvaja";
      if (igra) kat.vrstaNapake = 0;
      if (igra !== kat.igra) { kat.igra = igra; osveziKatTrak(); }
      // Tok brez dolzine po 3 s (core/os_predvajalnik.je_v_zivo): skladba s seznama je prenos v zivo.
      if (igra && podatki.zivo && kat.vrsta.length) oznaciZivo();
    }
  }

  // ------------------------------------------------------------------ dogodki iz safeer_os.py
  // ------------------------------------------------------------------ Prostori (Safeer Link Spaces, MVP 25. 10. 2026)
  // Ta racunalnik in zasloni povezanih naprav v enem preklopniku (pravila core/link_prostori.py, most safeer_os._prostori,
  // nacrt nacrti/safeer-link-spaces-adr.md). Odpre ga gumb v glavi ali Super+Tab (tipko ujame safeer_os._na_tipko, ker
  // WebKitGTK tipke Super ne sporoci zanesljivo). Izbira: puscice, poteg ali vodoraven poteg na sledilni ploscici, Super+Tab
  // naprej, Shift+Super+Tab nazaj; Enter ali klik odpre zaslon naprave po obstojeci poti (oddaljeni zaslon racunalnika ali
  // deljenje zaslona naprave Android). Ploscice so na stalnih mestih; slicica je v MVP ikona vrste naprave in stanje.
  // Krog 2 (25. 10. 2026): lokalna namizja Cinnamona v istem preklopniku (namizja), slicice racunalnikov v zivo samo
  // med odprtim preklopnikom (slike, slikaZanka), meni »+« (namizje, naprava, nacin prikaza), Super+Alt+puscica do
  // sosednjega prostora, neobvezen zgornji rob (rob).
  var PR = { seznam: [], izbran: 0, odpira: "", stanje: "", prej: null, zanka: 0, kolo: 0, poteg: null, nalozeno: false, cakaSmer: 0,
             zap: 0, nalaga: false, namizja: [], najvec: 12, slike: {}, slikaZanka: 0, slikaTece: false, meni: false,
             rob: false, robCas: 0 };
  var PROSTOR_IKONA = { racunalnik: "namizje", tablica: "tablica", telefon: "telefon", tv: "zaslon", naprava: "naprave" };
  function prostoriOdprto() { var s = $("slojProstori"); return !!(s && s.classList.contains("viden")); }
  function prostorKdaj(sekunde) {
    if (!sekunde) return "";
    var r = sekunde - Date.now() / 1000, a = Math.abs(r);
    try {
      var f = new Intl.RelativeTimeFormat(LOKALE[jezik] || "en-GB", { numeric: "auto" });
      if (a < 3600) return f.format(Math.round(r / 60), "minute");
      if (a < 48 * 3600) return f.format(Math.round(r / 3600), "hour");
      if (a < 30 * 86400) return f.format(Math.round(r / 86400), "day");
      return new Date(sekunde * 1000).toLocaleDateString(LOKALE[jezik] || "en-GB");
    } catch (e) {
      return new Date(sekunde * 1000).toLocaleString(LOKALE[jezik] || "en-GB");
    }
  }
  // Lokalne ploscice: namizja Cinnamona (trenutno = »ta«), brez njih (Wayland, brez wmctrl) ena ploscica »Ta racunalnik«.
  function prostoriLokalne() {
    if (!PR.namizja.length) return [{ ta: true, id: "" }];
    return PR.namizja.map(function (n) {
      return { namizje: true, st: n.st, ta: !!n.trenutno, okna: Array.isArray(n.okna) ? n.okna : [], id: "namizje:" + n.st };
    });
  }
  function prostoriPloscice() { return prostoriLokalne().concat(PR.seznam).concat([{ dodaj: true, id: "+" }]); }
  function prostorTrenutni() {
    var i = prostoriPloscice().map(function (p) { return !!p.ta; }).indexOf(true);
    return i < 0 ? 0 : i;
  }
  function prostorIme(p) {
    if (p.namizje) return t("prostorNamizje", { n: p.st + 1 });
    return p.ta ? t("taRacunalnik") : (p.dodaj ? t("prostorPlus") : (p.ime || p.id));
  }
  function prostorPod(p) {
    if (p.ta) return t("prostorTaPod");
    if (p.namizje) return p.okna.length ? t("prostorOken", { n: p.okna.length }) : t("prostorPrazno");
    if (p.dodaj) return t("prostorPlusPod");
    if (p.povezana) return t("prostorPovezana");
    return p.videna ? t("prostorNazadnje", { kdaj: prostorKdaj(p.videna) }) : t("prostorNiPovezana");
  }
  function narisiProstore(fokus) {
    var trak = $("prostoriTrak");
    if (!trak) return;
    var vse = prostoriPloscice();
    PR.izbran = Math.max(0, Math.min(PR.izbran, vse.length - 1));
    trak.innerHTML = "";
    vse.forEach(function (p, i) {
      var ovoj = el("div", "prostor-ovoj");
      var b = el("button", "prostor" + (p.ta ? " ta" : "") + (p.dodaj ? " dodaj" : "") + (!p.ta && !p.dodaj && !p.namizje && !p.povezana ? " brez" : ""));
      b.type = "button";
      b.setAttribute("data-prostor", String(i));
      var ime = prostorIme(p), pod = prostorPod(p);
      var slicica = el("span", "prostor-slicica", p.namizje ? "" : svg(p.ta ? "namizje" : (p.dodaj ? "plus" : (PROSTOR_IKONA[p.vrsta] || "naprave"))));
      // Ta racunalnik in njegova namizja: ozadje Safeer OS; namizje dobi se shemo oken (polozaj iz wmctrl, brez posnetka).
      if ((p.ta || p.namizje) && S.zacetek && S.zacetek.ozadje) slicica.style.backgroundImage = 'url("' + String(S.zacetek.ozadje).replace(/"/g, "%22") + '")';
      if (p.namizje) {
        p.okna.forEach(function (o) {
          var r = el("i", "prostor-okno");
          r.style.left = (o.x * 100) + "%"; r.style.top = (o.y * 100) + "%";
          r.style.width = (o.w * 100) + "%"; r.style.height = (o.h * 100) + "%";
          r.title = String(o.naslov || "");
          slicica.appendChild(r);
        });
      }
      if (!p.ta && !p.dodaj && !p.namizje) {
        b.setAttribute("data-id", String(p.id));
        if (p.povezana && PR.slike[p.id]) slicica.appendChild(prostorSlika(PR.slike[p.id]));
      }
      b.appendChild(slicica);
      var napis = el("span", "prostor-napis");
      napis.appendChild(el("b", "", ubezi(ime)));
      napis.appendChild(el("small", "", (!p.ta && !p.dodaj && !p.namizje ? '<i class="pika' + (p.povezana ? "" : " siva") + '" aria-hidden="true"></i>' : "") + ubezi(pod)));
      b.appendChild(napis);
      b.setAttribute("aria-label", [ime, p.vrsta ? t("prostorVrsta_" + p.vrsta) : "", pod].filter(Boolean).join(", "));
      if (p.ta) b.setAttribute("aria-current", "true");
      if (p.dodaj) { b.setAttribute("aria-haspopup", "true"); b.setAttribute("aria-expanded", PR.meni ? "true" : "false"); b.setAttribute("aria-controls", "prostoriMeni"); }
      if (PR.odpira && PR.odpira === p.id) b.setAttribute("aria-busy", "true");
      b.addEventListener("click", function () { PR.izbran = i; oznaciProstor(false); prostorIzberi(p); });
      b.addEventListener("focus", function () { if (PR.izbran !== i) { PR.izbran = i; oznaciProstor(false); } });
      ovoj.appendChild(b);
      // »Samo ena aplikacija«: obstojeca pot Programi -> naprava -> Odpri tukaj (en program na tem racunalniku).
      if (!p.ta && !p.dodaj && !p.namizje && p.povezana && p.aplikacije) {
        var en = el("button", "gumb majhen prostor-aplikacija", ubezi(t("prostorEnaAplikacija")));
        en.type = "button";
        en.title = t("prostorEnaAplikacijaNamig", { ime: ime });
        en.addEventListener("click", function () { prostorEnaAplikacija(p); });
        ovoj.appendChild(en);
      }
      trak.appendChild(ovoj);
    });
    $("prostoriStanje").textContent = PR.stanje;
    if ($("prostoriRob")) $("prostoriRob").checked = !!PR.rob;
    oznaciProstor(fokus);
  }
  // Slicica racunalnika v zivo (screen.thumb prek mosta, Python preveri sliko in napravo); src nastavimo kot lastnost.
  function prostorSlika(src) {
    var img = document.createElement("img");
    img.className = "prostor-zivo";
    img.alt = "";
    img.src = src;
    return img;
  }
  function osveziSlicice() {
    if (PR.slikaTece || !prostoriOdprto() || skrito()) return;
    var racunalniki = PR.seznam.filter(function (p) { return p.povezana && p.nacin === "racunalnik"; });
    if (!racunalniki.length) return;
    PR.slikaTece = true;
    // Ena naprava za drugo: pocasna povezava ne nabira klicev (Python ima se svoj premor na napravo).
    racunalniki.reduce(function (veriga, p) {
      return veriga.then(function () {
        if (!prostoriOdprto()) return null;
        return klic("prostorSlicica", [p.id]).then(function (r) {
          if (!r || !r.ok || typeof r.slika !== "string" || r.slika.indexOf("data:image/jpeg;base64,") !== 0) return;
          if (PR.slike[p.id] === r.slika) return;
          PR.slike[p.id] = r.slika;
          Array.prototype.forEach.call(document.querySelectorAll("#prostoriTrak button.prostor[data-id]"), function (b) {
            if (b.getAttribute("data-id") !== p.id) return;
            var s = b.querySelector(".prostor-slicica"), star = s.querySelector("img.prostor-zivo");
            if (star) star.src = r.slika; else s.appendChild(prostorSlika(r.slika));
            b.classList.add("zivo");
          });
        }, function () { return null; });
      });
    }, Promise.resolve()).then(function () { PR.slikaTece = false; }, function () { PR.slikaTece = false; });
  }
  // Izbrana ploscica: edina v zaporedju tipke Tab (roving tabindex), oznacena in po potrebi v fokusu.
  function oznaciProstor(fokus) {
    var trak = $("prostoriTrak");
    if (!trak) return;
    Array.prototype.forEach.call(trak.querySelectorAll(".prostor-ovoj"), function (o, i) {
      var izbran = i === PR.izbran;
      o.classList.toggle("izbran", izbran);
      Array.prototype.forEach.call(o.querySelectorAll("button"), function (b) { b.tabIndex = izbran ? 0 : -1; });
      if (izbran && fokus) {
        var b = o.querySelector("button.prostor");
        b.focus();
        if (b.scrollIntoView) b.scrollIntoView({ block: "nearest", inline: "nearest" });
      }
    });
  }
  function premakniProstor(smer) {
    var n = prostoriPloscice().length;
    PR.izbran = ((PR.izbran + smer) % n + n) % n;
    oznaciProstor(true);
  }
  function nalozProstore(fokus, osvezi) {
    var izbranId = (prostoriPloscice()[PR.izbran] || {}).id;
    if (!PR.nalozeno) { PR.stanje = t("prostoriIscem"); narisiProstore(fokus); }
    // Pocasen Control (vgradnja, obvisel D-Bus): sprotna osvezitev se ne zacne, dokler prejsnji klic tece, in odgovor
    // starejsega klica ne prepise novejsega (zaporedna stevilka; pregled 25. 10. 2026).
    if (osvezi && PR.nalaga) return Promise.resolve();
    var zap = ++PR.zap;
    PR.nalaga = true;
    var prej = PR.nalozeno ? JSON.stringify(PR.seznam) + "|" + PR.stanje + "|" + JSON.stringify(PR.namizja) : "";
    return klic("prostori", [!osvezi]).then(function (r) {
      if (zap !== PR.zap) return;
      PR.nalaga = false;
      PR.nalozeno = true;
      PR.seznam = r && Array.isArray(r.prostori) ? r.prostori : [];
      PR.namizja = r && Array.isArray(r.namizja) ? r.namizja : [];
      if (r && r.najvec_namizij) PR.najvec = r.najvec_namizij;
      if (r && typeof r.rob === "boolean") PR.rob = r.rob;
      if (r && r.koda === "ni_controla") PR.stanje = t("niControla");
      else if (PR.stanje === t("prostoriIscem")) PR.stanje = PR.seznam.length ? "" : t("prostoriPrazno");
      // Izbira ostane na isti napravi, tudi ce se je seznam vmes spremenil.
      var vse = prostoriPloscice(), i = vse.map(function (p) { return p.id; }).indexOf(izbranId);
      if (PR.cakaSmer) {
        // Prvo odprtje z bliznjico, preden je bil seznam znan: naslednji (prejsnji) prostor izberemo sele zdaj.
        PR.izbran = prostorZacetni(PR.cakaSmer);
        PR.cakaSmer = 0; prej = "";
      } else if (i >= 0) PR.izbran = i;
      // Osvezitev brez sprememb ne riše znova (klik, ki se je zacel na ploscici, se ne izgubi).
      if (prej && prej === JSON.stringify(PR.seznam) + "|" + PR.stanje + "|" + JSON.stringify(PR.namizja)) return;
      if (PR.meni) narisiMeni(false);
      if (prostoriOdprto()) narisiProstore(fokus && $("slojProstori").contains(document.activeElement) || fokus === "vedno");
    }, function () {
      if (zap !== PR.zap) return;
      PR.nalaga = false;
      PR.stanje = t("niUspelo");
      if (prostoriOdprto()) narisiProstore(false);
    });
  }
  // Prvi pritisk bliznjice izbere sosednji prostor trenutnega (namizja ali »Ta racunalnik«); nazaj iz prvega skoci na
  // zadnjo napravo (pred »+«). Gumb (smer 0) ostane na trenutnem.
  function prostorZacetni(smer) {
    var n = prostoriPloscice().length, i = prostorTrenutni();
    if (smer > 0) return Math.min(i + 1, n - 1);
    if (smer < 0) return i > 0 ? i - 1 : Math.max(0, n - 2);
    return i;
  }
  function odpriProstore(smer) {
    if (EN_RAZDELEK || !$("slojProstori")) return;
    if (prostoriOdprto()) { premakniProstor(smer || 1); return; }
    PR.prej = document.activeElement;
    PR.stanje = PR.nalozeno ? (PR.seznam.length ? "" : t("prostoriPrazno")) : "";
    PR.cakaSmer = PR.nalozeno ? 0 : (smer || 0);
    PR.izbran = !PR.nalozeno ? 0 : prostorZacetni(smer || 0);
    zapriMeni(false);
    $("slojProstori").classList.add("viden");
    $("gumbProstori").setAttribute("aria-expanded", "true");
    narisiProstore(true);
    nalozProstore("vedno");
    clearInterval(PR.zanka);
    // Stanje povezave se med odprtim preklopnikom osvezuje (naprava pride ali odide); zaprt sloj zanko ustavi.
    PR.zanka = setInterval(function () {
      if (!prostoriOdprto()) { clearInterval(PR.zanka); return; }
      if (!skrito()) nalozProstore(true, true);
    }, 5000);
    // Slicice racunalnikov: samo dokler je preklopnik odprt (zaprt ne sprasuje nobene naprave).
    clearInterval(PR.slikaZanka);
    PR.slikaZanka = setInterval(function () {
      if (!prostoriOdprto()) { clearInterval(PR.slikaZanka); PR.slikaZanka = 0; return; }
      osveziSlicice();
    }, 3000);
    setTimeout(osveziSlicice, 300);
  }
  function zapriProstore() {
    // Pospravi tudi, ce je sloj ze skril kdo drug (aria-expanded je ostal "true").
    var gumb = $("gumbProstori");
    if (!gumb || (!prostoriOdprto() && gumb.getAttribute("aria-expanded") !== "true")) return;
    $("slojProstori").classList.remove("viden");
    $("gumbProstori").setAttribute("aria-expanded", "false");
    clearInterval(PR.zanka);
    clearInterval(PR.slikaZanka);
    PR.slikaZanka = 0;
    zapriMeni(false);
    PR.cakaSmer = 0;
    var prej = PR.prej;
    PR.prej = null;
    if (prej && prej.focus && document.contains(prej)) prej.focus(); else $("gumbProstori").focus();
  }
  function prostorNapaka(r, p) {
    var koda = String((r && r.koda) || ""), ime = prostorIme(p);
    if (koda === "ni_prostora") return t("prostorNiVec", { ime: ime });
    if (koda === "ni_naslova") return t("prostorNiNaslova", { ime: ime });
    if (koda === "ni_controla") return t("niControla");
    if (koda === "ni_nacina") return t("prostorNacinNi", { ime: ime });
    return sporociloProsnje(r, ime) || (r && r.message ? String(r.message) : t("oddaljeniNapaka"));
  }
  function prostorDodajNapravo() {
    zapriProstore();
    // Obstojeca pot: povezan racunalnik -> Control z QR kodo za novo napravo; sicer prijava (QR / 6-mestna koda).
    klic(S.povezava && S.povezava.stanje === "povezan" ? "novaNaprava" : "prijava").then(function (ok) {
      if (ok === false) obvesti(t("niControla"));
    }, function () { obvesti(t("niUspelo")); });
  }
  function prostorNamizje(p) {
    zapriProstore();
    if (p.ta) return;
    // Preklop namizja Cinnamona (wmctrl -s); Python preveri stevilko.
    klic("prostorNamizje", [p.st]).then(function (r) {
      if (!r || !r.ok) obvesti(t("niUspelo"));
    }, function () { obvesti(t("niUspelo")); });
  }
  function prostorNovoNamizje() {
    zapriProstore();
    klic("prostorNovoNamizje").then(function (r) {
      if (r && r.ok) obvesti(t("prostorNamizje", { n: r.st + 1 }));
      else obvesti(t(r && r.koda === "najvec" ? "prostorNamizjaNajvec" : "prostorNovoNamizjeNi"));
    }, function () { obvesti(t("prostorNovoNamizjeNi")); });
  }
  // Meni »+«: novo namizje tega racunalnika, nacini prikaza povezanih naprav (kar naprava zna) in nova naprava.
  function narisiMeni(fokus) {
    var v = $("prostoriMeniVsebina");
    if (!v) return;
    v.innerHTML = "";
    function gumb(besedilo, oznaka, ob) {
      var b = el("button", "gumb majhen", ubezi(besedilo));
      b.type = "button";
      b.setAttribute("data-meni", oznaka);
      b.addEventListener("click", ob);
      return b;
    }
    if (PR.namizja.length) {
      var vr = el("div", "prostori-meni-vrsta");
      vr.appendChild(el("b", "", ubezi(t("prostorNovoNamizjePod"))));
      var nb = gumb(t("prostorNovoNamizje"), "namizje", prostorNovoNamizje);
      if (PR.namizja.length >= PR.najvec) { nb.disabled = true; nb.title = t("prostorNamizjaNajvec"); }
      vr.appendChild(nb);
      v.appendChild(vr);
    }
    PR.seznam.filter(function (p) { return p.povezana && Array.isArray(p.nacini) && p.nacini.length; }).forEach(function (p) {
      var vr = el("div", "prostori-meni-vrsta");
      vr.appendChild(el("b", "", ubezi(prostorIme(p))));
      p.nacini.forEach(function (n) {
        var besedilo = n === "aplikacija" ? t("prostorEnaAplikacija") : t("prostorNacin_" + n);
        vr.appendChild(gumb(besedilo, n + ":" + p.id, function () {
          if (n === "aplikacija") prostorEnaAplikacija(p); else prostorIzberi(p, n);
        }));
      });
      v.appendChild(vr);
    });
    var dv = el("div", "prostori-meni-vrsta");
    dv.appendChild(el("b", "", ubezi(t("prostorDodajPod"))));
    dv.appendChild(gumb(t("prostorDodaj"), "dodaj", prostorDodajNapravo));
    v.appendChild(dv);
    if (fokus) { var prvi = v.querySelector("button:not([disabled])"); if (prvi) prvi.focus(); }
  }
  function odpriMeni() {
    PR.meni = true;
    $("prostoriMeni").hidden = false;
    narisiMeni(true);
    var plus = document.querySelector("#prostoriTrak .prostor.dodaj");
    if (plus) plus.setAttribute("aria-expanded", "true");
  }
  function zapriMeni(fokus) {
    if (!PR.meni) return;
    PR.meni = false;
    if ($("prostoriMeni")) $("prostoriMeni").hidden = true;
    var plus = document.querySelector("#prostoriTrak .prostor.dodaj");
    if (plus) { plus.setAttribute("aria-expanded", "false"); if (fokus) plus.focus(); }
  }
  // Super+Alt+levo/desno (tudi iz gledalca naprave, `od`): naslednji prostor v vrstnem redu ploscic - namizje ali
  // povezana naprava; naprave brez povezave preskoci. Na koncu ne skoci okrog (kot Cinnamon, workspace-cycle false).
  function prostorSosednji(smer, od) {
    if (EN_RAZDELEK) return;
    Promise.resolve(PR.nalozeno ? null : nalozProstore(false)).then(function () {
      var vse = prostoriPloscice().filter(function (p) { return !p.dodaj; }), i = -1;
      if (od) {
        var k = String(od).replace(/-(os|control)$/, "");
        vse.forEach(function (p, j) { if (i < 0 && !p.namizje && !p.ta && String(p.id).replace(/-(os|control)$/, "") === k) i = j; });
      }
      if (i < 0) vse.forEach(function (p, j) { if (i < 0 && p.ta) i = j; });
      if (i < 0) i = 0;
      for (var j = i + smer; j >= 0 && j < vse.length; j += smer) {
        var c = vse[j];
        if (c.namizje) { prostorNamizje(c); obvesti(prostorIme(c)); return; }
        if (c.ta) { zapriProstore(); return; }
        if (c.povezana) { prostorIzberi(c); return; }
      }
      obvesti(t(smer > 0 ? "prostorZadnji" : "prostorPrvi"));
    });
  }
  function prostorIzberi(p, prikaz) {
    if (p.namizje) { prostorNamizje(p); return; }
    if (p.ta) { zapriProstore(); return; }
    if (p.dodaj) { if (PR.meni) zapriMeni(true); else odpriMeni(); return; }
    if (!p.povezana) { PR.stanje = t("prostorBrezPovezave", { ime: prostorIme(p) }); $("prostoriStanje").textContent = PR.stanje; return; }
    if (PR.odpira) return;
    PR.odpira = p.id;
    PR.stanje = t("prostorOdpiram", { ime: prostorIme(p) });
    narisiProstore(true);
    klic("prostorOdpri", [p.id, prikaz || "zrcaljenje"]).then(function (r) {
      PR.odpira = "";
      if (!r || !r.ok) {
        PR.stanje = prostorNapaka(r, p);
        if (prostoriOdprto()) narisiProstore(true); else obvesti(PR.stanje);
        return;
      }
      PR.stanje = "";
      zapriProstore();
      // Android: na napravi se pokaze sistemska potrditev deljenja zaslona (zahteva jo za vsako sejo).
      obvesti(r.nacin === "zaslon" ? t("prostorPotrdi", { ime: prostorIme(p) }) : t("prostorOdpiram", { ime: prostorIme(p) }));
    }, function (e) {
      PR.odpira = "";
      PR.stanje = String(e || t("oddaljeniNapaka"));
      if (prostoriOdprto()) narisiProstore(true); else obvesti(PR.stanje);
    });
  }
  function prostorEnaAplikacija(p) {
    zapriProstore();
    pojdi("programi");
    // Programi naprave (S.naprave iz napraveSProgrami) - id je lahko sorodnik (x, x-os, x-control).
    var osnova = String(p.id).replace(/-(os|control)$/, "");
    function najdi() {
      return (S.naprave || []).find(function (x) { return x.id === p.id || String(x.id).replace(/-(os|control)$/, "") === osnova; });
    }
    function izberi(n) {
      S.naprava = n.id; S.skupina = "vse"; narisiPrograme();
      if (!S.programiNaprav[n.id] || S.programiNaprav[n.id].napaka === "prosnja") nalozProgrameNaprave(n.id);
    }
    var n = najdi();
    if (n) { izberi(n); return; }
    // Seznam naprav s programi se se ni nalozil (ali je zastarel): nalozi ga zdaj in nato izberi napravo; ce je
    // ni, uporabnik to izve (prej se je tiho odprl samo seznam programov tega racunalnika - pregled 25. 10. 2026).
    obvesti(t("prostorAplikacijeNalagam", { ime: prostorIme(p) }));
    Promise.resolve(nalozNaprave()).then(function () {
      var m = najdi();
      if (m) izberi(m); else obvesti(t("prostorAplikacijeNi", { ime: prostorIme(p) }));
    });
  }
  function poveziProstore() {
    var gumb = $("gumbProstori"), sloj = $("slojProstori");
    if (!gumb || !sloj) return;
    if (EN_RAZDELEK) { gumb.hidden = true; return; }   // Safeer Player in okna razdelkov: samo glavno okno
    gumb.setAttribute("aria-expanded", "false");
    gumb.addEventListener("click", function () { if (prostoriOdprto()) zapriProstore(); else odpriProstore(0); });
    $("prostoriZapri").addEventListener("click", zapriProstore);
    sloj.querySelector(".tancica").addEventListener("click", zapriProstore);
    // Tipke: v fazi zajema na oknu, da jih med odprtim preklopnikom ne dobi nic drugega (iskanje ob tipkanju, Esc zapre
    // vse sloje). Enter in presledek ostaneta gumbu v fokusu (privzeto dejanje ni preprečeno).
    window.addEventListener("keydown", function (e) {
      var superTab = e.key === "Tab" && (e.metaKey || (e.getModifierState && (e.getModifierState("Meta") || e.getModifierState("OS"))));
      if (superTab && !e.altKey && !e.ctrlKey) {     // brez mosta (predogled) ali ce Super pride do strani
        e.preventDefault(); e.stopImmediatePropagation();
        odpriProstore(e.shiftKey ? -1 : 1);
        return;
      }
      if (!prostoriOdprto()) return;
      var k = e.key;
      if (k === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); if (PR.meni) zapriMeni(true); else zapriProstore(); return; }
      // V meniju »+« puscice premikajo med njegovimi gumbi (Enter / presledek jih sprozita).
      if (PR.meni && $("prostoriMeni").contains(document.activeElement) && /^Arrow/.test(k)) {
        var mg = Array.prototype.filter.call($("prostoriMeni").querySelectorAll("button"), function (b) { return !b.disabled; });
        var mi = mg.indexOf(document.activeElement);
        e.preventDefault(); e.stopImmediatePropagation();
        if (mg.length) mg[(mi + (k === "ArrowRight" || k === "ArrowDown" ? 1 : mg.length - 1)) % mg.length].focus();
        return;
      }
      if (k === "ArrowRight" || k === "ArrowDown") { e.preventDefault(); premakniProstor(1); }
      else if (k === "ArrowLeft" || k === "ArrowUp") { e.preventDefault(); premakniProstor(-1); }
      else if (k === "Home") { e.preventDefault(); PR.izbran = 0; oznaciProstor(true); }
      else if (k === "End") { e.preventDefault(); PR.izbran = prostoriPloscice().length - 1; oznaciProstor(true); }
      else if (k === "Tab") {
        // Fokus ostane v preklopniku (aria-modal): izbrana ploscica, njen gumb »Samo ena aplikacija«, Zapri.
        var gumbi = Array.prototype.filter.call(sloj.querySelectorAll("button, input"), function (b) {
          return b.tabIndex >= 0 && !b.hidden && !b.disabled && b.offsetParent !== null;
        });
        var i = gumbi.indexOf(document.activeElement);
        e.preventDefault();
        if (gumbi.length) gumbi[(i + (e.shiftKey ? gumbi.length - 1 : 1)) % gumbi.length].focus();
      }
      e.stopImmediatePropagation();
    }, true);
    // Poteg s prstom (zaslon na dotik) in vodoraven poteg z dvema prstoma na sledilni ploscici (kolesce deltaX).
    var trak = $("prostoriTrak");
    trak.addEventListener("pointerdown", function (e) { if (e.pointerType !== "mouse") PR.poteg = { x: e.clientX, y: e.clientY }; });
    trak.addEventListener("pointerup", function (e) {
      var p = PR.poteg; PR.poteg = null;
      if (!p) return;
      var dx = e.clientX - p.x;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(e.clientY - p.y)) premakniProstor(dx < 0 ? 1 : -1);
    });
    trak.addEventListener("pointercancel", function () { PR.poteg = null; });
    // Neobvezno (privzeto izklopljeno): kazalec, potisnjen na zgornji rob okna, po 0,4 s odpre Prostore.
    $("prostoriRob").addEventListener("change", function () {
      PR.rob = !!this.checked;
      klic("prostoriRob", [PR.rob]).then(function (r) { if (r && typeof r.rob === "boolean") PR.rob = r.rob; });
    });
    klic("prostoriRob", [null]).then(function (r) { if (r && typeof r.rob === "boolean") PR.rob = r.rob; }, function () {});
    document.addEventListener("mousemove", function (e) {
      if (!PR.rob || prostoriOdprto() || e.clientY > 1) {
        if (PR.robCas) { clearTimeout(PR.robCas); PR.robCas = 0; }
        return;
      }
      if (!PR.robCas) PR.robCas = setTimeout(function () { PR.robCas = 0; if (PR.rob && !prostoriOdprto()) odpriProstore(0); }, 400);
    }, { passive: true });
    trak.addEventListener("wheel", function (e) {
      if (Math.abs(e.deltaX) < 20 || Math.abs(e.deltaX) < Math.abs(e.deltaY)) return;
      e.preventDefault();
      var zdaj = Date.now();
      if (zdaj - PR.kolo < 300) return;
      PR.kolo = zdaj;
      premakniProstor(e.deltaX > 0 ? 1 : -1);
    }, { passive: false });
  }

  window.safeerOsDogodek = function (vrsta, podatki) {
    katDogodek(vrsta, podatki);
    // Super+Tab (safeer_os._na_tipko): odpre Prostore ali izbere naslednji / prejsnji prostor.
    // Super+Alt+levo/desno (safeer_os._na_tipko ali gledalec naprave): sosednji prostor brez preklopnika.
    if (vrsta === "prostori" && podatki && (podatki.sosednji === 1 || podatki.sosednji === -1)) prostorSosednji(podatki.sosednji, podatki.od || "");
    else if (vrsta === "prostori") odpriProstore(podatki && podatki.smer < 0 ? -1 : 1);
    // Safeer Agent je bil nastavljen ali izklopljen (Nastavitve, lahko v drugem oknu): lupa in bliznjice takoj vedo.
    if (vrsta === "agent" && podatki) { S.agent = { na_voljo: !!podatki.na_voljo }; lupaUredi(); if ($("bliznjice")) narisiBliznjice(); }
    if (vrsta === "jezik" && podatki) uporabiJezik(podatki.jezik);
    // Vgrajeni kanali Sporocil: znacka neprebranih, nalozen, ime; vklop celotnih Sporocil.
    if (vrsta === "kanaliSporocil") vkPosodobi(podatki);
    if (vrsta === "kanalPreklici") vkPrekliciDodajanje(String(podatki || ""));
    if (vrsta === "kanaliKatalog" && $("slojKanal") && $("slojKanal").classList.contains("viden")) vkOsveziKatalog();
    if (vrsta === "sporocilaVklop") { if (S.zacetek) S.zacetek.sporocila = podatki !== false; uskladiVklopSporocil(); narisiNastavitveDelov(); }
    if (vrsta === "priponkaNapredek" && podatki) napredekPriponke(podatki);
    if (vrsta === "priponkaShranjena" && podatki) priponkaShranjena(podatki);
    if (vrsta === "sporocilaSlikeOd" && Array.isArray(podatki)) {
      S.slikeOd = podatki;
      if (S.sporocilaOseba && S.sporocilaAktivni) narisiPano(S.sporocilaOseba, S.sporocilaAktivni, S.sporocilaZadnjaVsebina);
    }
    // Drugo okno (glavno ali Safeer Player) je skrilo ali vrnilo predmet menija; novi samodejni seznami.
    if (vrsta === "mediaSkrito") nastaviSkrito(podatki, false);
    if (vrsta === "mediaSamodejniOsvezeni") naloziSamodejne();
    if (vrsta === "stanje") narisiStanje(podatki);
    // Scit je spremenjen drugje (drugo okno, pult, Splet): ta stran pokaze isto stanje takoj.
    if (vrsta === "scit" && podatki && !scitZaposleno) { scitStanje = podatki; if ($("blokScit")) narisiScit(); }
    if (vrsta === "okna") narisiOkna(podatki);
    if (vrsta === "predvajalnik") osveziPredvajalnik(podatki);
    if (vrsta === "medijskaKnjiznica") naloziMedije();
    // Program namescen ali odstranjen (Safeer OS spremlja mape z zaganjalniki): seznam preberemo znova.
    if (vrsta === "programi") nalozPrograme();
    // Prikazana mapa ali seznam nedavnih se je spremenil zunaj Safeer OS; nosilec priklopljen ali odklopljen.
    if (vrsta === "datoteke" && podatki) datotekeSpremenjene(podatki.pot);
    if (vrsta === "nosilci" && S.razdelek === "datoteke") narisiMape();
    if (vrsta === "medijskoOsvezevanje") {
      S.mediaOsvezuje = !!podatki;
      $("mediaOsvezi").disabled = S.mediaOsvezuje || !S.mediaMape.length;
    }
    if (vrsta === "medijskaNapaka") obvesti(t("niUspelo"));
    // Vsebine brez peskovnika ne odpremo (sistem ga ne dovoli): povemo zakaj, lupina tece naprej. Cas si zapomnimo,
    // da splosno obvestilo o napaki tega pojasnila ne prekrije.
    if (vrsta === "spletBrezPeskovnika" || vrsta === "medijBrezPeskovnika") { brezPeskovnikaOb = Date.now(); obvesti(t(vrsta)); }
    if (vrsta === "posodobitev") pokaziPosodobitevDoma(podatki);
    // Magnet z druge naprave ali iz brskalnika prevzame glavno okno (kot prej); Safeer Player ga ne odpre se enkrat.
    if (vrsta === "stremioDodatek" && PREDVAJALNIK) pokaziStremioDodatek(podatki && podatki.url);
    if (vrsta === "magnet" && !PREDVAJALNIK) odpriMagnet(podatki && podatki.uri, podatki && podatki.samodejno === true);
    // Film iz torrenta (dodatek): med branjem torrenta in prenosom zacetka uporabnik vidi, da se nekaj dogaja.
    if (vrsta === "mediaTorrent") obvesti(t("mediaTorrentPripravljam", { ime: (podatki && podatki.naslov) || "" }));
    if (vrsta === "mediaMotor" && podatki) motorNapredek(podatki);
    if (vrsta === "mediaJellyfinZagon") jfNapredekZagona(podatki);
    if (vrsta === "magnetProgram" && S.magnet.gumbPrograma)
      S.magnet.gumbPrograma.textContent = t("magnetProgramPrenasam", { odstotek: Math.floor(100 * podatki.n / (podatki.vse || 1)) });
    if (vrsta === "magnetDeljen") {
      if (!podatki || !podatki.ok) { magnetSporocilo(magnetNapaka(podatki && podatki.koda)); }
      else {
        var v = $("magnetVsebina"); v.innerHTML = "";
        v.appendChild(el("p", "", ubezi(t("magnetDeljeno", { ime: podatki.ime }))));
        v.appendChild(el("p", "magnet-povezava", ubezi(podatki.uri)));
        var d = el("div", "magnet-dejanja"); magnetPosiljanje(d, function () { return podatki.uri; }); v.appendChild(d);
        magnetOsveziPrenose();
      }
    }
    // Niti kanalov so v bazo zapisale novo (sporocilo, oznake, stanje kanala): seznam takoj, ne ob 30-s osvezitvi.
    if (vrsta === "sporocila") sporocilaSpremenjena();
    // »pojdi« in »fokus« sta za glavno okno; Safeer Player in okna razdelkov dobijo svoj ukaz neposredno
    // (safeer_os.py _odpri_predvajalnik, _odpri_okno_razdelka).
    if (EN_RAZDELEK) return;
    if (vrsta === "pojdi") window.safeerOsPojdi(podatki);
    if (vrsta === "fokus") {
      osveziOkna();
      osveziStanje();
      osveziPovezavo();
      narisiNedavneDomov();
    }
  };

  // ------------------------------------------------------------------ zacetek
  function isciPriOsebi(niz) {
    var oseba = S.sporocilaOseba, cilj = $("panoZadetki"); if (!oseba) return;
    niz = String(niz || "").trim(); cilj.innerHTML = "";
    if (niz.length < 2) return;
    klic("sporocilaIsciPri", [oseba.id, niz]).then(function (zadetki) {
      if (!S.sporocilaOseba || S.sporocilaOseba.id !== oseba.id || $("panoIskanjeVnos").value.trim() !== niz) return;
      cilj.innerHTML = "";
      if (!zadetki || !zadetki.length) { cilj.appendChild(el("p", "drobno", ubezi(t("panoNiZadetkov")))); return; }
      zadetki.forEach(function (z) {
        var b = el("button", "pano-zadetek"); b.type = "button";
        b.appendChild(el("small", "", ubezi(((z.kanal || {}).ime || "") + " · " + kratekCas(z.cas))));
        b.appendChild(el("span", "", ubezi(z.izsek || "")));
        b.addEventListener("click", function () {
          var pog = null;
          S.sporocilaSkupine.forEach(function (s) { (s.pogovori || []).forEach(function (p) { if (p.id === z.pogovor_id && p.kanal_id === z.kanal_id) pog = p; }); });
          if (pog) { S.sporocilaOznaciId = z.id; odpriPogovor(oseba, pog); }
        });
        cilj.appendChild(b);
      });
    }).catch(function () {});
  }
  function poveziDogodke() {
    poveziKatalog();
    document.querySelectorAll("#meni button").forEach(function (b) {
      b.addEventListener("click", function () { pojdi(b.getAttribute("data-razdelek")); });
    });
    document.querySelectorAll("[data-pojdi]").forEach(function (b) {
      b.addEventListener("click", function () { pojdi(b.getAttribute("data-pojdi")); });
    });
    $("sporocilaDodaj").addEventListener("click", odpriCarovnikKanala);
    $("sporocilaPisi").addEventListener("click", odpriPisiNapravi);
    $("sporocilaNovo").addEventListener("click", function () { odpriNovo(null); });
    $("obrazecNovo").addEventListener("submit", posljiNovo);
    $("sporocilaPrilozi").addEventListener("click", function () { izberiPriloge("odgovor"); });
    $("novoPrilozi").addEventListener("click", function () { izberiPriloge("novo"); });
    // Datoteke se prilozijo, ce jih uporabnik spusti na vnos ali kamorkoli na odprt pogovor (kot v Gmailu).
    sprejemPrilog($("sporocilaVnos"), "odgovor", function () { return !!S.sporocilaAktivni && !$("sporocilaPrilozi").hidden; });
    sprejemPrilog($("sporocilaVsebina"), "odgovor", function () { return !!S.sporocilaAktivni && !$("sporocilaPrilozi").hidden; });
    sprejemPrilog($("obrazecNovo"), "novo", function () { return true; });
    $("nevarnoPreklici").addEventListener("click", function () { $("slojNevarno").classList.remove("viden"); S.nevarnoNadaljuj = null; });
    $("nevarnoNadaljuj").addEventListener("click", function () {
      var nadaljuj = S.nevarnoNadaljuj; S.nevarnoNadaljuj = null; $("slojNevarno").classList.remove("viden");
      if (nadaljuj) nadaljuj();
    });
    $("novoPreklici").addEventListener("click", zapriSloje);
    $("novoOsnutek").addEventListener("click", shraniNovoKotOsnutek);
    $("novoOdstrani").addEventListener("click", function () {
      klic("sporocilaOdstraniOsnutek", [S.novoOsnutek]).then(function (o) { S.osnutki = o || []; zapriSloje(); narisiSporocila(); })
        .catch(function (e) { obvesti(typeof e === "string" && e ? e : t("niUspelo")); });
    });
    $("pisiPreklici").addEventListener("click", zapriSloje);
    $("kanalPreklici").addEventListener("click", zapriSloje);
    $("kanalApiProtokol").querySelectorAll("button").forEach(function (b) {
      b.addEventListener("click", function () {
        $("kanalProtokol").value = b.getAttribute("data-protokol");
        $("kanalApiProtokol").querySelectorAll("button").forEach(function (x) { x.classList.toggle("izbran", x === b); });
        preklopiApiProtokol();
      });
    });
    $("kanalStranGesla").addEventListener("click", function () {
      var url = this.getAttribute("data-url"); if (url) odpriVSpletu(url, true);
    });
    $("kanalVrstaIzbira").querySelectorAll("button").forEach(function (b) {
      b.addEventListener("click", function () {
        $("kanalVrsta").value = b.getAttribute("data-vrsta");
        $("kanalVrstaIzbira").querySelectorAll("button").forEach(function (x) { x.classList.toggle("izbran", x === b); });
        preklopiKanalPolja();
      });
    });
    $("kanalZamenjaj").addEventListener("click", function () { $("kanalPonudnik").value = ""; preklopiKanalPolja(); });
    $("kanalNapredno").addEventListener("click", function () { $("kanalStrezniki").hidden = false; $("kanalNapredno").hidden = true; });
    ["kanalImap", "kanalSmtp"].forEach(function (id) { $(id).addEventListener("input", function () { this.setAttribute("data-rocno", "1"); }); });
    $("kanalNaslov").addEventListener("blur", function () {
      var naslov = this.value.trim(); if (naslov.indexOf("@") < 1 || $("kanalPonudnik").value !== "drug") return;
      // Drug ponudnik: ce je domena znanega ponudnika, ga izberemo; sicer predlagamo imap./smtp.domena.
      var znani = (kanalPonudnikiPodatki && kanalPonudnikiPodatki.ponudniki || []).filter(function (p) { return (p.domene || []).indexOf(naslov.split("@")[1].toLowerCase()) >= 0; })[0];
      if (znani) { izberiPonudnika(znani); return; }
      klic("sporocilaStreznik", [naslov]).then(function (p) {
        if (!$("kanalImap").getAttribute("data-rocno")) $("kanalImap").value = p.imap || "";
        if (!$("kanalSmtp").getAttribute("data-rocno")) $("kanalSmtp").value = p.smtp || "";
      });
    });
    $("kanalUrediPreklici").addEventListener("click", zapriSloje);
    $("kanalUrediVklop").addEventListener("click", function () {
      var k = S.urejaniKanal, b = $("kanalUrediVklop"); if (!k) return;
      var nov = b.getAttribute("aria-checked") !== "true";
      b.setAttribute("aria-checked", nov ? "true" : "false");
      klic("sporocilaKanalVklop", [k.id, nov]).then(function (p) {
        k.vklopljen = nov; S.sporocilaSkupine = p.skupine || []; S.sporocilaKanali = p.kanali || []; narisiSporocila();
      }).catch(function () { b.setAttribute("aria-checked", nov ? "false" : "true"); obvesti(t("niUspelo")); });
    });
    $("kanalOdstrani").addEventListener("click", function () {
      var k = S.urejaniKanal; if (!k) return;
      if ($("kanalOdstrani").getAttribute("data-potrdi") !== k.id) {
        $("kanalOdstrani").setAttribute("data-potrdi", k.id); $("kanalOdstrani").textContent = t("odstraniKanalPotrdi"); return;
      }
      $("kanalOdstrani").removeAttribute("data-potrdi"); $("kanalOdstrani").textContent = t("odstraniKanal");
      klic("sporocilaOdstrani", [k.id]).then(function () { zapriSloje(); S.sporocilaAktivni = null; naloziSporocila(); });
    });
    $("obrazecKanalUredi").addEventListener("submit", function (e) {
      e.preventDefault(); var k = S.urejaniKanal, g = $("kanalUrediGeslo").value;
      if (!k || !g) return;
      klic("sporocilaSkrivnost", [k.id, g]).then(function (p) {
        $("kanalUrediGeslo").value = ""; zapriSloje();
        S.sporocilaSkupine = p.skupine || []; S.sporocilaKanali = p.kanali || []; narisiSporocila();
      }).catch(function (napaka) { obvesti(String(napaka || t("niUspelo"))); });
    });
    $("sporocilaBesedilo").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); $("sporocilaVnos").requestSubmit(); }
    });
    // Sporocila: desni klik ali tipka Meni odpre meni mehurcka; Ctrl+C brez izbora kopira celo sporocilo.
    $("sporocilaVsebina").addEventListener("contextmenu", function (e) {
      var m = e.target && e.target.closest ? e.target.closest(".mehurcek") : null;
      if (!m) return;
      e.preventDefault();
      // Tipka Meni je meni ze odprla (keydown spodaj): istega dogodka ne obdelamo dvakrat.
      if (Date.now() - meniSporocilaOb < 200 && $("sporocilaMeni")._za === m && !$("sporocilaMeni").hidden) return;
      pokaziMeniSporocila(m, e.clientX, e.clientY, false);
    });
    $("sporocilaVsebina").addEventListener("keydown", function (e) {
      var m = e.target && e.target.closest ? e.target.closest(".mehurcek") : null;
      if (!m) return;
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && (e.key === "c" || e.key === "C")) {
        // Z izborom kopira brskalnik sam (dogodek copy spodaj); brez izbora gre v odlozisce celo sporocilo.
        if (!izbranoVSporocilih()) { e.preventDefault(); kopirajBesedilo(m._besedilo || ""); }
      } else if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) {
        e.preventDefault();
        var r = m.getBoundingClientRect();
        pokaziMeniSporocila(m, r.left + 16, r.bottom - 6, true);
      } else if ((e.key === "ArrowUp" || e.key === "ArrowDown") && !e.ctrlKey && !e.altKey && !e.metaKey && !e.shiftKey) {
        var sosed = e.key === "ArrowUp" ? m.previousElementSibling : m.nextElementSibling;
        if (sosed) { e.preventDefault(); fokusNaMehurcek($("sporocilaVsebina"), sosed); }
      }
    });
    $("sporocilaVsebina").addEventListener("focusout", function (e) {
      if (e.target && e.target.classList) e.target.classList.remove("fokus-tipke");
    });
    $("sporocilaVsebina").addEventListener("scroll", obPomikuSporocil);
    $("sporocilaMeni").addEventListener("keydown", function (e) {
      if (e.key === "Tab") { zapriMeniSporocila(); return; }
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      var gumbi = Array.prototype.slice.call(this.querySelectorAll("button")), i = gumbi.indexOf(document.activeElement);
      e.preventDefault(); e.stopPropagation();
      if (!gumbi.length) return;
      var dol = e.key === "ArrowDown";
      gumbi[i < 0 ? (dol ? 0 : gumbi.length - 1) : (i + (dol ? 1 : gumbi.length - 1)) % gumbi.length].focus();
    });
    document.addEventListener("copy", function () { if (izbranoVSporocilih()) obvesti(t("sporKopirano")); });
    // Klik drugam, Esc, drugo okno ali sprememba velikosti zapre meni mehurcka.
    document.addEventListener("mousedown", function (e) {
      var cilj = e.target && e.target.closest ? e.target : null;
      if (cilj && cilj.closest("#sporocilaMeni")) return;
      zapriMeniSporocila();
      // Desni klik na sporocilo ne sme podreti izbora cez vec sporocil: pritisk bi fokus prestavil na kliknjeni mehurcek,
      // brskalnik pa ob tem pocisti izbor, ki se ne zacne v njem. Meni (contextmenu) pride kot prej.
      if (e.button === 2 && cilj && cilj.closest(".mehurcek") && izbranoVSporocilih()) e.preventDefault();
    }, true);
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      var za = $("sporocilaMeni")._za;
      if (zapriMeniSporocila()) { e.preventDefault(); e.stopImmediatePropagation(); fokusNaMehurcek(null, za); }
    }, true);
    window.addEventListener("blur", zapriMeniSporocila);
    window.addEventListener("resize", zapriMeniSporocila);
    // Gumbi kanalov v filtru se dodajajo sproti (narisiFiltreKanalov): en poslusalec za vse.
    $("sporocilaFiltri").addEventListener("click", function (e) {
      var b = e.target && e.target.closest ? e.target.closest("button") : null; if (!b) return;
      izberiFilterKanala(b.getAttribute("data-kanal-vrsta") || "");
    });
    $("panoIskanjeVnos").addEventListener("input", function () { isciPriOsebi(this.value); });
    $("sporocilaSeznam").addEventListener("keydown", tipkeSeznama);
    $("sporocilaMape").querySelectorAll("button").forEach(function (b) {
      b.addEventListener("click", function () { izberiMapo(b.getAttribute("data-mapa") || "vse"); });
    });
    $("sporocilaIskanje").addEventListener("input", function () { S.sporocilaNiz = this.value; narisiSporocila(); });
    // Plosca filtra: gumb, Esc (fokus nazaj na gumb), klik drugam.
    $("sporocilaFilterGumb").addEventListener("click", function () { odpriFilter(); });
    $("sporocilaPocisti").addEventListener("click", function () {
      S.sporocilaFilter = ""; izberiMapo("vse"); $("sporocilaFilterGumb").focus(); odpriFilter(false);
    });
    // Esc zapre samo plosco filtra (ne razdelka - »Esc Domov«), tudi ce fokus ni vec v njej; fokus nazaj na gumb.
    window.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && odpriFilter(false)) { e.preventDefault(); e.stopImmediatePropagation(); $("sporocilaFilterGumb").focus(); }
    }, true);
    document.addEventListener("mousedown", function (e) {
      var c = e.target && e.target.closest ? e.target : null;
      if (c && (c.closest("#sporocilaFilterPlosca") || c.closest("#sporocilaFilterGumb"))) return;
      odpriFilter(false);
    });
    $("sporocilaFilterPlosca").addEventListener("focusout", function (e) {
      var kam = e.relatedTarget;
      if (kam && !this.contains(kam) && kam !== $("sporocilaFilterGumb")) odpriFilter(false);
    });
    // Seznam pogovorov: puscici gor/dol, Home/End in tipke dejanj obravnava tipkeSeznama (en poslusalec - dva sta
    // vrstico preskocila dvakrat).
    $("sporocilaNazaj").addEventListener("click", nazajNaSeznam);
    $("vgrajenKanalSeznam").addEventListener("click", nazajNaSeznam);
    $("sporocilaBesedilo").addEventListener("input", posodobiPoslji);
    // Pano z osebo: odprt ali zaprt ostane, kot ga je uporabnik pustil (samo ta racunalnik; brez shrambe privzeto odprt).
    S.sporocilaPanoOdprt = true;
    try { S.sporocilaPanoOdprt = localStorage.getItem("safeer.sporocilaPano") !== "0"; } catch (e) {}
    $("sporocilaPano").addEventListener("click", function () {
      S.sporocilaPanoOdprt = $("sporocilaPanoVsebina").hidden;
      $("sporocilaPanoVsebina").hidden = !S.sporocilaPanoOdprt;
      this.setAttribute("aria-pressed", S.sporocilaPanoOdprt ? "true" : "false");
      try { localStorage.setItem("safeer.sporocilaPano", S.sporocilaPanoOdprt ? "1" : "0"); } catch (e) {}
    });
    $("panoPreimenuj").addEventListener("click", function () { odpriOsebaSloj("preimenuj"); });
    $("panoZdruzi").addEventListener("click", function () { odpriOsebaSloj("zdruzi"); });
    $("osebaPreklici").addEventListener("click", zapriSloje);
    $("obrazecOseba").addEventListener("submit", function (e) {
      e.preventDefault(); var o = S.sporocilaOseba; if (!o) return;
      var klicMet = S.osebaNacin === "preimenuj" ? klic("sporocilaPreimenuj", [o.id, $("osebaIme").value.trim()]) : klic("sporocilaZdruzi", [o.id, $("osebaIzbira").value]);
      klicMet.then(function (p) { zapriSloje(); posodobiSeznamIzOdgovora(p); }).catch(function (err) { obvesti(typeof err === "string" && err ? err : t("niUspelo")); });
    });
    $("panoOznakaObrazec").addEventListener("submit", function (e) {
      e.preventDefault(); var a = S.sporocilaAktivni, v = $("panoOznakaVnos").value.trim(); if (!a || !v) return;
      $("panoOznakaVnos").value = ""; shraniOznake(a, (a.oznake || []).concat([v]));
    });
    $("obrazecKanal").addEventListener("submit", function (e) {
      e.preventDefault(); var email = $("kanalVrsta").value === "email";
      if ($("kanalVrsta").value === "aplikacije") return;
      if (email && $("kanalPonudnik").value === "outlook") { $("kanalNapaka").textContent = t("navOauth"); $("kanalNapaka").hidden = false; return; }
      function gostitelj(v, privzeto) { var t2 = String(v || "").trim(), i = t2.lastIndexOf(":"); var vr = i > 0 ? parseInt(t2.slice(i + 1), 10) : NaN; return isNaN(vr) ? [t2, privzeto] : [t2.slice(0, i), vr]; }
      var gi = gostitelj($("kanalImap").value, 993), gs = gostitelj($("kanalSmtp").value, 465);
      var p = email ? { vrsta:"email", naslov:$("kanalNaslov").value, imap:gi[0], imap_vrata:gi[1],
        smtp:gs[0], smtp_vrata:gs[1], geslo:$("kanalGeslo").value, ponudnik:$("kanalPonudnik").value } :
        $("kanalVrsta").value === "api" ? { vrsta:$("kanalProtokol").value, streznik:$("kanalApiStreznik").value, zeton:$("kanalApiZeton").value, ime:$("kanalApiIme").value } :
        { vrsta:"chatwoot", url:$("kanalUrl").value, account_id:Number($("kanalRacun").value), zeton:$("kanalZeton").value };
      var gumb = $("kanalPovezi"); gumb.disabled = true; gumb.textContent = t("povezujem");
      $("kanalNapaka").hidden = true;
      klic("sporocilaDodaj", [p]).then(function () {
        gumb.disabled = false; gumb.textContent = t("povezi");
        $("kanalGeslo").value = ""; $("kanalZeton").value = ""; $("kanalApiZeton").value = ""; zapriSloje(); naloziSporocila();
        setTimeout(naloziSporocila, 4000);
      }).catch(function (napaka) {
        gumb.disabled = false; gumb.textContent = t("povezi");
        $("kanalNapaka").textContent = String(napaka || t("niUspelo")); $("kanalNapaka").hidden = false;
      });
    });
    $("sporocilaVnos").addEventListener("submit", function (e) {
      e.preventDefault(); var p = S.sporocilaAktivni, besedilo = $("sporocilaBesedilo").value.trim();
      var priloge = S.priloge.odgovor.map(function (x) { return x.pot; });
      if (!p || (!besedilo && !priloge.length)) return;
      if (prilogePrevelike("odgovor")) { obvesti(t("priloge_prevelike")); return; }
      var gumbP = $("sporocilaVnos").querySelector('button[type="submit"]'); gumbP.disabled = true;
      klic("sporocilaPoslji", [p.kanal_id, p.id, besedilo, priloge]).then(function (r) {
        $("sporocilaBesedilo").value = ""; S.priloge.odgovor = []; narisiPriloge("odgovor"); posodobiPoslji();
        // Ista oseba (z id): pano, povezani viri in izbira kanala ostanejo (prej je bila oseba samo ime iz naslova).
        odpriPogovor(S.sporocilaOseba && S.sporocilaAktivni === p ? S.sporocilaOseba : { ime: $("sporocilaNaslov").textContent }, p);
        naloziSporocila();          // seznam pokaze zadnje sporocilo takoj, ne sele ob naslednji osvezitvi
        if (r && r.caka) obvesti(t(p.kanal_id === "safeer-link" ? "klepetCaka" : "sporCakaObvestilo"));
      }).catch(function (e) { posodobiPoslji(); obvesti(napakaSporocil(e)); });
    });
    $("kBrskalnik").addEventListener("click", function () {
      // Safeer Browser je jedro OS: vedno se odpre v tem oknu, tudi ce je namescen njegov
      // samostojni .desktop vnos.
      klic("splet", [""]);
    });
    $("gumbControl").addEventListener("click", function () {
      obvesti(t("odpiram", { ime: "Safeer Control" }));
      // Povezan racunalnik: Control z napravami; sicer prijavno okno (QR / koda / brez povezave).
      klic(S.povezava.stanje === "povezan" ? "control" : "prijava");
    });
    $("gumbOdjava").addEventListener("click", function () {
      if (!odjavaPotrjujem) {
        odjavaPotrjujem = true;
        clearTimeout(odjavaCas);
        odjavaCas = setTimeout(function () { odjavaPotrjujem = false; narisiPovezavo(); }, 5000);
        narisiPovezavo();
        return;
      }
      odjavaPotrjujem = false;
      klic("odjava").then(function (ok) {
        obvesti(t(ok ? "odjavljen" : "niUspelo"));
        setTimeout(osveziPovezavo, 2500);
        setTimeout(osveziPovezavo, 6000);
      });
    });
    $("domControl").addEventListener("click", function () { $("gumbControl").click(); });
    $("gumbStanje").addEventListener("click", function () {
      if ($("slojHitro").classList.contains("viden")) zapriSloje(); else odpriHitro();
    });
    $("gumbNapajanje").addEventListener("click", function () {
      if ($("slojNapajanje").classList.contains("viden")) zapriSloje(); else odpriNapajanje();
    });
    $("stikaloCelozaslonsko").addEventListener("click", function () {
      var b = $("stikaloCelozaslonsko"), nov = b.getAttribute("aria-checked") !== "true";
      b.setAttribute("aria-checked", nov ? "true" : "false");
      if (S.zacetek) S.zacetek.celozaslonsko = nov;
      klic("celozaslonsko", [nov]);
    });
    $("gumbNamizje").addEventListener("click", function () { klic("namizje"); });
    $("stikaloSamozagon").addEventListener("click", function () {
      var b = $("stikaloSamozagon"), nov = b.getAttribute("aria-checked") !== "true";
      b.setAttribute("aria-checked", nov ? "true" : "false");
      klic("samozagon", [nov]).then(function (zdaj) {
        if (S.zacetek) S.zacetek.samozagon = !!zdaj;
        b.setAttribute("aria-checked", zdaj ? "true" : "false");
      });
    });
    $("stikaloOdVklopa").addEventListener("click", function () {
      // Spremembo naredi sistem po skrbniskem geslu (pkexec) in traja do minute: stikalo pokaze, kar je res obveljalo.
      var b = $("stikaloOdVklopa");
      if (b.getAttribute("aria-busy") === "true") return;
      var nov = b.getAttribute("aria-checked") !== "true";
      b.setAttribute("aria-busy", "true");
      klic("odVklopa", [nov]).then(function (r) {
        b.removeAttribute("aria-busy");
        if (S.zacetek && r) S.zacetek.odVklopa = r;
        b.setAttribute("aria-checked", r && r.vklopljeno ? "true" : "false");
      }).catch(function () { b.removeAttribute("aria-busy"); });
    });
    $("gumbPosodobi").addEventListener("click", posodobi);
    $("gumbFlatpak").addEventListener("click", flatpakPreklop);
    $("stikaloBeta").addEventListener("click", preklopiBeto);
    $("domPosodobitevGumb").addEventListener("click", naPosodobitve);
    $("stikaloPredaja").addEventListener("click", function () {
      // "Predvajanje za druge naprave": Nadaljuj z druge naprave / Pošlji na napravo proti temu računalniku (nastavitev Controla).
      var b = $("stikaloPredaja"), nov = b.getAttribute("aria-checked") !== "true";
      b.setAttribute("aria-checked", nov ? "true" : "false");
      if (S.povezava) S.povezava.predajanje = nov;
      klic("predajanje", [nov]).then(function (zdaj) { b.setAttribute("aria-checked", zdaj ? "true" : "false"); }).catch(function () {});
    });
    $("stikaloZaupaj").addEventListener("click", function () {
      var b = $("stikaloZaupaj"), nov = b.getAttribute("aria-checked") !== "true";
      S.povezava.zaupana = nov;
      narisiPovezavo();
      klic("zaupanje", [nov]).then(function () { setTimeout(osveziPovezavo, 600); });
    });
    $("gumbNazajVMint").addEventListener("click", odpriMint);
    $("stikaloWifiOmrezje").addEventListener("click", function () {
      var b = $("stikaloWifiOmrezje"), nov = b.getAttribute("aria-checked") !== "true";
      b.setAttribute("aria-checked", nov ? "true" : "false");
      klic("wifi", [nov]).then(function () { setTimeout(function () { nalozOmrezje(true); }, 1500); });
    });
    $("gumbOmrezjeOsvezi").addEventListener("click", function () { nalozOmrezje(true); });
    $("gumbInternetPreizkus").addEventListener("click", internetPreizkus);
    $("gumbOmrezjeNazaj").addEventListener("click", function () { pojdi("nastavitve"); });
    $("gumbOmrezjeNapredno").addEventListener("click", function () {
      obvesti(t("odpiram", { ime: t("napredno") }));
      klic("nastavitve", ["omrezje"]);
    });
    $("stanjeOmrezje").addEventListener("click", function (e) { e.stopPropagation(); zapriSloje(); pojdi("omrezje"); });
    $("stanjeZvok").addEventListener("click", function (e) { e.stopPropagation(); zapriSloje(); pojdi("zvok"); });
    $("stanjeZvok").addEventListener("contextmenu", function (e) { e.preventDefault(); e.stopPropagation(); zapriSloje(); pojdi("zvok"); });
    $("gumbZvokNazaj").addEventListener("click", function () { pojdi("nastavitve"); });
    $("gumbNedavnePocistiDomov").addEventListener("click", pocistiNedavne);
    $("spletIskalnik").addEventListener("submit", function (e) {
      e.preventDefault();
      var vrednost = $("spletVnos").value.trim();
      if (!vrednost) return;
      var naslov = /^https?:\/\//i.test(vrednost) ? vrednost : normalizirajNaslov(vrednost);
      if (naslov) odpriSplet(naslov); else klic("iskanjeSplet", [vrednost]).catch(function () { obvesti(t("niUspelo")); });
    });
    $("zapisekNov").addEventListener("click", function () {
      Z.iskano = ""; $("zapiskiIskanje").value = "";
      klic("zapisekShrani", ["", t("zapisekNovNaslov"), "", null]).then(function (z) {
        odpriZapisek(z.id); setTimeout(function () { $("zapisekNaslov").focus(); $("zapisekNaslov").select(); }, 100);
      });
    });
    $("zapiskiIskanje").addEventListener("input", function () { Z.iskano = this.value; naloziZapiske(); });
    $("zapisekNaslov").addEventListener("input", shraniZapisekKmalu);
    $("zapisekNaslov").addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); $("zapisekBesedilo").focus(); } });
    $("zapisekBesedilo").addEventListener("input", function () { shraniZapisekKmalu(); ponudiOmembe(); });
    $("zapisekBesedilo").addEventListener("blur", function () { setTimeout(zapriOmembe, 150); });
    $("zapisekBesedilo").addEventListener("keydown", function (e) {
      if ($("zapisekOmembeOkno").hidden || !Z.omembe.length) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault(); Z.izbranaOmemba = (Z.izbranaOmemba + (e.key === "ArrowDown" ? 1 : Z.omembe.length - 1)) % Z.omembe.length; narisiOmembe();
      } else if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); vstaviOmembo(Z.omembe[Z.izbranaOmemba]); }
      else if (e.key === "Escape") { e.preventDefault(); zapriOmembe(); }
    });
    $("zapisekPogled").addEventListener("click", function () {
      Z.pogled = !Z.pogled; $("zapisekBesedilo").hidden = Z.pogled; $("zapisekPrikaz").hidden = !Z.pogled;
      $("zapisekPogled").textContent = t(Z.pogled ? "zapisekUredi" : "zapisekPogled"); if (Z.pogled) narisiPogledZapiska();
    });
    $("zapisekPripni").addEventListener("click", function () {
      if (!Z.aktivni) return;
      var novo = !Z.aktivni.pripet;
      klic("zapisekShrani", [Z.aktivni.id, $("zapisekNaslov").value, $("zapisekBesedilo").value, novo]).then(function () {
        Z.aktivni.pripet = novo; $("zapisekPripni").textContent = t(novo ? "zapisekOdpni" : "zapisekPripni"); naloziZapiske();
      });
    });
    $("zapisekIzbrisi").addEventListener("click", function () {
      if (!Z.aktivni) return;
      if (Date.now() - Z.izbrisPotrdi > 4000) {
        Z.izbrisPotrdi = Date.now(); $("zapisekIzbrisi").textContent = t("zapisekIzbrisiPotrdi");
        setTimeout(function () { $("zapisekIzbrisi").textContent = t("zapisekIzbrisi"); }, 4000); return;
      }
      klic("zapisekIzbrisi", [Z.aktivni.id]).then(function () {
        Z.aktivni = null; Z.izbrisPotrdi = 0; $("zapisekIzbrisi").textContent = t("zapisekIzbrisi");
        $("zapisekUrejevalnik").hidden = true; naloziZapiske();
      });
    });
    $("gumbZvokNapredno").addEventListener("click", function () {
      obvesti(t("odpiram", { ime: t("napredno") }));
      klic("nastavitve", ["sound"]);
    });
    $("mintPreklici").addEventListener("click", zapriSloje);
    $("gumbVodnik").addEventListener("click", odpriVodnik);
    $("gumbOdpriScit").addEventListener("click", function () { pojdi("scit"); });
    $("vodnikNaprej").addEventListener("click", function () { korakVodnika(1); });
    $("vodnikPreskoci").addEventListener("click", function () { korakVodnika(1); });
    $("vodnikNazaj").addEventListener("click", function () { korakVodnika(-1); });
    $("vodnikPreskociVse").addEventListener("click", zapriVodnik);
    $("vrnitevDa").addEventListener("click", function () { odgovoriVrnitev(true); });
    $("vrnitevNe").addEventListener("click", function () { odgovoriVrnitev(false); });
    // Tipkovnica in daljinec: puscice med gumbi vodnika (v polju in izbiri ostanejo polju), Escape preskoci vodnik.
    $("slojVodnik").addEventListener("keydown", function (e) {
      if (e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); zapriVodnik(); return; }
      if (e.defaultPrevented || ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].indexOf(e.key) < 0) return;
      if (e.target && /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
      var gumbi = Array.prototype.filter.call(this.querySelectorAll(".plosca button, .plosca select, .plosca input"),
        function (x) { return !x.hidden && !x.disabled && x.offsetParent !== null; });
      if (!gumbi.length) return;
      e.preventDefault();
      var i = gumbi.indexOf(document.activeElement), naprej = e.key === "ArrowRight" || e.key === "ArrowDown";
      gumbi[i < 0 ? 0 : (i + (naprej ? 1 : gumbi.length - 1)) % gumbi.length].focus();
    });
    $("mintSamoTokrat").addEventListener("click", function () { klic("nazajVMint", [false]); });
    $("mintZaStalno").addEventListener("click", function () { klic("nazajVMint", [true]); });
    document.querySelectorAll(".sloj .tancica").forEach(function (t_) { t_.addEventListener("click", function () {
      $("iskanje").value = "";
      zapriSloje();
    }); });
    $("dodajPreklici").addEventListener("click", zapriSloje);
    $("medijiDodaj").addEventListener("click", odpriDodaj);
    $("medijiMapa").addEventListener("click", function () {
      klic("medijskaMapa").catch(function () { obvesti(t("niUspelo")); });
    });
    $("mediaMapeGumb").addEventListener("click", function () {
      narisiMedijskeMape(); $("slojMediaMape").classList.add("viden"); naloziMedijskeMape();
      $("mediaMapeZapri").focus();
    });
    $("mediaMapeZapri").addEventListener("click", zapriSloje);
    $("mediaNapraveGumb").addEventListener("click", odpriMediaNaprave);
    $("medijiMagnet").addEventListener("click", function () { odpriMagnet(""); });
    // "Nadaljuj z druge naprave" tudi iz glave Medijskega centra (kot na Windows): sloj naprav z odprtim seznamom ponudb.
    $("medijiPredaja").addEventListener("click", function () {
      S.mediaNaprava = null;
      $("slojMediaNaprave").classList.add("viden");
      $("mediaNapraveZapri").focus();
      prikaziPredajo();
    });
    $("medijiDisk").addEventListener("click", function () {
      if (S.dvdPogon) klic("dvdPredvajaj", [S.dvdPogon]).then(function (ok) { if (!ok) obvesti(t("mediaNapaka_dvd")); });
    });
    $("magnetZapri").addEventListener("click", zapriSloje);
    $("magnetObrazec").addEventListener("submit", function (e) {
      e.preventDefault();
      var uri = $("magnetPolje").value.trim();
      if (uri.indexOf("magnet:?") !== 0) { magnetSporocilo(magnetNapaka("ni_magnet")); return; }
      preberiMagnet(uri, false);
    });
    $("magnetDeliDatoteko").addEventListener("click", function () { zagotoviProgram().then(function (ok) { if (ok) klic("magnetIzDatoteke", [false]); }); });
    $("magnetDeliMapo").addEventListener("click", function () { zagotoviProgram().then(function (ok) { if (ok) klic("magnetIzDatoteke", [true]); }); });
    $("magnetPrivzeto").addEventListener("click", function () {
      klic("magnetPrivzeto", [true]).then(function (je) { $("magnetPrivzeto").hidden = !!je; if (je) obvesti(t("magnetPrivzetoOk")); });
    });
    if (PREDVAJALNIK)       // dodatek Stremio (gumb "Install"), ki je cakal na Safeer Player
      klic("cakajociStremio").then(function (c) { if (c && c.url) pokaziStremioDodatek(c.url); }).catch(function () {});
    if (!PREDVAJALNIK)      // cakajoci magnet je za glavno okno, ki ga Safeer OS prav zanj odpira
      klic("cakajociMagnet").then(function (c) { if (c && c.uri) odpriMagnet(c.uri, c.samodejno === true); }).catch(function () {});
    $("mediaNapraveZapri").addEventListener("click", zapriSloje);
    $("mediaNapraveNazaj").addEventListener("click", nazajMediaNaprave);
    $("mediaMapeDodaj").addEventListener("click", function () { zapriSloje(); $("medijiMapa").click(); });
    $("galerijaZapri").addEventListener("click", zapriGalerijo);
    document.querySelector(".galerija-tancica").addEventListener("click", zapriGalerijo);
    $("galerijaNazaj").addEventListener("click", function () { premakniSliko(-1); });
    $("galerijaNaprej").addEventListener("click", function () { premakniSliko(1); });
    $("galerijaSlika").addEventListener("click", function () { document.querySelector(".galerija").classList.toggle("povecano"); });
    $("galerijaSlika").addEventListener("error", function () { if (S.galerija) $("galerijaNapis").textContent = t("mediaManjka"); });
    $("galerijaOdpri").addEventListener("click", function () {
      var g = S.galerija; if (!g) return;
      klic("odpriLokalniMedij", [g.seznam[g.i].pot]).then(function (ok) { if (!ok) obvesti(t("niUspelo")); });
    });
    document.addEventListener("keydown", function (e) {
      if (!S.galerija) return;
      if (e.key === "ArrowLeft") { e.preventDefault(); premakniSliko(-1); }
      else if (e.key === "ArrowRight" || e.key === " ") { e.preventDefault(); premakniSliko(1); }
      else if (e.key === "Home") { e.preventDefault(); S.galerija.i = 0; prikaziSliko(); }
      else if (e.key === "End") { e.preventDefault(); S.galerija.i = S.galerija.seznam.length - 1; prikaziSliko(); }
      else if (e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); zapriGalerijo(); }
    }, true);
    $("mediaOsvezi").addEventListener("click", function () {
      S.mediaOsvezuje = true; this.disabled = true;
      klic("osveziMedijskeMape").then(function (ok) {
        if (!ok) { S.mediaOsvezuje = false; $("mediaOsvezi").disabled = !S.mediaMape.length; }
      }).catch(function () { S.mediaOsvezuje = false; $("mediaOsvezi").disabled = !S.mediaMape.length; obvesti(t("niUspelo")); });
    });
    $("mediaVec").addEventListener("click", function () { naloziMedije(true); });
    poveziMeniDodaj();
    // Krajevna knjiznica se tudi nalaga sama, ko pride konec seznama v pogled (gumb »Prikaži več« ostane za tipkovnico).
    if ("IntersectionObserver" in window) new IntersectionObserver(function (vnosi) {
      if (vnosi.some(function (v) { return v.isIntersecting; }) && !$("mediaVec").hidden && S.mediaHasMore) {
        S.mediaHasMore = false; naloziMedije(true);
      }
    }, { root: $("vsebina"), rootMargin: "0px 0px 500px 0px" }).observe($("mediaVec"));
    $("medijiLokalno").addEventListener("click", function () {
      klic("lokalniMediji").catch(function () { obvesti(t("niUspelo")); });
    });
    $("medijiTok").addEventListener("click", function () {
      $("mediaTokIme").value = ""; $("mediaTokUrl").value = "";
      $("mediaTokVrsta").value = S.mediaFilter === "radio" ? "radio" : "tv";
      $("slojMediaTok").classList.add("viden");
      $("mediaTokIme").focus();
    });
    $("mediaTokPreklici").addEventListener("click", zapriSloje);
    $("obrazecMediaTok").addEventListener("submit", function (e) {
      e.preventDefault();
      var ime = $("mediaTokIme").value.trim(), url = $("mediaTokUrl").value.trim();
      if (!ime || !/^https?:\/\/[^\s]+$/i.test(url)) { obvesti(t("mediaNapacenTok")); return; }
      klic("dodajMedijskiTok", [ime, url, $("mediaTokVrsta").value]).then(function (ok) {
        if (ok) zapriSloje(); else obvesti(t("mediaNapacenTok"));
      }).catch(function () { obvesti(t("mediaNapacenTok")); });
    });
    $("medijiDodajPrazno").addEventListener("click", function () { $("medijiMapa").click(); });
    $("mediaBarOdpri").addEventListener("click", function () { if (spNaTraku()) { spPokaziRazdelek(false); return; } klic("predvajalnikUkaz", ["odpri"]).catch(function () {}); });
    poveziTrak();
    poveziNav();
    poveziPrilagodi();
    poveziIskanjeNastavitev();
    poveziAgenta();
    $("mediaBarNapredek").addEventListener("change", function () {
      var p = S.mediaPredvajalnik;
      S.mediaDragging = false;
      if (spNaTraku()) { spUkazTraka("cas", Number(this.value) / 1000); return; }
      if (p && p.trajanje > 0 && p.vrsta !== "tv" && p.vrsta !== "radio")
        klic("predvajalnikUkaz", ["skok", p.trajanje * Number(this.value) / 1000]);
    });
    $("mediaBarNapredek").addEventListener("pointerdown", function () { S.mediaDragging = true; });
    $("mediaBarNapredek").addEventListener("pointerup", function () { S.mediaDragging = false; });
    $("programiIskanje").addEventListener("input", function () {
      S.programIskanje = this.value.trim(); S.skupina = "vse"; narisiPrograme();
    });
    $("mediaIskanje").addEventListener("input", function () {
      // Iskanje gre po vseh vrstah (rezultati); prazno iskanje vrne zadnji zavihek. Na zavihku Twitch išče kanale Twitcha.
      var naTwitchu = zadnjaMedijskaKategorija() === "twitch";
      S.mediaIskanje = this.value.trim(); S.mediaFilter = S.mediaIskanje && !naTwitchu ? "vse" : zadnjaMedijskaKategorija(); narisiMedije();
      S.mediaRequest++;
      clearTimeout(S.mediaIskanjeZamik);
      S.mediaIskanjeZamik = setTimeout(function () { naloziMedije(); }, 180);
    });
    $("napraveIskanje").addEventListener("input", function () {
      S.napraveIskanje = this.value.trim(); narisiSeznamNaprav(S.povezava.stanje === "povezan");
    });
    $("datotekeIskanje").addEventListener("input", function () {
      var niz = this.value.trim();
      clearTimeout(ciljnoDatotekeZamik);
      if (!niz) { S.datotekeIskanje = ""; odpriNedavne(); return; }
      ciljnoDatotekeZamik = setTimeout(function () { prikaziIskanjeDatotek(niz); }, 250);
    });
    $("obrazecDodaj").addEventListener("submit", function (e) {
      e.preventDefault();
      var naslov = normalizirajNaslov($("dodajNaslov").value);
      if (!naslov) { $("dodajNaslov").focus(); return; }
      var kljuc = kljucNaslova(naslov);
      if (spletne().some(function (a) { return kljucNaslova(a.url) === kljuc; })) {
        obvesti(t("virZeDodan"));
        $("dodajNaslov").focus();
        return;
      }
      var ime = $("dodajIme").value.trim() || new URL(naslov).hostname.replace(/^www\./, "");
      var vnos = { ime: ime.slice(0, 40), url: naslov };
      if (!$("dodajMedijskaVrstaPolje").hidden) vnos.vrsta = $("dodajMedijskaVrsta").value;
      shraniSpletne(spletne().concat([vnos]).slice(0, 24));
      zapriSloje();
    });
    var iskanje = $("iskanje");
    iskanje.addEventListener("input", function () { lupaUredi(); isci(); });
    iskanje.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); premakniIzbiro(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); premakniIzbiro(-1); }
      else if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && agentNaVoljo() && iskanje.value.trim()) {
        // Ctrl+Enter: stavek gre Safeer Agentu (kot Shift+Enter na namizju gre v splet).
        e.preventDefault();
        vprasajAgenta(iskanje.value.trim());
        iskanje.value = ""; zapriSloje(); iskanje.blur();
      }
      else if (e.key === "Enter" && e.shiftKey && iskanje.value.trim()) {
        // Shift+Enter: vedno splet (kot lupa na namizju).
        e.preventDefault();
        izvediNamero(iskanje.value.trim(), { vrsta: "splet", razlog: "iskanje" });
        iskanje.value = ""; zapriSloje(); iskanje.blur();
      }
      else if (e.key === "Enter") {
        var a = document.querySelector("#zadetki .zadetek.aktiven");
        e.preventDefault();
        if (a) a.click(); else izvediNamero(iskanje.value.trim());
        iskanje.value = ""; iskanje.blur();
      }
    });
    iskanje.addEventListener("focus", function () { if (iskanje.value) isci(); lupaUredi(); });
    iskanje.addEventListener("blur", function () { setTimeout(lupaUredi, 0); });
    // Kot meni Start (in Rofi): kar zacnes tipkati, gre v iskanje - v oknu razdelka v njegovo iskanje.
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        var odprt = document.querySelector(".sloj.viden");
        if (odprt || iskanje.value) { iskanje.value = ""; zapriSloje(); iskanje.blur(); }
        else if (!EN_RAZDELEK) pojdi("domov");      // Safeer Player in okna razdelkov nimajo domacega zaslona
        return;
      }
      var cilj = poljeIskanjaOkna();
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && (e.key === "k" || e.key === "K")) {
        if (!cilj) return;
        e.preventDefault();
        cilj.focus(); cilj.select();
        lupaUredi();
        return;
      }
      var v = document.activeElement;
      if (v && (v.tagName === "INPUT" || v.tagName === "TEXTAREA" || v.tagName === "SELECT" || v.isContentEditable)) return;
      // Odprt obrazec (npr. »Dodaj postajo«) ne sme pošiljati tipk v iskanje za sabo.
      var sloj = document.querySelector(".sloj.viden");
      if (sloj && sloj.id !== "slojIskanje") return;
      if (!jeTipkaZaIskanje(e) || !cilj) return;
      e.preventDefault();
      cilj.focus();
      cilj.value += e.key;
      if (cilj === iskanje) { isci(); lupaUredi(); } else cilj.dispatchEvent(new Event("input"));
    });
  }

  // Tipka, ki zacne iskanje: en natisljiv znak brez Ctrl, Alt ali Meta (presledek ne - ta klikne gumb v fokusu).
  function jeTipkaZaIskanje(e) {
    return !!e.key && e.key.length === 1 && e.key !== " " && !e.ctrlKey && !e.altKey && !e.metaKey && !e.isComposing;
  }
  // Iskalno polje tega okna: glavno okno - lupa v glavi; Safeer Player - iskanje Medijskega centra; okno razdelka -
  // iskanje razdelka (prej je tipkanje v oknu Nastavitve slo v skrito lupo glavnega okna). Brez polja: null.
  function poljeIskanjaOkna() {
    if (PREDVAJALNIK) return $("mediaIskanje");
    if (!EN_RAZDELEK) return $("iskanje");
    return $({ nastavitve: "nastavitveIskanje", zapiski: "zapiskiIskanje", sporocila: "sporocilaIskanje" }[EN_RAZDELEK] || "") || null;
  }
  function agentNaVoljo() { return !!(S.agent && S.agent.na_voljo); }
  // Iskalna lupa v glavi: zlozena (kratko polje z namigom Ctrl+K), dokler je ne uporabis; razsirjena med iskanjem.
  function lupaUredi() {
    var l = $("iskanjeLupa"), v = $("iskanje");
    if (!l || !v) return;
    var odprta = document.activeElement === v || !!v.value || $("slojIskanje").classList.contains("viden");
    l.classList.toggle("razsirjena", odprta);
    v.placeholder = t(odprta ? (agentNaVoljo() ? "isciAliVprasaj" : "isci") : (agentNaVoljo() ? "isciKratkoAgent" : "isciKratko"));
    l.title = t("tipkaj") + " · Ctrl+K";
  }
  // Stavek iz lupe za Safeer Agenta (core/agent/storitev.vprasaj_tukaj): izid pove obvestilo, nic se ne ugiba.
  function vprasajAgenta(niz) {
    obvesti(t("agentDelam"));
    klic("agentVprasaj", [niz]).then(function (r) {
      if (r && r.koda === "ni_modela") { obvesti(t("agentNiModela")); return; }
      if (r && r.koda === "model_ni_dosegljiv") { obvesti(t("agentStNedosegljiv")); return; }
      obvesti((r && r.povzetek) || t("niUspelo"));
    }, function () { obvesti(t("niUspelo")); });
  }

  // Safeer Player: samo razdelek Medijski center, po zelji z iskanim nizom z delovne povrsine (?iskanje=).
  function zacniPredvajalnik() {
    var iskano = (location.search.match(/[?&]iskanje=([^&]*)/) || [])[1];
    var niz = "";
    try { niz = iskano ? decodeURIComponent(iskano).trim() : ""; } catch (e) { niz = ""; }
    window.safeerOsPojdi(niz ? "mediji:" + niz : "media");
  }

  /* ==== Vgrajeni kanali Sporocil (spletni klepeti in namizni programi) ===========================================
     Lastnik, 15. 10. 2026: spletni klepet (WhatsApp, Messenger, Telegram …) ali namizni program (Viber, Signal) je del
     namizja - v Sporocilih, ne v drugem oknu. Kanal je pogled vgrajenega Spleta (ena prijava s Spletom) ali vstavljeno
     okno programa; Safeer OS ga postavi nad to stran na mesto #vgrajenKanalVsebina (core/os_kanali_sporocil.py). Ta stran
     pove le pravokotnik in kdaj ga skriti (sloj, meni, drug kanal ali razdelek). Katalog je core/spletni_klepeti.py. */
  var VK = { kanali: [], aktivni: "", katalog: null, skrit: false, opazovalec: null, urejan: null, prej: null };
  IK.smeti = "M4 7h16 M9 7V4h6v3 M6 7l1 13h10l1-13 M10 11v6 M14 11v6";
  function vkKanal(id) { return VK.kanali.find(function (k) { return k.id === id; }) || null; }
  // Dejanje s kanalom (dodaj, vklop, premik ...): ce Safeer OS ne odgovori v 20 s, je to napaka - nikoli tisina
  // (zivi preizkus 15. 10. 2026: klik »Dodaj v Sporocila« brez odgovora ni pokazal nicesar).
  var VK_ROK_MS = 20000;
  function klicKanala(metoda, argumenti) {
    return new Promise(function (res, rej) {
      var rok = setTimeout(function () { rej("rok"); }, VK_ROK_MS);
      klic(metoda, argumenti).then(function (v) { clearTimeout(rok); res(v); },
        function (e) { clearTimeout(rok); rej(e); });
    });
  }
  function vkNapaka(e) { obvesti(t(String(e) === "rok" ? "kanalNapakaRok" : "kanalNapakaDejanje")); }
  function vkZnak(k, razred) {
    // Ikona strani (core/ikone_strani - prenesena neposredno s strani) ali ploscica z zacetnico.
    var z = el("span", razred || "kanal-znak");
    if (k.ikona) { var i = document.createElement("img"); i.src = k.ikona; i.alt = ""; z.appendChild(i); }
    else {
      // Ploscica z zacetnico v barvi iz tokens.css (stalna za storitev); ikona strani se prenese sele, ko je kanal dodan.
      var barve = ["splet", "slika", "video", "zvok", "dokument", "mapa", "arhiv", "naprava"];
      z.textContent = zacetnice(k.ime); z.classList.add("crka");
      z.style.background = "var(--vrsta-" + barve[barvaIzImena(k.katalog || k.id || k.ime) % barve.length] + ")";
    }
    return z;
  }
  function naloziVgrajeneKanale() {
    if (!most) return;
    klic("kanaliSeznam").then(function (s) { VK.kanali = s || []; narisiKanale(); osveziVgrajenKanal(); }).catch(function () {});
  }
  function vkNeprebrano() {
    return VK.kanali.reduce(function (n, k) { return n + (k.vklopljen ? (k.neprebrano || 0) : 0); }, 0);
  }
  function narisiVgrajeneKanale(cilj) {
    VK.kanali.forEach(function (k) {
      var b = el("button", "kanal-cip vgrajen" + (k.vklopljen ? "" : " izklopljen") + (VK.aktivni === k.id ? " izbran" : ""));
      b.type = "button"; b.setAttribute("data-kanal", k.id);
      b.appendChild(vkZnak(k));
      b.appendChild(el("span", "kanal-ime", ubezi(k.ime)));
      if (!k.vklopljen) b.appendChild(el("small", "", ubezi(t("kanalIzklopljen"))));
      else if (k.neprebrano) b.appendChild(el("b", "kanal-znacka", ubezi(k.neprebrano > 99 ? "99+" : String(k.neprebrano))));
      b.title = k.ime + (k.neprebrano ? " · " + t("kanalNeprebranih", { n: k.neprebrano }) : "");
      b.addEventListener("click", function () { if (k.vklopljen) odpriVgrajenKanal(k.id); else odpriUrejanjeVgrajenega(k); });
      b.addEventListener("contextmenu", function (e) { e.preventDefault(); odpriUrejanjeVgrajenega(k); });
      b.addEventListener("keydown", function (e) {
        if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) { e.preventDefault(); odpriUrejanjeVgrajenega(k); }
      });
      cilj.appendChild(b);
    });
  }
  function vkPravokotnik() {
    var v = $("vgrajenKanalVsebina"); if (!v) return null;
    var r = v.getBoundingClientRect();
    return { x: r.left, y: r.top, w: r.width, h: r.height, vw: window.innerWidth, vh: window.innerHeight,
      dpr: window.devicePixelRatio || 1 };
  }
  function odpriVgrajenKanal(id) {
    var k = vkKanal(id); if (!k) return;
    if (S.razdelek !== "sporocila") pojdi("sporocila");
    VK.aktivni = id;
    var n = document.querySelector(".nabiralnik"); if (n) n.classList.add("kanal-odprt");
    $("vgrajenKanal").hidden = false;
    $("vgrajenKanalIme").textContent = k.ime;
    var znak = vkZnak(k, "kanal-znak"); znak.id = "vgrajenKanalZnak"; $("vgrajenKanalZnak").replaceWith(znak);
    var splet = k.vrsta === "splet";
    ["vgrajenKanalNazaj", "vgrajenKanalOsvezi", "vgrajenKanalDomov", "vgrajenKanalSplet"].forEach(function (g) { $(g).hidden = !splet; });
    vkPonastaviOdstrani();
    $("vgrajenKanalPreklici").hidden = !k.caka;
    narisiKanale();
    vkSporocilo("");
    if (k.vrsta === "program" && k.namescen === false) { vkSporocilo(t("kanalProgramNi", { ime: k.ime })); return; }
    vkPokazi();       // getBoundingClientRect izracuna postavitev takoj (requestAnimationFrame v skritem oknu ne pride)
  }
  function vkPokazi() {
    if (!VK.aktivni || VK.skrit || S.razdelek !== "sporocila") return;
    klicKanala("kanalPokazi", [VK.aktivni, vkPravokotnik()]).then(function (r) {
      if (!r || r.ok === false) {
        vkSporocilo(t(r && r.razlog === "program" ? "kanalProgramNi" : "kanalNiMogoce", { ime: (vkKanal(VK.aktivni) || {}).ime || "" }));
        return;
      }
      // Wayland: okna drugega programa ni mogoce vstaviti - pove se posteno, program je v svojem oknu.
      vkSporocilo(r.vgrajeno === false ? t("kanalSvojeOkno", { ime: (vkKanal(VK.aktivni) || {}).ime || "" }) : "");
    }).catch(function (e) { vkSporocilo(t(String(e) === "rok" ? "kanalNapakaRok" : "kanalNiMogoce", { ime: (vkKanal(VK.aktivni) || {}).ime || "" })); });
  }
  function vkSporocilo(besedilo) {
    var p = $("vgrajenKanalSporocilo"); if (!p) return;
    p.textContent = besedilo; p.hidden = !besedilo;
  }
  function zapriVgrajenKanal(brezSkrij) {
    if (!VK.aktivni) return;
    VK.aktivni = "";
    var n = document.querySelector(".nabiralnik"); if (n) n.classList.remove("kanal-odprt");
    if ($("vgrajenKanal")) $("vgrajenKanal").hidden = true;
    // brezSkrij: kanal gre stran (preklic) - Safeer OS ga skrije sam; »kanalSkrij« bi ga pred tem lahko potrdil.
    if (brezSkrij !== true) klic("kanalSkrij").catch(function () {});
    narisiKanale();
  }
  function osveziVgrajenKanal() {
    if (!VK.aktivni) return;
    var k = vkKanal(VK.aktivni);
    if (!k || !k.vklopljen) { zapriVgrajenKanal(); return; }
    $("vgrajenKanalIme").textContent = k.ime;
    $("vgrajenKanalPreklici").hidden = !k.caka;
  }
  /* »Preklici dodajanje« (lastnik, 15. 10. 2026: Gmail se je dodal takoj in odprl prijavo Googla, nazaj ni bilo poti):
     kanal, ki se ni v uporabi (prijava ni koncana, core/os_kanali_sporocil.preklici), gre stran in uporabnik je spet
     tam, kjer je bil pred carovnikom. Tudi Esc in Nazaj na daljincu (tipko v kanalu ujame Safeer OS, dogodek
     »kanalPreklici«). Kanala v uporabi ta pot ne odstrani - za to je »Odstrani kanal« s potrditvijo. */
  function vkPrekliciDodajanje(id) {
    var k = vkKanal(id || VK.aktivni);
    if (!k || !k.caka) return false;
    var prej = VK.prej || {}; VK.prej = null;
    if (VK.aktivni === k.id) zapriVgrajenKanal(true);
    klicKanala("kanalPreklici", [k.id]).then(function (s) {
      vkPosodobi(s);
      obvesti(t("kanalDodajanjePreklicano", { ime: k.ime }));
      if (prej.kanal && prej.kanal !== k.id && vkKanal(prej.kanal)) odpriVgrajenKanal(prej.kanal);
      else if (prej.razdelek && prej.razdelek !== S.razdelek) pojdi(prej.razdelek);
    }).catch(vkNapaka);
    return true;
  }
  // »Odstrani kanal« v orodni vrstici kanala: ena potrditev (drugi klik v 5 s), brez brisanja podatkov strani.
  var vkOdstraniRok = 0;
  function vkPonastaviOdstrani() {
    var b = $("vgrajenKanalOdstrani"); if (!b) return;
    clearTimeout(vkOdstraniRok); b.classList.remove("potrdi"); b.title = t("odstraniKanal");
  }
  function vkOdstraniAktivni() {
    var b = $("vgrajenKanalOdstrani"), k = vkKanal(VK.aktivni); if (!k) return;
    if (!b.classList.contains("potrdi")) {
      b.classList.add("potrdi"); b.title = t("odstraniKanalPotrdi"); obvesti(t("odstraniKanalPotrdi"));
      vkOdstraniRok = setTimeout(vkPonastaviOdstrani, 5000);
      return;
    }
    vkPonastaviOdstrani();
    zapriVgrajenKanal();
    klicKanala("kanalOdstrani", [k.id, false]).then(vkPosodobi).catch(vkNapaka);
  }
  // Sloj (pogovorno okno), meni ali obvestilo nad vsebino: kanal je nad stranjo, zato se med tem skrije.
  function vkUskladiSloje() {
    var odprto = !!document.querySelector(".sloj.viden") || ($("sporocilaMeni") && !$("sporocilaMeni").hidden);
    if (odprto === VK.skrit) return;
    VK.skrit = odprto;
    if (!VK.aktivni) return;
    if (odprto) klic("kanalSkrij").catch(function () {}); else vkPokazi();
  }
  function vkPolozaj() {
    if (VK.aktivni && !VK.skrit) klic("kanalPolozaj", [vkPravokotnik()]).catch(function () {});
  }
  /* Carovnik »Dodaj kanal« › Aplikacije: katalog (vgradljivi klepeti in posta z enim klikom, namizni programi, ce so
     namesceni), lasten klepet z naslovom https, in programi z vec kanali (samo uradna stran za prenos). */
  function narisiKatalogKanalov(a) {
    a.textContent = "";
    var katalog = (kanalPonudnikiPodatki && kanalPonudnikiPodatki.klepeti) || [];
    var dodani = {}; VK.kanali.forEach(function (k) { if (k.katalog) dodani[k.katalog] = true; });
    [["klepet", "kanalAppKlepet"], ["posta", "kanalAppPosta"]].forEach(function (sk) {
      var seznam = katalog.filter(function (x) { return x.vrsta === sk[0]; });
      if (!seznam.length) return;
      a.appendChild(el("b", "aplikacije-skupina", ubezi(t(sk[1]))));
      seznam.forEach(function (x) {
        var v = el("div", "aplikacije-vrsta");
        v.appendChild(vkZnak({ ime: x.ime, katalog: x.id, ikona: x.ikona || "" }, "kanal-znak"));
        var ime = el("div", "ime", ubezi(x.ime));
        var program = !!x.program && !x.splet;
        var opis = x.razlog || (program ? (x.namescen ? t("kanalProgramNamescen") : t("kanalProgramOpis")) :
          String(x.splet || "").replace(/^https?:\/\//, "").split("/")[0]);
        ime.appendChild(el("small", "", ubezi(opis)));
        v.appendChild(ime);
        function gumb(besedilo, glavni, ob) {
          var g = el("button", "gumb" + (glavni ? " glavni" : ""), ubezi(besedilo)); g.type = "button";
          g.addEventListener("click", ob); v.appendChild(g); return g;
        }
        if (dodani[x.id]) v.appendChild(el("span", "oznaka-dodano", ubezi(t("kanalDodano"))));
        else if (x.splet || (program && x.namescen)) gumb(t("kanalDodajVSporocila"), true, function () { dodajVgrajeni({ katalog: x.id }, this); });
        if (program && !x.namescen && !dodani[x.id]) {
          gumb(t("kanalNamesti"), true, function () { zapriSloje(); klic("splet", [x.prenos, true]); });
          gumb(t("kanalIzberiProgram"), false, function () {
            klic("kanalIzberiProgram", [t("kanalIzberiProgram")]).then(function (pot) {
              if (pot) dodajVgrajeni({ katalog: x.id, pot: pot });
            }).catch(function (e) { vkNapakaCarovnika(e); });
          });
        } else if (!x.splet && !program && x.prenos) gumb(t("kanalAppPrenos"), false, function () { zapriSloje(); klic("splet", [x.prenos, true]); });
        a.appendChild(v);
      });
    });
    // Lasten klepet: Mattermost, Rocket.Chat, Zulip, lasten Element … (samo https, brez gesla v naslovu)
    a.appendChild(el("b", "aplikacije-skupina", ubezi(t("kanalSvojKlepet"))));
    var f = el("div", "svoj-klepet");
    f.innerHTML = '<p class="drobno">' + ubezi(t("kanalSvojKlepetOpis")) + '</p><input class="svoj-url" type="url" aria-label="' + ubezi(t("kanalSvojKlepet")) + '" ' +
      'inputmode="url" autocomplete="off" maxlength="2048" placeholder="https://chat.example.org"><input class="svoj-ime" ' +
      'type="text" maxlength="60" placeholder="' + ubezi(t("kanalSvojIme")) + '"><button type="button" class="gumb glavni" ' +
      'data-svoj="dodaj">' + ubezi(t("kanalDodajVSporocila")) + '</button>';
    a.appendChild(f);
    f.querySelector("[data-svoj]").addEventListener("click", function () {
      dodajVgrajeni({ url: f.querySelector(".svoj-url").value.trim(), ime: f.querySelector(".svoj-ime").value.trim() }, this);
    });
    // Programi z vec kanali v enem oknu: samo uradna stran za prenos (Safeer nicesar ne prenasa sam).
    [["vec", "kanalAppVec"]].forEach(function (sk) {
      var seznam = (kanalPonudnikiPodatki.aplikacije || []).filter(function (x) { return x.vrsta === sk[0]; });
      if (!seznam.length) return;
      a.appendChild(el("b", "aplikacije-skupina", ubezi(t(sk[1]))));
      seznam.forEach(function (x) {
        var v = el("div", "aplikacije-vrsta");
        var ime = el("div", "ime", ubezi(x.ime)); ime.appendChild(el("small", "", ubezi(x.opis || "")));
        v.appendChild(ime);
        var g = el("button", "gumb", ubezi(t("kanalAppPrenos"))); g.type = "button";
        g.addEventListener("click", function () { zapriSloje(); klic("splet", [x.prenos, true]); });
        v.appendChild(g);
        a.appendChild(v);
      });
    });
  }
  var NAPAKE_KANALA = { prazno: "kanalNapakaNaslov", https: "kanalNapakaHttps", poverilnice: "kanalNapakaGeslo",
    gostitelj: "kanalNapakaNaslov", dolzina: "kanalNapakaNaslov", najvec: "kanalNapakaNajvec", pot: "kanalNapakaPot",
    izklopljeno: "sporocilaIzklopljena" };
  function vkNapakaCarovnika(e) {
    var n = $("kanalNapaka");
    n.textContent = t(String(e) === "rok" ? "kanalNapakaRok" : (NAPAKE_KANALA[String(e)] || "kanalNapakaDejanje"));
    n.hidden = false;
    // Napaka je pod seznamom aplikacij: pokaze se tudi, ce je uporabnik pri vrhu seznama.
    if (n.scrollIntoView) n.scrollIntoView({ block: "nearest" });
  }
  function dodajVgrajeni(p, gumb) {
    $("kanalNapaka").hidden = true;
    // Kje je bil uporabnik pred carovnikom: »Preklici dodajanje« ga vrne tja.
    VK.prej = { razdelek: S.razdelek, kanal: VK.aktivni };
    if (gumb) gumb.disabled = true;          // med cakanjem: brez dvojnega dodajanja
    klicKanala("kanalDodaj", [p.katalog || "", p.url || "", p.ime || "", p.pot || ""]).then(function (s) {
      if (gumb) gumb.disabled = false;
      VK.kanali = s || [];
      zapriSloje();
      var nov = p.katalog ? VK.kanali.find(function (k) { return k.katalog === p.katalog; }) : VK.kanali[VK.kanali.length - 1];
      narisiKanale();
      if (nov) odpriVgrajenKanal(nov.id);
    }).catch(function (e) {
      if (gumb) gumb.disabled = false;
      vkNapakaCarovnika(e);
    });
  }
  // Urejanje kanala: ime, vklop, vrstni red, podatki strani, odstranitev (desni klik ali klik na izklopljen kanal).
  function odpriUrejanjeVgrajenega(k) {
    zapriSloje(); VK.urejan = k.id;
    $("vgrajenUrediNaslov").textContent = k.ime;
    $("vgrajenUrediIme").value = k.ime;
    $("vgrajenUrediVklop").setAttribute("aria-checked", k.vklopljen ? "true" : "false");
    $("vgrajenUrediPodatki").hidden = k.vrsta !== "splet";
    $("vgrajenUrediPodatkeTudi").parentNode.hidden = k.vrsta !== "splet";
    $("vgrajenUrediPodatkeTudi").checked = false;
    $("vgrajenUrediOdstrani").removeAttribute("data-potrdi"); $("vgrajenUrediOdstrani").textContent = t("odstraniKanal");
    var i = VK.kanali.findIndex(function (x) { return x.id === k.id; });
    $("vgrajenUrediGor").hidden = i <= 0; $("vgrajenUrediDol").hidden = i < 0 || i >= VK.kanali.length - 1;
    $("vgrajenUrediOpis").textContent = k.vrsta === "program" ? t("kanalProgramUredi") : (k.url || "");
    $("slojVgrajenUredi").classList.add("viden");
    $("vgrajenUrediIme").focus();
  }
  function vkPosodobi(s) { VK.kanali = s || []; narisiKanale(); osveziVgrajenKanal(); }
  /* Katalog za carovnik iz Safeer OS (kanaliKatalog): ali je namizni program namescen in ikona strani iz predpomnilnika
     (core/ikone_strani; manjkajoce Safeer OS prenese neposredno s strani in pove z dogodkom »kanaliKatalog«). Brez
     odgovora ostane katalog iz sporocilaPonudniki (zacetnice namesto ikon). */
  function vkOsveziKatalog() {
    klic("kanaliKatalog").then(function (k) {
      if (!Array.isArray(k)) return;
      VK.katalog = k;
      if (kanalPonudnikiPodatki) kanalPonudnikiPodatki.klepeti = k;
      if ($("slojKanal").classList.contains("viden") && kanalPonudnikiPodatki) narisiKatalogKanalov($("kanalAplikacijeMreza"));
    }).catch(function () {});
  }
  function poveziVgrajeneKanale() {
    if (!$("slojVgrajenUredi")) return;
    $("vgrajenUrediPreklici").addEventListener("click", zapriSloje);
    $("vgrajenUrediVklop").addEventListener("click", function () {
      var b = $("vgrajenUrediVklop"), nov = b.getAttribute("aria-checked") !== "true";
      b.setAttribute("aria-checked", nov ? "true" : "false");
      klicKanala("kanalVklopi", [VK.urejan, nov]).then(vkPosodobi).catch(function (e) { b.setAttribute("aria-checked", nov ? "false" : "true"); vkNapaka(e); });
    });
    $("vgrajenUrediGor").addEventListener("click", function () { klicKanala("kanalPremakni", [VK.urejan, -1]).then(function (s) { vkPosodobi(s); odpriUrejanjeVgrajenega(vkKanal(VK.urejan)); }).catch(vkNapaka); });
    $("vgrajenUrediDol").addEventListener("click", function () { klicKanala("kanalPremakni", [VK.urejan, 1]).then(function (s) { vkPosodobi(s); odpriUrejanjeVgrajenega(vkKanal(VK.urejan)); }).catch(vkNapaka); });
    $("vgrajenUrediPodatki").addEventListener("click", function () {
      var b = $("vgrajenUrediPodatki");
      if (b.getAttribute("data-potrdi") !== VK.urejan) { b.setAttribute("data-potrdi", VK.urejan); b.textContent = t("kanalIzbrisiPodatkePotrdi"); return; }
      b.removeAttribute("data-potrdi"); b.textContent = t("kanalIzbrisiPodatke");
      klicKanala("kanalIzbrisiPodatke", [VK.urejan]).then(function (s) { vkPosodobi(s); zapriSloje(); obvesti(t("kanalPodatkiIzbrisani")); })
        .catch(vkNapaka);
    });
    $("vgrajenUrediOdstrani").addEventListener("click", function () {
      var b = $("vgrajenUrediOdstrani");
      if (b.getAttribute("data-potrdi") !== VK.urejan) { b.setAttribute("data-potrdi", VK.urejan); b.textContent = t("odstraniKanalPotrdi"); return; }
      var id = VK.urejan;
      if (VK.aktivni === id) zapriVgrajenKanal();
      klicKanala("kanalOdstrani", [id, $("vgrajenUrediPodatkeTudi").checked === true]).then(function (s) { vkPosodobi(s); zapriSloje(); })
        .catch(vkNapaka);
    });
    $("obrazecVgrajenUredi").addEventListener("submit", function (e) {
      e.preventDefault();
      var ime = $("vgrajenUrediIme").value.trim(), k = vkKanal(VK.urejan);
      if (!k || !ime || ime === k.ime) { zapriSloje(); return; }
      klicKanala("kanalPreimenuj", [VK.urejan, ime]).then(function (s) { vkPosodobi(s); zapriSloje(); }).catch(vkNapaka);
    });
    ["nazaj", "osvezi", "domov", "splet"].forEach(function (ukaz) {
      var id = { nazaj: "vgrajenKanalNazaj", osvezi: "vgrajenKanalOsvezi", domov: "vgrajenKanalDomov", splet: "vgrajenKanalSplet" }[ukaz];
      $(id).addEventListener("click", function () {
        klicKanala("kanalUkaz", [VK.aktivni, ukaz]).then(function (ok) { if (ok === false) vkNapaka(""); }).catch(vkNapaka);
      });
    });
    $("vgrajenKanalUredi").addEventListener("click", function () { var k = vkKanal(VK.aktivni); if (k) odpriUrejanjeVgrajenega(k); });
    $("vgrajenKanalPreklici").addEventListener("click", function () { vkPrekliciDodajanje(VK.aktivni); });
    $("vgrajenKanalOdstrani").addEventListener("click", vkOdstraniAktivni);
    if ($("kanalZapri")) $("kanalZapri").addEventListener("click", zapriSloje);
    // Esc na strani (fokus ni v kanalu): enako kot »Preklici dodajanje«, ce je odprt kanal se v cakanju.
    document.addEventListener("keydown", function (e) {
      if ((e.key !== "Escape" && e.key !== "BrowserBack") || !VK.aktivni || document.querySelector(".sloj.viden")) return;
      if (vkPrekliciDodajanje(VK.aktivni)) { e.preventDefault(); e.stopImmediatePropagation(); }
    }, true);
    // Sloji in meni nad vsebino skrijejo kanal (je nad stranjo); velikost in premik okna mu sledita.
    VK.opazovalec = new MutationObserver(vkUskladiSloje);
    document.querySelectorAll(".sloj").forEach(function (s) { VK.opazovalec.observe(s, { attributes: true, attributeFilter: ["class"] }); });
    if ($("sporocilaMeni")) VK.opazovalec.observe($("sporocilaMeni"), { attributes: true, attributeFilter: ["hidden"] });
    if (window.ResizeObserver) new ResizeObserver(vkPolozaj).observe($("vgrajenKanalVsebina"));
    window.addEventListener("resize", vkPolozaj);
  }
  /* Moznost Sporocila v celoti (Nastavitve Safeer OS ali Prilagodi namizje): izklopljena - razdelka ni nikjer. */
  function sporocilaVklopljena() { return !S.zacetek || S.zacetek.sporocila !== false; }
  function uskladiVklopSporocil() {
    var vkl = sporocilaVklopljena();
    document.querySelectorAll('#meni button[data-razdelek="sporocila"]').forEach(function (b) { b.hidden = !vkl; });
    if (!vkl) {
      zapriVgrajenKanal();
      if (S.razdelek === "sporocila" && !EN_RAZDELEK) pojdi("domov");
    }
  }
  /* ==== konec: vgrajeni kanali Sporocil ========================================================================== */

  /* ==== Poraba kanalov (gumb »Info«) ===========================================================================
     Lastnik, 15. 10. 2026: »S pritiskom uporabnik izve povprecno uporabo strojne opreme za posamezni kanal pri
     Sporocilih ter sestevek skupnega – da se lazje odloci, kateri kanal potrebuje.« Meritve so v Safeer OS
     (core/os_poraba_kanalov.py, metoda opisana tam); ta stran jih samo pokaze. Cesar ni mogoce izmeriti, pise
     »ni merljivo locno« z razlogom - nikoli izmisljena stevilka. */
  IK.info = "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 11v6 M12 7.5v.1";
  var POR = { casovnik: 0, od: null, podatki: null };
  var POR_OSVEZI_MS = 5000;
  function porStevilo(v, decimalk) {
    try { return new Intl.NumberFormat(jezik, { maximumFractionDigits: decimalk, minimumFractionDigits: decimalk }).format(v); }
    catch (e) { return v.toFixed(decimalk); }
  }
  function porMiB(v) {
    if (typeof v !== "number") return null;
    return v >= 1024 ? porStevilo(v / 1024, 2) + " GiB" : porStevilo(v, v >= 100 ? 0 : 1) + " MiB";
  }
  function porBajti(b) {
    if (typeof b !== "number") return null;
    if (b < 1024) return porStevilo(b, 0) + " B";
    if (b < 1024 * 1024) return porStevilo(b / 1024, b < 10240 ? 1 : 0) + " KiB";
    return porMiB(b / 1048576);
  }
  function porCpu(v) { return typeof v === "number" ? porStevilo(v, 1) + " %" : null; }
  // RSS namesto PSS (procesa ni mogoce brati natancno, npr. podpeskovnik Flatpaka): »≈« in namig.
  function porPribl(niz, pribl) { return niz && pribl ? "≈ " + niz : niz; }
  function porVsaj(niz, delno) { return niz && delno ? t("porabaVsaj", { v: niz }) : niz; }
  // Celica: glavna vrednost (povprecje zadnje ure) in pod njo zdaj / od zagona.
  function porCelica(td, glavna, vrstice, ni, namig) {
    if (ni) {
      td.appendChild(el("span", "poraba-ni", ubezi(t("porabaNiMerljivo"))));
      if (namig) td.appendChild(el("small", "poraba-namig", ubezi(namig)));
      return;
    }
    td.appendChild(el("b", "", ubezi(glavna || t("porabaNiPodatka"))));
    vrstice.forEach(function (v) { if (v[1]) td.appendChild(el("small", "", ubezi(t(v[0]) + " " + v[1]))); });
  }
  function porVrstica(v, telo) {
    var tr = document.createElement("tr");
    if (!v.vklopljen) tr.className = "izklopljen";
    var ime = document.createElement("th"); ime.scope = "row";
    ime.appendChild(el("span", "", ubezi(v.ime)));
    ime.appendChild(el("small", "", ubezi(t(v.vrsta === "splet" ? "porabaVrstaSplet" : v.vrsta === "program" ? "porabaVrstaProgram" : "porabaVrstaApi"))));
    if (v.deljeno) ime.appendChild(el("small", "poraba-namig", ubezi(t("porabaDeljeno"))));
    tr.appendChild(ime);
    var niMem = v.vklopljen && (v.ni_merljivo || []).indexOf("mem_ura") >= 0;
    var namig = v.razlog ? t("porabaRazlog_" + v.razlog) : "";
    var mem = document.createElement("td"), cpu = document.createElement("td"), disk = document.createElement("td");
    porCelica(mem, porPribl(porMiB(v.mem_ura), v.priblizek), [["porabaTrenutno", porPribl(porMiB(v.mem_trenutno), v.priblizek)],
      ["porabaZagon", porPribl(porMiB(v.mem_zagon), v.priblizek)]], niMem, namig);
    if (v.priblizek && !niMem) { mem.appendChild(el("small", "poraba-namig", ubezi(t("porabaPriblizek")))); }
    porCelica(cpu, porCpu(v.cpu_ura), [["porabaTrenutno", porCpu(v.cpu_trenutno)], ["porabaZagon", porCpu(v.cpu_zagon)]], niMem, "");
    var niDisk = (v.ni_merljivo || []).indexOf("disk") >= 0;
    porCelica(disk, porBajti(v.disk), [], niDisk, niDisk ? t("porabaDisk_" + (v.razlog_disk || "program")) : "");
    if (!niDisk && v.razlog_disk) disk.title = t("porabaDisk_" + v.razlog_disk);
    tr.appendChild(mem); tr.appendChild(cpu); tr.appendChild(disk);
    var st = document.createElement("td");
    st.appendChild(el("span", "poraba-stanje", ubezi(t(v.vklopljen ? "porabaVklopljen" : "porabaIzklopljen"))));
    var g = el("button", "gumb", ubezi(t(v.vklopljen ? "porabaIzklopi" : "porabaVklopi"))); g.type = "button";
    g.setAttribute("aria-label", t(v.vklopljen ? "porabaIzklopiKanal" : "porabaVklopiKanal", { ime: v.ime }));
    g.setAttribute("data-poraba-kanal", v.id);
    g.addEventListener("click", function () { porPreklopi(v, g); });
    st.appendChild(g);
    tr.appendChild(st);
    telo.appendChild(tr);
  }
  function porSkupno(telo, ime, m) {
    var tr = document.createElement("tr"); tr.className = "poraba-skupno";
    var th = document.createElement("th"); th.scope = "row"; th.appendChild(el("span", "", ubezi(ime))); tr.appendChild(th);
    var mem = document.createElement("td"), cpu = document.createElement("td");
    porCelica(mem, porPribl(porMiB(m.mem_ura), m.priblizek), [["porabaTrenutno", porPribl(porMiB(m.mem_trenutno), m.priblizek)],
      ["porabaZagon", porPribl(porMiB(m.mem_zagon), m.priblizek)]], false, "");
    porCelica(cpu, porCpu(m.cpu_ura), [["porabaTrenutno", porCpu(m.cpu_trenutno)], ["porabaZagon", porCpu(m.cpu_zagon)]], false, "");
    tr.appendChild(mem); tr.appendChild(cpu);
    tr.appendChild(el("td", "", ubezi(t("porabaNiPodatka")))); tr.appendChild(document.createElement("td"));
    telo.appendChild(tr);
  }
  function narisiPorabo(p) {
    POR.podatki = p;
    var telo = $("porabaVrstice"), noga = $("porabaSkupaj"); telo.textContent = ""; noga.textContent = "";
    var kanali = (p && p.kanali) || [];
    if (!kanali.length) {
      var tr = document.createElement("tr"), td = el("td", "", ubezi(t("porabaNiKanalov"))); td.colSpan = 5;
      tr.appendChild(td); telo.appendChild(tr);
    }
    kanali.forEach(function (v) { porVrstica(v, telo); });
    var s = p.skupaj || {};
    var tr2 = document.createElement("tr"); tr2.className = "poraba-vsota";
    var th = document.createElement("th"); th.scope = "row"; th.appendChild(el("span", "", ubezi(t("porabaSkupaj"))));
    if (s.mem_ura_delno || s.mem_trenutno_delno) th.appendChild(el("small", "poraba-namig", ubezi(t("porabaSkupajDelno"))));
    tr2.appendChild(th);
    var mem = document.createElement("td"), cpu = document.createElement("td"), disk = document.createElement("td");
    porCelica(mem, porVsaj(porMiB(s.mem_ura), s.mem_ura_delno), [["porabaTrenutno", porVsaj(porMiB(s.mem_trenutno), s.mem_trenutno_delno)],
      ["porabaZagon", porVsaj(porMiB(s.mem_zagon), s.mem_zagon_delno)]], false, "");
    porCelica(cpu, porVsaj(porCpu(s.cpu_ura), s.cpu_ura_delno), [["porabaTrenutno", porVsaj(porCpu(s.cpu_trenutno), s.cpu_trenutno_delno)],
      ["porabaZagon", porVsaj(porCpu(s.cpu_zagon), s.cpu_zagon_delno)]], false, "");
    porCelica(disk, porVsaj(porBajti(s.disk), s.disk_delno), [], false, "");
    tr2.appendChild(mem); tr2.appendChild(cpu); tr2.appendChild(disk); tr2.appendChild(document.createElement("td"));
    noga.appendChild(tr2);
    var sk = p.skupno || {};
    var naslov = document.createElement("tr"), tdn = el("th", "poraba-podnaslov", ubezi(t("porabaSkupno"))); tdn.colSpan = 5; tdn.scope = "colgroup";
    naslov.appendChild(tdn); noga.appendChild(naslov);
    if (sk.safeer) porSkupno(noga, t("porabaSafeer"), sk.safeer);
    if (sk.omrezje && sk.omrezje.procesov) porSkupno(noga, t("porabaOmrezje"), sk.omrezje);
    if (sk.drugi && sk.drugi.procesov) porSkupno(noga, t("porabaDrugi"), sk.drugi);
    $("porabaOpomba").textContent = p.vzorcev ? t("porabaOpomba", { n: p.vzorcev, ms: porStevilo(p.cena_ms || 0, 1) }) : t("porabaZbiram");
  }
  function porOsvezi() {
    if (!$("slojPoraba").classList.contains("viden")) { porUstavi(); return; }
    klic("kanaliPoraba").then(narisiPorabo).catch(function () { $("porabaOpomba").textContent = t("porabaNapaka"); });
  }
  function porUstavi() { if (POR.casovnik) { clearInterval(POR.casovnik); POR.casovnik = 0; } }
  function odpriPorabo(od) {
    zapriSloje();
    POR.od = od || document.activeElement;
    $("porabaVrstice").textContent = ""; $("porabaSkupaj").textContent = ""; $("porabaOpomba").textContent = "";
    $("slojPoraba").classList.add("viden");
    $("porabaZapri").focus();
    porOsvezi();
    porUstavi(); POR.casovnik = setInterval(porOsvezi, POR_OSVEZI_MS);
  }
  function zapriPorabo() {
    porUstavi();
    $("slojPoraba").classList.remove("viden");
    if (POR.od && POR.od.focus && document.contains(POR.od)) POR.od.focus();
    // Gumb, ki je plosco odprl, ni vec viden (npr. kanal se je zaprl): fokus na drug viden gumb »Info«.
    if (document.activeElement === POR.od) return;
    ["vgrajenKanalInfo", "sporocilaPoraba"].some(function (id) {
      var g = $(id); if (!g || !g.getBoundingClientRect().width) return false;
      g.focus(); return true;
    });
  }
  function porPreklopi(v, g) {
    g.disabled = true;
    var nov = !v.vklopljen;
    var obljuba = (v.vrsta === "splet" || v.vrsta === "program")
      ? klicKanala("kanalVklopi", [v.id, nov]).then(vkPosodobi)
      : klic("sporocilaKanalVklop", [v.id, nov]).then(function (p) {
        S.sporocilaSkupine = p.skupine || []; S.sporocilaKanali = p.kanali || []; narisiSporocila();
      });
    obljuba.then(function () {
      porOsvezi();
      setTimeout(function () { var n = document.querySelector('[data-poraba-kanal="' + v.id + '"]'); if (n) n.focus(); }, 300);
    }).catch(function (e) { g.disabled = false; vkNapaka(e); });
  }
  function poveziPorabo() {
    if (!$("slojPoraba")) return;
    $("porabaZapri").addEventListener("click", zapriPorabo);
    $("slojPoraba").querySelector(".tancica").addEventListener("click", zapriPorabo);
    $("slojPoraba").addEventListener("keydown", function (e) {
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); zapriPorabo(); }
    });
    ["sporocilaPoraba", "vgrajenKanalInfo"].forEach(function (id) {
      var g = $(id); if (!g) return;
      g.setAttribute("aria-label", t("porabaGumb")); g.setAttribute("aria-haspopup", "dialog");
      g.addEventListener("click", function () { odpriPorabo(g); });
    });
  }

  function zacni() {
    if (/[?&]namizje=1/.test(location.search)) document.body.classList.add("namizje");
    if (RAZDELEK) {
      document.body.classList.add("en-razdelek", "razdelek-" + RAZDELEK);
      var jezikRazdelka = (location.search.match(/[?&]jezik=([a-z]{2})(?:&|$)/) || [])[1];
      if (jezikRazdelka && BESEDILA_OS[jezikRazdelka]) jezik = jezikRazdelka;
    }
    if (PREDVAJALNIK) {
      document.body.classList.add("predvajalnik");
      document.title = "Safeer Player";
      var oznaka = document.querySelector("#r-media .media-glava .media-kicker");
      if (oznaka) oznaka.textContent = "SAFEER PLAYER";
      // Jezik pove gostitelj ze v naslovu strani (?jezik=): Medijski center se pokaze takoj, ne sele po »zacetek«
      // (ta pri nepovezanem racunalniku caka na iskanje Safeer Linka), katalog pa se nalozi samo enkrat.
      var jezikStrani = (location.search.match(/[?&]jezik=([a-z]{2})(?:&|$)/) || [])[1];
      if (jezikStrani && BESEDILA_OS[jezikStrani]) jezik = jezikStrani;
    }
    prevedi();
    poveziDogodke();
    poveziProstore();
    poveziVgrajeneKanale();
    poveziPorabo();
    osveziUro();
    setInterval(function () { if (!skrito()) osveziUro(); }, 1000);
    document.addEventListener("visibilitychange", function () { if (!skrito()) osveziUro(); });
    narisiDomov();
    narisiPovezavo();
    if (PREDVAJALNIK) zacniPredvajalnik();
    if (!most) return;
    klic("zacetek").then(function (z) {
      S.zacetek = z;
      if (BESEDILA_OS[z.jezik]) jezik = z.jezik;
      prevedi();
      if (Array.isArray(z.spletne)) S.spletne = z.spletne;
      if (z.ozadje) $("ozadje").style.backgroundImage = 'url("' + z.ozadje.replace(/"/g, "%22") + '")';
      var ime = String(z.ime || "");
      $("imeUporabnika").textContent = ime;
      $("imeRacunalnika").textContent = z.racunalnik || "";
      if (z.sistem) $("sistemIme").textContent = z.sistem;
      $("sistemRacunalnik").textContent = z.racunalnik || "";
      $("zacetnica").textContent = (ime.trim().charAt(0) || "S").toUpperCase();
      S.povezava = z.povezava || S.povezava;
      S.agent = z.agent || { na_voljo: false };
      lupaUredi();
      narisiBliznjice();
      uskladiVklopSporocil();
      narisiPovezavo();
      osveziUro();
      narisiMape();
      narisiDomov();
      nalozPrograme();              // tudi za Safeer Player: predvajalniki racunalnika so med viri Medijskega centra
      if (RAZDELEK) {
        // Okno enega razdelka: ta razdelek (ali ukaz »pojdi«, ki ga je Safeer OS poslal ob odprtju).
        if (S.razdelek !== RAZDELEK) pojdi(RAZDELEK);
        document.title = t({ zapiski: "zapiski", sporocila: "sporocila", nastavitve: "nastavitve", scit: "scitAplikacija" }[RAZDELEK]) || document.title;
        if (S.vodnikPoZacetku) { S.vodnikPoZacetku = false; odpriVodnik(); }
        return;
      }
      if (PREDVAJALNIK) return;     // stanje, odprta okna, nedavne datoteke in sporocila so v lupini Safeer OS
      if (z.vodnik) odpriVodnik(); else if (z.vrnitev) odpriVrnitev();
      osveziStanje();
      osveziOkna();
      narisiNedavneDomov();
      spremljajDatoteke();          // nedavne na domacem zaslonu (ali odprti razdelek Datoteke) se osvezijo same
      klic("sporocilaSeznam").then(function (p) {
        S.sporocilaSkupine = p.skupine || []; S.sporocilaKanali = p.kanali || [];
      });
    }, function () {});
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", zacni); else zacni();
})();
