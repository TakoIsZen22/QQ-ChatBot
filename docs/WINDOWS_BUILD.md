# Windows 绿色包构建与依赖来源

普通使用者阅读 GETTING_STARTED.md，不需要执行构建。

## 构建机

Windows x64、Python 3.11/3.13、pip、7-Zip 完整版、系统 .NET Framework C# 编译器。新建干净的源码目录，在项目根执行：

```powershell
python tools/build-windows.py --sevenzip 'C:\Program Files\7-Zip\7z.exe'
python tools/package-release.py
```

前者从 package_release 的隐私白名单产生干净源码，再下载固定 CPython embeddable x64、跨版本安装锁定的 Windows cp313 wheels、复制独立 7-Zip 并编译窗口启动器。不会复制本机 `.venv`、账号、登录态、环境变量或运行数据。

输出 `dist/qq-chatbot-版本-windows-x64.zip` 与 `.sha256`。后者输出独立源码 ZIP。构建中间目录为 `.runtime/builds/qq-chatbot-版本-windows-x64`；重复构建同一版本时先保留并移动旧中间目录和旧 ZIP 到明确的归档目录，不覆盖、也不递归清理工作目录。下载缓存 `.runtime/public-downloads` 可复用。

## 运行机制

`QQ ChatBot.exe` 是 .NET Framework 窗口启动器，只接受预设开关，以绝对路径启动 `_runtime/pythonw.exe -m src.desktop`。CPython `_pth` 固定到内置标准库、vendored site-packages 和本安装根；不依赖系统 PATH 或 Python。GUI、核心、QQ启动、备份恢复复用同一私有运行时；源码运行仍使用原来的独立虚拟环境。

运行时首次不包含 QQ、NapCat 或登录态。向导下载固定版本并校验 SHA256，写入本目录 `.runtime`；只解压 QQ，不运行系统 QQ 安装器。OneBot HTTP/WS 与 NapCat WebUI 首次即监听127.0.0.1；WebUI 认证默认值由 NapCat 自己初始化，harness 不生成或读取它。

系统 WebView2、.NET Framework、VC/UCRT 需可用，绿色包不会静默安装系统组件。缺失时向导教程指向微软官方入口。Windows10/11 x64 是目标平台；不同干净机器的冷启动、手机扫码与设备验证仍需独立验收。

## 来源与许可

`config/runtime-downloads.json` 集中记录固定版本、官方下载 URL、SHA256、体积和解压限制。升级组件必须同步修改并重新验证，不能改成不校验的 latest 下载。

- CPython 3.13.16：[Python 官方发布页](https://www.python.org/downloads/release/python-31316/)，包内 `_runtime/LICENSE.txt` 保留 PSF/第三方许可。[官方 embeddable 说明](https://docs.python.org/3.13/using/windows.html#the-embeddable-package)。
- Python 依赖：`requirements.windows.lock.txt` 是合并锁文件，wheel 自带 dist-info/许可证保留。纯 Python 的 proxy_tools 在构建机从固定版本生成 wheel，用户端不运行 pip。
- 7-Zip 26.04：[官方发布](https://github.com/ip7z/7zip/releases/tag/26.04)。包内 `_tools/7zip/License.txt` 保留许可（LGPL、BSD 及 unRAR 限制）；未修改二进制，[对应源码](https://github.com/ip7z/7zip/releases/download/26.04/7z2604-src.7z) 可获得。仅捆绑解压所需7z.exe/7z.dll和许可。
- NapCat 4.18.38：[官方版本](https://github.com/NapNeko/NapCatQQ/releases/tag/v4.18.38)，从其发布资产 digest 取得 SHA256，不随本项目 ZIP 捆绑。
- QQ 9.9.33-52230：腾讯官方 CDN，URL 与 SHA256 对照 [NapCat 官方安装脚本](https://github.com/NapNeko/NapCat-Installer/blob/main/script/install.ps1)，由向导在使用者机器下载，不随本项目分发。

## GitHub Actions

将**干净源码包的内容**放到仓库根，包含 `.github/workflows/windows-release.yml`。在 Actions 允许工作流运行，选择 Windows portable release → Run workflow，下载产物；其中 ZIP 才是给用户的包。

发布 Releases 时标签必须为 `v` + `src/version.py`（例如 v0.10.0）。release published 事件会针对该标签构建，通过测试后用仓库自己的短期 GITHUB_TOKEN 上传发布资产，不需硬编码个人 token。构建失败不会上传半成品。发布说明应指向 GETTING_STARTED.md，并清楚区分 Windows 包与源码包。

本工作流已写入源码；是否在你的 GitHub 仓库成功运行，需要实际上传后观察 Actions。此地不声称远端流水线已通过。
