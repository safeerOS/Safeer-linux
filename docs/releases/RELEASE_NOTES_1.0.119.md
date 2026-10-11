# Safeer Browser for Linux 1.0.119 · Safeer Control 2.1.75 · Safeer OS 0.4.77

**Convert to … – checked on a real desktop and made friendlier.**

- *Convert to …* now appears only for files it can really convert. PDF, Markdown or SVG files no longer open a window that only says it cannot be done.
- The file name is shown exactly as written (before, the window title showed it in capital letters).
- After converting, the window shows the new file's name and a *Show in folder* button that opens the file manager with the file selected.
- When a file cannot be converted, the window says why in words (for example that the file may be damaged) instead of an internal code. The original always stays unchanged.
- Formats are laid out in a grid, *Close* is set apart, and Escape closes the window.
- In Files, the tooltip with a file's full name now appears only when the name is cut off – before, it could cover the right-click menu.

Tested with real files: JPG → WebP, PNG → JPG, FLAC → MP3, ODT → PDF (1.2 s), CSV → XLSX, and a damaged and an empty image.
