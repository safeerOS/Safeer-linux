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

console.log();
if (napak) { console.log("Napak: " + napak); process.exit(1); }
console.log("Vse v redu.");
