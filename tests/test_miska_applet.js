// Preizkus appleta Safeer Miska v Node brez Cinnamona: lazni imports (Applet, PopupMenu, Gio ...).
// Uporaba: node tests/test_miska_applet.js <applet.js> -> izpis JSON (tests/test_delovna.py).
const fs = require("fs");
const izvor = fs.readFileSync(process.argv[2], "utf8");
const izid = { prebrani: [], stikala: [], dbus_po_odstranitvi: 0, napaka: "" };
// Starejsa shema cinnamon-desktop: brez locate-pointer in middle-click-emulation.
const KLJUCI = new Set(["speed", "left-handed", "natural-scroll"]);

class Nastavitve {
    constructor(o) {
        this.id = o.schema_id;
        this.settings_schema = { has_key: (k) => this.id.endsWith("interface") || KLJUCI.has(k) };
    }
    _preveri(k) {
        izid.prebrani.push(k);
        if (!this.settings_schema.has_key(k)) throw new Error("g_error: kljuc " + k);
    }
    get_boolean(k) { this._preveri(k); return false; }
    get_double(k) { this._preveri(k); return 0; }
    get_int(k) { this._preveri(k); return 24; }
}

const cakajoci = [];
class Meni {
    constructor() { this.isOpen = false; this.uniceno = false; }
    addMenuItem() {}
    removeAll() {}
    toggle() {}
    destroy() { this.uniceno = true; }
}
class Element { constructor(b) { this.b = b; } connect() {} }
class Stikalo extends Element { constructor(b) { super(b); izid.stikala.push(b); } }

const imports = {
    ui: {
        applet: {
            TextIconApplet: class { set_applet_icon_symbolic_name() {} set_applet_tooltip() {} set_applet_label() {} },
            AppletPopupMenu: Meni,
        },
        popupMenu: {
            PopupMenuManager: class { addMenu() {} removeMenu() {} },
            PopupMenuItem: Element, PopupSeparatorMenuItem: Element, PopupSliderMenuItem: Element,
            PopupSwitchMenuItem: Stikalo,
        },
    },
    misc: { util: { spawn() {} } },
    gi: {
        Gio: {
            SettingsSchemaSource: { get_default: () => ({ lookup: () => true }) }, Settings: Nastavitve,
            DBus: { system: { call: (...a) => cakajoci.push(a[a.length - 1]) } }, DBusCallFlags: { NONE: 0 },
        },
        GLib: {
            get_language_names: () => ["sl_SI.UTF-8"], VariantType: class {}, Variant: class {},
            find_program_in_path: () => null,
        },
    },
    mainloop: { timeout_add_seconds: () => 1, source_remove() {} },
};

try {
    const main = new Function("imports", izvor + "\nreturn main;")(imports);
    const a = main({}, 0, 24, 1);
    a.on_applet_clicked();                     // _napolni: manjkajoci kljuci se preskocijo
    const meni = a.menu;
    a.on_applet_removed_from_panel();
    izid.meni_unicen = meni.uniceno;
    // Odgovor D-Bus pride po odstranitvi: ne sme sprozati novih klicev.
    const vir = { call_finish: () => ({ recursiveUnpack: () => [["/org/freedesktop/UPower/devices/miska"]] }) };
    for (const ob of cakajoci.splice(0)) ob(vir, null);
    izid.dbus_po_odstranitvi = cakajoci.length;
} catch (e) {
    izid.napaka = String(e);
}
console.log(JSON.stringify(izid));
