"""safeer://procesi - the browser's own task manager page.

One row per tab from the monitor's last sample: CPU share, resident memory, threads, state
(active / playing sound / sleeping / why it may not sleep) and two actions that go back to the
browser as links on the same scheme (`?spi=<id>` puts a tab to sleep, `?zapri=<id>` closes it).
Embedded web apps (chats beside the browser, Sporocila) are listed too, without actions.

Since 1.0.127 (GTK4 Splet, core/splet_spanje.py) the action links carry a one-time key (`&k=`): the
browser acts only on a key it handed out, so an old history entry or a reload never repeats an
action. Colours come from assets/os/tokens.css (one source for all Safeer pages). The page refreshes
itself every three seconds with location.replace (no history entries), but only while it is visible
and nothing on it has keyboard focus - a meta refresh used to throw the focus away every three seconds.
It is rendered from plain data, so it is testable without GTK.
"""
import functools
import html
import os
import secrets
import urllib.parse

REFRESH_SECONDS = 3
PAGE_URI = "safeer://procesi"

_TEXT = {
    "sl": {
        "title": "Procesi",
        "intro": "Vsak zavihek teče v svojem procesu. Safeer meri vsaki dve sekundi; težek zavihek v ozadju brez zvoka po minuti zaspi.",
        "tab": "Zavihek", "cpu": "CPU", "memory": "Pomnilnik", "threads": "Niti", "state": "Stanje", "actions": "Dejanja",
        "active": "aktiven", "audio": "zvok", "sleeping": "spi", "hot": "nad proračunom", "hog": "dolgo nad proračunom",
        "sleep": "Uspavaj", "close": "Zapri", "total": "Skupaj", "no_process": "—",
        "limit": "Meja pomnilnika na zavihek: {limit} MB · proračun CPU: {cpu} % enega jedra",
        "rule": "Zavihek v ozadju, ki ga {min} min ne uporabljaš, zaspi in sprosti pomnilnik; ko se vrneš, se naloži znova na istem mestu. Nikoli ne zaspi zavihek, ki predvaja zvok ali video, ima urejen ali poslan obrazec, prenos, kamero, mikrofon ali deljenje zaslona.",
        "app": "vdelana aplikacija", "media": "predvajanje", "form": "urejen obrazec", "post": "poslan obrazec",
        "download": "prenos", "capture": "kamera, mikrofon ali zaslon", "linked": "povezano okno",
    },
    "en": {
        "title": "Processes",
        "intro": "Every tab runs in its own process. Safeer samples every two seconds; a heavy background tab without sound is put to sleep after a minute.",
        "tab": "Tab", "cpu": "CPU", "memory": "Memory", "threads": "Threads", "state": "State", "actions": "Actions",
        "active": "active", "audio": "sound", "sleeping": "sleeping", "hot": "over budget", "hog": "over budget for long",
        "sleep": "Sleep", "close": "Close", "total": "Total", "no_process": "—",
        "limit": "Memory limit per tab: {limit} MB · CPU budget: {cpu} % of one core",
        "rule": "A background tab you have not used for {min} min goes to sleep and frees its memory; when you come back it loads again at the same place. A tab never sleeps while it plays sound or video, or has an edited or submitted form, a download, the camera, the microphone or screen sharing.",
        "app": "embedded app", "media": "playing", "form": "form being edited", "post": "submitted form",
        "download": "download", "capture": "camera, microphone or screen", "linked": "linked window",
    },
    "de": {
        "title": "Prozesse",
        "intro": "Jeder Tab läuft in einem eigenen Prozess. Safeer misst alle zwei Sekunden; ein schwerer Hintergrund-Tab ohne Ton wird nach einer Minute schlafen gelegt.",
        "tab": "Tab", "cpu": "CPU", "memory": "Speicher", "threads": "Threads", "state": "Status", "actions": "Aktionen",
        "active": "aktiv", "audio": "Ton", "sleeping": "schläft", "hot": "über dem Budget", "hog": "lange über dem Budget",
        "sleep": "Schlafen legen", "close": "Schließen", "total": "Gesamt", "no_process": "—",
        "limit": "Speichergrenze pro Tab: {limit} MB · CPU-Budget: {cpu} % eines Kerns",
        "rule": "Ein Hintergrund-Tab, den du {min} Min. nicht benutzt hast, schläft ein und gibt seinen Speicher frei; wenn du zurückkehrst, lädt er an derselben Stelle neu. Ein Tab schläft nie, solange er Ton oder Video abspielt oder ein bearbeitetes oder gesendetes Formular, einen Download, die Kamera, das Mikrofon oder eine Bildschirmfreigabe hat.",
        "app": "eingebettete App", "media": "Wiedergabe", "form": "Formular in Bearbeitung", "post": "gesendetes Formular",
        "download": "Download", "capture": "Kamera, Mikrofon oder Bildschirm", "linked": "verknüpftes Fenster",
    },
    "es": {
        "title": "Procesos",
        "intro": "Cada pestaña se ejecuta en su propio proceso. Safeer mide cada dos segundos; una pestaña pesada en segundo plano y sin sonido se duerme al cabo de un minuto.",
        "tab": "Pestaña", "cpu": "CPU", "memory": "Memoria", "threads": "Hilos", "state": "Estado", "actions": "Acciones",
        "active": "activa", "audio": "sonido", "sleeping": "dormida", "hot": "por encima del límite", "hog": "mucho tiempo por encima del límite",
        "sleep": "Dormir", "close": "Cerrar", "total": "Total", "no_process": "—",
        "limit": "Límite de memoria por pestaña: {limit} MB · límite de CPU: {cpu} % de un núcleo",
        "rule": "Una pestaña en segundo plano que no usas desde hace {min} min se duerme y libera su memoria; cuando vuelves, se carga de nuevo en el mismo lugar. Una pestaña nunca se duerme mientras reproduce sonido o vídeo, o tiene un formulario editado o enviado, una descarga, la cámara, el micrófono o la pantalla compartida.",
        "app": "aplicación integrada", "media": "reproducción", "form": "formulario en edición", "post": "formulario enviado",
        "download": "descarga", "capture": "cámara, micrófono o pantalla", "linked": "ventana vinculada",
    },
    "fr": {
        "title": "Processus",
        "intro": "Chaque onglet tourne dans son propre processus. Safeer mesure toutes les deux secondes ; un onglet lourd en arrière-plan sans son est mis en veille au bout d’une minute.",
        "tab": "Onglet", "cpu": "CPU", "memory": "Mémoire", "threads": "Threads", "state": "État", "actions": "Actions",
        "active": "actif", "audio": "son", "sleeping": "en veille", "hot": "au-delà du budget", "hog": "longtemps au-delà du budget",
        "sleep": "Mettre en veille", "close": "Fermer", "total": "Total", "no_process": "—",
        "limit": "Limite de mémoire par onglet : {limit} Mo · budget CPU : {cpu} % d’un cœur",
        "rule": "Un onglet en arrière-plan que vous n’avez pas utilisé depuis {min} min se met en veille et libère sa mémoire ; à votre retour, il se recharge au même endroit. Un onglet ne se met jamais en veille tant qu’il lit du son ou une vidéo, ou qu’il a un formulaire modifié ou envoyé, un téléchargement, la caméra, le micro ou un partage d’écran.",
        "app": "application intégrée", "media": "lecture", "form": "formulaire en cours", "post": "formulaire envoyé",
        "download": "téléchargement", "capture": "caméra, micro ou écran", "linked": "fenêtre liée",
    },
    "it": {
        "title": "Processi",
        "intro": "Ogni scheda gira in un proprio processo. Safeer misura ogni due secondi; una scheda pesante in background senza audio viene sospesa dopo un minuto.",
        "tab": "Scheda", "cpu": "CPU", "memory": "Memoria", "threads": "Thread", "state": "Stato", "actions": "Azioni",
        "active": "attiva", "audio": "audio", "sleeping": "sospesa", "hot": "oltre il budget", "hog": "a lungo oltre il budget",
        "sleep": "Sospendi", "close": "Chiudi", "total": "Totale", "no_process": "—",
        "limit": "Limite di memoria per scheda: {limit} MB · budget CPU: {cpu} % di un core",
        "rule": "Una scheda in background che non usi da {min} min viene sospesa e libera la memoria; quando torni, si ricarica nello stesso punto. Una scheda non viene mai sospesa mentre riproduce audio o video, o ha un modulo modificato o inviato, un download, la fotocamera, il microfono o la condivisione dello schermo.",
        "app": "app integrata", "media": "riproduzione", "form": "modulo in compilazione", "post": "modulo inviato",
        "download": "download", "capture": "fotocamera, microfono o schermo", "linked": "finestra collegata",
    },
}

#: Razlogi, zakaj zavihek ne sme zaspati (core/splet_spanje.razlogi_zascite), v vrstnem redu prikaza.
REASONS = ("media", "form", "post", "download", "capture", "linked")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@functools.lru_cache(maxsize=1)
def _tokens() -> str:
    """Barve iz enega vira (assets/os/tokens.css), kot predogled datotek in Splet; prebrane enkrat (stran se osvezi
    vsake 3 s)."""
    try:
        with open(os.path.join(_ROOT, "assets", "os", "tokens.css"), encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def _fmt_mb(mb, lang):
    if mb >= 1024:
        text = f"{mb / 1024:.2f} GB"
        return text if lang == "en" else text.replace(".", ",")     # decimalna vejica v vseh jezikih razen en
    return f"{mb} MB"


def _action(kind, tab_id, key):
    link = f"{PAGE_URI}?{kind}={urllib.parse.quote(tab_id, safe='')}"
    return link + (f"&k={urllib.parse.quote(key, safe='')}" if key else "")


def render(rows, lang="sl", limit_mb=0, cpu_budget=0.0, key="", sleep_minutes=0):
    """`rows`: list of dicts with id, title, cpu, rss_mb, threads, active, audio, sleeping, verdict and optionally
    pid (a process shared by two rows counts once in the total), app (embedded app: no actions) and reasons
    (keys of REASONS: why the tab may not sleep now). `key`: one-time key for the action links."""
    tx = _TEXT.get(lang, _TEXT["en"])
    body = []
    total_cpu = 0.0
    total_mb = 0
    counted = set()
    for row in sorted(rows, key=lambda r: (-(r.get("cpu") or 0.0), -(r.get("rss_mb") or 0))):
        tab_id = str(row.get("id", ""))
        cpu = float(row.get("cpu") or 0.0)
        mb = int(row.get("rss_mb") or 0)
        pid = row.get("pid") or 0
        if not pid or pid not in counted:
            total_cpu += cpu
            total_mb += mb
            if pid:
                counted.add(pid)
        sleeping = bool(row.get("sleeping"))
        app = bool(row.get("app"))
        reasons = [r for r in REASONS if r in (row.get("reasons") or ())]
        states = []
        if app:
            states.append(tx["app"])
        if row.get("active"):
            states.append(tx["active"])
        if row.get("audio"):
            states.append(tx["audio"])
        if sleeping:
            states.append(tx["sleeping"])
        states += [tx[r] for r in reasons if not (r == "media" and row.get("audio"))]
        verdict = row.get("verdict")
        if verdict in ("hot", "hog"):
            states.append(tx[verdict])
        klass = " class=\"hot\"" if verdict in ("hot", "hog") else ""
        measured = not sleeping and (pid or mb or cpu)
        cpu_text = f"{int(round(cpu * 100))} %" if measured else tx["no_process"]
        mem_text = _fmt_mb(mb, lang) if measured else tx["no_process"]
        threads = str(row.get("threads") or 0) if measured else tx["no_process"]
        actions = []
        if not app:
            if not sleeping and not row.get("active") and not row.get("audio") and not reasons:
                actions.append(f'<a href="{html.escape(_action("spi", tab_id, key))}">{tx["sleep"]}</a>')
            actions.append(f'<a href="{html.escape(_action("zapri", tab_id, key))}" class="close">{tx["close"]}</a>')
        body.append(
            f"<tr{klass}><td class=\"t\">{html.escape(str(row.get('title') or ''))}</td>"
            f"<td>{cpu_text}</td><td>{mem_text}</td><td>{threads}</td>"
            f"<td>{html.escape(', '.join(states))}</td><td>{' · '.join(actions)}</td></tr>"
        )
    body.append(
        f"<tr class=\"total\"><td class=\"t\">{tx['total']}</td><td>{int(round(total_cpu * 100))} %</td>"
        f"<td>{_fmt_mb(total_mb, lang)}</td><td></td><td></td><td></td></tr>"
    )
    limit_line = tx["limit"].format(limit=limit_mb, cpu=int(round(cpu_budget * 100))) if limit_mb else ""
    rule = f"<p class=\"rule\">{html.escape(tx['rule'].format(min=int(sleep_minutes)))}</p>" if sleep_minutes > 0 else ""
    nonce = secrets.token_urlsafe(12)
    return f"""<!doctype html>
<html lang="{html.escape(lang)}"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-{nonce}'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'">
<meta name="color-scheme" content="dark">
<title>Safeer · {tx['title']}</title>
<style>
{_tokens()}
  body {{ font-family: system-ui, sans-serif; background: var(--ozadje); color: var(--besedilo); margin: 0; padding: 32px; }}
  h1 {{ font-size: 22px; margin: 0 0 6px; }}
  p {{ color: var(--medlo); margin: 0 0 18px; max-width: 70ch; }}
  p.rule {{ color: var(--tise); font-size: 13px; }}
  table {{ border-collapse: collapse; width: 100%; max-width: 980px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--tanka); white-space: nowrap; }}
  td.t {{ white-space: normal; max-width: 40ch; overflow: hidden; text-overflow: ellipsis; }}
  th {{ color: var(--medlo); font-weight: 600; font-size: 13px; }}
  tr.hot td {{ color: var(--opozorilo); }}
  tr.total td {{ color: var(--medlo); font-weight: 600; border-top: 2px solid var(--rob); }}
  a {{ color: var(--zelena); text-decoration: none; border-radius: 4px; }} a.close {{ color: var(--rdeca); }}
  a:hover {{ text-decoration: underline; }}
  a:focus-visible {{ outline: 2px solid var(--fokus); outline-offset: 2px; }}
  .limit {{ color: var(--tise); font-size: 12px; margin-top: 14px; }}
</style></head><body>
<h1>🛡️ Safeer · {tx['title']}</h1>
<p>{tx['intro']}</p>
{rule}
<table><thead><tr><th scope="col">{tx['tab']}</th><th scope="col">{tx['cpu']}</th><th scope="col">{tx['memory']}</th><th scope="col">{tx['threads']}</th><th scope="col">{tx['state']}</th><th scope="col">{tx['actions']}</th></tr></thead>
<tbody>{''.join(body)}</tbody></table>
<div class="limit">{html.escape(limit_line)}</div>
<script nonce="{nonce}">
setInterval(function () {{
  var a = document.activeElement;
  if (document.hidden || (a && a !== document.body && a !== document.documentElement)) return;
  location.replace("{PAGE_URI}");
}}, {REFRESH_SECONDS * 1000});
</script>
</body></html>"""


def parse_action(uri):
    """Return ('spi'|'zapri', tab_id) for an action link, else (None, None)."""
    try:
        parsed = urllib.parse.urlparse(uri)
    except ValueError:
        return None, None
    if parsed.scheme != "safeer" or parsed.netloc != "procesi":
        return None, None
    query = urllib.parse.parse_qs(parsed.query)
    for key in ("spi", "zapri"):
        values = query.get(key)
        if values and values[0]:
            return key, values[0][:64]
    return None, None


def action_key(uri):
    """The one-time key (`k`) of an action link, or an empty string."""
    try:
        values = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query).get("k")
    except ValueError:
        return ""
    return values[0][:64] if values else ""
