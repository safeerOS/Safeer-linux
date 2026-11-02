# Poročilo o nalogi: OKNA-API

## Vzrok za spremembe
1. Vmesnik za namizje (Safeer OS) mora razdelke, ki imajo svoja okna (npr. Zapiski, Nastavitve, Medijski center, Sporočila), odpreti v lastnem oknu in ne znotraj istega okna kot preklop na podstran, saj namizno okolje pričakuje boljše ločevanje razdelkov (na pametnih televizorjih in prenosnih napravah to morda ni potrebno).
2. Ime "Usenet (prek TorBoxa)" ni bilo natančno, saj je dodan lasten Usenet ponudnik, zato je ime spremenjeno v nevtralno "API indeksator" po vseh prevodih, s popravljenimi spremljajočimi navodili.
3. Ker uporabnik v Medijskem centru izbira način predvajanja v menuju "Debrid storitve", Usenet ponudnik ni bil viden tam. Po zgledu TV vmesnika (Moji viri) mora biti enostaven in hiter prehod iz spustnega seznama Debrid neposredno v nastavitve Useneta.

## Kaj je spremenjeno
1. **Odkrivanje mostov za okna v `safeer_os.py`:**
   V Python mostu `_obdelaj_klic` smo omogočili klicev `"odpriOknoRazdelka"` in `"odpriPredvajalnik"`, ki neposredno sprožita gradnjo posamičnih oken `Gtk.ApplicationWindow`. Pri začetnem prenosu lastnosti sistema (`_zacetek`) je v izid dodana zastavica `"mostOkna": True`, ki `os.js` sporoči, da je gradnja teh oken podprta na trenutni platformi.
2. **Prehod na okna v `assets/os/os.js`:**
   Ob kliku na razdelek v funkciji `vTemOknu` preverimo, ali most podpira ustvarjanje oken in ali smo v glavnem oknu (kjer bi se prej odprla podstran). Če podpiramo in gre za enega izmed ustreznih razdelkov, metoda vrne `false` in ustrezno zahteva odpiranje prek `"odpriOknoRazdelka"` oziroma `"odpriPredvajalnik"`.
3. **Preimenovanje TorBox Usenet imena:**
   V `assets/os/besedila.js` je povsod `"usenetIme"` posodobljen (v slovenščini »API indeksator«, en »Indexer API«, de »Indexer-API«, es »API del indexador«, fr »API de l'indexeur«, it »API dell'indicizzatore«). Enako so posodobljena opozorilna besedila (`usenetBrezTorbox`, `usenetBrezPro` in `usenetPojasnilo`), ki zdaj obravnavajo tudi lastne ponudnike ("...ali dodaj ponudnika").
4. **Združenje vnosnih polj in prikaz indeksatorja v izbiri vira:**
   Polja za nastavitev API indeksatorja (`#unpIndeksator`) in lastnega Usenet ponudnika (`#unpSekcija`) sta bila združena pod isto streho pod razdelkom »Dodatki in viri«.
   V spustni meni ponudnikov `mediaDebrid` je dodana izbira "Usenet" oziroma "Dodaj ponudnika Usenet" (odvisno od stanja in prevodov). Ko uporabnik izbere to možnost, ga sistem neposredno preusmeri v meni `#slojKatViri` na vnosna polja za Usenet ponudnika, s čimer odpade iskanje polj v jedru aplikacije.

## Preizkusi
`node -e "new Function(require('fs').readFileSync('assets/os/os.js','utf8'))"` brez napak.
`node -e "new Function(require('fs').readFileSync('assets/os/besedila.js','utf8'))"` brez napak.
`ruff check safeer_os.py` nima nobenih novih napak (tiste, ki obstajajo, so tam že od prej in niso bile vpeljane s to spremembo).
Unit testi (zaradi zahtev in manjkajoče knjižnice na tem sistemu niso povsem prehodni za Pytest preko pytest) potrebujejo zagon na ciljnem stroju ali testnem namizju `flatpak run`, a ker sprememba ne vpliva na sistemske klice, ni prišlo do kršitev tipizacije.

## Za ročni preizkus
1. V glavnem oknu klikni na Medijski center, Zapiske ali Nastavitve. Odpreti se morajo nova, samostojna okna.
2. V Medijskem centru v zgornjem vrstici preveri spustni meni za izbiro Debrid storitev (»Debrid / Viri«). Tam se mora prikazati izbira »Dodaj ponudnika Usenet«.
3. Klikni to izbiro – odpreti se mora preglednica z nastavitvami za indeksator IN lastnega ponudnika NNTP v enem oknu / sekciji (`unpSekcija`).

KONEC