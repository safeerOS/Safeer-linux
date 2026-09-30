// SAMO ZA PREIZKUS (ni v paketu): lazni most window.SafeerOS z demonstracijskimi podatki, da se da
// postavitev delovne povrsine preveriti v brskalniku brez Safeer OS. Imena so izmisljena primeri.
(function () {
  var dom = "/home/demo";
  var zdaj = Date.now() / 1000;
  function dat(ime, vrsta, vel, st) { return { ime: ime, pot: dom + "/Dokumenti/" + ime, mapa: false, velikost: vel, spremenjeno: zdaj - st, vrsta: vrsta }; }
  var nedavne = [];
  [["Porocilo projekta.odt", "dokument", 248000], ["Izlet ob morju.jpg", "slika", 3100000], ["Proracun 2026.ods", "dokument", 84000],
    ["Predstavitev.odp", "dokument", 1900000], ["Posnetek.mp4", "video", 88000000], ["Pesem.flac", "zvok", 31000000],
    ["Navodila.pdf", "dokument", 540000], ["Zapiski.md", "dokument", 4000], ["Racun-sept.pdf", "dokument", 120000],
    ["Slika-02.png", "slika", 800000], ["Arhiv.zip", "arhiv", 5400000], ["Seznam.csv", "dokument", 12000],
    ["Pismo.odt", "dokument", 30000], ["Naslovnica.svg", "slika", 90000], ["Intervju.ogg", "zvok", 9000000],
    ["Program.AppImage", "program", 90000000], ["Kopija.tar.gz", "arhiv", 200000000], ["Drugo.txt", "dokument", 900]
  ].forEach(function (x, i) { nedavne.push(dat(x[0], x[1], x[2], i * 5400)); });
  var ikona = function (b) { return "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><rect width="48" height="48" rx="11" fill="' + b + '"/><rect x="12" y="13" width="24" height="22" rx="3" fill="none" stroke="white" stroke-width="3"/></svg>'); };
  var prgTel = ["Zemljevidi|splet|#26789a", "Kamera|predstavnost|#b45058", "Beležka|pisarna|#2558ad", "Glasba|predstavnost|#674da7", "Šah|igre|#a56536", "Koledar|pisarna|#207454", "Risanje|drugo|#6949b0"];
  var prgPc = ["Urejevalnik besedil|pisarna|#2558ad", "Preglednice|pisarna|#207454", "Urejanje slik|predstavnost|#6949b0", "Video studio|predstavnost|#b45058", "Razvojno okolje|programiranje|#4a5a70", "Igra ploščic|igre|#a56536"];
  function programi(seznam, n) { return seznam.map(function (s, i) { var p = s.split("|"); return { id: n + ".app" + i, ime: p[0], opis: "", skupina: p[1], ikona: ikona(p[2]), naprava: n }; }); }
  var odgovori = {
    zacetek: { jezik: "sl", ozadje: window.__OZADJE || "", mape: [{ vrsta: "HOME", pot: dom, ime: "demo" }, { vrsta: "DOCUMENTS", pot: dom + "/Dokumenti" },
      { vrsta: "PICTURES", pot: dom + "/Slike" }, { vrsta: "VIDEOS", pot: dom + "/Videi" }, { vrsta: "MUSIC", pot: dom + "/Glasba" }, { vrsta: "DOWNLOAD", pot: dom + "/Prejemi" }],
      spletne: [{ ime: "Spletna pošta", url: "https://example.org/posta" }] },
    nedavne: nedavne,
    mapa: { pot: dom + "/Dokumenti", napaka: "", elementi: [{ ime: "Projekti", pot: dom + "/Dokumenti/Projekti", mapa: true, velikost: 0, spremenjeno: zdaj - 9000, vrsta: "mapa" }].concat(nedavne) },
    napraveZDatotekami: [{ id: "tel", ime: "Telefon (demo)", platforma: "android" }],
    datotekeNaprave: { ok: true, items: [{ id: "media:audio", name: "Glasba", type: "folder" }, { id: "v1", name: "Posnetek.mp4", type: "video", size: 20000000 }] },
    napraveSProgrami: [{ id: "tel", ime: "Telefon (demo)", platforma: "android" }, { id: "pc", ime: "Prenosnik (demo)", platforma: "windows" }, { id: "tv", ime: "TV (demo)", platforma: "android" }],
    programiNaprave: null,
    predvajalnikStanje: { stanje: "predvaja", naslov: "Pesem (demo)", izvor: "Ta računalnik", pozicija: 42, trajanje: 180 },
    programi: [], isciDatoteke: [], knjiznicaMedijev: []
  };
  window.SafeerOS = { klic: function (m, a) {
    if (m === "programiNaprave") {
      if (a[0] === "tv") return Promise.resolve({ ok: false, koda: "ni_odgovora", programi: [] });
      return Promise.resolve({ ok: true, programi: a[0] === "tel" ? programi(prgTel, "tel") : programi(prgPc, "pc") });
    }
    return Promise.resolve(odgovori[m] !== undefined ? odgovori[m] : null);
  } };
})();
