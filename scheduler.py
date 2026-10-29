"""Windows Task Scheduler integration. Tasks run under the signed-in user."""

from __future__ import annotations

import os
import sys
import subprocess
import winreg
from datetime import datetime

from core import executable_command

TASK_PREFIX = "CodexWindowStarter_"
STARTUP_NAME = "CodexWindowStarterCatchup"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _folder():
    if sys.platform != "win32":
        raise RuntimeError("定时任务目前仅支持 Windows。")
    import win32com.client  # type: ignore[import-not-found]

    service = win32com.client.Dispatch("Schedule.Service")
    service.Connect()
    return service, service.GetFolder("\\")


def _names(folder) -> list[str]:
    return [task.Name for task in folder.GetTasks(0) if task.Name.startswith(TASK_PREFIX)]


def installed_times() -> list[str]:
    _, folder = _folder()
    return sorted(name[len(TASK_PREFIX):].replace("_", ":") for name in _names(folder))


def _register(service, folder, name: str, time: str) -> None:
    # Task Scheduler constants: daily=2, execute=0,
    # interactive token=3, create/update=6, ignore new instance=2.
    task = service.NewTask(0)
    task.RegistrationInfo.Description = "按设定时间发送一次简短 Codex 请求。"
    task.Principal.UserId = os.environ.get("USERDOMAIN", "") + "\\" + os.environ.get("USERNAME", "")
    task.Principal.LogonType = 3
    task.Principal.RunLevel = 0
    task.Settings.Enabled = True
    task.Settings.StartWhenAvailable = False
    task.Settings.DisallowStartIfOnBatteries = False
    task.Settings.StopIfGoingOnBatteries = False
    task.Settings.ExecutionTimeLimit = "PT15M"
    task.Settings.MultipleInstances = 2

    trigger = task.Triggers.Create(2)
    trigger.StartBoundary = f"{datetime.now():%Y-%m-%d}T{time}:00"
    trigger.DaysInterval = 1

    program, prefix = executable_command()
    action = task.Actions.Create(0)
    action.Path = program
    action.Arguments = (prefix + " " if prefix else "") + f"--run-slot {time}"
    action.WorkingDirectory = os.path.dirname(program)
    folder.RegisterTaskDefinition(name, task, 6, "", "", 3)


def _set_startup(enabled: bool) -> None:
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            program, prefix = executable_command()
            command = subprocess.list2cmdline([program]) + (" " + prefix if prefix else "") + " --run-catchup"
            winreg.SetValueEx(key, STARTUP_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, STARTUP_NAME)
            except FileNotFoundError:
                pass


def startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, STARTUP_NAME)
        return True
    except FileNotFoundError:
        return False


def install(times: list[str]) -> None:
    service, folder = _folder()
    expected = {TASK_PREFIX + time.replace(":", "_") for time in times}
    for time in times:
        _register(service, folder, TASK_PREFIX + time.replace(":", "_"), time)
    _set_startup(True)
    for name in _names(folder):
        if name not in expected:
            folder.DeleteTask(name, 0)


def uninstall() -> None:
    _, folder = _folder()
    _set_startup(False)
    for name in _names(folder):
        folder.DeleteTask(name, 0)
