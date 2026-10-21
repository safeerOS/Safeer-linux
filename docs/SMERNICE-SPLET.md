# Smernice za razvoj Spleta (WebKitGTK) - za vse agente

Velja za Splet (core/os_splet.py), Safeer Browser za Linux (safeer_brskalnik.py) in vse, kar uporablja nas WebKit.
Lastnik, 21. 10. 2026: »Smernice za razvoj spleta, ki bodo primerne za nas WebKit, naj bodo na voljo vsem agentom.«
Kar je tu oznaceno kot IZMERJENO, je bilo izmerjeno na testnem PC (i5-4590, 11,6 GB, Intel HD 4600) z naso gradnjo
WebKitGTK 2.54.1 (packaging/webkit/webkitgtk6-safeer.yml). Pred trditvijo o drugi razlicici izmeri znova.

## 1. Cilj
- Zgled so moderni brskalniki: omogocimo vse, kar drugi, ali bolje, in smo enako hitri. Strani nas prepoznajo kot
  Safari, zato smo vsaj tako dobri kot Safari (lastnik, 21. 10. 2026).
- Splet je motor Safeerja: brezhiben, hiter, varen. Izboljsava Spleta gre v vse brskalnike Safeer (AGENTS.md).
- Odlocamo z meritvijo (poglavje 3), ne po obcutku in ne po opisu drugega brskalnika.

## 2. Arhitektura, kakrsna je (IZMERJENO 21. 10. 2026)
- Vecprocesno: vsak zavihek ima svoj WebKitWebProcess; omrezje tece v locenem WebKitNetworkProcess (ne v glavnem).
- Peskovnik: vsak spletni proces v bubblewrap (2 bwrap) + xdg-dbus-proxy. Brez peskovnika samo, ce ga sistem ne
  dopusti (core/peskovnik_userns.py - uporabnik dobi opozorilo). Peskovnika nikoli ne izklapljaj za hitrost.
- Niti v spletnem procesu: ThreadedCompositor (vecnitno sestavljanje), »Core: Scrolling«, gonilnik GPU (Mesa).
  Strojno pospesevanje: ALWAYS (»on_demand« je v 2.4x opuscen), uporabnik ga lahko izklopi.
- Dodeljevalnik pomnilnika: bmalloc/libpas (analog PartitionAlloc); USE_SYSTEM_MALLOC ne vklapljaj.
- Izolacija napak: sesutje procesa zavihka -> nov proces po ~2 s, stran znova, ostali zavihki nedotaknjeni
  (web-process-terminated v core/os_splet.py). safeer://procesi kaze zavihke in procese.
- »En proces« (core/en_proces.py) velja za vmesnik Safeer (Python), ne za spletne strani.
- Android (telefon, tablica, TV): sistemski Android WebView (Chromium) - vecprocesen s peskovnikom tudi na TV; tehnike
  Chromiuma (V8, PartitionAlloc, site isolation po RAM) ima sam. Nas del: stevilo pogledov, uspavanje, mostovi.

## 3. Merjenje (obvezno pred trditvijo »hitreje« ali »manj RAM«)
- Pomnilnik: PSS in zasebni pomnilnik (/proc/PID/smaps_rollup), NE RSS - RSS steje skupne knjiznice v vsakem
  procesu (21. 10.: 18 procesov RSS 2,68 GB, PSS 1,22 GB; vnaprej pripravljen proces RSS 59 MB, PSS 11 MB).
- Hitrost: Speedometer 3.1 in MotionMark v VIDNEM oknu (skrito okno: rAF 0/s), izmenicno A/B istega dne, enako
  stevilo procesov, vsaj 3 ponovitve (AGENTS.md, pravila 1.0.127).
- Po vsakem preizkusu: Splet zapri, procese prestej in preveri, da ne ostanejo (lastnik: stari vmesniki ne smejo
  zasedati pomnilnika).

## 4. Funkcije WebKita (WebKit.Settings.get_all_features / set_feature_enabled, WebKitGTK 2.42+)
- Privzeto vklapljamo samo status »stable« ali »mature«. »testable«, »unstable«, »internal«, »embedder« samo z virom,
  meritvijo A/B, neodvisnim pregledom in za zastavico (profil ali nastavitev), nikoli na slepo.
- Seznam funkcij izpisi na napravi (2.54.1 ima 538). Pomembne (21. 10. 2026, status / privzeto):
  UseGPUProcessForDOMRendering stable/izkl. (kandidat za polni profil, A/B); UsesSingleWebProcess embedder/izkl.
  (kandidat za sibke naprave - oslabi izolacijo napak, presodi); HTTPSByDefault testable/izkl. (samodejni https;
  primerjaj z core/https_nadgradnja.py); SiteIsolation unstable/izkl. (se ne); ProcessSwapOnCrossSiteNavigation
  stable/vkl.; PageVisibilityBasedProcessSuppression internal/vkl. (zamrzovanje skritih strani); UpgradeKnownHostsToHTTPS
  internal/vkl.; MultiProcessBackForwardCache testable/izkl.

## 5. Profil po zmogljivosti naprave (lastnik, 21. 10. 2026)
- Vec RAM (racunalniki, telefoni z veliko RAM): polno - vecprocesno s peskovnikom, vec niti, GPU, vecji predpomnilnik.
- Malo RAM (TV, sibke naprave): varcno - enoprocesni modul aplikacije, brez predpomnilnika procesov, najvec en
  vnaprej pripravljen proces, prej uspavanje zavihkov.
- En vir resnice v core/ (profil naprave iz MemTotal in jeder); Splet in Safeer Browser ga bereta, ne racunata sama.

## 6. Pomnilnik in zavihki
- Zaprtje okna Spleta mora uniciti vse njegove poglede (in s tem procese). 21. 10. so po zaprtju ostali procesi
  zavihkov - to je napaka, ne predpomnilnik.
- Vsak WebContext/NetworkSession ima svoje procese: ne ustvarjaj novega konteksta brez razloga (lupa, predogledi,
  vdelane aplikacije naj delijo, kjer zasebnost dopusti).
- Uspavanje zavihkov (core/splet_spanje.py) nikoli ne uspava zavihka z zvokom, videom, obrazcem, prenosom, kamero,
  mikrofonom ali deljenjem zaslona. Meje po profilu in po tlaku pomnilnika.
- Zdruzevanje procesov (WebKitWebView »related-view«) samo za isto registrirano domeno; strani s prijavo ostanejo locene.

## 7. Varnost (dopolnjuje AGENTS.md)
- Mostovi: locen svet ali zeton (AGENTS.md). Omreznega procesa nikoli ne koncaj od zunaj.
- Naslovna vrstica: eno pravilo - core/config.py (je_spletni_naslov, naslov_ali_iskanje) = ui/splet.js (preizkus
  primerja odlocitev in koncni naslov). Brez sheme https; http samo localhost in zasebni/loopback/link-local IP;
  zeton nikoli k iskalniku; »0.0.0.0«, uporabniski del, ne-spletne sheme -> iskanje.
- Http -> https s povratkom (kot Safari/Chrome): samo GET glavnega okvirja, lokalni naslovi brez poskusa.
  Strani, ki https ne podpirajo, si zapomnimo trajno (z rokom) in jih naslednjic odpremo takoj na http - casa ne
  izgubljamo (lastnik, 21. 10. 2026); napaka TLS ali zavrnjena povezava = takojsen povratek, brez opozorilne strani.
  Pred nevarnimi stranmi scit Safeer Scit (DNS), ne opozorilo o http: Scit je PRIVZETI razresevalnik imen
  (core/config.py doh_provider="scit"), zato se ime nevarne strani zavrne, se preden se odpre katerakoli povezava
  http ali https (lastnik, 21. 10. 2026).
- Samodejna ponovitev nalaganja samo GET glavnega okvirja (core/network_errors.py).

## 8. Orodja za razvijalce
- WebDriver (WebKitWebDriver, kot safaridriver) in Safeer Browser --automation: avtomatizacija samo z zastavico.
- Web Inspector: nastavitev »Orodja za razvijalce«, privzeto izklopljena (kot Safari), Ctrl+Shift+I / F12.

## 9. Tehnike drugih brskalnikov -> nas WebKit
| Chromium | WebKit / Splet |
|---|---|
| Stiskanje kazalcev V8 | JSC tega ne ponuja kot stikalo gradnje - ne obljubljaj; raziskava z viri |
| PartitionAlloc | bmalloc/libpas - ze vklopljen |
| Site Isolation | SiteIsolation unstable - se ne; zdruzevanje po domeni z related-view |
| GPU/utility v nitih na sibkih napravah | UseGPUProcessForDOMRendering samo na polnem profilu po A/B |
| Freezing / Memory Saver | PageVisibilityBasedProcessSuppression + core/splet_spanje.py |
| Zygote / CoW | skupne knjiznice ze deli sistem (mmap); vnaprej pripravljen proces 11 MB PSS |

## 10. Preden odpres nalogo
- Preberi AGENTS.md in zapisnik (SAFEER-ZNANJE.md, ZAPISNIK) - ne ponavljaj poskusov, ki niso delovali.
- Vsaka sprememba: preizkus, ki brez popravka pade; neodvisni pregled; zivi preizkus po uporabnikovi poti.

## 11. Zgodovina WebKita in nauki (lastnik 21. 10. 2026: »poglej, kaj so se razvijalci iz napak naucili, da jih ne ponavljamo«)
Dejstva (viri v zapisniku SAFEER-ZNANJE.md, 21. 10. 2026 10:05):
- Chrome je do 2013 uporabljal WebKit. Aprila 2013 je Google naredil fork Blink: Chromov vecprocesni model se je
  razlikoval od WebKitovega, kar je oba zapletalo; v prvem koraku so izbrisali 7 sistemov gradnje in >7000 datotek
  (>4,5 milijona vrstic). Apple WebKita NI zapustil - ga vodi naprej (Safari); ob njem Igalia (WebKitGTK, WPE),
  Sony (PlayStation, Windows) in Red Hat (GNOME).
- WebKit je vecprocesnost (WebKit2) uredil v motorju; WebKitGTK je danes samo vecprocesen s peskovnikom.
- Igalia je 2024 za WebKitGTK/WPE zamenjala Cairo s Skio (Googlova knjiznica, kot ANGLE v drevesu WebKita): lastna
  knjiznica ni dosegla hitrosti in kakovosti; najprej prototip in meritev, en port najprej, brez regresij, zgodaj gorvodno.
- Chromium: ~70 % resnih varnostnih napak je napak pomnilnika, polovica use-after-free; odgovor je peskovnik, izolacija
  strani (po Spectre 2018), »pravilo dveh« (nezaupljiv vnos ne v privilegiranem procesu), varnejsi jeziki, hitre posodobitve.
- Site Isolation v WebKitu (julij 2025) dela samo na Applovih platformah; GTK nima - zato je pri nas »unstable«.
Nauki za Safeer (obvezno):
1. Ne forkaj WebKita. Nasi popravki (packaging/webkit/*.patch, libsoup) so cim manjsi in gredo gorvodno; ob vsaki novi
   razlicici WebKitGTK preveri, kateri so ze sprejeti, in jih odstrani.
2. Varnostne izdaje WebKitGTK (WSA) gredo v nas paket v nekaj dneh - zaostanek za stabilno razlicico je najvecje
   tveganje (21. 10. 2026: imamo 2.54.1 = najnovejsa stabilna). Enako za vgrajene knjiznice (ICU, libxml2, libjpeg, JPEG XL).
3. Arhitektura je v motorju: procesov ne upravljamo mimo WebKita (CacheModel, process swap, terminate_web_process po
   pravilih WebKita) - lastni »popravki« ob strani so ze povzrocili ostale procese (naloga 27).
4. Peskovnik vedno; nezaupljiva vsebina (strani, zadetki iskalnikov) se razclenjuje samo v spletnem procesu (locen svet),
   nikoli v procesu vmesnika Safeer (pravilo dveh).
5. Kar vzdrzujejo drugi in je dobro, uporabimo (Skia, ANGLE, GStreamer), namesto da pisemo svoje; najprej prototip in
   meritev, en port, brez regresij.
6. Funkcij, ki so v WebKitGTK »unstable« (SiteIsolation), ne vklapljamo - spremljamo webkit-dev in jih vzamemo, ko so stabilne.
