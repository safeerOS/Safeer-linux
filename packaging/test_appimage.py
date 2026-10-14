"""Extract and exercise an AppImage with its own Python and library environment."""
import os, pathlib, subprocess, sys, tempfile
repo=pathlib.Path(__file__).resolve().parents[1]
artifact=pathlib.Path(sys.argv[1]).resolve()
subprocess.run([str(artifact),'--version'],check=True)
with tempfile.TemporaryDirectory(prefix='safeer-appimage-test-') as directory:
    subprocess.run([str(artifact),'--appimage-extract'],cwd=directory,stdout=subprocess.DEVNULL,check=True)
    appdir=pathlib.Path(directory)/'squashfs-root'
    runner=appdir/'.smoke-run'
    content=(appdir/'AppRun').read_text()
    entry='exec "$APPDIR/usr/bin/safeer" "$@"'
    if content.count(entry)!=1:
        raise SystemExit('Unrecognized AppRun entry point')
    runner.write_text(content.replace(entry,'exec "$PYTHON" "$@"'))
    runner.chmod(0o755)
    lib=appdir/'usr/lib/safeer-browser'
    # GTK4 brskalnik (safeer_brskalnik.py) ima svoj preizkus: stran, prenos, nastavitve in vstavitev Safeer DRM.
    smoke='smoke_brskalnik.py' if (lib/'safeer_brskalnik.py').exists() else 'smoke.py'
    subprocess.run([str(runner),str(repo/'packaging'/smoke),str(lib)],check=True,timeout=120)
