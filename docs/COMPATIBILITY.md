# Compatibility and validation

> **This can and will brick your Sensor.** A matching profile is a prerequisite, not a guarantee of safety.

## Supported target

| Item | Required/tested value |
| --- | --- |
| Hardware | External Oculus Rift CV1 tracking sensor |
| Normal USB ID | `2833:0211` |
| Controller | Etron eSP770U |
| Image sensor | AR0134 monochrome IR |
| Flash | 128 KiB, JEDEC `C2 20 11` |
| Bootloader USB ID, if fallback starts | `1e4e:0668` |
| Installer host | Windows x64; Python 3.11–3.13 x64 |
| Runtime driver verified | Microsoft `usbvideo.sys` / `usbvideo.inf` |
| Final transport | USB 2 High-Speed, including when connected to a USB 3 port |

The exact boot, main application, descriptor/negotiation tables, frame context tables, and sensor-init table fingerprints are in [`cv1camera/profile.json`](../cv1camera/profile.json). Every edited byte has a required original value. An unexpected revision or partial prior modification is refused; **do not bypass these checks**. Different serial numbers and calibration are retained from each sensor, not copied from the development unit.

## What was tested on hardware

On **one CV1 sensor and one Windows system**, before packaging this public installer:

- Standard MJPEG/UVC enumeration with the Microsoft built-in webcam driver.
- All four modes: 1280×720/60, 1280×960/54, 960×576/90 and 960×960/54.
- Correct UVC negotiation intervals and captured packet timing.
- Clean steady-state JPEG decoding in all four modes. Early development tests occasionally produced incomplete startup packets; application behavior at startup is still worth checking.
- A cold-start 60-packet capture at 54 fps with no incomplete JPEG packets.
- Native Windows MediaCapture recording without custom mode initialization; strictly increasing timestamps and clean decoded output.
- Physical unplug/reconnect persistence and full non-journal flash verification.
- A visible response to a moving TV remote's infrared transmitter.
- Original boot copies and calibration preserved byte-for-byte.
- Deliberate invalid-main-CRC fallback, USB bootloader access, and restoration of the original main firmware on that unit.

The public installer's combined stock-to-final flow was **not reflashed onto the development sensor just to test packaging**. Its byte transformation reproduces the validated final firmware; its component USB operations were physically tested during development. Automated tests use synthetic images and mocked transports. These tests cannot establish compatibility with an untested sensor, interrupted configuration erase, USB controller, OS, driver stack, or application.

## Limits

- This is not a general firmware updater. It does not discover offsets for other revisions or include a force mode.
- The native USB 3 path was not made into conventional webcam video; automatic USB 2 operation is intentional.
- This profile repurposes a tracking sensor. Oculus tracking use while patched is not supported; restore your own stock backup first.
- No claim is made for every version of OBS, Teams, Zoom, browsers, or other apps. Test your intended application.
- Normal webcam use may work on other UVC hosts, but Linux/macOS installation and runtime behavior were not validated here.
- No sensor serial, calibration dump, room image, native recording, or personal machine log is published as test evidence. The published evidence is the method, checks, and aggregate outcome.
