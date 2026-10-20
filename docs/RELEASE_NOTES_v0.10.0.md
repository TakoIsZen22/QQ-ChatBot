## 首次公开发布

QQ ChatBot v0.10.0 — 跑在自己电脑上的个人 AI 伴侣。重长期记忆与人格养成，Windows 桌面端 + QQ 通道，数据全部存在本地。

### 下载

| 文件 | 说明 |
|---|---|
| `qq-chatbot-0.10.0-windows-x64.zip` | **Windows 绿色包（普通用户选这个）**，自带 Python 运行时与解压工具，解压后双击 `QQ ChatBot.exe` |
| `qq-chatbot-0.10.0.zip` | 干净源码包，给开发与维护者 |

两个包都附同名 `.sha256` 校验文件，可先校验再解压。

不要下载 GitHub 自动生成的 `Source code (zip)`，它不是绿色包。绿色包要**完整解压**后运行，不要在压缩包里直接双击，也不要放在 Program Files。

### 新手需要准备什么

1. **两个 QQ 号** — 你的主人号 + 一个独立的机器人号（不能相同）。程序不注册 QQ、不索取密码，两个号需要你手动加好友并确认申请。
2. **一个模型来源** — 二选一：
   - 用 [Magpie](https://github.com/yetone/magpie) 本地网关（地址固定 `http://127.0.0.1:3425/v1`），上游与订阅由你自己配置；
   - 或直接接自己的 OpenAI 兼容 API，填 Base URL 和模型 ID。
3. **约 3 GB 空间** — 首次向导会下载 QQ 组件。

NapCat 与独立 QQ 客户端**不用手动下载**：向导第 4 步一键自动完成（从官方 GitHub / 腾讯 CDN 拉取固定版本，按 SHA256 校验，约 350 MB），并使用独立目录，**不修改你系统里正在用的 QQ**。

还需要 Microsoft Edge WebView2 Runtime（常见 Windows 11 已自带）。

完整图文教程见仓库里的 `docs/GETTING_STARTED.md`，程序内「程序设置 → 新手教程」也能直接读。

### 功能

十二个模块：对话 / 记忆 / 角色 / 印象 / 日记 / 音乐 / 成长轨迹 / 学习 / QQ 桥接 / 设备 / 模型 / 插件。

聊天之外，工作可明确转交给你绑定的通用 CLI 或桌面 Agent（MCP / 本机接口）。模型只能生成待你确认的草稿，不会自动派发；回执单独标注来源，不会被聊天模型当成指令执行。

安全边界：不加陌生人、不自动同意好友、不群 @全体、不碰支付银行 App；单聊限流 20 条/分；三档保命开关（一键全停 / 只回复不主动 / 群里不说话）；语音只在本机转写；密钥只存环境变量名，程序不读取也不打印凭据值。

数据全部是本机明文 JSONL，复制即备份。`data/`、`logs/`、`.runtime/`、人设文件与账号配置都不在发布包内。

### 给维护者

- 交接与运维手册：`HANDOFF.md`、`AGENTS.md`
- 只读巡检接口：`tools/supervise.py --json`（schema `dafeiyu.supervision.v1`），任意 Agent 或任务计划程序都能调用
- 工作转交边界：`docs/AGENT_WORK.md`
- 发布流程：`docs/RELEASING.md`

MIT 许可。素材与第三方组件说明见 `NOTICE.md`。
