# 公开发布步骤

当前提供 1.00.01（仅自有 API）与 1.00.02（自有 API + 可选 Magpie），采用 MIT。主分支源码版本为 1.00.02。不要直接压缩整个在用项目或推送未经审查的旧 Git 历史。

## 1. 生成干净源码包

在项目根目录运行 `tools/test.bat`；检查默认配置账号与模型留空、高权限关闭、角色卡为通用模板，再运行：

```powershell
.\.venv\Scripts\python.exe tools\package-release.py
```

主源码包位于 `dist/qq-chatbot-1.00.02.zip`。同名包不会覆盖；需要重建时通过 `--output` 指定新的 ZIP 文件名。包内 `manifest.json` 记录每个文件的 SHA256，不包含个人安装状态。完整双版本构建见 [EDITIONS](EDITIONS.md)。

白名单仅包含源码、工具、测试、公开文档和步骤插图、依赖清单、通用配置与当前图标。排除 .git、虚拟环境、运行时、data/logs/backups、local.json、`*.local.*`、自定义插件和未使用的旧图标。发布器额外检测本机账号、称呼、绝对路径及常见凭据模式，发现则拒绝打包并只显示文件名。它不是通用秘密扫描器，最终仍须审查包内文件和素材来源。

## 2. 建立公开仓库

将 ZIP 解压到一个新的空目录，检查其中无个人配置、账号、聊天、QQ 登录态和旧 .git。在该新目录用 GitHub Desktop 或自己的 Git 客户端创建仓库并发布到自己的账号；远程地址和可见性由自己选择。本工具不创建仓库、不提交或推送，也不需要 GitHub token。

若准备复用已有仓库，先审查其全部历史；只加 .gitignore 不能删除已经进入历史的私人数据。不要把个人安装的 .git 复制到干净目录。

## 3. 构建可下载的 Windows 版本

源码上传不等于已经有可执行版。干净源码包含 `.github/workflows/windows-release.yml`；Actions 手动运行 Windows portable release 时可选 all 或单版，产物保留在该次构建的 Artifacts，不自动发布。

标签 `v1.00.01` 与 `v1.00.02` 各自只构建对应版本，并在自己的 Release 附上 Windows ZIP、源码 ZIP 及两个 SHA256 文件。主源码可以派生两版；1.00.01 专属源码不能构建 1.00.02。已公开的标签不移动，后续修订使用 `v1.00.01-r1` / `v1.00.02-r1`（再修订递增 r2），版本接入差异和包名保持不变。回退时解压旧 Release 到独立目录，按 HANDOFF 恢复私有数据，勿覆盖在用安装。重跑工作流只更新该标签资产，不删除 Release 或强推标签。仓库工作流使用 GitHub 自动凭据，无需填写个人 GitHub token。

本机构建命令、依赖与许可见 [WINDOWS_BUILD](WINDOWS_BUILD.md)。用户按需下载 `qq-chatbot-1.00.01-windows-x64.zip` 或 `qq-chatbot-1.00.02-windows-x64.zip`，不要下载自动生成的 Source code ZIP。

发布说明附上 [新手教程](GETTING_STARTED.md)，说明首次需要两个QQ账号和自己的模型服务，之后才能扫码聊天。公开包不含作者的模型访问权限或登录态。

## 4. 新用户签收

按 README 在另一目录/机器安装，选择自己的模型和账号，再按 HANDOFF 完成重启、换模型、备份和恢复。定期监管由新用户在自己选择的 Agent 中配置，不附带原作者任务、通知渠道或 Agent 账号。

旧用户原地升级时保留 data、local.json 与私有角色卡；源码默认值不会迁移外部 Agent 定时任务。升级后读取本机状态确认暂停与账号正确，再决定是否恢复回复。
