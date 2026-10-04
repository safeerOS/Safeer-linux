# Paketi .deb na pravem Linux Mintu

Posel `deb-appimage` v CI pakete zgradi in namesti na Ubuntu 22.04. Tam se paketa videza (`safeer-os-tema`,
`safeer-cinnamon`) sploh ne dasta namestiti – `mint-themes` obstaja samo v Linux Mintu –, odvisnosti pa razreši
drugo skladišče kot pri uporabniku. Ta preizkus naredi to, kar naredi uporabnik: v sliki Linux Minta (skladišča
Minta in Ubuntuja) namesti vseh pet paketov, jih zažene in odstrani.

```
tools/mint_namestitev/preizkus.sh linuxmintd/mint22.3-amd64 MAPA_S_PAKETI [MAPA_S_PREJŠNJO_IZDAJO]
```

Koraki (`v_vsebniku.sh`; prva napaka konča preizkus z izhodno kodo, ki ni 0):

1. namestitev vseh petih paketov z `apt-get install` (odvisnosti iz skladišč). Če je podana mapa s paketi zadnje
   objavljene izdaje, se najprej namesti ta, programi se zaženejo kot root (najslabši primer: v mapah programov
   ostane njihova bajtna koda), nato pridejo novi paketi čeznjo z ukazom, s katerim posodobitev namesti Safeer OS
   sam (`apt-get install --allow-downgrades`) – posodobitev je pot vsakega obstoječega uporabnika. Po namestitvi
   mora imeti vsak modul prevedeno bajtno kodo (`postinst`);
2. različice programov (`safeer`, `safeer-control`, `safeerctl`, `safeer-os`) se ujemajo z različicami paketov;
3. zaganjalniki v meniju so veljavni;
4. Safeer OS se zažene kot navaden uporabnik in izriše stran (posnetek zaslona ni prazen, v izpisu ni izjeme);
   peskovnik WebKita je v Safeer OS vedno vklopljen, zato to hkrati pove, da peskovnik na Mintu dela;
5. ukaza videza (`safeer-os-tema`, `safeer-cinnamon`) sta veljavna, datoteke tem so na mestu;
6. odstranitev ne pusti ničesar (tudi bajtne kode ne: `prerm`).

Teče v CI (`.github/workflows/linux-packages.yml`, posel `mint`, Linux Mint 22 in 22.3) na prav tistih datotekah,
ki gredo v izdajo, s posodobitvijo z zadnje objavljene izdaje; brez zelenega preizkusa izdaja ne nastane.

Česar ne preveri: namizja Cinnamon (vklop videza, pult, delovna površina – slika `linuxmintd` namizja nima) in
priporočenih paketov (`--no-install-recommends`; pri uporabniku so z namizjem že nameščeni).

Potrebuje Docker z dovoljenjem za `--privileged` (peskovnik WebKita). Linux Mint dovoli uporabniške imenske
prostore (`/etc/sysctl.d/20-apparmor-mint.conf`), Ubuntu jih omejuje. Nastavitev je v jedru gostitelja: na
gostitelju z Ubuntujem jo pred preizkusom izklopi (`sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`);
CI to naredi sam.

Prvi tek (4. 10. 2026) je našel napako, ki je enotni testi niso mogli: po `apt-get remove` so ostale mape
programov, ker je Python v njih pustil `__pycache__`. Od takrat paketi bajtno kodo prevedejo ob namestitvi
(hitrejši zagon – uporabnik v `/usr/lib` ne more pisati) in jo ob odstranitvi počistijo.
