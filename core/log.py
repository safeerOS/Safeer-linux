"""A small rotating log file for the browser's own messages.

The desktop launcher gives the browser no terminal: stdout ends in /dev/null and only stderr
reaches ~/.xsession-errors, so the diagnostics the code prints (a tab's web process stopping,
a filter list failing to compile, a memory limit being hit) were lost. `install()` keeps the
original streams and additionally writes every line to <config dir>/safeer.log, rotated at
1 MB with three backups. Callers keep using print(); nothing else in the code changes.

Only the browser's own messages land here. Page URLs appear only where the code already
prints them; the log is not a browsing history.
"""
import logging
import logging.handlers
import os
import sys
import threading

LOG_NAME = "safeer.log"
_LOGGER_NAME = "safeer"
_installed = False


class _Tee:
    """A text stream that forwards to the original stream and to the logger, line by line."""

    def __init__(self, original, level):
        self._original = original
        self._level = level
        self._buffer = ""
        self._lock = threading.Lock()

    def write(self, text):
        try:
            if self._original is not None:
                self._original.write(text)
        except Exception:  # noqa: BLE001 - a closed terminal must not break logging
            pass
        with self._lock:
            self._buffer += text
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line.strip():
                    logging.getLogger(_LOGGER_NAME).log(self._level, line.rstrip())
        return len(text)

    def flush(self):
        try:
            if self._original is not None:
                self._original.flush()
        except Exception:  # noqa: BLE001
            pass

    def isatty(self):
        try:
            return bool(self._original is not None and self._original.isatty())
        except Exception:  # noqa: BLE001
            return False

    def fileno(self):
        if self._original is None:
            raise OSError("no underlying stream")
        return self._original.fileno()

    @property
    def encoding(self):
        return getattr(self._original, "encoding", "utf-8")


def log_path(config_dir):
    return os.path.join(config_dir, LOG_NAME)


def install(config_dir, app_version=""):
    """Route print() output (stdout and stderr) into the rotating log file as well."""
    global _installed
    if _installed:
        return log_path(config_dir)
    try:
        os.makedirs(config_dir, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            log_path(config_dir), maxBytes=1024 * 1024, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname).1s %(message)s", "%Y-%m-%d %H:%M:%S"))
        logger = logging.getLogger(_LOGGER_NAME)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        logger.addHandler(handler)
        sys.stdout = _Tee(sys.__stdout__, logging.INFO)
        sys.stderr = _Tee(sys.__stderr__, logging.WARNING)
        _installed = True
        logger.info("Safeer Browser %s started (pid %d)", app_version, os.getpid())
        _crash_traces(config_dir)
    except Exception as exc:  # noqa: BLE001 - logging is best effort
        try:
            sys.__stderr__.write(f"[Log] Dnevnika ni bilo mogoče odpreti: {exc}\n")
        except Exception:  # noqa: BLE001
            pass
    return log_path(config_dir)


#: Sled sesutja (faulthandler) - odprta do konca procesa, sicer je ob SIGSEGV ne bi bilo kam zapisati.
SLED_NAME = "sled.log"
_sled = None


def _crash_traces(config_dir):
    """Safeer OS, Control in lupina so imeli sled vseh niti ob sesutju v knjiznici C (SIGSEGV, SIGABRT, SIGTRAP WebKita)
    in dnevnik neujetih izjem v nitih; Safeer Browser ne (revizija stabilnosti 20. 10. 2026) - sesutje je bilo brez sledi."""
    global _sled
    import faulthandler
    import signal
    import threading
    import traceback
    try:
        pot = os.path.join(config_dir, SLED_NAME)
        if os.path.exists(pot) and os.path.getsize(pot) > 1024 * 1024:
            os.replace(pot, pot + ".1")
        _sled = open(pot, "a", encoding="utf-8")  # noqa: SIM115 - odprta do konca procesa
        os.chmod(pot, 0o600)
        faulthandler.enable(file=_sled, all_threads=True)
        if hasattr(signal, "SIGTRAP"):
            faulthandler.register(signal.SIGTRAP, file=_sled, all_threads=True, chain=True)
    except (OSError, RuntimeError, ValueError) as exc:
        logging.getLogger(_LOGGER_NAME).warning("faulthandler: %s", exc)
    logger = logging.getLogger(_LOGGER_NAME)
    prej = sys.excepthook

    def neujeta(vrsta, vrednost, sled):
        logger.error("Neujeta izjema:\n%s", "".join(traceback.format_exception(vrsta, vrednost, sled)))
        prej(vrsta, vrednost, sled)
    sys.excepthook = neujeta

    def v_niti(args):
        if args.exc_type is SystemExit:
            return
        logger.error("Neujeta izjema v niti %s:\n%s", getattr(args.thread, "name", "?"),
                     "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))
    threading.excepthook = v_niti


def event(message, *args):
    """Log a line without going through print (for background threads)."""
    logging.getLogger(_LOGGER_NAME).info(message, *args)
