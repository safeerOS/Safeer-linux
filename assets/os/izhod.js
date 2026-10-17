/* Kam gre zvok - »Predvajaj na …« (lastnik, 14. 10. 2026: glasbo iz Medijskega centra hoce poslati na zvocnik v
 * domacem omrezju). Ena logika za hitre nastavitve zvoka in Medijski center (os.js), delovno povrsino (delovna.js) in
 * namizje QML (Namizje.qml): izbire iz klica »zvok« (safeer_os.zvok_stanje) in dejanja z isto privolitvijo kot prej -
 * zvocnik, ki ta trenutek igra drug vir (npr. TV), preklopimo sele po drugem pritisku.
 *
 * Brez DOM-a, okna in casovnikov: QML datoteko uvozi kot knjiznico JavaScript (import "../izhod.js"), stran kot <script>.
 * Gostitelj da `o` = { klic(metoda, argumenti, ok, napaka), obvesti(kljuc, zamenjave), osvezi(), pozneje(ms, fn),
 * narisi() }; besedila (kljuci) so v slovarju gostitelja, v vseh njegovih jezikih. */
var SafeerIzhod = (function () {
  "use strict";

  // Izbire: ta racunalnik, naprave v Safeer Linku in zvocniki DLNA v omrezju - izracuna jih Python v klicu »zvok«
  // (core/os_zvok.moznosti_izhoda), da je seznam isti tudi v oknu predvajalnika videa (GTK). Natanko ena je aktivna.
  function moznosti(z) {
    var m = z && z.moznosti;
    return m && m.length ? m : [{ vrsta: "racunalnik", id: "", ime: "", pod: "", aktiven: true, stanje: "" }];
  }
  function aktivna(z) {
    return moznosti(z).filter(function (m) { return m.aktiven; })[0] || null;
  }
  // Ali sploh obstaja kaj drugega kot ta racunalnik (za prazno stanje).
  function imaDruge(z) { return moznosti(z).length > 1; }

  // Stanje izbire na strani: katera izbira se ravno povezuje in kateri zvocnik caka na privolitev ({id: vir}).
  function novoStanje() { return { caka: "", potrdi: {} }; }

  // Nazaj na ta racunalnik: konca sejo na napravo v Linku ali na zvocnik.
  function nazaj(st, z, o) {
    var link = (z && z.link) || {};
    var metoda = (link.zvocnik || {}).naprava ? "zvokUstaviZvocnik" : "zvokUstavi";
    st.caka = "";
    o.klic(metoda, [], function () { o.obvesti("zvokNazaj"); o.pozneje(600, o.osvezi); },
      function () { o.obvesti("niUspelo"); o.osvezi(); });
  }
  function naNapravo(st, m, o) {
    st.caka = m.id;
    o.narisi();
    o.klic("zvokNaNapravo", [m.id], function (ok) {
      if (!ok) { st.caka = ""; o.obvesti("niUspelo"); } else o.obvesti("zvokNaNapravoZacet", { ime: m.ime });
      o.pozneje(800, o.osvezi);
      o.pozneje(6000, function () { if (st.caka === m.id) st.caka = ""; o.osvezi(); });
    }, function () { st.caka = ""; o.obvesti("niUspelo"); o.osvezi(); });
  }
  function naZvocnik(st, m, o) {
    var soglasje = !!st.potrdi[m.id];
    st.caka = m.id;
    delete st.potrdi[m.id];
    o.narisi();
    o.klic("zvokNaZvocnik", [m.id, soglasje], function (r) {
      st.caka = "";
      if (r && r.vir) { st.potrdi[m.id] = r.vir; o.obvesti("zvokZvocnikZaseden", { ime: m.ime, vir: r.vir }); }
      else if (!r || !r.ok) o.obvesti("niUspelo");
      else o.obvesti("zvokNaNapravoZacet", { ime: m.ime });
      o.osvezi();
      o.pozneje(3000, o.osvezi);
    }, function () { st.caka = ""; o.obvesti("niUspelo"); o.osvezi(); });
  }
  // Izbira vrstice: aktivne ne ponovimo; ta racunalnik = nazaj; sicer zacni na izbrani napravi ali zvocniku.
  function izberi(st, m, z, o) {
    if (!m || m.aktiven || (st.caka && st.caka === m.id)) return;
    if (m.vrsta === "racunalnik") nazaj(st, z, o);
    else if (m.vrsta === "naprava") naNapravo(st, m, o);
    else if (m.vrsta === "zvocnik") naZvocnik(st, m, o);
  }
  // Zamik zvoka na aktivnem zvocniku (ms, korak 50): slika videa pocaka zvocnik; shrani se na tej napravi.
  function zakasnitev(m, ms, o) {
    if (!m || m.vrsta !== "zvocnik" || !m.aktiven) return;
    m.zakasnitev = Math.max(0, Math.round(ms / 50) * 50);
    o.klic("zvokZakasnitevZvocnika", [m.id, m.zakasnitev], function () {}, function () { o.obvesti("niUspelo"); });
  }
  // Iskanje zvocnikov tece v ozadju (core/zvok_na_zvocnik.py, okoli 3 s): seznam preberemo znova po njem.
  function isci(st, o) {
    st.isce = true;
    o.narisi();
    o.klic("zvokIsciZvocnike", [], function () {
      o.pozneje(3500, function () { st.isce = false; o.osvezi(); });
    }, function () { st.isce = false; o.narisi(); });
  }

  return { moznosti: moznosti, aktivna: aktivna, imaDruge: imaDruge, novoStanje: novoStanje, izberi: izberi,
           nazaj: nazaj, naNapravo: naNapravo, naZvocnik: naZvocnik, isci: isci, zakasnitev: zakasnitev };
})();
