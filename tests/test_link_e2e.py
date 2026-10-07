"""Zascita ukazov od naprave do naprave (core/link_e2e): dogovor, sifriranje, ponarejanje in ponovitve.

Dve napravi (in po potrebi tretja, ki se dela, da je prva) sta povezani prek lazne poti, ki se obnasa kot sredisce:
sporocilu vpise posiljatelja in ga da naslovniku. »Sredisce« v preizkusih tudi bere, spreminja in ponavlja sporocila -
prav to mora zascita zdrzati. Vrednosti v razredu Vektorji so enake kot v preizkusu na Androidu (tests/E2eTest.kt):
obe izvedbi morata iz istih vhodov dobiti iste bajte.
"""
import base64
import hashlib
import json
import unittest

from core import link_e2e, link_krog
from dostop_za_preizkus import setUpModule, tearDownModule  # noqa: F401 - zapis dovoljenj v zacasni datoteki

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    KRIPTO = True
except Exception:  # noqa: BLE001
    KRIPTO = False


def _spki(zasebni) -> str:
    return base64.b64encode(zasebni.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).decode()


class _Naprava:
    """Ena naprava v preizkusu: kljuc naprave, svoj krog (id -> kljuc) in upravitelj zascite."""

    def __init__(self, omrezje: "_Omrezje", pripona: str = "", zasebni=None) -> None:
        # `zasebni`: kljuc druge naprave v preizkusu - tako nastane drug PROGRAM iste naprave (isti kljuc, druga pripona).
        self.zasebni = zasebni or ec.generate_private_key(ec.SECP256R1())
        self.kljuc = _spki(self.zasebni)
        self.jedro = link_krog.id_iz_kljuca(self.kljuc)
        self.id = self.jedro + pripona
        self.krog = {}
        self.prejeta = []          # (notranje sporocilo, id posiljatelja, jedro iz kljuca)
        self.seje = []
        self.podpisov = 0          # kolikokrat je naprava podpisala s kljucem naprave
        self.zdaj = 1000.0
        self.omrezje = omrezje
        self.upravitelj = link_e2e.Upravitelj(
            moj_id=lambda: self.id,
            poslji=lambda s: omrezje.poslji(self.id, s),
            podpisi=self._podpisi,
            kljuc_za=lambda i: self.krog.get(i),
            preveri=link_krog.preveri_podpis,
            id_iz_kljuca=link_krog.id_iz_kljuca,
            ob_sporocilu=lambda s, od, jedro: self.prejeta.append((s, od, jedro)),
            ob_seji=self.seje.append,
            ura=lambda: self.zdaj)
        omrezje.naprave[self.id] = self

    def _podpisi(self, bajti: bytes) -> str:
        self.podpisov += 1
        return base64.b64encode(self.zasebni.sign(bajti, ec.ECDSA(hashes.SHA256()))).decode()

    def pozna(self, *druge: "_Naprava") -> "_Naprava":
        for d in druge:
            self.krog[d.id] = d.kljuc
        return self


class _Omrezje:
    """Pot prek sredisca: vpise posiljatelja, sporocilo zapise (»sredisce vidi vse«) in ga dostavi takoj ali na roko."""

    def __init__(self, takoj: bool = True) -> None:
        self.naprave = {}
        self.videno = []            # vse, kar je slo cez sredisce (kot JSON niz - tako ga vidi sredisce)
        self.cakajo = []
        self.takoj = takoj
        self.spremeni = None        # funkcija (sporocilo) -> sporocilo | None: zlonamerno sredisce

    def poslji(self, od: str, sporocilo: dict) -> bool:
        s = json.loads(json.dumps(sporocilo))       # sredisce sporocilo razclene in zapise znova
        s["sender"] = od
        self.videno.append(json.dumps(s, ensure_ascii=False))
        if self.spremeni is not None:
            s = self.spremeni(s)
            if s is None:
                return True
        if self.takoj:
            self._dostavi(s)
        else:
            self.cakajo.append(s)
        return True

    def _dostavi(self, s: dict) -> None:
        cilj = self.naprave.get(str(s.get("target") or ""))
        if cilj is not None:
            cilj.upravitelj.prejmi(s)

    def dostavi_vse(self) -> None:
        while self.cakajo:
            self._dostavi(self.cakajo.pop(0))

    def dostavi_vse_razen(self, izpusti) -> None:
        """Dostavi vse, kar caka, razen sporocil, za katera `izpusti(sporocilo)` vrne True (ta sredisce zavrze)."""
        while self.cakajo:
            s = self.cakajo.pop(0)
            if not izpusti(s):
                self._dostavi(s)


UKAZ = {"id": "u1", "type": "control.command", "payload": {"action": "files.list", "args": {"path": "share:0:"}}}


def _opis_sporocila(sporocilo: dict) -> dict:
    """Kar upravitelj o poslanem sporocilu pove klicatelju ob sprejemu ali zavrnitvi (link_e2e._opis)."""
    return {"id": sporocilo["id"], "type": sporocilo["type"]}


@unittest.skipUnless(KRIPTO, "ni python3-cryptography")
class Vektorji(unittest.TestCase):
    """Iste vrednosti kot tests/E2eTest.kt: izvedbi se morata ujemati v bajt."""
    SID = "AAECAwQFBgcICQoLDA0ODw"
    NA = "AAECAwQFBgcICQoLDA0ODw=="
    NB = "EBESExQVFhcYGRobHB0eHw=="
    A = "n-00112233445566aa-control"
    B = "n-8899aabbccddeeff-os"
    EPK_A = ("MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEAhfmF/C2RDkoJ4+WmZ5pojpPLBUr321s32bluAKC1O0ZSn3ry5dxLS3aPKhaqHZaVvRfx1hZllLyiXxlMG5XlA==")
    EPK_B = ("MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE1lqTl3yqPRsIGFL/V6eeRl8WYFdzBLrq1QXdOkhYnPNQGF6JU3LfYiHqOhN1V+Rz/dtnVfBb1QfDxTP86ckShQ==")
    Z = "ccfc261f58193c98ca4ad4a53bbac6f0ee29bc4d48438090446908622ca79af6"

    def test_hkdf_rfc5869(self):
        okm = link_e2e.hkdf(bytes.fromhex("0b" * 22), bytes.fromhex("000102030405060708090a0b0c"),
                            bytes.fromhex("f0f1f2f3f4f5f6f7f8f9"), 42)
        self.assertEqual(okm.hex(), "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865")

    def test_ecdh_s_stalnima_kljucema(self):
        a = ec.derive_private_key(int("11" * 32, 16), ec.SECP256R1())
        b = ec.derive_private_key(int("22" * 32, 16), ec.SECP256R1())
        self.assertEqual((_spki(a), _spki(b)), (self.EPK_A, self.EPK_B))
        self.assertEqual(link_e2e.ecdh(a, self.EPK_B).hex(), self.Z)
        self.assertEqual(link_e2e.ecdh(b, self.EPK_A).hex(), self.Z)

    def test_gradivo_seje(self):
        k = link_e2e.izpelji(bytes.fromhex(self.Z), self.SID, self.NA, self.NB, self.A, self.B)
        self.assertEqual(k.k_ab.hex(), "0fcd326060beda1c556be1cae5472d82539f08edf6da6cdee256556a2757d52c")
        self.assertEqual(k.p_ab.hex(), "404c35a1")
        self.assertEqual(k.k_ba.hex(), "8c001903c4e631f20705439f9644be041298ddb04aaf1b2265316ab8330c19b6")
        self.assertEqual(k.p_ba.hex(), "ecd51692")

    def test_podpisani_bajti(self):
        self.assertEqual(hashlib.sha256(link_e2e.podatki_ponudbe(self.SID, self.A, self.B, self.NA, self.EPK_A)).hexdigest(),
                         "cec043e390432a21fc765a77d328204e622a108de1f5f33281e08558df3d1b61")
        self.assertEqual(hashlib.sha256(link_e2e.podatki_odgovora(self.SID, self.B, self.A, self.NA, self.NB,
                                                                  self.EPK_A, self.EPK_B)).hexdigest(),
                         "d66390d0afdbb058047c562a4a07c28501d32a846b9669346a3c076d694186bb")

    def test_sifropis(self):
        k = link_e2e.izpelji(bytes.fromhex(self.Z), self.SID, self.NA, self.NB, self.A, self.B)
        dodatno = link_e2e.aad(self.SID, "ab", 7, 3, 0, 1)
        self.assertEqual(dodatno, b"safeer-link-e2e-msg-v1\nAAECAwQFBgcICQoLDA0ODw\nab\n7\n3\n0\n1")
        cistopis = b'{"type":"control.command","payload":{"action":"files.list"}}'
        sifropis = link_e2e.sifriraj(k.k_ab, k.p_ab, 7, cistopis, dodatno)
        self.assertEqual(sifropis.hex(),
                         "49885b611b9612dcb3db420031fa11c1fbb39d066a57a69f1d33d8f1b9b8de1d0f52b92f3a91fe0e0a3762020eb87d53"
                         "71d86c460291ff5304d400e68a4595f748e67b9db5f94af2c8d666db")
        self.assertEqual(link_e2e.desifriraj(k.k_ab, k.p_ab, 7, sifropis, dodatno), cistopis)
        with self.assertRaises(link_e2e.Napaka):
            link_e2e.desifriraj(k.k_ba, k.p_ba, 7, sifropis, dodatno)          # kljuc druge smeri
        with self.assertRaises(link_e2e.Napaka):
            link_e2e.desifriraj(k.k_ab, k.p_ab, 8, sifropis, dodatno)          # drug stevec


@unittest.skipUnless(KRIPTO, "ni python3-cryptography")
class Seja(unittest.TestCase):
    def setUp(self):
        self.o = _Omrezje()
        self.a = _Naprava(self.o, "-control")
        self.b = _Naprava(self.o, "-os")
        self.a.pozna(self.b)
        self.b.pozna(self.a)

    def test_ukaz_in_odgovor_prideta_zascitena_z_jedrom_iz_kljuca(self):
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, UKAZ))
        self.assertEqual(self.b.prejeta, [(UKAZ, self.a.id, self.a.jedro)])
        odgovor = {"id": "r1", "type": "control.result", "ref_id": "u1", "payload": {"ok": True, "data": {"items": ["a", "b"]}}}
        self.assertTrue(self.b.upravitelj.poslji(self.a.id, odgovor))
        self.assertEqual(self.a.prejeta, [(odgovor, self.b.id, self.b.jedro)])
        # Ena seja za obe smeri; obe strani vesta, da druga zascito zna.
        self.assertEqual(sum(1 for s in self.o.videno if '"data.offer"' in s), 1)
        self.assertEqual((self.a.seje, self.b.seje), ([self.b.jedro], [self.a.jedro]))
        self.assertTrue(self.a.upravitelj.ima_sejo(self.b.id) and self.b.upravitelj.ima_sejo(self.a.id))
        self.assertEqual(self.a.upravitelj.jedro_seje(self.b.id), self.b.jedro)

    def test_sredisce_ne_vidi_vsebine(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.b.upravitelj.poslji(self.a.id, {"type": "control.result", "payload": {"data": {"url": "https://10.0.0.5:8791/d/x?k=SKRIVNOST"}}})
        vse = "\n".join(self.o.videno)
        for sled in ("files.list", "share:0:", "control.command", "control.result", "SKRIVNOST", "10.0.0.5"):
            self.assertNotIn(sled, vse)
        self.assertEqual({json.loads(s)["type"] for s in self.o.videno}, {"data.offer", "data.answer", "data.chunk"})

    def test_sporocila_pred_odgovorom_pocakajo_in_pridejo_po_vrsti(self):
        o = _Omrezje(takoj=False)
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        for i in range(3):
            self.assertTrue(a.upravitelj.poslji(b.id, {"type": "control.command", "payload": {"n": i}}))
        self.assertEqual(len(o.cakajo), 1)                      # samo ponudba; ukazi cakajo na dogovor
        o.dostavi_vse()
        self.assertEqual([s["payload"]["n"] for s, _od, _j in b.prejeta], [0, 1, 2])

    def test_dolgo_sporocilo_gre_v_vec_delih(self):
        dolgo = {"type": "control.result", "payload": {"data": "č" * 150_000}}       # 300 kB v UTF-8
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.assertTrue(self.b.upravitelj.poslji(self.a.id, dolgo))
        self.assertEqual(self.a.prejeta[-1][0], dolgo)
        kosi = [json.loads(s) for s in self.o.videno if '"data.chunk"' in s and json.loads(s)["sender"] == self.b.id]
        self.assertGreater(len(kosi), 2)
        self.assertTrue(all(len(json.dumps(k)) < 200_000 for k in kosi))

    def test_prevec_dolgo_sporocilo_ne_gre(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.assertFalse(self.a.upravitelj.poslji(self.b.id, {"type": "control.result", "payload": "x" * (link_e2e.DOLZINA_DELA * link_e2e.NAJVEC_DELOV + 10)}))

    def test_naprave_brez_kljuca_v_krogu_ne_naslovimo(self):
        tuja = _Naprava(self.o, "-os")
        self.assertFalse(self.a.upravitelj.poslji(tuja.id, UKAZ))
        self.assertEqual(self.o.videno, [])

    def test_ponudbe_neznane_naprave_ne_sprejmemo(self):
        tuja = _Naprava(self.o, "-os").pozna(self.b)
        self.assertTrue(tuja.upravitelj.poslji(self.b.id, UKAZ))        # ponudba gre ven ...
        self.assertEqual(self.b.prejeta, [])                             # ... a b nima kljuca te naprave: brez odgovora
        self.assertFalse(any('"data.answer"' in s for s in self.o.videno))

    def test_hkratna_dogovora_obe_smeri_delujeta(self):
        o = _Omrezje(takoj=False)
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        a.upravitelj.poslji(b.id, {"type": "control.command", "payload": {"od": "a"}})
        b.upravitelj.poslji(a.id, {"type": "control.command", "payload": {"od": "b"}})
        o.dostavi_vse()
        self.assertEqual([s["payload"]["od"] for s, _o, _j in b.prejeta], ["a"])
        self.assertEqual([s["payload"]["od"] for s, _o, _j in a.prejeta], ["b"])
        a.upravitelj.poslji(b.id, {"type": "control.result", "payload": {"od": "a2"}})
        b.upravitelj.poslji(a.id, {"type": "control.result", "payload": {"od": "b2"}})
        o.dostavi_vse()
        self.assertEqual(b.prejeta[-1][0]["payload"]["od"], "a2")
        self.assertEqual(a.prejeta[-1][0]["payload"]["od"], "b2")

    def test_po_ponovnem_zagonu_prejemnika_ukaz_ne_gre_dvakrat_naslednji_pa_pride(self):
        zavrnjena = []
        self.a.upravitelj._ob_zavrnitvi = lambda s, besedilo, koda: zavrnjena.append((s["id"], koda))
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.b.upravitelj.pozabi_vse()                           # b se je znova zagnal: sej ne pozna vec
        self.b.prejeta.clear()
        drugi = {"id": "u2", "type": "control.command", "payload": {"action": "apps.list"}}
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, drugi))     # gre po seji, ki je b ne pozna vec ...
        self.assertEqual(self.b.prejeta, [])                             # ... in se NE poslje se enkrat
        self.assertEqual(zavrnjena, [("u2", "ni_seje")])                 # klicatelj izve takoj
        self.assertFalse(self.a.upravitelj.ima_sejo(self.b.id))
        tretji = {"id": "u3", "type": "control.command", "payload": {"action": "apps.list"}}
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, tretji))    # naslednji ukaz: nov dogovor
        self.assertEqual([s for s, _o, _j in self.b.prejeta], [tretji])
        self.assertEqual(sum(1 for s in self.o.videno if '"data.offer"' in s), 2)
        self.assertEqual(sum(1 for s in self.o.videno if '"data.error"' in s), 1)

    def test_po_izgubljeni_seji_se_zavrnitev_javi_samo_za_sveza_sporocila(self):
        zavrnjena = []
        self.a.upravitelj._ob_zavrnitvi = lambda s, besedilo, koda: zavrnjena.append(s["id"])
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.b.upravitelj.pozabi_vse()
        self.b.prejeta.clear()
        o = self.o
        o.takoj = False
        self.a.upravitelj.poslji(self.b.id, {"id": "u2", "type": "control.command", "payload": {}})
        self.a.zdaj += link_e2e.NEPOTRJENA_VELJAJO_S + 1        # obvestilo »ni seje« pride pozno: klicatelj je ze obupal
        o.dostavi_vse()
        self.assertEqual((self.b.prejeta, zavrnjena), ([], []))
        self.assertFalse(self.a.upravitelj.ima_sejo(self.b.id))

    def test_dogovor_brez_odgovora_se_zacne_znova_stari_ukazi_odpadejo(self):
        o = _Omrezje(takoj=False)
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        a.upravitelj.poslji(b.id, {"type": "control.command", "payload": {"n": 1}})
        o.cakajo.clear()                                         # ponudba se je izgubila
        a.zdaj += link_e2e.DOGOVOR_CAKA_S + 1
        a.upravitelj.poslji(b.id, {"type": "control.command", "payload": {"n": 2}})
        o.dostavi_vse()
        self.assertEqual([s["payload"]["n"] for s, _o, _j in b.prejeta], [2])

    def test_dogovor_brez_sporocila_dokaze_kljuc_obema(self):
        self.assertTrue(self.a.upravitelj.dogovori_se(self.b.id))
        self.assertEqual((self.a.seje, self.b.seje), ([self.b.jedro], [self.a.jedro]))
        self.assertEqual(self.b.prejeta, [])                                     # nobenega sporocila ni bilo
        self.assertEqual([json.loads(s)["type"] for s in self.o.videno], ["data.offer", "data.answer"])
        self.assertTrue(self.a.upravitelj.dogovori_se(self.b.id))                # seja je ze: nic novega
        self.assertEqual(len(self.o.videno), 2)
        self.a.upravitelj.poslji(self.b.id, UKAZ)                                # ukaz gre po ze dogovorjeni seji
        self.assertEqual([json.loads(s)["type"] for s in self.o.videno][2:], ["data.chunk"])
        self.assertEqual(self.b.prejeta[0][0]["id"], "u1")

    def test_dogovor_brez_sporocila_z_neznano_napravo_ne_gre(self):
        tujec = _Naprava(self.o, "-x")
        self.assertFalse(self.a.upravitelj.dogovori_se(tujec.id))
        self.assertFalse(self.a.upravitelj.dogovori_se(""))
        self.assertEqual(self.o.videno, [])

    def test_ukaz_med_dogovorom_brez_sporocila_pocaka_nanj(self):
        self.o.takoj = False
        self.assertTrue(self.a.upravitelj.dogovori_se(self.b.id))
        self.assertTrue(self.a.upravitelj.dogovori_se(self.b.id))                # dogovor je na poti: ne zacnemo drugega
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, UKAZ))
        self.assertEqual([s["type"] for s in self.o.cakajo], ["data.offer"])
        self.o.dostavi_vse()
        self.assertEqual([p[0]["id"] for p in self.b.prejeta], ["u1"])

    def test_pozabi_napravo(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.a.upravitelj.pozabi(self.b.id)
        self.assertFalse(self.a.upravitelj.ima_sejo(self.b.id))

    def test_seja_potece(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.a.zdaj += link_e2e.SEJA_VELJA_S + 1
        self.assertFalse(self.a.upravitelj.ima_sejo(self.b.id))

    def test_tuj_prenos_ni_nas(self):
        self.assertFalse(self.a.upravitelj.prejmi({"type": "data.offer", "sender": self.b.id,
                                                   "payload": {"session_id": "x", "purpose": "file"}}))
        self.assertFalse(self.a.upravitelj.prejmi({"type": "data.chunk", "sender": self.b.id,
                                                   "payload": {"session_id": "x", "index": 0, "data": "AA=="}}))
        self.assertFalse(self.a.upravitelj.prejmi({"type": "control.command", "sender": self.b.id, "payload": {}}))
        self.assertFalse(self.a.upravitelj.prejmi({"type": "data.error", "sender": self.b.id, "payload": {"session_id": "x"}}))


@unittest.skipUnless(KRIPTO, "ni python3-cryptography")
class ZlonamernoSredisce(unittest.TestCase):
    def setUp(self):
        self.o = _Omrezje()
        self.a = _Naprava(self.o, "-control")
        self.b = _Naprava(self.o, "-os")
        self.a.pozna(self.b)
        self.b.pozna(self.a)

    def test_zamenjan_enkratni_kljuc_v_ponudbi(self):
        _z, tuj_epk = link_e2e.nov_par()

        def spremeni(s):
            if s["type"] == "data.offer":
                s["payload"]["epk"] = tuj_epk
            return s
        self.o.spremeni = spremeni
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.assertEqual(self.b.prejeta, [])
        self.assertFalse(self.b.upravitelj.ima_sejo(self.a.id))

    def test_zamenjan_enkratni_kljuc_v_odgovoru(self):
        _z, tuj_epk = link_e2e.nov_par()

        def spremeni(s):
            if s["type"] == "data.answer":
                s["payload"]["epk"] = tuj_epk
            return s
        self.o.spremeni = spremeni
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.assertEqual(self.b.prejeta, [])
        self.assertFalse(self.a.upravitelj.ima_sejo(self.b.id))

    def test_sredisce_ne_more_sestaviti_ukaza(self):
        """Ponarejen ukaz v imenu a: sredisce pozna vse, kar je slo cezenj, a nima ne kljuca naprave ne kljuca seje."""
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.b.prejeta.clear()
        kos = next(json.loads(s) for s in self.o.videno if '"data.chunk"' in s)
        ponaredek = json.loads(json.dumps(kos))
        ponaredek["payload"]["seq"] = 5
        self.b.upravitelj.prejmi(ponaredek)                         # isti sifropis pod drugim stevcem
        ponaredek = json.loads(json.dumps(kos))
        ponaredek["payload"]["seq"], ponaredek["payload"]["data"] = 6, base64.b64encode(b"x" * 80).decode()
        self.b.upravitelj.prejmi(ponaredek)                         # izmisljen sifropis
        self.assertEqual(self.b.prejeta, [])

    def test_ponovljen_kos_se_ne_izvede_se_enkrat(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        kos = next(json.loads(s) for s in self.o.videno if '"data.chunk"' in s)
        self.b.upravitelj.prejmi(kos)
        self.b.upravitelj.prejmi(kos)
        self.assertEqual(len(self.b.prejeta), 1)

    def test_ponovljena_stara_ponudba_ne_da_uporabne_seje(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        ponudba = next(json.loads(s) for s in self.o.videno if '"data.offer"' in s)
        kos = next(json.loads(s) for s in self.o.videno if '"data.chunk"' in s)
        self.b.upravitelj.pozabi_vse()
        self.b.prejeta.clear()
        self.b.upravitelj.prejmi(ponudba)           # sredisce znova poda staro ponudbo: b odgovori z NOVIM kljucem ...
        self.b.upravitelj.prejmi(kos)               # ... zato stari kos pod novo sejo ne pomeni nicesar
        self.assertEqual(self.b.prejeta, [])

    def test_kos_od_druge_naprave_kot_seja(self):
        c = _Naprava(self.o, "-os")
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        kos = next(json.loads(s) for s in self.o.videno if '"data.chunk"' in s)
        self.b.prejeta.clear()
        kos["sender"] = c.id
        kos["payload"]["seq"] = 9
        self.b.upravitelj.prejmi(kos)
        self.assertEqual(self.b.prejeta, [])

    def test_ponudba_za_drugo_napravo_ali_z_drugim_posiljateljem(self):
        c = _Naprava(self.o, "-os").pozna(self.a)
        self.a.pozna(c)
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        ponudba = next(json.loads(s) for s in self.o.videno if '"data.offer"' in s)
        c.upravitelj.prejmi(dict(ponudba, target=c.id))                         # ponudba je podpisana za b, ne za c
        self.assertFalse(c.upravitelj.ima_sejo(self.a.id))
        self.b.upravitelj.pozabi_vse()
        self.b.upravitelj.prejmi(dict(ponudba, sender=c.id))                    # sredisce trdi, da jo je poslal c
        self.assertFalse(self.b.upravitelj.ima_sejo(self.a.id))

    def test_notranje_sporocilo_ne_more_biti_prenos(self):
        self.a.upravitelj.poslji(self.b.id, {"type": "data.offer", "payload": {"purpose": "link"}})
        self.assertEqual(self.b.prejeta, [])


@unittest.skipUnless(KRIPTO, "ni python3-cryptography")
class PodobnaOznaka(unittest.TestCase):
    """Naprava, ki se predstavi z oznako, podobno oznaki druge naprave, ostane to, kar je njen kljuc."""

    def test_vnos_s_podobno_oznako_in_svojim_kljucem_dobi_svoje_jedro(self):
        o = _Omrezje()
        moja = _Naprava(o, "-control")
        racunalnik = _Naprava(o, "-control")
        gost = _Naprava(o)
        gost.id = moja.jedro + "-x"                   # oznaka je videti kot moja naprava, kljuc je gostov
        o.naprave[gost.id] = gost
        racunalnik.krog = {moja.id: moja.kljuc, gost.id: gost.kljuc}
        gost.pozna(racunalnik)
        self.assertTrue(gost.upravitelj.poslji(racunalnik.id, UKAZ))
        self.assertEqual(len(racunalnik.prejeta), 1)
        _s, od, jedro = racunalnik.prejeta[0]
        self.assertEqual((od, jedro), (gost.id, gost.jedro))
        self.assertNotEqual(jedro, moja.jedro)

    def test_podobna_oznaka_brez_svojega_vnosa_ne_more_podpisati(self):
        """Racunalnik za oznako brez lastnega vnosa najde kljuc MOJE naprave (isto jedro): gost ga nima, podpis pade."""
        o = _Omrezje()
        moja = _Naprava(o, "-control")
        racunalnik = _Naprava(o, "-control")
        gost = _Naprava(o)
        gost.id = moja.jedro + "-x"
        o.naprave[gost.id] = gost
        racunalnik.krog = {moja.id: moja.kljuc, gost.id: moja.kljuc}     # tako ga razresi krog (po jedru)
        gost.pozna(racunalnik)
        gost.upravitelj.poslji(racunalnik.id, UKAZ)
        self.assertEqual(racunalnik.prejeta, [])
        self.assertEqual(racunalnik.seje, [])


@unittest.skipUnless(KRIPTO, "ni python3-cryptography")
class ZavrnitevSredisca(unittest.TestCase):
    """Sredisce nasega sporocila prenosa ni moglo dostaviti: klicatelj izve takoj (kot pri nezascitenem ukazu)."""

    def setUp(self):
        self.o = _Omrezje(takoj=False)
        self.a = _Naprava(self.o, "-control")
        self.b = _Naprava(self.o, "-os")
        self.a.pozna(self.b)
        self.b.pozna(self.a)
        self.zavrnjena = []
        self.sprejeta = []
        self.a.upravitelj._ob_zavrnitvi = lambda s, napaka, koda: self.zavrnjena.append((s, koda))
        self.a.upravitelj._ob_sprejemu = self.sprejeta.append

    def _potrditev(self, oznaka, stanje="rejected", koda="ni_naprave"):
        return {"id": "1", "type": "data.ack", "ref_id": oznaka, "status": stanje, "error": "Naprave ni.", "error_code": koda}

    def test_zavrnjena_ponudba_zavrne_cakajoce_ukaze(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        drugi = {"id": "u2", "type": "control.command", "payload": {}}
        self.a.upravitelj.poslji(self.b.id, drugi)
        ponudba = self.o.cakajo.pop(0)
        self.assertTrue(self.a.upravitelj.prejmi(self._potrditev(ponudba["id"])))
        self.assertEqual(self.zavrnjena, [(_opis_sporocila(UKAZ), "ni_naprave"), (_opis_sporocila(drugi), "ni_naprave")])
        # Naslednji ukaz ne caka na iztek starega dogovora, a novega tudi ne zacne takoj: po zavrnjeni ponudbi nekaj
        # sekund ne podpisemo nove (peti pregled: tipka daljinca ob napravi, ki je ni, je porabila mejo podpisov).
        self.assertFalse(self.a.upravitelj.poslji(self.b.id, UKAZ))
        self.assertEqual(self.o.cakajo, [])
        self.a.zdaj += link_e2e.NEUSPEL_DOGOVOR_CAKA_S + 0.1
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, UKAZ))
        self.assertEqual([s["type"] for s in self.o.cakajo], ["data.offer"])

    def test_zavrnjen_kos_zavrne_svoje_sporocilo_seja_ostane(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.o.dostavi_vse()
        drugi = {"id": "u2", "type": "control.command", "payload": {}}
        self.a.upravitelj.poslji(self.b.id, drugi)
        kos = self.o.cakajo.pop(0)
        self.assertTrue(self.a.upravitelj.prejmi(self._potrditev(kos["id"], koda="naprava_ni_povezana")))
        self.assertEqual(self.zavrnjena, [(_opis_sporocila(drugi), "naprava_ni_povezana")])
        self.assertTrue(self.a.upravitelj.ima_sejo(self.b.id))

    def test_sprejeta_potrditev_in_tuje_potrditve(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        ponudba = self.o.cakajo[0]
        self.assertTrue(self.a.upravitelj.prejmi(self._potrditev(ponudba["id"], stanje="accepted", koda="")))
        self.assertEqual(self.zavrnjena, [])
        self.assertFalse(self.a.upravitelj.prejmi(self._potrditev("drugo-1")))                 # ni nase sporocilo
        self.assertFalse(self.a.upravitelj.prejmi(dict(self._potrditev(ponudba["id"]), sender=self.b.id)))   # ni od sredisca
        self.o.dostavi_vse()
        self.assertEqual(len(self.b.prejeta), 1)
        self.assertEqual(self.sprejeta, [])       # sprejeta PONUDBA se ni sprejet ukaz (caka na odgovor naprave)

    def test_sprejeto_sporocilo_javi_sprejem_enkrat(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.o.dostavi_vse()                      # dogovor in prvi ukaz
        drugi = {"id": "u2", "type": "cast.url", "payload": {"url": "https://primer.si/"}}
        self.a.upravitelj.poslji(self.b.id, drugi)
        kos = self.o.cakajo[0]
        self.assertTrue(self.a.upravitelj.prejmi(self._potrditev(kos["id"], stanje="accepted", koda="")))
        self.assertEqual(self.sprejeta, [_opis_sporocila(drugi)])
        self.assertTrue(self.a.upravitelj.prejmi(self._potrditev(kos["id"], stanje="accepted", koda="")))   # ponovljena
        self.assertEqual(self.sprejeta, [_opis_sporocila(drugi)])
        self.assertEqual(self.zavrnjena, [])

    def test_dolgo_sporocilo_javi_sprejem_enkrat(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.o.dostavi_vse()
        dolgo = {"id": "u3", "type": "control.result", "payload": {"data": "x" * (2 * link_e2e.DOLZINA_DELA + 10)}}
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, dolgo))
        kosi = list(self.o.cakajo)
        self.assertEqual(len(kosi), 3)
        for k in kosi:
            self.assertTrue(self.a.upravitelj.prejmi(self._potrditev(k["id"], stanje="accepted", koda="")))
        self.assertEqual(len(self.sprejeta), 1)
        self.assertEqual(self.sprejeta[0]["id"], "u3")

    def test_stari_zapisi_o_poslanem_se_zavrzejo(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.o.dostavi_vse()
        drugi = {"id": "u2", "type": "control.command", "payload": {}}
        self.a.upravitelj.poslji(self.b.id, drugi)
        stari_kos = self.o.cakajo.pop(0)
        self.a.zdaj += link_e2e.IZHODNA_VELJAJO_S + 1
        self.a.upravitelj.poslji(self.b.id, {"id": "u4", "type": "control.command", "payload": {}})
        self.assertNotIn(stari_kos["id"], self.a.upravitelj._izhodna)
        seja = self.a.upravitelj._seje[self.a.upravitelj._za[self.b.id]]
        self.assertEqual([z[3]["id"] for z in seja.zadnja], ["u4"])       # za ponovitev hranimo samo sveze
        # Pozna zavrnitev starega kosa ne javi nicesar (klicatelj je ze zdavnaj javil iztek).
        self.assertTrue(self.a.upravitelj.prejmi(self._potrditev(stari_kos["id"])))
        self.assertEqual(self.zavrnjena, [])


class _LazniOdjemalec:
    """Vticnica do sredisca za core/link_hub.Povezava: kar povezava poslje, gre »srediscu«; kar sredisce da, pride v vrsto."""

    def __init__(self, sredisce, device_id):
        self.sredisce, self.device_id, self.vrsta = sredisce, device_id, []

    def poslji(self, besedilo):
        self.sredisce.sprejmi(self.device_id, json.loads(besedilo))

    def prejmi(self):
        return self.vrsta.pop(0) if self.vrsta else None

    def zapri(self):
        pass


class _LaznoSredisce:
    def __init__(self):
        self.povezave, self.videno = {}, []

    def sprejmi(self, od, sporocilo):
        sporocilo["sender"] = od
        self.videno.append(json.dumps(sporocilo, ensure_ascii=False))
        cilj = self.povezave.get(str(sporocilo.get("target") or ""))
        if cilj is not None:
            cilj.odjemalec.vrsta.append(json.dumps(sporocilo))

    def tok(self):
        """Povezave berejo, dokler je kaj v vrstah (kot bralne niti)."""
        for _ in range(50):
            if not any(p.odjemalec.vrsta for p in self.povezave.values()):
                return
            for p in self.povezave.values():
                p.tece = True
                p._poslusaj()
                p.odjemalec = p._lazni
                p.tece = True


@unittest.skipUnless(KRIPTO, "ni python3-cryptography")
class OdjemalecLinka(unittest.TestCase):
    """core/link_hub.Povezava: zasciteni tipi gredo napravi z zascito samo po seji, drugi kot prej."""

    def _povezava(self, pripona, zmoznosti_drugih=None):
        from core import link_hub
        zasebni = ec.generate_private_key(ec.SECP256R1())
        kljuc = _spki(zasebni)
        p = link_hub.Povezava("wss://127.0.0.1:1/ws", "", link_krog.id_iz_kljuca(kljuc) + pripona, "naprava", odtis="ab")
        p.kljuc, p.prejeto, p.seje = kljuc, [], []
        p._lazni = _LazniOdjemalec(self.sredisce, p.device_id)
        p.odjemalec, p.tece = p._lazni, True
        p.ob_sporocilu = p.prejeto.append
        p._zascita = link_e2e.Upravitelj(
            moj_id=lambda: p.device_id, poslji=p._poslji_surovo,
            podpisi=lambda b: base64.b64encode(zasebni.sign(b, ec.ECDSA(hashes.SHA256()))).decode(),
            kljuc_za=lambda i: self.kljuci.get(i), preveri=link_krog.preveri_podpis, id_iz_kljuca=link_krog.id_iz_kljuca,
            ob_sporocilu=p._zasciteno_sporocilo, ob_seji=p.seje.append, ob_zavrnitvi=p._zasciteno_zavrnjeno,
            ob_sprejemu=p._zasciteno_sprejeto)
        self.sredisce.povezave[p.device_id] = p
        self.kljuci[p.device_id] = kljuc
        return p

    def setUp(self):
        from unittest import mock
        from core import link_hub
        link_hub._VPRASANJA.clear()             # zapis vprasanj je skupen programu: vsak preizkus zacne s praznim
        self.sredisce, self.kljuci = _LaznoSredisce(), {}
        self.a = self._povezava("-control")
        self.b = self._povezava("-os")
        popravek = mock.patch("core.link_dostop.zahteva_zascito", lambda device_id: False)
        popravek.start()
        self.addCleanup(popravek.stop)
        seznam = [{"id": self.a.device_id, "capabilities": ["remote", link_e2e.ZMOZNOST]},
                  {"id": self.b.device_id, "capabilities": ["remote", link_e2e.ZMOZNOST]},
                  {"id": "stara-naprava", "capabilities": ["remote"]}]
        for p in (self.a, self.b):
            p._zapomni_zmoznosti(seznam)

    def test_ukaz_in_odgovor_gresta_zascitena_in_nosita_jedro(self):
        ukaz = {"id": "u1", "type": "control.command", "target": self.b.device_id, "payload": {"action": "files.list"}}
        self.assertTrue(self.a.poslji(ukaz))
        self.sredisce.tok()
        self.assertEqual(len(self.b.prejeto), 1)
        prejet = self.b.prejeto[0]
        self.assertEqual((prejet["type"], prejet["id"], prejet["sender"], prejet["payload"]),
                         ("control.command", "u1", self.a.device_id, {"action": "files.list"}))
        self.assertEqual(prejet["_zascita"], self.a.device_id[:18])
        self.assertNotIn("target", prejet)
        self.assertTrue(self.b.poslji({"id": "r1", "type": "control.result", "target": self.a.device_id, "ref_id": "u1",
                                       "payload": {"ok": True}}))
        self.sredisce.tok()
        self.assertEqual((self.a.prejeto[-1]["type"], self.a.prejeto[-1]["ref_id"], self.a.prejeto[-1]["_zascita"]),
                         ("control.result", "u1", self.b.device_id[:18]))
        self.assertNotIn("files.list", "\n".join(self.sredisce.videno))
        self.assertEqual({json.loads(s)["type"] for s in self.sredisce.videno}, {"data.offer", "data.answer", "data.chunk"})
        self.assertEqual((self.a.seje, self.b.seje), ([self.b.device_id[:18]], [self.a.device_id[:18]]))

    def test_nadaljuj_na_napravi_gre_zasciteno(self):
        self.assertIn("handoff.request", link_e2e.ZASCITENI_TIPI)
        self.assertTrue(self.a.poslji({"id": "h1", "type": "handoff.request", "target": self.b.device_id,
                                       "payload": {"url": "https://primer.si/film"}}))
        self.sredisce.tok()
        self.assertEqual([(s["type"], s["id"], s["_zascita"]) for s in self.b.prejeto],
                         [("handoff.request", "h1", self.a.device_id[:18])])
        self.assertNotIn("primer.si", "\n".join(self.sredisce.videno))

    def test_dokaz_kljuca_ob_seznamu_naprav(self):
        """Napravo, ki zascito prijavi, a je se nismo preverili, preverimo takoj, ko jo zagledamo v seznamu naprav."""
        seznam = {"id": "1", "type": "cast.devices", "devices": [
            {"id": self.a.device_id, "capabilities": ["remote", link_e2e.ZMOZNOST]},
            {"id": self.b.device_id, "capabilities": ["remote", link_e2e.ZMOZNOST]},
            {"id": "stara-naprava", "capabilities": ["remote"]}]}
        self.a.odjemalec.vrsta.append(json.dumps(seznam))
        self.sredisce.tok()
        self.assertEqual([json.loads(s)["type"] for s in self.sredisce.videno], ["data.offer", "data.answer"])
        self.assertEqual({json.loads(s)["target"] for s in self.sredisce.videno}, {self.a.device_id, self.b.device_id})
        self.assertEqual((self.a.seje, self.b.seje), ([self.b.device_id[:18]], [self.a.device_id[:18]]))
        self.assertEqual((self.a.prejeto, self.b.prejeto), ([seznam], []))      # seznam gre naprej programu, drugega nic
        # Isti seznam se enkrat: seja je ze, novega dogovora ni.
        self.a.odjemalec.vrsta.append(json.dumps(seznam))
        self.sredisce.tok()
        self.assertEqual(len(self.sredisce.videno), 2)

    def test_dokaz_kljuca_najvec_enkrat_na_minuto_in_ne_ob_seji(self):
        from unittest import mock
        from core import link_hub
        kljuc_a = self.kljuci.pop(self.a.device_id)        # b nasega kljuca nima: ponudbo zavrne (»ni_kljuca«)
        ura = [1000.0]
        self.a._zascita._ura = lambda: ura[0]              # ista ura tudi za zascito (premor po neuspelem dogovoru)
        with mock.patch.object(link_hub, "_ura", lambda: ura[0]):
            self.a._dokazi_kljuce()
            self.sredisce.tok()
            self.assertEqual([json.loads(s)["type"] for s in self.sredisce.videno], ["data.offer", "data.error"])
            ura[0] += 30
            self.a._dokazi_kljuce()
            self.assertEqual(len(self.sredisce.videno), 2)                      # prezgodaj
            ura[0] += link_hub.DOKAZ_KLJUCA_NAJVEC_NA_S
            self.kljuci[self.a.device_id] = kljuc_a                             # b nas zdaj pozna
            self.a._dokazi_kljuce()
            self.sredisce.tok()
            self.assertEqual([json.loads(s)["type"] for s in self.sredisce.videno][2:], ["data.offer", "data.answer"])
            self.assertEqual(self.a.seje, [self.b.device_id[:18]])
            ura[0] += 2 * link_hub.DOKAZ_KLJUCA_NAJVEC_NA_S
            self.a._dokazi_kljuce()
            self.assertEqual(len(self.sredisce.videno), 4)                      # seja je: novega dogovora ni ...
            self.assertEqual(self.a.seje, [self.b.device_id[:18]] * 2)          # ... jedro pa se javi znova (zapis)
            self.a._zascita.pozabi(self.b.device_id)                            # seje ni vec
            self.a._zapomni_zmoznosti([{"id": self.b.device_id, "capabilities": ["remote"]}])
            ura[0] += 2 * link_hub.DOKAZ_KLJUCA_NAJVEC_NA_S
            self.a._dokazi_kljuce()
            self.assertEqual(len(self.sredisce.videno), 4)                      # zascite ne prijavi: nic
            self.a._zapomni_zmoznosti([{"id": self.b.device_id, "capabilities": ["remote", link_e2e.ZMOZNOST]}])
            with mock.patch("core.link_dostop.zahteva_zascito", lambda device_id: True):
                self.a._dokazi_kljuce()                                         # kljuc je ze dokazala, a seje ni: nov dogovor
            self.assertEqual(len(self.sredisce.videno), 5)

    def test_po_zasciteni_poti_gre_samo_dogovorjeni_nabor_tipov(self):
        """Naprava ne more po zasciteni poti poslati sporocila, ki ga sicer poslje samo sredisce."""
        self.a.poslji({"id": "u1", "type": "control.command", "target": self.b.device_id, "payload": {}})
        self.sredisce.tok()
        self.b.prejeto.clear()
        for tip in ("cast.devices", "trust.update", "pair.code", "cast.register", "data.offer", "sync.data", "share.screen", ""):
            self.a._zascita.poslji(self.b.device_id, {"id": "x", "type": tip, "devices": [], "payload": {}})
        self.sredisce.tok()
        self.assertEqual(self.b.prejeto, [])
        self.a._zascita.poslji(self.b.device_id, {"id": "c1", "type": "cast.url", "sender_name": "Televizor v dnevni sobi",
                                                  "payload": {"url": "https://primer.si/"}})
        self.sredisce.tok()
        self.assertEqual([(s["type"], s["sender"], s["_zascita"]) for s in self.b.prejeto],
                         [("cast.url", self.a.device_id, self.a.device_id[:18])])
        self.assertNotIn("sender_name", self.b.prejeto[0])              # imena za prikaz si naprava ne doloci sama

    def test_na_zasciten_ukaz_velja_samo_odgovor_iz_iste_seje(self):
        ukaz = {"id": "u1", "type": "control.command", "target": self.b.device_id, "payload": {"action": "files.list"}}
        self.assertTrue(self.a.poslji(ukaz))
        self.sredisce.tok()
        self.a.prejeto.clear()
        # Sredisce podtakne nezasciten odgovor: z oznako naprave brez zascite, brez oznake in z oznako vprasane naprave.
        for posiljatelj in ("stara-naprava", None, self.b.device_id):
            lazen = {"id": "r0", "type": "control.result", "ref_id": "u1", "payload": {"ok": True, "data": {"items": ["ponaredek"]}}}
            if posiljatelj:
                lazen["sender"] = posiljatelj
            self.a.odjemalec.vrsta.append(json.dumps(lazen))
        self.sredisce.tok()
        self.assertEqual(self.a.prejeto, [])
        # Odgovor iz preverjene seje DRUGE naprave (drug kljuc) prav tako ni odgovor vprasane.
        self.a._zasciteno_sporocilo({"id": "r1", "type": "control.result", "ref_id": "u1", "payload": {"ok": True}},
                                    "n-ffffffffffffffff-os", "n-ffffffffffffffff")
        self.assertEqual(self.a.prejeto, [])
        # Pravi odgovor pride.
        self.assertTrue(self.b.poslji({"id": "r2", "type": "control.result", "target": self.a.device_id, "ref_id": "u1",
                                       "payload": {"ok": True}}))
        self.sredisce.tok()
        self.assertEqual([(s["id"], s["_zascita"]) for s in self.a.prejeto], [("r2", self.b.device_id[:18])])

    def test_odgovor_starejse_naprave_na_nezasciten_ukaz_velja_kot_prej(self):
        self.assertTrue(self.a.poslji({"id": "u5", "type": "control.command", "target": "stara-naprava", "payload": {}}))
        self.a.odjemalec.vrsta.append(json.dumps({"id": "r5", "type": "control.result", "ref_id": "u5", "sender": "stara-naprava",
                                                  "payload": {"ok": True}}))
        self.sredisce.tok()
        self.assertEqual([s["id"] for s in self.a.prejeto], ["r5"])

    def test_ukaz_ki_ni_sel_ne_pusti_zapisa_o_vprasanju(self):
        self.kljuci.pop(self.b.device_id)
        self.assertFalse(self.a.poslji({"id": "u7", "type": "control.command", "target": self.b.device_id, "payload": {}}))
        self.assertNotIn("u7", self.a._vprasanja)

    def test_stari_napravi_in_drugim_tipom_kot_prej(self):
        self.a.poslji({"id": "u1", "type": "control.command", "target": "stara-naprava", "payload": {"action": "status"}})
        self.a.poslji({"id": "t1", "type": "share.text", "target": self.b.device_id, "payload": {"text": "zdravo"}})
        self.a.poslji({"id": "s1", "type": "sync.data", "target": "all", "payload": {}})
        self.a.poslji({"id": "sonda", "type": "control.command", "target": self.a.device_id, "payload": {}})
        self.assertEqual([json.loads(s)["type"] for s in self.sredisce.videno],
                         ["control.command", "share.text", "sync.data", "control.command"])

    def test_oznaka_zascite_iz_omrezja_se_ne_uposteva(self):
        self.b.odjemalec.vrsta.append(json.dumps({"id": "u1", "type": "control.command", "sender": self.a.device_id,
                                                  "_zascita": self.a.device_id[:18], "payload": {"action": "files.list"}}))
        self.sredisce.tok()
        self.assertEqual(len(self.b.prejeto), 1)
        self.assertNotIn("_zascita", self.b.prejeto[0])

    def test_brez_kljuca_naprave_ukaz_ne_gre_nezasciten(self):
        self.kljuci.pop(self.b.device_id)
        self.assertFalse(self.a.poslji({"id": "u1", "type": "control.command", "target": self.b.device_id, "payload": {}}))
        self.assertEqual(self.sredisce.videno, [])

    def test_naprava_ki_je_zascito_ze_vzpostavila_je_ne_izgubi_s_seznamom(self):
        from unittest import mock
        self.a._zapomni_zmoznosti([{"id": self.b.device_id, "capabilities": ["remote"]}])     # sredisce crta zmoznost
        with mock.patch("core.link_dostop.zahteva_zascito", lambda device_id: device_id == self.b.device_id):
            self.a.poslji({"id": "u1", "type": "control.command", "target": self.b.device_id, "payload": {}})
        self.assertEqual([json.loads(s)["type"] for s in self.sredisce.videno], ["data.offer"])

    def test_zavrnitev_sredisca_pride_kot_zavrnitev_ukaza(self):
        self.a.poslji({"id": "u1", "type": "control.command", "target": self.b.device_id, "payload": {}})
        ponudba = json.loads(self.sredisce.videno[0])
        self.b.odjemalec.vrsta.clear()
        self.a.odjemalec.vrsta.append(json.dumps({"id": "9", "type": "data.ack", "ref_id": ponudba["id"], "status": "rejected",
                                                  "error": "Naprave ni na Safeer Linku.", "error_code": "ni_naprave"}))
        self.sredisce.tok()
        self.assertEqual([(s["type"], s["ref_id"], s["status"], s["error_code"]) for s in self.a.prejeto],
                         [("control.ack", "u1", "rejected", "ni_naprave")])

    def test_kljuc_naprave_za_zascito_je_vezan_na_oznako(self):
        from unittest import mock
        from core import link_hub
        moja, tuja = self.a, self.b
        jedro = moja.device_id[:18]
        podobna = jedro + "-x"
        krog = link_krog.Krog()
        self.assertTrue(krog.dodaj(moja.device_id, moja.kljuc, "moja", "linux", "preizkus", 1000.0))
        self.assertTrue(krog.dodaj(podobna, tuja.kljuc, "podobna", "linux", "preizkus", 1000.0))
        self.assertTrue(krog.dodaj("stara", tuja.kljuc, "stara", "android", "preizkus", 1000.0))
        with mock.patch("core.link_krog.krog", lambda: krog):
            self.assertEqual(link_hub.kljuc_naprave_za_zascito(moja.device_id), moja.kljuc)
            # Oznaka z jedrom moje naprave, vpisana s kljucem tuje: velja kljuc, ki da jedro (moj), ne podtaknjeni.
            self.assertEqual(link_hub.kljuc_naprave_za_zascito(podobna), moja.kljuc)
            self.assertNotEqual(link_hub.kljuc_naprave_za_zascito(podobna), tuja.kljuc)
            # Sorodnik brez svojega vnosa ima isti kljuc.
            self.assertEqual(link_hub.kljuc_naprave_za_zascito(jedro + "-os"), moja.kljuc)
            self.assertEqual(link_hub.kljuc_naprave_za_zascito("stara"), tuja.kljuc)   # stara oznaka ni iz kljuca
            self.assertIsNone(link_hub.kljuc_naprave_za_zascito("neznana"))
            self.assertIsNone(link_hub.kljuc_naprave_za_zascito("n-0000000000000000-x"))   # tega jedra v krogu ni
        # Vnos MOJE oznake s tujim kljucem in brez pravega kljuca v krogu: podtaknjeni kljuc ne velja.
        prepisan = link_krog.Krog()
        self.assertTrue(prepisan.dodaj(moja.device_id, tuja.kljuc, "prepisana", "linux", "preizkus", 1000.0))
        with mock.patch("core.link_krog.krog", lambda: prepisan):
            self.assertIsNone(link_hub.kljuc_naprave_za_zascito(moja.device_id))
        # Vnos moje oznake s tujim kljucem pravega (pod oznako sorodnika) ne zasenci.
        zasencen = link_krog.Krog()
        self.assertTrue(zasencen.dodaj(moja.device_id, tuja.kljuc, "prepisana", "linux", "preizkus", 1000.0))
        self.assertTrue(zasencen.dodaj(jedro + "-brskalnik", moja.kljuc, "sorodnik", "linux", "preizkus", 1000.0))
        with mock.patch("core.link_krog.krog", lambda: zasencen):
            self.assertEqual(link_hub.kljuc_naprave_za_zascito(moja.device_id), moja.kljuc)
        # Umaknjen clan nima kljuca.
        umaknjen = link_krog.Krog()
        self.assertTrue(umaknjen.dodaj(moja.device_id, moja.kljuc, "moja", "linux", "preizkus", 1000.0))
        self.assertTrue(umaknjen.umakni(moja.device_id, "preizkus", 2000.0))
        with mock.patch("core.link_krog.krog", lambda: umaknjen):
            self.assertIsNone(link_hub.kljuc_naprave_za_zascito(moja.device_id))


@unittest.skipUnless(KRIPTO, "ni python3-cryptography")
class PregledPredIzdajo(unittest.TestCase):
    """Napake, ki jih je nasel neodvisni pregled pred izdajo (7. 10. 2026). Vsak preizkus je najprej padel."""

    def setUp(self):
        self.o = _Omrezje()
        self.a = _Naprava(self.o, "-control")
        self.b = _Naprava(self.o, "-os")
        self.a.pozna(self.b)
        self.b.pozna(self.a)

    def _ponudba(self, od: "_Naprava", za: "_Naprava", session_id: str) -> dict:
        """Veljavno podpisana ponudba naprave `od` z izbrano oznako seje (to lahko naredi vsaka naprava v krogu)."""
        _zasebni, epk = link_e2e.nov_par()
        nonce = base64.b64encode(b"n" * 16).decode()
        sig = base64.b64encode(od.zasebni.sign(link_e2e.podatki_ponudbe(session_id, od.id, za.id, nonce, epk),
                                               ec.ECDSA(hashes.SHA256()))).decode()
        return {"id": "x", "type": "data.offer", "sender": od.id, "target": za.id,
                "payload": {"session_id": session_id, "purpose": "link", "v": 2, "from": od.id, "to": za.id,
                            "nonce": nonce, "epk": epk, "sig": sig}}

    def test_ponarejeno_obvestilo_ni_seje_ne_ponovi_izvedenega_ukaza(self):
        """Sredisce v imenu b sporoci »seje ni«, ceprav je b ukaz ze izvedel: ukaz se NE sme izvesti se enkrat."""
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, UKAZ))
        self.assertEqual(len(self.b.prejeta), 1)
        kos = next(json.loads(s) for s in self.o.videno if '"data.chunk"' in s)
        for _ in range(3):          # tudi veckrat zapored
            sid = next(json.loads(s) for s in reversed(self.o.videno) if '"data.chunk"' in s)["payload"]["session_id"]
            self.a.upravitelj.prejmi({"id": "e", "type": "data.error", "sender": self.b.id,
                                      "payload": {"session_id": sid, "code": "ni_seje", "seq": 0}})
        self.assertEqual(kos["payload"]["seq"], 0)
        self.assertEqual(len(self.b.prejeta), 1, "ukaz se je po ponarejenem obvestilu izvedel znova")

    def test_ponudba_z_oznako_nasega_cakajocega_dogovora_ne_preusmeri_posiljanja(self):
        """a caka na odgovor b (oznaka seje S je v ponudbi vidna srediscu); c poslje svojo ponudbo z isto S.
        Sporocilo, ki ga a potem poslje napravi c, ne sme priti do b."""
        o = _Omrezje(takoj=False)
        a, b, c = _Naprava(o, "-control"), _Naprava(o, "-os"), _Naprava(o, "-tv")
        a.pozna(b, c)
        b.pozna(a)
        c.pozna(a)
        self.assertTrue(a.upravitelj.poslji(b.id, {"type": "control.command", "payload": {"za": "b"}}))
        sid = o.cakajo[0]["payload"]["session_id"]
        a.upravitelj.prejmi(self._ponudba(c, a, sid))
        o.dostavi_vse()
        self.assertEqual([s["payload"]["za"] for s, _od, _j in b.prejeta], ["b"])
        a.upravitelj.poslji(c.id, {"type": "control.command", "payload": {"za": "c"}})
        o.dostavi_vse()
        self.assertEqual([s["payload"]["za"] for s, _od, _j in b.prejeta], ["b"], "sporocilo za c je dobila naprava b")

    def test_po_obvestilu_ni_seje_klicatelj_izve_in_naslednji_ukaz_pride(self):
        zavrnjena = []
        self.a.upravitelj._ob_zavrnitvi = lambda s, besedilo, koda: zavrnjena.append((s.get("id"), koda))
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        sid = next(json.loads(s) for s in self.o.videno if '"data.chunk"' in s)["payload"]["session_id"]
        self.a.upravitelj.prejmi({"type": "data.error", "sender": self.b.id,
                                  "payload": {"session_id": sid, "code": "ni_seje", "seq": 0}})
        self.assertEqual(zavrnjena, [("u1", "ni_seje")])
        self.assertFalse(self.a.upravitelj.ima_sejo(self.b.id))
        tretji = {"id": "u3", "type": "control.command", "payload": {}}
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, tretji))
        self.assertEqual([s["id"] for s, _o, _j in self.b.prejeta], ["u1", "u3"])

    def test_obvestilo_druge_naprave_ali_z_drugo_kodo_seje_ne_zavrze(self):
        c = _Naprava(self.o, "-tv")
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        sid = next(json.loads(s) for s in self.o.videno if '"data.chunk"' in s)["payload"]["session_id"]
        self.a.upravitelj.prejmi({"type": "data.error", "sender": c.id,
                                  "payload": {"session_id": sid, "code": "ni_seje", "seq": 0}})
        self.a.upravitelj.prejmi({"type": "data.error", "sender": self.b.id,
                                  "payload": {"session_id": sid, "code": "ni_kljuca", "seq": 0}})
        self.assertTrue(self.a.upravitelj.ima_sejo(self.b.id))

    def test_sporocilo_ki_je_predolgo_cakalo_na_dogovor_ne_gre(self):
        o = _Omrezje(takoj=False)
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        zavrnjena = []
        a.upravitelj._ob_zavrnitvi = lambda s, besedilo, koda: zavrnjena.append((s.get("id"), koda))
        a.upravitelj.poslji(b.id, UKAZ)
        a.zdaj += link_e2e.V_VRSTI_VELJA_S + 1          # sredisce je odgovor zadrzalo
        o.dostavi_vse()
        self.assertEqual(b.prejeta, [])
        self.assertEqual(zavrnjena, [("u1", "cas")])
        self.assertTrue(a.upravitelj.ima_sejo(b.id))    # seja je nastala; novi ukazi gredo
        a.upravitelj.poslji(b.id, {"id": "u2", "type": "control.command", "payload": {}})
        o.dostavi_vse()
        self.assertEqual([s["id"] for s, _o, _j in b.prejeta], ["u2"])

    def test_prepozen_odgovor_ne_ustvari_seje(self):
        o = _Omrezje(takoj=False)
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        self.assertTrue(a.upravitelj.dogovori_se(b.id))
        a.zdaj += link_e2e.DOGOVOR_VELJA_S + 1
        o.dostavi_vse()
        self.assertFalse(a.upravitelj.ima_sejo(b.id))
        self.assertEqual(a.seje, [])

    def test_seja_s_poteklim_rokom_tudi_pri_prejemu_ne_velja(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.b.prejeta.clear()
        self.b.zdaj += link_e2e.SEJA_VELJA_S + 1
        self.a.upravitelj.poslji(self.b.id, {"id": "u2", "type": "control.command", "payload": {}})
        self.assertEqual(self.b.prejeta, [])
        self.assertEqual(sum(1 for s in self.o.videno if '"data.error"' in s), 1)

    def test_naprava_odstranjena_iz_kroga_izgubi_sejo(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.b.prejeta.clear()
        del self.b.krog[self.a.id]                  # uporabnik je napravo a na napravi b odstranil iz Linka
        self.a.upravitelj.poslji(self.b.id, {"id": "u2", "type": "control.command", "payload": {}})
        self.assertEqual(self.b.prejeta, [])
        self.assertFalse(self.b.upravitelj.ima_sejo(self.a.id))
        self.assertFalse(self.b.upravitelj.poslji(self.a.id, {"type": "control.result", "payload": {}}))

    def test_seja_ne_velja_ko_je_pod_oznako_v_krogu_drug_kljuc(self):
        c = _Naprava(self.o, "-tv")
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.b.prejeta.clear()
        self.b.krog[self.a.id] = c.kljuc            # pod oznako a je zdaj drug kljuc
        self.a.upravitelj.poslji(self.b.id, {"id": "u2", "type": "control.command", "payload": {}})
        self.assertEqual(self.b.prejeta, [])

    def test_nobeno_sporocilo_ne_vrze_izjeme(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        sid = next(json.loads(s) for s in self.o.videno if '"data.chunk"' in s)["payload"]["session_id"]
        cudna = [
            {"type": ["data.chunk"], "payload": {}},
            {"type": {"a": 1}},
            {"type": "data.offer", "sender": ["x"], "payload": {"purpose": "link", "session_id": ["x"], "from": {"a": 1},
                                                              "to": 5, "nonce": None, "epk": 1.5, "sig": [], "v": 2}},
            {"type": "data.offer", "sender": self.a.id,
             "payload": {"purpose": "link", "v": 2, "session_id": "\ud800", "from": self.a.id, "to": self.b.id,
                         "nonce": "\ud800", "epk": "\ud800", "sig": "\ud800"}},
            {"type": "data.answer", "sender": self.b.id, "payload": {"purpose": "link", "session_id": {"x": 1}, "from": [], "to": None}},
            {"type": "data.chunk", "sender": self.a.id, "payload": {"session_id": sid, "seq": "1", "m": [], "i": {}, "n": None, "data": 7}},
            {"type": "data.chunk", "sender": self.a.id, "payload": {"session_id": sid, "seq": 10 ** 30, "m": 0, "i": 0, "n": 1, "data": "AAAA"}},
            {"type": "data.chunk", "sender": self.a.id, "payload": {"session_id": sid, "seq": 5, "m": 0, "i": 0, "n": 1,
                                                                  "data": base64.b64encode(b"x" * (link_e2e.DOLZINA_DELA + 17)).decode()}},
            {"type": "data.error", "sender": self.a.id, "payload": {"session_id": [sid], "code": ["ni_seje"], "seq": "x"}},
            {"type": "data.ack", "ref_id": ["e2e-x"], "status": {}},
            {"type": "data.chunk", "payload": "niz"},
        ]
        for s in cudna:
            self.assertIn(self.b.upravitelj.prejmi(s), (True, False), s)
        self.assertEqual(len(self.b.prejeta), 1)
        self.assertTrue(self.b.upravitelj.ima_sejo(self.a.id))

    def test_notranje_sporocilo_s_tipom_ki_ni_niz_in_napaka_v_obdelavi(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.b.prejeta.clear()
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, {"type": ["control.command"], "payload": {}}))
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, {"type": None}))
        self.assertEqual(self.b.prejeta, [])

        def pade(sporocilo, od, jedro):
            raise RuntimeError("napaka v obdelavi")
        self.b.upravitelj._ob_sporocilu = pade
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, UKAZ))       # napaka pri prejemniku ne sme vreci izjeme
        self.assertTrue(self.b.upravitelj.ima_sejo(self.a.id))

    def test_ponovljena_stara_ponudba_po_ponovnem_zagonu_se_razresi(self):
        """b se znova zazene, sredisce mu ponovi staro ponudbo naprave a: b ima potem pod ISTO oznako sejo z drugim
        kljucem. Ko a poslje po svoji seji, b nepotrjeno sejo zavrze in to pove - naslednji ukaz pride."""
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        ponudba = next(json.loads(s) for s in self.o.videno if '"data.offer"' in s)
        self.b.upravitelj.pozabi_vse()
        self.b.prejeta.clear()
        self.b.upravitelj.prejmi(ponudba)
        self.a.upravitelj.poslji(self.b.id, {"id": "u2", "type": "control.command", "payload": {}})
        self.assertEqual(self.b.prejeta, [])
        self.assertFalse(self.b.upravitelj.ima_sejo(self.a.id))
        self.assertFalse(self.a.upravitelj.ima_sejo(self.b.id))
        self.a.upravitelj.poslji(self.b.id, {"id": "u3", "type": "control.command", "payload": {}})
        self.assertEqual([s["id"] for s, _o, _j in self.b.prejeta], ["u3"])

    def test_ponovljene_ponudbe_ne_izrinejo_delujoce_seje(self):
        from unittest import mock
        c, d = _Naprava(self.o, "-tv"), _Naprava(self.o, "-tablica")
        self.b.pozna(c, d)
        self.a.upravitelj.poslji(self.b.id, UKAZ)                  # seja a-b; na b jo potrdi prvi kos
        with mock.patch.object(link_e2e, "NAJVEC_SEJ", 2):
            self.b.upravitelj.prejmi(self._ponudba(c, self.b, "S-c"))      # nepotrjena seja iz ponudbe
            self.b.upravitelj.prejmi(self._ponudba(d, self.b, "S-d"))      # prostor naredi nepotrjena, ne delujoca
        self.assertTrue(self.b.upravitelj.ima_sejo(self.a.id))
        self.assertEqual(sorted(s.tuj_id for s in self.b.upravitelj._seje.values()), sorted([self.a.id, d.id]))

    def test_nedokoncanih_sporocil_je_omejeno(self):
        o = _Omrezje(takoj=False)
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        a.upravitelj.poslji(b.id, UKAZ)
        o.dostavi_vse()
        dolgo = {"type": "control.result", "payload": {"data": "x" * (link_e2e.DOLZINA_DELA + 10)}}      # dva dela
        for _ in range(link_e2e.NAJVEC_NEDOKONCANIH + 2):
            a.upravitelj.poslji(b.id, dolgo)
        prvi_deli = [s for s in o.cakajo if s["payload"]["i"] == 0]
        o.cakajo.clear()
        for s in prvi_deli:
            b.upravitelj.prejmi(s)                      # drugi deli nikoli ne pridejo
        seja = b.upravitelj._seje[a.upravitelj._za[b.id]]
        self.assertEqual(len(seja.deli), link_e2e.NAJVEC_NEDOKONCANIH)

    def test_naprava_ki_nas_nima_v_krogu_to_pove_takoj(self):
        tuja = _Naprava(self.o, "-os").pozna(self.b)       # tuja pozna b, b tuje ne
        zavrnjena = []
        tuja.upravitelj._ob_zavrnitvi = lambda s, besedilo, koda: zavrnjena.append((s.get("id"), koda))
        self.assertTrue(tuja.upravitelj.poslji(self.b.id, UKAZ))
        self.assertEqual(self.b.prejeta, [])
        self.assertEqual(zavrnjena, [("u1", "ni_kljuca")])
        self.assertEqual([json.loads(s)["type"] for s in self.o.videno], ["data.offer", "data.error"])


@unittest.skipUnless(KRIPTO, "ni python3-cryptography")
class OdjemalecPoPregledu(unittest.TestCase):
    """core/link_hub.Povezava po neodvisnem pregledu (ista lazna pot kot v OdjemalecLinka)."""
    _povezava = OdjemalecLinka._povezava
    setUp = OdjemalecLinka.setUp

    def _seznam(self):
        return {"id": "1", "type": "cast.devices", "devices": [
            {"id": self.a.device_id, "capabilities": ["remote", link_e2e.ZMOZNOST]},
            {"id": self.b.device_id, "capabilities": ["remote", link_e2e.ZMOZNOST]}]}

    def test_nezasciten_odgovor_brez_posiljatelja_ne_velja(self):
        self.a.odjemalec.vrsta.append(json.dumps({"id": "r1", "type": "control.result", "ref_id": "neznan", "payload": {"ok": True}}))
        self.a.odjemalec.vrsta.append(json.dumps({"id": "r2", "type": "control.result", "ref_id": "neznan",
                                                  "sender": "stara-naprava", "payload": {"ok": True}}))
        self.sredisce.tok()
        self.assertEqual([s["id"] for s in self.a.prejeto], ["r2"])

    def test_zapis_o_vprasanju_prezivi_novo_povezavo(self):
        self.assertTrue(self.a.poslji({"id": "u1", "type": "control.command", "target": self.b.device_id, "payload": {}}))
        self.sredisce.tok()
        nova = self._povezava("-znova")         # nov objekt povezave v istem programu (ponovna povezava s srediscem)
        nova.odjemalec.vrsta.append(json.dumps({"id": "r0", "type": "control.result", "ref_id": "u1",
                                                "sender": "stara-naprava", "payload": {"ok": True, "data": {"items": ["ponaredek"]}}}))
        self.sredisce.tok()
        self.assertEqual(nova.prejeto, [])

    def test_sprejem_sredisca_pride_kot_potrditev_ukaza(self):
        self.a.poslji({"id": "u1", "type": "control.command", "target": self.b.device_id, "payload": {}})
        self.sredisce.tok()
        kos = next(json.loads(s) for s in self.sredisce.videno if '"data.chunk"' in s)
        self.a.odjemalec.vrsta.append(json.dumps({"id": "9", "type": "data.ack", "ref_id": kos["id"], "status": "accepted"}))
        self.sredisce.tok()
        self.assertEqual([(s["type"], s["ref_id"], s["status"]) for s in self.a.prejeto],
                         [("control.ack", "u1", "accepted")])

    def test_napaka_pri_enem_sporocilu_ne_prekine_branja(self):
        prejeta = []

        def obdelaj(sporocilo):
            if sporocilo.get("id") == "pade":
                raise RuntimeError("napaka v obdelavi")
            prejeta.append(sporocilo.get("id"))
        self.a.ob_sporocilu = obdelaj
        for s in ({"id": "pade", "type": "share.text"}, {"id": "t", "type": ["x"]}, {"id": "ok", "type": "share.text"}):
            self.a.odjemalec.vrsta.append(json.dumps(s))
        self.a.tece = True
        self.a._poslusaj()                      # EN klic prebere vsa tri sporocila
        self.a.odjemalec = self.a._lazni
        self.assertEqual(prejeta, ["t", "ok"])
        self.assertEqual(self.a._lazni.vrsta, [])

    def test_program_po_ponovnem_zagonu_sam_obnovi_seje(self):
        """b se znova zazene (sej ne pozna vec, a ima se staro). Ob prvem seznamu naprav b sam zacne dogovor, zato
        naslednji ukaz naprave a pride po novi seji - brez »ni seje« in brez izgubljenega ukaza."""
        self.a.odjemalec.vrsta.append(json.dumps(self._seznam()))
        self.sredisce.tok()
        self.assertEqual([json.loads(s)["type"] for s in self.sredisce.videno], ["data.offer", "data.answer"])
        self.b._zascita.pozabi_vse()
        self.b._dokazi_kljucev.clear()
        self.b.odjemalec.vrsta.append(json.dumps(self._seznam()))
        self.sredisce.tok()
        self.assertEqual([json.loads(s)["type"] for s in self.sredisce.videno][2:], ["data.offer", "data.answer"])
        self.assertTrue(self.a.poslji({"id": "u1", "type": "control.command", "target": self.b.device_id, "payload": {}}))
        self.sredisce.tok()
        self.assertEqual([s["id"] for s in self.b.prejeto if s.get("type") == "control.command"], ["u1"])
        self.assertFalse(any('"data.error"' in s for s in self.sredisce.videno))


def _podpis(naprava: "_Naprava", bajti: bytes) -> str:
    return base64.b64encode(naprava.zasebni.sign(bajti, ec.ECDSA(hashes.SHA256()))).decode()


@unittest.skipUnless(KRIPTO, "ni python3-cryptography")
class DrugiPregled(unittest.TestCase):
    """Najdbe DRUGEGA neodvisnega pregleda (7. 10. 2026, po popravkih prvega). Vsak preizkus je najprej padel."""

    def test_veljavna_oznaka(self):
        for dobra in ("n-0123456789abcdef", "n-0123456789abcdef-os", "stara-naprava_1.2:3", "a" * 128):
            self.assertTrue(link_e2e.veljavna_oznaka(dobra), dobra)
        for slaba in ("", "a b", "a\nb", "a\rb", "a\tb", "a\x00b", "a\x7fb", "a\u0085b", "a\u2028b", "\u010d", "\ud800",
                      "a" * 129, None, 5, b"a", ["a"]):
            self.assertFalse(link_e2e.veljavna_oznaka(slaba), repr(slaba))

    def test_base64_in_oznaka_seje_strogo(self):
        """Iste vrednosti kot tests/E2eTest.kt (izvedbi morata sprejeti in zavrniti isto)."""
        for dober in ("AAAA", "AA==", "AAA="):
            self.assertTrue(link_e2e._veljaven_b64(dober, 64), dober)
        for slab in ("", "AAA", "AA=A", "A===", "====", "AAAA\n", " AAA", "AA-_", "AAAAA", None, 5, b"AAAA"):
            self.assertFalse(link_e2e._veljaven_b64(slab, 64), repr(slab))
        self.assertFalse(link_e2e._veljaven_b64("AAAAAAAA", 4))
        self.assertRaises(link_e2e.Napaka, link_e2e._iz_b64, "AAA", "x")
        self.assertEqual(link_e2e._iz_b64("AAAA", "x"), b"\x00\x00\x00")
        for dobra in ("AAECAwQFBgcICQoLDA0ODw", "S-1", "a_b"):
            self.assertTrue(link_e2e._veljavna_oznaka_seje(dobra), dobra)
        for slaba in ("", "a b", "a\nb", "a+b", "a/b", "a=", "a" * 65, None, 5):
            self.assertFalse(link_e2e._veljavna_oznaka_seje(slaba), repr(slaba))

    def test_polna_vrsta_ob_novem_dogovoru_javi_najstarejse(self):
        """Na dogovor brez odgovora caka polna vrsta SVEZIH sporocil. Nov dogovor z novim sporocilom jih prevzame; kar
        ne gre vec v vrsto (najstarejse), klicatelj izve - ne izgine tiho."""
        from unittest import mock
        o = _Omrezje(takoj=False)
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        zavrnjena = []
        a.upravitelj._ob_zavrnitvi = lambda s, besedilo, koda: zavrnjena.append((s.get("id"), koda))
        with mock.patch.object(link_e2e, "NAJVEC_V_VRSTI", 3):
            self.assertTrue(a.upravitelj.dogovori_se(b.id))                 # dogovor brez sporocila; odgovora ne bo
            o.cakajo.clear()
            a.zdaj += link_e2e.DOGOVOR_CAKA_S - 0.2
            for i in range(3):
                self.assertTrue(a.upravitelj.poslji(b.id, dict(UKAZ, id="s%d" % i)))    # sveza; vrsta je polna
            self.assertFalse(a.upravitelj.poslji(b.id, dict(UKAZ, id="prevec")))
            a.zdaj += 0.4                                                   # dogovor zdaj caka dlje kot 8 s
            self.assertTrue(a.upravitelj.poslji(b.id, dict(UKAZ, id="novo")))
        self.assertEqual(zavrnjena, [("s0", "cas")])
        o.dostavi_vse()
        self.assertEqual([s["id"] for s, _od, _j in b.prejeta], ["s1", "s2", "novo"])

    def test_oznaka_s_prelomom_vrstice_ne_preveze_seje_na_drugo_napravo(self):
        """Sredisce M v seznam naprav vpise vnos X = »<oznaka M>\\n<oznaka B>« (kljuc po jedru: M). Bajti ponudbe, ki bi
        jih C podpisal za X, so isti kot bajti ponudbe »od <C>\\n<M> za B« - B bi jo preverila s kljucem C. Izmerjeno
        pred popravkom (krog120/n1-napad.py): ukaz, ki ga je C poslal vnosu X, je B desifrirala in pripisala C."""
        o = _Omrezje(takoj=False)
        c, b, m = _Naprava(o, "-control"), _Naprava(o, "-os"), _Naprava(o, "-tv")
        x = m.id + "\n" + b.id
        f = c.id + "\n" + m.id
        c.krog[x] = m.kljuc             # iskanje kljuca po jedru (prvih 18 znakov) je v izdelku dalo isto
        b.krog[f] = c.kljuc
        self.assertEqual(link_e2e.podatki_ponudbe("s", c.id, x, "n", "e"), link_e2e.podatki_ponudbe("s", f, b.id, "n", "e"))
        # 1) C za tako oznako dogovora ne zacne in sporocila ne sprejme v posiljanje.
        self.assertFalse(c.upravitelj.dogovori_se(x))
        self.assertFalse(c.upravitelj.poslji(x, dict(UKAZ)))
        self.assertEqual(o.cakajo, [])
        # 2) Tudi ce bi ponudbo kdo podpisal (starejsi ali spremenjen program), je B ne sprejme.
        _zasebni, epk = link_e2e.nov_par()
        sid, nonce = "A" * 22, base64.b64encode(b"\x01" * 16).decode()
        ponudba = {"session_id": sid, "purpose": "link", "v": 2, "from": f, "to": b.id, "nonce": nonce, "epk": epk,
                   "sig": _podpis(c, link_e2e.podatki_ponudbe(sid, c.id, x, nonce, epk))}
        self.assertTrue(b.upravitelj.prejmi({"type": "data.offer", "sender": f, "payload": ponudba}))
        self.assertEqual((b.seje, o.cakajo), ([], []))
        self.assertFalse(b.upravitelj.ima_sejo(f))

    def test_polja_dogovora_sprejmejo_samo_svojo_abecedo(self):
        o = _Omrezje(takoj=False)
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        # Veljavno PODPISANA ponudba z oznako seje, ki ne sme v podpisane bajte (podpise jo lahko vsaka naprava v krogu):
        # zavrnjena mora biti, preden ta naprava karkoli podpise s svojim kljucem.
        podpisov = []
        izvirni = b.upravitelj._podpisi
        b.upravitelj._podpisi = lambda bajti: podpisov.append(bajti) or izvirni(bajti)
        for sid in ("abc\ndef", "abc def", "abc+def", "a" * 65):
            self.assertTrue(b.upravitelj.prejmi(PregledPredIzdajo()._ponudba(a, b, sid)), repr(sid))
        self.assertEqual((b.seje, o.cakajo, podpisov), ([], [], []))
        b.upravitelj._podpisi = izvirni
        self.assertTrue(a.upravitelj.dogovori_se(b.id))
        p = o.cakajo.pop(0)
        t = p["payload"]
        for polje, vrednost in (("session_id", t["session_id"] + "\n"), ("session_id", t["session_id"] + "+"),
                                ("session_id", "A" * 65), ("nonce", t["nonce"][:-2] + "\n="), ("nonce", t["nonce"][:-1]),
                                ("epk", t["epk"] + "\n"), ("epk", " " + t["epk"]), ("sig", t["sig"] + "\n"),
                                ("from", a.id + "\t"), ("from", a.id + " "), ("from", a.id + "\u010d")):
            slabo = json.loads(json.dumps(p))
            slabo["payload"][polje] = vrednost
            if polje == "from":
                slabo["sender"] = vrednost
                b.krog[vrednost] = a.kljuc      # tudi ce bi krog tako oznako poznal
            self.assertTrue(b.upravitelj.prejmi(slabo), polje)
            self.assertEqual((b.seje, o.cakajo), ([], []), "%s=%r" % (polje, vrednost))
        self.assertTrue(b.upravitelj.prejmi(p))             # nespremenjena ponudba se sprejme
        self.assertEqual(b.seje, [a.jedro])
        odgovor = o.cakajo.pop(0)
        for polje, vrednost in (("nonce", odgovor["payload"]["nonce"] + "\n"), ("epk", odgovor["payload"]["epk"] + " "),
                                ("sig", "\n" + odgovor["payload"]["sig"])):
            slabo = json.loads(json.dumps(odgovor))
            slabo["payload"][polje] = vrednost
            self.assertTrue(a.upravitelj.prejmi(slabo), polje)
            self.assertEqual(a.seje, [], polje)
        self.assertTrue(a.upravitelj.prejmi(odgovor))
        self.assertEqual(a.seje, [b.jedro])

    def test_ena_naprava_ne_izrine_sej_drugih(self):
        """c odpira sejo za sejo z b in vsako potrdi s sporocilom: izriva lahko samo SVOJE seje, ne seje a-b."""
        from unittest import mock
        o = _Omrezje()
        a, b, c = _Naprava(o, "-control"), _Naprava(o, "-os"), _Naprava(o, "-tv")
        for n in (a, b, c):
            n.pozna(a, b, c)
        with mock.patch.object(link_e2e, "NAJVEC_SEJ", 6), mock.patch.object(link_e2e, "NAJVEC_SEJ_NA_NAPRAVO", 3):
            self.assertTrue(a.upravitelj.poslji(b.id, dict(UKAZ)))          # potrjena seja a-b
            for i in range(10):
                c.upravitelj.pozabi(b.id)
                self.assertTrue(c.upravitelj.poslji(b.id, dict(UKAZ, id="c%d" % i)))
            self.assertTrue(b.upravitelj.ima_sejo(a.id))
            self.assertEqual(len([s for s in b.upravitelj._seje.values() if s.jedro == c.jedro]), 3)
            self.assertTrue(a.upravitelj.poslji(b.id, dict(UKAZ, id="u2")))
        self.assertEqual([s["id"] for s, _od, _j in b.prejeta if _od == a.id], ["u1", "u2"])
        self.assertFalse(any('"data.error"' in s for s in o.videno))

    def test_ponovljene_ponudbe_iste_naprave_ne_izrinejo_njene_potrjene_seje(self):
        """Meja na napravo: prostor najprej naredijo NEPOTRJENE seje te naprave (ponudbe lahko ponavlja sredisce)."""
        from unittest import mock
        o = _Omrezje()
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        pregled = PregledPredIzdajo()
        with mock.patch.object(link_e2e, "NAJVEC_SEJ_NA_NAPRAVO", 3):
            self.assertTrue(a.upravitelj.poslji(b.id, dict(UKAZ)))
            potrjena = a.upravitelj._za[b.id]
            for i in range(8):
                b.upravitelj.prejmi(pregled._ponudba(a, b, "ponovljena-%d" % i))
            self.assertIn(potrjena, b.upravitelj._seje)
            self.assertEqual(len(b.upravitelj._seje), 3)

    def test_pomnilnik_za_nedokoncana_sporocila_je_omejen_na_napravo_in_skupaj(self):
        from unittest import mock
        o = _Omrezje(takoj=False)
        a, b, c = _Naprava(o, "-control"), _Naprava(o, "-os"), _Naprava(o, "-tv")
        for n in (a, b, c):
            n.pozna(a, b, c)
        dolgo = {"type": "control.result", "payload": {"data": "x" * (link_e2e.DOLZINA_DELA + 10)}}      # dva dela
        en = 2 * link_e2e.DOLZINA_DELA

        def prvi_deli(od, koliko):
            for _ in range(koliko):
                od.upravitelj.poslji(b.id, dolgo)
            o.dostavi_vse_razen(lambda s: s["type"] == "data.chunk" and s["payload"]["n"] == 2 and s["payload"]["i"] == 1)

        def rezervirano(jedro=None):
            return sum(n * link_e2e.DOLZINA_DELA for s in b.upravitelj._seje.values() if jedro in (None, s.jedro)
                       for _cas, n, _z in s.deli.values())
        with mock.patch.object(link_e2e, "NAJVEC_REZERVIRANO_NA_NAPRAVO_B", 3 * en), \
                mock.patch.object(link_e2e, "NAJVEC_REZERVIRANO_B", 4 * en), \
                mock.patch.object(link_e2e, "NAJVEC_NEDOKONCANIH", 16):
            prvi_deli(c, 6)                                 # c: 6 nedokoncanih, a sme drzati samo 3
            self.assertEqual(rezervirano(c.jedro), 3 * en)
            prvi_deli(a, 2)                                 # a: 2 -> skupaj bi bilo 5, meja je 4: izpade najstarejse (od c)
            self.assertEqual(rezervirano(a.jedro), 2 * en)
            self.assertEqual(rezervirano(), 4 * en)

    def test_dokaz_kljuca_ne_izrine_dogovora_na_katerega_caka_ukaz(self):
        from unittest import mock
        o = _Omrezje(takoj=False)
        a = _Naprava(o, "-control")
        drugi = [_Naprava(o, "-n%d" % i) for i in range(6)]
        a.pozna(*drugi)
        zavrnjena = []
        a.upravitelj._ob_zavrnitvi = lambda s, besedilo, koda: zavrnjena.append((s.get("id"), koda))
        with mock.patch.object(link_e2e, "NAJVEC_DOGOVOROV", 2):
            self.assertTrue(a.upravitelj.poslji(drugi[0].id, dict(UKAZ, id="u0")))      # dogovor s cakajocim ukazom
            self.assertTrue(a.upravitelj.dogovori_se(drugi[1].id))                      # dokaz kljuca (brez sporocila)
            self.assertTrue(a.upravitelj.dogovori_se(drugi[2].id))                      # izrine dokaz kljuca, ne ukaza
            self.assertEqual(sorted(a.upravitelj._dogovori), sorted([drugi[0].id, drugi[2].id]))
            self.assertTrue(a.upravitelj.poslji(drugi[3].id, dict(UKAZ, id="u3")))      # izrine dokaz kljuca
            self.assertEqual(sorted(a.upravitelj._dogovori), sorted([drugi[0].id, drugi[3].id]))
            self.assertFalse(a.upravitelj.dogovori_se(drugi[4].id))                     # dokaz kljuca ukaza ne izrine
            self.assertEqual(zavrnjena, [])
            self.assertTrue(a.upravitelj.poslji(drugi[5].id, dict(UKAZ, id="u5")))      # ukaz izrine najstarejsega ...
            self.assertEqual(zavrnjena, [("u0", "cas")])                                # ... in klicatelj to izve
        self.assertEqual(sorted(a.upravitelj._dogovori), sorted([drugi[3].id, drugi[5].id]))

    def test_svez_ukaz_prezivi_nov_dogovor_z_isto_napravo_star_se_zavrne(self):
        """Dogovor brez odgovora se po 8 s zacne znova: ukaz, ki caka dlje, ne gre vec (klicatelj izve); ukaz, ki je
        prisel tik pred tem, caka naprej na novi dogovor - prej je tiho izginil."""
        o = _Omrezje(takoj=False)
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        zavrnjena = []
        a.upravitelj._ob_zavrnitvi = lambda s, besedilo, koda: zavrnjena.append((s.get("id"), koda))
        self.assertTrue(a.upravitelj.poslji(b.id, dict(UKAZ, id="star")))
        a.zdaj += link_e2e.DOGOVOR_CAKA_S - 0.5
        self.assertTrue(a.upravitelj.poslji(b.id, dict(UKAZ, id="svez")))
        o.cakajo.clear()                                    # sredisce prve ponudbe ni dostavilo
        a.zdaj += 1.0
        self.assertTrue(a.upravitelj.dogovori_se(b.id))     # (seznam naprav) dogovor se zacne znova
        self.assertEqual(zavrnjena, [("star", "cas")])
        o.dostavi_vse()
        self.assertEqual([s["id"] for s, _od, _j in b.prejeta], ["svez"])

    def test_meja_na_napravo_najprej_izrine_nadomescene_seje_ne_zive_seje_drugega_programa(self):
        """Tretji pregled (7. 10. 2026): naprava ima dva programa z istim kljucem - »control« (seja od zacetka, ziva,
        redko rabljena) in »os«, ki se pogosto znova zazene (vsakic nova, potrjena seja). Ko je meja sej na napravo
        dosezena, izpadejo stare seje programa »os«, ki jih je nadomestila novejsa - ne ziva seja programa »control«."""
        from unittest import mock
        o = _Omrezje()
        b = _Naprava(o, "-tv")
        control = _Naprava(o, "-control")
        os_program = _Naprava(o, "-os", zasebni=control.zasebni)
        self.assertEqual(os_program.jedro, control.jedro)
        b.pozna(control, os_program)
        control.pozna(b)
        os_program.pozna(b)
        with mock.patch.object(link_e2e, "NAJVEC_SEJ_NA_NAPRAVO", 4):
            self.assertTrue(control.upravitelj.poslji(b.id, dict(UKAZ, id="c1")))
            for i in range(8):
                b.zdaj += 60.0
                os_program.upravitelj.pozabi_vse()                  # program »os« se znova zazene
                self.assertTrue(os_program.upravitelj.poslji(b.id, dict(UKAZ, id="o%d" % i)))
            self.assertEqual(len([s for s in b.upravitelj._seje.values() if s.jedro == control.jedro]), 4)
            self.assertTrue(control.upravitelj.poslji(b.id, dict(UKAZ, id="c2")))
        self.assertEqual([s["id"] for s, od, _j in b.prejeta if od == control.id], ["c1", "c2"])
        self.assertEqual([s["id"] for s, od, _j in b.prejeta if od == os_program.id], ["o%d" % i for i in range(8)])
        self.assertFalse(any('"data.error"' in s for s in o.videno))

    def test_sporocilo_ki_po_dogovoru_ne_gre_klicatelj_izve(self):
        """Sporocilo caka na dogovor; ko dogovor uspe, ga ni mogoce poslati (povezave s srediscem ni vec): klicatelj
        mora izvedeti - prej je cakal na iztek casa. (Predolgo sporocilo poslji zavrne ze prej - CetrtiPregled.)"""
        o = _Omrezje(takoj=False)
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        zavrnjena = []
        a.upravitelj._ob_zavrnitvi = lambda s, besedilo, koda: zavrnjena.append((s.get("id"), koda))
        self.assertTrue(a.upravitelj.poslji(b.id, dict(UKAZ, id="prvi")))       # oba v vrsto
        self.assertTrue(a.upravitelj.poslji(b.id, dict(UKAZ, id="drugi")))
        pravo, padlo = a.upravitelj._poslji, []

        def prvi_kos_ne_gre(sporocilo):
            if sporocilo.get("type") == "data.chunk" and not padlo:
                padlo.append(1)
                return False
            return pravo(sporocilo)
        a.upravitelj._poslji = prvi_kos_ne_gre
        o.dostavi_vse()
        self.assertEqual(zavrnjena, [("prvi", "ni_poslano")])
        self.assertEqual([s["id"] for s, _od, _j in b.prejeta], ["drugi"])

    def test_pozna_kljuc(self):
        o = _Omrezje()
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        a.krog["z\nprelomom"] = b.kljuc
        self.assertTrue(a.upravitelj.pozna_kljuc(b.id))
        for brez in ("neznana", "z\nprelomom", "", "a b"):
            self.assertFalse(a.upravitelj.pozna_kljuc(brez), repr(brez))

    def test_posiljatelj_z_osamljenim_nadomestnim_znakom_ne_vrze(self):
        import contextlib
        import io
        o = _Omrezje()
        a = _Naprava(o, "-control")
        with contextlib.redirect_stdout(io.TextIOWrapper(io.BytesIO(), encoding="utf-8")):
            self.assertTrue(a.upravitelj.prejmi({"type": "data.offer", "sender": "\ud800" * 20, "payload": {"purpose": "link"}}))
            self.assertTrue(a.upravitelj.prejmi({"type": "data.error", "sender": "\ud800" * 20,
                                                 "payload": {"session_id": ["x"], "code": 5}}) in (True, False))

    def test_ura_sej_tece_tudi_med_spanjem_racunalnika(self):
        import time
        o = _Omrezje()
        u = link_e2e.Upravitelj(moj_id=lambda: "a", poslji=lambda s: True, podpisi=lambda b: "", kljuc_za=lambda i: None,
                                preveri=lambda k, b, p: False, id_iz_kljuca=lambda k: "", ob_sporocilu=lambda s, od, j: None)
        self.assertIs(u._ura, link_e2e.ura_sistema)
        if hasattr(time, "CLOCK_BOOTTIME"):
            self.assertAlmostEqual(link_e2e.ura_sistema(), time.clock_gettime(time.CLOCK_BOOTTIME), delta=2.0)
        self.assertIsNotNone(o)


@unittest.skipUnless(KRIPTO, "ni python3-cryptography")
class OdjemalecPoDrugemPregledu(unittest.TestCase):
    """core/link_hub.Povezava po drugem neodvisnem pregledu (ista lazna pot kot v OdjemalecLinka)."""
    _povezava = OdjemalecLinka._povezava
    setUp = OdjemalecLinka.setUp

    def test_odgovor_napravi_s_sejo_gre_zasciten_tudi_ko_sredisce_skrije_zmoznost(self):
        """Zapis »zascita« tu ne pomaga (v preizkusu ga ni - tako kot v izdelku, kadar je pod oznako naprave v krogu
        podtaknjen drug kljuc): odloci ziva preverjena seja."""
        self.assertTrue(self.a.poslji({"id": "u1", "type": "control.command", "target": self.b.device_id, "payload": {}}))
        self.sredisce.tok()
        self.b._zapomni_zmoznosti([{"id": self.a.device_id, "capabilities": ["remote"]}])     # sredisce zmoznost skrije
        self.assertTrue(self.b.poslji({"id": "r1", "type": "control.result", "target": self.a.device_id, "ref_id": "u1",
                                       "payload": {"ok": True, "data": {"skrivnost": "SKRIVNOST"}}}))
        self.sredisce.tok()
        self.assertFalse(any("SKRIVNOST" in s for s in self.sredisce.videno))
        self.assertEqual([s["id"] for s in self.a.prejeto if s.get("type") == "control.result"], ["r1"])

    def test_seznam_z_veliko_oznakami_iste_naprave_ne_sprozi_veliko_dogovorov(self):
        from core import link_hub
        jedro_b = self.b.device_id[:18]
        seznam = [{"id": "%s-x%d" % (jedro_b, i), "capabilities": [link_e2e.ZMOZNOST]} for i in range(500)]
        for d in seznam:
            self.kljuci[d["id"]] = self.b.kljuc
        self.a._zapomni_zmoznosti(seznam)
        for _ in range(3):
            self.a._dokazi_kljuce()
        ponudbe = [s for s in self.sredisce.videno if '"data.offer"' in s]
        self.assertEqual(len(ponudbe), link_hub.NAJVEC_DOKAZOV_NA_JEDRO)
        self.assertLessEqual(len(self.a._dokazi_kljucev), link_hub.NAJVEC_ZAPISOV_DOKAZOV)

    def test_naprave_brez_kljuca_v_seznamu_ne_porabijo_dokazov(self):
        """Tretji pregled: sredisce pred pravo napravo nasteje veliko izmisljenih (brez kljuca v nasem krogu). Te ne smejo
        porabiti dogovorov, ki jih sme sproziti en seznam, ne zapisa o poskusih - prava naprava pride na vrsto takoj."""
        from core import link_hub
        izmisljene = [{"id": "n-%016x-os" % i, "capabilities": [link_e2e.ZMOZNOST]} for i in range(100)]
        prava = {"id": self.b.device_id, "capabilities": ["remote", link_e2e.ZMOZNOST]}
        self.a._zapomni_zmoznosti(izmisljene + [prava])
        self.a._dokazi_kljuce()
        self.sredisce.tok()
        self.assertEqual([json.loads(s)["type"] for s in self.sredisce.videno], ["data.offer", "data.answer"])
        self.assertEqual(self.a.seje, [self.b.device_id[:18]])
        self.assertEqual(list(self.a._dokazi_kljucev), [self.b.device_id])
        self.assertGreater(len(izmisljene), link_hub.NAJVEC_DOKAZOV_NA_SEZNAM)

    def test_seznam_naprav_neveljavne_oznake_in_predolg_seznam(self):
        from core import link_hub
        seznam = [{"id": "x\ny", "capabilities": [link_e2e.ZMOZNOST]}, {"id": "a" * 500, "capabilities": [link_e2e.ZMOZNOST]},
                  {"id": 5, "capabilities": [link_e2e.ZMOZNOST]}, {"id": "dobra", "capabilities": [link_e2e.ZMOZNOST, 7, "x" * 500]},
                  "ni-slovar"] + [{"id": "n%d" % i, "capabilities": []} for i in range(5000)]
        self.a._zapomni_zmoznosti(seznam)
        self.assertEqual(len(self.a._zmoznosti_naprav), link_hub.NAJVEC_NAPRAV_V_SEZNAMU)
        self.assertEqual(self.a._zmoznosti_naprav["dobra"], frozenset({link_e2e.ZMOZNOST}))
        for slaba in ("x\ny", "a" * 500, "5", 5):
            self.assertNotIn(slaba, self.a._zmoznosti_naprav)

    def test_kljuc_za_zascito_samo_za_veljavno_oznako(self):
        from unittest import mock
        from core import link_hub
        jedro = self.b.device_id[:18]

        class _Krog:
            def kljuc_za_jedro(_s, j):
                return self.b.kljuc if j == jedro else None

            def clan(_s, i):
                return {"kljuc": self.b.kljuc}
        with mock.patch.object(link_hub.link_krog, "krog", lambda: _Krog()):
            self.assertEqual(link_hub.kljuc_naprave_za_zascito(jedro + "-os"), self.b.kljuc)
            for slaba in (jedro + "-tv\n" + self.a.device_id, jedro + "-x y", jedro + "\n", "stara naprava", "a\nb", "a" * 200):
                self.assertIsNone(link_hub.kljuc_naprave_za_zascito(slaba), repr(slaba))

    def test_sonda_v_sporocilu_naprave_in_nenavaden_json_ne_prekineta_branja(self):
        from core import link_hub
        prejeta = []
        self.a.ob_sporocilu = lambda s: prejeta.append(s.get("id"))
        self.a.odjemalec.vrsta.append(json.dumps({"id": "s1", "type": "share.text", "sender": self.b.device_id,
                                                  "ref_id": link_hub.SONDA_PREDPONA + "1", "error_code": "naprava_ni_povezana"}))
        self.a.odjemalec.vrsta.append('{"x":' + "1" * 5000 + "}")
        self.a.odjemalec.vrsta.append("[" * 100000)
        self.a.odjemalec.vrsta.append(json.dumps({"id": "ok", "type": "share.text"}))
        self.a.tece = True
        self.a._poslusaj()                      # EN klic prebere vse
        self.a.odjemalec = self.a._lazni
        self.assertEqual(prejeta, ["ok"])
        self.assertEqual(self.a._lazni.vrsta, [])

    def test_potrditev_sredisca_za_sondo_se_vedno_konca_branje(self):
        from core import link_hub
        self.a.odjemalec.vrsta.append(json.dumps({"id": "p", "type": "share.ack", "ref_id": link_hub.SONDA_PREDPONA + "2",
                                                  "error_code": "naprava_ni_povezana"}))
        self.a.odjemalec.vrsta.append(json.dumps({"id": "ok", "type": "share.text"}))
        self.a.tece = True
        self.a._poslusaj()
        self.assertEqual(len(self.a._lazni.vrsta), 1)       # sredisce nas ne vodi vec: zanka se konca (prijava znova)


@unittest.skipUnless(KRIPTO, "ni python3-cryptography")
class CetrtiPregled(unittest.TestCase):
    """Najdbe CETRTEGA neodvisnega pregleda (7. 10. 2026, koncno stanje po tretjem): seznanjena naprava s predelanim
    programom (ali sredisce) drugo napravo preobremeni - s podpisi in s pomnilnikom. Vsak preizkus je najprej padel."""

    def setUp(self):
        self.o = _Omrezje()
        self.a = _Naprava(self.o, "-control")
        self.b = _Naprava(self.o, "-os")
        self.a.pozna(self.b)
        self.b.pozna(self.a)
        self.pregled = PregledPredIzdajo()

    def _zavrnitve(self, naprava):
        zavrnjena = []
        naprava.upravitelj._ob_zavrnitvi = lambda s, besedilo, koda: zavrnjena.append((s.get("id"), koda))
        return zavrnjena

    # -- podpisi s kljucem naprave

    def test_ponovljena_ponudba_ne_sprozi_novega_podpisa(self):
        """Sredisce isto (veljavno podpisano) ponudbo dostavi veckrat: b zanjo podpise EN odgovor - ponovitev zavrne,
        preden karkoli preveri ali podpise."""
        ponudba = self.pregled._ponudba(self.a, self.b, "ponovljena-1")
        for _ in range(20):
            self.assertTrue(self.b.upravitelj.prejmi(json.loads(json.dumps(ponudba))))
        self.assertEqual(self.b.podpisov, 1)
        self.assertEqual(sum(1 for s in self.o.videno if '"data.answer"' in s), 1)

    def test_ponudbe_ene_naprave_imajo_mejo_podpisov(self):
        """Seznanjena naprava posilja ponudbo za ponudbo (vsako z novo oznako seje in svojim veljavnim podpisom): b v
        enem oknu zanjo podpise najvec NAJVEC_PODPISOV_NA_NAPRAVO odgovorov; po izteku okna spet."""
        for i in range(link_e2e.NAJVEC_PODPISOV_NA_NAPRAVO + 40):
            self.assertTrue(self.b.upravitelj.prejmi(self.pregled._ponudba(self.a, self.b, "p-%d" % i)))
        self.assertEqual(self.b.podpisov, link_e2e.NAJVEC_PODPISOV_NA_NAPRAVO)
        self.b.zdaj += link_e2e.OKNO_PODPISOV_S + 1
        self.b.upravitelj.prejmi(self.pregled._ponudba(self.a, self.b, "po-oknu"))
        self.assertEqual(self.b.podpisov, link_e2e.NAJVEC_PODPISOV_NA_NAPRAVO + 1)

    def test_meja_podpisov_je_na_napravo_ne_skupna(self):
        c = _Naprava(self.o, "-tv")
        self.b.pozna(c)
        c.pozna(self.b)
        for i in range(link_e2e.NAJVEC_PODPISOV_NA_NAPRAVO + 5):
            self.b.upravitelj.prejmi(self.pregled._ponudba(self.a, self.b, "p-%d" % i))
        pred = self.b.podpisov
        self.assertTrue(c.upravitelj.poslji(self.b.id, dict(UKAZ)))         # druga naprava: dogovor uspe
        self.assertEqual(self.b.podpisov, pred + 1)
        self.assertEqual([s["id"] for s, od, _j in self.b.prejeta if od == c.id], ["u1"])

    def test_meja_podpisov_steje_vse_programe_iste_naprave_in_tudi_nase_ponudbe(self):
        """Ukazi (ali odgovori) za veliko oznak iste naprave, ki ne odgovarja: vsak nov dogovor je podpis s kljucem
        naprave. V oknu jih je za eno napravo najvec NAJVEC_PODPISOV_NA_NAPRAVO; naprej poslji vrne False."""
        o = _Omrezje(takoj=False)
        a = _Naprava(o, "-control")
        programi = [_Naprava(o, "-p%d" % i, zasebni=self.b.zasebni) for i in range(link_e2e.NAJVEC_PODPISOV_NA_NAPRAVO + 10)]
        a.pozna(*programi)
        izidi = [a.upravitelj.poslji(p.id, dict(UKAZ, id="u%d" % i)) for i, p in enumerate(programi)]
        self.assertEqual(a.podpisov, link_e2e.NAJVEC_PODPISOV_NA_NAPRAVO)
        self.assertEqual(izidi.count(True), link_e2e.NAJVEC_PODPISOV_NA_NAPRAVO)
        self.assertFalse(izidi[-1])
        self.assertEqual(len(o.cakajo), link_e2e.NAJVEC_PODPISOV_NA_NAPRAVO)

    # -- pomnilnik

    def test_poslano_sporocilo_se_ne_hrani(self):
        """Za potrditve sredisca in obvestilo »seje ni« si zapomnimo samo tip in oznako sporocila, ne sporocila: odgovor,
        ki ponovi dolgo oznako ukaza ali nosi velik seznam, ne ostane v pomnilniku."""
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, dict(UKAZ)))
        veliko = {"id": "r-velik", "type": "control.result", "ref_id": "x" * 200_000, "payload": {"data": "y" * 400_000}}
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, veliko))
        self.assertEqual(self.b.prejeta[-1][0], veliko)
        u = self.a.upravitelj
        hranjeno = repr([v[2] for v in u._izhodna.values()]) + repr([s.zadnja for s in u._seje.values()])
        self.assertLess(len(hranjeno), 4000)
        self.assertIn("r-velik", hranjeno)

    def test_predolga_oznaka_sporocila_se_ne_hrani(self):
        zavrnjena = self._zavrnitve(self.a)
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, dict(UKAZ)))
        self.o.takoj = False
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, {"id": "i" * 5000, "type": "control.result", "payload": {}}))
        u = self.a.upravitelj
        self.assertLess(len(repr([v[2] for v in u._izhodna.values()]) + repr([s.zadnja for s in u._seje.values()])), 2000)
        kos = self.o.cakajo.pop(0)
        self.assertTrue(u.prejmi({"id": "1", "type": "data.ack", "ref_id": kos["id"], "status": "rejected",
                                  "error": "Naprave ni.", "error_code": "naprava_ni_povezana"}))
        self.assertEqual(zavrnjena, [(None, "naprava_ni_povezana")])       # zavrnitev pride, a brez (predolge) oznake

    def test_predolgo_sporocilo_je_zavrnjeno_takoj_tudi_brez_seje(self):
        """Prej je predolgo sporocilo cakalo na dogovor in drzalo pomnilnik; zdaj ga poslji zavrne takoj in zaradi njega
        ne zacne niti dogovora."""
        o = _Omrezje(takoj=False)
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        predolgo = {"id": "dolg", "type": "control.result",
                    "payload": {"data": "x" * (link_e2e.DOLZINA_DELA * link_e2e.NAJVEC_DELOV + 10)}}
        self.assertFalse(a.upravitelj.poslji(b.id, predolgo))
        self.assertEqual((o.cakajo, a.podpisov), ([], 0))

    def test_cakajoca_sporocila_imajo_mejo_bajtov_na_napravo_in_skupaj(self):
        from unittest import mock
        o = _Omrezje(takoj=False)
        a = _Naprava(o, "-control")
        b1 = _Naprava(o, "-os")
        b2 = _Naprava(o, "-tv", zasebni=b1.zasebni)             # drug program ISTE naprave
        c, d = _Naprava(o, "-os"), _Naprava(o, "-os")
        a.pozna(b1, b2, c, d)
        zavrnjena = self._zavrnitve(a)

        def sporocilo(i):
            return {"id": "s%d" % i, "type": "control.result", "payload": {"data": "x" * 1000}}
        en = len(json.dumps(sporocilo(0), separators=(",", ":")).encode())
        with mock.patch.object(link_e2e, "NAJVEC_CAKAJOCIH_NA_NAPRAVO_B", 3 * en + 10), \
                mock.patch.object(link_e2e, "NAJVEC_CAKAJOCIH_B", 5 * en + 10):
            self.assertTrue(a.upravitelj.poslji(b1.id, sporocilo(0)))
            self.assertTrue(a.upravitelj.poslji(b1.id, sporocilo(1)))
            self.assertTrue(a.upravitelj.poslji(b2.id, sporocilo(2)))       # drug program iste naprave: ista meja
            self.assertFalse(a.upravitelj.poslji(b2.id, sporocilo(3)))
            self.assertFalse(a.upravitelj.poslji(b1.id, sporocilo(4)))
            self.assertTrue(a.upravitelj.poslji(c.id, sporocilo(5)))        # druga naprava ima svojo mejo ...
            self.assertTrue(a.upravitelj.poslji(c.id, sporocilo(6)))
            self.assertFalse(a.upravitelj.poslji(d.id, sporocilo(7)))       # ... skupna meja pa velja za vse
            self.assertEqual(zavrnjena, [])
            # Ko sporocila zastarajo, klicatelji to izvejo in prostor je spet prost.
            a.zdaj += link_e2e.V_VRSTI_VELJA_S + 1
            self.assertTrue(a.upravitelj.poslji(d.id, sporocilo(8)))
        self.assertEqual(sorted(zavrnjena), [("s%d" % i, "cas") for i in (0, 1, 2, 5, 6)])

    # -- potrditve sredisca

    def test_koda_zavrnitve_sredisca_ni_nikoli_nasa_koda(self):
        """Sredisce kos dostavi, potem pa ga »zavrne« s kodo, ki pri nas pomeni »ni bilo poslano«: take kode klicatelj
        od sredisca ne dobi (program, ki bi ob njej poskusil znova, bi ukaz izvedel dvakrat)."""
        o = _Omrezje(takoj=False)
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        zavrnjena = self._zavrnitve(a)
        a.upravitelj.poslji(b.id, dict(UKAZ))
        o.dostavi_vse()
        kode = ("ni_poslano", "cas", "ni_seje", "ni_kljuca", "zascita", "naprava_ni_povezana")
        for i, koda in enumerate(kode):
            self.assertTrue(a.upravitelj.poslji(b.id, dict(UKAZ, id="k%d" % i)))
            kos = o.cakajo.pop(0)
            self.assertTrue(a.upravitelj.prejmi({"id": "1", "type": "data.ack", "ref_id": kos["id"], "status": "rejected",
                                                 "error": "x" * 5000, "error_code": koda}))
        self.assertEqual(zavrnjena, [("k0", "zavrnjeno"), ("k1", "zavrnjeno"), ("k2", "zavrnjeno"), ("k3", "zavrnjeno"),
                                     ("k4", "zavrnjeno"), ("k5", "naprava_ni_povezana")])

    def test_dolgo_sporocilo_sprejem_sele_z_zadnjim_kosom_zavrnitev_katerega_koli(self):
        o = _Omrezje(takoj=False)
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        zavrnjena = self._zavrnitve(a)
        sprejeta = []
        a.upravitelj._ob_sprejemu = lambda s: sprejeta.append(s.get("id"))
        a.upravitelj.poslji(b.id, dict(UKAZ))
        o.dostavi_vse()

        def potrdi(kos, stanje):
            return a.upravitelj.prejmi({"id": "1", "type": "data.ack", "ref_id": kos["id"], "status": stanje,
                                        "error": "Naprave ni.", "error_code": "naprava_ni_povezana"})

        def dolgo(oznaka):
            self.assertTrue(a.upravitelj.poslji(b.id, {"id": oznaka, "type": "control.result",
                                                       "payload": {"data": "x" * (2 * link_e2e.DOLZINA_DELA + 10)}}))
            kosi, o.cakajo[:] = list(o.cakajo), []
            self.assertEqual(len(kosi), 3)
            return kosi
        # 1) Prva dva kosa sprejeta, zadnji zavrnjen (naprava je medtem odsla): klicatelj izve - prej ni.
        kosi = dolgo("d1")
        potrdi(kosi[0], "accepted")
        potrdi(kosi[1], "accepted")
        self.assertEqual(sprejeta, [])                      # sprejet prvi kos se ni sprejeto sporocilo
        potrdi(kosi[2], "rejected")
        self.assertEqual((sprejeta, zavrnjena), ([], [("d1", "naprava_ni_povezana")]))
        # 2) Zavrnjen prvi IN zadnji: ena zavrnitev.
        kosi = dolgo("d2")
        potrdi(kosi[0], "rejected")
        potrdi(kosi[2], "rejected")
        self.assertEqual(zavrnjena, [("d1", "naprava_ni_povezana"), ("d2", "naprava_ni_povezana")])
        # 3) Vsi sprejeti: en sprejem, ob zadnjem.
        kosi = dolgo("d3")
        for k in kosi:
            potrdi(k, "accepted")
        self.assertEqual(sprejeta, ["d3"])

    def test_cast_media_je_med_zascitenimi_tipi(self):
        """Tipa danes ne obdela noben sprejemnik; ce ga kdaj bo, mora biti ze zasciten (in pravilo »od naprave z
        zascito samo zasciteno« zanj ze velja)."""
        self.assertIn("cast.media", link_e2e.ZASCITENI_TIPI)

    def test_predolg_zapis_kosa_se_zavrne_pred_dekodiranjem(self):
        from unittest import mock
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, dict(UKAZ)))
        sid = self.a.upravitelj._za[self.b.id]
        with mock.patch.object(link_e2e, "_iz_b64", wraps=link_e2e._iz_b64) as dekodiraj:
            self.assertTrue(self.b.upravitelj.prejmi({"type": "data.chunk", "sender": self.a.id, "payload": {
                "session_id": sid, "seq": 5, "m": 5, "i": 0, "n": 1, "data": "A" * (4 * link_e2e.DOLZINA_DELA)}}))
        dekodiraj.assert_not_called()
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, dict(UKAZ, id="u2")))      # seja dela naprej
        self.assertEqual([s["id"] for s, _od, _j in self.b.prejeta], ["u1", "u2"])


@unittest.skipUnless(KRIPTO, "ni python3-cryptography")
class OdjemalecPoCetrtemPregledu(unittest.TestCase):
    """core/link_hub.Povezava po cetrtem neodvisnem pregledu (ista lazna pot kot v OdjemalecLinka)."""
    _povezava = OdjemalecLinka._povezava
    setUp = OdjemalecLinka.setUp

    def test_sporocilo_s_predolgo_oznako_se_zavrze(self):
        dolga = "x" * 5000
        for s in ({"id": dolga, "type": "share.text", "sender": "stara-naprava"},
                  {"id": "p1", "ref_id": dolga, "type": "control.ack", "sender": "stara-naprava"},
                  {"id": "ok", "type": "share.text", "sender": "stara-naprava"}):
            self.a.odjemalec.vrsta.append(json.dumps(s))
        self.sredisce.tok()
        self.assertEqual([s["id"] for s in self.a.prejeto], ["ok"])       # oznake, ki niso niz: glej peti pregled

    def test_zasciten_ukaz_s_predolgo_oznako_ne_pride_do_programa(self):
        """Naprava s predelanim programom poslje ZASCITEN ukaz z zelo dolgo oznako: program ga ne dobi, zato odgovora
        (ki bi oznako ponovil) ni."""
        self.assertTrue(self.a.poslji({"id": "kratek", "type": "control.command", "target": self.b.device_id, "payload": {}}))
        self.sredisce.tok()
        self.assertTrue(self.a._zascita.poslji(self.b.device_id, {"id": "x" * 200_000, "type": "control.command",
                                                                  "payload": {"action": "files.list"}}))
        self.sredisce.tok()
        self.assertEqual([s["id"] for s in self.b.prejeto if s.get("type") == "control.command"], ["kratek"])

    def test_odgovor_ne_ponovi_predolge_oznake_in_dejanja(self):
        from core import link_daljinec
        r = link_daljinec.sporocilo_izida("cilj", "r" * 100_000, "d" * 100_000, {"ok": False, "message": "ne"})
        self.assertLessEqual(len(r["ref_id"]), 128)
        self.assertLessEqual(len(r["payload"]["action"]), 64)
        self.assertLess(len(json.dumps(r)), 1000)
        kratek = link_daljinec.sporocilo_izida("cilj", "u1", "files.list", {"ok": True})
        self.assertEqual((kratek["ref_id"], kratek["payload"]["action"]), ("u1", "files.list"))

    def test_ce_zapisa_dovoljenj_ni_mogoce_prebrati_gre_zasciteno(self):
        """Napaka pri branju zapisa ne sme pomeniti »naprava zascite ne zna« (sporocilo bi slo nezasciteno)."""
        from unittest import mock
        with mock.patch("core.link_dostop.zahteva_zascito", side_effect=RuntimeError("pokvarjeno")):
            self.assertTrue(self.a._naprava_zna_zascito("stara-naprava"))

    def test_sporocilo_ki_ni_slovar_ne_pride_do_programa(self):
        for surovo in ("[1,2]", '"niz"', "5", "null", json.dumps({"id": "ok", "type": "share.text"})):
            self.a.odjemalec.vrsta.append(surovo)
        self.a.tece = True
        self.a._poslusaj()
        self.a.odjemalec = self.a._lazni
        self.assertEqual(self.a.prejeto, [{"id": "ok", "type": "share.text"}])


@unittest.skipUnless(KRIPTO, "ni python3-cryptography")
class PetiPregled(unittest.TestCase):
    """PETI neodvisni pregled (7. 10. 2026, stanje po cetrtem): nobene najdbe, ki bi izdajo ustavila - utrditve meje
    podpisov, vrst in zapisov o poslanem. Vsak preizkus je najprej padel, razen kjer je izrecno zapisano drugace."""

    def setUp(self):
        self.o = _Omrezje(takoj=False)
        self.a = _Naprava(self.o, "-control")
        self.b = _Naprava(self.o, "-os")
        self.a.pozna(self.b)
        self.b.pozna(self.a)
        self.zavrnjena = []
        self.sprejeta = []
        self.a.upravitelj._ob_zavrnitvi = lambda s, besedilo, koda: self.zavrnjena.append((s.get("id"), koda))
        self.a.upravitelj._ob_sprejemu = lambda s: self.sprejeta.append(s.get("id"))

    def _potrdi(self, sporocilo, stanje="rejected", koda="naprava_ni_povezana"):
        return self.a.upravitelj.prejmi({"id": "1", "type": "data.ack", "ref_id": sporocilo["id"], "status": stanje,
                                         "error": "Naprave ni.", "error_code": koda})

    def _seja(self):
        """Dogovor med a in b do konca; vrne sejo na strani a."""
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, dict(UKAZ)))
        self.o.dostavi_vse()
        self.assertEqual([s["id"] for s, _od, _j in self.b.prejeta], ["u1"])
        return self.a.upravitelj._seje[self.a.upravitelj._za[self.b.id]]

    def _dolgo(self, oznaka, delov=3):
        """Poslje sporocilo v `delov` kosih in vrne kose (sredisce jih se ni dostavilo)."""
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, {
            "id": oznaka, "type": "control.result", "payload": {"data": "x" * ((delov - 1) * link_e2e.DOLZINA_DELA + 10)}}))
        kosi, self.o.cakajo[:] = list(self.o.cakajo), []
        self.assertEqual(len(kosi), delov)
        return kosi

    # -- meja podpisov

    def test_ukazi_napravi_ki_je_ni_ne_porabijo_meje_podpisov(self):
        """Uporabnik drzi tipko daljinca, naprave pa ni v Linku: sredisce vsako ponudbo zavrne. Prej je vsak ukaz zacel
        nov dogovor (podpis s kljucem naprave) - po 32 ukazih je bila meja polna in se minuto po tem, ko se je naprava
        vrnila, ni sel noben ukaz. Zdaj po zavrnjeni ponudbi nekaj sekund ne zacnemo nove."""
        for i in range(200):                    # 20 s, ukaz na 0,1 s
            self.a.zdaj += 0.1
            self.a.upravitelj.poslji(self.b.id, dict(UKAZ, id="t%d" % i))
            while self.o.cakajo:
                self._potrdi(self.o.cakajo.pop(0))
        self.assertLessEqual(self.a.podpisov, 8)
        self.assertEqual(len(self.zavrnjena), len(set(self.zavrnjena)))     # nobena zavrnitev ni javljena dvakrat
        # Naprava se vrne: po kratkem premoru ukaz gre.
        self.a.zdaj += link_e2e.NEUSPEL_DOGOVOR_CAKA_S + 0.1
        self.o.takoj = True
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, dict(UKAZ, id="po")))
        self.assertEqual([s["id"] for s, _od, _j in self.b.prejeta], ["po"])

    def test_naprava_ki_nas_nima_v_krogu_ne_porabi_meje_podpisov(self):
        """Enako, kadar ponudbo zavrne naprava sama (»ni_kljuca«): do naslednjega poskusa je kratek premor."""
        o = _Omrezje()
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)                              # b naprave a NIMA v krogu
        for i in range(100):
            a.zdaj += 0.1
            a.upravitelj.poslji(b.id, dict(UKAZ, id="t%d" % i))
        self.assertLessEqual(a.podpisov, 5)

    def test_odgovori_na_ponudbe_ne_porabijo_meje_za_nase_ponudbe(self):
        """Meja podpisov je locena za dogovore, ki jih zacnemo mi, in za odgovore na ponudbe druge naprave: naprava, ki
        nas zasuje s ponudbami, ne sme doseci, da svojega dogovora z njo ne moremo vec zaceti."""
        pregled = PregledPredIzdajo()
        o = _Omrezje()
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a2 = _Naprava(o, "-tv", zasebni=a.zasebni)             # drug program naprave a
        a.pozna(b)
        a2.pozna(b)
        b.pozna(a, a2)
        for i in range(link_e2e.NAJVEC_PODPISOV_NA_NAPRAVO + 5):
            b.upravitelj.prejmi(pregled._ponudba(a, b, "p-%d" % i))
        self.assertEqual(b.podpisov, link_e2e.NAJVEC_PODPISOV_NA_NAPRAVO)       # meja odgovorov je polna
        self.assertTrue(b.upravitelj.poslji(a2.id, dict(UKAZ)))                # svoj dogovor b vseeno zacne
        self.assertEqual([s["id"] for s, _od, _j in a2.prejeta], ["u1"])

    def test_nov_upravitelj_istega_programa_nima_nove_meje_podpisov(self):
        """Program ob novi povezavi s srediscem naredi nov upravitelj zascite. Meja podpisov velja za program (in
        napravo na drugi strani), ne za upravitelj - sicer bi jo sredisce s prekinjanjem povezave ponastavljalo."""
        pregled = PregledPredIzdajo()
        o = _Omrezje()
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        for i in range(link_e2e.NAJVEC_PODPISOV_NA_NAPRAVO):
            b.upravitelj.prejmi(pregled._ponudba(a, b, "p-%d" % i))
        self.assertEqual(b.podpisov, link_e2e.NAJVEC_PODPISOV_NA_NAPRAVO)
        b2 = _Naprava(o, "-os", zasebni=b.zasebni)             # isti program, nov upravitelj (nova povezava)
        b2.pozna(a)
        self.assertEqual(b2.id, b.id)
        for i in range(10):
            b2.upravitelj.prejmi(pregled._ponudba(a, b2, "q-%d" % i))
        self.assertEqual(b2.podpisov, 0)

    # -- potrditve sredisca in »seje ni« za sporocila v vec delih

    def test_zavrnjen_srednji_kos_ni_sprejeto_sporocilo(self):
        """Prej smo spremljali samo prvi in zadnji kos: zavrnjen srednji kos je ostal neopazen in klicatelj je za
        sporocilo, ki ga prejemnik ne more sestaviti, dobil »sprejeto«."""
        self._seja()
        kosi = self._dolgo("d1")
        self._potrdi(kosi[0], "accepted")
        self._potrdi(kosi[1], "rejected")
        self._potrdi(kosi[2], "accepted")
        self.assertEqual((self.sprejeta, self.zavrnjena), ([], [("d1", "naprava_ni_povezana")]))
        # Vsi sprejeti: en sprejem, ob zadnjem kosu.
        kosi = self._dolgo("d2")
        for kos in kosi:
            self.assertEqual(self.sprejeta, [])
            self._potrdi(kos, "accepted")
        self.assertEqual((self.sprejeta, self.zavrnjena), (["d2"], [("d1", "naprava_ni_povezana")]))

    def test_ni_seje_sredi_dolgega_sporocila_javi_to_sporocilo(self):
        """Prejemnik sejo izgubi sredi sporocila v vec delih in to javi pri drugem kosu: sporocilo ni prislo, klicatelj
        mora izvedeti (prej smo primerjali s stevcem PRVEGA kosa in sporocilo izpustili)."""
        seja = self._seja()
        kosi = self._dolgo("d1")
        self.assertTrue(self.a.upravitelj.prejmi({"type": "data.error", "sender": self.b.id, "payload": {
            "session_id": seja.session_id, "code": "ni_seje", "seq": kosi[1]["payload"]["seq"]}}))
        self.assertEqual(self.zavrnjena, [("d1", "ni_seje")])

    def test_zapisov_o_poslanih_kosih_je_dovolj_za_dolga_sporocila(self):
        """Varovalo novega vodenja (vsak kos ima svoj zapis); na prejsnji kodi je ta preizkus uspel. Dvajset najdaljsih
        sporocil zapored: potrditve kosov PRVEGA sporocila se vedno javijo njegov sprejem."""
        self._seja()
        prvo = self._dolgo("d0", link_e2e.NAJVEC_DELOV)
        for i in range(1, 20):
            self._dolgo("d%d" % i, link_e2e.NAJVEC_DELOV)
        for kos in prvo:
            self._potrdi(kos, "accepted")
        self.assertEqual((self.sprejeta, self.zavrnjena), (["d0"], []))

    def test_sporocilo_ki_med_posiljanjem_ne_gre_ne_pusti_zapisov(self):
        """Povezava s srediscem pade sredi sporocila v vec delih: klicatelj dobi False. Zapisov o tem sporocilu potem
        ni vec - poznejsa zavrnitev ze poslanega kosa ali »seje ni« ga ne javi se enkrat."""
        seja = self._seja()
        u = self.a.upravitelj
        pravi, klici = u._poslji, []

        def poslji(sporocilo):
            klici.append(sporocilo)
            return False if len(klici) == 2 else pravi(sporocilo)      # drugi kos ne gre
        u._poslji = poslji
        self.assertFalse(u.poslji(self.b.id, {"id": "d1", "type": "control.result",
                                              "payload": {"data": "x" * (2 * link_e2e.DOLZINA_DELA + 10)}}))
        u._poslji = pravi
        self.assertTrue(self._potrdi(klici[0]))
        self.assertEqual(self.zavrnjena, [])
        self.assertTrue(u.prejmi({"type": "data.error", "sender": self.b.id, "payload": {
            "session_id": seja.session_id, "code": "ni_seje", "seq": klici[0]["payload"]["seq"]}}))
        self.assertEqual(self.zavrnjena, [])

    def test_zavrnjeno_sporocilo_se_ob_seje_ni_ne_javi_se_enkrat(self):
        """Sredisce kos zavrne (klicatelj izve), potem pride se »seje ni« s stevcem tega kosa: sporocilo je ze javljeno
        kot zavrnjeno - drugic ga ne javimo."""
        seja = self._seja()
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, dict(UKAZ, id="u2")))
        kos = self.o.cakajo.pop(0)
        self._potrdi(kos)
        self.assertEqual(self.zavrnjena, [("u2", "naprava_ni_povezana")])
        self.assertTrue(self.a.upravitelj.prejmi({"type": "data.error", "sender": self.b.id, "payload": {
            "session_id": seja.session_id, "code": "ni_seje", "seq": kos["payload"]["seq"]}}))
        self.assertEqual(self.zavrnjena, [("u2", "naprava_ni_povezana")])

    def test_predolga_koda_sredisca_postane_splosna(self):
        self._seja()
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, dict(UKAZ, id="u2")))
        self._potrdi(self.o.cakajo.pop(0), koda="k" * 5000)
        self.assertEqual(self.zavrnjena, [("u2", "zavrnjeno")])

    # -- cakajoca sporocila

    def test_pozabi_javi_cakajoca_sporocila_in_ne_drzi_pomnilnika(self):
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, dict(UKAZ)))        # caka na dogovor
        self.a.upravitelj.pozabi(self.b.id)
        self.assertEqual(self.zavrnjena, [("u1", "cas")])
        self.assertEqual(self.a.upravitelj._izhodna, {})

    def test_prepozen_odgovor_javi_cakajoce_sporocilo_in_pospravi_zapis(self):
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, dict(UKAZ)))
        self.a.zdaj += link_e2e.DOGOVOR_VELJA_S + 1
        self.o.dostavi_vse()                    # ponudba pride do b, njegov odgovor nazaj - prepozno
        self.assertFalse(self.a.upravitelj.ima_sejo(self.b.id))
        self.assertEqual(self.zavrnjena, [("u1", "cas")])
        self.assertEqual((self.a.upravitelj._dogovori, self.a.upravitelj._izhodna), ({}, {}))

    def test_zastarelo_cakajoce_sporocilo_se_javi_tudi_ko_nic_ne_posiljamo(self):
        """Sporocilo caka na dogovor, ki ne uspe, program pa nicesar vec ne poslje: prej je cistopis ostal v pomnilniku
        do naslednjega posiljanja. Zdaj ga pospravi ze vsako prejeto sporocilo prenosa in klic pospravi()."""
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, dict(UKAZ)))
        self.a.zdaj += link_e2e.V_VRSTI_VELJA_S + 1
        self.a.upravitelj.prejmi({"id": "9", "type": "data.ack", "ref_id": "e2e-neznano", "status": "accepted"})
        self.assertEqual(self.zavrnjena, [("u1", "cas")])
        self.assertEqual(self.a.upravitelj._cakajocih_bajtov(), 0)
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, dict(UKAZ, id="u2")))
        self.a.zdaj += link_e2e.V_VRSTI_VELJA_S + 1
        self.a.upravitelj.pospravi()
        self.assertEqual(self.zavrnjena, [("u1", "cas"), ("u2", "cas")])


@unittest.skipUnless(KRIPTO, "ni python3-cryptography")
class OdjemalecPoPetemPregledu(unittest.TestCase):
    """core/link_hub.Povezava po petem neodvisnem pregledu (ista lazna pot kot v OdjemalecLinka)."""
    _povezava = OdjemalecLinka._povezava
    setUp = OdjemalecLinka.setUp

    def test_oznaka_sporocila_je_niz_stevilo_ali_je_ni(self):
        """Oznako (`id`, `ref_id`) programi ponavljajo v odgovorih in potrditvah: seznam ali slovar na tem mestu bi se
        ponovil v poljubni velikosti. Sprejmemo niz do 128 znakov, obicajno stevilo ali nic."""
        for i, oznaka in enumerate((["ni", "niz"], {"a": 1}, True, 10 ** 30, 7, 2.5, None, "ok", 1e30, float("inf"))):
            self.a.odjemalec.vrsta.append(json.dumps({"id": oznaka, "type": "share.text", "sender": "stara-naprava",
                                                      "payload": {"n": i}}))
        self.a.odjemalec.vrsta.append(json.dumps({"id": "r", "ref_id": ["x", "y"], "type": "control.ack",
                                                  "sender": "stara-naprava", "payload": {"n": 99}}))
        self.sredisce.tok()
        self.assertEqual([s["payload"]["n"] for s in self.a.prejeto], [4, 5, 6, 7])

    def test_zasciteno_sporocilo_z_oznako_ki_ni_niz_ne_pride_do_programa(self):
        self.assertTrue(self.a.poslji({"id": "kratek", "type": "control.command", "target": self.b.device_id, "payload": {}}))
        self.sredisce.tok()
        for oznaka in (["x"] * 1000, {"a": "b"}):
            self.assertTrue(self.a._zascita.poslji(self.b.device_id, {"id": oznaka, "type": "control.command",
                                                                      "payload": {"action": "files.list"}}))
        self.sredisce.tok()
        self.assertEqual([s["id"] for s in self.b.prejeto if s.get("type") == "control.command"], ["kratek"])

    def test_cakajoca_sporocila_se_pospravijo_ob_vsakem_prejetem_sporocilu(self):
        """Ukaz caka na dogovor z napravo, ki ne odgovori; od sredisca prihajajo samo druga sporocila. Po roku klicatelj
        dobi zavrnitev in cistopis ne ostane v pomnilniku (prej sele ob naslednjem posiljanju)."""
        ura = [1000.0]
        self.a._zascita._ura = lambda: ura[0]
        del self.sredisce.povezave[self.b.device_id]            # ponudba se izgubi: naprava b ne odgovori
        self.assertTrue(self.a.poslji({"id": "u1", "type": "control.command", "target": self.b.device_id, "payload": {}}))
        ura[0] += link_e2e.V_VRSTI_VELJA_S + 1
        self.a.odjemalec.vrsta.append(json.dumps({"id": "s1", "type": "share.text", "sender": "stara-naprava"}))
        self.sredisce.tok()
        potrditve = [s for s in self.a.prejeto if s.get("type") == "control.ack"]
        self.assertEqual([(s["ref_id"], s["status"], s["error_code"]) for s in potrditve], [("u1", "rejected", "cas")])
        self.assertEqual(self.a._zascita._cakajocih_bajtov(), 0)


@unittest.skipUnless(KRIPTO, "ni python3-cryptography")
class SestiPregled(unittest.TestCase):
    """SESTI (ozki) neodvisni pregled sprememb po petem (7. 10. 2026): nobene najdbe, ki bi izdajo ustavila. Vsak
    preizkus je najprej padel."""
    setUp = PetiPregled.setUp
    _potrdi = PetiPregled._potrdi
    _seja = PetiPregled._seja
    _dolgo = PetiPregled._dolgo

    def test_po_seje_ni_potrditve_kosov_sporocila_ne_javijo_vec(self):
        """Prejemnik sejo izgubi; njegov »seje ni« pride PRED potrditvami sredisca za kose istega sporocila. Sporocilo
        je ze javljeno kot zavrnjeno - potrditve ga ne smejo javiti se kot sprejeto (ali zavrnjeno drugic)."""
        seja = self._seja()
        kosi = self._dolgo("d1")
        self.assertTrue(self.a.upravitelj.prejmi({"type": "data.error", "sender": self.b.id, "payload": {
            "session_id": seja.session_id, "code": "ni_seje", "seq": kosi[0]["payload"]["seq"]}}))
        self.assertEqual(self.zavrnjena, [("d1", "ni_seje")])
        self._potrdi(kosi[0], "accepted")
        self._potrdi(kosi[1], "rejected")
        self._potrdi(kosi[2], "accepted")
        self.assertEqual((self.sprejeta, self.zavrnjena), ([], [("d1", "ni_seje")]))

    def test_premor_po_neuspelem_dogovoru_velja_tudi_za_nov_upravitelj(self):
        """Sredisce ponudbo zavrne in prekine povezavo; program se poveze znova (nov upravitelj) in uporabnik takoj spet
        poslje ukaz. Premor velja za program, ne za upravitelj - sicer bi vsak tak krog pomenil nov podpis."""
        o = _Omrezje(takoj=False)
        a, b = _Naprava(o, "-control"), _Naprava(o, "-os")
        a.pozna(b)
        b.pozna(a)
        self.assertTrue(a.upravitelj.poslji(b.id, dict(UKAZ)))
        ponudba = o.cakajo.pop(0)
        a.upravitelj.prejmi({"id": "1", "type": "data.ack", "ref_id": ponudba["id"], "status": "rejected",
                             "error_code": "naprava_ni_povezana"})
        a2 = _Naprava(o, "-control", zasebni=a.zasebni)         # isti program, nov upravitelj (nova povezava)
        a2.pozna(b)
        self.assertFalse(a2.upravitelj.poslji(b.id, dict(UKAZ, id="u2")))
        self.assertEqual((a2.podpisov, o.cakajo), (0, []))
        a2.zdaj += link_e2e.NEUSPEL_DOGOVOR_CAKA_S + 0.1
        self.assertTrue(a2.upravitelj.poslji(b.id, dict(UKAZ, id="u3")))
        self.assertEqual(a2.podpisov, 1)

    def test_izrinjen_zapis_kosa_izrine_vse_kose_sporocila(self):
        """Zapisov o poslanih kosih je omejeno stevilo. Ce izpade zapis ENEGA kosa, njegove zavrnitve ne opazimo vec -
        zato z njim izpadejo vsi kosi sporocila: klicatelj ne dobi izida (iztek casa), ne pa napacnega »sprejeto«."""
        from unittest import mock
        self._seja()
        with mock.patch.object(link_e2e, "NAJVEC_IZHODNIH", 4):
            kosi = self._dolgo("d1")                            # trije zapisi, z zapisom ukaza u1 stirje
            for oznaka in ("u2", "u3"):                         # vsak novi zapis izrine najstarejsega: u1, nato prvi kos d1
                self.assertTrue(self.a.upravitelj.poslji(self.b.id, dict(UKAZ, id=oznaka)))
        self._potrdi(kosi[0], "rejected")                       # zavrnitev kosa, katerega zapis je izpadel
        self._potrdi(kosi[1], "accepted")
        self._potrdi(kosi[2], "accepted")
        self.assertEqual((self.sprejeta, self.zavrnjena), ([], []))

    def test_pospravi_ne_caka_na_zaklep(self):
        """pospravi() klice bralna nit ob VSAKEM prejetem sporocilu: ne sme obstati, kadar zaklep upravitelja drzi nit,
        ki podpisuje ali posilja - sicer bi branje stalo pri vsakem sporocilu, ne le pri sporocilih zascite."""
        import threading
        u = self.a.upravitelj
        self.assertTrue(u.poslji(self.b.id, dict(UKAZ)))        # nekaj caka v vrsti
        drzi, spusti = threading.Event(), threading.Event()

        def posiljatelj():
            with u._zaklep:
                drzi.set()
                spusti.wait(5)
        nit = threading.Thread(target=posiljatelj, daemon=True)
        nit.start()
        self.assertTrue(drzi.wait(2))
        bralna = threading.Thread(target=u.pospravi, daemon=True)
        bralna.start()
        bralna.join(1)
        zastala = bralna.is_alive()
        spusti.set()
        nit.join(2)
        bralna.join(2)
        self.assertFalse(zastala)

    def test_napaka_pri_posiljanju_enega_cakajocega_sporocila_ne_izgubi_drugih(self):
        """Tri sporocila cakajo na dogovor. Ko odgovor pride, posiljanje drugega vrze izjemo: prvo in tretje gresta, za
        drugo klicatelj izve. Prej sta drugo in tretje izginili brez sledu (vrsta je bila ze izpraznjena)."""
        u = self.a.upravitelj
        for i in (1, 2, 3):
            self.assertTrue(u.poslji(self.b.id, dict(UKAZ, id="u%d" % i)))
        pravi, kosov = u._poslji, []

        def poslji(sporocilo):
            if sporocilo.get("type") == "data.chunk":
                kosov.append(sporocilo)
                if len(kosov) == 2:
                    raise OSError("vticnica je padla")
            return pravi(sporocilo)
        u._poslji = poslji
        self.o.dostavi_vse()
        u._poslji = pravi
        self.assertEqual([s["id"] for s, _od, _j in self.b.prejeta], ["u1", "u3"])
        self.assertEqual(self.zavrnjena, [("u2", "ni_poslano")])

    def test_pozabi_vse_javi_cakajoca_sporocila(self):
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, dict(UKAZ)))
        self.a.upravitelj.pozabi_vse()
        self.assertEqual(self.zavrnjena, [("u1", "cas")])
        self.assertEqual(self.a.upravitelj._cakajocih_bajtov(), 0)


if __name__ == "__main__":
    unittest.main()
