"""
test_dry_run.py - Validiert Konfiguration und MUX32-Pin-Routing.
"""

from isx3_api.commands import ISX3
from isx3_api.config_handler import ConfigBuilder


def test_dry_run():
    print("=== 1. Test: Konfiguration einlesen ===")
    config_file = "config/config.ini"
    builder = ConfigBuilder(config_file)
    queue = builder.generate_measurement_queue()
    print(f"[OK] Sweep generiert: {len(queue)} Frequenzpunkte pro Durchlauf.")

    # MUX-Konfiguration über has_section / get auslesen
    parser = builder.parser
    if hasattr(parser, "has_section") and parser.has_section("Mux"):
        mux_enabled = (
            parser.get("Mux", "enabled").strip().lower() in ("true", "1")
            if parser.has_option("Mux", "enabled")
            else False
        )
        mux_mode = (
            int(parser.get("Mux", "mode").strip())
            if parser.has_option("Mux", "mode")
            else 4
        )
        raw_sensors = (
            parser.get("Mux", "active_sensors").strip()
            if parser.has_option("Mux", "active_sensors")
            else "1"
        )
    else:
        mux_enabled, mux_mode, raw_sensors = False, 4, "1"

    print(f"[OK] MUX aktiviert: {mux_enabled}")
    print(f"[OK] MUX Modus:     {mux_mode}-Leiter")
    print(f"[OK] Sensor-Eintrag: '{raw_sensors}'")

    print("\n=== 2. Test: Pin-Routing-Logik (4-Leiter & 2-Leiter) ===")
    device = ISX3()
    # Dummy-Funktion fängt Befehle ab und gibt sie zur Kontrolle im Terminal aus
    device._send_command = lambda cmd, data: print(
        f"    -> ISX3 sendet CMD 0x{cmd:02X} mit Daten: {list(data)}"
    )

    print("\n[4-Leiter-Test für alle 8 Sensoren]:")
    for s in range(1, 9):
        ce, re, ws, we = device.route_mux_sensor(sensor_idx=s, wire_mode=4)
        assert (
            we == 4 * s and ce == 4 * s - 3
        ), f"Fehler bei Pin-Berechnung Sensor {s}"

    print("\n[2-Leiter-Test für Sensor 1 und 2]:")
    device.route_mux_sensor(sensor_idx=1, wire_mode=2)
    device.route_mux_sensor(sensor_idx=2, wire_mode=2)

    print("\n[OK] Alle MUX-Pin-Berechnungen sind fehlerfrei!")


if __name__ == "__main__":
    test_dry_run()