# Safeer Link Mesh (mesh1) — res decentralizirano

Stanje 29. 9. 2026. Veja `link-mesh` v Android-tv, Safeer-linux, Safeer-windows (in pozneje Mobile-android).

## Zakaj

Danes je zaupanje že decentralizirano (vsaka naprava hrani cel podpisan krog), nadzorna pot pa ne:
naprave izvolijo **en** hub (`IzvolitevHuba`), vse druge se umaknejo in se povežejo nanj. Če hub
ugasne, se Link za ~7–90 s podre, naprave se prerazporedijo, telefon in tablica pa izgubita
računalnik, ki je ves čas prižgan. Hub je ena točka odpovedi in ena točka, skozi katero gre vse.

## Pravilo mesh1

1. **Vsaka naprava je vozlišče.** Vsaka naprava s Safeer Linkom gosti svoj hub, vedno (brez
   izvolitve in brez umika). Njene aplikacije (Safeer OS, sprejemnik, Control) se prijavijo na
   **svoj** hub (lokalno).
2. **Vozlišča se povežejo neposredno, vsako z vsakim.** Hub A se poveže na hub B iz kroga zaupanja
   (mDNS oglas + ključ v potrdilu = ključ člana v krogu) z obstoječo prijavo s podpisom
   (`/cast/auth/challenge` → `/cast/auth/ticket` → WebSocket). Na eni strani je to navaden odjemalec
   z `role: "hub"` in zmožnostjo `mesh1`; od tu naprej je povezava simetrična (**sosednja povezava**).
   Klice obe strani; če nastaneta dve povezavi za isti par, ostane tista, ki jo je odprl manjši id.
3. **Sosedje si izmenjajo samo svoje lokalne naprave** (`mesh.devices`). Hub vsako napravo soseda
   vpiše v svoj register kot **oddaljeno napravo** z namestnikom povezave (proxy): pošiljanje nanjo
   se ovije v `mesh.route` in gre sosedu, ta ga dostavi svoji lokalni napravi. Vse obstoječe
   usmerjanje (`cast.*`, `share.*`, `control.*`, `chat.*`, `data.*`, `internet.*`, `handoff.*`,
   oddaje brez cilja) zato deluje brez sprememb.
4. **Brez zank.** Sosed nikoli ne posreduje naprej (samo lokalnim napravam) in v `mesh.devices`
   nikoli ne navede oddaljenih naprav ali sosedov. Oddaja brez cilja doseže vsako napravo natanko
   enkrat: lokalne neposredno, oddaljene prek njihovega huba.
5. **Lokalna registracija ima prednost.** Če se naprava prijavi tudi neposredno (stari odjemalec),
   velja neposredna povezava; oddaljeni zapis istega id se prezre.
6. **Izpad vozlišča podre samo njegove naprave.** Ko sosednja povezava pade, hub odstrani vse
   njegove oddaljene naprave in objavi nov `cast.devices`. Drugi pari tečejo naprej.
7. **Naslov naprave zunaj njene naprave ni nikoli zanka** (5. 10. 2026). Aplikacija, ki se prijavi
   na hub svoje naprave, ima pri njem naslov `127.0.0.1`. Ta naslov velja samo na tisti napravi: kdor
   ga dobi drugje, se z njim poveže sam nase (telefon je namesto zaslona računalnika klical svoja
   vrata). Zato:
   - **sosedom** (`mesh.devices`, izvoz): hub namesto zanke zapiše svoj naslov na poti do tistega
     soseda (vsakemu sosedu svojega – krajevni konec sosednje povezave);
   - **od sosedov** (uvoz): zanko ali prazen `ip` sosedove naprave hub zamenja z naslovom, na
     katerem teče sosedov hub (drugi konec sosednje povezave);
   - **svojim odjemalcem** (`cast.devices`): odjemalec z iste naprave dobi zanko (po njej prepozna
     procese svoje naprave); odjemalec od drugod – vmesnik telefona je lahko pripet na hub druge
     naprave – dobi naslov huba na poti do njega. Polje `here: true` pove, da je naprava na napravi
     huba, ne glede na to, kateri naslov je odjemalec dobil (po njem odjemalec ve, kako je hubu ime);
   - **odjemalec** zanko od huba, ki teče drugje, bere kot naslov tistega huba – tako dela tudi s
     starejšim hubom.
   Dovolj je, da pravilo upošteva ena stran – starejše različice pošiljajo `127.0.0.1`. Prek releja
   (Global Link) naslova ni: `ip` je prazen in odjemalec neposredne povezave (slika zaslona) ne
   poskuša, temveč pove, da ta deluje samo v istem omrežju. Naprava, ki je pri hubu prijavljena iz
   omrežja, obdrži svoj naslov.
8. **Naprava, ki ponuja neposredno povezavo, svoje naslove našteje sama** (5. 10. 2026). Naslov v
   seznamu naprav pripiše hub; napravi, ki jo vidi samo posredno, ga lahko pripiše narobe (pravilo 7
   je nastalo po taki napaki). Računalnik zato v odgovoru na `screen.start` poleg `port`, `fp` in
   `token` vrne `hosts` – svoje naslove IPv4, najverjetnejši najprej, največ štiri, brez zanke
   (isti seznam kot v `audio.play`):
   - naslov na poti do huba, kadar hub teče drugje;
   - naslovi vmesnikov krajevnega omrežja, tisti na privzeti poti prvi (vmesniki vsebnikov in
     navideznih strojev ne štejejo);
   - naslov na privzeti poti in naslovi predorov (VPN) nazadnje – računalnik, ki ves promet pošilja
     skozi VPN, bi sicer napravi v istem omrežju povedal samo naslov predora.

   Gledalec poskusi **najprej naslov iz seznama naprav, nato naštete**: vsakega enkrat, skupaj
   največ štiri, vsakega največ 4 s, kadar jih je več (računalnik čaka 30 s). Iz `hosts` vzame samo
   naslove IPv4 (štiri desetiška števila brez vodilnih ničel), ki niso zanka (127.x), 0.x ali 224 in
   več; imena gostitelja ne razrešuje. Povezavo sprejme samo, če se potrdilo ujema z odtisom iz
   odgovora, in enkratni žeton pošlje šele po tem – naprava na napačnem naslovu ga ne vidi. Ko pravo
   napravo najde, so napake končne (drugih naslovov ne poskuša več).

   Star računalnik `hosts` ne pošlje in gledalec dela kot prej; star gledalec polje prezre. Naprave
   brez naslova v seznamu gledalec še vedno ne prosi (pravilo 7).

9. **Kar hub posreduje sam – datoteko in zaslon – pošiljatelj odda hubu ciljne naprave** (5. 10. 2026).
   Pot v `share.file` (`/cast/file/<id>?k=…`) in pot gledalca v `share.screen`
   (`/cast/screen/<id>/view?k=…`) sta relativni na hub, ki je vsebino sprejel, in se čez sosede ne
   preneseta. Zato:
   - **datoteka**: pošiljatelj jo odda (`PUT /cast/file`) hubu ciljne naprave, prijavljen s sejo s
     podpisom (`/cast/auth/challenge` → `/cast/auth/ticket`), kot sosednja povezava. Hub oddajo zavrne
     (409 `naprava_pri_drugem_srediscu`), če je cilj pri sosedu. Prejemnik datoteko poišče **najprej
     pri svojem hubu, nato pri pošiljateljevem** – iz sporočila se ne vidi, kateri jo ima; naslednji
     pride na vrsto samo, če prejšnji odgovori 404, vsaka druga napaka je končna
     (`link_deljenje.prevzemi_pri_srediscih`). Do 1.0.97 je Safeer Control na Linuxu vprašal samo
     pošiljateljev hub in datoteka z drugega računalnika je ostala v zalogi njegovega huba.
   - **zaslon**: pošiljatelj začne deljenje (`POST /cast/share/screen/start`) pri hubu ciljne naprave
     z isto sejo in tja potiska okvirje; ta hub svoji napravi pove, kje je gledalec
     (`link_deljenje.sredisce_za_zaslon`). Tako delajo računalniki. Telefon (Android) deljenje začne
     pri SVOJEM hubu in `share.screen` gre do cilja čez sosede, zato prejemnik stran gledalca poišče
     **najprej pri svojem hubu, nato pri pošiljateljevem** (`link_deljenje.gledalec_pri_srediscih`;
     velja prvi, ki stran ima). Hub zaslon posreduje samo napravi, ki je prijavljena pri njem (sicer
     409 `naprava_pri_drugem_srediscu`) – pri tretjem hubu prejemnik strani ne bi iskal.
     Hub računalnika zaslon posreduje od 1.0.99 (Linux) in 1.0.40 (Windows): isti protokol kot hub na
     Androidu (`link_hub_deljenje.Zasloni`), stran gledalca je samo za gledanje, deljenje pa se konča
     tudi, ko ga 10 s nihče več ne gleda – pošiljatelj razlog dobi v odgovoru na svoj tok okvirjev
     (`razlog: ni_gledalcev`). Prej računalnik računalniku zaslona ni mogel pokazati, zaslon s
     telefona pa se je na računalniku odprl kot napaka (stran gledalca je iskal samo pri svojem hubu).

   Zaupanje je isto kot pri sosednji povezavi: ključ v potrdilu huba mora biti ključ člana kroga
   (`link_mesh.sredisce_naprave`).

10. **Zdoma kot doma: kar naprava streže neposredno, streže tudi njen hub** (6. 10. 2026). Rele (Global
    Link) pripelje samo do vrat huba. Hub zato pod `/cast` streže vse poti strežnika datotek svoje naprave
    z istim žetonom (`X-Safeer-Token`) in istimi pravili: `/cast/d/<id>` (GET, HEAD in urejanje s POST),
    `/cast/thumb/<id>`, sprotni tok `/cast/live/<id>` in tok torrenta (`/cast/m/…` na računalniku,
    `/cast/magnet/…` na Androidu). Da hub to zna, pove `server.hub = 2` v odgovoru `files.list`; brez tega
    polja (starejši Safeer) naprava zdoma ponudi samo branje datotek. Urejanje gre vedno po eni sami poti
    (preimenovanje ali brisanje se ne sme izvesti dvakrat).

    **Zaslon računalnika** gre po isti poti: gledalec v `screen.start` pošlje `relay: true`, računalnik pot
    potrdi (`relay: true` v odgovoru), gledalec pa pride do huba z `GET /cast/desktop`
    (`Upgrade: safeer-desktop`, žeton seje v glavi `X-Safeer-Desktop`). Po odgovoru `101` hub povezavo preda
    seji (`Zaslon.prevzemi`) in po njej teče isti pretok kot po neposredni: ista kakovost slike, zvok in vnos
    nazaj – kakovosti zaradi poti ne nižamo. Gledalec poskusi obe poti hkrati; neposredna ima 0,3 s
    prednosti, zato doma zmaga, preden se rele sploh odpre, zdoma pa nihče ne čaka na naslove domačega
    omrežja. Seja dobi natanko enega gledalca: drugi in tisti z napačnim žetonom dobita 404.

    **Središče druge naprave zdoma** (pravilo 9): kadar soseda v tem omrežju ni, je naslov njegovega središča
    krajevni konec releja do njega (`MeshPovezovalec.naslov_prek_releja`; na Androidu `GlobalLink.vrataReleja`). Po
    njem gredo oddaja datoteke napravi, prevzem datoteke z naprave in stran gledalca deljenega zaslona. Kratek
    poskus povezave (0,7 s) pove, ali je sosed v tem omrežju; zaupanje je isto – ključ v potrdilu mora biti ključ
    člana kroga. Do 1.0.100 je računalnik za napravo zdoma odgovoril »Naprava v tem omrežju ni dosegljiva.«

    **Opis strežnika datotek ne sme biti odvisen od naslova v domačem omrežju.** Naprava na mobilnih podatkih ga
    nima, do njenih datotek pa pride druga naprava prek huba. V `server` zato vedno pošlje `fp`, `token` in
    `hub: 2`; brez domačega naslova je v `base_url` naslov iz dokumentacijskega obsega (`192.0.2.1`, RFC 5737), na
    katerem ni nikogar – neposredni poskus odpove in odjemalec gre prek huba. Odjemalec, ki ta obseg pozna
    (`192.0.2.0/24`: `link_pretok.brez_omrezja`, na Androidu `PotDoNaprave.brezOmrezja`), neposrednega poskusa
    sploh ne naredi – uporabnik ne čaka na nekaj, kar ne more uspeti. Do Safeer OS 0.5.57 (Android) je
    naprava na mobilnih podatkih poslala seznam brez `server`: druga naprava je datoteke videla, odpreti pa ne.

## Sporočila (novo)

```
mesh.devices   {type, id, payload: {hub: <device_id huba>, devices: [<zapis kot v cast.devices>]}}
mesh.route     {type, id, payload: {to: <lokalni id pri sosedu>, msg: "<surovo sporočilo>"}}
mesh.trust     {type, id, payload: <krog json>}     (zdruzi s preverjanjem podpisov, brez odmeva)
```

Seznam naprav (`cast.devices`, `mesh.devices`) gre od 1.0.127 (Android 0.5.90) kot posnetek + spremembe – glej
»Seznam naprav: samo spremembe« spodaj (`cast.devices.delta`, `mesh.devices.delta`, `*.sync`).

- `mesh.route`: prejemnik preveri, da je `to` njegova **lokalna** naprava, in ji pošlje `msg`
  nespremenjen (pošiljatelja je vpisal hub, ki ga je sprejel od svoje naprave). Največ 1 MiB.
- Hub sprejme `mesh.*` samo od povezave, prijavljene z `role: "hub"` in podpisom člana kroga.
- `mesh.trust`: vsak hub krog po spremembi pošlje sosedom; sosed združi (`zdruzi(preveriPodpise)`)
  in ga razpošlje svojim napravam samo, če se je spremenil.

## Kaj se ne spremeni

- Seznanitev (SPAKE2, QR, 6-mestna koda) pri kateremkoli hubu; `pair.code` doseže vse zaslone prek
  oddaljenih zapisov.
- Neposredne seje (zaslon, programi, datoteke računalnika, Data Transport) — že tečejo mimo huba.
- Rele link.safeer.si za internet (samo šifrirano).

## Znane meje v1

- Dostava prek vmesnega vozlišča (narejeno 29. 9.): `mesh.devices` nosi še `relay` = naprave
  NEPOSREDNIH sosedov (z `hub`). Kdor do take naprave nima svoje poti, jo vpiše kot posredno in ji
  pošilja `mesh.route` z `relay: true`; vmesni Hub preda naprej samo napravi svojega neposrednega soseda
  in samo v imenu naprave, ki je lokalna pri prosilcu. Največ en vmesni skok, brez zank; neposredna pot
  ima vedno prednost, ob njenem izpadu promet takoj steče prek vmesnega (in obratno).
- Nastavitev »Pomagaj drugim napravam v Linku pri povezavi« (18. 10. 2026, `link_mesh.pomaga_pri_povezavi`,
  `link-pomoc.json` ob nastavitvah Linka): privzeto vklopljena, stran Linka uporabnika ob seznanitvi enkrat vpraša
  (fokus na »Da«), stikalo je v razdelku »Povezava zdoma«. Izklopljena: Hub sosedom ne pošilja `relay` (naprav
  drugih sosedov ne predstavi) in `mesh.route` z `relay: true` zavrže. Lastne naprave te naprave in njena pot
  prek drugih vozlišč ostanejo enake; sprememba velja takoj (`Hub.osvezi_pomoc`).
- `share.file` prek huba (stari telefonski rele): pot `path` velja na hubu pošiljatelja; oddaljeni
  prejemnik dobi še `hub_address` in `hub_fp`. Stari prejemniki tega ne poznajo — zato novi pošiljatelji
  uporabljajo neposredno pot (Protocol v1).
- Kategorije `sync.*` se hranijo na hubu, ki jih je sprejel.
- Klepet, ki čaka na nepovezano napravo, hrani hub pošiljatelja in ga dostavi, ko se cilj pojavi
  lokalno **ali prek soseda**.

## Global Link: soseda zunaj doma (narejeno 29. 9.)

- Vsak Hub se objavi na `link.safeer.si` (AgentHuba: `/v1/presence` s seznamom `allow` = člani kroga,
  `/v1/listen`, kanal `/v1/accept` → lokalni Hub). Rele prenaša samo šifrirane bajte; TLS s pripetim
  ključem iz kroga in prijava s podpisom sta enaka kot v LAN. Tujec ne izve niti, ali Hub obstaja.
- Kdor kliče soseda: najprej neposredno (mDNS ali zapomnjeni naslov). Po **2 zaporednih** neuspelih
  klicih (brez odgovora ali napačen ključ) pokliče prek releja (`LokalniRele` / `GlobalLink.naslov`):
  lokalna vrata `127.0.0.1:x` → kanal `/v1/connect?to=<id iz ključa>`. Zavrnitev (`cast.ack rejected`)
  ni neuspeh — sosed je dosegljiv.
- Cilj releja je id iz ključa člana (Hub se lahko oglaša s pripono, npr. `n-…-control`).
- Po neuspehu prek releja premor 60 s, podvaja se do 10 min (dnevna kvota Workerja).
- Naslov `127.*` / `::1` / `localhost` si nikoli ne zapomnimo kot naslov soseda (to je lokalni konec releja
  ali dohodni kanal releja).
- Izklop: `SAFEER_GLOBAL_LINK=0` (računalnik) / nastavitev »Dostop do mojih naprav od kjerkoli« (Android).
  Preizkus doma: `SAFEER_MESH_RELE=id1,id2` (računalnik) / »Preizkus: tudi doma prek interneta« (Android).
- Znana meja: povezava prek releja ostane, dokler deluje; ko se naprava vrne domov, preide na LAN šele ob
  naslednjem ponovnem priklopu.
- Popravek ob tem: kanal releja in sosednja povezava vtičnico ob koncu samo `shutdown`, zapre pa jo šele,
  ko je nobena nit ne uporablja več. Prej je druga nit (OpenSSL) brala že zaprto številko vtičnice, ki jo je
  sistem dal naslednjemu kanalu → `WRONG_VERSION_NUMBER` (4 od 10 prijav prek releja; po popravku 25/25).

## Global Link: neposredna pot od zunaj (INTERNET_DIRECT, 15. 10. 2026)

Vrstni red poti: **LAN_DIRECT → INTERNET_DIRECT → SAFEER_RELAY**. Koda: `core/link_neposredno.py` (Linux),
`link/GlobalLink.kt` (Android, odjemalec). Neobvezno, privzeto izklopljeno: »Neposredna povezava od zunaj«
(Safeer Link → Povezava zdoma). Potrebuje stalen javni IPv4 doma in ENA preusmerjena vrata TCP (privzeto 48990)
na računalnik s središčem. Razlog: oba konca imata simetričen CGNAT, luknjanje UDP ne uspe (webrtc-raziskava,
POROCILO.md); če en konec sprejema dohodne povezave, telefon odpre navadno odhodno povezavo TCP.

- **Vhod (središče):** trk pred TLS (id iz ključa + čas ±120 s + nonce enkrat + podpis ECDSA nad id-jem središča)
  → TLS (1.3; najmanj 1.2 zaradi Androida 9) s ključem središča → izziv (podpis nad izzivom, odtisom potrdila in namenom). Neznan id, napačen
  podpis, star ali ponovljen trk: tiho zaprto, brez bajta odgovora (pregledovalnik ne vidi ne TLS ne potrdila
  z imenom računalnika). Lastna `link_obramba` (brez izjeme za zanko). Fiksna meja velja samo za nepreverjene
  povezave (do zadnjega bajta trka: 128 skupaj, 32 z enega naslova; nova izrine najstarejšo nepreverjeno), člane in
  tunele omejujejo samo viri računalnika (`core/link_viri.py`) – glej »Meje in roki« spodaj.
  Šele nato tunel na `127.0.0.1:<vrata Huba>` – skozenj nespremenjen TLS Linka, prijava, vstopnica in pravila
  dostopa (`link_dostop`). Novih končnih točk ni.
- **Oglas:** javni IPv4 iz STUN (`stun.cloudflare.com`, isti ponudnik kot rele), podpisan s ključem središča, rok
  15 min, v `candidate_hints` prisotnosti na `link.safeer.si` – vidijo ga samo člani kroga (`allow`). Odjemalec
  ga preveri s ključem iz kroga (ne zaupa releju): podpis, id, odtis ključa, rok, javni IPv4, vrata ≥ 1024.
- **Preverjanje dosegljivosti:** središče oglas označi kot preverjen šele, ko je z JAVNEGA naslova prišla prava
  overjena povezava (preizkus ali tunel). Naprava zdoma, ki vidi nepreverjen oglas, v ozadju sama naredi preizkus
  (namen 2: overi se in takoj zapre, Huba ne doseže). Nepreverjen oglas se nikoli ne uporabi na poti, na katero
  uporabnik čaka. Nov javni naslov ali druga vrata: preverjanje znova.
- **Odjemalec:** `LokalniOdZunaj` zamenja `LokalniRele` (isti vmesnik `vrata`): vsaka krajevna povezava najprej
  neposredno (TCP 1,5 s, rokovanje 3 s), ob neuspehu takoj prek releja. Po neuspehu premor 5 min (do 30 min);
  sprememba omrežja (drug krajevni naslov) ga izbriše. Zadnja delujoča pot in oglas: `global-link-poti.json`.
  Povezava prek releja se nadgradi na neposredno, ko ta postane na voljo (samo neposredna vrata, brez novega
  kanala releja); Hub obdrži boljšo pot (`link_pot.RANG_POTI`: lan > neposredno > rele).
- **Meritve in vmesnik:** obe poti sta na zanki; `link_pot.oznaci_zanko` po vratih loči neposredno od releja, zato
  `poti_sosedov` in razdelek »Povezava zdoma« kažeta »Lokalno«, »Neposredno (internet)« ali »Prek releja« z
  izmerjenim zamikom (brez naslovov IP).
- Izklop ne glede na nastavitev: `SAFEER_NEPOSREDNO=0`.

## Meje in roki, ki jih uporabnik lahko občuti (pregled 18. 10. 2026)

Lastnik, 18. 10. 2026: »Zakaj moramo imeti omejitve glede kroga zaupanja in pri neposrednih vhodih od zunaj? Kaj če
bi naše okolje želelo imeti veliko podjetje, kot je BSH?«

**Načelo.** Fiksne številke veljajo samo za NEPREVERJENE (kdor se še ni podpisal s ključem iz kroga) in kot tehnične
meje protokola. Člana kroga ne omejuje nobena številka – samo pravi viri računalnika, merjeni ob vsaki novi povezavi
ali delu (`core/link_viri.py`):

- deskriptorji: Link vedno pusti ostalemu procesu 512 prostih (pri meji pod 2048 četrtino meje) – Safeer OS je
  16. in 17. 10. 2026 pri meji 1024 končal s SIGTRAP, ker WebKit ni dobil deskriptorja za nov spletni proces;
- pomnilnik: nov član samo, če ostane nad 5 % RAM-a (najmanj 256 MiB) – Splet uspava zavihke že pod 10 %;
- niti: če jih sistem ne da, se to zabeleži enako.

Ko viri pošle, zavrnitev ni tiha: član dobi kodo `ni_virov` (neposredni vhod: bajt `BREZ_VIROV` šele po TLS s ključem
središča, zato ga nihče na poti ne more ponarediti), naprava brez virov pokaže opozorilo nad seznamom naprav in
obvestilo namizja (koliko jih je zavrnila, kaj pomaga), zavrnjena naprava pa ime naprave, ki je nima, in pri poti
zdoma, zakaj je zdaj prek releja – v šestih jezikih (sl, en, de, es, fr, it). Pošiljanje `ni_virov` šteje kot
prehodno in poskusi znova. Obramba (`link_obramba`) ostane enako stroga; zavrnitev zaradi virov ni sovražen dogodek.

**Podjetje: en javni naslov, veliko naprav.** Meritev 18. 10. 2026 (zanka, 2 deljeni jedri, pravi TLS, trk in izziv):

| Članov z ISTEGA naslova hkrati | Vsi neposredno v | Največ hkrati nepreverjenih | Največ hkrati v TLS | Izrinjenih |
|---|---|---|---|---|
| 200 | 1,6 s | 3 | 17 | 0 |
| 500 | 4,2 s | 5 | 31 | 0 |

Na člana: ~170 KiB RSS (obe strani zanke skupaj), na središču 3 deskriptorji (zunanja vtičnica, zanka, Hub) in 2 niti
(tunel teče v niti rokovanja). Pri privzeti meji 65 536 deskriptorjev (`os_stabilnost`) je to ~21 000 hkratnih
tunelov, preden odloči pomnilnik. Prej: največ 8 hkratnih rokovanj z naslova – 9. hkratna povezava izza istega NAT-a
je bila zavrnjena in je odjemalca za 5 min vrnila na rele.

### Meje, ki ostanejo (in zakaj)

| Kje | Meja | Velja za | Zakaj (meritev) |
|---|---|---|---|
| Neposredni vhod, do trka | 128 skupaj, 32 z enega naslova; rok trka 6 s | samo nepreverjene | Pregled 18. 10. 2026: en naslov je s 16 tihimi trki zasedel vsa mesta. Nova povezava nikoli ne čaka: izrine najstarejšo nepreverjeno (istega naslova, sicer z naslova, ki jih ima največ; nezaupani pred zaupanimi). Pravi odjemalec pošlje trk v isti milisekundi kot TCP (500 hkrati: največ 5 nepreverjenih), zato je izrinjena skoraj vedno tiha – v obrambi šteje kot neuspelo rokovanje, kot prej tiha po roku. |
| Neposredni vhod, TLS in izziv | 30 s | člane | Ne število – rok: član, ki med rokovanjem izgubi signal, ne drži niti za vedno; ob navalu TLS čaka na procesor (500 hkrati: 4,2 s). |
| Izziv za prijavo pri središču | 1024 hkrati, 60 s, enkraten | nepreverjene | Izziv dobi kdorkoli. Poplava izrine najstarejši izziv (član ga porabi v milisekundah), prej je za 60 s zaprla prijavo vsem. |
| Seznanitev s kodo | 8 čakajočih, 5 napak na prijavo, 10 napak/min, zapore varovalke | nepreverjene | Ugibanje šestmestne kode (`link_varovalka`, docs/LINK-DEFENCE.md). |
| Naslovi sosedov iz oglasov mDNS | 32 tujih | nepreverjene | Oglas lahko objavi kdorkoli v omrežju; naslovi članov kroga brez meje. |
| Seznam naprav pri odjemalcu | 512 tujih oznak | nepreverjene | Seznam piše središče in si oznake lahko izmisli; vsi člani kroga brez meje (prej prvih 512 – naprava čez mejo bi ukaz dobila nezaščiten). |
| Zaščita od naprave do naprave | nepotrjene seje 256, dogovori brez sporočila 64, dokazi ključa 16 na seznam in 4 na napravo na minuto, podpisi 32 na napravo na minuto, čakajoča sporočila 4 MiB na napravo / 16 MiB skupaj | ponudbe, ki jih središče lahko ponavlja | Vsak dogovor je podpis s ključem naprave (pregledi 7. 10. 2026: 500 ponudb = 500 podpisov). Potrjene seje in dogovori z ukazi tega računalnika nimajo skupne meje – izrinjanje samo ob pomanjkanju pomnilnika. |
| Na napravo, ne skupno | vstopnice, seje, žetoni seznanitve: 16; žetoni datotek: 8; seje zaščite: 16 | eno napravo | Nova prijava naprave nadomesti njene stare zapise (odjemalec hrani zadnjega); zapisov drugih naprav nikoli ne izrine. Prej skupne meje 64/64/32/64: 65. naprava je drugim izrinila sejo (401). |
| Tehnične meje protokola | okvir WebSocket 1 MiB, izhodna vrsta 64 okvirjev / 512 KiB na povezavo, sporočilo soseda 1 MiB, id do 128 znakov, ime do 64 | vse | Brez meje okvirja bi naprava (ali kdor se zanjo izdaja) napovedala 4 GiB in napolnila pomnilnik. Seznam naprav: ~245 B na napravo brez kataloga programov (izmerjeno) – v 1 MiB ~4000 naprav; katalog programov (`apps`) to zmanjša. |
| Seznam mape, programi, ena pošiljka | 500 vnosov, 200 programov, 5000 datotek | eno sporočilo / dejanje | Velikost enega odgovora (Android sprejme do 256 KiB) in zapis vrste ob vsaki datoteki; ni meja števila naprav – za večje mape je potrebno listanje po straneh. |
| Sprotno pretvarjanje (`link_sprotno`) | 1 tok hkrati | procesor | Dva hkratna pretvarjanja (ffmpeg) bi zatikala oba; to je vir, ne število naprav. |
| Opis kosov `/kosi` | 2 hkrati, mesto 30 s, računanje 300 s, pisanje 60 s tišine | procesor in disk | Opis: 35–38 MB/s z numpy, 5–6 MB/s brez; odjemalec (`link_nadaljuj.ROK_OPISA_S`) dlje kot 300 s ne čaka. Ob preseženem roku 503 – naprava prenese celo datoteko. |
| Tiha sosednja povezava (`TIHI_SOSED_S`) | 40 s brez prejetega bajta | rok | Pong prek počasnega releja z oddajo na isti poti: 2,4–8,8 s; 30 s je pongu po pingu (25 s) pustilo 5 s. Vsak prejeti bajt šteje kot življenje. |
| Pošiljanje (Control) | čakanje na napravo 24 h, tudi čez ponovni zagon | rok | `posiljanje-vrsta.json` ob nastavitvah Controla (0600, samo poti, id, rok). |
| Znane naprave (Nemo, zadnja naprava) | 90 dni brez videnja / rabe | rok | Zapisujejo se samo člani kroga tega računalnika. |
| Disk (zgodovina Teamworka) | rezerva 2 % diska, najmanj 1 GiB, največ 10 GiB | disk | Prej 1 GiB za vse diske (64 GB: 1,6 %, 2 TB: 0,05 %). |

### Odstranjene meje (prej → zdaj)

Neposredni vhod: 16 rokovanj, 8 na naslov, 4 rezervirana, 64 tunelov, 4096 noncev (ob navalu bi posnet trk spet
veljal) → viri, nonci samo z rokom. Središče: 32 naprav, 16 sosedov, prvih 32 naprav v seznamu soseda, 64 sej,
64 vstopnic, 32 žetonov, 3 prenosi, 64 čakajočih datotek, 4 zasloni, 4 gledalci → viri oz. na napravo. Teamwork:
32 sej na napravo, 8 prvih prijav, 16 niti `files.session`, 1 GiB rezerve → viri, rezerva po disku. Pošiljanje: vrsta
50, 32 zadnjih in 32 znanih naprav → vse (90 dni). Nemo: 8 naprav → vse (pri več kot 99 imena s tremi števkami).
Mesh: 32 naslovov sosedov → člani brez meje. Zaščita: 256 sej, 64 dogovorov z ukazi → samo nepotrjene/prazni.
Odjemalec: 512 naprav v seznamu, 512 zapisov dokazov → člani brez meje. Datoteke: 64 žetonov skupaj, 512 izrecno
poslanih, 16 naročnikov → na napravo / brez. Internet prek telefona: 48 tokov → viri. Dostop: 5 odprtih prošenj,
256 zavrnitev → vse (ena prošnja na črko in napravo, 24 ur). Oznake zank (`link_pot`): 4096 → ključ so vrata.

### Kar pri velikem krogu še ni rešeno (izmerjeno, ni število)

- **Seznam naprav:** rešeno v 1.0.127 (Android 0.5.90) – glej »Seznam naprav: samo spremembe«. Do takrat je vsaka
  sprememba šla vsem povezanim s CELIM seznamom (val prijav N naprav O(N³) bajtov: 32 naprav 2,8 MB, 100 naprav 79 MB,
  200 naprav 628 MB, 400 naprav 5,2 GB), naprava, ki ni dohajala, pa je izpadla (izhodna vrsta 512 KiB).
- **Iskanje člana v krogu** je linearno: pri 1000 članih 0,2 ms (s spominom id-ja iz ključa; prej 1,9 ms).
- **Obramba je po naslovu IP:** naprave za istim NAT-om si delijo usodo – naprava, ki se prijavlja narobe, lahko
  zapre naslov za 10 min (na zaupanem naslovu sovražni dogodki štejejo pol). Po navodilu (obramba enako stroga)
  nespremenjeno.

## Seznam naprav: samo spremembe (devdelta1, 18. 10. 2026)

Lastnik, 18. 10. 2026: »Safeer Link naj pošilja samo spremembe seznama naprav, ne celega seznama ob vsaki spremembi – za
podjetja z veliko napravami.« Koda: `core/link_spremembe.py` (Linux), `cast/SeznamSprememb.kt` (Android). Skupna pogodba
s primeri, ki jih preverjata oba: `tests/fixtures/seznam_sprememb.json` (ista datoteka v obeh repozitorijih).

**Dogovor (zmožnost `devdelta1`).** Odjemalec, ki zna, jo navede v `cast.register` (`capabilities`); sosednje središče
v prijavi in v polju `caps` svojega `mesh.devices`. Kdor je ne navede (starejši Safeer na računalniku, Androidu ali
Windows), dobi cel seznam kot doslej – mešan krog dela, nič se ne spremeni zanj.

**Sporočila.**

```
cast.devices        {type, devices: [<zapis>...], epoch, ver}              posnetek (starejši prezre epoch/ver)
cast.devices.delta  {type, epoch, base, ver, devices: <sprememba>}         samo kdor zna, samo z base = njegova ver
cast.devices.sync   {id, type}                                             odjemalec -> središče: pošlji posnetek
mesh.devices        {type, id, payload: {hub, devices: {id: zapis}, relay: {id: zapis}, epoch, ver, caps}}
mesh.devices.delta  {type, id, payload: {hub, epoch, base, ver, devices: <sprememba>, relay: <sprememba>}}
mesh.devices.sync   {type, id, payload: {hub}}                             sosed -> sosed: pošlji posnetek

<sprememba> = {add: [<cel zapis z "id">...], chg: [{id, set: {polje: vrednost}, unset: [polje]}], del: [id...]}
```

- `epoch` je naključna oznaka zaporedja pri tem središču (nova ob ponovnem zagonu in za vsako novo skupino
  prejemnikov), `ver` zaporedna številka. Sprememba velja samo, če je `epoch` ista in `base` natanko prejemnikova `ver`.
- Spremenjena naprava nosi samo spremenjena polja (`set`) in odstranjena (`unset`). Čas zadnjega stika (`last_seen`)
  ni sprememba: sicer bi vsaka objava nosila vse aktivne naprave – gre samo v posnetek in z dodano napravo.
- Vrstni red: kar ostane, na svojem mestu, nove naprave na koncu – tako ga sestavi prejemnik, zato je posnetek vedno
  enak seznamu, ki ga ima prejemnik po spremembah. Isti vrstni red dobi tudi starejši odjemalec.

**Vrzel in dvom.** Prejemnik, ki dobi spremembo z drugo `epoch` ali `base` (vrzel), ali spremembo, ki se ne sklada z
njegovim seznamom (sprememba ali odstranitev naprave, ki je nima, dodajanje naprave, ki jo ima, `id` v `set`/`unset`,
zrcalo čez 4 MiB – dvom), zahteva posnetek (`*.sync`, največ vsaki 2 s, dokler ga ne dobi); do takrat ostane zadnji
pravi seznam. Po ponovni povezavi je prvo vedno posnetek. Središče, ki sporočila ne more poslati, prejemniku naslednjič
pošlje posnetek, ne spremembe. Objave so zaporedne (ena za drugo), zato spremembe pridejo v vrstnem redu verzij.

**Varnost – ista kot pri celem seznamu.** Sprememba je razlika istega seznama, ki bi ga prejemnik dobil cel, zato velja
isto filtriranje: čez mejo središča gredo samo člani kroga, brez pomoči drugim napravam ni naprav drugih sosedov
(`relay`), odjemalec od drugod dobi naš naslov namesto zanke (pravilo 7). Skupine prejemnikov so iste kot prej. Ista
povezava TLS, prijava s podpisom in pravila dostopa (`link_dostop`) – nič iz sporočila sprememb ne podeli dostopa.
Zahteva za posnetek ne gre nikomur naprej; neprijavljena povezava je ne more poslati (`naprava_ni_povezana`).
Preizkusi: `tests/test_link_spremembe.py` (tujec ni v nobeni spremembi, brez pomoči ni `relay`, `here`/`ip` kot pri
celem seznamu, naključni mešani krog: novi odjemalec ima po vsaki spremembi natanko cel seznam), na Androidu
`tests/SeznamSpremembTest.kt`.

**Združevanje (okno 0,25 s).** Prva sprememba po mirovanju gre takoj (doma ni zakasnitve), vse naslednje v oknu
gredo skupaj ob njegovem koncu. Objava vedno prebere trenutno stanje, zato se nobena sprememba ne izgubi. Okno je
izbrano z meritvijo (spodaj): 0,25 s je bilo najboljše pri vseh merilih (bajti, sporočila, procesor, konvergenca).

**Starejši prejemnik v velikem krogu.** Cel seznam, ki še čaka v izhodni vrsti, novejši nadomesti na istem mestu
(`link_ws.Povezava.poslji(..., nadomesti=)`, enako pri odhodni sosednji povezavi). Prej se jih je ob valu nabralo do meje
vrste in naprava je izpadla. Pri prejemniku, ki zna spremembe, se nič ne nadomešča.

**Vrsta za sprejem povezav.** Središče na računalniku ima vrsto `listen` 512 (Python privzeto 5): ob valu prijav je
jedro preostale klice zavrglo in naprave so čakale na ponovni SYN 1, 3, 7, 15 s.

**Meritev 18. 10. 2026** (`tools/link_val_prijav.py zanka`: pravo središče s TLS v svojem procesu na zanki, vseh N
odjemalcev hkrati v drugem procesu, 2 deljeni jedri; »pred« = 2e05acb, »po« = devdelta1 + okno 0,25 s + vrsta 512):

| Naprav | Pred: seznami | Pred: vsi imajo cel seznam | Pred: CPU središča | Po: seznami | Po: vsi imajo cel seznam | Po: CPU središča |
|---|---|---|---|---|---|---|
| 32 | 3,4–4,6 MB | 1,3–2,1 s | 0,11–0,14 s | 0,31 MB | 0,31–0,34 s | 0,08–0,09 s |
| 100 | 98–107 MB | 2,9–3,9 s | 0,7–0,8 s | 3,0 MB | 0,44–0,55 s | 0,20–0,25 s |
| 200 | ~500 MB, nato izpad | nikoli (128–145 od 200 izpadlo) | – | 12,2 MB | 1,2–1,5 s | 0,5–0,6 s |
| 400 | ~630 MB, nato izpad | nikoli (303–318 od 400 izpadlo) | – | 49–50 MB | 5,7–14,8 s (6 meritev, mediana ~7 s) | 1,8–4,3 s |

Bajti so koristna vsebina sporočil seznama, ki so jih odjemalci res prejeli. Na napravo je promet zdaj linearen: pri 400
napravah ~124 KB, kot en sam cel seznam (vsaka naprava mora vsako drugo izvedeti vsaj enkrat). Pri 400 napravah čas
določa odjemalski proces (400 rokovanj TLS v enem procesu na dveh jedrih), zato razpon. Ločeno: samo vrsta 512 na starem
protokolu (100 naprav) 113 MB in 2,4 s, 200 naprav še vedno izpad (197); samo spremembe brez večje vrste (100 naprav)
3,1 MB in 2,4 s. Cena okna: konec vala pride do 0,25 s pozneje (32 naprav: 0,31 s namesto 0,22 s pri starem protokolu z
večjo vrsto); posamezna sprememba po mirovanju gre takoj.

Mešan krog na novem središču (isti preizkus; starejši dobijo cel seznam, a z oknom in nadomeščanjem v vrsti): 100 naprav,
polovica starejših, 3,0 MB in 0,56 s; 100 samih starejših 2,9 MB in 0,38 s; 400 naprav, polovica starejših, 639 MB in
28,6 s; 400 samih starejših 734 MB in 38,6 s – brez izpadov (pred: nikoli, 303–318 izpadlih). Starejši odjemalci so v
velikem krogu počasnejši, a ostanejo povezani; posodobitev jih pospeši.

Isti preizkus kot prej (`tools/link_val_prijav.py obdelaj`: `Hub.obdelaj`, prave prijave, vsota poslanega, brez
omrežja): pred 3,2 MB / 93 MB / 742 MB / 5,9 GB za 32 / 100 / 200 / 400 naprav (zapisi naprav so v tej meritvi
~10 % daljši kot 18. 10. ob 20.19: prijava nosi protocol, kind, version); po, samo spremembe brez okna 0,35 / 3,4 / 13,7 /
54,7 MB; po z oknom 0,25 s 0,30 / 2,9 / 11,6 / 46,3 MB (tudi s prijavami, razporejenimi čez 2 s: 0,31 / 2,9 / 11,7 /
46,4 MB). Android (`tests/SeznamSpremembTest.kt`, 32 naprav – meja središča na Androidu, brez okna): 2,16 milijona znakov
s celimi seznami, 0,30 milijona s spremembami.

**Izbira okna** (zanka, 400 naprav, vrsta 512, po dve meritvi):

| Okno | Sporočil seznama | Vsi imajo cel seznam | CPU središča | Bajti |
|---|---|---|---|---|
| 0 (brez združevanja) | 45–50 tisoč | 13,2–14,2 s | 6,2–6,6 s | 53 MB |
| 0,10 s | 20–21 tisoč | 9,3–12,0 s | 3,8–4,5 s | 50,5 MB |
| 0,15 s | 12–13 tisoč | 7,5–8,3 s | 2,6–3,0 s | 49,7 MB |
| 0,25 s | 6–8 tisoč | 5,7–6,9 s | 1,8–2,2 s | 49,1 MB |

Pri 100 napravah so bila okna 0,10–0,25 s enaka (0,42–0,50 s), brez okna 0,72 s. Večje okno je pri valu boljše po vseh
merilih, ker središče in odjemalci opravijo manj dela; plača se le z zakasnitvijo spremembe sredi vala (največ 0,25 s).
Z vidika uporabnika: doma (posamezna sprememba) zakasnitve ni, v podjetju se val konča prej. Izbrano 0,25 s.

**Znane meje.** Prejemnik mora seznam dobiti vsaj enkrat cel, zato je promet vala prijav še vedno sorazmeren N × N (vsaka
od N naprav mora izvedeti za vse N) – na napravo pa linearen: pri 400 napravah ~120 KB, kot en cel seznam. Starejši
odjemalec dobi cel seznam ob vsakem oknu, v katerem se je kaj spremenilo. Središče na Androidu ima vrsto za sprejem 16
in nadomeščanja celega seznama v vrsti še nima (središče na Androidu ima mejo 32 naprav). V polni mreži vsako središče
sosedom še vedno predstavi naprave vseh svojih sosedov (`relay`) – zdaj s spremembami, ne s celim zemljevidom.

## Združljivost

- Hub z mesh1 sprejema stare odjemalce kot doslej.
- Star hub (brez mesh1) sosednje povezave ne razume (`neznan_tip`); nov hub ga zato ne kliče kot
  soseda, ampak se tja (dokler ga ne posodobimo) poveže po starem kot odjemalec.
- Izvolitev ostane samo za stare naprave; nove se ne umikajo.

## Preizkusi

- Enotski (brez omrežja): trije hubi A–B–C s pravimi `obdelaj`: seznam na vsakem vsebuje vse,
  usmerjanje s ciljem, oddaja natanko enkrat, izpad B odstrani samo B-jeve naprave, lokalna prednost,
  `mesh.route` na nelokalno napravo zavrnjen, `mesh.*` od ne-huba zavrnjen, klepet čaka in se dostavi
  ob pojavu prek soseda, krog se razširi brez odmeva.
- V živo: Linux, TV, testni telefon, Windows — vsaka vidi vsako; ugasnemo TV → ostali se vidijo
  naprej brez prekinitve; ugasnemo računalnik → isto.
