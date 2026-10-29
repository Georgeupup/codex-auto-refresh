# Codex 窗口定时器

一款 Windows 图形工具：在每天指定的时间，使用你已经登录的 Codex CLI 发送一条简短请求。适合想在工作前安排一次 Codex 请求、又不想每天手动打开终端的用户。

> **请先了解：**本工具发送的是真实请求，会消耗 Codex 使用量；它不能充值、增加额度或强制重置 5 小时窗口。请求成功也不等于重置时间发生变化。请以 [Codex 使用量页面](https://chatgpt.com/codex/settings/usage)显示的额度和重置时间为准。

## 下载与准备

1. 电脑需要 Windows 10/11、网络连接，以及已安装的 Codex CLI。可按 [Codex 官方安装说明](https://learn.chatgpt.com/docs/cli)安装；如果已有 Node.js 和 npm，也可在 PowerShell 中运行 `npm install -g @openai/codex@latest`。
2. 在 PowerShell 中运行 `codex login`，选择 **使用 ChatGPT 登录**，完成浏览器登录。运行 `codex login status`，确认显示 ChatGPT 登录。API Key 登录不会使用 ChatGPT 订阅额度。
3. 从本仓库下载 [CodexWindowStarter.exe](release/CodexWindowStarter.exe)：在文件页面点击右上角的下载按钮。把它放到一个固定目录，例如 `C:\Tools\CodexWindowStarter\`，然后双击打开。程序不包含 Codex CLI，不能替代第 1 步。

## 设置定时运行

1. 默认时间为 **06:00、11:00、16:00、21:00**。点击 **「＋ 添加时间点」**，在弹出的选择框中选小时和分钟；点击某一行右侧的 **×** 可以删除时间点。时间使用电脑的本地时区。
2. 检查右侧显示的 `codex.cmd` 或 `codex.exe` 路径，点击 **「检查登录」**。如果电脑上有多个 CLI，程序会优先选择它能找到的较新版本；必要时点击 **「选择」**手动指定。
3. 可以点击 **「立即触发一次 · 消耗额度」**进行实际测试。它会发送一条请求，成功后在执行记录中显示本次 token 数。
4. 点击 **「保存并启用」**。程序会为每个时间点创建 Windows 计划任务，并添加当前用户登录后的补跑启动项。此后可以关闭软件窗口，计划任务仍会运行。
5. 点击 **「停用」**会删除本工具创建的计划任务和启动项，保留时间设置与执行记录。

首次启用后请不要移动或删除 exe。要换位置或升级程序，先在旧程序中点击「停用」，再在新位置打开程序并点击「保存并启用」，让 Windows 任务指向新文件。

## 运行规则与限制

- 每个时间点最多尝试一次，不会持续重试。成功以 Codex CLI 返回 `turn.completed` 事件为准；「检查登录」仅检查 CLI 的登录状态，不能保证实际请求成功。
- 电脑需要开机、联网，且当前 Windows 用户已登录。电脑关机或休眠时不能准点执行；重新登录后，如果最近一个计划时间距今不足 5 小时且尚未尝试，程序会补跑一次。
- 程序只知道**自己**上次成功请求的时间，不知道你在 Codex 桌面端、IDE 或其他地方的使用情况。若离本工具上次成功请求不足 5 小时，它最多等待 10 分钟；超过 10 分钟则跳过。服务端的真实窗口仍以使用量页面为准。
- 少于 5 小时的相邻时间点会在界面提示。请求不会提前重置尚未结束的额度窗口。订阅计划、模型、上下文和推理量都可能影响实际消耗。
- 配置、执行记录和最近成功时间保存在 `%LOCALAPPDATA%\CodexWindowStarter\`。程序不读取或保存 OAuth 令牌，也不保存完整模型回复。认证由 Codex CLI 管理。

## 常见问题

**「检查登录」通过，但手动触发失败？** 这两个操作不同：前者运行 `codex login status`，后者真正调用模型。先在 PowerShell 中运行 `npm install -g @openai/codex@latest` 更新 CLI，再检查软件中的 CLI 路径，并查看执行记录。如果仍失败，可在终端运行 `codex login` 重新登录。

**为什么只让模型回复 OK，却显示很多 tokens？** Codex CLI 还会附带自身的上下文，token 数不等于提示词的字数，也不等于使用量页面显示的额度百分比。

**为什么到了时间，额度没有刷新？** 本工具没有重置额度的接口，只负责发送请求。窗口是否变化由 Codex 服务端决定；请查看使用量页面上的下次重置时间。

## 从源码运行或打包

需要 Windows、Python 3.12 或更新版本。在 PowerShell 中运行：

```powershell
python -m pip install -r requirements-build.txt
python app.py
```

要自行构建单文件 exe：

```powershell
.\build.ps1
```

输出为 `dist\CodexWindowStarter.exe`。源代码入口为 `app.py`；`core.py` 负责配置与 CLI 请求，`scheduler.py` 负责 Windows 计划任务和启动项。

## 致谢与许可

定时发送请求的想法参考了 [CCLimitPing](https://github.com/wavever/CCLimitPing)。本项目未复制其代码或捆绑其程序。项目采用 [MIT 许可证](LICENSE)。
