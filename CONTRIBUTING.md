# Contributing

This is experimental hardware modification. **This can and will brick your Sensor.** Do not treat a successful offline test as hardware validation.

Run the source tests and release checks from the project root:

```powershell
python -m unittest discover -s tests -v
python -O -m unittest discover -s tests -v
python tools/build_release.py
```

No hardware, USB dependencies, credentials, firmware images or private logs are needed for these checks. The tests use synthetic images/mocks and must never acquire real USB devices. Build output goes to ignored `dist/`; the ZIP uses an explicit source-file allowlist and a privacy check. Review its contents before publication.

For a different firmware revision, do not relax the existing matcher or copy offsets blindly. Establish a separate profile, backup/recovery strategy, preserved identity/calibration checks, and physical validation on an expendable sensor. Record compatibility honestly. No force-flash option should bypass the matcher.

Keep pull requests free of serials, calibration, firmware dumps, camera footage, machine paths, personal emails and support logs. Use generic examples and synthetic fixtures. See [privacy](docs/PRIVACY.md). Public Git commit metadata can expose personal information too: use a project author or GitHub privacy email before publishing history. Inspect **all prior commits**, not just the latest file tree.

Do not commit personal credentials or add telemetry. Preserve upstream license notices and explain material transport changes, especially timeout, write-order, and power-loss behavior.
