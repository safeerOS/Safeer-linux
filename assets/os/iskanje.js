/* Cista logika pametnega iskanja Safeer OS. Datoteka deluje tudi v Node.js testih. */
(function (koren, tvornica) {
  "use strict";
  var api = tvornica();
  if (typeof module === "object" && module.exports) module.exports = api;
  else koren.SafeerIskanje = api;
}(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function brezNaglasa(vrednost) {
    var s = String(vrednost == null ? "" : vrednost).toLowerCase();
    return typeof s.normalize === "function" ? s.normalize("NFD").replace(/[\u0300-\u036f]/g, "") : s;
  }

  function oceni(besedilo, niz) {
    var b = brezNaglasa(besedilo).trim(), n = brezNaglasa(niz).trim();
    if (!b || !n) return 0;
    if (b === n) return 100;
    if (b.indexOf(n) === 0) return 70;
    if (b.indexOf(" " + n) >= 0 || b.indexOf("." + n) >= 0) return 50;
    return b.indexOf(n) >= 0 ? 30 : 0;
  }

  function domena(naslov) {
    try { return new URL(naslov).hostname.replace(/^www\./, ""); } catch (e) { return ""; }
  }

  function oceniSpletno(vnos, niz) {
    var ime = (vnos && vnos.ime) || "", host = domena((vnos && vnos.url) || "");
    var dodatno = "";
    if (/youtube|youtu\.be/i.test(ime + " " + host)) dodatno = " yt";
    if (/gmail|mail\.google/i.test(ime + " " + host)) dodatno += " mail";
    return Math.max(oceni(ime, niz), oceni(host, niz), oceni(ime + " " + host + dodatno, niz));
  }

  function jeNaslov(niz) {
    var s = String(niz || "").trim();
    if (/^https?:\/\//i.test(s)) return true;
    if (/\.(pdf|docx?|odt|xlsx?|ods|pptx?|odp|txt|rtf|jpe?g|png|gif|webp|mp[34]|mkv|avi|flac|wav|zip|7z)$/i.test(s)) return false;
    return !/\s/.test(s) && /^[^./\\]+(?:\.[^./\\]+)+(?:[/:?#].*)?$/.test(s);
  }

  function jePotAliKoncnica(niz) {
    var s = String(niz || "").trim();
    return /^(~\/|\/|[a-z]:[\\/])/i.test(s) || /\.[a-z0-9]{1,8}$/i.test(s);
  }

  function vsebujeMedijskoBesedo(niz) {
    return /\b(film|filmi|filme|movie|movies|pelicula|peliculas|serie|series|serien|serija|serije|musik|music|musica|musique|glasba|glasbo|pesem|pesmi|song|songs|chanson|chansons|canzone|canzoni|lied|lieder|radio|tv|fernsehen|television|video|podcast)\b/i.test(brezNaglasa(niz));
  }

  function najboljsi(seznam, niz, ocenjevalnik) {
    var najboljsiVnos = null, najboljsaOcena = 0;
    (seznam || []).forEach(function (vnos) {
      var vrednost = ocenjevalnik ? ocenjevalnik(vnos, niz) : oceni(vnos.ime || vnos.naslov || "", niz);
      if (vrednost > najboljsaOcena) { najboljsaOcena = vrednost; najboljsiVnos = vnos; }
    });
    return { vnos: najboljsiVnos, ocena: najboljsaOcena };
  }

  function nameraIskanja(niz, podatki) {
    var q = String(niz || "").trim(), p = podatki || {};
    if (!q) return { vrsta: "prazno", niz: q };
    var spletna = najboljsi(p.spletne, q, oceniSpletno);
    if (jeNaslov(q)) return { vrsta: "splet", razlog: "naslov", niz: q };
    if (spletna.ocena > 0) return { vrsta: "splet", razlog: "aplikacija", niz: q, zadetek: spletna.vnos };

    var program = najboljsi(p.programi, q, function (v, n) {
      return Math.max(oceni(v.ime, n), oceni(v.splosno, n), oceni((v.kljucne || []).join(" "), n));
    });
    if (program.ocena >= 70) return { vrsta: "programi", niz: q, zadetek: program.vnos };

    var datoteka = najboljsi(p.datoteke, q);
    if (jePotAliKoncnica(q) || datoteka.ocena > 0) return { vrsta: "datoteke", niz: q, zadetek: datoteka.vnos };

    var medij = najboljsi(p.mediji, q, function (v, n) {
      var x = v.program || v.spletna || v;
      return Math.max(oceni(x.ime, n), oceni(x.url, n), oceni(x.opis, n));
    });
    if (vsebujeMedijskoBesedo(q) || medij.ocena > 0) return { vrsta: "media", niz: q, zadetek: medij.vnos };

    var naprava = najboljsi(p.naprave, q);
    if (naprava.ocena > 0) return { vrsta: "naprave", niz: q, zadetek: naprava.vnos };
    return { vrsta: "splet", razlog: "iskanje", niz: q };
  }

  return {
    brezNaglasa: brezNaglasa,
    oceni: oceni,
    oceniSpletno: oceniSpletno,
    jeNaslov: jeNaslov,
    jePotAliKoncnica: jePotAliKoncnica,
    vsebujeMedijskoBesedo: vsebujeMedijskoBesedo,
    nameraIskanja: nameraIskanja
  };
}));
