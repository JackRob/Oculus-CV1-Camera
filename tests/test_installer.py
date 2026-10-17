"""Synthetic images and mocks ONLY. These tests must never open a USB device."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cv1camera import installer, profile, transport


def fixture():
    original = bytearray(b"\xff" * profile.SIZE)
    original[0xDA2D:0xDA2F] = bytes.fromhex("e0ff")
    original[0x10187] = 255
    original[0x12DEC] = 1
    original[0x13CC4:0x13CC6] = (224).to_bytes(2, "big")
    original[0x18000:0x18020] = bytes(range(32))  # synthetic per-device identity
    original[0x1D000:0x1E000] = bytes(range(256)) * 16  # synthetic calibration
    original[0xFFEE:0xFFF0] = b"\x55\xaa"
    original[0xFFEC:0xFFEE] = profile.crc16(original[0x6000:0xFFE8]).to_bytes(2, "big")
    target = bytearray(original)
    target[0xDA2D:0xDA2F] = bytes.fromhex("7f02")
    target[0x10187] = 14
    target[0x12DEC] = 8
    target[0x13CC4:0x13CC6] = (700).to_bytes(2, "big")
    target[0xFFEC:0xFFEE] = profile.crc16(target[0x6000:0xFFE8]).to_bytes(2, "big")
    original, target = bytes(original), bytes(target)
    offsets = (0xDA2D, 0xFFEC, 0x10187, 0x12DEC, 0x13CC4)
    sizes = (2, 2, 1, 1, 2)
    data = {"edits": [{"offset": a, "before": original[a:a+n].hex(), "after": target[a:a+n].hex()}
                       for a, n in zip(offsets, sizes)],
            "fingerprints": [{"name": str(a), "start": a, "end": b,
                              "before": profile.sha(original[a:b]), "after": profile.sha(target[a:b])}
                             for a, b in ((0, 0x6000), (0x6000, 0x10000))]}
    return original, target, data


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.original, self.target, self.data = fixture()
        self.loader = mock.patch.object(profile, "load_profile", return_value=self.data)
        self.loader.start()
        self.addCleanup(self.loader.stop)

    def test_matches_expected_patch_and_preserves_identity_calibration(self):
        result = profile.patch(self.original)
        self.assertEqual(result, self.target)
        self.assertEqual(result[:0x6000], self.original[:0x6000])
        self.assertEqual(result[0x15000:], self.original[0x15000:])

    def test_different_synthetic_identity_and_calibration_preserved(self):
        other = bytearray(self.original)
        other[0x18000:0x19000] = b"\x31" * 4096
        other[0x1D000:0x1E000] = b"\x72" * 4096
        self.assertEqual(profile.patch(bytes(other))[0x15000:], other[0x15000:])

    def test_unknown_code_refused(self):
        image = bytearray(self.original)
        image[0x8000] ^= 1
        with self.assertRaises(profile.Refused):
            profile.patch(bytes(image))

    def test_wrong_edit_preimage_refused(self):
        image = bytearray(self.original)
        image[0x10187] = 0
        with self.assertRaises(profile.Refused):
            profile.patch(bytes(image))

    def test_repeat_install_refused(self):
        with self.assertRaises(profile.Refused):
            profile.patch(self.target)

    def test_truncated_image_refused(self):
        with self.assertRaises(profile.Refused):
            profile.patch(self.original[:-1])

    def test_patch_cannot_write_boot_even_with_modified_profile(self):
        self.data["edits"].append({"offset": 0, "before": "ff", "after": "00"})
        with self.assertRaises(profile.Refused):
            profile.patch(self.original)

    def test_allowed_journal_marker_pair(self):
        actual = bytearray(self.target)
        actual[0x1F100] = 0x55
        actual[0x1F1FE] = 0xAA
        profile.verify_image(bytes(actual), self.target)

    def test_unpaired_or_unexpected_journal_change_refused(self):
        for address, value in ((0x1F100, 0x55), (0x1F010, 0), (0x1F1FE, 0)):
            with self.subTest(address=address, value=value):
                actual = bytearray(self.target)
                actual[address] = value
                with self.assertRaises(profile.Refused):
                    profile.verify_image(bytes(actual), self.target)

    def test_nonjournal_change_refused(self):
        actual = bytearray(self.target)
        actual[0x1D000] ^= 1
        with self.assertRaises(profile.Refused):
            profile.verify_image(bytes(actual), self.target)

    def test_crc_reference(self):
        self.assertEqual(profile.crc16(b"123456789"), 0x4B37)


class BoundsTests(unittest.TestCase):
    def test_readonly_transport_cannot_erase_or_program(self):
        camera = mock.Mock()
        spi = transport.SPI(camera)
        with self.assertRaises(profile.Refused):
            spi._send(0x20, 0xD000)
        camera.assert_not_called()
        camera.reg_write.assert_not_called()

    def test_code_spi_rejects_prohibited_sectors(self):
        for sector in (0, 0x3000, 0x10000, 0x1D000):
            with self.assertRaises(profile.Refused):
                transport.SPI(mock.Mock(), write_sector=sector)

    def test_code_spi_rejects_unaligned_or_outside_program(self):
        camera = mock.Mock()
        spi = transport.SPI(camera, write_sector=0xD000)
        for address in (0, 0xD001, 0xE000, 0x1D000):
            with self.assertRaises(profile.Refused):
                spi._send(2, address, b"\0" * 32)
        camera.reg_write.assert_not_called()

    def test_config_writer_rejects_code_or_calibration(self):
        camera = transport.Camera(mock.Mock())
        for address in (0xD000, 0x10001, 0x1D000):
            with self.assertRaises(profile.Refused):
                camera.config_blocks(b"\xff" * profile.SIZE, [address])
        camera.handle.controlWrite.assert_not_called()

    def test_config_writer_rejects_boot_mode(self):
        camera = transport.Camera(mock.Mock(), boot=True)
        with self.assertRaises(profile.Refused):
            camera.config_blocks(b"\xff" * profile.SIZE, [0x10180])
        camera.handle.controlWrite.assert_not_called()


class MemoryCamera:
    def __init__(self, image):
        self.data = bytearray(image)
        self.handle = mock.Mock()
        self.handle.getSerialNumber.return_value = "SYNTHETIC-DEVICE-A"
        self.boot = False
        self.speed = 3
        self.writes = []
        self.fail_sector = None

    def image(self):
        return bytes(self.data)

    def config_blocks(self, image, blocks):
        self.writes.append((blocks[0] & ~4095))
        for address in blocks:
            self.data[address:address+32] = image[address:address+32]


class MemorySPI:
    def __init__(self, camera, write_sector=None):
        self.camera, self.sector = camera, write_sector

    def read(self, command, address=None, length=1):
        if command == 0x9F:
            return bytes.fromhex("c22011")
        if command == 5:
            return b"\0"
        raise AssertionError("Unexpected fake SPI operation")

    def array(self, start, length):
        return bytes(self.camera.data[start:start+length])

    def replace_sector(self, image):
        self.camera.writes.append(self.sector)
        if self.camera.fail_sector == self.sector:
            self.camera.data[self.sector:self.sector+4096] = b"\xff" * 4096
            raise TimeoutError("Synthetic interrupted sector write")
        self.camera.data[self.sector:self.sector+4096] = image[self.sector:self.sector+4096]


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.original, self.target, data = fixture()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        (self.folder / "original.bin").write_bytes(self.original)
        (self.folder / "original-confirmed.bin").write_bytes(self.original)
        installer.save_json(self.folder / "backup.json", {
            "schema": 1, "size": profile.SIZE, "usb_id": "2833:0211",
            "serial": "SYNTHETIC-DEVICE-A", "original_sha256": profile.sha(self.original)})
        self.camera = MemoryCamera(self.original)

        @contextlib.contextmanager
        def fake_device(boot=False):
            self.camera.boot = boot
            yield self.camera

        patches = (mock.patch.object(profile, "load_profile", return_value=data),
                   mock.patch.object(installer, "SPI", MemorySPI),
                   mock.patch.object(installer, "device", fake_device),
                   mock.patch.object(installer, "confirm"),
                   mock.patch.object(installer, "power_cycle"),
                   mock.patch("sys.stdout", new_callable=io.StringIO))
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def journal(self):
        return json.loads((self.folder / "operation.json").read_text(encoding="utf-8"))

    def test_install_write_order_and_exact_final_image(self):
        installer.install(self.folder)
        self.assertEqual(self.camera.writes, [0x13000, 0x12000, 0x10000, 0xD000, 0xF000])
        self.assertEqual(bytes(self.camera.data), self.target)
        self.assertEqual(self.journal()["state"], "written_verified_awaiting_power_cycle")

    def test_failed_write_is_journaled_and_never_automatically_retried(self):
        self.camera.fail_sector = 0xD000
        with self.assertRaises(TimeoutError):
            installer.install(self.folder)
        self.assertTrue(self.journal()["application_write_started"])
        self.assertEqual(self.journal()["started_sectors"][-1], 0xD000)
        self.assertNotIn(0xF000, self.camera.writes)
        count = len(self.camera.writes)
        with self.assertRaises(profile.Refused):
            installer.install(self.folder)
        self.assertEqual(len(self.camera.writes), count)

    def test_explicit_restore_can_restore_interrupted_application_sector(self):
        self.camera.fail_sector = 0xD000
        with self.assertRaises(TimeoutError):
            installer.install(self.folder)
        self.camera.fail_sector = None
        installer.restore(self.folder)
        self.assertEqual(bytes(self.camera.data), self.original)
        self.assertEqual(self.journal()["state"], "stock_restored_readback_verified")

    def test_wrong_sensor_refused_before_writes(self):
        self.camera.handle.getSerialNumber.return_value = "SYNTHETIC-DEVICE-B"
        with self.assertRaises(profile.Refused):
            installer.install(self.folder)
        self.assertEqual(self.camera.writes, [])

    def test_calibration_mismatch_refused_before_writes(self):
        self.camera.data[0x1D000] ^= 1
        with self.assertRaises(profile.Refused):
            installer.install(self.folder)
        self.assertEqual(self.camera.writes, [])

    def test_corrupt_backup_refused_before_usb(self):
        (self.folder / "original.bin").write_bytes(b"bad")
        with self.assertRaises(profile.Refused):
            installer.install(self.folder)
        self.assertEqual(self.camera.writes, [])

    def test_second_backup_must_match(self):
        (self.folder / "original-confirmed.bin").write_bytes(b"bad")
        with self.assertRaises(profile.Refused):
            installer.load_backup(self.folder)

    def test_restore_refuses_unrelated_config_damage(self):
        installer.install(self.folder)
        self.camera.writes.clear()
        self.camera.data[0x10000] ^= 1
        with self.assertRaises(profile.Refused):
            installer.restore(self.folder)
        self.assertEqual(self.camera.writes, [])

    def test_restore_refuses_boot_damage(self):
        installer.install(self.folder)
        self.camera.writes.clear()
        self.camera.data[0] ^= 1
        with self.assertRaises(profile.Refused):
            installer.restore(self.folder)
        self.assertEqual(self.camera.writes, [])

    def test_fallback_requires_application_write_journal(self):
        installer.save_json(self.folder / "operation.json", {
            "original_sha256": profile.sha(self.original), "application_write_started": False})
        with self.assertRaises(profile.Refused):
            installer.recover_application(self.folder)
        self.assertEqual(self.camera.writes, [])

    def test_fallback_restores_main_but_leaves_configuration_for_normal_restore(self):
        self.camera.fail_sector = 0xD000
        with self.assertRaises(TimeoutError):
            installer.install(self.folder)
        self.camera.fail_sector = None
        installer.recover_application(self.folder)
        self.assertEqual(self.camera.data[:0x10000], self.original[:0x10000])
        self.assertNotEqual(self.camera.data[0x10000:0x14000], self.original[0x10000:0x14000])
        self.assertEqual(self.journal()["state"], "application_recovered_configuration_restore_still_required")


if __name__ == "__main__":
    unittest.main()
