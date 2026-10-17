"""Create a source-only installer ZIP from an explicit, privacy-checked allowlist.

SPDX-License-Identifier: LGPL-2.1-or-later
"""

import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = ("README.md", "LICENSE", "NOTICE.md", "CONTRIBUTING.md", "CHANGELOG.md", "Install.cmd",
              "Install.ps1", "requirements.txt", ".gitignore", ".gitattributes")
DIRECTORIES = {"cv1camera": {".py", ".json"}, "docs": {".md"}, "tests": {".py"}, "tools": {".py"}}
PATTERNS = (
    ("Windows account path", re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\s]+", re.I)),
    ("Unix account path", re.compile(r"/(?:home|Users)/[A-Za-z0-9_.-]+/")),
    ("CV1 serial", re.compile(r"\bWMT[A-Z0-9]{8,}\b")),
    ("email address", re.compile(r"\b[A-Za-z0-9_.+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("GitHub credential", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)


def source_files():
    paths = [ROOT / name for name in ROOT_FILES]
    for directory, extensions in DIRECTORIES.items():
        paths.extend(path for path in (ROOT / directory).rglob("*")
                     if path.is_file() and path.suffix in extensions and "__pycache__" not in path.parts)
    return sorted(paths)


def check_privacy(paths):
    for path in paths:
        # LICENSE includes upstream FSF addresses and generic example authors, as legally required.
        if path.name == "LICENSE":
            continue
        text = path.read_text(encoding="utf-8")
        for description, pattern in PATTERNS:
            if pattern.search(text):
                raise ValueError(f"Possible {description} in {path.relative_to(ROOT)}; review before packaging.")


def main():
    paths = source_files()
    check_privacy(paths)
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    archive = output / "Oculus-CV1-Camera-0.1.0-windows-x64.zip"
    prefix = "Oculus-CV1-Camera-0.1.0/"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in paths:
            name = prefix + path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            data = path.read_bytes()
            if path.suffix == ".cmd":
                data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            bundle.writestr(info, data)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = output / "SHA256SUMS.txt"
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    print(f"Built {archive.name}: {len(paths)} source files, {archive.stat().st_size} bytes.")
    print("SHA256 " + digest)
    print("No firmware binaries, backups, logs, media, credentials or Git history included.")


if __name__ == "__main__":
    main()
