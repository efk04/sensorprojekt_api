import serial
from config.config_transmitter import ISX3Transmitter
from config.config_handler import ISX3ConfigParser

parser = ISX3ConfigParser('config.ini')
config = parser.parse()

com_port = config.connection.port
baud = config.connection.baudrate

print(f"Verbinde zu {com_port} mit {baud} Baud...")
    
try:
    # Pyserial Instanz öffnen (Timeout ist wichtig für das Lesen der ACKs!)
    with serial.Serial(port=com_port, baudrate=baud, timeout=2.0) as ser:
            
        # Transmitter initialisieren
        transmitter = ISX3Transmitter(ser)
            
        # Kompletten Parametersatz übertragen
        transmitter.apply_config(config)
            
        # Messung starten (Nutzt den Wert "number_of_spectra" aus der Config)
        # transmitter.start_measurement(config.measurement.number_of_spectra)
            
except serial.SerialException as e:
    print(f"Serieller Fehler: Konnte Port {com_port} nicht öffnen. ({e})")
except Exception as e:
    print(f"Fehler bei der Kommunikation: {e}")