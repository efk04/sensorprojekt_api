def stringarray_to_intarray(string_array):
    """Konvertiert ein Array von Strings in ein Array von Ganzzahlen."""
    int_array = []
    for string in string_array:
        try:
            # Versuche, den String in eine Ganzzahl zu konvertieren
            int_value = int(string, 16)
            int_array.append(int_value)
        except ValueError:
            print(f"Ungültiger Hex-String: {string}")
            int_array.append(0)  # Füge einen Standardwert hinzu oder handle den Fehler anders
    return int_array


string_array = ["0x0", "0xff", "0x3C", "0x4D"]
int_array = stringarray_to_intarray(string_array)
print(string_array)  
print(int_array)     # Ausgabe: [0, 255, 60, 77]