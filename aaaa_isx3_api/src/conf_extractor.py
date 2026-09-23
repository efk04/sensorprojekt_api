def extract_config_from_hdf(hdf_file_path: str | None = None):
    """
    Extracts the configuration from an HDF5 file and returns it as a new config.ini file.

    :param hdf_file_path: Path to the HDF5 file. If None, a file dialog asks for it.
    :return: path of the written config.ini file (None if the user cancelled a dialog).
    """
    import json
    import h5py
    from dataclasses import fields
    from tkinter import Tk, filedialog

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

    #read the flat settings dictionary that Measurement.safe_measurement_settings() stored as JSON
    with h5py.File(hdf_file_path, 'r') as hdf_file:
        dataset_path = "1-Measurement_Settings/measurement_settings"
        if dataset_path not in hdf_file:
            raise KeyError(f"The HDF5 file '{hdf_file_path}' does not contain '{dataset_path}'.")
        raw = hdf_file[dataset_path][0]
        flat_settings = json.loads(raw.decode('utf-8') if isinstance(raw, bytes) else raw)

    #rebuild the ini sections from the DeviceConfig structure (e.g. DCBiasConfig -> [DCBias])
    ini = configparser.ConfigParser()
    ini.optionxform = str
    for section_field in fields(DeviceConfig):
        section_name = section_field.type.__name__.removesuffix("Config")
        ini.add_section(section_name)
        for option in fields(section_field.type):
            if option.name not in flat_settings:
                continue
            value = flat_settings[option.name]
            if isinstance(value, bool):
                value = int(value)
            elif isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            ini.set(section_name, option.name, str(value))

    #ask the user where to save the config file
    output_path = filedialog.asksaveasfilename(
        title="Save extracted config as",
        defaultextension=".ini",
        initialfile="config.ini",
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