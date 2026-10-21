# QQ ChatBot 1.10.01 · 仅自有 API

本版面向直接接入自己模型 API 的使用者。支持 OpenAI 兼容 API，不提供 Magpie 专用选项或教程；聊天、QQ、人设与记忆功能与 1.10.02 相同，不包含模型服务或额度。

## 下载

- Windows x64：`qq-chatbot-1.10.01-windows-x64.zip`，完整解压后双击 `QQ ChatBot.exe`，自带 Python 与原生 QQ 宿主。
- 源码：`qq-chatbot-1.10.01.zip`，需要自行安装开发环境。
- 两包各附 `.sha256` 校验文件；Windows 的 WebView2、.NET 与 VC/UCRT 前提见教程。不要把 GitHub 自动生成的 Source code ZIP 当作桌面安装包。

## 相比 1.00.01-r2 的改动

- QQ 接入增加扫码 / QQ 账密双入口、可选 Windows DPAPI 加密记住 QQ 密码与启动时自动登录，以及验证码 / 设备验证入口。默认不记住、不自动登录；主动停止 QQ 会关闭自动登录。QQ 密码与登录材料不随发布包分发。
- 增加可选本机程序账号锁：记住密码、自动登录、托盘锁定、修改密码与持久化输错冷却。程序账号与 QQ 账号是两套独立登录。
- 群聊从监听扩展为逐群开启的文字回复：支持 @回复或每条文字回复、公开群人设、隔离上下文、群静音、清空上下文与未回复原因诊断。默认仅监听，仍需逐群授权；群对话不读取私人 soul.md、私聊记忆或日记，不执行工具。
- 优化 QQ 状态同步：拆分快速状态更新与较慢的信息读取，区分“已登录”和“通道连接”，补充心跳离线与恢复处理，减少状态显示滞后。
- 增加本机 QQ 检测与按版本适配清单，仅复制已支持版本的程序文件到独立运行目录，避免读取日常 QQ 的账号目录；未知版本仍拒绝加载。
- 保留用户提供的默认图片图标，以及昵称、角色形象、程序图标和私人 soul.md 的程序内定制入口。两版均不提供外部 Agent / CLI 绑定或工作转交。
- 固定版本规则：末两位 `01` 仅 API，`02` API + 可选 Magpie；以后功能升级使用例如 `1.11.01 / 1.11.02`，末两位不再承担补丁计数。运行时与发布链校验未知后缀并拒绝。

## 验证范围与已知限制

本轮覆盖 Python 回归、Node 原生协议夹具、发行权限与隐私白名单校验；Windows 构建和包内自检由对应标签的 Actions 执行。隔离 WebView2 登录界面与 Windows DPAPI 已在开发机验证。协议夹具不等于腾讯服务器实连。

此前本机扫码登录、主人文字接收和一次模型回复已由使用者确认；**新加 QQ 账密、验证码 / 设备验证、真实群回复、断网恢复及新机器安装仍待实测**。当前适配清单仅有 **QQ 9.9.33-52230**，不保证电脑上任意 QQ 版本可用。QQ 历史补拉、语音文件获取、图片上传发送尚未实现。

## 安装、升级与回滚

首次运行保持全部暂停，账号、API 地址与模型 ID 留空。按 [新手教程](https://github.com/TakoIsZen22/QQ-ChatBot/blob/v1.10.01/docs/GETTING_STARTED.md) 配置双 QQ 账号和自己的 API；凭据自行配置在 Windows 环境变量，程序只保存变量名。详见 [API 接入](https://github.com/TakoIsZen22/QQ-ChatBot/blob/v1.10.01/docs/MODEL_API.md)、[QQ 登录](https://github.com/TakoIsZen22/QQ-ChatBot/blob/v1.10.01/docs/QQ_SETUP.md)、[本机程序账号](https://github.com/TakoIsZen22/QQ-ChatBot/blob/v1.10.01/docs/LOCAL_LOGIN.md) 和 [群聊教程](https://github.com/TakoIsZen22/QQ-ChatBot/blob/v1.10.01/docs/GROUP_MONITOR.md)。

升级前保持暂停，备份完整 JSONL、附件与私人人设，私下另存本机配置；退出并停止旧安装后，将新版解压到新目录。不要覆盖在用目录或直接复制旧 Magpie 配置到本版。按 [交接手册](https://github.com/TakoIsZen22/QQ-ChatBot/blob/v1.10.01/HANDOFF.md) 恢复数据并核对基线，在新安装重新准备 QQ 后手动启用回复。回滚时停止新版并打开保留的旧目录与快照，不删除日志、配额或去重记录。

需要 Magpie 专用接入，请下载 [1.10.02](https://github.com/TakoIsZen22/QQ-ChatBot/releases/tag/v1.10.02)。原创代码为 MIT；第三方组件与图片权利见 [NOTICE](https://github.com/TakoIsZen22/QQ-ChatBot/blob/v1.10.01/NOTICE.md)。
