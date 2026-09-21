import struct
import serial
import time




class ISX3Transmitter:
    """
    Klasse zur Übertragung der Konfiguration an das Sciospec ISX-3 / ISX-3mini Messgerät.
    Erfordert ein ISX3DeviceConfig Objekt (aus dem Config-Parser).
    """

    # Bekannte System-Nachrichten (ACK/NACK), siehe Handbuch Kapitel 6.2 "Acknowledge messages"
    ACK_TAG = 0x18
    ACK_SUCCESS = 0x83
    NACK_NOT_EXECUTED = 0x81  # Befehl war syntaktisch gültig, wurde aber nicht ausgeführt (z.B. fehlende Voraussetzung wie kein geladenes Setup)
    NACK_NOT_RECOGNIZED = 0x82

    def __init__(self, serial_port: serial.Serial):
        """
        Erwartet eine geöffnete serielle Verbindung (pyserial).
        """
        self.ser = serial_port

    def _send_command(self, cmd_tag: int, data: bytes):
        """
        Verpackt die Daten in das Sciospec Frame-Format und sendet sie.
        Format: [CMD-Tag] [Length] [Data...] [CMD-Tag]
        """
        length = len(data)
        if length > 255:
            raise ValueError("Daten-Payload überschreitet maximale Frame-Länge von 255 Bytes.")

        # Frame zusammensetzen
        frame = bytes([cmd_tag, length]) + data + bytes([cmd_tag])

        # Puffer leeren: verwirft Störbytes (z.B. unaufgeforderte System-Nachrichten), die sonst
        # die Byte-Ausrichtung der Antwort auf DIESEN Befehl durcheinanderbringen würden.
        self.ser.reset_input_buffer()

        # Senden
        self.ser.write(frame)
        self.ser.flush()

        # Auf Bestätigung (ACK) warten
        self._wait_for_ack(cmd_tag)

    def _wait_for_ack(self, original_cmd_tag: int):
        """
        Liest den Rückgabe-Frame und prüft auf erfolgreiches Acknowledge.
        Ein ACK-Frame sieht so aus: 0x18 0x01 [Status] 0x18[cite: 2]
        Sucht aktiv nach dem Start-Tag 0x18, um sich nach evtl. verbliebenen Störbytes
        im Puffer wieder auf den Frame-Anfang zu synchronisieren.
        """
        tag = self.ser.read(1)
        while tag and tag[0] != self.ACK_TAG:
            tag = self.ser.read(1)

        if not tag:
            raise TimeoutError(f"Timeout beim Warten auf ACK für Befehl {hex(original_cmd_tag)}")

        rest = self.ser.read(3)
        if len(rest) < 3:
            raise TimeoutError(f"Timeout beim Warten auf ACK für Befehl {hex(original_cmd_tag)}")

        ack_frame = tag + rest

        if ack_frame[3] != self.ACK_TAG:
            raise ConnectionError(f"Ungültiger ACK-Frame empfangen: {ack_frame.hex()}")

        status = ack_frame[2]
        if status == self.ACK_SUCCESS:
            return  # Alles in Ordnung[cite: 2]
        elif status == self.NACK_NOT_EXECUTED:
            raise ValueError(f"NACK (0x81): Befehl {hex(original_cmd_tag)} war gültig, wurde aber nicht ausgeführt (z.B. fehlt eine Voraussetzung wie ein geladenes Setup)")
        elif status == self.NACK_NOT_RECOGNIZED:
            raise ValueError(f"NACK (0x82): Befehl {hex(original_cmd_tag)} nicht erkannt[cite: 2]")
        else:
            raise ValueError(f"Unerwarteter Status-Code {hex(status)} empfangen.")

    def apply_config(self, config): # config: ISX3DeviceConfig
        """
        Überträgt alle Einstellungen nacheinander an das Gerät.
        """
        print("Starte Übertragung der Konfiguration...")
        
        # 1. System Reset (Optional, aber empfohlen für sauberen Status)
        # self._send_command(0xA1, b'') 
        # time.sleep(2) # Warten auf Boot Ready (Wake Up Message 0x04)

        # 2. Options (0x97)[cite: 2]
        print("Übertrage Options...")
        if config.options.timestamp_mode == 1:
            self._send_command(0x97, bytes([0x01, 0x01])) # Enable ms[cite: 2]
        elif config.options.timestamp_mode == 2:
            self._send_command(0x97, bytes([0x02, 0x01])) # Enable us[cite: 2]
        else:
            self._send_command(0x97, bytes([0x01, 0x00])) # Disable
            self._send_command(0x97, bytes([0x02, 0x00])) 

        # Enable/Disable Current Range
        self._send_command(0x97, bytes([0x04, 1 if config.options.enable_current_range_output else 0])) # [cite: 2]

        # 3. Frontend (0xB0)[cite: 2]
        print("Übertrage Frontend-Settings...")
        # Löst alte Frontend Stacks auf (Clear Stack)[cite: 2]
        self._send_command(0xB0, bytes([0xFF, 0xFF, 0xFF])) #[cite: 2]
        
        # Sende neue Frontend-Settings (Mode, Channel, C-Range, V-Range)
        fe_payload = struct.pack('>BBBB', 
                                 config.frontend.measurement_mode,
                                 config.frontend.measurement_channel,
                                 config.frontend.current_range,
                                 config.frontend.voltage_range)
        self._send_command(0xB0, fe_payload) # [cite: 2]

        # 4. Extension Port (0xB2)[cite: 2]
        # Optional: nur relevant, wenn ein Extension-Port-Modul (z. B. MuxModule) angeschlossen ist.
        # Ohne ein solches Modul quittiert das Gerät den Befehl mit NACK (0x82) - das ist kein Fehler.
        print("Übertrage Extension Port-Settings...")
        ext_payload = struct.pack('>BBBB',
                                  config.extension_port.counter_port,
                                  config.extension_port.reference_port,
                                  config.extension_port.working_sense_port,
                                  config.extension_port.working_port)
        try:
            self._send_command(0xB2, ext_payload) #[cite: 2]
        except ValueError as e:
            print(f"Extension Port-Settings übersprungen (vermutlich kein Modul angeschlossen): {e}")

        # 5. Frequency Setup (0xB6)[cite: 2]
        print("Übertrage Frequency-Setup...")
        # Init / Clear current setup
        self._send_command(0xB6, bytes([0x01])) #[cite: 2]
        
        # Extended Options (EOPs) vorbereiten[cite: 2]
        f_conf = config.frequency_setup
        eops = b''
        if f_conf.point_delay_us > 0:
            eops += bytes([0x01]) + struct.pack('>I', f_conf.point_delay_us) # [cite: 2]
        if f_conf.phase_sync:
            eops += bytes([0x02]) + struct.pack('>I', 1) # [cite: 2]
        if f_conf.excitation_type != 1:  
            eops += bytes([0x03]) + struct.pack('>I', f_conf.excitation_type) #[cite: 2]

        # Frequenzpunkte hinzufügen
        if f_conf.mode.lower() == 'single':
            # Single Frequency: 0x02 [Freq] [Prec] [Amp] [EOPs...][cite: 2]
            payload = bytes([0x02]) + struct.pack('>fff', 
                                                  f_conf.frequency_hz, 
                                                  f_conf.precision, 
                                                  f_conf.amplitude)
            self._send_command(0xB6, payload + eops) # [cite: 2]
            
        elif f_conf.mode.lower() == 'sweep':
            # Frequency List: 0x03 [StartF] [StopF] [Count] [Scale] [Prec] [Amp] [EOPs...][cite: 2]
            # Hinweis: Laut Doku ist "Count" ein 4-Byte Float![cite: 2]
            payload = bytes([0x03]) + struct.pack('>fffBff', 
                                                  f_conf.start_frequency_hz,
                                                  f_conf.stop_frequency_hz,
                                                  float(f_conf.count),
                                                  f_conf.scale,
                                                  f_conf.precision,
                                                  f_conf.amplitude)
            self._send_command(0xB6, payload + eops) #[cite: 2]

        # 6. DC Bias (0xB6 0x33 / 0x30)[cite: 2]
        print("Übertrage DC Bias...")
        # Value setzen
        bias_payload = bytes([0x33]) + struct.pack('>f', config.dc_bias.bias_voltage_v) #[cite: 2]
        self._send_command(0xB6, bias_payload) #[cite: 2]
        # Aktivieren/Deaktivieren
        self._send_command(0xB6, bytes([0x30, 1 if config.dc_bias.enabled else 0])) #[cite: 2]

        # 7. Sync Time (0xB9)[cite: 2]
        print("Übertrage Sync Time...")
        sync_payload = struct.pack('>I', config.sync_time.sync_time_us) #[cite: 2]
        self._send_command(0xB9, sync_payload) #[cite: 2]

        print("Konfiguration erfolgreich auf das ISX-3 übertragen!")

            
    def start_measurement(self, number_of_spectra: int = 1):
        """
        Startet die Messung anhand der zuvor gesendeten Konfiguration (Befehl 0xB8).[cite: 2]
        Bei number_of_spectra = 0 misst das Gerät kontinuierlich, bis stop_measurement() gesendet wird.
        """
        print(f"Starte Messung für {number_of_spectra} Spektren...")
        payload = bytes([0x01]) + struct.pack('>H', number_of_spectra) # uint16[cite: 2]
        self._send_command(0xB8, payload) # [cite: 2]

    def stop_measurement(self):
        """
        Stoppt eine laufende Messung (Befehl 0xB8, OP=0x00 "Stop measurement").
        Eigener, kürzerer Befehl als start_measurement (OP=0x01) - siehe Handbuch Kapitel 6.5.12:
        Syntax: [CT] 01 00 [CT]
        """
        print("Stoppe Messung...")
        self._send_command(0xB8, bytes([0x00]))

    def software_reset(self):
        """
        Sendet einen Software-Reset (Befehl 0xA1). Setzt das Gerät aus einem
        hängenden oder kontinuierlichen Messzustand zurück, ohne es aus- und
        wieder einzuschalten.
        """
        print("Sende Software-Reset...")
        self._send_command(0xA1, b"")

    def read_measurement_frame(self, timeout: float = 1.0):
        """
        Liest einen einzelnen Messergebnis-Frame (Befehl 0xB8) vom Gerät.
        Berücksichtigt einen optionalen Zeitstempel am Frame-Ende (siehe Options 0x97).

        Returns:
            dict mit freq_id, real, imag und timestamp (None falls deaktiviert),
            oder None, wenn innerhalb von `timeout` kein vollständiger Frame empfangen wurde.
        """
        original_timeout = self.ser.timeout
        self.ser.timeout = timeout
        try:
            while True:
                tag = self.ser.read(1)
                if not tag:
                    return None
                if tag[0] != 0xB8:
                    continue

                length_byte = self.ser.read(1)
                if not length_byte:
                    return None
                length = length_byte[0]

                payload = self.ser.read(length)
                if len(payload) < length:
                    return None

                end_tag = self.ser.read(1)
                if not end_tag or end_tag[0] != 0xB8:
                    continue  # kein gültiger Frame, weiter nach dem naechsten Tag suchen

                freq_id = int.from_bytes(payload[0:2], "big")
                real = struct.unpack(">f", payload[2:6])[0]
                imag = struct.unpack(">f", payload[6:10])[0]
                timestamp = int.from_bytes(payload[10:length], "big") if length > 10 else None

                return {"freq_id": freq_id, "real": real, "imag": imag, "timestamp": timestamp}
        finally:
            self.ser.timeout = original_timeout

            