"""
unet_test_off.py (test_isx3_api.py) - Automated offline unit tests for the Sciospec ISX-3 API framework.

Tests without real hardware (via mocking):
1. SI prefix and configuration parsing (config_handler.py)
2. MUX pin routing for 4-wire, 2-wire, custom pins, and the register-ganging placeholder (commands.py & measurement.py)
3. Binary protocol: 15-byte Medical vs. 4-byte Standard, amplitude halving, frame parser (commands.py)
4. HDF5 file creation and measurement data persistence (measurement.py)
"""

import os
import sys
import struct
import tempfile
import shutil
import unittest
from unittest.mock import MagicMock, patch
import h5py
import matplotlib.pyplot as plt

# Add the src directory to sys.path so isx3_api can be imported directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from isx3_api.config_handler import (
    parse_value_with_prefix,
    parse_frequency_input,
    parse_precision_input,
    ConfigBuilder,
)
from isx3_api.commands import ISX3
from isx3_api.measurement import Measurement, parse_mux_sensor_expression


class TestConfigHandler(unittest.TestCase):
    """1. Tests unit conversion, SI prefixes, and measurement queue generation."""

    def test_parse_value_with_prefix(self):
        self.assertAlmostEqual(parse_value_with_prefix("100u"), 1e-4)
        self.assertAlmostEqual(parse_value_with_prefix("100uA"), 1e-4)
        self.assertAlmostEqual(parse_value_with_prefix("100mVpp"), 0.1)
        self.assertAlmostEqual(parse_value_with_prefix("2,5k"), 2500.0)
        self.assertAlmostEqual(parse_value_with_prefix(0.05), 0.05)

    def test_parse_frequency_input(self):
        self.assertAlmostEqual(parse_frequency_input("1k"), 1000.0)
        self.assertAlmostEqual(parse_frequency_input("1.5MHz"), 1.5e6)
        self.assertAlmostEqual(parse_frequency_input("500Hz"), 500.0)
        self.assertAlmostEqual(parse_frequency_input("ungueltig"), 100.0)

    def test_parse_precision_input(self):
        self.assertAlmostEqual(parse_precision_input("low"), 0.0)
        self.assertAlmostEqual(parse_precision_input("1 (medium - default)"), 1.0)
        self.assertAlmostEqual(parse_precision_input("very high"), 3.0)
        self.assertAlmostEqual(parse_precision_input(15.0), 10.0)

    def test_generate_measurement_queue(self):
        """Creates a temporary INI file and verifies the generated measurement queue."""
        temp_dir = tempfile.mkdtemp()
        ini_path = os.path.join(temp_dir, "test_config.ini")
        try:
            with open(ini_path, "w", encoding="utf-8") as f:
                f.write(
                    "[Connection]\ndevice_version = medical\nport = COM12\nbaudrate = 115200\n"
                    "[MUX]\nenabled = True\nmode = 4\nchannel = 3\nactive_sensors = 1-2\nswitch_delay_s = 0.05\n"
                    "[Frontend]\nmeasurement_mode = 2\nmeasurement_channel = 3\ncurrent_range = 2\nvoltage_range = 1\n"
                    "[FrequencyBlocks]\n"
                    "block_1_start = 100\nblock_1_stop = 1000\nblock_1_steps = 4\n"
                    "block_1_scale = logarithmic\nblock_1_precision = 1.0\nblock_1_exc_type = 2\nblock_1_amplitude = 100u\n"
                )
            builder = ConfigBuilder(ini_path)
            queue = builder.generate_measurement_queue()
            self.assertEqual(len(queue), 4)
            self.assertEqual(queue[0]["device_version"], "medical")
            self.assertAlmostEqual(queue[0]["frequency"], 100.0)
            self.assertAlmostEqual(queue[-1]["frequency"], 1000.0)
            self.assertAlmostEqual(queue[0]["amplitude"], 0.0001)
        finally:
            shutil.rmtree(temp_dir)


class TestMUXRouting(unittest.TestCase):
    """2. Tests MUX pin calculation (4-wire, 2-wire, custom pins, and deactivated multi-pin placeholder)."""

    def setUp(self):
        self.isx = ISX3()

    def test_4_wire_auto_numbering(self):
        self.assertEqual(self.isx.route_mux_sensor(sensor_idx=1, wire_mode=4), (1, 2, 3, 4))
        self.assertEqual(self.isx.route_mux_sensor(sensor_idx=2, wire_mode=4), (5, 6, 7, 8))
        self.assertEqual(self.isx.route_mux_sensor(sensor_idx=3, wire_mode=4), (9, 10, 11, 12))

    def test_2_wire_auto_numbering(self):
        self.assertEqual(self.isx.route_mux_sensor(sensor_idx=1, wire_mode=2), (1, 1, 2, 2))
        self.assertEqual(self.isx.route_mux_sensor(sensor_idx=2, wire_mode=2), (3, 3, 4, 4))

    def test_custom_pins_override(self):
        custom = (2, 5, 8, 6)
        pins = self.isx.route_mux_sensor(sensor_idx=1, wire_mode=4, custom_pins=custom)
        self.assertEqual(pins, (2, 5, 8, 6))
        self.assertEqual(self.isx.active_mux_pins, (2, 5, 8, 6))

    def test_multi_pin_ganging_placeholder_blocked(self):
        """
        Verifies that multi-pin electrode ganging is blocked by default (raising NotImplementedError
        until the manufacturer releases the register programming firmware update).
        """
        expr = "1: CE:1,5,9, RE:2,6,10, WS:3,7,11, WE:4,8,12"
        with self.assertRaises(NotImplementedError):
            parse_mux_sensor_expression(expr)

        with self.assertRaises(NotImplementedError):
            self.isx.configure_multipin_registers([1, 5, 9], [2, 6, 10], [3, 7, 11], [4, 8, 12])

        # --- RETAINED LEGACY TEST FOR EXPERIMENTAL MULTI-PIN PARSING (INACTIVE BY DEFAULT) ---
        # with patch("isx3_api.measurement.ENABLE_EXPERIMENTAL_MULTIPIN_STACKING", True), \
        #      patch.object(ISX3, "ENABLE_EXPERIMENTAL_MULTIPIN_STACKING", True):
        #     sensors, pin_map = parse_mux_sensor_expression(expr)
        #     self.assertEqual(sensors, [1])
        #     self.assertEqual(pin_map[1], [(1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12)])

    def test_invalid_wire_mode_raises(self):
        with self.assertRaises(ValueError):
            self.isx.route_mux_sensor(sensor_idx=1, wire_mode=3)


class TestBinaryProtocol(unittest.TestCase):
    """3. Tests binary frame construction and parsing (Medical vs. Standard, amplitude halving, timestamps)."""

    def setUp(self):
        self.isx = ISX3()
        self.isx.device = MagicMock()
        self.isx.device.is_open = True
        self.isx.device.in_waiting = 0

    def _mock_ack_response(self):
        """Simulates a valid ACK frame (0x18 0x01 0x83 0x18) from the device."""
        self.isx.device.read.side_effect = [bytes([0x18]), bytes([0x01, 0x83, 0x18])]

    def test_send_command_framing_and_ack(self):
        self._mock_ack_response()
        self.isx._send_command(0xB6, bytes([0x01]))
        self.isx.device.write.assert_called_once_with(bytes([0xB6, 0x01, 0x01, 0xB6]))

    @patch("time.sleep", return_value=None)
    def test_frontend_routing_medical_vs_standard(self, _mock_sleep):
        # 1. Medical mode: 15-byte payload in 0xB0 (without 0xB2)
        self.isx.device_version = "medical"
        self.isx.route_mux_sensor(sensor_idx=1, wire_mode=4)

        sent_frames = []
        with patch.object(self.isx, "_send_command", side_effect=lambda tag, data, **kw: sent_frames.append((tag, data))):
            self.isx._apply_frontend_and_routing(
                measurement_mode=2, measurement_channel=3, current_range=2, voltage_range=1
            )

        self.assertEqual(sent_frames[0], (0xB0, bytes([0xFF, 0xFF, 0xFF])))
        self.assertEqual(sent_frames[1][0], 0xB0)
        self.assertEqual(len(sent_frames[1][1]), 15)

        # 2. Standard mode: 4-byte payload in 0xB0 + separate 0xB2 command
        self.isx.device_version = "standard"
        sent_frames.clear()
        with patch.object(self.isx, "_send_command", side_effect=lambda tag, data, **kw: sent_frames.append((tag, data))):
            self.isx._apply_frontend_and_routing(
                measurement_mode=2, measurement_channel=2, current_range=2, voltage_range=1
            )

        self.assertEqual(sent_frames[0], (0xB0, bytes([0xFF, 0xFF, 0xFF])))
        self.assertEqual(sent_frames[1], (0xB0, bytes([2, 2, 2, 1])))
        self.assertEqual(sent_frames[2], (0xB2, bytes([1, 2, 3, 4])))

    @patch("time.sleep", return_value=None)
    def test_multi_pin_stacking_blocked_by_default(self, _mock_sleep):
        """Verifies that passing a list of pin tuples raises NotImplementedError unless experimental flag is set."""
        self.isx.device_version = "medical"
        multi_tuples = [(1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12)]
        with self.assertRaises(NotImplementedError):
            self.isx.route_mux_sensor(sensor_idx=1, wire_mode=4, custom_pins=multi_tuples)

        # --- RETAINED LEGACY TEST FOR 0xB0 STACKING (INACTIVE BY DEFAULT) ---
        # with patch.object(self.isx, "ENABLE_EXPERIMENTAL_MULTIPIN_STACKING", True):
        #     self.isx.route_mux_sensor(sensor_idx=1, wire_mode=4, custom_pins=multi_tuples)
        #     sent_frames = []
        #     with patch.object(self.isx, "_send_command", side_effect=lambda tag, data, **kw: sent_frames.append((tag, data))):
        #         self.isx._apply_frontend_and_routing(2, 3, 2, 1)
        #     self.assertEqual(len(sent_frames), 4)

    @patch("time.sleep", return_value=None)
    def test_amplitude_halving_in_medical_mode(self, _mock_sleep):
        """Verifies that in Medical mode Peak-to-Peak (0.0002 App) is halved to Peak (0.0001 Ap)."""
        sent_frames = []
        with patch.object(self.isx, "_send_command", side_effect=lambda tag, data, **kw: sent_frames.append((tag, data))):
            setup = {
                "device_version": "medical",
                "measurement_mode": 2,
                "measurement_channel": 1,
                "current_range": 2,
                "voltage_range": 1,
                "frequency": 1000.0,
                "precision": 1.0,
                "amplitude": 0.0002,
                "excitation_type": 1,
                "point_delay_us": 0,
                "phase_sync": False,
            }
            self.isx.set_frequency_setup(setup)

        last_tag, last_payload = sent_frames[-1]
        self.assertEqual(last_tag, 0xB6)
        self.assertEqual(last_payload[0], 0x02)
        freq, prec, sent_amp = struct.unpack(">fff", last_payload[1:13])
        self.assertAlmostEqual(sent_amp, 0.0001, places=7)

    def test_read_measurement_data_with_5byte_us_timestamp_and_current_range(self):
        """Verifies error-free parsing of 5-byte microsecond timestamps and current range feedback."""
        freq_id_bytes = (1).to_bytes(2, byteorder="big")
        ts_5bytes = (123456789).to_bytes(5, byteorder="big")
        cr_1byte = bytes([0x02])
        real_bytes = struct.pack(">f", 2000.5)
        imag_bytes = struct.pack(">f", -15.25)

        payload = freq_id_bytes + ts_5bytes + cr_1byte + real_bytes + imag_bytes
        length = len(payload)

        self.isx.device.read.side_effect = [
            bytes([0xB8]),
            bytes([length]),
            payload,
            bytes([0xB8]),
        ]

        settings = {"timestamp_mode": 2, "enable_current_range_output": True}
        res = self.isx.read_measurement_data(spectra=1, timeout=2.0, measurement_settings=settings)

        self.assertEqual(res["id"], [1])
        self.assertEqual(res["timestamp"], [123456789])
        self.assertEqual(res["timestamp_unit"], ["us"])
        self.assertEqual(res["current_range"], [2])
        self.assertAlmostEqual(res["real"][0], 2000.5, places=3)
        self.assertAlmostEqual(res["imag"][0], -15.25, places=3)


class TestHDF5Storage(unittest.TestCase):
    """4. Tests saving configuration and measurement data in HDF5 format."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        plt.ioff()

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.temp_dir)

    def test_hdf5_creation_and_saving(self):
        meas = Measurement()
        h5_path = meas.create_h5_file(mode_prefix="UNITTEST")
        self.assertTrue(os.path.exists(h5_path))

        results_data = {
            "id": [1],
            "real": [1998.4],
            "imag": [-2.1],
            "timestamp": [5000],
            "timestamp_unit": ["ms"],
            "current_range": [2],
        }
        current_setup = {"id": 1, "frequency": 1000.0}

        meas.save_measurement(
            results_data=results_data,
            timestamp=1700000000.0,
            current_setup=current_setup,
            icm=1,
            sensor_idx=2,
        )

        with h5py.File(h5_path, "r") as h5f:
            grp_path = "Sensor_2/Measurement_1.1"
            self.assertIn(grp_path, h5f)
            grp = h5f[grp_path]
            self.assertAlmostEqual(float(grp["frequency"][()]), 1000.0)
            self.assertAlmostEqual(float(grp["real_part"][0]), 1998.4, places=2)
            self.assertAlmostEqual(float(grp["imaginary_part"][0]), -2.1, places=2)
            self.assertEqual(int(grp["hw_timestamp"][0]), 5000)
            self.assertEqual(int(grp["current_range"][0]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)