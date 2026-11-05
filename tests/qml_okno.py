"""Enotno pospravljanje namizja QML (os_lupina.Namizje in njegov QQuickView) v preizkusih (5. 11. 2026).

Okno, ki ga preizkus samo zapre (close) ali pusti, ostane v krogu sklicev Namizje <-> Most <-> zaprtja, njegovi
casovniki QML pa tecejo naprej v naslednjih preizkusih (»Most … of null«), dokler ga ne pobere kasnejsi gc.collect().
Zato vsak preizkus okno pospravi sam, takoj in v glavni niti: prazen vir unici koren QML in njegove casovnike, nato
zapri in izbrisi (odlozeno brisanje izvedemo takoj, ne sele v kateri od kasnejsih zank).
"""
import gc


def pospravi_namizje(n) -> None:
    import shiboken6
    from PySide6.QtCore import QCoreApplication, QEvent, QUrl
    okno = getattr(n, "okno", None)
    if okno is None or not shiboken6.isValid(okno):
        return
    okno.setSource(QUrl())
    okno.close()
    okno.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()


def pospravi_ob_koncu(test, n):
    """Namizje n pospravi ob koncu preizkusa (addCleanup: pred koncem zakrp, ki so bile nastavljene prej)."""
    test.addCleanup(pospravi_namizje, n)
    return n
