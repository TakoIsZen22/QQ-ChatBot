# Phase 2–4 能力配置与权限

所有 JSON 片段都是 `config/local.json` 的合并片段，不能无意覆盖已有模型/主人配置。也可以在页面读取完整配置后修改、保存、重启。任何凭据不填在这些片段中。

## 日记、情绪、印象、成长

记忆/日记可由界面手动维护，也可由模型调用受限工具。日记每天最多三条、一两句、140 字，拒绝部分常见总结句；具体性仍需人格提示和人工抽查，程序无法理解所有语义。情绪有原因和小时有效期，跨会话保留、过期淡回平静。

印象默认每 24 小时刷新一次，亲密度默认 10，不从情绪机械推断好感涨跌。可插拔打分示例：

```json
{"plugins":{"enabled":true,"allowed":["impression_example"]},"impression":{"plugin":"impression_example"}}
```

仅加载项目 `user_plugins` 中精确允许的 Python 文件，接口为 `score(messages,current) -> {affinity,text}`。这是可信本机代码，不是沙箱，启用前审核源代码。成长工作/陪伴/学习三数归一化并写历史，立即进入下一轮模型上下文；不是随机篡改人格卡。

`role.evolution_enabled=false` 锁住稳定线。开启后，用户在能力工作台审核写入，模型反思保存在 reflection 记忆中，不能自行改系统卡或权限。每次加载最多最近五条稳定线。

## 主动、约定与睡眠

将 `awakening.enabled` 改 true，顶部再选择「允许主动」。随机检查 45–110 分钟、主人静默至少 15 分钟、概率 0.35、23:00–08:00 不打扰。启动不立刻主动。期间收到新消息则放弃本次主动。

约定时间需 ISO8601 且有时区，如 `2026-10-21T10:00:00+08:00`。到点提醒也受主动总开关、免打扰与限流约束，不会为了准点绕开静音。关闭主动时承诺保留，恢复后再判断是否提醒。

凌晨 4 点有模型且非全暂停时，静默整理当天聊天，今日无记录时取最近少量记录。日记仍遵守每日上限；反思标注为模型未核实。无聊天直接跳过，不强写。Windows 合盖、系统休眠时程序不运行；错过凌晨不会伪称已整理。睡眠整合和学习不会向主人发消息。

## 表情与视觉

辅助视觉模型名称填 `model.auxiliary`，走当前选择的模型 API。同一个兼容图片的模型可同时用于 main/auxiliary，但不要把不支持图片的路由填为辅助模型。

NapCat get_image 必须返回可读本机路径；harness 复制到 data/media，将图片送本机网关的辅助视觉路由描述，再记录 media_id。没有图像描述，不准收藏；模型不能从未知备注瞎猜。启用 `stickers.enabled=true` 后支持 list_stickers / sticker_note / collect_sticker / send_sticker，默认一天最多五轮，每轮一张、单独图像消息。认真、道歉等关键词会额外阻止表情，语义边界仍依赖人设提示。不开启时不会发送。

本机聊天窗口当前展示表情描述；真实图片通过 QQ 独立 image segment 发出。收藏来源为已经观察过的主人图片，不抓取任意 URL。辅助视觉需按本次安装选择真实可用的模型，并用自己的图片测试；文本连通不代表视觉通过。

## 网易云 PC

`music.enabled=true` 开启只读；打开网易云并播放，在 Windows 的系统媒体控件中确认歌曲可见。工作台点“读取当前歌曲”。实现使用 Windows SMTC；没有暴露 SMTC 的网易云版本明确报错，不通过窗口标题猜歌词/歌曲状态。

一起听双向控制需要主人单独授权后再改 `music.allow_control=true`。工作台支持上一首/下一首/播放/暂停；主人在网易云操作，下一次读状态可以看到变化。模型不会自己切歌或每首歌点评。当前不提供曲库搜索、任意点歌的通用接口；可通过已审核插件扩展。

歌词与热评只读已授权 HTTP 来源：须同时填 `music.allowed_sources` 与 `learning.allowed_hosts`，并开启 learning。调用本机 API：

```powershell
$headers=@{'X-Harness-Local'='1'}
$body=@{action='lyrics';url='用户已授权域名上的具体歌词或评论页面'} | ConvertTo-Json
Invoke-RestMethod 'http://127.0.0.1:8765/api/music' -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

会返回网页文本片段，不绕过登录/付费墙；查不到直说查不到。歌词/热评版权由来源决定，不自动上传分享。

## 本机 whisper 与语音输出

核心已在 Python 3.14 验证；whisper/PyTorch 单独使用 **Python 3.11** 环境。本次已安装 CPU torch/openai-whisper/scipy，下载 base 权重，完成 Windows 中文 TTS → 本机 whisper 的实际转写；16bit PCM WAV 无需 ffmpeg。其他压缩音频仍需 ffmpeg。

```powershell
# 在项目根目录运行
.\tools\install-voice.bat
```

脚本选择已安装的 Python 3.11（包括本机 uv/Astral provider），创建 .venv-voice，安装 CPU 版 torch、openai-whisper 和 scipy。无3.11时明确失败，不自行替换系统Python。16bit PCM WAV 可直接读入并本机重采样，无需 ffmpeg；其他压缩音频需另装 ffmpeg。NapCat get_record 默认请求 wav。

首次运行 whisper 会下载模型权重，依尺寸和网络耗时；这是模型下载，不是上传语音。CPU 默认 fp16=false，可先用 base。配置：

```json
{"voice":{"enabled":true,"python":"E:\\QQ Bot Harness\\.venv-voice\\Scripts\\python.exe","whisper_model":"base","language":"zh"}}
```

本机音频放 `data/media` 内，工作台填绝对路径进行转写；QQ 语音先由本机 NapCat get_record 转 wav，再由本机 whisper 子进程转文字。拒绝从事件给出的第三方 URL 下载转写服务，不提供任何云 STT 回退。

语音回复提供 `tools/tts.py`，使用 Windows 自带 System.Speech 离线中文音色，本机已实际合成 16kHz WAV。文字通过 stdin JSON 传给固定脚本，不插入 PowerShell 代码。Windows 没有中文音色时明确报错，需要用户在系统设置安装中文语音。

`voice.tts_command` 为 argv 数组，harness 在其后附加两个参数：`文本`、`输出 wav 绝对路径`。本机内置工具的配置为：

```json
{"voice":{"tts_command":["E:\\QQ Bot Harness\\.venv\\Scripts\\python.exe","E:\\QQ Bot Harness\\tools\\tts.py"]}}
```

也可选择经审核的其他本机 TTS，但不得使用云 TTS。未配置时明确文字降级，深夜也优先文字。合成通过不等于真实 QQ 语音往返已验收。

## ADB 专用设备

从 Android 官方安装 platform-tools，`adb devices` 查看 serial。仅模拟器或没有支付 App 的闲置备用机；不能连接主力机。设备串号由用户显式选择，harness 无法从硬件自动证明“备用机”身份。

```json
{"devices":{"enabled":false,"adb_path":"adb","serial":"","device_kind":"","allowed_packages":[]}}
```

填实际 serial、`device_kind` 为 `emulator` 或 `spare`、允许操作的精确包名列表，确认是专用设备后再 enabled=true。每步检查已安装包和前台包，检测到支付/银行或微信/QQ 等高风险综合 App 就拒绝整个设备；名称检测加前台精确允许表是防线，不能替代无支付 App 的设备隔离。

中文输入必须安装 ADBKeyboard，手动选为当前输入法；缺失/未启用会明确报错。不要授予本应用任意 shell 命令；仅 tap、swipe、text、screenshot，坐标验证且每步重新校验前台包。游戏内支付/网页支付无法单靠包名识别，允许清单只放经过核查的无此类能力的 App。

连招保存及回放通过 POST `/api/device`：

```json
{"action":"macro_save","name":"open_note","steps":[{"action":"tap","args":{"x":100,"y":200}},{"action":"text","args":{"text":"你好"}}]}
```

```json
{"action":"macro_replay","name":"open_note"}
```

最多二十步，截图保存在 data/device-screen.png。暂停取消当前子进程并阻止下一步，已经点击的动作不能撤回。

## 搜索、交叉查证与闲时学习

联网默认关。开启 learning 后，仅精确允许的 HTTPS 域名可读取，拒绝内网/保留 IP、凭据 URL、自动跳转，DNS 检查后固定解析结果。每页最多 200KB，每天最多三项学习任务。至少两份不同域名的材料才能归档。资料与模型分析都标注“待人工核实”，绝不把来源数量当作验证成功。

工作台支持输入已批准的来源收集。自动学习在闲置 ≥15 分钟、队列空、非暂停时，读取 `idle_plans`，每个 topic 成功后不再重复，每日失败只试一次。示例：

```json
{
  "learning": {
    "enabled": true,
    "allowed_hosts": ["docs.python.org", "www.sqlite.org"],
    "idle_plans": [{"topic":"核对本地存储的耐久性边界","urls":["https://docs.python.org/3/library/os.html","https://www.sqlite.org/atomiccommit.html"]}]
  }
}
```

搜索支持配置含 `{query}` 的公开 HTML 搜索 URL，搜索站域名和结果域名都需放进 allowed_hosts。不提供隐藏登录、搜索 API 密钥或绕过风控。请求 POST `/api/study` `{ "action":"search", "query":"要查的内容" }` 获取允许域名结果；idle_plan 省略 urls 时自行搜索 topic，再对不同域名材料进行对照。HTML 结构可能变化；无两份可用来源时失败并记录日志，不编搜索结果。

## MCP 与社区扩展

MCP 支持 stdio JSON-RPC initialize / tools/call，按服务器名、工具名精确允许；不是自动联网工具发现器。不启动未配置的服务、不把全套工具暴露给模型。例子用附带测试服务，不含真实外部权限：

```json
{"plugins":{"enabled":true,"mcp":[{"name":"echo-demo","command":["E:\\QQ Bot Harness\\.venv\\Scripts\\python.exe","E:\\QQ Bot Harness\\tests\\fixtures\\mcp_server.py"],"allowed_tools":["echo"],"timeout_seconds":20}]}}
```

工作台输入 name=`echo-demo`、tool=`echo`、arguments=`{"text":"你好"}`。生产接入替换为经用户审核的本机可执行 argv，精确列出工具；进程 stderr 当前不采集，协议错误会进入日志。协议测试以 2024-11-05 版本协商；其他版本必须实测兼容。

社区分享只生成本地 `share_drafts.jsonl` 草稿，POST `/api/share` 写入；不会自动上传主人聊天、记忆或金句。`publish_enabled` 目前为保留配置，未提供公共社区上传端点。具体社区插件应独立审核、配置来源、核查隐私与不可撤回配额后再加，不可用任意 MCP 发送来绕过铁律。
