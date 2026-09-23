"""
Minimales Test-TUI für das ISX-3: Config hochladen, Messung mit oder ohne Live-Plot starten/stoppen.
Während einer laufenden Messung: Ctrl+C zum Stoppen.
"""
import sys
from pathlib import Path

MAIN_FOLDER = Path(__file__).resolve().parent.parent
if str(MAIN_FOLDER) not in sys.path:
    sys.path.append(str(MAIN_FOLDER))

import serial
import matplotlib.pyplot as plt

from zz_sonstige.config.config_handler import ISX3ConfigParser
from config.config_transmitter import ISX3Transmitter

CONFIG_PATH = "config/config.ini"


def load_config():
    return ISX3ConfigParser(CONFIG_PATH).parse()


def connect(config):
    print(f"Verbinde zu {config.connection.port} mit {config.connection.baudrate} Baud...")
    ser = serial.Serial(port=config.connection.port, baudrate=config.connection.baudrate, timeout=2.0)
    print("Verbunden.")
    return ISX3Transmitter(ser)


def run_measurement(config, transmitter, use_plot: bool):
    frequency_points = config.frequency_setup.count if config.frequency_setup.mode.lower() == "sweep" else 1
    spectra = config.measurement.number_of_spectra
    continuous = spectra == 0
    expected_results = None if continuous else spectra * frequency_points

    transmitter.start_measurement(spectra)

    fig = ax = real_line = imag_line = None
    if use_plot:
        plt.ion()
        fig, ax = plt.subplots()
        ax.set_xlabel("Sample")
        ax.set_ylabel("Impedanz [Ohm]")
        real_line, = ax.plot([], [], label="Real")
        imag_line, = ax.plot([], [], label="Imag")
        ax.legend()
        plt.show()

    samples, real_vals, imag_vals = [], [], []
    count = 0

    print("Messung läuft. Ctrl+C zum Stoppen.")
    stopped_early = False
    try:
        while continuous or count < expected_results:
            if use_plot and not plt.fignum_exists(fig.number):
                print("Plot-Fenster geschlossen, breche Messung ab.")
                stopped_early = True
                break

            frame = transmitter.read_measurement_frame(timeout=1.0)
            if frame is None:
                if use_plot:
                    plt.pause(0.01)  # Fenster reaktiv halten, während auf Daten gewartet wird
                continue

            count += 1
            print(f"#{count} freq_id={frame['freq_id']} real={frame['real']:.4f} imag={frame['imag']:.4f}")

            if use_plot:
                samples.append(count)
                real_vals.append(frame["real"])
                imag_vals.append(frame["imag"])

                real_line.set_data(samples, real_vals)
                imag_line.set_data(samples, imag_vals)
                ax.relim()
                ax.autoscale_view()
                plt.pause(0.001)
    except KeyboardInterrupt:
        print("\nAbbruch angefordert.")
        stopped_early = True
    finally:
        # Kontinuierliche Messungen laufen immer weiter, bis das Gerät den Stop-Befehl bekommt;
        # bei einer festen Anzahl Spektren ist ein Stop nur nötig, falls wir vorzeitig abgebrochen haben.
        if continuous or stopped_early:
            try:
                transmitter.stop_measurement()
            except Exception as e:
                print(f"Warnung: Stop-Befehl konnte nicht bestätigt werden: {e}")
        print(f"Messung beendet. {count} Werte empfangen.")
        if use_plot:
            plt.ioff()


MENU = """
=== ISX-3 Test-TUI ===
[1] Verbinden
[2] Config zum Gerät hochladen
[3] Messung starten (Live-Plot, Ctrl+C zum Stoppen)
[4] Messung starten (nur Konsole, Ctrl+C zum Stoppen)
[5] Messung manuell stoppen
[6] Software-Reset (Gerät aus hängendem Zustand zurücksetzen)
[7] Beenden
"""


def main():
    transmitter = None

    while True:
        print(MENU)
        choice = input("Auswahl: ").strip()

        if choice == "1":
            try:
                config = load_config()
                transmitter = connect(config)
            except (serial.SerialException, FileNotFoundError) as e:
                print(f"Verbindung fehlgeschlagen: {e}")

        elif choice == "2":
            if transmitter is None:
                print("Bitte zuerst verbinden (Option 1).")
                continue
            transmitter.apply_config(load_config())

        elif choice == "3":
            if transmitter is None:
                print("Bitte zuerst verbinden (Option 1).")
                continue
            run_measurement(load_config(), transmitter, use_plot=True)

        elif choice == "4":
            if transmitter is None:
                print("Bitte zuerst verbinden (Option 1).")
                continue
            run_measurement(load_config(), transmitter, use_plot=False)

        elif choice == "5":
            if transmitter is None:
                print("Bitte zuerst verbinden (Option 1).")
                continue
            try:
                transmitter.stop_measurement()
            except Exception as e:
                print(f"Stop-Befehl fehlgeschlagen: {e}")

        elif choice == "6":
            if transmitter is None:
                print("Bitte zuerst verbinden (Option 1).")
                continue
            try:
                transmitter.software_reset()
            except Exception as e:
                print(f"Reset fehlgeschlagen: {e}")

        elif choice == "7":
            print("Beende TUI.")
            break

        else:
            print("Ungültige Auswahl.")


if __name__ == "__main__":
    main()
