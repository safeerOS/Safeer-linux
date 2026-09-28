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
  }

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
    o.classList.add("viden");
    clearTimeout(obvestiloCas);
    obvestiloCas = setTimeout(function () { o.classList.remove("viden"); }, 2600);
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
    if (razdelek === "nastavitve") { narisiNastavitve(); nalozScit(); scitZanka(); }
    if (razdelek === "programi") nalozNaprave();
    if (razdelek === "media") narisiMedije();
    if (razdelek === "splet") narisiSpletnoZacetno();
    if (razdelek === "zapiski") naloziZapiske(function (seznam) {
      if (!Z.aktivni && seznam.length) odpriZapisek(seznam[0].id);
    });
    if (razdelek === "omrezje") nalozOmrezje(false);
    if (razdelek === "zvok") { nalozZvok(); zvokZanka(); if (!jblStanje) nalozJbl(); }
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
    pojdi(kam);
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
    ["vse", "programi"], ["video", "video"], ["glasba", "glasba"],
    ["radio", "radio"], ["videospoti", "video"]
  ];
  function vrstaMedija(vnos) {
    var s = ((vnos.ime || "") + " " + (vnos.url || "") + " " + (vnos.id || "") + " " + (vnos.opis || "")).toLowerCase();
    if (/radio|podcast|tunein|radioplayer/.test(s)) return "radio";
    if (/videospot|music.?video|vevo|youtube|youtu\.be/.test(s)) return "videospoti";
    if (/glasb|music|spotify|deezer|soundcloud|rhythmbox|audacious|clementine/.test(s)) return "glasba";
    return "video";
  }
  function medijskiVnosi() {
    var vnosi = [];
    S.programi.filter(function (p) { return p.skupina === "predstavnost"; }).forEach(function (p) {
      vnosi.push({ vrsta: vrstaMedija(p), program: p });
    });
    spletne().forEach(function (a, i) {
      // Privzeta Gmail in Wikipedia sta spletni aplikaciji, ne medijska vira. Uporabnikovi drugi
      // viri ostanejo v katalogu, ker so lahko poimenovani poljubno.
      if (/gmail|mail\.google|wikipedia/i.test((a.ime || "") + " " + (a.url || ""))) return;
      vnosi.push({ vrsta: vrstaMedija(a), spletna: a, indeks: i });
    });
    return vnosi;
  }
  function narisiMedije() {
    var kategorije = $("mediaKategorije"), mreza = $("mediaMreza");
    if (!kategorije || !mreza) return;
    var vsi = medijskiVnosi();
    kategorije.innerHTML = "";
    MEDIA_KATEGORIJE.forEach(function (k) {
      var n = k[0] === "vse" ? vsi.length : vsi.filter(function (v) { return v.vrsta === k[0]; }).length;
      var b = el("button", "media-kategorija" + (S.mediaFilter === k[0] ? " izbrana" : ""),
        svg(k[1]) + '<div><b>' + ubezi(t("media_" + k[0])) + '</b><span>' + ubezi(t("media_" + k[0] + "_pod")) +
        '</span></div><i>' + n + "</i>");
      b.addEventListener("click", function () { S.mediaFilter = k[0]; narisiMedije(); });
      kategorije.appendChild(b);
    });
    var iskano = String(S.mediaIskanje || "").trim();
    var prikaz = vsi.filter(function (v) {
      var x = v.program || v.spletna || {};
      return (S.mediaFilter === "vse" || v.vrsta === S.mediaFilter) &&
        (!iskano || Math.max(SafeerIskanje.oceni(x.ime, iskano), SafeerIskanje.oceni(x.url, iskano),
          SafeerIskanje.oceni(x.opis, iskano)) > 0);
    });
    $("mediaStevec").textContent = prikaz.length ? String(prikaz.length) : "";
    mreza.innerHTML = "";
    prikaz.forEach(function (v) {
      mreza.appendChild(v.program ? ploscicaPrograma(v.program, true) : ploscicaSpletne(v.spletna, v.indeks, true));
    });
    $("mediaPrazno").hidden = prikaz.length !== 0;
  }
  function odpriDodaj() {
    $("dodajIme").value = "";
    $("dodajNaslov").value = "";
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
  function vrsticaDatoteke(d, zPotjo, nedavna) {
    var b = el("button", "vrstica");
    b.innerHTML = svg(IKONA_VRSTE[d.vrsta] || "datoteka") + '<span class="ime">' + ubezi(d.ime) + "</span>" +
      (zPotjo ? '<span class="pod pot">' + ubezi(skrajsajPot(d.pot.replace(/\/[^\/]*$/, "") || "/")) + "</span>" : "") +
      '<span class="pod">' + (d.mapa ? "" : ubezi(velikost(d.velikost || 0)) + " · ") + ubezi(datum(d.spremenjeno || d.cas)) + "</span>";
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
  }
  function odpriNedavne() {
    S.pot = "";
    narisiMape();
    var dr = $("drobtine");
    dr.innerHTML = "";
    dr.appendChild(el("button", "", ubezi(t("nedavno"))));
    var desnoN = el("div", "desno");
    var poc = el("button", "gumb", svg("x") + "<span>" + ubezi(t("pocistiSeznam")) + "</span>");
    poc.addEventListener("click", pocistiNedavne);
    desnoN.appendChild(poc);
    dr.appendChild(desnoN);
    klic("nedavne").then(function (seznam) {
      S.nedavne = seznam || [];
      var v = $("vsebinaMape");
      v.innerHTML = "";
      if (!S.nedavne.length) { v.appendChild(el("div", "prazno", ubezi(t("prazno")))); return; }
      S.nedavne.forEach(function (d) { v.appendChild(vrsticaDatoteke(d, true, true)); });
    }, function () {});
  }
  function prikaziIskanjeDatotek(niz, znani) {
    S.datotekeIskanje = String(niz || "").trim();
    S.pot = "";
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
    klic("isciDatoteke", [S.datotekeIskanje]).then(function (seznam) {
      if ($("datotekeIskanje").value.trim() !== S.datotekeIskanje) return;
      prikaziIskanjeDatotek(S.datotekeIskanje, seznam || []);
    }, function () { v.innerHTML = ""; v.appendChild(el("div", "prazno", ubezi(t("niZadetkov")))); });
  }
  function odpriMapo(pot) {
    klic("mapa", [pot]).then(function (r) {
      S.pot = r.pot;
      narisiMape();
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
      r.elementi.forEach(function (e) { v.appendChild(vrsticaDatoteke(e, false)); });
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
  function shraniIme(id, ime) {
    klic("preimenujNapravo", [id, ime]).then(function (r) {
      preimenujem = null;
      obvesti(t(r && r.ok ? "preimenovano" : "napPreimenovanje"));
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
    if (kompaktno) {
      cilj.appendChild(mreza);
      var vec = el("button", "gumb", svg("drsniki") + "<span>" + ubezi(t("nastavitve")) + "</span>");
      vec.addEventListener("click", function () { zapriSloje(); pojdi("nastavitve"); });
      cilj.appendChild(vec);
    }
  }
  function narisiHitro() { kontrole($("hitro"), true); }
  function odpriHitro() { zapriSloje(); narisiHitro(); $("slojHitro").classList.add("viden"); osveziStanje(); }

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
  var zvokStanje = null, zvokCas = 0, zvokDotik = 0, zvokCaka = "";
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
    else if (!s.mozno) pod = t("scitNiMozno");
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
    if (s.vklop && s.tece && s.zadnje && s.zadnje.length) {
      var z = el("div", "scit-zadnje", "<b>" + ubezi(t("scitZadnje")) + "</b>");
      s.zadnje.slice(0, 6).forEach(function (x) {
        z.appendChild(el("span", "", ubezi(x.ime) + " <i>" + ubezi(t("scitKat_" + x.kategorija)) + "</i>"));
      });
      c.appendChild(z);
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
    if (!link.naprave.length) l.appendChild(el("div", "prazno", ubezi(t(link.povezan ? "zvokBrezNaprav" : "zvokBrezLinka"))));
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
  function narisiNastavitve() {
    kontrole($("hitreNastavitve"), false);
    $("stikaloCelozaslonsko").setAttribute("aria-checked", S.zacetek && S.zacetek.celozaslonsko ? "true" : "false");
    $("stikaloSamozagon").setAttribute("aria-checked", S.zacetek && S.zacetek.samozagon ? "true" : "false");
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
  var iskanjeZamik = 0, iskanjeStevec = 0, iskanjeDatotekNiz = "", ciljnoDatotekeZamik = 0;
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
    if (!niz) { sloj.classList.remove("viden"); return; }
    $("slojHitro").classList.remove("viden");
    $("slojNapajanje").classList.remove("viden");
    sloj.classList.add("viden");
    var n = niz.toLowerCase();
    var z = $("zadetki");
    z.innerHTML = "";
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

    clearTimeout(iskanjeZamik);
    var moj = ++iskanjeStevec;
    if (n.length >= 2) {
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
    document.querySelectorAll(".sloj").forEach(function (s) { s.classList.remove("viden"); });
    if ($("iskanje").value && document.activeElement !== $("iskanje")) $("iskanje").value = "";
  }

  // ------------------------------------------------------------------ dogodki iz safeer_os.py
  window.safeerOsDogodek = function (vrsta, podatki) {
    if (vrsta === "stanje") narisiStanje(podatki);
    if (vrsta === "okna") narisiOkna(podatki);
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
    $("medijiDodajPrazno").addEventListener("click", odpriDodaj);
    $("programiIskanje").addEventListener("input", function () {
      S.programIskanje = this.value.trim(); S.skupina = "vse"; narisiPrograme();
    });
    $("mediaIskanje").addEventListener("input", function () {
      S.mediaIskanje = this.value.trim(); S.mediaFilter = "vse"; narisiMedije();
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
      shraniSpletne(spletne().concat([{ ime: ime.slice(0, 40), url: naslov }]).slice(0, 24));
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
      if (v && (v.tagName === "INPUT" || v.tagName === "TEXTAREA")) return;
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
      klic("sporocilaSeznam").then(function (p) {
        S.sporocilaSkupine = p.skupine || []; S.sporocilaKanali = p.kanali || [];
      });
    }, function () {});
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", zacni); else zacni();
})();
