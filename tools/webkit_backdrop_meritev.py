#!/usr/bin/env python3
"""Meritve popravka WebKit za plasti backdrop-filter v kompozitorju Skia (packaging/webkit/skia-backdrop-2n.patch).

Goli WebKitWebView (GTK 3, WebKit2 4.1) z izbranimi knjiznicami WebKitGTK (mapa namestitve gradnje, npr. brez popravka
in s popravkom), da sta razlicici primerljivi brez ostalega Safeerja. Za vsako stran in razlicico svoj proces.

    webkit_backdrop_meritev.py strani MAPA                       # zapise testne strani (HTML)
    webkit_backdrop_meritev.py meri --lib NAMESTITEV --stran IME [--sekunde 10]   # ena meritev, JSON na stdout
    webkit_backdrop_meritev.py posnetki --lib NAMESTITEV --izhod MAPA          # PNG strani za primerjavo pikslov
    webkit_backdrop_meritev.py primerjaj MAPA_A MAPA_B                         # stevilo razlicnih pikslov po PNG
    webkit_backdrop_meritev.py vse --lib IME=NAMESTITEV [--lib ...] --izhod MAPA   # vse meritve in posnetki

Meritev: najvecji RSS spletnega procesa (WebKitWebProcess) in njegov cas CPU v celem oknu; v ustaljenem delu (brez
prvih USTALITEV s nalaganja) intervali requestAnimationFrame (mediana, najvecji), stevilo okvirjev in CPU na okvir. Posnetek je risba pogleda (Gtk.Widget.draw), torej izhod
kompozitorja, ne webkit_web_view_get_snapshot (ta stran narise brez kompozitorja in plasti backdrop ne preizkusi).
Tece v okolju, v katerem je bil WebKit preveden (npr. flatpak run org.gnome.Sdk//50), knjiznice prek LD_LIBRARY_PATH.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time

SIRINA, VISINA = 1280, 720
USTALITEV = 2.0   # s od zacetka nalaganja, ki jih ustaljeni del meritve izpusti

# ---- testne strani --------------------------------------------------------------------------------------------------

# Brez drsnika: prekrivni drsnik po spremembi strani pobledi in bi posnetku dodal od casa odvisne piksle.
OZADJE = """
html { scrollbar-width: none; }
body { margin: 0; font: 16px sans-serif; background: linear-gradient(135deg, #f6d365, #fda085 40%, #5ee7df 70%, #b490ca); }
.vsebina { position: absolute; left: 0; top: 0; width: 1280px; }
.vsebina p { margin: 0; padding: 6px 12px; font-size: 22px; color: #123; }
.kvadrat { position: absolute; width: 90px; height: 90px; border-radius: 12px; }
"""


def _vsebina(animirana=False):
    kvadrati = []
    barve = ['#e63946', '#1d3557', '#2a9d8f', '#f4a261', '#6a4c93', '#06d6a0']
    for i in range(18):
        x, y = 40 + (i * 157) % 1150, 30 + (i * 97) % 600
        anim = ' animation: premik %.1fs linear infinite alternate;' % (1.5 + i % 4 * 0.5) if animirana else ''
        kvadrati.append('<div class="kvadrat" style="left:%dpx; top:%dpx; background:%s;%s"></div>' % (x, y, barve[i % 6], anim))
    besedilo = ''.join('<p>Vrstica %d: Safeer backdrop-filter test 0123456789 ABCDEFGHIJ</p>' % i for i in range(20))
    return '<div class="vsebina">%s%s</div>' % (besedilo, ''.join(kvadrati))


def _stran(slog, telo, skript=''):
    return ('<!DOCTYPE html><html><head><meta charset="utf-8"><style>%s%s'
            '@keyframes premik { from { transform: translateX(0); } to { transform: translateX(160px); } }</style>'
            '</head><body>%s<script>%s</script></body></html>') % (OZADJE, slog, telo, skript)


def _zlozene(n, filtri, animirana=False, dodatek=''):
    """n zlozenih (prekrivajocih se) plasti, vsaka 3 px zamaknjena; filtri: seznam vrednosti backdrop-filter po vrsti."""
    plasti = ''.join('<div class="z" style="left:%dpx; top:%dpx; backdrop-filter:%s"></div>' % (200 + 3 * i, 150 + 3 * i, filtri[i % len(filtri)])
                     for i in range(n))
    return _stran('.z { position: absolute; width: 420px; height: 160px; background: rgba(255,255,255,0.06); %s }' % dodatek,
                  _vsebina(animirana) + plasti)


def _neprekrivajoce(n):
    plasti = ''.join('<div style="height:120px"></div><div style="height:20px; backdrop-filter: blur(0)"></div>' for _ in range(n))
    return _stran('', _vsebina() + '<div style="position:relative">%s</div>' % plasti)


MESANO = ['blur(0)', 'blur(2px)', 'blur(6px)', 'blur(10px)']

# Strani za meritve (pomnilnik, CPU, interval okvirjev).
MERITVE = {
    'neprekrivajoce-28': lambda: _neprekrivajoce(28),
    'zlozene-30': lambda: _zlozene(30, ['blur(0)']),
    'anim-18-blur0': lambda: _zlozene(18, ['blur(0)'], animirana=True),
    'anim-18-blur6': lambda: _zlozene(18, ['blur(6px)'], animirana=True),
    'anim-18-mesano': lambda: _zlozene(18, MESANO, animirana=True),
}
# Linearnost zlozenih plasti: cas CPU na okvir pri n = 6 .. 36 (animirana vsebina, da se okvir vedno znova narise).
for _n in (6, 12, 18, 24, 30, 36):
    MERITVE['lin-%d-blur0' % _n] = (lambda n: lambda: _zlozene(n, ['blur(0)'], animirana=True))(_n)
    MERITVE['lin-%d-blur6' % _n] = (lambda n: lambda: _zlozene(n, ['blur(6px)'], animirana=True))(_n)

# Strani za primerjavo pikslov (brez animacije).
POSNETKI = {
    'p1-blur0': lambda: _zlozene(8, ['blur(0)']),
    'p2-blur3': lambda: _zlozene(8, ['blur(3px)']),
    'p3-blur8': lambda: _zlozene(8, ['blur(8px)']),
    'p4-veriga': lambda: _zlozene(6, ['blur(4px) brightness(1.2) saturate(2)', 'grayscale(1) blur(1px)', 'contrast(1.5) blur(5px)']),
    'p5-rotacija': lambda: _zlozene(6, ['blur(5px)'], dodatek='transform: rotate(12deg);'),
    'p6-zaobljeno': lambda: _zlozene(6, ['blur(6px)'], dodatek='border-radius: 28px;'),
    'p7-prosojnost': lambda: _zlozene(6, ['blur(2px)', 'blur(7px)'], dodatek='opacity: 0.6;'),
    'p8-obrezano': lambda: _stran('.okvir { position: absolute; left: 180px; top: 120px; width: 500px; height: 260px; overflow: hidden; }'
                                  '.z { position: absolute; width: 300px; height: 140px; backdrop-filter: blur(7px); }', _vsebina()
                                  + '<div class="okvir">%s</div>' % ''.join('<div class="z" style="left:%dpx; top:%dpx"></div>' % (-60 + 70 * i, -40 + 45 * i) for i in range(6))),
    'p9-hue-rotate': lambda: _zlozene(6, ['blur(4px)'], dodatek='filter: hue-rotate(90deg);'),
}
# Spremembe v okvirju na strani p0-spremembe: po vsaki posnetek (ozadje, vrstni red z, polozaj, filter, transformacija).
SPREMEMBE = [
    "document.body.style.background = 'linear-gradient(45deg, #0f2027, #2c5364 50%, #f8b500)'",
    "document.querySelectorAll('.z')[2].style.zIndex = 50",
    "document.querySelectorAll('.z')[4].style.left = '520px'",
    "document.querySelectorAll('.z')[1].style.backdropFilter = 'blur(9px) sepia(1)'",
    "document.querySelectorAll('.z')[3].style.transform = 'rotate(-8deg) scale(1.1)'",
]
POSNETKI['p0-spremembe'] = lambda: _zlozene(8, ['blur(0)', 'blur(4px)', 'blur(6px)'])

ZUNANJE = {'24ur': 'https://www.24ur.com/'}

# Zapise case requestAnimationFrame za vse strani, tudi zunanje.
SKRIPT_OKVIRJEV = """
(function () {
    if (window !== window.top) return;
    window.__okvirji = [];
    function okvir(t) { window.__okvirji.push(t); requestAnimationFrame(okvir); }
    requestAnimationFrame(okvir);
})();
"""


def zapisi_strani(mapa):
    os.makedirs(mapa, exist_ok=True)
    for ime, f in list(MERITVE.items()) + list(POSNETKI.items()):
        with open(os.path.join(mapa, ime + '.html'), 'w') as d:
            d.write(f())


# ---- en proces: pogled in meritev/posnetki --------------------------------------------------------------------------

def _pogled():
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('WebKit2', '4.1')
    from gi.repository import Gtk, WebKit2
    okno = Gtk.Window()
    okno.set_default_size(SIRINA, VISINA)
    okno.move(0, 0)
    ucm = WebKit2.UserContentManager()
    ucm.add_script(WebKit2.UserScript(SKRIPT_OKVIRJEV, WebKit2.UserContentInjectedFrames.TOP_FRAME,
                                      WebKit2.UserScriptInjectionTime.START, None, None))
    pogled = WebKit2.WebView(user_content_manager=ucm)
    pogled.get_settings().set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.ALWAYS)
    okno.add(pogled)
    okno.show_all()
    return Gtk, pogled


def _js(Gtk, pogled, koda, rok=10.0):
    """Izvede JS in vrne rezultat kot niz (ali None)."""
    from gi.repository import GLib
    izid = {}

    def konec(p, rez):
        try:
            v = p.evaluate_javascript_finish(rez)
            izid['v'] = v.to_string() if v is not None and not v.is_undefined() else None
        except GLib.Error as e:
            izid['v'], izid['napaka'] = None, e.message
    pogled.evaluate_javascript(koda, -1, None, None, None, konec)
    _cakaj(Gtk, lambda: 'v' in izid, rok)
    return izid.get('v')


def _cakaj(Gtk, pogoj, rok):
    konec = time.monotonic() + rok
    while time.monotonic() < konec and not pogoj():
        Gtk.main_iteration_do(False) if Gtk.events_pending() else time.sleep(0.005)


def _vrti(Gtk, sekunde):
    _cakaj(Gtk, lambda: False, sekunde)


def _nalozi(Gtk, pogled, url, rok=30.0):
    from gi.repository import WebKit2
    stanje = {'konec': False}
    pogled.connect('load-changed', lambda p, d: stanje.update(konec=True) if d == WebKit2.LoadEvent.FINISHED else None)
    pogled.load_uri(url)
    _cakaj(Gtk, lambda: stanje['konec'], rok)


def proces_meri(url, sekunde):
    """Otrok: nalozi stran in vrti okno meritve; starsev proces meri spletni proces. Na koncu izpise okvirje."""
    Gtk, pogled = _pogled()
    print('ZACETEK', flush=True)
    _nalozi(Gtk, pogled, url, rok=sekunde)
    _vrti(Gtk, max(0.0, sekunde))
    okvirji = _js(Gtk, pogled, 'JSON.stringify(window.__okvirji || [])', rok=5.0)
    print('OKVIRJI ' + (okvirji or 'null'), flush=True)


def proces_posnetki(mapa_strani, izhod):
    import cairo
    Gtk, pogled = _pogled()
    os.makedirs(izhod, exist_ok=True)

    def posnemi(ime):
        _js(Gtk, pogled, 'new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(1))))')
        _vrti(Gtk, 0.7)
        a = pogled.get_allocation()
        povrsina = cairo.ImageSurface(cairo.FORMAT_ARGB32, a.width, a.height)
        pogled.draw(cairo.Context(povrsina))
        povrsina.write_to_png(os.path.join(izhod, ime + '.png'))

    for ime in POSNETKI:
        _nalozi(Gtk, pogled, 'file://' + os.path.join(mapa_strani, ime + '.html'))
        _vrti(Gtk, 1.0)
        posnemi(ime)
        if ime == 'p0-spremembe':
            for i, koda in enumerate(SPREMEMBE, 1):
                _js(Gtk, pogled, koda + '; 1')
                posnemi('%s-%d' % (ime, i))


# ---- starsev proces: zagon otroka in meritev spletnega procesa ------------------------------------------------------

def _otroci(pid):
    """Vsi potomci procesa pid: {pid: ime}."""
    stars = {}
    for d in os.listdir('/proc'):
        if d.isdigit():
            try:
                with open('/proc/%s/stat' % d) as f:
                    s = f.read()
                ime = s[s.index('(') + 1:s.rindex(')')]
                stars[int(d)] = (int(s[s.rindex(')') + 2:].split()[1]), ime)
            except (OSError, ValueError):
                pass
    izid, vrsta = {}, [pid]
    while vrsta:
        p = vrsta.pop()
        for c, (pp, ime) in stars.items():
            if pp == p:
                izid[c] = ime
                vrsta.append(c)
    return izid


def _rss_cpu(pid):
    with open('/proc/%d/status' % pid) as f:
        rss = next(int(v.split()[1]) for v in f if v.startswith('VmRSS:'))
    with open('/proc/%d/stat' % pid) as f:
        polja = f.read().rsplit(')', 1)[1].split()
    return rss * 1024, (int(polja[11]) + int(polja[12])) / os.sysconf('SC_CLK_TCK')


def meri(lib, url, sekunde, poskusov=3):
    """Meritev; ce otrok pade (npr. napaka X ob zagonu), do poskusov krat."""
    for _ in range(poskusov):
        izid, koda = _meri(lib, url, sekunde)
        if koda == 0:
            return izid
    izid['napaka'] = 'otrok je koncal s kodo %s' % koda
    return izid


def _meri(lib, url, sekunde):
    okolje = dict(os.environ, LD_LIBRARY_PATH=os.path.join(lib, 'lib'))
    otrok = subprocess.Popen([sys.executable, '-I', os.path.abspath(__file__), '_otrok-meri', url, str(sekunde)],
                             stdout=subprocess.PIPE, text=True, env=okolje)
    assert otrok.stdout.readline().strip() == 'ZACETEK'
    zacetek = time.monotonic()
    rss_max, cpu, cpu_ustaljeno = 0, {}, None
    while otrok.poll() is None and time.monotonic() - zacetek < sekunde + 0.5:
        for p, ime in _otroci(otrok.pid).items():
            if ime.startswith('WebKitWebProces'):
                try:
                    rss, c = _rss_cpu(p)
                except (OSError, StopIteration):
                    continue
                rss_max, cpu[p] = max(rss_max, rss), c
        if cpu_ustaljeno is None and time.monotonic() - zacetek >= USTALITEV:
            cpu_ustaljeno, cas_ustaljeno = sum(cpu.values()), time.monotonic()
        if time.monotonic() - zacetek < sekunde:
            konec_meritve = time.monotonic()
        time.sleep(0.2)
    vrstica = otrok.stdout.readline()
    while vrstica and not vrstica.startswith('OKVIRJI '):
        vrstica = otrok.stdout.readline()
    otrok.wait(timeout=30) if otrok.poll() is None else None
    # Spletni proces, ki obtici v okvirju (brez popravka), ne konca sam takoj in bi obremenil naslednjo meritev.
    for p in cpu:
        try:
            with open('/proc/%d/comm' % p) as f:
                if f.read().startswith('WebKitWebProces'):
                    os.kill(p, 9)
        except OSError:
            pass
    time.sleep(1)
    casi = json.loads(vrstica[8:]) if vrstica.startswith('OKVIRJI ') else None
    izid = {'rss_mb': round(rss_max / 2**20), 'cpu_s': round(sum(cpu.values()), 2)}
    # Ustaljeni del: zadnjih (sekunde - USTALITEV) s casovnice strani, ki se konca hkrati z meritvijo.
    okno_ms = 1000 * (sekunde - USTALITEV)
    casi = [t for t in (casi or []) if t >= casi[-1] - okno_ms] if casi else []
    intervali = [b - a for a, b in zip(casi, casi[1:])]
    izid['okvirjev'] = len(intervali)
    izid['interval_mediana_ms'] = round(statistics.median(intervali), 1) if intervali else None
    # Ce v ustaljenem delu ni dveh okvirjev, je interval vsaj okno meritve (okvir se ni koncal).
    izid['interval_max_ms'] = round(max(intervali), 1) if intervali else '>%d' % okno_ms
    if cpu_ustaljeno is not None:
        cpu_okno = sum(cpu.values()) - cpu_ustaljeno
        izid['cpu_ustaljeno_pct'] = round(100 * cpu_okno / max(0.001, konec_meritve - cas_ustaljeno))
        if intervali:
            izid['cpu_ms_na_okvir'] = round(1000 * cpu_okno / len(intervali), 2)
    return izid, otrok.returncode


def primerjaj(a, b):
    import cairo
    izid = {}
    for ime in sorted(f for f in os.listdir(a) if f.endswith('.png')):
        if not os.path.exists(os.path.join(b, ime)):
            izid[ime[:-4]] = 'manjka'
            continue
        pa, pb = (cairo.ImageSurface.create_from_png(os.path.join(m, ime)) for m in (a, b))
        if (pa.get_width(), pa.get_height()) != (pb.get_width(), pb.get_height()):
            izid[ime[:-4]] = 'velikost'
            continue
        da, db = bytes(pa.get_data()), bytes(pb.get_data())
        razlicni = [i for i in range(0, len(da), 4) if da[i:i + 4] != db[i:i + 4]]
        izid[ime[:-4]] = [len(razlicni), max((abs(da[i + k] - db[i + k]) for i in razlicni for k in range(4)), default=0)]
    return izid   # {stran: [razlicnih pikslov, najvecja razlika kanala]}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sp = ap.add_subparsers(dest='ukaz', required=True)
    sp.add_parser('strani').add_argument('mapa')
    m = sp.add_parser('meri')
    m.add_argument('--lib', required=True)
    m.add_argument('--stran', required=True)
    m.add_argument('--sekunde', type=float, default=10)
    p = sp.add_parser('posnetki')
    p.add_argument('--lib', required=True)
    p.add_argument('--izhod', required=True)
    r = sp.add_parser('primerjaj')
    r.add_argument('a')
    r.add_argument('b')
    v = sp.add_parser('vse')
    v.add_argument('--lib', action='append', required=True, help='IME=NAMESTITEV')
    v.add_argument('--izhod', required=True)
    v.add_argument('--strani', nargs='*', help='samo te strani za meritve')
    v.add_argument('--sekunde', type=float, default=10)
    o = sp.add_parser('_otrok-meri')
    o.add_argument('url')
    o.add_argument('sekunde', type=float)
    o = sp.add_parser('_otrok-posnetki')
    o.add_argument('strani')
    o.add_argument('izhod')
    a = ap.parse_args()

    def url_strani(ime, mapa):
        return ZUNANJE[ime] if ime in ZUNANJE else 'file://' + os.path.join(mapa, ime + '.html')

    if a.ukaz == 'strani':
        zapisi_strani(a.mapa)
    elif a.ukaz == '_otrok-meri':
        proces_meri(a.url, a.sekunde)
    elif a.ukaz == '_otrok-posnetki':
        proces_posnetki(a.strani, a.izhod)
    elif a.ukaz == 'meri':
        mapa = tempfile.mkdtemp(prefix='backdrop-strani-')
        zapisi_strani(mapa)
        print(json.dumps(meri(a.lib, url_strani(a.stran, mapa), a.sekunde)))
    elif a.ukaz == 'posnetki':
        mapa = tempfile.mkdtemp(prefix='backdrop-strani-')
        zapisi_strani(mapa)
        subprocess.run([sys.executable, '-I', os.path.abspath(__file__), '_otrok-posnetki', mapa, a.izhod],
                       env=dict(os.environ, LD_LIBRARY_PATH=os.path.join(a.lib, 'lib')), check=True)
    elif a.ukaz == 'primerjaj':
        print(json.dumps(primerjaj(a.a, a.b), indent=1))
    elif a.ukaz == 'vse':
        mapa = os.path.join(a.izhod, 'strani')
        zapisi_strani(mapa)
        razlicice = dict(x.split('=', 1) for x in a.lib)
        izid = {'meritve': {}, 'piksli': {}}
        for ime in (a.strani or list(MERITVE) + list(ZUNANJE)):
            sekunde = 16 if ime in ZUNANJE else a.sekunde
            for r, lib in razlicice.items():
                izid['meritve'].setdefault(ime, {})[r] = meri(lib, url_strani(ime, mapa), sekunde)
                print(ime, r, json.dumps(izid['meritve'][ime][r]), flush=True)
        for r, lib in razlicice.items():
            subprocess.run([sys.executable, '-I', os.path.abspath(__file__), '_otrok-posnetki', mapa, os.path.join(a.izhod, 'png-' + r)],
                           env=dict(os.environ, LD_LIBRARY_PATH=os.path.join(lib, 'lib')), check=True)
        imena = list(razlicice)
        for r in imena[1:]:
            izid['piksli']['%s/%s' % (imena[0], r)] = primerjaj(os.path.join(a.izhod, 'png-' + imena[0]), os.path.join(a.izhod, 'png-' + r))
        with open(os.path.join(a.izhod, 'izid.json'), 'w') as f:
            json.dump(izid, f, indent=1)
        print(json.dumps(izid['piksli'], indent=1))


if __name__ == '__main__':
    main()
