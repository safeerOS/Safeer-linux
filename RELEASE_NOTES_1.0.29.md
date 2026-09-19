# Safeer Linux 1.0.29

**Saving a PDF works again, and in-page downloads are no longer blocked.**

- "Save" in the built-in PDF viewer (including your highlights, notes and drawings) did nothing: the browser's navigation guard blocked the viewer's own `blob:` address. Saving now goes to your Downloads folder under the document's file name (previously a generic `document.pdf`).
- The same guard silently blocked every download that a web page generates inside the browser (for example "export as CSV" buttons). Such downloads now work; `blob:` addresses are accepted only when they belong to the page's own origin or to the PDF viewer.

Slovensko: »Shrani« v vgrajenem pregledovalniku PDF (tudi z označbami, opombami in risbami) ni deloval, ker je varnostna zaščita blokirala pregledovalnikov lastni naslov `blob:`. Zdaj se PDF shrani v mapo Prenosi pod imenom dokumenta (prej splošni `document.pdf`). Ista zaščita je tiho blokirala tudi prenose, ki jih stran ustvari v brskalniku (npr. gumb »izvozi CSV«) — zdaj delujejo; naslovi `blob:` so dovoljeni samo, kadar pripadajo izvoru strani ali pregledovalniku PDF.
