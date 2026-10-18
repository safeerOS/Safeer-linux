# Beta kanal Safeer OS (Linux)

Stanje 18. 10. 2026 (Safeer OS 0.4.85). Cilj lastnika: »Beta kanal za navdušence, manjše in pogostejše izdaje.«

## Za uporabnika

- **Nastavitve → Posodobitve → Beta kanal** (privzeto izklopljeno). Vklop: Safeer OS poleg stabilnih išče tudi beta
  različice in ponudi novejšo od obeh. Nič se ne namesti samo – namesti jo uporabnik s pritiskom na posodobitev.
- **Izklop** vrne stabilni kanal. Nameščena beta ostane, dokler stabilna ni enaka ali novejša
  (`0.4.86-beta.2 < 0.4.86`); nikoli se ne zamenja nazaj na starejšo (podatki bete morda niso berljivi za starejšo).
- Preverba je ista kot za stabilno: poldrugo minuto po zagonu in nato na 6 ur, ob preklopu kanala takoj.

## Zakaj je varno

| | Stabilno | Beta |
|---|---|---|
| Seznam | `https://safeer.si/os/razlicice.json` | `https://safeer.si/os/razlicice-beta.json` |
| Podpis | Ed25519, kontekst `safeer-razlicice-v1` | isti ključ, kontekst `safeer-razlicice-beta-v1` |
| Paket | obvezen SHA-256 iz podpisanega seznama, samo https | enako |
| Anti-rollback | `izdano` | ločeno `izdano_beta` |

Ločen kontekst podpisa pomeni: kdor obvlada strežnik (ne ključa), beta seznama ne more podtakniti kot stabilnega – tudi
že nameščenim starejšim različicam ne. Stabilni kanal predizdaj ne pokaže nikoli, tudi če bi pomotoma zašle v
stabilni seznam. Če beta seznama ni, je potekel ali podpis ni veljaven, beta uporabnik dobi stabilne posodobitve.
Pravila Ščita (`core/scit_pravila.py`, `intel.safeer.si`) so svoj podpisan vir in s kanalom nimajo zveze.

## Kako lastnik izda beto

1. **Različice** (na veji izdaje): `packaging/VERSION`, `VERSION_OS` in `VERSION_CONTROL` dobijo isti konec `-beta.N`,
   npr. `1.0.128-beta.1`, `0.4.86-beta.1`, `2.1.83-beta.1`. V obeh `*.metainfo.xml` gre na vrh
   `<release version="…-beta.1" type="development" date="…">`. README in PACKAGING.md ostaneta na zadnji stabilni
   (`packaging/check_version.py` ju pri beti ne preverja, preveri pa, da imajo vse tri isti `-beta.N`).
   Paket .deb dobi v polju Version `0.4.86~beta.1` (`packaging/deb_razlicica.sh`), da ga stabilna `0.4.86` posodobi.
2. **Oznaka** `v1.0.128-beta.1` (po lastnikovem »da«). CI gradi in preizkuša isto kot za stabilno; posel
   `beta-izdaja` naredi **osnutek predizdaje** (draft + pre-release). Nič se ne objavi samo. Posel `release` (stabilna)
   se za beta oznake ne zažene.
3. **Preizkus** na testnem računalniku, nato lastnik osnutek objavi – ostane označen kot *Pre-release*, zato GitHub
   »Latest« (in preizkus nadgradnje v CI) ostane na stabilni.
4. **Podpisan beta seznam** (na računalniku s ključem za `razlicice.json`):

   ```
   gh release download v1.0.128-beta.1 --repo safeerOS/Safeer-linux --dir <mapa>
   python3 tools/beta_seznam.py --oznaka v1.0.128-beta.1 --mapa <mapa> --kljuc <zasebni ključ> --izhod <izhod> \
       --novo-sl "…" --novo-en "…"
   ```

   V seznam gre tudi skupni WebKit `safeer-webkit_<različica brskalnika>_amd64.deb` (polje `webkit_deb` pri
   `safeer-os` in `safeer-browser`): oba paketa .deb ga zahtevata, Safeer OS ga namesti v istem `apt-get`.
   Orodje samo izračuna SHA-256 in jih primerja s `SHA256SUMS`, preveri, da je predizdaja objavljena in ima iste
   velikosti datotek, in podpis preveri z javnim ključem v programu. `razlicice-beta.json` in `.sig` gresta na
   `https://safeer.si/os/` ob `razlicice.json` (z gradnjo strani, kot stabilni seznam). Seznam velja 30 dni (`--dni`).
5. **Stabilna izdaja** `1.0.128` (brez `-beta`): beta uporabniki jo dobijo sami, ker je novejša od vseh `1.0.128-beta.N`.
