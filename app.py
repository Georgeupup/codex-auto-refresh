"""Small Windows GUI and scheduled worker for Codex's 5-hour window."""

from __future__ import annotations

import argparse
import json
import msvcrt
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, Button, Canvas, Entry, Frame, Label, StringVar, Text, Toplevel, filedialog, messagebox, ttk
from tkinter import Tk

import core
import scheduler


def _slot_datetime(slot: str, now: datetime) -> datetime:
    hour, minute = map(int, slot.split(":"))
    point = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return point if point <= now else point - timedelta(days=1)


def run_scheduled(slot: str, point: datetime | None = None) -> None:
    """Run a due slot once, including when a logon task catches it up."""
    now = datetime.now()
    point = point or _slot_datetime(slot, now)
    if not timedelta(0) <= now - point < timedelta(hours=5):
        return
    config = core.load_config()
    if slot not in config["times"]:
        return

    directory = core.data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    lock_path = directory / "worker.lock"
    with lock_path.open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.seek(0)
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        try:
            state_path = directory / "attempts.json"
            try:
                attempts = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                attempts = {}
            key = f"{point:%Y-%m-%d} {slot}"
            if key in attempts:
                return
            attempts = {k: v for k, v in attempts.items() if k[:10] >= f"{now - timedelta(days=7):%Y-%m-%d}"}
            attempts[key] = f"{now:%Y-%m-%d %H:%M:%S}"
            state_path.write_text(json.dumps(attempts, ensure_ascii=False, indent=2), encoding="utf-8")
            wait_seconds = core.seconds_until_eligible(datetime.now(), core.last_success())
            if wait_seconds > 600:
                core.log_result(slot, "跳过：距离上次成功请求不足 5 小时，需等待超过 10 分钟")
                return
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            core.trigger(slot, config)
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def catch_up() -> None:
    config = core.load_config()
    now = datetime.now()
    due = max((_slot_datetime(slot, now), slot) for slot in config["times"])
    run_scheduled(due[1], due[0])


BG = "#F3F5F9"
INK = "#14213D"
MUTED = "#66758D"
BLUE = "#3563E9"
PALE = "#EDF2FF"
LINE = "#E4E9F1"
WHITE = "#FFFFFF"


def ui_button(parent, title: str, action, *, primary: bool = False, compact: bool = False) -> Button:
    button = Button(
        parent, text=title, command=action, font=("Microsoft YaHei UI", 10, "bold" if primary else "normal"),
        bg=BLUE if primary else "#EAF0FC", fg=WHITE if primary else "#244FBA",
        activebackground="#244FCB" if primary else "#DCE7FC", activeforeground=WHITE if primary else "#173F9F",
        relief="flat", bd=0,
        highlightthickness=0, cursor="hand2", padx=12 if compact else 17, pady=7 if compact else 10,
    )
    return button


class App(Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Codex 窗口定时器")
        self.geometry("900x680")
        self.minsize(780, 650)
        self.configure(bg=BG)
        self.time_slots = core.load_config()["times"]
        self.codex = StringVar(value=core.load_config()["codex_path"])
        self.notice = StringVar(value="设置好时间点后，点击下方按钮启用自动运行。")
        self.next_run = StringVar()

        header = Frame(self, bg="#111C35", height=118)
        header.pack(fill=X)
        header.pack_propagate(False)
        top = Frame(header, bg="#111C35")
        top.pack(fill=X, padx=28, pady=(13, 0))
        Label(top, text="CODEX  /  WINDOW TIMER", bg="#111C35", fg="#91A6D5", font=("Segoe UI", 9, "bold")).pack(side=LEFT)
        self.badge = Label(top, text="  检查中  ", bg="#26334D", fg=WHITE, font=("Microsoft YaHei UI", 9), padx=10, pady=5)
        self.badge.pack(side=RIGHT)
        Label(header, text="按计划发送 Codex 请求", bg="#111C35", fg=WHITE, font=("Microsoft YaHei UI", 19, "bold")).pack(anchor="w", padx=28, pady=(8, 0))
        Label(header, text="在你设定的时间发送一条简短请求；实际额度和重置时间由 Codex 服务端决定。", bg="#111C35", fg="#B9C7E0", font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=29, pady=(3, 0))

        body = Frame(self, bg=BG)
        body.pack(fill=BOTH, expand=True, padx=22, pady=13)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        left = Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        right = Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(9, 0))

        schedule_card = Frame(left, bg=WHITE, highlightbackground=LINE, highlightthickness=1)
        schedule_card.pack(fill=BOTH, expand=True)
        schedule_head = Frame(schedule_card, bg=WHITE)
        schedule_head.pack(fill=X, padx=18, pady=(12, 5))
        Label(schedule_head, text="每日触发时间", bg=WHITE, fg=INK, font=("Microsoft YaHei UI", 13, "bold")).pack(side=LEFT)
        ui_button(schedule_head, "＋ 添加时间点", self.add_time, compact=True).pack(side=RIGHT)
        Label(schedule_card, text="本机时间 · 到点自动运行 · 点击 × 可删除", bg=WHITE, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=18)

        list_area = Frame(schedule_card, bg=WHITE)
        list_area.pack(fill=BOTH, expand=True, padx=18, pady=(10, 7))
        self.list_canvas = Canvas(list_area, bg=WHITE, highlightthickness=0, bd=0, height=208)
        scrollbar = ttk.Scrollbar(list_area, orient="vertical", command=self.list_canvas.yview)
        self.list_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.list_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.list_inner = Frame(self.list_canvas, bg=WHITE)
        self.list_window = self.list_canvas.create_window((0, 0), window=self.list_inner, anchor="nw")
        self.list_inner.bind("<Configure>", lambda event: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")))
        self.list_canvas.bind("<Configure>", lambda event: self.list_canvas.itemconfigure(self.list_window, width=event.width))

        next_strip = Frame(schedule_card, bg=PALE)
        next_strip.pack(fill=X, padx=18, pady=(0, 12))
        Label(next_strip, text="下一次计划", bg=PALE, fg=BLUE, font=("Microsoft YaHei UI", 9, "bold")).pack(side=LEFT, padx=12, pady=10)
        Label(next_strip, textvariable=self.next_run, bg=PALE, fg=INK, font=("Microsoft YaHei UI", 10, "bold")).pack(side=RIGHT, padx=12)

        control_card = Frame(left, bg=WHITE, highlightbackground=LINE, highlightthickness=1)
        control_card.pack(fill=X, pady=(10, 0))
        Label(control_card, text="自动运行", bg=WHITE, fg=INK, font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", padx=18, pady=(10, 2))
        self.status_label = Label(control_card, text="正在读取系统任务状态…", bg=WHITE, fg=MUTED, font=("Microsoft YaHei UI", 9), anchor="w")
        self.status_label.pack(fill=X, padx=18)
        controls = Frame(control_card, bg=WHITE)
        controls.pack(fill=X, padx=18, pady=(9, 11))
        ui_button(controls, "保存并启用", self.install, primary=True).pack(side=LEFT)
        ui_button(controls, "停用", self.uninstall).pack(side=LEFT, padx=(8, 0))

        cli_card = Frame(right, bg=WHITE, highlightbackground=LINE, highlightthickness=1)
        cli_card.pack(fill=X)
        Label(cli_card, text="Codex CLI", bg=WHITE, fg=INK, font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", padx=18, pady=(16, 3))
        Label(cli_card, text="使用你已登录的 ChatGPT 订阅身份", bg=WHITE, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=18)
        path_row = Frame(cli_card, bg=WHITE)
        path_row.pack(fill=X, padx=18, pady=(13, 8))
        Entry(path_row, textvariable=self.codex, bg="#F7F9FC", fg=INK, relief="flat", font=("Segoe UI", 9), highlightthickness=1, highlightbackground=LINE).pack(side=LEFT, fill=X, expand=True, ipady=8)
        ui_button(path_row, "选择", self.browse, compact=True).pack(side=RIGHT, padx=(7, 0))
        ui_button(cli_card, "检查登录", self.check_login, compact=True).pack(anchor="w", padx=18, pady=(0, 16))

        log_card = Frame(right, bg=WHITE, highlightbackground=LINE, highlightthickness=1)
        log_card.pack(fill=BOTH, expand=True, pady=(14, 0))
        log_head = Frame(log_card, bg=WHITE)
        log_head.pack(fill=X, padx=18, pady=(15, 6))
        Label(log_head, text="执行记录", bg=WHITE, fg=INK, font=("Microsoft YaHei UI", 13, "bold")).pack(side=LEFT)
        ui_button(log_head, "刷新", self.refresh, compact=True).pack(side=RIGHT)
        self.log = Text(log_card, height=8, wrap="word", state="disabled", font=("Consolas", 9), bg="#F7F9FC", fg=INK, relief="flat", bd=0, padx=10, pady=10)
        self.log.pack(fill=BOTH, expand=True, padx=18, pady=(0, 10))
        ui_button(log_card, "立即触发一次 · 消耗额度", self.ping_now, compact=True).pack(anchor="e", padx=18, pady=(0, 15))

        footer = Frame(self, bg=BG)
        footer.pack(fill=X, padx=25, pady=(0, 9))
        Label(footer, textvariable=self.notice, bg=BG, fg=MUTED, font=("Microsoft YaHei UI", 9), anchor="w", wraplength=820, justify="left").pack(fill=X)
        self.render_times()
        self.refresh()
        self.tick()

    def tick(self) -> None:
        self.update_next_run()
        self.after(60_000, self.tick)

    def update_next_run(self) -> None:
        if self.time_slots:
            now = datetime.now()
            upcoming = min((_slot_datetime(slot, now) + timedelta(days=1), slot) for slot in self.time_slots)
            self.next_run.set(f"{upcoming[0]:%m/%d}  {upcoming[1]}")
        else:
            self.next_run.set("请添加时间点")

    def render_times(self) -> None:
        for child in self.list_inner.winfo_children():
            child.destroy()
        if not self.time_slots:
            Label(self.list_inner, text="还没有时间点。点击右上角的＋添加。", bg=WHITE, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=32)
            return
        for index, slot in enumerate(sorted(self.time_slots), 1):
            row = Frame(self.list_inner, bg="#F7F9FC", height=45)
            row.pack(fill=X, pady=(0, 5))
            row.pack_propagate(False)
            Label(row, text=f"{index:02d}", bg="#F7F9FC", fg="#95A3B8", font=("Segoe UI", 10, "bold")).pack(side=LEFT, padx=(12, 15))
            Label(row, text=slot, bg="#F7F9FC", fg=INK, font=("Segoe UI", 17, "bold")).pack(side=LEFT)
            hour = int(slot[:2])
            period = "凌晨" if hour < 6 else "上午" if hour < 12 else "下午" if hour < 18 else "晚上"
            Label(row, text=period, bg="#F7F9FC", fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(side=LEFT, padx=(14, 0))
            Button(row, text="×", command=lambda value=slot: self.remove_time(value), bg="#F7F9FC", fg=MUTED, activebackground="#FEECEC", activeforeground="#B84040", relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 16)).pack(side=RIGHT, padx=12)

    def add_time(self) -> None:
        if len(self.time_slots) >= 1440:
            messagebox.showinfo("时间点已满", "一天的每一分钟都已经添加。")
            return
        dialog = Toplevel(self)
        dialog.title("添加时间点")
        dialog.geometry("330x235")
        dialog.resizable(False, False)
        dialog.configure(bg=WHITE)
        dialog.transient(self)
        dialog.grab_set()
        Label(dialog, text="添加每日触发时间", bg=WHITE, fg=INK, font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w", padx=24, pady=(22, 4))
        Label(dialog, text="按本机时间，每天在该时间运行一次。", bg=WHITE, fg=MUTED, font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=24)
        selectors = Frame(dialog, bg=WHITE)
        selectors.pack(pady=22)
        candidate = (int(self.time_slots[-1][:2]) * 60 + int(self.time_slots[-1][3:]) + 300) % 1440 if self.time_slots else 360
        while f"{candidate // 60:02d}:{candidate % 60:02d}" in self.time_slots:
            candidate = (candidate + 1) % 1440
        hour = StringVar(value=f"{candidate // 60:02d}")
        minute = StringVar(value=f"{candidate % 60:02d}")
        ttk.Combobox(selectors, width=5, state="readonly", textvariable=hour, values=[f"{i:02d}" for i in range(24)], font=("Segoe UI", 14)).pack(side=LEFT)
        Label(selectors, text=" : ", bg=WHITE, fg=INK, font=("Segoe UI", 16, "bold")).pack(side=LEFT)
        ttk.Combobox(selectors, width=5, state="readonly", textvariable=minute, values=[f"{i:02d}" for i in range(60)], font=("Segoe UI", 14)).pack(side=LEFT)

        def save() -> None:
            value = f"{hour.get()}:{minute.get()}"
            if value in self.time_slots:
                messagebox.showwarning("时间重复", "这个时间点已经存在。", parent=dialog)
                return
            self.time_slots = core.normalize_times(self.time_slots + [value])
            self.render_times()
            self.notice.set("时间点已添加；点击“保存并启用”后生效。")
            dialog.destroy()
            self.update_next_run()

        ui_button(dialog, "添加时间点", save, primary=True).pack(pady=(0, 17))
        dialog.bind("<Return>", lambda event: save())

    def remove_time(self, value: str) -> None:
        self.time_slots.remove(value)
        self.render_times()
        self.notice.set("时间点已移除；点击“保存并启用”后生效。")
        self.update_next_run()

    def browse(self) -> None:
        path = filedialog.askopenfilename(title="选择 Codex CLI", filetypes=[("Codex CLI", "*.cmd *.exe"), ("所有文件", "*.*")])
        if path:
            self.codex.set(path)

    def refresh(self) -> None:
        try:
            times = scheduler.installed_times()
            active = bool(times) and scheduler.startup_enabled()
            self.badge.configure(text="  已启用  " if active else "  未启用  ", bg="#1B6D55" if active else "#38455E")
            self.status_label.configure(text=(f"每天 {', '.join(times)} 自动运行；登录后可补跑。" if active else "尚未启用。保存后即使关闭界面，也会按时运行。"))
        except Exception as exc:
            self.badge.configure(text="  状态异常  ", bg="#9B5A30")
            self.status_label.configure(text=f"无法读取任务状态：{exc}")
        self.log.configure(state="normal")
        self.log.delete("1.0", END)
        self.log.insert("1.0", core.read_history())
        self.log.configure(state="disabled")

    def check_login(self) -> None:
        self.notice.set("正在检查 Codex CLI 登录状态…")
        path = self.codex.get().strip()

        def work() -> None:
            ok, message = core.check_codex(path)
            self.after(0, lambda: self.notice.set(("检查通过：" if ok else "检查失败：") + message))

        threading.Thread(target=work, daemon=True).start()

    def install(self) -> None:
        try:
            times = core.normalize_times(self.time_slots)
            path = self.codex.get().strip()
            if not Path(path).is_file():
                raise ValueError("请先选择有效的 codex.cmd 或 codex.exe。")
            ready, reason = core.check_codex(path)
            if not ready:
                raise ValueError(reason)
            core.save_config({"times": times, "codex_path": path})
            scheduler.install(times)
            gaps = core.short_gaps(times)
            self.notice.set("已启用自动运行。" + (" 提醒：有时间点间隔小于 5 小时，后一请求可能不会开启新窗口。" if gaps else ""))
            self.refresh()
        except Exception as exc:
            messagebox.showerror("无法启用", str(exc))

    def uninstall(self) -> None:
        try:
            scheduler.uninstall()
            self.notice.set("已停用自动运行。时间设置和历史记录仍保留。")
            self.refresh()
        except Exception as exc:
            messagebox.showerror("无法停用", str(exc))

    def ping_now(self) -> None:
        path = self.codex.get().strip()
        if not Path(path).is_file():
            messagebox.showerror("无法触发", "请先选择有效的 Codex CLI 路径。")
            return
        self.notice.set("正在发送一次简短请求…")

        def work() -> None:
            _, message = core.trigger("手动", {"codex_path": path})
            self.after(0, lambda: (self.notice.set(message), self.refresh()))

        threading.Thread(target=work, daemon=True).start()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-slot", metavar="HH:MM")
    parser.add_argument("--run-catchup", action="store_true")
    args = parser.parse_args()
    if args.run_slot:
        run_scheduled(args.run_slot)
    elif args.run_catchup:
        catch_up()
    else:
        App().mainloop()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Scheduled tasks have no console; preserve a short diagnostic locally.
        core.log_result("程序", f"失败：{type(exc).__name__}: {exc}")
        raise
