# Safeer Browser for Linux 1.0.108 · Safeer Control 2.1.64 · Safeer OS 0.4.66

## Safeer OS 0.4.66

### The built-in browser opens again in installed packages

Since the built-in browser was introduced (the change is dated 28 September 2026), the installed Safeer OS package has been missing one module (`core/webkit_filters.py`). The browser code is loaded only when Web is opened for the first time, so the import failed at that moment and Safeer OS answered "This could not be opened." Started from the source tree everything worked, which is why no test showed it. Found on 7 October 2026 in a test installation made with the release packaging script; an installed 0.4.65 on a real computer had the same file missing and failed with the same import error.

- **The module is in the package.** A new test (`tests/test_tovor_uvozi.py`) walks every import in the packaged files – also imports inside functions, which the existing packaging test does not trigger – and fails when a module is missing from the hand-written package lists of Safeer OS or Safeer Control.
- **Safeer OS no longer closes when the browser sandbox cannot start.** WebKitGTK starts its sandbox (bubblewrap) with the first sandboxed view; where the kernel does not allow unprivileged user namespaces (containers, some hardened kernels) WebKitGTK terminates the whole process. Measured in a test container: a click on Web closed Safeer OS. Safeer OS now checks once, in a separate process, whether the sandbox can start; if not, it creates neither the built-in browser nor the light media view (an embedded page, the built-in player of a playlist track) and says why ("The web can't be opened: this system doesn't allow the browser's security sandbox"). The media view was added to this check after the pre-release review found it unguarded. On a computer with Linux Mint 22.3 a sandboxed view starts normally (checked with a separate process, without touching the running Safeer OS).
- **The toolbar is painted on first opening.** When the browser was first opened from another section (a link in a message), parts of its toolbar stayed unpainted until the window was resized. Measured in a test session without a compositor; the window is now repainted after the browser appears.
- **A page without a background of its own is readable – in both colour schemes.** The web view was given a dark background so that opening a page does not flash white; a page that sets no background (plain HTML, a text file, the engine's own "page could not be loaded" page) was then dark with black text. The view is now white under web pages and dark only under Safeer's own start page. White has to be in place before the page's document exists: WebKitGTK replaces it with its own dark base when a page declares a dark colour scheme (`color-scheme: dark`) – unless the view colour is set after that, which overrides the dark base and leaves white text on white. The first version of this change set the colour when the page was already shown; the pre-release review predicted the fault and a measurement confirmed it (pages with a dark scheme and no background were white on white after leaving the start page, and at times after Back). The colour is now set when the navigation is decided and when loading starts, and never again for the same kind of page. Measured on WebKitGTK 2.52.6 with four kinds of page (no scheme, `<meta name="color-scheme" content="dark">`, `light dark`, `:root { color-scheme: dark }`) in three sequences (start page → web, web → web, Back), with the light and the dark desktop theme: all readable; checked again in the installed built-in browser and in Safeer Browser.

### Messages: text can be selected and copied

Until 0.4.65 the whole page was unselectable, the system context menu is switched off in the shell and a message had no menu of its own: a message could not be copied.

- Select text with the mouse – also across several messages; time stamps are not included – and press Ctrl+C.
- Right-click, the Menu key or Shift+F10 on a message: **Copy message**, **Copy selection** (when something is selected), **Open link** (when the message is a single web link; it opens in the built-in browser).
- Ctrl+C on a message that has the focus, with nothing selected, copies the whole message. Up and Down move between messages; the message with the focus has a visible outline and only the list scrolls, not the page.
- A long message is copied whole (it was cut at 8192 characters).
- The conversation is no longer rebuilt on every refresh (every 30 seconds): a selection survives a new message, and the view does not jump while you read older messages or select text. Opening a conversation shows its last message.
- The mouse wheel at the end of the message list no longer starts scrolling the page.

Measured live on 7 October 2026 in the test container (installed with the packaging script, WebKitGTK 2.52.6): word selection and Ctrl+C, the whole message from the menu (11 729 characters), a selection across messages, the menu from the keyboard including Open link, focus returning to the message after a menu action, Up/Down between messages, a selection surviving a new message, the wheel at the top end of the list (the page stays in place). Not measured separately in the full-screen desktop mode and in languages other than Slovenian (the texts exist in all six languages and are checked by a test).

### Media centre: nothing has to be scrolled sideways

- **On your devices** is a grid like the catalogue instead of a shelf that scrolled to the right: two rows; when there is more, the last cell is **Show all** (and **Show less** afterwards).
- Genres wrap onto several lines instead of scrolling sideways.

Checked by rendering the real style sheets with sample content in WebKitGTK; not checked with a real library spread over several devices.

## Ctrl+C with nothing selected no longer empties the clipboard

WebKitGTK writes an empty clipboard when Copy (Ctrl+C) is used while nothing is selected: whatever was copied before – also in another program – is lost. Measured on WebKitGTK 2.52.6 with a page that contains no script at all; in the engine's source the cause is present from 2.48 (`Editor::canCopy` returns true for a caret outside an editable field, and writing an empty selection clears the clipboard on GTK).

Every web view of Safeer on Linux – the Safeer OS shell, the built-in browser, the media view, Safeer Browser (tabs, side panel), the Safeer Link window and the shared-screen viewer of Safeer Control – now carries a small script in its own script world. On a `copy` event with nothing selected and no text field in focus it cancels the default action; a cancelled event without data leaves the clipboard untouched (in the engine's source at least since 2.38, so nothing changes on older engines). Pages that handle `copy` themselves (spreadsheets, drawing tools) work as before: the script runs after their listeners and steps aside when they have already cancelled the event. Where it cannot know whether something is selected (a text field, a custom element that may hide a closed shadow tree, a stand-alone image) it does nothing. "Something is selected" is decided by the selection's type, range and text: a selection inside a shadow tree looks collapsed from outside, so its text is checked as well.

Measured live in the test container: empty area + Ctrl+C keeps the clipboard, both when another program put the text there and when it was copied in the same view a moment earlier (shell, built-in browser, Safeer Browser); a selected word is copied (page text, text field, and plain text inside an open shadow tree, a closed one on a `<div>` and a closed one on a custom element); a caret in a text field changes nothing; a page with its own `copy` handler still fills the clipboard.

## Safeer Control 2.1.64

- **Closing the window with another device's screen ends the session on that device.** Until 2.1.63 the device was told nothing. Measured on 7 October 2026: after the "Open here" window was closed on the computer, a tablet kept sharing its screen (the sharing service stayed in the foreground) and the game kept running. Control now sends the command `apps.close` with `stream: true` – "I no longer watch this screen". Whether the session was opened with "Open here", and the app therefore has to leave the screen, is decided by the device from its own record of the session; the computer does not claim it (a first version sent the app's name, and the pre-release review showed how that record could go stale and send a device to its home screen during a share its owner had started). When the device ends the sharing itself, nothing is sent. The device needs a Safeer OS release that knows the command (planned: 0.5.66); older releases do not know the command and keep sharing as before. **Covered by tests; not yet verified end to end on real devices.**
- The clipboard fix above also applies to the windows of Safeer Control.

## Safeer Browser 1.0.108

- The clipboard fix above (Ctrl+C with nothing selected).
- A page without a background of its own is readable, in the light and in the dark colour scheme (see above). Not measured: such pages with the browser's own "force dark mode" switched on.

## Pre-release review

The changes of this release were given to a reviewer separate from development (an internal review, not an external audit). The review was interrupted after five findings; each was checked by a test that failed first or by a measurement:

1. The sandbox check did not cover the media view – confirmed in the code, fixed, test added.
2. A cancelled copy might still empty the clipboard when the text had been copied in the same view – not reproduced: measured, the clipboard is kept.
3. The clipboard script might cancel a copy of text selected inside a shadow tree – not reproduced on WebKitGTK 2.52.6 (the three cases above copy correctly); the script now also checks the selection's text so that this does not depend on one engine version.
4. White view background and pages with a dark colour scheme – confirmed by measurement, fixed (above).
5. The record of "Open here" in Safeer Control could go stale – confirmed in the code, removed (above).

Not covered by this review: the Messages page (how message text and links are handled), keyboard handling, the incremental refresh, the media-centre grid and the new tests. The author's own check of the Messages code: message text is inserted as text, never as markup; "Open link" is offered only when the whole message is one `http://` or `https://` address.
