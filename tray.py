"""Windows notification area icon for the Tk interface."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable

import win32api
import win32con
import win32gui


TRAY_MESSAGE = win32con.WM_USER + 20
SHOW_COMMAND = 1001
EXIT_COMMAND = 1002


class TrayIcon:
    def __init__(self, icon_path: Path, on_action: Callable[[str], None]) -> None:
        self.icon_path = icon_path
        self.on_action = on_action
        self.visible = False
        self._hwnd = 0
        self._hicon = 0
        self._error: Exception | None = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="CodexWindowStarterTray", daemon=True)

    def start(self) -> None:
        self._thread.start()
        if not self._ready.wait(5):
            raise RuntimeError("托盘图标启动超时")
        if self._error:
            raise RuntimeError(f"托盘图标启动失败：{self._error}") from self._error

    def stop(self) -> None:
        if self._hwnd:
            try:
                win32gui.PostMessage(self._hwnd, win32con.WM_CLOSE, 0, 0)
            except win32gui.error:
                pass
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        try:
            hinst = win32api.GetModuleHandle(None)
            wc = win32gui.WNDCLASS()
            wc.hInstance = hinst
            wc.lpszClassName = f"CodexWindowStarterTray_{os.getpid()}_{id(self)}"
            restart_message = win32gui.RegisterWindowMessage("TaskbarCreated")
            wc.lpfnWndProc = {
                restart_message: self._on_restart,
                TRAY_MESSAGE: self._on_tray_message,
                win32con.WM_COMMAND: self._on_command,
                win32con.WM_CLOSE: self._on_close,
                win32con.WM_DESTROY: self._on_destroy,
            }
            win32gui.RegisterClass(wc)
            self._hwnd = win32gui.CreateWindow(
                wc.lpszClassName, "Codex 窗口定时器", win32con.WS_OVERLAPPED,
                0, 0, 0, 0, 0, 0, hinst, None,
            )
            self._hicon = win32gui.LoadImage(
                hinst, str(self.icon_path), win32con.IMAGE_ICON, 0, 0,
                win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE,
            )
            self._add_icon()
            self._ready.set()
            win32gui.PumpMessages()
        except Exception as exc:
            self._error = exc
            self._ready.set()
        finally:
            self.visible = False

    def _add_icon(self) -> None:
        nid = (
            self._hwnd, 0,
            win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
            TRAY_MESSAGE, self._hicon, "Codex 窗口定时器",
        )
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
            self.visible = True
        except win32gui.error:
            # Explorer may not be ready yet; TaskbarCreated will retry.
            self.visible = False

    def _on_restart(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        self._add_icon()
        return 0

    def _on_tray_message(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if lparam in (win32con.WM_LBUTTONUP, win32con.WM_LBUTTONDBLCLK):
            self.on_action("show")
        elif lparam == win32con.WM_RBUTTONUP:
            menu = win32gui.CreatePopupMenu()
            try:
                win32gui.AppendMenu(menu, win32con.MF_STRING, SHOW_COMMAND, "打开窗口")
                win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
                win32gui.AppendMenu(menu, win32con.MF_STRING, EXIT_COMMAND, "完全退出")
                x, y = win32gui.GetCursorPos()
                try:
                    win32gui.SetForegroundWindow(hwnd)
                except win32gui.error:
                    # Windows can deny focus to a background process; the menu can still open.
                    pass
                command = win32gui.TrackPopupMenu(
                    menu,
                    win32con.TPM_LEFTALIGN | win32con.TPM_RIGHTBUTTON | win32con.TPM_RETURNCMD | win32con.TPM_NONOTIFY,
                    x, y, 0, hwnd, None,
                )
                try:
                    win32gui.PostMessage(hwnd, win32con.WM_NULL, 0, 0)
                except win32gui.error:
                    pass
                self._dispatch_command(command)
            finally:
                win32gui.DestroyMenu(menu)
        return 0

    def _on_command(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        self._dispatch_command(win32api.LOWORD(wparam))
        return 0

    def _dispatch_command(self, command: int) -> None:
        if command == SHOW_COMMAND:
            self.on_action("show")
        elif command == EXIT_COMMAND:
            self.on_action("exit")

    def _on_close(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        win32gui.DestroyWindow(hwnd)
        return 0

    def _on_destroy(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if self.visible:
            try:
                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (hwnd, 0))
            except win32gui.error:
                pass
        self.visible = False
        if self._hicon:
            win32gui.DestroyIcon(self._hicon)
            self._hicon = 0
        self._hwnd = 0
        win32gui.PostQuitMessage(0)
        return 0
