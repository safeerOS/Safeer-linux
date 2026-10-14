// Safeer: miska v pultu Cinnamona - nastavitve miske in baterija brezzicne miske na enem mestu.
//
// Lastnik, 14. 10. 2026: na racunalniku brez baterije je Mintov applet »Upravljanje porabe« kazal ikono baterije,
// ki je bila v resnici baterija miske - najprej je mislil, da je napaka. Ta applet kaze ikono miske, v meniju pa
// baterijo miske (ce jo javlja) in nastavitve, ki jih Cinnamon omogoca: hitrost, levicarska miska, naravno drsenje,
// srednji klik, pokazi kazalec s Ctrl, velikost kazalca in vse ostale nastavitve.
const Applet = imports.ui.applet;
const PopupMenu = imports.ui.popupMenu;
const Util = imports.misc.util;
const Gio = imports.gi.Gio;
const GLib = imports.gi.GLib;
const Mainloop = imports.mainloop;

// UPower prek D-Bus (asinhrono): UPowerGlib.get_devices2 v cjs vrne prazne predmete (preizkus 14. 10. 2026).
const UPOWER = "org.freedesktop.UPower";
const VRSTA_MISKA = 5;
// UpDeviceLevel: 0 neznano, 1 brez ravni (velja odstotek), 3 nizka, 4 kriticna, 6 normalna, 7 visoka, 8 polna.

const BESEDILA = {
    sl: { miska: "Miška", baterija: "Baterija", hitrost: "Hitrost kazalca", levicar: "Levičarska miška",
          naravno: "Naravno drsenje", srednji: "Srednji klik z levim in desnim gumbom",
          najdi: "Pokaži kazalec ob pritisku Ctrl", velikost: "Velikost kazalca", obicajen: "Običajen", velik: "Velik",
          zelo: "Zelo velik", vse: "Vse nastavitve miške …", logitech: "Logitech (Solaar) …",
          polna: "polna", visoka: "visoka", normalna: "normalna", nizka: "nizka", kriticna: "kritično nizka",
          neznana: "ni podatka" },
    en: { miska: "Mouse", baterija: "Battery", hitrost: "Pointer speed", levicar: "Left-handed mouse",
          naravno: "Natural scrolling", srednji: "Middle click with left and right button",
          najdi: "Show pointer when Ctrl is pressed", velikost: "Pointer size", obicajen: "Normal", velik: "Large",
          zelo: "Extra large", vse: "All mouse settings …", logitech: "Logitech (Solaar) …",
          polna: "full", visoka: "high", normalna: "normal", nizka: "low", kriticna: "critically low",
          neznana: "unknown" },
    de: { miska: "Maus", baterija: "Akku", hitrost: "Zeigergeschwindigkeit", levicar: "Linkshändermaus",
          naravno: "Natürliches Scrollen", srednji: "Mittelklick mit linker und rechter Taste",
          najdi: "Zeiger beim Drücken von Strg zeigen", velikost: "Zeigergröße", obicajen: "Normal", velik: "Groß",
          zelo: "Sehr groß", vse: "Alle Mauseinstellungen …", logitech: "Logitech (Solaar) …",
          polna: "voll", visoka: "hoch", normalna: "normal", nizka: "niedrig", kriticna: "kritisch niedrig",
          neznana: "unbekannt" },
    es: { miska: "Ratón", baterija: "Batería", hitrost: "Velocidad del puntero", levicar: "Ratón para zurdos",
          naravno: "Desplazamiento natural", srednji: "Clic central con botón izquierdo y derecho",
          najdi: "Mostrar el puntero al pulsar Ctrl", velikost: "Tamaño del puntero", obicajen: "Normal",
          velik: "Grande", zelo: "Muy grande", vse: "Todos los ajustes del ratón …", logitech: "Logitech (Solaar) …",
          polna: "llena", visoka: "alta", normalna: "normal", nizka: "baja", kriticna: "críticamente baja",
          neznana: "sin datos" },
    fr: { miska: "Souris", baterija: "Batterie", hitrost: "Vitesse du pointeur", levicar: "Souris pour gaucher",
          naravno: "Défilement naturel", srednji: "Clic du milieu avec les boutons gauche et droit",
          najdi: "Montrer le pointeur avec Ctrl", velikost: "Taille du pointeur", obicajen: "Normale",
          velik: "Grande", zelo: "Très grande", vse: "Tous les réglages de la souris …",
          logitech: "Logitech (Solaar) …", polna: "pleine", visoka: "élevée", normalna: "normale", nizka: "faible",
          kriticna: "critique", neznana: "inconnue" },
    it: { miska: "Mouse", baterija: "Batteria", hitrost: "Velocità del puntatore", levicar: "Mouse per mancini",
          naravno: "Scorrimento naturale", srednji: "Clic centrale con tasto sinistro e destro",
          najdi: "Mostra il puntatore premendo Ctrl", velikost: "Dimensione del puntatore", obicajen: "Normale",
          velik: "Grande", zelo: "Molto grande", vse: "Tutte le impostazioni del mouse …",
          logitech: "Logitech (Solaar) …", polna: "piena", visoka: "alta", normalna: "normale", nizka: "bassa",
          kriticna: "criticamente bassa", neznana: "sconosciuta" },
};

function jezik() {
    for (let ime of GLib.get_language_names()) {
        let j = String(ime).slice(0, 2).toLowerCase();
        if (BESEDILA[j]) return j;
    }
    return "en";
}

const T = BESEDILA[jezik()];
const MISKA = "org.cinnamon.desktop.peripherals.mouse";
const VMESNIK = "org.cinnamon.desktop.interface";
const VELIKOSTI = [[24, "obicajen"], [32, "velik"], [48, "zelo"]];

function nastavitve(shema) {
    let vir = Gio.SettingsSchemaSource.get_default();
    return vir && vir.lookup(shema, true) ? new Gio.Settings({ schema_id: shema }) : null;
}

class SafeerMiska extends Applet.TextIconApplet {
    constructor(metadata, orientation, visina, id) {
        super(orientation, visina, id);
        this.set_applet_icon_symbolic_name("input-mouse-symbolic");
        this.set_applet_tooltip(T.miska);
        this.miska = nastavitve(MISKA);
        this.vmesnik = nastavitve(VMESNIK);
        this.menuManager = new PopupMenu.PopupMenuManager(this);
        this.menu = new Applet.AppletPopupMenu(this, orientation);
        this.menuManager.addMenu(this.menu);
        this.miske = [];
        this._preberi_miske();
        this._casovnik = Mainloop.timeout_add_seconds(120, () => { this._preberi_miske(); return true; });
    }

    _klic(pot, vmesnik, metoda, argumenti, vrsta, ob) {
        Gio.DBus.system.call(UPOWER, pot, vmesnik, metoda, argumenti, new GLib.VariantType(vrsta),
                             Gio.DBusCallFlags.NONE, 3000, null, (vir, izid) => {
            let v = null;
            try { v = vir.call_finish(izid).recursiveUnpack(); } catch (e) { v = null; }
            ob(v);
        });
    }

    _preberi_miske() {
        this._klic("/org/freedesktop/UPower", UPOWER, "EnumerateDevices", null, "(ao)", (v) => {
            let poti = v ? v[0] : [];
            let najdene = [], ostalo = poti.length;
            if (!ostalo) { this.miske = []; this._osvezi_ikono(); return; }
            for (let pot of poti) {
                this._klic(pot, "org.freedesktop.DBus.Properties", "GetAll",
                           new GLib.Variant("(s)", [UPOWER + ".Device"]), "(a{sv})", (l) => {
                    let p = l ? l[0] : null;
                    if (p && p.Type === VRSTA_MISKA)
                        najdene.push({ model: p.Model || "", raven: p.BatteryLevel || 0, odstotek: p.Percentage || 0 });
                    if (--ostalo === 0) { this.miske = najdene; this._osvezi_ikono(); }
                });
            }
        });
    }

    _miske() { return this.miske; }

    _raven(n) {
        let ravni = { 8: T.polna, 7: T.visoka, 6: T.normalna, 3: T.nizka, 4: T.kriticna };
        if (ravni[n.raven]) return ravni[n.raven];
        if (n.raven === 1 && n.odstotek > 0) return Math.round(n.odstotek) + " %";
        return T.neznana;          // 0: miska ravni (se) ni javila
    }

    _nizka(n) {
        return n.raven === 3 || n.raven === 4 || (n.raven === 1 && n.odstotek > 0 && n.odstotek <= 15);
    }

    _osvezi_ikono() {
        let miske = this._miske();
        let opis = [T.miska];
        let nizka = false;
        for (let n of miske) {
            opis.push((n.model || T.miska) + " · " + T.baterija + ": " + this._raven(n));
            nizka = nizka || this._nizka(n);
        }
        this.set_applet_tooltip(opis.join("\n"));
        // Ikona ostane miska; ko je baterija nizka, se doda kratko opozorilo.
        this.set_applet_label(nizka ? T.nizka : "");
    }

    _stikalo(besedilo, kljuc) {
        let p = new PopupMenu.PopupSwitchMenuItem(besedilo, this.miska.get_boolean(kljuc));
        p.connect("toggled", (_i, stanje) => this.miska.set_boolean(kljuc, stanje));
        this.menu.addMenuItem(p);
    }

    _napolni() {
        this.menu.removeAll();
        for (let n of this._miske()) {
            let p = new PopupMenu.PopupMenuItem((n.model || T.miska) + " — " + T.baterija + ": " + this._raven(n),
                                                { reactive: false });
            this.menu.addMenuItem(p);
        }
        if (this.miska) {
            if (this._miske().length) this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
            this.menu.addMenuItem(new PopupMenu.PopupMenuItem(T.hitrost, { reactive: false }));
            let drsnik = new PopupMenu.PopupSliderMenuItem((this.miska.get_double("speed") + 1) / 2);
            drsnik.connect("value-changed", (_d, v) => this.miska.set_double("speed", Math.max(-1, Math.min(1, v * 2 - 1))));
            this.menu.addMenuItem(drsnik);
            this._stikalo(T.levicar, "left-handed");
            this._stikalo(T.naravno, "natural-scroll");
            this._stikalo(T.srednji, "middle-click-emulation");
            this._stikalo(T.najdi, "locate-pointer");
        }
        if (this.vmesnik) {
            this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
            this.menu.addMenuItem(new PopupMenu.PopupMenuItem(T.velikost, { reactive: false }));
            let zdaj = this.vmesnik.get_int("cursor-size");
            for (let [px, kljuc] of VELIKOSTI) {
                let p = new PopupMenu.PopupMenuItem((zdaj === px ? "✓  " : "     ") + T[kljuc]);
                p.connect("activate", () => this.vmesnik.set_int("cursor-size", px));
                this.menu.addMenuItem(p);
            }
        }
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        if (GLib.find_program_in_path("solaar")) {
            let s = new PopupMenu.PopupMenuItem(T.logitech);
            s.connect("activate", () => Util.spawn(["solaar"]));
            this.menu.addMenuItem(s);
        }
        let vse = new PopupMenu.PopupMenuItem(T.vse);
        vse.connect("activate", () => Util.spawn(["cinnamon-settings", "mouse"]));
        this.menu.addMenuItem(vse);
    }

    on_applet_clicked() {
        if (!this.menu.isOpen) {
            this._napolni();
            this._preberi_miske();
        }
        this.menu.toggle();
    }

    on_applet_removed_from_panel() {
        if (this._casovnik) Mainloop.source_remove(this._casovnik);
        this._casovnik = 0;
    }
}

function main(metadata, orientation, visina, id) {
    return new SafeerMiska(metadata, orientation, visina, id);
}
