/* Safeer Cinnamon - delovna povrsina (iskanje, predvajalnik, datoteke, programi naprav).
 *
 * Vse podatke da Safeer OS prek mosta window.SafeerOS.klic(metoda, argumenti) - iste metode kot glavna
 * stran (mapa, nedavne, isciDatoteke, napraveZDatotekami, datotekeNaprave, napraveSProgrami,
 * programiNaprave, zazeniNaNapravi, odpriTukaj, knjiznicaMedijev, predvajalnikStanje ...).
 * Stran si ne izmislja naprav, datotek ali programov: kar most ne vrne, se ne prikaze.
 */
(function () {
  "use strict";

  // ------------------------------------------------------------------ most
  var most = window.SafeerOS || null;
  function klic(metoda, argumenti) {
    if (!most) return Promise.reject("brez mosta");
    return Promise.resolve(most.klic(metoda, argumenti || []));
  }
  function $(id) { return document.getElementById(id); }
  function el(oznaka, razred, besedilo) {
    var e = document.createElement(oznaka);
    if (razred) e.className = razred;
    if (besedilo != null) e.textContent = besedilo;
    return e;
  }

  // ------------------------------------------------------------------ besedila (SL, EN)
  var BESEDILA = {
    sl: {
      iskanjePh: "Išči po spletu, programih, datotekah in medijih …", iskanjeNamig: "Enter = splet",
      plosceNaslov: "Plošče", medijiNaslov: "Medijski center", datotekeNaslov: "Datoteke", programiNaslov: "Programi naprav",
      zamenjajStrani: "Zamenjaj levo in desno", ponastavi: "Privzeta postavitev", vecjiTekst: "Večje besedilo",
      manjProsojnosti: "Manj prosojnosti", skrijPlosco: "Skrij ploščo", spremeniVelikost: "Povleci za spremembo velikosti (puščice s tipkovnico)",
      odpriMedijskiCenter: "Odpri Medijski center", niPredvajanja: "Ni predvajanja",
      medijNavodilo: "Izberi glasbo ali video v Datotekah ali v Medijskem centru.",
      prejsnja: "Prejšnja", premor: "Predvajaj / premor", naslednja: "Naslednja",
      predvaja: "Predvaja", vPremoru: "Premor", ustavljeno: "Ustavljeno", napakaPredvajanja: "Predvajanje ni uspelo",
      filterPh: "Filtriraj …", filterPrgPh: "Išči programe …", vseVrste: "Vse vrste", vrstaDokument: "Dokumenti",
      vrstaSlika: "Slike", vrstaVideo: "Video", vrstaZvok: "Glasba", vrstaMapa: "Mape",
      en_mapa: "Mapa", en_dokument: "Dokument", en_slika: "Slika", en_video: "Video", en_zvok: "Zvok", en_arhiv: "Arhiv",
      en_program: "Program", en_splet: "Splet", en_drugo: "Drugo",
      stIme: "Ime", stVrsta: "Vrsta", stLokacija: "Lokacija", stVelikost: "Velikost", stSpremenjeno: "Spremenjeno",
      pregled: "Pregled", nedavno: "Nedavno", priljubljeno: "Priljubljeno", mape: "Mape", naprave: "Naprave",
      taRacunalnik: "Ta računalnik", domov: "Domača mapa",
      DOCUMENTS: "Dokumenti", PICTURES: "Fotografije", VIDEOS: "Videi", MUSIC: "Glasba", DOWNLOAD: "Prenosi", DESKTOP: "Namizje",
      nalagam: "Nalagam …", praznaMapa: "Mapa je prazna.", niZadetkov: "Ni ustreznih datotek.",
      niNedavnih: "Še ni nedavnih datotek.", niPriljubljenih: "Še nimaš priljubljenih. Desni klik na datoteko ali mapo → Dodaj med priljubljene.",
      niMape: "Mape ni več.", niDovoljenja: "Do te mape nimaš dovoljenja.",
      napravaNeOdgovori: "Naprava trenutno ni dosegljiva. Podatki niso prikazani, da ne bi bili zastareli.",
      napravaNeDeli: "Naprava ne deli datotek. Na njej v Safeer Linku vklopi deljenje datotek.",
      napravaOsvezeno: "osveženo ob {cas}", oddaljeno: "na napravi {naprava}",
      odpri: "Odpri", pokaziVMapi: "Pokaži v mapi", dodajPriljubljeno: "Dodaj med priljubljene",
      odstraniPriljubljeno: "Odstrani iz priljubljenih", predogled: "Predogled", zapri: "Zapri",
      odpiramNaNapravi: "Z naprave predvajam le glasbo in video. Druge datoteke odpri na sami napravi.",
      niUspelo: "Ni uspelo.", strani: "{a}–{b} od {n}", nazaj: "‹", naprej: "›",
      kVse: "Vse", kPisarna: "Pisarna", kUstvarjanje: "Ustvarjanje", kMediji: "Mediji", kSplet: "Splet", kIgre: "Igre",
      kDrugo: "Drugo", kPriljubljeni: "★ Priljubljeni",
      vseNaprave: "Vse naprave", razvrstiIme: "Po imenu", razvrstiNaprava: "Po napravi",
      pogledSeznam: "Seznam / mreža", spletnaAplikacija: "V brskalniku",
      odpriTukaj: "Odpri tukaj (zaslon naprave na tem računalniku)", zazeniNaNapravi: "Zaženi na napravi",
      kategorija: "Kategorija: {k}", popraviKategorijo: "Premakni v kategorijo",
      niNaprav: "Ni povezanih naprav s programi. Napravo dodaš v Safeer Linku (Safeer Control).",
      niProgramov: "V tej kategoriji ni programov.", napravaNedosegljiva: "{naprava}: ni dosegljiva",
      brezControla: "Safeer Link (Safeer Control) ne teče, zato programi naprav niso na voljo.",
      zagonPoslan: "Ukaz poslan napravi {naprava}.",
      skSplet: "Splet", skProgrami: "Programi", skProgramiNaprav: "Programi naprav", skDatoteke: "Datoteke", skMediji: "Mediji",
      isciVSpletu: "Išči »{q}« v spletu", odpreVBrskalniku: "privzeti brskalnik", isciem: "Iščem …",
      prostor: "{n} el.",
      spremeniOzadje: "Spremeni ozadje …", prilagodiDock: "Prilagodi dock …",
      dockNamig: "Program dodaš v dock tako, da ga povlečeš iz menija; odstraniš ga tako, da ga povlečeš ven.",
      linkPovezan: "Safeer Link · {n}", linkPovezanBrez: "Safeer Link · povezano",
      linkPovezi: "Poveži se v Safeer Link", linkNaslov: "Safeer Link: tvoje naprave (odpre Safeer Control)",
      naprav1: "1 naprava", naprav2: "2 napravi", naprav34: "{n} naprave", napravN: "{n} naprav",
      novoNaslov: "Nova mapa ali datoteka", novaMapa: "Nova mapa …", novaDatoteka: "Nova datoteka",
      vPrazna: "Prazna datoteka …", vBesedilo: "Besedilna datoteka …", vDokument: "Dokument …",
      vPreglednica: "Preglednica …", vPredstavitev: "Predstavitev …", vPredloga: "Predloga: {ime} …",
      oknoMapa: "Nova mapa", oknoDatoteka: "Nova datoteka", oknoPreimenuj: "Preimenuj",
      privzetoMapa: "Nova mapa", privzetoDatoteka: "Nova datoteka", privzetoDokument: "Nov dokument",
      privzetoPreglednica: "Nova preglednica", privzetoPredstavitev: "Nova predstavitev",
      novoIme: "Ime", novoVrsta: "Vrsta", novoKje: "Kje", novoSpremeni: "Spremeni …", preklici: "Prekliči",
      ustvari: "Ustvari", preimenuj: "Preimenuj", preimenujMeni: "Preimenuj …", vSmeti: "Premakni v Smeti",
      shraniNaNapravo: "Shrani na drugo napravo …", shrPripravljam: "Pripravljam »{ime}« (preverjam vsebino) …",
      shrPrenasam: "Naprava {naprava} shranjuje »{ime}« … {odst} %", shrKopijaNaslov: "Kopija je shranjena in preverjena",
      shrKopija: "»{ime}« je zdaj tudi na napravi {naprava}, v mapi {kje}. Kopija je preverjena – vsebina je enaka izvirniku.",
      shrVprasaj: "Izbrišem izvirnik na tem računalniku? Sprosti se {velikost}.", shrIzbrisi: "Izbriši izvirnik",
      shrObdrzi: "Obdrži oboje", shrIzbrisano: "Izvirnik je izbrisan. »{ime}« najdeš na napravi {naprava} ({kje}).",
      shrObdrzano: "Obdržano oboje: izvirnik je tu, kopija na napravi {naprava}.",
      shrNiNaprave: "Nobena naprava v Safeer Linku ta trenutek nima dovolj prostora ali ne more pomagati (baterija, zasedenost).",
      shrSpremenjena: "Datoteka se je medtem spremenila – izvirnika ne brišem. Shrani jo znova.",
      shrNapaka: "Shranjevanje na drugo napravo ni uspelo ({koda}).", shrZapri: "Zapri", shrPrenosi: "Prenosi",
      najvecje: "Največje datoteke", niVelikih: "Ni datotek, večjih od 100 MB.",
      maloProstora: "Na računalniku je prostora le še {prosto}. Večje datoteke lahko shraniš na napravo v Safeer Linku – izvirnik izbrišeš šele, ko vidiš, kje je kopija.",
      pokaziNajvecje: "Pokaži največje datoteke",
      vSmetiOk: "»{ime}« je v Smeteh (obnoviš ga v Datotekah → Smeti).", ustvarjeno: "Ustvarjeno: {ime}",
      izberiMapoNaslov: "Kam naj ustvarim?", izberi: "Izberi", osvezi: "Osveži",
      nObstaja: "Datoteka s tem imenom tu že obstaja.", nIme: "Ime ne sme biti prazno, začeti s piko ali vsebovati »/«.",
      nDovoljenje: "V to mapo nimaš dovoljenja za pisanje. Izberi drugo.", nMapa: "Te mape ni več.",
      nSmeti: "V Smeti ni šlo (morda nimaš dovoljenja).", nSplosno: "Ni uspelo."
    },
    en: {
      iskanjePh: "Search the web, apps, files and media …", iskanjeNamig: "Enter = web",
      plosceNaslov: "Panels", medijiNaslov: "Media center", datotekeNaslov: "Files", programiNaslov: "Apps on your devices",
      zamenjajStrani: "Swap left and right", ponastavi: "Default layout", vecjiTekst: "Larger text",
      manjProsojnosti: "Less transparency", skrijPlosco: "Hide panel", spremeniVelikost: "Drag to resize (arrow keys work too)",
      odpriMedijskiCenter: "Open Media center", niPredvajanja: "Nothing playing",
      medijNavodilo: "Pick music or a video in Files or in the Media center.",
      prejsnja: "Previous", premor: "Play / pause", naslednja: "Next",
      predvaja: "Playing", vPremoru: "Paused", ustavljeno: "Stopped", napakaPredvajanja: "Playback failed",
      filterPh: "Filter …", filterPrgPh: "Search apps …", vseVrste: "All types", vrstaDokument: "Documents",
      vrstaSlika: "Pictures", vrstaVideo: "Video", vrstaZvok: "Music", vrstaMapa: "Folders",
      en_mapa: "Folder", en_dokument: "Document", en_slika: "Picture", en_video: "Video", en_zvok: "Audio", en_arhiv: "Archive",
      en_program: "Program", en_splet: "Web", en_drugo: "Other",
      stIme: "Name", stVrsta: "Type", stLokacija: "Location", stVelikost: "Size", stSpremenjeno: "Modified",
      pregled: "Overview", nedavno: "Recent", priljubljeno: "Favourites", mape: "Folders", naprave: "Devices",
      taRacunalnik: "This computer", domov: "Home folder",
      DOCUMENTS: "Documents", PICTURES: "Pictures", VIDEOS: "Videos", MUSIC: "Music", DOWNLOAD: "Downloads", DESKTOP: "Desktop",
      nalagam: "Loading …", praznaMapa: "This folder is empty.", niZadetkov: "No matching files.",
      niNedavnih: "No recent files yet.", niPriljubljenih: "No favourites yet. Right-click a file or folder → Add to favourites.",
      niMape: "The folder no longer exists.", niDovoljenja: "You don't have access to this folder.",
      napravaNeOdgovori: "The device can't be reached right now. Nothing is shown so you never see stale data.",
      napravaNeDeli: "The device doesn't share files. Turn on file sharing for it in Safeer Link.",
      napravaOsvezeno: "refreshed at {cas}", oddaljeno: "on {naprava}",
      odpri: "Open", pokaziVMapi: "Show in folder", dodajPriljubljeno: "Add to favourites",
      odstraniPriljubljeno: "Remove from favourites", predogled: "Preview", zapri: "Close",
      odpiramNaNapravi: "From a device I can only play music and video. Open other files on the device itself.",
      niUspelo: "That didn't work.", strani: "{a}–{b} of {n}", nazaj: "‹", naprej: "›",
      kVse: "All", kPisarna: "Office", kUstvarjanje: "Creative", kMediji: "Media", kSplet: "Web", kIgre: "Games",
      kDrugo: "Other", kPriljubljeni: "★ Favourites",
      vseNaprave: "All devices", razvrstiIme: "By name", razvrstiNaprava: "By device",
      pogledSeznam: "List / grid", spletnaAplikacija: "In the browser",
      odpriTukaj: "Open here (device screen on this computer)", zazeniNaNapravi: "Start on the device",
      kategorija: "Category: {k}", popraviKategorijo: "Move to category",
      niNaprav: "No connected devices with apps. Add a device in Safeer Link (Safeer Control).",
      niProgramov: "No apps in this category.", napravaNedosegljiva: "{naprava}: not reachable",
      brezControla: "Safeer Link (Safeer Control) isn't running, so apps on your devices aren't available.",
      zagonPoslan: "Sent to {naprava}.",
      skSplet: "Web", skProgrami: "Apps", skProgramiNaprav: "Apps on devices", skDatoteke: "Files", skMediji: "Media",
      isciVSpletu: "Search the web for “{q}”", odpreVBrskalniku: "default browser", isciem: "Searching …",
      prostor: "{n} items",
      spremeniOzadje: "Change wallpaper …", prilagodiDock: "Customise dock …",
      dockNamig: "Add an app to the dock by dragging it from the menu; drag it out to remove it.",
      linkPovezan: "Safeer Link · {n}", linkPovezanBrez: "Safeer Link · connected",
      linkPovezi: "Connect to Safeer Link", linkNaslov: "Safeer Link: your devices (opens Safeer Control)",
      naprav1: "1 device", naprav2: "2 devices", naprav34: "{n} devices", napravN: "{n} devices",
      novoNaslov: "New folder or file", novaMapa: "New folder …", novaDatoteka: "New file",
      vPrazna: "Empty file …", vBesedilo: "Text file …", vDokument: "Document …",
      vPreglednica: "Spreadsheet …", vPredstavitev: "Presentation …", vPredloga: "Template: {ime} …",
      oknoMapa: "New folder", oknoDatoteka: "New file", oknoPreimenuj: "Rename",
      privzetoMapa: "New folder", privzetoDatoteka: "New file", privzetoDokument: "New document",
      privzetoPreglednica: "New spreadsheet", privzetoPredstavitev: "New presentation",
      novoIme: "Name", novoVrsta: "Type", novoKje: "Where", novoSpremeni: "Change …", preklici: "Cancel",
      ustvari: "Create", preimenuj: "Rename", preimenujMeni: "Rename …", vSmeti: "Move to Trash",
      shraniNaNapravo: "Store on another device …", shrPripravljam: "Preparing “{ime}” (checking its content) …",
      shrPrenasam: "{naprava} is storing “{ime}” … {odst} %", shrKopijaNaslov: "The copy is stored and verified",
      shrKopija: "“{ime}” is now also on {naprava}, in the folder {kje}. The copy is verified – identical to the original.",
      shrVprasaj: "Delete the original on this computer? This frees {velikost}.", shrIzbrisi: "Delete original",
      shrObdrzi: "Keep both", shrIzbrisano: "The original is deleted. You will find “{ime}” on {naprava} ({kje}).",
      shrObdrzano: "Kept both: the original is here, the copy is on {naprava}.",
      shrNiNaprave: "No device in Safeer Link has enough space right now or can help (battery, busy).",
      shrSpremenjena: "The file changed in the meantime – the original is not deleted. Store it again.",
      shrNapaka: "Storing on another device failed ({koda}).", shrZapri: "Close", shrPrenosi: "Downloads",
      najvecje: "Largest files", niVelikih: "No files larger than 100 MB.",
      maloProstora: "Only {prosto} left on this computer. You can store larger files on a device in Safeer Link – you delete the original only after you see where the copy is.",
      pokaziNajvecje: "Show largest files",
      vSmetiOk: "“{ime}” is in the Trash (restore it from Files → Trash).", ustvarjeno: "Created: {ime}",
      izberiMapoNaslov: "Where should I create it?", izberi: "Select", osvezi: "Refresh",
      nObstaja: "A file with this name already exists here.", nIme: "The name can't be empty, start with a dot or contain “/”.",
      nDovoljenje: "You can't write to this folder. Pick another one.", nMapa: "This folder no longer exists.",
      nSmeti: "Couldn't move it to the Trash (maybe no permission).", nSplosno: "That didn't work."
    }
  };
  var jezik = "sl";
  function t(k, z) {
    var b = (BESEDILA[jezik] && BESEDILA[jezik][k]);
    if (b == null) b = BESEDILA.en[k];
    if (b == null) b = k;
    if (z) Object.keys(z).forEach(function (x) { b = b.split("{" + x + "}").join(z[x]); });
    return b;
  }
  function prevedi() {
    document.documentElement.lang = jezik;
    document.querySelectorAll("[data-t]").forEach(function (e) { e.textContent = t(e.getAttribute("data-t")); });
    document.querySelectorAll("[data-ph]").forEach(function (e) { e.placeholder = t(e.getAttribute("data-ph")); });
    document.querySelectorAll("[data-naslov]").forEach(function (e) {
      e.title = t(e.getAttribute("data-naslov")); e.setAttribute("aria-label", e.title);
    });
  }

  // ------------------------------------------------------------------ nastavitve postavitve
  // Samo udobje enega uporabnika na tem racunalniku (sirina stolpcev, skrite plosce): localStorage.
  var PRIVZETO = { levo: 50, medij: 118, skrite: [], zamenjano: false, vecjiTekst: false, manjProsojnosti: false,
                   pogled: "mreza", priljubljeniPrg: [], kategorije: {}, priljubljeneDat: [] };
  var N = nalozi();
  function nalozi() {
    var n = JSON.parse(JSON.stringify(PRIVZETO));
    try {
      var s = JSON.parse(localStorage.getItem("safeer_delovna") || "{}");
      Object.keys(n).forEach(function (k) { if (s[k] != null && typeof s[k] === typeof n[k]) n[k] = s[k]; });
    } catch (e) { /* zasebni nacin ali pokvarjen zapis: privzeto */ }
    return n;
  }
  function shrani() { try { localStorage.setItem("safeer_delovna", JSON.stringify(N)); } catch (e) { /* ni shrambe */ } }

  function uveljaviPostavitev() {
    var root = document.documentElement.style;
    root.setProperty("--levo", String(Math.max(25, Math.min(75, N.levo))));
    root.setProperty("--medij", Math.max(92, N.medij) + "px");
    document.body.classList.toggle("vecji-tekst", !!N.vecjiTekst);
    document.body.classList.toggle("manj-prosojnosti", !!N.manjProsojnosti);
    ["mediji", "datoteke", "programi"].forEach(function (p) {
      var sk = N.skrite.indexOf(p) >= 0;
      document.querySelector('section[data-plosca="' + p + '"]').hidden = sk;
      var cb = document.querySelector('#meniPlosce input[data-plosca="' + p + '"]');
      if (cb) cb.checked = !sk;
    });
    $("deliMediji").hidden = N.skrite.indexOf("mediji") >= 0 || N.skrite.indexOf("datoteke") >= 0;
    var aPrazen = N.skrite.indexOf("mediji") >= 0 && N.skrite.indexOf("datoteke") >= 0;
    var bPrazen = N.skrite.indexOf("programi") >= 0;
    var p = $("postavitev");
    p.classList.toggle("samo-a", bPrazen && !aPrazen);
    p.classList.toggle("samo-b", aPrazen && !bPrazen);
    p.classList.toggle("zamenjano", !!N.zamenjano);
    if (N.skrite.indexOf("datoteke") >= 0) $("ploscaMediji").style.flex = "1";
    else $("ploscaMediji").style.flex = "";
    $("stikaloTekst").checked = !!N.vecjiTekst;
    $("stikaloProsojnost").checked = !!N.manjProsojnosti;
    requestAnimationFrame(function () { izrisiDatoteke(); izrisiPrograme(); });
  }

  // Delilnika: miska in tipkovnica (puscice). Brez navpicnega pomikanja: velikost se samo razporedi.
  function delilnik(elDeli, navpicno) {
    function premik(dx, dy) {
      if (navpicno) {
        var w = $("postavitev").getBoundingClientRect().width;
        N.levo = Math.max(25, Math.min(75, N.levo + dx / w * 100));
      } else {
        var h = $("stolpecA").getBoundingClientRect().height;
        N.medij = Math.max(92, Math.min(h * 0.6, N.medij + dy));
      }
      uveljaviPostavitev();
    }
    elDeli.addEventListener("pointerdown", function (e) {
      e.preventDefault(); elDeli.setPointerCapture(e.pointerId); elDeli.classList.add("vlecem");
      var x = e.clientX, y = e.clientY;
      function mv(ev) { premik(ev.clientX - x, ev.clientY - y); x = ev.clientX; y = ev.clientY; }
      function up() { elDeli.classList.remove("vlecem"); elDeli.removeEventListener("pointermove", mv); elDeli.removeEventListener("pointerup", up); shrani(); }
      elDeli.addEventListener("pointermove", mv); elDeli.addEventListener("pointerup", up);
    });
    elDeli.addEventListener("keydown", function (e) {
      var k = { ArrowLeft: [-24, 0], ArrowRight: [24, 0], ArrowUp: [0, -16], ArrowDown: [0, 16] }[e.key];
      if (!k) return;
      e.preventDefault(); premik(k[0], k[1]); shrani();
    });
  }

  // Premik plosce: povleci glavo programov na drugo stran (zamenja stolpca).
  function vleciGlavo() {
    document.querySelectorAll(".plosca .glava h2").forEach(function (h) {
      h.setAttribute("draggable", "true");
      h.addEventListener("dragstart", function (e) {
        var pl = h.closest(".plosca"); pl.classList.add("vlecem");
        e.dataTransfer.setData("text/plain", pl.id); e.dataTransfer.effectAllowed = "move";
      });
      h.addEventListener("dragend", function () {
        document.querySelectorAll(".vlecem, .cilj").forEach(function (x) { x.classList.remove("vlecem"); x.classList.remove("cilj"); });
      });
    });
    ["stolpecA", "stolpecB"].forEach(function (id) {
      var s = $(id);
      s.addEventListener("dragover", function (e) { e.preventDefault(); s.classList.add("cilj"); });
      s.addEventListener("dragleave", function () { s.classList.remove("cilj"); });
      s.addEventListener("drop", function (e) {
        e.preventDefault(); s.classList.remove("cilj");
        var iz = document.getElementById(e.dataTransfer.getData("text/plain"));
        if (iz && !s.contains(iz)) { N.zamenjano = !N.zamenjano; shrani(); uveljaviPostavitev(); }
      });
    });
  }

  // ------------------------------------------------------------------ pomozno
  var LOKALE = { sl: "sl-SI", en: "en-GB" };
  function velikost(b) {
    if (!b) return "";
    if (b >= 1073741824) return (b / 1073741824).toFixed(1).replace(".", jezik === "sl" ? "," : ".") + " GB";
    if (b >= 1048576) return (b / 1048576).toFixed(1).replace(".", jezik === "sl" ? "," : ".") + " MB";
    return Math.max(1, Math.round(b / 1024)) + " kB";
  }
  function cas(s) {
    if (!s) return "";
    var d = new Date(s * 1000), zdaj = new Date();
    var o = d.toDateString() === zdaj.toDateString() ? { hour: "2-digit", minute: "2-digit" }
      : d.getFullYear() === zdaj.getFullYear() ? { day: "numeric", month: "numeric" } : { day: "numeric", month: "numeric", year: "2-digit" };
    try { return d.toLocaleString(LOKALE[jezik] || "sl-SI", o); } catch (e) { return d.toISOString().slice(0, 10); }
  }
  var IKONE_VRST = {
    mapa: "M3 7h6l2 2h10v10H3z", slika: "M4 5h16v14H4z M8 14l3-3 5 5 M15 10h.01", video: "M4 6h12v12H4z M16 10l4-2v8l-4-2",
    zvok: "M9 18V6l10-2v12 M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0z", dokument: "M6 3h8l4 4v14H6z M14 3v4h4 M9 12h6 M9 16h6",
    arhiv: "M5 4h14v16H5z M12 4v8", splet: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M3 12h18 M12 3c3 3 3 15 0 18 M12 3c-3 3-3 15 0 18", program: "M4 5h16v14H4z M8 10l3 2-3 2 M13 15h3", drugo: "M6 3h8l4 4v14H6z"
  };
  function ikonaVrste(vrsta) {
    var v = IKONE_VRST[vrsta] ? vrsta : "drugo";
    var s = el("span", "ikona-vrste v-" + v);
    s.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + IKONE_VRST[v] + '"/></svg>';
    return s;
  }
  function vrstaOddaljenega(type) {
    return type === "folder" ? "mapa" : type === "audio" ? "zvok" : type === "video" ? "video" : type === "image" ? "slika" : "drugo";
  }
  // Barvna ploscica s prvo crko za program brez ikone - enako kot na glavni strani Safeer OS (os.js).
  function barva(ime) {
    var h = 0;
    for (var i = 0; i < ime.length; i++) h = (h * 31 + ime.charCodeAt(i)) >>> 0;
    var barve = ["#1f7a5c", "#2d5f9a", "#8a3d7a", "#a4492f", "#5a4aa0", "#2f7f8a", "#8a6d1f", "#3b6e2f"];
    return barve[h % barve.length];
  }
  function crka(ime, razred) {
    var c = el("span", (razred || "") + " crka", (String(ime || "?").trim().charAt(0) || "?").toUpperCase());
    c.style.background = barva(String(ime || "?"));
    c.setAttribute("aria-hidden", "true");
    return c;
  }
  function slikaAliCrka(src, ime, razred) {
    if (!src) return crka(ime, razred);
    var img = el("img", razred || ""); img.alt = ""; img.src = src; img.loading = "lazy";
    img.onerror = function () { img.replaceWith(crka(ime, razred)); };
    return img;
  }
  var casObvestila = 0;
  function obvesti(b) {
    var o = $("obvestilo"); o.textContent = b; o.hidden = false;
    clearTimeout(casObvestila); casObvestila = setTimeout(function () { o.hidden = true; }, 4200);
  }
  function stranskoBesedilo(p) { return p.replace(/^\/home\/[^/]+/, "~"); }

  // ------------------------------------------------------------------ zacetek
  var Z = { mape: [], dom: "", spletne: [] };
  function robovi(r) {
    ["vrh", "dno", "levo", "desno"].forEach(function (k) {
      var v = Math.max(0, Math.min(400, parseInt(r[k], 10) || 0));
      document.documentElement.style.setProperty("--r-" + k, v + "px");
    });
  }
  function zacni() {
    // Gumb + ima samo aria-label: brskalnikov namig (title) bi prekril meni, ki se odpre pod njim.
    var gn = $("gumbNovo"); if (gn) { gn.removeAttribute("data-naslov"); gn.setAttribute("aria-label", t("novoNaslov")); }
    var q = {};
    location.search.replace(/^\?/, "").split("&").forEach(function (d) { var x = d.split("="); if (x[0]) q[x[0]] = x[1]; });
    robovi(q);
    prevedi();
    uveljaviPostavitev();
    delilnik($("deliStolpca"), true);
    delilnik($("deliMediji"), false);
    vleciGlavo();
    vezi();
    if (!most) { document.body.classList.add("brez-mosta"); return; }
    klic("zacetek").then(function (z) {
      z = z || {};
      jezik = BESEDILA[z.jezik] ? z.jezik : "en"; prevedi();
      if (z.ozadje && !document.body.classList.contains("v-oknu")) {
        document.documentElement.style.setProperty("--ozadje-slika", 'url("' + z.ozadje + '")');
      }
      Z.mape = z.mape || []; Z.dom = (Z.mape[0] && Z.mape[0].pot) || "";
      Z.spletne = Array.isArray(z.spletne) ? z.spletne : [];
      zgradiStranDatotek();
      odpriVir({ vrsta: "nedavno" });
      preveriProstor();
      klic("predlogeDatotek").then(function (p) { predlogeDatotek = Array.isArray(p) ? p.slice(0, 12) : []; }).catch(function () {});
      naloziProgrameNaprav();
      medijZanka();
      osveziLink();
    }).catch(function () { zgradiStranDatotek(); });
  }

  // ------------------------------------------------------------------ DATOTEKE
  var D = { vir: null, vse: [], stran: 0, razvrsti: "ime", smer: 1, izbran: -1, naprave: [], zahteva: 0 };

  function zgradiStranDatotek() {
    var s = $("datStran"); s.innerHTML = "";
    function oznaka(b) { s.appendChild(el("p", "oznaka", b)); }
    function gumb(ime, vir, pikaOk) {
      var g = el("button"); g.type = "button";
      if (pikaOk != null) g.appendChild(el("i", "pika" + (pikaOk ? " ok" : "")));
      else g.appendChild(ikonaVrste(vir.vrsta === "naprava" ? "program" : "mapa"));
      g.appendChild(el("span", "napis", ime));
      g._vir = vir;
      g.addEventListener("click", function () { odpriVir(vir); });
      s.appendChild(g);
      return g;
    }
    oznaka(t("pregled"));
    gumb(t("nedavno"), { vrsta: "nedavno" });
    gumb(t("priljubljeno"), { vrsta: "priljubljeno" });
    gumb(t("najvecje"), { vrsta: "najvecje" });
    oznaka(t("mape"));
    Z.mape.forEach(function (m) {
      if (m.vrsta === "HOME") gumb(t("domov"), { vrsta: "lokalno", pot: m.pot });
      else if (["DOCUMENTS", "PICTURES", "VIDEOS", "MUSIC", "DOWNLOAD"].indexOf(m.vrsta) >= 0)
        gumb(BESEDILA[jezik][m.vrsta] ? t(m.vrsta) : m.ime, { vrsta: "lokalno", pot: m.pot });
    });
    oznaka(t("naprave"));
    // Ta racunalnik = cel datotecni sistem (kot »Racunalnik« v Nemu); domaca mapa je zgoraj med Mapami.
    gumb(t("taRacunalnik"), { vrsta: "lokalno", pot: "/" }, true);
    D.naprave.forEach(function (n) { gumb(n.ime, { vrsta: "naprava", id: n.id, ime: n.ime, pot: [] }, true); });
    oznaciVir();
    if (!most) return;
    klic("napraveZDatotekami").then(function (naprave) {
      var prej = JSON.stringify(D.naprave);
      D.naprave = Array.isArray(naprave) ? naprave.filter(function (n) { return n && n.id; }) : [];
      if (JSON.stringify(D.naprave) !== prej) zgradiStranDatotek();
    }).catch(function () {});
  }
  function enakVir(a, b) {
    if (!a || !b || a.vrsta !== b.vrsta) return false;
    if (a.vrsta === "lokalno") return a.pot === b.pot;
    if (a.vrsta === "naprava") return a.id === b.id;
    return true;
  }
  function oznaciVir() {
    document.querySelectorAll("#datStran button").forEach(function (g) {
      var v = g._vir, cur = D.vir;
      var da = cur && (enakVir(v, cur) || (v.vrsta === "lokalno" && cur.vrsta === "lokalno" && cur.koren === v.pot));
      g.setAttribute("aria-current", da ? "true" : "false");
    });
  }

  function odpriVir(vir) {
    D.vir = vir; D.stran = 0; D.izbran = -1; D.vse = [];
    if (vir.vrsta === "lokalno" && !vir.koren) vir.koren = vir.pot;
    oznaciVir();
    datSporocilo(t("nalagam"));
    $("datStanje").textContent = "";
    var st = ++D.zahteva;
    function prispelo(fn) { return function (r) { if (st === D.zahteva) fn(r); }; }
    if (vir.vrsta === "nedavno") {
      klic("nedavne").then(prispelo(function (r) { nastaviVnose(r || [], t("niNedavnih")); drobtine([t("nedavno")]); }))
        .catch(prispelo(function () { nastaviVnose([], t("niUspelo"), true); }));
    } else if (vir.vrsta === "najvecje") {
      // Za skupni prostor: najvecje datoteke v domaci mapi (pregled traja najvec 1,5 s, v ozadju).
      klic("najvecjeDatoteke").then(prispelo(function (r) { nastaviVnose(r || [], t("niVelikih")); drobtine([t("najvecje")]); }))
        .catch(prispelo(function () { nastaviVnose([], t("niUspelo"), true); }));
    } else if (vir.vrsta === "priljubljeno") {
      nastaviVnose(N.priljubljeneDat.slice(), t("niPriljubljenih")); drobtine([t("priljubljeno")]);
    } else if (vir.vrsta === "lokalno") {
      klic("mapa", [vir.pot]).then(prispelo(function (r) {
        r = r || {};
        if (r.napaka) { nastaviVnose([], r.napaka === "ni_dovoljenja" ? t("niDovoljenja") : t("niMape"), true); }
        else { vir.pot = r.pot || vir.pot; nastaviVnose(r.elementi || [], t("praznaMapa")); }
        drobtineLokalno(vir);
      })).catch(prispelo(function () { nastaviVnose([], t("niUspelo"), true); }));
    } else if (vir.vrsta === "naprava") {
      var mapa = vir.pot.length ? vir.pot[vir.pot.length - 1].id : "";
      drobtineNaprava(vir);
      klic("datotekeNaprave", [vir.id, mapa]).then(prispelo(function (r) {
        // Nedosegljiva ali nedeljena naprava: pokazemo stanje, nikoli starih podatkov.
        if (!r || !r.ok) { nastaviVnose([], t("napravaNeOdgovori"), true); $("datStanje").textContent = t("napravaNedosegljiva", { naprava: vir.ime }); return; }
        if (r.shared === false) { nastaviVnose([], t("napravaNeDeli"), true); return; }
        vir.streznik = r.server || ""; vir.kljuc = r.kljuc || "";
        var vnosi = (r.items || []).map(function (v) {
          return { ime: v.name || v.id, id: v.id, oddaljeno: true, naprava: vir.ime, mapa: v.type === "folder",
                   vrsta: vrstaOddaljenega(v.type), velikost: v.size || 0, spremenjeno: v.modified || v.mtime || 0, izvirnik: v };
        });
        nastaviVnose(vnosi, t("praznaMapa"));
        $("datStanje").textContent = t("napravaOsvezeno", { cas: cas(Date.now() / 1000) });
      })).catch(prispelo(function () { nastaviVnose([], t("napravaNeOdgovori"), true); }));
    }
  }
  function drobtine(deli) {
    var ol = $("drobtine"); ol.innerHTML = "";
    deli.forEach(function (d) {
      var li = el("li");
      if (typeof d === "string") li.textContent = d;
      else { var b = el("button", "", d.ime); b.type = "button"; b.addEventListener("click", d.klik); li.appendChild(b); }
      ol.appendChild(li);
    });
  }
  function drobtineLokalno(vir) {
    var koren = vir.koren || vir.pot, deli = [];
    var imeKorena = (Z.mape.filter(function (m) { return m.pot === koren; })[0] || {});
    var imeK = koren === "/" ? t("taRacunalnik") : imeKorena.vrsta === "HOME" ? t("domov")
      : (BESEDILA[jezik][imeKorena.vrsta] ? t(imeKorena.vrsta) : (koren.split("/").pop() || "/"));
    deli.push({ ime: imeK, klik: function () { odpriVir({ vrsta: "lokalno", pot: koren, koren: koren }); } });
    if (vir.pot.indexOf(koren) === 0 && vir.pot !== koren) {
      var pot = koren;
      vir.pot.slice(koren.length).split("/").filter(Boolean).forEach(function (del) {
        pot = pot.replace(/\/$/, "") + "/" + del;
        var p = pot;
        deli.push({ ime: del, klik: function () { odpriVir({ vrsta: "lokalno", pot: p, koren: koren }); } });
      });
    }
    var zadnji = deli.pop(); deli.push(zadnji.ime);
    drobtine(deli);
  }
  function drobtineNaprava(vir) {
    var deli = [{ ime: vir.ime, klik: function () { vir.pot = []; odpriVir(vir); } }];
    vir.pot.forEach(function (p, i) {
      deli.push({ ime: p.ime, klik: function () { vir.pot = vir.pot.slice(0, i + 1); odpriVir(vir); } });
    });
    var zadnji = deli.pop(); deli.push(zadnji.ime);
    drobtine(deli);
  }
  function datSporocilo(b, napaka) {
    var s = $("datSporocilo"); s.textContent = b || ""; s.hidden = !b; s.classList.toggle("napaka", !!napaka);
  }
  var prazenOpis = "";
  function nastaviVnose(vnosi, praznoBesedilo, napaka) {
    D.vse = vnosi; prazenOpis = praznoBesedilo; D.napaka = !!napaka;
    if (napaka) datSporocilo(praznoBesedilo, true); else datSporocilo("");
    izrisiDatoteke();
  }
  function filtrirani() {
    var q = ($("datFilter").value || "").trim().toLowerCase(), v = $("datVrsta").value;
    var r = D.vse.filter(function (e) {
      if (q && String(e.ime).toLowerCase().indexOf(q) < 0) return false;
      if (v && (v === "mapa" ? !e.mapa : e.vrsta !== v)) return false;
      return true;
    });
    if (D.vir && D.vir.vrsta === "nedavno" && D.razvrsti === "ime" && D.smer === 1 && !D.rocno) return r; // nedavne: po casu
    if (D.vir && D.vir.vrsta === "najvecje" && !D.rocno) return r; // najvecje: ze urejene po velikosti
    var k = D.razvrsti, s = D.smer;
    return r.sort(function (a, b) {
      if (a.mapa !== b.mapa) return a.mapa ? -1 : 1;
      var x = a[k], y = b[k];
      if (typeof x === "string") return x.localeCompare(y, jezik, { sensitivity: "base", numeric: true }) * s;
      return ((x || 0) - (y || 0)) * s;
    });
  }
  // Koliko vrstic gre v ploščo brez pomikanja.
  function vrsticNaStran() {
    var tb = $("datSeznam"), gl = document.querySelector(".dat-glavno");
    if (!gl || !gl.offsetParent) return 10;
    var vis = gl.getBoundingClientRect().height - document.querySelector(".dat-orodja").getBoundingClientRect().height
      - tb.tHead.getBoundingClientRect().height - $("datStrani").getBoundingClientRect().height - 8;
    var vzorec = tb.tBodies[0].rows[0];
    var h = vzorec ? vzorec.getBoundingClientRect().height : parseFloat(getComputedStyle(document.body).fontSize) * 2.05;
    return Math.max(1, Math.floor(vis / Math.max(h, 18)));
  }
  function izrisiDatoteke() {
    var tb = $("datVrstice");
    if (!tb) return;
    var seznam = filtrirani();
    tb.innerHTML = "";
    // en vzorcni red za meritev visine
    if (seznam.length) tb.appendChild(vrsticaDatoteke(seznam[0], 0));
    var naStran = vrsticNaStran();
    tb.innerHTML = "";
    var strani = Math.max(1, Math.ceil(seznam.length / naStran));
    var oznaci = -1;
    if (D.oznaci) {
      // Pravkar ustvarjen ali preimenovan vnos: pokazemo stran, kjer je, in ga oznacimo.
      for (var oi = 0; oi < seznam.length; oi++) if (seznam[oi].ime === D.oznaci) { oznaci = oi; break; }
      if (oznaci >= 0) { D.stran = Math.floor(oznaci / naStran); D.izbran = oznaci % naStran; }
      D.oznaci = "";
    }
    D.stran = Math.min(D.stran, strani - 1);
    var od = D.stran * naStran, do_ = Math.min(seznam.length, od + naStran);
    D.vidni = seznam.slice(od, do_);
    D.vidni.forEach(function (e, i) {
      var vr = vrsticaDatoteke(e, i);
      if (oznaci >= 0 && i === D.izbran) { vr.classList.add("novo"); setTimeout(function () { try { vr.focus(); } catch (x) {} }, 0); }
      tb.appendChild(vr);
    });
    if (!seznam.length && !D.napaka && D.vse !== null) datSporocilo(D.vse.length ? t("niZadetkov") : prazenOpis);
    else if (!D.napaka) datSporocilo("");
    ostraniStrani($("datStrani"), od, do_, seznam.length, strani, D.stran, function (s) { D.stran = s; D.izbran = -1; izrisiDatoteke(); });
    document.querySelectorAll("#datSeznam th button").forEach(function (b) {
      if (b.getAttribute("data-razvrsti") === D.razvrsti && D.rocno) b.setAttribute("data-smer", D.smer > 0 ? "▲" : "▼");
      else b.removeAttribute("data-smer");
    });
  }
  function vrsticaDatoteke(e, i) {
    var tr = el("tr"); tr.tabIndex = 0; tr.setAttribute("aria-selected", i === D.izbran ? "true" : "false");
    var td = el("td"), c = el("div", "celica-ime");
    c.appendChild(ikonaVrste(e.mapa ? "mapa" : e.vrsta)); c.appendChild(el("span", "", e.ime));
    td.appendChild(c); td.title = e.ime; tr.appendChild(td);
    tr.appendChild(el("td", "st-vrsta", t("en_" + (e.mapa ? "mapa" : (IKONE_VRST[e.vrsta] ? e.vrsta : "drugo")))));
    var lok = el("td", "st-lok");
    if (e.oddaljeno) { var o = el("span", "oznaka-vira oddaljeno", e.naprava); lok.appendChild(o); }
    else lok.textContent = e.pot ? stranskoBesedilo(e.pot.replace(/\/[^/]*$/, "")) : "";
    tr.appendChild(lok);
    tr.appendChild(el("td", "st-vel", e.mapa ? "" : velikost(e.velikost)));
    tr.appendChild(el("td", "st-cas", cas(e.spremenjeno)));
    tr.addEventListener("click", function () { D.izbran = i; oznaciIzbrano(); });
    tr.addEventListener("dblclick", function () { odpriVnos(e); });
    tr.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") { ev.preventDefault(); odpriVnos(e); }
      else if (ev.key === " ") { ev.preventDefault(); predogled(e); }
      else if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault();
        var n = i + (ev.key === "ArrowDown" ? 1 : -1), vr = $("datVrstice").rows;
        if (n >= 0 && n < vr.length) { D.izbran = n; vr[n].focus(); oznaciIzbrano(); }
      } else if (ev.key === "ContextMenu" || (ev.shiftKey && ev.key === "F10")) {
        ev.preventDefault(); var r = tr.getBoundingClientRect(); meniDatoteke(e, r.left + 40, r.bottom);
      } else if (ev.key === "Backspace") { ev.preventDefault(); gorVMapo(); }
      else if (ev.key === "F2" && !e.oddaljeno) { ev.preventDefault(); odpriOknoNovo({ nacin: "preimenuj", pot: e.pot, ime: e.ime, mapa: e.mapa }); }
      else if (ev.key === "Delete" && !e.oddaljeno) { ev.preventDefault(); vSmeti(e); }
    });
    tr.addEventListener("contextmenu", function (ev) { ev.preventDefault(); D.izbran = i; oznaciIzbrano(); meniDatoteke(e, ev.clientX, ev.clientY); });
    return tr;
  }
  function oznaciIzbrano() {
    Array.prototype.forEach.call($("datVrstice").rows, function (r, j) { r.setAttribute("aria-selected", j === D.izbran ? "true" : "false"); });
  }
  function gorVMapo() {
    var v = D.vir; if (!v) return;
    if (v.vrsta === "lokalno" && v.pot !== v.koren) odpriVir({ vrsta: "lokalno", pot: v.pot.replace(/\/[^/]+\/?$/, "") || "/", koren: v.koren });
    else if (v.vrsta === "naprava" && v.pot.length) { v.pot.pop(); odpriVir(v); }
  }
  function odpriVnos(e) {
    if (e.oddaljeno) {
      var v = D.vir;
      if (e.mapa) { v.pot.push({ id: e.id, ime: e.ime }); odpriVir(v); return; }
      if (e.vrsta !== "zvok" && e.vrsta !== "video") { obvesti(t("odpiramNaNapravi")); return; }
      if (!v.streznik) { obvesti(t("napravaNeOdgovori")); return; }
      var predvajljivi = D.vse.filter(function (x) { return !x.mapa && (x.vrsta === "zvok" || x.vrsta === "video"); });
      var seznam = predvajljivi.map(function (x) { return x.izvirnik; });
      klic("predvajajZNaprave", [v.streznik, v.kljuc, seznam, predvajljivi.indexOf(e), v.ime]).then(function (ok) {
        if (!ok) obvesti(t("niUspelo")); else medijOsvezi();
      }).catch(function () { obvesti(t("niUspelo")); });
      return;
    }
    if (e.mapa) { odpriVir({ vrsta: "lokalno", pot: e.pot, koren: D.vir && D.vir.vrsta === "lokalno" ? D.vir.koren : e.pot }); return; }
    var poskus = (e.vrsta === "zvok" || e.vrsta === "video") ? klic("odpriLokalniMedij", [e.pot]) : Promise.resolve(false);
    poskus.then(function (ok) {
      if (ok) { medijOsvezi(); return; }
      return klic("odpriDatoteko", [e.pot]).then(function (ok2) { if (!ok2) obvesti(t("niUspelo")); });
    }).catch(function () { obvesti(t("niUspelo")); });
  }
  function jePriljubljena(e) { return N.priljubljeneDat.some(function (p) { return p.pot === e.pot; }); }
  function meniDatoteke(e, x, y) {
    var m = [];
    m.push([t("odpri"), function () { odpriVnos(e); }]);
    if (!e.oddaljeno) {
      m.push([t("predogled"), function () { predogled(e); }, e.mapa]);
      m.push([t("pokaziVMapi"), function () { klic("pokaziVMapi", [e.pot]); }]);
      m.push(jePriljubljena(e)
        ? [t("odstraniPriljubljeno"), function () {
            N.priljubljeneDat = N.priljubljeneDat.filter(function (p) { return p.pot !== e.pot; }); shrani();
            if (D.vir && D.vir.vrsta === "priljubljeno") odpriVir(D.vir);
          }]
        : [t("dodajPriljubljeno"), function () {
            N.priljubljeneDat.push({ ime: e.ime, pot: e.pot, mapa: !!e.mapa, vrsta: e.mapa ? "mapa" : e.vrsta,
                                     velikost: e.velikost || 0, spremenjeno: e.spremenjeno || 0 });
            N.priljubljeneDat = N.priljubljeneDat.slice(-60); shrani();
          }]);
      m.push(["—"]);
      m.push([t("preimenujMeni"), function () { odpriOknoNovo({ nacin: "preimenuj", pot: e.pot, ime: e.ime, mapa: e.mapa }); }]);
      m.push([t("vSmeti"), function () { vSmeti(e); }]);
      if (!e.mapa) m.push([t("shraniNaNapravo"), function () { shraniNaNapravo(e); }]);
      m.push(["—"]);
      postavkeNovo(m, e.mapa ? e.pot : null);
    }
    pokaziMeni(m, x, y);
  }

  // ------------------------------------------------------------------ NOVA MAPA / DATOTEKA
  var VRSTE_NOVIH = [["prazna", "vPrazna", "privzetoDatoteka"], ["besedilo", "vBesedilo", "privzetoDatoteka"],
                     ["dokument", "vDokument", "privzetoDokument"], ["preglednica", "vPreglednica", "privzetoPreglednica"],
                     ["predstavitev", "vPredstavitev", "privzetoPredstavitev"]];
  var predlogeDatotek = [];
  /** Privzeto mesto za novo: odprta krajevna mapa, sicer domaca mapa (Nedavno, Priljubljeno, naprava). */
  function kamNovo() {
    var v = D.vir;
    if (v && v.vrsta === "lokalno" && v.pot) return v.pot;
    return Z.dom || "~";
  }
  function postavkeNovo(m, vMapo) {
    var kam = vMapo || kamNovo();
    m.push([t("novaMapa"), function () { odpriOknoNovo({ nacin: "mapa", kam: kam }); }]);
    m.push(["—"]);
    VRSTE_NOVIH.forEach(function (v) {
      m.push([t(v[1]), function () { odpriOknoNovo({ nacin: "datoteka", vrsta: v[0], kam: kam }); }]);
    });
    predlogeDatotek.forEach(function (p) {
      m.push([t("vPredloga", { ime: p.ime }), function () { odpriOknoNovo({ nacin: "datoteka", vrsta: "predloga", predloga: p.pot, ime: p.ime, kam: kam }); }]);
    });
  }
  function meniNovo(x, y) {
    var m = [];
    postavkeNovo(m, null);
    m.push(["—"]);
    m.push([t("osvezi"), function () { if (D.vir) odpriVir(D.vir); }]);
    pokaziMeni(m, x, y);
  }
  var NO = { nastavitve: null };
  function napakaNovo(koda) {
    return t({ obstaja: "nObstaja", napacno_ime: "nIme", ni_dovoljenja: "nDovoljenje", ni_dovoljeno: "nDovoljenje",
               ni_mape: "nMapa" }[koda] || "nSplosno");
  }
  function odpriOknoNovo(o) {
    NO.nastavitve = o;
    zapriMeni();
    var preimenuj = o.nacin === "preimenuj";
    $("novoNaslovOkna").textContent = t(preimenuj ? "oknoPreimenuj" : o.nacin === "mapa" ? "oknoMapa" : "oknoDatoteka");
    $("novoPotrdi").textContent = t(preimenuj ? "preimenuj" : "ustvari");
    $("novoKjeVrsta").hidden = preimenuj;
    $("novoVrstaVrsta").hidden = o.nacin !== "datoteka";
    var s = $("novoVrsta"); s.innerHTML = "";
    if (o.nacin === "datoteka") {
      VRSTE_NOVIH.forEach(function (v) { var op = el("option", "", t(v[1]).replace(/ \u2026$/, "")); op.value = v[0]; s.appendChild(op); });
      predlogeDatotek.forEach(function (p) { var op = el("option", "", t("vPredloga", { ime: p.ime }).replace(/ \u2026$/, "")); op.value = "predloga:" + p.pot; s.appendChild(op); });
      s.value = o.vrsta === "predloga" ? "predloga:" + o.predloga : (o.vrsta || "prazna");
    }
    var ime = preimenuj ? o.ime : o.nacin === "mapa" ? t("privzetoMapa")
      : o.vrsta === "predloga" ? o.ime : t((VRSTE_NOVIH.filter(function (v) { return v[0] === o.vrsta; })[0] || VRSTE_NOVIH[0])[2]);
    var polje = $("novoIme"); polje.value = ime;
    nastaviKje(o.kam);
    $("novoNapaka").hidden = true;
    $("oknoNovo").hidden = false;
    setTimeout(function () {
      polje.focus();
      // Kot v Nemu: oznaceno je ime brez koncnice, da ga uporabnik takoj prepise.
      var konec = preimenuj && !o.mapa && ime.lastIndexOf(".") > 0 ? ime.lastIndexOf(".") : ime.length;
      polje.setSelectionRange(0, konec);
    }, 0);
  }
  function nastaviKje(pot) {
    NO.kam = pot;
    var dom = (Z.dom || "").replace(/\/$/, "");
    $("novoKje").textContent = !pot || pot === "~" || pot.replace(/\/$/, "") === dom ? t("domov")
      : dom && pot.indexOf(dom + "/") === 0 ? t("domov") + " \u203a " + pot.slice(dom.length + 1).split("/").join(" \u203a ")
      : pot;
    $("novoKje").title = pot || "";
  }
  function zapriOknoNovo() { $("oknoNovo").hidden = true; NO.nastavitve = null; }
  function potrdiNovo() {
    var o = NO.nastavitve; if (!o) return;
    var ime = $("novoIme").value.trim();
    var obljuba;
    if (o.nacin === "preimenuj") obljuba = klic("preimenujDatoteko", [o.pot, ime]);
    else if (o.nacin === "mapa") obljuba = klic("novaMapa", [NO.kam, ime]);
    else {
      var v = $("novoVrsta").value;
      obljuba = v.indexOf("predloga:") === 0 ? klic("novaDatoteka", [NO.kam, ime, "prazna", v.slice(9)])
        : klic("novaDatoteka", [NO.kam, ime, v, ""]);
    }
    $("novoPotrdi").disabled = true;
    obljuba.then(function (r) {
      $("novoPotrdi").disabled = false;
      if (!r || !r.ok) { var n = $("novoNapaka"); n.textContent = napakaNovo(r && r.napaka); n.hidden = false; $("novoIme").focus(); return; }
      zapriOknoNovo();
      var nova = r.pot || "", mapa = nova.replace(/\/[^/]*$/, "") || "/", imeNovega = nova.split("/").pop();
      if (o.nacin !== "preimenuj") obvesti(t("ustvarjeno", { ime: imeNovega }));
      // Pokazemo mapo, kjer je nastalo, in vnos oznacimo (koren ohranimo, ce je mapa v njem).
      var koren = D.vir && D.vir.vrsta === "lokalno" && D.vir.koren && (mapa + "/").indexOf(D.vir.koren.replace(/\/$/, "") + "/") === 0
        ? D.vir.koren : mapa;
      D.oznaci = imeNovega;
      odpriVir({ vrsta: "lokalno", pot: mapa, koren: koren });
    }).catch(function () { $("novoPotrdi").disabled = false; var n = $("novoNapaka"); n.textContent = t("nSplosno"); n.hidden = false; });
  }
  // ------------------------------------------------------------------ SKUPNI PROSTOR (zakon solidarnosti)
  /** Ko racunalniku zmanjkuje prostora, Datoteke same ponudijo shranjevanje na napravo v Linku. */
  var opozoriloProstora = null;
  function preveriProstor() {
    klic("prostorDiska").then(function (p) {
      if (opozoriloProstora) { opozoriloProstora.remove(); opozoriloProstora = null; }
      if (!p || !p.malo) return;
      var o = el("div", "dat-opozorilo"); o.setAttribute("role", "status"); opozoriloProstora = o;
      o.style.cssText = "display:flex;gap:.8em;align-items:center;padding:.55em .8em;margin-bottom:.45em;border-radius:10px;background:rgba(255,190,90,.14);border:1px solid rgba(255,190,90,.45)";
      var b = el("span", "", t("maloProstora", { prosto: velikost(p.prosto) })); b.style.flex = "1";
      var g = el("button", "", t("pokaziNajvecje")); g.type = "button";
      g.addEventListener("click", function () { odpriVir({ vrsta: "najvecje" }); });
      o.appendChild(b); o.appendChild(g);
      var glavno = document.querySelector(".dat-glavno"); if (glavno) glavno.insertBefore(o, glavno.firstChild);
    }).catch(function () {});
  }

  // Datoteko shrani naprava v Safeer Linku z najvec prostora. Izvirnik izbrise sele uporabnik,
  // ko vidi, na kateri napravi in v kateri mapi je preverjena kopija.
  function shraniNaNapravo(e) {
    var ovoj = el("div", "meni"); ovoj.setAttribute("role", "dialog");
    ovoj.style.cssText = "position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);max-width:34em;padding:1em 1.2em";
    var naslov = el("p", "meni-naslov", t("shraniNaNapravo").replace(/\s\u2026$/, ""));
    var besedilo = el("p", "", t("shrPripravljam", { ime: e.ime })); besedilo.style.cssText = "margin:.6em 0";
    var vprasanje = el("p", ""); vprasanje.style.cssText = "margin:.6em 0;font-weight:600"; vprasanje.hidden = true;
    var gumbi = el("div", ""); gumbi.style.cssText = "display:flex;gap:.6em;justify-content:flex-end;margin-top:.8em";
    var gZapri = el("button", "", t("shrZapri")); gZapri.type = "button";
    gZapri.addEventListener("click", zapri); gumbi.appendChild(gZapri);
    [naslov, besedilo, vprasanje, gumbi].forEach(function (x) { ovoj.appendChild(x); });
    document.body.appendChild(ovoj);
    var id = null, casovnik = 0;
    function zapri() { clearTimeout(casovnik); ovoj.remove(); }
    function zamenjajGumbe(seznam) { gumbi.innerHTML = ""; seznam.forEach(function (g) { gumbi.appendChild(g); }); }
    function koncaj(sporocilo) { besedilo.textContent = sporocilo; vprasanje.hidden = true; zamenjajGumbe([gZapri]); }
    function napaka(r) {
      var k = (r && (r.napaka || r.koda)) || "napaka";
      koncaj(k === "ni_naprave" ? t("shrNiNaprave") : k === "spremenjena" ? t("shrSpremenjena") : t("shrNapaka", { koda: k }));
    }
    function pokazi(r) {
      // Android pove pot kot "Download/Safeer Shramba/ime": uporabnik pozna mapo Prenosi.
      var kje = (r.kje || "").replace(/^Download\//, t("shrPrenosi") + " › ").replace(/\//g, " › ");
      var z = { ime: r.ime, naprava: r.naprava || "", kje: kje, velikost: velikost(r.velikost),
                odst: r.velikost ? Math.floor(100 * (r.preneseno || 0) / r.velikost) : 0 };
      if (r.stanje === "pripravljam") { besedilo.textContent = t("shrPripravljam", z); }
      else if (r.stanje === "prenasam") { besedilo.textContent = t("shrPrenasam", z); }
      else if (r.stanje === "kopija") {
        naslov.textContent = t("shrKopijaNaslov");
        besedilo.textContent = t("shrKopija", z);
        vprasanje.textContent = t("shrVprasaj", z); vprasanje.hidden = false;
        var gIzbrisi = el("button", "", t("shrIzbrisi")); gIzbrisi.type = "button";
        var gObdrzi = el("button", "", t("shrObdrzi")); gObdrzi.type = "button";
        gIzbrisi.addEventListener("click", function () {
          gIzbrisi.disabled = true;
          klic("shrambaIzbrisi", [id]).then(function (x) {
            if (!x || !x.ok) { napaka(x); return; }
            koncaj(t("shrIzbrisano", z));
            if (D.vir) odpriVir(D.vir);
            preveriProstor();
          }).catch(function () { napaka(null); });
        });
        gObdrzi.addEventListener("click", function () {
          klic("shrambaObdrzi", [id]).then(function () { koncaj(t("shrObdrzano", z)); }).catch(function () { napaka(null); });
        });
        zamenjajGumbe([gObdrzi, gIzbrisi]);
        try { gObdrzi.focus(); } catch (x) {}
        return;
      }
      else if (r.stanje === "napaka") { napaka(r); return; }
      casovnik = setTimeout(osvezi, 1500);
    }
    function osvezi() {
      klic("shrambaStanje", [id]).then(function (r) { if (r && r.ok) pokazi(r); else napaka(r); }).catch(function () { napaka(null); });
    }
    klic("shraniNaNapravo", [e.pot]).then(function (r) {
      if (!r || !r.ok) { napaka(r); return; }
      id = r.id; pokazi(r);
    }).catch(function () { napaka(null); });
  }

  function vSmeti(e) {
    klic("vSmeti", [e.pot]).then(function (r) {
      if (!r || !r.ok) { obvesti(t("nSmeti")); return; }
      N.priljubljeneDat = N.priljubljeneDat.filter(function (p) { return p.pot !== e.pot; }); shrani();
      obvesti(t("vSmetiOk", { ime: e.ime }));
      if (D.vir) odpriVir(D.vir);
    }).catch(function () { obvesti(t("nSmeti")); });
  }
  function predogled(e) {
    if (!e || e.oddaljeno || e.mapa) return;
    var ovoj = el("div", "meni"); ovoj.setAttribute("role", "dialog");
    ovoj.style.cssText = "position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);max-width:70vw;max-height:80vh;overflow:hidden;padding:1em";
    ovoj.appendChild(el("p", "meni-naslov", e.ime));
    if (e.vrsta === "slika") {
      var img = el("img"); img.alt = e.ime; img.src = "file://" + encodeURI(e.pot);
      img.style.cssText = "max-width:66vw;max-height:60vh;display:block;border-radius:10px;margin:.3em auto";
      ovoj.appendChild(img);
    }
    var p = el("p", "", [stranskoBesedilo(e.pot), velikost(e.velikost), cas(e.spremenjeno)].filter(Boolean).join(" · "));
    p.style.cssText = "color:var(--tiho);margin:.5em .5em"; ovoj.appendChild(p);
    var g1 = el("button", "", t("odpri")); g1.type = "button"; g1.addEventListener("click", function () { zapri(); odpriVnos(e); });
    var g2 = el("button", "", t("zapri")); g2.type = "button"; g2.addEventListener("click", zapri);
    ovoj.appendChild(g1); ovoj.appendChild(g2);
    function zapri() { ovoj.remove(); document.removeEventListener("keydown", esc, true); }
    function esc(ev) { if (ev.key === "Escape" || ev.key === " ") { ev.preventDefault(); zapri(); } }
    document.addEventListener("keydown", esc, true);
    document.body.appendChild(ovoj); g1.focus();
  }

  function ostraniStrani(ovoj, od, do_, n, strani, trenutna, pojdi) {
    ovoj.innerHTML = "";
    if (n <= 0) return;
    ovoj.appendChild(el("span", "", t("strani", { a: od + 1, b: do_, n: n })));
    if (strani <= 1) return;
    var n1 = el("button", "", t("nazaj")); n1.type = "button"; n1.disabled = trenutna <= 0; n1.setAttribute("aria-label", "Prejšnja stran");
    var n2 = el("button", "", t("naprej")); n2.type = "button"; n2.disabled = trenutna >= strani - 1; n2.setAttribute("aria-label", "Naslednja stran");
    n1.addEventListener("click", function () { pojdi(trenutna - 1); });
    n2.addEventListener("click", function () { pojdi(trenutna + 1); });
    ovoj.appendChild(n1); ovoj.appendChild(n2);
  }

  // ------------------------------------------------------------------ PROGRAMI NAPRAV
  var P = { naprave: [], programi: [], nedosegljive: [], kategorija: "vse", stran: 0, brezControla: false, nalozeno: false };
  var KATEGORIJE = ["vse", "priljubljeni", "pisarna", "ustvarjanje", "mediji", "splet", "igre", "drugo"];
  var IMENA_KATEGORIJ = { vse: "kVse", priljubljeni: "kPriljubljeni", pisarna: "kPisarna", ustvarjanje: "kUstvarjanje",
                          mediji: "kMediji", splet: "kSplet", igre: "kIgre", drugo: "kDrugo" };
  // Skupine iz metapodatkov (core/os_programi, Android paketi) -> kategorije kataloga; uporabnik lahko popravi.
  var IZ_SKUPINE = { pisarna: "pisarna", ucenje: "pisarna", programiranje: "ustvarjanje", predstavnost: "mediji",
                     splet: "splet", igre: "igre", orodja: "drugo", sistem: "drugo", drugo: "drugo" };
  function kljucPrograma(p) { return p.naprava + ":" + p.id; }
  function kategorijaPrograma(p) { return N.kategorije[kljucPrograma(p)] || IZ_SKUPINE[p.skupina] || "drugo"; }

  function naloziProgrameNaprav() {
    klic("napraveSProgrami").then(function (naprave) {
      P.naprave = Array.isArray(naprave) ? naprave.filter(function (n) { return n && n.id; }) : [];
      P.brezControla = false;
      zgradiIzbiroNaprav();
      var obljube = P.naprave.map(function (n) {
        return klic("programiNaprave", [n.id]).then(function (r) { return { n: n, r: r }; })
          .catch(function () { return { n: n, r: null }; });
      });
      return Promise.all(obljube);
    }).then(function (izidi) {
      var vsi = [], ned = [];
      (izidi || []).forEach(function (x) {
        if (x.r && x.r.ok) x.r.programi.forEach(function (p) { p.imeNaprave = x.n.ime; p.platforma = x.n.platforma; vsi.push(p); });
        else { ned.push(x.n.ime); if (x.r && x.r.koda === "ni_controla") P.brezControla = true; }
      });
      // Spletne aplikacije, ki jih je uporabnik sam shranil v Safeer OS (potrjene bliznjice).
      Z.spletne.forEach(function (s, i) {
        if (!s || !s.url) return;
        vsi.push({ id: "splet:" + i, ime: s.ime || s.url, naprava: "splet", imeNaprave: t("spletnaAplikacija"), skupina: "splet",
                   ikona: s.ikona && /^(data:image\/|https:)/.test(s.ikona) ? s.ikona : "", url: s.url });
      });
      P.programi = vsi; P.nedosegljive = ned; P.nalozeno = true;
      izrisiPrograme();
      izrisiLink();
      ponoviCeTreba();
    }).catch(function () {
      P.brezControla = true; P.nalozeno = true; P.programi = []; izrisiPrograme();
      ponoviCeTreba();
    });
  }
  // Ob prijavi se Safeer Control (Link) lahko zazene sele za delovno povrsino: dokler ni naprav ali
  // Controla, poskusimo znova (8 s, najvec 8-krat); ko se odzove, osvezimo tudi naprave v Datotekah.
  var poskusiNaprav = 0, casPoskusa = 0;
  function ponoviCeTreba() {
    clearTimeout(casPoskusa);
    if (!(P.brezControla || !P.naprave.length) || poskusiNaprav >= 8) return;
    poskusiNaprav++;
    casPoskusa = setTimeout(function () { zgradiStranDatotek(); naloziProgrameNaprav(); }, 8000);
  }
  function zgradiIzbiroNaprav() {
    var s = $("prgNaprava"), prej = s.value; s.innerHTML = "";
    var o = el("option", "", t("vseNaprave")); o.value = ""; s.appendChild(o);
    P.naprave.forEach(function (n) { var x = el("option", "", n.ime); x.value = n.id; s.appendChild(x); });
    if (Z.spletne.length) { var w = el("option", "", t("spletnaAplikacija")); w.value = "splet"; s.appendChild(w); }
    s.value = prej;
  }
  function zgradiKategorije() {
    var z = $("prgKategorije"); z.innerHTML = "";
    KATEGORIJE.forEach(function (k) {
      if (k === "priljubljeni" && !N.priljubljeniPrg.length) return;
      var b = el("button", "", t(IMENA_KATEGORIJ[k])); b.type = "button"; b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", P.kategorija === k ? "true" : "false");
      b.addEventListener("click", function () { P.kategorija = k; P.stran = 0; izrisiPrograme(); });
      z.appendChild(b);
    });
  }
  function programiFiltrirani() {
    var q = ($("prgFilter").value || "").trim().toLowerCase(), nap = $("prgNaprava").value, k = P.kategorija;
    var r = P.programi.filter(function (p) {
      if (nap && p.naprava !== nap) return false;
      if (k === "priljubljeni" && N.priljubljeniPrg.indexOf(kljucPrograma(p)) < 0) return false;
      if (k !== "vse" && k !== "priljubljeni" && kategorijaPrograma(p) !== k) return false;
      if (q && (p.ime + " " + (p.opis || "")).toLowerCase().indexOf(q) < 0) return false;
      return true;
    });
    var po = $("prgRazvrsti").value;
    r.sort(function (a, b) {
      var fa = N.priljubljeniPrg.indexOf(kljucPrograma(a)) >= 0, fb = N.priljubljeniPrg.indexOf(kljucPrograma(b)) >= 0;
      if (fa !== fb) return fa ? -1 : 1;
      if (po === "naprava" && a.imeNaprave !== b.imeNaprave) return a.imeNaprave.localeCompare(b.imeNaprave, jezik);
      return a.ime.localeCompare(b.ime, jezik, { sensitivity: "base" });
    });
    return r;
  }
  function izrisiPrograme() {
    var mreza = $("prgMreza");
    if (!mreza) return;
    zgradiKategorije();
    var seznamPogled = N.pogled === "seznam";
    mreza.classList.toggle("seznam-pogled", seznamPogled);
    $("ikonaPogled").setAttribute("d", seznamPogled ? "M4 4h7v7H4z M13 4h7v7h-7z M4 13h7v7H4z M13 13h7v7h-7z" : "M4 6h16 M4 12h16 M4 18h16");
    var sp = $("prgSporocilo");
    var sporocila = [];
    if (!P.nalozeno) sporocila.push(t("nalagam"));
    else if (P.brezControla) sporocila.push(t("brezControla"));
    else if (!P.naprave.length) sporocila.push(t("niNaprav"));
    P.nedosegljive.forEach(function (n) { sporocila.push(t("napravaNedosegljiva", { naprava: n })); });
    // Zmogljivost mreze brez pomikanja
    var r = mreza.getBoundingClientRect(), fs = parseFloat(getComputedStyle(mreza).fontSize) || 14;
    var stolpci = seznamPogled ? 1 : Math.max(2, Math.min(6, Math.floor((r.width + 0.6 * fs) / (8.6 * fs))));
    var visVrst = seznamPogled ? 2.6 * fs : 7.4 * fs, gap = (seznamPogled ? 0.25 : 0.6) * fs;
    var visina = Math.max(visVrst, r.height);
    var vrstic = Math.max(1, Math.floor((visina + gap) / (visVrst + gap)));
    mreza.style.setProperty("--stolpci", stolpci);
    var naStran = stolpci * vrstic;
    var seznam = programiFiltrirani();
    var strani = Math.max(1, Math.ceil(seznam.length / naStran));
    P.stran = Math.min(P.stran, strani - 1);
    var od = P.stran * naStran, do_ = Math.min(seznam.length, od + naStran);
    mreza.innerHTML = "";
    seznam.slice(od, do_).forEach(function (p) { mreza.appendChild(ploscicaPrograma(p)); });
    if (P.nalozeno && P.programi.length && !seznam.length) sporocila.push(t("niProgramov"));
    sp.textContent = sporocila.join(" · "); sp.hidden = !sporocila.length;
    sp.classList.toggle("napaka", P.nedosegljive.length > 0 || P.brezControla);
    ostraniStrani($("prgStrani"), od, do_, seznam.length, strani, P.stran, function (s) { P.stran = s; izrisiPrograme(); });
  }
  function ploscicaPrograma(p) {
    var b = el("button", "program"); b.type = "button"; b.setAttribute("role", "listitem");
    // Brez ikone z naprave: crka v barvi kot v Safeer OS (ne izmisljamo logotipa programa).
    b.appendChild(slikaAliCrka(p.ikona, p.ime));
    b.appendChild(el("span", "ime", p.ime));
    b.appendChild(el("small", "", p.imeNaprave));
    if (N.priljubljeniPrg.indexOf(kljucPrograma(p)) >= 0) b.appendChild(el("span", "zvezda", "★"));
    b.title = p.ime + " · " + p.imeNaprave + (p.opis ? "\n" + p.opis : "");
    b.addEventListener("click", function (e) { var r = b.getBoundingClientRect(); meniPrograma(p, r.left + 12, r.bottom - 6, e); });
    b.addEventListener("contextmenu", function (e) { e.preventDefault(); meniPrograma(p, e.clientX, e.clientY, e); });
    return b;
  }
  function meniPrograma(p, x, y) {
    var m = [];
    if (p.naprava === "splet") {
      m.push([t("odpri"), function () { klic("splet", [p.url]); }]);
    } else {
      m.push([t("odpriTukaj"), function () { zazeni("odpriTukaj", p); }]);
      m.push([t("zazeniNaNapravi"), function () { zazeni("zazeniNaNapravi", p); }]);
    }
    var fav = N.priljubljeniPrg.indexOf(kljucPrograma(p)) >= 0;
    m.push([fav ? t("odstraniPriljubljeno") : t("dodajPriljubljeno"), function () {
      if (fav) N.priljubljeniPrg = N.priljubljeniPrg.filter(function (k) { return k !== kljucPrograma(p); });
      else N.priljubljeniPrg.push(kljucPrograma(p));
      shrani(); izrisiPrograme();
    }]);
    m.push(["—"]);
    m.push([t("kategorija", { k: t(IMENA_KATEGORIJ[kategorijaPrograma(p)]) }), null, true]);
    ["pisarna", "ustvarjanje", "mediji", "splet", "igre", "drugo"].forEach(function (k) {
      if (k === kategorijaPrograma(p)) return;
      m.push(["  → " + t(IMENA_KATEGORIJ[k]), function () { N.kategorije[kljucPrograma(p)] = k; shrani(); izrisiPrograme(); }]);
    });
    pokaziMeni(m, x, y);
  }
  function zazeni(metoda, p) {
    klic(metoda, [p.naprava, p.id]).then(function (r) {
      if (r && r.ok === false) obvesti((r.message || r.sporocilo) ? String(r.message || r.sporocilo) : t("niUspelo"));
      else obvesti((r && r.message) ? String(r.message) : t("zagonPoslan", { naprava: p.imeNaprave }));
    }).catch(function () { obvesti(t("niUspelo")); });
  }

  // ------------------------------------------------------------------ meni (skupen)
  var meniOdprt = null;
  function pokaziMeni(postavke, x, y) {
    var m = $("meniPrograma"); m.innerHTML = "";
    postavke.forEach(function (p) {
      if (p[0] === "—") { m.appendChild(el("hr")); return; }
      var b = el("button", "", p[0]); b.type = "button"; b.setAttribute("role", "menuitem");
      if (p[2] || !p[1]) b.disabled = true;
      else b.addEventListener("click", function () { zapriMeni(); p[1](); });
      m.appendChild(b);
    });
    m.hidden = false; m.style.position = "fixed";
    var w = m.offsetWidth, h = m.offsetHeight;
    m.style.left = Math.max(8, Math.min(x, innerWidth - w - 8)) + "px";
    m.style.top = Math.max(8, Math.min(y, innerHeight - h - 8)) + "px";
    meniOdprt = m;
    var prvi = m.querySelector("button:not(:disabled)"); if (prvi) prvi.focus();
  }
  function zapriMeni() { if (meniOdprt) { meniOdprt.hidden = true; meniOdprt = null; } }

  // ------------------------------------------------------------------ MEDIJI
  var M = { casovnik: 0, zadnje: null };
  function medijZanka() {
    clearTimeout(M.casovnik);
    if (document.hidden || N.skrite.indexOf("mediji") >= 0) { M.casovnik = setTimeout(medijZanka, 4000); return; }
    medijOsvezi().then(function () { M.casovnik = setTimeout(medijZanka, M.zadnje && M.zadnje.stanje === "predvaja" ? 1000 : 3000); });
  }
  function medijOsvezi() {
    return klic("predvajalnikStanje").then(function (p) { M.zadnje = p || {}; izrisiMedij(); }).catch(function () {});
  }
  function izrisiMedij() {
    var p = M.zadnje || {}, ima = !!p.naslov && p.stanje !== "ustavljeno";
    $("ploscaMediji").classList.toggle("prazno", !ima);
    $("medijNaslov").textContent = ima ? p.naslov : t("niPredvajanja");
    var pod = !ima ? t("medijNavodilo")
      : p.stanje === "napaka" ? t("napakaPredvajanja")
      : (p.stanje === "premor" ? t("vPremoru") : t("predvaja")) + (p.izvor ? " · " + p.izvor : "");
    $("medijPodnaslov").textContent = pod;
    $("medijNapredek").style.width = (ima && p.trajanje > 0 ? Math.min(100, p.pozicija / p.trajanje * 100) : 0) + "%";
    $("ikonaPremor").setAttribute("d", p.stanje === "predvaja" ? "M8 5v14 M16 5v14" : "M8 5v14l11-7z");
    document.querySelectorAll("#kontrole button").forEach(function (b) { b.disabled = !ima; });
  }

  // ------------------------------------------------------------------ ISKANJE
  var I = { st: 0, casovnik: 0, zadetki: [], izbran: -1 };
  function isci(q) {
    var st = ++I.st;
    q = q.trim();
    if (!q) { skrijZadetke(); return; }
    var ql = q.toLowerCase();
    var skupine = [];
    // Programi naprav (ze nalozeni, potrjeni seznami)
    var prg = P.programi.filter(function (p) { return (p.ime + " " + (p.opis || "")).toLowerCase().indexOf(ql) >= 0; }).slice(0, 6);
    var cakaj = [
      klic("programi").then(function (s) {
        return (s || []).filter(function (p) { return !p.skrit && (p.ime + " " + (p.splosno || "") + " " + (p.kljucne || "")).toLowerCase().indexOf(ql) >= 0; }).slice(0, 5);
      }).catch(function () { return []; }),
      q.length >= 2 ? klic("isciDatoteke", [q]).then(function (s) { return (s || []).slice(0, 6); }).catch(function () { return []; }) : Promise.resolve([]),
      q.length >= 2 ? klic("knjiznicaMedijev", ["", q, 0]).then(function (s) { return (s || []).slice(0, 5); }).catch(function () { return []; }) : Promise.resolve([])
    ];
    izrisiZadetke([{ naslov: t("skSplet"), vnosi: [{ vrsta: "splet", q: q }] }, { naslov: t("isciem"), vnosi: [] }]);
    Promise.all(cakaj).then(function (r) {
      if (st !== I.st) return;
      skupine.push({ naslov: t("skSplet"), vnosi: [{ vrsta: "splet", q: q }] });
      if (r[0].length) skupine.push({ naslov: t("skProgrami"), vnosi: r[0].map(function (p) { return { vrsta: "program", p: p }; }) });
      if (prg.length) skupine.push({ naslov: t("skProgramiNaprav"), vnosi: prg.map(function (p) { return { vrsta: "prgNaprave", p: p }; }) });
      if (r[1].length) skupine.push({ naslov: t("skDatoteke"), vnosi: r[1].map(function (d) { return { vrsta: "datoteka", d: d }; }) });
      if (r[2].length) skupine.push({ naslov: t("skMediji"), vnosi: r[2].map(function (d) { return { vrsta: "medij", d: d }; }) });
      izrisiZadetke(skupine);
    });
  }
  function izrisiZadetke(skupine) {
    var z = $("zadetki"); z.innerHTML = ""; I.zadetki = []; I.izbran = 0;
    skupine.forEach(function (s) {
      z.appendChild(el("p", "skupina-naslov", s.naslov));
      s.vnosi.forEach(function (v) {
        var b = el("button", "zadetek"); b.type = "button"; b.setAttribute("role", "option"); b.tabIndex = -1;
        var ime, pod = "", vir = "";
        if (v.vrsta === "splet") {
          b.appendChild(ikonaVrste("splet")); ime = t("isciVSpletu", { q: v.q }); pod = t("odpreVBrskalniku");
        } else if (v.vrsta === "program") {
          appendIkona(b, v.p.ikona, v.p.ime); ime = v.p.ime; pod = v.p.opis || ""; vir = t("taRacunalnik");
        } else if (v.vrsta === "prgNaprave") {
          appendIkona(b, v.p.ikona, v.p.ime); ime = v.p.ime; vir = v.p.imeNaprave;
        } else if (v.vrsta === "datoteka") {
          b.appendChild(ikonaVrste(v.d.mapa ? "mapa" : v.d.vrsta)); ime = v.d.ime; pod = stranskoBesedilo(v.d.pot); vir = t("taRacunalnik");
        } else {
          b.appendChild(ikonaVrste(v.d.vrsta === "glasba" ? "zvok" : v.d.vrsta === "slike" ? "slika" : "video"));
          ime = v.d.naslov || v.d.ime || v.d.pot; pod = stranskoBesedilo(v.d.pot || ""); vir = t("taRacunalnik");
        }
        b.appendChild(el("span", "ime", ime));
        if (pod) b.appendChild(el("small", "", pod));
        if (vir) b.appendChild(el("span", "oznaka-vira" + (v.vrsta === "prgNaprave" ? " oddaljeno" : ""), vir));
        b.addEventListener("click", function () { izberiZadetek(v); });
        b.addEventListener("mouseenter", function () { I.izbran = I.zadetki.indexOf(b); oznaciZadetek(); });
        b._v = v; I.zadetki.push(b); z.appendChild(b);
      });
    });
    z.hidden = false; $("iskalnoPolje").setAttribute("aria-expanded", "true");
    oznaciZadetek();
  }
  function appendIkona(b, src, ime) { b.appendChild(slikaAliCrka(src, ime || "?", "ikona-zadetka")); }
  function oznaciZadetek() {
    I.zadetki.forEach(function (b, i) { b.setAttribute("aria-selected", i === I.izbran ? "true" : "false"); });
    var b = I.zadetki[I.izbran]; if (b) b.scrollIntoView({ block: "nearest" });
  }
  function skrijZadetke() { $("zadetki").hidden = true; $("iskalnoPolje").setAttribute("aria-expanded", "false"); I.zadetki = []; }
  function izberiZadetek(v) {
    skrijZadetke();
    if (v.vrsta === "splet") odpriSplet(v.q);
    else if (v.vrsta === "program") klic("zazeni", [v.p.id]);
    else if (v.vrsta === "prgNaprave") { var r = $("iskalnoPolje").getBoundingClientRect(); meniPrograma(v.p, r.left, r.bottom + 6); }
    else if (v.vrsta === "datoteka") odpriVnos(v.d);
    else if (v.vrsta === "medij") klic("odpriLokalniMedij", [v.d.pot]).then(function (ok) { if (ok) medijOsvezi(); else obvesti(t("niUspelo")); });
    $("iskalnoPolje").value = "";
  }
  function odpriSplet(q) {
    // Spletni zadetek odpre privzeti brskalnik; starejsi Safeer OS brez te metode odpre vdelani Splet.
    klic("odpriVBrskalniku", [q]).then(function (ok) { if (ok === false) return klic("iskanjeSplet", [q]); })
      .catch(function () { klic("iskanjeSplet", [q]); });
  }

  // ------------------------------------------------------------------ SAFEER LINK (gumb pod iskalnikom)
  // Samo prikaz stanja; prijavno okno (Safeer Control) se odpre izkljucno na klik uporabnika.
  var L = { stanje: null, casovnik: 0 };
  function steviloNaprav(n) {
    var m100 = n % 100;
    if (jezik !== "sl") return t(n === 1 ? "naprav1" : "napravN", { n: n });
    if (m100 === 1) return t("naprav1");
    if (m100 === 2) return t("naprav2");
    if (m100 === 3 || m100 === 4) return t("naprav34", { n: n });
    return t("napravN", { n: n });
  }
  function izrisiLink() {
    var g = $("gumbLink"), p = L.stanje;
    if (!p || !p.control) { g.hidden = true; return; }
    var povezan = p.stanje === "povezan";
    var ids = {};
    P.naprave.concat(D.naprave).forEach(function (n) { if (n && n.id) ids[n.id] = 1; });
    var n = Object.keys(ids).length;
    g.hidden = false;
    g.classList.toggle("povezan", povezan);
    g.classList.toggle("nepovezan", !povezan);
    $("linkBesedilo").textContent = povezan ? (n ? t("linkPovezan", { n: steviloNaprav(n) }) : t("linkPovezanBrez")) : t("linkPovezi");
    g.title = t("linkNaslov");
  }
  function osveziLink() {
    clearTimeout(L.casovnik);
    if (!most) return;
    klic("povezava").then(function (p) { L.stanje = p || null; izrisiLink(); }).catch(function () {});
    L.casovnik = setTimeout(osveziLink, 60000);
  }

  // ------------------------------------------------------------------ vezave
  var zadnjeOsvezevanje = Date.now();
  function vezi() {
    var polje = $("iskalnoPolje");
    polje.addEventListener("input", function () { clearTimeout(I.casovnik); var q = polje.value; I.casovnik = setTimeout(function () { isci(q); }, 220); });
    polje.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        if (!I.zadetki.length) return;
        e.preventDefault(); I.izbran = (I.izbran + (e.key === "ArrowDown" ? 1 : -1) + I.zadetki.length) % I.zadetki.length; oznaciZadetek();
      } else if (e.key === "Escape") { skrijZadetke(); polje.value = ""; }
    });
    $("iskanje").addEventListener("submit", function (e) {
      e.preventDefault();
      var q = polje.value.trim(); if (!q) return;
      var b = I.zadetki[I.izbran];
      izberiZadetek(b ? b._v : { vrsta: "splet", q: q });
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { zapriMeni(); $("meniPlosce").hidden = true; }
      var vPolju = /^(INPUT|SELECT|TEXTAREA)$/.test((document.activeElement || {}).tagName || "");
      if ((e.ctrlKey && (e.key === "k" || e.key === "K")) || (!vPolju && e.key === "/")) { e.preventDefault(); polje.focus(); polje.select(); }
    });
    document.addEventListener("click", function (e) {
      if (meniOdprt && !meniOdprt.contains(e.target) && !e.target.closest(".program")) zapriMeni();
      if (!e.target.closest(".vrh")) skrijZadetke();
      if (!e.target.closest(".vrh-orodja")) { $("meniPlosce").hidden = true; $("gumbPlosce").setAttribute("aria-expanded", "false"); }
    });

    // Plosce, postavitev, dostopnost
    $("gumbPlosce").addEventListener("click", function () {
      var m = $("meniPlosce"); m.hidden = !m.hidden; this.setAttribute("aria-expanded", m.hidden ? "false" : "true");
    });
    document.querySelectorAll("#meniPlosce input[data-plosca]").forEach(function (cb) {
      cb.addEventListener("change", function () { nastaviSkrito(cb.getAttribute("data-plosca"), !cb.checked); });
    });
    document.querySelectorAll("[data-skrij]").forEach(function (b) {
      b.addEventListener("click", function () { nastaviSkrito(b.getAttribute("data-skrij"), true); });
    });
    $("gumbZamenjaj").addEventListener("click", function () { N.zamenjano = !N.zamenjano; shrani(); uveljaviPostavitev(); });
    $("gumbPonastavi").addEventListener("click", function () {
      var ohrani = { priljubljeniPrg: N.priljubljeniPrg, kategorije: N.kategorije, priljubljeneDat: N.priljubljeneDat };
      N = JSON.parse(JSON.stringify(PRIVZETO)); Object.keys(ohrani).forEach(function (k) { N[k] = ohrani[k]; });
      shrani(); uveljaviPostavitev();
    });
    $("stikaloTekst").addEventListener("change", function () { N.vecjiTekst = this.checked; shrani(); uveljaviPostavitev(); });
    $("stikaloProsojnost").addEventListener("change", function () { N.manjProsojnosti = this.checked; shrani(); uveljaviPostavitev(); });

    // Nova mapa / datoteka: gumb +, desni klik na prazno, Ctrl+Shift+N, okno
    $("gumbNovo").addEventListener("click", function (ev) {
      // Sicer bi splosni »klik drugam zapre meni« (document) meni takoj zaprl.
      ev.stopPropagation();
      var r = this.getBoundingClientRect(); meniNovo(r.left, r.bottom + 4);
    });
    document.querySelector(".dat-glavno").addEventListener("contextmenu", function (ev) {
      if (ev.target.closest("tbody tr") || ev.target.closest("input, select, button")) return;
      ev.preventDefault(); meniNovo(ev.clientX, ev.clientY);
    });
    $("ploscaDatoteke").addEventListener("keydown", function (ev) {
      if (ev.ctrlKey && ev.shiftKey && (ev.key === "N" || ev.key === "n")) { ev.preventDefault(); odpriOknoNovo({ nacin: "mapa", kam: kamNovo() }); }
    });
    $("obrazecNovo").addEventListener("submit", function (ev) { ev.preventDefault(); potrdiNovo(); });
    $("novoPreklici").addEventListener("click", zapriOknoNovo);
    $("oknoNovo").addEventListener("keydown", function (ev) { if (ev.key === "Escape") { ev.stopPropagation(); zapriOknoNovo(); } });
    $("oknoNovo").addEventListener("mousedown", function (ev) { if (ev.target === this) zapriOknoNovo(); });
    $("novoVrsta").addEventListener("change", function () {
      // Ime sledi vrsti, dokler ga uporabnik ni spremenil sam.
      var polje = $("novoIme"), prej = VRSTE_NOVIH.map(function (v) { return t(v[2]); });
      if (prej.indexOf(polje.value) < 0 && predlogeDatotek.map(function (p) { return p.ime; }).indexOf(polje.value) < 0) return;
      var v = this.value;
      polje.value = v.indexOf("predloga:") === 0 ? (predlogeDatotek.filter(function (p) { return "predloga:" + p.pot === v; })[0] || {}).ime || polje.value
        : t((VRSTE_NOVIH.filter(function (x) { return x[0] === v; })[0] || VRSTE_NOVIH[0])[2]);
    });
    $("novoSpremeni").addEventListener("click", function () {
      klic("izberiMapo", [NO.kam || "~", t("izberiMapoNaslov"), t("preklici"), t("izberi")]).then(function (p) {
        if (p) nastaviKje(p);
        $("novoIme").focus();
      }).catch(function () {});
    });

    // Datoteke
    $("datFilter").addEventListener("input", function () { D.stran = 0; izrisiDatoteke(); });
    $("datVrsta").addEventListener("change", function () { D.stran = 0; izrisiDatoteke(); });
    document.querySelectorAll("#datSeznam th button").forEach(function (b) {
      b.addEventListener("click", function () {
        var k = b.getAttribute("data-razvrsti");
        if (D.razvrsti === k && D.rocno) D.smer = -D.smer; else { D.razvrsti = k; D.smer = k === "spremenjeno" ? -1 : 1; }
        D.rocno = true; izrisiDatoteke();
      });
    });
    $("ploscaDatoteke").addEventListener("keydown", function (e) {
      if (e.key === "PageDown" || e.key === "PageUp") {
        e.preventDefault(); var b = $("datStrani").querySelectorAll("button")[e.key === "PageDown" ? 1 : 0];
        if (b && !b.disabled) b.click();
      }
    });

    // Programi
    $("prgFilter").addEventListener("input", function () { P.stran = 0; izrisiPrograme(); });
    $("prgNaprava").addEventListener("change", function () { P.stran = 0; izrisiPrograme(); });
    $("prgRazvrsti").addEventListener("change", function () { izrisiPrograme(); });
    $("prgPogled").addEventListener("click", function () { N.pogled = N.pogled === "seznam" ? "mreza" : "seznam"; shrani(); P.stran = 0; izrisiPrograme(); });
    $("ploscaProgrami").addEventListener("keydown", function (e) {
      if (e.key === "PageDown" || e.key === "PageUp") {
        e.preventDefault(); var b = $("prgStrani").querySelectorAll("button")[e.key === "PageDown" ? 1 : 0];
        if (b && !b.disabled) b.click();
      }
    });

    // Safeer Link, ozadje, dock
    $("gumbLink").addEventListener("click", function () {
      // Povezan racunalnik: okno »Poveži naprave« (QR ALI 6-mestna koda). Nepovezan: prijavno okno
      // (QR / vpis kode / brez povezave). Oboje v Safeer Controlu, nikoli samo ob prijavi.
      var povezan = L.stanje && L.stanje.stanje === "povezan";
      klic(povezan ? "novaNaprava" : "prijava").then(function (ok) { if (ok === false) obvesti(t("brezControla")); })
        .catch(function () {});
      setTimeout(osveziLink, 8000);
    });
    $("gumbOzadje").addEventListener("click", function () { $("meniPlosce").hidden = true; klic("nastavitveOzadja"); });
    $("gumbDock").addEventListener("click", function () { $("meniPlosce").hidden = true; klic("nastavitveDocka"); });

    // Mediji
    document.querySelectorAll("#kontrole [data-ukaz]").forEach(function (b) {
      b.addEventListener("click", function () { klic("predvajalnikUkaz", [b.getAttribute("data-ukaz")]).then(medijOsvezi); });
    });
    $("gumbMedijskiCenter").addEventListener("click", function () { klic("odpriRazdelek", ["media"]).catch(function () {}); });

    // Velikost okna: prerazporedi strani (brez pomikanja)
    var rt = 0;
    window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { izrisiDatoteke(); izrisiPrograme(); }, 120); });
    document.addEventListener("visibilitychange", function () { if (!document.hidden) medijZanka(); });
    // Dogodki iz Safeer OS (enako ime kot na glavni strani): osvezi, kar se je spremenilo.
    window.safeerOsDogodek = function (vrsta) {
      if (vrsta === "medijskaKnjiznica") medijOsvezi();
      else if (vrsta === "ozadje") {
        var u = arguments[1] || "";
        document.documentElement.style.setProperty("--ozadje-slika", u ? 'url("' + u + '")' : "none");
      }
      else if (vrsta === "robovi") { robovi(arguments[1] || {}); izrisiDatoteke(); izrisiPrograme(); }
      else if (vrsta === "fokus" && Date.now() - zadnjeOsvezevanje > 30000) {
        // Naprave v Linku se spreminjajo: ob vrnitvi v Safeer OS osvezimo najvec vsakih 30 s.
        zadnjeOsvezevanje = Date.now(); zgradiStranDatotek(); naloziProgrameNaprav(); osveziLink();
      }
    };
  }
  function nastaviSkrito(p, skrij) {
    N.skrite = N.skrite.filter(function (x) { return x !== p; });
    if (skrij) N.skrite.push(p);
    if (N.skrite.length >= 3) N.skrite = N.skrite.filter(function (x) { return x !== p; }); // vsaj ena plosca ostane
    shrani(); uveljaviPostavitev();
  }

  window.SafeerDelovna = { osvezi: function () { zgradiStranDatotek(); naloziProgrameNaprav(); medijOsvezi(); } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", zacni); else zacni();
})();
