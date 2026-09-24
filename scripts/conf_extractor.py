"""
Script to recreate the config.ini file from an HDF5 measurement file.
- file dialog to select the HDF5 measurement file
- file dialog to save the new config.ini file

The config is read from the structure that Measurement.safe_measurement_settings() stores:
Configuration/<Section> (group) -> <key> = "<value>" (attribute)
Comments of the original config file are not stored and can't be recreated.
"""

#Imports
import configparser
import h5py
from tkinter import Tk, filedialog


def extract_config_from_hdf(hdf_file_path: str | None = None):
    """
    Extracts the configuration from an HDF5 file and saves it as a new config.ini file.

    :param hdf_file_path: Path to the HDF5 file. If None, a file dialog asks for it.
    :return: path of the written config.ini file (None if the user cancelled a dialog).
    """

    #hidden tkinter window, only needed as parent for the file dialogs
    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    #ask the user for the HDF5 file if no path was given
    if hdf_file_path is None:
        hdf_file_path = filedialog.askopenfilename(
            title="Select measurement HDF5 file",
            filetypes=[("HDF5 files", "*.h5 *.hdf5"), ("All files", "*.*")],
        )
        if not hdf_file_path:
            root.destroy()
            print("No HDF5 file selected, nothing extracted.")
            return None

    #rebuild the config: every group is a section, every attribute a key
    ini = configparser.ConfigParser(interpolation=None)
    ini.optionxform = str #keep the case of the keys
    with h5py.File(hdf_file_path, 'r') as hdf_file:
        group_name = "Configuration"
        if group_name not in hdf_file:
            root.destroy()
            raise KeyError(f"The HDF5 file '{hdf_file_path}' does not contain the group '{group_name}'.")

        config_group = hdf_file[group_name]
        source_file = config_group.attrs.get("source_file", "config.ini")
        if isinstance(source_file, bytes):
            source_file = source_file.decode('utf-8')

        for section, section_group in config_group.items():
            ini.add_section(section)
            for key, value in section_group.attrs.items():
                ini.set(section, key, value.decode('utf-8') if isinstance(value, bytes) else str(value))

    #ask the user where to save the config file (suggests the name of the original config file)
    output_path = filedialog.asksaveasfilename(
        title="Save extracted config as",
        defaultextension=".ini",
        initialfile=source_file,
        filetypes=[("INI files", "*.ini"), ("All files", "*.*")],
    )
    root.destroy()

    if not output_path:
        print("No output file selected, config was not saved.")
        return None

    with open(output_path, 'w', encoding='utf-8') as config_file:
        ini.write(config_file)
    print(f"Config extracted to: {output_path}")

    return output_path


if __name__ == "__main__":
    extract_config_from_hdf()
