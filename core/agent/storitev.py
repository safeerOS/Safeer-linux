"""Link dejanje `agent.ask` na racunalniku (Safeer Control): telefon ali televizor poslje stavek, racunalnik ga z
lokalnim modelom razume in izvede naloge na napravah v Linku. Dostop: neznano dejanje zahteva polno zaupanje
(link_dostop.zahteva_dejanja -> VSE), zato agenta lahko uporabi le naprava iz ozjega kroga - ne more prek racunalnika
upravljati naprav, ki jih sama ne bi smela.

parametri: {"text": stavek, "minutes": trajanje seje (1.. ali 0/None = neomejeno), "stop": true = ustavi sejo,
"here": id naprave, ki pomeni "tukaj" (daljinec na telefonu upravlja televizor -> tukaj je televizor; privzeto posiljatelj)}
odgovor data: {"steps": [{"task": {...}, "ok": bool, "text": kratek izid, "device": ime}], "session_left_s": int|null}"""
from __future__ import annotations

import threading
import time
from typing import Callable, Dict, Optional

from core.agent import seja as seja_mod

#: Seja na posiljatelja (naprava), pozabljena po eni uri mirovanja.
_seje: Dict[str, seja_mod.Seja] = {}
_zadnjic: Dict[str, float] = {}
_zaklep = threading.Lock()
POZABI_PO_S = 3600
#: Tovarna seje (preizkusi jo zamenjajo).
nova_seja: Callable[..., seja_mod.Seja] = seja_mod.Seja


def _seja(posiljatelj: str, minute) -> seja_mod.Seja:
    zdaj = time.monotonic()
    with _zaklep:
        for k in [k for k, t in _zadnjic.items() if zdaj - t > POZABI_PO_S]:
            _seje.pop(k, None); _zadnjic.pop(k, None)
        s = _seje.get(posiljatelj)
        if s is None or not s.tece() or minute is not None:
            if minute is None:
                # Naprava trajanja ni povedala: privzeto iz Nastavitev Safeer OS (0 = neomejeno, kot do zdaj).
                from core.agent import nastavitve
                minute = nastavitve.trajanje()
            trajanje = int(minute) if isinstance(minute, (int, float)) and minute > 0 else None
            s = nova_seja(trajanje_min=trajanje, tukaj=posiljatelj)
            _seje[posiljatelj] = s
        _zadnjic[posiljatelj] = zdaj
        return s


def vprasaj(parametri: dict, posiljatelj: str, koncaj: Callable[[dict], None],
            izid: Callable[..., dict], v_ozadju: bool = True) -> None:
    if parametri.get("stop"):
        with _zaklep:
            s = _seje.pop(posiljatelj, None)
        if s is not None:
            s.ustavi()
        koncaj(izid(True, "Agent je ustavljen."))
        return
    besedilo = " ".join(str(parametri.get("text", "") or "").split())[:300]
    if not besedilo:
        koncaj(izid(False, "Ni besedila", koda="prazno"))
        return
    minute = parametri.get("minutes")
    s = _seja(posiljatelj, minute if isinstance(minute, (int, float)) and not isinstance(minute, bool) else None)
    tukaj = str(parametri.get("here") or "").strip()[:128]
    s.tukaj = tukaj or posiljatelj

    def delo() -> None:
        try:
            koraki = s.narocilo(besedilo)
            ok = any(k.ok for k in koraki)
            povzetek = " ".join(k.izid for k in koraki)[:300]
            ostane = None if s.trajanje_min is None else max(0, int(s.trajanje_min * 60 - (s.ura() - s._zacetek)))
            brez_modela = not ok and len(koraki) == 1 and koraki[0].izid.startswith("model ni dosegljiv")
            koncaj(izid(ok, povzetek, {"steps": [{"task": k.naloga, "ok": k.ok, "text": k.izid, "device": k.naprava}
                                                  for k in koraki], "session_left_s": ostane},
                        koda="agent_ni_modela" if brez_modela else ""))
        except Exception as e:  # noqa: BLE001 - odgovor mora vedno priti
            koncaj(izid(False, "Agent: " + (str(e) or type(e).__name__)[:120]))

    if v_ozadju:
        threading.Thread(target=delo, name="safeer-agent", daemon=True).start()
    else:
        delo()


def vprasaj_tukaj(besedilo: str, izvajalec=None) -> dict:
    """Iskalna lupa Safeer OS na tem racunalniku (lastnik, 19. 10. 2026: »znotraj iskalne lupe je nas AI asistent«):
    stavek gre istemu agentu kot z druge naprave, »tukaj« je ta racunalnik (naprava »ta« v seznamu Linka). Brez nastavljenega
    ali vklopljenega modela agent ne dela in to pove (koda »ni_modela«) - nic se ne ugiba.
    Vrne {"ok", "koda", "koraki": [{"ok", "besedilo", "naprava"}], "povzetek"}."""
    from core.agent import izvajanje
    from core.agent.razumevanje import naslov_modela
    besedilo = " ".join(str(besedilo or "").split())[:300]
    if not besedilo:
        return {"ok": False, "koda": "prazno", "koraki": [], "povzetek": ""}
    if not naslov_modela():
        return {"ok": False, "koda": "ni_modela", "koraki": [], "povzetek": ""}
    izv = izvajalec or izvajanje.Izvajalec()
    tukaj = next((str(n.get("id")) for n in izv.naprave() if n.get("ta")), "")
    s = _seja("lupa", None)
    s.izvajalec = izv
    s.tukaj = tukaj
    koraki = s.narocilo(besedilo)
    brez_modela = len(koraki) == 1 and not koraki[0].ok and koraki[0].izid.startswith("model ni dosegljiv")
    return {"ok": any(k.ok for k in koraki), "koda": "model_ni_dosegljiv" if brez_modela else "",
            "koraki": [{"ok": k.ok, "besedilo": k.izid, "naprava": k.naprava} for k in koraki],
            "povzetek": " ".join(k.izid for k in koraki)[:300]}
