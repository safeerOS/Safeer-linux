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
                self.assertIn("paket '%s_*_all.deb'"%paket,preizkus)
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
