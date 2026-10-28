"""Ciscenje ikon SVG iz tujih virov (core/varna_svg.py) in orodje za katalog Sporocil (tools/izdelaj_katalog_sporocil.py).
Preizkusa na pravih ikonah tecejo, ce je klon ferdium-recipes v SAFEER_FERDIUM_RECIPES."""
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import varna_svg  # noqa: E402
from core.varna_svg import NevarnaSvg, ocisti  # noqa: E402

RECEPTI = os.environ.get("SAFEER_FERDIUM_RECIPES", "")
SAFEER = KOREN
ORODJE = os.path.join(KOREN, "tools", "izdelaj_katalog_sporocil.py")
S = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10">%s</svg>'


def _drevo(svg):
    return ET.fromstring(svg)


def _imena(svg):
    return {el.tag.split("}")[-1] for el in _drevo(svg).iter()}


def _vsi_atributi(svg):
    return [(el.tag.split("}")[-1], k, v) for el in _drevo(svg).iter() for k, v in el.attrib.items()]


def test_odstrani_script_in_poddrevo():
    izid = ocisti(S % '<script>alert(1)</script><g><script type="text/javascript"><![CDATA[x()]]></script>'
                       '<path d="M0 0h10v10z"/></g>')
    assert "script" not in _imena(izid) and "alert" not in izid and "x()" not in izid
    assert "path" in _imena(izid)


def test_odstrani_foreignobject_s_html():
    izid = ocisti(S % '<foreignObject><div xmlns="http://www.w3.org/1999/xhtml"><iframe src="https://zlo.example/">'
                       '</iframe></div></foreignObject><rect width="1" height="1"/>')
    assert _imena(izid) == {"svg", "rect"} and "zlo" not in izid


def test_odstrani_dogodke_on():
    izid = ocisti('<svg xmlns="http://www.w3.org/2000/svg" onload="a()"><rect onclick="b()" ONMOUSEOVER="c()" '
                  'onfocusin="d()" width="2"/></svg>')
    assert not [a for a in _vsi_atributi(izid) if a[1].lower().startswith("on")]
    assert 'width="2"' in izid


@pytest.mark.parametrize("sklic", [
    "https://zlo.example/x.svg#a", "//zlo.example/a", "javascript:alert(1)", " JaVa\tScRiPt:alert(1)",
    "data:image/svg+xml;base64,PHN2Zy8+", "file:///etc/passwd#a", "x.svg#a",
])
def test_zunanji_in_javascript_href(sklic):
    izid = ocisti(S % ('<use href="%s"/><use xlink:href="%s"/><linearGradient id="g" xlink:href="%s"/>'
                       % ((sklic,) * 3)))
    assert not [a for a in _vsi_atributi(izid) if a[1].endswith("href")]


def test_notranji_href_ostane():
    izid = ocisti(S % '<defs><path id="p" d="M0 0"/></defs><use xlink:href="#p"/><use href="#p"/>')
    hrefi = [v for _, k, v in _vsi_atributi(izid) if k.endswith("href")]
    assert hrefi == ["#p", "#p"]


def test_a_in_animate_gresta_ven():
    izid = ocisti(S % '<a href="javascript:alert(1)"><rect width="1"/></a>'
                       '<rect width="2"><set attributeName="href" to="javascript:x"/>'
                       '<animate attributeName="fill" values="red"/></rect>')
    assert _imena(izid) == {"svg", "rect"} and "javascript" not in izid


def test_image_samo_rastrski_data():
    png = "data:image/png;base64,iVBORw0KGgo="
    izid = ocisti(S % ('<image width="1" height="1" xlink:href="%s"/><image xlink:href="https://zlo.example/a.png"/>'
                       '<image href="data:image/svg+xml;base64,PHN2Zy8+"/>' % png))
    slike = [el for el in _drevo(izid).iter() if el.tag.endswith("image")]
    assert len(slike) == 1 and list(slike[0].attrib.values())[-1] == png


@pytest.mark.parametrize("vrednost", ["url(https://zlo.example/a)", "url('//zlo.example/a')",
                                      "url(data:image/png;base64,AA)", "url(javascript:x)"])
def test_zunanji_url_v_atributu(vrednost):
    izid = ocisti(S % ('<rect fill="%s" filter="%s" width="3"/>' % (vrednost, vrednost)))
    atr = dict((k, v) for _, k, v in _vsi_atributi(izid) if _ == "rect")
    assert "fill" not in atr and "filter" not in atr and atr["width"] == "3"


def test_notranji_url_ostane():
    izid = ocisti(S % '<defs><linearGradient id="g1"/></defs><rect fill="url(#g1)" width="1"/>')
    assert 'fill="url(#g1)"' in izid


def test_css_v_style():
    izid = ocisti(S % ('<style>@import url(https://zlo.example/a.css); .a{fill:url(https://zlo.example/b)} '
                       '.b{fill:url(#g)} .c{fill:red}</style><rect class="a" style="fill:url(//zlo.example/c);'
                       'stroke:blue" width="1"/>'))
    assert "zlo.example" not in izid and "@import" not in izid
    assert "url(#g)" in izid and "fill:red" in izid and "stroke:blue" in izid


@pytest.mark.parametrize("css", [".a{background:expression(alert(1))}", ".a{fill:u\\72l(https://zlo.example/)}",
                                 ".a{-moz-binding:url(#x)}", ".a{fill:red}</style><script>x()</script>",
                                 "@\\69mport 'https://zlo.example/a.css';"])
def test_nevaren_css_gre_ves_ven(css):
    assert varna_svg.ocisti_css(css) == ""


def test_style_atribut_z_ubeznico_gre_ven():
    izid = ocisti(S % '<rect style="fill:u\\72l(https://zlo.example/)" width="1"/>')
    assert "style" not in izid and "zlo" not in izid


def test_tuji_imenski_prostori_in_metadata():
    izid = ocisti('<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/'
                  'inkscape" xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" '
                  'inkscape:version="1"><sodipodi:namedview/><metadata><x/></metadata>'
                  '<path inkscape:label="a" d="M0 0" data-x="1" aria-label="b"/></svg>')
    assert _imena(izid) == {"svg", "path"} and "inkscape" not in izid and "data-x" not in izid


def test_notranje_entitete_se_razresijo():
    izid = ocisti('<?xml version="1.0"?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
                  '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd" [<!ENTITY ns_svg "http://www.w3.org/2000/svg">'
                  '<!-- komentar --><!ENTITY barva "red">]><svg xmlns="&ns_svg;"><rect fill="&barva;"/></svg>')
    assert "DOCTYPE" not in izid and 'fill="red"' in izid


@pytest.mark.parametrize("doctype", [
    '<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]>',
    '<!DOCTYPE svg [<!ENTITY % p "x"> %p;]>',
    '<!DOCTYPE svg [<!ENTITY a "&b;&b;"><!ENTITY b "x">]>',
    '<!DOCTYPE svg [<!ELEMENT svg ANY>]>',
])
def test_nevarne_entitete_zavrnejo_ikono(doctype):
    with pytest.raises(NevarnaSvg):
        ocisti(doctype + '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')


def test_razsiritev_entitet_je_omejena():
    vrednost = "x" * 100_000
    telo = "".join("&e;" for _ in range(100))
    with pytest.raises(NevarnaSvg) as napaka:
        ocisti('<!DOCTYPE svg [<!ENTITY e "%s">]><svg xmlns="http://www.w3.org/2000/svg"><title>%s</title></svg>'
               % (vrednost, telo))
    assert napaka.value.args[0] == "entiteta"   # zavrnjeno PRED razsiritvijo, ne sele pri velikosti izhoda


@pytest.mark.parametrize("vhod", ["", "   ", "ni xml", "<html><script>x()</script></html>",
                                  '<svg xmlns="http://www.w3.org/2000/svg"><rect></svg>',
                                  '<x:svg xmlns:x="urn:zlo"/>', b"\xff\xfe<svg/>"])
def test_neveljaven_vhod(vhod):
    with pytest.raises(NevarnaSvg):
        ocisti(vhod)


def test_omejitev_velikosti(monkeypatch):
    monkeypatch.setattr(varna_svg, "NAJVEC_IZHOD", 200)
    with pytest.raises(NevarnaSvg):
        ocisti(S % ('<path d="%s"/>' % ("M0 0 " * 100)))
    with pytest.raises(NevarnaSvg):
        ocisti(b"<svg>" + b" " * (varna_svg.NAJVEC_VHOD + 1) + b"</svg>")


def test_besedilo_in_bom():
    izid = ocisti("\ufeff" + S % "<title>Ikona &amp; &lt;b&gt;</title><text>A<tspan>B</tspan>C</text>")
    koren = _drevo(izid)
    assert koren.find("{http://www.w3.org/2000/svg}title").text == "Ikona & <b>"
    assert "".join(koren.find("{http://www.w3.org/2000/svg}text").itertext()) == "ABC"


def _ikone_receptov():
    mapa = os.path.join(RECEPTI, "recipes")
    if not RECEPTI or not os.path.isdir(mapa):
        return []
    return sorted(os.path.join(mapa, r, "icon.svg") for r in os.listdir(mapa)
                  if os.path.isfile(os.path.join(mapa, r, "icon.svg")))


@pytest.mark.skipif(not _ikone_receptov(), reason="ni klona ferdium-recipes (SAFEER_FERDIUM_RECIPES)")
def test_vse_ikone_receptov_varne_in_idempotentne():
    ok = zavrnjene = 0
    for pot in _ikone_receptov():
        try:
            izid = ocisti(open(pot, "rb").read())
        except NevarnaSvg as e:
            assert e.args[0] in ("velikost",), (pot, e.args)
            zavrnjene += 1
            continue
        ok += 1
        assert ocisti(izid) == izid, pot
        nizko = izid.lower()
        for prepovedano in ("<script", "foreignobject", "javascript:", "<!doctype", "<!entity", " on"):
            if prepovedano == " on":
                assert not [a for a in _vsi_atributi(izid) if a[1].lower().startswith("on")], pot
            else:
                assert prepovedano not in nizko, (pot, prepovedano)
        for _, k, v in _vsi_atributi(izid):
            if k.endswith("href"):
                assert v.startswith("#") or v.startswith("data:image/"), (pot, k, v)
    assert ok >= 400 and ok + zavrnjene == len(_ikone_receptov())


@pytest.mark.skipif(not RECEPTI or not os.path.isdir(os.path.join(RECEPTI, ".git")), reason="ni klona ferdium-recipes")
def test_izdelava_kataloga(tmp_path):
    izhod = tmp_path / "k.json"
    ukaz = [sys.executable, ORODJE, "--recepti", RECEPTI, "--izhod", str(izhod)]
    if os.path.isdir(SAFEER):
        ukaz += ["--safeer", SAFEER]
    subprocess.run(ukaz, check=True, capture_output=True)
    k = json.loads(izhod.read_text("utf-8"))
    assert k["vir"]["licenca"] == "MIT" and "Permission is hereby granted" in k["vir"]["licenca_besedilo"]
    assert len(k["vir"]["commit"]) == 40
    ids = [v["id"] for v in k["katalog"]]
    assert len(ids) == len(set(ids)) and {"chatgpt", "claude-ai", "google-gemini", "gmail", "telegram"} <= set(ids)
    for v in k["katalog"]:
        assert list(v)[:5] == ["id", "ime", "vrsta", "splet", "prenos"]
        assert v["vrsta"] in ("klepet", "posta", "ai") and v["splet"].startswith("https://") and "{" not in v["splet"]
        assert v["vir"]["licenca"] == "MIT" and v["vir"]["commit"] == k["vir"]["commit"]
        assert v["vir"]["povezava"].endswith("/recipes/" + v["id"])
        if v["ikona_svg"]:
            assert ocisti(v["ikona_svg"]) == v["ikona_svg"]
    if os.path.isdir(SAFEER):
        po_id = {v["id"]: v for v in k["katalog"]}
        assert po_id["messenger"]["splet"] == "https://www.facebook.com/messages/"   # PRESELJENI iz Safeerja
        assert po_id["android-messages"]["obstojeci"] == "google-messages"
    # brez kode receptov: v katalogu ni nobenega izseka webview.js
    besedilo = izhod.read_text("utf-8")
    assert "setBadge" not in besedilo and "module.exports" not in besedilo


def test_poenoti_naslov():
    sys.path.insert(0, os.path.dirname(ORODJE))
    import izdelaj_katalog_sporocil as ik
    assert ik.poenoti_naslov("https://Web.WhatsApp.com") == "https://web.whatsapp.com/"
    for slab in ["http://a.com", "https://{teamId}.slack.com", "https://u:p@a.com", "javascript:x", "https://a",
                 "https://a.com /x", ""]:
        assert ik.poenoti_naslov(slab) == "", slab


def test_url_s_presledkom_v_style_ne_ostane():
    # Pregled naloge 45: »url (« s presledkom je element <style> prej obdrzal (zunanji vir).
    assert "zunaj" not in varna_svg.ocisti_css("rect { fill: url (http://zunaj.example/x.png) }")
    assert varna_svg.ocisti_css("rect { fill: url (#g) }").count("#g") == 1
