"""
conf_extractor.py - Rekonstruktion von INI-Dateien aus HDF5-Messdaten.

Liest die in einer HDF5-Datei gesicherte Gerätekonfiguration aus der Gruppe
'Configuration' aus und erzeugt daraus wieder eine valide .ini-Datei.
"""

import argparse
import configparser
import os
import sys
import h5py


def select_files_via_gui() -> tuple[str | None, str | None]:
    """
    Öffnet grafische Dialoge zur Datei- und Zielpfadauswahl.

    :return: Tupel aus (Eingabepfad_HDF5, Ausgabepfad_INI).
    """
    from tkinter import Tk, filedialog

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    try:
        hdf_path = filedialog.askopenfilename(
            title="HDF5-Messdatei auswählen",
            filetypes=[("HDF5-Dateien", "*.h5 *.hdf5"), ("Alle Dateien", "*.*")],
        )
        if not hdf_path:
            return None, None

        # Standard-Ausgabenamen anhand der HDF5-Datei vorschlagen
        default_ini_name = os.path.splitext(os.path.basename(hdf_path))[0] + "_extracted.ini"

        output_path = filedialog.asksaveasfilename(
            title="Extrahierte Konfiguration speichern unter",
            defaultextension=".ini",
            initialfile=default_ini_name,
            filetypes=[("INI-Dateien", "*.ini"), ("Alle Dateien", "*.*")],
        )
        return hdf_path, output_path
    finally:
        root.destroy()


def extract_config_from_hdf(hdf_file_path: str, output_ini_path: str) -> str:
    """
    Liest Konfigurationsgruppen und Attribute aus HDF5 und schreibt die INI-Datei.

    :param hdf_file_path: Pfad zur existierenden HDF5-Messdatei.
    :param output_ini_path: Zieldateipfad für die extrahierte .ini-Datei.
    :return: Pfad der geschriebenen INI-Datei.
    """
    if not os.path.isfile(hdf_file_path):
        raise FileNotFoundError(f"Die HDF5-Datei '{hdf_file_path}' existiert nicht.")

    ini = configparser.ConfigParser(interpolation=None)
    ini.optionxform = str  # Groß-/Kleinschreibung beibehalten

    with h5py.File(hdf_file_path, "r") as hdf:
        group_name = "Configuration"
        if group_name not in hdf:
            raise KeyError(f"Die HDF5-Datei enthält keine Konfigurationsgruppe '{group_name}'.")

        config_group = hdf[group_name]

        # Jede Untergruppe entspricht einer INI-Sektion ([Connection], [Frontend], ...)
        for section_name, section_group in config_group.items():
            ini.add_section(section_name)
            # Attribute entsprechen den Parametern dieser Sektion
            for key, val in section_group.attrs.items():
                # Bytes-Werte bei Bedarf in Strings dekodieren
                str_val = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                ini.set(section_name, key, str_val)

    # Zielverzeichnis bei Bedarf anlegen
    target_dir = os.path.dirname(output_ini_path)
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)

    with open(output_ini_path, "w", encoding="utf-8") as out_file:
        ini.write(out_file)

    print(f"[OK] Konfiguration erfolgreich extrahiert nach: {output_ini_path}")
    return output_ini_path


def main() -> None:
    """Parst Startargumente oder öffnet Fallback-Dialoge."""
    parser = argparse.ArgumentParser(description="Extrahiert die Konfiguration aus einer ISX-3 HDF5-Datei.")
    parser.add_argument("-i", "--input", help="Pfad zur HDF5-Datei", default=None)
    parser.add_argument("-o", "--output", help="Pfad zur Ausgabe-INI-Datei", default=None)
    args = parser.parse_args()

    hdf_in = args.input
    ini_out = args.output

    # Falls keine Parameter übergeben wurden, grafischen Dialog nutzen
    if not hdf_in or not ini_out:
        gui_in, gui_out = select_files_via_gui()
        hdf_in = hdf_in or gui_in
        ini_out = ini_out or gui_out

    if not hdf_in or not ini_out:
        print("[INFO] Vorgang abgebrochen: Keine Dateien ausgewählt.")
        sys.exit(0)

    try:
        extract_config_from_hdf(hdf_in, ini_out)
    except Exception as err:
        print(f"[FEHLER] Extraktion fehlgeschlagen: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()