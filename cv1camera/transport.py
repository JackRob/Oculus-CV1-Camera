"""CV1 eSP770U USB/SPI transport, restricted to the tested flash operations.

Register and flash-read protocol adapted from ouvrt/src/esp770u.c:
Copyright 2017-2018 Philipp Zabel. SPDX-License-Identifier: LGPL-2.1-or-later
Python transport and constrained write implementation: 2026 project contributors.
"""

import contextlib
import ctypes
import os
import struct
import time
from pathlib import Path

from .profile import CODE_SECTORS, CONFIG_SECTORS, SIZE, require

NORMAL = (0x2833, 0x0211)
BOOT = (0x1E4E, 0x0668)
_dll_directory = None
_helper = None


@contextlib.contextmanager
def context():
    global _dll_directory, _helper
    require(os.name == "nt" and struct.calcsize("P") == 8,
            "Hardware installer requires 64-bit Windows and 64-bit Python.")
    import usb1
    import libusb_package

    directory = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "UsbDk Runtime Library"
    require((directory / "UsbDkHelper.dll").is_file(),
            "Install the official UsbDk x64 runtime first; see docs/INSTALL.md.")
    if _dll_directory is None:
        _dll_directory = os.add_dll_directory(str(directory))
        _helper = ctypes.WinDLL(str(directory / "UsbDkHelper.dll"))
        usb1.loadLibrary(ctypes.CDLL(str(libusb_package.get_library_path())))
    with usb1.USBContext() as ctx:
        # UsbDk must be selected AFTER Windows libusb initialization.
        option = usb1.libusb1.libusb.libusb_set_option
        option.restype = ctypes.c_int
        require(option(ctx._USBContext__context_p, 1) == 0, "Could not select the UsbDk backend.")
        yield ctx


def inventory():
    with context() as ctx:
        return [((d.getVendorID(), d.getProductID()), d.getDeviceSpeed())
                for d in ctx.getDeviceList() if (d.getVendorID(), d.getProductID()) in (NORMAL, BOOT)]


@contextlib.contextmanager
def device(boot=False):
    wanted = BOOT if boot else NORMAL
    with context() as ctx:
        devices = [d for d in ctx.getDeviceList() if (d.getVendorID(), d.getProductID()) in (NORMAL, BOOT)]
        require(len(devices) == 1 and (devices[0].getVendorID(), devices[0].getProductID()) == wanted,
                "Connect exactly ONE CV1 sensor in the required normal/bootloader mode.")
        with contextlib.closing(devices[0].open()) as handle:
            handle.claimInterface(0)
            try:
                yield Camera(handle, boot=boot, speed=devices[0].getDeviceSpeed())
            finally:
                handle.releaseInterface(0)


class Camera:
    def __init__(self, handle, boot=False, speed=None):
        self.handle, self.boot, self.speed = handle, boot, speed

    def read(self, selector, length):
        result = bytes(self.handle.controlRead(0xA1, 0x81, selector << 8, 4 << 8, length, timeout=5000))
        require(len(result) == length, "Short extension-unit reply.")
        return result

    def write(self, selector, data):
        count = self.handle.controlWrite(0x21, 1, selector << 8, 4 << 8, data, timeout=10000)
        require(count == len(data), "Short extension-unit write.")

    def reg_read(self, address):
        self.write(3, bytes((0x82, address >> 8, address & 255, 0)))
        reply = self.read(3, 4)
        require(reply[0] == 0x82 and reply[2] == 0, "Invalid register reply.")
        return reply[1]

    def reg_write(self, address, value):
        data = bytes((2, address >> 8, address & 255, value))
        self.write(3, data)
        require(self.read(3, 4) == data, "Register write echo mismatch.")

    def idle(self):
        if not self.boot:
            require(self.reg_read(0xC052) == 0, "Firmware flash cache busy; close camera apps.")
        require(not self.reg_read(0xF0A1) & 1, "SPI controller busy.")

    def flash_read(self, address, length):
        require(not self.boot and 0 <= address <= SIZE - length and 1 <= length <= 128,
                "Invalid normal-mode flash read.")
        counter = self.read(10, 1)
        packet = bytearray(16)
        packet[:4] = bytes((counter[0], 0x41, 3, 1))
        packet[5:8] = address.to_bytes(3, "big")
        packet[8:10] = length.to_bytes(2, "big")
        self.write(11, packet)
        result = self.read(12, length)
        self.write(10, counter)
        return result

    def image(self):
        require(not self.boot, "Normal flash-read protocol is unavailable in bootloader mode.")
        result = bytearray()
        for address in range(0, SIZE, 128):
            result += self.flash_read(address, 128)
            if address % 0x8000 == 0:
                print(f"Reading flash: {address * 100 // SIZE}%", flush=True)
        return bytes(result)

    def config_blocks(self, target, blocks):
        require(not self.boot and len(target) == SIZE, "Configuration writes require normal firmware.")
        require(blocks and len(set(blocks)) == len(blocks) and all(
            a % 32 == 0 and (a & ~4095) in CONFIG_SECTORS for a in blocks),
            "Configuration write outside allowlist.")
        counter = self.read(10, 1)
        try:
            for address in blocks:
                packet = bytearray(16)
                packet[:4] = bytes((counter[0], 0x81, 3, 1))
                packet[4:8] = address.to_bytes(4, "big")
                packet[8:10] = (32).to_bytes(2, "big")
                self.write(11, packet)
                self.write(12, target[address:address + 32])
            # Tested CV1 batch finalization, NOT the incompatible SDK completion command.
            finish = bytearray(16)
            finish[:3] = bytes((counter[0], 2, 1))
            self.write(11, finish)
        finally:
            self.write(10, counter)
        spi = SPI(self)
        for address in blocks:
            require(spi.array(address, 32) == target[address:address + 32],
                    f"Physical configuration mismatch at 0x{address:05x}.")


class SPI:
    """Direct SPI. Only D000/F000 application sectors can be erased/programmed."""

    def __init__(self, camera, write_sector=None):
        require(write_sector is None or write_sector in CODE_SECTORS, "Prohibited write sector.")
        self.camera, self.write_sector = camera, write_sector

    def read(self, command, address=None, length=1):
        require(command in (3, 5, 0x9F) and 1 <= length <= 128, "Prohibited SPI read.")
        require((command == 3 and address is not None and 0 <= address <= SIZE - length)
                or (command != 3 and address is None), "Invalid SPI address.")
        camera = self.camera
        camera.idle()
        camera.reg_write(0xF0A0, 0xC2)
        try:
            camera.reg_write(0xF0A5, 0)
            camera.reg_write(0xF0A5, 0)
            header = bytes((command,)) + (address.to_bytes(3, "big") if address is not None else b"")
            for byte in header:
                camera.reg_write(0xF0A6, byte)
            camera.reg_write(0xF0A4, 0)
            camera.reg_write(0xF0A3, length - 1)
            camera.reg_write(0xF0A2, len(header) - 1)
            camera.reg_write(0xF0A1, 0x23 if command == 3 else 0x63)
            self._controller_wait()
            return bytes(camera.reg_read(0xF0A6) for _ in range(length))
        except BaseException:
            camera.reg_write(0xF0A1, 0xC0)
            raise
        finally:
            camera.reg_write(0xF0A0, 1)

    def array(self, address, length):
        require(0 <= address <= SIZE - length and length > 0, "Invalid array read.")
        return b"".join(self.read(3, a, min(128, address + length - a))
                        for a in range(address, address + length, 128))

    def _controller_wait(self):
        end = time.monotonic() + 2
        while self.camera.reg_read(0xF0A1) & 1:
            if time.monotonic() > end:
                raise TimeoutError("SPI controller timed out.")

    def _send(self, command, address=None, payload=b""):
        require(self.write_sector in CODE_SECTORS and command in (2, 4, 6, 0x20), "Prohibited SPI write.")
        if command == 2:
            require(address is not None and address % 32 == 0 and len(payload) == 32
                    and self.write_sector <= address <= self.write_sector + 4096 - 32,
                    "Page outside authorized sector.")
        elif command == 0x20:
            require(address == self.write_sector and not payload, "Erase outside authorized sector.")
        else:
            require(address is None and not payload, "Unexpected SPI payload.")
        camera = self.camera
        camera.idle()
        camera.reg_write(0xF0A0, 0xC2)
        try:
            camera.reg_write(0xF0A5, 0)
            camera.reg_write(0xF0A5, 0)
            header = bytes((command,)) + (address.to_bytes(3, "big") if address is not None else b"")
            for byte in header:
                camera.reg_write(0xF0A6, byte)
            camera.reg_write(0xF0A4, 0)
            camera.reg_write(0xF0A3, 0)
            camera.reg_write(0xF0A2, len(header) - 1 + len(payload))
            camera.reg_write(0xF0A1, 0x61)
            camera.reg_write(0xF0A0, 0xC2)
            for byte in payload:
                end = time.monotonic() + 2
                while camera.reg_read(0xF0A5) & 0x80:
                    if time.monotonic() > end:
                        raise TimeoutError("SPI TX FIFO timed out.")
                camera.reg_write(0xF0A6, byte)
            self._controller_wait()
        except BaseException:
            camera.reg_write(0xF0A1, 0xC0)
            raise
        finally:
            camera.reg_write(0xF0A0, 1)

    def _enable(self):
        require(self.read(5)[0] & 0x3F == 0, "Flash busy, protected or unexpectedly write-enabled.")
        self._send(6)
        require(self.read(5)[0] & 3 == 2, "Write-enable latch failed.")

    def _wait(self):
        end = time.monotonic() + 3
        while True:
            status = self.read(5)[0]
            if not status & 1:
                break
            if time.monotonic() > end:
                raise TimeoutError("Flash programming timed out.")
        require(status & 3 == 0, "Write-enable latch did not clear.")

    def replace_sector(self, image):
        sector = self.write_sector
        require(sector in CODE_SECTORS and len(image) == SIZE, "No authorized application sector.")
        if self.array(sector, 4096) == image[sector:sector + 4096]:
            return
        try:
            self._enable()
            self._send(0x20, sector)
            self._wait()
            require(self.array(sector, 4096) == b"\xff" * 4096, "Physical sector erase failed.")
            for address in range(sector, sector + 4096, 32):
                data = image[address:address + 32]
                if data == b"\xff" * 32:
                    continue
                self._enable()
                self._send(2, address, data)
                self._wait()
                require(self.array(address, 32) == data, "Physical page verification failed.")
            require(self.array(sector, 4096) == image[sector:sector + 4096], "Sector verification failed.")
        finally:
            self._send(4)
            require(self.read(5)[0] & 3 == 0, "Could not disable flash writes.")
