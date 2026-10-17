# Oculus CV1 Camera

Turn a supported **Oculus Rift CV1 external tracking sensor** into a native, monochrome infrared USB webcam. The sensor supplies standard **MJPEG over UVC** and uses Microsoft's built-in webcam driver. No virtual camera, bridge application, background service, or per-session initializer is required after flashing.

> [!CAUTION]
> **This can and will brick your Sensor.**
>
> This is experimental firmware modification. Treat the sensor as expendable. It can permanently stop responding, including after an apparently successful write. Backups and USB recovery do not guarantee recovery; opening the sensor and using a **3.3 V SPI flash programmer** may be necessary. Proceed entirely at your own risk. There is no warranty or guarantee of fitness, compatibility, recovery, or support.

## Get started

1. Read the [installation guide](docs/INSTALL.md), [compatibility limits](docs/COMPATIBILITY.md), and [recovery guide](docs/RECOVERY.md).
2. Download the [installer ZIP from Releases](https://github.com/JackRob/Oculus-CV1-Camera/releases). Extract it completely before running anything. The source ZIP from **Code → Download ZIP** also works.
3. On **Windows x64**, install **64-bit Python 3.11–3.13**. Connect exactly **one** CV1 sensor and close Oculus and camera applications.
4. Run **Install.cmd**, choose **Install**, and follow the backup, compatibility, risk-acceptance, and physical reconnect prompts. No flash writes occur until you explicitly accept the bricking risk.
5. After verification, close the installer and select **CV1 External Camera** in your webcam application. Confirm a live picture before relying on it.

The sensor automatically connects at **USB 2 High-Speed**, even through a USB 3 cable and port. This uses its existing hardware MJPEG path. It does not provide USB 3 webcam operation.

## What is available

| Native MJPEG mode | Frame rate |
| --- | --- |
| 1280 × 720 | 60 fps |
| 1280 × 960 | 54 fps |
| 960 × 576 | 90 fps |
| 960 × 960 | 54 fps |

These modes, native Windows capture, frame timing, cold startup, and infrared response were verified on **one sensor with one firmware revision**. The packaged installer is newly assembled from those tested operations; broad hardware compatibility and unattended installation have **not** been established. Each installation still needs its own live-video check. The firmware matcher refuses other revisions; there is no force option.

This remains an IR-filtered monochrome camera. A dark room needs **infrared illumination**. A television remote can demonstrate IR sensitivity but cannot illuminate a room. Exposure changes improve the tested profile without making it a normal visible-light webcam. Some apps may reject unusual frame rates; Windows Camera/native capture were tested, while every conferencing or streaming app was not.

## Backups and privacy

The installer reads **your own sensor's firmware**, makes two matching local backups, and patches that image. It does not distribute a complete firmware image or another sensor's calibration. Boot copies, USB identity and calibration are preserved.

Backups and operation records live under `%LOCALAPPDATA%\OculusCV1Camera\backups`. They can contain your sensor's serial number and calibration. **Keep them private and copy them to another disk. Never attach them to issues or pull requests.** The tool has no telemetry or upload function. Setup downloads dependencies from PyPI and the official UsbDk release, which have their own network logging.

- [Installation and verification](docs/INSTALL.md)
- [Supported hardware and test evidence](docs/COMPATIBILITY.md)
- [Restoration and recovery limits](docs/RECOVERY.md)
- [Firmware changes and protocol](docs/TECHNICAL.md)
- [Privacy and reporting problems](docs/PRIVACY.md)
- [Source/dependency credits](NOTICE.md)

Source code is **LGPL-2.1-or-later**; see [LICENSE](LICENSE). Original sensor firmware and third-party dependencies retain their respective ownership and licenses. This is an independent project, unaffiliated with Meta, Oculus, Etron, or Daynix.
