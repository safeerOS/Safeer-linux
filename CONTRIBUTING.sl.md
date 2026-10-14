# Sodelovanje pri Safeerju

*English: [CONTRIBUTING.md](CONTRIBUTING.md)*

Hvala, da si si vzel čas. Safeer je odprtokoden (Apache-2.0), dela ga majhna ekipa in vsak
popravek, prijavo napake ali popravek prevoda prebere človek. Raje ti pomagamo do prvega
sprejetega popravka, kot da čakamo na popolnega.

## Edino pravilo, o katerem se ne pogajamo

**Brez receptov za posamezne strani.** V Safeerju ni kode, napisane za eno imenovano spletno
stran: brez `if (hostname === "example.com")`, brez `site_example.js`, brez seznama selektorjev,
prepisanega iz ene strani. Vse deluje po tem, *kaj* stran je (oznake, oblika toka, vzorec
zahtev), ne po tem, kdo jo objavlja.

To ni stil, to je obljuba izdelka: delujejo tvoje strani, ne le naše. Pravilo preverja
`tests/test_brez_receptov_za_strani.py`. Edina stalna izjema je YouTube, katerega predvajalnik in
oglasi so del izdelka. Če stran ne deluje, je pravi popravek splošno pravilo za vso vrsto strani
in test, ki to dokaže.

Zaznamki, ploščice začetne strani in glasovne bližnjice niso recepti, so le vnosi v seznamu.

## Kje začeti

- **Naloge z oznako `good first issue`** so zastavljene tako, da zadošča en večer; vsaka pove,
  katere datoteke prebrati najprej.
- **Prevodi.** Vmesnik je v slovenščini, angleščini, nemščini, španščini, francoščini in
  italijanščini. Če je eden od teh tvoj jezik, preberi slovarje `BESEDILA` v `core/` in popravi,
  kar zveni narobe.
- **Napake, na katere naletiš sam.** Natančna prijava s koraki je prispevek sama po sebi.

Kam gre projekt, piše v [ROADMAP.md](ROADMAP.md#kam-gre-safeer). Ne veš, ali ideja sodi zraven? Najprej odpri nalogo (issue) in vprašaj.

## Priprava razvojnega okolja

Novo delo poteka na veji **`gtk4`** (GTK 4, WebKitGTK 6.0, Qt Quick za lupino Safeer OS).
Referenčni sistem je Linux Mint 22 ali Ubuntu 24.04.

```bash
git clone https://github.com/safeerOS/Safeer-linux.git
cd Safeer-linux && git switch gtk4

sudo apt install python3-gi python3-gi-cairo python3-pytest python3-cryptography \
  gir1.2-gtk-4.0 gir1.2-gtk-3.0 gir1.2-webkit-6.0 gir1.2-webkit2-4.1 gir1.2-soup-3.0 \
  gir1.2-secret-1 gir1.2-gstreamer-1.0 gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
  gstreamer1.0-libav glib-networking xvfb

python3 safeer_brskalnik.py        # Safeer Browser (GTK 4)
python3 safeer_os.py               # lupina Safeer OS
```

### Preizkusi

GTK 3 in GTK 4 ne moreta biti naložena v istem procesu Python, zato sta preizkusa v dveh
skupinah. `tools/razdeli_teste.py` skupino določi iz uvozov:

```bash
PYTHONPATH=tests xvfb-run -a python3 -m unittest $(python3 tools/razdeli_teste.py gtk3)
PYTHONPATH=tests xvfb-run -a python3 -m unittest $(python3 tools/razdeli_teste.py gtk4)
```

Skupina `gtk4` potrebuje še PySide6 za lupino Qt Quick (`pip install PySide6` ali
`python3 packaging/pyside6_vendor.py build/vendor` in `build/vendor` v `PYTHONPATH`, kot v CI).
Med delom zadošča ena datoteka: `xvfb-run -a python3 -m pytest -q tests/test_pojavna_okna.py`.

## Zgradba kode

- `core/` – skupni moduli. Logika, ki ne potrebuje okna (imena prenosov, pravila pojavnih oken,
  stopnje zaščite, dovoljenja strani …), je v modulih brez GTK, da si brskalnik, Safeer OS in
  preizkusi delijo eno izvedbo.
- `safeer_brskalnik.py` – Safeer Browser (GTK 4). `safeer_mint.py` – starejši brskalnik GTK 3.
- `safeer_os.py`, `assets/os/` – lupina Safeer OS (QML, plošče HTML/JS; vse barve in teme so v `os.css`).
- `packaging/` – .deb, AppImage, Flatpak (Flatpak ima naš popravljeni WebKitGTK).
- Nov modul v `core/` dodaj v `packaging/install_os_payload.sh` ali `install_control_payload.sh`;
  to preverja `tests/test_tovor_uvozi.py`.

Komentarji in sporočila commitov so lahko v slovenščini ali angleščini.

## Preden odpreš pull request

- Poženi preizkuse. Rdeči preizkusi pomenijo, da ni pripravljeno.
- Ena težava na pull request.
- V sporočilu commita povej *zakaj*: kaj je bilo narobe, kako veš, da je popravljeno, in na
  kateri napravi ali distribuciji si to videl delovati.
- Novo vedenje potrebuje test.
- Besedilo vmesnika gre v vse jezike, ki jih datoteka že ima. Če jezika ne znaš, napiši
  angleško in to omeni v pull requestu.
- Brez nadomestkov v vmesniku: gumb, ki še nič ne naredi, ne gre v izdajo.
- Nikoli ne objavi osebnih podatkov – imen, domačih poti, imen računalnikov, e-naslovov,
  ključev ali žetonov. `tests/test_brez_skrivnosti.py` preverja pogoste skrivnosti.

## Prijava napake

Odpri nalogo: kaj si naredil, kaj si pričakoval, kaj se je zgodilo, različica (Nastavitve ali
`safeer --version`) ter naprava ali distribucija.

**Varnostne napake ne sodijo med javne naloge.** Glej [SECURITY.md](SECURITY.md).

## Popravki, ki jih vračamo skupnosti

Ko je napaka v projektu, na katerem gradimo (WebKitGTK, libsoup, GStreamer, Cinnamon), jo
popravimo tudi tam, s testom, in jo prijavimo vzdrževalcem. Tako sta nastala popravljeni
WebKitGTK v našem Flatpaku in popravek uhajanja povezav v libsoup, prijavljen Ubuntuju. Če pri
delu na Safeerju najdeš takšno napako, je prijava s popravkom pri izvornem projektu enako
dobrodošla – in radi ti pomagamo pri pisanju.

## Trditve morajo biti resnične

Če sprememba spremeni, kaj brskalnik počne, v istem pull requestu posodobi README.

## Pravila vedenja

Velja [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
