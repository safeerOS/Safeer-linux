'use strict';
// Safeer DRM: predvajalnik zaščitenih vsebin (Widevine prek castLabs ECS) za Splet in Safeer predvajalnik.
//
// Vdelani način (tako ga zažene Safeer OS; isti dogovor kot SafeerMediaWebView.exe):
//   safeer-drm --parent=<okno> --url=<https> --profile=<mapa> --state=<events.jsonl> --command=<command.txt>
//   Okno je brez okvirja in brez gumba v opravilni vrstici; v »events.jsonl« zapiše WINDOW_HANDLE, Safeer OS
//   ga vstavi v svoje okno (uporabnik vidi isti predvajalnik kot vedno). Ukazi v command.txt: back, reload.
// Spotify (core/spotify_racun.py): safeer-drm --url=https://open.spotify.com/ --spotify=1 [--skrit=1] [--scit=<pravila>]
//   --profile --state --command, brez --parent: lastno okno za prijavo, po prijavi skrito (ukaza skrij/pokazi).
//   Medijski center stran upravlja s CDP prek webContents.debugger (brez vrat in brez omrezja): ukaz
//   cdp:<id>:<base64 JSON {expression}> izvede Runtime.evaluate, odgovor gre v events.jsonl (vrsta CDP).
// Samostojni način (za preizkus): safeer-drm <https-URL>
const fs = require('fs');
const path = require('path');
const { app, components, BrowserWindow, session, webFrameMain } = require('electron');

const argumenti = {};
for (const a of process.argv.slice(1)) {
  const m = /^--([a-z]+)=(.*)$/i.exec(a);
  if (m) argumenti[m[1].toLowerCase()] = m[2];
}
const vdelan = Boolean(argumenti.parent);
// Storitev (Netflix, Disney+ ...): uporabnik sam brska in se prijavlja - brez samodejnega klika in brez omejitve domene.
const storitev = argumenti.storitev === '1';
const PREIZKUS = 'https://bitmovin.com/demos/drm';
const statePath = argumenti.state || '';
const commandPath = argumenti.command || '';
// Spotify: stran upravlja Medijski center (seznami, predvajanje), okno je vidno samo za prijavo.
const spotify = argumenti.spotify === '1';
const skrit = spotify && argumenti.skrit === '1';
// Ukazi iz command.txt: vdelano okno ali Spotify (mapa seje je zasebna, pise jo samo Safeer OS).
const nadzor = vdelan || Boolean(spotify && commandPath);

function zapisi(type, detail = '') {
  if (!statePath) { console.log(`[safeer-drm] ${type} ${detail}`); return; }
  try { fs.appendFileSync(statePath, JSON.stringify({ time: new Date().toISOString(), type, detail }) + '\n'); } catch (_) {}
}
function varenGostitelj(raw) { try { return new URL(raw).hostname; } catch (_) { return 'invalid'; } }
function osnovnaDomena(host) { const d = host.replace(/^\.+|\.+$/g, '').toLowerCase().split('.'); return d.length >= 2 ? d.slice(-2).join('.') : host.toLowerCase(); }

function zacetniUrl() {
  // --url velja tudi brez --parent (Spotify: lastno okno); samostojni preizkus: prvi naslov https v ukazni vrstici.
  const kandidati = vdelan || argumenti.url ? [argumenti.url] : process.argv.slice(1);
  for (const a of kandidati) { try { const u = new URL(a); if (u.protocol === 'https:') return u.href; } catch (_) {} }
  return vdelan || argumenti.url ? null : PREIZKUS;
}
const prviUrl = zacetniUrl();
if ((vdelan || argumenti.url) && !prviUrl) { process.exitCode = 2; app.quit(); }

// Profil (piškotki, predpomnilnik) je za vsako sejo svoj, kot pri WebView2; Widevine modul ostane v
// skupni mapi aplikacije, da se ne prenaša ob vsakem predvajanju.
if (argumenti.profile) { fs.mkdirSync(argumenti.profile, { recursive: true }); app.setPath('sessionData', argumenti.profile); }
// Samo za meritve: SAFEER_DRM_CDP=<vrata> odpre razhroščevanje na 127.0.0.1 (Safeer OS te spremenljivke nikoli ne nastavi).
if (/^\d{4,5}$/.test(process.env.SAFEER_DRM_CDP || '')) { app.commandLine.appendSwitch('remote-debugging-address', '127.0.0.1'); app.commandLine.appendSwitch('remote-debugging-port', process.env.SAFEER_DRM_CDP); }
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');
app.commandLine.appendSwitch('disable-background-mode');
app.commandLine.appendSwitch('host-resolver-rules', 'MAP *.cfd 127.0.0.1, MAP *.buzz 127.0.0.1, MAP *.monster 127.0.0.1, MAP *.top 127.0.0.1, MAP *.click 127.0.0.1');
// Strani naj vidijo navaden Chrome (nekateri ponudniki zavrnejo »Electron« v UA).
app.userAgentFallback = app.userAgentFallback.replace(/ (Electron|safeer-drm|SafeerDRM|Safeer DRM)\/\S+/g, '');

const ZAPRTE_KONCNICE = ['monetag.com', '20bet.com', '1xbet.com', 'onclick.com', 'popunder.net', 'popcash.net', 'popads.net',
  'propellerads.com', 'exoclick.com', 'adsterra.com', 'juicyads.com', 'trafficjunky.com', 'adnxs.com', 'criteo.com', 'histats.com',
  'doubleclick.net', 'googlesyndication.com', 'clarity.ms', 'hotjar.com', 'bet365.com', 'parimatch.com', 'vulkan.com',
  'mostbet.com', 'pinup.com', 'admaven.com', 'hilltopads.com', 'a-ads.com'];
const ZAPRTI_ZNAKI = ['monetag', '20bet', '1xbet', 'onclick', 'popunder', 'popcash', 'popads', 'propellerads', 'exoclick',
  'adsterra', 'juicyads', 'trafficjunky', 'adnxs', 'criteo', 'histats', 'doubleclick', 'googlesyndication', 'disable-devtool',
  'clarity.ms', 'hotjar', 'bet365', 'parimatch', 'vulkan', 'mostbet', 'pinup', 'admaven', 'hilltopads', 'a-ads', '23vlcfp', '2lizguk'];
function zaprtGostitelj(raw) {
  let u; try { u = new URL(raw); } catch (_) { return ''; }
  if (u.protocol !== 'https:' && u.protocol !== 'http:') return '';
  const h = u.hostname.replace(/\.$/, '').toLowerCase();
  if (h === '127.0.0.1' || h === 'localhost' || h === 'tmdb.org' || h.endsWith('.tmdb.org') || h === 'themoviedb.org' || h.endsWith('.themoviedb.org')) return '';
  if (ZAPRTE_KONCNICE.some(d => h === d || h.endsWith('.' + d))) return h;
  const deli = h.split('.');
  return ZAPRTI_ZNAKI.some(z => deli.some(d => d.includes(z))) ? h : '';
}

// Scit za Spotify (core/adblock.SPOTIFY_OGLASI): Safeer OS zapise pravila v mapo seje (--scit); brez datoteke nic.
function beriPravila(pot) {
  try { const p = JSON.parse(fs.readFileSync(pot, 'utf8')); return p && typeof p === 'object' ? p : null; } catch (_) { return null; }
}
const pravila = spotify && argumenti.scit ? beriPravila(argumenti.scit) : null;
// Skripte, ki jih je uporabnik sam uvozil in vklopil (core/uporabniske_skripte.py): [{ime, koda}], samo v strani Spotify.
function beriSkripte(pot) {
  try {
    const p = JSON.parse(fs.readFileSync(pot, 'utf8'));
    return Array.isArray(p) ? p.filter(s => s && typeof s.koda === 'string').slice(0, 50) : [];
  } catch (_) { return []; }
}
const uporabniskeSkripte = spotify && argumenti.skripte ? beriSkripte(argumenti.skripte) : [];
function oglasnaZahteva(raw) {
  if (!pravila) return false;
  let u; try { u = new URL(raw); } catch (_) { return false; }
  const h = u.hostname.toLowerCase();
  if ((pravila.gostitelji || []).some(d => h === d || h.endsWith('.' + d))) return true;
  const pot = u.pathname;
  return (pravila.poti || []).some(([d, p]) => (h === d || h.endsWith('.' + d)) && pot.startsWith(p));
}

// Spotify, glavni svet strani pred njenimi skriptami (Page.addScriptToEvaluateOnNewDocument): zeton strani ostane v
// zaprtju (nikoli na disk ali v dnevnik). Medijski center ga uporabi samo prek klic() (https://api.spotify.com/v1/) in
// pf() - isti klic GraphQL kot spletna aplikacija (api-partner.spotify.com/pathfinder), z vzorcem, ki ga je poslala stran.
const SPOTIFY_ZACETEK = `(() => {
  if (window.__safeerSpotify) return;
  let zeton = '', utisano = false;
  const glave = {};          // client-token, app-platform ... (kot jih poslje stran)
  const vzorci = {};         // pathfinder: operationName -> { hash, spremenljivke }
  const mediji = new Set();
  const SPOTIFY = /^https:\\/\\/([a-z0-9-]+\\.)*spotify\\.com\\//i;
  const KOPIRAJ = ['client-token', 'app-platform', 'spotify-app-version', 'accept-language'];
  function preberiGlave(h) {
    const izid = {};
    try {
      if (!h) return izid;
      if (typeof Headers !== 'undefined' && h instanceof Headers) h.forEach((v, k) => { izid[k.toLowerCase()] = String(v); });
      else if (Array.isArray(h)) h.forEach(x => { izid[String(x[0]).toLowerCase()] = String(x[1]); });
      else Object.keys(h).forEach(k => { izid[k.toLowerCase()] = String(h[k]); });
    } catch (_) {}
    return izid;
  }
  function vzemi(g) {
    const m = /^Bearer\\s+(\\S+)$/i.exec(g.authorization || '');
    if (m) zeton = m[1];
    KOPIRAJ.forEach(k => { if (g[k] && g[k].length < 2000) glave[k] = g[k]; });
  }
  function zapomniVzorec(url, telo) {
    try {
      if (!/^https:\\/\\/api-partner\\.spotify\\.com\\/pathfinder\\/v\\d\\/query/.test(url)) return;
      let d = null;
      if (typeof telo === 'string' && telo) d = JSON.parse(telo);
      else {
        const u = new URL(url);
        d = { operationName: u.searchParams.get('operationName'), variables: JSON.parse(u.searchParams.get('variables') || '{}'),
              extensions: JSON.parse(u.searchParams.get('extensions') || '{}') };
      }
      const hash = d && d.extensions && d.extensions.persistedQuery && d.extensions.persistedQuery.sha256Hash;
      if (d && d.operationName && /^[0-9a-f]{64}$/.test(String(hash || ''))) vzorci[d.operationName] = { hash, spremenljivke: d.variables || {} };
    } catch (_) {}
  }
  const izvFetch = window.fetch;
  window.fetch = function (vir, nast) {
    try {
      const url = typeof vir === 'string' ? vir : String((vir && vir.url) || vir || '');
      if (SPOTIFY.test(url)) {
        vzemi(Object.assign(preberiGlave(vir && vir.headers), preberiGlave(nast && nast.headers)));
        zapomniVzorec(url, nast && nast.body);
      }
    } catch (_) {}
    return izvFetch.apply(this, arguments);
  };
  const izvOdpri = XMLHttpRequest.prototype.open, izvGlava = XMLHttpRequest.prototype.setRequestHeader, izvPoslji = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (_m, url) { try { this.__safeerUrl = String(url || ''); } catch (_) {} return izvOdpri.apply(this, arguments); };
  XMLHttpRequest.prototype.setRequestHeader = function (k, v) {
    try { if (SPOTIFY.test(this.__safeerUrl || '')) vzemi({ [String(k).toLowerCase()]: String(v) }); } catch (_) {}
    return izvGlava.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function (telo) { try { zapomniVzorec(this.__safeerUrl || '', telo); } catch (_) {} return izvPoslji.apply(this, arguments); };
  const izvPlay = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    try { mediji.add(this); if (utisano) this.muted = true; } catch (_) {}
    return izvPlay.apply(this, arguments);
  };
  async function poslji(url, metoda, telo, dodatne) {
    if (!zeton) return { status: 0, napaka: 'brez_zetona' };
    const h = Object.assign({}, glave, dodatne || {}, { authorization: 'Bearer ' + zeton });
    const r = await izvFetch.call(window, url, { method: metoda, credentials: 'omit', headers: h, body: telo === undefined ? undefined : JSON.stringify(telo) });
    let podatki = null;
    try { const b = await r.text(); podatki = b ? JSON.parse(b) : null; } catch (_) {}
    return { status: r.status, podatki };
  }
  Object.defineProperty(window, '__safeerSpotify', { configurable: false, writable: false, value: Object.freeze({
    nastavi(z) { if (typeof z === 'string' && /^[A-Za-z0-9._~+\\/=-]{20,4096}$/.test(z)) zeton = z; },
    imaZeton() { return Boolean(zeton); },
    vzorci() { return Object.keys(vzorci); },
    // Spletni API (https://api.spotify.com/v1/...), samo ta gostitelj.
    klic(pot, metoda, telo) {
      pot = String(pot || '').replace(/^\\/+/, '');
      if (!/^[A-Za-z0-9_\\/?&=%.,:-]{1,600}$/.test(pot) || pot.includes('..')) return Promise.resolve({ status: 0, napaka: 'pot' });
      return poslji('https://api.spotify.com/v1/' + pot, metoda || 'GET', telo, { 'content-type': 'application/json' });
    },
    // Isti klic GraphQL kot spletna aplikacija (pathfinder): vzorec (hash in spremenljivke) je stran ze poslala sama.
    pf(ime, zamenjave) {
      const v = vzorci[String(ime || '')];
      if (!v) return Promise.resolve({ status: 0, napaka: 'ni_vzorca' });
      const sprem = Object.assign({}, v.spremenljivke, zamenjave || {});
      return poslji('https://api-partner.spotify.com/pathfinder/v2/query', 'POST',
        { variables: sprem, operationName: ime, extensions: { persistedQuery: { version: 1, sha256Hash: v.hash } } },
        { 'content-type': 'application/json;charset=UTF-8' });
    },
    mediji() { return Array.from(mediji); },
    utisaj(da) { utisano = Boolean(da); mediji.forEach(m => { try { m.muted = utisano; } catch (_) {} }); return utisano; },
    jeUtisano() { return utisano; }
  }) });
})();`;

// Scit, v strani (samo z vklopljenim Scitom): oglas v predvajalniku takoj utisa, brez cakanja na strazo Safeer OS
// (ta je prvi oglas zaznala sele po 7 s - preizkus 17. 10. 2026). Oglas se predvaja do konca (ne blokiramo ga, ne
// nadomescamo in ne pospesujemo: sicer predvajalnik obstane in glasba po oglasu ne steche - preizkus 18. 10. 2026).
// Pesmi se ne dotakne: po oglasu glasnost vrne. Oglas prepozna po istih oznakah kot STANJE_JS.
const SPOTIFY_SCIT = `(() => {
  if (window.__safeerScit) return;
  window.__safeerScit = true;
  const OGLAS = /^(advertisement|ad|oglas|werbung|anzeige|anuncio|publicidad|publicité|annonce|pubblicità|annuncio)$/i;
  const OZNAKE = '[data-testid="context-item-info-ad-subtitle"], [data-testid="ad-type-label"], [data-testid="advertisement-label"],' +
    ' [data-testid="now-playing-bar"] a[href*="/ad/"], [data-testid="now-playing-widget"] a[href*="audio_ad"], [data-testid="now-playing-bar"] a[href*="audio_ad"]';
  let vOglasu = false;
  function jeOglas() {
    try {
      if (document.querySelector(OZNAKE)) return true;
      const md = navigator.mediaSession && navigator.mediaSession.metadata;
      return Boolean(md && OGLAS.test(String(md.title || '').trim()));
    } catch (_) { return false; }
  }
  function mediji() {
    const S = window.__safeerSpotify;
    const m = new Set(S ? S.mediji() : []);
    document.querySelectorAll('video,audio').forEach(x => m.add(x));
    return Array.from(m);
  }
  function korak() {
    const oglas = jeOglas();
    if (oglas) {
      if (!vOglasu && window.__safeerSpotify) window.__safeerSpotify.utisaj(true);
      vOglasu = true;
      mediji().forEach(m => { try { m.muted = true; } catch (_) {} });
    } else if (vOglasu) {
      vOglasu = false;
      if (window.__safeerSpotify) window.__safeerSpotify.utisaj(false);
    }
  }
  setInterval(korak, 200);          // okno ni duseno (backgroundThrottling: false): zaznava v 0,2 s
})();`;

const PREVERI_PREDVAJANJE = "(() => Array.from(document.querySelectorAll('video,audio')).some(m => !m.paused && !m.ended && m.readyState >= 2 && m.currentTime > 0))()";
const SAMODEJNI_ZAGON = `(() => {
  if (window.__safeerAutoplayInstalled) return true;
  window.__safeerAutoplayInstalled = true;
  const play = () => {
    document.querySelectorAll('video,audio').forEach(m => { try { m.muted = false; m.volume = 1.0; const p = m.play(); if (p) p.catch(() => {}); } catch (_) {} });
    const b = document.querySelector('[aria-label="Play"], [title="Play"], .vjs-big-play-button, .jw-icon-display, .plyr__control--overlaid, [data-plyr="play"], .play-button');
    if (b) { try { b.click(); } catch (_) {} }
  };
  const subtitlesOff = () => document.querySelectorAll('video').forEach(v => { try { Array.from(v.textTracks || []).forEach(t => { t.mode = 'disabled'; }); } catch (_) {} });
  const poke = () => {
    play();
    const media = Array.from(document.querySelectorAll('video,audio'));
    if (!media.some(m => !m.paused && m.readyState >= 2)) {
      const e = document.elementFromPoint(innerWidth / 2, innerHeight / 2);
      if (e) { try { e.click(); } catch (_) {} }
      setTimeout(play, 300);
    }
  };
  subtitlesOff(); setTimeout(subtitlesOff, 800); setTimeout(subtitlesOff, 2200);
  play(); setTimeout(play, 1200); setTimeout(play, 3000);
  setTimeout(poke, 4500); setTimeout(poke, 7000); setTimeout(poke, 9500);
  return true;
})();`;

let okno = null;
let predvajanjeZacelo = false;
let medijZaznan = false;
let napakHttp = 0;
let klikov = 0;
let okvirjevJavljenih = 0;
let casovnikKlika = null;

function zacniKlik() {
  if (!vdelan || storitev || klikov > 0 || casovnikKlika) return;
  // En pravi klik na sredino, če stran zavrne samodejni zagon (kot WebView2 predvajalnik).
  casovnikKlika = setTimeout(() => {
    if (predvajanjeZacelo || !okno) return;
    klikov++;
    const [w, h] = okno.getContentSize();
    const x = Math.max(1, Math.floor(w / 2)), y = Math.max(1, Math.floor(h / 2));
    try {
      okno.webContents.sendInputEvent({ type: 'mouseDown', x, y, button: 'left', clickCount: 1 });
      okno.webContents.sendInputEvent({ type: 'mouseUp', x, y, button: 'left', clickCount: 1 });
      zapisi('PLAY_CLICK', String(klikov));
    } catch (e) { zapisi('PLAY_CLICK_FAILED', e.name || 'Error'); }
  }, 2500);
}

function vsiOkvirji() { try { return okno.webContents.mainFrame.framesInSubtree; } catch (_) { return []; } }

async function preveriPredvajanje() {
  if (predvajanjeZacelo || !okno) return;
  for (const f of vsiOkvirji()) {
    try { if (await f.executeJavaScript(PREVERI_PREDVAJANJE) === true) { predvajanjeZacelo = true; zapisi('PLAYBACK_STARTED', varenGostitelj(prviUrl)); return; } } catch (_) {}
  }
}

let htmlCelozaslonsko = false;
function poslji_tipko(koda) {
  // Linux: vstavljeno okno X11 ne dobi tipkovnice (ni XEMBED), zato Safeer OS tipke posreduje sem.
  const wc = okno.webContents;
  if (koda === 'Escape' && htmlCelozaslonsko) { wc.executeJavaScript('document.exitFullscreen && document.exitFullscreen()').catch(() => {}); return; }
  wc.sendInputEvent({ type: 'keyDown', keyCode: koda });
  if (koda.length === 1 || koda === 'Space') wc.sendInputEvent({ type: 'char', keyCode: koda === 'Space' ? ' ' : koda });
  wc.sendInputEvent({ type: 'keyUp', keyCode: koda });
}

// CDP (Chrome DevTools Protocol) iz glavnega procesa: brez --remote-debugging-port, ki bi ga lahko uporabil vsak
// lokalni proces (in s tem prevzel prijavo v Spotify). Dovoljen je samo Runtime.evaluate v strani.
const NAJVEC_ODGOVORA = 4 * 1024 * 1024;
function prikljuciCdp() {
  if (!spotify || !okno) return Promise.resolve();
  const dbg = okno.webContents.debugger;
  if (dbg.isAttached()) return Promise.resolve();
  try { dbg.attach('1.3'); } catch (e) { zapisi('CDP_FAILED', String(e && e.message || e).slice(0, 120)); return Promise.resolve(); }
  dbg.on('detach', (_e, razlog) => zapisi('CDP_DETACHED', String(razlog || '').slice(0, 60)));
  // Skripta mora biti prijavljena, preden se nalozi prvi dokument (odpri caka na to obljubo).
  // Page.enable pred prvim dokumentom ne odgovori, brez njega pa skripta ne velja (izmerjeno 17. 10. 2026, Electron 44):
  // najprej prazen dokument, nato Page.enable in skripta, sele potem Spotify.
  const prijava = okno.loadURL('about:blank').catch(() => {})
    .then(() => dbg.sendCommand('Page.enable'))
    .then(() => dbg.sendCommand('Page.addScriptToEvaluateOnNewDocument', { source: SPOTIFY_ZACETEK }))
    .then(() => pravila ? dbg.sendCommand('Page.addScriptToEvaluateOnNewDocument', { source: SPOTIFY_SCIT }) : null)
    .then(() => uporabniskeSkripte.reduce((p, s) => p.then(() => dbg.sendCommand('Page.addScriptToEvaluateOnNewDocument',
      { source: '(() => { try {\n' + s.koda + '\n} catch (e) { /* skripta uporabnika */ } })();' })).catch(() => {}), Promise.resolve()))
    .then(() => zapisi('CDP_READY'), e => zapisi('CDP_FAILED', String(e && e.message || e).slice(0, 120)));
  return Promise.race([prijava, new Promise(r => setTimeout(r, 5000))]);
}
function izvediCdp(id, b64) {
  let zahteva;
  try { zahteva = JSON.parse(Buffer.from(b64, 'base64').toString('utf8')); } catch (_) { zapisi('CDP', JSON.stringify({ id, napaka: 'zahteva' })); return; }
  const izraz = zahteva && typeof zahteva.expression === 'string' ? zahteva.expression : '';
  const dbg = okno.webContents.debugger;
  if (!izraz || !dbg.isAttached()) { zapisi('CDP', JSON.stringify({ id, napaka: izraz ? 'cdp' : 'zahteva' })); return; }
  dbg.sendCommand('Runtime.evaluate', { expression: izraz, awaitPromise: true, returnByValue: true, userGesture: true,
    timeout: Math.min(Math.max(Number(zahteva.timeout) || 15000, 100), 60000) })
    .then(r => {
      if (r && r.exceptionDetails) {
        const opis = (r.exceptionDetails.exception && r.exceptionDetails.exception.description) || r.exceptionDetails.text || '';
        zapisi('CDP', JSON.stringify({ id, napaka: 'izjema', opis: String(opis).slice(0, 300) }));
        return;
      }
      let besedilo = JSON.stringify({ id, vrednost: r && r.result ? r.result.value : null });
      if (besedilo.length > NAJVEC_ODGOVORA) besedilo = JSON.stringify({ id, napaka: 'prevelik' });
      zapisi('CDP', besedilo);
    }, e => zapisi('CDP', JSON.stringify({ id, napaka: 'cdp', opis: String(e && e.message || e).slice(0, 200) })));
}

function obdelajUkaz() {
  if (!commandPath || !okno || !fs.existsSync(commandPath)) return;
  try {
    // Preimenovanje je atomarno: ukaz, ki ga Safeer OS pripne med branjem, ostane za naslednji krog.
    const branje = commandPath + '.r';
    fs.renameSync(commandPath, branje);
    const vsebina = fs.readFileSync(branje, 'utf8');
    fs.unlinkSync(branje);
    const zg = okno.webContents.navigationHistory;
    for (const vrstica of vsebina.split('\n')) {
      const surov = vrstica.trim();
      const ukaz = surov.toLowerCase();
      if (!ukaz) continue;
      if (ukaz === 'back' && zg.canGoBack()) zg.goBack();
      else if (ukaz === 'reload') okno.webContents.reload();
      else if (ukaz === 'exitfullscreen') okno.webContents.executeJavaScript('document.fullscreenElement && document.exitFullscreen()').catch(() => {});
      else if (ukaz.startsWith('key:') && /^key:[A-Za-z0-9 ]{1,12}$/.test(surov)) poslji_tipko(surov.slice(4));
      else if (spotify && ukaz === 'skrij') okno.hide();
      else if (spotify && ukaz === 'pokazi') { okno.show(); okno.focus(); }
      else if (spotify && /^cdp:[0-9]{1,12}:[A-Za-z0-9+\/=]{1,2000000}$/.test(surov)) { const d = surov.split(':'); izvediCdp(Number(d[1]), d[2]); }
    }
  } catch (_) {}
}

function nastaviSejo(ses) {
  const dovoljeno = new Set(['mediaKeySystem', 'protectedMediaIdentifier', 'fullscreen']);
  ses.setPermissionRequestHandler((_wc, p, cb) => { const ok = dovoljeno.has(p); if (!ok) zapisi('PERMISSION_BLOCKED', p); cb(ok); });
  ses.setPermissionCheckHandler((_wc, p) => dovoljeno.has(p));
  ses.on('will-download', (e) => { e.preventDefault(); zapisi('DOWNLOAD_BLOCKED'); });
  ses.webRequest.onBeforeRequest((d, cb) => {
    const h = zaprtGostitelj(d.url);
    if (h) { zapisi('AD_OR_THREAT_RESOURCE_BLOCKED', h); cb({ cancel: true }); }
    else cb({});
  });
  if (spotify) {
    // Zeton, ki ga stran sama poslje (tudi iz delavca), da zaprtju v strani; samo v pomnilniku, nikoli v datoteko.
    let zadnji = '';
    ses.webRequest.onBeforeSendHeaders({ urls: ['https://*.spotify.com/*'] }, (d, cb) => {
      try {
        const k = Object.keys(d.requestHeaders || {}).find(x => x.toLowerCase() === 'authorization');
        const m = k ? /^Bearer\s+(\S+)$/i.exec(String(d.requestHeaders[k])) : null;
        if (m && m[1] !== zadnji && okno) {
          zadnji = m[1];
          okno.webContents.executeJavaScript('window.__safeerSpotify && window.__safeerSpotify.nastavi(' + JSON.stringify(zadnji) + ')').catch(() => {});
        }
      } catch (_) {}
      cb({ requestHeaders: d.requestHeaders });
    });
  }
  ses.webRequest.onCompleted((d) => {
    const status = d.statusCode || 0;
    const glave = d.responseHeaders || {};
    const kljuc = Object.keys(glave).find(k => k.toLowerCase() === 'content-type');
    const tip = kljuc ? String(glave[kljuc][0] || '').toLowerCase() : '';
    if (status >= 400 && napakHttp < 30) { napakHttp++; zapisi('HTTP_ERROR', `${varenGostitelj(d.url)} status=${status} type=${tip}`); }
    if (medijZaznan || status < 200 || status >= 300) return;
    let pot = ''; try { pot = new URL(d.url).pathname.toLowerCase(); } catch (_) {}
    const medijPot = ['.m3u8', '.mpd', '.m4s', '.ts', '.mp4', '.webm'].some(k => pot.endsWith(k));
    const medijTip = tip.startsWith('video/') || tip.startsWith('audio/') || tip.includes('mpegurl') || tip.includes('dash+xml');
    if (d.resourceType === 'media' || medijPot || medijTip) { medijZaznan = true; zapisi('MEDIA_RESPONSE', varenGostitelj(d.url)); }
  });
}

function nastaviPiskotke() {
  const pot = argumenti.cookies || '';
  if (!pot) return Promise.resolve();
  let seznam = [];
  try { seznam = JSON.parse(fs.readFileSync(pot, 'utf8')); } catch (_) {}
  try { fs.unlinkSync(pot); } catch (_) {}
  return Promise.all((Array.isArray(seznam) ? seznam : []).filter(c => c && /(^|\.)spotify\.com$/.test(String(c.domain || '').replace(/^\./, '')))
    .map(c => session.defaultSession.cookies.set({ url: 'https://' + String(c.domain).replace(/^\./, '') + (c.path || '/'),
      name: String(c.name), value: String(c.value), domain: c.domain, path: c.path || '/', secure: c.secure !== false,
      httpOnly: Boolean(c.httpOnly), expirationDate: c.expirationDate || undefined }).catch(() => {})))
    .then(() => zapisi('COOKIES_SET', String(seznam.length)));
}

function odpri(url) {
  okno = new BrowserWindow({
    width: 1280, height: 720, backgroundColor: '#000000', autoHideMenuBar: true, title: 'Safeer',
    // Vdelan: brez okvirja, brez gumba v opravilni vrstici, zunaj zaslona, dokler ga Safeer OS ne vstavi v svoje okno.
    frame: !vdelan, skipTaskbar: vdelan, x: vdelan ? -32000 : undefined, y: vdelan ? -32000 : undefined,
    show: !vdelan && !skrit, focusable: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true, backgroundThrottling: false }
  });
  okno.setMenu(null);
  if (vdelan) {
    const rocaj = okno.getNativeWindowHandle();
    const stevilka = rocaj.length >= 8 ? rocaj.readBigUInt64LE(0) : BigInt(rocaj.readUInt32LE(0));
    zapisi('WINDOW_HANDLE', stevilka.toString());
    okno.showInactive();
  }
  const wc = okno.webContents;
  wc.setWindowOpenHandler(({ url: cilj }) => {
    // Prijava prek drugega ponudnika (Google, Apple, Facebook) pri storitvi: pravo pojavno okno z window.opener,
    // kot v brskalniku - prej se je stran nalozila namesto storitve in prijava se ni mogla vrniti (17. 10. 2026).
    let gost = ''; try { gost = new URL(cilj).hostname; } catch (_) {}
    if (storitev && cilj.startsWith('https:') && /(^|\.)(accounts\.google\.com|appleid\.apple\.com|facebook\.com)$/.test(gost)) {
      zapisi('POPUP_LOGIN', varenGostitelj(cilj));
      return { action: 'allow', overrideBrowserWindowOptions: { width: 520, height: 720, autoHideMenuBar: true, title: 'Safeer',
        parent: okno, modal: false, webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true } } };
    }
    // Storitev: drugo novo okno odpremo v istem predvajalniku; drugje pojavna okna zapremo.
    if (storitev && cilj.startsWith('https:')) { wc.loadURL(cilj); zapisi('POPUP_IN_PLACE', varenGostitelj(cilj)); }
    else zapisi('POPUP_BLOCKED');
    return { action: 'deny' };
  });
  const zacetnaDomena = osnovnaDomena(varenGostitelj(url));
  wc.on('will-navigate', (e, cilj) => {
    let u = null; try { u = new URL(cilj); } catch (_) {}
    zapisi('NAVIGATION_START', `${varenGostitelj(cilj)} redirected=False`);
    if (vdelan && !storitev && (!u || u.protocol !== 'https:' || osnovnaDomena(u.hostname) !== zacetnaDomena)) { e.preventDefault(); zapisi('NAVIGATION_BLOCKED', varenGostitelj(cilj)); }
    else if (!u || u.protocol !== 'https:') e.preventDefault();
  });
  wc.on('certificate-error', (e, cilj, _err, _cert, cb) => { e.preventDefault(); cb(false); zapisi('CERTIFICATE_BLOCKED', varenGostitelj(cilj)); });
  wc.on('render-process-gone', (_e, d) => zapisi('PROCESS_FAILED', d.reason));
  wc.on('did-frame-finish-load', (_e, glavni, procId, routingId) => {
    if (!storitev) { try { const f = webFrameMain.fromId(procId, routingId); if (f) f.executeJavaScript(SAMODEJNI_ZAGON).catch(() => {}); } catch (_) {} }
    if (!glavni && okvirjevJavljenih < 5) { okvirjevJavljenih++; zapisi('FRAME_READY'); }
    zacniKlik();
  });
  // Scit: oglasne pasice in ponudbe Premium skrije CSS iz pravil (vsak nov dokument znova).
  wc.on('dom-ready', () => { if (pravila && typeof pravila.css === 'string' && pravila.css) wc.insertCSS(pravila.css).catch(() => {}); });
  wc.on('did-finish-load', () => {
    zapisi('NAVIGATION_OK', 'Success');
    // Samo za preizkus paketa (CI, Flatpak s zypakom): ali stran dobi Widevine (CDM nalozen v peskovniku).
    // Safeer OS in Safeer Browser te spremenljivke nikoli ne nastavita.
    if (process.env.SAFEER_DRM_EME_PREIZKUS === '1') {
      wc.executeJavaScript(`navigator.requestMediaKeySystemAccess('com.widevine.alpha', [{initDataTypes: ['cenc'],
        videoCapabilities: [{contentType: 'video/mp4; codecs="avc1.42E01E"', robustness: 'SW_SECURE_CRYPTO'}]}])
        .then(a => a.createMediaKeys()).then(() => 'ok', e => 'napaka ' + (e && e.name) + ' ' + (e && e.message))`)
        .then(r => zapisi('EME', String(r).slice(0, 200)), e => zapisi('EME', 'napaka ' + String(e).slice(0, 200)));
    }
  });
  wc.on('did-fail-load', (_e, koda, opis, _u, glavni) => { if (glavni && koda !== -3) zapisi('NAVIGATION_FAILED', opis); });
  wc.on('enter-html-full-screen', () => { htmlCelozaslonsko = true; zapisi('FULLSCREEN_ON'); });
  wc.on('leave-html-full-screen', () => { htmlCelozaslonsko = false; zapisi('FULLSCREEN_OFF'); });
  wc.on('before-input-event', (e, i) => {
    if (i.type !== 'keyDown') return;
    if (!vdelan && i.key === 'F11') { okno.setFullScreen(!okno.isFullScreen()); e.preventDefault(); }
    // Esc zapre celozaslonski video (kot v Chromu); Electron tega sam ne naredi.
    else if (i.key === 'Escape' && htmlCelozaslonsko) { wc.executeJavaScript('document.exitFullscreen && document.exitFullscreen()').catch(() => {}); e.preventDefault(); }
    else if (!vdelan && i.key === 'Escape' && okno.isFullScreen()) okno.setFullScreen(false);
  });
  okno.on('closed', () => { okno = null; app.quit(); });
  // Prijava iz Spleta (Spotify): piskotke prenesemo v sejo pred prvim nalaganjem, datoteko takoj izbrisemo.
  Promise.all([prikljuciCdp(), nastaviPiskotke()]).then(() => { if (okno) okno.loadURL(url); });
  zapisi('SESSION_READY', varenGostitelj(url));
  if (nadzor) setInterval(obdelajUkaz, 100);
  if (vdelan) setInterval(preveriPredvajanje, 750);
  // Ce se Safeer OS konca (tudi sesutje), se konca tudi predvajalnik - ne sme ostati nevidno teci.
  const lastnik = parseInt(argumenti.lastnik || '', 10);
  if (lastnik > 1) setInterval(() => { try { process.kill(lastnik, 0); } catch (_) { app.exit(0); } }, 2000);
}

if (prviUrl) {
  app.whenReady().then(async () => {
    nastaviSejo(session.defaultSession);
    try {
      // Prvi zagon prenese Widevine (nekaj sekund); brez omrezja do Googla ne cakamo v nedogled.
      await Promise.race([components.whenReady(), new Promise((_, ne) => setTimeout(() => ne(new Error('Widevine ni pripravljen v 15 s')), 15000))]);
      const s = components.status();
      const wv = Object.values(s).find(c => /widevine/i.test(c.title || '')) || {};
      zapisi('DRM_READY', `widevine ${wv.version || '?'} ${wv.status || ''}`.trim());
    } catch (e) {
      // Brez Widevine se odprta stran vseeno naloži (video brez DRM dela naprej).
      zapisi('DRM_FAILED', String(e && e.message || e).slice(0, 200));
    }
    odpri(prviUrl);
  }).catch(e => { zapisi('START_FAILED', String(e && e.message || e).slice(0, 200)); app.exit(3); });
  app.on('window-all-closed', () => app.quit());
  // Izhod z ukazom CDP na poti je Chromium koncal s SIGTRAP (izmerjeno 17. 10. 2026): razhroscevalnik prej odklopimo.
  app.on('before-quit', () => { try { if (okno && okno.webContents.debugger.isAttached()) okno.webContents.debugger.detach(); } catch (_) {} });
}
