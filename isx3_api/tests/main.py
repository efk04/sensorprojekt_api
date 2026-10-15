"""
main.py - Zentraler Einstiegspunkt für die Ausführung von ISX-3-Messungen.

Startet den Messablauf entweder mit einem per Kommandozeile übergebenen
Konfigurationspfad oder öffnet bei fehlendem Argument einen Dateidialog.
"""

import sys
from isx3_api import Measurement


def main() -> None:
    """Instanziiert den Controller und startet die Messung."""
    # Optionalen Konfigurationspfad aus den Startargumenten einlesen
    # Beispiel: python main.py config/meine_messung.ini
    config_file = sys.argv[1] if len(sys.argv) > 1 else None

    measurement_controller = Measurement()
    measurement_controller.measurement(config_path=config_file)


if __name__ == "__main__":
    main()