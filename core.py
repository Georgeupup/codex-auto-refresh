"""Configuration and one-shot Codex window trigger."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

APP_NAME = "CodexWindowStarter"
DEFAULT_TIMES = ["06:00", "11:00", "16:00", "21:00"]
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_NAME


def config_path() -> Path:
    return data_dir() / "config.json"


def normalize_times(text: str | list[str]) -> list[str]:
    parts = re.split(r"[,，;；\s]+", text.strip()) if isinstance(text, str) else text
    times = [item.strip() for item in parts if item.strip()]
    if not times:
        raise ValueError("请先点击＋添加至少一个时间点。")
    if any(not TIME_RE.fullmatch(item) for item in times):
        raise ValueError("时间格式必须是 HH:MM。")
    if len(times) != len(set(times)):
        raise ValueError("时间不能重复。")
    return sorted(times)


def short_gaps(times: list[str]) -> list[tuple[str, str, int]]:
    minutes = [int(t[:2]) * 60 + int(t[3:]) for t in times]
    return [
        (times[i], times[(i + 1) % len(times)], (minutes[(i + 1) % len(times)] - minutes[i]) % 1440 or 1440)
        for i in range(len(times))
        if ((minutes[(i + 1) % len(times)] - minutes[i]) % 1440 or 1440) < 300
    ]


def find_codex() -> str:
    candidates = list(dict.fromkeys(filter(None, (
        shutil.which("codex.exe"), shutil.which("codex.cmd"), shutil.which("codex"),
    ))))
    return max(candidates, key=_probe_version) if candidates else ""


def load_config() -> dict:
    try:
        with config_path().open(encoding="utf-8") as handle:
            raw = json.load(handle)
        saved_path = str(raw.get("codex_path", ""))
        preferred_path = find_codex()
        if not Path(saved_path).is_file() or _probe_version(preferred_path) > _probe_version(saved_path):
            saved_path = preferred_path
        return {
            "times": normalize_times(raw.get("times", DEFAULT_TIMES)),
            "codex_path": saved_path,
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"times": DEFAULT_TIMES.copy(), "codex_path": find_codex()}


def save_config(config: dict) -> None:
    normalized = {
        "times": normalize_times(config["times"]),
        "codex_path": str(config["codex_path"]),
    }
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="config-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(normalized, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, config_path())
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def log_result(slot: str, result: str) -> None:
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "history.log").open("a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {slot}  {result}\n")


def last_success() -> datetime | None:
    try:
        raw = json.loads((data_dir() / "last_success.json").read_text(encoding="utf-8"))
        return datetime.fromisoformat(raw["completed_at"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def seconds_until_eligible(now: datetime, previous: datetime | None) -> float:
    if previous is None:
        return 0.0
    return max(0.0, (previous + timedelta(hours=5, seconds=45) - now).total_seconds())


def record_success() -> None:
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "last_success.json").write_text(json.dumps({"completed_at": datetime.now().isoformat()}), encoding="utf-8")


def read_history(lines: int = 30) -> str:
    try:
        return "".join((data_dir() / "history.log").read_text(encoding="utf-8").splitlines(keepends=True)[-lines:])
    except OSError:
        return "尚无执行记录。"


def executable_command() -> tuple[str, str]:
    """Return Task Scheduler's action executable and argument prefix."""
    if getattr(sys, "frozen", False):
        return sys.executable, ""
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    return str(pythonw if pythonw.exists() else python), subprocess.list2cmdline([str(Path(__file__).with_name("app.py"))])


def _subscription_env() -> dict[str, str]:
    environment = os.environ.copy()
    for name in ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL"):
        environment.pop(name, None)
    return environment


def _version_tuple(text: str) -> tuple[int, int, int]:
    match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", text)
    return tuple(map(int, match.groups())) if match else (0, 0, 0)


def _probe_version(path: str) -> tuple[int, int, int]:
    if not path or not Path(path).is_file():
        return (0, 0, 0)
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=12, check=False, creationflags=flags, env=_subscription_env())
        return _version_tuple(result.stdout + result.stderr) if result.returncode == 0 else (0, 0, 0)
    except (OSError, subprocess.TimeoutExpired):
        return (0, 0, 0)


def check_codex(path: str) -> tuple[bool, str]:
    if not path or not Path(path).is_file():
        return False, "找不到 Codex CLI；请先安装并登录，然后选择 codex.cmd 或 codex.exe。"
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        environment = _subscription_env()
        version = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=12, check=False, creationflags=flags, env=environment)
        if version.returncode != 0:
            return False, "Codex CLI 无法启动。"
        preferred_cli = find_codex()
        if preferred_cli and os.path.normcase(path) != os.path.normcase(preferred_cli):
            if _probe_version(preferred_cli) > _version_tuple(version.stdout):
                return False, "所选 Codex CLI 版本较旧；请点击“选择”，改用电脑上版本较新的 Codex CLI。"
        login = subprocess.run([path, "login", "status"], capture_output=True, text=True, timeout=12, check=False, creationflags=flags, env=environment)
        login_text = (login.stdout + login.stderr).lower()
        if login.returncode != 0 or "chatgpt" not in login_text:
            return False, "请先用 ChatGPT 订阅登录 Codex CLI（终端运行 codex login）。API Key 模式不会触发订阅窗口。"
        return True, version.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return False, "Codex CLI 检查超时或无法启动。"


def _failure_message(events: list[dict], exit_code: int) -> str:
    details = ""
    for event in reversed(events):
        if event.get("type") not in ("turn.failed", "error"):
            continue
        error = event.get("error") or event.get("message") or ""
        if isinstance(error, dict):
            error = error.get("message") or error.get("code") or ""
        details = str(error)
        break
    if "model_not_found" in details or ("not supported" in details and "ChatGPT" in details):
        return "失败：这个 Codex CLI 选择了当前 ChatGPT 账号不支持的模型。请改用更新的 codex.exe，再点“检查登录”。"
    if any(word in details.lower() for word in ("usage_limit", "rate_limit", "quota")):
        return "失败：当前额度或速率限制已触发；请稍后查看 Codex 使用量。"
    if any(word in details.lower() for word in ("unauthorized", "authentication", "invalid_token")):
        return "失败：Codex 登录已失效；请在终端重新运行 codex login。"
    code_match = re.search(r'"code"\s*:\s*"([a-z_]+)"', details)
    if code_match:
        return f"失败：Codex 返回 {code_match.group(1)}（退出码 {exit_code}）"
    return f"失败：Codex 未完成请求（退出码 {exit_code}）"


def trigger(slot: str, config: dict | None = None, runner=subprocess.run) -> tuple[bool, str]:
    """Send one small request; never claim that an existing window was reset."""
    config = config or load_config()
    path = config.get("codex_path", "")
    if not path or not Path(path).is_file():
        message = "失败：找不到 Codex CLI"
        log_result(slot, message)
        return False, message
    ready, reason = check_codex(path)
    if not ready:
        message = "失败：" + reason
        log_result(slot, message)
        return False, message

    workdir = data_dir() / "empty-workspace"
    workdir.mkdir(parents=True, exist_ok=True)
    command = [
        path, "exec", "--ephemeral", "--json", "--sandbox", "read-only", "--ignore-user-config",
        "--skip-git-repo-check", "--disable", "hooks", "-C", str(workdir),
        "Reply OK. Do not use tools.",
    ]
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        completed = runner(command, capture_output=True, text=True, timeout=180, check=False, cwd=workdir, creationflags=flags, env=_subscription_env())
    except subprocess.TimeoutExpired:
        message = "失败：Codex 请求超过 3 分钟"
    except OSError:
        message = "失败：无法启动 Codex CLI"
    else:
        events = []
        for line in completed.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        done = next((e for e in reversed(events) if e.get("type") == "turn.completed"), None)
        if completed.returncode == 0 and done is not None:
            usage = done.get("usage") or {}
            tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            message = f"已完成一次请求，消耗 {tokens} tokens" if tokens else "已完成一次请求"
            record_success()
            log_result(slot, message)
            return True, message
        message = _failure_message(events, completed.returncode)
    log_result(slot, message)
    return False, message
