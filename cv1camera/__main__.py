"""Guided Windows installer and offline planner. SPDX-License-Identifier: LGPL-2.1-or-later."""

import argparse
import contextlib
import os
import sys
from pathlib import Path

from . import __version__
from .profile import Refused, changed_blocks, patch, sha


@contextlib.contextmanager
def exclusive(root):
    """Prevent concurrent installers from interleaving USB flash operations."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / "installer.lock").open("a+b") as lock:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b"\0")
            lock.flush()
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise Refused("Another installer is running. Close it first.") from error
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def choose_backup(root):
    folders = sorted((root / "backups").glob("*/backup.json"), reverse=True)
    if not folders:
        raise Refused("No local backup found. Make a stock backup first.")
    for index, path in enumerate(folders, 1):
        print(f"{index}. {path.parent.name}")
    answer = input("Backup number (Enter cancels): ").strip()
    if not answer.isdigit() or not 1 <= int(answer) <= len(folders):
        raise Refused("Cancelled.")
    return folders[int(answer) - 1].parent


def main():
    parser = argparse.ArgumentParser(description="Native CV1 webcam firmware installer (experimental).")
    parser.add_argument("command", nargs="?", default="menu", choices=(
        "menu", "backup", "install", "verify", "restore", "recover-application", "plan"))
    parser.add_argument("--backup", type=Path, help="PRIVATE backup folder for this sensor")
    parser.add_argument("--image", type=Path, help="Stock image for offline planning only")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            if not args.image:
                parser.error("plan requires --image")
            original = args.image.read_bytes()
            target = patch(original)
            print(f"Compatible. {len(changed_blocks(original, target))} blocks; "
                  f"{sum(x != y for x, y in zip(original, target))} byte changes.")
            print("Plan only: NO USB access, NO image file created, NO flash writes.")
            print("Private target SHA256: " + sha(target))
            return 0
        from . import installer
        with exclusive(installer.private_root()):
            command = args.command
            print(f"Oculus CV1 Camera {__version__} - EXPERIMENTAL\n{installer.WARNING}\n")
            print("Connect exactly ONE CV1 sensor. Close Oculus software and all webcam apps.")
            if command == "menu":
                print("1. Install native MJPEG webcam firmware (includes backup)")
                print("2. Backup stock sensor only\n3. Verify installed profile")
                print("4. Restore original firmware\n5. Recover application from existing USB bootloader")
                choice = input("Choose 1-5, or Enter to exit: ").strip()
                command = {"1": "install", "2": "backup", "3": "verify", "4": "restore",
                           "5": "recover-application"}.get(choice)
                if not command:
                    return 0
            if command == "backup":
                installer.backup()
            elif command == "install":
                installer.install(args.backup or installer.backup())
            else:
                folder = args.backup or choose_backup(installer.private_root())
                {"verify": installer.verify, "restore": installer.restore,
                 "recover-application": installer.recover_application}[command](folder)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print(f"\nSTOP: {type(error).__name__}: {error}", file=sys.stderr)
        print("No automatic retry or speculative recovery is performed. Keep your private backup.", file=sys.stderr)
        print("If flash writes had started, read docs/RECOVERY.md before doing anything else.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
