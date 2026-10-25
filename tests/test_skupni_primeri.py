"""Naloga 134: skupni preizkusni primeri za Safeer OS Android (tests/SkupniPrimeriTest.kt) in namizje (ta datoteka).

Datoteka tests/skupni-primeri/debrid-serije.json je ista v repozitorijih Android-tv, Safeer-linux in Safeer-windows:
pravilo, spremenjeno samo na eni strani, tu ali tam pade. null v primeru = ni vrednosti (None ali prazen niz).
"""
import json
import unittest
from pathlib import Path

from core import debrid_pravila as P, media_servers, skrivni_dodatki as S, usenet_pravila as U, webtor as W

PRIMERI = Path(__file__).resolve().parent / "skupni-primeri" / "debrid-serije.json"
#: Webtor rezerva in dodatki z osebnim zetonom (25. 10. 2026) - ista datoteka kot na Androidu (veja webtor-rezerva).
PRIMERI_WEBTOR = Path(__file__).resolve().parent / "skupni-primeri" / "webtor-rezerva.json"
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


def izracunaj(f, v):
    """Isto ime pravila kot v primerih (in v Kotlinu preslikano)."""
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
