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
    ,telefon: "M8 3h8a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z M11 18h2"
  };
  function svg(ime) {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + (IK[ime] || IK.datoteka) + '"/></svg>';
  }

  // ------------------------------------------------------------------ most
  var most = window.SafeerOS || null;
  function klic(metoda, argumenti) {
    if (!most) return Promise.reject("brez mosta");
    return most.klic(metoda, argumenti || []);
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
  var LOKALE = { sl: "sl-SI", en: "en-GB", de: "de-DE", es: "es-ES", fr: "fr-FR", it: "it-IT" };
  function prevedi() {
    document.documentElement.lang = jezik;
    document.querySelectorAll("[data-t]").forEach(function (el) { el.textContent = t(el.getAttribute("data-t")); });
    document.querySelectorAll("[data-ph]").forEach(function (el) { el.placeholder = t(el.getAttribute("data-ph")); });
    document.querySelectorAll("[data-naslov]").forEach(function (el) { el.title = t(el.getAttribute("data-naslov")); });
    document.querySelectorAll("svg[data-ikona]").forEach(function (el) {
      el.setAttribute("viewBox", "0 0 24 24");
      el.innerHTML = '<path d="' + (IK[el.getAttribute("data-ikona")] || "") + '"/>';
    });
    vrsticaUredi();
    prevediKatalog();
  }

  /* Zlozljiva stranska vrstica: gumb v glavi ali Ctrl+B, kot v brskalnikih. */
  function vrsticaUredi() {
    var gumb = document.getElementById("gumbVrstica");
    if (!gumb) return;
    var skrcena = document.body.classList.contains("vrstica-skrcena");
    gumb.setAttribute("aria-expanded", skrcena ? "false" : "true");
    gumb.title = t(skrcena ? "vrsticaRazsiri" : "vrsticaSkrci");
    gumb.setAttribute("aria-label", gumb.title);
    if (gumb.dataset.vezan) return;
    gumb.dataset.vezan = "1";
    gumb.addEventListener("click", vrsticaPreklopi);
    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && (e.key === "b" || e.key === "B")) {
        e.preventDefault();
        // Skrita vrstica se s Ctrl+B najprej pokaze (kot v brskalnikih), sicer se skrci/razsiri.
        if (document.body.classList.contains("vrstica-skrita")) vrsticaSkrij(false); else vrsticaPreklopi();
      }
    });
    var skrij = document.getElementById("gumbSkrijVrstico"), rocaj = document.getElementById("rocajVrstice");
    if (skrij) skrij.addEventListener("click", function () { vrsticaSkrij(true); });
    if (rocaj) rocaj.addEventListener("click", function () { vrsticaSkrij(false); });
  }
  function vrsticaSkrij(da) {
    document.body.classList.toggle("vrstica-skrita", !!da);
    try { localStorage.setItem("safeer_vrstica_skrita", da ? "1" : "0"); } catch (e) {}
    var rocaj = document.getElementById("rocajVrstice");
    if (rocaj) { rocaj.title = t("vrsticaPokazi"); rocaj.setAttribute("aria-label", rocaj.title); }
    if (!da) { var izbran = document.querySelector("#meni button.izbran"); if (izbran) izbran.focus(); }
  }
  function vrsticaPreklopi() {
    var skrcena = document.body.classList.toggle("vrstica-skrcena");
    try { localStorage.setItem("safeer_vrstica_skrcena", skrcena ? "1" : "0"); } catch (e) {}
    vrsticaUredi();
  }
  try { if (localStorage.getItem("safeer_vrstica_skrcena") === "1") document.body.classList.add("vrstica-skrcena"); } catch (e) {}
  try { if (localStorage.getItem("safeer_vrstica_skrita") === "1") document.body.classList.add("vrstica-skrita"); } catch (e) {}

  function $(id) { return document.getElementById(id); }
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
  var S = {
    zacetek: null, programi: [], skupina: "vse", razdelek: "domov", pot: "", stanje: null,
    sporocilaSkupine: [], sporocilaKanali: [], sporocilaFilter: "", sporocilaAktivni: null,
    // Multi-host: programi drugih naprav v Safeer Linku (id naprave -> seznam), izbrana naprava ("" = ta racunalnik).
    naprave: [], vseNaprave: [], programiNaprav: {}, nalagam: {}, naprava: "",
    povezava: { stanje: "nov", control: true }, spletne: null, nedavne: [], mediaFilter: "vse",
    mediaLokalno: [], mediaTokovi: [], mediaMape: [], galerija: null, mediaOsvezuje: false, mediaPredvajalnik: null,
    mediaOffset: 0, mediaHasMore: false, mediaRequest: 0,
    mediaQueueKey: "", mediaDragging: false,
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
    S.razdelek = razdelek;
    // Gostitelj pokaze ali skrije desni vdelani brskalnik. Klic je idempotenten, zato
    // tudi programaticni safeerOsPojdi vedno obnovi pravilno postavitev.
    klic("razdelek", [razdelek]).catch(function () {});
    document.querySelectorAll("#meni button").forEach(function (b) {
      b.classList.toggle("izbran", b.getAttribute("data-razdelek") === razdelek);
    });
    document.querySelectorAll(".razdelek").forEach(function (r) { r.classList.toggle("viden", r.id === "r-" + razdelek); });
    $("vsebina").scrollTop = 0;
    if (razdelek === "datoteke" && !S.pot) odpriNedavne();
    if (razdelek === "naprave") { osveziPovezavo(); napraveZanka(); }
    if (razdelek === "sporocila") { naloziSporocila(); sporocilaZanka(); }
    if (razdelek === "nastavitve") { narisiNastavitve(); nalozScit(); scitZanka(); nalozPosodobitve(false); }
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
      if (!r || !r.ok) { obvesti(r && r.message ? r.message : t("niUspelo")); return; }
      if (!r.tu) obvesti(t("napravaNePretaka", { ime: p.ime, naprava: n.ime }));
    }, function () { obvesti(t("niUspelo")); });
  }
  function zazeniNaSamiNapravi(p) {
    var n = S.naprave.find(function (x) { return x.id === p.naprava; }) || { ime: "" };
    obvesti(t("zaganjamNa", { ime: p.ime, naprava: n.ime }));
    klic("zazeniNaNapravi", [p.naprava, p.id]).then(function (r) {
      var ok = r === true || !!(r && r.ok);
      if (!ok) obvesti(r && r.message ? r.message : t("niUspelo"));
    }, function () { obvesti(t("niUspelo")); });
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
    klic("napraveSProgrami").then(function (n) {
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
      else if (r && r.deli === false) S.programiNaprav[id].napaka = "ne_deli";
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
          if (!S.programiNaprav[n.id]) nalozProgrameNaprave(n.id);
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
        mreza.appendChild(el("div", "programi-obvestilo", ubezi(t(seznamN.napaka === "ne_deli" ? "napravaNeDeli" : "napravaNiOdgovorila"))));
        if (seznamN.napaka !== "ne_deli") return;
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
  var MEDIA_KATEGORIJE = [
    ["vse", "programi"], ["glasba", "glasba"], ["video", "video"], ["filmi", "video"],
    ["serije", "video"], ["tv", "video"], ["radio", "radio"], ["slike", "slika"]
  ];
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
  function naloziMedije(veckrat) {
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
    if (!veckrat && most) klic("tokoviMedijev").then(function (vnosi) {
      S.mediaTokovi = Array.isArray(vnosi) ? vnosi : [];
      narisiMedije();
    }).catch(function () {});
    if (S.mediaFilter === "tv" || S.mediaFilter === "radio") {
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
      if (r.shared === false) { mediaNapraveSporocilo(t("mediaNapravaNeDeli")); return; }
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
      klic("odpriLokalniMedij", [v.pot]).then(function (ok) { if (!ok) obvesti(t("niUspelo")); })
        .catch(function () { obvesti(t("niUspelo")); });
    });
    ovoj.appendChild(b);
    var odstrani = el("button", "media-kartica-odstrani", svg("x"));
    odstrani.type = "button"; odstrani.title = t("odstrani");
    odstrani.addEventListener("click", function () {
      klic("odstraniLokalniMedij", [v.pot]).then(function (ok) { if (ok) naloziMedije(); });
    });
    ovoj.appendChild(odstrani);
    return ovoj;
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
    b.addEventListener("click", function () {
      klic("odpriMedijskiTok", [v.url]).then(function (ok) { if (!ok) obvesti(t("niUspelo")); })
        .catch(function () { obvesti(t("niUspelo")); });
    });
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
    b.addEventListener("click", function () { klic("splet", [v.url]).catch(function () { obvesti(t("niUspelo")); }); });
    return b;
  }
  function narisiMedije() {
    var kategorije = $("mediaKategorije"), mreza = $("mediaMreza");
    if (!kategorije || !mreza) return;
    var vsi = medijskiVnosi(), lokalni = S.mediaLokalno;
    kategorije.innerHTML = "";
    MEDIA_KATEGORIJE.forEach(function (k) {
      var b = el("button", "media-kategorija" + (S.mediaFilter === k[0] ? " izbrana" : ""),
        svg(k[1]) + '<span>' + ubezi(t("media_" + k[0])) + '</span>');
      b.type = "button"; b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", S.mediaFilter === k[0] ? "true" : "false");
      b.addEventListener("click", function () { S.mediaFilter = k[0]; naloziMedije(); });
      kategorije.appendChild(b);
    });
    var iskano = String(S.mediaIskanje || "").trim().toLocaleLowerCase();
    var vrsta = S.mediaFilter;
    var prikaz = lokalni.filter(function (v) { return (vrsta === "vse" || v.vrsta === vrsta ||
      vrsta === "video" && (v.vrsta === "filmi" || v.vrsta === "serije")) && mediaUstreza(v, iskano); });
    var viri = vsi.filter(function (v) { return (vrsta === "vse" || v.vrsta === vrsta) && mediaUstreza(v.program || v.spletna, iskano); });
    var tokovi = S.mediaTokovi.filter(function (v) { return (vrsta === "vse" || v.vrsta === vrsta) && mediaUstreza(v, iskano); });
    var dodani = spletne().map(function (v) { return kljucNaslova(v.url); });
    var predlogi = MEDIA_PREDLOGI.filter(function (v) { return (vrsta === "vse" || v.vrsta === vrsta) && mediaUstreza(v, iskano) && dodani.indexOf(kljucNaslova(v.url)) < 0; });
    $("mediaStevec").textContent = prikaz.length ? String(prikaz.length) : "";
    $("mediaNaslovZbirke").textContent = vrsta === "vse" ? t("mediaTvojaZbirka") : mediaVrsta(vrsta);
    $("mediaHeroNaslov").textContent = vrsta === "vse" ? t("mediaHeroNaslov") : mediaVrsta(vrsta);
    // Prazno stanje nagovarja k dodajanju mape samo, dokler zbirka nima ničesar.
    $("mediaHeroOpis").textContent = t(vrsta === "vse" && !lokalni.length && !S.mediaMape.length ? "mediaHeroOpis" : "mediaHeroOpisIzbor");
    var samoViri = vrsta === "tv" || vrsta === "radio";
    $("mediaMreza").previousElementSibling.hidden = samoViri;
    $("mediaMreza").hidden = samoViri;
    mreza.innerHTML = "";
    prikaz.forEach(function (v) { mreza.appendChild(mediaKartica(v)); });
    $("mediaPrazno").hidden = samoViri || prikaz.length !== 0;
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
    $("mediaHeroDejanje").onclick = function () { vrsta === "tv" || vrsta === "radio" ? $("medijiTok").click() : $("medijiMapa").click(); };
    $("mediaHeroDejanje").querySelector("span").textContent = t(samoViri ? "dodajTok" : "dodajMapoMedijev");
    osveziPredvajalnik(S.mediaPredvajalnik);
    // Brez krajevnih vsebin v izbrani kategoriji gre katalog pred prazno knjižnico (sicer bi ga odrivala navzdol).
    $("r-media").classList.toggle("brez-krajevnega", samoViri || prikaz.length === 0);
    uskladiKatalog();
  }
  function casMedija(sekunde) {
    sekunde = Math.max(0, Math.floor(Number(sekunde) || 0));
    return Math.floor(sekunde / 60) + ":" + String(sekunde % 60).padStart(2, "0");
  }
  function prikaziMediaBar() {
    var p = S.mediaPredvajalnik;
    $("mediaPlayerBar").hidden = !(p && p.naslov && p.stanje !== "ustavljeno");
  }
  function osveziPredvajalnik(p) {
    if (!p) return;
    S.mediaPredvajalnik = p;
    prikaziMediaBar();
    var ima = !!p.naslov;
    var opis = !ima ? t("mediaSedajNamig") : p.stanje === "napaka" ? t("mediaNapaka_" + (p.napaka || "splosno")) :
      p.stanje === "ustavljeno" ? t("mediaUstavljeno") : p.stanje === "premor" ? t("mediaPremor") :
      p.vrsta === "tv" || p.vrsta === "radio" ? t("mediaVZivo") : (p.izvor || t("mediaTaRacunalnik"));
    $("mediaBarNaslov").textContent = ima ? p.naslov : t("mediaNicesar");
    $("mediaBarVrsta").textContent = opis;
    $("mediaSedajNaslov").textContent = ima ? p.naslov : t("mediaNicesar");
    $("mediaSedajPod").textContent = opis;
    $("mediaSedajArt").textContent = p.vrsta === "tv" || p.vrsta === "video" ? "▶" : "♫";
    $("mediaBarOdpri").textContent = $("mediaSedajArt").textContent;
    // Tok v živo nima dolžine: drsnik in skupni čas skrijemo, ostane oznaka »V živo«.
    var zivo = p.vrsta === "tv" || p.vrsta === "radio";
    $("mediaBarNapredek").style.visibility = $("mediaBarTrajanje").style.visibility = zivo ? "hidden" : "";
    $("mediaBarPremor").textContent = p.stanje === "predvaja" ? "Ⅱ" : "▶";
    $("mediaBarPremor").disabled = !ima;
    $("mediaBarPrejsnja").disabled = !ima || p.indeks <= 0;
    $("mediaBarNaslednja").disabled = !ima || p.indeks >= (p.skupaj || 0) - 1;
    $("mediaBarUstavi").disabled = !ima || p.stanje === "ustavljeno";
    $("mediaBarCas").textContent = p.vrsta === "tv" || p.vrsta === "radio" ? t("mediaVZivo") : casMedija(p.pozicija);
    $("mediaBarTrajanje").textContent = p.vrsta === "tv" || p.vrsta === "radio" ? "" : casMedija(p.trajanje);
    $("mediaBarNapredek").disabled = !p.trajanje || p.vrsta === "tv" || p.vrsta === "radio";
    if (!S.mediaDragging)
      $("mediaBarNapredek").value = p.trajanje ? Math.round(1000 * p.pozicija / p.trajanje) : 0;
    $("mediaOdpriOkno").hidden = !ima || p.stanje === "ustavljeno" || p.vrsta === "radio";
    if (narisiSedajKatalog()) return;      // skladba iz kataloga: desni stolpec kaže njo in njeno vrsto
    var seznam = p.vrstaSeznam || [];
    $("mediaCakalnaStevec").textContent = String(p.skupaj || seznam.length);
    var podpis = p.indeks + "|" + (p.zacetniIndeks || 0) + "|" + seznam.map(function (v) { return v.naslov + v.vrsta; }).join("|");
    if (podpis === S.mediaQueueKey) return;
    S.mediaQueueKey = podpis;
    var vrstaEl = $("mediaVrsta"); vrstaEl.innerHTML = "";
    if (!seznam.length) vrstaEl.appendChild(el("p", "media-vrsta-prazna", ubezi(t("mediaVrstaPrazna"))));
    seznam.forEach(function (v, i) {
      var stevilka = i + (p.zacetniIndeks || 0);
      var b = el("button", "media-vrsta-vnos" + (stevilka === p.indeks ? " izbran" : ""),
        '<span class="media-vrsta-stevilka">' + (stevilka === p.indeks ? "♫" : String(stevilka + 1)) + '</span><span><b>' + ubezi(v.naslov) +
        '</b><small>' + ubezi(v.vrsta === "tv" || v.vrsta === "radio" ? t("mediaVZivo") : (v.izvor || t("mediaTaRacunalnik"))) + '</small></span>');
      b.addEventListener("click", function () { klic("predvajalnikUkaz", ["predvajaj", stevilka]); });
      vrstaEl.appendChild(b);
    });
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
  function odpriSplet(naslov, ime) {
    klic("splet", [naslov]).catch(function () { obvesti(t("niUspelo")); });
  }
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
    // Nosilci (USB kljuci, zunanji in drugi diski, omrezna mesta) so mape kot vse druge.
    (S.nosilci || []).forEach(function (n) {
      var g = el("button", S.pot === n.pot ? "izbran" : "", svg("arhiv") + "<span>" + ubezi(n.ime) + "</span>");
      g.addEventListener("click", function () { odpriMapo(n.pot); });
      seznam.appendChild(g);
    });
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
          var jeRacunalnik = !n.ta && (n.vrsta === "computer" || n.vrsta === "control" ||
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
      var zdaj = !s.telefon ? "intZdaj_brez" : (!s.prek_telefona ? "intZdaj_doma" : (sme ? "intZdaj_telefon" : "intZdaj_ne"));
      vrstice.appendChild(internetVrstica("povezava", t("intZdaj"), t(zdaj), !!s.prek_telefona && sme));
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
  var zvokStanje = null, zvokCas = 0, zvokDotik = 0, zvokCaka = "", zvokPotrdi = {};
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
    var pod = jblZaposleno ? t("jblPrenasam") : t("jblOpis");
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
  var scitStanje = null, scitZaposleno = false, scitCas = null;
  function nalozScit() {
    klic("scit").then(function (s) { scitStanje = s; narisiScit(); }, function () {});
  }
  function scitZanka() {
    clearInterval(scitCas);
    scitCas = setInterval(function () {
      if (S.razdelek !== "nastavitve") { clearInterval(scitCas); return; }
      // Seznam nazadnje blokiranih naj ne skoci izpod kazalca ali izbranega gumba (»Dovoli« bi zadel napacno domeno).
      var blok = $("blokScit");
      if (blok && blok.querySelector(".scit-zadnje:hover, .scit-zadnje button:focus")) return;
      if (!scitZaposleno) nalozScit();
    }, 5000);
  }
  function narisiScit() {
    var c = $("blokScit");
    c.innerHTML = "";
    var s = scitStanje;
    if (!s) return;
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
    function poScitu(r) { if (r) scitStanje = r; narisiScit(); }
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
    // Naprave v Safeer Linku
    var l = $("zvokLink");
    l.innerHTML = "";
    link.naprave.forEach(function (n) {
      var tece = naLinku === n.id, caka = zvokCaka === n.id && !tece;
      var ikona = (n.platforma === "tablet" || n.platforma === "phone") ? "naprave" : "zaslon";
      var gumb;
      if (tece) {
        gumb = el("span", "dejanja");
        var st = (link.zvok.stanje === "tece") ? "zvokPredvaja" : "zvokPovezujem";
        gumb.appendChild(el("span", "znacka" + (link.zvok.stanje === "tece" ? " tece" : ""), ubezi(t(st))));
        var ust = el("button", "gumb", ubezi(t("ustavi")));
        ust.addEventListener("click", function (e) {
          e.stopPropagation();
          klic("zvokUstavi").then(function () { zvokCaka = ""; obvesti(t("zvokNazaj")); setTimeout(nalozZvok, 600); });
        });
        gumb.appendChild(ust);
      } else {
        gumb = el("button", "gumb" + (caka ? "" : " glavni"), ubezi(t(caka ? "zvokPovezujem" : "predvajajTukaj")));
        gumb.addEventListener("click", function (e) {
          e.stopPropagation();
          zvokCaka = n.id;
          narisiZvok(z);
          klic("zvokNaNapravo", [n.id]).then(function (ok) {
            if (!ok) { zvokCaka = ""; obvesti(t("niUspelo")); } else obvesti(t("zvokNaNapravoZacet", { ime: n.ime }));
            setTimeout(nalozZvok, 800); setTimeout(function () { zvokCaka = ""; nalozZvok(); }, 6000);
          });
        });
      }
      l.appendChild(zvokVrstica(ikona, n.ime, "Safeer Link", tece, gumb));
    });
    // Zvocniki v omrezju (DLNA, npr. JBL): enako kot naprave v Linku, zvok racunalnika gre nanje.
    var zv = link.zvocnik || {}, naZvocniku = zv.naprava || "";
    (link.zvocniki || []).forEach(function (n) {
      var tece = naZvocniku === n.id, caka = zvokCaka === n.id && !tece, potrdi = zvokPotrdi[n.id];
      var gumb;
      if (tece) {
        gumb = el("span", "dejanja");
        gumb.appendChild(el("span", "znacka" + (zv.stanje === "tece" ? " tece" : ""), ubezi(t(zv.stanje === "tece" ? "zvokPredvaja" : "zvokPovezujem"))));
        var ust = el("button", "gumb", ubezi(t("ustavi")));
        ust.addEventListener("click", function (e) {
          e.stopPropagation();
          klic("zvokUstaviZvocnik").then(function () { zvokCaka = ""; obvesti(t("zvokNazaj")); setTimeout(nalozZvok, 600); });
        });
        gumb.appendChild(ust);
      } else {
        gumb = el("button", "gumb" + (caka ? "" : " glavni"),
          ubezi(caka ? t("zvokPovezujem") : (potrdi ? t("zvokZvocnikPreklopi", { vir: potrdi }) : t("predvajajTukaj"))));
        gumb.addEventListener("click", function (e) {
          e.stopPropagation();
          var soglasje = !!zvokPotrdi[n.id];
          zvokCaka = n.id; delete zvokPotrdi[n.id];
          narisiZvok(z);
          klic("zvokNaZvocnik", [n.id, soglasje]).then(function (r) {
            zvokCaka = "";
            if (r && r.vir) { zvokPotrdi[n.id] = r.vir; obvesti(t("zvokZvocnikZaseden", { ime: n.ime, vir: r.vir })); }
            else if (!r || !r.ok) obvesti(t("niUspelo"));
            else obvesti(t("zvokNaNapravoZacet", { ime: n.ime }));
            nalozZvok(); setTimeout(nalozZvok, 3000);
          });
        });
      }
      var pod = t("zvokZvocnik") + (n.model && n.model !== n.ime ? " · " + n.model : "");
      l.appendChild(zvokVrstica("zvok", n.ime, pod, tece, gumb));
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
  var SKUPINE_NASTAVITEV = [
    ["g_videz", "paleta", ["backgrounds", "themes", "fonts", "effects", "desktop", "panel", "applets", "desklets", "extensions"]],
    ["g_zaslon", "zaslon", ["display", "nightlight", "screensaver", "sound", "power", "o:posnetek-zaslona"]],
    ["g_naprave", "naprave", ["o:omrezje", "o:bluetooth", "mouse", "keyboard", "gestures", "o:tiskalniki", "thunderbolt"]],
    ["g_sistem", "drsniki", ["user", "privacy", "default", "startup", "calendar", "notifications", "accessibility", "windows",
                            "workspaces", "hotcorner", "general", "actions", "o:jezik"]],
    ["g_vzdrzevanje", "scit", ["o:posodobitve", "o:programska-oprema", "o:gonilniki", "o:varnostne-kopije", "o:kopije-datotek",
                               "o:opravila", "o:diski", "o:sistemsko-porocilo", "o:viri-programov", "o:terminal", "o:datoteke"]]
  ];
  var IKONA_NASTAVITVE = {
    backgrounds: "slika", themes: "paleta", fonts: "dokument", display: "zaslon", nightlight: "luna", screensaver: "zakleni",
    sound: "zvok", power: "napajanje", mouse: "miska", keyboard: "tipkovnica", user: "uporabnik", privacy: "scit",
    notifications: "zvonec", calendar: "ura", startup: "ponovno", "posodobitve": "ponovno", "programska-oprema": "programi",
    "gonilniki": "program", "varnostne-kopije": "ura", "kopije-datotek": "arhiv", "opravila": "drsniki", "diski": "disk",
    "omrezje": "ethernet", "bluetooth": "bluetooth", "tiskalniki": "tiskalnik", "terminal": "program", "datoteke": "mapa",
    "posnetek-zaslona": "slika", "jezik": "splet", "viri-programov": "arhiv", "sistemsko-porocilo": "dokument",
    windows: "namizje", workspaces: "programi", desktop: "namizje", panel: "namizje", accessibility: "uporabnik"
  };
  function seznamNastavitev() {
    var r = (S.zacetek && S.zacetek.razpolozljivo) || { moduli: [], orodja: [] };
    var izhod = [];
    SKUPINE_NASTAVITEV.forEach(function (g) {
      var elementi = [];
      g[2].forEach(function (k) {
        var orodje = k.indexOf("o:") === 0, kljuc = orodje ? k.slice(2) : k;
        if ((orodje ? r.orodja : r.moduli).indexOf(kljuc) < 0) return;
        elementi.push({ modul: kljuc, ime: t((orodje ? "o_" : "m_") + kljuc), ikona: IKONA_NASTAVITVE[kljuc] || g[1] });
      });
      if (elementi.length) izhod.push({ naslov: t(g[0]), elementi: elementi });
    });
    return izhod;
  }
  function odpriNastavitev(n) {
    // Omrezje ima Safeer OS svojo stran; Mintovo okno ostane pod »Napredno«.
    if (n.modul === "omrezje") { pojdi("omrezje"); return; }
    // Zvok ima Safeer OS svojo stran (izhodi, programi, naprave v Linku); Mintovo okno je pod »Napredno«.
    if (n.modul === "sound") { pojdi("zvok"); return; }
    obvesti(t("odpiram", { ime: n.ime }));
    klic("nastavitve", [n.modul]).then(function (ok) { if (!ok) obvesti(t("niUspelo")); });
  }
  // ------------------------------------------------------------------ posodobitve (safeer.si/os/razlicice.json)
  S.posodobitve = { stanje: null, zanka: 0 };
  function narisiPosodobitve(st) {
    S.posodobitve.stanje = st;
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
      pod.textContent = novo + ((st.nacin === "deb" || st.nacin === "windows") ? t("posodobitevNaVoljoPod") : (st.nacin === "flatpak" || st.nacin === "appimage") ? t("posodobitevNaVoljoFlatpak") : t("posodobitevRocnoPod"));
      return;
    }
    naslov.textContent = t("posodobitevNajnovejsa", { v: (st && st.nasa) || (S.zacetek && S.zacetek.razlicica) || "" });
    pod.textContent = st && st.napaka ? t("posodobitevNapaka", { napaka: st.napaka }) : t("posodobitevNajnovejsaPod");
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
  function posodobi() {
    var st = S.posodobitve.stanje;
    if (!st || !st.nove || !st.nove.length) { nalozPosodobitve(true); return; }
    if (st.nacin !== "deb" && st.nacin !== "flatpak" && st.nacin !== "appimage" && st.nacin !== "windows") { klic("splet", [st.stran || "https://safeer.si/os/"]); return; }
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
    // Safeer od vklopa (zagonski in prijavni zaslon): samo, ce je namescen paket safeer-cinnamon s pomocnikom.
    var odVklopa = S.zacetek && S.zacetek.odVklopa;
    $("stikaloOdVklopa").hidden = !(odVklopa && odVklopa.na_voljo);
    $("stikaloOdVklopa").setAttribute("aria-checked", odVklopa && odVklopa.vklopljeno ? "true" : "false");
    var cilj = $("skupineNastavitev");
    cilj.innerHTML = "";
    seznamNastavitev().forEach(function (g) {
      cilj.appendChild(el("h2", "", ubezi(g.naslov)));
      var m = el("div", "nastavitve-mreza");
      g.elementi.forEach(function (n) {
        var b = el("button", "nastavitev", svg(n.ikona) + "<span>" + ubezi(n.ime) + "</span>");
        b.addEventListener("click", function () { odpriNastavitev(n); });
        m.appendChild(b);
      });
      cilj.appendChild(m);
    });
    $("oSistemu").textContent = t("razlicica", { v: (S.zacetek && S.zacetek.razlicica) || "" }) +
      (S.zacetek ? " · " + S.zacetek.racunalnik : "");
    if (!S.stanje) klic("stanje").then(function (s) { narisiStanje(s); kontrole($("hitreNastavitve"), false); }, function () {});
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
  function odpriMint() {
    zapriSloje();
    $("mintZaStalno").hidden = !(S.zacetek && S.zacetek.samozagon);
    $("slojMint").classList.add("viden");
    setTimeout(function () { $("mintSamoTokrat").focus(); }, 30);
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
      S.sporocilaSkupine = p.skupine || []; S.sporocilaKanali = p.kanali || [];
      narisiSporocila(); uskladiOdprtPogovor();
    }).catch(function () { narisiSporocila(); });
  }
  function kanalIkona(vrsta) { return vrsta === "email" ? "sporocila" : vrsta === "safeer" ? "povezava" : "sporocila"; }
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
    S.sporocilaKanali.forEach(function (k) {
      var opis = stanjeKanala(k);
      var b = el("button", "kanal-cip" + (opis ? " napaka" : ""));
      b.type = "button";
      b.innerHTML = "<i></i><span>" + ubezi(k.ime) + "</span>" + (opis ? "<small>" + ubezi(opis) + "</small>" : "");
      b.addEventListener("click", function () { if (k.vrsta === "safeer") odpriPisiNapravi(); else odpriUrejanjeKanala(k); });
      cilj.appendChild(b);
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
    $("slojKanalUredi").classList.add("viden"); $("kanalUrediGeslo").focus();
  }
  function narisiSporocila() {
    narisiKanale();
    var cilj = $("sporocilaSeznam"); if (!cilj) return; cilj.innerHTML = "";
    var kaj = S.sporocilaFilter;
    S.sporocilaSkupine.forEach(function (skupina) {
      (skupina.pogovori || []).forEach(function (p) {
        var vrsta = (p.kanal || {}).vrsta || "";
        if (kaj && vrsta !== kaj) return;
        var b = el("button", "pogovor-vrstica" + (S.sporocilaAktivni && S.sporocilaAktivni.id === p.id && S.sporocilaAktivni.kanal_id === p.kanal_id ? " izbran" : ""));
        b.innerHTML = '<span class="kanal-ikona">' + svg(kanalIkona(vrsta)) + '</span><span><b>' + ubezi(skupina.oseba.ime) +
          '</b><small>' + ubezi(p.zadnje_sporocilo || p.zadeva || "") + '</small></span><span><time>' +
          ubezi(kratekCas(p.cas)) + '</time>' + (p.neprebrano ? '<i>' + Number(p.neprebrano) + '</i>' : '') + '</span>';
        b.addEventListener("click", function () { odpriPogovor(skupina.oseba, p); }); cilj.appendChild(b);
      });
    });
    if (!cilj.children.length) cilj.appendChild(el("p", "prazno", ubezi(t("niPogovorov"))));
  }
  function odpriPogovor(oseba, pogovor) {
    S.sporocilaAktivni = pogovor; narisiSporocila();
    $("sporocilaNaslov").textContent = oseba.ime + " · " + ((pogovor.kanal || {}).ime || "");
    var vnos = $("sporocilaBesedilo"), gumb = $("sporocilaVnos").querySelector("button");
    vnos.disabled = false; gumb.disabled = false;
    naloziVsebinoPogovora(pogovor);
  }
  function naloziVsebinoPogovora(pogovor) {
    klic("sporocilaPogovor", [pogovor.kanal_id, pogovor.id]).then(function (seznam) {
      if (S.sporocilaAktivni !== pogovor) return;   // uporabnik je medtem odprl drug pogovor
      var cilj = $("sporocilaVsebina"); cilj.innerHTML = "";
      (seznam || []).forEach(function (s) {
        var m = el("div", "mehurcek " + (s.smer === "ven" ? "ven" : "noter"));
        m.textContent = s.besedilo || ""; m.appendChild(el("time", "", ubezi(kratekCas(s.cas)))); cilj.appendChild(m);
      }); cilj.scrollTop = cilj.scrollHeight;
      if (pogovor.neprebrano) { pogovor.neprebrano = 0; naloziSporocila(); }
    });
  }
  /* Po osvezitvi seznama: odprt pogovor dobi nova sporocila, izginul (odstranjen kanal) se zapre.
     Prej je desna stran ostala na starem stanju, dokler pogovora nisi znova odprl. */
  function uskladiOdprtPogovor() {
    var a = S.sporocilaAktivni; if (!a) return;
    var nov = null;
    S.sporocilaSkupine.forEach(function (s) {
      (s.pogovori || []).forEach(function (p) { if (p.id === a.id && p.kanal_id === a.kanal_id) nov = p; });
    });
    if (!nov) {
      S.sporocilaAktivni = null;
      $("sporocilaNaslov").textContent = t("izberiPogovor");
      $("sporocilaVsebina").innerHTML = "";
      $("sporocilaBesedilo").disabled = true; $("sporocilaVnos").querySelector("button").disabled = true;
      narisiSporocila();
      return;
    }
    if (nov.cas !== a.cas || nov.zadnje_sporocilo !== a.zadnje_sporocilo) {
      S.sporocilaAktivni = nov; narisiSporocila(); naloziVsebinoPogovora(nov);
    }
  }
  var sporocilaCasovnik = 0;
  function sporocilaZanka() {
    if (sporocilaCasovnik) return;
    sporocilaCasovnik = setInterval(function () {
      if (S.razdelek !== "sporocila") { clearInterval(sporocilaCasovnik); sporocilaCasovnik = 0; return; }
      naloziSporocila();
    }, 30000);
  }
  function odpriCarovnikKanala() { zapriSloje(); preklopiKanalPolja(); $("kanalNapaka").hidden = true; $("slojKanal").classList.add("viden"); $("kanalNaslov").focus(); }
  function preklopiKanalPolja() {
    var email = $("kanalVrsta").value === "email"; $("kanalEmail").hidden = !email; $("kanalChatwoot").hidden = email;
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
                klic("odpriLokalniMedij", [v.pot]).then(function (ok) { if (!ok) obvesti(t("niUspelo")); })
                  .catch(function () { obvesti(t("niUspelo")); });
              }));
          });
          tokovi.forEach(function (v) {
            mestoLokalnihMedijev.appendChild(zadetek(v.vrsta === "radio" ? "radio" : "video", v.ime,
              mediaVrsta(v.vrsta), function () {
                pojdi("media");
                klic("odpriMedijskiTok", [v.url]).then(function (ok) { if (!ok) obvesti(t("niUspelo")); })
                  .catch(function () { obvesti(t("niUspelo")); });
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

  function zapriSloje() {
    if (S.galerija) zapriGalerijo();
    document.querySelectorAll(".sloj").forEach(function (s) { s.classList.remove("viden"); });
    if ($("iskanje").value && document.activeElement !== $("iskanje")) $("iskanje").value = "";
  }

  // ------------------------------------------------------------------ Safeer Media: katalog
  // Filmi, serije, glasba, radio, TV v živo, seznami predvajanja in dodatki – isto jedro (core/os_media.py) in isti
  // klici mostu (media*) kot Safeer OS za Windows; krajevna knjižnica zgoraj ostane taka, kot je. Razlika je samo
  // predvajanje: stran sama ne predvaja ničesar (tuje vsebine v stran Safeer OS ne vgrajujemo). Tok in datoteko
  // predvaja domači predvajalnik (GStreamer), skladbo s seznama predvajanja vgradni predvajalnik YouTuba v lahkem
  // medijskem pogledu; ob koncu skladbe safeer_os.py pošlje dogodek »mediaKonec« in stran iz vrste izbere naslednjo.
  var kat = { katalog: [], viri: [], filter: "vse", genre: "", query: "", page: 1, skupaj_strani: 1, skupaj: null,
              aktivni: null, zahteva: 0, timer: 0, kljuc: "", razvrsti: "", izklopljeni: {}, znaniViri: {},
              izklopljeniJeziki: {}, znaniJeziki: {}, jezikVsebine: "", jezikiZa: null, seznami: [], seznam: null,
              vrsta: [], vrstaMesto: 0, vrstaZgodovina: [], izVrste: false,
              igra: false, nalozen: false, zanri: null, zahtevaPredvajanja: 0, knjiznica: [], zahtevaKnjiznice: 0 };
  // Kategorije Medijskega centra (zgoraj) -> vrsta v katalogu; slike so samo krajevne.
  var KAT_VRSTE = { vse: "vse", glasba: "glasba", video: "video", filmi: "film", serije: "serija", tv: "tv-v-zivo", radio: "radio", slike: "" };
  var KAT_FILMSKI_ZANRI = [["28", "katZanr_akcija"], ["878", "katZanr_scifi"], ["35", "katZanr_komedija"], ["27", "katZanr_grozljivka"],
                           ["18", "katZanr_drama"], ["53", "katZanr_triler"], ["16", "katZanr_animirani"], ["10749", "katZanr_romantika"]];
  // Jezik vsebine (izbira poleg zvrsti): isti seznam kot core/izvirni_jezik.py - enakost varuje preizkus.
  var KAT_JEZIKI = ["sl", "en", "de", "fr", "es", "it", "pt", "hr", "sr", "bs", "mk", "ru", "pl", "cs", "sk", "hu", "nl", "sv", "da",
                    "no", "fi", "is", "tr", "el", "ro", "bg", "sq", "uk", "ja", "ko", "zh", "hi", "ta", "te", "th", "ar", "he", "fa"];
  function jezikVelja(filter) { return filter === "vse" || filter === "film" || filter === "serija" || filter === "video" || filter === "glasba"; }
  // Izbrani jezik vsebine za pogled, ki ga katalog kaze ("" = vsi jeziki ali pogled brez te izbire).
  function izbranJezik() { return !kat.seznam && jezikVelja(kat.filter) ? (kat.jezikVsebine || "") : ""; }
  function katIkona(vrsta) { return vrsta === "glasba" || vrsta === "podcast" ? "glasba" : vrsta === "radio" ? "radio" : "video"; }
  function katOznaka(vrsta) {
    var k = { glasba: "media_glasba", video: "media_video", radio: "media_radio", "tv-v-zivo": "media_tv", serija: "media_serije",
              film: "media_filmi", slika: "media_slike" }[vrsta];
    return k ? t(k) : (vrsta === "podcast" ? "Podcast" : t("media_filmi"));
  }
  function katVidno() { return S.razdelek === "media"; }
  function katSplet(url) { if (url) klic("splet", [url]).catch(function () { obvesti(t("niUspelo")); }); }

  function narisiStranjevanje() {
    var c = $("mediaStranjevanje"); if (!c) return; c.innerHTML = "";
    if (kat.skupaj_strani <= 1) return;
    var skok = function (n) { kat.page = n; naloziKatalog(); $("katalog").scrollIntoView({ block: "start" }); };
    var prev = el("button", "gumb", ubezi(t("katPrejsnjaStran"))); prev.type = "button";
    prev.disabled = kat.page <= 1;
    prev.onclick = function () { if (kat.page > 1) skok(kat.page - 1); };
    var info = el("span", "stran-info", ubezi(t("katStran", { a: kat.page, b: kat.skupaj_strani })));
    var next = el("button", "gumb", ubezi(t("katNaslednjaStran"))); next.type = "button";
    next.disabled = kat.page >= kat.skupaj_strani;
    next.onclick = function () { if (kat.page < kat.skupaj_strani) skok(kat.page + 1); };
    c.appendChild(prev); c.appendChild(info); c.appendChild(next);
  }

  function narisiKatalog() {
    var mreza = $("katMreza"); if (!mreza) return; mreza.innerHTML = "";
    var zanriEl = $("mediaZanri");
    var izSeznama = !!kat.seznam;
    if (zanriEl) zanriEl.hidden = izSeznama || !skupinaZanrov(kat.filter);
    narisiJezikVsebine();
    narisiSeznamePredvajanja();
    narisiKnjiznico();
    // Odprt seznam predvajanja: mreža kaže njegove skladbe v vrstnem redu seznama (brez združevanja po izvajalcu).
    var list = izSeznama ? kat.seznam.vnosi.slice() : kat.katalog.slice();
    $("katPrazno").hidden = !!list.length || !kat.nalozen;
    // Prazen katalog pri izbranem jeziku: povemo, da je prazno zaradi izbire (ne »ni zadetkov«).
    $("katPrazno").textContent = izbranJezik() ? t("katPraznoJezik", { jezik: imeJezika(kat.jezikVsebine, true) }) : t("katPrazno");
    $("mediaPovzetek").textContent = izSeznama || !kat.nalozen ? "" :
      t("katZadetkov", { n: kat.skupaj != null ? kat.skupaj : list.length }) +
      (kat.skupaj_strani > 1 ? " · " + t("katStran", { a: kat.page, b: kat.skupaj_strani }) : "");
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
    var zadnjaSkupina = "";
    list.forEach(function (x) {
      var skupina = izSeznama ? "" : (x.skupina || (kat.filter === "glasba" ? x.izvajalec : ""));
      if (zdruzi && skupina && skupina !== zadnjaSkupina) {
        zadnjaSkupina = skupina;
        mreza.appendChild(el("h3", "kat-skupina", ubezi(zadnjaSkupina)));
      }
      var card = el("button", "kat-kartica"); card.type = "button";
      card.setAttribute("aria-label", (x.naslov || "") + " — " + katOznaka(x.vrsta));
      if (x.slika) {
        var image = document.createElement("img"); image.alt = ""; image.loading = "lazy"; image.src = x.slika;
        image.onerror = function () { image.replaceWith(el("span", "kat-brez-slike", svg(katIkona(x.vrsta)))); };
        card.appendChild(image);
      } else card.appendChild(el("span", "kat-brez-slike", svg(katIkona(x.vrsta))));
      var data = el("span", "kat-podatki");
      data.appendChild(el("b", "", ubezi(x.naslov || "")));
      var meta = el("span", "kat-meta");
      var metaOznaka = katOznaka(x.vrsta);
      if (x.v_zivo) metaOznaka += " · " + t("katVZivo");
      if (x.codec || x.bitrate) metaOznaka += " · " + [x.codec, x.bitrate ? x.bitrate + " kb/s" : ""].filter(Boolean).join(" ");
      if (x.vrsta === "serija" && (x.sezona || x.epizoda)) {
        metaOznaka += " · S" + String(x.sezona || 1).padStart(2, "0") + "E" + String(x.epizoda || 1).padStart(2, "0");
      }
      if (x.leto) metaOznaka += " · " + x.leto;
      // Skladba: pod naslovom izvajalec (koga pričakovati), ne splošna oznaka »Glasba«.
      if ((izSeznama || x.vrsta === "glasba") && x.izvajalec) metaOznaka = x.izvajalec;
      meta.appendChild(el("span", "", ubezi(metaOznaka)));
      if (x.stevilo_razlicic > 1) meta.appendChild(el("span", "", ubezi(t("katRazlicic", { n: x.stevilo_razlicic }))));
      data.appendChild(meta); card.appendChild(data);
      // Kakovost pokažemo le, če jo poznamo – »HD« na filmu iz leta 1938 bi bil zavajajoč.
      var znacka = x.kakovost || (x.vrsta === "tv-v-zivo" ? t("katVZivo") : "");
      if (znacka) card.appendChild(el("span", "kat-kakovost", ubezi(znacka)));
      if (Number(x.ocena || 0) > 0) card.appendChild(el("span", "kat-ocena", "★ " + Number(x.ocena).toFixed(1)));
      if (izSeznama) {
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
      card.onclick = function () {
        if (x.tmdb_id || x.vrsta === "serija" || (x.vrsta === "film" && !x.peertube_uuid)) {
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
    if (izSeznama) { var str = $("mediaStranjevanje"); if (str) str.innerHTML = ""; } else narisiStranjevanje();
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
  function narisiKnjiznico() {
    var c = $("mediaKnjiznica"); if (!c) return; c.innerHTML = "";
    var vnosi = knjiznicaVidna() ? (kat.knjiznica || []) : [];
    c.hidden = !vnosi.length;
    if (!vnosi.length) return;
    c.appendChild(el("h3", "", ubezi(t("knjiznicaNaslov"))));
    var vrsta = el("div", "kat-knjiznica-vrsta");
    vnosi.forEach(function (x) {
      var card = el("button", "kat-kartica"); card.type = "button";
      var kje = knjiznicaKje(x);
      card.setAttribute("aria-label", (x.naslov || "") + " — " + kje);
      card.title = (x.naslov || "") + " · " + kje;
      if (x.slika) {
        var image = document.createElement("img"); image.alt = ""; image.loading = "lazy"; image.src = x.slika;
        image.onerror = function () { image.replaceWith(el("span", "kat-brez-slike", svg("video"))); };
        card.appendChild(image);
      } else card.appendChild(el("span", "kat-brez-slike", svg("video")));
      var data = el("span", "kat-podatki");
      data.appendChild(el("b", "", ubezi(x.naslov || "")));
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
    c.appendChild(vrsta);
  }
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
    return klic("mediaSeznami").then(function (s) { kat.seznami = s || []; narisiSeznamePredvajanja(); }, function () {});
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
      glava.appendChild(el("small", "", ubezi(stSkladb(sz.vnosi.length) + (sz.vir ? " · " + sz.vir : ""))));
      var vse = el("button", "gumb glavni", ubezi("▶ " + t("seznamPredvajajVse"))); vse.type = "button";
      vse.onclick = function () { var prvi = sz.vnosi[0]; if (prvi) { nastaviVrsto(prvi); odpriKatalogVnos(prvi.id); } };
      glava.appendChild(vse);
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
    m.style.left = Math.max(12, Math.min(window.innerWidth - m.offsetWidth - 12, r.left)) + "px";
    m.style.top = Math.max(12, Math.min(window.innerHeight - m.offsetHeight - 12, r.bottom + 6)) + "px";
  }
  document.addEventListener("click", function (e) {
    var m = $("mediaSeznamMeni");
    if (m && !m.hidden && !e.target.closest("#mediaSeznamMeni") && !e.target.closest(".kat-na-seznam")) m.hidden = true;
    var plosca = $("mediaViriFilter");
    if (plosca && !plosca.hidden && !e.target.closest(".kat-filter-viri")) {
      plosca.hidden = true; $("mediaViriFilterGumb").setAttribute("aria-expanded", "false");
    }
  });

  // ---- trak »predvaja se«: skladba iz kataloga ali s seznama (naslov, prejšnja/premor/naslednja, premešaj, ponovi)
  function osveziKatTrak() {
    var pl = $("mediaPredvajalnik"), item = kat.aktivni;
    if (!pl) return;
    pl.hidden = !(item && item.zvok);
    if (pl.hidden) { osveziSedajKatalog(); return; }
    $("mediaPredvajalnikNaslov").textContent = item.naslov || "";
    $("mediaPredvajalnikMeta").textContent = [item.izvajalec, kat.seznam && kat.seznam.ime, item.vir].filter(Boolean).join(" · ");
    $("mediaKatPremor").innerHTML = kat.igra ? "&#10074;&#10074;" : "&#9654;";
    narisiVrsto();
    osveziSedajKatalog();
  }
  // Desni stolpec (»Zdaj se predvaja« in čakalna vrsta) velja tudi za skladbe iz kataloga in s seznamov
  // predvajanja: skladba v vgradnem predvajalniku ne gre skozi domači predvajalnik, vrsto pa vodi stran.
  function narisiSedajKatalog() {
    var item = kat.aktivni;
    if (!item || !item.zvok) return false;
    if (item.okno_youtube) {
      $("mediaSedajNaslov").textContent = item.naslov || "";
      $("mediaSedajPod").textContent = kat.igra ? (item.izvajalec || (kat.seznam && kat.seznam.ime) || "") : t("mediaPremor");
      $("mediaSedajArt").textContent = "♫";
      $("mediaOdpriOkno").hidden = true;
    }
    var vnosi = (kat.vrsta || []).length ? (kat.vrstaVnosi || []) : [];
    if (vnosi.length < 2 && !item.okno_youtube) return false;
    if (!vnosi.length) vnosi = [item];
    var mesto = Math.max(0, Math.min(vnosi.length - 1, kat.vrstaMesto || 0));
    var od = Math.max(0, Math.min(mesto - 2, vnosi.length - 30)), prikaz = vnosi.slice(od, od + 30);
    $("mediaCakalnaStevec").textContent = String(vnosi.length);
    var podpis = "kat|" + mesto + "|" + od + "|" + vnosi.length + "|" + (prikaz[0] && prikaz[0].id);
    if (podpis === S.mediaQueueKey) return true;
    S.mediaQueueKey = podpis;
    var vrstaEl = $("mediaVrsta"); vrstaEl.innerHTML = "";
    prikaz.forEach(function (v, i) {
      var stevilka = od + i;
      var b = el("button", "media-vrsta-vnos" + (stevilka === mesto ? " izbran" : ""),
        '<span class="media-vrsta-stevilka">' + (stevilka === mesto ? "♫" : String(stevilka + 1)) + '</span><span><b>' + ubezi(v.naslov || "") +
        '</b><small>' + ubezi(v.izvajalec || v.vir || "") + '</small></span>');
      b.addEventListener("click", function () {
        if (stevilka === kat.vrstaMesto) return;
        (kat.vrstaZgodovina = kat.vrstaZgodovina || []).push(kat.vrstaMesto);
        kat.vrstaMesto = stevilka; kat.izVrste = true; narisiVrsto(); odpriKatalogVnos(v.id);
      });
      vrstaEl.appendChild(b);
    });
    return true;
  }
  function osveziSedajKatalog() {
    if (narisiSedajKatalog()) { S.katSedaj = true; return; }
    if (!S.katSedaj) return;
    S.katSedaj = false; S.mediaQueueKey = null;          // nazaj na prikaz domačega predvajalnika
    osveziPredvajalnik(S.mediaPredvajalnik || { naslov: "", stanje: "ustavljeno", vrstaSeznam: [] });
  }
  function skrijKatTrak() { kat.aktivni = null; kat.igra = false; osveziKatTrak(); }
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
  function nastaviVrsto(zacetni) {
    // Skladba z odprtega seznama predvajanja: vrsta je seznam (v njegovem vrstnem redu), ne katalog.
    var osnova = kat.seznam && kat.seznam.vnosi.some(function (x) { return x.id === zacetni.id; }) ? kat.seznam.vnosi : (kat.prikazano || kat.katalog || []);
    var seznam = osnova.filter(function (x) { return x.vrsta === zacetni.vrsta && !x.stran; });
    kat.vrsta = seznam.map(function (x) { return x.id; });
    kat.vrstaVnosi = seznam;
    kat.vrstaMesto = Math.max(0, kat.vrsta.indexOf(zacetni.id));
    kat.vrstaZgodovina = [];
    narisiVrsto();
  }
  function naslednjiVVrsti(smer) {
    var n = (kat.vrsta || []).length;
    if (!n) return null;
    if (smer < 0) {
      if (kat.vrstaZgodovina && kat.vrstaZgodovina.length) return kat.vrstaZgodovina.pop();
      return (kat.vrstaMesto - 1 + n) % n;
    }
    if (vrstaNastavitev("ponovi", "0") === "1") return kat.vrstaMesto;          // ponovi skladbo
    if (vrstaNastavitev("premesaj", "0") === "1" && n > 1) {
      var r; do { r = Math.floor(Math.random() * n); } while (r === kat.vrstaMesto);
      return r;
    }
    var naslednji = kat.vrstaMesto + 1;
    return naslednji < n ? naslednji : (n > 1 && vrstaNastavitev("ponoviVse", "1") === "1" ? 0 : null);
  }
  function predvajajIzVrste(smer) {
    var mesto = naslednjiVVrsti(smer);
    if (mesto == null) return false;
    if (smer > 0) (kat.vrstaZgodovina = kat.vrstaZgodovina || []).push(kat.vrstaMesto);
    kat.vrstaMesto = mesto;
    narisiVrsto();
    kat.izVrste = true;
    odpriKatalogVnos(kat.vrsta[mesto]);
    return true;
  }
  function narisiVrsto() {
    var ima = (kat.vrsta || []).length > 1;
    ["mediaPrejsnja", "mediaNaslednja", "mediaPremesaj", "mediaPonovi"].forEach(function (id) { var g = $(id); if (g) g.hidden = !ima; });
    var pm = $("mediaPremesaj"), po = $("mediaPonovi");
    if (pm) pm.classList.toggle("vklopljen", vrstaNastavitev("premesaj", "0") === "1");
    if (po) po.classList.toggle("vklopljen", vrstaNastavitev("ponovi", "0") === "1");
  }

  function odpriKatalogVnos(id) {
    kat.izVrste = false;
    // Prenos, ki ga izdajatelj ponuja samo na svoji strani (npr. RTV SLO): odpremo ga v Spletu.
    var znan = (kat.katalog || []).filter(function (x) { return x.id === id; })[0];
    if (znan && znan.stran) { katSplet(znan.stran); return; }
    var zahteva = ++kat.zahtevaPredvajanja;
    klic("mediaPredvajaj", [id]).then(function (item) {
      if (zahteva !== kat.zahtevaPredvajanja) return;       // uporabnik je medtem izbral drugo vsebino
      if (!item) { obvesti(t("katNapakaVira")); return; }
      if (item.napaka_koda === "ni_toka") {
        // Noben vir tega ne predvaja: brez okna in brez strani – kratko obvestilo, film izgine iz mreže.
        obvesti(t("mediaNapaka_ni_toka", { ime: item.naslov || "" }));
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
      if (item.napaka_koda) { obvesti(t("mediaNapaka_" + item.napaka_koda)); return; }
      if (item.napaka) { obvesti(item.napaka); return; }
      if (item.sporocilo) { obvesti(item.sporocilo); return; }
      // »stran« ob predvajljivem toku je le izvor (npr. stran filma v arhivu); v Splet gre samo, kar nima toka.
      if (item.stran && !item.native) { katSplet(item.stran); return; }
      kat.aktivni = item; kat.igra = true;
      osveziKatTrak();
    }, function () { if (zahteva === kat.zahtevaPredvajanja) obvesti(t("katNapakaVira")); });
  }

  // ---- zvrsti pod kategorijami: pri filmih in serijah filmske (TMDB), pri glasbi, radiu in TV iz kataloga
  function skupinaZanrov(filter) {
    if (filter === "film" || filter === "serija" || filter === "vse") return "film";
    if (filter === "glasba" || filter === "radio" || filter === "tv-v-zivo") return filter;
    return "";
  }
  function izberiZanr(b) {
    kat.genre = b.getAttribute("data-media-genre") || "";
    kat.page = 1;
    $("mediaZanri").querySelectorAll("[data-media-genre]").forEach(function (q) { q.classList.toggle("izbran", q === b); });
    naloziKatalog();
  }
  function narisiZanre() {
    var vrstica = $("mediaZanri"); if (!vrstica) return;
    var skupina = skupinaZanrov(kat.filter);
    if (kat.zanri === skupina + "|" + jezik) return;
    kat.zanri = skupina + "|" + jezik;
    kat.genre = "";
    vrstica.innerHTML = "";
    vrstica.hidden = !skupina;
    if (!skupina) return;
    var gumb = function (id, napis, izbran) {
      var b = el("button", izbran ? "izbran" : ""); b.type = "button"; b.setAttribute("data-media-genre", id); b.textContent = napis;
      b.onclick = function () { izberiZanr(b); };
      vrstica.appendChild(b);
    };
    gumb("", t(skupina === "radio" ? "katVsePostaje" : skupina === "tv-v-zivo" ? "katVseDrzave" : skupina === "glasba" ? "katVsaGlasba" : "katVseVsebine"), true);
    if (skupina === "film") { KAT_FILMSKI_ZANRI.forEach(function (z) { gumb(z[0], t(z[1]), false); }); return; }
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
      if (x.jezik) kat.znaniJeziki[x.jezik] = 1;
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
  function osveziGumbViri() {
    var gumb = $("mediaViriFilterGumb"); if (!gumb) return;
    var n = Object.keys(kat.izklopljeni).length + Object.keys(kat.izklopljeniJeziki).length;
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
          osveziGumbViri(); kat.page = 1; naloziKatalog();
        };
        var besedilo = el("span"); besedilo.appendChild(el("b", "", ubezi(ime(id))));
        vrstica.appendChild(cb); vrstica.appendChild(besedilo); cilj.appendChild(vrstica);
      });
    };
    napolni($("mediaViriFilterSeznam"), Object.keys(kat.znaniViri).sort(function (a, b) { return String(kat.znaniViri[a]).localeCompare(String(kat.znaniViri[b])); }),
            function (id) { return kat.znaniViri[id]; }, kat.izklopljeni, "katViriNamig");
    napolni($("mediaJezikiFilterSeznam"), Object.keys(kat.znaniJeziki).sort(function (a, b) { return imeJezika(a).localeCompare(imeJezika(b)); }),
            imeJezika, kat.izklopljeniJeziki, "katJezikiNamig");
  }

  // Katalog pride najprej iz predpomnilnika (takoj); ko v ozadju prispejo sveži podatki, jih safeer_os.py pošlje kot
  // dogodek »mediaKatalogOsvezen« in pogled tiho posodobimo (drsnik ostane, kjer je).
  function prevzemiKatalog(response, tiho) {
    zapomniKatViri(response);
    if (!$("mediaViriFilter").hidden) narisiViriFilter();
    kat.kljuc = (response && response.kljuc) || "";
    kat.katalog = (response && response.vnosi) || [];
    if (response && response.viri) kat.viri = response.viri;
    kat.skupaj_strani = (response && response.skupaj_strani) || 1;
    kat.skupaj = (response && typeof response.skupaj === "number") ? response.skupaj : null;
    kat.nalozen = true;
    var drsnik = $("vsebina") || document.documentElement;
    var odmik = drsnik.scrollTop;
    narisiKatalog();
    if (tiho) drsnik.scrollTop = odmik;
  }
  function naloziKatalog() {
    var blok = $("katalog"); if (!blok || !most) return;
    blok.hidden = !kat.filter;
    if (!kat.filter) { $("r-media").classList.remove("ima-katalog"); return; }
    $("katNaslov").textContent = kat.filter === "vse" ? t("katVseVsebine") : katOznaka(kat.filter);
    narisiZanre();
    naloziSeznamePredvajanja();
    naloziKnjiznico();
    var zahteva = ++kat.zahteva;
    if (!kat.katalog.length) $("mediaPovzetek").textContent = t("katNalagam");
    klic("mediaKatalog", [kat.query, kat.filter, kat.genre, kat.page || 1, kat.razvrsti, Object.keys(kat.izklopljeni), false,
                          Object.keys(kat.izklopljeniJeziki), izbranJezik()]).then(function (response) {
      if (zahteva !== kat.zahteva) return;
      prevzemiKatalog(response);
    }, function () { if (zahteva === kat.zahteva) { kat.katalog = []; kat.nalozen = true; narisiKatalog(); } });
  }
  // Krajevna knjižnica je pravkar narisana (izbrana kategorija ali iskanje): katalog sledi isti izbiri.
  function uskladiKatalog() {
    var filter = KAT_VRSTE[S.mediaFilter] == null ? "vse" : KAT_VRSTE[S.mediaFilter];
    var query = String(S.mediaIskanje || "").trim();
    if (kat.nalozen && filter === kat.filter && query === kat.query && kat.jezik === jezik) return;
    var samoIskanje = kat.nalozen && filter === kat.filter && kat.jezik === jezik;
    kat.filter = filter; kat.query = query; kat.jezik = jezik; kat.page = 1; kat.seznam = null;
    clearTimeout(kat.timer);
    // Druga kategorija: kartice prejšnje takoj izginejo (sicer bi do odgovora kazali filme pod naslovom »Radio«).
    if (!samoIskanje) { kat.katalog = []; kat.nalozen = false; kat.skupaj = null; kat.skupaj_strani = 1; narisiKatalog(); }
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
        var info = el("div", "kat-epizoda-info");
        info.appendChild(el("b", "", "E" + String(ep.stevilka).padStart(2, "0") + "  " + ubezi(ep.naslov || t("katEpizoda"))));
        info.appendChild(el("small", "", ubezi([ep.datum, ep.trajanje ? ep.trajanje + " min" : "", ep.ocena ? "★ " + ep.ocena : ""].filter(Boolean).join(" · "))));
        if (ep.opis) info.appendChild(el("p", "", ubezi(ep.opis)));
        row.appendChild(info);
        var play = el("button", "gumb glavni", ubezi(t("katPredvajaj"))); play.type = "button";
        play.onclick = function () {
          klic("mediaEpizoda", [item.tmdb_id, season, ep.stevilka, item.naslov + " · " + ep.naslov]).then(function (entry) {
            if (entry && entry.id) { zapriKatalogPodrobnosti(); kat.vrsta = []; narisiVrsto(); odpriKatalogVnos(entry.id); }
            else obvesti(t("mediaNapaka_ni_toka", { ime: item.naslov || "" }));
          }, function () { obvesti(t("katNapakaVira")); });
        };
        row.appendChild(play); cilj.appendChild(row);
      });
      if (!episodes.length) cilj.appendChild(el("div", "prazno", ubezi(t("katBrezEpizod"))));
    }, function () { cilj.innerHTML = ""; cilj.appendChild(el("div", "prazno", ubezi(t("katBrezEpizod")))); });
  }
  function odpriKatalogPodrobnosti(id) {
    klic("mediaPodrobnosti", [id, jezik]).then(function (item) {
      if (!item) return;
      var panel = $("mediaPodrobnosti"); panel.hidden = false;
      var hero = $("mediaPodrobnostiJunak"); hero.innerHTML = "";
      if (item.slika) { var poster = document.createElement("img"); poster.src = item.slika; poster.alt = ""; hero.appendChild(poster); }
      var info = el("div"); info.appendChild(el("h2", "", ubezi(item.naslov || "")));
      info.appendChild(el("p", "kat-detail-meta", ubezi([item.leto, item.ocena ? "★ " + item.ocena : "", t(item.vrsta === "serija" ? "katSerija" : "katFilm")].filter(Boolean).join(" · "))));
      if (item.opis) info.appendChild(el("p", "", ubezi(item.opis)));
      hero.appendChild(info);
      narisiKjeGledati(item);
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
    }, function () { obvesti(t("katNapakaVira")); });
  }

  // ---- dodatki in viri (dodatek Stremio, osebni strežnik, spletni vir)
  function narisiKatViri() {
    var cilj = $("katViri"); if (!cilj) return; cilj.innerHTML = "";
    if (!kat.viri.length) { cilj.appendChild(el("p", "drobno", ubezi(t("katBrezVirov")))); return; }
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
  }
  function naloziKatViri() {
    return klic("mediaViri").then(function (viri) { kat.viri = Array.isArray(viri) ? viri : []; narisiKatViri(); }, function () {});
  }
  function odpriKatViri() {
    $("katVirSporocilo").textContent = "";
    $("slojKatViri").classList.add("viden");
    naloziKatViri();
    $("mediaStreznikUrl").focus();
  }
  function katPrilagodiObrazec() {
    // Dodatek in DLNA nimata prijave; polji za uporabnika in geslo pokažemo samo strežnikom, ki ju potrebujejo.
    var p = $("mediaStreznikVrsta").value, brez = p === "stremio" || p === "dlna";
    $("mediaStreznikUporabnik").hidden = brez; $("mediaStreznikSkrivnost").hidden = brez;
    $("mediaStreznikUrl").placeholder = t(p === "stremio" ? "katNaslovDodatka" : "katNaslovStreznika");
  }
  function poveziKatalog() {
    var ob = function (id, dogodek, fn) { var e = $(id); if (e) e.addEventListener(dogodek, fn); };
    ob("mediaRazvrsti", "change", function () { kat.razvrsti = this.value; kat.page = 1; naloziKatalog(); });
    ob("mediaJezik", "change", function () {
      kat.jezikVsebine = this.value; kat.page = 1;
      // Drug jezik: kartice prejsnjega takoj izginejo (jezik naslovov iz dodatkov se prvic poisce - to lahko traja).
      kat.katalog = []; kat.nalozen = false; kat.skupaj = null; kat.skupaj_strani = 1;
      narisiKatalog(); naloziKatalog();
    });
    ob("mediaViriFilterGumb", "click", function (event) {
      event.stopPropagation();
      var plosca = $("mediaViriFilter"), odpri = plosca.hidden;
      plosca.hidden = !odpri; this.setAttribute("aria-expanded", odpri ? "true" : "false");
      if (odpri) narisiViriFilter();
    });
    ob("mediaViriFilterPonastavi", "click", function () {
      kat.izklopljeni = {}; kat.izklopljeniJeziki = {};
      narisiViriFilter(); osveziGumbViri(); kat.page = 1; naloziKatalog();
    });
    ob("mediaPodrobnostiNazaj", "click", zapriKatalogPodrobnosti);
    ob("mediaPodrobnostiZapri", "click", zapriKatalogPodrobnosti);
    ob("mediaPrejsnja", "click", function () { predvajajIzVrste(-1); });
    ob("mediaNaslednja", "click", function () { predvajajIzVrste(1); });
    ob("mediaPremesaj", "click", function () { vrstaShrani("premesaj", vrstaNastavitev("premesaj", "0") === "1" ? "0" : "1"); narisiVrsto(); });
    ob("mediaPonovi", "click", function () { vrstaShrani("ponovi", vrstaNastavitev("ponovi", "0") === "1" ? "0" : "1"); narisiVrsto(); });
    ob("mediaKatPremor", "click", premorKatPredvajanja);
    ob("mediaZapri", "click", ustaviKatPredvajanje);
    ob("katDodatki", "click", odpriKatViri);
    ob("katViriZapri", "click", zapriSloje);
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
          naloziKatViri(); kat.page = 1; naloziKatalog();
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
        naloziKatViri(); kat.page = 1; naloziKatalog();
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
  }
  // Besedila ob menjavi jezika: napisi, ki jih ne nosi data-t (izbirnik razvrstitve, gumb virov, zvrsti).
  function prevediKatalog() {
    var r = $("mediaRazvrsti"); if (!r) return;
    [["", "katRazPriporoceno"], ["novo", "katRazNovo"], ["staro", "katRazStaro"], ["az", "katRazAZ"], ["za", "katRazZA"]].forEach(function (o, i) {
      if (!r.options[i]) r.add(new Option("", o[0]));
      r.options[i].textContent = t(o[1]);
    });
    kat.jezikiZa = null; narisiJezikVsebine();      // imena jezikov v novem jeziku vmesnika
    osveziGumbViri(); katPrilagodiObrazec();
  }
  function katDogodek(vrsta, podatki) {
    if (vrsta === "mediaKatalogOsvezen" && podatki && katVidno() && podatki.kljuc && podatki.kljuc === kat.kljuc) prevzemiKatalog(podatki, true);
    if (vrsta === "mediaNiNaVoljo" && podatki && podatki.idji && kat.katalog) {
      var prejKartic = kat.katalog.length;
      kat.katalog = kat.katalog.filter(function (x) { return podatki.idji.indexOf(x.id) < 0; });
      if (kat.katalog.length !== prejKartic) {
        if (typeof kat.skupaj === "number") kat.skupaj = Math.max(kat.katalog.length, kat.skupaj - (prejKartic - kat.katalog.length));
        if (katVidno()) { var drsnik = $("vsebina"), odmik = drsnik.scrollTop; narisiKatalog(); drsnik.scrollTop = odmik; }
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
    var zaAktivno = kat.aktivni && podatki && podatki.id === kat.aktivni.id;
    // Skladba je odigrana do konca (domači predvajalnik ali vgradni predvajalnik YouTuba): naslednja iz vrste.
    if (vrsta === "mediaKonec" && zaAktivno && !predvajajIzVrste(1)) skrijKatTrak();
    // Tipka ali daljinec »naslednja/prejšnja« pri skladbi iz kataloga: vrsto vodi stran.
    if (vrsta === "mediaVrstaUkaz" && kat.aktivni) predvajajIzVrste(Number(podatki) < 0 ? -1 : 1);
    if (vrsta === "mediaYt" && zaAktivno) { kat.igra = !!podatki.igra; osveziKatTrak(); }
    if (vrsta === "mediaYtZaprt" && zaAktivno) { kat.vrsta = []; skrijKatTrak(); }
    if (vrsta === "mediaYtNapaka" && zaAktivno) {
      // Lastnik posnetka vgradnje ne dovoli (ali posnetka ni več): poiščemo drug posnetek iste skladbe, sicer naslednja.
      var skladba = kat.aktivni;
      klic("mediaSeznamZamenjava", [skladba.id]).then(function (nova) {
        if (kat.aktivni !== skladba) return;
        if (nova && nova.youtube && nova.youtube !== skladba.youtube) { kat.izVrste = true; odpriKatalogVnos(skladba.id); return; }
        obvesti(t("seznamBrezPosnetka", { ime: skladba.naslov || "" }));
        if (!predvajajIzVrste(1)) ustaviKatPredvajanje();
      }, function () { if (kat.aktivni === skladba && !predvajajIzVrste(1)) ustaviKatPredvajanje(); });
    }
    // Stanje domačega predvajalnika: znak premora v traku sledi resničnemu stanju.
    if (vrsta === "predvajalnik" && kat.aktivni && kat.aktivni.zvok && !kat.aktivni.okno_youtube && podatki) {
      var igra = podatki.stanje === "predvaja";
      if (igra !== kat.igra) { kat.igra = igra; osveziKatTrak(); }
    }
  }

  // ------------------------------------------------------------------ dogodki iz safeer_os.py
  window.safeerOsDogodek = function (vrsta, podatki) {
    katDogodek(vrsta, podatki);
    if (vrsta === "stanje") narisiStanje(podatki);
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
    if (vrsta === "posodobitev") pokaziPosodobitevDoma(podatki);
    if (vrsta === "magnet") odpriMagnet(podatki && podatki.uri, podatki && podatki.samodejno === true);
    // Film iz torrenta (dodatek): med branjem torrenta in prenosom zacetka uporabnik vidi, da se nekaj dogaja.
    if (vrsta === "mediaTorrent") obvesti(t("mediaTorrentPripravljam", { ime: (podatki && podatki.naslov) || "" }));
    if (vrsta === "mediaMotor" && podatki) motorNapredek(podatki);
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
    if (vrsta === "pojdi") window.safeerOsPojdi(podatki);
    if (vrsta === "fokus") {
      osveziOkna();
      osveziStanje();
      osveziPovezavo();
      narisiNedavneDomov();
    }
  };

  // ------------------------------------------------------------------ zacetek
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
    $("pisiPreklici").addEventListener("click", zapriSloje);
    $("kanalPreklici").addEventListener("click", zapriSloje);
    $("kanalVrstaIzbira").querySelectorAll("button").forEach(function (b) {
      b.addEventListener("click", function () {
        $("kanalVrsta").value = b.getAttribute("data-vrsta");
        $("kanalVrstaIzbira").querySelectorAll("button").forEach(function (x) { x.classList.toggle("izbran", x === b); });
        preklopiKanalPolja();
      });
    });
    $("kanalNaslov").addEventListener("blur", function () {
      var naslov = this.value.trim(); if (naslov.indexOf("@") < 1) return;
      klic("sporocilaStreznik", [naslov]).then(function (p) {
        if (!$("kanalImap").value) $("kanalImap").value = p.imap || "";
        if (!$("kanalSmtp").value) $("kanalSmtp").value = p.smtp || "";
        var namig = p.namig === "aplikacije" ? t("namigGesloAplikacije") : p.namig === "oauth" ? t("namigOauth") : "";
        $("kanalNamig").textContent = namig; $("kanalNamig").hidden = !namig;
      });
    });
    $("kanalUrediPreklici").addEventListener("click", zapriSloje);
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
    $("sporocilaFiltri").querySelectorAll("button").forEach(function (b) {
      b.addEventListener("click", function () {
        S.sporocilaFilter = b.getAttribute("data-kanal-vrsta") || "";
        $("sporocilaFiltri").querySelectorAll("button").forEach(function (x) { x.classList.toggle("izbran", x === b); });
        narisiSporocila();
      });
    });
    $("obrazecKanal").addEventListener("submit", function (e) {
      e.preventDefault(); var email = $("kanalVrsta").value === "email";
      var p = email ? { vrsta:"email", naslov:$("kanalNaslov").value, imap:$("kanalImap").value,
        smtp:$("kanalSmtp").value, geslo:$("kanalGeslo").value } :
        { vrsta:"chatwoot", url:$("kanalUrl").value, account_id:Number($("kanalRacun").value), zeton:$("kanalZeton").value };
      var gumb = $("kanalPovezi"); gumb.disabled = true; gumb.textContent = t("povezujem");
      $("kanalNapaka").hidden = true;
      klic("sporocilaDodaj", [p]).then(function () {
        gumb.disabled = false; gumb.textContent = t("povezi");
        $("kanalGeslo").value = ""; $("kanalZeton").value = ""; zapriSloje(); naloziSporocila();
        setTimeout(naloziSporocila, 4000);
      }).catch(function (napaka) {
        gumb.disabled = false; gumb.textContent = t("povezi");
        $("kanalNapaka").textContent = String(napaka || t("niUspelo")); $("kanalNapaka").hidden = false;
      });
    });
    $("sporocilaVnos").addEventListener("submit", function (e) {
      e.preventDefault(); var p = S.sporocilaAktivni, besedilo = $("sporocilaBesedilo").value.trim();
      if (!p || !besedilo) return;
      klic("sporocilaPoslji", [p.kanal_id, p.id, besedilo]).then(function (r) {
        $("sporocilaBesedilo").value = ""; odpriPogovor({ ime: $("sporocilaNaslov").textContent.split(" · ")[0] }, p);
        naloziSporocila();          // seznam pokaze zadnje sporocilo takoj, ne sele ob naslednji osvezitvi
        if (r && r.caka) obvesti(t("klepetCaka"));
      }).catch(function (e) { obvesti(typeof e === "string" && e ? e : t("niUspelo")); });
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
    $("mediaBarOdpri").addEventListener("click", function () { klic("predvajalnikUkaz", ["odpri"]); });
    $("mediaOdpriOkno").addEventListener("click", function () { klic("predvajalnikUkaz", ["odpri"]); });
    [["mediaBarPremor", "premor"], ["mediaBarPrejsnja", "prejsnja"], ["mediaBarNaslednja", "naslednja"],
      ["mediaBarUstavi", "ustavi"]].forEach(function (x) {
      $(x[0]).addEventListener("click", function () { klic("predvajalnikUkaz", [x[1]]); });
    });
    $("mediaBarNapredek").addEventListener("change", function () {
      var p = S.mediaPredvajalnik;
      S.mediaDragging = false;
      if (p && p.trajanje > 0 && p.vrsta !== "tv" && p.vrsta !== "radio")
        klic("predvajalnikUkaz", ["skok", p.trajanje * Number(this.value) / 1000]);
    });
    $("mediaBarNapredek").addEventListener("pointerdown", function () { S.mediaDragging = true; });
    $("mediaBarNapredek").addEventListener("pointerup", function () { S.mediaDragging = false; });
    $("programiIskanje").addEventListener("input", function () {
      S.programIskanje = this.value.trim(); S.skupina = "vse"; narisiPrograme();
    });
    $("mediaIskanje").addEventListener("input", function () {
      S.mediaIskanje = this.value.trim(); S.mediaFilter = "vse"; narisiMedije();
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
    iskanje.addEventListener("input", isci);
    iskanje.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); premakniIzbiro(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); premakniIzbiro(-1); }
      else if (e.key === "Enter") {
        var a = document.querySelector("#zadetki .zadetek.aktiven");
        e.preventDefault();
        if (a) a.click(); else izvediNamero(iskanje.value.trim());
        iskanje.value = ""; iskanje.blur();
      }
    });
    iskanje.addEventListener("focus", function () { if (iskanje.value) isci(); });
    // Kot meni Start: kar zacnes tipkati, gre v iskanje.
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        var odprt = document.querySelector(".sloj.viden");
        if (odprt || iskanje.value) { iskanje.value = ""; zapriSloje(); iskanje.blur(); }
        else pojdi("domov");
        return;
      }
      var v = document.activeElement;
      if (v && (v.tagName === "INPUT" || v.tagName === "TEXTAREA" || v.tagName === "SELECT" || v.isContentEditable)) return;
      // Odprt obrazec (npr. »Dodaj postajo«) ne sme pošiljati tipk v iskanje za sabo.
      var sloj = document.querySelector(".sloj.viden");
      if (sloj && sloj.id !== "slojIskanje") return;
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      if (e.key && e.key.length === 1 && e.key !== " ") {
        e.preventDefault();
        iskanje.focus();
        iskanje.value += e.key;
        isci();
      }
    });
  }

  function zacni() {
    if (/[?&]namizje=1/.test(location.search)) document.body.classList.add("namizje");
    prevedi();
    poveziDogodke();
    osveziUro();
    setInterval(osveziUro, 1000);
    narisiDomov();
    narisiPovezavo();
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
      narisiPovezavo();
      osveziUro();
      narisiMape();
      narisiDomov();
      nalozPrograme();
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
