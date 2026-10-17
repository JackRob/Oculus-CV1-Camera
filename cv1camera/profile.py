"""Offline patch planning; no USB access or firmware image redistribution.

SPDX-License-Identifier: LGPL-2.1-or-later
"""

import hashlib
import json
from pathlib import Path

SIZE = 0x20000
JOURNAL = 0x1F000
CONFIG_SECTORS = (0x10000, 0x12000, 0x13000)
CODE_SECTORS = (0xD000, 0xF000)


class Refused(RuntimeError):
    """A precondition failed; do not bypass it."""


def require(condition, message):
    # Explicit exceptions remain enabled with python -O.
    if not condition:
        raise Refused(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def crc16(data):
    value = 0xFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xA001 if value & 1 else 0)
    return value


def load_profile():
    return json.loads(Path(__file__).with_name("profile.json").read_text(encoding="utf-8"))


def validate_image(image, installed=False):
    profile = load_profile()
    require(len(image) == SIZE, "Expected a 128 KiB CV1 flash image.")
    state = "after" if installed else "before"
    for region in profile["fingerprints"]:
        start, end = region["start"], region["end"]
        require(sha(image[start:end]) == region[state],
                f"Unsupported {state} firmware/layout in {region['name']}. No override is provided.")
    for edit in profile["edits"]:
        address = edit["offset"]
        expected = bytes.fromhex(edit[state])
        require(image[address:address + len(expected)] == expected,
                f"Unexpected bytes at 0x{address:05x}; incompatible or partially modified firmware.")
    require(image[0xFFEE:0xFFF0] == b"\x55\xaa", "Missing main firmware marker.")
    require(crc16(image[0x6000:0xFFE8]) == int.from_bytes(image[0xFFEC:0xFFEE], "big"),
            "Main firmware CRC is invalid.")


def patch(image):
    validate_image(image)
    result = bytearray(image)
    for edit in load_profile()["edits"]:
        address = edit["offset"]
        before, after = bytes.fromhex(edit["before"]), bytes.fromhex(edit["after"])
        require(len(before) == len(after) and len(before) > 0, "Invalid patch length.")
        require(all((i & ~4095) in CODE_SECTORS + CONFIG_SECTORS
                    for i in range(address, address + len(after))), "Patch outside write allowlist.")
        result[address:address + len(after)] = after
    result = bytes(result)
    require(result[:0x6000] == image[:0x6000], "Boot changes prohibited.")
    require(result[0x15000:] == image[0x15000:], "Identity/calibration/journal changes prohibited.")
    validate_image(result, installed=True)
    return result


def changed_blocks(before, after):
    require(len(before) == len(after) == SIZE, "Invalid image size.")
    blocks = sorted({i & ~31 for i, (x, y) in enumerate(zip(before, after)) if x != y})
    require(all((a & ~4095) in CODE_SECTORS + CONFIG_SECTORS for a in blocks),
            "Difference outside write allowlist.")
    return blocks


def verify_image(actual, expected):
    """Allow only the observed paired 55/AA controller journal markers."""
    require(len(actual) == len(expected) == SIZE, "Short verification image.")
    require(actual[:JOURNAL] == expected[:JOURNAL], "Flash verification failed outside journal.")
    allowed = {base + relative: value for base in range(JOURNAL, SIZE, 0x200)
               for relative, value in ((0x100, 0x55), (0x1FE, 0xAA))}
    for i in range(JOURNAL, SIZE):
        if actual[i] != expected[i]:
            require(i in allowed and expected[i] == 255 and actual[i] == allowed[i],
                    "Unexpected controller journal change.")
    for base in range(JOURNAL + 0x100, SIZE, 0x200):
        require((actual[base], actual[base + 254]) in ((255, 255), (0x55, 0xAA)),
                "Unpaired controller journal marker.")


def hs_config(image):
    """Reconstruct the firmware's packed high-speed descriptor record stream."""
    position = 0x10154
    output = bytearray()
    while position + 4 <= 0x10540 and image[position] == 0 and image[position + 2] == 0xF1:
        length, mask = image[position + 1], image[position + 3]
        require(length >= 4 and position + length <= SIZE, "Invalid packed descriptor.")
        if mask & 4:
            output += image[position + 4 + (1 if mask & 1 else 0):position + length]
        position += length
    require(len(output) >= 4, "Missing high-speed descriptor.")
    length = int.from_bytes(output[2:4], "little")
    require(length <= len(output), "Short packed configuration.")
    return bytes(output[:length])
