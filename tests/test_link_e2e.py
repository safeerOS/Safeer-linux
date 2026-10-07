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

    def __init__(self, omrezje: "_Omrezje", pripona: str = "") -> None:
        self.zasebni = ec.generate_private_key(ec.SECP256R1())
        self.kljuc = _spki(self.zasebni)
        self.jedro = link_krog.id_iz_kljuca(self.kljuc)
        self.id = self.jedro + pripona
        self.krog = {}
        self.prejeta = []          # (notranje sporocilo, id posiljatelja, jedro iz kljuca)
        self.seje = []
        self.zdaj = 1000.0
        self.omrezje = omrezje
        self.upravitelj = link_e2e.Upravitelj(
            moj_id=lambda: self.id,
            poslji=lambda s: omrezje.poslji(self.id, s),
            podpisi=lambda b: base64.b64encode(self.zasebni.sign(b, ec.ECDSA(hashes.SHA256()))).decode(),
            kljuc_za=lambda i: self.krog.get(i),
            preveri=link_krog.preveri_podpis,
            id_iz_kljuca=link_krog.id_iz_kljuca,
            ob_sporocilu=lambda s, od, jedro: self.prejeta.append((s, od, jedro)),
            ob_seji=self.seje.append,
            ura=lambda: self.zdaj)
        omrezje.naprave[self.id] = self

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


UKAZ = {"id": "u1", "type": "control.command", "payload": {"action": "files.list", "args": {"path": "share:0:"}}}


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

    def test_po_ponovnem_zagonu_prejemnika_se_dogovor_ponovi_in_ukaz_pride(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.b.upravitelj.pozabi_vse()                           # b se je znova zagnal: sej ne pozna vec
        self.b.prejeta.clear()
        drugi = {"id": "u2", "type": "control.command", "payload": {"action": "apps.list"}}
        self.assertTrue(self.a.upravitelj.poslji(self.b.id, drugi))
        self.assertEqual([s for s, _o, _j in self.b.prejeta], [drugi])
        self.assertEqual(sum(1 for s in self.o.videno if '"data.offer"' in s), 2)
        self.assertEqual(sum(1 for s in self.o.videno if '"data.error"' in s), 1)

    def test_star_ukaz_se_po_izgubljeni_seji_ne_ponovi(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.b.upravitelj.pozabi_vse()
        self.b.prejeta.clear()
        o = self.o
        o.takoj = False
        self.a.upravitelj.poslji(self.b.id, {"id": "u2", "type": "control.command", "payload": {}})
        self.a.zdaj += link_e2e.PONOVI_MLAJSE_OD_S + 1          # odgovor »ni seje« pride prepozno
        o.dostavi_vse()
        self.assertEqual(self.b.prejeta, [])

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
        self.assertEqual(self.zavrnjena, [(UKAZ, "ni_naprave"), (drugi, "ni_naprave")])
        # naslednji ukaz zacne nov dogovor takoj (ne caka na iztek starega)
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.assertEqual([s["type"] for s in self.o.cakajo], ["data.offer"])

    def test_zavrnjen_kos_zavrne_svoje_sporocilo_seja_ostane(self):
        self.a.upravitelj.poslji(self.b.id, UKAZ)
        self.o.dostavi_vse()
        drugi = {"id": "u2", "type": "control.command", "payload": {}}
        self.a.upravitelj.poslji(self.b.id, drugi)
        kos = self.o.cakajo.pop(0)
        self.assertTrue(self.a.upravitelj.prejmi(self._potrditev(kos["id"], koda="naprava_ni_povezana")))
        self.assertEqual(self.zavrnjena, [(drugi, "naprava_ni_povezana")])
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
        self.assertEqual(self.sprejeta, [drugi])
        self.assertTrue(self.a.upravitelj.prejmi(self._potrditev(kos["id"], stanje="accepted", koda="")))   # ponovljena
        self.assertEqual(self.sprejeta, [drugi])
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
        self.assertEqual([z[2]["id"] for z in seja.zadnja], ["u4"])       # za ponovitev hranimo samo sveze
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
            ob_sporocilu=p._zasciteno_sporocilo, ob_seji=p.seje.append, ob_zavrnitvi=p._zasciteno_zavrnjeno)
        self.sredisce.povezave[p.device_id] = p
        self.kljuci[p.device_id] = kljuc
        return p

    def setUp(self):
        from unittest import mock
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

    def test_dokaz_kljuca_najvec_enkrat_na_minuto_in_ne_za_ze_preverjene(self):
        from unittest import mock
        from core import link_hub
        self.kljuci.pop(self.a.device_id)        # b nasega kljuca nima: ponudbe ne more preveriti in ne odgovori
        ura = [1000.0]
        with mock.patch.object(link_hub.time, "monotonic", lambda: ura[0]):
            self.a._dokazi_kljuce()
            self.sredisce.tok()
            self.assertEqual([json.loads(s)["type"] for s in self.sredisce.videno], ["data.offer"])
            ura[0] += 30
            self.a._dokazi_kljuce()
            self.assertEqual(len(self.sredisce.videno), 1)                      # prezgodaj
            ura[0] += link_hub.DOKAZ_KLJUCA_NAJVEC_NA_S
            self.a._zascita.pozabi(self.b.device_id)      # upravitelj v preizkusu ima pravo uro: stari dogovor je zanj se svez
            self.a._dokazi_kljuce()
            self.assertEqual(len(self.sredisce.videno), 2)                      # po minuti nov poskus
            ura[0] += 2 * link_hub.DOKAZ_KLJUCA_NAJVEC_NA_S
            with mock.patch("core.link_dostop.zahteva_zascito", lambda device_id: True):
                self.a._dokazi_kljuce()
            self.assertEqual(len(self.sredisce.videno), 2)                      # ze preverjena: nic
            self.a._zapomni_zmoznosti([{"id": self.b.device_id, "capabilities": ["remote"]}])
            ura[0] += 2 * link_hub.DOKAZ_KLJUCA_NAJVEC_NA_S
            self.a._dokazi_kljuce()
            self.assertEqual(len(self.sredisce.videno), 2)                      # zascite ne prijavi: nic

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
        self.assertEqual(self.a._vprasanja, {})

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


if __name__ == "__main__":
    unittest.main()
