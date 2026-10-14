# Where Safeer is going

*Slovenščina: spodaj.*

This is the direction, not a promise with dates. A small team builds Safeer, and we would
rather ship one thing that works than announce five that do not. If you want to help with
any of it, open an issue or a discussion, and say which part.

## What guides every decision

- A neutral and open internet: your sites work, not just ours (no per-site recipes).
- Privacy before convenience: no telemetry, no account, no ad profile.
- Decisions from measurements, judged from the user's side.
- The best use of the hardware people already have; we make no hardware.
- When we find a bug in a project we build on, we fix it there too.

## Now — Linux, GTK 4 (branch `gtk4`)

- **Safeer Browser on GTK 4 and WebKitGTK 6.0.** The Flatpak ships our patched WebKitGTK.
  Includes tracking-protection levels, per-site permissions, a pop-up policy that never blocks
  sign-in windows, a choice of DNS-over-HTTPS provider, downloads, find, print and clearing site data.
- **Media Center.** Shelves (Continue, Recently added, Favourites), playback options (audio
  tracks, subtitle delay and search, equaliser), faster catalogue loading.
- **Safeer OS shell** on Linux Mint with Cinnamon, and the Safeer mouse applet.

## Next

- Media Center: synced lyrics, an electronic programme guide for live TV, posters and
  metadata for local videos, podcasts.
- Messages: attachments in e-mail.
- The same browser features in Safeer Browser for Android, Android TV and Windows. Every
  improvement to the web experience goes to all of them.

## Later

- Safeer for Windows, built from the same shared core.
- Media Center: DLNA server, casting, user profiles, watching together.

## Upstream work

- libsoup: connection leak through an HTTP proxy, reported to Ubuntu with a patch and test,
  upstream report to GNOME in preparation.

---

# Kam gre Safeer

To je smer, ne obljuba z datumi. Safeer dela majhna ekipa in raje izda eno stvar, ki deluje,
kot napove pet, ki ne. Če želiš pomagati, odpri nalogo ali razpravo in povej, pri čem.

## Kaj vodi vsako odločitev

- Nevtralen in odprt internet: delujejo tvoje strani, ne le naše (brez receptov za posamezne strani).
- Zasebnost pred udobjem: brez telemetrije, brez računa, brez oglasnega profila.
- Odločitve iz meritev, s strani uporabnika.
- Najboljša uporaba strojne opreme, ki jo ljudje že imajo; strojne opreme ne izdelujemo.
- Ko najdemo napako v projektu, na katerem gradimo, jo popravimo tudi tam.

## Zdaj – Linux, GTK 4 (veja `gtk4`)

- **Safeer Browser na GTK 4 in WebKitGTK 6.0.** Flatpak ima naš popravljeni WebKitGTK. Vsebuje
  stopnje zaščite pred sledenjem, dovoljenja po straneh, pravila za pojavna okna, ki nikoli ne
  blokirajo prijavnih oken, izbiro ponudnika DNS prek HTTPS, prenose, iskanje, tiskanje in brisanje podatkov strani.
- **Medijski center.** Police (Nadaljuj, Nazadnje dodano, Priljubljene), možnosti predvajanja
  (zvočni posnetki, zamik in iskanje podnapisov, izenačevalnik), hitrejše nalaganje kataloga.
- **Lupina Safeer OS** na Linux Mintu s Cinnamonom in Safeerjev applet za miško.

## Naslednje

- Medijski center: sinhronizirana besedila pesmi, programski vodnik za TV v živo, plakati in
  podatki za lokalne videe, podkasti.
- Sporočila: priponke v e-pošti.
- Iste možnosti brskalnika tudi v Safeer Browserju za Android, Android TV in Windows. Vsaka
  izboljšava spletne izkušnje gre v vse.

## Pozneje

- Safeer za Windows, iz istega skupnega jedra.
- Medijski center: strežnik DLNA, pretakanje na naprave, profili uporabnikov, skupno gledanje.

## Delo za skupnost

- libsoup: uhajanje povezav prek posrednika HTTP, prijavljeno Ubuntuju s popravkom in testom,
  prijava pri GNOME je v pripravi.
