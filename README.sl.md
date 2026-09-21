# Safeer Browser za Linux

Hiter, lahek brskalnik z zasebnostjo na prvem mestu za Linux Mint, Ubuntu in Debian — GTK3 in
WebKit2GTK, zato se odpre v trenutku in pusti ventilatorje pri miru.

[![Licenca](https://img.shields.io/badge/Licenca-Apache_2.0-blue?style=flat-square)](LICENSE)
[![Platforma](https://img.shields.io/badge/Platforma-Linux_Mint_%7C_Ubuntu_%7C_Debian-87cf3e?style=flat-square)](#zahteve)
[![Paketi](https://img.shields.io/badge/Paketi-deb_%7C_AppImage_%7C_Flatpak-cyan?style=flat-square)](../../releases/latest)

English: [README.md](README.md) · Spletna stran: [safeer.si](https://safeer.si)

> **Safeer je varnostna plast, ne jamstvo.** Zmanjša izpostavljenost in blokira znane grožnje.
> Pred vsakim novim ali neznanim napadom te ne more zaščititi.

---

## Kaj zna

**Hiter zagon, majhna poraba.** Nativni GTK3 z WebKit2GTK — brez Electrona, brez drugega
brskalniškega pogona, brez posodabljalnika v ozadju.

**Krajevni ščit pred grožnjami.** Botnetni C2, gostitelji zlonamerne kode in lažno
predstavljanje iz virov abuse.ch (Feodo Tracker, URLhaus, ThreatFox) in Phishing Army, ujeti
lokalno v O(k) prek obrnjenega domenskega drevesa. Za to odločitev se o tvojem brskanju nikamor
ne pošlje nič. Seznam pride kot podpisan vir (Ed25519) po prvem zagonu; dokler ni prenesen,
velja le majhen vgrajen zasilni seznam.

**Blokirani oglasi in sledilci**, blokirani piškotki tretjih oseb, sledilni parametri
odstranjeni iz povezav, brez telemetrije. Privzeti iskalnik je DuckDuckGo.

**Šifriran DNS** prek HTTPS z delujočim HTTP/2 in brez tihega preklopa na navadni DNS ob napaki.
Ponudnikoma, ki ju dosežemo po imenu (Quad9, AdGuard), se naslov strežnika enkrat poišče prek
sistemskega DNS; Cloudflare in Google dosežemo po IP. Zaenkrat samo naslovi IPv4 (zapisi A).

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

[![Izdaja](https://img.shields.io/badge/Release-v1.0.42-2dd4bf?style=flat-square)](../../releases/tag/v1.0.42)

Zadnja izdaja: **v1.0.42** — [opombe izdaje in prenosi](../../releases/tag/v1.0.42)

```bash
# Debian, Ubuntu, Linux Mint
sudo apt install ./safeer-browser_1.0.42_all.deb
```


Prenesi iz [Izdaj](../../releases/latest). Za vsako izdajo nastanejo trije paketi:

```bash
# Debian / Ubuntu / Linux Mint
sudo apt install ./safeer-browser_<verzija>_all.deb

# AppImage — brez namestitve, samo izvršljiv
chmod +x Safeer-Browser-<verzija>-x86_64.AppImage && ./Safeer-Browser-<verzija>-x86_64.AppImage

# Flatpak
flatpak install ./Safeer-Browser-<verzija>-x86_64.flatpak
```

Ali pa v upravitelju datotek preprosto dvoklikni `.deb`.

AppImage in Flatpak sta narejena samo za x86_64. Paket `.deb` ni vezan na arhitekturo (Python
na sistemskem GTK in WebKit2GTK), a na ARM64 ni preizkušen ob vsaki izdaji.

Preveri, kaj si prenesel, s `SHA256SUMS` iz iste izdaje:

```bash
sha256sum -c --ignore-missing SHA256SUMS
```

Vsote ujamejo poškodovan prenos. Še niso podpisane, zato ne varujejo pred nekom, ki bi lahko
zamenjal datoteke v sami izdaji.

**Safeer Control** — spremljevalna namizna aplikacija, ki ta računalnik poveže s telefonom ali
televizorjem Safeer prek tvojega omrežja — je v isti izdaji kot
`safeer-control_<verzija>_all.deb` in brskalnika ne potrebuje.

## Zahteve

Sodoben Linux Mint, Ubuntu ali Debian z GTK3 in WebKit2GTK. AppImage za izdaje je grajen proti
glibc 2.35 (Ubuntu 22.04), zato teče tudi na starejših sistemih.

## Gradnja iz izvorne kode

```bash
bash build_deb.sh                  # paket Debian
bash packaging/build_appimage.sh   # AppImage
bash packaging/build_flatpak.sh    # Flatpak
```

Testi:

```bash
python3 -m unittest discover -s tests
```

## Vzemi in predelaj

Kdor obvladuje brskalnik, določa pravila spleta. Projekt je pod Apache-2.0 prav zato, da ga
lahko vzameš, zamenjaš sezname, spremeniš videz, dodaš, kar potrebuješ, in izdaš svojega.

## Sodelovanje

Glej [CONTRIBUTING.md](CONTRIBUTING.md). Varnostne težave gredo po poti iz
[SECURITY.md](SECURITY.md), zasebno in ne v javno prijavo.

## Licenca

Apache License 2.0 — glej [LICENSE](LICENSE).
