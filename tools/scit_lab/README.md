# Preizkus Ščita na pravem systemd-resolved + NetworkManager

Ščit (`core/os_scit.py`) spreminja sistemsko nastavitev DNS. Enotni testi (`tests/test_os_scit.py`) preverijo
logiko, ne pa tega, kako se v resnici obnašata systemd-resolved in NetworkManager – in prav tam so bile napake,
ki jih enotni testi niso mogli videti (glej spodaj). To okolje jih pokaže v dveh minutah.

Dva vsebnika Docker v svojem omrežju (omrežja gostitelja se nič ne dotakne):

- **usmerjevalnik** (`scit-usm`): dnsmasq – DHCP (naslov, DNS, domena `lan`) in DNS z dnevnikom poizvedb;
- **računalnik** (`scit-odj`): systemd, systemd-resolved, NetworkManager in polkit kot na namiznem Linux Mintu 22;
  koda iz tega repozitorija je priklopljena na `/repo`, Ščit poganja gonilnik `lab_scit.py` (brez vmesnika).

```
tools/scit_lab/lab.sh zgradi      # enkrat
tools/scit_lab/lab.sh preizkus    # cel samodejni preizkus; izhodna koda = število napak
PUSTI=1 tools/scit_lab/lab.sh preizkus   # okolje po preizkusu ostane za ročno raziskovanje
```

Ročno: `lab.sh gor`, `lab.sh gonilnik`, `lab.sh u vklop`, `lab.sh dns`, `lab.sh q oglasi.preizkus.example`,
`lab.sh u izklop`, `lab.sh dol`. Privzeto ne potrebuje interneta (blokirana je preizkusna domena
`preizkus.example`); s `PRAVI_SEZNAMI=1` gonilnik prenese prave sezname.

Potrebuje Docker z dovoljenjem za `--privileged` (systemd v vsebniku). Gonilnik teče kot root, zato pravila
polkit ne preizkuša – to je preverjeno posebej (`pkcheck`).

## Kaj preizkus varuje

Vse to je bilo v različicah do Safeer OS 0.4.42 narobe in je tu zdaj preverjeno:

1. **Izklop Ščita ali izhod iz Safeer OS ne sme pustiti računalnika brez DNS.** `resolvectl revert` pobriše tudi
   strežnike, ki jih je systemd-resolved dobil od NetworkManagerja; ta jih znova pošlje šele ob naslednji povezavi.
   Zdaj vmesnik dobi nazaj strežnike NetworkManagerja.
2. **Ščit mora poizvedbe res dobiti.** systemd-resolved obdrži strežnik, ki ga trenutno uporablja, če je ta tudi na
   novem seznamu; »naš + usmerjevalnik« v enem koraku ga je pustil pri usmerjevalniku. Zdaj v dveh korakih.
3. **Iskalna domena iz DHCP ostane** (prej jo je zamenjala usmerjevalna domena `~.` in kratka domača imena,
   npr. `nas`, se niso več razrešila).
4. **Računalnik z lastnim strežnikom DNS** (Pi-hole, AdGuard Home; `DNSStubListener=no`): Ščit pove, da ni na
   voljo, in se nastavitve ne dotakne.
5. Sesutje (DNS dela naprej prek rezerve), nov zagon, menjava omrežja, ostanki starejših različic.
