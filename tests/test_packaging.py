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
        with tempfile.TemporaryDirectory(prefix='safeer package ') as directory:
            prefix=Path(directory)/'usr'
            subprocess.run(['bash',str(ROOT/'packaging/install_payload.sh'),str(prefix)],check=True)
            fake=Path(directory)/'python'
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            fake.chmod(0o755)
            output=subprocess.check_output([str(prefix/'bin/safeer-browser'),'https://example.com/a b'],env={**os.environ,'PYTHON':str(fake)},text=True).splitlines()
            self.assertEqual(output,[str(prefix/'lib/safeer-browser/safeer_mint.py'),'https://example.com/a b'])
            subprocess.run(['desktop-file-validate',str(prefix/'share/applications/safeer-browser.desktop')],check=True)

    def _polja_control(self, builder):
        """Polja datoteke DEBIAN/control iz skripte build_*deb.sh (heredoc pred postinst)."""
        text=(ROOT/builder).read_text()
        blok=re.search(r'cat << EOF2 > "\$BUILD_ROOT/DEBIAN/control"\n(.*?)\nEOF2\n',text,re.S)
        self.assertIsNotNone(blok,builder)
        return dict(re.findall(r'^([A-Za-z-]+): (.*)$',blok.group(1),re.M))

    def test_safeer_os_only_recommends_safeer_control(self):
        """Dvoklik v Mintu (Captain, GDebi = python-apt DebPackage.check) bere samo Depends in Pre-Depends: odvisnost od
        safeer-control, ki ni v nobenem skladiscu, je safeer-os 0.4.75 naredila nenamestljiv (»Odvisnost ni razresena«).
        Safeer OS dela brez Controla in ga namesti sam, zato je Control samo priporocen - brez Breaks/Conflicts, ki
        jih python-apt ob preverbi ne bere (dpkg bi zavrnil sele med namestitvijo)."""
        polja=self._polja_control('build_os_deb.sh')
        self.assertEqual(polja['Package'],'safeer-os')
        for polje in ('Depends','Pre-Depends','Breaks','Conflicts','Replaces','Provides'):
            self.assertNotIn('safeer-control',polja.get(polje,''),polje)
        priporoceni=[p.strip() for p in polja['Recommends'].split(',')]
        self.assertIn('safeer-control (>= ${CONTROL_VERSION})',priporoceni)
        self.assertIn('CONTROL_VERSION="$(cat "$DIR/packaging/VERSION_CONTROL")"',(ROOT/'build_os_deb.sh').read_text())
        # Kar Safeer OS res potrebuje za zagon, ostane v Depends (vse iz skladisc).
        for odvisnost in ('python3','python3-gi','gir1.2-gtk-3.0','gir1.2-webkit2-4.1'):
            self.assertIn(odvisnost,[p.strip() for p in polja['Depends'].split(',')])
        # Paket videza mora ostati odvisen od Safeer OS (zazene `safeer-os --namizje`).
        self.assertRegex((ROOT/'build_os_tema_deb.sh').read_text(),r'(?m)^Depends: safeer-os \(>= \$\{VERSION\}\)')

    def test_debian_maintainer_scripts_are_posix_sh(self):
        for builder in ('build_deb.sh','build_control_deb.sh','build_os_deb.sh'):
            with self.subTest(builder=builder):
                self._preveri_skripte(builder)

    PROGRAM_DIRS=(('build_deb.sh','/usr/lib/safeer-browser'),('build_control_deb.sh','/usr/lib/safeer-control'),
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
                    self.assertEqual(scripts['prerm'].count(lib),3)
                    for action in ('remove','upgrade'):
                        subprocess.run(['sh','-c',scripts['prerm'].replace(lib,str(mapa)),'prerm',action],check=True)
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
        pot=self.MAPA/'dvojni_klik.py'
        compile(pot.read_text(),str(pot),'exec')

    def test_double_click_check_and_safeer_os_alone(self):
        """Pred skupno namestitvijo: vsak paket gre skozi preverbo dvoklika (python-apt, kot Captain in GDebi) na cistem
        sistemu, safeer-os se namesti SAM (brez safeer-control), se zazene in odstrani; paket videza po Safeer OS."""
        preizkus=(self.MAPA/'v_vsebniku.sh').read_text()
        self.assertIn('-v "$TU/dvojni_klik.py:/dvojni_klik.py:ro"',(self.MAPA/'preizkus.sh').read_text())
        skupna=preizkus.index('apt-get install -y -q --allow-downgrades --reinstall')
        prejsnja=preizkus.index('/prejsnji/safeer-*_all.deb >/tmp/prejsnja.log')
        klik=preizkus.index('python3 /dvojni_klik.py "$BRSKALNIK" "$CONTROL" "$OS" "$CINNAMON"')
        sam=preizkus.index('apt-get install -y -q --no-install-recommends "$OS" >/tmp/os-sam.log')
        self.assertIn('python3-apt',preizkus[:klik])
        self.assertLess(klik,sam)
        self.assertLess(sam,prejsnja)
        self.assertLess(prejsnja,skupna)
        odsek=preizkus[sam:prejsnja]
        for korak in ('[ ! -e /usr/bin/safeer-control ]','safeer-os --version','preveri_zagon /tmp/safeer-os-sam.png',
                      'python3 /dvojni_klik.py "$TEMA"','apt-get purge -y -q safeer-os'):
            self.assertIn(korak,odsek)
        self.assertIn('apt-get install -s -q "$OS"',preizkus[:sam])
        # Obstojeci zagon po skupni namestitvi ostane.
        self.assertIn('preveri_zagon /tmp/safeer-os.png /tmp/zagon.log',preizkus[skupna:])

    def test_double_click_script(self):
        """dvojni_klik.py: izhodna koda 1 in razlog (kot ga pokaze Captain), ce paketa ni mogoce namestiti z dvoklikom."""
        import importlib.util, io, types
        from contextlib import redirect_stdout
        spec=importlib.util.spec_from_file_location('dvojni_klik',self.MAPA/'dvojni_klik.py')
        modul=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modul)
        predpomnilniki=[]

        class Paket:
            def __init__(self,pot,cache=None):
                predpomnilniki.append(cache)
                self.pot=pot
                self._failure_string='' if pot.endswith('dobro.deb') else 'Dependency is not satisfiable: safeer-control (>= 2.1.73)\n'

            def check(self):
                return not self._failure_string

        lazni_apt=types.SimpleNamespace(Cache=object,debfile=types.SimpleNamespace(DebPackage=Paket))
        izpis=io.StringIO()
        with redirect_stdout(izpis):
            self.assertEqual(modul.main(['/p/dobro.deb'],lazni_apt),0)
            self.assertEqual(modul.main(['/p/dobro.deb','/p/safeer-os.deb'],lazni_apt),1)
            self.assertEqual(modul.main([],lazni_apt),2)
        self.assertIn('NAPAKA  /p/safeer-os.deb: Dependency is not satisfiable: safeer-control (>= 2.1.73)',izpis.getvalue())
        self.assertEqual(len(predpomnilniki),3)
        self.assertEqual(len({id(c) for c in predpomnilniki}),3)     # svez predpomnilnik za vsak paket

    def test_every_deb_we_build_is_installed_and_removed_on_mint(self):
        """Nov paket .deb ne sme mimo preizkusa: vsak `Package:` iz skript build_*deb.sh mora biti v njem."""
        zgrajeni=set()
        for skripta in ROOT.glob('build_*deb.sh'):
            zgrajeni|=set(re.findall(r'^Package: (\S+)$',skripta.read_text(),re.M))
        self.assertGreaterEqual(len(zgrajeni),5,zgrajeni)
        preizkus=(self.MAPA/'v_vsebniku.sh').read_text()
        odstranjeni=set(re.search(r'apt-get remove ([^>\n]*)',preizkus).group(1).split())
        for paket in sorted(zgrajeni):
            with self.subTest(paket=paket):
                self.assertIn("paket '%s_*_all.deb'"%paket,preizkus)
                self.assertIn(paket,odstranjeni)

    def test_ci_installs_safeer_os_alone(self):
        """Tudi posel deb-appimage namesti safeer-os sam (brez safeer-control) in preveri polja paketa."""
        potek=(ROOT/'.github/workflows/linux-packages.yml').read_text()
        korak=potek.split('- name: Safeer OS package',1)[1].split('\n      - name:',1)[0]
        sam=korak.index('apt-get install -y --no-install-recommends "$OS_DEB"')
        skupaj=korak.index('"./safeer-control_$(cat packaging/VERSION_CONTROL)_all.deb" "$OS_DEB"')
        self.assertLess(sam,skupaj)
        self.assertIn('test ! -e /usr/bin/safeer-control',korak[sam:skupaj])
        self.assertIn('safeer-os --version',korak[sam:skupaj])
        self.assertIn('Depends Pre-Depends Breaks | grep -q safeer-control',korak)

    def test_release_waits_for_the_mint_job(self):
        """Izdaja (posel release) ne sme nastati, ce namestitev na Linux Mintu pade."""
        potek=(ROOT/'.github/workflows/linux-packages.yml').read_text()
        self.assertIn('\n  mint:\n',potek)
        self.assertIn('tools/mint_namestitev/preizkus.sh',potek)
        izdaja=potek.split('\n  release:\n',1)[1]
        potrebe=re.search(r'^    needs: \[([^\]]+)\]$',izdaja,re.M)
        self.assertIsNotNone(potrebe)
        self.assertIn('mint',[p.strip() for p in potrebe.group(1).split(',')])
