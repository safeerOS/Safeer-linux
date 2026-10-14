"""Seed dynamic GTK, GI, Python and WebKit resources before ELF dependency resolution."""
import os, pathlib, re, shutil, subprocess, sys, sysconfig
root = pathlib.Path(sys.argv[1])
# AppStream/desktop ID and the desktop file's base name: browser by default, Safeer OS when asked.
appid = sys.argv[2] if len(sys.argv) > 2 else 'io.github.memelandfaner.SafeerBrowser'
desktop_name = sys.argv[3] if len(sys.argv) > 3 else 'safeer-browser'
license_packages = set()
triplet = subprocess.check_output(['dpkg-architecture','-qDEB_HOST_MULTIARCH'],text=True).strip()
lib = pathlib.Path('/usr/lib')/triplet

def copy(source, target):
    source=pathlib.Path(source); target=root/target
    if not source.exists():
        raise SystemExit(f'Required runtime resource missing: {source}')
    ownership=subprocess.run(['dpkg-query','-S',str(source)],capture_output=True,text=True)
    for line in ownership.stdout.splitlines():
        if ': ' in line:
            license_packages.update(p.split(':')[0] for p in line.split(': ',1)[0].split(', '))
    target.parent.mkdir(parents=True,exist_ok=True)
    if source.is_dir():
        shutil.copytree(source,target,dirs_exist_ok=True,symlinks=False,
                        ignore=shutil.ignore_patterns('__pycache__','test','tests','config-*','_test*','_xxtest*'))
    else:
        shutil.copy2(source,target)

pyver=f'python{sys.version_info.major}.{sys.version_info.minor}'
copy(sys.executable,'usr/bin/python3')
copy(pathlib.Path('/usr/lib')/pyver,f'usr/lib/{pyver}')
for module in ('gi','cairo'):
    copy(pathlib.Path('/usr/lib/python3/dist-packages')/module,f'usr/lib/python3/dist-packages/{module}')
# Safeer OS and, since 14 Oct 2026, the browser (safeer_brskalnik.py) run on GTK4 + WebKitGTK 6.0 (Ubuntu 24.04 /
# Mint 22 on). SAFEER_BRSKALNIK_GTK3=1 builds the previous GTK3 + WebKitGTK 4.1 browser (Ubuntu 22.04).
gtk4 = appid == 'io.github.memelandfaner.SafeerOS' or os.environ.get('SAFEER_BRSKALNIK_GTK3') != '1'
subs = (('girepository-1.0','webkitgtk-6.0','gstreamer-1.0','gstreamer1.0','gdk-pixbuf-2.0') if gtk4 else
        ('girepository-1.0','webkit2gtk-4.1','gstreamer-1.0','gstreamer1.0','gdk-pixbuf-2.0','gtk-3.0'))
for sub in subs:
    copy(lib/sub,f'usr/lib/{triplet}/{sub}')
if gtk4 and (lib/'gtk-4.0').exists():
    copy(lib/'gtk-4.0',f'usr/lib/{triplet}/gtk-4.0')   # media and print modules, when the host has them
# GIO TLS and proxy support are dynamically loaded.
for name in ('libgiognutls.so','libgiolibproxy.so'):
    copy(lib/'gio/modules'/name,f'usr/lib/{triplet}/gio/modules/{name}')
libs = (('libwebkitgtk-6.0.so.4','libjavascriptcoregtk-6.0.so.1','libgtk-4.so.1','libgirepository-1.0.so.1','libgstreamer-1.0.so.0')
        if gtk4 else
        ('libwebkit2gtk-4.1.so.0','libjavascriptcoregtk-4.1.so.0','libgtk-3.so.0','libgdk-3.so.0','libgirepository-1.0.so.1','libgstreamer-1.0.so.0'))
for name in libs:
    copy(lib/name,f'usr/lib/{name}')
copy('/usr/share/glib-2.0/schemas','usr/share/glib-2.0/schemas')
# No glibc, loader, GPU drivers, credentials or host certificate stores are copied.
subprocess.run(['glib-compile-schemas',str(root/'usr/share/glib-2.0/schemas')],check=True)

for package in sorted(license_packages):
    notice=pathlib.Path('/usr/share/doc')/package/'copyright'
    if notice.exists():
        dest=root/'usr/share/doc'/package/'copyright'
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(notice,dest)

# Match the desktop ID and AppStream component ID for AppImage validators.
metadata=root/'usr/share/metainfo'
(metadata/f'{appid}.metainfo.xml').rename(metadata/f'{appid}.appdata.xml')
xml=metadata/f'{appid}.appdata.xml'
text=xml.read_text().replace(f'{desktop_name}.desktop',f'{appid}.desktop')
# appimagetool validates with the build host's appstreamcli (Ubuntu 22.04: AppStream 0.15),
# where vcs-browser URLs are a warning and <developer> is unknown. Use the 0.15 equivalents.
text=re.sub(r'\s*<url type="vcs-browser">[^<]*</url>','',text)
text=re.sub(r'<developer id="[^"]*">\s*<name>([^<]*)</name>\s*</developer>',r'<developer_name>\1</developer_name>',text)
xml.write_text(text)
desktop=root/f'usr/share/applications/{desktop_name}.desktop'
desktop.rename(desktop.with_name(f'{appid}.desktop'))
