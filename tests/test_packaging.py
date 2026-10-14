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

    def test_browser_launcher_in_flatpak_uses_host_tools_and_deb_data(self):
        """Kot packaging/safeer-os-launcher: ovoji orodij gostitelja in iste mape podatkov kot .deb."""
        brskalnik=(ROOT/'packaging/safeer-launcher').read_text()
        os_=(ROOT/'packaging/safeer-os-launcher').read_text()
        for vrstica in ('if [ -n "${FLATPAK_ID:-}" ] && [ -d /app/host-bin ]; then','export PATH="/app/host-bin:$PATH"',
                        'export XDG_CONFIG_HOME="$HOME/.config" XDG_DATA_HOME="$HOME/.local/share" XDG_CACHE_HOME="$HOME/.cache"'):
            self.assertIn(vrstica,os_)
            self.assertIn(vrstica,brskalnik)
        # Obseg systemd ostane (odziven racunalnik, ko stran porabi prevec), Flatpak paketa .deb pa ga ne potrebuje.
        self.assertLess(brskalnik.index('exec flatpak run "$FP_ID"'),brskalnik.index('systemd-run --user --scope'))

    def test_browser_flatpak_ships_our_webkit_and_safeer_drm(self):
        """Flatpak brskalnika ima nas WebKitGTK 6.0 iz iste datoteke modula kot Safeer OS (brez kopije gradnje) in
        dovoljenja, ki jih Safeer DRM potrebuje: zagon na gostitelju (flatpak-spawn --host) in skupne mape v domu."""
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
        self.assertIn('bash packaging/flatpak_host_wrappers.sh /app/host-bin',brskalnik)
        dovoljenja=set(re.findall(r'^  - (--\S+)$',brskalnik,re.M))
        drm=(ROOT/'core/safeer_drm.py').read_text()
        self.assertIn('"flatpak-spawn", "--host"',drm)
        self.assertIn('--talk-name=org.freedesktop.Flatpak',dovoljenja)
        self.assertIn('Path(os.path.expanduser("~/.local/share/safeer-drm"))',drm)
        self.assertIn('--filesystem=home',dovoljenja)
        self.assertTrue({'--socket=wayland','--socket=fallback-x11','--share=network','--socket=pulseaudio',
                         '--device=dri'}<=dovoljenja,dovoljenja)
        # Ovoj »safeer« v /app/host-bin bi v brskalniku pokazal na brskalnik gostitelja.
        self.assertIn('rm -f /app/host-bin/safeer /app/host-bin/safeer-browser',brskalnik)

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
