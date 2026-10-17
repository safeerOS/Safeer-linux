/* Plosca sporocil delovne povrsine: pogovori iz Sporocil Safeer OS (klepet: Safeer Link, Matrix, Telegram ...;
   e-posta posebej), neprebrani z modro piko, iskanje, »Novo sporocilo« in »Odpri v celoti« (okno Sporocila).
   Odpre jo kuverta v pultu zgoraj desno (safeer_os.py _preklopi_plosco_sporocil). */
(function () {
  "use strict";
  var most = window.SafeerOS || null;
  var BESEDILA = {
    sl: { naslov: "Sporočila in e-pošta", klepet: "Sporočila", email: "E-pošta", isci: "Išči sporočila …",
          novo: "Novo sporočilo", vse: "Odpri v celoti", prazno: "Ni sporočil.", praznoIsk: "Ni zadetkov.",
          brezKanalov: "Ni še povezanih kanalov. Dodaš jih v Sporočilih (Odpri v celoti).", zapri: "Zapri",
          prebrano: "Označi kot prebrano", neprebrano: "Označi kot neprebrano", zvezdica: "Označi kot pomembno", brezZvezdice: "Odstrani oznako pomembno", izbrisi: "Izbriši", izbrisano: "Izbrisano.", razveljavi: "Razveljavi", napaka: "Dejanja ni bilo mogoče izvesti." },
    en: { naslov: "Messages and email", klepet: "Messages", email: "Email", isci: "Search messages …",
          novo: "New message", vse: "Open all", prazno: "No messages.", praznoIsk: "No matches.",
          brezKanalov: "No channels connected yet. Add them in Messages (Open all).", zapri: "Close",
          prebrano: "Mark as read", neprebrano: "Mark as unread", zvezdica: "Mark as important", brezZvezdice: "Remove important", izbrisi: "Delete", izbrisano: "Deleted.", razveljavi: "Undo", napaka: "The action could not be completed." },
    de: { naslov: "Nachrichten und E-Mail", klepet: "Nachrichten", email: "E-Mail", isci: "Nachrichten suchen …",
          novo: "Neue Nachricht", vse: "Alles öffnen", prazno: "Keine Nachrichten.", praznoIsk: "Keine Treffer.",
          brezKanalov: "Noch keine Kanäle verbunden. Füge sie in Nachrichten hinzu (Alles öffnen).", zapri: "Schließen",
          prebrano: "Als gelesen markieren", neprebrano: "Als ungelesen markieren", zvezdica: "Als wichtig markieren", brezZvezdice: "Wichtig entfernen", izbrisi: "Löschen", izbrisano: "Gelöscht.", razveljavi: "Rückgängig", napaka: "Die Aktion konnte nicht ausgeführt werden." },
    es: { naslov: "Mensajes y correo", klepet: "Mensajes", email: "Correo", isci: "Buscar mensajes …",
          novo: "Nuevo mensaje", vse: "Abrir todo", prazno: "No hay mensajes.", praznoIsk: "Sin resultados.",
          brezKanalov: "Aún no hay canales conectados. Añádelos en Mensajes (Abrir todo).", zapri: "Cerrar",
          prebrano: "Marcar como leído", neprebrano: "Marcar como no leído", zvezdica: "Marcar como importante", brezZvezdice: "Quitar importante", izbrisi: "Eliminar", izbrisano: "Eliminado.", razveljavi: "Deshacer", napaka: "No se pudo completar la acción." },
    fr: { naslov: "Messages et e-mails", klepet: "Messages", email: "E-mail", isci: "Rechercher des messages …",
          novo: "Nouveau message", vse: "Tout ouvrir", prazno: "Aucun message.", praznoIsk: "Aucun résultat.",
          brezKanalov: "Aucun canal connecté. Ajoute-les dans Messages (Tout ouvrir).", zapri: "Fermer",
          prebrano: "Marquer comme lu", neprebrano: "Marquer comme non lu", zvezdica: "Marquer comme important", brezZvezdice: "Retirer important", izbrisi: "Supprimer", izbrisano: "Supprimé.", razveljavi: "Annuler", napaka: "L’action n’a pas pu être effectuée." },
    it: { naslov: "Messaggi ed e-mail", klepet: "Messaggi", email: "E-mail", isci: "Cerca messaggi …",
          novo: "Nuovo messaggio", vse: "Apri tutto", prazno: "Nessun messaggio.", praznoIsk: "Nessun risultato.",
          brezKanalov: "Nessun canale collegato. Aggiungili in Messaggi (Apri tutto).", zapri: "Chiudi",
          prebrano: "Segna come letto", neprebrano: "Segna come non letto", zvezdica: "Segna come importante", brezZvezdice: "Rimuovi importante", izbrisi: "Elimina", izbrisano: "Eliminato.", razveljavi: "Annulla", napaka: "Impossibile completare l’azione." }
  };
  var jezik = (location.search.match(/[?&]jezik=([a-z]{2})(?:&|$)/) || [])[1] || "sl";
  if (!BESEDILA[jezik]) jezik = "en";
  var LOKALE = { sl: "sl-SI", en: "en-GB", de: "de-DE", es: "es-ES", fr: "fr-FR", it: "it-IT" };
  var S = { vrsta: "klepet", podatki: { skupine: [], kanali: [] }, nalozeno: false, skriti: {} };

  function t(k) { return BESEDILA[jezik][k] || BESEDILA.en[k] || k; }
  function $(id) { return document.getElementById(id); }
  function klic(m, a) { return most ? Promise.resolve(most.klic(m, a || [])) : Promise.reject("brez mosta"); }

  // Vrstice: en pogovor = ena vrstica (oseba, zadnje sporocilo ali zadeva, cas, neprebrano).
  function vrstice() {
    var izid = [];
    (S.podatki.skupine || []).forEach(function (skupina) {
      (skupina.pogovori || []).forEach(function (p) {
        var vrsta = ((p.kanal || {}).vrsta || "") === "email" ? "email" : "klepet";
        izid.push({ vrsta: vrsta, ime: (skupina.oseba || {}).ime || p.oseba_id || "", p: p });
      });
    });
    izid.sort(function (a, b) { return String(b.p.cas || "").localeCompare(String(a.p.cas || "")); });
    return izid;
  }
  function kratekCas(cas) {
    var d = new Date(cas || ""); if (isNaN(d.getTime())) return "";
    var lok = LOKALE[jezik] || "en-GB", danes = new Date();
    if (d.toDateString() === danes.toDateString()) return d.toLocaleTimeString(lok, { hour: "2-digit", minute: "2-digit" });
    return d.toLocaleDateString(lok, { day: "numeric", month: "short" });
  }
  function zacetnice(ime) {
    var deli = String(ime || "?").trim().split(/\s+/).filter(Boolean);
    return ((deli[0] || "?").charAt(0) + (deli.length > 1 ? deli[deli.length - 1].charAt(0) : "")).toUpperCase();
  }
  function barva(ime) {
    var h = 0, s = String(ime || "");
    for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360;
    return "hsl(" + h + ", 45%, 42%)";
  }
  function narisi() {
    var vse = vrstice(), q = $("iskanje").value.trim().toLowerCase();
    var stevilo = { klepet: 0, email: 0 };
    vse.forEach(function (v) { stevilo[v.vrsta] += Number(v.p.neprebrano || 0); });
    [["zavSporocila", "klepet"], ["zavEposta", "email"]].forEach(function (z) {
      var b = $(z[0]);
      b.textContent = t(z[1]);
      if (stevilo[z[1]]) { var s = document.createElement("span"); s.className = "stevec"; s.textContent = stevilo[z[1]]; b.appendChild(s); }
      b.classList.toggle("izbran", S.vrsta === z[1]);
      b.setAttribute("aria-selected", S.vrsta === z[1] ? "true" : "false");
    });
    var seznam = $("seznam");
    seznam.textContent = "";
    var izbrane = vse.filter(function (v) {
      if (v.vrsta !== S.vrsta || S.skriti[kljuc(v.p)]) return false;
      if (!q) return true;
      return (v.ime + " " + (v.p.zadeva || "") + " " + (v.p.zadnje_sporocilo || "")).toLowerCase().indexOf(q) >= 0;
    });
    izbrane.slice(0, 60).forEach(function (v) {
      var li = document.createElement("li");
      var b = document.createElement("button");
      b.type = "button";
      b.className = "vrstica" + (v.p.neprebrano ? " neprebrano" : "");
      var pika = document.createElement("span"); pika.className = "pika" + (v.p.neprebrano ? "" : " prebrano");
      var av = document.createElement("span"); av.className = "avatar"; av.textContent = zacetnice(v.ime);
      av.style.background = barva(v.ime);
      var bes = document.createElement("span"); bes.className = "besedilo";
      var ime = document.createElement("b"); ime.textContent = v.ime;
      var vrst = document.createElement("small");
      vrst.textContent = v.vrsta === "email" && v.p.zadeva ? v.p.zadeva : (v.p.zadnje_sporocilo || v.p.zadeva || "");
      bes.appendChild(ime); bes.appendChild(vrst);
      var desno = document.createElement("span"); desno.className = "desno";
      var cas = document.createElement("time"); cas.textContent = kratekCas(v.p.cas); desno.appendChild(cas);
      if (v.p.neprebrano) { var n = document.createElement("i"); n.textContent = v.p.neprebrano; desno.appendChild(n); }
      b.appendChild(pika); b.appendChild(av); b.appendChild(bes); b.appendChild(desno);
      if (v.p.zvezdica) { var zv = document.createElement("span"); zv.className = "zvezda"; zv.textContent = "★"; desno.appendChild(zv); }
      b.addEventListener("click", function () { odpri("pogovor:" + v.p.kanal_id + ":" + v.p.id); });
      li.appendChild(b); li.appendChild(gumbiVrstice(v)); seznam.appendChild(li);
    });
    if (!izbrane.length) {
      var p = document.createElement("p"); p.className = "prazno";
      p.textContent = !S.nalozeno ? "" : q ? t("praznoIsk") : (S.podatki.kanali || []).length ? t("prazno") : t("brezKanalov");
      seznam.appendChild(p);
    }
  }
  // Dejanja v vrstici (lastnik, 17. 10. 2026: ze v plosci oznaci prebrano, izbrisi, oznaci kot pomembno). Isti klic
  // kot okno Sporocila (sporocilaDejanje); gumb samo, ce ga kanal zmore (kanal.dejanja). Oznake takoj, izbris po 5 s
  // z moznostjo »Razveljavi«.
  var IKONE = {
    prebrano: "M4 7l8 6 8-6 M4 7h16v11H4z", neprebrano: "M4 7l8 6 8-6 M4 7h16v11H4z M19 4.5a1.5 1.5 0 1 0 0.01 0",
    zvezdica: "M12 4l2.5 5 5.5.8-4 3.9.9 5.5L12 16.6 7.1 19.2l.9-5.5-4-3.9 5.5-.8z",
    izbrisi: "M5 7h14 M10 7V5h4v2 M7 7l1 12h8l1-12"
  };
  function kljuc(p) { return p.kanal_id + "\u0001" + p.id; }
  function zmore(p, d) { return ((p.kanal || {}).dejanja || []).indexOf(d) >= 0; }
  function gumb(ime, pot, fn, vkljucen) {
    var g = document.createElement("button");
    g.type = "button"; g.className = "dejanje" + (vkljucen ? " vkljucen" : ""); g.title = t(ime); g.setAttribute("aria-label", t(ime));
    g.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + pot + '"/></svg>';
    g.addEventListener("click", function (e) { e.stopPropagation(); fn(); });
    return g;
  }
  function gumbiVrstice(v) {
    var d = document.createElement("span"); d.className = "dejanja";
    var p = v.p, prebrano = !Number(p.neprebrano || 0);
    var oznaka = prebrano ? "neprebrano" : "prebrano";
    if (zmore(p, oznaka)) d.appendChild(gumb(oznaka, IKONE[oznaka], function () { dejanje(v, oznaka); }));
    var zv = p.zvezdica ? "brez_zvezdice" : "zvezdica";
    if (zmore(p, zv)) d.appendChild(gumb(p.zvezdica ? "brezZvezdice" : "zvezdica", IKONE.zvezdica, function () { dejanje(v, zv); }, !!p.zvezdica));
    if (zmore(p, "izbrisi")) d.appendChild(gumb("izbrisi", IKONE.izbrisi, function () { izbrisi(v); }));
    return d;
  }
  function posodobi(p) { if (p && p.skupine) S.podatki = p; narisi(); if (p && (p.napake || []).length) sporoci(t("napaka")); }
  function dejanje(v, d) {
    var prej = { n: v.p.neprebrano, z: v.p.zvezdica };
    if (d === "prebrano") v.p.neprebrano = 0;
    else if (d === "neprebrano") v.p.neprebrano = Math.max(1, Number(v.p.neprebrano) || 0);
    else if (d === "zvezdica") v.p.zvezdica = true;
    else if (d === "brez_zvezdice") v.p.zvezdica = false;
    narisi();
    klic("sporocilaDejanje", [[[v.p.kanal_id, v.p.id]], d, ""]).then(posodobi, function () {
      v.p.neprebrano = prej.n; v.p.zvezdica = prej.z; narisi(); sporoci(t("napaka"));
    });
  }
  function izbrisi(v) {
    var k = kljuc(v.p);
    S.skriti[k] = true; narisi();
    var ura = setTimeout(function () {
      skrijSporocilo();
      klic("sporocilaDejanje", [[[v.p.kanal_id, v.p.id]], "izbrisi", ""]).then(function (p) {
        delete S.skriti[k]; posodobi(p);
      }, function () { delete S.skriti[k]; narisi(); sporoci(t("napaka")); });
    }, 5000);
    sporoci(t("izbrisano"), function () { clearTimeout(ura); delete S.skriti[k]; narisi(); });
  }
  function sporoci(besedilo, razveljavi) {
    var o = $("obvestilo");
    o.textContent = "";
    var b = document.createElement("span"); b.textContent = besedilo; o.appendChild(b);
    if (razveljavi) {
      var g = document.createElement("button"); g.type = "button"; g.className = "razveljavi"; g.textContent = t("razveljavi");
      g.addEventListener("click", function () { razveljavi(); skrijSporocilo(); });
      o.appendChild(g);
    }
    o.hidden = false;
    clearTimeout(sporoci.ura);
    sporoci.ura = setTimeout(skrijSporocilo, razveljavi ? 5000 : 4000);
  }
  function skrijSporocilo() { $("obvestilo").hidden = true; }

  function odpri(cilj) {
    klic("odpriRazdelek", [cilj]).catch(function () {});
    klic("skrijPloscoSporocil").catch(function () {});
  }
  function osvezi() {
    return klic("sporocilaSeznam").then(function (p) {
      S.podatki = p || { skupine: [], kanali: [] }; S.nalozeno = true; narisi();
    }, function () { S.nalozeno = true; narisi(); });
  }
  // Novo sporocilo ali prebran pogovor (niti kanalov v realnem casu): odprta plosca se osvezi takoj.
  var dogodekCas = 0;
  window.safeerOsDogodek = function (vrsta) {
    if (vrsta !== "sporocila" || dogodekCas || document.visibilityState === "hidden") return;
    dogodekCas = setTimeout(function () { dogodekCas = 0; osvezi(); }, 120);
  };
  // Safeer OS poklice ob vsakem odprtju plosce (podatki so sveži, iskanje prazno, fokus v iskanju).
  window.safeerPloscaOsvezi = function () {
    $("iskanje").value = "";
    osvezi().then(function () { $("iskanje").focus(); });
  };

  document.documentElement.lang = jezik;
  $("naslov").textContent = t("naslov");
  $("iskanje").placeholder = t("isci");
  $("novo").textContent = t("novo");
  $("vse").textContent = t("vse");
  $("zapri").setAttribute("aria-label", t("zapri"));
  $("zapri").addEventListener("click", function () { klic("skrijPloscoSporocil").catch(function () {}); });
  $("novo").addEventListener("click", function () { odpri(S.vrsta === "email" ? "sporocila:novo-email" : "sporocila:novo"); });
  $("vse").addEventListener("click", function () { odpri("sporocila"); });
  $("iskanje").addEventListener("input", narisi);
  [["zavSporocila", "klepet"], ["zavEposta", "email"]].forEach(function (z) {
    $(z[0]).addEventListener("click", function () { S.vrsta = z[1]; narisi(); });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") klic("skrijPloscoSporocil").catch(function () {});
  });
  narisi();
  osvezi().then(function () {
    // Prvi pogled: zavihek z neprebranimi (e-posta, ce je novo samo tam); brez klepetov sploh pa e-posta - plosca
    // ne sme kazati »Ni sporocil«, ko je v e-posti polno pisem (lastnik, 14. 10. 2026).
    var n = { klepet: 0, email: 0 }, vseh = { klepet: 0, email: 0 };
    vrstice().forEach(function (v) { n[v.vrsta] += Number(v.p.neprebrano || 0); vseh[v.vrsta]++; });
    if ((!n.klepet && n.email) || (!vseh.klepet && vseh.email)) { S.vrsta = "email"; narisi(); }
  });
})();
