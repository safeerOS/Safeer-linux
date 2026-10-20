# Zapisi neodvisnih pregledov izdaj

Izdaja (oznaka `vX.Y.Z` ali `vX.Y.Z-beta.N`) nastane samo z zapisom `docs/pregledi/<oznaka>.md`, ki ga preveri
`tools/preveri_pregled.py` (pre-push in posel izdaje v CI). Pregleda pregledovalec drugega ponudnika kot avtor kode
(kodo pise Claude; pregleda npr. Gemini prek Pi). Po pregledanem commitu se smejo spremeniti samo datoteke izdaje
(ta zapis, opombe, stevilke razlicic, metainfo, README) - vsaka druga sprememba zahteva nov pregled.

Glava (vrstice pred prvo prazno vrstico):

```
Izdaja: v1.0.129
Commit: 1a2b3c4
Pregledovalec: Gemini prek Pi
Ponudnik: google
Odprte kriticne in visoke: 0

Povzetek pregleda in najdbe (kaj je bilo popravljeno, s commiti) ...
```

V zapis ne gredo imena ljudi, poti domace mape, imena naprav ali naslovi (AGENTS.md, Zasebnost).
