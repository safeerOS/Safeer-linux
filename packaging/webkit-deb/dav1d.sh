#!/usr/bin/env bash
# Dekoder AV1 dav1ddec (gst-plugins-rs, crate gst-plugin-dav1d) za pakete .deb - zraven nasega WebKitGTK v
# /usr/lib/<paket>/webkit/lib/gstreamer-1.0 (packaging/webkit-deb/vgradi.sh; pot doda core/zasebni_webkit.py).
# Zakaj: noble (Linux Mint 22) ima libdav1d7, nima pa vticnika GStreamer zanj; gst-libav nima dekoderja AV1, ostane le
# pocasni libaom av1dec (rang secondary). Lastnik, 18. 10. 2026: YouTube AV1 720p v nasem WebKitu z dav1ddec 0 izpuscenih
# slicic in ~12 % manj CPU kot z av1dec.
#
#   dav1d.sh IZHODNA_MAPA      -> libgstdav1d.so (strip), LICENSE-MIT, LICENSE-APACHE, gradnja.txt
#
# Gradnja proti sistemskemu GStreamerju noble (1.24) in libdav1d 1.4 (apt: libgstreamer1.0-dev
# libgstreamer-plugins-base1.0-dev libdav1d-dev pkg-config). Rust iz rustup: cargo iz apt noble (1.75) je prestar, crate
# zahteva 1.83. Crate s preverbo SHA-256 (cksum indeksa crates.io), odvisnosti iz njegovega Cargo.lock (--locked: cargo
# preveri kontrolne vsote vseh odvisnosti). ~1 min, 550 KB po strip (merjeno 18. 10. 2026 na Ubuntu 24.04).
set -euo pipefail
RAZLICICA=0.14.5
SHA256=fee4d853d1a7b253a6771e63dac20c43bce86ea27486f8672e65a0f7c0e0bcd6
RUST=1.95.0
IZHOD="${1:?Uporaba: dav1d.sh IZHODNA_MAPA}"

command -v rustup >/dev/null || { echo "dav1d.sh: ni rustup (Rust $RUST)" >&2; exit 1; }
rustup toolchain install "$RUST" --profile minimal --no-self-update >&2
DELO="$(mktemp -d)"
trap 'rm -rf "$DELO"' EXIT
curl -fsSL --retry 3 -o "$DELO/crate.tar.gz" \
    "https://static.crates.io/crates/gst-plugin-dav1d/gst-plugin-dav1d-$RAZLICICA.crate"
echo "$SHA256  $DELO/crate.tar.gz" | sha256sum -c --quiet -
tar -C "$DELO" -xzf "$DELO/crate.tar.gz"
IZVOR="$DELO/gst-plugin-dav1d-$RAZLICICA"
[ -f "$IZVOR/Cargo.lock" ] || { echo "dav1d.sh: crate nima Cargo.lock" >&2; exit 1; }
CARGO_TARGET_DIR="$DELO/target" cargo +"$RUST" build --release --locked --manifest-path "$IZVOR/Cargo.toml" >&2

mkdir -p "$IZHOD"
IZHOD="$(cd "$IZHOD" && pwd)"
SO="$IZHOD/libgstdav1d.so"
install -m 644 "$DELO/target/release/libgstdav1d.so" "$SO"
strip --strip-unneeded "$SO"
install -m 644 "$IZVOR/LICENSE-MIT" "$IZVOR/LICENSE-APACHE" "$IZHOD/"
POTREBNE="$(readelf -d "$SO" | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p' | paste -sd ' ')"
for knj in libdav1d.so.7 libgstreamer-1.0.so.0 libgstvideo-1.0.so.0; do
    case " $POTREBNE " in *" $knj "*) ;; *) echo "dav1d.sh: $SO ni povezan z $knj ($POTREBNE)" >&2; exit 1 ;; esac
done
{
    echo "gst-plugin-dav1d $RAZLICICA (crates.io sha256 $SHA256, MIT OR Apache-2.0)"
    rustc +"$RUST" --version
    echo "gstreamer-1.0 $(pkg-config --modversion gstreamer-1.0), dav1d $(pkg-config --modversion dav1d)"
    echo "NEEDED: $POTREBNE"
    echo "velikost: $(stat -c %s "$SO") B"
    echo "Cargo.lock sha256: $(sha256sum "$IZVOR/Cargo.lock" | cut -d' ' -f1)"
} > "$IZHOD/gradnja.txt"

# GStreamer sistema mora vticnik najti in ga uvrstiti pred av1dec (rang primary 256 > secondary 128).
GST_PLUGIN_PATH="$IZHOD" GST_REGISTRY="$DELO/registry.bin" python3 -I - "$SO" <<'PY'
import ctypes, sys
g = ctypes.CDLL("libgstreamer-1.0.so.0")
g.gst_init(None, None)
g.gst_element_factory_find.restype = ctypes.c_void_p
g.gst_element_factory_find.argtypes = [ctypes.c_char_p]
g.gst_plugin_feature_get_rank.restype = ctypes.c_uint
g.gst_plugin_feature_get_rank.argtypes = [ctypes.c_void_p]
g.gst_plugin_feature_get_plugin.restype = ctypes.c_void_p
g.gst_plugin_feature_get_plugin.argtypes = [ctypes.c_void_p]
g.gst_plugin_get_filename.restype = ctypes.c_char_p
g.gst_plugin_get_filename.argtypes = [ctypes.c_void_p]
f = g.gst_element_factory_find(b"dav1ddec")
assert f, "GStreamer ne najde dav1ddec"
pot = g.gst_plugin_get_filename(g.gst_plugin_feature_get_plugin(f)).decode()
rang = g.gst_plugin_feature_get_rank(f)
print("dav1ddec:", pot, "rang", rang, file=sys.stderr)
assert pot == sys.argv[1] and rang >= 256, (pot, rang)
PY
cat "$IZHOD/gradnja.txt" >&2
