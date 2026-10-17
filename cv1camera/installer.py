"""Backup-first installation and explicit restoration. No automatic retries.

SPDX-License-Identifier: LGPL-2.1-or-later
"""

import datetime
import json
import os
import time
import uuid
from pathlib import Path

from .profile import (CODE_SECTORS, CONFIG_SECTORS, SIZE, changed_blocks, hs_config,
                      patch, require, sha, validate_image, verify_image)
from .transport import NORMAL, SPI, device, inventory

WARNING = "This can and will brick your Sensor. Proceed only if you accept permanently losing it."
ACKNOWLEDGEMENT = "I ACCEPT THE BRICKING RISK"


def private_root():
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / ".local" / "share") / "OculusCV1Camera"


def write_new(path, data):
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def save_json(path, data):
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def confirm():
    print("\nDANGER: " + WARNING)
    print("Recovery is not guaranteed. A backup cannot repair a sensor that no longer responds over USB.")
    require(input(f'Type {ACKNOWLEDGEMENT} to allow flash writes: ').strip() == ACKNOWLEDGEMENT,
            "Cancelled. No flash write was authorized.")


def identify(camera, original=None, serial=None):
    spi = SPI(camera)
    require(spi.read(0x9F, length=3) == bytes.fromhex("c22011"), "Unsupported flash JEDEC ID.")
    require(spi.read(5)[0] & 0x3F == 0, "Flash is busy or protected.")
    if original is not None:
        require(spi.array(0, 0x6000) == original[:0x6000], "Boot copies differ from this backup.")
        require(spi.array(0x1D000, 4096) == original[0x1D000:0x1E000],
                "Calibration differs. NEVER restore another sensor's backup.")
    if not camera.boot:
        current_serial = camera.handle.getSerialNumber()
        require(bool(current_serial), "Missing sensor serial; refusing to associate a backup.")
        if serial is not None:
            require(current_serial == serial, "Backup belongs to a different sensor.")
        return current_serial


def backup():
    with device() as camera:
        serial = identify(camera)
        print("Reading two independent backups; do not unplug the sensor.", flush=True)
        first, second = camera.image(), camera.image()
        require(first == second, "Backup reads differ; nothing will be written.")
        folder = private_root() / "backups" / (
            datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
        folder.mkdir(parents=True, exist_ok=False)
        write_new(folder / "original.bin", first)
        write_new(folder / "original-confirmed.bin", second)
        manifest = {"schema": 1, "original_sha256": sha(first), "serial": serial,
                    "usb_id": "2833:0211", "size": SIZE,
                    "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        save_json(folder / "backup.json", manifest)
        # Keep the backup even when a later compatibility/physical check refuses installation.
        print(f"PRIVATE backup saved: {folder}\nDo not upload this folder.", flush=True)
        validate_image(first)
        for start, length in ((0, 0x6000), (0x1D000, 4096)):
            require(SPI(camera).array(start, length) == first[start:start + length],
                    "Physical boot/calibration read differs from backup.")
        for sector in CODE_SECTORS + CONFIG_SECTORS:
            print(f"Checking physical flash sector 0x{sector:05x}", flush=True)
            require(SPI(camera).array(sector, 4096) == first[sector:sector + 4096],
                    "Physical flash differs from backup; no writes permitted.")
    print("Backup and supported stock firmware verified. Copy this PRIVATE folder to another disk.")
    return folder


def load_backup(folder):
    folder = Path(folder).resolve()
    manifest = json.loads((folder / "backup.json").read_text(encoding="utf-8"))
    original = (folder / "original.bin").read_bytes()
    require(manifest.get("schema") == 1 and manifest.get("size") == SIZE, "Unsupported backup manifest.")
    require(manifest.get("usb_id") == "2833:0211" and bool(manifest.get("serial")), "Invalid backup identity.")
    require(sha(original) == manifest["original_sha256"], "Backup checksum failed.")
    require((folder / "original-confirmed.bin").read_bytes() == original, "Second backup differs.")
    validate_image(original)
    return folder, manifest, original, patch(original)


def audit(camera, expected):
    verify_image(camera.image(), expected)
    for sector in CODE_SECTORS + CONFIG_SECTORS:
        print(f"Physical verification: 0x{sector:05x}", flush=True)
        require(SPI(camera).array(sector, 4096) == expected[sector:sector + 4096],
                f"Physical flash mismatch at sector 0x{sector:05x}.")
    require(SPI(camera).array(0, 0x6000) == expected[:0x6000], "Physical boot copies differ.")
    require(SPI(camera).array(0x1D000, 4096) == expected[0x1D000:0x1E000], "Physical calibration differs.")


def journal_path(folder):
    return folder / "operation.json"


def install(folder):
    folder, manifest, original, target = load_backup(folder)
    path = journal_path(folder)
    require(not path.exists(), "An operation already exists for this backup. Use verify or explicit restore.")
    blocks = changed_blocks(original, target)
    print(f"Plan: {sum(x != y for x, y in zip(original, target))} byte changes in {len(blocks)} blocks.")
    print("Boot copies, device identity and calibration are preserved. USB runs at High-Speed (USB 2).")
    confirm()
    journal = {"operation": "install", "original_sha256": sha(original), "target_sha256": sha(target),
               "state": "preflight", "started_sectors": [], "verified_sectors": [],
               "application_write_started": False}
    save_json(path, journal)
    try:
        with device() as camera:
            identify(camera, original, manifest["serial"])
            verify_image(camera.image(), original)
            # Inspect all sectors BEFORE the first write, including ones that were previously backed up.
            for sector in CODE_SECTORS + CONFIG_SECTORS:
                require(SPI(camera).array(sector, 4096) == original[sector:sector + 4096],
                        "Sensor changed since backup; refusing installation.")
            for sector in (0x13000, 0x12000, 0x10000, 0xD000, 0xF000):
                journal["state"] = "writing"
                journal["started_sectors"].append(sector)
                if sector in CODE_SECTORS:
                    journal["application_write_started"] = True
                save_json(path, journal)  # durable intent BEFORE erase/program
                print(f"Writing sector 0x{sector:05x}; DO NOT disconnect or close this window.", flush=True)
                if sector in CONFIG_SECTORS:
                    camera.config_blocks(target, [a for a in blocks if (a & ~4095) == sector])
                else:
                    SPI(camera, write_sector=sector).replace_sector(target)
                journal["verified_sectors"].append(sector)
                save_json(path, journal)
            audit(camera, target)
        journal["state"] = "written_verified_awaiting_power_cycle"
        save_json(path, journal)
    except BaseException:
        journal["state"] = "interrupted_or_failed_do_not_retry_install"
        save_json(path, journal)
        print("STOP: installation did not complete. Keep the backup. Follow docs/RECOVERY.md.")
        raise
    power_cycle(folder)


def power_cycle(folder):
    print("\nFlash readback passed. Unplug the sensor for FIVE seconds, then reconnect it.")
    print("Leave webcam apps closed. Watching for disconnect/reconnect for up to five minutes.", flush=True)
    absent = False
    end = time.monotonic() + 300
    while time.monotonic() < end:
        connected = inventory()
        if not connected:
            absent = True
        if absent and connected:
            time.sleep(3)
            verify(folder, observed_power_cycle=True)
            return
        time.sleep(0.5)
    require(False, "Power-cycle observation timed out. Reconnect and run Verify; installation is not marked complete.")


def verify(folder, observed_power_cycle=False):
    folder, manifest, original, target = load_backup(folder)
    with device() as camera:
        identify(camera, original, manifest["serial"])
        require(camera.speed == 3, "Expected USB 2 High-Speed. Profile did not load at startup.")
        audit(camera, target)
        configuration = bytes(camera.handle.controlRead(0x80, 6, 0x200, 0, 324, timeout=5000))
        require(configuration == hs_config(target) and len(configuration) == 324,
                "Active native MJPEG configuration differs; power-cycle the sensor.")
        # GET_DEF UVC probe must use the corrected 60fps interval without a runtime initializer.
        probe = bytes(camera.handle.controlRead(0xA1, 0x87, 0x100, 1, 26, timeout=5000))
        require(len(probe) == 26 and int.from_bytes(probe[4:8], "little") == 166666,
                "Active frame negotiation did not load the corrected timing.")
    save_json(folder / "verification.json", {"profile_verified": True,
              "power_cycle_observed_this_run": observed_power_cycle, "native_mjpeg": True,
              "usb2_high_speed": True, "capture_test": "Open a webcam app to confirm live video.",
              "verified_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    path = journal_path(folder)
    if path.exists():
        journal = json.loads(path.read_text(encoding="utf-8"))
        journal["state"] = "profile_verified"
        journal["power_cycle_observed"] = observed_power_cycle or journal.get("power_cycle_observed", False)
        save_json(path, journal)
    print("\nNative MJPEG firmware, High-Speed USB and active descriptors VERIFIED.")
    print("Close this installer. Select 'CV1 External Camera' in Windows Camera or your webcam app.")
    print("Check a live picture. A dark room needs IR illumination; the image is monochrome.")


def restore(folder):
    folder, manifest, original, target = load_backup(folder)
    blocks = changed_blocks(original, target)
    journal_file = journal_path(folder)
    previous = json.loads(journal_file.read_text(encoding="utf-8")) if journal_file.exists() else {}
    confirm()
    with device() as camera:
        identify(camera, original, manifest["serial"])
        current = camera.image()
        # A journal from THIS backup permits resuming partial sector writes, not arbitrary firmware.
        require(previous.get("original_sha256") == sha(original), "Missing matching installation journal.")
        permitted = set()
        for sector in previous.get("started_sectors", []):
            require(sector in CODE_SECTORS + CONFIG_SECTORS, "Invalid operation journal sector.")
            permitted.update(range(sector, sector + 4096))
        require(all(x == y or i in permitted for i, (x, y) in enumerate(zip(current[:0x1F000], original))),
                "Unexpected changes outside this installation's sectors; refusing restore.")
        # Config-sector erase interruption is not repaired by blindly overwriting a few blocks.
        config_bytes = {a + n for a in blocks if (a & ~4095) in CONFIG_SECTORS for n in range(32)}
        require(all(current[i] == original[i] for sector in CONFIG_SECTORS
                    for i in range(sector, sector + 4096) if i not in config_bytes),
                "Configuration damaged beyond patch blocks. USB restore is insufficient; see recovery docs.")
        previous["state"] = "restoring"
        save_json(journal_file, previous)
        try:
            for sector in CODE_SECTORS:
                SPI(camera, write_sector=sector).replace_sector(original)
            for sector in (0x13000, 0x12000, 0x10000):
                selected = [a for a in blocks if (a & ~4095) == sector
                            and current[a:a + 32] != original[a:a + 32]]
                if selected:
                    camera.config_blocks(original, selected)
            audit(camera, original)
        except BaseException:
            previous["state"] = "restore_failed"
            save_json(journal_file, previous)
            raise
    previous["state"] = "stock_restored_readback_verified"
    save_json(journal_file, previous)
    print("Original firmware restored and readback verified. Unplug for five seconds and reconnect.")
    print("Stock Oculus firmware does not provide this project's conventional native webcam profile.")


def recover_application(folder):
    folder, manifest, original, target = load_backup(folder)
    journal_file = journal_path(folder)
    journal = json.loads(journal_file.read_text(encoding="utf-8"))
    require(journal.get("original_sha256") == sha(original) and journal.get("application_write_started"),
            "No matching journal of application writes. Do not force recovery.")
    print("Bootloader recovery restores ONLY application sectors D000/F000. It does not repair configuration.")
    confirm()
    with device(boot=True) as camera:
        identify(camera, original)
        spi = SPI(camera)
        for start, length in ((0x6000, 0x7000), (0xE000, 0x1000)):
            require(spi.array(start, length) == original[start:start + length],
                    "Unexpected application changes outside the authorized recovery sectors.")
        journal["state"] = "recovering_application"
        save_json(journal_file, journal)
        for sector in CODE_SECTORS:
            SPI(camera, write_sector=sector).replace_sector(original)
        require(spi.array(0, 0x10000) == original[:0x10000], "Full boot/main recovery verification failed.")
        require(spi.array(0x1D000, 4096) == original[0x1D000:0x1E000], "Calibration mismatch after recovery.")
    journal["state"] = "application_recovered_configuration_restore_still_required"
    save_json(journal_file, journal)
    print("Original boot/main physically verified. Unplug for five seconds, reconnect, then run Restore.")
