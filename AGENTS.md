# Pravila za AI pomocnike (Claude, Codex, Antigravity …) v Safeer-linux

Velja za vsako spremembo v tem repozitoriju. Kratko, preverljivo; podrobnosti so v kodi in testih.

## Vrednote in vodila
- Nevtralen in odprt internet; varnost in zasebnost uporabnika pred udobjem razvijalca.
- Odlocamo z izmerjenimi podatki, ne po obcutku. Vsako trditev (hitrost, RAM, CPU) podpre meritev.
- Odlocitev vedno s strani uporabnika: kaj je zanj najbolj udobno in varno.
- Popravek napake v odprtokodnem projektu (WebKit, libsoup …) vrnemo skupnosti.
- Safeer Link nima sredisca: vsaka naprava je lahko sredisce. Vloge (sredisce, posrednik, pomocnik, nadzornik) so
  zacasne funkcije po zmogljivosti v trenutku, nikoli trajen rang; odpad katerekoli naprave ali streznika ne razbije
  kroga. Vsak krog naprav je svoj svet - skupnega imenika vseh uporabnikov ni (lastnik, 20. 10. 2026, po Giordanu
  Brunu: »v neskoncnem ni izstopajocih tock, zato je vsaka tocka osrednja«).
- Rezervni nacin mora biti vedno na voljo, a ne sme izpodbijati najboljsega: vklopi se sam samo, ko najboljsi nacin
  ne dela, in se vrne nanj, takoj ko spet dela (lastnik, 20. 10. 2026; npr. Link: Mesh je najboljsi, izvolitev enega
  Huba je rezerva).
- Vsaka izboljsava spletne izkusnje v Spletu (Safeer OS) gre tudi v vse brskalnike Safeer: Safeer Browser za Linux
  (safeer_brskalnik.py), Windows, telefon in TV (lastnik, 14. 10. 2026). Kar je skupno, je v skupnem modulu (core/).
- Splet in brskalniki Safeer se zgledujejo po modernih brskalnikih: omogocimo vse, kar drugi, ali bolje, in smo enako
  hitri. Strani nas prepoznajo kot Safari, zato smo vsaj tako dobri kot Safari (lastnik, 21. 10. 2026). Http strani
  samodejno na https, ce jih stran ponuja (povratek na http, ce ne); iskanje ostane mogoce tudi za vpis, ki je naslov.
- Profil po zmogljivosti naprave (lastnik, 21. 10. 2026): naprave z vec RAM (racunalniki, telefoni z veliko RAM)
  polno izkoristijo vecprocesni spletni motor s peskovnikom, vecnitno sestavljanje strani in GPU; TV in naprave z malo
  RAM ohranijo varcni enoprocesni modul aplikacije. Izmerjeno 21. 10.: spletni motor je ze vecprocesen (WebKitGTK:
  procesi strani v bubblewrap; Android WebView: sandboxed_process tudi na TV) - »en proces« velja za vmesnik Safeer.

## Razvoj Spleta (WebKit)
- Vedno nas WebKit (lastnik, 21. 10. 2026): program, meritev ali preizkus s sistemskim WebKitGTK ni veljaven - pred
  meritvijo preveri razlicico in pot nalozene knjiznice (21. 10. je LD_LIBRARY_PATH na napacno mapo tiho nalozil 2.52.6).

## Utrjena gradnja (lastnik, 21. 10. 2026: »ce imamo te ranljivosti, nismo zares Safeer«)
- Vsaka knjiznica in program, ki ga gradimo sami (WebKit, JavaScriptCore, libsoup, dav1d, rqbit, Qt, nase .so), je vsaj
  tako utrjen kot paket distribucije: -fstack-protector-strong, -D_FORTIFY_SOURCE=3, -fstack-clash-protection,
  -fcf-protection=full (CET: IBT+SHSTK), PIE, -Wl,-z,relro,-z,now (BIND_NOW), GNU_STACK RW (brez E).
- Izmerjeno 21. 10.: nas WebKit 2.54.1 brez BIND_NOW, 2 namesto 10 funkcij _chk, brez CET; libsoup brez zascite sklada
  (Ubuntujev libwebkitgtk vse ima). Vsaka nova gradnja: readelf -dlnW + nm -D v CI za VSAKO datoteko .so/program v paketu;
  manjkajoca zascita ustavi gradnjo. Hitrost ni razlog za manj zascite; ce zastavica ne gre z BOLT/PGO, izmeri in zapisi.
- Pred vsakim delom na Spletu, Safeer Browserju ali WebKitu preberi docs/SMERNICE-SPLET.md (izmerjena arhitektura,
  merjenje PSS in A/B, funkcije WebKita, profil naprave, pomnilnik, varnost, ustreznice tehnik drugih brskalnikov).

## Zasebnost (nikoli v repo, commit, PR ali opombe izdaje)
- Ime lastnika, domaca pot, uporabnisko ime, ime gostitelja, MAC, e-naslovi, posnetki zaslona naprav. V besedilu: »lastnik«.
- Gesla, zetoni, kljuci (`-----BEGIN … PRIVATE KEY-----`, `ghp_…`, `github_pat_…`, `AIza…`, `AKIA…`) – preveri `tests/test_brez_skrivnosti.py`.
- Skrivnosti kanalov samo v sistemski zbirki (core/sporocila/skrivnosti.py), nikoli v datoteki ali dnevniku.

## Git in izdaje
- Novo delo gradi na veji `gtk4` (GTK4, WebKitGTK 6.0, QML) - najnovejsa tehnologija, ki dela na nasih napravah, brez dvojnega dela na starejsih vejah (lastnik, 14. 10. 2026).
- Delo na vejah; brez `--force`, brez brisanja oznak in izdaj, brez `git stash` brez oznake.
- Vmesni commiti z `[skip ci]` (gradnja WebKita traja 2–3 h); zadnji commit veje brez.
- Nic se ne objavi brez lastnikovega »da«. Pred izdajo: pregled kode, zelen CI, preizkus na testnem PC.
- Avtor commitov je ekipa: `Safeer <info@safeer.si>` (lastnik, 18. 10. 2026: »team Safeer, we have a team work«).
  Brez vrstic `Co-Authored-By`, `Claude-Session` in podobnih oznak posameznega orodja ali agenta - tudi v PR in MR
  gorvodno. Da je pri delu pomagal AI, lahko pove opis PR/MR (»Safeer team, with AI assistance«), ne avtorstvo.

## Koda
- Komentarji in sporocila commitov v slovenscini (brez sumnikov v imenih), kratki, povejo ZAKAJ in kdaj je bilo izmerjeno.
- En proces: vmesnik Safeer OS, Safeer Control, Splet in predvajalnik tecejo v istem procesu (core/en_proces.py);
  spletne strani tecejo v procesih spletnega motorja s peskovnikom.
- Safeer je samo GTK4 in WebKitGTK 6.0 (GTK3 umaknjen 18. 10. 2026): nove kode za GTK3 ne pisi.
- Nov modul v `core/` dodaj v seznam v `packaging/install_os_payload.sh` oziroma `install_control_payload.sh` (test `tests/test_tovor_uvozi.py`).
- Dostop drugih naprav: o vsebinah te naprave odloca samo ta naprava (core/link_dostop.py); nic iz dohodnega sporocila ne sme podeliti dostopa.
- Brez nadomestkov (»TODO«, lazni podatki, prazni gumbi) v vmesniku; kar ni narejeno, se ne pokaze.
- Besedila vmesnika v vseh jezikih, ki jih datoteka ze ima (sl, en, de, es, fr, it).
- Barve in videz iz enega vira (`assets/os/tokens.css`; QML dobi paleto iz njega prek core/os_lupina.paleta()), ne trdo kodirane barve po datotekah.
- Dostopnost: tipkovnica, fokus, kontrast; animacije spostujejo zmanjsano gibanje.

## Preizkusi
- Vsi preizkusi v enem procesu: `python3 -m pytest -q -p no:cacheprovider tests/` (CI poganja pytest, ker unittest ne vidi preizkusov kot funkcij).
- Vodilo D-Bus v preizkusu: `tests/zasebno_vodilo.ZasebnoVodilo` (lasten dbus-daemon), nikoli `Gio.TestDBus` - ta v
  vecnitnem procesu naredi fork() brez exec in spremeni okolje procesa (setenv); polni tek se je 19. 10. 2026 sesul
  (segfault). Podprocesu daj okolje z `env=`, namesto da spreminjas `os.environ`.
- `python3 -m pytest -q -p no:cacheprovider tests/<datoteka>`; za JS `node -e "new Function(require('fs').readFileSync(F,'utf8'))"`.
- Zivi preizkus na testnem PC (Flatpak): `flatpak run --command=sh … -c "export PATH=/app/host-bin:$PATH; …"` – brez tega PATH orodja gostitelja (gsettings …) niso vidna.
- Vsak preizkus za sabo pospravi (lastnik, 16. 10. 2026: vsebnik `stres-tm` je 3 dni zasedal pomnilnik prenosnika):
  Docker samo z `--rm` (ali `docker rm -f` v `trap … EXIT`), zagnani procesi z `trap 'kill $PID' EXIT`, zacasne datoteke v `mktemp -d`.
  Na koncu preveri `docker ps -a` in `pgrep -af safeer` - ostane samo to, kar je teklo pred preizkusom. Procese koncaj po PID, ne s `pkill -f`.

## Kaj ni delovalo (preveri, preden poskusis)
- Zapisnik poskusov, ki niso bili ucinkoviti, vodi lastnik izven repozitorija (SAFEER-ZNANJE.md, razdelek ZAPISNIK). Novo napako dopisi tja.

## Pravila iz napak izdaje 1.0.127 (19. 10. 2026) - obvezno za vsakega pomocnika
Vsaka od teh napak je ze bila narejena; neodvisni pregled ali lastna raziskava jo je ujela sele tik pred objavo.
- **Gradnja (BOLT, prevajalnik, povezovalnik):** nikoli `llvm-bolt --use-gnu-stack` - zbrise PT_GNU_STACK, sklad
  vseh procesov z WebKitom postane izvrsljiv (glibc 2.41+ knjiznice sploh ne nalozi). Po vsaki spremembi gradnje
  preveri vsako knjiznico in program v paketu: `readelf -lW` -> `GNU_STACK ... RW` (brez E) in v delujocem procesu
  `[stack]` brez `x` (`packaging/webkit-deb/bolt.sh`, `packaging/smoke_webkit_deb.py`). Hitrost ni razlog za manj zascite.
- **Root in datoteke uporabnika:** `pkexec`/`sudo` nikoli ne bere datoteke, ki jo lahko uporabnik spremeni (npr. v
  `~/.cache`), po tem, ko smo jo preverili: program z uporabnikovimi pravicami jo zamenja po vpisu gesla in dobi root.
  Root naj vsebino dobi po standardnem vhodu ali jo sam prekopira v svojo mapo in preveri SHA-256 KOPIJE proti vsoti
  iz podpisanega vira (`core/os_posodobitve.NAMESTI_DEB_KOT_ROOT`, `core/os_scit.namesti_pravilo`).
- **Potisk na GitHub:** pred potiskom nove veje preveri, kaj vse gre ven (`git rev-list <veja> --not <vrhovi iz
  git ls-remote>`): stevilo commitov, avtorje, vsebino. Nikoli ne potiskaj iz starega klona z zgodovino pred ciscenjem
  (veja `obnova-zavihka` je tako v safeerOS odnesla 328 starih commitov z imenom lastnika). Nov repozitorij je najprej zaseben.
- **Meritve in javne trditve:** primerjaj samo izmenicne meritve istega dne z enakim stevilom procesov in vsaj tremi
  ponovitvami; enkratna meritev proti izhodiscu drugega dne ni rezultat. Stevilka gre v opombe ali gorvodno (GitHub,
  Bugzilla) sele, ko je tako izmerjena - sicer jo je treba javno popravljati.
- **Izdaja:** objava sele po neodvisnem pregledu (drug agent ali clovek, ki dela ni naredil) in po pregledu varnostno
  obcutljive kode (posodobitve, dostop naprav, root, DNS). Oznaka `v*` v CI nima predpomnilnika veje - paketi izdaje so
  artefakti zelenega teka veje za isti commit, ne nova gradnja iz oznake.
- **Preizkusi:** vsak varnostni popravek ima preizkus, ki brez popravka pade (preveri tako, da popravek zacasno umaknes).
- **Mostovi WebKit (`register_script_message_handler`):** WebKit da `window.webkit.messageHandlers` VSEM okvirjem strani
  in sporocilu ne doda okvirja. Vsak most je zato v locenem svetu (`UserScript.new_for_world`, kot `SVET_SKLADBE`,
  `SafeerControl.SVET_VNOSA`) ali sprejme samo sporocila z zetonom iz zaprtja skripta glavnega okvirja (`ZETON_MOSTU` v
  `safeer_os.py` in `core/safeer_link.py`). Preizkus v pravem WebKitu: okvir drugega izvora mostu ne doseze.
- **Omrezje s kljucem ali ukazom:** `http://` samo v domace omrezje, zahteve s kljucem ne sledijo preusmeritvam
  (`core/agent/nastavitve.odpri`), prenosi preverijo VSAK skok preusmeritve. TLS brez CA (samopodpisano) samo s
  pripetim odtisom, preverjenim PRED posiljanjem (`core/os_jbl._zahteva`); odtise in kljuce primerjaj s
  `hmac.compare_digest`. Javni kljuc (npr. JBL One) ni skrivnost in ne dokazuje, kdo poslja.
- **Root prek pkexec:** pkexec in program vedno z absolutno potjo (`core/root_ukaz.py`): pkexec program poisce po
  PATH klicatelja, kjer je ~/.local/bin pred /usr/bin. Root ne bere ne kopira uporabnikove datoteke brez preverbe
  vrste in omejitve velikosti (`dd iflag=nofollow,nonblock`, glej `NAMESTI_DEB_KOT_ROOT`).
- **Podatki z drugih naprav:** ime ali pot, ki jo poslje druga naprava, je samo ime (`link_deljenje.varno_ime`) in
  `realpath` cilja mora ostati v nameravani mapi; nikoli absolutna pot ali `..`. Umik naprave iz kroga takoj preklice
  njene zetone in seje (ne sele ob izteku).
- **Okolje procesa (os.environ):** ko proces tece z nitmi (ze `import gi` z GTK zazene 8 niti), spremenljivk ne
  dodajaj in ne brisi - samo zamenjaj vrednost obstojece (`core/okolje_procesa.py`: rezervacije in prevzem pred nitmi).
  Podprocesu daj okolje z `env=`/`execve`, zastavice v procesu namesto okoljskih spremenljivk.
- **Scit (DNS):** razresevalnik odgovori v ~0,4 s (`ROK_NAPREJ`), sicer systemd-resolved preide na usmerjevalnik
  MIMO Scita in tam ostane. Pocasen DoH ne sme zadrzati odgovora.

## Pravila iz napak izdaje 1.0.129 (20. 10. 2026) - obvezno za vsakega pomocnika
Lastnik je dvakrat posnel isto napako (lupa -> »Išči v spletu« -> »Strani trenutno ni mogoče odpreti«), webmaster
pregled pa je na strani nasel 6 napacnih SHA-256. Vsaka tocka spodaj je ze bila narejena narobe.
- **Popravi vzrok, ne simptoma; »popravljeno« sele po uporabnikovi poti v zivo.** Prvi popravek (samodejna ponovitev)
  je skril simptom, lastnik je cez 10 minut poslal »Se vedno ne deluje«. Vzrok je bil izmerjen sele z nadzorom procesov:
  napako ponovi na pravi napravi po enakih korakih kot uporabnik (lupa, cakanje, iskanje), zapisi dnevnik (sled.log) in
  sele nato popravi. Preizkus enote ne dokazuje, da uporabnikova pot dela.
- **Omreznega procesa WebKit nikoli ne koncaj od zunaj (SIGTERM),** dokler zivijo spletni procesi istega konteksta:
  WebKit jih hrani za nove zavihke s povezavo na koncanega - prvo nalaganje odpove z notranjo napako (WebKitErrorDomain
  300). Velja tudi za recikliranje ob porabi pomnilnika. Puscanje libsoup resujemo z nasim popravkom (packaging/libsoup),
  ne z ubijanjem procesa; AppImage nosi sistemski libsoup - zaznava »nas libsoup« mora to razlikovati.
- **Samodejna ponovitev nalaganja:** samo GET glavnega okvirja; POST, PUT in neznana metoda nikoli. `decide-policy`
  pride tudi za iframe - metode zbiraj (ne zamenjuj) in neznan naslov je GET samo, ce so vse zbrane GET. Napake, pri
  katerih zahteva morda ze odsla (prekinjena povezava, rok), ponovi samo na straneh zadetkov iskalnikov
  (core/network_errors.py). Preizkus, ki caka »tisino« nalaganja, mora cakati dlje od najdaljsega zamika ponovitve.
- **Vsote in stevilke na strani nikoli rocno.** Gradnja strani vzame SHA-256 iz SHA256SUMS izdaje in se USTAVI ob
  neujemanju ali manjkajoci vsoti; po objavi prenesi vsaj eno datoteko in primerjaj vsoto. Isto za velikosti in razlicice.
- **Ne strgaj iskalnikov z urllib/curl** (DuckDuckGo po 2 zahtevah vrne 202 - robot). Sprotni zadetki lupe beremo v
  skritem Spletu v seji uporabnika (core/spletni_zadetki.py), skripta v locenem svetu, besedilo prek textContent.
- **Preizkus, ki isce v kodi** (dostopnost, encoding, mostovi), mora pokriti vse oblike zapisa (`Gtk.Button`,
  `self.Gtk.Button`, pomozne funkcije `self._gumb(...)`); preveri, da pade na kodi pred popravkom.
- **Simbolne povezave v preizkusih paketov:** `stat -L` (knjiznica .so.4 je povezava; inode povezave ni inode datoteke).
- **Testni PC (XTEST):** pred vsakim klikom ali tipkanjem posnetek; koordinate iz pomanjsanega posnetka preracunaj
  (1440x900 zaslon, pomanjsan posnetek) - napacen klik je tipkal v lupo namizja.
- **Webmaster pregled:** vsaka sprememba strani safeer.si, Spleta ali lupe gre pred objavo skozi webmaster pregled
  (vsote, povezave 200, sitemap/canonical, telefon, dostopnost, hitrost) - drug agent kot avtor. Napake iz pregleda
  se popravijo ali izrecno prestavijo v zapisnik; prestavljene tocke so prva naloga naslednje izdaje.
