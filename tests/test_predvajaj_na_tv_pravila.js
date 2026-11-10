#!/usr/bin/env node
'use strict';
const path = require('path');
const PredvajajNaTvPravila = require(path.join(__dirname, '..', 'assets', 'os', 'predvajaj_na_tv_pravila.js'));

let preverb = 0;
let napak = 0;

function preveriEnako(opis, pricakovano, dobljeno) {
    preverb++;
    const strPricakovano = JSON.stringify(pricakovano);
    const strDobljeno = JSON.stringify(dobljeno);
    if (strPricakovano === strDobljeno) {
        // console.log(`  ok  ${opis}`);
    } else {
        napak++;
        console.log(`  NAPAKA  ${opis}: pricakovano ${strPricakovano}, dobljeno ${strDobljeno}`);
    }
}

function preveri(vOzjemKrogu, polja, pricakovano) {
    const izid = PredvajajNaTvPravila.preveri(vOzjemKrogu, polja);
    preveriEnako(`preveri(${vOzjemKrogu}, ${JSON.stringify(polja)})`, pricakovano, izid);
}

const Vrsta = PredvajajNaTvPravila.Vrsta;
const Zavrnitev = PredvajajNaTvPravila.Zavrnitev;

function zavrnjeno(razlog) {
    return { vrsta: "Zavrnjeno", razlog: razlog };
}

function sprejeto(vrsta, id, sezona, epizoda, naslov, polozajMs) {
    return {
        vrsta: "Sprejeto",
        zahteva: {
            vrsta: vrsta,
            id: id,
            sezona: sezona,
            epizoda: epizoda,
            naslov: naslov,
            polozajMs: polozajMs
        }
    };
}

// a) ni v krogu + veljavno -> NI_V_KROGU
preveri(false, { vrsta: "film", id: "tt1234567" }, zavrnjeno(Zavrnitev.NI_V_KROGU));
// ni v krogu + neveljavno -> NI_V_KROGU
preveri(false, { vrsta: "nepoznano" }, zavrnjeno(Zavrnitev.NI_V_KROGU));

// b) neznana vrsta
preveri(true, { vrsta: "FILM", id: "tt1234567" }, zavrnjeno(Zavrnitev.NEZNANA_VRSTA));
preveri(true, { vrsta: "nesto" }, zavrnjeno(Zavrnitev.NEZNANA_VRSTA));

// c) id
// FILM
preveri(true, { vrsta: "film", id: "tt1234567" }, sprejeto(Vrsta.FILM, "tt1234567", null, null, "", 0));
preveri(true, { vrsta: "film", id: "tt1234567890" }, sprejeto(Vrsta.FILM, "tt1234567890", null, null, "", 0));
preveri(true, { vrsta: "film", id: "tt1234567/../x" }, zavrnjeno(Zavrnitev.NEVELJAVEN_ID));
preveri(true, { vrsta: "film", id: "tt1234567%00" }, zavrnjeno(Zavrnitev.NEVELJAVEN_ID));
preveri(true, { vrsta: "film", id: "http://x" }, zavrnjeno(Zavrnitev.NEVELJAVEN_ID));
preveri(true, { vrsta: "film", id: "tt12345678901" }, zavrnjeno(Zavrnitev.NEVELJAVEN_ID));
preveri(true, { vrsta: "film", id: "tt123456" }, zavrnjeno(Zavrnitev.NEVELJAVEN_ID));
preveri(true, { vrsta: "film", id: "tt١٢٣٤٥٦٧" }, zavrnjeno(Zavrnitev.NEVELJAVEN_ID));
preveri(true, { vrsta: "film", id: " tt1234567" }, zavrnjeno(Zavrnitev.NEVELJAVEN_ID));

// KANAL
preveri(true, { vrsta: "kanal", id: "kanal1" }, sprejeto(Vrsta.KANAL, "kanal1", null, null, "", 0));
preveri(true, { vrsta: "kanal", id: "a".repeat(64) }, sprejeto(Vrsta.KANAL, "a".repeat(64), null, null, "", 0));
preveri(true, { vrsta: "kanal", id: "a".repeat(65) }, zavrnjeno(Zavrnitev.NEVELJAVEN_ID));
preveri(true, { vrsta: "kanal", id: ".." }, zavrnjeno(Zavrnitev.NEVELJAVEN_ID));
preveri(true, { vrsta: "kanal", id: "a..b" }, zavrnjeno(Zavrnitev.NEVELJAVEN_ID));
preveri(true, { vrsta: "kanal", id: ".skrit" }, zavrnjeno(Zavrnitev.NEVELJAVEN_ID));
preveri(true, { vrsta: "kanal", id: "a/b" }, zavrnjeno(Zavrnitev.NEVELJAVEN_ID));

// d) EPIZODA
preveri(true, { vrsta: "epizoda", id: "tt1234567", sezona: "1", epizoda: "2" }, sprejeto(Vrsta.EPIZODA, "tt1234567", 1, 2, "", 0));
preveri(true, { vrsta: "epizoda", id: "tt1234567", sezona: "0", epizoda: "9999" }, sprejeto(Vrsta.EPIZODA, "tt1234567", 0, 9999, "", 0));
preveri(true, { vrsta: "epizoda", id: "tt1234567", sezona: "1000", epizoda: "1" }, zavrnjeno(Zavrnitev.NEVELJAVNA_EPIZODA));
preveri(true, { vrsta: "epizoda", id: "tt1234567", sezona: "1", epizoda: "10000" }, zavrnjeno(Zavrnitev.NEVELJAVNA_EPIZODA));
preveri(true, { vrsta: "epizoda", id: "tt1234567", sezona: "1", epizoda: "0" }, zavrnjeno(Zavrnitev.NEVELJAVNA_EPIZODA));
preveri(true, { vrsta: "epizoda", id: "tt1234567", sezona: "-1", epizoda: "1" }, zavrnjeno(Zavrnitev.NEVELJAVNA_EPIZODA));
preveri(true, { vrsta: "epizoda", id: "tt1234567", sezona: "1" }, zavrnjeno(Zavrnitev.NEVELJAVNA_EPIZODA));

// e) naslov
preveri(true, { vrsta: "film", id: "tt1234567", naslov: "a".repeat(200) }, sprejeto(Vrsta.FILM, "tt1234567", null, null, "a".repeat(200), 0));
preveri(true, { vrsta: "film", id: "tt1234567", naslov: "a".repeat(201) }, zavrnjeno(Zavrnitev.PREDOLGO));
preveri(true, { vrsta: "film", id: "tt1234567", naslov: "a\nb\u0000c" }, sprejeto(Vrsta.FILM, "tt1234567", null, null, "abc", 0));

// f) polozajMs
preveri(true, { vrsta: "film", id: "tt1234567", polozajMs: "86400000" }, sprejeto(Vrsta.FILM, "tt1234567", null, null, "", 86400000));
preveri(true, { vrsta: "film", id: "tt1234567", polozajMs: "86400001" }, zavrnjeno(Zavrnitev.NEVELJAVEN_POLOZAJ));
preveri(true, { vrsta: "film", id: "tt1234567", polozajMs: "-1" }, zavrnjeno(Zavrnitev.NEVELJAVEN_POLOZAJ));
preveri(true, { vrsta: "film", id: "tt1234567", polozajMs: "1e3" }, zavrnjeno(Zavrnitev.NEVELJAVEN_POLOZAJ));
preveri(true, { vrsta: "film", id: "tt1234567", polozajMs: "1234567890" }, zavrnjeno(Zavrnitev.NEVELJAVEN_POLOZAJ)); // 10 stevk

// KANAL polozaj vedno 0
preveri(true, { vrsta: "kanal", id: "kanal1", polozajMs: "123" }, sprejeto(Vrsta.KANAL, "kanal1", null, null, "", 0));

// Krozna pot
const z1 = { vrsta: Vrsta.FILM, id: "tt1234567", sezona: null, epizoda: null, naslov: "Film", polozajMs: 1234 };
preveriEnako("krozna pot z1", sprejeto(Vrsta.FILM, "tt1234567", null, null, "Film", 1234), PredvajajNaTvPravila.preveri(true, PredvajajNaTvPravila.sporocilo(z1)));

const z2 = { vrsta: Vrsta.EPIZODA, id: "tt1234567", sezona: 1, epizoda: 2, naslov: "Ep", polozajMs: 1234 };
preveriEnako("krozna pot z2", sprejeto(Vrsta.EPIZODA, "tt1234567", 1, 2, "Ep", 1234), PredvajajNaTvPravila.preveri(true, PredvajajNaTvPravila.sporocilo(z2)));

const z3 = { vrsta: Vrsta.KANAL, id: "kanal1", sezona: null, epizoda: null, naslov: "Kan", polozajMs: 0 };
preveriEnako("krozna pot z3", sprejeto(Vrsta.KANAL, "kanal1", null, null, "Kan", 0), PredvajajNaTvPravila.preveri(true, PredvajajNaTvPravila.sporocilo(z3)));

// Besedila zavrnitve
const jeziki = ["sl", "en", "de", "es", "fr", "it"];
const zavrnitve = [
    Zavrnitev.NI_V_KROGU,
    Zavrnitev.NEZNANA_VRSTA,
    Zavrnitev.NEVELJAVEN_ID,
    Zavrnitev.NEVELJAVNA_EPIZODA,
    Zavrnitev.PREDOLGO,
    Zavrnitev.NEVELJAVEN_POLOZAJ
];
for (const r of zavrnitve) {
    for (const j of jeziki) {
        const besedilo = PredvajajNaTvPravila.besediloZavrnitve(r, j);
        preveriEnako(`besediloZavrnitve(${r}, ${j})`, true, besedilo.length > 0);
    }
}

// Dodatni primeri za JS
// polja = null
preveri(true, null, zavrnjeno(Zavrnitev.NEZNANA_VRSTA));
preveri(true, undefined, zavrnjeno(Zavrnitev.NEZNANA_VRSTA));

// polja z ne-nizi (stevilo, objekt, polje)
preveri(true, { vrsta: "film", id: 1234567 }, zavrnjeno(Zavrnitev.NEVELJAVEN_ID));
preveri(true, { vrsta: "film", id: "tt1234567", naslov: {} }, sprejeto(Vrsta.FILM, "tt1234567", null, null, "", 0));
preveri(true, { vrsta: "film", id: "tt1234567", polozajMs: [] }, sprejeto(Vrsta.FILM, "tt1234567", null, null, "", 0));

// prototipna polja (__proto__, constructor kot kljuc) se prezrejo
const zlobnaPolja = JSON.parse('{"vrsta": "film", "id": "tt1234567", "__proto__": {"naslov": "zlo"}, "constructor": "zlo"}');
preveri(true, zlobnaPolja, sprejeto(Vrsta.FILM, "tt1234567", null, null, "", 0));

// 10 000 nakljucnih vhodov ne vrze izjeme
let nakljucnihPreverb = 0;
try {
    for (let i = 0; i < 10000; i++) {
        const nakljucnaPolja = {};
        if (Math.random() > 0.5) nakljucnaPolja.vrsta = Math.random().toString(36);
        if (Math.random() > 0.5) nakljucnaPolja.id = Math.random().toString(36);
        if (Math.random() > 0.5) nakljucnaPolja.sezona = Math.random().toString(36);
        if (Math.random() > 0.5) nakljucnaPolja.epizoda = Math.random().toString(36);
        if (Math.random() > 0.5) nakljucnaPolja.naslov = Math.random().toString(36);
        if (Math.random() > 0.5) nakljucnaPolja.polozajMs = Math.random().toString(36);

        // Tudi ne-nizi
        if (Math.random() > 0.9) nakljucnaPolja.vrsta = 123;
        if (Math.random() > 0.9) nakljucnaPolja.id = {};

        PredvajajNaTvPravila.preveri(Math.random() > 0.5, nakljucnaPolja);
        nakljucnihPreverb++;
    }
    preveriEnako("10000 nakljucnih vhodov", 10000, nakljucnihPreverb);
} catch (e) {
    napak++;
    console.log("NAPAKA: Izjema pri nakljucnih vhodih: " + e);
}

if (napak > 0) {
    console.log(`NAPAK: ${napak}`);
    process.exit(1);
}
console.log(`VSE OK (${preverb} preverb)`);
process.exit(0);
