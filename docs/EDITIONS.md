# 两种发行版本与接入教程

| 项目 | 1.00.01 · 自有 API 版 | 1.00.02 · API + Magpie 版 |
|---|---|---|
| 自有 OpenAI 兼容 API | 支持 | 支持 |
| Magpie 专用选项与教程 | 无 | 支持，可选 |
| 首次模型地址 | 空，由你填写 | 默认本机 Magpie，可改自有 API |
| 默认密钥环境变量名称 | HARNESS_API_KEY | MAGPIE_API_KEY，选自有 API 时可改 HARNESS_API_KEY |
| Magpie 软件 | 不包含 | 不包含，复用你已安装的 Magpie |
| 图标、QQ、聊天、记忆、人设 | 两版相同 | 两版相同 |

## 下载与安装

在 Releases 的 Assets 下载所需的 `qq-chatbot-1.00.01-windows-x64.zip` 或 `qq-chatbot-1.00.02-windows-x64.zip`。完整解压到独立可写目录，双击 `QQ ChatBot.exe`；不需要另装 Python。Windows 的 WebView2、.NET Framework 与 VC/UCRT 前提见 GETTING_STARTED.md。

当前修订标签为 `v1.00.01-r2` / `v1.00.02-r2`，两版均移除外部 Agent / CLI 工作绑定。程序版本号与 ZIP 文件名保留原版号；下载时核对修订标签，旧版仅供回滚。

首次启动保持全部暂停、QQ 未启用、账号及模型 ID 留空。先配置模型，再按程序设置中的首次向导保存双 QQ 账号、下载官方 QQ 组件、扫码登录与验收。两版都不会继承作者的账号、登录态、聊天或私人 soul.md。

## 1.00.01：自有 API

1. 设置 → 模型与 API 接入，仅有「自定义 OpenAI 兼容 API」。填写服务方给出的 Base URL，通常以 `/v1` 结尾；不要填写完整 `/chat/completions`。远程地址必须 HTTPS，本机回环可 HTTP。
2. 密钥环境变量名称填 `HARNESS_API_KEY` 或你选择的名称。在 Windows「编辑账户的环境变量」中自行配置同名变量；程序里不填密钥值。彻底退出托盘与核心后重开，以读取新环境。
3. 检查连接 / 读取模型，填主模型 ID；需要识图时再填视觉辅助 ID。服务方不支持清单时可手填 ID，协议需兼容 Chat Completions、工具调用，视觉需 image_url。
4. 保存设置 → 重启聊天 → 手动开启只回复 → 发一句话测试。连接检查只读模型清单，不代表推理或视觉已经通过。

本版无预设外部 API 地址、模型、密钥或 Magpie 专用入口；手改配置为 Magpie 会明确报错，不会自动换服务。详细错误排查见 MODEL_API.md。

## 1.00.02：自有 API 或可选 Magpie

自有 API 按上述步骤，先在接入方式选择「自定义 OpenAI 兼容 API」。程序不会因自有 API 失败而回退 Magpie。

已有 Magpie：在 Magpie 自行配置上游与授权并启动网关；选择「Magpie 本机网关」，地址固定 `http://127.0.0.1:3425/v1`。检查连接读取真实模型 ID，保存并重启聊天，手动开启只回复。网关若要求鉴权，自行设置 `MAGPIE_API_KEY` 环境变量；厂商密钥与订阅登录留在 Magpie。完整图文步骤在本版的 MAGPIE_SETUP.md，也可在程序内打开。

## 切换版本与回滚

两个版本分别解压到不同目录，不覆盖正在运行的安装；同一时间只运行一个聊天安装，以免端口冲突。旧程序先确认没有未结束的外部工作，创建并验证数据快照，记录 API 地址、模型 ID 与暂停状态，然后从托盘退出并停止全部。

在新安装先配置 API，再通过备份恢复入口迁移完整 JSONL 与附件。不要直接复制旧 config/local.json：旧 Magpie 配置在 1.00.01 会被拒绝；路径与账号应在新向导重新设置。Windows 环境变量由你自行管理。QQ 需在新安装重新准备组件并扫码；每台机器独立验收收发。需要开机自启或快捷方式时，只为当前安装重新登记。

回滚时退出并停止新安装，重新打开保留的旧目录；保持暂停，检查数据基线后由你决定恢复回复。不要清空日志、配额、去重或 QQ profile。

## 为维护者构建

在主源码根目录执行，先运行测试，再构建两种版本：

```powershell
python -m unittest discover -s tests -q
python tools/build-editions.py --sevenzip 'C:\Program Files\7-Zip\7z.exe'
```

需要 Windows x64、VS C++/Windows SDK、7-Zip 和构建依赖；普通使用者不需要这些。仅源码包用 `python tools/build-editions.py --source-only`，单一版本可加 `--edition 1.00.01` 或 `--edition 1.00.02`。输出位于 dist，各含 ZIP、SHA256 校验文件；源码包不带 `windows-x64` 后缀。不会覆盖已有 ZIP 或 `.runtime/edition-builds/<版本>`，需要重建时先把旧产物与该构建目录移到自己选定的归档目录，不删除私人数据。

构建链先走 tools/package_release.py 隐私白名单，再由 tools/release_editions.py 改版本、公开默认值和 UI，最后在各自目录校验与打包。src/core/edition.py 校验运行时接入权限，所有模型请求仍走 src/modules/model.py。公共下载缓存仅复用固定运行组件，不复制本机环境或凭据。主源码的 config/local.json、data、logs、backups、.runtime 和私人人设均不进入包。
