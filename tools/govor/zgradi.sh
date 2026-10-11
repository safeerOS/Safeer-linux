#!/bin/bash
# Zgradi whisper-cli (whisper.cpp) za govor v iskalni lupi Safeer OS (core/os_govor.py).
# $1 = razlicica: x86_64-v3 (AVX2, FMA, F16C) ali x86_64 (osnovni procesor), $2 = izhodna mapa.
# Brez OpenMP in s staticnim libstdc++: program potrebuje samo libc/libm (Ubuntu 22.04 / Mint 21 in novejsi).
set -euo pipefail
RAZLICICA="$1"; IZHOD="$(realpath -m "$2")"
OZNAKA=v1.9.5
ZAPIS=d1be6fde11ac6e0407606b4e42fe72d34add8037
CMAKE="${CMAKE:-cmake}"
DELO="$(mktemp -d)"
trap 'rm -rf "$DELO"' EXIT
git -c advice.detachedHead=false clone -q --depth 1 --branch "$OZNAKA" https://github.com/ggml-org/whisper.cpp "$DELO/src"
test "$(git -C "$DELO/src" rev-parse HEAD)" = "$ZAPIS" || { echo "whisper.cpp $OZNAKA ni pricakovani zapis $ZAPIS"; exit 1; }
case "$RAZLICICA" in
  x86_64-v3) CPU="-DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON" ;;
  x86_64)    CPU="-DGGML_AVX=OFF -DGGML_AVX2=OFF -DGGML_FMA=OFF -DGGML_F16C=OFF" ;;
  *) echo "neznana razlicica $RAZLICICA"; exit 2 ;;
esac
# shellcheck disable=SC2086
"$CMAKE" -S "$DELO/src" -B "$DELO/build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF \
  -DGGML_OPENMP=OFF -DWHISPER_SDL2=OFF -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_SERVER=OFF $CPU \
  -DCMAKE_EXE_LINKER_FLAGS="-static-libstdc++ -static-libgcc" > "$DELO/cmake.log"
"$CMAKE" --build "$DELO/build" -j "$(nproc)" --target whisper-cli > "$DELO/build.log"
mkdir -p "$IZHOD"
install -m 755 "$DELO/build/bin/whisper-cli" "$IZHOD/whisper-cli-$RAZLICICA"
strip "$IZHOD/whisper-cli-$RAZLICICA"
# Samo sistemske knjiznice, ki jih ima vsak Linux.
if ldd "$IZHOD/whisper-cli-$RAZLICICA" | grep -v -E 'linux-vdso|ld-linux|libc\.so|libm\.so|libpthread|libdl|librt'; then
  echo "nepricakovana knjiznica"; exit 3
fi
cp "$DELO/src/samples/jfk.wav" "$IZHOD/jfk.wav"
cp "$DELO/src/LICENSE" "$IZHOD/whisper.cpp-LICENSE"     # MIT: obvestilo gre zraven programa
sha256sum "$IZHOD/whisper-cli-$RAZLICICA"
