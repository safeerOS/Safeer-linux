"""Safeer Agent: razumevanje (shema, vec nalog), izvajanje prek Linka (lazne naprave), seja (trajanje, ustavitev)."""
from core.agent import izvajanje, razumevanje, seja

NAPRAVE = [
    {"id": "n-tv", "ime": "Dnevna soba", "platforma": "tv", "vrsta": "screen"},
    {"id": "n-tab", "ime": "Tablica", "platforma": "tablet", "vrsta": "screen"},
    {"id": "n-tel", "ime": "Telefon", "platforma": "phone", "vrsta": "screen"},
    {"id": "n-pc-control", "ime": "Racunalnik", "platforma": "linux", "vrsta": "control"},
]


class Link:
    def __init__(self, programi=None):
        self.klici = []
        self.programi = programi or {"n-tab": [{"id": "com.google.android.youtube", "name": "YouTube"},
                                               {"id": "si.rtv.app", "name": "RTV Slovenija"}]}

    def naprave(self):
        return NAPRAVE

    def ukaz(self, nid, dejanje, parametri):
        self.klici.append((nid, dejanje, parametri))
        if dejanje == "apps.list":
            return {"ok": True, "data": {"items": self.programi.get(nid, []), "enabled": nid in self.programi}}
        return {"ok": True}


def test_preveri_odgovor():
    n = razumevanje.preveri({"naloge": [{"dejanje": "utisaj", "naprava": "tv", "kaj": ""},
                                        {"dejanje": "leti", "naprava": "tv", "kaj": ""},
                                        {"dejanje": "odpri_aplikacijo", "naprava": "tablica", "kaj": "YouTube"}]})
    assert [(x.dejanje, x.naprava, x.kaj) for x in n] == [("utisaj", "tv", ""), ("odpri_aplikacijo", "tablica", "YouTube")]
    assert razumevanje.preveri({"dejanje": "pavza", "naprava": "tukaj", "kaj": ""})[0].dejanje == "pavza"
    assert razumevanje.preveri("x") == [] and len(razumevanje.preveri({"naloge": [{"dejanje": "pavza", "naprava": "tv"}] * 9})) == 5


def test_sporocila_imajo_zglede_z_vec_nalogami():
    s = razumevanje.sporocila("glasneje")
    assert s[0]["role"] == "system" and s[-1] == {"role": "user", "content": "glasneje"}
    assert any('"naloge"' in m["content"] and m["content"].count("dejanje") == 2 for m in s if m["role"] == "assistant")


def test_razumi_model_nedosegljiv():
    def pade(*_a):
        raise OSError("ni povezave")
    r = razumevanje.razumi("glasneje", pade)
    assert r.naloge == [] and "ni dosegljiv" in r.napaka


def test_izvajanje_glasnost_in_aplikacija():
    link = Link()
    iz = izvajanje.Izvajalec(link.naprave, link.ukaz)
    a = izvajanje.izvedi(razumevanje.Naloga("utisaj", "tv"), iz)
    b = izvajanje.izvedi(razumevanje.Naloga("odpri_aplikacijo", "tablica", "youtube"), iz)
    assert a.ok and "Utišano" in a.besedilo and b.ok and "YouTube" in b.besedilo
    assert link.klici[0] == ("n-tv", "volume", {"direction": "mute"})
    assert link.klici[-1] == ("n-tab", "apps.launch", {"app": "com.google.android.youtube"})


def test_izvajanje_tukaj_in_manjkajoca_naprava():
    link = Link()
    iz = izvajanje.Izvajalec(lambda: NAPRAVE[:2], link.ukaz)
    assert izvajanje.izvedi(razumevanje.Naloga("pavza", "tukaj"), iz, tukaj="n-tab").ok
    assert link.klici[-1] == ("n-tab", "key", {"key": "pause"})
    r = izvajanje.izvedi(razumevanje.Naloga("pavza", "telefon"), iz)
    assert not r.ok and "ni v Linku" in r.besedilo


def test_naslov_strani():
    assert izvajanje.naslov_strani("siol.net") == "https://siol.net"
    assert izvajanje.naslov_strani("vreme ljubljana").startswith("https://duckduckgo.com/?q=vreme+ljubljana")
    assert izvajanje.naslov_strani("") == ""


def test_seja_vec_nalog_po_vrsti():
    link = Link()
    model = lambda s, shema: {"naloge": [{"dejanje": "utisaj", "naprava": "tv", "kaj": ""},
                                         {"dejanje": "odpri_aplikacijo", "naprava": "tablica", "kaj": "YouTube"}]}
    s = seja.Seja(izvajalec=izvajanje.Izvajalec(link.naprave, link.ukaz), klic_modela=model)
    k = s.narocilo("utišaj televizor in na tablici odpri YouTube")
    assert [x.ok for x in k] == [True, True] and len(s.koraki) == 2


def test_seja_trajanje_in_ustavitev():
    t = [0.0]
    link = Link()
    model = lambda s, shema: {"naloge": [{"dejanje": "pavza", "naprava": "tv", "kaj": ""}]}
    s = seja.Seja(trajanje_min=1, izvajalec=izvajanje.Izvajalec(link.naprave, link.ukaz), klic_modela=model, ura=lambda: t[0])
    assert s.narocilo("pavza")[0].ok
    t[0] = 61
    assert s.narocilo("pavza")[0].izid == "Seja je končana."
    n = seja.Seja(trajanje_min=None, izvajalec=izvajanje.Izvajalec(link.naprave, link.ukaz), klic_modela=model, ura=lambda: 1e9)
    assert n.tece()
    n.ustavi()
    assert not n.tece()
    assert seja.Seja(trajanje_min=0).trajanje_min == 1      # najmanj 1 minuta


def test_storitev_agent_ask_in_ustavitev(monkeypatch):
    from core import link_daljinec, link_dostop
    from core.agent import storitev
    assert link_dostop.zahteva_dejanja("agent.ask") == link_dostop.VSE      # samo ozji krog
    link = Link()
    model = lambda s, shema: {"naloge": [{"dejanje": "utisaj", "naprava": "tv", "kaj": ""}]}
    monkeypatch.setattr(storitev, "nova_seja", lambda **k: seja.Seja(
        izvajalec=izvajanje.Izvajalec(link.naprave, link.ukaz), klic_modela=model, **k))
    storitev._seje.clear()
    odg = []
    storitev.vprasaj({"text": "utišaj tv", "minutes": 5}, "n-tel", odg.append, link_daljinec.izid, v_ozadju=False)
    assert odg[-1]["ok"] and odg[-1]["data"]["steps"][0]["text"].startswith("Utišano")
    assert 0 < odg[-1]["data"]["session_left_s"] <= 300
    storitev.vprasaj({"stop": True}, "n-tel", odg.append, link_daljinec.izid, v_ozadju=False)
    assert odg[-1]["ok"] and "n-tel" not in storitev._seje
    storitev.vprasaj({"text": ""}, "n-tel", odg.append, link_daljinec.izid, v_ozadju=False)
    assert not odg[-1]["ok"]


def test_control_pozna_agent_ask(monkeypatch):
    from core import link_daljinec
    from core.agent import storitev
    klici = []
    monkeypatch.setattr(storitev, "vprasaj", lambda p, pos, k, iz: klici.append((p, pos)))
    link_daljinec.izvedi_control("agent.ask", {"text": "pavza"}, lambda u: None, lambda r: None, posiljatelj="n-x")
    assert klici == [({"text": "pavza"}, "n-x")]


def test_popravi_stisaj_utisaj():
    N = razumevanje.Naloga
    assert razumevanje.popravi("stišaj televizor", [N("utisaj", "tv")])[0].dejanje == "glasnost_dol"
    assert razumevanje.popravi("utišaj tv", [N("glasnost_dol", "tv")])[0].dejanje == "utisaj"
    assert razumevanje.popravi("odpri Netflix na tv in stišaj ga", [N("odpri_aplikacijo", "tv"), N("utisaj", "tv")])[1].dejanje == "glasnost_dol"
    obe = [N("utisaj", "tv"), N("glasnost_dol", "tablica")]
    assert [n.dejanje for n in razumevanje.popravi("utišaj tv in stišaj tablico", obe)] == ["utisaj", "glasnost_dol"]
    assert razumevanje.popravi("pavza", [N("pavza", "tukaj")])[0].dejanje == "pavza"


def test_naslov_modela(monkeypatch, tmp_path):
    monkeypatch.setenv("SAFEER_AGENT", "http://192.0.2.5:8085")
    assert razumevanje.naslov_modela() == "http://192.0.2.5:8085"
    monkeypatch.setenv("SAFEER_AGENT", "ftp://x")
    assert razumevanje.naslov_modela() == ""
    monkeypatch.delenv("SAFEER_AGENT")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert razumevanje.naslov_modela() == ""
    (tmp_path / ".config" / "safeer-agent").mkdir(parents=True)
    (tmp_path / ".config" / "safeer-agent" / "naslov").write_text("http://192.0.2.6:8085\n")
    assert razumevanje.naslov_modela() == "http://192.0.2.6:8085"


def test_storitev_tukaj_je_ciljna_naprava(monkeypatch):
    from core import link_daljinec
    from core.agent import storitev
    link = Link()
    model = lambda s, shema: {"naloge": [{"dejanje": "pavza", "naprava": "tukaj", "kaj": ""}]}
    monkeypatch.setattr(storitev, "nova_seja", lambda **k: seja.Seja(
        izvajalec=izvajanje.Izvajalec(link.naprave, link.ukaz), klic_modela=model, **k))
    storitev._seje.clear()
    odg = []
    storitev.vprasaj({"text": "pavza", "here": "n-tv"}, "n-tel", odg.append, link_daljinec.izid, v_ozadju=False)
    assert link.klici[-1] == ("n-tv", "key", {"key": "pause"})


def test_isci_in_predvajaj():
    link = Link()
    iz = izvajanje.Izvajalec(link.naprave, link.ukaz)
    a = izvajanje.izvedi(razumevanje.Naloga("isci", "racunalnik", "risanke"), iz)
    assert a.ok and link.klici[-1] == ("n-pc-control", "search.query", {"q": "risanke"})
    b = izvajanje.izvedi(razumevanje.Naloga("predvajaj", "tv", "Radio 1"), iz)
    assert b.ok and link.klici[-1][1] == "open_in_app" and "Radio+1" in link.klici[-1][2]["url"]
    c = izvajanje.izvedi(razumevanje.Naloga("predvajaj", "tv", ""), iz)
    assert not c.ok


def test_predvajaj_brez_aplikacije_odpre_stran():
    link = Link()
    resnicni = link.ukaz
    link.ukaz = lambda nid, d, p: {"ok": False} if d == "open_in_app" else resnicni(nid, d, p)
    iz = izvajanje.Izvajalec(link.naprave, link.ukaz)
    assert izvajanje.izvedi(razumevanje.Naloga("predvajaj", "tablica", "Siddharta"), iz).ok
    assert link.klici[-1][1] == "open_url"


def test_storitev_brez_modela_ima_kodo(monkeypatch):
    from core import link_daljinec
    from core.agent import storitev
    def pade(*_a):
        raise OSError("x")
    monkeypatch.setattr(storitev, "nova_seja", lambda **k: seja.Seja(klic_modela=pade, **k))
    storitev._seje.clear()
    odg = []
    storitev.vprasaj({"text": "glasneje"}, "n-tel", odg.append, link_daljinec.izid, v_ozadju=False)
    assert odg[-1]["ok"] is False and odg[-1]["code"] == "agent_ni_modela"
