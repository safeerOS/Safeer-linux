# Namizje Safeer = vse iz aplikacije Safeer OS (popis, 18. 10. 2026)

Cilj 3.1 (lastnik): kdor uporablja namizno okolje Safeer, aplikacije Safeer OS ne potrebuje vec. Aplikacija ostane za
tiste, ki imajo Mintovo ali drugo namizje.

Kaj je »aplikacija Safeer OS« v tem popisu: staro glavno okno `assets/os/index.html` + `os.js` s stransko vrstico
(Domov, Medijski center, Safeer Link, Sporocila, Programi, Datoteke, Splet, Zapiski, Nastavitve; podstrani Omrezje,
Zvok, Scit; sloji Hitre nastavitve, Napajanje, Dodaj spletno aplikacijo). Namizje je `assets/os/qml/Namizje.qml`
(+ `Datoteke.qml`, `Programi.qml`, …) in samostojni programi istega procesa, ki jih namizje odpre: okna razdelkov
`index.html?razdelek=zapiski|sporocila|nastavitve|scit` (vsak ima svoj vnos v meniju, `packaging/safeer-os-*.desktop`),
Safeer Player (Medijski center), Splet na namizju in okno Safeer Link (Control). Pravilo: z namizja se staro glavno
okno ne sme odpreti nikoli (`safeer_os._odpri_razdelek`).

Ocena dela: S = do pol dneva, M = dan, L = vec dni.

| Del aplikacije | Kaj namizje (QML) ze ima - kje | Kaj je manjkalo | Ocena | Stanje |
|---|---|---|---|---|
| Domov: iskanje | Lupa z istimi viri in ucenjem: `Namizje.qml` (Steklo `iskanje`, `zadetki`), iskanje z glasom | Osebe in pogovori Sporocil (ime, naslov, zadeva, zadnje sporocilo) - iskanje aplikacije jih najde, namizje ne | S | dodano |
| Vodnik ob prvem zagonu (jezik, racuni, Scit, Link) | Gumb v oknu Nastavitve | Nova namestitev z namizjem Safeer vodnika ni pokazala (samo staro glavno okno); gumb Nazaj na prvem koraku je vodnik pokvaril | S | dodano |
| Domov: velike ploscice (Brskalnik, Mediji, Datoteke, Naprave) | Iskanje → Splet na namizju, plosca Medijski center, plosca Datoteke, gumb Safeer Link | - | - | ima |
| Domov: nedavno uporabljeni programi | `Programi.qml` razvrscanje »Nazadnje« / »Najveckrat«, priljubljeni | - | - | ima |
| Domov: spletne aplikacije (ploscice + »Dodaj«) | `Programi.qml` kaze shranjene spletne aplikacije | Dodajanje in odstranjevanje spletne aplikacije; privzete (YouTube, RTV 365, Gmail, Wikipedia) se na namizju niso pokazale, dokler jih uporabnik ni shranil v aplikaciji | M | dodano |
| Domov: opomba »Na voljo je posodobitev« | Dogodek `posodobitev` je prisel tudi v QML, a ga namizje ni pokazalo | Opomba na namizju z gumbom do Posodobitev | S | dodano |
| Domov: odprta okna, nedavne datoteke, sistem (omrezje, baterija), ura, napajanje, hitre nastavitve | Pult Linux Minta in dock Plank (namizno okolje), `Datoteke.qml` vir »Nedavno« | - | - | ima (pult, Datoteke) |
| Medijski center: ves razdelek | »Odpri Medijski center« → Safeer Player (`_odpri_predvajalnik`), iskanje »Poisci v Medijskem centru« | - | - | ima |
| Medijski center: vrstica »Predvaja se« | Pripomocek `medijski` v `Namizje.qml`: naslov, ovitek, prejsnja/premor/naslednja, napredek (samo prikaz), »Predvajaj na …« | Premik po posnetku (drsnik, tipke), cas/trajanje, Ustavi, glasnost in utisaj, cakalna vrsta, odprtje videa | M | dodano |
| Safeer Link (Naprave) | Gumb Link pod iskanjem (stevilo naprav, prijava), datoteke in programi naprav v Datotekah/Programih, »Prikazi na …«, okno Safeer Link (zaupanje, predaja, odjava, preimenovanje, upravljanje racunalnika) | - | - | ima (okno Safeer Link) |
| Sporocila | Okno Sporocila (meni, iskanje »sporocila«), kuverta v pultu s plosco | Na samem namizju ni bilo videti, da so nova sporocila, in ni bilo vstopa brez iskanja | S | dodano |
| Programi | `Programi.qml`: kategorije, naprave, ponudniki, GitHub, igre v oblaku, dock, priljubljeni | Razdelek »programi« (iz drugih oken) je odprl staro glavno okno | S | dodano (usmeritev) |
| Datoteke | `Datoteke.qml` (bogatejse od aplikacije: Najvecje, Koš, pogoni, naprave, pretvorba …) | Razdelek »datoteke« (iz drugih oken) je odprl staro glavno okno | S | dodano (usmeritev) |
| Splet | Iskanje → Splet na namizju (`spletNaNamizju`), okno Splet (`--razdelek splet`) | - | - | ima |
| Zapiski | Okno Zapiski (meni), zapiski v iskanju | - | - | ima (okno Zapiski) |
| Nastavitve | Okno Nastavitve (meni namizja »Tema sistema«, gumb ⚙ v oknu aplikacije, meni sistema) | - | - | ima (okno Nastavitve) |
| Nastavitve → Omrezje (Wi-Fi, internet prek telefona) | - | Ploscica »Omrezje« v oknu Nastavitve je odprla staro glavno okno Safeer OS | S | dodano |
| Nastavitve → Zvok (izhodi, zvok na napravi, JBL) | »Predvajaj na …« v pripomocku | Ploscica »Zvok« v oknu Nastavitve je odprla staro glavno okno Safeer OS | S | dodano |
| Scit | Svoj program (okno, meni), stanje in stevec v pultu (commit 38ae939) | - | - | ima |
| Prilagodi (ozadje, plosce, Sporocila vkl/izkl) | `Prilagodi.qml` | - | - | ima |

## Kaj je dodano v tej izdaji (Safeer 1.0.127 / Safeer OS 0.4.85)

1. Z namizja se staro glavno okno ne odpre vec: `_odpri_razdelek` usmeri vsak razdelek (omrezje in zvok v okno
   Nastavitve, datoteke in programi na plosce namizja); okno Nastavitve pokaze Omrezje in Zvok kot svoji podstrani.
2. Pripomocek Medijski center: drsnik polozaja (miska, puscici levo/desno po 10 s), cas, Ustavi, glasnost z utisajem,
   cakalna vrsta domacega predvajalnika (izbira skladbe), klik na ovitek odpre video.
3. Gumb Sporocila pod iskanjem s stevilom neprebranih (isto stevilo kot kuverta v pultu); klik odpre Sporocila.
4. Opomba o posodobitvi na namizju; klik odpre Nastavitve pri Posodobitvah.
5. Spletne aplikacije v Programih: »Dodaj spletno aplikacijo« in »Odstrani« (z »Razveljavi«) v meniju; isti seznam kot
   v aplikaciji (privzete, dokler uporabnik ne shrani svojih).
6. Iskanje na namizju najde osebe in pogovore Sporocil; Enter ali klik odpre okno Sporocila pri tem pogovoru.
7. Vodnik ob prvem zagonu: namizje ga ob novi namestitvi odpre v oknu Nastavitve; gumb Nazaj na prvem koraku in
   Preskoci na zadnjem sta skrita (prej sta bila vidna, Nazaj je vodnik pokvaril).

## Preizkusi

- `tests/test_namizje_vse_iz_os.py` - usmeritve razdelkov, spletne aplikacije, namizje QML (offscreen): Medijski center,
  Sporocila, posodobitev, iskanje sporocil, vodnik.
- `tests/test_namizje_nastavitve_zivo.py` - prava stran okna Nastavitve v WebKitGTK 6.0: Omrezje in Zvok v istem oknu,
  vodnik, sidro Posodobitev (s staro os.js preizkus pade).

## Odlocitve za lastnika (izbrano po udobju uporabnika, lahko se spremeni)

| Kaj | Izbrano | Zakaj |
|---|---|---|
| Premik po posnetku s tipkovnico | 10 s na pritisk puscice | Kot v vecini predvajalnikov; miska skoci kamorkoli. |
| Korak glasnosti s tipkovnico | 5 % | 20 pritiskov od tisine do polne glasnosti. |
| Znacka neprebranih | do 99, nato »99+« | Gumb ostane majhen in berljiv. |
| Gumb Sporocila | viden vedno, ko so Sporocila vklopljena (tudi pri 0) | Stalen vstop brez iskanja; izklop v Prilagodi namizje skrije gumb. |
| Klik na gumb Sporocila | okno Sporocila (ne plosca kuverte) | Z namizja uporabnik pricakuje cel nabiralnik; kuverta v pultu ostane hitri pogled. |
| Osvezitev stevila brez ikone v pultu | 60 s (z ikono takoj ob spremembi); prvo 3 s po izrisu | Kanali Sporocil se nalozijo, ko je namizje mirno. |
| Iskanje po Sporocilih | seznam pogovorov najvec na 30 s (in po novem sporocilu), do 4 zadetki | Brez branja baze ob vsaki crki. |
| Enter pri imenu osebe | odpre pogovor (za programom, pred razdelki Safeer OS) | Isti vrstni red kot namera iskanja v aplikaciji. |
| Privzete spletne aplikacije na namizju | YouTube, RTV 365, Gmail, Wikipedia (kot Domov aplikacije), dokler uporabnik ne shrani svojih | En seznam za aplikacijo in namizje; vsako se odstrani z »Razveljavi«. |
| Ozka plosca Medijski center | pod 470 px gumb »Odpri Medijski center« postane ikona | Naslov ostane berljiv v oknu 960 px. |
| Vodnik ob prvem zagonu na namizju | odpre okno Nastavitve z vodnikom; po koncu okno ostane odprto | Uporabnik vidi, kje vodnik najde znova. |
