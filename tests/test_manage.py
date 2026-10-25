#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Проверки установки в изолированной временной домашней папке."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "manager", Path(__file__).resolve().parents[1] / "scripts/manage.py"
)
manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manager)


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.values = {
            "ROOT": root / "project", "HOME": root / "home",
            "DEST": root / "home/.local/bin/cosmic-osd",
            "STATE": root / "home/.local/share/cosmic-osd-no-layout-popup/install.json",
            "SYSTEM": root / "usr/bin/cosmic-osd",
        }
        self.patches = [patch.object(manager, k, v) for k, v in self.values.items()]
        for item in self.patches:
            item.start()
        manager.SYSTEM.parent.mkdir(parents=True)
        manager.SYSTEM.write_bytes(b"original")
        manager.SYSTEM.chmod(0o755)
        (manager.ROOT / "build").mkdir(parents=True)
        binary = manager.ROOT / "build/cosmic-osd"
        binary.write_bytes(b"patched")
        (manager.ROOT / "build/build-info.json").write_text(json.dumps({
            "upstream_revision": manager.REVISION,
            "architecture": manager.platform.machine(),
            "sha256": manager.digest(binary),
        }))
        self.package = patch.object(manager.subprocess, "check_output", return_value=manager.PACKAGE_VERSION)
        self.package.start()

    def tearDown(self):
        self.package.stop()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_install_and_rollback_preserve_original(self):
        manager.install()
        self.assertEqual(manager.DEST.read_bytes(), b"patched")
        self.assertTrue(os.access(manager.DEST, os.X_OK))
        self.assertTrue(manager.STATE.is_file())
        self.assertEqual(manager.SYSTEM.read_bytes(), b"original")
        manager.uninstall()
        self.assertFalse(manager.DEST.exists())
        self.assertFalse(manager.STATE.exists())
        self.assertEqual(manager.SYSTEM.read_bytes(), b"original")

    def test_unknown_version_refused(self):
        with patch.object(manager.subprocess, "check_output", return_value="other"):
            with self.assertRaises(RuntimeError):
                manager.install()
        self.assertFalse(manager.DEST.exists())

    def test_changed_build_refused(self):
        (manager.ROOT / "build/cosmic-osd").write_bytes(b"different")
        with self.assertRaises(RuntimeError):
            manager.install()
        self.assertFalse(manager.DEST.exists())

    def test_existing_override_preserved(self):
        manager.DEST.parent.mkdir(parents=True)
        manager.DEST.write_bytes(b"user file")
        with self.assertRaises(RuntimeError):
            manager.install()
        self.assertEqual(manager.DEST.read_bytes(), b"user file")

    def test_dangling_symlink_preserved(self):
        manager.DEST.parent.mkdir(parents=True)
        manager.DEST.symlink_to(manager.DEST.parent / "missing")
        with self.assertRaises(RuntimeError):
            manager.install()
        self.assertTrue(manager.DEST.is_symlink())

    def test_modified_override_not_deleted(self):
        manager.install()
        manager.DEST.write_bytes(b"user changes")
        with self.assertRaises(RuntimeError):
            manager.uninstall()
        self.assertEqual(manager.DEST.read_bytes(), b"user changes")

    def test_missing_original_prevents_rollback(self):
        manager.install()
        manager.SYSTEM.unlink()
        with self.assertRaises(RuntimeError):
            manager.uninstall()
        self.assertTrue(manager.DEST.exists())

    def test_install_and_uninstall_never_signal(self):
        with patch.object(manager.signal, "pidfd_send_signal") as send:
            manager.install()
            manager.uninstall()
            send.assert_not_called()

    def test_restart_signals_only_selected_process(self):
        manager.install()
        with patch.object(manager, "session_processes", return_value=[(123, 456, manager.SYSTEM)]), \
             patch.object(manager, "check_path") as check_path, \
             patch.object(manager.os, "pidfd_open", return_value=77) as open_pid, \
             patch.object(manager.os, "close") as close, \
             patch.object(manager.signal, "pidfd_send_signal") as send:
            manager.restart()
            check_path.assert_called_once_with(456)
            open_pid.assert_called_once_with(123)
            send.assert_called_once_with(77, manager.signal.SIGTERM)
            close.assert_called_once_with(77)

    def test_restart_refuses_ambiguous_processes(self):
        manager.install()
        with patch.object(manager, "session_processes", return_value=[]), \
             patch.object(manager.signal, "pidfd_send_signal") as send:
            with self.assertRaises(RuntimeError):
                manager.restart()
            send.assert_not_called()

    def test_restart_refuses_changed_process(self):
        manager.install()
        with patch.object(manager, "session_processes", side_effect=[[(123, 456, manager.SYSTEM)], []]), \
             patch.object(manager, "check_path"), \
             patch.object(manager.os, "pidfd_open", return_value=77), \
             patch.object(manager.os, "close"), \
             patch.object(manager.signal, "pidfd_send_signal") as send:
            with self.assertRaises(RuntimeError):
                manager.restart()
            send.assert_not_called()

    def test_restart_refuses_updated_package(self):
        manager.install()
        with patch.object(manager.subprocess, "check_output", return_value="updated"), \
             patch.object(manager.signal, "pidfd_send_signal") as send:
            with self.assertRaises(RuntimeError):
                manager.restart()
            send.assert_not_called()

    def test_root_refused(self):
        with patch.object(manager.os, "geteuid", return_value=0):
            with self.assertRaises(RuntimeError):
                manager.require_user()


if __name__ == "__main__":
    unittest.main()
