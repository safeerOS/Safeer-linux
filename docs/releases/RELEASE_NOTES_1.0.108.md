# Safeer Browser for Linux 1.0.108 · Safeer Control 2.1.64 · Safeer OS 0.4.66

## Safeer OS 0.4.66

### The built-in browser opens again in installed packages

Since the built-in browser was introduced (the change is dated 28 September 2026), the installed Safeer OS package has been missing one module (`core/webkit_filters.py`). The browser code is loaded only when Web is opened for the first time, so the import failed at that moment and Safeer OS answered "This could not be opened." Started from the source tree everything worked, which is why no test showed it. Found on 7 October 2026 in a test installation made with the release packaging script; an installed 0.4.65 on a real computer had the same file missing and failed with the same import error.

- **The module is in the package.** A new test (`tests/test_tovor_uvozi.py`) reads the packaged files and collects their imports of Safeer's own modules – also imports inside functions, which the existing packaging test does not trigger, and imports made with `__import__("…")` or `importlib.import_module("…")` – and fails when a module is missing from the hand-written package lists of Safeer OS or Safeer Control. An import counts as optional only inside a `try` that catches the import error itself; `try … except Exception` does not make it optional. For Safeer OS the test also checks that the data files the packaged modules read (the bank catalogue, the BankGuard page script, the browser's start page with its style sheet, script and picture) are copied. It does not see an import whose module name is computed at run time. A check of the test itself: with the threat-list module removed from the package list, the first version of the test still passed; the present one fails.
- **Safeer OS no longer closes when the browser sandbox cannot start.** WebKitGTK starts its sandbox (bubblewrap) with the first sandboxed view; where the kernel does not allow unprivileged user namespaces (containers, some hardened kernels) WebKitGTK terminates the whole process. Measured in a test container: a click on Web closed Safeer OS. Safeer OS now checks, in a separate process, whether the sandbox can start; if not, it creates neither the built-in browser nor the light media view (an embedded page, the built-in player of a playlist track) and says why ("The web can't be opened: this system doesn't allow the browser's security sandbox"). A positive result holds for the whole run; a negative one is checked again on the next attempt made 30 seconds or more later, so that one failed check does not switch the browser off until Safeer OS is restarted. In the media centre the general "could not be played" notice is not shown within one second after the explanation, so that it does not replace it (a timing rule, covered by a check of the source only). On a computer with Linux Mint 22.3 a sandboxed view starts normally (checked with a separate process, without touching the running Safeer OS). Not measured live: the explanation in the media centre (the test container has no network for the catalogue).
- **The toolbar is painted on first opening.** When the browser was first opened from another section (a link in a message), parts of its toolbar stayed unpainted until the window was resized. Measured in a test session without a compositor; the window is now repainted after the browser appears.
- **A page without a background of its own is readable – in both colour schemes.** The web view was given a dark background so that opening a page does not flash white; a page that sets no background (plain HTML, a text file, the engine's own "page could not be loaded" page) was then dark with black text. The view is now white under web pages and dark only under Safeer's own pages. White has to be in place before the page's document exists: WebKitGTK replaces it with its own dark base when a page declares a dark colour scheme (`color-scheme: dark`) – unless the view colour is set after that, which overrides the dark base and leaves white text on white. The colour is therefore set when the navigation is decided and when loading starts, and never again for the same kind of page. Measured on WebKitGTK 2.52.6 with four kinds of page (no scheme, `<meta name="color-scheme" content="dark">`, `light dark`, `:root { color-scheme: dark }`) in three sequences (start page → web, web → web, Back), with the light and the dark desktop theme: all readable; checked again in the installed built-in browser and in Safeer Browser. Unchanged: an empty view (`about:blank`) counts as Safeer's own and keeps the dark base – how a pop-up that a page opens empty and fills by script looks was not measured.

### Messages: text can be selected and copied

Until 0.4.65 the whole page was unselectable, the system context menu is switched off in the shell and a message had no menu of its own: a message could not be copied.

- Select text with the mouse – also across several messages; time stamps are not included – and press Ctrl+C.
- Right-click, the Menu key or Shift+F10 on a message: **Copy message**, **Copy selection** (when something is selected), **Open link** (when the message is a single web link).
- Ctrl+C on a message that has the focus, with nothing selected, copies the whole message. Up and Down move between messages; the message with the focus has a visible outline and only the list scrolls, not the page.
- A long message is copied whole (it was cut at 8192 characters).
- The mouse wheel at the end of the message list no longer starts scrolling the page.

**Open link shows where the link leads.** The text of a message comes from somewhere else (e-mail, chat, another device) and can be written to mislead. Therefore:

- the menu item names the host that will be opened, as the browser itself understands the address – **Open link · other.example**. This also holds when the text uses look-alike characters: a host in another script is shown in its encoded form (`xn--…`), a numeric address in its plain form, and of a very long host the end stays visible;
- the link is not offered at all with a user name or password in front of the host (`https://bank.example@other.example/` leads to `other.example`), with a backslash, or with invisible characters, control characters or characters that change the direction of writing;
- only `http` and `https`; the case of the scheme does not matter (`Https://…`, as phone keyboards write it, was offered before but then did nothing);
- the link opens in a new tab of the built-in browser, so the page that is open there stays (a tab that shows the start page or is empty is reused); when an address cannot be opened, Safeer OS says so instead of doing nothing.

After Open link, Messages no longer counts as open: a message that arrives while you browse stays unread. When you return to Messages and the open conversation has a new message, the view moves to it.

**The conversation stays where you read it.** A refresh (every 30 seconds while Messages is open, and after sending) keeps the messages already on the screen as the same elements and only adds, inserts or removes what changed:

- a selection and an open menu survive a new message – also a message that was delivered late and is sorted in between the others;
- what you are reading stays in place when the oldest message leaves the list (a conversation shows the last 50) or a late message is inserted above it;
- opening a conversation shows its last message, and so does sending one – also when you were reading older messages;
- an answer that arrives late no longer replaces a newer one.

Measured on 7 October 2026 in the test container (WebKitGTK 2.52.6), with the real style sheets and the real code:

| Case | Before this fix | Now |
| --- | --- | --- |
| Oldest message (508 px high) leaves the list while reading 100 px above the end | view jumped by 418 px | 0 px |
| The same while selecting text at the end | jumped by 518 px | 0 px, selection kept |
| A late message is inserted above what is being read, text selected, menu open | everything redrawn: selection lost, menu closed, view moved | 0 px, selection and menu kept |
| A message is sent while reading older messages (the list answers first) | the sent message was not shown | shown |

Also measured live there, in Safeer OS installed with the packaging script: word selection and Ctrl+C, the whole message from the menu (11 729 characters), a selection across messages, the menu from the keyboard, focus returning to the message after a menu action, Up/Down between messages, the wheel at the top end of the list; a deceptive link (`https://…@…`) offers only Copy message; `Http://…` opens; a second link opens in a new tab and the first page stays; a message that arrived while the browser was open stayed unread (48 seconds, longer than the refresh interval) and was shown and marked read on return; with the conversation scrolled up, leaving Messages and returning after a new message arrived showed that message. What the address check does with 24 deceptive and unusual addresses was measured in WebKitGTK's own address parser (the tests in the suite use the parser of Node.js). Not measured separately in the full-screen desktop mode and in languages other than Slovenian (the texts exist in all six languages and are checked by a test); the "could not be opened" notice after Open link is covered by tests only.

### Media centre: nothing has to be scrolled sideways

- **On your devices** is a grid like the catalogue instead of a shelf that scrolled to the right: two rows; when there is more, the last cell is **Show all** (and **Show less** afterwards).
- Genres wrap onto several lines instead of scrolling sideways.
- The number of columns is taken from the browser, not calculated from the width: the calculation ignored the grid's side padding and, in a band of widths, counted one column more than the style sheet – three rows instead of two. Measured in WebKitGTK over 1251 widths: 28 disagreed before, none now. The grid is also drawn again when its width changes without the window changing – the page gets a scroll bar once the catalogue is drawn below it, or the section was not visible when the grid was drawn. Measured: three rows in both cases before, two now.

Checked by rendering the real style sheets and the real drawing code with sample content in WebKitGTK; not checked with a real library spread over several devices.

## Ctrl+C with nothing selected no longer empties the clipboard

WebKitGTK writes an empty clipboard when Copy (Ctrl+C) is used while nothing is selected: whatever was copied before – also in another program – is lost. Measured on WebKitGTK 2.52.6 with a page that contains no script at all; in the engine's source the cause is present from 2.48 (`Editor::canCopy` returns true for a caret outside an editable field, and writing an empty selection clears the clipboard on GTK).

Every web view of Safeer on Linux – the Safeer OS shell, the built-in browser, the media view, Safeer Browser (tabs, side panel), the Safeer Link window and the shared-screen viewer of Safeer Control – now carries a small script in its own script world. On a `copy` event with nothing selected and no text field in focus it cancels the default action; a cancelled event without data leaves the clipboard untouched (in the engine's source at least since 2.38, so nothing changes on older engines). Pages that handle `copy` themselves (spreadsheets, drawing tools) work as before: the script runs after their listeners and steps aside when they have already cancelled the event. Where it cannot know whether something is selected (a text field, a custom element that may hide a closed shadow tree, a stand-alone image) it does nothing. "Something is selected" is decided by the selection's type, range and text: a selection inside a shadow tree looks collapsed from outside, so its text is checked as well. A selection left behind in a part of the page that is no longer displayed – text selected in a message, then another section opened – has no text, nothing drawn, and both of its ends lie in the part that is not displayed; the engine still reports it as a selection and Copy emptied the clipboard. It now counts as "nothing selected"; a selection without text but with something drawn (an image) is left to the browser.

Measured live in the test container: empty area + Ctrl+C keeps the clipboard, both when another program put the text there and when it was copied in the same view a moment earlier (shell, built-in browser, Safeer Browser); a selected word is copied (page text, text field, and plain text inside an open shadow tree, a closed one on a `<div>` and a closed one on a custom element); a caret in a text field changes nothing; a page with its own `copy` handler still fills the clipboard; Ctrl+A and Ctrl+C in the Safeer OS shell keep the clipboard; on a test page that carries the script, a selection in a part of the page that was then hidden + Ctrl+C keeps it (it was emptied before this fix) and a selected image is still copied. Measured on one engine version (2.52.6, X11); the packages use the system's WebKitGTK. Not covered: a selection inside content hidden with `visibility: hidden` (not measured).

## Safeer Control 2.1.64

- **Closing the window with another device's screen ends the session on that device.** Until 2.1.63 the device was told nothing. Measured on 7 October 2026: after the "Open here" window was closed on the computer, a tablet kept sharing its screen (the sharing service stayed in the foreground) and the game kept running. Control now sends the command `apps.close` with `stream: true` – "I no longer watch this screen". Whether the session was opened with "Open here", and the app therefore has to leave the screen, is decided by the device from its own record of the session; the computer does not claim it. When the device ends the sharing itself, nothing is sent. The device needs a Safeer OS release that knows the command (planned: 0.5.66); what released versions do with it was not measured. A computer that shares its screen does not end the sharing on this command yet.
- **The window remembers which device it shows.** There is one viewer window. When a second device starts sharing and the window switches to it, the first device is now told that it is no longer watched (before, it kept sharing unseen). Touches and keys from the window are passed on only while the device the window shows is also the one Safeer Link counts as watched; closing the window tells the device it shows and the device Safeer Link counts as watched (normally the same one); quitting Safeer Control with the window open tells the device before the connection closes (it waits at most one second).
- The clipboard fix above also applies to the windows of Safeer Control.

**Covered by tests; not yet verified end to end on real devices.** Known limits with two devices sharing at the same time, unchanged from 2.1.63: which device the window shows is taken from Safeer Link at the moment the viewer page opens, so when two devices start sharing within about a second, the window can show the first while touches go to the second; and when the second device's sharing ends before its page has opened, the window closes and the first device is not told.

## Safeer Browser 1.0.108

- The clipboard fix above (Ctrl+C with nothing selected).
- A page without a background of its own is readable, in the light and in the dark colour scheme (see above). The process list (`safeer://procesi`), which paints its own dark background, keeps the dark view colour.
- **Force dark mode keeps pages readable.** The mode (off by default) puts a colour filter on the page. Until 1.0.107 its style sheet also forced a "dark" background on the page's root element. The filter inverts that background too, so it came out light grey: a page without a background of its own, and a page with its own light background on the root element, were light grey with light text. The style sheet now sets only the filter. The page keeps its own background and colour scheme; a page without a background takes the white view colour; the filter then inverts background and text together. Measured on WebKitGTK 2.52.6 with twelve kinds of page (no background; a dark colour scheme declared in three ways; an own dark background on the root element in three forms; a dark scheme with its own light text; an ordinary light page; a light background on the root element; a dark background on the body, over the full height and on a short page), the style sheet applied both ways the browser applies it: with the old style sheet 10 of the 12 were readable (dark desktop theme), with the new one all 12 (dark and light desktop theme). A light page comes out dark. A page that is dark by itself comes out light with dark text – the mode does not recognise pages that are already dark (as before).

## Pre-release review

The changes of this release were given four times to a reviewer separate from development (internal reviews, not an external audit). Every finding was checked by a test that failed first or by a measurement.

Second review (interrupted after five findings):

1. The sandbox check did not cover the media view – confirmed in the code, fixed, test added.
2. A cancelled copy might still empty the clipboard when the text had been copied in the same view – not reproduced: measured, the clipboard is kept.
3. The clipboard script might cancel a copy of text selected inside a shadow tree – not reproduced on WebKitGTK 2.52.6; the script now also checks the selection's text so that this does not depend on one engine version.
4. White view background and pages with a dark colour scheme – confirmed by measurement, fixed.
5. The record of "Open here" in Safeer Control could go stale – confirmed in the code, removed.

Third review (complete; it read the code and ran nothing, so each point was then measured or tested here):

1. "Open link" accepted deceptive addresses and replaced the page open in the browser – confirmed, fixed.
2. A link with a capitalised scheme was offered and then did nothing; a refused address gave no notice – confirmed, fixed.
3. After "Open link" new messages were marked read unseen – confirmed in the code, fixed, measured live.
4. The view jumped when the oldest message left the list; a late message redrew the conversation – confirmed by measurement (table above), fixed.
5. The sent message was not shown when the list answered first – confirmed by measurement, fixed.
6. Force dark mode on the white view colour – measured: the fault exists, is older than this release and independent of the view colour; fixed (see the fourth review).
7. Internal pages outside the page folder counted as web pages – confirmed in the code; they paint their own background, so nothing was unreadable.
8. The viewer window and a second sharing device – confirmed in the code, improved, covered by tests only (limits above).
9. The grid's column count disagreed with the style sheet – confirmed by measurement, fixed.
10. The package test treated too much as optional and missed some imports – confirmed (the check described above), fixed.
11. A negative sandbox check held for the whole run – confirmed in the code, fixed.

Also from the third review: a selection without copyable text – measured: Ctrl+A on an unselectable page selects nothing (clipboard kept), a selection in a hidden part of the page emptied the clipboard; fixed.

Fourth review (of the fixes above; complete, read the code and ran nothing). It found no address for which the label of Open link differs from the host that is opened. Its findings:

1. The first fix of force dark mode forced a white background and a light colour scheme on the root element; pages with their own dark background there and light text became dark with dark text – confirmed by measurement (4 of the 12 kinds of page unreadable). Replaced by the style sheet described above.
2. On return to Messages a new message was read (and so marked read) but the view could stay away from it – confirmed in a model of the list; fixed and measured live.
3. The viewer window infers the device it shows – confirmed in the code; not changed in this release (limits above).
4. The grid's column check ran before the catalogue was drawn – confirmed by measurement (the grid made narrower by the width of a scroll bar after drawing: three rows), fixed.
5. Statements in these notes that claimed more than the code does – corrected.
6. Smaller points, fixed: the one-second rule for the sandbox notice (it was three seconds); the hidden-selection rule now also requires both ends of the selection to lie in a part that is not displayed; the process list is the only internal page that keeps the dark view colour (a placeholder page without a background would otherwise get it too – from the code, not measured); a failed request for a conversation no longer leaves "show the last message" pending.

Not changed after the reviews: the sandbox check runs on the main thread (up to 8 seconds when bubblewrap hangs instead of failing, and again on an attempt made 30 seconds or more later); a device whose share cannot be displayed is not told to stop; the end of sharing sent by a device is not checked against the device that is being watched.
