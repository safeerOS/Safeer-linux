/* Lastni vgrajeni viri v Medijskem centru (lastnik, 15. 10. 2026): uporabnik vgradi katerokoli stran ali svojo
 * komponento React; Safeer da samo orodje, Scit ga varuje ne glede na stran. Ta datoteka je samostojna (brez os.js),
 * zato jo lahko uporabi vsaka stran Safeer OS.
 *
 * Komponenta za vgradnjo (enakovredno »React / Next.js Component Example«, brez Reacta na nasi strani):
 *
 *   var vgradnja = SafeerVgrajeno.odpri({
 *     url: "https://...",        // koncni naslov (core/os_vgrajeni_viri.py ga je preveril in sestavil iz predloge)
 *     title: "Ime vira",         // napis v vrstici nad vsebino
 *     allowFullscreen: true,     // gumb »Cel zaslon« in allow="fullscreen" za okvir
 *     allowPopups: false,        // »Dovoli pojavna okna« vira (privzeto ne) - okno odpre Splet, ne ta stran
 *     onClose: function () {}    // klic ob zaprtju (gumb Nazaj, Escape, gumb Nazaj na daljincu)
 *   });
 *   vgradnja.zapri();
 *
 *   SafeerVgrajeno.komponenta({ koda, props, title, allowFullscreen, onClose, onError, knjiznica })
 *     - prilepljena koda React (JSX ali JS, »export default« ali poimenovana funkcijska komponenta) tece SAMO v okvirju
 *       peskovnik.html s sandbox="allow-scripts" (brez allow-same-origin: neprozoren izvor - ne doseze mostu, shrambe,
 *       piskotkov ne DOM-a te strani) in s strogo CSP (brez omrezja: connect-src 'none'). React, ReactDOM in Babel
 *       (samo, ce koda potrebuje JSX ali import/export) so lokalni (assets/os/vendor, preverjen SHA-256) in gredo v
 *       okvir kot besedilo s postMessage.
 *     - props gredo v okvir s postMessage; nazaj sprejmemo samo: nalozen, pripravljen, zapri, celozaslonsko, napaka,
 *       potrebujemBabel - in samo iz tega okvirja (event.source). Vnosov za katalog komponenta ne more dati.
 *
 * Varnost okvirja s stranjo (stran je tuja): sandbox="allow-scripts allow-same-origin allow-forms allow-presentation"
 * (+ allow-popups le z vklopljenim »Dovoli pojavna okna«); nikoli allow-top-navigation. allow-same-origin je tu
 * varen, ker ima okvir vedno izvor https/http, nasa stran pa file:// - izvora nista enaka, zato se okvir ne more
 * dotakniti te strani ne odstraniti peskovnika; brez njega bi vecina predvajalnikov odpovedala (piskotki, shramba,
 * DRM, preverjanje izvora). Most Safeer OS v okvirju ne deluje (safeer_os.py: zeton mostu je samo v glavnem okvirju).
 */
(function () {
  "use strict";
  var odprte = [];
  var nastavitve = { aktivno: null, besedila: {} };
  var DOVOLJENA = { nalozen: 1, pripravljen: 1, zapri: 1, celozaslonsko: 1, napaka: 1, potrebujemBabel: 1 };

  function besedilo(kljuc, privzeto) { return nastavitve.besedila[kljuc] || privzeto; }
  function aktivno(da) {
    try { return Promise.resolve(nastavitve.aktivno ? nastavitve.aktivno(!!da) : true); }
    catch (e) { return Promise.resolve(false); }
  }
  function naCelZaslon(el) {
    var f = el.requestFullscreen || el.webkitRequestFullscreen;
    if (f) try { f.call(el); } catch (e) { /* ni dovoljeno */ }
  }
  function vCelemZaslonu() { return !!(document.fullscreenElement || document.webkitFullscreenElement); }

  // Ovoj cez Medijski center: vrstica z gumbom Nazaj (in Cel zaslon) ter okvir. Fokus gre na Nazaj, nato v okvir.
  function ovoj(title, allowFullscreen, zapri) {
    var sloj = document.createElement("div");
    sloj.className = "vgrajeno-sloj";
    sloj.setAttribute("role", "dialog");
    sloj.setAttribute("aria-modal", "true");
    sloj.setAttribute("aria-label", title || "");
    var vrstica = document.createElement("div");
    vrstica.className = "vgrajeno-vrstica";
    var nazaj = document.createElement("button");
    nazaj.type = "button"; nazaj.className = "gumb vgrajeno-nazaj";
    nazaj.textContent = "← " + besedilo("nazaj", "Nazaj");
    nazaj.addEventListener("click", zapri);
    var napis = document.createElement("b");
    napis.className = "vgrajeno-naslov"; napis.textContent = title || "";
    vrstica.appendChild(nazaj); vrstica.appendChild(napis);
    if (allowFullscreen) {
      var cel = document.createElement("button");
      cel.type = "button"; cel.className = "gumb vgrajeno-cel";
      cel.textContent = besedilo("celZaslon", "Cel zaslon");
      cel.addEventListener("click", function () { naCelZaslon(sloj); });
      vrstica.appendChild(cel);
    }
    sloj.appendChild(vrstica);
    return sloj;
  }

  function vgradnja(okvir, sloj, opts, poZaprtju) {
    var zaprto = false, prejFokus = document.activeElement;
    var h = {
      okvir: okvir, sloj: sloj,
      zapri: function () {
        if (zaprto) return; zaprto = true;
        odprte = odprte.filter(function (x) { return x !== h; });
        try { okvir.src = "about:blank"; } catch (e) { /* ze odstranjen */ }
        if (sloj.parentNode) sloj.parentNode.removeChild(sloj);
        if (poZaprtju) poZaprtju();
        if (!odprte.length) aktivno(false);
        if (prejFokus && document.contains(prejFokus) && prejFokus.focus) prejFokus.focus({ preventScroll: true });
        if (opts.onClose) try { opts.onClose(); } catch (e) { /* klicatelj */ }
      }
    };
    odprte.push(h);
    return h;
  }

  /** Stran (ali predloga, ze izpolnjena) v okvirju cez Medijski center. Vrne {zapri, okvir, sloj}. */
  function odpri(opts) {
    opts = opts || {};
    var url = String(opts.url || "");
    if (!/^https?:\/\//i.test(url)) throw new Error("vgrajeno: samo http(s)");
    var h;
    var sloj = ovoj(opts.title, opts.allowFullscreen !== false, function () { h.zapri(); });
    var okvir = document.createElement("iframe");
    okvir.className = "vgrajeno-okvir";
    okvir.title = opts.title || "";
    okvir.setAttribute("sandbox", "allow-scripts allow-same-origin allow-forms allow-presentation" +
                       (opts.allowPopups ? " allow-popups" : ""));
    okvir.setAttribute("allow", "autoplay; " + (opts.allowFullscreen !== false ? "fullscreen; " : "") +
                       "encrypted-media; picture-in-picture");
    if (opts.allowFullscreen !== false) okvir.setAttribute("allowfullscreen", "");
    okvir.setAttribute("referrerpolicy", "no-referrer");
    sloj.appendChild(okvir);
    h = vgradnja(okvir, sloj, opts);
    document.body.appendChild(sloj);
    sloj.querySelector(".vgrajeno-nazaj").focus({ preventScroll: true });
    // Okvir dobi naslov sele, ko Safeer OS ve, da je vir odprt (pravila okvirjev, filter EasyList).
    aktivno(true).then(function () { if (odprte.indexOf(h) >= 0) okvir.src = url; });
    okvir.addEventListener("load", function () { if (okvir.src && okvir.src !== "about:blank") try { okvir.focus(); } catch (e) { /* */ } });
    return h;
  }

  // Barve iz tokens.css (stran) za peskovnik - okvir tokens.css ne nalozi (neprozoren izvor).
  function barve() {
    var s = getComputedStyle(document.documentElement), izid = {};
    ["--ozadje", "--besedilo", "--medlo", "--zelena", "--rob", "--kartica"].forEach(function (ime) {
      var v = s.getPropertyValue(ime).trim(); if (v) izid[ime] = v;
    });
    return izid;
  }

  /** Komponenta React v peskovniku cez Medijski center. opts.knjiznica(ime) -> Promise<besedilo> (react, react-dom,
   *  babel - Safeer OS jih da iz assets/os/vendor po preverbi SHA-256). Vrne {zapri, okvir, sloj, props(novi)}. */
  function komponenta(opts) {
    opts = opts || {};
    var h, poslusalec;
    var sloj = ovoj(opts.title, opts.allowFullscreen !== false, function () { h.zapri(); });
    var okvir = document.createElement("iframe");
    okvir.className = "vgrajeno-okvir";
    okvir.title = opts.title || "";
    okvir.setAttribute("sandbox", "allow-scripts");                 // NIKOLI allow-same-origin (glej zgoraj)
    okvir.setAttribute("allow", opts.allowFullscreen !== false ? "fullscreen; autoplay" : "autoplay");
    okvir.setAttribute("referrerpolicy", "no-referrer");
    sloj.appendChild(okvir);
    var napaka = function (sporocilo) { if (opts.onError) try { opts.onError(String(sporocilo || "")); } catch (e) { /* */ } };
    h = vgradnja(okvir, sloj, opts, function () { window.removeEventListener("message", poslusalec); });
    h.props = function (p) { if (okvir.contentWindow) okvir.contentWindow.postMessage({ tip: "props", props: p || {} }, "*"); };
    var knjiznice = null;
    poslusalec = function (e) {
      // Samo iz NASEGA okvirja (neprozoren izvor »null«) in samo dovoljena sporocila; vse drugo prezremo.
      if (e.source !== okvir.contentWindow || (e.origin !== "null" && e.origin !== "")) return;
      var d = e.data;
      if (!d || typeof d !== "object" || d.safeerVgrajeno !== 1 || !DOVOLJENA[d.tip]) return;
      if (d.tip === "nalozen" && knjiznice) {
        okvir.contentWindow.postMessage({ tip: "zazeni", koda: String(opts.koda || ""), props: opts.props || {},
                                          react: knjiznice[0], reactDom: knjiznice[1], barve: barve() }, "*");
        knjiznice = null;                         // samo enkrat
      }
      else if (d.tip === "zapri") h.zapri();
      else if (d.tip === "celozaslonsko" && opts.allowFullscreen !== false) naCelZaslon(sloj);
      else if (d.tip === "napaka") napaka(typeof d.sporocilo === "string" ? d.sporocilo.slice(0, 500) : "");
      else if (d.tip === "pripravljen" && opts.onReady) try { opts.onReady(); } catch (x) { /* */ }
      else if (d.tip === "potrebujemBabel") {
        opts.knjiznica("babel").then(function (b) {
          if (okvir.contentWindow) okvir.contentWindow.postMessage({ tip: "babel", koda: b }, "*");
        }, function () { napaka("babel"); });
      }
    };
    window.addEventListener("message", poslusalec);
    document.body.appendChild(sloj);
    sloj.querySelector(".vgrajeno-nazaj").focus({ preventScroll: true });
    // Peskovnik je datoteka strani (peskovnik.html), ne srcdoc: srcdoc bi podedoval politiko strani (script-src 'self').
    Promise.all([opts.knjiznica("react"), opts.knjiznica("react-dom"), aktivno(true)]).then(function (k) {
      if (odprte.indexOf(h) < 0) return;
      knjiznice = k;
      okvir.src = opts.peskovnik || "peskovnik.html";
      okvir.addEventListener("load", function () { try { okvir.focus(); } catch (e) { /* */ } }, { once: true });
    }, function () { napaka("knjiznica"); h.zapri(); });
    return h;
  }

  function zapriVse() { odprte.slice().reverse().forEach(function (h) { h.zapri(); }); }

  // Escape (gumb Nazaj na daljincu) zapre vir; ce je element v celem zaslonu, ga najprej zapusti brskalnik.
  window.addEventListener("keydown", function (e) {
    if (e.key !== "Escape" || !odprte.length || vCelemZaslonu()) return;
    e.preventDefault(); e.stopImmediatePropagation();
    odprte[odprte.length - 1].zapri();
  }, true);

  window.SafeerVgrajeno = {
    odpri: odpri, komponenta: komponenta, zapriVse: zapriVse,
    odprto: function () { return odprte.length > 0; },
    /** nastavi({aktivno: fn(da) -> Promise, besedila: {nazaj, celZaslon}}) - os.js poveze most Safeer OS. */
    nastavi: function (n) { for (var k in n) nastavitve[k] = n[k]; },
  };
})();
