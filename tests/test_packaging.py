import os
import re
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest
import time
from unittest.mock import patch
from core import default_browser

ROOT=Path(__file__).resolve().parents[1]


# Moduli, ki so samo interni poskus in jih uradni paket namerno nima (uvoz je neobvezen).
NAMERNO_IZPUSCENI={'os_jbl'}

class PackagingTests(unittest.TestCase):
    def test_check_version_preveri_tudi_safeer_os(self):
        """packaging/check_version.py: najnovejsa izdaja v metainfo Safeer OS = VERSION_OS (pregled 14. 10. 2026)."""
        with tempfile.TemporaryDirectory() as d:
            koren = Path(d)
            for rel in ('packaging/check_version.py','packaging/VERSION','packaging/VERSION_OS','packaging/VERSION_CONTROL',
                        'README.md','PACKAGING.md','io.github.memelandfaner.SafeerBrowser.metainfo.xml',
                        'io.github.memelandfaner.SafeerOS.metainfo.xml'):
                (koren/rel).parent.mkdir(parents=True,exist_ok=True)
                shutil.copy(ROOT/rel,koren/rel)
            ukaz=['python3',str(koren/'packaging/check_version.py')]
            okolje={k:v for k,v in os.environ.items() if not k.startswith('GITHUB_REF')}
            self.assertEqual(subprocess.run(ukaz,capture_output=True,env=okolje).returncode,0)
            (koren/'packaging/VERSION_OS').write_text('9.9.9\n')
            r=subprocess.run(ukaz,capture_output=True,text=True,env=okolje)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('VERSION_OS',r.stderr)

    def test_control_payload_can_actually_start(self):
        """Namesceni Safeer Control mora biti uvozljiv brez izvorne mape.

        Tovor je dolgo nosil rocno pisan seznam modulov in trije so manjkali (link_programi,
        link_vnos, link_zaslon): iz izvorne mape je vse delovalo, namesceni paket pa je ob zagonu
        padel z ImportError. Ta test namesti tovor in ga uvozi tako, kot ga uvozi zaganjalnik -
        z izvorno mapo zunaj poti.
        """
        import sys
        with tempfile.TemporaryDirectory() as directory:
            prefix=Path(directory)/'usr'
            subprocess.run(['bash',str(ROOT/'packaging/install_control_payload.sh'),str(prefix)],check=True)
            lib=prefix/'lib/safeer-control'
            environment={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
            code=f"import sys; sys.path.insert(0, {str(lib)!r}); import safeer_control; print(safeer_control.APP_ID)"
            result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,
                                  cwd=tempfile.gettempdir(),env=environment)
            self.assertEqual(result.returncode,0,result.stderr[-800:])
            self.assertIn('SafeerControl',result.stdout)
            self.assertTrue((lib/'assets/link/link.js').stat().st_mode & 0o004)

    def test_os_payload_can_actually_start(self):
        """Namesceni Safeer OS (Linux) mora biti uvozljiv brez izvorne mape - isti nauk kot pri Controlu:
        seznam modulov v install_os_payload.sh je rocen, zato ga ta test preveri z uvozom."""
        import sys
        with tempfile.TemporaryDirectory() as directory:
            prefix=Path(directory)/'usr'
            subprocess.run(['bash',str(ROOT/'packaging/install_os_payload.sh'),str(prefix)],check=True)
            lib=prefix/'lib/safeer-os'
            environment={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
            code=f"import sys; sys.path.insert(0, {str(lib)!r}); import safeer_os; from core import link_hub, link_seja, link_krog, link_programi, threat_intel; print(safeer_os.APP_ID, safeer_os.RAZLICICA)"
            result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,
                                  cwd=tempfile.gettempdir(),env=environment)
            self.assertEqual(result.returncode,0,result.stderr[-800:])
            self.assertIn('SafeerOS',result.stdout)
            self.assertIn((ROOT/'packaging/VERSION_OS').read_text().strip(),result.stdout)
            subprocess.run(['desktop-file-validate',str(prefix/'share/applications/safeer-os.desktop')],check=True)
            self.assertTrue((lib/'assets/os/index.html').exists())
            self.assertTrue((lib/'assets/os/index.html').stat().st_mode & 0o004)

    def test_payloads_ship_every_lazily_imported_core_module(self):
        """Tudi leni uvozi (``from core import x`` v funkciji) morajo biti v tovoru.

        link_krog uvozi link_kripto sele ob podpisu: namesceni Control se je zagnal, a se ni mogel
        vpisati v krog zaupanja, zato mu hub ni poslal seznama naprav (prazen seznam na Linuxu).
        """
        vzorec=re.compile(r'^\s*from core import ([\w, ]+)|^\s*from core\.(\w+) import|^\s*import core\.(\w+)',re.M)
        for skripta,mapa in (('install_control_payload.sh','safeer-control'),('install_os_payload.sh','safeer-os')):
            with self.subTest(skripta=skripta), tempfile.TemporaryDirectory() as directory:
                prefix=Path(directory)/'usr'
                subprocess.run(['bash',str(ROOT/'packaging'/skripta),str(prefix)],check=True)
                lib=prefix/'lib'/mapa
                manjka=set()
                for datoteka in [*lib.glob('*.py'),*(lib/'core').glob('*.py')]:
                    for m in vzorec.finditer(datoteka.read_text(encoding='utf-8')):
                        imena=[i.strip() for i in (m.group(1) or '').split(',') if i.strip()]+[g for g in m.group(2,3) if g]
                        for ime in imena:
                            if ime in NAMERNO_IZPUSCENI:
                                continue
                            if (ROOT/'core'/f'{ime}.py').exists() and not (lib/'core'/f'{ime}.py').exists():
                                manjka.add(f'{datoteka.name} -> {ime}')
                self.assertFalse(manjka,sorted(manjka))
                # Interni poskusi (preklop vhoda JBL) ne smejo v uradni paket.
                for ime in NAMERNO_IZPUSCENI:
                    self.assertFalse((lib/'core'/f'{ime}.py').exists(),ime)

    def test_xdg_config_and_ipc_use_same_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.check_output(['/usr/bin/python3','-c','from core.config import CONFIG_DIR; print(CONFIG_DIR)'],cwd=ROOT,env={**os.environ,'XDG_CONFIG_HOME':directory},text=True).strip()
            self.assertEqual(result,str(Path(directory)/'safeer-mint'))

    def test_sandbox_registration_does_not_write_host_defaults(self):
        with patch.dict(os.environ,{'FLATPAK_ID':'io.github.memelandfaner.SafeerBrowser'}), patch.object(default_browser,'ensure_desktop_entry') as create:
            success,errors=default_browser.set_default_browser(str(ROOT))
            self.assertFalse(success)
            self.assertTrue(errors)
            create.assert_not_called()

    def test_shared_launcher_is_relocatable_and_preserves_arguments(self):
        # Brskalnik v paketih je GTK4 (safeer_brskalnik.py); GTK3 je umaknjen 18. 10. 2026.
        vstop='safeer_brskalnik.py'
        with tempfile.TemporaryDirectory(prefix='safeer package ') as directory:
            prefix=Path(directory)/'usr'
            subprocess.run(['bash',str(ROOT/'packaging/install_payload.sh'),str(prefix)],check=True)
            fake=Path(directory)/'python'
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            fake.chmod(0o755)
            output=subprocess.check_output([str(prefix/'bin/safeer-browser'),'https://example.com/a b'],env={**os.environ,'PYTHON':str(fake)},text=True).splitlines()
            # -s: uporabnikov site-packages ne vpliva (pomocnik, naloga 2-4, 20. 10. 2026).
            self.assertEqual(output,['-s',str(prefix/'lib/safeer-browser'/vstop),'https://example.com/a b'])
            subprocess.run(['desktop-file-validate',str(prefix/'share/applications/safeer-browser.desktop')],check=True)

    def test_browser_payload_can_actually_start(self):
        """Namesceni GTK4 brskalnik se zazene brez izvorne mape: --version prek zaganjalnika (razlicica iz
        packaging/VERSION v tovoru) in uvoz modulov, ki jih Splet nalozi lenobno (zgodovina, uvoz zavihkov, Safeer DRM)."""
        import sys
        with tempfile.TemporaryDirectory() as directory:
            prefix=Path(directory)/'usr'
            subprocess.run(['bash',str(ROOT/'packaging/install_payload.sh'),str(prefix)],check=True)
            lib=prefix/'lib/safeer-browser'
            environment={k:v for k,v in os.environ.items() if k != 'PYTHONPATH'}
            verzija=(ROOT/'packaging/VERSION').read_text().strip()
            result=subprocess.run([str(prefix/'bin/safeer'),'--version'],capture_output=True,text=True,
                                  cwd=tempfile.gettempdir(),env={**environment,'PYTHON':sys.executable})
            self.assertEqual(result.returncode,0,result.stderr[-800:])
            self.assertEqual(result.stdout.strip(),'Safeer Browser '+verzija)
            code=(f"import sys; sys.path.insert(0, {str(lib)!r}); import safeer_brskalnik; "
                  "from core import os_splet, safeer_drm, zgodovina, uvoz_zavihkov, bookmarks_importer, splet_prenosi; "
                  "print(safeer_brskalnik.APP_ID, safeer_drm.vgrajena_mapa())")
            result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,
                                  cwd=tempfile.gettempdir(),env=environment)
            self.assertEqual(result.returncode,0,result.stderr[-800:])
            self.assertIn('io.github.memelandfaner.SafeerBrowser',result.stdout)
            # Safeer DRM: izvor logike (main.js) je v tovoru, Safeer DRM sam pa v <tovor>/safeer-drm, ce je gradnja podala
            # SAFEER_DRM_TOVOR (tests/test_safeer_drm_paket.py); med delovanjem se nic ne prenese.
            self.assertTrue((lib/'assets/safeer_drm/main.js').is_file())
            self.assertIn(str(lib/'safeer-drm'),result.stdout)
            self.assertTrue((lib/'ui/splet.html').is_file())
            for ime in NAMERNO_IZPUSCENI:
                self.assertFalse((lib/'core'/f'{ime}.py').exists(),ime)

    def test_browser_desktop_entry(self):
        """Vnos v meniju: privzeti brskalnik za http/https in HTML, okno GTK4 (ID programa) pripada vnosu, brez
        dejanja »Novo okno«, ki ga GTK4 brskalnik z enim primerkom ne zna (samo dvigne obstojece okno)."""
        import configparser
        vnos=configparser.ConfigParser(interpolation=None)
        vnos.optionxform=str
        vnos.read(ROOT/'packaging/safeer-browser.desktop',encoding='utf-8')
        d=vnos['Desktop Entry']
        tipi=set(d['MimeType'].strip(';').split(';'))
        self.assertTrue({'text/html','x-scheme-handler/http','x-scheme-handler/https'}<=tipi,tipi)
        app_id=re.search(r'^APP_ID = "([^"]+)"',(ROOT/'safeer_brskalnik.py').read_text(),re.M).group(1)
        self.assertEqual(d['StartupWMClass'],app_id)
        self.assertEqual(d['Exec'],'safeer %U')
        self.assertNotIn('Actions',d)
        subprocess.run(['desktop-file-validate',str(ROOT/'packaging/safeer-browser.desktop')],check=True)

    def test_browser_launcher_in_flatpak_has_no_host_tools(self):
        """Od 1.0.127 brskalnik v Flatpaku nima ovojev gostitelja; Safeer OS (lupina) jih obdrzi. Skupna mapa nastavitev s
        paketom .deb gre prek SAFEER_MINT_CONFIG_DIR (safeer_brskalnik.py), ne prek XDG_* v dom."""
        brskalnik=(ROOT/'packaging/safeer-launcher').read_text()
        os_=(ROOT/'packaging/safeer-os-launcher').read_text()
        for vrstica in ('if [ -n "${FLATPAK_ID:-}" ] && [ -d /app/host-bin ]; then','export PATH="/app/host-bin:$PATH"',
                        'export XDG_CONFIG_HOME="$HOME/.config" XDG_DATA_HOME="$HOME/.local/share" XDG_CACHE_HOME="$HOME/.cache"'):
            self.assertIn(vrstica,os_)
            self.assertNotIn(vrstica,brskalnik)
        vstop=(ROOT/'safeer_brskalnik.py').read_text()
        self.assertNotIn('/app/host-bin:',vstop)
        self.assertIn('os.environ.setdefault("SAFEER_MINT_CONFIG_DIR", _skupna)',vstop)
        # Obseg systemd ostane (odziven racunalnik, ko stran porabi prevec), Flatpak paketa .deb pa ga ne potrebuje.
        self.assertLess(brskalnik.index('exec flatpak run "$FP_ID"'),brskalnik.index('systemd-run --user --scope'))

    def test_browser_flatpak_ships_our_webkit_and_safeer_drm(self):
        """Flatpak brskalnika ima nas WebKitGTK 6.0 iz iste datoteke modula kot Safeer OS (brez kopije gradnje) in zypak
        za Safeer DRM v peskovniku (od 1.0.127 brez zagona na gostitelju; tests/test_peskovnik_brskalnika.py)."""
        brskalnik=(ROOT/'io.github.memelandfaner.SafeerBrowser.yml').read_text()
        os_=(ROOT/'io.github.memelandfaner.SafeerOS.yml').read_text()
        moduli=('  - packaging/webkit/webkitgtk6-safeer.yml\n','  - packaging/webkit/webkitgtk6-safeer-typelib.yml\n')
        for modul in moduli:
            self.assertIn(modul,brskalnik)
            self.assertIn(modul,os_)
        # WebKit je prvi modul (predpomnilnik flatpak-builderja), typelib takoj za njim.
        seznam=re.findall(r'^  - (\S.*)$',brskalnik.split('\nmodules:\n',1)[1],re.M)
        self.assertEqual(seznam[:2],[m.strip()[2:] for m in moduli])
        self.assertNotIn('webkitgtk.org/releases',brskalnik)
        self.assertRegex(brskalnik,r"(?m)^runtime: org\.gnome\.Platform\nruntime-version: '50'$")
        self.assertIn("runtime-version: '50'",os_)
        self.assertIn('bash packaging/install_payload.sh /app io.github.memelandfaner.SafeerBrowser',brskalnik)
        self.assertNotIn('flatpak_host_wrappers.sh',brskalnik)
        self.assertNotIn('/app/host-bin',brskalnik)
        dovoljenja=set(re.findall(r'^  - (--\S+)$',brskalnik,re.M))
        drm=(ROOT/'core/safeer_drm.py').read_text()
        self.assertIn('ZYPAK = "/app/bin/zypak-wrapper"',drm)
        self.assertIn('  - name: zypak\n',brskalnik)
        self.assertTrue({'--socket=wayland','--socket=fallback-x11','--share=network','--socket=pulseaudio',
                         '--device=dri','--filesystem=xdg-download','--filesystem=xdg-config/safeer-mint:create'}<=dovoljenja,
                        dovoljenja)
        # Safeer OS (lupina namizja) obdrzi dostop do gostitelja.
        self.assertIn('--talk-name=org.freedesktop.Flatpak',os_)

    def test_flatpak_libsoup_s_popravki_za_webkitom(self):
        """org.gnome.Platform//50 ima libsoup 3.6.6 (CVE-2026-5119, CVE-2026-3099, CVE-2026-66337 …): oba Flatpaka
        vzameta libsoup >= 3.8.0 iz packaging/libsoup, takoj za WebKitom (predpomnilnik WebKita ostane veljaven)."""
        modul=(ROOT/'packaging/libsoup/libsoup3-safeer.yml').read_text()
        razlicica=re.search(r'libsoup-(\d+)\.(\d+)\.(\d+)\.tar\.xz',modul).groups()
        self.assertGreaterEqual(tuple(map(int,razlicica)),(3,8,0))
        self.assertRegex(modul,r'(?m)^    sha256: [0-9a-f]{64}$')
        self.assertIn('https://download.gnome.org/sources/libsoup/%s.%s/'%razlicica[:2],modul)
        # Brez --libdir=lib gre knjiznica v /app/lib/x86_64-linux-gnu in nalozi se 3.6.6 iz runtime-a (CI #813).
        self.assertIn('  - --libdir=lib',modul)
        for manifest in ('io.github.memelandfaner.SafeerOS.yml','io.github.memelandfaner.SafeerBrowser.yml'):
            with self.subTest(manifest=manifest):
                seznam=re.findall(r'^  - (\S.*)$',(ROOT/manifest).read_text().split('\nmodules:\n',1)[1],re.M)
                self.assertEqual(seznam[:3],['packaging/webkit/webkitgtk6-safeer.yml',
                                             'packaging/webkit/webkitgtk6-safeer-typelib.yml',
                                             'packaging/libsoup/libsoup3-safeer.yml'])

    def test_webkit_s_clangom_in_thinlto(self):
        """WebKitGTK 2.53.1+ podpira LTO/PGO samo s Clangom (Speedometer 3.1 na testnem PC z GCC -O2: 8.2, Firefox 12.8):
        modul ga gradi s Clangom 22 iz razsiritve SDK, ki jo oba manifesta in CI namestita (veja 25.08 = GNOME 50)."""
        modul=(ROOT/'packaging/webkit/webkitgtk6-safeer.yml').read_text()
        for niz in ('  append-path: /usr/lib/sdk/llvm22/bin\n','    CC: clang\n','    CXX: clang++\n',
                    '  - -DLTO_MODE=thin\n','  - -DCMAKE_AR=/usr/lib/sdk/llvm22/bin/llvm-ar\n'):
            self.assertIn(niz,modul)
        for manifest in ('io.github.memelandfaner.SafeerOS.yml','io.github.memelandfaner.SafeerBrowser.yml'):
            with self.subTest(manifest=manifest):
                self.assertIn('\nsdk-extensions:\n  - org.freedesktop.Sdk.Extension.llvm22\n',(ROOT/manifest).read_text())
        wf=(ROOT/'.github/workflows/linux-packages.yml').read_text()
        # Posla izdaje (flatpak, flatpak-brskalnik) in ucni tek PGO; posel kljuca profila namesti samo razsiritev llvm22.
        self.assertEqual(wf.count('org.gnome.Sdk//50 org.freedesktop.Sdk.Extension.llvm22//25.08'),3)
        self.assertEqual(wf.count('flatpak install --user --noninteractive flathub org.freedesktop.Sdk.Extension.llvm22//25.08\n'),1)

    @staticmethod
    def _pgo():
        import importlib.util
        spec=importlib.util.spec_from_file_location('pgo',ROOT/'packaging/webkit/pgo.py')
        pgo=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pgo)
        return pgo

    def test_webkit_pgo_razlicici_manifesta(self):
        """PGO (packaging/webkit/pgo.py): instrumentirana razlicica in razlicica s profilom imata isti izvor, popravke in
        ime modula (pot gradnje /run/build/<ime> je v imenih lokalnih funkcij profila) kot gradnja brez PGO; profil
        zdruzi llvm-profdata iz iste razsiritve pred gradnjo WebKita."""
        pgo=self._pgo()
        izdaja=(ROOT/'packaging/webkit/webkitgtk6-safeer.yml').read_text()
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            (d/'profraw').mkdir()
            with self.assertRaises(SystemExit):
                pgo.manifest('uporaba',d/'profraw',d/'izhod')
            (d/'profraw'/'1-a.profraw').write_bytes(b'x')
            for nacin,opcije in (('ucenje',['-DENABLE_LLVM_PROFILE_GENERATION=ON']),
                                 ('uporaba',['-DUSE_PGO_PROFILE=ON','-DPGO_PROFILE_PATH='+pgo.PROFDATA])):
                with self.subTest(nacin=nacin):
                    manifest=pgo.manifest(nacin,d/'profraw',d/nacin).read_text()
                    modul=(d/nacin/'webkitgtk6-safeer-pgo.yml').read_text()
                    for opcija in opcije:
                        self.assertIn('  - %s\n'%opcija,modul)
                    self.assertEqual(modul.replace(''.join('  - %s\n'%o for o in opcije),'')
                                     .replace('name: %s\n'%pgo.MODUL_IME,'name: webkitgtk6-safeer\n')
                                     .replace(str(ROOT/'packaging/webkit')+'/',''),izdaja)
                    for pot in re.findall(r'(?m)^    path: (\S+)$',modul):
                        self.assertTrue(Path(pot).is_file(),pot)
                    seznam=re.findall(r'^  - (\S.*)$',manifest.split('\nmodules:\n',1)[1],re.M)
                    pricakovano=[str(d/nacin/'webkitgtk6-safeer-pgo.yml'),str(ROOT/'packaging/webkit/webkitgtk6-safeer-typelib.yml')]
                    if nacin=='uporaba':
                        pricakovano.insert(0,str(d/nacin/'webkitgtk6-safeer-pgo-profil.yml'))
                        profil=(d/nacin/'webkitgtk6-safeer-pgo-profil.yml').read_text()
                        self.assertIn('llvm-profdata merge --output=%s *.profraw'%pgo.PROFDATA,profil)
                        # type: file s sha256, ne type: dir (flatpak-builder dir vedno gradi znova; WebKit je za tem modulom).
                        self.assertIn('  - type: file\n    path: %s\n    sha256: %s\n'%(d/'profraw'/'1-a.profraw',
                                      '2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881'),profil)
                        self.assertNotIn('  - type: dir\n',profil)
                    self.assertEqual(seznam[:len(pricakovano)],pricakovano)
                    self.assertIn('        path: %s\n'%ROOT,manifest)
        self.assertEqual(pgo.MODUL_IME,'webkitgtk6-safeer-pgo')
        self.assertIn('startAutomatically&iterationCount=',pgo.TRENING_POIZVEDBA)
        self.assertEqual(pgo.SPEEDOMETER[2],'1386415be8fef2f6b6bbdbe1828872471c5d802a')

    def test_webkit_pgo_manifest_safeer_os_in_relativne_poti(self):
        """Manifest s profilom tudi za Safeer OS; v razlicici (build/pgo/<ID>) so vse poti absolutne in obstajajo - tudi
        popravek zypaka (packaging/zypak), ki ga stari pgo.py ni prestavil (gradnja bi padla)."""
        pgo=self._pgo()
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            (d/'profraw').mkdir()
            (d/'profraw'/'1-a.profraw').write_bytes(b'x')
            for ime in ('io.github.memelandfaner.SafeerOS.yml','io.github.memelandfaner.SafeerBrowser.yml'):
                with self.subTest(manifest=ime):
                    pot=pgo.manifest('uporaba',d/'profraw',d/ime,ROOT/ime)
                    besedilo=pot.read_text()
                    seznam=re.findall(r'^  - (\S.*)$',besedilo.split('\nmodules:\n',1)[1],re.M)
                    self.assertEqual(seznam[:4],[str(d/ime/'webkitgtk6-safeer-pgo-profil.yml'),str(d/ime/'webkitgtk6-safeer-pgo.yml'),
                                                 str(ROOT/'packaging/webkit/webkitgtk6-safeer-typelib.yml'),
                                                 str(ROOT/'packaging/libsoup/libsoup3-safeer.yml')])
                    poti=re.findall(r'(?m)^\s*(?:- )?path: (\S+)$',besedilo)
                    self.assertIn(str(ROOT),poti)
                    for p in poti+[s for s in seznam if s.endswith('.yml')]:
                        # build/rqbit je artefakt posla rqbit-deb (lokalno ga morda ni); pot mora biti absolutna.
                        self.assertTrue(os.path.isabs(p) and (os.path.exists(p) or p==str(ROOT/'build/rqbit')),p)
                    if 'SafeerOS' in ime:
                        self.assertIn(str(ROOT/'build/rqbit'),poti)
                    if 'Browser' in ime:
                        self.assertIn(str(ROOT/'packaging/zypak/zypak-expose-paths.patch'),poti)
                    # Izvirni manifest ostane nespremenjen (lokalna gradnja brez PGO).
                    self.assertIn('  - packaging/webkit/webkitgtk6-safeer.yml\n',(ROOT/ime).read_text())
            profil=(d/'io.github.memelandfaner.SafeerOS.yml'/'webkitgtk6-safeer-pgo-profil.yml').read_text()
            self.assertIn('> %s'%pgo.POVZETEK,profil)
            self.assertIn("grep -o '/run/build/[^/;:]*'",profil)

    def test_webkit_pgo_kljuc_profila(self):
        """Kljuc profila se spremeni z izvorom/popravki WebKita, ucnim tekom in razlicico LLVM - ne pa s kodo Safeerja,
        libsoup ali drugimi moduli (ucni tek ~2 h tece samo, ko je res potreben)."""
        pgo=self._pgo()
        osnova=pgo.kljuc('22.1.8')
        self.assertRegex(osnova,r'^[0-9a-f]{20}-llvm22\.1\.8$')
        self.assertEqual(pgo.kljuc('22.1.8'),osnova)
        self.assertNotEqual(pgo.kljuc('22.1.9'),osnova)
        with self.assertRaises(SystemExit):
            pgo.kljuc('22.1.8; rm -rf /')
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            shutil.copytree(ROOT/'packaging/webkit',d/'webkit')
            with patch.object(pgo,'WEBKIT',d/'webkit'),patch.object(pgo,'MODUL',d/'webkit/webkitgtk6-safeer.yml'),\
                 patch.object(pgo,'TRENING',d/'webkit/pgo_trening.py'):
                self.assertEqual(pgo.kljuc('22.1.8'),osnova)
                self.assertEqual([p.name for p in pgo.popravki()],['skia-backdrop-2n.patch','gst-mse-suspend.patch'])
                for datoteka in ('gst-mse-suspend.patch','webkitgtk6-safeer.yml','pgo_trening.py'):
                    with self.subTest(datoteka=datoteka):
                        izvirnik=(d/'webkit'/datoteka).read_bytes()
                        (d/'webkit'/datoteka).write_bytes(izvirnik+b'\n')
                        self.assertNotEqual(pgo.kljuc('22.1.8'),osnova)
                        (d/'webkit'/datoteka).write_bytes(izvirnik)
                with patch.object(pgo,'TRENING_POIZVEDBA','?startAutomatically&iterationCount=10'):
                    self.assertNotEqual(pgo.kljuc('22.1.8'),osnova)

    def test_webkit_pgo_razlicica_llvm(self):
        pgo=self._pgo()
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            with self.assertRaises(SystemExit):
                pgo.llvm_razlicica(d)
            (d/'lib').mkdir()
            (d/'lib/libLLVM.so.22.1').write_bytes(b'')
            self.assertEqual(pgo.llvm_razlicica(d),'22.1')
            (d/'lib/cmake/llvm').mkdir(parents=True)
            (d/'lib/cmake/llvm/LLVMConfig.cmake').write_text('set(LLVM_VERSION_MAJOR 22)\nset(LLVM_PACKAGE_VERSION 22.1.8)\n')
            self.assertEqual(pgo.llvm_razlicica(d),'22.1.8')

    def test_flatpaka_izdaje_z_webkitom_s_pgo(self):
        """Lastnik 15. 10. 2026 ("DA"): oba Flatpaka izdaje (iste datoteke kot prej) imata WebKitGTK s PGO. Ucni tek
        samo, ko profila s kljucem ni; brez profila posla Flatpak ne tecata (nikoli tiho brez PGO) in izdaje ni."""
        wf=(ROOT/'.github/workflows/linux-packages.yml').read_text()
        posli=dict(re.findall(r'(?ms)^  ([a-z0-9-]+):\n(.*?)(?=^  [a-z0-9-]+:\n|\Z)',wf.split('\njobs:\n',1)[1]))
        self.assertNotIn('webkit-pgo-brskalnik',posli)
        profil=posli['webkit-pgo-profil']
        self.assertIn('python3 packaging/webkit/pgo.py kljuc',profil)
        self.assertIn('actions/artifacts?name=$IME',profil)
        self.assertIn('IME="webkit-pgo-profraw-$KLJUC"',profil)
        ucenje=posli['webkit-pgo-ucenje']
        self.assertIn("    needs: webkit-pgo-profil\n    if: needs.webkit-pgo-profil.outputs.run_id == ''\n",ucenje)
        self.assertIn('name: webkit-pgo-profraw-${{ needs.webkit-pgo-profil.outputs.kljuc }}',ucenje)
        self.assertIn('retention-days: 90',ucenje)
        self.assertIn('python3 packaging/webkit/pgo.py ucenje',ucenje)
        self.assertIn('python3 packaging/webkit/pgo.py speedometer',ucenje)
        pogoj=("    if: ${{ !cancelled() && needs.webkit-pgo-profil.result == 'success' && (needs.webkit-pgo-ucenje.result == "
               "'success' || (needs.webkit-pgo-ucenje.result == 'skipped' && needs.webkit-pgo-profil.outputs.run_id != '')) }}\n")
        for posel,manifest,skripta in (('flatpak','io.github.memelandfaner.SafeerOS.yml','build_os_flatpak.sh'),
                                       ('flatpak-brskalnik','io.github.memelandfaner.SafeerBrowser.yml','build_flatpak.sh')):
            with self.subTest(posel=posel):
                k=posli[posel]
                if posel=='flatpak':
                    # Safeer OS dobi se nas rqbit (posel rqbit-deb): brez njega Flatpaka ne gradimo.
                    self.assertIn('    needs: [webkit-pgo-profil, webkit-pgo-ucenje, rqbit-deb]\n'
                                  +pogoj.replace("!cancelled() && ","!cancelled() && needs.rqbit-deb.result == 'success' && "),k)
                else:
                    self.assertIn('    needs: [webkit-pgo-profil, webkit-pgo-ucenje]\n'+pogoj,k)
                self.assertIn('python3 packaging/webkit/pgo.py uporaba build/pgo/profraw %s'%manifest,k)
                self.assertIn('SAFEER_FLATPAK_MANIFEST: ${{ steps.pgo.outputs.manifest }}',k)
                self.assertIn('bash packaging/%s 2>&1 | tee'%skripta,k)
                self.assertIn('set -o pipefail\n',k)
                self.assertIn('run-id: ${{ needs.webkit-pgo-profil.outputs.run_id || github.run_id }}',k)
                # Isti kljuc profila z namescenim Clangom; predpomnilnik flatpak-builderja s profilom in commitoma SDK/llvm22.
                self.assertIn('[ "$K" = "${{ needs.webkit-pgo-profil.outputs.kljuc }}" ]',k)
                self.assertIn('$(python3 packaging/webkit/pgo.py okolje)',k)
                self.assertIn('key: ${{ steps.pgo.outputs.predpomnilnik }}',k)
                # pgo.py sestavi manifest: njegova sprememba mora dati nov kljuc (sicer se nov predpomnilnik ne shrani).
                self.assertIn("'packaging/webkit/pgo.py', 'packaging/libsoup/**'",k)
                for preverba in ("grep -q '^USE_PGO_PROFILE:BOOL=ON$' \"$G\"","grep -q '^build.ninja -fprofile-use: [1-9]' \"$G\"",
                                 "/run/build/webkitgtk6-safeer-pgo$","grep -q 'clang version 22\\.' \"$G\"",
                                 "grep -q '^LTO_MODE:.*=thin$' \"$G\""):
                    self.assertIn(preverba,k)
                self.assertIn('from gi.repository import Soup, WebKit',k)
        self.assertIn('smoke_brskalnik.py',posli['flatpak-brskalnik'])
        self.assertIn('zypak-wrapper',posli['flatpak-brskalnik'])
        self.assertIn('scit_lab/lab.sh preizkus',posli['flatpak'])
        izdaja=posli['release']
        self.assertIn('ls -l artifacts/flatpak/Safeer-OS-*-x86_64.flatpak artifacts/flatpak-brskalnik/Safeer-Browser-*-x86_64.flatpak',izdaja)
        potrebe=[p.strip() for p in re.search(r'^    needs: \[([^\]]+)\]$',izdaja,re.M).group(1).split(',')]
        self.assertTrue({'flatpak','flatpak-brskalnik'}<=set(potrebe),potrebe)
        # Imena paketov za uporabnike ostanejo.
        for skripta,ime in (('build_os_flatpak.sh','"dist/Safeer-OS-${VERSION}-x86_64.flatpak"'),
                            ('build_flatpak.sh','"dist/Safeer-Browser-${VERSION}-x86_64.flatpak"')):
            besedilo=(ROOT/'packaging'/skripta).read_text()
            self.assertIn(ime,besedilo)
            self.assertIn('MANIFEST="${SAFEER_FLATPAK_MANIFEST:-io.github.memelandfaner.',besedilo)

    def test_debian_maintainer_scripts_are_posix_sh(self):
        for builder in ('build_deb.sh','build_os_deb.sh'):
            with self.subTest(builder=builder):
                self._preveri_skripte(builder)

    # Safeer Control je od 12. 10. 2026 v paketu safeer-os (build_os_deb.sh): ena namestitev, ena posodobitev.
    PROGRAM_DIRS=(('build_deb.sh','/usr/lib/safeer-browser'),('build_os_deb.sh','/usr/lib/safeer-control'),
                  ('build_os_deb.sh','/usr/lib/safeer-os'))

    def test_packages_compile_bytecode_and_clean_it_up(self):
        """Uporabnik v /usr/lib ne more pisati: brez prevoda ob namestitvi Python ob vsakem zagonu znova prevede vse
        module. Kar postinst prevede, mora prerm odstraniti - sicer dpkg po odstranitvi pusti mapo programa (najdeno
        s preizkusom namestitve na Linux Mintu, 4. 10. 2026)."""
        for builder,lib in self.PROGRAM_DIRS:
            with self.subTest(builder=builder):
                scripts=dict(self._skripte(builder))
                self.assertIn('/usr/bin/python3 -m compileall -q %s '%lib,scripts['postinst'])
                self.assertIn('/usr/bin/find %s -depth '%lib,scripts['prerm'])
                # prerm res pobrise bajtno kodo - in samo njo.
                with tempfile.TemporaryDirectory() as directory:
                    mapa=Path(directory)/'program'
                    (mapa/'core/__pycache__').mkdir(parents=True)
                    (mapa/'__pycache__').mkdir()
                    (mapa/'core/a.py').write_text('x=1\n')
                    (mapa/'assets').mkdir()
                    (mapa/'assets/stran.html').write_text('<p>')
                    for pyc in ('core/__pycache__/a.cpython-312.pyc','__pycache__/b.cpython-310.pyc','core/c.pyc'):
                        (mapa/pyc).write_bytes(b'x')
                    self.assertGreaterEqual(scripts['prerm'].count(lib),2)
                    # Samo ta mapa je prava; vse drugo (druge mape programov, safeer-cinnamon --izklopi ob `remove`)
                    # gre v prazno, da preizkus ne spremeni racunalnika, na katerem tece.
                    telo=scripts['prerm'].replace(lib,str(mapa)).replace('/usr/lib/','/nonexistent/lib/')
                    telo=telo.replace('/usr/bin/safeer-cinnamon','/nonexistent/safeer-cinnamon')
                    for action in ('remove','upgrade'):
                        subprocess.run(['sh','-c',telo,'prerm',action],check=True)
                    self.assertEqual(sorted(str(p.relative_to(mapa)) for p in mapa.rglob('*')),
                                     ['assets','assets/stran.html','core','core/a.py'])

    def _skripte(self, builder):
        text=(ROOT/builder).read_text()
        return re.findall(r"cat << 'EOF2?' > \"\$BUILD_ROOT/DEBIAN/(postinst|prerm|postrm)\"\n(.*?)\nEOF2?\n",text,re.S)

    def _preveri_skripte(self, builder):
        scripts=self._skripte(builder)
        self.assertEqual({name for name,_ in scripts},{'postinst','prerm','postrm'})
        shell=shutil.which('dash') or shutil.which('sh')
        for name,body in scripts:
            self.assertTrue(body.startswith('#!/bin/sh\n'),name)
            self.assertNotIn('pipefail',body,name)
            subprocess.run([shell,'-n'],input=body,text=True,check=True)
            for action in ('configure','remove'):
                with tempfile.TemporaryDirectory() as directory:
                    # Run with empty PATH stubs so no host alternatives or caches are touched.
                    result=subprocess.run([shell,'-c',body.replace('/usr/bin/','/nonexistent/').replace('/usr/sbin/','/nonexistent/'),name,action],
                                          env={'PATH':directory},capture_output=True,text=True)
                    self.assertEqual(result.returncode,0,(name,action,result.stderr))


class DebWebkitTests(unittest.TestCase):
    """Paketa .deb z nasim WebKitGTK in libsoup (packaging/webkit-deb, lastnik 15. 10. 2026): isti izvor kot Flatpak,
    od 19. 10. 2026 en skupni paket safeer-webkit z zasebno predpono /usr/lib/safeer-webkit, ki ga zahtevata safeer-os
    in safeer-browser; Python nalozi typelibe iz nje pred `import gi`."""
    WEBKIT_DEB=ROOT/'packaging/webkit-deb'

    def _modul(self, pot):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest('python3-yaml ni namescen')
        r=subprocess.run(['python3',str(self.WEBKIT_DEB/'modul.py'),str(ROOT/pot)],capture_output=True,text=True,check=True)
        import json
        return json.loads(r.stdout)

    def test_deb_gradi_iz_istih_modulov_kot_flatpak(self):
        """En vir resnice: arhiv, SHA-256, popravki in moznosti CMake WebKita ter meson libsoup so iz modulov Flatpak."""
        wk=self._modul('packaging/webkit/webkitgtk6-safeer.yml')
        besedilo=(ROOT/'packaging/webkit/webkitgtk6-safeer.yml').read_text()
        self.assertIn('url: %s\n'%wk['url'],besedilo)
        self.assertIn('sha256: %s\n'%wk['sha256'],besedilo)
        self.assertEqual([Path(p).name for p in wk['popravki']],['skia-backdrop-2n.patch','gst-mse-suspend.patch'])
        self.assertTrue(all(Path(p).is_file() for p in wk['popravki']))
        for moznost in ('-DLTO_MODE=thin','-DUSE_GTK4=ON','-DCMAKE_BUILD_TYPE=Release','-DCMAKE_INSTALL_LIBDIR=lib',
                        '-DCMAKE_AR=/usr/lib/llvm-22/bin/llvm-ar', '-DENABLE_WEBDRIVER=ON'):
            self.assertIn(moznost,wk['moznosti'])
        # Orodja razsiritve Flatpak llvm22 so v paketih apt.llvm.org pod /usr/lib/llvm-22/bin.
        self.assertFalse([m for m in wk['moznosti'] if '/usr/lib/sdk' in m])
        self.assertEqual(wk['okolje'].get('WEBKIT_NINJA_LINK_MAX'),'1')
        soup=self._modul('packaging/libsoup/libsoup3-safeer.yml')
        self.assertRegex(soup['url'],r'/libsoup-3\.(8|9|[1-9][0-9])\.\d+\.tar\.xz$')
        self.assertIn('--libdir=lib',soup['moznosti'])

    def test_zgradi_namesti_v_zasebno_predpono_s_clangom_22(self):
        zgradi=(self.WEBKIT_DEB/'zgradi.sh').read_text()
        for niz in ('packaging/webkit/webkitgtk6-safeer.yml','packaging/libsoup/libsoup3-safeer.yml','LLVM=/usr/lib/llvm-22/bin',
                    '-DCMAKE_INSTALL_PREFIX="$PREDPONA"','-DCMAKE_INSTALL_RPATH="$PREDPONA/lib"',
                    '-DBWRAP_EXECUTABLE=/usr/bin/bwrap','-DDBUS_PROXY_EXECUTABLE=/usr/bin/xdg-dbus-proxy',
                    'packaging/webkit-deb/typelibi.py','gradnja.txt','sha256sum -c'):
            self.assertIn(niz,zgradi)
        # Ena predpona (paket safeer-webkit): druge zgradi.sh zavrne, preden karkoli izbrise.
        self.assertIn('[ "$PREDPONA" = /usr/lib/safeer-webkit ] ||',zgradi)
        self.assertLess(zgradi.index('[ "$PREDPONA" = /usr/lib/safeer-webkit ] ||'),zgradi.index('rm -rf "$PREDPONA"'))
        for staro in ('/usr/lib/safeer-os/webkit','/usr/lib/safeer-browser/webkit'):
            r=subprocess.run(['bash',str(self.WEBKIT_DEB/'zgradi.sh'),staro],capture_output=True,text=True,env={'PATH':'/usr/bin:/bin'})
            self.assertEqual(r.returncode,2,r.stderr)
            self.assertIn('PREDPONA mora biti /usr/lib/safeer-webkit',r.stderr)
        odvisnosti=(self.WEBKIT_DEB/'odvisnosti.sh').read_text()
        self.assertIn('llvm-toolchain-${VERSION_CODENAME:-noble}-22',odvisnosti)
        for paket in ('clang-22','lld-22','libclang-rt-22-dev','libgtk-4-dev','gettext','bubblewrap','xdg-dbus-proxy'):
            self.assertIn(paket,odvisnosti)
        for skripta in ('zgradi.sh','odvisnosti.sh','vgradi.sh','ucni_tek.sh','paket.sh','razlicica_odvisnosti.sh'):
            subprocess.run(['bash','-n',str(self.WEBKIT_DEB/skripta)],check=True)

    def test_bolt_v_gradnji_izdaje(self):
        """BOLT (packaging/webkit-deb/bolt.sh) je v gradnji izdaje (lastnik, 18. 10. 2026): CI gradi oba paketa .deb s
        SAFEER_WEBKIT_BOLT=1; bolt-22 je ista gradnja LLVM kot clang-22; ce BOLT pade, pade gradnja (nikoli tiho brez)."""
        zgradi=(self.WEBKIT_DEB/'zgradi.sh').read_text()
        self.assertIn('BOLT="${SAFEER_WEBKIT_BOLT:-0}"',zgradi)
        self.assertIn('BOLT_MOZNOSTI=("-DCMAKE_SHARED_LINKER_FLAGS=$LDFLAGS -Wl,--emit-relocs")',zgradi)   # utrjena gradnja: LDFLAGS ostanejo
        self.assertIn('"${WK_MOZNOSTI[@]}" "${PGO_MOZNOSTI[@]}" "${BOLT_MOZNOSTI[@]}"',zgradi)
        # BOLT po namestitvi in pred strip (potrebuje simbole in relokacije), zapis v gradnja.txt.
        klic=zgradi.index('bash "$KOREN/packaging/webkit-deb/bolt.sh" "$PREDPONA" "$DELO/bolt"')
        self.assertLess(zgradi.index('ninja -C "$DELO/webkit" install'),klic)
        self.assertLess(klic,zgradi.index('> "$d/gradnja.txt"'))
        self.assertLess(klic,zgradi.index('--strip-unneeded'))
        self.assertIn('else echo "bolt: ne"; fi',zgradi)
        self.assertIn('-fprofile-use --emit-relocs; do',zgradi)
        # bolt-22 pripet na isto gradnjo kot clang-22, preverba ponudbe apt.llvm.org in namescene razlicice.
        odvisnosti=(self.WEBKIT_DEB/'odvisnosti.sh').read_text()
        self.assertRegex(odvisnosti,r'\nLLVM_PAKET="[^"]+"\n')
        self.assertIn('for PAKET in clang-22 bolt-22; do',odvisnosti)
        self.assertIn('"bolt-22=$LLVM_PAKET" "libbolt-22-dev=$LLVM_PAKET"',odvisnosti)
        self.assertIn("[ \"$(dpkg-query -W -f '${Version}' bolt-22)\" = \"$LLVM_PAKET\" ]",odvisnosti)
        bolt=(self.WEBKIT_DEB/'bolt.sh').read_text()
        self.assertIn('set -euo pipefail',bolt)
        self.assertIn('''sed -n 's/^LLVM_PAKET="\\(.*\\)"$/\\1/p' "$KOREN/packaging/webkit-deb/odvisnosti.sh"''',bolt)
        for niz in ('-instrument','--instrumentation-file-append-pid','merge-fdata','--reorder-blocks=ext-tsp',
                    '--reorder-functions=cdsort','--split-functions','--split-all-cold','--icf=safe','--use-gnu-stack',
                    '"$PREDPONA" "$DELO/fdata" bolt','"$PREDPONA" "$DELO/preveri" preveri','.rela.text',
                    'bolt: da (llvm-bolt $LLVM_RAZLICICA, bolt-22 $LLVM_PAKET'):
            self.assertIn(niz,bolt)
        self.assertNotIn('grep -q',bolt)   # pipefail: -q zapre cev (SIGPIPE) in javi napacno napako
        self.assertNotIn('apt-get',bolt)   # orodja namesti odvisnosti.sh
        subprocess.run(['bash','-n',str(self.WEBKIT_DEB/'bolt.sh')],check=True)
        # Isti ucni tek kot PGO: pgo_trening.py (v kljucu profila Flatpaka) ostane nespremenjen, procesi koncajo normalno.
        trening=(self.WEBKIT_DEB/'bolt_trening.py').read_text()
        self.assertIn('WebKit.WebView.terminate_web_process = lambda self: None',trening)
        self.assertIn('"pgo_trening.py"',trening)
        compile(trening,'bolt_trening.py','exec')
        ucni=(self.WEBKIT_DEB/'ucni_tek.sh').read_text()
        self.assertIn('NACIN="${3:-pgo}"',ucni)
        self.assertIn('TRENING="$KOREN/packaging/webkit-deb/bolt_trening.py"',ucni)
        # CI: posel webkit-deb vedno z BOLT, kljuc iz datotek BOLT; profil PGO ni odvisen od BOLT; zapis gradnje preverjen.
        potek=(ROOT/'.github/workflows/linux-packages.yml').read_text()
        profil=potek.split('\n  webkit-deb-profil:\n',1)[1].split('\n  webkit-deb:\n',1)[0]
        posel=potek.split('\n  webkit-deb:\n',1)[1].split('\n  dav1d-deb:\n',1)[0]
        self.assertIn('SAFEER_WEBKIT_PGO=uporaba SAFEER_WEBKIT_PROFRAW=build/pgo/profraw SAFEER_WEBKIT_BOLT=1 \\\n',posel)
        self.assertEqual(posel.count('key: webkit-deb-pgo-bolt-safeer-webkit-${{ hashFiles('),2)
        for datoteka in ('packaging/webkit-deb/bolt.sh','packaging/webkit-deb/bolt_trening.py'):
            self.assertEqual(posel.count("'%s'"%datoteka),2,datoteka)
        self.assertNotIn('bolt',profil.lower())
        self.assertIn('python3-gi gir1.2-gtk-4.0 xvfb xauth dbus procps git',posel)
        self.assertIn("grep -q '^bolt: da (llvm-bolt 22\\.' gradnja.txt",posel)
        self.assertIn("grep -q '^build.ninja --emit-relocs: [1-9]' gradnja.txt",posel)
        self.assertNotIn('inputs.bolt',potek)
        # Paket: preizkus nalozenih knjiznic zahteva zapis BOLT optimizacije (ne instrumentacije).
        smoke=(ROOT/'packaging/smoke_webkit_deb.py').read_text()
        self.assertIn('"\\nbolt: da (" not in gradnja',smoke)
        self.assertIn('b"BOLT revision"',smoke)
        # Poskusi (obe knjiznici, nato vsaka sama), JavaScriptCore brez zbirnika LLInt, sklad klicev ob padcu (gdb).
        for niz in ('webkit jsc;webkit;jsc','llintPCRangeStart','llintPCRangeEnd','--skip-funcs=','gdb -q -batch',
                    'brez BOLT','obnovi'):
            self.assertIn(niz,bolt)
        self.assertIn('xauth dbus procps git gdb\n',posel)
        self.assertIn('"; %s brez BOLT" % os.path.basename(os.path.realpath(pot)) in gradnja',smoke)
        # Nadaljevanje (lastnik, 19. 10. 2026): stanje pred BOLT v predpomnilniku tudi ob padcu, nadaljuj.sh brez prevoda.
        nadaljuj=(self.WEBKIT_DEB/'nadaljuj.sh').read_text()
        subprocess.run(['bash','-n',str(self.WEBKIT_DEB/'nadaljuj.sh')],check=True)
        self.assertIn('bash "$KOREN/packaging/webkit-deb/bolt.sh" "$PREDPONA" "$DELO/bolt"',nadaljuj)
        for niz in ('$Z/cmake.txt','$Z/stevci.txt','--strip-unneeded',"tar -C / -I 'zstd -19 -T0'",'zstd -q -t "$IZHOD.del"'):
            self.assertIn(niz,nadaljuj)
        self.assertNotIn('ninja',nadaljuj.replace('build.ninja',''))
        self.assertIn('SAFEER_BOLT_PREDBOLT',bolt)
        self.assertEqual(posel.count('key: webkit-deb-predbolt-safeer-webkit-${{ hashFiles('),2)
        self.assertIn("if: always() && steps.wk.outputs.cache-hit != 'true' && steps.predbolt.outputs.cache-hit != 'true'"
                      " && hashFiles('build/webkit-predbolt.tar.zst') != ''",posel)
        self.assertIn('bash packaging/webkit-deb/nadaljuj.sh /usr/lib/safeer-webkit build/safeer-webkit.tar.zst',posel)
        self.assertEqual(posel.count("'packaging/webkit-deb/nadaljuj.sh'"),2)
        # Zapis gradnje v nadaljuj.sh je enak kot v zgradi.sh (iste vrstice za webkitgtk, libsoup, popravke, sistem).
        zgradi_zapis=zgradi.split('> "$d/gradnja.txt"')[0].rsplit('{\n',1)[1]
        for vrstica in zgradi_zapis.splitlines()[-6:]:
            self.assertIn(vrstica.strip(),nadaljuj)

    def test_bolt_brez_izvrsljivega_sklada(self):
        """Raziskava 19. 10. 2026: --use-gnu-stack je v knjiznicah 1.0.127 zamenjal PT_GNU_STACK z novim segmentom; glibc je
        zato vsem procesom z WebKitom (namizje, brskalnik, spletni proces) naredil izvrsljiv sklad, glibc 2.41+ pa take
        knjiznice ne nalozi. Moznost ne sme vec v bolt.sh, bolt.sh in dimni preizkus pa napako ujameta sama."""
        bolt=(self.WEBKIT_DEB/'bolt.sh').read_text()
        moznosti=bolt.split('MOZNOSTI=(',1)[1].split(')',1)[0]
        self.assertNotIn('--use-gnu-stack',moznosti)
        self.assertIn('awk \'$1 == "GNU_STACK" {print $7}\'',bolt)
        self.assertIn('nima PT_GNU_STACK RW',bolt)
        smoke=(ROOT/'packaging/smoke_webkit_deb.py').read_text()
        self.assertIn('preveri_sklad()',smoke.split('def ob_zagonu',1)[1])
        import importlib.util
        spec=importlib.util.spec_from_file_location('smoke_sklad',ROOT/'packaging/smoke_webkit_deb.py')
        vir=smoke.split('PT_GNU_STACK, PF_X =',1)[1].split('def preveri_sklad',1)[0]
        imena={}
        exec('PT_GNU_STACK, PF_X ='+vir,imena)
        with tempfile.TemporaryDirectory() as d:
            # knjiznica z RW skladom (iz tega sistema) in ista z izbrisanim PT_GNU_STACK (tip spremenjen v PT_NULL)
            # vsak ELF64 tega sistema ima PT_GNU_STACK RW - tudi tolmac Pythona, ki ta preizkus poganja
            dobra=Path(d)/'dobra.so'
            import sys as _sys
            dobra.write_bytes(Path(os.path.realpath(_sys.executable)).read_bytes())
            self.assertEqual(imena['sklad_elf'](str(dobra)) & imena['PF_X'],0)
            podatki=bytearray(dobra.read_bytes())
            phoff=int.from_bytes(podatki[0x20:0x28],'little'); phentsize=int.from_bytes(podatki[0x36:0x38],'little')
            phnum=int.from_bytes(podatki[0x38:0x3A],'little')
            for i in range(phnum):
                o=phoff+i*phentsize
                if int.from_bytes(podatki[o:o+4],'little')==imena['PT_GNU_STACK']:
                    podatki[o:o+4]=(0).to_bytes(4,'little')
            slaba=Path(d)/'slaba.so'
            slaba.write_bytes(bytes(podatki))
            self.assertIsNone(imena['sklad_elf'](str(slaba)),'knjiznica brez PT_GNU_STACK mora biti prepoznana')

    def test_bolt_na_preizkusni_knjiznici(self):
        """bolt.sh od instrumentacije do optimizirane knjiznice na majhnih knjiznicah z imeni WebKita (Clang 22, lld,
        --emit-relocs); ucni tek je preizkusni program. Brez bolt-22 in clang-22 (CI preizkusov) preskoceno."""
        llvm='/usr/lib/llvm-22/bin'
        if not all(os.access(os.path.join(llvm,o),os.X_OK) for o in ('llvm-bolt','merge-fdata','clang++','llvm-readelf')):
            self.skipTest('ni bolt-22 in clang-22 (apt.llvm.org)')
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            lib=d/'webkit'/'lib'
            lib.mkdir(parents=True)
            (d/'wk.cpp').write_text('#include <map>\n#include <string>\nextern "C" int wk(int n) { std::map<std::string,int> m;'
                                    ' for (int i = 0; i < n; i++) m[std::to_string(i % 31)] += i; int s = 0;'
                                    ' for (auto& p : m) s += p.second % 7; return s; }\n')
            (d/'jsc.cpp').write_text('#include <algorithm>\n#include <vector>\nextern "C" int jsc(int n) { std::vector<int> v;'
                                     ' for (int i = 0; i < n; i++) v.push_back(i * 7919 % 1000); std::sort(v.begin(), v.end());'
                                     ' return v[n / 2]; }\n')
            (d/'glavni.cpp').write_text('#include <cstdio>\nextern "C" int wk(int); extern "C" int jsc(int);\n'
                                        'int main() { long s = 0; for (int i = 0; i < 300; i++) s += wk(50) + jsc(200);'
                                        ' std::printf("%ld\\n", s); return 0; }\n')
            for vir,ime,povezava in (('wk.cpp','libwebkitgtk-6.0.so.4.19.4','libwebkitgtk-6.0.so.4'),
                                     ('jsc.cpp','libjavascriptcoregtk-6.0.so.1.8.8','libjavascriptcoregtk-6.0.so.1')):
                subprocess.run([llvm+'/clang++','-O2','-fPIC','-shared','-fuse-ld=lld','-Wl,--emit-relocs','-Wl,-soname,'+povezava,
                                '-o',str(lib/ime),str(d/vir)],check=True)
                (lib/povezava).symlink_to(ime)
            subprocess.run([llvm+'/clang++','-O2','-fuse-ld=lld','-o',str(d/'glavni'),str(d/'glavni.cpp'),'-L'+str(lib),
                            '-l:libwebkitgtk-6.0.so.4','-l:libjavascriptcoregtk-6.0.so.1','-Wl,-rpath,'+str(lib)],check=True)
            pricakovano=subprocess.run([str(d/'glavni')],capture_output=True,text=True,check=True).stdout
            tek=d/'tek.sh'
            tek.write_text('#!/bin/sh\nset -e\nmkdir -p "$2"\n"%s" > "$2/izhod.txt"\n' % (d/'glavni'))
            okolje=dict(os.environ,SAFEER_BOLT_TEK=str(tek),SAFEER_BOLT_NAJMANJ_PROFILOV='1',SAFEER_BOLT_NAJVECJI_PROFIL_MIB='0')
            r=subprocess.run(['bash',str(self.WEBKIT_DEB/'bolt.sh'),str(d/'webkit'),str(d/'delo')],capture_output=True,
                             text=True,env=okolje)
            self.assertEqual(r.returncode,0,r.stdout[-3000:]+r.stderr[-3000:])
            povzetek=(d/'delo'/'povzetek.txt').read_text()
            self.assertTrue(povzetek.startswith('bolt: da (llvm-bolt 22.'),povzetek)
            for ime in ('libwebkitgtk-6.0.so.4.19.4','libjavascriptcoregtk-6.0.so.1.8.8'):
                self.assertIn(ime,povzetek)
                sekcije=subprocess.run([llvm+'/llvm-readelf','-S',str(lib/ime)],capture_output=True,text=True).stdout
                self.assertIn('.note.bolt_info',sekcije)
                self.assertNotIn('bolt_instr',subprocess.run([llvm+'/llvm-readelf','-s',str(lib/ime)],capture_output=True,
                                                              text=True).stdout)   # optimizirana, ne instrumentirana
                # PT_GNU_STACK RW (19. 10. 2026: --use-gnu-stack ga je odstranil -> izvrsljiv sklad vseh procesov)
                segmenti=subprocess.run([llvm+'/llvm-readelf','-lW',str(lib/ime)],capture_output=True,text=True).stdout
                self.assertRegex(segmenti,r'GNU_STACK\s+(\S+\s+){5}RW\s',ime)
            # Ucni tek je dal profil (instrumentirani knjiznici), preverba je tekla z optimiziranima - enak rezultat.
            self.assertTrue(list((d/'delo'/'fdata').glob('webkit.*.fdata')))
            self.assertTrue(list((d/'delo'/'fdata').glob('jsc.*.fdata')))
            self.assertEqual((d/'delo'/'preveri'/'izhod.txt').read_text(),pricakovano)
            self.assertEqual(subprocess.run([str(d/'glavni')],capture_output=True,text=True).stdout,pricakovano)

    def test_prednalaganje_po_prijavi(self):
        """packaging/prednalozi.py (paket .deb z nasim WebKitom): po prijavi, z zamikom in najnizjo prioriteto, prebere
        WebKit in kodo brskalnika (ne Safeer DRM); nic, ce brskalnik tece ali ga uporabnik ni uporabil 14 dni."""
        import importlib.util
        spec=importlib.util.spec_from_file_location('prednalozi',ROOT/'packaging/prednalozi.py')
        p=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(p)
        with tempfile.TemporaryDirectory() as d:
            koren=Path(d)/'safeer-browser'
            # Skupni WebKit (paket safeer-webkit) je ob mapi programa: /usr/lib/safeer-webkit ob /usr/lib/safeer-browser.
            for rel,vel in (('safeer-webkit/lib/libwebkitgtk-6.0.so.4.19.4',300000),('safeer-browser/core/os_splet.py',1000),
                            ('safeer-browser/safeer_brskalnik.py',100),('safeer-browser/safeer-drm/safeer-drm',500000),
                            ('safeer-os/core/os_splet.py',7)):
                (Path(d)/rel).parent.mkdir(parents=True,exist_ok=True)
                (Path(d)/rel).write_bytes(b'x'*vel)
            (Path(d)/'safeer-webkit/lib/libwebkitgtk-6.0.so.4').symlink_to('libwebkitgtk-6.0.so.4.19.4')
            poti=sorted(os.path.relpath(x,d) for x in p.datoteke(str(koren)))
            self.assertEqual(poti,['safeer-browser/core/os_splet.py','safeer-browser/safeer_brskalnik.py',
                                   'safeer-webkit/lib/libwebkitgtk-6.0.so.4.19.4'])
            self.assertEqual(p.prednalozi(str(koren)),(3,301100))
            # Paket z lastno kopijo (do 1.0.127~pred): mapa webkit v programu, ce skupnega ni.
            star=Path(d)/'star'/'safeer-browser'
            (star/'webkit/lib').mkdir(parents=True)
            (star/'webkit/lib/libwebkitgtk-6.0.so.4.19.4').write_bytes(b'x'*10)
            self.assertEqual(p.webkit(str(star)),str(star/'webkit'))
            d=Path(d)
            nastavitve=d/'c'/'safeer-mint'
            nastavitve.mkdir(parents=True)
            (nastavitve/'settings.json').write_text('{}')
            with patch.dict(os.environ,{'XDG_CONFIG_HOME':str(d/'c')}):
                self.assertTrue(p.nedavno_uporabljen())
                self.assertFalse(p.nedavno_uporabljen(time.time()+15*86400))
            with patch.dict(os.environ,{'XDG_CONFIG_HOME':str(d/'ni')}):
                self.assertFalse(p.nedavno_uporabljen())
                self.assertEqual(p.main(['--zdaj']),0)     # brskalnik ni bil uporabljen: nic
        self.assertEqual(p.VSEBINA,("core","ui","assets","safeer_brskalnik.py","packaging"))
        self.assertEqual(p.WEBKIT,("../safeer-webkit","webkit"))
        self.assertGreaterEqual(p.ZAMIK,30)
        # Samo paket z nasim WebKitom; zagon ob prijavi (XDG autostart) z isto potjo, besedila v 6 jezikih.
        deb=(ROOT/'build_deb.sh').read_text()
        kos=deb.split('if [ -n "$WEBKIT_DEB" ]; then\n    # Nas WebKit po prijavi',1)[1].split('\nfi\n',1)[0]
        self.assertIn('install -Dm755 "$DIR/packaging/prednalozi.py" "$BUILD_ROOT/usr/lib/safeer-browser/prednalozi.py"',kos)
        self.assertIn('"$BUILD_ROOT/etc/xdg/autostart/safeer-browser-prednalaganje.desktop"',kos)
        vnos=(ROOT/'packaging/safeer-browser-prednalaganje.desktop').read_text()
        self.assertIn('Exec=/usr/bin/python3 -s /usr/lib/safeer-browser/prednalozi.py\n',vnos)
        self.assertIn('TryExec=/usr/lib/safeer-browser/prednalozi.py\n',vnos)
        for jezik in ('sl','de','es','fr','it'):
            self.assertIn('Name[%s]='%jezik,vnos)
            self.assertIn('Comment[%s]='%jezik,vnos)
        if shutil.which('desktop-file-validate'):
            subprocess.run(['desktop-file-validate',str(ROOT/'packaging/safeer-browser-prednalaganje.desktop')],check=True)

    def test_typelib_dobi_absolutno_pot_do_nase_knjiznice(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('typelibi',self.WEBKIT_DEB/'typelibi.py')
        t=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(t)
        gir='<namespace name="WebKit" shared-library="libwebkitgtk-6.0.so.4,libjavascriptcoregtk-6.0.so.1" c:prefix="WebKit">'
        novo,n=t.absolutno(gir,'/usr/lib/safeer-webkit/lib/')
        self.assertEqual(n,1)
        self.assertIn('shared-library="/usr/lib/safeer-webkit/lib/libwebkitgtk-6.0.so.4,'
                      '/usr/lib/safeer-webkit/lib/libjavascriptcoregtk-6.0.so.1"',novo)
        # Ze absolutna pot ostane, brez knjiznice ni sprememb.
        self.assertEqual(t.absolutno(novo,'/drugje/lib')[0],novo)
        self.assertEqual(t.absolutno('<namespace name="GLib">','/x')[1],0)

    def _webkit(self, koren, mapa='webkit'):
        """Lazni typelib WebKit: mapa 'webkit' v programu (stara postavitev, razvoj) ali skupni 'safeer-webkit' (koren je
        tedaj mapa, v kateri so programi, npr. /usr/lib)."""
        tl=Path(koren)/mapa/'lib/girepository-1.0'
        tl.mkdir(parents=True)
        (tl/'WebKit-6.0.typelib').write_bytes(b'x')
        return str(tl)

    def test_zasebni_webkit_najde_skupno_predpono(self):
        """Od 19. 10. 2026: safeer-os, safeer-control in safeer-browser najdejo isti WebKit v /usr/lib/safeer-webkit
        (mapa safeer-webkit ob mapi programa); mapa webkit v programu (paket z lastno kopijo, razvoj) ima prednost;
        izvorna mapa brez obeh ostane na WebKitu sistema (None)."""
        from core import zasebni_webkit
        with tempfile.TemporaryDirectory() as d:
            lib=Path(d)/'usr/lib'
            for program in ('safeer-os','safeer-control','safeer-browser','drugo'):
                (lib/program).mkdir(parents=True)
            self.assertIsNone(zasebni_webkit.predpona(str(lib/'safeer-os')))
            self._webkit(lib,'safeer-webkit')
            for program in ('safeer-os','safeer-control','safeer-browser'):
                self.assertEqual(zasebni_webkit.predpona(str(lib/program)),str(lib/'safeer-webkit'),program)
            # Ostanek stare kopije brez typeliba (dpkg je odstranil datoteke) ne steje.
            (lib/'safeer-os/webkit/lib').mkdir(parents=True)
            self.assertEqual(zasebni_webkit.predpona(str(lib/'safeer-os')),str(lib/'safeer-webkit'))
            # Izvorna mapa (razvoj) dalec od /usr/lib: WebKit sistema, kot doslej.
            izvor=Path(d)/'dom/Safeer-linux'
            izvor.mkdir(parents=True)
            self.assertIsNone(zasebni_webkit.predpona(str(izvor)))
            okolje={k:v for k,v in os.environ.items() if k not in ('FLATPAK_ID','APPIMAGE','SAFEER_SISTEMSKI_WEBKIT','GST_PLUGIN_PATH')}
            okolje['GI_TYPELIB_PATH']='/a'
            with patch.dict(os.environ,okolje,clear=True):
                self.assertEqual(zasebni_webkit.nastavi(str(lib/'safeer-control')),str(lib/'safeer-webkit'))
                self.assertEqual(os.environ['GI_TYPELIB_PATH'],'%s:/a'%(lib/'safeer-webkit/lib/girepository-1.0'))
        self.assertEqual(zasebni_webkit.PREDPONE_PAKETOV[0],'/usr/lib/safeer-webkit')
        # Odtis gradnje uporabljenega WebKita (paket.sh): Safeer OS in Safeer Control ga spremljata (nova_razlicica).
        with tempfile.TemporaryDirectory() as d:
            self._webkit(Path(d),'safeer-webkit')
            (Path(d)/'safeer-os').mkdir()
            with patch.object(zasebni_webkit,'_nastavljena',None):
                self.assertIsNone(zasebni_webkit.pot_odtisa())
            with patch.object(zasebni_webkit,'_nastavljena',str(Path(d)/'safeer-webkit')):
                self.assertIsNone(zasebni_webkit.pot_odtisa())          # paket brez odtisa
                (Path(d)/'safeer-webkit/share/webkitgtk-safeer').mkdir(parents=True)
                (Path(d)/'safeer-webkit/share/webkitgtk-safeer/odtis').write_text('0123456789abcdef\n')
                self.assertEqual(zasebni_webkit.pot_odtisa(),str(Path(d)/'safeer-webkit/share/webkitgtk-safeer/odtis'))
        for vstop,datoteka in (('safeer_os.py','VERSION_OS'),('safeer_control.py','VERSION_CONTROL')):
            s=(ROOT/vstop).read_text()
            telo=s.split('    def _spremljaj_novo_razlicico(self) -> None:',1)[1].split('\n    def ',1)[0]
            self.assertIn('odtis = zasebni_webkit.pot_odtisa()',telo,vstop)
            self.assertIn('nova_razlicica.Spremljevalec(\n                    Gio, GLib, odtis, nova_razlicica.beri(odtis)',telo,vstop)
            self.assertIn('nova_razlicica.beri(os.path.join(KOREN, "packaging", "%s"))'%datoteka,telo,vstop)
        # Zunanji programi ne podedujejo poti skupnega WebKita (kot prej poti kopij v paketih).
        cisto=zasebni_webkit.okolje_za_zunanje({'GI_TYPELIB_PATH':'/usr/lib/safeer-webkit/lib/girepository-1.0:/x',
                                                'GST_PLUGIN_PATH':'/usr/lib/safeer-webkit/lib/gstreamer-1.0'})
        self.assertEqual(cisto,{'GI_TYPELIB_PATH':'/x'})

    def test_zasebni_webkit_najde_predpono_paketa(self):
        from core import zasebni_webkit
        with tempfile.TemporaryDirectory() as d:
            brskalnik=Path(d)/'safeer-browser'
            tl=self._webkit(brskalnik)
            os_tl=self._webkit(Path(d)/'safeer-os')
            (Path(d)/'safeer-control').mkdir()
            self.assertEqual(zasebni_webkit.predpona(str(brskalnik)),str(brskalnik/'webkit'))
            # Safeer Control brez svoje mape webkit in brez skupnega safeer-webkit: ni nasega WebKita.
            self.assertIsNone(zasebni_webkit.predpona(str(Path(d)/'safeer-control')))
            self.assertIsNone(zasebni_webkit.predpona(str(Path(d)/'drugo')))
            okolje={k:v for k,v in os.environ.items() if k not in ('FLATPAK_ID','APPIMAGE','SAFEER_SISTEMSKI_WEBKIT')}
            okolje['GI_TYPELIB_PATH']='/a:%s'%tl
            with patch.dict(os.environ,okolje,clear=True):
                self.assertEqual(zasebni_webkit.nastavi(str(brskalnik)),str(brskalnik/'webkit'))
                # Na zacetku in brez podvajanja (ponovni zagon iz istega procesa).
                self.assertEqual(os.environ['GI_TYPELIB_PATH'],'%s:/a'%tl)
                zasebni_webkit.nastavi(str(brskalnik))
                self.assertEqual(os.environ['GI_TYPELIB_PATH'],'%s:/a'%tl)
            for kljuc in ('FLATPAK_ID','APPIMAGE','SAFEER_SISTEMSKI_WEBKIT'):
                with patch.dict(os.environ,dict(okolje,**{kljuc:'1'}),clear=True):
                    os.environ.pop('GI_TYPELIB_PATH')
                    self.assertIsNone(zasebni_webkit.nastavi(str(Path(d)/'safeer-os')))
                    self.assertNotIn('GI_TYPELIB_PATH',os.environ)
            self.assertTrue(os_tl)

    def test_zasebni_webkit_doda_vticnike_gstreamer_dav1d(self):
        """dav1ddec v PREDPONA/lib/gstreamer-1.0 (packaging/webkit-deb/dav1d.sh): mapa na konec GST_PLUGIN_PATH,
        obstojeca vrednost ostane, brez podvajanja; brez mape (lokalna gradnja) GST_PLUGIN_PATH ostane nedotaknjen."""
        from core import zasebni_webkit
        with tempfile.TemporaryDirectory() as d:
            brskalnik=Path(d)/'safeer-browser'
            self._webkit(brskalnik)
            okolje={k:v for k,v in os.environ.items()
                    if k not in ('FLATPAK_ID','APPIMAGE','SAFEER_SISTEMSKI_WEBKIT','GST_PLUGIN_PATH')}
            with patch.dict(os.environ,okolje,clear=True):
                zasebni_webkit.nastavi(str(brskalnik))
                self.assertNotIn('GST_PLUGIN_PATH',os.environ)
            vticniki=brskalnik/'webkit/lib/gstreamer-1.0'
            vticniki.mkdir()
            with patch.dict(os.environ,dict(okolje,GST_PLUGIN_PATH='/a'),clear=True):
                zasebni_webkit.nastavi(str(brskalnik))
                self.assertEqual(os.environ['GST_PLUGIN_PATH'],'/a:%s'%vticniki)
                zasebni_webkit.nastavi(str(brskalnik))
                self.assertEqual(os.environ['GST_PLUGIN_PATH'],'/a:%s'%vticniki)
            with patch.dict(os.environ,okolje,clear=True):
                zasebni_webkit.nastavi(str(brskalnik))
                self.assertEqual(os.environ['GST_PLUGIN_PATH'],str(vticniki))
            # Safeer Control (v paketu safeer-os) uporabi skupni WebKit z dav1ddec (paket safeer-webkit).
            os_vt=Path(d)/'safeer-webkit/lib/gstreamer-1.0'
            self._webkit(Path(d),'safeer-webkit')
            os_vt.mkdir()
            (Path(d)/'safeer-control').mkdir()
            with patch.dict(os.environ,okolje,clear=True):
                zasebni_webkit.nastavi(str(Path(d)/'safeer-control'))
                self.assertEqual(os.environ['GST_PLUGIN_PATH'],str(os_vt))
            with patch.dict(os.environ,dict(okolje,FLATPAK_ID='x'),clear=True):
                zasebni_webkit.nastavi(str(brskalnik))
                self.assertNotIn('GST_PLUGIN_PATH',os.environ)

    def test_dav1d_skripta_pripne_crate_in_preveri_vticnik(self):
        """packaging/webkit-deb/dav1d.sh: gst-plugin-dav1d 0.14.5 s SHA-256 iz crates.io, odvisnosti iz Cargo.lock
        (--locked), strip, preverba v GStreamerju sistema (rang nad av1dec)."""
        skripta=(self.WEBKIT_DEB/'dav1d.sh').read_text()
        self.assertIn('RAZLICICA=0.14.5\n',skripta)
        self.assertIn('SHA256=fee4d853d1a7b253a6771e63dac20c43bce86ea27486f8672e65a0f7c0e0bcd6\n',skripta)
        self.assertRegex(skripta,r'\nRUST=1\.\d+\.\d+\n')
        for niz in ('https://static.crates.io/crates/gst-plugin-dav1d/gst-plugin-dav1d-$RAZLICICA.crate','sha256sum -c',
                    'build --release --locked','strip --strip-unneeded','LICENSE-MIT','LICENSE-APACHE','gradnja.txt',
                    'libdav1d.so.7','b"dav1ddec"','rang >= 256'):
            self.assertIn(niz,skripta)
        subprocess.run(['bash','-n',str(self.WEBKIT_DEB/'dav1d.sh')],check=True)
        self.assertIn(' libdav1d7 ',(self.WEBKIT_DEB/'knjiznice.sh').read_text())
        vgradi=(self.WEBKIT_DEB/'vgradi.sh').read_text()
        self.assertIn('SAFEER_DAV1D',vgradi)
        self.assertIn('"$WK/lib/gstreamer-1.0/libgstdav1d.so"',vgradi)
        # Vticnik se vgradi pred dpkg-shlibdeps, da odvisnost libdav1d7 zapise iz knjiznice.
        self.assertLess(vgradi.index('libgstdav1d.so"'),vgradi.index('dpkg-shlibdeps -O'))

    #: Zapis gradnje laznega arhiva (kot ga napise zgradi.sh; paket.sh iz njega vzame razlicici WebKitGTK in libsoup).
    GRADNJA=('Ubuntu clang version 22.1.8\nLTO_MODE:UNINITIALIZED=thin\nbuild.ninja -fuse-ld=lld: 10\n'
             'webkitgtk: webkitgtk-2.54.1 %s\nlibsoup: libsoup-3.8.0 %s\npredpona: /usr/lib/safeer-webkit\n'%('a'*64,'b'*64))

    def _lazni_arhiv(self, d, predpona='/usr/lib/safeer-webkit', gradnja=None):
        """Arhiv kot iz zgradi.sh, a ponaredek: ELF datoteke so kopije /bin/true (dovolj za dpkg-shlibdeps in pakiranje)."""
        wk=Path(d)/'drevo'/predpona.lstrip('/')
        for f in ('lib/libwebkitgtk-6.0.so.4','lib/libjavascriptcoregtk-6.0.so.1','lib/libsoup-3.0.so.0',
                  'bin/WebKitWebDriver',
                  'libexec/webkitgtk-6.0/WebKitWebProcess','libexec/webkitgtk-6.0/WebKitNetworkProcess'):
            (wk/f).parent.mkdir(parents=True,exist_ok=True)
            shutil.copy('/bin/true',wk/f)
        for f in ('WebKit-6.0','Soup-3.0'):
            (wk/'lib/girepository-1.0').mkdir(parents=True,exist_ok=True)
            (wk/'lib/girepository-1.0'/(f+'.typelib')).write_bytes(b'x')
        (wk/'share/webkitgtk-safeer').mkdir(parents=True,exist_ok=True)
        (wk/'share/webkitgtk-safeer/gradnja.txt').write_text(self.GRADNJA if gradnja is None else gradnja)
        arhiv=Path(d)/'webkit.tar.zst'
        arhiv.unlink(missing_ok=True)
        subprocess.run(['tar','-C',str(Path(d)/'drevo'),'-I','zstd','-cf',str(arhiv),'usr'],check=True)
        return arhiv

    def _dav1d_mapa(self, d, so):
        mapa=Path(d)/'dav1d'
        mapa.mkdir()
        shutil.copy(so,mapa/'libgstdav1d.so')
        for f in ('LICENSE-MIT','LICENSE-APACHE'):
            (mapa/f).write_text('licenca\n')
        (mapa/'gradnja.txt').write_text('gst-plugin-dav1d 0.14.5 (preizkus)\n')
        return mapa

    def test_vgradi_doda_dav1d_in_zahteva_libdav1d7(self):
        """SAFEER_DAV1D: vticnik v PREDPONA/lib/gstreamer-1.0 + licenci; libdav1d7 v Depends iz dpkg-shlibdeps,
        sicer vgradi.sh pade (vticnik, ki ni povezan z libdav1d, ni dav1ddec)."""
        for orodje in ('dpkg-shlibdeps','zstd','file'):
            if not shutil.which(orodje):
                self.skipTest('ni %s'%orodje)
        # Negativno: ELF brez libdav1d.so.7.
        with tempfile.TemporaryDirectory() as d:
            arhiv=self._lazni_arhiv(d)
            okolje=dict(os.environ,SAFEER_DAV1D=str(self._dav1d_mapa(d,'/bin/true')))
            r=subprocess.run(['bash',str(self.WEBKIT_DEB/'vgradi.sh'),str(Path(d)/'koren'),str(arhiv)],
                             env=okolje,capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0,r.stdout)
            self.assertIn('ni libdav1d7',r.stderr)
            # Manjkajoca mapa vticnika se zavrne.
            okolje['SAFEER_DAV1D']=str(Path(d)/'ni')
            r=subprocess.run(['bash',str(self.WEBKIT_DEB/'vgradi.sh'),str(Path(d)/'koren'),str(arhiv)],
                             env=okolje,capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('ni libgstdav1d.so',r.stderr)
        # Pozitivno: prava knjiznica, povezana z libdav1d (le ce sta prevajalnik in libdav1d-dev).
        cc=shutil.which('cc')
        if not cc or not shutil.which('pkg-config') or not subprocess.run(['pkg-config','--exists','dav1d'],capture_output=True).returncode==0:
            self.skipTest('ni cc ali libdav1d-dev')
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'v.c').write_text('#include <dav1d/dav1d.h>\nconst char *v(void) { return dav1d_version(); }\n')
            so=Path(d)/'v.so'
            subprocess.run([cc,'-shared','-fPIC','-o',str(so),str(Path(d)/'v.c'),'-Wl,--no-as-needed','-ldav1d'],check=True)
            arhiv=self._lazni_arhiv(d)
            okolje=dict(os.environ,SAFEER_DAV1D=str(self._dav1d_mapa(d,so)))
            koren=Path(d)/'koren'
            r=subprocess.run(['bash',str(self.WEBKIT_DEB/'vgradi.sh'),str(koren),str(arhiv)],
                             env=okolje,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr[-2000:])
            self.assertRegex(r.stdout,r'(^|, )libdav1d7( |,|$)')
            wk=koren/'usr/lib/safeer-webkit'
            self.assertTrue((wk/'lib/gstreamer-1.0/libgstdav1d.so').is_file())
            self.assertEqual((wk/'lib/gstreamer-1.0/libgstdav1d.so').stat().st_mode & 0o777,0o644)
            for f in ('LICENSE-MIT','LICENSE-APACHE','gradnja.txt'):
                self.assertTrue((wk/'share/doc/gst-plugin-dav1d'/f).is_file(),f)

    def test_smoke_preveri_dav1d_in_predvaja_av1(self):
        """packaging/smoke_webkit_deb.py: dav1ddec iz predpone z rangom nad drugimi dekoderji AV1 in predvajanje
        vgrajenega videa AV1 v strani (proces, ki dekodira, ima nalozen nas libgstdav1d.so)."""
        import base64
        import hashlib
        smoke=(ROOT/'packaging/smoke_webkit_deb.py').read_text()
        for niz in ('gst_element_factory_find','b"dav1ddec"','b"av1dec"','"libgstdav1d.so"','/av1.webm','"AV1 ok','::notice::dav1d'):
            self.assertIn(niz,smoke)
        vgrajen=smoke.split('AV1_WEBM = base64.b64decode("""',1)[1].split('""")',1)[0]
        webm=base64.b64decode(vgrajen)
        self.assertEqual(webm[:4],bytes.fromhex('1a45dfa3'))
        self.assertEqual(hashlib.sha256(webm).hexdigest(),'972c68171a82bd8558b7031503168d7a4351a96ffede52f3e7925b6ae7ff6952')
        self.assertIn(b'V_AV1',webm)
        self.assertIn('stran AV1','\n'.join((ROOT/'tools/mint_namestitev/v_vsebniku.sh').read_text().splitlines()))

    def test_ci_gradi_dav1d_za_oba_paketa(self):
        potek=(ROOT/'.github/workflows/linux-packages.yml').read_text()
        posel=potek.split('\n  dav1d-deb:\n',1)[1].split('\n  brskalnik:\n',1)[0]
        self.assertIn('runs-on: ubuntu-24.04',posel)
        self.assertIn('libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libdav1d-dev',posel)
        self.assertIn('bash packaging/webkit-deb/dav1d.sh build/dav1d',posel)
        self.assertEqual(posel.count("key: dav1d-deb-${{ hashFiles('packaging/webkit-deb/dav1d.sh') }}"),2)
        self.assertIn('name: dav1d-deb',posel)
        # dav1ddec gre enkrat v paket safeer-webkit (posel webkit-deb); programa ga dobita z odvisnostjo.
        wk=potek.split('\n  webkit-deb:\n',1)[1].split('\n  dav1d-deb:\n',1)[0]
        self.assertIn('needs: [webkit-deb-profil, dav1d-deb]\n',wk)
        self.assertIn('name: dav1d-deb\n          path: build/dav1d',wk)
        self.assertIn('SAFEER_DAV1D=build/dav1d bash packaging/webkit-deb/paket.sh build/safeer-webkit.tar.zst .',wk)
        self.assertIn("grep -F './usr/lib/safeer-webkit/lib/gstreamer-1.0/libgstdav1d.so'",wk)
        self.assertIn("Depends | grep -E '(^|, )libdav1d7( |,|$)'",wk)
        for ime,naslednji,potrebe in (('brskalnik','safeer-os','webkit-deb'),('safeer-os','qt-xcb','[webkit-deb, rqbit-deb]')):
            with self.subTest(posel=ime):
                del_=potek.split('\n  %s:\n'%ime,1)[1].split('\n  %s:\n'%naslednji,1)[0]
                self.assertIn('needs: %s\n'%potrebe,del_)
                self.assertNotIn('SAFEER_DAV1D',del_)
                self.assertNotIn('dav1d-deb',del_)
        # Flatpak: samo porocilo, ali runtime GNOME 50 ze ima dav1ddec (posel ne pade).
        for ime,app,naslednji in (('flatpak','SafeerOS','flatpak-brskalnik'),('flatpak-brskalnik','SafeerBrowser','scit-lab')):
            with self.subTest(flatpak=ime):
                del_=potek.split('\n  %s:\n'%ime,1)[1].split('\n  %s:\n'%naslednji,1)[0]
                korak=del_.split('- name: AV1 decoder dav1ddec in the GNOME 50 runtime (report only)',1)[1].split('\n      - ',1)[0]
                self.assertIn('continue-on-error: true',korak)
                self.assertIn('APP=io.github.memelandfaner.%s'%app,korak)
                self.assertIn('flatpak run --command=gst-inspect-1.0 $APP dav1ddec',korak)
                self.assertIn('::notice::Flatpak',korak)

    def test_vstopne_tocke_nastavijo_webkit_pred_import_gi(self):
        for vstop in ('safeer_brskalnik.py','safeer_os.py','safeer_control.py'):
            with self.subTest(vstop=vstop):
                s=(ROOT/vstop).read_text()
                self.assertIn('zasebni_webkit.nastavi(KOREN)',s)
                self.assertLess(s.index('zasebni_webkit.nastavi(KOREN)'),s.index('\nimport gi'))
        for skripta in ('install_os_payload.sh','install_control_payload.sh'):
            self.assertRegex((ROOT/'packaging'/skripta).read_text(),r'for modul in [^;]*\bzasebni_webkit\b')

    def _paket_webkit(self, d, arhiv, okolje=None):
        """packaging/webkit-deb/paket.sh v mapo d (drevo paketa v d, da preizkus ne pise v build/ repozitorija)."""
        okolje=dict(os.environ if okolje is None else okolje,SAFEER_WEBKIT_PAKET_DREVO=str(Path(d)/'drevo-paketa'))
        return subprocess.run(['bash',str(self.WEBKIT_DEB/'paket.sh'),str(arhiv),str(d)],env=okolje,capture_output=True,text=True)

    def test_paket_safeer_webkit(self):
        """packaging/webkit-deb/paket.sh: safeer-webkit_<izdaja>_amd64.deb z /usr/lib/safeer-webkit, razlicica izdaje,
        Depends iz dpkg-shlibdeps + peskovnik + TLS, brez skript vzdrzevalca in brez datotek izven predpone in doc.
        Arhiv za drugo predpono (stari arhiv paketa z lastno kopijo) se zavrne."""
        for orodje in ('dpkg-shlibdeps','dpkg-deb','zstd','file'):
            if not shutil.which(orodje):
                self.skipTest('ni %s'%orodje)
        verzija=(ROOT/'packaging/VERSION').read_text().strip()
        deb_verzija=subprocess.run(['bash',str(ROOT/'packaging/deb_razlicica.sh'),verzija],capture_output=True,text=True,
                                   check=True).stdout.strip()
        with tempfile.TemporaryDirectory() as d:
            r=self._paket_webkit(d,self._lazni_arhiv(d))
            self.assertEqual(r.returncode,0,r.stderr[-3000:])
            deb=Path(d)/('safeer-webkit_%s_amd64.deb'%verzija)
            self.assertEqual(r.stdout.strip(),str(deb))
            polja=subprocess.run(['dpkg-deb','-f',str(deb),'Package','Version','Architecture','Depends','Section','Maintainer',
                                  'Description'],capture_output=True,text=True,check=True).stdout
            for niz in ('Package: safeer-webkit\n','Version: %s\n'%deb_verzija,'Architecture: amd64\n','Section: libs\n',
                        'Maintainer: Safeer <info@safeer.si>\n','WebKitGTK 2.54.1 and libsoup 3.8.0'):
                self.assertIn(niz,polja)
            for odvisnost in ('libc6','bubblewrap','xdg-dbus-proxy','glib-networking'):
                self.assertIn(odvisnost,polja)
            self.assertNotIn('gir1.2-webkit-6.0',polja)
            vsebina=subprocess.run(['dpkg-deb','-c',str(deb)],capture_output=True,text=True,check=True).stdout
            poti=[v.split()[5] for v in vsebina.splitlines()]
            self.assertIn('./usr/lib/safeer-webkit/bin/WebKitWebDriver',poti)
            self.assertIn('./usr/lib/safeer-webkit/libexec/webkitgtk-6.0/WebKitWebProcess',poti)
            self.assertIn('./usr/lib/safeer-webkit/lib/girepository-1.0/WebKit-6.0.typelib',poti)
            self.assertIn('./usr/share/doc/safeer-webkit/copyright',poti)
            dovoljeno=('./','./usr/','./usr/lib/','./usr/share/','./usr/share/doc/')
            self.assertEqual([x for x in poti if x not in dovoljeno and not x.startswith(('./usr/lib/safeer-webkit/',
                                                                                          './usr/share/doc/safeer-webkit/'))],[])
            kontrola=subprocess.run(['dpkg-deb','--ctrl-tarfile',str(deb)],capture_output=True,check=True).stdout
            import io,tarfile
            imena={Path(x).name for x in tarfile.open(fileobj=io.BytesIO(kontrola)).getnames()}
            self.assertFalse(imena & {'preinst','postinst','prerm','postrm'},imena)
            # Odtis gradnje (Safeer OS/Control ob novi gradnji zazeneta znova): ista gradnja isti odtis, druga drug.
            def odtis(paket):
                return subprocess.run(['dpkg-deb','--fsys-tarfile',str(paket)],capture_output=True,check=True).stdout
            def beri_odtis(paket):
                t=tarfile.open(fileobj=io.BytesIO(odtis(paket)))
                return t.extractfile('./usr/lib/safeer-webkit/share/webkitgtk-safeer/odtis').read().decode().strip()
            prvi=beri_odtis(deb)
            self.assertRegex(prvi,r'^[0-9a-f]{16}$')
            r=self._paket_webkit(d,self._lazni_arhiv(d))
            self.assertEqual((r.returncode,beri_odtis(deb)),(0,prvi))
            drevo=Path(d)/'drevo'/'usr/lib/safeer-webkit'
            (drevo/'lib/libjavascriptcoregtk-6.0.so.1').write_bytes(b'\x7fELF nova gradnja')
            arhiv=Path(d)/'webkit.tar.zst'
            arhiv.unlink()
            subprocess.run(['tar','-C',str(Path(d)/'drevo'),'-I','zstd','-cf',str(arhiv),'usr'],check=True)
            r=self._paket_webkit(d,arhiv)
            self.assertEqual(r.returncode,0,r.stderr[-2000:])
            self.assertNotEqual(beri_odtis(deb),prvi)
            # Stari arhiv (lastna predpona paketa) ne gre v safeer-webkit.
            with tempfile.TemporaryDirectory() as d2:
                arhiv=self._lazni_arhiv(d2,'/usr/lib/safeer-os/webkit',self.GRADNJA.replace('/usr/lib/safeer-webkit','/usr/lib/safeer-os/webkit'))
                r=self._paket_webkit(d2,arhiv)
                self.assertNotEqual(r.returncode,0)
                self.assertFalse(list(Path(d2).glob('*.deb')))
                arhiv=self._lazni_arhiv(d2,'/usr/lib/safeer-webkit',self.GRADNJA.replace('/usr/lib/safeer-webkit','/usr/lib/safeer-os/webkit'))
                r=self._paket_webkit(d2,arhiv)
                self.assertNotEqual(r.returncode,0)
                self.assertIn('predpona: /usr/lib/safeer-webkit',r.stderr)

    def test_programi_imajo_vgrajen_webkit(self):
        """build_deb.sh in build_os_deb.sh (namizno okolje safeer-os in aplikacija safeer-os-app) s SAFEER_WEBKIT_DEB
        (lastnik, 20. 10. 2026: vsak prenos je ena datoteka): paket je amd64, WebKit iz safeer-webkit iste izdaje nosi v
        /usr/lib/<paket>/webkit-vgrajen, zahteva njegove odvisnosti (peskovnik), ne zahteva paketa safeer-webkit in ne
        WebKitGTK sistema; star loceni safeer-webkit odstrani (Conflicts s stalno mejo), Provides +vgrajen je nad njo.
        postinst ga namesti v /usr/lib/safeer-webkit, postrm ga odstrani z zadnjim programom. Namizno okolje in aplikacija
        se zamenjata (Conflicts + Replaces). safeer-webkit druge izdaje ali drug paket se zavrne; star SAFEER_WEBKIT_TAR
        tudi (tiho bi zgradil paket na WebKitu sistema)."""
        for orodje in ('dpkg-shlibdeps','dpkg-deb','zstd','file'):
            if not shutil.which(orodje):
                self.skipTest('ni %s'%orodje)
        verzija=(ROOT/'packaging/VERSION').read_text().strip()
        deb_verzija=subprocess.run(['bash',str(ROOT/'packaging/deb_razlicica.sh'),verzija],capture_output=True,text=True,
                                   check=True).stdout.strip()
        with tempfile.TemporaryDirectory() as d:
            r=self._paket_webkit(d,self._lazni_arhiv(d))
            self.assertEqual(r.returncode,0,r.stderr[-3000:])
            webkit=r.stdout.strip()
            odvisnost=subprocess.run(['bash',str(self.WEBKIT_DEB/'razlicica_odvisnosti.sh'),webkit],capture_output=True,
                                     text=True,check=True).stdout.strip()
            self.assertEqual(odvisnost,'safeer-webkit (>= %s)'%deb_verzija)
            # Drug paket ali druga razlicica: zavrnjeno.
            drevo=Path(d)/'drugi'
            subprocess.run(['dpkg-deb','-R',webkit,str(drevo)],check=True)
            kontrola=(drevo/'DEBIAN/control').read_text()
            for ime,sprememba in (('druga-razlicica',('Version: %s'%deb_verzija,'Version: 0.0.1')),
                                  ('drug-paket',('Package: safeer-webkit','Package: safeer-drugo'))):
                with self.subTest(ime=ime):
                    (drevo/'DEBIAN/control').write_text(kontrola.replace(*sprememba))
                    tuj=Path(d)/(ime+'.deb')
                    subprocess.run(['dpkg-deb','--build','--root-owner-group',str(drevo),str(tuj)],capture_output=True,check=True)
                    r=subprocess.run(['bash',str(self.WEBKIT_DEB/'razlicica_odvisnosti.sh'),str(tuj)],capture_output=True,text=True)
                    self.assertNotEqual(r.returncode,0)
                    self.assertEqual(r.stdout,'')
            os_v=(ROOT/'packaging/VERSION_OS').read_text().strip()
            for skripta,deb,lib,paket in (('build_deb.sh','safeer-browser_%s_amd64.deb'%verzija,'safeer-browser','safeer-browser'),
                                          ('build_os_deb.sh','safeer-os_%s_amd64.deb'%os_v,'safeer-os','safeer-os'),
                                          ('build_os_deb.sh','safeer-os-app_%s_amd64.deb'%os_v,'safeer-os','safeer-os-app')):
                with self.subTest(paket=paket):
                    deb=ROOT/deb
                    okolje=dict(os.environ,SAFEER_WEBKIT_DEB=webkit,SAFEER_DEB_BREZ_QT='1',SAFEER_OS_PAKET=paket)
                    try:
                        r=subprocess.run(['bash',str(ROOT/skripta)],cwd=ROOT,env=okolje,capture_output=True,text=True)
                        self.assertEqual(r.returncode,0,r.stdout[-2000:]+r.stderr[-2000:])
                        polja=subprocess.run(['dpkg-deb','-f',str(deb),'Package','Architecture','Depends','Provides',
                                              'Conflicts','Replaces'],capture_output=True,text=True,check=True).stdout
                        self.assertIn('Package: %s\n'%paket,polja)
                        self.assertIn('Architecture: amd64',polja)
                        odv=polja.split('Depends: ',1)[1].split('\n',1)[0]
                        self.assertNotRegex(odv,r'(^|, )safeer-webkit\b')
                        for tuje in ('gir1.2-webkit-6.0','gir1.2-soup-3.0','libwebkitgtk','libsoup-3.0'):
                            self.assertNotIn(tuje,odv)
                        for nujno in ('bubblewrap','xdg-dbus-proxy','glib-networking'):
                            self.assertIn(nujno,odv)    # odvisnosti vgrajenega WebKita
                        self.assertIn('safeer-webkit (= %s+vgrajen)'%deb_verzija,polja)
                        self.assertIn('safeer-webkit (<< 1.0.128+vgrajen~)',polja)
                        # Replaces z isto mejo: dpkg -i star safeer-webkit odstrani sam in sele po razpakiranju (pomocnik,
                        # pregled 1.0.129: brez njega »conflicting packages - not installing«).
                        zamenja=polja.split('Replaces: ',1)[1].split('\n',1)[0]
                        self.assertIn('safeer-webkit (<< 1.0.128+vgrajen~)',zamenja)
                        vsebina=subprocess.run(['dpkg-deb','-c',str(deb)],capture_output=True,text=True,check=True).stdout
                        vir='./usr/lib/%s/webkit-vgrajen/'%paket
                        for f in ('share/webkitgtk-safeer/odtis','share/webkitgtk-safeer/razlicica',
                                  'lib/girepository-1.0/WebKit-6.0.typelib','libexec/webkitgtk-6.0/WebKitWebProcess'):
                            self.assertIn(vir+f,vsebina)
                        self.assertIn('./usr/share/doc/%s/safeer-webkit.copyright'%paket,vsebina)
                        self.assertNotIn(' ./usr/lib/safeer-webkit/',vsebina)   # skupna mapa ni datoteka paketa
                        self.assertNotIn('/%s/webkit/'%paket,vsebina)            # ne lastna kopija iz 1.0.127~pred
                        self.assertIn('./usr/lib/%s/core/zasebni_webkit.py'%lib,vsebina)
                        with tempfile.TemporaryDirectory() as k:
                            subprocess.run(['dpkg-deb','-e',str(deb),k],check=True)
                            postinst=(Path(k)/'postinst').read_text()
                            postrm=(Path(k)/'postrm').read_text()
                        self.assertIn('wk_vir=/usr/lib/%s/webkit-vgrajen'%paket,postinst)
                        self.assertIn('cp -al "$wk_vir" "$wk_novo"',postinst)
                        self.assertIn('[ "$wk_p" = "%s" ] && continue'%paket,postrm)
                        self.assertIn('rm -rf /usr/lib/safeer-webkit',postrm)
                        # Ostanki prekinjene namestitve se ne kopicijo (pomocnik, pregled 1.0.129).
                        self.assertIn('rm -rf "$wk_cilj".novo.* "$wk_cilj".staro.*',postinst)
                        self.assertIn('rm -rf /usr/lib/safeer-webkit.novo.* /usr/lib/safeer-webkit.staro.*',postrm)
                        self.assertNotIn('@safeer-webkit',postinst+postrm)
                        if lib=='safeer-os':
                            # Vnos »Safeer OS« (aplikacija v oknu): namizno okolje ga v meniju ne kaze, aplikacija ga.
                            okno=subprocess.run('dpkg-deb --fsys-tarfile "%s" | tar -xO ./usr/share/applications/safeer-os.desktop'%deb,
                                                shell=True,capture_output=True,text=True,check=True).stdout
                            self.assertIn('Exec=/usr/bin/safeer-os --okno',okno)
                            self.assertEqual('\nNoDisplay=true' in okno,paket=='safeer-os')
                        if paket=='safeer-os':
                            self.assertIn('safeer-os-app (= ',polja)
                            self.assertRegex(polja,r'Conflicts: .*\bsafeer-os-app\b')
                            self.assertRegex(polja,r'Replaces: .*\bsafeer-os-app\b')
                            self.assertIn('./usr/bin/safeer-cinnamon',vsebina)
                        if paket=='safeer-os-app':
                            self.assertRegex(polja,r'Conflicts: .*\bsafeer-os\b(?!-)')
                            self.assertRegex(polja,r'Replaces: .*\bsafeer-os\b(?!-)')
                            self.assertNotIn('safeer-cinnamon',vsebina)
                        # Stari nacin (lastna kopija iz arhiva) se zavrne, preden karkoli zgradi.
                        r=subprocess.run(['bash',str(ROOT/skripta)],cwd=ROOT,capture_output=True,text=True,
                                         env=dict(okolje,SAFEER_WEBKIT_TAR='webkit.tar.zst'))
                        self.assertEqual(r.returncode,2)
                        self.assertIn('SAFEER_WEBKIT_TAR ni vec',r.stderr)
                    finally:
                        deb.unlink(missing_ok=True)
                        (ROOT/'SHA256SUMS').unlink(missing_ok=True)
                        (ROOT/'safeer-browser-linux.tar.gz').unlink(missing_ok=True)

    def test_nadgradnja_odstrani_staro_kopijo_webkita(self):
        """dpkg ob posodobitvi s paketa z lastno kopijo (/usr/lib/<paket>/webkit, do 1.0.127~pred) na paket brez nje
        odstrani stare datoteke WebKita in prazne mape; ostane ena kopija v /usr/lib/safeer-webkit. Pravi dpkg v loceni
        korenski mapi (--root), paketi brez skript vzdrzevalca - preizkus ne spremeni racunalnika, na katerem tece."""
        if not shutil.which('dpkg') or not shutil.which('dpkg-deb') or os.geteuid()!=0:
            self.skipTest('ni dpkg ali ni root')
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            koren=d/'koren'
            (koren/'var/lib/dpkg/info').mkdir(parents=True)
            (koren/'var/lib/dpkg/updates').mkdir()
            (koren/'var/lib/dpkg/status').write_text('')
            (koren/'var/lib/dpkg/available').write_text('')

            def paket(ime,razlicica,datoteke,odvisnosti=''):
                drevo=d/('%s-%s'%(ime,razlicica))
                for f in datoteke:
                    (drevo/f).parent.mkdir(parents=True,exist_ok=True)
                    (drevo/f).write_bytes(b'x'*64)
                (drevo/'DEBIAN').mkdir(parents=True)
                (drevo/'DEBIAN/control').write_text('Package: %s\nVersion: %s\nArchitecture: all\nMaintainer: Safeer <info@safeer.si>\n'
                                                    '%sDescription: preizkus\n'%(ime,razlicica,'Depends: %s\n'%odvisnosti if odvisnosti else ''))
                deb=d/('%s_%s.deb'%(ime,razlicica))
                subprocess.run(['dpkg-deb','--build','--root-owner-group',str(drevo),str(deb)],capture_output=True,check=True)
                return str(deb)

            def dpkg(*a):
                return subprocess.run(['dpkg','--root=%s'%koren,'--log=/dev/null','--force-script-chrootless','--force-not-root',*a],
                                      capture_output=True,text=True)
            kopija=['lib/libwebkitgtk-6.0.so.4','lib/girepository-1.0/WebKit-6.0.typelib','libexec/webkitgtk-6.0/WebKitWebProcess']
            stari=[paket('safeer-os','0.4.84',['usr/lib/safeer-os/core/a.py']+['usr/lib/safeer-os/webkit/'+f for f in kopija]),
                   paket('safeer-browser','1.0.126',['usr/lib/safeer-browser/core/a.py']+['usr/lib/safeer-browser/webkit/'+f for f in kopija])]
            r=dpkg('-i',*stari)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertTrue((koren/'usr/lib/safeer-os/webkit/lib/libwebkitgtk-6.0.so.4').is_file())
            novi=[paket('safeer-webkit','1.0.127',['usr/lib/safeer-webkit/'+f for f in kopija]),
                  paket('safeer-os','0.4.85',['usr/lib/safeer-os/core/a.py'],'safeer-webkit (>= 1.0.127)'),
                  paket('safeer-browser','1.0.127',['usr/lib/safeer-browser/core/a.py'],'safeer-webkit (>= 1.0.127)')]
            r=dpkg('-i',*novi)
            self.assertEqual(r.returncode,0,r.stderr)
            for star in ('usr/lib/safeer-os/webkit','usr/lib/safeer-browser/webkit'):
                self.assertFalse((koren/star).exists(),star)
            self.assertTrue((koren/'usr/lib/safeer-os/core/a.py').is_file())
            from core import zasebni_webkit
            for program in ('safeer-os','safeer-browser'):
                self.assertEqual(zasebni_webkit.predpona(str(koren/'usr/lib'/program)),str(koren/'usr/lib/safeer-webkit'))
            # Posodobitev samo enega programa ne odstrani drugega (spodnja meja razlicice, ne natancna).
            r=dpkg('-i',paket('safeer-webkit','1.0.128',['usr/lib/safeer-webkit/'+f for f in kopija]))
            self.assertEqual(r.returncode,0,r.stderr)
            stanje=dpkg('--audit')
            self.assertEqual((stanje.returncode,stanje.stdout),(0,''))
            r=dpkg('-r','safeer-os','safeer-browser','safeer-webkit')
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertFalse((koren/'usr/lib/safeer-webkit').exists())

    def test_namesceni_tovori_na_skupnem_webkitu(self):
        """Tovori Safeer OS, Safeer Control in Safeer Browser, namesceni brez izvorne mape, nalozijo WebKit iz skupne
        predpone <lib>/safeer-webkit: prava (majhna) knjiznica libwebkitgtk-6.0.so.4 in typelib WebKit-6.0 z absolutno
        potjo iz packaging/webkit-deb/typelibi.py - GI jo nalozi namesto WebKitGTK sistema (ta je lahko namescen).
        V istem procesu Node.js, rqbit in Safeer DRM iz paketa ostanejo na svojih mestih, zunanji programi pa poti
        skupnega WebKita ne podedujejo."""
        import sys
        for orodje in ('cc','g-ir-compiler'):
            if not shutil.which(orodje):
                self.skipTest('ni %s'%orodje)
        with tempfile.TemporaryDirectory() as d:
            prefix=Path(d)/'usr'
            for skripta in ('install_os_payload.sh','install_control_payload.sh','install_payload.sh'):
                subprocess.run(['bash',str(ROOT/'packaging'/skripta),str(prefix)],check=True,capture_output=True)
            lib=prefix/'lib'
            wk=lib/'safeer-webkit'
            (wk/'lib').mkdir(parents=True)
            (wk/'share/gir-1.0').mkdir(parents=True)
            (Path(d)/'wk.c').write_text('unsigned int webkit_get_major_version(void) { return 77; }\n')
            subprocess.run(['cc','-shared','-fPIC','-Wl,-soname,libwebkitgtk-6.0.so.4','-o',str(wk/'lib/libwebkitgtk-6.0.so.4'),
                            str(Path(d)/'wk.c')],check=True)
            (wk/'share/gir-1.0/WebKit-6.0.gir').write_text(
                '<?xml version="1.0"?>\n<repository version="1.2" xmlns="http://www.gtk.org/introspection/core/1.0" '
                'xmlns:c="http://www.gtk.org/introspection/c/1.0">\n  <namespace name="WebKit" version="6.0" '
                'shared-library="libwebkitgtk-6.0.so.4" c:identifier-prefixes="WebKit" c:symbol-prefixes="webkit">\n'
                '    <function name="get_major_version" c:identifier="webkit_get_major_version">\n'
                '      <return-value transfer-ownership="none"><type name="guint" c:type="guint"/></return-value>\n'
                '    </function>\n  </namespace>\n</repository>\n')
            r=subprocess.run([sys.executable,str(self.WEBKIT_DEB/'typelibi.py'),str(wk)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn(str(wk/'lib/libwebkitgtk-6.0.so.4'),r.stdout)
            # Programi paketa, ki jih tovor najde sam (lazni, a izvrsljivi).
            for f in ('safeer-os/node/bin/node','safeer-os/rqbit/rqbit','safeer-os/safeer-drm/safeer-drm'):
                (lib/f).parent.mkdir(parents=True,exist_ok=True)
                (lib/f).write_text('#!/bin/sh\nexit 0\n')
                (lib/f).chmod(0o755)
            okolje={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','GI_TYPELIB_PATH','GST_PLUGIN_PATH','FLATPAK_ID',
                                                                  'APPIMAGE','SAFEER_SISTEMSKI_WEBKIT','SAFEER_RQBIT','SAFEER_DRM_MAPA')}
            for program in ('safeer-os','safeer-control','safeer-browser'):
                with self.subTest(program=program):
                    koren=lib/program
                    koda=(f"import sys, os; sys.path.insert(0, {str(koren)!r}); from core import zasebni_webkit as z; "
                          f"p = z.nastavi({str(koren)!r}); import gi; gi.require_version('WebKit', '6.0'); "
                          "from gi.repository import WebKit; v = WebKit.get_major_version(); "
                          "m = sorted({l.split()[-1] for l in open('/proc/self/maps') if 'libwebkitgtk-6.0' in l}); "
                          "print('PREDPONA', p); print('VERZIJA', v); print('KNJIZNICE', m); "
                          "print('ZUNANJI', z.okolje_za_zunanje().get('GI_TYPELIB_PATH', '-'))")
                    if program!='safeer-browser':
                        koda+=("; from core import node_izvajalnik as n, os_torrent as t; print('NODE', n.pot(sistemski=False)); "
                               "print('NODE_OKOLJE', n.okolje().get('GI_TYPELIB_PATH', '-')); print('RQBIT', t.vgrajen_program())")
                    if program=='safeer-os':
                        koda+="; from core import safeer_drm as d; print('DRM', d.izvrsljiva())"
                    r=subprocess.run([sys.executable,'-c',koda],capture_output=True,text=True,cwd=tempfile.gettempdir(),
                                     env=okolje,timeout=60)
                    self.assertEqual(r.returncode,0,r.stderr[-1500:])
                    izpis=dict(v.split(' ',1) for v in r.stdout.splitlines() if ' ' in v)
                    self.assertEqual(izpis['PREDPONA'],str(wk))
                    self.assertEqual(izpis['VERZIJA'],'77')
                    self.assertEqual(izpis['KNJIZNICE'],str([str(wk/'lib/libwebkitgtk-6.0.so.4')]))
                    self.assertEqual(izpis['ZUNANJI'],'-')
                    if program!='safeer-browser':
                        self.assertEqual(izpis['NODE'],str(lib/'safeer-os/node/bin/node'))
                        self.assertEqual(izpis['NODE_OKOLJE'],'-')
                        self.assertEqual(izpis['RQBIT'],str(lib/'safeer-os/rqbit/rqbit'))
                    if program=='safeer-os':
                        self.assertEqual(izpis['DRM'],str(lib/'safeer-os/safeer-drm/safeer-drm'))

    def test_meritev_pomnilnika_webkita(self):
        """tools/webkit_pomnilnik.py (meritev prihranka na testnem PC): vsota Pss knjiznic WebKita po datotekah iz
        /proc/*/smaps; preslikave drugih knjiznic in procesi brez WebKita ne stejejo."""
        import importlib.util
        spec=importlib.util.spec_from_file_location('webkit_pomnilnik',ROOT/'tools/webkit_pomnilnik.py')
        m=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        wk='/usr/lib/safeer-webkit/lib/libwebkitgtk-6.0.so.4.19.4'
        jsc='/usr/lib/safeer-webkit/lib/libjavascriptcoregtk-6.0.so.1.8.8'
        with tempfile.TemporaryDirectory() as d:
            def proces(pid,preslikave):
                (Path(d)/pid).mkdir()
                (Path(d)/pid/'smaps').write_text(''.join(
                    '7f00%04x000-7f00%04x000 r-xp 00000000 08:01 1 %s\nSize: 9 kB\nRss: %d kB\nPss: %d kB\nShared_Clean: 0 kB\n'
                    %(i,i+1,pot,rss,pss) for i,(pot,rss,pss) in enumerate(preslikave)))
            proces('10',[(wk,60000,30000),(jsc,30000,15000),('/usr/lib/x86_64-linux-gnu/libc.so.6',2000,100)])
            proces('11',[(wk,60000,30000),(jsc,30000,15000)])
            proces('12',[('[heap]',500,500)])
            po_datoteki,procesov=m.izmeri(proc=d)
        self.assertEqual(procesov,2)
        self.assertEqual(po_datoteki,{wk:{'Rss':120000,'Pss':60000},jsc:{'Rss':60000,'Pss':30000}})

    def test_ci_gradi_webkit_enkrat_in_preizkusi_oba_programa(self):
        """En posel webkit-deb (brez matrike) zgradi WebKit s PGO in BOLT za /usr/lib/safeer-webkit in paket safeer-webkit;
        brskalnik in safeer-os ga prenesta in vgradita v svoje pakete (od 20. 10. 2026), izdaja ga ne objavi."""
        potek=(ROOT/'.github/workflows/linux-packages.yml').read_text()
        profil=potek.split('\n  webkit-deb-profil:\n',1)[1].split('\n  webkit-deb:\n',1)[0]
        posel=potek.split('\n  webkit-deb:\n',1)[1].split('\n  brskalnik:\n',1)[0]
        self.assertNotIn('matrix',posel)
        self.assertNotIn('matrix',profil)
        self.assertIn('image: ubuntu:24.04',posel)
        # PGO je privzet (lastnik, 15. 10. 2026): lasten ucni tek gradnje noble, profil v predpomnilniku.
        self.assertIn('needs: [webkit-deb-profil, dav1d-deb]',posel)
        self.assertIn('SAFEER_WEBKIT_PGO=ucenje bash packaging/webkit-deb/zgradi.sh /usr/lib/safeer-webkit\n',profil)
        self.assertIn('bash packaging/webkit-deb/ucni_tek.sh /usr/lib/safeer-webkit build/pgo/profraw',profil)
        self.assertIn('SAFEER_WEBKIT_PGO=uporaba SAFEER_WEBKIT_PROFRAW=build/pgo/profraw SAFEER_WEBKIT_BOLT=1',posel)
        self.assertEqual(posel.count('bash packaging/webkit-deb/zgradi.sh '),1)
        self.assertIn('packaging/webkit-deb/zgradi.sh /usr/lib/safeer-webkit build/safeer-webkit.tar.zst',posel)
        for vzorec in ("grep -q '^USE_PGO_PROFILE:BOOL=ON$' gradnja.txt","grep -q '^bolt: da (llvm-bolt 22\\.' gradnja.txt",
                       "grep -q '^build.ninja -fprofile-use: [1-9]' gradnja.txt","grep -qx 'predpona: /usr/lib/safeer-webkit' gradnja.txt"):
            self.assertIn(vzorec,posel)
        for staro in ('zgradi.sh /usr/lib/safeer-os','zgradi.sh /usr/lib/safeer-browser','webkit-deb-safeer-','SAFEER_WEBKIT_TAR',
                      'build/webkit-safeer-'):
            self.assertNotIn(staro,potek)
        # Kljuca predpomnilnika iz vseh datotek gradnje in ucnega teka; brez restore-keys (star WebKit ne sme v paket).
        for datoteka in ('packaging/webkit/webkitgtk6-safeer.yml','packaging/webkit/*.patch','packaging/libsoup/**',
                         'packaging/webkit-deb/zgradi.sh','packaging/webkit-deb/modul.py','packaging/webkit-deb/typelibi.py',
                         'packaging/webkit-deb/odvisnosti.sh','packaging/webkit/pgo_trening.py','packaging/webkit-deb/ucni_tek.sh'):
            # Koncni arhiv (2x) in stanje pred BOLT (2x, nadaljevanje po padcu BOLT, lastnik 19. 10. 2026).
            self.assertEqual(posel.count("'%s'"%datoteka),4,datoteka)
            self.assertEqual(profil.count("'%s'"%datoteka),2,datoteka)
        self.assertNotIn('restore-keys',posel+profil)
        # Paket safeer-webkit iz arhiva (tudi iz predpomnilnika: pakiranje ni v kljucu, traja minute) kot artefakt.
        self.assertLess(posel.index('run: zstd -q -t build/safeer-webkit.tar.zst'),posel.index('bash packaging/webkit-deb/paket.sh'))
        self.assertIn('run: bash packaging/webkit-deb/knjiznice.sh',posel)
        self.assertIn('name: safeer-webkit\n          path: safeer-webkit_*_amd64.deb',posel)
        # Isti Speedometer kot ucni tek Flatpaka.
        self.assertIn('1386415be8fef2f6b6bbdbe1828872471c5d802a',(self.WEBKIT_DEB/'ucni_tek.sh').read_text())
        # Pripeta kopija Flatpaka je od gtk4-integracija v packaging/webkit/pgo.py (vir PGO kot type: file s sha256).
        self.assertIn('1386415be8fef2f6b6bbdbe1828872471c5d802a',(ROOT/'packaging/webkit/pgo.py').read_text())
        # Od 20. 10. 2026 je WebKit vgrajen (lastnik: ena datoteka): brskalnik in safeer-os artefakt safeer-webkit prenesta,
        # WebKit vgradita (Provides +vgrajen), namestita samo svoj paket in preverita eno kopijo na disku.
        for ime,paket,skripta,naslednji in (('brskalnik','safeer-browser','build_deb.sh','safeer-os'),
                                            ('safeer-os','safeer-os','build_os_deb.sh','qt-xcb')):
            with self.subTest(posel=ime):
                del_=potek.split('\n  %s:\n'%ime,1)[1].split('\n  %s:\n'%naslednji,1)[0]
                self.assertRegex(del_,r'needs: \[?webkit-deb\b')
                self.assertIn('name: safeer-webkit\n          path: build/safeer-webkit',del_)
                self.assertNotIn('knjiznice.sh',del_)
                self.assertRegex(del_,r'SAFEER_WEBKIT_DEB="\$WEBKIT" bash %s\n'%skripta)
                self.assertIn('Provides | grep -F "safeer-webkit (= $(dpkg-deb -f "$WEBKIT" Version)+vgrajen)"',del_)
                self.assertIn("::error::",del_)
                self.assertNotIn('Depends | grep -F "safeer-webkit (>=',del_)
                self.assertIn('packaging/smoke_webkit_deb.py /usr/lib/%s'%paket,del_)
                self.assertNotIn('apt-get remove -y %s safeer-webkit'%paket,del_)
                self.assertNotIn('"$WEBKIT" "$OS"',del_)
                self.assertRegex(del_,r'/usr/lib/safeer-webkit[; ]')
                self.assertIn('_amd64.deb',del_)
        os_=potek.split('\n  safeer-os:\n',1)[1].split('\n  qt-xcb:\n',1)[0]
        self.assertIn('SAFEER_OS_PAKET=safeer-os-app ',os_)
        self.assertIn('apt-get install -y --no-install-recommends "$APP"',os_)
        self.assertIn('safeer-os-app_*.deb',os_)
        qt=potek.split('\n  qt-xcb:\n',1)[1].split('\n  mint:\n',1)[0]
        mint=potek.split('\n  mint:\n',1)[1].split('\n  webkit-pgo-profil:\n',1)[0]
        for del_ in (qt,mint):
            self.assertNotIn('name: safeer-webkit',del_)
        for izdaja in ('release','beta-izdaja'):
            del_=potek.split('\n  %s:\n'%izdaja,1)[1].split('\n  beta-izdaja:\n',1)[0]
            self.assertIn('artifacts/safeer-os/safeer-os-app_*_amd64.deb',del_)
            self.assertIn("! -name 'safeer-webkit_*'",del_)
        self.assertIn('/smoke_webkit_deb.py',(ROOT/'tools/mint_namestitev/preizkus.sh').read_text())
        mint_skripta=(ROOT/'tools/mint_namestitev/v_vsebniku.sh').read_text()
        self.assertIn('webkit_preizkus "s sistemskim WebKitGTK',mint_skripta)
        self.assertIn('"$BRSKALNIK" >"$ZACASNO/namestitev.log"',mint_skripta)
        self.assertIn('NAPAKA: po posodobitvi je ostala stara kopija WebKita',mint_skripta)
        # Preizkus WebKita v namescenem paketu zahteva skupno predpono (ne ostanka stare kopije).
        self.assertIn('PREDPONA != "/usr/lib/safeer-webkit"',(ROOT/'packaging/smoke_webkit_deb.py').read_text())

class RqbitPaketTests(unittest.TestCase):
    """Nas rqbit v paketu .deb Safeer OS (packaging/rqbit, lastnik 18. 10. 2026): pripet uradni vir, nas popravek za
    racunalnike brez IPv6, gradnja v CI (posel rqbit-deb) in core/os_torrent.py, ki ga uporabi namesto prenosa."""
    MAPA=ROOT/'packaging/rqbit'

    def _paket(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('rqbit_paket_preizkus',self.MAPA/'rqbit_paket.py')
        modul=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modul)
        return modul

    def test_pin_vira_popravkov_in_motorja(self):
        import hashlib
        import json
        from core import os_torrent
        p=json.loads((self.MAPA/'rqbit.json').read_text())
        # Ista razlicica kot uradni program, ki ga Safeer prenese tam, kjer vgrajenega ni (Windows, Flatpak, AppImage).
        self.assertEqual(p['razlicica'],os_torrent.RQBIT_RAZLICICA)
        self.assertEqual(p['oznaka'],'v'+p['razlicica'])
        self.assertEqual(p['repozitorij'],'https://github.com/ikatson/rqbit.git')
        self.assertRegex(p['commit'],r'^[0-9a-f]{40}$')
        self.assertRegex(p['drevo_sha256'],r'^[0-9a-f]{64}$')
        self.assertEqual((p['cilj'],p['lastnosti'],p['profil']),('x86_64-unknown-linux-musl','rust-tls','release'))
        self.assertRegex(p['rust'],r'^\d+\.\d+\.\d+$')
        self.assertEqual(list(p['popravki']),['ipv4-fallback-without-ipv6.patch'])
        for ime,odtis in p['popravki'].items():
            self.assertEqual(hashlib.sha256((self.MAPA/ime).read_bytes()).hexdigest(),odtis,ime)
        # Vsaka datoteka v packaging/rqbit je v kljucu predpomnilnika CI (hashFiles('packaging/rqbit/**')).
        self.assertEqual(sorted(f.name for f in self.MAPA.iterdir() if f.name!='__pycache__'),
                         ['ipv4-fallback-without-ipv6.patch','rqbit.json','rqbit_paket.py'])

    def test_popravek_za_racunalnike_brez_ipv6(self):
        """Popravek gorvodno: avtor ekipa Safeer, brez oznak orodja; vsa tri mesta, ki vezejo [::], in testi."""
        popravek=(self.MAPA/'ipv4-fallback-without-ipv6.patch').read_text()
        self.assertIn('\nFrom: Safeer <info@safeer.si>\n',popravek)
        self.assertNotRegex(popravek,r'(?i)co-authored-by|claude|generated with')
        for niz in ('fallback_to_ipv4_only_if_no_ipv6(&mut opts, probe_ipv6_socket);',
                    'nix::errno::Errno::EAFNOSUPPORT',
                    'UdpTrackerClient::new(token.clone(), bind_device.as_ref(), opts.ipv4_only)',
                    '+        ipv4_only: bool,\n',
                    '+                request_dualstack: !ipv4_only,',
                    '+            (Ipv4Addr::UNSPECIFIED, LSD_PORT).into()',
                    '+                        ipv4_only: opts.ipv4_only,',
                    'fn test_fallback_to_ipv4_only_if_no_ipv6()',
                    'async fn test_session_starts_with_default_listen_addr()',
                    'async fn test_ipv4_only_binds_ipv4()'):
            self.assertIn(niz,popravek)
        for datoteka in ('crates/librqbit/src/session.rs','crates/tracker_comms/src/tracker_comms_udp.rs',
                         'crates/librqbit_lsd/src/lib.rs','crates/rqbit/src/main.rs'):
            self.assertIn('diff --git a/%s b/%s\n'%(datoteka,datoteka),popravek)

    def test_drevo_sha256(self):
        """Odtis drevesa: neodvisen od gita in arhiva, zazna vsebino, pravice in simbolne povezave, .git na vrhu izpusti."""
        rp=self._paket()
        with tempfile.TemporaryDirectory() as d:
            koren=Path(d)/'vir'
            (koren/'crates/a').mkdir(parents=True)
            (koren/'crates/a/lib.rs').write_text('fn a() {}\n')
            (koren/'README.md').write_text('rqbit\n')
            (koren/'crates/a/README.md').symlink_to('../../README.md')
            (koren/'.git').mkdir()
            (koren/'.git/HEAD').write_text('x\n')
            prvi=rp.drevo_sha256(koren)
            self.assertRegex(prvi,r'^[0-9a-f]{64}$')
            (koren/'.git/HEAD').write_text('y\n')
            self.assertEqual(rp.drevo_sha256(koren),prvi)
            (koren/'crates/a/lib.rs').write_text('fn b() {}\n')
            drugi=rp.drevo_sha256(koren)
            self.assertNotEqual(drugi,prvi)
            os.chmod(koren/'crates/a/lib.rs',0o755)
            self.assertNotEqual(rp.drevo_sha256(koren),drugi)
            os.chmod(koren/'crates/a/lib.rs',0o644)
            (koren/'crates/a/README.md').unlink()
            (koren/'crates/a/README.md').symlink_to('../README.md')
            self.assertNotEqual(rp.drevo_sha256(koren),drugi)

    def _gradnja(self, d, program):
        """Mapa gradnje, kot jo naredi `zgradi` (z danim programom)."""
        import hashlib
        import json
        rp=self._paket()
        p=rp.pin()
        mapa=Path(d)/'rqbit'
        mapa.mkdir()
        shutil.copyfile(program,mapa/'rqbit')
        os.chmod(mapa/'rqbit',0o755)
        for ime in rp.DOKUMENTI:
            (mapa/ime).write_text(ime+'\n')
        for ime in p['popravki']:
            shutil.copyfile(self.MAPA/ime,mapa/ime)
        zapis={k:p[k] for k in ('razlicica','oznaka','commit','drevo_sha256','popravki','rust','cilj','lastnosti','profil')}
        zapis.update(rustc='rustc %s (preizkus)'%p['rust'],program_sha256=hashlib.sha256((mapa/'rqbit').read_bytes()).hexdigest(),
                     velikost=(mapa/'rqbit').stat().st_size,staticen=True)
        (mapa/'gradnja.json').write_text(json.dumps(zapis))
        return rp,mapa

    def test_preveri_zavrne_tujo_ali_staro_gradnjo(self):
        import json
        if not shutil.which('readelf'):
            self.skipTest('ni readelf (binutils)')
        with tempfile.TemporaryDirectory() as d:
            rp,mapa=self._gradnja(d,shutil.which('true'))
            # Dinamicno povezan program (/bin/true) ni nasa staticna gradnja.
            with self.assertRaisesRegex(SystemExit,'ni staticen'):
                rp.preveri(mapa)
            # Zamenjan program: SHA-256 ni zapisani.
            with open(mapa/'rqbit','ab') as f:
                f.write(b'x')
            with self.assertRaisesRegex(SystemExit,'SHA-256'):
                rp.preveri(mapa)
            # Gradnja iz drugega vira (stara v predpomnilniku): ne gre v paket.
            zapis=json.loads((mapa/'gradnja.json').read_text())
            zapis['commit']='0'*40
            (mapa/'gradnja.json').write_text(json.dumps(zapis))
            with self.assertRaisesRegex(SystemExit,'commit'):
                rp.preveri(mapa)

    def test_namesti_v_paket(self):
        """Staticen program, ki se predstavi kot prava razlicica: namesti v lib/<paket>/rqbit, obvestila v share/doc."""
        cc=shutil.which('cc') or shutil.which('gcc')
        if not cc or not shutil.which('readelf'):
            self.skipTest('ni prevajalnika C ali readelf')
        import platform
        if platform.machine() not in ('x86_64','amd64'):
            self.skipTest('preverba razlicice tece samo na x86_64')
        rp=self._paket()
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'r.c').write_text('#include <stdio.h>\nint main(void){puts("rqbit %s");return 0;}\n'%rp.pin()['razlicica'])
            r=subprocess.run([cc,'-static','-O1','-o',str(Path(d)/'r'),str(Path(d)/'r.c')],capture_output=True,text=True)
            if r.returncode:
                self.skipTest('ni staticne libc: '+r.stderr[-200:])
            rp,mapa=self._gradnja(d,Path(d)/'r')
            rp.preveri(mapa)
            koren=Path(d)/'deb'
            rp.namesti(mapa,koren/'usr','safeer-os')
            program=koren/'usr/lib/safeer-os/rqbit/rqbit'
            self.assertEqual(program.stat().st_mode & 0o777,0o755)
            for ime in ('LICENSE','OBVESTILO.txt','LICENSES-THIRD-PARTY.txt','gradnja.json','ipv4-fallback-without-ipv6.patch'):
                self.assertEqual((koren/'usr/share/doc/safeer-os/rqbit'/ime).stat().st_mode & 0o777,0o644,ime)
            # core/os_torrent.py v tem tovoru najde vgrajenega (Safeer Control prek sosednje mape safeer-os).
            from core import os_torrent as ot
            (koren/'usr/lib/safeer-control').mkdir(parents=True)
            with patch.dict(os.environ,{ot.SPREMENLJIVKA_VGRAJENEGA:''}):
                for tovor in ('safeer-os','safeer-control'):
                    with patch.object(ot,'_tovor',lambda t=tovor: str(koren/'usr/lib'/t)):
                        self.assertEqual(ot.pot_programa(),str(program))

    def test_deb_vgradi_rqbit_iz_posla_ci(self):
        deb=(ROOT/'build_os_deb.sh').read_text()
        self.assertIn('python3 "$DIR/packaging/rqbit/rqbit_paket.py" namesti "$SAFEER_RQBIT_TOVOR" "$BUILD_ROOT/usr" "$PKG_NAME"',deb)
        self.assertIn('[ -n "${SAFEER_RQBIT_TOVOR:-}" ] ||',deb.split('then ARCH="amd64"',1)[0].rsplit('\n',1)[1])
        potek=(ROOT/'.github/workflows/linux-packages.yml').read_text()
        posel=potek.split('\n  rqbit-deb:\n',1)[1].split('\n  brskalnik:\n',1)[0]
        self.assertIn('runs-on: ubuntu-24.04',posel)
        self.assertIn('musl-tools python3-seccomp',posel)
        self.assertEqual(posel.count("key: rqbit-deb-${{ hashFiles('packaging/rqbit/**') }}"),2)
        self.assertIn("if: steps.rqbit.outputs.cache-hit != 'true'\n        run: python3 packaging/rqbit/rqbit_paket.py zgradi build/rqbit",posel)
        # Preverba in prenos brez IPv6 tudi, ko je program iz predpomnilnika.
        korak=posel.split('- name: Check the build and download a torrent without IPv6',1)[1].split('\n      - ',1)[0]
        self.assertNotIn('if:',korak)
        self.assertIn('rqbit_paket.py preveri build/rqbit',korak)
        self.assertIn('rqbit_paket.py dim build/rqbit/rqbit --brez-ipv6',korak)
        self.assertIn('name: rqbit-deb\n          path: build/rqbit/',posel)
        os_=potek.split('\n  safeer-os:\n',1)[1].split('\n  qt-xcb:\n',1)[0]
        self.assertIn('name: rqbit-deb\n          path: build/rqbit',os_)
        self.assertLess(os_.index('chmod 755 build/rqbit/rqbit'),os_.index('SAFEER_RQBIT_TOVOR="$PWD/build/rqbit"'))
        self.assertIn("./usr/lib/safeer-os/rqbit/rqbit$'",os_)
        self.assertIn("grep -F './usr/share/doc/safeer-os/rqbit/LICENSES-THIRD-PARTY.txt'",os_)
        self.assertIn('sha256sum -c -',os_)
        self.assertIn("assert p == '/usr/lib/safeer-os/rqbit/rqbit', p",os_)
        # Kljuci predpomnilnika WebKita ostanejo nedotaknjeni (gradnja 2-3 h): rqbit ni v njih.
        for kljuc in re.findall(r'key: (webkit-[^\n]*)',potek):
            self.assertNotIn('rqbit',kljuc)

    def test_flatpak_in_appimage_imata_nas_rqbit(self):
        """Napaka brez IPv6 ne ostane v nobenem paketu za Linux: Flatpak in AppImage Safeer OS nosita isti preverjen program
        kot .deb (artefakt posla rqbit-deb). Safeer Browser magnetov nima in rqbita ne nosi."""
        try:
            import yaml
        except ImportError:
            self.skipTest('python3-yaml ni namescen')
        m=yaml.safe_load((ROOT/'io.github.memelandfaner.SafeerOS.yml').read_text())
        modul=next(x for x in m['modules'] if isinstance(x,dict) and x.get('name')=='safeer-os')
        self.assertIn({'type':'dir','path':'build/rqbit','dest':'rqbit-tovor'},modul['sources'])
        ukazi=modul['build-commands']
        namesti='python3 packaging/rqbit/rqbit_paket.py namesti rqbit-tovor /app safeer-os'
        self.assertLess(ukazi.index('chmod 755 rqbit-tovor/rqbit'),ukazi.index(namesti))
        self.assertLess(next(i for i,u in enumerate(ukazi) if 'install_os_payload.sh /app' in u),ukazi.index(namesti))
        # Glavni vir (.) izpusti build/: rqbit pride samo iz svojega vira.
        self.assertIn('build',next(x for x in modul['sources'] if x.get('path')=='.')['skip'])
        self.assertNotIn('rqbit',(ROOT/'io.github.memelandfaner.SafeerBrowser.yml').read_text())
        self.assertNotIn('os_torrent',(ROOT/'packaging/install_payload.sh').read_text())
        flatpak=(ROOT/'packaging/build_os_flatpak.sh').read_text()
        self.assertLess(flatpak.index('[ ! -f build/rqbit/gradnja.json ]'),flatpak.index('"$BUILDER"'))
        potek=(ROOT/'.github/workflows/linux-packages.yml').read_text()
        posel=potek.split('\n  flatpak:\n',1)[1].split('\n  flatpak-brskalnik:\n',1)[0]
        self.assertIn('name: rqbit-deb\n          path: build/rqbit',posel)
        self.assertLess(posel.index('python3 packaging/rqbit/rqbit_paket.py preveri build/rqbit'),
                        posel.index('python3 packaging/webkit/pgo.py uporaba'))
        self.assertIn("files/lib/safeer-os/rqbit/rqbit\"\n",posel)
        self.assertIn('for koren in /app/lib/safeer-os /app/lib/safeer-control; do',posel)
        self.assertIn("assert p == '/app/lib/safeer-os/rqbit/rqbit' and t.program_na_voljo(), p",posel)
        # AppImage: izven usr/ (pred linuxdeploy), v CI obvezen, AppRun-os poda pot.
        appimage=(ROOT/'packaging/build_os_appimage.sh').read_text()
        self.assertIn('python3 packaging/rqbit/rqbit_paket.py namesti "$SAFEER_RQBIT_TOVOR" "$APPDIR/usr" safeer-os',appimage)
        self.assertLess(appimage.index('mv "$APPDIR/usr/lib/safeer-os/rqbit" "$APPDIR/opt/rqbit"'),appimage.index('"$LINUXDEPLOY"'))
        self.assertIn('elif [ -n "${CI:-}" ]; then\n    echo "manjka SAFEER_RQBIT_TOVOR',appimage)
        self.assertIn('export SAFEER_RQBIT="$APPDIR/opt/rqbit/rqbit"',(ROOT/'packaging/AppRun-os').read_text())
        os_=potek.split('\n  safeer-os:\n',1)[1].split('\n  qt-xcb:\n',1)[0]
        vrstica=next(v for v in os_.splitlines() if v.rstrip().endswith('bash packaging/build_os_appimage.sh'))
        self.assertIn('SAFEER_RQBIT_TOVOR="$PWD/build/rqbit"',vrstica)
        self.assertIn('RQ=build/os-appimage-x/squashfs-root/opt/rqbit/rqbit',os_)
        self.assertIn("grep -F 'export SAFEER_RQBIT=\"$APPDIR/opt/rqbit/rqbit\"' build/os-appimage-x/squashfs-root/AppRun",os_)
        # Kot jo postavi Flatpak (predpona /app): core najde program iz Safeer OS in Safeer Control.
        cc=shutil.which('cc') or shutil.which('gcc')
        import platform
        if not cc or not shutil.which('readelf') or platform.machine() not in ('x86_64','amd64'):
            return
        rp=self._paket()
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'r.c').write_text('#include <stdio.h>\nint main(void){puts("rqbit %s");return 0;}\n'%rp.pin()['razlicica'])
            if subprocess.run([cc,'-static','-o',str(Path(d)/'r'),str(Path(d)/'r.c')],capture_output=True).returncode:
                return
            rp,mapa=self._gradnja(d,Path(d)/'r')
            app=Path(d)/'app'
            rp.namesti(mapa,app,'safeer-os')
            (app/'lib/safeer-control').mkdir(parents=True)
            from core import os_torrent as ot
            with patch.dict(os.environ,{ot.SPREMENLJIVKA_VGRAJENEGA:''}):
                for tovor in ('safeer-os','safeer-control'):
                    with patch.object(ot,'_tovor',lambda t=tovor: str(app/'lib'/t)):
                        self.assertEqual(ot.pot_programa(),str(app/'lib/safeer-os/rqbit/rqbit'))
            self.assertTrue((app/'share/doc/safeer-os/rqbit/LICENSES-THIRD-PARTY.txt').is_file())


class MintInstallTests(unittest.TestCase):
    """Posel `mint` v CI (tools/mint_namestitev): paketi .deb se namestijo, zazenejo in odstranijo na Linux Mintu."""
    MAPA=ROOT/'tools/mint_namestitev'

    def test_scripts_parse(self):
        for ime in ('preizkus.sh','v_vsebniku.sh'):
            with self.subTest(skripta=ime):
                subprocess.run(['bash','-n',str(self.MAPA/ime)],check=True)

    def test_every_deb_we_build_is_installed_and_removed_on_mint(self):
        """Nov paket .deb ne sme mimo preizkusa: vsak `Package:` iz skript build_*deb.sh mora biti v njem."""
        zgrajeni=set()
        for skripta in ROOT.glob('build_*deb.sh'):
            besedilo=skripta.read_text()
            imena=set(re.findall(r'^Package: (\S+)$',besedilo,re.M))
            if '${PKG_NAME}' in imena:      # build_os_deb.sh: namizno okolje in aplikacija (SAFEER_OS_PAKET)
                imena.discard('${PKG_NAME}')
                imena|=set(re.search(r'\n    (safeer-os\) NAMIZJE=1 ;;\n    safeer-os-app)\) NAMIZJE=0 ;;',besedilo).group(1)
                           .replace(') NAMIZJE=1 ;;\n    ',' ').split())
            zgrajeni|=imena
        self.assertEqual(zgrajeni,{'safeer-browser','safeer-os','safeer-os-app'})
        # safeer-webkit je od 20. 10. 2026 vgrajen v programe: preizkus ga ne namesti posebej in preveri, da ga ni.
        preizkus=(self.MAPA/'v_vsebniku.sh').read_text()
        self.assertNotIn("paket 'safeer-webkit_",preizkus)
        self.assertIn('NAPAKA: star paket safeer-webkit je se namescen',preizkus)
        self.assertIn('NAPAKA: namizno okolje je WebKit namestilo ponovno',preizkus)
        odstranjeni=set(re.search(r'apt-get remove ([^>\n]*)',preizkus).group(1).split())
        for paket in sorted(zgrajeni):
            with self.subTest(paket=paket):
                # Od 15. 10. 2026 sta paketa amd64 (nas WebKitGTK, packaging/webkit-deb).
                self.assertRegex(preizkus,r"paket '%s_\*_(all|amd64)\.deb'"%re.escape(paket))
                if paket=='safeer-os':
                    # Namizno okolje odstrani namestitev aplikacije (Conflicts + Replaces), preizkus to preveri.
                    self.assertIn('NAPAKA: namizno okolje je ostalo ob aplikaciji',preizkus)
                else:
                    self.assertIn(paket,odstranjeni)

    def test_release_waits_for_the_mint_job(self):
        """Izdaja (posel release) ne sme nastati, ce namestitev na Linux Mintu pade."""
        potek=(ROOT/'.github/workflows/linux-packages.yml').read_text()
        self.assertIn('\n  mint:\n',potek)
        self.assertIn('tools/mint_namestitev/preizkus.sh',potek)
        izdaja=potek.split('\n  release:\n',1)[1]
        potrebe=re.search(r'^    needs: \[([^\]]+)\]$',izdaja,re.M)
        self.assertIsNotNone(potrebe)
        self.assertIn('mint',[p.strip() for p in potrebe.group(1).split(',')])


class CiPregledTests(unittest.TestCase):
    """Pregled CI 18. 10. 2026: profil PGO samo iz zaupanja vrednega teka, pogoji v korakih res ustavijo korak, test
    nadgradnje se ne preskoci tiho, prirezan arhiv WebKita ne gre v predpomnilnik, lokalna gradnja ne izbrise
    namescenega WebKita, gstreamer1.0-plugins-good je odvisnost."""
    POTEK=ROOT/'.github/workflows/linux-packages.yml'

    def _korak(self, posel, ime, potek=None):
        try:
            import yaml
        except ImportError:
            self.skipTest('python3-yaml ni namescen')
        wf=yaml.safe_load((potek or self.POTEK).read_text())
        for k in wf['jobs'][posel]['steps']:
            if k.get('name')==ime:
                return k
        self.fail('ni koraka %s / %s'%(posel,ime))

    def _gh(self, d, podatki):
        """Lazni gh: `api POT --jq IZRAZ` vrne podatki[POT] skozi pravi jq; `release download OZNAKA … --dir D`."""
        if not shutil.which('jq'):
            self.skipTest('jq ni namescen')
        import json
        (Path(d)/'podatki.json').write_text(json.dumps(podatki))
        gh=Path(d)/'bin/gh'
        gh.parent.mkdir()
        gh.write_text('''#!/usr/bin/env python3
import json, os, subprocess, sys
p = json.load(open(os.path.join(os.path.dirname(__file__), "..", "podatki.json")))
a = sys.argv[1:]
if a[0] == "api":
    v = p.get(a[1])
    if v is None:
        sys.exit("HTTP 500")
    izraz = a[a.index("--jq") + 1]
    sys.exit(subprocess.run(["jq", "-r", izraz], input=json.dumps(v), text=True).returncode)
if a[:2] == ["release", "download"]:
    if p.get("prenos:" + a[2]) != "ok":
        sys.exit("prenos ni uspel")
    d = a[a.index("--dir") + 1]
    open(os.path.join(d, "safeer-os_1.0_amd64.deb"), "w").close()
    sys.exit(0)
sys.exit("neznan ukaz")
''')
        gh.chmod(0o755)
        return str(gh.parent)

    def _pozeni(self, d, skripta, okolje):
        izhod=Path(d)/'izhod'
        izhod.write_text('')
        env=dict(os.environ,GITHUB_REPOSITORY='lastnik/repo',GITHUB_OUTPUT=str(izhod),GH_TOKEN='x',**okolje)
        r=subprocess.run(['bash','-e','-c',skripta],cwd=d,env=env,capture_output=True,text=True)
        return r.returncode,dict(v.split('=',1) for v in izhod.read_text().splitlines() if '=' in v),r.stdout+r.stderr

    def test_profil_pgo_samo_iz_zaupanja_vrednega_teka(self):
        skripta=self._korak('webkit-pgo-profil','Profile with this key (artifact of an earlier trusted run)')['run']
        artefakti=lambda *teki: {'artifacts':[{'expired':t==1,'created_at':'2026-10-1%dT10:00:00Z'%t,'workflow_run':{'id':t}}
                                             for t in teki]}
        runs=lambda t,dogodek,repo,veja: {'event':dogodek,'head_repository':{'id':repo},'head_branch':veja}
        osnova={'repos/lastnik/repo/actions/runs/1':runs(1,'push',42,'main'),
                'repos/lastnik/repo/actions/runs/2':runs(2,'push',42,'nova-funkcija'),
                'repos/lastnik/repo/actions/runs/3':runs(3,'pull_request',999,'main'),
                'repos/lastnik/repo/actions/runs/4':runs(4,'push',42,'gtk4-deb-webkit'),
                'repos/lastnik/repo/actions/runs/5':runs(5,'pull_request',42,'main')}
        ime='repos/lastnik/repo/actions/artifacts?name=webkit-pgo-profraw-K&per_page=100'
        primeri=[  # (teki z artefaktom, izdaja, izbran tek, pricakovana koda, pricakovan run_id)
            ((1,2,3),'false','',0,'2'),      # fork PR (3) in iztekel (1) izpuscena; veja istega repozitorija je OK
            ((1,2,3),'true','',0,None),      # izdaja: veja nova-funkcija ni dovoljena -> ucni tek v tem teku
            ((2,3,4,5),'true','',0,'4'),     # izdaja: najnovejsi zaupanja vreden (5 je pull_request)
            ((2,3,4),'false','3',1,None),    # izrecno izbran tek iz forka: napaka, ne tiho
            ((2,3,4),'true','2',1,None),     # izrecno izbran tek z druge veje pri izdaji: napaka
            ((2,3,4),'false','4',0,'4'),
        ]
        for teki,izdaja,tek,koda,run_id in primeri:
            with self.subTest(teki=teki,izdaja=izdaja,tek=tek), tempfile.TemporaryDirectory() as d:
                pot=self._gh(d,dict(osnova,**{ime:artefakti(*teki)}))
                k,izhod,izpis=self._pozeni(d,skripta,{'PATH':pot+os.pathsep+os.environ['PATH'],'KLJUC':'K','NOV':'',
                                                     'TEK':tek,'REPO_ID':'42','IZDAJA':izdaja})
                self.assertEqual(k,koda,izpis)
                self.assertEqual(izhod.get('run_id'),run_id,izpis)
        with tempfile.TemporaryDirectory() as d:   # napaka API ustavi korak (ne tiho ucni tek)
            pot=self._gh(d,osnova)
            k,_i,izpis=self._pozeni(d,skripta,{'PATH':pot+os.pathsep+os.environ['PATH'],'KLJUC':'K','NOV':'','TEK':'',
                                              'REPO_ID':'42','IZDAJA':'true'})
            self.assertNotEqual(k,0,izpis)

    def test_nadgradnja_ni_tiho_preskocena(self):
        skripta=self._korak('mint','Packages of the last published release (for the upgrade test)')['run']
        self.assertNotIn('|| echo',skripta)
        izdaje='repos/lastnik/repo/releases?per_page=100'
        zadnja='repos/lastnik/repo/releases/latest'
        objavljena=[{'draft':False,'prerelease':False,'tag_name':'v1.0.9'}]
        primeri=[  # (podatki, izdaja, koda, .deb prenesen, opozorilo)
            ({izdaje:[]},'true',0,False,'::warning::'),
            ({izdaje:[{'draft':True,'prerelease':False,'tag_name':'v2'}]},'false',0,False,'::notice::'),
            ({izdaje:objavljena,zadnja:{'tag_name':'v1.0.9'},'prenos:v1.0.9':'ok'},'true',0,True,'Upgrade test from v1.0.9'),
            ({izdaje:objavljena,zadnja:{'tag_name':'v1.0.9'}},'true',1,False,''),   # prenos pade: korak pade
            ({},'true',1,False,''),                                                 # API pade: korak pade
        ]
        for podatki,izdaja,koda,deb,besedilo in primeri:
            with self.subTest(podatki=sorted(podatki),izdaja=izdaja), tempfile.TemporaryDirectory() as d:
                pot=self._gh(d,podatki)
                k,_i,izpis=self._pozeni(d,skripta,{'PATH':pot+os.pathsep+os.environ['PATH'],'IZDAJA':izdaja})
                self.assertEqual(k!=0,koda!=0,izpis)
                self.assertEqual(any(Path(d,'prejsnji').glob('*.deb')),deb,izpis)
                self.assertIn(besedilo,izpis)

    def test_pogoji_v_korakih_ustavijo_korak(self):
        """bash -e ne ustavi koraka, ce pade ukaz pred zadnjim && - vsak pogoj mora biti svoj ukaz (ali z || exit)."""
        try:
            import yaml
        except ImportError:
            self.skipTest('python3-yaml ni namescen')
        def ocisti(v):
            v=re.sub(r"'[^']*'|\"(?:\\.|[^\"\\])*\"",'Q',v)
            prej=None
            while prej!=v:
                prej,v=v,re.sub(r'\([^()]*\)','P',v)
            return re.sub(r'\[\[.*?\]\]','T',v)
        napake=[]
        for potek in sorted((ROOT/'.github/workflows').glob('*.yml')):
            for posel,j in yaml.safe_load(potek.read_text())['jobs'].items():
                for k in j.get('steps',[]):
                    for v in (k.get('run') or '').replace('\\\n',' ').splitlines():
                        v=v.strip()
                        c=ocisti(v)
                        if (v and not v.startswith('#') and ' && ' in c and '||' not in c
                                and not re.match(r'(if|elif|while|until)\b',c)):
                            napake.append('%s/%s/%s: %s'%(potek.name,posel,k.get('name'),v))
        self.assertEqual(napake,[])
        self.assertTrue(ocisti("a && b").count('&&'))   # varovalo: vzorec res najde verigo

    def test_arhiv_webkita_preverjen_pred_predpomnilnikom(self):
        wf=self.POTEK.read_text()
        posel=wf.split('\n  webkit-deb:\n',1)[1].split('\n  dav1d-deb:\n',1)[0]
        preveri=posel.index('run: zstd -q -t build/safeer-webkit.tar.zst')
        shrani=posel.index('- name: Save our WebKitGTK')
        self.assertLess(preveri,shrani)
        self.assertIn("if: success() && steps.wk.outputs.cache-hit != 'true'\n",posel[shrani:])
        # always() samo za stanje pred BOLT (nadaljevanje po padcu BOLT): bolt.sh ga zapise pod koncnim imenom sele po
        # zstd -t, zato prirezan arhiv ne pride v predpomnilnik.
        self.assertEqual(posel.count('if: always()'),1)
        self.assertIn("if: always() && steps.wk.outputs.cache-hit != 'true' && steps.predbolt.outputs.cache-hit != 'true'"
                      " && hashFiles('build/webkit-predbolt.tar.zst') != ''",posel)
        bolt=(ROOT/'packaging/webkit-deb/bolt.sh').read_text()
        self.assertLess(bolt.index('-cf "$ARHIV.del"'),bolt.index('zstd -q -t "$ARHIV.del" && mv "$ARHIV.del" "$ARHIV"'))
        zgradi=(ROOT/'packaging/webkit-deb/zgradi.sh').read_text()
        kos=zgradi.split('if [ -n "$IZHOD" ]; then',1)[1]
        self.assertLess(kos.index('-cf "$IZHOD.del"'),kos.index('zstd -q -t "$IZHOD.del"'))
        self.assertLess(kos.index('zstd -q -t "$IZHOD.del"'),kos.index('mv "$IZHOD.del" "$IZHOD"'))

    def test_lokalna_gradnja_ne_izbrise_namescenega_webkita(self):
        """zgradi.sh zavrne predpono, ki jo ima namescen paket (dpkg -S), preden karkoli izbrise. V PATH sta samo
        lazni dpkg in nujna orodja: ce bi preverba manjkala, skripta pade (ni nproc) pred rm -rf."""
        with tempfile.TemporaryDirectory() as d:
            for orodje in ('dirname','basename','cat'):
                os.symlink(shutil.which(orodje),os.path.join(d,orodje))
            Path(d,'dpkg').write_text('#!/bin/sh\n[ "$1" = -S ] && echo "safeer-webkit: $2" && exit 0\nexit 1\n')
            os.chmod(os.path.join(d,'dpkg'),0o755)
            r=subprocess.run(['/bin/bash',str(ROOT/'packaging/webkit-deb/zgradi.sh'),'/usr/lib/safeer-webkit'],
                             env={'PATH':d},capture_output=True,text=True)
            self.assertEqual(r.returncode,3,r.stderr)
            self.assertIn('pripada namescenemu paketu (safeer-webkit)',r.stderr)
            self.assertIn('docker run --rm',r.stderr)
            self.assertIn('build/safeer-webkit.tar.zst',r.stderr)

    def test_libsoup_s_popravkom_puscanja_connect(self):
        """Nas popravek libsoup (Launchpad #2170998): CONNECT skozi posrednik (DoH v Spletu) ne pusca SoupConnection.
        Isti modul gradita .deb (zgradi.sh) in Flatpak."""
        modul=(ROOT/'packaging/libsoup/libsoup3-safeer.yml').read_text()
        self.assertIn('path: soup-cookie-jar-connect-leak.patch',modul)
        popravek=(ROOT/'packaging/libsoup/soup-cookie-jar-connect-leak.patch').read_text()
        self.assertIn('+        g_clear_object (&conn);',popravek)
        for manifest in ('io.github.memelandfaner.SafeerOS.yml','io.github.memelandfaner.SafeerBrowser.yml'):
            self.assertIn('packaging/libsoup/libsoup3-safeer.yml',(ROOT/manifest).read_text())

    def test_plugins_good_je_odvisnost(self):
        """qtdemux, matroskademux in vpx so v gstreamer1.0-plugins-good; GDebi ne namesti priporocil."""
        os_=(ROOT/'build_os_deb.sh').read_text()
        odvisnosti=re.search(r'^Depends: (.*)$',os_,re.M).group(1)
        priporocila=re.search(r'^Recommends: (.*)$',os_,re.M).group(1)
        self.assertIn('gstreamer1.0-plugins-good',odvisnosti)
        self.assertNotIn('gstreamer1.0-plugins-good',priporocila)
        brskalnik=(ROOT/'build_deb.sh').read_text()
        gtk4=[v for v in re.findall(r'^\s*ODVISNOSTI="(.*)"$',brskalnik,re.M) if 'gir1.2-gtk-4.0' in v]
        self.assertEqual(len(gtk4),2)      # paket izdaje (nas WebKit) in lokalna gradnja (sistemski WebKit)
        for vrstica in gtk4:
            self.assertIn('gstreamer1.0-plugins-good',vrstica)


def test_aplikacija_ne_izklopi_cinnamona_ob_odstranitvi():
    """Neodvisni pregled OpenAI 1.0.129: safeer-os-app je dobil isti prerm/postrm kot namizno okolje - odstranitev
    aplikacije bi izklopila videz Safeer Cinnamon (od ločenega paketa), purge pa pobrisal njegovo stanje. Cinnamonov
    del velja samo za paket safeer-os (dpkg poda ime v DPKG_MAINTSCRIPT_PACKAGE)."""
    import re
    from pathlib import Path
    s = (Path(__file__).resolve().parents[1] / "build_os_deb.sh").read_text(encoding="utf-8")
    pogoj = '[ "${DPKG_MAINTSCRIPT_PACKAGE:-safeer-os}" = "safeer-os" ]'
    izklop = re.search(r'^if \[ "\$\{1:-\}" = "remove" \].*safeer-cinnamon.*then$', s, re.M)
    assert izklop and pogoj in izklop.group(0), "izklop videza ni omejen na safeer-os"
    brisanje = re.search(r"^if .*purge.*rm -rf /var/lib/safeer-cinnamon.*$", s, re.M)
    assert brisanje and pogoj in brisanje.group(0), "brisanje stanja Cinnamona ni omejeno na safeer-os"
