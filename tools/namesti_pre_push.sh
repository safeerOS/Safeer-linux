#!/usr/bin/env bash
# Namesti pred-potisno zaporo (tools/pre_push_testi.sh) za ta repozitorij.
# Ce je nastavljen globalni core.hooksPath (npr. varnostne kljuke), git .git/hooks ne bere: zato naredimo lokalno mapo
# kljuk, ki ohrani vse globalne kljuke (povezave) in doda pre-push, ter jo nastavimo SAMO za ta repozitorij.
set -eu
k="$(git rev-parse --show-toplevel)"
gd="$(git rev-parse --absolute-git-dir)"
m="$gd/safeer-hooks"; mkdir -p "$m"
globalna="$(git config --global core.hooksPath || true)"
globalna="${globalna/#\~/$HOME}"
if [ -n "$globalna" ] && [ -d "$globalna" ]; then
  for f in "$globalna"/*; do [ -x "$f" ] && [ "$(basename "$f")" != pre-push ] && ln -sf "$f" "$m/$(basename "$f")"; done
fi
printf '#!/usr/bin/env bash\nexec bash "$(git rev-parse --show-toplevel)/tools/pre_push_testi.sh"\n' > "$m/pre-push"
chmod +x "$m/pre-push" "$k/tools/pre_push_testi.sh"
git config --local core.hooksPath "$m"
echo "pre-push zapora namescena: $m (globalne kljuke ohranjene: ${globalna:-ni})"
