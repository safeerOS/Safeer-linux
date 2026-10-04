"use strict";

const assert = require("assert");
const { nameraIskanja, brezNaglasa, ujemaBesede } = require("../assets/os/iskanje.js");

const podatki = {
  spletne: [
    { ime: "YouTube", url: "https://www.youtube.com" },
    { ime: "Gmail", url: "https://mail.google.com" }
  ],
  programi: [{ ime: "LibreOffice Writer", splosno: "Writer", kljucne: ["document"] }],
  datoteke: [{ ime: "porocilo.pdf", pot: "/home/ana/porocilo.pdf" }],
  mediji: [{ spletna: { ime: "Radio Slovenija", url: "https://radio.test" } }],
  naprave: [{ ime: "Televizor dnevna", id: "tv-1" }]
  ,sporocila: [{ oseba: { ime: "Ana Novak", identitete: [["email", "ana@example.test"]] }, pogovori: [{ zadnje_sporocilo: "Se vidiva" }] }]
};

assert.deepStrictEqual(nameraIskanja("example.org", podatki).razlog, "naslov");
assert.deepStrictEqual(nameraIskanja("http://localhost:8080", podatki).razlog, "naslov");
assert.strictEqual(nameraIskanja("yt", podatki).zadetek.ime, "YouTube");
assert.strictEqual(nameraIskanja("tube", podatki).zadetek.ime, "YouTube");
assert.strictEqual(nameraIskanja("writer", podatki).vrsta, "programi");
assert.strictEqual(nameraIskanja("porocilo.pdf", podatki).vrsta, "datoteke");
assert.strictEqual(nameraIskanja("film", podatki).vrsta, "media");
assert.strictEqual(nameraIskanja("musique", podatki).vrsta, "media");
assert.strictEqual(nameraIskanja("películas", podatki).vrsta, "media");
assert.strictEqual(nameraIskanja("televizor", podatki).vrsta, "naprave");
assert.strictEqual(nameraIskanja("Ana Novak", podatki).vrsta, "sporocila");
assert.strictEqual(nameraIskanja("vreme jutri", podatki).razlog, "iskanje");

// Brez sumnikov in posebnih crk (ista tabela kot v Pythonu), vec besed v poljubnem vrstnem redu.
assert.strictEqual(brezNaglasa("Ščit Đorđe Łódź Søren Straße"), "scit dorde lodz soren strasse");
assert.ok(ujemaBesede("Žur na morju 2026.mp4", "zur"));
assert.ok(ujemaBesede("Žur na morju 2026.mp4", "MORJU žur"));
assert.ok(!ujemaBesede("Žur na morju 2026.mp4", "zur hribi"));
assert.ok(ujemaBesede("karkoli", ""), "prazen niz ustreza vsemu");
assert.ok(ujemaBesede("karkoli", "   "));

console.log("pametno iskanje: OK");
