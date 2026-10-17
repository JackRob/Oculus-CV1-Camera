# Restoration and recovery

> **This can and will brick your Sensor.** Recovery is not guaranteed. A backup is data, not a way to communicate with an unresponsive chip. A **3.3 V SPI flash programmer** and opening the sensor may be required. Permanent failure is possible.

Keep both `original.bin` and `original-confirmed.bin`, `backup.json`, and `operation.json` together in the private backup folder. The original image contains sensor-specific identity and calibration. Never use another sensor's backup. Checksum manifests detect accidental corruption; they are not signatures or protection against malicious local edits.

The installer never deliberately damages a CRC to enter recovery, patches the bootloader, erases calibration, or automatically retries a failed installation. Do not unplug during a write in an attempt to force fallback.

## If the sensor still enumerates as `2833:0211`

1. Close all camera and Oculus applications. Keep one sensor connected.
2. Run **Install.cmd → Restore original firmware**, and choose the matching private backup. Alternatively, from the project folder:

   ```powershell
   $cv1Python = "$env:LOCALAPPDATA\OculusCV1Camera\python-env-0.1.0\Scripts\python.exe"
   & $cv1Python -m cv1camera restore --backup 'D:\PrivateCV1Backup'
   ```

3. Accept the risk prompt only if you intend to restore. The tool checks the serial, boot copies, calibration, matching operation journal, and changes outside the permitted installation sectors.
4. It restores application sectors D000/F000 and the changed configuration blocks, then performs full non-journal and physical readback checks. Power-cycle **only after it reports successful restoration**.

An interrupted configuration-sector erase can damage bytes outside the patch's 32-byte blocks. This tool refuses that situation rather than guessing how to repair it. Stock restoration does not preserve the MJPEG webcam behavior; it restores the sensor's pre-installation state.

## If the sensor enumerates as `1e4e:0668`

This is the eSP770U fallback USB bootloader. Fallback was physically tested on one unit by invalidating the main CRC and restoring it. It is **not** guaranteed for a valid-CRC firmware hang, failed bootloader, or configuration damage.

1. Keep the original private backup and the installation journal. Ensure no normal CV1 device or other fallback device is connected.
2. Use **Install.cmd → Recover application from existing USB bootloader**, or:

   ```powershell
   & $cv1Python -m cv1camera recover-application --backup 'D:\PrivateCV1Backup'
   ```

3. The tool checks JEDEC ID, both boot copies, calibration, untouched main regions and a matching journal showing that application writes started. It only restores the original **D000 and F000 application sectors**. It does not flash boot sectors or configuration via the fallback loader.
4. After full boot/main verification succeeds, unplug for five seconds and reconnect. Then run the **normal Restore** operation to restore the modified configuration blocks.

The original recovery transport was physically validated for F000. D000 uses the same bounded SPI sequence that was separately validated in normal mode; combined interrupted-D000 fallback recovery in the public installer has not been physically tested. Do not treat this command as a universal unbrick tool.

## If there is no USB device, or checks refuse recovery

Check the physical connection and try one direct port. A failed-device entry is different from no electrical connection. Keep the backup. Repeated flashing, forcing another firmware revision, or disabling the checks will not establish a working recovery path.

If no loader responds, software over USB cannot restore the sensor. Hardware recovery requires opening it and correctly identifying, powering, connecting and programming the SPI flash. This project does not provide a validated hardware-programmer procedure. Use appropriate electronics expertise and your sensor's own backup. Do not connect a 5 V programmer to a 3.3 V flash chip.

## After a stopped install

`operation.json` records write intent **before** each sector change and records successful readback afterward. The installer will not simply retry installation using that journal. Explicit restoration can resume application-sector restoration; configuration damage outside the changed blocks is refused. Preserve the journal if a restore fails. Never edit it to bypass a refusal, and never delete it to make an interrupted installation look fresh.
