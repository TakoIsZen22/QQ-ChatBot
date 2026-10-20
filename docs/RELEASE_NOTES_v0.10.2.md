## 本版重点：复用系统 QQ 时会先检查版本

上一版开始优先复用本机已安装的 QQ。本版补上一个关键校验，避免用户白等。

**腾讯服务器要求 QQ 的 buildId 不低于 40768**，更旧的版本登录会被直接拒绝（`error 45`，提示"QQ版本过低"）。本版在复用前就会读 `versions/config.json` 里的 `buildId`：

- 版本够新 → 正常复用，省掉约 300 MB 下载
- 版本过旧 → **自动改用独立客户端**，并在向导里提前说明原因，不让你扫完码才发现被拒

门槛值登记在 `config/runtime-downloads.json` 的 `qq.min_build_id`，跟随 QQ 版本一起维护，不硬编码在代码里。

> 顺带一提：NapCat 官方说明同样建议 buildId 40768 以上，本项目锁定的 QQ 9.9.33-52230 属于官方实测版本。

## 下载

| 文件 | 说明 |
|---|---|
| `qq-chatbot-0.10.2-windows-x64.zip` | **Windows 绿色包（普通用户选这个）**，自带 Python 运行时与解压工具，解压后双击 `QQ ChatBot.exe` |
| `qq-chatbot-0.10.2.zip` | 干净源码包，给开发与维护者 |

两个包都附同名 `.sha256` 校验文件。

不要下载 GitHub 自动生成的 `Source Code` 压缩包，它不是绿色包。

## 本版修复

- 复用系统 QQ 前校验 buildId，过旧则自动改用独立客户端并说明原因。
- 外部 Agent 回执编码不再硬编码 UTF-8，兼容 Windows 英文区域（cp1252）与中文区域（GBK）。
- 绿色包缺少 tkinter 时，桌面启动失败提示改为引导使用浏览器界面，不再推荐不可用的备用界面。
- `sha256` 校验文件改用 LF 换行，Linux/macOS 上 `sha256sum -c` 不再报错；源码包也补上校验文件。
- 桌面自启路径断言兼容 Windows 8.3 短名（`RUNNER~1`），CI 上不再误报。

## 新手需要准备什么

1. **两个 QQ 号** — 主人号 + 独立机器人号（不能相同），需手动加好友。
2. **一个模型来源** — Magpie 本地网关，或自己的 OpenAI 兼容 API。
3. **约 3 GB 空间**（复用本机 QQ 时占用更少）。

NapCat 会自动从官方 GitHub 下载并校验，约 34 MB。

完整教程见 `docs/GETTING_STARTED.md`，程序内「程序设置 → 新手教程」也能直接读。

## 安全边界

不加陌生人、不自动同意好友、不群 @全体、不碰支付银行 App；单聊限流 20 条/分；三档保命开关；语音只在本机转写；密钥只存环境变量名。

`data/`、`logs/`、`.runtime/`、人设文件与账号配置都不在发布包内。

## 给维护者

- 只读巡检：`tools/supervise.py --json`（schema `dafeiyu.supervision.v1`）
- 交接与运维：`HANDOFF.md`、`AGENTS.md`
- 工作转交边界：`docs/AGENT_WORK.md`

MIT 许可。素材说明见 `NOTICE.md`。
