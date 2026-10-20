## 本版重点：不再强制下载 QQ 客户端

如果你电脑上**已经装了 QQ**，本版会直接复用它启动机器人，省掉约 300 MB 下载。只有探测不到可用 QQ 时才下载独立客户端。

复用的只是 QQ 的可执行文件。机器人账号的登录态仍保存在独立目录 `Documents\Tencent Files\NapCat`，**不会和你日常使用的 QQ 串号**，也不会修改系统 QQ 的任何文件。

> ⚠️ 一个前提：被复用的 QQ 要能被腾讯服务器接受。版本过旧时登录会报 `error 45`（版本过低）。遇到这种情况，升级你的 QQ，或删掉 `config/local.json` 里的 `qq.client_path` 后重新点「准备组件」，程序会下载一份独立客户端。程序不会自动升级你的 QQ。

## 下载

| 文件 | 说明 |
|---|---|
| `qq-chatbot-0.10.1-windows-x64.zip` | **Windows 绿色包（普通用户选这个）**，自带 Python 运行时与解压工具，解压后双击 `QQ ChatBot.exe` |
| `qq-chatbot-0.10.1.zip` | 干净源码包，给开发与维护者 |

两个包都附同名 `.sha256` 校验文件。

不要下载 GitHub 自动生成的 `Source Code` 压缩包，它不是绿色包。

## 本版修复

- **外部 Agent 回执乱码**：工作转交的外部 CLI 输出不再硬编码 UTF-8，兼容 Windows 英文区域（cp1252）和中文区域（GBK），回执不再显示成乱码。
- **绿色包桌面报错误导**：缺少 tkinter 时，桌面窗口启动失败提示不再推荐不可用的备用界面，改为引导用浏览器打开 `http://127.0.0.1:8765`。
- **校验文件换行符**：`sha256` 文件改用 LF，Linux/macOS 上 `sha256sum -c` 不再报「No such file or directory」。源码包也补上了校验文件。
- **CI 误报**：桌面自启路径的测试兼容 Windows 8.3 短名（`RUNNER~1`）。

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
