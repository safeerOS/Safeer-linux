// Preneseno iz src/main/kotlin/si/safeer/tv/os/PredvajajNaTvPravila.kt.
// Obe datoteki se morata spreminjati skupaj (pravilo enotnega vmesnika, TV je vzorec).
// Cista logika brez DOM, brez omrezja in brez casa.

const PredvajajNaTvPravila = (function() {
    const Vrsta = { FILM: "FILM", EPIZODA: "EPIZODA", KANAL: "KANAL" };
    const Zavrnitev = {
        NI_V_KROGU: "NI_V_KROGU",
        NEZNANA_VRSTA: "NEZNANA_VRSTA",
        NEVELJAVEN_ID: "NEVELJAVEN_ID",
        NEVELJAVNA_EPIZODA: "NEVELJAVNA_EPIZODA",
        PREDOLGO: "PREDOLGO",
        NEVELJAVEN_POLOZAJ: "NEVELJAVEN_POLOZAJ"
    };

    function preveri(vOzjemKrogu, polja) {
        if (!vOzjemKrogu) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NI_V_KROGU };

        const safePolja = (polja && typeof polja === 'object' && !Array.isArray(polja)) ? polja : {};

        function getPolje(key) {
            if (Object.prototype.hasOwnProperty.call(safePolja, key)) {
                const val = safePolja[key];
                return typeof val === 'string' ? val : null;
            }
            return null;
        }

        const vrstaStr = getPolje("vrsta");
        let vrsta;
        if (vrstaStr === "film") vrsta = Vrsta.FILM;
        else if (vrstaStr === "epizoda") vrsta = Vrsta.EPIZODA;
        else if (vrstaStr === "kanal") vrsta = Vrsta.KANAL;
        else return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEZNANA_VRSTA };

        const idStr = getPolje("id");
        if (idStr === null) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVEN_ID };

        if (vrsta === Vrsta.FILM || vrsta === Vrsta.EPIZODA) {
            if (idStr.length < 9 || idStr.length > 12 || !idStr.startsWith("tt")) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVEN_ID };
            for (let i = 2; i < idStr.length; i++) {
                const c = idStr.charCodeAt(i);
                if (c < 48 || c > 57) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVEN_ID };
            }
        } else { // KANAL
            if (idStr.length === 0 || idStr.length > 64) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVEN_ID };
            if (idStr.startsWith(".")) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVEN_ID };
            if (idStr.indexOf("..") !== -1) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVEN_ID };
            for (let i = 0; i < idStr.length; i++) {
                const c = idStr.charCodeAt(i);
                if (!(
                    (c >= 65 && c <= 90) || // A-Z
                    (c >= 97 && c <= 122) || // a-z
                    (c >= 48 && c <= 57) || // 0-9
                    c === 46 || c === 95 || c === 45 // . _ -
                )) {
                    return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVEN_ID };
                }
            }
        }

        let sezona = null;
        let epizoda = null;
        if (vrsta === Vrsta.EPIZODA) {
            const sezonaStr = getPolje("sezona");
            if (sezonaStr === null || sezonaStr.length === 0 || sezonaStr.length > 3) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVNA_EPIZODA };
            for (let i = 0; i < sezonaStr.length; i++) {
                const c = sezonaStr.charCodeAt(i);
                if (c < 48 || c > 57) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVNA_EPIZODA };
            }
            sezona = parseInt(sezonaStr, 10);
            if (sezona < 0 || sezona > 999) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVNA_EPIZODA };

            const epizodaStr = getPolje("epizoda");
            if (epizodaStr === null || epizodaStr.length === 0 || epizodaStr.length > 4) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVNA_EPIZODA };
            for (let i = 0; i < epizodaStr.length; i++) {
                const c = epizodaStr.charCodeAt(i);
                if (c < 48 || c > 57) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVNA_EPIZODA };
            }
            epizoda = parseInt(epizodaStr, 10);
            if (epizoda < 1 || epizoda > 9999) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVNA_EPIZODA };
        }

        const surovNaslov = getPolje("naslov") || "";
        let naslov = "";
        for (let i = 0; i < surovNaslov.length; i++) {
            const c = surovNaslov.charCodeAt(i);
            if (c >= 32 && c !== 127) {
                naslov += surovNaslov[i];
            }
        }
        if (naslov.length > 200) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.PREDOLGO };

        let polozajMs;
        if (vrsta === Vrsta.KANAL) {
            polozajMs = 0;
        } else {
            const polozajStr = getPolje("polozajMs");
            if (polozajStr === null || polozajStr.length === 0) {
                polozajMs = 0;
            } else {
                if (polozajStr.length > 9) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVEN_POLOZAJ };
                for (let i = 0; i < polozajStr.length; i++) {
                    const c = polozajStr.charCodeAt(i);
                    if (c < 48 || c > 57) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVEN_POLOZAJ };
                }
                polozajMs = parseInt(polozajStr, 10);
                if (polozajMs < 0 || polozajMs > 86400000) return { vrsta: "Zavrnjeno", razlog: Zavrnitev.NEVELJAVEN_POLOZAJ };
            }
        }

        return {
            vrsta: "Sprejeto",
            zahteva: {
                vrsta: vrsta,
                id: idStr,
                sezona: sezona,
                epizoda: epizoda,
                naslov: naslov,
                polozajMs: polozajMs
            }
        };
    }

    function sporocilo(z) {
        if (!z) return {};
        const map = {};
        if (z.vrsta === Vrsta.FILM) map["vrsta"] = "film";
        else if (z.vrsta === Vrsta.EPIZODA) map["vrsta"] = "epizoda";
        else if (z.vrsta === Vrsta.KANAL) map["vrsta"] = "kanal";

        if (z.id !== undefined && z.id !== null) map["id"] = z.id;

        if (z.vrsta === Vrsta.EPIZODA) {
            if (z.sezona !== null && z.sezona !== undefined) map["sezona"] = z.sezona.toString();
            if (z.epizoda !== null && z.epizoda !== undefined) map["epizoda"] = z.epizoda.toString();
        }

        if (z.naslov !== undefined && z.naslov !== null) map["naslov"] = z.naslov;

        if (z.vrsta !== Vrsta.KANAL) {
            if (z.polozajMs !== null && z.polozajMs !== undefined) map["polozajMs"] = z.polozajMs.toString();
        }
        return map;
    }

    function besediloZavrnitve(r, jezik) {
        if (jezik === "sl") {
            if (r === Zavrnitev.NI_V_KROGU) return "Naprava ni v ožjem krogu.";
            if (r === Zavrnitev.NEZNANA_VRSTA) return "Neznana vrsta vsebine.";
            if (r === Zavrnitev.NEVELJAVEN_ID) return "Neveljaven identifikator vsebine.";
            if (r === Zavrnitev.NEVELJAVNA_EPIZODA) return "Neveljavna sezona ali epizoda.";
            if (r === Zavrnitev.PREDOLGO) return "Naslov je predolg.";
            if (r === Zavrnitev.NEVELJAVEN_POLOZAJ) return "Neveljaven položaj predvajanja.";
        } else if (jezik === "de") {
            if (r === Zavrnitev.NI_V_KROGU) return "Das Gerät gehört nicht zum engen Kreis.";
            if (r === Zavrnitev.NEZNANA_VRSTA) return "Unbekannter Inhaltstyp.";
            if (r === Zavrnitev.NEVELJAVEN_ID) return "Ungültige Inhaltskennung.";
            if (r === Zavrnitev.NEVELJAVNA_EPIZODA) return "Ungültige Staffel oder Episode.";
            if (r === Zavrnitev.PREDOLGO) return "Der Titel ist zu lang.";
            if (r === Zavrnitev.NEVELJAVEN_POLOZAJ) return "Ungültige Wiedergabeposition.";
        } else if (jezik === "es") {
            if (r === Zavrnitev.NI_V_KROGU) return "El dispositivo no está en el círculo íntimo.";
            if (r === Zavrnitev.NEZNANA_VRSTA) return "Tipo de contenido desconocido.";
            if (r === Zavrnitev.NEVELJAVEN_ID) return "Identificador de contenido no válido.";
            if (r === Zavrnitev.NEVELJAVNA_EPIZODA) return "Temporada o episodio no válido.";
            if (r === Zavrnitev.PREDOLGO) return "El título es demasiado largo.";
            if (r === Zavrnitev.NEVELJAVEN_POLOZAJ) return "Posición de reproducción no válida.";
        } else if (jezik === "fr") {
            if (r === Zavrnitev.NI_V_KROGU) return "L'appareil ne fait pas partie du cercle restreint.";
            if (r === Zavrnitev.NEZNANA_VRSTA) return "Type de contenu inconnu.";
            if (r === Zavrnitev.NEVELJAVEN_ID) return "Identifiant de contenu non valide.";
            if (r === Zavrnitev.NEVELJAVNA_EPIZODA) return "Saison ou épisode non valide.";
            if (r === Zavrnitev.PREDOLGO) return "Le titre est trop long.";
            if (r === Zavrnitev.NEVELJAVEN_POLOZAJ) return "Position de lecture non valide.";
        } else if (jezik === "it") {
            if (r === Zavrnitev.NI_V_KROGU) return "Il dispositivo non fa parte della cerchia ristretta.";
            if (r === Zavrnitev.NEZNANA_VRSTA) return "Tipo di contenuto sconosciuto.";
            if (r === Zavrnitev.NEVELJAVEN_ID) return "Identificatore di contenuto non valido.";
            if (r === Zavrnitev.NEVELJAVNA_EPIZODA) return "Stagione o episodio non valido.";
            if (r === Zavrnitev.PREDOLGO) return "Il titolo è troppo lungo.";
            if (r === Zavrnitev.NEVELJAVEN_POLOZAJ) return "Posizione di riproduzione non valida.";
        } else {
            if (r === Zavrnitev.NI_V_KROGU) return "Device is not in the inner circle.";
            if (r === Zavrnitev.NEZNANA_VRSTA) return "Unknown content type.";
            if (r === Zavrnitev.NEVELJAVEN_ID) return "Invalid content identifier.";
            if (r === Zavrnitev.NEVELJAVNA_EPIZODA) return "Invalid season or episode.";
            if (r === Zavrnitev.PREDOLGO) return "Title is too long.";
            if (r === Zavrnitev.NEVELJAVEN_POLOZAJ) return "Invalid playback position.";
        }
        return "";
    }

    return {
        Vrsta: Vrsta,
        Zavrnitev: Zavrnitev,
        preveri: preveri,
        sporocilo: sporocilo,
        besediloZavrnitve: besediloZavrnitve
    };
})();

if (typeof module !== 'undefined' && module.exports) {
    module.exports = PredvajajNaTvPravila;
}
if (typeof window !== 'undefined') {
    window.PredvajajNaTvPravila = PredvajajNaTvPravila;
} else if (typeof global !== 'undefined') {
    global.PredvajajNaTvPravila = PredvajajNaTvPravila;
}
