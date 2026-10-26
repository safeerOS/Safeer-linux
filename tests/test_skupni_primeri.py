"""Naloga 134: skupni preizkusni primeri za Safeer OS Android (tests/SkupniPrimeriTest.kt) in namizje (ta datoteka).

Datoteka tests/skupni-primeri/debrid-serije.json je ista v repozitorijih Android-tv, Safeer-linux in Safeer-windows:
pravilo, spremenjeno samo na eni strani, tu ali tam pade. null v primeru = ni vrednosti (None ali prazen niz).
"""
import base64
import json
import unittest
from pathlib import Path

from core import debrid_pravila as P, media_servers, skrivni_dodatki as S, usenet_pravila as U, webtor as W
from core import usenet_nntp as NN, usenet_nzb as NZ, usenet_yenc as Y

PRIMERI = Path(__file__).resolve().parent / "skupni-primeri" / "debrid-serije.json"
#: Webtor rezerva in dodatki z osebnim zetonom (25. 10. 2026) - ista datoteka kot na Androidu (veja webtor-rezerva).
PRIMERI_WEBTOR = Path(__file__).resolve().parent / "skupni-primeri" / "webtor-rezerva.json"
#: Lasten pogon Usenet (lastnik 25. 10. 2026 22:10): yEnc, NZB, kode NNTP - lastnik datoteke je Safeer-linux.
PRIMERI_USENET = Path(__file__).resolve().parent / "skupni-primeri" / "usenet-pogon.json"
#: Pravila iz PRIMERI_WEBTOR, ki jih namizje se nima - in zakaj. Novo pravilo v datoteki mora priti sem ali v izracunaj.
NI_NA_NAMIZJU = {
    "uskladitev_novejsi": "usklajevanje kljucev v ozjem krogu (secrets.sync) namizje se nima",
    "scit_primeren_za_ucenje": "Scit na namizju se gostiteljev ne uci (izmerjeno 25. 10.: seznami Webtorja ne blokirajo)",
    "webtor_nauceni_gostitelj": "Scit na namizju se gostiteljev ne uci",
}
#: Koraki izbire virov: namizje (usenet_pravila.vrstni_red_virov) ima korak »takoj« razdeljen na ⚡ in povezave.
KORAKI_ANDROID = {U.KORAK_USENET_TAKOJ: "USENET_PRIPRAVLJEN", U.KORAK_PREDPOMNJEN: "TAKOJ", U.KORAK_NEPOSREDNI: "TAKOJ",
                  U.KORAK_USENET_CAKAJ: "USENET_CAKANJE", U.KORAK_WEBTOR: "WEBTOR", U.KORAK_DEBRID_CAKAJ: "CAKANJE_DEBRID"}


def _koraki_kot_android(ima_usenet: bool) -> list:
    izid = []
    for k in U.vrstni_red_virov(ima_usenet, True):
        if not izid or izid[-1] != KORAKI_ANDROID[k]:
            izid.append(KORAKI_ANDROID[k])
    return izid


def _wt_kljuc(x):
    return None if x is None else W.kljuc(x[0], x[1])


def _meritev(m):
    return P.Meritev(m["ponudnik"], m["ping_ms"], m["bajtov"], m["cas_ms"])


def _ali_none(v):
    return v if v not in ("",) else None


def _b64(b):
    return base64.b64encode(b).decode("ascii")


def _yenc_izhod(telo):
    try:
        d = Y.dekodiraj(telo)
    except Y.NapakaYenc as e:
        return {"izid": e.izid}
    return {"izid": Y.OK, "ime": d.ime, "del": d.del_, "skupaj": d.skupaj, "velikost": d.velikost,
            "zacetek": d.zacetek, "konec": d.konec, "crc32": "%08x" % d.crc32, "crc_preverjen": d.crc_preverjen,
            "podatki_b64": _b64(d.podatki)}


def _nzb_izhod(podatki):
    try:
        n = NZ.razcleni(podatki)
    except NZ.NapakaNzb as e:
        return {"izid": e.izid}
    return {"izid": NZ.OK, "naslov": n.naslov, "ima_geslo": n.ima_geslo, "datoteke": [
        {"ime": d.ime, "skupine": list(d.skupine), "bajtov_nzb": d.bajtov_nzb, "manjka": d.manjka,
         "segmenti": [[x.stevilka, x.bajtov, x.id] for x in d.segmenti]} for d in n.datoteke]}


def _usenet(f, v):
    """Lasten pogon Usenet (core/usenet_yenc.py, usenet_nzb.py, usenet_nntp.py; Android isto v Kotlinu)."""
    if f == "yenc_dekodiraj":
        return _yenc_izhod(base64.b64decode(v["telo_b64"]))
    if f in ("nntp_telo", "yenc_iz_nntp"):
        r = NN.odpakiraj_telo(base64.b64decode(v["surovo_b64"]))
        if f == "yenc_iz_nntp":
            return {"izid": Y.PRIREZANO} if r is None else _yenc_izhod(r[0])
        return None if r is None else {"telo_b64": _b64(r[0]), "ostanek_b64": _b64(r[1])}
    if f == "nntp_izid":
        return NN.izid_odgovora(v["ukaz"], v["vrstica"])
    if f == "nntp_ukrep":
        return NN.ukrep_bazena(v["izid"], v["faza"], v["stara"], v["poskus"])
    if f == "nntp_sme_odpreti":
        return NN.sme_odpreti(v["ustavljen"], v["premor"], v["odprtih"], v["najvec"], v["uspela"], v["sonda"])
    if f == "nntp_premor":
        n, p = NN.nov_premor(v["najvec"], v["odprtih"], v["premor_s"], v["tece"], v["zmanjsaj"])
        return {"najvec": n, "premor_s": int(p)}
    if f == "nntp_poverilnica":
        return NN.varna_poverilnica(v["vrednost"])
    if f == "nntp_id_odgovora":
        return NN.id_odgovora_ustreza(v["vrstica"], v["id"])
    if f == "nntp_ponudnik":
        return NN.ponudnik(v["gostitelj"])
    if f == "nntp_zapah_odtis":
        r, g = NN.zapah_odtis(bytes.fromhex(v["sol_hex"]), v["ponudnik"], v["uporabnik"], v["geslo"])
        return {"racun": r, "geslo": g}
    if f == "nntp_id":
        return NZ.id_clanka(v["id"])
    if f == "varno_ime":
        return NZ.varno_ime(v["ime"])
    if f == "nzb_ime":
        return NZ.ime_iz_subject(v["subject"])
    if f == "nzb_razcleni":
        return _nzb_izhod(base64.b64decode(v["xml_b64"]) if "xml_b64" in v else v["xml"].encode("utf-8"))
    if f == "usenet_meje":
        return {"nzb_bajtov": U.NAJVEC_NZB_BAJTOV, "nzb_datotek": NZ.NAJVEC_DATOTEK,
                "nzb_segmentov": NZ.NAJVEC_SEGMENTOV, "nzb_elementov": NZ.NAJVEC_ELEMENTOV,
                "segmentov_datoteke": NZ.NAJVEC_SEGMENTOV_DATOTEKE,
                "telo_bajtov": NN.NAJVEC_TELO_BAJTOV, "del_bajtov": Y.NAJVEC_DEL_BAJTOV,
                "ime_znakov": NZ.NAJVEC_IME_ZNAKOV, "ime_bajtov": NZ.NAJVEC_IME_BAJTOV,
                "naslov_znakov": NZ.NAJVEC_NASLOV_ZNAKOV, "skupin": NZ.NAJVEC_SKUPIN,
                "vrstica_bajtov": NN.NAJVEC_VRSTICA_BAJTOV, "id_znakov": NZ.NAJVEC_ID_ZNAKOV,
                "poverilnica_bajtov": NN.NAJVEC_POVERILNICA_BAJTOV, "povezav_privzeto": NN.PRIVZETO_POVEZAV,
                "povezav_najvec": NN.NAJVEC_POVEZAV, "vrata": NN.VRATA, "prosta_najdlje_s": int(NN.PROSTA_NAJDLJE_S),
                "premor_od_s": int(NN.PREMOR_OD_S), "premor_brez_odprtih_s": int(NN.PREMOR_BREZ_ODPRTIH_S),
                "premor_do_s": int(NN.PREMOR_DO_S), "rast_bazena_s": int(NN.RAST_BAZENA_S),
                "ziva_prijava_s": int(NN.ZIVA_PRIJAVA_S), "zapah_ponovitev": NN.ZAPAH_PONOVITEV,
                "zapahov_najvec": NN.NAJVEC_ZAPAHOV}
    raise KeyError("neznano pravilo: " + f)


USENET_POGON = {"yenc_dekodiraj", "nntp_telo", "yenc_iz_nntp", "nntp_izid", "nntp_id", "varno_ime", "nzb_ime",
                "nzb_razcleni", "usenet_meje", "nntp_ukrep", "nntp_sme_odpreti", "nntp_premor", "nntp_poverilnica",
                "nntp_id_odgovora", "nntp_zapah_odtis", "nntp_ponudnik"}


def izracunaj(f, v):
    """Isto ime pravila kot v primerih (in v Kotlinu preslikano)."""
    if f in USENET_POGON:
        return _usenet(f, v)
    if f == "vrstni_red":
        return P.vrstni_red(set(v["z_kljucem"]), v["prednostna"])
    if f == "aktivna":
        return P.aktivna(set(v["z_kljucem"]), v["prednostna"], v["izklopljeno"])
    if f == "ocisti_kljuc":
        return P.ocisti_kljuc(v["vnos"])
    if f == "razlog_za_uporabnika":
        return P.razlog_za_uporabnika(v["napake"])
    if f == "poskusi_s_cakanjem":
        return P.poskusi_s_cakanjem(v["samo_predpomnjeno"], v["napake"])
    if f == "rd_vrsta_napake":
        return P.rd_vrsta_napake(v["http"], v["koda"])
    if f == "ad_vrsta_napake":
        return P.ad_vrsta_napake(v["http"], v["koda"])
    if f == "torbox_vrsta_napake":
        return P.torbox_vrsta_napake(v["http"], v["koda"])
    if f == "hashi_za_preverbo":
        return P.hashi_za_preverbo(v["hashi"])
    if f == "predpomnjeni_naprej":
        return P.predpomnjeni_naprej(v["hashi"], set(v["predpomnjeni"]))
    if f == "samodejni_torrent":
        return P.samodejni_torrent(v["aktivna"], v["hashi"], set(v["predpomnjeni"]))
    if f == "najhitrejsa":
        return P.najhitrejsa([_meritev(m) for m in v["meritve"]])
    if f == "opis_meritve":
        return P.opis_meritve(_meritev(v))
    if f == "izberi_datoteko":
        d = P.izberi_datoteko([P.Datoteka(x["id"], x["ime"], x["velikost"]) for x in v["datoteke"]], v["indeks"])
        return d.ime if d else None
    if f == "je_epizoda":
        return media_servers.stremio_je_epizoda(v["id"])
    if f == "id_epizode_imdb":
        return _ali_none(media_servers.stremio_id_epizode_imdb(v["imdb"] or "", v["id_epizode"], v["sezona"], v["epizoda"]))
    if f == "imdb_iz_meta":
        return _ali_none(media_servers.stremio_imdb_iz_meta({"imdb_id": v["imdb_polje"]}, v["id"]))
    # Grokov pregled 25. 10. 2026: (storitev, napaka) po vrstnem redu poskusov, pospravljanje samo svojih, meja odgovora.
    if f == "razlog_po_storitvah":
        return P.razlog_po_storitvah([tuple(x) for x in v["napake"]])
    if f == "cakalna_storitev":
        return P.cakalna_storitev(v["samo_predpomnjeno"], [tuple(x) for x in v["napake"]])
    if f == "ponudnik_napake":
        return P.ponudnik_napake([tuple(x) for x in v["napake"]])
    if f == "rd_dodano_ms":
        return P.rd_dodano_ms(v["added"])
    if f == "ad_dodano_ms":
        return P.ad_dodano_ms(v["upload_date"])
    if f == "dodal_smo_mi":
        return P.dodal_smo_mi(v["dodano_ms"], v["odgovor_ms"])
    if f == "najvec_odgovora":
        return P.NAJVEC_ODGOVORA
    # Vrstni red virov (lastnik 25. 10. 2026 07:25): Usenet, ki ga ima TorBox pripravljenega, gre prvi.
    if f == "vrstni_red_virov":
        return U.vrstni_red_virov(v["usenet"], v["webtor"])
    if f == "usenet_za_takojsnjo":
        return U.za_takojsnjo(v["gb"])
    if f == "usenet_za_samodejno":
        return U.za_samodejno(v["gb"])
    if f == "usenet_najboljsa_pripravljena":
        return U.najboljsa_pripravljena(v["pripravljene"])
    # Dodatki z osebnim zetonom v naslovu (core/skrivni_dodatki.py, Android SkrivnostiPravila.kt).
    if f == "skrivna_predpona_dodatka":
        return S.skrivna_predpona_dodatka(v["naslov"])
    if f == "skrivna_predpona_toka":
        return S.skrivna_predpona_toka(v["naslov"])
    if f == "v_nadomestek":
        return S.v_nadomestek(v["naslov"])
    if f == "za_prikaz":
        return S.za_prikaz(v["naslov"])
    if f == "odstrani_tok_ob_shranjevanju":
        return S.odstrani_tok_ob_shranjevanju(v["osnova"], v["tok"])
    # Webtor rezerva (core/webtor.py, Android WebtorPravila.kt).
    if f == "webtor_oznaka":
        return list(W.razcleni(v["ime"]))
    if f == "je_webtor_dodatek":
        return W.je_webtor_dodatek(v["id"], v["osnova"])
    if f == "webtor_odlocitev":
        return W.odlocitev(v["koda"], v["prvi_bajt_ms"], v["potekel"], v.get("vsebina"))
    if f == "webtor_rok_sonde":
        return W.rok_sonde(v["zacetek_prve"], v["zdaj"], v["poskusov"])
    if f == "webtor_steje_kot_poskus":
        return W.steje_kot_poskus(v["izid"], v["trajanje_ms"])
    if f == "webtor_vrstni_red":
        return W.vrstni_red([_wt_kljuc(x) for x in v["nasi"]], [(_wt_kljuc(w[:2]), w[2]) for w in v["webtor"]],
                            v["imamo_torbox"], v.get("samo_takoj", False), v.get("datoteke"))
    # Verzija 3 (Android webtor-popravek, 25. 10. 2026 popoldne): datoteka iz JWT, pregled vsebine sonde.
    if f == "webtor_kljuc_toka":
        k = W.kljuc_webtor(v["hash"], v["url"])
        return list(k) if k else None
    if f == "webtor_je_video_ime":
        return W.je_video_ime(v["ime"])
    if f == "webtor_datoteka":
        return W.datoteka(v["idx"], v["ime_toka"], v["nas_idx"], v["nas_ime"])
    if f == "webtor_posoda":
        return W.posoda(bytes.fromhex(v["glava_hex"]))
    if f == "webtor_avi_kodek":
        return W.avi_kodek(bytes.fromhex(v["glava_hex"]))
    if f == "webtor_pregled":
        return list(W.pregled(v["vrsta"], bytes.fromhex(v["glava_hex"]), v["skupaj"], float(v["pricakovano_gb"]),
                              lambda m: m in v["podprti"]))
    if f == "webtor_skupna_velikost":
        return W.skupna_velikost(v["koda"], v["content_range"], v["content_length"])
    if f == "vrstni_red_korakov":
        return _koraki_kot_android(v["ima_usenet"])
    if f == "izberi_usenet":
        # Debrid.usenet_takoj odloca s tem pravilom (25. 10. 2026; prej svoja zanka) - isti primeri kot Android.
        return U.izberi_usenet(v["izidi"], v["rok_potekel"])
    if f == "scit_dovoljena":
        return W.scit_dovoljena(v["ime"], v["naucene"], v["zdaj"])
    raise KeyError("neznano pravilo: " + f)


class SkupniPrimeri(unittest.TestCase):
    def test_vsi_primeri(self):
        self._preveri(PRIMERI, set(), 60)

    def test_webtor_rezerva(self):
        self._preveri(PRIMERI_WEBTOR, set(NI_NA_NAMIZJU), 130)

    def test_usenet_pogon(self):
        self._preveri(PRIMERI_USENET, set(), 410)  # v4 (zaklep racuna, pregleda Grok 43 in 44)

    def _preveri(self, pot, preskoci: set, najmanj: int):
        koren = json.loads(pot.read_text(encoding="utf-8"))
        self.assertTrue(preskoci <= {p["f"] for p in koren["primeri"]}, "NI_NA_NAMIZJU ima pravilo, ki ga ni vec")
        napake = []
        for p in koren["primeri"]:
            if p["f"] in preskoci:
                continue
            try:
                dobljeno = izracunaj(p["f"], p["vhod"])
            except Exception as e:  # noqa: BLE001 - izjema je napaka primera, ne konec preizkusa
                dobljeno = "izjema %s: %s" % (type(e).__name__, e)
            if dobljeno != p["izhod"]:
                napake.append("%s %s: pricakovano %r, dobljeno %r" % (p["f"], p["vhod"], p["izhod"], dobljeno))
        self.assertEqual(napake, [], "\n".join(napake))
        self.assertGreaterEqual(len(koren["primeri"]), najmanj)


if __name__ == "__main__":
    unittest.main()
