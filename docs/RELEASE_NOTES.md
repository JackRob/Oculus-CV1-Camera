# Experimental CV1 native IR webcam — 0.1.0

> **This can and will brick your Sensor.** Permanent failure is possible. USB recovery is not guaranteed; opening the sensor and using a 3.3 V SPI programmer may be necessary. Proceed entirely at your own risk, with no warranty.

Source installer for Windows x64. For one recognized Oculus Rift CV1 external sensor firmware revision, it prepares native MJPEG/UVC with automatic USB 2 High-Speed startup. No bridge, virtual camera, service or per-session initializer is needed after successful flashing.

Download and extract the ZIP, read `README.md` and `docs/INSTALL.md`, install 64-bit Python 3.11–3.13, then run `Install.cmd`. The tool backs up your own sensor and refuses unknown firmware before allowing flash writes. Keep the private backup on another disk. An explicit risk phrase is required before writing.

The four native MJPEG modes are 1280×720/60, 1280×960/54, 960×576/90 and 960×960/54. The image is monochrome IR; dark rooms need IR illumination.

**Validation limit:** the final firmware profile and component operations were verified on one physical sensor. The newly packaged combined installer has offline tests but has not been physically tested across a population of devices or every failure mode. A live-video check on each installation remains necessary. Read the compatibility and recovery guides before proceeding.

This ZIP includes readable source and patch differences, not a complete firmware image, private calibration, serial numbers, captures or Git history. First-run setup downloads hash-pinned Python dependencies and, if needed, the official UsbDk flashing runtime. The tool has no telemetry or upload function.
