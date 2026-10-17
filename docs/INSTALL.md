# Installation

> **This can and will brick your Sensor.** Treat it as expendable. No backup, readback check, firmware matcher, or recovery command makes flashing safe. A 3.3 V SPI programmer and physical access to the flash chip may be required to recover it; permanent failure is possible.

## Before you start

- Use a Windows 10/11 **x64** PC and **64-bit Python 3.11–3.13** from [python.org](https://www.python.org/downloads/windows/). Hardware development used Python 3.13. Other OS installers, ARM64 and 32-bit Windows are not supported.
- Use an external Oculus Rift **CV1 tracking sensor**, USB ID `2833:0211`. This does not target Rift DK2, Rift S, Quest, or headset cameras.
- Connect **one sensor only**, directly to a reliable USB port. The final firmware automatically uses USB 2 speed; you do not need a special hub.
- Close Camera, OBS, browsers using the camera, Oculus software, and other USB tools. Disable automatic sleep for the duration of flashing. Keep power and the USB connection stable.
- Read [compatibility](COMPATIBILITY.md) and [recovery](RECOVERY.md) first. Do not flash a sensor you cannot afford to lose.

## Guided installer

1. Download and extract the [release ZIP](https://github.com/JackRob/Oculus-CV1-Camera/releases). Keep the whole folder together. Running files from inside the ZIP is not supported.
2. Double-click **Install.cmd**. Review the source first if desired. Windows asks for administrator access; use the **same Windows account** so the private backup location stays consistent.
3. If UsbDk is absent, setup offers the official **Daynix UsbDk 1.0.22 x64** runtime. It validates the MSI's SHA256 and Authenticode signature before installation. Setup never disables driver-signature enforcement. Reboot if requested, then restart the installer.
4. Setup creates an isolated Python environment under `%LOCALAPPDATA%\OculusCV1Camera` and installs three version/hash-pinned packages from PyPI. Internet access is needed for this first setup.
5. Choose **Install**. The tool reads the sensor twice, saves both backups and a checksum manifest, checks the known firmware/layout fingerprints, and checks physical flash against the saved data. This can take several minutes. An unsupported revision stops without flash writes.
6. **Copy the displayed PRIVATE backup folder to another disk** before accepting the write prompt. It contains sensor-specific information. The folder is outside the source checkout.
7. Review the proposed change and type `I ACCEPT THE BRICKING RISK` only if you accept permanent loss. The tool writes the narrow profile and reads it back. **Do not unplug, close the window, restart, or suspend the PC while writing or verifying.**
8. When prompted **after readback succeeds**, unplug the sensor for **five seconds**, then reconnect it. The installer observes removal and return and checks the persistent profile and active USB configuration. Do not open webcam apps yet. If observation times out, reconnect and use **Verify** from the menu.
9. Close the installer. Open **Windows Camera** or another webcam app and select **CV1 External Camera**. Confirm that live video works. The installer verifies firmware, USB speed, descriptors, and negotiation; it does **not** claim that a live-video test ran on your machine.

UsbDk is a flashing transport, not the runtime webcam driver. You can remove **UsbDk Runtime Libraries** through Windows Installed Apps after successful verification. Keep it installed if you expect to restore or diagnose the sensor soon. Leave it installed if another device/tool depends on it. No initializer or service needs to run for the sensor to boot as a webcam.

## Command line

From the extracted project folder, with the setup-created Python environment:

```powershell
$cv1Python = "$env:LOCALAPPDATA\OculusCV1Camera\python-env-0.1.0\Scripts\python.exe"
& $cv1Python -m cv1camera backup
# Use the PRIVATE backup folder printed above:
& $cv1Python -m cv1camera install --backup 'D:\PrivateCV1Backup'
& $cv1Python -m cv1camera verify --backup 'D:\PrivateCV1Backup'
& $cv1Python -m cv1camera restore --backup 'D:\PrivateCV1Backup'
```

`install` without `--backup` makes a fresh stock backup first. A backup with an existing operation journal cannot be reused to retry installation. Use explicit restore if the first attempt was interrupted. To reinstall after a successful stock restoration, make a fresh backup.

For a manual Python environment on Windows x64:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: --require-hashes -r requirements.txt
.\.venv\Scripts\python.exe -m cv1camera
```

Install the official [UsbDk x64 runtime](https://github.com/daynix/UsbDk/releases/tag/v1.00-22) separately for the manual route. SHA256 of `UsbDk_1.0.22_x64.msi`:

```text
91f6f695e1e13c656024e6d3b55620bf08d8835ef05ee0496935ba6bb62466a5
```

`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1 -CheckOnly` checks Python/UsbDk availability without setup, downloads, USB access, or flashing. The execution-policy override is process-local; no permanent policy change is made.

## Offline plan

This works without USB packages, a connected device, or administrator rights:

```powershell
python -m cv1camera plan --image 'D:\PrivateCV1Backup\original.bin'
```

It checks the stock image and reports the patch size. It does not create an image file or flash anything. Do not publish the image or its private manifest.

## Picture checks

- The image is **monochrome infrared**. A dark room needs an IR illuminator. A visible lamp may emit little usable IR.
- Aim a TV remote's transmitting end at the lens from roughly 30 cm and hold a button while moving it. A bright blinking or moving spot demonstrates IR response; some remotes use radio for most buttons.
- A green/garbled picture or raw YUY2 option suggests the complete profile did not load. Close apps, power-cycle once, and run **Verify**. Do not keep reflashing.
- Some applications choose unsupported frame rates or cannot handle 54/90 fps. Test Windows Camera, then select one of the advertised MJPEG modes if your app allows it. Compatibility with every conferencing application is not guaranteed.
- For black frames, check the lens and illumination first. If USB verification fails, follow [recovery](RECOVERY.md).
