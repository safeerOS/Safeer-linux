#!/usr/bin/env bash
# Video v oknu GTK4: gtk4paintablesink (gst-plugins-rs, crate gst-plugin-gtk4) za pakete .deb - zraven nasega WebKitGTK v
# /usr/lib/<paket>/webkit/lib/gstreamer-1.0 (kot dav1d.sh; pot doda core/zasebni_webkit.py v GST_PLUGIN_PATH).
# Zakaj: noble (Linux Mint 22) nima paketa gstreamer1.0-gtk4 (v Ubuntu je od 26.04). Brez vticnika safeer_os.py v
# _odpri_medijski_predvajalnik izbere autovideosink: film tece v GOLEM oknu brez gumbov (naslov »safeer_os.py«, plosca
# Cinnamon ostane), Pavza in Cel zaslon pa veljata za drugo okno. Lastnik, 17. 11. 2026: »v Medijskem centru na Linuxu
# ne morem dati filma na pavzo in res cez celi zaslon«; na prenosniku `gst-inspect-1.0 gtk4paintablesink` = ni vticnika.
#
#   gtk4sink.sh IZHODNA_MAPA      -> libgstgtk4.so (strip), LICENSE-MPL-2.0, gradnja.txt
#
# Gradnja proti sistemskemu GStreamerju noble (1.24) in GTK 4.14 (apt: libgtk-4-dev libgstreamer1.0-dev
# libgstreamer-plugins-base1.0-dev pkg-config). Rust iz rustup (crate zahteva 1.83, cargo iz apt noble 1.75 je prestar).
# Crate s preverbo SHA-256 (crates.io), odvisnosti iz njegovega Cargo.lock (--locked). Licenca MPL-2.0 (datoteka zraven).
set -euo pipefail
RAZLICICA=0.14.5
SHA256=43374b56cbf41ca49730deb030f8d880bbf427226b53e14760f6b8bef03f4c0e
RUST=1.95.0
IZHOD="${1:?Uporaba: gtk4sink.sh IZHODNA_MAPA}"

command -v rustup >/dev/null || { echo "gtk4sink.sh: ni rustup (Rust $RUST)" >&2; exit 1; }
rustup toolchain install "$RUST" --profile minimal --no-self-update >&2
DELO="$(mktemp -d)"
trap 'rm -rf "$DELO"' EXIT
curl -fsSL --retry 3 -o "$DELO/crate.tar.gz" \
    "https://static.crates.io/crates/gst-plugin-gtk4/gst-plugin-gtk4-$RAZLICICA.crate"
echo "$SHA256  $DELO/crate.tar.gz" | sha256sum -c --quiet -
tar -C "$DELO" -xzf "$DELO/crate.tar.gz"
IZVOR="$DELO/gst-plugin-gtk4-$RAZLICICA"
[ -f "$IZVOR/Cargo.lock" ] || { echo "gtk4sink.sh: crate nima Cargo.lock" >&2; exit 1; }
# Utrjena gradnja (AGENTS.md): polni RELRO in BIND_NOW. Znacilnosti: X11 (GLX, EGL), Wayland (EGL), dmabuf (GTK >= 4.14).
RUSTFLAGS="-C link-arg=-Wl,-z,relro,-z,now" CARGO_TARGET_DIR="$DELO/target" cargo +"$RUST" build --release --locked \
    --features "wayland,x11egl,x11glx,dmabuf" --manifest-path "$IZVOR/Cargo.toml" >&2

mkdir -p "$IZHOD"
IZHOD="$(cd "$IZHOD" && pwd)"
SO="$IZHOD/libgstgtk4.so"
install -m 644 "$DELO/target/release/libgstgtk4.so" "$SO"
strip --strip-unneeded "$SO"
install -m 644 "$IZVOR/LICENSE-MPL-2.0" "$IZHOD/"
POTREBNE="$(readelf -d "$SO" | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | paste -sd ' ')"
for knj in libgtk-4.so.1 libgstreamer-1.0.so.0 libgstvideo-1.0.so.0 libgstgl-1.0.so.0; do
    case " $POTREBNE " in *" $knj "*) ;; *) echo "gtk4sink.sh: $SO ni povezan z $knj ($POTREBNE)" >&2; exit 1 ;; esac
done
{
    echo "gst-plugin-gtk4 $RAZLICICA (crates.io sha256 $SHA256, MPL-2.0)"
    rustc +"$RUST" --version
    echo "gstreamer-1.0 $(pkg-config --modversion gstreamer-1.0), gtk4 $(pkg-config --modversion gtk4)"
    echo "znacilnosti: wayland,x11egl,x11glx,dmabuf"
    echo "NEEDED: $POTREBNE"
    echo "velikost: $(stat -c %s "$SO") B"
    echo "Cargo.lock sha256: $(sha256sum "$IZVOR/Cargo.lock" | cut -d' ' -f1)"
} > "$IZHOD/gradnja.txt"

# GStreamer sistema mora vticnik najti: tvornica gtk4paintablesink iz TE datoteke.
GST_PLUGIN_PATH="$IZHOD" GST_REGISTRY="$DELO/registry.bin" python3 -I - "$SO" <<'PY'
import ctypes, sys
g = ctypes.CDLL("libgstreamer-1.0.so.0")
g.gst_init(None, None)
g.gst_element_factory_find.restype = ctypes.c_void_p
g.gst_element_factory_find.argtypes = [ctypes.c_char_p]
g.gst_plugin_feature_get_plugin.restype = ctypes.c_void_p
g.gst_plugin_feature_get_plugin.argtypes = [ctypes.c_void_p]
g.gst_plugin_get_filename.restype = ctypes.c_char_p
g.gst_plugin_get_filename.argtypes = [ctypes.c_void_p]
f = g.gst_element_factory_find(b"gtk4paintablesink")
assert f, "GStreamer ne najde gtk4paintablesink"
pot = g.gst_plugin_get_filename(g.gst_plugin_feature_get_plugin(f)).decode()
print("gtk4paintablesink:", pot, file=sys.stderr)
assert pot == sys.argv[1], pot
PY
cat "$IZHOD/gradnja.txt" >&2
