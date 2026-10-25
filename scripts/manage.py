#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Установка в домашнюю папку; системный бинарник никогда не изменяется."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
REVISION = "9b14ee017fb8fdb7d03d73da597cf17b89d890f7"
PACKAGE_VERSION = "1.10.0~1791315686~24.04~9b14ee0"
HOME = Path.home()
DEST = HOME / ".local/bin/cosmic-osd"
STATE = HOME / ".local/share/cosmic-osd-no-layout-popup/install.json"
SYSTEM = Path("/usr/bin/cosmic-osd")


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def require_user():
    if os.geteuid() == 0:
        raise RuntimeError("Do not run this tool as root or with sudo.")


def session_processes():
    """Отбираем только процессы текущего пользователя, запущенные cosmic-session."""
    result = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            if (entry / "comm").read_text().strip() != "cosmic-osd":
                continue
            status = (entry / "status").read_text().splitlines()
            parent = next(line.split()[1] for line in status if line.startswith("PPid:"))
            if (Path("/proc") / parent / "comm").read_text().strip() != "cosmic-session":
                continue
            exe = (entry / "exe").resolve(strict=True)
            if exe not in (SYSTEM, DEST):
                continue
            result.append((int(entry.name), int(parent), exe))
        except (OSError, StopIteration):
            continue
    return result


def check_path(parent):
    env = (Path("/proc") / str(parent) / "environ").read_bytes().split(b"\0")
    path = next((v[5:].decode() for v in env if v.startswith(b"PATH=")), "")
    resolved = shutil.which("cosmic-osd", path=path)
    if resolved != str(DEST):
        raise RuntimeError("cosmic-session PATH does not select ~/.local/bin/cosmic-osd. Restart cancelled.")


def check_package():
    version = subprocess.check_output(
        ["dpkg-query", "-W", "-f=${Version}", "cosmic-osd"], text=True
    ).strip()
    if version != PACKAGE_VERSION:
        raise RuntimeError(f"Unsupported package version: {version}. Expected {PACKAGE_VERSION}.")
    return version


def install():
    version = check_package()
    binary = ROOT / "build/cosmic-osd"
    info = json.loads((ROOT / "build/build-info.json").read_text())
    if info.get("upstream_revision") != REVISION or info.get("architecture") != platform.machine():
        raise RuntimeError("Build revision or architecture mismatch.")
    checksum = digest(binary)
    if info.get("sha256") != checksum:
        raise RuntimeError("Build checksum mismatch.")
    if DEST.exists() or DEST.is_symlink() or STATE.exists() or STATE.is_symlink():
        raise RuntimeError("Existing override or installation state found. Nothing overwritten.")
    original = digest(SYSTEM)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    record = {"installed_sha256": checksum, "original_sha256": original,
              "package_version": version, "upstream_revision": REVISION}
    temporary = None
    created = False
    try:
        with tempfile.NamedTemporaryFile(dir=DEST.parent, delete=False) as out:
            temporary = Path(out.name)
            with binary.open("rb") as source:
                shutil.copyfileobj(source, out)
        temporary.chmod(0o755)
        if digest(temporary) != checksum:
            raise RuntimeError("Installed copy checksum mismatch.")
        # Жёсткая ссылка обеспечивает отказ вместо перезаписи существующего файла.
        os.link(temporary, DEST)
        created = True
        with STATE.open("x") as out:
            json.dump(record, out, indent=2)
            out.write("\n")
    except BaseException:
        if created:
            DEST.unlink()
        raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f"Installed: {DEST}\nOriginal unchanged: {SYSTEM}")
    print("No process restarted. Run: python3 scripts/manage.py restart")


def uninstall():
    record = json.loads(STATE.read_text())
    if DEST.is_symlink() or digest(DEST) != record["installed_sha256"]:
        raise RuntimeError("Override has changed. Refusing to remove it.")
    if not SYSTEM.is_file() or not os.access(SYSTEM, os.X_OK):
        raise RuntimeError("System original unavailable. Refusing to remove override.")
    DEST.unlink()
    STATE.unlink()
    print("Override removed; system original will be used on next login.")
    print("Log out and back in to complete rollback. No process was stopped.")


def restart():
    check_package()
    record = json.loads(STATE.read_text())
    if DEST.is_symlink() or digest(DEST) != record["installed_sha256"]:
        raise RuntimeError("Installed override does not match installation record.")
    processes = session_processes()
    if len(processes) != 1:
        raise RuntimeError("Expected exactly one cosmic-session-managed OSD. Log out and back in instead.")
    pid, parent, _ = processes[0]
    check_path(parent)
    # pidfd закрепляет процесс и исключает отправку сигнала повторно использованному PID.
    fd = os.pidfd_open(pid)
    try:
        if session_processes() != processes:
            raise RuntimeError("Process changed. Restart cancelled.")
        signal.pidfd_send_signal(fd, signal.SIGTERM)
    finally:
        os.close(fd)
    print("SIGTERM sent only to cosmic-osd; cosmic-session should restart it automatically.")
    print("Verify: python3 scripts/manage.py status")


def status():
    print(f"Override: {DEST} (exists: {DEST.exists()})")
    print(f"Installation record exists: {STATE.exists()}")
    for pid, parent, exe in session_processes():
        print(f"PID={pid} parent={parent} executable={exe}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall", "restart", "status"))
    args = parser.parse_args()
    require_user()
    globals()[args.action]()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        sys.exit(f"Error: {exc}")
