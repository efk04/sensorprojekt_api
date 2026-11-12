"""
auswertung_visualisierung.py - Universelle Auswertung, Timing-Analyse & Vergleichs-Visualisierung
für eigene API-HDF5-Messdateien (.h5) und offizielle Sciospec-GUI-HDF5-Dateien (.scio5 / .h5).

Integrierte Features:
1. Timing- & Performance-Analyse pro Sensor (Gesamtzeit, Zeit pro Einzel-Sweep & Zeit pro Frequenzpunkt)
2. Statistische Wiederholgenauigkeit (Standardabweichung ±1σ als Fehlerband bei Mehrfach-Sweeps)
3. Dynamische Autoranging-Auswertung (Erkennung von Current-Range-Wechseln über der Frequenz)
4. Multi-Plot-Auswahl (Bode, Nyquist, Real/Imag oder Kombi-Dashboard Bode + Nyquist)
5. Automatischer Konfigurations-Steckbrief (inkl. Multi-Pin MUX-Belegung) & Bauteil-Schätzung (R, C, L)
"""

import os
from tkinter import Tk, filedialog
import h5py
import matplotlib.pyplot as plt
import numpy as np


DEFAULT_H5_DIR = r"C:\Users\lukas\Documents\GitHub\sensorprojekt_api\isx3_api\measurements"

CR_LABELS = {
    0: "Autoranging",
    1: "±10 mA (100 Ω)",
    2: "±100 µA (10 kΩ)",
    4: "±1 µA (1 MΩ)",
    6: "±10 nA (100 MΩ)",
}


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


def _estimate_component(freqs: np.ndarray, z_mag: np.ndarray, phase: np.ndarray, imag: np.ndarray) -> str:
    """Schätzt anhand des Phasenwinkels, ob ein Widerstand (R), Kondensator (C) oder Induktivität (L) vorliegt."""
    if len(freqs) == 0:
        return "Keine Daten"

    mean_phase = float(np.mean(phase))
    mean_z = float(np.mean(z_mag))

    if abs(mean_phase) <= 15.0:
        return f"Ohmscher Widerstand R ≈ {mean_z:.2f} Ω (φ_mean = {mean_phase:.1f}°)"
    elif mean_phase <= -65.0:
        valid = np.abs(imag) > 1e-9
        if np.any(valid):
            c_vals = 1.0 / (2.0 * np.pi * freqs[valid] * np.abs(imag[valid]))
            c_median = float(np.median(c_vals))
            if c_median >= 1e-6:
                return f"Kapazitiv C ≈ {c_median * 1e6:.2f} µF (φ_mean = {mean_phase:.1f}°)"
            elif c_median >= 1e-9:
                return f"Kapazitiv C ≈ {c_median * 1e9:.2f} nF (φ_mean = {mean_phase:.1f}°)"
            else:
                return f"Kapazitiv C ≈ {c_median * 1e12:.2f} pF (φ_mean = {mean_phase:.1f}°)"
    elif mean_phase >= 65.0:
        valid = freqs > 0
        if np.any(valid):
            l_vals = np.abs(imag[valid]) / (2.0 * np.pi * freqs[valid])
            l_median = float(np.median(l_vals))
            return f"Induktiv L ≈ {l_median * 1e3:.3f} mH (φ_mean = {mean_phase:.1f}°)"

    return f"Mischimpedanz |Z|_mean = {mean_z:.2f} Ω, φ_mean = {mean_phase:.1f}°"


def _parse_api_hdf5(h5: h5py.File) -> tuple[dict[str, dict], list[float], dict]:
    """Liest das eigene Python-API HDF5-Format inklusive Timing, Standardabweichung und Autoranging aus."""
    results = {}
    block_transitions = []
    meta_info = {"type": "API", "sections": {}}

    if "Configuration" in h5:
        cfg_grp = h5["Configuration"]
        meta_info["device_version"] = cfg_grp.attrs.get("device_version", "unbekannt")
        meta_info["measurement_type"] = cfg_grp.attrs.get("measurement_type", "MAIN")
        meta_info["source_file"] = cfg_grp.attrs.get("source_file", "-")

        for sec_name in cfg_grp.keys():
            sec_obj = cfg_grp[sec_name]
            meta_info["sections"][sec_name] = dict(sec_obj.attrs)

        if "FrequencyBlocks" in cfg_grp:
            fb_grp = cfg_grp["FrequencyBlocks"]
            for k in sorted(fb_grp.attrs.keys()):
                if "_stop" in k:
                    try:
                        block_transitions.append(float(fb_grp.attrs[k]))
                    except ValueError:
                        pass

    sensor_groups = [k for k in h5.keys() if k.startswith("Sensor_")]
    has_direct_meas = any(k.startswith("Measurement_") for k in h5.keys())

    targets = []
    if sensor_groups:
        for sg in sorted(sensor_groups, key=lambda x: int(x.split("_")[1]) if x.split("_")[1].isdigit() else 0):
            s_num = sg.split("_")[1]
            targets.append((f"API Sensor #{s_num}", h5[sg]))
    elif has_direct_meas:
        targets.append(("API Main Port", h5))
    elif "Measurement" in h5:
        targets.append(("API Main Port", h5["Measurement"]))

    for label, grp in targets:
        meas_keys = sorted(
            [mk for mk in grp.keys() if mk.startswith("Measurement_")],
            key=lambda x: [int(n) for n in x.split("_")[1].split(".")],
        )
        if not meas_keys:
            continue

        api_dur_ms = grp.attrs.get("measurement_duration_ms", None)
        if api_dur_ms is None and "Measurement" in h5 and "measurement_duration_ms" in h5["Measurement"].attrs:
            api_dur_ms = h5["Measurement"].attrs["measurement_duration_ms"]

        f_list, re_mean_l, im_mean_l = [], [], []
        z_mean_l, z_std_l, ph_mean_l, ph_std_l = [], [], [], []
        cr_list = []
        hw_ts_matrix = []
        hw_ts_unit = None
        py_timestamps = []
        spectra_count = 1

        for m_key in meas_keys:
            ds = grp[m_key]
            f_val = float(np.mean(ds["frequency"][()]))
            re_raw = np.atleast_1d(np.array(ds["real_part"][()], dtype=float))
            im_raw = np.atleast_1d(np.array(ds["imaginary_part"][()], dtype=float))
            spectra_count = max(spectra_count, len(re_raw))

            z_raw = np.hypot(re_raw, im_raw)
            ph_raw = np.degrees(np.arctan2(im_raw, re_raw))

            f_list.append(f_val)
            re_mean_l.append(float(np.mean(re_raw)))
            im_mean_l.append(float(np.mean(im_raw)))
            z_mean_l.append(float(np.mean(z_raw)))
            z_std_l.append(float(np.std(z_raw, ddof=1)) if len(z_raw) > 1 else 0.0)
            ph_mean_l.append(float(np.mean(ph_raw)))
            ph_std_l.append(float(np.std(ph_raw, ddof=1)) if len(ph_raw) > 1 else 0.0)

            if "timestamp" in ds:
                py_timestamps.append(float(np.mean(ds["timestamp"][()])))

            if "current_range" in ds:
                cr_vals = np.atleast_1d(ds["current_range"][()])
                cr_list.append(int(cr_vals[0]) if len(cr_vals) > 0 else -1)

            if "hw_timestamp" in ds:
                hw_vals = np.atleast_1d(np.array(ds["hw_timestamp"][()], dtype=float))
                hw_ts_matrix.append(hw_vals)
                if hw_ts_unit is None:
                    hw_ts_unit = ds["hw_timestamp"].attrs.get("unit", "ms")

        if api_dur_ms is None and len(py_timestamps) > 1:
            span_s = max(py_timestamps) - min(py_timestamps)
            if span_s > 0:
                api_dur_ms = span_s * 1000.0

        hw_sweep_ms_list = []
        hw_total_ms = None
        if hw_ts_matrix and len(hw_ts_matrix) > 1:
            scale_to_ms = 0.001 if hw_ts_unit == "us" else 1.0
            min_len = min(len(row) for row in hw_ts_matrix)
            if min_len > 0:
                mat = np.array([row[:min_len] for row in hw_ts_matrix], dtype=float) * scale_to_ms
                n_pts = mat.shape[0]
                for s_idx in range(min_len):
                    col = mat[:, s_idx]
                    span = float(np.max(col) - np.min(col))
                    est_sweep = span * (n_pts / max(1, n_pts - 1))
                    hw_sweep_ms_list.append(est_sweep)
                total_span = float(np.max(mat) - np.min(mat))
                total_pts = n_pts * min_len
                hw_total_ms = total_span * (total_pts / max(1, total_pts - 1))

        # Dauer für EINEN einzelnen Sweep berechnen (entweder aus HW-Timestamps oder aus API-Gesamtzeit / Spectra)
        single_sweep_ms = None
        if hw_sweep_ms_list:
            single_sweep_ms = float(np.mean(hw_sweep_ms_list))
        elif api_dur_ms is not None:
            single_sweep_ms = float(api_dur_ms) / max(1, spectra_count)

        f_arr = np.array(f_list, dtype=float)
        re_arr = np.array(re_mean_l, dtype=float)
        im_arr = np.array(im_mean_l, dtype=float)
        z_arr = np.array(z_mean_l, dtype=float)
        ph_arr = np.array(ph_mean_l, dtype=float)

        results[label] = {
            "frequency": f_arr,
            "real": re_arr,
            "imag": im_arr,
            "z_mag": z_arr,
            "z_std": np.array(z_std_l, dtype=float),
            "phase": ph_arr,
            "phase_std": np.array(ph_std_l, dtype=float),
            "current_range": np.array(cr_list, dtype=int) if cr_list else np.array([]),
            "spectra_count": spectra_count,
            "api_duration_ms": float(api_dur_ms) if api_dur_ms is not None else None,
            "single_sweep_ms": single_sweep_ms,
            "hw_sweep_ms_list": hw_sweep_ms_list,
            "hw_total_ms": hw_total_ms,
            "hw_ts_unit": hw_ts_unit,
            "component_est": _estimate_component(f_arr, z_arr, ph_arr, im_arr),
        }

    return results, sorted(list(set(block_transitions))), meta_info


def _parse_sciospec_gui_hdf5(h5: h5py.File) -> tuple[dict[str, dict], list[float], dict]:
    """Liest das native Sciospec-Software HDF5-Format (.scio5 / .h5) inklusive Standardabweichung und Timestamps aus."""
    results = {}
    block_transitions = []
    meta_info = {"type": "SCIOSPEC_GUI", "sections": {}}

    for top_key in h5.keys():
        top_obj = h5[top_key]
        if not isinstance(top_obj, h5py.Group):
            continue

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

            spectra_count = 1
            if raw_meas.ndim == 3:
                spectra_count = raw_meas.shape[0]
                re_all = raw_meas[:, :, 0]
                im_all = raw_meas[:, :, 1]
                z_all = np.hypot(re_all, im_all)
                ph_all = np.degrees(np.arctan2(im_all, re_all))

                re_arr = np.mean(re_all, axis=0)
                im_arr = np.mean(im_all, axis=0)
                z_arr = np.mean(z_all, axis=0)
                z_std = np.std(z_all, axis=0, ddof=1) if spectra_count > 1 else np.zeros_like(z_arr)
                ph_arr = np.mean(ph_all, axis=0)
                ph_std = np.std(ph_all, axis=0, ddof=1) if spectra_count > 1 else np.zeros_like(ph_arr)
            elif raw_meas.ndim == 2:
                re_arr = raw_meas[:, 0]
                im_arr = raw_meas[:, 1]
                z_arr = np.hypot(re_arr, im_arr)
                z_std = np.zeros_like(z_arr)
                ph_arr = np.degrees(np.arctan2(im_arr, re_arr))
                ph_std = np.zeros_like(ph_arr)
            else:
                continue

            min_len = min(len(f_arr), len(re_arr), len(im_arr))
            f_arr, re_arr, im_arr = f_arr[:min_len], re_arr[:min_len], im_arr[:min_len]
            z_arr, z_std = z_arr[:min_len], z_std[:min_len]
            ph_arr, ph_std = ph_arr[:min_len], ph_std[:min_len]

            hw_sweep_ms_list = []
            hw_total_ms = None
            single_sweep_ms = None
            if "timestamp" in port_obj:
                try:
                    ts_raw = np.array(port_obj["timestamp"][()], dtype=float).flatten()
                    if len(ts_raw) > 1:
                        span_s = float(np.max(ts_raw) - np.min(ts_raw))
                        scale = 1.0 if span_s > 100.0 else 1000.0
                        hw_total_ms = span_s * scale
                        single_sweep_ms = hw_total_ms / max(1, spectra_count)
                        hw_sweep_ms_list = [single_sweep_ms]
                except Exception:
                    pass

            label = f"Sciospec GUI ({port_key})"
            results[label] = {
                "frequency": f_arr,
                "real": re_arr,
                "imag": im_arr,
                "z_mag": z_arr,
                "z_std": z_std,
                "phase": ph_arr,
                "phase_std": ph_std,
                "current_range": np.array([]),
                "spectra_count": spectra_count,
                "api_duration_ms": hw_total_ms,
                "single_sweep_ms": single_sweep_ms,
                "hw_sweep_ms_list": hw_sweep_ms_list,
                "hw_total_ms": hw_total_ms,
                "hw_ts_unit": "s/ms",
                "component_est": _estimate_component(f_arr, z_arr, ph_arr, im_arr),
            }

    return results, sorted(list(set(block_transitions))), meta_info


def parse_any_hdf5_file(h5_file: str) -> tuple[dict[str, dict], list[float], str, dict]:
    """Erkennt automatisch, ob eine API-HDF5-Datei oder eine Sciospec-GUI-HDF5-Datei vorliegt."""
    with h5py.File(h5_file, "r") as h5:
        keys = list(h5.keys())
        is_api = any(
            k.startswith("Sensor_") or k.startswith("Measurement") or k == "Configuration"
            for k in keys
        )

        if is_api:
            data, trans, meta = _parse_api_hdf5(h5)
            return data, trans, "API", meta
        else:
            data, trans, meta = _parse_sciospec_gui_hdf5(h5)
            if data:
                return data, trans, "SCIOSPEC_GUI", meta
            data, trans, meta = _parse_api_hdf5(h5)
            return data, trans, "API", meta


def print_diagnostic_report(data_dict: dict, meta_info: dict, file_name: str) -> None:
    """Gibt den kompletten Konfigurations-Steckbrief, die Timing-Analyse, Autoranging und Bauteil-Schätzung aus."""
    print("\n" + "=" * 80)
    print(f" DIAGNOSE-, TIMING- & BAUTEIL-REPORT: {file_name}")
    print("=" * 80)

    if meta_info.get("type") == "API" and meta_info.get("sections"):
        secs = meta_info["sections"]
        conn = secs.get("Connection", {})
        fe = secs.get("Frontend", {})
        mux = secs.get("MUX", {})
        fsetup = secs.get("FrequencySetup", {})
        meas = secs.get("Measurement", {})

        dev_ver = meta_info.get("device_version", conn.get("device_version", "standard")).upper()
        port = conn.get("port", "-")
        mux_en = mux.get("enabled", "False")
        cr_code = int(fe.get("current_range", 2))
        cr_text = CR_LABELS.get(cr_code, str(cr_code))
        amp = fsetup.get("amplitude", "-")
        exc = "Voltage (Spannung)" if str(fsetup.get("excitation_type", "2")) == "1" else "Current (Strom)"

        print(f" [KONFIGURATIONS-STECKBRIEF]")
        print(f"  • Geräte-Modell   : {dev_ver} (Port: {port})")
        print(f"  • Betriebsart     : {'MUX (Aktive Sensoren/Pins: ' + str(mux.get('active_sensors', '-')) + ')' if mux_en == 'True' else 'Main Port (Front-BNC)'}")
        print(f"  • Anregung & Range: {exc} | Amplitude = {amp} | Current Range = {cr_text}")
        print(f"  • Timing-Optionen : Spectra = {meas.get('number_of_spectra', '1')} | Point Delay = {fsetup.get('point_delay_ms', '-')} ms")
        print("-" * 80)

    print(" [TIMING-ANALYSE PRO SENSOR, WIEDERHOLGENAUIGKEIT & BAUTEIL-SCHÄTZUNG]")
    for label, d in data_dict.items():
        n_pts = len(d["frequency"])
        n_spec = d["spectra_count"]
        api_ms = d["api_duration_ms"]
        sw_ms = d["single_sweep_ms"]

        print(f"\n  >>> {label} ({n_pts} Frequenzpunkte × {n_spec} Wiederholung(en)) <<<")
        print(f"      • Bauteil-Schätzung : {d['component_est']}")

        if n_spec > 1:
            mean_rel_std = float(np.mean(d["z_std"] / np.maximum(d["z_mag"], 1e-12)) * 100.0)
            max_rel_std = float(np.max(d["z_std"] / np.maximum(d["z_mag"], 1e-12)) * 100.0)
            print(f"      • Statistik (±1σ)   : Mittlere Streuung |Z| = ±{mean_rel_std:.3f} % (Max: ±{max_rel_std:.3f} %)")

        if api_ms is not None:
            print(f"      • Gesamt-Messzeit   : {api_ms:.2f} ms ({api_ms / 1000.0:.3f} s) für alle {n_spec} Durchläufe")
        if sw_ms is not None:
            ms_per_pt = sw_ms / max(1, n_pts)
            print(f"      • Dauer für 1 Sweep : {sw_ms:.2f} ms ({sw_ms / 1000.0:.3f} s) -> ≈ {ms_per_pt:.2f} ms pro Frequenzpunkt")

        cr_arr = d["current_range"]
        if len(cr_arr) > 0 and np.any(cr_arr >= 0):
            unique_crs = sorted(list(set(cr_arr[cr_arr >= 0])))
            cr_names = [f"Code {c} ({CR_LABELS.get(c, 'Unbekannt')})" for c in unique_crs]
            print(f"      • Aktive Strombereiche: {', '.join(cr_names)}")
            switches = []
            for idx in range(1, len(cr_arr)):
                if cr_arr[idx] != cr_arr[idx - 1]:
                    switches.append(f"bei {d['frequency'][idx]:g} Hz (Code {cr_arr[idx-1]} -> {cr_arr[idx]})")
            if switches:
                print(f"      • Autoranging-Schaltpunkte: {', '.join(switches)}")

    print("=" * 80)


def _ask_plot_and_axis_options() -> dict:
    """Fragt den Nutzer nach Diagrammtyp, Achsenskalierung und Fehlerbändern."""
    print("\n--- DIAGRAMM- & DARSTELLUNGS-OPTIONEN ---")
    print("  Welchen Diagramm-Typ möchtest du anzeigen?")
    print("    [1] Bode-Diagramm (|Z| und Phase φ über Frequenz) [Standard]")
    print("    [2] Kombi-Dashboard (Bode-Diagramm links + Nyquist-Ortskurve rechts)")
    print("    [3] Nyquist-Diagramm (Ortskurve: Im{Z} über Re{Z})")
    print("    [4] Real- und Imaginärteil über der Frequenz")
    pt_choice = input("  Deine Wahl (1-4) [Standard: 1]: ").strip()
    plot_mode_map = {"1": "bode", "2": "dashboard", "3": "nyquist", "4": "re_im"}
    plot_mode = plot_mode_map.get(pt_choice, "bode")

    y_scale = "log"
    x_scale = "log"
    if plot_mode in ("bode", "dashboard"):
        print("\n  Skalierung der Betrags-Achse |Z| (Y-Achse):")
        print("    [1] Logarithmisch (Log-Log Bode-Plot) [Standard]")
        print("    [2] Linear (Wie Standard-Ansicht in der Sciospec-GUI)")
        y_choice = input("  Deine Wahl (1 oder 2) [Standard: 1]: ").strip()
        y_scale = "linear" if y_choice == "2" else "log"

        print("\n  Skalierung der Frequenz-Achse f (X-Achse):")
        print("    [1] Logarithmisch [Standard]")
        print("    [2] Linear")
        x_choice = input("  Deine Wahl (1 oder 2) [Standard: 1]: ").strip()
        x_scale = "linear" if x_choice == "2" else "log"

    show_std_in = input("\n  Standardabweichung (±1σ Fehlerband) anzeigen, falls mehrere Sweeps vorliegen? ([J]/n): ").strip().lower()
    show_std = show_std_in not in ["n", "nein", "no"]

    custom_limits = input("  Manuelle Achsen-Grenzen (Min/Max) für Bode festlegen? (j/[N]): ").strip().lower()
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
        "plot_mode": plot_mode,
        "x_scale": x_scale,
        "y_scale": y_scale,
        "show_std": show_std,
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


def _draw_bode_on_axes(ax_z, ax_p, data_dict: dict, transitions: list[float], axis_opts: dict, colors: list[str], prefix: str = "", line_style: str = "o-") -> None:
    """Hilfsfunktion zum Zeichnen von Bode-Kurven inkl. ±1σ-Fehlerband und Sweep-Dauer in der Legende."""
    for ch_idx, (label, data) in enumerate(data_dict.items()):
        freqs = data["frequency"]
        z_mag = data["z_mag"]
        z_std = data["z_std"]
        phase = data["phase"]
        ph_std = data["phase_std"]
        cr_arr = data["current_range"]

        time_tag = ""
        if data.get("single_sweep_ms") is not None:
            sw_s = data["single_sweep_ms"] / 1000.0
            time_tag = f" [1 Sweep: {sw_s:.2f} s]" if sw_s >= 1.0 else f" [1 Sweep: {data['single_sweep_ms']:.0f} ms]"

        full_label_base = f"{prefix}{label}{time_tag}"

        indices = [0]
        if not prefix:
            for t in transitions[:-1]:
                idx = int(np.searchsorted(freqs, t))
                if 0 < idx < len(freqs):
                    indices.append(idx)
        indices.append(len(freqs))

        for i in range(len(indices) - 1):
            start_i = indices[i]
            end_i = indices[i + 1]
            plot_end = min(len(freqs), end_i + 1) if i < len(indices) - 2 else end_i
            col = colors[(ch_idx + i) % len(colors)]
            blk_suffix = f" - Block {i + 1}" if len(indices) > 2 else ""
            lbl = f"{full_label_base}{blk_suffix}"

            f_seg = freqs[start_i:plot_end]
            z_seg = z_mag[start_i:plot_end]
            p_seg = phase[start_i:plot_end]

            ax_z.plot(f_seg, z_seg, line_style, color=col, linewidth=1.7, markersize=4.5, label=lbl)
            ax_p.plot(f_seg, p_seg, line_style, color=col, linewidth=1.7, markersize=4.5, label=lbl)

            if axis_opts.get("show_std", True) and data["spectra_count"] > 1:
                zs_seg = z_std[start_i:plot_end]
                ps_seg = ph_std[start_i:plot_end]
                z_low = np.maximum(z_seg - zs_seg, 1e-12) if axis_opts["y_scale"] == "log" else (z_seg - zs_seg)
                ax_z.fill_between(f_seg, z_low, z_seg + zs_seg, color=col, alpha=0.18)
                ax_p.fill_between(f_seg, p_seg - ps_seg, p_seg + ps_seg, color=col, alpha=0.18)

        if len(cr_arr) == len(freqs) and np.any(cr_arr >= 0):
            for idx in range(1, len(cr_arr)):
                if cr_arr[idx] != cr_arr[idx - 1]:
                    f_sw = freqs[idx]
                    ax_z.axvline(f_sw, color="#cc00cc", linestyle="--", alpha=0.6)
                    ax_p.axvline(f_sw, color="#cc00cc", linestyle="--", alpha=0.6, label=f"CR-Switch @ {f_sw:g} Hz")


def plot_single_file(data_dict: dict, transitions: list[float], file_name: str, file_type: str, axis_opts: dict) -> None:
    """Plottet eine einzelne Datei im gewählten Modus (Bode, Dashboard, Nyquist oder Real/Imag)."""
    if not data_dict:
        print("[FEHLER] Keine gültigen Messdaten in der Datei gefunden.")
        return

    mode = axis_opts.get("plot_mode", "bode")
    colors = ["#0055cc", "#e66000", "#1b8a5a", "#800080", "#8c564b", "#008080"]

    if mode == "dashboard":
        fig = plt.figure(figsize=(15, 8))
        gs = fig.add_gridspec(2, 2, width_ratios=[1.35, 1.0])
        ax_z = fig.add_subplot(gs[0, 0])
        ax_p = fig.add_subplot(gs[1, 0], sharex=ax_z)
        ax_nyq = fig.add_subplot(gs[:, 1])

        _draw_bode_on_axes(ax_z, ax_p, data_dict, transitions, axis_opts, colors)
        for t in transitions[:-1]:
            ax_z.axvline(t, color="red", linestyle=":", alpha=0.7)
            ax_p.axvline(t, color="red", linestyle=":", alpha=0.7)
        _apply_axis_limits(ax_z, ax_p, axis_opts)

        ax_z.set_ylabel(r"Betrag $|Z|$ / $\Omega$")
        ax_z.set_title(f"Bode-Diagramm [{file_type}]: {file_name}")
        ax_z.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_z.legend(loc="best", fontsize=8)

        ax_p.set_xlabel("Frequenz $f$ / Hz")
        ax_p.set_ylabel(r"Phase $\phi$ / °")
        ax_p.grid(True, which="both", linestyle="--", alpha=0.5)

        for idx, (label, d) in enumerate(data_dict.items()):
            col = colors[idx % len(colors)]
            ax_nyq.plot(d["real"], d["imag"], "o-", color=col, markersize=4.5, label=f"{label} ({d['component_est'].split('(')[0].strip()})")
        ax_nyq.axhline(0, color="black", linewidth=0.8, linestyle=":")
        ax_nyq.axvline(0, color="black", linewidth=0.8, linestyle=":")
        ax_nyq.set_xlabel(r"Realteil $Z_{\mathrm{real}}$ / $\Omega$")
        ax_nyq.set_ylabel(r"Imaginärteil $Z_{\mathrm{imag}}$ / $\Omega$")
        ax_nyq.set_title("Nyquist-Ortskurve")
        ax_nyq.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_nyq.legend(loc="best", fontsize=8)

    elif mode == "nyquist":
        fig, ax_nyq = plt.subplots(figsize=(9, 7))
        for idx, (label, d) in enumerate(data_dict.items()):
            col = colors[idx % len(colors)]
            ax_nyq.plot(d["real"], d["imag"], "o-", color=col, markersize=5, label=label)
        ax_nyq.axhline(0, color="black", linewidth=0.8, linestyle=":")
        ax_nyq.axvline(0, color="black", linewidth=0.8, linestyle=":")
        ax_nyq.set_aspect("equal", adjustable="datalim")
        ax_nyq.set_xlabel(r"Realteil $Z_{\mathrm{real}}$ / $\Omega$")
        ax_nyq.set_ylabel(r"Imaginärteil $Z_{\mathrm{imag}}$ / $\Omega$")
        ax_nyq.set_title(f"Nyquist-Diagramm [{file_type}]: {file_name}")
        ax_nyq.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_nyq.legend(loc="best")

    elif mode == "re_im":
        fig, (ax_re, ax_im) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        for idx, (label, d) in enumerate(data_dict.items()):
            col = colors[idx % len(colors)]
            ax_re.plot(d["frequency"], d["real"], "o-", color=col, label=f"{label} (Real)")
            ax_im.plot(d["frequency"], d["imag"], "s--", color=col, label=f"{label} (Imag)")
        ax_re.set_xscale("log")
        ax_im.set_xscale("log")
        ax_re.set_ylabel(r"$Z_{\mathrm{real}}$ / $\Omega$")
        ax_im.set_ylabel(r"$Z_{\mathrm{imag}}$ / $\Omega$")
        ax_im.set_xlabel("Frequenz $f$ / Hz")
        ax_re.set_title(f"Real- und Imaginärteil [{file_type}]: {file_name}")
        ax_re.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_im.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_re.legend(loc="best")
        ax_im.legend(loc="best")

    else:
        fig, (ax_z, ax_p) = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
        _draw_bode_on_axes(ax_z, ax_p, data_dict, transitions, axis_opts, colors)
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
    """Plottet zwei HDF5-Dateien (z.B. API vs. Sciospec-GUI) zum direkten Vergleich inklusive Timing-Vergleich."""
    if not data_1 or not data_2:
        print("[FEHLER] Mindestens eine der beiden Dateien enthält keine gültigen Messdaten.")
        return

    first_d1 = next(iter(data_1.values()))
    first_d2 = next(iter(data_2.values()))
    print("\n" + "=" * 75)
    print(f" DIREKTER VERGLEICHS-REPORT: {name_1}  vs.  {name_2}")
    print("=" * 75)
    if len(first_d1["z_mag"]) == len(first_d2["z_mag"]):
        rel_err_z = np.abs(first_d1["z_mag"] - first_d2["z_mag"]) / np.maximum(first_d2["z_mag"], 1e-12) * 100.0
        abs_err_p = np.abs(first_d1["phase"] - first_d2["phase"])
        print(f" • Mittlere Abweichung |Z| : {np.mean(rel_err_z):.3f} % (Max: {np.max(rel_err_z):.3f} %)")
        print(f" • Mittlere Abweichung φ   : {np.mean(abs_err_p):.3f} ° (Max: {np.max(abs_err_p):.3f} °)")
    else:
        print(f" • Hinweis: Unterschiedliche Punktanzahl ({len(first_d1['z_mag'])} vs. {len(first_d2['z_mag'])} Punkte).")

    t1_sw = first_d1.get("single_sweep_ms")
    t2_sw = first_d2.get("single_sweep_ms")
    if t1_sw is not None or t2_sw is not None:
        s1 = f"{t1_sw:.1f} ms ({t1_sw / 1000.0:.2f} s)" if t1_sw is not None else "nicht aufgezeichnet"
        s2 = f"{t2_sw:.1f} ms ({t2_sw / 1000.0:.2f} s)" if t2_sw is not None else "nicht aufgezeichnet"
        print(f" • Dauer für 1 Sweep       : Datei 1 = {s1}  |  Datei 2 = {s2}")
    print("=" * 75)

    mode = axis_opts.get("plot_mode", "bode")
    colors_1 = ["#0055cc", "#0088ff", "#003380"]
    colors_2 = ["#e63900", "#ff8000", "#992600"]

    if mode == "dashboard":
        fig = plt.figure(figsize=(15, 8))
        gs = fig.add_gridspec(2, 2, width_ratios=[1.35, 1.0])
        ax_z = fig.add_subplot(gs[0, 0])
        ax_p = fig.add_subplot(gs[1, 0], sharex=ax_z)
        ax_nyq = fig.add_subplot(gs[:, 1])

        _draw_bode_on_axes(ax_z, ax_p, data_1, transitions, axis_opts, colors_1, prefix=f"{name_1} | ", line_style="o-")
        _draw_bode_on_axes(ax_z, ax_p, data_2, transitions, axis_opts, colors_2, prefix=f"{name_2} | ", line_style="s--")
        _apply_axis_limits(ax_z, ax_p, axis_opts)

        ax_z.set_ylabel(r"Betrag $|Z|$ / $\Omega$")
        ax_z.set_title(f"Bode-Vergleich: {name_1} vs. {name_2}")
        ax_z.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_z.legend(loc="best", fontsize=8)
        ax_p.set_xlabel("Frequenz $f$ / Hz")
        ax_p.set_ylabel(r"Phase $\phi$ / °")
        ax_p.grid(True, which="both", linestyle="--", alpha=0.5)

        for idx, (l1, d1) in enumerate(data_1.items()):
            ax_nyq.plot(d1["real"], d1["imag"], "o-", color=colors_1[idx % len(colors_1)], label=f"{name_1} | {l1}")
        for idx, (l2, d2) in enumerate(data_2.items()):
            ax_nyq.plot(d2["real"], d2["imag"], "s--", color=colors_2[idx % len(colors_2)], label=f"{name_2} | {l2}")
        ax_nyq.set_xlabel(r"Realteil $Z_{\mathrm{real}}$ / $\Omega$")
        ax_nyq.set_ylabel(r"Imaginärteil $Z_{\mathrm{imag}}$ / $\Omega$")
        ax_nyq.set_title("Nyquist-Vergleich")
        ax_nyq.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_nyq.legend(loc="best", fontsize=8)
    else:
        fig, (ax_z, ax_p) = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
        _draw_bode_on_axes(ax_z, ax_p, data_1, transitions, axis_opts, colors_1, prefix=f"{name_1} | ", line_style="o-")
        _draw_bode_on_axes(ax_z, ax_p, data_2, transitions, axis_opts, colors_2, prefix=f"{name_2} | ", line_style="s--")

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
    print("\n" + "=" * 75)
    print(" HDF5 AUSWERTUNG, TIMING-ANALYSE & VERGLEICH (API & SCIOSPEC-GUI)")
    print("=" * 75)
    print("Was möchtest du tun?")
    print("  [1] Nur EINE Datei auswerten & plotten (API .h5 ODER Sciospec-GUI .scio5/.h5) [Standard]")
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

        data_1, trans_1, type_1, meta_1 = parse_any_hdf5_file(path_1)
        data_2, trans_2, type_2, meta_2 = parse_any_hdf5_file(path_2)
        print_diagnostic_report(data_1, meta_1, os.path.basename(path_1))
        print_diagnostic_report(data_2, meta_2, os.path.basename(path_2))

        axis_opts = _ask_plot_and_axis_options()
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

        data_dict, transitions, f_type, meta_info = parse_any_hdf5_file(h5_path)
        print_diagnostic_report(data_dict, meta_info, os.path.basename(h5_path))

        axis_opts = _ask_plot_and_axis_options()
        plot_single_file(
            data_dict=data_dict,
            transitions=transitions,
            file_name=os.path.basename(h5_path),
            file_type=f_type,
            axis_opts=axis_opts,
        )

def plot_multi_file_comparison(
    datasets: list[tuple[str, dict, dict, list[float]]],
    axis_opts: dict,
) -> None:
    """
    Legt beliebig viele HDF5-Messdateien (z.B. 3 Messungen mit 4, 12 und 20 Pins)
    in einem gemeinsamen Bode-Plot (oder Kombi-Dashboard) uebereinander.
    """
    if not datasets:
        print("[FEHLER] Keine gueltigen Datensaetze zum Vergleichen vorhanden.")
        return

    palette = [
        "#0055cc",  # Blau (z.B. 4 Pins)
        "#e66000",  # Orange (z.B. 12 Pins)
        "#1b8a5a",  # Gruen (z.B. 20 Pins)
        "#cc00cc",  # Magenta
        "#8c564b",  # Braun
        "#008080",  # Teal
    ]
    markers = ["o-", "s--", "^-.", "d:", "v-", "P--"]

    print("\n" + "=" * 85)
    print(f" MULTI-DATEI VERGLEICHS-TABELLE ({len(datasets)} MESSREIHEN)")
    print("=" * 85)
    print(f" {'Nr.':<4} | {'Datei / Pin-Konfiguration':<42} | {'|Z| @ 1 kHz':<14} | {'|Z| @ 1 MHz':<14}")
    print("-" * 85)

    all_transitions = []
    mode = axis_opts.get("plot_mode", "bode")

    if mode == "dashboard":
        fig = plt.figure(figsize=(15, 8))
        gs = fig.add_gridspec(2, 2, width_ratios=[1.35, 1.0])
        ax_z = fig.add_subplot(gs[0, 0])
        ax_p = fig.add_subplot(gs[1, 0], sharex=ax_z)
        ax_nyq = fig.add_subplot(gs[:, 1])
    else:
        fig, (ax_z, ax_p) = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
        ax_nyq = None

    for idx, (file_name, data_dict, meta_info, trans) in enumerate(datasets):
        all_transitions.extend(trans)
        col = palette[idx % len(palette)]
        style = markers[idx % len(markers)]

        # Aktive Pin-Konfiguration automatisch aus den HDF5-Metadaten (Configuration/MUX) holen
        pin_info = ""
        if meta_info.get("type") == "API" and "MUX" in meta_info.get("sections", {}):
            mux_sec = meta_info["sections"]["MUX"]
            if str(mux_sec.get("enabled", "False")) == "True":
                raw_sens = str(mux_sec.get("active_sensors", "")).strip()
                if raw_sens:
                    pin_info = f" [{raw_sens}]"

        for ch_label, d in data_dict.items():
            freqs = d["frequency"]
            z_mag = d["z_mag"]
            z_std = d["z_std"]
            phase = d["phase"]
            ph_std = d["phase_std"]

            # Kennwerte bei ~1 kHz (Plateau) und ~1 MHz (Kapazitaet) fuer die Tabelle ermitteln
            idx_1k = int(np.argmin(np.abs(freqs - 1000.0)))
            idx_1m = int(np.argmin(np.abs(freqs - 1000000.0)))
            z_1k = z_mag[idx_1k] if len(z_mag) > 0 else 0.0
            z_1m = z_mag[idx_1m] if len(z_mag) > 0 else 0.0

            short_pin = (pin_info[:38] + "..]") if len(pin_info) > 41 else pin_info
            table_label = short_pin.strip(" []") if short_pin else file_name
            print(f" #{idx+1:<3} | {table_label:<42} | {z_1k:>10.2f} Ohm | {z_1m:>10.2f} Ohm")

            legend_lbl = f"#{idx+1}: {file_name}{pin_info} (|Z|_1k={z_1k:.0f} Ω)"

            ax_z.plot(freqs, z_mag, style, color=col, linewidth=1.8, markersize=5, label=legend_lbl)
            ax_p.plot(freqs, phase, style, color=col, linewidth=1.8, markersize=5, label=legend_lbl)

            if axis_opts.get("show_std", True) and d.get("spectra_count", 1) > 1:
                z_low = np.maximum(z_mag - z_std, 1e-12) if axis_opts["y_scale"] == "log" else (z_mag - z_std)
                ax_z.fill_between(freqs, z_low, z_mag + z_std, color=col, alpha=0.15)
                ax_p.fill_between(freqs, phase - ph_std, phase + ph_std, color=col, alpha=0.15)

            if ax_nyq is not None:
                ax_nyq.plot(d["real"], d["imag"], style, color=col, markersize=4.5, label=legend_lbl)

    print("=" * 85)

    unique_trans = sorted(list(set(all_transitions)))
    for t in unique_trans[:-1]:
        ax_z.axvline(t, color="gray", linestyle=":", alpha=0.7)
        ax_p.axvline(t, color="gray", linestyle=":", alpha=0.7)

    _apply_axis_limits(ax_z, ax_p, axis_opts)
    scale_info = "Linear |Z|" if axis_opts["y_scale"] == "linear" else "Log |Z|"

    ax_z.set_ylabel(r"Betrag $|Z|$ / $\Omega$")
    ax_z.set_title(f"Multi-Pin / Mehrdateien-Vergleich ({len(datasets)} Messreihen, {scale_info})")
    ax_z.grid(True, which="both", linestyle="--", alpha=0.5)
    ax_z.legend(loc="best", fontsize=8.5)

    ax_p.set_xlabel("Frequenz $f$ / Hz")
    ax_p.set_ylabel(r"Phase $\phi$ / °")
    ax_p.grid(True, which="both", linestyle="--", alpha=0.5)
    ax_p.legend(loc="best", fontsize=8.5)

    if ax_nyq is not None:
        ax_nyq.axhline(0, color="black", linewidth=0.8, linestyle=":")
        ax_nyq.axvline(0, color="black", linewidth=0.8, linestyle=":")
        ax_nyq.set_xlabel(r"Realteil $Z_{\mathrm{real}}$ / $\Omega$")
        ax_nyq.set_ylabel(r"Imaginärteil $Z_{\mathrm{imag}}$ / $\Omega$")
        ax_nyq.set_title("Nyquist-Vergleich")
        ax_nyq.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_nyq.legend(loc="best", fontsize=8)

    plt.tight_layout()
    plt.show()


def main():
    print("\n" + "=" * 75)
    print(" HDF5 AUSWERTUNG, TIMING-ANALYSE & VERGLEICH (API & SCIOSPEC-GUI)")
    print("=" * 75)
    print("Was möchtest du tun?")
    print("  [1] Nur EINE Datei auswerten & plotten (API .h5 ODER Sciospec-GUI .scio5/.h5) [Standard]")
    print("  [2] ZWEI Dateien direkt vergleichen (z.B. API-Messung vs. Sciospec-GUI)")
    print("  [3] MEHRERE Dateien (z.B. 3 Messreihen: 4 Pins, 12 Pins, 20 Pins) übereinanderlegen")
    mode_choice = input("\nDeine Wahl (1, 2 oder 3) [Standard: 1]: ").strip()

    if mode_choice == "3":
        count_in = input("\nWie viele Dateien möchtest du übereinanderlegen? [Standard: 3]: ").strip()
        num_files = int(count_in) if count_in.isdigit() and int(count_in) >= 2 else 3

        datasets = []
        for i in range(1, num_files + 1):
            print(f"\n-> Bitte wähle Datei #{i} von {num_files} aus...")
            p = select_h5_file(title=f"Datei #{i} von {num_files} wählen (z.B. {i*4} Pins)")
            if not p:
                print(f"[INFO] Auswahl bei Datei #{i} abgebrochen.")
                break
            d_dict, trans, f_type, meta = parse_any_hdf5_file(p)
            print_diagnostic_report(d_dict, meta, os.path.basename(p))
            datasets.append((os.path.basename(p), d_dict, meta, trans))

        if len(datasets) >= 2:
            axis_opts = _ask_plot_and_axis_options()
            plot_multi_file_comparison(datasets=datasets, axis_opts=axis_opts)
        else:
            print("[WARNUNG] Für einen Mehrfach-Vergleich werden mindestens 2 Dateien benötigt.")

    elif mode_choice == "2":
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

        data_1, trans_1, type_1, meta_1 = parse_any_hdf5_file(path_1)
        data_2, trans_2, type_2, meta_2 = parse_any_hdf5_file(path_2)
        print_diagnostic_report(data_1, meta_1, os.path.basename(path_1))
        print_diagnostic_report(data_2, meta_2, os.path.basename(path_2))

        axis_opts = _ask_plot_and_axis_options()
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

        data_dict, transitions, f_type, meta_info = parse_any_hdf5_file(h5_path)
        print_diagnostic_report(data_dict, meta_info, os.path.basename(h5_path))

        axis_opts = _ask_plot_and_axis_options()
        plot_single_file(
            data_dict=data_dict,
            transitions=transitions,
            file_name=os.path.basename(h5_path),
            file_type=f_type,
            axis_opts=axis_opts,
        )

if __name__ == "__main__":
    main()