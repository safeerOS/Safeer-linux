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

    def test_debian_maintainer_scripts_are_posix_sh(self):
        text=(ROOT/'build_deb.sh').read_text()
        scripts=re.findall(r"cat << 'EOF' > \"\$BUILD_ROOT/DEBIAN/(post(?:inst|rm))\"\n(.*?)\nEOF\n",text,re.S)
        self.assertEqual({name for name,_ in scripts},{'postinst','postrm'})
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

