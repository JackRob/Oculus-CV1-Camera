# Firmware profile and implementation

> **This can and will brick your Sensor.** These details describe one tested firmware revision; they are not instructions to patch arbitrary images by offset.

## Patch-only distribution

`cv1camera/profile.json` contains **98 changed bytes in 54 contiguous runs**, with original values and replacements. It contains no complete firmware image, serial number, calibration, or private capture. The planner applies those changes to the attached sensor's backed-up 128 KiB image and preserves all other bytes.

Compatibility requires exact hashes for immutable boot/main and selected table ranges, each edit's preimage, a valid main CRC, normal USB ID, and the tested flash JEDEC ID. Hashes cover code/table regions, not personal serial/calibration fields. The tool has no arbitrary flash-address, chip-erase, force, or automatic boot-entry command. Checks use explicit exceptions and remain active under `python -O`.

## Changes

| Area | Change |
| --- | --- |
| USB classes | Eight video class bytes change from vendor-specific `FF` to video `0E` |
| HS configuration | Advertise one MJPEG format at index 1; packed descriptor stream produces a 324-byte active configuration |
| Stream contexts | Existing JPEG contexts populate format-1 records |
| Negotiation timing | Four F2 table intervals follow the existing JPEG mode rates: 60/54/90/54 fps |
| Startup | Physical `DA2D: E0 FF → 7F 02`; existing USB-mode setter receives USB 2 mode at every boot |
| Main CRC | Physical `FFEC: 25 85 → 14 E6`, big-endian CRC16/Modbus, init FFFF over `[6000, FFE8)` |
| Exposure mode | Saved AE mode at `12DEC: 01 → 08` |
| AR0134 integration | Six existing coarse integration values increase within the tested frame lengths; gain is unchanged |

Both boot copies (`0000–5FFF`) and calibration (`1D000–1DFFF`) are preserved. The profile does not relocate sensor initialization records, add encoder code, or convert video on the host. USB 2 startup selects the controller's existing MJPEG path. Changing descriptor labels alone was insufficient: matching contexts and negotiation timing were also necessary.

## Transport and write bounds

The Windows tool uses `libusb1`, packaged libusb, and the **UsbDk backend** to claim the existing device temporarily. It releases the device after flashing/verifying; Windows then uses the normal webcam driver. UsbDk is never the webcam video provider.

The eSP770U extension unit is **unit 4 on interface 0**. Selectors 10/11/12 provide counter/control/data transactions; selector 3 provides register access. Read protocol and register operations are adapted from [ouvrt's eSP770U implementation](https://github.com/pH5/ouvrt/blob/446354fae08f9851658e92d31fe422d21fd3c47f/src/esp770u.c).

- Configuration writes are limited to changed **32-byte blocks** in sectors `10000`, `12000`, and `13000`, through the firmware's tested batching/finalization path. This path may erase/rewrite internally; a 32-byte API operation is not power-failure atomic.
- Direct SPI erase/program is restricted to application sectors `D000` and `F000`, preserving all unrelated bytes from the sensor's backup. Each is a 4 KiB erase followed by 32-byte programming and physical verification.
- SPI reads allow only JEDEC ID `9F`, status `05`, and array read `03`. SPI writes allow page program `02`, write enable/disable `06/04`, and sector erase `20`, with explicit address bounds.
- Sector installation order is frame contexts/exposure (`13000`), saved exposure mode (`12000`), descriptors/timing (`10000`), startup code (`D000`), and main CRC (`F000`). The tool never intentionally reboots mid-write.
- A filesystem lock prevents two instances of this tool interleaving writes. It cannot prevent an unrelated application or tool from interfering; close them first.

## Verification

Two matching normal-mode firmware acquisitions are saved before writing. Physical SPI reads check boot copies, calibration and all affected sectors. Preflight repeats the relevant checks before installation. Readback requires **all bytes below `1F000` to match**, including identity/calibration; physical SPI independently checks every affected sector, boot copies and calibration.

The firmware-managed last sector may change only at previously observed paired journal positions: `55` at relative `100`, `AA` at relative `1FE`, repeated every `200` bytes. Only original `FF` to those values is accepted; all other differences or unpaired markers fail verification. The patch never directly writes that sector.

After a physical reconnect, verification also requires USB **High-Speed**, the expected 324-byte MJPEG-only configuration, and UVC GET_DEF probe interval **166666 × 100 ns** for the default 60 fps mode. It performs no runtime initialization. The user then checks live video in a native application. The packaged verifier does not equate descriptor presence with a successful frame capture.

Full hardware test methods and limits are listed in [COMPATIBILITY.md](COMPATIBILITY.md). Source tests intentionally cannot access hardware. The release workflow builds a source installer ZIP and SHA256 file, never a binary firmware image or a hardware-test log.
