# Safeer Browser za Linux

Hiter, lahek brskalnik z zasebnostjo na prvem mestu za Linux Mint, Ubuntu in Debian — nativni GTK4
in WebKitGTK 6.0 z našimi popravki pogona, zato se odpre v trenutku in pusti ventilatorje pri miru.

[![Licenca](https://img.shields.io/badge/Licenca-Apache_2.0-blue?style=flat-square)](LICENSE)
[![Platforma](https://img.shields.io/badge/Platforma-Linux_Mint_%7C_Ubuntu_%7C_Debian-87cf3e?style=flat-square)](#zahteve)
[![Paketi](https://img.shields.io/badge/Paketi-deb_%7C_AppImage_%7C_Flatpak-cyan?style=flat-square)](../../releases/latest)

English: [README.md](README.md) · Spletna stran: [safeer.si](https://safeer.si)

> **Safeer je varnostna plast, ne jamstvo.** Zmanjša izpostavljenost in blokira znane grožnje.
> Pred vsakim novim ali neznanim napadom te ne more zaščititi.

---

## Kaj zna

**Nativni GTK4, naš WebKit.** Nativni GTK4 z WebKitGTK 6.0 — brez Electrona, brez drugega
brskalniškega pogona, brez posodabljalnika v ozadju. Flatpak prinese WebKitGTK 2.54.1 s popravki, ki
smo jih razvili sami ([packaging/webkit](packaging/webkit)): plasti z backdrop-filter v kompozitorju
Skia se ne izrisujejo več 2ⁿ-krat, utišan video MediaSource izven vidnega polja pa tokov ne pušča več
obtičanih v »nalaganju«. Popravki so pripravljeni za WebKit; ko jih bo imel WebKitGTK sam, naše
gradnje ne bo več.

**Isti pogon kot Safeer OS.** Brskalnik in Splet v Safeer OS sta ena koda: vsaka izboljšava spleta je
takoj v obeh.

**Klepeti in pošta ob strani.** Stranska plošča ima spletne klepete in pošto (WhatsApp, Messenger,
Telegram, Gmail …) z istega seznama kot Sporočila v Safeer OS, prijavljene z isto sejo kot zavihki in
z isto zaščito. Število neprebranih pove naslov strani.

**Zaščiten video.** Safeer DRM, pomočnik, ki je del paketa in se zažene le ob potrebi, predvaja video z
Widevine (Netflix, Disney+ …) v zavihku brskalnika, pogon strani pa ostane v celoti v peskovniku. Googlov modul
Widevine se ob prvem zaščitenem videu samodejno prenese z Googlovih strežnikov.

**Krajevni ščit pred grožnjami.** Botnetni C2, gostitelji zlonamerne kode in lažno
predstavljanje iz virov abuse.ch (Feodo Tracker, URLhaus, ThreatFox) in Phishing Army, ujeti
lokalno v O(k) prek obrnjenega domenskega drevesa. Za to odločitev se o tvojem brskanju nikamor
ne pošlje nič. Seznam pride kot podpisan vir (Ed25519) po prvem zagonu; dokler ni prenesen,
velja le majhen vgrajen zasilni seznam.

**Blokirani oglasi in sledilci**, blokirani piškotki tretjih oseb, sledilni parametri
odstranjeni iz povezav, brez telemetrije. Privzeti iskalnik je DuckDuckGo.

**Nezaželena pojavna okna blokirana, prijavna ostanejo.** Stran lahko odpre okno le po tvojem
kliku. Okno, ki ga skripta odpre na drugo stran, je blokirano z vrstico, kjer ga lahko vseeno odpreš
ali stran vedno dovoliš; prijavna in plačilna okna (Google, Microsoft, Apple, PayPal, `/login`,
`/oauth` …) in okna iste strani se vedno odprejo, z ohranjeno povezavo do strani, zato »Prijava z …«
deluje.

**Varni prenosi.** Datoteke gredo v mapo Prenosi pod imenom, ki ga da strežnik, nikoli ne prepišejo
obstoječe, programi in namestitveni paketi (`.deb`, `.AppImage`, `.exe`, `.sh` …) pa se prenesejo
šele po tvoji potrditvi.

**Povezave na druge programe vprašajo.** `mailto:`, `magnet:`, `zoommtg:` in podobne odpre program na
tvojem računalniku po potrditvi; »vedno« si brskalnik lahko zapomni za vsako stran.

**Šifriran DNS** prek HTTPS (izbereš Quad9, AdGuard, Cloudflare, Google, svoj strežnik ali izklop) z
delujočim HTTP/2 in brez tihega preklopa na navadni DNS ob napaki. Ponudnikoma, ki ju dosežemo po imenu
(Quad9, AdGuard), se naslov strežnika enkrat poišče prek sistemskega DNS; Cloudflare in Google dosežemo
po IP. Najprej se vpraša za naslov IPv4 (zapis A), IPv6 (AAAA) le, če ga stran nima.

**Predvajanje v ozadju.** Glasba in podkasti tečejo naprej ob menjavi zavihkov, z dovolj nizko
porabo procesorja, da prenosnik ostane tih.

**Uvoz zaznamkov z enim klikom.** Bere profile Firefoxa (`places.sqlite`) ter Chrome, Brave in
Chromium (`Bookmarks`) neposredno, združi brez podvojitev, zna pa tudi uvoz iz izvoza Netscape
HTML za vse ostalo.

**Bližnjice, ki jih že poznaš.** `Ctrl+T`, `Ctrl+W`, `Ctrl+Shift+T`, `Ctrl+Tab`,
`Ctrl+1`…`Ctrl+9`, `Alt+Home` ter `Ctrl+B` in `Ctrl+Shift+B` za vrstico in meni priljubljenih.

**Dostojen sostanovalec na namizju.** S seboj prinese AppStream metainfo, zato se pravilno
pokaže v Upravitelju programov, namesti zaganjalnik pod Internet, se registrira kot alternativni
spletni brskalnik in nikoli na skrivaj ne prevzame vloge privzetega brskalnika — če ga hočeš
imeti za privzetega, je tu `safeer --set-default`.

## Namestitev

[![Izdaja](https://img.shields.io/badge/Release-v1.0.108-2dd4bf?style=flat-square)](../../releases/tag/v1.0.108)

Zadnja izdaja: **v1.0.108** — [opombe izdaje in prenosi](../../releases/tag/v1.0.108)

```bash
# Debian, Ubuntu, Linux Mint
sudo apt install ./safeer-browser_1.0.108_all.deb
```


Prenesi iz [Izdaj](../../releases/latest). Za vsako izdajo nastanejo trije paketi:

```bash
# Debian / Ubuntu / Linux Mint
sudo apt install ./safeer-browser_<verzija>_amd64.deb

# AppImage — brez namestitve, samo izvršljiv
chmod +x Safeer-Browser-<verzija>-x86_64.AppImage && ./Safeer-Browser-<verzija>-x86_64.AppImage

# Flatpak
flatpak install ./Safeer-Browser-<verzija>-x86_64.flatpak
```

Ali pa v upravitelju datotek preprosto dvoklikni `.deb`.

`.deb` in **Flatpak** imata naš WebKitGTK 2.54 in libsoup 3.8 (gradnja s Clangom in ThinLTO, s popravki
Safeerja); `.deb` ju hrani v `/usr/lib/safeer-browser/webkit` ob programu in WebKitGTK sistema ne
zamenja. AppImage uporablja WebKitGTK sistema, na katerem je zgrajen. Če sta nameščena `.deb` in
Flatpak, ukaz `safeer` zažene Flatpak (iste nastavitve, prijave in zaznamki). Vsi paketi so narejeni
samo za x86_64 (amd64).

Preveri, kaj si prenesel, s `SHA256SUMS` iz iste izdaje:

```bash
sha256sum -c --ignore-missing SHA256SUMS
```

Vsote ujamejo poškodovan prenos. Še niso podpisane, zato ne varujejo pred nekom, ki bi lahko
zamenjal datoteke v sami izdaji.

**Safeer Control** — ta računalnik poveže s telefonom ali televizorjem Safeer prek tvojega omrežja — je
del enega paketa Safeer OS `safeer-os_<verzija>_amd64.deb` v isti izdaji (ena namestitev za Safeer OS,
Control in videz Safeer Cinnamon) in brskalnika ne potrebuje. Prinese tudi `safeerctl`, Safeer Link
iz ukazne vrstice (`safeerctl devices`, `safeerctl send datoteka --to NAPRAVA`, `--json` za skripte):
glej [docs/SAFEERCTL.md](docs/SAFEERCTL.md). S telefonom s Safeer OS Mobile lahko internet tega računalnika
ob izpadu domače povezave teče skozi telefon — brez dostopne točke: glej
[docs/INTERNET-GATEWAY.md](docs/INTERNET-GATEWAY.md).

**Nazaj na Cinnamon.** Nastavitve Safeer OS → *Nazaj na Cinnamon* (ali `safeer-os --nazaj-na-cinnamon` v terminalu,
tudi kadar namizje ne dela): Safeer OS se ne zažene več ob prijavi, Mintov pult, dock in videz se vrnejo, kot so bili
pred Safeer OS. Nič se ne odstrani, tvoji podatki ostanejo; nazaj prideš, ko Safeer OS odpreš iz menija.

## Zahteve

`.deb` in AppImage: Linux Mint 22 ali novejši, Ubuntu 24.04 ali novejši ali Debian 13, z GTK4 in
WebKitGTK 6.0 (AppImage je grajen proti glibc 2.39). Starejši sistemi, npr. Linux Mint 21: uporabi
Flatpak — GTK4 in naš WebKit prinese s sabo.

Iz izvorne kode `bash install.sh` za trenutnega uporabnika namesti isti brskalnik GTK4
(`safeer_brskalnik.py`) in preveri iste pakete kot `.deb`; `bash uninstall.sh` ga odstrani
(`--purge` tudi profil).

## Gradnja iz izvorne kode

```bash
bash build_deb.sh                  # paket Debian
bash packaging/build_appimage.sh   # AppImage
bash packaging/build_flatpak.sh    # Flatpak
```

Testi (en proces, samo GTK 4; podrobnosti v [CONTRIBUTING.sl.md](CONTRIBUTING.sl.md#preizkusi)):

```bash
PYTHONPATH=tests xvfb-run -a python3 -m pytest -q tests/
```

## Vzemi in predelaj

Kdor obvladuje brskalnik, določa pravila spleta. Projekt je pod Apache-2.0 prav zato, da ga
lahko vzameš, zamenjaš sezname, spremeniš videz, dodaš, kar potrebuješ, in izdaš svojega.

## Sodelovanje

Glej [CONTRIBUTING.sl.md](CONTRIBUTING.sl.md). Varnostne težave gredo po poti iz
[SECURITY.md](SECURITY.md), zasebno in ne v javno prijavo.

## Licenca

Apache License 2.0 — glej [LICENSE](LICENSE).
