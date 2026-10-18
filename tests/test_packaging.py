import os
import re
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest
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
                        'safeer_mint.py','README.md','PACKAGING.md','io.github.memelandfaner.SafeerBrowser.metainfo.xml',
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
        # Od 14. 10. 2026 je brskalnik v paketih GTK4 (safeer_brskalnik.py); SAFEER_BRSKALNIK_GTK3=1 zgradi prejsnjega.
        for gtk3,vstop in ((False,'safeer_brskalnik.py'),(True,'safeer_mint.py')):
            with self.subTest(vstop=vstop), tempfile.TemporaryDirectory(prefix='safeer package ') as directory:
                prefix=Path(directory)/'usr'
                okolje={**os.environ,'SAFEER_BRSKALNIK_GTK3':'1' if gtk3 else '0'}
                subprocess.run(['bash',str(ROOT/'packaging/install_payload.sh'),str(prefix)],check=True,env=okolje)
                fake=Path(directory)/'python'
                fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
                fake.chmod(0o755)
                output=subprocess.check_output([str(prefix/'bin/safeer-browser'),'https://example.com/a b'],env={**os.environ,'PYTHON':str(fake)},text=True).splitlines()
                self.assertEqual(output,[str(prefix/'lib/safeer-browser'/vstop),'https://example.com/a b'])
                drugi='safeer_mint.py' if vstop=='safeer_brskalnik.py' else 'safeer_brskalnik.py'
                self.assertFalse((prefix/'lib/safeer-browser'/drugi).exists(),drugi)
                subprocess.run(['desktop-file-validate',str(prefix/'share/applications/safeer-browser.desktop')],check=True)

    def test_browser_payload_can_actually_start(self):
        """Namesceni GTK4 brskalnik se zazene brez izvorne mape: --version prek zaganjalnika (razlicica iz
        packaging/VERSION v tovoru) in uvoz modulov, ki jih Splet nalozi lenobno (zgodovina, uvoz zavihkov, Safeer DRM)."""
        import sys
        with tempfile.TemporaryDirectory() as directory:
            prefix=Path(directory)/'usr'
            subprocess.run(['bash',str(ROOT/'packaging/install_payload.sh'),str(prefix)],check=True)
            lib=prefix/'lib/safeer-browser'
            environment={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','SAFEER_BRSKALNIK_GTK3')}
            verzija=(ROOT/'packaging/VERSION').read_text().strip()
            result=subprocess.run([str(prefix/'bin/safeer'),'--version'],capture_output=True,text=True,
                                  cwd=tempfile.gettempdir(),env={**environment,'PYTHON':sys.executable})
            self.assertEqual(result.returncode,0,result.stderr[-800:])
            self.assertEqual(result.stdout.strip(),'Safeer Browser '+verzija)
            code=(f"import sys; sys.path.insert(0, {str(lib)!r}); import safeer_brskalnik; "
                  "from core import os_splet, safeer_drm, zgodovina, uvoz_zavihkov, bookmarks_importer, splet_prenosi; "
                  "print(safeer_brskalnik.APP_ID, safeer_drm.vir_logike())")
            result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,
                                  cwd=tempfile.gettempdir(),env=environment)
            self.assertEqual(result.returncode,0,result.stderr[-800:])
            self.assertIn('io.github.memelandfaner.SafeerBrowser',result.stdout)
            # Safeer DRM: logika predvajalnika (main.js) pride s tovorom, paket ECS se prenese ob prvi potrebi.
            self.assertTrue((lib/'assets/safeer_drm/main.js').is_file())
            self.assertIn(str(lib/'assets/safeer_drm'),result.stdout)
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
                        self.assertTrue(os.path.isabs(p) and os.path.exists(p),p)
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
    zasebna predpona /usr/lib/<paket>/webkit, Python nalozi typelibe iz nje pred `import gi`."""
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
                        '-DCMAKE_AR=/usr/lib/llvm-22/bin/llvm-ar'):
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
        self.assertIn('/usr/lib/safeer-*/webkit)',zgradi)
        odvisnosti=(self.WEBKIT_DEB/'odvisnosti.sh').read_text()
        self.assertIn('llvm-toolchain-${VERSION_CODENAME:-noble}-22',odvisnosti)
        for paket in ('clang-22','lld-22','libclang-rt-22-dev','libgtk-4-dev','gettext','bubblewrap','xdg-dbus-proxy'):
            self.assertIn(paket,odvisnosti)
        for skripta in ('zgradi.sh','odvisnosti.sh','vgradi.sh','ucni_tek.sh'):
            subprocess.run(['bash','-n',str(self.WEBKIT_DEB/skripta)],check=True)

    def test_typelib_dobi_absolutno_pot_do_nase_knjiznice(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('typelibi',self.WEBKIT_DEB/'typelibi.py')
        t=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(t)
        gir='<namespace name="WebKit" shared-library="libwebkitgtk-6.0.so.4,libjavascriptcoregtk-6.0.so.1" c:prefix="WebKit">'
        novo,n=t.absolutno(gir,'/usr/lib/safeer-os/webkit/lib/')
        self.assertEqual(n,1)
        self.assertIn('shared-library="/usr/lib/safeer-os/webkit/lib/libwebkitgtk-6.0.so.4,'
                      '/usr/lib/safeer-os/webkit/lib/libjavascriptcoregtk-6.0.so.1"',novo)
        # Ze absolutna pot ostane, brez knjiznice ni sprememb.
        self.assertEqual(t.absolutno(novo,'/drugje/lib')[0],novo)
        self.assertEqual(t.absolutno('<namespace name="GLib">','/x')[1],0)

    def _webkit(self, koren):
        tl=Path(koren)/'webkit/lib/girepository-1.0'
        tl.mkdir(parents=True)
        (tl/'WebKit-6.0.typelib').write_bytes(b'x')
        return str(tl)

    def test_zasebni_webkit_najde_predpono_paketa(self):
        from core import zasebni_webkit
        with tempfile.TemporaryDirectory() as d:
            brskalnik=Path(d)/'safeer-browser'
            tl=self._webkit(brskalnik)
            os_tl=self._webkit(Path(d)/'safeer-os')
            (Path(d)/'safeer-control').mkdir()
            self.assertEqual(zasebni_webkit.predpona(str(brskalnik)),str(brskalnik/'webkit'))
            # Safeer Control v paketu safeer-os (/usr/lib/safeer-control) uporabi WebKit paketa safeer-os.
            self.assertEqual(zasebni_webkit.predpona(str(Path(d)/'safeer-control')),str(Path(d)/'safeer-os/webkit'))
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
            # Safeer Control uporabi WebKit (in dav1ddec) paketa safeer-os.
            os_vt=Path(d)/'safeer-os/webkit/lib/gstreamer-1.0'
            self._webkit(Path(d)/'safeer-os')
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

    def _lazni_arhiv(self, d, paket):
        wk=Path(d)/'drevo/usr/lib'/paket/'webkit'
        for f in ('lib/libwebkitgtk-6.0.so.4','lib/libjavascriptcoregtk-6.0.so.1','lib/libsoup-3.0.so.0',
                  'libexec/webkitgtk-6.0/WebKitWebProcess','libexec/webkitgtk-6.0/WebKitNetworkProcess'):
            (wk/f).parent.mkdir(parents=True,exist_ok=True)
            shutil.copy('/bin/true',wk/f)
        for f in ('WebKit-6.0','Soup-3.0'):
            (wk/'lib/girepository-1.0').mkdir(parents=True,exist_ok=True)
            (wk/'lib/girepository-1.0'/(f+'.typelib')).write_bytes(b'x')
        (wk/'share/webkitgtk-safeer').mkdir(parents=True)
        (wk/'share/webkitgtk-safeer/gradnja.txt').write_text(
            'Ubuntu clang version 22.1.8\nLTO_MODE:UNINITIALIZED=thin\nbuild.ninja -fuse-ld=lld: 10\npredpona: /usr/lib/%s/webkit\n'%paket)
        arhiv=Path(d)/'webkit.tar.zst'
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
            arhiv=self._lazni_arhiv(d,'safeer-os')
            okolje=dict(os.environ,SAFEER_DAV1D=str(self._dav1d_mapa(d,'/bin/true')))
            r=subprocess.run(['bash',str(self.WEBKIT_DEB/'vgradi.sh'),str(Path(d)/'koren'),'safeer-os',str(arhiv)],
                             env=okolje,capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0,r.stdout)
            self.assertIn('ni libdav1d7',r.stderr)
            # Manjkajoca mapa vticnika se zavrne.
            okolje['SAFEER_DAV1D']=str(Path(d)/'ni')
            r=subprocess.run(['bash',str(self.WEBKIT_DEB/'vgradi.sh'),str(Path(d)/'koren'),'safeer-os',str(arhiv)],
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
            arhiv=self._lazni_arhiv(d,'safeer-os')
            okolje=dict(os.environ,SAFEER_DAV1D=str(self._dav1d_mapa(d,so)))
            koren=Path(d)/'koren'
            r=subprocess.run(['bash',str(self.WEBKIT_DEB/'vgradi.sh'),str(koren),'safeer-os',str(arhiv)],
                             env=okolje,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr[-2000:])
            self.assertRegex(r.stdout,r'(^|, )libdav1d7( |,|$)')
            wk=koren/'usr/lib/safeer-os/webkit'
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
        for ime,paket,naslednji in (('brskalnik','safeer-browser','safeer-os'),('safeer-os','safeer-os','mint')):
            with self.subTest(posel=ime):
                del_=potek.split('\n  %s:\n'%ime,1)[1].split('\n  %s:\n'%naslednji,1)[0]
                self.assertIn('needs: [webkit-deb, dav1d-deb]',del_)
                self.assertIn('name: dav1d-deb\n          path: build/dav1d',del_)
                self.assertIn('SAFEER_DAV1D=build/dav1d SAFEER_WEBKIT_TAR=build/webkit-%s.tar.zst'%paket,del_)
                self.assertIn("grep -F './usr/lib/%s/webkit/lib/gstreamer-1.0/libgstdav1d.so'"%paket,del_)
                self.assertIn("Depends | grep -E '(^|, )libdav1d7( |,|$)'",del_)
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

    def test_paket_z_nasim_webkitom_je_amd64_brez_sistemskega_webkita(self):
        """build_deb.sh s SAFEER_WEBKIT_TAR: drevo /usr/lib/safeer-browser/webkit, Depends iz dpkg-shlibdeps + peskovnik,
        brez gir1.2-webkit-6.0. Arhiv je ponaredek (ELF datoteke so kopije /bin/true), dovolj za pakiranje."""
        for orodje in ('dpkg-shlibdeps','dpkg-deb','zstd','file'):
            if not shutil.which(orodje):
                self.skipTest('ni %s'%orodje)
        with tempfile.TemporaryDirectory() as d:
            wk=Path(d)/'drevo/usr/lib/safeer-browser/webkit'
            for f in ('lib/libwebkitgtk-6.0.so.4','lib/libjavascriptcoregtk-6.0.so.1','lib/libsoup-3.0.so.0',
                      'libexec/webkitgtk-6.0/WebKitWebProcess','libexec/webkitgtk-6.0/WebKitNetworkProcess'):
                (wk/f).parent.mkdir(parents=True,exist_ok=True)
                shutil.copy('/bin/true',wk/f)
            for f in ('WebKit-6.0','Soup-3.0'):
                (wk/'lib/girepository-1.0').mkdir(parents=True,exist_ok=True)
                (wk/'lib/girepository-1.0'/(f+'.typelib')).write_bytes(b'x')
            (wk/'share/webkitgtk-safeer').mkdir(parents=True)
            gradnja=('Ubuntu clang version 22.1.8\nLTO_MODE:UNINITIALIZED=thin\nbuild.ninja -fuse-ld=lld: 10\n'
                     'predpona: /usr/lib/safeer-browser/webkit\n')
            (wk/'share/webkitgtk-safeer/gradnja.txt').write_text(gradnja)
            arhiv=Path(d)/'webkit.tar.zst'
            subprocess.run(['tar','-C',str(Path(d)/'drevo'),'-I','zstd','-cf',str(arhiv),'usr'],check=True)
            verzija=(ROOT/'packaging/VERSION').read_text().strip()
            deb=ROOT/('safeer-browser_%s_amd64.deb'%verzija)
            okolje=dict(os.environ,SAFEER_WEBKIT_TAR=str(arhiv))
            okolje.pop('SAFEER_BRSKALNIK_GTK3',None)
            try:
                r=subprocess.run(['bash',str(ROOT/'build_deb.sh')],cwd=ROOT,env=okolje,capture_output=True,text=True)
                self.assertEqual(r.returncode,0,r.stdout[-2000:]+r.stderr[-2000:])
                polja=subprocess.run(['dpkg-deb','-f',str(deb),'Architecture','Depends','Installed-Size'],capture_output=True,text=True,check=True).stdout
                self.assertIn('Architecture: amd64',polja)
                self.assertRegex(polja,r'Installed-Size: [1-9][0-9]*')
                for odvisnost in ('libc6','bubblewrap','xdg-dbus-proxy','glib-networking','gir1.2-gtk-4.0'):
                    self.assertIn(odvisnost,polja)
                self.assertNotIn('gir1.2-webkit-6.0',polja)
                self.assertNotIn('gir1.2-soup-3.0',polja)
                vsebina=subprocess.run(['dpkg-deb','-c',str(deb)],capture_output=True,text=True,check=True).stdout
                self.assertIn('./usr/lib/safeer-browser/webkit/libexec/webkitgtk-6.0/WebKitWebProcess',vsebina)
                self.assertIn('./usr/lib/safeer-browser/core/zasebni_webkit.py',vsebina)
                # Arhiv za drug paket (druga predpona) se zavrne: poti pomoznih procesov so prevedene v knjiznico.
                (wk/'share/webkitgtk-safeer/gradnja.txt').write_text(gradnja.replace('safeer-browser','safeer-os'))
                subprocess.run(['tar','-C',str(Path(d)/'drevo'),'-I','zstd','-cf',str(arhiv),'usr'],check=True)
                r=subprocess.run(['bash',str(ROOT/'build_deb.sh')],cwd=ROOT,env=okolje,capture_output=True,text=True)
                self.assertNotEqual(r.returncode,0)
                self.assertIn('predpona: /usr/lib/safeer-browser/webkit',r.stderr)
            finally:
                deb.unlink(missing_ok=True)
                (ROOT/'SHA256SUMS').unlink(missing_ok=True)

    def test_ci_gradi_webkit_za_oba_paketa_in_ju_preizkusi(self):
        potek=(ROOT/'.github/workflows/linux-packages.yml').read_text()
        profil=potek.split('\n  webkit-deb-profil:\n',1)[1].split('\n  webkit-deb:\n',1)[0]
        posel=potek.split('\n  webkit-deb:\n',1)[1].split('\n  brskalnik:\n',1)[0]
        self.assertIn('paket: [safeer-browser, safeer-os]',posel)
        self.assertIn('image: ubuntu:24.04',posel)
        # PGO je privzet (lastnik, 15. 10. 2026): lasten ucni tek gradnje noble, profil v predpomnilniku.
        self.assertIn('needs: webkit-deb-profil',posel)
        self.assertIn('SAFEER_WEBKIT_PGO=ucenje bash packaging/webkit-deb/zgradi.sh /usr/lib/safeer-browser/webkit',profil)
        self.assertIn('bash packaging/webkit-deb/ucni_tek.sh /usr/lib/safeer-browser/webkit build/pgo/profraw',profil)
        self.assertIn('SAFEER_WEBKIT_PGO=uporaba SAFEER_WEBKIT_PROFRAW=build/pgo/profraw',posel)
        self.assertIn('packaging/webkit-deb/zgradi.sh /usr/lib/${{ matrix.paket }}/webkit',posel)
        self.assertIn("grep -q '^USE_PGO_PROFILE:BOOL=ON$' gradnja.txt",posel)
        # Kljuca predpomnilnika iz vseh datotek gradnje in ucnega teka; brez restore-keys (star WebKit ne sme v paket).
        for datoteka in ('packaging/webkit/webkitgtk6-safeer.yml','packaging/webkit/*.patch','packaging/libsoup/**',
                         'packaging/webkit-deb/zgradi.sh','packaging/webkit-deb/modul.py','packaging/webkit-deb/typelibi.py',
                         'packaging/webkit-deb/odvisnosti.sh','packaging/webkit/pgo_trening.py','packaging/webkit-deb/ucni_tek.sh'):
            self.assertEqual(posel.count("'%s'"%datoteka),2,datoteka)
            self.assertEqual(profil.count("'%s'"%datoteka),2,datoteka)
        self.assertNotIn('restore-keys',posel+profil)
        # Isti Speedometer kot ucni tek Flatpaka.
        self.assertIn('1386415be8fef2f6b6bbdbe1828872471c5d802a',(self.WEBKIT_DEB/'ucni_tek.sh').read_text())
        # Pripeta kopija Flatpaka je od gtk4-integracija v packaging/webkit/pgo.py (vir PGO kot type: file s sha256).
        self.assertIn('1386415be8fef2f6b6bbdbe1828872471c5d802a',(ROOT/'packaging/webkit/pgo.py').read_text())
        for ime,paket,skripta in (('brskalnik','safeer-browser','build_deb.sh'),('safeer-os','safeer-os','build_os_deb.sh')):
            with self.subTest(posel=ime):
                del_=potek.split('\n  %s:\n'%ime,1)[1].split('\n  mint:\n' if ime=='safeer-os' else '\n  safeer-os:\n',1)[0]
                self.assertRegex(del_,r'needs: \[?webkit-deb\b')
                self.assertIn('name: webkit-deb-%s'%paket,del_)
                self.assertIn('SAFEER_WEBKIT_TAR=build/webkit-%s.tar.zst bash %s'%(paket,skripta),del_)
                self.assertIn('packaging/smoke_webkit_deb.py /usr/lib/%s'%paket,del_)
                self.assertIn('_amd64.deb',del_)
        self.assertIn('/smoke_webkit_deb.py',(ROOT/'tools/mint_namestitev/preizkus.sh').read_text())
        self.assertIn('webkit_preizkus "s sistemskim WebKitGTK',(ROOT/'tools/mint_namestitev/v_vsebniku.sh').read_text())


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
            zgrajeni|=set(re.findall(r'^Package: (\S+)$',skripta.read_text(),re.M))
        self.assertGreaterEqual(len(zgrajeni),2,zgrajeni)
        preizkus=(self.MAPA/'v_vsebniku.sh').read_text()
        odstranjeni=set(re.search(r'apt-get remove ([^>\n]*)',preizkus).group(1).split())
        for paket in sorted(zgrajeni):
            with self.subTest(paket=paket):
                # Od 15. 10. 2026 sta paketa amd64 (nas WebKitGTK, packaging/webkit-deb).
                self.assertRegex(preizkus,r"paket '%s_\*_(all|amd64)\.deb'"%re.escape(paket))
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
