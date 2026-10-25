"""
commands.py - Treiber- und Kommunikationsschicht für das Sciospec ISX-3 Impedanzspektrometer.
"""

import struct
import time
import serial
import serial.tools.list_ports


MSG_DICT = {
    0x01: "Frame-NACK: Ungültige Syntax",
    0x02: "Kommunikations-Timeout (weniger Daten empfangen als erwartet)",
    0x04: "System-Boot bereit (Wake-Up-Meldung)",
    0x11: "Gültige TCP-Client-Socket-Verbindung",
    0x81: "NACK: Befehl wurde nicht ausgeführt (Syntax- oder Parameterfehler)",
    0x82: "NACK: Befehl wurde nicht erkannt / unbekanntes Tag",
    0x83: "ACK: Befehl erfolgreich ausgeführt",
    0x84: "System bereit (System operational and ready)",
    0x90: "Warnung: Überstrom erkannt (DC Current Range überschritten)",
    0x91: "Warnung: Überspannung erkannt (DC Voltage Range überschritten)",
    0x92: "Datenstau: Messdaten konnten nicht über die Schnittstelle gesendet werden",
}


class ISX3:
    """Kapselt alle Steuerbefehle und das Binärprotokoll des Sciospec ISX-3."""

    ACK_TAG = 0x18
    ACK_SUCCESS = 0x83
    NACK_SYNTAX = 0x81
    NACK_NOT_RECOGNIZED = 0x82

    CMD_SETUP_FRONTEND = 0xB0
    CMD_GET_FRONTEND = 0xB1
    CMD_SETUP_EXTENSION = 0xB2
    CMD_GET_EXTENSION_PORT = 0xB3
    CMD_GET_EXTENSION_MODULE = 0xB5
    CMD_SETUP_FREQUENCY = 0xB6
    CMD_GET_SETUP = 0xB7
    CMD_MEASURE = 0xB8

    def __init__(self):
        self.device: serial.Serial | None = None
        self.serial_protocol = None
        self.print_msg = True
        self.active_mux_pins: tuple[int, int, int, int] | None = None

    def is_port_available(self, port: str) -> bool:
        available_ports = [p.device for p in serial.tools.list_ports.comports()]
        return port in available_ports

    def list_available_ports(self) -> list[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect_device_fs(self, settings: dict) -> serial.Serial | None:
        port = settings.get("port", "COM12")
        baudrate = int(settings.get("baudrate", 115200))

        if not self.is_port_available(port):
            print(f"[FEHLER] Serieller Port '{port}' ist nicht verfügbar.")
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
            print(f"[OK] Erfolgreich verbunden mit {self.device.name} bei {baudrate} Baud.")
            return self.device
        except serial.SerialException as error:
            print(f"[FEHLER] Verbindung fehlgeschlagen: {error}")
            return None

    def _send_command(self, cmd_tag: int, data: bytes, timeout: float = 3.0) -> None:
        if not self.device or not self.device.is_open:
            raise ConnectionError("Keine aktive serielle Verbindung zum ISX-3 vorhanden.")

        if self.device.in_waiting > 0:
            self.device.read(self.device.in_waiting)

        length = len(data)
        if length > 255:
            raise ValueError(f"Payload-Länge ({length} Bytes) überschreitet das Maximum von 255 Bytes.")

        frame = bytes([cmd_tag, length]) + data + bytes([cmd_tag])
        self.device.write(frame)
        self.device.flush()

        self._wait_for_ack(cmd_tag, timeout=timeout)

    def _wait_for_ack(self, original_cmd_tag: int, timeout: float = 3.0) -> None:
        start_time = time.time()
        while time.time() - start_time < timeout:
            tag_byte = self.device.read(1)
            if not tag_byte:
                continue

            tag = tag_byte[0]

            if tag == self.ACK_TAG:
                rest = self.device.read(3)
                if len(rest) < 3:
                    raise TimeoutError(f"Unvollständiger ACK-Frame für Befehl 0x{original_cmd_tag:02X}.")
                if rest[2] != self.ACK_TAG:
                    continue

                status = rest[1]
                if status == self.ACK_SUCCESS:
                    return
                if status in (0x90, 0x91):
                    print(f"[WARNUNG] ISX-3 meldet: {MSG_DICT[status]}")
                    continue
                if status == self.NACK_SYNTAX:
                    raise ValueError(f"NACK (0x81): Ungültige Syntax/Parameter für Befehl 0x{original_cmd_tag:02X}.")
                if status == self.NACK_NOT_RECOGNIZED:
                    raise ValueError(f"NACK (0x82): Befehl 0x{original_cmd_tag:02X} wurde vom ISX-3 nicht erkannt.")

                status_text = MSG_DICT.get(status, f"Unbekannter Status-Code 0x{status:02X}")
                raise ValueError(f"Unerwarteter Status empfangen: {status_text}")

            elif tag in (0x1D, self.CMD_GET_EXTENSION_MODULE, self.CMD_GET_FRONTEND, self.CMD_GET_EXTENSION_PORT):
                len_b = self.device.read(1)
                if not len_b:
                    continue
                msg_len = len_b[0]
                payload = self.device.read(msg_len)
                self.device.read(1)
                if tag == 0x1D:
                    print(f"[STATUS-INFO] ISX-3 Systemnachricht (0x1D): Payload={payload.hex()}")
                continue

        raise TimeoutError(f"Timeout: Keine Bestätigung (ACK) für Befehl 0x{original_cmd_tag:02X} erhalten.")

    def software_reset(self) -> None:
        if not self.device or not self.device.is_open:
            print("[WARNUNG] Kein Gerät verbunden, Reset übersprungen.")
            return

        reset_frame = bytes([0xA1, 0x00, 0xA1])
        self.device.write(reset_frame)
        self.device.flush()
        time.sleep(1.0)
        self.device.reset_input_buffer()
        self.active_mux_pins = None
        print("[OK] Software-Reset an ISX-3 gesendet.")

    def set_options(self, settings: dict) -> None:
        timestamp_mode = int(settings.get("timestamp_mode", 0))
        enable_current_range_output = bool(settings.get("enable_current_range_output", False))
        dc_bias_enabled = bool(settings.get("dc_bias_enabled", False))
        bias_voltage_v = float(settings.get("bias_voltage_v", 0.0))
        sync_time_us = int(settings.get("sync_time_us", 0))

        if timestamp_mode == 1:
            self._send_command(0x97, bytes([0x01, 0x01]))
        elif timestamp_mode == 2:
            self._send_command(0x97, bytes([0x02, 0x01]))
        else:
            self._send_command(0x97, bytes([0x01, 0x00]))
            self._send_command(0x97, bytes([0x02, 0x00]))

        self._send_command(0x97, bytes([0x04, 1 if enable_current_range_output else 0]))

        if not settings.get("mux_enabled", False):
            bias_payload = bytes([0x33]) + struct.pack(">f", float(bias_voltage_v))
            self._send_command(self.CMD_SETUP_FREQUENCY, bias_payload)
            self._send_command(self.CMD_SETUP_FREQUENCY, bytes([0x30, 1 if dc_bias_enabled else 0]))

        sync_payload = struct.pack(">I", int(sync_time_us))
        self._send_command(0xB9, sync_payload)

    def set_extension_port(
        self,
        counter_port: int,
        reference_port: int,
        working_sense_port: int,
        working_port: int,
    ) -> None:
        pins = (
            int(counter_port),
            int(reference_port),
            int(working_sense_port),
            int(working_port),
        )
        self._send_command(self.CMD_SETUP_EXTENSION, bytes(pins))

    def route_mux_sensor(
        self,
        sensor_idx: int,
        wire_mode: int = 4,
        custom_pins: tuple[int, int, int, int] | None = None,
        **kwargs,
    ) -> tuple[int, int, int, int]:
        if custom_pins is not None:
            ce, re, ws, we = custom_pins
        elif wire_mode == 4:
            if not 1 <= sensor_idx <= 32:
                raise ValueError(f"Sensor-Index {sensor_idx} ungültig.")
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
            raise ValueError(f"Ungültiger wire_mode: {wire_mode}. Erlaubt sind nur 2 oder 4.")

        self.active_mux_pins = (ce, re, ws, we)
        print(f"[MUX32] Sensor #{sensor_idx} ({wire_mode}-Leiter) ausgewählt -> CE:{ce}, RE:{re}, WS:{ws}, WE:{we}")
        return ce, re, ws, we

    def clear_mux_routing(self) -> None:
        self.active_mux_pins = None
        if self.device and self.device.is_open:
            self._send_command(self.CMD_SETUP_FRONTEND, bytes([0xFF, 0xFF, 0xFF]))

    def _build_extended_options(
        self,
        point_delay_us: int,
        phase_sync: bool,
        excitation_type: int,
        frequency_hz: float = 100000.0,
    ) -> bytes:
        eops = b""
        if point_delay_us > 0:
            eops += bytes([0x01]) + struct.pack(">I", int(point_delay_us))
        if phase_sync and frequency_hz >= 100000.0:
            eops += bytes([0x02]) + struct.pack(">I", 1)
        if excitation_type != 1:
            eops += bytes([0x03]) + struct.pack(">I", int(excitation_type))
        return eops

    def set_frequency_setup(self, current_setup: dict) -> None:
        """Klassischer Punkt-für-Punkt-Modus (0xB6 0x02)."""
        measurement_mode = int(current_setup.get("measurement_mode", 2))
        measurement_channel = int(current_setup.get("measurement_channel", 1))
        current_range = int(current_setup.get("current_range", 2))
        voltage_range = int(current_setup.get("voltage_range", 1))

        frequency = float(current_setup["frequency"])
        precision = float(current_setup.get("precision", 1.0))
        amplitude = float(current_setup.get("amplitude", 0.0001))
        excitation_type = int(current_setup.get("excitation_type", 2))
        point_delay_us = int(current_setup.get("point_delay_us", 0))
        phase_sync = bool(current_setup.get("phase_sync", False))

        self._send_command(self.CMD_SETUP_FREQUENCY, bytes([0x01]))
        self._send_command(self.CMD_SETUP_FRONTEND, bytes([0xFF, 0xFF, 0xFF]))

        fe_payload = struct.pack(">BBBB", measurement_mode, measurement_channel, current_range, voltage_range)
        self._send_command(self.CMD_SETUP_FRONTEND, fe_payload)

        if self.active_mux_pins is not None:
            self.set_extension_port(*self.active_mux_pins)

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
            amplitude = float(block["amplitude"])
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

        self._send_command(self.CMD_SETUP_FRONTEND, bytes([0xFF, 0xFF, 0xFF]))

        fe_payload = struct.pack(">BBBB", measurement_mode, measurement_channel, current_range, voltage_range)
        self._send_command(self.CMD_SETUP_FRONTEND, fe_payload)

        if self.active_mux_pins is not None:
            self.set_extension_port(*self.active_mux_pins)
            time.sleep(max(0.08, float(switch_delay)))
        else:
            time.sleep(0.02)

    def start_measurement(
        self, spectra: int, id: int, measurement_settings: dict, expected_frames: int | None = None
    ) -> dict:
        if not self.device or not self.device.is_open:
            print("[FEHLER] Kein Gerät verbunden.")
            return {
                "id": [], "real": [], "imag": [], "timestamp": [],
                "timestamp_unit": [], "current_range": [], "frequencies": [],
            }

        cmd_tag = self.CMD_MEASURE

        if spectra == 0:
            data_start = bytes([0x01, 0x00, 0x00])
            self.device.write(bytes([cmd_tag, len(data_start)]) + data_start + bytes([cmd_tag]))
            self.device.flush()
            print("[INFO] Kontinuierliche Messung gestartet. Drücke Strg+C zum Stoppen...")
            try:
                while True:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                pass
            data_stop = bytes([0x00])
            self.device.write(bytes([cmd_tag, len(data_stop)]) + data_stop + bytes([cmd_tag]))
            self.device.flush()
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

        return self.read_measurement_data(
            spectra=total_frames,
            timeout=timeout,
            measurement_settings=measurement_settings,
        )

    def read_measurement_data(
        self, spectra: int, timeout: float, measurement_settings: dict
    ) -> dict:
        results = {
            "id": [], "real": [], "imag": [], "timestamp": [],
            "timestamp_unit": [], "current_range": [], "frequencies": [],
        }

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
                        print(f"[WARNUNG] ISX-3 meldet während Messung: {MSG_DICT[status]}")
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
                raise TimeoutError("Unerwarteter Verbindungsabbruch beim Lesen der Frame-Länge.")
            length = len_byte[0]

            frame = self.device.read(length)
            if len(frame) < length:
                raise TimeoutError(f"Unvollständige Payload empfangen: {len(frame)} von {length} Bytes.")

            end_tag = self.device.read(1)
            if not end_tag or end_tag[0] != self.CMD_MEASURE:
                raise ValueError("Ungültiges oder fehlendes End-Tag (0xB8) im Messframe.")

            freq_id = int.from_bytes(frame[0:2], byteorder="big")
            timestamp_val = None
            timestamp_unit = None
            current_range_val = None

            if length == 0x0A:
                real = struct.unpack(">f", frame[2:6])[0]
                imag = struct.unpack(">f", frame[6:10])[0]
            elif length == 0x0E:
                timestamp_val = struct.unpack(">I", frame[2:6])[0]
                timestamp_unit = "ms"
                real = struct.unpack(">f", frame[6:10])[0]
                imag = struct.unpack(">f", frame[10:14])[0]
            elif length == 0x0B:
                current_range_val = frame[2]
                real = struct.unpack(">f", frame[3:7])[0]
                imag = struct.unpack(">f", frame[7:11])[0]
            elif length == 0x0F and measurement_settings.get("enable_current_range_output", 0) == 0:
                timestamp_val = int.from_bytes(frame[2:7], byteorder="big")
                timestamp_unit = "us"
                real = struct.unpack(">f", frame[7:11])[0]
                imag = struct.unpack(">f", frame[11:15])[0]
            elif length == 0x0F and measurement_settings.get("enable_current_range_output", 0) != 0:
                timestamp_val = struct.unpack(">I", frame[2:6])[0]
                timestamp_unit = "ms"
                current_range_val = frame[6]
                real = struct.unpack(">f", frame[7:11])[0]
                imag = struct.unpack(">f", frame[11:15])[0]
            else:
                raise ValueError(f"Nicht unterstützte Frame-Länge: 0x{length:02X} ({length} Bytes).")

            results["id"].append(freq_id)
            results["real"].append(real)
            results["imag"].append(imag)
            results["timestamp"].append(timestamp_val)
            results["timestamp_unit"].append(timestamp_unit)
            results["current_range"].append(current_range_val)

        return results