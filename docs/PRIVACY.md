# Privacy and support reports

The repository and release ZIP contain source code, patch differences, generic documentation and synthetic tests. They do not contain the development sensor's serial number, complete firmware, calibration, webcam captures, private room imagery, local account paths, conversation history or machine logs.

The installer does **not** send telemetry or upload anything. Setup downloads the official UsbDk MSI from GitHub and pinned Python packages from PyPI. Those services can observe the download request and IP address. No sensor identifier is put in those requests.

## Private local data

`%LOCALAPPDATA%\OculusCV1Camera\backups\<timestamp-random-id>` contains:

- `original.bin` and `original-confirmed.bin`: complete original flash, including identity and calibration.
- `backup.json`: serial number, image checksum, acquisition time and generic device information.
- `operation.json`: local flash journal needed for restoration/recovery.
- `verification.json`: local verification outcome.

Backup folder names use a timestamp and random suffix, not a serial number. The directory is not encrypted; anyone who can read your Windows account's files can read it. Store a private copy on another disk. Removing setup files does not remove the backup automatically. Deleting it can remove your best chance of restoration.

The project ignores common backup/log/media extensions in Git, and release packaging uses an explicit file allowlist. `.gitignore` is not a privacy boundary: do not force-add private data or paste it into a report.

## Reporting a problem

Use the repository's issue template. Include only:

- Installer version, Windows version and general USB connection type.
- Stage that failed: setup, backup, compatibility check, write, readback, cold startup or live capture.
- Whether Device Manager shows normal `2833:0211`, fallback `1e4e:0668`, a failed USB device or no device.
- A short **redacted** error message, and whether the operation journal says writing began.

**Do not upload firmware, calibration, manifests, entire logs, serial numbers, screenshots with account names/paths, or camera captures.** Error messages can include local paths; replace user/account/folder names before posting. A maintainer does not need your complete firmware backup in a public issue.
