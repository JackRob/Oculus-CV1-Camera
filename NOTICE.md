# Credits and third-party notices

This project is an independent community tool. No affiliation with Meta/Oculus, Etron, Daynix, or the upstream projects is implied.

- **ouvrt**, Copyright 2017–2018 Philipp Zabel, **LGPL-2.1-or-later**. The eSP770U USB flash-read and register-access protocol in `cv1camera/transport.py` is adapted from [`src/esp770u.c`](https://github.com/pH5/ouvrt/blob/446354fae08f9851658e92d31fe422d21fd3c47f/src/esp770u.c). The public Python transport, constrained write paths, profile, installer, tests and docs were assembled/modified in 2026 by this project's contributors. License text is included in `LICENSE`.
- **python-libusb1** (`libusb1`), **LGPL-2.1-or-later**: [source](https://github.com/vpelletier/python-libusb1). Downloaded as a separately installed dependency.
- **libusb-package** and bundled **libusb**: [package source and license notices](https://github.com/pyocd/libusb-package), [libusb source and LGPL-2.1-or-later license](https://github.com/libusb/libusb). Installed separately from PyPI; see the dependency's own license files for the wrapper and bundled library.
- **importlib-resources**, **Apache-2.0**: [source and license](https://github.com/python/importlib_resources). A separately installed dependency of libusb-package.
- **UsbDk**, Daynix, **Apache-2.0**: [source](https://github.com/daynix/UsbDk), [official release](https://github.com/daynix/UsbDk/releases/tag/v1.00-22). The installer downloads the official MSI; it is not redistributed in this source ZIP. Its license and notices remain with that software.
- The original sensor firmware is not distributed here. Users must acquire it from their own sensor. The source license does not grant rights to proprietary firmware, trademarks, or third-party software.

This repository's code is licensed under **GNU LGPL version 2.1 or, at your option, any later version**, without warranty, including merchantability or fitness for a particular purpose. Preserve upstream copyright and license notices when redistributing modifications.
