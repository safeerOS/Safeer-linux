# Pravila za AI pomocnike (Claude, Codex, Antigravity …) v Safeer-linux

Velja za vsako spremembo v tem repozitoriju. Kratko, preverljivo; podrobnosti so v kodi in testih.

## Vrednote in vodila
- Nevtralen in odprt internet; varnost in zasebnost uporabnika pred udobjem razvijalca.
- Odlocamo z izmerjenimi podatki, ne po obcutku. Vsako trditev (hitrost, RAM, CPU) podpre meritev.
- Odlocitev vedno s strani uporabnika: kaj je zanj najbolj udobno in varno.
- Popravek napake v odprtokodnem projektu (WebKit, libsoup …) vrnemo skupnosti.
- Vsaka izboljsava spletne izkusnje v Spletu (Safeer OS) gre tudi v vse brskalnike Safeer: Safeer Browser za Linux
  (safeer_brskalnik.py), Windows, telefon in TV (lastnik, 14. 10. 2026). Kar je skupno, je v skupnem modulu (core/).

## Zasebnost (nikoli v repo, commit, PR ali opombe izdaje)
- Ime lastnika, domaca pot, uporabnisko ime, ime gostitelja, MAC, e-naslovi, posnetki zaslona naprav. V besedilu: »lastnik«.
- Gesla, zetoni, kljuci (`-----BEGIN … PRIVATE KEY-----`, `ghp_…`, `github_pat_…`, `AIza…`, `AKIA…`) – preveri `tests/test_brez_skrivnosti.py`.
- Skrivnosti kanalov samo v sistemski zbirki (core/sporocila/skrivnosti.py), nikoli v datoteki ali dnevniku.

## Git in izdaje
- Novo delo gradi na veji `gtk4` (GTK4, WebKitGTK 6.0, QML) - najnovejsa tehnologija, ki dela na nasih napravah, brez dvojnega dela na starejsih vejah (lastnik, 14. 10. 2026).
- Delo na vejah; brez `--force`, brez brisanja oznak in izdaj, brez `git stash` brez oznake.
- Vmesni commiti z `[skip ci]` (gradnja WebKita traja 2–3 h); zadnji commit veje brez.
- Nic se ne objavi brez lastnikovega »da«. Pred izdajo: pregled kode, zelen CI, preizkus na testnem PC.

## Koda
- Komentarji in sporocila commitov v slovenscini (brez sumnikov v imenih), kratki, povejo ZAKAJ in kdaj je bilo izmerjeno.
- En proces: Safeer OS, Safeer Control, Splet in predvajalnik tecejo v istem procesu (core/en_proces.py).
- Safeer je samo GTK4 in WebKitGTK 6.0 (GTK3 umaknjen 18. 10. 2026): nove kode za GTK3 ne pisi.
- Nov modul v `core/` dodaj v seznam v `packaging/install_os_payload.sh` oziroma `install_control_payload.sh` (test `tests/test_tovor_uvozi.py`).
- Dostop drugih naprav: o vsebinah te naprave odloca samo ta naprava (core/link_dostop.py); nic iz dohodnega sporocila ne sme podeliti dostopa.
- Brez nadomestkov (»TODO«, lazni podatki, prazni gumbi) v vmesniku; kar ni narejeno, se ne pokaze.
- Besedila vmesnika v vseh jezikih, ki jih datoteka ze ima (sl, en, de, es, fr, it).
- Barve in videz iz enega vira (`assets/os/tokens.css`; QML dobi paleto iz njega prek core/os_lupina.paleta()), ne trdo kodirane barve po datotekah.
- Dostopnost: tipkovnica, fokus, kontrast; animacije spostujejo zmanjsano gibanje.

## Preizkusi
- Vsi preizkusi v enem procesu: `python3 -m pytest -q -p no:cacheprovider tests/` (CI poganja pytest, ker unittest ne vidi preizkusov kot funkcij).
- `python3 -m pytest -q -p no:cacheprovider tests/<datoteka>`; za JS `node -e "new Function(require('fs').readFileSync(F,'utf8'))"`.
- Zivi preizkus na testnem PC (Flatpak): `flatpak run --command=sh … -c "export PATH=/app/host-bin:$PATH; …"` – brez tega PATH orodja gostitelja (gsettings …) niso vidna.
- Vsak preizkus za sabo pospravi (lastnik, 16. 10. 2026: vsebnik `stres-tm` je 3 dni zasedal pomnilnik prenosnika):
  Docker samo z `--rm` (ali `docker rm -f` v `trap … EXIT`), zagnani procesi z `trap 'kill $PID' EXIT`, zacasne datoteke v `mktemp -d`.
  Na koncu preveri `docker ps -a` in `pgrep -af safeer` - ostane samo to, kar je teklo pred preizkusom. Procese koncaj po PID, ne s `pkill -f`.

## Kaj ni delovalo (preveri, preden poskusis)
- Zapisnik poskusov, ki niso bili ucinkoviti, vodi lastnik izven repozitorija (SAFEER-ZNANJE.md, razdelek ZAPISNIK). Novo napako dopisi tja.
