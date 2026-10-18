#!/usr/bin/env bash
# Namesti pred-potisno zaporo (tools/pre_push_testi.sh) v .git/hooks tega repozitorija.
set -eu
k="$(git rev-parse --show-toplevel)"
printf '#!/usr/bin/env bash\nexec bash "$(git rev-parse --show-toplevel)/tools/pre_push_testi.sh"\n' > "$k/.git/hooks/pre-push"
chmod +x "$k/.git/hooks/pre-push" "$k/tools/pre_push_testi.sh"
echo "pre-push zapora namescena v $k/.git/hooks/pre-push"
