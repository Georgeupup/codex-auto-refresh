"""Regression checks for the Windows tray menu."""

import unittest
from pathlib import Path
from unittest.mock import patch

import win32con
import win32gui

from tray import EXIT_COMMAND, TRAY_MESSAGE, TrayIcon


class TrayMenuTests(unittest.TestCase):
    def test_right_click_exit_works_if_focus_is_denied(self):
        actions = []
        tray = TrayIcon(Path("unused.ico"), actions.append)
        with (
            patch("tray.win32gui.GetCursorPos", return_value=(100, 100)),
            patch("tray.win32gui.SetForegroundWindow", side_effect=win32gui.error(5, "SetForegroundWindow", "denied")),
            patch("tray.win32gui.TrackPopupMenu", return_value=EXIT_COMMAND),
            patch("tray.win32gui.PostMessage"),
        ):
            tray._on_tray_message(0, TRAY_MESSAGE, 0, win32con.WM_RBUTTONUP)

        self.assertEqual(actions, ["exit"])


if __name__ == "__main__":
    unittest.main()
