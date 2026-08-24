import struct
import serial
import time

class ISX3Transmitter:
    """
    Klasse zur Übertragung der Konfiguration an das Sciospec ISX-3 / ISX-3mini Messgerät.
    Erfordert ein ISX3DeviceConfig Objekt (aus dem Config-Parser).
    """

    # Bekannte System-Nachrichten (ACK/NACK)
    ACK_TAG = 0x18
    ACK_SUCCESS = 0x83
    NACK_SYNTAX = 0x81
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
        
        # Senden
        self.ser.write(frame)
        self.ser.flush()

        # Auf Bestätigung (ACK) warten
        self._wait_for_ack(cmd_tag)

    def _wait_for_ack(self, original_cmd_tag: int):
        """
        Liest den Rückgabe-Frame und prüft auf erfolgreiches Acknowledge.
        Ein ACK-Frame sieht so aus: 0x18 0x01 [Status] 0x18[cite: 2]
        """
        # Wir erwarten 4 Bytes für das ACK
        ack_frame = self.ser.read(4)
        
        if len(ack_frame) < 4:
            raise TimeoutError(f"Timeout beim Warten auf ACK für Befehl {hex(original_cmd_tag)}")

        if ack_frame[0] != self.ACK_TAG or ack_frame[3] != self.ACK_TAG:
            raise ConnectionError(f"Ungültiger ACK-Frame empfangen: {ack_frame.hex()}")

        status = ack_frame[2]
        if status == self.ACK_SUCCESS:
            return  # Alles in Ordnung[cite: 2]
        elif status == self.NACK_SYNTAX:
            raise ValueError(f"NACK (0x81): Falsche Syntax für Befehl {hex(original_cmd_tag)}[cite: 2]")
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
        print("Übertrage Extension Port-Settings...")
        ext_payload = struct.pack('>BBBB',
                                  config.extension_port.counter_port,
                                  config.extension_port.reference_port,
                                  config.extension_port.working_sense_port,
                                  config.extension_port.working_port)
        self._send_command(0xB2, ext_payload) #[cite: 2]

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