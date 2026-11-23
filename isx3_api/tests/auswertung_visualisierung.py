"""
auswertung_visualisierung.py - Universal evaluation, timing analysis, and comparison visualization
for custom Python API HDF5 files (.h5), official Sciospec GUI HDF5 files (.scio5 / .h5),
and classic Sciospec ASCII spectrum files (.spec, including multi-file MUX & repeat grouping).

Integrated features:
1. Timing & performance analysis per sensor (total duration, single-sweep duration, time per point,
   and execution mode comparison: 'sweep' 0xB6 Sub 0x03 vs. 'point_list' 0xB6 Sub 0x02 vs. 'single')
2. Statistical repeatability (±1 sigma standard deviation shaded error bands for multi-sweep runs)
3. Dynamic autoranging evaluation (detection of current range switches across frequencies)
4. Multi-plot selection (Bode, Nyquist, Real/Imag, or combined Bode + Nyquist dashboard)
5. Automatic configuration summary & equivalent circuit component estimation (R, C, L)
6. Multi-file overlay comparison & automatic MUX sensor matching (1 API .h5 vs. N .spec files)
"""

import os
import re
from datetime import datetime
from tkinter import Tk, filedialog
import h5py
import matplotlib.pyplot as plt
import numpy as np


DEFAULT_H5_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "measurements"))

CR_LABELS = {
    0: "Autoranging",
    1: "±10 mA (100 Ω)",
    2: "±100 µA (10 kΩ)",
    4: "±1 µA (1 MΩ)",
    6: "±10 nA (100 MΩ)",
}


def select_measurement_files(
    title: str = "Messdatei(en) wählen (.h5, .scio5 oder eine/mehrere .spec Dateien)",
    allow_multiple: bool = True,
) -> list[str]:
    """
    Opens a file dialog to select one HDF5 file (.h5 / .scio5) or one/multiple
    Sciospec ASCII spectrum files (.spec).
    """
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    init_dir = DEFAULT_H5_DIR if os.path.exists(DEFAULT_H5_DIR) else os.getcwd()

    if allow_multiple:
        paths = filedialog.askopenfilenames(
            title=title,
            initialdir=init_dir,
            filetypes=[
                ("Alle unterstützten Messdaten", "*.h5 *.hdf5 *.scio5 *.spec"),
                ("HDF5 / Sciospec Container", "*.h5 *.hdf5 *.scio5"),
                ("Sciospec ASCII Spektren (.spec)", "*.spec"),
                ("Alle Dateien", "*.*"),
            ],
        )
        root.destroy()
        return list(paths) if paths else []
    else:
        path = filedialog.askopenfilename(
            title=title,
            initialdir=init_dir,
            filetypes=[
                ("Alle unterstützten Messdaten", "*.h5 *.hdf5 *.scio5 *.spec"),
                ("HDF5 / Sciospec Container", "*.h5 *.hdf5 *.scio5"),
                ("Sciospec ASCII Spektren (.spec)", "*.spec"),
                ("Alle Dateien", "*.*"),
            ],
        )
        root.destroy()
        return [path] if path else []


def _estimate_component(freqs: np.ndarray, z_mag: np.ndarray, phase: np.ndarray, imag: np.ndarray) -> str:
    """Estimates whether a resistor (R), capacitor (C), or inductor (L) is measured based on phase angle."""
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


def _parse_spec_timestamp(ts_str: str) -> float | None:
    """
    Parses timestamp strings from Sciospec .spec headers into POSIX seconds
    (e.g., '13-Nov.-2026 12:28:08:093 p.m.' or '13-Dec-2021 01:34:43:616 PM').
    """
    s = ts_str.strip()
    if not s:
        return None

    # Normalize German/English month abbreviations and a.m./p.m. markers
    s = s.replace("a.m.", "AM").replace("p.m.", "PM").replace("A.M.", "AM").replace("P.M.", "PM")
    month_replacements = {
        "Jan.": "Jan", "Feb.": "Feb", "Mär.": "Mar", "Mrz.": "Mar", "Mar.": "Mar",
        "Apr.": "Apr", "Mai": "May", "May.": "May", "Jun.": "Jun", "Jul.": "Jul",
        "Aug.": "Aug", "Sep.": "Sep", "Sept.": "Sep", "Okt.": "Oct", "Oct.": "Oct",
        "Nov.": "Nov", "Dez.": "Dec", "Dec.": "Dec",
    }
    for k, v in month_replacements.items():
        s = s.replace(k, v)

    # Convert trailing millisecond colon ':093' into '.093000' for strptime
    m = re.match(r"^(.+\d{2}:\d{2}:\d{2}):(\d{1,3})\s*(AM|PM)?$", s, flags=re.IGNORECASE)
    if m:
        base_part = m.group(1).strip()
        ms_part = m.group(2).zfill(3)
        ampm_part = f" {m.group(3).upper()}" if m.group(3) else ""
        s_clean = f"{base_part}.{ms_part}{ampm_part}"
        for fmt in ("%d-%b-%Y %I:%M:%S.%f %p", "%d-%b-%Y %H:%M:%S.%f", "%Y.%m.%d. %H:%M:%S.%f"):
            try:
                return datetime.strptime(s_clean, fmt).timestamp()
            except ValueError:
                pass
    return None


def _parse_single_spec_file(spec_path: str) -> dict | None:
    """Reads a single Sciospec .spec file and extracts header metadata and impedance columns."""
    with open(spec_path, "r", encoding="utf-8", errors="replace") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

    if not lines:
        return None

    header_idx = None
    for idx, line in enumerate(lines):
        if line.lower().startswith("frequency"):
            header_idx = idx
            break

    if header_idx is None:
        return None

    header_lines = lines[:header_idx]
    data_lines = lines[header_idx + 1 :]

    spec_name = header_lines[1] if len(header_lines) > 1 else os.path.basename(spec_path)
    channel_str = "MAIN PORT"
    offset_str = "0.0V"
    warnings_list = []
    range_list = []
    volt_range_list = []
    timestamp_sec = None

    for hl in header_lines:
        hl_low = hl.lower()
        if hl_low.startswith("channel:"):
            channel_str = hl.split(":", 1)[1].strip()
        elif hl_low.startswith("offset:"):
            offset_str = hl.split(":", 1)[1].strip()
        elif hl_low.startswith("range:"):
            nums = re.findall(r"\d+", hl.split(":", 1)[1])
            range_list = [int(n) for n in nums]
        elif hl_low.startswith("voltrange:"):
            nums = re.findall(r"\d+", hl.split(":", 1)[1])
            volt_range_list = [int(n) for n in nums]
        elif "overcurrent" in hl_low or "overvoltage" in hl_low:
            warnings_list.append(hl)
        else:
            ts_try = _parse_spec_timestamp(hl)
            if ts_try is not None:
                timestamp_sec = ts_try

    freqs, reals, imags = [], [], []
    for dl in data_lines:
        parts = [p.strip() for p in dl.split(",")]
        if len(parts) >= 3:
            try:
                freqs.append(float(parts[0]))
                reals.append(float(parts[1]))
                imags.append(float(parts[2]))
            except ValueError:
                continue

    if not freqs:
        return None

    return {
        "file_path": spec_path,
        "file_name": os.path.basename(spec_path),
        "spec_name": spec_name,
        "channel": channel_str,
        "offset": offset_str,
        "warnings": warnings_list,
        "range_list": range_list,
        "volt_range_list": volt_range_list,
        "timestamp_sec": timestamp_sec,
        "frequency": np.array(freqs, dtype=float),
        "real": np.array(reals, dtype=float),
        "imag": np.array(imags, dtype=float),
    }


def _aggregate_spec_entries(entries: list[dict], label: str) -> dict:
    """Aggregates one or multiple .spec sweeps of the same sensor/channel into mean and ±1 sigma arrays."""
    spectra_count = len(entries)
    f_arr = entries[0]["frequency"]
    min_len = min(len(e["frequency"]) for e in entries)
    f_arr = f_arr[:min_len]

    re_mat = np.array([e["real"][:min_len] for e in entries], dtype=float)
    im_mat = np.array([e["imag"][:min_len] for e in entries], dtype=float)
    z_mat = np.hypot(re_mat, im_mat)
    ph_mat = np.degrees(np.arctan2(im_mat, re_mat))

    re_mean = np.mean(re_mat, axis=0)
    im_mean = np.mean(im_mat, axis=0)
    z_mean = np.mean(z_mat, axis=0)
    z_std = np.std(z_mat, axis=0, ddof=1) if spectra_count > 1 else np.zeros_like(z_mean)
    ph_mean = np.mean(ph_mat, axis=0)
    ph_std = np.std(ph_mat, axis=0, ddof=1) if spectra_count > 1 else np.zeros_like(ph_mean)

    ts_vals = sorted([e["timestamp_sec"] for e in entries if e["timestamp_sec"] is not None])
    single_sweep_ms = None
    total_ms = None
    if len(ts_vals) >= 2:
        diffs_ms = np.diff(ts_vals) * 1000.0
        valid_diffs = diffs_ms[diffs_ms > 0]
        if len(valid_diffs) > 0:
            single_sweep_ms = float(np.median(valid_diffs))
            total_ms = single_sweep_ms * spectra_count

    cr_list = entries[0]["range_list"][:min_len] if entries[0]["range_list"] else []
    cr_arr = np.array(cr_list, dtype=int) if len(cr_list) == min_len else np.array([])

    all_warnings = []
    for e in entries:
        all_warnings.extend(e["warnings"])

    return {
        "frequency": f_arr,
        "real": re_mean,
        "imag": im_mean,
        "z_mag": z_mean,
        "z_std": z_std,
        "phase": ph_mean,
        "phase_std": ph_std,
        "current_range": cr_arr,
        "spectra_count": spectra_count,
        "api_duration_ms": total_ms,
        "single_sweep_ms": single_sweep_ms,
        "hw_sweep_ms_list": [single_sweep_ms] if single_sweep_ms else [],
        "hw_total_ms": total_ms,
        "hw_ts_unit": "ms",
        "execution_mode": "sciospec_gui",
        "component_est": _estimate_component(f_arr, z_mean, ph_mean, im_mean),
        "warnings": sorted(list(set(all_warnings))),
    }


def parse_sciospec_spec_files(
    spec_paths: list[str],
    target_sensor_count: int | None = None,
) -> tuple[dict[str, dict], list[float], str, dict]:
    """
    Parses one or multiple Sciospec .spec files.
    - Automatically groups files by their 'Channel:' header.
    - If all .spec files share the same generic channel name but 'target_sensor_count' (>1)
      is known (e.g., when comparing against an API MUX .h5 file with N sensors), distributes
      the .spec files across the sensors.
    """
    parsed_entries = []
    for sp in sorted(spec_paths):
        item = _parse_single_spec_file(sp)
        if item is not None:
            parsed_entries.append(item)

    if not parsed_entries:
        return {}, [], "SCIOSPEC_SPEC", {"type": "SCIOSPEC_SPEC", "file_count": 0}

    unique_channels = []
    for e in parsed_entries:
        if e["channel"] not in unique_channels:
            unique_channels.append(e["channel"])

    results = {}
    n_files = len(parsed_entries)

    if len(unique_channels) > 1:
        for ch_idx, ch_name in enumerate(unique_channels, start=1):
            ch_entries = [e for e in parsed_entries if e["channel"] == ch_name]
            lbl = f"Sciospec .spec #{ch_idx} ({ch_name})"
            results[lbl] = _aggregate_spec_entries(ch_entries, lbl)

    elif target_sensor_count is not None and target_sensor_count > 1 and n_files >= target_sensor_count:
        print(
            f"\n[INFO] Ordne {n_files} ausgewählte .spec-Datei(en) automatisch den "
            f"{target_sensor_count} MUX-Sensoren der Vergleichsdatei zu..."
        )
        if n_files == target_sensor_count:
            for s_idx in range(target_sensor_count):
                lbl = f"Sciospec .spec Sensor #{s_idx + 1} ({parsed_entries[s_idx]['file_name']})"
                results[lbl] = _aggregate_spec_entries([parsed_entries[s_idx]], lbl)
        else:
            print("  Wie wurden die .spec-Dateien für die MUX-Sensoren von der Sciospec-GUI nummeriert?")
            print("    [1] Zyklisch / Round-Robin (Datei 1=Sens 1, Datei 2=Sens 2 ... danach nächster Sweep) [Standard]")
            print("    [2] Blockweise pro Sensor (erste K Dateien = Sens 1, nächste K Dateien = Sens 2 ...)")
            order_in = input("  Deine Wahl (1 oder 2) [Standard: 1]: ").strip()
            for s_idx in range(target_sensor_count):
                if order_in == "2":
                    chunk = n_files // target_sensor_count
                    s_entries = parsed_entries[s_idx * chunk : (s_idx + 1) * chunk]
                else:
                    s_entries = parsed_entries[s_idx::target_sensor_count]
                lbl = f"Sciospec .spec Sensor #{s_idx + 1} ({len(s_entries)} Sweeps)"
                results[lbl] = _aggregate_spec_entries(s_entries, lbl)

    elif n_files > 1 and target_sensor_count is None:
        print(f"\n[INFO] Es wurden {n_files} .spec-Dateien geladen (Header-Channel: '{unique_channels[0]}').")
        print("  Wie sollen diese .spec-Dateien ausgewertet werden?")
        print(f"    [1] Alle {n_files} Dateien sind Wiederholungen (Sweeps) DESSELBEN Sensors -> Mittelwert & ±1σ bilden [Standard]")
        print(f"    [2] Jede .spec-Datei ist ein EIGENER MUX-Sensor (Sensor #1 bis Sensor #{n_files})")
        print("    [3] Aufteilen auf N MUX-Sensoren mit je K Wiederholungen")
        grp_choice = input("  Deine Wahl (1, 2 oder 3) [Standard: 1]: ").strip()

        if grp_choice == "2":
            for s_idx, entry in enumerate(parsed_entries, start=1):
                lbl = f"Sciospec .spec Sensor #{s_idx} ({entry['file_name']})"
                results[lbl] = _aggregate_spec_entries([entry], lbl)
        elif grp_choice == "3":
            s_cnt_in = input(f"  Anzahl der MUX-Sensoren N (Teiler von {n_files}): ").strip()
            s_cnt = int(s_cnt_in) if s_cnt_in.isdigit() and int(s_cnt_in) > 0 else 1
            for s_idx in range(s_cnt):
                s_entries = parsed_entries[s_idx::s_cnt]
                if s_entries:
                    lbl = f"Sciospec .spec Sensor #{s_idx + 1} ({len(s_entries)} Sweeps)"
                    results[lbl] = _aggregate_spec_entries(s_entries, lbl)
        else:
            lbl = f"Sciospec .spec ({unique_channels[0]}, {n_files} Sweeps)"
            results[lbl] = _aggregate_spec_entries(parsed_entries, lbl)
    else:
        lbl = f"Sciospec .spec ({unique_channels[0]})"
        results[lbl] = _aggregate_spec_entries(parsed_entries, lbl)

    all_warnings = []
    for e in parsed_entries:
        all_warnings.extend(e["warnings"])

    meta_info = {
        "type": "SCIOSPEC_SPEC",
        "file_count": n_files,
        "channels": unique_channels,
        "offset": parsed_entries[0]["offset"],
        "warnings": sorted(list(set(all_warnings))),
    }
    return results, [], "SCIOSPEC_SPEC", meta_info


def _parse_api_hdf5(h5: h5py.File) -> tuple[dict[str, dict], list[float], dict]:
    """Parses the custom Python API HDF5 format including timing, execution mode, standard deviation, and autoranging."""
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

        exec_mode = grp.attrs.get("execution_mode", None)
        if exec_mode is None and "Measurement" in h5 and "execution_mode" in h5["Measurement"].attrs:
            exec_mode = h5["Measurement"].attrs["execution_mode"]
        if exec_mode is None:
            fsetup_sec = meta_info.get("sections", {}).get("FrequencySetup", {})
            exec_mode = fsetup_sec.get("mode", "sweep")

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
        exec_mode_clean = str(exec_mode).strip().lower()

        if hw_ts_matrix and len(hw_ts_matrix) > 1:
            scale_to_ms = 0.001 if hw_ts_unit == "us" else 1.0
            min_len = min(len(row) for row in hw_ts_matrix)
            if min_len > 0:
                mat = np.array([row[:min_len] for row in hw_ts_matrix], dtype=float) * scale_to_ms
                n_pts = mat.shape[0]

                # Fix 1: Erkennung unskalierter Ticks (Faktor 256 in älteren Dateien vor dem 13.11.)
                if np.max(mat) > 100000.0 and (api_dur_ms is None or np.max(mat) > api_dur_ms * 20):
                    mat = mat / 256.0

                # Fix 2: Unterscheidung zwischen kontinuierlichem Timer (sweep) und Reset pro Punkt (point_list)
                if exec_mode_clean == "point_list":
                    # Bei point_list startet der HW-Timer bei jedem Punkt neu -> reale Gesamtzeit nutzen
                    if api_dur_ms is not None and api_dur_ms > 0:
                        hw_total_ms = float(api_dur_ms)
                    elif len(py_timestamps) > 1:
                        span_s = max(py_timestamps) - min(py_timestamps)
                        hw_total_ms = span_s * 1000.0 * (n_pts / max(1, n_pts - 1))
                    else:
                        # Fallback: Summe der Einzelpunkt-Dauern
                        hw_total_ms = float(np.sum(mat[:, -1]))
                    if hw_total_ms:
                        hw_sweep_ms_list = [hw_total_ms / max(1, min_len)] * min_len
                else:
                    # Beim echten Hardware-Sweep (0x03) läuft der Timer kontinuierlich durch
                    for s_idx in range(min_len):
                        col = mat[:, s_idx]
                        span = float(np.max(col) - np.min(col))
                        est_sweep = span * (n_pts / max(1, n_pts - 1))
                        hw_sweep_ms_list.append(est_sweep)
                    total_span = float(np.max(mat) - np.min(mat))
                    total_pts = n_pts * min_len
                    hw_total_ms = total_span * (total_pts / max(1, total_pts - 1))

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
            "execution_mode": str(exec_mode).strip().lower(),
            "component_est": _estimate_component(f_arr, z_arr, ph_arr, im_arr),
        }

    return results, sorted(list(set(block_transitions))), meta_info


def _parse_sciospec_gui_hdf5(h5: h5py.File) -> tuple[dict[str, dict], list[float], dict]:
    """Parses the native Sciospec software HDF5 format (.scio5 / .h5) including standard deviation and timestamps."""
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
                "execution_mode": "sciospec_gui",
                "component_est": _estimate_component(f_arr, z_arr, ph_arr, im_arr),
            }

    return results, sorted(list(set(block_transitions))), meta_info


def parse_any_measurement_selection(
    file_paths: list[str] | str,
    target_sensor_count: int | None = None,
) -> tuple[dict[str, dict], list[float], str, dict, str]:
    """
    Universal dispatcher: accepts either a single HDF5 path (.h5/.scio5) or a list of
    one/multiple .spec paths and returns (data_dict, transitions, file_type, meta_info, display_name).
    """
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    if not file_paths:
        return {}, [], "UNKNOWN", {}, "Keine Datei"

    first_ext = os.path.splitext(file_paths[0])[1].lower()
    if first_ext == ".spec" or any(p.lower().endswith(".spec") for p in file_paths):
        spec_list = [p for p in file_paths if p.lower().endswith(".spec")]
        data, trans, f_type, meta = parse_sciospec_spec_files(spec_list, target_sensor_count=target_sensor_count)
        if len(spec_list) == 1:
            disp_name = os.path.basename(spec_list[0])
        else:
            disp_name = f"{len(spec_list)}x .spec ({os.path.basename(spec_list[0])} .. {os.path.basename(spec_list[-1])})"
        return data, trans, f_type, meta, disp_name

    # HDF5 file (.h5 / .hdf5 / .scio5)
    h5_file = file_paths[0]
    disp_name = os.path.basename(h5_file)
    with h5py.File(h5_file, "r") as h5:
        keys = list(h5.keys())
        is_api = any(
            k.startswith("Sensor_") or k.startswith("Measurement") or k == "Configuration"
            for k in keys
        )

        if is_api:
            data, trans, meta = _parse_api_hdf5(h5)
            return data, trans, "API", meta, disp_name
        else:
            data, trans, meta = _parse_sciospec_gui_hdf5(h5)
            if data:
                return data, trans, "SCIOSPEC_GUI", meta, disp_name
            data, trans, meta = _parse_api_hdf5(h5)
            return data, trans, "API", meta, disp_name


def print_diagnostic_report(data_dict: dict, meta_info: dict, file_name: str) -> None:
    """Prints the configuration summary, timing analysis, autoranging details, and component estimation."""
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

        f_mode = str(fsetup.get("mode", "sweep")).strip().lower()
        f_mode_lbl = {
            "sweep": "Hardware-Block-Sweep (0xB6 Sub 0x03)",
            "point_list": "Python-Einzelpunkt-Liste (0xB6 Sub 0x02 pro Punkt)",
            "single": f"Diskrete Einzelmessung ({fsetup.get('frequency_hz', '1000.0')} Hz)",
        }.get(f_mode, f_mode)

        print(" [KONFIGURATIONS-STECKBRIEF (API HDF5)]")
        print(f"  • Geräte-Modell   : {dev_ver} (Port: {port})")
        print(f"  • Betriebsart     : {'MUX (Aktive Sensoren/Pins: ' + str(mux.get('active_sensors', '-')) + ')' if mux_en == 'True' else 'Main Port (Front-BNC)'}")
        print(f"  • Frequenz-Modus  : {f_mode_lbl}")
        print(f"  • Anregung & Range: {exc} | Amplitude = {amp} | Current Range = {cr_text}")
        print(f"  • Timing-Optionen : Spectra = {meas.get('number_of_spectra', '1')} | Point Delay = {fsetup.get('point_delay_ms', '-')} ms")
        print("-" * 80)
    elif meta_info.get("type") == "SCIOSPEC_SPEC":
        print(" [KONFIGURATIONS-STECKBRIEF (SCIOSPEC .SPEC EXPORT)]")
        print(f"  • Geladene .spec  : {meta_info.get('file_count', 1)} Datei(en)")
        print(f"  • Kanal / Port    : {', '.join(meta_info.get('channels', ['-']))} | DC-Offset: {meta_info.get('offset', '0.0V')}")
        if meta_info.get("warnings"):
            print(f"  • HARDWARE-WARNUNG: {', '.join(meta_info['warnings'])} (Bitte Messbereich / Kabel prüfen!)")
        print("-" * 80)

    print(" [TIMING-ANALYSE PRO SENSOR, WIEDERHOLGENAUIGKEIT & BAUTEIL-SCHÄTZUNG]")
    for label, d in data_dict.items():
        n_pts = len(d["frequency"])
        n_spec = d["spectra_count"]
        api_ms = d["api_duration_ms"]
        sw_ms = d["single_sweep_ms"]

        print(f"\n  >>> {label} ({n_pts} Frequenzpunkte × {n_spec} Wiederholung(en)) <<<")
        print(f"      • Bauteil-Schätzung : {d['component_est']}")
        if d.get("warnings"):
            print(f"      • Warnung im Header : {', '.join(d['warnings'])}")

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


def _extract_sensor_pin_mapping(meta_info: dict) -> dict[int, str]:
    """
    Parses the MUX 'active_sensors' string (e.g. '1: 1,1,2,2; 2: 5,5,6,6; 3: 9,9,10,10')
    into a sensor-specific dictionary {1: '1: 1,1,2,2', 2: '2: 5,5,6,6', ...}.
    """
    pin_map: dict[int, str] = {}
    if meta_info.get("type") == "API" and "MUX" in meta_info.get("sections", {}):
        mux_sec = meta_info["sections"]["MUX"]
        if str(mux_sec.get("enabled", "False")) == "True":
            raw_sens = str(mux_sec.get("active_sensors", "")).strip()
            if raw_sens:
                parts = [p.strip() for p in re.split(r"[;|]", raw_sens) if p.strip()]
                for idx, p in enumerate(parts, start=1):
                    m = re.match(r"^(\d+)\s*:\s*(.+)$", p)
                    if m:
                        pin_map[int(m.group(1))] = f"Pins {m.group(2).strip()}"
                    else:
                        pin_map[idx] = p
    return pin_map


def _apply_style_preset(axis_opts: dict) -> tuple[float, float, float]:
    """
    Applies matplotlib font/tick scaling for Normal vs. Presentation mode
    and returns (line_width, marker_size, legend_fontsize).
    """
    lw = float(axis_opts.get("line_width", 1.8))
    ms = float(axis_opts.get("marker_size", 5.0))
    is_pres = axis_opts.get("style_preset", "normal") == "presentation"

    if is_pres:
        plt.rcParams.update({
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "axes.labelsize": 13,
            "axes.labelweight": "bold",
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "axes.linewidth": 1.3,
        })
        leg_fs = 10.0
    else:
        plt.rcParams.update({
            "axes.titlesize": 12,
            "axes.titleweight": "normal",
            "axes.labelsize": 10.5,
            "axes.labelweight": "normal",
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "axes.linewidth": 0.9,
        })
        leg_fs = 8.5

    return lw, ms, leg_fs


def _ask_plot_and_axis_options(has_multi_sensors: bool = False) -> dict:
    """Prompts the user for diagram type, style preset (normal vs. presentation), MUX sensor grouping, and axis scaling."""
    print("\n--- DIAGRAMM- & DARSTELLUNGS-OPTIONEN ---")
    print("  Welchen Diagramm-Typ möchtest du anzeigen?")
    print("    [1] Bode-Diagramm (|Z| und Phase φ über Frequenz) [Standard]")
    print("    [2] Kombi-Dashboard (Bode-Diagramm links + Nyquist-Ortskurve rechts)")
    print("    [3] Nyquist-Diagramm (Ortskurve: Im{Z} über Re{Z})")
    print("    [4] Real- und Imaginärteil über der Frequenz")
    pt_choice = input("  Deine Wahl (1-4) [Standard: 1]: ").strip()
    plot_mode_map = {"1": "bode", "2": "dashboard", "3": "nyquist", "4": "re_im"}
    plot_mode = plot_mode_map.get(pt_choice, "bode")

    print("\n  Darstellungs-Stil & Linienstärke (Empfehlung):")
    print("    [1] Standard / Labor-Analyse   (Linie: 1.8 pt, Marker: 4.5 pt -> feine Detailanalyse am Monitor) [Standard]")
    print("    [2] Präsentation / Beamer-Folie (Linie: 3.0 pt, Marker: 7.0 pt, größere Achsenschrift -> optimal für Folien)")
    print("    [3] Benutzerdefiniert          (Linienstärke und Markergröße frei eingeben)")
    style_choice = input("  Deine Wahl (1, 2 oder 3) [Standard: 1]: ").strip()

    if style_choice == "2":
        style_preset = "presentation"
        line_width = 3.0
        marker_size = 7.0
    elif style_choice == "3":
        style_preset = "presentation"
        lw_in = input("    Linienstärke in pt (Empfehlung: 1.8 normal, 3.0 Folie) [Standard: 3.0]: ").strip()
        ms_in = input("    Markergröße in pt  (Empfehlung: 4.5 normal, 7.0 Folie) [Standard: 7.0]: ").strip()
        try:
            line_width = float(lw_in) if lw_in else 3.0
            marker_size = float(ms_in) if ms_in else 7.0
        except ValueError:
            line_width, marker_size = 3.0, 7.0
    else:
        style_preset = "normal"
        line_width = 1.8
        marker_size = 4.5

    mux_compare_mode = "per_sensor_subplots"
    if has_multi_sensors:
        print("\n  MUX-Sensoren Vergleichs-Aufteilung (Mehrere Sensoren erkannt):")
        print("    [1] Pro Sensor ein eigener Teilplot untereinander in 1 Fenster (Sensor #1 vs. #1, #2 vs. #2...) [Empfohlen]")
        print("    [2] Pro Sensor ein eigenes separates Plot-Fenster öffnen")
        print("    [3] Alle Kurven aller Sensoren in einem einzigen Diagramm übereinanderlegen")
        mux_in = input("  Deine Wahl (1, 2 oder 3) [Standard: 1]: ").strip()
        mux_map = {
            "1": "per_sensor_subplots",
            "2": "per_sensor_windows",
            "3": "all_in_one",
        }
        mux_compare_mode = mux_map.get(mux_in, "per_sensor_subplots")

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
        "style_preset": style_preset,
        "line_width": line_width,
        "marker_size": marker_size,
        "mux_compare_mode": mux_compare_mode,
        "x_scale": x_scale,
        "y_scale": y_scale,
        "show_std": show_std,
        "f_lim": f_lim,
        "z_lim": z_lim,
        "p_lim": p_lim,
    }


def _apply_axis_limits(ax_z, ax_p, axis_opts: dict) -> None:
    """Applies logarithmic/linear scaling and optional user-defined axis bounds."""
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


def _draw_bode_on_axes(
    ax_z,
    ax_p,
    data_dict: dict,
    transitions: list[float],
    axis_opts: dict,
    colors: list[str],
    prefix: str = "",
    line_style: str = "o-",
) -> None:
    """Helper function to draw Bode curves including ±1 sigma error bands, execution mode, and sweep duration."""
    lw, ms, _ = _apply_style_preset(axis_opts)

    for ch_idx, (label, data) in enumerate(data_dict.items()):
        freqs = data["frequency"]
        z_mag = data["z_mag"]
        z_std = data["z_std"]
        phase = data["phase"]
        ph_std = data["phase_std"]
        cr_arr = data["current_range"]

        exec_m = data.get("execution_mode", "")
        mode_tag = ""
        if exec_m == "point_list":
            mode_tag = " [Py-List 0x02]"
        elif exec_m == "sweep":
            mode_tag = " [HW-Sweep 0x03]"
        elif exec_m == "single":
            mode_tag = " [Single 0x02]"

        time_tag = ""
        if data.get("single_sweep_ms") is not None:
            sw_s = data["single_sweep_ms"] / 1000.0
            time_tag = f" [1 Sweep: {sw_s:.2f} s]" if sw_s >= 1.0 else f" [1 Sweep: {data['single_sweep_ms']:.0f} ms]"

        full_label_base = f"{prefix}{label}{mode_tag}{time_tag}"

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

            ax_z.plot(f_seg, z_seg, line_style, color=col, linewidth=lw, markersize=ms, label=lbl)
            ax_p.plot(f_seg, p_seg, line_style, color=col, linewidth=lw, markersize=ms, label=lbl)

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
                    ax_z.axvline(f_sw, color="#cc00cc", linestyle="--", linewidth=max(1.2, lw * 0.65), alpha=0.6)
                    ax_p.axvline(f_sw, color="#cc00cc", linestyle="--", linewidth=max(1.2, lw * 0.65), alpha=0.6, label=f"CR-Switch @ {f_sw:g} Hz")


def plot_single_file(data_dict: dict, transitions: list[float], file_name: str, file_type: str, axis_opts: dict) -> None:
    """Plots a single dataset (from .h5, .scio5, or one/multiple .spec files) in the selected mode."""
    if not data_dict:
        print("[FEHLER] Keine gültigen Messdaten gefunden.")
        return

    lw, ms, leg_fs = _apply_style_preset(axis_opts)
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
            ax_z.axvline(t, color="red", linestyle=":", linewidth=max(1.2, lw * 0.6), alpha=0.7)
            ax_p.axvline(t, color="red", linestyle=":", linewidth=max(1.2, lw * 0.6), alpha=0.7)
        _apply_axis_limits(ax_z, ax_p, axis_opts)

        ax_z.set_ylabel(r"Betrag $|Z|$ / $\Omega$")
        ax_z.set_title(f"Bode-Diagramm [{file_type}]: {file_name}")
        ax_z.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_z.legend(loc="best", fontsize=leg_fs)

        ax_p.set_xlabel("Frequenz $f$ / Hz")
        ax_p.set_ylabel(r"Phase $\phi$ / °")
        ax_p.grid(True, which="both", linestyle="--", alpha=0.5)

        for idx, (label, d) in enumerate(data_dict.items()):
            col = colors[idx % len(colors)]
            ax_nyq.plot(d["real"], d["imag"], "o-", color=col, linewidth=lw, markersize=ms, label=f"{label} ({d['component_est'].split('(')[0].strip()})")
        ax_nyq.axhline(0, color="black", linewidth=0.9, linestyle=":")
        ax_nyq.axvline(0, color="black", linewidth=0.9, linestyle=":")
        ax_nyq.set_xlabel(r"Realteil $Z_{\mathrm{real}}$ / $\Omega$")
        ax_nyq.set_ylabel(r"Imaginärteil $Z_{\mathrm{imag}}$ / $\Omega$")
        ax_nyq.set_title("Nyquist-Ortskurve")
        ax_nyq.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_nyq.legend(loc="best", fontsize=leg_fs)

    elif mode == "nyquist":
        fig, ax_nyq = plt.subplots(figsize=(9, 7))
        for idx, (label, d) in enumerate(data_dict.items()):
            col = colors[idx % len(colors)]
            ax_nyq.plot(d["real"], d["imag"], "o-", color=col, linewidth=lw, markersize=ms, label=label)
        ax_nyq.axhline(0, color="black", linewidth=0.9, linestyle=":")
        ax_nyq.axvline(0, color="black", linewidth=0.9, linestyle=":")
        ax_nyq.set_aspect("equal", adjustable="datalim")
        ax_nyq.set_xlabel(r"Realteil $Z_{\mathrm{real}}$ / $\Omega$")
        ax_nyq.set_ylabel(r"Imaginärteil $Z_{\mathrm{imag}}$ / $\Omega$")
        ax_nyq.set_title(f"Nyquist-Diagramm [{file_type}]: {file_name}")
        ax_nyq.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_nyq.legend(loc="best", fontsize=leg_fs)

    elif mode == "re_im":
        fig, (ax_re, ax_im) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        for idx, (label, d) in enumerate(data_dict.items()):
            col = colors[idx % len(colors)]
            ax_re.plot(d["frequency"], d["real"], "o-", color=col, linewidth=lw, markersize=ms, label=f"{label} (Real)")
            ax_im.plot(d["frequency"], d["imag"], "s--", color=col, linewidth=lw, markersize=ms, label=f"{label} (Imag)")
        ax_re.set_xscale("log")
        ax_im.set_xscale("log")
        ax_re.set_ylabel(r"$Z_{\mathrm{real}}$ / $\Omega$")
        ax_im.set_ylabel(r"$Z_{\mathrm{imag}}$ / $\Omega$")
        ax_im.set_xlabel("Frequenz $f$ / Hz")
        ax_re.set_title(f"Real- und Imaginärteil [{file_type}]: {file_name}")
        ax_re.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_im.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_re.legend(loc="best", fontsize=leg_fs)
        ax_im.legend(loc="best", fontsize=leg_fs)

    else:
        fig, (ax_z, ax_p) = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
        _draw_bode_on_axes(ax_z, ax_p, data_dict, transitions, axis_opts, colors)
        for t in transitions[:-1]:
            ax_z.axvline(t, color="red", linestyle=":", linewidth=max(1.2, lw * 0.6), alpha=0.7)
            ax_p.axvline(t, color="red", linestyle=":", linewidth=max(1.2, lw * 0.6), alpha=0.7, label=f"Block-Grenze ({t:g} Hz)")

        _apply_axis_limits(ax_z, ax_p, axis_opts)
        scale_info = "Linear |Z|" if axis_opts["y_scale"] == "linear" else "Log |Z|"
        ax_z.set_ylabel(r"Betrag $|Z|$ / $\Omega$")
        ax_z.set_title(f"Messdaten-Auswertung [{file_type}]: {file_name} ({scale_info})")
        ax_z.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_z.legend(loc="best", fontsize=leg_fs)

        ax_p.set_xlabel("Frequenz $f$ / Hz")
        ax_p.set_ylabel(r"Phase $\phi$ / °")
        ax_p.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_p.legend(loc="best", fontsize=leg_fs)

    plt.tight_layout()
    plt.show()


def plot_comparison(
    data_1: dict,
    name_1: str,
    data_2: dict,
    name_2: str,
    transitions: list[float],
    axis_opts: dict,
    meta_1: dict | None = None,
    meta_2: dict | None = None,
) -> None:
    """
    Overlays two datasets (e.g., Hardware-Sweep vs. Python-Point-List or API .h5 vs. Sciospec .spec)
    and prints a sensor-by-sensor deviation and timing speedup report.
    If multiple sensors are present and sensor-wise plotting is selected, delegates to plot_multi_file_comparison.
    """
    if not data_1 or not data_2:
        print("[FEHLER] Mindestens eine der beiden Messreihen enthält keine gültigen Messdaten.")
        return

    items_1 = list(data_1.items())
    items_2 = list(data_2.items())
    pair_count = min(len(items_1), len(items_2))

    print("\n" + "=" * 80)
    print(f" DIREKTER VERGLEICHS-REPORT ({pair_count} SENSOR-PAARE): {name_1}  vs.  {name_2}")
    print("=" * 80)

    for p_idx in range(pair_count):
        lbl_1, d1 = items_1[p_idx]
        lbl_2, d2 = items_2[p_idx]
        m1_str = d1.get("execution_mode", "-")
        m2_str = d2.get("execution_mode", "-")
        print(f"  >>> Paar #{p_idx + 1}: {lbl_1} [{m1_str}]  <-->  {lbl_2} [{m2_str}] <<<")
        if len(d1["z_mag"]) == len(d2["z_mag"]):
            rel_err_z = np.abs(d1["z_mag"] - d2["z_mag"]) / np.maximum(d2["z_mag"], 1e-12) * 100.0
            abs_err_p = np.abs(d1["phase"] - d2["phase"])
            print(f"      • Mittlere Abweichung |Z| : {np.mean(rel_err_z):.3f} % (Max: {np.max(rel_err_z):.3f} %)")
            print(f"      • Mittlere Abweichung φ   : {np.mean(abs_err_p):.3f} ° (Max: {np.max(abs_err_p):.3f} °)")
        else:
            print(f"      • Hinweis: Unterschiedliche Punktanzahl ({len(d1['z_mag'])} vs. {len(d2['z_mag'])} Punkte).")

        t1_sw = d1.get("single_sweep_ms")
        t2_sw = d2.get("single_sweep_ms")
        if t1_sw is not None or t2_sw is not None:
            s1 = f"{t1_sw:.1f} ms ({t1_sw / 1000.0:.2f} s)" if t1_sw is not None else "n/a"
            s2 = f"{t2_sw:.1f} ms ({t2_sw / 1000.0:.2f} s)" if t2_sw is not None else "n/a"
            print(f"      • Dauer für 1 Sweep       : Messung 1 = {s1}  |  Messung 2 = {s2}")
            if t1_sw and t2_sw and t1_sw > 0 and t2_sw > 0:
                faster_factor = max(t1_sw, t2_sw) / min(t1_sw, t2_sw)
                diff_ms = abs(t1_sw - t2_sw)
                print(f"      • Zeitunterschied         : Δt = {diff_ms:.1f} ms (Faktor {faster_factor:.2f}x schneller)")

    print("=" * 80)

    # If multiple MUX sensors exist and user chose per-sensor view, use the sensor-grouped comparison
    if pair_count > 1 and axis_opts.get("mux_compare_mode", "per_sensor_subplots") != "all_in_one":
        datasets = [
            (name_1, data_1, meta_1 or {}, transitions),
            (name_2, data_2, meta_2 or {}, transitions),
        ]
        plot_multi_file_comparison(datasets=datasets, axis_opts=axis_opts)
        return

    lw, ms, leg_fs = _apply_style_preset(axis_opts)
    mode = axis_opts.get("plot_mode", "bode")
    colors_1 = ["#0055cc", "#0088ff", "#003380", "#1b8a5a", "#008080"]
    colors_2 = ["#e63900", "#ff8000", "#992600", "#cc00cc", "#8c564b"]

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
        ax_z.legend(loc="best", fontsize=leg_fs)
        ax_p.set_xlabel("Frequenz $f$ / Hz")
        ax_p.set_ylabel(r"Phase $\phi$ / °")
        ax_p.grid(True, which="both", linestyle="--", alpha=0.5)

        for idx, (l1, d1) in enumerate(data_1.items()):
            ax_nyq.plot(d1["real"], d1["imag"], "o-", color=colors_1[idx % len(colors_1)], linewidth=lw, markersize=ms, label=f"{name_1} | {l1}")
        for idx, (l2, d2) in enumerate(data_2.items()):
            ax_nyq.plot(d2["real"], d2["imag"], "s--", color=colors_2[idx % len(colors_2)], linewidth=lw, markersize=ms, label=f"{name_2} | {l2}")
        ax_nyq.set_xlabel(r"Realteil $Z_{\mathrm{real}}$ / $\Omega$")
        ax_nyq.set_ylabel(r"Imaginärteil $Z_{\mathrm{imag}}$ / $\Omega$")
        ax_nyq.set_title("Nyquist-Vergleich")
        ax_nyq.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_nyq.legend(loc="best", fontsize=leg_fs)
    else:
        fig, (ax_z, ax_p) = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
        _draw_bode_on_axes(ax_z, ax_p, data_1, transitions, axis_opts, colors_1, prefix=f"{name_1} | ", line_style="o-")
        _draw_bode_on_axes(ax_z, ax_p, data_2, transitions, axis_opts, colors_2, prefix=f"{name_2} | ", line_style="s--")

        for t in transitions[:-1]:
            ax_z.axvline(t, color="gray", linestyle=":", linewidth=max(1.2, lw * 0.6), alpha=0.7)
            ax_p.axvline(t, color="gray", linestyle=":", linewidth=max(1.2, lw * 0.6), alpha=0.7)

        _apply_axis_limits(ax_z, ax_p, axis_opts)
        scale_info = "Linear |Z|" if axis_opts["y_scale"] == "linear" else "Log |Z|"
        ax_z.set_ylabel(r"Betrag $|Z|$ / $\Omega$")
        ax_z.set_title(f"Direkter Messvergleich ({scale_info}): {name_1} vs. {name_2}")
        ax_z.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_z.legend(loc="best", fontsize=leg_fs)

        ax_p.set_xlabel("Frequenz $f$ / Hz")
        ax_p.set_ylabel(r"Phase $\phi$ / °")
        ax_p.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_p.legend(loc="best", fontsize=leg_fs)

    plt.tight_layout()
    plt.show()


def plot_multi_file_comparison(
    datasets: list[tuple[str, dict, dict, list[float]]],
    axis_opts: dict,
) -> None:
    """
    Overlays an arbitrary number of measurement datasets (.h5, .scio5, or .spec).
    Supports sensor-by-sensor grouping (Subplots per sensor or separate windows per sensor)
    when MUX files with multiple sensors are compared!
    """
    if not datasets:
        print("[FEHLER] Keine gültigen Datensätze zum Vergleichen vorhanden.")
        return

    lw, ms, leg_fs = _apply_style_preset(axis_opts)

    palette = [
        "#0055cc",  # Blue (Messreihe 1)
        "#e66000",  # Orange (Messreihe 2)
        "#1b8a5a",  # Green (Messreihe 3)
        "#cc00cc",  # Magenta (Messreihe 4)
        "#8c564b",  # Brown (Messreihe 5)
        "#008080",  # Teal (Messreihe 6)
    ]
    markers = ["o-", "s--", "^-.", "d:", "v-", "P--"]

    max_sensors = max(len(d_dict) for _, d_dict, _, _ in datasets)
    mux_mode = axis_opts.get("mux_compare_mode", "per_sensor_subplots")

    # =========================================================================
    # FALL A: SENSORWEISER VERGLEICH (Pro Sensor #1..#N werden die Dateien verglichen)
    # =========================================================================
    if max_sensors > 1 and mux_mode in ("per_sensor_subplots", "per_sensor_windows"):
        print("\n" + "=" * 95)
        print(f" SENSORWEISER VERGLEICHS-REPORT ({max_sensors} SENSOREN ÜBER {len(datasets)} DATEIEN)")
        print("=" * 95)

        all_transitions = []
        for _, _, _, trans in datasets:
            all_transitions.extend(trans)
        unique_trans = sorted(list(set(all_transitions)))
        scale_info = "Linear |Z|" if axis_opts["y_scale"] == "linear" else "Log |Z|"

        if mux_mode == "per_sensor_subplots":
            # Ein großes Übersichts-Fenster: Zeile s = Sensor #s (Links: |Z|, Rechts: Phase φ)
            fig, axes = plt.subplots(
                max_sensors,
                2,
                figsize=(16, max(7.5, 3.6 * max_sensors)),
                sharex=True,
                squeeze=False,
            )
            fig.suptitle(
                f"Sensorweiser MUX-Vergleich ({len(datasets)} Messreihen × {max_sensors} Sensoren, {scale_info})",
                fontsize=14 if axis_opts.get("style_preset") == "presentation" else 12,
                fontweight="bold",
            )

        for s_idx in range(max_sensors):
            s_num = s_idx + 1
            print(f"\n  >>> SENSOR #{s_num} VERGLEICH <<<")
            print(f"  {'Datei-Nr. & Name':<44} | {'Kanal / Pins':<24} | {'|Z| @ 1 kHz':<13} | {'|Z| @ 1 MHz':<13}")
            print("  " + "-" * 91)

            if mux_mode == "per_sensor_windows":
                fig, (ax_z, ax_p) = plt.subplots(2, 1, figsize=(12, 8.5), sharex=True)
            else:
                ax_z = axes[s_idx, 0]
                ax_p = axes[s_idx, 1]

            ref_z = None
            ref_p = None
            ref_name = None

            for f_idx, (file_name, data_dict, meta_info, _) in enumerate(datasets):
                items = list(data_dict.items())
                if s_idx >= len(items):
                    continue

                ch_label, d = items[s_idx]
                pin_map = _extract_sensor_pin_mapping(meta_info)
                pin_str = pin_map.get(s_num, "")
                pin_tag = f" [{pin_str}]" if pin_str else ""

                col = palette[f_idx % len(palette)]
                style = markers[f_idx % len(markers)]

                freqs = d["frequency"]
                z_mag = d["z_mag"]
                z_std = d["z_std"]
                phase = d["phase"]
                ph_std = d["phase_std"]

                idx_1k = int(np.argmin(np.abs(freqs - 1000.0)))
                idx_1m = int(np.argmin(np.abs(freqs - 1000000.0)))
                z_1k = z_mag[idx_1k] if len(z_mag) > 0 else 0.0
                z_1m = z_mag[idx_1m] if len(z_mag) > 0 else 0.0

                ch_short = f"{ch_label}{pin_tag}".strip()
                print(f"  #{f_idx + 1}: {file_name[:39]:<39} | {ch_short[:24]:<24} | {z_1k:>9.1f} Ω | {z_1m:>9.1f} Ω")

                if ref_z is None:
                    ref_z = z_mag
                    ref_p = phase
                    ref_name = file_name
                elif len(z_mag) == len(ref_z):
                    rel_err_z = float(np.mean(np.abs(z_mag - ref_z) / np.maximum(ref_z, 1e-12)) * 100.0)
                    abs_err_p = float(np.mean(np.abs(phase - ref_p)))
                    print(f"      ↳ Mittlere Abweichung zu #{1} ({ref_name[:22]}..): Δ|Z| = {rel_err_z:.2f} %, Δφ = {abs_err_p:.2f}°")

                sw_tag = f", {d['single_sweep_ms']/1000.0:.2f}s" if d.get("single_sweep_ms") else ""
                legend_lbl = f"#{f_idx + 1}: {file_name} - {ch_label}{pin_tag} (|Z|_1k={z_1k:.0f} Ω{sw_tag})"

                ax_z.plot(freqs, z_mag, style, color=col, linewidth=lw, markersize=ms, label=legend_lbl)
                ax_p.plot(freqs, phase, style, color=col, linewidth=lw, markersize=ms, label=legend_lbl)

                if axis_opts.get("show_std", True) and d.get("spectra_count", 1) > 1:
                    z_low = np.maximum(z_mag - z_std, 1e-12) if axis_opts["y_scale"] == "log" else (z_mag - z_std)
                    ax_z.fill_between(freqs, z_low, z_mag + z_std, color=col, alpha=0.15)
                    ax_p.fill_between(freqs, phase - ph_std, phase + ph_std, color=col, alpha=0.15)

            for t in unique_trans[:-1]:
                ax_z.axvline(t, color="gray", linestyle=":", linewidth=max(1.1, lw * 0.55), alpha=0.7)
                ax_p.axvline(t, color="gray", linestyle=":", linewidth=max(1.1, lw * 0.55), alpha=0.7)

            _apply_axis_limits(ax_z, ax_p, axis_opts)

            ax_z.set_ylabel(f"Sensor #{s_num}\n$|Z|$ / $\Omega$")
            ax_p.set_ylabel(f"Sensor #{s_num}\nPhase $\phi$ / °")
            ax_z.grid(True, which="both", linestyle="--", alpha=0.5)
            ax_p.grid(True, which="both", linestyle="--", alpha=0.5)
            ax_z.legend(loc="best", fontsize=leg_fs)

            if mux_mode == "per_sensor_subplots":
                if s_idx == 0:
                    ax_z.set_title(f"Impedanzbetrag $|Z|$ ({scale_info})")
                    ax_p.set_title("Phasenwinkel $\phi$")
                if s_idx == max_sensors - 1:
                    ax_z.set_xlabel("Frequenz $f$ / Hz")
                    ax_p.set_xlabel("Frequenz $f$ / Hz")
                ax_p.legend(loc="best", fontsize=leg_fs)
            else:
                ax_z.set_title(f"Sensor #{s_num} Vergleich ({len(datasets)} Messreihen, {scale_info})")
                ax_p.set_xlabel("Frequenz $f$ / Hz")
                ax_p.legend(loc="best", fontsize=leg_fs)
                plt.tight_layout()

        print("=" * 95)
        plt.tight_layout()
        plt.show()
        return

    # =========================================================================
    # FALL B: ALLE KURVEN IN EINEM EINZIGEN PLOT (Standard bei 1 Sensor / Main Port)
    # =========================================================================
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

    curve_counter = 0
    for idx, (file_name, data_dict, meta_info, trans) in enumerate(datasets):
        all_transitions.extend(trans)
        pin_map = _extract_sensor_pin_mapping(meta_info)

        for s_idx, (ch_label, d) in enumerate(data_dict.items(), start=1):
            col = palette[curve_counter % len(palette)]
            style = markers[curve_counter % len(markers)]
            curve_counter += 1

            pin_str = pin_map.get(s_idx, "")
            pin_info = f" [{pin_str}]" if pin_str else ""

            freqs = d["frequency"]
            z_mag = d["z_mag"]
            z_std = d["z_std"]
            phase = d["phase"]
            ph_std = d["phase_std"]

            idx_1k = int(np.argmin(np.abs(freqs - 1000.0)))
            idx_1m = int(np.argmin(np.abs(freqs - 1000000.0)))
            z_1k = z_mag[idx_1k] if len(z_mag) > 0 else 0.0
            z_1m = z_mag[idx_1m] if len(z_mag) > 0 else 0.0

            short_pin = (pin_info[:38] + "..]") if len(pin_info) > 41 else pin_info
            table_label = f"{ch_label} {short_pin.strip(' []')}".strip()
            print(f" #{curve_counter:<3} | {table_label[:42]:<42} | {z_1k:>10.2f} Ohm | {z_1m:>10.2f} Ohm")

            sw_tag = f", {d['single_sweep_ms']/1000.0:.2f}s" if d.get("single_sweep_ms") else ""
            legend_lbl = f"#{curve_counter}: {file_name} - {ch_label}{pin_info} (|Z|_1k={z_1k:.0f} Ω{sw_tag})"

            ax_z.plot(freqs, z_mag, style, color=col, linewidth=lw, markersize=ms, label=legend_lbl)
            ax_p.plot(freqs, phase, style, color=col, linewidth=lw, markersize=ms, label=legend_lbl)

            if axis_opts.get("show_std", True) and d.get("spectra_count", 1) > 1:
                z_low = np.maximum(z_mag - z_std, 1e-12) if axis_opts["y_scale"] == "log" else (z_mag - z_std)
                ax_z.fill_between(freqs, z_low, z_mag + z_std, color=col, alpha=0.15)
                ax_p.fill_between(freqs, phase - ph_std, phase + ph_std, color=col, alpha=0.15)

            if ax_nyq is not None:
                ax_nyq.plot(d["real"], d["imag"], style, color=col, linewidth=lw, markersize=ms, label=legend_lbl)

    print("=" * 85)

    unique_trans = sorted(list(set(all_transitions)))
    for t in unique_trans[:-1]:
        ax_z.axvline(t, color="gray", linestyle=":", linewidth=max(1.2, lw * 0.6), alpha=0.7)
        ax_p.axvline(t, color="gray", linestyle=":", linewidth=max(1.2, lw * 0.6), alpha=0.7)

    _apply_axis_limits(ax_z, ax_p, axis_opts)
    scale_info = "Linear |Z|" if axis_opts["y_scale"] == "linear" else "Log |Z|"

    ax_z.set_ylabel(r"Betrag $|Z|$ / $\Omega$")
    ax_z.set_title(f"Mehrdateien-Vergleich ({len(datasets)} Messreihen, {scale_info})")
    ax_z.grid(True, which="both", linestyle="--", alpha=0.5)
    ax_z.legend(loc="best", fontsize=leg_fs)

    ax_p.set_xlabel("Frequenz $f$ / Hz")
    ax_p.set_ylabel(r"Phase $\phi$ / °")
    ax_p.grid(True, which="both", linestyle="--", alpha=0.5)
    ax_p.legend(loc="best", fontsize=leg_fs)

    if ax_nyq is not None:
        ax_nyq.axhline(0, color="black", linewidth=0.9, linestyle=":")
        ax_nyq.axvline(0, color="black", linewidth=0.9, linestyle=":")
        ax_nyq.set_xlabel(r"Realteil $Z_{\mathrm{real}}$ / $\Omega$")
        ax_nyq.set_ylabel(r"Imaginärteil $Z_{\mathrm{imag}}$ / $\Omega$")
        ax_nyq.set_title("Nyquist-Vergleich")
        ax_nyq.grid(True, which="both", linestyle="--", alpha=0.5)
        ax_nyq.legend(loc="best", fontsize=leg_fs)

    plt.tight_layout()
    plt.show()


def main():
    """Interactive CLI menu for evaluating and comparing HDF5 (.h5 / .scio5) and .spec measurement files."""
    print("\n" + "=" * 80)
    print(" MESSDATEN-AUSWERTUNG, TIMING-ANALYSE & VERGLEICH (.h5 / .scio5 / .spec)")
    print("=" * 80)
    print("Was möchtest du tun?")
    print("  [1] EINE Messung auswerten & plotten (1x .h5/.scio5 ODER 1..N zusammengehörige .spec Dateien) [Standard]")
    print("  [2] ZWEI Messungen direkt vergleichen (z.B. Hardware-Sweep vs. Python-Liste ODER API .h5 vs. .spec)")
    print("  [3] MEHRERE Messreihen (z.B. 3 verschiedene Versuche) vergleichen (inkl. MUX-Sensor-Gruppierung)")
    mode_choice = input("\nDeine Wahl (1, 2 oder 3) [Standard: 1]: ").strip()

    if mode_choice == "3":
        count_in = input("\nWie viele Messreihen möchtest du vergleichen? [Standard: 3]: ").strip()
        num_series = int(count_in) if count_in.isdigit() and int(count_in) >= 2 else 3

        datasets = []
        target_sensors = None
        for i in range(1, num_series + 1):
            print(f"\n-> Bitte wähle Datei(en) für Messreihe #{i} von {num_series} aus (Mehrfachauswahl für .spec möglich)...")
            paths = select_measurement_files(
                title=f"Messreihe #{i} von {num_series} wählen (.h5, .scio5 oder mehrere .spec)",
                allow_multiple=True,
            )
            if not paths:
                print(f"[INFO] Auswahl bei Messreihe #{i} abgebrochen.")
                break
            d_dict, trans, f_type, meta, disp_name = parse_any_measurement_selection(
                paths, target_sensor_count=target_sensors
            )
            if target_sensors is None and len(d_dict) > 1:
                target_sensors = len(d_dict)
            print_diagnostic_report(d_dict, meta, disp_name)
            datasets.append((disp_name, d_dict, meta, trans))

        if len(datasets) >= 2:
            has_multi = any(len(d_dict) > 1 for _, d_dict, _, _ in datasets)
            axis_opts = _ask_plot_and_axis_options(has_multi_sensors=has_multi)
            plot_multi_file_comparison(datasets=datasets, axis_opts=axis_opts)
        else:
            print("[WARNUNG] Für einen Mehrfach-Vergleich werden mindestens 2 Messreihen benötigt.")

    elif mode_choice == "2":
        print("\n-> Bitte wähle zuerst die 1. Messung aus (z.B. deine API-Messdatei .h5)...")
        paths_1 = select_measurement_files(
            title="1. Messung wählen (z.B. API .h5 Datei)",
            allow_multiple=True,
        )
        if not paths_1:
            print("[INFO] Keine 1. Messung ausgewählt. Abbruch.")
            return

        data_1, trans_1, type_1, meta_1, name_1 = parse_any_measurement_selection(paths_1)
        print_diagnostic_report(data_1, meta_1, name_1)

        print(
            "\n-> Bitte wähle nun die 2. Messung zum Vergleich aus "
            "(Tipp: Bei MUX kannst du alle zugehörigen .spec Dateien gleichzeitig mit Strg/Shift markieren!)..."
        )
        paths_2 = select_measurement_files(
            title="2. Messung zum Vergleich wählen (.scio5, .h5 oder mehrere .spec Dateien)",
            allow_multiple=True,
        )
        if not paths_2:
            print("[INFO] Keine 2. Messung ausgewählt. Abbruch.")
            return

        target_sensors = len(data_1) if len(data_1) > 1 else None
        data_2, trans_2, type_2, meta_2, name_2 = parse_any_measurement_selection(
            paths_2, target_sensor_count=target_sensors
        )
        print_diagnostic_report(data_2, meta_2, name_2)

        has_multi = (len(data_1) > 1) or (len(data_2) > 1)
        axis_opts = _ask_plot_and_axis_options(has_multi_sensors=has_multi)
        all_trans = sorted(list(set(trans_1 + trans_2)))
        plot_comparison(
            data_1=data_1,
            name_1=name_1,
            data_2=data_2,
            name_2=name_2,
            transitions=all_trans,
            axis_opts=axis_opts,
            meta_1=meta_1,
            meta_2=meta_2,
        )
    else:
        print("\n-> Bitte wähle die Messdatei(en) aus (.h5, .scio5 oder eine/mehrere .spec Dateien)...")
        paths = select_measurement_files(
            title="Messdatei(en) wählen (.h5, .scio5 oder mehrere .spec Dateien)",
            allow_multiple=True,
        )
        if not paths:
            print("[INFO] Keine Datei ausgewählt. Abbruch.")
            return

        data_dict, transitions, f_type, meta_info, disp_name = parse_any_measurement_selection(paths)
        print_diagnostic_report(data_dict, meta_info, disp_name)

        axis_opts = _ask_plot_and_axis_options(has_multi_sensors=False)
        plot_single_file(
            data_dict=data_dict,
            transitions=transitions,
            file_name=disp_name,
            file_type=f_type,
            axis_opts=axis_opts,
        )


if __name__ == "__main__":
    main()
