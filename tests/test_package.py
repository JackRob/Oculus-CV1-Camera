"""Check the distribution boundary without using real sensor data."""

import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from tools import build_release


class PackageTests(unittest.TestCase):
    def test_allowlist_excludes_firmware_media_logs_and_git_history(self):
        files = build_release.source_files()
        self.assertTrue(files)
        for path in files:
            relative = path.relative_to(build_release.ROOT)
            self.assertNotIn(".git", relative.parts)
            self.assertNotIn("backups", relative.parts)
            self.assertNotIn("work", relative.parts)
            self.assertNotIn(path.suffix, (".bin", ".mp4", ".png", ".jpg", ".log", ".whl"))

    def test_privacy_scanner_rejects_personal_paths_serials_emails_credentials(self):
        values = (
            "C:" + chr(92) + "Users" + chr(92) + "example" + chr(92) + "private",
            "/home/" + "example" + "/private",
            "WMT" + "D123456789012",
            "private" + "@" + "example.invalid",
            "ghp_" + "x" * 25,
            "-----BEGIN " + "PRIVATE KEY-----",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "README.md"
            with mock.patch.object(build_release, "ROOT", root):
                for text in values:
                    with self.subTest(kind=text[:5]):
                        path.write_text(text, encoding="utf-8")
                        with self.assertRaises(ValueError):
                            build_release.check_privacy([path])

    def test_current_source_passes_privacy_scan(self):
        build_release.check_privacy(build_release.source_files())

    def test_profile_contains_only_narrow_patch_not_firmware(self):
        path = build_release.ROOT / "cv1camera" / "profile.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        changes = data["edits"]
        addresses = set()
        for edit in changes:
            before, after = bytes.fromhex(edit["before"]), bytes.fromhex(edit["after"])
            self.assertEqual(len(before), len(after))
            self.assertLess(len(before), 32)
            for address in range(edit["offset"], edit["offset"] + len(before)):
                self.assertNotIn(address, addresses)
                self.assertIn(address & ~4095, (0xD000, 0xF000, 0x10000, 0x12000, 0x13000))
                addresses.add(address)
        self.assertEqual(len(addresses), 98)
        self.assertEqual(data["changed_bytes"], 98)
        self.assertEqual(set(data), {"id", "flash_size", "jedec_id", "changed_bytes", "fingerprints", "edits"})

    def test_zip_deterministic_and_contains_only_allowlisted_source(self):
        files = build_release.source_files()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for source in files:
                target = root / source.relative_to(build_release.ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            with mock.patch.object(build_release, "ROOT", root), contextlib.redirect_stdout(io.StringIO()):
                build_release.main()
                path = next((root / "dist").glob("*.zip"))
                first = path.read_bytes()
                build_release.main()
                self.assertEqual(path.read_bytes(), first)
                with zipfile.ZipFile(path) as bundle:
                    self.assertEqual(len(bundle.namelist()), len(files))
                    self.assertIsNone(bundle.testzip())
                    command = bundle.read("Oculus-CV1-Camera-0.1.0/Install.cmd")
                    self.assertIn(b"\r\n", command)
                    self.assertNotIn(b"\r\r\n", command)


if __name__ == "__main__":
    unittest.main()
