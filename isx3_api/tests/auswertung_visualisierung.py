"""
auswertung_visualisierung.py - Universelle Auswertung & Vergleichs-Visualisierung
für eigene API-HDF5-Messdateien (.h5) und offizielle Sciospec-GUI-HDF5-Dateien (.scio5 / .h5).
"""

import os
from tkinter import Tk, filedialog
import h5py
import matplotlib.pyplot as plt
import numpy as np


DEFAULT_H5_DIR = r"C:\Users\lukas\Documents\GitHub\sensorprojekt_api\isx3_api\measurements"


def select_h5_file(title: str = "Wähle eine HDF5-Messdatei (.h5 / .scio5)") -> str | None:
    """Öffnet einen Dateidialog zur Auswahl einer API- oder Sciospec-HDF5-Datei."""
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    init_h5 = DEFAULT_H5_DIR if os.path.exists(DEFAULT_H5_DIR) else os.getcwd()
    h5_path = filedialog.askopenfilename(
        title=title,
        initialdir=init_h5,
        filetypes=[
            ("HDF5 / Sciospec Messdaten", "*.h5 *.hdf5 *.scio5"),
            ("Alle Dateien", "*.*"),
        ],
    )
    root.destroy()
    return h5_path or None


def _parse_api_hdf5(h5: h5py.File) -> tuple[dict[str, dict[str, np.ndarray]], list[float]]:
    """Liest das eigene Python-API HDF5-Format (Sensor_X / Measurement_Y) aus."""
    results = {}
    block_transitions = []

    if "Configuration" in h5 and "FrequencyBlocks" in h5["Configuration"]:
        fb_grp = h5["Configuration"]["FrequencyBlocks"]
        for k in sorted(fb_grp.attrs.keys()):
            if "_stop" in k:
                try:
                    block_transitions.append(float(fb_grp.attrs[k]))
                except ValueError:
                    pass

    sensor_groups = [k for k in h5.keys() if k.startswith("Sensor_") or k == "Measurement"]

    for k in sensor_groups:
        label = k
        if k.startswith("Sensor_"):
            parts = k.split("_")
            if len(parts) > 1 and parts[1].isdigit():
                label = f"API Sensor #{int(parts[1])}"
        else:
            label = "API Main Port"

        grp = h5[k]
        meas_keys = sorted(
            [mk for mk in grp.keys() if mk.startswith("Measurement_")],
            key=lambda x: [int(n) for n in x.split("_")[1].split(".")],
        )
        if not meas_keys:
            continue

        f_list, re_list, im_list = [], [], []
        for m_key in meas_keys:
            ds = grp[m_key]
            f_val = float(np.mean(ds["frequency"][()]))
            re_val = float(np.mean(ds["real_part"][()]))
            im_val = float(np.mean(ds["imaginary_part"][()]))

            f_list.append(f_val)
            re_list.append(re_val)
            im_list.append(im_val)

        f_arr = np.array(f_list, dtype=float)
        re_arr = np.array(re_list, dtype=float)
        im_arr = np.array(im_list, dtype=float)

        results[label] = {
            "frequency": f_arr,
            "real": re_arr,
            "imag": im_arr,
            "z_mag": np.hypot(re_arr, im_arr),
            "phase": np.degrees(np.arctan2(im_arr, re_arr)),
        }

    return results, sorted(list(set(block_transitions)))


def _parse_sciospec_gui_hdf5(h5: h5py.File) -> tuple[dict[str, dict[str, np.ndarray]], list[float]]:
    """
    Liest das native Sciospec-Software HDF5-Format (.scio5 / .h5) aus.
    Struktur laut Handbuch Kap. 7.7.5: <KonfigName>/data/<PortGroup>/frequency & measurementData
    """
    results = {}
    block_transitions = []

    for top_key in h5.keys():
        top_obj = h5[top_key]
        if not isinstance(top_obj, h5py.Group):
            continue

        # Frequenzblöcke aus setup/frequencySetting auslesen, falls vorhanden
        if "setup" in top_obj and "frequencySetting" in top_obj["setup"]:
            try:
                f_set = top_obj["setup"]["frequencySetting"][()]
                if hasattr(f_set, "dtype") and f_set.dtype.names and "maxFrequency" in f_set.dtype.names:
                    for row in np.atleast_1d(f_set):
                        block_transitions.append(float(row["maxFrequency"]))
            except Exception:
                pass

        if "data" not in top_obj:
            continue

        data_grp = top_obj["data"]
        for port_key in data_grp.keys():
            port_obj = data_grp[port_key]
            if not isinstance(port_obj, h5py.Group):
                continue
            if "frequency" not in port_obj or "measurementData" not in port_obj:
                continue

            f_arr = np.array(port_obj["frequency"][()], dtype=float).flatten()
            raw_meas = np.array(port_obj["measurementData"][()], dtype=float)

            # measurementData ist 3D: [timestamp_idx, freq_idx, 0=Real / 1=Imag]
            if raw_meas.ndim == 3:
                mean_meas = np.mean(raw_meas, axis=0)
                re_arr = mean_meas[:, 0]
                im_arr = mean_meas[:, 1]
            elif raw_meas.ndim == 2:
                re_arr = raw_meas[:, 0]
                im_arr = raw_meas[:, 1]
            else:
                continue

            min_len = min(len(f_arr), len(re_arr), len(im_arr))
            f_arr = f_arr[:min_len]
            re_arr = re_arr[:min_len]
            im_arr = im_arr[:min_len]

            label = f"Sciospec GUI ({port_key})"
            results[label] = {
                "frequency": f_arr,
                "real": re_arr,
                "imag": im_arr,
                "z_mag": np.hypot(re_arr, im_arr),
                "phase": np.degrees(np.arctan2(im_arr, re_arr)),
            }

    return results, sorted(list(set(block_transitions)))


def parse_any_hdf5_file(h5_file: str) -> tuple[dict[str, dict[str, np.ndarray]], list[float], str]:
    """
    Erkennt automatisch, ob eine API-HDF5-Datei oder eine Sciospec-GUI-HDF5-Datei vorliegt,
    und gibt (results_dict, block_transitions, file_type) zurück.
    """
    with h5py.File(h5_file, "r") as h5:
        keys = list(h5.keys())
        is_api = any(k.startswith("Sensor_") or k == "Measurement" or k == "Configuration" for k in keys)

        if is_api:
            data, trans = _parse_api_hdf5(h5)
            return data, trans, "API"
        else:
            data, trans = _parse_sciospec_gui_hdf5(h5)
            if data:
                return data, trans, "SCIOSPEC_GUI"
            # Fallback, falls trotzdem API-Gruppen enthalten sind
            data, trans = _parse_api_hdf5(h5)
            return data, trans, "API"


def _ask_axis_options() -> dict:
    """Fragt den Nutzer in der Konsole nach Skalierung (log/linear) und optionalen Achsenlimits."""
    print("\n--- ACHSEN- & DARSTELLUNGS-OPTIONEN ---")
    print("  Skalierung der Betrags-Achse |Z| (Y-Achse):")
    print("    [1] Logarithmisch (Log-Log Bode-Plot) [Standard]")
    print("    [2] Linear (Wie Standard-Ansicht in der Sciospec-GUI)")
    y_choice = input("  Deine Wahl (1 oder 2) [Standard: 1]: ").strip()
    y_scale = "linear" if y_choice == "2" else "log"

    print("\n  Skalierung der Frequenz-Achse f (X-Achse):")
    print("    [1] Logarithmisch [Standard]")
    print("    [2] Linear")
    x_choice = input("  Deine Wahl (1 oder 2) [Standard: 1]: ").strip()
    x_scale = "linear" if x_choice == "2" else "log"

    custom_limits = input("\n  Möchtest du manuelle Achsen-Grenzen (Min/Max) festlegen? (j/[N]): ").strip().lower()
    f_lim, z_lim, p_lim = None, None, None

    if custom_limits in ["j", "ja", "y", "yes"]:
        try:
            f_min = input("    Frequenz Min [Hz] (Enter für Auto): ").strip()
            f_max = input("    Frequenz Max [Hz] (Enter für Auto): ").strip()
            if f_min or f_max:
                f_lim = (float(f_min) if f_min else None, float(f_max) if f_max else None)

            z_min = input("    Betrag |Z| Min [Ohm] (Enter für Auto): ").strip()
            z_max = input("    Betrag |Z| Max [Ohm] (Enter für Auto): ").strip()
            if z_min or z_max:
                z_lim = (float(z_min) if z_min else None, float(z_max) if z_max else None)

            p_min = input("    Phase Min [Grad] (Enter für Auto): ").strip()
            p_max = input("    Phase Max [Grad] (Enter für Auto): ").strip()
            if p_min or p_max:
                p_lim = (float(p_min) if p_min else None, float(p_max) if p_max else None)
        except ValueError as e:
            print(f"  [WARNUNG] Ungültige Zahleneingabe ({e}) -> Verwende Auto-Skalierung.")

    return {
        "x_scale": x_scale,
        "y_scale": y_scale,
        "f_lim": f_lim,
        "z_lim": z_lim,
        "p_lim": p_lim,
    }


def _apply_axis_limits(ax_z, ax_p, axis_opts: dict) -> None:
    ax_z.set_xscale(axis_opts["x_scale"])
    ax_z.set_yscale(axis_opts["y_scale"])
    ax_p.set_xscale(axis_opts["x_scale"])

    if axis_opts["f_lim"]:
        if axis_opts["f_lim"][0] is not None:
            ax_z.set_xlim(left=axis_opts["f_lim"][0])
            ax_p.set_xlim(left=axis_opts["f_lim"][0])
        if axis_opts["f_lim"][1] is not None:
            ax_z.set_xlim(right=axis_opts["f_lim"][1])
            ax_p.set_xlim(right=axis_opts["f_lim"][1])

    if axis_opts["z_lim"]:
        if axis_opts["z_lim"][0] is not None:
            ax_z.set_ylim(bottom=axis_opts["z_lim"][0])
        if axis_opts["z_lim"][1] is not None:
            ax_z.set_ylim(top=axis_opts["z_lim"][1])

    if axis_opts["p_lim"]:
        if axis_opts["p_lim"][0] is not None:
            ax_p.set_ylim(bottom=axis_opts["p_lim"][0])
        if axis_opts["p_lim"][1] is not None:
            ax_p.set_ylim(top=axis_opts["p_lim"][1])


def plot_single_file(data_dict: dict, transitions: list[float], file_name: str, file_type: str, axis_opts: dict) -> None:
    """Plottet eine einzelne Datei (entweder API oder Sciospec-GUI) mit Block-Farben."""
    if not data_dict:
        print("[FEHLER] Keine gültigen Messdaten in der Datei gefunden.")
        return

    fig, (ax_z, ax_p) = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
    colors = ["blue", "orange", "green", "purple", "brown", "teal"]

    for ch_idx, (label, data) in enumerate(data_dict.items()):
        freqs = data["frequency"]
        z_mag = data["z_mag"]
        phase = data["phase"]

        indices = [0]
        for t in transitions[:-1]:
            idx = int(np.searchsorted(freqs, t))
            if 0 < idx < len(freqs):
                indices.append(idx)
        indices.append(len(freqs))

        for i in range(len(indices) - 1):
            start_i = indices[i]
            end_i = indices[i + 1]
            # Überlappungspunkt mitnehmen, damit keine Lücke in der Linie entsteht
            plot_end = min(len(freqs), end_i + 1) if i < len(indices) - 2 else end_i
            col = colors[(ch_idx + i) % len(colors)]
            blk_suffix = f" - Block {i + 1}" if len(indices) > 2 else ""
            lbl = f"{label}{blk_suffix}"

            ax_z.plot(freqs[start_i:plot_end], z_mag[start_i:plot_end], "o-", color=col, label=lbl)
            ax_p.plot(freqs[start_i:plot_end], phase[start_i:plot_end], "o-", color=col, label=lbl)

    for t in transitions[:-1]:
        ax_z.axvline(t, color="red", linestyle=":", alpha=0.7)
        ax_p.axvline(t, color="red", linestyle=":", alpha=0.7, label=f"Block-Grenze ({t:g} Hz)")

    _apply_axis_limits(ax_z, ax_p, axis_opts)

    scale_info = "Linear |Z|" if axis_opts["y_scale"] == "linear" else "Log |Z|"
    ax_z.set_ylabel(r"Betrag $|Z|$ / $\Omega$")
    ax_z.set_title(f"HDF5-Auswertung [{file_type}]: {file_name} ({scale_info})")
    ax_z.grid(True, which="both", linestyle="--", alpha=0.5)
    ax_z.legend(loc="best", fontsize=9)

    ax_p.set_xlabel("Frequenz $f$ / Hz")
    ax_p.set_ylabel(r"Phase $\phi$ / °")
    ax_p.grid(True, which="both", linestyle="--", alpha=0.5)
    if len(transitions) > 1:
        ax_p.legend(loc="best", fontsize=8)

    plt.tight_layout()
    plt.show()


def plot_comparison(
    data_1: dict,
    name_1: str,
    data_2: dict,
    name_2: str,
    transitions: list[float],
    axis_opts: dict,
) -> None:
    """Plottet zwei HDF5-Dateien (z.B. API vs. Sciospec-GUI) zum direkten Vergleich übereinander."""
    if not data_1 or not data_2:
        print("[FEHLER] Mindestens eine der beiden Dateien enthält keine gültigen Messdaten.")
        return

    fig, (ax_z, ax_p) = plt.subplots(2, 1, figsize=(12, 9), sharex=True)

    # Datei 1 plotten (durchgezogene Linie mit Kreisen)
    for label_1, d1 in data_1.items():
        lbl = f"{name_1} | {label_1}"
        ax_z.plot(d1["frequency"], d1["z_mag"], "o-", color="#0055cc", linewidth=1.8, markersize=5, label=lbl)
        ax_p.plot(d1["frequency"], d1["phase"], "o-", color="#0055cc", linewidth=1.8, markersize=5, label=lbl)

    # Datei 2 plotten (gestrichelte Linie mit Quadraten)
    for label_2, d2 in data_2.items():
        lbl = f"{name_2} | {label_2}"
        ax_z.plot(d2["frequency"], d2["z_mag"], "s--", color="#e63900", linewidth=1.6, markersize=5, alpha=0.85, label=lbl)
        ax_p.plot(d2["frequency"], d2["phase"], "s--", color="#e63900", linewidth=1.6, markersize=5, alpha=0.85, label=lbl)

    # Statistische Abweichung in der Konsole ausgeben, falls Punktanzahl übereinstimmt
    first_d1 = next(iter(data_1.values()))
    first_d2 = next(iter(data_2.values()))
    if len(first_d1["z_mag"]) == len(first_d2["z_mag"]):
        rel_err_z = np.abs(first_d1["z_mag"] - first_d2["z_mag"]) / np.maximum(first_d2["z_mag"], 1e-12) * 100.0
        abs_err_p = np.abs(first_d1["phase"] - first_d2["phase"])
        print("\n" + "=" * 65)
        print(f" VERGLEICHS-STATISTIK: {name_1} vs. {name_2}")
        print("=" * 65)
        print(f" • Mittlere Abweichung |Z|: {np.mean(rel_err_z):.3f} % (Max: {np.max(rel_err_z):.3f} %)")
        print(f" • Mittlere Abweichung φ  : {np.mean(abs_err_p):.3f} ° (Max: {np.max(abs_err_p):.3f} °)")
        print("=" * 65)

    for t in transitions[:-1]:
        ax_z.axvline(t, color="gray", linestyle=":", alpha=0.7)
        ax_p.axvline(t, color="gray", linestyle=":", alpha=0.7)

    _apply_axis_limits(ax_z, ax_p, axis_opts)

    scale_info = "Linear |Z|" if axis_opts["y_scale"] == "linear" else "Log |Z|"
    ax_z.set_ylabel(r"Betrag $|Z|$ / $\Omega$")
    ax_z.set_title(f"Direkter Messvergleich ({scale_info}): {name_1} vs. {name_2}")
    ax_z.grid(True, which="both", linestyle="--", alpha=0.5)
    ax_z.legend(loc="best", fontsize=9)

    ax_p.set_xlabel("Frequenz $f$ / Hz")
    ax_p.set_ylabel(r"Phase $\phi$ / °")
    ax_p.grid(True, which="both", linestyle="--", alpha=0.5)
    ax_p.legend(loc="best", fontsize=9)

    plt.tight_layout()
    plt.show()


def main():
    print("\n" + "=" * 70)
    print(" HDF5 AUSWERTUNG & VERGLEICHS-VISUALISIERUNG (API & SCIOSPEC-GUI)")
    print("=" * 70)
    print("Was möchtest du tun?")
    print("  [1] Nur EINE Datei plotten (API .h5 ODER Sciospec-GUI .scio5/.h5) [Standard]")
    print("  [2] ZWEI Dateien direkt vergleichen (z.B. API-Messung vs. Sciospec-GUI)")
    mode_choice = input("\nDeine Wahl (1 oder 2) [Standard: 1]: ").strip()

    if mode_choice == "2":
        print("\n-> Bitte wähle zuerst die 1. Datei aus (z.B. deine API-Messdatei)...")
        path_1 = select_h5_file(title="1. HDF5-Datei wählen (z.B. API-Messung)")
        if not path_1:
            print("[INFO] Keine 1. Datei ausgewählt. Abbruch.")
            return

        print("-> Bitte wähle nun die 2. Datei zum Vergleich aus (z.B. Sciospec-GUI Export)...")
        path_2 = select_h5_file(title="2. HDF5-Datei zum Vergleich wählen (z.B. Sciospec-GUI)")
        if not path_2:
            print("[INFO] Keine 2. Datei ausgewählt. Abbruch.")
            return

        data_1, trans_1, type_1 = parse_any_hdf5_file(path_1)
        data_2, trans_2, type_2 = parse_any_hdf5_file(path_2)
        print(f"[OK] Datei 1 geladen ({type_1}): {os.path.basename(path_1)}")
        print(f"[OK] Datei 2 geladen ({type_2}): {os.path.basename(path_2)}")

        axis_opts = _ask_axis_options()
        all_trans = sorted(list(set(trans_1 + trans_2)))
        plot_comparison(
            data_1=data_1,
            name_1=os.path.basename(path_1),
            data_2=data_2,
            name_2=os.path.basename(path_2),
            transitions=all_trans,
            axis_opts=axis_opts,
        )
    else:
        print("\n-> Bitte wähle die HDF5-Datei aus (API .h5 oder Sciospec-GUI .scio5/.h5)...")
        h5_path = select_h5_file(title="HDF5-Messdatei wählen (API oder Sciospec-GUI)")
        if not h5_path:
            print("[INFO] Keine Datei ausgewählt. Abbruch.")
            return

        data_dict, transitions, f_type = parse_any_hdf5_file(h5_path)
        print(f"[OK] Datei erkannt als '{f_type}': {os.path.basename(h5_path)}")

        axis_opts = _ask_axis_options()
        plot_single_file(
            data_dict=data_dict,
            transitions=transitions,
            file_name=os.path.basename(h5_path),
            file_type=f_type,
            axis_opts=axis_opts,
        )


if __name__ == "__main__":
    main()