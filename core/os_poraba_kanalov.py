"""Poraba kanalov Sporocil (plosca »Info«): vzorcenje vsakih 30 s, pripis procesov kanalom in porocilo za stran.

Kako vemo, kateri proces je kanalov (dokumentirana metoda, nic izmisljenega):
  * Spletni kanal: WebKitGTK 6.0 nima API, ki bi pogledu povedal PID njegovega spletnega procesa (preverjeno
    15. 10. 2026, WebKitGTK 2.52: WebView nima ne PID ne identifikatorja procesa; cmdline in okolje procesov ne
    vsebujeta strani). Zato SONDA: v locenem svetu skript (stran ga ne vidi) kanal za SONDA_MS zaposli procesor,
    hkrati beremo /proc/<pid>/stat vseh spletnih procesov Safeer OS - proces kanala je tisti, ki je v tem casu porabil
    procesor (najmanj polovico pricakovanega in vsaj 3-krat vec od naslednjega; sicer poskus znova, nic ugibanja).
    Preizkus 15. 10. 2026 (3 pogledi, 150 ms): 16-17 tikov v pravem procesu, 0 v ostalih. Stran, ki se nalaga, porabi
    procesor tudi sama (39 proti 16 tikov), zato se najprej izmeri enako dolgo okno brez sonde in steje razlika.
    Sonda tece ob nalaganju, ko se spremeni registrirana domena strani (WebKit takrat lahko zamenja proces), po padcu,
    ko se kanal odpre v oknu Sporocil, in po neuspehu znova (5 s, 10 s, nato ob vzorcu najvec vsakih 60 s).
    Kandidati so potomci Safeer OS in - v Flatpaku - procesi v podpeskovniku portala (poraba_kanalov.Proc.nasi).
    Diagnostika gre v dnevnik (»[Sporocila] poraba:«, brez vsebine strani).
    Servisni delavci tecejo v svojih procesih brez strani - teh sonda ne najde; so v vrstici »drugi spletni procesi«.
  * Namizni program: _NET_WM_PID vstavljenega okna, koren programa (navzgor, dokler je ime procesa enako) in vsi
    njegovi potomci (Electron, QtWebEngine). Brez PID (Flatpak, drug imenski prostor procesov): ni merljivo.
  * Kanali API (posta, Telegram, Matrix, Chatwoot, Safeer Chat): tecejo v procesu Safeer OS - delez ni locljiv,
    pomnilnik in procesor sta »vkljucena v Safeer OS«; merljiv je prostor na disku (sporocila v lokalni bazi,
    predpomnilnik prilog).
"""
from __future__ import annotations

import os
import threading
import time
from typing import Callable, Dict, Optional

from core import poraba_kanalov as _p

#: Koliko casa sonda zaposli kanal (en tik ure je 10 ms; 250 ms = ~25 tikov - vec od sunkov strani, ki se nalaga).
SONDA_MS = 250
#: Po koliko ms sonde beremo stevce (sonda + zakasnitev zagona skripta).
SONDA_BERI_MS = 500
SONDA_POSKUSOV = 3
#: Rezerva, ce WebKit ne poklice povratnega klica sonde (pogled unicen, proces visi): izid po tem roku.
SONDA_ROK_MS = 5000
#: Po koncu skripte pocakaj en do dva tika ure, da jedro zapise porabo procesorja v /proc.
SONDA_ZAPIS_MS = 30
#: Po neuspelih hitrih poskusih: sonda znova ob vzorcu, najvec vsakih toliko sekund.
SONDA_PREMOR_S = 60
SONDA_SVET = "safeer-poraba"
#: Kako dolgo velja izmerjen prostor na disku (branje podatkov strani in mape prilog ni zastonj).
DISK_VELJA_S = 60
SPLETNI_PROCES = "WebKitWebProces"      # /proc/<pid>/comm je prirezan na 15 znakov
OMREZNI_PROCES = "WebKitNetworkPr"


def _imenski_prostor() -> str:
    try:
        return os.readlink("/proc/self/ns/pid") + (" flatpak" if os.path.exists("/.flatpak-info") else "")
    except OSError:
        return "?"


def _domena(url: str) -> str:
    from core import pojavna_okna
    return pojavna_okna.osnova(pojavna_okna.gostitelj(url or ""))


class PorabaKanalov:
    def __init__(self, GLib, kanali, sporocila: Callable[[], object], proc: Optional[_p.Proc] = None,
                 koren_pid: Optional[int] = None) -> None:
        self.GLib = GLib
        self.kanali = kanali                    # core/os_kanali_sporocil.KanaliSporocil
        self.sporocila = sporocila              # () -> core/os_sporocila.SporocilaOS ali None
        self.proc = proc or _p.Proc()
        self.koren_pid = koren_pid or os.getpid()
        self.zgodovina = _p.Zgodovina()
        #: kid -> (pid, domena) spletnega procesa kanala (sonda)
        self.pid_spleta: Dict[str, tuple] = {}
        self._sonde: list = []
        self._sonda_tece = False
        self._sonda_zeton = None
        self._poskusi: Dict[str, int] = {}
        self._zadnja_sonda: Dict[str, float] = {}
        self._casovnik = 0
        #: kljuc -> {"cas", "tiki": {pid: tiki}} - za procesor med vzorcema (posebej za vzorce in za odprto plosco)
        self._prej_vzorec: Dict[str, dict] = {}
        self._prej_ogled: Dict[str, dict] = {}
        self._disk: dict = {"cas": -1e9, "splet": {}, "api": {}}
        self._disk_tece = False
        #: cena merjenja: procesorski cas vzorcenja (s) in stevilo vzorcev
        self.cena_s, self.vzorcev = 0.0, 0

    # ------------------------------------------------------------------ zivljenje kanalov
    def prikljuci(self, kid: str, z) -> None:
        """Nov zivi kanal: spletnemu sledimo nalaganju (sonda), vzorcenje se zazene."""
        if z.aplikacija is not None:
            pogled = z.aplikacija.pogled
            pogled.connect("load-changed", lambda p, d, kid=kid: self._nalaganje(kid, p, d))
            pogled.connect("web-process-terminated", lambda *_a, kid=kid: self.pid_spleta.pop(kid, None))
        self.uskladi()

    def pozabi(self, kid: str) -> None:
        self.pid_spleta.pop(kid, None)
        self._poskusi.pop(kid, None)
        self._zadnja_sonda.pop(kid, None)
        self._prej_vzorec.pop(kid, None)
        self._prej_ogled.pop(kid, None)
        self.uskladi()

    def uskladi(self) -> None:
        """Vzorci tecejo samo, ko je ziv vsaj en spletni kanal ali program (brez kanalov se ne meri nic)."""
        if self.kanali.zivi and not self._casovnik:
            self._casovnik = self.GLib.timeout_add_seconds(_p.VZOREC_S, self._vzorci, priority=self.GLib.PRIORITY_LOW)
        elif not self.kanali.zivi and self._casovnik:
            self.GLib.source_remove(self._casovnik)
            self._casovnik = 0

    def ustavi(self) -> None:
        if self._casovnik:
            self.GLib.source_remove(self._casovnik)
            self._casovnik = 0

    def _nalaganje(self, kid: str, pogled, dogodek) -> None:
        nick = getattr(dogodek, "value_nick", "")
        if nick == "committed":
            znan = self.pid_spleta.get(kid)
            if znan is not None and znan[1] != _domena(pogled.get_uri() or ""):
                self.pid_spleta.pop(kid, None)     # druga stran: WebKit je morda zamenjal proces
        elif nick == "finished" and kid not in self.pid_spleta:
            self.sonda(kid)

    # ------------------------------------------------------------------ sonda
    def spletni_procesi(self, starsi=None, ime: str = SPLETNI_PROCES) -> list:
        """Nasi procesi WebKita: potomci Safeer OS in (Flatpak) procesi v podpeskovniku portala (Proc.nasi)."""
        v_drevesu, podpeskovnik = self.proc.nasi(self.koren_pid, ime, starsi)
        return v_drevesu + podpeskovnik

    def sonda(self, kid: str) -> None:
        if kid not in self._sonde:
            self._sonde.append(kid)
        self._zadnja_sonda[kid] = time.monotonic()
        if not self._sonda_tece:
            self.GLib.idle_add(self._naslednja_sonda, priority=self.GLib.PRIORITY_LOW)

    def ob_prikazu(self, kid: str) -> None:
        """Kanal je odprt v oknu Sporocil: ce njegov proces se ni znan, sonda takoj (stevec poskusov znova)."""
        z = self.kanali.zivi.get(kid)
        if z is not None and z.aplikacija is not None and kid not in self.pid_spleta:
            self._poskusi.pop(kid, None)
            self.sonda(kid)

    def _ponovi_kasneje(self, kid: str) -> None:
        """Neuspela sonda: znova cez 2 s, 5 s (prva sonda pogosto ujame zagon strani - 18. 10. 2026); nato ob vsakem vzorcu ali odprtju plosce, najvec vsakih 60 s."""
        n = self._poskusi.get(kid, 0) + 1
        self._poskusi[kid] = n
        if n < SONDA_POSKUSOV:
            self.GLib.timeout_add_seconds(2 if n == 1 else 5, lambda: (kid in self.kanali.zivi and kid not in self.pid_spleta
                                                          and self.sonda(kid), False)[1])

    def _sonda_ce_je_cas(self, kid: str, premor_s: float = SONDA_PREMOR_S) -> None:
        if time.monotonic() - self._zadnja_sonda.get(kid, -1e9) >= premor_s:
            self.sonda(kid)

    @staticmethod
    def _dnevnik(*deli) -> None:
        # Diagnostika sonde (brez vsebine strani): id kanala, stevila procesov, tiki, izid.
        print("[Sporocila] poraba:", *deli, flush=True)

    def _naslednja_sonda(self) -> bool:
        if self._sonda_tece:
            return False        # hkrati najvec ena sonda (sicer bi si kanala delila stevce)
        while self._sonde:
            kid = self._sonde.pop(0)
            z = self.kanali.zivi.get(kid)
            if z is None or z.aplikacija is None:
                continue
            pogled = z.aplikacija.pogled
            v_drevesu, podpeskovnik = self.proc.nasi(self.koren_pid, SPLETNI_PROCES)
            kandidati = v_drevesu + podpeskovnik
            if not kandidati:
                vidni = len([p for p in self.proc.starsi() if self.proc.ime(p) == SPLETNI_PROCES])
                self._dnevnik("sonda kanal=%s brez kandidatov (drevo 0, podpeskovnik 0, vidnih procesov WebKit %d, "
                              "pid=%d, imenski prostor %s)" % (kid, vidni, self.koren_pid, _imenski_prostor()))
                self._ponovi_kasneje(kid)
                continue
            self._sonda_tece = True
            # Ozadje: najprej enako dolgo okno brez sonde (proces, ki se nalaga, porabi procesor tudi sam - zivi
            # preizkus: 39 proti 16 tikov), nato sonda; steje razlika med oknoma.
            ozadje = {p: self.proc.tiki(p) for p in kandidati}
            self.GLib.timeout_add(SONDA_BERI_MS, self._sonda_zazeni, kid, ozadje)
            return False
        return False

    def _sonda_zazeni(self, kid: str, ozadje: dict) -> bool:
        z = self.kanali.zivi.get(kid)
        if z is None or z.aplikacija is None:
            self._sonda_tece = False
            self._naslednja_sonda()
            return False
        pogled = z.aplikacija.pogled
        pred = {p: self.proc.tiki(p) for p in ozadje}
        brez_sonde = {p: max(0, pred[p] - t) for p, t in ozadje.items()}
        domena = _domena(pogled.get_uri() or "")
        koda = "var t=performance.now();while(performance.now()-t<%d){}" % SONDA_MS
        # Izid se bere, ko skripta KONCA (povratni klic), ne po fiksnih 500 ms: pod obremenitvijo (CI, polni nabor
        # preizkusov, kanal se se nalaga) se je sonda zacela pozno in v oknu je bilo le 5-7 od 25 tikov (18. 10. 2026).
        zeton = object()
        self._sonda_zeton = zeton
        zacetek = time.monotonic()
        izid = (kid, pred, domena, brez_sonde, zacetek)

        def koncana(vir, rezultat, *_a):
            try:
                vir.evaluate_javascript_finish(rezultat)
            except Exception as e:  # noqa: BLE001 - napaka skripte ali unicen pogled: izid vseeno prebere rok
                self._dnevnik("sonda kanal=%s skripta: %s" % (kid, str(e)[:120]))
            self.GLib.timeout_add(SONDA_ZAPIS_MS, self._sonda_izid_zeton, zeton, *izid)
        try:
            pogled.evaluate_javascript(koda, -1, SONDA_SVET, None, None, koncana, None)
        except Exception:  # noqa: BLE001 - pogled je ze unicen
            self._sonda_zeton = None
            self._sonda_tece = False
            self._naslednja_sonda()
            return False
        self.GLib.timeout_add(SONDA_ROK_MS, self._sonda_izid_zeton, zeton, *izid)
        return False

    def _sonda_izid_zeton(self, zeton, kid: str, pred: dict, domena: str, brez_sonde: dict, zacetek: float) -> bool:
        """Prvi od (povratni klic, rok) prebere izid; drugi ne naredi nic."""
        if getattr(self, "_sonda_zeton", None) is not zeton:
            return False
        self._sonda_zeton = None
        # Ozadje je bilo merjeno v oknu SONDA_BERI_MS; okno sonde je lahko daljse - ozadje sorazmerno povecaj.
        faktor = max(1.0, (time.monotonic() - zacetek) * 1000.0 / SONDA_BERI_MS)
        return self._sonda_izid(kid, pred, domena, {p: t * faktor for p, t in brez_sonde.items()})

    def _sonda_izid(self, kid: str, pred: dict, domena: str, brez_sonde: Optional[dict] = None) -> bool:
        self._sonda_tece = False
        brez_sonde = brez_sonde or {}
        razlike = sorted(((self.proc.tiki(p) - t - brez_sonde.get(p, 0), p) for p, t in pred.items()
                          if self.proc.zivi(p)), reverse=True)
        pricakovano = SONDA_MS / 1000.0 * self.proc.hz
        # Zanka sonde meri stensko uro: pod obremenitvijo (vec procesov na jedro) dobi le del jedra - izmerjeno
        # 18. 10. 2026 (xvfb, polni nabor): 6-11 od 25 tikov, drugi proces pa negativno (ozadje nalaganja). Zato
        # spodnja meja petina pricakovanega, odlocitev pa jasna prevlada (3x) nad drugim kandidatom.
        uspeh = bool(razlike) and razlike[0][0] >= max(3.0, pricakovano / 5) and (
            len(razlike) < 2 or razlike[0][0] >= 3 * max(razlike[1][0], 1.0))
        self._dnevnik("sonda kanal=%s kandidatov=%d tiki=%s pricakovano=%d izid=%s" % (
            kid, len(pred), [r[0] for r in razlike[:3]], round(pricakovano), razlike[0][1] if uspeh else "ni"))
        if uspeh:
            if kid in self.kanali.zivi:
                self.pid_spleta[kid] = (razlike[0][1], domena)
            self._poskusi.pop(kid, None)
        else:
            self._ponovi_kasneje(kid)
        self._naslednja_sonda()
        return False

    # ------------------------------------------------------------------ meritve
    def _pidi(self, kid: str, z, otroci) -> tuple:
        """(pidi, razlog) - razlog, ce kanal ni merljiv locno."""
        if z.aplikacija is not None:
            znan = self.pid_spleta.get(kid)
            if znan is None or not self.proc.zivi(znan[0]):
                if znan is not None:
                    self.pid_spleta.pop(kid, None)
                    self.sonda(kid)
                else:
                    self._sonda_ce_je_cas(kid)      # prejsnja sonda ni uspela: znova, najvec vsakih 60 s
                return [], "sonda"
            return [znan[0]], ""
        if z.program is not None:
            pid = int(getattr(z, "pid", 0) or 0)
            if not pid or not self.proc.zivi(pid):
                return [], "pid"
            return self.proc.drevo(self.proc.koren_programa(pid), otroci), ""
        return [], "pid"

    def _meri(self, kljuc: str, pidi: list, prej: dict, delez: float = 1.0) -> tuple:
        """(MiB, % procesorja ali None) za mnozico procesov; prej[kljuc] hrani stevce za naslednjic."""
        zdaj = time.monotonic()
        meritve = [self.proc.pomnilnik(p) for p in pidi]
        mem = sum(m[0] for m in meritve) / 1024.0 * delez
        prej.setdefault("_priblizek", set())
        if any(not m[1] for m in meritve):
            prej["_priblizek"].add(kljuc)
        else:
            prej["_priblizek"].discard(kljuc)
        tiki = {p: self.proc.tiki(p) for p in pidi}
        star = prej.get(kljuc)
        cpu = None
        if star is not None and zdaj > star["cas"]:
            # Procesi, ki jih prej ni bilo, so nastali med vzorcema: steje ves njihov cas.
            delta = sum(t - star["tiki"].get(p, 0) for p, t in tiki.items() if t >= star["tiki"].get(p, 0))
            cpu = _p.cpu_odstotek(0, delta, zdaj - star["cas"], self.proc.hz)
            if cpu is not None:
                cpu = round(cpu * delez, 1)
        prej[kljuc] = {"cas": zdaj, "tiki": tiki}
        return round(mem, 1), cpu

    def _vse_meritve(self, prej: dict) -> dict:
        """kljuc -> {"mem", "cpu", "razlog", "deljeno"} za zive kanale in skupne vrstice."""
        starsi = self.proc.starsi()
        otroci = self.proc.otroci(starsi)
        izid, pidi_kanalov = {}, {}
        for kid, z in list(self.kanali.zivi.items()):
            pidi, razlog = self._pidi(kid, z, otroci)
            pidi_kanalov[kid] = (pidi, razlog)
        # Isti proces pri dveh kanalih (WebKit lahko proces iste strani uporabi znova): razdeljen enako, oznacen.
        stetje: Dict[int, int] = {}
        for pidi, _r in pidi_kanalov.values():
            for p in pidi:
                stetje[p] = stetje.get(p, 0) + 1
        for kid, (pidi, razlog) in pidi_kanalov.items():
            if razlog:
                izid[kid] = {"mem": None, "cpu": None, "razlog": razlog}
                continue
            n = max(stetje.get(p, 1) for p in pidi) if pidi else 1
            mem, cpu = self._meri(kid, pidi, prej, 1.0 / n)
            izid[kid] = {"mem": mem, "cpu": cpu, "razlog": "", "deljeno": n > 1,
                         "priblizek": kid in prej.get("_priblizek", ())}
        pripisani = {p for pidi, _r in pidi_kanalov.values() for p in pidi}
        drugi = [p for p in self.spletni_procesi(starsi) if p not in pripisani]
        omrezje = self.spletni_procesi(starsi, OMREZNI_PROCES)
        for kljuc, pidi in (("_safeer", [self.koren_pid]), ("_omrezje", omrezje), ("_drugi", drugi)):
            mem, cpu = self._meri(kljuc, pidi, prej)
            izid[kljuc] = {"mem": mem, "cpu": cpu, "razlog": "", "procesov": len(pidi),
                           "priblizek": kljuc in prej.get("_priblizek", ())}
        return izid

    def _vzorci(self) -> bool:
        if not self.kanali.zivi:
            self._casovnik = 0
            return False
        zacetek = time.process_time()
        zdaj = time.monotonic()
        for kljuc, m in self._vse_meritve(self._prej_vzorec).items():
            self.zgodovina.dodaj(kljuc, zdaj, m["mem"], m["cpu"])
        self.cena_s += time.process_time() - zacetek
        self.vzorcev += 1
        return True

    # ------------------------------------------------------------------ disk
    def _osvezi_disk(self, ob_koncu: Callable[[], None]) -> None:
        """Podatki strani po registriranih domenah (WebsiteDataManager) in prostor kanalov API (baza, priloge)."""
        if self._disk_tece:
            return
        self._disk_tece = True
        stanje = {"splet": None, "api": None}

        def konec():
            if stanje["splet"] is not None and stanje["api"] is not None:
                self._disk = {"cas": time.monotonic(), "splet": stanje["splet"], "api": stanje["api"]}
                self._disk_tece = False
                ob_koncu()

        splet = self.kanali.jedro() if callable(getattr(self.kanali, "jedro", None)) else None
        upravitelj = None
        try:
            upravitelj = splet.podatki() if splet is not None else None
        except Exception:  # noqa: BLE001
            upravitelj = None
        if upravitelj is None:
            stanje["splet"] = {}
        else:
            from gi.repository import WebKit
            T = WebKit.WebsiteDataTypes
            tipi = [T.DISK_CACHE, T.LOCAL_STORAGE, T.INDEXEDDB_DATABASES, T.DOM_CACHE,
                    T.SERVICE_WORKER_REGISTRATIONS]

            def prebrano(m, r, *_a):
                velikosti = {}
                try:
                    for d in m.fetch_finish(r):
                        velikosti[d.get_name()] = velikosti.get(d.get_name(), 0) + sum(d.get_size(t) for t in tipi)
                except Exception as e:  # noqa: BLE001
                    print("[Sporocila] poraba, podatki strani:", e, flush=True)
                stanje["splet"] = velikosti
                konec()
            upravitelj.fetch(T.ALL, None, prebrano, None)

        so = self.sporocila()

        def api():
            izid = {}
            try:
                if so is not None:
                    izid = dict(so.velikost_kanalov() or {})
            except Exception as e:  # noqa: BLE001
                print("[Sporocila] poraba, baza:", e, flush=True)
            stanje["api"] = izid
            self.GLib.idle_add(lambda: (konec(), False)[1])
        threading.Thread(target=api, name="safeer-poraba-disk", daemon=True).start()
        konec()

    # ------------------------------------------------------------------ porocilo za ploscico
    def porocilo(self, ob_koncu: Callable[[dict], None]) -> None:
        """Porocilo za ploscico »Info« (klic na glavni niti); prostor na disku se osvezi najvec vsakih 60 s."""
        for kid, z in list(self.kanali.zivi.items()):
            if z.aplikacija is not None and kid not in self.pid_spleta:
                self._sonda_ce_je_cas(kid, 10)       # plosca je odprta: neznan proces poskusi najti zdaj
        if time.monotonic() - self._disk["cas"] > DISK_VELJA_S and not self._disk_tece:
            self._osvezi_disk(lambda: ob_koncu(self._sestavi()))
            return
        ob_koncu(self._sestavi())

    def _sestavi(self) -> dict:
        meritve = self._vse_meritve(self._prej_ogled)
        vrstice = []
        from core import spletni_klepeti
        for k in self.kanali.kanali.seznam():
            vnos = spletni_klepeti.po_id(k.get("katalog", "")) or {}
            program = spletni_klepeti.je_program(vnos)
            m = meritve.get(k["id"]) if k["id"] in self.kanali.zivi else None
            v = self._vrstica(k["id"], k.get("ime", ""), "program" if program else "splet", bool(k.get("vklopljen")), m)
            if program:
                v["disk"] = None
                v["ni_merljivo"].append("disk")
                v["razlog_disk"] = "program"
            else:
                v["disk"] = self._disk["splet"].get(_domena(k.get("url", "")), 0)
                v["razlog_disk"] = "domena"
            vrstice.append(v)
        so = self.sporocila()
        if so is not None:
            try:
                kanali_api = list(so.seznam_kanalov() or [])
            except Exception:  # noqa: BLE001
                kanali_api = []
            for k in kanali_api:
                v = self._vrstica(k["id"], k.get("ime", ""), k.get("vrsta", "api"), bool(k.get("vklopljen", True)), None)
                v["razlog"] = "safeer"
                v["disk"] = self._disk["api"].get(k["id"])
                if v["disk"] is None:
                    v["ni_merljivo"].append("disk")
                v["razlog_disk"] = "baza"
                vrstice.append(v)
        skupno = {}
        for kljuc in ("_safeer", "_omrezje", "_drugi"):
            m = meritve.get(kljuc) or {}
            p = self.zgodovina.povzetek(kljuc)
            skupno[kljuc[1:]] = {"mem_trenutno": m.get("mem"), "cpu_trenutno": m.get("cpu"), "mem_ura": p["mem_ura"],
                                 "mem_zagon": p["mem_zagon"], "cpu_ura": p["cpu_ura"], "cpu_zagon": p["cpu_zagon"],
                                 "procesov": m.get("procesov", 0), "priblizek": bool(m.get("priblizek"))}
        return {"kanali": vrstice, "skupaj": _p.sestej(vrstice), "skupno": skupno,
                "vzorec_s": _p.VZOREC_S, "okno_s": _p.OKNO_S, "vzorcev": self.vzorcev,
                "cena_ms": round(self.cena_s / self.vzorcev * 1000, 2) if self.vzorcev else None,
                "disk_cas_s": round(time.monotonic() - self._disk["cas"]) if self._disk["cas"] > 0 else None}

    def _vrstica(self, kid: str, ime: str, vrsta: str, vklopljen: bool, m: Optional[dict]) -> dict:
        p = self.zgodovina.povzetek(kid)
        v = {"id": kid, "ime": ime, "vrsta": vrsta, "vklopljen": vklopljen, "mem_trenutno": None, "cpu_trenutno": None,
             "mem_ura": p["mem_ura"], "mem_zagon": p["mem_zagon"], "cpu_ura": p["cpu_ura"], "cpu_zagon": p["cpu_zagon"],
             "vzorcev": p["vzorcev"], "razlog": "", "deljeno": False, "priblizek": False, "ni_merljivo": []}
        if m is not None:
            v.update(mem_trenutno=m["mem"], cpu_trenutno=m["cpu"], razlog=m["razlog"], deljeno=bool(m.get("deljeno")),
                     priblizek=bool(m.get("priblizek")))
        if vklopljen and (m is None or m["razlog"]):
            v["razlog"] = v["razlog"] or ("nalaga" if vrsta in ("splet", "program") else "safeer")
            v["ni_merljivo"] += ["mem_trenutno", "mem_ura", "mem_zagon", "cpu_trenutno", "cpu_ura", "cpu_zagon"]
        return v
