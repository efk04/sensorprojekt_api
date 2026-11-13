"""
commands.py - Driver and low-level communication layer for the Sciospec ISX-3.

Provides binary frame communication with ACK/NACK verification, analog frontend
and frequency sweep setup for both Standard and Medical Research models, a
placeholder for future register-based multi-pin ganging, and the automated
system baseline drift check on the internal 2 kOhm reference path.
"""

import math
import struct
import time
import serial
import serial.tools.list_ports
from typing import Any

# Definition of ISX-3 response and status codes
MSG_DICT = {
    0x01: "Frame-NACK: Ungueltige Syntax",
    0x02: "Kommunikations-Timeout (weniger Daten empfangen als erwartet)",
    0x04: "System-Boot bereit (Wake-Up-Meldung)",
    0x11: "Gueltige TCP-Client-Socket-Verbindung",
    0x81: "NACK: Befehl wurde nicht ausgefuehrt (Syntax- oder Parameterfehler)",
    0x82: "NACK: Befehl wurde nicht erkannt / unbekanntes Tag",
    0x83: "ACK: Befehl erfolgreich ausgefuehrt",
    0x84: "System bereit (System operational and ready)",
    0x90: "Warnung: Ueberstrom erkannt (DC Current Range ueberschritten)",
    0x91: "Warnung: Ueberspannung erkannt (DC Voltage Range ueberschritten)",
    0x92: "Datenstau: Messdaten konnten nicht ueber die Schnittstelle gesendet werden",
}


class ISX3:
    """Encapsulates all control commands and the binary protocol of the Sciospec ISX-3."""

    # Protocol control bytes for device acknowledgments
    ACK_TAG = 0x18
    ACK_SUCCESS = 0x83
    NACK_SYNTAX = 0x81
    NACK_NOT_RECOGNIZED = 0x82

    # Command tags (Command Identifiers)
    CMD_SETUP_FRONTEND = 0xB0
    CMD_GET_FRONTEND = 0xB1
    CMD_SETUP_EXTENSION = 0xB2
    CMD_GET_EXTENSION_PORT = 0xB3
    CMD_GET_EXTENSION_MODULE = 0xB5
    CMD_SETUP_FREQUENCY = 0xB6
    CMD_GET_SETUP = 0xB7
    CMD_MEASURE = 0xB8

    # Feature flag: Keep legacy multi-pin 0xB0 stacking disabled until firmware register update is available
    ENABLE_EXPERIMENTAL_MULTIPIN_STACKING = False

    def __init__(self):
        """Initializes the device interface and internal state variables."""
        self.device = None
        self.serial_protocol = None
        self.print_msg = True
        self.active_mux_pins = None
        self.device_version = "standard"

    def is_port_available(self, port: str) -> bool:
        """Checks whether the specified serial port exists on the operating system."""
        available_ports = [p.device for p in serial.tools.list_ports.comports()]
        return port in available_ports

    def list_available_ports(self) -> list[str]:
        """Returns a list of all detected serial COM ports."""
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect_device_fs(self, settings: dict):
        """
        Opens the serial USB connection to the ISX-3 device.

        Args:
            settings: Dictionary containing 'port', 'baudrate', and 'device_version'.
        """
        port = settings.get("port", "COM12")
        baudrate = int(settings.get("baudrate", 115200))
        self.device_version = str(settings.get("device_version", "standard")).strip().lower()

        if not self.is_port_available(port):
            print(f"[FEHLER] Serieller Port '{port}' ist nicht verfuegbar.")
            return None

        try:
            self.device = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=2.0,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
            )
            self.serial_protocol = "FS"
            self.active_mux_pins = None
            self.device.reset_input_buffer()
            self.device.reset_output_buffer()
            ver_label = "Medical Research ISX-3" if "medical" in self.device_version else "ISX-3 / ISX-3mini (Standard)"
            print(f"[OK] Verbunden mit {self.device.name} ({baudrate} Baud) | Modus: {ver_label}")
            return self.device
        except serial.SerialException as error:
            print(f"[FEHLER] Verbindung fehlgeschlagen: {error}")
            return None

    def _send_command(self, cmd_tag: int, data: bytes, timeout: float = 3.0) -> None:
        """
        Sends a data packet using the Sciospec frame format: [Tag] [Length] [Payload] [Tag]
        and waits for the device acknowledgment (ACK).
        """
        if not self.device or not self.device.is_open:
            raise ConnectionError("Keine aktive serielle Verbindung zum ISX-3 vorhanden.")

        # Discard stale bytes in the input buffer before sending a new command
        if self.device.in_waiting > 0:
            self.device.read(self.device.in_waiting)

        length = len(data)
        if length > 255:
            raise ValueError(f"Payload-Laenge ({length} Bytes) ueberschreitet das Maximum von 255 Bytes.")

        frame = bytes([cmd_tag, length]) + data + bytes([cmd_tag])
        self.device.write(frame)
        self.device.flush()

        self._wait_for_ack(cmd_tag, timeout=timeout)

    def _wait_for_ack(self, original_cmd_tag: int, timeout: float = 3.0) -> None:
        """Reads the device response and verifies that a valid ACK frame was received."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            tag_byte = self.device.read(1)
            if not tag_byte:
                continue

            tag = tag_byte[0]

            # Process acknowledgment frame (0x18)
            if tag == self.ACK_TAG:
                rest = self.device.read(3)
                if len(rest) < 3:
                    raise TimeoutError(f"Unvollstaendiger ACK-Frame fuer Befehl 0x{original_cmd_tag:02X}.")
                if rest[2] != self.ACK_TAG:
                    continue

                status = rest[1]
                if status == self.ACK_SUCCESS:
                    return
                if status in (0x90, 0x91):
                    print(f"[WARNUNG] ISX-3 meldet: {MSG_DICT[status]}")
                    continue
                if status == self.NACK_SYNTAX:
                    raise ValueError(f"NACK (0x81): Ungueltige Syntax/Parameter fuer Befehl 0x{original_cmd_tag:02X}.")
                if status == self.NACK_NOT_RECOGNIZED:
                    raise ValueError(f"NACK (0x82): Befehl 0x{original_cmd_tag:02X} wurde vom ISX-3 nicht erkannt.")

                status_text = MSG_DICT.get(status, f"Unbekannter Status-Code 0x{status:02X}")
                raise ValueError(f"Unerwarteter Status empfangen: {status_text}")

            # Consume asynchronous system messages or trailing measurement frames (0xB8)
            elif tag in (
                0x1D,
                self.CMD_MEASURE,
                self.CMD_GET_EXTENSION_MODULE,
                self.CMD_GET_FRONTEND,
                self.CMD_GET_EXTENSION_PORT,
            ):
                len_b = self.device.read(1)
                if not len_b:
                    continue
                msg_len = len_b[0]
                payload = self.device.read(msg_len)
                self.device.read(1)
                if tag == 0x1D:
                    print(f"[STATUS-INFO] ISX-3 Systemnachricht (0x1D): Payload={payload.hex()}")
                continue

        raise TimeoutError(f"Timeout: Keine Bestaetigung (ACK) fuer Befehl 0x{original_cmd_tag:02X} erhalten.")

    def stop_measurement(self) -> None:
        """
        Sends the explicit stop command (0xB8 0x01 0x00 0xB8) to the ISX-3 to ensure
        the device exits measurement mode, and flushes any remaining measurement frames.
        """
        if not self.device or not self.device.is_open:
            return
        try:
            stop_frame = bytes([self.CMD_MEASURE, 0x01, 0x00, self.CMD_MEASURE])
            self.device.write(stop_frame)
            self.device.flush()
            time.sleep(0.15)
            # Flush any trailing measurement bytes and the stop ACK from the input buffer
            while self.device.in_waiting > 0:
                self.device.read(self.device.in_waiting)
                time.sleep(0.05)
            self.device.reset_input_buffer()
        except Exception as e:
            print(f"[HINWEIS] Fehler beim Stoppen der Messung: {e}")

    def software_reset(self) -> None:
        """Sends the software reset command (0xA1) to the ISX-3."""
        if not self.device or not self.device.is_open:
            print("[WARNUNG] Kein Geraet verbunden, Reset uebersprungen.")
            return

        reset_frame = bytes([0xA1, 0x00, 0xA1])
        self.device.write(reset_frame)
        self.device.flush()
        time.sleep(1.0)
        self.device.reset_input_buffer()
        self.active_mux_pins = None
        print("[OK] Software-Reset an ISX-3 gesendet.")

    def set_options(self, settings: dict) -> None:
        """
        Configures optional frame extensions (0x97) and inter-sweep synchronization.
        In Medical Research ISX-3 mode, inactive 0x97 commands are skipped or protected
        via try-except to prevent ACK timeouts or NACK command lockups.
        """
        self.device_version = str(settings.get("device_version", self.device_version)).strip().lower()
        timestamp_mode = int(settings.get("timestamp_mode", 0))
        enable_current_range_output = bool(settings.get("enable_current_range_output", False))
        dc_bias_enabled = bool(settings.get("dc_bias_enabled", False))
        bias_voltage_v = float(settings.get("bias_voltage_v", 0.0))
        sync_time_us = int(settings.get("sync_time_us", 0))

        # Ensure the device is not stuck in measurement mode before applying options
        self.stop_measurement()

        if "medical" not in self.device_version or timestamp_mode > 0 or enable_current_range_output:
            try:
                if timestamp_mode == 1:
                    self._send_command(0x97, bytes([0x01, 0x01]), timeout=1.0)
                elif timestamp_mode == 2:
                    self._send_command(0x97, bytes([0x02, 0x01]), timeout=1.0)
                elif "medical" not in self.device_version:
                    self._send_command(0x97, bytes([0x01, 0x00]), timeout=1.0)
                    self._send_command(0x97, bytes([0x02, 0x00]), timeout=1.0)

                if enable_current_range_output or "medical" not in self.device_version:
                    self._send_command(0x97, bytes([0x04, 1 if enable_current_range_output else 0]), timeout=1.0)
            except Exception as e:
                print(f"[HINWEIS] Befehl 0x97 wird von dieser Firmware nicht bestaetigt (uebersprungen): {e}")
                settings["timestamp_mode"] = 0
                settings["enable_current_range_output"] = False
                if self.device and self.device.is_open:
                    time.sleep(0.1)
                    self.device.reset_input_buffer()
                    self.device.reset_output_buffer()
        else:
            print("[INFO] Medical-Modus: Ueberspringe inaktive 0x97-Optionen (verhindert ACK-Timeout).")

        # DC bias is only used on the main front BNC port
        if not settings.get("mux_enabled", False):
            try:
                bias_payload = bytes([0x33]) + struct.pack(">f", float(bias_voltage_v))
                self._send_command(self.CMD_SETUP_FREQUENCY, bias_payload, timeout=1.5)
                self._send_command(self.CMD_SETUP_FREQUENCY, bytes([0x30, 1 if dc_bias_enabled else 0]), timeout=1.5)
            except Exception as e:
                print(f"[HINWEIS] DC-Bias Setup uebersprungen: {e}")

        # Inter-sweep pause (0xB9)
        if sync_time_us > 0 or "medical" not in self.device_version:
            try:
                sync_payload = struct.pack(">I", int(sync_time_us))
                self._send_command(0xB9, sync_payload, timeout=1.5)
            except Exception as e:
                print(f"[HINWEIS] Sync-Time (0xB9) uebersprungen: {e}")

    def set_extension_port(
        self,
        counter_port: int,
        reference_port: int,
        working_sense_port: int,
        working_port: int,
    ) -> None:
        """Switches the external extension port on Standard ISX-3 devices (command 0xB2)."""
        pins = (
            int(counter_port),
            int(reference_port),
            int(working_sense_port),
            int(working_port),
        )
        self._send_command(self.CMD_SETUP_EXTENSION, bytes(pins))

    def configure_multipin_registers(
        self,
        ce_pins: list[int],
        re_pins: list[int],
        ws_pins: list[int],
        we_pins: list[int],
        mux_channel: int = 3,
    ) -> None:
        """
        PLACEHOLDER FOR FUTURE FIRMWARE UPDATE (Register-Based Multi-Pin Ganging):
        According to the manufacturer (Sciospec), simultaneous parallel switching of
        multiple multiplexer channels onto a single electrode path (CE, RE, WS, WE)
        is not supported by the current 0xB0 command stack. A future firmware update
        will provide direct hardware register programming (bitmask addressing) to close
        arbitrary relay combinations simultaneously.

        Once the manufacturer releases the register specification:
        1. Convert ce_pins, re_pins, ws_pins, we_pins into 32-bit/64-bit relay bitmasks.
        2. Pack the register address and bitmask payload into the new command tag.
        3. Transmit via self._send_command(...) and verify ACK.
        """
        raise NotImplementedError(
            "Multi-Pin-Parallelschaltung (Electrode Ganging) wird von der aktuellen ISX-3 Firmware "
            "hardwareseitig noch nicht unterstuetzt. Ein zukuenftiges Firmware-Update des Herstellers "
            "wird hierfuer eine direkte Register-Programmierung bereitstellen (Platzhalter: "
            "ISX3.configure_multipin_registers)."
        )

    def route_mux_sensor(
        self,
        sensor_idx: int,
        wire_mode: int = 4,
        custom_pins: tuple[int, int, int, int] | list[tuple[int, int, int, int]] | None = None,
        **kwargs: Any,
    ) -> tuple[int, int, int, int] | list[tuple[int, int, int, int]]:
        """
        Calculates pin channel assignments for MUX32/64 and updates routing state.
        Note: Experimental multi-pin list routing is retained in code for reference
        but blocked unless ENABLE_EXPERIMENTAL_MULTIPIN_STACKING is explicitly enabled.
        """
        if custom_pins is not None:
            if isinstance(custom_pins, list):
                if not self.ENABLE_EXPERIMENTAL_MULTIPIN_STACKING:
                    # Trigger the register placeholder error when multi-pin lists are passed
                    self.configure_multipin_registers([], [], [], [])

                # --- DEACTIVATED LEGACY MULTI-PIN STACKING (RETAINED FOR REFERENCE) ---
                pin_tuples = [tuple(int(x) for x in t) for t in custom_pins]
                self.active_mux_pins = pin_tuples if len(pin_tuples) > 1 else pin_tuples[0]
                ce_s = ",".join(str(t[0]) for t in pin_tuples)
                re_s = ",".join(str(t[1]) for t in pin_tuples)
                ws_s = ",".join(str(t[2]) for t in pin_tuples)
                we_s = ",".join(str(t[3]) for t in pin_tuples)
                print(
                    f"[MUX] Sensor #{sensor_idx} (Multi-Pin Custom) aktiviert -> "
                    f"CE:[{ce_s}], RE:[{re_s}], WS:[{ws_s}], WE:[{we_s}]"
                )
                return self.active_mux_pins
            else:
                ce, re, ws, we = (int(x) for x in custom_pins)
        elif wire_mode == 4:
            ce = 4 * sensor_idx - 3
            re = 4 * sensor_idx - 2
            ws = 4 * sensor_idx - 1
            we = 4 * sensor_idx
        elif wire_mode == 2:
            ce = 2 * sensor_idx - 1
            re = ce
            we = 2 * sensor_idx
            ws = we
        else:
            raise ValueError(f"Ungueltiger wire_mode: {wire_mode}. Nur 2 oder 4 erlaubt.")

        self.active_mux_pins = (ce, re, ws, we)
        print(f"[MUX] Sensor #{sensor_idx} ({wire_mode}-Leiter) aktiviert -> CE:{ce}, RE:{re}, WS:{ws}, WE:{we}")
        return ce, re, ws, we

    def clear_mux_routing(self) -> None:
        """Stops any residual measurements and resets the active multiplexer routing."""
        self.active_mux_pins = None
        if self.device and self.device.is_open:
            self.stop_measurement()
            try:
                self._send_command(self.CMD_SETUP_FRONTEND, bytes([0xFF, 0xFF, 0xFF]), timeout=1.5)
            except Exception:
                pass

    def _apply_frontend_and_routing(
        self,
        measurement_mode: int,
        measurement_channel: int,
        current_range: int,
        voltage_range: int,
        switch_delay: float = 0.02,
    ) -> None:
        """
        Configures the analog frontend via command 0xB0.
        Distinguishes between the 15-byte Medical protocol and the 4-byte Standard protocol (with 0xB2).
        """
        if int(current_range) not in (0, 1, 2, 4, 6):
            print(f"[WARNUNG] Ungueltiger current_range={current_range}, setze auf 2 (±100 µA).")
            current_range = 2

        if int(voltage_range) not in (1, 2):
            voltage_range = 1

        # Clear previous frontend setup once before applying new assignment
        self._send_command(self.CMD_SETUP_FRONTEND, bytes([0xFF, 0xFF, 0xFF]))

        # Normalize pin configuration
        if self.active_mux_pins is not None:
            if isinstance(self.active_mux_pins, list):
                if not self.ENABLE_EXPERIMENTAL_MULTIPIN_STACKING:
                    self.configure_multipin_registers([], [], [], [])
                pin_tuples = self.active_mux_pins
            else:
                pin_tuples = [self.active_mux_pins]
        else:
            pin_tuples = []

        if "medical" in self.device_version:
            header = struct.pack(">BBB", int(measurement_mode), int(current_range), int(voltage_range))

            if pin_tuples:
                chan_type = int(measurement_channel) if int(measurement_channel) in (2, 3) else 3
                # In normal operation pin_tuples contains exactly 1 tuple (ce, re, ws, we).
                # Legacy stacking loop is preserved for reference.
                for ce, re, ws, we in pin_tuples:
                    if measurement_mode == 1:
                        ch_settings = struct.pack(">BHBH", chan_type, ce, chan_type, we)
                    elif measurement_mode == 3:
                        ch_settings = struct.pack(">BHBHBH", chan_type, ce, chan_type, re, chan_type, we)
                    else:
                        ch_settings = struct.pack(
                            ">BHBHBHBH",
                            chan_type, ce,
                            chan_type, re,
                            chan_type, ws,
                            chan_type, we,
                        )
                    self._send_command(self.CMD_SETUP_FRONTEND, header + ch_settings)
            else:
                chan_type = 1
                ce = re = ws = we = 0
                if measurement_mode == 1:
                    ch_settings = struct.pack(">BHBH", chan_type, ce, chan_type, we)
                elif measurement_mode == 3:
                    ch_settings = struct.pack(">BHBHBH", chan_type, ce, chan_type, re, chan_type, we)
                else:
                    ch_settings = struct.pack(">BHBHBHBH", chan_type, ce, chan_type, re, chan_type, ws, chan_type, we)
                self._send_command(self.CMD_SETUP_FRONTEND, header + ch_settings)

            time.sleep(max(0.08, float(switch_delay)))
        else:
            # Standard mode: 4-byte frontend command + routing via command 0xB2
            fe_payload = struct.pack(
                ">BBBB", int(measurement_mode), int(measurement_channel), int(current_range), int(voltage_range)
            )
            self._send_command(self.CMD_SETUP_FRONTEND, fe_payload)

            if pin_tuples:
                for ce, re, ws, we in pin_tuples:
                    self.set_extension_port(ce, re, ws, we)
                time.sleep(max(0.08, float(switch_delay)))
            else:
                time.sleep(0.02)

    def _build_extended_options(
        self,
        point_delay_us: int,
        phase_sync: bool,
        excitation_type: int,
        frequency_hz: float = 100000.0,
    ) -> bytes:
        """Builds the binary Extended Options (EOPs) for the frequency setup (0xB6)."""
        eops = b""
        if point_delay_us > 0:
            eops += bytes([0x01]) + struct.pack(">I", int(point_delay_us))
        if phase_sync and frequency_hz >= 100000.0:
            eops += bytes([0x02]) + struct.pack(">I", 1)
        if excitation_type != 1:
            eops += bytes([0x03]) + struct.pack(">I", int(excitation_type))
        return eops

    def set_frequency_setup(self, current_setup: dict) -> None:
        """Configures a single discrete frequency point (0xB6 Sub 0x02)."""
        self.device_version = str(current_setup.get("device_version", self.device_version)).strip().lower()
        measurement_mode = int(current_setup.get("measurement_mode", 2))
        measurement_channel = int(current_setup.get("measurement_channel", 1))
        current_range = int(current_setup.get("current_range", 2))
        voltage_range = int(current_setup.get("voltage_range", 1))

        frequency = float(current_setup["frequency"])
        precision = float(current_setup.get("precision", 1.0))

        raw_amplitude = float(current_setup.get("amplitude", 0.0001))
        # In Medical mode: automatically halve peak-to-peak (App/Vpp) to peak (Ap/Vp) for firmware
        amplitude = raw_amplitude * 0.5 if "medical" in self.device_version else raw_amplitude

        excitation_type = int(current_setup.get("excitation_type", 2))
        point_delay_us = int(current_setup.get("point_delay_us", 0))
        phase_sync = bool(current_setup.get("phase_sync", False))

        self._send_command(self.CMD_SETUP_FREQUENCY, bytes([0x01]))

        self._apply_frontend_and_routing(
            measurement_mode=measurement_mode,
            measurement_channel=measurement_channel,
            current_range=current_range,
            voltage_range=voltage_range,
            switch_delay=0.02,
        )

        eops = self._build_extended_options(
            point_delay_us=point_delay_us,
            phase_sync=phase_sync,
            excitation_type=excitation_type,
            frequency_hz=frequency,
        )

        freq_payload = bytes([0x02]) + struct.pack(">fff", frequency, precision, amplitude) + eops
        self._send_command(self.CMD_SETUP_FREQUENCY, freq_payload)

    def configure_hardware_sweep(
        self,
        blocks: list[dict],
        global_settings: dict,
        switch_delay_s: float = 0.10,
    ) -> None:
        """Configures hardware-controlled multi-block frequency sweeps (0xB6 Sub 0x03)."""
        self.device_version = str(global_settings.get("device_version", self.device_version)).strip().lower()
        measurement_mode = int(global_settings.get("measurement_mode", 2))
        measurement_channel = int(global_settings.get("measurement_channel", 1))
        current_range = int(global_settings.get("current_range", 2))
        voltage_range = int(global_settings.get("voltage_range", 1))
        switch_delay = float(global_settings.get("switch_delay_s", switch_delay_s))

        self._send_command(self.CMD_SETUP_FREQUENCY, bytes([0x01]))

        for block in blocks:
            start_f = float(block["start_frequency_hz"])
            stop_f = float(block["stop_frequency_hz"])
            count = float(block["count"])
            scale_flag = 1 if str(block["scale"]).strip().lower() == "logarithmic" else 0
            precision = float(block["precision"])

            raw_amplitude = float(block["amplitude"])
            amplitude = raw_amplitude * 0.5 if "medical" in self.device_version else raw_amplitude

            excitation_type = int(block["excitation_type"])
            point_delay_us = int(block["point_delay_us"])
            phase_sync = bool(block["phase_sync"])

            eops = self._build_extended_options(
                point_delay_us=point_delay_us,
                phase_sync=phase_sync,
                excitation_type=excitation_type,
                frequency_hz=stop_f,
            )
            sweep_payload = (
                bytes([0x03])
                + struct.pack(">fffBff", start_f, stop_f, count, scale_flag, precision, amplitude)
                + eops
            )
            self._send_command(self.CMD_SETUP_FREQUENCY, sweep_payload)

        self._apply_frontend_and_routing(
            measurement_mode=measurement_mode,
            measurement_channel=measurement_channel,
            current_range=current_range,
            voltage_range=voltage_range,
            switch_delay=switch_delay,
        )

    def start_measurement(
        self, spectra: int, id: int, measurement_settings: dict, expected_frames: int | None = None
    ) -> dict:
        """Starts the measurement run via command 0xB8, reads incoming frames, and cleanly stops measurement mode."""
        if not self.device or not self.device.is_open:
            print("[FEHLER] Kein Geraet verbunden.")
            return {
                "id": [], "real": [], "imag": [], "timestamp": [],
                "timestamp_unit": [], "current_range": [], "frequencies": [],
            }

        cmd_tag = self.CMD_MEASURE

        if spectra == 0:
            data_start = bytes([0x01, 0x00, 0x00])
            self.device.write(bytes([cmd_tag, len(data_start)]) + data_start + bytes([cmd_tag]))
            self.device.flush()
            print("[INFO] Kontinuierliche Messung gestartet. Druecke Strg+C zum Stoppen...")
            try:
                while True:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                pass
            self.stop_measurement()
            print("[INFO] Kontinuierliche Messung gestoppt.")
            return {
                "id": [], "real": [], "imag": [], "timestamp": [],
                "timestamp_unit": [], "current_range": [], "frequencies": [],
            }

        data_start = bytes([0x01]) + int(spectra).to_bytes(2, byteorder="big")
        frame = bytes([cmd_tag, len(data_start)]) + data_start + bytes([cmd_tag])
        self.device.write(frame)
        self.device.flush()

        total_frames = expected_frames if expected_frames is not None else spectra
        precision_val = float(measurement_settings.get("precision", 1.0))
        per_frame_timeout = max(1.0, 0.8 * (1.0 + precision_val))
        timeout = max(20.0, float(total_frames) * per_frame_timeout)

        try:
            return self.read_measurement_data(
                spectra=total_frames,
                timeout=timeout,
                measurement_settings=measurement_settings,
            )
        finally:
            # Guarantee that the ISX-3 exits measurement mode after reading frames
            self.stop_measurement()

    def read_measurement_data(
        self, spectra: int, timeout: float, measurement_settings: dict
    ) -> dict:
        """Parses measurement data frames (0xB8) from the serial byte stream."""
        results = {
            "id": [], "real": [], "imag": [], "timestamp": [],
            "timestamp_unit": [], "current_range": [], "frequencies": [],
        }

        ts_mode = int(measurement_settings.get("timestamp_mode", 0))
        cr_out = int(bool(measurement_settings.get("enable_current_range_output", False)))

        ts_bytes = 4 if ts_mode == 1 else (5 if ts_mode == 2 else 0)
        cr_bytes = 1 if cr_out else 0
        expected_base_len = 2 + ts_bytes + cr_bytes + 8

        start_time = time.time()

        while len(results["id"]) < spectra:
            if time.time() - start_time > timeout:
                raise TimeoutError(
                    f"Timeout beim Lesen der Messdaten: Nur {len(results['id'])}/{spectra} Frames empfangen."
                )

            tag = self.device.read(1)
            if not tag:
                continue

            if tag[0] == 0x1D:
                len_b = self.device.read(1)
                if len_b:
                    self.device.read(len_b[0] + 1)
                continue

            if tag[0] == self.ACK_TAG:
                ack_rest = self.device.read(3)
                if len(ack_rest) == 3 and ack_rest[2] == self.ACK_TAG:
                    status = ack_rest[1]
                    if status == self.ACK_SUCCESS:
                        continue
                    elif status in (0x90, 0x91):
                        print(f"[WARNUNG] ISX-3 meldet waehrend Messung: {MSG_DICT[status]}")
                        continue
                    elif status == self.NACK_SYNTAX:
                        raise ValueError("NACK (0x81): ISX-3 meldet Syntax-/Parameterfehler bei Befehl 0xB8!")
                    elif status == self.NACK_NOT_RECOGNIZED:
                        raise ValueError("NACK (0x82): ISX-3 erkennt Befehl 0xB8 nicht!")
                    else:
                        status_text = MSG_DICT.get(status, f"0x{status:02X}")
                        raise ValueError(f"Unerwarteter Status von ISX-3: {status_text}")
                continue

            if tag[0] != self.CMD_MEASURE:
                continue

            len_byte = self.device.read(1)
            if not len_byte:
                raise TimeoutError("Unerwarteter Verbindungsabbruch beim Lesen der Frame-Laenge.")
            length = len_byte[0]

            frame = self.device.read(length)
            if len(frame) < length:
                raise TimeoutError(f"Unvollstaendige Payload empfangen: {len(frame)} von {length} Bytes.")

            end_tag = self.device.read(1)
            if not end_tag or end_tag[0] != self.CMD_MEASURE:
                raise ValueError("Ungueltiges oder fehlendes End-Tag (0xB8) im Messframe.")

            offset = 1 if length == (expected_base_len + 1) else 0

            freq_id = int.from_bytes(frame[offset : offset + 2], byteorder="big")
            pos = offset + 2

            timestamp_val = None
            timestamp_unit = None
            current_range_val = None

            if ts_bytes == 4 and (pos + 4 + cr_bytes + 8) <= length:
                timestamp_val = struct.unpack(">I", frame[pos : pos + 4])[0]
                timestamp_unit = "ms"
                pos += 4
            elif ts_bytes == 5 and (pos + 5 + cr_bytes + 8) <= length:
                timestamp_val = int.from_bytes(frame[pos : pos + 5], byteorder="big")
                timestamp_unit = "us"
                pos += 5

            if cr_bytes == 1 and (pos + 1 + 8) <= length:
                current_range_val = frame[pos]
                pos += 1

            real = struct.unpack(">f", frame[length - 8 : length - 4])[0]
            imag = struct.unpack(">f", frame[length - 4 : length])[0]

            results["id"].append(freq_id)
            results["real"].append(real)
            results["imag"].append(imag)
            results["timestamp"].append(timestamp_val)
            results["timestamp_unit"].append(timestamp_unit)
            results["current_range"].append(current_range_val)

        return results

    def run_baseline_drift_check(
        self, port: str = "COM12", baudrate: int = 115200, mux_channel: int = 3, cycles: int = 5, freq_hz: float = 1000.0
    ) -> dict:
        """
        Performs a thermal stability check on the internal 2 kOhm reference resistor (pins 22,22,23,23).
        Measures impedance repeatedly and evaluates drift percentage (threshold <= 0.2%).
        """
        settings = {
            "port": port,
            "baudrate": baudrate,
            "device_version": "medical",
            "timestamp_mode": 0,
            "enable_current_range_output": False,
        }

        if not self.connect_device_fs(settings):
            return {
                "stable": False,
                "error": f"Verbindung zu Port '{port}' fehlgeschlagen.",
                "readings": [],
                "drift_pct": 0.0,
            }

        readings = []
        pins = (22, 22, 23, 23)  # Internal 2 kOhm precision resistor on MUX port 3

        try:
            print(f"\n[BASELINE-CHECK] Starte Stabilitaetspruefung auf 2 kΩ Referenz ({cycles} Zyklen @ {freq_hz:g} Hz)...")
            self.clear_mux_routing()
            self.route_mux_sensor(sensor_idx=2, wire_mode=4, custom_pins=pins)

            setup = {
                "device_version": "medical",
                "measurement_mode": 2,
                "measurement_channel": int(mux_channel),
                "current_range": 2,
                "voltage_range": 1,
                "frequency": freq_hz,
                "precision": 1.0,
                "amplitude": 0.0001,
                "excitation_type": 2,
                "point_delay_us": 20000,
                "phase_sync": False,
            }
            self.set_frequency_setup(setup)

            for i in range(cycles):
                raw = self.start_measurement(spectra=1, id=i + 1, measurement_settings=settings, expected_frames=1)
                if raw.get("real") and raw.get("imag"):
                    re = raw["real"][0]
                    im = raw["imag"][0]
                    z_mag = math.hypot(re, im)
                    readings.append(z_mag)
                    print(f"  Zyklus {i+1}/{cycles}: |Z| = {z_mag:.2f} Ohm")
                time.sleep(0.2)

        except Exception as e:
            return {
                "stable": False,
                "error": str(e),
                "readings": readings,
                "drift_pct": 0.0,
            }
        finally:
            try:
                self.clear_mux_routing()
            except Exception:
                pass
            if self.device and self.device.is_open:
                self.device.close()
                print("[OK] Serielle Schnittstelle nach Baseline-Check geschlossen.")

        if len(readings) < 2:
            return {
                "stable": False,
                "error": "Zu wenig gueltige Messwerte empfangen.",
                "readings": readings,
                "drift_pct": 0.0,
            }

        mean_z = sum(readings) / len(readings)
        max_diff = max(abs(r - mean_z) for r in readings)
        drift_pct = (max_diff / mean_z) * 100.0

        is_stable = drift_pct <= 0.2
        status_text = "STABIL (OK)" if is_stable else "INSTABIL (Drift zu hoch)"

        print(f"[ERGEBNIS] Mittelwert: {mean_z:.2f} Ohm | Maximaler Drift: {drift_pct:.3f}% -> Status: {status_text}")

        return {
            "stable": is_stable,
            "error": None,
            "mean_z": mean_z,
            "readings": readings,
            "drift_pct": drift_pct,
        }