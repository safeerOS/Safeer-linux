// Preizkus glasovne slovnice daljinca (assets/link/daljinec.js) brez brskalnika.
//   node tests/test_daljinec_slovnica.js
// Ista datoteka daljinec.js je na telefonu, televizorju in Linuxu, zato preizkus tece tu za vse.
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

function nalozi(jezik, aplikacije) {
  const koda = fs.readFileSync(path.join(__dirname, "..", "assets", "link", "daljinec.js"), "utf8");
  const okno = {
    SafeerLink: { jezik: () => jezik, ukaz: () => {}, znaGovor: () => false },
    SafeerLinkStran: { jezik: jezik, prijaznoIme: (n) => n.ime },
    localStorage: { getItem: () => null, setItem: () => {} },
    addEventListener: () => {},
  };
  const dokument = { getElementById: () => null, querySelectorAll: () => [], addEventListener: () => {}, visibilityState: "visible" };
  const ctx = { window: okno, document: dokument, navigator: { language: jezik }, setTimeout, clearTimeout, Date, JSON, Math, encodeURIComponent, String, Number, parseInt, RegExp, Object, Array };
  ctx.window.window = ctx.window;
  vm.createContext(ctx);
  vm.runInContext(koda, ctx);
  const d = ctx.window.SafeerDaljinec;
  // Aplikacije naprave (kot bi jih vrnil ukaz "apps").
  d.odpri({ id: "tv-test", ime: "Televizor", zmoznosti: ["remote"] });
  // odpri() brez DOM-a samo nastavi stanje; seznam aplikacij vstavimo prek localStorage nadomestka:
  return d;
}

let napak = 0;
function preveri(opis, pogoj) {
  console.log((pogoj ? "  OK   " : "  NAPAKA ") + opis);
  if (!pogoj) napak++;
}
function r(d, besedilo) { return d.razumi(besedilo); }

// ---- slovensko, brez seznama aplikacij ----
{
  const d = nalozi("sl", []);
  let u = r(d, "glasneje"); preveri("glasneje -> volume up", u && u.dejanje === "volume" && u.parametri.direction === "up");
  u = r(d, "malo tišje prosim"); preveri("tišje -> volume down", u && u.dejanje === "volume" && u.parametri.direction === "down");
  u = r(d, "utišaj"); preveri("utišaj -> mute", u && u.parametri.direction === "mute");
  u = r(d, "glasnost na 30"); preveri("glasnost na 30 -> level 30", u && u.dejanje === "volume" && u.parametri.level === 30);
  u = r(d, "domov"); preveri("domov -> key home", u && u.dejanje === "key" && u.parametri.key === "home");
  u = r(d, "nazaj"); preveri("nazaj -> key back", u && u.parametri.key === "back");
  u = r(d, "pavza"); preveri("pavza -> key pause", u && u.parametri.key === "pause");
  u = r(d, "predvajaj"); preveri("predvajaj (samo) -> play_pause", u && u.parametri.key === "play_pause");
  u = r(d, "preklopi na program 25"); preveri("program 25 -> stevke 25", u && u.dejanje === "digits" && u.parametri.digits === "25");
  u = r(d, "odpri safeer.si"); preveri("odpri safeer.si -> open_url https", u && u.dejanje === "open_url" && u.parametri.url === "https://safeer.si");
  u = r(d, "poišči vreme v ljubljani"); preveri("poišči -> iskanje", u && u.dejanje === "open_url" && /google\.com\/search\?q=vreme%20v%20ljubljani/.test(u.parametri.url));
  u = r(d, "predvajaj siddharta"); preveri("predvajaj X -> youtube iskanje", u && u.dejanje === "open_url" && /youtube\.com\/results\?search_query=siddharta/.test(u.parametri.url));
  u = r(d, "odpri youtube"); preveri("odpri youtube (brez app) -> youtube.com", u && u.dejanje === "open_url" && u.parametri.url === "https://www.youtube.com/");
  u = r(d, "kaj je na zaslonu"); preveri("kaj je na zaslonu -> screenshot", u && u.dejanje === "screenshot");
  u = r(d, "počisti predpomnilnik"); preveri("počisti -> clear_cache", u && u.dejanje === "clear_cache");
  u = r(d, "abrakadabra neznano"); preveri("neznano -> iskanje z opozorilom", u && u.dejanje === "iskanje" && u.neznano === true);
  u = r(d, "stran dol"); preveri("stran dol -> scroll down", u && u.dejanje === "scroll" && u.parametri.direction === "down");
  u = r(d, "Nazaj."); preveri("locilo na koncu ne moti", u && u.parametri.key === "back");
  u = r(d, "odpri safeer.si."); preveri("pika za naslovom ne moti", u && u.dejanje === "open_url" && u.parametri.url === "https://safeer.si");
}

// ---- slovensko, z aplikacijami naprave ----
{
  const d = nalozi("sl", []);
  // Seznam aplikacij nastavimo prek razumi-ja: daljinec.js ga hrani v zaprtem stanju, zato
  // ga napolnimo z odzivom na ukaz "apps" (simulacija odgovora naprave).
  // Tu uporabimo interni obvod: odziv z ref, ki ga je ustvaril naloziAplikacije, ni dosegljiv
  // brez DOM-a, zato razumi preizkusimo z najdiAplikacijo prek localStorage (odpri prebere shranjene).
}
{
  const koda = fs.readFileSync(path.join(__dirname, "..", "assets", "link", "daljinec.js"), "utf8");
  const shranjene = JSON.stringify([{ package: "org.droidtv.playtv", label: "TV" }, { package: "com.google.android.youtube.tv", label: "YouTube" }, { package: "com.example.safeerbrowser", label: "Safeer Browser" }, { package: "com.netflix.ninja", label: "Netflix" }, { package: "com.google.android.youtube.tv", label: "YouTube" }]);
  const okno = {
    SafeerLink: { jezik: () => "sl", ukaz: () => {}, znaGovor: () => false },
    SafeerLinkStran: { jezik: "sl", prijaznoIme: (n) => n.ime },
    localStorage: { getItem: (k) => (k === "safeer_daljinec_apps_tv1" ? shranjene : null), setItem: () => {} },
    addEventListener: () => {},
  };
  const dokument = { getElementById: () => null, querySelectorAll: () => [], addEventListener: () => {}, visibilityState: "visible" };
  const ctx = { window: okno, document: dokument, navigator: { language: "sl" }, setTimeout, clearTimeout, Date, JSON, Math, encodeURIComponent, String, Number, parseInt, RegExp, Object, Array };
  ctx.window.window = ctx.window;
  vm.createContext(ctx);
  vm.runInContext(koda, ctx);
  const d = ctx.window.SafeerDaljinec;
  d.odpri({ id: "tv1", ime: "Televizor", zmoznosti: ["remote"] });
  let u = r(d, "odpri youtube"); preveri("odpri youtube -> YouTube", u && u.dejanje === "launch_app" && u.parametri.package === "com.google.android.youtube.tv");
  u = r(d, "zaženi netflix"); preveri("zaženi netflix -> launch_app", u && u.dejanje === "launch_app" && u.parametri.package === "com.netflix.ninja");
  u = r(d, "netflix"); preveri("samo ime -> launch_app", u && u.dejanje === "launch_app");
  u = r(d, "odpri brskalnik"); preveri("odpri brskalnik -> Safeer Browser", u && u.dejanje === "launch_app" && u.parametri.package === "com.example.safeerbrowser");
  u = r(d, "predvajaj linkin park na youtubu"); preveri("predvajaj X na youtubu -> open_in_app YouTube", u && u.dejanje === "open_in_app" && u.parametri.package === "com.google.android.youtube.tv" && /search_query=linkin%20park/.test(u.parametri.url));
  u = r(d, "odpri spotify"); preveri("odpri neobstojece -> napaka, ne iskanje", u && u.dejanje === "napaka");
  u = r(d, "odpri tv"); preveri("odpri tv -> aplikacija TV (tocno ime)", u && u.dejanje === "launch_app" && u.parametri.package === "org.droidtv.playtv");
  u = r(d, "yt"); preveri("yt ne najde playtv, ampak YouTube", u && u.dejanje === "launch_app" && u.parametri.package === "com.google.android.youtube.tv");
  u = r(d, "odpri televizijo"); preveri("televizija -> ne playtv po naključju (ni xplore) -> TV", u && u.dejanje === "launch_app" && u.parametri.package === "org.droidtv.playtv");
}

// ---- angleško ----
{
  const d = nalozi("en", []);
  let u = r(d, "volume up"); preveri("volume up", u && u.parametri.direction === "up");
  u = r(d, "set volume to 40"); preveri("set volume to 40", u && u.parametri.level === 40);
  u = r(d, "go back"); preveri("go back -> back", u && u.parametri.key === "back");
  u = r(d, "open example.com"); preveri("open example.com -> url", u && u.dejanje === "open_url" && u.parametri.url === "https://example.com");
  u = r(d, "search for cats"); preveri("search for cats", u && /q=cats/.test(u.parametri.url));
  u = r(d, "play some jazz on youtube"); preveri("play X on youtube", u && /youtube\.com\/results/.test(u.parametri.url) && /jazz/.test(u.parametri.url) && !/youtube%20/.test(u.parametri.url));
  u = r(d, "channel 12"); preveri("channel 12 -> digits", u && u.dejanje === "digits" && u.parametri.digits === "12");
}

// ---- nemško ----
{
  const d = nalozi("de", []);
  let u = r(d, "lauter"); preveri("de lauter", u && u.parametri.direction === "up");
  u = r(d, "öffne heise.de"); preveri("de öffne url", u && u.dejanje === "open_url" && u.parametri.url === "https://heise.de");
  u = r(d, "suche nach wetter berlin"); preveri("de suche", u && /q=wetter%20berlin/.test(u.parametri.url));
}

// ---- regresije 19. 10. 2026 (ocena hitrega prevajalnika na 66 ukazih sl + en) ----
// Daljinec upravlja natanko eno napravo; prijaznoIme kot v link.js (tehnicni ID -> Televizor/Zaslon).
function naloziNaprava(jezik, naprava, aplikacije) {
  const koda = fs.readFileSync(path.join(__dirname, "..", "assets", "link", "daljinec.js"), "utf8");
  const shranjene = JSON.stringify(aplikacije || []);
  const okno = {
    SafeerLink: { jezik: () => jezik, ukaz: () => {}, znaGovor: () => false },
    SafeerLinkStran: { jezik: jezik, prijaznoIme: (n) => (n.ime && !/^[a-z0-9]+-[a-z0-9-]{4,}$/i.test(n.ime) ? n.ime : n.vloga === "receiver" ? "Televizor" : "Zaslon") },
    localStorage: { getItem: (k) => (k === "safeer_daljinec_apps_" + naprava.id ? shranjene : null), setItem: () => {} },
    addEventListener: () => {},
  };
  const dokument = { getElementById: () => null, querySelectorAll: () => [], addEventListener: () => {}, visibilityState: "visible" };
  const ctx = { window: okno, document: dokument, navigator: { language: jezik }, setTimeout, clearTimeout, Date, JSON, Math, encodeURIComponent, String, Number, parseInt, RegExp, Object, Array };
  ctx.window.window = ctx.window;
  vm.createContext(ctx);
  vm.runInContext(koda, ctx);
  const d = ctx.window.SafeerDaljinec;
  d.odpri(naprava);
  return d;
}
const TELEFON = { id: "tel1", ime: "Pixel 7", platforma: "phone" };
const TELEVIZOR = { id: "tv1", ime: "Dnevna soba", platforma: "tv" };
const TABLICA_PO_IMENU = { id: "tab1", ime: "Tablica v kuhinji" };
const SPREJEMNIK = { id: "rec1", ime: "a1b2c3-d4e5f6", vloga: "receiver" };
const RACUNALNIK = { id: "pc1", ime: "Prenosnik", platforma: "linux" };
const YT = [{ package: "com.google.android.youtube.tv", label: "YouTube" }];
const smer = (u, s) => !!u && u.dejanje === "volume" && u.parametri.direction === s;
const tipkaJe = (u, k) => !!u && u.dejanje === "key" && u.parametri.key === k;
const urlJe = (u, url) => !!u && u.dejanje === "open_url" && u.parametri.url === url;
const zavrnjeno = (u, vrsta) => !!u && u.dejanje === "napaka" && u.drugaNaprava === vrsta && /\S/.test(u.opis || "");

// 1) Utisaj v vseh jezikih; "sound on the phone" ni "sound on" (prej: "turn off the sound on the phone" -> unmute).
const UTISAJ = {
  sl: [["izklopi zvok", "mute"], ["ugasni zvok", "mute"], ["izklopi zvok na telefonu", "mute"], ["vklopi zvok", "unmute"]],
  en: [["turn off the sound", "mute"], ["turn the sound off", "mute"], ["switch off the sound", "mute"], ["turn off the sound on the phone", "mute"],
    ["turn the sound off on my phone", "mute"], ["turn on the sound", "unmute"], ["turn the sound on", "unmute"]],
  de: [["schalte den Ton aus", "mute"], ["Ton ausschalten", "mute"], ["Ton aus auf dem Handy", "mute"], ["schalte den Ton an", "unmute"]],
  es: [["apaga el sonido", "mute"], ["quita el sonido en el teléfono", "mute"], ["desactiva el sonido", "mute"], ["activa el sonido", "unmute"]],
  fr: [["coupe le son", "mute"], ["éteins le son sur le téléphone", "mute"], ["désactive le son", "mute"], ["remets le son", "unmute"]],
  it: [["spegni l'audio", "mute"], ["togli l'audio sul telefono", "mute"], ["disattiva il suono", "mute"], ["riattiva l'audio", "unmute"]],
};
for (const jezik of Object.keys(UTISAJ)) {
  const d = naloziNaprava(jezik, TELEFON);
  for (const [stavek, s] of UTISAJ[jezik]) preveri(`${jezik} »${stavek}« -> ${s}`, smer(r(d, stavek), s));
}
{
  const d = naloziNaprava("en", { id: "x1", ime: "Zaslon" });
  preveri("en »turn off the sound on the radio« -> mute, ne unmute", smer(r(d, "turn off the sound on the radio"), "mute"));
  const tv = naloziNaprava("en", TELEVIZOR);
  preveri("en TV: »turn off the sound on the phone« -> ni unmute, zavrnjeno (telefon)", zavrnjeno(r(tv, "turn off the sound on the phone"), "telefon"));
}

// 2) Naslov iz stavka: brez polnil in fraz o napravi (prej "https://siol.netnatablici", "thewebsite24ur.com").
{
  const tab = naloziNaprava("sl", TABLICA_PO_IMENU);
  preveri("sl tablica po imenu: »odpri siol.net na tablici« -> https://siol.net", urlJe(r(tab, "odpri siol.net na tablici"), "https://siol.net"));
  preveri("sl »odpri spletno stran 24ur.com« -> https://24ur.com", urlJe(r(tab, "odpri spletno stran 24ur.com"), "https://24ur.com"));
  preveri("sl narekovano »odpri 24 ur . com« -> https://24ur.com", urlJe(r(tab, "odpri 24 ur . com"), "https://24ur.com"));
  preveri("sl narekovano »odpri 24 ur pika com« -> https://24ur.com", urlJe(r(tab, "odpri 24 ur pika com"), "https://24ur.com"));
  preveri("sl narekovano »odpri www . siol . net« -> https://www.siol.net", urlJe(r(tab, "odpri www . siol . net"), "https://www.siol.net"));
  preveri("sl »odpri vreme arso.si« -> https://arso.si (dolge besede se ne zlepijo)", urlJe(r(tab, "odpri vreme arso.si"), "https://arso.si"));
  let u = r(tab, "odpri stran o vremenu");
  preveri("sl »odpri stran o vremenu« ni naslov https://ovremenu", !!u && !/ovremenu/.test(String(u.parametri.url || "")));
  u = r(tab, "odpri ab cd.qqq");
  preveri("sl neznana koncnica se ne zlepi (abcd.qqq)", !!u && !/abcd\.qqq/.test(String(u.parametri.url || "")));
}
const NASLOVI = {
  en: [["open the website 24ur.com", "https://24ur.com"], ["open the site rtvslo.si on my phone", "https://rtvslo.si"], ["open 24 ur dot com", "https://24ur.com"]],
  de: [["öffne die Webseite 24ur.com", "https://24ur.com"], ["öffne siol.net auf dem Handy", "https://siol.net"], ["öffne 24 ur punkt com", "https://24ur.com"]],
  es: [["abre la página web 24ur.com", "https://24ur.com"], ["abre siol.net en el móvil", "https://siol.net"], ["abre 24 ur punto com", "https://24ur.com"]],
  fr: [["ouvre le site 24ur.com", "https://24ur.com"], ["ouvre siol.net sur le téléphone", "https://siol.net"], ["ouvre 24 ur point com", "https://24ur.com"]],
  it: [["apri il sito 24ur.com", "https://24ur.com"], ["apri siol.net sul telefono", "https://siol.net"], ["apri 24 ur punto com", "https://24ur.com"]],
};
for (const jezik of Object.keys(NASLOVI)) {
  const d = naloziNaprava(jezik, TELEFON);
  for (const [stavek, url] of NASLOVI[jezik]) preveri(`${jezik} »${stavek}« -> ${url}`, urlJe(r(d, stavek), url));
}
{
  // Izgovorjena pika samo pred znano koncnico na koncu naslova; navaden stavek ostane iskanje.
  let u = r(naloziNaprava("es", TELEFON), "busca a las tres en punto de la tarde");
  preveri("es »en punto de la tarde« ostane iskanje", !!u && /q=a%20las%20tres%20en%20punto%20de%20la%20tarde$/.test(u.parametri.url));
  u = r(naloziNaprava("fr", TELEFON), "cherche le point de vue");
  preveri("fr »le point de vue« ostane iskanje", !!u && /q=le%20point%20de%20vue$/.test(u.parametri.url));
}

// 3) Fraza o napravi nikoli v iskanje ali naslov; ukaz za drugo napravo se ne izvede (prej YouTube iskanje "na telefonu").
const POKAZI_YOUTUBE = {
  sl: ["pokaži mi YouTube na telefonu", "telefon"], en: ["show me YouTube on the phone", "telefon"], de: ["zeig mir YouTube auf dem Handy", "telefon"],
  es: ["muéstrame YouTube en el móvil", "telefon"], fr: ["montre-moi YouTube sur le téléphone", "telefon"], it: ["mostrami YouTube sul telefono", "telefon"],
};
for (const jezik of Object.keys(POKAZI_YOUTUBE)) {
  const [stavek, vrsta] = POKAZI_YOUTUBE[jezik];
  const tel = naloziNaprava(jezik, TELEFON, YT);
  const u = r(tel, stavek);
  preveri(`${jezik} telefon: »${stavek}« -> aplikacija YouTube`, !!u && u.dejanje === "launch_app" && u.parametri.package === YT[0].package);
  const tv = naloziNaprava(jezik, TELEVIZOR, YT);
  const z = r(tv, stavek);
  preveri(`${jezik} TV: »${stavek}« -> zavrnjeno z imenom naprave`, zavrnjeno(z, vrsta) && z.opis.indexOf("Dnevna soba") >= 0);
}
{
  const tel = naloziNaprava("sl", TELEFON);
  let u = r(tel, "pokaži mi YouTube na telefonu");
  preveri("sl brez aplikacij: YouTube brez »na telefonu« v naslovu", urlJe(u, "https://www.youtube.com/"));
  const pc = naloziNaprava("sl", RACUNALNIK);
  u = r(pc, "poišči recepte na računalniku");
  preveri("sl »poišči recepte na računalniku« -> iskanje samo »recepte«", !!u && /q=recepte$/.test(u.parametri.url) && u.ocisceno === "poišči recepte");
  u = r(pc, "predvajaj Rock Radio na računalniku");
  preveri("sl »predvajaj Rock Radio na računalniku« -> YouTube »rock radio«", !!u && /search_query=rock%20radio$/.test(u.parametri.url));
  u = r(naloziNaprava("en", RACUNALNIK), "search for Peppa Pig on my PC");
  preveri("en »search for Peppa Pig on my PC« -> iskanje »peppa pig«", !!u && /q=peppa%20pig$/.test(u.parametri.url));
  u = r(naloziNaprava("sl", SPREJEMNIK), "glasneje na televizorju");
  preveri("sl sprejemnik (vloga receiver): »glasneje na televizorju« -> volume up", smer(u, "up"));
  u = r(naloziNaprava("sl", TELEVIZOR), "utišaj tablico");
  preveri("sl TV: »utišaj tablico« -> zavrnjeno (tablica)", zavrnjeno(u, "tablica"));
  u = r(naloziNaprava("en", TELEVIZOR), "pause the TV");
  preveri("en TV: »pause the TV« -> pause", tipkaJe(u, "pause"));
  u = r(naloziNaprava("sl", TELEVIZOR), "poišči nov telefon");
  preveri("sl TV: »poišči nov telefon« ostane iskanje", !!u && /q=nov%20telefon$/.test(u.parametri.url));
}

// 4) Pavza s predmetom (prej spletno iskanje "daj na pavzo", "ustavi glasbo").
const PAVZA = {
  sl: ["daj na pavzo", "ustavi glasbo", "ustavi predvajanje", "ustavi glasbo na telefonu"],
  en: ["pause the music", "stop the music", "stop playback", "pause it", "stop the music on the phone"],
  de: ["pausiere die Musik", "stoppe die Musik", "Wiedergabe stoppen", "halte die Musik an"],
  es: ["pausa la música", "para la música", "detén la reproducción", "pon la música en pausa"],
  fr: ["mets la musique en pause", "arrête la musique", "arrête la lecture"],
  it: ["metti in pausa la musica", "ferma la musica", "interrompi la riproduzione"],
};
for (const jezik of Object.keys(PAVZA)) {
  const d = naloziNaprava(jezik, TELEFON);
  for (const stavek of PAVZA[jezik]) preveri(`${jezik} »${stavek}« -> key pause`, tipkaJe(r(d, stavek), "pause"));
}
{
  preveri("sl »nadaljuj predvajanje« -> play_pause", tipkaJe(r(naloziNaprava("sl", TELEFON), "nadaljuj predvajanje"), "play_pause"));
  preveri("en »resume playback« -> play_pause", tipkaJe(r(naloziNaprava("en", TELEFON), "resume playback"), "play_pause"));
}

// Racunalnik s Safeer OS (search.query): izgovorjeno gre v iskalno lupo racunalnika. Do 19. 10. 2026 je parameter
// izvediBesedilo(besedilo) zakril funkcijo besedilo() in ta pot je vedno padla s TypeError.
{
  const koda = fs.readFileSync(path.join(__dirname, "..", "assets", "link", "daljinec.js"), "utf8");
  const klici = [];
  const element = () => ({ textContent: "", hidden: false, style: {}, dataset: {}, classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    setAttribute() {}, removeAttribute() {}, addEventListener() {}, appendChild() {}, querySelector: () => null, querySelectorAll: () => [] });
  const elementi = {};
  const okno = {
    SafeerLink: { jezik: () => "sl", ukaz: (id, dejanje, parametri, ref) => klici.push({ id, dejanje, parametri: JSON.parse(parametri || "{}"), ref }), znaGovor: () => false },
    SafeerLinkStran: { jezik: "sl", prijaznoIme: (n) => n.ime },
    localStorage: { getItem: () => null, setItem: () => {} },
    addEventListener: () => {},
  };
  const dokument = { getElementById: (id) => (elementi[id] = elementi[id] || element()), querySelectorAll: () => [], addEventListener: () => {},
    visibilityState: "visible", body: element(), createElement: () => element() };
  const ctx = { window: okno, document: dokument, navigator: { language: "sl" }, setTimeout, clearTimeout, Date, JSON, Math, encodeURIComponent,
    String, Number, parseInt, RegExp, Object, Array };
  ctx.window.window = ctx.window;
  vm.createContext(ctx);
  let napaka = null;
  try {
    vm.runInContext(koda, ctx);
    const d = ctx.window.SafeerDaljinec;
    d.odpri(RACUNALNIK);
    const stanjeKlic = klici.find((k) => k.dejanje === "status");
    if (stanjeKlic) d.odziv({ ref: stanjeKlic.ref, ok: true, data: { actions: ["search.query", "volume", "key"] } });
    d.govor({ stanje: "koncno", besedilo: "poisci vreme v ljubljani" });
  } catch (e) {
    napaka = e;
  }
  preveri("racunalnik: izgovorjeno gre v search.query brez napake", !napaka && klici.some((k) => k.dejanje === "search.query" && /vreme/.test(k.parametri.q || "")));
  if (napaka) console.log("   " + napaka);
}

console.log();
if (napak) { console.log("Napak: " + napak); process.exit(1); }
console.log("Vse v redu.");
